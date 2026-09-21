import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gemini_benchmark as g

class GeminiTests(unittest.TestCase):
    def test_credentials_excluded(self):
        self.assertEqual(g.clean_environment({'HOME':'/h','PATH':'/bin','GEMINI_API_KEY':'secret','GOOGLE_APPLICATION_CREDENTIALS':'secret','AGY_GATEWAY_API_KEY':'secret'}),{'HOME':'/h','PATH':'/bin'})
    def test_valid_stream(self):
        p={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
        events=[{'event':'init','init':{'model':'gemini-3.5-flash-medium','tools':[]}}, {'event':'result','result':{'status':'SUCCESS','structured_output':p}}]
        self.assertEqual(g.parse_stream('\n'.join(map(json.dumps,events)),0,'gemini-3.5-flash-medium')['status'],'ok')
    def test_model_mismatch_fails(self):
        raw='{"event":"init","init":{"model":"other","tools":[]}}\n{"event":"result","result":{"status":"SUCCESS"}}'
        self.assertEqual(g.parse_stream(raw,0,'requested')['status'],'model_mismatch')
    def test_tools_available_fails(self):
        raw='{"event":"init","init":{"model":"m","tools":["view_file"]}}'
        self.assertEqual(g.parse_stream(raw,0,'m')['status'],'isolation_violation')
    def test_tool_use_fails(self):
        raw='{"event":"step_update","step_update":{"step_type":"tool","tool_name":"view_file"}}'
        self.assertEqual(g.parse_stream(raw,0,'m')['status'],'isolation_violation')
    def test_missing_init_fails_closed(self):
        self.assertEqual(g.parse_stream('',0,'m')['status'],'service_error')
    def test_run_blocked_before_subprocess(self):
        with self.assertRaisesRegex(RuntimeError,'isolation'):
            g.run(None)

if __name__=='__main__': unittest.main()
