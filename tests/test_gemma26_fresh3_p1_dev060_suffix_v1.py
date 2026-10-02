import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemma26_fresh3_p1_dev060_suffix_v1 as suffix


class FakeLedger:
    cap = Decimal('0.02')
    master_cap = Decimal('12.38')
    closed = False

    def __init__(self):
        self.actions = []

    def state(self):
        return {}, set(), False

    def accounted(self):
        return Decimal(0)

    def reserve(self, amount, record_id):
        self.actions.append(('reserve', amount, record_id))
        return 'test-attempt-id'

    def settle(self, attempt_id, actual):
        self.actions.append(('settle', attempt_id, actual))
        return actual is not None

    def close(self):
        self.actions.append(('close',))


class GemmaP1Dev060Tests(unittest.TestCase):
    def test_manifest_binds_only_unsent_dev060_and_preserves_unknown(self):
        manifest, digest = suffix.verify()
        self.assertEqual(digest, suffix.sha(suffix.MANIFEST))
        self.assertEqual(manifest['ids'], ['DEV-060'])
        self.assertEqual(manifest['preserved_unknown_id'], 'DEV-059')
        self.assertEqual(manifest['request']['record_id'], 'DEV-060')
        self.assertEqual(manifest['prior']['failed_attempt_id'],
                         '84558e99-3982-449f-ba47-4f2f3176f2dc')
        self.assertEqual(manifest['prior']['sealed_old_child_sha256'], suffix.sha(suffix.OLD_CHILD))

    def test_prefix_change_or_replay_claim_rejected(self):
        original_sha = suffix.sha
        def changed(path):
            if Path(path) == suffix.old_paths()['attempts']:
                return '0' * 64
            return original_sha(path)
        with patch.object(suffix, 'sha', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'source hashes differ'):
                suffix.prior_gate()
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            (stage / 'suffix.claim.json').write_text('{}')
            review = stage / 'suffix.root-review.json'
            review.write_text('{}')
            with patch.object(suffix, 'STAGE', stage), patch.object(
                    suffix, 'expected_review', return_value={}):
                with self.assertRaisesRegex(FileExistsError, 'already claimed'):
                    suffix.run(review, suffix.BASE / 'budget.json')

    def test_old_child_requires_seal_reconciliation_and_unknown_bound(self):
        value = suffix.reconciled_old_child()
        self.assertEqual(value['unknown_upper_bound_usd'], str(suffix.RESERVE))
        self.assertEqual(value['old_child_sha256'], suffix.sha(suffix.OLD_CHILD))
        with patch.object(suffix, 'OLD_CHILD', Path('/nonexistent/old-child.jsonl')):
            with self.assertRaises((OSError, ValueError)):
                suffix.reconciled_old_child()

    def test_global_hold_requires_prior_hold_and_rejects_stale_head(self):
        baseline = suffix.rows(suffix.AUTHORITY_SNAPSHOT)
        old_hold = {'event': 'hold', 'id': suffix.predecessor.AUTHORITY_ID,
                    'usd': str(suffix.predecessor.CHILD_CAP),
                    'source_sha256': suffix.predecessor.global_hold_source(
                        suffix.OLD_BUDGET, suffix.OLD_PARTITION)}
        with tempfile.TemporaryDirectory() as directory:
            authority = Path(directory) / 'authority.jsonl'
            def save(events):
                authority.write_text(''.join(json.dumps(e) + '\n' for e in events))
            save(baseline)
            with patch.object(suffix, 'AUTHORITY', authority):
                with self.assertRaisesRegex(ValueError, 'Original Gemma global hold missing'):
                    suffix.hold_authority(suffix.sha(authority), 'f' * 64)
                save(baseline + [old_hold])
                stale = suffix.sha(authority)
                suffix.hold_authority(stale, 'f' * 64)
                saved = suffix.rows(authority)
                self.assertEqual(saved[-1], {'event': 'hold', 'id': suffix.AUTHORITY_ID,
                                             'usd': str(suffix.CAP), 'source_sha256': 'f' * 64})
                with self.assertRaisesRegex(ValueError, 'head changed'):
                    suffix.hold_authority(stale, 'f' * 64)
                self.assertEqual(suffix.rows(authority), saved)

    def test_one_call_reserves_before_fetch_and_does_not_retry_unknown(self):
        suffix.verify()
        prior = suffix.rows(suffix.old_paths()['attempts'])[-2]
        model, endpoint = prior['model_catalog_entry'], prior['provider_endpoint']
        body = suffix.rows(suffix.old_paths()['responses'])[0]['raw_response']
        for fail in (False, True):
            ledger = FakeLedger()
            with tempfile.TemporaryDirectory() as directory:
                stage = Path(directory)
                review = stage / 'suffix.root-review.json'
                review.write_text(json.dumps({'approved': True,
                                               'global_authority_head_sha256': '0' * 64}))
                def fetch(payload, token, wire, rid, attempt, request_sha):
                    self.assertEqual(ledger.actions[0], ('reserve', suffix.RESERVE, 'DEV-060'))
                    ledger.actions.append(('fetch', rid))
                    if fail:
                        raise TimeoutError('synthetic offline timeout')
                    suffix.frozen.durable(wire, {'id': rid, 'attempt_id': attempt,
                                                  'request_sha256': request_sha,
                                                  'http_status': 200})
                    return body
                with patch.object(suffix, 'STAGE', stage), patch.object(
                        suffix, 'expected_review', return_value={
                            'approved': True, 'global_authority_head_sha256': '0' * 64}), patch.object(
                        suffix, 'checked_route', return_value=(model, endpoint)), patch.object(
                        suffix.partitions, 'open_partition', return_value=ledger), patch.object(
                        suffix.paid, 'load_key', return_value='offline-test-token'), patch.object(
                        suffix, 'hold_authority'), patch.object(
                        suffix.frozen, 'fetch_captured', side_effect=fetch), patch.object(
                        suffix, 'audit_response', return_value={'passed': True}):
                    result = suffix.run(review, suffix.BASE / 'budget.json')
                self.assertEqual(result, not fail)
                self.assertEqual([x[0] for x in ledger.actions].count('reserve'), 1)
                self.assertEqual([x[0] for x in ledger.actions].count('fetch'), 1)
                self.assertEqual([x['id'] for x in suffix.rows(stage / 'suffix.attempts.jsonl')],
                                 ['DEV-060'])
                terminal = suffix.rows(stage / 'suffix.journal.jsonl')[-1]
                self.assertEqual(terminal['event'], 'phase_stopped' if fail else 'phase_completed')
                if fail:
                    self.assertIsNone(suffix.rows(stage / 'suffix.attempts.jsonl')[0]['observed_cost_usd'])


if __name__ == '__main__':
    unittest.main()
