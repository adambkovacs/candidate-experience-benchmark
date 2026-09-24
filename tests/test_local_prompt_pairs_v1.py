import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from evaluate_local_prompt_pairs_v1 import audit_p0, equal_visible_controls


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


class LocalPairAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = 'synthetic-sdk'
        self.prediction = {'sentiment': 'positive', 'follow_up_needed': 'no',
                           'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        self.inputs = [{'id': f'DEV-{i:03}', 'feedback': f'Feedback {i}'} for i in range(1, 61)]
        self.rows = []
        self.events = []
        for i, source in enumerate(self.inputs):
            request = {'messages': [{'role': 'system', 'content': 'policy'},
                                    {'role': 'user', 'content': json.dumps({'feedback': source['feedback']})}],
                       'config': {'temperature': 0, 'reasoningParsing': {'enabled': False}}}
            row = {'id': source['id'], 'attempt_id': f'attempt-{i}', 'requested_model': 'model',
                   'surface': 'LM Studio JavaScript SDK', 'thinking': 'off', 'format': 'prompt',
                   'started_utc': f'2026-09-21T19:{i:02}:00Z', 'request': request,
                   'reference_labels_read': False,
                   'policy_sha256': hashlib.sha256(b'policy').hexdigest(),
                   'input_sha256': hashlib.sha256(source['feedback'].encode()).hexdigest(),
                   'artifact_sha256': 'artifact', 'artifact_path': 'model.gguf',
                   'template_sha256': 'template', 'timeout_seconds': 600,
                   'model_info': {'identifier': 'model', 'path': 'model.gguf', 'sizeBytes': 100,
                                  'contextLength': 8192, 'quantization': {'name': 'Q4_K_M'},
                                  'instanceReference': f'instance-{i}'},
                   'load_config': {'fields': []}, 'prediction_config': {'fields': []},
                   'raw_response': json.dumps(self.prediction), 'non_reasoning_content': json.dumps(self.prediction),
                   'reasoning_content': '', 'stats': {'stopReason': 'eosFound'},
                   'prediction': self.prediction, 'status': 'ok'}
            self.rows.append(row)
            self.events.extend([{'event': 'started', 'id': row['id'], 'attempt_id': row['attempt_id'],
                                 'request_sha256': hashlib.sha256(json.dumps(request, separators=(',', ':')).encode()).hexdigest()},
                                {'event': 'finished', 'id': row['id'], 'attempt_id': row['attempt_id'], 'status': 'ok'}])
        self.baseline = Path('results/baseline.jsonl')
        self.journal = Path('results/baseline.jsonl.attempts.jsonl')
        self.manifest = Path('results/baseline-manifest.json')
        self.inputs_path = Path('data/pilot/inputs.jsonl')
        write_jsonl(self.root / self.inputs_path, self.inputs)
        write_jsonl(self.root / self.baseline, self.rows)
        write_jsonl(self.root / self.journal, self.events)
        (self.root / self.manifest).write_text(json.dumps({'status': 'complete', 'unique_records': 60,
            'valid_outputs': 60, 'thinking': 'off', 'surface': 'LM Studio JavaScript SDK1.5.0',
            'lms_commit': 'abc', 'lm_studio': '0.4', 'selected_gguf_runtime': 'engine',
            'hardware': {'identifier': 'Mac'}, 'artifact': {'sha256': 'artifact', 'bytes': 100,
            'quantization': 'Q4_K_M'}, 'template_sha256': 'template', 'format': 'prompt',
            'prediction_sha256': sha(self.root / self.baseline)}) + '\n')
        self.parent = {'source_sha256': {str(self.baseline): sha(self.root / self.baseline),
                         str(self.manifest): sha(self.root / self.manifest),
                         str(self.inputs_path): sha(self.root / self.inputs_path)},
                       'runtime': {'cli_commit': 'abc', 'lm_studio_version': '0.4',
                                   'selected_engine': 'engine'},
                       'hardware': {'model_identifier': 'Mac'},
                       'configs': {self.config: {'surface': 'lmstudio_sdk', 'identifier': 'model',
                         'artifact_path': 'model.gguf', 'artifact_sha256': 'artifact',
                         'artifact_bytes': 100, 'baseline_file': str(self.baseline),
                         'baseline_manifest_file': str(self.manifest), 'timeout_ms': 600000}}}

    def test_p0_audit_accepts_complete_hash_bound_single_record_evidence(self):
        audited = audit_p0(self.root, self.parent, self.config)
        self.assertEqual(len(audited['rows']), 60)
        self.assertEqual(audited['controls']['request_config']['temperature'], 0)

    def test_p0_audit_rejects_journal_gap(self):
        write_jsonl(self.root / self.journal, self.events[:-1])
        with self.assertRaisesRegex(ValueError, 'journal'):
            audit_p0(self.root, self.parent, self.config)

    def test_p0_audit_rejects_frozen_baseline_drift(self):
        self.rows[0]['request']['messages'][1]['content'] = '{"feedback":"changed"}'
        write_jsonl(self.root / self.baseline, self.rows)
        with self.assertRaisesRegex(ValueError, 'Frozen source hash mismatch'):
            audit_p0(self.root, self.parent, self.config)

    def test_p0_audit_rejects_unbacked_native_split_even_with_updated_hashes(self):
        self.rows[0]['raw_response'] = 'different native text'
        write_jsonl(self.root / self.baseline, self.rows)
        self.parent['source_sha256'][str(self.baseline)] = sha(self.root / self.baseline)
        manifest = json.loads((self.root / self.manifest).read_text())
        manifest['prediction_sha256'] = sha(self.root / self.baseline)
        (self.root / self.manifest).write_text(json.dumps(manifest) + '\n')
        self.parent['source_sha256'][str(self.manifest)] = sha(self.root / self.manifest)
        with self.assertRaisesRegex(ValueError, 'raw response'):
            audit_p0(self.root, self.parent, self.config)

    def test_p0_accepts_frozen_e4b_commit_and_hardware_labels(self):
        manifest = json.loads((self.root / self.manifest).read_text())
        manifest['lms_commit'] = 'CLI commit: abc'
        manifest['hardware'] = {'model': 'Mac'}
        (self.root / self.manifest).write_text(json.dumps(manifest) + '\n')
        self.parent['source_sha256'][str(self.manifest)] = sha(self.root / self.manifest)
        self.assertEqual(len(audit_p0(self.root, self.parent, self.config)['rows']), 60)
        manifest['lms_commit'] = 'CLI commit: different'
        (self.root / self.manifest).write_text(json.dumps(manifest) + '\n')
        self.parent['source_sha256'][str(self.manifest)] = sha(self.root / self.manifest)
        with self.assertRaisesRegex(ValueError, 'manifest does not bind'):
            audit_p0(self.root, self.parent, self.config)

    def test_visible_controls_ignore_only_ephemeral_instance(self):
        left = self.rows[0]
        right = json.loads(json.dumps(left))
        right['model_info']['instanceReference'] = 'new-instance'
        equal_visible_controls(left, right)
        right['request']['config']['temperature'] = 1
        with self.assertRaisesRegex(ValueError, 'request config'):
            equal_visible_controls(left, right)

    def test_p0_rejects_invalid_status_for_valid_native_json(self):
        self.rows[0]['status'] = 'invalid_output'
        self.rows[0]['prediction'] = None
        self.events[1]['status'] = 'invalid_output'
        write_jsonl(self.root / self.baseline, self.rows)
        write_jsonl(self.root / self.journal, self.events)
        self.parent['source_sha256'][str(self.baseline)] = sha(self.root / self.baseline)
        manifest = json.loads((self.root / self.manifest).read_text())
        manifest.update({'prediction_sha256': sha(self.root / self.baseline), 'valid_outputs': 59})
        (self.root / self.manifest).write_text(json.dumps(manifest) + '\n')
        self.parent['source_sha256'][str(self.manifest)] = sha(self.root / self.manifest)
        with self.assertRaisesRegex(ValueError, 'invalid status contradicts'):
            audit_p0(self.root, self.parent, self.config)


if __name__ == '__main__':
    unittest.main()
