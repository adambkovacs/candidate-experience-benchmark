"""Regression checks for the saved, source-bound first-P0 comparison."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import analyze_cross_category_v1 as cross  # noqa: E402


class CrossCategoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset, cls.findings, cls.plan = cross.build()

    def test_full_declared_first_p0_selector_and_exclusions(self):
        self.assertEqual(self.dataset['counts'], {
            'historicalGeneral': 117, 'declaredGeneral': 32,
            'native': 7, 'excludedP0Rows': 211,
            'excludedHistorical': 9, 'excludedCatalog': 202,
        })
        self.assertEqual(len(self.dataset['runs']), 156)
        self.assertEqual(len({row['runId'] for row in self.dataset['runs']}), 156)
        self.assertTrue(self.dataset['selectionRule']['noScoreSelection'])
        excluded = {row['runId']: row['reason'] for row in self.dataset['exclusions']}
        self.assertIn('recovery composite', excluded['sonnet5-low-with-retry'])
        self.assertIn('development-fold-fitted', excluded['anyjev-qwen06-l2'])
        self.assertIn('development-fold-fitted', excluded['extended-anyjev-qwen06-l1-direct-native-cv5-fresh1-p0'])
        self.assertIn('task-fine-tuned', excluded['alex-openjev08'])
        self.assertIn('rules', excluded['rules-v1'])
        self.assertEqual(Counter(row['stratum'] for row in self.dataset['runs']), {
            'historical-first-P0': 117, 'declared-fresh1-P0': 32, 'native-first-P0': 7,
        })

    def test_all_case_positions_and_paired_tallies_reconcile(self):
        expected = {f'DEV-{number:03d}' for number in range(1, 61)}
        for run in self.dataset['runs']:
            with self.subTest(run=run['runId']):
                rows = run['cases']
                self.assertEqual({row['id'] for row in rows}, expected)
                self.assertEqual(len(rows), 60)
                self.assertEqual(sum(row['allFourMatch'] is not None for row in rows), run['scores']['valid'])
                self.assertEqual(sum(row['allFourMatch'] is True for row in rows), run['scores']['all_four'])
                self.assertEqual(sum(run['outcomes'].values()), 60)
                if run['category'] == 'general-llm':
                    self.assertEqual(len(run['pairedWithNative']), 7)
                    for tally in run['pairedWithNative'].values():
                        self.assertEqual(sum(tally.values()), 60)

    def test_failures_and_cost_missingness_are_not_repaired(self):
        rows = {row['runId']: row for row in self.dataset['runs']}
        invalid = rows['extended-anyjev-qwen06-generated-fresh-three-fresh1-p0']
        self.assertEqual(invalid['scores']['valid'], 0)
        self.assertEqual(invalid['outcomes'], {'invalid_output': 60})
        self.assertTrue(all(row['prediction'] is None for row in invalid['cases']))
        qwen = rows['extended-openrouter-paid-qwen36-35b-a3b-off-fresh1-p0']
        self.assertEqual(qwen['scores']['valid'], 59)
        self.assertFalse(qwen['complete'])
        self.assertIsNone(qwen['savedResponses'])
        self.assertEqual(qwen['controls']['cost']['unknownUpperBoundUsd'], 0.0299008)
        self.assertEqual(qwen['controls']['route'], 'OpenRouter · akashml/fp8')
        self.assertIsNone(rows['sonnet5-low-first-pass']['controls']['cost']['observedUsd'])
        self.assertEqual(rows['sonnet5-low-first-pass']['scores']['valid'], 59)
        gemini = rows['gemini38-low-p0-openrouter-v2']
        self.assertEqual(gemini['sourceUrl'], cross.GITHUB + str(cross.BASE_SOURCE))
        self.assertEqual(gemini['sourceCaseKey'], gemini['runId'])
        self.assertIn('p0-routing-probe', gemini['runEvidenceLeadUrl'])
        self.assertIn('not asserted', gemini['runEvidenceLeadCompleteness'])

    def test_source_hashes_and_native_scores_match_saved_evidence(self):
        for path, value in self.dataset['sourceSha256'].items():
            with self.subTest(path=path):
                self.assertEqual(sha256((ROOT / path).read_bytes()).hexdigest(), value)
        self.assertEqual(self.dataset['sourceSha256'], self.plan['sourceSha256'])
        native = [row for row in self.dataset['runs'] if row['category'] == 'dedicated-decision']
        self.assertEqual([row['scores']['all_four'] for row in native], [43, 45, 55, 54, 45, 49, 54])
        for row in self.dataset['runs']:
            path = cross.source_path(row['sourceUrl'])
            self.assertEqual(sha256((ROOT / path).read_bytes()).hexdigest(), row['sourceSha256'])
            if row['sourceReportUrl']:
                report = cross.source_path(row['sourceReportUrl'])
                self.assertEqual(sha256((ROOT / report).read_bytes()).hexdigest(), row['sourceReportSha256'])

    def test_joined_findings_are_computed_and_keep_case_denominators(self):
        cases = {row['id']: row['byStratum'] for row in self.dataset['caseSummaries']}
        all_native_missed = [ident for ident, strata in cases.items()
                             if strata['native-first-P0']['allFourMatches'] == 0]
        self.assertEqual(all_native_missed, ['DEV-029', 'DEV-030'])
        self.assertEqual(cases['DEV-029']['historical-first-P0']['allFourMatches'], 89)
        self.assertEqual(cases['DEV-029']['historical-first-P0']['validOutputs'], 113)
        self.assertEqual(cases['DEV-030']['declared-fresh1-P0']['allFourMatches'], 8)
        self.assertEqual(cases['DEV-030']['declared-fresh1-P0']['configurationRows'], 32)
        self.assertIn('| cloudflare/clef | Historical P0 | 76 | 7 | 34 |', self.findings)
        self.assertIn('| cloudflare/clef | Declared fresh1/pass1 P0 | 11 | 2 | 19 |', self.findings)
        self.assertIn('The first equal-total but different-case pair in fixed source order', self.findings)
        self.assertIn('including 4 where the general run had no usable answer', self.findings)
        self.assertIn('not the full specialist roster', self.findings)
        self.assertIn('(202 catalog, 9 historical)', self.findings)
        self.assertIn('can point to one probe or batch', self.findings)

    def test_validity_is_required_before_any_reference_match(self):
        labels = {field: 'no' for field in cross.FIELDS}
        references = {f'DEV-{number:03d}': {'proposed_labels': labels}
                      for number in range(1, 61)}
        rows = [{'id': ident, 'status': 'invalid_output' if ident == 'DEV-001' else 'ok',
                 'prediction': labels} for ident in references]
        cases, score, outcomes = cross.case_rows(rows, references, {'ok'})
        self.assertEqual(score['valid'], 59)
        self.assertEqual(score['all_four'], 59)
        self.assertIsNone(cases[0]['prediction'])
        self.assertTrue(cases[0]['unusableSourcePredictionPresent'])
        self.assertEqual(outcomes, {'invalid_output': 1, 'ok': 59})

    def test_saved_outputs_are_current(self):
        outputs = {
            ROOT / 'results/cross-category-v1/dataset.json': json.dumps(self.dataset, indent=2, ensure_ascii=False) + '\n',
            ROOT / 'results/cross-category-v1/plan.json': json.dumps(self.plan, indent=2, ensure_ascii=False) + '\n',
            ROOT / 'results/cross-category-v1/findings.md': self.findings,
        }
        for path, expected in outputs.items():
            self.assertEqual(path.read_text(), expected)


if __name__ == '__main__':
    unittest.main()
