import copy
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
import mistral_later_phase_continuation as later


class MistralLaterPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draft = later.expected_manifest()
        cls.frozen = copy.deepcopy(cls.draft)
        cls.frozen['status'] = 'FROZEN'
        cls.raw = (json.dumps(cls.frozen) + '\n').encode()
        cls.digest = hashlib.sha256(cls.raw).hexdigest()

    def review(self):
        return {'schema': later.REVIEW_SCHEMA, 'approved': True,
                'manifest_sha256': self.digest,
                'controller_sha256': self.frozen['controller']['sha256'],
                'suffix_reconciliation_sha256': self.frozen['sources']['reconciliation']['sha256'],
                'original_review_sha256': self.frozen['sources']['root_review']['sha256'],
                'budget_manifest_sha256': self.frozen['sources']['budget_manifest']['sha256'],
                'partition_id': self.frozen['root_partition_id'],
                'acknowledge_historical_p1_59_plus_1': True,
                'acknowledge_timing_deviation': True,
                'approved_phases': [{'repeat': 'repeat2', 'condition': 'P0', 'phase': 'smoke'}],
                'review_note': 'Explicit synthetic approval fixture'}

    def test_exact_frozen_order_and_composite_p1(self):
        manifest = later.validate_manifest(self.raw, self.digest)
        self.assertEqual([(x['repeat'], x['condition']) for x in manifest['phases']], list(later.ORDER))
        self.assertEqual(later.verify_suffix(manifest['sources'])['policy']['original_failed_id'], 'DEV-043')
        for phase in manifest['phases']:
            self.assertEqual([x['record_id'] for x in phase['development']], later.IDS)
        altered = copy.deepcopy(manifest)
        altered['phases'][0]['development'][42]['record_id'] = 'DEV-999'
        with self.assertRaisesRegex(ValueError, 'differs'):
            later.validate_manifest(json.dumps(altered).encode())
        altered = copy.deepcopy(manifest)
        altered['sources']['reconciliation']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'differs'):
            later.validate_manifest(json.dumps(altered).encode())

    def test_explicit_review_must_acknowledge_failure_timing_and_hashes(self):
        receipt = self.review()
        later.validate_review(json.dumps(receipt).encode(), self.frozen, self.digest, 'repeat2', 'P0', 'smoke')
        for key, value in [('acknowledge_historical_p1_59_plus_1', False),
                           ('acknowledge_timing_deviation', False),
                           ('suffix_reconciliation_sha256', '0' * 64),
                           ('approved_phases', [])]:
            broken = {**receipt, key: value}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'review'):
                later.validate_review(json.dumps(broken).encode(), self.frozen, self.digest,
                                      'repeat2', 'P0', 'smoke')

    def test_order_refuses_unfinished_prior_and_uninspected_smoke(self):
        with mock.patch.object(later, 'reconcile_phase', return_value={'completion_status': 'partial'}):
            with self.assertRaisesRegex(ValueError, 'Prior continuation phase'):
                later.prior_complete(self.frozen, 'repeat3', 'P1')
        with mock.patch.object(later, 'reconcile_phase', return_value={'completion_status': 'closed_with_failures'}):
            later.prior_complete(self.frozen, 'repeat3', 'P1')
        with mock.patch.object(later, 'reconcile_phase', return_value={'completion_status': 'not_started'}):
            with self.assertRaisesRegex(ValueError, 'smoke'):
                later.require_inspected_smoke(self.frozen, self.digest, 'repeat2', 'P0')

    def test_truncated_http_error_is_durable_and_stops_without_retry(self):
        class InterruptedBody:
            def read(self, _size):
                raise http.client.IncompleteRead(b'{"error":"synthetic-key', 100)
            def close(self):
                pass
        class Ledger:
            def __init__(self):
                self.events = [{'event': 'budget', 'cap_usd': '0.15'}]
                self.closed = False
            def state(self):
                return {}, set(), False
            def reserve(self, amount, rid):
                self.events.append({'event': 'reserve', 'record_id': rid, 'attempt_id': 'attempt-one', 'usd': str(amount)})
                return 'attempt-one'
            def settle(self, attempt, charge):
                self.assertion = (attempt, charge)
                return False
            def close(self):
                self.closed = True
        with tempfile.TemporaryDirectory() as dirname:
            temp = Path(dirname)
            manifest = temp / 'manifest.json'
            review = temp / 'review.json'
            manifest.write_bytes(self.raw)
            review.write_text(json.dumps(self.review()))
            paths = {key: temp / ('smoke.' + key) for key in ('claim', 'journal', 'attempts', 'responses')}
            ledger = Ledger()
            error = urllib.error.HTTPError('https://invalid.example', 429, 'limited',
                                           {'retry-after': '9'}, InterruptedBody())
            with mock.patch.object(later, 'phase_paths', return_value=paths), \
                 mock.patch.object(later, 'prior_complete'), \
                 mock.patch.object(later.wave, 'live_controls', return_value=({}, {'context_length': 256000}, '0.02502400000')), \
                 mock.patch.object(later.wave, 'budget_gate', return_value=ledger), \
                 mock.patch.object(later.paid, 'load_key', return_value='synthetic-key'), \
                 mock.patch.object(later.wave, 'fetch_recorded', side_effect=error) as fetch:
                self.assertFalse(later.dispatch(manifest, self.digest, review, 'repeat2', 'P0', 'smoke'))
                self.assertEqual(fetch.call_count, 1)
                with self.assertRaises(FileExistsError):
                    later.dispatch(manifest, self.digest, review, 'repeat2', 'P0', 'smoke')
            attempt = json.loads(paths['attempts'].read_text().splitlines()[0])
            raw = json.loads(paths['responses'].read_text().splitlines()[0])
            events = [json.loads(x) for x in paths['journal'].read_text().splitlines()]
            self.assertEqual(attempt['status'], 'service_error')
            self.assertTrue(attempt['cost_unknown'])
            self.assertFalse(attempt['billing_ok'])
            self.assertEqual(ledger.assertion, ('attempt-one', None))
            self.assertEqual(raw['read_error'], 'IncompleteRead')
            self.assertIn('[REDACTED]', raw['error_body'])
            self.assertEqual(events[-1]['event'], 'phase_stopped')
            self.assertTrue(ledger.closed)

    def test_budget_pending_prevents_key_load_and_claim(self):
        class Blocked:
            def state(self):
                return {}, {'pending'}, False
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as dirname:
            temp = Path(dirname)
            manifest = temp / 'manifest.json'
            review = temp / 'review.json'
            manifest.write_bytes(self.raw)
            review.write_text(json.dumps(self.review()))
            paths = {key: temp / key for key in ('claim', 'journal', 'attempts', 'responses')}
            with mock.patch.object(later, 'phase_paths', return_value=paths), \
                 mock.patch.object(later, 'prior_complete'), \
                 mock.patch.object(later.wave, 'live_controls', return_value=({}, {'context_length': 256000}, '0.02502400000')), \
                 mock.patch.object(later.wave, 'budget_gate', return_value=Blocked()), \
                 mock.patch.object(later.paid, 'load_key') as load_key:
                with self.assertRaisesRegex(ValueError, 'budget'):
                    later.dispatch(manifest, self.digest, review, 'repeat2', 'P0', 'smoke')
                load_key.assert_not_called()
            self.assertFalse(any(x.exists() for x in paths.values()))

    def test_crashed_started_call_is_ambiguous_not_complete(self):
        with tempfile.TemporaryDirectory() as dirname:
            temp = Path(dirname)
            frozen = temp / 'frozen-manifest.json'
            frozen.write_bytes(self.raw)
            phase_paths = {key: temp / ('development.' + key)
                           for key in ('claim', 'journal', 'attempts', 'responses')}
            phase_paths['claim'].write_text(json.dumps({
                'manifest_sha256': self.digest, 'repeat': 'repeat2',
                'condition': 'P0', 'phase': 'development',
                'request_ids': later.IDS, 'ledger_event_count': 1}) + '\n')
            first = self.frozen['phases'][0]['development'][0]
            phase_paths['journal'].write_text(''.join(json.dumps(x) + '\n' for x in [
                {'event': 'phase_started'},
                {'event': 'request_intent', 'id': 'DEV-001',
                 'request_sha256': first['request_sha256']},
                {'event': 'request_started', 'id': 'DEV-001',
                 'attempt_id': 'ambiguous-one', 'request_sha256': first['request_sha256']},
                {'event': 'phase_aborted', 'ledger_event_count': 2}]))
            phase_paths['attempts'].write_text('')
            phase_paths['responses'].write_text('')
            ledger_path = temp / 'child.jsonl'
            ledger_path.write_text(''.join(json.dumps(x) + '\n' for x in [
                {'event': 'budget', 'cap_usd': '0.15'},
                {'event': 'reserve', 'record_id': 'DEV-001',
                 'attempt_id': 'ambiguous-one', 'usd': '0.02502400000'}]))
            original_path = later.path
            def local_path(relative):
                return frozen if str(relative) == str(later.OUTPUT / 'frozen-manifest.json') else original_path(relative)
            with mock.patch.object(later, 'phase_paths', return_value=phase_paths), \
                 mock.patch.object(later, 'path', side_effect=local_path), \
                 mock.patch.object(later.suffix, 'child_ledger_path', return_value=ledger_path):
                report = later.reconcile_phase(self.frozen, 'repeat2', 'P0')
            self.assertEqual(report['completion_status'], 'partial')
            self.assertEqual(report['unknown_started_ids'], ['DEV-001'])
            self.assertEqual(report['never_sent_ids'][0], 'DEV-002')
            self.assertEqual(report['status_counts'], {'never_sent': 59, 'unknown_started': 1})


if __name__ == '__main__':
    unittest.main()
