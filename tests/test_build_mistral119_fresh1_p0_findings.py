from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_mistral119_fresh1_p0_findings as findings


class MistralFresh1P0FindingsTests(unittest.TestCase):
    def test_reconciliation_uses_stage_local_ledger_in_archived_clone(self):
        partition_id = 'fixture-child-v1'
        child_name = f'suffix.budget-manifest-{partition_id}.jsonl'
        old_host_path = f'/unavailable/original/mac/results/{child_name}'
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory)
            stage = Path('results/archived-stage')
            folder = clone / stage
            folder.mkdir(parents=True)
            ledger_bytes = b'{"event":"partition_closed"}\n'
            (folder / child_name).write_bytes(ledger_bytes)
            (folder / 'suffix.budget-manifest.json').write_text(json.dumps({
                'partitions': [{'id': partition_id, 'child_ledger': old_host_path}]}))
            reconciliation = {
                'child_ledger': old_host_path,
                'child_sha256': hashlib.sha256(ledger_bytes).hexdigest(),
            }
            with patch.object(findings, 'ROOT', clone):
                local = findings.verify_reconciled_child(
                    stage, reconciliation, 'suffix.budget-manifest.json')
            self.assertEqual(local, folder / child_name)

    def test_projection_reconciles_scores_and_keeps_unknowns(self):
        result = findings.build()
        self.assertEqual(result['outcomes'], {
            'valid': 55, 'failed': 5, 'neverSent': 0,
            'failedIds': ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058', 'DEV-060']})
        self.assertEqual(result['scoring']['allFourMatches'], 40)
        self.assertEqual(result['scoring']['allFourDenominator'], 60)
        self.assertEqual(result['scoring']['allFourMatchRate'], 0.666667)
        self.assertEqual(result['scoring']['allFourAmongValid'], 0.727273)
        self.assertIn('human review of all 60 labels on 2026-10-02',
                      result['scoring']['referenceStatus'])
        self.assertEqual(result['scoring']['fieldMatches'], {
            'sentiment': 46, 'follow_up_needed': 52,
            'serious_concern_reported': 48, 'testimonial_potential': 51})
        self.assertEqual(result['usage']['promptTokens'], 78702)
        self.assertEqual(result['usage']['completionTokens'], 2164)
        self.assertEqual(result['usage']['observedKnownCostUsd'], '0.005084835')
        self.assertEqual(result['usage']['unknownChargeUpperBoundUsd'], '0.20889600')
        self.assertFalse(result['lineage']['cleanRepeatabilityClaim'])
        self.assertFalse(result['lineage']['referenceLabelsSent'])

    def test_public_projection_has_no_private_quota_or_account_fields(self):
        result = findings.build()
        forbidden = ('quota', 'account', 'authority', 'master_ledger', 'child_ledger')
        encoded = str(result).lower()
        self.assertFalse(any(term in encoded for term in forbidden))


if __name__ == '__main__':
    unittest.main()
