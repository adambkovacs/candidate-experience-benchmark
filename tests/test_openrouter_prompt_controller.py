"""Paid prompt conditions must preserve pinned runtime and endpoint controls."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_paid_benchmark as r
from evaluate_prompt_variants import extract_controls

class PaidRuntimeBindingTests(unittest.TestCase):
 def fixture(self):
  saved=json.loads((r.ROOT/'results/openrouter-parallel-gemma31-off-2026-09-23/smoke.jsonl').read_text().splitlines()[0]);p=saved['request'];e=saved['provider_endpoint']
  args=SimpleNamespace(model=saved['requested_model'],reasoning=saved['reasoning_effort'],max_tokens=p['max_tokens'],start=1,budget_partition_manifest='partition.json',budget_partition_id='fixed-child')
  controls={'adapter_controls':extract_controls(saved),'model':saved['requested_model'],'effort':saved['reasoning_effort'],'quantization':saved['quantization'],'runtime':saved['runtime'],'hardware':saved['hardware'],'retry_policy':saved['retry_policy'],'context_tokens':e['context_length'],'output_reserve_tokens':p['max_tokens'],'sampling':{'temperature':0},'output_method':'json_schema','parsing':'strict_json'}
  return args,controls,e,p
 def test_actual_saved_controls_and_default_payload_match(self):
  a,c,e,p=self.fixture();self.assertEqual(r.paid_adapter_controls(a,e,p),c['adapter_controls']);r.check_paid_phase_two(a,c,e)
 def test_live_endpoint_drift_fails(self):
  for key,value in [('context_length',1000),('quantization','changed')]:
   with self.subTest(key=key):
    a,c,e,p=self.fixture();e=copy.deepcopy(e);e[key]=value
    with self.assertRaisesRegex(ValueError,'controls differ'):r.check_paid_phase_two(a,c,e)
 def test_runtime_output_and_policy_drift_fail(self):
  for key in ('model','effort','runtime','hardware','sampling','output_method','parsing','retry_policy','output_reserve_tokens'):
   with self.subTest(key=key):
    a,c,e,p=self.fixture();c[key]='changed'
    with self.assertRaisesRegex(ValueError,'controls differ'):r.check_paid_phase_two(a,c,e)
 def test_no_partial_condition_or_unpartitioned_spend(self):
  for key,value in [('start',2),('budget_partition_manifest',None),('budget_partition_id',None)]:
   with self.subTest(key=key):
    a,c,e,p=self.fixture();setattr(a,key,value)
    with self.assertRaises(ValueError):r.check_paid_phase_two(a,c,e)


class PaidControllerWiringTests(unittest.TestCase):
 def setup_run(self,folder,continue_invalid=False):
  from test_openrouter_paid_benchmark import fixture
  import prompt_admission
  model,endpoint=fixture();path=Path(folder)
  a=SimpleNamespace(output=str(path/'out.jsonl'),model=model['id'],provider=endpoint['tag'],reasoning='off',max_tokens=4096,max_input_price=Decimal('.1'),max_output_price=Decimal('.7'),phase='smoke',start=1,timeout=600,env_file=None,prompt_variant='P1',parent_baseline_id='frozen-parent',prompt_execution_manifest='frozen.json',prompt_execution_manifest_sha256='hash',prompt_configuration_id='condition',prompt_schedule_journal=str(path/'schedule'),budget_partition_manifest='partition.json',budget_partition_id='child',continue_on_invalid_output=continue_invalid)
  instruction,_=r.variant_instruction(r.baseline_instruction(),'P1','frozen-parent');schema=json.loads((r.ROOT/'schemas/judgments.schema.json').read_text());rows=r.select_rows(r.read_rows(r.ROOT/'data/pilot/inputs.jsonl'),'smoke',1)
  payload=r.make_payload(a.model,endpoint,rows[0]['feedback'],instruction,schema,a.reasoning,a.max_tokens,a.max_input_price,a.max_output_price,model)
  controls={'model':a.model,'effort':a.reasoning,'quantization':endpoint.get('quantization'),'runtime':'OpenRouter HTTP v1','hardware':'Remote provider undisclosed','sampling':{'temperature':0},'output_method':'json_schema','parsing':'strict_json','retry_policy':'none; exclusive files; every attempt reserves against shared cap','context_tokens':endpoint['context_length'],'output_reserve_tokens':a.max_tokens,'adapter_controls':r.paid_adapter_controls(a,endpoint,payload)}
  guard=SimpleNamespace(controls=controls,config={'continue_on_invalid_output':continue_invalid},claimed={'attempt_id':'schedule-claim'},begin=mock.Mock(),check_request=mock.Mock(),check_response=mock.Mock(side_effect=lambda record:prompt_admission.audit_response(record,'openrouter_paid_v1',4096)),finish=mock.Mock())
  prediction={'sentiment':'neutral','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'no'}
  body={'model':a.model,'provider':endpoint['provider_name'],'usage':{'cost':.0001,'prompt_tokens':100},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(prediction)}}]}
  return a,guard,model,endpoint,body
 def run_mocked(self,a,guard,model,endpoint,bodies,folder):
  responses=[{'data':[model]},{'data':{'id':a.model,'endpoints':[endpoint]}}]+bodies
  with mock.patch('prompt_controller.prepare',return_value=guard),mock.patch.object(r,'load_key',return_value='SECRET'),mock.patch.object(r,'fetch',side_effect=responses) as fetch,mock.patch('paid_budget_partitions.open_partition',side_effect=lambda *args:r.BudgetLedger(Path(folder)/'ledger')):
   r.run(a)
  return fetch
 def test_bound_payload_checked_before_every_request_and_finished(self):
  with tempfile.TemporaryDirectory() as d:
   a,g,m,e,b=self.setup_run(d);self.run_mocked(a,g,m,e,[b]*3,d)
   self.assertEqual(g.check_request.call_count,3);self.assertEqual(g.check_response.call_count,3);g.begin.assert_called_once_with('OpenRouter HTTP v1');self.assertTrue(g.finish.call_args.args[1])
   for i,call in enumerate(g.check_request.call_args_list):
    payload,ids,controls=call.args;self.assertEqual(ids,[f'DEV-{i+1:03}']);self.assertEqual(controls,g.controls['adapter_controls']);self.assertEqual(set(json.loads(payload['messages'][1]['content'])),{'feedback'})
   raw=[json.loads(x) for x in Path(a.output).read_text().splitlines()];self.assertTrue(all(x['prompt_variant']['variant']=='P1' for x in raw));self.assertTrue(all(x['prompt_response_diagnostics']['passed'] for x in raw))
 def test_context_or_truncation_stops_even_with_invalid_continue(self):
  for case in ('length','overflow','function_call','multiple_choices'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
    a,g,m,e,b=self.setup_run(d,True)
    if case=='length':b['choices'][0]['finish_reason']='length'
    elif case=='overflow':b['usage']['prompt_tokens']=4097
    elif case=='function_call':b['choices'][0]['message']['function_call']={'name':'unexpected'}
    else:b['choices'].append(copy.deepcopy(b['choices'][0]))
    self.run_mocked(a,g,m,e,[b],d)
    row=json.loads(Path(a.output).read_text());self.assertEqual(row['status'],'prompt_admission_failure');self.assertFalse(row['prompt_response_diagnostics']['passed']);self.assertTrue(row['billing_ok']);self.assertFalse(g.finish.call_args.args[1]);self.assertEqual(g.check_request.call_count,1)
 def test_endpoint_drift_blocks_before_budget_open(self):
  with tempfile.TemporaryDirectory() as d:
   a,g,m,e,b=self.setup_run(d);e=copy.deepcopy(e);e['context_length']+=1
   with mock.patch('prompt_controller.prepare',return_value=g),mock.patch.object(r,'load_key',return_value='SECRET'),mock.patch.object(r,'fetch',side_effect=[{'data':[m]},{'data':{'id':a.model,'endpoints':[e]}}]),mock.patch('paid_budget_partitions.open_partition',side_effect=AssertionError('budget must remain unopened')):
    with self.assertRaisesRegex(ValueError,'controls differ'):r.run(a)
   g.begin.assert_not_called();g.finish.assert_not_called()
 def test_request_rejection_spends_nothing_and_stops_claim(self):
  with tempfile.TemporaryDirectory() as d:
   a,g,m,e,b=self.setup_run(d);g.check_request.side_effect=ValueError('request mismatch')
   with self.assertRaisesRegex(ValueError,'request mismatch'):self.run_mocked(a,g,m,e,[],d)
   self.assertFalse(g.finish.call_args.args[1]);events=[json.loads(x) for x in Path(d,'ledger').read_text().splitlines()];self.assertFalse(any(x['event']=='reserve' for x in events))
 def test_original_error_survives_schedule_finalization_error(self):
  with tempfile.TemporaryDirectory() as d:
   a,g,m,e,b=self.setup_run(d);g.check_request.side_effect=ValueError('original request mismatch');g.finish.side_effect=RuntimeError('journal error')
   with self.assertRaisesRegex(ValueError,'original request mismatch') as error:self.run_mocked(a,g,m,e,[],d)
   self.assertIn('Prompt schedule finalization also failed',error.exception.__notes__[0])

class PaidFrozenManifestTests(unittest.TestCase):
 def fixture(self,folder):
  import shutil
  import prompt_admission as admission
  import prompt_execution_gates as gates
  from frozen_prompt_variants import compose_instruction
  root=Path(folder)
  def write(name,value,raw=False):
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value if raw else json.dumps(value));return {'file':name,'sha256':gates.sha(p.read_bytes())}
  shutil.copytree(r.ROOT/'prompts',root/'prompts');write('docs/LABELING_GUIDE.md',(r.ROOT/'docs/LABELING_GUIDE.md').read_text(),True)
  inputs=write('data/pilot/inputs.jsonl',(r.ROOT/'data/pilot/inputs.jsonl').read_text(),True);rows=[json.loads(x) for x in gates.bound(inputs,root).decode().splitlines()]
  schema=write('schemas/judgments.schema.json',json.loads((r.ROOT/'schemas/judgments.schema.json').read_text()))
  source=r.ROOT/'results/openrouter-parallel-gemma31-off-2026-09-23/smoke.jsonl';history=write('history.jsonl',source.read_text(),True);saved=json.loads(source.read_text().splitlines()[0]);endpoint=saved['provider_endpoint'];model=saved['model_catalog_entry'];payload=saved['request']
  controller=write('scripts/openrouter_paid_benchmark.py',Path(r.__file__).read_text(),True)
  baseline=r.baseline_instruction();cid='gemma-off';parent='gemma-off-p0'
  controls={'adapter_controls':extract_controls(saved),'model':saved['requested_model'],'model_revision':None,'effort':saved['reasoning_effort'],'quantization':saved['quantization'],'runtime':saved['runtime'],'hardware':saved['hardware'],'retry_policy':saved['retry_policy'],'context_tokens':endpoint['context_length'],'output_reserve_tokens':payload['max_tokens'],'sampling':{'temperature':0},'output_method':'json_schema','parsing':'strict_json'}
  ch=gates.canonical(controls);config={'id':cid,'parent_baseline_id':parent,'role':'system','controls':controls,'controls_sha256':ch,'controller':controller,'controller_timeout_seconds':600,'continue_on_invalid_output':False,'batch_membership':[[row['id']] for row in rows],'baseline_instruction':write('baseline.txt',baseline,True),'parent_baseline':write('parent.json',{'id':parent,'context_unit':'single_record','controls_sha256':ch,'baseline_instruction_sha256':gates.sha(baseline.encode())}),'conditions':{}}
  for variant in ('P1','P2'):
   instruction=compose_instruction(baseline,variant,role='system',parent_baseline_id=parent,root=root)['instruction'];evidence={'adapter':'openrouter_paid_v1','condition':variant,'parent_baseline_id':parent,'controls_sha256':ch,'instruction_sha256':gates.sha(instruction.encode()),'inputs_sha256':inputs['sha256'],'schema_sha256':schema['sha256'],'prospective_rendered_tokens':None,'unknown_reason':'Provider tokenizer and template unavailable','advertised_context':write(variant+'context.json',{'kind':'saved_attempt_context_v1','raw_attempts':history}),'historical_usage':write(variant+'usage.json',{'kind':'saved_attempt_usage_v1','raw_attempts':history}),'requests':[]}
   for n,row in enumerate(rows[:3]+rows):
    spec=write(variant+str(n)+'request.json',admission.expected_request('openrouter_paid_v1',instruction,[row],controls));evidence['requests'].append({'record_ids':[row['id']],'client_request':spec,'request_bytes':len(gates.bound(spec,root))})
   config['conditions'][variant]={'instruction':write(variant+'.txt',instruction,True),'observational_evidence':write(variant+'evidence.json',evidence)}
  manifest={'contract':'prompt-execution-gates-v1','frozen_utc':'2026-01-01T00:00:00Z','inputs':inputs,'schema':schema,'prompt_bundle':{'file':'prompts/variants-v1/manifest.json','sha256':gates.MANIFEST_SHA256},'configurations':[config],'execution_journal':'schedule-events.jsonl','roster':write('roster.json',{'entries':[{'id':cid,'parent_baseline_id':parent,'state':'scheduled','reason':'Completed baseline'}]}),'source_inventory':write('inventory.json',{'entries':[{'id':cid,'disposition':'completed','reason':'Saved P0'}]}),'schedule':write('schedule.json',{'order':[{'id':cid,'conditions':['P1','P2']}]})}
  spec=write('manifest.json',manifest);prices=payload['provider']['max_price']
  args=SimpleNamespace(output=str(root/'smoke.jsonl'),model=saved['requested_model'],provider=endpoint['tag'],reasoning=saved['reasoning_effort'],max_tokens=payload['max_tokens'],max_input_price=Decimal(str(prices['prompt'])),max_output_price=Decimal(str(prices['completion'])),phase='smoke',start=1,timeout=600,env_file=None,prompt_variant='P1',parent_baseline_id=parent,prompt_execution_manifest=str(root/spec['file']),prompt_execution_manifest_sha256=spec['sha256'],prompt_configuration_id=cid,prompt_schedule_journal=str(root/'schedule-events.jsonl'),budget_partition_manifest='partition.json',budget_partition_id='child',continue_on_invalid_output=False)
  return root,args,model,endpoint,[json.loads(x)['raw_response'] for x in source.read_text().splitlines()]
 def test_actual_admission_and_schedule_allow_smoke_only_once(self):
  with tempfile.TemporaryDirectory() as d:
   root,args,model,endpoint,bodies=self.fixture(d)
   with mock.patch.object(r,'ROOT',root),mock.patch.object(r,'__file__',str(root/'scripts/openrouter_paid_benchmark.py')),mock.patch.object(r,'load_key',return_value='SECRET'),mock.patch.object(r,'fetch',side_effect=[{'data':[model]},{'data':{'id':args.model,'endpoints':[endpoint]}}]+bodies),mock.patch('paid_budget_partitions.open_partition',side_effect=lambda *a:r.BudgetLedger(root/'ledger')):
    r.run(args)
   events=[json.loads(x) for x in (root/'schedule-events.jsonl').read_text().splitlines()];self.assertEqual([x['event'] for x in events],['initialized','claimed','finished']);self.assertEqual(events[-1]['status'],'completed')
   result=json.loads(Path(args.output+'.prompt-admission.json').read_text());self.assertTrue(result['admitted']);self.assertFalse(result['fully_verified_controls'])
   args.output=str(root/'duplicate.jsonl')
   with mock.patch.object(r,'ROOT',root),mock.patch.object(r,'__file__',str(root/'scripts/openrouter_paid_benchmark.py')),mock.patch.object(r,'load_key',return_value='SECRET'),mock.patch.object(r,'fetch',side_effect=[{'data':[model]},{'data':{'id':args.model,'endpoints':[endpoint]}}]),mock.patch('paid_budget_partitions.open_partition',side_effect=AssertionError('no duplicate spend')):
    with self.assertRaisesRegex(ValueError,'Duplicate phase'):r.run(args)
 def test_actual_manifest_model_mismatch_rejected_before_credentials(self):
  with tempfile.TemporaryDirectory() as d:
   root,args,model,endpoint,bodies=self.fixture(d);args.model='qwen/qwen3.8-27b'
   with mock.patch.object(r,'ROOT',root),mock.patch.object(r,'__file__',str(root/'scripts/openrouter_paid_benchmark.py')),mock.patch.object(r,'load_key',side_effect=AssertionError('no credentials')):
    with self.assertRaisesRegex(ValueError,'Actual model'):r.run(args)


if __name__=='__main__':unittest.main()
