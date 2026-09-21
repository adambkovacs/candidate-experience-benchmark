import json
import sys
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import claude_benchmark as cb

class ClaudeAdapterTests(unittest.TestCase):
    def test_environment_excludes_api_routes_and_secrets(self):
        env = cb.clean_environment({'HOME':'/home/user','PATH':'/bin','ANTHROPIC_API_KEY':'secret','CLAUDE_CODE_OAUTH_TOKEN':'secret','OPENROUTER_API_KEY':'secret','CLAUDE_CODE_USE_BEDROCK':'1','ANTHROPIC_BASE_URL':'evil'})
        self.assertEqual(env['HOME'], '/home/user')
        self.assertFalse(any('secret' in v for v in env.values()))
        self.assertNotIn('ANTHROPIC_BASE_URL',env)
        self.assertNotIn('CLAUDE_CODE_USE_BEDROCK',env)
    def test_subscription_guard(self):
        for auth in ({}, {'loggedIn':True,'authMethod':'api_key'}, {'loggedIn':True,'authMethod':'claude.ai','apiProvider':'bedrock'}):
            with self.assertRaises(ValueError): cb.require_subscription(auth)
        cb.require_subscription({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'})
    def test_command_isolation_and_no_bare_mode(self):
        cmd = cb.command('claude','claude-sonnet-4-6','low','rubric',{'type':'object'})
        self.assertNotIn('--bare',cmd)
        for flag in ('--safe-mode','--strict-mcp-config','--no-session-persistence','--disable-slash-commands'):
            self.assertIn(flag,cmd)
        self.assertEqual(cmd[cmd.index('--tools')+1], '')
        self.assertEqual(cmd[cmd.index('--setting-sources')+1], '')
        self.assertEqual(cmd[cmd.index('--system-prompt')+1], 'rubric')
    def test_structured_output_only(self):
        good = {'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
        self.assertEqual(cb.parse_result({'structured_output':good,'subtype':'success'},0)['status'],'ok')
        self.assertEqual(cb.parse_result({'result':json.dumps(good),'subtype':'success'},0)['status'],'invalid_output')
        self.assertEqual(cb.parse_result({'structured_output':good,'is_error':True},1)['status'],'service_error')
    def test_record_input_excludes_labels_and_id(self):
        row={'id':'DEV-001','feedback':'example','proposed_labels':{'secret':'label'}}
        self.assertEqual(json.loads(cb.feedback_input(row)),{'feedback':'example'})
    def test_metrics_do_not_claim_billed_cost(self):
        parsed=cb.parse_result({'structured_output':{},'total_cost_usd':0.1,'duration_api_ms':200,'duration_ms':500,'modelUsage':{'claude-sonnet-4-6':{}}},0)
        self.assertEqual(parsed['cli_estimated_api_equivalent_usd'],0.1)
        self.assertIsNone(parsed['actual_billed_usd'])
        self.assertEqual(parsed['returned_models'],['claude-sonnet-4-6'])

    def test_schema_annotation_adaptation_preserves_constraints(self):
        schema={'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['sentiment']}
        cmd=cb.command('claude','claude-sonnet-5','low','rubric',schema)
        sent=json.loads(cmd[cmd.index('--json-schema')+1])
        self.assertEqual(sent,{'type':'object','required':['sentiment']})
        self.assertIn('$schema',schema)

    def test_verbose_event_array_records_wrapper_and_billing(self):
        result=cb.parse_result([
            {'type':'system','subtype':'init','tools':['StructuredOutput'],'model':'claude-sonnet-5','mcp_servers':[]},
            {'type':'assistant','message':{'model':'claude-sonnet-5'}},
            {'type':'rate_limit_event','rate_limit_info':{'isUsingOverage':True}},
            {'type':'result','subtype':'success','structured_output':{}}],0)
        self.assertEqual(result['assistant_models'],['claude-sonnet-5'])
        self.assertTrue(result['overage_observed'])
        self.assertEqual(result['init_tools'],['StructuredOutput'])

    def test_run_fresh_empty_workspaces_and_exclusive_output(self):
        good={'sentiment':'positive','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'yes'}
        inference_cwds=[]
        def fake(cmd,**kwargs):
            if 'status' in cmd:
                payload=json.dumps({'loggedIn':True,'authMethod':'claude.ai','apiProvider':'firstParty'})
            elif '--version' in cmd: payload='2.1.274'
            elif '--help' in cmd: payload='--safe-mode --tools --setting-sources --json-schema --no-session-persistence'
            else:
                inference_cwds.append(kwargs['cwd'])
                self.assertEqual(list(Path(kwargs['cwd']).iterdir()),[])
                self.assertEqual(set(json.loads(kwargs['input'])),{'feedback'})
                self.assertNotIn('proposed_labels',str(cmd))
                payload=json.dumps({'type':'result','subtype':'success','structured_output':good})
            return SimpleNamespace(stdout=payload,stderr='',returncode=0)
        with tempfile.TemporaryDirectory() as d:
            args=SimpleNamespace(extra_usage_disabled=True,model='claude-sonnet-5',effort='low',limit=3,output=str(Path(d)/'out.jsonl'),config_note='mock',timeout=30)
            with patch.object(cb.platform,'platform',return_value='test-host'),patch.object(cb.shutil,'which',return_value='/bin/claude'),patch.object(cb.subprocess,'run',side_effect=fake):
                cb.run(args)
                self.assertEqual(len(set(inference_cwds)),3)
                self.assertEqual(len(Path(args.output).read_text().splitlines()),3)
                with self.assertRaises(FileExistsError): cb.run(args)
                args.offset=30
                args.limit=1
                args.output=str(Path(d)/'continuation.jsonl')
                cb.run(args)
                self.assertEqual(json.loads(Path(args.output).read_text())['id'],'DEV-031')

    def test_failure_text_preserved_and_credentials_redacted(self):
        parsed=cb.parse_result({'type':'result','subtype':'error_max_turns','result':'Malformed answer','errors':['Bearer secret sk-secret123'],'is_error':True},1)
        self.assertEqual(parsed['raw_response']['result'],'Malformed answer')
        self.assertNotIn('secret',str(parsed['raw_response']['errors']))
        with self.assertRaises(ValueError): cb.parse_result([],0)

    def test_haiku_omits_unsupported_effort(self):
        cmd=cb.command('claude','claude-haiku-4-5-20251001','not_applicable','rubric',{})
        self.assertNotIn('--effort',cmd)

    def test_supported_effort_validation_prevents_silent_haiku_clamping(self):
        with self.assertRaises(ValueError): cb.validate_effort('claude-haiku-4-5-20251001','high')
        with self.assertRaises(ValueError): cb.validate_effort('claude-opus-5','not_applicable')
        cb.validate_effort('claude-haiku-4-5-20251001','not_applicable')
        for model in ('claude-sonnet-5','claude-opus-5','claude-fable-5-1'):
            for effort in ('low','medium','high','xhigh','max'): cb.validate_effort(model,effort)

if __name__ == '__main__': unittest.main()
