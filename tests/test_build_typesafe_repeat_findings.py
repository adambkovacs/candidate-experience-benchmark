import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_typesafe_repeat_findings as report
import typesafe_repeat_execution as execution


class TypeSafeRepeatFindingsTests(unittest.TestCase):
    def test_first_attempt_history_and_shared_valid_flips(self):
        series = report.build()['series'][0]
        self.assertEqual(series['completedConditions'], 9)
        self.assertEqual(series['missingPasses'], [])
        self.assertEqual(series['passes']['original']['P0']['score']['outcomes']['service_error'], 1)
        self.assertEqual(series['passes']['original']['P0']['score']['invalidIds'], ['DEV-046'])
        self.assertEqual(series['passes']['original']['P1']['score']['invalidIds'], ['DEV-053'])
        self.assertEqual(series['passes']['original']['P2']['score']['invalidIds'], ['DEV-040'])
        self.assertEqual(series['passes']['repeat2']['P0']['score']['invalidIds'], ['DEV-040', 'DEV-055'])
        self.assertEqual(series['passes']['repeat3']['P0']['score']['valid'], 60)
        self.assertEqual(series['changesAcrossThreePasses']['P0']['denominator'], 57)
        self.assertEqual(series['changesAcrossThreePasses']['P0']['excludedIds'],
                         ['DEV-040', 'DEV-046', 'DEV-055'])
        flip = next(x for x in series['pairwiseFlips'] if x['condition'] == 'P0' and
                    x['from'] == 'original' and x['to'] == 'repeat2')
        self.assertEqual(flip['denominator'], 57)
        self.assertEqual(flip['excludedIds'], ['DEV-040', 'DEV-046', 'DEV-055'])
        self.assertIsNone(series['passes']['repeat2']['P0']['usage']['actualCostUsd'])
        self.assertIsNone(series['passes']['repeat2']['P0']['usage']['inferenceSeconds'])
        self.assertEqual(series['passes']['original']['P0']['usage']['unknownCostCount'], 1)
        self.assertEqual(series['budget']['historicalUnknownReservationUsd'], '0.002123688')
        self.assertEqual(series['budget']['pendingAttemptCount'], 1)
        self.assertEqual(series['method'], 'native-choice')

    def test_saved_raw_status_tampering_is_rejected(self):
        original = report.rows
        target = execution.stage_paths(execution.BASE, 'repeat2', 'P0', 'development', 0)['attempts.jsonl']
        def changed(path):
            value = original(path)
            if Path(path) == target:
                value = copy.deepcopy(value)
                value[0]['status'] = 'service_error'
            return value
        with mock.patch.object(report, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'outcome differs'):
                report.build()

    def test_saved_usage_or_ledger_settlement_tampering_is_rejected(self):
        original = report.rows
        target = execution.stage_paths(execution.BASE, 'repeat2', 'P1', 'development', 0)['attempts.jsonl']
        def changed_usage(path):
            value = original(path)
            if Path(path) == target:
                value = copy.deepcopy(value)
                value[0]['reported_input_tokens'] += 1
            return value
        with mock.patch.object(report, 'rows', side_effect=changed_usage):
            with self.assertRaisesRegex(ValueError, 'usage fields'):
                report.build()
        ledger = report.native.LEDGER
        first_attempt = original(target)[0]['budget_attempt_id']
        def changed_ledger(path):
            value = original(path)
            if Path(path) == ledger:
                value = copy.deepcopy(value)
                next(x for x in value if x['event'] == 'settle' and x['attempt_id'] == first_attempt)['usd'] = '0.9'
            return value
        with mock.patch.object(report, 'rows', side_effect=changed_ledger):
            with self.assertRaisesRegex(ValueError, 'budget evidence'):
                report.build()

    def test_open_phase_is_excluded_from_report(self):
        original = report.phase_status
        def phase(repeat, condition, name):
            if (repeat, condition, name) == ('repeat3', 'P1', 'development'):
                return 'open'
            return original(repeat, condition, name)
        with mock.patch.object(report, 'phase_status', side_effect=phase):
            series = report.build()['series'][0]
        self.assertEqual(series['completedConditions'], 8)
        self.assertEqual(series['missingPasses'],
                         [{'pass': 'repeat3', 'condition': 'P1',
                           'status': 'development_open_or_incomplete'}])
        self.assertNotIn('P1', series['passes']['repeat3'])
        self.assertNotIn('P1', series['changesAcrossThreePasses'])

    def test_check_mode_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'jev-report.json'
            report.main(['--output', str(target)])
            report.main(['--output', str(target), '--check'])
            target.write_text(json.dumps({'stale': True}) + '\n')
            with self.assertRaisesRegex(ValueError, 'Stale'):
                report.main(['--output', str(target), '--check'])


if __name__ == '__main__':
    unittest.main()
