import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen36_prompt_recovery_v1 as recovery


class Qwen36RecoveryTest(unittest.TestCase):
    def plans(self):
        return [recovery.RESULT / f'{mode}-{variant.lower()}-smoke-plan.json'
                for mode, variant in recovery.ORDER]

    def test_four_input_only_plans_match_frozen_smoke(self):
        for original in self.plans():
            with self.subTest(path=original.name), tempfile.TemporaryDirectory(dir=recovery.RESULT) as directory:
                folder = Path(directory)
                plan = json.loads(original.read_text())
                plan['new_output'] = str((folder / 'fresh-smoke.jsonl').relative_to(ROOT))
                path = folder / 'plan.json'
                path.write_text(json.dumps(plan))
                result = recovery.verify(path, recovery.sha(path))
                self.assertEqual(result['requests'], 3)
                self.assertEqual(result['three_call_bound_usd'], '0.0897024')
                self.assertEqual(result['proposed_partition_cap_usd'], '0.09')
                self.assertTrue(plan['offline_only'])
                self.assertFalse(plan['reference_labels_read'])
                self.assertFalse(plan['inference_performed'])
                self.assertFalse(plan['original_timing_preserved'])

    def test_hash_and_membership_drift_fail(self):
        path = self.plans()[0]
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            recovery.verify(path, '0' * 64)
        plan = json.loads(path.read_text())
        plan['record_ids'] = ['DEV-001']
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / 'plan.json'
            changed.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'membership'):
                recovery.verify(changed, recovery.sha(changed))

    def test_bound_and_routing_drift_fail(self):
        path = self.plans()[1]
        original = json.loads(path.read_text())
        for key, value, message in (
            ('three_call_bound_usd', '0.08', 'reserve or cap'),
            ('requests', original['requests'][:2], 'request bindings'),
            ('original_timing_preserved', True, 'timing disclosure')):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                changed = Path(directory) / 'plan.json'
                plan = copy.deepcopy(original)
                plan[key] = value
                changed.write_text(json.dumps(plan))
                with self.assertRaisesRegex(ValueError, message):
                    recovery.verify(changed, recovery.sha(changed))

    def test_existing_output_blocks_replay(self):
        path = self.plans()[2]
        plan = json.loads(path.read_text())
        output = recovery.ROOT / plan['new_output']
        real_exists = Path.exists
        def exists(candidate):
            return candidate == output or real_exists(candidate)
        with patch.object(Path, 'exists', exists):
            with self.assertRaises(FileExistsError):
                recovery.verify(path, recovery.sha(path))

    def test_exact_review_and_partition_are_required_before_key_access(self):
        with tempfile.TemporaryDirectory(dir=recovery.RESULT) as directory:
            folder = Path(directory)
            plan = json.loads(self.plans()[0].read_text())
            plan['new_output'] = str((folder / 'fresh-smoke.jsonl').relative_to(ROOT))
            plan_path = folder / 'plan.json'
            plan_path.write_text(json.dumps(plan))
            plan_sha = recovery.sha(plan_path)
            budget = folder / 'budget.json'
            review = folder / 'review.json'
            entry = {'id': 'qwen36-on-p1-recovery', 'model': recovery.MODEL,
                     'provider': recovery.PROVIDER, 'reasoning': 'on',
                     'cap_usd': '0.09', 'child_ledger': str(folder / 'child.jsonl')}
            budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                'master_ledger': str((recovery.ROOT / 'results/openrouter-paid-budget.jsonl').resolve()),
                'partitions': [entry]}))
            receipt = {'approved': True, 'recovery_plan_sha256': plan_sha,
                       'wrapper_sha256': recovery.sha(recovery.__file__),
                       'budget_manifest_sha256': recovery.sha(budget),
                       'partition_id': entry['id'],
                       'continue_on_known_billing_intrinsic_invalid': True}
            review.write_text(json.dumps(receipt))
            self.assertEqual(recovery.review_execution(plan_path, plan_sha, budget,
                             entry['id'], review)[1]['requests'], 3)
            with patch.object(recovery, 'load_key') as key:
                receipt['wrapper_sha256'] = '0' * 64
                review.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, 'root review'):
                    recovery.execute(plan_path, plan_sha, budget, entry['id'], review)
                key.assert_not_called()
            receipt['wrapper_sha256'] = recovery.sha(recovery.__file__)
            entry['cap_usd'] = '0.08'
            budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                'master_ledger': str((recovery.ROOT / 'results/openrouter-paid-budget.jsonl').resolve()),
                'partitions': [entry]}))
            receipt['budget_manifest_sha256'] = recovery.sha(budget)
            review.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'partition cap'):
                recovery.review_execution(plan_path, plan_sha, budget, entry['id'], review)

    def test_known_billing_intrinsic_invalid_continuation_only(self):
        base = {'status': 'invalid_output', 'billing_ok': True, 'cost_unknown': False,
                'raw_response': {'choices': [{'finish_reason': 'stop', 'message': {}}]},
                'prompt_response_diagnostics': {'blockers': []}}
        self.assertTrue(recovery.continue_smoke(base))
        for change in ({'billing_ok': False}, {'cost_unknown': True},
                       {'prompt_response_diagnostics': {'blockers': ['observed context overflow']}},
                       {'status': 'service_error'},
                       {'raw_response': {'choices': [{'finish_reason': 'length', 'message': {}}]}}):
            with self.subTest(change=change):
                self.assertFalse(recovery.continue_smoke({**base, **change}))

    def test_mocked_smoke_uses_exact_frozen_requests_and_new_outputs(self):
        original = json.loads(self.plans()[0].read_text())
        historical = ROOT / 'results/hosted-prompt-preparation-2026-09-24/openrouter-paid-qwen36-35b-a3b-on/historical-attempts.jsonl'
        model = json.loads(historical.read_text().splitlines()[0])['model_catalog_entry']
        endpoint = recovery.endpoint_from_audit(recovery.ROUTE)
        answer = {'sentiment': 'positive', 'follow_up_needed': 'no',
                  'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        body = {'model': recovery.MODEL, 'provider': recovery.NAME,
                'choices': [{'finish_reason': 'stop',
                             'message': {'content': json.dumps(answer)}}],
                'usage': {'cost': 0.001, 'prompt_tokens': 100, 'completion_tokens': 20}}
        with tempfile.TemporaryDirectory(dir=recovery.RESULT) as directory:
            folder = Path(directory)
            plan_path = folder / 'plan.json'
            original['new_output'] = str((folder / 'smoke.jsonl').relative_to(ROOT))
            plan_path.write_text(json.dumps(original))
            plan_sha = recovery.sha(plan_path)
            entry = {'id': 'mock-partition', 'model': recovery.MODEL,
                     'provider': recovery.PROVIDER, 'reasoning': 'on',
                     'cap_usd': '0.09', 'child_ledger': str(folder / 'child.jsonl')}
            budget = folder / 'budget.json'
            budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                'master_ledger': str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()),
                'partitions': [entry]}))
            review = folder / 'review.json'
            review.write_text(json.dumps({'approved': True, 'recovery_plan_sha256': plan_sha,
                'wrapper_sha256': recovery.sha(recovery.__file__),
                'budget_manifest_sha256': recovery.sha(budget),
                'partition_id': entry['id'],
                'continue_on_known_billing_intrinsic_invalid': True}))
            class Ledger:
                master_cap = 10
                cap = 0.09
                file = SimpleNamespace(name=str(folder / 'child.jsonl'))
                def __init__(self): self.count = 0
                def reserve(self, amount, record_id):
                    self.count += 1
                    return f'attempt-{self.count}'
                def settle(self, attempt, actual): return True
                def accounted(self): return self.count * 0.001
                def close(self): pass
            ledger = Ledger()
            responses = [{'data': [model]}, {'data': {'id': recovery.MODEL, 'endpoints': [endpoint]}}] + [body] * 3
            with patch.object(recovery, 'load_key', return_value='test-token'), \
                 patch.object(recovery, 'fetch', side_effect=responses) as fetch, \
                 patch.object(recovery.partitions, 'open_partition', return_value=ledger):
                recovery.execute(plan_path, plan_sha, budget, entry['id'], review)
            self.assertEqual(fetch.call_count, 5)
            self.assertEqual(ledger.count, 3)
            rows = [json.loads(x) for x in (folder / 'smoke.jsonl').read_text().splitlines()]
            self.assertEqual([r['id'] for r in rows], ['DEV-001', 'DEV-002', 'DEV-003'])
            self.assertTrue(all(r['status'] == 'ok' and r['reference_labels_read'] is False for r in rows))
            attempts = [json.loads(x) for x in (folder / 'smoke.jsonl.attempts.jsonl').read_text().splitlines()]
            self.assertTrue(attempts[-1]['completed'])


if __name__ == '__main__':
    unittest.main()
