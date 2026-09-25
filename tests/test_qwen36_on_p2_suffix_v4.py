import importlib.util
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qwen36_on_p2_suffix_v4', ROOT / 'scripts/qwen36_on_p2_suffix_v4.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@contextmanager
def output_absent_for_admission():
    original_exists = Path.exists
    journal = Path(str(module.OUTPUT) + '.attempts.jsonl')
    with patch.object(Path, 'exists', lambda path: False if path in (module.OUTPUT, journal) else original_exists(path)):
        yield


class Final19Tests(unittest.TestCase):
    def test_plan_admits_only_never_sent_records_within_budget(self):
        with output_absent_for_admission():
            result = module.verify(module.PLAN, module.smoke.sha(module.PLAN))
        self.assertEqual(result['record_ids'], [f'DEV-{i:03}' for i in range(42, 61)])
        self.assertEqual(result['prior_state']['attempted'], 41)
        self.assertEqual(result['prior_state']['failed_ids'], ['DEV-033', 'DEV-039', 'DEV-040', 'DEV-041'])
        self.assertEqual(result['call_bound_usd'], '0.5681152')
        self.assertEqual(result['proposed_partition_cap_usd'], '0.60')

    def test_prior_failed_record_cannot_be_reintroduced(self):
        plan = json.loads(module.PLAN.read_text())
        plan['record_ids'][0] = 'DEV-041'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            path.write_text(json.dumps(plan))
            with patch.object(module, 'RESULT', Path(directory).resolve()):
                with self.assertRaisesRegex(ValueError, 'protocol'):
                    module.verify(path)

    def test_predecessor_evidence_and_frozen_request_fail_closed(self):
        plan = json.loads(module.PLAN.read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            with patch.object(module, 'RESULT', Path(directory).resolve()):
                altered = json.loads(json.dumps(plan))
                altered['sources']['v3_result']['sha256'] = '0' * 64
                path.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, 'Changed source'):
                    module.verify(path)
                altered = json.loads(json.dumps(plan))
                altered['requests'][0] = altered['requests'][1]
                path.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, 'Exact frozen suffix request'):
                    module.verify(path)

    def test_review_and_exclusive_output_gate(self):
        budget = ROOT / 'results/qwen36-on-p2-final20-v3/budget-manifest.json'
        review = ROOT / 'results/qwen36-on-p2-final20-v3/root-review.json'
        with output_absent_for_admission():
            with self.assertRaisesRegex((ValueError, FileNotFoundError), 'root review|No such file'):
                module.review_execution(module.PLAN, module.smoke.sha(module.PLAN),
                                        budget, 'qwen36-on-p2-final19-v4', review)
        original_exists = Path.exists
        with patch.object(Path, 'exists', lambda path: True if path == module.OUTPUT else original_exists(path)):
            with self.assertRaisesRegex(FileExistsError, 'output'):
                module.verify(module.PLAN)

    def test_stop_policy_for_provider_and_unknown_charge(self):
        good = {'billing_ok': True, 'cost_unknown': False,
                'prompt_response_diagnostics': {'blockers': []}, 'status': 'ok'}
        invalid = dict(good, status='invalid_output',
                       raw_response={'choices': [{'finish_reason': 'stop', 'message': {'content': 'bad'}}]})
        self.assertTrue(module.smoke.continue_smoke(good))
        self.assertTrue(module.smoke.continue_smoke(invalid))
        self.assertFalse(module.smoke.continue_smoke(dict(good, status='service_error')))
        self.assertFalse(module.smoke.continue_smoke(dict(invalid, cost_unknown=True)))
        self.assertFalse(module.smoke.continue_smoke(dict(invalid, status='provider_mismatch')))


if __name__ == '__main__':
    unittest.main()
