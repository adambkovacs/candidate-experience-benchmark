import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_fresh3_p0_p1_composite_successor_v1 as successor


class GemmaCompositeSuccessorTests(unittest.TestCase):
    BUDGET = ROOT / ('results/repeatability-v1/gemma26-on-fresh-matched3-v2/'
                     'third-interruption-continuation-v1/budget.json')
    PARTITION = 'gemma26-on-v2-third-interruption-v1'

    def test_manifest_binds_real_composite_and_frozen_controls(self):
        manifest = successor.verify()
        self.assertEqual(manifest['preserved_failed_ids'], ['DEV-005', 'DEV-006'])
        self.assertEqual(manifest['stages'], ['fresh3/P0/smoke',
            'fresh3/P0/development', 'fresh3/P1/smoke', 'fresh3/P1/development'])
        self.assertEqual(manifest['composite_projection_sha256'], successor.sha(successor.PROJECTION))
        self.assertEqual(manifest['frozen_runner_sha256'], successor.sha(
            ROOT / 'scripts/gemma26_on_fresh_repeat_execution_v2.py'))

    def test_p0_smoke_order_accepted_and_p1_waits_for_p0(self):
        manifest = successor.verify()
        plan = successor.study.verify('fresh3', manifest['frozen_plan_sha256']['fresh3'])
        successor.require_order(plan, 'P0', 'smoke')
        with self.assertRaises((OSError, ValueError)):
            successor.require_order(plan, 'P0', 'development')
        with self.assertRaises((OSError, ValueError)):
            successor.require_order(plan, 'P1', 'smoke')
        with self.assertRaisesRegex(ValueError, 'only fresh3 P0/P1'):
            successor.require_order(plan, 'P2', 'smoke')

    def test_composite_failure_change_blocks_admission(self):
        real = successor.composite.build
        def changed(root):
            value = real(root)
            value['fresh3P2']['failedIds'] = ['DEV-005']
            return value
        with patch.object(successor.composite, 'build', changed):
            with self.assertRaisesRegex(ValueError, 'P2 composite'):
                successor.verify()

    def test_unapproved_receipt_blocks_before_live_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'receipt.json'
            path.write_text('{}')
            with patch.object(successor.frozen, 'live_controls', side_effect=AssertionError('live called')):
                with self.assertRaises(ValueError):
                    successor.run('P0', 'smoke', path)

    def test_receipt_shape_passes_frozen_review_without_allocating(self):
        receipt = successor.expected_review('fresh3', 'P0', 'smoke', self.BUDGET,
                                             self.PARTITION)
        receipt['reviewer'] = 'offline-test'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'receipt.json'
            path.write_text(json.dumps(receipt))
            self.assertEqual(successor.check_review(path, 'fresh3', 'P0', 'smoke'), receipt)
            receipt['successor_controller_sha256'] = '0' * 64
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, 'Successor stage receipt differs'):
                successor.check_review(path, 'fresh3', 'P0', 'smoke')

    def test_authority_hold_is_single_and_stale_head_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'authority.jsonl'
            first = {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                     'cap_usd': '10.00', 'decision_key': successor.AUTHORITY_DECISION_KEY,
                     'approval_sha256': successor.AUTHORITY_APPROVAL_SHA}
            path.write_text(json.dumps(first) + '\n')
            with patch.object(successor, 'AUTHORITY', path):
                head = hashlib.sha256(path.read_bytes()).hexdigest()
                source = successor.global_hold_source(self.BUDGET, self.PARTITION)
                successor.hold_authority(head, self.BUDGET, self.PARTITION, source)
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1]['usd'], '0.40')
                with self.assertRaisesRegex(ValueError, 'head changed'):
                    successor.hold_authority(head, self.BUDGET, self.PARTITION, source)
                successor.hold_authority(hashlib.sha256(path.read_bytes()).hexdigest(),
                                         self.BUDGET, self.PARTITION, source)
                self.assertEqual(len(path.read_text().splitlines()), 2)

    def test_two_reviewed_children_cannot_share_one_global_hold(self):
        with tempfile.TemporaryDirectory(dir=successor.BASE) as temp:
            fixture = Path(temp)
            second_budget = fixture / 'budget.json'
            budget = json.loads(self.BUDGET.read_text())
            budget['partitions'][0]['id'] = 'second-reviewed-child'
            budget['partitions'][0]['child_ledger'] = str(fixture / 'second-child.jsonl')
            second_budget.write_text(json.dumps(budget))
            authority = fixture / 'authority.jsonl'
            authority.write_text(json.dumps({
                'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                'cap_usd': '10.00', 'decision_key': successor.AUTHORITY_DECISION_KEY,
                'approval_sha256': successor.AUTHORITY_APPROVAL_SHA}) + '\n')
            with patch.object(successor, 'AUTHORITY', authority):
                first = successor.expected_review('fresh3', 'P0', 'smoke',
                                                  self.BUDGET, self.PARTITION)
                second = successor.expected_review('fresh3', 'P1', 'smoke',
                                                   second_budget, 'second-reviewed-child')
                first['reviewer'] = second['reviewer'] = 'offline-test'
                first_path, second_path = fixture / 'first-review.json', fixture / 'second-review.json'
                first_path.write_text(json.dumps(first))
                second_path.write_text(json.dumps(second))
                self.assertEqual(successor.check_review(first_path, 'fresh3', 'P0', 'smoke'), first)
                self.assertEqual(successor.check_review(second_path, 'fresh3', 'P1', 'smoke'), second)
                self.assertNotEqual(first['global_hold_source_sha256'],
                                    second['global_hold_source_sha256'])
                successor.hold_authority(first['global_authority_head_sha256'],
                                         self.BUDGET, self.PARTITION,
                                         first['global_hold_source_sha256'])
                with self.assertRaisesRegex(ValueError, 'Global Gemma hold differs'):
                    successor.hold_authority(hashlib.sha256(authority.read_bytes()).hexdigest(),
                                             second_budget, 'second-reviewed-child',
                                             second['global_hold_source_sha256'])
                self.assertEqual(len(authority.read_text().splitlines()), 2)

    def test_frozen_order_function_restored(self):
        original = successor.frozen.require_order
        with successor.successor_order_gate():
            self.assertIs(successor.frozen.require_order, successor.require_order)
        self.assertIs(successor.frozen.require_order, original)


if __name__ == '__main__':
    unittest.main()
