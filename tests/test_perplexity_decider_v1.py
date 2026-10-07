import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_decision_smoke as native
import perplexity_decider_plan_v1 as plan
import perplexity_decider_full_plan_v1 as full_plan
import perplexity_decider_smoke_v1 as smoke


KEY = 'decider'
STAGE = 'fresh1/P0'


def answer(payload, *, returned=plan.MODELS[KEY]['returned_model'], provider='Perplexity'):
    choices = {}
    for field, question in payload['questions'].items():
        options = list(question['criteria'])
        choices[field] = {'type': 'choice', 'choice': options[0], 'confidence': 1.0,
                          'probabilities': {option: float(i == 0)
                                            for i, option in enumerate(options)}}
    return json.dumps({'model': returned, 'provider': provider, 'answers': choices,
                       'usage': {'input_tokens': 2400, 'output_tokens': 0,
                                 'cost': '0.000096'}}).encode()


class FakeLedger:
    def __init__(self):
        self.master_cap = Decimal('22.38')
        self.cap = plan.bound(KEY, 3)
        self.closed = False
        self.pending = {}
        self.actual = Decimal('0')

    def state(self):
        return None, self.pending, False

    def accounted(self):
        return self.actual + sum(self.pending.values(), Decimal('0'))

    def reserve(self, amount, rid):
        ident = 'attempt-' + rid
        self.pending[ident] = amount
        return ident

    def settle(self, ident, actual):
        if actual > self.pending[ident]:
            return False
        del self.pending[ident]
        self.actual += actual
        return True

    def close(self):
        self.closed = True


class PerplexityPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.value, cls.digest = plan.verify(ROOT)

    def test_exact_route_and_nine_input_only_stages(self):
        value = self.value
        model = value['models'][KEY]
        self.assertEqual((value['status'], value['inference_performed'],
                          value['allocation_performed'], value['reference_labels_read']),
                         ('prepared_not_admitted', False, False, False))
        self.assertEqual((model['model'], model['provider_tag'], model['expected_returned_model']),
                         ('perplexity/pplx-decider-v1-27b', 'perplexity',
                          'perplexity/pplx-decider-v1-27b-20261001'))
        self.assertEqual([stage['id'] for stage in model['stages']],
                         [f'{fresh}/{condition}' for fresh in plan.PASSES
                          for condition in plan.CONDITIONS])
        for condition in plan.CONDITIONS:
            requests = model['requests'][condition]
            self.assertEqual([r['id'] for r in requests], list(plan.IDS))
            for item in requests:
                payload = item['payload']
                self.assertEqual(set(payload), {'model', 'state', 'questions', 'provider'})
                self.assertEqual(set(payload['state']), {'feedback', 'policy'})
                self.assertEqual(payload['provider']['only'], ['perplexity'])
                self.assertFalse(payload['provider']['allow_fallbacks'])
                self.assertEqual([q['type'] for q in payload['questions'].values()], ['choice'] * 4)
        self.assertNotIn('proposed_labels', json.dumps(value))
        self.assertEqual(plan.bound(KEY, 1), Decimal('0.04194304'))
        self.assertEqual(plan.bound(KEY, 3), Decimal('0.12582912'))

    def test_catalog_and_payload_drift_fail_closed(self):
        snapshot = json.loads((ROOT / plan.catalog_path(KEY)).read_text())
        snapshot['response']['data']['endpoints'][0]['name'] = 'different version'
        with self.assertRaisesRegex(ValueError, 'provider/version'):
            plan.validate_catalog(KEY, snapshot)
        item = self.value['models'][KEY]['requests']['P1'][0]
        payload = json.loads(json.dumps(item['payload']))
        payload['state']['reference'] = 'hidden answer'
        with self.assertRaisesRegex(ValueError, 'changed input'):
            plan.verify_request(payload, item['payload']['state']['feedback'],
                                item['payload']['state']['policy'], KEY, 'P1')

    def test_full_plan_has_no_dispatch_or_advance_allocation(self):
        value, _ = full_plan.verify(ROOT)
        self.assertEqual((value['status'], value['development_runner_status']),
                         ('prepared_not_admitted', 'not_prepared_no_dispatch'))
        self.assertEqual(len(value['stages']), 9)
        self.assertEqual(value['development_ids'], list(plan.IDS))
        self.assertEqual(value['proposed_development_child_usd'], '0.75')
        self.assertEqual(value['per_request_four_context_bound_usd'], '0.04194304')


