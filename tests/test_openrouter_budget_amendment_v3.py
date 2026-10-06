"""Real file locks and ledger writes, exclusively in temporary directories."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_budget_amendment_v3 as amendment
import openrouter_budget_v3 as old_budget
import openrouter_budget_v4 as budget
import paid_budget_partitions_v3 as old_partitions
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v2 as old_authority
import postapproval_authority_v3 as authority


def _race_activate(review, gate, results):
    gate.wait()
    try:
        amendment.activate(review); results.put(True)
    except (ValueError, BlockingIOError):
        results.put(False)


class AdditionalOpenRouterBudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.master = self.base / 'master.jsonl'
        self.master.write_text(json.dumps({'event': 'budget', 'cap_usd': '12.38'}) + '\n')
        ledger = old_budget.BudgetLedger(self.master)
        try:
            known = ledger.reserve(Decimal('0.4'), 'OLD-KNOWN'); ledger.settle(known, Decimal('0.4'))
            unknown = ledger.reserve(Decimal('0.3'), 'OLD-UNKNOWN')
            evidence = self.base / 'unknown.jsonl'
            evidence.write_text(json.dumps({'attempt_id': unknown, 'cost_unknown': True,
                                            'reserved_cost_usd': '0.3'}) + '\n')
            ledger.finalize_unknown_at_reserved_upper_bound(unknown, 'Preserve prior unknown', evidence)
        finally:
            ledger.close()
        self.auth = self.base / 'authority.jsonl'
        header = json.dumps(old_authority.HEADER).encode() + b'\n'
        self.baseline = {'baseline_head': old_authority.sha(header), 'baseline_events': 1}
        self.auth.write_bytes(header + json.dumps({'event': 'hold', 'id': 'old-shared',
            'usd': '1.00', 'source_sha256': 'a' * 64}).encode() + b'\n')
        self.master_before, self.auth_before = self.master.read_bytes(), self.auth.read_bytes()
        self.proposal_path = self.base / 'proposal.json'
        self.proposal = amendment.prepare(self.proposal_path, master_path=self.master,
                                         authority_path=self.auth, **self.baseline)
        candidate = json.loads((self.base / 'root-review-candidate.json').read_text())
        self.review = self.base / 'activation.root-review.json'
        candidate.update(approved=True, independent_review=True, authorized_by_root=True,
                         reviewer='root', reviewed_utc='2026-10-06T18:00:00+00:00')
        self.review.write_text(json.dumps(candidate))

    def activate(self):
        return amendment.activate(self.review)

    def snapshot(self):
        return authority.read_authority(self.auth, **self.baseline)

    def allocate(self, pid, amount):
        manifest = self.base / (pid + '.budget.json')
        partitions.allocate(self.master, manifest, [{'id': pid, 'cap_usd': str(amount),
            'model': 'deepseek/deepseek-v4.1-flash', 'provider': 'open-inference/fp4', 'reasoning': 'low'}])
        return manifest

    def hold(self, pid, amount, *, pool='openrouter_additional', manifest=None, head=None):
        return authority.hold_authority(self.auth, pid, amount, 'b' * 64,
            head or self.snapshot().head_sha256, stage_path=self.base / (pid + '.claim'),
            funding_pool=pool, budget_path=manifest, partition_id=pid, **self.baseline)

    def test_preparation_is_offline_and_does_not_add_point_fifty_five(self):
        self.assertEqual(self.master.read_bytes(), self.master_before)
        self.assertEqual(self.auth.read_bytes(), self.auth_before)
        self.assertEqual(self.proposal['spec']['new_master_cap_usd'], '22.38')
        self.assertEqual(self.proposal['spec']['new_total_authority_cap_usd'], '20.00')
        self.assertTrue(self.proposal['spec']['prior_0_55_request_superseded'])
        self.assertFalse(self.proposal['spec']['prior_0_55_request_additive'])
        self.assertFalse(self.snapshot().amendment_complete)
        self.assertEqual(self.snapshot().openrouter_available_usd, 0)

    def test_unapproved_and_stale_reviews_cannot_amend(self):
        review = json.loads(self.review.read_text()); review['approved'] = False
        self.review.write_text(json.dumps(review))
        with self.assertRaises(ValueError): self.activate()
        self.assertEqual(self.auth.read_bytes(), self.auth_before)
        review['approved'] = True; self.review.write_text(json.dumps(review))
        self.master.write_bytes(self.master_before + b'{"event":"reserve"}\n')
        with self.assertRaises(ValueError): self.activate()
        self.assertEqual(self.auth.read_bytes(), self.auth_before)

    def test_exact_amendment_preserves_charges_unknowns_and_fences_old_writers(self):
        self.activate()
        self.assertTrue(self.master.read_bytes().startswith(self.master_before))
        self.assertTrue(self.auth.read_bytes().startswith(self.auth_before))
        ledger = budget.BudgetLedger(self.master)
        try:
            self.assertEqual(ledger.cap, Decimal('22.38'))
            self.assertEqual(ledger.accounted(), Decimal('0.7'))
            self.assertEqual(sum(e['event'] == 'unknown_cost_accounted_as_upper_bound' for e in ledger.events), 1)
        finally: ledger.close()
        state = self.snapshot()
        self.assertEqual((state.shared_available_usd, state.openrouter_available_usd), (Decimal('9'), Decimal('10')))
        with self.assertRaises(ValueError): old_budget.BudgetLedger(self.master)
        with self.assertRaises(ValueError): old_authority.read_authority(self.auth, **self.baseline)
        with self.assertRaises(ValueError): self.activate()

    def test_unreviewed_master_raise_is_rejected(self):
        ledger = budget.BudgetLedger(self.master)
        try:
            with self.assertRaises(ValueError): ledger.amend_cap(Decimal('22.38'), 'Not reviewed')
        finally: ledger.close()
        self.assertEqual(self.master.read_bytes(), self.master_before)

    def test_partial_activation_exposes_no_extra_pool_and_recovers_exact_append(self):
        original = old_authority._append
        def fail_master(handle, event):
            if event['event'] == 'cap_amendment': raise OSError('Synthetic crash before master append')
            return original(handle, event)
        with patch.object(old_authority, '_append', side_effect=fail_master):
            with self.assertRaises(OSError): self.activate()
        saved = self.auth.read_bytes()
        self.assertFalse(self.snapshot().amendment_complete)
        self.assertEqual(self.snapshot().openrouter_available_usd, 0)
        with self.assertRaises(ValueError): self.hold('uncommitted', Decimal('0.1'), pool='shared')
        self.activate()
        self.assertEqual(self.auth.read_bytes(), saved)
        self.assertTrue(self.snapshot().amendment_complete)

    def test_earmarked_money_never_funds_shared_or_foreign_master(self):
        self.activate()
        self.hold('cloudflare-shared', Decimal('9'), pool='shared')
        with self.assertRaises(ValueError): self.hold('cloudflare-over', Decimal('0.01'), pool='shared')
        self.assertEqual(self.snapshot().openrouter_available_usd, Decimal('10'))
        manifest = self.allocate('or-next', Decimal('0.6307840'))
        foreign = json.loads(manifest.read_text()); foreign['master_ledger'] = str(self.base / 'cloudflare-master.jsonl')
        wrong = self.base / 'wrong-budget.json'; wrong.write_text(json.dumps(foreign))
        with self.assertRaises(ValueError): self.hold('or-next', Decimal('0.6307840'), manifest=wrong)
        self.hold('or-next', Decimal('0.6307840'), manifest=manifest)
        self.assertEqual(self.snapshot().openrouter_available_usd, Decimal('9.3692160'))

    def test_child_unknown_retains_whole_hold_and_master_allocation(self):
        self.activate(); amount = Decimal('0.6307840')
        manifest = self.allocate('unknown-stage', amount)
        self.hold('unknown-stage', amount, manifest=manifest)
        child = partitions.open_partition(self.master, manifest, 'unknown-stage',
            'deepseek/deepseek-v4.1-flash', 'open-inference/fp4', 'low')
        try:
            attempt = child.reserve(Decimal('0.0630784'), 'DEV-051')
            self.assertFalse(child.settle(attempt, None))
            self.assertEqual(child.accounted(), Decimal('0.0630784'))
            with self.assertRaises(ValueError): child.reserve(Decimal('0.0630784'), 'DEV-052')
            self.assertEqual(child.master_cap, Decimal('22.38'))
        finally: child.close()
        self.assertEqual(self.snapshot().openrouter_accounted_usd, amount)
        with self.assertRaises(ValueError): partitions.reconcile_partition(self.master, manifest, 'unknown-stage')

    def test_master_reservation_and_partition_caps_remain_aggregate(self):
        self.activate(); manifest = self.allocate('large-child', Decimal('15'))
        with self.assertRaises(ValueError): self.allocate('too-large', Decimal('7'))
        child = partitions.open_partition(self.master, manifest, 'large-child',
            'deepseek/deepseek-v4.1-flash', 'open-inference/fp4', 'low')
        try:
            attempt = child.reserve(Decimal('15'), 'ONE'); child.settle(attempt, Decimal('15'))
            with self.assertRaises(ValueError): child.reserve(Decimal('0.001'), 'TWO')
        finally: child.close()
        self.assertIsNot(partitions._core.BudgetLedger, old_partitions.BudgetLedger)
        self.assertEqual(old_partitions.BudgetLedger, old_budget.BudgetLedger)

    def test_two_concurrent_holds_cannot_spend_same_earmarked_capacity(self):
        self.activate()
        manifests = {pid: self.allocate(pid, Decimal('9')) for pid in ('one', 'two')}
        head = self.snapshot().head_sha256; gate = threading.Barrier(2)
        def submit(pid):
            gate.wait()
            try:
                self.hold(pid, Decimal('9'), manifest=manifests[pid], head=head); return True
            except (ValueError, BlockingIOError): return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ('one', 'two')))
        self.assertEqual(results.count(True), 1)
        self.assertEqual(self.snapshot().openrouter_accounted_usd, Decimal('9'))

    def test_two_real_processes_amend_only_once(self):
        ctx = multiprocessing.get_context('spawn'); gate = ctx.Event(); results = ctx.Queue()
        processes = [ctx.Process(target=_race_activate, args=(str(self.review), gate, results)) for _ in range(2)]
        for process in processes: process.start()
        gate.set()
        outcomes = [results.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30); self.assertEqual(process.exitcode, 0)
        self.assertEqual(outcomes.count(True), 1)
        self.assertTrue(self.snapshot().amendment_complete)
        self.assertEqual(sum(json.loads(line).get('event') == 'authority_amendment'
                             for line in self.auth.read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
