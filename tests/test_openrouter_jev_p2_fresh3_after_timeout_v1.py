"""Offline checks for the interrupted fresh2 -> distinct fresh3 transition."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_jev_p2_fresh3_after_timeout_v1 as successor
import openrouter_jev_authority_v2 as bridge
import postapproval_authority_v2 as authority


class Fresh3AfterTimeoutTest(unittest.TestCase):
    def test_actual_terminal_chain_has_all_60_attempted_and_two_retained_unknowns(self):
        proof = successor.interrupted_predecessor()
        self.assertEqual(proof['status'], 'interrupted_all_60_attempted')
        self.assertEqual(proof['valid_count'], 57)
        self.assertEqual(proof['intrinsic_invalid_ids'], ['DEV-040'])
        self.assertEqual(proof['unknown_charge_ids'], ['DEV-018', 'DEV-060'])
        self.assertEqual(proof['never_sent_ids'], [])
        self.assertEqual(proof['known_actual_cost_usd'], '0.006622434')
        self.assertEqual(proof['retained_unknown_upper_bound_usd'], '0.002688000')
        self.assertEqual(proof['tail_attempts_sha256'],
                         '744188d50c8d2bcd948dd81e5948b186a601f5f1095762be85d0f69f3fbd6119')
        self.assertEqual(proof['tail_child_sha256'],
                         '9f437e1bd14f3ef05ac761d4389a5dc13c4d0942a592565d185278b17cc4e705')

    def test_proposal_and_private_core_replace_only_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proposal.json'
            successor.prepare(path)
            proposal = successor.verify(path)
            core = successor._core(proposal_path=path)
            manifest = core.verify(successor.CONFIG, successor.BASE)
            prior = core.predecessor(successor.CONFIG, successor.STAGE, manifest,
                                     base=successor.BASE)
            self.assertEqual(prior, proposal['predecessor_proof'])
            self.assertIs(core.smoke_v2.hold_authority, authority.hold_authority)
            self.assertEqual(core.context_proof(successor.CONFIG, manifest,
                                                base=successor.BASE),
                             proposal['context_proof_sha256'])
            self.assertEqual(core.smoke_inspection(successor.CONFIG, manifest,
                                                   base=successor.BASE),
                             proposal['smoke_inspection_sha256'])
            budget = Path(directory) / 'offline-budget.json'
            budget.write_text('{}\n')
            receipt = core.expected_receipt(
                successor.CONFIG, successor.STAGE, manifest,
                budget,
                proposal['context_proof_sha256'],
                proposal['smoke_inspection_sha256'], prior, 'a' * 64,
                base=successor.BASE)
            self.assertEqual(receipt['fresh3_after_timeout_wrapper_sha256'],
                             proposal['wrapper_sha256'])
            self.assertEqual(receipt['fresh3_after_timeout_proposal_sha256'],
                             successor._sha(path))
            self.assertEqual(receipt['fresh3_after_timeout_predecessor_sha256'],
                             proposal['predecessor_proof_sha256'])
            self.assertEqual(receipt['predecessor_proof'], prior)
            with self.assertRaises(ValueError):
                core.predecessor(successor.CONFIG, 'fresh2', manifest,
                                 base=successor.BASE)

    def test_changed_saved_proposal_or_tail_attempt_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proposal.json'
            successor.prepare(path)
            saved = path.read_bytes()
            edited = json.loads(saved)
            edited['predecessor_proof']['valid_count'] = 58
            path.write_text(json.dumps(edited) + '\n')
            with self.assertRaises(ValueError):
                successor.verify(path)
            path.write_bytes(saved)
            attempts_path = bridge.TAIL_BASE / successor.CONFIG / 'tail' / 'attempts.jsonl'
            real_rows = successor._rows

            def changed_rows(path_arg):
                rows = real_rows(path_arg)
                if Path(path_arg) == attempts_path:
                    rows = copy.deepcopy(rows)
                    rows[-1]['error_type'] = 'OtherError'
                return rows

            with patch.object(successor, '_rows', side_effect=changed_rows):
                with self.assertRaisesRegex(ValueError, 'Tail terminal or unknown evidence differs'):
                    successor.interrupted_predecessor()

    def test_stale_head_stops_before_private_execution_or_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            ledger = temp / 'authority.jsonl'
            shutil.copyfile(bridge.AUTHORITY, ledger)
            receipt = temp / 'review.json'
            receipt.write_text(json.dumps({'global_authority_head_sha256': '0'*64}) + '\n')
            called = []

            class FakeCore:
                def execute(self, *args, **kwargs):
                    called.append(True)

            with patch.object(successor, '_core', return_value=FakeCore()):
                with self.assertRaisesRegex(ValueError, 'Stale v2 authority head'):
                    successor.execute(receipt, temp / 'missing-budget.json',
                                      base=temp, proposal_path=temp / 'missing-proposal.json',
                                      authority_path=ledger)
            self.assertEqual(called, [])


if __name__ == '__main__':
    unittest.main()
