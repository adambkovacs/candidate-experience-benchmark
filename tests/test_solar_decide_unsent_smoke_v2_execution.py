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
import openrouter_budget_v4 as budget_v4
from development_benchmark import KEYS, VALUES


def temp_child(path):
    child = budget_v4.BudgetLedger(path, cap_limit=run.CAP)
    child.master_cap = budget_v4.CAP
    return child


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
            child_path = Path(temp) / 'child.jsonl'
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
                  mock.patch.object(run.partitions, 'open_partition',
                                    side_effect=lambda *args: temp_child(child_path)),
                  mock.patch.object(run, 'load_key', return_value='test-token')):
                self.assertTrue(run.execute(send=send))
                rows = run.jsonl(Path(temp) / 'smoke.raw.jsonl')
                self.assertEqual([row['id'] for row in rows], ['DEV-002','DEV-003'])
                self.assertEqual(len(payloads), 2)
                self.assertEqual(len(run.jsonl(Path(temp) / 'smoke.parsed.jsonl')), 2)
                events = run.jsonl(child_path)
                self.assertEqual([event['event'] for event in events],
                                 ['budget','reserve','settle','reserve','settle'])
                self.assertEqual([event['usd'] for event in events if event['event']=='settle'],
                                 ['0.000005']*2)
                with self.assertRaises(FileExistsError):
                    run.execute(send=send)

    def test_mocked_429_keeps_unknown_and_second_unsent(self):
        with tempfile.TemporaryDirectory() as temp:
            child_path = Path(temp) / 'child.jsonl'
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
                  mock.patch.object(run.partitions, 'open_partition',
                                    side_effect=lambda *args: temp_child(child_path)),
                  mock.patch.object(run, 'load_key', return_value='test-token')):
                self.assertFalse(run.execute(send=send))
                rows = run.jsonl(Path(temp) / 'smoke.attempts.jsonl')
                self.assertEqual([(row['id'],row['status']) for row in rows],
                                 [('DEV-002','unknown_cost')])
                self.assertEqual(len(calls), 1)
                events = run.jsonl(child_path)
                self.assertEqual([event['event'] for event in events], ['budget','reserve'])
                self.assertEqual(events[1]['record_id'], 'DEV-002')
                self.assertEqual(events[1]['usd'], str(run.BOUND))

    def test_bound_money_and_key_sources_reject_drift(self):
        saved = json.loads(run.MANIFEST.read_text())
        for name in ('scripts/openrouter_budget_amendment_v3.py',
                     'scripts/openrouter_benchmark.py',
                     'scripts/development_benchmark.py'):
            self.assertEqual(saved['source_sha256'][name], run.sha(ROOT / name))
            changed = json.loads(json.dumps(saved))
            changed['source_sha256'][name] = '0'*64
            with tempfile.TemporaryDirectory() as temp:
                changed_path = Path(temp) / 'manifest.json'
                changed_path.write_text(json.dumps(changed))
                with mock.patch.object(run, 'MANIFEST', changed_path):
                    with self.assertRaises(ValueError):
                        run.verify()


if __name__ == '__main__':
    unittest.main()
