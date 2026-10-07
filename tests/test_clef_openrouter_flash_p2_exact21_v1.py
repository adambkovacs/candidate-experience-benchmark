import io
import json
from decimal import Decimal
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_openrouter_flash_p2_exact21_v1 as successor
import clef_openrouter_native_v1 as route
import clef_openrouter_full_v1 as full
import openrouter_decision_smoke as native


def answer(payload):
    answers = {}
    for key, question in payload['questions'].items():
        labels = list(question['criteria'])
        answers[key] = {'type': 'choice', 'choice': labels[0], 'confidence': 1.0,
                        'probabilities': {label: float(i == 0) for i, label in enumerate(labels)}}
    return json.dumps({'model': payload['model'], 'provider': 'Cloudflare', 'answers': answers,
                       'usage': {'input_tokens': 2200, 'output_tokens': 0, 'cost': '0.000198'}}).encode()


class FakeLedger:
    def __init__(self):
        self.cap = route.bound(successor.KEY, 1) + Decimal('.01')
        self.master_cap = Decimal('22.38')
        self.closed = False
        self.pending = {}
        self.actual = Decimal(0)

    def state(self):
        return None, self.pending, False

    def accounted(self):
        return self.actual + sum(self.pending.values(), Decimal(0))

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
        pass


class SuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.digest = successor.verify(ROOT)
        cls.original, cls.route_sha = route.verify(ROOT)

    def test_only_never_sent_suffix_and_unknown_preserved(self):
        plan = self.plan
        self.assertEqual(plan['request_ids'], list(successor.IDS))
        self.assertEqual(plan['request_ids'], [f'DEV-{i:03}' for i in range(40, 61)])
        self.assertEqual(plan['parent']['unknown_upper_bound_usd'], '0.02359296')
        self.assertEqual(plan['parent']['known_actual_usd'], '0.11685312')
        self.assertEqual(plan['parent']['unused_after_finalization_usd'], '0.25955392')
        self.assertEqual(plan['parent']['exact_requests'], self.original['models']['clef-flash']['requests']['P2'][39:])
        self.assertFalse(plan['inference_performed'] or plan['allocation_performed'])

    def test_parent_prefix_and_immutable_attempt_hash_bound(self):
        if not (ROOT / full.BASE / successor.KEY / 'fresh3/P2/development.raw.jsonl').exists():
            self.skipTest('Private original HTTP response is only checked in the execution checkout')
        parent, budget, child, entry = successor.parent_paths(ROOT)
        evidence = self.plan['parent']
        pieces = child.read_bytes().splitlines(keepends=True)
        self.assertEqual(native.sha(b''.join(pieces[:evidence['child_prefix_events']])),
                         evidence['child_prefix_sha256'])
        self.assertEqual(len(pieces), evidence['child_prefix_events'] + 2)
        self.assertEqual(successor.sha_path(parent / 'development.attempts.jsonl'),
                         evidence['source_sha256'][str((parent / 'development.attempts.jsonl').relative_to(ROOT))])
        self.assertEqual(successor.verify_parent_reconciled(ROOT, self.plan), successor.sha_path(child))

    def test_twenty_one_mocked_requests_settle_and_replay_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / successor.REVIEW).parent.mkdir(parents=True)
            (root / successor.REVIEW).write_text('{}')
            budget = root / 'budget.json';budget.write_text('{}')
            ledger = FakeLedger()
            catalog = json.loads((ROOT / route.catalog_path(successor.KEY)).read_text())['response']
            calls = []
            def send(payload, token):
                calls.append(payload)
                return 200, answer(payload)
            with mock.patch.object(successor, 'verify', return_value=(self.plan, self.digest)), \
                    mock.patch.object(successor, 'verify_parent_reconciled', return_value='c' * 64), \
                    mock.patch.object(successor, 'verify_review', return_value='r' * 64), \
                    mock.patch.object(successor, 'verify_hold', return_value=None), \
                    mock.patch.object(route, 'verify', return_value=(self.original, self.route_sha)), \
                    mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}, clear=False):
                successor.run(budget, root=root,
                    fetch=lambda _: (native.canonical(catalog), catalog), send=send,
                    open_child=lambda *args: ledger)
                with self.assertRaises(FileExistsError):
                    successor.run(budget, root=root,
                        fetch=lambda _: (native.canonical(catalog), catalog), send=send,
                        open_child=lambda *args: ledger)
            self.assertEqual(len(calls), 21)
            self.assertEqual(ledger.actual, Decimal('.004158'))
            self.assertFalse(ledger.pending)
            saved = successor.rows(root / successor.BASE / 'development.parsed.jsonl')
            self.assertEqual([x['id'] for x in saved], list(successor.IDS))

    def test_unknown_first_keeps_reserve_and_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / successor.REVIEW).parent.mkdir(parents=True)
            (root / successor.REVIEW).write_text('{}')
            budget = root / 'budget.json';budget.write_text('{}')
            ledger = FakeLedger()
            catalog = json.loads((ROOT / route.catalog_path(successor.KEY)).read_text())['response']
            calls = []
            def send(payload, token):
                calls.append(payload)
                return 429, b'{"error":"rate limit"}'
            with mock.patch.object(successor, 'verify', return_value=(self.plan, self.digest)), \
                    mock.patch.object(successor, 'verify_parent_reconciled', return_value='c' * 64), \
                    mock.patch.object(successor, 'verify_review', return_value='r' * 64), \
                    mock.patch.object(successor, 'verify_hold', return_value=None), \
                    mock.patch.object(route, 'verify', return_value=(self.original, self.route_sha)), \
                    mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}, clear=False):
                with self.assertRaisesRegex(ValueError, 'cost unknown'):
                    successor.run(budget, root=root,
                        fetch=lambda _: (native.canonical(catalog), catalog), send=send,
                        open_child=lambda *args: ledger)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(ledger.pending), 1)
            self.assertEqual(len(successor.rows(root / successor.BASE / 'development.raw.jsonl')), 1)


if __name__ == '__main__':
    unittest.main()
