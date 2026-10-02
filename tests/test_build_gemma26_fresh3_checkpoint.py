import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_gemma26_fresh3_checkpoint as report


def prior_inputs():
    first = json.loads((ROOT / report.FIRST_FEED).read_text())
    second = json.loads((ROOT / report.SECOND_FEED).read_text())
    requests = {name: json.loads((ROOT / report.BASE / name / 'manifest.json').read_text())
                ['conditions']['P0']['development'] for name in report.p2.PASSES}
    original = report.rows(ROOT / report.FIRST_P0)
    prefix = report.rows(ROOT / report.SECOND_P0_PREFIX)
    suffix = json.loads((ROOT / report.SECOND_P0_SUFFIX).read_text())['responses']
    records = {'fresh1': report.normalize(original, requests['fresh1']),
               'fresh2': report.normalize(prefix + suffix, requests['fresh2'])}
    labels = {row['id']: row['proposed_labels'] for row in report.rows(ROOT / report.LABELS)}
    published = {'condition': 'P0',
                 'fresh1': first['passes']['fresh1']['P0']['score'],
                 'fresh2': second['compositeP0']['score']}
    return records, labels, published, requests


class GemmaFresh3CheckpointTests(unittest.TestCase):
    def test_prior_fixed60_scores_and_failure_denominator(self):
        records, labels, published, _ = prior_inputs()
        records['fresh3'] = copy.deepcopy(records['fresh1'])
        result = report.analyze(records, labels, published)
        self.assertEqual(result['fixed60Scores']['fresh1']['allFour'], 59)
        self.assertEqual(result['fixed60Scores']['fresh2']['allFour'], 56)
        self.assertEqual(result['failureIdsByPass']['fresh2'], ['DEV-002'])
        self.assertEqual(result['allThreeSharedValid']['denominator'], 59)
        self.assertEqual(result['allThreeSharedValid']['excludedIds'], ['DEV-002'])
        self.assertEqual([row['denominator'] for row in result['pairwiseAvailableValid']],
                         [59, 59, 60])
        self.assertEqual(result['fixed60Ranges']['allFour'],
                         {'min': 56, 'max': 59, 'spread': 3})

    def test_equal_aggregate_with_different_record_flip_is_visible(self):
        records, labels, published, _ = prior_inputs()
        records['fresh3'] = copy.deepcopy(records['fresh1'])
        baseline = report.analyze(records, labels, published)
        altered = copy.deepcopy(records)
        rid = next(rid for rid in report.IDS if rid != 'DEV-002' and
                   report.p2.all_match(altered['fresh3'][rid]['prediction'], labels[rid]))
        altered['fresh3'][rid]['prediction']['follow_up_needed'] = (
            'no' if labels[rid]['follow_up_needed'] != 'no' else 'yes')
        changed = report.analyze(altered, labels, published)
        self.assertIn(rid, changed['allThreeSharedValid']['pairwise'][2]
                      ['changedFourFieldVectorIds'])
        self.assertNotEqual(baseline['fixed60Scores']['fresh3'],
                            changed['fixed60Scores']['fresh3'])

    def test_projection_requires_exact_root_review_and_source_hash(self):
        _, _, _, requests = prior_inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (report.BASE / 'fresh3/manifest.json',
                             report.BASE / 'fresh3-p0-p1-composite-successor-v1/manifest.json'):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            folder = root / report.CHECKPOINT / 'P0'
            folder.mkdir(parents=True)
            source = {key: '0' * 64 for key in ('claim', 'review', 'journal',
                                                'attempts', 'responses', 'wire')}
            projected = [{'id': request['record_id'],
                          'requestSha256': request['request_sha256'],
                          'status': 'ok', 'prediction': None}
                         for request in requests['fresh3']]
            projection = {'schema': report.SCHEMA + '-projection-v1',
                          'stage': 'fresh3/P0/development', 'condition': 'P0',
                          'planSha256': report.sha(root / report.BASE / 'fresh3/manifest.json'),
                          'admissionManifestSha256': report.sha(root / report.BASE /
                              'fresh3-p0-p1-composite-successor-v1/manifest.json'),
                          'manualPrivacyReviewRequired': True,
                          'privateSourceSha256': source, 'responses': projected}
            projection_path = folder / 'public-projection.json'
            projection_path.write_text(json.dumps(projection))
            with self.assertRaisesRegex(ValueError, 'Missing checkpoint source'):
                report.projected_rows(root, 'P0', [])
            review = {'schema': report.SCHEMA + '-terminal-public-review-v1',
                      'approved': True, 'condition': 'P0', 'terminalExitCode': 0,
                      'attemptedCount': 60, 'projectionSha256': report.sha(projection_path),
                      'privateSourceSha256': source, 'reviewer': 'root'}
            review_path = folder / 'terminal-public-review.json'
            review_path.write_text(json.dumps(review))
            self.assertEqual(len(report.projected_rows(root, 'P0', [])), 60)
            review['terminalExitCode'] = 1
            review_path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'review differ'):
                report.projected_rows(root, 'P0', [])
            review['terminalExitCode'] = 0
            review_path.write_text(json.dumps(review))
            projection['responses'][0]['id'] = 'DEV-002'
            projection_path.write_text(json.dumps(projection))
            with self.assertRaisesRegex(ValueError, 'review differ'):
                report.projected_rows(root, 'P0', [])

    def test_duplicate_missing_or_failed_prior_position_rejected(self):
        records, labels, published, requests = prior_inputs()
        records['fresh3'] = copy.deepcopy(records['fresh1'])
        bad = copy.deepcopy(records)
        bad['fresh2']['DEV-002'] = copy.deepcopy(bad['fresh2']['DEV-003'])
        with self.assertRaisesRegex(ValueError, 'score differs|failure differs'):
            report.analyze(bad, labels, published)
        public = [{'id': request['record_id'],
                   'requestSha256': request['request_sha256'],
                   'status': 'ok', 'prediction': labels[request['record_id']]}
                  for request in requests['fresh3']]
        public[0]['requestSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'request identity'):
            report.normalize(public, requests['fresh3'])

    def test_export_requires_real_closed_phase(self):
        with patch.object(report.frozen, 'verify_phase_closure',
                          side_effect=ValueError('incomplete phase')):
            with self.assertRaisesRegex(ValueError, 'incomplete phase'):
                report.export_projection('P0')

    def test_closed_p0_projection_matches_prior_sources_and_fixed60_preview(self):
        projection = json.loads((ROOT / report.CHECKPOINT / 'P0/public-projection.json').read_text())
        self.assertEqual([row['id'] for row in projection['responses']], report.IDS)
        self.assertEqual({row['status'] for row in projection['responses']}, {'ok'})
        self.assertEqual({frozenset(row) for row in projection['responses']},
                         {frozenset(report.second.PUBLIC_KEYS)})
        with patch.object(report, 'projected_rows',
                          return_value=projection['responses']):
            preview = report.build()
        condition = preview['conditions']['P0']
        self.assertEqual(preview['scoredSeriesConditions'], 8)
        self.assertEqual([(condition['fixed60Scores'][name]['allFour'],
                           condition['fixed60Scores'][name]['valid'])
                          for name in report.p2.PASSES],
                         [(59, 60), (56, 59), (58, 60)])
        self.assertEqual(condition['allThreeSharedValid']['denominator'], 59)
        self.assertEqual([pair['changedFourFieldVectorCount'] for pair in
                          condition['allThreeSharedValid']['pairwise']], [4, 3, 1])
        self.assertNotIn('raw_response', json.dumps(preview))
        self.assertNotIn('body_base64', json.dumps(preview))

    def test_published_p0_rebuilds_from_reviewed_public_sources(self):
        saved = json.loads((ROOT / report.OUTPUTS['P0']).read_text())
        self.assertEqual(report.build(), saved)
        self.assertEqual(saved['schema'], report.SCHEMA)
        self.assertEqual(saved['cutoff'], 'P0')
        self.assertEqual(saved['scoredSeriesConditions'], 8)
        self.assertEqual(saved['conditions']['P0']['thirdPassUsage']
                         ['reportedKnownCostUsd'], '0.01918032')
        self.assertTrue(saved['conditions']['P0']['thirdPassUsage']
                        ['reportedReasoningExceedsCompletion'])
        for binding in saved['sourceBindings']:
            self.assertEqual(report.sha(ROOT / binding['path']), binding['sha256'])
        self.assertNotRegex(json.dumps(saved),
                            r'raw_response|body_base64|api_key|provider_headers|feedback')


if __name__ == '__main__':
    unittest.main()
