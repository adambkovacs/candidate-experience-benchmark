"""Fake provider and ledger tests for the paid repeat execution gates."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import copy
import io
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_repeat_execution as execution
import openrouter_repeat_study as study

SHA = '7069119bcb1d4d8f8cfe00e4aa136c47ca4b10995a2e3261ba13386076cff4bb'
PREDICTION = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}
ENDPOINT = {'model_id': study.MODEL, 'provider_name': 'DeepInfra',
            'tag': study.PROVIDER, 'context_length': 262144}


def response(status='ok', cost='0.0001'):
    model = study.MODEL if status != 'model_mismatch' else 'wrong/model'
    content = json.dumps(PREDICTION) if status != 'invalid_output' else 'invalid json'
    return {'model': model, 'provider': 'DeepInfra',
            'usage': {'cost': cost, 'prompt_tokens': 100, 'completion_tokens': 20},
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}


class FakeLedger:
    def __init__(self, events):
        self.events = events
        self.cap = execution.paid.number('0.20')
        self.closed = False

    def reserve(self, amount, rid):
        self.events.append(('reserve', rid))
        return 'attempt-' + rid

    def settle(self, attempt, actual):
        self.events.append(('settle', attempt, actual))
        return actual is not None

    def close(self):
        self.closed = True


class ExecutionTest(unittest.TestCase):
    def setUp(self):
        self.plan = study.plan_data('repeat2')

    def test_order_blocks_skip_before_key_and_claim(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'verify', return_value=self.plan), patch.object(
                    execution.paid, 'load_key', side_effect=AssertionError('key read')):
                with self.assertRaisesRegex(ValueError, 'Prior condition incomplete'):
                    execution.execute('repeat2', 'P1', 'smoke', SHA, '/unused')
            self.assertFalse((Path(temp) / 'repeat2' / 'P1').exists())

    def test_root_review_blocks_before_key_and_claim(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'verify', return_value=self.plan), patch.object(
                    execution, 'review_receipt', side_effect=ValueError('review missing')):
                with patch.object(execution.paid, 'load_key', side_effect=AssertionError('key read')):
                    with self.assertRaisesRegex(ValueError, 'review missing'):
                        execution.execute('repeat2', 'P2', 'smoke', SHA, '/unused')
            self.assertFalse((Path(temp) / 'repeat2' / 'P2').exists())

    def test_receipt_rejects_changed_controller(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'review.json'
            path.write_text(json.dumps({'schema': execution.RECEIPT_SCHEMA,
                                        'approved': True, 'configuration_id': study.CONFIG,
                                        'partition_cap_usd': study.CAP_USD,
                                        'controller_sha256': '0' * 64}))
            with self.assertRaisesRegex(ValueError, 'controller hash differs'):
                execution.review_receipt(path, 'repeat2', SHA)

    def test_receipt_binds_both_plans_policy_and_budget_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            budget = root / 'partition.json'
            budget.write_text('{"version":"paid-partitions-v1"}\n')
            master = root / 'master.jsonl'
            receipt_path = root / 'review.json'
            plans = {r: study.sha(study.BASE / r / 'manifest.json') for r in study.ORDERS}
            receipt = {'schema': execution.RECEIPT_SCHEMA, 'approved': True,
                       'configuration_id': study.CONFIG, 'partition_cap_usd': study.CAP_USD,
                       'controller_sha256': study.sha(execution.__file__),
                       'hosted_execution_sha256': study.sha(execution.HOSTED_EXECUTION),
                       'plan_sha256': plans, 'master_ledger': str(master),
                       'budget_manifest': {'path': 'partition.json', 'sha256': study.sha(budget)},
                       'partition_id': 'gemma26'}
            receipt_path.write_text(json.dumps(receipt))
            with patch.object(execution, 'ROOT', root), patch.object(execution, 'MASTER', master):
                value, path = execution.review_receipt(receipt_path, 'repeat2', plans['repeat2'])
                self.assertEqual(path, budget.resolve())
                self.assertEqual(value['partition_id'], 'gemma26')
                budget.write_text('{}\n')
                with self.assertRaisesRegex(ValueError, 'Bound file changed'):
                    execution.review_receipt(receipt_path, 'repeat2', plans['repeat2'])

    def test_changed_endpoint_price_blocks_before_key_or_claim(self):
        old = json.loads((ROOT / 'results/hosted-prompt-preparation-2026-09-24'
                          '/openrouter-paid-gemma4-26b-a4b-off/historical-attempts.jsonl').read_text().splitlines()[0])
        endpoint = copy.deepcopy(old['provider_endpoint'])
        endpoint['pricing']['completion'] = '0.00000035'
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'verify', return_value=self.plan), patch.object(
                    execution, 'review_receipt', return_value=({'partition_id': 'gemma26'}, Path('/unused'))), patch.object(
                    execution.paid, 'fetch', side_effect=[{'data': [old['model_catalog_entry']]},
                                                           {'data': {'id': study.MODEL, 'endpoints': [endpoint]}}]), patch.object(
                    execution.paid, 'load_key', side_effect=AssertionError('key read')):
                with self.assertRaises(ValueError):
                    execution.execute('repeat2', 'P2', 'smoke', SHA, '/unused')
            self.assertFalse((Path(temp) / 'repeat2' / 'P2').exists())

    def run_fake_smoke(self, outcomes):
        events = []
        ledger = FakeLedger(events)
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            review = Path(temp) / 'review.json'
            review.write_text('{}')
            with patch.object(study, 'verify', return_value=self.plan), patch.object(
                    execution, 'review_receipt', return_value=({'partition_id': 'gemma26'}, Path('/unused'))), patch.object(
                    execution, 'live_controls', return_value=({}, ENDPOINT, execution.paid.number('0.01974272'))), patch.object(
                    execution, 'budget_gate', return_value=ledger), patch.object(
                    execution.paid, 'load_key', return_value='fake-token'):
                remaining = iter(outcomes)
                def fake_fetch(path, token, payload, timeout):
                    self.assertEqual(path, '/chat/completions')
                    self.assertEqual(events[-1][0], 'reserve')
                    events.append(('fetch', payload['messages'][1]['content']))
                    item = next(remaining)
                    if isinstance(item, BaseException):
                        raise item
                    return item
                with patch.object(execution.paid, 'fetch', side_effect=fake_fetch):
                    completed = execution.execute('repeat2', 'P2', 'smoke', SHA, str(review))
            folder = Path(temp) / 'repeat2' / 'P2'
            rows = [json.loads(x) for x in (folder / 'smoke.attempts.jsonl').read_text().splitlines()]
            journal = [json.loads(x)['event'] for x in (folder / 'smoke.journal.jsonl').read_text().splitlines()]
            self.assertTrue((folder / 'smoke.claim.json').exists())
            self.raw_rows = [json.loads(x) for x in (folder / 'smoke.responses.jsonl').read_text().splitlines()]
        self.assertTrue(ledger.closed)
        return completed, rows, journal, events

    def test_three_successful_smoke_calls_are_durable(self):
        completed, rows, journal, events = self.run_fake_smoke([response()] * 3)
        self.assertTrue(completed)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['id'] for r in rows], ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertEqual(journal[-1], 'phase_completed')
        self.assertEqual([e[0] for e in events], ['reserve', 'fetch', 'settle'] * 3)

    def test_unknown_cost_stops_and_retains_started_attempt(self):
        completed, rows, journal, events = self.run_fake_smoke([response(cost=None)])
        self.assertFalse(completed)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['cost_unknown'])
        self.assertFalse(rows[0]['billing_ok'])
        self.assertEqual(journal[-1], 'phase_stopped')
        self.assertEqual([e[0] for e in events], ['reserve', 'fetch', 'settle'])

    def test_identity_mismatch_stops_without_second_reserve(self):
        completed, rows, journal, events = self.run_fake_smoke([response(status='model_mismatch')])
        self.assertFalse(completed)
        self.assertEqual(rows[0]['status'], 'model_mismatch')
        self.assertEqual(journal[-1], 'phase_stopped')
        self.assertEqual(len([e for e in events if e[0] == 'reserve']), 1)

    def test_smoke_inspection_binds_three_valid_attempts(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'verify', return_value=self.plan):
                folder, _, journal, attempts = execution.phase_paths('repeat2', 'P2', 'smoke')
                folder.mkdir(parents=True)
                journal.write_text(json.dumps({'event': 'phase_completed'}) + '\n')
                attempts.write_text(''.join(json.dumps({'id': f'DEV-{i:03d}', 'status': 'ok',
                                                        'billing_ok': True, 'cost_unknown': False}) + '\n'
                                            for i in range(1, 4)))
                execution.inspect('repeat2', 'P2', SHA, 'Three raw responses checked')
                execution.require_order(self.plan, 'P2', 'development')
                attempts.write_text(attempts.read_text() + '{}\n')
                with self.assertRaisesRegex(ValueError, 'Smoke inspection binding changed'):
                    execution.require_order(self.plan, 'P2', 'development')

    def test_intrinsic_invalid_stops_under_frozen_gemma_policy(self):
        original = json.loads((ROOT / 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json').read_text())
        config = next(x for x in original['configurations'] if x['id'] == study.CONFIG)
        self.assertIs(config['continue_on_invalid_output'], False)
        row = {'status': 'invalid_output', 'billing_ok': True, 'cost_unknown': False,
               'raw_response': response('invalid_output'),
               'response_diagnostic': {'blockers': [], 'passed': True}}
        self.assertFalse(execution.CONTINUE_INTRINSIC_INVALID)
        self.assertFalse(execution.continue_record(row, 'development'))
        self.assertFalse(execution.continue_record(row, 'smoke'))
        row['raw_response']['choices'][0]['message']['function_call'] = {'name': 'x'}
        self.assertFalse(execution.continue_record(row, 'development'))




    def test_http_error_evidence(self):
        error = urllib.error.HTTPError('https://example.invalid', 429, 'Limited',
            {'retry-after': '60', 'x-request-id': 'req-123'}, io.BytesIO(b'{"error":"fake-token limited"}'))
        completed, rows, journal, events = self.run_fake_smoke([error])
        self.assertFalse(completed)
        self.assertEqual(rows[0]['error_body'], '{"error":"[REDACTED] limited"}')
        self.assertEqual(rows[0]['error_headers']['retry-after'], '60')
        self.assertEqual(self.raw_rows[0]['attempt_id'], rows[0]['attempt_id'])
        self.assertTrue(rows[0]['cost_unknown'])
        self.assertEqual(len([e for e in events if e[0] == 'fetch']), 1)

    def test_malformed_response_retained(self):
        for body in (response(cost='N/A'), {**response(), 'choices': [None]}):
            with self.subTest(body=body):
                completed, rows, journal, events = self.run_fake_smoke([body])
                self.assertFalse(completed)
                self.assertEqual(rows[0]['raw_response'], body)
                self.assertEqual(self.raw_rows[0]['raw_response'], body)
                self.assertEqual(self.raw_rows[0]['attempt_id'], rows[0]['attempt_id'])

if __name__ == '__main__':
    unittest.main()
