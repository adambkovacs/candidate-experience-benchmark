"""Offline Gemma 26 repeat freeze checks. No provider or budget call."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_repeat_study as study


class OpenRouterRepeatStudyTest(unittest.TestCase):
    def test_saved_requests_and_rotation(self):
        self.assertEqual(study.ORDERS, {'repeat2': ['P2', 'P1', 'P0'],
                                        'repeat3': ['P1', 'P0', 'P2']})
        for repeat in study.ORDERS:
            plan = study.plan_data(repeat)
            self.assertEqual(plan['historical_pass_order'], ['P0', 'P2', 'P1'])
            self.assertEqual(plan['repeat_status'], 'offline_prepared_no_inference')
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(len(plan['source_bindings']), len({x['path'] for x in plan['source_bindings']}))
            self.assertNotIn('data/pilot/proposed_labels.jsonl', {x['path'] for x in plan['source_bindings']})
            for binding in plan['source_bindings']:
                self.assertEqual(hashlib.sha256((ROOT / binding['path']).read_bytes()).hexdigest(), binding['sha256'])
            for condition, entry in plan['conditions'].items():
                self.assertEqual(len(entry['smoke']), 3)
                self.assertEqual(len(entry['development']), 60)
                self.assertEqual([r['record_id'] for r in entry['development']],
                                 [f'DEV-{i:03d}' for i in range(1, 61)])
                self.assertEqual(entry['smoke'], entry['development'][:3])
                for request in entry['development']:
                    payload = request['payload']
                    self.assertEqual(payload['provider']['only'], ['deepinfra/fp8'])
                    self.assertEqual(payload['reasoning'], {'enabled': False})
                    self.assertEqual(payload['temperature'], 0)
                    self.assertEqual(payload['max_tokens'], 4096)
                    self.assertEqual(study.digest(json.dumps(payload, sort_keys=True)), request['request_sha256'])

    def test_frozen_manifest_hashes(self):
        for repeat in study.ORDERS:
            path = study.BASE / repeat / 'manifest.json'
            self.assertEqual(study.verify(repeat, study.sha(path)), study.plan_data(repeat))
            with self.assertRaisesRegex(ValueError, 'Manifest hash mismatch'):
                study.verify(repeat, '0' * 64)

    def test_source_binding_detects_change(self):
        plan = study.plan_data('repeat2')
        binding = plan['source_bindings'][0]
        with patch.object(study, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'Wave proposal or paired manifest changed'):
                study.plan_data('repeat2')
        self.assertEqual(study.read_bound(binding), (ROOT / binding['path']).read_bytes())


if __name__ == '__main__':
    unittest.main()
