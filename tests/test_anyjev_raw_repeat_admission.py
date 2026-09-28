"""Offline AnyJev raw repeat admission checks; no model is loaded in tests."""
import copy
import fcntl
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anyjev_raw_repeat_admission as admission


class FakeResult:
    def __init__(self, raw):
        self.raw = raw

    def to_dict(self):
        return copy.deepcopy(self.raw)

    def __iter__(self):
        return iter(SimpleNamespace(question=SimpleNamespace(id=key), diagnostics={})
                    for key in admission.KEYS)


class FakeDecider:
    def __init__(self, backend, source_by_feedback):
        self.backend = backend
        self.source_by_feedback = source_by_feedback
        self.stats = {'backend_calls': 1, 'flat_prompts': 4, 'shared_groups': 0,
                      'shared_prompts': 0, 'adaptive_items': 0, 'adaptive_shifts_total': 0}

    def decide(self, state, questions, level):
        self.backend.observed_signatures = self.backend.expected_signatures
        self.backend.prompt_token_counts = [x['input_tokens'] for x in self.backend.expected_signatures]
        return FakeResult(self.source_by_feedback[state['feedback']])


class AnyJevRawRepeatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (Path(sys.executable).resolve() != admission.PYTHON.resolve()
                or not admission.MODEL.is_dir() or not admission.SOURCE.is_dir()):
            raise unittest.SkipTest('Pinned local specialist Python/source/assets required; no downloads or model calls')
        cls.plan = admission.expected_plan()
        cls.rows, cls.policy = admission.source_rows()
        cls.historical = admission.read_jsonl(admission.HISTORY / 'smoke.jsonl')
        cls.historical_development = admission.read_jsonl(admission.HISTORY / 'development.jsonl')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.phase = self.plan['schedule'][0]
        self.path_patch = mock.patch.object(admission, 'PLAN_PATH', self.root / 'manifest.json')
        self.lock_patch = mock.patch.object(admission, 'HOST_LOCK', self.root / 'host.lock')
        self.path_patch.start(); self.lock_patch.start()
        self.addCleanup(self.path_patch.stop); self.addCleanup(self.lock_patch.stop)
        admission.PLAN_PATH.write_text(admission.canonical(self.plan))
        self.plan_sha = admission.file_hash(admission.PLAN_PATH)
        self.verify_patch = mock.patch.object(admission, 'verify_plan', return_value=(self.plan, self.plan_sha))
        self.verify_patch.start(); self.addCleanup(self.verify_patch.stop)

    def receipt(self, stage, **overrides):
        path = self.root / f'{stage}-receipt.json'
        value = {'kind': 'root-reviewed-anyjev-raw-native-p0-stage-v1',
                 'approved': True, 'phase': self.phase, 'stage': stage,
                 'plan_sha256': self.plan_sha}
        value.update(overrides)
        path.write_text(admission.canonical(value))
        return path

    def fake_model(self, *, failure=False, invalid=False):
        backend = SimpleNamespace(expected_signatures=None, observed_signatures=None,
                                  prompt_token_counts=[])
        raw = [copy.deepcopy(row['raw_response']) for row in self.historical_development]
        if invalid:
            first = raw[0]['questions']['sentiment']['distribution']
            first[next(iter(first))] = -1.0
        lookup = {row['feedback']: item for row, item in zip(self.rows, raw)}
        fake = FakeDecider(backend, lookup)
        if failure:
            fake.decide = mock.Mock(side_effect=RuntimeError('synthetic failure'))
        return mock.patch.multiple(admission,
            load_backend=mock.DEFAULT, make_decider=mock.DEFAULT), backend, fake

    def run_smoke(self, *, failure=False, invalid=False):
        patches, backend, fake = self.fake_model(failure=failure, invalid=invalid)
        with patches as functions:
            functions['load_backend'].return_value = (backend, object(), [])
            functions['make_decider'].return_value = fake
            return admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))

    def test_historical_parity_and_exact_native_request_identity(self):
        self.assertEqual(self.plan['schedule'], ['repeat2/P0', 'repeat3/P0'])
        self.assertEqual(len(self.plan['requests']), 60)
        self.assertTrue(self.plan['historical']['eligible_as_pass1'])
        self.assertFalse(self.plan['reference_labels_used'])
        self.assertEqual(self.plan['historical']['development_sha256'],
            'b1a1291e315dfd34312363fb5198d64b4f248f13f979a32240ac3ba19327d528')
        self.assertEqual(self.plan['historical']['runner_sha256'],
            self.plan['source_sha256'][str(admission.ROOT / 'scripts/anyjev_benchmark.py')])
        self.assertEqual(self.plan['requests'][0]['native_decisions'][0]['answer_token_ids'],
                         [32, 33, 34, 35, 36])
        self.assertEqual([x['input_tokens'] for x in self.plan['requests'][0]['native_decisions']],
                         self.historical[0]['prompt_token_counts'])
        self.assertEqual(set(self.plan['asset_sha256']),
                         {x['rfilename'] for x in admission.read_json(admission.MODEL / 'download-manifest.json')['siblings']})

    def test_history_rejects_normal_prompt_or_control_drift(self):
        changed = copy.deepcopy(self.plan['requests'])
        changed[0]['native_decisions'][0]['input_tokens'] += 1
        with self.assertRaisesRegex(ValueError, 'native parity'):
            admission.check_history(admission.ROOT, self.rows, self.policy, changed,
                self.plan['runtime']['packages'], admission.read_json(admission.MODEL / 'download-manifest.json'))
        specs = admission.question_specs(self.policy)
        bad = copy.deepcopy(self.historical[0]['raw_response'])
        bad['questions']['sentiment']['distribution']['unexpected'] = 0.0
        with self.assertRaisesRegex(ValueError, 'option identity'):
            admission.project_raw(bad, specs)

    def test_stage_receipt_precedes_model_load(self):
        patches, backend, fake = self.fake_model()
        with patches as functions:
            with self.assertRaisesRegex(ValueError, 'root-reviewed'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke',
                    self.receipt('smoke', plan_sha256='0' * 64))
            functions['load_backend'].assert_not_called()
        self.assertFalse((admission.phase_path(self.phase) / 'smoke.claim.json').exists())

    def test_durable_raw_journal_closure_and_no_replay(self):
        self.run_smoke()
        folder = admission.phase_path(self.phase)
        self.assertEqual(admission.verify_output(self.plan, self.phase, 'smoke'),
                         admission.file_hash(folder / 'smoke.records.jsonl'))
        self.assertEqual(len(admission.read_jsonl(folder / 'smoke.raw.jsonl')), 3)
        self.assertEqual([x['event'] for x in admission.read_jsonl(folder / 'smoke.journal.jsonl')],
            ['phase_started', 'request_started', 'request_completed',
             'request_started', 'request_completed', 'request_started', 'request_completed',
             'phase_completed'])
        patches, _, _ = self.fake_model()
        with patches as functions:
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
            functions['load_backend'].assert_not_called()

    def test_started_failure_preserves_unknown_and_denies_replay(self):
        with self.assertRaisesRegex(RuntimeError, 'retain started unknown'):
            self.run_smoke(failure=True)
        folder = admission.phase_path(self.phase)
        self.assertTrue((folder / 'smoke.claim.json').exists())
        self.assertEqual([x['event'] for x in admission.read_jsonl(folder / 'smoke.journal.jsonl')],
            ['phase_started', 'request_started', 'phase_stopped'])
        with self.assertRaises(FileExistsError): self.run_smoke()

    def test_invalid_smoke_retained_but_development_denied(self):
        self.run_smoke(invalid=True)
        folder = admission.phase_path(self.phase)
        self.assertEqual(admission.read_jsonl(folder / 'smoke.records.jsonl')[0]['status'], 'invalid_output')
        inspection = folder / 'smoke-inspection.json'
        inspection.write_text(admission.canonical({'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'inspected_ids': [f'DEV-{i:03d}' for i in range(1, 4)], 'approved': True}))
        with self.assertRaisesRegex(ValueError, 'inspected successful smoke'):
            admission.check_receipt(self.plan, self.plan_sha, self.phase, 'development',
                self.receipt('development', smoke_inspection_sha256=admission.file_hash(inspection)))

    def test_inspected_smoke_admits_full_development_and_fences_repeat3(self):
        self.run_smoke()
        folder = admission.phase_path(self.phase)
        inspection = folder / 'smoke-inspection.json'
        inspection.write_text(admission.canonical({'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'inspected_ids': [f'DEV-{i:03d}' for i in range(1, 4)], 'approved': True}))
        receipt = self.receipt('development', smoke_inspection_sha256=admission.file_hash(inspection))
        patches, backend, fake = self.fake_model()
        with patches as functions:
            functions['load_backend'].return_value = (backend, object(), [])
            functions['make_decider'].return_value = fake
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'development', receipt)
        self.assertEqual(len(admission.read_jsonl(folder / 'development.records.jsonl')), 60)
        admission.check_predecessors(self.plan, self.plan_sha, 'repeat3/P0')
        completion = admission.read_json(folder / 'development.completion.json')
        completion['output_sha256'] = '0' * 64
        (folder / 'development.completion.json').write_text(admission.canonical(completion))
        with self.assertRaisesRegex(ValueError, 'lacks verified development closure'):
            admission.check_predecessors(self.plan, self.plan_sha, 'repeat3/P0')

    def test_raw_identity_tamper_and_predecessor_gate(self):
        self.run_smoke()
        folder = admission.phase_path(self.phase)
        captures = admission.read_jsonl(folder / 'smoke.raw.jsonl')
        captures[0]['native_decisions'][0]['answer_token_ids'] = [0]
        (folder / 'smoke.raw.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in captures))
        with self.assertRaisesRegex(ValueError, 'output binding failed'):
            admission.verify_output(self.plan, self.phase, 'smoke')
        with self.assertRaises((FileNotFoundError, ValueError)):
            admission.check_predecessors(self.plan, self.plan_sha, 'repeat3/P0')

    def test_common_os_lock_blocks_concurrent_stage(self):
        holder = subprocess.Popen([sys.executable, '-c',
            'import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX); print("READY",flush=True); sys.stdin.read(1)',
            str(admission.HOST_LOCK)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'READY')
            with self.assertRaisesRegex(RuntimeError, 'host lock'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
            self.assertFalse((admission.phase_path(self.phase) / 'smoke.claim.json').exists())
        finally:
            holder.stdin.write('x'); holder.stdin.flush(); holder.wait(timeout=10)
            holder.stdin.close(); holder.stdout.close()


if __name__ == '__main__': unittest.main()
