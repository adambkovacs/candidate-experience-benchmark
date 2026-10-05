import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_clef_flash_p2_findings as findings


class ClefFlashP2FindingsTests(unittest.TestCase):
    def test_projection_scores_p2_and_binds_both_matched_conditions(self):
        report = findings.build()
        self.assertEqual(report['configuration']['condition'], 'P2')
        self.assertEqual(report['phase']['counts'], {
            'valid': 60, 'invalidOutput': 0, 'serviceError': 0,
            'unknownOutcome': 0, 'neverSent': 0})
        self.assertEqual(report['phase']['allFourCorrect'], 46)
        self.assertEqual(report['phase']['observedInputTokens'], 154954)
        self.assertEqual(report['phaseByPass']['fresh2']['allFourCorrect'], 46)
        self.assertEqual(report['phaseByPass']['fresh2']['observedInputTokens'], 154954)
        self.assertEqual(report['phaseByPass']['fresh3']['allFourCorrect'], 46)
        self.assertEqual(report['phaseByPass']['fresh3']['observedInputTokens'], 154954)
        self.assertEqual(report['controls']['matchedFresh1P0']['allFourDelta'], 1)
        self.assertEqual(report['controls']['matchedFresh1P1']['allFourDelta'], -1)
        self.assertEqual(report['controls']['sharedValid'], 60)
        self.assertEqual(report['controls']['fullPassesCompleted'], 3)
        for key in ('p2Repeatability', 'p2Fresh1Fresh3', 'p2Fresh2Fresh3'):
            repeatability = report['controls'][key]
            self.assertEqual(repeatability['predictionVectorChangedIds'], [])
            self.assertEqual(repeatability['nativeDistributionsChangedIds'], [])
            self.assertEqual(repeatability['vendorConfidenceChangedIds'], [])
        self.assertIsNone(report['cost']['providerBilledUsd'])
        self.assertEqual(report['cost']['publishedInputPriceEstimateUsd'], '0.01394586')
        self.assertNotIn('account_id_sha256', json.dumps(report))
        self.assertNotIn('quota', json.dumps(report).lower())
        self.assertTrue(any(k.endswith('clef-flash-fresh1-p2-smoke-grant.json')
                            for k in report['sourceSha256']))
        self.assertTrue(any(k.endswith('clef-flash-fresh1-p2-development-grant.json')
                            for k in report['sourceSha256']))

    def test_saved_projection_matches_current_source_evidence(self):
        self.assertEqual(findings.build(),
                         json.loads((ROOT / findings.OUTPUT).read_text()))

    def test_changed_completion_blocks_projection(self):
        original = findings.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('clef-flash/fresh1/P2/development/completion.json'):
                value['attempted'] = 59
            return value

        with patch.object(findings.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'completion'):
                findings.build()


if __name__ == '__main__':
    unittest.main()
