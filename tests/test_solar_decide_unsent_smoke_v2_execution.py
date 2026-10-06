import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import solar_decide_unsent_smoke_v2_execution as run
from development_benchmark import KEYS, VALUES


class FakeChild:
    cap = run.CAP
    master_cap = Decimal('22.38')
    closed = False

    def __init__(self):
        self.pending = {}
        self.costs = []
        self.closed_handle = False

    def state(self):
        return {}, set(self.pending), False

    def accounted(self):
        return sum(self.costs, Decimal(0)) + sum(self.pending.values(), Decimal(0))

    def reserve(self, amount, record_id):
        attempt = 'attempt-' + record_id
        self.pending[attempt] = amount
        return attempt

    def settle(self, attempt, amount):
        assert amount <= self.pending.pop(attempt)
        self.costs.append(amount)
        return True

    def close(self):
        self.closed_handle = True


def response():
    answers = {}
    for key in KEYS:
        chosen = VALUES[key][0]
        answers[key] = {'type': 'choice', 'choice': chosen,
            'probabilities': {value: 1.0 if value == chosen else 0.0 for value in VALUES[key]},
            'confidence': 1.0}
    return {'model': run.solar.VERSION, 'provider': run.solar.PROVIDER,
        'answers': answers,
        'usage': {'input_tokens': 100, 'output_tokens': 0, 'cost': 0.000005}}


class SolarUnsentExecutionTests(unittest.TestCase):
    def test_offline_manifest_requires_exact_two_and_risk_receipt(self):
        value = run.manifest_value()
        self.assertEqual(value['request_ids'], ['DEV-002', 'DEV-003'])
        self.assertEqual(value['per_request_reserve_usd'], '0.10485760')
        self.assertEqual(value['risk_hold_usd'], '0.07864320')
        self.assertEqual(run.verify(), run.sha(run.MANIFEST))

    def test_native_usage_uses_four_question_ceiling(self):
        body = response()
        body['usage']['input_tokens'] = run.solar.CONTEXT + 1
        body['usage']['cost'] = float(Decimal(body['usage']['input_tokens']) * run.solar.PROMPT_RATE)
        prediction, actual = run.validate_returned(body)
        self.assertEqual(set(prediction), set(KEYS))
        self.assertLessEqual(actual, run.BOUND)
        body['usage']['input_tokens'] = 4 * run.solar.CONTEXT + 1
        with self.assertRaises(ValueError):
            run.validate_returned(body)

    def test_mocked_two_request_success_and_no_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            child = FakeChild()
            payloads = []
            stage_review = Path(temp) / 'stage-review.json'
            stage_review.write_text('{}\n')
            def send(payload, token):
                payloads.append(payload)
                self.assertEqual(token, 'test-token')
                return 200, json.dumps(response()).encode()
            with (mock.patch.object(run, 'BASE', Path(temp)),
                  mock.patch.object(run, 'STAGE_REVIEW', stage_review),
                  mock.patch.object(run, 'require_stage_review'),
                  mock.patch.object(run, 'verify', return_value='checked'),
                  mock.patch.object(run, 'live_route', return_value=(b'{}', {})),
                  mock.patch.object(run.partitions, 'open_partition', return_value=child),
                  mock.patch.object(run, 'load_key', return_value='test-token')):
                self.assertTrue(run.execute(send=send))
                rows = run.jsonl(Path(temp) / 'smoke.raw.jsonl')
                self.assertEqual([row['id'] for row in rows], ['DEV-002','DEV-003'])
                self.assertEqual(len(payloads), 2)
                self.assertEqual(len(run.jsonl(Path(temp) / 'smoke.parsed.jsonl')), 2)
                self.assertEqual(child.costs, [Decimal('0.000005')]*2)
                self.assertTrue(child.closed_handle)
                with self.assertRaises(FileExistsError):
                    run.execute(send=send)

    def test_mocked_429_keeps_unknown_and_second_unsent(self):
        with tempfile.TemporaryDirectory() as temp:
            child = FakeChild()
            calls = []
            stage_review = Path(temp) / 'stage-review.json'
            stage_review.write_text('{}\n')
            def send(payload, token):
                calls.append(payload)
                return 429, b'{"error":{"type":"too_many_requests"}}'
            with (mock.patch.object(run, 'BASE', Path(temp)),
                  mock.patch.object(run, 'STAGE_REVIEW', stage_review),
                  mock.patch.object(run, 'require_stage_review'),
                  mock.patch.object(run, 'verify', return_value='checked'),
                  mock.patch.object(run, 'live_route', return_value=(b'{}', {})),
                  mock.patch.object(run.partitions, 'open_partition', return_value=child),
                  mock.patch.object(run, 'load_key', return_value='test-token')):
                self.assertFalse(run.execute(send=send))
                rows = run.jsonl(Path(temp) / 'smoke.attempts.jsonl')
                self.assertEqual([(row['id'],row['status']) for row in rows],
                                 [('DEV-002','unknown_cost')])
                self.assertEqual(len(calls), 1)
                self.assertEqual(child.pending, {'attempt-DEV-002': run.BOUND})
                self.assertTrue(child.closed_handle)


if __name__ == '__main__':
    unittest.main()
