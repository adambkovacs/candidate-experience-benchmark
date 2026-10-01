"""Offline gates for the Qwen27 same-route interrupted continuation."""
import base64
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen27_v2_interruption_continuation as c


class ContinuationTests(unittest.TestCase):
    def test_exact_never_sent_suffix_and_original_payloads(self):
        for kind, first, count in (('medium', 'DEV-023', 38), ('xhigh', 'DEV-038', 23)):
            config = 'openrouter-paid-qwen3.8-27b-' + kind
            with self.subTest(kind=kind):
                old, sources = c.verify_old(config)
                self.assertEqual(old['failedId'], 'DEV-022' if kind == 'medium' else 'DEV-037')
                self.assertIn(kind + '_smoke_review', sources)
                self.assertIn(kind + '_development_responses', sources)
                chosen = c.selected_requests(config, 'fresh3', 'P0', 'suffix')
                plan = c.study.verify(config, 'fresh3', c.PLANS[kind])
                original = plan['conditions']['P0']['development']
                self.assertEqual(len(chosen), count)
                self.assertEqual([r['record_id'] for r in chosen],
                                 [f'DEV-{n:03d}' for n in range(int(first[-3:]), 61)])
                self.assertEqual(chosen, original[-count:])
                self.assertEqual(len(c.selected_requests(config, 'fresh3', 'P1', 'smoke')), 3)
                self.assertEqual(len(c.selected_requests(config, 'fresh3', 'P1', 'development')), 60)
                with self.assertRaises(ValueError):
                    c.selected_requests(config, 'fresh3', 'P2', 'development')

    def test_source_drift_and_label_marker_rejected(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        with patch.dict(c.OLD['medium'], {'child': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                c.verify_old(config)
        real = c.interrupted.build

        def changed():
            report = real()
            report['series']['medium']['valid'] = 22
            return report

        with patch.object(c.interrupted, 'build', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'accounting differs'):
                c.verify_old(config)

    def test_distinct_budget_allocation_and_terminal_state(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            budget = root / 'budget.json'
            child = root / 'budget-qwen27-medium-v2-interruption-v1.jsonl'
            master = root / 'master.jsonl'
            item = {'id': 'qwen27-medium-v2-interruption-v1', 'cap_usd': '0.10',
                    'child_ledger': str(child), 'model': c.study.MODEL,
                    'provider': c.study.PROVIDER,
                    'reasoning': c.study.CONFIGS[config]['effort']}
            budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                'master_ledger': str(master), 'partitions': [item]}) + '\n')
            child.write_text(json.dumps({'event': 'budget', 'cap_usd': '0.10'}) + '\n')
            allocation = {'event': 'budget_partition', 'partition_id': item['id'],
                'allocated_usd': '0.10', 'manifest_path': str(budget),
                'manifest_sha256': c.study.sha(budget), 'child_ledger': str(child),
                'model': c.study.MODEL, 'provider': c.study.PROVIDER,
                'reasoning': item['reasoning']}
            master.write_text(json.dumps(allocation) + '\n')
            with patch.object(c, 'folder', return_value=root), patch.object(c, 'MASTER', master):
                self.assertEqual(c.budget_entry(config, budget, require_fresh=True), item)
                child.write_text(child.read_text() + json.dumps({'event': 'partition_closed'}) + '\n')
                with self.assertRaisesRegex(ValueError, 'closure.*reconciliation'):
                    c.budget_entry(config, budget)
                master.write_text(master.read_text() + json.dumps({
                    'event': 'partition_reconciled', 'partition_id': item['id']}) + '\n')
                self.assertEqual(c.budget_entry(config, budget), item)
                with self.assertRaisesRegex(ValueError, 'spent or reconciled'):
                    c.budget_entry(config, budget, require_fresh=True)

    def test_fake_transport_durable_known_settlement_and_duplicate_refusal(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        old = c.rows(c.study.BASE / config / 'fresh3/P0/development.attempts.jsonl')[0]
        body = old['raw_response']
        request = c.selected_requests(config, 'fresh3', 'P0', 'suffix')[0]
        model, endpoint = old['model_catalog_entry'], old['provider_endpoint']

        class Ledger:
            cap = Decimal('0.10')
            master_cap = Decimal('12.38')
            closed = False
            def __init__(self):
                self.cost = Decimal(0)
                self.closed_called = False
            def state(self):
                return Decimal(0), {}, False
            def accounted(self):
                return self.cost
            def reserve(self, bound, rid):
                self.cost += bound
                return 'fake-attempt-1'
            def settle(self, attempt, actual):
                self.cost += actual - c.RESERVE
                return actual is not None
            def close(self):
                self.closed_called = True

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            review = root / 'review.json'
            review.write_text('{}\n')
            ledger = Ledger()
            manifest = {'series_id': 'fake-continuation', 'configuration_id': config,
                'source_bindings': {'new_budget_manifest': {'path': 'dummy', 'sha256': 'a'}},
                'partition_id': 'qwen27-medium-v2-interruption-v1', 'child_cap_usd': '0.10'}
            calls = []

            def fake_fetch(payload, token, timeout, output, rid, attempt, request_sha):
                calls.append(rid)
                c.paid.durable(output, {'id': rid, 'attempt_id': attempt,
                    'request_sha256': request_sha, 'http_status': 200,
                    'body_base64': base64.b64encode(json.dumps(body).encode()).decode(),
                    'body_truncated_at_limit': False, 'read_error': None})
                return body

            with patch.object(c, 'folder', return_value=root), \
                 patch.object(c, 'verify_manifest', return_value=manifest), \
                 patch.object(c, 'require_order'), patch.object(c, 'verify_review'), \
                 patch.object(c.study, 'verify', return_value={'configuration_id': config}), \
                 patch.object(c, 'selected_requests', return_value=[request]), \
                 patch.object(c.original, 'live_controls', return_value=(model, endpoint, c.RESERVE)) as live, \
                 patch.object(c, 'bound', return_value=root / 'budget.json'), \
                 patch.object(c, 'budget_entry', return_value={'child_ledger': str(root / 'child.jsonl')}), \
                 patch.object(c.partitions, 'open_partition', return_value=ledger), \
                 patch.object(c.paid, 'load_key', return_value='fake-token'), \
                 patch.object(c.original, 'fetch_recorded', side_effect=fake_fetch):
                self.assertTrue(c.execute(config, 'manifest-hash', 'fresh3', 'P0',
                                          'suffix', review))
                self.assertTrue(ledger.closed_called)
                self.assertEqual(live.call_count, 2)
                self.assertEqual(calls, ['DEV-023'])
                files = c.stage_files(config, 'fresh3', 'P0', 'suffix')
                self.assertEqual(c.rows(files['journal'])[-1]['event'], 'phase_completed')
                self.assertEqual(c.rows(files['attempts'])[0]['status'], 'ok')
                self.assertFalse(c.rows(files['attempts'])[0]['reference_labels_read'])
                with self.assertRaises(FileExistsError):
                    c.execute(config, 'manifest-hash', 'fresh3', 'P0', 'suffix', review)
                self.assertEqual(calls, ['DEV-023'])

    def test_unknown_cost_stops_before_next_request(self):
        config = 'openrouter-paid-qwen3.8-27b-xhigh'
        old = c.rows(c.study.BASE / config / 'fresh3/P0/development.attempts.jsonl')[0]
        selected = c.selected_requests(config, 'fresh3', 'P0', 'suffix')[:2]

        class Ledger:
            cap = Decimal('0.10')
            master_cap = Decimal('12.38')
            closed = False
            def state(self):
                return {}, set(), False
            def accounted(self):
                return Decimal(0)
            def reserve(self, bound, rid):
                return 'unknown-attempt'
            def settle(self, attempt, actual):
                self.actual = actual
                return False
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            receipt = root / 'review.json'
            receipt.write_text('{}\n')
            ledger = Ledger()
            manifest = {'series_id': 'fake-xhigh', 'configuration_id': config,
                'source_bindings': {'new_budget_manifest': {'path': 'dummy'}},
                'partition_id': 'qwen27-xhigh-v2-interruption-v1', 'child_cap_usd': '0.10'}
            with patch.object(c, 'folder', return_value=root), \
                 patch.object(c, 'verify_manifest', return_value=manifest), \
                 patch.object(c, 'require_order'), patch.object(c, 'verify_review'), \
                 patch.object(c.study, 'verify', return_value={'configuration_id': config}), \
                 patch.object(c, 'selected_requests', return_value=selected), \
                 patch.object(c.original, 'live_controls', return_value=(
                     old['model_catalog_entry'], old['provider_endpoint'], c.RESERVE)) as live, \
                 patch.object(c, 'bound', return_value=root / 'budget.json'), \
                 patch.object(c, 'budget_entry', return_value={}), \
                 patch.object(c.partitions, 'open_partition', return_value=ledger), \
                 patch.object(c.paid, 'load_key', return_value='fake-token'), \
                 patch.object(c.original, 'fetch_recorded', side_effect=TimeoutError) as fetch:
                self.assertFalse(c.execute(config, 'manifest-hash', 'fresh3', 'P0',
                                           'suffix', receipt))
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(live.call_count, 2)
                files = c.stage_files(config, 'fresh3', 'P0', 'suffix')
                attempts = c.rows(files['attempts'])
                self.assertEqual([r['id'] for r in attempts], ['DEV-038'])
                self.assertIsNone(ledger.actual)
                self.assertTrue(attempts[0]['cost_unknown'])
                self.assertEqual(c.rows(files['journal'])[-1]['event'], 'phase_stopped')
                self.assertEqual(c.rows(files['responses']), [])


if __name__ == '__main__':
    unittest.main()
