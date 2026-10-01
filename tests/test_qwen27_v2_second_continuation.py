"""Offline admission and route gates for the separate Qwen27 successor."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import qwen27_v2_second_continuation as c


class SecondContinuationTests(unittest.TestCase):
    def test_sealed_prefixes_and_exact_never_sent_membership(self):
        expected = {'medium': (16, 'DEV-039', 22),
                    'xhigh': (8, 'DEV-009', 52)}
        for kind, (settled, first_id, count) in expected.items():
            config = 'openrouter-paid-qwen3.8-27b-' + kind
            with self.subTest(kind=kind):
                sources = c.verify_first_stop(config)
                self.assertGreaterEqual(len(sources), 8)
                rows = c.rows(c.first.stage_files(config, *c.FIRST_STOP[kind]['stage'])['attempts'])
                self.assertEqual(len(rows), settled)
                self.assertTrue(all(x['status'] == 'ok' and x['billing_ok'] and
                                    x['cost_unknown'] is False for x in rows))
                selected = c.selected_requests(config, *c.stages(config)[0])
                self.assertEqual(len(selected), count)
                self.assertEqual(selected[0]['record_id'], first_id)
                self.assertEqual(selected[-1]['record_id'], 'DEV-060')
                plan = c.study.verify(config, 'fresh3', c.PLANS[kind])
                self.assertEqual(selected, plan['conditions'][c.stages(config)[0][1]]['development'][-count:])
        medium = 'openrouter-paid-qwen3.8-27b-medium'
        self.assertEqual(len(c.selected_requests(medium, 'fresh3', 'P1', 'smoke')), 3)
        self.assertEqual(len(c.selected_requests(medium, 'fresh3', 'P1', 'development')), 60)
        with self.assertRaisesRegex(ValueError, 'outside second continuation'):
            c.selected_requests('openrouter-paid-qwen3.8-27b-xhigh',
                                'fresh3', 'P0', 'suffix')

    def test_tampered_first_seal_or_reconciliation_rejected(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        for key in ('child', 'journal', 'reconciliation'):
            with self.subTest(key=key), patch.dict(c.FIRST_STOP['medium'], {key: '0'*64}):
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    c.verify_first_stop(config)

    def test_new_child_must_have_distinct_allocation_and_terminal_reconciliation(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            budget = directory / 'budget.json'
            master = directory / 'master.jsonl'
            pid = 'qwen27-medium-v2-interruption-v2'
            child = directory / ('budget-' + pid + '.jsonl')
            item = {'id': pid, 'cap_usd': '0.20', 'child_ledger': str(child),
                    'model': c.study.MODEL, 'provider': c.study.PROVIDER,
                    'reasoning': c.study.CONFIGS[config]['effort']}
            budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                'master_ledger': str(master), 'partitions': [item]}) + '\n')
            child.write_text(json.dumps({'event': 'budget', 'cap_usd': '0.20'}) + '\n')
            allocation = {'event': 'budget_partition', 'partition_id': pid,
                'allocated_usd': '0.20', 'manifest_path': str(budget),
                'manifest_sha256': c.study.sha(budget), 'child_ledger': str(child),
                'model': c.study.MODEL, 'provider': c.study.PROVIDER,
                'reasoning': item['reasoning']}
            master.write_text(json.dumps(allocation) + '\n')
            with patch.object(c, 'folder', return_value=directory), \
                 patch.object(c, 'MASTER', master):
                self.assertEqual(c.budget_entry(config, budget, require_fresh=True), item)
                child.write_text(child.read_text() + json.dumps({'event': 'partition_closed'}) + '\n')
                with self.assertRaisesRegex(ValueError, 'closure.*reconciliation'):
                    c.budget_entry(config, budget)
                master.write_text(master.read_text() + json.dumps({
                    'event': 'partition_reconciled', 'partition_id': pid}) + '\n')
                self.assertEqual(c.budget_entry(config, budget), item)
                with self.assertRaisesRegex(ValueError, 'spent or reconciled'):
                    c.budget_entry(config, budget, require_fresh=True)
                item['id'] = 'qwen27-medium-v2-interruption-v1'
                budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                    'master_ledger': str(master), 'partitions': [item]}) + '\n')
                with self.assertRaisesRegex(ValueError, 'allocation differs|route, cap or identity differs'):
                    c.budget_entry(config, budget)

    def test_rolling_uptime_is_observed_but_not_an_experimental_change(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        plan = c.study.verify(config, 'fresh3', c.PLANS['medium'])
        old = c.rows(c.study.BASE / config / 'fresh3/P0/development.attempts.jsonl')[0]
        model = old['model_catalog_entry']
        endpoint = copy.deepcopy(old['provider_endpoint'])
        endpoint['uptime_last_5m'] = -1
        endpoints = {'data': {'id': c.study.MODEL, 'endpoints': [endpoint]}}
        with tempfile.TemporaryFile(mode='w+t') as journal, patch.object(
                c.paid, 'fetch', side_effect=[{'data': [model]}, endpoints]):
            got_model, got_endpoint, reserve = c.checked_live_controls(
                plan, 'P0', journal, 'DEV-039')
            self.assertEqual((got_model, got_endpoint, reserve),
                             (model, endpoint, c.RESERVE))
            journal.seek(0)
            events = [json.loads(line) for line in journal]
            self.assertEqual([x['event'] for x in events], ['route_observed'])
            self.assertEqual(events[0]['provider_endpoints'], [endpoint])

    def test_route_change_is_recorded_before_request_or_reserve(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        plan = c.study.verify(config, 'fresh3', c.PLANS['medium'])
        old = c.rows(c.study.BASE / config / 'fresh3/P0/development.attempts.jsonl')[0]
        model = old['model_catalog_entry']
        endpoint = copy.deepcopy(old['provider_endpoint'])
        endpoint['context_length'] += 1
        endpoints = {'data': {'id': c.study.MODEL, 'endpoints': [endpoint]}}
        with tempfile.TemporaryFile(mode='w+t') as journal, patch.object(
                c.paid, 'fetch', side_effect=[{'data': [model]}, endpoints]):
            with self.assertRaisesRegex(ValueError, 'experimental endpoint fields differ'):
                c.checked_live_controls(plan, 'P0', journal, 'DEV-039')
            journal.seek(0)
            events = [json.loads(line) for line in journal]
            self.assertEqual([x['event'] for x in events],
                             ['route_observed', 'route_rejected'])
            self.assertEqual(events[1]['changed_experimental_fields'], ['context_length'])
            self.assertEqual(events[0]['provider_endpoints'], [endpoint])

    def test_price_rejection_retains_observed_price_even_if_selector_raises(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        plan = c.study.verify(config, 'fresh3', c.PLANS['medium'])
        old = c.rows(c.study.BASE / config / 'fresh3/P0/development.attempts.jsonl')[0]
        endpoint = copy.deepcopy(old['provider_endpoint'])
        endpoint['pricing']['prompt'] = '1'
        endpoints = {'data': {'id': c.study.MODEL, 'endpoints': [endpoint]}}
        with tempfile.TemporaryFile(mode='w+t') as journal, patch.object(
                c.paid, 'fetch', side_effect=[{'data': [old['model_catalog_entry']]}, endpoints]):
            with self.assertRaises(ValueError):
                c.checked_live_controls(plan, 'P0', journal, 'DEV-039')
            journal.seek(0)
            events = [json.loads(line) for line in journal]
            self.assertEqual([x['event'] for x in events],
                             ['route_observed', 'route_rejected'])
            self.assertIn('pricing', events[0]['changed_experimental_fields'])
            self.assertIn('pricing', events[1]['changed_experimental_fields'])
            self.assertEqual(events[0]['provider_endpoints'], [endpoint])

    def test_pre_send_route_abort_never_reserves_or_replays(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        request = c.selected_requests(config, 'fresh3', 'P0', 'suffix')[0]

        class Ledger:
            cap = Decimal('0.20')
            master_cap = Decimal('12.38')
            closed = False
            reserves = 0
            def state(self):
                return {}, {}, False
            def accounted(self):
                return Decimal(0)
            def reserve(self, *args):
                self.reserves += 1
                raise AssertionError('No reserve is allowed on route rejection')
            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            review = directory / 'review.json'
            review.write_text('{}\n')
            ledger = Ledger()
            manifest = {'series_id': c.SCHEMA + '-medium',
                        'configuration_id': config,
                        'source_bindings': {'new_budget_manifest': {'path': 'dummy'}},
                        'partition_id': 'qwen27-medium-v2-interruption-v2',
                        'child_cap_usd': '0.20'}

            def reject(plan, condition, journal, rid):
                c.paid.durable(journal, {'event': 'route_observed', 'id': rid,
                    'model_catalog_entries': [], 'provider_endpoints': []})
                c.paid.durable(journal, {'event': 'route_rejected', 'id': rid,
                    'changed_experimental_fields': ['pricing']})
                raise ValueError('Live experimental endpoint fields differ: pricing')

            with patch.object(c, 'folder', return_value=directory), \
                 patch.object(c, 'verify_manifest', return_value=manifest), \
                 patch.object(c, 'verify_runtime_sources'), \
                 patch.object(c, 'require_order'), patch.object(c, 'verify_review'), \
                 patch.object(c.study, 'verify', return_value={'configuration_id': config}), \
                 patch.object(c, 'selected_requests', return_value=[request]), \
                 patch.object(c, 'bound', return_value=directory / 'budget.json'), \
                 patch.object(c, 'budget_entry', return_value={}), \
                 patch.object(c.partitions, 'open_partition', return_value=ledger), \
                 patch.object(c.paid, 'load_key', return_value='fake-token'), \
                 patch.object(c, 'checked_live_controls', side_effect=reject):
                with self.assertRaisesRegex(ValueError, 'experimental endpoint fields differ'):
                    c.execute(config, 'fake-sha', 'fresh3', 'P0', 'suffix', review)
                events = c.rows(c.stage_files(config, 'fresh3', 'P0', 'suffix')['journal'])
                self.assertEqual([e['event'] for e in events],
                    ['phase_started', 'route_observed', 'route_rejected', 'phase_aborted'])
                self.assertEqual(ledger.reserves, 0)
                self.assertTrue(ledger.closed)
                self.assertEqual(c.rows(c.stage_files(config, 'fresh3', 'P0', 'suffix')['attempts']), [])
                with self.assertRaises(FileExistsError):
                    c.execute(config, 'fake-sha', 'fresh3', 'P0', 'suffix', review)


if __name__ == '__main__':
    unittest.main()
