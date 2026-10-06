"""Fixed-denominator and portable-source checks for the final DeepSeek suffix."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deepseek_low_final_suffix_findings as report


class FinalSuffixFindingsTests(unittest.TestCase):
    def test_scores_and_public_payload(self):
        result = report.build(ROOT)
        series = result['series'][0]
        p2 = series['historicalFirstPass']['P2']
        self.assertEqual((60, 56, 53), (p2['denominator'], p2['valid'], p2['allFour']))
        self.assertEqual({'ok': 56, 'invalid_output': 1, 'service_error': 3},
                         series['finalP2Outcomes'])
        self.assertEqual(['DEV-039', 'DEV-040', 'DEV-049', 'DEV-050'], p2['invalidIds'])
        self.assertEqual([55, 56], [item['sharedValidChanges']['denominator']
                                    for item in series['withinPassComparisons'][1:]])
        self.assertEqual((57, 3), (series['p2ObservedUsage']['prompt_tokens']['observedCount'],
                                  series['p2ObservedUsage']['prompt_tokens']['missingCount']))
        self.assertEqual((57, 3), (series['p2ObservedUsage']['observedCostCount'],
                                  series['p2ObservedUsage']['unknownCostCount']))
        self.assertEqual(60, series['p2ObservedUsage']['clientRequestTimingCount'])
        public = json.dumps(result)
        for private in ('raw_response', 'error_body', 'budgetAccounting', 'child_cap_usd',
                        'master_ledger', 'api_key', 'authorization'):
            self.assertNotIn(private, public)
        self.assertEqual(result, json.loads((ROOT / 'public-site/deepseek-low-final-suffix-findings.json').read_text()))

    def archive(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for source in report.build(ROOT)['sourceBindings']:
            relative = Path(source['path'])
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def test_relocation_requires_no_live_ledger(self):
        root = self.archive()
        self.assertFalse((root / 'results/openrouter-paid-budget.jsonl').exists())
        self.assertEqual(report.build(ROOT), report.build(root))

    def test_tampered_prediction_or_prior_projection_is_rejected(self):
        root = self.archive()
        path = root / report.NEW / 'suffix.records.jsonl'
        rows = report.jsonl(path)
        rows[0]['prediction']['sentiment'] = 'tampered'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(root)
        shutil.copy2(ROOT / report.NEW / 'suffix.records.jsonl', path)
        projection = root / report.PROJECTION
        data = json.loads(projection.read_text())
        data['positions'][50] = {'id': 'DEV-051', 'status': 'ok'}
        projection.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(root)


if __name__ == '__main__':
    unittest.main()
