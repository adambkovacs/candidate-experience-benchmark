import copy
import sys
from pathlib import Path
import unittest
from unittest import mock
import tempfile
from types import SimpleNamespace
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openrouter_benchmark as runner

class FreeOnlyTests(unittest.TestCase):
    def test_prices_fail_closed(self):
        for price in ({}, {'prompt':'0'}, {'prompt':'0','completion':'1'},
                      {'prompt':'0','completion':'NaN'}, {'prompt':'0','completion':'0','request':'0.1'}):
            self.assertFalse(runner.zero_price(price))
        self.assertTrue(runner.zero_price({'prompt':'0','completion':'0','discount':0}))

    def test_endpoint_and_model_validation(self):
        catalog={'data':[{'id':'qwen/test:free','pricing':{'prompt':'0','completion':'0'}}]}
        endpoint={'tag':'provider/fp4','pricing':{'prompt':'0','completion':'0'},'supported_parameters':['structured_outputs']}
        endpoints={'data':{'endpoints':[endpoint]}}
        self.assertEqual(runner.select_endpoint('qwen/test:free','provider/fp4',catalog,endpoints),endpoint)
        for model,provider in [('qwen/test','provider/fp4'),('qwen/test:free','other')]:
            with self.assertRaises(ValueError): runner.select_endpoint(model,provider,catalog,endpoints)
        changed=copy.deepcopy(endpoints)
        changed['data']['endpoints'][0]['pricing']['completion']='0.01'
        with self.assertRaises(ValueError): runner.select_endpoint('qwen/test:free','provider/fp4',catalog,changed)

    def test_payload_isolated_and_zero_cap(self):
        one=runner.make_payload('qwen/test:free','provider/fp4','one','rubric',{})
        two=runner.make_payload('qwen/test:free','provider/fp4','two','rubric',{})
        self.assertNotIn('one',str(two['messages']))
        self.assertEqual(one['provider']['max_price'],{'prompt':0,'completion':0,'request':0,'image':0})
        self.assertFalse(one['provider']['allow_fallbacks'])
        self.assertEqual(one['provider']['only'],['provider/fp4'])
        self.assertEqual(len(one['messages']),2)
        self.assertNotIn('proposed_labels',str(one))
        self.assertNotIn('models',one)

    def test_run_stops_after_service_error_and_never_reads_labels(self):
        endpoint={'tag':'provider/fp4','provider_name':'Provider','pricing':{'prompt':'0','completion':'0'},'supported_parameters':['structured_outputs','reasoning']}
        responses=[{'data':[{'id':'qwen/test:free','pricing':{'prompt':'0','completion':'0'},'reasoning':{'mandatory':False,'supported_efforts':['low','medium','xhigh']}}]},
                   {'data':{'endpoints':[endpoint]}}, RuntimeError('private error')]
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(output=str(Path(tmp)/'run.jsonl'),env_file=None,timeout=2,
                                 model='qwen/test:free',provider='provider/fp4',limit=3,reasoning='off',max_tokens=8192)
            with mock.patch.object(runner,'fetch',side_effect=responses) as fetch, mock.patch.object(runner,'load_key',return_value='SECRET'):
                runner.run(args)
            rows=[json.loads(x) for x in Path(args.output).read_text().splitlines()]
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['status'],'service_error')
            self.assertNotIn('private error',str(rows))
            self.assertNotIn('SECRET',str(rows))
            payload=fetch.call_args_list[-1].args[2]
            self.assertEqual(set(json.loads(payload['messages'][1]['content'])),{'feedback'})
            self.assertNotIn('proposed_labels',str(payload))

    def test_returned_model_allowlist_uses_exact_endpoint_names(self):
        names=runner.allowed_returned_models('qwen/qwen3.8-27b:free',
            {'model_id':'qwen/qwen3.8-27b:free','name':'ModelRun | qwen/qwen3.8-27b-20260814:free'})
        self.assertEqual(names,{'qwen/qwen3.8-27b:free','qwen/qwen3.8-27b',
            'qwen/qwen3.8-27b-20260814:free','qwen/qwen3.8-27b-20260814'})
        self.assertNotIn('qwen/qwen3.8-27b-OTHER',names)

    def test_reasoning_native_wire_values(self):
        for effort in ['off','low','medium','xhigh']:
            payload=runner.make_payload('qwen/test:free','provider/fp4','text','rubric',{},effort,1234)
            expected={'enabled':False} if effort=='off' else {'enabled':True,'effort':effort}
            self.assertEqual(payload['reasoning'],expected)
            self.assertEqual(payload['max_tokens'],1234)
        with self.assertRaises(ValueError):runner.reasoning_config('none')

    def test_reasoning_capability_fail_closed(self):
        entry={'id':'qwen/test:free','reasoning':{'mandatory':False,'supported_efforts':['low','medium','xhigh']}}
        catalog={'data':[entry]};endpoint={'supported_parameters':['reasoning']}
        for effort in ['off','low','medium','xhigh']:
            runner.validate_reasoning(entry['id'],endpoint,catalog,effort)
        entry['reasoning']['mandatory']=True
        with self.assertRaises(ValueError):runner.validate_reasoning(entry['id'],endpoint,catalog,'off')
        entry['reasoning']['supported_efforts']=['low']
        with self.assertRaises(ValueError):runner.validate_reasoning(entry['id'],endpoint,catalog,'xhigh')
        with self.assertRaises(ValueError):runner.validate_reasoning(entry['id'],{},catalog,'low')

    def test_no_redirect(self):
        with self.assertRaises(ValueError): runner.NoRedirect().redirect_request(None,None,302,'',{},'https://example.org')

if __name__=='__main__': unittest.main()
