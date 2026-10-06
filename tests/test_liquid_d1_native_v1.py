import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import liquid_d1_native_v1 as liquid
import liquid_d1_smoke_v1 as smoke
import openrouter_decision_smoke as native
from development_benchmark import KEYS, VALUES


class LiquidOfflineTest(unittest.TestCase):
    def test_saved_plan_covers_every_condition_and_pass_with_input_only(self):
        plan, digest = liquid.verify()
        self.assertEqual(plan['status'], 'prepared_not_admitted')
        self.assertEqual(len(plan['phases']), 9)
        self.assertEqual([p['id'] for p in plan['phases']],
                         [f'fresh{i}/{condition}' for i in (1, 2, 3) for condition in ('P0', 'P1', 'P2')])
        self.assertEqual(len({p['id'] for p in plan['phases']}), 9)
        self.assertEqual([len(p['requests']) for p in plan['phases']], [60] * 9)
        self.assertEqual(plan['smoke_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertEqual(plan['max_aggregate_billable_input_tokens'], 262144)
        self.assertEqual(plan['three_record_smoke_bound_usd'], '0.03145728')
        self.assertEqual(digest, native.sha(native.canonical(plan)))
        for phase in plan['phases']:
            for request in phase['requests']:
                self.assertEqual(set(request['payload']['state']), {'feedback', 'policy'})
                self.assertEqual(set(request['payload']['state']), {'feedback', 'policy'})
                self.assertEqual(native.sha(native.canonical(request['payload'])), request['payload_sha256'])

    def test_native_question_delta_only(self):
        plan, _ = liquid.verify()
        phases = {p['id']: p for p in plan['phases']}
        for condition in ('P1', 'P2'):
            for before, after in zip(phases['fresh1/P0']['requests'], phases[f'fresh1/{condition}']['requests']):
                payload = after['payload']
                self.assertEqual(payload['state'], before['payload']['state'])
                liquid.check_payload(payload, payload['state']['feedback'], payload['state']['policy'], condition)
                self.assertNotEqual(after['payload_sha256'], before['payload_sha256'])
        for condition in ('P0', 'P1', 'P2'):
            self.assertEqual(phases[f'fresh1/{condition}']['requests_sha256'], phases[f'fresh2/{condition}']['requests_sha256'])

    def test_catalog_identity_and_price_drift_rejected(self):
        catalog = json.loads((liquid.BASE / 'endpoint-public.json').read_text())
        liquid.validate_catalog(catalog)
        for key, value in [('tag', 'other'), ('name', 'Liquid | next'), ('context_length', 65535)]:
            changed = json.loads(json.dumps(catalog))
            changed['data']['endpoints'][0][key] = value
            with self.assertRaises(ValueError): liquid.validate_catalog(changed)
        for key, value in [('prompt', '0.00000005'), ('input_cache_read', '0.00000005')]:
            changed = json.loads(json.dumps(catalog))
            changed['data']['endpoints'][0]['pricing'][key] = value
            with self.assertRaises(ValueError): liquid.validate_catalog(changed)

    def test_review_gate_prevents_send_without_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(smoke, 'post', side_effect=AssertionError('sent')):
                with self.assertRaises(FileNotFoundError):
                    smoke.run(liquid.BASE / 'smoke.root-review.json', Path(directory) / 'missing-budget.json',
                              send=smoke.post)

    def test_review_template_binds_plan_budget_and_runner(self):
        plan, digest = liquid.verify()
        with tempfile.TemporaryDirectory() as directory:
            budget = Path(directory) / 'budget.json'
            budget.write_text('{}\n')
            expected = smoke.expected_receipt(plan, digest, budget)
            self.assertEqual(expected['approved'], True)
            self.assertEqual(expected['three_record_bound_usd'], '0.03145728')
            self.assertEqual(expected['runner_sha256'], liquid.native.sha((ROOT / 'scripts/liquid_d1_smoke_v1.py').read_bytes()))
            with self.assertRaises(ValueError): smoke.verify_review(Path(directory) / 'other.json', plan, digest, budget)

    def test_four_question_aggregate_usage_is_accepted_within_bound(self):
        answers = {}
        for key in KEYS:
            choices = list(VALUES[key])
            answers[key] = {'type': 'choice', 'choice': choices[0], 'confidence': 1.0,
                            'probabilities': {name: float(name == choices[0]) for name in choices}}
        body = {'model': liquid.VERSION, 'provider': liquid.PROVIDER, 'answers': answers,
                'usage': {'input_tokens': liquid.CONTEXT + 1, 'output_tokens': 0}}
        self.assertEqual(set(smoke.validate_returned(body)), set(KEYS))
        body['usage']['input_tokens'] = liquid.QUESTION_COUNT * liquid.CONTEXT + 1
        with self.assertRaises(ValueError): smoke.validate_returned(body)


if __name__ == '__main__': unittest.main()