class PerplexitySmokeTests(unittest.TestCase):
    def setUp(self):
        self.value, self.digest = plan.verify(ROOT)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.budget = self.root / 'budget.json'
        self.budget.write_text('{}')
        self.receipt = smoke.stage_dir(self.root, KEY, STAGE) / 'smoke.root-review.json'
        self.receipt.parent.mkdir(parents=True)
        self.receipt.write_text('{}')
        self.ledger = FakeLedger()
        self.catalog = json.loads((ROOT / plan.catalog_path(KEY)).read_text())['response']

    def run_with(self, send):
        with mock.patch.object(plan, 'verify', return_value=(self.value, self.digest)), \
                mock.patch.object(smoke, 'verify_review', return_value={}), \
                mock.patch.object(smoke, 'verify_hold', return_value=None), \
                mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}, clear=False):
            return smoke.run(KEY, STAGE, self.receipt, self.budget, root=self.root,
                             fetch=lambda _: (native.canonical(self.catalog), self.catalog),
                             send=send, open_child=lambda *args: self.ledger)

    def test_review_gate_precedes_fetch_and_child(self):
        fetch, send, child = mock.Mock(), mock.Mock(), mock.Mock()
        with mock.patch.object(plan, 'verify', return_value=(self.value, self.digest)), \
                mock.patch.object(smoke, 'verify_review', side_effect=ValueError('independent review missing')):
            with self.assertRaisesRegex(ValueError, 'review missing'):
                smoke.run(KEY, STAGE, self.receipt, self.budget, root=self.root,
                          fetch=fetch, send=send, open_child=child)
        fetch.assert_not_called()
        send.assert_not_called()
        child.assert_not_called()

    def test_three_responses_settle_sequentially_and_cannot_replay(self):
        calls = []

        def send(payload, token):
            calls.append(payload['state']['feedback'])
            return 200, answer(payload)

        self.run_with(send)
        self.assertEqual(len(calls), 3)
        self.assertEqual(self.ledger.actual, Decimal('0.000288'))
        self.assertFalse(self.ledger.pending)
        folder = smoke.stage_dir(self.root, KEY, STAGE)
        raw = [json.loads(line) for line in (folder / 'smoke.raw.jsonl').read_text().splitlines()]
        self.assertEqual([record['id'] for record in raw], list(plan.SMOKE_IDS))
        with self.assertRaises(FileExistsError):
            self.run_with(send)
        self.assertEqual(len(calls), 3)

    def test_unknown_cost_stops_after_first_and_keeps_reserve(self):
        calls = []

        def send(payload, token):
            calls.append(payload)
            return 429, b'{"error":"rate limited"}'

        with self.assertRaisesRegex(ValueError, 'cost unknown'):
            self.run_with(send)
        self.assertEqual(len(calls), 1)
        self.assertEqual(list(self.ledger.pending.values()), [plan.bound(KEY, 1)])
        with self.assertRaises(FileExistsError):
            self.run_with(send)

    def test_wrong_returned_version_stops_with_raw_response_preserved(self):
        calls = []

        def send(payload, token):
            calls.append(payload)
            return 200, answer(payload, returned=plan.MODELS[KEY]['model'])

        with self.assertRaisesRegex(ValueError, 'Returned model mismatch'):
            self.run_with(send)
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.ledger.pending)
        folder = smoke.stage_dir(self.root, KEY, STAGE)
        self.assertEqual(len((folder / 'smoke.raw.jsonl').read_text().splitlines()), 1)
        self.assertEqual(len((folder / 'smoke.parsed.jsonl').read_text().splitlines()), 0)


if __name__ == '__main__':
    unittest.main()
