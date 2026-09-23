import argparse,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import claude_benchmark as single
import claude_batch_benchmark as batch

class ClaudeVariantsTests(unittest.TestCase):
 def test_default_has_no_bundle_dependency_and_exact_bytes(self):
  with patch('frozen_prompt_variants.compose_instruction',side_effect=AssertionError('bundle accessed')):
   text,audit=single.variant_instruction('base\r\nΩ',None,None)
  self.assertEqual(text,'base\r\nΩ');self.assertIsNone(audit)
 def test_explicit_composition_preserves_role_and_base(self):
  for variant in ['P0','P1','P2']:
   text,audit=single.variant_instruction('base\r\nΩ',variant,'baseline')
   self.assertEqual(audit['instruction_role'],'system');self.assertEqual(audit['parent_baseline_id'],'baseline')
   self.assertEqual(text,'base\r\nΩ' if variant=='P0' else 'base\r\nΩ\n\n'+(single.ROOT/'prompts/variants-v1'/('P1-classifier.txt' if variant=='P1' else 'P2-classifier-sop.txt')).read_text())
 def test_non_p0_live_fails_before_any_process(self):
  for module in [single,batch]:
   with patch('subprocess.run',side_effect=AssertionError('process attempted')):
    with self.assertRaisesRegex(ValueError,'gates'):module.run(argparse.Namespace(prompt_variant='P1',parent_baseline_id='baseline',variant_preview_output=None))
 def test_preview_is_exclusive_offline_and_preserves_schema_order(self):
  rows=[{'id':f'DEV-{i:03d}','feedback':f'feedback{i}','reference':'FORBIDDEN'} for i in range(1,13)]
  for workflow,module in [('single_record',single),('batch10',batch)]:
   with tempfile.TemporaryDirectory() as d:
    args=argparse.Namespace(prompt_variant='P2',parent_baseline_id='baseline',variant_preview_output=str(Path(d)/'offline-preview.json'),limit=12,offset=0)
    with patch.object(single,'read_rows',return_value=rows),patch('subprocess.run',side_effect=AssertionError('process attempted')):
     module.run(args)
     with self.assertRaises(FileExistsError):module.run(args)
    data=json.loads(Path(args.variant_preview_output).read_text());self.assertTrue(data['offline_only']);self.assertFalse(data['inference_performed'])
    requests=data['requests'];self.assertEqual(len(requests),12 if workflow=='single_record' else 2)
    ids=[rid for request in requests for rid in request['record_ids']];self.assertEqual(ids,[r['id'] for r in rows])
    self.assertNotIn('FORBIDDEN',json.dumps(data))
    for request in requests:
     self.assertEqual(request['prompt_variant']['instruction_role'],'system')
     if workflow=='batch10':self.assertEqual(request['schema'],batch.batch_schema(request['record_ids']))
     else:self.assertEqual(request['schema'],json.loads((single.ROOT/'schemas/judgments.schema.json').read_text()))
