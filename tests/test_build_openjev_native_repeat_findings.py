"""Offline OpenJev native reporting tests. Synthetic stages never run a model."""
import base64
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
import build_openjev_native_repeat_findings as report


class NativeOpenJevReportTests(unittest.TestCase):
    def copy_sources(self, target):
        plan, _, _, _, bindings = report.source_context(REPO)
        for item in bindings:
            source = REPO / item['path']
            destination = target / item['path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        for mode in report.MODES:
            spec = plan['historical'][mode]
            for filename in spec['files_sha256']:
                relative = Path(spec['directory']) / filename
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(REPO / relative, destination)
        return plan

    @staticmethod
    def write_json(folder, name, value):
        (folder / name).write_text(json.dumps(value, sort_keys=True) + '\n')

    @staticmethod
    def write_jsonl(folder, name, values):
        (folder / name).write_text(''.join(json.dumps(v, sort_keys=True) + '\n' for v in values))

    def create_closed(self, target, plan, *, phase='openjev-fixed/fresh1/P0', invalid_id=None,
                      flip_id=None):
        folder = target / report.BASE / phase
        folder.mkdir(parents=True)
        old = report.rows(target, Path(plan['historical']['fixed']['directory']) / 'development-reconciled.jsonl')
        controller_sha = plan['source_sha256'][str(REPO / 'scripts/openjev_native_repeat_admission.py')]
        for name, count in (('smoke', 3), ('development', 60)):
            raw = []; records = []; journal = []
            for historic, request in zip(old[:count], plan['requests']['fixed'][:count]):
                rid = request['id']; attempt = f'fixture-{name}-{rid}'
                body = copy.deepcopy(historic['raw_response'])
                invalid = name == 'development' and rid == invalid_id
                if invalid:
                    body['model'] = 'wrong-model'
                flip = name == 'development' and rid == flip_id
                if flip:
                    sentiment = body['answers']['sentiment']
                    alternate = 'negative' if sentiment['choice'] != 'negative' else 'positive'
                    sentiment['choice'] = alternate
                    sentiment['probabilities'] = {key: 1.0 if key == alternate else 0.0
                                                   for key in sentiment['probabilities']}
                captured = {'id': rid, 'attempt_id': attempt,
                    'request_sha256': request['request_sha256'], 'http_status': 200,
                    'headers': {}, 'body_base64': base64.b64encode(json.dumps(body).encode()).decode(),
                    'truncated': False, 'incomplete': False, 'elapsed_seconds': 0.25}
                decision = ({'status': 'invalid_output', 'reason': 'ValueError'} if invalid
                            else {'status': 'ok', 'prediction': {
                                **historic['prediction'],
                                'sentiment': alternate if flip else historic['prediction']['sentiment']}})
                raw.append(captured)
                records.append({'id': rid, 'attempt_id': attempt,
                    'request_sha256': request['request_sha256'], 'decision': decision,
                    'reference_labels_read': False})
                journal.extend([{'event': 'started', 'id': rid, 'attempt_id': attempt,
                    'request_sha256': request['request_sha256']},
                    {'event': 'finished', 'id': rid, 'attempt_id': attempt,
                     'status': decision['status']}])
            for suffix, values in (('raw', raw), ('records', records), ('journal', journal)):
                self.write_jsonl(folder, name + '.' + suffix + '.jsonl', values)
            if name == 'development':
                smoke_raw = report.sha(folder / 'smoke.raw.jsonl')
                smoke_records = report.sha(folder / 'smoke.records.jsonl')
                self.write_json(folder, 'smoke-inspection.json',
                    {'kind': 'openjev-native-smoke-inspection-v1', 'approved': True,
                     'phase': phase, 'plan_sha256': report.MANIFEST_SHA,
                     'raw_sha256': smoke_raw, 'records_sha256': smoke_records,
                     'reference_labels_read': False})
            review = {'kind': 'root-reviewed-openjev-native-stage-v1', 'approved': True,
                'phase': phase, 'stage': name, 'plan_sha256': report.MANIFEST_SHA,
                'controller_sha256': controller_sha,
                'predecessor_sha256': report.sha(folder / 'smoke-inspection.json')
                   if name == 'development' else None,
                'reference_labels_read': False,
                'source_commit': plan['runtime']['source_commit'],
                'artifact_manifest_sha256': plan['artifact_manifest_sha256']}
            self.write_json(folder, name + '.root-review.json', review)
            receipt_sha = report.sha(folder / (name + '.root-review.json'))
            self.write_json(folder, name + '.claim.json',
                {'phase': phase, 'stage': name, 'plan_sha256': report.MANIFEST_SHA,
                 'controller_sha256': controller_sha, 'receipt_sha256': receipt_sha,
                 'claimed_utc': 1.0, 'reference_labels_read': False})
            self.write_json(folder, name + '.completion.json',
                {'phase': phase, 'stage': name, 'status': 'completed', 'reason': None,
                 'count': count, 'attempted': count,
                 'raw_sha256': report.sha(folder / (name + '.raw.jsonl')),
                 'records_sha256': report.sha(folder / (name + '.records.jsonl')),
                 'journal_sha256': report.sha(folder / (name + '.journal.jsonl')),
                 'plan_sha256': report.MANIFEST_SHA, 'receipt_sha256': receipt_sha})
        return folder

    def test_historical_is_observational_and_no_fresh_stages_are_scored(self):
        result = report.build()
        self.assertEqual(set(result['configurations']), set(report.MODES))
        self.assertEqual({mode: result['configurations'][mode]['historicalObservation']['score']['allFour']
                          for mode in report.MODES}, {'fixed': 52, 'adaptive': 51, 'thinking': 57})
        for mode in report.MODES:
            config = result['configurations'][mode]
            self.assertEqual(config['historicalObservation']['score']['valid'], 60)
            self.assertEqual(config['historicalObservation']['status'],
                             'historical_observation_excluded_from_fresh_triplet')
            self.assertEqual(len(config['missingPasses']), 3)
            self.assertEqual(config['freshPasses'], {})
            self.assertIsNone(config['threePassSummary']['P0']['allFour']['range'])
            self.assertIsNone(config['historicalObservation']['usage']['actualCostUsd'])
            self.assertIsNone(config['historicalObservation']['usage']['inferenceSeconds'])
        self.assertIn('development-continuation.jsonl',
                      result['configurations']['fixed']['historicalObservation']['evidence'])
        self.assertIsNone(result['configurations']['fixed']['historicalObservation']
                          ['interruption']['unrecordedAttemptSeconds'])

    def test_synthetic_closed_stage_scores_invalid_and_keeps_confusion_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = self.copy_sources(root)
            self.create_closed(root, plan, invalid_id='DEV-004')
            result = report.build(root)
            fresh = result['configurations']['fixed']['freshPasses']['fresh1']
            self.assertEqual((fresh['score']['denominator'], fresh['score']['valid']), (60, 59))
            self.assertEqual(fresh['score']['outcomes']['invalid_output'], 1)
            self.assertEqual(fresh['score']['invalidIds'], ['DEV-004'])
            self.assertEqual(sum(sum(row.values()) for row in fresh['confusionCounts']['sentiment'].values()), 60)
            self.assertEqual(fresh['usage']['requestCount'], 60)
            self.assertIsInstance(fresh['usage']['tokens']['input_tokens'], int)
            self.assertIsNone(fresh['usage']['actualCostUsd'])
            self.assertIsNone(fresh['usage']['inferenceSeconds'])
            self.assertEqual(result['configurations']['fixed']['pairwiseFlips'], [])
            self.assertIsNone(result['configurations']['fixed']['changesAcrossThreePasses'])

    def test_relocated_closed_stage_uses_frozen_controller_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = self.copy_sources(root)
            self.create_closed(root, plan)
            with patch.object(report, 'ROOT', root):
                result = report.build(root)
            self.assertEqual(result['configurations']['fixed']['freshPasses']['fresh1']
                             ['score']['valid'], 60)

    def test_three_fresh_passes_calculate_shared_valid_flips(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = self.copy_sources(root)
            self.create_closed(root, plan)
            self.create_closed(root, plan, phase='openjev-fixed/fresh2/P0', flip_id='DEV-001')
            self.create_closed(root, plan, phase='openjev-fixed/fresh3/P0', invalid_id='DEV-004')
            config = report.build(root)['configurations']['fixed']
            self.assertEqual(config['threePassSummary']['P0']['allFour']['completedPasses'], 3)
            self.assertIsNotNone(config['threePassSummary']['P0']['allFour']['range'])
            self.assertEqual(config['pairwiseFlips'][0]['fourFieldVector']['caseIds'], ['DEV-001'])
            self.assertEqual(config['pairwiseFlips'][1]['denominator'], 59)
            self.assertEqual(config['changesAcrossThreePasses']['denominator'], 59)
            self.assertEqual(config['changesAcrossThreePasses']['fourFieldVector'], ['DEV-001'])

    def test_closed_receipt_and_projection_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = self.copy_sources(root)
            folder = self.create_closed(root, plan)
            receipt = folder / 'development.root-review.json'
            saved = receipt.read_bytes()
            receipt.write_text(receipt.read_text().replace('"approved": true', '"approved": false'))
            with self.assertRaisesRegex(ValueError, 'admission or hashes'):
                report.build(root)
            receipt.write_bytes(saved)
            records = report.rows(root, report.BASE / 'openjev-fixed/fresh1/P0/development.records.jsonl')
            records[0]['decision']['prediction']['sentiment'] = 'negative'
            self.write_jsonl(folder, 'development.records.jsonl', records)
            end = json.loads((folder / 'development.completion.json').read_text())
            end['records_sha256'] = report.sha(folder / 'development.records.jsonl')
            self.write_json(folder, 'development.completion.json', end)
            with self.assertRaisesRegex(ValueError, 'saved projection differs'):
                report.build(root)

    def test_claimed_phase_does_not_change_public_report_before_terminal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); self.copy_sources(root)
            before = report.build(root)
            folder = root / report.BASE / 'openjev-fixed/fresh1/P0'
            folder.mkdir(parents=True)
            self.write_json(folder, 'smoke.claim.json', {'claimed': True})
            (folder / 'smoke.raw.jsonl').write_bytes(b'{partial')
            (folder / 'smoke.journal.jsonl').write_text('{"event":"started"}\n')
            result = report.build(root)
            self.assertEqual(result, before)
            config = result['configurations']['fixed']
            self.assertEqual(config['freshPasses'], {})
            self.assertEqual(config['missingPasses'][0]['status'], 'not_completed')

    def test_stopped_smoke_preserves_unknown_id_without_scoring(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = self.copy_sources(root)
            folder = self.create_closed(root, plan)
            for name in ('development.root-review.json', 'development.claim.json',
                         'development.raw.jsonl', 'development.records.jsonl',
                         'development.journal.jsonl', 'development.completion.json',
                         'smoke-inspection.json'):
                (folder / name).unlink()
            raw = report.rows(root, report.BASE / 'openjev-fixed/fresh1/P0/smoke.raw.jsonl')[0]
            raw['http_status'] = 503
            raw['body_base64'] = base64.b64encode(b'service unavailable').decode()
            self.write_jsonl(folder, 'smoke.raw.jsonl', [raw])
            self.write_jsonl(folder, 'smoke.records.jsonl', [])
            self.write_jsonl(folder, 'smoke.journal.jsonl', [
                {'event': 'started', 'id': 'DEV-001', 'attempt_id': raw['attempt_id'],
                 'request_sha256': raw['request_sha256']},
                {'event': 'stopped_unknown', 'id': 'DEV-001', 'attempt_id': raw['attempt_id']}])
            end = json.loads((folder / 'smoke.completion.json').read_text())
            end.update(status='stopped', reason='OpenJev HTTP status 503', count=0,
                       attempted=1, raw_sha256=report.sha(folder / 'smoke.raw.jsonl'),
                       records_sha256=report.sha(folder / 'smoke.records.jsonl'),
                       journal_sha256=report.sha(folder / 'smoke.journal.jsonl'))
            self.write_json(folder, 'smoke.completion.json', end)
            result = report.build(root)['configurations']['fixed']
            self.assertEqual(result['freshPasses'], {})
            stopped = result['missingPasses'][0]
            self.assertEqual(stopped['status'], 'stopped')
            self.assertEqual(stopped['startedIds'], ['DEV-001'])
            self.assertEqual(stopped['unknownStartedIds'], ['DEV-001'])
            self.assertEqual(stopped['savedIds'], [])
            self.assertEqual(stopped['failedIds'], ['DEV-001'])

    def test_historical_source_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); plan = self.copy_sources(root)
            source = root / plan['historical']['thinking']['directory'] / 'development.jsonl'
            source.write_bytes(source.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'Source hash differs'):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
