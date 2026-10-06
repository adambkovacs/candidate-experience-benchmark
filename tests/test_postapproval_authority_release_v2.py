"""Controller tests mutate only temporary authority and receipt files."""
from decimal import Decimal
import hashlib
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
import postapproval_authority_release_v2 as controller
import openrouter_native_variants_v2 as old_writer


class FirstReleaseControllerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve()
        self.ledger = self.folder / 'authority.jsonl'
        self.proposal_path = self.folder / 'proposal.json'
        self.review_path = self.folder / 'root-review.json'
        self.receipt_path = self.folder / 'release-receipt.json'
        source = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
        self.production_head = hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copyfile(source, self.ledger)
        proposal = json.loads((ROOT / 'results/route-audits/postapproval-authority-v2-20261006/proposal.json').read_text())
        proposal['authority_file'] = str(self.ledger)
        self.proposal = proposal
        self.save_proposal()
        self.approve()

    def save_proposal(self):
        self.proposal_path.write_text(json.dumps(self.proposal, indent=2) + '\n')

    def approve(self):
        review = controller.review_template(self.proposal_path, self.receipt_path)
        review.update(approved=True, reviewer='root')
        self.review_path.write_text(json.dumps(review, indent=2) + '\n')

    def test_template_requires_explicit_review_and_verify_is_read_only(self):
        template = controller.review_template(self.proposal_path, self.receipt_path)
        self.assertIs(template['approved'], False)
        self.assertEqual(template['reviewer'], '')
        initial = self.ledger.read_bytes()
        self.review_path.write_text(json.dumps(template) + '\n')
        with self.assertRaises(ValueError):
            controller.verify(self.proposal_path, self.review_path, self.receipt_path)
        self.approve()
        result = controller.verify(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(result['status'], 'ready_to_append')
        self.assertFalse(self.receipt_path.exists())
        self.assertEqual(self.ledger.read_bytes(), initial)

    def test_commit_persists_receipt_and_retry_does_not_reappend(self):
        initial = self.ledger.read_bytes()
        result = controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(result['status'], 'release_receipted')
        self.assertEqual(self.ledger.read_bytes()[:len(initial)], initial)
        after = self.ledger.read_bytes()
        self.assertEqual(authority.read_authority(self.ledger).available_usd,
                         Decimal('0.125417936'))
        self.assertEqual(json.loads(self.receipt_path.read_text()),
                         self.proposal['proposed_release_receipt'])
        with self.assertRaises(ValueError):
            old_writer.hold_authority(self.ledger, 'legacy-next', Decimal('0.01'),
                                      'a'*64, hashlib.sha256(after).hexdigest(),
                                      stage_path=self.folder / 'legacy-stage')
        self.assertEqual(controller.commit(self.proposal_path, self.review_path,
                                           self.receipt_path)['status'], 'release_receipted')
        self.assertEqual(self.ledger.read_bytes(), after)
        self.assertEqual(hashlib.sha256((ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl').read_bytes()).hexdigest(),
                         self.production_head)

    def test_crash_after_append_recovers_receipt_even_after_new_hold(self):
        with patch.object(controller, '_persist_receipt', side_effect=RuntimeError('simulated crash')):
            with self.assertRaisesRegex(RuntimeError, 'simulated crash'):
                controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertFalse(self.receipt_path.exists())
        after_release = authority.read_authority(self.ledger)
        self.assertEqual(after_release.release_count, 1)
        authority.hold_authority(self.ledger, 'new-reviewed-hold', Decimal('0.01'),
                                 'a'*64, after_release.head_sha256,
                                 stage_path=self.folder/'new-stage')
        later = self.ledger.read_bytes()
        controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), later)
        self.assertEqual(json.loads(self.receipt_path.read_text()),
                         self.proposal['proposed_release_receipt'])

    def test_stale_authority_and_master_heads_fail_without_append(self):
        initial = self.ledger.read_bytes()
        self.ledger.write_bytes(initial +
            b'{"event":"hold","id":"other","usd":"0.001","source_sha256":"' +
            b'a'*64 + b'"}\n')
        changed = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), changed)
        self.ledger.write_bytes(initial)
        self.proposal['master_head_sha256_at_proposal'] = '0'*64
        self.save_proposal()
        self.approve()
        with self.assertRaises(ValueError):
            controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), initial)

    def test_changed_source_claim_or_receipt_collision_fails_before_append(self):
        initial = self.ledger.read_bytes()
        self.proposal['proposed_release_receipt']['release_event']['child_sha256'] = 'f'*64
        self.save_proposal()
        self.approve()
        with self.assertRaises(ValueError):
            controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), initial)
        self.proposal['proposed_release_receipt']['release_event']['child_sha256'] = authority.file_sha(
            Path(self.proposal['proposed_release_receipt']['release_event']['child_ledger_path']))
        self.save_proposal()
        self.approve()
        self.receipt_path.write_text('{"wrong":true}\n')
        with self.assertRaises(ValueError):
            controller.commit(self.proposal_path, self.review_path, self.receipt_path)
        self.assertEqual(self.ledger.read_bytes(), initial)


if __name__ == '__main__':
    unittest.main()
