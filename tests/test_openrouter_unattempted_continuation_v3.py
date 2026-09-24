import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_unattempted_continuation_v3 as v3

class V3OfflineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.inventory=v3.read_inventory()
  cls.manifests={}
  for c in cls.inventory['candidate_conditions']:
   key=(c['configuration_id'],c['condition'])
   cls.manifests[key]=json.loads((v3.DEST/(key[0]+'-'+key[1].lower())/'draft-manifest.json').read_text())
 def test_exact_sealed_v2_suffixes(self):
  self.assertEqual(len(self.manifests),3)
  self.assertEqual(sum(len(x['remaining_ids']) for x in self.manifests.values()),74)
  for key,m in self.manifests.items():
   with self.subTest(key=key):
    v3.validate(m,False)
    self.assertEqual(len(m['histories']),2)
    self.assertEqual(m['remaining_ids'],v3.base.ids(61-len(m['remaining_ids'])))
    self.assertFalse(m['reference_labels_read'])
 def test_failed_v2_record_cannot_replay(self):
  m=copy.deepcopy(self.manifests[('qwen27-low-hosted-addendum-v1','P1')]);m['remaining_ids'].insert(0,'DEV-020')
  with self.assertRaises(ValueError):v3.validate(m,False)
 def test_v2_lineage_and_extension_source_are_bound(self):
  m=copy.deepcopy(self.manifests[('openrouter-paid-gemma4-26b-a4b-on','P2')]);m['lineage_v2_reconciliation']['sha256']='0'*64
  with self.assertRaises(ValueError):v3.validate(m,False)
  m=copy.deepcopy(self.manifests[('openrouter-paid-gemma4-26b-a4b-on','P2')]);m['extension_controller']['sha256']='0'*64
  with self.assertRaises(ValueError):v3.validate(m,False)
 def test_draft_cannot_execute_or_touch_network(self):
  p=v3.DEST/'qwen27-low-hosted-addendum-v1-p1/draft-manifest.json'
  a=type('A',(),{'manifest':str(p),'sha256':v3.base.digest(p.read_bytes()),'review':'unused','env_file':None})()
  with patch.object(v3.base.paid,'fetch',side_effect=AssertionError('network touched')):
   with self.assertRaisesRegex(ValueError,'Manifest not frozen'):v3.execute(a)
if __name__=='__main__':unittest.main()
