"""Offline checks for the separate Qwen27 ModelRun free-route series."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gemma26_free_fresh_execution as canonical
import qwen27_free_fresh_execution as execution
import qwen27_free_fresh_study as study
from development_benchmark import digest
import openrouter_free_quota_v1 as quota


class HTTPResponse:
    def __init__(self, body, status=200):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {'content-type': 'application/json', 'content-length': str(len(body))}

    def read(self, n=-1):
        return self.body.read(n)

    def close(self):
        self.body.close()


def catalog():
    return {'data': [{'id': study.MODEL, 'pricing': {'prompt': '0', 'completion': '0'},
                      'reasoning': {'mandatory': False, 'supported_efforts': ['medium', 'xhigh']}}]}


def endpoints():
    return {'data': {'id': study.MODEL, 'endpoints': [{
        'model_id': study.MODEL, 'tag': study.PROVIDER, 'provider_name': study.PROVIDER_NAME,
        'quantization': 'fp4', 'status': 0, 'context_length': 262144,
        'max_completion_tokens': 235929, 'pricing': {'prompt': '0', 'completion': '0'},
        'supported_parameters': ['structured_outputs', 'reasoning', 'reasoning_effort',
                                 'max_tokens', 'temperature'],
    }]}}


class QwenFreeTests(unittest.TestCase):
    def test_six_plans_preserve_all_ordered_input_only_requests(self):
        for config, (_, effort) in study.CONFIGS.items():
            for fresh_pass in study.ORDERS:
                plan = study.plan_data(config, fresh_pass)
                self.assertEqual(plan['condition_order'], study.ORDERS[fresh_pass])
                self.assertFalse(plan['reference_labels_read'])
                self.assertEqual(plan['reasoning_effort'], effort)
                self.assertTrue(all('provider-errors' not in x['path'] for x in plan['source_bindings']))
                for condition in ('P0', 'P1', 'P2'):
                    group = plan['conditions'][condition]
                    self.assertEqual(len(group['smoke']), 3)
                    self.assertEqual([x['record_id'] for x in group['development']],
                                     [f'DEV-{i:03}' for i in range(1, 61)])
                    for row in group['development']:
                        payload = row['payload']
                        self.assertEqual(payload['model'], study.MODEL)
                        self.assertEqual(payload['provider']['only'], [study.PROVIDER])
                        self.assertFalse(payload['provider']['allow_fallbacks'])
                        self.assertEqual(set(payload['provider']['max_price'].values()), {0})
                        self.assertEqual(payload['reasoning'], {'enabled': True, 'effort': effort})
                        self.assertEqual(payload['temperature'], 0)
                        self.assertEqual(payload['max_tokens'], 4096)
                        self.assertTrue(payload['response_format']['json_schema']['strict'])
                        self.assertEqual(digest(json.dumps(payload, sort_keys=True)), row['request_sha256'])
                        self.assertEqual(set(json.loads(payload['messages'][1]['content'])), {'feedback'})

    def test_endpoint_exact_zero_route_and_effort(self):
        model, route = execution.endpoint_check(catalog(), endpoints(), 'medium')
        self.assertEqual(model['id'], study.MODEL)
        self.assertEqual(route['tag'], study.PROVIDER)
        changed = endpoints()
        changed['data']['endpoints'][0]['pricing']['request'] = '0.01'
        with self.assertRaisesRegex(ValueError, 'price'):
            execution.endpoint_check(catalog(), changed, 'medium')
        changed = endpoints()
        changed['data']['endpoints'][0]['supported_parameters'].remove('structured_outputs')
        with self.assertRaisesRegex(ValueError, 'controls'):
            execution.endpoint_check(catalog(), changed, 'medium')
        changed = catalog()
        changed['data'][0]['reasoning']['supported_efforts'] = ['medium']
        with self.assertRaisesRegex(ValueError, 'effort'):
            execution.endpoint_check(changed, endpoints(), 'xhigh')

    def test_private_module_isolation_and_exact_live_payload_gate(self):
        first = execution.engine(next(iter(study.CONFIGS)))
        second = execution.engine(list(study.CONFIGS)[1])
        self.assertIsNot(first, second)
        self.assertIsNot(first, canonical)
        self.assertNotEqual(first.study.CONFIG, second.study.CONFIG)
        self.assertEqual(canonical.RECEIPT_SCHEMA, 'gemma26-free-fresh-root-review-v1')
        plan = study.plan_data(first.study.CONFIG, 'fresh1')
        with patch.object(execution.transport, 'fetch', side_effect=[catalog(), endpoints()]):
            self.assertEqual(first.live_controls(plan, 'P0')[1]['tag'], study.PROVIDER)
        plan['conditions']['P0']['development'][0]['payload']['reasoning']['effort'] = 'xhigh'
        with patch.object(execution.transport, 'fetch', side_effect=[catalog(), endpoints()]):
            with self.assertRaisesRegex(ValueError, 'payload controls'):
                first.live_controls(plan, 'P0')

    def test_review_receipt_is_private_and_configuration_specific(self):
        module = execution.engine(next(iter(study.CONFIGS)))
        with tempfile.TemporaryDirectory() as temp:
            outside = Path(temp) / module.study.CONFIG
            outside.mkdir(mode=0o700)
            note = Path(temp) / 'review.json'
            note.write_text('{}'); note.chmod(0o600)
            with self.assertRaisesRegex(ValueError, 'approval'):
                module.review_receipt(str(note), 'fresh1', 'P0', 'smoke', 'synthetic-sha')
            self.assertEqual(module.private_path(outside, directory=True), outside.resolve())

    def test_canonical_free_quota_and_raw_capture_reused_without_patching(self):
        module = execution.engine(next(iter(study.CONFIGS)))
        self.assertIs(module.free_quota, canonical.free_quota)
        self.assertIs(module.paid_execution.fetch_captured, canonical.paid_execution.fetch_captured)
        self.assertEqual(module.account_eligible.__code__.co_code,
                         canonical.account_eligible.__code__.co_code)

    def test_input_only_plan_does_not_read_private_historical_attempts(self):
        with patch.object(study.paid_study, 'verify', side_effect=AssertionError('private historical read')):
            for config in study.CONFIGS:
                self.assertEqual(study.plan_data(config, 'fresh1')['configuration_id'], config)

    def _smoke(self, temp, status):
        config = next(iter(study.CONFIGS))
        module = execution.engine(config)
        plan = study.plan_data(config, 'fresh1')
        base = Path(temp) / 'plans'
        manifest = base / 'fresh1' / 'manifest.json'
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(plan))
        plan_hash = study.sha(manifest)
        module.study.BASE = base
        module.study.verify = lambda *_: plan
        evidence = Path(temp) / config
        evidence.mkdir(mode=0o700)
        review = Path(temp) / 'review.json'
        review.write_text('{}'); review.chmod(0o600)
        qpath = Path(temp) / 'quota' / 'events.jsonl'
        prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        body = json.dumps({'model': study.MODEL, 'provider': study.PROVIDER_NAME,
                           'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'cost': 0},
                           'choices': [{'finish_reason': 'stop',
                                        'message': {'content': json.dumps(prediction)}}]}).encode()
        response = [HTTPResponse(body, status) for _ in range(3)]
        real_admit, real_start = quota.admit_stage, quota.start_call
        clock = [time.time()]
        def tick():
            clock[0] += 4
            return clock[0]
        with patch.object(module, 'review_receipt', return_value=({'approved': True}, evidence)), \
             patch.object(module, 'live_controls', return_value=(catalog()['data'][0], endpoints()['data']['endpoints'][0])), \
             patch.object(module.transport, 'load_key', return_value='private-token'), \
             patch.object(module, 'account_eligible', return_value=1000), \
             patch.object(module.transport.OPENER, 'open', side_effect=response), \
             patch.object(module.free_quota, 'admit_stage', side_effect=lambda stage, count, provider_remaining: real_admit(stage, count, path=qpath, provider_remaining=provider_remaining)), \
             patch.object(module.free_quota, 'start_call', side_effect=lambda stage, rid: real_start(stage, rid, path=qpath, clock=tick, sleep=lambda _: None)):
            done = module.execute('fresh1', 'P0', 'smoke', plan_hash, str(review))
        _, files = module.paths(evidence, 'fresh1', 'P0', 'smoke')
        return module, done, evidence, files

    def test_private_lifecycle_closes_three_raw_valid_smokes(self):
        with tempfile.TemporaryDirectory() as temp:
            module, done, evidence, files = self._smoke(temp, 200)
            self.assertTrue(done)
            self.assertEqual(len(module.rows(files['attempts'])), 3)
            self.assertEqual(len(module.rows(files['wire'])), 3)
            self.assertEqual(module.verify_closed(evidence, 'fresh1', 'P0', 'smoke')['wire_sha256'],
                             study.sha(files['wire']))

    def test_http_error_retains_raw_and_stops_without_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            module, done, evidence, files = self._smoke(temp, 404)
            self.assertFalse(done)
            self.assertEqual(len(module.rows(files['wire'])), 1)
            self.assertEqual(module.rows(files['wire'])[0]['http_status'], 404)
            self.assertEqual(module.rows(files['attempts'])[0]['status'], 'service_error')
            self.assertFalse(files['completion'].exists())


if __name__ == '__main__':
    unittest.main()
