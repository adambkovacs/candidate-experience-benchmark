"""Offline checks for the separate Claude subscription repeat roster."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import claude_repeat_roster as roster
import claude_repeat_study as completed_opus


class ClaudeRepeatRosterTest(unittest.TestCase):
    CONFIG = 'fable51-low-phase2-batch10-p0'

    def _prepared(self, folder):
        context = patch.object(roster, 'BASE_ROOT', folder / 'claude-roster-v1')
        context.start()
        self.addCleanup(context.stop)
        roster.prepare(self.CONFIG)
        plan = roster.verify_manifest(
            self.CONFIG, 'repeat2',
            roster.sha(roster.base(self.CONFIG) / 'repeat2/manifest.json'))
        return plan

    def _admission(self, folder, plan):
        private = folder / 'private-subscription-preflight.json'
        private.write_text(json.dumps({
            'operator': 'root', 'cli_version': roster.RUNTIME,
            'auth_method': 'claude.ai', 'api_provider': 'firstParty',
            'usage_credits_off': True, 'extra_usage_disabled': True,
            'session_used_percent': 1, 'weekly_used_percent': 1,
            'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat()}) + '\n')
        private_hash = roster.sha(private)
        review = folder / 'root-review.json'
        review.write_text(json.dumps({
            'schema': 'claude-repeat-roster-root-review-v1', 'approved': True,
            'configuration_id': self.CONFIG, 'repeat': 'repeat2',
            'manifest_sha256': roster.sha(roster.base(self.CONFIG) / 'repeat2/manifest.json'),
            'controller_sha256': roster.sha(ROOT / 'scripts/claude_repeat_roster.py'),
            'mechanics_sha256': roster.sha(ROOT / 'scripts/claude_repeat_study.py'),
            'private_preflight_sha256': private_hash,
            'cli_path': str(roster.CLI), 'cli_version': roster.RUNTIME,
            'approved_phases': [{'condition': plan['condition_order'][0], 'phase': 'smoke'}],
            'review_note': 'Explicit offline test authorization'}) + '\n')
        return private, private_hash, review, roster.sha(review)

    def test_exact_eligible_roster_and_frozen_request_reconstruction(self):
        self.assertEqual(len(roster.ROSTER), 15)
        self.assertNotIn('opus55-medium-batch10', roster.ROSTER)
        self.assertFalse(any('max' in effort or 'ultra' in effort
                             for _, effort in roster.ROSTER.values()))
        for config in roster.ROSTER:
            with self.subTest(config=config):
                two = roster.plan_data(config, 'repeat2')
                three = roster.plan_data(config, 'repeat3')
                self.assertEqual(set(two['historical_pass_order']), {'P0', 'P1', 'P2'})
                self.assertEqual(set(two['condition_order']), {'P0', 'P1', 'P2'})
                self.assertEqual(set(three['condition_order']), {'P0', 'P1', 'P2'})
                self.assertEqual({*two['historical_pass_order'], *two['condition_order'],
                                  *three['condition_order']}, {'P0', 'P1', 'P2'})
                self.assertEqual(two['runtime_required'], roster.RUNTIME)
                self.assertEqual(two['historical_runtime'], roster.HISTORICAL_RUNTIME)
                self.assertFalse(two['reference_labels_read'])
                for binding in two['source_bindings']:
                    self.assertEqual(roster.source(binding['path']), binding)
                for condition in ('P0', 'P1', 'P2'):
                    entries = two['conditions'][condition]['development']
                    self.assertEqual(len(entries), 6)
                    self.assertEqual([rid for batch in entries for rid in batch['record_ids']],
                                     [f'DEV-{i:03d}' for i in range(1, 61)])
                    for item in [two['conditions'][condition]['smoke'], *entries]:
                        self.assertEqual(item['request']['input'], json.loads(item['input_text']))
                        self.assertTrue(all(set(row) == {'id', 'feedback'} for row in
                                            item['request']['input']['records']))
                        self.assertNotIn('proposed_labels', json.dumps(item))

    def test_rotations_follow_each_historical_order(self):
        first = roster.plan_data('fable51-low-phase2-batch10-p0', 'repeat2')
        second = roster.plan_data('fable51-medium-phase2-batch10-p0', 'repeat2')
        self.assertEqual(first['historical_pass_order'], ['P0', 'P2', 'P1'])
        self.assertEqual(first['condition_order'], ['P2', 'P1', 'P0'])
        self.assertEqual(second['historical_pass_order'], ['P0', 'P1', 'P2'])
        self.assertEqual(second['condition_order'], ['P1', 'P2', 'P0'])

    def test_completed_lane_import_remains_isolated(self):
        isolated = roster.mechanics()
        self.assertIsNot(isolated, completed_opus)
        isolated.CONFIG = 'different'
        self.assertEqual(completed_opus.CONFIG, 'opus55-medium-batch10')

    def test_manifest_hash_and_preflight_privacy(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                roster.verify_manifest(self.CONFIG, 'repeat2', '0' * 64)
            private, private_hash, review, review_hash = self._admission(folder, plan)
            with self.assertRaisesRegex(ValueError, 'public repository'):
                roster.private_preflight(ROOT / 'AGENTS.md', '0' * 64, roster.mechanics())
            admitted = roster.private_preflight(private, private_hash, roster.mechanics())
            self.assertTrue(admitted['usage_credits_off'])
            roster.root_review(review, review_hash, plan, private_hash)
            saved = json.loads(review.read_text())
            saved['weekly_used_percent'] = 1
            review.write_text(json.dumps(saved) + '\n')
            with self.assertRaisesRegex(ValueError, 'admission hashes only'):
                roster.root_review(review, roster.sha(review), plan, private_hash)

    def test_order_and_no_replay_stop_before_preflight_or_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = self._prepared(Path(temp))
            order = plan['condition_order']
            with self.assertRaisesRegex(ValueError, 'Previous condition incomplete'):
                roster.run_phase(plan, order[1], 'smoke', str(roster.CLI),
                                 '/unused', '0' * 64, '/unused', '0' * 64)
            _, claim, _, _, journal = roster.phase_paths(self.CONFIG, 'repeat2', order[0], 'smoke')
            claim.parent.mkdir(parents=True)
            claim.write_text('{}\n')
            journal.write_text('{"event":"dispatch_intent","batch_index":0}\n')
            with self.assertRaises(FileExistsError):
                roster.run_phase(plan, order[0], 'smoke', str(roster.CLI),
                                 '/unused', '0' * 64, '/unused', '0' * 64)
            self.assertFalse(roster.completed(self.CONFIG, 'repeat2', order[0], 'smoke'))

    def test_api_auth_rejected_before_public_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            private, private_hash, review, review_hash = self._admission(folder, plan)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(stdout=json.dumps({
                    'loggedIn': True, 'authMethod': 'apiKey', 'apiProvider': 'firstParty'}),
                    returncode=0)
            with patch.object(roster.subprocess, 'run', side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, 'Claude.ai subscription login required'):
                    roster.run_phase(plan, plan['condition_order'][0], 'smoke', str(roster.CLI),
                                     review, review_hash, private, private_hash)
            self.assertEqual(len(calls), 1)
            self.assertFalse(roster.phase_paths(self.CONFIG, 'repeat2',
                                                plan['condition_order'][0], 'smoke')[1].exists())

    def test_raw_stdout_saved_before_parse_and_private_usage_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            private, private_hash, review, review_hash = self._admission(folder, plan)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                if command[1:4] == ['--safe-mode', 'auth', 'status']:
                    return SimpleNamespace(stdout=json.dumps({
                        'loggedIn': True, 'authMethod': 'claude.ai',
                        'apiProvider': 'firstParty'}), returncode=0)
                if command[1:] == ['--version']:
                    return SimpleNamespace(stdout=roster.RUNTIME + '\n', returncode=0)
                return SimpleNamespace(stdout='{invalid-json', stderr='upstream diagnostic',
                                       returncode=1)
            with patch.object(roster.subprocess, 'run', side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, 'Stopped on first non-ok'):
                    roster.run_phase(plan, plan['condition_order'][0], 'smoke', str(roster.CLI),
                                     review, review_hash, private, private_hash)
            phase = roster.phase_paths(self.CONFIG, 'repeat2', plan['condition_order'][0], 'smoke')
            raw = phase[0] / 'smoke.batch-000.raw.jsonl'
            self.assertEqual(json.loads(raw.read_text())['stdout'], '{invalid-json')
            self.assertEqual(json.loads(phase[2].read_text())['status'], 'service_error')
            public_claim = phase[1].read_text()
            self.assertIn(private_hash, public_claim)
            self.assertNotIn('session_used_percent', public_claim)
            self.assertNotIn('weekly_used_percent', public_claim)
            self.assertNotIn('usage_credits_off', public_claim)
            self.assertEqual(len(calls), 3)
            with patch.object(roster.subprocess, 'run', side_effect=AssertionError('replayed')):
                with self.assertRaises(FileExistsError):
                    roster.run_phase(plan, plan['condition_order'][0], 'smoke', str(roster.CLI),
                                     review, review_hash, private, private_hash)


if __name__ == '__main__':
    unittest.main()
