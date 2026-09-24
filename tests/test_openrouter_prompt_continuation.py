import copy,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_prompt_continuation as c

def record(finish='length',status='invalid_output'):
 return {'id':'DEV-001','status':status,'cost_unknown':False,'billing_ok':True,'raw_response':{'choices':[{'finish_reason':finish,'message':{'content':'{}'}}],'usage':{'prompt_tokens':10,'completion_tokens':4096}}}
class ContinuationTests(unittest.TestCase):
 def test_remaining_skips_failed_record_once(self):
  req=[{'record_ids':['DEV-'+str(i).zfill(3)]} for i in range(1,61)]
  self.assertEqual(c.remaining([record()],req),req[1:])
 def test_nonprefix_or_duplicates_rejected(self):
  req=[{'record_ids':['DEV-'+str(i).zfill(3)]} for i in range(1,61)]
  r=record();r['id']='DEV-002'
  with self.assertRaises(ValueError):c.remaining([r],req)
  with self.assertRaises(ValueError):c.remaining([record(),record()],req)
 def test_original_other_stop_or_unknown_rejected(self):
  req=[{'record_ids':['DEV-'+str(i).zfill(3)]} for i in range(1,61)]
  for key,value in [('status','ok'),('cost_unknown',True),('billing_ok',False)]:
   r=record();r[key]=value
   with self.assertRaises(ValueError):c.remaining([r],req)
  with self.assertRaises(ValueError):c.remaining([record('error')],req)
 def test_output_length_may_continue(self):
  d=c.response_diagnostics(record(),100);self.assertTrue(d['passed']);self.assertTrue(d['output_budget_exhausted'])
 def test_input_overflow_stops_even_with_output_length(self):
  r=record();r['raw_response']['usage']['prompt_tokens']=101
  self.assertFalse(c.response_diagnostics(r,100)['passed'])
 def test_provider_tool_identity_unknown_and_refusal_stop(self):
  variants=[]
  for key,val in [('cost_unknown',True),('billing_ok',False),('identity_violation',True)]:
   r=record();r[key]=val;variants.append(r)
  for key in ['tool_calls','function_call','refusal']:
   r=record();r['raw_response']['choices'][0]['message'][key]='present';variants.append(r)
  r=record();r['raw_response']['choices'][0]['error']={'code':504};variants.append(r)
  r=record();r['raw_response']['error']={'code':504};variants.append(r)
  for r in variants:self.assertFalse(c.response_diagnostics(r,100)['passed'])
 def test_other_invalid_output_stops(self):
  self.assertFalse(c.response_diagnostics(record('stop'),100)['passed'])
  self.assertTrue(c.response_diagnostics(record('stop','ok'),100)['passed'])
 def test_no_implicit_draft_execution(self):
  with self.assertRaisesRegex(ValueError,'Draft cannot infer'):c.validate({'contract':c.CONTRACT,'policy':c.POLICY,'status':'DRAFT'})
class SavedManifestTests(unittest.TestCase):
 def setUp(self):
  import json
  self.manifest=json.loads((c.ROOT/'results/prompt-comparison-v1-2026-09-24/hosted-continuations-v1/low-P2/draft-manifest.json').read_text())
 def test_actual_frozen_inputs_and_terminal_sources_reproduce(self):
  guard,original,requests=c.validate(self.manifest,require_frozen=False)
  self.assertEqual(len(original),13)
  self.assertEqual([r['record_ids'][0] for r in requests],[f'DEV-{i:03d}' for i in range(14,61)])
 def test_retry_of_failed_record_rejected(self):
  self.manifest['remaining_requests'][0]['record_ids']=['DEV-013']
  with self.assertRaisesRegex(ValueError,'request subset'):c.validate(self.manifest,require_frozen=False)
 def test_changed_output_budget_rejected(self):
  self.manifest['policy']['output_tokens']=8192
  with self.assertRaisesRegex(ValueError,'Unsupported amendment'):c.validate(self.manifest,require_frozen=False)
 def test_missing_original_condition_rejected(self):
  del self.manifest['terminal_original_conditions']['P1']
  with self.assertRaisesRegex(ValueError,'Both original conditions'):c.validate(self.manifest,require_frozen=False)

if __name__=='__main__':unittest.main()
