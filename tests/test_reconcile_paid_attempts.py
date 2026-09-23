import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import reconcile_paid_attempts as r
from development_benchmark import digest

def record(n,attempt=None,timeout=300,stamp='2026-09-23T10:00:00Z'):
 p={'model':'qwen/qwen3.6-35b-a3b','messages':[{'role':'system','content':'rubric'},{'role':'user','content':json.dumps({'feedback':f'feedback{n}'})}],'reasoning':{'enabled':False},'temperature':0,'max_tokens':4096,'response_format':{'type':'json_schema','json_schema':{'schema':{}}},'provider':{'only':['test/fp8'],'allow_fallbacks':False}}
 return {'id':f'DEV-{n:03}','attempt_id':attempt or f'A{n}','phase':'development','started_utc':stamp,'request':p,'request_sha256':digest(json.dumps(p,sort_keys=True)),'requested_model':p['model'],'provider_endpoint':{'tag':'test/fp8','provider_name':'Test','model_id':p['model'],'quantization':'fp8'},'quantization':'fp8','reasoning_effort':'off','policy_sha256':digest('rubric'),'schema_sha256':digest(json.dumps({},sort_keys=True)),'input_sha256':digest(f'feedback{n}'),'request_timeout_seconds':timeout,'status':'ok','prediction':{'sentiment':'neutral','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'no'},'returned_model':p['model'],'returned_provider':'Test','cost_unknown':False,'observed_cost_usd':'.001','reserved_cost_usd':'.02','elapsed_seconds':1,'reference_labels_read':False,'surface':'paid','runtime':'HTTP','hardware':'unknown'}
class ReconcileTests(unittest.TestCase):
 def setup_files(self,d,rows):
  root=Path(d);inp=root/'inputs.jsonl';inp.write_text(''.join(json.dumps({'id':f'DEV-{i:03}','feedback':f'feedback{i}'})+'\n' for i in range(1,61)))
  paths=[]
  for i,rr in enumerate(rows):
   p=root/f'attempt{i}.jsonl';p.write_text(''.join(json.dumps(x)+'\n' for x in rr));paths.append(p)
  return root,inp,paths
 def test_resume_latest_and_all_attempts_timing_costs(self):
  old=[record(i) for i in range(1,10)];old[-1].update(status='service_error',cost_unknown=True,observed_cost_usd=None,prediction=None)
  new=[record(i,attempt=f'B{i}',timeout=600,stamp='2026-09-23T11:00:00Z') for i in range(9,61)]
  with tempfile.TemporaryDirectory() as d:
   root,inp,paths=self.setup_files(d,[old,new]);before=[p.read_bytes() for p in paths]
   rows,audit=r.reconcile(paths,inp,root,allow_timeout_change=True)
   self.assertEqual(len(rows),60);self.assertEqual(rows[8]['attempt_id'],'B9');self.assertEqual(audit['total_attempts'],61)
   self.assertEqual(audit['costs']['known_actual_usd'],'0.060');self.assertEqual(audit['costs']['unknown_reserved_upper_bound_usd'],'0.02')
   self.assertEqual(audit['registry_fields']['attempt_files'],['attempt0.jsonl','attempt1.jsonl']);self.assertEqual(audit['total_attempt_seconds'],61)
   from build_development_report import load_timing_attempts
   self.assertEqual(len(load_timing_attempts({**audit['registry_fields'],'predictions_file':'reconciled.jsonl'},{f'DEV-{i:03}' for i in range(1,61)},root)),61)
   self.assertEqual(before,[p.read_bytes() for p in paths]);self.assertEqual(audit['timeout_values_seconds'],[300,600])
 def test_partial_explicit_and_missing_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root,inp,p=self.setup_files(d,[[record(2)]])
   with self.assertRaises(ValueError):r.reconcile(p,inp,root)
   rows,audit=r.reconcile(p,inp,root,allow_partial=True);self.assertEqual(audit['missing_ids'][0],'DEV-001');self.assertEqual(len(rows),1)
 def test_mismatch_duplicate_unknown_smoke_rejected(self):
  for mutation in ('duplicate','model','control','schema','policy','input','unknown','smoke','timeout'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    first=record(1);second=record(2)
    if mutation=='duplicate':second['attempt_id']=first['attempt_id']
    if mutation=='model':second['requested_model']='other'
    if mutation=='control':
     second['request']['reasoning']={'enabled':True};second['request_sha256']=digest(json.dumps(second['request'],sort_keys=True))
    if mutation=='schema':second['schema_sha256']='wrong'
    if mutation=='policy':second['request']['messages'][0]['content']='newrubric'
    if mutation=='input':second['request']['messages'][1]['content']=json.dumps({'feedback':'wrong','labels':{}})
    if mutation=='unknown':second['id']='DEV-061'
    if mutation=='smoke':second['phase']='smoke'
    if mutation=='timeout':second['request_timeout_seconds']=600
    root,inp,p=self.setup_files(d,[[first,second]])
    with self.assertRaises(ValueError):r.reconcile(p,inp,root,allow_partial=True)
 def test_missing_timeout_requires_explicit_source_override(self):
  with tempfile.TemporaryDirectory() as d:
   x=record(1);del x['request_timeout_seconds'];root,inp,p=self.setup_files(d,[[x]])
   with self.assertRaises(ValueError):r.reconcile(p,inp,root,allow_partial=True)
   rows,audit=r.reconcile(p,inp,root,allow_partial=True,legacy_timeouts={str(p[0].resolve()):300});self.assertEqual(audit['timeout_values_seconds'],[300]);self.assertEqual(audit['legacy_timeout_overrides'][0]['seconds'],300)
 def test_reversed_chronology_and_changed_provider_quant_rejected(self):
  for change in ['chronology','provider','quantization']:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
    first=record(1);second=record(2)
    if change=='chronology':second['started_utc']='2026-09-22T10:00:00Z'
    if change=='provider':
     second['provider_endpoint']['tag']='other/fp8';second['request']['provider']['only']=['other/fp8']
    if change=='quantization':second['quantization']='fp4';second['provider_endpoint']['quantization']='fp4'
    second['request_sha256']=digest(json.dumps(second['request'],sort_keys=True))
    root,inp,p=self.setup_files(d,[[first],[second]])
    with self.assertRaises(ValueError):r.reconcile(p,inp,root,allow_partial=True)

if __name__=='__main__':unittest.main()
