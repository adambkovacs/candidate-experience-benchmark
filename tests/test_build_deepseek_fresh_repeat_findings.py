"""Synthetic sealed and in-progress DeepSeek fresh-report evidence."""
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import affordable_hosted_repeat_admission as admission
import affordable_hosted_repeat_execution as execution
import build_deepseek_fresh_repeat_findings as report
from development_benchmark import read_rows
import openrouter_paid_benchmark as paid


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


class DeepSeekReporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = self.root / report.BASE
        self.base.mkdir(parents=True)
        self.copy(report.BASE / 'manifest.json')
        self.copy(report.BASE / 'admission-plan.json')
        self.copy(report.LABELS)
        self.manifest = json.loads((self.base / 'manifest.json').read_text())
        for source in self.manifest['source_bindings'] + self.manifest['code_bindings']:
            if source['path'] not in execution.MUTABLE:
                self.copy(source['path'])
        self.copy(report.BASE / 'budget.json')
        self.budget = json.loads((self.base / 'budget.json').read_text())
        self.partition = self.budget['partitions'][0]
        self.ledger = self.base / ('budget-' + self.partition['id'] + '.jsonl')
        write_rows(self.ledger, [{'event': 'budget', 'cap_usd': self.partition['cap_usd']}])
        self.template = json.loads((REPO / report.BASE / 'phase-01-smoke.records.jsonl').read_text().splitlines()[0])
        self.raw_template = self.template['raw_response']
        history, controls, endpoint, model = admission.source_state()
        self.endpoint, self.model = endpoint, model
        self.history, self.schema = history, controls['response_format']['json_schema']['schema']
        self.inputs = read_rows(admission.INPUTS)

    def copy(self, relative):
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, target)

    def make_stage(self, index, stage, changed=None):
        phase = self.manifest['phases'][index]
        condition = phase['condition']
        ids = phase['smoke_ids'] if stage == 'smoke' else phase['development_ids']
        policy_source = (self.history['baseline_instruction'] if condition == 'P0'
                         else self.history['conditions'][condition]['instruction'])
        policy = (REPO / policy_source['file']).read_text()
        prefix = self.base / f'phase-{index+1:02d}-{stage}'
        claim_path = Path(str(prefix) + '.claim.json')
        journal_path = Path(str(prefix) + '.journal.jsonl')
        raw_path = Path(str(prefix) + '.raw.jsonl')
        records_path = Path(str(prefix) + '.records.jsonl')
        review_path = Path(str(prefix) + '.root-review.json')
        receipt = {'approved': True, 'manifest_sha256': report.sha(self.base / 'manifest.json'),
                   'budget_manifest_sha256': report.sha(self.base / 'budget.json'),
                   'partition_id': self.partition['id'], 'phase_index': index,
                   'stage': stage, 'runner_sha256': report.sha(self.root / 'scripts/affordable_hosted_repeat_execution.py')}
        if stage == 'development':
            smoke = self.base / f'phase-{index+1:02d}-smoke'
            receipt['smoke_inspection'] = {'approved': True, 'statuses': ['ok'] * 3,
                **{'smoke_' + key + '_sha256': report.sha(Path(str(smoke) + '.' + key + '.jsonl'))
                   for key in ('records', 'journal', 'raw')}}
        write_json(review_path, receipt)
        claim = {'schema': 'affordable-hosted-stage-claim-v1',
                 'manifest_sha256': receipt['manifest_sha256'],
                 'review_sha256': report.sha(review_path),
                 'budget_manifest_sha256': receipt['budget_manifest_sha256'],
                 'partition_id': self.partition['id'], 'phase_index': index,
                 'repeat': phase['repeat'], 'condition': condition,
                 'stage': stage, 'ids': ids}
        write_json(claim_path, claim)
        events = [{'event': 'stage_claimed', 'claim_sha256': report.sha(claim_path)}]
        raw_lines, records, budget_events = [], [], []
        for pos, (rid, item) in enumerate(zip(ids, self.inputs)):
            frozen = self.manifest['requests_by_condition'][condition][pos]
            payload = paid.make_payload(admission.MODEL, self.endpoint, item['feedback'], policy,
                                        self.schema, 'off', 4096, paid.number('0.1'),
                                        paid.number('0.5'), self.model)
            attempt = f'synthetic-{index}-{stage}-{rid}'
            body = copy.deepcopy(self.raw_template)
            prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                          'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
            if changed and rid == 'DEV-001':
                prediction['sentiment'] = 'positive'
            body['choices'][0]['message']['content'] = json.dumps(prediction)
            body['usage']['cost'] = 0.0001
            raw = {'attempt_id': attempt, 'id': rid, 'body': body}
            raw_lines.append(json.dumps(raw) + '\n')
            row = copy.deepcopy(self.template)
            row.update(id=rid, repeat=phase['repeat'], condition=condition, phase=stage,
                       attempt_id=attempt, request=payload, request_sha256=frozen['request_sha256'],
                       input_sha256=frozen['input_sha256'], policy_sha256=frozen['instruction_sha256'],
                       budget_partition_id=self.partition['id'], provider_endpoint=self.endpoint,
                       raw_response=body, usage=body['usage'], prediction=prediction,
                       observed_cost_usd='0.0001', reserved_cost_usd=str(admission.RESERVE),
                       client_http_duration_seconds=0.2)
            records.append(row)
            events.extend([
                {'event': 'request_started', 'attempt_id': attempt, 'id': rid,
                 'request_sha256': frozen['request_sha256'], 'reserved_cost_usd': str(admission.RESERVE)},
                {'event': 'raw_saved', 'attempt_id': attempt,
                 'raw_sha256': hashlib.sha256(''.join(raw_lines).encode()).hexdigest()},
                {'event': 'request_finished', 'attempt_id': attempt, 'id': rid,
                 'status': 'ok', 'billing_ok': True}])
            budget_events.extend([{'event': 'reserve', 'attempt_id': attempt, 'record_id': rid,
                                   'usd': str(admission.RESERVE)},
                                  {'event': 'settle', 'attempt_id': attempt, 'usd': '0.0001'}])
        events.append({'event': 'stage_completed', 'count': len(ids)})
        write_rows(journal_path, events)
        raw_path.write_text(''.join(raw_lines))
        write_rows(records_path, records)
        with self.ledger.open('a') as out:
            out.write(''.join(json.dumps(event) + '\n' for event in budget_events))
        return {'claim': claim_path, 'journal': journal_path, 'raw': raw_path,
                'records': records_path, 'review': review_path}

    def test_unclosed_stage_is_stable_and_unscored(self):
        baseline = report.build(self.root)
        stem = self.base / 'phase-01-development'
        Path(str(stem) + '.claim.json').write_text('{}')
        Path(str(stem) + '.journal.jsonl').write_text('{"event":"request_started"}\n')
        Path(str(stem) + '.records.jsonl').write_text('{partial')
        self.assertEqual(baseline, report.build(self.root))
        self.assertEqual(0, baseline['series'][0]['completedConditions'])
        self.assertEqual(9, len(baseline['series'][0]['missingPasses']))
        Path(str(stem) + '.journal.jsonl').write_text('{"event":"request_started"}\n{"event":')
        self.assertEqual(baseline, report.build(self.root))

    def test_closed_phase_scored_and_tamper_rejected(self):
        self.make_stage(0, 'smoke')
        paths = self.make_stage(0, 'development')
        report.capture_prefix(self.root, 0)
        series = report.build(self.root)['series'][0]
        self.assertEqual(1, series['completedConditions'])
        entry = series['passes']['fresh1']['P0']
        self.assertEqual(60, entry['score']['denominator'])
        self.assertEqual(60, entry['score']['valid'])
        self.assertEqual(60, sum(sum(row.values()) for row in entry['score']['confusionCounts']['sentiment'].values()))
        self.assertEqual('0.0060', entry['usage']['actualCostUsd'])
        self.assertEqual('client_http_duration_not_provider_inference', entry['usage']['timingKind'])
        self.assertEqual(60, entry['evidence']['budgetSettlement']['settledAttempts'])
        text = paths['raw'].read_text().replace('neutral', 'positive', 1)
        paths['raw'].write_text(text)
        with self.assertRaisesRegex(ValueError, 'strict runner verification'):
            report.build(self.root)

    def test_missing_settlement_and_bad_smoke_receipt_rejected(self):
        self.make_stage(0, 'smoke')
        self.make_stage(0, 'development')
        with self.assertRaises(FileNotFoundError):
            report.build(self.root)
        report.capture_prefix(self.root, 0)
        report.build(self.root)
        snapshot = self.root / report.prefix_path(0)
        snapshot.write_text(snapshot.read_text().replace('"usd": "0.0001"', '"usd": "0.9"', 1))
        with self.assertRaisesRegex(ValueError, 'budget settlement'):
            report.build(self.root)
        snapshot.write_text(snapshot.read_text().replace('"usd": "0.9"', '"usd": "0.0001"', 1))
        review = self.base / 'phase-01-development.root-review.json'
        receipt = json.loads(review.read_text())
        receipt['smoke_inspection']['smoke_raw_sha256'] = '0' * 64
        write_json(review, receipt)
        with self.assertRaisesRegex(ValueError, 'smoke inspection'):
            report.build(self.root)

    def test_prompt_flips_and_three_pass_ranges(self):
        for index, phase in enumerate(self.manifest['phases']):
            self.make_stage(index, 'smoke')
            self.make_stage(index, 'development', changed=(phase['condition'] == 'P1' and phase['repeat'] == 'fresh2'))
            report.capture_prefix(self.root, index)
        series = report.build(self.root)['series'][0]
        self.assertEqual(9, series['completedConditions'])
        self.assertEqual(3, series['pairedDeltaSpread']['P1']['completedPairs'])
        self.assertEqual(60, series['withinPassPromptFlips'][0]['denominator'])
        self.assertEqual(1, next(x for x in series['pairwiseFlips'] if x['condition'] == 'P1' and
                                 x['from'] == 'fresh1' and x['to'] == 'fresh2')['sentiment']['changed'])
        self.assertEqual(['DEV-001'], series['changesAcrossThreePasses']['P1']['fields']['sentiment'])

    def test_later_live_appends_do_not_change_closed_report(self):
        self.make_stage(0, 'smoke')
        self.make_stage(0, 'development')
        snapshot = report.capture_prefix(self.root, 0)
        before = report.build(self.root)
        with self.ledger.open('ab') as out:
            out.write(b'{"event":"reserve","attempt_id":"later","record_id":"DEV-001","usd":"0.1069056"}\n')
            out.write(b'{"event":"settle","attempt_id":"later"')
        self.assertEqual(before, report.build(self.root))
        self.assertEqual(snapshot, report.capture_prefix(self.root, 0))
        self.ledger.unlink()
        self.assertEqual(before, report.build(self.root))

    def test_real_tracked_phase_relocates_with_original_budget_and_snapshot(self):
        archive = subprocess.run(['git', 'archive', 'HEAD'], cwd=REPO, check=True,
                                 stdout=subprocess.PIPE).stdout
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with tarfile.open(fileobj=BytesIO(archive)) as tar:
                tar.extractall(root, filter='data')
            for phase in range(2, 10):
                (root / report.BASE / f'phase-{phase:02d}-development.journal.jsonl').unlink(missing_ok=True)
            (root / report.prefix_path(0)).unlink(missing_ok=True)
            budget = json.loads((root / report.BASE / 'budget.json').read_text())
            self.assertEqual((REPO / report.BASE / 'budget.json').read_bytes(),
                             (root / report.BASE / 'budget.json').read_bytes())
            partition = budget['partitions'][0]
            ledger = root / report.BASE / ('budget-' + partition['id'] + '.jsonl')
            values = [{'event': 'budget', 'cap_usd': partition['cap_usd']}]
            for stage in ('smoke', 'development'):
                records = report.rows(root / report.BASE / f'phase-01-{stage}.records.jsonl')
                for row in records:
                    values.extend(({'event': 'reserve', 'attempt_id': row['attempt_id'],
                                    'record_id': row['id'], 'usd': row['reserved_cost_usd']},
                                   {'event': 'settle', 'attempt_id': row['attempt_id'],
                                    'usd': row['observed_cost_usd']}))
            write_rows(ledger, values)
            self.assertTrue(report.closed(root, 0, 'development'))
            with self.assertRaises(FileNotFoundError):
                report.build(root)
            report.capture_prefix(root, 0)
            self.assertEqual(1, report.build(root)['series'][0]['completedConditions'])


if __name__ == '__main__':
    unittest.main()
