import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_claude_roster_findings as report
import claude_repeat_roster as roster


class ClaudeRosterFindingsTests(unittest.TestCase):
    config = report.CONFIGS[0]

    def _copy_config(self, config=None, include_phases=True):
        config = config or self.config
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        pair_path = Path(roster.PAIRS) / config / 'paired-manifest.json'
        pair = json.loads((ROOT / pair_path).read_text())
        paths = {report.opus.LABELS, Path(roster.COVERAGE), pair_path}
        for repeat in ('repeat2', 'repeat3'):
            plan_path = report.BASE / config / repeat / 'manifest.json'
            paths.add(plan_path)
            plan = json.loads((ROOT / plan_path).read_text())
            paths.update(Path(item['path']) for item in plan['source_bindings'])
        for condition in report.CONDITIONS:
            sources = pair['conditions'][condition]
            paths.add(Path(sources['predictions']['file']))
            paths.add(Path(sources['request_evidence']['file']))
        for relative in paths:
            dest = root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, dest)
        if include_phases:
            shutil.copytree(ROOT / report.BASE / config, root / report.BASE / config, dirs_exist_ok=True)
        return root

    def test_real_closed_roster_has_four_separate_full_series(self):
        payload = report.build(ROOT, configs=report.FABLE_CONFIGS)
        self.assertEqual([s['configuration'] for s in payload['series']], list(report.FABLE_CONFIGS))
        for series in payload['series']:
            self.assertEqual(series['completedConditions'], 9)
            self.assertEqual(series['plannedConditions'], 9)
            self.assertEqual(series['missingPasses'], [])
            self.assertEqual(series['partialPasses'], [])
            self.assertEqual(series['denominator'], 60)
            self.assertEqual(len(series['pairwiseFlips']), 9)
            self.assertEqual(len(series['withinPassPromptDeltas']), 6)
            self.assertEqual(len([item for item in series['sourceBindings']
                                  if item['path'].endswith('-root-review-v1.json')]), 12)
            self.assertFalse(any('preflight-v' in item['path'] for item in series['sourceBindings']))
            for name in ('original', 'repeat2', 'repeat3'):
                for condition in report.CONDITIONS:
                    phase = series['passes'][name][condition]
                    self.assertEqual(phase['completionStatus'], 'complete')
                    self.assertEqual(phase['score']['denominator'], 60)
                    self.assertEqual(phase['score']['valid'], 60)
                    self.assertIsNone(phase['usage']['actualCostUsd'])
                    self.assertIsNone(phase['usage']['inferenceSeconds'])

    def test_published_fable_series_stay_unchanged(self):
        published = json.loads((ROOT / 'public-site/claude-roster-repeats.json').read_text())
        published_fable = {**published, 'series': [s for s in published['series']
                                              if s['configuration'] in report.FABLE_CONFIGS]}
        self.assertEqual(report.build(ROOT, configs=report.FABLE_CONFIGS), published_fable)

    def test_opus5_four_efforts_bind_original_and_closed_first_phase(self):
        self.assertEqual(len(report.OPUS5_CONFIGS), 4)
        for config in report.OPUS5_CONFIGS:
            with self.subTest(config=config):
                ids, labels, pair, plans, bind, _ = report._source_context(ROOT, config)
                self.assertEqual(len(ids), 60)
                for condition in report.CONDITIONS:
                    historical, _ = report._historical(ROOT, config, condition, pair,
                                                       plans['repeat2'][0], ids, labels, bind)
                    self.assertEqual(historical['score']['denominator'], 60)
                    self.assertEqual(historical['score']['valid'], 60)
                plan, plan_binding = plans['repeat2']
                smoke, _, _ = report._phase(ROOT, config, 'repeat2', 'P0', 'smoke',
                                            plan, plan_binding, ids, labels, bind)
                development, _, _ = report._phase(ROOT, config, 'repeat2', 'P0', 'development',
                                                  plan, plan_binding, ids, labels, bind)
                self.assertEqual(smoke['completionStatus'], 'complete')
                self.assertEqual(development['completionStatus'], 'complete')
                self.assertEqual(development['score']['valid'], 60)
                self.assertIsNone(development['usage']['actualCostUsd'])

    def test_opus5_prepared_but_unstarted_phases_are_missing(self):
        config = report.OPUS5_CONFIGS[0]
        root = self._copy_config(config=config, include_phases=False)
        series = report.build(root, configs=(config,))['series'][0]
        self.assertEqual(series['displayName'], 'Claude Opus 5 · low effort · batch 10')
        self.assertEqual(series['completedConditions'], 3)
        self.assertEqual(len(series['missingPasses']), 6)
        self.assertEqual(series['partialPasses'], [])
        self.assertEqual(set(series['passes']['original']), set(report.CONDITIONS))
        self.assertEqual(series['passes']['repeat2'], {})
        self.assertEqual(series['passes']['repeat3'], {})

    def test_missing_development_is_open_not_zero(self):
        root = self._copy_config()
        (root / report.BASE / self.config / 'repeat3/P2/development.journal.jsonl').unlink()
        series = report.build(root, configs=(self.config,))['series'][0]
        self.assertEqual(series['completedConditions'], 8)
        self.assertNotIn('P2', series['passes']['repeat3'])
        self.assertIn({'pass': 'repeat3', 'condition': 'P2', 'status': 'open_or_not_started'},
                      series['missingPasses'])
        self.assertIsNone(series['threePassSummary']['P2']['allFour']['range'])

    def test_raw_capture_change_with_updated_hash_still_fails_prediction_mirror(self):
        root = self._copy_config()
        folder = root / report.BASE / self.config / 'repeat2/P2'
        raw_path = folder / 'development.batch-001.raw.jsonl'
        raw = json.loads(raw_path.read_text())
        raw['stdout'] = '[]'
        raw_path.write_text(json.dumps(raw) + '\n')
        attempts_path = folder / 'development.attempts.jsonl'
        attempts = [json.loads(line) for line in attempts_path.read_text().splitlines()]
        attempts[0]['raw_capture_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        attempts_path.write_text(''.join(json.dumps(item) + '\n' for item in attempts))
        with self.assertRaises(ValueError):
            report.build(root, configs=(self.config,))

    def test_root_review_phase_change_with_updated_claim_hash_is_rejected(self):
        root = self._copy_config()
        folder = root / report.BASE / self.config / 'repeat2/P2'
        review_path = folder / 'development-root-review-v1.json'
        review = json.loads(review_path.read_text())
        review['approved_phases'] = [{'condition': 'P1', 'phase': 'development'}]
        review_path.write_text(json.dumps(review) + '\n')
        claim_path = folder / 'development.claim.json'
        claim = json.loads(claim_path.read_text())
        claim['root_review_sha256'] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        claim_path.write_text(json.dumps(claim) + '\n')
        with self.assertRaisesRegex(ValueError, 'root review'):
            report.build(root, configs=(self.config,))

    def test_stopped_phase_keeps_failed_batch_and_never_sent_in_sixty(self):
        root = self._copy_config()
        folder = root / report.BASE / self.config / 'repeat2/P2'
        attempts_path = folder / 'development.attempts.jsonl'
        attempts = [json.loads(line) for line in attempts_path.read_text().splitlines()]
        attempts[0]['status'] = 'service_error'
        attempts_path.write_text(json.dumps(attempts[0]) + '\n')
        records_path = folder / 'development.records.jsonl'
        records = [json.loads(line) for line in records_path.read_text().splitlines()[:10]]
        for record in records:
            record['status'] = 'service_error'
            record['prediction'] = None
        records_path.write_text(''.join(json.dumps(record) + '\n' for record in records))
        journal_path = folder / 'development.journal.jsonl'
        journal = [json.loads(line) for line in journal_path.read_text().splitlines()]
        journal[2]['status'] = 'service_error'
        journal = journal[:3] + [{'event': 'phase_stopped', 'reason': 'service_error', 'batch_index': 1}]
        journal_path.write_text(''.join(json.dumps(event) + '\n' for event in journal))
        series = report.build(root, configs=(self.config,))['series'][0]
        result = series['passes']['repeat2']['P2']
        self.assertEqual(series['completedConditions'], 8)
        self.assertEqual(result['completionStatus'], 'partial')
        self.assertEqual(result['score']['denominator'], 60)
        self.assertEqual(result['score']['outcomes']['service_error'], 10)
        self.assertEqual(result['score']['outcomes']['never_sent'], 50)
        self.assertEqual(result['usage']['requestCount'], 1)

    def test_check_is_deterministic_and_does_not_rewrite_stale_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fable.json'
            frozen = report.build(ROOT, configs=report.FABLE_CONFIGS)
            with mock.patch.object(report, 'build', return_value=frozen):
                report.main(['--output', str(path)])
                expected = path.read_bytes()
                report.main(['--output', str(path), '--check'])
                self.assertEqual(path.read_bytes(), expected)
                path.write_bytes(expected + b' ')
                with self.assertRaisesRegex(ValueError, 'Stale report'):
                    report.main(['--output', str(path), '--check'])
                self.assertEqual(path.read_bytes(), expected + b' ')


if __name__ == '__main__':
    unittest.main()
