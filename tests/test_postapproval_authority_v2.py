"""Offline tests: every authority mutation is confined to temporary copies."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import postapproval_authority_v2 as authority
import openrouter_native_variants_v2 as old_writer


HOLD_ID = 'jev-openrouter-native-p2-choice-v1-fresh1-full-v1'
STAGE = ROOT / 'results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AMOUNT = Decimal('0.073788960')


def _multiprocess_hold(path, kind, head, gate, output):
    gate.wait()
    try:
        authority.hold_authority(path, kind+'-next', Decimal('0.08'), 'a'*64,
                                 head, stage_path=Path(path).parent/(kind+'-stage'))
        output.put((kind, True))
    except (ValueError, BlockingIOError):
        output.put((kind, False))


class PostapprovalAuthorityV2Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / 'authority.jsonl'
        shutil.copyfile(ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl', self.ledger)

    def release(self, *, amount=AMOUNT, head=None, stage=STAGE, child=None,
                master=MASTER, release_id='jev-p2-fresh1-unused-v2'):
        return authority.release_authority(
            self.ledger, release_id, HOLD_ID, amount,
            head or authority.read_authority(self.ledger).head_sha256,
            stage_path=stage, receipt_path=stage.parent / (stage.name + '.root-review.json'),
            manifest_path=stage.parent.parent / (stage.parent.name + '.json'),
            budget_manifest_path=stage.parent / (stage.name + '.budget.json'),
            child_ledger_path=child or stage.parent /
                'fresh1.budget-jev-openrouter-native-p2-choice-v1-fresh1-full-v1.jsonl',
            master_ledger_path=master)

    def test_original_history_source_bound_release_and_new_hold(self):
        before_raw = self.ledger.read_bytes()
        before = authority.read_authority(self.ledger)
        self.assertEqual((before.hold_count, before.accounted_usd, before.available_usd),
                         (47, Decimal('9.948371024'), Decimal('0.051628976')))
        receipt = self.release(head=before.head_sha256)
        self.assertEqual(self.ledger.read_bytes()[:len(before_raw)], before_raw)
        after = authority.read_authority(self.ledger)
        self.assertEqual((after.release_count, after.accounted_usd, after.available_usd),
                         (1, Decimal('9.874582064'), Decimal('0.125417936')))
        self.assertEqual(receipt['new_head_sha256'], after.head_sha256)
        self.assertEqual(receipt['release_event']['hold_source_sha256'],
                         '1be9ec2c2a5ccf011ce3dc00ef472a553fe00a3a886b7abaa8f8bbef918afa99')
        stage = Path(self.tmp.name) / 'future-stage'
        authority.hold_authority(self.ledger, 'cloudflare-next-reviewed-stage',
                                 Decimal('0.056448000'), 'a' * 64,
                                 after.head_sha256, stage_path=stage)
        final = authority.read_authority(self.ledger)
        self.assertEqual(final.available_usd, Decimal('0.068969936'))
        self.assertEqual(final.hold_count, 48)

    def test_stale_duplicate_and_excess_release_do_not_append(self):
        initial = self.ledger.read_bytes()
        head = hashlib.sha256(initial).hexdigest()
        with self.assertRaises(ValueError):
            self.release(amount=AMOUNT + Decimal('0.000000001'), head=head)
        self.assertEqual(self.ledger.read_bytes(), initial)
        self.release(head=head)
        saved = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            self.release(head=head, release_id='other')
        with self.assertRaises(ValueError):
            self.release(head=hashlib.sha256(saved).hexdigest(), release_id='other')
        with self.assertRaises(ValueError):
            authority.hold_authority(self.ledger, 'new-stage', Decimal('0.01'), 'a'*64,
                                     head, stage_path=Path(self.tmp.name)/'stage')
        self.assertEqual(self.ledger.read_bytes(), saved)

    def test_wrong_stage_child_and_master_reconciliation_fail_closed(self):
        initial = self.ledger.read_bytes()
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.release(stage=STAGE.parent / 'fresh2')
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.release(child=STAGE.parent / 'fresh2.budget-jev-openrouter-native-p2-choice-v1-fresh2-full-v1.jsonl')
        master = Path(self.tmp.name) / 'master.jsonl'
        rows = [json.loads(line) for line in MASTER.read_text().splitlines()]
        rows = [row for row in rows if not (row.get('event') == 'partition_reconciled'
                and row.get('partition_id') == HOLD_ID)]
        master.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(ValueError):
            self.release(master=master)
        self.assertEqual(self.ledger.read_bytes(), initial)

    def test_reader_rejects_tamper_unknown_event_and_crash_tail(self):
        self.release()
        valid = self.ledger.read_bytes()
        rows = [json.loads(line) for line in valid.splitlines()]
        rows[-1]['child_sha256'] = 'f' * 64
        self.ledger.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaises(ValueError):
            authority.read_authority(self.ledger)
        self.ledger.write_bytes(valid + b'{"event":"release"')
        with self.assertRaises(ValueError):
            authority.read_authority(self.ledger)
        self.ledger.write_bytes(valid + b'{"event":"mystery"}\n')
        with self.assertRaises(ValueError):
            authority.read_authority(self.ledger)

    def test_old_writer_fences_after_release(self):
        self.release()
        saved = self.ledger.read_bytes()
        with self.assertRaises(ValueError):
            old_writer.hold_authority(self.ledger, 'old-next-stage', Decimal('0.01'),
                                      'b'*64, hashlib.sha256(saved).hexdigest(),
                                      stage_path=Path(self.tmp.name)/'stage')
        self.assertEqual(self.ledger.read_bytes(), saved)

    def test_two_concurrent_provider_holds_cannot_spend_same_headroom(self):
        self.release()
        head = authority.read_authority(self.ledger).head_sha256
        gate = threading.Barrier(2)

        def admit(kind):
            gate.wait()
            try:
                authority.hold_authority(self.ledger, kind+'-next', Decimal('0.08'),
                                         'a'*64, head,
                                         stage_path=Path(self.tmp.name)/(kind+'-stage'))
                return True
            except (ValueError, BlockingIOError):
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(admit, kind) for kind in ('cloudflare', 'openrouter')]
            results = [future.result() for future in futures]
        self.assertEqual(results.count(True), 1)
        self.assertEqual(authority.read_authority(self.ledger).accounted_usd,
                         Decimal('9.954582064'))

    def test_two_processes_share_inode_lock_and_cannot_double_spend(self):
        self.release()
        head = authority.read_authority(self.ledger).head_sha256
        ctx = multiprocessing.get_context('spawn')
        gate = ctx.Barrier(2)
        output = ctx.Queue()
        processes = [ctx.Process(target=_multiprocess_hold,
                                 args=(str(self.ledger), kind, head, gate, output))
                     for kind in ('cloudflare', 'openrouter')]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join()
            self.assertEqual(process.exitcode, 0)
        results = [output.get(timeout=2) for _ in processes]
        self.assertEqual(sum(succeeded for _, succeeded in results), 1)
        self.assertEqual(authority.read_authority(self.ledger).accounted_usd,
                         Decimal('9.954582064'))

    def test_joint_preflight_requires_both_exact_heads_and_clean_master(self):
        self.release()
        master = Path(self.tmp.name) / 'master.jsonl'
        shutil.copyfile(MASTER, master)
        authority_head = authority.read_authority(self.ledger).head_sha256
        master_head = hashlib.sha256(master.read_bytes()).hexdigest()
        result = authority.verify_joint_headroom(self.ledger, master, '0.056448000',
                                                  authority_head, master_head)
        self.assertEqual(result['authority_available_usd'], '0.125417936')
        self.assertGreaterEqual(Decimal(result['master_available_usd']), Decimal('0.056448000'))
        with self.assertRaises(ValueError):
            authority.verify_joint_headroom(self.ledger, master, '0.056448000',
                                             '0'*64, master_head)
        with self.assertRaises(ValueError):
            authority.verify_joint_headroom(self.ledger, master, '0.056448000',
                                             authority_head, '0'*64)
        with self.assertRaises(ValueError):
            authority.verify_joint_headroom(self.ledger, master, '0.126',
                                             authority_head, master_head)

    def test_generic_closed_suffix_with_two_ids_and_retained_cost(self):
        base = Path(self.tmp.name).resolve() / 'suffix' / 'route'
        stage = base / 'tail'
        stage.mkdir(parents=True)
        pid = 'route-tail-v1'
        ids = ['DEV-019', 'DEV-020']
        master = Path(self.tmp.name).resolve() / 'suffix-master.jsonl'
        child = base / 'tail.budget-route-tail-v1.jsonl'
        manifest_path = base.parent / 'route.json'
        budget_path = base / 'tail.budget.json'
        receipt_path = base / 'tail.root-review.json'

        def write(path, value):
            path.write_text(json.dumps(value, sort_keys=True) + '\n')

        manifest = {'configuration_id': 'route', 'stage': 'tail',
                    'partition_id': pid, 'ids': ids, 'model': 'model',
                    'provider_tag': 'provider',
                    'whole_suffix_full_context_bound_usd': '0.020'}
        write(manifest_path, manifest)
        budget = {'version': 'paid-partitions-v1', 'master_ledger': str(master),
                  'partitions': [{'id': pid, 'cap_usd': '0.020',
                                  'child_ledger': str(child), 'model': 'model',
                                  'provider': 'provider', 'reasoning': 'none'}]}
        write(budget_path, budget)
        source = authority.sha(authority.canonical({
            'manifest_sha256': authority.file_sha(manifest_path),
            'budget_manifest_sha256': authority.file_sha(budget_path),
            'partition_id': pid, 'child_ledger': str(child), 'cap_usd': '0.020'}))
        receipt = {'schema': 'future-suffix-root-review', 'approved': True,
                   'reviewer': 'root', 'configuration_id': 'route', 'stage': 'tail',
                   'partition_id': pid, 'global_hold_id': pid,
                   'global_hold_source_sha256': source, 'global_hold_usd': '0.020',
                   'global_authority_cap_usd': '10.00',
                   'global_authority_approval_sha256': authority.HEADER['approval_sha256'],
                   'manifest_sha256': authority.file_sha(manifest_path),
                   'budget_manifest_sha256': authority.file_sha(budget_path),
                   'child_cap_usd': '0.020', 'ids': ids}
        write(receipt_path, receipt)
        shutil.copyfile(receipt_path, stage / 'review-receipt.json')
        child_events = [{'event': 'budget', 'cap_usd': '0.020'}]
        attempts = []
        for index, rid in enumerate(ids):
            aid = f'attempt-{index}'
            cost = ('0.003', '0.004')[index]
            child_events.extend([{'event': 'reserve', 'attempt_id': aid,
                                  'record_id': pid + ':' + rid, 'usd': '0.010'},
                                 {'event': 'settle', 'attempt_id': aid, 'usd': cost}])
            attempts.extend([{'stage': 'reserved', 'id': rid, 'attempt_id': aid,
                              'reserved_cost_usd': '0.010'},
                             {'stage': 'started', 'id': rid, 'attempt_id': aid},
                             {'stage': 'response', 'id': rid, 'attempt_id': aid,
                              'http_status': 200, 'cost_unknown': False,
                              'actual_cost_usd': cost},
                             {'stage': 'parsed', 'id': rid, 'attempt_id': aid,
                              'valid': True}])
        child_events.append({'event': 'partition_closed', 'reason': 'terminal'})
        child.write_text(''.join(json.dumps(row) + '\n' for row in child_events))
        (stage / 'attempts.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in attempts))
        completion = {'schema': 'future-suffix-completion', 'configuration_id': 'route',
                      'stage': 'tail', 'ids': ids, 'valid_count': 2,
                      'invalid_count': 0, 'invalid_ids': [],
                      'attempts_sha256': authority.file_sha(stage / 'attempts.jsonl'),
                      'receipt_sha256': authority.file_sha(receipt_path),
                      'manifest_sha256': authority.file_sha(manifest_path),
                      'budget_manifest_sha256': authority.file_sha(budget_path),
                      'known_actual_cost_usd': '0.007', 'reference_labels_read': False}
        write(stage / 'completion.json', completion)
        reconciliation = {'event': 'partition_reconciled', 'partition_id': pid,
                          'known_actual_usd': '0.007', 'unknown_upper_bound_usd': '0',
                          'unused_allocation_released_usd': '0.013',
                          'child_ledger': str(child), 'child_sha256': authority.file_sha(child)}
        write(stage / 'budget-reconciliation.json', reconciliation)
        allocation = {'event': 'budget_partition', 'partition_id': pid,
                      'allocated_usd': '0.020', 'manifest_path': str(budget_path),
                      'manifest_sha256': authority.file_sha(budget_path),
                      'child_ledger': str(child)}
        master.write_text(''.join(json.dumps(row) + '\n' for row in
                                  [{'event': 'budget', 'cap_usd': '12.38'},
                                   allocation, reconciliation]))
        self.ledger.write_text(''.join(json.dumps(row) + '\n' for row in
                                       [authority.HEADER, {'event': 'hold', 'id': pid,
                                                           'usd': '0.020', 'source_sha256': source}]))
        baseline = authority.sha(self.ledger.read_bytes())
        result = authority.release_authority(
            self.ledger, 'route-tail-unused-v2', pid, '0.013', baseline,
            stage_path=stage, receipt_path=receipt_path,
            manifest_path=manifest_path, budget_manifest_path=budget_path,
            child_ledger_path=child, master_ledger_path=master,
            baseline_head=baseline, baseline_events=2)
        state = authority.read_authority(self.ledger,
                                         baseline_head=baseline, baseline_events=2)
        self.assertEqual(state.accounted_usd, Decimal('0.007'))
        self.assertEqual(result['new_head_sha256'], state.head_sha256)


if __name__ == '__main__':
    unittest.main()
