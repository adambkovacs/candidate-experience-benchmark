import copy,json,sys,tempfile,unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
import openrouter_paid_benchmark as r

MODEL='qwen/qwen3.8-27b'
def fixture():
 return ({'id':MODEL,'reasoning':{'mandatory':False,'supported_efforts':['low','high']},'supported_parameters':['reasoning']},
 {'tag':'provider/fp8','provider_name':'Provider','model_id':MODEL,'status':0,'context_length':8192,'max_completion_tokens':8192,'pricing':{'prompt':'0.0000001','completion':'0.0000007'},'supported_parameters':['structured_outputs','reasoning','max_tokens','temperature']})
class PaidTests(unittest.TestCase):
 def test_price_units_and_extra_fees_fail_closed(self):
  m,e=fixture();p=r.make_payload(MODEL,e,'feedback','rubric',{},'off',4096,Decimal('.1'),Decimal('.7'),m)
  self.assertEqual(p['provider']['max_price'],{'prompt':.1,'completion':.7,'request':0,'image':0})
  self.assertFalse(p['provider']['allow_fallbacks']);self.assertEqual(p['provider']['only'],['provider/fp8'])
  self.assertEqual(p['reasoning'],{'enabled':False});self.assertEqual(json.loads(p['messages'][1]['content']),{'feedback':'feedback'})
  self.assertEqual(r.reservation(e,4096),Decimal('0.0036864'))
  self.assertEqual(r.reservation(e,4096,Decimal('.2'),Decimal('1')),Decimal('.0057344'))
  for k,v in [('request','.01'),('input_cache_write','.0001'),('unknown','1'),('overrides',[]),('completion','NaN')]:
   bad=copy.deepcopy(e);bad['pricing'][k]=v
   with self.assertRaises(ValueError):r.check_prices(bad,Decimal('.1'),Decimal('.7'))
 def test_capabilities_and_identity(self):
  m,e=fixture();c={'data':[m]};es={'data':{'id':MODEL,'endpoints':[e]}}
  self.assertEqual(r.select_endpoint(MODEL,'provider/fp8',c,es,Decimal('.1'),Decimal('.7')),(m,e))
  for mutation in ({'status':-5},{'tag':'other'},{'model_id':'different'}):
   bad=copy.deepcopy(es);bad['data']['endpoints'][0].update(mutation)
   with self.assertRaises(ValueError):r.select_endpoint(MODEL,'provider/fp8',c,bad,Decimal('.1'),Decimal('.7'))
 def test_reasoning_model_specific(self):
  m,e=fixture();self.assertEqual(r.reasoning(m,e,'high'),{'enabled':True,'effort':'high'})
  for effort in ['max','ultra','medium','na']:
   with self.assertRaises(ValueError):r.reasoning(m,e,effort)
  self.assertIsNone(r.reasoning({'supported_parameters':[]},{'supported_parameters':[]},'na'))
  with self.assertRaises(ValueError):r.reasoning({'supported_parameters':['reasoning']},e,'na')
  with self.assertRaises(ValueError):r.reasoning({'reasoning':{'mandatory':True}},e,'off')
 def test_ledger_durable_reserve_settle_and_cap(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger';a=r.BudgetLedger(p);i=a.reserve(Decimal('.6'),'A');a.settle(i,Decimal('.4'));j=a.reserve(Decimal('.6'),'B');a.settle(j,Decimal('.6'))
   with self.assertRaises(ValueError):a.reserve(Decimal('.00001'),'C')
   a.close();b=r.BudgetLedger(p);self.assertEqual(b.accounted(),Decimal('1.0'));b.close()
 def test_unknown_and_crash_reservations_block_future_runs(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger';a=r.BudgetLedger(p);i=a.reserve(Decimal('.1'),'A');a.settle(i,None);a.close();b=r.BudgetLedger(p)
   with self.assertRaises(ValueError):b.reserve(Decimal('.1'),'B')
   self.assertEqual(b.accounted(),Decimal('.1'));b.close()
 def test_lock_prevents_concurrent_overspend(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger';a=r.BudgetLedger(p)
   with self.assertRaises(BlockingIOError):r.BudgetLedger(p)
   a.close()
 def test_actual_cost_over_reserve_stops_ledger(self):
  with tempfile.TemporaryDirectory() as d:
   a=r.BudgetLedger(Path(d)/'ledger');i=a.reserve(Decimal('.1'),'A');self.assertFalse(a.settle(i,Decimal('.2')))
   with self.assertRaises(ValueError):a.reserve(Decimal('.1'),'B')
   a.close()
 def test_input_contract(self):
  rows=[{'id':f'DEV-{i:03}','feedback':'x'} for i in range(1,61)]
  self.assertEqual(r.validate_rows(rows),rows)
  for change in ('duplicate','metadata','missing'):
   bad=copy.deepcopy(rows)
   if change=='duplicate':bad[-1]['id']='DEV-001'
   if change=='metadata':bad[0]['proposed_labels']={}
   if change=='missing':bad.pop()
   with self.assertRaises(ValueError):r.validate_rows(bad)
 def test_smoke_journal_before_request_and_unknown_cost_stop(self):
  m,e=fixture();calls=[]
  with tempfile.TemporaryDirectory() as d:
   args=SimpleNamespace(output=str(Path(d)/'out'),model=MODEL,provider=e['tag'],max_input_price=Decimal('.1'),max_output_price=Decimal('.7'),reasoning='off',max_tokens=4096,phase='smoke',env_file=None,timeout=1)
   def fetch(path,*rest,**kwargs):
    calls.append(path)
    if path=='/models':return {'data':[m]}
    if path.endswith('/endpoints'):return {'data':{'id':MODEL,'endpoints':[e]}}
    self.assertEqual(json.loads(Path(args.output+'.attempts.jsonl').read_text())['request']['messages'][1]['role'],'user')
    self.assertIn('reserve',Path(d,'ledger').read_text())
    raise RuntimeError('SECRET')
   with mock.patch.object(r,'fetch',side_effect=fetch),mock.patch.object(r,'load_key',return_value='SECRET'),mock.patch.object(r,'LEDGER_PATH',Path(d)/'ledger'):
    r.run(args)
   out=Path(args.output).read_text();self.assertNotIn('SECRET',out);row=json.loads(out);self.assertTrue(row['cost_unknown']);self.assertEqual(row['status'],'service_error');self.assertEqual(calls.count('/chat/completions'),1)

class ResponseTests(unittest.TestCase):
 def test_success_and_response_guards(self):
  prediction={'sentiment':'neutral','follow_up_needed':'no','serious_concern_reported':'no','testimonial_potential':'no'}
  for override,status,expected_calls in [({},'ok',3),({'model':'wrong'},'model_mismatch',1),({'provider':'wrong'},'provider_mismatch',1),({'usage':{}},'ok',1),({'finish':'length'},'invalid_output',1)]:
   with self.subTest(override=override),tempfile.TemporaryDirectory() as d:
    m,e=fixture();args=SimpleNamespace(output=str(Path(d)/'out'),model=MODEL,provider=e['tag'],max_input_price=Decimal('.1'),max_output_price=Decimal('.7'),reasoning='off',max_tokens=4096,phase='smoke',env_file=None,timeout=1)
    body={'model':override.get('model',MODEL),'provider':override.get('provider','Provider'),'usage':override.get('usage',{'cost':.0001}),'choices':[{'finish_reason':override.get('finish','stop'),'message':{'content':json.dumps(prediction)}}]}
    responses=[{'data':[m]},{'data':{'id':MODEL,'endpoints':[e]}}]+[body]*3
    with mock.patch.object(r,'fetch',side_effect=responses) as fetch,mock.patch.object(r,'load_key',return_value='SECRET'),mock.patch.object(r,'LEDGER_PATH',Path(d)/'ledger'):
     r.run(args)
    rows=[json.loads(x) for x in Path(args.output).read_text().splitlines()];self.assertEqual(len(rows),expected_calls);self.assertEqual(rows[-1]['status'],status)
    self.assertEqual(sum(x.args[0]=='/chat/completions' for x in fetch.call_args_list),expected_calls)
    if not override:self.assertEqual(Decimal(rows[-1]['aggregate_accounted_usd']),Decimal('.0003'))
 def test_named_none_supported_only_when_advertised(self):
  m,e=fixture()
  with self.assertRaises(ValueError):r.reasoning(m,e,'none')
  m['reasoning']['supported_efforts']=['none','high'];self.assertEqual(r.reasoning(m,e,'none'),{'enabled':False,'effort':'none'})
 def test_unauthorized_model_is_rejected(self):
  m,e=fixture()
  with self.assertRaises(ValueError):r.select_endpoint('openai/paid','provider/fp8',{'data':[m]},{'data':{'id':MODEL,'endpoints':[e]}},Decimal('.1'),Decimal('.7'))

class UnknownUpperBoundTests(unittest.TestCase):
 def test_explicit_unknown_accounting_keeps_full_reserve_and_persists(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'ledger';proof=Path(d)/'attempt.jsonl';a=r.BudgetLedger(path);i=a.reserve(Decimal('.6'),'A')
   proof.write_text(json.dumps({'attempt_id':i,'cost_unknown':True,'reserved_cost_usd':'.6'})+'\n')
   before=proof.read_bytes();a.finalize_unknown_at_reserved_upper_bound(i,'HTTP error with no usage cost',proof)
   self.assertEqual(proof.read_bytes(),before);self.assertEqual(a.accounted(),Decimal('.6'));self.assertEqual(a.events[-1]['actual_cost_usd'],None)
   with self.assertRaises(ValueError):a.finalize_unknown_at_reserved_upper_bound(i,'duplicate',proof)
   with self.assertRaises(ValueError):a.settle(i,Decimal('0'))
   a.close();b=r.BudgetLedger(path);self.assertEqual(b.accounted(),Decimal('.6'))
   with self.assertRaises(ValueError):b.reserve(Decimal('.400001'),'B')
   j=b.reserve(Decimal('.4'),'B');b.settle(j,Decimal('.4'));self.assertEqual(b.accounted(),Decimal('1'));b.close()
 def test_evidence_and_pending_required(self):
  with tempfile.TemporaryDirectory() as d:
   a=r.BudgetLedger(Path(d)/'ledger');i=a.reserve(Decimal('.6'),'A');proof=Path(d)/'attempt'
   for data in ({'attempt_id':'wrong','cost_unknown':True,'reserved_cost_usd':'.6'},{'attempt_id':i,'cost_unknown':False,'reserved_cost_usd':'.6'},{'attempt_id':i,'cost_unknown':True,'reserved_cost_usd':'.5'}):
    proof.write_text(json.dumps(data))
    with self.assertRaises(ValueError):a.finalize_unknown_at_reserved_upper_bound(i,'reason',proof)
   with self.assertRaises(ValueError):a.finalize_unknown_at_reserved_upper_bound('unknown','reason',proof)
   with self.assertRaises(ValueError):a.finalize_unknown_at_reserved_upper_bound(i,' ',proof)
   self.assertEqual(a.accounted(),Decimal('.6'));self.assertIn(i,a.state()[1]);a.close()
 def test_replay_rejects_reduced_unknown_bound(self):
  with tempfile.TemporaryDirectory() as d:
   a=r.BudgetLedger(Path(d)/'ledger');i=a.reserve(Decimal('.6'),'A')
   a.append({'event':'unknown_cost_accounted_as_upper_bound','attempt_id':i,'usd':'.1','actual_cost_usd':None})
   with self.assertRaises(ValueError):a.accounted()
   a.close()

if __name__=='__main__':unittest.main()
