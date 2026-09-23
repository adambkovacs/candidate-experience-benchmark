import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import codex_benchmark as c

class CodexTests(unittest.TestCase):
    def test_sol_terra_catalogue_efforts(self):
        for model in ('gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-6-sol', 'gpt-6-luna'):
            for effort in ('low','medium','high','xhigh'):
                c.validate_model_effort(model, effort)

    def test_unknown_model_or_effort_rejected(self):
        for model, effort in [('gpt-6-sol','max'),('gpt-6-sol','ultra'),('unknown','low'),('gpt-5.6-luna','ultra'),('gpt-5.6-sol','minimal')]:
            with self.assertRaises(ValueError): c.validate_model_effort(model, effort)

    def test_run_isolates_each_record_and_excludes_labels(self):
        prediction={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
        contexts=[]
        def fake_run(cmd, **kw):
            if cmd[1:]==['login','status']:
                return SimpleNamespace(returncode=0,stdout='',stderr='Logged in using ChatGPT')
            if cmd[1:]==['--version']:
                return SimpleNamespace(returncode=0,stdout='codex-cli fixture',stderr='')
            cwd=kw['cwd']; contexts.append(cwd)
            self.assertEqual(set(p.name for p in cwd.iterdir()), {'schema.json'})
            self.assertNotIn('proposed_labels',kw['input'])
            self.assertNotIn('scenario_family',kw['input'])
            (cwd/'response.json').write_text(json.dumps(prediction))
            return SimpleNamespace(returncode=0,stdout='{"type":"turn.completed"}',stderr='')
        with tempfile.TemporaryDirectory() as d, patch.object(c.subprocess,'run',side_effect=fake_run), patch.object(c.platform,'platform',return_value='test-host'):
            args=SimpleNamespace(codex='codex',model='gpt-5.6-sol',effort='low',limit=2,timeout=1,output=str(Path(d)/'out.jsonl'))
            c.run(args)
            self.assertEqual(len(set(contexts)),2)
            self.assertTrue(all(not p.exists() for p in contexts))
            self.assertEqual(len(Path(args.output).read_text().splitlines()),2)
            with self.assertRaises(FileExistsError): c.run(args)
    def test_timeout_preserves_partial_transport_evidence(self):
        def fake_run(cmd, **kwargs):
            if cmd[1:] == ['login', 'status']:
                return SimpleNamespace(returncode=0,stdout='Logged in using ChatGPT',stderr='')
            if cmd[1:] == ['--version']:
                return SimpleNamespace(returncode=0,stdout='fixture',stderr='')
            raise c.subprocess.TimeoutExpired(cmd, 1, output=b'partial event', stderr=b'transport detail')
        with tempfile.TemporaryDirectory() as temp, patch.object(c.subprocess, 'run', side_effect=fake_run), patch.object(c.platform, 'platform', return_value='test-host'):
            output = Path(temp)/'attempt.jsonl'
            args = SimpleNamespace(codex='codex',model='gpt-5.6-sol',effort='low',limit=1,timeout=1,output=str(output))
            with self.assertRaises(RuntimeError): c.run(args)
            row = json.loads(output.read_text())
            self.assertEqual(row['raw_stdout'], 'partial event')
            self.assertEqual(row['raw_stderr'], 'transport detail')
            self.assertEqual(row['status'], 'service_error')

    def test_completed_metadata_warning_preserved(self):
        warning={'type':'item.completed','item':{'type':'error','message':'Model metadata for `gpt-6-sol` not found. Defaulting to fallback metadata; this can degrade performance and cause issues.'}}
        raw=json.dumps({'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'})
        events=json.dumps(warning)+'\n'+json.dumps({'type':'turn.completed'})
        result=c.parse_result(0,events,raw)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(len(result['runtime_metadata_warnings']),1)
        self.assertEqual(c.parse_result(1,events,raw)['status'],'service_error')
        self.assertEqual(c.parse_result(0,json.dumps(warning),raw)['status'],'service_error')

    def test_environment_allowlist(self):
        env = c.clean_environment({'HOME':'/home/test', 'PATH':'/bin', 'OPENAI_API_KEY':'secret', 'CODEX_API_KEY':'secret', 'CODEX_THREAD_ID':'other', 'CODEX_HOME':'evil'})
        self.assertEqual(env, {'HOME':'/home/test', 'PATH':'/bin'})
    def test_request_contains_only_feedback_and_policy(self):
        prompt = c.make_prompt('rubric', {'feedback':'text', 'proposed_labels':'SECRET', 'id':'test'})
        self.assertNotIn('SECRET', prompt)
        self.assertNotIn('test', prompt)
    def test_restrictions(self):
        cmd = c.command('codex','gpt-5.6-luna','low',Path('/tmp/clean'),Path('/tmp/schema'))
        for part in ('--ignore-user-config','--ignore-rules','--ephemeral','read-only','forced_login_method="chatgpt"','project_doc_max_bytes=0','skills.include_instructions=false','features.shell_tool=false','features.memories=false'):
            self.assertIn(part, cmd)
    def test_runtime_paths_follow_record_directory(self):
        cmd=c.command('codex','m','low',Path('/private/tmp/record'),Path('/private/tmp/schema'))
        self.assertIn('sqlite_home="/private/tmp/record/db"',cmd)
        self.assertIn('log_dir="/private/tmp/record/logs"',cmd)
    def test_malformed_event_is_not_ignored(self):
        result=c.parse_result(0,'garbage\n{"type":"turn.completed"}','{}')
        self.assertEqual(result['status'],'service_error')
        self.assertEqual(result['event_parse_errors'],['garbage'])
    def test_tool_use_rejected(self):
        events = [{'type':'item.completed','item':{'type':'command_execution','command':'cat labels'}}]
        self.assertEqual(c.parse_result(0,json.dumps(events[0]),'{}')['status'], 'isolation_violation')
    def test_warning_is_not_tool_activity(self):
        events = json.dumps({'type':'item.completed','item':{'type':'error','message':'Under-development features enabled: skip_host_skill_discovery.'}}) + '\n' + '{"type":"turn.completed"}'
        self.assertEqual(c.parse_result(0, events, '{}')['status'], 'invalid_output')
    def test_recovered_transport_errors_keep_valid_completion(self):
        pred={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
        events=[{'type':'error','message':'Reconnecting... waiting for network'},
                {'type':'item.completed','item':{'type':'error','message':'Falling back from WebSockets to HTTPS transport. network error'}},
                {'type':'turn.completed','usage':{'input_tokens':10}}]
        result=c.parse_result(0,'\n'.join(map(json.dumps,events)),json.dumps(pred))
        self.assertEqual(result['status'],'ok')
        self.assertEqual(len(result['recovered_transport_errors']),2)
        self.assertEqual(c.parse_result(0,'\n'.join(map(json.dumps,events[:-1])),json.dumps(pred))['status'],'service_error')

    def test_failed_turn_rejected(self):
        r=c.parse_result(0,json.dumps({'type':'turn.failed'}),'{}')
        self.assertEqual(r['status'],'service_error')
    def test_schema_and_completion_required(self):
        pred={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
        self.assertEqual(c.parse_result(0,'',json.dumps(pred))['status'],'service_error')
        self.assertEqual(c.parse_result(0,'{"type":"turn.completed"}',json.dumps(pred))['status'],'ok')
        pred['extra']='bad'
        self.assertEqual(c.parse_result(0,'{"type":"turn.completed"}',json.dumps(pred))['status'],'invalid_output')

if __name__ == '__main__': unittest.main()
