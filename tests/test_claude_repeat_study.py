"""Offline guards for the bounded Claude subscription repeat lane."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import claude_repeat_study as study

class ClaudeRepeatStudyTest(unittest.TestCase):
    def test_frozen_reconstruction_and_rotation(self):
        for repeat,order in study.ORDERS.items():
            plan=study.plan_data(repeat)
            self.assertEqual(plan['condition_order'],order)
            self.assertEqual(plan['historical_pass_order'],['P0','P2','P1'])
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(plan['model'],'claude-opus-5-5')
            for binding in plan['source_bindings']:
                self.assertEqual(hashlib.sha256((ROOT/binding['path']).read_bytes()).hexdigest(),binding['sha256'])
            for condition,data in plan['conditions'].items():
                self.assertEqual(len(data['development']),6)
                self.assertEqual(data['smoke']['record_ids'],['DEV-001','DEV-002','DEV-003'])
                self.assertEqual([rid for r in data['development'] for rid in r['record_ids']],[f'DEV-{i:03d}' for i in range(1,61)])
                for request in [data['smoke'],*data['development']]:
                    self.assertEqual(request['request']['input'],json.loads(request['input_text']))
                    self.assertEqual(set(request['request']['input']),{'records'})
                    self.assertTrue(all(set(r)=={'id','feedback'} for r in request['request']['input']['records']))
                    self.assertNotIn('prediction',json.dumps(request))
                    self.assertNotIn('proposed_labels',json.dumps(request))

    def test_manifest_binding_and_no_skipped_conditions(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study,'BASE',Path(temp)):
            study.prepare()
            for repeat in study.ORDERS:
                path=study.BASE/repeat/'manifest.json'
                self.assertEqual(study.verify_manifest(repeat,study.sha(path)),study.plan_data(repeat))
                with self.assertRaisesRegex(ValueError,'hash mismatch'):
                    study.verify_manifest(repeat,'0'*64)
            with patch.object(study,'preflight',side_effect=AssertionError('preflight called')):
                with self.assertRaisesRegex(ValueError,'Previous condition'):
                    study.run_phase(study.plan_data('repeat2'),'P1','smoke','/unused','/unused','0'*64)
                with self.assertRaisesRegex(ValueError,'Repeat two'):
                    study.run_phase(study.plan_data('repeat3'),'P1','smoke','/unused','/unused','0'*64)
            self.assertFalse((study.BASE/'repeat2'/'P1'/'smoke.claim.json').exists())

    def test_no_replay_after_claim_or_ambiguous_intent(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study,'BASE',Path(temp)):
            plan=study.plan_data('repeat2')
            folder,claim,attempts,records,journal=study.paths('repeat2','P2','smoke')
            folder.mkdir(parents=True)
            claim.write_text('{}\n')
            journal.write_text('{"event":"dispatch_intent","batch_index":0}\n')
            with patch.object(study,'preflight',side_effect=AssertionError('preflight called')):
                with self.assertRaises(FileExistsError):
                    study.run_phase(plan,'P2','smoke','/unused','/unused','0'*64)
            self.assertFalse(study.completed('repeat2','P2','smoke'))

    def test_api_auth_rejected_before_claim_and_dispatch(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study,'BASE',Path(temp)):
            calls=[]
            def fake_run(cmd,**kwargs):
                calls.append(cmd)
                return SimpleNamespace(stdout=json.dumps({'loggedIn':True,'authMethod':'apiKey','apiProvider':'firstParty'}),returncode=0)
            with patch.object(study,'preflight',return_value={'usage_credits_off':True}),patch.object(study.subprocess,'run',side_effect=fake_run):
                with self.assertRaisesRegex(ValueError,'Claude.ai subscription login required'):
                    study.run_phase(study.plan_data('repeat2'),'P2','smoke','/fake/claude','/private/receipt','a'*64)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0],['/fake/claude','--safe-mode','auth','status'])
            self.assertFalse(study.paths('repeat2','P2','smoke')[1].exists())

    def test_malformed_stdout_is_durable_before_parse_and_stops(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study,'BASE',Path(temp)):
            plan=study.plan_data('repeat2')
            manifest=study.BASE/'repeat2'/'manifest.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{}')
            calls=[]
            def fake_run(cmd,**kwargs):
                calls.append(cmd)
                if cmd[1:4]==['--safe-mode','auth','status']:
                    return SimpleNamespace(stdout=json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'}),returncode=0)
                if cmd[1:] == ['--version']:
                    return SimpleNamespace(stdout=study.RUNTIME+'\n',returncode=0)
                return SimpleNamespace(stdout='{invalid-json',stderr='upstream diagnostic',returncode=1)
            with patch.object(study,'preflight',return_value={'usage_credits_off':True}),patch.object(study.subprocess,'run',side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError,'Stopped on first non-ok'):
                    study.run_phase(plan,'P2','smoke','/fake/claude','/private/receipt','a'*64)
            folder,claim,attempts,records,journal=study.paths('repeat2','P2','smoke')
            raw=folder/'smoke.batch-000.raw.jsonl'
            self.assertTrue(raw.exists())
            saved=json.loads(raw.read_text())
            self.assertEqual(saved['stdout'],'{invalid-json')
            self.assertEqual(saved['stderr'],'upstream diagnostic')
            self.assertEqual(saved['input_sha256'],json.loads(attempts.read_text())['input_sha256'])
            attempt=json.loads(attempts.read_text())
            self.assertEqual(attempt['raw_capture_sha256'],study.sha(raw))
            self.assertEqual(attempt['status'],'service_error')
            self.assertEqual(json.loads(journal.read_text().splitlines()[-1])['event'],'phase_stopped')
            self.assertFalse(study.completed('repeat2','P2','smoke'))
            with patch.object(study,'preflight',side_effect=AssertionError('preflight called')):
                with self.assertRaises(FileExistsError):
                    study.run_phase(plan,'P2','smoke','/fake/claude','/private/receipt','a'*64)
            self.assertEqual(len(calls),3)

    def test_development_requires_inspected_smoke(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(study,'BASE',Path(temp)):
            with patch.object(study,'preflight',side_effect=AssertionError('preflight called')):
                with self.assertRaisesRegex(ValueError,'Inspected smoke'):
                    study.run_phase(study.plan_data('repeat2'),'P2','development','/unused','/unused','0'*64)

if __name__=='__main__':unittest.main()
