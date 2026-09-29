"""Offline source-reconstruction checks for DeepSeek high matched three."""
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_high_fresh_repeat_study as study


class DeepSeekHighFreshTests(unittest.TestCase):
    def test_full_historical_control_and_request_reconstruction(self):
        plans = [study.plan_data(name) for name in study.ORDERS]
        self.assertEqual([p['condition_order'] for p in plans],
                         [list(order) for order in study.ORDERS.values()])
        for plan in plans:
            self.assertEqual(plan['execution_status'], 'offline_prepared_no_inference_no_allocation')
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(plan['historical_development_statuses'], study.EXPECTED_STATUSES)
            self.assertEqual(plan['historical_endpoint_prompt_price_usd_per_token'], '0.0000001')
            self.assertEqual(plan['current_saved_route_prompt_price_usd_per_token'], '0.00000003')
            for condition in study.CONDITIONS:
                branch = plan['conditions'][condition]
                self.assertEqual(len(branch['smoke']), 3)
                self.assertEqual(len(branch['development']), 60)
                self.assertEqual(branch['smoke'], branch['development'][:3])
                self.assertEqual([x['record_id'] for x in branch['development']],
                                 [f'DEV-{i:03d}' for i in range(1, 61)])
                for item in branch['development']:
                    self.assertEqual(set(json.loads(item['payload']['messages'][1]['content'])),
                                     {'feedback'})
                    self.assertNotIn('prediction', item)
                    self.assertNotIn('raw_response', item)
                    self.assertEqual(item['payload']['reasoning'],
                                     {'enabled': True, 'effort': 'high'})
                    self.assertEqual(item['payload']['provider']['max_price']['prompt'], 0.1)
        for condition in study.CONDITIONS:
            first = plans[0]['conditions'][condition]['development']
            self.assertTrue(all(plan['conditions'][condition]['development'] == first
                                for plan in plans[1:]))
        self.assertEqual([sum(not row['saved_request_hash_present'] for row in
                              plans[0]['conditions'][condition]['development'])
                          for condition in study.CONDITIONS], [0, 54, 59])

    def test_known_cost_and_unknown_bound_are_separate(self):
        estimate = study.estimate(study.sources()[0])
        self.assertEqual(estimate['historical_attempt_rows_in_proxy'], 189)
        self.assertEqual(Decimal(estimate['historical_one_pass_known_cost_usd']),
                         Decimal('0.04874595'))
        self.assertEqual(Decimal(estimate['historical_one_pass_unknown_reserve_bound_usd']),
                         Decimal('0.2138112'))
        self.assertEqual(Decimal(estimate['three_pass_known_plus_unknown_sensitivity_usd']),
                         Decimal('0.78767145'))
        self.assertEqual(Decimal(estimate['proposed_child_budget_usd']), Decimal('0.90'))
        self.assertEqual(Decimal(estimate['per_request_maximum_reserve_usd']),
                         Decimal('0.1069056'))

    def test_tampered_saved_request_or_price_fails_closed(self):
        audit, _, controls = study.sources()
        inputs = study.input_rows()
        original = study.historical_rows
        for change in ('request', 'price', 'reference'):
            def altered(audit_arg, condition):
                rows = original(audit_arg, condition)
                row = dict(rows['DEV-001'])
                if change == 'request':
                    row['request'] = dict(row['request'], temperature=0.1)
                elif change == 'price':
                    endpoint = dict(row['provider_endpoint'])
                    endpoint['pricing'] = dict(endpoint['pricing'], completion='0.0000006')
                    row['provider_endpoint'] = endpoint
                else:
                    row['reference_labels_read'] = True
                rows['DEV-001'] = row
                return rows
            with self.subTest(change=change), patch.object(study, 'historical_rows', side_effect=altered):
                with self.assertRaises(ValueError):
                    study.condition_data(audit, controls, inputs, 'P0')

    def test_smoke_request_drift_fails_closed(self):
        audit, _, controls = study.sources()
        inputs = study.input_rows()
        conditions = {name: study.condition_data(audit, controls, inputs, name)
                      for name in study.CONDITIONS}
        original = study.rows
        def changed(relative):
            observed = original(relative)
            if relative == study.SMOKES['P1']:
                observed[0] = dict(observed[0], request=dict(observed[0]['request'], temperature=1))
            return observed
        with patch.object(study, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Historical smoke request'):
                study.estimate(audit, conditions)

    def test_verify_rejects_wrong_manifest_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'fresh1' / 'manifest.json'
            target.parent.mkdir()
            target.write_text('{}\n')
            with patch.object(study, 'BASE', Path(temp)):
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                    study.verify('fresh1', '0' * 64)


if __name__ == '__main__':
    unittest.main()
