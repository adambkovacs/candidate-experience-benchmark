"""Offline isolation and source checks for the Gemma 26B $12.38-budget lane."""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_on_fresh_repeat_study_v2 as study
import gemma26_on_fresh_repeat_execution_v2 as execution
import paid_budget_partitions_v3 as partitions


class Gemma26Budget1238Tests(unittest.TestCase):
    def test_all_passes_preserve_original_payloads_controls_and_order(self):
        self.assertEqual(study.SERIES, 'gemma26-on-fresh-matched3-v2')
        self.assertNotEqual(study.BASE, study.ORIGINAL_BASE)
        for repeat in study.ORDERS:
            with self.subTest(repeat=repeat):
                plan = study.plan_data(repeat)
                original_path = study.ORIGINAL_BASE / repeat / 'manifest.json'
                original = json.loads(original_path.read_text())
                self.assertEqual(plan['conditions'], original['conditions'])
                self.assertEqual(plan['condition_order'], original['condition_order'])
                self.assertEqual(plan['original_plan_binding'], {
                    'path': str(original_path.relative_to(ROOT)),
                    'sha256': study.sha(original_path),
                })
                self.assertEqual(plan['model'], original['model'])
                self.assertEqual(plan['reasoning_effort'], original['reasoning_effort'])
                self.assertEqual(plan['child_partition_cap_proposed_usd'], '0.40')

    def test_new_money_modules_and_original_plan_are_source_bound(self):
        plan = study.plan_data('fresh1')
        bindings = {item['path']: item['sha256'] for item in plan['source_bindings']}
        for relative in (
                'scripts/gemma26_on_fresh_repeat_study_v2.py',
                'scripts/gemma26_on_fresh_repeat_execution_v2.py',
                'scripts/openrouter_budget_v3.py',
                'scripts/paid_budget_partitions_v3.py',
                plan['original_plan_binding']['path']):
            with self.subTest(relative=relative):
                self.assertEqual(bindings[relative], study.sha(ROOT / relative))
        self.assertNotIn('scripts/openrouter_budget_v2.py', bindings)
        self.assertNotIn('scripts/paid_budget_partitions_v2.py', bindings)
        self.assertIs(execution.partitions, partitions)

    def test_verifier_rejects_changed_bound_source_without_freezing_real_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            plan = study.plan_data('fresh1')
            folder = base / 'fresh1'
            folder.mkdir()
            manifest = folder / 'manifest.json'
            manifest.write_text(json.dumps(plan) + '\n')
            with patch.object(study, 'BASE', base):
                self.assertEqual(study.verify('fresh1', study.sha(manifest)), plan)
                plan['source_bindings'][0]['sha256'] = '0' * 64
                manifest.write_text(json.dumps(plan) + '\n')
                with self.assertRaisesRegex(ValueError, 'Bound source changed'):
                    study.verify('fresh1', study.sha(manifest))

    def test_old_receipts_and_old_phase_tree_cannot_admit_new_series(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'v2'
            old = Path(temp) / 'v1' / 'fresh1' / 'P0'
            old.mkdir(parents=True)
            (old / 'development.claim.json').write_text('{"historical":true}\n')
            receipt = Path(temp) / 'receipt.json'
            receipt.write_text(json.dumps({
                'schema': execution.RECEIPT_SCHEMA,
                'approved': True,
                'configuration_id': study.CONFIG,
                'partition_cap_usd': '0.40',
                'stage': 'fresh1/P0/smoke',
            }) + '\n')
            with self.assertRaisesRegex(ValueError, 'configuration or cap differs'):
                execution.review_receipt(receipt, 'fresh1', 'P0', 'smoke', 'x')
            receipt.write_text(json.dumps({
                'schema': 'gemma26-on-fresh-matched3-root-review-v1',
                'approved': True,
                'series_id': study.SERIES,
            }) + '\n')
            with self.assertRaisesRegex(ValueError, 'missing approval'):
                execution.review_receipt(receipt, 'fresh1', 'P0', 'smoke', 'x')
            plan = study.plan_data('fresh2')
            with patch.object(study, 'BASE', base):
                with self.assertRaisesRegex(ValueError, 'Earlier fresh pass incomplete'):
                    execution.require_order(plan, 'P1', 'smoke')

    def test_budget_gate_requires_amended_master_cap(self):
        class Child:
            cap = Decimal('0.40')
            master_cap = Decimal('10')
            closed = False

            def close(self):
                self.closed = True

        child = Child()
        with patch.object(partitions, 'open_partition', return_value=child):
            with self.assertRaisesRegex(ValueError, 'Amended master'):
                execution.budget_gate({'partition_id': 'new-child'}, Path('/unused'))
        self.assertTrue(child.closed)


if __name__ == '__main__':
    unittest.main()
