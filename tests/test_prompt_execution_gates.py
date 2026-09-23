import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prompt_execution_gates as g
from frozen_prompt_variants import compose_instruction
ROOT=Path(__file__).resolve().parents[1]
class GateTests(unittest.TestCase):
 def write(self,root,name,value,raw=False):
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value if raw else json.dumps(value));return {'file':name,'sha256':g.sha(p.read_bytes())}
 def fixture(self,d):
  root=Path(d);shutil.copytree(ROOT/'prompts',root/'prompts');(root/'docs').mkdir();shutil.copy(ROOT/'docs/LABELING_GUIDE.md',root/'docs/LABELING_GUIDE.md')
  inp=self.write(root,'inputs.jsonl','\n'.join(json.dumps({'id':f'DEV-{i:03}','feedback':'Synthetic text.'}) for i in range(1,61)),True);schema=self.write(root,'schema.json',{'type':'object'});opaque=self.write(root,'opaque.json',{})
  m={'contract':'prompt-execution-gates-v1','frozen_utc':'2026-01-01T00:00:00Z','inputs':inp,'schema':schema,'prompt_bundle':{'file':'prompts/variants-v1/manifest.json','sha256':g.MANIFEST_SHA256},'configurations':[]}
  roster=[];inventory=[];schedule=[]
  for n in range(2):
   cid='config'+str(n);parent='parent'+str(n);roster.append({'id':cid,'parent_baseline_id':parent,'state':'scheduled','reason':'Complete baseline'});inventory.append({'id':cid,'disposition':'completed','reason':'Saved P0'});order=['P1','P2'] if n==0 else ['P2','P1'];schedule.append({'id':cid,'conditions':order})
   controls={**{k:'fixture' for k in ('model','model_revision','quantization','runtime','hardware','effort','sampling','output_method','parsing','retry_policy')},'context_tokens':4096,'output_reserve_tokens':1024};ch=g.canonical(controls);base='Complete baseline instruction';groups=[[f'DEV-{i:03}' for i in range(start,start+10)] for start in range(1,61,10)]
   c={'id':cid,'parent_baseline_id':parent,'role':'system','baseline_instruction':self.write(root,cid+'-base.txt',base,True),'parent_baseline':self.write(root,cid+'-parent.json',{'id':parent,'context_unit':'batch10','controls_sha256':ch,'baseline_instruction_sha256':g.sha(base.encode())}),'controls':controls,'controls_sha256':ch,'batch_membership':groups,'conditions':{}}
   for v in ('P0','P1','P2'):
    text=compose_instruction(base,v,role='system',parent_baseline_id=parent,root=root)['instruction'];bindings={'condition':v,'parent_baseline_id':parent,'controls_sha256':ch,'instruction_sha256':g.sha(text.encode()),'inputs_sha256':inp['sha256'],'schema_sha256':schema['sha256']}
    token={**bindings,'method':'exact_rendered','wrapper_coverage':'complete','measured_utc':'2026-01-01T00:01:00Z','tokenizer':opaque,'raw_measurements':opaque,'requests':[{'record_ids':ids,'input_tokens':1000,'output_reserve_tokens':1024,'context_tokens':4096} for ids in groups]}
    smoke={**bindings,'started_utc':'2026-01-01T00:02:00Z','finished_utc':'2026-01-01T00:03:00Z','inspected_utc':'2026-01-01T00:04:00Z','inspection':'passed','inspector':'fixture','raw_attempts':opaque,'records':[{'id':f'DEV-{i:03}','status':'ok','prediction':{'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}} for i in range(1,4)]}
    c['conditions'][v]={'instruction':self.write(root,cid+v+'.txt',text,True),'token_evidence':self.write(root,cid+v+'token.json',token),'smoke_evidence':self.write(root,cid+v+'smoke.json',smoke),'development_not_before':'2026-01-01T00:'+('05' if v=='P0' else '06' if v==order[0] else '07')+':00Z'}
   m['configurations'].append(c)
  for name,value in [('roster',{'entries':roster}),('source_inventory',{'entries':inventory}),('schedule',{'order':schedule})]:m[name]=self.write(root,name+'.json',value)
  return root,m
 def test_valid_structure_never_authorizes_runtime(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);r=g.validate(m,root);self.assertTrue(r['structural_checks_passed']);self.assertFalse(r['execution_allowed']);self.assertEqual(len(r['blockers']),3)
 def test_bound_source_tampering(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);(root/'inputs.jsonl').write_text('{}')
   with self.assertRaises(ValueError):g.validate(m,root)
 def test_condition_guards(self):
  for case in ('overflow','opaque','time','failed','identity','budgets','order','instruction'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d);c=m['configurations'][0];cond=c['conditions']['P1']
    if case=='order':cond['development_not_before']='2026-01-01T00:08:00Z'
    elif case=='instruction':cond['instruction']=self.write(root,'wrong.txt','changed',True)
    else:
     key='token_evidence' if case in ('overflow','opaque','budgets') else 'smoke_evidence';x=g.json_bound(cond[key],root)
     if case=='overflow':x['requests'][0]['input_tokens']=4000
     if case=='opaque':x['wrapper_coverage']='unknown'
     if case=='budgets':x['requests'][0]['output_reserve_tokens']=1
     if case=='time':x['inspected_utc']='2026-01-01T00:09:00Z'
     if case=='failed':x['records'][0]['status']='service_error'
     if case=='identity':x['parent_baseline_id']='other'
     cond[key]=self.write(root,'changed.json',x)
    with self.assertRaises(ValueError):g.validate(m,root)
 def test_roster_and_baseline_gates(self):
  for case in ('executable','missing','counterbalance'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d);key='schedule' if case=='counterbalance' else 'source_inventory';x=g.json_bound(m[key],root)
    if case=='executable':x['entries'][0]['disposition']='executable'
    elif case=='missing':x['entries'].pop()
    else:x['order'][1]['conditions']=['P1','P2']
    m[key]=self.write(root,'changed.json',x)
    with self.assertRaises(ValueError):g.validate(m,root)
 def test_historical_p0_reuse(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);c=m['configurations'][0]['conditions']['P0']
   for key in ('token_evidence','smoke_evidence'):
    value=g.json_bound(c[key],root)
    for field in ('measured_utc','started_utc','finished_utc','inspected_utc'):
     if field in value:value[field]=value[field].replace('2026-01-01','2025-12-01')
    c[key]=self.write(root,'historical-'+key+'.json',value)
   c['development_not_before']='2025-12-01T00:05:00Z'
   self.assertTrue(g.validate(m,root)['structural_checks_passed'])
 def test_inspected_intrinsic_failure_retained_but_service_blocks(self):
  for failure,accepted in [('intrinsic_schema',True),('transport',False),('identity',False),('truncation',False)]:
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d);c=m['configurations'][0]['conditions']['P1'];smoke=g.json_bound(c['smoke_evidence'],root)
    smoke['inspection']='accepted_unchanged';smoke['records'][0].update(status='invalid_output' if accepted else 'service_error',prediction=None,failure_class=failure,accepted_unchanged=True,inspection_reason='Inspected raw response; preserve this unchanged observation.')
    c['smoke_evidence']=self.write(root,'accepted-smoke.json',smoke)
    if accepted:self.assertTrue(g.validate(m,root)['structural_checks_passed'])
    else:
     with self.assertRaises(ValueError):g.validate(m,root)
if __name__=='__main__':unittest.main()
