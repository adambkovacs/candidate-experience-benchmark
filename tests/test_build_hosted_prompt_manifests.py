import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_hosted_prompt_manifests as b
from evaluate_prompt_variants import extract_controls

class HostedPreparationTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d);registry=json.loads((b.ROOT/'results/openrouter-paid-run-registry.json').read_text());entry=next(r for r in registry if r['id']=='openrouter-paid-gemma4-31b-off')
  shutil.copytree(b.ROOT/'prompts',root/'prompts')
  paths=['data/pilot/inputs.jsonl','schemas/judgments.schema.json','docs/LABELING_GUIDE.md','scripts/openrouter_paid_benchmark.py']+entry['attempt_files']+[entry['predictions_file']]
  for name in set(paths):
   dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(b.ROOT/name,dest)
  blocked={'id':'blocked-mistral','model':'mistralai/mistral-small-2603','status':'smoke_upstream_rate_limit','notes':'Shared upstream pool429; wait for provider recovery'}
  other={'id':'other-adapter','model':'other-model','status':'complete'};entries=[other,entry,blocked]
  (root/'snapshot.json').write_text(json.dumps(entries));roster=[];inventory=[]
  for e in entries:
   blocked=e['id']=='blocked-mistral';roster.append({'id':e['id'],'parent_baseline_id':e['id'],'state':'blocked' if blocked else 'scheduled','reason':'Explicit root disposition'});inventory.append({'id':e['id'],'disposition':'blocked' if blocked else 'completed','reason':'Saved evidence'})
  (root/'roster.json').write_text(json.dumps({'entries':roster}));(root/'inventory.json').write_text(json.dumps({'entries':inventory}));return root,entry
 def test_full_roster_global_order_exact_requests_and_no_inference(self):
  with tempfile.TemporaryDirectory() as d:
   root,entry=self.fixture(d)
   with mock.patch('openrouter_paid_benchmark.fetch',side_effect=AssertionError('No network')),mock.patch('openrouter_paid_benchmark.load_key',side_effect=AssertionError('No credentials')),mock.patch('openrouter_paid_benchmark.BudgetLedger',side_effect=AssertionError('No budget')):
    result=b.build(root,'snapshot.json','prepared','roster.json','inventory.json')
   self.assertEqual(result['status'],'DRAFT_NOT_FROZEN');self.assertIsNone(result['frozen_utc']);self.assertEqual(result['full_source_count'],3);self.assertEqual(len(result['configurations']),1);self.assertEqual(result['other_adapter_ids'],['other-adapter']);self.assertIn('pool429',result['blocked_hosted_candidates'][0]['reason'])
   schedule=json.loads((root/result['global_schedule']['file']).read_text())['order'];self.assertEqual(schedule[1]['conditions'],['P2','P1'])
   c=json.loads((root/result['configurations'][0]['configuration']['file']).read_text());self.assertEqual(c['parent_baseline_id'],entry['id'])
   source=json.loads((root/entry['attempt_files'][0]).read_text().splitlines()[0]);self.assertEqual(c['controls']['adapter_controls'],extract_controls(source))
   for variant in ('P1','P2'):
    ev=json.loads((root/c['conditions'][variant]['observational_evidence']['file']).read_text());self.assertIsNone(ev['prospective_rendered_tokens']);self.assertEqual(len(ev['requests']),63)
    self.assertEqual(ev['requests'][3]['record_ids'],['DEV-001']);self.assertEqual(ev['requests'][-1]['record_ids'],['DEV-060'])
    envelope=json.loads((root/ev['requests'][0]['client_request']['file']).read_text());self.assertEqual(set(json.loads(envelope['request']['messages'][1]['content'])),{'feedback'});self.assertEqual(envelope['request']['provider'],source['request']['provider']);self.assertEqual(envelope['request']['max_tokens'],source['request']['max_tokens'])
   with self.assertRaises(FileExistsError):b.build(root,'snapshot.json','prepared','roster.json','inventory.json')
 def test_no_independent_schedule_without_root_roster(self):
  with tempfile.TemporaryDirectory() as d:
   root,_=self.fixture(d);r=b.build(root,'snapshot.json','prepared');self.assertIsNone(r['global_schedule']);self.assertIsNone(r['full_roster'])
 def test_incomplete_full_roster_rejected_and_references_forbidden(self):
  with tempfile.TemporaryDirectory() as d:
   root,_=self.fixture(d);(root/'bad-roster.json').write_text('{"entries":[]}')
   with self.assertRaisesRegex(ValueError,'full source'):b.build(root,'snapshot.json','prepared','bad-roster.json','inventory.json')
   with self.assertRaisesRegex(ValueError,'Reference'):b.build(root,'proposed_labels.jsonl','prepared')
 def test_substantive_control_tampering_not_normalized(self):
  with tempfile.TemporaryDirectory() as d:
   root,e=self.fixture(d);p=root/e['attempt_files'][0];rows=[json.loads(x) for x in p.read_text().splitlines()];rows[1]['request']['max_tokens']+=1;p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
   result=b.build(root,'snapshot.json','prepared');self.assertEqual(result['configurations'],[]);self.assertTrue(any('hash' in r['reason'] for r in result['blocked_hosted_candidates']))
 def test_only_exact_legacy_surface_label_is_normalized(self):
  source=json.loads((b.ROOT/'results/openrouter-qwen35-on-2026-09-23/smoke.jsonl').read_text().splitlines()[0]);original=copy.deepcopy(source);actual=extract_controls(source);self.assertEqual(actual['surface'],'OpenRouter paid HTTP');self.assertEqual(source,original)
  altered=copy.deepcopy(source);altered['surface']='OpenRouter paid HTTP, aggregate cap $2';self.assertEqual(extract_controls(altered)['surface'],altered['surface'])
  for key in ('max_tokens','temperature'):
   altered=copy.deepcopy(source);altered['request'][key]+=1;self.assertNotEqual(extract_controls(altered)['request_controls'],actual['request_controls'])

if __name__=='__main__':unittest.main()
