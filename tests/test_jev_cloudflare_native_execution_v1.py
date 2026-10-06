from decimal import Decimal
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from development_benchmark import KEYS, VALUES
import clef_native_remaining_cloudflare_v1 as clef
import jev_cloudflare_native_execution_v1 as execution
import jev_cloudflare_native_preparation_v1 as prep


ACCOUNT = 'a' * 32
PRICE_PAGE = b'<html>typesafe/jev 32,000 tokens $0.042 per 1M input</html>'


def saved_envelope(version='jev-1.13.0'):
    answers = {}
    for field in KEYS:
        labels = VALUES[field]
        answers[field] = {'type': 'choice', 'choice': labels[0],
                          'confidence': 0.8,
                          'probabilities': {label: int(label == labels[0])
                                            for label in labels}}
    provider = {'status': 200, 'success': True, 'errors': [], 'messages': [],
                'result': {'model': version, 'answers': answers,
                           'usage': {'input_tokens': 500, 'output_tokens': 40}}}
    return {'content': [{'type': 'text', 'text': json.dumps(provider)}]}


class JevCloudflareNativeExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'jev'
        self.authority = Path(self.temp.name) / 'authority.jsonl'
        self.plan, self.plan_hash = prep.checked_plan(execution.PLAN)
        self.authority.write_text(json.dumps(clef.initial_header(
            clef.digest(clef.PLAN), 'b' * 64)) + '\n')

    def grant(self, repeat='fresh1', condition='P0', phase='smoke',
              prior_hash=None, smoke_review_hash=None):
        value = execution.grant_value(
            repeat, condition, phase, ACCOUNT, self.plan_hash,
            prep.sha(self.authority.read_bytes()), prep.sha(PRICE_PAGE),
            prior_hash, smoke_review_hash)
        path = Path(self.temp.name) / f'{repeat}-{condition}-{phase}-grant.json'
        path.write_text(json.dumps(value) + '\n')
        return path

    def admit(self, grant=None, repeat='fresh1', condition='P0', phase='smoke',
              smoke_review_path=None):
        return execution.admit(repeat, condition, phase,
            grant or self.grant(repeat, condition, phase), ACCOUNT,
            authority_path=self.authority, base=self.base,
            smoke_review_path=smoke_review_path,
            fetcher=lambda _: PRICE_PAGE)

    def prepare(self, directory):
        return execution.prepare(directory, ACCOUNT, base=self.base,
                                 authority_path=self.authority)

    def consume(self, ready, directory, original=None):
        request = directory / 'app-bridge' / f"{ready['attempt_id']}.request.json"
        execution.record_timing(request, 1_797_000_000_000, 1_797_000_000_025,
                                25, 'date_now_wall',
                                'outer_returned_original_saved' if original is not None
                                else 'outer_tool_exception',
                                base=self.base, authority_path=self.authority)
        if original is not None:
            execution.durable_file(request.with_name(
                ready['attempt_id'] + '.tool-result.original.json'), original)
        return execution.consume(request, base=self.base,
                                 authority_path=self.authority)

    def test_shared_cap_counts_clef_holds_and_rejects_overrun(self):
        with self.authority.open('a') as handle:
            handle.write(json.dumps({'event': 'hold', 'id': 'cloudflare-only-clef-unknown',
                'usd': '9.739', 'grant_sha256': 'c' * 64}) + '\n')
        grant = self.grant()
        with self.assertRaisesRegex(ValueError, 'cap exhausted'):
            self.admit(grant)
        self.assertEqual(len(execution.read_jsonl(self.authority)), 2)
        self.assertFalse(execution.stage_dir('fresh1', 'P0', 'smoke', self.base).exists())

    def test_admission_one_request_and_three_valid_smoke_closure(self):
        self.admit()
        directory = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        self.assertEqual(len(execution.read_jsonl(self.authority)), 2)
        for index in range(3):
            ready = self.prepare(directory)
            self.assertEqual(ready['id'], prep.SMOKE_IDS[index])
            self.assertEqual(ready['body']['model'], 'typesafe/jev')
            with self.assertRaisesRegex(ValueError, 'unresolved attempt'):
                self.prepare(directory)
            result = self.consume(ready, directory, saved_envelope())
            self.assertEqual(result['status'], 'valid')
        completion = execution.read_json(directory / 'completion.json')
        self.assertEqual(completion['status'], 'complete')
        self.assertEqual(completion['attempted'], 3)
        self.assertEqual(completion['counts']['valid'], 3)
        self.assertEqual(completion['never_sent'], [])
        records = execution.read_jsonl(directory / 'records.jsonl')
        self.assertEqual([record['id'] for record in records], list(prep.SMOKE_IDS))
        self.assertEqual(records[0]['published_input_cost_estimate_usd'], '0.000021')
        self.assertIsNone(records[0]['actual_charge_usd'])
        self.assertEqual(records[0]['client_mcp_round_trip_ms'], 25)
        raw = execution.read_jsonl(directory / 'raw.jsonl')[0]
        self.assertEqual(raw['provider_server_timing_status'], 'unavailable')
        self.assertIsNone(raw['provider_server_duration_ms'])
        self.assertEqual(raw['client_timing_scope'], 'client_mcp_round_trip')
        self.assertTrue(raw['started_at_utc'].endswith('Z'))
        self.assertTrue(raw['ended_at_utc'].endswith('Z'))
        self.assertTrue(all(record['reference_labels_read'] is False for record in records))
        self.assertEqual(Decimal(completion['stage_hold_usd']), prep.reservation_usd(3))
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.prepare(directory)

    def test_returned_version_drift_stops_and_retains_original(self):
        self.admit()
        directory = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        ready = self.prepare(directory)
        result = self.consume(ready, directory, saved_envelope('jev-1.14.0'))
        self.assertEqual(result['status'], 'service_error')
        self.assertEqual(result['stage_status'], 'stopped')
        self.assertEqual(execution.read_json(directory / 'completion.json')['never_sent'],
                         list(prep.SMOKE_IDS[1:]))
        record = execution.read_jsonl(directory / 'records.jsonl')[0]
        self.assertEqual(record['usage']['input_tokens'], 500)
        self.assertEqual(record['published_input_cost_estimate_usd'], '0.000021')
        self.assertIsNone(record['actual_charge_usd'])
        original_path = directory / 'app-bridge' / f"{ready['attempt_id']}.tool-result.original.json"
        self.assertTrue(original_path.exists())
        self.assertEqual(execution.read_jsonl(directory / 'raw.jsonl')[0]
                         ['original_tool_result_sha256'], prep.sha(original_path.read_bytes()))

    def test_provider_4006_stops_with_client_timing_and_unknown_charge(self):
        self.admit()
        directory = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        ready = self.prepare(directory)
        provider = {'status': 400, 'success': False,
                    'errors': [{'code': 4006, 'message': 'Daily quota exhausted'}],
                    'messages': [], 'result': None}
        result = self.consume(ready, directory,
                              {'content': [{'type': 'text', 'text': json.dumps(provider)}]})
        self.assertEqual(result['status'], 'service_error')
        self.assertEqual(result['stage_status'], 'stopped')
        record = execution.read_jsonl(directory / 'records.jsonl')[0]
        self.assertEqual(record['client_mcp_round_trip_ms'], 25)
        self.assertEqual(record['provider_server_timing_status'], 'unavailable')
        self.assertIsNone(record['provider_server_duration_ms'])
        self.assertEqual(record['charge_status'], 'unknown_reserved')
        self.assertEqual(execution.read_json(directory / 'completion.json')['never_sent'],
                         list(prep.SMOKE_IDS[1:]))

    def test_unknown_tool_exception_stops_without_replay(self):
        self.admit()
        directory = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        ready = self.prepare(directory)
        request = directory / 'app-bridge' / f"{ready['attempt_id']}.request.json"
        execution.record_timing(request, 1_797_000_000_000, 1_797_000_000_025,
                                25, 'date_now_wall', 'outer_tool_exception',
                                base=self.base, authority_path=self.authority)
        execution.mark_unknown(request, base=self.base, authority_path=self.authority)
        result = execution.consume(request, base=self.base,
                                   authority_path=self.authority)
        self.assertEqual(result['status'], 'unknown_outcome')
        self.assertEqual(result['stage_status'], 'stopped')
        with self.assertRaisesRegex(ValueError, 'terminal'):
            self.prepare(directory)
        self.assertEqual(len(execution.read_jsonl(self.authority)), 2)
        timing = execution.read_json(request.with_name(ready['attempt_id'] + '.timing.json'))
        self.assertEqual(timing['outcome'], 'outer_tool_exception')
        self.assertEqual(timing['client_mcp_round_trip_ms'], 25)

    def test_original_save_failure_keeps_timing_and_prevents_replay(self):
        self.admit()
        directory = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        ready = self.prepare(directory)
        request = directory / 'app-bridge' / f"{ready['attempt_id']}.request.json"
        execution.record_timing(request, 1_797_000_000_000, 1_797_000_000_025,
                                25, 'date_now_wall',
                                'outer_returned_original_save_failed',
                                base=self.base, authority_path=self.authority)
        timing = execution.read_json(request.with_name(ready['attempt_id'] + '.timing.json'))
        self.assertEqual(timing['outcome'], 'outer_returned_original_save_failed')
        self.assertEqual(timing['provider_server_timing_status'], 'unavailable')
        with self.assertRaisesRegex(ValueError, 'unresolved attempt'):
            self.prepare(directory)
        with self.assertRaisesRegex(ValueError, 'Exactly one original'):
            execution.consume(request, base=self.base, authority_path=self.authority)

    def test_saved_original_is_required_before_next_request(self):
        self.admit()
        directory = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        ready = self.prepare(directory)
        self.consume(ready, directory, saved_envelope())
        original = directory / 'app-bridge' / f"{ready['attempt_id']}.tool-result.original.json"
        original.unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'tool-result.original'):
            self.prepare(directory)
        self.assertEqual(len(execution.read_jsonl(directory / 'records.jsonl')), 1)

    def test_development_requires_exact_independent_smoke_review(self):
        grant = self.grant(phase='development')
        with self.assertRaisesRegex(ValueError, 'Smoke review required'):
            self.admit(grant, phase='development')
        self.assertEqual(len(execution.read_jsonl(self.authority)), 1)
        self.admit()
        smoke_dir = execution.stage_dir('fresh1', 'P0', 'smoke', self.base)
        for _ in range(3):
            ready = self.prepare(smoke_dir)
            self.consume(ready, smoke_dir, saved_envelope())
        completion_path = smoke_dir / 'completion.json'
        completion = execution.read_json(completion_path)
        review = {'kind': execution.KIND + '-smoke-review', 'approved': True,
                  'reviewer': '/root', 'stage': 'jev/fresh1/P0/smoke',
                  'plan_sha256': self.plan_hash,
                  'completion_sha256': prep.sha(completion_path.read_bytes()),
                  'raw_sha256': completion['raw_sha256'],
                  'records_sha256': completion['records_sha256'],
                  'decision': 'admit_unchanged_full_stage'}
        review_path = Path(self.temp.name) / 'smoke-review.json'
        review_path.write_text(json.dumps(review) + '\n')
        full_grant = self.grant(phase='development',
                                smoke_review_hash=prep.sha(review_path.read_bytes()))
        self.admit(full_grant, phase='development', smoke_review_path=review_path)
        full_dir = execution.stage_dir('fresh1', 'P0', 'development', self.base)
        full_ready = self.prepare(full_dir)
        self.assertEqual(full_ready['id'], 'DEV-001')
        self.assertEqual(len(execution.read_jsonl(self.authority)), 3)
        self.consume(full_ready, full_dir, saved_envelope())
        for _ in range(59):
            ready = self.prepare(full_dir)
            self.consume(ready, full_dir, saved_envelope())
        full_completion = execution.read_json(full_dir / 'completion.json')
        self.assertEqual(full_completion['status'], 'complete')
        self.assertEqual(full_completion['attempted'], 60)
        self.assertEqual(full_completion['counts']['valid'], 60)
        self.assertEqual(full_completion['never_sent'], [])
        self.assertEqual(len(execution.read_jsonl(self.authority)), 3)


if __name__ == '__main__':
    unittest.main()
