import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_public_explorer import tokens,export,surface
class PublicExportTests(unittest.TestCase):
 def test_batch_usage_is_counted_once_not_per_member_or_nested_iteration(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'batch.jsonl';p.write_text(json.dumps({'batch_size':10,'usage':{'input_tokens':2,'output_tokens':100,'cache_read_input_tokens':80,'iterations':[{'input_tokens':999,'output_tokens':999}]}})+'\n')
   t=tokens({'raw_batch_attempt_files':['batch.jsonl'],'attempt_files':['missing.jsonl']},Path(d));self.assertEqual(t['input'],2);self.assertEqual(t['output'],100);self.assertEqual(t['totalRequests'],1);self.assertEqual(t['cachedInput'],80)
 def test_missing_usage_is_not_zero_or_complete(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.jsonl';p.write_text('{}\n'+json.dumps({'usage':{'prompt_tokens':0,'completion_tokens':3}})+'\n')
   t=tokens({'attempt_files':['a.jsonl']},Path(d));self.assertEqual(t['input'],0);self.assertIsNone(t['reasoning']);self.assertFalse(t['complete']);self.assertEqual(t['reportedRequests'],1)
 def test_public_payload_has_only_allowed_top_level_fields_and_no_private_paths(self):
  x=export();self.assertEqual(x['denominator'],60);self.assertEqual(set(x),{'generatedAt','denominator','referenceNote','runs','cases','promptComparisons'})
  text=json.dumps(x);self.assertNotIn('/Users/',text);self.assertNotIn('api_key',text);self.assertNotIn('raw_response',text);self.assertNotIn('execution-journal',text)
  ids={r['id'] for r in x['runs']};self.assertEqual(len(ids),len(x['runs']))
  for r in x['runs']:
   self.assertTrue(0<=r['valid']<=60)
   for v in r['metrics'].values():self.assertTrue(0<=v<=r['valid'])
  for c in x['cases']:self.assertIn(c['configuration'],ids)
 def test_subscription_costs_are_not_invented(self):
  x=export()
  for r in x['runs']:
   if 'subscription' in r['surface']:self.assertIsNone(r['cost']['actualUsd'])
if __name__=='__main__':unittest.main()
