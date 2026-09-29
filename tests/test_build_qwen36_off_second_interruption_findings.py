"""Portable second-interruption findings; no inference or production prefix writes."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import build_qwen36_off_second_interruption_findings as report
import build_qwen36_off_continuation_findings as prior
from tests.test_additional_hosted_fresh_repeat_findings import copy_public_provider_error_bundle
from export_provider_error_public_evidence import INVENTORY as ACCOUNT_ID_SOURCES


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(value) + '\n' for value in values))


class PortableFixture(unittest.TestCase):
    def setUp(self):
        source = report.build(REPO)
        if source['series'][0]['completedConditions'] < 6:
            self.skipTest('Six public predecessor phases are not closed')
        self.temp = tempfile.TemporaryDirectory(dir=REPO)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        copy_public_provider_error_bundle(self.root)
        for item in source['sourceBindings']:
            relative = Path(item['path'])
            if relative.is_absolute():
                raise AssertionError('Nonportable source binding')
            if relative.name.endswith('budget-prefix.json') and report.NEW in relative.parents:
                continue
            if report.NEW in relative.parents and relative.name.startswith(('phase-08-', 'phase-09-')):
                continue
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, path)
        self.manifest = json.loads((self.root / report.NEW / 'manifest.json').read_text())
        self.projection = json.loads((self.root / report.projection_path()).read_text())
        # A portable test child: copy only the 29 settled suffix charges, then
        # append synthetic later stages. It cannot affect the production ledger.
        self.ledger = self.root / report.NEW / (
            'budget-' + self.manifest['partition_id'] + '.jsonl')
        events = [{'event': 'budget', 'cap_usd': '0.06'}]
        for i, row in enumerate(self.projection['positions'][31:]):
            attempt = f'suffix-test-{i}'
            events += [{'event': 'reserve', 'attempt_id': attempt,
                        'record_id': row['id'], 'usd': str(report.admission.RESERVE)},
                       {'event': 'settle', 'attempt_id': attempt,
                        'usd': row['observed_cost_usd']}]
        write_rows(self.ledger, events)

    def stage(self, index, name):
        manifest = self.manifest
        phase = manifest['phases'][index]
        selected = manifest['requests_by_condition'][phase['condition']]
        if name == 'smoke':
            selected = selected[:3]
        stem = self.root / report.NEW / f'phase-{index + 1:02d}-{name}'
        paths = {key: Path(str(stem) + suffix) for key, suffix in
            (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
             ('raw', '.raw.jsonl'), ('records', '.records.jsonl'),
             ('review', '.root-review.json'))}
        review = {'schema': 'qwen36-off-v2-second-interruption-v1-stage-review',
            'approved': True, 'manifest_sha256': report.MANIFEST_SHA,
            'controller_sha256': manifest['controller']['sha256'],
            'old_child_ledger_sha256': manifest['sources']['old_child_ledger']['sha256'],
            'old_terminal_reconciliation_sha256': manifest['sources']['old_terminal_reconciliation']['sha256'],
            'new_budget_manifest_sha256': report.BUDGET_SHA,
            'partition_id': manifest['partition_id'], 'phase_index': index,
            'stage': name, 'ids': [item['id'] for item in selected]}
        if name == 'development':
            smoke = self.root / report.NEW / f'phase-{index + 1:02d}-smoke'
            review['smoke_inspection'] = {'approved': True, 'statuses': ['ok'] * 3,
                **{'smoke_' + key + '_sha256': report.sha(Path(str(smoke) + '.' + key + '.jsonl'))
                   for key in ('records', 'journal', 'raw')}}
        write_json(paths['review'], review)
        claim = {'schema': 'affordable-hosted-stage-claim-v1',
            'manifest_sha256': report.MANIFEST_SHA,
            'review_sha256': report.sha(paths['review']),
            'budget_manifest_sha256': report.BUDGET_SHA,
            'partition_id': manifest['partition_id'], 'phase_index': index,
            'repeat': phase['repeat'], 'condition': phase['condition'],
            'stage': name, 'ids': [item['id'] for item in selected]}
        write_json(paths['claim'], claim)
        journal = [{'event': 'stage_claimed', 'claim_sha256': report.sha(paths['claim'])}]
        raw, records = [], []
        ledger = [json.loads(line) for line in self.ledger.read_text().splitlines()]
        for i, item in enumerate(selected):
            rid = item['id']; attempt = f'phase-{index}-{name}-{i}'
            prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                          'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
            body = {'model': report.admission.MODEL, 'provider': 'AkashML',
                'usage': {'cost': '0.0001', 'prompt_tokens': 10,
                          'completion_tokens': 5, 'total_tokens': 15},
                'choices': [{'message': {'content': json.dumps(prediction)},
                             'finish_reason': 'stop'}]}
            raw.append({'attempt_id': attempt, 'id': rid, 'body': body})
            row = {'id': rid, 'repeat': phase['repeat'], 'condition': phase['condition'],
                'phase': name, 'attempt_id': attempt, 'request': item['payload'],
                'request_sha256': item['request_sha256'],
                'input_sha256': item['input_sha256'],
                'policy_sha256': item['instruction_sha256'],
                'requested_model': report.admission.MODEL,
                'provider_endpoint': {'tag': report.admission.PROVIDER,
                    'provider_name': 'AkashML', 'quantization': 'fp8'},
                'reference_labels_read': False, 'reserved_cost_usd': str(report.admission.RESERVE),
                'budget_partition_id': manifest['partition_id'],
                'reasoning_effort': 'off', 'continue_on_invalid_output': False,
                'retry_policy': 'none', 'client_request_started_utc': '2026-09-29T00:00:00+00:00',
                'client_request_finished_utc': '2026-09-29T00:00:01+00:00',
                'client_http_duration_seconds': 0.3, 'raw_response': body,
                'usage': body['usage'], 'prediction': prediction,
                'returned_model': report.admission.MODEL,
                'returned_provider': 'AkashML', 'finish_reason': 'stop',
                'status': 'ok', 'observed_cost_usd': '0.0001',
                'cost_unknown': False, 'billing_ok': True}
            records.append(row)
            journal.extend(({'event': 'request_started', 'attempt_id': attempt,
                'id': rid, 'request_sha256': item['request_sha256'],
                'reserved_cost_usd': str(report.admission.RESERVE)},
                {'event': 'raw_saved', 'attempt_id': attempt, 'raw_sha256': ''},
                {'event': 'request_finished', 'attempt_id': attempt,
                 'id': rid, 'status': 'ok', 'billing_ok': True}))
            ledger += [{'event': 'reserve', 'attempt_id': attempt, 'record_id': rid,
                        'usd': str(report.admission.RESERVE)},
                       {'event': 'settle', 'attempt_id': attempt, 'usd': '0.0001'}]
        write_rows(paths['raw'], raw); write_rows(paths['records'], records)
        lines = paths['raw'].read_bytes().splitlines(keepends=True)
        for i in range(len(selected)):
            journal[2 + 3 * i]['raw_sha256'] = hashlib.sha256(b''.join(lines[:i + 1])).hexdigest()
        journal.append({'event': 'stage_completed', 'count': len(selected)})
        write_rows(paths['journal'], journal)
        write_rows(self.ledger, ledger)
        return paths


class SecondReporterTests(PortableFixture):
    def test_relocated_checkout_excludes_private_original_error(self):
        for relative, _, _ in ACCOUNT_ID_SOURCES:
            (self.root / relative).unlink(missing_ok=True)
        for name in ('raw', 'records'):
            self.assertFalse((self.root / prior.LATER /
                f'phase-07-development.{name}.jsonl').exists())
        result = report.build(self.root)
        series = result['series'][0]
        self.assertEqual(6, series['completedConditions'])
        self.assertEqual('budget_prefix_absent', series['missingPasses'][0]['status'])
        self.assertEqual(report.METHOD, series['method'])
        self.assertEqual('0.0598016', series['secondInterruption']['oldUnknownChargeUpperBoundUsd'])
        self.assertEqual([('DEV-006', 'service_error', '0.0299008'),
                          ('DEV-031', 'service_error', '0.0299008')],
            [(item['id'], item['status'], item['upperBoundUsd']) for item in
             series['secondInterruption']['retainedOldUnknownBounds']])
        self.assertNotIn('raw_error_response', json.dumps(result))

    def test_suffix_prefix_scores_fixed_sixty_and_retains_both_unknown_bounds(self):
        prefix = report.capture_prefix(self.root, 6)
        self.assertTrue(prefix.exists())
        result = report.build(self.root)
        series = result['series'][0]
        self.assertEqual(7, series['completedConditions'])
        p1 = series['passes']['fresh3']['P1']
        self.assertEqual('closed_with_service_error', p1['status'])
        self.assertEqual(60, p1['score']['denominator'])
        self.assertEqual(59, p1['score']['valid'])
        self.assertEqual(['DEV-031'], p1['score']['invalidIds'])
        self.assertEqual('0.0598016', p1['budgetAccountingCumulative']['combinedUnknownChargeUpperBoundUsd'])
        p1_flips = [item for item in series['pairwiseFlips'] if
                    item['condition'] == 'P1' and item['to'] == 'fresh3']
        self.assertTrue(p1_flips)
        self.assertTrue(all(item['denominator'] == 59 for item in p1_flips))
        self.assertNotIn('evidence_path', prefix.read_text())

    def test_two_later_phases_strict_and_budget_prefixes(self):
        report.capture_prefix(self.root, 6)
        self.stage(7, 'smoke'); self.stage(7, 'development')
        report.capture_prefix(self.root, 7)
        partial = report.build(self.root)['series'][0]
        self.assertEqual(8, partial['completedConditions'])
        self.stage(8, 'smoke'); self.stage(8, 'development')
        report.capture_prefix(self.root, 8)
        complete = report.build(self.root)['series'][0]
        self.assertEqual(9, complete['completedConditions'])
        self.assertEqual([], complete['missingPasses'])
        self.assertFalse(complete['cleanMatchedThreeEligible'])
        self.assertEqual('0.0598016', complete['passes']['fresh3']['P0']
                         ['budgetAccountingCumulative']['combinedUnknownChargeUpperBoundUsd'])

    def test_projection_and_budget_tamper_are_rejected(self):
        projection_path = self.root / report.projection_path()
        data = json.loads(projection_path.read_text())
        data['positions'][30]['status'] = 'ok'
        write_json(projection_path, data)
        with self.assertRaisesRegex(ValueError, 'Source hash changed|not closed 59/60|position differs'):
            report.build(self.root)
        shutil.copy2(REPO / report.projection_path(), projection_path)
        prefix = report.capture_prefix(self.root, 6)
        payload = json.loads(prefix.read_text())
        payload['events'][-1]['usd'] = '0.9'
        write_json(prefix, payload)
        with self.assertRaisesRegex(ValueError, 'settlement differs'):
            report.build(self.root)

    def test_closed_stage_without_prefix_unscored_and_invalid_stage_rejected(self):
        report.capture_prefix(self.root, 6)
        self.stage(7, 'smoke'); development = self.stage(7, 'development')
        series = report.build(self.root)['series'][0]
        self.assertEqual(7, series['completedConditions'])
        self.assertEqual('budget_prefix_absent_or_prior_unreported',
                         series['missingPasses'][0]['status'])
        report.capture_prefix(self.root, 7)
        raw = development['raw']
        raw.write_text(raw.read_text().replace('neutral', 'positive', 1))
        with self.assertRaisesRegex(ValueError, 'strict runner verification'):
            report.build(self.root)


if __name__ == '__main__':
    unittest.main()
