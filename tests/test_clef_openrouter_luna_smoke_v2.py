"""Offline exact-unsent Luna smoke and composite-gate regressions."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_openrouter_luna_smoke_v2 as v2
import clef_openrouter_native_v1 as frozen
import clef_openrouter_smoke_v1 as old
import openrouter_decision_smoke as native
import openrouter_budget_v4


class LunaV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        paths = set(v2.SOURCES) | {frozen.PLAN}
        paths |= {frozen.catalog_path(key) for key in frozen.MODELS}
        paths |= {v2.PARENT / name for name in v2.PARENT_FILES}
        for rel in paths:
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, self.root / rel)
        self.folder = self.root / v2.BASE
        self.folder.mkdir(parents=True)
        (self.folder / 'plan.json').write_bytes((ROOT / v2.PLAN).read_bytes())

    def test_parent_reinterpretation_keeps_original_failure_and_only_two_unsent(self):
        plan, digest = v2.verify(self.root)
        self.assertEqual(plan['request_ids'], ['DEV-002', 'DEV-003'])
        self.assertEqual(plan['parent']['original_status'], 'invalid_native_response')
        self.assertEqual(plan['parent']['dated_model_parse'], 'valid_native_choice')
        self.assertEqual(plan['parent']['known_cost_usd'], '0.0002233')
        self.assertEqual(plan['child_cap_usd'], '0.8400000')
        self.assertEqual(digest, native.sha(native.canonical(plan)))

    def test_parent_raw_and_source_drift_fail_closed(self):
        path = self.root / v2.PARENT / 'smoke.raw.jsonl'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'plan differs'):
            v2.verify(self.root)
        path.write_bytes((ROOT / v2.PARENT / 'smoke.raw.jsonl').read_bytes())
        source = self.root / v2.SOURCES[0]
        source.write_bytes(source.read_bytes() + b'\n# drift\n')
        with self.assertRaisesRegex(ValueError, 'plan differs'):
            v2.verify(self.root)

    def prepare_runner(self):
        self.review = self.folder / 'root-review.json'
        self.review.write_text('{}')
        self.budget = self.folder / 'budget.json'
        self.budget.write_text('{}')
        self.child_path = self.folder / 'child.jsonl'
        self.child = openrouter_budget_v4.BudgetLedger(self.child_path, cap_limit=v2.BOUND)
        self.child.master_cap = openrouter_budget_v4.CAP
        catalog = json.loads((ROOT / frozen.catalog_path(v2.KEY)).read_text())['response']
        self.fetch = lambda _: (native.canonical(catalog), catalog)

    def response(self, payload):
        answers = {}
        for key, question in payload['questions'].items():
            options = list(question['criteria'])
            answers[key] = {'type': 'choice', 'choice': options[0], 'confidence': 1.0,
                            'probabilities': {option: float(i == 0) for i, option in enumerate(options)}}
        return json.dumps({'model': v2.DATED_MODEL, 'provider': 'OpenAI', 'answers': answers,
                           'usage': {'input_tokens': 2233, 'output_tokens': 0, 'cost': '0.0002233'}}).encode()

    def run_with(self, send):
        with mock.patch.object(v2, 'verify_review', return_value={}), \
                mock.patch.object(v2, 'verify_hold', return_value=None), \
                mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}):
            v2.run(self.review, self.budget, root=self.root, fetch=self.fetch,
                   send=send, open_child=lambda *args: self.child)

    def test_real_child_two_successes_raw_before_parse_and_no_replay(self):
        self.prepare_runner()
        self.review.write_text(json.dumps({'approved': True}))
        self.budget.write_text(json.dumps({'partitions': [{
            'id': v2.PARTITION_ID, 'cap_usd': str(v2.BOUND),
            'child_ledger': str(self.child_path)}]}))
        calls = []
        def send(payload, token):
            calls.append(payload)
            return 200, self.response(payload)
        self.run_with(send)
        self.assertEqual(len(calls), 2)
        self.assertEqual([row['id'] for row in v2.lines(self.folder / 'smoke.raw.jsonl')], list(v2.IDS))
        self.assertEqual([row['status'] for row in v2.lines(self.folder / 'smoke.attempts.jsonl')], ['ok', 'ok'])
        self.assertEqual([row['event'] for row in v2.lines(self.child_path)],
                         ['budget', 'reserve', 'settle', 'reserve', 'settle'])
        projection, digest = v2.composite_inspection(self.root)
        self.assertEqual([row['id'] for row in projection['rows']], ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertEqual(projection['original_dev001_status_preserved'], 'invalid_native_response')
        self.assertEqual(digest, native.sha(native.canonical(projection)))
        self.assertEqual(projection['suffix_child_state'], 'completed_open')
        child = openrouter_budget_v4.BudgetLedger(self.child_path, cap_limit=v2.BOUND)
        child.append({'event': 'partition_closed', 'reason': 'terminal test reconciliation'})
        child.close()
        known = '0.0004466'
        receipt = {'event': 'partition_reconciled', 'partition_id': v2.PARTITION_ID,
                   'known_actual_usd': known, 'unknown_upper_bound_usd': '0',
                   'unused_allocation_released_usd': str(v2.BOUND - v2.Decimal(known)),
                   'child_ledger': str(self.child_path),
                   'child_sha256': v2.sha_path(self.child_path)}
        (self.folder / 'smoke.reconciliation.json').write_text(json.dumps(receipt))
        sealed, sealed_digest = v2.composite_inspection(self.root)
        self.assertEqual(sealed['suffix_child_state'], 'sealed_reconciled')
        self.assertNotEqual(sealed_digest, digest)
        receipt['known_actual_usd'] = '0'
        (self.folder / 'smoke.reconciliation.json').write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'reconciliation differs'):
            v2.composite_inspection(self.root)
        with self.assertRaises(FileExistsError):
            self.run_with(send)
        self.assertEqual(len(calls), 2)

    def test_first_unknown_stops_and_keeps_full_reserve(self):
        self.prepare_runner()
        calls = []
        def send(payload, token):
            calls.append(payload)
            return 429, b'{"error":"unpriced"}'
        with self.assertRaisesRegex(ValueError, 'cost unknown'):
            self.run_with(send)
        self.assertEqual(len(calls), 1)
        self.assertEqual([row['id'] for row in v2.lines(self.folder / 'smoke.raw.jsonl')], ['DEV-002'])
        self.assertEqual([row['status'] for row in v2.lines(self.folder / 'smoke.attempts.jsonl')], ['unknown_cost'])
        self.assertEqual([row['event'] for row in v2.lines(self.child_path)], ['budget', 'reserve'])
        with self.assertRaises(FileExistsError):
            self.run_with(send)


if __name__ == '__main__':
    unittest.main()
