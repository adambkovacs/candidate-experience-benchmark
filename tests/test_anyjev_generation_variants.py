import argparse,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import anyjev_generation_control as runner
class GeneratedVariantsTests(unittest.TestCase):
 def args(self,path,variant):return argparse.Namespace(prompt_variant=variant,parent_baseline_id='anyjev-qwen06-generated-control',variant_preview_output=str(path),model_path='not-loaded',revision='configured-revision',device='mps',dtype='float32',limit=3,max_input_tokens=4096,max_new_tokens=4096)
 def test_default_legacy_messages_and_no_bundle(self):
  policy='rubric\r\nΩ';feedback='quoted Ω'
  legacy=runner.make_payload(feedback,policy,'not-sent','generated-off');messages=legacy['messages'];messages[0]['content']+='\nRequired JSON schema: '+json.dumps(legacy['response_format']['json_schema']['schema'])
  with patch('frozen_prompt_variants.compose_instruction',side_effect=AssertionError('bundle')):
   self.assertEqual(json.dumps(runner.control_messages(feedback,policy)).encode(),json.dumps(messages).encode())
 def test_live_variants_block_before_artifact_or_import(self):
  for variant in ['P1','P2']:
   with patch.object(runner,'verify_artifact',side_effect=AssertionError('artifact accessed')):
    with self.assertRaisesRegex(ValueError,'gates'):runner.run(argparse.Namespace(prompt_variant=variant))
 def test_offline_only_system_changes_after_embedded_schema(self):
  baseline=[]
  for variant in ['P0','P1','P2']:
   with tempfile.TemporaryDirectory() as d:
    args=self.args(Path(d)/'preview',variant)
    with patch.object(runner,'verify_artifact',side_effect=AssertionError('artifact accessed')):
     runner.run(args)
     with self.assertRaises(FileExistsError):runner.run(args)
    data=json.loads(Path(args.variant_preview_output).read_text());self.assertFalse(data['inference_performed']);self.assertEqual(data['instruction_role'],'system');self.assertFalse(data['controls']['enable_thinking']);self.assertFalse(data['controls']['do_sample'])
    self.assertEqual([r['record_id'] for r in data['requests']],['DEV-001','DEV-002','DEV-003'])
    if variant=='P0':baseline=data['requests']
    else:
     addition=(runner.ROOT/'prompts/variants-v1'/('P1-classifier.txt' if variant=='P1' else 'P2-classifier-sop.txt')).read_text()
     for previous,current in zip(baseline,data['requests']):
      self.assertEqual(current['messages'][0]['content'],previous['messages'][0]['content']+'\n\n'+addition)
      self.assertEqual(current['messages'][1],previous['messages'][1]);self.assertIn('Required JSON schema:',previous['messages'][0]['content'])
 def test_metadata_rejected_before_composition(self):
  rows=runner.read_rows(runner.ROOT/'data/pilot/inputs.jsonl');rows[0]['reference']='FORBIDDEN'
  with tempfile.TemporaryDirectory() as d:
   args=self.args(Path(d)/'preview','P2')
   with patch.object(runner,'read_rows',return_value=rows),patch.object(runner,'variant_instruction',side_effect=AssertionError('composition')):
    with self.assertRaisesRegex(ValueError,'input-only'):runner.run(args)
   self.assertFalse(Path(args.variant_preview_output).exists())
 def test_saved_p0_request_hashes_all_sixty(self):
  root=runner.ROOT;policy=(root/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0];inputs={r['id']:r for r in runner.read_rows(root/'data/pilot/inputs.jsonl')};saved=runner.read_rows(root/'results/anyjev-qwen06-generated-mps-2026-09-23/development.jsonl');self.assertEqual(len(saved),60)
  for r in saved:
   messages=runner.control_messages(inputs[r['id']]['feedback'],policy);self.assertEqual(r['request_sha256'],runner.digest(json.dumps(messages,sort_keys=True)));self.assertEqual(messages,runner.control_messages(inputs[r['id']]['feedback'],policy,'P0','saved-baseline'));self.assertFalse(r['enable_thinking']);self.assertFalse(r['do_sample'])
