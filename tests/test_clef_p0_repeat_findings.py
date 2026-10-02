import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_clef_p0_repeat_findings as repeats
import clef_native_preparation as prep


class ClefP0RepeatFindingsTests(unittest.TestCase):
    def test_closed_report_matches_archived_evidence(self):
        built = repeats.build()
        self.assertEqual(built, json.loads((ROOT / repeats.OUTPUT).read_text()))
        self.assertEqual(built['cohort']['fullPassesPerModelCompleted'], 2)
        self.assertEqual(built['cohort']['requiredFullPassesPerCondition'], 3)
        self.assertGreater(len(built['sourceSha256']), 1200)
        for model, expected in [('clef', 53), ('clef-flash', 45)]:
            item = built['models'][model]
            self.assertEqual((item['fresh1']['valid'], item['fresh2']['valid']), (60, 60))
            self.assertEqual((item['fresh1']['allFourCorrect'], item['fresh2']['allFourCorrect']),
                             (expected, expected))
            self.assertEqual(item['paired']['sharedValid'], 60)
            self.assertEqual(item['paired']['predictionVectorChangedIds'], [])
            self.assertEqual(item['paired']['allFourBecameCorrectIds'], [])
            self.assertEqual(item['paired']['allFourBecameIncorrectIds'], [])
            self.assertEqual(item['fresh2']['observedInputTokens'], 132694)
            self.assertIsNone(item['fresh2']['providerBilledUsd'])
            for field in prep.KEYS:
                self.assertEqual(item['paired']['fields'][field]['nativeDistributionChangedIds'], [])
                self.assertEqual(item['paired']['fields'][field]['vendorConfidenceChangedIds'], [])

    def test_paired_score_transition_and_native_fields_stay_distinct(self):
        field = prep.KEYS[0]
        labels = prep.VALUES[field]
        reference = {name: prep.VALUES[name][0] for name in prep.KEYS}
        first_rows, second_rows = [], []
        for number, rid in enumerate(repeats.IDS):
            first_rows.append({'id': rid, 'reference': reference,
                'prediction': dict(reference),
                'probabilities': {name: {value: (1 if value == reference[name] else 0)
                                        for value in prep.VALUES[name]} for name in prep.KEYS},
                'confidence': {name: 0.5 for name in prep.KEYS}})
            second_rows.append(json.loads(json.dumps(first_rows[-1])))
        second_rows[0]['prediction'][field] = labels[1]
        second_rows[0]['probabilities'][field][labels[0]] = 0.1
        second_rows[0]['probabilities'][field][labels[1]] = 0.9
        second_rows[1]['confidence'][field] = 0.8
        out = repeats.paired(first_rows, second_rows)
        self.assertEqual(out['predictionVectorChangedIds'], ['DEV-001'])
        self.assertEqual(out['allFourBecameIncorrectIds'], ['DEV-001'])
        self.assertEqual(out['fields'][field]['nativeDistributionChangedIds'], ['DEV-001'])
        self.assertEqual(out['fields'][field]['vendorConfidenceChangedIds'], ['DEV-002'])

    def test_changed_second_completion_refuses_publication(self):
        original = repeats.first.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('/clef/fresh2/P0/development/completion.json'):
                value['attempted'] = 59
            return value

        with patch.object(repeats.first.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'Incomplete or unbound'):
                repeats.build()

    def test_changed_bridge_reply_refuses_publication(self):
        original = repeats.first.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('.response.json') and '/fresh2/' in str(relative):
                value['http_status'] = 202
            return value

        with patch.object(repeats.first.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'Fresh2 raw/parsed mismatch'):
                repeats.build()

    def test_missing_second_stage_refuses_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises((FileNotFoundError, ValueError)):
                repeats.build(Path(temporary))


if __name__ == '__main__':
    unittest.main()
