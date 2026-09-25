"""Offline controls for the separate paid Gemini batch surface."""
import copy
import contextlib
import io
import tempfile
import urllib.error
from types import SimpleNamespace
from unittest import mock
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini_openrouter_batch_v3 as g


class GeminiOpenRouterBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((g.PREP / 'catalog.json').read_text())

    def endpoint(self, model, effort):
        path = g.PREP / (model.split('/')[1] + '-endpoints.json')
        return g.check_catalog(model, effort, self.catalog, json.loads(path.read_text()))[1]

    def test_exact_roster_efforts_and_standard_endpoint(self):
        self.assertEqual(sum(map(len, g.ROSTER.values())), 10)
        for model, efforts in g.ROSTER.items():
            for effort in efforts:
                endpoint = self.endpoint(model, effort)
                self.assertEqual(endpoint['tag'], 'google-ai-studio')
                self.assertEqual(endpoint['status'], 0)
        with self.assertRaises(ValueError):
            self.endpoint('google/gemini-3.1-pro-preview', 'xhigh')
        with self.assertRaises(ValueError):
            self.endpoint('google/gemini-3.6-flash', 'high')

    def test_frozen_batch_membership_and_no_tools_or_search(self):
        model = 'google/gemini-3.8-flash'
        endpoint = self.endpoint(model, 'high')
        for variant in ('P0', 'P1', 'P2'):
            requests = g.prepared_requests(model, 'high', variant, 'hosted-gemini38-high-p0', endpoint)
            self.assertEqual(len(requests), 7)
            self.assertEqual(requests[0]['record_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
            self.assertEqual([len(r['record_ids']) for r in requests[1:]], [10] * 6)
            self.assertEqual([x for r in requests[1:] for x in r['record_ids']], [f'DEV-{i:03}' for i in range(1, 61)])
            for request in requests:
                payload = request['payload']
                self.assertEqual(payload['tools'], [])
                self.assertEqual(payload['tool_choice'], 'none')
                self.assertIn({'id': 'web', 'enabled': False}, payload['plugins'])
                self.assertIn({'id': 'response-healing', 'enabled': False}, payload['plugins'])
                self.assertFalse('references' in g.canon(payload).decode().lower())
                self.assertEqual(request['payload_sha256'], g.sha(g.canon(payload)))
                self.assertLess(len(g.canon(payload)) + g.ALLOWANCE_TOKENS, g.CONTEXT_THRESHOLD)

    def test_max_price_text_only_filter_keeps_multimodal_endpoint(self):
        model = 'google/gemini-3.8-flash'
        endpoint = self.endpoint(model, 'low')
        self.assertGreater(g.price(endpoint['pricing']['image']), 0)
        payload = g.prepared_requests(model, 'low', 'P0', 'hosted-gemini38-low-p0', endpoint)[0]['payload']
        self.assertEqual(payload['provider']['max_price'], {'prompt': 0.75, 'completion': 3.75})
        self.assertEqual(payload['provider']['only'], ['google-ai-studio'])
        self.assertFalse(payload['provider']['allow_fallbacks'])
        self.assertTrue(payload['provider']['require_parameters'])
        self.assertEqual([m['role'] for m in payload['messages']], ['user'])
        self.assertTrue(all(isinstance(m['content'], str) for m in payload['messages']))
        self.assertNotIn('image_config', payload)
        self.assertEqual(payload['tools'], [])
        self.assertEqual(payload['tool_choice'], 'none')

    def test_pricing_drift_and_additional_categories_fail_closed(self):
        model = 'google/gemini-3.1-pro-preview'
        path = g.PREP / 'gemini-3.1-pro-preview-endpoints.json'
        original = json.loads(path.read_text())
        model_entry, endpoint = g.check_catalog(model, 'low', self.catalog, original)
        self.assertTrue(model_entry['reasoning']['mandatory'])
        changed = copy.deepcopy(original)
        target = next(e for e in changed['data']['endpoints'] if e['tag'] == g.PROVIDER)
        target['pricing']['new_fee'] = '0.1'
        with self.assertRaises(ValueError):
            g.check_catalog(model, 'low', self.catalog, changed)
        changed = copy.deepcopy(original)
        target = next(e for e in changed['data']['endpoints'] if e['tag'] == g.PROVIDER)
        target['pricing']['internal_reasoning'] = '0.1'
        with self.assertRaises(ValueError):
            g.check_catalog(model, 'low', self.catalog, changed)
        requests = g.prepared_requests(model, 'low', 'P0', 'hosted-pro-low-p0', endpoint)
        self.assertGreater(g.Decimal(requests[0]['reserve_usd']), 0)
        self.assertLess(g.Decimal(requests[0]['reserve_usd']), g.Decimal('0.30'))


    def fake_run(self, mode):
        model, effort = 'google/gemini-3.1-pro-preview', 'low'
        endpoint_doc = json.loads((g.PREP / 'gemini-3.1-pro-preview-endpoints.json').read_text())
        endpoint = self.endpoint(model, effort)
        with tempfile.TemporaryDirectory(prefix='gemini-controller-test-', dir=ROOT / 'results') as temp:
            folder = Path(temp)
            prepared = folder / 'condition'
            args = SimpleNamespace(model=model, effort=effort, variant='P0',
                                   configuration_id='gemini-test-p0', parent_p0=None,
                                   timeout=300, output_dir=str(prepared))
            with contextlib.redirect_stdout(io.StringIO()):
                g.prepare(args)
            manifest_path = prepared / 'manifest.json'
            manifest_sha = g.sha(manifest_path.read_bytes())
            partition = folder / 'budget.json'
            partition.write_text('{}\n')
            receipt = folder / 'approval.json'
            receipt.write_text(json.dumps({'schema': 'gemini-openrouter-run-approval-v3',
                'approved': True, 'manifest_sha256': manifest_sha, 'phase': 'smoke',
                'budget_manifest_sha256': g.sha(partition.read_bytes()),
                'partition_id': 'fake-partition'}))
            run_args = SimpleNamespace(manifest=str(manifest_path), manifest_sha256=manifest_sha,
                phase='smoke', budget_manifest=str(partition), partition_id='fake-partition',
                approval=str(receipt), smoke_inspection=None, env_file=None)
            class FakeLedger:
                master_cap = g.Decimal(10)
                def __init__(self):
                    self.reserves = []
                    self.settlements = []
                    self.closed = False
                def reserve(self, amount, record_id):
                    if mode == 'cap':
                        raise ValueError('cap reached')
                    self.reserves.append((amount, record_id))
                    return 'fake-attempt-1'
                def settle(self, attempt, actual):
                    self.settlements.append((attempt, actual))
                    return actual is not None
                def close(self):
                    self.closed = True
            ledger = FakeLedger()
            paid_calls = []
            metadata_calls = 0
            def fake_fetch(path, *args, **kwargs):
                nonlocal metadata_calls
                if path == '/models':
                    return self.catalog
                if path.endswith('/endpoints'):
                    return endpoint_doc
                if path.startswith('/generation?id='):
                    metadata_calls += 1
                    if mode in ('metadata-missing', 'missing-provider-timeout') or (mode == 'missing-provider-late' and metadata_calls < 5):
                        raise urllib.error.HTTPError('https://openrouter.ai/api/v1/generation', 404, 'not indexed', {}, None)
                    return {'data': {'id': 'gen-test', 'model': endpoint['name'].split(' | ', 1)[1],
                        'provider_name': 'Wrong Provider' if mode == 'metadata-conflict' else g.PROVIDER_NAME,
                        'generation_time': 111, 'latency': 222,
                        'native_tokens_reasoning': 90, 'total_cost': 0.01, 'num_fetches': 0, 'num_search_results': 0}}
                self.assertEqual(path, '/chat/completions')
                paid_calls.append(args[1])
                if mode == 'error':
                    raise RuntimeError('provider failed')
                records = [{'id': f'DEV-{i:03}', 'sentiment': 'neutral',
                    'follow_up_needed': 'no', 'serious_concern_reported': 'no',
                    'testimonial_potential': 'no'} for i in range(1, 4)]
                response = {'id': 'gen-test', 'model': endpoint['name'].split(' | ', 1)[1],
                    'provider': 'Wrong Provider' if mode == 'wrong-provider' else g.PROVIDER_NAME,
                    'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'records': records})}}],
                    'usage': {'prompt_tokens': 4000, 'completion_tokens': 200,
                              'cost': 0.01, 'completion_tokens_details': {'reasoning_tokens': 90}}}
                if mode == 'unknown':
                    del response['usage']['cost']
                    response['id'] = None
                if mode in ('missing-provider-late', 'missing-provider-timeout'):
                    del response['provider']
                if mode == 'tool-use':
                    response['usage']['server_tool_use_details'] = {'tool_calls_executed': 1}
                return response
            with mock.patch.object(g, 'fetch', side_effect=fake_fetch), \
                 mock.patch.object(g, 'load_key', return_value=None if mode == 'blank-key' else 'test-key'), \
                 mock.patch.object(g, 'open_partition', return_value=ledger), \
                 mock.patch.object(g.time, 'sleep'), \
                 contextlib.redirect_stdout(io.StringIO()):
                if mode in ('cap', 'blank-key'):
                    with self.assertRaises(ValueError):
                        g.run(run_args)
                else:
                    g.run(run_args)
            if mode == 'blank-key':
                self.assertFalse((prepared / 'smoke-journal.jsonl').exists())
                return paid_calls, ledger, [], [], []
            journal = [json.loads(x) for x in (prepared / 'smoke-journal.jsonl').read_text().splitlines()]
            attempts = [json.loads(x) for x in (prepared / 'smoke-attempts.jsonl').read_text().splitlines()]
            rows = [json.loads(x) for x in (prepared / 'smoke-records.jsonl').read_text().splitlines()]
            return paid_calls, ledger, journal, attempts, rows

    def test_revision_accepted_and_terminal_success(self):
        paid, ledger, journal, attempts, rows = self.fake_run('success')
        self.assertEqual(len(paid), 1)
        self.assertEqual(len(ledger.reserves), 1)
        self.assertEqual(len(ledger.settlements), 1)
        self.assertEqual(attempts[0]['status'], 'ok')
        self.assertIn(attempts[0]['returned_model'], attempts[0]['allowed_returned_models'])
        self.assertEqual(attempts[0]['usage']['completion_tokens_details']['reasoning_tokens'], 90)
        self.assertEqual(attempts[0]['generation_metadata']['generation_time'], 111)
        self.assertEqual(attempts[0]['generation_metadata']['provider_name'], g.PROVIDER_NAME)
        self.assertEqual(len(rows), 3)
        self.assertEqual(journal[-1]['reason'], 'completed')
        self.assertTrue(journal[-1]['completed'])

    def test_unknown_cost_stops_with_one_paid_request(self):
        paid, ledger, journal, attempts, rows = self.fake_run('unknown')
        self.assertEqual(len(paid), 1)
        self.assertEqual(len(ledger.reserves), 1)
        self.assertEqual(ledger.settlements, [('fake-attempt-1', None)])
        self.assertTrue(attempts[0]['cost_unknown'])
        self.assertFalse(journal[-1]['completed'])
        self.assertEqual(journal[-1]['reason'], 'billing_unknown_or_overrun')
        self.assertEqual(len(rows), 3)

    def test_exact_response_provider_admits_missing_telemetry_with_known_cost(self):
        paid, ledger, journal, attempts, rows = self.fake_run('metadata-missing')
        self.assertEqual(len(paid), 1)
        self.assertEqual(attempts[0]['status'], 'ok')
        self.assertEqual(attempts[0]['generation_telemetry_status'], 'pending')
        self.assertEqual(attempts[0]['observed_cost_usd'], '0.01')
        self.assertTrue(journal[-1]['completed'])

    def test_missing_provider_falls_back_to_metadata(self):
        paid, ledger, journal, attempts, rows = self.fake_run('missing-provider-late')
        self.assertEqual(len(paid), 1)
        self.assertEqual(attempts[0]['status'], 'ok')
        self.assertEqual(attempts[0]['generation_telemetry_status'], 'verified')

    def test_missing_provider_and_metadata_stops_without_post_retry(self):
        paid, ledger, journal, attempts, rows = self.fake_run('missing-provider-timeout')
        self.assertEqual(len(paid), 1)
        self.assertEqual(attempts[0]['status'], 'identity_unverified')
        self.assertFalse(journal[-1]['completed'])

    def test_wrong_response_provider_stops_even_if_metadata_is_clean(self):
        paid, ledger, journal, attempts, rows = self.fake_run('wrong-provider')
        self.assertEqual(len(paid), 1)
        self.assertEqual(attempts[0]['status'], 'identity_violation')
        self.assertFalse(journal[-1]['completed'])

    def test_conflicting_metadata_stops_even_if_response_provider_is_clean(self):
        paid, ledger, journal, attempts, rows = self.fake_run('metadata-conflict')
        self.assertEqual(len(paid), 1)
        self.assertEqual(attempts[0]['status'], 'identity_violation')
        self.assertFalse(journal[-1]['completed'])

    def test_server_tool_usage_stops(self):
        paid, ledger, journal, attempts, rows = self.fake_run('tool-use')
        self.assertEqual(len(paid), 1)
        self.assertEqual(attempts[0]['status'], 'control_violation')
        self.assertFalse(journal[-1]['completed'])

    def test_provider_error_stops_without_duplicate_request(self):
        paid, ledger, journal, attempts, rows = self.fake_run('error')
        self.assertEqual(len(paid), 1)
        self.assertEqual(len(ledger.reserves), 1)
        self.assertEqual(attempts[0]['status'], 'service_error')
        self.assertTrue(attempts[0]['cost_unknown'])
        self.assertFalse(journal[-1]['completed'])
        self.assertEqual(journal[-1]['reason'], 'billing_unknown_or_overrun')
        self.assertEqual(len(rows), 3)

    def test_empty_key_fails_before_ledger_or_paid_request(self):
        paid, ledger, journal, attempts, rows = self.fake_run('blank-key')
        self.assertEqual(paid, [])
        self.assertEqual(ledger.reserves, [])
        self.assertEqual(journal, [])

    def test_budget_cap_stops_before_paid_request_with_terminal(self):
        paid, ledger, journal, attempts, rows = self.fake_run('cap')
        self.assertEqual(paid, [])
        self.assertEqual(ledger.reserves, [])
        self.assertEqual(attempts, [])
        self.assertEqual(rows, [])
        self.assertEqual(journal[-1]['reason'], 'exception:ValueError')
        self.assertEqual(journal[-1]['started_batches'], 0)
        self.assertFalse(journal[-1]['completed'])


if __name__ == '__main__':
    unittest.main()
