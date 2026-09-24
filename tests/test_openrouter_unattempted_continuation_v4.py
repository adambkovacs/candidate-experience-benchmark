import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_unattempted_continuation_v4 as v4

class V4OfflineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.path=v4.DEST/'qwen27-low-hosted-addendum-v1-p2/draft-manifest.json'
  cls.manifest=json.loads(cls.path.read_text())
 def test_exact_five_with_full_disjoint_history(self):
  m=self.manifest;v4.validate(m,False)
  self.assertEqual(m['remaining_ids'],[f'DEV-{i:03}' for i in range(56,61)])
  self.assertEqual(len(m['histories']),3)
  self.assertEqual([r['id'] for h in m['histories'] for r in v4.base.lines(h['output'])], [f'DEV-{i:03}' for i in range(1,56)])
 def test_dev055_timeout_cannot_replay(self):
  m=copy.deepcopy(self.manifest);m['remaining_ids'].insert(0,'DEV-055')
  with self.assertRaises(ValueError):v4.validate(m,False)
 def test_sealed_v3_lineage_and_wrapper_bound(self):
  m=copy.deepcopy(self.manifest);m['lineage_v3_reconciliation']['sha256']='0'*64
  with self.assertRaises(ValueError):v4.validate(m,False)
  m=copy.deepcopy(self.manifest);m['extension_controller']['sha256']='0'*64
  with self.assertRaises(ValueError):v4.validate(m,False)
 def test_draft_stops_before_network(self):
  a=type('A',(),{'manifest':str(self.path),'sha256':v4.base.digest(self.path.read_bytes()),'review':'unused','env_file':None})()
  with patch.object(v4.base.paid,'fetch',side_effect=AssertionError('network touched')):
   with self.assertRaisesRegex(ValueError,'Manifest not frozen'):v4.execute(a)
if __name__=='__main__':unittest.main()
