import json,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prompt_execution_gates as g
import evaluate_prompt_variants as e
import codex_benchmark as codex
ROOT=Path(__file__).resolve().parents[1]
class SubscriptionSmokeTests(unittest.TestCase):
 def fixture(self,root,kind):
  folder=ROOT/'results/subscription-batch-p0-2026-09-23'/('sonnet5-medium-phase2-batch10-p0' if kind=='claude_batch_v1' else 'codex-gpt-5.6-luna-low-phase2-batch10-p0')
  name='smoke.jsonl.batches.jsonl' if kind=='claude_batch_v1' else 'smoke-attempts.jsonl';raw=[json.loads(x) for x in (folder/name).read_text().splitlines()];pred=[json.loads(x) for x in (folder/'smoke.jsonl').read_text().splitlines()];r=raw[0]
  inputs=[json.loads(x) for x in (ROOT/'data/pilot/inputs.jsonl').read_text().splitlines()];policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
  text=r['request']['system'] if kind=='claude_batch_v1' else codex.baseline_instruction(policy,'batch10');role='system' if kind=='claude_batch_v1' else 'cli_combined_prompt'
  controls={'model':r['requested_model'],'effort':r['effort'],'runtime':r['cli_version'],'adapter_controls':e.extract_claude_controls(r) if kind=='claude_batch_v1' else e.extract_codex_controls(r)}
  smoke={'extractor':kind,'inspection':'passed','records':[{'id':p['id'],'status':p['status'],'prediction':p['prediction']} for p in pred],'started_utc':r['started_utc'],'finished_utc':(g.stamp(r['started_utc'])+timedelta(seconds=r['elapsed_seconds']+1)).isoformat()}
  self.save(root,smoke,raw,pred);return [smoke,inputs,text,controls,role,root],raw,pred
 def save(self,root,smoke,raw,pred):
  for key,name,rows in [('raw_attempts','raw.jsonl',raw),('raw_predictions','pred.jsonl',pred)]:
   p=root/name;p.write_text('\n'.join(json.dumps(x) for x in rows));smoke[key]={'file':name,'sha256':g.sha(p.read_bytes())}
 def test_saved_smoke_contracts(self):
  for kind in ('claude_batch_v1','codex_batch_v1'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
    args,_,_=self.fixture(Path(d),kind);result=g.verify_subscription_smoke(*args);self.assertTrue(result['verified']);self.assertEqual(result['records'],3);self.assertTrue(result['limitations'])
 def test_raw_tampering_and_no_retry_omission(self):
  for kind in ('claude_batch_v1','codex_batch_v1'):
   for change in ('input','identity','response','timing','duplicate','output','phase'):
    with self.subTest(kind=kind,change=change),tempfile.TemporaryDirectory() as d:
     args,raw,pred=self.fixture(Path(d),kind);r=raw[0]
     if change=='input':r['request']['system' if kind=='claude_batch_v1' else 'prompt']='wrong'
     if change=='identity':r['requested_model']='other'
     if change=='response':r['prediction']={}
     if change=='timing':args[0]['finished_utc']=args[0]['started_utc']
     if change=='duplicate':raw.append(dict(r))
     if change=='output':pred[0]['prediction']={}
     if change=='phase':r['phase']='development'
     self.save(Path(d),args[0],raw,pred)
     with self.assertRaises((ValueError,KeyError)):g.verify_subscription_smoke(*args)
if __name__=='__main__':unittest.main()
