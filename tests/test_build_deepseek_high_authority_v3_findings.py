"""Closed DeepSeek high P0 must remain source-bound and retain its invalid result."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_qwen36_on_hosted_authority_v2_findings as prior
import build_deepseek_high_authority_v3_findings as report


class DeepSeekHighFindingsTests(unittest.TestCase):
    def test_existing_series_preserved_and_p0_is_closed_with_invalid(self):
        value = report.build(ROOT)
        previous = prior.build(ROOT)
        self.assertEqual(value['series'][:len(previous['series'])], previous['series'])
        self.assertEqual(len(value['series']), len(previous['series']) + 1)
        item = value['series'][-1]
        self.assertEqual(item['configuration'], report.CONFIG)
        self.assertEqual(item['completedConditions'],
                         sum(len(phases) for phases in item['passes'].values()))
        self.assertEqual(item['cleanCompletedConditions'],
                         sum(phase['status'] == 'completed'
                             for phases in item['passes'].values()
                             for phase in phases.values()))
        self.assertEqual(len(item['missingPasses']), 9 - item['completedConditions'])
        self.assertTrue(all(x['status'] == 'not_published' for x in item['missingPasses']))
        self.assertIn('P0', item['passes']['fresh1'])
        phase = item['passes']['fresh1']['P0']
        self.assertEqual(phase['status'], 'completed_with_intrinsic_invalid')
        self.assertEqual(phase['score']['allFour'], 57)
        self.assertEqual(phase['score']['valid'], 59)
        self.assertEqual(phase['score']['invalidIds'], ['DEV-030'])
        self.assertEqual(phase['score']['outcomes'], {'ok': 59, 'invalid_output': 1})
        self.assertEqual(phase['usage']['actualCostUsd'], '0.034324790897')
        paths = {x['path'] for x in item['sourceBindings']}
        self.assertIn(str(report.FOLDER / 'closure-ledger-snapshot.jsonl'), paths)
        self.assertNotIn(str(report.BASE / 'budget-deepseek-high-authority-v3-fresh123.jsonl'), paths)
        self.assertFalse(any(path.endswith('budget-deepseek-high-authority-v3-fresh123.jsonl')
                             for path in paths))

    def test_missing_immutable_snapshot_rejected(self):
        original = report.existing.bind
        snapshot = report.FOLDER / 'closure-ledger-snapshot.jsonl'
        def changed(root, relative, bindings, expected=None):
            if str(relative) == str(snapshot):
                raise ValueError('DeepSeek report source hash differs: snapshot')
            return original(root, relative, bindings, expected)
        with patch.object(report.existing, 'bind', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'snapshot'):
                report.build(ROOT)

    def test_invalid_prediction_cannot_be_silently_repaired(self):
        original = report.existing.rows
        target = report.FOLDER / 'development.attempts.jsonl'
        def changed(root, relative):
            values = original(root, relative)
            if relative == target:
                values[29]['status'] = 'ok'
            return values
        with patch.object(report.existing, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'classification'):
                report.build(ROOT)

    def test_existing_publication_keeps_closed_p0_while_builder_develops(self):
        published = json.loads((ROOT / 'public-site/additional-hosted-fresh-repeats.json').read_text())
        current = report.build(ROOT)
        for old, new in zip(published['series'][:2], current['series'][:2]):
            self.assertEqual(old['configuration'], new['configuration'])
        published_high = next(item for item in published['series']
                              if item['configuration'] == report.CONFIG)
        current_high = next(item for item in current['series']
                            if item['configuration'] == report.CONFIG)
        self.assertEqual(published_high['passes']['fresh1']['P0'],
                         current_high['passes']['fresh1']['P0'])
        self.assertIn('P0', current_high['passes']['fresh1'])

    def test_synthetic_future_stage_requires_approved_source_bound_closure(self):
        # The fixture is isolated: no P1 closure is written to the real evidence tree.
        with tempfile.TemporaryDirectory(prefix='synthetic-deepseek-stage-') as tmp:
            root = Path(tmp).resolve()
            source = report.FOLDER
            target = report.BASE / 'fresh1/P1'
            plan = json.loads((ROOT / report.BASE / 'fresh1/manifest.json').read_text())
            plan['conditions']['P1']['development'] = plan['conditions']['P0']['development']
            plan_path = root / report.BASE / 'fresh1/manifest.json'
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps(plan))
            plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            for name in ('development.claim.json', 'development.root-review.json',
                         'development.responses.jsonl',
                         'smoke.attempts.jsonl', 'smoke.responses.jsonl',
                         'smoke.journal.jsonl'):
                path = root / target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / source / name, path)
            journal = report.existing.rows(ROOT, source / 'development.journal.jsonl')
            for row in journal:
                if 'condition' in row:
                    row['condition'] = 'P1'
            (root / target / 'development.journal.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in journal))
            attempts = report.existing.rows(ROOT, source / 'development.attempts.jsonl')
            for row in attempts:
                row['condition'] = 'P1'
                row['manifest_sha256'] = plan_sha
            (root / target / 'development.attempts.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in attempts))
            shutil.copyfile(ROOT / source / 'closure-ledger-snapshot.jsonl',
                            root / target / 'closure-ledger-snapshot.jsonl')
            required = [report.BASE / 'execution-manifest.json',
                        report.BASE / 'public-route.json', report.LABELS,
                        Path('scripts/deepseek_high_authority_v3.py')]
            for path in required:
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                if path == report.BASE / 'public-route.json':
                    shutil.copyfile(ROOT / path, destination)
                else:
                    destination.write_text('synthetic fixture source\n')
            paths = [*required, report.BASE / 'fresh1/manifest.json',
                     *(target / name for name in (
                         'development.claim.json', 'development.root-review.json',
                         'development.journal.jsonl', 'development.attempts.jsonl',
                         'development.responses.jsonl', 'smoke.attempts.jsonl',
                         'smoke.responses.jsonl', 'smoke.journal.jsonl',
                         'closure-ledger-snapshot.jsonl'))]
            bindings = {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest()
                        for path in paths}
            closure = {'schema': 'deepseek-high-authority-v3-stage-closure-root-review-v1',
                       'verdict': 'APPROVE', 'independent_review': True,
                       'configuration_id': report.CONFIG, 'stage': 'fresh1/P1/development',
                       'model': report.MODEL, 'provider': report.PROVIDER,
                       'frozen_continue_on_invalid_output': True,
                       'record_count': 60, 'unknown_cost_count': 0,
                       'source_bindings': bindings,
                       'child_ledger_at_review': {
                           'snapshot_path': str(target / 'closure-ledger-snapshot.jsonl'),
                           'sha256': bindings[str(target / 'closure-ledger-snapshot.jsonl')],
                           'settled_attempt_count': 63, 'pending_count': 0},
                       'status_counts': {'ok': 59, 'invalid_output': 1},
                       'valid_count': 59, 'intrinsic_invalid_ids': ['DEV-030'],
                       'all_four_correct_fixed_denominator': 57,
                       'known_development_cost_usd': '0.034324790897'}
            labels = {row['id']: row['proposed_labels']
                      for row in report.existing.rows(ROOT, report.LABELS)}
            bound = []
            bind = lambda path, digest=None: report.existing.bind(root, path, bound, digest)
            stage = report.later_stage(root, plan, 'fresh1', 'P1', closure, bind, labels)
            self.assertEqual(stage['status'], 'completed_with_intrinsic_invalid')
            self.assertEqual(stage['score']['allFour'], 57)
            self.assertEqual(stage['score']['invalidIds'], ['DEV-030'])
            self.assertEqual(len(bound), len(bindings))
            original_bindings = dict(bindings)
            closure['source_bindings'].pop(str(target / 'closure-ledger-snapshot.jsonl'))
            with self.assertRaisesRegex(ValueError, 'closure is not independently verified'):
                report.later_stage(root, plan, 'fresh1', 'P1', closure, bind, labels)
            closure['source_bindings'] = original_bindings
            (root / target / 'closure-ledger-snapshot.jsonl').write_text('tampered\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                report.later_stage(root, plan, 'fresh1', 'P1', closure, bind, labels)


if __name__ == '__main__':
    unittest.main()
