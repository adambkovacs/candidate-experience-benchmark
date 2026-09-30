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
import openrouter_decision_development as first
import openrouter_decision_repeats as repeat
import openrouter_decision_smoke as smoke
from tests.test_openrouter_decision_smoke import catalog, valid_body


class KevRepeatTests(unittest.TestCase):
    def copied_first(self, directory, completion=True):
        root = Path(directory)
        first_base = root / 'first'
        first_base.mkdir()
        filenames = ['manifest.json', 'native-plan.json', 'root-review.json']
        if completion:
            filenames += ['attempts.jsonl', 'completion.json']
        for filename in filenames:
            shutil.copyfile(first.BASE / filename, first_base / filename)
        ledger = root / 'budget.jsonl'
        shutil.copyfile(repeat.LEDGER_PATH, ledger)
        return first_base, ledger

    def prepared(self, directory, completion=True):
        first_base, ledger = self.copied_first(directory, completion)
        base = Path(directory) / 'repeats'
        repeat.prepare_candidates(base, first_base)
        return base, first_base, ledger

    def receipt(self, directory, manifest):
        path = Path(directory) / 'root-review.json'
        path.write_text(json.dumps({'approved': True, 'reviewer': 'offline-test',
            'pass_id': manifest['pass_id'],
            'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'max_reservation_usd': manifest['pass_bound_usd'], 'record_count': 60}))
        return path

    def test_candidates_copy_exact_wire_and_remain_unadmitted(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            original = repeat.load_first_static(first_base)
            for ordinal in (2, 3):
                candidate = repeat.load_candidate(ordinal, base, first_base)
                self.assertFalse(candidate['admission_ready'])
                self.assertFalse(candidate['inference_performed'])
                self.assertFalse(candidate['reference_labels_read'])
                self.assertEqual(candidate['requests'], original['requests'])
                self.assertEqual(candidate['pass_id'], repeat.PASSES[ordinal])
                self.assertEqual(candidate['pass_bound_usd'], '0.020643840')
                self.assertFalse((repeat.pass_dir(base, ordinal) / 'manifest.json').exists())
            self.assertFalse((repeat.pass_dir(base, 2) / 'attempts.jsonl').exists())

    def test_first_predecessor_reconciles_and_freeze_requires_completion(self):
        manifest = repeat.load_first_static()
        proof = repeat.inspect_finished(manifest, first.BASE, repeat.LEDGER_PATH,
                                        first.validate_receipt)
        self.assertEqual(proof['predecessor_actual_cost_usd'], '0.004703412')
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory, completion=False)
            with self.assertRaises(FileNotFoundError):
                repeat.freeze(2, base, first_base, ledger)
            self.assertFalse((repeat.pass_dir(base, 2) / 'manifest.json').exists())

    def test_fresh2_freeze_binds_predecessor_and_fresh3_waits(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            manifest_hash = repeat.freeze(2, base, first_base, ledger)
            manifest = repeat.load_frozen(2, base, first_base, ledger)
            self.assertEqual(manifest_hash, smoke.sha(smoke.canonical(manifest)))
            self.assertEqual(manifest['predecessor_proof']['predecessor_actual_cost_usd'],
                             '0.004703412')
            self.assertNotEqual(manifest['pass_id'], first.PASS_ID)
            with self.assertRaises(FileNotFoundError):
                repeat.freeze(3, base, first_base, ledger)
            self.assertFalse((repeat.pass_dir(base, 3) / 'manifest.json').exists())

    def test_tampered_predecessor_blocks_frozen_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            repeat.freeze(2, base, first_base, ledger)
            path = first_base / 'attempts.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[1]['raw_response_base64'] = base64.b64encode(b'{}').decode()
            path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            with self.assertRaises(ValueError):
                repeat.load_frozen(2, base, first_base, ledger)

    def test_jev_parser_source_drift_blocks_before_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            repeat.freeze(2, base, first_base, ledger)
            path = first_base / 'manifest.json'
            first_manifest = json.loads(path.read_text())
            first_manifest['jev_adapter_sha256'] = '0' * 64
            path.write_text(json.dumps(first_manifest))
            with patch.object(smoke, 'post') as post:
                with self.assertRaisesRegex(ValueError, 'Frozen first-pass source'):
                    repeat.execute(2, '/nonexistent/receipt.json', base, first_base, ledger)
                post.assert_not_called()

    def test_mocked_fresh2_completion_allows_fresh3_freeze(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            repeat.freeze(2, base, first_base, ledger)
            manifest2 = repeat.load_frozen(2, base, first_base, ledger)
            review2 = self.receipt(repeat.pass_dir(base, 2), manifest2)
            raw = json.dumps(valid_body(repeat.ROUTE)).encode()
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(repeat.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                repeat.execute(2, review2, base, first_base, ledger)
            self.assertEqual(post.call_count, 60)
            manifest3_hash = repeat.freeze(3, base, first_base, ledger)
            manifest3 = repeat.load_frozen(3, base, first_base, ledger)
            self.assertEqual(manifest3_hash, smoke.sha(smoke.canonical(manifest3)))
            self.assertEqual(manifest3['predecessor_proof']['predecessor_pass_id'], repeat.PASSES[2])
            self.assertEqual(manifest3['requests'], manifest2['requests'])
            self.assertNotEqual(manifest3['pass_id'], manifest2['pass_id'])

    def test_receipt_rejection_and_duplicate_dispatch_never_post(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            repeat.freeze(2, base, first_base, ledger)
            manifest = repeat.load_frozen(2, base, first_base, ledger)
            receipt = self.receipt(repeat.pass_dir(base, 2), manifest)
            altered = json.loads(receipt.read_text())
            altered['pass_id'] = repeat.PASSES[3]
            receipt.write_text(json.dumps(altered))
            with patch.object(smoke, 'post') as post:
                with self.assertRaises(ValueError):
                    repeat.execute(2, receipt, base, first_base, ledger)
                post.assert_not_called()
            receipt = self.receipt(repeat.pass_dir(base, 2), manifest)
            raw = json.dumps(valid_body(repeat.ROUTE)).encode()
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(repeat.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)):
                repeat.execute(2, receipt, base, first_base, ledger)
            before = smoke.sha((repeat.pass_dir(base, 2) / 'attempts.jsonl').read_bytes())
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(repeat.ROUTE)), \
                 patch.object(smoke, 'post') as post:
                with self.assertRaises(FileExistsError):
                    repeat.execute(2, receipt, base, first_base, ledger)
                post.assert_not_called()
            self.assertEqual(smoke.sha((repeat.pass_dir(base, 2) / 'attempts.jsonl').read_bytes()), before)

    def test_unknown_cost_stops_and_keeps_pending_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            base, first_base, ledger = self.prepared(directory)
            repeat.freeze(2, base, first_base, ledger)
            manifest = repeat.load_frozen(2, base, first_base, ledger)
            receipt = self.receipt(repeat.pass_dir(base, 2), manifest)
            body = valid_body(repeat.ROUTE)
            del body['usage']['cost']
            raw = json.dumps(body).encode()
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'offline-test-key'}), \
                 patch.object(smoke, 'fetch_catalog', return_value=catalog(repeat.ROUTE)), \
                 patch.object(smoke, 'post', return_value=(200, raw)) as post:
                with self.assertRaisesRegex(ValueError, 'Unknown provider cost'):
                    repeat.execute(2, receipt, base, first_base, ledger)
            self.assertEqual(post.call_count, 1)
            self.assertFalse((repeat.pass_dir(base, 2) / 'completion.json').exists())
            rows = [json.loads(line) for line in (repeat.pass_dir(base, 2) / 'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows], ['reserved', 'response'])
            self.assertTrue(rows[1]['cost_unknown'])


if __name__ == '__main__':
    unittest.main()
