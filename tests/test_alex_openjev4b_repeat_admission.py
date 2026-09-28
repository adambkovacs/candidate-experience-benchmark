"""Offline Alex 4B native P0 admission tests with model doubles; no weights are loaded."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import alex_openjev4b_repeat_admission as admission


class Tokenizer:
    def __call__(self, text, truncation=False):
        if truncation:
            raise AssertionError('Native full input must not truncate')
        return {'input_ids': [len(text) % 251 + 1] * max(1, len(text) // 10)}


class ModelDouble:
    def __init__(self, *, failure=False):
        self.tok = Tokenizer()
        self.template = 'Premise: {premise}\nHypothesis: {hypothesis}'
        self.failure = failure
        self.calls = 0

    def predict(self, pairs):
        self.calls += 1
        if self.failure:
            raise RuntimeError('synthetic interrupted native call')
        assert len(pairs) == 14
        return SimpleNamespace(tolist=lambda: [[0.1, 0.8, 0.1] for _ in pairs])


class AlexAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.plan_path = self.root / 'manifest.json'
        self.lock = self.root / 'host.lock'
        patches = [mock.patch.object(admission, 'PLAN_PATH', self.plan_path),
                   mock.patch.object(admission, 'HOST_LOCK', self.lock)]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        rows, policy = admission.source_rows()
        self.requests = admission.native_requests(rows, policy, Tokenizer(),
            'Premise: {premise}\nHypothesis: {hypothesis}')
        self.plan = {'schema': 'alex-openjev4b-native-p0-repeat-admission-v1',
                     'disposition': 'fresh_matched_three_historical_observational',
                     'schedule': list(admission.SCHEDULE),
                     'requests': self.requests,
                     'nli_template': 'Premise: {premise}\nHypothesis: {hypothesis}',
                     'model_path': str(admission.MODEL),
                     'artifact_revision': admission.REVISION,
                     'asset_sha256': {str(Path(admission.MODEL.name) / 'model.safetensors'): 'asset-sha'},
                     'runtime': {'device': 'mps:0', 'dtype': 'torch.float32'},
                     'stage_inputs': {'smoke': {'limit': 3}, 'development': {'limit': 60}}}
        self.sha = 'plan-sha'
        verify = mock.patch.object(admission, 'verify_plan', return_value=(self.plan, self.sha))
        verify.start()
        self.addCleanup(verify.stop)
        self.phase = 'fresh1/P0'

    def receipt(self, stage, **changes):
        target = self.root / f'{stage}-review.json'
        value = {'kind': 'root-reviewed-alex-openjev4b-native-p0-stage-v1',
                 'approved': True, 'phase': self.phase, 'stage': stage,
                 'plan_sha256': self.sha,
                 'controller_sha256': admission.file_hash(admission.__file__),
                 'artifact_sha256': 'asset-sha', 'reference_labels_read': False}
        value.update(changes)
        target.write_text(admission.canonical(value))
        return target

    def run_smoke(self, backend=None):
        backend = backend or ModelDouble()
        with mock.patch.object(admission, 'load_backend', return_value=backend):
            result = admission.run_stage(self.plan, self.sha, self.phase,
                                         'smoke', self.receipt('smoke'))
        return backend, result

    def test_native_14_hypothesis_identity_and_max_entailment(self):
        self.assertEqual(len(self.requests), 60)
        self.assertEqual(len(self.requests[0]['nli_inputs']), 14)
        self.assertTrue(all(0 < x['input_tokens'] <= 4096
                            for request in self.requests for x in request['nli_inputs']))
        probabilities = [[0.2, 0.7, 0.1] for _ in range(14)]
        probabilities[3] = [0.01, 0.98, 0.01]
        projected = admission.project_probabilities(probabilities)
        self.assertEqual(projected['sentiment'], 'neutral')
        self.assertEqual(projected['follow_up_needed'], 'yes')
        self.assertEqual(self.plan['disposition'],
                         'fresh_matched_three_historical_observational')

    def test_wrong_receipt_denies_before_model_load_or_claim(self):
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaisesRegex(ValueError, 'root-reviewed'):
                admission.run_stage(self.plan, self.sha, self.phase, 'smoke',
                                    self.receipt('smoke', plan_sha256='wrong'))
            loader.assert_not_called()
        self.assertFalse((admission.phase_path(self.phase) / 'smoke.claim.json').exists())

    def test_raw_is_durable_before_projection_and_replay_denied(self):
        model = ModelDouble()
        original = admission.project_probabilities
        observed = []

        def projected(values):
            raw = admission.phase_path(self.phase) / 'smoke.raw.jsonl'
            observed.append(len(admission.read_jsonl(raw)))
            return original(values)

        with mock.patch.object(admission, 'load_backend', return_value=model), \
                mock.patch.object(admission, 'project_probabilities', side_effect=projected):
            admission.run_stage(self.plan, self.sha, self.phase, 'smoke', self.receipt('smoke'))
        self.assertEqual(observed[:3], [1, 2, 3])
        self.assertEqual(model.calls, 3)
        folder = admission.phase_path(self.phase)
        self.assertEqual(admission.verify_output(self.plan, self.phase, 'smoke'),
                         admission.file_hash(folder / 'smoke.records.jsonl'))
        self.assertEqual([row['event'] for row in admission.read_jsonl(folder / 'smoke.journal.jsonl')],
                         ['phase_started'] + ['request_started', 'request_completed'] * 3
                         + ['phase_completed'])
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.sha, self.phase, 'smoke', self.receipt('smoke'))
            loader.assert_not_called()

    def test_started_failure_retains_unknown_without_replay(self):
        model = ModelDouble(failure=True)
        with mock.patch.object(admission, 'load_backend', return_value=model):
            with self.assertRaisesRegex(RuntimeError, 'retain started unknown'):
                admission.run_stage(self.plan, self.sha, self.phase, 'smoke', self.receipt('smoke'))
        folder = admission.phase_path(self.phase)
        events = admission.read_jsonl(folder / 'smoke.journal.jsonl')
        self.assertEqual([row['event'] for row in events],
                         ['phase_started', 'request_started', 'phase_stopped'])
        self.assertFalse((folder / 'smoke.completion.json').exists())
        self.assertEqual(model.calls, 1)
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.sha, self.phase, 'smoke', self.receipt('smoke'))
            loader.assert_not_called()

    def test_development_requires_inspected_valid_smoke(self):
        self.run_smoke()
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaises((FileNotFoundError, ValueError)):
                admission.run_stage(self.plan, self.sha, self.phase, 'development',
                                    self.receipt('development'))
            loader.assert_not_called()
        folder = admission.phase_path(self.phase)
        inspection = folder / 'smoke-inspection.json'
        inspection.write_text(admission.canonical({
            'phase': self.phase, 'plan_sha256': self.sha,
            'smoke_records_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'inspected_ids': ['DEV-001', 'DEV-002', 'DEV-003'], 'approved': True}))
        receipt = self.receipt('development', smoke_inspection_sha256=admission.file_hash(inspection))
        with mock.patch.object(admission, 'load_backend', return_value=ModelDouble()):
            admission.run_stage(self.plan, self.sha, self.phase, 'development', receipt)
        self.assertEqual(len(admission.read_jsonl(folder / 'development.records.jsonl')), 60)

    def test_predecessor_and_native_identity_failure_before_inference(self):
        model = ModelDouble()
        self.phase = 'fresh2/P0'
        with mock.patch.object(admission, 'load_backend', return_value=model):
            with self.assertRaises(FileNotFoundError):
                admission.run_stage(self.plan, self.sha, self.phase, 'smoke', self.receipt('smoke'))
        self.assertEqual(model.calls, 0)
        self.phase = 'fresh1/P0'
        changed = copy.deepcopy(self.plan)
        changed['requests'][0]['nli_inputs'][0]['input_tokens'] += 1
        with mock.patch.object(admission, 'verify_plan', return_value=(changed, self.sha)), \
                mock.patch.object(admission, 'load_backend', return_value=model):
            with self.assertRaisesRegex(ValueError, 'native NLI input/token identity'):
                admission.run_stage(changed, self.sha, self.phase, 'smoke', self.receipt('smoke'))
        self.assertEqual(model.calls, 0)
        folder = admission.phase_path(self.phase)
        self.assertTrue((folder / 'smoke.claim.json').exists())
        self.assertEqual([r['event'] for r in admission.read_jsonl(folder / 'smoke.journal.jsonl')],
                         ['phase_started'])

    def test_artifact_manifest_requires_content_hash_not_size_only(self):
        root = self.root / 'model'
        folder = root / admission.MODEL.name
        folder.mkdir(parents=True)
        filenames = [str(Path(admission.MODEL.name) / n) for n in (
            'chat_template.jinja', 'config.json', 'model.safetensors',
            'tokenizer.json', 'tokenizer_config.json', 'train_result.json')]
        (root / 'modeling_openjev.py').write_bytes(b'fixture')
        siblings = []
        for name in filenames:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'fixture')
            blob = hashlib.sha1(b'blob 7\0fixture').hexdigest()
            siblings.append({'rfilename': name, 'size': 7, 'blobId': blob})
        manifest = {'repo': 'AlexWortega/openjev', 'sha': admission.REVISION,
                    'siblings': siblings}
        staged = self.root / 'staged-manifest.json'
        staged.write_text(json.dumps(manifest))
        with mock.patch.object(admission, 'MODEL_ROOT', root), \
                mock.patch.object(admission, 'MODEL', folder), \
                mock.patch.object(admission, 'STAGED_MANIFEST', staged), \
                mock.patch.object(admission, 'MODEL_SOURCE_SHA', hashlib.sha256(b'fixture').hexdigest()):
            admission.verify_assets()
            (folder / 'tokenizer.json').write_bytes(b'fixturE')
            with self.assertRaisesRegex(ValueError, 'Git asset differs'):
                admission.verify_assets()

    def test_historical_split_preserves_possible_dev046_attempt(self):
        directory = admission.HISTORY
        complete = admission.read_jsonl(directory / 'development-complete.jsonl')
        requests = []
        for record in complete:
            requests.append({'id': record['id'],
                             'input_sha256': record['input_sha256'],
                             'request_sha256': record['request_sha256'],
                             'nli_inputs': [{'input_tokens': value}
                                            for value in record['metadata']['input_tokens']]})
        history = admission.historical_parity(admission.ROOT, requests,
                                               complete[0]['runtime_versions'],
                                               'Premise: {premise}\nHypothesis: {hypothesis}')
        self.assertFalse(history['eligible_as_fresh_pass1'])
        self.assertEqual(history['unknown_attempt'],
                         {'id': 'DEV-046', 'status': 'possibly_started_outcome_unknown'})
        with mock.patch.dict(admission.HISTORICAL_FILES,
                             {'development-resume-2026-09-24.jsonl': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'evidence differs'):
                admission.historical_parity(admission.ROOT, requests,
                                            complete[0]['runtime_versions'],
                                            'Premise: {premise}\nHypothesis: {hypothesis}')


if __name__ == '__main__': unittest.main()
