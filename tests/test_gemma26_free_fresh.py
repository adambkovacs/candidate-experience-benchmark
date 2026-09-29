"""Offline protocol checks for the distinct free-route Gemma series."""
import io
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gemma26_free_fresh_study as study
import gemma26_free_fresh_execution as run
import openrouter_free_quota_v1 as quota
from development_benchmark import digest


PREDICTION = {'sentiment': 'neutral', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'no'}


def endpoint(price='0', context=262144, parameters=None):
    return {'model_id': study.MODEL, 'tag': study.PROVIDER,
            'provider_name': study.PROVIDER_NAME, 'quantization': 'unknown',
            'status': 0, 'context_length': context, 'max_completion_tokens': 32768,
            'pricing': {'prompt': price, 'completion': '0'},
            'supported_parameters': parameters or ['reasoning', 'include_reasoning',
                                                   'response_format', 'max_tokens', 'temperature']}


def response():
    return {'model': study.MODEL, 'provider': study.PROVIDER_NAME,
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'cost': 0},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(PREDICTION)}}]}


class HTTPResponse:
    def __init__(self, body, status=200):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {'content-type': 'application/json', 'content-length': str(len(body))}

    def read(self, n=-1):
        return self.body.read(n)

    def close(self):
        self.body.close()


def quota_worker(path, stage, event, queue):
    event.wait()
    try:
        quota.admit_stage(stage, 60, path=Path(path), provider_remaining=1000)
        queue.put('admitted')
    except ValueError:
        queue.put('rejected')


