import base64
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openrouter_kev_interrupted_continuation as cont
import openrouter_decision_smoke as smoke
import openrouter_decision_repeats as repeat
from tests.test_openrouter_decision_smoke import catalog, valid_body


class KevInterruptedContinuationTests(unittest.TestCase):
    def prepared_temp(self, directory):
        base = Path(directory) / 'tail'
        ledger = Path(directory) / 'budget.jsonl'
        shutil.copyfile(cont.LEDGER_PATH, ledger)
        manifest_hash = cont.prepare(base, cont.REPEAT_BASE, cont.first.BASE, ledger)
        manifest = json.loads((base / 'manifest.json').read_text())
        receipt = base / 'root-review.json'
        receipt.write_text(json.dumps({'approved': True, 'reviewer': 'offline-test',
            'pass_id': cont.PASS_ID, 'manifest_sha256': manifest_hash,
            'start_id': 'DEV-027', 'end_id': 'DEV-060', 'record_count': 34,
            'max_reservation_usd': manifest['tail_bound_usd']}))
        return base, ledger, receipt, manifest

    def test_prefix_and_unknown_charge_reconcile(self):
        original = repeat.load_frozen(3)
        proof = cont.inspect_prefix(original)
        self.assertEqual(proof['prefix_valid_count'], 25)
        self.assertEqual(proof['prefix_known_actual_cost_usd'], '0.001959258')
        self.assertEqual(proof['unknown_record_id'], 'DEV-026')
        self.assertIsNone(proof['unknown_actual_cost_usd'])
        self.assertEqual(proof['unknown_upper_bound_usd'], '0.000344064')
        self.assertEqual(len(proof['never_sent_ids']), 34)

    def test_relocated_checkout_accepts_unchanged_historical_ledger_path(self):
        original = repeat.load_frozen(3)
        expected = cont.inspect_prefix(original)
        with tempfile.TemporaryDirectory() as directory:
            relocated = (Path(directory) / 'export' /
                'results/route-audits/decision-kev-repeats-20260930/fresh3')
            relocated.parent.mkdir(parents=True)
            shutil.copytree(cont.ORIGINAL_DIR, relocated)
            ledger = Path(directory) / 'budget.jsonl'
            shutil.copyfile(cont.LEDGER_PATH, ledger)
            unchanged = ledger.read_bytes()
            rows = [json.loads(line) for line in unchanged.decode().splitlines()]
            unknown = next(row for row in rows if row.get('event') == 'unknown_cost_accounted_as_upper_bound'
                and row.get('attempt_id') == expected['unknown_attempt_id'])
            self.assertNotEqual(Path(unknown['evidence_path']), relocated / 'attempts.jsonl')
            self.assertEqual(cont.inspect_prefix(original, relocated, ledger), expected)
            self.assertEqual(ledger.read_bytes(), unchanged)

    def test_wrong_historical_evidence_suffix_blocks(self):
        original = repeat.load_frozen(3)
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'budget.jsonl'
            rows = [json.loads(line) for line in cont.LEDGER_PATH.read_text().splitlines()]
            unknown = next(row for row in rows if row.get('event') == 'unknown_cost_accounted_as_upper_bound'
                and row.get('attempt_id') == 'd85c42b2-1333-4797-8a52-d324457a2361')
            unknown['evidence_path'] = '/different/export/attempts.jsonl'
            ledger.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            with self.assertRaisesRegex(ValueError, 'unknown-charge retention'):
                cont.inspect_prefix(original, cont.ORIGINAL_DIR, ledger)

    def test_manifest_exact_tail_and_no_dev026(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, _, manifest = self.prepared_temp(directory)
            self.assertEqual(cont.load_prepared(base, cont.REPEAT_BASE, cont.first.BASE, ledger), manifest)
            self.assertEqual([row['id'] for row in manifest['requests']],
                             [f'DEV-{index:03}' for index in range(27, 61)])
            self.assertEqual(manifest['tail_bound_usd'], '0.011698176')
            self.assertFalse(manifest['inference_performed'])
            self.assertFalse(manifest['reference_labels_read'])
            self.assertNotIn('DEV-026', [row['id'] for row in manifest['requests']])
            self.assertEqual([row['payload'] for row in manifest['requests']],
                             [row['payload'] for row in repeat.load_frozen(3)['requests'][26:]])

    def test_tampered_unknown_accounting_blocks_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, receipt, _ = self.prepared_temp(directory)
            rows = [json.loads(line) for line in ledger.read_text().splitlines()]
            event = next(row for row in rows if row.get('event') == 'unknown_cost_accounted_as_upper_bound'
                         and row.get('attempt_id') == 'd85c42b2-1333-4797-8a52-d324457a2361')
            event['evidence_sha256'] = '0' * 64
            ledger.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            with patch.object(smoke, 'post') as post:
                with self.assertRaises(ValueError):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
                post.assert_not_called()

    def test_receipt_and_headroom_guard_before_post(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, receipt, manifest = self.prepared_temp(directory)
            bad = json.loads(receipt.read_text())
            bad['start_id'] = 'DEV-026'
            receipt.write_text(json.dumps(bad))
            with patch.object(smoke, 'post') as post:
                with self.assertRaises(ValueError):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
                post.assert_not_called()
            bad['start_id'] = 'DEV-027'
            receipt.write_text(json.dumps(bad))
            with ledger.open('a') as output:
                output.write(json.dumps({'event': 'reserve', 'attempt_id': 'other',
                    'record_id': 'other', 'usd': '0.02'}) + '\n')
                output.write(json.dumps({'event': 'settle', 'attempt_id': 'other', 'usd': '0.02'}) + '\n')
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(cont.ROUTE)), \
                 patch.object(smoke, 'post') as post:
                with self.assertRaisesRegex(ValueError, 'Whole 34-record tail bound'):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
                post.assert_not_called()
            self.assertFalse((base / 'attempts.jsonl').exists())

    def test_mocked_34_tail_completion_keeps_unknown26_and_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, receipt, manifest = self.prepared_temp(directory)
            raw = json.dumps(valid_body(cont.ROUTE)).encode()
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(cont.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
            self.assertEqual(post.call_count, 34)
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 102)
            self.assertEqual([row['id'] for row in rows if row['stage'] == 'validated'],
                             [f'DEV-{index:03}' for index in range(27, 61)])
            self.assertEqual(base64.b64decode(rows[1]['raw_response_base64']), raw)
            completion = json.loads((base / 'completion.json').read_text())
            self.assertEqual(completion['combined_observed_valid_count'], 59)
            self.assertEqual(completion['original_unknown_record_id'], 'DEV-026')
            self.assertIsNone(completion['original_unknown_actual_cost_usd'])
            self.assertFalse(completion['clean_full_third_pass_complete'])
            self.assertEqual(completion['manifest_sha256'], smoke.sha(smoke.canonical(manifest)))
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(cont.ROUTE)), \
                 patch.object(smoke, 'post') as post:
                with self.assertRaises(FileExistsError):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
                post.assert_not_called()

    def test_new_unknown_cost_stops_tail_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, receipt, _ = self.prepared_temp(directory)
            body = valid_body(cont.ROUTE)
            del body['usage']['cost']
            raw = json.dumps(body).encode()
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(cont.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
            self.assertEqual(post.call_count, 1)
            self.assertFalse((base / 'completion.json').exists())
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'response'])
            self.assertEqual(rows[0]['id'], 'DEV-027')

    def test_new_transport_timeout_keeps_tail_reserve_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, receipt, _ = self.prepared_temp(directory)
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(cont.ROUTE)), \
                 patch.object(smoke, 'post', side_effect=TimeoutError('offline test')) as post:
                with self.assertRaises(TimeoutError):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
            self.assertEqual(post.call_count, 1)
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'transport_error'])
            self.assertEqual(rows[1]['id'], 'DEV-027')
            self.assertTrue(rows[1]['cost_unknown'])
            self.assertGreaterEqual(rows[1]['client_request_elapsed_ns'], 0)
            self.assertFalse((base / 'completion.json').exists())

    def test_wrong_returned_provider_settles_known_cost_then_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            base, ledger, receipt, _ = self.prepared_temp(directory)
            body = valid_body(cont.ROUTE)
            body['provider'] = 'Other'
            raw = json.dumps(body).encode()
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(cont.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                with self.assertRaisesRegex(ValueError, 'Returned provider mismatch'):
                    cont.execute(receipt, base, cont.REPEAT_BASE, cont.first.BASE, ledger)
            self.assertEqual(post.call_count, 1)
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'response'])
            self.assertEqual(base64.b64decode(rows[1]['raw_response_base64']), raw)
            attempt_id = rows[1]['attempt_id']
            events = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertEqual([event['event'] for event in events if event.get('attempt_id') == attempt_id],
                             ['reserve', 'settle'])
            self.assertFalse((base / 'completion.json').exists())


if __name__ == '__main__':
    unittest.main()
