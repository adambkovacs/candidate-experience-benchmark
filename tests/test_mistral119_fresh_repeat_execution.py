"""Offline exact-route, receipt, budget, and raw-evidence checks for Mistral119."""
import base64
from decimal import Decimal
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as wrapped
import openrouter_budget_v2 as budgets
import paid_budget_partitions_v2 as partitions
import qwen27_fresh_repeat_execution as canonical

run = wrapped.runner
PREDICTION = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}


class FakeResponse:
    def __init__(self, body):
        self.body = io.BytesIO(body)
        self.status = 200
        self.headers = {'content-type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.body.close()

    def read(self, limit):
        return self.body.read(limit)


class Mistral119ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.config = 'openrouter-paid-mistral-small4-119b-none'
        self.plan = study.plan_data(self.config, 'fresh1')
        self.original, _ = study.historical(self.config)
        self.endpoint = self.original['provider_endpoint']
        self.model = self.original['model_catalog_entry']

    def response(self, cost='0.0001'):
        return {'model': study.MODEL, 'provider': study.PROVIDER_NAME,
                'usage': {'cost': cost, 'prompt_tokens': 100, 'completion_tokens': 20},
                'choices': [{'finish_reason': 'stop',
                             'message': {'content': json.dumps(PREDICTION)}}]}

    def fixture(self, temp, cap='0.15'):
        root = Path(temp)
        base = root / 'plans'
        original = study.BASE / self.config / 'fresh1/manifest.json'
        plan_file = base / self.config / 'fresh1/manifest.json'
        plan_file.parent.mkdir(parents=True)
        shutil.copy2(original, plan_file)
        master = root / 'master.jsonl'
        budget = root / 'budget.json'
        partition_id = 'mistral119-test'
        allocated = partitions.allocate(master, budget, [{
            'id': partition_id, 'cap_usd': cap, 'model': study.MODEL,
            'provider': study.PROVIDER, 'reasoning': study.CONFIGS[self.config]['effort'],
        }])
        child = Path(allocated['partitions'][0]['child_ledger'])
        return root, base, plan_file, master, budget, child, partition_id

    def receipt(self, root, master, budget, pid, phase, cap='0.15'):
        review = root / f'{phase}-review.json'
        data = {'schema': wrapped.RECEIPT_SCHEMA, 'approved': True,
                'configuration_id': self.config, 'stage': f'fresh1/P0/{phase}',
                'controller_sha256': study.sha(wrapped.__file__),
                'execution_manifest_sha256': study.sha(run.EXECUTION_MANIFEST),
                'plan_sha256': wrapped.execution_plan()['plans_sha256'][self.config],
                'master_ledger': str(master.resolve()),
                'budget_manifest': {'path': budget.name, 'sha256': study.sha(budget)},
                'partition_id': pid, 'partition_cap_usd': cap}
        review.write_text(json.dumps(data) + '\n')
        return review

    def stage(self, root, base, master, review, phase, responses, key_expected=True):
        items = iter(responses)

        def opener(request, timeout):
            self.assertEqual(request.full_url, run.transport.BASE + '/chat/completions')
            self.assertEqual(timeout, study.TIMEOUT)
            item = next(items)
            if isinstance(item, Exception):
                raise item
            return FakeResponse(item if isinstance(item, bytes) else json.dumps(item).encode())

        key = 'fake-key' if key_expected else None
        key_patch = patch.object(run.paid, 'load_key', return_value=key) if key_expected else \
            patch.object(run.paid, 'load_key', side_effect=AssertionError('key must not be read'))
        with patch.object(wrapped._Study, 'BASE', base), \
             patch.object(wrapped._Study, 'verify', return_value=self.plan), \
             patch.object(run, 'ROOT', root), patch.object(run, 'MASTER', master), \
             patch.object(run, 'live_controls', return_value=(self.model, self.endpoint, study.RESERVE)), \
             key_patch, \
             patch.object(run.transport.OPENER, 'open', side_effect=opener), \
             patch.object(run, 'audit_response', return_value={'passed': True, 'blockers': []}):
            return run.execute(self.config, 'fresh1', 'P0', phase,
                               study.sha(base / self.config / 'fresh1/manifest.json'), review)

    def test_private_import_and_execution_manifest_bind_six_plans(self):
        self.assertIsNot(run, canonical)
        self.assertNotIn(self.config, canonical.study.CONFIGS)
        expected = wrapped.execution_plan()
        self.assertEqual(expected['funding_status'], 'unfunded_no_whole_series_cap_proposed')
        self.assertEqual([len(passes) for passes in expected['plans_sha256'].values()], [3, 3])
        self.assertIn('qwen27_fresh_repeat_execution.py', expected['source_code_sha256'])
        self.assertEqual(run.verify_execution_manifest(study.sha(run.EXECUTION_MANIFEST)), expected)

    def test_both_exact_live_routes_and_efforts_reject_endpoint_drift(self):
        for config in study.CONFIGS:
            plan = study.plan_data(config, 'fresh1')
            original, _ = study.historical(config)
            endpoint = original['provider_endpoint']
            model = original['model_catalog_entry']
            catalog = {'data': [model]}
            endpoints = {'data': {'id': study.MODEL, 'endpoints': [endpoint]}}
            with self.subTest(config=config), patch.object(run.paid, 'fetch', side_effect=[catalog, endpoints]):
                _, selected, reserve = wrapped.live_controls(plan, 'P0')
                self.assertEqual(selected, endpoint)
                self.assertEqual(reserve, study.RESERVE)
            altered = json.loads(json.dumps(endpoint))
            altered['max_completion_tokens'] = 1
            with patch.object(run.paid, 'fetch', side_effect=[catalog, {'data': {'id': study.MODEL, 'endpoints': [altered]}}]):
                with self.assertRaises(ValueError):
                    wrapped.live_controls(plan, 'P0')

    def test_real_child_smoke_inspection_development_and_no_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, plan_file, master, budget, child, pid = self.fixture(temp)
            smoke_review = self.receipt(root, master, budget, pid, 'smoke')
            self.assertTrue(self.stage(root, base, master, smoke_review, 'smoke', [self.response()] * 3))
            with patch.object(wrapped._Study, 'BASE', base), \
                 patch.object(wrapped._Study, 'verify', return_value=self.plan):
                with self.assertRaisesRegex(ValueError, 'Inspected smoke required'):
                    run.require_order(self.plan, 'P0', 'development')
                run.inspect(self.config, 'fresh1', 'P0', study.sha(plan_file),
                            'Inspected three known-billed raw responses.')
                run.require_order(self.plan, 'P0', 'development')
            dev_review = self.receipt(root, master, budget, pid, 'development')
            self.assertTrue(self.stage(root, base, master, dev_review, 'development',
                                       [self.response()] * 60))
            with patch.object(wrapped._Study, 'BASE', base), \
                 patch.object(wrapped._Study, 'verify', return_value=self.plan):
                run.verify_phase_closure(self.plan, 'P0', 'development')
            with self.assertRaises(FileExistsError):
                self.stage(root, base, master, dev_review, 'development', [self.response()] * 60)
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('0.15'))
            try:
                self.assertEqual(ledger.accounted(), Decimal('0.0063'))
                self.assertEqual(ledger.state()[1], set())
                self.assertEqual(len([x for x in ledger.events if x['event'] == 'reserve']), 63)
            finally:
                ledger.close()

    def test_malformed_200_preserves_raw_unknown_reserve_without_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, _, master, budget, child, pid = self.fixture(temp)
            review = self.receipt(root, master, budget, pid, 'smoke')
            malformed = b'{"choices": [broken'
            self.assertFalse(self.stage(root, base, master, review, 'smoke', [malformed]))
            folder = base / self.config / 'fresh1/P0'
            raw = run.jsonl(folder / 'smoke.responses.jsonl')[0]
            self.assertEqual(base64.b64decode(raw['body_base64']), malformed)
            attempt = run.jsonl(folder / 'smoke.attempts.jsonl')[0]
            self.assertTrue(attempt['cost_unknown'])
            self.assertEqual(attempt['error_type'], 'JSONDecodeError')
            ledger = budgets.BudgetLedger(child, cap_limit=Decimal('0.15'))
            try:
                self.assertEqual(ledger.accounted(), study.RESERVE)
                self.assertEqual(len(ledger.state()[1]), 1)
            finally:
                ledger.close()
            with self.assertRaises(FileExistsError):
                self.stage(root, base, master, review, 'smoke', [self.response()] * 3)

    def test_receipt_cap_and_effort_must_match_actual_allocation_before_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, _, master, budget, _, pid = self.fixture(temp)
            review = self.receipt(root, master, budget, pid, 'smoke', cap='0.16')
            with self.assertRaisesRegex(ValueError, 'cap must exactly match'):
                self.stage(root, base, master, review, 'smoke', [], key_expected=False)
            folder = base / self.config / 'fresh1/P0'
            self.assertFalse((folder / 'smoke.claim.json').exists())
            review = self.receipt(root, master, budget, pid, 'smoke', cap='0.15')
            data = json.loads(review.read_text())
            data['configuration_id'] = 'openrouter-paid-mistral-small4-119b-high'
            review.write_text(json.dumps(data) + '\n')
            with self.assertRaisesRegex(ValueError, 'stage or configuration'):
                self.stage(root, base, master, review, 'smoke', [], key_expected=False)

    def test_real_child_lock_blocks_duplicate_before_key_and_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root, base, _, master, budget, child, pid = self.fixture(temp)
            review = self.receipt(root, master, budget, pid, 'smoke')
            held = budgets.BudgetLedger(child, cap_limit=Decimal('0.15'))
            try:
                with self.assertRaises(BlockingIOError):
                    self.stage(root, base, master, review, 'smoke', [], key_expected=False)
                self.assertFalse((base / self.config / 'fresh1/P0/smoke.claim.json').exists())
            finally:
                held.close()


if __name__ == '__main__':
    unittest.main()
