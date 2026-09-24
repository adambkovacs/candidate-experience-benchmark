import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_subscription_prompt_manifests as b
import prompt_admission as admission
ROOT=Path(__file__).resolve().parents[1]

class BuilderTests(unittest.TestCase):
 def fixture(self,d,selected_ids=None):
  root=Path(d);source=json.loads((ROOT/'results/prompt-pairing-reconciled-baselines-2026-09-24.json').read_text())
  selected=[x for x in source['configurations'] if x['id'] in (selected_ids or ('codex-gpt-5.6-luna-medium','opus55-low-batch10'))]
  for directory in ('prompts','schemas'):
   shutil.copytree(ROOT/directory,root/directory)
  names=['docs/LABELING_GUIDE.md','data/pilot/inputs.jsonl','scripts/codex_batch_benchmark.py','scripts/claude_batch_benchmark.py']
  for entry in selected:names.extend(x['file'] for x in entry['evidence'] if x.get('available'))
  for name in set(names):
   target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(ROOT/name,target)
  source_spec=b.write(root/'source.json',{'configurations':selected},root)
  roster=b.write(root/'roster.json',{'entries':[{'id':e['id'],'parent_baseline_id':e['id'],'state':'scheduled','reason':'Complete fixture P0'} for e in selected]},root)
  inventory=b.write(root/'inventory.json',{'entries':[{'id':e['id'],'disposition':'completed','reason':'Complete fixture P0'} for e in selected]},root)
  schedule=b.write(root/'schedule.json',{'order':[{'id':e['id'],'conditions':['P1','P2'] if n%2==0 else ['P2','P1']} for n,e in enumerate(selected)]},root)
  freeze=root/'freeze.json';b.write(freeze,{'contract':'prompt-global-roster-v1','frozen_utc':'2026-01-01T00:00:00Z','source_snapshot':source_spec,'roster':roster,'source_inventory':inventory,'schedule':schedule,'execution_journal':'execution.jsonl'},root)
  cache=root/'cache.json';cache.write_text(json.dumps({'identity':'DO_NOT_COPY_PRIVATE_ID','fetched_at':'fixture','models':[{'slug':name,'context_window':272000,'effective_context_window_percent':95,'max_context_window':872000,'hidden_instructions':'DO_NOT_COPY_PROMPT'} for name in ('gpt-6-astra','gpt-6-sol','gpt-6-luna','gpt-5.6-luna','gpt-5.6-sol','gpt-5.6-terra')]}))
  return root,freeze,cache,selected
 def test_real_saved_parents_prepare_two_exact_admitted_shards(self):
  with tempfile.TemporaryDirectory() as d:
   root,freeze,cache,_=self.fixture(d);result=b.build(root,freeze,cache,root/'prepared')
   self.assertEqual(len(result['prepared']),2);self.assertEqual(result['blocked'],[])
   projection=(root/'prepared/codex-context-source-projection.json').read_text()
   self.assertNotIn('DO_NOT_COPY',projection);self.assertIn('context-field', (root/'prepared/codex-context-catalogue.json').read_text())
   for row in result['prepared']:
    manifest=json.loads((root/row['manifest']['file']).read_text())
    self.assertEqual(manifest['manifest_scope'],[row['id']])
    for condition in ('P1','P2'):
     audit=admission.admit_smoke(manifest,root,row['id'],condition)
     self.assertTrue(audit['admitted']);self.assertFalse(audit['fully_verified_controls'])
   with self.assertRaises(FileExistsError):b.build(root,freeze,cache,root/'prepared')
 def test_changed_parent_source_is_named_blocker_not_silent_omission(self):
  with tempfile.TemporaryDirectory() as d:
   root,freeze,cache,selected=self.fixture(d);name=selected[0]['configuration']['raw_batch_attempt_files'][0]
   (root/name).write_text('{}\n')
   result=b.build(root,freeze,cache,root/'prepared')
   self.assertEqual(len(result['prepared']),1);self.assertEqual(result['blocked'][0]['id'],selected[0]['id']);self.assertIn('Source snapshot mismatch',result['blocked'][0]['reason'])
 def test_known_partial_parents_keep_unknowns_and_audit_available_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   selected=['codex-gpt-6-sol-low-batch10','codex-gpt-6-luna-low-batch10']
   root,freeze,cache,_=self.fixture(d,selected);result=b.build(root,freeze,cache,root/'prepared',selected)
   self.assertEqual(len(result['prepared']),2);self.assertEqual(result['blocked'],[])
   for row in result['prepared']:
    self.assertFalse(row['baseline_evidence_complete'])
    manifest=json.loads((root/row['manifest']['file']).read_text());config=manifest['configurations'][0]
    audit=json.loads((root/config['baseline_evidence_audit']['file']).read_text())
    self.assertFalse(audit['strict_raw_audit_passed']);self.assertTrue(audit['missing_historical_evidence']);self.assertGreater(audit['complete_raw_attempts_audited'],0)
    self.assertTrue(any('schema_sha256' in gap['missing_fields'] for gap in audit['missing_historical_evidence']))
    self.assertTrue(admission.admit_smoke(manifest,root,row['id'],'P1')['admitted'])

 def test_accepted_runtime_patch_is_explicit_and_only_runtime_changes(self):
  with tempfile.TemporaryDirectory() as d:
   root,freeze,cache,_=self.fixture(d,['codex-gpt-5.6-luna-medium'])
   result=b.build(root,freeze,cache,root/'prepared',codex_runtime='codex-cli 0.155.0-alpha.16.3')
   self.assertEqual(result['blocked'],[]);self.assertEqual(len(result['prepared']),1)
   item=result['prepared'][0];manifest=json.loads((root/item['manifest']['file']).read_text());config=manifest['configurations'][0]
   self.assertEqual(config['historical_controls']['runtime'],'codex-cli 0.155.0-alpha.16')
   self.assertEqual(config['controls']['runtime'],'codex-cli 0.155.0-alpha.16.3')
   result=admission.admit_smoke(manifest,root,item['id'],'P1')
   self.assertEqual(result['runtime_transition']['authorization'],admission.RUNTIME_AUTHORIZATION)
   for field,value in [('model','other'),('effort','high'),('context_tokens',999999),('output_reserve_tokens',4096),('sampling',{'temperature':1})]:
    bad=copy.deepcopy(config);bad['controls'][field]=value
    with self.assertRaises(ValueError):admission.historical_controls(bad)
   bad=copy.deepcopy(config);bad['runtime_transition']['to']='codex-cli 0.156.1'
   with self.assertRaises(ValueError):admission.historical_controls(bad)

if __name__=='__main__':unittest.main()
