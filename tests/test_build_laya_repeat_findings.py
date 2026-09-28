"""Offline evidence checks for the native P0 Laya repeat report."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_laya_repeat_findings as report


class LayaRepeatFindingsTests(unittest.TestCase):
    config = 'laya-english-expanded-cpu'

    def fixture(self, *, repeat3=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        plan = json.loads((ROOT / report.MANIFEST).read_text())
        original_root = next(source.parent.parent for name in plan['source_sha256']
                             if (source := Path(name)).name == 'laya_repeat_admission.py'
                             and source.parent.name == 'scripts')
        files = {report.MANIFEST, report.LABELS}
        for absolute in plan['source_sha256']:
            source = Path(absolute)
            if source.is_relative_to(original_root):
                files.add(source.relative_to(original_root))
        historical = plan['configurations'][self.config]['historical']
        for stage in ('smoke', 'development'):
            files.add(Path(historical['directory']) / f'{stage}.jsonl')
        for repeat in (('repeat2', 'repeat3') if repeat3 else ('repeat2',)):
            phase = report.BASE / self.config / repeat / 'P0'
            for stage in ('smoke', 'development'):
                for suffix in ('root-review.json', 'intent.json', 'jsonl', 'completion.json'):
                    files.add(phase / f'{stage}.{suffix}')
            files.add(phase / 'smoke-inspection.json')
        for relative in files:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def test_real_closed_english_is_three_native_p0_passes(self):
        series = report.build(ROOT, configs=(self.config,))['series'][0]
        self.assertEqual(series['method'], 'native-output-stability')
        self.assertEqual(series['conditionOrder'], ['P0'])
        self.assertEqual(series['completedConditions'], 3)
        self.assertEqual(series['plannedConditions'], 3)
        self.assertEqual(series['missingPasses'], [])
        self.assertEqual(series['withinPassPromptDeltas'], [])
        self.assertEqual(len(series['pairwiseFlips']), 3)
        self.assertEqual(series['changesAcrossThreePasses']['P0']['fourFieldVector'], [])
        self.assertEqual(series['threePassSummary']['P0']['allFour']['completedPasses'], 3)
        for name in report.PASSES:
            pass_data = series['passes'][name]['P0']
            self.assertEqual(pass_data['score']['denominator'], 60)
            self.assertEqual(pass_data['score']['valid'], 60)
            self.assertEqual(pass_data['usage']['requestCount'], 60)
            self.assertIsNone(pass_data['usage']['actualCostUsd'])
            self.assertIsNone(pass_data['usage']['inferenceSeconds'])

    def test_open_phase_is_omitted_without_reading_partial_journal(self):
        root = self.fixture()
        phase = report.BASE / self.config / 'repeat3/P0'
        (root / phase).mkdir(parents=True)
        (root / phase / 'development.jsonl').write_bytes(b'{partial')
        series = report.build(root, configs=(self.config,))['series'][0]
        self.assertEqual(series['completedConditions'], 2)
        self.assertEqual(series['passes']['repeat3'], {})
        self.assertEqual(series['missingPasses'],
                         [{'pass': 'repeat3', 'condition': 'P0', 'status': 'open_or_not_started'}])
        self.assertIsNone(series['threePassSummary']['P0']['allFour']['range'])
        self.assertNotIn('P0', series['changesAcrossThreePasses'])

    def test_terminal_marker_requires_all_bound_evidence(self):
        root = self.fixture()
        phase = report.BASE / self.config / 'repeat3/P0'
        (root / phase).mkdir(parents=True)
        (root / phase / 'development.completion.json').write_text('{}\n')
        with self.assertRaises((ValueError, FileNotFoundError)):
            report.build(root, configs=(self.config,))

    def test_repeat_raw_record_cannot_drift_from_completion(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/development.jsonl'
        target.write_bytes(target.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'completion differs'):
            report.build(root, configs=(self.config,))

    def test_inspection_and_development_receipt_must_bind(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/smoke-inspection.json'
        payload = json.loads(target.read_text())
        payload['approved'] = False
        target.write_text(json.dumps(payload) + '\n')
        with self.assertRaisesRegex(ValueError, 'Development admission'):
            report.build(root, configs=(self.config,))

    def test_stage_receipt_and_intent_must_bind(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/development.root-review.json'
        payload = json.loads(target.read_text())
        payload['approval_basis'] = 'Changed later'
        target.write_text(json.dumps(payload) + '\n')
        with self.assertRaisesRegex(ValueError, 'Durable stage intent'):
            report.build(root, configs=(self.config,))

    def test_historical_hash_and_reference_are_frozen(self):
        root = self.fixture()
        target = root / report.LABELS
        target.write_bytes(target.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(root, configs=(self.config,))

    def test_plan_bound_source_cannot_drift(self):
        root = self.fixture()
        target = root / 'scripts/specialist_benchmark.py'
        target.write_bytes(target.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(root, configs=(self.config,))

    def test_prediction_must_match_saved_raw_choice_even_with_rebound_completion(self):
        root = self.fixture()
        phase = report.BASE / self.config / 'repeat2/P0'
        target = root / phase / 'development.jsonl'
        entries = [json.loads(line) for line in target.read_text().splitlines()]
        entries[0]['prediction']['sentiment'] = 'negative' if entries[0]['prediction']['sentiment'] != 'negative' else 'positive'
        target.write_text(''.join(json.dumps(row) + '\n' for row in entries))
        completion = root / phase / 'development.completion.json'
        data = json.loads(completion.read_text())
        data['output_sha256'] = report.sha(target)
        completion.write_text(json.dumps(data) + '\n')
        with self.assertRaisesRegex(ValueError, 'raw/request/control evidence differs'):
            report.build(root, configs=(self.config,))


if __name__ == '__main__':
    unittest.main()
