"""Offline gates for the second, separately admitted Gemma 26B continuation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_v2_second_continuation as second


class SecondContinuationTests(unittest.TestCase):
    def test_exact_stopped_boundary_and_sealed_unknown(self):
        prefix = second.verify_stopped_prefix()
        self.assertEqual(prefix['failed_id'], 'DEV-002')
        self.assertEqual(prefix['never_sent_ids'], [f'DEV-{i:03d}' for i in range(3, 61)])
        self.assertEqual(prefix['known_prefix_usd'], '0.00028017')
        seal = second.verify_old_seal(
            second.PREVIOUS / 'terminal-reconciliation-after-dev002.json', prefix)
        self.assertEqual(seal['known_actual_usd'], '0.06819211')
        self.assertEqual(seal['unknown_upper_bound_usd'], '0.01974272')
        self.assertEqual(seal['old_child_ledger']['sha256'], second.FIRST_SEALED_CHILD_SHA)
        self.assertEqual(seal['old_reconciliation']['sha256'], second.FIRST_RECONCILIATION_SHA)

    def test_stale_stopped_evidence_and_seal_are_rejected(self):
        with patch.dict(second.FIRST_STOP_SHA, {'attempts': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'stopped evidence changed'):
                second.verify_stopped_prefix()
        prefix = second.verify_stopped_prefix()
        with patch.object(second, 'FIRST_SEALED_CHILD_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'sealed evidence changed'):
                second.verify_old_seal(
                    second.PREVIOUS / 'terminal-reconciliation-after-dev002.json', prefix)

    def test_suffix_and_later_requests_equal_frozen_plans(self):
        self.assertEqual(len(second.STAGES), 7)
        self.assertEqual(second.STAGES[0], ('fresh2', 'P0', 'suffix'))
        self.assertEqual(second.STAGES[1:], [
            ('fresh3', 'P2', 'smoke'), ('fresh3', 'P2', 'development'),
            ('fresh3', 'P0', 'smoke'), ('fresh3', 'P0', 'development'),
            ('fresh3', 'P1', 'smoke'), ('fresh3', 'P1', 'development')])
        for repeat, condition, stage in second.STAGES:
            with self.subTest(repeat=repeat, condition=condition, stage=stage):
                selected = second.selected_requests(repeat, condition, stage)
                original = second.study.verify(repeat, second.first.PLAN_SHAS[repeat])[
                    'conditions'][condition]['development' if stage == 'suffix' else stage]
                self.assertEqual(selected, original[2:] if stage == 'suffix' else original)
                self.assertEqual(len(selected), 58 if stage == 'suffix' else 3 if stage == 'smoke' else 60)
        with self.assertRaisesRegex(ValueError, 'outside second continuation'):
            second.selected_requests('fresh2', 'P0', 'development')

    def test_new_budget_requires_separate_child_and_seal_prevents_dispatch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            output = Path(temp) / 'second'
            output.mkdir()
            child = output / ('budget-' + second.PARTITION_ID + '.jsonl')
            child.write_text('{"event":"budget","cap_usd":"0.30"}\n')
            budget = output / 'budget.json'
            manifest = {'version': 'paid-partitions-v1', 'master_ledger': str(Path(temp) / 'master.jsonl'),
                        'partitions': [{'id': second.PARTITION_ID, 'cap_usd': '0.30',
                                        'child_ledger': str(child), 'model': second.study.MODEL,
                                        'provider': second.study.PROVIDER,
                                        'reasoning': second.study.EFFORT}]}
            budget.write_text(json.dumps(manifest) + '\n')
            master = Path(temp) / 'master.jsonl'
            allocation = {'event': 'budget_partition', 'partition_id': second.PARTITION_ID,
                          'allocated_usd': '0.30', 'manifest_path': str(budget),
                          'manifest_sha256': second.sha(budget), 'child_ledger': str(child),
                          'model': second.study.MODEL, 'provider': second.study.PROVIDER,
                          'reasoning': second.study.EFFORT}
            master.write_text(json.dumps(allocation) + '\n')
            with patch.object(second, 'OUTPUT', output), patch.object(second, 'MASTER', master):
                self.assertEqual(second.budget_entry(budget, require_fresh=True)['cap_usd'], '0.30')
                with self.assertRaisesRegex(ValueError, 'manifest path differs'):
                    second.budget_entry(output / 'wrong.json')
                reconciled = {'event': 'partition_reconciled', 'partition_id': second.PARTITION_ID,
                              'known_actual_usd': '0', 'unknown_upper_bound_usd': '0',
                              'unused_allocation_released_usd': '0.30',
                              'child_ledger': str(child), 'child_sha256': None}
                with child.open('a') as out:
                    out.write(json.dumps({'event': 'partition_closed', 'reason': 'terminal'}) + '\n')
                reconciled['child_sha256'] = second.sha(child)
                with master.open('a') as out:
                    out.write(json.dumps(reconciled) + '\n')
                self.assertEqual(second.budget_entry(budget)['cap_usd'], '0.30')
                with self.assertRaisesRegex(ValueError, 'sealed or reconciled'):
                    second.budget_entry(budget, require_dispatch=True)

    def test_claim_prevents_duplicate_dispatch_before_network(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            output = Path(temp)
            phase = output / 'fresh2' / 'P0'
            phase.mkdir(parents=True)
            (phase / 'suffix.claim.json').write_text('{}\n')
            with patch.object(second, 'OUTPUT', output), \
                 patch.object(second, 'verify_manifest', return_value={}), \
                 patch.object(second, 'verify_runtime_sources'), \
                 patch.object(second, 'require_order'), \
                 patch.object(second, 'verify_review'), \
                 patch.object(second.original, 'live_controls') as route:
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    second.execute('0' * 64, 'fresh2', 'P0', 'suffix',
                                   phase / 'suffix.root-review.json')
                route.assert_not_called()

    def test_frozen_invalid_policy_and_later_stage_gate(self):
        self.assertIs(second.original.CONTINUE_INTRINSIC_INVALID, False)
        self.assertIs(second.original.continue_record({
            'status': 'invalid_output', 'billing_ok': True,
            'cost_unknown': False, 'response_diagnostic': {'passed': True}},
            'development'), False)
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            with patch.object(second, 'OUTPUT', Path(temp)):
                with self.assertRaisesRegex(ValueError, 'stage evidence missing'):
                    second.require_order({}, '0' * 64, 'fresh3', 'P2', 'smoke')

    def test_helper_mutation_rejected_at_manifest_verification(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            output = Path(temp)
            helper = output / 'copied-helper.py'
            helper.write_text('VALUE = 1\n')
            sources = {key: second.binding(helper) for key in second.RUNTIME_SOURCE_KEYS}
            sources['new_budget_manifest'] = second.binding(helper)
            sources['old_reconciliation'] = second.binding(helper)
            manifest = {'source_bindings': sources}
            frozen = output / 'manifest.json'
            frozen.write_text(json.dumps(manifest) + '\n')
            digest = second.sha(frozen)
            with patch.object(second, 'OUTPUT', output), \
                 patch.object(second, 'expected_manifest', return_value=manifest):
                self.assertEqual(second.verify_manifest(digest), manifest)
                helper.write_text('VALUE = 2\n')
                with self.assertRaisesRegex(ValueError, 'Bound source changed'):
                    second.verify_manifest(digest)

    def test_helper_mutation_rejected_before_each_request(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            helper = Path(temp) / 'copied-helper.py'
            helper.write_text('VALUE = 1\n')
            manifest = {'source_bindings': {
                key: second.binding(helper) for key in second.RUNTIME_SOURCE_KEYS}}
            second.verify_runtime_sources(manifest)
            helper.write_text('VALUE = 2\n')
            with self.assertRaisesRegex(ValueError, 'Bound source changed'):
                second.verify_runtime_sources(manifest)

    def test_dispatch_checks_helpers_again_before_reservation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            output = Path(temp)
            budget = output / 'budget.json'
            budget.write_text('{}\n')
            review = output / 'review.json'
            review.write_text('{}\n')
            manifest = {'source_bindings': {'new_budget_manifest': second.binding(budget)},
                        'child_cap_usd': '0.30'}
            ledger = MagicMock()
            ledger.cap = Decimal('0.30')
            ledger.master_cap = Decimal('12.38')
            ledger.closed = False
            ledger.state.return_value = (None, {}, False)
            ledger.accounted.return_value = Decimal(0)
            request = {'record_id': 'DEV-003', 'payload': {}, 'request_sha256': '0' * 64}
            with patch.object(second, 'OUTPUT', output), \
                 patch.object(second, 'verify_manifest', return_value=manifest), \
                 patch.object(second, 'verify_runtime_sources',
                              side_effect=[None, ValueError('Bound source changed')]) as check, \
                 patch.object(second, 'require_order'), \
                 patch.object(second, 'verify_review'), \
                 patch.object(second.study, 'verify', return_value={}), \
                 patch.object(second.original, 'live_controls',
                              return_value=({}, {}, second.RESERVE)), \
                 patch.object(second, 'budget_entry'), \
                 patch.object(second.partitions, 'open_partition', return_value=ledger), \
                 patch.object(second.paid, 'load_key', return_value='test-only'), \
                 patch.object(second, 'selected_requests', return_value=[request]), \
                 patch.object(second.original, 'fetch_captured') as fetch:
                with self.assertRaisesRegex(ValueError, 'Bound source changed'):
                    second.execute('0' * 64, 'fresh2', 'P0', 'suffix', review)
                self.assertEqual(check.call_count, 2)
                ledger.reserve.assert_not_called()
                fetch.assert_not_called()
                ledger.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
