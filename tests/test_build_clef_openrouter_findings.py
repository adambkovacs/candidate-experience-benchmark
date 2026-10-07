"""Closed-only OpenRouter Clef/Flash public projection checks."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import build_clef_openrouter_findings as findings
from scripts import clef_openrouter_native_v1 as route
from scripts import clef_openrouter_full_v1 as full
from scripts.development_benchmark import ROOT


class ClefOpenRouterFindingsTests(unittest.TestCase):
    def isolated_public_copy(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        receipt = findings.read_json(ROOT / findings.RECEIPT)
        paths = set(findings.SOURCE_FILES) | {
            str(findings.PROJECTION), str(findings.RECEIPT), str(findings.OUTPUT)}
        paths.update(name for name in receipt['source_sha256']
                     if name.endswith('smoke.root-inspection.json'))
        for name in paths:
            src, dst = ROOT / name, root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        return root

    def test_first_pass_closed_scores_are_reconstructible(self):
        result = findings.check(ROOT)
        self.assertIn({'model_key': 'clef', 'stage': 'fresh1/P0'}, result['included_stages'])
        self.assertIn({'model_key': 'clef-flash', 'stage': 'fresh1/P0'}, result['included_stages'])
        by = {stage['model_key']: stage for stage in result['stages']
              if stage['stage'] == 'fresh1/P0'}
        self.assertEqual(by['clef']['all_four_correct'], 54)
        self.assertEqual(by['clef-flash']['all_four_correct'], 45)
        self.assertEqual(by['clef']['observed_known_cost_usd'], '0.03184656')
        self.assertEqual(by['clef-flash']['observed_known_cost_usd'], '0.01194246')
        self.assertEqual({k: by['clef']['fields'][k]['correct'] for k in findings.KEYS},
                         dict(zip(findings.KEYS, (56, 59, 56, 58))))
        self.assertEqual({k: by['clef-flash']['fields'][k]['correct'] for k in findings.KEYS},
                         dict(zip(findings.KEYS, (50, 57, 56, 57))))
        for comparison in result['comparisons']:
            self.assertEqual(comparison['shared_valid_denominator'], 60)
        self.assertNotIn('Cloudflare direct', result['route'])

    def test_public_checkout_and_tampered_projection(self):
        root = self.isolated_public_copy()
        findings.check(root)
        path = root / findings.PROJECTION
        projection = json.loads(path.read_text())
        projection['stages'][0]['records'][0]['prediction']['sentiment'] = 'negative'
        findings.write_json(path, projection)
        with self.assertRaisesRegex(ValueError, 'Projection receipt differs'):
            findings.check(root)

    def test_public_projection_omits_feedback_and_raw_response(self):
        projection = findings.read_json(ROOT / findings.PROJECTION)
        for stage in projection['stages']:
            for record in stage['records']:
                self.assertTrue(record['id'].startswith('DEV-'))
                self.assertFalse({'feedback', 'user_id', 'response_base64', 'raw_response'} & set(record))

    def test_present_private_file_must_match_immutable_hash(self):
        root = self.isolated_public_copy()
        private = next(name for name in findings.read_json(root / findings.RECEIPT)['source_sha256']
                       if name.endswith('development.parsed.jsonl'))
        target = root / private
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('changed\n')
        with self.assertRaisesRegex(ValueError, 'Bound source changed'):
            findings.check(root)

    def test_interrupted_or_incomplete_journal_is_rejected(self):
        source = ROOT / full.BASE / 'clef/fresh1/P0/development.raw.jsonl'
        if not source.exists():
            self.skipTest('Private raw evidence absent in public checkout')
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in findings.stage_paths('clef', 'fresh1/P0').values():
                dst = root / file
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / file, dst)
            for file in ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl',
                         'root-inspection.json'):
                src = ROOT / route.BASE / 'clef/fresh1/P0' / ('smoke.' + file)
                dst = root / route.BASE / 'clef/fresh1/P0' / ('smoke.' + file)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
            dst = root / full.REVIEW
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / full.REVIEW, dst)
            journal = root / findings.stage_paths('clef', 'fresh1/P0')['journal.jsonl']
            journal.write_text('\n'.join(journal.read_text().splitlines()[:-1]) + '\n')
            plan = findings.read_json(ROOT / route.PLAN)
            _, route_sha = route.verify(ROOT)
            _, full_sha = full.verify(ROOT)
            with self.assertRaisesRegex(ValueError, 'not a closed 60-record'):
                findings.private_stage(root, plan, full_sha, route_sha, 'clef', 'fresh1/P0')

    def test_comparison_counts_gains_losses_and_record_flips(self):
        truth = findings.labels(ROOT)
        base = [{'id': rid, 'prediction': dict(truth[rid])} for rid in route.IDS]
        altered = json.loads(json.dumps(base))
        altered[0]['prediction']['sentiment'] = 'negative' if truth['DEV-001']['sentiment'] != 'negative' else 'positive'
        result = findings.compare({'model_key': 'clef', 'stage': 'fresh1/P0', 'records': base},
                                  {'model_key': 'clef', 'stage': 'fresh1/P1', 'records': altered},
                                  truth, 'paired_prompt')
        self.assertEqual(result['shared_valid_denominator'], 60)
        self.assertEqual(result['changed_prediction_ids'], ['DEV-001'])
        self.assertEqual(result['all_four_lost_ids'], ['DEV-001'])
        self.assertEqual(result['all_four_gained_ids'], [])


if __name__ == '__main__':
    unittest.main()
