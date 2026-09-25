import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_gemini_openrouter_report_v1 as report
from openrouter_benchmark import allowed_returned_models


class GeminiHostedReport(unittest.TestCase):
    def fixture(self, folder, invalid_batch=1):
        original = report.ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0/manifest.json'
        (folder / 'manifest.json').write_bytes(original.read_bytes())
        manifest = json.loads(original.read_text())
        manifest_sha = report.sha(original.read_bytes())
        endpoint = next(e for e in json.loads(report.bound(manifest['endpoints']).read_text())['data']['endpoints']
                        if e.get('tag') == report.PROVIDER)
        for phase, plans in (('smoke', manifest['requests'][:1]), ('development', manifest['requests'][1:])):
            attempts, records, journal = [], [], []
            for index, plan in enumerate(plans):
                batch_index = index if phase == 'smoke' else index + 1
                ids = plan['record_ids']
                attempt_id = f'{phase}-{index}'
                generation_id = f'gen-{phase}-{index}'
                invalid = phase == 'development' and batch_index == invalid_batch
                predictions = {ident: {'sentiment': 'positive', 'follow_up_needed': 'no',
                                       'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
                               for ident in ids}
                content = 'not json' if invalid else json.dumps({'records': [{'id': ident, **predictions[ident]} for ident in ids]})
                usage = {'prompt_tokens': 10, 'completion_tokens': 2, 'cost': 0.001,
                         'prompt_tokens_details': {'cached_tokens': 1},
                         'completion_tokens_details': {'reasoning_tokens': 0}}
                raw = {'id': generation_id, 'model': manifest['model'], 'provider': report.PROVIDER_NAME,
                       'usage': usage, 'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}
                status = 'invalid_output' if invalid else 'ok'
                attempt = {'attempt_id': attempt_id, 'phase': phase, 'batch_index': batch_index,
                           'ids': ids, 'started_utc': '2026-09-25T00:00:00Z',
                           'model': manifest['model'], 'effort': manifest['effort'],
                           'provider': report.PROVIDER, 'requested_endpoint': endpoint,
                           'request': plan['payload'], 'request_sha256': plan['payload_sha256'],
                           'reserved_cost_usd': plan['reserve_usd'], 'reference_labels_read': False,
                           'manifest_sha256': manifest_sha, 'raw_response': raw,
                           'generation_id': generation_id, 'returned_model': manifest['model'],
                           'returned_provider': report.PROVIDER_NAME, 'usage': usage,
                           'generation_metadata': {'id': generation_id, 'model': manifest['model'],
                                                   'provider_name': report.PROVIDER_NAME,
                                                   'generation_time': 1000 + index*100,
                                                   'total_cost': 0.001},
                           'allowed_returned_models': sorted(allowed_returned_models(manifest['model'], endpoint)),
                           'status': status, 'observed_cost_usd': '0.001',
                           'cost_unknown': False, 'billing_ok': True}
                if not invalid:
                    attempt['predictions'] = predictions
                attempts.append(attempt)
                journal.extend((
                    {'event': 'intent', 'phase': phase, 'ids': ids,
                     'payload_sha256': plan['payload_sha256'], 'reserve_usd': plan['reserve_usd']},
                    {'event': 'started', 'attempt_id': attempt_id, 'ids': ids,
                     'started_utc': attempt['started_utc']},
                    {'event': 'finished', 'attempt_id': attempt_id, 'status': status, 'billing_ok': True}))
                for pos, ident in enumerate(ids):
                    records.append({'id': ident, 'phase': phase, 'status': status,
                                    'prediction': None if invalid else predictions[ident],
                                    'model': manifest['model'], 'effort': manifest['effort'],
                                    'batch_index': batch_index, 'batch_size': len(ids), 'batch_position': pos,
                                    'generation_id': generation_id,
                                    'request_sha256': plan['payload_sha256']})
            journal.append({'event': 'terminal', 'phase': phase, 'expected_batches': len(plans),
                            'started_batches': len(plans), 'finished_batches': len(plans),
                            'completed': True, 'reason': 'completed'})
            for name, data in ((f'{phase}-attempts.jsonl', attempts),
                               (f'{phase}-records.jsonl', records),
                               (f'{phase}-journal.jsonl', journal)):
                (folder / name).write_text(''.join(json.dumps(row) + '\n' for row in data))

    def test_closed_report_counts_batches_once_and_retains_invalid_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.fixture(folder)
            real_binding = report.binding
            def test_binding(path):
                path = Path(path)
                if path.is_relative_to(folder):
                    return {'path': str(path), 'sha256': report.sha(path.read_bytes())}
                return real_binding(path)
            with mock.patch.object(report, 'binding', side_effect=test_binding):
                result = report.build(folder)
            self.assertEqual(len(result['public_runs']), 1)
            self.assertEqual(len(result['public_cases']), 60)
            run = result['public_runs'][0]
            self.assertEqual(run['valid'], 50)
            self.assertEqual(run['tokens']['input'], 60)
            self.assertEqual(run['tokens']['output'], 12)
            self.assertEqual(run['cost']['actualUsd'], 0.006)
            self.assertEqual(run['timing']['providerGenerationReportedRequests'], 6)
            self.assertIsNone(run['timing']['inferenceSeconds'])
            self.assertEqual(sum(c['status'] == 'invalid_output' for c in result['public_cases']), 10)
            attempt_file = folder / 'development-attempts.jsonl'
            saved_attempts = report.rows(attempt_file)
            saved_attempts[0].pop('generation_metadata')
            attempt_file.write_text(''.join(json.dumps(row) + '\n' for row in saved_attempts))
            with mock.patch.object(report, 'binding', side_effect=test_binding):
                reduced = report.build(folder)
            self.assertEqual(reduced['public_runs'][0]['timing']['providerGenerationReportedRequests'], 5)
            journal = folder / 'development-journal.jsonl'
            journal.write_text('\n'.join(journal.read_text().splitlines()[:-1]) + '\n')
            with mock.patch.object(report, 'binding', side_effect=test_binding):
                with self.assertRaisesRegex(ValueError, 'closed 6-batch terminal'):
                    report.build(folder)

    def test_real_smoke_recovery_is_hash_bound(self):
        folder = report.ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0'
        manifest_path = folder / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        records, attempts, durations = report._validate_phase(
            folder, manifest, report.sha(manifest_path.read_bytes()), 'smoke',
            report.read_rows(report.ROOT / 'data/pilot/inputs.jsonl'), [])
        self.assertEqual([r['status'] for r in records], ['ok'] * 3)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(durations, [1.209])

    def test_real_development_prefix_recovery_is_hash_bound(self):
        folder = report.ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0'
        manifest = json.loads((folder / 'manifest.json').read_text())
        attempt = report.rows(folder / 'development-attempts.jsonl')[0]
        source = []
        metadata = report._metadata(attempt, folder, 'development', source, manifest)
        self.assertEqual(metadata['id'], attempt['generation_id'])
        self.assertEqual(len(source), 2)


if __name__ == '__main__':
    unittest.main()
