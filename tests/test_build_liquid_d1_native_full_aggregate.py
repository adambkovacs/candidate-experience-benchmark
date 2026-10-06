import sys
import json
from pathlib import Path
import shutil
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_liquid_d1_native_full_aggregate as report
from development_benchmark import KEYS


class LiquidAggregateTests(unittest.TestCase):
    def test_condition_flip_counts_only_changed_labels(self):
        first = {'all_four_correct': 1,
                 'fields': {key: {'correct': 1} for key in KEYS},
                 'records': [{'id': 'DEV-001', 'prediction': {key: 'no' for key in KEYS}},
                             {'id': 'DEV-002', 'prediction': {key: 'no' for key in KEYS}}]}
        second = {'all_four_correct': 2,
                  'fields': {key: {'correct': 2} for key in KEYS},
                  'records': [{'id': 'DEV-001', 'prediction': {**{key: 'no' for key in KEYS},
                                                              'follow_up_needed': 'yes'}},
                              {'id': 'DEV-002', 'prediction': {key: 'no' for key in KEYS}}]}
        result = report.condition_summary({'fresh1/P1': first, 'fresh2/P1': second}, 'P1')
        self.assertEqual(result['all_four_correct_range']['min'], 1)
        self.assertEqual(result['all_four_correct_range']['max'], 2)
        self.assertEqual(result['choice_flip_record_count'], 1)
        self.assertEqual(result['choice_flips'][0]['id'], 'DEV-001')
        self.assertEqual(result['choice_flips'][0]['fields'], ['follow_up_needed'])

    def test_feed_uses_only_explicit_closed_stages(self):
        if not report.OUTPUT.exists():
            self.skipTest('Public aggregate not present in this checkout')
        result = report.build()
        self.assertEqual(result['closed_development_stages'], list(report.CLOSED_STAGES))
        self.assertEqual(result['closed_stage_count'], 7)
        self.assertEqual(result['planned_stage_count'], 9)
        self.assertEqual(result['unpublished_development_stages'],
                         ['fresh3/P1', 'fresh3/P2'])
        self.assertEqual(json.loads(report.OUTPUT.read_text()), result)

    def test_selected_root_uses_only_declared_source_bindings(self):
        if not report.OUTPUT.exists():
            self.skipTest('Public aggregate not present in this checkout')
        saved = json.loads(report.OUTPUT.read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for binding in saved['sourceBindings']:
                source = ROOT / binding['path']
                target = root / binding['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            self.assertEqual(report.build(root), saved)
            (root / saved['sourceBindings'][0]['path']).write_text('changed')
            with self.assertRaises(ValueError):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
