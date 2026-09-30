import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_kev_native_findings as report


class KevNativeFindings(unittest.TestCase):
    def test_closed_first_and_pending_successors(self):
        with tempfile.TemporaryDirectory() as temp:
            result = report.build(repeat_base=Path(temp))
        self.assertEqual(result['completedPasses'], 1)
        first = result['passes']['fresh1']
        self.assertEqual(first['score']['denominator'], 60)
        self.assertEqual(first['score']['valid'], 60)
        self.assertEqual(first['usage']['actualProviderCostUsd'], '0.004703412')
        self.assertEqual(first['usage']['inputTokens'], 111986)
        self.assertEqual(first['usage']['outputTokens'], 17350)
        self.assertEqual(result['passes']['fresh2']['completionStatus'], 'pending')
        self.assertEqual(result['passes']['fresh3']['completionStatus'], 'pending')
        for key, value in first['score']['fields'].items():
            self.assertEqual(sum(sum(row.values()) for row in first['confusionCounts'][key].values()), 60)
            self.assertEqual(sum(value for value in first['referenceClassCounts'][key].values()), 60)
            self.assertEqual(sum(v.get('correct', 0) + v.get('wrong', 0) for v in first['reportedConfidenceBins'][key].values()), 60)
            self.assertEqual(first['reportedConfidenceThresholds'][key]['0.7']['covered'],
                             first['reportedConfidenceThresholds'][key]['0.7']['correct'] +
                             first['reportedConfidenceThresholds'][key]['0.7']['wrong'])
            self.assertEqual(value, sum(first['confusionCounts'][key][label].get(label, 0)
                                        for label in first['confusionCounts'][key]))

    def test_actual_two_closed_and_audited_interruption(self):
        result = report.build()
        self.assertEqual(result['completedPasses'], 2)
        self.assertEqual(result['repeatComparisons']['fresh1_to_fresh2']['recordsWithIdenticalFourFields'], 60)
        self.assertEqual(result['passes']['fresh2']['score']['allFour'], 48)
        third = result['passes']['fresh3']
        self.assertEqual(third['completionStatus'], 'interrupted')
        self.assertIsNone(third['score'])
        self.assertEqual(third['outcomes'], {'valid': 59, 'transportErrorUnknownOutcome': 1,
                                            'neverSent': 0})
        self.assertEqual(third['continuationStatus'], 'closed')
        self.assertEqual(third['knownActualProviderCostUsd'], '0.004624830')
        self.assertEqual(third['unknownCostReservationUsd'], '0.000344064')
        self.assertEqual(third['usage']['inputTokens'], 110115)
        self.assertEqual(third['usage']['outputTokens'], 17062)
        self.assertEqual(third['usage']['clientRequestSeconds']['total'], 118.75626029)
        self.assertEqual(third['usage']['clientRequestSeconds']['unknownAttempt'], 60.435302333)
        self.assertEqual(third['tail']['valid'], 34)
        self.assertEqual(third['tail']['usage']['actualProviderCostUsd'], '0.002665572')
        self.assertEqual(third['tail']['usage']['inputTokens'], 63466)
        self.assertEqual(third['tail']['usage']['outputTokens'], 9841)

    def test_absent_and_live_tail_remain_unscored_prefix_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            absent = report.build(tail_base=base)
            third = absent['passes']['fresh3']
            self.assertEqual(third['continuationStatus'], 'not_started')
            self.assertEqual(third['outcomes'], {'valid': 25, 'transportErrorUnknownOutcome': 1,
                                                 'neverSent': 34})
            self.assertEqual(third['outcomesAsOf'], 'original-interruption')
            self.assertIsNone(third['score'])
            (base / 'attempts.jsonl').write_text('{"stage":"reserved"}\n')
            live = report.build(tail_base=base)['passes']['fresh3']
            self.assertEqual(live['continuationStatus'], 'running_unscored')
            self.assertEqual(live['outcomesAsOf'], 'original-interruption')
            self.assertIsNone(live['score'])

    def test_tail_raw_tamper_rejected_even_with_rebound_completion_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            tail = Path(temp) / 'tail'
            shutil.copytree(report.TAIL, tail)
            attempts = tail / 'attempts.jsonl'
            lines = attempts.read_text().splitlines()
            row = json.loads(lines[1])
            row['body']['answers']['sentiment']['choice'] = 'negative'
            lines[1] = json.dumps(row)
            attempts.write_text('\n'.join(lines) + '\n')
            completion = json.loads((tail / 'completion.json').read_text())
            completion['attempts_sha256'] = report.smoke.sha(attempts.read_bytes())
            (tail / 'completion.json').write_text(json.dumps(completion))
            with self.assertRaisesRegex(ValueError, 'native raw response differs'):
                report.build(tail_base=tail)

    def test_tail_ledger_settlement_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / 'budget.jsonl'
            events = [json.loads(line) for line in report.LEDGER_PATH.read_text().splitlines()]
            attempt = next(event['attempt_id'] for event in events if event.get('event') == 'reserve'
                and event.get('record_id') == report.continuation.PASS_ID + ':DEV-027')
            settle = next(event for event in events if event.get('event') == 'settle'
                and event.get('attempt_id') == attempt)
            settle['usd'] = '0.000000001'
            ledger.write_text('\n'.join(json.dumps(event) for event in events) + '\n')
            with self.assertRaisesRegex(ValueError, 'tail ledger settlement differs'):
                report.build(ledger_path=ledger)

    def test_relocated_prefix_and_tail_keep_historical_ledger_path(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / 'export' / 'results' / 'route-audits'
            original = base / 'decision-kev-repeats-20260930' / 'fresh3'
            tail = base / 'kev-fresh3-continuation-20260930'
            original.parent.mkdir(parents=True)
            shutil.copytree(report.REPEATS / 'fresh3', original)
            shutil.copytree(report.TAIL, tail)
            ledger = Path(temp) / 'budget.jsonl'
            shutil.copyfile(report.LEDGER_PATH, ledger)
            manifest = json.loads((original / 'manifest.json').read_text())
            prefix = report.interrupted(manifest, original, ledger)
            result = report.closed_continuation(manifest, original, tail, ledger, prefix)
            self.assertEqual(result['outcomes']['valid'], 59)
            self.assertEqual(result['outcomes']['neverSent'], 0)
            self.assertEqual(result['knownActualProviderCostUsd'], '0.004624830')

    def test_tail_cannot_claim_clean_third_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            tail = Path(temp) / 'tail'
            shutil.copytree(report.TAIL, tail)
            completion = json.loads((tail / 'completion.json').read_text())
            completion['clean_full_third_pass_complete'] = True
            (tail / 'completion.json').write_text(json.dumps(completion))
            with self.assertRaisesRegex(ValueError, 'completion differs'):
                report.build(tail_base=tail)

    def test_valid_label_change_rejected_by_frozen_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'proposed_labels.jsonl'
            lines = (report.ROOT / 'data/pilot/proposed_labels.jsonl').read_text().splitlines()
            row = json.loads(lines[0])
            row['proposed_labels']['sentiment'] = 'negative'
            lines[0] = json.dumps(row)
            path.write_text('\n'.join(lines) + '\n')
            with self.assertRaisesRegex(ValueError, 'reference SHA-256 differs'):
                report.build(refs_path=path)

    def test_unreviewed_attempt_journal_is_running_unscored(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'fresh2'
            directory.mkdir()
            (directory / 'attempts.jsonl').write_text('{"stage":"reserved"}\n')
            result = report.build(repeat_base=Path(temp))
            self.assertEqual(result['passes']['fresh2']['completionStatus'], 'running')
            self.assertIsNone(result['passes']['fresh2']['score'])
            self.assertEqual(result['completedPasses'], 1)

    def test_cli_check_detects_stale_snapshot_without_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'kev.json'
            output.write_text('stale\n')
            before = output.read_bytes()
            with mock.patch.object(sys, 'argv', ['report', '--output', str(output), '--check']):
                with self.assertRaisesRegex(ValueError, 'Stale Kev native report'):
                    report.main()
            self.assertEqual(output.read_bytes(), before)
            with mock.patch.object(sys, 'argv', ['report', '--output', str(output)]):
                report.main()
            expected = output.read_bytes()
            with mock.patch.object(sys, 'argv', ['report', '--output', str(output), '--check']):
                report.main()
            self.assertEqual(output.read_bytes(), expected)

    def copy_first(self, destination):
        source = report.FIRST
        for name in ('manifest.json', 'native-plan.json', 'root-review.json',
                     'attempts.jsonl', 'completion.json'):
            shutil.copy2(source / name, destination / name)

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.copy_first(directory)
            (directory / 'completion.json').unlink()
            with self.assertRaises(FileNotFoundError):
                report.build(first_base=directory, repeat_base=directory / 'repeats')

    def test_raw_response_tamper_rejected_even_with_rebound_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.copy_first(directory)
            lines = (directory / 'attempts.jsonl').read_text().splitlines()
            row = json.loads(lines[1])
            row['body']['answers']['sentiment']['choice'] = 'negative'
            lines[1] = json.dumps(row)
            attempts = directory / 'attempts.jsonl'
            attempts.write_text('\n'.join(lines) + '\n')
            completion = json.loads((directory / 'completion.json').read_text())
            completion['attempts_sha256'] = report.smoke.sha(attempts.read_bytes())
            (directory / 'completion.json').write_text(json.dumps(completion))
            with self.assertRaisesRegex(ValueError, 'raw response differs'):
                report.build(first_base=directory, repeat_base=directory / 'repeats')

    def test_interruption_audit_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = report.REPEATS / 'fresh3'
            for name in ('manifest.json', 'root-review.json', 'attempts.jsonl',
                         'interruption-audit.json'):
                shutil.copy2(source / name, directory / name)
            audit_path = directory / 'interruption-audit.json'
            audit = json.loads(audit_path.read_text())
            audit['valid_count'] = 26
            audit_path.write_text(json.dumps(audit))
            manifest = json.loads((directory / 'manifest.json').read_text())
            with self.assertRaisesRegex(ValueError, 'audit or unknown-cost accounting'):
                report.interrupted(manifest, directory, report.LEDGER_PATH)

    def test_completion_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.copy_first(directory)
            completion = json.loads((directory / 'completion.json').read_text())
            completion['attempts_sha256'] = '0' * 64
            (directory / 'completion.json').write_text(json.dumps(completion))
            with self.assertRaisesRegex(ValueError, 'terminal 60-record completion'):
                report.build(first_base=directory, repeat_base=directory / 'repeats')


if __name__ == '__main__':
    unittest.main()
