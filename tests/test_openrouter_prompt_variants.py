import argparse,copy,json,sys,tempfile,unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_paid_benchmark as runner

class OpenRouterVariantsTests(unittest.TestCase):
 source=runner.ROOT/'results/openrouter-parallel-gemma31-off-2026-09-23/development.jsonl'
 def args(self,d,variant='P0'):
  saved=json.loads(self.source.read_text().splitlines()[0]);request=saved['request'];prices=request['provider']['max_price']
  return argparse.Namespace(prompt_variant=variant,parent_baseline_id='openrouter-paid-gemma4-31b-off',variant_preview_output=str(Path(d)/'preview.json'),variant_baseline_attempts=str(self.source),model=saved['requested_model'],provider=saved['provider_endpoint']['tag'],reasoning=saved['reasoning_effort'],max_tokens=request['max_tokens'],max_input_price=Decimal(str(prices['prompt'])),max_output_price=Decimal(str(prices['completion'])),phase='smoke',start=1)
 def test_default_policy_has_no_bundle_dependency(self):
  with patch('frozen_prompt_variants.compose_instruction',side_effect=AssertionError('bundle read')):
   self.assertEqual(runner.variant_instruction('exact\r\nΩ'),('exact\r\nΩ',None))
 def test_live_p1_p2_reject_before_key_network_ledger_or_output(self):
  for variant in ['P1','P2']:
   with patch.object(runner,'load_key',side_effect=AssertionError('key read')),patch.object(runner,'fetch',side_effect=AssertionError('network')),patch.object(runner,'BudgetLedger',side_effect=AssertionError('ledger')):
    with self.assertRaisesRegex(ValueError,'gates'):runner.run(argparse.Namespace(prompt_variant=variant))
 def test_offline_p0_exact_saved_payload_and_p1_p2_change_only_system(self):
  originals=[json.loads(x)['request'] for x in self.source.read_text().splitlines()[:3]]
  for variant in ['P0','P1','P2']:
   with tempfile.TemporaryDirectory() as d:
    args=self.args(d,variant)
    with patch.object(runner,'load_key',side_effect=AssertionError('key read')),patch.object(runner,'fetch',side_effect=AssertionError('network')),patch.object(runner,'BudgetLedger',side_effect=AssertionError('ledger')):
     runner.run(args)
     with self.assertRaises(FileExistsError):runner.run(args)
    data=json.loads(Path(args.variant_preview_output).read_text());self.assertFalse(data['inference_performed']);self.assertFalse(data['reference_labels_read']);self.assertEqual(data['requested_model'],args.model)
    self.assertEqual([q['record_id'] for q in data['requests']],['DEV-001','DEV-002','DEV-003'])
    for q,original in zip(data['requests'],originals):
     payload=q['request'];self.assertEqual(q['prompt_variant']['instruction_role'],'system')
     if variant=='P0':self.assertEqual(payload,original)
     else:
      addition=(runner.ROOT/'prompts/variants-v1'/('P1-classifier.txt' if variant=='P1' else 'P2-classifier-sop.txt')).read_text()
      self.assertEqual(payload['messages'][0]['content'],original['messages'][0]['content']+'\n\n'+addition)
      restored=copy.deepcopy(payload);restored['messages'][0]=original['messages'][0];self.assertEqual(restored,original)
 def test_unexpected_input_metadata_rejected_before_output(self):
  rows=runner.read_rows(runner.ROOT/'data/pilot/inputs.jsonl');rows[0]['reference']='FORBIDDEN'
  with tempfile.TemporaryDirectory() as d:
   args=self.args(d)
   with patch.object(runner,'read_rows',return_value=rows),patch.object(runner,'variant_instruction',side_effect=AssertionError('composition')):
    with self.assertRaisesRegex(ValueError,'only ID and feedback'):runner.run(args)
   self.assertFalse(Path(args.variant_preview_output).exists())
 def test_snapshot_controls_mismatch_rejected(self):
  for field,value in [('max_tokens',2048),('reasoning','on'),('provider','other')]:
   with tempfile.TemporaryDirectory() as d:
    args=self.args(d);setattr(args,field,value)
    with self.assertRaises(ValueError):runner.run(args)
    self.assertFalse(Path(args.variant_preview_output).exists())
