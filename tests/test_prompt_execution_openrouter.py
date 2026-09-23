import copy,json,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prompt_execution_gates as g
from evaluate_prompt_variants import extract_controls
ROOT=Path(__file__).resolve().parents[1]
class OpenRouterSmokeTests(unittest.TestCase):
 def fixture(self,root):
  raw=[json.loads(x) for x in (ROOT/'results/openrouter-qwen35-on-2026-09-23/smoke.jsonl').read_text().splitlines()];row=raw[0];request=row['request'];schema=request['response_format']['json_schema']['schema'];text=request['messages'][0]['content']
  inputs=[{'id':r['id'],'feedback':json.loads(r['request']['messages'][1]['content'])['feedback']} for r in raw]
  controls={'adapter_controls':extract_controls(row),'model':row['requested_model'],'effort':row['reasoning_effort'],'quantization':row['quantization'],'runtime':row['runtime'],'hardware':row['hardware'],'retry_policy':row['retry_policy'],'output_reserve_tokens':request['max_tokens'],'context_tokens':row['provider_endpoint']['context_length'],'sampling':{'temperature':request['temperature']},'output_method':'json_schema','parsing':'strict_json'}
  smoke={'inspection':'passed','records':[{'id':r['id'],'status':r['status'],'prediction':r['prediction']} for r in raw],'started_utc':raw[0]['started_utc'],'finished_utc':(g.stamp(raw[-1]['started_utc'])+timedelta(seconds=raw[-1]['elapsed_seconds']+1)).isoformat()}
  self.save(root,smoke,raw);return smoke,inputs,text,schema,controls,'system',root,raw
 def save(self,root,smoke,raw):
  p=root/'smoke.jsonl';p.write_text('\n'.join(json.dumps(r) for r in raw));smoke['raw_attempts']={'file':p.name,'sha256':g.sha(p.read_bytes())}
 def test_actual_saved_smoke_without_references(self):
  with tempfile.TemporaryDirectory() as d:
   args=self.fixture(Path(d));result=g.verify_openrouter_smoke(*args[:-1]);self.assertTrue(result['verified']);self.assertEqual(result['attempts'],3)
 def test_tampering_transport_and_truncation(self):
  for kind in ('input','hash','provider','model','tool','length','usage','schema','status','ids','time'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d:
    args=self.fixture(Path(d));smoke,_,_,_,_,_,root,raw=args;r=raw[0]
    if kind=='input':r['request']['messages'][1]['content']='{"feedback":"changed"}'
    if kind=='hash':r['request_sha256']='bad'
    if kind=='provider':r['raw_response']['provider']='other'
    if kind=='model':r['raw_response']['model']='other'
    if kind=='tool':r['raw_response']['choices'][0]['message']['tool_calls']=[{}]
    if kind=='length':r['raw_response']['choices'][0]['finish_reason']='length'
    if kind=='usage':r['usage']={'cost':99}
    if kind=='schema':r['request']['response_format']={}
    if kind=='status':r['status']='service_error'
    if kind=='ids':r['id']='DEV-004'
    if kind=='time':smoke['finished_utc']=smoke['started_utc']
    self.save(root,smoke,raw)
    with self.assertRaises(ValueError):g.verify_openrouter_smoke(*args[:-1])
 def test_intrinsic_invalid_needs_explicit_acceptance(self):
  with tempfile.TemporaryDirectory() as d:
   args=self.fixture(Path(d));smoke,_,_,_,_,_,root,raw=args;r=raw[0];r['raw_response']['choices'][0]['message']['content']='not json';r.update(status='invalid_output',prediction=None);smoke['records'][0].update(status='invalid_output',prediction=None);self.save(root,smoke,raw)
   with self.assertRaises(ValueError):g.verify_openrouter_smoke(*args[:-1])
   smoke['inspection']='accepted_unchanged';smoke['records'][0].update(failure_class='intrinsic_schema',accepted_unchanged=True,inspection_reason='Malformed JSON preserved, no repair.')
   self.assertEqual(g.verify_openrouter_smoke(*args[:-1])['intrinsic_invalid_outputs'],1)
 def test_gate_dispatch_keeps_token_and_schedule_blockers(self):
  from test_prompt_execution_gates import GateTests
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   helper=GateTests();root,m=helper.fixture(d)
   for config in m['configurations']:
    parent=g.json_bound(config['parent_baseline'],root);parent['context_unit']='single_record';config['parent_baseline']=helper.write(root,config['id']+'-parent.json',parent)
    config['batch_membership']=[[f'DEV-{i:03}'] for i in range(1,61)]
    for cond in config['conditions'].values():
     token=g.json_bound(cond['token_evidence'],root);token['requests']=[{**token['requests'][0],'record_ids':ids} for ids in config['batch_membership']];cond['token_evidence']=helper.write(root,cond['token_evidence']['file'],token)
     smoke=g.json_bound(cond['smoke_evidence'],root);smoke['extractor']='openrouter_paid_v1';cond['smoke_evidence']=helper.write(root,cond['smoke_evidence']['file'],smoke)
   with patch.object(g,'verify_openrouter_smoke',return_value={'verified':True}) as verify:
    result=g.validate(m,root)
   self.assertEqual(verify.call_count,6);self.assertEqual(len(result['blockers']),2);self.assertFalse(result['execution_allowed'])
if __name__=='__main__':unittest.main()
