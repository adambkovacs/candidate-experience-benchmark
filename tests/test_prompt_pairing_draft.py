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

 def test_batch_preparation_retains_history_without_pairing_context_mismatch(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pred=self.fixture(root);self.write(root,1,[{'id':'old','model':'m','effort':'low','status':'completed','predictions_file':pred}])
   new='results/new.jsonl';(root/new).write_bytes((root/pred).read_bytes())
   (root/draft.BATCH_PREPARATION).write_text(json.dumps([{'id':'new','historical_parent':'old','model':'m','effort':'low','status':'complete','workflow':'batch10','prompt_variant':'P0','predictions_file':new}]))
   result=draft.build(root,draft.REGISTRIES+(draft.BATCH_PREPARATION,));index={r['id']:r for r in result['configurations']}
   self.assertEqual(index['old']['draft_category'],'historical_context_replaced_for_batch_pairing')
   self.assertEqual(index['old']['configuration']['predictions_file'],pred)
   self.assertEqual(index['new']['draft_category'],'eligible_generative_baseline_candidate')
   self.assertEqual(index['new']['coverage']['valid_status_records'],59)
   self.assertTrue(result['batch_baseline_links'][0]['new_baseline_complete'])
   self.assertFalse(result['eligible_paired_comparison'])

 def test_incomplete_new_batch_does_not_retire_existing_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);pred=self.fixture(root);self.write(root,1,[{'id':'old','model':'m','effort':'low','status':'completed','predictions_file':pred}])
   (root/draft.BATCH_PREPARATION).write_text(json.dumps([{'id':'new','historical_parent':'old','model':'m','effort':'low','status':'running','workflow':'batch10','prompt_variant':'P0'}]))
   r=draft.build(root,draft.REGISTRIES+(draft.BATCH_PREPARATION,))
   self.assertEqual(r['configurations'][0]['draft_category'],'eligible_generative_baseline_candidate')
   self.assertFalse(r['batch_baseline_links'][0]['new_baseline_complete'])

 def test_batch_parent_identity_changes_are_rejected(self):
  for field,value in [('historical_parent','missing'),('model','other'),('effort','high'),('workflow','single_record'),('prompt_variant','P1')]:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
    root=Path(d);pred=self.fixture(root);self.write(root,1,[{'id':'old','model':'m','effort':'low','status':'completed','predictions_file':pred}])
    new={'id':'new','historical_parent':'old','model':'m','effort':'low','status':'complete','workflow':'batch10','prompt_variant':'P0','predictions_file':pred};new[field]=value
    (root/draft.BATCH_PREPARATION).write_text(json.dumps([new]))
    with self.assertRaises(ValueError):draft.build(root,draft.REGISTRIES+(draft.BATCH_PREPARATION,))

 def test_user_hosted_replacement_is_not_new_local_work(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root);self.write(root,0,[{'id':'local-pending','status':'replaced_by_hosted_user_request','notes':'Paid hosted route is separately recorded'}]);r=draft.build(root)['configurations'][0]
   self.assertEqual(r['draft_category'],'local_surface_replaced_by_user_request')
   self.assertEqual(r['configuration']['notes'],'Paid hosted route is separately recorded')
   self.assertFalse(r['eligible_paired_comparison'])
