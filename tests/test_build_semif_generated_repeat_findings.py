"""Synthetic-only offline tests; no SemIf weights or inference are loaded."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(os.environ.get('SEMIF_TEST_REPO', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_semif_generated_repeat_findings as report


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.canonical(obj))


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n' for row in rows))


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticGeneratedReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((REPO / report.MANIFEST).read_text())
        required = {str(report.MANIFEST), str(report.LABELS), self.plan['inputs']['file'],
                    self.plan['historical']['execution_manifest']['file'],
                    *self.plan['source_sha256'].keys(),
                    *(item['file'] for item in self.plan['historical']['evidence'].values())}
        for relative in required:
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, destination)
        self.metadata = report.load_jsonl(self.root / self.plan['historical']['evidence']['P0']['file'])[0]['metadata']
        self.prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                           'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        self.overrides = {}

    def stage(self, phase, name, length_at=None):
        folder = self.root / report.BASE / phase
        count = self.plan['stage_inputs'][name]['limit']
        requests = self.plan['requests'][phase.split('/')[1]][:count]
        receipt = {'kind': 'root-reviewed-semif-generated-fresh-stage-v1', 'approved': True,
                   'phase': phase, 'stage': name, 'plan_sha256': report.MANIFEST_SHA,
                   'controller_sha256': self.plan['source_sha256']['scripts/semif_generated_repeat_admission.py'],
                   'reference_labels_read': False}
        if name == 'development':
            receipt['smoke_inspection_sha256'] = hash_file(folder / 'smoke-inspection.json')
        receipt_path = folder / f'{name}.root-review.json'
        write_json(receipt_path, receipt)
        write_json(folder / f'{name}.claim.json', {
            'phase': phase, 'stage': name, 'plan_sha256': report.MANIFEST_SHA,
            'receipt_sha256': hash_file(receipt_path),
            'controller_sha256': receipt['controller_sha256'],
            'policy': 'one attempt; unknown started positions never replayed'})
        journal = [{'event': 'phase_started', 'phase': phase, 'stage': name}]
        events, captures, records = [], [], []
        for request in requests:
            ident = request['id']
            finish = 'length' if ident == length_at else 'stop'
            predicted = self.overrides.get((phase, name, ident), self.prediction)
            raw = {'content': json.dumps(predicted), 'finish_reason': finish}
            event = {'id': ident, 'text': raw['content'], 'token': 1, 'from_draft': False,
                     'prompt_tokens': request['input_tokens'], 'generation_tokens': 12,
                     'finish_reason': finish}
            prediction = predicted if finish == 'stop' else None
            status = 'ok' if prediction else 'invalid_output'
            journal.extend([{'event': 'request_started', 'id': ident,
                             'request_sha256': request['messages_sha256'],
                             'started_utc': '2026-09-28T00:00:00Z'},
                            {'event': 'request_completed', 'id': ident, 'status': status}])
            events.append(event)
            captures.append({'id': ident, 'request_sha256': request['messages_sha256'],
                             'metadata': self.metadata, 'raw_response': raw,
                             'stream_events_sha256': report.digest(report.canonical(event).encode())})
            records.append({'id': ident, 'phase': phase, 'stage': name, 'status': status,
                            'prediction': prediction, 'attempts': 1,
                            'request_sha256': request['messages_sha256'],
                            'rendered_prompt_sha256': request['rendered_prompt_sha256'],
                            'input_token_ids_sha256': request['input_token_ids_sha256'],
                            'input_tokens': request['input_tokens'],
                            'input_sha256': request['input_sha256'],
                            'policy_sha256': self.plan['policy_prefix_sha256'],
                            'artifact_revision': self.plan['artifact_revision'],
                            'runtime_versions': self.plan['runtime']['packages'],
                            'host': self.plan['runtime']['platform'],
                            'metadata': self.metadata,
                            'raw_sha256': report.digest(report.canonical(raw).encode()),
                            'elapsed_seconds': 0.25, 'output_tokens': 12})
        journal.append({'event': 'phase_completed', 'count': count})
        for suffix, rows in [('journal', journal), ('events', events), ('raw', captures), ('records', records)]:
            write_rows(folder / f'{name}.{suffix}.jsonl', rows)
        write_json(folder / f'{name}.completion.json', {
            'phase': phase, 'stage': name, 'plan_sha256': report.MANIFEST_SHA,
            'output_sha256': hash_file(folder / f'{name}.records.jsonl'), 'count': count})
        return records

    def close_first_phase(self, length_at=None):
        phase = 'fresh1/P0'
        smoke = self.stage(phase, 'smoke', length_at if length_at in ('DEV-001','DEV-002','DEV-003') else None)
        folder = self.root / report.BASE / phase
        inspection = {'phase': phase, 'plan_sha256': report.MANIFEST_SHA,
                      'smoke_sha256': hash_file(folder / 'smoke.records.jsonl'),
                      'inspected_ids': ['DEV-001', 'DEV-002', 'DEV-003'],
                      'approved': True, 'inspector': 'synthetic-test'}
        if any(row['status'] != 'ok' for row in smoke):
            inspection.update({'accepted_unchanged_invalids': True,
                               'failure_class': 'intrinsic_schema',
                               'inspection_reason': 'Synthetic known length finish'})
        write_json(folder / 'smoke-inspection.json', inspection)
        self.stage(phase, 'development', length_at)
        return folder

    def test_no_live_evidence_is_unscored(self):
        series = report.build(self.root)['series'][0]
        self.assertEqual(series['completedConditions'], 0)
        self.assertEqual(len(series['missingPasses']), 9)
        self.assertEqual(series['missingPasses'][0]['status'], 'not_started')
        self.assertFalse(series['historicalObservationalOnly']['eligibleAsFirstPass'])
        self.assertEqual(series['historicalObservationalOnly']['unknownStartedId'], 'DEV-033')

    def test_closed_known_length_is_invalid_not_unknown(self):
        self.close_first_phase('DEV-001')
        series = report.build(self.root)['series'][0]
        score = series['passes']['fresh1']['P0']['score']
        self.assertEqual(series['completedConditions'], 1)
        self.assertEqual(score['valid'], 59)
        self.assertEqual(score['outcomes']['invalid_output'], 1)
        self.assertEqual(score['invalidIds'], ['DEV-001'])
        for field in report.FIELDS:
            matrix = series['passes']['fresh1']['P0']['confusionCounts'][field]
            self.assertEqual(sum(sum(row.values()) for row in matrix.values()), 60)
            for truth, row in matrix.items():
                self.assertEqual(sum(row.values()), series['referenceClassCounts'][field][truth])
        sentiment = series['passes']['fresh1']['P0']['confusionCounts']['sentiment']
        self.assertEqual(sum(row.get('__invalid_or_missing__', 0) for row in sentiment.values()), 1)
        self.assertIsNone(series['passes']['fresh1']['P0']['usage']['actualCostUsd'])
        self.assertEqual(series['passes']['fresh1']['P0']['usage']['tokens']['output_tokens'], 720)

    def test_all_nine_synthetic_phases_close_without_flips(self):
        for phase in self.plan['schedule']:
            smoke = self.stage(phase, 'smoke')
            folder = self.root / report.BASE / phase
            write_json(folder / 'smoke-inspection.json', {
                'phase': phase, 'plan_sha256': report.MANIFEST_SHA,
                'smoke_sha256': hash_file(folder / 'smoke.records.jsonl'),
                'inspected_ids': ['DEV-001', 'DEV-002', 'DEV-003'],
                'approved': True, 'inspector': 'synthetic-test'})
            self.stage(phase, 'development')
        series = report.build(self.root)['series'][0]
        self.assertEqual(series['completedConditions'], 9)
        self.assertEqual(len(series['withinPassPromptDeltas']), 6)
        self.assertEqual(len(series['withinPassPromptFlips']), 6)
        self.assertEqual(len(series['pairwiseFlips']), 9)
        self.assertEqual(series['changesAcrossThreePasses']['P0']['fourFieldVector'], [])
        self.assertEqual(series['passes']['fresh1']['P0']['confusionCounts']['sentiment']['positive']['positive'],
                         series['referenceClassCounts']['sentiment']['positive'])

    def test_prompt_flip_can_exist_with_zero_net_field_delta(self):
        labels = {row['id']: row['proposed_labels'] for row in
                  report.load_jsonl(self.root / report.LABELS)}
        positive = next(rid for rid, value in labels.items() if value['sentiment'] == 'positive')
        negative = next(rid for rid, value in labels.items() if value['sentiment'] == 'negative')
        for rid in (positive, negative):
            self.overrides[('fresh1/P1', 'development', rid)] = dict(self.prediction, sentiment='negative')
        for phase in self.plan['schedule'][:3]:
            self.stage(phase, 'smoke')
            folder = self.root / report.BASE / phase
            write_json(folder / 'smoke-inspection.json', {
                'phase': phase, 'plan_sha256': report.MANIFEST_SHA,
                'smoke_sha256': hash_file(folder / 'smoke.records.jsonl'),
                'inspected_ids': ['DEV-001', 'DEV-002', 'DEV-003'],
                'approved': True, 'inspector': 'synthetic-test'})
            self.stage(phase, 'development')
        series = report.build(self.root)['series'][0]
        delta = next(row for row in series['withinPassPromptDeltas']
                     if row['pass'] == 'fresh1' and row['to'] == 'P1')
        flip = next(row for row in series['withinPassPromptFlips']
                    if row['pass'] == 'fresh1' and row['to'] == 'P1')
        self.assertEqual(delta['fields']['sentiment'], 0)
        self.assertEqual(flip['sentiment']['changed'], 2)
        self.assertEqual(set(flip['sentiment']['caseIds']), {positive, negative})

    def test_open_claim_is_unscored(self):
        folder = self.root / report.BASE / 'fresh1/P0'
        write_json(folder / 'development.claim.json', {'synthetic': True})
        write_rows(folder / 'development.journal.jsonl', [{'event': 'request_started', 'id': 'DEV-001'}])
        self.assertEqual(report.build(self.root)['series'][0]['completedConditions'], 0)

    def test_interrupted_unknown_raw_is_unscored(self):
        folder = self.root / report.BASE / 'fresh1/P0'
        write_json(folder / 'development.claim.json', {'synthetic': True})
        write_rows(folder / 'development.journal.jsonl', [
            {'event': 'phase_started', 'phase': 'fresh1/P0', 'stage': 'development'},
            {'event': 'request_started', 'id': 'DEV-001'},
            {'event': 'phase_stopped', 'id': 'DEV-001',
             'started_outcome': 'raw_saved_no_replay'}])
        write_rows(folder / 'development.raw.jsonl', [
            {'id': 'DEV-001', 'raw_response': {'content': '{', 'finish_reason': None}}])
        series = report.build(self.root)['series'][0]
        self.assertEqual(series['completedConditions'], 0)
        self.assertEqual(series['missingPasses'][0]['status'], 'claimed_in_progress_or_interrupted')

    def test_frozen_source_tamper_fails_closed(self):
        path = self.root / 'scripts/semif_prompt_execution.py'
        path.write_bytes(path.read_bytes() + b'\n# synthetic tamper\n')
        with self.assertRaisesRegex(ValueError, 'Bound source changed'):
            report.build(self.root)

    def test_raw_tamper_fails_closed(self):
        folder = self.close_first_phase()
        path = folder / 'development.raw.jsonl'
        rows = report.load_jsonl(path)
        rows[0]['raw_response']['content'] = 'tampered'
        write_rows(path, rows)
        with self.assertRaisesRegex(ValueError, 'Generated raw stream differs'):
            report.build(self.root)

    def test_missing_receipt_fails_closed(self):
        folder = self.close_first_phase()
        (folder / 'development.root-review.json').unlink()
        with self.assertRaises(FileNotFoundError):
            report.build(self.root)

    def test_completion_hash_tamper_fails_closed(self):
        folder = self.close_first_phase()
        path = folder / 'development.completion.json'
        value = json.loads(path.read_text())
        value['output_sha256'] = '0' * 64
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, 'completion differs'):
            report.build(self.root)


if __name__ == '__main__':
    unittest.main()
