import hashlib
import json
from contextlib import ExitStack, contextmanager
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_supplemental_decision_runs_v1 as subject


class SupplementalDecisionRunsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = subject.build(ROOT)

    def test_all_closed_runs_keep_scores_costs_and_public_links(self):
        feed = self.expected
        self.assertEqual((feed['schema'], feed['denominator'], len(feed['runs'])),
                         ('supplemental-decision-runs-v1', 60,
                          27 + len(subject.clef_builder.check(ROOT)['stages'])))
        self.assertEqual(len({run['id'] for run in feed['runs']}), len(feed['runs']))
        self.assertEqual({run['model'] for run in feed['runs']},
                         {'upstage/solar-decide', 'liquid/d1',
                          'togethercomputer/tev1-4b-experimental',
                          'cloudflare/clef', 'cloudflare/clef-flash',
                          'openai/gpt-6-luna-decisions'})
        by_id = {run['id']: run for run in feed['runs']}
        self.assertEqual([by_id[f'solar-decide-native-fresh1-{prompt}']['metrics']['all_four']
                          for prompt in ('p0', 'p1', 'p2')], [55, 53, 53])
        self.assertEqual([by_id[f'liquid-d1-native-fresh1-{prompt}']['metrics']['all_four']
                          for prompt in ('p0', 'p1', 'p2')], [43, 42, 41])
        self.assertEqual([by_id[f'tev1-4b-native-fresh1-{prompt}']['metrics']['all_four']
                          for prompt in ('p0', 'p1', 'p2')], [45, 44, 44])
        self.assertEqual([by_id[f'clef-openrouter-native-fresh1-{prompt}']['metrics']['all_four']
                          for prompt in ('p0', 'p1', 'p2')], [54, 51, 49])
        self.assertEqual([by_id[f'clef-flash-openrouter-native-fresh1-{prompt}']['metrics']['all_four']
                          for prompt in ('p0', 'p1', 'p2')], [45, 47, 46])
        self.assertEqual(by_id['luna-decisions-openrouter-native-fresh1-p0']['metrics']['all_four'], 49)
        self.assertEqual(by_id['luna-decisions-openrouter-native-fresh1-p0']['returnedModel'],
                         'openai/gpt-6-luna-decisions-20261006')
        self.assertEqual(sum(run['cost']['knownUsd'] for run in feed['runs']
                             if run['id'].startswith('solar-decide-native-fresh1')), 0.067881)
        old = json.loads((ROOT / subject.OUTPUT).read_text())
        old_first = {run['id']: run for run in old['runs'] if
                     run['id'].startswith('solar-decide-native-fresh1')}
        for ident, previous in old_first.items():
            self.assertEqual((by_id[ident]['id'], by_id[ident]['sourceRecordsUrl'],
                              by_id[ident]['evidenceUrl']),
                             (previous['id'], previous['sourceRecordsUrl'],
                              previous['evidenceUrl']))
        final = by_id['solar-decide-native-fresh3-p2']
        self.assertEqual((final['records'], final['savedResponses'], final['valid'],
                          final['complete'], final['pairedEligible']),
                         (60, 59, 59, False, False))
        self.assertEqual((final['tokens']['reportedRequests'],
                          final['tokens']['totalRequests'], final['tokens']['complete']),
                         (59, 60, False))
        self.assertEqual(final['cost']['unknownUpperBoundUsd'], 0.1048576)
        self.assertIn('DEV-009', final['resultStatus'])
        self.assertIn('original run and its continuation', final['resultStatus'])
        self.assertEqual((final['timing']['requests'], final['timing']['totalRequests'],
                          final['timing']['totalSeconds'], final['timing']['inferenceSeconds']),
                         (59, 60, 473.12019091, None))
        later = by_id['solar-decide-native-fresh2-p0']
        self.assertEqual((later['timing']['requests'], later['timing']['totalSeconds']),
                         (60, 413.03287796))
        first = by_id['solar-decide-native-fresh1-p0']
        self.assertEqual((first['timing']['requests'], first['timing']['totalSeconds']),
                         (60, 467.469690796))
        for run in feed['runs']:
            self.assertEqual(run['records'], 60)
            self.assertEqual(run['valid'], 59 if run is final else 60)
            self.assertEqual(run['savedResponses'], run['valid'])
            self.assertEqual(run['complete'], run is not final)
            self.assertTrue(run['sourceOnlyDetails'])
            self.assertIsNone(run['cost']['actualUsd'])
            self.assertIsNone(run['cost']['estimatedUsd'])
            self.assertIsNone(run['timing']['inferenceSeconds'])
            if (run['id'].startswith('solar-decide-native-') or
                    '-openrouter-native-' in run['id']):
                self.assertEqual(run['timing']['requests'], run['valid'])
                self.assertIsNotNone(run['timing']['totalSeconds'])
                self.assertIsNone(run['timing']['medianSeconds'])
                self.assertIsNone(run['timing']['p95Seconds'])
            else:
                self.assertEqual(run['timing']['requests'], 0)
            self.assertEqual(run['tokens']['reportedRequests'], run['valid'])
            self.assertEqual(run['parentBaselineId'], None if run['condition'] == 'P0'
                             else run['id'].rsplit('-', 1)[0] + '-p0')
            path = Path(run['sourceRecordsUrl'].split('/blob/main/', 1)[1])
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                             run['sourceRecordSha256'])
        encoded = json.dumps(feed)
        for private in ('development.raw.jsonl', 'development.parsed.jsonl',
                        'development.attempts.jsonl', 'development.journal.jsonl',
                        'response_base64', 'feedback'):
            self.assertNotIn(private, encoded)

    def small_copy(self, temp):
        root = Path(temp)
        paths = [subject.SOLAR, subject.SOLAR_FULL, subject.LIQUID, subject.TEV,
                 subject.CLEF_OPENROUTER, subject.clef_builder.PROJECTION,
                 subject.clef_builder.RECEIPT,
                 subject.solar_builder.PROJECTION, subject.solar_builder.RECEIPT,
                 subject.solar_full_builder.PROJECTION, subject.solar_full_builder.RECEIPT,
                 subject.tev_builder.PROJECTION, subject.tev_builder.RECEIPT,
                 Path('public-site/data-provider-errors-v1.json'),
                 Path('scripts/build_supplemental_decision_runs_v1.py')]
        paths += [Path('results/liquid-d1-native-v1/full-v1') / stage /
                  'development.public.json' for stage in subject.NINE]
        for path in paths:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)
        return root

    @contextmanager
    def builder_stubs(self):
        reports = {path: json.loads((ROOT / path).read_text())
                   for path in (subject.SOLAR, subject.SOLAR_FULL,
                                subject.LIQUID, subject.TEV, subject.CLEF_OPENROUTER)}
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(subject.solar_builder, 'build', return_value=reports[subject.SOLAR]))
            stack.enter_context(mock.patch.object(subject.solar_full_builder, 'build', return_value=reports[subject.SOLAR_FULL]))
            stack.enter_context(mock.patch.object(subject.liquid_builder, 'build', return_value=reports[subject.LIQUID]))
            stack.enter_context(mock.patch.object(subject.tev_builder, 'build', return_value=reports[subject.TEV]))
            stack.enter_context(mock.patch.object(subject.clef_builder, 'check', return_value=reports[subject.CLEF_OPENROUTER]))
            yield

    def test_changed_public_projection_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.small_copy(temp)
            path = root / subject.solar_builder.PROJECTION
            value = json.loads(path.read_text())
            value['stages'][0]['records'][0]['prediction']['sentiment'] = 'negative'
            path.write_text(json.dumps(value))
            with self.builder_stubs(), self.assertRaisesRegex(ValueError, 'projection differs'):
                subject.build(root)

    def test_changed_report_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.small_copy(temp)
            path = root / subject.TEV
            value = json.loads(path.read_text())
            value['stages'][0]['all_four_correct'] += 1
            path.write_text(json.dumps(value))
            with self.builder_stubs(), self.assertRaisesRegex(ValueError, 'report differs'):
                subject.build(root)

    def test_changed_clef_projection_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.small_copy(temp)
            path = root / subject.clef_builder.PROJECTION
            value = json.loads(path.read_text())
            value['stages'][0]['records'][0]['prediction']['sentiment'] = 'negative'
            path.write_text(json.dumps(value))
            with self.builder_stubs(), self.assertRaisesRegex(ValueError, 'projection differs'):
                subject.build(root)

    def test_future_closed_clef_repeat_adds_one_distinct_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.small_copy(temp)
            report_path = root / subject.CLEF_OPENROUTER
            projection_path = root / subject.clef_builder.PROJECTION
            receipt_path = root / subject.clef_builder.RECEIPT
            report = json.loads(report_path.read_text())
            projection = json.loads(projection_path.read_text())
            receipt = json.loads(receipt_path.read_text())
            extra = json.loads(json.dumps(next(item for item in report['stages']
                                               if item['model_key'] == 'clef' and item['stage'] == 'fresh1/P0')))
            extra['stage'] = 'fresh2/P0'
            report['stages'].append(extra)
            report['included_stages'].append({'model_key': 'clef', 'stage': 'fresh2/P0'})
            public = json.loads(json.dumps(next(item for item in projection['stages']
                                                if item['model_key'] == 'clef' and item['stage'] == 'fresh1/P0')))
            public['stage'] = 'fresh2/P0'
            projection['stages'].append(public)
            receipt['included_stages'].append({'model_key': 'clef', 'stage': 'fresh2/P0'})
            receipt['projection_sha256'] = subject.clef_builder.sha(subject.clef_builder.canonical(projection))
            report['evidence']['projection_receipt_sha256'] = subject.clef_builder.sha(
                subject.clef_builder.canonical(receipt))
            for path, value in ((report_path, report), (projection_path, projection),
                                (receipt_path, receipt)):
                path.write_text(json.dumps(value))
            with self.builder_stubs(), mock.patch.object(subject.clef_builder, 'check', return_value=report):
                feed = subject.build(root)
            self.assertEqual(len(feed['runs']), len(self.expected['runs']) + 1)
            self.assertIn('clef-openrouter-native-fresh2-p0', {run['id'] for run in feed['runs']})

    def test_final_projection_and_unknown_bound_cannot_be_cleaned_by_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.small_copy(temp)
            path = root / subject.SOLAR_FULL
            value = json.loads(path.read_text())
            final = value['stages'][-1]
            final['valid_answers'] = 60
            path.write_text(json.dumps(value))
            with self.builder_stubs(), self.assertRaisesRegex(ValueError, 'report differs'):
                subject.build(root)

    def test_invalid_score_cost_and_private_link_rejected(self):
        example = self.expected['runs'][0]
        args = ('solar-decide', example['model'], example['returnedModel'],
                example['provider'], subject.THREE, 'fresh1/P0',
                {'all_four': 61, **{key: 55 for key in subject.FIELDS}}, 1, 1,
                '0.01', subject.solar_builder.PROJECTION, 'a' * 64, subject.SOLAR)
        with self.assertRaisesRegex(ValueError, 'out of 60'):
            subject.row(*args)
        args = (*args[:6], {'all_four': 55, **{key: 55 for key in subject.FIELDS}},
                *args[7:])
        with self.assertRaisesRegex(ValueError, 'charge'):
            subject.row(*args[:9], '-0.01', *args[10:])
        with self.assertRaisesRegex(ValueError, 'Private source'):
            subject.row(*args[:10], Path('private/raw.jsonl'), *args[11:])


if __name__ == '__main__':
    unittest.main()
