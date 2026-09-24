import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reconcile_local_prompt_suffix_v1 as module


def write(path, value, json_lines=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if json_lines:
        path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in value))
    else:
        path.write_text(json.dumps(value) + '\n' if not isinstance(value, str) else value)
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LocalSuffixReconciliationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.suffix_count = 41
        self.build()

    def path(self, name):
        return self.root / name

    def row(self, number, phase, manifest_hash, controller_hash, status='ok'):
        rid = module.IDS[number - 1]
        decision = {'status': status}
        if status == 'ok':
            decision['prediction'] = self.truth
        return {'id': rid, 'configuration': module.CONFIGURATION, 'variant': 'P2',
                'phase': phase, 'attempt_id': f'attempt-{number}',
                'manifest_sha256': manifest_hash, 'controller_sha256': controller_hash,
                'preflight_sha256': self.preflight_hash, 'parent_manifest_sha256': self.parent_hash,
                'interruption_audit_sha256': self.audit_hash,
                'reference_labels_read': False, 'request_sha256': f'request-{number}',
                'decision': decision, 'elapsed_seconds': 2.0,
                'runtime_attestation': {'surface': 'lmstudio_sdk'},
                'stats': {'promptTokensCount': 10, 'predictedTokensCount': 5}}

    def evidence(self, rows, output, journal, manifest_hash, phase):
        output_hash = write(self.path(output), rows, True)
        hashes = [hashlib.sha256(line.encode()).hexdigest()
                  for line in self.path(output).read_text().splitlines()]
        events = []
        for row, row_hash in zip(rows, hashes):
            started = {'event': 'started', 'id': row['id'], 'attempt_id': row['attempt_id'],
                       'request_sha256': row['request_sha256'], 'manifest_sha256': manifest_hash}
            if phase == 'development_suffix':
                started['controller_sha256'] = self.suffix_controller_hash
            events.extend((started, {'event': 'finished', 'id': row['id'],
                                     'attempt_id': row['attempt_id'],
                                     'status': row['decision']['status'], 'output_sha256': row_hash}))
        if phase == 'development':
            events.append({'event': 'started', 'id': 'DEV-019',
                           'attempt_id': 'pending-19', 'request_sha256': 'request-19'})
        journal_hash = write(self.path(journal), events, True)
        return output_hash, journal_hash

    def build(self):
        self.truth = dict(zip(module.KEYS, ('positive', 'yes', 'no', 'yes')))
        self.audit_hash = None
        refs = [{'id': rid, 'proposed_labels': self.truth} for rid in module.IDS]
        write(self.path('data/pilot/proposed_labels.jsonl'), refs, True)
        write(self.path('data/pilot/pairs.json'), [])
        write(self.path('scripts/development_benchmark.py'), 'synthetic scorer binding\n')
        self.parent_hash = write(self.path('parent/manifest.json'), {})
        self.preflight_hash = write(self.path('parent/preflight.json'), {})
        self.parent_controller_hash = write(self.path('scripts/local_prompt_execution_v1.cjs'), 'parent controller\n')
        self.suffix_controller_hash = write(self.path('scripts/local_prompt_suffix_v1.cjs'), 'suffix controller\n')
        self.review_hash = write(self.path('parent/review.json'), {})
        self.smoke_hash = write(self.path('parent/smoke.json'), {})
        original = [self.row(i, 'development', self.parent_hash, self.parent_controller_hash,
                             'invalid_output' if i in (2, 4, 6, 8) else 'ok') for i in range(1, 19)]
        self.original_output_hash, self.original_journal_hash = self.evidence(
            original, 'parent/development.jsonl', 'parent/development.attempts.jsonl',
            self.parent_hash, 'development')
        audit = {'unfinished': {'id': 'DEV-019', 'attempt_id': 'pending-19',
                                'request_sha256': 'request-19', 'retry_authorized': False},
                 'saved': {'count': 18, 'status_counts': {'ok': 14, 'invalid_output': 4}},
                 'evidence': {'development_output_sha256': self.original_output_hash,
                              'development_journal_sha256': self.original_journal_hash,
                              'development_terminal_exists': False}}
        self.audit_hash = write(self.path('parent/interruption.json'), audit)
        # Recreate rows with audit hash only in suffix; the original predates the audit.
        binding = {'parent_manifest': 'parent/manifest.json', 'parent_preflight': 'parent/preflight.json',
                   'parent_controller': 'scripts/local_prompt_execution_v1.cjs',
                   'parent_review': 'parent/review.json', 'interruption_audit': 'parent/interruption.json',
                   'original_output': 'parent/development.jsonl',
                   'original_journal': 'parent/development.attempts.jsonl',
                   'original_smoke_inspection': 'parent/smoke.json',
                   'original_terminal': 'parent/development.terminal.json',
                   'stale_lock_sha256': 'stale-lock'}
        for key, value in list(binding.items()):
            if key not in ('original_terminal', 'stale_lock_sha256'):
                binding[key + '_sha256'] = module.digest(self.path(value))
        manifest = {'version': 'local-prompt-suffix-v1', 'configuration': module.CONFIGURATION,
                    'variant': 'P2', 'phase': 'development_suffix', 'canonical_denominator': 60,
                    'allowed_ids': module.IDS[19:], 'ambiguous_parent_id': 'DEV-019',
                    'controller_sha256': self.suffix_controller_hash, 'binding': binding}
        self.manifest_hash = write(self.path(module.MANIFEST), manifest)
        release = {'interruption_audit_sha256': self.audit_hash,
                   'original_lock_sha256': 'stale-lock', 'pid_absent_verified': True,
                   'lock_removed': True}
        release_hash = write(self.path('results/local-prompt-suffix-v1/lock-release-root.json'), release)
        review = {'approved_for_execution': True, 'manifest_sha256': self.manifest_hash,
                  'controller_sha256': self.suffix_controller_hash,
                  'interruption_audit_sha256': self.audit_hash,
                  'lock_release_receipt_sha256': release_hash, 'allowed_ids': module.IDS[19:]}
        write(self.path('results/local-prompt-suffix-v1/execution-review-root.json'), review)
        self.make_suffix(41)

    def make_suffix(self, count, last_status=None):
        rows = [self.row(i, 'development_suffix', self.manifest_hash, self.suffix_controller_hash,
                         last_status if last_status and i == 19 + count else 'ok')
                for i in range(20, 20 + count)]
        output_hash, journal_hash = self.evidence(
            rows, str(module.SUFFIX), 'results/local-prompt-suffix-v1/development-suffix.attempts.jsonl',
            self.manifest_hash, 'development_suffix')
        statuses = {name: sum(row['decision']['status'] == name for row in rows)
                    for name in ('ok', 'invalid_output')}
        terminal = {'status': 'completed' if count == 41 else 'stopped',
                    'configuration': module.CONFIGURATION, 'variant': 'P2', 'phase': 'development_suffix',
                    'manifest_sha256': self.manifest_hash, 'controller_sha256': self.suffix_controller_hash,
                    'output_sha256': output_hash, 'journal_sha256': journal_hash,
                    'canonical_denominator': 60, 'parent_saved_rows': 18,
                    'ambiguous_original_id': 'DEV-019', 'requested_suffix_records': 41,
                    'claimed_attempts': count, 'finished_attempts': count, 'saved_rows': count,
                    'ok_rows': statuses['ok'], 'invalid_output_rows': statuses['invalid_output'],
                    'ambiguous_timeout': False, 'stopped_reason': 'service failed' if count < 41 else None}
        terminal['runtime_attestation'] = {'surface': 'lmstudio_sdk'}
        write(self.path('results/local-prompt-suffix-v1/development-suffix.terminal.json'), terminal)

    def test_complete_still_preserves_unknown(self):
        report = module.reconcile(self.root)
        self.assertEqual(report['saved_rows'], 59)
        self.assertEqual(report['claimed_attempts'], 60)
        self.assertEqual(report['ambiguous_outcome_ids'], ['DEV-019'])
        self.assertEqual(report['never_sent_ids'], [])
        self.assertFalse(report['coverage_complete'])
        self.assertEqual(report['valid_outputs'], 55)
        self.assertEqual(report['all_four_correct'], 55)
        self.assertEqual(report['field_accuracy']['sentiment'], 55 / 60)
        self.assertIsNone(report['resource']['cost_usd'])

    def test_partial_terminal_marks_remaining_never_sent(self):
        self.make_suffix(4, 'service_failure')
        report = module.reconcile(self.root)
        self.assertEqual(report['saved_rows'], 22)
        self.assertEqual(report['ambiguous_outcome_ids'], ['DEV-019'])
        self.assertEqual(report['never_sent_ids'], module.IDS[23:])
        self.assertEqual(report['valid_outputs'], 17)

    def test_last_request_failure_has_no_never_sent_ids(self):
        self.make_suffix(41, 'service_failure')
        path = self.path('results/local-prompt-suffix-v1/development-suffix.terminal.json')
        terminal = json.loads(path.read_text())
        terminal['status'] = 'stopped'
        terminal['stopped_reason'] = 'service failed'
        write(path, terminal)
        report = module.reconcile(self.root)
        self.assertEqual(report['never_sent_ids'], [])
        self.assertEqual(report['terminal']['status'], 'stopped')

    def test_missing_terminal_rejected(self):
        self.path('results/local-prompt-suffix-v1/development-suffix.terminal.json').unlink()
        with self.assertRaises(FileNotFoundError):
            module.reconcile(self.root)

    def test_extra_journal_claim_rejected(self):
        path = self.path('results/local-prompt-suffix-v1/development-suffix.attempts.jsonl')
        with path.open('a') as handle:
            handle.write(json.dumps({'event': 'started', 'id': 'DEV-061'}) + '\n')
        with self.assertRaises(ValueError):
            module.reconcile(self.root)

    def test_tampered_original_rejected(self):
        with self.path('parent/development.jsonl').open('a') as handle:
            handle.write('{}\n')
        with self.assertRaises(ValueError):
            module.reconcile(self.root)

    def test_ambiguous_timeout_rejected(self):
        path = self.path('results/local-prompt-suffix-v1/development-suffix.terminal.json')
        terminal = json.loads(path.read_text())
        terminal['ambiguous_timeout'] = True
        write(path, terminal)
        with self.assertRaises(ValueError):
            module.reconcile(self.root)


if __name__ == '__main__':
    unittest.main()
