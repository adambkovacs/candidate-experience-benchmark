"""Offline admission checks for the new Sonnet 5.5 subscription lanes."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import claude_sonnet55_matched3 as lane


class Sonnet55MatchedThreeTest(unittest.TestCase):
    def test_four_efforts_three_passes_and_input_isolation(self):
        for effort in lane.EFFORTS:
            lane.configure(effort)
            for pass_name, order in lane.ORDERS.items():
                with self.subTest(effort=effort, pass_name=pass_name):
                    plan = lane.plan_data(pass_name)
                    self.assertEqual(plan['model'], 'claude-sonnet-5-5')
                    self.assertEqual(plan['effort'], effort)
                    self.assertEqual(plan['condition_order'], order)
                    self.assertFalse(plan['reference_labels_read'])
                    for condition in ('P0', 'P1', 'P2'):
                        batches = plan['conditions'][condition]['development']
                        self.assertEqual(len(batches), 6)
                        self.assertEqual([rid for batch in batches for rid in batch['record_ids']],
                                         [f'DEV-{i:03d}' for i in range(1, 61)])
                        for batch in [plan['conditions'][condition]['smoke'], *batches]:
                            self.assertEqual(batch['request']['input'], json.loads(batch['input_text']))
                            self.assertEqual([set(row) for row in batch['request']['input']['records']],
                                             [{'id', 'feedback'}] * len(batch['record_ids']))
                            self.assertNotIn('prediction', json.dumps(batch))

    def test_manifest_binding_and_no_replay(self):
        lane.configure('low')
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(lane, 'BASE', Path(temporary)):
                lane.prepare()
                manifest_path = lane.BASE / 'pass1/manifest.json'
                manifest = lane.verify_manifest('pass1', lane.sha(manifest_path))
                binding_paths = {binding['path'] for binding in manifest['source_bindings']}
                self.assertIn('scripts/development_benchmark.py', binding_paths)
                with self.assertRaisesRegex(ValueError, 'Previous condition incomplete'):
                    lane.run_phase(manifest, 'P1', 'smoke', str(lane.CLI),
                                   '/unused', '0' * 64, '/unused', '0' * 64)
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    lane.verify_manifest('pass1', '0' * 64)

    def test_development_needs_separate_review_bound_to_inspected_smoke(self):
        lane.configure('low')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(lane, 'BASE', root / 'series'):
                lane.prepare()
                manifest = lane.verify_manifest('pass1', lane.sha(lane.BASE / 'pass1/manifest.json'))
                preflight_hash = 'p' * 64
                review_path = root / 'root-review.json'

                def review(phases, inspection_hash):
                    value = {
                        'schema': 'claude-sonnet55-fresh-matched3-root-review-v2',
                        'approved': True, 'configuration_id': lane.CONFIG, 'pass': 'pass1',
                        'manifest_sha256': lane.sha(lane.BASE / 'pass1/manifest.json'),
                        'controller_sha256': lane.sha(ROOT / 'scripts/claude_sonnet55_matched3.py'),
                        'mechanics_sha256': lane.sha(ROOT / 'scripts/claude_repeat_study.py'),
                        'roster_sha256': lane.sha(ROOT / 'scripts/claude_repeat_roster.py'),
                        'private_preflight_sha256': preflight_hash,
                        'cli_path': str(lane.CLI), 'cli_version': lane.RUNTIME,
                        'approved_phases': phases, 'smoke_inspection_sha256': inspection_hash,
                        'review_note': 'Offline gate test'}
                    review_path.write_text(json.dumps(value) + '\n')
                    return lane.sha(review_path)

                smoke = {'condition': 'P0', 'phase': 'smoke'}
                development = {'condition': 'P0', 'phase': 'development'}
                both_hash = review([smoke, development], None)
                with self.assertRaisesRegex(ValueError, 'root review differs'):
                    lane.root_review(review_path, both_hash, manifest, preflight_hash,
                                     'P0', 'smoke', None)
                smoke_review_hash = review([smoke], None)
                lane.root_review(review_path, smoke_review_hash, manifest, preflight_hash,
                                 'P0', 'smoke', None)

                # The smoke review cannot admit development, even after smoke closes.
                smoke_folder, claim, attempts, records, journal = lane.phase_paths(
                    'pass1', 'P0', 'smoke')
                smoke_folder.mkdir(parents=True)
                claim.write_text('{}\n')
                attempts.write_text('{}\n')
                records.write_text('{}\n')
                journal.write_text('{"event":"phase_completed"}\n')
                inspection = smoke_folder / 'smoke-inspection.json'
                inspection.write_text(json.dumps({
                    'inspection': 'accepted_unchanged',
                    'attempts_sha256': lane.sha(attempts),
                    'records_sha256': lane.sha(records),
                    'journal_sha256': lane.sha(journal)}) + '\n')
                with patch.object(lane, 'private_preflight'):
                    with self.assertRaisesRegex(ValueError, 'root review differs'):
                        lane._admit(manifest, 'P0', 'development', str(lane.CLI),
                                    review_path, smoke_review_hash, root / 'private', preflight_hash)

                    stale_hash = review([development], '0' * 64)
                    with self.assertRaisesRegex(ValueError, 'root review differs'):
                        lane._admit(manifest, 'P0', 'development', str(lane.CLI),
                                    review_path, stale_hash, root / 'private', preflight_hash)

                    current_hash = review([development], lane.sha(inspection))
                    lane._admit(manifest, 'P0', 'development', str(lane.CLI),
                                review_path, current_hash, root / 'private', preflight_hash)

    def test_excludes_max_and_ultra(self):
        for effort in ('max', 'ultra', 'not_applicable'):
            with self.assertRaises(ValueError):
                lane.configure(effort)


if __name__ == '__main__':
    unittest.main()
