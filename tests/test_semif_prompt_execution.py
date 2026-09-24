import copy,json,sys,unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import semif_prompt_execution as e
import specialist_benchmark as runner
import test_anyjev_prompt_execution as fixture

class SemifExactTests(unittest.TestCase):
 put=fixture.ExactExecutionTests.put
 freeze=fixture.ExactExecutionTests.freeze
 def setUp(self):
  fixture.ExactExecutionTests.setUp(self);patch.object(runner,'ROOT',self.root).start();self.versions.update({'mlx':'0.32.2','mlx-lm':'0.32.0','laya':'0.3.4','semif-phase1':'0.1.0'})
  self.cid='semif-generated-bf16';self.pre=json.loads((self.actual/'results/semif-generated-phase2-token-preflight-2026-09-23.json').read_text());self.baseline=e.lines((self.actual/'results/semif-generated-bf16-2026-09-23/development.jsonl').read_bytes())
  for row in self.baseline:row['requested_model']=str(self.root/'model');row['metadata']['source']=str(self.root/'model')
  self.controls=e.controls_from_baseline(self.baseline[0],262144);self.config.update(id=self.cid,parent_baseline_id=self.cid,controls=self.controls,controls_sha256=e.g.canonical(self.controls))
  base=e.g.bound(self.config['baseline_instruction'],self.root).decode();self.config['parent_baseline']=self.put('parent.json',{'id':self.cid,'context_unit':'single_record','controls_sha256':e.g.canonical(self.controls),'baseline_instruction_sha256':e.g.sha(base.encode())})
  names=['specialist_benchmark.py','semif_prompt_execution.py','anyjev_prompt_execution.py','frozen_prompt_variants.py','prompt_schedule.py','prompt_execution_gates.py','jev_benchmark.py','development_benchmark.py']
  for name in names:(self.root/'scripts'/name).write_bytes((self.actual/'scripts'/name).read_bytes())
  self.config['native_execution']={'adapter':e.ADAPTER,'journal':'journal.jsonl','token_preflight':self.put('preflight.json',self.pre),'baseline_predictions':self.put('baseline.jsonl',''.join(json.dumps(x)+'\n' for x in self.baseline)),'controller_sources':[e.binding(self.root/'scripts'/n,self.root) for n in names]}
  self.manifest.update(roster=self.put('roster.json',{'entries':[{'id':self.cid,'parent_baseline_id':self.cid,'state':'scheduled','reason':'complete'}]}),source_inventory=self.put('inventory.json',{'entries':[{'id':self.cid,'disposition':'completed','reason':'complete'}]}),schedule=self.put('schedule.json',{'order':[{'id':self.cid,'conditions':['P1','P2']}]}),manifest_scope=[self.cid]);self.args.parent_baseline_id=self.cid;self.args.execution_configuration=self.cid;self.args.kind='semif';self.args.mode='generated';self.args.bits=None;self.args.offset=0;self.args.max_tokens=4096;self.args.revision=self.baseline[0]['artifact_revision'];self.freeze()
 def plan(self):return e.load_plan(self.args,self.root)
 def test_native_manifest_and_historical_limitation(self):
  plan=self.plan();self.assertIn('source_reconstructed',plan['configuration']['controls']['historical_prompt_evidence'])
 def test_direct_and_quantization_context_changes_rejected(self):
  for field,value in [('kind','laya'),('mode','direct'),('bits',4),('offset',1),('max_tokens',8192),('device','cpu')]:
   with self.subTest(field=field):
    args=copy.copy(self.args);setattr(args,field,value)
    with self.assertRaises(ValueError):e.load_plan(args,self.root)
 def fake_tok(self,plan):
  model=Path(self.args.model_path);model.mkdir();(model/'config.json').write_text(json.dumps({'text_config':{'max_position_embeddings':262144}}));counts={}
  class Tok:
   bos_token=None
   def apply_chat_template(self,messages,**kwargs):return json.dumps(messages,sort_keys=True)
   def encode(self,prompt,**kwargs):return list(range(counts[prompt]))
  tok=Tok()
  for variant in ['P0','P1','P2']:
   for row,record in zip(plan['rows'],plan['preflight']['conditions'][variant]['records']):
    prompt=tok.apply_chat_template(runner.generated_messages(row['feedback'],plan['policy'],variant,self.cid));counts[prompt]=record['generation_input_tokens'];record['rendered_prompt_sha256']=e.g.sha(prompt.encode());record['generation_token_ids_sha256']=e.g.sha(json.dumps(list(range(counts[prompt]))).encode())
  return tok
 def test_all180_native_guard_and_generation_token_ids(self):
  plan=self.plan();tok=self.fake_tok(plan);result=e.exact_token_check(plan,self.args,tok);self.assertEqual(len(result['records']),60);self.assertIn('no historical',result['historical_P0_evidence'])
  plan['preflight']['conditions']['P2']['records'][-1]['generation_token_ids_sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'token mismatch'):e.exact_token_check(plan,self.args,tok)
 def test_actual_generation_special_token_rule_checked(self):
  plan=self.plan();tok=self.fake_tok(plan);original=tok.encode
  tok.encode=lambda text,**kw:original(text,**kw)+([999] if 'add_special_tokens' in kw else [])
  with self.assertRaisesRegex(ValueError,'token mismatch'):e.exact_token_check(plan,self.args,tok)
 def test_smoke_inspection_required(self):
  plan=self.plan();tok=self.fake_tok(plan)
  with self.assertRaisesRegex(ValueError,'inspection'):e.inspect_smoke(plan,self.args,tok)
 def inspected_fixture(self,invalid=False):
  plan=self.plan();tok=self.fake_tok(plan);records=[];declared=[];text='{"type":"object"}' if invalid else '{"sentiment":"positive","follow_up_needed":"no","serious_concern_reported":"no","testimonial_potential":"yes"}'
  for row,base,evidence in zip(plan['rows'][:3],plan['baseline'],plan['preflight']['conditions']['P1']['records']):
   messages=runner.generated_messages(row['feedback'],plan['policy'],'P1',self.cid);prompt=tok.apply_chat_template(messages)
   raw={**base,'messages':messages,'generated_request_sha256':e.g.canonical(messages),'rendered_prompt_sha256':e.g.sha(prompt.encode()),'input_tokens':evidence['generation_input_tokens'],'execution_stage':'smoke','execution_manifest':plan['manifest_binding'],'native_controls':self.controls,'started_utc':'2026-09-24T00:01:00Z','finished_utc':'2026-09-24T00:01:05Z','stream_events':[{'text':text,'token':2,'prompt_tokens':evidence['generation_input_tokens'],'finish_reason':'stop'}],'eos_token_ids':[2],'raw_response':{'content':text,'finish_reason':'stop'},'prediction':json.loads(text),'status':'invalid_output' if invalid else 'ok'}
   records.append(raw);declared.append({k:raw[k] for k in ['id','prediction','status']})
  inspection={'manifest':plan['manifest_binding'],'condition':'P1','inspector':'offline test','inspected_utc':'2026-09-24T00:02:00Z','raw_attempts':self.put('P1-smoke.jsonl',''.join(json.dumps(x)+'\n' for x in records)),'records':declared}
  self.args.smoke_inspection=str(self.root/'inspection.json');self.args.smoke_inspection_sha256=self.put('inspection.json',inspection)['sha256'];return plan,tok,records,inspection
 def test_smoke_native_stream_tampering_and_inspection(self):
  plan,tok,records,inspection=self.inspected_fixture();e.inspect_smoke(plan,self.args,tok);records[0]['stream_events'][0]['token']=9
  inspection['raw_attempts']=self.put('P1-smoke.jsonl',''.join(json.dumps(x)+'\n' for x in records));self.args.smoke_inspection_sha256=self.put('inspection.json',inspection)['sha256']
  with self.assertRaisesRegex(ValueError,'truncation/token'):e.inspect_smoke(plan,self.args,tok)
 def test_schema_copy_needs_explicit_unchanged_acceptance(self):
  plan,tok,records,inspection=self.inspected_fixture(invalid=True)
  with self.assertRaisesRegex(ValueError,'unchanged acceptance'):e.inspect_smoke(plan,self.args,tok)
  for row in inspection['records']:row.update(accepted_unchanged=True,failure_class='intrinsic_schema',inspection_reason='Schema copied; native EOS, no repair')
  self.args.smoke_inspection_sha256=self.put('inspection.json',inspection)['sha256'];e.inspect_smoke(plan,self.args,tok)
 def test_mocked_native_smoke_keeps_invalid_schema_and_journal(self):
  plan=self.plan();tok=self.fake_tok(plan);tok.eos_token_ids=[2];self.args.config_note='offline fixture'
  metadata={k:v for k,v in plan['baseline'][0]['metadata'].items() if k not in ['enable_thinking','max_tokens','temperature']}
  backend=SimpleNamespace(load_model=lambda *a,**kw:(object(),tok,metadata))
  def stream(model,tokenizer,prompt,**kw):return [SimpleNamespace(text='{"type":"object"}',token=2,from_draft=False,prompt_tokens=len(tok.encode(prompt)),generation_tokens=1,finish_reason='stop')]
  modules={'semif_phase1':SimpleNamespace(mlx_backend=backend),'mlx_lm':SimpleNamespace(stream_generate=stream),'mlx_lm.sample_utils':SimpleNamespace(make_sampler=lambda **kw:None),'transformers':SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a,**kw:tok))}
  with patch.object(e,'load_plan',return_value=plan),patch.object(e,'verify_local_sources'),patch.dict(sys.modules,modules):e.execute(self.args,self.root)
  rows=e.lines(Path(self.args.output).read_bytes());self.assertEqual(len(rows),3);self.assertTrue(all(x['status']=='invalid_output' and x['prediction']=={'type':'object'} for x in rows))
  journal=e.lines((self.root/'journal.jsonl').read_bytes());self.assertEqual(journal[-1]['status'],'completed');self.assertEqual([x['stage'] for x in journal if x['event']=='claimed'],['smoke'])
 def test_strict_parse_preserves_invalid_schema_without_repair(self):
  self.assertEqual(e.parse('{"type":"object"}',True),{'type':'object'})
  self.assertIsNone(e.parse('```json\n{}\n```',True));self.assertIsNone(e.parse('{}',False))

if __name__=='__main__':unittest.main()
