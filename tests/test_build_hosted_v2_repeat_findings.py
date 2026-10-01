import json
import shutil
import subprocess
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_hosted_v2_repeat_findings as report
import export_provider_error_public_evidence as public_export


class HostedV2ReportTests(unittest.TestCase):
    def test_terminal_gate_never_scores_open_or_stopped_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.jsonl'
            self.assertEqual(report.terminal_status(path), 'not_completed')
            path.write_text(json.dumps({'event': 'request_started'}) + '\n')
            self.assertEqual(report.terminal_status(path), 'claimed_in_progress_or_interrupted')
            path.write_text(json.dumps({'event': 'phase_stopped'}) + '\n')
            self.assertEqual(report.terminal_status(path), 'stopped_unscored')
            path.write_text(json.dumps({'event': 'phase_completed'}) + '\n')
            self.assertEqual(report.terminal_status(path), 'completed')

    def test_stopped_status_binds_terminal_journal_and_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'stopped'
            folder.mkdir()
            config = 'openrouter-paid-qwen3.8-27b-medium'
            (folder / 'development.journal.jsonl').write_text(
                json.dumps({'event': 'phase_stopped', 'id': 'DEV-022',
                            'reason': 'service_error', 'utc': '2026-10-01T02:35:47Z'}) + '\n')
            review = folder / 'development.root-review.json'
            review.write_text('{}\n')
            claim = folder / 'development.claim.json'
            claim.write_text(json.dumps({'configuration_id': config, 'series_id': 'qwen27-medium',
                                         'fresh_pass': 'fresh3',
                                         'condition': 'P0', 'phase': 'development',
                                         'manifest_sha256': 'frozen-plan',
                                         'root_review_sha256': report.sha(review)}) + '\n')
            bindings = []
            evidence = report.stopped_evidence(root, folder, config, 'qwen27-medium', 'fresh3', 'P0',
                                               'frozen-plan', bindings)
            self.assertEqual({item['path'] for item in bindings},
                             {'stopped/development.journal.jsonl', 'stopped/development.claim.json',
                              'stopped/development.root-review.json'})
            self.assertEqual(evidence['journal']['sha256'],
                             report.sha(folder / 'development.journal.jsonl'))
            claim.write_text(claim.read_text().replace('frozen-plan', 'wrong-plan'))
            with self.assertRaisesRegex(ValueError, 'claim differs'):
                report.stopped_evidence(root, folder, config, 'qwen27-medium', 'fresh3', 'P0',
                                        'frozen-plan', [])
            claim.write_text(claim.read_text().replace('wrong-plan', 'frozen-plan'))
            (folder / 'development.journal.jsonl').write_text(
                json.dumps({'event': 'phase_stopped', 'id': 'DEV-061',
                            'reason': 'service_error', 'utc': '2026-10-01T02:35:47Z'}) + '\n')
            with self.assertRaisesRegex(ValueError, 'invalid terminal journal'):
                report.stopped_evidence(root, folder, config, 'qwen27-medium', 'fresh3', 'P0',
                                        'frozen-plan', [])

    def test_source_binding_rejects_drift_and_moving_ledgers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'closed.jsonl'
            target.write_text('{}\n')
            bindings = []
            bound = report.bind(root, 'closed.jsonl', bindings)
            self.assertEqual(bound['sha256'], report.sha(target))
            self.assertEqual(report.bind(root, 'closed.jsonl', bindings), bound)
            self.assertEqual(len(bindings), 1)
            target.write_text('{"changed":true}\n')
            with self.assertRaisesRegex(ValueError, 'changed'):
                report.bind(root, 'closed.jsonl', bindings, bound['sha256'])
            with self.assertRaisesRegex(ValueError, 'Moving budget ledger'):
                report.bind(root, 'results/openrouter-paid-budget.jsonl', bindings)
            with self.assertRaisesRegex(ValueError, 'Moving budget ledger'):
                report.bind(root, 'results/repeatability-v1/x/budget-partitions-v1-child.jsonl', bindings)

    def test_audited_private_source_requires_exact_public_attestation(self):
        private, original_sha, _ = next(item for item in public_export.INVENTORY
                                        if 'gemma4-26b-a4b-on-p2/development.jsonl' in item[0])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / public_export.PUBLIC_DIR, root / public_export.PUBLIC_DIR)
            bindings = []
            value = report.bind(root, private, bindings, original_sha)
            self.assertEqual(value['sourceKind'], 'sanitized_public_copy')
            self.assertEqual(value['privateOriginalSha256Attestation'], original_sha)
            self.assertTrue((root / value['path']).is_file())
            with self.assertRaisesRegex(ValueError, 'Source binding escapes'):
                report.bind(root, '../unapproved.jsonl', bindings)
            with self.assertRaisesRegex(ValueError, 'Bound source missing'):
                report.bind(root, 'results/unapproved-private.jsonl', bindings)
            with self.assertRaisesRegex(ValueError, 'Frozen private-source hash differs'):
                report.bind(root, private, bindings, '0' * 64)
            (root / value['path']).write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'Public source hash mismatch'):
                report.bind(root, private, bindings, original_sha)

    def test_clean_committed_export_has_three_complete_nine_slot_matrices(self):
        probe = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'],
                               cwd=ROOT, capture_output=True, text=True, check=False)
        if probe.returncode or probe.stdout.strip() != 'true':
            self.skipTest('Git checkout required for committed-export verification')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'snapshot.tar'
            with archive.open('wb') as output:
                subprocess.run(['git', 'archive', '--format=tar', 'HEAD'], cwd=ROOT,
                               stdout=output, check=True)
            with tarfile.open(archive) as stream:
                stream.extractall(root, filter='data')
            shutil.copy2(ROOT / 'scripts/build_hosted_v2_repeat_findings.py',
                         root / 'scripts/build_hosted_v2_repeat_findings.py')
            feed = report.build(root)
            self.assertEqual(feed['schema'], report.SCHEMA)
            self.assertEqual(len(feed['series']), 3)
            self.assertTrue(any(source.get('sourceKind') == 'sanitized_public_copy'
                                for source in feed['sourceBindings']))
            self.assertFalse(any(source['path'].endswith('openrouter-paid-budget.jsonl') or
                                 'budget-partitions-v1-' in source['path'] and
                                 source['path'].endswith('.jsonl')
                                 for source in feed['sourceBindings']))
            for series in feed['series']:
                slots = {(fresh, condition) for fresh in report.PASSES for condition in report.CONDITIONS}
                scored = {(fresh, condition) for fresh in report.PASSES
                          for condition in series['passes'][fresh]}
                missing = {(entry['pass'], entry['condition']) for entry in series['missingPasses']}
                self.assertEqual(slots, scored | missing)
                self.assertFalse(scored & missing)
                self.assertEqual(series['completedConditions'], len(scored))
                self.assertEqual(series['plannedConditions'], 9)
                for entry in series['missingPasses']:
                    if entry['status'] == 'stopped_unscored':
                        self.assertEqual(set(entry['evidence']), {'journal', 'claim', 'review'})
                        for binding in entry['evidence'].values():
                            self.assertIn(binding, feed['sourceBindings'])

    def test_usage_keeps_reasoning_detail_separate_and_missing_values_unknown(self):
        records = [
            {'usage': {'prompt_tokens': 100, 'completion_tokens': 40,
                       'completion_tokens_details': {'reasoning_tokens': 45}},
             'observed_cost_usd': '0.001', 'elapsed_seconds': 2.5},
            {'usage': {'prompt_tokens': 120, 'completion_tokens': 50},
             'observed_cost_usd': None, 'elapsed_seconds': 3.0},
        ]
        value = report.usage(records)
        self.assertEqual(value['tokens']['prompt_tokens'], 220)
        self.assertEqual(value['tokens']['completion_tokens'], 90)
        self.assertIsNone(value['tokens']['reasoning_output_tokens'])
        self.assertEqual(value['tokenAvailability']['providerReportedReasoningTokens']['missingCount'], 1)
        self.assertEqual(value['providerReasoningTokensAboveCompletionCount'], 1)
        self.assertEqual(value['knownCostUsd'], '0.001')
        self.assertIsNone(value['actualCostUsd'])
        self.assertEqual(value['unknownCostCount'], 1)
        self.assertEqual(value['requestSecondsTotal'], 5.5)

    def test_score_uses_fixed_denominator_and_flips_use_shared_valid(self):
        labels_rows = report.read_jsonl(ROOT / report.LABELS)[:2]
        ids = [row['id'] for row in labels_rows]
        labels = {row['id']: row['proposed_labels'] for row in labels_rows}
        first = [{'id': rid, 'status': 'ok', 'prediction': labels[rid]} for rid in ids]
        second = [{'id': ids[0], 'status': 'ok', 'prediction': labels[ids[0]]},
                  {'id': ids[1], 'status': 'invalid_output', 'prediction': None}]
        result = report.score(first, labels, ids)
        self.assertEqual(result['allFour'], 2)
        self.assertEqual(result['denominator'], 2)
        self.assertEqual(result['valid'], 2)
        with self.assertRaisesRegex(ValueError, 'invalid prediction'):
            report.score(second, labels, ids)
        changed = report.flips(first, second, ids)
        self.assertEqual(changed['denominator'], 1)
        self.assertEqual(changed['excludedIds'], [ids[1]])
        self.assertEqual(changed['fourFieldVector']['changed'], 0)


if __name__ == '__main__':
    unittest.main()
