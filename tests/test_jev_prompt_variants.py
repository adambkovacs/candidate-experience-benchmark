import argparse,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import jev_benchmark as j
class JevPreviewTests(unittest.TestCase):
 def args(self,**kw):
  values=dict(surface='openjev',mode='generated-off',model='diffusiongemma-26b',base_url='http://localhost:8000',prompt_variant='P1',parent_baseline_id='baseline',variant_preview_output=None,start=1,limit=3)
  return argparse.Namespace(**(values|kw))
 def test_composition_preserves_entire_request(self):
  for mode in ('generated-off','generated-on'):
   base=j.make_payload('feedback','policy','diffusiongemma-26b',mode)
   for variant in ('P0','P1','P2'):
    result,audit=j.generated_variant_payload('feedback','policy','diffusiongemma-26b',mode,variant,'baseline')
    if variant=='P0':self.assertEqual(json.dumps(result),json.dumps(base))
    else:self.assertTrue(result['messages'][0]['content'].startswith(base['messages'][0]['content']));self.assertNotEqual(result,base)
    result['messages'][0]=base['messages'][0];self.assertEqual(result,base)
 def test_live_and_direct_rejected_before_side_effects(self):
  for args in (self.args(),self.args(mode='fixed'),self.args(surface='typesafe',mode='official'),self.args(mode='thinking',prompt_variant='P0')):
   with patch.object(j,'load_key',side_effect=AssertionError('key')),patch.object(j,'fetch',side_effect=AssertionError('network')),patch.object(j,'BudgetLedger',side_effect=AssertionError('ledger')):
    with self.assertRaises(ValueError):j.run(args)
 def test_preview_is_offline_exclusive(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'preview.json';a=self.args(variant_preview_output=str(p))
   with patch.object(j,'load_key',side_effect=AssertionError('key')),patch.object(j,'fetch',side_effect=AssertionError('network')),patch.object(j,'BudgetLedger',side_effect=AssertionError('ledger')):
    j.run(a)
    with self.assertRaises(FileExistsError):j.run(a)
   result=json.loads(p.read_text());self.assertEqual(len(result['requests']),3);self.assertFalse(result['rendered_prompt_verified'])
 def test_metadata_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'preview.json';rows=[{'id':str(i),'feedback':'text','labels':{}} for i in range(60)]
   with patch.object(j,'read_rows',return_value=rows):
    with self.assertRaises(ValueError):j.run(self.args(variant_preview_output=str(p)))
   self.assertFalse(p.exists())
 def test_default_gate_has_no_bundle_dependency(self):
  with patch.dict(sys.modules,{'frozen_prompt_variants':None}):self.assertFalse(j.variant_gate_or_preview(self.args(prompt_variant=None,parent_baseline_id=None)))
 def test_saved_120_canonical_hashes(self):
  inputs={r['id']:r['feedback'] for r in j.read_rows(j.ROOT/'data/pilot/inputs.jsonl')};policy=(j.ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
  for mode in ('generated-off','generated-on'):
   rows=j.read_rows(j.ROOT/f'results/openjev-local-{mode}-2026-09-23/development.jsonl');self.assertEqual(len(rows),60)
   for row in rows:
    payload,_=j.generated_variant_payload(inputs[row['id']],policy,row['requested_model'],mode,'P0','baseline')
    self.assertEqual(row['request_sha256'],j.digest(json.dumps(payload,sort_keys=True)))
if __name__=='__main__':unittest.main()
