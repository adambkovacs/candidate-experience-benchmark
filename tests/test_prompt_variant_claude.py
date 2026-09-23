import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_prompt_variants as e
from claude_benchmark import baseline_instruction
ROOT=Path(__file__).resolve().parents[1]
class ClaudeEvidenceTests(unittest.TestCase):
 def fixture(self):
  folder=ROOT/'results/claude-subscription-2026-09-23'
  raw=e.rows_from((folder/'opus55-low-batch10-development.jsonl.batches.jsonl').read_bytes())
  pred={r['id']:r for r in e.rows_from((folder/'opus55-low-batch10-development.jsonl').read_bytes())}
  inputs={r['id']:r for r in e.rows_from((ROOT/'data/pilot/inputs.jsonl').read_bytes())}
  return raw,pred,inputs,baseline_instruction('batch10'),e.extract_claude_controls(raw[0])
 def audit(self,args,retries=[]):return e.audit_claude_batches(*args,'latest_chronological',retries)
 def test_saved_full_requests_and_batch_accounting(self):
  args=self.fixture();out=self.audit(args);t=e.telemetry(out)
  self.assertEqual(t['attempts'],6);self.assertEqual(t['attempt_seconds'],sum(r['elapsed_seconds'] for r in args[0]));self.assertGreater(t['input_tokens'],24000)
 def test_tampering(self):
  for field in ('request','ids','usage','effort','phase','schema_sha256','raw_events'):
   with self.subTest(field=field):
    args=self.fixture();args[0][0][field]=None
    with self.assertRaises((ValueError,TypeError,KeyError)):self.audit(args)
 def test_synthetic_timeout_retry_retained_once(self):
  args=list(self.fixture());first=copy.deepcopy(args[0][0]);first.update(attempt_id='failed-001',status='service_error',error_type='TimeoutExpired',prediction=None,usage=None,model_usage=None,raw_events=None,started_utc='2026-01-01T00:00:00Z',elapsed_seconds=600)
  args[0].insert(0,first)
  with self.assertRaises(ValueError):self.audit(args)
  out=self.audit(args,['batch-001']);self.assertEqual(len(out),7);self.assertIsNone(e.telemetry(out)['input_tokens']);self.assertEqual(e.telemetry(out)['attempt_seconds'],sum(r['elapsed_seconds'] for r in args[0]))
 def test_membership_and_selected_output(self):
  args=self.fixture();args[1]['DEV-001']['batch_position']=2
  with self.assertRaises(ValueError):self.audit(args)
if __name__=='__main__':unittest.main()
