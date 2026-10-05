import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_clef_flash_p1_findings as findings


class ClefFlashP1FindingsTests(unittest.TestCase):
    def test_projection_scores_p1_and_audits_matched_p0_control(self):
        report = findings.build()
        self.assertEqual(report['configuration']['model'], 'clef-flash')
        self.assertEqual(report['configuration']['condition'], 'P1')
        self.assertEqual(report['phase']['counts'], {
            'valid': 60, 'invalidOutput': 0, 'serviceError': 0,
            'unknownOutcome': 0, 'neverSent': 0})
        self.assertEqual(report['phase']['observedInputTokens'], 144694)
        self.assertEqual(report['phaseByPass']['fresh2']['observedInputTokens'], 144694)
        self.assertEqual(report['phaseByPass']['fresh3']['observedInputTokens'], 144694)
        self.assertEqual(report['phaseByPass']['fresh2']['allFourCorrect'], 47)
        self.assertEqual(report['phaseByPass']['fresh3']['allFourCorrect'], 47)
        self.assertEqual(report['controls']['p1Repeatability']['sharedValid'], 60)
        self.assertEqual(report['controls']['p1Repeatability']['predictionVectorChangedIds'], [])
        self.assertEqual(report['controls']['p1Repeatability']['nativeDistributionsChangedIds'], [])
        self.assertEqual(report['controls']['p1Repeatability']['vendorConfidenceChangedIds'], [])
        for key in ('p1Fresh1Fresh3', 'p1Fresh2Fresh3'):
            self.assertEqual(report['controls'][key]['predictionVectorChangedIds'], [])
            self.assertEqual(report['controls'][key]['nativeDistributionsChangedIds'], [])
            self.assertEqual(report['controls'][key]['vendorConfidenceChangedIds'], [])
        self.assertEqual(report['controls']['fullPassesCompleted'], 3)
        self.assertIsNone(report['cost']['providerBilledUsd'])
        self.assertEqual(report['cost']['publishedInputPriceEstimateUsd'], '0.01302246')
        self.assertEqual(report['controls']['matchedFresh1P0']['sharedValid'], 60)
        self.assertTrue(report['controls']['matchedFresh1P0']['auditPassed'])
        comparison = report['controls']['matchedFresh1P0']['comparison']
        self.assertEqual(comparison['allFourDelta'], 2)
        self.assertEqual(comparison['allFourBecameCorrectIds'], ['DEV-027', 'DEV-044'])
        self.assertEqual(comparison['allFourBecameIncorrectIds'], [])
        self.assertEqual(len(comparison['nativeDistributionsChangedIds']), 60)
        self.assertEqual(len(comparison['vendorConfidenceChangedIds']), 60)
        self.assertEqual(report['phase']['fields']['follow_up_needed']['correct'], 57)
        self.assertEqual(len(report['phase']['fields']['follow_up_needed']
                             ['chosenProbabilityHighErrors']), 2)
        self.assertEqual(len(report['phase']['fields']['serious_concern_reported']
                             ['vendorConfidenceHighErrors']), 1)
        self.assertNotIn('account_id_sha256', json.dumps(report))
        self.assertNotIn('quota', json.dumps(report).lower())
        self.assertGreater(len(report['sourceSha256']), 50)

    def test_saved_projection_matches_current_source_evidence(self):
        report = findings.build()
        self.assertEqual(report, json.loads((ROOT / findings.OUTPUT).read_text()))

    def test_changed_development_completion_blocks_projection(self):
        original = findings.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('clef-flash/fresh1/P1/development/completion.json'):
                value['attempted'] = 59
            return value

        from unittest.mock import patch
        with patch.object(findings.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'completion'):
                findings.build()

    def test_changed_connected_app_request_blocks_projection(self):
        original = findings.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('/clef-flash/fresh1/P1/development/app-bridge/'
                                      '00bf29c5-e843-420a-9aa7-4b719fc5b96d.request.json'):
                value['request_sha256'] = '0' * 64
            return value

        from unittest.mock import patch
        with patch.object(findings.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'P1 app, response'):
                findings.build()


if __name__ == '__main__':
    unittest.main()
