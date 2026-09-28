"""Offline SemIf repeat admission guards. These tests never load weights."""
import copy
import fcntl
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semif_repeat_admission as admission


class SemIfRepeatAdmissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (Path(sys.executable).resolve() != admission.PYTHON.resolve()
                or not admission.MODEL.is_dir()
                or not admission.SOURCE.is_dir()):
            raise unittest.SkipTest(
                'SemIf admission integration checks require the pinned local specialist '
                'interpreter, source checkout and model assets; they never download models.')
        cls.plan = admission.expected_plan()

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
        self.historical = admission.read_jsonl(admission.ROOT / admission.HISTORY['semif-direct'] / 'smoke.jsonl')
        self.metadata = self.historical[0]['metadata']

    def receipt(self, stage, **overrides):
        path = self.root / f'{stage}-receipt.json'
        value = {'kind': 'root-reviewed-semif-native-p0-stage-v1', 'approved': True,
                 'phase': self.phase, 'stage': stage, 'plan_sha256': self.plan_sha}
        value.update(overrides)
        path.write_text(admission.canonical(value))
        return path

    def fake_backend(self):
        from semif_phase1 import mlx_backend
        return mock.patch.object(mlx_backend, 'load_model',
            return_value=(object(), object(), self.metadata))

    def fake_scores(self, *, invalid_first=False):
        rows = [copy.deepcopy(row['raw_response']) for row in self.historical]
        if invalid_first:
            rows[0]['decisions'][0]['probabilities'] = [0.0] * 5
        return mock.patch.object(admission, 'score_raw', side_effect=rows)

    def run_smoke(self, *, invalid_first=False):
        with mock.patch.object(admission, 'check_laya_closed', return_value=self.plan['laya_plan_sha256']), \
             self.fake_backend(), self.fake_scores(invalid_first=invalid_first):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))

    def test_frozen_history_modes_assets_and_exact_order(self):
        self.assertEqual(len(self.plan['configurations']), 3)
        self.assertEqual(self.plan['schedule'],
            [f'{name}/repeat{repeat}/P0' for repeat in (2, 3) for name in admission.MODES])
        self.assertEqual([x['id'] for x in self.plan['requests']],
                         [f'DEV-{i:03d}' for i in range(1, 61)])
        self.assertFalse(self.plan['reference_labels_used'])
        self.assertEqual(len(self.plan['configurations']['semif-direct']['assets_sha256']), 11)
        for name, config in self.plan['configurations'].items():
            self.assertEqual(config['historical']['eligible_as_pass1'], True, name)
            self.assertEqual(config['historical']['runtime_versions'], self.plan['runtime']['packages'])
            self.assertEqual(len(config['native_requests']), 60)
            self.assertEqual(len(config['native_requests'][0]['decisions']), 4)
        self.assertEqual(admission.verify_plan()[1], self.plan_sha)

    def test_source_asset_and_manifest_drift_fail_closed(self):
        altered = copy.deepcopy(self.plan)
        altered['requests'][0]['request_sha256'] = '0' * 64
        admission.PLAN_PATH.write_text(admission.canonical(altered))
        with mock.patch.object(admission, 'expected_plan', return_value=self.plan):
            with self.assertRaisesRegex(ValueError, 'Frozen SemIf plan differs'):
                admission.verify_plan()
        real_hash = admission.file_hash
        def drift(path):
            if Path(path).name == 'chat_template.jinja': return 'f' * 64
            return real_hash(path)
        with mock.patch.object(admission, 'file_hash', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'SemIf artifact changed'):
                admission.expected_plan()

    def test_exact_mode_scoring_calls(self):
        feedback = 'A fictional comment'; policy = 'A fixed policy'
        direct = mock.Mock()
        direct.score.side_effect = [{'id': key} for key in admission.KEYS]
        self.assertEqual(len(admission.score_raw(direct, object(), object(), {}, 'direct', feedback, policy)['decisions']), 4)
        self.assertEqual(direct.score.call_count, 4)
        serial = mock.Mock()
        serial.SerialPrefixScorer.return_value.score.side_effect = [{'id': key} for key in admission.KEYS]
        self.assertEqual(len(admission.score_raw(serial, object(), object(), {}, 'serial', feedback, policy)['decisions']), 4)
        self.assertEqual(serial.SerialPrefixScorer.call_count, 1)
        shared = mock.Mock()
        shared.score_shared.return_value = ([{'id': key} for key in admission.KEYS], {'timing': 1})
        self.assertEqual(len(admission.score_raw(shared, object(), object(), {}, 'shared', feedback, policy)['decisions']), 4)
        self.assertEqual(shared.score_shared.call_count, 1)

    def test_stage_receipt_and_laya_closure_precede_model_load(self):
        with mock.patch.object(admission, 'check_laya_closed', side_effect=ValueError('Laya incomplete')), \
             self.fake_backend() as load:
            with self.assertRaisesRegex(ValueError, 'Laya incomplete'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
            load.assert_not_called()
        self.assertFalse((admission.phase_path(self.phase) / 'smoke.claim.json').exists())
        with mock.patch.object(admission, 'check_laya_closed', return_value=self.plan['laya_plan_sha256']), \
             self.fake_backend() as load:
            with self.assertRaisesRegex(ValueError, 'Missing exact root-reviewed'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke',
                                    self.receipt('smoke', plan_sha256='0' * 64))
            load.assert_not_called()

    def test_smoke_raw_is_durable_and_replay_refused(self):
        self.run_smoke()
        folder = admission.phase_path(self.phase)
        self.assertEqual(admission.verify_output(self.plan, self.phase, 'smoke'),
                         admission.file_hash(folder / 'smoke.records.jsonl'))
        self.assertEqual(len(admission.read_jsonl(folder / 'smoke.raw.jsonl')), 3)
        self.assertEqual([x['event'] for x in admission.read_jsonl(folder / 'smoke.journal.jsonl')].count('request_started'), 3)
        with mock.patch.object(admission, 'check_laya_closed', return_value=self.plan['laya_plan_sha256']), \
             self.fake_backend() as load:
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
            load.assert_not_called()

    def test_changed_native_token_request_rejected_even_with_updated_raw_hash(self):
        self.run_smoke()
        folder = admission.phase_path(self.phase)
        raw_path = folder / 'smoke.raw.jsonl'
        records_path = folder / 'smoke.records.jsonl'
        raw = admission.read_jsonl(raw_path)
        records = admission.read_jsonl(records_path)
        raw[0]['raw_response']['decisions'][0]['prompt_sha256'] = '0' * 64
        records[0]['raw_sha256'] = admission.digest(json.dumps(raw[0]['raw_response'], sort_keys=True))
        raw_path.write_text(''.join(json.dumps(x) + '\n' for x in raw))
        records_path.write_text(''.join(json.dumps(x) + '\n' for x in records))
        with self.assertRaisesRegex(ValueError, 'output binding failed'):
            admission.verify_output(self.plan, self.phase, 'smoke')

    def test_smoke_invalid_retained_but_development_denied(self):
        self.run_smoke(invalid_first=True)
        folder = admission.phase_path(self.phase)
        records = admission.read_jsonl(folder / 'smoke.records.jsonl')
        self.assertEqual([x['status'] for x in records], ['invalid_output', 'ok', 'ok'])
        self.assertEqual(len(admission.read_jsonl(folder / 'smoke.raw.jsonl')), 3)
        inspection = folder / 'smoke-inspection.json'
        inspection.write_text(admission.canonical({'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_sha256': admission.file_hash(folder / 'smoke.records.jsonl'),
            'inspected_ids': [f'DEV-{i:03d}' for i in range(1, 4)], 'approved': True}))
        with self.assertRaisesRegex(ValueError, 'inspected smoke'):
            admission.check_receipt(self.plan_sha, self.phase, 'development',
                self.receipt('development', smoke_inspection_sha256=admission.file_hash(inspection)))

    def test_started_failure_retained_and_no_replay(self):
        with mock.patch.object(admission, 'check_laya_closed', return_value=self.plan['laya_plan_sha256']), \
             self.fake_backend(), mock.patch.object(admission, 'score_raw', side_effect=RuntimeError('fake failure')):
            with self.assertRaisesRegex(RuntimeError, 'retain started unknown'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
        folder = admission.phase_path(self.phase)
        self.assertTrue((folder / 'smoke.claim.json').exists())
        self.assertEqual([x['event'] for x in admission.read_jsonl(folder / 'smoke.journal.jsonl')][-2:],
                         ['request_started', 'phase_stopped'])
        with mock.patch.object(admission, 'check_laya_closed', return_value=self.plan['laya_plan_sha256']), \
             self.fake_backend() as load:
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
            load.assert_not_called()

    def test_common_os_lock_rejects_concurrent_dispatch(self):
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
