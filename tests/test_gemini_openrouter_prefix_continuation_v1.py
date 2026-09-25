"""Offline coverage for additive batch-1 proof and five-batch suffix."""
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
import gemini_openrouter_prefix_continuation_v1 as g

SOURCE = ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0'

class PrefixContinuationTests(unittest.TestCase):
    def fixture(self, folder):
        for name in ('manifest.json', 'smoke-attempts.jsonl', 'smoke-records.jsonl',
                     'smoke-journal.jsonl', 'smoke-recovered-generation-metadata.json',
                     'development-attempts.jsonl',
                     'development-records.jsonl', 'development-journal.jsonl', g.BATCH1_METADATA):
            shutil.copyfile(SOURCE / name, folder / name)
        with contextlib.redirect_stdout(io.StringIO()):
            g.write_proof(SimpleNamespace(manifest=str(folder / 'manifest.json')))
            g.write_prefix_proof(SimpleNamespace(manifest=str(folder / 'manifest.json')))
        return folder / 'manifest.json'

    def test_prefix_proof_exact_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            folder = Path(temp)
            manifest = self.fixture(folder)
            proof = g.validate_prefix(manifest, folder / 'development-prefix-recovery-proof-v1.json')
            self.assertEqual(proof['schema'], g.PREFIX_SCHEMA)
            self.assertEqual(proof['batch_index'], 1)
            self.assertEqual(len(proof['predictions']), 10)
            self.assertEqual(proof['observed_cost_usd'], '0.0035265')
            self.assertEqual(json.loads((folder / 'development-attempts.jsonl').read_text())['status'], 'identity_unverified')
            metadata = folder / g.BATCH1_METADATA
            data = json.loads(metadata.read_text())
            data['id'] = 'wrong-generation'
            metadata.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                g.validate_prefix(manifest, folder / 'development-prefix-recovery-proof-v1.json')

    def test_provider_present_runs_only_five_suffix_batches_without_get(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            folder = Path(temp)
            manifest = self.fixture(folder)
            proof = folder / 'development-prefix-recovery-proof-v1.json'
            budget = folder / 'budget.json'
            budget.write_text('{}\n')
            receipt = folder / 'suffix-approval.json'
            receipt.write_text(json.dumps({'schema': g.SUFFIX_APPROVAL_SCHEMA, 'approved': True,
                'manifest_sha256': g.sha(manifest.read_bytes()),
                'prefix_recovery_proof_sha256': g.sha(proof.read_bytes()),
                'controller_sha256': g.sha(Path(g.__file__).read_bytes()),
                'budget_manifest_sha256': g.sha(budget.read_bytes()),
                'partition_id': 'fake-partition', 'first_batch_index': 2, 'last_batch_index': 6}))
            args = SimpleNamespace(manifest=str(manifest), manifest_sha256=g.sha(manifest.read_bytes()),
                budget_manifest=str(budget), partition_id='fake-partition', approval=str(receipt), env_file=None)
            class Ledger:
                master_cap = g.Decimal(10)
                def __init__(self): self.reserves=[]; self.settles=[]
                def reserve(self, amount, ids):
                    self.reserves.append((amount, ids)); return 'attempt-' + str(len(self.reserves))
                def settle(self, attempt, cost):
                    self.settles.append((attempt,cost)); return cost is not None
                def close(self): pass
            ledger=Ledger()
            catalog=json.loads((g.PREP / 'catalog.json').read_text())
            endpoints=json.loads((g.PREP / 'gemini-3.8-flash-endpoints.json').read_text())
            endpoint=g.check_catalog('google/gemini-3.8-flash','low',catalog,endpoints)[1]
            revision=endpoint['name'].split(' | ',1)[1]
            calls=[]
            def fake_fetch(path,*rest,**kwargs):
                calls.append(path)
                if path=='/models': return catalog
                if path.endswith('/endpoints'): return endpoints
                self.assertEqual(path,'/chat/completions')
                batch=sum(p=='/chat/completions' for p in calls)
                first=batch*10+1
                records=[{'id':f'DEV-{i:03}','sentiment':'neutral',
                          'follow_up_needed':'no','serious_concern_reported':'no',
                          'testimonial_potential':'no'} for i in range(first,first+10)]
                return {'id':f'gen-{batch}','model':revision,'provider':g.PROVIDER_NAME,
                        'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'records':records})}}],
                        'usage':{'cost':0.001}}
            with mock.patch.object(g,'fetch',side_effect=fake_fetch), \
                 mock.patch.object(g,'load_key',return_value='test-key'), \
                 mock.patch.object(g,'open_partition',return_value=ledger), \
                 contextlib.redirect_stdout(io.StringIO()):
                g.run_remaining(args)
            self.assertEqual(calls.count('/chat/completions'),5)
            self.assertFalse(any(p.startswith('/generation?id=') for p in calls))
            self.assertEqual(len(ledger.reserves),5)
            attempts=[json.loads(x) for x in (folder/'development-continuation-v1-attempts.jsonl').read_text().splitlines()]
            self.assertEqual([a['batch_index'] for a in attempts],[2,3,4,5,6])
            self.assertTrue(all(a['status']=='ok' and a['generation_metadata_deferred'] for a in attempts))
            rows=[json.loads(x) for x in (folder/'development-continuation-v1-records.jsonl').read_text().splitlines()]
            self.assertEqual([r['id'] for r in rows],[f'DEV-{i:03}' for i in range(11,61)])
            journal=[json.loads(x) for x in (folder/'development-continuation-v1-journal.jsonl').read_text().splitlines()]
            self.assertTrue(journal[-1]['completed'])
            self.assertEqual(journal[-1]['expected_batches'],5)
            self.assertEqual(json.loads((folder/'development-attempts.jsonl').read_text())['status'],'identity_unverified')

    def test_missing_provider_uses_bounded_get_only(self):
        calls=[]
        def fake(path,*args,**kwargs):
            calls.append(path)
            if len(calls)<12:
                raise urllib.error.HTTPError('url',404,'not indexed',{},None)
            return {'data':{'id':'gen-1'}}
        with mock.patch.object(g,'fetch',side_effect=fake), mock.patch.object(g.time,'sleep') as sleep:
            self.assertEqual(g.fetch_generation_fallback('gen-1','key',300)['data']['id'],'gen-1')
        self.assertEqual(len(calls),12)
        self.assertEqual(sleep.call_count,11)
        self.assertTrue(all(p.startswith('/generation?id=') for p in calls))

if __name__=='__main__': unittest.main()
