"""Offline evidence checks for the three paid hosted wave series."""
import base64
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_hosted_wave_findings as report


class HostedWaveFindingsTest(unittest.TestCase):
    def test_qwen_series_uses_frozen_review_and_complete_phases(self):
        spec = report.qwen.SPEC
        series = report.build_series(spec)
        self.assertEqual(series['configuration'], spec.id)
        self.assertEqual(series['denominator'], 60)
        self.assertEqual(series['plannedConditions'], 9)
        self.assertEqual(series['passes']['original']['P0']['completionStatus'], 'complete')
        self.assertEqual(series['passes']['repeat2']['P2']['completionStatus'], 'complete')
        self.assertIn('responses', series['passes']['repeat2']['P2']['evidence'])
        self.assertEqual(series['completedConditions'] + len(series['partialPasses']) +
                         len(series['missingPasses']), 9)
        paths = {binding['path'] for binding in series['sourceBindings']}
        self.assertIn('scripts/openrouter_qwen27_repeat.py', paths)
        self.assertIn(report.qwen.PREFLIGHT, paths)

    def test_qwen_review_preflight_binding_survives_checkout_relocation(self):
        spec = report.qwen.SPEC
        base = Path('results/repeatability-v1') / spec.id
        paths = {report.LABELS, Path(spec.pair), report.HOSTED,
                 base / 'root-review-v1.json', base / 'budget-partition-v1.json',
                 base / 'public-route-preflight.json',
                 base / 'repeat2/manifest.json', base / 'repeat3/manifest.json'}
        for repeat in ('repeat2', 'repeat3'):
            plan = json.loads((ROOT / base / repeat / 'manifest.json').read_text())
            paths.update(Path(binding['path']) for binding in plan['source_bindings'])
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp)
            for relative in paths:
                target = clone / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            series = report.build_series(spec, clone)
            self.assertEqual(series['completedConditions'], 3)
            self.assertEqual(len(series['missingPasses']), 6)
            preflight = clone / report.qwen.PREFLIGHT
            preflight.write_text(preflight.read_text().replace('262144', '262143'))
            with self.assertRaisesRegex(ValueError, 'Source hash changed'):
                report.build_series(spec, clone)

    def test_qwen_partial_unknown_cost_keeps_sixty_positions(self):
        spec = report.qwen.SPEC
        base = Path('results/repeatability-v1') / spec.id
        folder = base / 'repeat2/P2'
        plan = json.loads((ROOT / base / 'repeat2/manifest.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in [base / 'repeat2/manifest.json',
                             *(folder / name for name in ('development.claim.json',
                                                          'development.journal.jsonl',
                                                          'development.attempts.jsonl',
                                                          'development.responses.jsonl'))]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            attempts_path = root / folder / 'development.attempts.jsonl'
            attempt = json.loads(attempts_path.read_text().splitlines()[0])
            attempt.pop('raw_response')
            attempt['status'] = 'service_error'
            attempt['error_body'] = '{"error":"limited"}'
            attempt['http_status'] = 429
            attempt['error_headers'] = {}
            attempt['observed_cost_usd'] = None
            attempt['cost_unknown'] = True
            attempt['billing_ok'] = False
            attempts_path.write_text(json.dumps(attempt) + '\n')
            journal = root / folder / 'development.journal.jsonl'
            events = [json.loads(line) for line in journal.read_text().splitlines()][:4]
            events[3].update(status='service_error', billing_ok=False, cost_unknown=True)
            events.append({'event': 'phase_stopped', 'id': 'DEV-001', 'reason': 'service_error'})
            journal.write_text(''.join(json.dumps(event) + '\n' for event in events))
            responses = root / folder / 'development.responses.jsonl'
            raw = json.loads(responses.read_text().splitlines()[0])
            raw = {'id': raw['id'], 'attempt_id': raw['attempt_id'],
                   'request_sha256': raw['request_sha256'], 'http_status': 429,
                   'error_body': attempt['error_body'], 'error_headers': {}}
            responses.write_text(json.dumps(raw) + '\n')
            bind, _ = report.binder(root)
            review_sha = json.loads((root / folder / 'development.claim.json').read_text())['root_review_sha256']
            ids = [f'DEV-{i:03d}' for i in range(1, 61)]
            labels = {row['id']: row['proposed_labels'] for row in report.rows(ROOT, report.LABELS)}
            with patch.object(report, '_smoke', return_value={}):
                entry, reason, _ = report._repeat_phase(root, spec, base, 'repeat2', 'P2', plan,
                                                        review_sha, ids, labels, bind)
            self.assertIsNone(reason)
            self.assertEqual(entry['completionStatus'], 'partial')
            self.assertEqual(entry['score']['denominator'], 60)
            self.assertEqual(entry['score']['outcomes']['service_error'], 1)
            self.assertEqual(entry['score']['outcomes']['never_sent'], 59)
            self.assertEqual(entry['usage']['unknownCostCount'], 1)
            self.assertIsNone(entry['usage']['actualCostUsd'])
            self.assertIsNone(entry['usage']['tokens']['input_tokens'])

    def test_cli_check_detects_stale_output_without_writing(self):
        payload = {'schema': 'hosted-repeat-series-v1', 'series': []}
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'series.json'
            with patch.object(report, 'build', return_value=payload):
                report.main(['--output', str(output)])
                original = output.read_bytes()
                report.main(['--output', str(output), '--check'])
                self.assertEqual(output.read_bytes(), original)
                output.write_text('{}\n')
                with self.assertRaisesRegex(ValueError, 'Stale report'):
                    report.main(['--output', str(output), '--check'])
                self.assertEqual(output.read_text(), '{}\n')

    def test_all_series_use_closed_phases_only(self):
        for spec in report.wave.SPECS.values():
            with self.subTest(config=spec.id):
                series = report.build_series(spec)
                self.assertEqual(series['schema'], 'hosted-repeat-findings-v1')
                self.assertEqual(series['denominator'], 60)
                self.assertEqual(series['completedConditions'] + len(series['missingPasses']) +
                                 len(series['partialPasses']), 9)
                for name in ('repeat2', 'repeat3'):
                    for condition, entry in series['passes'][name].items():
                        self.assertIn(entry['terminalEvent'],
                                      ('phase_completed', 'phase_stopped', 'phase_aborted'))
                        self.assertEqual(entry['score']['denominator'], 60)
                        self.assertIn('actualCostUsd', entry['usage'])
                        self.assertIn('tokens', entry['usage'])
                        self.assertIn('requestSecondsTotal', entry['usage'])

    def test_open_journal_is_not_scored(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        plan = {'conditions': {'P2': {'development': []}}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'results/repeatability-v1' / spec.id / 'repeat2/P2'
            folder.mkdir(parents=True)
            (folder / 'development.journal.jsonl').write_text(json.dumps({'event': 'phase_started'}) + '\n')
            result = report._repeat_phase(root, spec, Path('results/repeatability-v1') / spec.id,
                                          'repeat2', 'P2', plan, 'review', [], {}, lambda *_: None)
            self.assertEqual(result, (None, 'open_no_terminal', None))

    def test_source_bindings_survive_checkout_relocation(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        base = Path('results/repeatability-v1') / spec.id
        paths = {report.LABELS, Path(spec.pair), report.HOSTED,
                 base / 'root-review-v1.json', base / 'budget-partition-v1.json',
                 base / 'repeat2/manifest.json', base / 'repeat3/manifest.json'}
        for repeat in ('repeat2', 'repeat3'):
            plan = json.loads((ROOT / base / repeat / 'manifest.json').read_text())
            paths.update(Path(binding['path']) for binding in plan['source_bindings'])
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp)
            for relative in paths:
                target = clone / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            series = report.build_series(spec, clone)
            self.assertEqual(series['configuration'], spec.id)
            self.assertEqual(series['completedConditions'], 3)
            self.assertEqual(len(series['missingPasses']), 6)

    def test_raw_body_tamper_is_rejected(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        source = Path('results/repeatability-v1') / spec.id / 'repeat2/P2/smoke.responses.jsonl'
        original = [json.loads(line) for line in (ROOT / source).read_text().splitlines()]
        attempt_path = ROOT / source.parent / 'smoke.attempts.jsonl'
        attempts = [json.loads(line) for line in attempt_path.read_text().splitlines()]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, target)
            bind, _ = report.binder(root)
            self.assertEqual(report._sidecar(root, source, attempts, bind, required=True)['path'], str(source))
            changed = copy.deepcopy(original)
            body = json.loads(base64.b64decode(changed[0]['body_base64']))
            body['provider'] = 'Other'
            changed[0]['body_base64'] = base64.b64encode(json.dumps(body).encode()).decode()
            changed[0]['body_bytes_captured'] = len(base64.b64decode(changed[0]['body_base64']))
            target.write_text(''.join(json.dumps(row) + '\n' for row in changed))
            with self.assertRaisesRegex(ValueError, 'Raw body differs'):
                report._sidecar(root, source, attempts, bind, required=True)

    def test_aborted_started_attempt_can_retain_raw_sidecar(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        source = Path('results/repeatability-v1') / spec.id / 'repeat2/P2/smoke.responses.jsonl'
        raw = json.loads((ROOT / source).read_text().splitlines()[0])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / source
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(raw) + '\n')
            bind, _ = report.binder(root)
            pending = {'id': raw['id'], 'attempt_id': raw['attempt_id'],
                       'request_sha256': raw['request_sha256']}
            self.assertIsNotNone(report._sidecar(root, source, [], bind, pending=pending))
            with self.assertRaisesRegex(ValueError, 'More raw responses'):
                report._sidecar(root, source, [], bind)

    def test_completed_development_cannot_omit_raw_sidecar(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        base = Path('results/repeatability-v1') / spec.id
        plan = json.loads((ROOT / base / 'repeat2/manifest.json').read_text())
        folder = base / 'repeat2/P2'
        required = [base / 'repeat2/manifest.json',
                    *(folder / name for name in ('development.claim.json',
                                                 'development.journal.jsonl',
                                                 'development.attempts.jsonl'))]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in required:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            bind, _ = report.binder(root)
            review_sha = json.loads((root / folder / 'development.claim.json').read_text())['root_review_sha256']
            ids = [f'DEV-{i:03d}' for i in range(1, 61)]
            labels = {row['id']: row['proposed_labels'] for row in
                      report.rows(ROOT, report.LABELS)}
            with patch.object(report, '_smoke', return_value={}):
                with self.assertRaisesRegex(ValueError, 'Raw response sidecar missing'):
                    report._repeat_phase(root, spec, base, 'repeat2', 'P2', plan,
                                         review_sha, ids, labels, bind)

    def test_stopped_known_overspend_keeps_cost_and_denominator(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        base = Path('results/repeatability-v1') / spec.id
        plan = json.loads((ROOT / base / 'repeat2/manifest.json').read_text())
        folder = base / 'repeat2/P2'
        names = ('development.claim.json', 'development.journal.jsonl',
                 'development.attempts.jsonl', 'development.responses.jsonl')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in [base / 'repeat2/manifest.json', *(folder / name for name in names)]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            journal = root / folder / 'development.journal.jsonl'
            events = [json.loads(line) for line in journal.read_text().splitlines()]
            events = [*events[:4], {'event': 'phase_stopped', 'id': 'DEV-001',
                                    'reason': 'ok'}]
            events[3]['billing_ok'] = False
            journal.write_text(''.join(json.dumps(event) + '\n' for event in events))
            attempts_path = root / folder / 'development.attempts.jsonl'
            attempt = json.loads(attempts_path.read_text().splitlines()[0])
            attempt['observed_cost_usd'] = '0.05'
            attempt['raw_response']['usage']['cost'] = 0.05
            attempt['usage']['cost'] = 0.05
            attempt['billing_ok'] = False
            attempts_path.write_text(json.dumps(attempt) + '\n')
            responses_path = root / folder / 'development.responses.jsonl'
            response = json.loads(responses_path.read_text().splitlines()[0])
            body = json.loads(base64.b64decode(response['body_base64']))
            body['usage']['cost'] = 0.05
            encoded = json.dumps(body).encode()
            response['body_base64'] = base64.b64encode(encoded).decode()
            response['body_bytes_captured'] = len(encoded)
            responses_path.write_text(json.dumps(response) + '\n')
            bind, _ = report.binder(root)
            review_sha = json.loads((root / folder / 'development.claim.json').read_text())['root_review_sha256']
            ids = [f'DEV-{i:03d}' for i in range(1, 61)]
            labels = {row['id']: row['proposed_labels'] for row in
                      report.rows(ROOT, report.LABELS)}
            with patch.object(report, '_smoke', return_value={}):
                entry, reason, _ = report._repeat_phase(root, spec, base, 'repeat2', 'P2', plan,
                                                        review_sha, ids, labels, bind)
            self.assertIsNone(reason)
            self.assertEqual(entry['completionStatus'], 'partial')
            self.assertEqual(entry['score']['denominator'], 60)
            self.assertEqual(entry['score']['outcomes']['never_sent'], 59)
            self.assertEqual(entry['usage']['knownCostUsd'], '0.05')
            self.assertEqual(entry['usage']['actualCostUsd'], '0.05')

    def test_usage_must_mirror_raw_body_when_present(self):
        spec = report.wave.SPECS['openrouter-paid-gemma4-31b-off']
        source = ROOT / 'results/repeatability-v1' / spec.id / 'repeat2/P2/development.attempts.jsonl'
        row = json.loads(source.read_text().splitlines()[0])
        plan = json.loads((ROOT / 'results/repeatability-v1' / spec.id / 'repeat2/manifest.json').read_text())
        planned = plan['conditions']['P2']['development'][0]
        changed = copy.deepcopy(row)
        changed['usage']['prompt_tokens'] += 1
        with self.assertRaisesRegex(ValueError, 'usage differs'):
            report._check_attempt(spec, changed, planned, 'development',
                                  'repeat2', 'P2', row['manifest_sha256'])

    def test_mistral_known_invalid_is_in_sixty_record_denominator(self):
        spec = report.wave.SPECS['openrouter-paid-mistral-small32-24b-venice-not-applicable']
        source = ROOT / 'results/repeatability-v1' / spec.id / 'repeat2/P2/development.attempts.jsonl'
        row = json.loads(source.read_text().splitlines()[0])
        planned = json.loads((ROOT / 'results/repeatability-v1' / spec.id / 'repeat2/manifest.json').read_text())['conditions']['P2']['development'][0]
        changed = copy.deepcopy(row)
        changed['status'] = 'invalid_output'
        changed['prediction'] = None
        changed['raw_response']['choices'][0]['message']['content'] = 'invalid json'
        report._check_attempt(spec, changed, planned, 'development', 'repeat2', 'P2', changed['manifest_sha256'])
        self.assertTrue(report._continued_intrinsic_invalid(changed))
        changed['raw_response']['choices'][0]['message']['refusal'] = 'refused'
        self.assertFalse(report._continued_intrinsic_invalid(changed))
        del changed['raw_response']['choices'][0]['message']['refusal']
        ids = [f'DEV-{i:03d}' for i in range(1, 61)]
        indexed = {rid: {'id': rid, 'status': 'never_sent', 'prediction': None} for rid in ids}
        indexed['DEV-001'] = changed
        labels = {rid: {field: 'no' for field in report.FIELDS} for rid in ids}
        score = report.shared.score(indexed, labels, ids)
        self.assertEqual(score['denominator'], 60)
        self.assertEqual(score['outcomes']['invalid_output'], 1)
        self.assertEqual(score['outcomes']['service_error'], 0)

    def test_real_mistral_429_partial_retains_error_and_unknown_cost(self):
        spec = report.wave.SPECS['openrouter-paid-mistral-small32-24b-venice-not-applicable']
        series = report.build_series(spec)
        entry = series['passes']['repeat2']['P1']
        self.assertEqual(entry['completionStatus'], 'partial')
        self.assertEqual(entry['terminalEvent'], 'phase_stopped')
        self.assertEqual(entry['finishedRequests'], 43)
        self.assertEqual(entry['score']['denominator'], 60)
        self.assertEqual(entry['score']['outcomes']['valid'], 42)
        self.assertEqual(entry['score']['outcomes']['service_error'], 1)
        self.assertEqual(entry['score']['outcomes']['never_sent'], 17)
        self.assertEqual(entry['usage']['unknownCostCount'], 1)
        self.assertIsNone(entry['usage']['actualCostUsd'])
        self.assertIsNone(entry['usage']['tokens']['input_tokens'])
        self.assertIn('responses', entry['evidence'])
        folder = ROOT / 'results/repeatability-v1' / spec.id / 'repeat2/P1'
        attempt = json.loads((folder / 'development.attempts.jsonl').read_text().splitlines()[-1])
        response = json.loads((folder / 'development.responses.jsonl').read_text().splitlines()[-1])
        self.assertEqual((attempt['id'], attempt['status'], attempt['http_status']),
                         ('DEV-043', 'service_error', 429))
        self.assertTrue(attempt['cost_unknown'])
        self.assertFalse(attempt['billing_ok'])
        self.assertIsNone(attempt['observed_cost_usd'])
        self.assertEqual(response['attempt_id'], attempt['attempt_id'])
        self.assertEqual(response['error_body'], attempt['error_body'])
        self.assertTrue(response['error_body'])


if __name__ == '__main__':
    unittest.main()
