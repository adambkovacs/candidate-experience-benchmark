import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import export_provider_error_public_evidence as subject


class ProviderErrorExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.relative = 'results/example/error.jsonl'
        self.source = self.root / self.relative
        self.source.parent.mkdir(parents=True)
        self.row = {
            'id': 'DEV-001', 'status': 'service_error', 'request': {'prompt': 'question'},
            'prediction': None, 'usage': None, 'actual_usd': None,
            'client_seconds': 1.25, 'failure': {'reason': 'rate_limit'},
            'raw_error_response': {
                'error': {'message': 'provider failure', 'code': 429,
                          'metadata': {'raw': 'queue full', 'provider_name': 'test',
                                       'is_byok': False, 'limit_source': 'provider',
                                       'remedy_hint': 'wait'}},
                'user_id': 'synthetic-account-123',
            },
        }
        self.source.write_bytes(subject.canonical(self.row))
        self.original = self.source.read_bytes()
        self.inventory = ((self.relative, hashlib.sha256(self.original).hexdigest(), 1),)

    def test_only_account_field_removed_preserving_failure_and_measurements(self):
        out = subject.build(self.root, self.inventory, enforce_tracked_set=False)
        public = json.loads(out[str(subject.PUBLIC_DIR / self.relative)])
        expected = copy.deepcopy(self.row)
        del expected['raw_error_response']['user_id']
        self.assertEqual(public, expected)
        self.assertNotIn(b'synthetic-account-123', b''.join(out.values()))
        manifest = json.loads(out[str(subject.PUBLIC_DIR / 'manifest.json')])
        self.assertEqual(manifest['sources'][0]['removedFieldPaths'],
                         {'raw_error_response.user_id': 1})
        self.assertNotIn('synthetic-account-123', json.dumps(manifest))

    def test_original_unchanged_idempotent_and_public_only_verification(self):
        with patch.object(subject, 'INVENTORY', self.inventory):
            subject.export(self.root, self.inventory, enforce_tracked_set=False)
            subject.export(self.root, self.inventory, enforce_tracked_set=False)
            subject.export(self.root, self.inventory, enforce_tracked_set=False, check=True)
            self.assertEqual(self.source.read_bytes(), self.original)
            self.source.unlink()
            self.assertTrue(subject.verify_public(self.root))

    def test_source_hash_drift_and_unknown_shape_fail_before_write(self):
        changed = copy.deepcopy(self.row)
        changed['request']['prompt'] = 'different'
        self.source.write_bytes(subject.canonical(changed))
        with self.assertRaisesRegex(ValueError, 'source hash drift'):
            subject.export(self.root, self.inventory, enforce_tracked_set=False)
        self.assertFalse((self.root / subject.PUBLIC_DIR).exists())
        changed = copy.deepcopy(self.row)
        changed['raw_error_response']['account_name'] = 'unknown'
        self.source.write_bytes(subject.canonical(changed))
        revised = ((self.relative, subject.digest(self.source.read_bytes()), 1),)
        with self.assertRaisesRegex(ValueError, 'Unknown provider error shape'):
            subject.export(self.root, revised, enforce_tracked_set=False)

    def test_unknown_nested_metadata_and_duplicate_identifier_fail(self):
        changed = copy.deepcopy(self.row)
        changed['raw_error_response']['error']['metadata']['new_private_field'] = 'x'
        self.source.write_bytes(subject.canonical(changed))
        revised = ((self.relative, subject.digest(self.source.read_bytes()), 1),)
        with self.assertRaisesRegex(ValueError, 'Unknown provider metadata fields'):
            subject.build(self.root, revised, enforce_tracked_set=False)
        changed = copy.deepcopy(self.row)
        changed['failure']['detail'] = 'synthetic-account-123'
        self.source.write_bytes(subject.canonical(changed))
        revised = ((self.relative, subject.digest(self.source.read_bytes()), 1),)
        with self.assertRaisesRegex(ValueError, 'outside approved field'):
            subject.build(self.root, revised, enforce_tracked_set=False)
        changed = copy.deepcopy(self.row)
        changed['account_id'] = 'another-synthetic-id'
        self.source.write_bytes(subject.canonical(changed))
        revised = ((self.relative, subject.digest(self.source.read_bytes()), 1),)
        with self.assertRaisesRegex(ValueError, 'Unexpected sensitive field'):
            subject.build(self.root, revised, enforce_tracked_set=False)

    def test_unknown_inventory_and_public_tamper_fail(self):
        with patch.object(subject, '_tracked_inventory', return_value={self.relative, 'results/new.jsonl'}):
            with self.assertRaisesRegex(ValueError, 'inventory drift'):
                subject.build(self.root, self.inventory)
        with patch.object(subject, '_tracked_inventory', return_value=set()):
            # Future untracking may remove the path from Git while the exact
            # private original remains available for source-hash verification.
            self.assertIn(str(subject.PUBLIC_DIR / 'manifest.json'),
                          subject.build(self.root, self.inventory))
        with patch.object(subject, 'INVENTORY', self.inventory):
            subject.export(self.root, self.inventory, enforce_tracked_set=False)
            public = self.root / subject.PUBLIC_DIR / self.relative
            public.write_bytes(public.read_bytes().replace(b'provider failure', b'other failure'))
            with self.assertRaisesRegex(ValueError, 'Public source hash mismatch'):
                subject.verify_public(self.root)

    def test_real_git_no_match_after_untracking_keeps_pinned_private_check(self):
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True,
                       capture_output=True)
        # The private original is present but has never been added to Git.
        self.assertEqual(subject._tracked_inventory(self.root), set())
        subject.export(self.root, self.inventory, enforce_tracked_set=True)
        subject.export(self.root, self.inventory, enforce_tracked_set=True,
                       check=True)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_public_verifier_rejects_unmapped_file(self):
        with patch.object(subject, 'INVENTORY', self.inventory):
            subject.export(self.root, self.inventory, enforce_tracked_set=False)
            extra = self.root / subject.PUBLIC_DIR / 'unmapped.jsonl'
            extra.write_text('{"user_id":"synthetic"}\n')
            with self.assertRaisesRegex(ValueError, 'Unexpected public export file set'):
                subject.verify_public(self.root)

    def test_real_audited_sources_all_validate_without_writing(self):
        self.assertTrue(subject.verify_public())
        present = sum((subject.ROOT / path).is_file() for path, _, _ in subject.INVENTORY)
        if present not in (0, len(subject.INVENTORY)):
            self.fail('Only some private originals remain in the checkout')
        if present:
            outputs = subject.build()
            self.assertEqual(len(outputs), 29)
            manifest = json.loads(outputs[str(subject.PUBLIC_DIR / 'manifest.json')])
        else:
            # A public Git checkout has no private originals to authenticate.
            manifest = json.loads((subject.ROOT / subject.PUBLIC_DIR / 'manifest.json').read_text())
        self.assertEqual(sum(x['removedFieldPaths']['raw_error_response.user_id']
                             for x in manifest['sources']), 29)
        self.assertEqual(len(manifest['sources']), 28)


if __name__ == '__main__':
    unittest.main()