class FreeGemmaTests(unittest.TestCase):
    def test_actual_plan_rebuild_preserves_prompts_order_and_isolates_route(self):
        plan = study.plan_data('fresh1')
        self.assertEqual(plan['condition_order'], ['P0', 'P1', 'P2'])
        self.assertEqual(plan['configuration_id'], study.CONFIG)
        self.assertEqual(plan['historical_deepinfra_status'].split('_')[0], 'unexecuted')
        for condition in ('P0', 'P1', 'P2'):
            dev = plan['conditions'][condition]['development']
            self.assertEqual([x['record_id'] for x in dev], [f'DEV-{i:03}' for i in range(1, 61)])
            self.assertEqual(len(plan['conditions'][condition]['smoke']), 3)
            for request in dev:
                payload = request['payload']
                self.assertEqual(payload['model'], study.MODEL)
                self.assertEqual(payload['provider']['only'], [study.PROVIDER])
                self.assertFalse(payload['provider']['allow_fallbacks'])
                self.assertEqual(set(payload['provider']['max_price'].values()), {0})
                self.assertEqual(payload['reasoning'], {'enabled': True})
                self.assertTrue(payload['response_format']['json_schema']['strict'])
                self.assertEqual(digest(json.dumps(payload, sort_keys=True)), request['request_sha256'])
                self.assertEqual([x['role'] for x in payload['messages']], ['system', 'user'])
                self.assertEqual(set(json.loads(payload['messages'][1]['content'])), {'feedback'})

    def test_free_endpoint_zero_price_and_exact_route(self):
        catalog = {'data': [{'id': study.MODEL, 'pricing': {'prompt': '0', 'completion': '0'},
                             'reasoning': {'mandatory': False, 'default_enabled': False}}]}
        endpoints = {'data': {'id': study.MODEL, 'endpoints': [endpoint()]}}
        self.assertEqual(run.free_endpoint(catalog, endpoints)[1]['tag'], study.PROVIDER)
        endpoints['data']['endpoints'][0]['pricing']['request'] = '0.01'
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            run.free_endpoint(catalog, endpoints)
        endpoints['data']['endpoints'][0] = endpoint(parameters=['reasoning', 'temperature'])
        with self.assertRaisesRegex(ValueError, 'controls'):
            run.free_endpoint(catalog, endpoints)
        endpoints['data']['endpoints'][0] = endpoint(context=131072)
        with self.assertRaisesRegex(ValueError, 'capacity'):
            run.free_endpoint(catalog, endpoints)

    def test_account_readonly_eligibility_fails_closed(self):
        def fetch(path, **_):
            return {'data': {'is_free_tier': False, 'free_model_daily_requests':
                             {'limit': 1000, 'remaining': 567}}} if path == '/key' else {'data': {'total_credits': 10}}
        with patch.object(run.transport, 'fetch', side_effect=fetch):
            self.assertEqual(run.account_eligible('private-token'), 567)
        with patch.object(run.transport, 'fetch', side_effect=lambda p, **_: {
                'data': {'is_free_tier': True, 'free_model_daily_requests':
                         {'limit': 1000, 'remaining': 567}} if p == '/key' else {'total_credits': 10}}):
            with self.assertRaisesRegex(ValueError, 'tier'):
                run.account_eligible('private-token')
        with patch.object(run.transport, 'fetch', side_effect=lambda p, **_: {
                'data': {'is_free_tier': False, 'free_model_daily_requests':
                         {'limit': 1000, 'remaining': 567}} if p == '/key' else {'total_credits': 9.99}}):
            with self.assertRaisesRegex(ValueError, 'tier'):
                run.account_eligible('private-token')
        with patch.object(run.transport, 'fetch', side_effect=lambda p, **_: {
                'data': {'is_free_tier': False} if p == '/key' else {'total_credits': 10}}):
            with self.assertRaisesRegex(ValueError, 'remaining capacity'):
                run.account_eligible('private-token')

    def _fake_plan(self):
        base = study.plan_data('fresh1')
        first = base['conditions']['P0']['smoke']
        base['conditions']['P0']['smoke'] = first
        return base

    def _run_smoke(self, temp, bodies):
        evidence = Path(temp) / 'private-evidence'
        evidence.mkdir(mode=0o700)
        quota_path = Path(temp) / 'shared-quota' / 'events.jsonl'
        real_admit, real_start = quota.admit_stage, quota.start_call
        fake_time = [time.time()]
        def advance():
            fake_time[0] += 4
            return fake_time[0]
        review = Path(temp) / 'root-review.json'
        review.write_text('{"synthetic":true}')
        review.chmod(0o600)
        plan = self._fake_plan()
        fake_base = Path(temp) / 'fake-plans'
        fake_plan_path = fake_base / 'fresh1' / 'manifest.json'
        fake_plan_path.parent.mkdir(parents=True)
        fake_plan_path.write_text(json.dumps(plan))
        plan_sha = study.sha(fake_plan_path)
        responses = [HTTPResponse(x) for x in bodies]
        with patch.object(study, 'verify', return_value=plan), \
             patch.object(run, 'review_receipt', return_value=({'approved': True}, evidence)), \
             patch.object(run, 'live_controls', return_value=({'id': study.MODEL}, endpoint())), \
             patch.object(run.transport, 'load_key', return_value='private-token'), \
             patch.object(run, 'account_eligible', return_value=1000), \
             patch.object(run.transport.OPENER, 'open', side_effect=responses), \
             patch.object(quota, 'admit_stage', side_effect=lambda stage, count, provider_remaining: real_admit(stage, count, path=quota_path, provider_remaining=provider_remaining)), \
             patch.object(quota, 'start_call', side_effect=lambda stage, rid: real_start(stage, rid, path=quota_path, clock=advance, sleep=lambda _: None)):
            result = run.execute('fresh1', 'P0', 'smoke', plan_sha, str(review))
        folder, files = run.paths(evidence, 'fresh1', 'P0', 'smoke')
        return result, folder, files, quota_path, fake_base, plan_sha

    def test_real_bounded_transport_closes_three_valid_smoke_calls_privately(self):
        with tempfile.TemporaryDirectory() as temp:
            body = json.dumps(response()).encode()
            done, folder, files, quota_path, fake_base, _ = self._run_smoke(temp, [body] * 3)
            self.assertTrue(done)
            self.assertEqual(len(run.rows(files['attempts'])), 3)
            self.assertEqual(len(run.rows(files['wire'])), 3)
            self.assertEqual(run.rows(files['attempts'])[0]['observed_cost_usd'], '0')
            self.assertEqual(run.rows(files['attempts'])[0]['cost_observation_status'], 'returned_zero')
            self.assertEqual(files['attempts'].stat().st_mode & 0o077, 0)
            self.assertTrue(files['completion'].exists())
            self.assertEqual(len([x for x in run.rows(quota_path) if x['event'] == 'call_started']), 3)
            with patch.object(study, 'verify', return_value=self._fake_plan()), \
                 patch.object(study, 'BASE', fake_base):
                self.assertEqual(run.verify_closed(Path(temp) / 'private-evidence',
                                                   'fresh1', 'P0', 'smoke')['wire_sha256'], study.sha(files['wire']))

    def test_malformed_200_is_saved_before_parse_and_cannot_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            malformed = b'{"choices": ['
            done, folder, files, _, _, plan_sha = self._run_smoke(temp, [malformed])
            self.assertFalse(done)
            wire = run.rows(files['wire'])
            self.assertEqual(len(wire), 1)
            self.assertEqual(wire[0]['http_status'], 200)
            self.assertEqual(len(run.rows(files['attempts'])), 1)
            self.assertEqual(run.rows(files['attempts'])[0]['status'], 'service_error')
            self.assertFalse(files['completion'].exists())
            with patch.object(study, 'verify', return_value=self._fake_plan()), \
                 patch.object(run, 'review_receipt', return_value=({'approved': True}, Path(temp) / 'private-evidence')), \
                 patch.object(run, 'live_controls', return_value=({'id': study.MODEL}, endpoint())), \
                patch.object(run.transport, 'load_key', return_value='private-token'), \
                 patch.object(run, 'account_eligible', return_value=1000):
                with self.assertRaises(FileExistsError):
                    run.execute('fresh1', 'P0', 'smoke', plan_sha, str(Path(temp) / 'root-review.json'))

    def test_positive_returned_cost_stops_stage_even_on_free_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            value = response(); value['usage']['cost'] = 0.001
            done, _, files, _, _, _ = self._run_smoke(temp, [json.dumps(value).encode()])
            self.assertFalse(done)
            row = run.rows(files['attempts'])[0]
            self.assertEqual(row['status'], 'billing_violation')
            self.assertEqual(row['observed_cost_usd'], '0.001')

    def test_shared_quota_reserves_whole_phases_and_rejects_capacity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'quota' / 'events.jsonl'
            now = time.time()
            for index in range(16):
                quota.admit_stage(f'other-free-series/{index}', 60, path=path, now=now, provider_remaining=1000)
            self.assertEqual(path.stat().st_mode & 0o077, 0)
            with self.assertRaisesRegex(ValueError, 'capacity exhausted'):
                quota.admit_stage('gemma/fresh1/P0/development', 60, path=path, now=now, provider_remaining=1000)
            quota.admit_stage('gemma/fresh1/P0/smoke', 3, path=path, now=now, provider_remaining=1000)
            with self.assertRaisesRegex(ValueError, 'already reserved'):
                quota.admit_stage('gemma/fresh1/P0/smoke', 3, path=path, now=now, provider_remaining=1000)

    def test_shared_minute_gate_rejects_replay_and_counts_other_series(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'quota' / 'events.jsonl'
            now = time.time()
            quota.admit_stage('gemma/smoke', 3, path=path, now=now, provider_remaining=1000)
            quota.admit_stage('qwen/smoke', 3, path=path, now=now, provider_remaining=1000)
            clock = [now]
            def tick():
                clock[0] += 4
                return clock[0]
            quota.start_call('gemma/smoke', 'DEV-001', path=path, clock=tick, sleep=lambda _: None)
            quota.start_call('qwen/smoke', 'DEV-001', path=path, clock=tick, sleep=lambda _: None)
            with self.assertRaisesRegex(ValueError, 'replayed'):
                quota.start_call('gemma/smoke', 'DEV-001', path=path, clock=tick, sleep=lambda _: None)
            self.assertEqual(len([x for x in run.rows(path) if x['event'] == 'call_started']), 2)

    def test_provider_remaining_includes_all_outstanding_free_series(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'quota' / 'events.jsonl'
            now = time.time()
            quota.admit_stage('gemma/development', 60, path=path, now=now, provider_remaining=60)
            with self.assertRaisesRegex(ValueError, 'Provider free-model daily capacity'):
                quota.admit_stage('qwen/smoke', 3, path=path, now=now, provider_remaining=60)
            quota.start_call('gemma/development', 'DEV-001', path=path,
                             clock=lambda: now + .001, sleep=lambda _: None)
            # The provider's remaining count now reflects that one started call.
            with self.assertRaisesRegex(ValueError, 'Provider free-model daily capacity'):
                quota.admit_stage('qwen/smoke', 3, path=path, now=now + .002,
                                  provider_remaining=59)

    def test_shared_quota_lock_is_atomic_across_processes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'quota' / 'events.jsonl'
            for index in range(15):
                quota.admit_stage(f'existing/{index}', 60, path=path, provider_remaining=1000)
            context = multiprocessing.get_context('spawn')
            event, queue = context.Event(), context.Queue()
            processes = [context.Process(target=quota_worker, args=(str(path), f'parallel/{i}', event, queue))
                         for i in range(2)]
            for process in processes:
                process.start()
            event.set()
            outcomes = sorted(queue.get(timeout=5) for _ in processes)
            for process in processes:
                process.join(timeout=5)
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(outcomes, ['admitted', 'rejected'])


if __name__ == '__main__':
    unittest.main()
