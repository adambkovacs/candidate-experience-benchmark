"""Offline gates for the shared Codex subscription repeat roster."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import codex_repeat_roster as roster
import codex_repeat_study as canonical


class RosterTests(unittest.TestCase):
    def test_all_fifteen_lanes_rebuild_exact_historical_batches(self):
        self.assertEqual(len(roster.CONFIGS), 15)
        for config in roster.CONFIGS:
            with self.subTest(config=config):
                second = roster.plan_data(config, 'repeat2')
                third = roster.plan_data(config, 'repeat3')
                self.assertEqual(second['historical_pass_order'][0], 'P0')
                self.assertEqual(second['condition_order'], roster.schedule(second['historical_pass_order'])['repeat2'])
                self.assertEqual(third['condition_order'], roster.schedule(second['historical_pass_order'])['repeat3'])
                self.assertEqual(second['batch_size'], 10)
                self.assertFalse(second['reference_labels_read'])
                self.assertEqual(second['effort'] in ('max', 'ultra'), False)
                self.assertIn('scripts/codex_repeat_roster.py', [x['path'] for x in second['source_bindings']])
                for condition in ('P0', 'P1', 'P2'):
                    one = second['conditions'][condition]
                    two = third['conditions'][condition]
                    self.assertEqual(len(one['development']), 6)
                    self.assertEqual(len(one['smoke']['record_ids']), 3)
                    self.assertEqual([len(x['record_ids']) for x in one['development']], [10] * 6)
                    self.assertEqual([x['request'] for x in one['development']],
                                     [x['request'] for x in two['development']])
                    self.assertEqual([x['record_ids'] for x in one['development']],
                                     [[f'DEV-{i:03d}' for i in range(start, start + 10)]
                                      for start in range(1, 61, 10)])

    def test_other_roster_members_and_bad_schedule_are_rejected(self):
        for config in ('codex-gpt-6-luna-medium-batch10',
                       'codex-gpt-6-sol-high-batch10',
                       'codex-gpt-6-sol-medium-batch10',
                       'codex-gpt-6-astra-ultra'):
            with self.subTest(config=config), self.assertRaises(ValueError):
                roster.plan_data(config, 'repeat2')
        with self.assertRaises(ValueError):
            roster.schedule(['P0', 'P1', 'P1'])

    def test_private_runner_does_not_change_canonical_luna_lane(self):
        original = (canonical.CONFIG, canonical.BASE, canonical.MODEL,
                    canonical.EFFORT, canonical.TIMEOUT, canonical.plan_data)
        runner = roster.configured_runner('codex-gpt-5.6-luna-high')
        self.assertEqual(runner.CONFIG, 'codex-gpt-5.6-luna-high')
        self.assertEqual(runner.MODEL, 'gpt-5.6-luna')
        self.assertEqual(runner.EFFORT, 'high')
        self.assertEqual((canonical.CONFIG, canonical.BASE, canonical.MODEL,
                          canonical.EFFORT, canonical.TIMEOUT, canonical.plan_data), original)
        self.assertIsNot(runner, canonical)

    def test_root_review_requires_exact_controls_and_fresh_positive_quota(self):
        config = roster.CONFIGS[0]
        manifest = roster.plan_data(config, 'repeat2')
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as private_folder:
            temporary = Path(folder)
            plan_path = temporary / 'repeat2' / 'manifest.json'
            plan_path.parent.mkdir()
            plan_path.write_text(json.dumps(manifest) + '\n')
            runner = type('PrivateRunner', (), {'BASE': temporary, 'filehash': staticmethod(
                lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())})()
            now = datetime.now(timezone.utc)
            review = {'schema': roster.REVIEW_SCHEMA, 'approved': True,
                      'configuration_id': config, 'repeat': 'repeat2',
                      'condition': 'P2', 'phase': 'smoke',
                      'manifest_sha256': runner.filehash(plan_path),
                      'controller_sha256': runner.filehash(roster.CONTROLLER),
                      'model': manifest['model'], 'effort': manifest['effort'],
                      'runtime': roster.RUNTIME,
                      'quota': {'source': 'Codex get_usage_limits',
                                'checked_at_utc': now.isoformat(),
                                'ordinary_usage_allowed': True,
                                'spend_control_reached': False,
                                'weekly_remaining_percent': 98,
                                'five_hour_remaining_percent': None}}
            receipt = Path(private_folder) / 'review.json'
            def gate(value, phase='smoke'):
                receipt.write_text(json.dumps(value) + '\n')
                with patch.object(roster, 'ROOT', temporary):
                    return roster.review_gate(runner, manifest, 'repeat2', 'P2', phase,
                                              receipt, runner.filehash(receipt), now=now)
            self.assertEqual(gate(review), review)
            with patch.object(roster, 'ROOT', temporary), self.assertRaisesRegex(ValueError, 'outside the public repository'):
                public_copy = temporary / 'private-should-not-publish.json'
                public_copy.write_text(json.dumps(review) + '\n')
                roster.review_gate(runner, manifest, 'repeat2', 'P2', 'smoke',
                                   public_copy, runner.filehash(public_copy), now=now)
            for bad in ({'approved': False}, {'condition': 'P1'}, {'runtime': 'different'}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    gate({**review, **bad})
            for bad in ({'weekly_remaining_percent': 0},
                        {'ordinary_usage_allowed': False},
                        {'spend_control_reached': True},
                        {'checked_at_utc': (now - timedelta(minutes=6)).isoformat()}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    gate({**review, 'quota': {**review['quota'], **bad}})
            inspection = temporary / 'repeat2' / 'P2' / 'smoke-inspection.json'
            inspection.parent.mkdir()
            inspection.write_text('{"inspection":"accepted_unchanged"}\n')
            development = {**review, 'phase': 'development',
                           'smoke_inspection_sha256': runner.filehash(inspection)}
            self.assertEqual(gate(development, 'development'), development)
            with self.assertRaisesRegex(ValueError, 'smoke inspection'):
                gate({**development, 'smoke_inspection_sha256': '0' * 64}, 'development')

            gate(development, 'development')
            attestation = roster.attest_admission(runner, manifest, 'repeat2', 'P2',
                                                  'development', runner.filehash(receipt))
            public = attestation.read_text()
            self.assertIn('admitted_before_dispatch', public)
            self.assertIn('"dispatch_status": "not_asserted"', public)
            for private in ('weekly_remaining_percent', 'five_hour_remaining_percent',
                            str(receipt), 'checked_at_utc', '"quota"'):
                self.assertNotIn(private, public)
            self.assertEqual(roster.attest_admission(runner, manifest, 'repeat2', 'P2',
                                                    'development', runner.filehash(receipt)), attestation)

    def test_runtime_failure_does_not_turn_admission_into_dispatch_claim(self):
        config = roster.CONFIGS[0]
        manifest = roster.plan_data(config, 'repeat2')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            plan_path = base / 'repeat2' / 'manifest.json'
            plan_path.parent.mkdir()
            plan_path.write_text(json.dumps(manifest) + '\n')
            runner = Mock()
            runner.BASE = base
            runner.filehash.side_effect = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            runner.verify_manifest.return_value = manifest
            runner.run_phase.side_effect = RuntimeError('CLI authentication unavailable')
            with patch.object(roster, 'configured_runner', return_value=runner), \
                 patch.object(roster, 'review_gate', return_value={'approved': True}):
                with self.assertRaisesRegex(RuntimeError, 'authentication unavailable'):
                    roster.main(['--config', config, 'smoke', '--repeat', 'repeat2',
                                 '--condition', 'P2', '--manifest-sha256', '0' * 64,
                                 '--review-receipt', '/private/tmp/private-review.json',
                                 '--review-sha256', 'a' * 64])
            attestation = base / 'repeat2' / 'P2' / f'smoke.admission-{"a" * 64}.json'
            self.assertEqual(json.loads(attestation.read_text())['dispatch_status'], 'not_asserted')

    def test_missing_root_review_stops_before_dispatch(self):
        runner = Mock()
        runner.verify_manifest.return_value = {'configuration_id': roster.CONFIGS[0]}
        runner.filehash.side_effect = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            receipt = Path(folder) / 'absent-roster-review.json'
            with patch.object(roster, 'configured_runner', return_value=runner):
                with self.assertRaises(FileNotFoundError):
                    roster.main(['--config', roster.CONFIGS[0], 'smoke', '--repeat', 'repeat2',
                                 '--condition', 'P2', '--manifest-sha256', '0' * 64,
                                 '--review-receipt', str(receipt), '--review-sha256', '0' * 64])
        runner.run_phase.assert_not_called()


if __name__ == '__main__':
    unittest.main()
