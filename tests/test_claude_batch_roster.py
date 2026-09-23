import argparse,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import claude_batch_benchmark as b
import claude_benchmark as s
class BatchRosterTests(unittest.TestCase):
 def test_exact_roster_and_command_controls(self):
  self.assertEqual(sum(map(len,b.SUPPORTED_BATCH_EFFORTS.values())),17)
  for model,efforts in b.SUPPORTED_BATCH_EFFORTS.items():
   for effort in efforts:
    b.validate_batch_config(model,effort);cmd=s.command('claude',model,effort,'policy',{'type':'object'})
    self.assertEqual(cmd[cmd.index('--model')+1],model)
    if effort=='not_applicable':self.assertNotIn('--effort',cmd)
    else:self.assertEqual(cmd[cmd.index('--effort')+1],effort)
    for flag in ('--safe-mode','--strict-mcp-config','--no-session-persistence','--permission-mode'):self.assertIn(flag,cmd)
 def test_invalid_config_before_process(self):
  for model,effort in [('claude-haiku-4-5-20251001','low'),('claude-opus-5','not_applicable'),('claude-opus-5','max'),('claude-opus-5-5','ultra'),('unknown','low')]:
   with patch('subprocess.run',side_effect=AssertionError('process')):
    with self.assertRaises(ValueError):b.run(argparse.Namespace(model=model,effort=effort))
 def test_all_previews_offline_schema_order_exclusive(self):
  for model,efforts in b.SUPPORTED_BATCH_EFFORTS.items():
   for effort in efforts:
    with self.subTest(model=model,effort=effort),tempfile.TemporaryDirectory() as d:
     path=Path(d)/'preview.json';args=argparse.Namespace(model=model,effort=effort,prompt_variant='P0',parent_baseline_id='new-batch-p0',variant_preview_output=str(path),limit=60,offset=0)
     with patch('subprocess.run',side_effect=AssertionError('process')):
      b.run(args)
      with self.assertRaises(FileExistsError):b.run(args)
     data=json.loads(path.read_text());self.assertEqual(len(data['requests']),6)
     ids=[]
     for request in data['requests']:
      self.assertEqual(len(request['record_ids']),10);self.assertEqual(request['schema'],b.batch_schema(request['record_ids']));ids+=request['record_ids']
     self.assertEqual(ids,[f'DEV-{i:03}' for i in range(1,61)])
if __name__=='__main__':unittest.main()
