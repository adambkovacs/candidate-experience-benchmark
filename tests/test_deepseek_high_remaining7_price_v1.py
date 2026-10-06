"""Offline checks for the distinct remaining-seven high-price proposal."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_high_remaining7_price_v1 as proposal


class RemainingHighTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior = json.loads(proposal.prior.ROUTE.read_text())
        cls.model = prior['model']
        cls.endpoint = prior['selected_endpoint']

    def route(self):
        endpoint = deepcopy(self.endpoint)
        endpoint['pricing']['prompt'] = '0.000000055'
        return {'schema': proposal.SCHEMA + '-public-route',
                'inference_sent': False, 'model': deepcopy(self.model),
                'selected_endpoint': endpoint}

    def capacity(self):
        return {'master_cap_usd': '22.38', 'master_available_usd': '1.00',
                'master_pending_count': 0, 'master_blocked': False,
                'master_closed': False, 'amendment_complete': True,
                'openrouter_additional_available_usd': '1.00',
                'observation_only': True}

    def test_new_ceiling_and_reserve_admit_current_price(self):
        live = self.route()['selected_endpoint']
        self.assertEqual(proposal.check_route(self.model, live,
                         self.model, self.endpoint), Decimal('0.06905856'))
        self.assertEqual(proposal.check_route(self.model, self.endpoint,
                         self.model, self.endpoint), Decimal('0.06905856'))

    def test_price_boundary_identity_and_reasoning_refusals(self):
        cases = [('prompt', '0.000000060001'),
                 ('completion', '0.000001500001'),
                 ('input_cache_read', '0.000000060001'),
                 ('prompt', '-0.000000001'),
                 ('discount', 1)]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                live = self.route()['selected_endpoint']
                live['pricing'][key] = value
                with self.assertRaises(ValueError):
                    proposal.check_route(self.model, live, self.model, self.endpoint)
        live = self.route()['selected_endpoint']
        live['provider_name'] = 'Other'
        with self.assertRaises(ValueError):
            proposal.check_route(self.model, live, self.model, self.endpoint)
        changed = deepcopy(self.model)
        changed['reasoning'] = False
        with self.assertRaises(ValueError):
            proposal.check_route(changed, self.route()['selected_endpoint'],
                                 self.model, self.endpoint)

    def test_seven_phase_plan_amends_only_max_price(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(proposal, 'ROUTE', Path(tmp) / 'route.json'):
            proposal.ROUTE.write_text(json.dumps(self.route()))
            plan = proposal.execution_plan(self.route(), self.capacity())
        self.assertEqual([(p['repeat'], p['condition']) for p in plan['phase_order']],
                         list(proposal.PHASES))
        self.assertEqual(plan['request_count'], 441)
        self.assertEqual(len(plan['requests_by_stage']), 14)
        self.assertEqual(plan['per_request_reserve_usd'], '0.06905856')
        self.assertEqual(plan['proposed_child_cap_usd'], '1.00')
        self.assertFalse(plan['inference_authorized'])
        self.assertFalse(plan['allocation_authorized'])
        self.assertFalse(plan['execution_adapter_admitted'])
        first = plan['requests_by_stage']['fresh1/P2/smoke'][0]
        self.assertNotEqual(first['request_sha256'], first['original_request_sha256'])
        self.assertEqual(first['payload']['provider']['max_price'],
                         {'prompt': 0.06, 'completion': 1.5, 'request': 0, 'image': 0})
        self.assertEqual(first['payload']['reasoning'],
                         {'enabled': True, 'effort': 'high'})

    def test_child_capacity_below_one_dollar_refused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(proposal, 'ROUTE', Path(tmp) / 'route.json'):
            proposal.ROUTE.write_text(json.dumps(self.route()))
            cap = self.capacity()
            cap['openrouter_additional_available_usd'] = '0.99'
            with self.assertRaisesRegex(ValueError, 'capacity'):
                proposal.execution_plan(self.route(), cap)


if __name__ == '__main__': unittest.main()
