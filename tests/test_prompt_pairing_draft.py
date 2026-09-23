import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_prompt_pairing_draft as draft
class DraftTests(unittest.TestCase):
 def fixture(self,root):
  (root/'data/pilot').mkdir(parents=True);(root/'results').mkdir()
  (root/'data/pilot/inputs.jsonl').write_text(''.join(json.dumps({'id':f'DEV-{i:03d}','feedback':'synthetic'})+'\n' for i in range(1,61)))
  pred='results/predictions.jsonl';(root/pred).write_text(''.join(json.dumps({'id':f'DEV-{i:03d}','phase':'development','status':'invalid_output' if i==1 else 'ok'})+'\n' for i in range(1,61)))
  for registry in draft.REGISTRIES:
   path=root/registry;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('[]')
  return pred
 def write(self,root,index,rows):(root/draft.REGISTRIES[index]).write_text(json.dumps(rows))
 def test_preserves_every_entry_and_deterministic_failure_denominator(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pred=self.fixture(root);rows=[{'id':'baseline','status':'complete','model':'known','effort':'off','predictions_file':pred},{'id':'pending','status':'running','notes':'retain this dependency'},{'id':'history','effort':'max','status':'completed','predictions_file':pred},{'id':'rules-v1','status':'complete'}];self.write(root,0,rows)
   result=draft.build(root);self.assertEqual(result,draft.build(root));self.assertEqual(result['configuration_count'],4);index={r['id']:r for r in result['configurations']}
   self.assertEqual([r['configuration'] for r in result['configurations']],rows)
   self.assertEqual(index['baseline']['coverage']['valid_status_records'],59);self.assertTrue(index['baseline']['coverage']['exact_60_input_ids'])
   self.assertFalse(result['eligible_paired_comparison']);self.assertEqual(index['pending']['draft_category'],'pending_generative_candidate')
   self.assertEqual(index['rules-v1']['draft_category'],'deterministic_baseline')
   # Sharing a prediction file is explicitly flagged, including historical views.
   self.assertEqual(index['history']['underlying_draft_category'],'historical_future_exclusion')
 def test_unknown_specialist_pending_and_direct_not_converted(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pred=self.fixture(root);self.write(root,5,[{'id':'unknown-specialist','status':'complete','predictions_file':pred},{'id':'laya-english','status':'unsupported_length'},{'id':'semif-generated-bf16','status':'ready_for_local_validation'}]);index={r['id']:r for r in draft.build(root)['configurations']}
   self.assertEqual(index['unknown-specialist']['draft_category'],'pending_method_verification');self.assertEqual(index['laya-english']['draft_category'],'direct_specialist');self.assertEqual(index['semif-generated-bf16']['draft_category'],'pending_generative_candidate')
 def test_missing_or_incomplete_or_smoke_cannot_be_eligible(self):
  for mode in ['missing','partial','smoke']:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);pred=self.fixture(root)
    if mode=='missing':(root/pred).unlink()
    elif mode=='partial':(root/pred).write_text('{"id":"DEV-001","status":"ok"}\n')
    else:(root/pred).write_text((root/pred).read_text().replace('development','smoke'))
    self.write(root,0,[{'id':'candidate','status':'complete','predictions_file':pred}]);self.assertEqual(draft.build(root)['configurations'][0]['draft_category'],'pending_generative_candidate')
 def test_sonnet_views_require_selection_and_hash_changes_track_sources(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pred=self.fixture(root);self.write(root,2,[{'id':i,'status':'completed','predictions_file':pred} for i in ['sonnet5-low-first-pass','sonnet5-low-with-retry']]);before=draft.build(root)
   self.assertTrue(all(r['draft_category']=='overlapping_baseline_view' for r in before['configurations']))
   (root/pred).write_text((root/pred).read_text()+'\n');after=draft.build(root);self.assertNotEqual(before['configurations'][0]['evidence'][0]['sha256'],after['configurations'][0]['evidence'][0]['sha256'])
 def test_reference_path_refused_and_registry_duplicates_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root)
   with self.assertRaises(ValueError):draft.file_bytes(root,'data/pilot/proposed_labels.jsonl')
   self.write(root,0,[{'id':'duplicate'}]);self.write(root,1,[{'id':'duplicate'}])
   with self.assertRaisesRegex(ValueError,'Duplicate'):draft.build(root)

 def test_complete_service_failure_retains_sixty_record_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pred=self.fixture(root);rows=[json.loads(x) for x in (root/pred).read_text().splitlines()];rows[0]['status']='service_error';(root/pred).write_text(''.join(json.dumps(x)+'\n' for x in rows))
   self.write(root,4,[{'id':'retained-service-failure','status':'complete_with_service_failure','predictions_file':pred}]);r=draft.build(root)['configurations'][0]
   self.assertEqual(r['draft_category'],'eligible_generative_baseline_candidate');self.assertTrue(r['coverage']['exact_60_input_ids']);self.assertEqual(r['coverage']['valid_status_records'],59);self.assertFalse(r['eligible_paired_comparison'])
