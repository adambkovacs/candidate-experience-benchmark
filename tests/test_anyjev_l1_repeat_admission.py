"""Offline controls for the candidate direct-native AnyJev L1 controller."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anyjev_l1_repeat_admission as l1
import anyjev_cached_l1 as cached


class L1CandidateTest(unittest.TestCase):
    def setUp(self):
        self.folds = json.loads(l1.FOLD_PATH.read_text())['folds']

    def test_five_outer_folds_and_smoke_identity(self):
        self.assertEqual(l1.fold_contract(self.folds), [1, 4, 5])
        changed = json.loads(json.dumps(self.folds))
        changed[0]['train_ids'].append(changed[0]['test_ids'][0])
        with self.assertRaisesRegex(ValueError, '48 IDs'):
            l1.fold_contract(changed)

    def test_fit_boundary_has_only_48_train_texts_and_indices(self):
        fold = self.folds[0]
        all_labels = cached.load_labels()
        feedback = {rid: f'fictional {rid}' for rid in fold['train_ids']}
        training = {rid: all_labels[rid] for rid in fold['train_ids']}
        states, targets = l1.narrow_training(fold, feedback, training)
        self.assertEqual(len(states), 48)
        self.assertTrue(all(set(state) == {'feedback'} for state in states))
        self.assertEqual(set(targets), set(l1.KEYS))
        self.assertTrue(all(len(values) == 48 for values in targets.values()))
        leaked = dict(training)
        leaked[fold['test_ids'][0]] = all_labels[fold['test_ids'][0]]
        with self.assertRaisesRegex(ValueError, '48 train'):
            l1.narrow_training(fold, feedback, leaked)

    def test_native_request_signatures_use_one_probe_set_and_train_only(self):
        plan = json.loads(l1.L0_PLAN.read_text())
        fold = self.folds[0]
        for key in l1.KEYS:
            signatures = l1.operation_signatures(plan, fold['train_ids'], key)
            per_row = [x for x in plan['requests'][0]['native_calls'][0] if x['question'] == key]
            probe = [x for x in plan['requests'][0]['native_calls'][1] if x['question'] == key]
            self.assertEqual(len(signatures), len(probe) + 48 * len(per_row))
            self.assertEqual(sum(x['kind'] == 'probe' for x in signatures), len(probe))
            self.assertEqual(len(l1.operation_signatures(plan, [fold['test_ids'][0]], key)),
                             len(probe) + len(per_row))

    def test_backend_return_is_durable_before_decision_projection(self):
        class Tokenizer:
            def encode(self, text, add_special_tokens=False):
                return list(text.encode())
        class Backend:
            tokenizer = Tokenizer()
            context_limit = 4096
            def next_token_logprobs(self, prompts, token_ids):
                return [[-1.0, -2.0] for _ in prompts]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            backend = l1.capturing_backend(Backend)()
            prompt = 'input-only fictional feedback'
            signature = {'prompt_sha256': l1.digest(prompt), 'answer_token_ids': [1, 2],
                         'input_tokens': len(prompt.encode())}
            def native():
                backend.next_token_logprobs([prompt], [[1, 2]])
                captured = l1.shared.read_jsonl(folder / 'raw.jsonl')
                self.assertEqual(captured[0]['kind'], 'backend_return')
                return {'kind': 'choice', 'level': 'L1', 'answer': 'wrong'}
            returned = l1.call_and_capture(folder, 'decision', 'op-1', [signature], backend, native)
            self.assertEqual(returned['answer'], 'wrong')
            self.assertEqual([x['kind'] for x in l1.shared.read_jsonl(folder / 'raw.jsonl')],
                             ['backend_return', 'decision'])
            self.assertEqual([x['event'] for x in l1.shared.read_jsonl(folder / 'journal.jsonl')],
                             ['operation_started', 'operation_returned'])

    def test_backend_rejects_prompt_or_answer_token_drift_before_scoring(self):
        class Tokenizer:
            def encode(self, text, add_special_tokens=False): return list(text.encode())
        class Backend:
            tokenizer = Tokenizer()
            context_limit = 4096
            def next_token_logprobs(self, prompts, token_ids):
                raise AssertionError('Unexpected native scoring')
        with tempfile.TemporaryDirectory() as temp:
            backend = l1.capturing_backend(Backend)()
            expected = {'prompt_sha256': l1.digest('original'), 'answer_token_ids': [1, 2],
                        'input_tokens': len('original')}
            backend.begin('fit-1', [expected], Path(temp) / 'raw.jsonl')
            with self.assertRaisesRegex(ValueError, 'prompt/token identity'):
                backend.next_token_logprobs(['changed'], [[1, 2]])
            with self.assertRaisesRegex(ValueError, 'prompt/token identity'):
                backend.next_token_logprobs(['original'], [[2, 1]])
            self.assertFalse((Path(temp) / 'raw.jsonl').exists())

    def test_unknown_started_call_is_retained_and_not_projected(self):
        class Backend:
            expected = None
            def begin(self, operation_id, signatures, path): self.expected = signatures
            def finish(self): self.expected = None
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with self.assertRaisesRegex(RuntimeError, 'uncertain'):
                l1.call_and_capture(folder, 'calibration', 'fold-1', [], Backend(),
                                    lambda: (_ for _ in ()).throw(RuntimeError('uncertain')))
            self.assertEqual([x['event'] for x in l1.shared.read_jsonl(folder / 'journal.jsonl')],
                             ['operation_started', 'operation_stopped'])
            self.assertFalse((folder / 'raw.jsonl').exists())

    def test_invalid_l1_projection_rejects_fallback_level(self):
        spec = {'options': ['yes: Yes', 'no: No']}
        raw = {'kind': 'choice', 'level': 'L0', 'answer': 'yes: Yes', 'confidence': .9,
               'distribution': {'yes: Yes': .9, 'no: No': .1}}
        with self.assertRaisesRegex(ValueError, 'shape differs'):
            l1.project_decision(raw, spec)
        raw['level'] = 'L1'
        self.assertEqual(l1.project_decision(raw, spec), 'yes')

    def test_receipt_and_predecessor_gates_before_any_claim(self):
        plan = {'folds': self.folds}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            receipt = folder / 'receipt.json'
            receipt.write_text(json.dumps({'kind': 'wrong', 'approved': True,
                'phase': 'fresh1/P0', 'stage': 'smoke', 'plan_sha256': 'plan'}))
            with mock.patch.object(l1, 'phase_dir', return_value=folder), \
                 mock.patch.object(l1, 'load_backend', side_effect=AssertionError('model loaded')):
                with self.assertRaisesRegex(ValueError, 'exact root-reviewed'):
                    l1.run_locked(plan, 'plan', 'fresh1/P0', 'smoke', receipt)
                self.assertFalse((folder / 'smoke.claim.json').exists())
            with mock.patch.object(l1, 'verify_stage', side_effect=ValueError('predecessor not verified')):
                with self.assertRaisesRegex(ValueError, 'predecessor not verified'):
                    l1.check_predecessors(plan, 'plan', 'fresh2/P0')

    def test_prior_stage_claim_blocks_replay_before_model_load(self):
        plan = {'folds': self.folds}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            receipt = folder / 'receipt.json'
            receipt.write_text(json.dumps({'kind': 'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1',
                'approved': True, 'phase': 'fresh1/P0', 'stage': 'smoke', 'plan_sha256': 'plan'}))
            (folder / 'smoke.claim.json').write_text('{}')
            with mock.patch.object(l1, 'phase_dir', return_value=folder), \
                 mock.patch.object(l1, 'load_backend', side_effect=AssertionError('model loaded')):
                with self.assertRaisesRegex(FileExistsError, 'no replay'):
                    l1.run_locked(plan, 'plan', 'fresh1/P0', 'smoke', receipt)

    def test_upstream_api_and_source_files_are_explicitly_pinned(self):
        self.assertIn('anyjev/decider.py', l1.UPSTREAM)
        self.assertIn('anyjev/calibrate/posthoc.py', l1.UPSTREAM)
        self.assertTrue(all((l1.SOURCE / name).is_file() for name in l1.UPSTREAM))
        self.assertEqual(l1.PASSES, ('fresh1/P0', 'fresh2/P0', 'fresh3/P0'))

    def test_fake_smoke_then_full_reuses_artifacts_and_closes_sixty(self):
        spec_by_id = {spec['id']: spec for spec in l1.question_specs(
            (l1.ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0])}
        class Question:
            def __init__(self, key):
                self.id = key; self.key = key; self.options = spec_by_id[key]['options']; self.k = len(self.options)
        questions = [Question(key) for key in l1.KEYS]
        fit_sizes = []
        class Backend:
            name = 'Qwen/Qwen3-0.6B'
            def begin(self, operation_id, signatures, capture_path):
                self.operation_id = operation_id; self.signatures = signatures; self.capture_path = capture_path
            def finish(self):
                self.operation_id = None
            def emit(self, k):
                l1.shared.append_row(self.capture_path, {'kind': 'backend_return',
                    'operation_id': self.operation_id,
                    'signatures': [{key: item[key] for key in
                        ('prompt_sha256', 'answer_token_ids', 'input_tokens')} for item in self.signatures],
                    'logprobs': [[-1.0] * k for _ in self.signatures]})
        backend = Backend()
        class Decision:
            def __init__(self, q): self.question = q
            def to_dict(self):
                return {'kind': 'choice', 'level': 'L1', 'answer': self.question.options[0],
                    'confidence': 1.0, 'distribution': {option: float(i == 0)
                    for i, option in enumerate(self.question.options)}}
        class Decider:
            def __init__(self, backend, **kwargs): self.backend = backend
            def calibrate(self, question, states, labels, level):
                self.backend.emit(question.k)
                fit_sizes.append((len(states), len(labels), set().union(*(set(x) for x in states))))
                return {'model': self.backend.name, 'question': question.key, 'method': 'temperature',
                    'n_calib': 48, 'temperature': 1.0, 'prior_method': 'content_free',
                    'prior_strength': 1.0, 'prior': [[1 / question.k] * question.k for _ in range(question.k)]}
            def load_artifact(self, question, artifact): pass
            def decide_batch(self, states, question, level, require):
                self.backend.emit(question.k)
                return [Decision(question)]
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(l1, 'BASE', Path(temp)), \
                 mock.patch.object(l1, 'load_backend', return_value=(backend, Decider, questions)):
                phase = 'fresh1/P0'
                folder = l1.phase_dir(phase)
                folder.mkdir(parents=True)
                smoke_receipt = folder / 'smoke.root-review.json'
                smoke_receipt.write_text(json.dumps({'kind': 'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1',
                    'approved': True, 'phase': phase, 'stage': 'smoke', 'plan_sha256': 'plan'}))
                plan = {'folds': self.folds}
                smoke_sha = l1.run_locked(plan, 'plan', phase, 'smoke', smoke_receipt)
                smoke_artifacts = {entry['fold']: entry['sha256'] for entry in
                    l1.shared.read_json(folder / 'smoke.completion.json')['artifacts']}
                inspection = folder / 'smoke-inspection.json'
                inspection.write_text(json.dumps({'approved': True, 'phase': phase, 'plan_sha256': 'plan',
                    'smoke_completion_sha256': smoke_sha, 'inspected_ids': list(l1.SMOKE_IDS)}))
                dev_receipt = folder / 'development.root-review.json'
                dev_receipt.write_text(json.dumps({'kind': 'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1',
                    'approved': True, 'phase': phase, 'stage': 'development', 'plan_sha256': 'plan',
                    'smoke_inspection_sha256': l1.sha(inspection)}))
                l1.run_locked(plan, 'plan', phase, 'development', dev_receipt)
                dev_artifacts = {entry['fold']: entry['sha256'] for entry in
                    l1.shared.read_json(folder / 'development.completion.json')['artifacts']}
                self.assertEqual({key: dev_artifacts[key] for key in smoke_artifacts}, smoke_artifacts)
                ids = [r['id'] for stage in ('smoke', 'development') for r in
                       l1.shared.read_jsonl(folder / f'{stage}.records.jsonl')]
                self.assertEqual(len(set(ids)), 60)
                self.assertEqual(len(fit_sizes), 20)
                self.assertTrue(all(size == (48, 48, {'feedback'}) for size in fit_sizes))
                self.assertEqual(l1.shared.read_json(folder / 'development.completion.json')['combined_heldout_count'], 60)


if __name__ == '__main__': unittest.main()
