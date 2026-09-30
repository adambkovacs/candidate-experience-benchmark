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
        self.assertEqual(third['outcomes'], {'valid': 25, 'transportErrorUnknownOutcome': 1,
                                            'neverSent': 34})
        self.assertEqual(third['knownActualProviderCostUsd'], '0.001959258')
        self.assertEqual(third['unknownCostReservationUsd'], '0.000344064')

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
