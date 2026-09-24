import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_prompt_protocol import audit

class SavedExecutionAuditTests(unittest.TestCase):
 def setUp(self):
  self.manifest=json.loads((ROOT/'results/prompt-comparison-v1-2026-09-24/paired-reports/openrouter-paid-gemma4-31b-off/paired-manifest.json').read_text())
 def test_real_completed_pair_remains_observational(self):
  result=audit(self.manifest,ROOT)
  self.assertEqual(result['status'],'verified_observational')
  self.assertFalse(result['fully_verified_controls'])
 def test_changed_manifest_binding_is_rejected(self):
  self.manifest['execution_evidence']['P1']['execution_manifest']['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'hash mismatch'):audit(self.manifest,ROOT)
 def test_other_condition_smoke_cannot_authorize_development(self):
  self.manifest['execution_evidence']['P1']['smoke_supplement']=copy.deepcopy(self.manifest['execution_evidence']['P2']['smoke_supplement'])
  with self.assertRaisesRegex(ValueError,'supplement binding'):audit(self.manifest,ROOT)
 def test_reporting_another_output_is_rejected(self):
  self.manifest['conditions']['P1']['predictions']=copy.deepcopy(self.manifest['conditions']['P0']['predictions'])
  with self.assertRaisesRegex(ValueError,'journalled outputs'):audit(self.manifest,ROOT)

if __name__=='__main__':unittest.main()
