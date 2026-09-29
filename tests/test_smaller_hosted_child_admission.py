import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen36_off_fresh_repeat_admission as qwen_admission
import qwen36_off_fresh_repeat_execution_v2 as qwen_runner
import deepseek_low_fresh_repeat_admission as low_admission
import deepseek_low_fresh_repeat_execution_v2 as low_runner


CASES = ((qwen_admission, qwen_runner, '0.15'),
         (low_admission, low_runner, '0.25'))


def review_for(runner, manifest, budget, partition_id, path):
    receipt = {'approved': True, 'manifest_sha256': runner.sha(manifest),
               'budget_manifest_sha256': runner.sha(budget), 'partition_id': partition_id,
               'phase_index': 0, 'stage': 'smoke',
               'runner_sha256': runner.sha(runner.__file__)}
    path.write_text(json.dumps(receipt))


def budget_for(admission, cap, partition_id, path):
    path.write_text(json.dumps({'master_ledger': str(admission.MASTER.resolve()),
                                'partitions': [{'id': partition_id, 'model': admission.MODEL,
                                                'provider': admission.PROVIDER,
                                                'reasoning': 'off' if admission is qwen_admission else 'low',
                                                'cap_usd': str(cap)}]}))


class SmallerChildAdmissionTests(unittest.TestCase):
    def fixture(self, admission, runner, directory):
        plan_path, manifest_path = directory / 'plan.json', directory / 'manifest.json'
        plan = admission.plan_data()
        plan_path.write_text(json.dumps(plan))
        master_before = hashlib.sha256(admission.MASTER.read_bytes()).hexdigest()
        manifest = runner.freeze(plan_path, manifest_path)
        self.assertEqual(master_before, hashlib.sha256(admission.MASTER.read_bytes()).hexdigest())
        self.assertEqual(manifest['requests_by_condition'], plan['requests_by_condition'])
        self.assertEqual(manifest['schema'], 'affordable-hosted-fresh3-execution-v2')
        self.assertIn(Path(runner.__file__).name,
                      [Path(binding['path']).name for binding in manifest['code_bindings']])
        self.assertNotIn(Path(runner.__file__).name.replace('_v2.py', '.py'),
                         [Path(binding['path']).name for binding in manifest['code_bindings']])
        return manifest_path, manifest

    def test_real_prepare_accepts_smaller_caps_and_preserves_bindings(self):
        for admission, runner, proposed in CASES:
            with self.subTest(config=admission.CONFIG), tempfile.TemporaryDirectory(dir=ROOT) as temp:
                directory = Path(temp)
                manifest_path, manifest = self.fixture(admission, runner, directory)
                budget = directory / 'child-budget.json'
                review = directory / 'review.json'
                partition_id = 'offline-child'
                for cap in (proposed, str(admission.RESERVE), str(admission.CAP)):
                    budget_for(admission, cap, partition_id, budget)
                    review_for(runner, manifest_path, budget, partition_id, review)
                    with patch.object(runner, 'OUTPUT_DIR', directory):
                        loaded, phase, paths = runner.prepare(
                            manifest_path, runner.sha(manifest_path), budget, partition_id,
                            0, 'smoke', review, directory)
                    self.assertEqual(loaded, manifest)
                    self.assertEqual(phase, manifest['phases'][0])
                    self.assertFalse(any(path.exists() for path in paths.values()))
                self.assertEqual(runner.sha(manifest_path), hashlib.sha256(manifest_path.read_bytes()).hexdigest())
                changed = json.loads(json.dumps(manifest))
                changed['code_bindings'][1]['sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'Execution code drift'):
                    runner.verify_sources(changed)

    def test_outside_cap_range_fails_before_key_or_claim(self):
        for admission, runner, _ in CASES:
            with self.subTest(config=admission.CONFIG), tempfile.TemporaryDirectory(dir=ROOT) as temp:
                directory = Path(temp)
                manifest_path, _ = self.fixture(admission, runner, directory)
                budget = directory / 'child-budget.json'
                review = directory / 'review.json'
                partition_id = 'offline-child'
                for cap in ('0.31', str(admission.RESERVE / 2)):
                    budget_for(admission, cap, partition_id, budget)
                    review_for(runner, manifest_path, budget, partition_id, review)
                    with patch.object(runner, 'OUTPUT_DIR', directory), \
                         patch.object(runner.paid, 'load_key') as key, \
                         patch.object(runner.paid, 'fetch') as fetch:
                        with self.assertRaisesRegex(ValueError, 'Exact child partition differs'):
                            runner.execute(manifest_path, runner.sha(manifest_path), budget,
                                           partition_id, 0, 'smoke', review, directory)
                        key.assert_not_called()
                        fetch.assert_not_called()
                    self.assertFalse(runner.paths(directory, 0, 'smoke')['claim'].exists())

    def test_stale_actual_budget_receipt_hash_fails(self):
        for admission, runner, proposed in CASES:
            with self.subTest(config=admission.CONFIG), tempfile.TemporaryDirectory(dir=ROOT) as temp:
                directory = Path(temp)
                manifest_path, _ = self.fixture(admission, runner, directory)
                budget = directory / 'child-budget.json'
                review = directory / 'review.json'
                partition_id = 'offline-child'
                budget_for(admission, proposed, partition_id, budget)
                review_for(runner, manifest_path, budget, partition_id, review)
                budget.write_text(budget.read_text() + '\n')
                with patch.object(runner, 'OUTPUT_DIR', directory):
                    with self.assertRaisesRegex(ValueError, 'review receipt'):
                        runner.prepare(manifest_path, runner.sha(manifest_path), budget,
                                       partition_id, 0, 'smoke', review, directory)
                self.assertFalse(runner.paths(directory, 0, 'smoke')['claim'].exists())


if __name__ == '__main__':
    unittest.main()
