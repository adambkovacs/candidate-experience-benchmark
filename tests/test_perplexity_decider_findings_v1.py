"""Mutation checks for the saved Perplexity projection boundary."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import build_perplexity_decider_findings_v1 as findings
import perplexity_decider_full_v1 as full
import perplexity_decider_plan_v1 as route


class ProjectionBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.folder = self.root / 'stage'
        self.folder.mkdir()
        source = ROOT / full.BASE / 'decider/fresh1/P0'
        for part in ('claim.json', 'journal.jsonl', 'raw.jsonl',
                     'attempts.jsonl', 'parsed.jsonl'):
            shutil.copyfile(source / f'development.{part}',
                            self.folder / f'development.{part}')
        plan, self.route_sha = route.verify(ROOT)
        _, self.full_sha = full.verify(ROOT)
        self.expected = plan['models']['decider']['requests']['P0']

    def project(self):
        return findings.phase(self.root, self.folder, 'development',
                              list(route.IDS), self.expected, 'fresh1/P0',
                              self.route_sha, self.full_sha)

    def change_first_row(self, part, edit):
        path = self.folder / f'development.{part}.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        edit(rows[0])
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def test_saved_stage_is_accepted(self):
        self.assertEqual(len(self.project()['records']), 60)

    def test_parsed_prediction_drift_is_rejected(self):
        self.change_first_row('parsed', lambda row: row['prediction'].update(sentiment='neutral'))
        with self.assertRaises(ValueError):
            self.project()

    def test_raw_request_drift_is_rejected(self):
        self.change_first_row('raw', lambda row: row.update(payload_sha256='0' * 64))
        with self.assertRaises(ValueError):
            self.project()

    def test_parsed_usage_drift_is_rejected(self):
        self.change_first_row('parsed', lambda row: row.update(input_tokens=1))
        with self.assertRaises(ValueError):
            self.project()

    def test_reference_exposure_claim_is_rejected(self):
        path = self.folder / 'development.claim.json'
        claim = json.loads(path.read_text())
        claim['reference_labels_sent'] = True
        path.write_text(json.dumps(claim))
        with self.assertRaises(ValueError):
            self.project()


if __name__ == '__main__':
    unittest.main()
