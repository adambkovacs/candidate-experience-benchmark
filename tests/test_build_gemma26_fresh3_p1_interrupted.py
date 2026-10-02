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
import build_gemma26_fresh3_p1_interrupted as report


class GemmaP1InterruptedReportTests(unittest.TestCase):
    def projection(self):
        return json.loads((ROOT / report.PROJECTION).read_text())

    def test_private_export_accounts_for_59_prefix_plus_one_successor(self):
        attempt, stage_hashes, other_hashes = report.private_suffix_gate()
        self.assertEqual(attempt['id'], 'DEV-060')
        self.assertEqual(attempt['status'], 'ok')
        self.assertEqual(set(stage_hashes), set(report.suffix.PREFIX_FILES))
        self.assertEqual(set(other_hashes), {'review', 'budget', 'child'})
        projection = self.projection()
        self.assertEqual([r['id'] for r in projection['responses']], report.IDS)
        self.assertEqual({r['status'] for r in projection['responses']}, {'ok', 'service_error'})
        self.assertEqual([r['id'] for r in projection['responses'] if r['status'] != 'ok'],
                         ['DEV-059'])
        self.assertEqual({frozenset(r) for r in projection['responses']},
                         {frozenset(report.PUBLIC_KEYS)})
        self.assertNotRegex(json.dumps(projection),
                            r'raw_response|body_base64|feedback|api_key|error_body|error_headers')

    def test_public_projection_needs_exact_manual_review_and_source_hashes(self):
        projection = self.projection()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = (report.PROJECTION, report.BASE / 'fresh3/manifest.json',
                       report.suffix.MANIFEST.relative_to(ROOT),
                       report.suffix.TERMINAL.relative_to(ROOT),
                       report.suffix.TERMINAL_REVIEW.relative_to(ROOT),
                       report.suffix.OLD_RECONCILIATION.relative_to(ROOT))
            for relative in sources:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            review_path = root / report.REVIEW
            with self.assertRaisesRegex(ValueError, 'Missing P1 public source'):
                report.public_projection(root, [])
            review = {'schema': report.SCHEMA + '-terminal-public-review-v1',
                      'approved': True, 'reviewer': 'root', 'terminalExitCode': 0,
                      'attemptedCount': 60,
                      'projectionSha256': report.sha(root / report.PROJECTION),
                      'privateSourceSha256': projection['privateSourceSha256']}
            review_path.write_text(json.dumps(review))
            self.assertEqual(len(report.public_projection(root, [])), 60)
            review['projectionSha256'] = '0' * 64
            review_path.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, 'privacy review differs'):
                report.public_projection(root, [])

    def test_fixed60_p1_analysis_keeps_failed_position(self):
        saved = self.projection()['responses']
        plan = json.loads((ROOT / report.BASE / 'fresh3/manifest.json').read_text())
        normalized = report.normalize_third(saved, plan['conditions']['P1']['development'])
        self.assertEqual(normalized['DEV-059'], {'status': 'service_error', 'prediction': None})
        with patch.object(report, 'public_projection', return_value=saved):
            feed = report.build()
        p1 = feed['conditions']['P1']
        self.assertEqual(feed['scoredSeriesConditions'], 9)
        self.assertFalse(feed['cleanMatchedThreeEligible'])
        self.assertEqual(p1['fixed60Scores']['fresh3']['denominator'], 60)
        self.assertEqual(p1['fixed60Scores']['fresh3']['valid'], 59)
        self.assertEqual(p1['fixed60Scores']['fresh3']['outcomes']['service_error'], 1)
        self.assertEqual(p1['failureIdsByPass']['fresh3'], ['DEV-059'])
        self.assertEqual(p1['thirdPassUsage']['missingCostCount'], 1)
        self.assertEqual(p1['thirdPassUsage']['reportedKnownCostUsd'], '0.01941923')
        self.assertTrue(p1['thirdPassUsage']['reportedReasoningExceedsCompletion'])

    def test_tampered_dev059_or_dev060_rows_rejected(self):
        saved = self.projection()['responses']
        requests = json.loads((ROOT / report.BASE / 'fresh3/manifest.json').read_text())[
            'conditions']['P1']['development']
        for position, field, value in ((58, 'status', 'ok'),
                                       (58, 'observedCostUsd', '0.0001'),
                                       (59, 'requestSha256', '0' * 64),
                                       (59, 'id', 'DEV-059')):
            altered = copy.deepcopy(saved)
            altered[position][field] = value
            with self.assertRaises(ValueError):
                report.normalize_third(altered, requests)

    def test_saved_feed_rebuilds_from_reviewed_sources(self):
        saved = json.loads((ROOT / report.OUTPUT).read_text())
        self.assertEqual(report.build(), saved)
        self.assertEqual(saved['conditions']['P1']['fixed60Scores']['fresh3']['valid'], 59)
        for binding in saved['sourceBindings']:
            self.assertEqual(report.sha(ROOT / binding['path']), binding['sha256'])
        self.assertNotRegex(json.dumps(saved),
                            r'raw_response|body_base64|api_key|error_headers|feedback')


if __name__ == '__main__':
    unittest.main()
