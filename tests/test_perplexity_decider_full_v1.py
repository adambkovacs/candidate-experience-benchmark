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
import perplexity_decider_plan_v1 as route
import perplexity_decider_smoke_v1 as smoke
import perplexity_decider_full_v1 as full


KEY = 'decider'
STAGE = 'fresh1/P0'


def response(payload):
    answers = {}
    for field, question in payload['questions'].items():
        options = list(question['criteria'])
        answers[field] = {'type': 'choice', 'choice': options[0], 'confidence': 1.0,
                          'probabilities': {option: float(index == 0)
                                            for index, option in enumerate(options)}}
    return json.dumps({'model': route.MODELS[KEY]['returned_model'], 'provider': 'Perplexity',
                       'answers': answers,
                       'usage': {'input_tokens': 2400, 'output_tokens': 4,
                                 'cost': '0.000096'}}).encode()


class FakeLedger:
    def __init__(self):
        self.cap = Decimal('0.25')
        self.master_cap = Decimal('22.38')
        self.closed = False
        self.pending = {}
        self.actual = Decimal('0')

    def state(self):
        return None, self.pending, False

    def accounted(self):
        return self.actual + sum(self.pending.values(), Decimal('0'))

    def reserve(self, amount, rid):
        attempt = 'attempt-' + rid
        self.pending[attempt] = amount
        return attempt

    def settle(self, attempt, amount):
        if amount > self.pending[attempt]:
            return False
        del self.pending[attempt]
        self.actual += amount
        return True

    def close(self):
        self.closed = True


class PerplexityFullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full_plan, cls.full_sha = full.verify(ROOT)
        cls.route_plan, cls.route_sha = route.verify(ROOT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.budget = self.root / 'budget.json'
        self.budget.write_text('{}')
        self.ledger = FakeLedger()
        self.catalog = json.loads((ROOT / route.catalog_path(KEY)).read_text())['response']
        review = self.root / full.REVIEW
        review.parent.mkdir(parents=True)
        review.write_text('{}')

    def run_with(self, send):
        with mock.patch.object(full, 'verify', return_value=(self.full_plan, self.full_sha)), \
                mock.patch.object(route, 'verify', return_value=(self.route_plan, self.route_sha)), \
                mock.patch.object(full, 'verify_global_review', return_value={}), \
                mock.patch.object(full, 'verify_smoke_inspection', return_value='a' * 64), \
                mock.patch.object(full, 'verify_hold', return_value=None), \
                mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}, clear=False):
            full.run(KEY, STAGE, self.budget, root=self.root,
                     fetch=lambda _: (native.canonical(self.catalog), self.catalog),
                     send=send, open_child=lambda *args: self.ledger)

    def test_full_gate_pins_route_sixty_ids_and_one_request_reserve(self):
        self.assertEqual(self.full_plan['schema'], 'perplexity-decider-native-full-gate-v2')
        self.assertEqual(self.full_plan['models'][KEY]['model'], route.MODELS[KEY]['model'])
        self.assertEqual(self.full_plan['models'][KEY]['development_ids'], list(route.IDS))
        self.assertEqual(len(self.full_plan['models'][KEY]['stages']), 9)
        self.assertEqual(self.full_plan['models'][KEY]['per_request_four_context_bound_usd'], '0.04194304')
        self.assertEqual(self.full_plan['proposed_child_usd'], '0.25')
        self.assertFalse(self.full_plan['inference_performed'])
        self.assertFalse(self.full_plan['allocation_performed'])

    def test_sixty_development_requests_close_once(self):
        sent = []

        def send(payload, token):
            sent.append(payload['state']['feedback'])
            return 200, response(payload)

        self.run_with(send)
        self.assertEqual(len(sent), 60)
        self.assertEqual(self.ledger.actual, Decimal('0.005760'))
        self.assertFalse(self.ledger.pending)
        folder = full.stage_dir(self.root, KEY, STAGE)
        raw = [json.loads(line) for line in (folder / 'development.raw.jsonl').read_text().splitlines()]
        self.assertEqual([row['id'] for row in raw], list(route.IDS))
        self.assertEqual(json.loads((folder / 'development.claim.json').read_text())['reference_labels_sent'], False)
        with self.assertRaises(FileExistsError):
            self.run_with(send)
        self.assertEqual(len(sent), 60)

    def test_unknown_first_stops_and_keeps_full_bound(self):
        sent = []

        def send(payload, token):
            sent.append(payload)
            return 429, b'{"error":"upstream rate limit"}'

        with self.assertRaisesRegex(ValueError, 'cost unknown'):
            self.run_with(send)
        self.assertEqual(len(sent), 1)
        self.assertEqual(list(self.ledger.pending.values()), [route.bound(KEY, 1)])
        with self.assertRaises(FileExistsError):
            self.run_with(send)

    def test_missing_smoke_inspection_blocks_before_fetch(self):
        fetch, send, child = mock.Mock(), mock.Mock(), mock.Mock()
        with mock.patch.object(full, 'verify', return_value=(self.full_plan, self.full_sha)), \
                mock.patch.object(route, 'verify', return_value=(self.route_plan, self.route_sha)), \
                mock.patch.object(full, 'verify_global_review', return_value={}), \
                mock.patch.object(full, 'verify_smoke_inspection', side_effect=ValueError('inspection missing')):
            with self.assertRaisesRegex(ValueError, 'inspection missing'):
                full.run(KEY, STAGE, self.budget, root=self.root,
                         fetch=fetch, send=send, open_child=child)
        fetch.assert_not_called()
        send.assert_not_called()
        child.assert_not_called()

    def test_budget_manifest_must_match_reviewed_child_cap(self):
        manifest = {'version': 'paid-partitions-v1',
                    'master_ledger': str((self.root / 'master.jsonl').resolve()),
                    'partitions': [{'id': full.partition_id(KEY),
                                    'model': route.MODELS[KEY]['model'],
                                    'provider': 'Perplexity', 'reasoning': full.REASONING,
                                    'cap_usd': '0.30'}]}
        self.budget.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'reviewed \\$0.25 cap'):
            full._budget_entry(self.budget, KEY, self.root / 'master.jsonl')

    def test_wrong_returned_model_stops_after_one_saved_raw_response(self):
        sent = []

        def send(payload, token):
            sent.append(payload)
            body = json.loads(response(payload))
            body['model'] = route.MODELS[KEY]['model']
            return 200, json.dumps(body).encode()

        with self.assertRaisesRegex(ValueError, 'Returned model mismatch'):
            self.run_with(send)
        self.assertEqual(len(sent), 1)
        self.assertFalse(self.ledger.pending)
        folder = full.stage_dir(self.root, KEY, STAGE)
        self.assertEqual(len((folder / 'development.raw.jsonl').read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
