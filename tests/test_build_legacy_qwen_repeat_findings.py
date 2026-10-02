import importlib.util
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('legacy_qwen_findings',
    ROOT / 'scripts/build_legacy_qwen_repeat_findings.py')
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
findings = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(findings)


class LegacyQwenFindingsTests(unittest.TestCase):
    def test_report_rebuilds_from_closed_source_and_tracks_all_configurations(self):
        report = findings.build(ROOT)
        saved = json.loads((ROOT / findings.OUTPUT).read_text())
        self.assertEqual(report, saved)
        self.assertEqual([row['configuration'] for row in report['series']], list(findings.CONFIGS))
        self.assertEqual([row['displayName'] for row in report['series']],
                         [findings.DISPLAY_NAMES[name] for name in findings.CONFIGS])
        target = report['series'][0]
        self.assertGreaterEqual(target['completedConditions'], 1)
        self.assertEqual(target['passes']['fresh1']['P0']['score']['denominator'], 60)
        self.assertEqual(target['passes']['fresh1']['P0']['score']['valid'], 60)
        self.assertEqual(target['passes']['fresh1']['P0']['score']['allFour'], 0)
        self.assertEqual(target['passes']['fresh1']['P0']['predictedClassCounts']['testimonial_potential'],
                         {'yes': 60})
        self.assertEqual(target['passes']['fresh1']['P0']['classConfusion']['testimonial_potential'],
                         {'insufficient_information': {'yes': 1},
                          'no': {'yes': 50}, 'yes': {'yes': 9}})
        self.assertEqual(len(target['missingPasses']) + target['completedConditions'], 9)
        self.assertEqual(target['passes']['fresh1']['P0']['usage']['actualCostUsd'], None)
        for other in report['series'][1:]:
            self.assertEqual(other['completedConditions'] + len(other['missingPasses']), 9)

    def test_inspected_stopped_sdk_smoke_is_bound_but_unscored(self):
        report = findings.build(ROOT)
        for config_id, expected in [('qwen3-0.6b-sdk-thinking-on', (1, 2)),
                                    ('qwen3-0.6b-sdk-thinking-off', (0, 3))]:
            with self.subTest(config_id=config_id):
                series = next(row for row in report['series']
                              if row['configuration'] == config_id)
                item = next(row for row in series['missingPasses']
                            if row['pass'] == 'fresh1' and row['condition'] == 'P0')
                self.assertEqual(item['status'], 'smoke_blocked')
                self.assertEqual((item['stage'], item['attempted'], item['saved'],
                                  item['valid'], item['invalid']), ('smoke', 3, 3, *expected))
                self.assertNotIn('P0', series['passes']['fresh1'])
                self.assertEqual(series['completedConditions'], 0)
                bound = {source['path'] for source in series['sourceBindings']}
                self.assertTrue({item['evidence']['inspection']['path'],
                                 item['evidence']['raw']['path'],
                                 item['evidence']['completion']['path']} <= bound)

    def test_closed_phase_rejects_mutated_saved_record(self):
        phase = findings.BASE / findings.TARGET / 'fresh1' / 'P0'
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for name in ('smoke', 'development'):
                for suffix in ('root-review.json', 'claim.json', 'raw.jsonl',
                               'records.jsonl', 'journal.jsonl', 'completion.json'):
                    relative = phase / f'{name}.{suffix}'
                    dest = temp / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / relative, dest)
            review = json.loads((ROOT / phase / 'development.root-review.json').read_text())
            audit = Path(review['route_catalog_file'])
            (temp / audit).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / audit, temp / audit)
            record_file = temp / phase / 'development.records.jsonl'
            record_file.write_bytes(record_file.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'Source hash differs|Closed stage evidence differs'):
                findings.closed_stage(temp, plan, findings.TARGET, 'fresh1', 'P0',
                                      'development', findings.binder(temp)[0])

    def test_pairwise_flips_wait_for_two_closed_passes_and_use_shared_valid_ids(self):
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        first = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in findings.IDS}
        second = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in findings.IDS}
        second['DEV-001']['prediction']['sentiment'] = 'negative'
        second['DEV-002'] = {'status': 'invalid_output', 'prediction': None}
        score = {'allFour': 0, 'fields': {field: 0 for field in findings.FIELDS}}
        passes = {'fresh1': {'P0': {'score': score}}, 'fresh2': {}, 'fresh3': {}}
        by_condition, flips, across = findings.summary(passes, {('fresh1', 'P0'): first})
        self.assertEqual(flips, [])
        self.assertEqual(by_condition['P0']['allFour']['completedPasses'], 1)
        passes['fresh2']['P0'] = {'score': score}
        _, flips, across = findings.summary(passes, {('fresh1', 'P0'): first,
                                                     ('fresh2', 'P0'): second})
        self.assertEqual(len(flips), 1)
        self.assertEqual(flips[0]['denominator'], 59)
        self.assertEqual(flips[0]['excludedIds'], ['DEV-002'])
        self.assertEqual(flips[0]['sentiment']['caseIds'], ['DEV-001'])
        self.assertEqual(across, {})

    def test_confusion_excludes_invalid_response_from_each_reference_class(self):
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        labels = {rid: prediction.copy() for rid in findings.IDS}
        rows = {rid: {'status': 'ok', 'prediction': prediction.copy()} for rid in findings.IDS}
        labels['DEV-001']['testimonial_potential'] = 'yes'
        rows['DEV-001'] = {'status': 'invalid_output', 'prediction': None}
        rows['DEV-002']['prediction']['testimonial_potential'] = 'yes'
        counts, confusion = findings.class_counts(rows, labels)
        self.assertEqual(counts['testimonial_potential'], {'no': 58, 'yes': 1})
        self.assertEqual(confusion['testimonial_potential'], {'no': {'no': 58, 'yes': 1},
                                                             'yes': {}})

    def test_sdk_frozen_adapter_fixture_classification_and_usage(self):
        plan = json.loads((ROOT / findings.MANIFEST).read_text())
        config = plan['configurations']['qwen3-0.6b-sdk-thinking-on']
        request = config['conditions']['P0']['requests'][0]
        historical = json.loads((ROOT / 'results/qwen3-0.6b-sdk-thinking-2026-09-21/'
                                 'development.jsonl').read_text().splitlines()[0])
        prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                      'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        result = {'modelInfo': historical['model_info'],
                  'loadConfig': historical['load_config'],
                  'predictionConfig': historical['prediction_config'],
                  'stats': historical['stats'], 'content': historical['raw_response'],
                  'nonReasoningContent': json.dumps(prediction)}
        raw = {'result': result, 'elapsed_seconds': 1.5}
        self.assertEqual(findings.classify_sdk(raw, config, request),
                         {'status': 'ok', 'prediction': prediction})
        tokens = findings.usage([raw], 'lmstudio_sdk')['tokens']
        self.assertEqual(tokens['input_tokens'], result['stats']['promptTokensCount'])
        self.assertEqual(tokens['output_tokens'], result['stats']['predictedTokensCount'])
        self.assertEqual(tokens['total_tokens'], result['stats']['totalTokensCount'])
        self.assertIsNone(tokens['reasoning_output_tokens'])

        altered = copy.deepcopy(raw)
        altered['result']['stats']['promptTokensCount'] += 1
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'control_failure', 'reason': 'prompt_token_count'})
        altered = copy.deepcopy(raw)
        altered['result']['predictionConfig']['fields'][0]['value'] = 'changed'
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'control_failure', 'reason': 'prediction_config'})
        altered = copy.deepcopy(raw)
        altered['result']['nonReasoningContent'] = '```json\n{}\n```'
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'invalid_output', 'reason': 'non_json'})
        altered = copy.deepcopy(raw)
        altered['result']['stats']['stopReason'] = 'maxPredictedTokensReached'
        self.assertEqual(findings.classify_sdk(altered, config, request),
                         {'status': 'invalid_output', 'reason': 'stop_reason'})


if __name__ == '__main__':
    unittest.main()
