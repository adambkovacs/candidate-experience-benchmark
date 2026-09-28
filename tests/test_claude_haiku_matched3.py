"""Offline checks for the separate fresh matched-three Haiku lane."""

import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import claude_haiku_matched3 as haiku


class HaikuMatchedThreeTest(unittest.TestCase):
    def _prepared(self, directory):
        context = patch.object(haiku, 'BASE', directory / 'fresh-haiku')
        context.start()
        self.addCleanup(context.stop)
        haiku.prepare()
        return haiku.verify_manifest('pass1', haiku.sha(haiku.BASE / 'pass1/manifest.json'))

    def _admission(self, directory, manifest):
        preflight = directory / 'private-subscription-preflight.json'
        preflight.write_text(json.dumps({
            'operator': 'root', 'cli_version': haiku.RUNTIME,
            'auth_method': 'claude.ai', 'api_provider': 'firstParty',
            'usage_credits_off': True, 'extra_usage_disabled': True,
            'session_used_percent': 1, 'weekly_used_percent': 1,
            'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat()}) + '\n')
        preflight_hash = haiku.sha(preflight)
        review = directory / 'haiku-root-review.json'
        review.write_text(json.dumps({
            'schema': 'claude-haiku-fresh-matched3-root-review-v1', 'approved': True,
            'configuration_id': haiku.CONFIG, 'pass': 'pass1',
            'manifest_sha256': haiku.sha(haiku.BASE / 'pass1/manifest.json'),
            'controller_sha256': haiku.sha(ROOT / 'scripts/claude_haiku_matched3.py'),
            'mechanics_sha256': haiku.sha(ROOT / 'scripts/claude_repeat_study.py'),
            'roster_sha256': haiku.sha(ROOT / 'scripts/claude_repeat_roster.py'),
            'private_preflight_sha256': preflight_hash, 'cli_path': str(haiku.CLI),
            'cli_version': haiku.RUNTIME,
            'approved_phases': [{'condition': manifest['condition_order'][0], 'phase': 'smoke'}],
            'review_note': 'Offline test admission'}) + '\n')
        return preflight, preflight_hash, review, haiku.sha(review)

    def test_three_orders_and_exact_input_only_requests(self):
        self.assertEqual(haiku.ORDERS, {'pass1': ['P0', 'P1', 'P2'],
                                        'pass2': ['P1', 'P2', 'P0'],
                                        'pass3': ['P2', 'P0', 'P1']})
        for pass_name in haiku.ORDERS:
            with self.subTest(pass_name=pass_name):
                plan = haiku.plan_data(pass_name)
                self.assertEqual(plan['model'], 'claude-haiku-4-5-20251001')
                self.assertEqual(plan['effort'], 'not_applicable')
                self.assertFalse(plan['reference_labels_read'])
                self.assertEqual(plan['timeout_seconds'], 600)
                for binding in plan['source_bindings']:
                    self.assertEqual(haiku.source(binding['path']), binding)
                for condition in ('P0', 'P1', 'P2'):
                    development = plan['conditions'][condition]['development']
                    self.assertEqual(len(development), 6)
                    self.assertEqual([rid for b in development for rid in b['record_ids']],
                                     [f'DEV-{i:03d}' for i in range(1, 61)])
                    for item in [plan['conditions'][condition]['smoke'], *development]:
                        self.assertEqual(item['request']['input'], json.loads(item['input_text']))
                        self.assertTrue(all(set(r) == {'id', 'feedback'} for r in
                                            item['request']['input']['records']))
                        self.assertNotIn('prediction', json.dumps(item))

    def test_historical_failure_is_bound_but_not_replayed(self):
        plan = haiku.plan_data('pass1')
        original = json.loads((ROOT / haiku.P1_ATTEMPTS).read_text().splitlines()[1])
        self.assertIn('ENOTFOUND', original['raw_response']['result'])
        new_ids = [rid for b in plan['conditions']['P1']['development']
                   for rid in b['record_ids']]
        self.assertEqual(new_ids, [f'DEV-{i:03d}' for i in range(1, 61)])
        self.assertNotIn('raw_response', json.dumps(plan['conditions']['P1']['development']))
        self.assertIn(haiku.P1_ATTEMPTS,
                      [x['path'] for x in plan['source_bindings']])
        self.assertIn(haiku.RECONCILIATION,
                      [x['path'] for x in plan['source_bindings']])

    def test_manifest_reconstruction_order_and_no_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = self._prepared(Path(temp))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                haiku.verify_manifest('pass1', '0' * 64)
            with self.assertRaisesRegex(ValueError, 'Previous condition incomplete'):
                haiku.run_phase(plan, 'P1', 'smoke', str(haiku.CLI),
                                '/unused', '0' * 64, '/unused', '0' * 64)
            _, claim, _, _, journal = haiku.phase_paths('pass1', 'P0', 'smoke')
            claim.parent.mkdir(parents=True)
            claim.write_text('{}\n')
            journal.write_text('{"event":"dispatch_intent","batch_index":0}\n')
            with self.assertRaises(FileExistsError):
                haiku.run_phase(plan, 'P0', 'smoke', str(haiku.CLI),
                                '/unused', '0' * 64, '/unused', '0' * 64)
            self.assertFalse(haiku.completed('pass1', 'P0', 'smoke'))

    def test_private_preflight_and_exact_root_review_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            preflight, preflight_hash, review, review_hash = self._admission(folder, plan)
            haiku.root_review(review, review_hash, plan, preflight_hash)
            with self.assertRaisesRegex(ValueError, 'public repository'):
                haiku.roster.private_preflight(ROOT / 'AGENTS.md', '0' * 64,
                                               haiku.roster.mechanics())
            altered = json.loads(review.read_text())
            altered['weekly_used_percent'] = 1
            review.write_text(json.dumps(altered) + '\n')
            with patch.object(haiku.subprocess, 'run', side_effect=AssertionError('dispatched')):
                with self.assertRaisesRegex(ValueError, 'admission hashes only'):
                    haiku.run_phase(plan, 'P0', 'smoke', str(haiku.CLI), review,
                                    haiku.sha(review), preflight, preflight_hash)
            self.assertFalse(haiku.phase_paths('pass1', 'P0', 'smoke')[1].exists())

    def test_raw_saved_before_parse_and_failure_stops_without_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            preflight, preflight_hash, review, review_hash = self._admission(folder, plan)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                if command[1:4] == ['--safe-mode', 'auth', 'status']:
                    return SimpleNamespace(stdout=json.dumps({
                        'loggedIn': True, 'authMethod': 'claude.ai',
                        'apiProvider': 'firstParty'}), returncode=0)
                if command[1:] == ['--version']:
                    return SimpleNamespace(stdout=haiku.RUNTIME + '\n', returncode=0)
                return SimpleNamespace(stdout='{malformed', stderr='transport failed', returncode=1)
            with patch.object(haiku.subprocess, 'run', side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, 'Stopped on first non-ok'):
                    haiku.run_phase(plan, 'P0', 'smoke', str(haiku.CLI), review,
                                    review_hash, preflight, preflight_hash)
            phase = haiku.phase_paths('pass1', 'P0', 'smoke')
            self.assertEqual(json.loads((phase[0] / 'smoke.batch-000.raw.jsonl').read_text())
                             ['stdout'], '{malformed')
            self.assertEqual(json.loads(phase[2].read_text())['status'], 'service_error')
            self.assertEqual(json.loads(phase[4].read_text().splitlines()[-1])['event'],
                             'phase_stopped')
            self.assertEqual(len(calls), 3)
            with patch.object(haiku.subprocess, 'run', side_effect=AssertionError('replayed')):
                with self.assertRaises(FileExistsError):
                    haiku.run_phase(plan, 'P0', 'smoke', str(haiku.CLI), review,
                                    review_hash, preflight, preflight_hash)

    def test_api_key_auth_is_rejected_before_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            preflight, preflight_hash, review, review_hash = self._admission(folder, plan)
            calls = []
            def fake_run(command, **kwargs):
                calls.append(command)
                return SimpleNamespace(stdout=json.dumps({
                    'loggedIn': True, 'authMethod': 'apiKey',
                    'apiProvider': 'firstParty'}), returncode=0)
            with patch.object(haiku.subprocess, 'run', side_effect=fake_run):
                with self.assertRaisesRegex(ValueError, 'Claude.ai subscription login required'):
                    haiku.run_phase(plan, 'P0', 'smoke', str(haiku.CLI), review,
                                    review_hash, preflight, preflight_hash)
            self.assertEqual(len(calls), 1)
            self.assertFalse(haiku.phase_paths('pass1', 'P0', 'smoke')[1].exists())

    def test_report_retains_nonstarted_and_stopped_states(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            plan = self._prepared(folder)
            self.assertEqual(haiku.report()['passes']['pass1']['P0']['smoke']['state'],
                             'not_started')
            preflight, preflight_hash, review, review_hash = self._admission(folder, plan)
            def fake_run(command, **kwargs):
                if command[1:4] == ['--safe-mode', 'auth', 'status']:
                    return SimpleNamespace(stdout=json.dumps({
                        'loggedIn': True, 'authMethod': 'claude.ai',
                        'apiProvider': 'firstParty'}), returncode=0)
                if command[1:] == ['--version']:
                    return SimpleNamespace(stdout=haiku.RUNTIME + '\n', returncode=0)
                return SimpleNamespace(stdout='{malformed', stderr='', returncode=1)
            with patch.object(haiku.subprocess, 'run', side_effect=fake_run):
                with self.assertRaises(RuntimeError):
                    haiku.run_phase(plan, 'P0', 'smoke', str(haiku.CLI), review,
                                    review_hash, preflight, preflight_hash)
            self.assertEqual(haiku.report()['passes']['pass1']['P0']['smoke']['state'],
                             'stopped_or_ambiguous')
            self.assertEqual(haiku.report()['passes']['pass1']['P0']['smoke']['counts']
                             ['service_error'], 3)
            self.assertEqual(haiku.report()['passes']['pass1']['P0']['development']['state'],
                             'not_started')


if __name__ == '__main__':
    unittest.main()
