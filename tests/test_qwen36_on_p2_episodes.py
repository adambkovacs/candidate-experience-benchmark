"""Offline evidence and admission checks for never-sent Qwen P2 episodes."""
import base64
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/qwen36_on_p2_episodes.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('qwen36_on_p2_episodes', SCRIPT)
episodes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(episodes)


class QwenEpisodesTest(unittest.TestCase):
    def test_initial_lineage_is_exact_42_with_five_full_bound_429s(self):
        state = episodes.initial_state()
        self.assertEqual(state['attempted_ids'], episodes.ALL_IDS[:42])
        self.assertEqual(state['failed_ids'], ['DEV-033', 'DEV-039', 'DEV-040', 'DEV-041', 'DEV-042'])
        self.assertEqual(len(state['requests']), 60)
        manifest = episodes.expected_manifest(1)
        self.assertEqual(manifest['request_ids'], episodes.ALL_IDS[42:])
        self.assertEqual(manifest['call_bound_usd'], '0.5382144')
        self.assertEqual(manifest['previous_attempted_ids'] + manifest['request_ids'], episodes.ALL_IDS)

    def test_successor_derives_only_ids_not_attempted_in_prior_episode(self):
        state = episodes.initial_state()
        state['attempted_ids'] = episodes.ALL_IDS[:43]
        state['failed_ids'] = episodes.FAILED + ['DEV-043']
        state['previous_reconciliation'] = {'file': 'episode-001/reconciliation.json', 'sha256': 'x'}
        with patch.object(episodes, 'predecessor', return_value=state):
            manifest = episodes.expected_manifest(2)
        self.assertEqual(manifest['request_ids'], episodes.ALL_IDS[43:])
        self.assertEqual(manifest['call_bound_usd'], str(Decimal('0.0299008') * 17))
        self.assertNotIn('DEV-043', manifest['request_ids'])

    def test_captured_raw_redacts_credential_before_durable_save(self):
        with tempfile.TemporaryFile(mode='w+') as out:
            body = b'{"secret":"Bearer abc-secret","usage":{"cost":0.01}}'
            result = episodes.capture(io.BytesIO(body), 'abc-secret', 'DEV-043', 'attempt-1', 'request-hash', out)
            out.seek(0)
            persisted = out.read()
        self.assertNotIn('abc-secret', persisted)
        self.assertTrue(result['credential_redacted'])
        self.assertIn(b'[REDACTED]', base64.b64decode(result['body_base64']))

    def test_incomplete_http_error_retains_bounded_partial_and_read_error(self):
        class Partial:
            def read(self, amount):
                raise episodes.http.client.IncompleteRead(b'partial secret')
        with tempfile.TemporaryFile(mode='w+') as out:
            result = episodes.capture(Partial(), 'secret', 'DEV-043', 'attempt-1', 'hash', out, 429)
        self.assertEqual(result['read_error'], 'IncompleteRead')
        self.assertEqual(result['http_status'], 429)
        self.assertNotIn(b'secret', base64.b64decode(result['body_base64']))

    def test_public_route_and_frozen_request_preflight_rejects_price_or_identity_drift(self):
        manifest = episodes.expected_manifest(1)
        row = json.loads(episodes.v4.OUTPUT.read_text().splitlines()[0])
        model = row['model_catalog_entry']
        endpoint = row['provider_endpoint']
        catalog = {'data': [model]}
        endpoints = {'data': {'id': episodes.recovery.MODEL, 'endpoints': [endpoint]}}
        with patch.object(episodes.paid, 'fetch', side_effect=[catalog, endpoints]):
            self.assertEqual(episodes.live_controls(manifest)[1]['tag'], 'akashml/fp8')
        wrong_price = json.loads(json.dumps(endpoint))
        wrong_price['pricing']['completion'] = '0.000001'
        with patch.object(episodes.paid, 'fetch', side_effect=[catalog, {'data': {'id': episodes.recovery.MODEL, 'endpoints': [wrong_price]}}]):
            with self.assertRaisesRegex(ValueError, 'price|route'):
                episodes.live_controls(manifest)
        wrong_provider = json.loads(json.dumps(endpoint))
        wrong_provider['provider_name'] = 'Different provider'
        with patch.object(episodes.paid, 'fetch', side_effect=[catalog, {'data': {'id': episodes.recovery.MODEL, 'endpoints': [wrong_provider]}}]):
            with self.assertRaisesRegex(ValueError, 'route'):
                episodes.live_controls(manifest)

    def test_budget_gate_rejects_cap_below_full_18_call_bound(self):
        manifest = episodes.expected_manifest(1)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            budget = folder / 'budget.json'
            review = folder / 'root-review.json'
            budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                'master_ledger': str(folder / 'results/openrouter-paid-budget.jsonl'),
                'partitions': [{'id': 'qwen-episode-test', 'model': episodes.recovery.MODEL,
                    'provider': episodes.recovery.PROVIDER, 'reasoning': 'on',
                    'cap_usd': '0.53', 'child_ledger': str(folder / 'child.jsonl')}]}))
            review.write_text(json.dumps({'schema': episodes.REVIEW_SCHEMA, 'approved': True,
                'manifest_sha256': 'manifest-hash', 'controller_sha256': manifest['controller']['sha256'],
                'budget_manifest_sha256': episodes.recovery.sha(budget),
                'partition_id': 'qwen-episode-test', 'request_ids': manifest['request_ids'],
                'failed_ids_retained': manifest['failed_ids'], 'cooldown_note': 'Reviewed after 429'}))
            with patch.object(episodes, 'ROOT', folder), patch.object(episodes, 'episode_dir', return_value=folder):
                with self.assertRaisesRegex(ValueError, 'partition route or bound'):
                    episodes.review_gate(manifest, 'manifest-hash', review, budget, 'qwen-episode-test')

    def test_started_without_attributed_raw_is_ambiguous_and_blocks_successor(self):
        manifest = episodes.expected_manifest(1)
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'manifest.json').write_text('{}')
            report = {'evidence': {key: {'file': key, 'sha256': 'hash'} for key in
                                   ('claim', 'review', 'journal', 'responses', 'attempts')},
                      'budget_manifest': {'sha256': 'budget-hash'}}
            saved = {
                'claim': json.dumps({'manifest_sha256': 'hash', 'review_sha256': 'hash',
                                     'budget_manifest_sha256': 'budget-hash', 'partition_id': 'test'}).encode(),
                'review': json.dumps({'schema': episodes.REVIEW_SCHEMA, 'approved': True,
                                      'manifest_sha256': 'hash', 'controller_sha256': manifest['controller']['sha256'],
                                      'budget_manifest_sha256': 'budget-hash', 'partition_id': 'test',
                                      'request_ids': manifest['request_ids'],
                                      'failed_ids_retained': manifest['failed_ids']}).encode(),
                'journal': b'\n'.join(json.dumps(x).encode() for x in [
                    {'event': 'episode_started'},
                    {'event': 'request_started', 'id': 'DEV-043', 'attempt_id': 'attempt-1', 'request_sha256': 'request-hash'},
                    {'event': 'episode_stopped', 'id': 'DEV-043'}]) + b'\n',
                'responses': b'', 'attempts': b''}
            with patch.object(episodes, 'episode_dir', return_value=folder), \
                 patch.object(episodes, 'validate_manifest', return_value=manifest), \
                 patch.object(episodes, 'read_bound', side_effect=lambda item: saved[item['file']]), \
                 patch.object(episodes.recovery, 'sha', return_value='hash'):
                with self.assertRaisesRegex(ValueError, 'delivery ambiguous'):
                    episodes.validate_reconciliation(1, report)

    def test_reconciliation_requires_full_unknown_charge_bound(self):
        manifest = episodes.expected_manifest(1)
        request = json.loads(episodes.recovery.source(manifest['requests'][0]).read_text())['request']
        request_sha = episodes.paid.digest(json.dumps(request, sort_keys=True))
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'results').mkdir()
            (folder / 'manifest.json').write_text('{}')
            pid = 'qwen-episode-test'
            event = {'event': 'partition_reconciled', 'partition_id': pid,
                     'child_sha256': 'child-hash', 'known_actual_usd': '0',
                     'unknown_upper_bound_usd': '0.0299008'}
            (folder / 'results/openrouter-paid-budget.jsonl').write_text(json.dumps(event) + '\n')
            report = {'schema': episodes.CONTRACT + '-reconciliation', 'episode_index': 1,
                      'manifest_sha256': 'manifest-hash',
                      'previous_attempted_ids': manifest['previous_attempted_ids'],
                      'attempted_ids': episodes.ALL_IDS[:43], 'failed_ids': episodes.FAILED + ['DEV-043'],
                      'remaining_never_sent_ids': episodes.ALL_IDS[43:],
                      'evidence': {key: {'file': key, 'sha256': 'review-hash' if key == 'review' else 'x'}
                                   for key in ('claim', 'review', 'journal', 'responses', 'attempts')},
                      'budget_manifest': {'file': 'budget', 'sha256': 'budget-hash'},
                      'child_ledger': {'file': 'child.jsonl', 'sha256': 'child-hash'},
                      'master_reconciliation_event': event}
            def jsonl(*items):
                return b''.join(json.dumps(x).encode() + b'\n' for x in items)
            saved = {
                'claim': json.dumps({'manifest_sha256': 'manifest-hash', 'review_sha256': 'review-hash',
                                     'budget_manifest_sha256': 'budget-hash', 'partition_id': pid}).encode(),
                'review': json.dumps({'schema': episodes.REVIEW_SCHEMA, 'approved': True,
                                      'manifest_sha256': 'manifest-hash',
                                      'controller_sha256': manifest['controller']['sha256'],
                                      'budget_manifest_sha256': 'budget-hash', 'partition_id': pid,
                                      'request_ids': manifest['request_ids'],
                                      'failed_ids_retained': manifest['failed_ids']}).encode(),
                'journal': jsonl({'event': 'episode_started'},
                    {'event': 'request_started', 'id': 'DEV-043', 'attempt_id': 'attempt-1',
                     'request_sha256': request_sha},
                    {'event': 'request_finished', 'id': 'DEV-043', 'attempt_id': 'attempt-1',
                     'status': 'service_error', 'billing_ok': False, 'cost_unknown': True},
                    {'event': 'episode_stopped', 'id': 'DEV-043', 'reason': 'service_error'}),
                'responses': jsonl({'id': 'DEV-043', 'attempt_id': 'attempt-1',
                    'request_sha256': request_sha, 'http_status': 429,
                    'body_base64': base64.b64encode(b'{"error":"rate limit"}').decode()}),
                'attempts': jsonl({'id': 'DEV-043', 'attempt_id': 'attempt-1',
                    'request': request, 'request_sha256': request_sha, 'reference_labels_read': False,
                    'requested_model': episodes.recovery.MODEL, 'reasoning_effort': 'on',
                    'request_timeout_seconds': episodes.TIMEOUT, 'budget_partition_id': pid,
                    'manifest_sha256': 'manifest-hash', 'timing_kind': 'client_request_elapsed',
                    'elapsed_seconds': 1.25,
                    'status': 'service_error', 'cost_unknown': True, 'billing_ok': False}),
                'budget': json.dumps({'partitions': [{'id': pid, 'child_ledger': str(folder / 'child.jsonl')}]}).encode(),
                'child.jsonl': jsonl({'event': 'budget', 'cap_usd': '0.5382144'},
                    {'event': 'reserve', 'id': 'irrelevant', 'attempt_id': 'attempt-1',
                     'record_id': 'DEV-043', 'usd': '0.0299008'},
                    {'event': 'unknown_cost_accounted_as_upper_bound', 'attempt_id': 'attempt-1',
                     'usd': '0.0299008'}, {'event': 'partition_closed'})}
            original_sha = episodes.recovery.sha
            with patch.object(episodes, 'ROOT', folder), \
                 patch.object(episodes, 'episode_dir', return_value=folder), \
                 patch.object(episodes, 'validate_manifest', return_value=manifest), \
                 patch.object(episodes, 'read_bound', side_effect=lambda item: saved[item['file']]), \
                 patch.object(episodes.recovery, 'sha', side_effect=lambda path:
                     'manifest-hash' if Path(path) == folder / 'manifest.json' else original_sha(path)):
                self.assertEqual(episodes.validate_reconciliation(1, report), report)
                response = episodes.lines(saved['responses'])
                response[0]['id'] = 'DEV-044'
                saved['responses'] = jsonl(*response)
                with self.assertRaisesRegex(ValueError, 'Started/raw/attempt identity differs'):
                    episodes.validate_reconciliation(1, report)
                response[0]['id'] = 'DEV-043'
                saved['responses'] = jsonl(*response)
                child = episodes.lines(saved['child.jsonl'])
                child[2]['usd'] = '0'
                saved['child.jsonl'] = jsonl(*child)
                with self.assertRaisesRegex(ValueError, 'settled amounts differ|full-bound accounting'):
                    episodes.validate_reconciliation(1, report)
                child[2] = {'event': 'settle', 'attempt_id': 'attempt-1', 'usd': '0.01'}
                saved['child.jsonl'] = jsonl(*child)
                attempt = episodes.lines(saved['attempts'])
                attempt[0].update(cost_unknown=False, billing_ok=True, observed_cost_usd='0.01')
                saved['attempts'] = jsonl(*attempt)
                journal = episodes.lines(saved['journal'])
                journal[2].update(cost_unknown=False, billing_ok=True)
                saved['journal'] = jsonl(*journal)
                event['known_actual_usd'] = '0.01'
                event['unknown_upper_bound_usd'] = '0'
                report['master_reconciliation_event'] = event
                (folder / 'results/openrouter-paid-budget.jsonl').write_text(json.dumps(event) + '\n')
                self.assertEqual(episodes.validate_reconciliation(1, report), report)
                attempt[0]['observed_cost_usd'] = '0.02'
                saved['attempts'] = jsonl(*attempt)
                with self.assertRaisesRegex(ValueError, 'settled charge differs'):
                    episodes.validate_reconciliation(1, report)

                # An otherwise valid response without a provider charge stops,
                # then can reconcile only after the full hold is accounted.
                prior = json.loads(episodes.v4.ORIGINAL.read_text().splitlines()[0])
                raw = prior['raw_response']
                raw.pop('usage', None)
                saved['responses'] = jsonl({'id': 'DEV-043', 'attempt_id': 'attempt-1',
                    'request_sha256': request_sha, 'http_status': None,
                    'body_base64': base64.b64encode(json.dumps(raw).encode()).decode()})
                attempt[0].update(status='ok', cost_unknown=True, billing_ok=False,
                                  observed_cost_usd=None, raw_response=raw,
                                  provider_endpoint=prior['provider_endpoint'],
                                  prediction=prior['prediction'])
                saved['attempts'] = jsonl(*attempt)
                journal[2].update(status='ok', cost_unknown=True, billing_ok=False)
                journal[3]['reason'] = 'ok'
                saved['journal'] = jsonl(*journal)
                child[2] = {'event': 'unknown_cost_accounted_as_upper_bound',
                            'attempt_id': 'attempt-1', 'usd': '0.0299008'}
                saved['child.jsonl'] = jsonl(*child)
                event['known_actual_usd'] = '0'
                event['unknown_upper_bound_usd'] = '0.0299008'
                report['failed_ids'] = episodes.FAILED.copy()
                (folder / 'results/openrouter-paid-budget.jsonl').write_text(json.dumps(event) + '\n')
                self.assertEqual(episodes.validate_reconciliation(1, report), report)

                # Captured malformed HTTP200 bytes retain a service error and
                # can be reconciled after the same explicit upper-bound action.
                saved['responses'] = jsonl({'id': 'DEV-043', 'attempt_id': 'attempt-1',
                    'request_sha256': request_sha, 'http_status': None,
                    'body_base64': base64.b64encode(b'{malformed').decode()})
                attempt[0].update(status='service_error', error_type='JSONDecodeError')
                attempt[0].pop('raw_response')
                saved['attempts'] = jsonl(*attempt)
                journal[2]['status'] = 'service_error'
                journal[3]['reason'] = 'service_error'
                saved['journal'] = jsonl(*journal)
                report['failed_ids'] = episodes.FAILED + ['DEV-043']
                self.assertEqual(episodes.validate_reconciliation(1, report), report)


if __name__ == '__main__':
    unittest.main()
