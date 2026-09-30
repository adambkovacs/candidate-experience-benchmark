import base64
from datetime import datetime
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openrouter_decision_smoke as smoke
from development_benchmark import KEYS, VALUES


def catalog(route):
    return {'data': {'id': route['model'],
        'architecture': {'modality': 'text->decisions', 'output_modalities': ['decisions']},
        'endpoints': [{'model_id': route['model'], 'tag': route['tag'],
            'provider_name': route['provider'],
            'name': route['provider'] + ' | ' + route['version'],
            'status': 0, 'context_length': route['context'],
            'pricing': {'prompt': '0.000000042', 'completion': '0', 'discount': 0},
            'supported_parameters': []}]}}


def valid_body(route):
    answers = {}
    for key in KEYS:
        labels = VALUES[key]
        answers[key] = {'type': 'choice', 'choice': labels[0], 'confidence': 0.9,
                        'probabilities': {label: 1.0 if i == 0 else 0.0
                                          for i, label in enumerate(labels)}}
    return {'model': route['version'], 'provider': route['provider'],
            'answers': answers, 'usage': {'input_tokens': 500, 'output_tokens': 80,
                                          'cost': 0.000021}}


class OpenRouterDecisionSmokeTests(unittest.TestCase):
    def prepared_temp(self, directory, name='jev'):
        base = Path(directory)
        snapshots = {key: catalog(route) for key, route in smoke.ROUTES.items()}
        manifest = smoke.build_manifest(snapshots)
        for key, snapshot in snapshots.items():
            (base / (key + '-endpoint.json')).write_text(json.dumps(snapshot))
        (base / 'manifest.json').write_text(json.dumps(manifest))
        receipt = {'approved': True, 'reviewer': 'offline-test',
                   'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
                   'route': name,
                   'max_reservation_usd': manifest['routes'][name]['three_request_bound_usd']}
        receipt_path = base / 'review.json'
        receipt_path.write_text(json.dumps(receipt))
        return base, receipt_path

    def test_manifest_is_input_only_and_binds_exact_native_choice(self):
        snapshots = {name: catalog(route) for name, route in smoke.ROUTES.items()}
        manifest = smoke.build_manifest(snapshots)
        self.assertFalse(manifest['inference_performed'])
        self.assertFalse(manifest['reference_labels_read'])
        for name, route in smoke.ROUTES.items():
            item = manifest['routes'][name]
            self.assertEqual([r['id'] for r in item['requests']], ['DEV-001', 'DEV-002', 'DEV-003'])
            self.assertEqual(item['three_request_bound_usd'], str(3 * smoke.bound(route)))
            for record in item['requests']:
                payload = record['payload']
                self.assertEqual(payload['model'], route['model'])
                self.assertEqual(set(payload['questions']), set(KEYS))
                self.assertEqual({q['type'] for q in payload['questions'].values()}, {'choice'})
                self.assertEqual(set(payload['state']), {'feedback', 'policy'})
                self.assertEqual(payload['provider']['only'], [route['tag']])
                self.assertIs(payload['provider']['allow_fallbacks'], False)
                self.assertNotIn('proposed_labels', json.dumps(record))

    def test_route_and_price_drift_fail_closed(self):
        for route in smoke.ROUTES.values():
            original = catalog(route)
            smoke.validate_endpoint(original, route)
            for field, value in [('tag', 'other'), ('name', 'other'), ('context_length', 1)]:
                altered = json.loads(json.dumps(original))
                altered['data']['endpoints'][0][field] = value
                with self.assertRaises(ValueError):
                    smoke.validate_endpoint(altered, route)
            altered = json.loads(json.dumps(original))
            altered['data']['endpoints'][0]['pricing']['request'] = '0.001'
            with self.assertRaises(ValueError):
                smoke.validate_endpoint(altered, route)

    def test_receipt_requires_exact_reviewed_route_and_bound(self):
        manifest = smoke.build_manifest({name: catalog(route) for name, route in smoke.ROUTES.items()})
        receipt = {'approved': True, 'reviewer': 'offline-test',
                   'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
                   'route': 'jev',
                   'max_reservation_usd': manifest['routes']['jev']['three_request_bound_usd']}
        smoke.validate_receipt(receipt, manifest, 'jev')
        for change in ({'approved': False}, {'route': 'kev'}, {'max_reservation_usd': '0'}):
            altered = dict(receipt, **change)
            with self.assertRaises(ValueError):
                smoke.validate_receipt(altered, manifest, 'jev')

    def test_exact_provider_version_and_native_distributions(self):
        route = smoke.ROUTES['jev']
        body = valid_body(route)
        self.assertEqual(set(smoke.validate_response(body, route)), set(KEYS))
        for key, value in [('provider', 'Other'), ('model', route['model'])]:
            altered = json.loads(json.dumps(body))
            altered[key] = value
            with self.assertRaises(ValueError):
                smoke.validate_response(altered, route)
        altered = json.loads(json.dumps(body))
        altered['answers']['sentiment']['probabilities']['positive'] = 0.8
        with self.assertRaises(ValueError):
            smoke.validate_response(altered, route)

    def test_unknown_cost_remains_unknown(self):
        self.assertIsNone(smoke.response_cost({'usage': {'input_tokens': 1}}))
        self.assertIsNone(smoke.response_cost({'usage': {'cost': None}}))
        self.assertEqual(str(smoke.response_cost({'usage': {'cost': '0.000021'}})), '0.000021')

    def test_execution_without_receipt_never_touches_catalog_or_ledger(self):
        with patch.object(smoke, 'load_prepared', side_effect=ValueError('not prepared')) as prepared, \
             patch.object(smoke, 'fetch_catalog') as catalog_fetch, \
             patch.object(smoke, 'BudgetLedger') as ledger:
            with self.assertRaisesRegex(ValueError, 'not prepared'):
                smoke.execute('jev', '/nonexistent/review.json')
            prepared.assert_called_once()
            catalog_fetch.assert_not_called()
            ledger.assert_not_called()

    def test_mocked_three_call_smoke_settles_shared_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            base, receipt = self.prepared_temp(directory)
            ledger_path = base / 'budget.jsonl'
            ledger_path.write_text('{"event":"budget","cap_usd":"10"}\n')
            route = smoke.ROUTES['jev']
            raw = json.dumps(valid_body(route), separators=(',', ':')).encode()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(route)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                smoke.execute('jev', receipt, base=base, ledger_path=ledger_path)
            self.assertEqual(post.call_count, 3)
            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual(sum(e['event'] == 'reserve' for e in events), 3)
            self.assertEqual(sum(e['event'] == 'settle' for e in events), 3)
            rows = [json.loads(line) for line in (base / 'jev-attempts.jsonl').read_text().splitlines()]
            self.assertEqual(sum(row['stage'] == 'validated' for row in rows), 3)
            responses = [row for row in rows if row['stage'] == 'response']
            self.assertEqual(len(responses), 3)
            for response in responses:
                self.assertEqual(base64.b64decode(response['raw_response_base64']), raw)
                self.assertEqual(response['raw_response_sha256'], smoke.sha(raw))
                self.assertEqual(response['raw_response_size_bytes'], len(raw))
                self.assertIsInstance(response['client_request_elapsed_ns'], int)
                self.assertGreaterEqual(response['client_request_elapsed_ns'], 0)
                self.assertLessEqual(datetime.fromisoformat(response['request_start_utc'].replace('Z', '+00:00')),
                                     datetime.fromisoformat(response['request_end_utc'].replace('Z', '+00:00')))
                self.assertNotIn('offline-test-key', json.dumps(response))

    def test_mocked_unknown_cost_stops_after_one_pending_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            base, receipt = self.prepared_temp(directory, name='kev')
            ledger_path = base / 'budget.jsonl'
            ledger_path.write_text('{"event":"budget","cap_usd":"10"}\n')
            route = smoke.ROUTES['kev']
            body = valid_body(route)
            del body['usage']['cost']
            raw = json.dumps(body).encode()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(route)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
                    smoke.execute('kev', receipt, base=base, ledger_path=ledger_path)
            self.assertEqual(post.call_count, 1)
            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual([e['event'] for e in events], ['budget', 'reserve'])
            responses = [json.loads(line) for line in (base / 'kev-attempts.jsonl').read_text().splitlines()
                         if json.loads(line)['stage'] == 'response']
            self.assertEqual(base64.b64decode(responses[0]['raw_response_base64']), raw)
            self.assertTrue(responses[0]['cost_unknown'])

    def test_malformed_raw_response_is_preserved_with_pending_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            base, receipt = self.prepared_temp(directory)
            ledger_path = base / 'budget.jsonl'
            ledger_path.write_text('{"event":"budget","cap_usd":"10"}\n')
            raw = b'{invalid-json\xff'
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(smoke.ROUTES['jev'])), \
                 patch.object(smoke, 'post', return_value=(502, raw)):
                with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
                    smoke.execute('jev', receipt, base=base, ledger_path=ledger_path)
            rows = [json.loads(line) for line in (base / 'jev-attempts.jsonl').read_text().splitlines()]
            response = next(row for row in rows if row['stage'] == 'response')
            self.assertEqual(base64.b64decode(response['raw_response_base64']), raw)
            self.assertIsNone(response['body'])
            self.assertTrue(response['parse_error_type'])

    def test_transport_error_records_elapsed_time_and_keeps_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            base, receipt = self.prepared_temp(directory)
            ledger_path = base / 'budget.jsonl'
            ledger_path.write_text('{"event":"budget","cap_usd":"10"}\n')
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(smoke.ROUTES['jev'])), \
                 patch.object(smoke, 'post', side_effect=TimeoutError('offline test')) as post:
                with self.assertRaises(TimeoutError):
                    smoke.execute('jev', receipt, base=base, ledger_path=ledger_path)
            self.assertEqual(post.call_count, 1)
            rows = [json.loads(line) for line in (base / 'jev-attempts.jsonl').read_text().splitlines()]
            failure = next(row for row in rows if row['stage'] == 'transport_error')
            self.assertGreaterEqual(failure['client_request_elapsed_ns'], 0)
            self.assertTrue(failure['request_start_utc'].endswith('Z'))
            self.assertTrue(failure['request_end_utc'].endswith('Z'))
            self.assertTrue(failure['cost_unknown'])
            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual([event['event'] for event in events], ['budget', 'reserve'])


if __name__ == '__main__':
    unittest.main()
