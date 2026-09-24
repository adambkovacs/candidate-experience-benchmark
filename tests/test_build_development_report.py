import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_development_report import load_timing_attempts, reject_smoke_artifact, validate_development_dataset, validate_full60_predictions, batch_timing
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

    def test_full60_attempt_alias_accepted_only_when_declared(self):
        name = self.write('full60.jsonl', {**self.row, 'phase': 'full60'})
        rows = load_timing_attempts({'predictions_file': name, 'attempt_files': [name],
            'attempt_phase': 'full60'}, {'DEV-001'}, self.root)
        self.assertEqual(len(rows), 1)
        with self.assertRaisesRegex(ValueError, 'phase'):
            self.load([name])

    def test_smoke3_attempt_rejected_under_full60_alias(self):
        name = self.write('attempt.jsonl', {**self.row, 'phase': 'smoke3'})
        with self.assertRaisesRegex(ValueError, 'phase'):
            load_timing_attempts({'predictions_file': name, 'attempt_files': [name],
                'attempt_phase': 'full60'}, {'DEV-001'}, self.root)

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

    def test_full60_predictions_need_canonical_order(self):
        rows = [{'id': f'DEV-{i:03}', 'phase': 'full60'} for i in range(1, 61)]
        ids = [r['id'] for r in rows]
        reject_smoke_artifact('results/full60.jsonl', rows)
        validate_full60_predictions({'attempt_phase': 'full60'}, rows, ids)
        with self.assertRaisesRegex(ValueError, 'exact ordered 60 IDs'):
            validate_full60_predictions({'attempt_phase': 'full60'}, list(reversed(rows)), ids)
        with self.assertRaisesRegex(ValueError, 'exact ordered 60 IDs'):
            validate_full60_predictions({'attempt_phase': 'full60'}, rows[:59], ids)

    def test_smoke3_prediction_row_rejected(self):
        with self.assertRaisesRegex(ValueError, 'phase'):
            reject_smoke_artifact('development.jsonl', [{'id': 'DEV-001', 'phase': 'smoke3'}])

    def test_development_prediction_rows_accepted(self):
        reject_smoke_artifact('development.jsonl', [{'id': 'DEV-001'}])


class BatchTimingTests(unittest.TestCase):
    def test_two_batches_count_time_once_and_failures_stay_in60_denominator(self):
        from development_benchmark import score
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            attempts=[{'id':'batch-01','phase':'development','record_order':['A','B'],'batch_size':2,'status':'ok','elapsed_seconds':10},
                      {'id':'batch-02','phase':'development','record_order':['C','D'],'batch_size':2,'status':'service_error','elapsed_seconds':20}]
            (root/'attempts.jsonl').write_text(''.join(json.dumps(a)+'\n' for a in attempts))
            labels={k:'insufficient_information' for k in KEYS}
            rows=[{'id':i,'batch_id':'batch-01' if i in 'AB' else 'batch-02','timing_kind':'amortized_batch_share_not_individual_latency','status':'ok' if i in 'AB' else 'service_error','prediction':labels if i in 'AB' else None,'elapsed_seconds':5 if i in 'AB' else 10} for i in 'ABCD']
            config={'attempt_phase':'development','predictions_file':'unused','raw_batch_attempt_files':['attempts.jsonl']}
            timing=batch_timing(config,set('ABCD'),rows,root)
            self.assertEqual(timing['sum_batch_request_seconds'],30)
            self.assertEqual(timing['batch_requests'],2)
            self.assertEqual(timing['batch_median_seconds'],15)
            self.assertNotIn('median_seconds',timing)
            self.assertNotIn('p95_nearest_rank_seconds',timing)
            self.assertAlmostEqual(timing['successful_records_per_request_second'],2/30)
            refs=[{'id':i,'proposed_labels':labels} for i in list('ABCD')+[str(i) for i in range(56)]]
            result=score(refs,rows,[])
            self.assertEqual(result['valid_outputs'],2)
            self.assertEqual(result['metrics']['sentiment']['denominator'],60)
            self.assertEqual(len(result['missing_or_failed']),58)
            retry={**attempts[0],'record_order':['A','C'],'elapsed_seconds':8}
            (root/'retry.jsonl').write_text(json.dumps(retry)+'\n')
            with self.assertRaisesRegex(ValueError,'changed record membership'):
                batch_timing({**config,'raw_batch_attempt_files':['attempts.jsonl','retry.jsonl']},set('ABCD'),rows,root)
            with self.assertRaisesRegex(ValueError,'Repeated attempt path'):
                batch_timing({**config,'raw_batch_attempt_files':['attempts.jsonl','./attempts.jsonl']},set('ABCD'),rows,root)


if __name__ == '__main__':
    unittest.main()

class IncompleteTimingTests(unittest.TestCase):
    def test_unknown_interrupted_attempt_withholds_full_aggregates(self):
        from build_development_report import mark_incomplete_timing
        timing={'sum_record_seconds':12,'median_seconds':6,'p95_nearest_rank_seconds':8,'note':'Saved attempts.'}
        result=mark_incomplete_timing(timing,{'timing_incomplete_reason':'Interrupted attempt duration unknown'},[{'elapsed_seconds':4},{'elapsed_seconds':8}])
        self.assertFalse(result['all_attempt_timing_complete'])
        self.assertIsNone(result['sum_record_seconds']);self.assertIsNone(result['median_seconds']);self.assertIsNone(result['p95_nearest_rank_seconds'])
        self.assertEqual(result['known_recorded_sum_record_seconds'],12)
    def test_missing_duration_is_not_zero_but_complete_timings_stay_unchanged(self):
        from build_development_report import mark_incomplete_timing
        complete=mark_incomplete_timing({'sum_record_seconds':4,'note':''},{},[{'elapsed_seconds':4}])
        self.assertTrue(complete['all_attempt_timing_complete']);self.assertEqual(complete['sum_record_seconds'],4)
        missing=mark_incomplete_timing({'sum_record_seconds':4,'note':''},{},[{'elapsed_seconds':4},{'elapsed_seconds':None}])
        self.assertFalse(missing['all_attempt_timing_complete']);self.assertIsNone(missing['sum_record_seconds']);self.assertEqual(missing['saved_attempts_missing_duration'],1)
