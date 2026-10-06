"""Closed DeepSeek high P0 must remain source-bound and retain its invalid result."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_qwen36_on_hosted_authority_v2_findings as prior
import build_deepseek_high_authority_v3_findings as report


class DeepSeekHighFindingsTests(unittest.TestCase):
    def test_existing_series_preserved_and_p0_is_closed_with_invalid(self):
        value = report.build(ROOT)
        previous = prior.build(ROOT)
        self.assertEqual(value['series'][:len(previous['series'])], previous['series'])
        self.assertEqual(len(value['series']), len(previous['series']) + 1)
        item = value['series'][-1]
        self.assertEqual(item['configuration'], report.CONFIG)
        self.assertEqual(item['completedConditions'], 1)
        self.assertEqual(item['passes']['fresh1'].keys(), {'P0'})
        phase = item['passes']['fresh1']['P0']
        self.assertEqual(phase['status'], 'completed_with_intrinsic_invalid')
        self.assertEqual(phase['score']['allFour'], 57)
        self.assertEqual(phase['score']['valid'], 59)
        self.assertEqual(phase['score']['invalidIds'], ['DEV-030'])
        self.assertEqual(phase['score']['outcomes'], {'ok': 59, 'invalid_output': 1})
        self.assertEqual(phase['usage']['actualCostUsd'], '0.034324790897')
        paths = {x['path'] for x in item['sourceBindings']}
        self.assertIn(str(report.FOLDER / 'closure-ledger-snapshot.jsonl'), paths)
        self.assertNotIn(str(report.BASE / 'budget-deepseek-high-authority-v3-fresh123.jsonl'), paths)
        self.assertFalse(any('/fresh1/P1/development.' in path for path in paths))

    def test_missing_immutable_snapshot_rejected(self):
        original = report.existing.bind
        snapshot = report.FOLDER / 'closure-ledger-snapshot.jsonl'
        def changed(root, relative, bindings, expected=None):
            if str(relative) == str(snapshot):
                raise ValueError('DeepSeek report source hash differs: snapshot')
            return original(root, relative, bindings, expected)
        with patch.object(report.existing, 'bind', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'snapshot'):
                report.build(ROOT)

    def test_invalid_prediction_cannot_be_silently_repaired(self):
        original = report.existing.rows
        target = report.FOLDER / 'development.attempts.jsonl'
        def changed(root, relative):
            values = original(root, relative)
            if relative == target:
                values[29]['status'] = 'ok'
            return values
        with patch.object(report.existing, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'classification'):
                report.build(ROOT)

    def test_published_report_rebuilds(self):
        published = json.loads((ROOT / 'public-site/additional-hosted-fresh-repeats.json').read_text())
        self.assertEqual(published, report.build(ROOT))


if __name__ == '__main__':
    unittest.main()
