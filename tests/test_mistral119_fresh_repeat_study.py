"""Offline source, input-isolation, and budget checks for Mistral119 plans."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_fresh_repeat_study as study


class Mistral119FreshStudyTests(unittest.TestCase):
    def test_both_efforts_have_three_independent_counterbalanced_input_only_passes(self):
        inputs = study.input_rows()
        ids = [row['id'] for row in inputs]
        self.assertEqual(len(ids), 60)
        for config, spec in study.CONFIGS.items():
            original, count = study.historical(config)
            self.assertEqual(count, 5 if spec['effort'] == 'none' else 3)
            for repeat, order in study.ORDERS.items():
                with self.subTest(config=config, repeat=repeat):
                    plan = study.plan_data(config, repeat)
                    self.assertEqual(plan['condition_order'], order)
                    self.assertEqual(plan['configuration_id'], config)
                    self.assertIsNone(plan['budget_estimate']['whole_series_child_cap_proposed_usd'])
                    self.assertIs(plan['reference_labels_read'], False)
                    self.assertFalse(any('reference' in entry['path'].lower()
                                         for entry in plan['source_bindings']))
                    for condition in study.CONDITIONS:
                        phase = plan['conditions'][condition]
                        self.assertEqual([r['record_id'] for r in phase['development']], ids)
                        self.assertEqual([r['record_id'] for r in phase['smoke']], ids[:3])
                        self.assertEqual(phase['smoke'], phase['development'][:3])
                        self.assertEqual(len({r['request_sha256'] for r in phase['development']}), 60)
                        for item, request in zip(inputs, phase['development']):
                            payload = request['payload']
                            self.assertEqual(set(payload), {'model', 'temperature', 'max_tokens',
                                                            'stream', 'provider', 'response_format',
                                                            'reasoning', 'messages'})
                            self.assertEqual(payload['messages'][1], {
                                'role': 'user', 'content': json.dumps({'feedback': item['feedback']})})
                            self.assertEqual(request['input_sha256'], study.digest(item['feedback']))
                            self.assertEqual(payload['reasoning'], original['request']['reasoning'])
                    self.assertEqual(plan['conditions']['P0']['development'][0]['payload'],
                                     original['request'])
                    self.assertNotEqual(plan['conditions']['P0']['development'][0]['request_sha256'],
                                        plan['conditions']['P1']['development'][0]['request_sha256'])
                    self.assertNotEqual(plan['conditions']['P1']['development'][0]['request_sha256'],
                                        plan['conditions']['P2']['development'][0]['request_sha256'])

    def test_historical_failure_route_or_request_mutation_fails_closed(self):
        config = 'openrouter-paid-mistral-small4-119b-none'
        source = study.CONFIGS[config]['historical_smokes'][0]
        real_jsonl = study.jsonl
        for mutation in ('status', 'request', 'route'):
            def changed(path):
                rows = copy.deepcopy(real_jsonl(path))
                if path == source:
                    if mutation == 'status':
                        rows[0]['status'] = 'ok'
                    elif mutation == 'request':
                        rows[0]['request']['temperature'] = 1
                    else:
                        rows[0]['provider_endpoint']['tag'] = 'mistral'
                return rows
            with self.subTest(mutation=mutation), patch.object(study, 'jsonl', side_effect=changed):
                with self.assertRaises(ValueError):
                    study.plan_data(config, 'fresh1')

    def test_later_input_drift_changes_reconstruction_even_when_dev001_matches(self):
        config = 'openrouter-paid-mistral-small4-119b-high'
        manifest = study.BASE / config / 'fresh1/manifest.json'
        inputs = study.input_rows()
        altered = copy.deepcopy(inputs)
        altered[29]['feedback'] += ' changed'
        with patch.object(study, 'input_rows', return_value=altered):
            changed = study.plan_data(config, 'fresh1')
        normal = study.plan_data(config, 'fresh1')
        self.assertEqual(changed['conditions']['P0']['development'][0]['request_sha256'],
                         normal['conditions']['P0']['development'][0]['request_sha256'])
        self.assertNotEqual(changed['conditions']['P0']['development'][29]['request_sha256'],
                            normal['conditions']['P0']['development'][29]['request_sha256'])
        with patch.object(study, 'input_rows', return_value=altered):
            with self.assertRaisesRegex(ValueError, 'source reconstruction'):
                study.verify(config, 'fresh1', study.sha(manifest))

    def test_reserve_is_not_a_cost_proxy_or_spending_authority(self):
        for config, count in [('openrouter-paid-mistral-small4-119b-none', 5),
                              ('openrouter-paid-mistral-small4-119b-high', 3)]:
            plan = study.plan_data(config, 'fresh1')
            budget = plan['budget_estimate']
            self.assertEqual(budget['historical_failed_smoke_attempts'], count)
            self.assertIsNone(budget['historical_known_cost_proxy_usd'])
            self.assertIsNone(budget['whole_series_child_cap_proposed_usd'])
            self.assertEqual(Decimal(budget['maximum_per_request_reserve_usd']), Decimal('0.04177920'))
            self.assertEqual(Decimal(budget['three_smoke_reservations_usd']), Decimal('0.12533760'))
            self.assertEqual(budget['calls_per_full_series'], 567)
            self.assertEqual(Decimal(budget['all_calls_at_maximum_reserve_usd']), Decimal('23.68880640'))
            self.assertEqual(plan['execution_status'], 'offline_prepared_no_inference_no_allocation')

    def test_six_manifests_verify_hash_and_source_bindings(self):
        for config in study.CONFIGS:
            for repeat in study.ORDERS:
                path = study.BASE / config / repeat / 'manifest.json'
                with self.subTest(config=config, repeat=repeat):
                    frozen = study.verify(config, repeat, study.sha(path))
                    names = {entry['path'] for entry in frozen['source_bindings']}
                    self.assertIn('scripts/mistral119_fresh_repeat_study.py', names)
                    self.assertIn('tests/test_mistral119_fresh_repeat_study.py', names)
                    self.assertIn('scripts/development_benchmark.py', names)
                    self.assertIn('prompts/variants-v1/manifest.json', names)
                    self.assertIn(study.INPUTS, names)
                    self.assertIn(study.ROUTE_AUDIT, names)
                    with self.assertRaisesRegex(ValueError, 'Manifest SHA-256 mismatch'):
                        study.verify(config, repeat, '0' * 64)


if __name__ == '__main__':
    unittest.main()
