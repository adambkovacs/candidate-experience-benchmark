"""Offline Jev P1 release tests. Production ledgers are only read."""
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import postapproval_authority_v2 as authority
import postapproval_jev_release_proposals_v2 as releases
import postapproval_authority_release_v2 as first_controller


class JevP1ReleaseProposalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve()
        self.ledger = self.folder / 'authority.jsonl'
        shutil.copyfile(releases.AUTHORITY, self.ledger)
        self.before = self.ledger.read_bytes()
        self.output = self.folder / 'proposal'
        paths = releases.prepare(self.output, authority_path=self.ledger)
        self.proposal_path = Path(paths['proposal_path'])
        self.unsupported_path = Path(paths['unsupported_path'])
        self.receipt_path = self.folder / 'p1-fresh1-release-receipt.json'
        self.review_path = self.folder / 'p1-fresh1.root-review.json'
        review = releases.template(self.proposal_path, self.receipt_path)
        review.update(approved=True, reviewer='root')
        self.review_path.write_text(json.dumps(review) + '\n')

    def test_prepare_binds_current_head_and_records_fresh2_as_unsupported(self):
        proposal = json.loads(self.proposal_path.read_text())
        unsupported = json.loads(self.unsupported_path.read_text())
        self.assertEqual(proposal['authority_head_sha256'], authority.sha(self.before))
        receipt = proposal['proposed_release_receipt']
        self.assertEqual(receipt['release_event']['usd'], '0.074235000')
        self.assertEqual(receipt['release_event']['hold_source_sha256'], releases.SOURCE)
        self.assertEqual(unsupported['status'], 'unsupported_no_release_event')
        self.assertEqual(unsupported['invalid_ids'], ['DEV-056'])
        self.assertEqual(unsupported['known_actual_usd'], '0.006405000')
        self.assertEqual(unsupported['unknown_upper_bound_usd'], '0')
        self.assertEqual(self.ledger.read_bytes(), self.before)
        self.assertEqual(releases.verify(self.proposal_path, self.review_path,
                                         self.receipt_path)['status'], 'ready_to_append')

    def test_review_required_and_temp_commit_is_idempotent(self):
        template = releases.template(self.proposal_path, self.receipt_path)
        self.assertIs(template['approved'], False)
        self.review_path.write_text(json.dumps(template) + '\n')
        with self.assertRaises(ValueError):
            releases.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), self.before)
        template.update(approved=True, reviewer='root')
        self.review_path.write_text(json.dumps(template) + '\n')
        self.assertEqual(releases.commit(self.proposal_path, self.review_path,
                                         self.receipt_path)['status'], 'release_receipted')
        after = self.ledger.read_bytes()
        self.assertEqual(after[:len(self.before)], self.before)
        self.assertEqual(authority.read_authority(self.ledger).release_count, 2)
        self.assertEqual(releases.commit(self.proposal_path, self.review_path,
                                         self.receipt_path)['status'], 'release_receipted')
        self.assertEqual(self.ledger.read_bytes(), after)

    def test_receipt_recovers_after_append_even_with_later_hold(self):
        with patch.object(first_controller, '_persist_receipt', side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError, 'crash'):
                releases.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertFalse(self.receipt_path.exists())
        state = authority.read_authority(self.ledger)
        authority.hold_authority(self.ledger, 'later-stage', Decimal('0.001'), 'a'*64,
                                 state.head_sha256, stage_path=self.folder/'later-stage')
        after = self.ledger.read_bytes()
        releases.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), after)
        self.assertEqual(json.loads(self.receipt_path.read_text()),
                         json.loads(self.proposal_path.read_text())['proposed_release_receipt'])

    def test_stale_head_and_existing_output_do_not_release(self):
        authority.hold_authority(self.ledger, 'unrelated-stage', Decimal('0.001'), 'a'*64,
                                 authority.sha(self.before), stage_path=self.folder/'unrelated-stage')
        changed = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            releases.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), changed)
        self.ledger.write_bytes(self.before)
        self.receipt_path.write_text('occupied\n')
        with self.assertRaises(ValueError):
            releases.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_fresh2_invalid_stage_cannot_pass_reviewed_verifier(self):
        p = releases._paths('fresh2')
        with self.assertRaisesRegex(ValueError, 'terminal completion'):
            authority.release_authority(
                self.ledger, 'unsupported-fresh2', p['pid'], '0.074235000',
                authority.sha(self.before), stage_path=p['stage'],
                receipt_path=p['receipt'], manifest_path=p['manifest'],
                budget_manifest_path=p['budget'], child_ledger_path=p['child'],
                master_ledger_path=releases.MASTER)
        self.assertEqual(self.ledger.read_bytes(), self.before)


if __name__ == '__main__':
    unittest.main()
