import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import specialist_benchmark as s
class SemifPreviewTests(unittest.TestCase):
 def args(self,root,**kw):
  a=dict(kind='semif',mode='generated',prompt_variant='P1',parent_baseline_id='semif-generated-bf16',variant_preview_output=str(root/'preview.json'),output=str(root/'inference.jsonl'),model_path='/nonexistent',revision='configured-only',bits=None,max_tokens=4096,limit=60)
  a.update(kw);return SimpleNamespace(**a)
 def test_default_and_explicit_p0_equal_legacy_messages(self):
  policy=(s.ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
  for row in s.read_rows(s.ROOT/'data/pilot/inputs.jsonl'):
   p=s.make_payload(row['feedback'],policy,'not-sent','generated-off');expected=p['messages'];expected[0]['content']+='\nRequired JSON schema: '+json.dumps(p['response_format']['json_schema']['schema'])
   self.assertEqual(s.generated_messages(row['feedback'],policy),expected)
   self.assertEqual(s.generated_messages(row['feedback'],policy,'P0','semif-generated-bf16'),expected)
 def test_preview_never_builds_runtime_and_preserves_order_schema_roles(self):
  with tempfile.TemporaryDirectory() as d:
   args=self.args(Path(d))
   with mock.patch.object(s,'build_runner',side_effect=AssertionError('model loading forbidden')):s.run(args)
   data=json.loads(Path(args.variant_preview_output).read_text());self.assertFalse(Path(args.output).exists());self.assertEqual([r['id'] for r in data['requests']],[f'DEV-{i:03}' for i in range(1,61)])
   inputs=s.read_rows(s.ROOT/'data/pilot/inputs.jsonl')
   for req,row in zip(data['requests'],inputs):
    self.assertEqual([m['role'] for m in req['messages']],['system','user']);self.assertEqual(json.loads(req['messages'][1]['content']),{'feedback':row['feedback']});self.assertIn('Required JSON schema:',req['messages'][0]['content'])
   self.assertIn('Source reconstruction only',data['historical_parity']);self.assertEqual(data['controls']['max_new_tokens'],2048)
   with self.assertRaises(FileExistsError):s.run(args)
 def test_live_variants_and_wrong_specialists_fail_before_runtime(self):
  with tempfile.TemporaryDirectory() as d:
   for kind,mode in [('semif','direct'),('semif','serial'),('semif','shared'),('laya','default'),('alex','nli')]:
    with mock.patch.object(s,'build_runner',side_effect=AssertionError('runtime forbidden')):
     with self.assertRaises(ValueError):s.run(self.args(Path(d),kind=kind,mode=mode))
   for variant in ['P0','P1','P2']:
    with mock.patch.object(s,'build_runner',side_effect=AssertionError('runtime forbidden')):
     with self.assertRaisesRegex(ValueError,'gates'):s.run(self.args(Path(d),prompt_variant=variant,variant_preview_output=None))
    self.assertFalse((Path(d)/'inference.jsonl').exists())
    self.assertFalse((Path(d)/'preview.json').exists())
 def test_default_does_not_require_variant_bundle(self):
  a=SimpleNamespace(kind='semif',mode='generated')
  with mock.patch.object(s,'read_rows',side_effect=AssertionError('unexpected input read')):self.assertFalse(s.variant_gate_or_preview(a))
