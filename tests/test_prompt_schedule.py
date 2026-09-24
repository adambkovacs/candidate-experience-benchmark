import fcntl,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prompt_schedule as s
import prompt_execution_gates as g

class ScheduleTests(unittest.TestCase):
 def fixture(self,d):
  root=Path(d);path=root/'schedule.json';path.write_text(json.dumps({'order':[{'id':'a','conditions':['P1','P2']},{'id':'b','conditions':['P2','P1']}]}))
  evidence=root/'evidence.json';evidence.write_text('{}')
  return root,{'file':path.name,'sha256':g.sha(path.read_bytes())},root/'journal.jsonl',[{'file':evidence.name,'sha256':g.sha(evidence.read_bytes())}]
 def test_full_order_and_independent_configurations(self):
  with tempfile.TemporaryDirectory() as d:
   root,spec,journal,evidence=self.fixture(d)
   a=s.claim(spec,journal,'a','P1','smoke',root);b=s.claim(spec,journal,'b','P2','smoke',root)
   s.finish(spec,journal,a['attempt_id'],'completed',evidence,root);s.finish(spec,journal,b['attempt_id'],'stopped',evidence,root)
   for stage in ('inspected_admission','development'):
    claim=s.claim(spec,journal,'a','P1',stage,root);s.finish(spec,journal,claim['attempt_id'],'completed',evidence,root)
   self.assertEqual(s.claim(spec,journal,'a','P2','smoke',root)['stage'],'smoke')
   self.assertEqual(s.claim(spec,journal,'b','P1','smoke',root)['stage'],'smoke')
 def test_order_duplicate_and_unmatched_start(self):
  with tempfile.TemporaryDirectory() as d:
   root,spec,journal,evidence=self.fixture(d)
   for condition,stage in (('P2','smoke'),('P1','development'),('P1','inspected_admission')):
    with self.assertRaises(ValueError):s.claim(spec,journal,'a',condition,stage,root)
   claimed=s.claim(spec,journal,'a','P1','smoke',root)
   for stage in s.STAGES:
    with self.assertRaises(ValueError):s.claim(spec,journal,'a','P1',stage,root)
   with self.assertRaises(ValueError):s.finish(spec,journal,'unknown','completed',evidence,root)
   s.finish(spec,journal,claimed['attempt_id'],'completed',evidence,root)
   with self.assertRaises(ValueError):s.finish(spec,journal,claimed['attempt_id'],'completed',evidence,root)
   with self.assertRaises(ValueError):s.claim(spec,journal,'a','P1','smoke',root)
   with self.assertRaises(ValueError):s.claim(spec,journal,'a','P1','development',root)
 def test_actual_file_lock_contention(self):
  with tempfile.TemporaryDirectory() as d:
   root,spec,journal,_=self.fixture(d)
   with journal.open('a+b') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with self.assertRaises(RuntimeError):s.claim(spec,journal,'a','P1','smoke',root)
    self.assertEqual(journal.read_bytes(),b'')
   self.assertEqual(s.claim(spec,journal,'a','P1','smoke',root)['stage'],'smoke')
 def test_hash_and_forged_order_tampering(self):
  for mutation in ('hash','rehashed_order','source','evidence','tail'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
    root,spec,journal,evidence=self.fixture(d);c=s.claim(spec,journal,'a','P1','smoke',root)
    s.finish(spec,journal,c['attempt_id'],'completed',evidence,root)
    if mutation=='source':(root/'schedule.json').write_text('{}')
    elif mutation=='evidence':(root/'evidence.json').write_text('changed')
    elif mutation=='tail':journal.write_bytes(journal.read_bytes()+b'{')
    else:
     events=[json.loads(x) for x in journal.read_text().splitlines()];events[1]['stage']='development'
     if mutation=='rehashed_order':
      for i,event in enumerate(events):
       event['previous_sha256']=events[i-1]['event_sha256'] if i else None;event['event_sha256']=s._digest(event)
     journal.write_text(''.join(json.dumps(x)+'\n' for x in events))
    with self.assertRaises(ValueError):s.claim(spec,journal,'b','P2','smoke',root)
 def test_schedule_rebinding_and_stopped_retry(self):
  with tempfile.TemporaryDirectory() as d:
   root,spec,journal,evidence=self.fixture(d);c=s.claim(spec,journal,'a','P1','smoke',root);s.finish(spec,journal,c['attempt_id'],'stopped',evidence,root)
   with self.assertRaises(ValueError):s.claim(spec,journal,'a','P1','inspected_admission',root)
   (root/'copy.json').write_bytes((root/'schedule.json').read_bytes());new={**spec,'file':'copy.json'}
   with self.assertRaises(ValueError):s.claim(new,journal,'b','P2','smoke',root)
if __name__=='__main__':unittest.main()
