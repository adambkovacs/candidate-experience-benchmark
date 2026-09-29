"""Offline lifecycle and money checks for the Qwen27 fresh runner."""
import io
import base64
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_budget_v2 as budgets
import qwen27_fresh_repeat_study as study
import qwen27_fresh_repeat_execution as runner

PREDICTION = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = headers or {'content-type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.body.close()

    def read(self, limit):
        return self.body.read(limit)


class Qwen27ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.config = 'openrouter-paid-qwen3.8-27b-medium'
        self.plan = study.plan_data(self.config, 'fresh1')
        self.manifest_sha = study.sha(study.BASE / self.config / 'fresh1/manifest.json')
        audit, _ = study.historical_data(self.config)
        _, rows, _ = study.source_rows(audit, 'P0')
        self.endpoint = rows['DEV-001']['provider_endpoint']
        self.model = rows['DEV-001']['model_catalog_entry']

    def response(self, cost='0.0001'):
        return {'model': study.MODEL, 'provider': study.PROVIDER_NAME,
                'usage': {'cost': cost, 'prompt_tokens': 100, 'completion_tokens': 20},
                'choices': [{'finish_reason': 'stop',
                             'message': {'content': json.dumps(PREDICTION)}}]}

    def fixture(self, temp):
        base = Path(temp) / 'plans'
        manifest = base / self.config / 'fresh1/manifest.json'
        manifest.parent.mkdir(parents=True)
        shutil.copy2(study.BASE / self.config / 'fresh1/manifest.json', manifest)
        return base, manifest, Path(temp) / 'child.jsonl'

    def run_stage(self, base, child, phase, responses):
        items = iter(responses)
        review = base / 'offline-review.json'
        review.write_text('{"fixture": true}\n')
        def open_response(request, timeout):
            self.assertEqual(request.full_url, runner.transport.BASE + '/chat/completions')
            self.assertEqual(timeout, study.TIMEOUT)
            item = next(items)
            if isinstance(item, Exception):
                raise item
            if isinstance(item, bytes):
                return FakeResponse(item)
            return FakeResponse(json.dumps(item).encode())
        def gate(_receipt, _path, _config):
            return budgets.BudgetLedger(child, cap_limit=study.CONFIGS[self.config]['proposed_child_budget'])
        with patch.object(study, 'BASE', base), \
             patch.object(study, 'verify', return_value=self.plan), \
             patch.object(runner, 'review_receipt', return_value=({'partition_id': 'temp'}, Path('/unused'))), \
             patch.object(runner, 'live_controls', return_value=(self.model, self.endpoint, Decimal('0.047001600'))), \
             patch.object(runner, 'budget_gate', side_effect=gate), \
             patch.object(runner.paid, 'load_key', return_value='fake-key'), \
             patch.object(runner.transport.OPENER, 'open', side_effect=open_response), \
             patch.object(runner, 'audit_response', return_value={'passed': True, 'blockers': []}):
            return runner.execute(self.config, 'fresh1', 'P0', phase,
                                  study.sha(base / self.config / 'fresh1/manifest.json'), review)

    def test_six_frozen_plans_enter_execution_manifest_without_approval(self):
        value = runner.execution_plan()
        self.assertEqual(value['status'], 'offline_frozen_not_approved')
        self.assertEqual(set(value['plans_sha256']), set(study.CONFIGS))
        self.assertEqual([len(value['plans_sha256'][config]) for config in study.CONFIGS], [3, 3])
        frozen = runner.verify_execution_manifest(study.sha(runner.EXECUTION_MANIFEST))
        self.assertEqual(frozen, value)
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            runner.verify_execution_manifest('0' * 64)

    def test_live_exact_route_and_limits_reject_drift(self):
        import copy
        live = copy.deepcopy(self.endpoint)
        catalog = {'data': [self.model]}
        endpoints = {'data': {'id': study.MODEL, 'endpoints': [live]}}
        with patch.object(runner.paid, 'fetch', side_effect=[catalog, endpoints]):
            _, selected, reserve = runner.live_controls(self.plan, 'P0')
        self.assertEqual(selected, live)
        self.assertEqual(reserve, Decimal('0.047001600'))
        live['max_prompt_tokens'] = 1
        with patch.object(runner.paid, 'fetch', side_effect=[catalog, endpoints]):
            with self.assertRaisesRegex(ValueError, 'route, limits or price'):
                runner.live_controls(self.plan, 'P0')

    def test_real_child_ledger_known_smoke_and_inspected_development(self):
        with tempfile.TemporaryDirectory() as temp:
            base, manifest, child = self.fixture(temp)
            self.assertTrue(self.run_stage(base, child, 'smoke', [self.response()] * 3))
            with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=self.plan):
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    runner.require_order(self.plan, 'P0', 'development')
                runner.inspect(self.config, 'fresh1', 'P0', study.sha(manifest), 'Three raw responses inspected.')
                runner.require_order(self.plan, 'P0', 'development')
            self.assertTrue(self.run_stage(base, child, 'development', [self.response()] * 60))
            with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=self.plan):
                runner.verify_phase_closure(self.plan, 'P0', 'development')
            ledger = budgets.BudgetLedger(child, cap_limit=study.CONFIGS[self.config]['proposed_child_budget'])
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.0063'))
                self.assertEqual(ledger.state()[1], set())
                self.assertEqual(len([x for x in ledger.events if x['event'] == 'reserve']), 63)
            finally:
                ledger.close()

    def test_http_error_retains_unknown_reserve_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            error = urllib.error.HTTPError('https://example.invalid', 429, 'Queue timeout',
                                           {'retry-after': '1'}, io.BytesIO(b'{"error":"busy"}'))
            self.assertFalse(self.run_stage(base, child, 'smoke', [error]))
            error.close()
            folder = base / self.config / 'fresh1/P0'
            records = runner.jsonl(folder / 'smoke.attempts.jsonl')
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]['http_status'], 429)
            self.assertTrue(records[0]['cost_unknown'])
            ledger = budgets.BudgetLedger(child, cap_limit=study.CONFIGS[self.config]['proposed_child_budget'])
            try:
                self.assertEqual(len(ledger.state()[1]), 1)
                self.assertEqual(ledger.accounted(), Decimal('0.047001600'))
            finally:
                ledger.close()

    def test_malformed_http_200_captures_bytes_before_parse_and_never_replays(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            malformed = b'{"choices": [incomplete'
            self.assertFalse(self.run_stage(base, child, 'smoke', [malformed]))
            folder = base / self.config / 'fresh1/P0'
            raw = runner.jsonl(folder / 'smoke.responses.jsonl')
            attempts = runner.jsonl(folder / 'smoke.attempts.jsonl')
            self.assertEqual(len(raw), 1)
            self.assertEqual(base64.b64decode(raw[0]['body_base64']), malformed)
            self.assertEqual(raw[0]['http_status'], 200)
            self.assertEqual(attempts[0]['error_type'], 'JSONDecodeError')
            self.assertTrue(attempts[0]['cost_unknown'])
            with self.assertRaises(FileExistsError):
                self.run_stage(base, child, 'smoke', [self.response()] * 3)
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('1.00'))
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.047001600'))
                self.assertEqual(len(ledger.state()[1]), 1)
                self.assertEqual(len([x for x in ledger.events if x['event'] == 'reserve']), 1)
            finally:
                ledger.close()

    def test_oversized_http_200_and_error_body_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            with patch.object(runner, 'MAX_RESPONSE_BYTES', 16):
                self.assertFalse(self.run_stage(base, child, 'smoke', [b'X' * 100]))
            folder = base / self.config / 'fresh1/P0'
            raw = runner.jsonl(folder / 'smoke.responses.jsonl')[0]
            self.assertEqual(base64.b64decode(raw['body_base64']), b'X' * 16)
            self.assertTrue(raw['body_truncated_at_limit'])
            self.assertEqual(raw['body_bytes_captured'], 16)
            self.assertEqual(runner.jsonl(folder / 'smoke.attempts.jsonl')[0]['status'], 'service_error')
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            error = urllib.error.HTTPError('https://example.invalid', 503, 'unavailable',
                                           {'retry-after': '1'}, io.BytesIO(b'E' * 100))
            with patch.object(runner, 'MAX_RESPONSE_BYTES', 16):
                self.assertFalse(self.run_stage(base, child, 'smoke', [error]))
            error.close()
            folder = base / self.config / 'fresh1/P0'
            raw = runner.jsonl(folder / 'smoke.responses.jsonl')[0]
            record = runner.jsonl(folder / 'smoke.attempts.jsonl')[0]
            self.assertEqual(base64.b64decode(raw['body_base64']), b'E' * 16)
            self.assertTrue(raw['body_truncated_at_limit'])
            self.assertTrue(record['error_body_truncated_at_limit'])
            self.assertEqual(record['http_status'], 503)

    def test_known_billed_invalid_stops_and_cannot_open_development(self):
        with tempfile.TemporaryDirectory() as temp:
            base, manifest, child = self.fixture(temp)
            invalid = self.response()
            invalid['choices'][0]['message']['content'] = 'not JSON'
            self.assertFalse(self.run_stage(base, child, 'smoke', [invalid]))
            folder = base / self.config / 'fresh1/P0'
            rows = runner.jsonl(folder / 'smoke.attempts.jsonl')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['status'], 'invalid_output')
            self.assertTrue(rows[0]['billing_ok'])
            self.assertFalse(rows[0]['cost_unknown'])
            with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=self.plan):
                with self.assertRaisesRegex(ValueError, 'ordered frozen request list'):
                    runner.inspect(self.config, 'fresh1', 'P0', study.sha(manifest), 'Cannot accept.')
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    runner.require_order(self.plan, 'P0', 'development')
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('1.00'))
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.0001'))
            finally:
                ledger.close()

    def test_xhigh_configuration_uses_distinct_effort_and_cap(self):
        self.config = 'openrouter-paid-qwen3.8-27b-xhigh'
        self.plan = study.plan_data(self.config, 'fresh1')
        audit, _ = study.historical_data(self.config)
        _, rows, _ = study.source_rows(audit, 'P0')
        self.endpoint = rows['DEV-001']['provider_endpoint']
        self.model = rows['DEV-001']['model_catalog_entry']
        self.assertEqual(self.plan['conditions']['P0']['smoke'][0]['payload']['reasoning'],
                         {'enabled': True, 'effort': 'xhigh'})
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            self.assertTrue(self.run_stage(base, child, 'smoke', [self.response()] * 3))
            record = runner.jsonl(base / self.config / 'fresh1/P0/smoke.attempts.jsonl')[0]
            self.assertEqual(record['reasoning_effort'], 'xhigh')
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('0.80'))
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.0003'))
            finally:
                ledger.close()

    def test_duplicate_phase_claim_cannot_resend(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            self.assertTrue(self.run_stage(base, child, 'smoke', [self.response()] * 3))
            with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                self.run_stage(base, child, 'smoke', [self.response()] * 3)
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('1.00'))
            try:
                self.assertEqual(len([x for x in ledger.events if x['event'] == 'reserve']), 3)
            finally:
                ledger.close()

    def test_reserve_cap_and_child_lock_stop_before_http(self):
        with tempfile.TemporaryDirectory() as temp:
            base, _, child = self.fixture(temp)
            held = budgets.BudgetLedger(child, cap_limit=study.CONFIGS[self.config]['proposed_child_budget'])
            folder = base / self.config / 'fresh1/P0'
            try:
                with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=self.plan), \
                     patch.object(runner, 'review_receipt', return_value=({'partition_id': 'temp'}, Path('/unused'))), \
                     patch.object(runner, 'live_controls', return_value=(self.model, self.endpoint, Decimal('0.047001600'))), \
                     patch.object(runner, 'budget_gate', side_effect=lambda *_: budgets.BudgetLedger(child, cap_limit=Decimal('1.00'))), \
                     patch.object(runner.paid, 'load_key', side_effect=AssertionError('key must not be used')):
                    with self.assertRaises(BlockingIOError):
                        runner.execute(self.config, 'fresh1', 'P0', 'smoke', self.manifest_sha, '/unused')
                self.assertFalse((folder / 'smoke.claim.json').exists())
            finally:
                held.close()
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('1.00'))
            try:
                for number in range(21):
                    attempt = ledger.reserve(Decimal('0.047001600'), f'PRE-{number}')
                    ledger.settle(attempt, Decimal('0.047001600'))
                with self.assertRaisesRegex(ValueError, 'cap reached'):
                    ledger.reserve(Decimal('0.047001600'), 'NEXT')
            finally:
                ledger.close()


if __name__ == '__main__':
    unittest.main()
