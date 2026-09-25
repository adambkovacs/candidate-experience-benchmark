import copy
from decimal import Decimal
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gemini_repeat_study as study


class GeminiRepeatStudyTests(unittest.TestCase):
    def test_four_plans_bind_two_exact_historical_triples(self):
        for config, (_, model, partition) in study.CONFIGS.items():
            for repeat, order in study.ORDERS.items():
                plan = study.expected_plan(config, repeat)
                self.assertEqual(plan['condition_order'], list(order))
                self.assertEqual(plan['model'], model)
                self.assertEqual(plan['partition_id'], partition)
                self.assertEqual(plan['proposed_partition_cap_usd'], '0.30')
                self.assertFalse(plan['partition_allocated'])
                self.assertEqual(plan['original_p0_baseline_id'], config)
                for condition in ('P0', 'P1', 'P2'):
                    requests = plan['conditions'][condition]['requests']
                    self.assertEqual(len(requests), 7)
                    self.assertEqual(requests[0]['record_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
                    self.assertEqual([rid for group in requests[1:] for rid in group['record_ids']],
                                     [f'DEV-{i:03}' for i in range(1, 61)])
                    for request in requests:
                        payload = request['payload']
                        self.assertEqual(payload['model'], model)
                        self.assertEqual(payload['temperature'], 0)
                        self.assertEqual(payload['max_tokens'], 8192)
                        self.assertEqual(payload['reasoning'], {'enabled': True, 'effort': 'low'})
                        self.assertEqual(payload['provider']['only'], ['google-ai-studio'])
                        self.assertFalse(payload['provider']['allow_fallbacks'])
                        self.assertEqual(payload['tools'], [])
                        self.assertEqual(payload['tool_choice'], 'none')
                        self.assertEqual(payload['plugins'], [{'id': 'web', 'enabled': False},
                                                               {'id': 'response-healing', 'enabled': False}])
                        self.assertEqual(request['payload_sha256'], study.v3.sha(study.v3.canon(payload)))

    def test_plan_tampering_and_wrong_parent_rejected(self):
        plan = study.expected_plan('gemini36-flash-low-p0-openrouter-v3', 'repeat2')
        with tempfile.TemporaryDirectory(dir=study.BASE) as name:
            path = Path(name) / 'plan.json'
            raw = (json.dumps(plan) + '\n').encode()
            path.write_bytes(raw)
            self.assertEqual(study.validate_plan(path, hashlib.sha256(raw).hexdigest()), plan)
            bad = copy.deepcopy(plan)
            bad['conditions']['P1']['requests'][1]['payload']['temperature'] = 1
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, 'differs'):
                study.validate_plan(path)
            bad = copy.deepcopy(plan)
            bad['original_p0_baseline_id'] = 'new-repeat-p0'
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, 'differs'):
                study.validate_plan(path)

    def test_order_gate_keeps_unsent_phases_closed(self):
        plan = study.expected_plan('gemini37-flash-low-p0-openrouter-v3', 'repeat2')
        study.require_order(plan, 'P1', 'smoke')
        with self.assertRaisesRegex(ValueError, 'Prior condition'):
            study.require_order(plan, 'P2', 'smoke')
        with self.assertRaisesRegex(ValueError, 'inspected smoke'):
            study.require_order(plan, 'P1', 'development')

    def test_live_catalog_drift_rejected_before_key(self):
        plan = study.expected_plan('gemini36-flash-low-p0-openrouter-v3', 'repeat2')
        condition = plan['conditions']['P1']
        cat = json.loads(study.bound(condition['catalog']).read_text())
        eps = json.loads(study.bound(condition['endpoints']).read_text())
        with mock.patch.object(study.v3, 'fetch', side_effect=[cat, eps]):
            _, endpoint = study.live_controls(plan, 'P1')
        self.assertEqual(endpoint['tag'], 'google-ai-studio')
        altered = copy.deepcopy(eps)
        item = next(x for x in altered['data']['endpoints'] if x.get('tag') == 'google-ai-studio')
        item['pricing']['prompt'] = '0.00000074'
        with mock.patch.object(study.v3, 'fetch', side_effect=[cat, altered]):
            with self.assertRaisesRegex(ValueError, 'price|payload'):
                study.live_controls(plan, 'P1')

    def test_truncated_http_error_saved_before_any_parsing(self):
        class Broken:
            def read(self, _limit):
                raise http.client.IncompleteRead(b'{"error":"cut synthetic-key', 8)
            def close(self):
                pass
        request = study.expected_plan('gemini37-flash-low-p0-openrouter-v3', 'repeat2')['conditions']['P1']['requests'][1]
        error = urllib.error.HTTPError('https://invalid.example', 429, 'limited',
                                       {'retry-after': '8'}, Broken())
        with tempfile.TemporaryFile(mode='w+') as output:
            saved = study.capture_http_error(error, 'synthetic-key', output, request, 'attempt-1')
            output.seek(0)
            persisted = json.loads(output.readline())
        self.assertEqual(saved, persisted)
        self.assertEqual(persisted['http_status'], 429)
        self.assertEqual(persisted['read_error'], 'IncompleteRead')
        self.assertEqual(persisted['record_ids'], request['record_ids'])
        self.assertIn('[REDACTED]', persisted['error_body'])
        self.assertNotIn('synthetic-key', json.dumps(persisted))
        error.close()

    def test_smoke_saves_raw_before_parse_and_stops_without_retry(self):
        config = 'gemini36-flash-low-p0-openrouter-v3'
        plan = study.expected_plan(config, 'repeat2')
        order = []
        class Ledger:
            cap = Decimal('0.30')
            def __init__(self):
                self.reserved = []
                self.settled = []
                self.closed = False
            def state(self):
                return {}, set(), False
            def reserve(self, amount, rid):
                self.reserved.append((amount, rid))
                return 'synthetic-batch-1'
            def settle(self, attempt, actual):
                self.settled.append((attempt, actual))
                return True
            def close(self):
                self.closed = True
        ledger = Ledger()
        with tempfile.TemporaryDirectory(dir=study.BASE) as name:
            root = Path(name)
            plan_file = root / 'manifest.json'
            raw_plan = (json.dumps(plan) + '\n').encode()
            plan_file.write_bytes(raw_plan)
            plan_sha = hashlib.sha256(raw_plan).hexdigest()
            review = root / 'review.json'
            review.write_text('{}')
            def paths(_config, _repeat, _condition, phase):
                return {key: root / f'{phase}.{key}' for key in
                        ('claim', 'journal', 'attempts', 'responses', 'records')}
            def open_budget(*_args):
                order.append('budget')
                return ledger
            def key(_path):
                order.append('key')
                return 'synthetic-key'
            def saved_fetch(_payload, _token, _timeout, output, rid, attempt, request_sha):
                body = {'model': plan['model'], 'provider': study.v3.PROVIDER_NAME,
                        'usage': {'cost': '0.0001'}, 'choices': []}
                study.v3.durable(output, {'id': rid, 'attempt_id': attempt,
                                          'request_sha256': request_sha,
                                          'body_base64': 'e30='})
                self.assertTrue(paths(None, None, None, 'smoke')['responses'].read_text())
                return body
            with mock.patch.object(study, 'phase_paths', side_effect=paths), \
                 mock.patch.object(study, 'review_gate', return_value=root / 'unused-budget'), \
                 mock.patch.object(study, 'live_controls', return_value=({}, {'context_length': 1048576})), \
                 mock.patch.object(study, 'open_partition', side_effect=open_budget), \
                 mock.patch.object(study.v3, 'load_key', side_effect=key), \
                 mock.patch.object(study.wave, 'fetch_recorded', side_effect=saved_fetch):
                self.assertFalse(study.run(plan_file, plan_sha, review, 'P1', 'smoke'))
            attempts = study.lines(paths(None, None, None, 'smoke')['attempts'])
            journal = study.lines(paths(None, None, None, 'smoke')['journal'])
            self.assertEqual(order, ['budget', 'key'])
            self.assertEqual(len(ledger.reserved), 1)
            self.assertEqual(ledger.settled, [('synthetic-batch-1', Decimal('0.0001'))])
            self.assertTrue(ledger.closed)
            self.assertEqual(attempts[0]['status'], 'control_violation')
            self.assertEqual(journal[-1]['event'], 'phase_stopped')

    def test_offline_parser_keeps_provider_and_tool_controls(self):
        plan = study.expected_plan('gemini36-flash-low-p0-openrouter-v3', 'repeat2')
        condition = plan['conditions']['P1']
        historical = study.lines(study.bound(condition['historical']['development_attempts']))[0]
        endpoint = json.loads(study.bound(condition['endpoints']).read_text())
        _, selected = study.v3.check_catalog(plan['model'], 'low',
                                              json.loads(study.bound(condition['catalog']).read_text()), endpoint)
        body = copy.deepcopy(historical['raw_response'])
        result = study.classify(plan, condition['requests'][1], body, selected)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['predictions']), 10)
        body['choices'][0]['message']['tool_calls'] = [{'id': 'unwanted'}]
        self.assertEqual(study.classify(plan, condition['requests'][1], body, selected)['status'],
                         'control_violation')


if __name__ == '__main__':
    unittest.main()
