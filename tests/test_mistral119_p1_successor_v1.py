import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_p1_successor_v1 as stage


class FakeChild:
    master_cap = stage.Decimal('12.38')
    closed = False

    def __init__(self, cap):
        self.cap = cap
        self.reservations = []

    def state(self):
        return None, None, False

    def accounted(self):
        return stage.Decimal(0)

    def reserve(self, amount, record_id):
        self.reservations.append((amount, record_id))
        return 'fake-attempt'

    def close(self):
        pass


class P1SuccessorTests(unittest.TestCase):
    def test_p0_evidence_and_frozen_p1_membership(self):
        binding = stage.p0_gate()
        self.assertEqual((binding['valid'], binding['failed'], binding['never_sent']),
                         (55, 5, 0))
        self.assertEqual(binding['failed_ids'], stage.FAILED)
        self.assertFalse(binding['repeat_pass_credit'])
        manifest = stage.manifest_value()
        plan = stage.study.verify(stage.smoke.CONFIG, 'fresh1',
                                  stage.prior.PLAN_SHA['fresh1'])
        self.assertEqual(manifest['smoke_requests'],
                         plan['conditions']['P1']['smoke'])
        self.assertEqual(manifest['development_requests'],
                         plan['conditions']['P1']['development'])
        self.assertEqual([r['record_id'] for r in manifest['development_requests']],
                         stage.IDS)
        self.assertFalse(manifest['reference_labels_read'])
        self.assertFalse(manifest['reference_labels_sent'])

    def test_changed_p0_source_blocks_admission_without_mutating_evidence(self):
        original = stage.p0.source_path
        target = stage.p0.STAGES[0][0] / 'development.attempts.jsonl'
        with tempfile.TemporaryDirectory() as folder:
            copied = Path(folder) / 'altered.jsonl'
            rows = stage.p0.read_rows(target)
            rows[0]['status'] = 'unknown_cost'
            copied.write_text(''.join(json.dumps(row) + '\n' for row in rows))

            def substituted(path):
                return copied if Path(path) == target else original(path)

            with patch.object(stage.p0, 'source_path', side_effect=substituted):
                with self.assertRaises(ValueError):
                    stage.p0_gate()

    def test_no_development_without_inspected_closed_smoke(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(stage, 'BASE', Path(folder)):
                stage.prepare()
                manifest, digest = stage.verify()
                with self.assertRaises((FileNotFoundError, ValueError)):
                    stage.gate('fresh1', 'P1', 'development', manifest, digest)
                self.assertFalse((Path(folder) / 'development.claim.json').exists())

    def test_inspected_successor_smoke_admits_development_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            with patch.object(stage, 'BASE', base):
                stage.prepare()
                manifest, digest = stage.verify()
                smoke_binding = {'manifest_sha256': digest,
                    'source_sha256': {'claim.json': 'a' * 64},
                    'budget_reconciliation_sha256': 'b' * 64,
                    'count': 3, 'known_cost_usd': '0.001',
                    'ids': stage.IDS[:3]}
                inspection = {'schema': 'mistral119-v3-phase-smoke-inspection-v1',
                    'reviewer': 'root', 'verdict': 'PASS',
                    'raw_responses_inspected': True, 'terminal_exit_code': 0,
                    'manifest_sha256': digest,
                    'source_sha256': smoke_binding['source_sha256'],
                    'budget_reconciliation_sha256':
                        smoke_binding['budget_reconciliation_sha256'],
                    'ids': stage.IDS[:3], 'valid_count': 3, 'invalid_count': 0,
                    'known_cost_usd': smoke_binding['known_cost_usd']}
                (base / 'smoke.inspection.json').write_text(json.dumps(inspection))

                def closed(folder, phase, requests, manifest_sha):
                    self.assertEqual(Path(folder), base)
                    self.assertEqual(phase, 'smoke')
                    self.assertEqual(requests, manifest['smoke_requests'])
                    self.assertEqual(manifest_sha, digest)
                    return smoke_binding

                with patch.object(stage.prior, 'closed_phase', side_effect=closed):
                    binding = stage.gate('fresh1', 'P1', 'development',
                                         manifest, digest)
                self.assertEqual(binding['smoke']['ids'], stage.IDS[:3])
                self.assertEqual(binding['smoke']['inspection_sha256'],
                                 stage.sha(base / 'smoke.inspection.json'))

    def test_fake_smoke_holds_budget_once_and_preserves_unknown_request(self):
        with tempfile.TemporaryDirectory() as folder:
            base = (Path(folder) / 'stage').resolve()
            authority = Path(folder) / 'authority.jsonl'
            authority.write_text(json.dumps({'event': 'authority',
                'kind': 'postapproval-paid-work-v1',
                'cap_usd': str(stage.third.AUTHORITY_CAP),
                'decision_key': stage.third.AUTHORITY_DECISION_KEY,
                'approval_sha256': stage.third.AUTHORITY_APPROVAL_SHA}) + '\n')
            with patch.object(stage, 'BASE', base), \
                 patch.object(stage, 'AUTHORITY', authority):
                stage.prepare()
                budget = base / 'smoke.budget-manifest.json'
                child = base / (budget.stem + '-' + stage.PID['smoke'] + '.jsonl')
                budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                    'master_ledger': str(stage.smoke.MASTER.resolve()),
                    'partitions': [{'id': stage.PID['smoke'],
                        'cap_usd': str(stage.SMOKE_CAP), 'model': stage.study.MODEL,
                        'provider': stage.study.PROVIDER, 'reasoning': 'none',
                        'child_ledger': str(child)}]}))
                manifest, digest = stage.verify()
                binding = stage.gate('fresh1', 'P1', 'smoke', manifest, digest)
                receipt = stage.expected_receipt('smoke', manifest, digest,
                                                 budget, binding)
                receipt['reviewer'] = 'root'
                receipt['global_authority_head_sha256'] = hashlib.sha256(
                    authority.read_bytes()).hexdigest()
                receipt_path = base / 'smoke.root-review.json'
                receipt_path.write_text(json.dumps(receipt))
                child_ledger = FakeChild(stage.SMOKE_CAP)
                payloads = []

                def fake_send(payload, token):
                    payloads.append(payload)
                    raise RuntimeError('fake transport stop')

                live = lambda *_: ({'id': stage.study.MODEL},
                                   {'tag': stage.study.PROVIDER}, stage.study.RESERVE)
                def missing_key(_):
                    raise ValueError('missing test key')

                with self.assertRaisesRegex(ValueError, 'missing test key'):
                    stage.run('smoke', receipt_path, budget, send=fake_send,
                              live=live, open_child=lambda *_: child_ledger,
                              load_key=missing_key)
                self.assertEqual(len(authority.read_text().splitlines()), 1)
                self.assertFalse((base / 'smoke.claim.json').exists())

                opens = 0
                def transient_open(*_):
                    nonlocal opens
                    opens += 1
                    if opens == 2:
                        raise RuntimeError('transient second open')
                    return child_ledger

                with self.assertRaisesRegex(RuntimeError, 'transient second open'):
                    stage.run('smoke', receipt_path, budget, send=fake_send,
                              live=live, open_child=transient_open,
                              load_key=lambda *_: 'fake-key')
                self.assertEqual(opens, 2)
                self.assertEqual(len(authority.read_text().splitlines()), 2)
                self.assertFalse((base / 'smoke.claim.json').exists())
                self.assertEqual(payloads, [])

                with self.assertRaisesRegex(RuntimeError, 'fake transport stop'):
                    stage.run('smoke', receipt_path, budget, send=fake_send,
                              live=live, open_child=lambda *_: child_ledger,
                              load_key=lambda *_: 'fake-key')
                self.assertEqual(child_ledger.reservations,
                                 [(stage.study.RESERVE, 'DEV-001')])
                self.assertEqual(payloads, [manifest['smoke_requests'][0]['payload']])
                self.assertEqual(len(authority.read_text().splitlines()), 2)
                attempt = stage.prior.rows(base / 'smoke.attempts.jsonl')[0]
                self.assertEqual(attempt['id'], 'DEV-001')
                self.assertTrue(attempt['cost_unknown'])
                self.assertEqual(attempt['reserved_cost_usd'], str(stage.study.RESERVE))
                with self.assertRaises(FileExistsError):
                    stage.run('smoke', receipt_path, budget, send=fake_send,
                              live=live, open_child=lambda *_: child_ledger,
                              load_key=lambda *_: 'fake-key')
                self.assertEqual(len(payloads), 1)
                self.assertEqual(len(authority.read_text().splitlines()), 2)

    def test_changed_authority_head_blocks_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            authority = Path(folder) / 'authority.jsonl'
            authority.write_text(json.dumps({'event': 'authority',
                'kind': 'postapproval-paid-work-v1',
                'cap_usd': str(stage.third.AUTHORITY_CAP),
                'decision_key': stage.third.AUTHORITY_DECISION_KEY,
                'approval_sha256': stage.third.AUTHORITY_APPROVAL_SHA}) + '\n')
            with patch.object(stage, 'AUTHORITY', authority):
                with self.assertRaisesRegex(ValueError, 'head changed'):
                    stage.hold_authority('smoke', '0' * 64, 'a' * 64)
            self.assertEqual(len(authority.read_text().splitlines()), 1)

    def test_shared_cap_and_exact_predispatch_hold_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            authority = Path(folder) / 'authority.jsonl'
            genesis = {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                       'cap_usd': str(stage.third.AUTHORITY_CAP),
                       'decision_key': stage.third.AUTHORITY_DECISION_KEY,
                       'approval_sha256': stage.third.AUTHORITY_APPROVAL_SHA}
            authority.write_text(json.dumps(genesis) + '\n' + json.dumps({
                'event': 'hold', 'id': 'other-paid-stage', 'usd': '9.90',
                'source_sha256': 'b' * 64}) + '\n')
            with patch.object(stage, 'AUTHORITY', authority):
                head = hashlib.sha256(authority.read_bytes()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'authority exhausted'):
                    stage.hold_authority('smoke', head, 'a' * 64)
                self.assertEqual(len(authority.read_text().splitlines()), 2)
                authority.write_text(json.dumps(genesis) + '\n')
                head = hashlib.sha256(authority.read_bytes()).hexdigest()
                self.assertEqual(stage.hold_authority('smoke', head, 'a' * 64), 'new')
                head = hashlib.sha256(authority.read_bytes()).hexdigest()
                self.assertEqual(stage.hold_authority('smoke', '0' * 64,
                                                      'a' * 64), 'existing')
                with self.assertRaisesRegex(ValueError, 'Existing P1 hold differs'):
                    stage.hold_authority('smoke', head, 'c' * 64)
                self.assertEqual(len(authority.read_text().splitlines()), 2)

    def test_budget_manifest_must_bind_exact_child_and_route(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder).resolve()
            with patch.object(stage, 'BASE', base):
                stage.prepare()
                budget = base / 'smoke.budget-manifest.json'
                budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                    'master_ledger': str(stage.smoke.MASTER.resolve()),
                    'partitions': [{'id': stage.PID['smoke'],
                        'cap_usd': str(stage.SMOKE_CAP), 'model': stage.study.MODEL,
                        'provider': 'wrong-provider', 'reasoning': 'none',
                        'child_ledger': str(base / 'wrong.jsonl')}]}))
                with self.assertRaisesRegex(ValueError, 'child partition differs'):
                    stage.budget_identity('smoke', budget)


if __name__ == '__main__':
    unittest.main()
