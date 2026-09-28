"""Verify the published Claude bundles without private source captures."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from export_claude_public_evidence import verify_public
from build_claude_repeat_findings import _binder as archival_binder


class PublicClaudeBundleReleaseTests(unittest.TestCase):
    BUNDLES = (
        ('claude-roster', 'claude-roster-repeats.json', 2003),
        ('haiku', 'haiku-fresh-matched3.json', 200),
        ('opus-medium', 'claude-repeats.json', 128),
    )

    def test_exported_evidence_and_site_reports_are_bound(self):
        for name, site_name, expected_sources in self.BUNDLES:
            with self.subTest(bundle=name):
                bundle = ROOT / 'public-evidence' / 'claude-20260928' / name
                report = verify_public(bundle, ROOT)
                self.assertEqual((bundle / 'report.json').read_bytes(),
                                 (ROOT / 'public-site' / site_name).read_bytes())
                mapping = json.loads((bundle / 'mapping.json').read_text())
                self.assertEqual(len(mapping['entries']), expected_sources)
                self.assertTrue(any(item['redacted'] for item in mapping['entries']))
                self.assertIsInstance(report, dict)

    def test_archival_rebuild_explains_absent_private_original(self):
        with self.assertRaisesRegex(FileNotFoundError, 'Private archival source unavailable'):
            archival_binder(ROOT)[0]('results/absent-private-capture.jsonl')


if __name__ == '__main__':
    unittest.main()
