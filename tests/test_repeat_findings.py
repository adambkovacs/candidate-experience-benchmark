"""Safety checks for offline repeat evidence admission and scoring."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_repeat_findings.py'
spec = importlib.util.spec_from_file_location('build_repeat_findings', SCRIPT)
repeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repeat)


class RepeatFindingsTest(unittest.TestCase):
    def test_in_progress_journal_never_reads_record_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = Path('run/repeat3/P0')
            target = root / folder
            target.mkdir(parents=True)
            (target / 'development.journal.jsonl').write_text('{"event":"phase_started"}\n{"event":"request_started"}\n')
            (target / 'development.records.jsonl').write_text('not json')
            with patch.object(repeat, 'ROOT', root):
                self.assertFalse(repeat.completed_repeat(folder, 'repeat3', 'P0', 'abc'))

    def test_forged_terminal_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = Path('run/repeat3/P0')
            target = root / folder
            target.mkdir(parents=True)
            (target / 'development.journal.jsonl').write_text('{"event":"phase_completed","request_count":5,"record_count":60}\n')
            with patch.object(repeat, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'terminal counts'):
                    repeat.completed_repeat(folder, 'repeat3', 'P0', 'abc')

    def test_source_binding_catches_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'labels.jsonl').write_text('original\n')
            with patch.object(repeat, 'ROOT', root):
                expected = repeat.binding(Path('labels.jsonl'))['sha256']
                (root / 'labels.jsonl').write_text('changed\n')
                with self.assertRaisesRegex(ValueError, 'Source SHA changed'):
                    repeat.binding(Path('labels.jsonl'), expected)

    def test_flip_excludes_invalid_record_and_keeps_ids(self):
        ids = ['DEV-001', 'DEV-002']
        prediction = dict.fromkeys(repeat.FIELDS, 'no')
        left = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in ids}
        right = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in ids}
        right['DEV-001']['prediction']['follow_up_needed'] = 'yes'
        right['DEV-002'] = {'status': 'invalid_output', 'prediction': None}
        result = repeat.flip(left, right, ids)
        self.assertEqual(result['denominator'], 1)
        self.assertEqual(result['excludedIds'], ['DEV-002'])
        self.assertEqual(result['follow_up_needed']['caseIds'], ['DEV-001'])
        self.assertEqual(result['fourFieldVector']['changed'], 1)

    def test_duplicate_or_missing_records_rejected(self):
        ids = [f'DEV-{n:03}' for n in range(1, 61)]
        records = [{'id': rid, 'request_sha256': 'x', 'status': 'ok'} for rid in ids]
        attempts = [{'record_order': ids[i:i+10], 'batch_size': 10, 'request_sha256': 'x', 'status': 'ok'} for i in range(0, 60, 10)]
        repeat.validate_evidence(records, attempts, ids, 'P0', 'repeat2')
        records[-1]['id'] = ids[0]
        with self.assertRaisesRegex(ValueError, 'Incomplete/duplicate'):
            repeat.validate_evidence(records, attempts, ids, 'P0', 'repeat2')

    def test_unresolved_and_never_sent_keep_distinct_sixty_position_counts(self):
        ids = [f'DEV-{n:03}' for n in range(1, 61)]
        labels = {rid: dict.fromkeys(repeat.FIELDS, 'no') for rid in ids}
        records = {rid: {'status': 'ok', 'prediction': labels[rid].copy()} for rid in ids}
        records[ids[0]] = {'status': 'unknown_started', 'prediction': None}
        records[ids[1]] = {'status': 'never_sent', 'prediction': None}
        result = repeat.score(records, labels, ids)
        self.assertEqual(result['denominator'], 60)
        self.assertEqual(result['valid'], 58)
        self.assertEqual(result['allFour'], 58)
        self.assertEqual(result['outcomes']['unknown_started'], 1)
        self.assertEqual(result['outcomes']['never_sent'], 1)
        self.assertEqual(result['outcomes']['other_error'], 0)
        self.assertEqual(result['invalidIds'], ids[:2])

    def test_unfinished_repeats_never_produce_ranges_or_prompt_deltas(self):
        with patch.object(repeat, 'completed_repeat', return_value=False):
            report = repeat.build_series(repeat.SOL_CONFIG, 'Sol high')
        self.assertEqual(report['completedConditions'], 3)
        self.assertEqual(len(report['missingPasses']), 6)
        self.assertEqual(report['passes']['repeat2'], {})
        self.assertEqual(report['passes']['repeat3'], {})
        self.assertEqual(report['pairwiseFlips'], [])
        self.assertTrue(all(x['pass'] == 'original' for x in report['withinPassPromptDeltas']))
        for condition in repeat.CONDITIONS:
            self.assertIsNone(report['threePassSummary'][condition]['allFour']['range'])
            self.assertIsNone(report['threePassSummary'][condition]['allFour']['mean'])
            self.assertNotIn(condition, report['changesAcrossThreePasses'])

    def test_saved_series_are_separate_and_missing_passes_have_no_scores(self):
        report = repeat.build()
        self.assertEqual([s['configuration'] for s in report['series']], [repeat.CONFIG, repeat.SOL_CONFIG, repeat.SOL_MEDIUM_CONFIG])
        luna, sol, sol_medium = report['series']
        self.assertEqual(luna['passes']['original']['P0']['score']['allFour'], 50)
        self.assertEqual(luna['completedConditions'], 9)
        self.assertEqual(report['passes'], luna['passes'])  # Legacy Luna view is unchanged.
        for series in (luna, sol, sol_medium):
            self.assertEqual(series['denominator'], 60)
            self.assertEqual(series['completedConditions'] + len(series['missingPasses']), 9)
            self.assertEqual(len(series['passes']['original']), 3)
            for missing in series['missingPasses']:
                self.assertNotIn(missing['condition'], series['passes'][missing['pass']])
            for condition in repeat.CONDITIONS:
                scores = [series['passes'][name][condition]['score']['allFour'] for name in repeat.PASSES if condition in series['passes'][name]]
                summary = series['threePassSummary'][condition]['allFour']
                self.assertEqual(summary['values'], scores)
                if len(scores) < 3:
                    self.assertIsNone(summary['mean'])
                    self.assertIsNone(summary['range'])
                else:
                    self.assertEqual(summary['range'], [min(scores), max(scores)])
            for delta in series['withinPassPromptDeltas']:
                base = series['passes'][delta['pass']]['P0']['score']['allFour']
                variant = series['passes'][delta['pass']][delta['to']]['score']['allFour']
                self.assertEqual(delta['allFour'], variant - base)


if __name__ == '__main__': unittest.main()
