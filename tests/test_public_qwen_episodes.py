"""Public Qwen episode view preserves the interrupted evidence boundary."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_public_explorer as explorer


class QwenEpisodePublicTests(unittest.TestCase):
    def test_closed_public_view_keeps_failures_bounds_and_private_boundary(self):
        saved, paths, known, unknown, failures = explorer.qwen_on_p2_episode_public_view(ROOT)
        self.assertEqual([row['id'] for row in saved], [f'DEV-{i:03}' for i in range(1, 61)])
        self.assertEqual(sum(row['status'] == 'ok' for row in saved), 54)
        self.assertEqual([row['id'] for row in saved if row['status'] == 'service_error'], failures)
        self.assertEqual(str(known), '0.0628516')
        self.assertEqual(str(unknown), '0.1794048')
        self.assertIn(Path('results/qwen36-on-p2-never-sent-episodes-v1/episode-001/responses.public.jsonl'), paths)
        self.assertNotIn(Path('results/qwen36-on-p2-never-sent-episodes-v1/episode-001/responses.jsonl'), paths)
        self.assertTrue(all(set(row) <= {'id', 'status', 'prediction', 'elapsed_seconds', 'usage'}
                            for row in saved[42:]))

    def test_public_response_mutation_fails_closed_without_private_original(self):
        _, paths, _, _, _ = explorer.qwen_on_p2_episode_public_view(ROOT)
        extra = [Path('results/hosted-final-suffix-reconciled-v3/qwen36-on-p2.json'),
                 Path('results/qwen36-on-p2-final19-v4/reconciliation.json')]
        for index in (1, 2):
            report = json.loads((ROOT / f'results/qwen36-on-p2-never-sent-episodes-v1/episode-{index:03}/reconciliation.json').read_text())
            extra.extend(Path(binding['file']) for binding in report['evidence'].values()
                         if not (index == 1 and binding['file'].endswith('/responses.jsonl')))
            extra.extend(Path(report[key]['file']) for key in ('budget_manifest', 'child_ledger'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in set(paths + extra):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            public = root / 'results/qwen36-on-p2-never-sent-episodes-v1/episode-001/responses.public.jsonl'
            public.write_bytes(public.read_bytes() + b'\n')
            with self.assertRaisesRegex(ValueError, 'public redaction boundary'):
                explorer.qwen_on_p2_episode_public_view(root)

    def test_explorer_uses_closed_composite_without_publishing_private_response(self):
        value = explorer.export(ROOT)
        run = next(row for row in value['runs'] if row['id'] == 'openrouter-paid-qwen36-35b-a3b-on--p2')
        self.assertEqual((run['records'], run['valid'], run['neverSent']), (60, 54, 0))
        self.assertEqual(run['statusCounts'], {'ok': 54, 'service_error': 6})
        self.assertFalse(run['pairedEligible'])
        self.assertIsNone(run['cost']['actualUsd'])
        self.assertEqual(run['cost']['unknownUpperBoundUsd'], '0.1794048')
        self.assertEqual(len([case for case in value['cases'] if case['configuration'] == run['id']]), 60)
        self.assertTrue(run['sourceViews'])
        self.assertFalse(any('episode-001/responses.jsonl' in url for url in run['evidenceSources']))
        self.assertTrue(any('episode-001/responses.public.jsonl' in url for url in run['evidenceSources']))
        self.assertNotIn('user_id', json.dumps(run))


if __name__ == '__main__':
    unittest.main()
