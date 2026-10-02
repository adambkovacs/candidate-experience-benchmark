import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_gemma26_postabort_findings as report


class GemmaPostabortFindingsTests(unittest.TestCase):
    def test_published_token_conflict_is_explicit(self):
        feed = json.loads((report.ROOT / report.OUTPUT).read_text())
        usage = feed['compositeUsage']
        self.assertGreater(
            usage['tokenAvailability']['reasoning_tokens']['reportedSum'],
            usage['tokenAvailability']['completion_tokens']['reportedSum'])
        self.assertTrue(usage['reportedReasoningExceedsCompletion'])
        self.assertIn('categories conflict', usage['tokenCategoryCaveat'])

    def test_composite_usage_retains_missing_cost_and_token_counts(self):
        rows = [
            {'observedCostUsd': '0.2', 'clientSeconds': 1.0,
             'tokens': {'prompt_tokens': 10, 'completion_tokens': 2,
                        'total_tokens': 12, 'reasoning_tokens': None}},
            {'observedCostUsd': None, 'clientSeconds': 2.0,
             'tokens': {key: None for key in report.TOKEN_KEYS}},
            {'observedCostUsd': '0.3', 'clientSeconds': 3.0,
             'tokens': {'prompt_tokens': 20, 'completion_tokens': 3,
                        'total_tokens': 23, 'reasoning_tokens': 1}},
        ]
        usage = report.composite_usage(rows)
        self.assertEqual(usage['reportedKnownCostUsd'], '0.5')
        self.assertEqual(usage['reportedCostCount'], 2)
        self.assertEqual(usage['missingCostCount'], 1)
        self.assertIsNone(usage['providerBilledUsd'])
        self.assertEqual(usage['clientRequestSecondsTotal'], 6.0)
        self.assertIsNone(usage['pureInferenceSeconds'])
        self.assertEqual(usage['tokenAvailability']['prompt_tokens'],
                         {'reportedSum': 30, 'reportedCount': 2,
                          'missingCount': 1, 'sumAllRequests': None})
        self.assertEqual(usage['tokenAvailability']['reasoning_tokens'],
                         {'reportedSum': 1, 'reportedCount': 1,
                          'missingCount': 2, 'sumAllRequests': None})
        self.assertFalse(usage['reportedReasoningExceedsCompletion'])
        self.assertIn('do not add', usage['tokenCategoryCaveat'])

    def test_closed_source_projection_is_allowlisted(self):
        plan = json.loads((report.ROOT / report.BASE / 'fresh3/manifest.json').read_text())
        requests = plan['conditions']['P2']['development']
        # Synthetic privacy fixture; no private provider error bodies are needed.
        def fixture(request, status):
            return {'id': request['record_id'], 'request_sha256': request['request_sha256'],
                    'request': request['payload'], 'reference_labels_read': False,
                    'status': status, 'billing_ok': True, 'cost_unknown': False,
                    'observed_cost_usd': '0.0001', 'elapsed_seconds': 1.0,
                    'prediction': {'sentiment': 'positive', 'follow_up_needed': 'no',
                        'serious_concern_reported': 'no', 'testimonial_potential': 'yes'},
                    'raw_response': 'private fixture body', 'error_headers': {'x-fixture': 'private'}}
        valid_row = report.projection_row(fixture(requests[0], 'ok'), requests[0])
        failed_row = report.projection_row(fixture(requests[4], 'service_error'), requests[4])
        self.assertEqual(set(valid_row), report.PUBLIC_KEYS)
        self.assertEqual(set(failed_row), report.PUBLIC_KEYS)
        self.assertNotIn('raw_response', json.dumps(valid_row))
        self.assertNotIn('error_headers', json.dumps(failed_row))
        self.assertEqual(failed_row['status'], 'service_error')
        self.assertIsNone(failed_row['prediction'])

    def test_intrinsic_invalid_last_position_is_preserved(self):
        plan = json.loads((report.ROOT / report.BASE / 'fresh3/manifest.json').read_text())
        request = plan['conditions']['P2']['development'][-1]
        row = report.projection_row({
            'id': 'DEV-060', 'request_sha256': request['request_sha256'],
            'request': request['payload'], 'reference_labels_read': False,
            'status': 'invalid_output', 'elapsed_seconds': 1.5,
            'observed_cost_usd': '0.0001'}, request)
        self.assertEqual(row['status'], 'invalid_output')
        self.assertIsNone(row['prediction'])
        self.assertNotIn('request', row)

    def test_failed_cost_must_be_numeric_not_provider_text(self):
        plan = json.loads((report.ROOT / report.BASE / 'fresh3/manifest.json').read_text())
        request = plan['conditions']['P2']['development'][-1]
        raw = {'id': 'DEV-060', 'request_sha256': request['request_sha256'],
            'request': request['payload'], 'reference_labels_read': False,
            'status': 'service_error', 'elapsed_seconds': 1.5,
            'observed_cost_usd': 'secret-text'}
        with self.assertRaises(Exception):
            report.projection_row(raw, request)

    def test_missing_or_unreconciled_terminal_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in (report.AUDIT, report.FOURTH_TERMINAL,
                        report.FIFTH_TERMINAL, report.THIRD_PUBLIC,
                        report.successor.BASE.relative_to(report.ROOT) / 'manifest.json'):
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report.ROOT / rel, dest)
            with self.assertRaisesRegex(ValueError, 'Missing evidence'):
                report.terminal_gate(root, [])
            terminal = root / report.TERMINAL
            terminal.parent.mkdir(parents=True, exist_ok=True)
            terminal.write_text(json.dumps({
                'schema': 'gemma26-on-v2-postabort-suffix-terminal-reconciliation-v1',
                'status': 'terminal_completed_composite_phase_unscored',
                'attempted_ids': report.IDS[53:60],
                'counts': {'valid': 7, 'failed': 0, 'never_sent_stage': 0},
                'score': None, 'reference_labels_read': False,
                'manifest_sha256': report.sha(root /
                    report.successor.BASE.relative_to(report.ROOT) / 'manifest.json'),
                'partition_id': report.successor.PARTITION_ID,
                'budget_reconciliation': {'event': 'not_reconciled',
                    'partition_id': report.successor.PARTITION_ID,
                    'known_actual_usd': '0', 'unknown_upper_bound_usd': '0',
                    'child_sha256': '0' * 64}}))
            with self.assertRaisesRegex(ValueError, 'not reconciled'):
                report.terminal_gate(root, [])

    def test_sealed_child_missing_or_hash_changed_blocks_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for rel in (report.AUDIT, report.FOURTH_TERMINAL,
                        report.FIFTH_TERMINAL, report.THIRD_PUBLIC,
                        report.TERMINAL,
                        report.successor.BASE.relative_to(report.ROOT) / 'manifest.json',
                        report.successor.CHILD.relative_to(report.ROOT)):
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report.ROOT / rel, dest)
            self.assertEqual(report.terminal_gate(root, [])['attempted_ids'],
                             report.IDS[53:60])
            child = root / report.successor.CHILD.relative_to(report.ROOT)
            original = child.read_bytes()
            child.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing evidence'):
                report.terminal_gate(root, [])
            child.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                report.terminal_gate(root, [])

    def test_fixed_sixty_composite_includes_intrinsic_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_files = [
                Path('scripts/build_gemma26_postabort_findings.py'),
                report.successor.BASE.relative_to(report.ROOT) / 'manifest.json',
                report.successor.study.BASE.relative_to(report.ROOT) / 'fresh3/manifest.json',
                report.first_report.LABELS,
                report.THIRD_PUBLIC, report.FOURTH_TERMINAL,
                report.FIFTH_TERMINAL, report.AUDIT,
            ]
            for rel in source_files:
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(report.ROOT / rel, dest)
            plan = json.loads((root / source_files[2]).read_text())
            labels = {r['id']: r['proposed_labels'] for r in
                      report.first_report.rows(root / report.first_report.LABELS)}
            rows = []
            for request in plan['conditions']['P2']['development']:
                rid = request['record_id']
                status = ('service_error' if rid in ('DEV-005', 'DEV-006') else
                          'invalid_output' if rid == 'DEV-060' else 'ok')
                rows.append({'id': rid, 'requestSha256': request['request_sha256'],
                    'status': status, 'prediction': labels[rid] if status == 'ok' else None,
                    'observedCostUsd': '0' if status == 'ok' else None,
                    'clientSeconds': 1.0,
                    'tokens': {key: None for key in report.TOKEN_KEYS}})
            (root / report.TERMINAL).parent.mkdir(parents=True, exist_ok=True)
            (root / report.TERMINAL).write_text('{}\n')
            projection = {'schema': report.SCHEMA + '-projection-v1',
                'status': 'awaiting_manual_public_review',
                'manualPrivacyReviewRequired': True,
                'frozenPlanSha256': report.successor.first.PLAN_SHAS['fresh3'],
                'terminalSha256': report.sha(root / report.TERMINAL),
                'successorManifestSha256': report.sha(root / source_files[1]),
                'privateSourceSha256': json.loads(
                    (report.ROOT / report.PROJECTION).read_text())['privateSourceSha256'],
                'responses': rows}
            (root / report.PROJECTION).write_text(json.dumps(projection) + '\n')
            (root / report.PUBLIC_REVIEW).write_text(json.dumps({
                'schema': report.SCHEMA + '-public-review-v1', 'approved': True,
                'projectionSha256': report.sha(root / report.PROJECTION)}) + '\n')
            terminal = {'counts': {'valid': 6, 'failed': 1},
                'source_sha256': json.loads((report.ROOT / report.TERMINAL).read_text())[
                    'source_sha256'],
                'budget_reconciliation': {'known_actual_usd': '0.003',
                                          'unknown_upper_bound_usd': '0.01974272'}}
            previous = {'completedConditions': 6, 'configuration': 'test',
                        'sourceBindings': []}
            with patch.object(report.second_report, 'build', return_value=previous), \
                 patch.object(report, 'terminal_gate', return_value=terminal):
                value = report.build(root)
                (root / report.PUBLIC_REVIEW).unlink()
                with self.assertRaisesRegex(ValueError, 'Missing evidence'):
                    report.build(root)
            self.assertEqual(value['completedConditions'], 7)
            self.assertEqual(value['fresh3P2']['score']['saved'], 60)
            self.assertEqual(value['fresh3P2']['score']['valid'], 57)
            self.assertEqual(value['fresh3P2']['failedIds'],
                             ['DEV-005', 'DEV-006', 'DEV-060'])
            self.assertFalse(value['cleanMatchedThreeEligible'])
            self.assertEqual(value['compositeUsage']['reportedCostCount'], 57)
            self.assertEqual(value['compositeUsage']['missingCostCount'], 3)
            self.assertIsNone(value['compositeUsage']['pureInferenceSeconds'])


if __name__ == '__main__':
    unittest.main()
