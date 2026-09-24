import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gemini_prompt_execution_v2 as subject


class GeminiExactOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(subject.MANIFEST.read_text())
        cls.row = subject.inputs(cls.manifest)[0]
        cls.group = [cls.row]

    def stream(self, model='gemini-3.1-pro-low', prediction=None, tool=None, success=True):
        if prediction is None:
            prediction = {'id': self.row['id'], 'sentiment': 'neutral', 'follow_up_needed': 'no',
                'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        events = [{'event': 'init', 'init': {'agent': 'recruitment-benchmark', 'model': model,
            'tools': ['finish'], 'memory_enabled': False, 'mcpServers': [], 'skills': [], 'plugins': [],
            'json_schema': subject.batch_schema(self.group)}}]
        if tool:
            events.append({'event': 'step_update', 'step_update': {'step_type': 'tool', 'tool_name': tool}})
        events.append({'event': 'result', 'result': {'status': 'SUCCESS' if success else 'ERROR',
            'structured_output': {'records': [prediction]}, 'usage': {'input_tokens': 1, 'output_tokens': 1}}})
        return '\n'.join(json.dumps(e) for e in events)

    def test_full_offline_preflight_checks_all_previews(self):
        result = subject.preflight()
        self.assertEqual((result['preview_count'], result['condition_count'], result['record_count']), (28, 14, 60))
        self.assertFalse(result['inference_performed'])

    def test_frozen_schedule_and_output_scope(self):
        altered = copy.deepcopy(self.manifest)
        altered['configurations'][0]['condition_order'].reverse()
        with self.assertRaisesRegex(ValueError, 'order differs'):
            subject.verify_manifest(altered)
        altered = copy.deepcopy(self.manifest)
        altered['configurations'][0]['conditions']['P1']['smoke_output'] = '/tmp/outside/smoke.jsonl'
        with self.assertRaises(ValueError): subject.verify_manifest(altered)

    def test_cli_transition_binding_cannot_be_silently_removed(self):
        altered = copy.deepcopy(self.manifest)
        altered['transition']['reason'] = 'same runtime as parent'
        with self.assertRaisesRegex(ValueError, 'version-transition'):
            subject.verify_manifest(altered)
        altered = copy.deepcopy(self.manifest)
        altered['cli']['version'] = '1.2.9'
        with self.assertRaisesRegex(ValueError, 'Pinned native CLI changed'):
            subject.verify_manifest(altered)

    def test_preview_membership_tamper_rejected(self):
        altered = copy.deepcopy(self.manifest)
        spec = altered['configurations'][0]['conditions']['P1']['smoke_preview']
        preview = subject.bound_json(spec)
        preview['requests'][0]['record_ids'][0] = 'DEV-060'
        with patch.object(subject, 'bound_json', side_effect=lambda x: preview if x == spec else json.loads(subject.bound(x).read_text())):
            with self.assertRaisesRegex(ValueError, 'Exact preview request differs'):
                subject.verify_manifest(altered)

    def test_strict_native_response_and_identity_failure(self):
        raw = self.stream()
        result = subject.strict_response(raw, '', 0, 'gemini-3.1-pro-low', self.group)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['predictions'][self.row['id']]['sentiment'], 'neutral')
        self.assertEqual(subject.strict_response(self.stream(model='other-model'), '', 0, 'gemini-3.1-pro-low', self.group)['status'], 'model_mismatch')
        self.assertEqual(subject.strict_response(raw, 'Warning: ignored schema', 0, 'gemini-3.1-pro-low', self.group)['status'], 'unverified_configuration')
        self.assertEqual(subject.strict_response(self.stream(tool='shell'), '', 0, 'gemini-3.1-pro-low', self.group)['status'], 'isolation_violation')

    def test_invalid_output_only_after_successful_native_finish(self):
        bad = {'id': self.row['id'], 'sentiment': 'wrong'}
        self.assertEqual(subject.strict_response(self.stream(prediction=bad), '', 0, 'gemini-3.1-pro-low', self.group)['status'], 'invalid_output')
        self.assertEqual(subject.strict_response(self.stream(prediction=bad, success=False), '', 0, 'gemini-3.1-pro-low', self.group)['status'], 'service_error')
        self.assertEqual(subject.strict_response(self.stream(prediction=bad), 'Warning: schema ignored', 0, 'gemini-3.1-pro-low', self.group)['status'], 'unverified_configuration')
        exposed = [json.loads(line) for line in self.stream(prediction=bad).splitlines()]
        exposed[0]['init']['mcpServers'] = ['unexpected']
        self.assertEqual(subject.strict_response('\n'.join(json.dumps(e) for e in exposed), '', 0, 'gemini-3.1-pro-low', self.group)['status'], 'isolation_violation')
        exposed[0]['init']['mcpServers'] = []
        exposed[0]['init']['memory_enabled'] = True
        self.assertEqual(subject.strict_response('\n'.join(json.dumps(e) for e in exposed), '', 0, 'gemini-3.1-pro-low', self.group)['status'], 'isolation_violation')

    def test_live_gate_requires_bound_review(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'root-review.json'
            path.write_text('{}')
            with self.assertRaises(ValueError):
                subject.load_review(subject.bind(subject.MANIFEST)['sha256'], '0' * 64, path, subject.sha(path.read_bytes()))

    def test_reused_output_rejected_before_runtime_or_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'smoke.jsonl'; path.write_text('')
            altered = copy.deepcopy(self.manifest['configurations'][0])
            altered['conditions']['P1']['smoke_output'] = str(path)
            with patch.object(subject, 'runtime', side_effect=AssertionError('runtime reached')):
                with self.assertRaises(FileExistsError):
                    subject.run_stage(self.manifest, altered, 'P1', 'smoke')

    def test_smoke_inspection_binds_raw_request_and_predictions(self):
        item = copy.deepcopy(self.manifest['configurations'][0]); condition = 'P1'
        rows = subject.inputs(self.manifest)[:3]
        preview = subject.bound_json(item['conditions'][condition]['smoke_preview'])['requests'][0]
        judgments = [{'id': r['id'], 'sentiment': 'neutral', 'follow_up_needed': 'no',
            'serious_concern_reported': 'no', 'testimonial_potential': 'no'} for r in rows]
        events = [
            {'event': 'init', 'init': {'agent': 'recruitment-benchmark', 'model': item['model'],
                'tools': ['finish'], 'memory_enabled': False, 'mcpServers': [], 'skills': [], 'plugins': [],
                'json_schema': preview['request']['output_schema']}},
            {'event': 'result', 'result': {'status': 'SUCCESS', 'structured_output': {'records': judgments}}}]
        stdout = '\n'.join(json.dumps(e) for e in events)
        parsed = subject.strict_response(stdout, '', 0, item['model'], rows)
        finished = datetime.now(timezone.utc) - timedelta(seconds=2)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            output = directory / 'smoke.jsonl'; attempts = directory / 'smoke-attempts.jsonl'
            terminal = directory / 'smoke.terminal.json'; inspection = directory / 'smoke-inspection.json'
            item['conditions'][condition]['smoke_output'] = str(output)
            attempt = {'id': 'batch-01', 'status': 'ok', 'record_order': [r['id'] for r in rows], 'request': copy.deepcopy(preview['request']),
                'request_sha256': preview['request_sha256'], 'schema_sha256': preview['schema_sha256'],
                'prompt_variant': preview['prompt_variant'], 'agent_definition': subject.native.AGENT,
                'reference_labels_read': False, 'controller_retries': 0,
                'cli_binary_sha256': self.manifest['cli']['sha256'], 'cli_version': '1.2.10',
                'billing_audit': {'useG1Credits': False}, 'raw_stdout': stdout, 'raw_stderr': '',
                'returncode': 0, 'predictions': parsed['predictions'], 'finished_utc': finished.isoformat()}
            predictions = [{'id': r['id'], 'status': 'ok', 'prediction': parsed['predictions'][r['id']]} for r in rows]
            attempts.write_text(json.dumps(attempt) + '\n')
            output.write_text(''.join(json.dumps(r) + '\n' for r in predictions))
            terminal.write_text(json.dumps({'status': 'completed'}))
            with patch.object(subject, 'bind', side_effect=lambda path: {'file': str(path), 'sha256': subject.sha(Path(path).read_bytes())}), patch.object(subject, 'bound_json', return_value={'requests': [preview]}), patch.object(subject, 'inputs', return_value=rows):
                declaration = {'contract': 'gemini-exact-smoke-inspection-v2', 'manifest': subject.bind(subject.MANIFEST),
                    'configuration_id': item['configuration_id'], 'condition': condition,
                    'predictions': subject.bind(output), 'raw_attempts': subject.bind(attempts),
                    'terminal': subject.bind(terminal), 'inspector': 'offline-test',
                    'inspected_utc': datetime.now(timezone.utc).isoformat(), 'records': copy.deepcopy(predictions)}
                inspection.write_text(json.dumps(declaration))
                self.assertEqual(subject.inspect_smoke(self.manifest, item, condition, inspection, subject.sha(inspection.read_bytes()))['file'], str(inspection.resolve()))
                declaration['records'][0]['prediction'] = None
                inspection.write_text(json.dumps(declaration))
                with self.assertRaisesRegex(ValueError, 'inspection differs'):
                    subject.inspect_smoke(self.manifest, item, condition, inspection, subject.sha(inspection.read_bytes()))
                declaration['records'] = copy.deepcopy(predictions)
                attempt['request']['prompt'] += ' tampered'
                attempts.write_text(json.dumps(attempt) + '\n')
                declaration['raw_attempts'] = subject.bind(attempts)
                inspection.write_text(json.dumps(declaration))
                with self.assertRaisesRegex(ValueError, 'frozen preview'):
                    subject.inspect_smoke(self.manifest, item, condition, inspection, subject.sha(inspection.read_bytes()))


if __name__ == '__main__': unittest.main()
