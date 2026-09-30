import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openrouter_decision_development as dev
import openrouter_decision_smoke as smoke
from tests.test_openrouter_decision_smoke import catalog, valid_body


class KevDevelopmentTests(unittest.TestCase):
    def evidence_copy(self, directory):
        root = Path(directory)
        smoke_base = root / 'smoke'
        smoke_base.mkdir()
        for filename in ('manifest.json', 'kev-endpoint.json', 'jev-endpoint.json',
                         'kev-attempts.jsonl', 'kev-root-review.json'):
            shutil.copyfile(smoke.BASE / filename, smoke_base / filename)
        attempts = [json.loads(line) for line in (smoke_base / 'kev-attempts.jsonl').read_text().splitlines()]
        ids = {row['ledger_attempt_id'] for row in attempts if row['stage'] == 'reserved'}
        ledger_events = [json.loads(line) for line in dev.LEDGER_PATH.read_text().splitlines()]
        relevant = [event for event in ledger_events if event.get('attempt_id') in ids]
        ledger_path = root / 'budget.jsonl'
        ledger_path.write_text('\n'.join(json.dumps(event) for event in
            [{'event': 'budget', 'cap_usd': '10'}] + relevant) + '\n')
        return smoke_base, ledger_path

    def prepared_copy(self, directory):
        smoke_base, ledger_path = self.evidence_copy(directory)
        base = Path(directory) / 'development'
        manifest_hash = dev.prepare(base=base, smoke_base=smoke_base, ledger_path=ledger_path)
        manifest = json.loads((base / 'manifest.json').read_text())
        receipt = {'approved': True, 'reviewer': 'offline-test', 'pass_id': dev.PASS_ID,
                   'manifest_sha256': manifest_hash, 'record_count': 60,
                   'max_reservation_usd': manifest['pass_bound_usd']}
        receipt_path = Path(directory) / 'review.json'
        receipt_path.write_text(json.dumps(receipt))
        return base, smoke_base, ledger_path, receipt_path, manifest

    def test_closed_smoke_proof_and_exact_bound(self):
        proof = dev.inspect_smoke()
        self.assertEqual(proof['smoke_cost_usd'], '0.000234864')
        self.assertEqual([row['id'] for row in proof['smoke_attempts']],
                         ['DEV-001', 'DEV-002', 'DEV-003'])
        self.assertEqual(str(60 * smoke.bound(dev.ROUTE)), '0.020643840')

    def test_manifest_has_60_input_only_native_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, _, manifest = self.prepared_copy(directory)
            self.assertEqual(dev.load_prepared(base, smoke_base, ledger_path), manifest)
            self.assertFalse(manifest['reference_labels_read'])
            self.assertFalse(manifest['inference_performed'])
            self.assertEqual([row['id'] for row in manifest['requests']],
                             [f'DEV-{i:03}' for i in range(1, 61)])
            self.assertEqual(manifest['pass_bound_usd'], '0.020643840')
            plan = json.loads((base / 'native-plan.json').read_text())
            self.assertEqual(manifest['native_plan_sha256'], smoke.sha(smoke.canonical(plan)))
            self.assertEqual([entry['ordinal'] for entry in plan['passes']], [1, 2, 3])
            self.assertEqual(plan['native_prompt_comparisons']['P1_equivalent'].split(';')[0],
                             'design_pending')
            for row in manifest['requests']:
                self.assertEqual(row['payload']['model'], dev.ROUTE['model'])
                self.assertEqual(set(row['payload']['state']), {'feedback', 'policy'})
                self.assertEqual(row['payload']['provider']['only'], [dev.ROUTE['tag']])
                self.assertNotIn('proposed_labels', json.dumps(row))

    def test_tampered_native_plan_invalidates_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, _, _ = self.prepared_copy(directory)
            path = base / 'native-plan.json'
            plan = json.loads(path.read_text())
            plan['passes'][1]['status'] = 'admitted'
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'Native three-pass plan differs'):
                dev.load_prepared(base, smoke_base, ledger_path)

    def test_tampered_smoke_raw_blocks_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            smoke_base, ledger_path = self.evidence_copy(directory)
            path = smoke_base / 'kev-attempts.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[1]['raw_response_base64'] = base64.b64encode(b'{}').decode()
            path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            with self.assertRaises(ValueError):
                dev.inspect_smoke(smoke_base, ledger_path)

    def test_receipt_and_headroom_fail_before_request(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, receipt, manifest = self.prepared_copy(directory)
            bad_receipt = json.loads(receipt.read_text())
            bad_receipt['max_reservation_usd'] = '0'
            receipt.write_text(json.dumps(bad_receipt))
            with patch.object(smoke, 'fetch_catalog') as fetch, patch.object(smoke, 'post') as post:
                with self.assertRaises(ValueError):
                    dev.execute(receipt, base, smoke_base, ledger_path)
                fetch.assert_not_called()
                post.assert_not_called()
            receipt.write_text(json.dumps(dict(bad_receipt,
                max_reservation_usd=manifest['pass_bound_usd'])))
            with ledger_path.open('a') as output:
                output.write(json.dumps({'event': 'reserve', 'attempt_id': 'other',
                    'record_id': 'other', 'usd': '9.98'}) + '\n')
                output.write(json.dumps({'event': 'settle', 'attempt_id': 'other',
                    'usd': '9.98'}) + '\n')
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post') as post:
                with self.assertRaisesRegex(ValueError, 'Full Kev first-pass bound'):
                    dev.execute(receipt, base, smoke_base, ledger_path)
                post.assert_not_called()
            self.assertFalse((base / 'attempts.jsonl').exists())

    def test_mocked_full_pass_writes_60_valid_with_raw_and_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, receipt, manifest = self.prepared_copy(directory)
            raw = json.dumps(valid_body(dev.ROUTE), separators=(',', ':')).encode()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                dev.execute(receipt, base, smoke_base, ledger_path)
            self.assertEqual(post.call_count, 60)
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 180)
            self.assertEqual(sum(row['stage'] == 'validated' for row in rows), 60)
            response = rows[1]
            self.assertEqual(base64.b64decode(response['raw_response_base64']), raw)
            self.assertGreaterEqual(response['client_request_elapsed_ns'], 0)
            completion = json.loads((base / 'completion.json').read_text())
            self.assertEqual(completion['valid_count'], 60)
            self.assertEqual(completion['manifest_sha256'], smoke.sha(smoke.canonical(manifest)))

    def test_unknown_cost_stops_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, receipt, _ = self.prepared_copy(directory)
            body = valid_body(dev.ROUTE)
            del body['usage']['cost']
            raw = json.dumps(body).encode()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
                    dev.execute(receipt, base, smoke_base, ledger_path)
            self.assertEqual(post.call_count, 1)
            self.assertFalse((base / 'completion.json').exists())
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'response'])
            self.assertTrue(rows[1]['cost_unknown'])

    def test_transport_error_records_timing_and_pending_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, receipt, _ = self.prepared_copy(directory)
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post', side_effect=TimeoutError('offline test')) as post:
                with self.assertRaises(TimeoutError):
                    dev.execute(receipt, base, smoke_base, ledger_path)
            self.assertEqual(post.call_count, 1)
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'transport_error'])
            self.assertGreaterEqual(rows[1]['client_request_elapsed_ns'], 0)
            self.assertTrue(rows[1]['request_start_utc'].endswith('Z'))
            self.assertTrue(rows[1]['request_end_utc'].endswith('Z'))
            self.assertFalse((base / 'completion.json').exists())

    def test_returned_provider_mismatch_settles_cost_then_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, receipt, _ = self.prepared_copy(directory)
            body = valid_body(dev.ROUTE)
            body['provider'] = 'Other'
            raw = json.dumps(body).encode()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                with self.assertRaisesRegex(ValueError, 'Returned provider mismatch'):
                    dev.execute(receipt, base, smoke_base, ledger_path)
            self.assertEqual(post.call_count, 1)
            rows = [json.loads(line) for line in (base / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'response'])
            self.assertEqual(rows[1]['body']['provider'], 'Other')
            events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'settle')
            self.assertFalse((base / 'completion.json').exists())

    def test_duplicate_dispatch_never_posts_or_changes_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            base, smoke_base, ledger_path, receipt, _ = self.prepared_copy(directory)
            raw = json.dumps(valid_body(dev.ROUTE)).encode()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)):
                dev.execute(receipt, base, smoke_base, ledger_path)
            evidence_hash = smoke.sha((base / 'attempts.jsonl').read_bytes())
            ledger_hash = smoke.sha(ledger_path.read_bytes())
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(dev.ROUTE)), \
                 patch.object(smoke, 'post') as post:
                with self.assertRaises(FileExistsError):
                    dev.execute(receipt, base, smoke_base, ledger_path)
                post.assert_not_called()
            self.assertEqual(smoke.sha((base / 'attempts.jsonl').read_bytes()), evidence_hash)
            self.assertEqual(smoke.sha(ledger_path.read_bytes()), ledger_hash)


if __name__ == '__main__':
    unittest.main()
