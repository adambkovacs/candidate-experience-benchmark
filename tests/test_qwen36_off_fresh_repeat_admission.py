import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen36_off_fresh_repeat_admission as admission


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
        self.assertEqual(plan['budget']['historical_combined_proxy_usd'], '0.0827355')
        self.assertEqual(plan['budget']['per_call_reserve_usd'], '0.0299008')
        self.assertEqual(plan['budget']['proposed_child_cap_usd'], '0.30')
        self.assertEqual(plan['budget']['ledger']['admission_capacity_now'],
                         not bool(plan['budget']['ledger']['active_partitions'] or
                                  plan['budget']['ledger']['pending_attempts'] or
                                  plan['budget']['ledger']['blocked'] or
                                  plan['budget']['ledger']['closed']) and
                         float(plan['budget']['ledger']['headroom_usd']) >= float(admission.CAP))
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

    def test_historical_route_and_request_binding_fail_closed(self):
        history, controls, endpoint, model = admission.source_state()
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            hosted = Path(tmp) / 'hosted.json'
            contents = json.loads(admission.HOSTED.read_text())
            target = next(x for x in contents['configurations'] if x['id'] == admission.CONFIG)
            target['controls']['adapter_controls']['provider_tag'] = 'other/fp8'
            hosted.write_text(json.dumps(contents))
            with patch.object(admission, 'HOSTED', hosted):
                with self.assertRaisesRegex(ValueError, 'Historical route controls changed'):
                    admission.source_state()
            p0 = Path(tmp) / 'p0.jsonl'
            lines = admission.P0.read_text().splitlines()
            first = json.loads(lines[0]); first['request_sha256'] = '0' * 64
            lines[0] = json.dumps(first)
            p0.write_text('\n'.join(lines) + '\n')
            with patch.object(admission, 'P0', p0):
                with self.assertRaisesRegex(ValueError, 'Reconstruction differs'):
                    admission.plan_data()
        self.assertEqual(endpoint['tag'], admission.PROVIDER)
        self.assertEqual(controls['provider']['only'], [admission.PROVIDER])

    def test_later_review_feedback_and_p2_suffix_request_cannot_drift(self):
        original = admission.read_rows(admission.INPUTS)
        changed = [dict(row) for row in original]
        changed[41]['feedback'] += ' changed after historical run'
        with patch.object(admission, 'read_rows', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'P0/DEV-042'):
                admission.plan_data()
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            suffix = Path(tmp) / 'suffix.jsonl'
            rows = [json.loads(line) for line in admission.P2_SUFFIX.read_text().splitlines()]
            rows[4]['request_sha256'] = '0' * 64
            suffix.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with patch.object(admission, 'P2_SUFFIX', suffix):
                with self.assertRaisesRegex(ValueError, 'P2/DEV-058'):
                    admission.plan_data()

    def test_duplicate_or_reordered_historical_suffix_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            suffix = Path(tmp) / 'suffix.jsonl'
            rows = [json.loads(line) for line in admission.P2_SUFFIX.read_text().splitlines()]
            rows[4], rows[5] = rows[5], rows[4]
            suffix.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with patch.object(admission, 'P2_SUFFIX', suffix):
                with self.assertRaisesRegex(ValueError, 'P2 suffix changed|membership or order'):
                    admission.plan_data()


if __name__ == '__main__':
    unittest.main()
