"""Closed E4B suffix is scored descriptively while unknowns stay unknown."""
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

    def test_closed_suffix_retains_cutoff_and_scores_descriptive_composite(self):
        findings = report.build()
        self.assertEqual(findings['denominator'], 60)
        self.assertEqual(findings['savedValid'], 58)
        self.assertEqual(findings['invalid'], 0)
        self.assertEqual(findings['unknownIds'], ['DEV-039', 'DEV-052'])
        self.assertEqual(findings['neverSentIds'], [])
        self.assertIsNone(findings['finalScore'])
        self.assertEqual(findings['scoreStatus'], 'descriptive_interrupted_composite')
        self.assertEqual(findings['descriptiveScore'], {
            'denominator': 60, 'valid': 58, 'allFour': 48,
            'fields': {'sentiment': 56, 'follow_up_needed': 57,
                       'serious_concern_reported': 53, 'testimonial_potential': 54}})
        self.assertEqual(findings['finalSuffix'], {
            'status': 'completed', 'attempted': 8, 'savedValid': 8, 'allFour': 7,
            'denominator': 8, 'unknownIds': [], 'cleanRepeatCredit': False})
        self.assertEqual(findings['usage']['tokens']['coverage'],
                         '58_saved_responses_only_two_timeout_usages_unknown')
        self.assertIsNone(findings['usage']['actualCostUsd'])
        self.assertEqual(findings['seriesStatus'],
                         'descriptive_interrupted_not_clean_matched_three')
        self.assertGreater(len(findings['sourceBindings']), 40)
        self.assertEqual(findings['hostInterruption']['observation'],
                         'both_timeout_intervals_overlap_recorded_host_sleep')
        self.assertEqual(findings['hostInterruption']['inferenceTimeConclusion'],
                         'unavailable')
        self.assertEqual(findings['hostInterruption']['source']['path'], str(report.HOST_NOTE))
        self.assertEqual(findings['originalCutoff']['savedValid'], 50)
        self.assertEqual(findings['originalCutoff']['neverSentIds'], report.FINAL_IDS)
        self.assertIsNone(findings['originalCutoff']['finalScore'])
        self.assertEqual(findings['originalCutoff']['scoreStatus'],
                         'unavailable_while_planned_requests_remain_unsent')
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

    def test_relocated_closed_suffix_rejects_raw_or_review_drift(self):
        root = self.fixture()
        relocated = report.build(root)
        self.assertEqual(relocated['descriptiveScore']['allFour'], 48)
        raw = root / report.FINAL_SUFFIX / 'suffix.raw.jsonl'
        value = raw.read_bytes()
        raw.write_bytes(value.replace(b'DEV-053', b'DEV-054', 1))
        with self.assertRaisesRegex(ValueError, 'Final E4B suffix saved row membership differs'):
            report.build(root)
        raw.write_bytes(value)
        review = root / report.FINAL_SUFFIX / 'suffix.root-review.json'
        receipt = json.loads(review.read_text())
        receipt['approved'] = False
        review.write_text(json.dumps(receipt) + '\n')
        with self.assertRaisesRegex(ValueError, 'Final E4B suffix root receipt differs'):
            report.build(root)

    def test_suffix_record_tamper_cannot_launder_seven_of_eight_result(self):
        root = self.fixture()
        records = root / report.FINAL_SUFFIX / 'suffix.records.jsonl'
        rows = [json.loads(line) for line in records.read_text().splitlines()]
        rows[0]['decision']['prediction']['sentiment'] = 'negative'
        records.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        done_path = root / report.FINAL_SUFFIX / 'suffix.completion.json'
        done = json.loads(done_path.read_text())
        done['records_sha256'] = hashlib.sha256(records.read_bytes()).hexdigest()
        done_path.write_text(json.dumps(done) + '\n')
        with self.assertRaisesRegex(ValueError, 'Final E4B suffix raw classification differs'):
            report.build(root)


if __name__ == '__main__':
    unittest.main()
