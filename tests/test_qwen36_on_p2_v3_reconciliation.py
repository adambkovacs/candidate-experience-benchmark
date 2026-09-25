import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_qwen36_on_p2_v3_reconciliation as module

REPO = Path(__file__).resolve().parents[1]


def write(root, name, value, jsonl=False):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((''.join(json.dumps(row) + '\n' for row in value) if jsonl
                     else json.dumps(value) + '\n'))
    return {'file': name, 'sha256': module.digest(path)}


class Final20ReconciliationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.patcher = patch.multiple(module, PLAN=Path('plan.json'), OUTPUT=Path('v3.jsonl'),
                                      DEST=Path('report.json'), CONTROLLER=Path('controller.py'))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        (self.root / 'controller.py').write_text('frozen controller\n')
        refs = module.read_rows(REPO / 'data/pilot/proposed_labels.jsonl')
        self.truth = {row['id']: row['proposed_labels'] for row in refs}
        write(self.root, 'data/pilot/proposed_labels.jsonl', refs, True)
        write(self.root, 'data/pilot/pairs.json',
              json.loads((REPO / 'data/pilot/pairs.json').read_text()))
        original = [self.row(i) for i in range(1, 34)]
        v1 = [self.row(i) for i in range(34, 40)]
        v2 = [self.row(40)]
        for row in (original[-1], v1[-1], v2[-1]):
            row.update(status='service_error', prediction=None, http_status=429,
                       observed_cost_usd=None, cost_unknown=True)
        sources = {
            'original_result': write(self.root, 'original.jsonl', original, True),
            'original_journal': write(self.root, 'original.journal', self.journal(1, 33), True),
            'v1_result': write(self.root, 'v1.jsonl', v1, True),
            'v1_journal': write(self.root, 'v1.journal', self.journal(34, 39), True),
            'v2_result': write(self.root, 'v2.jsonl', v2, True),
            'v2_journal': write(self.root, 'v2.journal',
                                [{'event': 'started', 'id': 'DEV-040'},
                                 {'event': 'terminal', 'attempted_records': 1, 'planned_records': 21,
                                  'terminal_status': 'service_error', 'completed': False}], True),
            'v2_plan': write(self.root, 'v2-plan.json', {}),
            'v1_report': write(self.root, 'v1-report.json', {}),
            'smoke_review': write(self.root, 'smoke-review.json', {'approved': True}),
        }
        prior = {'contract': 'qwen36-on-p2-final21-reconciliation-v2', 'attempted': 40,
                 'valid_outputs': 37, 'never_sent_ids': module.FINAL,
                 'status_counts': {'service_error': 3}, 'eligible_paired_comparison': False,
                 'sources': {'prior_report': sources['v1_report'],
                             'suffix_v2': sources['v2_result'],
                             'suffix_v2_journal': sources['v2_journal']}}
        sources['v2_report'] = write(self.root, 'v2-report.json', prior)
        self.requests = []
        for offset in range(20):
            request = {'model': 'qwen/qwen3.6-35b-a3b', 'test_index': offset}
            self.requests.append(write(self.root, f'request-{offset}.json', {'request': request}))
        frozen = write(self.root, 'frozen.json', {})
        route = write(self.root, 'route.json', {})
        plan = {'frozen_execution': frozen, 'route_audit': route, 'contract': 'qwen36-on-p2-never-sent-final20-v3',
                'configuration_id': 'openrouter-paid-qwen36-35b-a3b-on',
                'condition': 'P2', 'reasoning': 'on', 'record_ids': module.FINAL,
                'excluded_failed_ids': ['DEV-033', 'DEV-039', 'DEV-040'],
                'new_output': str(module.OUTPUT), 'original_timing_preserved': False,
                'per_call_reserve_usd': str(module.RESERVE),
                'call_bound_usd': str(module.RESERVE * 20),
                'proposed_partition_cap_usd': str(module.CAP),
                'sources': sources, 'requests': self.requests}
        write(self.root, 'plan.json', plan)
        child = self.root / 'child.jsonl'
        write(self.root, 'child.jsonl', [{'event': 'partition_closed'}], True)
        write(self.root, 'results/openrouter-paid-budget.jsonl',
              [{'event': 'partition_reconciled', 'partition_id': 'test-final20',
                'child_sha256': module.digest(child),
                'known_actual_usd': '0.20', 'unknown_upper_bound_usd': '0'}], True)
        self.manifest = self.root / 'manifest.json'
        write(self.root, 'manifest.json',
              {'version': 'paid-partitions-v1',
               'master_ledger': str(self.root / 'results/openrouter-paid-budget.jsonl'),
               'partitions': [{'id': 'test-final20', 'model': 'qwen/qwen3.6-35b-a3b',
                               'provider': 'akashml/fp8', 'reasoning': 'on', 'cap_usd': '0.64',
                               'child_ledger': str(child)}]})
        self.review = self.root / 'review.json'
        write(self.root, 'review.json',
              {'approved': True, 'suffix_plan_sha256': module.digest(self.root / 'plan.json'),
               'wrapper_sha256': module.digest(self.root / 'controller.py'),
               'budget_manifest_sha256': module.digest(self.manifest),
               'partition_id': 'test-final20',
               'preserved_v2_report_sha256': sources['v2_report']['sha256'],
               'continue_on_known_billing_intrinsic_invalid': True})

    def row(self, number):
        ident = f'DEV-{number:03}'
        return {'id': ident, 'status': 'ok', 'prediction': self.truth[ident],
                'observed_cost_usd': '0.01', 'cost_unknown': False,
                'reserved_cost_usd': str(module.RESERVE), 'elapsed_seconds': 1.0}

    @staticmethod
    def journal(first, last):
        return [{'event': 'started', 'id': f'DEV-{i:03}'} for i in range(first, last + 1)] + [
            {'event': 'terminal'}]

    def save_suffix(self, count, fail_last=False):
        master = self.root / 'results/openrouter-paid-budget.jsonl'
        master_events = module.lines(master)
        master_events[0]['known_actual_usd'] = str(module.Decimal('0.01') * (count - int(fail_last)))
        master_events[0]['unknown_upper_bound_usd'] = str(module.RESERVE if fail_last else module.Decimal(0))
        write(self.root, 'results/openrouter-paid-budget.jsonl', master_events, True)
        rows, events = [], []
        for offset in range(count):
            row = self.row(41 + offset)
            request = json.loads((self.root / self.requests[offset]['file']).read_text())['request']
            request_sha = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
            row.update(attempt_id=f'attempt-{offset}', request=request,
                       request_sha256=request_sha, budget_partition_id='test-final20',
                       requested_model='qwen/qwen3.6-35b-a3b', reasoning_effort='on',
                       quantization='fp8', reference_labels_read=False,
                       prompt_recovery={'contract': 'qwen36-on-p2-never-sent-final20-v3',
                                        'plan_sha256': module.digest(self.root / 'plan.json'),
                                        'prior_report_sha256':
                                            json.loads((self.root / 'plan.json').read_text())
                                            ['sources']['v2_report']['sha256'],
                                        'review_receipt_sha256': module.digest(self.review)})
            if fail_last and offset == count - 1:
                row.update(status='service_error', prediction=None,
                           http_status=429, cost_unknown=True, observed_cost_usd=None)
            rows.append(row)
            events += [{'event': 'started', 'id': row['id'], 'attempt_id': row['attempt_id'],
                        'request_sha256': request_sha},
                       {'event': 'finished', 'id': row['id'], 'attempt_id': row['attempt_id'],
                        'status': row['status']}]
        write(self.root, 'v3.jsonl', rows, True)
        events.append({'event': 'terminal', 'attempted_records': count, 'planned_records': 20,
                       'completed': count == 20, 'terminal_status': rows[-1]['status'],
                       'plan_sha256': module.digest(self.root / 'plan.json'),
                       'condition': 'P2', 'reasoning': 'on'})
        write(self.root, 'v3.jsonl.attempts.jsonl', events, True)

    def reconcile(self):
        return module.reconcile(self.root, self.manifest, 'test-final20', self.review)

    def test_completed_twenty_preserves_three_failures_and_is_descriptive(self):
        self.save_suffix(20)
        report = self.reconcile()
        self.assertEqual((report['attempted'], report['valid_outputs'], report['never_sent_count']),
                         (60, 57, 0))
        self.assertEqual(report['status_counts'], {'ok': 57, 'service_error': 3})
        self.assertFalse(report['eligible_paired_comparison'])
        self.assertTrue(report['coverage_complete'])
        self.assertEqual(report['cost']['unknown_reserved_upper_bound_usd'],
                         str(module.RESERVE * 3))

    def test_partial_terminal_keeps_never_sent_and_new_failure(self):
        self.save_suffix(2, fail_last=True)
        report = self.reconcile()
        self.assertEqual((report['attempted'], report['never_sent_count']), (42, 18))
        self.assertEqual(report['status_counts']['service_error'], 4)
        self.assertEqual(report['never_sent_ids'][0], 'DEV-043')

    def test_rejects_missing_terminal_and_request_or_predecessor_drift(self):
        self.save_suffix(2)
        journal = self.root / 'v3.jsonl.attempts.jsonl'
        events = module.lines(journal)
        write(self.root, 'v3.jsonl.attempts.jsonl', events[:-1], True)
        with self.assertRaisesRegex(ValueError, 'not terminal'):
            self.reconcile()
        write(self.root, 'v3.jsonl.attempts.jsonl', events, True)
        requests = module.lines(self.root / 'v3.jsonl')
        requests[0]['request']['test_index'] = 99
        write(self.root, 'v3.jsonl', requests, True)
        with self.assertRaisesRegex(ValueError, 'linkage differs'):
            self.reconcile()
        self.save_suffix(2)
        write(self.root, 'v2.jsonl', [self.row(40)], True)
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            self.reconcile()


if __name__ == '__main__':
    unittest.main()
