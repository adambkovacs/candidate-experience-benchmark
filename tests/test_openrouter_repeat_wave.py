"""Offline controls and fake-provider tests for the three paid repeat lanes."""
import copy
import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_repeat_wave as wave

SHA = '1' * 64
PREDICTION = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}


def response(spec, status='ok', cost='0.0001'):
    return {'model': spec.model if status != 'model_mismatch' else 'wrong/model',
            'provider': spec.provider_name,
            'usage': {'cost': cost, 'prompt_tokens': 100, 'completion_tokens': 20},
            'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps(PREDICTION) if status == 'ok' else 'invalid json'}}]}


class FakeLedger:
    def __init__(self, cap, events):
        self.cap = wave.paid.number(cap)
        self.events = events
        self.closed = False

    def reserve(self, amount, rid):
        self.events.append(('reserve', rid))
        return 'attempt-' + rid

    def settle(self, attempt, actual):
        self.events.append(('settle', attempt, actual))
        return actual is not None

    def close(self):
        self.closed = True


class FakeHTTPResponse:
    status = 200
    headers = {'content-type': 'application/json', 'x-request-id': 'fake-request'}

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.body[:limit]


class RepeatWaveTest(unittest.TestCase):
    def test_all_saved_requests_controls_and_rotations(self):
        for spec in wave.SPECS.values():
            for repeat in spec.orders:
                with self.subTest(config=spec.id, repeat=repeat):
                    plan = wave.plan_data(spec, repeat)
                    self.assertEqual(plan['condition_order'], list(spec.orders[repeat]))
                    self.assertEqual(plan['historical_pass_order'], list(spec.historical_order))
                    self.assertEqual(plan['request_timeout_seconds'], spec.timeout)
                    self.assertFalse(plan['reference_labels_read'])
                    self.assertNotIn('data/pilot/proposed_labels.jsonl',
                                     {b['path'] for b in plan['source_bindings']})
                    for condition in ('P0', 'P1', 'P2'):
                        entry = plan['conditions'][condition]
                        self.assertEqual(len(entry['development']), 60)
                        self.assertEqual(entry['smoke'], entry['development'][:3])
                        self.assertEqual([r['record_id'] for r in entry['development']],
                                         [f'DEV-{i:03d}' for i in range(1, 61)])
                        for request in entry['development']:
                            payload = request['payload']
                            self.assertEqual(payload['provider']['only'], [spec.provider])
                            self.assertEqual(payload.get('reasoning'),
                                             {'enabled': spec.effort == 'on'} if spec.effort != 'na' else None)
                            self.assertEqual('reasoning' in payload, spec.effort != 'na')
                            self.assertEqual(payload['max_tokens'], 4096)
                            self.assertEqual(wave.digest(json.dumps(payload, sort_keys=True)),
                                             request['request_sha256'])

    def test_frozen_manifest_hashes(self):
        for spec in wave.SPECS.values():
            for repeat in spec.orders:
                path = spec.base / repeat / 'manifest.json'
                saved = json.loads(path.read_text())
                rebuilt = wave.plan_data(spec, repeat)
                saved_bindings = {b['path']: b['sha256'] for b in saved['source_bindings']}
                rebuilt_bindings = {b['path']: b['sha256'] for b in rebuilt['source_bindings']}
                self.assertEqual({k: v for k, v in saved.items() if k != 'source_bindings'},
                                 {k: v for k, v in rebuilt.items() if k != 'source_bindings'})
                changed = {p for p in saved_bindings if saved_bindings[p] != rebuilt_bindings[p]}
                self.assertLessEqual(changed, {'scripts/openrouter_repeat_wave.py'})
                if changed:
                    with self.assertRaisesRegex(ValueError, 'Bound file changed: scripts/openrouter_repeat_wave.py'):
                        wave.verify(spec, repeat, wave.sha(path))
                else:
                    self.assertEqual(wave.verify(spec, repeat, wave.sha(path)), rebuilt)
                with self.assertRaisesRegex(ValueError, 'Manifest hash mismatch'):
                    wave.verify(spec, repeat, '0' * 64)

    def test_source_and_policy_guards(self):
        spec = wave.SPECS['openrouter-paid-mistral-small32-24b-venice-not-applicable']
        with patch.object(wave, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'Wave proposal or paired manifest changed'):
                wave.plan_data(spec, 'repeat2')
        bad = copy.deepcopy(wave.plan_data(spec, 'repeat2'))
        bad['conditions']['P0']['development'][0]['payload']['reasoning'] = {'enabled': False}
        self.assertNotEqual(bad, wave.plan_data(spec, 'repeat2'))

    def test_order_and_review_block_before_key_or_claim(self):
        spec = wave.SPECS['openrouter-paid-gemma4-31b-on']
        plan = wave.plan_data(spec, 'repeat2')
        with tempfile.TemporaryDirectory() as temp, patch.object(wave, 'ROOT', Path(temp)):
            with patch.object(wave, 'verify', return_value=plan), patch.object(
                    wave.paid, 'load_key', side_effect=AssertionError('key read')):
                with self.assertRaisesRegex(ValueError, 'Prior condition incomplete'):
                    wave.execute(spec, 'repeat2', 'P2', 'smoke', SHA, '/unused')
                with patch.object(wave, 'review_receipt', side_effect=ValueError('missing review')):
                    with self.assertRaisesRegex(ValueError, 'missing review'):
                        wave.execute(spec, 'repeat2', 'P1', 'smoke', SHA, '/unused')
            self.assertFalse((Path(temp) / 'results/repeatability-v1' / spec.id).exists())

    def test_mistral_invalid_continues_development_only(self):
        mistral = wave.SPECS['openrouter-paid-mistral-small32-24b-venice-not-applicable']
        gemma = wave.SPECS['openrouter-paid-gemma4-31b-off']
        row = {'status': 'invalid_output', 'billing_ok': True, 'cost_unknown': False,
               'raw_response': response(mistral, 'invalid_output'),
               'response_diagnostic': {'blockers': [], 'passed': False}}
        self.assertTrue(wave.continue_record(mistral, row, 'development'))
        self.assertFalse(wave.continue_record(mistral, row, 'smoke'))
        self.assertFalse(wave.continue_record(gemma, row, 'development'))
        row['cost_unknown'] = True
        self.assertFalse(wave.continue_record(mistral, row, 'development'))

    def test_historical_endpoint_rebuild_and_price_drift(self):
        for spec in wave.SPECS.values():
            with self.subTest(config=spec.id):
                path = ROOT / 'results/hosted-prompt-preparation-2026-09-24' / spec.id / 'historical-attempts.jsonl'
                old = json.loads(path.read_text().splitlines()[0])
                catalog = {'data': [old['model_catalog_entry']]}
                endpoint = {'data': {'id': spec.model, 'endpoints': [old['provider_endpoint']]}}
                plan = wave.plan_data(spec, 'repeat2')
                with patch.object(wave.paid, 'fetch', side_effect=[catalog, endpoint]):
                    _, selected, reserve = wave.live_controls(spec, plan, spec.orders['repeat2'][0])
                self.assertEqual(selected['tag'], spec.provider)
                self.assertEqual(reserve, wave.paid.number(
                    next(x for x in json.loads((ROOT / wave.WAVE).read_text())['configurations']
                         if x['id'] == spec.id)['per_call_reserve_usd']))
                drift = copy.deepcopy(endpoint)
                drift['data']['endpoints'][0]['pricing']['completion'] = '0.0000001'
                with patch.object(wave.paid, 'fetch', side_effect=[catalog, drift]):
                    with self.assertRaises(ValueError):
                        wave.live_controls(spec, plan, spec.orders['repeat2'][0])

    def test_review_binds_controller_plans_and_child_manifest(self):
        spec = wave.SPECS['openrouter-paid-gemma4-31b-off']
        plans = {repeat: wave.sha(spec.base / repeat / 'manifest.json') for repeat in spec.orders}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            budget = root / 'budget.json'
            budget.write_text('{}')
            review = root / 'review.json'
            receipt = {'schema': wave.RECEIPT_SCHEMA, 'approved': True,
                       'configuration_id': spec.id, 'partition_cap_usd': spec.cap,
                       'controller_sha256': wave.sha(wave.__file__),
                       'hosted_execution_sha256': wave.sha(ROOT / wave.HOSTED),
                       'plan_sha256': plans, 'master_ledger': str(wave.MASTER),
                       'budget_manifest': {'path': 'budget.json', 'sha256': wave.sha(budget)},
                       'partition_id': 'fake-partition'}
            review.write_text(json.dumps(receipt))
            with patch.object(wave, 'read_bound', return_value=budget):
                self.assertEqual(wave.review_receipt(spec, review, 'repeat2', plans['repeat2'])[1], budget)
                receipt['controller_sha256'] = '0' * 64
                review.write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, 'controller or original policy hash differs'):
                    wave.review_receipt(spec, review, 'repeat2', plans['repeat2'])

    def test_smoke_inspection_binds_raw_responses(self):
        spec = wave.SPECS['openrouter-paid-gemma4-31b-off']
        plan = wave.plan_data(spec, 'repeat2')
        with tempfile.TemporaryDirectory() as temp, patch.object(wave, 'ROOT', Path(temp)):
            with patch.object(wave, 'verify', return_value=plan):
                condition = spec.orders['repeat2'][0]
                folder, _, journal, attempts = wave.phase_paths(spec, 'repeat2', condition, 'smoke')
                folder.mkdir(parents=True)
                journal.write_text(json.dumps({'event': 'phase_completed'}) + '\n')
                attempts.write_text(''.join(json.dumps({
                    'id': f'DEV-{i:03d}', 'attempt_id': f'a-{i}', 'status': 'ok',
                    'billing_ok': True, 'cost_unknown': False}) + '\n' for i in range(1, 4)))
                responses = folder / 'smoke.responses.jsonl'
                responses.write_text(''.join(json.dumps({
                    'id': f'DEV-{i:03d}', 'attempt_id': f'a-{i}',
                    'body_base64': base64.b64encode(json.dumps(response(spec)).encode()).decode(),
                    'body_truncated_at_limit': False, 'read_error': None}) + '\n'
                    for i in range(1, 4)))
                wave.inspect(spec, 'repeat2', condition, SHA, 'Inspected all three raw bodies')
                wave.require_order(spec, plan, condition, 'development')
                responses.write_text(responses.read_text() + '{}\n')
                with self.assertRaisesRegex(ValueError, 'Smoke inspection binding changed'):
                    wave.require_order(spec, plan, condition, 'development')

    def run_fake(self, spec, outcomes):
        plan = wave.plan_data(spec, 'repeat2')
        events = []
        ledger = FakeLedger(spec.cap, events)
        endpoint = {'model_id': spec.model, 'provider_name': spec.provider_name,
                    'tag': spec.provider, 'context_length': spec.context}
        with tempfile.TemporaryDirectory() as temp, patch.object(wave, 'ROOT', Path(temp)):
            review = Path(temp) / 'review.json'
            review.write_text('{}')
            with patch.object(wave, 'verify', return_value=plan), patch.object(
                    wave, 'review_receipt', return_value=({'partition_id': spec.id}, Path('/unused'))), patch.object(
                    wave, 'live_controls', return_value=({}, endpoint, wave.paid.number('0.01'))), patch.object(
                    wave, 'budget_gate', return_value=ledger), patch.object(
                    wave.paid, 'load_key', return_value='fake-token'):
                items = iter(outcomes)

                def open_response(request, timeout):
                    self.assertTrue(request.full_url.endswith('/chat/completions'))
                    self.assertEqual(timeout, spec.timeout)
                    self.assertEqual(events[-1][0], 'reserve')
                    events.append(('fetch', timeout))
                    outcome = next(items)
                    body = outcome if isinstance(outcome, bytes) else json.dumps(outcome).encode()
                    return FakeHTTPResponse(body)

                with patch.object(wave.transport.OPENER, 'open', side_effect=open_response):
                    finished = wave.execute(spec, 'repeat2', spec.orders['repeat2'][0],
                                            'smoke', SHA, review)
            folder = spec.base / 'repeat2' / spec.orders['repeat2'][0]
            attempts = [json.loads(x) for x in (folder / 'smoke.attempts.jsonl').read_text().splitlines()]
            raw = [json.loads(x) for x in (folder / 'smoke.responses.jsonl').read_text().splitlines()]
            journal = [json.loads(x)['event'] for x in (folder / 'smoke.journal.jsonl').read_text().splitlines()]
        self.assertTrue(ledger.closed)
        return finished, attempts, raw, journal, events

    def test_fake_smoke_reserves_before_calls_and_preserves_raw(self):
        for spec in wave.SPECS.values():
            with self.subTest(config=spec.id):
                finished, attempts, raw, journal, events = self.run_fake(spec, [response(spec)] * 3)
                self.assertTrue(finished)
                self.assertEqual(len(attempts), len(raw))
                self.assertEqual(len(attempts), 3)
                self.assertEqual([x[0] for x in events], ['reserve', 'fetch', 'settle'] * 3)
                self.assertEqual(journal[-1], 'phase_completed')
                self.assertEqual(json.loads(base64.b64decode(raw[0]['body_base64'])), response(spec))

    def test_malformed_http_200_body_is_durable_with_unknown_billing_hold(self):
        spec = wave.SPECS['openrouter-paid-mistral-small32-24b-venice-not-applicable']
        malformed = b'{"model":"mistralai/mistral-small-3.2-24b-instruct","usage":{"cost":'
        finished, attempts, raw, journal, events = self.run_fake(spec, [malformed])
        self.assertFalse(finished)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]['status'], 'service_error')
        self.assertTrue(attempts[0]['cost_unknown'])
        self.assertFalse(attempts[0]['billing_ok'])
        self.assertEqual(raw[0]['http_status'], 200)
        self.assertEqual(raw[0]['response_headers']['x-request-id'], 'fake-request')
        self.assertEqual(base64.b64decode(raw[0]['body_base64']), malformed)
        self.assertEqual(journal[-1], 'phase_stopped')
        self.assertEqual([x[0] for x in events], ['reserve', 'fetch', 'settle'])

    def test_unknown_billing_stops_without_second_call(self):
        spec = wave.SPECS['openrouter-paid-mistral-small32-24b-venice-not-applicable']
        finished, attempts, raw, journal, events = self.run_fake(spec, [response(spec, cost=None)])
        self.assertFalse(finished)
        self.assertTrue(attempts[0]['cost_unknown'])
        self.assertEqual(len(raw), 1)
        self.assertEqual(journal[-1], 'phase_stopped')
        self.assertEqual([x[0] for x in events], ['reserve', 'fetch', 'settle'])


if __name__ == '__main__':
    unittest.main()
