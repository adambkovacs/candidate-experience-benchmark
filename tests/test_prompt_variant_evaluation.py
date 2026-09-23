import copy,hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_prompt_variants as e
from frozen_prompt_variants import compose_instruction
REPO=Path(__file__).resolve().parents[1]
def write(root,name,value,jsonl=False):
 p=root/name;p.write_text(''.join(json.dumps(x)+'\n' for x in value) if jsonl else json.dumps(value));return {'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
class PairedTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d);(root/'prompts').mkdir();shutil.copytree(REPO/'prompts/variants-v1',root/'prompts/variants-v1');(root/'docs').mkdir();shutil.copyfile(REPO/'docs/LABELING_GUIDE.md',root/'docs/LABELING_GUIDE.md')
  inp=[{'id':f'DEV-{i:03}','feedback':f'feedback{i}'} for i in range(1,61)]
  labels={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
  refs=[{'id':x['id'],'split':'development','proposed_labels':labels} for x in inp]
  m={'contract':'prompt-pairs-v1','parent_baseline_id':'baseline','role':'system','inputs':write(root,'inputs.jsonl',inp,True),'references':write(root,'refs.jsonl',refs,True),'pairs':write(root,'pairs.json',[]),'conditions':{},'allow_missing_outputs':False,'attempt_selection':'latest_chronological','retry_authorizations':{}}
  (root/'base.txt').write_text('rubric');m['baseline_instruction']={'file':'base.txt','sha256':hashlib.sha256(b'rubric').hexdigest()}
  for variant in ['P0','P1','P2']:
   text=compose_instruction('rubric',variant,role='system',parent_baseline_id='baseline',root=root)['instruction'];rows=[]
   for x in inp:
    p={'model':'qwen/test','provider':{'only':['provider/fp8'],'allow_fallbacks':False},'reasoning':{'enabled':False},'temperature':0,'max_tokens':4096,'messages':[{'role':'system','content':text},{'role':'user','content':json.dumps({'feedback':x['feedback']})}],'response_format':{'type':'json_schema','json_schema':{'schema':{}}}}
    rows.append({'id':x['id'],'phase':'development','started_utc':'2026-09-23T10:00:00Z','attempt_id':variant+x['id'],'status':'ok','prediction':dict(labels),'request':p,'input_sha256':hashlib.sha256(x['feedback'].encode()).hexdigest(),'requested_model':'qwen/test','provider_endpoint':{'tag':'provider/fp8','provider_name':'Provider','model_id':'qwen/test','quantization':'fp8'},'quantization':'fp8','runtime':'HTTP','hardware':'unknown','surface':'OpenRouter paid','retry_policy':'none','reasoning_effort':'off'})
   for row in rows:
    row['request_sha256']=e.canonical_hash(row['request']);row['raw_response']={'model':'qwen/test','provider':'Provider','choices':[{'finish_reason':'stop','message':{'content':json.dumps(row['prediction'])}}]}
   m['conditions'][variant]={'predictions':write(root,variant+'.jsonl',rows,True),'request_evidence':write(root,variant+'-raw.jsonl',rows,True),'extractor':'openrouter_paid_v1'}
  m['controls']=e.extract_controls(rows[0]);m['controls_sha256']=e.canonical_hash(m['controls']);return root,m
 def mutate(self,root,m,variant,func,both=True):
  names=['predictions','request_evidence'] if both else ['predictions']
  for key in names:
   name=m['conditions'][variant][key]['file'];rows=[json.loads(x) for x in (root/name).read_text().splitlines()];func(rows)
   if both:
    for row in rows:
     row['request_sha256']=e.canonical_hash(row['request'])
     if row['status']=='ok':row['raw_response']['choices'][0]['message']['content']=json.dumps(row['prediction'])
   m['conditions'][variant][key]=write(root,name,rows,True)
 def test_valid_transitions_failures_and_denominator(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d)
   self.mutate(root,m,'P0',lambda rr:rr[0]['prediction'].update(sentiment='negative'))
   self.mutate(root,m,'P1',lambda rr:rr[1].update(status='service_error',prediction=None))
   result=e.evaluate(m,root);p=result['comparisons']['P0_to_P1']
   self.assertTrue(result['controls_verified']);self.assertFalse(result['eligible_paired_comparison']);self.assertEqual(p['fields']['sentiment']['wrong_to_correct'],['DEV-001']);self.assertEqual(p['fields']['sentiment']['correct_to_wrong'],[]);self.assertEqual(p['valid_to_failed'],['DEV-002']);self.assertEqual(result['conditions']['P1']['evaluation']['metrics']['sentiment']['denominator'],60);self.assertIsNone(result['conditions']['P1']['telemetry']['input_tokens'])
 def test_missing_output_requires_flag_and_stays_denominator(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);self.mutate(root,m,'P2',lambda rr:rr.pop(),both=False)
   with self.assertRaises(ValueError):e.evaluate(m,root)
   m['allow_missing_outputs']=True;r=e.evaluate(m,root);self.assertEqual(r['conditions']['P2']['evaluation']['valid_outputs'],59);self.assertEqual(r['comparisons']['P0_to_P2']['valid_to_failed'],['DEV-060']);self.assertEqual(r['conditions']['P2']['omitted_predictions'][0]['selected_audited_status'],'ok');self.assertFalse(r['eligible_paired_comparison'])
 def test_tampering_and_crosscontrols_rejected(self):
  for change in ['control','input','prompt','prediction','duplicate']:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d)
    if change=='control':self.mutate(root,m,'P1',lambda rr:rr[0]['request'].update(temperature=.6))
    if change=='input':self.mutate(root,m,'P1',lambda rr:rr[0].update(input_sha256='wrong'))
    if change=='prompt':self.mutate(root,m,'P1',lambda rr:rr[0]['request']['messages'][0].update(content='wrong'))
    if change=='prediction':self.mutate(root,m,'P1',lambda rr:rr[0]['prediction'].update(sentiment='negative'),both=False)
    if change=='duplicate':self.mutate(root,m,'P1',lambda rr:rr.append(rr[0]))
    with self.assertRaises(ValueError):e.evaluate(m,root)
 def test_declarations_alone_cannot_establish_pair(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);m['conditions']['P1']['extractor']='declared_only';del m['conditions']['P1']['request_evidence']
   r=e.evaluate(m,root);self.assertFalse(r['eligible_paired_comparison']);self.assertEqual(r['conditions']['P1']['actual_controls_verification'],'unavailable')
 def test_hash_mismatch_unknown_id_and_max_exclusion(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);(root/'P1.jsonl').write_text('changed')
   with self.assertRaises(ValueError):e.evaluate(m,root)
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);self.mutate(root,m,'P1',lambda rr:rr[0].update(id='UNKNOWN'))
   with self.assertRaises(ValueError):e.evaluate(m,root)
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);m['controls']['reasoning_effort']='max';m['controls_sha256']=e.canonical_hash(m['controls'])
   with self.assertRaises(ValueError):e.evaluate(m,root)
 def test_correct_to_wrong_concerns_and_failure_recovery(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d)
   refs=[json.loads(x) for x in (root/'refs.jsonl').read_text().splitlines()];refs[0]['proposed_labels']['serious_concern_reported']='yes';m['references']=write(root,'refs.jsonl',refs,True)
   self.mutate(root,m,'P0',lambda rr:rr[0]['prediction'].update(serious_concern_reported='yes'))
   self.mutate(root,m,'P1',lambda rr:rr[1]['prediction'].update(serious_concern_reported='yes'))
   self.mutate(root,m,'P0',lambda rr:rr[2].update(status='service_error',prediction=None))
   result=e.evaluate(m,root);change=result['comparisons']['P0_to_P1'];self.assertEqual(change['fields']['serious_concern_reported']['correct_to_wrong'],['DEV-001','DEV-002']);self.assertEqual(change['failed_to_valid'],['DEV-003']);self.assertIn('DEV-001',result['conditions']['P1']['evaluation']['serious_concerns']['predicted_no']);self.assertIn('DEV-002',result['conditions']['P1']['evaluation']['serious_concerns']['false_escalations']);self.assertEqual(change['cases'][0]['feedback'],'feedback1')
 def test_empty_audit_and_wrong_raw_provider_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);m['conditions']['P1']['request_evidence']=write(root,'empty.jsonl',[],True)
   with self.assertRaises(ValueError):e.evaluate(m,root)
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);self.mutate(root,m,'P1',lambda rr:rr[0]['raw_response'].update(provider='Other'))
   with self.assertRaises(ValueError):e.evaluate(m,root)

 def test_later_retry_cannot_be_ignored_and_needs_authorization(self):
  with tempfile.TemporaryDirectory() as d:
   root,m=self.fixture(d);spec=m['conditions']['P1']['request_evidence'];rows=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()];retry=copy.deepcopy(rows[0]);retry.update(attempt_id='retry1',started_utc='2026-09-23T11:00:00Z');retry['prediction']['sentiment']='negative';retry['raw_response']['choices'][0]['message']['content']=json.dumps(retry['prediction']);rows.append(retry);m['conditions']['P1']['request_evidence']=write(root,spec['file'],rows,True)
   with self.assertRaises(ValueError):e.evaluate(m,root)
   m['retry_authorizations']={'P1':['retry1']}
   with self.assertRaises(ValueError):e.evaluate(m,root)
   m['attempt_selection']='first_chronological';result=e.evaluate(m,root);self.assertTrue(result['controls_verified']);self.assertFalse(result['eligible_paired_comparison'])
   m['attempt_selection']='latest_chronological';predspec=m['conditions']['P1']['predictions'];predrows=[json.loads(x) for x in (root/predspec['file']).read_text().splitlines()];predrows[0]=retry;m['conditions']['P1']['predictions']=write(root,predspec['file'],predrows,True);self.assertTrue(e.evaluate(m,root)['controls_verified'])
 def test_order_and_chronology_rejected(self):
  for mutation in ['reverse','timestamp']:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d);spec=m['conditions']['P1']['request_evidence'];rows=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()]
    if mutation=='reverse':rows.reverse()
    else:rows[-1]['started_utc']='2026-09-22T10:00:00Z'
    m['conditions']['P1']['request_evidence']=write(root,spec['file'],rows,True)
    with self.assertRaises(ValueError):e.evaluate(m,root)
 def test_raw_usage_and_cost_mirrors_bound(self):
  for mutation in ['usage','cost']:
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    root,m=self.fixture(d);spec=m['conditions']['P1']['request_evidence'];rows=[json.loads(x) for x in (root/spec['file']).read_text().splitlines()];row=rows[0];row['raw_response']['usage']={'prompt_tokens':100,'completion_tokens':50,'cost':.01};row['usage']=copy.deepcopy(row['raw_response']['usage']);row.update(cost_unknown=False,observed_cost_usd='.01')
    if mutation=='usage':row['usage']['prompt_tokens']=0
    else:row['observed_cost_usd']='0'
    m['conditions']['P1']['request_evidence']=write(root,spec['file'],rows,True)
    with self.assertRaises(ValueError):e.evaluate(m,root)

if __name__=='__main__':unittest.main()
