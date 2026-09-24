import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_prompt_variants import paired_condition_controls,canonical_hash
class RuntimeTransitionTests(unittest.TestCase):
 def setUp(self):
  c=json.loads((ROOT/'results/prompt-comparison-v1-2026-09-24/subscription-codex-runtime163-v1/codex-gpt-5.6-luna-medium/execution-manifest.json').read_text())['configurations'][0]
  self.m={'controls':c['controls']['adapter_controls'],'historical_controls':c['historical_controls']['adapter_controls'],'runtime_transition':c['runtime_transition'],'conditions':{v:{'extractor':'codex_batch_v1'} for v in ['P0','P1','P2']}}
  self.m['historical_controls_sha256']=canonical_hash(self.m['historical_controls'])
 def test_approved_patch_keeps_both_versions(self):
  self.assertEqual(paired_condition_controls(self.m,'P0')['cli_version'],'codex-cli 0.155.0-alpha.16')
  self.assertEqual(paired_condition_controls(self.m,'P2')['cli_version'],'codex-cli 0.155.0-alpha.16.3')
 def test_effort_change_is_not_covered_by_approval(self):
  self.m['controls']['effort']='high'
  with self.assertRaisesRegex(ValueError,'other control'):paired_condition_controls(self.m,'P1')
 def test_unapproved_version_rejected(self):
  self.m['runtime_transition']['to']='codex-cli other'
  with self.assertRaisesRegex(ValueError,'Unsupported'):paired_condition_controls(self.m,'P1')
 def test_no_silent_historical_override(self):
  del self.m['runtime_transition']
  with self.assertRaisesRegex(ValueError,'require runtime'):paired_condition_controls(self.m,'P0')
 def test_cannot_apply_codex_exception_to_other_adapter(self):
  self.m['conditions']['P0']['extractor']='claude_batch_v1'
  with self.assertRaisesRegex(ValueError,'other control'):paired_condition_controls(self.m,'P0')
if __name__=='__main__':unittest.main()
