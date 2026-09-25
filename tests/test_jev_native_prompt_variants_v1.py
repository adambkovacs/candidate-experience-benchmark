import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jev_native_prompt_variants_v1 as native
from development_benchmark import KEYS


class NativeJevVariants(unittest.TestCase):
    def fixture_response(self, *, usage=True):
        answers = {}
        for key, choices in native.make_payload('x', 'y', native.PRICE_MODEL, 'official')['questions'].items():
            labels = list(choices['criteria'])
            answers[key] = {'type': 'choice', 'choice': labels[0],
                            'probabilities': {label: float(i == 0) for i, label in enumerate(labels)},
                            'confidence': 1.0}
        response = {'model': native.PRICE_MODEL, 'answers': answers}
        if usage:
            response['usage'] = {'input_tokens': 100, 'output_tokens': 20}
        return response

    def smoke_fixture(self, directory):
        root = Path(directory)
        manifest = root / 'manifest.json'
        manifest.write_text(json.dumps(native.planned_manifest(), indent=2, ensure_ascii=False) + '\n')
        sha = native.sha_bytes(manifest.read_bytes())
        review = root / 'review.json'
        review.write_text(json.dumps({'kind': 'jev-native-plan-review-v1',
                                      'manifest_sha256': sha, 'variant': 'P1', 'reviewed': True}))
        ledger = root / 'ledger.jsonl'
        ledger.write_text(json.dumps({'event': 'budget', 'cap_usd': '1'}) + '\n' +
                          json.dumps({'event': 'reserve', 'attempt_id': 'prior-unknown',
                                      'record_id': 'old', 'usd': '0.002'}) + '\n')
        return SimpleNamespace(authorize_hosted_inference=True, manifest=str(manifest),
            variant='P1', phase='smoke', review_receipt=str(review), smoke_attempts=None,
            smoke_inspection=None, output=str(root/'out.jsonl'), journal=str(root/'journal.jsonl'),
            budget_ledger=str(ledger), max_usd=Decimal('1'), env_file=None, timeout=1), ledger

    def test_only_instructions_change(self):
        policy = native.load_policy()
        p0 = native.payload('example', policy, 'P0')
        p1 = native.payload('example', policy, 'P1')
        p2 = native.payload('example', policy, 'P2')
        self.assertEqual(p0['state'], p1['state'])
        self.assertEqual(p0['state'], p2['state'])
        self.assertEqual(p0['model'], p1['model'])
        for key in KEYS:
            q0, q1, q2 = (p['questions'][key] for p in (p0, p1, p2))
            self.assertEqual(q0['type'], q1['type'])
            self.assertEqual(q0['criteria'], q1['criteria'])
            self.assertEqual(q0['criteria'], q2['criteria'])
            self.assertEqual(q1['instructions'], q0['instructions'] + native.P1)
            self.assertEqual(q2['instructions'], q1['instructions'] + native.P2[key])
        self.assertNotIn('messages', p1)
        self.assertNotIn('response_format', p2)

    def test_manifest_matches_saved_p0_and_contains_no_references(self):
        value = native.planned_manifest(verify_baseline=True)
        self.assertEqual(value['parent_baseline_id'], 'typesafe-jev113-v2')
        self.assertEqual(len(value['requests']['P0']), 60)
        self.assertEqual(len(value['requests']['P1']), 60)
        self.assertEqual(len(value['requests']['P2']), 60)
        self.assertNotIn('proposed_labels', json.dumps(value))
        self.assertNotIn('prediction', json.dumps(value))
        self.assertGreater(Decimal(value['planned_reservation_upper_usd']['P2']), Decimal('0'))

    def test_frozen_manifest_and_receipt_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            value = native.planned_manifest()
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
            manifest, sha = native.read_frozen_manifest(path)
            self.assertEqual(value, manifest)
            review = Path(directory) / 'review.json'
            review.write_text(json.dumps({'kind': 'jev-native-plan-review-v1',
                                          'manifest_sha256': sha, 'variant': 'P1', 'reviewed': True}))
            native.receipt(review, 'jev-native-plan-review-v1', sha, 'P1')
            with self.assertRaises(ValueError):
                native.receipt(review, 'jev-native-plan-review-v1', sha, 'P2')
            value['model'] = 'jev-latest'
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
            with self.assertRaises(ValueError):
                native.read_frozen_manifest(path)

    def test_development_rejects_uninspected_smoke_before_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps(native.planned_manifest(), indent=2, ensure_ascii=False) + '\n')
            sha = native.sha_bytes(manifest.read_bytes())
            review = root / 'review.json'
            review.write_text(json.dumps({'kind': 'jev-native-plan-review-v1',
                                          'manifest_sha256': sha, 'variant': 'P1', 'reviewed': True}))
            smoke = root / 'smoke.jsonl'
            smoke.write_text('')
            args = SimpleNamespace(authorize_hosted_inference=True, manifest=str(manifest),
                variant='P1', phase='development', review_receipt=str(review),
                smoke_attempts=str(smoke), smoke_inspection=None, output=str(root/'out.jsonl'),
                journal=str(root/'journal.jsonl'), budget_ledger=str(native.LEDGER),
                max_usd=Decimal('1'), env_file=None, timeout=1)
            with mock.patch.object(native, 'load_key') as key, mock.patch.object(native, 'fetch') as fetch:
                with self.assertRaises(ValueError):
                    native.execute(args)
            key.assert_not_called()
            fetch.assert_not_called()

    def test_smoke_records_terminal_and_preserves_prior_unknown_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            args, ledger = self.smoke_fixture(directory)
            with mock.patch.object(native, 'LEDGER', ledger), \
                 mock.patch.object(native, 'load_key', return_value='secret'), \
                 mock.patch.object(native, 'fetch', return_value=self.fixture_response()) as fetch:
                native.execute(args)
            self.assertEqual(fetch.call_count, 3)
            saved = [json.loads(line) for line in Path(args.output).read_text().splitlines()]
            journal = [json.loads(line) for line in Path(args.journal).read_text().splitlines()]
            self.assertEqual([r['id'] for r in saved], list(native.SMOKE_IDS))
            self.assertTrue(all(r['status'] == 'ok' and r['reported_input_tokens'] == 100
                                and r['provider_reported_inference_seconds'] is None
                                and r['client_http_call_seconds'] >= 0 for r in saved))
            self.assertEqual(journal[-1]['event'], 'terminal')
            self.assertEqual(journal[-1]['status'], 'complete')
            self.assertEqual(journal[-1]['finished_requests'], 3)
            plan, sha = native.read_frozen_manifest(args.manifest)
            native.verify_smoke(saved, plan, sha, 'P1')
            events = [json.loads(line) for line in ledger.read_text().splitlines()]
            self.assertFalse(any(e.get('event') == 'settle' and e.get('attempt_id') == 'prior-unknown'
                                 for e in events))

    def test_unknown_usage_stops_with_durable_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            args, ledger = self.smoke_fixture(directory)
            with mock.patch.object(native, 'LEDGER', ledger), \
                 mock.patch.object(native, 'load_key', return_value='secret'), \
                 mock.patch.object(native, 'fetch', return_value=self.fixture_response(usage=False)) as fetch:
                native.execute(args)
            self.assertEqual(fetch.call_count, 1)
            saved = [json.loads(line) for line in Path(args.output).read_text().splitlines()]
            journal = [json.loads(line) for line in Path(args.journal).read_text().splitlines()]
            self.assertEqual(saved[0]['status'], 'ok')
            self.assertTrue(saved[0]['cost_unknown'])
            self.assertEqual(len(saved), 1)
            self.assertEqual(journal[-1]['status'], 'stopped')
            self.assertEqual(journal[-1]['stop_reason'], 'cost_unknown')
            self.assertEqual(journal[-1]['finished_requests'], 1)


if __name__ == '__main__':
    unittest.main()
