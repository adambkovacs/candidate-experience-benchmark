import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import affordable_hosted_repeat_admission as admission
import affordable_hosted_repeat_execution as runner
from development_benchmark import digest
from openrouter_budget_v2 import BudgetLedger


class ExecutionTests(unittest.TestCase):
    def test_simulated_successful_smoke_executes_three_calls_and_verifies(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            directory = Path(temp)
            child = directory / 'child.jsonl'
            review_path, budget_path = directory / 'review.json', directory / 'budget.json'
            review_path.write_text('{}')
            budget_path.write_text('{}')
            manifest = admission.plan_data()
            phase = manifest['phases'][0]
            p = runner.paths(directory, 0, 'smoke')
            _, _, endpoint, model = admission.source_state()
            prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                          'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
            response = {'model': admission.MODEL, 'provider': endpoint['provider_name'],
                        'usage': {'cost': '0.001'},
                        'choices': [{'message': {'content': json.dumps(prediction)},
                                     'finish_reason': 'stop'}]}
            calls = []

            def fetch(path, *args, **kwargs):
                if path == '/models':
                    return {'data': [model]}
                if path.endswith('/endpoints'):
                    return {'data': {'id': admission.MODEL, 'endpoints': [endpoint]}}
                self.assertEqual(path, '/chat/completions')
                calls.append(args[1])
                return response

            def open_child(*args):
                return BudgetLedger(child, cap_limit=admission.CAP)

            with patch.object(runner, 'prepare', return_value=(manifest, phase, p)), \
                 patch.object(runner, 'verify_sources'), \
                 patch.object(runner.paid, 'fetch', side_effect=fetch), \
                 patch.object(runner.paid, 'load_key', return_value='test-token'), \
                 patch.object(runner.partitions, 'open_partition', side_effect=open_child):
                result = runner.execute('unused', 'manifest-sha', budget_path, 'child', 0,
                                        'smoke', review_path, directory)

            self.assertEqual(result, {'completed': True, 'count': 3})
            self.assertEqual(len(calls), 3)
            self.assertEqual([r['id'] for r in jsonl(p['records'])], phase['smoke_ids'])
            self.assertEqual([e['event'] for e in jsonl(p['journal'])],
                             ['stage_claimed'] + ['request_started', 'raw_saved', 'request_finished'] * 3
                             + ['stage_completed'])
            for record in jsonl(p['records']):
                self.assertGreaterEqual(record['client_http_duration_seconds'], 0)
                self.assertTrue(math.isfinite(record['client_http_duration_seconds']))
                self.assertLessEqual(record['client_request_started_utc'],
                                     record['client_request_finished_utc'])
            self.assertTrue(runner.finished(manifest, directory, 0, 'smoke',
                                            'manifest-sha', runner.sha(budget_path), 'child'))
            records = jsonl(p['records'])
            records[0]['client_http_duration_seconds'] = float('nan')
            p['records'].write_text(''.join(json.dumps(record) + '\n' for record in records))
            self.assertFalse(runner.finished(manifest, directory, 0, 'smoke',
                                             'manifest-sha', runner.sha(budget_path), 'child'))

    def test_freeze_binds_source_and_code_without_ledger_mutation(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            path = Path(temp)
            plan_path, manifest_path = path / 'plan.json', path / 'manifest.json'
            plan = admission.plan_data()
            plan_path.write_text(json.dumps(plan))
            before = hashlib.sha256(admission.MASTER.read_bytes()).hexdigest()
            manifest = runner.freeze(plan_path, manifest_path)
            self.assertEqual(before, hashlib.sha256(admission.MASTER.read_bytes()).hexdigest())
            self.assertEqual(len(manifest['code_bindings']), len(runner.CODE))
            loaded = runner.load_manifest(manifest_path, runner.sha(manifest_path))
            self.assertEqual(loaded, manifest)
            with self.assertRaises(FileExistsError):
                runner.freeze(plan_path, manifest_path)
            with patch.object(runner, 'sha', side_effect=lambda p: 'drift' if Path(p).name == 'openrouter_paid_benchmark.py' else runner_sha(p)):
                with self.assertRaisesRegex(ValueError, 'Execution code drift'):
                    runner.verify_sources(manifest)

    def test_development_requires_clean_exact_inspected_smoke(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            directory = Path(temp)
            manifest = fixture_manifest()
            with self.assertRaisesRegex(ValueError, 'Smoke is not terminal'):
                inspect(manifest, directory, 0, 'development', {})
            p = write_stage(manifest, directory, 0, 'smoke')
            with self.assertRaisesRegex(ValueError, 'inspected smoke'):
                inspect(manifest, directory, 0, 'development', {})
            review = smoke_review(p)
            inspect(manifest, directory, 0, 'development', review)
            p['records'].write_text(p['records'].read_text().replace('"ok"', '"invalid_output"', 1))
            with self.assertRaisesRegex(ValueError, 'Smoke is not terminal'):
                inspect(manifest, directory, 0, 'development', review)

    def test_predecessors_reject_cross_manifest_partition_and_request_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            directory = Path(temp)
            manifest = fixture_manifest()
            smoke = write_stage(manifest, directory, 0, 'smoke')
            development = write_stage(manifest, directory, 0, 'development')
            current_smoke = write_stage(manifest, directory, 1, 'smoke')
            inspect(manifest, directory, 1, 'development', smoke_review(current_smoke))
            for field, bad in (('manifest_sha256', 'other-manifest'),
                               ('budget_manifest_sha256', 'other-budget'),
                               ('partition_id', 'other-partition'),
                               ('repeat', 'fresh3'), ('condition', 'P2')):
                claim = json.loads(smoke['claim'].read_text())
                claim[field] = bad
                smoke['claim'].write_text(json.dumps(claim))
                with self.assertRaisesRegex(ValueError, 'Previous phase'):
                    inspect(manifest, directory, 1, 'development', smoke_review(current_smoke))
                write_stage(manifest, directory, 0, 'smoke')
            rows = jsonl(development['records'])
            rows[0]['request_sha256'] = rows[1]['request_sha256']
            development['records'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Previous phase'):
                inspect(manifest, directory, 1, 'development', smoke_review(current_smoke))
            write_stage(manifest, directory, 0, 'development')
            raw_rows = jsonl(development['raw'])
            raw_rows[0]['attempt_id'] = raw_rows[1]['attempt_id']
            development['raw'].write_text(''.join(json.dumps(row) + '\n' for row in raw_rows))
            with self.assertRaisesRegex(ValueError, 'Previous phase'):
                inspect(manifest, directory, 1, 'development', smoke_review(current_smoke))

    def test_current_smoke_rejects_wrong_claim_even_with_inspection_hashes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            directory = Path(temp)
            manifest = fixture_manifest()
            smoke = write_stage(manifest, directory, 0, 'smoke')
            claim = json.loads(smoke['claim'].read_text())
            claim['partition_id'] = 'other-partition'
            smoke['claim'].write_text(json.dumps(claim))
            with self.assertRaisesRegex(ValueError, 'Smoke is not terminal'):
                inspect(manifest, directory, 0, 'development', smoke_review(smoke))

    def test_raw_reparse_and_order_are_required(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            directory = Path(temp)
            manifest = fixture_manifest()
            smoke = write_stage(manifest, directory, 0, 'smoke')
            inspect(manifest, directory, 0, 'development', smoke_review(smoke))
            raw = jsonl(smoke['raw'])
            raw[0]['body']['choices'][0]['message']['content'] = json.dumps(
                {'sentiment': 'positive', 'follow_up_needed': 'no',
                 'serious_concern_reported': 'no', 'testimonial_potential': 'no'})
            smoke['raw'].write_text(''.join(json.dumps(item) + '\n' for item in raw))
            events = jsonl(smoke['journal'])
            for position in range(3):
                events[2 + 3 * position]['raw_sha256'] = hashlib.sha256(
                    ''.join(smoke['raw'].read_text().splitlines(keepends=True)[:position + 1]).encode()).hexdigest()
            smoke['journal'].write_text(''.join(json.dumps(event) + '\n' for event in events))
            with self.assertRaisesRegex(ValueError, 'Smoke is not terminal'):
                inspect(manifest, directory, 0, 'development', smoke_review(smoke))
            write_stage(manifest, directory, 0, 'smoke')
            records = jsonl(smoke['records'])
            records[0], records[1] = records[1], records[0]
            smoke['records'].write_text(''.join(json.dumps(row) + '\n' for row in records))
            with self.assertRaisesRegex(ValueError, 'Smoke is not terminal'):
                inspect(manifest, directory, 0, 'development', smoke_review(smoke))

    def test_crash_after_reservation_cannot_replay_and_retains_unknown(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            directory = Path(temp)
            child = directory / 'child.jsonl'
            review_path, budget_path = directory / 'review.json', directory / 'budget.json'
            review_path.write_text('{}')
            budget_path.write_text('{}')
            phase = {'repeat': 'fresh1', 'condition': 'P0', 'smoke_ids': ['DEV-001', 'DEV-002', 'DEV-003']}
            manifest = admission.plan_data()
            p = runner.paths(directory, 0, 'smoke')
            _, _, endpoint, model = admission.source_state()
            catalog = {'data': [model]}
            endpoints = {'data': {'id': admission.MODEL, 'endpoints': [endpoint]}}
            def fetch(path, *args, **kwargs):
                if path == '/models': return catalog
                if path.endswith('/endpoints'): return endpoints
                raise KeyboardInterrupt('simulated process death during HTTP')
            def open_child(*args):
                return BudgetLedger(child, cap_limit=admission.CAP)
            with patch.object(runner, 'prepare', return_value=(manifest, phase, p)), \
                 patch.object(runner, 'verify_sources'), \
                 patch.object(runner.paid, 'fetch', side_effect=fetch), \
                 patch.object(runner.paid, 'load_key', return_value='test-token'), \
                 patch.object(runner.partitions, 'open_partition', side_effect=open_child):
                with self.assertRaises(KeyboardInterrupt):
                    runner.execute('unused', 'manifest-sha', budget_path, 'child', 0, 'smoke', review_path, directory)
            self.assertTrue(p['claim'].exists())
            self.assertEqual(jsonl(p['journal'])[-1]['event'], 'request_started')
            ledger = BudgetLedger(child, cap_limit=admission.CAP)
            try:
                _, pending, _ = ledger.state()
                self.assertEqual(len(pending), 1)
                self.assertEqual(ledger.accounted(), admission.RESERVE)
                with self.assertRaisesRegex(ValueError, 'Unresolved charge'):
                    ledger.reserve(admission.RESERVE, 'DEV-002')
            finally:
                ledger.close()
            with patch.object(runner, 'load_manifest', return_value=manifest), \
                 patch.object(runner, 'verify_receipt', return_value={}), \
                 patch.object(runner, 'inspect_predecessors'):
                with self.assertRaises(FileExistsError):
                    runner.prepare('unused', 'manifest-sha', child, 'child', 0, 'smoke', 'unused', directory)

    def test_child_budget_hard_stops_without_overrun(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            child = Path(temp) / 'child.jsonl'
            ledger = BudgetLedger(child, cap_limit=admission.CAP)
            try:
                for i in range(4):
                    attempt = ledger.reserve(admission.RESERVE, f'DEV-{i+1:03}')
                    self.assertTrue(ledger.settle(attempt, admission.RESERVE))
                self.assertEqual(ledger.accounted(), admission.RESERVE * 4)
                with self.assertRaisesRegex(ValueError, 'cap reached'):
                    ledger.reserve(admission.RESERVE, 'DEV-005')
            finally:
                ledger.close()


def fixture_manifest():
    ids = ['DEV-001', 'DEV-002', 'DEV-003']
    requests = {}
    for condition in ('P0', 'P1'):
        requests[condition] = [
            {'id': record_id, 'request_sha256': digest(json.dumps({'id': record_id, 'condition': condition}, sort_keys=True)),
             'input_sha256': digest('input-' + record_id), 'instruction_sha256': digest('policy-' + condition)}
            for record_id in ids]
    return {'phases': [{'repeat': 'fresh1', 'condition': 'P0', 'smoke_ids': ids, 'development_ids': ids},
                       {'repeat': 'fresh1', 'condition': 'P1', 'smoke_ids': ids, 'development_ids': ids}],
            'requests_by_condition': requests,
            'route': {'provider_name': 'OpenInference', 'quantization': 'fp4'}}


def write_stage(manifest, directory, index, stage):
    phase = manifest['phases'][index]
    ids = phase['smoke_ids'] if stage == 'smoke' else phase['development_ids']
    p = runner.paths(directory, index, stage)
    claim = {'schema': 'affordable-hosted-stage-claim-v1', 'manifest_sha256': 'manifest-sha',
             'review_sha256': 'a' * 64, 'budget_manifest_sha256': 'budget-sha',
             'partition_id': 'child', 'phase_index': index, 'repeat': phase['repeat'],
             'condition': phase['condition'], 'stage': stage, 'ids': ids}
    p['claim'].write_text(json.dumps(claim))
    events = [{'event': 'stage_claimed', 'claim_sha256': runner.sha(p['claim'])}]
    raw_lines = []
    records = []
    endpoint = {'tag': admission.PROVIDER, 'provider_name': 'OpenInference',
                'quantization': 'fp4', 'model_id': admission.MODEL}
    prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                  'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
    for number, record_id in enumerate(ids):
        attempt = f'attempt-{index}-{stage}-{number}'
        request = {'id': record_id, 'condition': phase['condition']}
        frozen = manifest['requests_by_condition'][phase['condition']][number]
        body = {'model': admission.MODEL, 'provider': 'OpenInference',
                'usage': {'cost': '0.001'},
                'choices': [{'message': {'content': json.dumps(prediction)}, 'finish_reason': 'stop'}]}
        raw_lines.append(json.dumps({'attempt_id': attempt, 'id': record_id, 'body': body}) + '\n')
        record = {'id': record_id, 'repeat': phase['repeat'], 'condition': phase['condition'],
                  'phase': stage, 'attempt_id': attempt, 'request': request,
                  'request_sha256': frozen['request_sha256'], 'input_sha256': frozen['input_sha256'],
                  'policy_sha256': frozen['instruction_sha256'], 'requested_model': admission.MODEL,
                  'provider_endpoint': endpoint, 'raw_response': body, 'usage': body['usage'],
                  'returned_model': admission.MODEL, 'returned_provider': 'OpenInference',
                  'finish_reason': 'stop', 'prediction': prediction, 'status': 'ok',
                  'reference_labels_read': False, 'reserved_cost_usd': str(admission.RESERVE),
                  'budget_partition_id': 'child', 'reasoning_effort': 'off',
                  'client_request_started_utc': '2026-09-29T10:00:00+00:00',
                  'client_request_finished_utc': '2026-09-29T10:00:01+00:00',
                  'client_http_duration_seconds': 0.5,
                  'observed_cost_usd': '0.001', 'cost_unknown': False, 'billing_ok': True}
        records.append(record)
        events.extend([{'event': 'request_started', 'attempt_id': attempt, 'id': record_id,
                        'request_sha256': frozen['request_sha256'],
                        'reserved_cost_usd': str(admission.RESERVE)},
                       {'event': 'raw_saved', 'attempt_id': attempt,
                        'raw_sha256': hashlib.sha256(''.join(raw_lines).encode()).hexdigest()},
                       {'event': 'request_finished', 'attempt_id': attempt, 'id': record_id,
                        'status': 'ok', 'billing_ok': True}])
    events.append({'event': 'stage_completed', 'count': len(ids)})
    p['raw'].write_text(''.join(raw_lines))
    p['records'].write_text(''.join(json.dumps(record) + '\n' for record in records))
    p['journal'].write_text(''.join(json.dumps(event) + '\n' for event in events))
    return p


def smoke_review(p):
    return {'smoke_inspection': {'approved': True, 'smoke_records_sha256': runner.sha(p['records']),
            'smoke_journal_sha256': runner.sha(p['journal']), 'smoke_raw_sha256': runner.sha(p['raw']),
            'statuses': ['ok'] * 3}}


def inspect(manifest, directory, index, stage, review):
    return runner.inspect_predecessors(manifest, directory, index, stage, review,
                                       'manifest-sha', 'budget-sha', 'child')


def runner_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


if __name__ == '__main__': unittest.main()
