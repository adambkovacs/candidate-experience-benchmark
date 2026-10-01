"""Closed, interrupted E4B evidence is reported without scoring unsent records."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_e4b_interruption_findings as report


class E4BInterruptionReportTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for binding in report.build()['sourceBindings']:
            source = ROOT / binding['path']
            target = root / binding['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        return root

    def test_actual_stopped_series_keeps_unknown_and_unsent_separate(self):
        findings = report.build()
        self.assertEqual(findings['denominator'], 60)
        self.assertEqual(findings['savedValid'], 50)
        self.assertEqual(findings['invalid'], 0)
        self.assertEqual(findings['unknownIds'], ['DEV-039', 'DEV-052'])
        self.assertEqual(findings['neverSentIds'], report.IDS[52:])
        self.assertIsNone(findings['finalScore'])
        self.assertEqual(findings['scoreStatus'],
                         'unavailable_while_planned_requests_remain_unsent')
        self.assertEqual(findings['usage']['tokens']['input'], 137099)
        self.assertEqual(findings['usage']['tokens']['output'], 20884)
        self.assertIsNone(findings['usage']['actualCostUsd'])
        self.assertEqual(findings['seriesStatus'],
                         'descriptive_interrupted_not_clean_matched_three')
        self.assertEqual(len(findings['sourceBindings']), 40)
        self.assertEqual(findings['hostInterruption']['observation'],
                         'both_timeout_intervals_overlap_recorded_host_sleep')
        self.assertEqual(findings['hostInterruption']['inferenceTimeConclusion'],
                         'unavailable')
        self.assertEqual(findings['hostInterruption']['source']['path'], str(report.HOST_NOTE))
        text = json.dumps(findings)
        self.assertNotIn('partialResult', text)
        self.assertNotIn('reasoningContent', text)
        self.assertNotIn('SDK client', text)

    def test_missing_or_changed_immutable_source_rejected(self):
        root = self.fixture()
        raw = root / report.BASE / 'fresh2/P2/development.raw.jsonl'
        raw.write_bytes(raw.read_bytes().replace(b'DEV-001', b'DEV-002', 1))
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(root)

    def test_changed_saved_decision_rejected_even_with_new_completion_hash(self):
        root = self.fixture()
        folder = root / report.CONTINUATION / 'fresh2/P2'
        records_file = folder / 'suffix.records.jsonl'
        rows = [json.loads(line) for line in records_file.read_text().splitlines()]
        rows[0]['decision']['prediction']['sentiment'] = 'tampered'
        records_file.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        completion_file = folder / 'suffix.completion.json'
        completion = json.loads(completion_file.read_text())
        completion['records_sha256'] = hashlib.sha256(records_file.read_bytes()).hexdigest()
        completion_file.write_text(json.dumps(completion) + '\n')
        with self.assertRaisesRegex(ValueError, 'Saved response differs from raw'):
            report.build(root)

    def test_missing_terminal_suffix_rejected(self):
        root = self.fixture()
        (root / report.CONTINUATION / 'fresh2/P2/suffix.completion.json').unlink()
        with self.assertRaises(FileNotFoundError):
            report.build(root)


if __name__ == '__main__':
    unittest.main()
