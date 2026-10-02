"""Offline checks for the versioned Sonnet 5.5 continuation lane."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import claude_sonnet55_matched3_v2 as lane


class Sonnet55ContinuationTest(unittest.TestCase):
    def test_exact_builtin_tuple_gate(self):
        valid = {
            'init_plugins': [{'name': name, 'path': path, 'source': source}
                             for name, path, source in sorted(lane.BUILTIN_PLUGINS)],
            'init_tools': ['StructuredOutput'], 'init_mcp_servers': [],
            'init_skills': [], 'init_model': lane.MODEL,
            'requested_model': lane.MODEL, 'assistant_models': [lane.MODEL],
            'returned_models': [lane.MODEL], 'init_api_key_source': 'none',
            'overage_observed': False,
            'raw_events': [{'type': 'assistant', 'message': {'content': [
                {'type': 'tool_use', 'name': 'StructuredOutput'}]}}],
        }
        self.assertTrue(lane.isolation_ok_v2(valid))
        self.assertFalse(lane.isolation_ok_v2({**valid, 'init_plugins':
            valid['init_plugins'] + [{'name': 'unknown', 'path': 'builtin',
                                     'source': 'unknown@builtin'}]}))
        self.assertFalse(lane.isolation_ok_v2({**valid, 'init_plugins':
            valid['init_plugins'][:2]}))
        self.assertFalse(lane.isolation_ok_v2({**valid, 'init_plugins':
            [{**valid['init_plugins'][0], 'source': 'user@custom'},
             *valid['init_plugins'][1:]]}))
        self.assertFalse(lane.isolation_ok_v2({**valid, 'init_tools':
            ['StructuredOutput', 'Bash']}))

    def test_offline_sidecar_preserves_original_and_blocks_replay(self):
        lane.configure('low')
        original = lane.ORIGINAL_BASE / 'low/pass1'
        original_files = [original / 'manifest.json', ROOT / 'scripts/claude_sonnet55_matched3.py',
                          *(original / 'P0' / name for name in (
                              'smoke.claim.json', 'smoke.attempts.jsonl',
                              'smoke.records.jsonl', 'smoke.journal.jsonl',
                              'smoke.batch-000.raw.jsonl', 'smoke.root-review.json'))]
        before = {str(path): lane.sha(path) for path in original_files}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(lane, 'BASE', Path(temporary)):
                lane.prepare()
                lane.offline_admit()
                saved = lane.verify_offline_admission()
                self.assertEqual(saved['original_status'], 'service_error')
                self.assertEqual(saved['reparsed_status'], 'ok')
                self.assertTrue(saved['v2_isolation_ok'])
                self.assertFalse(saved['inference_performed'])
                self.assertTrue(lane.completed('pass1', 'P0', 'smoke'))
                manifest = lane.verify_manifest('pass1', lane.sha(lane.BASE / 'pass1/manifest.json'))
                with patch.object(lane.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'no v2 replay'):
                        lane.run_phase(manifest, 'P0', 'smoke', str(lane.CLI),
                                       '/unused', '0' * 64, '/unused', '0' * 64)
                    run.assert_not_called()
                with self.assertRaises(FileExistsError):
                    lane.offline_admit()
        self.assertEqual(before, {str(path): lane.sha(path) for path in original_files})

    def test_development_review_must_bind_sidecar_hash(self):
        lane.configure('low')
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(lane, 'BASE', Path(temporary)):
                lane.prepare()
                lane.offline_admit()
                manifest = lane.verify_manifest('pass1', lane.sha(lane.BASE / 'pass1/manifest.json'))
                preflight_hash = 'p' * 64
                review_path = lane.BASE / 'pass1/P0/development.root-review.json'

                def write_review(smoke_hash):
                    review = {
                        'schema': 'claude-sonnet55-fresh-matched3-v2-root-review-v1',
                        'approved': True, 'configuration_id': lane.CONFIG,
                        'pass': 'pass1',
                        'manifest_sha256': lane.sha(lane.BASE / 'pass1/manifest.json'),
                        'controller_sha256': lane.sha(ROOT / 'scripts/claude_sonnet55_matched3_v2.py'),
                        'mechanics_sha256': lane.sha(ROOT / 'scripts/claude_repeat_study.py'),
                        'roster_sha256': lane.sha(ROOT / 'scripts/claude_repeat_roster.py'),
                        'private_preflight_sha256': preflight_hash,
                        'cli_path': str(lane.CLI), 'cli_version': lane.RUNTIME,
                        'approved_phases': [{'condition': 'P0', 'phase': 'development'}],
                        'smoke_evidence_sha256': smoke_hash,
                        'review_note': 'Offline admission test'}
                    review_path.write_text(json.dumps(review) + '\n')
                    return lane.sha(review_path)

                bad_hash = write_review('0' * 64)
                with patch.object(lane, 'private_preflight'):
                    with self.assertRaisesRegex(ValueError, 'root review differs'):
                        lane._admit(manifest, 'P0', 'development', str(lane.CLI),
                                    review_path, bad_hash, '/unused', preflight_hash)
                    good_hash = write_review(lane.sha(lane.offline_admission_path()))
                    lane._admit(manifest, 'P0', 'development', str(lane.CLI),
                                review_path, good_hash, '/unused', preflight_hash)


if __name__ == '__main__':
    unittest.main()
