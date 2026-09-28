import copy
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import typesafe_repeat_study as study
import jev_native_prompt_variants_v1 as native


class TypeSafeRepeatAdmissionTests(unittest.TestCase):
    def test_current_first_attempt_selection_and_budget(self):
        result = study.plan()
        self.assertFalse(result['dispatch_authorized'])
        self.assertEqual(result['historical_selection']['P0']['status_counts'],
                         {'ok': 59, 'service_error': 1})
        self.assertEqual(result['historical_selection']['P0']['failed_id'], 'DEV-046')
        self.assertTrue(result['historical_selection']['P0']['retry_excluded_from_first_pass'])
        self.assertEqual(result['historical_selection']['P1']['status_counts'],
                         {'ok': 59, 'invalid_output': 1})
        self.assertEqual(result['historical_selection']['P2']['status_counts'],
                         {'ok': 59, 'invalid_output': 1})
        self.assertEqual([x['condition_order'] for x in result['future_passes']],
                         [['P1', 'P2', 'P0'], ['P2', 'P0', 'P1']])
        self.assertEqual(result['upper_bounds_usd']['two_more_passes'], '0.867255984')
        expected = Decimal(result['budget_snapshot']['accounted_usd']) + Decimal('0.867255984')
        self.assertEqual(Decimal(result['upper_bounds_usd']['accounted_plus_two']), expected)
        self.assertEqual(Decimal(result['upper_bounds_usd']['headroom_after_two']), Decimal('1') - expected)
        self.assertFalse(result['upper_bounds_usd']['fresh_three_fits'])
        self.assertEqual(result['budget_snapshot']['pending_upper_usd'], '0.002123688')
        self.assertFalse(any('proposed_labels' in x['path'] for x in result['source_bindings']))
        for repeat in result['future_passes']:
            for phase in repeat['conditions'].values():
                self.assertEqual(phase['smoke_ids'], study.SMOKE_IDS)
                self.assertEqual(phase['development_ids'], study.IDS)
                self.assertEqual(len(phase['requests']), 60)

    def test_duplicate_dev046_cannot_be_folded_into_first_attempt(self):
        manifest, _ = native.read_frozen_manifest(study.BASE / 'input-only-manifest.json')
        first, all_attempts = study.historical_p0(manifest)
        self.assertEqual(first[45]['status'], 'service_error')
        self.assertEqual(all_attempts[46]['status'], 'ok')
        self.assertNotEqual(first[45]['budget_attempt_id'], all_attempts[46]['budget_attempt_id'])
        original = study.lines
        def changed(path):
            rows = original(path)
            if Path(path) == study.P0_CONTINUATION:
                rows = copy.deepcopy(rows)
                rows[0]['id'] = 'DEV-047'
            return rows
        with mock.patch.object(study, 'lines', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'exact 46-attempt prefix'):
                study.historical_p0(manifest)

    def test_original_failed_attempt_must_remain_failed(self):
        manifest, _ = native.read_frozen_manifest(study.BASE / 'input-only-manifest.json')
        original = study.lines
        def changed(path):
            rows = original(path)
            if Path(path) == study.P0_PREFIX:
                rows = copy.deepcopy(rows)
                rows[-1]['status'] = 'ok'
            return rows
        with mock.patch.object(study, 'lines', side_effect=changed):
            with self.assertRaises(ValueError):
                study.historical_p0(manifest)

    def test_ledger_settlement_conflict_rejected(self):
        original = study.lines
        def changed(path):
            rows = original(path)
            if Path(path) == native.LEDGER:
                rows = copy.deepcopy(rows)
                next(x for x in rows if x['event'] == 'settle')['usd'] = '0.90'
            return rows
        with mock.patch.object(study, 'lines', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'settlement differs|cap already exceeded'):
                study.plan()

    def test_new_series_cannot_fit_existing_cap(self):
        actual = study.plan()
        self.assertGreater(Decimal(actual['upper_bounds_usd']['fresh_three_passes']), Decimal('1'))
        altered = copy.deepcopy(actual['budget_snapshot'])
        altered['accounted_usd'] = '0.20'
        with mock.patch.object(study, 'ledger_snapshot', return_value=altered):
            with self.assertRaisesRegex(ValueError, 'exceeds existing'):
                study.plan()


if __name__ == '__main__':
    unittest.main()
