"""Offline gates and real temporary-ledger exercises for DeepSeek high."""
import base64
from decimal import Decimal
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_budget_v2 as budgets
import paid_budget_partitions_v2 as partitions
import qwen27_fresh_repeat_execution as canonical
import deepseek_high_fresh_repeat_study as study
import deepseek_high_fresh_repeat_execution as wrapped

run = wrapped.runner
PREDICTION = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {'content-type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, limit):
        return self.body.read(limit)


class DeepSeekHighExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = study.plan_data('fresh1')
        cls.plan_sha = study.sha(study.BASE / 'fresh1/manifest.json')
        cls.old_endpoint = json.loads((study.ROOT / study.ROUTE_AUDIT).read_text())['selected_endpoint']
        cls.old_model = study.historical_rows(json.loads((study.ROOT / study.AUDIT).read_text()), 'P0')['DEV-001']['model_catalog_entry']

    def response(self, cost='0.0001'):
        return {'model': study.MODEL, 'provider': study.PROVIDER_NAME,
                'usage': {'cost': cost, 'prompt_tokens': 100, 'completion_tokens': 20},
                'choices': [{'finish_reason': 'stop',
                             'message': {'content': json.dumps(PREDICTION)}}]}

    def fixture(self, temp):
        base = Path(temp) / 'plans'
        manifest = base / 'fresh1/manifest.json'
        manifest.parent.mkdir(parents=True)
        shutil.copy2(study.BASE / 'fresh1/manifest.json', manifest)
        return base, manifest, Path(temp) / 'child.jsonl'

    def stage(self, base, child, phase, responses, invalid_length=False):
        items = iter(responses)
        review = base / 'offline-review.json'
        review.write_text('{"fixture":true}\n')

        def opener(request, timeout):
            self.assertEqual(request.full_url, run.transport.BASE + '/chat/completions')
            self.assertEqual(timeout, study.TIMEOUT)
            item = next(items)
            if isinstance(item, Exception):
                raise item
            return FakeResponse(item if isinstance(item, bytes) else json.dumps(item).encode())

        def gate(_receipt, _path, config):
            self.assertEqual(config, study.CONFIG)
            return budgets.BudgetLedger(child, cap_limit=study.PROPOSED_CHILD)

        with patch.object(wrapped._Study, 'BASE', wrapped._BasePath(base)), \
             patch.object(wrapped._Study, 'verify', return_value=self.plan), \
             patch.object(run, 'review_receipt', return_value=({'partition_id': 'temp'}, Path('/unused'))), \
             patch.object(run, 'live_controls', return_value=(self.old_model, self.old_endpoint, study.RESERVE)), \
             patch.object(run, 'budget_gate', side_effect=gate), \
             patch.object(run.paid, 'load_key', return_value='fake-key'), \
             patch.object(run.transport.OPENER, 'open', side_effect=opener), \
             patch.object(run, 'audit_response', side_effect=(
                 lambda record, *_: {'passed': False, 'blockers': ['truncation:length']}
                 if invalid_length and record.get('finish_reason') == 'length'
                 else {'passed': True, 'blockers': []})):
            return run.execute(study.CONFIG, 'fresh1', 'P0', phase,
                               study.sha(base / 'fresh1/manifest.json'), review)

    def test_private_import_does_not_modify_qwen27_runner(self):
        self.assertIsNot(run, canonical)
        self.assertIs(canonical.study.CONFIGS, sys.modules['qwen27_fresh_repeat_study'].CONFIGS)
        self.assertNotIn(study.CONFIG, canonical.study.CONFIGS)
        self.assertEqual(run.study.CONFIGS[study.CONFIG]['effort'], study.EFFORT)

    def test_execution_manifest_binds_three_plans_shared_transport_and_tests(self):
        expected = wrapped.execution_plan()
        self.assertEqual(expected['status'], 'offline_frozen_not_approved')
        self.assertEqual(len(expected['plans_sha256'][study.CONFIG]), 3)
        self.assertIn('qwen27_fresh_repeat_execution.py', expected['source_code_sha256'])
        self.assertIn('openrouter_benchmark.py', expected['source_code_sha256'])
        self.assertEqual(run.verify_execution_manifest(study.sha(run.EXECUTION_MANIFEST)), expected)
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            run.verify_execution_manifest('0' * 64)

    def test_live_route_price_limit_and_payload_check(self):
        import copy
        endpoint = copy.deepcopy(self.old_endpoint)
        catalog = {'data': [self.old_model]}
        endpoints = {'data': {'id': study.MODEL, 'endpoints': [endpoint]}}
        with patch.object(run.paid, 'fetch', side_effect=[catalog, endpoints]):
            _, selected, reserve = wrapped.live_controls(self.plan, 'P0')
        self.assertEqual(selected, endpoint)
        self.assertEqual(reserve, study.RESERVE)
        for key, value in [('max_prompt_tokens', 1), ('max_completion_tokens', 1),
                           ('pricing', {'prompt': '0.0000002', 'completion': '0.0000009'})]:
            altered = copy.deepcopy(endpoint)
            altered[key] = value
            with self.subTest(key=key), patch.object(run.paid, 'fetch',
                                                     side_effect=[catalog, {'data': {'id': study.MODEL, 'endpoints': [altered]} }]):
                with self.assertRaises(ValueError):
                    wrapped.live_controls(self.plan, 'P0')
        changed = copy.deepcopy(self.plan)
        changed['conditions']['P0']['development'][0]['payload']['temperature'] = 1
        with patch.object(run.paid, 'fetch', side_effect=[catalog, endpoints]):
            with self.assertRaisesRegex(ValueError, 'payload'):
                wrapped.live_controls(changed, 'P0')

    def test_smoke_inspection_then_full_development_and_no_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            base, manifest, child = self.fixture(temp)
            self.assertTrue(self.stage(base, child, 'smoke', [self.response()] * 3))
            with patch.object(wrapped._Study, 'BASE', wrapped._BasePath(base)), \
                 patch.object(wrapped._Study, 'verify', return_value=self.plan):
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    run.require_order(self.plan, 'P0', 'development')
                run.inspect(study.CONFIG, 'fresh1', 'P0', study.sha(manifest), 'Three raw bodies inspected.')
            self.assertTrue(self.stage(base, child, 'development', [self.response()] * 60))
            with patch.object(wrapped._Study, 'BASE', wrapped._BasePath(base)), \
                 patch.object(wrapped._Study, 'verify', return_value=self.plan):
                run.verify_phase_closure(self.plan, 'P0', 'development')
            with self.assertRaises(FileExistsError):
                self.stage(base, child, 'development', [self.response()] * 60)
            ledger = budgets.BudgetLedger(child, cap_limit=study.PROPOSED_CHILD)
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.0063'))
                self.assertEqual(ledger.state()[1], set())
                self.assertEqual(len([r for r in ledger.events if r['event'] == 'reserve']), 63)
            finally:
                ledger.close()

    def test_known_billed_length_invalid_retained_and_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base, manifest, child = self.fixture(temp)
            self.assertTrue(self.stage(base, child, 'smoke', [self.response()] * 3))
            with patch.object(wrapped._Study, 'BASE', wrapped._BasePath(base)), \
                 patch.object(wrapped._Study, 'verify', return_value=self.plan):
                run.inspect(study.CONFIG, 'fresh1', 'P0', study.sha(manifest),
                            'Three complete raw responses inspected.')
            invalid = self.response()
            invalid['choices'][0]['finish_reason'] = 'length'
            self.assertTrue(self.stage(base, child, 'development',
                                       [invalid] + [self.response()] * 59,
                                       invalid_length=True))
            attempts = run.jsonl(base / 'fresh1/P0/development.attempts.jsonl')
            self.assertEqual(len(attempts), 60)
            self.assertEqual(attempts[0]['status'], 'invalid_output')
            self.assertEqual(attempts[0]['observed_cost_usd'], '0.0001')
            with patch.object(wrapped._Study, 'BASE', wrapped._BasePath(base)), \
                 patch.object(wrapped._Study, 'verify', return_value=self.plan):
                wrapped.verify_phase_closure(self.plan, 'P0', 'development')

    def test_malformed_200_raw_before_parse_unknown_bound_and_no_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            malformed = b'{"choices": [incomplete'
            self.assertFalse(self.stage(base, child, 'smoke', [malformed]))
            folder = base / 'fresh1/P0'
            raw = run.jsonl(folder / 'smoke.responses.jsonl')
            attempts = run.jsonl(folder / 'smoke.attempts.jsonl')
            self.assertEqual(base64.b64decode(raw[0]['body_base64']), malformed)
            self.assertEqual(attempts[0]['error_type'], 'JSONDecodeError')
            self.assertTrue(attempts[0]['cost_unknown'])
            self.assertEqual(len(attempts), 1)
            ledger = budgets.BudgetLedger(child, cap_limit=study.PROPOSED_CHILD)
            try:
                self.assertEqual(ledger.accounted(), study.RESERVE)
                self.assertEqual(len(ledger.state()[1]), 1)
            finally:
                ledger.close()
            with self.assertRaises(FileExistsError):
                self.stage(base, child, 'smoke', [self.response()] * 3)

    def test_bounded_http_error_body_and_unknown_charge(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            error = urllib.error.HTTPError('https://example.invalid', 503, 'busy',
                                           {'retry-after': '2'}, io.BytesIO(b'X' * 100))
            with patch.object(run, 'MAX_RESPONSE_BYTES', 16):
                self.assertFalse(self.stage(base, child, 'smoke', [error]))
            error.close()
            row = run.jsonl(base / 'fresh1/P0/smoke.responses.jsonl')[0]
            attempt = run.jsonl(base / 'fresh1/P0/smoke.attempts.jsonl')[0]
            self.assertEqual(base64.b64decode(row['body_base64']), b'X' * 16)
            self.assertTrue(row['body_truncated_at_limit'])
            self.assertEqual(attempt['http_status'], 503)
            self.assertTrue(attempt['cost_unknown'])
            ledger = budgets.BudgetLedger(child, cap_limit=study.PROPOSED_CHILD)
            try:
                self.assertEqual(ledger.accounted(), study.RESERVE)
            finally:
                ledger.close()

    def test_receipt_binds_exact_stage_controller_plan_and_cap(self):
        execution = wrapped.execution_plan()
        receipt = {'schema': run.RECEIPT_SCHEMA, 'approved': True,
                   'configuration_id': study.CONFIG, 'partition_cap_usd': str(study.PROPOSED_CHILD),
                   'stage': 'fresh1/P0/smoke', 'controller_sha256': study.sha(wrapped.__file__),
                   'hosted_execution_sha256': study.sha(run.HOSTED_EXECUTION),
                   'execution_manifest_sha256': 'fixture', 'plan_sha256': execution['plans_sha256'][study.CONFIG],
                   'master_ledger': str(run.MASTER), 'budget_manifest': {'path': 'fixture', 'sha256': 'fixture'},
                   'partition_id': 'fixture'}
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(run, 'verify_execution_manifest', return_value=execution), \
             patch.object(run, 'bound_file', return_value=Path(temp) / 'budget.json'):
            path = Path(temp) / 'review.json'
            path.write_text(json.dumps(receipt))
            run.review_receipt(path, study.CONFIG, 'fresh1', 'P0', 'smoke', self.plan_sha)
            for key, bad in [('stage', 'fresh1/P1/smoke'),
                             ('controller_sha256', '0' * 64),
                             ('partition_cap_usd', '0'),
                             ('plan_sha256', {'fresh1': '0' * 64})]:
                changed = dict(receipt, **{key: bad})
                path.write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError):
                    run.review_receipt(path, study.CONFIG, 'fresh1', 'P0', 'smoke', self.plan_sha)

    def test_real_master_child_partition_admits_exact_cap_route_and_effort(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            master = root / 'master.jsonl'
            manifest = root / 'partitions.jsonl'
            budgets.BudgetLedger(master).close()
            partitions.allocate(master, manifest, [{
                'id': 'deepseek-high-fixture', 'cap_usd': str(study.PROPOSED_CHILD),
                'model': study.MODEL, 'provider': study.PROVIDER,
                'reasoning': study.EFFORT,
            }])
            receipt = {'partition_id': 'deepseek-high-fixture'}
            with patch.object(run, 'MASTER', master):
                child = run.budget_gate(receipt, manifest, study.CONFIG)
                try:
                    self.assertEqual(child.cap, study.PROPOSED_CHILD)
                    attempt_id = child.reserve(study.RESERVE, 'DEV-001')
                    self.assertTrue(child.settle(attempt_id, Decimal('0.01')))
                    self.assertEqual(child.accounted(), Decimal('0.01'))
                finally:
                    child.close()
                with patch.object(wrapped._Study, 'PROVIDER', 'other/fp4'):
                    with self.assertRaisesRegex(ValueError, 'outside partition'):
                        run.budget_gate(receipt, manifest, study.CONFIG)
                altered = {study.CONFIG: dict(wrapped._Study.CONFIGS[study.CONFIG], effort='low')}
                with patch.object(wrapped._Study, 'CONFIGS', altered):
                    with self.assertRaisesRegex(ValueError, 'outside partition'):
                        run.budget_gate(receipt, manifest, study.CONFIG)


if __name__ == '__main__':
    unittest.main()
