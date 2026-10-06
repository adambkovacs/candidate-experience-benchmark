import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_jev_p2_fresh2_suffix_v1 as suffix


class JevP2Fresh2SuffixV1Test(unittest.TestCase):
    def test_exact_terminal_prefix_unknown_and_unsent_boundary(self):
        proof = suffix.inspect_parent()
        self.assertEqual(proof['valid_prefix_ids'], suffix.full.IDS[:17])
        self.assertEqual(proof['unknown_attempted_id'], 'DEV-018')
        self.assertEqual(proof['never_sent_ids'], suffix.IDS)
        self.assertEqual(proof['known_actual_cost_usd'], '0.001940694')
        self.assertEqual(proof['unknown_charge_upper_bound_usd'], '0.001344000')
        self.assertEqual(proof['parent_source_sha256']['terminal-public.json'],
                         suffix.PINNED['terminal-public.json'])

    def test_proposal_binds_original_requests_and_shortfall(self):
        manifest = suffix.build_manifest()
        original = suffix.frozen.build_plan()[suffix.CONFIG]
        self.assertEqual(manifest['ids'], [x['id'] for x in original['requests'][18:]])
        self.assertEqual(manifest['request_sha256'],
                         [x['payload_sha256'] for x in original['requests'][18:]])
        self.assertEqual(len(manifest['request_bytes']), 42)
        self.assertEqual(manifest['whole_suffix_full_context_bound_usd'], '0.056448000')
        self.assertEqual(manifest['authority_shortfall_usd_at_snapshot'], '0.004819024')
        self.assertFalse(manifest['dispatch_enabled'])
        self.assertFalse(manifest['parent_scope']['clean_repeat_credit'])
        self.assertTrue(manifest['admission']['no_DEV018_replay'])

    def test_prepared_proposal_is_immutable_and_verifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            suffix.prepare(base)
            self.assertEqual(suffix.verify(base)['status'], 'blocked_shared_authority')
            path = base / 'proposal.json'
            changed = json.loads(path.read_text())
            changed['ids'][0] = 'DEV-018'
            path.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'proposal differs'):
                suffix.verify(base)

    def test_parent_attempt_tamper_blocks_before_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / 'fresh2'
            parent.mkdir()
            for name in suffix.PINNED:
                if name != 'child_ledger':
                    shutil.copyfile(suffix.PARENT / name, parent / name)
            attempts = parent / 'attempts.jsonl'
            attempts.write_bytes(attempts.read_bytes() + b'{}\n')
            with self.assertRaisesRegex(ValueError, 'Immutable parent source changed'):
                suffix.build_manifest(parent_dir=parent)

    def test_no_dispatch_surface_and_no_reference_payload(self):
        self.assertFalse(hasattr(suffix, 'execute'))
        self.assertFalse(hasattr(suffix, 'run'))
        original = suffix.frozen.build_plan()[suffix.CONFIG]
        for row in original['requests'][18:]:
            self.assertEqual(set(row['payload']['state']), {'feedback', 'policy'})
            self.assertNotIn('reference', row['payload'])
            self.assertNotIn('id', row['payload'])


if __name__ == '__main__':
    unittest.main()
