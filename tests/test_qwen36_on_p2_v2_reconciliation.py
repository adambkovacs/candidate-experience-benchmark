import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_qwen36_on_p2_v2_reconciliation as module

REPO = Path(__file__).resolve().parents[1]


def write(path, value, jsonl=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row)+'\n' for row in value) if jsonl else json.dumps(value)+'\n')
    return {'file': str(path), 'sha256': module.digest(path)}


class Final21ReconciliationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        refs = module.read_rows(REPO/'data/pilot/proposed_labels.jsonl')
        self.truth = {r['id']: r['proposed_labels'] for r in refs}
        write(self.root/'data/pilot/proposed_labels.jsonl', refs, True)
        write(self.root/'data/pilot/pairs.json', json.loads((REPO/'data/pilot/pairs.json').read_text()))
        self.patch = patch.multiple(module, PLAN=Path('plan.json'), OUTPUT=Path('v2.jsonl'),
                                    BUDGET=Path('budget/manifest.json'), PARTITION='test-partition')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        original = [self.row(i) for i in range(1,34)]
        v1 = [self.row(i) for i in range(34,40)]
        v2 = [self.row(40)]
        for row in (original[-1],v1[-1],v2[-1]):
            row.update(status='service_error', prediction=None, http_status=429,
                       observed_cost_usd=None, cost_unknown=True, reserved_cost_usd='0.10')
        self.original = write(self.root/'original.jsonl',original,True)
        self.v1 = write(self.root/'v1.jsonl',v1,True)
        self.original_journal = write(self.root/'original.journal.jsonl',
                                      [{'event':'started','id':f'DEV-{i:03}'} for i in range(1,34)]+[{'event':'terminal'}],True)
        self.v1_journal = write(self.root/'v1.journal.jsonl',
                                [{'event':'started','id':f'DEV-{i:03}'} for i in range(34,40)]+[{'event':'terminal'}],True)
        prior = {'attempted':39,'valid_outputs':37,'never_sent_ids':module.EXPECTED_SUFFIX,
                 'status_counts':{'service_error':2},
                 'sources':{'original':self.original,'suffix':self.v1}}
        self.prior = write(self.root/'prior.json',prior)
        review = write(self.root/'review.json',{'approved':True})
        plan = {'contract':'qwen36-on-p2-never-sent-final21-v2','record_ids':module.EXPECTED_SUFFIX,
                'excluded_failed_ids':['DEV-033','DEV-039'],'new_output':str(module.OUTPUT),
                'original_timing_preserved':False,
                'sources':{'original_result':self.original,'original_journal':self.original_journal,
                           'v1_result':self.v1,'v1_journal':self.v1_journal,
                           'v1_report':self.prior,'smoke_review':review}}
        write(self.root/'plan.json',plan)
        write(self.root/'v2.jsonl',v2,True)
        self.terminal = {'event':'terminal','attempted_records':1,'planned_records':21,
                         'completed':False,'terminal_status':'service_error'}
        write(self.root/'v2.jsonl.attempts.jsonl',[self.terminal],True)
        child = self.root/'budget/child.jsonl'
        write(child,[{'event':'budget','cap_usd':'0.64'},{'event':'partition_closed'}],True)
        master = self.root/'budget/master.jsonl'
        write(master,[{'event':'partition_reconciled','partition_id':'test-partition',
                       'child_sha256':module.digest(child),'known_actual_usd':'0',
                       'unknown_upper_bound_usd':'0.10'}],True)
        write(self.root/'budget/manifest.json',{'version':'paid-partitions-v1',
              'master_ledger':str(master),'partitions':[{'id':'test-partition','child_ledger':str(child),
              'model':'qwen/qwen3.6-35b-a3b','provider':'akashml/fp8','reasoning':'on'}]})

    def row(self, number):
        ident=f'DEV-{number:03}'
        return {'id':ident,'status':'ok','prediction':self.truth[ident],
                'observed_cost_usd':'0.01','cost_unknown':False,
                'reserved_cost_usd':'0.10','elapsed_seconds':1.0}

    def test_terminal_partial_counts_all_three_failures_and_twenty_never_sent(self):
        result=module.reconcile(self.root)
        self.assertEqual((result['attempted'],result['valid_outputs'],result['never_sent_count']),(40,37,20))
        self.assertEqual(result['status_counts'],{'ok':37,'service_error':3})
        self.assertEqual(result['cost']['known_observed_usd'],'0.37')
        self.assertEqual(result['cost']['unknown_reserved_upper_bound_usd'],'0.30')
        self.assertIsNone(result['cost']['actual_total_usd'])
        self.assertFalse(result['eligible_paired_comparison'])
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['timing']['sum_reported_attempt_seconds'],40.0)

    def test_refuses_live_or_mismatched_terminal_and_budget(self):
        journal=self.root/'v2.jsonl.attempts.jsonl'
        write(journal,[{'event':'started','id':'DEV-040'}],True)
        with self.assertRaisesRegex(ValueError,'not terminal'):
            module.reconcile(self.root)
        write(journal,[dict(self.terminal,attempted_records=2)],True)
        with self.assertRaisesRegex(ValueError,'terminal disagrees'):
            module.reconcile(self.root)
        write(journal,[self.terminal],True)
        write(self.root/'budget/child.jsonl',[{'event':'budget','cap_usd':'0.64'}],True)
        with self.assertRaisesRegex(ValueError,'not sealed'):
            module.reconcile(self.root)

    def test_rejects_duplicate_suffix_or_prior_hash_change(self):
        row=self.row(39)
        write(self.root/'v2.jsonl',[row],True)
        with self.assertRaisesRegex(ValueError,'planned prefix'):
            module.reconcile(self.root)
        write(self.root/'v2.jsonl',[self.row(40)],True)
        prior=json.loads((self.root/'prior.json').read_text())
        prior['valid_outputs']=38
        write(self.root/'prior.json',prior)
        with self.assertRaisesRegex(ValueError,'Source hash mismatch'):
            module.reconcile(self.root)


if __name__=='__main__': unittest.main()
