import sys
import json
from pathlib import Path
import shutil
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_liquid_d1_native_full_aggregate as report
from development_benchmark import KEYS, VALUES


class LiquidAggregateTests(unittest.TestCase):
    def test_paired_prompt_counts_equal_scores_with_changed_answers_and_missing_ids(self):
        reference = {key: VALUES[key][0] for key in KEYS}
        wrong = VALUES['sentiment'][1]
        correct = dict(reference)
        incorrect = {**reference, 'sentiment': wrong}
        truth = {f'DEV-{index:03d}': reference for index in range(1, 5)}
        left = {'records': [{'id': 'DEV-001', 'prediction': correct},
                            {'id': 'DEV-002', 'prediction': incorrect},
                            {'id': 'DEV-003', 'prediction': correct}]}
        right = {'records': [{'id': 'DEV-001', 'prediction': incorrect},
                             {'id': 'DEV-002', 'prediction': correct},
                             {'id': 'DEV-004', 'prediction': correct}]}
        result = report.paired_prompt_comparison(left, right, truth,
                                                  'fresh1/P0', 'fresh1/P1')
        self.assertEqual(result['shared_valid'], 2)
        self.assertEqual(result['left_only_ids'], ['DEV-003'])
        self.assertEqual(result['right_only_ids'], ['DEV-004'])
        self.assertEqual(result['changed_record_count'], 2)
        self.assertEqual(result['label_flips_by_field']['sentiment']['ids'],
                         ['DEV-001', 'DEV-002'])
        self.assertEqual(result['all_four'],
                         {'left_correct': 1, 'right_correct': 1,
                          'gained_ids': ['DEV-002'], 'lost_ids': ['DEV-001']})
        self.assertEqual(result['fields']['sentiment']['gained_ids'], ['DEV-002'])
        self.assertEqual(result['fields']['sentiment']['lost_ids'], ['DEV-001'])

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
        self.assertEqual(result['closed_stage_count'], 9)
        self.assertEqual(result['planned_stage_count'], 9)
        self.assertEqual(result['unpublished_development_stages'], [])
        self.assertTrue(all(value['usage']['output_tokens'] == 0
                            for value in result['phases'].values()))
        self.assertTrue(all(value['usage']['input_tokens'] > 0
                            for value in result['phases'].values()))
        self.assertEqual(len(result['matched_prompt_comparisons']), 9)
        self.assertTrue(all(item['shared_valid'] == 60 and
                            not item['left_only_ids'] and not item['right_only_ids']
                            for item in result['matched_prompt_comparisons'].values()))
        for stage in result['phases'].values():
            for key in KEYS:
                matrix = stage['confusion_reference_by_choice'][key]
                self.assertEqual(sum(map(sum, (row.values() for row in matrix.values()))), 60)
                self.assertEqual(sum(matrix[value][value] for value in VALUES[key]),
                                 stage['fields_correct'][key])
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
