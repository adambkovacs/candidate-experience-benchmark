"""Offline admission checks for the amended Gemini high repeat bridge."""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini31_high_authority_v2 as bridge


class Gemini31HighAuthorityTests(unittest.TestCase):
    CONFIG = 'gemini31-pro-preview-high-p0-openrouter-v3'

    def test_plans_reconstruct_all_six_label_free_phases(self):
        for repeat, order in bridge.runner.ORDERS.items():
            plan = bridge.runner.validate_plan(bridge.runner.plan_path(self.CONFIG, repeat))
            self.assertEqual(plan['condition_order'], list(order))
            self.assertEqual(plan['model'], 'google/gemini-3.1-pro-preview')
            self.assertEqual(plan['effort'], 'high')
            self.assertFalse(plan['reference_labels_read'])
            for condition in order:
                requests = plan['conditions'][condition]['requests']
                self.assertEqual(len(requests), 7)
                self.assertEqual(requests[0]['record_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
                self.assertEqual([rid for request in requests[1:] for rid in request['record_ids']],
                                 [f'DEV-{index:03}' for index in range(1, 61)])
                self.assertTrue(all(request['payload_sha256'] == bridge.runner.digest(
                    bridge.runner.v3.canon(request['payload']))
                    for request in requests))

    def test_repeat_three_accepts_only_bound_repeat_two_authority_hold(self):
        plan = bridge.runner.validate_plan(bridge.runner.plan_path(self.CONFIG, 'repeat3'))
        repeat_two = bridge.runner.plan_path(self.CONFIG, 'repeat2')
        source_sha = bridge.runner.digest(repeat_two.read_bytes())
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            budget = Path(folder) / 'budget.json'
            budget.write_text('{}\n')
            receipt = Path(folder) / 'review.json'
            receipt.write_text(json.dumps({'authority_ledger': str(bridge.AUTHORITY)}))
            hold = {'event': 'hold', 'version': 3, 'id': plan['partition_id'],
                    'funding_pool': 'openrouter_additional', 'source_sha256': source_sha,
                    'usd': '2.00', 'budget_manifest_path': str(budget),
                    'budget_manifest_sha256': bridge.runner.digest(budget.read_bytes()),
                    'partition_id': plan['partition_id'], 'master_path': str(bridge.runner.MASTER)}
            with patch.object(bridge, '_original_review_gate', return_value=budget), \
                    patch.object(bridge.authority, 'read_authority', return_value=SimpleNamespace(amendment_complete=True)), \
                    patch.object(bridge.runner, 'lines', return_value=[hold]):
                self.assertEqual(bridge.review_gate(plan, 'smoke', 'P2', receipt, 'repeat3hash'), budget)
                hold['source_sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'authority hold differs'):
                    bridge.review_gate(plan, 'smoke', 'P2', receipt, 'repeat3hash')

    def test_insufficient_first_reservation_prevents_phase_claim(self):
        path = bridge.runner.plan_path(self.CONFIG, 'repeat2')
        plan_sha = bridge.runner.digest(path.read_bytes())
        child = SimpleNamespace(cap=Decimal('2.00'), accounted=lambda: Decimal('1.90'),
                                state=lambda: (None, set(), False), close=lambda: None)
        with patch.object(bridge, 'review_gate', return_value=ROOT / 'unused-budget.json'), \
                patch.object(bridge.partitions, 'open_partition', return_value=child), \
                patch.object(bridge, '_original_run') as dispatch:
            with self.assertRaisesRegex(ValueError, 'no phase claim'):
                bridge.run(path, plan_sha, ROOT / 'unused-review.json', 'P1', 'smoke')
            dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
