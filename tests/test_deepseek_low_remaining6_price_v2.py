"""Offline checks for the separately versioned low remaining-six successor."""
from copy import deepcopy
from decimal import Decimal
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_low_remaining6_price_v2 as proposal


class RemainingLowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior = json.loads((ROOT / 'results/repeatability-v1/deepseek-high-authority-v3/public-route.json').read_text())
        cls.model = prior['model']
        cls.endpoint = prior['selected_endpoint']
        cls.endpoint['pricing']['prompt'] = '0.000000055'
        cls.endpoint['pricing']['completion'] = '0.00000132'
        cls.endpoint['pricing']['input_cache_read'] = '0.0000000165'

    def route(self):
        return {'schema': proposal.SCHEMA + '-public-route', 'inference_sent': False,
                'model': deepcopy(self.model), 'endpoint': deepcopy(self.endpoint)}

    def capacity(self):
        return {'master_cap_usd': '22.38', 'master_available_usd': '1.00',
                'master_pending_count': 0, 'master_blocked': False, 'master_closed': False,
                'openrouter_additional_available_usd': '0.75',
                'amendment_complete': True, 'observation_only': True}

    def test_current_route_and_price_decreases_preserve_reserve(self):
        model, endpoint = deepcopy(self.model), deepcopy(self.endpoint)
        self.assertEqual(proposal.check_route(model, endpoint, model, endpoint),
                         Decimal('0.06905856'))
        saved = deepcopy(endpoint)
        endpoint['pricing']['prompt'] = '0.0000000500'
        self.assertEqual(proposal.check_route(model, endpoint, model, saved),
                         Decimal('0.06905856'))

    def test_price_increase_identity_and_negative_rejected(self):
        for key, value in (('prompt', '0.000000060001'),
                           ('completion', '0.000001500001'),
                           ('input_cache_read', '0.000000060001'),
                           ('input_cache_read', '-0.000000001')):
            with self.subTest(key=key):
                changed = deepcopy(self.endpoint)
                changed['pricing'][key] = value
                with self.assertRaises(ValueError):
                    proposal.check_route(self.model, changed, self.model, self.endpoint)
        changed = deepcopy(self.endpoint)
        changed['quantization'] = 'fp16'
        with self.assertRaises(ValueError):
            proposal.check_route(self.model, changed, self.model, self.endpoint)

    def test_six_phase_plan_uses_separate_request_ceiling_and_conditional_child(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(proposal, 'ROUTE', Path(tmp) / 'route.json'):
            proposal.ROUTE.write_text(json.dumps(self.route()))
            plan = proposal.execution_plan(self.route(), self.capacity(), 'test-route-sha')
        self.assertEqual([(p['repeat'], p['condition']) for p in plan['phase_order']],
                         list(proposal.PHASES))
        self.assertEqual([p['phase_index'] for p in plan['phase_order']], list(range(3, 9)))
        self.assertEqual(plan['request_count'], 378)
        self.assertEqual(plan['per_request_reserve_usd'], '0.06905856')
        self.assertEqual(plan['proposed_child_cap_usd'], '0.75')
        self.assertFalse(plan['full_series_completion_guaranteed'])
        self.assertFalse(plan['allocation_authorized'])
        self.assertFalse(plan['inference_authorized'])
        self.assertFalse(plan['execution_adapter_admitted'])
        first = plan['requests_by_condition']['P2'][0]
        self.assertNotEqual(first['request_sha256'], first['original_request_sha256'])
        self.assertEqual(first['payload']['provider']['max_price']['prompt'], 0.06)
        self.assertEqual(first['payload']['provider']['max_price']['completion'], 1.5)
        self.assertEqual(first['payload']['provider']['only'], [proposal.old.PROVIDER])
        self.assertEqual(first['payload']['reasoning'], {'enabled': True, 'effort': 'low'})

    def test_below_child_capacity_refused(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(proposal, 'ROUTE', Path(tmp) / 'route.json'):
            proposal.ROUTE.write_text(json.dumps(self.route()))
            capacity = self.capacity()
            capacity['openrouter_additional_available_usd'] = '0.74'
            with self.assertRaisesRegex(ValueError, 'capacity'):
                proposal.execution_plan(self.route(), capacity, 'test-route-sha')

    def test_atomic_prepare_prevalidates_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'successor'
            with patch.object(proposal, 'BASE', base), \
                 patch.object(proposal, 'ROUTE', base / 'public-route.json'), \
                 patch.object(proposal, 'MANIFEST', base / 'execution-manifest.json'), \
                 patch.object(proposal, 'CANDIDATE', base / 'design.root-review-candidate.json'), \
                 patch.object(proposal, 'LOCK', Path(tmp) / '.prepare.lock'), \
                 patch.object(proposal, 'public_route', return_value=self.route()), \
                 patch.object(proposal, 'capacity_observation', return_value=self.capacity()):
                with patch.object(proposal, 'execution_plan', side_effect=ValueError('prevalidation')):
                    with self.assertRaisesRegex(ValueError, 'prevalidation'):
                        proposal.prepare()
                self.assertFalse(base.exists())
                digest = proposal.prepare()
                self.assertEqual(digest, proposal.verify())
                before = proposal.MANIFEST.read_bytes()
                with self.assertRaises(FileExistsError):
                    proposal.prepare()
                self.assertEqual(proposal.MANIFEST.read_bytes(), before)

    def test_remaining_phase_claim_any_subtree_blocks_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / 'manifest.json').write_bytes((proposal.ORIGINAL / 'manifest.json').read_bytes())
            nested = base / 'interruption-continuation-v1'
            nested.mkdir()
            (nested / 'phase-04-smoke.claim.json').write_text('{}\n')
            with patch.object(proposal, 'ORIGINAL', base):
                with self.assertRaisesRegex(ValueError, 'already has evidence'):
                    proposal.sealed_sources()


if __name__ == '__main__':
    unittest.main()
