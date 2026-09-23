import json,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gemini_batch_benchmark as g
class NativeGeminiTests(unittest.TestCase):
 def stream(self,**overrides):
  init={'model':'gemini-3.8-flash-low','agent':'recruitment-benchmark','tools':[],'mcpServers':[],'skills':[],'plugins':[],'memory_enabled':False};init.update(overrides)
  prediction={'id':'DEV-001','sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
  return '\n'.join(json.dumps(e) for e in [{'event':'init','init':init},{'event':'result','result':{'status':'SUCCESS','structured_output':{'records':[prediction]}}}])
 def test_valid_native_stream(self):
  self.assertEqual(g.inspect_stream(self.stream(),0,'gemini-3.8-flash-low',[{'id':'DEV-001'}])['status'],'ok')
 def test_model_tools_agent_and_malformed_fail_closed(self):
  for override in [{'model':'other'},{'tools':['view_file']},{'agent':'default'},{'tools':None}]:
   self.assertNotEqual(g.inspect_stream(self.stream(**override),0,'gemini-3.8-flash-low',[{'id':'DEV-001'}])['status'],'ok')
  self.assertEqual(g.inspect_stream(self.stream()+'\nBAD',0,'gemini-3.8-flash-low',[{'id':'DEV-001'}])['status'],'service_error')
 def test_contradictory_runtime_context_controls_rejected(self):
  self.assertEqual(g.inspect_stream(self.stream(skills=None),0,'gemini-3.8-flash-low',[{'id':'DEV-001'}])['status'],'isolation_violation')
 def test_tool_event_rejected_and_retained(self):
  raw=self.stream()+'\n'+json.dumps({'event':'step_update','step_update':{'step_type':'tool','tool_name':'view_file'}})
  result=g.inspect_stream(raw,0,'gemini-3.8-flash-low',[{'id':'DEV-001'}]);self.assertEqual(result['status'],'isolation_violation');self.assertEqual(len(result['observed_tool_items']),1)
 def test_credits_must_be_explicit_false(self):
  with tempfile.TemporaryDirectory() as d:
   h=Path(d);p=h/'.gemini/antigravity-cli/settings.json';p.parent.mkdir(parents=True)
   for data in [{},{'useG1Credits':True},{'useG1Credits':False,'modelProvider':'vertex'}]:
    p.write_text(json.dumps(data))
    with self.assertRaises(RuntimeError):g.require_credits_off(h)
   p.write_text('{"useG1Credits":false}');self.assertFalse(g.require_credits_off(h)['useG1Credits'])
 def test_global_context_content_blocks(self):
  with tempfile.TemporaryDirectory() as d:
   h=Path(d);p=h/'.gemini/GEMINI.md';p.parent.mkdir();p.write_text('unrelated memory')
   with self.assertRaises(RuntimeError):g.context_audit(h)

class NativeGuardTests(unittest.TestCase):
 def test_control_warnings(self):
  for text in ['WARNING: skills ignored','unsupported flag --agent','unknown agent','invalid schema','fallback enabled']:
   self.assertTrue(g.control_warning(text))
  self.assertFalse(g.control_warning('Fetching available models...'))
 def test_sparse_credit_persistence_reasserted(self):
  with tempfile.TemporaryDirectory() as d:
   h=Path(d);p=h/'.gemini/antigravity-cli/settings.json';p.parent.mkdir(parents=True);p.write_text('{}')
   self.assertFalse(g.establish_credits_off(h)['useG1Credits']);self.assertIs(json.loads(p.read_text())['useG1Credits'],False)
 def test_invalid_configuration_before_process(self):
  import argparse
  from unittest.mock import patch
  for timeout,model,effort in [(0,'gemini-3.8-flash-low','low'),(600,'gemini-3.8-flash-low','high')]:
   with patch.object(g.subprocess,'run',side_effect=AssertionError('process attempted')):
    with self.assertRaises(ValueError):g.run(argparse.Namespace(timeout=timeout,model=model,effort=effort))

class DocumentedAgentControlsTests(unittest.TestCase):
 def test_no_ambient_or_default_components(self):
  for field in ['excludeDefaultComponents: true','inheritCustomizations: false','inheritMcp: false','tools: []','mcpServers: []','skills: []','plugins: []','commandExecutionPolicy: "off"','# System Prompt']:
   self.assertIn(field,g.AGENT)

class FinishOutputTests(NativeGeminiTests):
 def test_finish_only_schema_and_payload_match(self):
  rows=[{'id':'DEV-001'}];events=[json.loads(x) for x in self.stream(tools=['finish'],json_schema=g.batch_schema(rows)).splitlines()]
  payload=events[-1]['result']['structured_output']
  events.insert(1,{'event':'step_update','step_update':{'step_type':'tool','tool_name':'finish','tool_info':{'parameters':payload}}})
  raw='\n'.join(map(json.dumps,events));self.assertEqual(g.inspect_stream(raw,0,'gemini-3.8-flash-low',rows)['status'],'ok')
  events[1]['step_update']['tool_info']['parameters']={'records':[]}
  self.assertNotEqual(g.inspect_stream('\n'.join(map(json.dumps,events)),0,'gemini-3.8-flash-low',rows)['status'],'ok')
 def test_finish_with_external_tools_rejected(self):
  self.assertEqual(g.inspect_stream(self.stream(tools=['finish','view_file']),0,'gemini-3.8-flash-low',[{'id':'DEV-001'}])['status'],'isolation_violation')

class ObservedWorkflowTests(NativeGeminiTests):
 def test_inventory_disclosed_only_explicit_mode(self):
  raw=self.stream(tools=['finish','view_file','run_command'])
  self.assertEqual(g.inspect_stream(raw,0,'gemini-3.8-flash-low',[{'id':'DEV-001'}])['status'],'isolation_violation')
  result=g.inspect_stream(raw,0,'gemini-3.8-flash-low',[{'id':'DEV-001'}],'native-agent-observed-no-external-tools')
  self.assertEqual(result['status'],'ok');self.assertEqual(result['available_tools'],['finish','view_file','run_command'])
 def test_observed_external_action_still_rejected(self):
  for update in [{'step_type':'tool','tool_name':'view_file'},{'step_type':'message','subagent_info':{'id':'other'}}]:
   raw=self.stream(tools=['view_file'])+'\n'+json.dumps({'event':'step_update','step_update':update})
   self.assertEqual(g.inspect_stream(raw,0,'gemini-3.8-flash-low',[{'id':'DEV-001'}],'native-agent-observed-no-external-tools')['status'],'isolation_violation')
 def test_unknown_mode_rejected(self):
  with self.assertRaises(ValueError):g.inspect_stream('',0,'model',[],'relaxed')
