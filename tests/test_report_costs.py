import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_development_report import summarize_costs,cost_table,load_timing_attempts
class CostTests(unittest.TestCase):
 def test_actual_and_unknown_bounds_separate_exact_decimals(self):
  rows=[{'cost_unknown':False,'observed_cost_usd':'0.10000000000000001','reserved_cost_usd':'1'}, {'cost_unknown':False,'observed_cost_usd':'0.2'}, {'cost_unknown':True,'observed_cost_usd':None,'reserved_cost_usd':'0.04'}]
  c=summarize_costs(rows,['first.jsonl','retry.jsonl'])
  self.assertEqual(c['known_actual_usd'],'0.30000000000000001');self.assertEqual(c['unknown_reserved_upper_bound_usd'],'0.04');self.assertEqual(c['known_plus_unknown_upper_bound_usd'],'0.34000000000000001');self.assertIsNone(c['total_actual_usd']);self.assertEqual(c['scope'],'declared development attempts only');self.assertEqual(c['source_paths'],['first.jsonl','retry.jsonl'])
 def test_subscription_equivalent_and_missing_fields_are_unavailable(self):
  for row in [{},{'usage':{'cost':5},'total_cost_usd':5},{'observed_cost_usd':None},{'cost_unknown':False}]:
   c=summarize_costs([row],['a']);self.assertEqual(c['availability'],'unavailable');self.assertIsNone(c['known_actual_usd']);self.assertIsNone(c['total_actual_usd'])
 def test_partial_coverage_not_zero(self):
  c=summarize_costs([{'cost_unknown':False,'observed_cost_usd':'0.01'},{}],['a']);self.assertEqual(c['availability'],'partial');self.assertEqual(c['known_actual_usd'],'0.01');self.assertIsNone(c['known_plus_unknown_upper_bound_usd']);self.assertEqual(c['missing_financial_attempts'],1)
 def test_invalid_amounts_rejected(self):
  for value in ['NaN','Infinity','-1',True,'bad']:
   with self.subTest(value=value),self.assertRaises(ValueError):summarize_costs([{'cost_unknown':False,'observed_cost_usd':value}],['a'])
  with self.assertRaises(ValueError):summarize_costs([{'cost_unknown':True,'observed_cost_usd':'0','reserved_cost_usd':'.1'}],['a'])
 def test_all_declared_attempts_including_retry_count_once(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for i,cost in [(1,'.1'),(2,'.2')]:
    (root/f'a{i}.jsonl').write_text(json.dumps({'id':'DEV-001','attempt_id':str(i),'phase':'development','elapsed_seconds':1,'cost_unknown':False,'observed_cost_usd':cost})+'\n')
   config={'attempt_phase':'development','predictions_file':'a2.jsonl','attempt_files':['a1.jsonl','a2.jsonl']}
   c=summarize_costs(load_timing_attempts(config,{'DEV-001'},root),config['attempt_files']);self.assertEqual(c['total_actual_usd'],'0.3');self.assertEqual(c['attempt_count'],2)
   for paths in [['a1.jsonl','a1.jsonl'],['smoke.jsonl']]:
    if paths[0]=='smoke.jsonl':(root/'smoke.jsonl').write_bytes((root/'a1.jsonl').read_bytes())
    with self.assertRaises(ValueError):load_timing_attempts({**config,'attempt_files':paths},{'DEV-001'},root)
 def test_table_cash_unknown_and_ledger_scope(self):
  c=summarize_costs([{'cost_unknown':True,'observed_cost_usd':None,'reserved_cost_usd':'.04'}],['retry.jsonl'])
  text='\n'.join(cost_table([{'id':'paid','cost':c},{'id':'subscription','cost':summarize_costs([{}],['cli'])}]))
  self.assertIn('Unknown-cost reserved upper bound',text);self.assertIn('retry.jsonl',text);self.assertIn('not the shared $1 ledger balance',text);self.assertNotIn('| subscription |',text);self.assertNotIn('spent',text)
if __name__=='__main__':unittest.main()
