"""Offline controls for the audited GPT-6 Sol medium repeat lane."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import codex_repeat_sol_medium as next_lane
import codex_repeat_study as luna_runner
import codex_repeat_next as sol_high

next_lane.configure_runner()
runner = next_lane.runner


class SolMediumRepeatTest(unittest.TestCase):
    def test_historical_request_bytes_and_rotation(self):
        self.assertEqual(next_lane.HISTORICAL_ORDER, ['P0', 'P2', 'P1'])
        self.assertEqual(next_lane.ORDERS, {'repeat2': ['P2', 'P1', 'P0'],
                                            'repeat3': ['P1', 'P0', 'P2']})
        for repeat in next_lane.ORDERS:
            plan = next_lane.plan_data(repeat)
            self.assertEqual(plan['configuration_id'], next_lane.CONFIG)
            self.assertEqual(plan['model'], 'gpt-6-sol')
            self.assertEqual(plan['effort'], 'medium')
            self.assertEqual(plan['eligibility_addendum'], next_lane.AUDIT)
            self.assertEqual(plan['timeout_seconds'], 600.0)
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(plan['runtime_amendment']['historical_p0'], next_lane.P0_RUNTIME)
            self.assertEqual(plan['runtime_amendment']['from'], next_lane.PREVIOUS_RUNTIME)
            self.assertEqual(plan['runtime_amendment']['to'], next_lane.RUNTIME)
            for binding in plan['source_bindings']:
                self.assertEqual(hashlib.sha256((ROOT / binding['path']).read_bytes()).hexdigest(), binding['sha256'])
            for condition, entry in plan['conditions'].items():
                self.assertEqual(len(entry['development']), 6)
                self.assertEqual(entry['smoke']['record_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
                ids = [rid for req in entry['development'] for rid in req['record_ids']]
                self.assertEqual(ids, [f'DEV-{n:03d}' for n in range(1, 61)])
                for request in [entry['smoke'], *entry['development']]:
                    self.assertEqual(request['repeat'], repeat)
                    self.assertEqual(request['condition'], condition)
                    self.assertNotIn('proposed_labels', json.dumps(request))
                    self.assertEqual(runner.digest(request['request']['prompt']), request['request_sha256'])

    def test_runner_is_bound_to_this_lane(self):
        self.assertEqual(runner.BASE, next_lane.BASE)
        self.assertIs(runner.plan_data, next_lane.plan_data)
        self.assertEqual(runner.MODEL, 'gpt-6-sol')
        self.assertEqual(runner.EFFORT, 'medium')
        self.assertEqual(luna_runner.CONFIG, 'codex-gpt-6-luna-medium-batch10')
        self.assertNotEqual(luna_runner.BASE, runner.BASE)
        self.assertIsNot(luna_runner.plan_data, runner.plan_data)
        self.assertEqual(sol_high.CONFIG, 'codex-gpt-6-sol-high-batch10')
        self.assertIsNot(sol_high.runner, runner)

    def test_manifests_are_hash_bound_without_reference_file(self):
        for repeat in next_lane.ORDERS:
            path = next_lane.BASE / repeat / 'manifest.json'
            self.assertEqual(runner.verify_manifest(repeat, runner.filehash(path)), next_lane.plan_data(repeat))
            with self.assertRaisesRegex(ValueError, 'Manifest hash mismatch'):
                runner.verify_manifest(repeat, '0' * 64)
            bound = {item['path'] for item in next_lane.plan_data(repeat)['source_bindings']}
            self.assertNotIn('data/pilot/proposed_labels.jsonl', bound)

    def test_schedule_blocks_skipped_condition_before_runtime(self):
        plan = next_lane.plan_data('repeat2')
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, 'BASE', Path(temp)):
            with patch.object(runner, 'runtime_check', side_effect=AssertionError('runtime called')):
                with self.assertRaisesRegex(ValueError, 'Previous condition lacks completed development'):
                    runner.run_phase(plan, 'P1', 'smoke', '/unused/codex')
            self.assertFalse((runner.BASE / 'repeat2' / 'P1' / 'smoke.claim.json').exists())

    def test_repeat_three_requires_repeat_two_before_runtime(self):
        plan = next_lane.plan_data('repeat3')
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, 'BASE', Path(temp)):
            with patch.object(runner, 'runtime_check', side_effect=AssertionError('runtime called')):
                with self.assertRaisesRegex(ValueError, 'Repeat two is incomplete'):
                    runner.run_phase(plan, 'P1', 'smoke', '/unused/codex')
            self.assertFalse((runner.BASE / 'repeat3' / 'P1' / 'smoke.claim.json').exists())

    def test_development_requires_inspected_smoke(self):
        plan = next_lane.plan_data('repeat2')
        with tempfile.TemporaryDirectory() as temp, patch.object(runner, 'BASE', Path(temp)):
            with patch.object(runner, 'runtime_check', side_effect=AssertionError('runtime called')):
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    runner.run_phase(plan, 'P2', 'development', '/unused/codex')


if __name__ == '__main__':
    unittest.main()
