"""Read-only publication checks for the interrupted Gemma26 continuation."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_gemma26_continuation_findings as report


class ContinuationFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = report.build(report.ROOT)

    def clean_snapshot(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for source in self.snapshot['sourceBindings']:
            relative = Path(source['path'])
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(report.ROOT / relative, dest)
        return temp, root

    def test_fixed_denominator_failure_and_missing_phases(self):
        value = self.snapshot
        self.assertEqual(value['method'], 'descriptive-interrupted-series-continuation')
        self.assertIs(value['cleanMatchedThreeEligible'], False)
        self.assertEqual(value['denominator'], 60)
        self.assertEqual(value['completedConditions'] + len(value['missingPasses']), 9)
        self.assertEqual({(fresh, condition): phase['score']['allFour']
                          for fresh, entries in value['passes'].items()
                          for condition, phase in entries.items()},
                         {('fresh1', 'P0'): 59, ('fresh1', 'P1'): 58,
                          ('fresh1', 'P2'): 57, ('fresh2', 'P1'): 58,
                          ('fresh2', 'P2'): 56})
        self.assertNotIn('P0', value['passes']['fresh2'])
        self.assertEqual(len(value['stoppedPhases']), 1)
        stopped = value['stoppedPhases'][0]
        self.assertEqual((stopped['pass'], stopped['condition']), ('fresh2', 'P0'))
        self.assertEqual(stopped['status'], 'stopped_unscored')
        self.assertIsNone(stopped['score'])
        self.assertEqual(stopped['attempted'], 2)
        self.assertEqual(stopped['validOutputCount'], 1)
        self.assertEqual(stopped['failedId'], 'DEV-002')
        self.assertEqual(stopped['neverSentCount'], 58)
        self.assertEqual(stopped['neverSentIds'], report.IDS[2:])
        self.assertEqual(stopped['usage']['unknownCostCount'], 1)
        self.assertIsNone(stopped['usage']['actualCostUsd'])
        self.assertEqual(stopped['usage']['unknownCostUpperBoundUsd'], '0.01974272')
        self.assertIn({'pass': 'fresh2', 'condition': 'P0',
                       'status': 'stopped_unscored'}, value['missingPasses'])
        p2 = value['passes']['fresh1']['P2']
        self.assertEqual(p2['status'], 'completed_interrupted')
        self.assertEqual(p2['score']['outcomes']['service_error'], 1)
        self.assertEqual(p2['score']['outcomes']['never_sent'], 0)
        self.assertEqual(p2['score']['saved'], 60)
        self.assertEqual(p2['score']['valid'], 59)
        self.assertEqual(p2['score']['allFour'], 57)
        self.assertEqual(p2['score']['denominator'], 60)
        self.assertEqual(p2['usage']['unknownCostCount'], 1)
        self.assertIsNone(p2['usage']['actualCostUsd'])
        self.assertEqual(p2['usage']['unknownCostUpperBoundUsd'], '0.01974272')
        self.assertEqual(p2['usage']['tokenAvailability']['prompt_tokens']['missingCount'], 1)
        self.assertEqual(p2['usage']['tokenAvailability']['providerReportedReasoningTokens']['missingCount'], 1)
        self.assertNotIn('DEV-007', p2['score']['validIds'])
        rendered = json.dumps(value)
        self.assertNotIn('error_body', rendered)
        self.assertNotIn('user_id', rendered)
        self.assertNotIn('budget.jsonl', rendered)
        self.assertNotIn('results/openrouter-paid-budget', rendered)

    def test_clean_archive_rebuild_and_prefix_tamper_refused(self):
        temp, root = self.clean_snapshot()
        with temp:
            self.assertEqual(report.build(root), self.snapshot)
            prefix = root / report.CONT / 'public-prefix-v1/development.attempts.jsonl'
            prefix.write_bytes(prefix.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                report.build(root)

    def test_closed_stage_tamper_and_missing_predecessor_refused(self):
        temp, root = self.clean_snapshot()
        with temp:
            path = root / report.CONT / 'fresh2/P1/development.journal.jsonl'
            if not path.exists():
                self.skipTest('fresh2/P1 is not in this immutable cutoff')
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events[-1]['event'] = 'phase_stopped'
            path.write_text(''.join(json.dumps(x) + '\n' for x in events))
            with self.assertRaises(ValueError):
                report.build(root)

    def test_score_distinguishes_unsent_from_invalid(self):
        labels = {rid: {key: 'no' for key in report.KEYS} for rid in report.IDS}
        scored = report.score([{'id': 'DEV-001', 'status': 'invalid_output'},
                               {'id': 'DEV-002', 'status': 'service_error'}], labels)
        self.assertEqual(scored['outcomes'], {'valid': 0, 'invalid_output': 1,
                                              'service_error': 1, 'never_sent': 58})
        self.assertEqual(scored['scoreKind'], 'fixed_60_partial_tally')

    def test_closed_stage_cost_must_match_raw_response_and_journal(self):
        temp, root = self.clean_snapshot()
        with temp:
            path = root / report.CONT / 'fresh1/P2/suffix.attempts.jsonl'
            saved = [json.loads(line) for line in path.read_text().splitlines()]
            saved[0]['observed_cost_usd'] = '0.00000001'
            path.write_text(''.join(json.dumps(row) + '\n' for row in saved))
            with self.assertRaises(ValueError):
                report.build(root)

    def test_stopped_phase_terminal_evidence_must_remain_bound(self):
        temp, root = self.clean_snapshot()
        with temp:
            path = root / report.CONT / 'fresh2/P0/development.journal.jsonl'
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events[-1]['id'] = 'DEV-003'
            path.write_text(''.join(json.dumps(row) + '\n' for row in events))
            with self.assertRaises(ValueError):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
