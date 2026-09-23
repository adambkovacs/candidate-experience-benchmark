import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from openrouter_paid_benchmark import BudgetLedger,budget_fields
from paid_budget_partitions import allocate,open_partition,reconcile_partition
class PartitionTests(unittest.TestCase):
 def specs(self):return [{'id':'a','model':'model-a','provider':'p','reasoning':'off','cap_usd':'0.35'},{'id':'b','model':'model-b','provider':'p','reasoning':'on','cap_usd':'0.35'}]
 def test_bound_parallel_and_reconcile_without_fake_spend(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);master=root/'master.jsonl';manifest=root/'partitions.json';allocate(master,manifest,self.specs())
   m=BudgetLedger(master);self.assertEqual(str(m.accounted()),'0.70')
   with self.assertRaises(ValueError):m.reserve('.01','x')
   m.close()
   a=open_partition(master,manifest,'a','model-a','p','off');b=open_partition(master,manifest,'b','model-b','p','on')
   self.assertEqual(budget_fields(a)['aggregate_cap_usd'],'5');self.assertEqual(budget_fields(a)['partition_cap_usd'],'0.35');self.assertIsNone(budget_fields(a)['aggregate_accounted_usd'])
   aid=a.reserve('.1','one');a.settle(aid,'.02');bid=b.reserve('.1','two');b.settle(bid,'.03')
   with self.assertRaises(ValueError):a.reserve('.34','three')
   a.close();b.close();event=reconcile_partition(master,manifest,'a');self.assertEqual(event['known_actual_usd'],'0.02');self.assertEqual(event['unknown_upper_bound_usd'],'0');self.assertNotIn('actual_cost_usd',event)
   with self.assertRaises(ValueError):open_partition(master,manifest,'a','model-a','p','off')
   reconcile_partition(master,manifest,'b');m=BudgetLedger(master);self.assertEqual(str(m.accounted()),'0.05');m.close()
 def test_pending_blocks_reconciliation_and_manifest_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);master=root/'master.jsonl';manifest=root/'partitions.json';allocate(master,manifest,self.specs());a=open_partition(master,manifest,'a','model-a','p','off');a.reserve('.1','one');a.close()
   with self.assertRaises(ValueError):reconcile_partition(master,manifest,'a')
   with self.assertRaises(ValueError):open_partition(master,manifest,'b','wrong','p','on')
   manifest.write_text(manifest.read_text()+' ')
   with self.assertRaises(ValueError):open_partition(master,manifest,'b','model-b','p','on')
 def test_oversubscription_and_duplicate_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);specs=self.specs();specs[0]['cap_usd']='4';specs[1]['cap_usd']='4'
   with self.assertRaises(ValueError):allocate(root/'master',root/'manifest',specs)
   self.assertFalse((root/'manifest').exists())

 def test_locks_reuse_and_unknown_bound(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);master=root/'master';manifest=root/'manifest';held=BudgetLedger(master)
   with self.assertRaises(BlockingIOError):allocate(master,manifest,self.specs())
   held.close();allocate(master,manifest,self.specs())
   with self.assertRaises(ValueError):allocate(master,root/'other',self.specs())
   child=open_partition(master,manifest,'a','model-a','p','off')
   with self.assertRaises(BlockingIOError):reconcile_partition(master,manifest,'a')
   attempt=child.reserve('.1','unknown');evidence=root/'evidence.jsonl';evidence.write_text(json.dumps({'attempt_id':attempt,'cost_unknown':True,'reserved_cost_usd':'.1'})+'\n');child.finalize_unknown_at_reserved_upper_bound(attempt,'operator review',evidence);child.close()
   event=reconcile_partition(master,manifest,'a');self.assertEqual(event['known_actual_usd'],'0');self.assertEqual(event['unknown_upper_bound_usd'],'0.1')
   m=BudgetLedger(master);self.assertEqual(m.accounted(),__import__('decimal').Decimal('.45'));m.close()
 def test_partition_identity_and_child_path_reuse(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);master=root/'master';manifest=root/'manifest';(root/'manifest-a.jsonl').write_text('occupied')
   with self.assertRaises(ValueError):allocate(master,manifest,self.specs())
   self.assertFalse(manifest.exists());(root/'manifest-a.jsonl').unlink();allocate(master,manifest,self.specs())
   for args in [('model-a','wrong','off'),('model-a','p','high')]:
    with self.assertRaises(ValueError):open_partition(master,manifest,'a',*args)

 def test_missing_or_empty_child_cannot_reset_funds(self):
  for empty in (False,True):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);master=root/'master';manifest=root/'manifest';data=allocate(master,manifest,self.specs());child=Path(data['partitions'][0]['child_ledger'])
    if empty:child.write_text('')
    else:child.unlink()
    with self.assertRaisesRegex(ValueError,'Missing or empty'):open_partition(master,manifest,'a','model-a','p','off')
    with self.assertRaisesRegex(ValueError,'Missing or empty'):reconcile_partition(master,manifest,'a')
    self.assertEqual(child.exists(),empty)
    if empty:self.assertEqual(child.stat().st_size,0)
 def test_closed_ledger_cannot_amend_cap(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'ledger';path.write_text('{"event":"budget","cap_usd":"1"}\n');ledger=BudgetLedger(path);ledger.append({'event':'partition_closed'})
   with self.assertRaises(ValueError):ledger.amend_cap('5','explicit approval does not reopen closed ledger')
   ledger.close()
