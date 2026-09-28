"""Offline admission checks for the recovered Gemini 3.8 Flash low lane."""

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini38_low_repeat as repeat
import gemini_openrouter_batch_v3 as v3


CONFIG = 'gemini38-low-p0-openrouter-v2'


class Gemini38LowRepeatTests(unittest.TestCase):
    def test_two_plans_reconstruct_exact_recovered_historical_triple(self):
        for name, order in repeat.ORDERS.items():
            with self.subTest(repeat=name):
                plan = repeat.expected_plan(CONFIG, name)
                self.assertEqual(plan['condition_order'], list(order))
                self.assertEqual(plan['historical_order'], ['P0', 'P1', 'P2'])
                self.assertEqual(plan['original_p0_baseline_id'], CONFIG)
                self.assertEqual(plan['proposed_partition_cap_usd'], '0.30')
                self.assertFalse(plan['partition_allocated'])
                self.assertFalse(plan['reference_labels_read'])
                self.assertTrue(plan['no_automatic_retry'])
                self.assertNotIn('data/pilot/proposed_labels.jsonl', plan['source_bindings'])
                self.assertEqual({c: len(plan['conditions'][c]['requests'])
                                  for c in ('P0', 'P1', 'P2')},
                                 {'P0': 7, 'P1': 7, 'P2': 7})
                self.assertEqual(plan['conditions']['P0']['historical']['recovered_admission']['path'],
                                 str(repeat.P0_ADMISSION.relative_to(ROOT)))
                for condition in ('P1', 'P2'):
                    old = json.loads(repeat.bound(plan['conditions'][condition]['historical']['manifest']).read_text())
                    self.assertEqual(old['parent_p0']['baseline_id'], CONFIG)
                    self.assertEqual(old['parent_p0']['admission_proof'],
                                     plan['conditions']['P0']['historical']['recovered_admission'])

    def test_v2_p0_payload_matches_v3_and_reserved_bound_is_explicit(self):
        plan = repeat.expected_plan(CONFIG, 'repeat2')
        original = json.loads(repeat.bound(plan['conditions']['P0']['historical']['manifest']).read_text())
        self.assertEqual(original['requests'], plan['conditions']['P0']['requests'])
        per = {c: sum((Decimal(row['reserve_usd']) for row in plan['conditions'][c]['requests']),
                      Decimal(0)) for c in ('P0', 'P1', 'P2')}
        self.assertEqual(per, {'P0': Decimal('0.50912475'),
                               'P1': Decimal('0.51452700'),
                               'P2': Decimal('0.54328125')})
        self.assertEqual(2 * sum(per.values(), Decimal(0)), Decimal('3.13386600'))

    def test_source_hash_drift_and_unreviewed_condition_fail_closed(self):
        real_bind = repeat.bind
        with patch.object(repeat, 'bind', side_effect=lambda path: (
                {**real_bind(path), 'sha256': '0' * 64}
                if str(path).endswith('development-attempts.jsonl') else real_bind(path))):
            with self.assertRaises(ValueError):
                repeat.expected_plan(CONFIG, 'repeat2')
        with self.assertRaisesRegex(ValueError, 'Outside recovered Gemini'):
            repeat.expected_plan('gemini38-flash-medium-p0-openrouter-v3', 'repeat2')

    def test_live_preflight_fails_on_route_or_price_drift_without_key(self):
        plan = repeat.expected_plan(CONFIG, 'repeat2')
        old = plan['conditions']['P1']
        catalog = json.loads(repeat.bound(old['catalog']).read_text())
        endpoints = json.loads(repeat.bound(old['endpoints']).read_text())
        with patch.object(v3, 'fetch', side_effect=[catalog, endpoints]):
            repeat.live_controls(plan, 'P1')
        changed = json.loads(json.dumps(endpoints))
        entry = next(x for x in changed['data']['endpoints'] if x.get('tag') == v3.PROVIDER)
        entry['pricing']['completion'] = '0.00000400'
        with patch.object(v3, 'fetch', side_effect=[catalog, changed]):
            with self.assertRaises(ValueError):
                repeat.live_controls(plan, 'P1')

    def test_order_gate_requires_prior_phase_and_repeat(self):
        plan = repeat.expected_plan(CONFIG, 'repeat2')
        with patch.object(repeat, 'complete', return_value=False):
            repeat.require_order(plan, 'P1', 'smoke')
            with self.assertRaisesRegex(ValueError, 'Prior condition is incomplete'):
                repeat.require_order(plan, 'P2', 'smoke')
        with patch.object(repeat, 'validate_plan', return_value=plan), \
                patch.object(repeat, 'complete', return_value=False):
            with self.assertRaisesRegex(ValueError, 'Repeat 2 is incomplete'):
                repeat.require_order(repeat.expected_plan(CONFIG, 'repeat3'), 'P2', 'smoke')

    def test_synthetic_dispatch_reserves_then_saves_raw_before_parse(self):
        plan = repeat.expected_plan(CONFIG, 'repeat2')
        request = plan['conditions']['P1']['requests'][0]
        with tempfile.TemporaryDirectory() as folder:
            phase_dir = Path(folder)
            paths = {key: phase_dir / ('smoke.' + name) for key, name in (
                ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
                ('attempts', 'attempts.jsonl'), ('responses', 'responses.jsonl'),
                ('records', 'records.jsonl'))}
            review = phase_dir / 'review.json'
            review.write_text('{}')
            calls = []

            class Ledger:
                cap = Decimal('0.30')

                def state(self):
                    calls.append('state')
                    return Decimal(0), {}, False

                def reserve(self, amount, group):
                    self.assert_amount = amount
                    calls.append('reserve')
                    return 'synthetic-attempt'

                def settle(self, attempt_id, actual):
                    calls.append('settle')
                    return actual is not None

                def close(self):
                    calls.append('close')

            ledger = Ledger()

            def capture(payload, token, timeout, out, ids, attempt_id, digest):
                self.assertEqual(calls[-1], 'reserve')
                self.assertEqual(digest, request['payload_sha256'])
                calls.append('send_once')
                repeat.v3.durable(out, {'attempt_id': attempt_id, 'synthetic': True})
                return {'usage': {'cost': 0.001}}

            def parse_after_raw(*args):
                self.assertEqual(len(repeat.lines(paths['responses'])), 1)
                calls.append('parse_after_raw')
                return {'status': 'ok', 'predictions': {rid: {} for rid in request['record_ids']}}

            with patch.object(repeat, 'validate_plan', return_value=plan), \
                    patch.object(repeat, 'require_order'), \
                    patch.object(repeat, 'phase_paths', return_value=paths), \
                    patch.object(repeat, 'review_gate', return_value=review), \
                    patch.object(repeat, 'live_controls', return_value=({}, {})), \
                    patch.object(repeat, 'open_partition', return_value=ledger), \
                    patch.object(repeat, 'path_inside', side_effect=lambda path: Path(path)), \
                    patch.object(repeat.v3, 'load_key', return_value='synthetic-token'), \
                    patch.object(repeat.wave, 'fetch_recorded', side_effect=capture), \
                    patch.object(repeat, 'classify', side_effect=parse_after_raw):
                self.assertTrue(repeat.run(phase_dir / 'unused-manifest.json', 'plan-hash',
                                           review, 'P1', 'smoke'))
            self.assertEqual(calls.count('send_once'), 1)
            self.assertLess(calls.index('reserve'), calls.index('send_once'))
            self.assertLess(calls.index('send_once'), calls.index('parse_after_raw'))
            self.assertLess(calls.index('parse_after_raw'), calls.index('settle'))
            self.assertEqual(repeat.lines(paths['journal'])[-1]['event'], 'phase_completed')

    def test_ambiguous_synthetic_transport_stops_without_retry_or_release(self):
        plan = repeat.expected_plan(CONFIG, 'repeat2')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            paths = {key: base / ('smoke.' + name) for key, name in (
                ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
                ('attempts', 'attempts.jsonl'), ('responses', 'responses.jsonl'),
                ('records', 'records.jsonl'))}
            review = base / 'review.json'
            review.write_text('{}')
            calls = []

            class Ledger:
                cap = Decimal('0.30')

                def state(self):
                    return Decimal(0), {}, False

                def reserve(self, amount, group):
                    calls.append('reserve')
                    return 'synthetic-attempt'

                def settle(self, attempt_id, actual):
                    calls.append(('settle', actual))
                    return False

                def close(self):
                    pass

            def interrupted(*args):
                calls.append('send_once')
                raise TimeoutError('synthetic ambiguous boundary')

            with patch.object(repeat, 'validate_plan', return_value=plan), \
                    patch.object(repeat, 'require_order'), \
                    patch.object(repeat, 'phase_paths', return_value=paths), \
                    patch.object(repeat, 'review_gate', return_value=review), \
                    patch.object(repeat, 'live_controls', return_value=({}, {})), \
                    patch.object(repeat, 'open_partition', return_value=Ledger()), \
                    patch.object(repeat, 'path_inside', side_effect=lambda path: Path(path)), \
                    patch.object(repeat.v3, 'load_key', return_value='synthetic-token'), \
                    patch.object(repeat.wave, 'fetch_recorded', side_effect=interrupted):
                self.assertFalse(repeat.run(base / 'unused-manifest.json', 'plan-hash',
                                            review, 'P1', 'smoke'))
            self.assertEqual(calls, ['reserve', 'send_once', ('settle', None)])
            self.assertEqual(repeat.lines(paths['attempts'])[0]['cost_unknown'], True)
            self.assertEqual(repeat.lines(paths['journal'])[-1]['event'], 'phase_stopped')


if __name__ == '__main__':
    unittest.main()
