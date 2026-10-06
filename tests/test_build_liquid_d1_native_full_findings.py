import unittest
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_liquid_d1_native_full_findings as report


class LiquidFullFindingsTests(unittest.TestCase):
    def test_threshold_audit_uses_provider_confidence_not_choice_probability(self):
        rows = [
            {'reference': {'follow_up_needed': 'yes'},
             'answers': {'follow_up_needed': {'choice': 'no', 'confidence': 0.995,
                                             'probabilities': {'no': 0.8}}}},
            {'reference': {'follow_up_needed': 'no'},
             'answers': {'follow_up_needed': {'choice': 'no', 'confidence': 0.95,
                                             'probabilities': {'no': 0.999}}}},
            {'reference': {'follow_up_needed': 'yes'},
             'answers': {'follow_up_needed': {'choice': 'yes', 'confidence': 0.2,
                                             'probabilities': {'yes': 0.999}}}},
        ]
        actual = report.field_audit(rows, 'follow_up_needed')
        self.assertEqual(actual['correct'], 2)
        self.assertEqual(actual['confusion_reference_by_choice']['yes']['no'], 1)
        at_90 = actual['provider_confidence_thresholds']['0.9']
        self.assertEqual((at_90['retained'], at_90['correct_retained'],
                          at_90['confidently_wrong'], at_90['abstained']), (2, 1, 1, 1))
        self.assertEqual(at_90['conditional_agreement'], 0.5)
        at_99 = actual['provider_confidence_thresholds']['0.99']
        self.assertEqual((at_99['retained'], at_99['correct_retained'],
                          at_99['confidently_wrong']), (1, 0, 1))

    def test_p0_projection_excludes_request_text_and_reference_labels(self):
        if not (report.FOLDER / 'development.raw.jsonl').exists():
            self.skipTest('Private raw evidence is not archived in public checkout')
        result = report.build()
        self.assertEqual((result['record_count'], result['valid_outputs']), (60, 60))
        self.assertEqual(result['source_bindings']['raw_sha256'],
                         report.full.sha(report.FOLDER / 'development.raw.jsonl'))
        for row in result['records']:
            self.assertNotIn('reference', row)
            self.assertNotIn('feedback', row)
            self.assertNotIn('response_base64', row)
            self.assertNotIn('id', row['answers']['sentiment'])

    def test_portable_checker_rejects_changed_confidence_or_source_hash(self):
        if not report.OUTPUT.exists():
            self.skipTest('Public projection is not present in this checkout')
        value = json.loads(report.OUTPUT.read_text())
        self.assertEqual(report.portable_check(value), report.full.sha(report.OUTPUT))
        changed = deepcopy(value)
        changed['records'][0]['answers']['sentiment']['confidence'] = 0.0
        with self.assertRaises(ValueError):
            report.portable_check(changed)
        changed = deepcopy(value)
        changed['source_bindings']['raw_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            report.portable_check(changed)


if __name__ == '__main__':
    unittest.main()
