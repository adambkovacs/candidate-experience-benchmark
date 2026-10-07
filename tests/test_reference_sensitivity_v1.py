import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import analyze_reference_sensitivity_v1 as sensitivity


class ReferenceSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = sensitivity.analysis()

    def test_only_documented_alternatives_and_all_seven_scenarios(self):
        data = self.result
        self.assertEqual(data['reference_status'], 'frozen_v0.2_provisional_unchanged')
        self.assertEqual(data['extended_run_count'], 637)
        self.assertEqual(data['native_seven_run_count'], 7)
        self.assertEqual(len(data['scenarios']), 7)
        self.assertEqual([(item['id'], item['field'], item['saved'], item['alternative'])
                          for item in data['alternatives']],
                         [(item[0], item[1], item[2], item[3])
                          for item in sensitivity.ALTERNATIVES])
        self.assertEqual(len(data['extended_run_sources']), 637)
        self.assertEqual(len(data['native_seven_run_sources']), 7)
        self.assertTrue(all(len(scenario['extended_run_deltas']) == 637 and
                            len(scenario['native_seven_run_deltas']) == 7
                            for scenario in data['scenarios']))

    def test_saved_scores_and_distinct_case_deltas_reconcile(self):
        scenarios = {scenario['id']: scenario for scenario in self.result['scenarios']}
        singles = [scenarios[case] for case in ('dev006', 'dev013', 'dev030')]
        combined = scenarios['dev006+dev013+dev030']
        for cohort in ('extended_run_deltas', 'native_seven_run_deltas'):
            single_by_id = [{row['id']: row for row in scenario[cohort]} for scenario in singles]
            for row in combined[cohort]:
                self.assertEqual(row['denominator'], 60)
                self.assertEqual(len(row['changed_case_effects']), 3)
                self.assertEqual(row['score_deltas']['all_four'],
                                 sum(part[row['id']]['score_deltas']['all_four']
                                     for part in single_by_id))
                self.assertEqual(row['hypothetical_scores']['all_four'] -
                                 row['saved_scores']['all_four'],
                                 row['score_deltas']['all_four'])
                self.assertEqual(sum(effect['all_four_delta']
                                     for effect in row['changed_case_effects']),
                                 row['score_deltas']['all_four'])
        self.assertEqual(scenarios['dev006']['native_seven_summary']
                         ['all_four_delta_distribution'], {'-1': 1, '0': 1, '1': 5})
        self.assertEqual(scenarios['dev030']['native_seven_summary']
                         ['all_four_delta_distribution'], {'0': 7})

    def test_invalid_or_unsent_answer_cannot_gain_under_hypothetical_key(self):
        reference = {field: 'no' for field in sensitivity.FIELDS}
        revised = {**reference, 'sentiment': 'positive'}
        effect = sensitivity.case_effect('DEV-030', None, reference, revised, 'never_sent')
        self.assertEqual(effect['all_four_delta'], 0)
        self.assertEqual(effect['status'], 'never_sent')
        self.assertIsNone(effect['prediction'])

    def test_unreviewed_alternative_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'revision.json'
            proposal = json.loads((ROOT / sensitivity.REVISION).read_text())
            proposal['unchanged_needs_human'][0]['alternative'] = 'mixed'
            path.write_text(json.dumps(proposal))
            with self.assertRaisesRegex(ValueError, 'Documented alternative labels changed'):
                sensitivity.reviewed_alternatives(revision_path=path)


if __name__ == '__main__':
    unittest.main()
