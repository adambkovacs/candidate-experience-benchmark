import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location(
    'gemma26_v2_fourth_suffix', ROOT / 'scripts/gemma26_v2_fourth_suffix.py')
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


class FourthSuffixTests(unittest.TestCase):
    def test_real_sealed_predecessor_and_frozen_ten_requests(self):
        gate = successor.prior_gate()
        requests = successor.selected_requests()
        self.assertEqual(gate['failed_id'], 'DEV-006')
        self.assertEqual(gate['never_sent_ids'],
                         [f'DEV-{i:03d}' for i in range(7, 61)])
        self.assertEqual([r['record_id'] for r in requests], list(successor.IDS))
        self.assertEqual(len(requests), 10)
        self.assertEqual(successor.CAP - successor.RESERVE * len(requests),
                         successor.CAP - successor.RESERVE * 10)
        self.assertGreaterEqual(successor.CAP - successor.RESERVE * 10, 0)

    def test_predecessor_terminal_hash_drift_fails_closed(self):
        with patch.object(successor.third, 'audit_prior'), \
             patch.object(successor.third, 'verify_manifest'), \
             patch.object(successor, 'TERMINAL_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'terminal differs'):
                successor.prior_gate()

    def test_budget_manifest_requires_exact_new_child_and_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            child = base / ('budget-' + successor.PARTITION_ID + '.jsonl')
            entry = {'id': successor.PARTITION_ID, 'cap_usd': '0.20',
                     'model': successor.study.MODEL,
                     'provider': successor.study.PROVIDER,
                     'reasoning': successor.study.EFFORT,
                     'child_ledger': str(child)}
            budget = {'version': 'paid-partitions-v1',
                      'master_ledger': str(successor.third.MASTER.resolve()),
                      'partitions': [entry]}
            path = base / 'budget.json'
            path.write_text(json.dumps(budget))
            with patch.object(successor, 'BASE', base):
                self.assertEqual(successor.budget_entry(path), entry)
                entry['cap_usd'] = '0.21'
                path.write_text(json.dumps(budget))
                with self.assertRaisesRegex(ValueError, 'route or cap'):
                    successor.budget_entry(path)

    def test_route_drift_rejected_without_inference(self):
        expected = {key: None for key in successor.ROUTE_FIELDS}
        endpoint = dict(expected, tag='other/fp8')
        with patch.object(successor.original, 'live_controls',
                          return_value=({}, endpoint, successor.RESERVE)):
            with self.assertRaisesRegex(ValueError, 'endpoint or reserve'):
                successor.checked_route({}, expected)

    def test_existing_claim_blocks_before_route_or_key(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            stage = base / 'fresh3/P2'
            stage.mkdir(parents=True)
            budget = base / 'budget.json'
            budget.write_text('{}')
            review = stage / 'suffix.root-review.json'
            review.write_text(json.dumps({'approved': True}))
            (stage / 'suffix.claim.json').write_text('{}')
            with patch.object(successor, 'BASE', base), \
                 patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=({'prior': {}}, 'sha')), \
                 patch.object(successor, 'expected_review', return_value={'approved': True}), \
                 patch.object(successor, 'checked_route') as route, \
                 patch.object(successor.paid, 'load_key') as key:
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    successor.run(review, budget)
                route.assert_not_called()
                key.assert_not_called()

    def test_first_429_stops_before_dev008_and_retains_unknown(self):
        class Ledger:
            cap = successor.CAP
            master_cap = successor.Decimal('12.38')
            closed = False

            def __init__(self):
                self.reserved = []
                self.settled = []
                self.was_closed = False

            def state(self):
                return None, {}, False

            def accounted(self):
                return successor.RESERVE if self.settled else successor.Decimal(0)

            def reserve(self, amount, rid):
                self.reserved.append((amount, rid))
                return 'attempt-1'

            def settle(self, attempt, actual):
                self.settled.append((attempt, actual))
                return False

            def close(self):
                self.was_closed = True

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            stage = base / 'fresh3/P2'
            stage.mkdir(parents=True)
            budget = base / 'budget.json'
            budget.write_text('{}')
            review = stage / 'suffix.root-review.json'
            manifest = {'prior': {'route_fields': {}}, 'prior_gate_sha256': 'gate',
                        'source_sha256': {}, 'requests': [
                            {'record_id': rid, 'request_sha256': rid, 'payload': {}}
                            for rid in successor.IDS]}
            ledger = Ledger()
            with patch.object(successor, 'BASE', base), \
                 patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=(manifest, 'manifest-sha')), \
                 patch.object(successor, 'budget_entry'), \
                 patch.object(successor, 'expected_review', return_value={'approved': True}), \
                 patch.object(successor, 'prior_gate', return_value={'gate': True}), \
                 patch.object(successor, 'digest', return_value='gate'), \
                 patch.object(successor.study, 'verify', return_value={}), \
                 patch.object(successor, 'checked_route', return_value=({}, {'context_length': 262144})), \
                 patch.object(successor.partitions, 'open_partition', return_value=ledger), \
                 patch.object(successor.paid, 'load_key', return_value='unused-fake'), \
                 patch.object(successor.original, 'fetch_captured',
                              side_effect=successor.original.CapturedHTTPError(429, '{}', {})):
                review.write_text(json.dumps({'approved': True}))
                self.assertFalse(successor.run(review, budget))
            attempts = [json.loads(line) for line in
                        (stage / 'suffix.attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['id'] for row in attempts], ['DEV-007'])
            self.assertEqual(attempts[0]['status'], 'service_error')
            self.assertTrue(attempts[0]['cost_unknown'])
            self.assertEqual(ledger.reserved, [(successor.RESERVE, 'DEV-007')])
            self.assertEqual(ledger.settled, [('attempt-1', None)])
            self.assertTrue(ledger.was_closed)


if __name__ == '__main__':
    unittest.main()
