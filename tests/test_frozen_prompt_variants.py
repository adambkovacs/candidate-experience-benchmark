import hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import frozen_prompt_variants as v
from unittest import mock
REPO=Path(__file__).resolve().parents[1]
class VariantTests(unittest.TestCase):
 def bundle(self,d):
  root=Path(d);(root/'prompts').mkdir();shutil.copytree(REPO/'prompts/variants-v1',root/'prompts/variants-v1');(root/'docs').mkdir();shutil.copyfile(REPO/'docs/LABELING_GUIDE.md',root/'docs/LABELING_GUIDE.md');return root
 def test_p0_preserves_unicode_whitespace_and_roles(self):
  for role in ['system','user','cli_combined_prompt']:
   baseline=' \r\nRubric café\t\nJSON schema unchanged.\n'
   result=v.compose_instruction(baseline,'P0',role=role,parent_baseline_id='p0-config',root=REPO)
   self.assertEqual(result['instruction'].encode(),baseline.encode());self.assertEqual(result['role'],role);self.assertEqual(result['audit']['baseline_instruction_sha256'],result['audit']['composed_instruction_sha256']);self.assertIsNone(result['audit']['addition_sha256'])
 def test_additions_exact_and_p2_starts_p1_without_mutation(self):
  one=v.compose_instruction('BASE','P1',role='system',parent_baseline_id='id',root=REPO);two=v.compose_instruction('BASE','P2',role='system',parent_baseline_id='id',root=REPO)
  self.assertTrue(two['instruction'].startswith(one['instruction']));self.assertEqual(one['instruction'],'BASE\n\n'+(REPO/'prompts/variants-v1/P1-classifier.txt').read_text());self.assertEqual(two['audit']['parent_baseline_id'],'id');self.assertEqual(two['audit']['composition_separator'],'\n\n');self.assertEqual(two['audit']['composed_instruction_sha256'],hashlib.sha256(two['instruction'].encode()).hexdigest());self.assertFalse(two['audit']['inference_performed'])
 def test_file_tampering_rejected_even_for_p0(self):
  with tempfile.TemporaryDirectory() as d:
   root=self.bundle(d);p=root/'prompts/variants-v1/P1-classifier.txt';p.write_text(p.read_text()+'edited')
   for variant in ['P0','P1','P2']:
    with self.assertRaises(ValueError):v.compose_instruction('base',variant,role='system',parent_baseline_id='id',root=root)
 def test_manifest_and_source_tampering_rejected(self):
  for target in ['prompts/variants-v1/manifest.json','docs/LABELING_GUIDE.md']:
   with self.subTest(target=target),tempfile.TemporaryDirectory() as d:
    root=self.bundle(d);p=root/target;p.write_text('changed\n'+p.read_text())
    with self.assertRaises(ValueError):v.compose_instruction('base','P1',role='system',parent_baseline_id='id',root=root)
 def test_manifest_cannot_silently_repin_changed_candidate(self):
  with tempfile.TemporaryDirectory() as d:
   root=self.bundle(d);p=root/'prompts/variants-v1/P2-classifier-sop.txt';p.write_text('replacement');m=root/'prompts/variants-v1/manifest.json';data=json.loads(m.read_text());data['files'][p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':len(p.read_bytes())};m.write_text(json.dumps(data))
   with self.assertRaises(ValueError):v.compose_instruction('base','P2',role='system',parent_baseline_id='id',root=root)
 def test_reject_invalid_arguments(self):
  for changes in [{'variant':'other'},{'role':'assistant'},{'parent_baseline_id':''},{'baseline_instruction':b'bytes'},{'baseline_instruction':''}]:
   args=dict(baseline_instruction='base',variant='P0',role='system',parent_baseline_id='id',root=REPO);args.update(changes)
   with self.assertRaises(ValueError):v.compose_instruction(**args)
 def test_only_frozen_prompt_and_rubric_sources_read(self):
  with tempfile.TemporaryDirectory() as d:
   root=self.bundle(d)
   result=v.compose_instruction('base','P2',role='user',parent_baseline_id='id',root=root)
   self.assertEqual(result['audit']['source_policy_sha256'],'81e5f843de69c1c54ca4f17b70df51886405ad3a7606d5644ac24aeb29f839a5');self.assertFalse((root/'data').exists())
 def test_p2_nesting_guard_even_if_manifest_is_deliberately_reapproved(self):
  with tempfile.TemporaryDirectory() as d:
   root=self.bundle(d);p=root/'prompts/variants-v1/P2-classifier-sop.txt';p.write_text('No P1 prefix');m=root/'prompts/variants-v1/manifest.json';data=json.loads(m.read_text());data['files'][p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':len(p.read_bytes())};m.write_text(json.dumps(data))
   with mock.patch.object(v,'MANIFEST_SHA256',hashlib.sha256(m.read_bytes()).hexdigest()),self.assertRaisesRegex(ValueError,'verbatim P1'):
    v.compose_instruction('base','P2',role='system',parent_baseline_id='id',root=root)

if __name__=='__main__':unittest.main()
