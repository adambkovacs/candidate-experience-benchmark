import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_hosted_final_suffix_reconciliation as module

REPO = Path(__file__).resolve().parents[1]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + '\n')
    return {'file': str(path), 'sha256': module.digest(path)}


def write_lines(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in data))
    return {'file': str(path), 'sha256': module.digest(path)}


class SuffixReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        refs = module.read_rows(REPO / 'data/pilot/proposed_labels.jsonl')
        pairs = json.loads((REPO / 'data/pilot/pairs.json').read_text())
        write_lines(self.root / 'data/pilot/proposed_labels.jsonl', refs)
        write_json(self.root / 'data/pilot/pairs.json', pairs)
        self.truth = {row['id']: row['proposed_labels'] for row in refs}
        self.spec = {'plan': 'plan.json', 'output': 'suffix.jsonl', 'partition': 'test-partition',
                     'parent': 'test-parent', 'failed': 'DEV-053'}
        self.patch_spec = patch.dict(module.SPECS, {'test': self.spec})
        self.patch_spec.start()
        self.addCleanup(self.patch_spec.stop)
        self.patch_budget = patch.object(module, 'BUDGET', Path('budget/manifest.json'))
        self.patch_budget.start()
        self.addCleanup(self.patch_budget.stop)
        self.original = [self.row(i) for i in range(1, 54)]
        self.original[-1].update(status='service_error', prediction=None, observed_cost_usd=None,
                                 cost_unknown=True, reserved_cost_usd='0.10')
        self.suffix = [self.row(i) for i in range(54, 61)]
        original = write_lines(self.root / 'original.jsonl', self.original)
        journal = write_lines(self.root / 'original.journal.jsonl', [{'event': 'terminal'}])
        self.plan = {'record_ids': [f'DEV-{i:03}' for i in range(54, 61)],
                     'excluded_failed_id': 'DEV-053', 'original_result': original,
                     'original_journal': journal}
        write_json(self.root / 'plan.json', self.plan)
        write_lines(self.root / 'suffix.jsonl', self.suffix)
        self.terminal = {'event': 'terminal', 'attempted_records': 7, 'planned_records': 7,
                         'completed': True, 'terminal_status': 'ok'}
        write_lines(self.root / 'suffix.jsonl.attempts.jsonl', [self.terminal])
        child = self.root / 'budget/child.jsonl'
        write_lines(child, [{'event': 'budget', 'cap_usd': '1'}, {'event': 'partition_closed'}])
        master = self.root / 'budget/master.jsonl'
        write_lines(master, [{'event': 'partition_reconciled', 'partition_id': 'test-partition',
                              'child_sha256': module.digest(child), 'known_actual_usd': '0.07',
                              'unknown_upper_bound_usd': '0'}])
        write_json(self.root / 'budget/manifest.json',
                   {'version': 'paid-partitions-v1', 'master_ledger': str(master),
                    'partitions': [{'id': 'test-partition', 'child_ledger': str(child)}]})

    def row(self, i):
        ident = f'DEV-{i:03}'
        return {'id': ident, 'status': 'ok', 'prediction': self.truth[ident],
                'observed_cost_usd': '0.01', 'cost_unknown': False,
                'reserved_cost_usd': '0.10', 'elapsed_seconds': 1.5}

    def test_reconciles_disjoint_sixty_and_preserves_failed_unknown(self):
        result = module.reconcile('test', self.root)
        self.assertEqual(result['attempted'], 60)
        self.assertEqual(result['valid_outputs'], 59)
        self.assertEqual(result['status_counts'], {'ok': 59, 'service_error': 1})
        self.assertEqual(result['cost']['known_observed_usd'], '0.59')
        self.assertEqual(result['cost']['unknown_reserved_upper_bound_usd'], '0.10')
        self.assertIsNone(result['cost']['actual_total_usd'])
        self.assertFalse(result['eligible_paired_comparison'])
        self.assertEqual(result['timing']['attempts'], 60)
        self.assertTrue(result['timing']['complete'])

    def test_refuses_unsealed_budget_or_missing_terminal(self):
        child = self.root / 'budget/child.jsonl'
        write_lines(child, [{'event': 'budget', 'cap_usd': '1'}])
        with self.assertRaisesRegex(ValueError, 'not sealed'):
            module.reconcile('test', self.root)
        write_lines(child, [{'event': 'budget', 'cap_usd': '1'}, {'event': 'partition_closed'}])
        journal = self.root / 'suffix.jsonl.attempts.jsonl'
        write_lines(journal, [{'event': 'started'}])
        with self.assertRaisesRegex(ValueError, 'not terminal'):
            module.reconcile('test', self.root)

    def test_qwen8_interruption_is_one_ambiguous_attempt_not_a_retry(self):
        module.SPECS['test'] = {**self.spec, 'failed': 'DEV-027', 'interruption': 'interruption.jsonl'}
        original = [self.row(i) for i in range(1, 27)]
        suffix = [self.row(i) for i in range(28, 61)]
        original_binding = write_lines(self.root / 'original.jsonl', original)
        journal_binding = write_lines(self.root / 'original.journal.jsonl', [{'event': 'started', 'id': 'DEV-027'}])
        write_lines(self.root / 'suffix.jsonl', suffix)
        self.terminal.update(attempted_records=33, planned_records=33)
        write_lines(self.root / 'suffix.jsonl.attempts.jsonl', [self.terminal])
        write_lines(self.root / 'interruption.jsonl',
                    [{'id': 'DEV-027', 'status': 'interrupted_no_provider_result',
                      'cost_unknown': True, 'reserved_cost_usd': '0.10',
                      'source_result_sha256': original_binding['sha256'],
                      'source_journal_sha256': journal_binding['sha256']}])
        write_json(self.root / 'plan.json', {'ids': [f'DEV-{i:03}' for i in range(28, 61)],
                    'excluded_ambiguous_id': 'DEV-027',
                    'sources': {'original': original_binding, 'journal': journal_binding}})
        result = module.reconcile('test', self.root)
        self.assertEqual(result['attempted'], 60)
        self.assertEqual(result['valid_outputs'], 59)
        self.assertEqual(result['status_counts']['interrupted_no_provider_result'], 1)
        self.assertEqual(result['timing']['elapsed_available'], 59)
        self.assertFalse(result['timing']['complete'])
        self.assertEqual(result['cost']['unknown_reserved_upper_bound_usd'], '0.10')
        interrupted = self.root / 'interruption.jsonl'
        evidence = module.lines(interrupted)
        evidence[0]['source_result_sha256'] = 'wrong'
        write_lines(interrupted, evidence)
        with self.assertRaisesRegex(ValueError, 'interruption receipt'):
            module.reconcile('test', self.root)

    def test_terminal_partial_suffix_keeps_failures_and_never_sent_ids(self):
        partial = self.suffix[:6]
        partial[-1].update(status='service_error', prediction=None, observed_cost_usd=None,
                           cost_unknown=True, reserved_cost_usd='0.10')
        write_lines(self.root / 'suffix.jsonl', partial)
        self.terminal.update(attempted_records=6, completed=False, terminal_status='service_error')
        write_lines(self.root / 'suffix.jsonl.attempts.jsonl', [self.terminal])
        result = module.reconcile('test', self.root)
        self.assertEqual(result['attempted'],59)
        self.assertEqual(result['valid_outputs'],57)
        self.assertEqual(result['status_counts']['service_error'],2)
        self.assertEqual(result['never_sent_ids'],['DEV-060'])
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['cost']['unknown_reserved_upper_bound_usd'],'0.20')
        self.terminal['completed'] = True
        write_lines(self.root / 'suffix.jsonl.attempts.jsonl', [self.terminal])
        with self.assertRaisesRegex(ValueError, 'terminal disagrees'):
            module.reconcile('test', self.root)

    def test_refuses_duplicate_or_missing_suffix_id(self):
        self.suffix[0]['id'] = 'DEV-053'
        write_lines(self.root / 'suffix.jsonl', self.suffix)
        with self.assertRaisesRegex(ValueError, 'planned prefix'):
            module.reconcile('test', self.root)


if __name__ == '__main__':
    unittest.main()
