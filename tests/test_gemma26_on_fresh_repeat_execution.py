"""Offline lifecycle, money and predecessor checks for the Gemma fresh runner."""
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
import gemma26_on_fresh_repeat_study as study
import gemma26_on_fresh_repeat_execution as execution
import openrouter_budget_v2 as budgets
import paid_budget_partitions_v2 as partitions

PREDICTION = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}
ENDPOINT = {'model_id': study.MODEL, 'provider_name': 'DeepInfra',
            'tag': study.PROVIDER, 'quantization': 'fp8', 'context_length': study.CONTEXT,
            'pricing': {'prompt': '0.00000007', 'completion': '0.00000034'}}


def response(cost='0.0001', content=None, model=None, provider='DeepInfra'):
    return {'model': model or study.MODEL, 'provider': provider,
            'usage': {'cost': cost, 'prompt_tokens': 100, 'completion_tokens': 20},
            'choices': [{'finish_reason': 'stop',
                         'message': {'content': json.dumps(PREDICTION) if content is None else content}}]}


class Gemma26OnExecutionTests(unittest.TestCase):
    def setUp(self):
        self.plan = study.plan_data('fresh1')
        self.manifest_sha = study.sha(study.BASE / 'fresh1' / 'manifest.json')

    def _run_stage(self, base, ledger_path, phase, fetch_items):
        plan_file = base / 'fresh1' / 'manifest.json'
        phase_dir = base / 'fresh1' / 'P0'
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(study.BASE / 'fresh1' / 'manifest.json', plan_file)
        review_file = base / 'review.json'
        review_file.write_text('{"offline_test_receipt":true}\n')
        plan = json.loads(plan_file.read_text())
        items = iter(fetch_items)
        def open_response(request, timeout):
            self.assertEqual(timeout, 300)
            self.assertEqual(request.get_header('Authorization'), 'Bearer fake-token')
            item = next(items)
            if isinstance(item, BaseException):
                raise item
            body = item if isinstance(item, bytes) else json.dumps(item).encode()
            response = io.BytesIO(body)
            response.status = 200
            response.headers = {'content-type': 'application/json'}
            return response
        def gate(_receipt, _budget_path):
            return budgets.BudgetLedger(ledger_path, cap_limit=study.PROPOSED_CHILD_USD)
        with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=plan), \
             patch.object(execution, 'review_receipt', return_value=({'partition_id': 'gemma-test'}, Path('/unused'))), \
             patch.object(execution, 'live_controls', return_value=({'id': study.MODEL}, ENDPOINT, Decimal('0.01974272'))), \
             patch.object(execution, 'budget_gate', side_effect=gate), \
             patch.object(execution.paid, 'load_key', return_value='fake-token'), \
             patch.object(execution.transport.OPENER, 'open', side_effect=open_response), \
             patch.object(execution, 'audit_response', return_value={'passed': True, 'blockers': []}):
            result = execution.execute('fresh1', 'P0', phase, self.manifest_sha, str(review_file))
        return result, phase_dir

    def _verify_temp_closure(self, base, condition, phase):
        plan = json.loads((base / 'fresh1' / 'manifest.json').read_text())
        with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=plan):
            return execution.verify_phase_closure(plan, condition, phase)

    def test_known_smoke_settles_real_reservations_and_is_exactly_ordered(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'runs'
            ledger_path = Path(temp) / 'child.jsonl'
            result, folder = self._run_stage(base, ledger_path, 'smoke', [response()] * 3)
            self.assertTrue(result)
            events = [json.loads(x) for x in ledger_path.read_text().splitlines()]
            self.assertEqual([x['event'] for x in events], ['budget'] + ['reserve', 'settle'] * 3)
            ledger = budgets.BudgetLedger(ledger_path, cap_limit=study.PROPOSED_CHILD_USD)
            try:
                amounts, pending, blocked = ledger.state()
                self.assertFalse(pending)
                self.assertFalse(blocked)
                self.assertEqual(ledger.accounted(), Decimal('0.0003'))
                self.assertEqual(len([e for e in events if e['event'] == 'reserve']), 3)
                self.assertTrue(all(Decimal(e['usd']) == Decimal('0.01974272') for e in events if e['event'] == 'reserve'))
            finally:
                ledger.close()
            closure = self._verify_temp_closure(base, 'P0', 'smoke')
            self.assertEqual(closure['manifest_sha256'], self.manifest_sha)
            self.assertEqual(len(json.loads((folder / 'smoke.journal.jsonl').read_text().splitlines()[-1])['attempt_ids']), 3)

    def test_unknown_charge_is_stopped_and_retains_full_pending_reserve(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'runs'
            ledger_path = Path(temp) / 'child.jsonl'
            error = urllib.error.HTTPError('https://example.invalid', 429, 'Limited',
                                           {'retry-after': '60'}, io.BytesIO(b'{"error":"busy"}'))
            with patch.object(error, 'read', wraps=error.read) as read_error:
                result, folder = self._run_stage(base, ledger_path, 'smoke', [error])
                read_error.assert_called_once_with(execution.MAX_RESPONSE_BYTES + 1)
            self.assertFalse(result)
            row = json.loads((folder / 'smoke.attempts.jsonl').read_text().splitlines()[0])
            self.assertEqual(row['http_status'], 429)
            self.assertEqual(row['status'], 'service_error')
            self.assertTrue(row['cost_unknown'])
            self.assertFalse(row['billing_ok'])
            self.assertEqual(len(json.loads((folder / 'smoke.responses.jsonl').read_text().splitlines()[0])['error_body']), 16)
            ledger = budgets.BudgetLedger(ledger_path, cap_limit=study.PROPOSED_CHILD_USD)
            try:
                amounts, pending, blocked = ledger.state()
                self.assertEqual(len(pending), 1)
                self.assertEqual(next(iter(amounts.values())), Decimal('0.01974272'))
                self.assertFalse(blocked)
                self.assertEqual(sum(Decimal(e.get('usd', '0')) for e in ledger.events if e['event'] == 'settle'), Decimal(0))
            finally:
                ledger.close()
            with self.assertRaisesRegex(ValueError, 'exact ordered frozen request list'):
                self._verify_temp_closure(base, 'P0', 'smoke')

    def test_malformed_http_200_is_captured_before_parse_and_holds_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'runs'
            ledger_path = Path(temp) / 'child.jsonl'
            malformed = b'{"choices": [{"message": '
            result, folder = self._run_stage(base, ledger_path, 'smoke', [malformed])
            self.assertFalse(result)
            wire = json.loads((folder / 'smoke.wire.jsonl').read_text().splitlines()[0])
            self.assertEqual(base64.b64decode(wire['body_base64']), malformed)
            self.assertEqual(wire['http_status'], 200)
            self.assertFalse(wire['body_truncated_at_limit'])
            response = json.loads((folder / 'smoke.responses.jsonl').read_text().splitlines()[0])
            self.assertEqual(response['capture_error'], 'JSONDecodeError')
            record = json.loads((folder / 'smoke.attempts.jsonl').read_text().splitlines()[0])
            self.assertEqual(record['status'], 'service_error')
            self.assertIsNone(record['observed_cost_usd'])
            self.assertTrue(record['cost_unknown'])
            ledger = budgets.BudgetLedger(ledger_path, cap_limit=study.PROPOSED_CHILD_USD)
            try:
                self.assertEqual(len(ledger.state()[1]), 1)
                self.assertEqual(ledger.accounted(), Decimal('0.01974272'))
            finally:
                ledger.close()

    def test_inspected_smoke_is_required_and_binds_development_predecessor(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'runs'
            ledger_path = Path(temp) / 'child.jsonl'
            _, folder = self._run_stage(base, ledger_path, 'smoke', [response()] * 3)
            plan_file = base / 'fresh1' / 'manifest.json'
            plan = json.loads(plan_file.read_text())
            manifest_sha = study.sha(plan_file)
            with patch.object(study, 'BASE', base), patch.object(study, 'verify', return_value=plan):
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    execution.require_order(plan, 'P0', 'development')
                execution.inspect('fresh1', 'P0', manifest_sha, 'Inspected three raw JSON responses and matching model/provider/cost.')
                execution.require_order(plan, 'P0', 'development')
            # A successful smoke receipt unlocks this same condition's development
            # runner; use mocked responses and a real child budget ledger.
            _, dev_folder = self._run_stage(base, ledger_path, 'development', [response()] * 60)
            closure = self._verify_temp_closure(base, 'P0', 'development')
            self.assertEqual(closure['manifest_sha256'], manifest_sha)
            self.assertEqual(len(json.loads((dev_folder / 'development.journal.jsonl').read_text().splitlines()[-1])['attempt_ids']), 60)

    def test_journal_reordering_and_duplicate_attempt_id_break_predecessor(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'runs'
            ledger_path = Path(temp) / 'child.jsonl'
            _, folder = self._run_stage(base, ledger_path, 'smoke', [response()] * 3)
            attempts_path = folder / 'smoke.attempts.jsonl'
            rows = [json.loads(x) for x in attempts_path.read_text().splitlines()]
            rows[1]['attempt_id'] = rows[0]['attempt_id']
            attempts_path.write_text(''.join(json.dumps(x) + '\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'Attempt IDs are missing or duplicated'):
                self._verify_temp_closure(base, 'P0', 'smoke')

    def test_journal_order_and_terminal_record_count_are_strict(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'runs'
            ledger_path = Path(temp) / 'child.jsonl'
            _, folder = self._run_stage(base, ledger_path, 'smoke', [response()] * 3)
            journal_path = folder / 'smoke.journal.jsonl'
            journal = [json.loads(x) for x in journal_path.read_text().splitlines()]
            original = json.loads(json.dumps(journal))
            journal[1], journal[2] = journal[2], journal[1]
            journal_path.write_text(''.join(json.dumps(x) + '\n' for x in journal))
            with self.assertRaisesRegex(ValueError, 'Journal order'):
                self._verify_temp_closure(base, 'P0', 'smoke')
            original[-1]['request_count'] = 2
            journal_path.write_text(''.join(json.dumps(x) + '\n' for x in original))
            with self.assertRaisesRegex(ValueError, 'Journal order'):
                self._verify_temp_closure(base, 'P0', 'smoke')

    def test_root_receipt_binds_all_frozen_passes_stage_and_budget_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            budget_manifest = root / 'budget.json'
            budget_manifest.write_text('{"frozen":true}\n')
            receipt_path = root / 'review.json'
            plan_hashes = {name: study.sha(study.BASE / name / 'manifest.json') for name in study.ORDERS}
            receipt = {'schema': execution.RECEIPT_SCHEMA, 'approved': True,
                       'configuration_id': study.CONFIG,
                       'partition_cap_usd': str(study.PROPOSED_CHILD_USD),
                       'stage': 'fresh1/P0/smoke',
                       'controller_sha256': study.sha(execution.__file__),
                       'hosted_execution_sha256': study.sha(execution.HOSTED_EXECUTION),
                       'plan_sha256': plan_hashes,
                       'master_ledger': str(root / 'master.jsonl'),
                       'budget_manifest': {'path': 'budget.json', 'sha256': study.sha(budget_manifest)},
                       'partition_id': 'gemma-test'}
            receipt_path.write_text(json.dumps(receipt) + '\n')
            with patch.object(execution, 'ROOT', root), patch.object(execution, 'MASTER', root / 'master.jsonl'):
                approved, path = execution.review_receipt(
                    receipt_path, 'fresh1', 'P0', 'smoke', plan_hashes['fresh1'])
                self.assertTrue(approved['approved'])
                self.assertEqual(path, budget_manifest.resolve())
                receipt['stage'] = 'fresh1/P1/smoke'
                receipt_path.write_text(json.dumps(receipt) + '\n')
                with self.assertRaisesRegex(ValueError, 'Root review stage differs'):
                    execution.review_receipt(receipt_path, 'fresh1', 'P0', 'smoke', plan_hashes['fresh1'])
                receipt['stage'] = 'fresh1/P0/smoke'
                receipt['plan_sha256']['fresh3'] = '0' * 64
                receipt_path.write_text(json.dumps(receipt) + '\n')
                with self.assertRaisesRegex(ValueError, 'Root review plan hashes differ'):
                    execution.review_receipt(receipt_path, 'fresh1', 'P0', 'smoke', plan_hashes['fresh1'])

    def test_real_child_lock_contention_blocks_before_key_or_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            master = root / 'master.jsonl'
            manifest = root / 'partitions.json'
            allocated = partitions.allocate(master, manifest, [{
                'id': 'gemma-test', 'cap_usd': '0.40', 'model': study.MODEL,
                'provider': study.PROVIDER, 'reasoning': study.EFFORT,
            }])
            child = Path(allocated['partitions'][0]['child_ledger'])
            held = budgets.BudgetLedger(child, cap_limit=study.PROPOSED_CHILD_USD)
            phase_dir = study.BASE / 'fresh1' / 'P0'
            self.assertFalse(phase_dir.joinpath('smoke.claim.json').exists())
            try:
                with patch.object(execution, 'MASTER', master), \
                     patch.object(execution, 'review_receipt', return_value=({'partition_id': 'gemma-test'}, manifest)), \
                     patch.object(execution, 'live_controls', return_value=({'id': study.MODEL}, ENDPOINT, Decimal('0.01974272'))), \
                     patch.object(execution.paid, 'load_key', side_effect=AssertionError('key must remain unread')):
                    with self.assertRaises(BlockingIOError):
                        execution.execute('fresh1', 'P0', 'smoke', self.manifest_sha, '/review')
                self.assertFalse(phase_dir.joinpath('smoke.claim.json').exists())
            finally:
                held.close()

    def test_all_full_context_reservations_fail_before_child_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger_path = Path(temp) / 'child.jsonl'
            ledger = budgets.BudgetLedger(ledger_path, cap_limit=study.PROPOSED_CHILD_USD)
            try:
                for index in range(20):
                    attempt = ledger.reserve(Decimal('0.01974272'), f'DEV-{index:03d}')
                    ledger.settle(attempt, Decimal('0.01974272'))
                with self.assertRaisesRegex(ValueError, 'cap reached'):
                    ledger.reserve(Decimal('0.01974272'), 'DEV-over-cap')
            finally:
                ledger.close()


if __name__ == '__main__':
    unittest.main()
