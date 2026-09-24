import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen36_prompt_full60_v1 as full
import qwen36_prompt_recovery_v1 as smoke


class Full60Test(unittest.TestCase):
    def plans(self):
        return [full.RESULT / f'{mode}-{variant.lower()}-full60-plan.json'
                for mode, variant in smoke.ORDER]

    def fixture(self, folder, original):
        plan = copy.deepcopy(original)
        plan['new_output'] = str((folder / 'development.jsonl').relative_to(ROOT))
        path = folder / 'plan.json'
        path.write_text(json.dumps(plan))
        digest = smoke.sha(path)
        entry = {'id': 'qwen36-full60-test', 'model': smoke.MODEL,
                 'provider': smoke.PROVIDER, 'reasoning': plan['reasoning'],
                 'cap_usd': '1.80', 'child_ledger': str(folder / 'child.jsonl')}
        budget = folder / 'budget.json'
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()),
            'partitions': [entry]}))
        receipt = {'approved': True, 'full60_plan_sha256': digest,
                   'wrapper_sha256': smoke.sha(full.__file__),
                   'budget_manifest_sha256': smoke.sha(budget),
                   'partition_id': entry['id'],
                   'smoke_result_sha256': plan['smoke_result']['sha256'],
                   'continue_on_known_billing_intrinsic_invalid': True}
        review = folder / 'review.json'
        review.write_text(json.dumps(receipt))
        return path, digest, budget, entry['id'], review, receipt

    def test_four_plans_bind_sixty_unsent_requests_and_completed_smoke(self):
        for path in self.plans():
            with self.subTest(path=path.name):
                result = full.verify(path, smoke.sha(path))
                self.assertEqual(result['records'], 60)
                self.assertEqual(result['sixty_call_bound_usd'], '1.7940480')
                self.assertEqual(result['proposed_partition_cap_usd'], '1.80')
                self.assertEqual(result['smoke_inspection']['status'], 'passed')
                plan = json.loads(path.read_text())
                self.assertEqual(len(plan['requests']), 60)
                self.assertFalse(plan['original_timing_preserved'])

    def test_request_and_smoke_hash_drift_block(self):
        original = json.loads(self.plans()[0].read_text())
        with tempfile.TemporaryDirectory(dir=full.RESULT) as directory:
            folder = Path(directory)
            path, digest, _, _, _, _ = self.fixture(folder, original)
            self.assertEqual(full.verify(path, digest)['records'], 60)
            for field, value, message in (
                ('requests', original['requests'][:59], 'requests differ'),
                ('sixty_call_bound_usd', '1.7', 'reserve or partition'),
                ('smoke_result', {'file': original['smoke_result']['file'], 'sha256': '0' * 64}, 'Changed source')):
                with self.subTest(field=field):
                    changed = copy.deepcopy(original)
                    changed['new_output'] = str((folder / 'development.jsonl').relative_to(ROOT))
                    changed[field] = value
                    path.write_text(json.dumps(changed))
                    with self.assertRaisesRegex(ValueError, message):
                        full.verify(path, smoke.sha(path))

    def test_exact_review_before_key_and_partition_cap(self):
        with tempfile.TemporaryDirectory(dir=full.RESULT) as directory:
            folder = Path(directory)
            path, digest, budget, pid, review, receipt = self.fixture(folder, json.loads(self.plans()[0].read_text()))
            self.assertEqual(full.review_execution(path, digest, budget, pid, review)[1]['records'], 60)
            receipt['wrapper_sha256'] = '0' * 64
            review.write_text(json.dumps(receipt))
            with patch.object(full, 'load_key') as key:
                with self.assertRaisesRegex(ValueError, 'root review'):
                    full.execute(path, digest, budget, pid, review)
                key.assert_not_called()
            receipt['wrapper_sha256'] = smoke.sha(full.__file__)
            data = json.loads(budget.read_text())
            data['partitions'][0]['cap_usd'] = '1.79'
            budget.write_text(json.dumps(data))
            receipt['budget_manifest_sha256'] = smoke.sha(budget)
            review.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'partition cap'):
                full.review_execution(path, digest, budget, pid, review)

    def test_mocked_full60_uses_bound_inputs_and_new_outputs(self):
        original = json.loads(self.plans()[0].read_text())
        historical = ROOT / 'results/hosted-prompt-preparation-2026-09-24/openrouter-paid-qwen36-35b-a3b-on/historical-attempts.jsonl'
        model = json.loads(historical.read_text().splitlines()[0])['model_catalog_entry']
        endpoint = smoke.endpoint_from_audit(smoke.ROUTE)
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        body = {'model': smoke.MODEL, 'provider': smoke.NAME,
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(prediction)}}],
                'usage': {'cost': 0.001, 'prompt_tokens': 100, 'completion_tokens': 20}}
        with tempfile.TemporaryDirectory(dir=full.RESULT) as directory:
            folder = Path(directory)
            path, digest, budget, pid, review, _ = self.fixture(folder, original)
            class Ledger:
                master_cap = 10
                cap = 1.80
                file = SimpleNamespace(name=str(folder / 'child.jsonl'))
                def __init__(self): self.count = 0
                def reserve(self, amount, record_id):
                    self.count += 1
                    return f'attempt-{self.count}'
                def settle(self, attempt, actual): return True
                def accounted(self): return self.count * 0.001
                def close(self): pass
            ledger = Ledger()
            responses = [{'data': [model]}, {'data': {'id': smoke.MODEL, 'endpoints': [endpoint]}}] + [body] * 60
            with patch.object(full, 'load_key', return_value='test-token'), \
                 patch.object(full, 'fetch', side_effect=responses) as fetch, \
                 patch.object(full.partitions, 'open_partition', return_value=ledger):
                full.execute(path, digest, budget, pid, review)
            self.assertEqual(fetch.call_count, 62)
            self.assertEqual(ledger.count, 60)
            rows = [json.loads(line) for line in (folder / 'development.jsonl').read_text().splitlines()]
            self.assertEqual([r['id'] for r in rows], [f'DEV-{i:03}' for i in range(1, 61)])
            self.assertTrue(all(r['status'] == 'ok' and r['reference_labels_read'] is False for r in rows))
            events = [json.loads(line) for line in (folder / 'development.jsonl.attempts.jsonl').read_text().splitlines()]
            self.assertTrue(events[-1]['completed'])


if __name__ == '__main__':
    unittest.main()
