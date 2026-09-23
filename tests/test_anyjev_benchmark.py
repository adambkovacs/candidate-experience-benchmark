import json
import hashlib
from unittest import mock
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import anyjev_benchmark as runner

class AnyJevTests(unittest.TestCase):
    def test_four_choice_specs_keep_entire_policy_and_semantic_options(self):
        specs=runner.question_specs('FULL POLICY SENTINEL')
        self.assertEqual([s['id'] for s in specs],list(runner.KEYS))
        for spec in specs:
            self.assertIn('FULL POLICY SENTINEL',spec['text'])
            self.assertEqual(len(spec['options']),len(runner.VALUES[spec['id']]))
            for label,text in zip(runner.VALUES[spec['id']],spec['options']):
                self.assertTrue(text.startswith(label+': '))
                self.assertGreater(len(text),len(label)+3)
        self.assertNotIn('proposed_labels',json.dumps(specs))

    def test_only_label_free_levels_and_fresh_instances(self):
        class Capture:
            def __init__(self,backend,**kw):self.kw=kw
        a=runner.make_decider(None,'L0',Capture)
        b=runner.make_decider(None,'raw',Capture)
        self.assertIsNot(a,b)
        self.assertEqual(a.kw['prior'],'content_free')
        self.assertFalse(a.kw['adapt'])
        self.assertFalse(a.kw['shared_prefix'])
        self.assertFalse(a.kw['adaptive_shifts'])
        for level in ['L1','L2','auto']:
            with self.assertRaises(ValueError):runner.make_decider(None,level,Capture)

    def test_full_context_guard_rejects_before_backend(self):
        class Base:
            tokenizer=SimpleNamespace(encode=lambda p,**kw:list(p))
            def next_token_logprobs(self,prompts,ids):self.called=True;return [[0]]
        b=runner.guarded_backend_class(Base)();b.context_limit=4;b.prompt_token_counts=[];b.called=False
        with self.assertRaises(ValueError):b.next_token_logprobs(['12345'],[[1]])
        self.assertFalse(b.called)
        self.assertEqual(b.next_token_logprobs(['1234'],[[1]]),[[0]])
        self.assertEqual(b.prompt_token_counts,[4])

    def test_prediction_maps_indices_and_rejects_wrong_level_or_probabilities(self):
        qs=[SimpleNamespace(id=k) for k in runner.KEYS]
        class Result(dict):level='L0'
        r=Result({q.id:SimpleNamespace(level='L0',probs=[1]+[0]*(len(runner.VALUES[q.id])-1)) for q in qs})
        self.assertEqual(runner.extract_prediction(r,qs,'L0'),{k:runner.VALUES[k][0] for k in runner.KEYS})
        r[qs[0].id].probs[0]=float('nan')
        with self.assertRaises(ValueError):runner.extract_prediction(r,qs,'L0')
        r.level='L1'
        with self.assertRaises(ValueError):runner.extract_prediction(r,qs,'L0')

    def test_source_rejects_dirty_checkout(self):
        with mock.patch.object(runner.subprocess,'check_output',side_effect=[runner.SOURCE_REVISION,' M anyjev/decider.py']):
            with self.assertRaisesRegex(ValueError,'uncommitted'):runner.verify_source('/source')

    def test_non_lfs_same_size_mutation_fails_hash(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);data=b'abc';(p/'model.safetensors').write_bytes(b'xyz')
            sha=hashlib.sha1(b'blob 3\0'+data).hexdigest()
            (p/'download-manifest.json').write_text(json.dumps({'sha':'rev','siblings':[{'rfilename':'model.safetensors','size':3,'blobId':sha}]}))
            with self.assertRaisesRegex(ValueError,'checksum'):runner.verify_artifact(p,'rev')

    def test_artifact_rejects_classifier_and_incomplete_weights(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'model.safetensors').write_bytes(b'abc')
            (p/'config.json').write_text(json.dumps({'architectures':['Qwen3ForSequenceClassification']}))
            files=[{'rfilename':f.name,'size':f.stat().st_size, 'blobId':hashlib.sha1(b'blob '+str(f.stat().st_size).encode()+b'\0'+f.read_bytes()).hexdigest()} for f in p.iterdir()]
            (p/'download-manifest.json').write_text(json.dumps({'sha':'revision','siblings':files}))
            with self.assertRaisesRegex(ValueError,'causal-LM'):runner.verify_artifact(p,'revision')
            (p/'model.safetensors').write_bytes(b'a')
            with self.assertRaisesRegex(ValueError,'Incomplete'):runner.verify_artifact(p,'revision')

if __name__=='__main__':unittest.main()
