"""Offline checks for source-bound hosted repeat findings."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_hosted_repeat_findings as hosted


class HostedRepeatFindingsTest(unittest.TestCase):
    def test_saved_sources_are_separate_and_only_closed_phases_score(self):
        real_repeat_phase = hosted._repeat_phase
        def missing_repeat3(root, repeat, condition, plan, review_sha, ids, labels, bind):
            if repeat == 'repeat3':
                return None, 'fixture_missing_repeat3'
            return real_repeat_phase(root, repeat, condition, plan, review_sha, ids, labels, bind)
        with patch.object(hosted, '_repeat_phase', side_effect=missing_repeat3):
            report = hosted.build()
        self.assertEqual(report['configuration'], hosted.CONFIG)
        self.assertEqual(report['denominator'], 60)
        self.assertEqual(set(report['passes']['original']), {'P0', 'P1', 'P2'})
        self.assertEqual(report['passes']['repeat2']['P2']['score']['allFour'], 51)
        self.assertEqual(report['passes']['repeat2']['P2']['usage']['actualCostUsd'], '0.01154420')
        self.assertEqual(report['passes']['repeat2']['P1']['usage']['actualCostUsd'], '0.00762006')
        self.assertEqual(report['passes']['repeat2']['P2']['score']['denominator'], 60)
        self.assertEqual(report['threePassSummary']['P2']['allFour']['completedPasses'], 2)
        self.assertIsNone(report['threePassSummary']['P2']['allFour']['range'])
        self.assertFalse(any(x['from'] == 'repeat3' or x['to'] == 'repeat3' for x in report['pairwiseFlips']))
        self.assertIn({'pass': 'repeat3', 'condition': 'P2', 'status': 'fixture_missing_repeat3'},
                      report['missingPasses'])
        self.assertTrue(any(x['path'].endswith('root-review-v1.json') for x in report['sourceBindings']))

    def test_source_context_accepts_relocated_checkout_with_same_hashes(self):
        _, _, _, _, _, _, sources = hosted._source_context(ROOT)
        relocated = self.root / 'relocated'
        for item in sources:
            destination = relocated / item['path']
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / item['path'], destination)
        _, _, _, _, _, _, copied_sources = hosted._source_context(relocated)
        self.assertEqual(copied_sources, sources)

    def test_cli_check_and_explicit_output_update(self):
        output = self.root / 'findings.json'
        fixture = {'schema': 'synthetic-test-report', 'configuration': 'fixture',
                   'completedConditions': 3, 'partialPasses': [], 'values': [1, 2, 3]}
        with patch.object(hosted, 'build', return_value=fixture):
            with self.assertRaisesRegex(ValueError, 'Stale report'):
                hosted.main(['--output', str(output), '--check'])
            hosted.main(['--output', str(output)])
            original = output.read_bytes()
            hosted.main(['--output', str(output), '--check'])
            self.assertEqual(output.read_bytes(), original)
            output.write_text('stale\n')
            with self.assertRaisesRegex(ValueError, 'Stale report'):
                hosted.main(['--output', str(output), '--check'])
            hosted.main(['--output', str(output)])
            self.assertEqual(output.read_bytes(), original)

    def test_synthetic_complete_third_pass_populates_ranges_and_flips(self):
        # The third pass exists only in memory for this aggregation test. No
        # saved repeat3 evidence is created or presented as an observed run.
        real_rows = hosted._rows
        real_phase = hosted._repeat_phase
        fixture_rows = {}
        for condition in hosted.CONDITIONS:
            source = hosted.BASE / 'repeat2' / condition / 'development.attempts.jsonl'
            fixture_rows[condition] = copy.deepcopy(real_rows(ROOT, source))
        first = fixture_rows['P2'][0]['prediction']
        alternate = next(row['prediction']['sentiment'] for row in fixture_rows['P2']
                         if row['prediction']['sentiment'] != first['sentiment'])
        first['sentiment'] = alternate

        def synthetic_rows(root, relative):
            parts = Path(relative).parts
            if 'repeat3' in parts and Path(relative).name == 'development.attempts.jsonl':
                return copy.deepcopy(fixture_rows[parts[-2]])
            return real_rows(root, relative)

        def synthetic_phase(root, repeat, condition, plan, review_sha, ids, labels, bind):
            if repeat != 'repeat3':
                return real_phase(root, repeat, condition, plan, review_sha, ids, labels, bind)
            rows = fixture_rows[condition]
            score = hosted.shared.score({row['id']: row for row in rows}, labels, ids)
            return {'completionStatus': 'complete', 'terminalEvent': 'synthetic_fixture',
                    'finishedRequests': len(rows), 'score': score,
                    'usage': {}, 'evidence': {'fixture': 'in-memory-only'}}, None

        with patch.object(hosted, '_repeat_phase', side_effect=synthetic_phase), \
                patch.object(hosted, '_rows', side_effect=synthetic_rows):
            report = hosted.build()
        p2 = report['threePassSummary']['P2']['allFour']
        self.assertEqual(p2['completedPasses'], 3)
        self.assertEqual(len(p2['values']), 3)
        self.assertEqual(p2['range'], [min(p2['values']), max(p2['values'])])
        flip = next(item for item in report['pairwiseFlips']
                    if item['condition'] == 'P2' and item['from'] == 'repeat2'
                    and item['to'] == 'repeat3')
        self.assertEqual(flip['sentiment']['caseIds'], [fixture_rows['P2'][0]['id']])
        self.assertEqual(flip['fourFieldVector']['changed'], 1)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repeat = 'repeat2'
        self.condition = 'P2'
        self.folder = self.root / hosted.BASE / self.repeat / self.condition
        self.folder.mkdir(parents=True)
        self.plan = json.loads((ROOT / hosted.BASE / self.repeat / 'manifest.json').read_text())
        manifest = self.root / hosted.BASE / self.repeat / 'manifest.json'
        manifest.write_text(json.dumps(self.plan) + '\n')
        self.manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        self.ids = [f'DEV-{i:03}' for i in range(1, 61)]
        labels = [json.loads(x) for x in (ROOT / hosted.LABELS).read_text().splitlines()]
        self.labels = {row['id']: row['proposed_labels'] for row in labels}
        pair = json.loads((ROOT / hosted.PAIR).read_text())
        historical = Path(pair['conditions'][self.condition]['request_evidence']['file'])
        self.source_rows = [json.loads(x) for x in (ROOT / historical).read_text().splitlines()]
        self.bind = lambda path, expected=None: hosted._binding(self.root, path, expected)

    def _row(self, index, status='ok'):
        planned = self.plan['conditions'][self.condition]['development'][index]
        row = copy.deepcopy(self.source_rows[index])
        row.update(id=planned['record_id'], request=planned['payload'],
                   request_sha256=planned['request_sha256'], repeat=self.repeat,
                   condition=self.condition, phase='development',
                   manifest_sha256=self.manifest_sha, attempt_id=f'attempt-{index + 1}',
                   status=status, observed_cost_usd='0.01', elapsed_seconds=2.0,
                   cost_unknown=False, billing_ok=True)
        row['response_diagnostic'] = {'passed': True, 'blockers': []}
        row['raw_response']['usage']['cost'] = 0.01
        row['usage'] = copy.deepcopy(row['raw_response']['usage'])
        if status != 'ok':
            row['prediction'] = None
        return row

    def _write_phase(self, rows, terminal='phase_stopped', dangling=False):
        (self.folder / 'development.claim.json').write_text(json.dumps({
            'repeat': self.repeat, 'condition': self.condition, 'phase': 'development',
            'manifest_sha256': self.manifest_sha, 'root_review_sha256': 'review-hash'}))
        events = [{'event': 'phase_started', 'repeat': self.repeat,
                   'condition': self.condition, 'phase': 'development'}]
        for row in rows:
            identity = {'id': row['id'], 'request_sha256': row['request_sha256']}
            events.append({'event': 'request_intent', **identity})
            events.append({'event': 'request_started', **identity,
                           'attempt_id': row['attempt_id']})
            events.append({'event': 'request_finished', 'id': row['id'],
                           'attempt_id': row['attempt_id'], 'status': row['status'],
                           'billing_ok': row['billing_ok'], 'cost_unknown': row['cost_unknown']})
        if dangling:
            planned = self.plan['conditions'][self.condition]['development'][len(rows)]
            identity = {'id': planned['record_id'], 'request_sha256': planned['request_sha256']}
            events.append({'event': 'request_intent', **identity})
            events.append({'event': 'request_started', **identity,
                           'attempt_id': 'pending-attempt'})
        events.append({'event': terminal, 'id': rows[-1]['id'] if rows else None,
                       'reason': rows[-1]['status'] if rows else None,
                       'repeat': self.repeat, 'condition': self.condition, 'phase': 'development',
                       'request_count': len(rows)})
        (self.folder / 'development.journal.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in events))
        (self.folder / 'development.attempts.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
        (self.folder / 'development.responses.jsonl').write_text(''.join(json.dumps({
            'id': row['id'], 'attempt_id': row['attempt_id'],
            'request_sha256': row['request_sha256'], 'raw_response': row['raw_response']}) + '\n'
            for row in rows if 'raw_response' in row))

    def _phase(self):
        with patch.object(hosted, '_smoke_binding', return_value={}):
            return hosted._repeat_phase(self.root, self.repeat, self.condition,
                                        self.plan, 'review-hash', self.ids,
                                        self.labels, self.bind)

    def test_stopped_phase_retains_invalid_and_never_sent_in_sixty(self):
        rows = [self._row(0), self._row(1, 'invalid_output')]
        rows[1]['elapsed_seconds'] = None
        self._write_phase(rows)
        entry, why = self._phase()
        self.assertIsNone(why)
        self.assertEqual(entry['completionStatus'], 'partial')
        self.assertEqual(entry['score']['denominator'], 60)
        self.assertEqual(entry['score']['outcomes']['valid'], 1)
        self.assertEqual(entry['score']['outcomes']['invalid_output'], 1)
        self.assertEqual(entry['score']['outcomes']['never_sent'], 58)
        self.assertEqual(entry['usage']['actualCostUsd'], '0.02')
        self.assertIsNone(entry['usage']['requestSecondsTotal'])

    def test_nested_token_totals_use_raw_usage_and_unknown_stays_null(self):
        first = self._row(0)
        usage = first['raw_response']['usage']
        usage['prompt_tokens_details']['cached_tokens'] = 7
        usage['prompt_tokens_details']['cache_write_tokens'] = 3
        usage['completion_tokens_details']['reasoning_tokens'] = 5
        first['usage'] = copy.deepcopy(usage)
        self._write_phase([first])
        entry, _ = self._phase()
        self.assertEqual(entry['usage']['tokens']['cached_input_tokens'], 7)
        self.assertEqual(entry['usage']['tokens']['cache_write_input_tokens'], 3)
        self.assertEqual(entry['usage']['tokens']['reasoning_output_tokens'], 5)

        second = self._row(1)
        second['raw_response']['usage']['completion_tokens_details'].pop('reasoning_tokens')
        second['usage'] = copy.deepcopy(second['raw_response']['usage'])
        self._write_phase([first, second])
        entry, _ = self._phase()
        self.assertIsNone(entry['usage']['tokens']['reasoning_output_tokens'])
        self.assertEqual(entry['usage']['tokens']['cached_input_tokens'],
                         7 + second['usage']['prompt_tokens_details']['cached_tokens'])

    def test_aborted_started_attempt_stays_unknown_and_cost_is_not_zero(self):
        row = self._row(0, 'service_error')
        row['raw_response'] = ['malformed', 'provider', 'body']
        row['usage'] = None
        row.pop('returned_model', None)
        row.pop('returned_provider', None)
        row['cost_unknown'] = True
        row['observed_cost_usd'] = None
        row['billing_ok'] = False
        self._write_phase([row], terminal='phase_aborted', dangling=True)
        entry, _ = self._phase()
        self.assertEqual(entry['completionStatus'], 'partial')
        self.assertEqual(entry['score']['outcomes']['service_error'], 1)
        self.assertEqual(entry['score']['outcomes']['unknown_started'], 1)
        self.assertEqual(entry['score']['outcomes']['never_sent'], 58)
        self.assertEqual(entry['usage']['unknownCostCount'], 2)
        self.assertIsNone(entry['usage']['actualCostUsd'])

    def test_preclassification_service_error_keeps_raw_usage_without_invented_cost(self):
        row = self._row(0, 'service_error')
        row['cost_unknown'] = True
        row['observed_cost_usd'] = None
        row['billing_ok'] = False
        row['raw_response']['usage']['cost'] = 'malformed-provider-cost'
        row.pop('usage')  # Error occurred before the runner copied usage.
        self._write_phase([row], terminal='phase_aborted')
        entry, why = self._phase()
        self.assertIsNone(why)
        self.assertEqual(entry['usage']['unknownCostCount'], 1)
        self.assertIsNone(entry['usage']['actualCostUsd'])
        self.assertEqual(entry['usage']['tokens']['input_tokens'],
                         row['raw_response']['usage']['prompt_tokens'])
        self.assertEqual(entry['usage']['tokens']['reasoning_output_tokens'],
                         row['raw_response']['usage']['completion_tokens_details']['reasoning_tokens'])

        row['raw_response'].pop('usage')
        row['usage'] = {}  # Another pre-classification error shape.
        self._write_phase([row], terminal='phase_aborted')
        entry, _ = self._phase()
        self.assertIsNone(entry['usage']['tokens']['input_tokens'])
        self.assertIsNone(entry['usage']['tokens']['reasoning_output_tokens'])

    def test_open_partial_line_is_missing_but_malformed_terminal_rejects(self):
        journal = self.folder / 'development.journal.jsonl'
        journal.write_text('{"event":"phase_started"}\n{"event":"request_intent"')
        self.assertEqual(self._phase(), (None, 'open_no_terminal'))
        journal.write_text('{"event":"phase_started"}\n{"event":}\n')
        with self.assertRaises(json.JSONDecodeError):
            self._phase()

    def test_changed_payload_attempt_or_cost_cannot_score(self):
        row = self._row(0)
        cases = [
            ('hash', lambda value: value.update(request_sha256='0' * 64)),
            ('cost', lambda value: value.update(observed_cost_usd='0.02')),
            ('usage', lambda value: value['usage'].update(prompt_tokens=999999)),
            ('prediction', lambda value: value['prediction'].update(sentiment='negative')),
            ('identity', lambda value: value['raw_response'].update(provider='Elsewhere')),
        ]
        for name, mutation in cases:
            with self.subTest(name=name):
                changed = copy.deepcopy(row)
                mutation(changed)
                self._write_phase([changed])
                with self.assertRaises(ValueError):
                    self._phase()

    def test_duplicate_attempt_and_response_binding_fail(self):
        rows = [self._row(0), self._row(1, 'invalid_output')]
        rows[1]['attempt_id'] = rows[0]['attempt_id']
        self._write_phase(rows)
        with self.assertRaisesRegex(ValueError, 'reused'):
            self._phase()
        rows[1]['attempt_id'] = 'attempt-2'
        self._write_phase(rows)
        sidecar = self.folder / 'development.responses.jsonl'
        data = [json.loads(x) for x in sidecar.read_text().splitlines()]
        data[0]['request_sha256'] = 'f' * 64
        sidecar.write_text(''.join(json.dumps(x) + '\n' for x in data))
        with self.assertRaisesRegex(ValueError, 'sidecar request binding'):
            self._phase()

    def test_smoke_inspection_hash_is_required(self):
        saved = ROOT / hosted.BASE / 'repeat2' / 'P2'
        for name in ('smoke-inspection.json', 'smoke.journal.jsonl',
                     'smoke.attempts.jsonl', 'smoke.claim.json'):
            shutil.copyfile(saved / name, self.folder / name)
        actual_manifest = hosted._sha(ROOT / hosted.BASE / 'repeat2' / 'manifest.json')
        actual_review = hosted._sha(ROOT / hosted.REVIEW)
        hosted._smoke_binding(self.root, hosted.BASE / 'repeat2' / 'P2',
                              'repeat2', 'P2', self.plan, actual_manifest, actual_review,
                              self.bind)
        with (self.folder / 'smoke.attempts.jsonl').open('a') as output:
            output.write('{}\n')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            hosted._smoke_binding(self.root, hosted.BASE / 'repeat2' / 'P2',
                                  'repeat2', 'P2', self.plan, actual_manifest,
                                  actual_review, self.bind)


if __name__ == '__main__':
    unittest.main()
