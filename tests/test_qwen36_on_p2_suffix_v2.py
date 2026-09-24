import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('qwen36_on_p2_suffix_v2', ROOT / 'scripts/qwen36_on_p2_suffix_v2.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Final21Tests(unittest.TestCase):
    def test_frozen_plan_exact_never_sent_ids_and_cost(self):
        result = module.verify(module.PLAN, module.smoke.sha(module.PLAN))
        self.assertEqual(result['record_ids'], [f'DEV-{i:03}' for i in range(40, 61)])
        self.assertEqual(result['prior_state']['failed_ids'], ['DEV-033', 'DEV-039'])
        self.assertEqual(result['prior_state']['attempted'], 39)
        self.assertEqual(result['call_bound_usd'], '0.6279168')
        self.assertEqual(result['proposed_partition_cap_usd'], '0.64')

    def test_tampered_plan_or_source_binding_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=module.RESULT) as directory:
            path = Path(directory) / 'plan.json'
            plan = json.loads(module.PLAN.read_text())
            plan['record_ids'][0] = 'DEV-039'
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'protocol differs'):
                module.verify(path)
            plan = json.loads(module.PLAN.read_text())
            plan['sources']['v1_result']['sha256'] = '0' * 64
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Changed source'):
                module.verify(path)
        with self.assertRaisesRegex(ValueError, 'plan hash mismatch'):
            module.verify(module.PLAN, '0' * 64)

    def test_started_dev040_claim_is_rejected(self):
        original = module.read_lines
        def changed(path):
            data = original(path)
            if path == module.V1_JOURNAL:
                return data[:-1] + [{'event': 'started', 'id': 'DEV-040'}] + data[-1:]
            return data
        with patch.object(module, 'read_lines', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'started claims'):
                module.verify(module.PLAN)

    def test_output_exclusivity_and_review_gate(self):
        original_exists = Path.exists
        with patch.object(Path, 'exists', lambda path: True if path == module.OUTPUT else original_exists(path)):
            with self.assertRaisesRegex(FileExistsError, 'output'):
                module.verify(module.PLAN)
        with tempfile.TemporaryDirectory(dir=module.RESULT) as directory:
            folder = Path(directory)
            budget = folder / 'budget.json'
            review = folder / 'review.json'
            budget.write_text('{}')
            review.write_text(json.dumps({'approved': False}))
            with self.assertRaisesRegex(ValueError, 'root review'):
                module.review_execution(module.PLAN, module.smoke.sha(module.PLAN), budget, 'new-partition', review)


if __name__ == '__main__':
    unittest.main()
