import copy
import base64
import hashlib
import http.client
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import mistral_p1_never_sent_suffix as suffix


class MistralP1SuffixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draft = suffix.expected_manifest()
        cls.frozen = copy.deepcopy(cls.draft)
        cls.frozen['status'] = 'FROZEN'
        cls.raw = (json.dumps(cls.frozen) + '\n').encode()
        cls.digest = hashlib.sha256(cls.raw).hexdigest()

    def test_exact_seventeen_and_failed_original_preserved(self):
        found = suffix.validate_manifest(self.raw, self.digest)
        self.assertEqual(found['request_ids'], [f'DEV-{i:03}' for i in range(44, 61)])
        self.assertEqual([r['record_id'] for r in found['requests']], found['request_ids'])
        self.assertEqual(suffix.require_unknown_accounted(found)['attempt_id'], suffix.FAILED_ATTEMPT)
        original = suffix.source_state(
            suffix.wave.verify(suffix.wave.SPECS[suffix.SPEC_ID], 'repeat2',
                               found['sources']['manifest']['sha256']),
            found['sources'])
        self.assertEqual([r['id'] for r in original], [f'DEV-{i:03}' for i in range(1, 44)])
        self.assertEqual(original[-1]['status'], 'service_error')

    def test_manifest_cannot_add_failed_or_change_payload(self):
        bad = copy.deepcopy(self.frozen)
        bad['request_ids'][0] = 'DEV-043'
        with self.assertRaisesRegex(ValueError, 'differs|attempted'):
            suffix.validate_manifest(json.dumps(bad).encode())
        bad = copy.deepcopy(self.frozen)
        bad['requests'][0]['payload']['temperature'] = 1
        with self.assertRaisesRegex(ValueError, 'differs'):
            suffix.validate_manifest(json.dumps(bad).encode())

    def test_ledger_receipt_is_required_without_mutation(self):
        bad = copy.deepcopy(self.frozen)
        bad['sources']['dev043_accounting']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'changed'):
            suffix.require_unknown_accounted(bad)
        with mock.patch.object(suffix, 'read_bound', wraps=suffix.read_bound) as read:
            suffix.require_unknown_accounted(self.frozen)
            self.assertTrue(read.called)

    def test_new_review_and_cooldown_gate(self):
        receipt = {'schema': suffix.REVIEW_SCHEMA, 'approved': True,
                   'manifest_sha256': self.digest,
                   'original_review_sha256': self.frozen['sources']['original_review']['sha256'],
                   'budget_manifest_sha256': self.frozen['sources']['budget_manifest']['sha256'],
                   'controller_sha256': self.frozen['controller']['sha256'],
                   'partition_id': 'mistral32-repeat-v1',
                   'approved_phases': ['development'], 'cooldown_note': 'Separate root observation',
                   'cooldown_not_before_utc': '2030-01-01T00:00:00Z',
                   'capacity_probe_policy': 'waived_with_reason',
                   'probe_waiver_reason': 'Explicit decision'}
        raw = json.dumps(receipt).encode()
        with self.assertRaisesRegex(ValueError, 'cooldown'):
            suffix.validate_review(raw, self.digest, self.frozen, 'development')
        receipt['cooldown_not_before_utc'] = '2020-01-01T00:00:00Z'
        suffix.validate_review(json.dumps(receipt).encode(), self.digest, self.frozen, 'development')
        receipt['approved_phases'] = ['capacity_probe']
        with self.assertRaisesRegex(ValueError, 'review'):
            suffix.validate_review(json.dumps(receipt).encode(), self.digest, self.frozen, 'development')
        receipt['approved_phases'] = ['development']
        receipt['capacity_probe_policy'] = 'required'
        with self.assertRaisesRegex(ValueError, 'inspected|binding'):
            suffix.validate_review(json.dumps(receipt).encode(), self.digest, self.frozen, 'development')

    def test_truncated_429_is_saved_then_stops_with_unknown_charge(self):
        class InterruptedBody:
            def read(self, _limit):
                raise http.client.IncompleteRead(b'{"error":"cut synthetic-key', 12)
            def close(self):
                pass

        class ChildLedger:
            def __init__(self):
                self.settlements = []
                self.closed = False
            def state(self):
                return {}, set(), False
            def reserve(self, _amount, rid):
                assert rid == 'DEV-044'
                return 'attempt-44'
            def settle(self, attempt, actual):
                self.settlements.append((attempt, actual))
                return False
            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            manifest = root / 'manifest.json'
            review = root / 'review.json'
            manifest.write_bytes(self.raw)
            review.write_text('{}')
            ledger = ChildLedger()
            order = []
            def paths(phase):
                return {key: root / f'{phase}.{key}' for key in ('claim', 'journal', 'attempts', 'responses')}
            def budget_gate(*_args):
                order.append('budget')
                return ledger
            def load_key(_env_file):
                order.append('key')
                return 'synthetic-key'
            error = urllib.error.HTTPError('https://invalid.example', 429, 'limited',
                                           {'retry-after': '9'}, InterruptedBody())
            with mock.patch.object(suffix, 'phase_paths', side_effect=paths), \
                 mock.patch.object(suffix, 'validate_review', return_value={}), \
                 mock.patch.object(suffix.wave, 'live_controls', return_value=({}, {'context_length': 256000}, '0.02502400000')), \
                 mock.patch.object(suffix.wave, 'budget_gate', side_effect=budget_gate), \
                 mock.patch.object(suffix.paid, 'load_key', side_effect=load_key), \
                 mock.patch.object(suffix.wave, 'fetch_recorded', side_effect=error):
                self.assertFalse(suffix.dispatch(manifest, self.digest, review, 'development'))
            attempt = json.loads(paths('development')['attempts'].read_text().splitlines()[0])
            raw = json.loads(paths('development')['responses'].read_text().splitlines()[0])
            journal = [json.loads(line) for line in paths('development')['journal'].read_text().splitlines()]
            self.assertEqual(order, ['budget', 'key'])
            self.assertEqual(ledger.settlements, [('attempt-44', None)])
            self.assertTrue(ledger.closed)
            self.assertEqual(attempt['status'], 'service_error')
            self.assertEqual(attempt['http_status'], 429)
            self.assertEqual(attempt['read_error'], 'IncompleteRead')
            self.assertTrue(attempt['cost_unknown'])
            self.assertFalse(attempt['billing_ok'])
            self.assertEqual(raw['read_error'], 'IncompleteRead')
            self.assertEqual(raw['error_body'], attempt['error_body'])
            self.assertIn('[REDACTED]', raw['error_body'])
            self.assertEqual(journal[-1]['event'], 'phase_stopped')
            self.assertEqual(journal[-1]['id'], 'DEV-044')

    def test_started_without_response_is_ambiguous_and_never_replayed(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            def paths(phase):
                return {key: root / f'{phase}.{key}' for key in ('claim', 'journal', 'attempts', 'responses')}
            local = paths('development')
            local['claim'].write_text(json.dumps({'manifest_sha256': self.digest,
                                                  'request_ids': suffix.IDS}) + '\n')
            first = self.frozen['requests'][0]
            local['journal'].write_text('\n'.join(json.dumps(row) for row in [
                {'event': 'phase_started'},
                {'event': 'request_intent', 'id': 'DEV-044', 'request_sha256': first['request_sha256']},
                {'event': 'request_started', 'id': 'DEV-044', 'attempt_id': 'ambiguous-1',
                 'request_sha256': first['request_sha256']},
                {'event': 'phase_aborted'}]) + '\n')
            local['attempts'].write_text('')
            local['responses'].write_text('')
            ledger = root / 'child.jsonl'
            ledger.write_text(json.dumps({'event': 'reserve', 'record_id': 'DEV-043',
                                          'attempt_id': suffix.FAILED_ATTEMPT, 'usd': '0.02502400000'}) + '\n' +
                              json.dumps(json.loads(suffix.read_bound(self.frozen['sources']['dev043_accounting']))) + '\n' +
                              json.dumps({'event': 'reserve', 'record_id': 'DEV-044',
                                          'attempt_id': 'ambiguous-1', 'usd': '0.02502400000'}) + '\n')
            with tempfile.NamedTemporaryFile(mode='wb') as manifest:
                manifest.write(self.raw)
                manifest.flush()
                with mock.patch.object(suffix, 'phase_paths', side_effect=paths), \
                     mock.patch.object(suffix, 'child_ledger_path', return_value=ledger):
                    report = suffix.reconcile(manifest.name, self.digest)
            self.assertFalse(report['strict_complete_pass'])
            self.assertEqual(report['denominator'], 60)
            self.assertEqual(report['status_counts'], {'never_sent': 16, 'ok': 42,
                                                       'service_error': 1, 'unknown_started': 1})
            self.assertEqual(report['unknown_started_ids'], ['DEV-044'])
            self.assertEqual(report['never_sent_ids'][0], 'DEV-045')

    def test_full_coverage_retains_historical_failure(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            def paths(phase):
                return {key: root / f'{phase}.{key}' for key in ('claim', 'journal', 'attempts', 'responses')}
            local = paths('development')
            local['claim'].write_text(json.dumps({'manifest_sha256': self.digest,
                                                  'request_ids': suffix.IDS}) + '\n')
            events = [{'event': 'phase_started'}]
            attempts, sidecars = [], []
            ledger = [{'event': 'reserve', 'record_id': 'DEV-043',
                       'attempt_id': suffix.FAILED_ATTEMPT, 'usd': '0.02502400000'},
                      json.loads(suffix.read_bound(self.frozen['sources']['dev043_accounting']))]
            for index, request in enumerate(self.frozen['requests']):
                rid = request['record_id']
                attempt = f'fresh-{index}'
                events += [{'event': 'request_intent', 'id': rid,
                            'request_sha256': request['request_sha256']},
                           {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                            'request_sha256': request['request_sha256']},
                           {'event': 'request_finished', 'id': rid, 'attempt_id': attempt,
                            'status': 'ok', 'billing_ok': True, 'cost_unknown': False}]
                attempts.append({'id': rid, 'attempt_id': attempt, 'status': 'ok',
                                 'phase': 'development', 'manifest_sha256': self.digest,
                                 'request': request['payload'],
                                 'request_sha256': request['request_sha256'],
                                 'reference_labels_read': False, 'billing_ok': True,
                                 'cost_unknown': False, 'observed_cost_usd': '0.0001',
                                 'reserved_cost_usd': '0.02502400000',
                                 'raw_response': {'usage': {'cost': '0.0001'}}})
                sidecars.append({'id': rid, 'attempt_id': attempt,
                                 'request_sha256': request['request_sha256'],
                                 'body_base64': base64.b64encode(json.dumps({'usage': {'cost': '0.0001'}}).encode()).decode()})
                ledger.extend([{'event': 'reserve', 'record_id': rid, 'attempt_id': attempt,
                                'usd': '0.02502400000'},
                               {'event': 'settle', 'attempt_id': attempt, 'usd': '0.0001'}])
            events.append({'event': 'phase_completed'})
            ledger.extend([{'event': 'reserve', 'record_id': 'DEV-044',
                            'attempt_id': 'later-phase-44', 'usd': '0.02502400000'},
                           {'event': 'settle', 'attempt_id': 'later-phase-44', 'usd': '0.0001'}])
            for key, data in [('journal', events), ('attempts', attempts), ('responses', sidecars)]:
                local[key].write_text(''.join(json.dumps(x) + '\n' for x in data))
            ledger_path = root / 'child.jsonl'
            ledger_path.write_text(''.join(json.dumps(x) + '\n' for x in ledger))
            with tempfile.NamedTemporaryFile(mode='wb') as manifest:
                manifest.write(self.raw)
                manifest.flush()
                with mock.patch.object(suffix, 'phase_paths', side_effect=paths), \
                     mock.patch.object(suffix, 'child_ledger_path', return_value=ledger_path):
                    report = suffix.reconcile(manifest.name, self.digest)
            self.assertEqual(report['status_counts'], {'ok': 59, 'service_error': 1})
            self.assertEqual(report['coverage_status'], 'closed_with_historical_service_error')
            self.assertEqual(report['positions'][42]['id'], 'DEV-043')
            self.assertEqual(report['positions'][42]['status'], 'service_error')
            self.assertFalse(report['strict_complete_pass'])

    def test_original_partial_without_suffix_is_not_clean_pass(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            def paths(phase):
                return {key: root / f'{phase}.{key}' for key in ('claim', 'journal', 'attempts', 'responses')}
            with tempfile.NamedTemporaryFile(mode='wb') as manifest:
                manifest.write(self.raw)
                manifest.flush()
                with mock.patch.object(suffix, 'phase_paths', side_effect=paths):
                    report = suffix.reconcile(manifest.name, self.digest)
            self.assertEqual(report['status_counts'], {'never_sent': 17, 'ok': 42, 'service_error': 1})
            self.assertEqual(report['coverage_status'], 'partial')
            self.assertFalse(report['strict_complete_pass'])


if __name__ == '__main__':
    unittest.main()
