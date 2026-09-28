"""Offline Alex report checks. Synthetic phase evidence stays in temporary fixtures."""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_alex_native_repeat_findings as report
from development_benchmark import KEYS, VALUES, digest


class AlexNativeFindingsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.plans = {}
        for name, spec in report.CONFIGS.items():
            base = Path('results/repeatability-v1') / name
            plan = json.loads((report.ROOT / base / 'manifest.json').read_text())
            self.plans[name] = plan
            self.copy(base / 'manifest.json')
            original_root = next(Path(filename).parent.parent for filename in plan['source_sha256']
                                 if Path(filename).name == spec['controller'])
            for filename in plan['source_sha256']:
                source = Path(filename)
                try: relative = source.relative_to(original_root)
                except ValueError: continue
                self.copy(relative)
            historical = Path(plan['historical']['directory'])
            if 'files_sha256' in plan['historical']:
                for filename in plan['historical']['files_sha256']:
                    self.copy(historical / filename)
            else:
                for filename in ('smoke.jsonl', 'development.jsonl'):
                    self.copy(historical / filename)
        self.copy('data/pilot/proposed_labels.jsonl')
        self.history = {name: report.rows(self.root, Path(plan['historical']['directory']) /
                                        report.CONFIGS[name]['historical_file'])
                        for name, plan in self.plans.items()}

    def copy(self, relative):
        relative = Path(relative)
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report.ROOT / relative, target)

    def write(self, relative, value):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
        return target

    def write_rows(self, relative, values):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in values))
        return target

    def fake_stage(self, name, phase, stage, *, invalid_id=None, changed_id=None):
        spec = report.CONFIGS[name]
        plan = self.plans[name]
        base = Path('results/repeatability-v1') / name
        folder = base / phase
        count = plan['stage_inputs'][stage]['limit']
        receipt = {'kind': spec['kind'], 'approved': True, 'phase': phase, 'stage': stage,
            'plan_sha256': spec['manifest_sha'],
            'controller_sha256': next(value for filename, value in plan['source_sha256'].items()
                                      if Path(filename).name == spec['controller']),
            'artifact_sha256': plan['asset_sha256'][Path(plan['model_path']).name + '/model.safetensors'],
            'reference_labels_read': False}
        if stage == 'development':
            receipt['smoke_inspection_sha256'] = report.sha(self.root / folder / 'smoke-inspection.json')
        receipt_path = self.write(folder / f'{stage}.root-review.json', receipt)
        self.write(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
            'plan_sha256': spec['manifest_sha'], 'receipt_sha256': report.sha(receipt_path),
            'policy': 'exclusive one attempt; uncertain started positions are not replayed'})
        journal = [{'event': 'phase_started', 'phase': phase, 'stage': stage}]
        raw, records = [], []
        for i, request in enumerate(plan['requests'][:count]):
            rid = request['id']; attempt = f'synthetic-{phase}-{stage}-{rid}'
            probabilities = copy.deepcopy(self.history[name][i]['raw_response']['nli_probabilities'])
            if rid == changed_id:
                current = spec['module'].project_probabilities(probabilities)['sentiment']
                target = 'negative' if current == 'positive' else 'positive'
                for j in range(len(VALUES['sentiment'])):
                    probabilities[j] = [0.9, 0.05, 0.05]
                probabilities[VALUES['sentiment'].index(target)] = [0.05, 0.9, 0.05]
            if rid == invalid_id:
                probabilities[0] = [0.0, 0.0, 0.0]
            capture = {'id': rid, 'attempt_id': attempt, 'request_sha256': request['request_sha256'],
                'nli_inputs': request['nli_inputs'],
                'hypothesis_order': [[key, label] for key in KEYS for label in VALUES[key]],
                'nli_probabilities': probabilities, 'client_prediction_seconds': 0.1}
            try: prediction = spec['module'].project_probabilities(probabilities); status = 'ok'
            except ValueError: prediction = None; status = 'invalid_output'
            raw.append(capture)
            records.append({'id': rid, 'attempt_id': attempt, 'phase': phase, 'stage': stage,
                'status': status, 'prediction': prediction, 'request_sha256': request['request_sha256'],
                'input_sha256': request['input_sha256'],
                'raw_sha256': digest(spec['module'].canonical(capture)),
                'reference_labels_read': False, 'model_path': plan['model_path'],
                'artifact_revision': plan['artifact_revision'], 'device': 'mps:0',
                'dtype': 'torch.float32', 'quantization': 'none', 'batch_size': 4,
                'max_tokens': 4096, 'client_prediction_seconds': 0.1})
            journal.extend([{'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                             'request_sha256': request['request_sha256']},
                            {'event': 'request_completed', 'id': rid, 'attempt_id': attempt,
                             'status': status}])
        journal.append({'event': 'phase_completed', 'count': count})
        raw_path = self.write_rows(folder / f'{stage}.raw.jsonl', raw)
        records_path = self.write_rows(folder / f'{stage}.records.jsonl', records)
        journal_path = self.write_rows(folder / f'{stage}.journal.jsonl', journal)
        self.write(folder / f'{stage}.completion.json', {'phase': phase, 'stage': stage,
            'plan_sha256': spec['manifest_sha'], 'count': count,
            'records_sha256': report.sha(records_path), 'raw_sha256': report.sha(raw_path),
            'journal_sha256': report.sha(journal_path)})
        if stage == 'smoke':
            self.write(folder / 'smoke-inspection.json', {'phase': phase,
                'plan_sha256': spec['manifest_sha'], 'smoke_records_sha256': report.sha(records_path),
                'inspected_ids': report.IDS[:3], 'approved': True})
        return folder

    def fake_closed(self, name, pass_name, **development_options):
        phase = pass_name + '/P0'
        self.fake_stage(name, phase, 'smoke')
        return self.fake_stage(name, phase, 'development', **development_options)

    def test_current_report_has_two_separate_historical_observations_and_no_fresh_scores(self):
        result = report.build(self.root)
        self.assertEqual(len(result['series']), 2)
        for series in result['series']:
            self.assertEqual(series['completedConditions'], 0)
            self.assertEqual(len(series['missingPasses']), 3)
            self.assertEqual(series['passOrder'], ['fresh1', 'fresh2', 'fresh3'])
            self.assertTrue(series['historicalObservation']['score'])
            self.assertFalse(series['historicalObservation']['freshPassEligible'])
            self.assertEqual(series['threePassSummary']['P0']['allFour']['completedPasses'], 0)
            for field in KEYS:
                matrix = series['historicalObservation']['confusionCounts'][field]
                self.assertEqual(sum(sum(row.values()) for row in matrix.values()), 60)
                self.assertEqual(sum(row['__invalid_or_missing__'] for row in matrix.values()), 0)
        four = next(s for s in result['series'] if '4b' in s['configuration'])
        self.assertEqual(four['historicalObservation']['unknownPriorAttempt']['id'], 'DEV-046')
        self.assertTrue(any('DEV-046' in note for note in four['limitations']))
        zero_eight = next(s for s in result['series'] if '08' in s['configuration'])
        self.assertFalse(any('DEV-046' in note for note in zero_eight['limitations']))

    def test_closed_08_three_pass_scores_flips_and_invalid_denominator(self):
        name = 'alex-openjev08-native-p0-v1'
        self.fake_closed(name, 'fresh1')
        self.fake_closed(name, 'fresh2', changed_id='DEV-001', invalid_id='DEV-002')
        self.fake_closed(name, 'fresh3')
        series = report.build(self.root, (name,))['series'][0]
        self.assertEqual(series['completedConditions'], 3)
        self.assertEqual(series['passes']['fresh2']['P0']['score']['valid'], 59)
        self.assertEqual(series['passes']['fresh2']['P0']['score']['denominator'], 60)
        matrix = series['passes']['fresh2']['P0']['confusionCounts']
        for field in KEYS:
            self.assertEqual(sum(sum(row.values()) for row in matrix[field].values()), 60)
            self.assertEqual(sum(row['__invalid_or_missing__'] for row in matrix[field].values()), 1)
        labels = {row['id']: row['proposed_labels'] for row in report.rows(self.root, Path('data/pilot/proposed_labels.jsonl'))}
        for field in KEYS:
            self.assertEqual(matrix[field][labels['DEV-002'][field]]['__invalid_or_missing__'], 1)
        self.assertTrue(any(f['fourFieldVector']['changed'] for f in series['pairwiseFlips']))
        self.assertEqual(series['changesAcrossThreePasses']['P0']['denominator'], 59)
        self.assertAlmostEqual(series['passes']['fresh1']['P0']['usage']['clientPredictionSeconds'], 6.0)
        self.assertIsNone(series['passes']['fresh1']['P0']['usage']['actualCostUsd'])

    def test_closed_4b_requires_inspection_receipt_and_raw_hash(self):
        name = 'alex-openjev4b-native-p0-v1'
        folder = self.fake_closed(name, 'fresh1')
        self.assertEqual(report.build(self.root, (name,))['series'][0]['completedConditions'], 1)
        receipt_path = self.root / folder / 'development.root-review.json'
        receipt = json.loads(receipt_path.read_text()); receipt['smoke_inspection_sha256'] = '0'*64
        receipt_path = self.write(folder / 'development.root-review.json', receipt)
        claim = json.loads((self.root / folder / 'development.claim.json').read_text())
        claim['receipt_sha256'] = report.sha(receipt_path)
        self.write(folder / 'development.claim.json', claim)
        with self.assertRaisesRegex(ValueError, 'inspected successful smoke'):
            report.build(self.root, (name,))
        self.fake_stage(name, 'fresh1/P0', 'development')
        raw_path = self.root / folder / 'development.raw.jsonl'
        raw = report.rows(self.root, folder / 'development.raw.jsonl');raw[0]['nli_probabilities'][0]=[0,0,0]
        self.write_rows(folder / 'development.raw.jsonl', raw)
        with self.assertRaisesRegex(ValueError, 'binding differs'):
            report.build(self.root, (name,))

    def test_in_progress_partial_is_not_read_or_scored(self):
        name = 'alex-openjev08-native-p0-v1'
        before = report.build(self.root, (name,))['series'][0]
        folder = Path('results/repeatability-v1') / name / 'fresh1/P0'
        self.write(folder / 'smoke.claim.json', {'phase': 'fresh1/P0'})
        target = self.root / folder / 'development.raw.jsonl'
        target.write_text('{partial')
        series = report.build(self.root, (name,))['series'][0]
        self.assertEqual(series['completedConditions'], 0)
        self.assertEqual(series['missingPasses'][0]['status'], 'not_completed')
        self.assertEqual(series, before)

    def test_later_completion_after_open_predecessor_rejected(self):
        name = 'alex-openjev08-native-p0-v1'
        self.fake_closed(name, 'fresh2')
        with self.assertRaisesRegex(ValueError, 'open predecessor'):
            report.build(self.root, (name,))

    def test_historical_hash_tamper_rejected(self):
        name = 'alex-openjev4b-native-p0-v1'
        target = self.root / self.plans[name]['historical']['directory'] / 'interruption-2026-09-24.json'
        target.write_text(target.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(self.root, (name,))

    def test_cli_check_detects_stale_file_without_overwrite(self):
        destination = self.root / 'report.json'
        destination.write_text(json.dumps(report.build(self.root), indent=2, ensure_ascii=False) + '\n')
        with mock.patch.object(report, 'ROOT', self.root):
            report.main(['--output', str(destination), '--check'])
            destination.write_text('stale\n')
            with self.assertRaisesRegex(ValueError, 'Stale report'):
                report.main(['--output', str(destination), '--check'])
            self.assertEqual(destination.read_text(), 'stale\n')


if __name__ == '__main__': unittest.main()
