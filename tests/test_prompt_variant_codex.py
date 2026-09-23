import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evaluate_prompt_variants as e
import codex_benchmark as c
ROOT=Path(__file__).resolve().parents[1]
class CodexEvidenceTests(unittest.TestCase):
 def fixture(self):
  folder=ROOT/'results/codex-gpt-6-sol-high-batch10-resumed-2026-09-23'
  raw=e.rows_from((folder/'development-attempts.jsonl').read_bytes());pred={r['id']:r for r in e.rows_from((folder/'development.jsonl').read_bytes())};inputs={r['id']:r for r in e.rows_from((ROOT/'data/pilot/inputs.jsonl').read_bytes())};policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
  return [raw,pred,inputs,c.baseline_instruction(policy,'batch10'),e.extract_codex_controls(raw[0])]
 def audit(self,args,retries=[]):return e.audit_codex_batches(*args,'latest_chronological',retries)
 def test_saved_and_count_once(self):
  args=self.fixture();out=self.audit(args);self.assertEqual(len(out),6);self.assertEqual(e.telemetry(out)['attempt_seconds'],sum(r['elapsed_seconds'] for r in args[0]));self.assertGreater(e.telemetry(out)['input_tokens'],0)
 def test_tampering_and_hash_only_reject(self):
  for field in ('request','record_order','usage','effort','phase','command','raw_events'):
   with self.subTest(field=field):
    args=self.fixture();args[0][0][field]=None
    with self.assertRaises((ValueError,TypeError,KeyError)):self.audit(args)
 def test_timeout_retry_retains_time_unknown_usage(self):
  args=self.fixture();r=copy.deepcopy(args[0][0]);r.update(started_utc='2026-01-01T00:00:00Z',status='service_error',error_type='TimeoutExpired',usage=None,prediction=None,raw_events=None,elapsed_seconds=600);args[0].insert(0,r)
  with self.assertRaises(ValueError):self.audit(args)
  retry=args[0][1]['id']+'@'+args[0][1]['started_utc'];out=self.audit(args,[retry]);self.assertEqual(len(out),7);self.assertIsNone(e.telemetry(out)['input_tokens']);self.assertEqual(e.telemetry(out)['attempt_seconds'],sum(r['elapsed_seconds'] for r in args[0]))
 def test_exploded_linkage(self):
  args=self.fixture();args[1]['DEV-001']['started_utc']='changed'
  with self.assertRaises(ValueError):self.audit(args)
if __name__=='__main__':unittest.main()
