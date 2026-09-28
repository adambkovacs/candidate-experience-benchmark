"""Synthetic, offline generated-report evidence tests; no model or server starts."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import build_openjev_generated_repeat_findings as report


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, sort_keys=True) + '\n' for v in values))


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GeneratedReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((report.ROOT / report.MANIFEST).read_text())
        original = next(Path(n).parent.parent for n in self.plan['source_sha256']
                        if Path(n).name == 'openjev_generated_repeat_admission_v2.py')
        copies = [report.MANIFEST, report.LABELS,
                  Path('results/prompt-comparison-v1-2026-09-24/openjev-generated-exact-v1/execution-manifest.draft.json'),
                  Path('results/prompt-comparison-v1-2026-09-24/openjev-generated-exact-v1/preflight.json')]
        copies += [Path(p).relative_to(original) for p in self.plan['source_sha256']]
        copies += [Path(v['path']) for m in report.MODES
                   for v in self.plan['historical'][m]['conditions'].values()]
        for relative in set(copies):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(report.ROOT / relative, target)
        self.labels = {r['id']: r['proposed_labels']
                       for r in report.rows(self.root, report.LABELS)}

    def phase(self, phase='generated-off/fresh1/P0', stage='smoke', count=None,
              length_at=None, unknown_at=None, predecessor=None, flip_first=False,
              omit_unknown_raw=False):
        count = count or (3 if stage == 'smoke' else 60)
        folder = self.root / report.BASE / phase
        folder.mkdir(parents=True, exist_ok=True)
        mode, _, condition = phase.split('/')
        planned = self.plan['requests'][mode][condition]
        review = {'kind': 'root-reviewed-openjev-generated-stage-v2',
            'approved': True, 'phase': phase, 'stage': stage,
            'plan_sha256': report.MANIFEST_SHA,
            'controller_sha256': report.controller_sha(self.plan),
            'predecessor_sha256': predecessor, 'reference_labels_read': False,
            'source_commit': self.plan['runtime']['source_commit'],
            'artifact_manifest_sha256': self.plan['artifact_manifest_sha256'],
            'historical_preflight_sha256': self.plan['historical_preflight_sha256'],
            'server_policy': self.plan['runtime']['cache_policy']}
        write_json(folder / f'{stage}.root-review.json', review)
        receipt_sha = hash_file(folder / f'{stage}.root-review.json')
        write_json(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
            'plan_sha256': report.MANIFEST_SHA,
            'controller_sha256': report.controller_sha(self.plan),
            'receipt_sha256': receipt_sha, 'reference_labels_read': False})
        write_json(folder / f'{stage}.server-attestation.json', {
            'kind': 'openjev-generated-server-launch-observation-v2',
            'phase': phase, 'stage': stage,
            'source_commit': self.plan['runtime']['source_commit'],
            'artifact_manifest_sha256': self.plan['artifact_manifest_sha256'],
            'configured_server_env': self.plan['runtime']['server_env'],
            'configured_upstream_model_default': 'dgemma',
            'logical_response_model': 'diffusiongemma-26b',
            'cache_policy': self.plan['runtime']['cache_policy'],
            'health_observed': True, 'loaded_settings_measured': False,
            'live_rendered_token_ids_measured': False})
        journal, raw, records = [], [], []
        for index, item in enumerate(planned[:count]):
            rid = item['id']
            attempt = f'synthetic-{stage}-{rid}'
            journal.append({'event': 'started', 'id': rid, 'attempt_id': attempt,
                            'request_sha256': item['request_sha256'],
                            'wire_body_sha256': item['wire_body_sha256']})
            if index == unknown_at:
                if not omit_unknown_raw:
                    raw.append({'id': rid, 'attempt_id': attempt,
                                'request_sha256': item['request_sha256'],
                                'error_type': 'IncompleteRead', 'elapsed_seconds': 0.25})
                journal.append({'event': 'stopped_unknown', 'id': rid, 'attempt_id': attempt})
                break
            finish = 'length' if index == length_at else 'stop'
            prediction = dict(self.labels[rid])
            if flip_first and index == 0:
                prediction['sentiment'] = ('negative' if prediction['sentiment'] != 'negative'
                                            else 'positive')
            response = {'model': 'diffusiongemma-26b',
                        'usage': {'prompt_tokens': item['input_tokens'], 'completion_tokens': 12},
                        'choices': [{'finish_reason': finish,
                                     'message': {'content': json.dumps(prediction)}}]}
            from openjev_prompt_execution import parse_native_response
            decision = parse_native_response(response, item['input_tokens'])
            raw.append({'id': rid, 'attempt_id': attempt,
                'request_sha256': item['request_sha256'],
                'wire_body_sha256': item['wire_body_sha256'],
                'offline_rendered_token_ids_sha256': item['offline_rendered_token_ids_sha256'],
                'input_tokens': item['input_tokens'], 'http_status': 200,
                'headers': {}, 'body_base64': base64.b64encode(json.dumps(response).encode()).decode(),
                'truncated': False, 'incomplete': False, 'elapsed_seconds': 0.25})
            records.append({'id': rid, 'attempt_id': attempt,
                            'request_sha256': item['request_sha256'],
                            'decision': decision, 'reference_labels_read': False})
            journal.append({'event': 'finished', 'id': rid, 'attempt_id': attempt,
                            'status': decision['status']})
        for kind, values in (('journal', journal), ('raw', raw), ('records', records)):
            write_rows(folder / f'{stage}.{kind}.jsonl', values)
        stopped = unknown_at is not None
        write_json(folder / f'{stage}.completion.json', {
            'phase': phase, 'stage': stage, 'status': 'stopped' if stopped else 'completed',
            'reason': 'IncompleteRead' if stopped else None,
            'count': len(records), 'attempted': len(journal) - len(records) - int(stopped),
            'plan_sha256': report.MANIFEST_SHA, 'receipt_sha256': receipt_sha,
            'server_attestation_sha256': hash_file(folder / f'{stage}.server-attestation.json'),
            **{kind + '_sha256': hash_file(folder / f'{stage}.{kind}.jsonl')
               for kind in ('journal', 'raw', 'records')}})
        if stage == 'smoke' and not stopped:
            declarations = []
            for row in records:
                item = {'id': row['id'], 'status': row['decision']['status'],
                        'prediction': row['decision']['prediction']}
                if item['status'] == 'invalid_output':
                    item.update({'accepted_unchanged': True, 'inspection_reason': 'synthetic length'})
                declarations.append(item)
            write_json(folder / 'smoke-inspection.json', {
                'kind': 'openjev-generated-smoke-inspection-v1',
                'approved': True, 'phase': phase, 'plan_sha256': report.MANIFEST_SHA,
                'reference_labels_read': False, 'records': declarations,
                'raw_sha256': hash_file(folder / 'smoke.raw.jsonl'),
                'records_sha256': hash_file(folder / 'smoke.records.jsonl')})
        return folder

    def closed(self, length_at=None, phase='generated-off/fresh1/P0', flip_first=False):
        folder = self.phase(phase, 'smoke', length_at=0 if length_at == 0 else None,
                            flip_first=flip_first)
        self.phase(phase, 'development', length_at=length_at,
                   predecessor=hash_file(folder / 'smoke-inspection.json'),
                   flip_first=flip_first)
        return folder

    def test_empty_report_is_relocated_and_historical_separate(self):
        output = report.build(self.root)
        self.assertEqual(len(output['configurations']['generated-off']['missingPhases']), 9)
        self.assertEqual(output['configurations']['generated-off']['historicalObservation']['status'],
                         'historical_observation_excluded_from_fresh_triplet')
        self.assertEqual(output['configurations']['generated-on']['freshPasses']['fresh1'], {})
        self.assertTrue(all(Path(b['path']).is_absolute() is False
                            for b in output['sourceBindings']))

    def test_closed_length_is_invalid_but_measured(self):
        self.closed(length_at=0)
        result = report.build(self.root)['configurations']['generated-off']
        entry = result['freshPasses']['fresh1']['P0']
        self.assertEqual(entry['score']['valid'], 59)
        self.assertEqual(entry['score']['outcomes']['invalid_output'], 1)
        self.assertEqual(entry['usage']['tokens']['output_tokens'], 720)
        self.assertEqual(entry['usage']['clientRequestSecondsTotal'], 15)
        self.assertIsNone(entry['usage']['actualCostUsd'])
        self.assertEqual(len(result['missingPhases']), 8)

    def test_raw_tamper_and_parser_mismatch_fail_closed(self):
        folder = self.closed()
        file = folder / 'development.raw.jsonl'
        rows = report.rows(self.root, file.relative_to(self.root))
        rows[0]['input_tokens'] += 1
        write_rows(file, rows)
        with self.assertRaisesRegex(ValueError, 'hashes differ'):
            report.build(self.root)
        end = json.loads((folder / 'development.completion.json').read_text())
        end['raw_sha256'] = hash_file(file)
        write_json(folder / 'development.completion.json', end)
        with self.assertRaisesRegex(ValueError, 'saved response identity'):
            report.build(self.root)

    def test_claimed_and_partial_are_unscored(self):
        phase = 'generated-off/fresh1/P0'
        folder = self.root / report.BASE / phase
        write_json(folder / 'smoke.claim.json', {'synthetic': True})
        write_rows(folder / 'smoke.journal.jsonl', [{'event': 'started', 'id': 'DEV-001'}])
        output = report.build(self.root)['configurations']['generated-off']
        self.assertEqual(output['missingPhases'][0]['status'], 'claimed_in_progress_or_interrupted')
        self.assertEqual(output['freshPasses']['fresh1'], {})

    def test_stopped_unknown_has_identity_and_no_score(self):
        self.phase('generated-off/fresh1/P0', 'smoke', unknown_at=1)
        output = report.build(self.root)['configurations']['generated-off']
        missing = output['missingPhases'][0]
        self.assertEqual(missing['status'], 'stopped_unknown')
        self.assertEqual(missing['unknownStartedIds'], ['DEV-002'])
        self.assertEqual(missing['savedIds'], ['DEV-001'])
        self.assertEqual(missing['neverSentIds'], ['DEV-003'])
        self.assertEqual(missing['usage']['requestCount'], 2)
        self.assertEqual(missing['usage']['rawCaptureCount'], 2)
        self.assertEqual(missing['usage']['rawResponseCount'], 1)
        self.assertEqual(missing['usage']['clientRequestSecondsTotal'], 0.5)
        self.assertIsNone(missing['usage']['tokens']['input_tokens'])
        self.assertIsNone(missing['usage']['tokens']['output_tokens'])
        self.assertEqual(missing['usage']['tokens']['knownSavedOutputTokens'], 12)
        self.assertIsNone(missing['usage']['tokens']['unknownAttemptTokens'])
        self.assertNotIn('score', missing)
        self.assertEqual(output['freshPasses']['fresh1'], {})

    def test_stopped_before_unknown_raw_keeps_known_subtotals_without_zero_full_totals(self):
        self.phase('generated-off/fresh1/P0', 'smoke', unknown_at=1,
                   omit_unknown_raw=True)
        missing = report.build(self.root)['configurations']['generated-off']['missingPhases'][0]
        usage = missing['usage']
        self.assertEqual(missing['startedIds'], ['DEV-001', 'DEV-002'])
        self.assertEqual(missing['rawSavedIds'], ['DEV-001'])
        self.assertEqual(missing['unknownStartedIds'], ['DEV-002'])
        self.assertEqual(missing['neverSentIds'], ['DEV-003'])
        self.assertEqual(usage['requestCount'], 2)
        self.assertEqual(usage['rawCaptureCount'], 1)
        self.assertEqual(usage['rawResponseCount'], 1)
        self.assertIsNone(usage['clientRequestSecondsTotal'])
        self.assertEqual(usage['knownClientSecondsSubtotal'], 0.25)
        self.assertIsNone(usage['tokens']['input_tokens'])
        self.assertIsNone(usage['tokens']['output_tokens'])
        self.assertEqual(usage['tokens']['knownSavedOutputTokens'], 12)

    def test_stopped_development_preserves_full_never_sent_denominator(self):
        phase = 'generated-off/fresh1/P0'
        folder = self.phase(phase, 'smoke')
        self.phase(phase, 'development', unknown_at=1,
                   predecessor=hash_file(folder / 'smoke-inspection.json'))
        output = report.build(self.root)['configurations']['generated-off']
        missing = output['missingPhases'][0]
        self.assertEqual(missing['stage'], 'development')
        self.assertEqual(missing['startedIds'], ['DEV-001', 'DEV-002'])
        self.assertEqual(missing['unknownStartedIds'], ['DEV-002'])
        self.assertEqual(missing['neverSentIds'], report.IDS[2:])
        self.assertEqual(len(missing['neverSentIds']), 58)
        self.assertEqual(missing['usage']['requestCount'], 2)
        self.assertIsNone(missing['usage']['tokens']['output_tokens'])
        self.assertEqual(output['freshPasses']['fresh1'], {})

    def test_closed_phase_after_open_predecessor_rejected(self):
        self.closed(phase='generated-off/fresh1/P1')
        with self.assertRaisesRegex(ValueError, 'Closed generated phase follows open predecessor'):
            report.build(self.root)

    def test_full_frozen_matrix_produces_pairwise_prompt_and_repeat_denominators(self):
        for phase in report.SCHEDULE:
            self.closed(phase=phase, flip_first=phase == 'generated-off/fresh1/P1')
        result = report.build(self.root)
        for mode in report.MODES:
            group = result['configurations'][mode]
            self.assertEqual(group['missingPhases'], [])
            self.assertEqual(sum(len(v) for v in group['freshPasses'].values()), 9)
            self.assertEqual(len(group['pairwiseFlips']['P0']), 3)
            self.assertEqual(group['pairwiseFlips']['P0'][0]['denominator'], 60)
            self.assertEqual(len(group['withinPassPromptDifferences']['fresh1']), 2)
            delta = group['withinPassPromptDifferences']['fresh1'][0]['netScoreDelta']['allFour']
            self.assertEqual(delta, -1 if mode == 'generated-off' else 0)
            self.assertEqual(group['changesAcrossThreePasses']['P0']['denominator'], 60)


if __name__ == '__main__':
    unittest.main()
