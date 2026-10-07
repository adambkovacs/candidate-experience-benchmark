import base64
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
import clef_openrouter_native_v1 as route
import clef_openrouter_smoke_v1 as smoke
import clef_openrouter_full_v1 as full
import openrouter_decision_smoke as native


def response(payload, returned=None):
    answers = {}
    for key, question in payload['questions'].items():
        options = list(question['criteria'])
        answers[key] = {'type': 'choice', 'choice': options[0], 'confidence': 1.0,
                        'probabilities': {option: float(i == 0) for i, option in enumerate(options)}}
    return json.dumps({'model': returned or payload['model'],
                       'provider': route.MODELS['luna-decisions']['provider']
                       if payload['model'] == route.MODELS['luna-decisions']['model'] else 'Cloudflare',
                       'answers': answers,
                       'usage': {'input_tokens': 2200, 'output_tokens': 0, 'cost': '0.000528'}}).encode()


class FakeLedger:
    def __init__(self, key):
        self.cap = route.bound(key, 1) + Decimal('.04')
        self.master_cap = Decimal('22.38')
        self.closed = False
        self.pending = {}
        self.actual = Decimal(0)
        self.close_count = 0

    def state(self):
        return None, self.pending, False

    def accounted(self):
        return self.actual + sum(self.pending.values(), Decimal(0))

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
        self.close_count += 1


class FullTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route_plan, cls.route_sha = route.verify(ROOT)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = 'clef'
        self.stage = 'fresh1/P0'
        self.folder = full.stage_dir(self.root, self.key, self.stage)
        self.folder.mkdir(parents=True)
        review = self.root / full.REVIEW
        review.parent.mkdir(parents=True, exist_ok=True)
        review.write_text('{}')
        self.budget = self.root / 'budget.json'
        self.budget.write_text('{}')
        self.ledger = FakeLedger(self.key)
        self.catalog = json.loads((ROOT / route.catalog_path(self.key)).read_text())['response']
        self.full_plan = full.build(ROOT)
        self.full_sha = native.sha(native.canonical(self.full_plan))

    def run_with(self, send):
        with mock.patch.object(full, 'verify', return_value=(self.full_plan, self.full_sha)), \
                mock.patch.object(route, 'verify', return_value=(self.route_plan, self.route_sha)), \
                mock.patch.object(full, 'verify_global_review', return_value={}), \
                mock.patch.object(full, 'verify_smoke_inspection', return_value='a' * 64), \
                mock.patch.object(full, 'verify_hold', return_value=None), \
                mock.patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-only'}, clear=False):
            full.run(self.key, self.stage, self.budget, root=self.root,
                     fetch=lambda _: (native.canonical(self.catalog), self.catalog),
                     send=send, open_child=lambda *args: self.ledger)

    def test_exact_sixty_development_requests_and_no_replay(self):
        calls = []
        def send(payload, token):
            calls.append(payload['state']['feedback'])
            return 200, response(payload)
        self.run_with(send)
        self.assertEqual(len(calls), 60)
        self.assertEqual(self.ledger.actual, Decimal('.031680'))
        self.assertFalse(self.ledger.pending)
        self.assertEqual(self.ledger.close_count, 1)
        raw = [json.loads(line) for line in (self.folder / 'development.raw.jsonl').read_text().splitlines()]
        parsed = [json.loads(line) for line in (self.folder / 'development.parsed.jsonl').read_text().splitlines()]
        self.assertEqual([r['id'] for r in raw], list(route.IDS))
        self.assertEqual([r['id'] for r in parsed], list(route.IDS))
        self.assertTrue(all(r['response_base64'] and r['client_request_elapsed_ns'] >= 0 for r in raw))
        with self.assertRaises(FileExistsError):
            self.run_with(send)
        self.assertEqual(len(calls), 60)

    def test_unknown_first_keeps_reserve_and_stops(self):
        calls = []
        def send(payload, token):
            calls.append(payload)
            return 429, b'{"error":"provider busy"}'
        with self.assertRaisesRegex(ValueError, 'cost unknown'):
            self.run_with(send)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.ledger.pending), 1)
        self.assertEqual(len((self.folder / 'development.raw.jsonl').read_text().splitlines()), 1)
        with self.assertRaises(FileExistsError):
            self.run_with(send)

    def test_missing_inspection_rejects_before_child_or_post(self):
        with mock.patch.object(full, 'verify', return_value=(self.full_plan, self.full_sha)), \
                mock.patch.object(route, 'verify', return_value=(self.route_plan, self.route_sha)), \
                mock.patch.object(full, 'verify_global_review', return_value={}), \
                mock.patch.object(full, 'verify_smoke_inspection', side_effect=ValueError('missing inspection')):
            fetch, send, child = mock.Mock(), mock.Mock(), mock.Mock()
            with self.assertRaisesRegex(ValueError, 'missing inspection'):
                full.run(self.key, self.stage, self.budget, root=self.root,
                         fetch=fetch, send=send, open_child=child)
            fetch.assert_not_called()
            send.assert_not_called()
            child.assert_not_called()

    def test_luna_requires_exact_dated_returned_id(self):
        payload = self.route_plan['models']['luna-decisions']['requests']['P0'][0]['payload']
        dated = response(payload, full.RETURNED_MODEL['luna-decisions'])
        self.assertEqual(set(full.validate_returned('luna-decisions', json.loads(dated))),
                         {'sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'})
        with self.assertRaisesRegex(ValueError, 'Returned model mismatch'):
            full.validate_returned('luna-decisions', json.loads(response(payload)))

    def test_historical_luna_claim_blocks_replay_in_new_smoke_mode(self):
        old = smoke.stage_dir(self.root, 'luna-decisions', self.stage)
        old.mkdir(parents=True)
        (old / 'smoke.claim.json').write_text('{}')
        with mock.patch.object(full, 'verify', return_value=(self.full_plan, self.full_sha)), \
                mock.patch.object(route, 'verify', return_value=(self.route_plan, self.route_sha)), \
                mock.patch.object(full, 'verify_global_review', return_value={}), \
                mock.patch.object(full, 'verify_previous_stage', return_value=None), \
                mock.patch.object(full, 'verify_hold', return_value=None):
            fetch, send, child = mock.Mock(), mock.Mock(), mock.Mock()
            with self.assertRaisesRegex(FileExistsError, 'Historical smoke already claimed'):
                full.run('luna-decisions', self.stage, self.budget, phase='smoke',
                         root=self.root, fetch=fetch, send=send, open_child=child)
            fetch.assert_not_called()
            send.assert_not_called()
            child.assert_not_called()

    def test_v4_authority_released_hold_rejected(self):
        from contextlib import contextmanager
        cap = route.bound(self.key, 1) + Decimal('.04')
        pid = full.partition_id(self.key)
        budget = {'version': 'paid-partitions-v1', 'master_ledger': str(smoke.MASTER.resolve()),
                  'partitions': [{'id': pid, 'model': route.MODELS[self.key]['model'],
                                  'provider': 'Cloudflare', 'reasoning': full.REASONING,
                                  'cap_usd': str(cap)}]}
        self.budget.write_text(json.dumps(budget))
        source = full.hold_source(self.full_sha, self.budget, self.key)
        hold = {'version': 3, 'funding_pool': 'openrouter_additional', 'usd': str(cap),
                'source_sha256': source, 'budget_manifest_sha256': full.sha_path(self.budget),
                'budget_manifest_path': str(self.budget.resolve()),
                'master_path': str(smoke.MASTER.resolve()), 'partition_id': pid}
        @contextmanager
        def locked(_):
            yield io.StringIO('v4 authority fixture')
        with mock.patch.object(full.authority.old, '_locked', locked), \
                mock.patch.object(full.authority, '_scan', return_value=(object(), {pid: hold}, set())):
            full.verify_hold(self.full_sha, self.budget, self.key)
        with mock.patch.object(full.authority.old, '_locked', locked), \
                mock.patch.object(full.authority, '_scan', return_value=(object(), {pid: hold}, {pid})), \
                self.assertRaisesRegex(ValueError, 'active development authority hold missing'):
            full.verify_hold(self.full_sha, self.budget, self.key)


if __name__ == '__main__':
    unittest.main()
