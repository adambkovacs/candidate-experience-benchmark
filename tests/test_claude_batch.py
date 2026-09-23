import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from claude_benchmark import parse_result
from claude_batch_benchmark import validate_batch, batch_schema, isolation_ok, parse_batch_result
class BatchTests(unittest.TestCase):
 def test_exact_contract(self):
  row={'id':'DEV-001','sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
  self.assertTrue(validate_batch({'records':[row]},['DEV-001']))
  for body in [{'records':[row,row]},{'records':[]},{'records':[dict(row,id='OTHER')]},{'records':[dict(row,extra=1)]},{'records':[row],'extra':1}]:self.assertFalse(validate_batch(body,['DEV-001']))
 def test_builtin_guard(self):
  r={'init_plugins':[{'name':'agents-md','path':'builtin','source':'agents-md@builtin'}],'init_tools':['StructuredOutput'],'assistant_models':['claude-opus-5-5'],'requested_model':'claude-opus-5-5','init_model':'claude-opus-5-5','raw_events':[]}
  self.assertTrue(isolation_ok(r))
  self.assertFalse(isolation_ok(dict(r,init_plugins=[{'name':'unknown','path':'builtin','source':'unknown@builtin'}])))
  self.assertFalse(isolation_ok(dict(r,raw_events=[{'message':{'content':[{'type':'tool_use','name':'Read'}]}}])))
 def test_batch_shape_requires_explicit_validation(self):
  row={'id':'DEV-001','sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
  for body in [{'records':[row]},{'records':[dict(row,id='OTHER')]},{'records':[row,row]},{'records':[dict(row,sentiment='WRONG')]}]:
   parsed=parse_result({'type':'result','subtype':'success','structured_output':body},0)
   self.assertEqual(parsed['status'],'invalid_output')
  self.assertTrue(validate_batch({'records':[row]},['DEV-001']))
  flat={k:v for k,v in row.items() if k!='id'}
  self.assertEqual(parse_batch_result({'type':'result','subtype':'success','structured_output':flat},0,['DEV-001'])['status'],'invalid_output')
 def test_schema_bounds(self):
  schema=batch_schema(['A','B']);self.assertEqual(schema['properties']['records']['minItems'],2);self.assertEqual(schema['properties']['records']['items']['properties']['id']['enum'],['A','B'])
if __name__=='__main__':unittest.main()
