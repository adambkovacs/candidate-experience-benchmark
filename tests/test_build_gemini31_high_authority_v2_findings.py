"""Offline checks for the source-bound Gemini high authority report wrapper."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_gemini_repeat_findings as frozen_report
import build_gemini31_high_authority_v2_findings as report


class GeminiAuthorityReportTests(unittest.TestCase):
    def test_existing_series_preserved_and_closed_authority_phases_bound(self):
        value = report.build(ROOT)
        original = frozen_report.build(ROOT, include_recovered_low=True)
        self.assertEqual(value['schema'], original['schema'])
        self.assertEqual(value['series'][:len(original['series'])], original['series'])
        self.assertEqual(len(value['series']), len(original['series']) + 1)
        self.assertEqual(len({item['configuration'] for item in value['series']}), len(value['series']))
        high = value['series'][-1]
        self.assertEqual(high['configuration'], report.CONFIG)
        self.assertEqual(high['denominator'], 60)
        self.assertEqual(high['plannedConditions'], 9)
        self.assertEqual([high['passes']['repeat2'][c]['score']['allFour'] for c in report.CONDITIONS],
                         [56, 56, 56])
        for condition in report.CONDITIONS:
            self.assertEqual(high['passes']['repeat2'][condition]['score']['valid'], 60)
        bindings = {item['path']: item['sha256'] for item in high['sourceBindings']}
        for condition in report.CONDITIONS:
            path = report.BASE / report.CONFIG / 'repeat2' / condition / 'closure.review.json'
            self.assertEqual(bindings[str(path)], frozen_report._sha(ROOT / path))
        for condition in report.CONDITIONS:
            path = report.BASE / report.CONFIG / 'repeat3' / condition / 'closure.review.json'
            if (ROOT / path).exists():
                self.assertEqual(bindings[str(path)], frozen_report._sha(ROOT / path))
                self.assertEqual(high['passes']['repeat3'][condition]['completionStatus'], 'complete')
            else:
                self.assertNotIn(condition, high['passes']['repeat3'])
        self.assertNotIn('results/openrouter-paid-budget.jsonl', bindings)
        self.assertFalse(any(name.endswith('budget-g31-pro-high-repeat-authority-v2.jsonl')
                             for name in bindings))

    def test_unreviewed_repeat3_development_is_not_published(self):
        original = report._closure
        with patch.object(report, '_closure', side_effect=lambda root, repeat, condition:
                          None if repeat == 'repeat3' else original(root, repeat, condition)):
            high = report.build(ROOT)['series'][-1]
        self.assertEqual(high['completedConditions'], 6)
        self.assertEqual(high['passes']['repeat3'], {})

    def test_missing_required_repeat2_closure_refused(self):
        original = report._closure
        with patch.object(report, '_closure', side_effect=lambda root, repeat, condition:
                          None if (repeat, condition) == ('repeat2', 'P0') else
                          original(root, repeat, condition)):
            with self.assertRaisesRegex(ValueError, 'repeat2 closure is missing'):
                report.build(ROOT)

    def test_duplicate_configuration_refused(self):
        with patch.object(frozen_report, 'build', return_value={
                'schema': 'gemini-repeat-series-v1',
                'series': [{'configuration': report.CONFIG}]}):
            with self.assertRaisesRegex(ValueError, 'duplicates a published series'):
                report.build(ROOT)

    def test_unapproved_closure_receipt_refused(self):
        relative = report.BASE / report.CONFIG / 'repeat2/P0/closure.review.json'
        receipt = json.loads((ROOT / relative).read_text())
        receipt['checks']['raw_base64_body_equals_attempt_raw_response'] = False
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / 'closure.review.json'
            changed.write_text(json.dumps(receipt) + '\n')
            original_file = report._file
            with patch.object(report, '_file', side_effect=lambda root, path:
                              changed if Path(path) == relative else original_file(root, path)):
                with self.assertRaisesRegex(ValueError, 'not approved and complete'):
                    report._closure(ROOT, 'repeat2', 'P0')

    def test_published_bytes_match_wrapper(self):
        published = json.loads((ROOT / 'public-site/gemini-repeats.json').read_text())
        self.assertEqual(published, report.build(ROOT))


if __name__ == '__main__':
    unittest.main()
