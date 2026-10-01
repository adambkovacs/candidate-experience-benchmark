"""Offline gates for the stopped Gemma-on P2 continuation."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_v2_continuation as continuation


class Gemma26ContinuationTests(unittest.TestCase):
    def test_exact_stopped_prefix_and_pending_429(self):
        prefix = continuation.verify_stopped_prefix()
        self.assertEqual(prefix['prefix_ids'], [f'DEV-{i:03d}' for i in range(1, 8)])
        self.assertEqual(prefix['never_sent_ids'], [f'DEV-{i:03d}' for i in range(8, 61)])
        self.assertEqual(prefix['known_prefix_usd'], '0.00271628')
        self.assertEqual(len(continuation.STAGES), 13)
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            child = Path(temp) / 'pending-child.jsonl'
            lines = continuation.OLD_LEDGER.read_bytes().splitlines(keepends=True)
            original_prefix = b''.join(lines[:continuation.OLD_LEDGER_LINES])
            self.assertEqual(hashlib.sha256(original_prefix).hexdigest(), continuation.OLD_LEDGER_SHA)
            child.write_bytes(original_prefix)
            with patch.object(continuation, 'OLD_LEDGER', child):
                with self.assertRaisesRegex(ValueError, 'Failed reservation differs'):
                    continuation.verify_old_seal(ROOT / 'missing-reconciliation.json', prefix)

    def test_suffix_and_later_stages_use_only_original_frozen_payloads(self):
        self.assertEqual(continuation.STAGES[0], ('fresh1', 'P2', 'suffix'))
        self.assertEqual([x['record_id'] for x in continuation.selected_requests(*continuation.STAGES[0])],
                         continuation.SUFFIX)
        for repeat, condition, stage in continuation.STAGES:
            with self.subTest(repeat=repeat, condition=condition, stage=stage):
                selected = continuation.selected_requests(repeat, condition, stage)
                plan = continuation.source_plan(repeat)
                source = plan['conditions'][condition]['development' if stage == 'suffix' else stage]
                self.assertEqual(selected, source[7:] if stage == 'suffix' else source)
                self.assertEqual(len(selected), 53 if stage == 'suffix' else 3 if stage == 'smoke' else 60)
        with self.assertRaisesRegex(ValueError, 'outside versioned'):
            continuation.selected_requests('fresh1', 'P2', 'development')

    def test_stale_original_hash_is_rejected(self):
        with patch.dict(continuation.PREFIX_SHAS, {'attempts': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'Original stopped attempts changed'):
                continuation.verify_stopped_prefix()

    def synthetic_seal(self, root):
        prefix = continuation.verify_stopped_prefix()
        child = root / 'old-child.jsonl'
        original_lines = continuation.OLD_LEDGER.read_bytes().splitlines(keepends=True)
        self.assertGreaterEqual(len(original_lines), continuation.OLD_LEDGER_LINES)
        original_prefix = b''.join(original_lines[:continuation.OLD_LEDGER_LINES])
        self.assertEqual(hashlib.sha256(original_prefix).hexdigest(), continuation.OLD_LEDGER_SHA)
        child.write_bytes(original_prefix)
        unknown = {'event': 'unknown_cost_accounted_as_upper_bound',
                   'attempt_id': prefix['failed_attempt_id'], 'usd': str(continuation.RESERVE),
                   'actual_cost_usd': None, 'reason': 'Captured 429 unknown charge',
                   'evidence_path': str(continuation.prefix_paths()['attempts'].resolve()),
                   'evidence_sha256': continuation.PREFIX_SHAS['attempts']}
        with child.open('a') as out:
            out.write(json.dumps(unknown) + '\n')
            out.write(json.dumps({'event': 'partition_closed', 'reason': 'terminal'}) + '\n')
        reconciled = {'event': 'partition_reconciled',
                      'partition_id': continuation.OLD_PARTITION,
                      'known_actual_usd': '0.04530062',
                      'unknown_upper_bound_usd': str(continuation.RESERVE),
                      'unused_allocation_released_usd': '0.33495666',
                      'child_ledger': str(child.resolve()),
                      'child_sha256': continuation.sha(child)}
        reconciliation = root / 'reconciliation.json'
        reconciliation.write_text(json.dumps(reconciled) + '\n')
        master = root / 'master.jsonl'
        master.write_text(''.join(json.dumps(event) + '\n' for event in (
            {'event': 'budget', 'cap_usd': '12.38'},
            {'event': 'budget_partition', 'partition_id': continuation.OLD_PARTITION,
             'allocated_usd': '0.40', 'manifest_path': str(root / 'old-budget.json'),
             'manifest_sha256': '0' * 64, 'child_ledger': str(child.resolve()),
             'model': continuation.study.MODEL, 'provider': continuation.study.PROVIDER,
             'reasoning': continuation.study.EFFORT},
            reconciled)))
        return prefix, child, master, reconciliation

    def synthetic_allocation(self, area):
        prefix, old_child, master, reconciliation = self.synthetic_seal(area)
        output = area / 'continuation'
        output.mkdir()
        budget = output / 'budget.json'
        child = output / ('budget-' + continuation.PARTITION_ID + '.jsonl')
        child.write_text('{"event":"budget","cap_usd":"0.30"}\n')
        budget_data = {'version': 'paid-partitions-v1', 'master_ledger': str(master),
                       'partitions': [{'id': continuation.PARTITION_ID,
                                      'cap_usd': '0.30', 'child_ledger': str(child),
                                      'model': continuation.study.MODEL,
                                      'provider': continuation.study.PROVIDER,
                                      'reasoning': continuation.study.EFFORT}]}
        budget.write_text(json.dumps(budget_data) + '\n')
        allocation = {'event': 'budget_partition', 'partition_id': continuation.PARTITION_ID,
                      'allocated_usd': '0.30', 'manifest_path': str(budget),
                      'manifest_sha256': continuation.sha(budget),
                      'child_ledger': str(child), 'model': continuation.study.MODEL,
                      'provider': continuation.study.PROVIDER,
                      'reasoning': continuation.study.EFFORT}
        with master.open('a') as out:
            out.write(json.dumps(allocation) + '\n')
        return prefix, old_child, master, reconciliation, output, budget, child

    def test_synthetic_seal_uses_pinned_prefix_after_real_ledger_grows(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            area = Path(temp)
            source = area / 'later-sealed-ledger.jsonl'
            source.write_bytes(continuation.OLD_LEDGER.read_bytes() +
                               b'{"event":"unknown_cost_accounted_as_upper_bound"}\n' +
                               b'{"event":"partition_closed"}\n')
            with patch.object(continuation, 'OLD_LEDGER', source):
                prefix, child, master, reconciliation = self.synthetic_seal(area)
            self.assertEqual(len(continuation.rows(child)), continuation.OLD_LEDGER_LINES + 2)
            with patch.object(continuation, 'OLD_LEDGER', child), \
                 patch.object(continuation, 'MASTER', master):
                self.assertEqual(continuation.verify_old_seal(reconciliation, prefix)['unknown_upper_bound_usd'],
                                 str(continuation.RESERVE))

    def test_seal_requires_exact_unknown_accounting_and_reconciliation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            prefix, child, master, reconciliation = self.synthetic_seal(Path(temp))
            with patch.object(continuation, 'OLD_LEDGER', child), \
                 patch.object(continuation, 'MASTER', master):
                self.assertEqual(continuation.verify_old_seal(reconciliation, prefix)['unknown_upper_bound_usd'],
                                 str(continuation.RESERVE))
                data = continuation.rows(child)
                data[-2]['evidence_sha256'] = '0' * 64
                child.write_text(''.join(json.dumps(row) + '\n' for row in data))
                with self.assertRaisesRegex(ValueError, 'not been accounted'):
                    continuation.verify_old_seal(reconciliation, prefix)

    def test_allocated_manifest_freezes_descriptive_series_and_receipt_binds_suffix(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            area = Path(temp)
            _, old_child, master, reconciliation, output, budget, child = self.synthetic_allocation(area)
            with patch.object(continuation, 'OLD_LEDGER', old_child), \
                 patch.object(continuation, 'MASTER', master), \
                 patch.object(continuation, 'OUTPUT', output):
                opening = child.read_bytes()
                with child.open('a') as out:
                    out.write('{"event":"reserve","attempt_id":"foreign","record_id":"DEV-001","usd":"0.01"}\n')
                with self.assertRaisesRegex(ValueError, 'spent, sealed or reconciled'):
                    continuation.freeze(budget, reconciliation)
                child.write_bytes(opening)
                digest = continuation.freeze(budget, reconciliation)
                manifest = continuation.verify_manifest(digest)
                self.assertFalse(manifest['clean_matched_three_eligible'])
                self.assertEqual(manifest['stages'][0]['ids'], continuation.SUFFIX)
                review = continuation.expected_review(manifest, digest, 'fresh1', 'P2', 'suffix')
                self.assertEqual(review['ids'], continuation.SUFFIX)
                self.assertEqual(review['child_cap_usd'], '0.30')
                review_path = continuation.review_path('fresh1', 'P2', 'suffix')
                review_path.parent.mkdir(parents=True)
                review_path.write_text(json.dumps(review) + '\n')
                continuation.verify_review(review_path, manifest, digest, 'fresh1', 'P2', 'suffix')
                review['request_sha256'][0] = '0' * 64
                review_path.write_text(json.dumps(review) + '\n')
                with self.assertRaisesRegex(ValueError, 'does not bind'):
                    continuation.verify_review(review_path, manifest, digest, 'fresh1', 'P2', 'suffix')

    def test_reconciled_child_preserves_closed_evidence_but_blocks_new_dispatch(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            area = Path(temp)
            _, old_child, master, reconciliation, output, budget, child = self.synthetic_allocation(area)
            with patch.object(continuation, 'OLD_LEDGER', old_child), \
                 patch.object(continuation, 'MASTER', master), \
                 patch.object(continuation, 'OUTPUT', output):
                digest = continuation.freeze(budget, reconciliation)
                manifest = continuation.verify_manifest(digest)
                repeat, condition, stage = continuation.STAGES[0]
                review = continuation.expected_review(manifest, digest, repeat, condition, stage)
                review_path = continuation.review_path(repeat, condition, stage)
                review_path.parent.mkdir(parents=True)
                review_path.write_text(json.dumps(review) + '\n')
                paths = continuation.stage_paths(repeat, condition, stage)
                paths['claim'].write_text(json.dumps({
                    'series_id': continuation.SCHEMA, 'fresh_pass': repeat,
                    'condition': condition, 'phase': stage, 'manifest_sha256': digest,
                    'root_review_sha256': continuation.sha(review_path)}) + '\n')
                model_record = continuation.rows(
                    continuation.BASE / 'fresh1/P0/development.attempts.jsonl')[0]
                body = model_record['raw_response']
                model = model_record['model_catalog_entry']
                endpoint = model_record['provider_endpoint']
                cost = model_record['observed_cost_usd']
                attempts, responses, wire = [], [], []
                journal = [{'event': 'phase_started', 'fresh_pass': repeat,
                            'condition': condition, 'phase': stage}]
                for index, request in enumerate(continuation.selected_requests(repeat, condition, stage)):
                    rid = request['record_id']
                    attempt = f'synthetic-{index:03d}'
                    record = {'id': rid, 'attempt_id': attempt, 'series_id': continuation.SCHEMA,
                              'manifest_sha256': digest, 'request': request['payload'],
                              'request_sha256': request['request_sha256'],
                              'reserved_cost_usd': str(continuation.RESERVE),
                              'reference_labels_read': False, 'billing_ok': True,
                              'cost_unknown': False, 'observed_cost_usd': cost,
                              'model_catalog_entry': model, 'provider_endpoint': endpoint}
                    record.update(continuation.original.classify(body, model, endpoint))
                    record['response_diagnostic'] = continuation.audit_response(
                        record, 'openrouter_paid_v1', endpoint['context_length'] - 4096)
                    self.assertEqual(record['status'], 'ok')
                    self.assertTrue(record['response_diagnostic']['passed'])
                    attempts.append(record)
                    responses.append({'id': rid, 'attempt_id': attempt,
                                      'request_sha256': request['request_sha256'],
                                      'raw_response': body})
                    encoded = json.dumps(body).encode()
                    wire.append({'id': rid, 'attempt_id': attempt,
                                 'request_sha256': request['request_sha256'],
                                 'http_status': 200, 'body_base64': base64.b64encode(encoded).decode(),
                                 'body_truncated_at_limit': False, 'read_error': None})
                    journal.extend((
                        {'event': 'request_intent', 'id': rid,
                         'request_sha256': request['request_sha256']},
                        {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                         'request_sha256': request['request_sha256']},
                        {'event': 'request_finished', 'id': rid, 'attempt_id': attempt,
                         'status': 'ok', 'billing_ok': True, 'cost_unknown': False,
                         'observed_cost_usd': cost}))
                    with child.open('a') as out:
                        out.write(json.dumps({'event': 'reserve', 'attempt_id': attempt,
                                              'record_id': rid, 'usd': str(continuation.RESERVE)}) + '\n')
                        out.write(json.dumps({'event': 'settle', 'attempt_id': attempt,
                                              'usd': cost}) + '\n')
                journal.append({'event': 'phase_completed', 'fresh_pass': repeat,
                                'condition': condition, 'phase': stage,
                                'request_count': len(attempts),
                                'attempt_ids': [row['attempt_id'] for row in attempts]})
                for name, values in (('attempts', attempts), ('responses', responses),
                                     ('wire', wire), ('journal', journal)):
                    paths[name].write_text(''.join(json.dumps(value) + '\n' for value in values))
                continuation.verify_stage_closure(manifest, digest, repeat, condition, stage)
                with child.open('a') as out:
                    out.write('{"event":"partition_closed","reason":"terminal"}\n')
                known = continuation.paid.number(cost) * len(attempts)
                terminal = {'event': 'partition_reconciled',
                            'partition_id': continuation.PARTITION_ID,
                            'known_actual_usd': str(known), 'unknown_upper_bound_usd': '0',
                            'unused_allocation_released_usd': str(
                                continuation.paid.number('0.30') - known),
                            'child_ledger': str(child.resolve()),
                            'child_sha256': continuation.sha(child)}
                with master.open('a') as out:
                    out.write(json.dumps(terminal) + '\n')
                self.assertEqual(continuation.verify_manifest(digest), manifest)
                continuation.verify_stage_closure(manifest, digest, repeat, condition, stage)
                next_repeat, next_condition, next_stage = continuation.STAGES[1]
                next_review_path = continuation.review_path(next_repeat, next_condition, next_stage)
                next_review_path.parent.mkdir(parents=True)
                next_review_path.write_text(json.dumps(continuation.expected_review(
                    manifest, digest, next_repeat, next_condition, next_stage)) + '\n')
                with patch.object(continuation.original, 'live_controls',
                                  return_value=(model, endpoint, continuation.RESERVE)):
                    with self.assertRaisesRegex(ValueError, 'Inactive or mismatched partition'):
                        continuation.execute(digest, next_repeat, next_condition,
                                             next_stage, next_review_path)
                self.assertFalse(continuation.stage_paths(
                    next_repeat, next_condition, next_stage)['claim'].exists())
                terminal['child_sha256'] = '0' * 64
                master.write_text(''.join(json.dumps(row) + '\n' for row in
                                          continuation.rows(master)[:-1] + [terminal]))
                with self.assertRaisesRegex(ValueError, 'terminal reconciliation differs'):
                    continuation.verify_manifest(digest)

    def test_public_projection_removes_nested_account_id_without_changing_outcomes(self):
        sources = continuation.prefix_paths()
        attempts = continuation.rows(sources['attempts'])
        responses = continuation.rows(sources['responses'])
        wire = continuation.rows(sources['wire'])
        for kind, original in (('attempts', attempts[-1]), ('responses', responses[-1]),
                               ('wire', wire[-1])):
            with self.subTest(kind=kind):
                projected = continuation.public_prefix_row(kind, original)
                self.assertEqual(projected['id'], 'DEV-007')
                self.assertEqual(projected['attempt_id'], original['attempt_id'])
                if kind == 'wire':
                    body = json.loads(base64.b64decode(projected['body_base64']))
                    self.assertEqual(projected['body_bytes_captured'],
                                     len(base64.b64decode(projected['body_base64'])))
                else:
                    body = json.loads(projected['error_body'])
                    for field in ('status', 'cost_unknown', 'observed_cost_usd'):
                        if field in original:
                            self.assertEqual(projected[field], original[field])
                self.assertNotIn('user_id', body)
                self.assertIn('error', body)
        self.assertEqual(continuation.public_prefix_row('attempts', attempts[0]), attempts[0])

    def test_private_prefix_export_is_new_and_hash_bound(self):
        before = continuation.sha(continuation.prefix_paths()['attempts'])
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            output = Path(temp) / 'continuation'
            with patch.object(continuation, 'OUTPUT', output):
                destination = output / 'public-prefix-v1'
                manifest = continuation.export_public_prefix(destination)
                self.assertTrue(manifest['manual_privacy_review_required'])
                self.assertEqual(len(manifest['mappings']), 3)
                for mapping in manifest['mappings']:
                    self.assertEqual(continuation.sha(ROOT / mapping['private']['path']),
                                     mapping['private']['sha256'])
                    self.assertEqual(continuation.sha(ROOT / mapping['public']['path']),
                                     mapping['public']['sha256'])
                self.assertNotIn('user_id', json.loads(
                    continuation.rows(destination / 'development.attempts.jsonl')[-1]['error_body']))
                with self.assertRaisesRegex(ValueError, 'new exact versioned'):
                    continuation.export_public_prefix(destination)
        self.assertEqual(continuation.sha(continuation.prefix_paths()['attempts']), before)


if __name__ == '__main__':
    unittest.main()
