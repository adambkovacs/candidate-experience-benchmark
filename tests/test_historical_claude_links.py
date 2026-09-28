"""Check the 14 public historical links without private originals."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_public_explorer as explorer
import export_historical_claude_links as historical


class HistoricalClaudeLinkTests(unittest.TestCase):
    def test_exact_14_source_mapping_has_60_public_rows_each(self):
        entries = historical.check(ROOT)
        self.assertEqual(set(entries), set(historical.SOURCES))
        self.assertEqual(len(entries), 14)
        for source, entry in entries.items():
            with self.subTest(source=source):
                self.assertTrue(entry['redacted'])
                public = ROOT / entry['publicPath']
                self.assertEqual(len([json.loads(line) for line in public.read_text().splitlines()]), 60)

    def test_explorer_routes_only_exact_backed_historical_sources(self):
        mapping = historical.public_path_map(str(ROOT))
        self.assertEqual(set(mapping), set(historical.SOURCES))
        for source in historical.SOURCES:
            with self.subTest(source=source):
                self.assertEqual(explorer.public_evidence_url(source, ROOT),
                                 explorer.GITHUB + mapping[source])
        unrelated = 'results/unrelated.jsonl'
        self.assertEqual(explorer.public_evidence_url(unrelated, ROOT),
                         explorer.GITHUB + unrelated)


if __name__ == '__main__':
    unittest.main()
