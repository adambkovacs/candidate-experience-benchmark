"""Offline tests for the exact second DeepSeek low price exception."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import deepseek_low_price_successor_v2 as successor
import deepseek_low_second_interruption as run


class SecondPriceSuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = run.original_manifest()
        cls.phase = cls.manifest['phases'][2]
        cls.history, cls.controls, cls.old_endpoint, cls.old_model = (
            successor.admission.source_state())

    def catalogs(self, **changes):
        endpoint = deepcopy(self.old_endpoint)
        endpoint['pricing'].update(successor.PRICES)
        endpoint.update(changes)
        return ({'data': [deepcopy(self.old_model)]},
                {'data': {'id': successor.admission.MODEL,
                          'endpoints': [endpoint]}}, endpoint)

    def test_public_audit_binds_original_raw_responses_and_exact_rates(self):
        self.assertEqual(successor.verify_route_audit(), successor.sha(successor.ROUTE_AUDIT))
        audit = json.loads(successor.ROUTE_AUDIT.read_text())
        self.assertEqual(audit['admitted_prices_usd_per_token'], successor.PRICES)
        self.assertEqual(audit['selected_endpoint']['pricing'],
                         successor.expected_pricing(self.old_endpoint))
        for source in audit['sources']:
            self.assertEqual(successor.sha(ROOT / source['file']), source['sha256'])

    def test_changed_public_source_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            changed = Path(temp) / 'endpoints.json'
            changed.write_text('{}\n')
            with patch.object(successor, 'RAW_ENDPOINTS', changed):
                with self.assertRaisesRegex(ValueError, 'public route source changed'):
                    successor.verify_route_audit()

    def test_three_exact_lower_prices_preserve_frozen_requests_and_reserve(self):
        catalog, endpoints, endpoint = self.catalogs()
        context = successor.checked_live_context(self.manifest, self.phase,
                                                  'development', catalog, endpoints)
        self.assertEqual(context, (self.history, self.controls, endpoint, self.old_model))
        self.assertEqual(successor.paid.reservation(endpoint, 4096,
            successor.paid.number('0.1'), successor.paid.number('0.5')),
            successor.admission.RESERVE)
        rebuilt = run._rebuild_requests(self.manifest, 2, 'suffix', endpoint, self.old_model)
        self.assertEqual([item['id'] for _, item, _ in rebuilt], run.IDS[49:])
        self.assertEqual([item['request_sha256'] for _, item, _ in rebuilt],
                         [item['request_sha256'] for item in
                          run.selected_items(self.manifest, 2, 'suffix')])

    def test_any_price_or_identity_drift_is_rejected(self):
        cases = []
        for key in successor.PRICES:
            catalog, endpoints, endpoint = self.catalogs()
            endpoint['pricing'][key] = str(successor.paid.number(endpoint['pricing'][key])
                                           + successor.paid.number('0.000000000001'))
            cases.append((catalog, endpoints))
        cases.append(self.catalogs(context_length=self.old_endpoint['context_length'] - 1)[:2])
        cases.append(self.catalogs(provider_name='DifferentProvider')[:2])
        cases.append(self.catalogs(supported_parameters=['structured_outputs',
                                                          'max_tokens', 'temperature'])[:2])
        for catalog, endpoints in cases:
            with self.subTest(endpoint=endpoints['data']['endpoints'][0]):
                with self.assertRaises(ValueError):
                    successor.checked_live_context(self.manifest, self.phase,
                                                   'development', catalog, endpoints)

    def test_frozen_request_mutation_is_rejected(self):
        altered = deepcopy(self.manifest)
        altered['requests_by_condition'][self.phase['condition']][0]['request_sha256'] = '0' * 64
        catalog, endpoints, _ = self.catalogs()
        with self.assertRaisesRegex(ValueError, 'frozen request'):
            successor.checked_live_context(altered, self.phase,
                                           'development', catalog, endpoints)

    def test_route_drift_fails_before_key_child_lock_or_claim(self):
        catalog, endpoints, endpoint = self.catalogs()
        endpoint['pricing']['completion'] = '0.000000397'
        with patch.object(run, 'prepare', return_value=(self.manifest, {})), \
             patch.object(run.original, 'verify_sources'), \
             patch.object(run.paid, 'fetch', side_effect=(catalog, endpoints)), \
             patch.object(run.partitions, 'open_partition') as child, \
             patch.object(run.paid, 'load_key') as key, \
             patch.object(run.original, 'atomic_json') as claim:
            with self.assertRaisesRegex(ValueError, 'prices differ'):
                run.execute('manifest', 'sha', 'budget', 2, 'suffix', 'review')
            child.assert_not_called()
            key.assert_not_called()
            claim.assert_not_called()


if __name__ == '__main__':
    unittest.main()
