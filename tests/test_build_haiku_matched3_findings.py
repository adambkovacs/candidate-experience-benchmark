"""Source-bound checks for the separate Haiku matched-three report."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_haiku_matched3_findings as report
import claude_haiku_matched3 as haiku


class HaikuMatchedThreeReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These integration checks authenticate private originals; the public
        # bundle has separate hash, redaction and parser-fidelity checks.
        if not (ROOT / report.BASE / 'pass1/P0/development.batch-001.raw.jsonl').exists():
            raise unittest.SkipTest('Private Haiku captures unavailable; verify the public export instead')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / report.BASE, self.root / report.BASE)
        sources = {Path(report.opus.LABELS),
                   Path('scripts/build_haiku_matched3_findings.py'),
                   Path('scripts/build_claude_repeat_findings.py'),
                   Path('scripts/build_repeat_findings.py'),
                   Path('scripts/development_benchmark.py')}
        for name in report.PASSES:
            plan = json.loads((ROOT / report.BASE / name / 'manifest.json').read_text())
            sources.update(Path(item['path']) for item in plan['source_bindings'])
        for relative in sources:
            dest = self.root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, dest)
        context = patch.object(haiku, 'ROOT', self.root)
        context.start()
        self.addCleanup(context.stop)

    def test_full_series_uses_new_pass_one_and_preserves_historical_failure(self):
        result = report.build(self.root)
        self.assertEqual(result['completedConditions'], 9)
        self.assertEqual(result['plannedConditions'], 9)
        self.assertEqual(result['passOrder'], ['pass1', 'pass2', 'pass3'])
        self.assertEqual(len(result['pairwiseFlips']), 9)
        self.assertEqual(len(result['withinPassPromptDeltas']), 6)
        self.assertEqual(result['historicalContext']['P1']['validPredictions'], 50)
        self.assertEqual(result['historicalContext']['P1']['attemptedTransportFailures'], 10)
        self.assertEqual(result['historicalContext']['P1']['failureIds'],
                         [f'DEV-{i:03d}' for i in range(11, 21)])
        self.assertEqual(result['passes']['pass1']['P1']['score']['denominator'], 60)
        self.assertEqual(result['passes']['pass1']['P1']['score']['valid'], 60)
        self.assertEqual(result['passes']['pass1']['P1']['score']['allFour'], 53)
        self.assertIsNone(result['passes']['pass1']['P1']['usage']['actualCostUsd'])
        self.assertIsNone(result['passes']['pass1']['P1']['usage']['inferenceSeconds'])
        self.assertEqual(len(result['passes']['pass1']['P1']['evidence']['rawCaptures']), 6)

    def test_open_phase_is_excluded_and_missing_is_explicit(self):
        path = self.root / report.BASE / 'pass3/P1/development.journal.jsonl'
        path.write_text('{"event":"phase_started"}\n')
        result = report.build(self.root)
        self.assertEqual(result['completedConditions'], 8)
        self.assertIn({'pass': 'pass3', 'condition': 'P1', 'status': 'open_or_not_started'},
                      result['missingPasses'])
        self.assertIsNone(result['threePassSummary']['P1']['allFour']['range'])

    def test_raw_review_inspection_and_record_tampering_rejected(self):
        folder = self.root / report.BASE / 'pass2/P1'
        raw = folder / 'development.batch-001.raw.jsonl'
        original = raw.read_bytes()
        raw.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            report.build(self.root)
        raw.write_bytes(original)
        review = folder / 'development.root-review.json'
        original = review.read_bytes()
        review.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'Source hash changed'):
            report.build(self.root)
        review.write_bytes(original)
        inspection = folder / 'smoke-inspection.json'
        saved = json.loads(inspection.read_text())
        saved['records_sha256'] = '0' * 64
        inspection.write_text(json.dumps(saved) + '\n')
        with self.assertRaisesRegex(ValueError, 'smoke inspection differs'):
            report.build(self.root)
        shutil.copy2(ROOT / report.BASE / 'pass2/P1/smoke-inspection.json', inspection)
        records = folder / 'development.records.jsonl'
        values = [json.loads(line) for line in records.read_text().splitlines()]
        values[0]['prediction']['sentiment'] = 'negative' if values[0]['prediction']['sentiment'] != 'negative' else 'positive'
        records.write_text(''.join(json.dumps(row) + '\n' for row in values))
        with self.assertRaisesRegex(ValueError, 'record differs'):
            report.build(self.root)

    def test_check_mode_and_historical_source_binding(self):
        output = self.root / 'haiku.json'
        with patch.object(report, 'ROOT', self.root):
            report.main(['--output', str(output)])
            before = output.read_bytes()
            report.main(['--output', str(output), '--check'])
            output.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'Stale report'):
                report.main(['--output', str(output), '--check'])
            output.write_bytes(before)
        historical = self.root / haiku.RECONCILIATION
        historical.write_text(historical.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Frozen Haiku plan differs'):
            report.build(self.root)


if __name__ == '__main__':
    unittest.main()
