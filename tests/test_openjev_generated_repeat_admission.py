import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(os.environ.get('RECRUITMENT_REPO_ROOT', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(REPO / 'scripts'))
TARGET = Path(os.environ.get('OPENJEV_GENERATED_CONTROLLER', REPO / 'scripts/openjev_generated_repeat_admission.py'))
spec = importlib.util.spec_from_file_location('openjev_generated_repeat_admission', TARGET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeProcess:
    pid = 12345
    def poll(self): return None
    def terminate(self): pass
    def wait(self, timeout=None): return 0


class GeneratedAdmissionTests(unittest.TestCase):
    def test_rotated_schedule_and_reference_free_requests(self):
        self.assertEqual(mod.ROTATION, (('P0','P1','P2'),('P1','P2','P0'),('P2','P0','P1')))
        data, policy = mod.source_rows()
        self.assertEqual(len(data), 60)
        self.assertTrue(all(set(row) == {'id','feedback'} for row in data))
        for mode in mod.MODES:
            for condition in mod.CONDITIONS:
                payload, audit = mod.generated_variant_payload(data[0]['feedback'],policy,'diffusiongemma-26b',mode,condition,'openjev-'+mode)
                self.assertEqual(payload['chat_template_kwargs']['enable_thinking'],mode=='generated-on')
                self.assertEqual(payload['max_tokens'],2048)
                self.assertEqual(payload['messages'][0]['role'],'system')
                self.assertNotIn('proposed_labels',json.dumps(payload))

    def test_frozen_plan_has_eighteen_ordered_phases(self):
        plan_path = REPO / 'results/repeatability-v1/openjev-generated-fresh-v1/manifest.json'
        if not plan_path.exists(): self.skipTest('Frozen plan has not been copied into this checkout')
        plan = json.loads(plan_path.read_text())
        expected = [f'{mode}/fresh{index}/{condition}' for mode in mod.MODES
                    for index, order in enumerate(mod.ROTATION, 1) for condition in order]
        self.assertEqual(plan['schedule'], expected)
        self.assertEqual(plan['source_sha256'][str(TARGET)], mod.sha(TARGET))
        self.assertFalse(plan['reference_labels_used_for_requests'])
        self.assertEqual(plan['runtime']['requested_on_effective_reasoning'], 'unknown; requested setting only')
        self.assertEqual(plan['runtime']['configured_upstream_model_default'], 'dgemma')
        self.assertEqual(plan['runtime']['logical_response_model'], 'diffusiongemma-26b')
        self.assertIn('not measured', plan['runtime']['server_env_scope'])
        self.assertIn('not exposed', plan['runtime']['rendered_token_hash_scope'])
        self.assertNotIn('OPENJEV_UPSTREAM_MODEL', plan['runtime']['server_env'])
        self.assertIn('offline_rendered_token_ids_sha256', plan['requests']['generated-off']['P0'][0])
        self.assertNotIn('rendered_token_ids_sha256', plan['requests']['generated-off']['P0'][0])
        self.assertEqual(len(plan['requests']['generated-on']['P2']), 60)

    def test_transport_preserves_malformed_http_body(self):
        body=b'{malformed-json'
        class Response:
            status=200
            def read(self,n): return body
            def getheaders(self): return [('Content-Type','application/json'),('X-Request-ID','abc'),('Authorization','hidden')]
        class Connection:
            def __init__(self,*a,**k): pass
            def request(self,*a,**k): pass
            def getresponse(self): return Response()
            def close(self): pass
        with patch.object(mod.http.client,'HTTPConnection',Connection): result=mod.transport({'x':1})
        self.assertEqual(base64.b64decode(result['body_base64']),body)
        self.assertEqual(result['headers'],{'content-type':'application/json','x-request-id':'abc'})

    def test_receipt_requires_exact_stage_bindings(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'receipt.json'
            plan={'artifact_manifest_sha256':'asset','historical_preflight_sha256':'preflight','runtime':{'cache_policy':'fresh'}}
            receipt={'kind':'root-reviewed-openjev-generated-stage-v1','approved':True,'phase':'generated-off/fresh1/P0',
                     'stage':'smoke','plan_sha256':'plan','controller_sha256':mod.sha(TARGET),
                     'predecessor_sha256':None,'reference_labels_read':False,'source_commit':mod.native.SOURCE_COMMIT,
                     'artifact_manifest_sha256':'asset','historical_preflight_sha256':'preflight','server_policy':'fresh'}
            p.write_text(json.dumps(receipt))
            self.assertEqual(mod.check_receipt(p,plan,'plan',receipt['phase'],'smoke',None),mod.sha(p))
            receipt['server_policy']='changed';p.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError):mod.check_receipt(p,plan,'plan',receipt['phase'],'smoke',None)

    def test_stage_raw_before_projection_and_no_replay(self):
        phase='generated-off/fresh1/P0'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'phase';folder.mkdir();lock=root/'lock';lock.touch()
            item={'id':'DEV-001','payload':{'model':'diffusiongemma-26b'},'request_sha256':'request',
                  'offline_rendered_token_ids_sha256':'render','input_tokens':5,
                  'wire_body_sha256':mod.hashlib.sha256(json.dumps({'model':'diffusiongemma-26b'}).encode()).hexdigest()}
            plan={'schedule':[phase],'requests':{'generated-off':{'P0':[item]}},
                  'artifact_manifest_sha256':'asset','historical_preflight_sha256':'preflight',
                  'runtime':{'cache_policy':'fresh'}}
            fake={'http_status':200,'headers':{},'body_base64':base64.b64encode(b'{bad').decode(),
                  'truncated':False,'incomplete':False}
            with patch.object(mod,'phase_folder',return_value=folder),patch.object(mod.native,'HOST_LOCK',lock),\
                 patch.object(mod,'predecessor',return_value=None),patch.object(mod,'check_receipt',return_value='receipt'),\
                 patch.object(mod.native,'start_server',return_value=FakeProcess()),patch.object(mod,'transport',return_value=fake):
                with self.assertRaises(ValueError):mod.execute(plan,'plan',phase,'smoke',root/'receipt')
                self.assertEqual(len(mod.rows(folder/'smoke.raw.jsonl')),1)
                self.assertEqual(base64.b64decode(mod.rows(folder/'smoke.raw.jsonl')[0]['body_base64']),b'{bad')
                self.assertEqual(mod.rows(folder/'smoke.raw.jsonl')[0]['offline_rendered_token_ids_sha256'],'render')
                self.assertNotIn('rendered_token_ids_sha256',mod.rows(folder/'smoke.raw.jsonl')[0])
                attested=mod.native.read_json(folder/'smoke.server-attestation.json')
                self.assertEqual(attested['kind'],'openjev-generated-server-launch-observation-v1')
                self.assertEqual(attested['configured_upstream_model_default'],'dgemma')
                self.assertEqual(attested['logical_response_model'],'diffusiongemma-26b')
                self.assertIs(attested['loaded_settings_measured'],False)
                self.assertIs(attested['live_rendered_token_ids_measured'],False)
                self.assertEqual(mod.rows(folder/'smoke.journal.jsonl')[-1]['event'],'stopped_unknown')
                self.assertEqual(mod.rows(folder/'smoke.records.jsonl'),[])
                self.assertEqual(mod.native.read_json(folder/'smoke.completion.json')['status'],'stopped')
                with self.assertRaises(ValueError):mod.execute(plan,'plan',phase,'smoke',root/'receipt')

    def test_common_gpu_lock_is_reused(self):
        self.assertEqual(mod.native.HOST_LOCK.name, 'execution.lock')
        self.assertIn('laya-expanded-cpu-v1', str(mod.native.HOST_LOCK))

    def test_captured_length_is_invalid_and_continues_but_incomplete_stops(self):
        phase='generated-off/fresh1/P0'
        payload={'model':'diffusiongemma-26b'}
        items=[{'id':f'DEV-{i:03d}','payload':payload,'request_sha256':f'request-{i}',
                'offline_rendered_token_ids_sha256':f'render-{i}','input_tokens':5,
                'wire_body_sha256':mod.hashlib.sha256(json.dumps(payload).encode()).hexdigest()}
               for i in (1,2)]
        plan={'schedule':[phase],'requests':{'generated-off':{'P0':items}},
              'artifact_manifest_sha256':'asset','runtime':{'cache_policy':'fresh'}}

        def captured(finish, *, incomplete=False):
            body={'model':'diffusiongemma-26b',
                  'usage':{'prompt_tokens':5,'completion_tokens':3},
                  'choices':[{'finish_reason':finish,'message':{'content':'{}'}}]}
            return {'http_status':200,'headers':{},
                    'body_base64':base64.b64encode(json.dumps(body).encode()).decode(),
                    'truncated':False,'incomplete':incomplete}

        for first_incomplete in (False,True):
            with self.subTest(first_incomplete=first_incomplete), tempfile.TemporaryDirectory() as d:
                root=Path(d);folder=root/'phase';folder.mkdir();lock=root/'lock';lock.touch()
                responses=[captured('length',incomplete=first_incomplete),captured('stop')]
                with patch.object(mod,'phase_folder',return_value=folder),patch.object(mod.native,'HOST_LOCK',lock),\
                     patch.object(mod,'predecessor',return_value=None),patch.object(mod,'check_receipt',return_value='receipt'),\
                     patch.object(mod.native,'start_server',return_value=FakeProcess()),\
                     patch.object(mod,'transport',side_effect=responses) as transport:
                    if first_incomplete:
                        with self.assertRaises(ValueError):mod.execute(plan,'plan',phase,'smoke',root/'receipt')
                    else:
                        mod.execute(plan,'plan',phase,'smoke',root/'receipt')
                records=mod.rows(folder/'smoke.records.jsonl')
                completion=mod.native.read_json(folder/'smoke.completion.json')
                if first_incomplete:
                    self.assertEqual(transport.call_count,1)
                    self.assertEqual(records,[])
                    self.assertEqual(completion['status'],'stopped')
                    self.assertEqual(mod.rows(folder/'smoke.journal.jsonl')[-1]['event'],'stopped_unknown')
                else:
                    self.assertEqual(transport.call_count,2)
                    self.assertEqual([r['decision']['finish_reason'] for r in records],['length','stop'])
                    self.assertEqual(records[0]['decision']['status'],'invalid_output')
                    self.assertEqual(completion['status'],'completed')

    def test_inspected_three_successes_required_for_development(self):
        phase='generated-off/fresh1/P0'
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            raw=folder/'smoke.raw.jsonl';records=folder/'smoke.records.jsonl';journal=folder/'smoke.journal.jsonl'
            raw.write_text(''.join(json.dumps({'id':f'DEV-{i:03d}','http_status':200,'incomplete':False,'truncated':False,'body_base64':base64.b64encode(b'{}').decode(),'input_tokens':5})+'\n' for i in range(1,4)))
            records.write_text(''.join(json.dumps({'id':f'DEV-{i:03d}','decision':{'status':'ok','prediction':None}})+'\n' for i in range(1,4)))
            journal.write_text('{}\n')
            end={'status':'completed','count':3,'plan_sha256':'plan','raw_sha256':mod.sha(raw),
                 'records_sha256':mod.sha(records),'journal_sha256':mod.sha(journal)}
            (folder/'smoke.completion.json').write_text(json.dumps(end))
            inspection={'kind':'openjev-generated-smoke-inspection-v1','approved':True,'phase':phase,
                        'plan_sha256':'plan','raw_sha256':end['raw_sha256'],
                        'records_sha256':end['records_sha256'],'reference_labels_read':False,
                        'records':[{'id':f'DEV-{i:03d}','status':'ok','prediction':None} for i in range(1,4)]}
            (folder/'smoke-inspection.json').write_text(json.dumps(inspection))
            with patch.object(mod,'phase_folder',return_value=folder),patch.object(mod,'parse_native_response',return_value={'status':'ok','prediction':None}):
                self.assertEqual(mod.predecessor({'schedule':[phase]},'plan',phase,'development'),mod.sha(folder/'smoke-inspection.json'))
            saved=mod.rows(records);saved[0]['decision']['status']='invalid_output'
            records.write_text(''.join(json.dumps(x)+'\n' for x in saved))
            end['records_sha256']=mod.sha(records);(folder/'smoke.completion.json').write_text(json.dumps(end))
            inspection['records_sha256']=end['records_sha256']
            inspection['records'][0].update(status='invalid_output',accepted_unchanged=True,inspection_reason='Intrinsic malformed JSON preserved')
            (folder/'smoke-inspection.json').write_text(json.dumps(inspection))
            decisions=[{'status':'invalid_output','prediction':None}]+[{'status':'ok','prediction':None}]*2
            with patch.object(mod,'phase_folder',return_value=folder),patch.object(mod,'parse_native_response',side_effect=decisions):
                self.assertEqual(mod.predecessor({'schedule':[phase]},'plan',phase,'development'),mod.sha(folder/'smoke-inspection.json'))
            del inspection['records'][0]['accepted_unchanged']
            (folder/'smoke-inspection.json').write_text(json.dumps(inspection))
            with patch.object(mod,'phase_folder',return_value=folder),patch.object(mod,'parse_native_response',side_effect=decisions):
                with self.assertRaises(ValueError):mod.predecessor({'schedule':[phase]},'plan',phase,'development')

if __name__ == '__main__': unittest.main()
