import copy,json,tempfile,unittest
import test_prompt_execution_gates as fixtures
import prompt_admission as a
import prompt_execution_gates as g

class AdmissionTests(unittest.TestCase):
 def fixture(self,d):
  helper=fixtures.GateTests();root,m=helper.fixture(d)
  m['schema']=helper.write(root,'schema.json',json.loads((fixtures.ROOT/'schemas/judgments.schema.json').read_text()))
  from evaluate_prompt_variants import extract_claude_controls
  raw=(fixtures.ROOT/'results/subscription-batch-p0-2026-09-23/sonnet5-medium-phase2-batch10-p0/smoke.jsonl.batches.jsonl').read_text()
  saved=json.loads(raw.splitlines()[0]);raw_spec=helper.write(root,'historical.jsonl',raw,True)
  for c in m['configurations']:
   c['role']='system';c['controls'].update(model=saved['requested_model'],effort=saved['effort'],runtime=saved['cli_version'],context_tokens=200000,adapter_controls=extract_claude_controls(saved));c['controls_sha256']=g.canonical(c['controls'])
   parent=g.json_bound(c['parent_baseline'],root);parent['controls_sha256']=c['controls_sha256'];c['parent_baseline']=helper.write(root,c['id']+'parent-updated.json',parent)
   for variant in ('P1','P2'):
    cond=c['conditions'][variant];token=g.json_bound(cond['token_evidence'],root)
    evidence={k:token[k] for k in ('condition','parent_baseline_id','instruction_sha256','inputs_sha256','schema_sha256')}
    evidence['schema_sha256']=m['schema']['sha256']
    evidence.update(controls_sha256=c['controls_sha256'],adapter='claude_batch_v1',prospective_rendered_tokens=None,unknown_reason='Provider scaffold and tokenizer not exposed',requests=[])
    evidence['advertised_context']=helper.write(root,c['id']+variant+'context.json',{'kind':'saved_attempt_context_v1','raw_attempts':raw_spec})
    evidence['historical_usage']=helper.write(root,c['id']+variant+'usage.json',{'kind':'saved_attempt_usage_v1','raw_attempts':raw_spec})
    instruction=g.bound(cond['instruction'],root).decode()
    for n,ids in enumerate([['DEV-001','DEV-002','DEV-003']]+c['batch_membership']):
     source=helper.write(root,c['id']+variant+str(n)+'request.json',a.expected_request('claude_batch_v1',instruction,[{'id':i,'feedback':'Synthetic text.'} for i in ids],c['controls']))
     evidence['requests'].append({'record_ids':ids,'client_request':source,'request_bytes':len(g.bound(source,root))})
    cond['observational_evidence']=helper.write(root,c['id']+variant+'observation.json',evidence)
  return helper,root,m
 def test_smoke_admitted_with_honest_unknowns(self):
  with tempfile.TemporaryDirectory() as d:
   _,root,m=self.fixture(d);result=a.admit_smoke(m,root,'config0','P1')
   self.assertTrue(result['admitted']);self.assertIsNone(result['prospective_rendered_tokens']);self.assertFalse(result['fully_verified_controls'])
 def test_mutations_fail_closed(self):
  for case in ('local','estimate','bytes','missing_feedback','executable','context','control','schedule','extra_record','metadata','payload_model','unbacked_context','unknown_reserve_on_exposed_adapter'):
   with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
    h,root,m=self.fixture(d);c=m['configurations'][0];cond=c['conditions']['P1'];e=g.json_bound(cond['observational_evidence'],root)
    if case=='local':e['adapter']='lmstudio_sdk'
    if case=='estimate':e['prospective_rendered_tokens']=400
    if case=='bytes':e['requests'][0]['request_bytes']+=1
    if case=='missing_feedback':
     source=h.write(root,'missing.txt',g.bound(cond['instruction'],root).decode(),True);e['requests'][0].update(client_request=source,request_bytes=len(g.bound(source,root)))
    if case=='executable':
     inv=g.json_bound(m['source_inventory'],root);inv['entries'][0]['disposition']='executable';m['source_inventory']=h.write(root,'bad-inventory.json',inv)
    if case=='context':e['historical_usage']=h.write(root,'bad-usage.json',{'model':'fixture','requests':[{'input_tokens':4000,'output_tokens':10}]})
    if case in ('extra_record','metadata','payload_model'):
     req=e['requests'][0];payload=g.json_bound(req['client_request'],root)
     if case=='extra_record':payload['request']['input']['records'].append({'id':'DEV-004','feedback':'extra'})
     if case=='metadata':payload['request']['input']['records'][0]['reference_labels']={}
     if case=='payload_model':payload['adapter_controls']['requested_model']='other'
     req['client_request']=h.write(root,'mutated-request.json',payload);req['request_bytes']=len(g.bound(req['client_request'],root))
    if case=='unbacked_context':e['advertised_context']=h.write(root,'invented-context.json',{'model':'fixture','context_tokens':200000,'source':'I claim a source'})
    if case=='unknown_reserve_on_exposed_adapter':
     c['controls']['output_reserve_tokens']=None;c['controls']['output_reserve_source']='unexposed_cli_default_unchanged';c['controls_sha256']=g.canonical(c['controls'])
     parent=g.json_bound(c['parent_baseline'],root);parent['controls_sha256']=c['controls_sha256'];c['parent_baseline']=h.write(root,'updated-parent.json',parent);e['controls_sha256']=c['controls_sha256']
    if case=='control':c['controls']['effort']='high'
    if case=='schedule':m['schedule']=h.write(root,'bad-schedule.json',{'order':[]})
    cond['observational_evidence']=h.write(root,'changed-evidence.json',e)
    with self.assertRaises(ValueError):a.admit_smoke(m,root,'config0','P1')
 def test_manifest_or_custom_verifier_cannot_claim_development(self):
  with tempfile.TemporaryDirectory() as d:
   h,root,m=self.fixture(d);cond=m['configurations'][0]['conditions']['P1'];s=g.json_bound(cond['smoke_evidence'],root)
   s.update(controls_sha256=m['configurations'][0]['controls_sha256'],extractor='claude_batch_v1')
   cond['smoke_evidence']=h.write(root,'smoke-forged.json',s)
   with self.assertRaises(ValueError):a.admit_development(m,root,'config0','P1',lambda *args:{'verified':True})
   with self.assertRaises((ValueError,KeyError)):a.admit_development(m,root,'config0','P1')
 def test_diagnostics_are_not_model_prose(self):
  r=a.audit_response({'choices':[{'finish_reason':'stop','message':{'content':'context_length_exceeded'}}]},'openrouter_paid_v1',100)
  self.assertTrue(r['passed'])
  for raw in ({'choices':[{'finish_reason':'length'}]},{'usage':{'prompt_tokens':101}},{'events':[{'type':'context_compacted'}]},{'raw_events':[{'type':'system','subtype':'compact_boundary'}]},{'raw_events':[{'type':'item.completed','item':{'type':'context_compaction'}}]},{'control_violation':True},{'usage':{'input_tokens':50,'cache_read_input_tokens':60,'cache_creation_input_tokens':0}}):
   self.assertFalse(a.audit_response(raw,'codex_batch_v1',100)['passed'])
 def test_explicit_shard_keeps_global_roster_and_schedule(self):
  with tempfile.TemporaryDirectory() as d:
   _,root,m=self.fixture(d);m['manifest_scope']=['config1'];m['configurations']=m['configurations'][1:]
   self.assertTrue(a.admit_smoke(m,root,'config1','P2')['admitted'])
   for scope in ([],['config0'],['config1','config1'],['invented']):
    broken=copy.deepcopy(m);broken['manifest_scope']=scope
    with self.assertRaises(ValueError):a.admit_smoke(broken,root,'config1','P2')
   del m['manifest_scope']
   with self.assertRaises(ValueError):a.admit_smoke(m,root,'config1','P2')

if __name__=='__main__':unittest.main()
