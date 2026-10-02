import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SPEC = importlib.util.spec_from_file_location(
    'gemma26_v2_final_suffix', ROOT / 'scripts/gemma26_v2_final_suffix.py')
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


class FinalSuffixTests(unittest.TestCase):
    def test_real_sealed_predecessor_and_frozen_fourteen_requests(self):
        gate = successor.prior_gate()
        requests = successor.selected_requests()
        self.assertEqual(gate['last_sent_id'], 'DEV-046')
        self.assertEqual(gate['never_sent_ids'],
                         [f'DEV-{i:03d}' for i in range(47, 61)])
        self.assertEqual([r['record_id'] for r in requests], list(successor.IDS))
        self.assertEqual(len(requests), 14)
        self.assertEqual(successor.CAP - successor.RESERVE * len(requests),
                         successor.Decimal('0.02360192'))
        self.assertGreaterEqual(successor.CAP - successor.RESERVE * 14, 0)

    def test_predecessor_terminal_hash_drift_fails_closed(self):
        with patch.object(successor.fifth, 'verify'), \
             patch.object(successor, 'TERMINAL_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'terminal differs'):
                successor.prior_gate()

    def test_budget_manifest_requires_exact_new_child_and_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            child = base / ('budget-' + successor.PARTITION_ID + '.jsonl')
            entry = {'id': successor.PARTITION_ID, 'cap_usd': '0.30',
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
                entry['cap_usd'] = '0.31'
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

    def test_global_authority_hold_is_atomic_unique_and_head_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'authority.jsonl'
            ledger.write_bytes(successor.AUTHORITY_SNAPSHOT.read_bytes())
            head = hashlib.sha256(ledger.read_bytes()).hexdigest()
            successor.hold_new_authority(ledger, head, 'a' * 64)
            events = [json.loads(line) for line in ledger.read_bytes().splitlines()]
            self.assertEqual(events[-1], {'event': 'hold',
                'id': successor.AUTHORITY_HOLD_ID, 'usd': '0.30',
                'source_sha256': 'a' * 64})
            with self.assertRaisesRegex(ValueError, 'head changed'):
                successor.hold_new_authority(ledger, head, 'a' * 64)
            after = hashlib.sha256(ledger.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                successor.hold_new_authority(ledger, after, 'a' * 64)
            self.assertEqual(len(ledger.read_bytes().splitlines()), len(events))

    def test_global_authority_cap_blocks_without_append(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'authority.jsonl'
            ledger.write_bytes(successor.AUTHORITY_SNAPSHOT.read_bytes())
            with ledger.open('a') as out:
                out.write(json.dumps({'event': 'hold', 'id': 'other-authorized-stage',
                    'usd': '8.00', 'source_sha256': 'b' * 64}) + '\n')
            before = ledger.read_bytes()
            with self.assertRaisesRegex(ValueError, 'exhausted'):
                successor.hold_new_authority(ledger,
                    hashlib.sha256(before).hexdigest(), 'a' * 64)
            self.assertEqual(ledger.read_bytes(), before)

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

    def test_child_without_full_next_reserve_blocks_before_key_or_send(self):
        class Ledger:
            cap = successor.CAP
            master_cap = successor.Decimal('12.38')
            closed = False

            def state(self):
                return None, {}, False

            def accounted(self):
                return successor.CAP - successor.RESERVE / 2

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            stage = base / 'fresh3/P2'
            stage.mkdir(parents=True)
            budget = base / 'budget.json'
            budget.write_text('{}')
            review = stage / 'suffix.root-review.json'
            review.write_text(json.dumps({'approved': True}))
            manifest = {'prior': {'route_fields': {}}}
            with patch.object(successor, 'BASE', base), \
                 patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=(manifest, 'sha')), \
                 patch.object(successor, 'expected_review', return_value={'approved': True}), \
                 patch.object(successor, 'budget_entry'), \
                 patch.object(successor.study, 'verify', return_value={}), \
                 patch.object(successor, 'checked_route', return_value=({}, {})), \
                 patch.object(successor.partitions, 'open_partition', return_value=Ledger()), \
                 patch.object(successor.paid, 'load_key') as key, \
                 patch.object(successor.original, 'fetch_captured') as send:
                with self.assertRaisesRegex(ValueError, 'child unavailable'):
                    successor.run(review, budget)
                key.assert_not_called()
                send.assert_not_called()

    def test_first_429_stops_before_dev048_and_retains_unknown(self):
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
            review_value = {'approved': True,
                            'global_authority_head_sha256': 'a' * 64}
            with patch.object(successor, 'BASE', base), \
                 patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=(manifest, 'manifest-sha')), \
                 patch.object(successor, 'budget_entry'), \
                 patch.object(successor, 'expected_review', return_value=review_value), \
                 patch.object(successor, 'prior_gate', return_value={'gate': True}), \
                 patch.object(successor, 'digest', return_value='gate'), \
                 patch.object(successor.study, 'verify', return_value={}), \
                 patch.object(successor, 'checked_route', return_value=({}, {'context_length': 262144})), \
                 patch.object(successor.partitions, 'open_partition', return_value=ledger), \
                 patch.object(successor.paid, 'load_key', return_value='unused-fake'), \
                 patch.object(successor, 'hold_new_authority') as global_hold, \
                 patch.object(successor.original, 'fetch_captured',
                              side_effect=successor.original.CapturedHTTPError(429, '{}', {})):
                review.write_text(json.dumps(review_value))
                self.assertFalse(successor.run(review, budget))
            attempts = [json.loads(line) for line in
                        (stage / 'suffix.attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['id'] for row in attempts], ['DEV-047'])
            self.assertEqual(attempts[0]['status'], 'service_error')
            self.assertTrue(attempts[0]['cost_unknown'])
            self.assertEqual(ledger.reserved, [(successor.RESERVE, 'DEV-047')])
            self.assertEqual(ledger.settled, [('attempt-1', None)])
            global_hold.assert_called_once()
            self.assertTrue(ledger.was_closed)


if __name__ == '__main__':
    unittest.main()
