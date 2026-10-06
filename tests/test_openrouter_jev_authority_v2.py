import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_jev_authority_v2 as bridge
import openrouter_budget_v3 as budget_v3
import paid_budget_partitions_v3 as partitions


class JevAuthorityV2Test(unittest.TestCase):
    def test_tail_is_exact_unsent_suffix_and_parent_unknown_is_retained(self):
        manifest = bridge.tail_manifest()
        requests = bridge.frozen.build_plan()[bridge.suffix.CONFIG]['requests']
        self.assertEqual(manifest['ids'], [x['id'] for x in requests[18:]])
        self.assertEqual(manifest['request_sha256'],
                         [x['payload_sha256'] for x in requests[18:]])
        self.assertEqual(len(manifest['ids']), 42)
        self.assertEqual(manifest['ids'][0], 'DEV-019')
        self.assertEqual(manifest['ids'][-1], 'DEV-060')
        self.assertNotIn('DEV-018', manifest['ids'])
        self.assertEqual(manifest['whole_pass_bound_usd'], '0.056448000')
        self.assertEqual(manifest['parent_evidence']['unknown_attempted_id'], 'DEV-018')
        self.assertEqual(manifest['parent_evidence']['unknown_charge_upper_bound_usd'],
                         '0.001344000')
        self.assertFalse(manifest['continuation_is_clean_repeat'])
        prior = bridge._tail_predecessor(bridge.suffix.CONFIG, bridge.TAIL_STAGE,
                                         manifest)
        self.assertEqual(prior['parent_terminal_sha256'],
                         bridge.suffix.PINNED['terminal-public.json'])
        self.assertFalse(prior['clean_repeat_credit'])

    def test_core_copy_uses_v2_hold_without_mutating_frozen_modules(self):
        old_writer = bridge.smoke_v2.hold_authority
        old_expected = bridge.full.expected_receipt
        tail = bridge._tail_core()
        future = bridge._full_core(bridge.jev.CONFIGS[0])
        self.assertIs(tail.smoke_v2.hold_authority, bridge.authority_v2.hold_authority)
        self.assertIs(future.smoke_v2.hold_authority, bridge.authority_v2.hold_authority)
        self.assertIs(bridge.smoke_v2.hold_authority, old_writer)
        self.assertIs(bridge.full.expected_receipt, old_expected)
        self.assertIsNot(tail, future)
        self.assertEqual(tail.IDS, bridge.suffix.IDS)
        self.assertEqual(bridge.full.IDS, [f'DEV-{i:03d}' for i in range(1, 61)])

    def test_real_allocator_accepts_exact_tail_partition_on_temp_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'tail'
            master = Path(tmp) / 'master.jsonl'
            bridge.prepare_tail(base=base)
            manifest = bridge.verify_tail(base=base)
            p = bridge.full.paths(base, bridge.suffix.CONFIG, bridge.TAIL_STAGE)
            budget_v3.BudgetLedger(master).close()
            partition_id = manifest['passes'][0]['partition_id']
            self.assertEqual(partition_id, bridge.TAIL_PARTITION)
            self.assertIn('dev019-060', partition_id)
            budget = partitions.allocate(master, p['budget'], [{
                'id': partition_id,
                'cap_usd': manifest['whole_pass_bound_usd'],
                'model': manifest['model'],
                'provider': manifest['provider_tag'],
                'reasoning': 'none'}])
            self.assertEqual(budget['partitions'][0]['id'], partition_id)
            self.assertEqual(budget['partitions'][0]['cap_usd'], '0.056448000')
            self.assertTrue(Path(budget['partitions'][0]['child_ledger']).is_file())
            self.assertEqual(len(bridge._tail_core(base=base).budget_identity(
                bridge.suffix.CONFIG, bridge.TAIL_STAGE, manifest, p['budget'],
                base=base, master=master)), 64)

    def test_receipt_binds_bridge_authority_frozen_sources_and_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'tail'
            bridge.prepare_tail(base=base)
            core = bridge._tail_core(base=base)
            manifest = bridge.verify_tail(base=base)
            budget = Path(tmp) / 'budget.json'
            budget.write_text('{}\n')
            receipt = core.expected_receipt(
                bridge.suffix.CONFIG, bridge.TAIL_STAGE, manifest, budget,
                'a'*64, 'b'*64, bridge._tail_predecessor(
                    bridge.suffix.CONFIG, bridge.TAIL_STAGE, manifest), 'c'*64,
                base=base)
            self.assertEqual(receipt['bridge_sha256'], bridge._digest(bridge.__file__))
            self.assertEqual(receipt['authority_module_sha256'],
                             bridge._digest(bridge.authority_v2.__file__))
            self.assertEqual(receipt['frozen_execution_core_sha256'],
                             bridge._digest(bridge.full.__file__))
            self.assertEqual(receipt['original_request_sha256'],
                             manifest['original_request_sha256'])
            self.assertEqual(receipt['parent_evidence'], manifest['parent_evidence'])
            self.assertEqual(receipt['ids'], bridge.suffix.IDS)
            self.assertFalse(receipt['continuation_is_clean_repeat'])
            receipt['global_authority_head_sha256'] = (
                bridge.authority_v2.read_authority(bridge.AUTHORITY).head_sha256)
            path = bridge.full.paths(base, bridge.suffix.CONFIG, bridge.TAIL_STAGE)['receipt']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(receipt) + '\n')
            self.assertEqual(core.validate_receipt(
                bridge.suffix.CONFIG, bridge.TAIL_STAGE, manifest, path, budget,
                'a'*64, 'b'*64,
                bridge._tail_predecessor(bridge.suffix.CONFIG, bridge.TAIL_STAGE,
                                         manifest), 'c'*64, base=base), receipt)
            receipt['bridge_sha256'] = '0'*64
            path.write_text(json.dumps(receipt) + '\n')
            with self.assertRaisesRegex(ValueError, 'receipt differs'):
                core.validate_receipt(
                    bridge.suffix.CONFIG, bridge.TAIL_STAGE, manifest, path, budget,
                    'a'*64, 'b'*64,
                    bridge._tail_predecessor(bridge.suffix.CONFIG, bridge.TAIL_STAGE,
                                             manifest), 'c'*64, base=base)

    def test_stale_authority_head_stops_before_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / 'stale.json'
            receipt.write_text(json.dumps({'global_authority_head_sha256': '0'*64}))
            calls = []
            with self.assertRaisesRegex(ValueError, 'Stale v2 authority head'):
                bridge.execute(bridge.suffix.CONFIG, bridge.TAIL_STAGE,
                               receipt, Path(tmp) / 'missing-budget.json',
                               base=Path(tmp), token='unused',
                               transport=lambda *_: calls.append(1))
            self.assertEqual(calls, [])

    def test_tampered_tail_proposal_stops_before_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            tail_base = base / bridge.TAIL_BASE.relative_to(bridge.BASE)
            bridge.prepare_tail(base=tail_base)
            manifest_path = bridge.full.paths(tail_base, bridge.suffix.CONFIG)['manifest']
            changed = json.loads(manifest_path.read_text())
            changed['ids'][0] = 'DEV-018'
            manifest_path.write_text(json.dumps(changed) + '\n')
            head = bridge.authority_v2.read_authority(bridge.AUTHORITY).head_sha256
            receipt = Path(tmp) / 'current-head.json'
            receipt.write_text(json.dumps({'global_authority_head_sha256': head}))
            calls = []
            with self.assertRaisesRegex(ValueError, 'Tail proposal differs'):
                bridge.execute(bridge.suffix.CONFIG, bridge.TAIL_STAGE,
                               receipt, Path(tmp) / 'missing-budget.json',
                               base=base, token='unused',
                               transport=lambda *_: calls.append(1))
            self.assertEqual(calls, [])

    def test_p2_fresh3_needs_interrupted_composite_and_no_clean_credit(self):
        manifest = bridge.jev.verify(bridge.suffix.CONFIG)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            bridge.prepare_tail(base=base / bridge.TAIL_BASE.relative_to(bridge.BASE))
            with self.assertRaises(FileNotFoundError):
                bridge._full_predecessor(bridge.suffix.CONFIG, 'fresh3', manifest,
                                         base=base)
            with self.assertRaises(FileNotFoundError):
                bridge.build_composite(base=base)

    def test_private_v2_bridge_runs_fake_p1_fresh3_with_exact_receipt(self):
        """An isolated fake transport proves the new hold is on the run path."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'proposal'
            master = Path(tmp) / 'master.jsonl'
            authority = Path(tmp) / 'authority.jsonl'
            config = bridge.jev.CONFIGS[0]
            bridge.prepare(config, base=base)
            manifest = bridge._source_bound(config, base=base)[0]
            p = bridge.full.paths(base, config, 'fresh3')
            ledger = budget_v3.BudgetLedger(master)
            ledger.close()
            header = json.dumps(bridge.authority_v2.HEADER) + '\n'
            authority.write_text(header)
            header_sha = hashlib.sha256(header.encode()).hexdigest()
            pid = manifest['passes'][2]['partition_id']
            partitions.allocate(master, p['budget'], [{
                'id': pid, 'cap_usd': manifest['whole_pass_bound_usd'],
                'model': manifest['model'], 'provider': manifest['provider_tag'],
                'reasoning': 'none'}])
            core = bridge._full_core(config, base=base)
            context = core.context_proof(config, manifest, base=base)
            inspection = core.smoke_inspection(config, manifest, base=base)
            predecessor = core.predecessor(config, 'fresh3', manifest, base=base)
            source = core.budget_identity(config, 'fresh3', manifest, p['budget'],
                                          base=base, master=master)
            receipt = core.expected_receipt(config, 'fresh3', manifest, p['budget'],
                                            context, inspection, predecessor, source,
                                            base=base)
            receipt['global_authority_head_sha256'] = header_sha
            p['receipt'].write_text(json.dumps(receipt) + '\n')
            catalog = json.loads((ROOT / 'results/route-audits/native-variants-recheck-20261006' /
                                  'jev-endpoint.raw.json').read_text())
            old_rows = [json.loads(line) for line in bridge.jev.P0_ATTEMPTS.read_text().splitlines()]
            bodies = [json.dumps(row['body'], separators=(',', ':')).encode()
                      for row in old_rows if row.get('stage') == 'response'] * 20
            sent = []
            real_read = bridge.authority_v2.read_authority
            real_hold = bridge.authority_v2.hold_authority

            def read(path):
                return real_read(path, baseline_head=header_sha, baseline_events=1)

            def hold(path, hold_id, amount, source_hash, expected_head, *, stage_path):
                return real_hold(path, hold_id, amount, source_hash, expected_head,
                                 stage_path=stage_path, baseline_head=header_sha,
                                 baseline_events=1)

            with mock.patch.object(bridge.authority_v2, 'read_authority', side_effect=read), \
                 mock.patch.object(bridge.authority_v2, 'hold_authority', side_effect=hold):
                result = bridge.execute(config, 'fresh3', p['receipt'], p['budget'],
                                        base=base, master=master, authority=authority,
                                        catalog_fetch=lambda *_: catalog,
                                        transport=lambda *_: (sent.append(1) or 200,
                                                              bodies[len(sent)-1]),
                                        token='fake')
            self.assertEqual(result['valid_count'], 60)
            self.assertEqual(len(sent), 60)
            self.assertEqual(len(authority.read_text().splitlines()), 2)
            self.assertEqual(json.loads(authority.read_text().splitlines()[1])['id'], pid)
            self.assertEqual(len((p['stage'] / 'attempts.jsonl').read_text().splitlines()), 240)


if __name__ == '__main__':
    unittest.main()
