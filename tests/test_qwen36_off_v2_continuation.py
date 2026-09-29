"""Offline synthetic continuation; no live OpenRouter request or allocation."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'tests'))
import qwen36_off_v2_continuation as continuation
import qwen36_off_fresh_repeat_execution_v2 as original
import qwen36_off_fresh_repeat_admission as admission
import build_additional_hosted_fresh_repeat_findings as report
from test_additional_hosted_fresh_repeat_findings import SeriesFixture, write_json, write_rows


class ContinuationFixture:
    def __init__(self, case):
        self.temp = tempfile.TemporaryDirectory(dir=REPO)
        case.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.series = SeriesFixture(report.SPECS[0], self.root, '0.15')
        self.series.stage(0, 'smoke')
        self.series.stage(0, 'development')
        self.base = self.series.base
        self.suffix = self.base / 'never-sent-suffix-v1'
        self.suffix.mkdir()
        controller = self.root / 'scripts/qwen36_off_v2_continuation.py'
        shutil.copy2(REPO / 'scripts/qwen36_off_v2_continuation.py', controller)
        self.controller = controller
        self.secret = 'user_id=PRIVATE_SYNTHETIC_ACCOUNT'
        raw_path = self.base / 'phase-01-development.raw.jsonl'
        rec_path = self.base / 'phase-01-development.records.jsonl'
        journal_path = self.base / 'phase-01-development.journal.jsonl'
        raw = [json.loads(line) for line in raw_path.read_text().splitlines()][:6]
        records = [json.loads(line) for line in rec_path.read_text().splitlines()][:6]
        journal = [json.loads(line) for line in journal_path.read_text().splitlines()]
        raw[5] = {'id': 'DEV-006', 'attempt_id': records[5]['attempt_id'],
                  'error_body': self.secret}
        records[5].update(status='service_error', http_status=429,
                          error_type='HTTPError', raw_error_response=self.secret,
                          observed_cost_usd=None, cost_unknown=True, billing_ok=False)
        for key in ('raw_response', 'prediction', 'usage', 'returned_model',
                    'returned_provider', 'finish_reason'):
            records[5].pop(key, None)
        write_rows(raw_path, raw)
        write_rows(rec_path, records)
        write_rows(journal_path, journal[:16] + [journal[16],
            {'event': 'request_finished', 'attempt_id': records[5]['attempt_id'],
             'id': 'DEV-006', 'status': 'service_error', 'billing_ok': False}])
        ledger_path = self.series.ledger
        ledger = [json.loads(line) for line in ledger_path.read_text().splitlines()]
        ledger = ledger[:19]
        ledger[-1] = {'event': 'unknown_cost_accounted_as_upper_bound',
                      'attempt_id': records[5]['attempt_id'], 'usd': str(admission.RESERVE),
                      'actual_cost_usd': None, 'reason': 'synthetic HTTP429',
                      'evidence_path': str(rec_path), 'evidence_sha256': continuation.sha(rec_path)}
        write_rows(ledger_path, ledger)
        budget_path = self.base / 'budget.json'
        budget = json.loads(budget_path.read_text())
        budget['master_ledger'] = str(self.root / 'results/openrouter-paid-budget.jsonl')
        budget['partitions'][0]['child_ledger'] = str(ledger_path)
        write_json(budget_path, budget)
        for stage in ('smoke', 'development'):
            stem = self.base / f'phase-01-{stage}'
            review_path = Path(str(stem) + '.root-review.json')
            claim_path = Path(str(stem) + '.claim.json')
            stage_journal = Path(str(stem) + '.journal.jsonl')
            review = json.loads(review_path.read_text())
            review['budget_manifest_sha256'] = continuation.sha(budget_path)
            write_json(review_path, review)
            claim = json.loads(claim_path.read_text())
            claim['budget_manifest_sha256'] = continuation.sha(budget_path)
            claim['review_sha256'] = continuation.sha(review_path)
            write_json(claim_path, claim)
            stage_events = [json.loads(line) for line in stage_journal.read_text().splitlines()]
            stage_events[0]['claim_sha256'] = continuation.sha(claim_path)
            write_rows(stage_journal, stage_events)
        development_review_path = self.base / 'phase-01-development.root-review.json'
        development_review = json.loads(development_review_path.read_text())
        for part in ('records', 'journal', 'raw'):
            development_review['smoke_inspection']['smoke_' + part + '_sha256'] = continuation.sha(
                self.base / f'phase-01-smoke.{part}.jsonl')
        write_json(development_review_path, development_review)
        development_claim_path = self.base / 'phase-01-development.claim.json'
        development_claim = json.loads(development_claim_path.read_text())
        development_claim['review_sha256'] = continuation.sha(development_review_path)
        write_json(development_claim_path, development_claim)
        development_events = [json.loads(line) for line in journal_path.read_text().splitlines()]
        development_events[0]['claim_sha256'] = continuation.sha(development_claim_path)
        write_rows(journal_path, development_events)
        self.patches = [patch.object(continuation, 'ROOT', self.root),
                        patch.object(continuation, 'BASE', self.base),
                        patch.object(continuation, 'SUFFIX', self.suffix),
                        patch.object(continuation, 'PARTITION', self.series.partition['id']),
                        patch.object(continuation, '__file__', str(controller)),
                        patch.object(original, 'ROOT', self.root),
                        patch.object(admission, 'MASTER', self.root / 'results/openrouter-paid-budget.jsonl'),
                        patch.object(admission, 'INPUTS', self.root / 'results/data/development-inputs.jsonl')]
        # SeriesFixture copies the source path recorded by the original plan.
        self.patches[-1] = patch.object(admission, 'INPUTS', self.root /
            admission.INPUTS.relative_to(REPO))
        for item in self.patches:
            item.start()
            case.addCleanup(item.stop)
        self.manifest_path = self.suffix / 'manifest.json'
        continuation.freeze(self.manifest_path)
        self.manifest_sha = continuation.sha(self.manifest_path)
        self.review_path = self.suffix / 'root-review.json'
        manifest = json.loads(self.manifest_path.read_text())
        write_json(self.review_path, {'schema': continuation.SCHEMA + '-root-review',
            'approved': True, 'manifest_sha256': self.manifest_sha,
            'controller_sha256': manifest['controller']['sha256'],
            'budget_manifest_sha256': continuation.sha(self.base / 'budget.json'),
            'original_review_sha256': manifest['sources']['development_review']['sha256'],
            'partition_id': continuation.PARTITION, 'request_ids': continuation.IDS,
            'failed_id_retained': 'DEV-006', 'cooldown_note': 'synthetic reviewed cooldown',
            'cooldown_not_before_utc': '2026-01-01T00:00:00Z'})

    def close(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def add_suffix(self, count, outcome='ok', http_status=429):
        manifest = json.loads(self.manifest_path.read_text())
        files = continuation.files()
        write_json(files['claim'], {'schema': continuation.SCHEMA + '-claim',
            'manifest_sha256': self.manifest_sha,
            'review_sha256': continuation.sha(self.review_path),
            'budget_manifest_sha256': continuation.sha(self.base / 'budget.json'),
            'partition_id': continuation.PARTITION, 'request_ids': continuation.IDS})
        journal = [{'event': 'suffix_claimed', 'claim_sha256': continuation.sha(files['claim'])}]
        raw, records, ledger = [], [], [json.loads(line) for line in self.series.ledger.read_text().splitlines()]
        for index, item in enumerate(manifest['requests'][:count]):
            rid = item['id']
            attempt = f'suffix-{index}'
            prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                          'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
            invalid = outcome == 'invalid_output' and index == count - 1
            failure = outcome == 'service_error' and index == count - 1
            body = {'model': admission.MODEL, 'provider': 'AkashML',
                    'usage': {'cost': '0.0001', 'prompt_tokens': 10,
                              'completion_tokens': 5, 'total_tokens': 15},
                    'choices': [{'message': {'content': '{invalid' if invalid else json.dumps(prediction)},
                                 'finish_reason': 'stop'}]}
            sidecar = ({'id': rid, 'attempt_id': attempt, 'error_body': self.secret,
                        'transport_error': 'HTTPError', 'http_status': http_status} if failure else
                       {'id': rid, 'attempt_id': attempt, 'body': body})
            raw.append(sidecar)
            row = {'id': rid, 'attempt_id': attempt, 'request': item['payload'],
                   'request_sha256': item['request_sha256'], 'input_sha256': item['input_sha256'],
                   'policy_sha256': item['instruction_sha256'],
                   'reference_labels_read': False, 'requested_model': admission.MODEL,
                   'reasoning_effort': 'off', 'provider_endpoint':
                       {'tag': admission.PROVIDER, 'provider_name': 'AkashML'},
                   'budget_partition_id': continuation.PARTITION,
                   'reserved_cost_usd': str(admission.RESERVE),
                   'client_request_started_utc': '2026-09-29T00:00:00+00:00',
                   'client_request_finished_utc': '2026-09-29T00:00:01+00:00',
                   'client_http_duration_seconds': 0.25,
                   'status': 'service_error' if failure else 'invalid_output' if invalid else 'ok',
                   'observed_cost_usd': None if failure else '0.0001',
                   'cost_unknown': failure, 'billing_ok': not failure}
            if failure:
                row.update(error_type='HTTPError', http_status=http_status,
                           raw_error_response=self.secret)
            else:
                row.update(raw_response=body, usage=body['usage'],
                           prediction=None if invalid else prediction,
                           returned_model=admission.MODEL, returned_provider='AkashML',
                           finish_reason='stop')
            records.append(row)
            journal.extend(({'event': 'request_started', 'attempt_id': attempt, 'id': rid,
                             'request_sha256': item['request_sha256'],
                             'reserved_cost_usd': str(admission.RESERVE)},
                            {'event': 'raw_saved', 'attempt_id': attempt, 'raw_sha256': ''},
                            {'event': 'request_finished', 'attempt_id': attempt, 'id': rid,
                             'status': row['status'], 'billing_ok': row['billing_ok']}))
            ledger.append({'event': 'reserve', 'attempt_id': attempt,
                           'record_id': rid, 'usd': str(admission.RESERVE)})
            if not failure:
                ledger.append({'event': 'settle', 'attempt_id': attempt, 'usd': '0.0001'})
        write_rows(files['raw'], raw)
        import hashlib
        lines = files['raw'].read_bytes().splitlines(keepends=True)
        for index in range(count):
            journal[2 + 3 * index]['raw_sha256'] = hashlib.sha256(b''.join(lines[:index + 1])).hexdigest()
        journal.append({'event': 'suffix_completed', 'count': len(continuation.IDS)}
                       if count == len(continuation.IDS) and outcome == 'ok' else
                       {'event': 'suffix_stopped', 'id': records[-1]['id'],
                        'reason': records[-1]['status']})
        write_rows(files['journal'], journal)
        write_rows(files['records'], records)
        if outcome == 'service_error':
            ledger.append({'event': 'unknown_cost_accounted_as_upper_bound',
                'attempt_id': records[-1]['attempt_id'], 'usd': str(admission.RESERVE),
                'actual_cost_usd': None, 'reason': 'synthetic failure',
                'evidence_path': str(files['records']),
                'evidence_sha256': continuation.sha(files['records'])})
        write_rows(self.series.ledger, ledger)
        return files


class QwenContinuationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ContinuationFixture(self)

    def test_real_frozen_request_reconstruction_and_original_six(self):
        manifest = continuation.validate_manifest(self.fixture.manifest_path,
                                                  self.fixture.manifest_sha)
        self.assertEqual(54, len(manifest['requests']))
        self.assertEqual('DEV-007', manifest['requests'][0]['id'])
        self.assertEqual('DEV-060', manifest['requests'][-1]['id'])
        result = continuation.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        self.assertEqual('not_started', result['status'])
        self.assertEqual({'ok': 5, 'service_error': 1, 'never_sent': 54}, result['status_counts'])
        self.assertEqual('0.0299008', result['unknown_charge_upper_bound_usd'])
        self.assertNotIn(self.fixture.secret, json.dumps(result))

    def test_closed_suffix_is_59_valid_one_error_and_public_projection_is_sanitized(self):
        self.fixture.add_suffix(54)
        result = continuation.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        self.assertEqual('closed_with_service_error', result['status'])
        self.assertEqual(59, result['valid'])
        self.assertEqual({'ok': 59, 'service_error': 1}, result['status_counts'])
        self.assertEqual('0.0062', result['known_actual_usd'])
        self.assertEqual('0.0299008', result['unknown_charge_upper_bound_usd'])
        self.assertEqual({'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
                         result['positions'][6]['usage'])
        self.assertNotIn(self.fixture.secret, json.dumps(result))
        self.assertIn('sha256', result['evidence']['raw'])

    def test_stopped_http429_and_billed_invalid_are_unscored(self):
        self.fixture.add_suffix(2, 'service_error')
        result = continuation.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        self.assertEqual('stopped', result['status'])
        self.assertIsNone(result['valid'])
        self.assertEqual(52, result['status_counts']['never_sent'])
        self.assertEqual('0.0598016', result['unknown_charge_upper_bound_usd'])
        self.assertNotIn(self.fixture.secret, json.dumps(result))

    def test_stopped_http503_keeps_remaining_never_sent(self):
        self.fixture.add_suffix(1, 'service_error', http_status=503)
        result = continuation.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        self.assertEqual('stopped', result['status'])
        self.assertEqual(503, result['positions'][6]['http_status'])
        self.assertEqual(53, result['status_counts']['never_sent'])
        self.assertNotIn(self.fixture.secret, json.dumps(result))

    def test_billed_invalid_stops_without_turning_the_phase_into_a_closed_score(self):
        self.fixture.add_suffix(2, 'invalid_output')
        result = continuation.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        self.assertEqual('stopped', result['status'])
        self.assertIsNone(result['valid'])
        self.assertEqual(1, result['status_counts']['invalid_output'])
        self.assertEqual(52, result['status_counts']['never_sent'])
        self.assertEqual('0.0001', result['positions'][7]['observed_cost_usd'])
        self.assertEqual('0.0299008', result['unknown_charge_upper_bound_usd'])

    def test_overreserve_known_charge_is_billing_blocked(self):
        files = self.fixture.add_suffix(1, 'invalid_output')
        rec = [json.loads(line) for line in files['records'].read_text().splitlines()]
        rec[0]['status'] = 'billing_blocked'
        rec[0]['billing_ok'] = False
        rec[0]['observed_cost_usd'] = '0.0300000'
        rec[0]['raw_response']['usage']['cost'] = '0.0300000'
        rec[0]['usage']['cost'] = '0.0300000'
        write_rows(files['records'], rec)
        raw = [json.loads(line) for line in files['raw'].read_text().splitlines()]
        raw[0]['body']['usage']['cost'] = '0.0300000'
        write_rows(files['raw'], raw)
        events = [json.loads(line) for line in files['journal'].read_text().splitlines()]
        events[2]['raw_sha256'] = continuation.sha(files['raw'])
        events[3]['status'] = 'billing_blocked'
        events[3]['billing_ok'] = False
        events[4]['reason'] = 'billing_blocked'
        write_rows(files['journal'], events)
        ledger = [json.loads(line) for line in self.fixture.series.ledger.read_text().splitlines()]
        ledger[-1]['usd'] = '0.0300000'
        ledger.append({'event': 'blocked', 'reason': 'Actual cost exceeds reserved bound'})
        write_rows(self.fixture.series.ledger, ledger)
        result = continuation.reconcile(self.fixture.manifest_path, self.fixture.manifest_sha)
        self.assertEqual('stopped', result['status'])
        self.assertEqual('billing_blocked', result['positions'][6]['status'])
        self.assertEqual('0.0300000', result['positions'][6]['observed_cost_usd'])

    def test_source_drift_and_missing_full_bound_fail_before_key(self):
        with patch.object(continuation.paid, 'load_key') as key:
            records = self.fixture.base / 'phase-01-development.records.jsonl'
            data = records.read_bytes()
            records.write_bytes(data + b'\n')
            with self.assertRaises(ValueError):
                continuation.execute(self.fixture.manifest_path, self.fixture.manifest_sha,
                                     self.fixture.review_path, self.fixture.base / 'budget.json')
            records.write_bytes(data)
            ledger = self.fixture.series.ledger
            original_data = ledger.read_bytes()
            ledger.write_bytes(b'\n'.join(original_data.splitlines()[:-1]) + b'\n')
            with self.assertRaises(ValueError):
                continuation.execute(self.fixture.manifest_path, self.fixture.manifest_sha,
                                     self.fixture.review_path, self.fixture.base / 'budget.json')
            ledger.write_bytes(original_data)
            key.assert_not_called()

    def test_duplicate_claim_and_route_drift_fail_before_key(self):
        with patch.object(continuation.paid, 'load_key') as key:
            continuation.files()['claim'].write_text('{}')
            with self.assertRaises(FileExistsError):
                continuation.execute(self.fixture.manifest_path, self.fixture.manifest_sha,
                                     self.fixture.review_path, self.fixture.base / 'budget.json')
            continuation.files()['claim'].unlink()
            _, _, endpoint, model = admission.source_state()
            changed = {**endpoint, 'tag': 'different/fp8'}
            with (patch.object(continuation.paid, 'fetch', return_value={}),
                  patch.object(continuation.paid, 'select_endpoint', return_value=(model, changed))):
                with self.assertRaisesRegex(ValueError, 'Live route'):
                    continuation.execute(self.fixture.manifest_path, self.fixture.manifest_sha,
                                         self.fixture.review_path, self.fixture.base / 'budget.json')
            key.assert_not_called()

    def run_cap_stop(self, allowed):
        fixture = self.fixture
        _, _, endpoint, model = admission.source_state()
        class LimitedLedger:
            closed = False
            def __init__(self):
                self.count = 0
            def state(self):
                return {}, set(), False
            def reserve(self, amount, rid):
                if self.count >= allowed:
                    raise ValueError('Aggregate $0.15 cap reached')
                self.count += 1
                attempt = f'cap-{self.count}'
                with fixture.series.ledger.open('a') as out:
                    out.write(json.dumps({'event': 'reserve', 'attempt_id': attempt,
                        'record_id': rid, 'usd': str(amount)}) + '\n')
                return attempt
            def settle(self, attempt, actual):
                with fixture.series.ledger.open('a') as out:
                    out.write(json.dumps({'event': 'settle', 'attempt_id': attempt,
                        'usd': str(actual)}) + '\n')
                return True
            def close(self):
                pass
        body = {'model': admission.MODEL, 'provider': 'AkashML',
            'usage': {'cost': '0.0001', 'prompt_tokens': 10,
                'completion_tokens': 5, 'total_tokens': 15},
            'choices': [{'message': {'content': json.dumps({'sentiment': 'neutral',
                'follow_up_needed': 'no', 'serious_concern_reported': 'no',
                'testimonial_potential': 'no'})}, 'finish_reason': 'stop'}]}
        with (patch.object(continuation, 'live_controls', return_value=(model, endpoint)),
              patch.object(continuation.partitions, 'open_partition', return_value=LimitedLedger()),
              patch.object(continuation.paid, 'load_key', return_value='synthetic-token'),
              patch.object(continuation.paid, 'fetch', return_value=body) as transport):
            result = continuation.execute(fixture.manifest_path, fixture.manifest_sha,
                fixture.review_path, fixture.base / 'budget.json')
        self.assertEqual('child_cap', result['status'])
        self.assertEqual(f'DEV-{7 + allowed:03d}', result['next_unsent_id'])
        self.assertEqual(allowed, transport.call_count)
        reconciled = continuation.reconcile(fixture.manifest_path, fixture.manifest_sha)
        self.assertEqual('admission_stopped', reconciled['status'])
        self.assertIsNone(reconciled['valid'])
        self.assertEqual(54 - allowed, reconciled['status_counts']['never_sent'])

    def test_child_cap_stops_before_first_http(self):
        self.run_cap_stop(0)

    def test_child_cap_stops_after_one_without_sending_the_next(self):
        self.run_cap_stop(1)


if __name__ == '__main__':
    unittest.main()
