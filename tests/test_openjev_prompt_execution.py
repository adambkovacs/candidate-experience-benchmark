import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import openjev_prompt_execution as execution


class OpenJevExecutionTests(unittest.TestCase):
    def native_response(self, content='{"sentiment":"neutral","follow_up_needed":"no","serious_concern_reported":"no","testimonial_potential":"no"}',
                        model='diffusiongemma-26b', prompt_tokens=10):
        return {'model': model, 'usage': {'prompt_tokens': prompt_tokens, 'completion_tokens': 12},
                'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}

    def test_manifest_conditions_keep_counterbalanced_order(self):
        manifest = json.loads(execution.MANIFEST.read_text())
        off = execution.condition(manifest, 'generated-off', 'P1')
        on = execution.condition(manifest, 'generated-on', 'P2')
        self.assertEqual(off['variant_order'], ['P1', 'P2'])
        self.assertEqual(on['variant_order'], ['P2', 'P1'])
        self.assertFalse(off['chat_template_enable_thinking'])
        self.assertTrue(on['chat_template_enable_thinking'])
        changed = json.loads(json.dumps(manifest))
        changed['conditions'][0]['variant_order'].reverse()
        with self.assertRaisesRegex(ValueError, 'Counterbalanced schedule changed'):
            execution.condition(changed, 'generated-off', 'P1')

    def test_missing_review_receipt_rejected_before_model_or_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'Review receipt must be within'):
                execution.load_review(execution.binding(execution.MANIFEST)['sha256'],
                    execution.binding(execution.PREFLIGHT)['sha256'],
                    Path(temporary) / 'missing.json', '0' * 64)

    def test_existing_output_rejected_before_server_or_schedule(self):
        manifest = json.loads(execution.MANIFEST.read_text())
        item = execution.condition(manifest, 'generated-off', 'P1')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / item['outputs']['P1']['smoke']
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{}\n')
            with patch.object(execution, 'ROOT', root):
                with self.assertRaisesRegex(FileExistsError, 'already exists'):
                    execution.execute(manifest, None, '0' * 64, '0' * 64, item, 'P1', 'smoke')

    def test_server_requires_unused_attestation_path_before_model_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            attestation = Path(temporary) / 'server.json'
            attestation.write_text('{}\n')
            with patch.object(execution, 'ATTESTATION', attestation):
                with self.assertRaises(FileExistsError):
                    execution.serve({}, '0' * 64, '0' * 64)

    def test_development_requires_separate_smoke_inspection(self):
        manifest = json.loads(execution.MANIFEST.read_text())
        item = execution.condition(manifest, 'generated-on', 'P2')
        with self.assertRaisesRegex(ValueError, 'separate reviewed smoke inspection'):
            execution.inspect_smoke(manifest, item, 'P2', None, None)

    def test_native_response_classifies_content_and_rejects_control_failures(self):
        good = execution.parse_native_response(self.native_response(), 10)
        self.assertEqual(good['status'], 'ok')
        self.assertEqual(good['prediction']['sentiment'], 'neutral')
        malformed = execution.parse_native_response(self.native_response(content='{'), 10)
        self.assertEqual(malformed['status'], 'invalid_output')
        self.assertIsNone(malformed['prediction'])
        with self.assertRaisesRegex(ValueError, 'Returned model identity mismatch'):
            execution.parse_native_response(self.native_response(model='other-model'), 10)
        with self.assertRaisesRegex(ValueError, 'Native usage differs'):
            execution.parse_native_response(self.native_response(prompt_tokens=11), 10)
        with self.assertRaisesRegex(ValueError, 'output reserve'):
            response = self.native_response()
            response['usage']['completion_tokens'] = 2049
            execution.parse_native_response(response, 10)

    def test_smoke_inspection_checks_raw_parse_tamper_and_intrinsic_acceptance(self):
        manifest = json.loads(execution.MANIFEST.read_text())
        item = copy.deepcopy(execution.condition(manifest, 'generated-off', 'P1'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            item['outputs']['P1']['smoke'] = 'smoke.jsonl'
            smoke = root / 'smoke.jsonl'
            terminal = root / 'smoke.jsonl.terminal.json'
            inspection_path = root / 'inspection.json'
            finished = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
            inspected = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            good = execution.parse_native_response(self.native_response(), 10)
            bad = execution.parse_native_response(self.native_response(content='{'), 10)
            raw = []
            for i, parsed in enumerate((good, bad, good), 1):
                response = self.native_response(content='{' if i == 2 else self.native_response()['choices'][0]['message']['content'])
                raw.append({'id': f'DEV-{i:03d}', 'status': parsed['status'],
                            'prediction': parsed['prediction'], 'finish_reason': 'stop',
                            'input_tokens': 10, 'returned_model': 'diffusiongemma-26b',
                            'raw_response': response, 'finished_utc': finished})
            smoke.write_text(''.join(json.dumps(row) + '\n' for row in raw))
            terminal.write_text('{"status":"completed"}\n')
            def fake_binding(path):
                path = Path(path)
                return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            inspection = {'contract': 'openjev-generated-exact-smoke-inspection-v1',
                'manifest': fake_binding(execution.MANIFEST), 'mode': 'generated-off',
                'condition': 'P1', 'raw_attempts': fake_binding(smoke),
                'terminal': fake_binding(terminal), 'inspector': 'test',
                'inspected_utc': inspected,
                'records': [{'id': row['id'], 'status': row['status'],
                             'prediction': row['prediction'],
                             **({'accepted_unchanged': True, 'inspection_reason': 'Intrinsic malformed JSON'} if row['status'] == 'invalid_output' else {})}
                            for row in raw]}
            def check():
                inspection_path.write_text(json.dumps(inspection))
                digest = hashlib.sha256(inspection_path.read_bytes()).hexdigest()
                return execution.inspect_smoke(manifest, item, 'P1', inspection_path, digest)
            with patch.object(execution, 'ROOT', root), patch.object(execution, 'binding', side_effect=fake_binding):
                self.assertEqual(check(), fake_binding(inspection_path))
                inspection['records'][1].pop('accepted_unchanged')
                with self.assertRaisesRegex(ValueError, 'unchanged acceptance'):
                    check()
                inspection['records'][1]['accepted_unchanged'] = True
                inspection['records'][0]['prediction'] = None
                with self.assertRaisesRegex(ValueError, 'Inspected smoke row differs'):
                    check()
                inspection['records'][0]['prediction'] = good['prediction']
                raw[0]['raw_response']['model'] = 'other-model'
                smoke.write_text(''.join(json.dumps(row) + '\n' for row in raw))
                inspection['raw_attempts'] = fake_binding(smoke)
                with self.assertRaisesRegex(ValueError, 'Returned model identity mismatch'):
                    check()


if __name__ == '__main__':
    unittest.main()
