"""Relocatable, offline checks for the native SemIf P0 evidence report."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_semif_repeat_findings as report


class SemIfRepeatFindingsTests(unittest.TestCase):
    config = 'semif-direct'

    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        plan = json.loads((ROOT / report.MANIFEST).read_text())
        original_root = next(source.parent.parent for name in plan['source_sha256']
                             if (source := Path(name)).name == 'semif_repeat_admission.py'
                             and source.parent.name == 'scripts')
        files = {report.MANIFEST, report.LABELS, report.LAYA_MANIFEST}
        for absolute in plan['source_sha256']:
            source = Path(absolute)
            if source.is_relative_to(original_root):
                files.add(source.relative_to(original_root))
        history = plan['configurations'][self.config]['historical']
        for stage in ('smoke', 'development'):
            files.add(Path(history['directory']) / f'{stage}.jsonl')
        phase = report.BASE / self.config / 'repeat2/P0'
        for stage in ('smoke', 'development'):
            for suffix in ('root-review.json', 'claim.json', 'journal.jsonl',
                           'raw.jsonl', 'records.jsonl', 'completion.json'):
                files.add(phase / f'{stage}.{suffix}')
        files.add(phase / 'smoke-inspection.json')
        for relative in files:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def test_relocated_complete_phase_retains_scores_flips_and_unknowns(self):
        root = self.fixture()
        series = report.build(root, configs=(self.config,))['series'][0]
        self.assertEqual(series['method'], 'native-output-stability')
        self.assertEqual(series['conditionOrder'], ['P0'])
        self.assertEqual(series['completedConditions'], 2)
        self.assertEqual(series['missingPasses'],
                         [{'pass': 'repeat3', 'condition': 'P0', 'status': 'open_or_not_started'}])
        self.assertEqual(series['passes']['original']['P0']['score']['allFour'], 36)
        self.assertEqual(series['passes']['repeat2']['P0']['score']['allFour'], 36)
        self.assertEqual(series['passes']['repeat2']['P0']['score']['valid'], 60)
        self.assertEqual(series['pairwiseFlips'][0]['fourFieldVector']['changed'], 0)
        self.assertEqual(series['passes']['repeat2']['P0']['usage']['requestCount'], 60)
        self.assertGreater(series['passes']['repeat2']['P0']['usage']['tokens']['input_tokens'], 0)
        self.assertIsNone(series['passes']['repeat2']['P0']['usage']['actualCostUsd'])
        self.assertIsNone(series['passes']['repeat2']['P0']['usage']['inferenceSeconds'])
        self.assertIsNone(series['passes']['repeat2']['P0']['usage']['modelLoadSeconds'])
        self.assertNotIn('P0', series['changesAcrossThreePasses'])

    def test_live_partial_file_is_never_read_before_terminal_marker(self):
        root = self.fixture()
        phase = root / report.BASE / self.config / 'repeat3/P0'
        phase.mkdir(parents=True)
        (phase / 'development.raw.jsonl').write_bytes(b'{partial')
        series = report.build(root, configs=(self.config,))['series'][0]
        self.assertEqual(series['passes']['repeat3'], {})
        self.assertEqual(series['completedConditions'], 2)

    def test_terminal_marker_without_evidence_fails_closed(self):
        root = self.fixture()
        phase = root / report.BASE / self.config / 'repeat3/P0'
        phase.mkdir(parents=True)
        (phase / 'development.completion.json').write_text('{}\n')
        with self.assertRaises((ValueError, FileNotFoundError)):
            report.build(root, configs=(self.config,))

    def test_raw_capture_must_match_record_hash_and_frozen_signature(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/development.raw.jsonl'
        lines = [json.loads(line) for line in target.read_text().splitlines()]
        lines[0]['raw_response']['decisions'][0]['probabilities'][0] += .01
        target.write_text(''.join(json.dumps(line) + '\n' for line in lines))
        with self.assertRaises(ValueError):
            report.build(root, configs=(self.config,))

    def test_terminal_journal_must_match_all_requests(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/development.journal.jsonl'
        target.write_text(''.join(target.read_text().splitlines(keepends=True)[:-1]))
        with self.assertRaisesRegex(ValueError, 'journal not terminal'):
            report.build(root, configs=(self.config,))

    def test_claim_must_bind_root_delegated_receipt(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/development.root-review.json'
        receipt = json.loads(target.read_text())
        receipt['approval_basis'] = 'Changed later'
        target.write_text(json.dumps(receipt) + '\n')
        with self.assertRaisesRegex(ValueError, 'claim does not bind receipt'):
            report.build(root, configs=(self.config,))

    def test_development_receipt_must_bind_inspected_smoke(self):
        root = self.fixture()
        target = root / report.BASE / self.config / 'repeat2/P0/smoke-inspection.json'
        inspection = json.loads(target.read_text())
        inspection['approved'] = False
        target.write_text(json.dumps(inspection) + '\n')
        with self.assertRaisesRegex(ValueError, 'does not bind inspected'):
            report.build(root, configs=(self.config,))

    def test_historical_and_plan_sources_are_hash_bound(self):
        root = self.fixture()
        target = root / 'scripts/specialist_benchmark.py'
        target.write_bytes(target.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            report.build(root, configs=(self.config,))

    def test_invalid_native_distribution_is_an_invalid_output(self):
        root = self.fixture()
        plan, _, _, options, _, _, _ = report.source_context(root)
        config = plan['configurations'][self.config]
        capture = json.loads((root / report.BASE / self.config /
                              'repeat2/P0/development.raw.jsonl').read_text().splitlines()[0])
        raw = copy.deepcopy(capture['raw_response'])
        raw['decisions'][0]['probabilities'][0] = float('nan')
        self.assertIsNone(report.raw_result(raw, config, options[0],
                                            config['native_requests'][0]['decisions']))
        raw = copy.deepcopy(capture['raw_response'])
        values = raw['decisions'][0]['probabilities']
        original = values[0]
        values[0] = -0.01
        values[1] += original + 0.01
        self.assertAlmostEqual(sum(values), 1.0)
        self.assertIsNone(report.raw_result(raw, config, options[0],
                                            config['native_requests'][0]['decisions']))

    def test_closed_invalid_output_remains_in_fixed_denominator(self):
        root = self.fixture()
        phase = root / report.BASE / self.config / 'repeat2/P0'
        raw_file = phase / 'development.raw.jsonl'
        record_file = phase / 'development.records.jsonl'
        journal_file = phase / 'development.journal.jsonl'
        completion_file = phase / 'development.completion.json'
        captures = [json.loads(line) for line in raw_file.read_text().splitlines()]
        records = [json.loads(line) for line in record_file.read_text().splitlines()]
        journal = [json.loads(line) for line in journal_file.read_text().splitlines()]
        index = 3
        captures[index]['raw_response']['decisions'][0]['probabilities'][0] = float('nan')
        records[index]['prediction'] = None
        records[index]['status'] = 'invalid_output'
        records[index]['raw_sha256'] = report.digest(json.dumps(
            captures[index]['raw_response'], sort_keys=True))
        journal[2 + 2 * index]['status'] = 'invalid_output'
        for target, items in ((raw_file, captures), (record_file, records), (journal_file, journal)):
            target.write_text(''.join(json.dumps(item) + '\n' for item in items))
        completion = json.loads(completion_file.read_text())
        completion['output_sha256'] = report.sha(record_file)
        completion_file.write_text(json.dumps(completion) + '\n')
        series = report.build(root, configs=(self.config,))['series'][0]
        score = series['passes']['repeat2']['P0']['score']
        self.assertEqual(score['denominator'], 60)
        self.assertEqual(score['valid'], 59)
        self.assertEqual(score['outcomes']['invalid_output'], 1)
        self.assertEqual(score['invalidIds'], ['DEV-004'])
        self.assertEqual(series['pairwiseFlips'][0]['denominator'], 59)


if __name__ == '__main__':
    unittest.main()
