"""Portable, source-bound checks for the DEV-050 public interruption view."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import build_deepseek_low_third_interruption_findings as report


class ThirdInterruptionTests(unittest.TestCase):
    def test_committed_archive_is_unscored_and_sanitized(self):
        result = report.build(REPO)
        series = result['series'][0]
        self.assertEqual(2, series['completedConditions'])
        self.assertNotIn('P2', series['passes']['fresh1'])
        self.assertEqual('stopped_at_DEV-050_unscored', series['missingPasses'][0]['status'])
        self.assertEqual(40, series['originalInterruptionCheckpoint']['attemptedAtInterruption'])
        self.assertEqual(49, series['secondInterruptionCheckpoint']['attemptedAtSecondInterruption'])
        third = series['thirdInterruptionCheckpoint']
        self.assertEqual(50, third['attemptedAtThirdInterruption'])
        self.assertEqual(10, third['neverSentAtThirdInterruption'])
        self.assertEqual({'ok': 46, 'invalid_output': 1, 'service_error': 3,
                          'never_sent': 10}, third['outcomes'])
        self.assertEqual(['DEV-040', 'DEV-049', 'DEV-050'], third['serviceErrorIds'])
        self.assertIsNone(third['score'])
        public = json.dumps(result)
        for forbidden in ('budgetAccountingCumulative', 'sealedChild', 'child_cap_usd',
                          'unused_allocation_released_usd', 'error_body', 'raw_response',
                          '"request":', '"feedback":', 'user_id'):
            self.assertNotIn(forbidden, public)

    def relocated(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        manifest = json.loads((REPO / report.NEW / 'manifest.json').read_text())
        paths = [report.NEW / name for name in (
            'manifest.json', 'phase-03-suffix.public.json',
            *report.STAGE_SHA.keys(),
            'budget-' + manifest['partition_id'] + '.jsonl')]
        paths.append(report.prior.NEW / 'phase-03-suffix.public.json')
        for name, source in manifest['source_bindings'].items():
            if name not in report.PRIVATE_SOURCES:
                paths.append(Path(source['path']))
        paths.append(Path(manifest['controller']['path']))
        for relative in set(paths):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        original = report.prior.build(REPO)
        return root, original

    def test_relocated_archive_does_not_need_original_absolute_checkout_or_private_sources(self):
        root, original = self.relocated()
        self.assertFalse((root / report.prior.BASE / 'phase-03-development.raw.jsonl').exists())
        with patch.object(report.prior, 'build', return_value=copy.deepcopy(original)):
            result = report.build(root)
        self.assertEqual(50, result['series'][0]['thirdInterruptionCheckpoint'][
            'attemptedAtThirdInterruption'])

    def test_snapshot_and_stage_tamper_are_rejected(self):
        root, original = self.relocated()
        snapshot = root / report.NEW / 'phase-03-suffix.public.json'
        data = json.loads(snapshot.read_text())
        data['positions'][49]['status'] = 'ok'
        snapshot.write_text(json.dumps(data))
        with patch.object(report.prior, 'build', return_value=copy.deepcopy(original)):
            with self.assertRaisesRegex(ValueError, 'Source hash differs'):
                report.build(root)
        shutil.copy2(REPO / report.NEW / 'phase-03-suffix.public.json', snapshot)
        record = root / report.NEW / 'phase-03-suffix.records.jsonl'
        data = json.loads(record.read_text())
        data['reference_labels_read'] = True
        record.write_text(json.dumps(data))
        with patch.object(report.prior, 'build', return_value=copy.deepcopy(original)):
            with self.assertRaisesRegex(ValueError, 'Source hash differs'):
                report.build(root)

    def test_original_absolute_budget_metadata_is_checked_without_opening_live_master(self):
        root, original = self.relocated()
        path = root / report.NEW / 'budget.json'
        data = json.loads(path.read_text())
        data['partitions'][0]['child_ledger'] = '/somewhere/else.jsonl'
        path.write_text(json.dumps(data))
        with patch.object(report.prior, 'build', return_value=copy.deepcopy(original)):
            with self.assertRaisesRegex(ValueError, 'Source hash differs'):
                report.build(root)

    def test_earlier_prediction_drift_is_rejected_even_with_updated_snapshot_hash(self):
        root, original = self.relocated()
        path = root / report.NEW / 'phase-03-suffix.public.json'
        data = json.loads(path.read_text())
        data['positions'][0]['prediction']['sentiment'] = 'negative'
        path.write_text(json.dumps(data))
        with patch.object(report.prior, 'build', return_value=copy.deepcopy(original)), \
                patch.object(report, 'SNAPSHOT_SHA', report._sha(path)):
            with self.assertRaisesRegex(ValueError, 'Earlier public positions changed'):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
