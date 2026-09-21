import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_development_report import load_timing_attempts, reject_smoke_artifact, validate_development_dataset
from development_benchmark import KEYS


class TimingProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.row = {'id': 'DEV-001', 'started_utc': '2026-09-21T10:00:00Z',
                    'elapsed_seconds': 2.0, 'status': 'ok', 'raw_response': 'answer'}

    def write(self, name, row=None):
        (self.root / name).write_text(json.dumps(self.row if row is None else row) + '\n')
        return name

    def load(self, files, **kwargs):
        return load_timing_attempts({'predictions_file': 'development.jsonl',
            'attempt_files': files, 'attempt_phase': 'development', **kwargs}, {'DEV-001'}, self.root)

    def test_phase_required(self):
        with self.assertRaisesRegex(ValueError, 'attempt_phase'):
            self.load([self.write('a.jsonl')], attempt_phase=None)

    def test_duplicate_path(self):
        name = self.write('a.jsonl')
        with self.assertRaisesRegex(ValueError, 'Repeated attempt path'):
            self.load([name, './' + name])

    def test_duplicate_content(self):
        with self.assertRaisesRegex(ValueError, 'Repeated attempt content'):
            self.load([self.write('a.jsonl'), self.write('b.jsonl')])

    def test_reclassified_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'Repeated raw attempt'):
            self.load([self.write('a.jsonl'), self.write('b.jsonl',
                {**self.row, 'status': 'service_error', 'audit': 'reclassified'})])

    def test_real_retry_allowed(self):
        rows = self.load([self.write('a.jsonl'), self.write('b.jsonl',
            {**self.row, 'started_utc': '2026-09-21T10:01:00Z'})])
        self.assertEqual(len(rows), 2)

    def test_smoke_filename_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Smoke'):
            self.load([self.write('smoke-verified.jsonl')])

    def test_smoke_row_rejected(self):
        with self.assertRaisesRegex(ValueError, 'phase'):
            self.load([self.write('a.jsonl', {**self.row, 'phase': 'smoke'})])

    def test_unknown_id_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.load([self.write('a.jsonl', {**self.row, 'id': 'OTHER'})])

    def test_baseline_without_timestamp_allowed(self):
        rows = self.load([self.write('rules.jsonl', {'id': 'DEV-001', 'elapsed_seconds': 0, 'status': 'ok'})])
        self.assertEqual(len(rows), 1)

    def test_reclassified_without_timestamp_rejected(self):
        original = {k: v for k, v in self.row.items() if k != 'started_utc'}
        with self.assertRaisesRegex(ValueError, 'Repeated raw attempt'):
            self.load([self.write('a.jsonl', original), self.write('b.jsonl',
                {**original, 'status': 'error', 'prediction': None, 'audit_note': 'updated'})])

    def test_smoke_directory_rejected(self):
        (self.root / 'smoke-run').mkdir()
        with self.assertRaisesRegex(ValueError, 'Smoke'):
            self.load([self.write('smoke-run/predictions.jsonl')])

    def test_default_prediction_file_is_validated(self):
        self.write('development.jsonl')
        rows = load_timing_attempts({'predictions_file': 'development.jsonl',
            'attempt_phase': 'development'}, {'DEV-001'}, self.root)
        self.assertEqual(len(rows), 1)

    def test_invalid_duration_rejected(self):
        for elapsed in [-1, float('nan'), float('inf'), True, '2']:
            with self.subTest(elapsed=elapsed), self.assertRaisesRegex(ValueError, 'elapsed_seconds'):
                self.load([self.write('a.jsonl', {**self.row, 'elapsed_seconds': elapsed})])


class ReportDatasetTests(unittest.TestCase):
    def setUp(self):
        self.inputs = [{'id': str(i)} for i in range(60)]
        self.refs = [{'id': str(i), 'split': 'development',
                     'proposed_labels': {k: 'insufficient_information' for k in KEYS}}
                     for i in range(60)]

    def test_exact60_matching_ids(self):
        validate_development_dataset(self.inputs, list(reversed(self.refs)))

    def test_missing_record_rejected(self):
        with self.assertRaisesRegex(ValueError, 'exactly60'):
            validate_development_dataset(self.inputs[:-1], self.refs[:-1])

    def test_same_count_mismatched_ids_rejected(self):
        self.refs[-1]['id'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'matched'):
            validate_development_dataset(self.inputs, self.refs)

    def test_duplicate_ids_rejected(self):
        self.inputs[-1]['id'] = '0'
        with self.assertRaisesRegex(ValueError, 'unique'):
            validate_development_dataset(self.inputs, self.refs)

    def test_non_development_reference_rejected(self):
        self.refs[0]['split'] = 'test'
        with self.assertRaisesRegex(ValueError, 'development labels'):
            validate_development_dataset(self.inputs, self.refs)

    def test_smoke_predictions_rejected_even_with_separate_attempts(self):
        with self.assertRaisesRegex(ValueError, 'Smoke'):
            reject_smoke_artifact('results/smoke.jsonl', [{'id': 'DEV-001'}])

    def test_smoke_prediction_row_rejected(self):
        with self.assertRaisesRegex(ValueError, 'phase'):
            reject_smoke_artifact('development.jsonl', [{'id': 'DEV-001', 'phase': 'smoke'}])

    def test_development_prediction_rows_accepted(self):
        reject_smoke_artifact('development.jsonl', [{'id': 'DEV-001'}])


if __name__ == '__main__':
    unittest.main()
