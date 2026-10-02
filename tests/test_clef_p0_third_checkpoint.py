import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_clef_p0_third_checkpoint as checkpoint
import build_clef_findings as first
import clef_native_preparation as prep


class ClefThirdP0CheckpointTests(unittest.TestCase):
    def test_archived_checkpoint_matches_saved_feed(self):
        built = checkpoint.build()
        self.assertEqual(built, json.loads((ROOT / checkpoint.OUTPUT).read_text()))
        clef = built['models']['clef']
        flash = built['models']['clef-flash']
        self.assertEqual(clef['p0AllFourByPass'],
                         {'fresh1': 53, 'fresh2': 53, 'fresh3': 53})
        self.assertEqual(clef['fresh3P0']['valid'], 60)
        self.assertEqual(clef['fresh3P0']['denominator'], 60)
        self.assertEqual(clef['fresh2ToFresh3']['sharedValid'], 60)
        self.assertEqual(clef['threePassPredictionChangedIds'], [])
        self.assertEqual(clef['nativeDistributionChangedIds'], [])
        self.assertEqual(clef['vendorConfidenceChangedIds'], [])
        for field in prep.KEYS:
            self.assertEqual(clef['fresh3P0']['fields'][field]['valid'], 60)
            self.assertEqual(clef['fresh2ToFresh3']['fields'][field]
                             ['nativeDistributionChangedIds'], [])
            self.assertEqual(clef['fresh2ToFresh3']['fields'][field]
                             ['vendorConfidenceChangedIds'], [])
        self.assertEqual(clef['fresh3P0']['observedInputTokens'], 132694)
        self.assertIsNone(clef['fresh3P0']['providerBilledUsd'])
        self.assertEqual(flash['scoredCellsOfNine'], 2)
        self.assertEqual(flash['fresh3P0']['attempted'], 1)
        self.assertEqual(flash['fresh3P0']['valid'], 0)
        self.assertEqual(flash['fresh3P0']['unknownOutcomeIds'], ['DEV-001'])
        self.assertEqual(flash['fresh3P0']['neverSentIds'], list(first.IDS[1:]))
        self.assertIsNone(flash['fresh3P0']['score'])
        self.assertIs(flash['fresh3P0']['externalConnectorError'], True)
        self.assertIs(flash['fresh3P0']['providerEnvelopeAvailable'], False)
        self.assertNotIn('4006', json.dumps(built['models']))
        self.assertIn('results/clef-native-v1/clef-flash/fresh3/P0/development/'
                      'external-error-audit.json', built['sourceSha256'])

    def test_changed_flash_error_audit_refuses_publication(self):
        original = first.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('/external-error-audit.json'):
                value['no_replay'] = False
            return value

        with patch.object(first.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'Flash unknown result'):
                checkpoint.build()

    def test_changed_clef_terminal_refuses_publication(self):
        original = first.Sources.json

        def changed(sources, relative):
            value = original(sources, relative)
            if str(relative).endswith('/clef/fresh3/P0/development/completion.json'):
                value['attempted'] = 59
            return value

        with patch.object(first.Sources, 'json', changed):
            with self.assertRaisesRegex(ValueError, 'Incomplete or unbound'):
                checkpoint.build()

    def test_missing_evidence_refuses_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises((FileNotFoundError, ValueError)):
                checkpoint.build(Path(temporary))


if __name__ == '__main__':
    unittest.main()
