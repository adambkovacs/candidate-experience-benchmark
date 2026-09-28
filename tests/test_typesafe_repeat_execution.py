import copy
import os
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import typesafe_repeat_execution as execution
import typesafe_repeat_study as study
import jev_native_prompt_variants_v1 as native


class FakeResponse:
    def __init__(self, body, endpoint=execution.ENDPOINT):
        self.body = body
        self.endpoint = endpoint
        self.status = 200
    def read(self, size):
        return self.body[:size]
    def geturl(self):
        return self.endpoint
    def close(self):
        pass


class FakeOpener:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.calls = []
    def open(self, request, timeout):
        self.calls.append(request)
        return FakeResponse(self.bodies.pop(0))


class JevExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_ledger = native.LEDGER
        cls.plan = study.plan()
        cls.manifest, _ = native.read_frozen_manifest(study.BASE / 'input-only-manifest.json')
        cls.good = json.loads((study.BASE / 'P1-smoke.jsonl').read_text().splitlines()[0])['raw_response']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = self.root / 'ledger.jsonl'
        self.ledger.write_bytes(native.LEDGER.read_bytes())
        self.frozen = self.root / 'frozen.json'
        self.frozen.write_text('{}')
        self.review = self.root / 'review.json'
        self.base = self.root / 'runs'
        self.patches = [mock.patch.object(native, 'LEDGER', self.ledger),
                        mock.patch.object(execution, 'load_frozen', return_value={'plan': self.plan}),
                        mock.patch.object(execution, 'price_preflight', return_value='price-hash'),
                        mock.patch.object(execution, 'load_key', return_value='fake-token')]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def reviewed(self, stage=0, start=0, phase='smoke'):
        value = {'kind': 'typesafe-repeat-phase-review-v1',
                 'frozen_sha256': execution.file_sha(self.frozen),
                 'controller_sha256': execution.file_sha(execution.__file__),
                 'repeat': 'repeat2', 'condition': 'P1', 'phase': phase,
                 'stage': stage, 'start_index': start,
                 'price_page_sha256': 'price-hash', 'reviewed': True}
        self.review.write_text(json.dumps(value))

    def run_smoke(self, bodies, stage=0):
        opener = FakeOpener(bodies)
        result = execution.run_stage(frozen_path=self.frozen, phase_review=self.review,
                                     repeat='repeat2', condition='P1', phase='smoke',
                                     stage=stage, base=self.base, opener=opener)
        return result, opener

    def test_no_review_no_key_or_dispatch(self):
        opener = FakeOpener([])
        with mock.patch.object(execution, 'load_key', side_effect=AssertionError('key read')):
            with self.assertRaises(FileNotFoundError):
                execution.run_stage(frozen_path=self.frozen, phase_review=self.review,
                                    repeat='repeat2', condition='P1', phase='smoke',
                                    base=self.base, opener=opener)
        self.assertFalse(opener.calls)

    def test_price_change_blocks_before_key_or_claim(self):
        self.reviewed()
        with mock.patch.object(execution, 'price_preflight', return_value='changed-price'):
            with mock.patch.object(execution, 'load_key', side_effect=AssertionError('key read')):
                with self.assertRaisesRegex(ValueError, 'Review receipt'):
                    self.run_smoke([])
        self.assertFalse(execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['claim.json'].exists())

    def test_timeout_override_is_rejected_before_key_or_claim(self):
        self.reviewed()
        with mock.patch.object(execution, 'load_key', side_effect=AssertionError('key read')):
            with self.assertRaisesRegex(ValueError, 'Invalid stage or timeout'):
                execution.run_stage(frozen_path=self.frozen, phase_review=self.review,
                                    repeat='repeat2', condition='P1', phase='smoke',
                                    base=self.base, timeout=121, opener=FakeOpener([]))
        self.assertFalse(execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['claim.json'].exists())

    def test_success_raw_precedes_row_and_replay_claim_fails(self):
        self.reviewed()
        raw = json.dumps(self.good).encode()
        result, opener = self.run_smoke([raw] * 3)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(opener.calls), 3)
        self.assertTrue(all(b'proposed_labels' not in req.data for req in opener.calls))
        paths = execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)
        rows = execution.read_lines(paths['attempts.jsonl'])
        self.assertEqual([r['status'] for r in rows], ['ok'] * 3)
        for row in rows:
            evidence = json.loads((paths['claim.json'].parent / row['raw_path']).read_text())
            self.assertEqual(hashlib.sha256(__import__('base64').b64decode(evidence['raw_base64'])).hexdigest(), row['raw_sha256'])
            self.assertEqual(os.stat(paths['claim.json'].parent / row['raw_path']).st_mode & 0o777, 0o600)
            self.assertIsNone(row['actual_charge_usd'])
            self.assertIsNone(row['provider_inference_seconds'])
            self.assertEqual(row['request_timeout_seconds'], 120)
            self.assertIs(row['reference_labels_read'], False)
        with self.assertRaisesRegex(ValueError, 'claimed'):
            self.run_smoke([raw] * 3)

    def test_reflected_token_is_redacted_from_durable_evidence(self):
        self.reviewed()
        body = dict(self.good, echoed_secret='fake-token')
        result, _ = self.run_smoke([json.dumps(body).encode()] * 3)
        self.assertEqual(result['status'], 'complete')
        folder = execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['claim.json'].parent
        for path in folder.iterdir():
            self.assertNotIn(b'fake-token', path.read_bytes())
        rows = execution.read_lines(execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['attempts.jsonl'])
        self.assertTrue(all(row['token_redacted'] for row in rows))

    def test_unknown_cost_holds_reservation_and_blocks_continuation(self):
        self.reviewed()
        result, opener = self.run_smoke([b'{"error":"rate limited"}'])
        self.assertEqual(result['reason'], 'cost_unknown')
        self.assertEqual(len(opener.calls), 1)
        rows = execution.read_lines(execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['attempts.jsonl'])
        self.assertTrue(rows[0]['cost_unknown'])
        self.assertEqual(rows[0]['status'], 'identity_violation')
        self.assertEqual(len(execution.pending_ids(execution.read_lines(self.ledger))), 2)
        self.reviewed(stage=1, start=1)
        with self.assertRaisesRegex(ValueError, 'Only contiguous|Unreviewed pending'):
            self.run_smoke([json.dumps(self.good).encode()], stage=1)

    def test_model_mismatch_stops_and_settles_reported_usage(self):
        self.reviewed()
        wrong = dict(self.good, model='other-version')
        result, _ = self.run_smoke([json.dumps(wrong).encode()])
        self.assertEqual(result['reason'], 'identity_violation')
        row = execution.read_lines(execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['attempts.jsonl'])[0]
        self.assertEqual(row['status'], 'identity_violation')
        self.assertEqual(row['estimated_usage_cost_usd'], str(execution.usage_cost(wrong)))

    def test_above_bound_records_full_estimate_and_stops(self):
        self.reviewed()
        costly = copy.deepcopy(self.good)
        costly['usage']['input_tokens'] = 100_000_000
        result, _ = self.run_smoke([json.dumps(costly).encode()])
        self.assertEqual(result['reason'], 'above_reservation')
        row = execution.read_lines(execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)['attempts.jsonl'])[0]
        self.assertEqual(Decimal(row['estimated_usage_cost_usd']), Decimal('4.2'))
        self.assertEqual(Decimal(execution.read_lines(self.ledger)[-1]['usd']), Decimal('4.2'))

    def test_interrupted_started_attempt_cannot_be_replayed(self):
        paths = execution.stage_paths(self.base, 'repeat2', 'P1', 'smoke', 0)
        execution.exclusive_json(paths['claim.json'], {'start_index': 0})
        paths['journal.jsonl'].write_text(json.dumps({'event': 'started', 'id': 'DEV-001'}) + '\n')
        paths['attempts.jsonl'].write_text('')
        self.reviewed(stage=1, start=0)
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            self.run_smoke([json.dumps(self.good).encode()], stage=1)

    def test_reviewed_continuation_starts_at_next_never_sent_development_id(self):
        paths = execution.stage_paths(self.base, 'repeat2', 'P1', 'development', 0)
        execution.exclusive_json(paths['claim.json'], {'start_index': 0})
        raw = b'failed response'
        raw_sha = execution.sha(raw)
        raw_name = 'development-000-DEV-001.raw.json'
        execution.exclusive_json(paths['claim.json'].parent / raw_name,
                                 {'attempt_id': 'old', 'request_sha256': 'old-request',
                                  'raw_base64': __import__('base64').b64encode(raw).decode()})
        paths['journal.jsonl'].write_text(''.join(json.dumps(event) + '\n' for event in [
            {'event': 'started', 'id': 'DEV-001', 'attempt_id': 'old', 'request_sha256': 'old-request'},
            {'event': 'finished', 'id': 'DEV-001', 'attempt_id': 'old',
             'status': 'service_error', 'raw_sha256': raw_sha},
            {'event': 'terminal', 'status': 'stopped', 'reason': 'service_error'}]))
        paths['attempts.jsonl'].write_text(json.dumps({'id': 'DEV-001', 'status': 'service_error',
                                                       'budget_attempt_id': 'old',
                                                       'request_sha256': 'old-request',
                                                       'raw_sha256': raw_sha, 'raw_path': raw_name}) + '\n')
        self.reviewed(stage=1, start=1, phase='development')
        with mock.patch.object(execution, 'previous_gate'):
            opener = FakeOpener([json.dumps(self.good).encode()] * 59)
            result = execution.run_stage(frozen_path=self.frozen, phase_review=self.review,
                                         repeat='repeat2', condition='P1', phase='development',
                                         stage=1, base=self.base, opener=opener)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(opener.calls), 59)
        rows = execution.read_lines(execution.stage_paths(self.base, 'repeat2', 'P1', 'development', 1)['attempts.jsonl'])
        self.assertEqual([r['id'] for r in rows], study.IDS[1:])

    def test_unknown_pending_from_other_attempt_blocks_admission(self):
        with self.ledger.open('a') as out:
            out.write(json.dumps({'event': 'reserve', 'attempt_id': 'new-unknown',
                                  'record_id': 'DEV-001', 'usd': '0.001'}) + '\n')
        self.reviewed()
        with mock.patch.object(execution, 'load_key', side_effect=AssertionError('key read')):
            with self.assertRaisesRegex(ValueError, 'Unreviewed pending'):
                self.run_smoke([])

    def test_freeze_requires_exact_current_draft_and_review(self):
        with mock.patch.object(native, 'LEDGER', self.original_ledger):
            real = study.plan()
        draft = self.root / 'draft.json'
        draft.write_bytes(execution.json_bytes(real))
        review = self.root / 'freeze-review.json'
        review.write_text(json.dumps({'kind': 'typesafe-repeat-freeze-review-v1',
                                      'draft_sha256': execution.file_sha(draft),
                                      'controller_sha256': execution.file_sha(execution.__file__),
                                      'reviewed': True}))
        with mock.patch.object(native, 'LEDGER', self.original_ledger):
            with mock.patch.object(execution.study, 'plan', return_value=real):
                frozen = execution.freeze(draft, review, self.root / 'actual-frozen.json')
        self.assertEqual(frozen['draft_sha256'], execution.file_sha(draft))
        with self.assertRaises(FileExistsError):
            with mock.patch.object(execution.study, 'plan', return_value=real):
                execution.freeze(draft, review, self.root / 'actual-frozen.json')


if __name__ == '__main__':
    unittest.main()
