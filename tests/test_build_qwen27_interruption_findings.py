"""Evidence checks for the two stopped Qwen27 fresh3/P0 runs."""
import base64
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
import build_qwen27_interruption_findings as findings


class Qwen27InterruptionFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = findings.build()

    def test_stopped_denominators_null_scores_and_sealed_bounds(self):
        report = self.report
        self.assertEqual(report['schema'], findings.SCHEMA)
        for suffix, valid, failed, unsent, known, cap in (
                ('medium', 21, 'DEV-022', 38, '0.025301700', '1.00'),
                ('xhigh', 36, 'DEV-037', 23, '0.036876300', '0.80')):
            with self.subTest(suffix=suffix):
                row = report['series'][suffix]
                self.assertEqual((row['valid'], row['failedId'], row['neverSent']),
                                 (valid, failed, unsent))
                self.assertEqual(row['valid'] + row['attemptedUnknown'] +
                                 row['neverSent'], 60)
                self.assertIsNone(row['score'])
                self.assertFalse(row['strictCompletePass'])
                self.assertEqual(row['knownObservedStageCostUsd'], known)
                self.assertEqual(row['unknownStageCostUpperBoundUsd'], '0.047001600')
                self.assertEqual(row['budget']['capUsd'], cap)
                self.assertEqual(row['neverSentIds'][0],
                                 f'DEV-{int(failed[-3:]) + 1:03d}')
                self.assertEqual(row['neverSentIds'][-1], 'DEV-060')
                self.assertIsNone(row['tokens']['failedRequestUsage'])
                self.assertIsNone(row['timing']['pureInferenceSeconds'])
        serialized = json.dumps(report)
        self.assertNotIn('error_body', serialized)
        self.assertNotIn('raw_response', serialized)
        self.assertEqual(len(report['sourceBindings']), len(set(report['sourceBindings'])))

    def test_frozen_plan_hash_drift_is_rejected(self):
        with patch.dict(findings.PLANS, {'medium': '0' * 64}):
            with self.assertRaises(ValueError):
                findings.build()

    def test_attempt_membership_and_label_marker_drift_are_rejected(self):
        original = findings.jsonl

        def altered(path):
            rows = original(path)
            if str(path).endswith('openrouter-paid-qwen3.8-27b-medium/fresh3/P0/development.attempts.jsonl'):
                rows = copy.deepcopy(rows)
                rows[0]['reference_labels_read'] = True
            return rows

        with patch.object(findings, 'jsonl', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'membership differs'):
                findings.build()

    def test_raw_response_reparse_detects_wire_drift(self):
        original = findings.jsonl

        def altered(path):
            rows = original(path)
            if str(path).endswith('openrouter-paid-qwen3.8-27b-medium/fresh3/P0/development.responses.jsonl'):
                rows = copy.deepcopy(rows)
                body = json.loads(base64.b64decode(rows[0]['body_base64']))
                body['choices'][0]['message']['content'] = '{}'
                rows[0]['body_base64'] = base64.b64encode(json.dumps(body).encode()).decode()
            return rows

        with patch.object(findings, 'jsonl', side_effect=altered):
            with self.assertRaisesRegex(ValueError, 'Captured response differs'):
                findings.build()

    def test_stopped_journal_cannot_claim_completion(self):
        config = 'openrouter-paid-qwen3.8-27b-medium'
        folder = findings.BASE / config / 'fresh3/P0'
        attempts = findings.jsonl(folder / 'development.attempts.jsonl')
        journal = findings.jsonl(folder / 'development.journal.jsonl')
        plan = findings.study.verify(config, 'fresh3', findings.PLANS['medium'])
        journal[-1] = {**journal[-1], 'event': 'phase_completed'}
        with self.assertRaisesRegex(ValueError, 'lifecycle'):
            findings.verify_journal(journal, attempts,
                                    plan['conditions']['P0']['development'][:22], config)

    def test_reconciliation_tamper_and_nonfinite_timing_are_rejected(self):
        config = 'openrouter-paid-qwen3.8-27b-xhigh'
        folder = findings.BASE / config / 'fresh3/P0'
        attempts = findings.jsonl(folder / 'development.attempts.jsonl')
        reconciliation = json.loads((folder / 'terminal-reconciliation.json').read_text())
        reconciliation['unknown_upper_bound_usd'] = '0'
        source = {'development_attempts': findings.bind(folder / 'development.attempts.jsonl')}
        with self.assertRaisesRegex(ValueError, 'Terminal reconciliation differs'):
            findings.verify_child(config, folder, attempts, reconciliation, source)
        with self.assertRaisesRegex(ValueError, 'Invalid client duration'):
            findings.strict_duration(float('nan'))

    def test_relocated_snapshot_rechecks_original_absolute_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp).resolve() / 'snapshot'
            shutil.copytree(ROOT / 'scripts', archive / 'scripts',
                            ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(ROOT / 'results/repeatability-v1/qwen27-fresh-matched3-v2',
                            archive / 'results/repeatability-v1/qwen27-fresh-matched3-v2')
            paths = {'docs/HOST_INTERRUPTION_2026-10-01.md',
                     'results/openrouter-paid-budget.jsonl'}
            for kind in ('medium', 'xhigh'):
                config = 'openrouter-paid-qwen3.8-27b-' + kind
                for repeat in ('fresh1', 'fresh2', 'fresh3'):
                    manifest = (ROOT / 'results/repeatability-v1/qwen27-fresh-matched3-v2' /
                                config / repeat / 'manifest.json')
                    paths.update(item['path'] for item in json.loads(
                        manifest.read_text())['source_bindings'])
            for relative in paths:
                source, target = ROOT / relative, archive / relative
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            relocated = findings.build(archive)
            self.assertEqual(relocated['series'], self.report['series'])
            self.assertEqual(relocated['sourceBindings']['medium_child_ledger']['path'],
                self.report['sourceBindings']['medium_child_ledger']['path'])
            self.assertTrue(all((archive / item['path']).is_file()
                for item in relocated['sourceBindings'].values()))
            public = findings.build_public(archive)
            self.assertEqual(public['series']['medium']['failedId'], 'DEV-022')
            self.assertNotIn('budget', public['series']['medium'])
            self.assertNotIn('budget', public['series']['xhigh'])
            self.assertNotIn('capUsd', json.dumps(public))
            self.assertNotIn('unusedAllocationReleasedUsd', json.dumps(public))
            public_file = archive / 'public-report.json'
            findings.main(['--root', str(archive), '--output', str(public_file)])
            self.assertEqual(json.loads(public_file.read_text()), public)
            self.assertEqual(findings.ROOT, ROOT)
            self.assertEqual(findings.study.ROOT, ROOT)
            budget = archive / 'results/repeatability-v1/qwen27-fresh-matched3-v2/budget-partitions-v1.json'
            changed = json.loads(budget.read_text())
            changed['master_ledger'] = str(archive / 'results/openrouter-paid-budget.jsonl')
            budget.write_text(json.dumps(changed) + '\n')
            with self.assertRaisesRegex(ValueError, 'Bound file changed'):
                findings.build(archive)
            with findings.snapshot(archive):
                config = 'openrouter-paid-qwen3.8-27b-medium'
                stage = findings.BASE / config / 'fresh3/P0'
                sources = {'development_attempts': findings.bind(
                    stage / 'development.attempts.jsonl')}
                with self.assertRaisesRegex(ValueError, 'original master ledger identity'):
                    findings.verify_child(config, stage,
                        findings.jsonl(stage / 'development.attempts.jsonl'),
                        json.loads((stage / 'terminal-reconciliation.json').read_text()),
                        sources)
            changed['master_ledger'] = str(
                findings.ORIGIN / 'results/openrouter-paid-budget.jsonl')
            changed['partitions'][0]['child_ledger'] = str(
                archive / 'results/repeatability-v1/qwen27-fresh-matched3-v2/'
                'budget-partitions-v1-qwen27-medium-v2.jsonl')
            budget.write_text(json.dumps(changed) + '\n')
            with findings.snapshot(archive):
                with self.assertRaisesRegex(ValueError, 'original child ledger identity'):
                    findings.verify_child(config, stage,
                        findings.jsonl(stage / 'development.attempts.jsonl'),
                        json.loads((stage / 'terminal-reconciliation.json').read_text()),
                        sources)
            self.assertEqual(findings.ROOT, ROOT)


if __name__ == '__main__':
    unittest.main()
