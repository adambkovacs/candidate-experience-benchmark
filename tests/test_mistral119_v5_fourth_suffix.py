import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_v5_fourth_suffix as stage


class FakeChild:
    master_cap = stage.Decimal('12.38')
    cap = stage.CAP
    closed = False

    def __init__(self):
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


class FourthSuffixTests(unittest.TestCase):
    def test_sealed_boundary_and_exact_frozen_requests(self):
        binding = stage.prior_gate()
        self.assertEqual(binding['failed_ids_preserved'],
                         ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058'])
        self.assertEqual(binding['unsent_ids'], list(stage.IDS))
        manifest = stage.manifest_value()
        self.assertEqual([x['record_id'] for x in manifest['suffix_requests']],
                         list(stage.IDS))
        self.assertFalse(manifest['reference_labels_read'])
        self.assertEqual(stage.CAP, stage.Decimal('0.09'))
        self.assertGreaterEqual(stage.CAP, stage.study.RESERVE * 2)
        plan = stage.study.verify(stage.smoke.CONFIG, 'fresh1',
                                  stage.prior.PLAN_SHA['fresh1'])
        self.assertEqual(manifest['suffix_requests'],
                         plan['conditions']['P0']['development'][58:60])

    def test_fake_execution_reserves_once_and_does_not_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            base = (Path(folder) / 'stage').resolve()
            authority = Path(folder) / 'authority.jsonl'
            original_verify = stage.verify
            with patch.object(stage, 'BASE', base), patch.object(stage, 'AUTHORITY', authority):
                stage.prepare(base)
                budget = base / 'suffix.budget-manifest.json'
                child_path = base / (budget.stem + '-' + stage.PID + '.jsonl')
                budget.write_text(json.dumps({'version': 'paid-partitions-v1',
                    'master_ledger': str(stage.smoke.MASTER.resolve()),
                    'partitions': [{'id': stage.PID, 'cap_usd': str(stage.CAP),
                        'model': stage.study.MODEL, 'provider': stage.study.PROVIDER,
                        'reasoning': 'none', 'child_ledger': str(child_path)}]}))
                authority.write_text(json.dumps({'event': 'authority',
                    'kind': 'postapproval-paid-work-v1',
                    'cap_usd': str(stage.third.AUTHORITY_CAP),
                    'decision_key': stage.third.AUTHORITY_DECISION_KEY,
                    'approval_sha256': stage.third.AUTHORITY_APPROVAL_SHA}) + '\n')
                with patch.object(stage, 'verify', side_effect=lambda: original_verify(base)):
                    manifest, digest = stage.verify()
                    binding = stage.gate('fresh1', 'P0', 'suffix', manifest, digest)
                    receipt = stage.expected_receipt('fresh1', 'P0', 'suffix',
                        manifest, digest, budget, binding)
                    receipt['reviewer'] = 'root'
                    receipt['global_authority_head_sha256'] = hashlib.sha256(
                        authority.read_bytes()).hexdigest()
                    review_path = base / 'suffix.root-review.json'
                    review_path.write_text(json.dumps(receipt))
                    fake = FakeChild()
                    payloads = []

                    def fake_send(payload, token):
                        payloads.append(payload)
                        raise RuntimeError('fake transport stop')

                    live = lambda *_: ({'id': stage.study.MODEL},
                                       {'tag': stage.study.PROVIDER},
                                       stage.study.RESERVE)
                    with self.assertRaisesRegex(RuntimeError, 'fake transport stop'):
                        stage.run(review_path, budget, send=fake_send, live=live,
                                  open_child=lambda *_: fake,
                                  load_key=lambda *_: 'fake-key')
                    self.assertEqual(fake.reservations,
                                     [(stage.study.RESERVE, 'DEV-059')])
                    self.assertEqual(payloads, [manifest['suffix_requests'][0]['payload']])
                    self.assertEqual(len(authority.read_text().splitlines()), 2)
                    claim = json.loads((base / 'suffix.claim.json').read_text())
                    self.assertEqual(claim['ids'], list(stage.IDS))
                    attempts = stage.prior.rows(base / 'suffix.attempts.jsonl')
                    self.assertEqual([x['id'] for x in attempts], ['DEV-059'])
                    self.assertTrue(attempts[0]['cost_unknown'])
                    self.assertEqual(attempts[0]['reserved_cost_usd'], str(stage.study.RESERVE))
                    with self.assertRaises(FileExistsError):
                        stage.run(review_path, budget, send=fake_send, live=live,
                                  open_child=lambda *_: fake,
                                  load_key=lambda *_: 'fake-key')
                    self.assertEqual(len(payloads), 1)

    def test_changed_prior_hash_blocks_admission(self):
        original_sha = stage.sha

        def changed(path):
            if Path(path).name == 'suffix.third-budget-reconciliation.json':
                return '0' * 64
            return original_sha(path)

        with patch.object(stage, 'sha', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'sealed evidence differs'):
                stage.manifest_value()


if __name__ == '__main__':
    unittest.main()
