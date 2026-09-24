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
import qwen36_off_p2_suffix_v1 as suffix
import qwen36_prompt_recovery_v1 as smoke


class SuffixTest(unittest.TestCase):
    def fixture(self, folder):
        plan = copy.deepcopy(json.loads(suffix.PLAN.read_text()))
        plan['new_output'] = str((folder / 'suffix.jsonl').relative_to(ROOT))
        path = folder / 'plan.json'
        path.write_text(json.dumps(plan))
        digest = smoke.sha(path)
        entry = {'id': 'qwen36-suffix-test', 'model': smoke.MODEL,
                 'provider': smoke.PROVIDER, 'reasoning': 'off',
                 'cap_usd': '0.22', 'child_ledger': str(folder / 'child.jsonl')}
        budget = folder / 'budget.json'
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()),
            'partitions': [entry]}))
        receipt = {'approved': True, 'suffix_plan_sha256': digest,
                   'wrapper_sha256': smoke.sha(suffix.__file__),
                   'budget_manifest_sha256': smoke.sha(budget),
                   'partition_id': entry['id'],
                   'preserved_original_result_sha256': plan['original_result']['sha256'],
                   'continue_on_known_billing_intrinsic_invalid': True}
        review = folder / 'review.json'
        review.write_text(json.dumps(receipt))
        return path, digest, budget, entry['id'], review, receipt

    def test_only_never_sent_suffix_and_original_failure_preserved(self):
        with tempfile.TemporaryDirectory(dir=suffix.RESULT) as directory:
            path, digest, *_ = self.fixture(Path(directory))
            result = suffix.verify(path, digest)
            self.assertEqual(result['record_ids'], [f'DEV-{i:03}' for i in range(54, 61)])
            self.assertEqual(result['seven_call_bound_usd'], '0.2093056')
            self.assertEqual(result['preserved_prefix']['failed_id'], 'DEV-053')
            self.assertEqual(result['preserved_prefix']['failed_status'], 'HTTP429_unknown_billing')

    def test_failed_record_and_review_drift_block_before_key(self):
        with tempfile.TemporaryDirectory(dir=suffix.RESULT) as directory:
            folder = Path(directory)
            path, digest, budget, pid, review, receipt = self.fixture(folder)
            plan = json.loads(path.read_text())
            plan['record_ids'] = [f'DEV-{i:03}' for i in range(53, 61)]
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'never-sent'):
                suffix.verify(path, smoke.sha(path))
            path, digest, budget, pid, review, receipt = self.fixture(folder)
            receipt['wrapper_sha256'] = '0' * 64
            review.write_text(json.dumps(receipt))
            with patch.object(suffix, 'load_key') as key:
                with self.assertRaisesRegex(ValueError, 'root review'):
                    suffix.execute(path, digest, budget, pid, review)
                key.assert_not_called()

    def test_mocked_execution_sends_exact_seven_and_no_dev053(self):
        historical = ROOT / 'results/hosted-prompt-preparation-2026-09-24/openrouter-paid-qwen36-35b-a3b-off/historical-attempts.jsonl'
        model = json.loads(historical.read_text().splitlines()[0])['model_catalog_entry']
        endpoint = smoke.endpoint_from_audit(smoke.ROUTE)
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        body = {'model': smoke.MODEL, 'provider': smoke.NAME,
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(prediction)}}],
                'usage': {'cost': 0.001, 'prompt_tokens': 100, 'completion_tokens': 20}}
        with tempfile.TemporaryDirectory(dir=suffix.RESULT) as directory:
            folder = Path(directory)
            path, digest, budget, pid, review, _ = self.fixture(folder)
            class Ledger:
                master_cap = 10
                cap = 0.22
                file = SimpleNamespace(name=str(folder / 'child.jsonl'))
                def __init__(self): self.ids = []
                def reserve(self, amount, record_id):
                    self.ids.append(record_id)
                    return f'attempt-{len(self.ids)}'
                def settle(self, attempt, actual): return True
                def accounted(self): return len(self.ids) * 0.001
                def close(self): pass
            ledger = Ledger()
            responses = [{'data': [model]}, {'data': {'id': smoke.MODEL, 'endpoints': [endpoint]}}] + [body] * 7
            with patch.object(suffix, 'load_key', return_value='test-token'), \
                 patch.object(suffix, 'fetch', side_effect=responses) as fetch, \
                 patch.object(suffix.partitions, 'open_partition', return_value=ledger):
                suffix.execute(path, digest, budget, pid, review)
            self.assertEqual(fetch.call_count, 9)
            self.assertEqual(ledger.ids, [f'DEV-{i:03}' for i in range(54, 61)])
            rows = [json.loads(line) for line in (folder / 'suffix.jsonl').read_text().splitlines()]
            self.assertEqual([r['id'] for r in rows], ledger.ids)
            self.assertTrue(all(r['status'] == 'ok' and r['reference_labels_read'] is False for r in rows))
            events = [json.loads(line) for line in (folder / 'suffix.jsonl.attempts.jsonl').read_text().splitlines()]
            self.assertTrue(events[-1]['completed'])


if __name__ == '__main__':
    unittest.main()
