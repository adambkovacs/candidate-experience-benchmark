import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gemini_batch_benchmark as g
class GeminiPreviewTests(unittest.TestCase):
 def args(self,root,**kw):
  a=dict(agy='/nonexistent',model='gemini-3.8-flash-low',effort='low',timeout=600,workflow_mode='strict',phase='development',offset=0,limit=60,output=str(root/'predictions.jsonl'),attempts=str(root/'attempts.jsonl'),prompt_variant='P2',parent_baseline_id='gemini-batch-parent',variant_preview_output=str(root/'preview.json'))
  a.update(kw);return SimpleNamespace(**a)
 def test_preview_is_offline_and_preserves_full_batch_schema(self):
  with tempfile.TemporaryDirectory() as d:
   a=self.args(Path(d))
   with mock.patch.object(g,'clean_environment',side_effect=AssertionError('credentials forbidden')),mock.patch.object(g.subprocess,'run',side_effect=AssertionError('process/network forbidden')):g.run(a)
   p=json.loads(Path(a.variant_preview_output).read_text());self.assertFalse(p['inference_performed']);self.assertEqual(p['instruction_role'],'cli_combined_prompt');self.assertEqual(p['agent_definition'],g.AGENT)
   rows=g.read_rows(g.ROOT/'data/pilot/inputs.jsonl');policy=(g.ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
   self.assertEqual(len(p['requests']),6)
   for i,r in enumerate(p['requests']):
    group=rows[i*10:(i+1)*10];self.assertEqual(r['record_ids'],[x['id'] for x in group]);self.assertEqual(r['request']['prompt'],g.batch_prompt(policy,group,'P2',a.parent_baseline_id));self.assertEqual(r['request']['output_schema'],g.batch_schema(group));self.assertEqual(r['prompt_variant']['instruction_role'],'cli_combined_prompt')
   self.assertFalse(Path(a.output).exists());self.assertFalse(Path(a.attempts).exists())
   with self.assertRaises(FileExistsError):g.run(a)
 def test_live_variants_reject_before_auth(self):
  with tempfile.TemporaryDirectory() as d:
   for v in ('P1','P2'):
    with mock.patch.object(g,'clean_environment',side_effect=AssertionError('auth forbidden')):
     with self.assertRaisesRegex(ValueError,'gates'):g.run(self.args(Path(d),prompt_variant=v,variant_preview_output=None))
 def test_default_gate_needs_no_bundle_or_inputs(self):
  with mock.patch.object(g,'read_rows',side_effect=AssertionError('unexpected reads')):self.assertFalse(g.variant_gate_or_preview(SimpleNamespace()))
 def test_invalid_preview_membership_and_missing_variant(self):
  with tempfile.TemporaryDirectory() as d:
   for kw in ({'offset':1,'limit':3},{'prompt_variant':None},{'parent_baseline_id':None}):
    with mock.patch.object(g,'clean_environment',side_effect=AssertionError('auth forbidden')):
     with self.assertRaises(ValueError):g.run(self.args(Path(d),**kw))
 def test_saved_historical_p0_prompt_schema_and_membership(self):
  inputs={r['id']:r for r in g.read_rows(g.ROOT/'data/pilot/inputs.jsonl')};policy=(g.ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0];count=0
  folder=g.ROOT/'results/antigravity-gemini36-flash-high-native129-2026-09-23'
  for name in ('smoke-attempts.jsonl','development-attempts.jsonl'):
   for line in (folder/name).read_text().splitlines():
    old=json.loads(line);group=[inputs[k] for k in old['record_order']]
    self.assertEqual(g.batch_prompt(policy,group),old['request']['prompt']);self.assertEqual(g.batch_prompt(policy,group,'P0','historical-parent'),old['request']['prompt']);self.assertEqual(g.batch_schema(group),old['request']['output_schema']);count+=1
  self.assertEqual(count,4)
