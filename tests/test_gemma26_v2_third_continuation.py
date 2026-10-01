"""Offline boundaries for the versioned DEV-005 Gemma26 successor."""
import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_v2_third_continuation as successor


class ThirdContinuationTests(unittest.TestCase):
    def test_read_only_audit_pins_three_failures_and_exact_never_sent_suffix(self):
        prior = successor.audit_prior()
        self.assertEqual(prior['never_sent_ids'],
                         [f'DEV-{n:03d}' for n in range(6, 61)])
        self.assertEqual(prior['historical_unknown_upper_bounds'], {
            'DEV-007': '0.01974272', 'DEV-002': '0.01974272',
            'DEV-005': '0.01974272'})
        self.assertEqual(prior['sealed_child']['sha256'], successor.SEALED_CHILD_SHA)
        self.assertEqual(prior['sealed_reconciliation']['sha256'],
                         successor.RECONCILIATION_SHA)
        self.assertFalse((ROOT / successor.OUTPUT).exists())

    def test_selected_requests_never_replay_prior_five_or_read_labels(self):
        self.assertEqual(successor.STAGES, [
            ('fresh3', 'P2', 'suffix'), ('fresh3', 'P0', 'smoke'),
            ('fresh3', 'P0', 'development'), ('fresh3', 'P1', 'smoke'),
            ('fresh3', 'P1', 'development')])
        suffix = successor.selected_requests('fresh3', 'P2', 'suffix')
        self.assertEqual([r['record_id'] for r in suffix],
                         [f'DEV-{n:03d}' for n in range(6, 61)])
        frozen = successor.study.verify('fresh3', successor.first.PLAN_SHAS['fresh3'])[
            'conditions']['P2']['development']
        self.assertEqual(suffix, frozen[5:])
        self.assertNotIn('proposed_labels', json.dumps(suffix))
        for repeat, condition, stage in successor.STAGES[1:]:
            chosen = successor.selected_requests(repeat, condition, stage)
            expected = successor.IDS[:3] if stage == 'smoke' else successor.IDS
            self.assertEqual([r['record_id'] for r in chosen], expected)
        with self.assertRaisesRegex(ValueError, 'outside'):
            successor.selected_requests('fresh3', 'P2', 'development')

    def test_stopped_source_and_seal_hash_drift_fail_closed(self):
        with patch.dict(successor.STOP_SHA, {'attempts': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'stopped evidence changed'):
                successor.audit_prior()
        with patch.object(successor, 'SEALED_CHILD_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'child seal changed'):
                successor.audit_prior()
        with patch.dict(successor.CLOSED_SHA,
                        {'fresh2_P0_suffix_attempts': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'closed stage source differs'):
                successor.audit_prior()

    def test_duplicate_stage_claim_rejected_before_route_or_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            claim = Path(temp) / 'claim.json'
            claim.write_text('{}\n')
            with patch.object(successor, 'verify_manifest', return_value={}), \
                 patch.object(successor, 'require_order'), \
                 patch.object(successor, 'verify_review'), \
                 patch.object(successor, 'stage_paths', return_value={'claim': claim}), \
                 patch.object(successor.original, 'live_controls',
                              side_effect=AssertionError('route must not be reached')):
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    successor.execute('0' * 64, 'fresh3', 'P2', 'suffix', claim)

    def test_review_receipt_is_bound_to_new_manifest_and_exact_stage(self):
        manifest = {'source_bindings': {
            'controller': {'sha256': 'a' * 64},
            'old_reconciliation': {'sha256': successor.RECONCILIATION_SHA},
            'new_budget_manifest': {'sha256': 'b' * 64}},
            'child_cap_usd': '0.4'}
        value = successor.expected_review(manifest, 'c' * 64,
                                          'fresh3', 'P2', 'suffix')
        self.assertEqual(value['ids'], successor.SUFFIX)
        self.assertEqual(value['stage'], 'fresh3/P2/suffix')
        self.assertEqual(value['old_reconciliation_sha256'],
                         successor.RECONCILIATION_SHA)
        self.assertEqual(value['manifest_sha256'], 'c' * 64)

    def test_fake_timeout_stops_after_one_new_id_and_preserves_unknown_cost(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'fresh3/P2'
            paths = {kind: folder / ('suffix.' + extension) for kind, extension in {
                'claim': 'claim.json', 'journal': 'journal.jsonl',
                'attempts': 'attempts.jsonl', 'responses': 'responses.jsonl',
                'wire': 'wire.jsonl'}.items()}
            review = root / 'receipt.json'
            review.write_text('{}\n')
            selected = successor.selected_requests('fresh3', 'P2', 'suffix')[:2]
            ledger = Mock()
            ledger.cap = Decimal('0.4')
            ledger.master_cap = Decimal('12.38')
            ledger.closed = False
            ledger.state.return_value = ({}, {}, False)
            ledger.accounted.return_value = Decimal(0)
            ledger.reserve.return_value = 'fake-attempt-006'
            ledger.settle.return_value = False
            manifest = {'child_cap_usd': '0.4',
                        'source_bindings': {'new_budget_manifest': {'path': 'unused',
                                                                    'sha256': '0' * 64}}}
            manifest['source_bindings'].update({key: {'path': 'unused', 'sha256': '0' * 64}
                                                for key in successor.RUNTIME_SOURCE_KEYS})
            with patch.object(successor, 'verify_manifest', return_value=manifest), \
                 patch.object(successor, 'require_order'), \
                 patch.object(successor, 'verify_review'), \
                 patch.object(successor, 'stage_paths', return_value=paths), \
                 patch.object(successor, 'selected_requests', return_value=selected), \
                 patch.object(successor, 'read_bound', return_value=root / 'budget.json'), \
                 patch.object(successor, 'budget_entry', return_value={}), \
                 patch.object(successor.partitions, 'open_partition', return_value=ledger), \
                 patch.object(successor.paid, 'load_key', return_value='fake-key'), \
                 patch.object(successor.original, 'live_controls',
                              return_value=({}, {'context_length': 8192}, successor.RESERVE)) as live, \
                 patch.object(successor.original, 'fetch_captured',
                              side_effect=TimeoutError('fake timeout')) as fetch, \
                 patch.object(successor.original, 'continue_record', return_value=False):
                completed = successor.execute('0' * 64, 'fresh3', 'P2',
                                              'suffix', review)
            self.assertFalse(completed)
            self.assertEqual(live.call_count, 2)
            fetch.assert_called_once()
            ledger.reserve.assert_called_once_with(successor.RESERVE, 'DEV-006')
            ledger.settle.assert_called_once_with('fake-attempt-006', None)
            journal = successor.rows(paths['journal'])
            self.assertEqual(journal[-1]['event'], 'phase_stopped')
            self.assertEqual(journal[-1]['id'], 'DEV-006')
            self.assertFalse(any(x.get('id') == 'DEV-007' for x in journal))
            attempts = successor.rows(paths['attempts'])
            self.assertEqual(len(attempts), 1)
            self.assertEqual(attempts[0]['id'], 'DEV-006')
            self.assertEqual(attempts[0]['error_type'], 'TimeoutError')
            self.assertIs(attempts[0]['cost_unknown'], True)
            self.assertIsNone(attempts[0]['observed_cost_usd'])


if __name__ == '__main__':
    unittest.main()
