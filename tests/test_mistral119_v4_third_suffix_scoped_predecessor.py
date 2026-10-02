import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_v4_third_suffix_scoped_predecessor as bridge


class FakeChild:
    master_cap = bridge.Decimal('12.38')
    cap = bridge.stage.CAP
    closed = False

    def state(self):
        return (None, None, False)

    def accounted(self):
        return bridge.Decimal(0)

    def reserve(self, amount, record_id):
        if amount != bridge.stage.study.RESERVE or record_id != 'DEV-054':
            raise AssertionError('Unexpected fake reservation')
        return 'fake-attempt'

    def close(self):
        pass


class ScopedPredecessorTests(unittest.TestCase):
    def fixture(self, base, authority):
        bridge.stage.prepare(base)
        budget = base / 'suffix.budget-manifest.json'
        child = base / (budget.stem + '-' + bridge.stage.PID + '.jsonl')
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str(bridge.stage.smoke.MASTER.resolve()),
            'partitions': [{'id': bridge.stage.PID,
                'cap_usd': str(bridge.stage.CAP),
                'model': bridge.stage.study.MODEL,
                'provider': bridge.stage.study.PROVIDER,
                'reasoning': 'none', 'child_ledger': str(child)}]}))
        authority.write_text(json.dumps({'event': 'authority',
            'kind': 'postapproval-paid-work-v1', 'cap_usd': '10.00',
            'decision_key': bridge.stage.AUTHORITY_DECISION_KEY,
            'approval_sha256': bridge.stage.AUTHORITY_APPROVAL_SHA}) + '\n')
        old_verify = bridge.stage.verify
        with patch.object(bridge.stage, 'verify', side_effect=lambda: old_verify(base)):
            manifest, digest = bridge.stage.verify()
            gate = bridge.stage.gate('fresh1', 'P0', 'suffix', manifest, digest)
            old_receipt = bridge.stage.expected_receipt('fresh1', 'P0', 'suffix',
                manifest, digest, budget, gate)
            old_receipt['global_authority_head_sha256'] = hashlib.sha256(
                authority.read_bytes()).hexdigest()
            old_receipt['reviewer'] = 'root'
            old_path = base / 'suffix.root-review.json'
            old_path.write_text(json.dumps(old_receipt))
            source = bridge.stage.global_hold_source(budget, bridge.stage.PID)
            bridge.stage.hold_authority(old_receipt['global_authority_head_sha256'],
                                        budget, source)
            next_receipt = bridge.expected_review(old_path, budget)
            next_receipt['existing_authority_head_sha256'] = hashlib.sha256(
                authority.read_bytes()).hexdigest()
            review = base / 'suffix.v4-root-review.json'
            review.write_text(json.dumps(next_receipt))
        return budget, old_path, review, old_verify

    def test_nested_predecessor_gate_reaches_fake_transport_without_second_hold(self):
        with tempfile.TemporaryDirectory() as folder:
            base = (Path(folder) / 'stage').resolve()
            authority = Path(folder) / 'authority.jsonl'
            with patch.object(bridge, 'BASE', base), patch.object(bridge, 'REVIEW',
                    base / 'suffix.v4-root-review.json'), \
                    patch.object(bridge.stage, 'BASE', base), \
                    patch.object(bridge.stage, 'AUTHORITY', authority):
                budget, old, review, original_verify = self.fixture(base, authority)
                seen = []

                def fake_send(payload, token):
                    seen.append((payload['model'], token))
                    raise RuntimeError('fake transport stop')

                live = lambda *_: ({'id': bridge.stage.study.MODEL},
                                   {'tag': bridge.stage.study.PROVIDER},
                                   bridge.stage.study.RESERVE)
                with patch.object(bridge.stage, 'verify',
                        side_effect=lambda: original_verify(base)):
                    with self.assertRaisesRegex(RuntimeError, 'fake transport stop'):
                        bridge.run(review, old, budget, send=fake_send, live=live,
                            open_child=lambda *_: FakeChild(), load_key=lambda *_: 'fake-key')
                self.assertEqual(len(seen), 1)
                self.assertEqual(len(authority.read_text().splitlines()), 2)
                claim = json.loads((base / 'suffix.claim.json').read_text())
                self.assertEqual(claim['ids'], list(bridge.stage.IDS))
                self.assertFalse((base / 'suffix.raw.jsonl').read_text())

    def test_review_or_existing_hold_change_blocks_before_fake_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            base = (Path(folder) / 'stage').resolve()
            authority = Path(folder) / 'authority.jsonl'
            with patch.object(bridge, 'BASE', base), patch.object(bridge, 'REVIEW',
                    base / 'suffix.v4-root-review.json'), \
                    patch.object(bridge.stage, 'BASE', base), \
                    patch.object(bridge.stage, 'AUTHORITY', authority):
                budget, old, review, original_verify = self.fixture(base, authority)
                value = json.loads(review.read_text())
                value['wrapper_sha256'] = '0' * 64
                review.write_text(json.dumps(value))
                with patch.object(bridge.stage, 'verify',
                        side_effect=lambda: original_verify(base)):
                    with self.assertRaisesRegex(ValueError, 'receipt differs'):
                        bridge.run(review, old, budget,
                                   send=lambda *_: self.fail('fake send after bad receipt'))
                value['wrapper_sha256'] = bridge.sha(bridge.__file__)
                review.write_text(json.dumps(value))
                with authority.open('a') as file:
                    file.write(json.dumps({'event': 'hold', 'id': 'unreviewed',
                        'source_sha256': '0' * 64, 'usd': '0.01'}) + '\n')
                with patch.object(bridge.stage, 'verify',
                        side_effect=lambda: original_verify(base)):
                    with self.assertRaisesRegex(ValueError, 'authority head changed'):
                        bridge.run(review, old, budget,
                            live=lambda *_: ({'id': bridge.stage.study.MODEL},
                                {'tag': bridge.stage.study.PROVIDER},
                                bridge.stage.study.RESERVE),
                            open_child=lambda *_: FakeChild(),
                            send=lambda *_: self.fail('fake send after changed hold'))
                self.assertFalse((base / 'suffix.claim.json').exists())


if __name__ == '__main__':
    unittest.main()
