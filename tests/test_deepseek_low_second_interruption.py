"""Offline tests for the distinct DeepSeek low DEV-050 continuation."""
import io
import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import deepseek_low_second_interruption as run
import paid_budget_partitions_v3 as partitions


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


class DeepSeekLowSecondInterruptionTests(unittest.TestCase):
    def test_exact_49_position_prefix_and_no_replay_schedule(self):
        prefix = run.verify_stopped_prefix()
        self.assertEqual(prefix['attempted_ids'], run.IDS[:49])
        self.assertEqual(prefix['remaining_ids'], run.IDS[49:])
        self.assertEqual(prefix['prior_service_errors'], ['DEV-040', 'DEV-049'])
        self.assertEqual(prefix['invalid_ids'], ['DEV-039'])
        self.assertEqual(run.selected_ids(2, 'suffix'), run.IDS[49:])
        self.assertEqual(len(run.SEQUENCE), 13)
        self.assertEqual(run.SEQUENCE[1:], tuple((i, stage)
            for i in range(3, 9) for stage in ('smoke', 'development')))
        for stage in ((2, 'development'), (3, 'suffix'), (9, 'smoke')):
            with self.assertRaises(ValueError):
                run.selected_ids(*stage)

    def test_first_prefix_hash_pin_detects_mutation(self):
        changed = {**run.FIRST_EVIDENCE_SHA, 'records': '0' * 64}
        with patch.object(run, 'FIRST_EVIDENCE_SHA', changed):
            with self.assertRaisesRegex(ValueError, 'evidence hash changed'):
                run.verify_stopped_prefix()

    def test_first_child_seal_preserves_dev049_bound(self):
        seal = run.verify_old_seal(run.PREVIOUS / 'terminal-reconciliation-after-dev049.json',
                                   run.verify_stopped_prefix())
        self.assertEqual(seal['known_actual_usd'], '0.00202348')
        self.assertEqual(seal['unknown_upper_bound_usd'], '0.1069056')
        self.assertEqual(seal['released_usd'], '0.03107092')

    def test_historical_projection_keeps_failures_and_never_sent(self):
        result = run.project_original()
        self.assertEqual((result['attempted_count'], result['never_sent_count']), (49, 11))
        self.assertEqual(result['status_counts'], {'ok': 46, 'invalid_output': 1,
                         'service_error': 2, 'never_sent': 11})
        self.assertEqual(result['positions'][38]['status'], 'invalid_output')
        self.assertEqual(result['positions'][39]['status'], 'service_error')
        self.assertEqual(result['positions'][48]['status'], 'service_error')
        self.assertEqual([p['id'] for p in result['positions'][49:]], run.IDS[49:])
        self.assertNotIn('raw_error_response', json.dumps(result))

    def test_selected_payloads_are_original_frozen_requests(self):
        original = run.original_manifest()
        manifest = {'phases': original['phases'],
                    'requests_by_condition': original['requests_by_condition']}
        history = run.admission.source_state()
        endpoint = json.loads(json.dumps(history[2]))
        endpoint['pricing']['prompt'] = run.lower_price.NEW_PROMPT_PRICE
        for index, stage in run.SEQUENCE:
            rebuilt = run._rebuild_requests(manifest, index, stage, endpoint, history[3])
            self.assertEqual([x[0]['id'] for x in rebuilt], run.selected_ids(index, stage))
            self.assertEqual([x[1]['request_sha256'] for x in rebuilt],
                [x['request_sha256'] for x in run.selected_items(manifest, index, stage)])

    def synthetic_child(self, area, cap='0.20'):
        output = area / 'second-interruption-continuation-v1'
        output.mkdir()
        master = area / 'master.jsonl'
        budget = output / 'budget.json'
        partitions.allocate(master, budget, [{'id': run.PARTITION_ID, 'cap_usd': cap,
            'model': run.admission.MODEL, 'provider': run.admission.PROVIDER,
            'reasoning': 'low'}])
        return output, master, budget, output / ('budget-' + run.PARTITION_ID + '.jsonl')

    def test_child_budget_requires_exact_master_allocation(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            output, master, budget, child = self.synthetic_child(Path(temp))
            with patch.object(run, 'OUTPUT', output), patch.object(run.admission, 'MASTER', master):
                self.assertEqual(run.budget_entry(budget, require_fresh=True)['cap_usd'], '0.20')
                with self.assertRaisesRegex(ValueError, 'budget path differs'):
                    run.budget_entry(output / 'missing.json')
                self.assertEqual(run.rows(child), [{'event': 'budget', 'cap_usd': '0.20'}])

    def test_root_receipt_binds_exact_new_sources_and_ids(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            output, master, budget, _child = self.synthetic_child(Path(temp))
            manifest = {'controller': run.binding(run.__file__),
                'source_bindings': {'new_budget_manifest': run.binding(budget),
                    'first_terminal_reconciliation': run.binding(
                        run.PREVIOUS / 'terminal-reconciliation-after-dev049.json')},
                'partition_id': run.PARTITION_ID, 'child_cap_usd': '0.20'}
            review = output / 'phase-03-suffix.root-review.json'
            receipt = {'schema': run.SCHEMA + '-stage-review', 'approved': True,
                'manifest_sha256': 'fake-hash',
                'controller_sha256': manifest['controller']['sha256'],
                'first_terminal_reconciliation_sha256': manifest['source_bindings'][
                    'first_terminal_reconciliation']['sha256'],
                'new_budget_manifest_sha256': run.sha(budget),
                'partition_id': run.PARTITION_ID, 'child_cap_usd': '0.20',
                'phase_index': 2, 'stage': 'suffix', 'ids': run.IDS[49:]}
            review.write_text(json.dumps(receipt) + '\n')
            with patch.object(run, 'OUTPUT', output):
                run.verify_review(review, manifest, 'fake-hash', 2, 'suffix')
                receipt['ids'] = run.IDS[50:]
                review.write_text(json.dumps(receipt) + '\n')
                with self.assertRaisesRegex(ValueError, 'exact sources'):
                    run.verify_review(review, manifest, 'fake-hash', 2, 'suffix')

    def test_sealed_reconciled_child_verifies_history_but_refuses_dispatch(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            output, master, budget, _child = self.synthetic_child(Path(temp))
            partitions.reconcile_partition(master, budget, run.PARTITION_ID)
            with patch.object(run, 'OUTPUT', output), patch.object(run.admission, 'MASTER', master):
                self.assertEqual(run.budget_entry(budget)['cap_usd'], '0.20')
                with self.assertRaisesRegex(ValueError, 'sealed or reconciled'):
                    run.budget_entry(budget, require_dispatch=True)

    def test_terminal_reconciliation_hash_or_accounting_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            output, master, budget, _child = self.synthetic_child(Path(temp))
            partitions.reconcile_partition(master, budget, run.PARTITION_ID)
            data = run.rows(master)
            data[-1]['unknown_upper_bound_usd'] = '0.01'
            master.write_text(''.join(json.dumps(x) + '\n' for x in data))
            with patch.object(run, 'OUTPUT', output), patch.object(run.admission, 'MASTER', master):
                with self.assertRaisesRegex(ValueError, 'terminal reconciliation differs'):
                    run.budget_entry(budget)

    def test_frozen_manifest_historical_verification_and_no_new_dispatch_after_seal(self):
        prefix = run.verify_stopped_prefix()
        old = run.verify_old_seal(run.PREVIOUS / 'terminal-reconciliation-after-dev049.json',
                                  prefix)
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            output, master, budget, child = self.synthetic_child(Path(temp))
            manifest_path = output / 'manifest.json'
            with patch.object(run, 'OUTPUT', output), \
                 patch.object(run.admission, 'MASTER', master), \
                 patch.object(run, 'verify_stopped_prefix', return_value=prefix), \
                 patch.object(run, 'verify_old_seal', return_value=old):
                manifest = run.freeze(manifest_path, budget,
                    run.PREVIOUS / 'terminal-reconciliation-after-dev049.json')
                digest = run.sha(manifest_path)
                self.assertEqual(run.validate_manifest(manifest_path, digest), manifest)
                review = run.review_path(2, 'suffix')
                review.write_text(json.dumps({'schema': run.SCHEMA + '-stage-review',
                    'approved': True, 'manifest_sha256': digest,
                    'controller_sha256': manifest['controller']['sha256'],
                    'first_terminal_reconciliation_sha256': manifest['source_bindings'][
                        'first_terminal_reconciliation']['sha256'],
                    'new_budget_manifest_sha256': run.sha(budget),
                    'partition_id': run.PARTITION_ID, 'child_cap_usd': '0.20',
                    'phase_index': 2, 'stage': 'suffix', 'ids': run.IDS[49:]}) + '\n')
                _, target = run.prepare(manifest_path, digest, budget, 2, 'suffix', review)
                self.assertFalse(target['claim'].exists())
                target['claim'].write_text('{}\n')
                with self.assertRaises(FileExistsError):
                    run.prepare(manifest_path, digest, budget, 2, 'suffix', review)
                target['claim'].unlink()
                partitions.reconcile_partition(master, budget, run.PARTITION_ID)
                self.assertEqual(run.validate_manifest(manifest_path, digest), manifest)
                with self.assertRaisesRegex(ValueError, 'sealed or reconciled'):
                    run.prepare(manifest_path, digest, budget, 2, 'suffix', review)

    def _execute_fixture(self, area, responses, cap='0.20'):
        output, master, budget, child = self.synthetic_child(area, cap)
        original = run.original_manifest()
        manifest = {'schema': run.SCHEMA, 'phases': original['phases'],
            'requests_by_condition': original['requests_by_condition'],
            'partition_id': run.PARTITION_ID, 'child_cap_usd': cap,
            'source_bindings': {'new_budget_manifest': run.binding(budget),
                'first_terminal_reconciliation': run.binding(
                    run.PREVIOUS / 'terminal-reconciliation-after-dev049.json')},
            'controller': run.binding(run.__file__),
            'method': 'descriptive-second-interruption-continuation'}
        historical = run.admission.source_state()
        model, endpoint = historical[3], json.loads(json.dumps(historical[2]))
        endpoint['pricing']['prompt'] = run.lower_price.NEW_PROMPT_PRICE
        catalog = {'data': [model]}
        endpoints = {'data': {'id': run.admission.MODEL, 'endpoints': [endpoint]}}
        target = run.original.paths(output, 2, 'suffix')
        review = output / 'phase-03-suffix.root-review.json'
        review.write_text(json.dumps({'schema': run.SCHEMA + '-stage-review',
            'approved': True, 'manifest_sha256': 'fake-hash',
            'controller_sha256': manifest['controller']['sha256'],
            'first_terminal_reconciliation_sha256': manifest['source_bindings'][
                'first_terminal_reconciliation']['sha256'],
            'new_budget_manifest_sha256': run.sha(budget),
            'partition_id': run.PARTITION_ID, 'child_cap_usd': cap,
            'phase_index': 2, 'stage': 'suffix', 'ids': run.IDS[49:]}) + '\n')
        calls = []
        stream = iter(responses)

        def opener(_request, timeout):
            self.assertEqual(timeout, 300)
            calls.append(True)
            body = next(stream)
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
        return result, target, child, calls, manifest, output, master, budget

    def _response(self):
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
            'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}
        return {'model': run.admission.MODEL, 'provider': 'OpenInference',
            'usage': {'cost': '0.0002', 'prompt_tokens': 100, 'completion_tokens': 20},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(prediction)}}]}

    def test_cap_refusal_sends_only_dev050_and_preserves_dev051(self):
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            result, target, child, calls, *_ = self._execute_fixture(
                Path(temp), [self._response()], cap=str(run.RESERVE))
            self.assertEqual(result['status'], 'child_cap')
            self.assertEqual(result['next_unsent_id'], 'DEV-051')
            self.assertEqual(len(calls), 1)
            self.assertEqual([x['id'] for x in run.rows(target['records'])], ['DEV-050'])
            self.assertEqual(run.rows(target['journal'])[-1]['event'], 'admission_stopped')

    def test_http429_preserves_private_raw_and_no_retry(self):
        historical_prefix = run.verify_stopped_prefix()
        with tempfile.TemporaryDirectory(dir=run.ROOT / 'results') as temp:
            error = urllib.error.HTTPError('https://example.invalid', 429, 'rate limit',
                                           {'content-type': 'application/json'},
                                           io.BytesIO(b'{"error":{"account_id":"private"}}'))
            result, target, child, calls, manifest, output, master, budget = \
                self._execute_fixture(Path(temp), [error])
            error.close()
            self.assertEqual(result['stopped_id'], 'DEV-050')
            self.assertEqual(len(calls), 1)
            record = run.rows(target['records'])[0]
            self.assertEqual((record['status'], record['cost_unknown']), ('service_error', True))
            self.assertEqual(run.rows(child)[-1]['event'], 'reserve')
            with patch.object(run, 'OUTPUT', output), \
                 patch.object(run.admission, 'MASTER', master), \
                 patch.object(run, 'verify_stopped_prefix', return_value=historical_prefix):
                projected = run.reconcile_suffix(manifest, 'fake-hash')
            self.assertEqual(projected['status'], 'stopped')
            self.assertEqual(projected['status_counts']['service_error'], 3)
            self.assertNotIn('account_id', json.dumps(projected))


if __name__ == '__main__':
    unittest.main()
