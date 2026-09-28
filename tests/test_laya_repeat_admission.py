import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import laya_repeat_admission as admission


class LayaRepeatAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.plan_sha = admission.verify_plan()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.phase = 'laya-english-expanded-cpu/repeat2/P0'
        self.patch = mock.patch.object(admission, 'PLAN_PATH', self.root / 'manifest.json')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root / 'manifest.json').write_text(admission.canonical(self.plan))

    def receipt(self, stage, **extra):
        path = self.root / (stage + '-receipt.json')
        path.write_text(admission.canonical({'kind': 'root-reviewed-laya-p0-stage-v1',
            'phase': self.phase, 'stage': stage, 'plan_sha256': self.plan_sha,
            'approved': True, **extra}))
        return path

    def source_output(self, stage, command):
        source = admission.ROOT / 'results/laya-english-expanded-cpu-2026-09-23' / (stage + '.jsonl')
        shutil.copyfile(source, Path(command[command.index('--output') + 1]))
        return types.SimpleNamespace(returncode=0)

    def test_frozen_manifest_binds_all_three_distinct_configs_and_sources(self):
        self.assertEqual(len(self.plan['configurations']), 3)
        self.assertEqual(len(self.plan['schedule']), 6)
        self.assertEqual([r['id'] for r in self.plan['requests']],
                         [f'DEV-{i:03d}' for i in range(1, 61)])
        self.assertEqual({c['historical']['runner_git_commit'] for c in self.plan['configurations'].values()},
                         {'91b646d', 'adc1fb8', 'e147bac'})
        self.assertFalse(self.plan['reference_labels_used'])
        self.assertEqual(self.plan['runtime']['hardware']['machine_model'], 'Mac16,5')
        self.assertEqual(self.plan['runtime']['hardware']['chip_type'], 'Apple M4 Max')
        self.assertEqual(self.plan['runtime']['hardware']['physical_memory'], '128 GB')
        self.assertTrue(all(c['historical']['runtime_matches_repeat']
                            for c in self.plan['configurations'].values()))
        self.assertEqual(admission.verify_plan()[1], self.plan_sha)

    def test_manifest_tamper_and_asset_drift_block_preflight(self):
        altered = json.loads((self.root / 'manifest.json').read_text())
        altered['requests'][0]['request_sha256'] = '0' * 64
        (self.root / 'manifest.json').write_text(admission.canonical(altered))
        with self.assertRaisesRegex(ValueError, 'Frozen plan differs'):
            admission.verify_plan(self.root / 'manifest.json')
        (self.root / 'manifest.json').write_text(admission.canonical(self.plan))
        real_hash = admission.file_hash
        def drift(path):
            if str(path).endswith('typed-decisions/model.safetensors'):
                return 'f' * 64
            return real_hash(path)
        with mock.patch.object(admission, 'file_hash', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'Frozen plan differs'):
                admission.verify_plan(self.root / 'manifest.json')
        with mock.patch.object(admission, 'hardware_identity', return_value={
                **self.plan['runtime']['hardware'], 'chip_type': 'different CPU'}):
            with self.assertRaisesRegex(ValueError, 'Frozen plan differs'):
                admission.verify_plan(self.root / 'manifest.json')

    def test_stage_is_only_expanded_cpu_p0_and_exact_schedule(self):
        command = admission.stage_command(self.plan, self.phase, 'smoke')
        self.assertEqual(command[command.index('--kind') + 1], 'laya')
        self.assertEqual(command[command.index('--mode') + 1], 'expanded')
        self.assertEqual(command[command.index('--device') + 1], 'cpu')
        self.assertEqual(command[command.index('--limit') + 1], '3')
        with self.assertRaises(ValueError):
            admission.stage_command(self.plan, 'laya-english-expanded-cpu/repeat2/P1', 'smoke')
        with self.assertRaises(ValueError):
            admission.stage_command(self.plan, 'laya-english/repeat2/P0', 'smoke')

    def test_smoke_needs_exact_receipt_and_cannot_replay(self):
        with self.assertRaises(ValueError):
            admission.check_stage_receipt(self.phase, 'smoke', self.plan_sha, self.receipt('smoke', plan_sha256='0' * 64))
        receipt = self.receipt('smoke')
        with mock.patch.object(admission.subprocess, 'run', side_effect=lambda command, **kw: self.source_output('smoke', command)) as run:
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', receipt)
            self.assertTrue(run.called)
            self.assertEqual(run.call_args.kwargs['env']['OMP_NUM_THREADS'], '4')
            self.assertEqual(run.call_args.kwargs['env']['HF_HUB_OFFLINE'], '1')
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', receipt)
        self.assertEqual(admission.verify_output(self.plan, self.phase, 'smoke'),
                         admission.file_hash(admission.phase_paths(self.phase) / 'smoke.jsonl'))

    def test_development_requires_verified_inspected_smoke_and_full_output(self):
        with mock.patch.object(admission.subprocess, 'run', side_effect=lambda command, **kw: self.source_output('smoke', command)):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
        smoke = admission.phase_paths(self.phase) / 'smoke.jsonl'
        inspection = admission.phase_paths(self.phase) / 'smoke-inspection.json'
        inspection.write_text(admission.canonical({'phase': self.phase, 'plan_sha256': self.plan_sha,
            'smoke_sha256': admission.file_hash(smoke),
            'inspected_ids': ['DEV-001', 'DEV-002', 'DEV-003'], 'approved': True}))
        receipt = self.receipt('development', smoke_inspection_sha256=admission.file_hash(inspection))
        admission.check_stage_receipt(self.phase, 'development', self.plan_sha, receipt)
        with mock.patch.object(admission.subprocess, 'run', side_effect=lambda command, **kw: self.source_output('development', command)):
            admission.run_stage(self.plan, self.plan_sha, self.phase, 'development', receipt)
        output = admission.phase_paths(self.phase) / 'development.jsonl'
        self.assertEqual(len(output.read_text().splitlines()), 60)
        lines = output.read_text().splitlines()
        changed = json.loads(lines[0]); changed['request_sha256'] = '0' * 64
        lines[0] = json.dumps(changed)
        output.write_text('\n'.join(lines) + '\n')
        with self.assertRaisesRegex(ValueError, 'Output binding failed'):
            admission.verify_output(self.plan, self.phase, 'development')

    def test_interrupted_runner_preserves_intent_and_rejects_replay(self):
        receipt = self.receipt('smoke')
        with mock.patch.object(admission.subprocess, 'run', return_value=types.SimpleNamespace(returncode=77)):
            with self.assertRaisesRegex(RuntimeError, 'preserve intent'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', receipt)
        self.assertTrue((admission.phase_paths(self.phase) / 'smoke.intent.json').exists())
        with mock.patch.object(admission.subprocess, 'run') as run:
            with self.assertRaises(FileExistsError):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', receipt)
            run.assert_not_called()

    def test_predecessor_order_requires_verified_output_not_just_completion(self):
        later = 'laya-typed-expanded-cpu/repeat2/P0'
        with self.assertRaisesRegex(ValueError, 'Predecessor'):
            admission.run_stage(self.plan, self.plan_sha, later, 'smoke',
                                self.receipt('smoke').with_name('smoke-receipt.json'))
        prior = admission.phase_paths(self.phase)
        prior.mkdir(parents=True, exist_ok=True)
        output = prior / 'development.jsonl'
        shutil.copyfile(admission.ROOT / 'results/laya-english-expanded-cpu-2026-09-23/development.jsonl', output)
        (prior / 'development.completion.json').write_text(admission.canonical({
            'phase': self.phase, 'stage': 'development', 'plan_sha256': self.plan_sha,
            'output_sha256': admission.file_hash(output), 'count': 60}))
        admission.check_predecessors(self.plan, self.plan_sha, later)
        records = output.read_text().splitlines()
        first = json.loads(records[0]); first['request_sha256'] = '0' * 64
        records[0] = json.dumps(first)
        output.write_text('\n'.join(records) + '\n')
        with self.assertRaisesRegex(ValueError, 'Predecessor'):
            admission.check_predecessors(self.plan, self.plan_sha, later)

    def test_real_os_lock_rejects_concurrent_phase_before_any_intent(self):
        lock = self.root / 'execution.lock'
        holder = subprocess.Popen([sys.executable, '-c',
            'import fcntl,sys; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX); print("READY",flush=True); sys.stdin.read(1)',
            str(lock)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'READY')
            with self.assertRaisesRegex(RuntimeError, 'global execution lock'):
                admission.run_stage(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt('smoke'))
            self.assertFalse((admission.phase_paths(self.phase) / 'smoke.intent.json').exists())
        finally:
            holder.stdin.write('x'); holder.stdin.flush(); holder.wait(timeout=10)
            holder.stdin.close(); holder.stdout.close()


if __name__ == '__main__':
    unittest.main()
