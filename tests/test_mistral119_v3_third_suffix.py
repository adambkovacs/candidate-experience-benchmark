import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_v3_third_suffix as stage


class FakeChild:
    master_cap = stage.Decimal('12.38')
    cap = stage.CAP
    closed = False

    def state(self):
        return (None, None, False)

    def accounted(self):
        return stage.Decimal(0)

    def close(self):
        pass


class ThirdSuffixTests(unittest.TestCase):
    def fixture(self, folder):
        base = Path(folder)
        stage.prepare(base)
        budget = base / 'suffix.budget-manifest.json'
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str(stage.smoke.MASTER.resolve()),
            'partitions': [{'id': stage.PID, 'cap_usd': str(stage.CAP),
                'model': stage.study.MODEL, 'provider': stage.study.PROVIDER,
                'reasoning': 'none',
                'child_ledger': str((base / (budget.stem + '-' + stage.PID + '.jsonl')).resolve())}]}))
        authority = base / 'authority.jsonl'
        authority.write_text(json.dumps({'event': 'authority',
            'kind': 'postapproval-paid-work-v1', 'cap_usd': '10.00',
            'decision_key': stage.AUTHORITY_DECISION_KEY,
            'approval_sha256': stage.AUTHORITY_APPROVAL_SHA}) + '\n')
        original_verify = stage.verify
        return base, budget, authority, original_verify

    def test_terminal_gate_and_exact_unsent_frozen_requests(self):
        binding = stage.prior_gate()
        self.assertEqual(binding['preserved_failed_ids'],
                         ['DEV-048', 'DEV-050', 'DEV-053'])
        self.assertEqual(binding['unsent_ids'], list(stage.IDS))
        manifest = stage.manifest_value()
        self.assertEqual([r['record_id'] for r in manifest['suffix_requests']],
                         list(stage.IDS))
        self.assertEqual(manifest['child_cap_usd'], '0.30')
        self.assertEqual(manifest['seven_request_full_context_upper_bound_usd'],
                         '0.29245440')
        self.assertFalse(manifest['reference_labels_read'])
        self.assertEqual(manifest['exact_route']['provider_tag'], 'mistral/zdr')

    def test_changed_predecessor_or_manifest_blocks(self):
        with patch.object(stage, 'TERMINAL_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'terminal, billing'):
                stage.prior_gate()
        with tempfile.TemporaryDirectory() as folder:
            stage.prepare(folder)
            stage.verify(folder)
            path = Path(folder) / 'manifest.json'
            altered = json.loads(path.read_text())
            altered['suffix_requests'][0]['record_id'] = 'DEV-053'
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, 'manifest or source drift'):
                stage.verify(folder)

    def test_exact_child_and_global_hold_are_one_to_one(self):
        with tempfile.TemporaryDirectory() as folder:
            base, budget, authority, _ = self.fixture(folder)
            with patch.object(stage, 'BASE', base), patch.object(stage, 'AUTHORITY', authority):
                source = stage.global_hold_source(budget, stage.PID)
                head = hashlib.sha256(authority.read_bytes()).hexdigest()
                stage.hold_authority(head, budget, source)
                rows = [json.loads(line) for line in authority.read_text().splitlines()]
                self.assertEqual(rows[1], {'event': 'hold', 'id': stage.AUTHORITY_ID,
                    'source_sha256': source, 'usd': '0.30'})
                with self.assertRaisesRegex(ValueError, 'head changed'):
                    stage.hold_authority(head, budget, source)
                stage.hold_authority(hashlib.sha256(authority.read_bytes()).hexdigest(),
                                     budget, source)
                self.assertEqual(len(authority.read_text().splitlines()), 2)
                altered = json.loads(budget.read_text())
                altered['partitions'][0]['child_ledger'] = str(base / 'other-child.jsonl')
                budget.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError, 'child controls'):
                    stage.global_hold_source(budget, stage.PID)

    def test_missing_receipt_cannot_hold_or_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            base, budget, authority, original_verify = self.fixture(folder)
            with patch.object(stage, 'BASE', base), patch.object(stage, 'AUTHORITY', authority), \
                    patch.object(stage, 'verify', side_effect=lambda: original_verify(base)):
                with self.assertRaises(FileNotFoundError):
                    stage.run(base / 'suffix.root-review.json', budget,
                        live=lambda *_: self.fail('live before receipt'),
                        open_child=lambda *_: self.fail('child before receipt'),
                        send=lambda *_: self.fail('send before receipt'),
                        load_key=lambda *_: self.fail('key before receipt'))
                self.assertEqual(len(authority.read_text().splitlines()), 1)
                self.assertFalse((base / 'suffix.claim.json').exists())

    def test_reviewed_path_holds_then_delegates_without_sending_in_test(self):
        with tempfile.TemporaryDirectory() as folder:
            base, budget, authority, original_verify = self.fixture(folder)
            with patch.object(stage, 'BASE', base), patch.object(stage, 'AUTHORITY', authority), \
                    patch.object(stage, 'verify', side_effect=lambda: original_verify(base)):
                manifest, digest = stage.verify()
                gate = stage.gate('fresh1', 'P0', 'suffix', manifest, digest)
                receipt = stage.expected_receipt('fresh1', 'P0', 'suffix', manifest,
                    digest, budget, gate)
                receipt['global_authority_head_sha256'] = hashlib.sha256(
                    authority.read_bytes()).hexdigest()
                receipt['reviewer'] = 'offline-review'
                review = base / 'suffix.root-review.json'
                review.write_text(json.dumps(receipt))
                seen = []

                def lifecycle(*args, **kwargs):
                    seen.append((args, kwargs))
                    self.assertEqual(stage.prior.SUFFIX_BASE, base)
                    self.assertEqual(stage.prior.SUFFIX_CAP, stage.CAP)
                    self.assertEqual(stage.prior.partition_id('fresh1', 'P0', 'suffix'),
                                     stage.PID)
                    return 'offline-delegated'

                live = lambda *_: ({'id': stage.study.MODEL},
                                   {'tag': stage.study.PROVIDER}, stage.study.RESERVE)
                with patch.object(stage.prior, 'run', side_effect=lifecycle):
                    self.assertEqual(stage.run(review, budget, live=live,
                        open_child=lambda *_: FakeChild(),
                        send=lambda *_: self.fail('no inference in offline test')),
                        'offline-delegated')
                self.assertEqual(len(seen), 1)
                self.assertEqual(len(authority.read_text().splitlines()), 2)
                self.assertFalse((base / 'suffix.claim.json').exists())

    def test_claim_and_bad_route_block_before_global_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            base, budget, authority, original_verify = self.fixture(folder)
            with patch.object(stage, 'BASE', base), patch.object(stage, 'AUTHORITY', authority), \
                    patch.object(stage, 'verify', side_effect=lambda: original_verify(base)):
                manifest, digest = stage.verify()
                gate = stage.gate('fresh1', 'P0', 'suffix', manifest, digest)
                receipt = stage.expected_receipt('fresh1', 'P0', 'suffix', manifest,
                    digest, budget, gate)
                receipt['global_authority_head_sha256'] = hashlib.sha256(
                    authority.read_bytes()).hexdigest()
                receipt['reviewer'] = 'offline-review'
                review = base / 'suffix.root-review.json'
                review.write_text(json.dumps(receipt))
                (base / 'suffix.claim.json').write_text('{}')
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    stage.run(review, budget, live=lambda *_: self.fail('route after claim'))
                (base / 'suffix.claim.json').unlink()
                with self.assertRaisesRegex(ValueError, 'Fresh exact route'):
                    stage.run(review, budget,
                        live=lambda *_: ({'id': stage.study.MODEL},
                            {'tag': 'other'}, stage.study.RESERVE))
                self.assertEqual(len(authority.read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
