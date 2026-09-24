import argparse,copy,json,os,sys,tempfile,unittest
from types import SimpleNamespace
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import anyjev_prompt_execution as e
import anyjev_generation_control as runner

class ExactExecutionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.actual=runner.ROOT
  self.versions={'torch':'2.10.0','transformers':'5.17.0','numpy':'2.2.6','tokenizers':'0.23.2'}
  self.addCleanup(patch.stopall);patch.object(runner,'ROOT',self.root).start();patch.dict(os.environ,{'OMP_NUM_THREADS':'4','MKL_NUM_THREADS':'4'}).start();patch.object(e.importlib.metadata,'version',side_effect=lambda p:self.versions[p]).start()
  sources=['scripts/'+n for n in ['anyjev_generation_control.py','anyjev_prompt_execution.py','anyjev_benchmark.py','frozen_prompt_variants.py','prompt_schedule.py','prompt_execution_gates.py','jev_benchmark.py','development_benchmark.py']]
  for name in sources+['data/pilot/inputs.jsonl','docs/LABELING_GUIDE.md','schemas/judgments.schema.json','prompts/variants-v1/manifest.json','prompts/variants-v1/P1-classifier.txt','prompts/variants-v1/P2-classifier-sop.txt']:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((self.actual/name).read_bytes())
  self.pre=json.loads((self.actual/'results/anyjev-generated-phase2-token-preflight-2026-09-23.json').read_text());self.baseline=e.lines((self.actual/self.pre['baseline_file']).read_bytes())
  self.controls=e.controls_from_baseline(self.baseline[0],40960);patch.object(e.platform,'platform',return_value=self.controls['hardware']).start()
  policy=(self.root/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0];base=runner.control_messages('',policy)[0]['content']
  self.cid='anyjev-qwen06-generated-control';self.pre['baseline_sha256']=self.put('baseline.jsonl',''.join(json.dumps(x)+'\n' for x in self.baseline))['sha256']
  self.config={'id':self.cid,'parent_baseline_id':self.cid,'role':'system','baseline_instruction':self.put('base.txt',base),'parent_baseline':self.put('parent.json',{'id':self.cid,'context_unit':'single_record','controls_sha256':e.g.canonical(self.controls),'baseline_instruction_sha256':e.g.sha(base.encode())}),'controls':self.controls,'controls_sha256':e.g.canonical(self.controls),'batch_membership':[[f'DEV-{i:03d}'] for i in range(1,61)],'conditions':{},'native_execution':{'adapter':e.ADAPTER,'journal':'journal.jsonl','token_preflight':self.put('preflight.json',self.pre),'baseline_predictions':e.binding(self.root/'baseline.jsonl',self.root),'controller_sources':[e.binding(self.root/n,self.root) for n in sources]}}
  for v in ['P1','P2']:
   instruction=runner.control_messages('',policy,v,self.cid)[0]['content'];self.config['conditions'][v]={'instruction':self.put(v+'.txt',instruction),'output_paths':{'smoke':v+'-smoke.jsonl','development':v+'-development.jsonl'}}
  self.manifest={'contract':'prompt-execution-gates-v1','frozen_utc':'2026-09-24T00:00:00Z','inputs':e.binding(self.root/'data/pilot/inputs.jsonl',self.root),'schema':e.binding(self.root/'schemas/judgments.schema.json',self.root),'prompt_bundle':e.binding(self.root/'prompts/variants-v1/manifest.json',self.root),'roster':self.put('roster.json',{'entries':[{'id':self.cid,'parent_baseline_id':self.cid,'state':'scheduled','reason':'complete baseline'}]}),'source_inventory':self.put('inventory.json',{'entries':[{'id':self.cid,'disposition':'completed','reason':'60 terminal'}]}),'schedule':self.put('schedule.json',{'order':[{'id':self.cid,'conditions':['P1','P2']}]}),'configurations':[self.config],'manifest_scope':[self.cid]}
  self.args=argparse.Namespace(prompt_variant='P1',parent_baseline_id=self.cid,execution_manifest=str(self.root/'manifest.json'),execution_configuration=self.cid,execution_stage='smoke',execution_journal=str(self.root/'journal.jsonl'),limit=3,output=str(self.root/'P1-smoke.jsonl'),model_path=str(self.root/'model'),revision=self.controls['model_revision'],device='mps',dtype='bfloat16',max_input_tokens=4096,max_new_tokens=4096)
  self.freeze()
 def put(self,name,value):
  p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value if isinstance(value,str) else json.dumps(value));return e.binding(p,self.root)
 def freeze(self):self.args.execution_manifest_sha256=self.put('manifest.json',self.manifest)['sha256']
 def plan(self):return e.load_plan(self.args,self.root)
 def test_exact_manifest_accepts_scoped_complete_baseline(self):self.assertEqual(self.plan()['stage'],'smoke')
 def test_fail_closed_before_any_model_load(self):
  for field,value in [('dtype','float32'),('max_new_tokens',2048),('limit',60),('execution_journal',str(self.root/'other'))]:
   with self.subTest(field=field):
    args=copy.copy(self.args);setattr(args,field,value)
    with self.assertRaises(ValueError):e.load_plan(args,self.root)
  (self.root/'scripts/anyjev_generation_control.py').write_text('changed')
  with self.assertRaisesRegex(ValueError,'hash mismatch'):self.plan()
 def test_incomplete_inventory_and_counterbalance_rejected(self):
  self.manifest['source_inventory']=self.put('inventory.json',{'entries':[{'id':self.cid,'disposition':'executable','reason':'pending'}]});self.freeze()
  with self.assertRaisesRegex(ValueError,'Executable'):self.plan()
 def test_global_order_not_shard_parity(self):
  other={'id':'earlier','parent_baseline_id':'earlier','state':'scheduled','reason':'complete'}
  self.manifest['roster']=self.put('roster.json',{'entries':[other,{'id':self.cid,'parent_baseline_id':self.cid,'state':'scheduled','reason':'complete'}]})
  self.manifest['source_inventory']=self.put('inventory.json',{'entries':[{'id':x,'disposition':'completed','reason':'complete'} for x in ['earlier',self.cid]]})
  self.manifest['schedule']=self.put('schedule.json',{'order':[{'id':'earlier','conditions':['P1','P2']},{'id':self.cid,'conditions':['P2','P1']}]});self.freeze();self.plan()
  self.manifest['schedule']=self.put('schedule.json',{'order':[{'id':'earlier','conditions':['P1','P2']},{'id':self.cid,'conditions':['P1','P2']}]});self.freeze()
  with self.assertRaisesRegex(ValueError,'Counterbalance'):self.plan()
 def fake_tokenizer(self,plan):
  model=Path(self.args.model_path);model.mkdir();(model/'download-manifest.json').write_text('{}');(model/'config.json').write_text(json.dumps({'max_position_embeddings':40960}));plan['preflight']['artifact_manifest_sha256']=e.g.sha(b'{}');plan['preflight']['artifact_files']={'config.json':e.g.sha((model/'config.json').read_bytes())}
  counts={}
  class Tok:
   pad_token_id=1;eos_token_id=2
   def apply_chat_template(self,messages,**kwargs):return json.dumps(messages,sort_keys=True)
   def encode(self,prompt,**kwargs):return list(range(counts[prompt]))
  tok=Tok()
  for variant in ['P0','P1','P2']:
   for row,record in zip(plan['rows'],plan['preflight']['conditions'][variant]['records']):
    prompt=tok.apply_chat_template(runner.control_messages(row['feedback'],plan['policy'],variant,self.cid));counts[prompt]=record['input_tokens'];record['rendered_prompt_sha256']=e.g.sha(prompt.encode())
  return tok
 def test_all180_exact_token_checks_and_tampering(self):
  plan=self.plan();tok=self.fake_tokenizer(plan);audit=e.exact_token_check(plan,self.args,tok);self.assertEqual(len(audit['records']),60)
  plan['preflight']['conditions']['P2']['records'][-1]['input_tokens']+=1
  with self.assertRaisesRegex(ValueError,'Exact rendered'):e.exact_token_check(plan,self.args,tok)
 def test_historical_count_parity_required(self):
  plan=self.plan();tok=self.fake_tokenizer(plan);plan['baseline'][-1]['input_tokens']+=1
  with self.assertRaisesRegex(ValueError,'Historical'):e.exact_token_check(plan,self.args,tok)
 def inspected_fixture(self,invalid=False):
  plan=self.plan();tok=self.fake_tokenizer(plan);Path(self.args.model_path,'generation_config.json').write_text(json.dumps({'eos_token_id':2}))
  good={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
  raw_text='```json fenced```' if invalid else json.dumps(good);tok.decode=lambda ids,**kwargs:raw_text
  records=[];declared=[]
  for item,evidence,baseline in zip(plan['rows'][:3],plan['preflight']['conditions']['P1']['records'],plan['baseline']):
   messages=runner.control_messages(item['feedback'],plan['policy'],'P1',self.cid);prompt=tok.apply_chat_template(messages)
   row={**baseline,'messages':messages,'request_sha256':e.g.canonical(messages),'rendered_prompt_sha256':e.g.sha(prompt.encode()),'input_tokens':evidence['input_tokens'],'execution_manifest':plan['manifest_binding'],'execution_stage':'smoke','native_controls':self.controls,'started_utc':'2026-09-24T00:01:00Z','finished_utc':'2026-09-24T00:01:05Z','raw_response':raw_text,'status':'invalid_output' if invalid else 'ok','prediction':None if invalid else good,'eos_token_ids':[2],'generated_token_ids':[100,2],'output_tokens':2,'finish_reason':'stop'}
   records.append(row);declared.append({k:row[k] for k in ('id','status','prediction')})
  raw=self.put('P1-smoke.jsonl',''.join(json.dumps(x)+'\n' for x in records));inspection={'manifest':plan['manifest_binding'],'condition':'P1','inspector':'offline unit test fixture','inspected_utc':'2026-09-24T00:02:00Z','raw_attempts':raw,'records':declared}
  self.args.smoke_inspection=str(self.root/'inspection.json');self.args.smoke_inspection_sha256=self.put('inspection.json',inspection)['sha256']
  return plan,tok,records,inspection
 def test_raw_smoke_inspection_and_eos_tampering(self):
  plan,tok,records,inspection=self.inspected_fixture();e.inspect_smoke(plan,self.args,tok)
  records[0]['generated_token_ids'][-1]=9
  inspection['raw_attempts']=self.put('P1-smoke.jsonl',''.join(json.dumps(x)+'\n' for x in records));self.args.smoke_inspection_sha256=self.put('inspection.json',inspection)['sha256']
  with self.assertRaisesRegex(ValueError,'termination'):e.inspect_smoke(plan,self.args,tok)
 def test_intrinsic_invalid_requires_explicit_unchanged_acceptance(self):
  plan,tok,records,inspection=self.inspected_fixture(invalid=True)
  with self.assertRaisesRegex(ValueError,'unchanged acceptance'):e.inspect_smoke(plan,self.args,tok)
  for row in inspection['records']:row.update(accepted_unchanged=True,failure_class='intrinsic_schema',inspection_reason='Fences retained; no repair, ended EOS')
  self.args.smoke_inspection_sha256=self.put('inspection.json',inspection)['sha256'];e.inspect_smoke(plan,self.args,tok)
 def test_mocked_smoke_execution_journals_raw_failures_without_repair(self):
  plan=self.plan();tok=self.fake_tokenizer(plan);measured=e.exact_token_check(plan,self.args,tok);self.args.config_note='offline fixture'
  class Tensor:
   def __init__(self,n):self.shape=[1,n]
   def to(self,device):return self
  class Tokenizer:
   pad_token_id=1;eos_token_id=2
   def apply_chat_template(self,*a,**kw):return tok.apply_chat_template(*a,**kw)
   def __call__(self,prompt,**kw):return {'input_ids':Tensor(len(tok.encode(prompt)))}
   def decode(self,*a,**kw):return '```json fenced```'
  class Generated:
   def __getitem__(self,key):return SimpleNamespace(tolist=lambda:[100,2])
  class Model:
   config=SimpleNamespace(max_position_embeddings=40960);generation_config=SimpleNamespace(eos_token_id=2)
   def to(self,device):return self
   def eval(self):return self
   def parameters(self):return iter([SimpleNamespace(device='mps:0',dtype='torch.bfloat16')])
   def generate(self,**kw):return Generated()
  torch=SimpleNamespace(bfloat16='bfloat16',inference_mode=nullcontext)
  transformers=SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**kw:Tokenizer()),AutoModelForCausalLM=SimpleNamespace(from_pretrained=lambda *a,**kw:Model()))
  with patch.object(e,'load_plan',return_value=plan),patch.object(e,'exact_token_check',return_value=measured),patch.object(runner,'verify_artifact',return_value={'repo':self.controls['model']}),patch.dict(sys.modules,{'torch':torch,'transformers':transformers}):e.execute(self.args,self.root)
  raw=e.lines(Path(self.args.output).read_bytes());self.assertEqual(len(raw),3);self.assertTrue(all(r['status']=='invalid_output' and r['prediction'] is None and r['raw_response']=='```json fenced```' for r in raw))
  journal=e.lines((self.root/'journal.jsonl').read_bytes());self.assertEqual([x.get('stage') for x in journal if x['event']=='claimed'],['smoke']);self.assertEqual(journal[-1]['status'],'completed')
  self.assertEqual(len(e.lines(Path(self.args.output+'.events.jsonl').read_bytes())),6)
 def test_development_requires_inspection_not_only_token_fit(self):
  plan=self.plan();tok=self.fake_tokenizer(plan)
  with self.assertRaisesRegex(ValueError,'inspection'):e.inspect_smoke(plan,self.args,tok)

if __name__=='__main__':unittest.main()
