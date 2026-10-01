import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import solar_decide_smoke_v1 as run
import solar_decide_offline_plan as plan
from development_benchmark import KEYS, VALUES


class FakeChild:
    def __init__(self, cap=Decimal('0.08')):
        self.cap = cap
        self.master_cap = Decimal('12.38')
        self.closed = False
        self.events = []
        self.pending = set()
        self.blocked = False
    def state(self):
        return {}, set(self.pending), self.blocked
    def accounted(self):
        total = Decimal(0)
        for _, amount in self.events:
            total += amount
        return total
    def reserve(self, amount, rid):
        assert self.accounted() + amount <= self.cap
        attempt = 'attempt-' + rid
        self.events.append((attempt, amount))
        self.pending.add(attempt)
        return attempt
    def settle(self, attempt, amount):
        assert attempt in self.pending
        reserved = dict(self.events)[attempt]
        self.pending.remove(attempt)
        self.events = [(a, amount if a == attempt else v) for a, v in self.events]
        self.blocked = amount > reserved or self.accounted() > self.cap
        return not self.blocked
    def close(self):
        self.closed = True


def valid_body():
    answers = {}
    for key in KEYS:
        labels = VALUES[key]
        answers[key] = {'type': 'choice', 'choice': labels[0], 'confidence': 1,
                        'probabilities': {label: (1.0 if i == 0 else 0.0)
                                          for i, label in enumerate(labels)}}
    return {'model': plan.VERSION, 'provider': plan.PROVIDER, 'answers': answers,
            'usage': {'input_tokens': 1000, 'output_tokens': 0, 'cost': 0.00005}}


class SolarSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name) / 'stage'
        self.budget = Path(self.tmp.name) / 'partition.json'
        self.budget.write_text('{}\n')
        self.digest = run.prepare(self.base)
        manifest = json.loads((self.base / 'manifest.json').read_text())
        self.receipt = self.base / 'smoke.root-review.json'
        self.receipt.write_text(json.dumps({**run.expected_receipt(manifest, self.digest, self.budget),
                                             'reviewer': 'root'}) + '\n')
        self.route_raw = (run.PUBLIC_AUDIT / 'endpoints.json').read_bytes()
        self.route = json.loads(self.route_raw)

    def execute(self, send, child=None, fetch=None):
        child = child or FakeChild()
        fetch = fetch or (lambda: (self.route_raw, self.route))
        with patch.object(run, 'load_key', return_value='fake-secret'):
            run.run(self.receipt, self.budget, self.base, fetch=fetch, send=send,
                    open_child=lambda *args: child)
        return child

    def test_manifest_has_exact_input_only_three_and_distinct_source_bindings(self):
        manifest, digest = run.verify(self.base)
        self.assertEqual(digest, self.digest)
        self.assertEqual(manifest['smoke_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertFalse(manifest['reference_labels_read'])
        self.assertEqual(manifest['provider_tag'], 'upstage')
        self.assertEqual(manifest['three_record_bound_usd'], '0.07864320')
        self.assertIn('scripts/paid_budget_partitions_v3.py', manifest['source_sha256'])
        for request in manifest['requests']:
            self.assertEqual(request['payload']['provider']['only'], ['upstage'])
            self.assertIs(request['payload']['provider']['allow_fallbacks'], False)
            self.assertEqual(set(request['payload']['state']), {'feedback', 'policy'})
            self.assertNotIn('reference_labels', request['payload'])
            self.assertNotIn('reference_answers', request['payload']['state'])

    def test_source_or_payload_drift_rejected(self):
        path = self.base / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['requests'][0]['payload']['state']['feedback'] += 'tampered'
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'drift'):
            run.verify(self.base)

    def test_bad_receipt_stops_before_transport(self):
        receipt = json.loads(self.receipt.read_text()); receipt['three_record_bound_usd'] = '0.01'
        self.receipt.write_text(json.dumps(receipt))
        with patch.object(run, 'load_key', return_value='fake-secret'):
            with self.assertRaisesRegex(ValueError, 'receipt'):
                run.run(self.receipt, self.budget, self.base,
                        fetch=lambda: self.fail('route fetched before receipt'),
                        send=lambda *_: self.fail('sent'), open_child=lambda *_: self.fail('budget opened'))

    def test_route_drift_stops_before_reservation(self):
        route = json.loads(self.route_raw)
        route['data']['endpoints'][0]['pricing']['prompt'] = '0.00000006'
        with self.assertRaisesRegex(ValueError, 'prices'):
            self.execute(lambda *_: self.fail('sent'), fetch=lambda: (b'changed', route))
        self.assertFalse((self.base / 'smoke.claim.json').exists())

    def test_route_drift_after_first_request_stops_second(self):
        altered = json.loads(self.route_raw)
        altered['data']['endpoints'][1]['context_length'] = 8192
        route_calls = []
        def fetch():
            route_calls.append(1)
            return (self.route_raw, self.route) if len(route_calls) < 3 else (b'changed', altered)
        child = FakeChild()
        sent = []
        with self.assertRaises(ValueError):
            self.execute(lambda *_: (sent.append(1), (200, json.dumps(valid_body()).encode()))[1],
                         child, fetch)
        self.assertEqual(sent, [1])
        self.assertFalse(child.pending)

    def test_child_must_cover_all_three_full_context_bounds(self):
        child = FakeChild(Decimal('0.05'))
        with self.assertRaisesRegex(ValueError, 'full three-request bound'):
            self.execute(lambda *_: self.fail('sent before full admission'), child)
        self.assertFalse((self.base / 'smoke.claim.json').exists())

    def test_success_raw_parsed_and_no_replay(self):
        body = json.dumps(valid_body()).encode()
        calls = []
        def send(payload, token):
            self.assertEqual(token, 'fake-secret')
            calls.append(payload)
            return 200, body
        child = self.execute(send)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(child.pending), 0)
        self.assertEqual(child.accounted(), Decimal('0.00015'))
        raw = [json.loads(x) for x in (self.base / 'smoke.raw.jsonl').read_text().splitlines()]
        parsed = [json.loads(x) for x in (self.base / 'smoke.parsed.jsonl').read_text().splitlines()]
        self.assertEqual(len(raw), len(parsed))
        self.assertEqual(len(raw), 3)
        self.assertTrue(all(x['returned_model'] == plan.VERSION for x in parsed))
        journal = [json.loads(x) for x in (self.base / 'smoke.journal.jsonl').read_text().splitlines()]
        self.assertEqual(sum(x['event'] == 'request_started' for x in journal), 3)
        self.assertTrue(all(x['live_endpoint_sha256'] == run.native.sha(self.route_raw)
                            for x in journal if x['event'] == 'request_started'))
        with self.assertRaises(FileExistsError):
            self.execute(lambda *_: self.fail('replayed'))

    def test_unknown_cost_retains_full_reservation_and_stops(self):
        body = valid_body(); del body['usage']['cost']
        calls = []
        child = FakeChild()
        with self.assertRaisesRegex(ValueError, 'full reservation retained'):
            self.execute(lambda *_: (calls.append(1), (200, json.dumps(body).encode()))[1], child)
        self.assertEqual(calls, [1])
        self.assertEqual(child.pending, {'attempt-DEV-001'})
        self.assertEqual(child.accounted(), run.BOUND)
        self.assertEqual(len((self.base / 'smoke.raw.jsonl').read_text().splitlines()), 1)

    def test_known_over_bound_cost_is_settled_and_blocks_child(self):
        body = valid_body(); body['usage']['cost'] = 0.04
        child = FakeChild()
        sent = []
        with self.assertRaisesRegex(ValueError, 'blocked by observed cost'):
            self.execute(lambda *_: (sent.append(1), (200, json.dumps(body).encode()))[1], child)
        self.assertEqual(sent, [1])
        self.assertFalse(child.pending)
        self.assertTrue(child.blocked)
        self.assertEqual(child.accounted(), Decimal('0.04'))
        attempts = [json.loads(x) for x in (self.base / 'smoke.attempts.jsonl').read_text().splitlines()]
        self.assertEqual(attempts[0]['status'], 'observed_cost_over_bound')
        self.assertEqual(attempts[0]['actual_cost_usd'], '0.04')

    def test_invalid_distribution_stops_after_known_settlement(self):
        body = valid_body(); body['answers']['sentiment']['probabilities']['negative'] = 0.5
        child = FakeChild()
        with self.assertRaises(ValueError):
            self.execute(lambda *_: (200, json.dumps(body).encode()), child)
        self.assertFalse(child.pending)
        self.assertEqual(child.accounted(), Decimal('0.00005'))
        self.assertEqual(len((self.base / 'smoke.raw.jsonl').read_text().splitlines()), 1)

    def test_returned_model_mismatch_stops_after_known_settlement(self):
        body = valid_body(); body['model'] = plan.MODEL
        child = FakeChild()
        with self.assertRaisesRegex(ValueError, 'Returned model mismatch'):
            self.execute(lambda *_: (200, json.dumps(body).encode()), child)
        self.assertFalse(child.pending)
        self.assertEqual(len((self.base / 'smoke.parsed.jsonl').read_text().splitlines()), 0)

    def test_transport_unknown_retains_reserve_and_no_retry(self):
        child = FakeChild()
        calls = []
        def fail(*_):
            calls.append(1)
            raise TimeoutError('no answer')
        with self.assertRaises(TimeoutError):
            self.execute(fail, child)
        self.assertEqual(calls, [1])
        self.assertEqual(child.pending, {'attempt-DEV-001'})
        self.assertEqual(child.accounted(), run.BOUND)


if __name__ == '__main__':
    unittest.main()
