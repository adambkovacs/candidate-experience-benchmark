"""Offline proof and continuation tests; no OpenRouter inference."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini_openrouter_metadata_recovery_v1 as g

SOURCE = ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0'


class RecoveryTests(unittest.TestCase):
    def fixture(self, folder):
        for name in ('manifest.json', 'smoke-attempts.jsonl', 'smoke-records.jsonl',
                     'smoke-journal.jsonl', g.METADATA_FILE):
            shutil.copyfile(SOURCE / name, folder / name)
        with contextlib.redirect_stdout(io.StringIO()):
            g.write_proof(SimpleNamespace(manifest=str(folder / 'manifest.json')))
        return folder / 'manifest.json'

    def test_recovery_proof_preserves_failed_smoke_and_bindings(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            folder = Path(temp)
            manifest = self.fixture(folder)
            proof = g.validate_recovery(manifest, folder / 'smoke-recovery-proof-v1.json')
            self.assertEqual(proof['schema'], g.RECOVERY_SCHEMA)
            self.assertEqual(proof['original_smoke_terminal'], 'identity_unverified')
            self.assertEqual(len(proof['predictions']), 3)
            self.assertEqual(proof['observed_cost_usd'], '0.001704')
            self.assertEqual(proof['generation_id'], proof['recovered_metadata']['id'])
            attempt = json.loads((folder / 'smoke-attempts.jsonl').read_text())
            self.assertEqual(attempt['status'], 'identity_unverified')
            self.assertNotIn('predictions', attempt)

    def test_tampered_metadata_or_smoke_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            folder = Path(temp)
            manifest = self.fixture(folder)
            path = folder / g.METADATA_FILE
            data = json.loads(path.read_text())
            data['provider_name'] = 'Different Provider'
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                g.validate_recovery(manifest, folder / 'smoke-recovery-proof-v1.json')

    def test_generation_get_retries_404_only_without_post(self):
        count = 0
        def fake(path, *args, **kwargs):
            nonlocal count
            self.assertTrue(path.startswith('/generation?id='))
            count += 1
            if count < 3:
                raise urllib.error.HTTPError('url', 404, 'not yet indexed', {}, None)
            return {'data': {'id': 'gen-1'}}
        with mock.patch.object(g, 'fetch', side_effect=fake), mock.patch.object(g.time, 'sleep') as sleep:
            result = g.fetch_generation_with_retry('gen-1', 'key', 300)
        self.assertEqual(result['data']['id'], 'gen-1')
        self.assertEqual(count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_generation_get_stops_after_three_404s(self):
        paths = []
        def fake(path, *args, **kwargs):
            paths.append(path)
            raise urllib.error.HTTPError('url', 404, 'not yet indexed', {}, None)
        with mock.patch.object(g, 'fetch', side_effect=fake), mock.patch.object(g.time, 'sleep') as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                g.fetch_generation_with_retry('gen-1', 'key', 300)
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(path.startswith('/generation?id=') for path in paths))
        self.assertEqual(sleep.call_count, 2)

    def test_development_continuation_requires_exact_receipt_and_no_smoke_replay(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            folder = Path(temp)
            manifest = self.fixture(folder)
            budget = folder / 'budget.json'
            budget.write_text('{}\n')
            receipt = folder / 'approval.json'
            receipt.write_text(json.dumps({'schema': g.APPROVAL_SCHEMA, 'approved': True,
                'manifest_sha256': g.sha(manifest.read_bytes()),
                'smoke_recovery_proof_sha256': g.sha((folder / 'smoke-recovery-proof-v1.json').read_bytes()),
                'controller_sha256': g.sha(Path(g.__file__).read_bytes()),
                'budget_manifest_sha256': g.sha(budget.read_bytes()),
                'partition_id': 'fake-partition', 'phase': 'development'}))
            args = SimpleNamespace(manifest=str(manifest), manifest_sha256=g.sha(manifest.read_bytes()),
                budget_manifest=str(budget), partition_id='fake-partition', approval=str(receipt),
                env_file=None)
            class Ledger:
                master_cap = g.Decimal(10)
                def __init__(self):
                    self.reserves = []
                    self.settles = []
                def reserve(self, amount, ids):
                    self.reserves.append((amount, ids))
                    return 'attempt-' + str(len(self.reserves))
                def settle(self, attempt, cost):
                    self.settles.append((attempt, cost))
                    return cost is not None
                def close(self): pass
            ledger = Ledger()
            catalog = json.loads((g.PREP / 'catalog.json').read_text())
            endpoints = json.loads((g.PREP / 'gemini-3.8-flash-endpoints.json').read_text())
            endpoint = g.check_catalog('google/gemini-3.8-flash', 'low', catalog, endpoints)[1]
            revision = endpoint['name'].split(' | ', 1)[1]
            calls = {'chat': 0, 'get': 0}
            def fake_fetch(path, *rest, **kwargs):
                if path == '/models': return catalog
                if path.endswith('/endpoints'): return endpoints
                if path.startswith('/generation?id='):
                    calls['get'] += 1
                    if calls['get'] <= 2:
                        raise urllib.error.HTTPError('url', 404, 'not yet indexed', {}, None)
                    return {'data': {'id': 'gen-' + str(calls['chat']), 'model': revision,
                        'provider_name': g.PROVIDER_NAME, 'total_cost': 0.001,
                        'num_fetches': 0, 'num_search_results': 0}}
                self.assertEqual(path, '/chat/completions')
                calls['chat'] += 1
                first = (calls['chat'] - 1) * 10 + 1
                records = [{'id': f'DEV-{i:03}', 'sentiment': 'neutral',
                    'follow_up_needed': 'no', 'serious_concern_reported': 'no',
                    'testimonial_potential': 'no'} for i in range(first, first + 10)]
                return {'id': 'gen-' + str(calls['chat']), 'model': revision,
                    'provider': g.PROVIDER_NAME,
                    'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'records': records})}}],
                    'usage': {'cost': 0.001}}
            with mock.patch.object(g, 'fetch', side_effect=fake_fetch), \
                 mock.patch.object(g, 'load_key', return_value='test-key'), \
                 mock.patch.object(g, 'open_partition', return_value=ledger), \
                 mock.patch.object(g.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                g.run_development(args)
            self.assertEqual(calls['chat'], 6)
            self.assertEqual(calls['get'], 8)
            self.assertEqual(len(ledger.reserves), 6)
            self.assertEqual(len(ledger.settles), 6)
            rows = [json.loads(line) for line in (folder / 'development-records.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 60)
            self.assertEqual([r['id'] for r in rows], [f'DEV-{i:03}' for i in range(1, 61)])
            journal = [json.loads(line) for line in (folder / 'development-journal.jsonl').read_text().splitlines()]
            self.assertTrue(journal[-1]['completed'])
            self.assertEqual(json.loads((folder / 'smoke-attempts.jsonl').read_text())['status'], 'identity_unverified')


if __name__ == '__main__':
    unittest.main()
