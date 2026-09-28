"""Synthetic offline fixtures for the native L2 reporter; no model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

SOURCE = Path(os.environ.get('ANYJEV_L2_TEST_REPO', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SOURCE / 'scripts'))
if (SOURCE / 'scripts/build_anyjev_l2_repeat_findings.py').exists():
    import build_anyjev_l2_repeat_findings as report
else:
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_anyjev_l2_repeat_findings',
                                                  '/private/tmp/build_anyjev_l2_repeat_findings.py')
    report = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(report)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def write_lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticL2Report(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths = [
            report.PLAN, report.RUN_MANIFEST, report.CONTROLLER, report.BASE_RUNNER,
            report.PROTOCOL, report.FOLDS, report.LABELS, report.INPUTS,
            Path('scripts/build_repeat_findings.py'),
            Path('scripts/development_benchmark.py'),
            Path('scripts/build_anyjev_l2_repeat_findings.py')]
        paths += [p.relative_to(SOURCE) for p in (SOURCE / report.HISTORY).iterdir() if p.is_file()]
        for relative in paths:
            src = SOURCE / relative
            if relative.name == 'build_anyjev_l2_repeat_findings.py' and not src.exists():
                src = Path('/private/tmp/build_anyjev_l2_repeat_findings.py')
            dst = self.root / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        self.plan = json.loads((self.root / report.PLAN).read_text())
        self.original_root = Path(self.plan['output_dir']).parents[3]
        self.hist = self.root / report.HISTORY
        self.folder = self.root / report.BASE / 'repeat2'
        self.folder.mkdir(parents=True)

    def build(self):
        return report.build(self.root)

    def test_historical_complete_and_both_repeats_pending(self):
        result = self.build()
        self.assertEqual(result['completedConditions'], 1)
        self.assertEqual(result['passes']['original']['P0']['score']['denominator'], 60)
        self.assertEqual(result['passes']['original']['P0']['score']['allFour'], 13)
        self.assertEqual([x['status'] for x in result['missingPasses']],
                         ['not_started', 'plan_not_frozen'])
        self.assertIsNone(result['threePassSummary']['P0']['allFour']['range'])
        for field, matrix in result['confusionCounts']['original'].items():
            self.assertEqual(sum(sum(columns.values()) for columns in matrix.values()), 60, field)
        self.assertIsNone(result['passes']['original']['P0']['usage']['tokens']['input_tokens'])
        self.assertIsNone(result['passes']['original']['P0']['usage']['inferenceSeconds'])
        self.assertIsNone(result['passes']['original']['P0']['usage']['actualCostUsd'])

    def test_historical_hash_tamper_fails_closed(self):
        target = self.hist / 'full.jsonl'
        target.write_bytes(target.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            self.build()

    def test_claimed_or_unknown_stage_remains_unscored(self):
        (self.folder / 'smoke.operations.jsonl').write_text('{"event":"started"}\n')
        (self.folder / 'smoke.raw.jsonl').write_text('{"partial":')
        result = self.build()
        self.assertEqual(result['completedConditions'], 1)
        self.assertEqual(result['missingPasses'][0]['status'], 'claimed_in_progress_or_interrupted')
        self.assertEqual(result['passes']['repeat2'], {})

    def make_closed(self):
        full = [json.loads(x) for x in (self.hist / 'full.jsonl').read_text().splitlines()]
        smoke = full[:3]
        attempts_full = [json.loads(x) for x in (self.hist / 'full.attempts.jsonl').read_text().splitlines()]
        collection = json.loads((self.hist / 'collection-manifest.json').read_text())
        collection['run_manifest_sha256'] = self.plan['run_manifest_sha256']
        for number in range(1, 6):
            artifact = json.loads((self.hist / f'fold-{number}-artifacts.json').read_text())
            artifact['run_manifest_sha256'] = self.plan['run_manifest_sha256']
            write_json(self.folder / f'fold-{number}-artifacts.json', artifact)
        for record in full:
            record['run_manifest_sha256'] = self.plan['run_manifest_sha256']
            record['artifact_sha256'] = digest(self.folder / f'fold-{record["fold"]}-artifacts.json')
        smoke = full[:3]
        attempts_full = [next(x for x in full if x['id'] == a['id']) for a in attempts_full]
        write_lines(self.folder / 'smoke.jsonl', smoke)
        write_lines(self.folder / 'smoke.attempts.jsonl', smoke)
        write_lines(self.folder / 'full.jsonl', full)
        write_lines(self.folder / 'full.attempts.jsonl', attempts_full)
        for stage, records, fit_folds in [('smoke', smoke, (1, 4, 5)),
                                          ('full', attempts_full, (2, 3))]:
            captures = []
            for number in fit_folds:
                artifact = json.loads((self.folder / f'fold-{number}-artifacts.json').read_text())
                for field in report.FIELDS:
                    captures.append({'operation': 'fit_head',
                                     'identity': {'fold': number, 'question': field},
                                     'result': artifact['artifacts'][field]})
            for record in records:
                for field in report.FIELDS:
                    q = record['questions'][field]
                    captures.append({'operation': 'predict',
                                     'identity': {'fold': record['fold'], 'id': record['id'], 'question': field},
                                     'result': [{'level': 'L2', 'probs': q['probs'],
                                                 'diagnostics': q['diagnostics']}]})
            events = [{'event': 'run_started', 'stage': stage,
                       'run_manifest_sha256': self.plan['run_manifest_sha256'],
                       'runner_sha256': self.plan['base_runner_sha256']}]
            for item in captures:
                events.append({'event': 'started', 'operation': item['operation'], **item['identity']})
                events.append({'event': 'finished', 'status': 'ok',
                               'operation': item['operation'], **item['identity']})
            events.append({'event': 'terminal', 'status': 'completed',
                           'completed_prediction_records': len(records),
                           'native_fit_calls_completed': len(fit_folds) * 4,
                           'native_prediction_calls_completed': len(records) * 4,
                           'run_manifest_sha256': self.plan['run_manifest_sha256']})
            write_lines(self.folder / f'{stage}.raw.jsonl', captures)
            write_lines(self.folder / f'{stage}.operations.jsonl', events)
        collection['output_sha256'] = digest(self.folder / 'full.jsonl')
        collection['fold_artifacts'] = [
            {'fold': n, 'file': f'fold-{n}-artifacts.json',
             'sha256': digest(self.folder / f'fold-{n}-artifacts.json')}
            for n in range(1, 6)]
        write_json(self.folder / 'collection-manifest.json', collection)
        for stage in ('smoke', 'full'):
            review = {'decision': 'approved', 'phase': 'repeat2', 'stage': stage,
                      'plan_sha256': digest(self.root / report.PLAN),
                      'controller_sha256': self.plan['controller_sha256'],
                      'scope': 'one native L2 stage only'}
            if stage == 'full':
                review.update(smoke_raw_sha256=digest(self.folder / 'smoke.raw.jsonl'),
                              smoke_rows_sha256=digest(self.folder / 'smoke.jsonl'),
                              smoke_completion_sha256=digest(self.folder / 'smoke.repeat-completion.json'))
            write_json(self.folder / f'{stage}.root-review.json', review)
            names = [f'{stage}.raw.jsonl', f'{stage}.operations.jsonl',
                     f'{stage}.attempts.jsonl', f'{stage}.jsonl']
            names += ([f'fold-{n}-artifacts.json' for n in (1, 4, 5)] if stage == 'smoke'
                      else ['collection-manifest.json', 'smoke.repeat-completion.json'] +
                      [f'fold-{n}-artifacts.json' for n in range(1, 6)])
            completion = {'contract': 'anyjev-l2-repeat-completion-v1',
                          'phase': 'repeat2', 'stage': stage, 'status': 'completed',
                          'controller_sha256': self.plan['controller_sha256'],
                          'raw_sha256': digest(self.folder / f'{stage}.raw.jsonl'),
                          'stage_bindings': {name: digest(self.folder / name) for name in names},
                          'external_bindings': {
                              key: {'path': str(target), 'sha256': digest(local)}
                              for key, target, local in (
                                  ('plan', self.original_root / report.PLAN,
                                   self.root / report.PLAN),
                                  ('review', self.original_root / report.BASE / 'repeat2' /
                                   f'{stage}.root-review.json', self.folder / f'{stage}.root-review.json'),
                                  ('run_manifest', Path(self.plan['run_manifest']),
                                   self.root / report.RUN_MANIFEST),
                                  ('base_runner', self.original_root / report.BASE_RUNNER,
                                   self.root / report.BASE_RUNNER))}}
            if stage == 'full':
                base_review = {'decision': 'approved',
                    'protocol_sha256': self.plan['protocol_sha256'],
                    'smoke_sha256': digest(self.folder / 'smoke.jsonl'),
                    'runner_sha256': self.plan['base_runner_sha256'],
                    'run_manifest_sha256': self.plan['run_manifest_sha256']}
                write_json(self.folder / 'base-smoke-review.json', base_review)
                completion.update(smoke_completion_sha256=digest(self.folder / 'smoke.repeat-completion.json'),
                                  base_smoke_review_path=str(self.original_root / report.BASE / 'repeat2' /
                                                             'base-smoke-review.json'),
                                  base_smoke_review_sha256=digest(self.folder / 'base-smoke-review.json'))
            write_json(self.folder / f'{stage}.repeat-completion.json', completion)
        return full

    def test_synthetic_closed_full_is_scored_and_bound(self):
        self.make_closed()
        result = self.build()
        self.assertEqual(result['completedConditions'], 2)
        self.assertEqual(result['passes']['repeat2']['P0']['score']['denominator'], 60)
        self.assertEqual(result['passes']['repeat2']['P0']['score']['valid'], 60)
        self.assertEqual(len(result['pairwiseFlips']), 1)
        self.assertIsNone(result['threePassSummary']['P0']['allFour']['range'])
        self.assertEqual(sum(sum(cols.values()) for cols in
                             result['confusionCounts']['repeat2']['sentiment'].values()), 60)

    def test_synthetic_raw_tamper_fails_closed(self):
        self.make_closed()
        raw = self.folder / 'full.raw.jsonl'
        raw.write_bytes(raw.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'hash differs|changed|Incomplete'):
            self.build()

    def test_synthetic_missing_completion_not_scored(self):
        self.make_closed()
        (self.folder / 'full.repeat-completion.json').unlink()
        result = self.build()
        self.assertEqual(result['completedConditions'], 1)
        self.assertEqual(result['missingPasses'][0]['status'], 'claimed_in_progress_or_interrupted')

    def test_confusion_retains_invalid_in_sixty_denominator(self):
        indexed = {rid: {'status': 'ok', 'prediction': self.build()['passes']['original']['P0']['score']}
                   for rid in report.IDS}
        labels = {rid: {'sentiment': 'neutral', **{field: 'no' for field in report.FIELDS[1:]}}
                  for rid in report.IDS}
        indexed['DEV-001'] = {'status': 'invalid_output', 'prediction': None}
        for rid in report.IDS[1:]:
            indexed[rid]['prediction'] = labels[rid]
        matrix = report.confusion_counts(indexed, labels)
        self.assertEqual(matrix['sentiment']['neutral']['__invalid_or_missing__'], 1)
        self.assertEqual(sum(matrix['sentiment']['neutral'].values()), 60)


if __name__ == '__main__':
    unittest.main()
