"""Offline checks for the never-sent DeepSeek low suffix and later phases."""
import json
import io
from decimal import Decimal
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import deepseek_low_interruption_continuation as run
import paid_budget_partitions_v2 as partitions
import openrouter_budget_v2 as budgets


class FakeResponse:
    status = 200
    headers = {'content-type': 'application/json'}

    def __init__(self, body):
        self.body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.body.close()

    def read(self, amount):
        return self.body.read(amount)


class DeepSeekLowInterruptionTests(unittest.TestCase):
    def test_real_stopped_prefix_is_exact_and_never_replays(self):
        summary = run.verify_stopped_prefix()
        self.assertEqual(summary['attempted_ids'], [f'DEV-{n:03d}' for n in range(1, 41)])
        self.assertEqual(summary['remaining_ids'], [f'DEV-{n:03d}' for n in range(41, 61)])
        self.assertEqual(summary['failed_id'], 'DEV-040')
        self.assertEqual(summary['invalid_ids'], ['DEV-039'])
        self.assertEqual(run.SEQUENCE[0], (2, 'suffix'))
        self.assertEqual(len(run.SEQUENCE), 13)

    def test_original_later_record_mutation_fails(self):
        source = run.BASE / 'phase-03-development.records.jsonl'
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            shutil.copy2(source, base / source.name)
            for part in ('claim.json', 'journal.jsonl', 'raw.jsonl'):
                name = 'phase-03-development.' + part
                shutil.copy2(run.BASE / name, base / name)
            p = base / source.name
            lines = p.read_text().splitlines()
            changed = json.loads(lines[38]); changed['id'] = 'DEV-038'
            lines[38] = json.dumps(changed)
            p.write_text('\n'.join(lines) + '\n')
            with patch.object(run, 'BASE', base):
                with self.assertRaises(ValueError):
                    run.verify_stopped_prefix()

    def test_pending_unknown_and_insufficient_child_cannot_freeze(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            with patch.object(run, 'OUTPUT', output):
                with self.assertRaises(ValueError):
                    run.freeze(output / 'manifest.json', run.BASE / 'budget.json',
                               output / 'missing-reconciliation.json')
            self.assertFalse((output / 'manifest.json').exists())

    def test_real_old_child_is_sealed_with_full_unknown_bound(self):
        seal = run.verify_old_seal(run.BASE / 'terminal-reconciliation-after-dev040.json',
                                   run.verify_stopped_prefix())
        self.assertEqual(seal['known_actual_usd'], '0.04109562')
        self.assertEqual(seal['unknown_upper_bound_usd'], '0.1069056')
        self.assertEqual(seal['released_usd'], '0.10199878')

    def test_root_receipt_requires_exact_suffix_and_budget(self):
        self.assertEqual(run.selected_ids(2, 'suffix'), [f'DEV-{n:03d}' for n in range(41, 61)])
        self.assertEqual(run.selected_ids(3, 'smoke'), ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertEqual(len(run.selected_ids(8, 'development')), 60)
        for stage in ((2, 'development'), (3, 'suffix'), (9, 'smoke')):
            with self.assertRaises(ValueError):
                run.selected_ids(*stage)

    def _execute_fixture(self, temp, responses, cap='0.12'):
        base = Path(temp)
        output = base / 'interruption-continuation-v1'
        output.mkdir()
        master = base / 'master.jsonl'
        budget = output / 'budget.json'
        pid = 'deepseek-low-interruption-20260929'
        partitions.allocate(master, budget, [{'id': pid, 'cap_usd': cap,
            'model': run.admission.MODEL, 'provider': run.admission.PROVIDER,
            'reasoning': 'low'}])
        original = run.original_manifest()
        manifest = {'schema': run.SCHEMA, 'phases': original['phases'],
            'requests_by_condition': original['requests_by_condition'],
            'partition_id': pid, 'child_cap_usd': cap,
            'source_bindings': {
                'new_budget_manifest': run.binding(budget),
                'old_terminal_reconciliation': run.binding(
                    run.BASE / 'terminal-reconciliation-after-dev040.json')},
            'controller': run.binding(run.__file__),
            'method': 'descriptive-continuation-after-service-error'}
        phase = original['phases'][2]
        historical = run.admission.source_state()
        model = historical[3]
        endpoint = json.loads(json.dumps(historical[2]))
        endpoint['pricing']['prompt'] = run.lower_price.NEW_PROMPT_PRICE
        catalog = {'data': [model]}
        endpoints = {'data': {'id': run.admission.MODEL, 'endpoints': [endpoint]}}
        target = run.original.paths(output, 2, 'suffix')
        review = output / 'phase-03-suffix.root-review.json'
        review.write_text(json.dumps({'schema': run.SCHEMA + '-stage-review',
            'approved': True, 'manifest_sha256': 'fake-hash',
            'controller_sha256': manifest['controller']['sha256'],
            'old_terminal_reconciliation_sha256':
                manifest['source_bindings']['old_terminal_reconciliation']['sha256'],
            'new_budget_manifest_sha256':
                manifest['source_bindings']['new_budget_manifest']['sha256'],
            'partition_id': pid, 'child_cap_usd': cap,
            'phase_index': 2, 'stage': 'suffix',
            'ids': run.selected_ids(2, 'suffix')}) + '\n')
        calls = []
        items = iter(responses)

        def opener(_request, timeout):
            self.assertEqual(timeout, 300)
            calls.append(True)
            body = next(items)
            if isinstance(body, Exception):
                raise body
            return FakeResponse(body if isinstance(body, bytes) else json.dumps(body).encode())

        with patch.object(run, 'OUTPUT', output), \
             patch.object(run.admission, 'MASTER', master), \
             patch.object(run, 'prepare', return_value=(manifest, target)), \
             patch.object(run.paid, 'fetch', side_effect=[catalog, endpoints]), \
             patch.object(run.lower_price, 'checked_live_context', return_value=historical), \
             patch.object(run.paid, 'load_key', return_value='fake-key'), \
             patch.object(run.captured_transport.transport.OPENER, 'open', side_effect=opener):
            result = run.execute(output / 'manifest.json', 'fake-hash', budget, 2,
                                 'suffix', review)
        child = output / ('budget-' + pid + '.jsonl')
        return result, target, child, calls, manifest

    def _response(self):
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
            'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}
        return {'model': run.admission.MODEL, 'provider': 'OpenInference',
            'usage': {'cost': '0.0002', 'prompt_tokens': 100,
                      'completion_tokens': 20},
            'choices': [{'finish_reason': 'stop',
                'message': {'content': json.dumps(prediction)}}]}

    def test_real_temp_child_stops_before_second_http_when_next_reserve_cannot_fit(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            result, target, child, calls, _manifest = self._execute_fixture(temp,
                [self._response()], cap=str(run.RESERVE))
            self.assertEqual(result['status'], 'child_cap')
            self.assertEqual(result['next_unsent_id'], 'DEV-042')
            self.assertEqual(len(calls), 1)
            self.assertEqual([x['id'] for x in run.rows(target['records'])], ['DEV-041'])
            self.assertEqual(run.rows(target['journal'])[-1]['event'], 'admission_stopped')
            ledger = budgets.BudgetLedger(child, cap_limit=run.RESERVE)
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.0002'))
                self.assertEqual(ledger.state()[1], set())
            finally:
                ledger.close()

    def test_malformed_http_200_saves_bytes_and_full_unknown_bound_without_replay(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            malformed = b'{"choices": [broken'
            result, target, child, calls, _manifest = self._execute_fixture(temp,
                [malformed], cap='0.12')
            self.assertEqual(result['stopped_id'], 'DEV-041')
            self.assertEqual(len(calls), 1)
            raw = run.rows(target['raw'])[0]
            import base64
            self.assertEqual(base64.b64decode(raw['body_base64']), malformed)
            row = run.rows(target['records'])[0]
            self.assertEqual(row['status'], 'service_error')
            self.assertTrue(row['cost_unknown'])
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('0.12'))
            try:
                self.assertEqual(ledger.accounted(), run.RESERVE)
                self.assertEqual(len(ledger.state()[1]), 1)
            finally:
                ledger.close()
            self.assertTrue(target['claim'].exists())

    def test_complete_suffix_has_strict_receipts_and_preserves_original_failed_denominator(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            result, target, child, calls, manifest = self._execute_fixture(temp,
                [self._response()] * 20, cap='0.12')
            self.assertEqual(result, {'completed': True, 'count': 20})
            self.assertEqual(len(calls), 20)
            with patch.object(run, 'OUTPUT', Path(temp) / 'interruption-continuation-v1'), \
                 patch.object(run.admission, 'MASTER', Path(temp) / 'master.jsonl'):
                self.assertTrue(run.strict_finished(manifest, 'fake-hash', 2, 'suffix'))
                projection = run.reconcile_suffix(manifest, 'fake-hash')
            self.assertEqual(projection['status'], 'closed_with_service_error')
            self.assertEqual(len(projection['positions']), 60)
            self.assertEqual(projection['positions'][38]['status'], 'invalid_output')
            self.assertEqual(projection['positions'][39]['status'], 'service_error')
            self.assertEqual(projection['positions'][40]['id'], 'DEV-041')
            self.assertNotIn('raw_error_response', json.dumps(projection))

    def test_http_429_private_error_is_bound_but_not_exported(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            private = b'{"error":"queue_timeout","user_id":"private-account"}'
            error = urllib.error.HTTPError('https://example.invalid', 429,
                'queue', {'retry-after': '1'}, io.BytesIO(private))
            result, target, child, calls, manifest = self._execute_fixture(temp,
                [error], cap='0.12')
            self.assertEqual(result['stopped_id'], 'DEV-041')
            import base64
            self.assertEqual(base64.b64decode(run.rows(target['raw'])[0]['body_base64']), private)
            with patch.object(run, 'OUTPUT', Path(temp) / 'interruption-continuation-v1'), \
                 patch.object(run.admission, 'MASTER', Path(temp) / 'master.jsonl'):
                projection = run.reconcile_suffix(manifest, 'fake-hash')
            self.assertEqual(projection['status'], 'stopped')
            self.assertEqual(projection['positions'][40]['http_status'], 429)
            self.assertEqual(projection['positions'][41]['status'], 'never_sent')
            self.assertNotIn('private-account', json.dumps(projection))
            self.assertEqual(projection['positions'][40]['unknown_upper_bound_usd'],
                             str(run.RESERVE))
            error.close()

    def test_parseable_but_structurally_invalid_http_200_is_retained_as_service_error(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            result, target, _child, _calls, manifest = self._execute_fixture(temp,
                [{}], cap='0.12')
            self.assertEqual(result['stopped_id'], 'DEV-041')
            self.assertEqual(run.rows(target['records'])[0]['status'], 'service_error')
            with patch.object(run, 'OUTPUT', Path(temp) / 'interruption-continuation-v1'), \
                 patch.object(run.admission, 'MASTER', Path(temp) / 'master.jsonl'):
                projected = run.reconcile_suffix(manifest, 'fake-hash')
            self.assertEqual(projected['positions'][40]['status'], 'service_error')
            self.assertEqual(projected['positions'][40]['unknown_upper_bound_usd'],
                             str(run.RESERVE))
            self.assertEqual(projected['never_sent_count'], 19)

    def test_known_billed_malformed_object_remains_failed_with_known_charge(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            malformed = {'usage': {'cost': '0.0002', 'prompt_tokens': 10},
                         'choices': [None]}
            result, target, child, _calls, manifest = self._execute_fixture(temp,
                [malformed], cap='0.12')
            self.assertEqual(result['status'], 'service_error')
            row = run.rows(target['records'])[0]
            self.assertEqual(row['observed_cost_usd'], '0.0002')
            self.assertFalse(row['cost_unknown'])
            with patch.object(run, 'OUTPUT', Path(temp) / 'interruption-continuation-v1'), \
                 patch.object(run.admission, 'MASTER', Path(temp) / 'master.jsonl'):
                projected = run.reconcile_suffix(manifest, 'fake-hash')
            self.assertEqual(projected['positions'][40]['status'], 'service_error')
            self.assertEqual(projected['positions'][40]['observed_cost_usd'], '0.0002')
            self.assertEqual(projected['positions'][40]['unknown_upper_bound_usd'], '0')
            self.assertEqual(projected['new_known_actual_usd'], '0.0002')

    def test_unstarted_suffix_reports_original_40_and_20_never_sent_without_score(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            output = Path(temp) / 'interruption-continuation-v1'
            output.mkdir()
            manifest = {'method': 'descriptive-continuation-after-service-error',
                'source_bindings': {}}
            with patch.object(run, 'OUTPUT', output):
                result = run.reconcile_suffix(manifest, 'fake-hash')
            self.assertEqual(result['status'], 'not_started')
            self.assertEqual(result['attempted_count'], 40)
            self.assertEqual(result['never_sent_count'], 20)
            self.assertEqual(len(result['positions']), 60)
            self.assertNotIn('score', result)

    def test_original_public_projection_has_no_private_error_body_or_partial_score(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            with patch.object(run, 'OUTPUT', Path(temp) / 'interruption-continuation-v1'):
                projected = run.project_original()
        text = json.dumps(projected)
        self.assertEqual(projected['status_counts'],
            {'ok': 38, 'invalid_output': 1, 'service_error': 1, 'never_sent': 20})
        self.assertEqual(projected['old_known_actual_usd'], '0.04109562')
        self.assertEqual(projected['old_unknown_charge_upper_bound_usd'], '0.1069056')
        self.assertFalse(projected['completed_pass'])
        self.assertNotIn('raw_error_response', text)
        self.assertNotIn('user_id', text)

    def test_completed_suffix_allows_next_smoke_but_not_development_without_inspection(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            _result, _target, _child, _calls, manifest = self._execute_fixture(temp,
                [self._response()] * 20, cap='0.12')
            output = Path(temp) / 'interruption-continuation-v1'
            budget = output / 'budget.json'
            for stage in ('smoke', 'development'):
                path = output / f'phase-04-{stage}.root-review.json'
                path.write_text(json.dumps({'schema': run.SCHEMA + '-stage-review',
                    'approved': True, 'manifest_sha256': 'fake-hash',
                    'controller_sha256': manifest['controller']['sha256'],
                    'old_terminal_reconciliation_sha256':
                        manifest['source_bindings']['old_terminal_reconciliation']['sha256'],
                    'new_budget_manifest_sha256':
                        manifest['source_bindings']['new_budget_manifest']['sha256'],
                    'partition_id': manifest['partition_id'],
                    'child_cap_usd': manifest['child_cap_usd'],
                    'phase_index': 3, 'stage': stage,
                    'ids': run.selected_ids(3, stage)}) + '\n')
            with patch.object(run, 'OUTPUT', output), \
                 patch.object(run.admission, 'MASTER', Path(temp) / 'master.jsonl'), \
                 patch.object(run, 'validate_manifest', return_value=manifest):
                prepared, target = run.prepare(output / 'manifest.json', 'fake-hash', budget,
                    3, 'smoke', output / 'phase-04-smoke.root-review.json')
                self.assertEqual(prepared, manifest)
                self.assertFalse(target['claim'].exists())
                with self.assertRaises(ValueError):
                    run.prepare(output / 'manifest.json', 'fake-hash', budget,
                        3, 'development', output / 'phase-04-development.root-review.json')


if __name__ == '__main__':
    unittest.main()
