import hashlib
import json
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import openrouter_budget_v3 as budget_v3
import openrouter_native_variants_v2 as run
import paid_budget_partitions_v3 as partitions


class NativeV2Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'plans'
        self.master = Path(self.temp.name) / 'master.jsonl'
        self.authority = Path(self.temp.name) / 'authority.jsonl'
        ledger = budget_v3.BudgetLedger(self.master)
        ledger.close()
        authority = {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                     'cap_usd': '10.00', 'decision_key': run.AUTHORITY_DECISION_KEY,
                     'approval_sha256': run.AUTHORITY_APPROVAL_SHA}
        self.authority.write_text(json.dumps(authority) + '\n')
        run.prepare(self.base)
        self.config = 'kev-openrouter-native-p1-choice-v1'
        self.manifest = run.verify(self.config, self.base)
        self.p = run.paths(self.base, self.config)

    def allocate(self, *, amount=None):
        self.p['budget'].parent.mkdir(parents=True, exist_ok=True)
        cap = amount or self.manifest['smoke_bound_usd']
        partitions.allocate(self.master, self.p['budget'], [{
            'id': self.manifest['partition_id'], 'cap_usd': cap,
            'model': self.manifest['model'], 'provider': self.manifest['provider_tag'],
            'reasoning': 'none'}])

    def receipt(self):
        identity = run.budget_identity(self.config, self.manifest, self.p['budget'],
                                       base=self.base, master=self.master)
        value = run.expected_receipt(self.config, self.manifest, self.p['budget'],
                                     identity, base=self.base)
        value['global_authority_head_sha256'] = hashlib.sha256(self.authority.read_bytes()).hexdigest()
        self.p['receipt'].write_text(json.dumps(value) + '\n')

    def catalog(self, route):
        return json.loads((ROOT / 'results/route-audits/native-variants-recheck-20261006' /
                           (self.manifest['route'] + '-endpoint.raw.json')).read_text())

    def bodies(self):
        p = ROOT / 'results/route-audits/decision-smoke-20260930/kev-attempts.jsonl'
        rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        return [json.dumps(x['body'], separators=(',', ':')).encode() for x in rows
                if x.get('stage') == 'response'][:3]

    def execute(self, transport):
        return run.execute(self.config, 'smoke', self.p['receipt'], self.p['budget'],
                           base=self.base, master=self.master, authority=self.authority,
                           catalog_fetch=self.catalog, transport=transport, token='fake')

    def test_offline_manifest_binds_frozen_three_requests(self):
        self.assertEqual(self.manifest['smoke_ids'], list(run.IDS))
        self.assertEqual(self.manifest['smoke_bound_usd'], '0.001032192')
        self.assertEqual(self.manifest['full_pass_bound_usd'], '0.020643840')
        self.assertFalse(self.manifest['admission']['full_pass_dispatch_enabled'])
        with self.assertRaisesRegex(ValueError, 'Full-pass dispatch blocked'):
            run.execute(self.config, 'fresh1', None, None, base=self.base)

    def test_smoke_success_and_no_replay(self):
        self.allocate()
        self.receipt()
        responses = iter(self.bodies())
        result = self.execute(lambda _payload, _token: (200, next(responses)))
        self.assertEqual(result['valid_count'], 3)
        self.assertEqual([json.loads(x)['stage'] for x in
                          (self.p['stage'] / 'attempts.jsonl').read_text().splitlines()],
                         ['reserved', 'started', 'response', 'parsed'] * 3)
        self.assertEqual(len(self.authority.read_text().splitlines()), 2)
        with self.assertRaises(FileExistsError):
            self.execute(lambda *_: self.fail('replayed'))

    def test_unknown_transport_retains_reservation_and_hold(self):
        self.allocate()
        self.receipt()
        def fail(*_):
            raise TimeoutError('simulated unknown')
        with self.assertRaises(TimeoutError):
            self.execute(fail)
        child = self.p['budget'].parent / ('budget-' + self.manifest['partition_id'] + '.jsonl')
        rows = [json.loads(x) for x in child.read_text().splitlines()]
        self.assertEqual([x['event'] for x in rows], ['budget', 'reserve'])
        self.assertEqual(len(self.authority.read_text().splitlines()), 2)
        self.assertFalse((self.p['stage'] / 'completion.json').exists())
        with self.assertRaises(FileExistsError):
            self.execute(fail)

    def test_cap_and_receipt_drift_fail_before_hold(self):
        self.allocate(amount='0.0001')
        with self.assertRaises(ValueError):
            run.budget_identity(self.config, self.manifest, self.p['budget'],
                                base=self.base, master=self.master)
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)

    def test_route_drift_fails_before_hold(self):
        self.allocate()
        self.receipt()
        def drift(route):
            value = self.catalog(route)
            value['data']['endpoints'][0]['pricing']['prompt'] = '0.000000043'
            return value
        with self.assertRaisesRegex(ValueError, 'Price changed'):
            run.execute(self.config, 'smoke', self.p['receipt'], self.p['budget'],
                        base=self.base, master=self.master, authority=self.authority,
                        catalog_fetch=drift, transport=lambda *_: self.fail('sent'), token='fake')
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)

    def test_authority_hold_is_idempotent_and_cap_checked(self):
        original_head = hashlib.sha256(self.authority.read_bytes()).hexdigest()
        hold_id = self.manifest['global_hold_id']
        amount = Decimal(self.manifest['smoke_bound_usd'])
        run.hold_authority(self.authority, hold_id, amount, 'a' * 64,
                           original_head, stage_path=self.p['stage'])
        run.hold_authority(self.authority, hold_id, amount, 'a' * 64,
                           original_head, stage_path=self.p['stage'])
        self.assertEqual(len(self.authority.read_text().splitlines()), 2)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            run.hold_authority(self.authority, hold_id, amount, 'b' * 64,
                               original_head, stage_path=self.p['stage'])
        with self.assertRaisesRegex(ValueError, 'cap exhausted'):
            run.hold_authority(self.authority, 'other-stage', Decimal('10'), 'c' * 64,
                               hashlib.sha256(self.authority.read_bytes()).hexdigest(),
                               stage_path=self.p['stage'])

    def test_second_plan_build_drift_stops_before_hold_or_reserve(self):
        self.allocate()
        self.receipt()
        original = run.frozen.build_plan(ROOT)
        changed = deepcopy(original)
        item = changed[self.config]['requests'][0]
        item['payload']['state']['feedback'] += ' changed after review'
        item['payload_sha256'] = run.sha(run.decision.canonical(item['payload']))
        changed[self.config]['requests_sha256'] = run.sha(
            run.decision.canonical(changed[self.config]['requests']))
        with mock.patch.object(run.frozen, 'build_plan', side_effect=[original, changed]) as builder:
            with self.assertRaisesRegex(ValueError, 'Current input requests differ'):
                self.execute(lambda *_: self.fail('transport called'))
        self.assertEqual(builder.call_count, 2)
        child = self.p['budget'].parent / ('budget-' + self.manifest['partition_id'] + '.jsonl')
        self.assertEqual([json.loads(x)['event'] for x in child.read_text().splitlines()],
                         ['budget'])
        self.assertEqual(len(self.authority.read_text().splitlines()), 1)
        self.assertFalse(self.p['stage'].exists())


if __name__ == '__main__':
    unittest.main()
