import copy
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semif_prompt_continuation as continuation


class SemIfContinuationTests(unittest.TestCase):
    @contextmanager
    def committed_evidence_fixture(self):
        """Recreate the audit-time journal, independent of later execution."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            audit = json.loads(continuation.AUDIT.read_text())
            correction = json.loads(continuation.CORRECTION.read_text())
            for relative in (audit['source']['original_manifest'], audit['saved_output']['path'],
                             audit['events']['path']):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((continuation.ROOT / relative).read_bytes())
            audit_path = root / continuation.AUDIT.relative_to(continuation.ROOT)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_bytes(continuation.AUDIT.read_bytes())
            correction_path = root / continuation.CORRECTION.relative_to(continuation.ROOT)
            correction_path.write_bytes(continuation.CORRECTION.read_bytes())
            claim = audit['global_journal_claim']
            journal = root / claim['path']
            journal.parent.mkdir(parents=True, exist_ok=True)
            journal.write_text(json.dumps({'attempt_id': claim['claim_id'], 'seq': claim['seq'],
                                           'event': claim['event'], 'utc': claim['utc']}) + '\n')
            with patch.object(continuation, 'ROOT', root), patch.object(continuation, 'CORRECTION', correction_path):
                yield audit_path, audit, correction, root

    def test_committed_interruption_and_separate_manifest_validate(self):
        with self.committed_evidence_fixture() as (audit_path, _, _, _):
            evidence = continuation.validate_interruption(audit_path)
        manifest = json.loads(continuation.MANIFEST.read_text())
        continuation.validate_continuation_manifest(manifest, evidence)
        self.assertEqual(evidence['audit']['continuation_boundary']['eligible_unattempted_ids'], continuation.ELIGIBLE)
        config = manifest['configurations'][0]
        self.assertEqual(config['conditions']['P2']['output_paths']['development'],
                         str((continuation.CONTINUATION / 'development-DEV034-060.jsonl').relative_to(continuation.ROOT)))
        self.assertEqual(config['native_execution']['journal'],
                         str((continuation.CONTINUATION / 'execution-journal.jsonl').relative_to(continuation.ROOT)))

    def test_parent_control_or_allowlist_change_rejected(self):
        with self.committed_evidence_fixture() as (audit_path, _, _, _):
            evidence = continuation.validate_interruption(audit_path)
        manifest = json.loads(continuation.MANIFEST.read_text())
        changed = copy.deepcopy(manifest)
        changed['configurations'][0]['controls']['sampling']['temperature'] = 1
        with self.assertRaisesRegex(ValueError, 'Frozen execution controls'):
            continuation.validate_continuation_manifest(changed, evidence)
        changed = copy.deepcopy(manifest)
        changed['continuation']['eligible_unattempted_ids'].insert(0, 'DEV-033')
        with self.assertRaisesRegex(ValueError, 'coverage policy'):
            continuation.validate_continuation_manifest(changed, evidence)

    def test_audit_rejects_new_started_record_even_with_updated_hashes(self):
        with self.committed_evidence_fixture() as (audit_path, audit, correction, root):
            evidence = continuation.validate_interruption(audit_path)
            events_path = root / evidence['events_binding']['file']
            with events_path.open('a') as stream:
                stream.write(json.dumps({'event': 'started', 'id': 'DEV-034', 'utc': '2026-09-24T12:40:00+00:00'}) + '\n')
            audit['events']['sha256'] = continuation.gates.sha(events_path.read_bytes())
            audit['events']['event_count'] = 66
            audit_path.write_text(json.dumps(audit))
            correction['original_audit']['sha256'] = continuation.gates.sha(audit_path.read_bytes())
            correction_path = continuation.CORRECTION
            correction_path.write_text(json.dumps(correction))
            terminal = root / audit['terminal_record']['path']
            self.assertFalse(terminal.exists())
            with self.assertRaisesRegex(ValueError, 'event count'):
                continuation.validate_interruption(audit_path)

    def test_run_refuses_missing_review_receipt_before_model_import(self):
        with self.assertRaisesRegex(ValueError, 'Run requires a root-review'):
            continuation.run(None, {'manifest_binding': {'sha256': '1' * 64}}, None, '0' * 64)

    def test_run_rejects_reused_output_before_model_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            preview = root / 'preflight.json'
            report = {'contract': 'test', 'manifest': {'sha256': '1' * 64}}
            preview.write_text(json.dumps(report))
            output = root / 'existing.jsonl'
            output.write_text('{}\n')
            with patch.object(continuation, 'PREVIEW', preview), patch.object(continuation, 'CONTINUATION', root), \
                 patch.object(continuation, 'verify_review_receipt'):
                with self.assertRaisesRegex(ValueError, 'output or journal already exists'):
                    continuation.run(None, {'manifest_binding': report['manifest'], 'output': output},
                                     report, continuation.gates.sha(preview.read_bytes()), root / 'receipt.json', '2' * 64)


if __name__ == '__main__':
    unittest.main()
