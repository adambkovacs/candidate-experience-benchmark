"""Offline Qwen 3.6 reasoning-on admission proof."""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen36_on_fresh_repeat_study as study


class Qwen36OnFreshRepeatStudyTests(unittest.TestCase):
    def test_three_rotations_reconstruct_60_input_only_requests(self):
        plans = [study.plan_data(name) for name in study.ORDERS]
        self.assertEqual([p['condition_order'] for p in plans], list(study.ORDERS.values()))
        for plan in plans:
            self.assertEqual(plan['execution_status'], 'offline_prepared_no_inference_no_allocation')
            self.assertEqual(plan['historical_p2_outcomes_preserved'], {'ok': 54, 'service_error': 6})
            self.assertFalse(plan['reference_labels_read'])
            for condition in study.CONDITIONS:
                phase = plan['conditions'][condition]
                self.assertEqual(len(phase['smoke']), 3)
                self.assertEqual(len(phase['development']), 60)
                self.assertEqual(phase['smoke'], phase['development'][:3])
                self.assertEqual([r['record_id'] for r in phase['development']],
                                 [f'DEV-{i:03}' for i in range(1, 61)])
                for request in phase['development']:
                    self.assertEqual(set(json.loads(request['payload']['messages'][1]['content'])), {'feedback'})
                    self.assertNotIn('raw_response', request)
                    self.assertNotIn('prediction', request)
        for condition in study.CONDITIONS:
            initial = plans[0]['conditions'][condition]['development']
            self.assertTrue(all(p['conditions'][condition]['development'] == initial for p in plans[1:]))
        failed = [r['record_id'] for r in plans[0]['conditions']['P2']['development']
                  if r['historical_outcome_excluded'] == 'service_error']
        self.assertEqual(failed, ['DEV-033', 'DEV-039', 'DEV-040', 'DEV-041', 'DEV-042', 'DEV-043'])

    def test_known_cost_unknown_bounds_and_reservations_stay_distinct(self):
        estimate = study.estimate()
        self.assertEqual(estimate['historical_attempt_rows_in_proxy'], 190)
        self.assertEqual(Decimal(estimate['historical_one_pass_known_charges_usd']), Decimal('0.2043159'))
        self.assertEqual(Decimal(estimate['historical_one_pass_unknown_charge_bounds_usd']), Decimal('0.2093056'))
        self.assertEqual(Decimal(estimate['three_pass_known_charge_proxy_usd']), Decimal('0.6129477'))
        self.assertEqual(Decimal(estimate['three_pass_unknown_bound_sensitivity_usd']), Decimal('0.6279168'))
        self.assertEqual(Decimal(estimate['three_pass_known_plus_unknown_sensitivity_usd']), Decimal('1.2408645'))
        self.assertEqual(Decimal(estimate['maximum_per_request_reserve_usd']), Decimal('0.0299008'))
        self.assertEqual(estimate['calls_per_full_series'], 567)
        self.assertEqual(Decimal(estimate['all_calls_at_maximum_reserve_usd']), Decimal('16.9537536'))

    def test_historical_missing_request_fails_closed(self):
        original = study.source_rows

        def altered(condition):
            rows = original(condition)
            rows['DEV-001'] = dict(rows['DEV-001'], request=None)
            return rows

        with patch.object(study, 'source_rows', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'request body missing'):
                study.build_condition('P0', study.input_rows())

    def test_manifest_hash_check_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'fresh1' / 'manifest.json'
            target.parent.mkdir()
            target.write_text('{}\n')
            with patch.object(study, 'BASE', Path(temporary)):
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                    study.verify('fresh1', '0' * 64)


if __name__ == '__main__':
    unittest.main()
