import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_jev_confidence_findings as confidence
import build_jev_native_prompt_report_v1 as verified


def references():
    return {row['id']: row['proposed_labels']
            for row in verified.lines(ROOT / 'data/pilot/proposed_labels.jsonl')}


class JevConfidenceFindingsTests(unittest.TestCase):
    def test_closed_sources_and_fixed_denominator(self):
        report = confidence.build()
        self.assertEqual(report['conditions']['P0']['valid'], 60)
        self.assertEqual(report['conditions']['P1']['invalidIds'], ['DEV-053'])
        self.assertEqual(report['conditions']['P2']['invalidIds'], ['DEV-040'])
        for condition in report['conditions'].values():
            for field in condition['fields'].values():
                self.assertEqual(field['correct'] + field['wrong'], condition['valid'])
                for threshold in field['thresholds'].values():
                    self.assertEqual(threshold['retained'] + threshold['withheldValid'], condition['valid'])
                    self.assertEqual(threshold['retainedCorrect'] + threshold['retainedWrong'], threshold['retained'])
                    self.assertEqual(threshold['withheldCorrect'] + threshold['withheldWrong'], threshold['withheldValid'])
                    self.assertEqual(threshold['retainedWrong'] + threshold['withheldWrong'], field['wrong'])
                    self.assertEqual(threshold['retained'] + threshold['withheldValid'] + threshold['unavailableInvalid'], 60)
        self.assertEqual(report['conditions']['P0']['fields']['serious_concern_reported']['thresholds']['0.9']['confidentlyWrongIds'], ['DEV-029'])

    def test_malformed_confidence_and_prediction_cannot_enter_analysis(self):
        rows = verified.lines(ROOT / 'results/jev-native-prompt-variants-v1/P1-development.jsonl')
        bad = copy.deepcopy(rows)
        bad[0]['raw_response']['answers']['sentiment']['confidence'] = 1.01
        with self.assertRaises(ValueError):
            confidence.condition_summary(bad, references())
        bad = copy.deepcopy(rows)
        bad[0]['prediction']['sentiment'] = 'negative'
        with self.assertRaises(ValueError):
            confidence.condition_summary(bad, references())

    def test_invalid_distribution_is_unavailable_not_wrong(self):
        rows = verified.lines(ROOT / 'results/jev-native-prompt-variants-v1/P1-development.jsonl')
        invalid = next(row for row in rows if row['id'] == 'DEV-053')
        self.assertEqual(invalid['status'], 'invalid_output')
        self.assertIsNone(invalid['prediction'])
        summary = confidence.condition_summary(rows, references())
        self.assertEqual(summary['valid'], 59)
        self.assertEqual(summary['invalidIds'], ['DEV-053'])
        for field in summary['fields'].values():
            self.assertTrue(all(case['id'] != 'DEV-053' for case in field['wrongCases']))

    def test_request_source_drift_rejected_by_frozen_validator(self):
        source = ROOT / 'results/jev-native-prompt-variants-v1'
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / 'historical'
            shutil.copytree(source, copy)
            path = copy / 'P1-development.jsonl'
            rows = verified.lines(path)
            rows[0]['request']['state']['feedback'] += ' changed'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaises(ValueError):
                confidence.build(copy)

    def test_selected_probability_not_used_as_reported_confidence(self):
        report = confidence.build()
        cases = report['conditions']['P0']['fields']['serious_concern_reported']['wrongCases']
        self.assertTrue(any(case['confidence'] != case['selectedChoiceProbability'] for case in cases))
        observed = {case['id'] for case in cases if case['confidence'] >= 0.9}
        self.assertEqual(observed, set(report['conditions']['P0']['fields']['serious_concern_reported']['thresholds']['0.9']['confidentlyWrongIds']))


if __name__ == '__main__':
    unittest.main()
