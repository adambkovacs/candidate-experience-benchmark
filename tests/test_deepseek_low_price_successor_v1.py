"""Offline price-amendment gates; no key, reservation, or provider request."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_price_successor_v1 as successor


class LowerPriceSuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((successor.BASE / 'manifest.json').read_text())
        cls.phase = cls.manifest['phases'][1]
        cls.history, cls.controls, cls.historical_endpoint, cls.historical_model = (
            successor.admission.source_state())

    def catalogs(self, prompt=successor.NEW_PROMPT_PRICE, **changes):
        endpoint = deepcopy(self.historical_endpoint)
        endpoint['pricing']['prompt'] = prompt
        endpoint.update(changes)
        return ({'data': [deepcopy(self.historical_model)]},
                {'data': {'id': successor.admission.MODEL, 'endpoints': [endpoint]}}, endpoint)

    def test_exact_lower_price_preserves_request_bytes_and_reserve(self):
        catalog, endpoints, endpoint = self.catalogs()
        context = successor.checked_live_context(self.manifest, self.phase,
            'development', catalog, endpoints)
        self.assertEqual(context[2], endpoint)
        self.assertEqual(context[0], self.history)
        self.assertEqual(context[1], self.controls)
        self.assertEqual(context[3], self.historical_model)
        self.assertEqual(successor.paid.reservation(endpoint, 4096,
            successor.paid.number('0.1'), successor.paid.number('0.5')),
            successor.admission.RESERVE)

    def test_higher_price_and_other_endpoint_drift_rejected(self):
        changed_completion = deepcopy(self.historical_endpoint)
        changed_completion['pricing']['prompt'] = successor.NEW_PROMPT_PRICE
        changed_completion['pricing']['completion'] = '0.0000006'
        changed_cache = deepcopy(self.historical_endpoint)
        changed_cache['pricing']['prompt'] = successor.NEW_PROMPT_PRICE
        changed_cache['pricing']['input_cache_read'] = '0.00000002'
        for catalog, endpoints, _ in (
            self.catalogs(prompt='0.00000011'),
            self.catalogs(context_length=self.historical_endpoint['context_length'] - 1),
            self.catalogs(max_prompt_tokens=1),
            self.catalogs(max_completion_tokens=1),
            self.catalogs(provider_name='DifferentProvider'),
            self.catalogs(pricing=changed_completion['pricing']),
            self.catalogs(pricing=changed_cache['pricing']),
        ):
            with self.subTest(endpoint=endpoints['data']['endpoints'][0]):
                with self.assertRaises(ValueError):
                    successor.checked_live_context(self.manifest, self.phase,
                        'development', catalog, endpoints)

    def test_observational_endpoint_fields_may_change(self):
        catalog, endpoints, endpoint = self.catalogs(
            uptime_last_5m=0.5, native_tools=True, supports_image_reference=False)
        self.assertEqual(successor.checked_live_context(self.manifest, self.phase,
            'development', catalog, endpoints)[2], endpoint)

    def test_changed_request_rejected(self):
        altered = deepcopy(self.manifest)
        altered['requests_by_condition'][self.phase['condition']][0]['request_sha256'] = '0' * 64
        catalog, endpoints, _ = self.catalogs()
        with self.assertRaisesRegex(ValueError, 'frozen request'):
            successor.checked_live_context(altered, self.phase,
                'development', catalog, endpoints)

    def test_claimed_smoke_and_old_phase_are_outside_successor(self):
        for index, stage in ((0, 'development'), (1, 'smoke')):
            with self.assertRaises(ValueError):
                successor.stage_path(index, stage, 'root-review.json')

    def test_supplemental_review_binds_both_controllers_and_old_review(self):
        with tempfile.TemporaryDirectory(dir=successor.ROOT) as temp:
            base = Path(temp)
            old_review = base / 'phase-02-development.root-review.json'
            old_review.write_text('{}\n')
            (base / 'budget.json').write_text('{}\n')
            audit = base / 'lower-price-endpoint-audit-v1.json'
            audit.write_text(json.dumps({
                'schema': successor.AUDIT_SCHEMA,
                'manifest_sha256': successor.MANIFEST_SHA,
                'model_id': successor.admission.MODEL,
                'provider_tag': successor.admission.PROVIDER,
                'frozen_prompt_price_usd_per_token': successor.OLD_PROMPT_PRICE,
                'admitted_prompt_price_usd_per_token': successor.NEW_PROMPT_PRICE,
                'selected_endpoint': {
                    'tag': successor.admission.PROVIDER,
                    'model_id': successor.admission.MODEL,
                    'status': 0,
                    'pricing': {'prompt': successor.NEW_PROMPT_PRICE},
                },
            }) + '\n')
            supplement = base / 'phase-02-development.price-amendment.root-review.json'
            with patch.object(successor, 'BASE', base), patch.object(successor, 'ROUTE_AUDIT', audit):
                expected = {
                    'schema': successor.SCHEMA, 'approved': True,
                    'manifest_sha256': successor.MANIFEST_SHA,
                    'budget_manifest_sha256': successor.original.sha(base / 'budget.json'),
                    'original_review_sha256': successor.original.sha(old_review),
                    'original_controller_sha256': successor.original.sha(successor.original.__file__),
                    'successor_controller_sha256': successor.original.sha(successor.__file__),
                    'successor_tests_sha256': successor.original.sha(Path(__file__)),
                    'route_audit_sha256': successor.original.sha(audit),
                    'partition_id': successor.PARTITION_ID, 'phase_index': 1,
                    'stage': 'development',
                    'frozen_prompt_price_usd_per_token': successor.OLD_PROMPT_PRICE,
                    'admitted_prompt_price_usd_per_token': successor.NEW_PROMPT_PRICE,
                    'per_request_reserve_usd': str(successor.admission.RESERVE),
                }
                supplement.write_text(json.dumps(expected) + '\n')
                self.assertEqual(successor.verify_amendment(1, 'development',
                    successor.MANIFEST_SHA, old_review, supplement), expected)
                expected['successor_controller_sha256'] = '0' * 64
                supplement.write_text(json.dumps(expected) + '\n')
                with self.assertRaisesRegex(ValueError, 'supplemental root review'):
                    successor.verify_amendment(1, 'development', successor.MANIFEST_SHA,
                        old_review, supplement)

    def test_dedicated_process_override_is_scoped_to_old_execute(self):
        catalog, endpoints, endpoint = self.catalogs()
        original_source_state = successor.admission.source_state
        seen = []
        def fake_execute(*args):
            seen.append(successor.admission.source_state()[2])
            return {'completed': True}
        with patch.object(successor.original, 'prepare', return_value=(self.manifest, self.phase, {})), \
             patch.object(successor, 'verify_amendment'), \
             patch.object(successor.paid, 'fetch', side_effect=(catalog, endpoints)), \
             patch.object(successor.original, 'verify_sources'), \
             patch.object(successor.original, 'execute', side_effect=fake_execute) as execute, \
             patch.object(successor.paid, 'load_key') as key:
            result = successor.run(1, 'development',
                successor.BASE / 'phase-02-development.price-amendment.root-review.json')
            self.assertEqual(result, {'completed': True})
            execute.assert_called_once()
            key.assert_not_called()
        self.assertEqual(seen, [endpoint])
        self.assertIs(successor.admission.source_state, original_source_state)

    def test_failed_live_check_never_enters_old_execute(self):
        catalog, endpoints, _ = self.catalogs(prompt='0.00000011')
        with patch.object(successor.original, 'prepare', return_value=(self.manifest, self.phase, {})), \
             patch.object(successor, 'verify_amendment'), \
             patch.object(successor.paid, 'fetch', side_effect=(catalog, endpoints)), \
             patch.object(successor.original, 'execute') as execute, \
             patch.object(successor.paid, 'load_key') as key:
            with self.assertRaises(ValueError):
                successor.run(1, 'development',
                    successor.BASE / 'phase-02-development.price-amendment.root-review.json')
            execute.assert_not_called()
            key.assert_not_called()

    def test_real_old_request_loop_claims_and_uses_child_ledger(self):
        """Only transport/catalog/key are fake; execute and ledger are real."""
        catalog, endpoints, endpoint = self.catalogs()
        with tempfile.TemporaryDirectory(dir=successor.ROOT) as temp:
            folder = Path(temp)
            master = folder / 'master.jsonl'
            budget = folder / 'budget.jsonl'
            successor.original.partitions.allocate(master, budget, [{
                'id': successor.PARTITION_ID, 'cap_usd': '0.25',
                'model': successor.admission.MODEL,
                'provider': successor.admission.PROVIDER, 'reasoning': 'low',
            }])
            p = successor.original.paths(folder, 1, 'development')
            body = {
                'model': successor.admission.MODEL,
                'provider': endpoint['provider_name'],
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
                'usage': {'cost': '0.0001'},
            }
            calls = []
            def fake_fetch(path, *args, **kwargs):
                calls.append(path)
                if path == '/models':
                    return catalog
                if path.endswith('/endpoints'):
                    return endpoints
                self.assertEqual(path, '/chat/completions')
                if calls.count('/chat/completions') == 1:
                    return body
                raise RuntimeError('fake transport interruption')
            real_open_partition = successor.original.partitions.open_partition
            def open_temp_partition(_master, _budget, partition_id, model, provider, reasoning):
                return real_open_partition(master, budget, partition_id, model, provider, reasoning)
            with patch.object(successor.original, 'prepare', return_value=(self.manifest, self.phase, p)), \
                 patch.object(successor, 'verify_amendment'), \
                 patch.object(successor.admission, 'MASTER', master), \
                 patch.object(successor.original.partitions, 'open_partition', side_effect=open_temp_partition), \
                 patch.object(successor.paid, 'fetch', side_effect=fake_fetch), \
                 patch.object(successor.paid, 'load_key', return_value='fake-test-key') as key, \
                 patch.object(successor.original, 'verify_sources'):
                result = successor.run(1, 'development',
                    successor.BASE / 'phase-02-development.price-amendment.root-review.json')
            self.assertEqual(result['status'], 'service_error')
            key.assert_called_once()
            self.assertEqual(calls.count('/models'), 2)
            self.assertEqual(calls.count('/chat/completions'), 2)
            self.assertTrue(all(x.exists() for x in p.values()))
            records = successor.original.jsonl(p['records'])
            self.assertEqual([x['status'] for x in records], ['invalid_output', 'service_error'])
            self.assertEqual(records[0]['provider_endpoint']['pricing']['prompt'],
                             successor.NEW_PROMPT_PRICE)
            self.assertEqual(records[0]['request_sha256'],
                             self.manifest['requests_by_condition'][self.phase['condition']][0]['request_sha256'])
            self.assertEqual(records[0]['observed_cost_usd'], '0.0001')
            self.assertIsNone(records[1]['observed_cost_usd'])
            self.assertTrue(records[1]['cost_unknown'])
            child = folder / ('budget-' + successor.PARTITION_ID + '.jsonl')
            events = successor.original.jsonl(child)
            self.assertEqual([x['event'] for x in events],
                             ['budget', 'reserve', 'settle', 'reserve'])
            self.assertEqual(Decimal(events[1]['usd']), successor.admission.RESERVE)
            self.assertEqual(Decimal(events[2]['usd']), Decimal('0.0001'))


if __name__ == '__main__':
    unittest.main()
