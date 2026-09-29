"""Offline second-interruption protocol tests; no allocation or hosted request."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import qwen36_off_v2_second_interruption as second
from openrouter_budget_v2 import BudgetLedger


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


class Fixture(unittest.TestCase):
    def setUp(self):
        if not all((second.OLD / f'phase-07-development.{part}.jsonl').exists()
                   for part in ('journal', 'raw', 'records')):
            self.skipTest('Private original failed evidence is unavailable in this checkout')
        self.temp = tempfile.TemporaryDirectory(dir=REPO)
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'second-interruption-v1'
        self.output.mkdir()
        self.patch_output = patch.object(second, 'OUTPUT', self.output)
        self.patch_output.start(); self.addCleanup(self.patch_output.stop)
        self.budget = self.output / 'budget.json'
        self.ledger = self.output / f'budget-{second.PARTITION}.jsonl'
        write_json(self.budget, {'version': 'paid-partitions-v1',
            'master_ledger': str(second.admission.MASTER.resolve()),
            'partitions': [{'id': second.PARTITION, 'model': second.admission.MODEL,
                'provider': second.admission.PROVIDER, 'reasoning': 'off',
                'cap_usd': '0.06', 'child_ledger': str(self.ledger)}]})
        write_rows(self.ledger, [{'event': 'budget', 'cap_usd': '0.06'}])
        self.path = self.output / 'manifest.json'
        second.freeze(self.path, self.budget)
        self.manifest_sha = second.sha(self.path)
        self.manifest = second.validate_manifest(self.path, self.manifest_sha)

    def review(self, index=6, stage='suffix', inspection=None):
        p = second.review_path(index, stage)
        value = {'schema': second.SCHEMA + '-stage-review', 'approved': True,
            'manifest_sha256': self.manifest_sha,
            'controller_sha256': self.manifest['controller']['sha256'],
            'old_child_ledger_sha256': second.OLD_LEDGER_SHA,
            'old_terminal_reconciliation_sha256': self.manifest['sources']['old_terminal_reconciliation']['sha256'],
            'new_budget_manifest_sha256': second.sha(self.budget),
            'partition_id': second.PARTITION, 'phase_index': index, 'stage': stage,
            'ids': [x['id'] for x in second.selected_items(self.manifest, index, stage)]}
        if inspection is not None:
            value['smoke_inspection'] = inspection
        write_json(p, value)
        return p

    def add_suffix(self, count=29, outcome='ok', status_code=503):
        target = second.stage_paths(6, 'suffix')
        review = self.review()
        write_json(target['claim'], {'schema': 'affordable-hosted-stage-claim-v1',
            'manifest_sha256': self.manifest_sha, 'review_sha256': second.sha(review),
            'budget_manifest_sha256': second.sha(self.budget),
            'partition_id': second.PARTITION, 'phase_index': 6,
            'repeat': 'fresh3', 'condition': 'P1', 'stage': 'suffix',
            'ids': second.REMAINING})
        events = [{'event': 'stage_claimed', 'claim_sha256': second.sha(target['claim'])}]
        raw, records = [], []
        ledger = [{'event': 'budget', 'cap_usd': '0.06'}]
        secret = 'user_id=SYNTHETIC_PRIVATE_ACCOUNT'
        for i, item in enumerate(second.selected_items(self.manifest, 6, 'suffix')[:count]):
            is_last = i == count - 1
            failure = is_last and outcome == 'service_error'
            invalid = is_last and outcome == 'invalid_output'
            rid, attempt = item['id'], f'synthetic-{i}'
            prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                          'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
            body = {'model': second.admission.MODEL, 'provider': 'AkashML',
                'usage': {'cost': '0.0001', 'prompt_tokens': 10,
                          'completion_tokens': 5, 'total_tokens': 15},
                'choices': [{'message': {'content': '{invalid' if invalid else json.dumps(prediction)},
                             'finish_reason': 'stop'}]}
            sidecar = ({'id': rid, 'attempt_id': attempt,
                        'transport_error': 'HTTPError', 'error_body': secret,
                        'http_status': status_code} if failure else
                       {'id': rid, 'attempt_id': attempt, 'body': body})
            raw.append(sidecar)
            row = {'id': rid, 'attempt_id': attempt, 'repeat': 'fresh3',
                'condition': 'P1', 'phase': 'development', 'request': item['payload'],
                'request_sha256': item['request_sha256'],
                'input_sha256': item['input_sha256'],
                'policy_sha256': item['instruction_sha256'],
                'reference_labels_read': False, 'requested_model': second.admission.MODEL,
                'provider_endpoint': {'tag': second.admission.PROVIDER,
                                      'provider_name': 'AkashML'},
                'budget_partition_id': second.PARTITION, 'reasoning_effort': 'off',
                'reserved_cost_usd': str(second.RESERVE),
                'client_request_started_utc': '2026-09-29T00:00:00+00:00',
                'client_request_finished_utc': '2026-09-29T00:00:01+00:00',
                'client_http_duration_seconds': 0.3,
                'status': 'service_error' if failure else 'invalid_output' if invalid else 'ok',
                'observed_cost_usd': None if failure else '0.0001',
                'cost_unknown': failure, 'billing_ok': not failure}
            if failure:
                row.update(raw_error_response=secret, http_status=status_code,
                           error_type='HTTPError')
            else:
                row.update(raw_response=body, usage=body['usage'],
                           prediction=None if invalid else prediction,
                           returned_model=second.admission.MODEL,
                           returned_provider='AkashML', finish_reason='stop')
            records.append(row)
            events.extend(({'event': 'request_started', 'attempt_id': attempt,
                'id': rid, 'request_sha256': item['request_sha256'],
                'reserved_cost_usd': str(second.RESERVE)},
                {'event': 'raw_saved', 'attempt_id': attempt, 'raw_sha256': ''},
                {'event': 'request_finished', 'attempt_id': attempt, 'id': rid,
                 'status': row['status'], 'billing_ok': row['billing_ok']}))
            ledger.append({'event': 'reserve', 'attempt_id': attempt,
                           'record_id': rid, 'usd': str(second.RESERVE)})
            if not failure:
                ledger.append({'event': 'settle', 'attempt_id': attempt, 'usd': '0.0001'})
        write_rows(target['raw'], raw); write_rows(target['records'], records)
        lines = target['raw'].read_bytes().splitlines(keepends=True)
        for i in range(count):
            events[2 + i * 3]['raw_sha256'] = hashlib.sha256(b''.join(lines[:i + 1])).hexdigest()
        if count == 29 and outcome == 'ok':
            events.append({'event': 'stage_completed', 'count': 29})
        elif outcome == 'cap':
            events.append({'event': 'admission_stopped',
                           'next_unsent_id': second.REMAINING[count], 'reason': 'child_cap'})
        else:
            events.append({'event': 'stage_stopped', 'id': records[-1]['id'],
                           'reason': records[-1]['status']})
        write_rows(target['journal'], events)
        if outcome == 'service_error' and count:
            ledger.append({'event': 'unknown_cost_accounted_as_upper_bound',
                'attempt_id': records[-1]['attempt_id'], 'usd': str(second.RESERVE),
                'actual_cost_usd': None, 'reason': 'Synthetic terminal failure',
                'evidence_path': str(target['records']),
                'evidence_sha256': second.sha(target['records'])})
        write_rows(self.ledger, ledger)
        return target, secret


class SecondInterruptionTests(Fixture):
    def test_real_persisted_sources_and_order_without_private_export(self):
        source, bindings = second.old_context()
        self.assertEqual(9, len(source['phases']))
        self.assertEqual(second.OLD_LEDGER_SHA, bindings['old_child_ledger']['sha256'])
        self.assertEqual(second.REMAINING[0], second.selected_items(self.manifest, 6, 'suffix')[0]['id'])
        self.assertEqual('P2', self.manifest['phases'][7]['condition'])
        self.assertEqual('P0', self.manifest['phases'][8]['condition'])
        result = second.reconcile_suffix(self.path, self.manifest_sha)
        self.assertEqual('not_started', result['status'])
        self.assertEqual(29, result['status_counts']['never_sent'])

    def test_predecessor_and_duplicate_rejected_before_key(self):
        review = self.review()
        second.prepare(self.path, self.manifest_sha, self.budget, 6, 'suffix', review)
        later = self.review(7, 'smoke')
        with self.assertRaisesRegex(ValueError, 'suffix lacks exact closure'):
            second.prepare(self.path, self.manifest_sha, self.budget, 7, 'smoke', later)
        second.stage_paths(6, 'suffix')['claim'].write_text('{}')
        with patch.object(second.paid, 'load_key', side_effect=AssertionError('key opened')):
            with self.assertRaises(FileExistsError):
                second.execute(self.path, self.manifest_sha, self.budget, 6, 'suffix', review)

    def test_route_and_cap_stop_before_http(self):
        review = self.review()
        with (patch.object(second.first_suffix, 'live_controls', side_effect=ValueError('route changed')),
              patch.object(second.paid, 'load_key', side_effect=AssertionError('key opened'))):
            with self.assertRaisesRegex(ValueError, 'route changed'):
                second.execute(self.path, self.manifest_sha, self.budget, 6, 'suffix', review)
        self.assertFalse(second.stage_paths(6, 'suffix')['claim'].exists())
        class CappedLedger:
            closed = False
            def state(self): return None, {}, False
            def reserve(self, *_): raise ValueError('cap reached')
            def close(self): pass
        with (patch.object(second.first_suffix, 'live_controls', return_value=({}, {})),
              patch.object(second.partitions, 'open_partition', return_value=CappedLedger()),
              patch.object(second.paid, 'load_key', return_value='SYNTHETIC_KEY'),
              patch.object(second.paid, 'fetch', side_effect=AssertionError('HTTP sent'))):
            outcome = second.execute(self.path, self.manifest_sha, self.budget, 6, 'suffix', review)
        self.assertEqual('child_cap', outcome['status'])
        result = second.reconcile_suffix(self.path, self.manifest_sha)
        self.assertEqual('admission_stopped', result['status'])
        self.assertEqual(29, result['status_counts']['never_sent'])

    def test_closed_suffix_allows_next_smoke_but_not_uninspected_development(self):
        self.add_suffix()
        result = second.reconcile_suffix(self.path, self.manifest_sha)
        self.assertEqual('closed_with_service_error', result['status'])
        self.assertEqual(59, result['valid'])
        self.assertEqual(['DEV-006', 'DEV-031'], result['old_failed_ids'])
        review = self.review(7, 'smoke')
        second.prepare(self.path, self.manifest_sha, self.budget, 7, 'smoke', review)
        dev_review = self.review(7, 'development')
        with self.assertRaisesRegex(ValueError, 'Previous stage|smoke inspection'):
            second.prepare(self.path, self.manifest_sha, self.budget, 7, 'development', dev_review)

    def test_provider_stop_and_billed_invalid_stay_unclosed_and_private(self):
        _, secret = self.add_suffix(2, 'service_error')
        result = second.reconcile_suffix(self.path, self.manifest_sha)
        self.assertEqual('stopped', result['status'])
        self.assertEqual(503, result['positions'][32]['http_status'])
        self.assertEqual('0.0299008', result['new_unknown_charge_upper_bound_usd'])
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(27, result['status_counts']['never_sent'])
        self.add_suffix(2, 'invalid_output')
        result = second.reconcile_suffix(self.path, self.manifest_sha)
        self.assertEqual('stopped', result['status'])
        self.assertEqual('0.0002', result['new_known_actual_usd'])
        self.assertEqual('invalid_output', result['positions'][32]['status'])

    def test_tampered_budget_and_record_fail(self):
        self.add_suffix(1, 'cap')
        target = second.stage_paths(6, 'suffix')
        result = second.reconcile_suffix(self.path, self.manifest_sha)
        self.assertEqual('admission_stopped', result['status'])
        rows = [json.loads(line) for line in target['records'].read_text().splitlines()]
        rows[0]['request_sha256'] = '0' * 64
        write_rows(target['records'], rows)
        with self.assertRaisesRegex(ValueError, 'request or journal'):
            second.reconcile_suffix(self.path, self.manifest_sha)
        self.budget.write_text(self.budget.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Bound evidence changed'):
            second.validate_manifest(self.path, self.manifest_sha)

    def test_real_child_ledger_executes_later_smoke_and_development(self):
        self.add_suffix()
        self.assertEqual('closed_with_service_error',
                         second.reconcile_suffix(self.path, self.manifest_sha)['status'])
        endpoint = {'tag': second.admission.PROVIDER, 'provider_name': 'AkashML',
                    'quantization': 'fp8'}
        prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        dispatched = []
        def fetch(_path, _token, payload, _timeout):
            dispatched.append(payload)
            return {'model': second.admission.MODEL, 'provider': 'AkashML',
                'usage': {'cost': '0.0001', 'prompt_tokens': 10,
                          'completion_tokens': 5, 'total_tokens': 15},
                'choices': [{'message': {'content': json.dumps(prediction)},
                             'finish_reason': 'stop'}]}
        def open_real_child(*_args):
            return BudgetLedger(self.ledger, cap_limit=second.CAP)
        smoke_review = self.review(7, 'smoke')
        with (patch.object(second.first_suffix, 'live_controls',
                           return_value=({}, endpoint)),
              patch.object(second.partitions, 'open_partition',
                           side_effect=open_real_child),
              patch.object(second.paid, 'load_key', return_value='SYNTHETIC_KEY'),
              patch.object(second.paid, 'fetch', side_effect=fetch)):
            smoke_result = second.execute(self.path, self.manifest_sha, self.budget,
                                          7, 'smoke', smoke_review)
            self.assertTrue(smoke_result['completed'])
            self.assertTrue(second.strict_finished(self.manifest, self.manifest_sha,
                                                   7, 'smoke'))
            smoke = second.stage_paths(7, 'smoke')
            inspection = {'approved': True, 'statuses': ['ok'] * 3,
                          **{'smoke_' + part + '_sha256': second.sha(smoke[part])
                             for part in ('records', 'journal', 'raw')}}
            dev_review = self.review(7, 'development', inspection)
            development_result = second.execute(self.path, self.manifest_sha,
                self.budget, 7, 'development', dev_review)
            self.assertTrue(development_result['completed'])
        self.assertTrue(second.strict_finished(self.manifest, self.manifest_sha,
                                               7, 'development'))
        frozen = self.manifest['requests_by_condition']['P2']
        self.assertEqual([item['payload'] for item in frozen[:3]] +
                         [item['payload'] for item in frozen], dispatched)
        next_review = self.review(8, 'smoke')
        second.prepare(self.path, self.manifest_sha, self.budget, 8, 'smoke',
                       next_review)


if __name__ == '__main__':
    unittest.main()
