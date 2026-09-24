import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_subscription_prompt_manifests as b
import prompt_admission as admission
ROOT=Path(__file__).resolve().parents[1]

class BuilderTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d);source=json.loads((ROOT/'results/prompt-pairing-reconciled-baselines-2026-09-24.json').read_text())
  selected=[x for x in source['configurations'] if x['id'] in ('codex-gpt-5.6-luna-medium','opus55-low-batch10')]
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
if __name__=='__main__':unittest.main()
