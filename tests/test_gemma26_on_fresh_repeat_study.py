"""Offline Gemma 26 on fresh-three plan reconstruction and cost checks."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_on_fresh_repeat_study as study


class Gemma26OnFreshRepeatStudyTests(unittest.TestCase):
    def test_three_passes_bind_same_complete_request_roster_and_rotation(self):
        plans = [study.plan_data(name) for name in study.ORDERS]
        self.assertEqual([p['condition_order'] for p in plans], list(study.ORDERS.values()))
        self.assertEqual({p['series_id'] for p in plans}, {study.SERIES})
        self.assertEqual({p['configuration_id'] for p in plans}, {study.CONFIG})
        for plan in plans:
            self.assertEqual(plan['execution_status'], 'offline_prepared_no_inference_no_allocation')
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(plan['development_count_per_condition'], 60)
            self.assertEqual(plan['smoke_count_per_condition'], 3)
            for condition in study.CONDITIONS:
                source = plan['conditions'][condition]
                self.assertEqual(len(source['development']), 60)
                self.assertEqual(len(source['smoke']), 3)
                self.assertEqual([r['record_id'] for r in source['development']],
                                 [r['record_id'] for r in source['smoke']] +
                                 [r['record_id'] for r in source['development'][3:]])
                for request in source['development']:
                    user_content = request['payload']['messages'][1]['content']
                    self.assertEqual(set(__import__('json').loads(user_content)), {'feedback'})

    def test_historical_charge_and_reservation_estimates(self):
        estimate = study.estimate(study.historical_data()[0])
        self.assertEqual(Decimal(estimate['historical_one_pass_known_development_and_smoke_usd']),
                         Decimal('0.06608528'))
        self.assertEqual(Decimal(estimate['historical_one_pass_unknown_charge_bounds_usd']),
                         Decimal('0.03948544'))
        self.assertEqual(Decimal(estimate['three_pass_known_charge_proxy_usd']),
                         Decimal('0.19825584'))
        self.assertEqual(Decimal(estimate['three_pass_known_plus_historical_unknown_sensitivity_usd']),
                         Decimal('0.31671216'))
        self.assertEqual(Decimal(estimate['maximum_per_request_reserve_usd']),
                         Decimal('0.01974272'))
        self.assertEqual(estimate['calls_per_full_series'], 567)
        self.assertEqual(Decimal(estimate['all_calls_reserved_at_maximum_usd']),
                         Decimal('11.19412224'))
        self.assertEqual(Decimal(estimate['proposed_child_cap_usd']), Decimal('0.40'))


if __name__ == '__main__':
    unittest.main()
