"""Offline public-only checks for DeepSeek-low interruption findings."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import build_deepseek_low_interruption_findings as report
import build_additional_hosted_fresh_repeat_findings as additional


class PublicFixture:
    def __init__(self, case):
        self.temp = tempfile.TemporaryDirectory()
        case.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.generic, self.manifest, self.labels, self.ids, self.partition, _, self.binding = \
            report.source_context(REPO)
        for index in (1, 2):
            relative = report.BASE / f'phase-{index:02d}-development.records.jsonl'
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        self.source = patch.object(report, 'source_context', side_effect=self.context)
        self.source.start()
        case.addCleanup(self.source.stop)
        self.prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
            'serious_concern_reported': 'no', 'testimonial_potential': 'yes'}
        self.budget = [{'event': 'budget', 'cap_usd': self.manifest['child_cap_usd']}]

    def context(self, _root):
        return (copy.deepcopy(self.generic), self.manifest, self.labels, self.ids,
                self.partition, [], self.binding)

    def row(self, condition, pos, *, status='ok', cost='0.0001', prefix='new'):
        item = self.manifest['requests_by_condition'][condition][pos]
        row = {'id': item['id'], 'status': status, 'request_sha256': item['request_sha256'],
            'attempt_id': f'{prefix}-{item["id"]}', 'observed_cost_usd': cost,
            'cost_unknown': cost is None,
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20},
            'client_http_duration_seconds': 0.2}
        if status == 'ok':
            row['prediction'] = self.prediction
        if cost is None:
            row['unknown_upper_bound_usd'] = str(report.admission.RESERVE)
        return row

    def evidence(self, index):
        def group(stage):
            result = {}
            for part in ('claim', 'journal', 'raw', 'records', 'review'):
                suffix = '.root-review.json' if part == 'review' else \
                    ('.claim.json' if part == 'claim' else f'.{part}.jsonl')
                relative = report.NEW / f'phase-{index + 1:02d}-{stage}{suffix}'
                if part == 'review':
                    path = self.root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{}\n')
                    digest = report.sha(path)
                else:
                    digest = 'a' * 64
                result[part] = {'path': str(relative), 'sha256': digest}
            return result
        return group('suffix') if index == 2 else {
            'smoke': group('smoke'), 'development': group('development')}

    def settle(self, rows):
        for row in rows:
            self.budget.extend(({'event': 'reserve', 'attempt_id': row['attempt_id'],
                'record_id': row['id'], 'usd': str(report.admission.RESERVE)},
                {'event': 'settle', 'attempt_id': row['attempt_id'],
                 'usd': row['observed_cost_usd']}))

    def write(self, index, value):
        path = self.root / report.snapshot_path(index)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) + '\n')
        return path

    def core(self, index):
        return {'schema': report.SNAPSHOT_SCHEMA, 'status': 'closed',
            'phase_index': index, 'manifest_sha256': report.MANIFEST_SHA,
            'partition_id': self.manifest['partition_id'],
            'budget_cap_usd': self.manifest['child_cap_usd'],
            'source_bindings': self.manifest['source_bindings'],
            'budget_prefix_source_sha256': 'b' * 64,
            'evidence': self.evidence(index)}

    def close_suffix(self):
        self.budget = [{'event': 'budget', 'cap_usd': self.manifest['child_cap_usd']}]
        rows = [self.row('P2', i, prefix='old') for i in range(40)]
        rows[38] = self.row('P2', 38, status='invalid_output', cost='0.0003083', prefix='old')
        rows[39] = self.row('P2', 39, status='service_error', cost=None, prefix='old')
        rows[39]['http_status'] = 429
        suffix = [self.row('P2', i) for i in range(40, 60)]
        rows.extend(suffix)
        self.settle(suffix)
        data = self.core(2)
        data.update(status='closed_with_service_error', positions=rows,
            status_counts={'ok': 58, 'invalid_output': 1,
            'service_error': 1}, old_known_actual_usd=self.manifest['old_known_actual_usd'],
            old_unknown_charge_upper_bound_usd=self.manifest['old_unknown_charge_upper_bound_usd'],
            budget_rows=suffix, budget_events=copy.deepcopy(self.budget),
            source_event_count=len(self.budget),
            new_known_actual_usd='0.0020', new_unknown_charge_upper_bound_usd='0')
        return self.write(2, data)

    def stop_suffix_at_049(self):
        self.budget = [{'event': 'budget', 'cap_usd': self.manifest['child_cap_usd']}]
        old = [self.row('P2', i, prefix='old') for i in range(40)]
        old[38] = self.row('P2', 38, status='invalid_output', cost='0.0003083', prefix='old')
        old[39] = self.row('P2', 39, status='service_error', cost=None, prefix='old')
        old[39]['http_status'] = 429
        new = [self.row('P2', i) for i in range(40, 49)]
        new[-1] = self.row('P2', 48, status='service_error', cost=None)
        new[-1]['http_status'] = 429
        new[-1]['evidence_sha256'] = 'a' * 64
        self.settle(new[:-1])
        self.budget.extend(({'event': 'reserve', 'attempt_id': new[-1]['attempt_id'],
            'record_id': 'DEV-049', 'usd': str(report.admission.RESERVE)},
            {'event': 'unknown_cost_accounted_as_upper_bound',
             'attempt_id': new[-1]['attempt_id'], 'usd': str(report.admission.RESERVE),
             'actual_cost_usd': None, 'evidence_sha256': 'a' * 64}))
        positions = old + [{key: value for key, value in row.items() if key != 'evidence_sha256'}
                           for row in new]
        positions.extend({'id': f'DEV-{i:03d}', 'status': 'never_sent'} for i in range(50, 61))
        data = self.core(2)
        data.update(status='stopped', positions=positions,
            status_counts={'ok': 46, 'invalid_output': 1, 'service_error': 2,
                           'never_sent': 11},
            old_known_actual_usd=self.manifest['old_known_actual_usd'],
            old_unknown_charge_upper_bound_usd=self.manifest['old_unknown_charge_upper_bound_usd'],
            budget_rows=new, budget_events=copy.deepcopy(self.budget),
            source_event_count=len(self.budget),
            new_known_actual_usd='0.0008',
            new_unknown_charge_upper_bound_usd=str(report.admission.RESERVE),
            new_pending_unknown_reserve_usd='0',
            attempted_count=49, never_sent_count=11,
            sealed_child={'partition_id': self.manifest['partition_id'],
                'child_sha256': 'c' * 64, 'reconciliation_sha256': 'd' * 64,
                'known_actual_usd': '0.0008',
                'unknown_upper_bound_usd': str(report.admission.RESERVE),
                'unused_allocation_released_usd': '0.0322944'})
        return self.write(2, data)

    def close_later(self, index):
        condition = self.manifest['phases'][index]['condition']
        smoke = [self.row(condition, i, prefix=f'{index}-smoke') for i in range(3)]
        development = [self.row(condition, i, prefix=f'{index}-dev') for i in range(60)]
        self.settle(smoke)
        self.settle(development)
        data = self.core(index)
        data.update(smoke=smoke, development=development,
            budget_events=copy.deepcopy(self.budget),
            source_event_count=len(self.budget),
            new_known_actual_usd=str(sum(
                (report.Decimal(event['usd']) for event in self.budget
                 if event['event'] == 'settle'), report.Decimal(0))),
            new_unknown_charge_upper_bound_usd='0')
        return self.write(index, data)


class DeepSeekLowPublicReportTests(unittest.TestCase):
    def setUp(self):
        self.fx = PublicFixture(self)

    def test_current_partial_checkpoint_is_not_a_score_or_live_suffix_count(self):
        result = report.build(self.fx.root)
        series = result['series'][0]
        self.assertEqual(report.SERIES, series['seriesId'])
        self.assertFalse(series['cleanMatchedThreeEligible'])
        self.assertEqual(2, series['completedConditions'])
        self.assertNotIn('P2', series['passes']['fresh1'])
        self.assertEqual('terminal_suffix_snapshot_pending', series['continuationStatus'])
        self.assertEqual(20, series['originalInterruptionCheckpoint']['neverSentAtInterruption'])
        self.assertEqual('DEV-039', series['originalInterruptionCheckpoint']['invalidId'])
        self.assertEqual('DEV-040', series['originalInterruptionCheckpoint']['serviceErrorId'])
        self.assertNotIn('raw_error_response', json.dumps(result))
        self.assertNotIn('user_id', json.dumps(result))

    def test_closed_suffix_scores_fixed_sixty_and_keeps_both_failures(self):
        self.fx.close_suffix()
        result = report.build(self.fx.root)
        series = result['series'][0]
        first = series['passes']['fresh1']['P2']
        self.assertEqual(60, first['score']['denominator'])
        self.assertEqual(58, first['score']['valid'])
        self.assertEqual(['DEV-039', 'DEV-040'], first['score']['invalidIds'])
        self.assertEqual('0.1069056', first['usage']['unknownChargeUpperBoundUsd'])
        self.assertEqual('0.0020', series['budgetAccountingCumulative']['newKnownAllAttemptCostUsd'])
        self.assertEqual(3, series['completedConditions'])
        self.assertEqual(6, len(series['missingPasses']))

    def test_terminal_dev049_is_visible_but_never_partially_scored(self):
        self.fx.stop_suffix_at_049()
        series = report.build(self.fx.root)['series'][0]
        self.assertEqual(2, series['completedConditions'])
        self.assertNotIn('P2', series['passes']['fresh1'])
        self.assertEqual('suffix_stopped_at_DEV-049_unscored', series['continuationStatus'])
        second = series['secondInterruptionCheckpoint']
        self.assertEqual(49, second['attemptedAtSecondInterruption'])
        self.assertEqual(11, second['neverSentAtSecondInterruption'])
        self.assertEqual(['DEV-040', 'DEV-049'], second['serviceErrorIds'])
        self.assertIsNone(second['score'])
        self.assertEqual('0.2138112', series['budgetAccountingCumulative'][
            'combinedUnknownChargeUpperBoundUsd'])
        self.assertEqual('stopped_at_DEV-049_unscored', series['missingPasses'][0]['status'])

    def test_dev049_requires_finalized_unknown_and_seal(self):
        path = self.fx.stop_suffix_at_049()
        data = json.loads(path.read_text())
        data['new_pending_unknown_reserve_usd'] = str(report.admission.RESERVE)
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'terminal disposition'):
            report.build(self.fx.root)
        self.fx.stop_suffix_at_049()
        data = json.loads(path.read_text())
        data['sealed_child'] = None
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'terminal disposition'):
            report.build(self.fx.root)

    def test_dev049_sealed_release_must_equal_prefix_arithmetic(self):
        path = self.fx.stop_suffix_at_049()
        data = json.loads(path.read_text())
        data['sealed_child']['unused_allocation_released_usd'] = '0.04'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Sealed child money'):
            report.build(self.fx.root)
        self.fx.stop_suffix_at_049()
        data = json.loads(path.read_text())
        data['sealed_child']['known_actual_usd'] = '0.0009'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'Sealed child money'):
            report.build(self.fx.root)

    def test_later_closed_phase_extends_exact_child_prefix(self):
        self.fx.close_suffix()
        self.fx.close_later(3)
        series = report.build(self.fx.root)['series'][0]
        self.assertEqual(4, series['completedConditions'])
        self.assertEqual(60, series['passes']['fresh2'][
            self.fx.manifest['phases'][3]['condition']]['score']['denominator'])
        self.assertEqual(57, series['withinPassPromptFlips'][1]['denominator'])

    def test_tampered_snapshot_and_budget_fail_closed(self):
        path = self.fx.close_suffix()
        data = json.loads(path.read_text())
        data['positions'][39]['status'] = 'ok'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            report.build(self.fx.root)
        self.fx.close_suffix()
        data = json.loads(path.read_text())
        data['budget_events'][-1]['usd'] = '0.9'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'budget settlement'):
            report.build(self.fx.root)

    def test_snapshot_source_hash_and_prefix_attestation_are_required(self):
        path = self.fx.close_suffix()
        data = json.loads(path.read_text())
        data['source_bindings']['failed_records']['sha256'] = '0' * 64
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'snapshot differs'):
            report.build(self.fx.root)
        self.fx.close_suffix()
        data = json.loads(path.read_text())
        data['budget_prefix_source_sha256'] = 'not-a-hash'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'snapshot differs'):
            report.build(self.fx.root)

    def test_public_snapshot_rejects_raw_payload_and_unreported_successor(self):
        path = self.fx.close_suffix()
        data = json.loads(path.read_text())
        data['positions'][0]['raw_error_response'] = {'user_id': 'private'}
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'fields differ'):
            report.build(self.fx.root)
        path.unlink()
        self.fx.close_later(3)
        with self.assertRaisesRegex(ValueError, 'unreported predecessor'):
            report.build(self.fx.root)

    def test_source_manifest_sha_is_pinned(self):
        manifest = REPO / report.NEW / 'manifest.json'
        self.assertEqual(report.MANIFEST_SHA, report.sha(manifest))

    def test_capture_refuses_nonterminal_suffix_without_export(self):
        with patch.object(report.runner, 'validate_manifest', return_value=self.fx.manifest), \
             patch.object(report.runner, 'reconcile_suffix', return_value={'status': 'admission_stopped'}), \
             patch.object(report, 'ROOT', self.fx.root):
            with self.assertRaisesRegex(ValueError, 'not terminally stopped or closed'):
                report.capture(self.fx.root, 2)
        self.assertFalse((self.fx.root / report.snapshot_path(2)).exists())

    def test_immutable_public_export_rejects_private_field(self):
        path = self.fx.root / report.snapshot_path(2)
        with self.assertRaisesRegex(ValueError, 'Private provider field'):
            report._write_immutable(path, {'user_id': 'private-account'})
        self.assertFalse(path.exists())

    def test_clean_public_checkout_needs_no_private_dev040_record(self):
        self.fx.source.stop()
        _, _, _, _, _, bindings, _ = report.source_context(REPO)
        paths = {item['path'] for item in bindings}
        paths.add(str(report.NEW / 'manifest.json'))
        for relative in paths:
            source = REPO / relative
            target = self.fx.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.assertFalse((self.fx.root / report.BASE /
            'phase-03-development.records.jsonl').exists())
        self.assertFalse((self.fx.root / report.BASE /
            'phase-03-development.raw.jsonl').exists())
        result = report.build(self.fx.root)
        self.assertEqual(2, result['series'][0]['completedConditions'])
        self.assertNotIn('P2', result['series'][0]['passes']['fresh1'])

    def test_real_dev049_snapshot_rebuilds_without_private_provider_bytes(self):
        self.fx.source.stop()
        _, _, _, _, _, bindings, _ = report.source_context(REPO)
        paths = {item['path'] for item in bindings}
        paths.update((str(report.NEW / 'manifest.json'), str(report.snapshot_path(2))))
        snapshot = json.loads((REPO / report.snapshot_path(2)).read_text())
        paths.add(snapshot['evidence']['review']['path'])
        for relative in paths:
            source = REPO / relative
            target = self.fx.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for kind in ('raw', 'records'):
            self.assertFalse((self.fx.root / report.BASE /
                f'phase-03-development.{kind}.jsonl').exists())
            self.assertFalse((self.fx.root / report.NEW /
                f'phase-03-suffix.{kind}.jsonl').exists())
        series = report.build(self.fx.root)['series'][0]
        self.assertEqual('suffix_stopped_at_DEV-049_unscored', series['continuationStatus'])
        self.assertEqual(2, series['completedConditions'])


if __name__ == '__main__':
    unittest.main()
