"""Offline checks for public copies of private Claude evidence."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import export_claude_public_evidence as exporter
from claude_batch_benchmark import parse_batch_result


class PublicClaudeEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw_rel = Path('results/private/smoke.batch-000.raw.jsonl')
        self.attempt_rel = Path('results/private/smoke.attempts.jsonl')
        self.raw_path = self.root / self.raw_rel
        self.attempt_path = self.root / self.attempt_rel
        self.raw_path.parent.mkdir(parents=True)
        prediction = {'records': [{'id': 'DEV-001', 'sentiment': 'positive',
                                   'follow_up_needed': 'no',
                                   'serious_concern_reported': 'no',
                                   'testimonial_potential': 'no'}]}
        rate = {'type': 'rate_limit_event', 'rate_limit_info': {
            'unifiedWindows': {'five_hour': {'utilization': 0.75, 'resetsAt': 12345},
                               'seven_day': {'utilization': 0.25, 'resetsAt': 67890}},
            'status': 'allowed', 'isUsingOverage': False}}
        events = [
            {'type': 'system', 'subtype': 'init', 'cwd': '/Users/tester/work',
             'email': 'private@example.test', 'access_token': 'secret-value'},
            {'type': 'assistant', 'message': {'model': 'claude-haiku-4-5-20251001',
                                              'content': []}},
            rate,
            {'type': 'result', 'subtype': 'success', 'is_error': False,
             'structured_output': prediction, 'usage': {'input_tokens': 12,
                                                        'output_tokens': 8},
             'modelUsage': {}, 'total_cost_usd': 0.01,
             'duration_ms': 1400, 'duration_api_ms': 1200},
        ]
        raw = {'schema': 'claude-repeat-raw-capture-v1', 'record_ids': ['DEV-001'],
               'exit_code': 0, 'stdout': json.dumps(events), 'stderr': ''}
        attempt = {'ids': ['DEV-001'], 'requested_model': 'claude-haiku-4-5-20251001',
                   'request': {'feedback': 'A short public synthetic comment'},
                   'prediction': prediction, 'status': 'ok',
                   'usage': {'input_tokens': 12, 'output_tokens': 8},
                   'model_usage': {}, 'overage_observed': False,
                   'rate_limit_events': [rate['rate_limit_info']],
                   'raw_events': events, 'actual_billed_usd': None,
                   'cli_duration_ms': 1400, 'cli_api_duration_ms': 1200,
                   'cli_estimated_api_equivalent_usd': 0.01,
                   'returned_models': [], 'raw_capture_file': self.raw_path.name}
        self.raw_path.write_bytes(exporter.canonical(raw))
        self.attempt_path.write_bytes(exporter.canonical(attempt))
        self.original_raw = self.raw_path.read_bytes()
        self.original_attempt = self.attempt_path.read_bytes()
        self.report_path = self.root / 'private-report.json'
        sources = [self.binding(self.raw_rel), self.binding(self.attempt_rel)]
        self.report_path.write_bytes(exporter.canonical({
            'schema': 'test-private-report', 'sourceBindings': sources,
            'passes': {'P0': {'evidence': {'rawCaptures': [sources[0]],
                                           'attempts': sources[1]},
                              'score': {'valid': 1}}}}))
        self.output = self.root / 'public-evidence/claude'

    def binding(self, relative):
        return {'path': str(relative),
                'sha256': hashlib.sha256((self.root / relative).read_bytes()).hexdigest()}

    def test_export_preserves_private_bytes_and_prediction_usage(self):
        mapping = exporter.export(self.report_path, self.output, self.root)
        self.assertEqual(self.raw_path.read_bytes(), self.original_raw)
        self.assertEqual(self.attempt_path.read_bytes(), self.original_attempt)
        public = exporter.verify_public(self.output, self.root)
        self.assertEqual(public['passes']['P0']['score']['valid'], 1)
        self.assertEqual(len(mapping), 2)
        raw_public = self.root / mapping[str(self.raw_rel)]['publicPath']
        attempt_public = self.root / mapping[str(self.attempt_rel)]['publicPath']
        raw = json.loads(raw_public.read_text())
        events = json.loads(raw['stdout'])
        original_events = json.loads(json.loads(self.original_raw)['stdout'])
        self.assertEqual(parse_batch_result(original_events, 0, ['DEV-001'])['status'], 'ok')
        self.assertEqual(parse_batch_result(events, 0, ['DEV-001'])['status'], 'ok')
        safe_rate = [event for event in events if event.get('type') == 'rate_limit_event']
        self.assertEqual(safe_rate, [{'type': 'rate_limit_event',
                                      'rate_limit_info': {'isUsingOverage': False}}])
        self.assertNotIn('/Users/tester', raw_public.read_text())
        attempt = json.loads(attempt_public.read_text())
        self.assertEqual(attempt['prediction'], json.loads(self.original_attempt)['prediction'])
        self.assertEqual(attempt['usage'], {'input_tokens': 12, 'output_tokens': 8})
        self.assertFalse(attempt['overage_observed'])
        self.assertNotIn('rate_limit_events', attempt)
        self.assertNotIn('email', attempt_public.read_text())
        first = ((self.output / 'report.json').read_bytes(),
                 (self.output / 'mapping.json').read_bytes())
        exporter.export(self.report_path, self.output, self.root)
        self.assertEqual(first, ((self.output / 'report.json').read_bytes(),
                                 (self.output / 'mapping.json').read_bytes()))

    def test_multi_series_report_binding_groups(self):
        private = json.loads(self.report_path.read_text())
        wrapped = {'schema': 'test-roster-report', 'series': [private, private]}
        self.report_path.write_bytes(exporter.canonical(wrapped))
        mapping = exporter.export(self.report_path, self.output, self.root)
        self.assertEqual(len(mapping), 2)
        public = exporter.verify_public(self.output, self.root)
        self.assertEqual(len(public['series']), 2)
        self.assertEqual(public['series'][0]['sourceBindings'],
                         public['series'][1]['sourceBindings'])

    def test_public_bundle_survives_original_source_changes(self):
        code_rel = Path('scripts/frozen-runner.py')
        code_path = self.root / code_rel
        code_path.parent.mkdir(parents=True)
        code_path.write_bytes(b'original runner bytes\n')
        private = json.loads(self.report_path.read_text())
        private['sourceBindings'].append(self.binding(code_rel))
        self.report_path.write_bytes(exporter.canonical(private))
        mapping = exporter.export(self.report_path, self.output, self.root)
        self.assertTrue(all(entry['publicPath'].startswith('public-evidence/claude/evidence/')
                            for entry in mapping.values()))
        self.assertFalse(mapping[str(code_rel)]['redacted'])
        self.assertEqual((self.root / mapping[str(code_rel)]['publicPath']).read_bytes(),
                         b'original runner bytes\n')
        self.raw_path.write_bytes(b'legitimate later source edit\n')
        self.attempt_path.unlink()
        code_path.write_bytes(b'updated runner bytes\n')
        exporter.verify_public(self.output, self.root)
        check = subprocess.run([sys.executable, str(Path(exporter.__file__)),
                                '--check', '--source-root', str(self.root),
                                '--output-dir', str(self.output)],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_tampered_public_copy_and_private_binding_rejected(self):
        mapping = exporter.export(self.report_path, self.output, self.root)
        public_path = self.root / mapping[str(self.raw_rel)]['publicPath']
        public_path.write_bytes(public_path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'Public evidence hash changed'):
            exporter.verify_public(self.output, self.root)
        public_path.write_bytes(self.original_raw)
        with self.assertRaisesRegex(ValueError, 'Public evidence hash changed'):
            exporter.verify_public(self.output, self.root)
        self.attempt_path.write_bytes(self.original_attempt + b' ')
        with self.assertRaisesRegex(ValueError, 'Private source binding changed'):
            exporter.export(self.report_path, self.output, self.root)

    def test_nested_report_binding_must_match_mapping(self):
        exporter.export(self.report_path, self.output, self.root)
        report_path = self.output / 'report.json'
        map_path = self.output / 'mapping.json'
        report = json.loads(report_path.read_text())
        report['passes']['P0']['evidence']['attempts']['sha256'] = '0' * 64
        report_path.write_bytes(exporter.canonical(report))
        mapping = json.loads(map_path.read_text())
        mapping['publicReportSha256'] = exporter.sha(report_path.read_bytes())
        map_path.write_bytes(exporter.canonical(mapping))
        with self.assertRaisesRegex(ValueError, 'Public report binding differs from mapping'):
            exporter.verify_public(self.output, self.root)

    def test_redaction_scan_rejects_private_fields(self):
        with self.assertRaisesRegex(ValueError, 'Private field remains'):
            exporter.assert_redacted({'rate_limit_info': {'utilization': 0.1}})
        with self.assertRaisesRegex(ValueError, 'Private profile or token'):
            exporter.assert_redacted({'note': 'Bearer secret-token'})
        redacted = exporter.redact({'header': 'Bearer actual-token'})
        self.assertEqual(redacted, {'header': 'Bearer [REDACTED]'})
        self.assertEqual(exporter.redact(redacted), redacted)
        exporter.assert_redacted(redacted)
        with self.assertRaisesRegex(ValueError, 'lacks no-overage evidence'):
            exporter.redact({'type': 'rate_limit_event',
                             'rate_limit_info': {'unifiedWindows': {}}})
        with self.assertRaisesRegex(ValueError, 'escapes source root'):
            exporter.safe_path(self.root, '../outside')


if __name__ == '__main__':
    unittest.main()
