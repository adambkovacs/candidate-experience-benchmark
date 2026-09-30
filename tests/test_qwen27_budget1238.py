"""Offline source, payload and budget isolation checks for Qwen27 v2."""
import inspect
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen27_fresh_repeat_study as original_study
import qwen27_fresh_repeat_execution as original_execution
import qwen27_fresh_repeat_study_v2 as study
import qwen27_fresh_repeat_execution_v2 as execution
import paid_budget_partitions_v3 as partitions


class Qwen27Budget1238Tests(unittest.TestCase):
    def test_six_plans_preserve_every_original_request_and_control(self):
        self.assertEqual(study.SERIES, 'qwen27-fresh-matched3-v2')
        self.assertNotEqual(study.BASE, original_study.BASE)
        for config in study.CONFIGS:
            for repeat in study.ORDERS:
                with self.subTest(config=config, repeat=repeat):
                    plan = study.plan_data(config, repeat)
                    original_path = original_study.BASE / config / repeat / 'manifest.json'
                    original = original_study.verify(config, repeat, original_study.sha(original_path))
                    self.assertEqual(plan['conditions'], original['conditions'])
                    self.assertEqual(plan['condition_order'], original['condition_order'])
                    self.assertEqual(plan['series_id'], study.SERIES + '-' + config.rsplit('-', 1)[-1])
                    self.assertEqual(plan['aggregate_cap_usd'], '12.38')
                    self.assertEqual(plan['proposed_child_budget_usd'], original['proposed_child_budget_usd'])
                    self.assertEqual(plan['original_plan_binding'], {
                        'path': str(original_path.relative_to(ROOT)),
                        'sha256': study.sha(original_path),
                    })

    def test_versioned_money_and_original_manifest_are_bound(self):
        for config in study.CONFIGS:
            plan = study.plan_data(config, 'fresh1')
            bindings = {item['path']: item['sha256'] for item in plan['source_bindings']}
            for relative in (
                    'scripts/qwen27_fresh_repeat_study_v2.py',
                    'scripts/qwen27_fresh_repeat_execution_v2.py',
                    'tests/test_qwen27_budget1238.py',
                    'scripts/openrouter_budget_v3.py',
                    'scripts/paid_budget_partitions_v3.py',
                    plan['original_plan_binding']['path']):
                with self.subTest(config=config, relative=relative):
                    self.assertEqual(bindings[relative], study.sha(ROOT / relative))
            self.assertNotIn('scripts/openrouter_budget_v2.py', bindings)
            self.assertNotIn('scripts/paid_budget_partitions_v2.py', bindings)
        self.assertIs(execution.partitions, partitions)

    def test_execution_manifest_uses_six_versioned_plans_and_v3_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch.object(study, 'BASE', base):
                for config in study.CONFIGS:
                    for repeat in study.ORDERS:
                        target = base / config / repeat / 'manifest.json'
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(json.dumps(study.plan_data(config, repeat)) + '\n')
                execution_plan = execution.execution_plan()
                self.assertEqual(execution_plan['schema'], 'qwen27-fresh-matched3-execution-v2')
                self.assertEqual(len(execution_plan['plans_sha256']), 2)
                self.assertEqual(sum(map(len, execution_plan['plans_sha256'].values())), 6)
                self.assertIn('paid_budget_partitions_v3.py', execution_plan['source_code_sha256'])
                self.assertIn('openrouter_budget_v3.py', execution_plan['source_code_sha256'])
                self.assertNotIn('paid_budget_partitions_v2.py', execution_plan['source_code_sha256'])

    def test_old_receipts_and_phase_tree_cannot_admit_new_series(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary) / 'v2'
            old = Path(temporary) / 'v1' / 'openrouter-paid-qwen3.8-27b-medium' / 'fresh1' / 'P0'
            old.mkdir(parents=True)
            (old / 'smoke.claim.json').write_text('{}\n')
            self.assertNotEqual(
                execution.phase_paths('openrouter-paid-qwen3.8-27b-medium', 'fresh1', 'P0', 'smoke')[0],
                original_execution.phase_paths('openrouter-paid-qwen3.8-27b-medium', 'fresh1', 'P0', 'smoke')[0],
            )
            receipt = Path(temporary) / 'receipt.json'
            receipt.write_text(json.dumps({
                'schema': execution.RECEIPT_SCHEMA, 'approved': True,
                'configuration_id': 'openrouter-paid-qwen3.8-27b-medium',
                'partition_cap_usd': '1.00',
                'stage': 'fresh1/P0/smoke',
            }) + '\n')
            with self.assertRaisesRegex(ValueError, 'configuration or cap differs'):
                execution.review_receipt(receipt, 'openrouter-paid-qwen3.8-27b-medium',
                                         'fresh1', 'P0', 'smoke', 'x')
            receipt.write_text(json.dumps({
                'schema': original_execution.RECEIPT_SCHEMA, 'approved': True,
                'series_id': study.SERIES + '-medium',
            }) + '\n')
            with self.assertRaisesRegex(ValueError, 'missing approval'):
                execution.review_receipt(receipt, 'openrouter-paid-qwen3.8-27b-medium',
                                         'fresh1', 'P0', 'smoke', 'x')
            with patch.object(study, 'BASE', base):
                self.assertFalse((base / 'openrouter-paid-qwen3.8-27b-medium' /
                                  'fresh1' / 'P0' / 'smoke.claim.json').exists())

    def test_new_phase_claim_blocks_replay_before_provider_or_budget(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch.object(study, 'BASE', base), \
                 patch.object(study, 'verify', return_value={'series_id': study.SERIES + '-medium'}), \
                 patch.object(execution, 'require_order'), \
                 patch.object(execution, 'review_receipt') as receipt, \
                 patch.object(execution, 'live_controls') as provider, \
                 patch.object(execution, 'budget_gate') as budget:
                folder, claim, _, _ = execution.phase_paths(config, 'fresh1', 'P0', 'smoke')
                folder.mkdir(parents=True)
                claim.write_text('{"already_claimed":true}\n')
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    execution.execute(config, 'fresh1', 'P0', 'smoke', 'x', Path('/unused'))
                receipt.assert_not_called()
                provider.assert_not_called()
                budget.assert_not_called()

    def test_budget_gate_requires_amended_master_cap(self):
        class Child:
            cap = Decimal('1.00')
            master_cap = Decimal('10')
            closed = False

            def close(self):
                self.closed = True

        child = Child()
        with patch.object(partitions, 'open_partition', return_value=child):
            with self.assertRaisesRegex(ValueError, 'Amended master'):
                execution.budget_gate({'partition_id': 'medium-child'}, Path('/unused'),
                                      'openrouter-paid-qwen3.8-27b-medium')
        self.assertTrue(child.closed)
        child.cap = Decimal('0.80')
        child.master_cap = Decimal('12.38')
        child.closed = False
        with patch.object(partitions, 'open_partition', return_value=child):
            self.assertIs(execution.budget_gate({'partition_id': 'xhigh-child'}, Path('/unused'),
                                                'openrouter-paid-qwen3.8-27b-xhigh'), child)
        self.assertFalse(child.closed)

    def test_wire_capture_parser_and_stop_policy_match_frozen_runner(self):
        for name in ('response_bytes', 'safe_headers', 'fetch_recorded',
                     'classify', 'continue_record'):
            with self.subTest(name=name):
                self.assertEqual(inspect.getsource(getattr(execution, name)),
                                 inspect.getsource(getattr(original_execution, name)))
        self.assertIs(execution.CONTINUE_INTRINSIC_INVALID, False)
        self.assertEqual(execution.MAX_RESPONSE_BYTES, original_execution.MAX_RESPONSE_BYTES)


if __name__ == '__main__':
    unittest.main()
