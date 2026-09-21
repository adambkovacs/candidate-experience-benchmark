import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
from types import SimpleNamespace
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jev_benchmark as j

class JevTests(unittest.TestCase):
    def response(self):
        return {'model':'openjev-0.1', 'answers':{k:{'type':'choice','choice':v[0],
            'probabilities':{label:float(i==0) for i,label in enumerate(v)},'confidence':1.0}
            for k,v in j.VALUES.items()}}

    def test_modes_and_identity(self):
        j.validate_config('openjev','http://127.0.0.1:8080','openjev-0.1','fixed')
        j.validate_config('typesafe','https://api.typesafe.ai','jev-1.13.0','official',True)
        for args in [('typesafe','https://api.typesafe.ai','jev-1.13.0','official'),
                     ('typesafe','https://api.typesafe.ai','jev-latest','official',True),
                     ('typesafe','https://evil.test','jev-1.13.0','official',True),
                     ('openjev','http://127.0.0.1:8080','jev-latest','fixed'),
                     ('openjev','https://codiv.ai','openjev-0.1','fixed'),
                     ('openjev','http://localhost:8080/?x=1','openjev-0.1','fixed')]:
            with self.assertRaises(ValueError): j.validate_config(*args)

    def test_frozen_four_choice_and_no_labels(self):
        p=j.make_payload('feedback','rubric','openjev-0.1','fixed')
        self.assertEqual(list(p['questions']),list(j.KEYS))
        self.assertEqual(set(p['state']),{'feedback','policy'})
        self.assertEqual(p['samples'],1)
        self.assertEqual(p['think'],0)
        self.assertFalse(p['sequential'])
        for k in j.KEYS:
            self.assertEqual(list(p['questions'][k]['criteria']),j.VALUES[k])
            self.assertEqual(p['questions'][k]['type'],'choice')
        self.assertNotIn('proposed_labels',json.dumps(p))
        self.assertNotIn('feedback',j.make_payload('different','rubric','openjev-0.1','fixed')['state']['feedback'])

    def test_adaptive_omits_samples_and_official_omits_extensions(self):
        self.assertNotIn('samples',j.make_payload('f','p','openjev-0.1','adaptive'))
        self.assertEqual(set(j.make_payload('f','p','jev-1.13.0','official')),{'state','model','questions'})

    def test_parse_valid(self):
        self.assertTrue(j.valid(j.parse_response(self.response(),'openjev-0.1')))

    def test_reject_mismatches_and_bad_distributions(self):
        for change in ['model','labels','confidence','nan','sum','choice','type']:
            b=self.response(); a=b['answers']['sentiment']
            if change=='model': b['model']='jev-1.13.0'
            if change=='labels': a['probabilities']['unknown']=0
            if change=='confidence': a['confidence']=True
            if change=='nan': a['probabilities']['positive']=float('nan')
            if change=='sum': a['probabilities']['positive']=0.5
            if change=='choice': a['choice']='negative'
            if change=='type': a['type']='noul'
            with self.subTest(change=change),self.assertRaises(ValueError): j.parse_response(b,'openjev-0.1')

    def test_run_reads_only_input_and_retains_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(surface='openjev',base_url='http://127.0.0.1:8080',
                model='openjev-0.1',mode='fixed',authorize_hosted_inference=False,
                output=str(Path(tmp)/'out.jsonl'),limit=1,config_note='fixture',timeout=1)
            original=j.read_rows
            def checked_read(path):
                self.assertEqual(Path(path).name,'inputs.jsonl')
                return original(path)
            with mock.patch.object(j,'read_rows',side_effect=checked_read), mock.patch.object(j,'fetch',return_value=self.response()) as fetch:
                j.run(args)
            record=json.loads(Path(args.output).read_text())
            self.assertEqual(record['status'],'ok')
            self.assertEqual(record['raw_response'],self.response())
            self.assertIsNone(record['actual_reads'])
            self.assertEqual(set(fetch.call_args.args[1]['state']),{'feedback','policy'})
            with self.assertRaises(FileExistsError): j.run(args)

    def test_hosted_budget_blocks_before_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(surface='typesafe',base_url='https://api.typesafe.ai',
                model='jev-1.13.0',mode='official',authorize_hosted_inference=True,
                output=str(Path(tmp)/'out.jsonl'),limit=3,config_note='fixture',timeout=1,
                max_usd='0.00000001',env_file=None,budget_ledger=str(Path(tmp)/'ledger.jsonl'))
            with mock.patch.object(j,'load_key',return_value='secret'), mock.patch.object(j,'fetch') as fetch:
                j.run(args)
            fetch.assert_not_called()
            self.assertEqual(Path(args.output).read_text(),'')

    def test_hosted_unknown_usage_stops_and_reserves(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(surface='typesafe',base_url='https://api.typesafe.ai',
                model='jev-1.13.0',mode='official',authorize_hosted_inference=True,
                output=str(Path(tmp)/'out.jsonl'),limit=3,config_note='fixture',timeout=1,
                max_usd='0.1',env_file=None,budget_ledger=str(Path(tmp)/'ledger.jsonl'))
            response=self.response();response['model']='jev-1.13.0'
            with mock.patch.object(j,'load_key',return_value='secret'), mock.patch.object(j,'fetch',return_value=response) as fetch:
                j.run(args)
            self.assertEqual(fetch.call_count,1)
            row=json.loads(Path(args.output).read_text())
            self.assertTrue(row['cost_unknown'])
            self.assertEqual(row['reserved_cost_usd'],row['cumulative_accounted_usd'])

    def test_usage_cost_and_safe_key_parser(self):
        self.assertEqual(str(j.usage_cost({'usage':{'input_tokens':1000000}})),'0.042')
        self.assertIsNone(j.usage_cost({'usage':{'input_tokens':True}}))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.env';path.write_text('OTHER=hidden\nTYPESAFE_API_KEY="selected"\n')
            with mock.patch.dict(j.os.environ,{},clear=True):
                self.assertEqual(j.load_key('typesafe',path),'selected')
                self.assertIsNone(j.load_key('openjev',path))

    def test_budget_survives_restart_and_unknown_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.jsonl'
            a=j.BudgetLedger(path,j.Decimal('1'))
            first=a.reserve(j.Decimal('0.6'),'one')
            self.assertIsNotNone(first)
            a.close()
            b=j.BudgetLedger(path,j.Decimal('1'))
            self.assertIsNone(b.reserve(j.Decimal('0.5'),'two'))
            b.settle(first,j.Decimal('0.1'))
            self.assertIsNotNone(b.reserve(j.Decimal('0.5'),'two'))
            self.assertEqual(b.accounted(),j.Decimal('0.6'))
            b.close()

    def test_local_thinking_and_generation_settings(self):
        j.validate_config('openjev','http://localhost:8080','openjev-0.1','thinking')
        p=j.make_payload('feedback','policy','openjev-0.1','thinking')
        self.assertEqual((p['samples'],p['steps'],p['think']),(1,1,512))
        for mode,thinking in [('generated-on',True),('generated-off',False)]:
            j.validate_config('openjev','http://localhost:8080','diffusiongemma-26b',mode)
            p=j.make_payload('feedback','policy','diffusiongemma-26b',mode)
            self.assertEqual(p['chat_template_kwargs']['enable_thinking'],thinking)
            self.assertEqual(len(p['messages']),2)
            self.assertNotIn('questions',p)

    def test_no_redirect(self):
        with self.assertRaises(ValueError): j.NoRedirect().redirect_request()

if __name__=='__main__': unittest.main()
