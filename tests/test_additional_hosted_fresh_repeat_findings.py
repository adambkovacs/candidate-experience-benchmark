"""Synthetic sealed evidence for Qwen off and DeepSeek low v2 reporting."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import build_additional_hosted_fresh_repeat_findings as report
import export_provider_error_public_evidence as provider_export
import openrouter_paid_benchmark as paid
from development_benchmark import read_rows


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


def copy_public_provider_error_bundle(root):
    source = REPO / 'public-evidence/provider-errors-v1'
    target = root / 'public-evidence/provider-errors-v1'
    shutil.copytree(source, target, dirs_exist_ok=True)


def saved_qwen_context(case):
    """Use frozen public controls when the private historical P2 raw is absent."""
    saved_manifest = json.loads((REPO / case.base / 'manifest.json').read_text())
    plan_path = REPO / saved_manifest['admission_plan']
    plan = json.loads(plan_path.read_text())
    if report.sha(plan_path) != saved_manifest['admission_plan_sha256']:
        raise ValueError('Saved Qwen plan hash differs')
    bound = {item['path']: item['sha256'] for item in plan['source_bindings']}
    for source in (case.admission.HOSTED, case.admission.P0):
        relative = str(source.relative_to(case.admission.ROOT))
        if bound.get(relative) != report.sha(source):
            raise ValueError('Saved Qwen public control source differs')
    matches = [item for item in json.loads(case.admission.HOSTED.read_text())['configurations']
               if item['id'] == case.admission.CONFIG]
    if len(matches) != 1:
        raise ValueError('Saved Qwen historical configuration differs')
    history = matches[0]
    controls = history['controls']['adapter_controls']['request_controls']
    original_p0 = json.loads(case.admission.P0.read_text().splitlines()[0])
    return history, controls, original_p0['provider_endpoint'], original_p0['model_catalog_entry'], plan


def synthetic_ledger_snapshot(case):
    """Keep fixture admission independent of the evolving paid ledger state."""
    return {'cap_usd': '10', 'accounted_usd': '0', 'headroom_usd': '10',
            'pending_attempts': 0, 'active_partitions': [], 'blocked': False,
            'closed': False, 'admission_capacity_now': True,
            'ledger_sha256': report.sha(case.admission.MASTER)}


class SeriesFixture:
    def __init__(self, case, root, cap):
        self.spec, self.root, self.cap = case, root, cap
        self.base = root / case.base
        self.base.mkdir(parents=True, exist_ok=True)
        copy_public_provider_error_bundle(root)
        self.inputs = read_rows(case.admission.INPUTS)
        public_only_qwen = (case.admission.CONFIG == 'openrouter-paid-qwen36-35b-a3b-off'
                            and not case.admission.P2.is_file())
        if public_only_qwen:
            self.history, self.controls, self.endpoint, self.model, plan = saved_qwen_context(case)
        else:
            self.history, self.controls, self.endpoint, self.model = case.admission.source_state()
            snapshot = synthetic_ledger_snapshot(case)
            with patch.object(case.admission, 'ledger_snapshot', return_value=snapshot):
                plan = case.admission.plan_data()
        with tempfile.TemporaryDirectory(dir=REPO) as temp:
            plan_path, manifest_path = Path(temp) / 'plan.json', Path(temp) / 'manifest.json'
            plan_path.write_text(json.dumps(plan))
            context = (patch.object(case.admission, 'plan_data', return_value=plan)
                       if public_only_qwen else
                       patch.object(case.admission, 'ledger_snapshot', return_value=snapshot))
            with context:
                manifest = case.execution.freeze(plan_path, manifest_path)
            relative = Path(manifest['admission_plan'])
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plan_path, target)
            shutil.copy2(manifest_path, self.base / 'manifest.json')
        self.manifest = manifest
        for source in manifest['source_bindings'] + manifest['code_bindings']:
            if source['path'] not in case.execution.MUTABLE:
                self.copy(source['path'])
        self.copy(report.LABELS)
        self.partition = {'id': 'synthetic-' + case.effort,
                          'model': case.admission.MODEL, 'provider': case.admission.PROVIDER,
                          'reasoning': case.effort, 'cap_usd': cap,
                          'child_ledger': str(REPO / case.base / ('budget-synthetic-' + case.effort + '.jsonl'))}
        budget = {'version': 'paid-partitions-v1',
                  'master_ledger': str(REPO / 'results/openrouter-paid-budget.jsonl'),
                  'partitions': [self.partition]}
        write_json(self.base / 'budget.json', budget)
        self.ledger = self.base / ('budget-' + self.partition['id'] + '.jsonl')
        write_rows(self.ledger, [{'event': 'budget', 'cap_usd': cap}])

    def copy(self, relative):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not (REPO / relative).exists() and str(relative) in {
                path for path, _, _ in provider_export.INVENTORY}:
            return  # Public bundle is copied and the report binds its actual bytes.
        shutil.copy2(REPO / relative, target)

    def stage(self, index, name, invalid_id=None, changed_id=None):
        spec = self.spec
        phase = self.manifest['phases'][index]
        condition = phase['condition']
        ids = phase['smoke_ids'] if name == 'smoke' else phase['development_ids']
        source = (self.history['baseline_instruction'] if condition == 'P0' else
                  self.history['conditions'][condition]['instruction'])
        policy = (REPO / source['file']).read_text()
        schema = self.controls['response_format']['json_schema']['schema']
        stem = self.base / f'phase-{index + 1:02d}-{name}'
        paths = {part: Path(str(stem) + suffix) for part, suffix in
                 (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
                  ('raw', '.raw.jsonl'), ('records', '.records.jsonl'),
                  ('review', '.root-review.json'))}
        receipt = {'approved': True, 'manifest_sha256': report.sha(self.base / 'manifest.json'),
                   'budget_manifest_sha256': report.sha(self.base / 'budget.json'),
                   'partition_id': self.partition['id'], 'phase_index': index, 'stage': name,
                   'runner_sha256': report.sha(self.root / 'scripts' /
                                               Path(spec.execution.__file__).name)}
        if name == 'development':
            smoke = self.base / f'phase-{index + 1:02d}-smoke'
            receipt['smoke_inspection'] = {'approved': True, 'statuses': ['ok'] * 3,
                **{'smoke_' + part + '_sha256': report.sha(Path(str(smoke) + '.' + part + '.jsonl'))
                   for part in ('records', 'journal', 'raw')}}
        write_json(paths['review'], receipt)
        claim = {'schema': 'affordable-hosted-stage-claim-v1',
                 'manifest_sha256': receipt['manifest_sha256'],
                 'review_sha256': report.sha(paths['review']),
                 'budget_manifest_sha256': receipt['budget_manifest_sha256'],
                 'partition_id': self.partition['id'], 'phase_index': index,
                 'repeat': phase['repeat'], 'condition': condition, 'stage': name, 'ids': ids}
        write_json(paths['claim'], claim)
        events = [{'event': 'stage_claimed', 'claim_sha256': report.sha(paths['claim'])}]
        raw_lines, records, budget_events = [], [], []
        for position, rid in enumerate(ids):
            item = self.inputs[position]
            frozen = self.manifest['requests_by_condition'][condition][position]
            payload = paid.make_payload(spec.admission.MODEL, self.endpoint, item['feedback'],
                                        policy, schema, spec.effort, 4096,
                                        paid.number('0.1'),
                                        paid.number('0.9' if spec.effort == 'off' else '0.5'),
                                        self.model)
            attempt = f'synthetic-{spec.effort}-{index}-{name}-{rid}'
            prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                          'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
            if changed_id == rid:
                prediction['sentiment'] = 'positive'
            is_invalid = name == 'development' and spec.continue_on_invalid and invalid_id == rid
            content = '{invalid' if is_invalid else json.dumps(prediction)
            body = {'model': spec.admission.MODEL, 'provider': spec.provider_name,
                    'usage': {'cost': '0.0001', 'prompt_tokens': 10, 'completion_tokens': 5,
                              'total_tokens': 15},
                    'choices': [{'message': {'content': content}, 'finish_reason': 'stop'}]}
            actual_prediction = None if is_invalid else prediction
            status = 'invalid_output' if is_invalid else 'ok'
            raw_lines.append(json.dumps({'attempt_id': attempt, 'id': rid, 'body': body}) + '\n')
            records.append({'id': rid, 'repeat': phase['repeat'], 'condition': condition,
                            'phase': name, 'attempt_id': attempt, 'request': payload,
                            'request_sha256': frozen['request_sha256'],
                            'input_sha256': frozen['input_sha256'],
                            'policy_sha256': frozen['instruction_sha256'],
                            'requested_model': spec.admission.MODEL,
                            'provider_endpoint': self.endpoint,
                            'raw_response': body, 'usage': body['usage'],
                            'returned_model': spec.admission.MODEL,
                            'returned_provider': spec.provider_name,
                            'finish_reason': 'stop', 'prediction': actual_prediction,
                            'status': status, 'reference_labels_read': False,
                            'reserved_cost_usd': str(spec.admission.RESERVE),
                            'budget_partition_id': self.partition['id'],
                            'reasoning_effort': spec.effort,
                            'continue_on_invalid_output': spec.continue_on_invalid,
                            'client_request_started_utc': '2026-09-29T10:00:00+00:00',
                            'client_request_finished_utc': '2026-09-29T10:00:01+00:00',
                            'client_http_duration_seconds': 0.2,
                            'observed_cost_usd': '0.0001', 'cost_unknown': False,
                            'billing_ok': True})
            events.extend(({'event': 'request_started', 'attempt_id': attempt, 'id': rid,
                            'request_sha256': frozen['request_sha256'],
                            'reserved_cost_usd': str(spec.admission.RESERVE)},
                           {'event': 'raw_saved', 'attempt_id': attempt,
                            'raw_sha256': hashlib.sha256(''.join(raw_lines).encode()).hexdigest()},
                           {'event': 'request_finished', 'attempt_id': attempt, 'id': rid,
                            'status': status, 'billing_ok': True}))
            budget_events.extend(({'event': 'reserve', 'attempt_id': attempt,
                                   'record_id': rid, 'usd': str(spec.admission.RESERVE)},
                                  {'event': 'settle', 'attempt_id': attempt,
                                   'usd': '0.0001'}))
        events.append({'event': 'stage_completed', 'count': len(ids)})
        write_rows(paths['journal'], events)
        paths['raw'].write_text(''.join(raw_lines))
        write_rows(paths['records'], records)
        with self.ledger.open('a') as out:
            out.write(''.join(json.dumps(event) + '\n' for event in budget_events))
        return paths


class AdditionalHostedReporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_both_series_missing_are_explicit(self):
        result = report.build(self.root)
        self.assertEqual([], result['series'])
        self.assertEqual(2, len(result['missingSeries']))
        self.assertEqual([], result['sourceBindings'])
        orphan = self.root / report.SPECS[0].base / 'phase-01-development.journal.jsonl'
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text('{"event":"stage_completed","count":60}\n')
        with self.assertRaisesRegex(ValueError, 'without a v2 manifest'):
            report.build(self.root)

    def test_optional_qwen_closed_and_low_missing(self):
        qwen = SeriesFixture(report.SPECS[0], self.root, '0.15')
        qwen.stage(0, 'smoke')
        qwen.stage(0, 'development')
        report.capture_prefix(self.root, qwen.spec, 0)
        result = report.build(self.root)
        self.assertEqual([qwen.spec.series_id], [item['seriesId'] for item in result['series']])
        self.assertEqual(result['schema'], result['series'][0]['schema'])
        self.assertEqual(1, result['series'][0]['completedConditions'])
        self.assertEqual(60, result['series'][0]['passes']['fresh1']['P0']['score']['valid'])
        self.assertEqual(1, len(result['missingSeries']))
        self.assertTrue(all(not item['path'].startswith(str(self.root))
                            for item in result['sourceBindings']))
        raw = qwen.base / 'phase-01-development.raw.jsonl'
        raw.write_text(raw.read_text().replace('neutral', 'positive', 1))
        with self.assertRaisesRegex(ValueError, 'strict runner verification'):
            report.build(self.root)

    def test_frozen_manifest_without_budget_is_pending(self):
        qwen = SeriesFixture(report.SPECS[0], self.root, '0.15')
        (qwen.base / 'budget.json').unlink()
        result = report.build(self.root)
        self.assertEqual([], result['series'])
        self.assertEqual('budget_absent', result['missingSeries'][0]['status'])
        (qwen.base / 'phase-01-development.claim.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'without a budget manifest'):
            report.build(self.root)

    def test_low_invalid_keeps_sixty_denominator_and_shared_valid_flips(self):
        low = SeriesFixture(report.SPECS[1], self.root, '0.25')
        for index in range(4):
            low.stage(index, 'smoke')
            low.stage(index, 'development', invalid_id='DEV-042' if index == 2 else None,
                      changed_id='DEV-001' if index == 3 else None)
            report.capture_prefix(self.root, low.spec, index)
        result = report.build(self.root)
        series = result['series'][0]
        self.assertEqual(4, series['completedConditions'])
        first_p2 = series['passes']['fresh1']['P2']['score']
        self.assertEqual(60, first_p2['denominator'])
        self.assertEqual(59, first_p2['valid'])
        self.assertEqual(['DEV-042'], first_p2['invalidIds'])
        self.assertEqual({'ok': 59, 'invalid_output': 1}, first_p2['outcomes'])
        pair = next(item for item in series['pairwiseFlips'] if item['condition'] == 'P2')
        self.assertEqual(59, pair['denominator'])
        self.assertEqual(['DEV-042'], pair['excludedIds'])
        self.assertEqual(['DEV-001'], pair['sentiment']['caseIds'])
        self.assertEqual(5, len(series['missingPasses']))
        snapshot = low.base / 'phase-04-budget-prefix.jsonl'
        snapshot.write_text(snapshot.read_text().replace('"usd": "0.0001"',
                                                         '"usd": "0.9"', 1))
        with self.assertRaisesRegex(ValueError, 'budget settlement|Budget prefix'):
            report.build(self.root)

    def test_open_stage_is_unscored(self):
        low = SeriesFixture(report.SPECS[1], self.root, '0.25')
        stem = low.base / 'phase-01-development'
        Path(str(stem) + '.journal.jsonl').write_text('{"event":"request_started"}\n')
        result = report.build(self.root)
        self.assertEqual(0, result['series'][0]['completedConditions'])
        self.assertEqual(9, len(result['series'][0]['missingPasses']))
        low.stage(1, 'smoke')
        low.stage(1, 'development')
        with self.assertRaisesRegex(ValueError, 'incomplete predecessor'):
            report.build(self.root)

    def test_lower_price_stage_requires_exact_successor_receipt_and_sources(self):
        low = SeriesFixture(report.SPECS[1], self.root, '0.25')
        low.stage(0, 'smoke')
        low.stage(0, 'development')
        report.capture_prefix(self.root, low.spec, 0)
        low.stage(1, 'smoke')
        development = low.stage(1, 'development')
        records = read_rows(development['records'])
        for row in records:
            row['provider_endpoint']['pricing']['prompt'] = (
                report.low_price_successor.NEW_PROMPT_PRICE)
        write_rows(development['records'], records)
        for relative in (
            'scripts/deepseek_low_price_successor_v1.py',
            'tests/test_deepseek_low_price_successor_v1.py',
            str(low.spec.base / 'lower-price-endpoint-audit-v1.json'),
        ):
            low.copy(relative)
        with self.assertRaisesRegex(ValueError, 'supplemental root review'):
            report.capture_prefix(self.root, low.spec, 1)
        supplement = low.base / 'phase-02-development.price-amendment.root-review.json'
        successor = report.low_price_successor
        with patch.object(successor, 'ROOT', self.root), \
             patch.object(successor, 'BASE', low.base), \
             patch.object(successor, 'ROUTE_AUDIT', low.base / 'lower-price-endpoint-audit-v1.json'), \
             patch.object(successor, '__file__', str(self.root / 'scripts/deepseek_low_price_successor_v1.py')), \
             patch.object(report.low_execution, 'ROOT', self.root), \
             patch.object(report.low_execution, '__file__', str(self.root / 'scripts/deepseek_low_fresh_repeat_execution_v2.py')):
            expected = successor.amendment_fields(1, 'development',
                report.sha(low.base / 'manifest.json'), development['review'])
        write_json(supplement, expected)
        report.capture_prefix(self.root, low.spec, 1)
        series = report.build(self.root)['series'][0]
        phase = series['passes']['fresh1']['P1']
        self.assertEqual(successor.OLD_PROMPT_PRICE,
            phase['servedRoute']['historicalPromptPriceUsdPerToken'])
        self.assertEqual(successor.NEW_PROMPT_PRICE,
            phase['servedRoute']['observedPromptPriceUsdPerToken'])
        self.assertEqual(0.1, records[0]['request']['provider']['max_price']['prompt'])
        self.assertIn('amendmentReview', phase['evidence'])
        self.assertIn('successorController', phase['evidence'])
        self.assertIn('successorTests', phase['evidence'])
        self.assertIn('routeAudit', phase['evidence'])
        self.assertNotIn('observedPromptPriceUsdPerToken',
                         series['passes']['fresh1']['P0']['servedRoute'])
        supplement.write_text(supplement.read_text().replace(
            successor.NEW_PROMPT_PRICE, '0.00000002'))
        with self.assertRaisesRegex(ValueError, 'supplemental root review'):
            report.build(self.root)


if __name__ == '__main__':
    unittest.main()
