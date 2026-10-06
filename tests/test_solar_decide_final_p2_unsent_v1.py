import io
import json
import os
from decimal import Decimal
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from development_benchmark import KEYS, VALUES
import openrouter_budget_v4 as budget_v4
import openrouter_decision_smoke as native
import paid_budget_partitions_v4 as partitions
import solar_decide_final_p2_unsent_v1 as run


class SolarSuffixTests(unittest.TestCase):
    def test_exact_original_and_unsent_suffix(self):
        audit, terminal = run.original_proof()
        self.assertEqual(audit['failed_record_id'], 'DEV-009')
        self.assertEqual(terminal['unknown_upper_bound_usd'], '0.10485760')
        value = run.manifest_value()
        self.assertEqual(value['never_sent_ids'], [f'DEV-{i:03}' for i in range(10, 61)])
        self.assertEqual(value['request_count'], 51)
        self.assertFalse(value['allocation_authorized'])
        self.assertFalse(value['inference_authorized'])
        self.assertTrue(value['no_new_smoke'])
        self.assertEqual(value['per_request_conservative_reserve_usd'], '0.10485760')

    def test_original_release_is_bound_to_sealed_unknown_and_unused_amount(self):
        receipt = json.loads(run.RELEASE_RECEIPT.read_text())
        receipt['event']['usd'] = '0.70140446'
        with tempfile.TemporaryDirectory() as temp:
            changed = Path(temp) / 'unused-release-receipt.json'
            changed.write_text(json.dumps(receipt) + '\n')
            with patch.object(run, 'RELEASE_RECEIPT', changed):
                with self.assertRaisesRegex(ValueError, 'authority release'):
                    run.original_proof()

    def test_stage_gate_uses_isolated_missing_budget_and_no_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            with patch.object(run, 'BUDGET', base / 'missing.json'):
                with self.assertRaises((FileNotFoundError, ValueError)):
                    run.stage_template()
            with patch.object(run, 'BASE', base):
                folder, paths = run.stage_paths()
                folder.mkdir(parents=True)
                paths['claim.json'].write_text('{}\n')
                with patch.object(run, 'verify', return_value='synthetic'), \
                        patch.object(run, 'require_review'), \
                        patch.object(run, 'exact_budget'), \
                        patch.object(run, 'verify_hold', return_value=type('State', (), {'head_sha256':'0'*64})()):
                    with self.assertRaises(FileExistsError):
                        run.stage_template()

    def test_transitive_money_source_drift_rejects_manifest(self):
        original = run.sha
        for name in ('openrouter_budget_amendment_v3.py',
                     'openrouter_benchmark.py', 'paid_budget_partitions_v4.py',
                     'solar_decide_risk_hold_v1.py'):
            with self.subTest(name=name):
                def changed(path):
                    return '0'*64 if Path(path).name == name else original(path)
                with patch.object(run, 'sha', side_effect=changed):
                    with self.assertRaisesRegex(ValueError, 'manifest'):
                        run.verify()

    def test_real_temporary_child_mock_http_success_unknown_and_no_replay(self):
        item = run.suffix()[0]
        catalog = json.loads((ROOT / 'results/route-audits/solar-openrouter-endpoint-20260930.json').read_text())
        catalog_raw = native.canonical(catalog)
        answers = {}
        for key in KEYS:
            values = list(VALUES[key]); selected = values[0]
            answers[key] = {'type':'choice','choice':selected,
                'probabilities':{value:1 if value==selected else 0 for value in values},
                'confidence':1}
        good_wire = native.canonical({'model':run.prior.solar.VERSION,
            'provider':run.prior.solar.PROVIDER,'answers':answers,
            'usage':{'input_tokens':100,'output_tokens':8,'cost':0.000005}})
        for unknown in (False, True):
            with self.subTest(unknown=unknown), tempfile.TemporaryDirectory() as temp:
                base=Path(temp).resolve();master=base/'master.jsonl'
                master.write_text(json.dumps({'event':'budget','cap_usd':'1'})+'\n')
                budget=base/'budget.json';child=base/('budget-'+run.PARTITION_ID+'.jsonl')
                manifest=base/'manifest.json';manifest.write_text('{}\n')
                folder=base/run.STAGE;folder.mkdir(parents=True)
                review=folder/'development.root-review.json';review.write_text('{"approved":true}\n')
                with patch.object(budget_v4,'CAP',Decimal('1')):
                    partitions.allocate(master,budget,[{'id':run.PARTITION_ID,
                        'cap_usd':'0.50','model':run.prior.solar.MODEL,
                        'provider':run.prior.solar.PROVIDER,'reasoning':run.REASONING}])
                    with patch.object(run,'BASE',base),patch.object(run,'MANIFEST',manifest), \
                            patch.object(run,'BUDGET',budget),patch.object(run,'CHILD',child), \
                            patch.object(run.prior.risk,'MASTER',master), \
                            patch.object(run,'suffix',return_value=[item]), \
                            patch.object(run,'verify',return_value='synthetic'), \
                            patch.object(run,'verify_stage_review'), \
                            patch.dict(os.environ,{'OPENROUTER_API_KEY':'test-token'}):
                        calls=[]
                        def send(payload,token):
                            self.assertEqual(token,'test-token');calls.append(payload)
                            return (429,b'{"error":"rate limit"}') if unknown else (200,good_wire)
                        fetch=lambda:(catalog_raw,catalog)
                        if unknown:
                            with self.assertRaisesRegex(ValueError,'cost unknown'):
                                run.execute(review,fetch=fetch,send=send)
                        else:
                            closure=run.execute(review,fetch=fetch,send=send)
                            self.assertEqual((closure['request_count'],closure['known_valid_count']),(1,1))
                        self.assertEqual(len(calls),1)
                        events=run.jsonl(child)
                        self.assertEqual(sum(e['event']=='reserve' for e in events),1)
                        self.assertEqual(sum(e['event']=='settle' for e in events),0 if unknown else 1)
                        with self.assertRaises(FileExistsError):
                            run.execute(review,fetch=fetch,send=lambda *_:self.fail('Replayed'))

    def test_clean_archive_verify_without_original_private_raw(self):
        if not (ROOT / '.git').exists():
            self.assertFalse((ROOT / 'results/solar-decide-native-full-v1/execution-adapter-v2/fresh3/P2/development.raw.jsonl').exists())
            self.assertEqual(run.verify(),run.sha(run.MANIFEST))
            return
        data=subprocess.check_output(['git','archive','HEAD'],cwd=ROOT)
        with tempfile.TemporaryDirectory() as temp:
            checkout=Path(temp)
            with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as archive:
                archive.extractall(checkout)
            paths=[*run.SOURCES,
                   'results/solar-decide-native-full-v1/final-p2-unsent-v1/manifest.json',
                   'results/solar-decide-native-full-v1/final-p2-unsent-v1/root-review.json']
            for name in paths:
                source=ROOT/name;target=checkout/name
                if source.is_file() and (not target.is_file() or target.read_bytes()!=source.read_bytes()):
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,target)
            env=dict(os.environ,PYTHONPATH=str(checkout/'scripts'))
            result=subprocess.run([sys.executable,'scripts/solar_decide_final_p2_unsent_v1.py','verify'],
                                  cwd=checkout,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__ == '__main__':
    unittest.main()
