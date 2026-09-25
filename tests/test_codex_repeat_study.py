"""Offline guards for the bounded Codex repeat lane. No inference calls."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import codex_repeat_study as study


class CodexRepeatStudyTest(unittest.TestCase):
    def test_frozen_historical_requests_and_rotation(self):
        for repeat, expected_order in study.ORDERS.items():
            plan = study.plan_data(repeat)
            self.assertEqual(plan['condition_order'], expected_order)
            self.assertEqual(plan['historical_pass_order'], ['P0','P2','P1'])
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(plan['runtime_amendment']['from'], study.PREVIOUS_RUNTIME)
            self.assertEqual(plan['runtime_amendment']['to'], study.RUNTIME)
            self.assertEqual(len(plan['source_bindings']), len({b['path'] for b in plan['source_bindings']}))
            for binding in plan['source_bindings']:
                self.assertEqual(hashlib.sha256((ROOT / binding['path']).read_bytes()).hexdigest(), binding['sha256'])
            for condition, entry in plan['conditions'].items():
                self.assertEqual(len(entry['development']), 6)
                self.assertEqual(entry['smoke']['record_ids'], ['DEV-001','DEV-002','DEV-003'])
                self.assertEqual(len(entry['smoke']['record_ids']), 3)
                ids = [rid for req in entry['development'] for rid in req['record_ids']]
                self.assertEqual(ids, [f'DEV-{n:03d}' for n in range(1,61)])
                for request in [entry['smoke'],*entry['development']]:
                    self.assertEqual(request['repeat'], repeat)
                    self.assertEqual(request['condition'], condition)
                    self.assertNotIn('proposed_labels', json.dumps(request))
                    self.assertEqual(study.digest(request['request']['prompt']), request['request_sha256'])

    def test_manifests_are_hash_bound(self):
        for repeat in study.ORDERS:
            path = study.BASE / repeat / 'manifest.json'
            self.assertEqual(study.verify_manifest(repeat, study.filehash(path)), study.plan_data(repeat))
            with self.assertRaisesRegex(ValueError, 'Manifest hash mismatch'):
                study.verify_manifest(repeat, '0' * 64)

    def test_schedule_blocks_condition_skipping_before_runtime(self):
        manifest = study.plan_data('repeat2')
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'runtime_check', side_effect=AssertionError('runtime was called')):
                with self.assertRaisesRegex(ValueError, 'Previous condition lacks completed development'):
                    study.run_phase(manifest, 'P1', 'smoke', '/unused/codex')
            self.assertFalse((study.BASE/'repeat2'/'P1'/'smoke.claim.json').exists())

    def test_repeat_three_waits_for_repeat_two(self):
        manifest = study.plan_data('repeat3')
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'runtime_check', side_effect=AssertionError('runtime was called')):
                with self.assertRaisesRegex(ValueError, 'Repeat two is incomplete'):
                    study.run_phase(manifest, 'P1', 'smoke', '/unused/codex')
            self.assertFalse((study.BASE/'repeat3'/'P1'/'smoke.claim.json').exists())

    def test_development_requires_inspected_smoke_before_runtime(self):
        manifest = study.plan_data('repeat2')
        with tempfile.TemporaryDirectory() as temp, patch.object(study, 'BASE', Path(temp)):
            with patch.object(study, 'runtime_check', side_effect=AssertionError('runtime was called')):
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    study.run_phase(manifest, 'P2', 'development', '/unused/codex')
            self.assertFalse((study.BASE/'repeat2'/'P2'/'development.claim.json').exists())


if __name__ == '__main__':
    unittest.main()
