import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import affordable_hosted_repeat_admission as admission


class AdmissionTests(unittest.TestCase):
    def test_fresh_three_pass_plan_preserves_frozen_requests_and_budget(self):
        before = hashlib.sha256(admission.MASTER.read_bytes()).hexdigest()
        plan = admission.plan_data()
        self.assertEqual(before, hashlib.sha256(admission.MASTER.read_bytes()).hexdigest())
        self.assertFalse(plan['historical_first_pass_eligible'])
        self.assertEqual(plan['request_count'], 567)
        self.assertEqual(len(plan['phases']), 9)
        self.assertEqual({p['repeat'] for p in plan['phases']}, set(admission.ORDERS))
        for repeat, order in admission.ORDERS.items():
            self.assertEqual([p['condition'] for p in plan['phases'] if p['repeat'] == repeat], list(order))
        for condition in ('P0', 'P1', 'P2'):
            rows = plan['requests_by_condition'][condition]
            self.assertEqual([r['id'] for r in rows], [f'DEV-{n:03d}' for n in range(1, 61)])
            self.assertEqual(len({r['request_sha256'] for r in rows}), 60)
        self.assertEqual(plan['budget']['historical_combined_proxy_usd'], '0.028534290')
        self.assertEqual(plan['budget']['per_call_reserve_usd'], '0.1069056')
        self.assertEqual(plan['budget']['proposed_child_cap_usd'], '0.46')
        self.assertTrue(plan['budget']['ledger']['admission_capacity_now'])
        self.assertTrue(plan['budget']['conditional_completion'])

    def test_pending_master_attempt_blocks_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / 'budget.jsonl'
            ledger.write_text('\n'.join(json.dumps(x) for x in [
                {'event': 'budget', 'cap_usd': '10'},
                {'event': 'reserve', 'attempt_id': 'unresolved', 'record_id': 'DEV-001', 'usd': '0.01'},
            ]) + '\n')
            with patch.object(admission, 'MASTER', ledger):
                snapshot = admission.ledger_snapshot()
        self.assertEqual(snapshot['pending_attempts'], 1)
        self.assertFalse(snapshot['admission_capacity_now'])

    def test_changed_smoke_evidence_fails_closed(self):
        with patch.object(admission, 'HISTORICAL_SMOKE_TRIPLE', admission.HISTORICAL_SMOKE_TRIPLE + 1):
            with self.assertRaisesRegex(ValueError, 'smoke proxy changed'):
                admission.plan_data()


if __name__ == '__main__':
    unittest.main()
