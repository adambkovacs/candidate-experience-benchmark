"""Offline source and accounting checks for the hosted Qwen ON public report."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_additional_hosted_fresh_repeat_findings as existing
import build_qwen36_on_hosted_authority_v2_findings as report


class QwenHostedFindingsTests(unittest.TestCase):
    def test_existing_series_preserved_and_interrupted_p1_remains_descriptive(self):
        value = report.build(ROOT)
        original = existing.build(ROOT, configuration='openrouter-paid-deepseek-v41-flash-low')
        self.assertEqual(value['series'][:len(original['series'])], original['series'])
        self.assertEqual(len(value['series']), len(original['series']) + 1)
        qwen = value['series'][-1]
        self.assertEqual(qwen['configuration'], report.CONFIG)
        self.assertGreaterEqual(qwen['completedConditions'], 2)
        self.assertFalse(qwen['cleanMatchedThreeEligible'])
        self.assertEqual(qwen['passes']['fresh1']['P0']['score']['allFour'], 54)
        self.assertEqual(qwen['passes']['fresh1']['P0']['score']['valid'], 60)
        composite = qwen['passes']['fresh1']['P1']
        self.assertEqual(composite['status'], 'completed_interrupted_composite')
        self.assertEqual(composite['score']['allFour'], 52)
        self.assertEqual(composite['score']['valid'], 59)
        self.assertEqual(composite['score']['invalidIds'], ['DEV-049'])
        self.assertEqual(composite['usage']['actualCostUsd'], None)
        self.assertEqual(composite['usage']['knownCostUsd'], '0.0696082')
        self.assertEqual(composite['unknownChargeUpperBoundUsd'], '0.0299008')
        p2 = qwen['passes']['fresh1']['P2']
        self.assertEqual(p2['status'], 'completed')
        self.assertEqual((p2['score']['allFour'], p2['score']['valid']), (56, 60))
        self.assertEqual(p2['usage']['knownCostUsd'], '0.0644868')
        self.assertEqual(qwen['withinPassPromptDeltas'][0]['allFour'], 2)
        self.assertEqual(qwen['withinPassPromptDeltas'][0]['scope'],
                         'descriptive matched first pass; interrupted P1 excluded')
        self.assertIn({'pass': 'fresh1', 'condition': 'P1',
                       'status': 'interrupted_descriptive'}, qwen['missingPasses'])
        paths = {item['path'] for item in qwen['sourceBindings']}
        self.assertIn(str(report.CONT / 'budget-before-reconciliation.jsonl'), paths)
        self.assertNotIn(str(report.CONT / 'budget-qwen36-on-hosted-p1-unsent-v1.jsonl'), paths)
        self.assertNotIn(str(report.BASE / 'budget-qwen36-on-hosted-authority-v2-fresh123.jsonl'), paths)
        self.assertIn(str(report.REMAINING / 'budget-at-fresh1-p2-closure.jsonl'), paths)
        self.assertNotIn(str(report.REMAINING / 'budget-qwen36-on-remaining-hosted-v1.jsonl'), paths)

    def test_remaining_phase_rejects_changed_prediction_and_snapshot(self):
        target = report.REMAINING / report.CONFIG / 'fresh1/P2/development.attempts.jsonl'
        original_rows = report.rows
        def changed(root, relative):
            values = original_rows(root, relative)
            if relative == target:
                values = copy.deepcopy(values)
                values[0]['prediction']['sentiment'] = 'negative'
            return values
        with patch.object(report, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'strict output differs'):
                report.build(ROOT)
        original_sha = report.sha
        snapshot = ROOT / report.REMAINING / 'budget-at-fresh1-p2-closure.jsonl'
        with patch.object(report, 'sha', side_effect=lambda path:
                          '0' * 64 if Path(path) == snapshot else original_sha(path)):
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                report.build(ROOT)

    def test_remaining_phase_without_closure_receipt_earns_no_credit(self):
        missing = {report.REMAINING / report.CONFIG / repeat / condition /
                   'closure.review.json' for repeat, condition in report.REMAINING_STAGES}
        original_file = report.file
        def without_closure(root, relative):
            if relative in missing:
                return Path('/nonexistent-qwen-closure-review.json')
            return original_file(root, relative)
        with patch.object(report, 'file', side_effect=without_closure):
            value = report.build(ROOT)['series'][-1]
        self.assertEqual(value['completedConditions'], 1)
        self.assertNotIn('P2', value['passes']['fresh1'])
        self.assertEqual(value['passes']['fresh1']['P1']['status'],
                         'completed_interrupted_composite')

    def test_changed_saved_prediction_rejected(self):
        original = report.rows
        target = report.BASE / 'fresh1/P0/development.attempts.jsonl'
        def changed(root, relative):
            values = original(root, relative)
            if relative == target:
                values = copy.deepcopy(values)
                values[0]['prediction']['sentiment'] = 'negative'
            return values
        with patch.object(report, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'score or cost differs'):
                report.build(ROOT)

    def test_changed_archived_child_hash_rejected(self):
        original = report.sha
        target = report.CONT / 'budget-before-reconciliation.jsonl'
        with patch.object(report, 'sha', side_effect=lambda path:
                          '0' * 64 if Path(path) == ROOT / target else original(path)):
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                report.build(ROOT)

    def test_published_report_preserves_qwen_and_prior_series(self):
        published = json.loads((ROOT / 'public-site/additional-hosted-fresh-repeats.json').read_text())
        base = report.build(ROOT)
        self.assertEqual(published['series'][:len(base['series'])], base['series'])
        self.assertEqual(published['availableConfigurations'][:len(base['availableConfigurations'])],
                         base['availableConfigurations'])
        self.assertEqual(published['sourceBindings'][:len(base['sourceBindings'])],
                         base['sourceBindings'])


if __name__ == '__main__':
    unittest.main()
