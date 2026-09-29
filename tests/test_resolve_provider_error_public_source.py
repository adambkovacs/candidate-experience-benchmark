import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_deepseek_fresh_repeat_findings as report_common
import resolve_provider_error_public_source as report_resolver
from scripts import export_provider_error_public_evidence as exporter
from scripts import resolve_provider_error_public_source as resolver


class PublicSourceResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.relative = 'results/example/error.jsonl'
        self.source = self.root / self.relative
        self.source.parent.mkdir(parents=True)
        row = {'id': 'DEV-001', 'status': 'service_error', 'prediction': None,
               'usage': None, 'raw_error_response': {
                   'error': {'message': 'upstream unavailable', 'code': 429,
                             'metadata': {'raw': 'busy', 'provider_name': 'test',
                                          'is_byok': False, 'limit_source': 'provider',
                                          'remedy_hint': 'wait'}},
                   'user_id': 'synthetic-private-id'}}
        self.source.write_bytes(exporter.canonical(row))
        self.original_sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.inventory = ((self.relative, self.original_sha, 1),)
        self.patch = patch.object(exporter, 'INVENTORY', self.inventory)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        other_patch = patch.object(report_resolver.exporter, 'INVENTORY', self.inventory)
        other_patch.start()
        self.addCleanup(other_patch.stop)
        exporter.export(self.root, self.inventory, enforce_tracked_set=False)

    def test_public_sha_bound_even_when_private_file_exists(self):
        public, binding = resolver.resolve(self.root, self.relative, self.original_sha)
        self.assertEqual(public, (self.root / exporter.PUBLIC_DIR / self.relative).resolve())
        self.assertEqual(binding['sha256'], hashlib.sha256(public.read_bytes()).hexdigest())
        self.assertEqual(binding['privateOriginalSha256Attestation'], self.original_sha)
        self.assertNotEqual(binding['sha256'], self.original_sha)
        self.assertEqual(binding['privateOriginalVerification'], 'not_rehashed_by_public_report')
        self.assertNotIn(b'synthetic-private-id', public.read_bytes())
        self.assertTrue(self.source.exists())
        bound = []
        value = report_common.bind(self.root, self.relative, bound, self.original_sha)
        self.assertEqual(value, binding)
        self.assertEqual(report_common.file(self.root, self.relative), public)
        self.assertEqual(bound, [binding])

    def test_public_checkout_without_original_and_tamper_rejected(self):
        self.source.unlink()
        public, binding = resolver.resolve(self.root, self.relative, self.original_sha)
        self.assertTrue(public.is_file())
        self.assertEqual(binding['path'], str(exporter.PUBLIC_DIR / self.relative))
        self.assertEqual(report_common.file(self.root, self.relative), public)
        with self.assertRaisesRegex(ValueError, 'private-source hash differs'):
            resolver.resolve(self.root, self.relative, '0' * 64)
        public.write_bytes(public.read_bytes().replace(b'upstream unavailable', b'other failure'))
        with self.assertRaisesRegex(ValueError, 'Public source hash mismatch'):
            resolver.resolve(self.root, self.relative, self.original_sha)


if __name__ == '__main__':
    unittest.main()
