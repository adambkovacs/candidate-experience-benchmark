import dataclasses
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'scripts/anyjev_l2_repeat_admission.py'
spec = importlib.util.spec_from_file_location('l2_repeat_candidate', SOURCE)
repeat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repeat)
repeat.ROOT = REPO
repeat.BASE_SOURCE = REPO / 'scripts/anyjev_l2_cv.py'
repeat.PROTOCOL = REPO / 'results/anyjev-l2-protocol-2026-09-24/protocol-v3.json'
repeat.FOLDS = REPO / 'results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json'
repeat.HISTORY = REPO / 'results/anyjev-l2-cv5-hf517-v1-2026-09-24'
repeat.SHARED_LOCK = REPO / 'results/prompt-comparison-v1-2026-09-24/local-gpu.lock'
repeat.HOST_LOCK = REPO / 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock'
sys.path.insert(0, str(REPO / 'scripts'))


class Tests(unittest.TestCase):
    def test_historical_parity_source_and_private_module(self):
        repeat.verify_history()
        import anyjev_l2_cv as canonical
        original = canonical.audited_call
        private = repeat.load_base()
        self.assertIsNot(private, canonical)
        private.audited_call = object()
        self.assertIs(canonical.audited_call, original)
        self.assertEqual(private.GPU_LOCK, repeat.SHARED_LOCK)

    def test_native_raw_is_durable_before_projection_failure(self):
        base = repeat.load_base()
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            raw = folder / 'smoke.raw.jsonl'
            journal = folder / 'smoke.operations.jsonl'
            attempts = folder / 'smoke.attempts.jsonl'
            lock = folder / 'shared.lock'
            base.audited_call = repeat.capturing_audited_call(base, raw)

            @dataclasses.dataclass
            class Decision:
                probs: list
                level: str
                diagnostics: dict

            def callback(output, operations, state):
                result = base.audited_call(operations, 'predict',
                    {'fold': 1, 'id': 'DEV-001', 'question': 'sentiment'},
                    lambda: [Decision([0.7, 0.3], 'L2', {'readout': 'head:ridge'})])
                self.assertEqual(len(result), 1)
                self.assertTrue(raw.exists())
                raise ValueError('synthetic projection rejection')

            identity = {'stage': 'smoke', 'configuration': 'test',
                        'run_manifest_sha256': 'test', 'gpu_lock': str(lock)}
            with self.assertRaisesRegex(ValueError, 'projection rejection'):
                base.run_journaled(attempts, journal, lock, identity, callback)
            self.assertTrue(lock.exists())
            capture = json.loads(raw.read_text().strip())
            self.assertEqual(capture['identity']['id'], 'DEV-001')
            self.assertEqual(capture['result'][0]['probs'], [0.7, 0.3])
            self.assertEqual(repeat.verify_raw_stage(folder, 'smoke')['completed_native_operations'], 1)
            with self.assertRaises(FileExistsError):
                base.run_journaled(attempts, journal, lock, identity, callback)

    def test_nonfinite_native_raw_survives(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / 'raw.jsonl'
            repeat.append_raw(path, 'fit_head', {'fold': 1, 'question': 'sentiment'},
                              {'candidate': [float('nan'), float('inf')]})
            item = json.loads(path.read_text())
            self.assertEqual(item['result']['candidate'],
                             [{'nonfinite_float': 'nan'}, {'nonfinite_float': 'inf'}])

    def test_known_wrong_native_level_is_captured_then_rejected(self):
        base = repeat.load_base()
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            raw = folder / 'smoke.raw.jsonl'
            journal = folder / 'operations.jsonl'
            base.audited_call = repeat.capturing_audited_call(base, raw)
            @dataclasses.dataclass
            class Decision:
                probs: list
                level: str
                diagnostics: dict
            with journal.open('w') as handle:
                with self.assertRaisesRegex(ValueError, 'level differs'):
                    base.audited_call(handle, 'predict',
                        {'fold': 1, 'id': 'DEV-001', 'question': 'sentiment'},
                        lambda: [Decision([1.0], 'L0', {})])
            self.assertTrue(raw.exists())
            self.assertEqual(json.loads(raw.read_text())['operation'], 'predict')
            self.assertEqual(json.loads(journal.read_text().splitlines()[-1])['status'], 'failed')

    def test_review_binds_raw_inspected_smoke(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            plan = folder / 'plan.json'; plan.write_text('{}\n')
            raw = folder / 'smoke.raw.jsonl'; raw.write_text('{"raw": 1}\n')
            rows = folder / 'smoke.jsonl'; rows.write_text('{"id":"DEV-001"}\n')
            smoke_completion = folder / 'smoke.repeat-completion.json'
            smoke_completion.write_text('{}\n')
            review = folder / 'review.json'
            body = {'decision': 'approved', 'phase': 'repeat2', 'stage': 'full',
                    'plan_sha256': repeat.sha(plan),
                    'controller_sha256': repeat.sha(SOURCE),
                    'scope': 'one native L2 stage only',
                    'smoke_raw_sha256': repeat.sha(raw),
                    'smoke_rows_sha256': repeat.sha(rows),
                    'smoke_completion_sha256': repeat.sha(smoke_completion)}
            review.write_text(json.dumps(body))
            with patch.object(repeat, 'verify_completion', return_value={}):
                repeat.validate_review(review, plan_path=plan, phase='repeat2', stage='full', output_dir=folder)
            raw.write_text('{"raw": 2}\n')
            with self.assertRaisesRegex(ValueError, 'inspected smoke bytes changed'):
                repeat.validate_review(review, plan_path=plan, phase='repeat2', stage='full', output_dir=folder)

    def test_common_host_lock_excludes_second_process(self):
        import subprocess
        with tempfile.TemporaryDirectory() as dirname:
            lock = Path(dirname) / 'lock'
            with repeat.common_host_lock(lock):
                code = ("import fcntl,sys; f=open(sys.argv[1],'a'); "
                        "fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)")
                process = subprocess.run([sys.executable, '-c', code, str(lock)],
                                         capture_output=True, text=True)
                self.assertNotEqual(process.returncode, 0)
            with repeat.common_host_lock(lock):
                pass

    def test_repeat3_requires_repeat2_completion(self):
        with tempfile.TemporaryDirectory() as dirname:
            plan_path = Path(dirname) / 'plan.json'
            manifest = Path(dirname) / 'run-manifest.json'; manifest.write_text('{}\n')
            plan = {'contract': 'anyjev-l2-repeat-plan-v1', 'phase': 'repeat3',
                    'controller_sha256': repeat.sha(SOURCE),
                    'base_runner_sha256': repeat.sha(repeat.BASE_SOURCE),
                    'protocol_sha256': repeat.HISTORICAL_HASHES['protocol'],
                    'fold_sha256': repeat.HISTORICAL_HASHES['folds'],
                    'historical_full_sha256': repeat.HISTORICAL_HASHES['full'],
                    'historical_collection_sha256': repeat.HISTORICAL_HASHES['collection'],
                    'gpu_lock': str(repeat.SHARED_LOCK), 'host_lock': str(repeat.HOST_LOCK),
                    'smoke_ids': ['DEV-001','DEV-002','DEV-003'],
                    'model_revision': 'c1899de289a04d12100db370d81485cdf75e47ca',
                    'device': 'mps', 'dtype': 'bfloat16', 'batch_size': 4,
                    'max_context': 4096, 'quantization': 'none',
                    'fit_controls': {'layers': None, 'kinds': ['lda','ridge'],
                                     'n_folds': 5, 'seed': 0, 'listing': 'auto'},
                    'label_boundary': 'code-enforced 48 train labels per fold; no OS isolation',
                    'output_dir': str(REPO / 'results/repeatability-v1/anyjev-l2-cv5-v1/repeat3'),
                    'model_path': '/private/tmp/synthetic-model',
                    'run_manifest': str(manifest),
                    'run_manifest_sha256': repeat.sha(manifest)}
            plan_path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'repeat2 completion missing'):
                repeat.validate_plan(plan_path, phase='repeat3', stage='smoke')

    def test_wrapper_completion_binds_raw_and_predecessor(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            plan = folder / 'plan.json'; plan.write_text('{}\n')
            review = folder / 'review.json'; review.write_text('{}\n')
            manifest = folder / 'run-manifest.json'; manifest.write_text('{}\n')
            base_review = folder / 'base-smoke-review.json'; base_review.write_text('{}\n')

            def stage_files(stage, count):
                raw = folder / f'{stage}.raw.jsonl'
                journal = folder / f'{stage}.operations.jsonl'
                with raw.open('w') as raw_handle, journal.open('w') as journal_handle:
                    for index in range(count):
                        identity = {'fold': 1, 'question': 'sentiment', 'id': f'DEV-{index:03d}'}
                        operation = 'fit_head' if index < (12 if stage == 'smoke' else 8) else 'predict'
                        raw_handle.write(json.dumps({'operation': operation, 'identity': identity,
                                                     'result': {'index': index}}) + '\n')
                        journal_handle.write(json.dumps({'event': 'finished', 'status': 'ok',
                                                         'operation': operation, **identity}) + '\n')
                    journal_handle.write(json.dumps({'event': 'terminal', 'status': 'completed'}) + '\n')
                (folder / f'{stage}.attempts.jsonl').write_text('{}\n')
                (folder / f'{stage}.jsonl').write_text('{}\n')

            stage_files('smoke', 24)
            for fold in range(1, 6):
                (folder / f'fold-{fold}-artifacts.json').write_text('{}\n')
            smoke = repeat.write_completion(folder, phase='repeat2', stage='smoke',
                plan_path=plan, review_path=review, run_manifest=manifest)
            smoke_path = Path(smoke['wrapper_completion_path'])
            self.assertEqual(repeat.verify_completion(smoke_path, phase='repeat2', stage='smoke')['status'],
                             'completed')
            stage_files('full', 236)
            (folder / 'collection-manifest.json').write_text('{}\n')
            full = repeat.write_completion(folder, phase='repeat2', stage='full',
                plan_path=plan, review_path=review, run_manifest=manifest,
                base_smoke_review=base_review)
            full_path = Path(full['wrapper_completion_path'])
            repeat.verify_completion(full_path, phase='repeat2', stage='full')
            (folder / 'smoke.raw.jsonl').write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'smoke.raw.jsonl changed'):
                repeat.verify_completion(full_path, phase='repeat2', stage='full')

    def test_no_wrapper_completion_on_missing_raw(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            (folder / 'smoke.operations.jsonl').write_text('{"event":"terminal","status":"completed"}\n')
            plan = folder / 'plan.json'; plan.write_text('{}\n')
            review = folder / 'review.json'; review.write_text('{}\n')
            manifest = folder / 'run-manifest.json'; manifest.write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'native raw'):
                repeat.write_completion(folder, phase='repeat2', stage='smoke',
                    plan_path=plan, review_path=review, run_manifest=manifest)
            self.assertFalse((folder / 'smoke.repeat-completion.json').exists())


if __name__ == '__main__':
    unittest.main()
