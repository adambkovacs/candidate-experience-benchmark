import argparse,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import development_benchmark as runner
class HttpVariantsTests(unittest.TestCase):
 def test_default_exact_legacy_serialization_without_bundle(self):
  instruction='rubric\r\nΩ';schema={'type':'object'};feedback='quoted Ω'
  with patch('frozen_prompt_variants.compose_instruction',side_effect=AssertionError('bundle')):
   text,audit=runner.variant_instruction(instruction)
   payload=runner.make_payload('model',feedback,text,schema)
  legacy={'model':'model','temperature':0,'max_tokens':512,'stream':False,'messages':[{'role':'system','content':instruction},{'role':'user','content':json.dumps({'feedback':feedback})}],'response_format':{'type':'json_schema','json_schema':{'name':'judgments','strict':True,'schema':schema}}}
  self.assertEqual(json.dumps(payload).encode(),json.dumps(legacy).encode());self.assertIsNone(audit)
 def test_live_p1_p2_block_before_network_and_auth(self):
  for variant in ['P1','P2']:
   with patch.object(runner.OPENER,'open',side_effect=AssertionError('network')),patch.object(runner.os.environ,'get',side_effect=AssertionError('auth')):
    with self.assertRaisesRegex(ValueError,'gates'):runner.run(argparse.Namespace(prompt_variant=variant))
 def test_offline_variants_only_change_system_and_exclusive_output(self):
  baseline=[]
  for variant in ['P0','P1','P2']:
   with tempfile.TemporaryDirectory() as d:
    args=argparse.Namespace(model='model',limit=3,prompt_variant=variant,parent_baseline_id='http-baseline',variant_preview_output=str(Path(d)/'preview.json'))
    with patch.object(runner.OPENER,'open',side_effect=AssertionError('network')),patch.object(runner.os.environ,'get',side_effect=AssertionError('auth')):
     runner.run(args)
     with self.assertRaises(FileExistsError):runner.run(args)
    data=json.loads(Path(args.variant_preview_output).read_text());self.assertFalse(data['inference_performed']);self.assertEqual([r['record_id'] for r in data['requests']],['DEV-001','DEV-002','DEV-003'])
    if variant=='P0':baseline=data['requests']
    else:
     addition=(runner.ROOT/'prompts/variants-v1'/('P1-classifier.txt' if variant=='P1' else 'P2-classifier-sop.txt')).read_text()
     for original,current in zip(baseline,data['requests']):
      self.assertEqual(current['prompt_variant']['instruction_role'],'system');payload=current['request'];self.assertEqual(payload['messages'][0]['content'],original['request']['messages'][0]['content']+'\n\n'+addition)
      restored=copy.deepcopy(payload);restored['messages'][0]=original['request']['messages'][0];self.assertEqual(restored,original['request'])
 def test_unexpected_metadata_fails_before_composition(self):
  rows=runner.read_rows(runner.ROOT/'data/pilot/inputs.jsonl');rows[0]['reference']='FORBIDDEN'
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'preview';args=argparse.Namespace(prompt_variant='P2',parent_baseline_id='baseline',variant_preview_output=str(path),model='model',limit=3)
   with patch.object(runner,'read_rows',return_value=rows),patch.object(runner,'variant_instruction',side_effect=AssertionError('composition')):
    with self.assertRaisesRegex(ValueError,'input-only'):runner.run(args)
   self.assertFalse(path.exists())
 def test_saved_http_baseline_hash_and_control_parity(self):
  rows=runner.read_rows(runner.ROOT/'results/qwen3-0.6b-q4_k_m-2026-09-21/development.jsonl');inputs={r['id']:r for r in runner.read_rows(runner.ROOT/'data/pilot/inputs.jsonl')};schema=json.loads((runner.ROOT/'schemas/judgments.schema.json').read_text());instruction=runner.baseline_instruction()
  self.assertEqual(len(rows),60)
  for r in rows:
   payload=runner.make_payload(r['requested_model'],inputs[r['id']]['feedback'],instruction,schema)
   self.assertEqual(r['policy_sha256'],runner.digest(instruction));self.assertEqual(r['input_sha256'],runner.digest(inputs[r['id']]['feedback']));self.assertEqual(r['schema_sha256'],runner.digest(json.dumps(schema,sort_keys=True)))
   self.assertEqual(payload['temperature'],r['temperature']);self.assertEqual(payload['max_tokens'],r['max_tokens'])
