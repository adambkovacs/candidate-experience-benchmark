import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'build_extended_run_catalog_v1', ROOT / 'scripts/build_extended_run_catalog_v1.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ExtendedRunCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = MODULE.build(ROOT)

    def test_checked_in_catalog_matches_public_reports(self):
        saved = json.loads((ROOT / MODULE.OUT).read_text())
        self.assertEqual(saved, self.catalog)
        self.assertEqual(saved['runCount'], len(saved['runs']))

    def test_each_row_has_a_unique_public_report_binding(self):
        rows = self.catalog['runs']
        self.assertEqual(len(rows), len({row['id'] for row in rows}))
        for row in rows:
            path = row['sourceRecordsUrl'].removeprefix(MODULE.BASE)
            self.assertIn(path, self.catalog['sourceSha256'])
            self.assertEqual(row['sourceRecordSha256'], self.catalog['sourceSha256'][path])
            self.assertEqual(row['evidenceUrl'], row['sourceRecordsUrl'])
            self.assertEqual(row['records'], 60)
            self.assertLessEqual(row['valid'], 60)
            self.assertLessEqual(row['metrics']['all_four'], row['valid'])
            for field in MODULE.FIELDS:
                self.assertLessEqual(row['metrics'][field], row['valid'])

    def test_historical_original_and_sonnet_first_pass_are_not_duplicated(self):
        rows = self.catalog['runs']
        for row in rows:
            if row['sourceFamily'] in MODULE.HISTORICAL_ORIGINAL:
                self.assertNotEqual(row['repeatPass'], 'original')
            if row['sourceFamily'] == 'sonnet55-fresh-matched3':
                self.assertNotEqual(row['repeatPass'], 'pass1')
        base = json.loads((ROOT / 'public-site/data-provider-errors-v1.json').read_text())
        supplemental = json.loads((ROOT / 'public-site/supplemental-decision-runs-v1.json').read_text())
        known = {row['id'] for row in base['runs']} | {row['id'] for row in supplemental['runs']}
        self.assertFalse(known & {row['id'] for row in rows})

    def test_partial_and_zero_response_stages_are_truthful(self):
        rows = self.catalog['runs']
        self.assertTrue(any(row['sourceFamily'] == 'jev-native-prompt-findings' and
                            row['valid'] == 17 and not row['complete'] for row in rows))
        self.assertFalse(any(row['sourceStage'] == 'cloudflare-clef-direct/fresh3/P2'
                             for row in rows))
        self.assertTrue(any(row['sourceFamily'] == 'hosted-repeats' and
                            row['repeatPass'] == 'repeat2' and row['condition'] == 'P1' and
                            row['valid'] == 59 and not row['complete'] for row in rows))
        invalid_only = next(row for row in rows if row['sourceFamily'] == 'anyjev-generated-repeats'
                            and row['repeatPass'] == 'fresh1' and row['condition'] == 'P0')
        self.assertEqual(invalid_only['valid'], 0)
        self.assertEqual(invalid_only['savedResponses'], 60)
        self.assertEqual(invalid_only['recordsMeaning'], 'planned denominator')

    def test_request_denominator_and_pricing_basis(self):
        rows = self.catalog['runs']
        codex = next(row for row in rows if row['sourceFamily'] == 'codex-fresh-repeats'
                     and row['repeatPass'] == 'fresh1' and row['condition'] == 'P0')
        self.assertEqual(codex['tokens']['totalRequests'], 6)
        self.assertEqual(codex['tokens']['reportedRequests'], 6)
        self.assertEqual(codex['timing']['totalRequests'], 6)
        jev = next(row for row in rows if row['sourceFamily'] == 'jev-native-prompt-findings'
                   and row['repeatPass'] == 'fresh1' and row['condition'] == 'P0')
        self.assertIsNone(jev['cost']['knownUsd'])
        self.assertAlmostEqual(jev['cost']['estimatedUsd'], 0.005890920)
        typesafe_repeat = next(row for row in rows if row['sourceFamily'] == 'typesafe-repeats'
                               and row['repeatPass'] == 'repeat2' and row['condition'] == 'P0')
        self.assertIsNone(typesafe_repeat['cost']['knownUsd'])
        self.assertIsNotNone(typesafe_repeat['cost']['estimatedUsd'])
        kev = next(row for row in rows if row['sourceFamily'] == 'kev-native-repeats'
                   and row['repeatPass'] == 'fresh1')
        self.assertIsNotNone(kev['cost']['knownUsd'])

    def test_missing_token_and_unknown_charge_are_retained(self):
        row = next(row for row in self.catalog['runs']
                   if row['sourceFamily'] == 'qwen36-off-second-interruption-findings'
                   and row['repeatPass'] == 'fresh1' and row['condition'] == 'P0')
        self.assertEqual(row['tokens']['reportedRequests'], 59)
        self.assertEqual(row['tokens']['totalRequests'], 60)
        self.assertFalse(row['tokens']['complete'])
        self.assertAlmostEqual(row['cost']['unknownUpperBoundUsd'], 0.0299008)
        self.assertEqual(row['cost']['unknownCostCount'], 1)

    def test_direct_flash_is_distinct_from_openrouter_route(self):
        rows = self.catalog['runs']
        flash = [row for row in rows if row['sourceStage'].startswith('cloudflare-clef-flash-direct/')]
        self.assertEqual(len(flash), 7)
        self.assertTrue(all(row['model'] == '@cf/cloudflare/clef-flash' and
                            row['surface'] == 'Cloudflare connected app' for row in flash))
        self.assertFalse(any(row['sourceStage'] == 'cloudflare-clef-flash-direct/fresh1/P0'
                             for row in rows))

    def test_report_drift_and_invalid_scores_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'public-site').mkdir()
            for family in MODULE.FEEDS:
                source = ROOT / 'public-site' / (family + '.json')
                shutil.copy2(source, root / 'public-site' / source.name)
            report = root / 'public-site/typesafe-repeats.json'
            document = json.loads(report.read_text())
            document['series'][0]['passes']['repeat2']['P0']['score']['allFour'] = 61
            report.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                MODULE.build(root)


if __name__ == '__main__':
    unittest.main()
