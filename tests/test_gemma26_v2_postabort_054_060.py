import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_v2_postabort_054_060 as successor


class PostabortSuffixTests(unittest.TestCase):
    def test_real_terminal_prefix_and_only_unsent_seven(self):
        gate = successor.prior_gate()
        requests = successor.selected_requests()
        self.assertEqual(gate['last_sent_id'], 'DEV-053')
        self.assertEqual(gate['never_sent_ids'], list(successor.IDS))
        self.assertEqual([r['record_id'] for r in requests], list(successor.IDS))
        self.assertEqual(successor.CAP - successor.Decimal('0.00244094') -
                         len(requests) * successor.RESERVE,
                         successor.Decimal('0.15936002'))
        manifest, digest = successor.verify()
        self.assertEqual(digest, successor.sha(successor.BASE / 'manifest.json'))
        self.assertEqual(manifest['postabort_audit_sha256'], successor.AUDIT_SHA)
        self.assertEqual(manifest['ids'], list(successor.IDS))

    def test_terminal_audit_drift_blocks(self):
        with patch.object(successor.final, 'verify'), \
             patch.object(successor, 'AUDIT_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'terminal audit differs'):
                successor.prior_gate()

    def test_original_child_prefix_may_grow_but_cannot_change(self):
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / 'child.jsonl'
            original = successor.CHILD.read_bytes()
            child.write_bytes(original + b'{"event":"successor-test"}\n')
            with patch.object(successor.final, 'verify'), \
                 patch.object(successor, 'CHILD', child):
                self.assertEqual(successor.prior_gate()['last_sent_id'], 'DEV-053')
                child.write_bytes(b'X' + original[1:])
                with self.assertRaisesRegex(ValueError, 'child budget prefix differs'):
                    successor.prior_gate()

    def test_existing_child_and_global_hold_are_read_only(self):
        before_child = successor.CHILD.read_bytes()
        before_global = successor.AUTHORITY.read_bytes()
        self.assertEqual(successor.budget_entry(successor.BUDGET)['id'],
                         successor.PARTITION_ID)
        successor.check_existing_authority(successor.AUTHORITY,
                                           hashlib.sha256(before_global).hexdigest())
        self.assertEqual(successor.CHILD.read_bytes(), before_child)
        self.assertEqual(successor.AUTHORITY.read_bytes(), before_global)
        with self.assertRaisesRegex(ValueError, 'head changed'):
            successor.check_existing_authority(successor.AUTHORITY, '0' * 64)

    def test_missing_existing_global_hold_blocks_without_append(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'authority.jsonl'
            events = [json.loads(x) for x in successor.AUTHORITY.read_text().splitlines()]
            events = [x for x in events if x.get('id') != successor.AUTHORITY_HOLD_ID]
            ledger.write_text(''.join(json.dumps(x) + '\n' for x in events))
            before = ledger.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Existing global hold missing'):
                successor.check_existing_authority(
                    ledger, hashlib.sha256(before).hexdigest())
            self.assertEqual(ledger.read_bytes(), before)

    def test_existing_claim_blocks_before_route_or_key(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            stage = base / 'fresh3/P2'
            stage.mkdir(parents=True)
            budget = successor.BUDGET
            review = stage / 'suffix.root-review.json'
            review.write_text(json.dumps({'approved': True}))
            (stage / 'suffix.claim.json').write_text('{}')
            with patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=({'prior': {'route_fields': {}}}, 'sha')), \
                 patch.object(successor, 'expected_review', return_value={'approved': True}), \
                 patch.object(successor, 'checked_route') as route, \
                 patch.object(successor.paid, 'load_key') as key:
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    successor.run(review, budget)
                route.assert_not_called()
                key.assert_not_called()

    def test_partial_or_pending_child_blocks_before_key_and_send(self):
        class Ledger:
            cap = successor.CAP
            master_cap = successor.Decimal('12.38')
            closed = False
            events = [None] * 15
            def state(self):
                return None, self.pending, False
            def accounted(self):
                return successor.Decimal('0.00244094')
            def close(self):
                pass
            pending = {'ambiguous-attempt': 'pending'}
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory) / 'fresh3/P2'
            stage.mkdir(parents=True)
            review = stage / 'suffix.root-review.json'
            review.write_text(json.dumps({'approved': True}))
            with patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=({'prior': {'route_fields': {}}}, 'sha')), \
                 patch.object(successor, 'expected_review', return_value={'approved': True}), \
                 patch.object(successor, 'budget_entry'), \
                 patch.object(successor.study, 'verify', return_value={}), \
                 patch.object(successor, 'checked_route', return_value=({}, {})), \
                 patch.object(successor.partitions, 'open_partition', return_value=Ledger()), \
                 patch.object(successor.paid, 'load_key') as key, \
                 patch.object(successor.original, 'fetch_captured') as send:
                with self.assertRaisesRegex(ValueError, 'seven-call reserve'):
                    successor.run(review, successor.BUDGET)
                key.assert_not_called()
                send.assert_not_called()
                Ledger.pending = {}
                Ledger.events = [None] * 16
                with self.assertRaisesRegex(ValueError, 'seven-call reserve'):
                    successor.run(review, successor.BUDGET)
                key.assert_not_called()
                send.assert_not_called()

    def test_first_429_stops_after_only_dev054_and_retains_unknown(self):
        class Ledger:
            cap = successor.CAP
            master_cap = successor.Decimal('12.38')
            closed = False
            events = [None] * 15
            def __init__(self):
                self.reserved = []
                self.settled = []
            def state(self):
                return None, {}, False
            def accounted(self):
                return successor.Decimal('0.00244094') + (
                    successor.RESERVE if self.settled else successor.Decimal(0))
            def reserve(self, amount, rid):
                self.reserved.append((amount, rid))
                return 'new-attempt-1'
            def settle(self, attempt, actual):
                self.settled.append((attempt, actual))
                return False
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory) / 'fresh3/P2'
            stage.mkdir(parents=True)
            review = stage / 'suffix.root-review.json'
            review_value = {'approved': True, 'global_authority_head_sha256': 'a' * 64}
            review.write_text(json.dumps(review_value))
            manifest = {'prior': {'route_fields': {}}, 'source_sha256': {},
                        'prior_gate_sha256': 'gate', 'requests': [
                            {'record_id': rid, 'request_sha256': rid, 'payload': {}}
                            for rid in successor.IDS]}
            ledger = Ledger()
            with patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=(manifest, 'manifest-sha')), \
                 patch.object(successor, 'budget_entry'), \
                 patch.object(successor, 'expected_review', return_value=review_value), \
                 patch.object(successor, 'prior_gate', return_value={'gate': True}), \
                 patch.object(successor, 'digest', return_value='gate'), \
                 patch.object(successor.study, 'verify', return_value={}), \
                 patch.object(successor, 'checked_route', return_value=({}, {'context_length': 262144})), \
                 patch.object(successor.partitions, 'open_partition', return_value=ledger), \
                 patch.object(successor.paid, 'load_key', return_value='fake'), \
                 patch.object(successor, 'check_existing_authority') as hold, \
                 patch.object(successor.original, 'fetch_captured',
                              side_effect=successor.original.CapturedHTTPError(429, '{}', {})):
                self.assertFalse(successor.run(review, successor.BUDGET))
            attempts = [json.loads(x) for x in
                        (stage / 'suffix.attempts.jsonl').read_text().splitlines()]
            self.assertEqual([x['id'] for x in attempts], ['DEV-054'])
            self.assertEqual(ledger.reserved, [(successor.RESERVE, 'DEV-054')])
            self.assertEqual(ledger.settled, [('new-attempt-1', None)])
            self.assertTrue(attempts[0]['cost_unknown'])
            hold.assert_called_once()

    def test_all_seven_sends_reserve_first_and_do_not_add_authority_hold(self):
        class Ledger:
            cap = successor.CAP
            master_cap = successor.Decimal('12.38')
            closed = False
            events = [None] * 15
            def __init__(self):
                self.reserved = []
                self.settled = []
            def state(self):
                return None, {}, False
            def accounted(self):
                return (successor.Decimal('0.00244094') +
                        successor.Decimal('0.0001') * len(self.settled))
            def reserve(self, amount, rid):
                self.reserved.append(rid)
                return 'attempt-' + rid
            def settle(self, attempt, actual):
                self.settled.append((attempt, actual))
                return True
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory) / 'fresh3/P2'
            stage.mkdir(parents=True)
            review = stage / 'suffix.root-review.json'
            review_value = {'approved': True, 'global_authority_head_sha256': 'a' * 64}
            review.write_text(json.dumps(review_value))
            manifest = {'prior': {'route_fields': {}}, 'source_sha256': {},
                        'prior_gate_sha256': 'gate', 'requests': [
                            {'record_id': rid, 'request_sha256': rid, 'payload': {}}
                            for rid in successor.IDS]}
            ledger = Ledger()
            def captured(payload, token, wire, rid, attempt, digest):
                self.assertEqual(ledger.reserved[-1], rid)
                successor.original.durable(wire, {'id': rid, 'attempt_id': attempt,
                    'http_status': 200})
                return {'usage': {'cost': '0.0001'}, 'choices': []}
            with patch.object(successor, 'STAGE', stage), \
                 patch.object(successor, 'verify', return_value=(manifest, 'manifest-sha')), \
                 patch.object(successor, 'budget_entry'), \
                 patch.object(successor, 'expected_review', return_value=review_value), \
                 patch.object(successor, 'prior_gate', return_value={'gate': True}), \
                 patch.object(successor, 'digest', return_value='gate'), \
                 patch.object(successor.study, 'verify', return_value={}), \
                 patch.object(successor, 'checked_route', return_value=({}, {'context_length': 262144})), \
                 patch.object(successor.partitions, 'open_partition', return_value=ledger), \
                 patch.object(successor.paid, 'load_key', return_value='fake'), \
                 patch.object(successor, 'check_existing_authority') as hold, \
                 patch.object(successor.original, 'fetch_captured', side_effect=captured), \
                 patch.object(successor.original, 'classify', return_value={'status': 'ok'}), \
                 patch.object(successor.original, 'continue_record', return_value=True), \
                 patch.object(successor, 'audit_response', return_value={'passed': True}):
                self.assertTrue(successor.run(review, successor.BUDGET))
            self.assertEqual(ledger.reserved, list(successor.IDS))
            self.assertEqual(len(ledger.settled), 7)
            hold.assert_called_once()
            journal = [json.loads(x) for x in
                       (stage / 'suffix.journal.jsonl').read_text().splitlines()]
            self.assertEqual(journal[-1]['event'], 'phase_completed')


if __name__ == '__main__':
    unittest.main()
