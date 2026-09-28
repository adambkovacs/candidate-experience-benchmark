"""Fake-only stage checks for the SemIf generated fresh-three candidate."""
import copy
import fcntl
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semif_generated_repeat_admission as admission


class SemIfGeneratedAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (Path(sys.executable).resolve() != admission.PYTHON.resolve()
                or not admission.MODEL.is_dir() or not admission.PLAN_PATH.is_file()):
            raise unittest.SkipTest('Pinned local specialist interpreter, tokenizer and candidate plan required; no weights are loaded')
        from transformers import AutoTokenizer
        cls.tokenizer = AutoTokenizer.from_pretrained(str(admission.MODEL), local_files_only=True)
        cls.plan = admission.read_json(admission.PLAN_PATH)
        cls.metadata = admission.jsonl(admission.ROOT / admission._HISTORY['P0'])[0]['metadata']

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.phase = admission.SCHEDULE[0]
        self.path_patch = mock.patch.object(admission, 'PLAN_PATH', self.root / 'manifest.json')
        self.lock_patch = mock.patch.object(admission, 'HOST_LOCK', self.root / 'host.lock')
        self.path_patch.start(); self.lock_patch.start()
        self.addCleanup(self.path_patch.stop); self.addCleanup(self.lock_patch.stop)
        admission.PLAN_PATH.write_text(admission.canonical(self.plan))
        self.plan_sha = admission.file_hash(admission.PLAN_PATH)
        admission._STARTED_IN_PROCESS = False

    def receipt(self, stage, **changes):
        path = self.root / f'{stage}-receipt.json'
        value = {'kind': 'root-reviewed-semif-generated-fresh-stage-v1', 'approved': True,
                 'phase': self.phase, 'stage': stage, 'plan_sha256': self.plan_sha,
                 'controller_sha256': admission.file_hash(admission.__file__),
                 'reference_labels_read': False}
        value.update(changes)
        path.write_text(admission.canonical(value))
        return path

    def generator(self, stage='smoke', invalid_first=False, fail_first=False, length_first=False, incomplete_first=False):
        requests = self.plan['requests']['P0']
        counter = {'number': 0}
        def generate(_model, _tokenizer, _prompt, **_kwargs):
            index = counter['number']; counter['number'] += 1
            if fail_first and index == 0:
                yield types.SimpleNamespace(text='{', token=1, from_draft=False,
                    prompt_tokens=requests[index]['input_tokens'], generation_tokens=1,
                    finish_reason=None)
                raise RuntimeError('simulated interrupted local generation')
            content = 'not json' if invalid_first and index == 0 else json.dumps({
                'sentiment': 'neutral', 'follow_up_needed': 'no',
                'serious_concern_reported': 'no', 'testimonial_potential': 'no'})
            yield types.SimpleNamespace(text=content, token=2, from_draft=False,
                prompt_tokens=requests[index]['input_tokens'], generation_tokens=1,
                finish_reason=('length' if length_first and index == 0 else None if incomplete_first and index == 0 else 'stop'))
        return generate

    def run_fake(self, stage='smoke', **generator_options):
        with mock.patch('transformers.AutoTokenizer.from_pretrained', return_value=self.tokenizer):
            return admission.run_stage(self.plan, self.plan_sha, self.phase, stage,
                self.receipt(stage), load=lambda *_: (object(), self.tokenizer,
                    {k:v for k,v in self.metadata.items() if k not in ('enable_thinking','max_tokens','temperature')}),
                generate=self.generator(stage, **generator_options), sampler=lambda **_: object())

    def test_plan_is_fresh_nine_phase_and_keeps_old_unknown(self):
        self.assertEqual(self.plan['schedule'], admission.SCHEDULE)
        self.assertEqual(len(self.plan['schedule']), 9)
        self.assertEqual(len(self.plan['requests']['P0']), 60)
        self.assertEqual(self.plan['historical']['unknown_started_id'], 'DEV-033')
        self.assertFalse(self.plan['historical']['eligible_as_first_pass'])
        self.assertEqual((self.plan['historical']['saved_P2'],
                          self.plan['historical']['valid_P2'],
                          self.plan['historical']['intrinsic_invalid_P2']), (59, 57, 2))
        self.assertFalse(self.plan['reference_labels_read'])
        self.assertEqual(self.plan['same_weights_native_control']['artifact_revision'], admission.REVISION)
        for condition in ('P0', 'P1', 'P2'):
            self.assertEqual([r['id'] for r in self.plan['requests'][condition]],
                [f'DEV-{i:03d}' for i in range(1,61)])
            self.assertTrue(all(r['input_tokens'] <= 4096 for r in self.plan['requests'][condition]))

    def test_smoke_raw_stream_precedes_projection_and_no_replay(self):
        self.run_fake()
        folder = admission.phase_path(self.phase)
        self.assertEqual(len(admission.jsonl(folder / 'smoke.events.jsonl')), 3)
        self.assertEqual(len(admission.jsonl(folder / 'smoke.raw.jsonl')), 3)
        self.assertEqual([x['event'] for x in admission.jsonl(folder / 'smoke.journal.jsonl')].count('request_started'), 3)
        self.assertEqual(admission.verify_output(self.plan, self.phase, 'smoke'),
                         admission.file_hash(folder / 'smoke.records.jsonl'))
        admission._STARTED_IN_PROCESS = False
        with mock.patch('transformers.AutoTokenizer.from_pretrained', return_value=self.tokenizer):
            with self.assertRaisesRegex(FileExistsError, 'already attempted'):
                self.run_fake()

    def test_started_failure_retains_partial_stream_and_denies_replay(self):
        with self.assertRaisesRegex(RuntimeError, 'simulated interrupted'):
            self.run_fake(fail_first=True)
        folder = admission.phase_path(self.phase)
        self.assertTrue((folder / 'smoke.claim.json').is_file())
        self.assertEqual(len(admission.jsonl(folder / 'smoke.events.jsonl')), 1)
        self.assertFalse((folder / 'smoke.raw.jsonl').exists())
        self.assertEqual(admission.jsonl(folder / 'smoke.journal.jsonl')[-1]['started_outcome'], 'unknown_no_replay')
        admission._STARTED_IN_PROCESS = False
        with self.assertRaises(FileExistsError):
            self.run_fake()

    def test_known_length_is_invalid_but_incomplete_stream_stops(self):
        self.run_fake(length_first=True)
        folder = admission.phase_path(self.phase)
        self.assertEqual(admission.jsonl(folder / 'smoke.raw.jsonl')[0]['raw_response']['finish_reason'], 'length')
        self.assertEqual(admission.jsonl(folder / 'smoke.records.jsonl')[0]['status'], 'invalid_output')
        self.assertEqual(len(admission.jsonl(folder / 'smoke.records.jsonl')), 3)
        self.assertEqual(admission.verify_output(self.plan, self.phase, 'smoke'),
                         admission.file_hash(folder / 'smoke.records.jsonl'))
        admission._STARTED_IN_PROCESS = False
        with self.assertRaises(FileExistsError):
            self.run_fake()

    def test_incomplete_stream_saves_raw_and_stops_without_replay(self):
        with self.assertRaisesRegex(RuntimeError, 'no complete terminal'):
            self.run_fake(incomplete_first=True)
        folder = admission.phase_path(self.phase)
        raw = admission.jsonl(folder / 'smoke.raw.jsonl')
        self.assertEqual(len(raw), 1)
        self.assertIsNone(raw[0]['raw_response']['finish_reason'])
        self.assertFalse((folder / 'smoke.records.jsonl').exists())
        self.assertEqual(admission.jsonl(folder / 'smoke.journal.jsonl')[-1]['started_outcome'], 'raw_saved_no_replay')
        admission._STARTED_IN_PROCESS = False
        with self.assertRaises(FileExistsError):
            self.run_fake()

    def test_invalid_smoke_retained_but_development_requires_acceptance(self):
        self.run_fake(invalid_first=True)
        folder = admission.phase_path(self.phase)
        self.assertEqual(admission.jsonl(folder / 'smoke.records.jsonl')[0]['status'], 'invalid_output')
        inspection = {'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'inspected_ids': [f'DEV-{i:03d}' for i in range(1,4)],
            'approved': True, 'inspector': 'independent-reviewer'}
        path = folder / 'smoke-inspection.json'; path.write_text(admission.canonical(inspection))
        receipt = self.receipt('development', smoke_inspection_sha256=admission.file_hash(path))
        with self.assertRaisesRegex(ValueError, 'unchanged acceptance'):
            admission.check_receipt(self.plan, self.plan_sha, self.phase, 'development', receipt)
        inspection.update(accepted_unchanged_invalids=True, failure_class='intrinsic_schema',
                          inspection_reason='Raw first response is intrinsic invalid JSON, accepted without repair')
        path.write_text(admission.canonical(inspection))
        receipt = self.receipt('development', smoke_inspection_sha256=admission.file_hash(path))
        admission.check_receipt(self.plan, self.plan_sha, self.phase, 'development', receipt)

    def test_unreviewed_receipt_and_busy_gpu_lock_fail_before_load(self):
        loader = mock.Mock()
        with self.assertRaisesRegex(ValueError, 'Exact reviewed'):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke',
                self.receipt('smoke', plan_sha256='0'*64), load=loader)
        loader.assert_not_called()
        admission._STARTED_IN_PROCESS = False
        with admission.HOST_LOCK.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with self.assertRaisesRegex(RuntimeError, 'owns the GPU host'):
                    admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke',
                        self.receipt('smoke'), load=loader)
            finally: fcntl.flock(lock, fcntl.LOCK_UN)
        loader.assert_not_called()

    def test_development_requires_inspection_and_predecessor_closure(self):
        self.run_fake()
        folder = admission.phase_path(self.phase)
        with self.assertRaises(FileNotFoundError):
            admission.check_predecessors(self.plan, self.plan_sha, admission.SCHEDULE[1])
        admission._STARTED_IN_PROCESS = False
        with self.assertRaises((FileNotFoundError, ValueError)):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'development',
                self.receipt('development'), load=mock.Mock())
        inspection = {'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'inspected_ids': [f'DEV-{i:03d}' for i in range(1,4)],
            'approved': True, 'inspector': 'independent-reviewer'}
        path = folder / 'smoke-inspection.json'; path.write_text(admission.canonical(inspection))
        receipt = self.receipt('development', smoke_inspection_sha256=admission.file_hash(path))
        admission._STARTED_IN_PROCESS = False
        with mock.patch('transformers.AutoTokenizer.from_pretrained', return_value=self.tokenizer):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'development', receipt,
                load=lambda *_: (object(), self.tokenizer,
                    {k:v for k,v in self.metadata.items() if k not in ('enable_thinking','max_tokens','temperature')}),
                generate=self.generator('development'), sampler=lambda **_: object())
        self.assertEqual(len(admission.jsonl(folder / 'development.records.jsonl')), 60)
        admission.check_predecessors(self.plan, self.plan_sha, admission.SCHEDULE[1])

    def test_installed_generation_source_drift_blocks_before_load(self):
        target = next(path for path in self.plan['runtime']['current_source_hashes']
                      if Path(path).name == 'generate.py')
        actual_hash = admission.file_hash
        def changed(path):
            if str(path) == target:
                return '0' * 64
            return actual_hash(path)
        loader = mock.Mock()
        with mock.patch.object(admission, 'file_hash', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'runtime source changed'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke',
                    self.receipt('smoke'), load=loader)
        loader.assert_not_called()
        self.assertFalse((admission.phase_path(self.phase) / 'smoke.claim.json').exists())

    def test_tampered_raw_or_parser_mirror_rejected(self):
        self.run_fake()
        folder = admission.phase_path(self.phase)
        path = folder / 'smoke.raw.jsonl'
        rows = admission.jsonl(path)
        rows[0]['raw_response']['content'] = 'different'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'binding failed'):
            admission.verify_output(self.plan, self.phase, 'smoke')


if __name__ == '__main__': unittest.main()
