import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_clef_findings as findings
import clef_native_preparation as prep


class ClefFindingsTests(unittest.TestCase):
    def test_saved_report_matches_all_closed_evidence(self):
        built = findings.build()
        saved = json.loads((ROOT / findings.OUTPUT).read_text())
        self.assertEqual(built, saved)
        self.assertEqual(set(built['models']), {'clef', 'clef-flash'})
        self.assertEqual([built['models'][name]['valid'] for name in findings.MODELS], [60, 60])
        self.assertEqual([built['models'][name]['allFourCorrect'] for name in findings.MODELS], [53, 45])
        self.assertEqual([built['models'][name]['publishedInputPriceEstimateUsd']
                          for name in findings.MODELS], ['0.03184656', '0.01194246'])
        self.assertIsNone(built['cost']['providerBilledUsd'])
        self.assertFalse(built['timing']['inferenceLatencyAvailable'])
        self.assertIn('postapproval-ledger-after-full-p0.jsonl',
                      ' '.join(built['sourceSha256']))
        self.assertNotIn('results/postapproval-paid-work-2026-10-02.jsonl',
                         built['sourceSha256'])

    def test_vendor_confidence_is_not_chosen_probability(self):
        field = 'follow_up_needed'
        first, second, third = prep.VALUES[field]
        entries = []
        for number in range(60):
            entries.append({'id': f'DEV-{number + 1:03d}',
                            'reference': {field: second if number < 10 else first},
                            'prediction': {field: first},
                            'probabilities': {field: {first: 0.9, second: 0.1, third: 0.0}},
                            'confidence': {field: 0.2}})
        result = findings.field_metrics(entries, field)
        self.assertEqual(result['correct'], 50)
        self.assertEqual(len(result['chosenProbabilityHighErrors']), 10)
        self.assertEqual(result['vendorConfidenceHighErrors'], [])
        self.assertEqual(result['nativeDistribution']['zeroTrueClassProbabilityCount'], 0)

    def test_non_distribution_rejected(self):
        field = 'follow_up_needed'
        first, second, third = prep.VALUES[field]
        entries = [{'id': f'DEV-{number + 1:03d}',
                    'reference': {field: first}, 'prediction': {field: first},
                    'probabilities': {field: {first: 0.9, second: 0.9, third: 0.0}},
                    'confidence': {field: 0.9}} for number in range(60)]
        with self.assertRaisesRegex(ValueError, 'Invalid native distribution'):
            findings.field_metrics(entries, field)

    def test_missing_second_terminal_stage_refuses_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            completion = root / findings.BASE / 'clef/fresh1/P0/development/completion.json'
            completion.parent.mkdir(parents=True)
            completion.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'not terminal: clef-flash'):
                findings.build(root)

    def test_record_mismatch_refuses_publication(self):
        original_json = findings.Sources.json

        def changed_json(sources, relative):
            value = original_json(sources, relative)
            if str(relative).endswith('/clef/fresh1/P0/development/claim.json'):
                value['model'] = 'clef-flash'
            return value

        with patch.object(findings.Sources, 'json', changed_json):
            with self.assertRaisesRegex(ValueError, 'Incomplete or unbound'):
                findings.build()


if __name__ == '__main__':
    unittest.main()
