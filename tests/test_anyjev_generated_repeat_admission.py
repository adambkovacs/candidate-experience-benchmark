"""Generated-control admission tests with fake tokenizer/model; no weights or network."""
import contextlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anyjev_generated_repeat_admission as admission


VALID = json.dumps({'sentiment': 'positive', 'follow_up_needed': 'no',
                    'serious_concern_reported': 'no', 'testimonial_potential': 'yes'})
FENCED = '```json\n' + VALID + '\n```'


class Row:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class Tensor:
    def __init__(self, values):
        self.values = values
        self.shape = (1, len(values))

    def to(self, device):
        return self

    def __getitem__(self, index):
        if isinstance(index, tuple):
            return Row(self.values[index[1]])
        return Row(self.values)


class Tokenizer:
    pad_token_id = None
    eos_token_id = 0

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, enable_thinking):
        assert tokenize is False and add_generation_prompt is True and enable_thinking is False
        return json.dumps(messages, sort_keys=True) + '<assistant>'

    def encode(self, prompt, *, add_special_tokens):
        assert add_special_tokens is False
        return [sum(map(ord, prompt[i:i + 8])) % 255 + 1
                for i in range(0, len(prompt), 8)]

    def __call__(self, prompt, *, return_tensors, add_special_tokens):
        assert return_tensors == 'pt'
        return {'input_ids': Tensor(self.encode(prompt, add_special_tokens=add_special_tokens))}

    def decode(self, ids, *, skip_special_tokens):
        assert skip_special_tokens is True
        return ''.join(chr(value) for value in ids if value != 0)


class Model:
    generation_config = types.SimpleNamespace(eos_token_id=0)

    def __init__(self, text=FENCED, fail=False):
        self.text = text
        self.fail = fail
        self.calls = 0

    def generate(self, *, input_ids, do_sample, max_new_tokens, pad_token_id):
        assert do_sample is False and max_new_tokens == 4096 and pad_token_id == 0
        self.calls += 1
        if self.fail:
            raise RuntimeError('synthetic model interruption')
        return Tensor(input_ids.values + [ord(x) for x in self.text] + [0])


class GeneratedAdmissionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.tok = Tokenizer()
        self.rows, self.policy = admission.shared.source_rows()
        self.requests = admission.request_signatures(self.rows, self.policy, self.tok)
        self.plan = {'schedule': list(admission.SCHEDULE), 'requests': self.requests,
                     'stage_inputs': {'smoke': {'limit': 3}, 'development': {'limit': 60}},
                     'model_id': admission.MODEL_ID, 'artifact_revision': admission.REVISION,
                     'asset_sha256': {'model.safetensors': 'weights-sha'}}
        self.plan_sha = 'plan-sha'
        self.phase = 'fresh1/P0'
        for name, value in (('PLAN_PATH', self.root / 'manifest.json'),
                            ('HOST_LOCK', self.root / 'host.lock')):
            patcher = mock.patch.object(admission, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        verify = mock.patch.object(admission, 'verify_plan',
                                   return_value=(self.plan, self.plan_sha))
        verify.start()
        self.addCleanup(verify.stop)
        module = types.ModuleType('transformers')
        module.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda *a, **k: self.tok)
        module_patch = mock.patch.dict(sys.modules, {'transformers': module})
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.torch = types.SimpleNamespace(inference_mode=contextlib.nullcontext)

    def receipt(self, stage, **extra):
        path = self.root / f'{stage}-receipt.json'
        value = {'kind': 'root-reviewed-anyjev-generated-stage-v1',
                 'approved': True, 'phase': self.phase, 'stage': stage,
                 'plan_sha256': self.plan_sha,
                 'controller_sha256': admission.file_hash(admission.__file__),
                 'artifact_sha256': 'weights-sha', 'reference_labels_read': False}
        value.update(extra)
        path.write_text(admission.shared.canonical(value))
        return path

    def run_smoke(self, model=None):
        model = model or Model()
        with mock.patch.object(admission, 'load_backend',
                               return_value=(self.tok, model, self.torch)):
            admission.run_stage(self.plan, self.plan_sha, self.phase,
                                'smoke', self.receipt('smoke'))
        return model

    def inspected_smoke(self):
        folder = admission.phase_path(self.phase)
        rows = admission.read_jsonl(folder / 'smoke.records.jsonl')
        inspection = folder / 'smoke-inspection.json'
        inspection.write_text(admission.shared.canonical({
            'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_records_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'approved': True,
            'records': [{'id': row['id'], 'status': row['status'],
                         'prediction': row['prediction'], 'raw_sha256': row['raw_sha256'],
                         'accepted_unchanged': True, 'failure_class': 'intrinsic_schema',
                         'inspection_reason': 'Exact saved fenced response retained'}
                        for row in rows]}))
        return self.receipt('development',
                            smoke_inspection_sha256=admission.file_hash(inspection))

    def test_schedule_full_rotation_and_frozen_request_identity(self):
        self.assertEqual(len(admission.SCHEDULE), 9)
        self.assertEqual(admission.SCHEDULE[:3], ('fresh1/P0', 'fresh1/P1', 'fresh1/P2'))
        self.assertEqual(admission.SCHEDULE[3:6], ('fresh2/P1', 'fresh2/P2', 'fresh2/P0'))
        self.assertEqual(admission.SCHEDULE[6:], ('fresh3/P2', 'fresh3/P0', 'fresh3/P1'))
        self.assertEqual({key: len(value) for key, value in self.requests.items()},
                         {'P0': 60, 'P1': 60, 'P2': 60})
        self.assertEqual(len({self.requests[key][0]['messages_sha256']
                              for key in ('P0', 'P1', 'P2')}), 3)

    def test_wrong_receipt_denied_before_claim_or_model_load(self):
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaisesRegex(ValueError, 'root-reviewed'):
                admission.run_stage(self.plan, self.plan_sha, self.phase,
                                    'smoke', self.receipt('smoke', plan_sha256='wrong'))
            loader.assert_not_called()
        self.assertFalse((admission.phase_path(self.phase) / 'smoke.claim.json').exists())

    def test_fenced_raw_saved_before_strict_projection_and_never_replayed(self):
        original = admission.parse_generated
        seen = []
        def parser(text, ended):
            seen.append(len(admission.read_jsonl(admission.phase_path(self.phase) /
                                                 'smoke.raw.jsonl')))
            return original(text, ended)
        model = Model(FENCED)
        with mock.patch.object(admission, 'parse_generated', side_effect=parser), \
                mock.patch.object(admission, 'load_backend',
                                  return_value=(self.tok, model, self.torch)):
            admission.run_stage(self.plan, self.plan_sha, self.phase,
                                'smoke', self.receipt('smoke'))
        self.assertEqual(seen[:3], [1, 2, 3])
        folder = admission.phase_path(self.phase)
        self.assertEqual(model.calls, 3)
        self.assertEqual([r['status'] for r in admission.read_jsonl(folder / 'smoke.records.jsonl')],
                         ['invalid_output'] * 3)
        self.assertTrue(all(r['raw_response'].startswith('```json')
                            for r in admission.read_jsonl(folder / 'smoke.raw.jsonl')))
        with self.assertRaises(FileExistsError):
            self.run_smoke()

    def test_started_unknown_stops_without_replay(self):
        model = Model(fail=True)
        with mock.patch.object(admission, 'load_backend',
                               return_value=(self.tok, model, self.torch)):
            with self.assertRaisesRegex(RuntimeError, 'retain started unknown'):
                admission.run_stage(self.plan, self.plan_sha, self.phase,
                                    'smoke', self.receipt('smoke'))
        folder = admission.phase_path(self.phase)
        self.assertEqual([r['event'] for r in admission.read_jsonl(folder / 'smoke.journal.jsonl')],
                         ['phase_started', 'request_started', 'phase_stopped'])
        self.assertFalse((folder / 'smoke.completion.json').exists())
        with self.assertRaises(FileExistsError):
            self.run_smoke()

    def test_invalid_smoke_needs_explicit_inspection_then_development(self):
        self.run_smoke()
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaises((FileNotFoundError, ValueError)):
                admission.run_stage(self.plan, self.plan_sha, self.phase,
                                    'development', self.receipt('development'))
            loader.assert_not_called()
        receipt = self.inspected_smoke()
        with mock.patch.object(admission, 'load_backend',
                               return_value=(self.tok, Model(VALID), self.torch)):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'development', receipt)
        folder = admission.phase_path(self.phase)
        self.assertEqual(len(admission.read_jsonl(folder / 'development.records.jsonl')), 60)
        self.assertTrue(all(r['status'] == 'ok'
                            for r in admission.read_jsonl(folder / 'development.records.jsonl')))

    def test_predecessor_and_live_token_mismatch_fail_closed(self):
        self.phase = 'fresh1/P1'
        with mock.patch.object(admission, 'load_backend') as loader:
            with self.assertRaises(FileNotFoundError):
                admission.run_stage(self.plan, self.plan_sha, self.phase,
                                    'smoke', self.receipt('smoke'))
            loader.assert_not_called()
        self.phase = 'fresh1/P0'
        changed = copy.deepcopy(self.plan)
        changed['requests']['P0'][0]['input_ids_sha256'] = 'wrong'
        with mock.patch.object(admission, 'verify_plan', return_value=(changed, self.plan_sha)), \
                mock.patch.object(admission, 'load_backend',
                                  return_value=(self.tok, Model(), self.torch)):
            with self.assertRaisesRegex(ValueError, 'request identity differs'):
                admission.run_stage(changed, self.plan_sha, self.phase,
                                    'smoke', self.receipt('smoke'))
        folder = admission.phase_path(self.phase)
        self.assertTrue((folder / 'smoke.claim.json').exists())
        self.assertEqual([r['event'] for r in admission.read_jsonl(folder / 'smoke.journal.jsonl')],
                         ['phase_started'])


if __name__ == '__main__':
    unittest.main()
