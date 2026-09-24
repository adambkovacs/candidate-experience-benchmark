#!/usr/bin/env python3
"""Pinned native AnyJev L2 outer-CV controller. No inference runs on import/preflight.

Smoke fits only folds holding DEV-001..003. Full requires a reviewed smoke hash,
reuses those exact heads, fits remaining folds and never silently retries a run.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/anyjev-source')
PROTOCOL_PATH = ROOT / 'results/anyjev-l2-protocol-2026-09-24/protocol-v2.json'
PROTOCOL_SHA = 'cccb98feca141d6ade7428351e68c37e1a1a1ba2f7f5f1a5d664926ea376ebae'
FOLD_SHA = '7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c'
INPUTS = ROOT / 'data/pilot/inputs.jsonl'
LABELS = ROOT / 'data/pilot/proposed_labels.jsonl'
SMOKE_IDS = ('DEV-001', 'DEV-002', 'DEV-003')
QUESTIONS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
FIT_KWARGS = {'layers': None, 'kinds': ('lda', 'ridge'), 'n_folds': 5, 'seed': 0, 'listing': 'auto'}
GPU_LOCK = ROOT / 'results/prompt-comparison-v1-2026-09-24/local-gpu.lock'
HELPERS = ('anyjev_cached_l1.py', 'anyjev_benchmark.py', 'development_benchmark.py', 'specialist_benchmark.py')
FIXED_BATCH = 4
FIXED_CONTEXT = 4096


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def append_event(handle, event, **fields):
    """A completed fsync is the boundary before every expensive native call."""
    handle.write(json.dumps({'event': event, 'utc': utc_now(), **fields}, sort_keys=True) + '\n')
    handle.flush()
    os.fsync(handle.fileno())


def audited_call(handle, operation, identity, callback):
    append_event(handle, 'started', operation=operation, **identity)
    try:
        result = callback()
    except BaseException as exc:
        append_event(handle, 'finished', operation=operation, status='failed',
                     error_type=type(exc).__name__, error_message=str(exc), **identity)
        raise
    append_event(handle, 'finished', operation=operation, status='ok', **identity)
    return result


def acquire_gpu_lock(path, identity):
    path = Path(path)
    with path.open('x') as handle:
        json.dump({'owner': 'anyjev-l2', 'pid': os.getpid(), 'utc': utc_now(), **identity}, handle)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    return path


def run_journaled(attempts_path, journal_path, lock_path, identity, callback):
    """No replay: an interrupted call retains journal and GPU lock for audit."""
    if Path(attempts_path).exists() or Path(journal_path).exists():
        raise FileExistsError('Never rerun ambiguous native stage')
    completed = False
    failure = None
    lock_owned = False
    state = {}
    with Path(attempts_path).open('x') as output, Path(journal_path).open('x') as journal:
        try:
            acquire_gpu_lock(lock_path, identity)
            lock_owned = True
            append_event(journal, 'run_started', **identity)
            callback(output, journal, state)
            completed = True
        except BaseException as exc:
            failure = exc
            raise
        finally:
            events = rows(journal_path)
            append_event(journal, 'terminal', stage=identity['stage'],
                         status='completed' if completed else 'stopped',
                         error_type=type(failure).__name__ if failure else None,
                         error_message=str(failure) if failure else None,
                         native_fit_calls_completed=sum(e.get('event') == 'finished' and
                                                        e.get('operation') == 'fit_head' and
                                                        e.get('status') == 'ok' for e in events),
                         native_prediction_calls_completed=sum(e.get('event') == 'finished' and
                                                               e.get('operation') == 'predict' and
                                                               e.get('status') == 'ok' for e in events),
                         completed_prediction_records=len(rows(attempts_path)),
                         runtime=state.get('runtime'),
                         run_manifest_sha256=identity.get('run_manifest_sha256'),
                         gpu_lock_preserved=bool(lock_owned and not completed))
            if lock_owned and completed:
                Path(lock_path).unlink()


def verify_run_manifest(path, args):
    manifest = json.loads(Path(path).read_text())
    expected = {'protocol_sha256': PROTOCOL_SHA, 'fold_sha256': FOLD_SHA,
                'runner_sha256': sha(__file__), 'batch_size': FIXED_BATCH,
                'max_context': FIXED_CONTEXT, 'device': 'mps', 'dtype': 'bfloat16',
                'quantization': 'none', 'model_revision': args.model_revision,
                'model_path': str(args.model_path.resolve()),
                'gpu_lock': str(GPU_LOCK)}
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f'Frozen run manifest {key} changed')
    if args.batch_size != FIXED_BATCH or args.max_context != FIXED_CONTEXT:
        raise ValueError('Batch/context differ from reviewed run manifest')
    helper_hashes = {name: sha(ROOT / 'scripts' / name) for name in HELPERS}
    if manifest.get('helper_sha256') != helper_hashes:
        raise ValueError('Imported helper source hash changed')
    return manifest


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def exclusive_json(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
        handle.flush()


def exclusive_jsonl(path, values):
    with Path(path).open('x') as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False) + '\n')
        handle.flush()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def verify_protocol():
    from anyjev_cached_l1 import (verify_fold_file, POLICY_SHA256, SPECS_SHA256,
                                  INPUT_SHA256, SOURCE_REVISION, MODEL_REVISION)
    if sha(PROTOCOL_PATH) != PROTOCOL_SHA:
        raise ValueError('Frozen L2 protocol hash changed')
    protocol = json.loads(PROTOCOL_PATH.read_text())
    if protocol.get('contract') != 'anyjev-l2-outer-cv5-protocol-v2' or protocol.get('source_revision') != SOURCE_REVISION:
        raise ValueError('Wrong frozen L2 protocol')
    if protocol.get('model_revision') != MODEL_REVISION or protocol.get('model') != 'Qwen/Qwen3-0.6B':
        raise ValueError('Model identity changed')
    if protocol.get('fit_controls') != {'layers': None, 'kinds': ['lda', 'ridge'], 'n_folds': 5, 'seed': 0, 'listing': 'auto'}:
        raise ValueError('Native fit controls changed')
    if protocol.get('device') != 'mps' or protocol.get('dtype') != 'bfloat16' or protocol.get('quantization') != 'none':
        raise ValueError('Runtime controls changed')
    baseline_spec = protocol['baseline_precision_evidence']
    baseline_path = ROOT / baseline_spec['file']
    if sha(baseline_path) != baseline_spec['sha256']:
        raise ValueError('Pinned L0 precision source changed')
    baseline = rows(baseline_path)
    if len(baseline) != baseline_spec['rows_verified'] or [r.get('id') for r in baseline] != [f'DEV-{n:03d}' for n in range(1, 61)]:
        raise ValueError('L0 precision evidence lacks canonical sixty')
    if any(r.get('dtype') != 'torch.bfloat16' or r.get('device') != 'mps:0' or
           r.get('quantization') != 'none' or r.get('runtime_versions') != baseline_spec['runtime_versions']
           for r in baseline):
        raise ValueError('L0 precision/runtime evidence differs from v2 protocol')
    fold_spec = protocol['outer_folds']
    if fold_spec['sha256'] != FOLD_SHA:
        raise ValueError('Outer fold binding changed')
    fold_map = verify_fold_file(Path(fold_spec['file']), FOLD_SHA)
    if sha(INPUTS) != INPUT_SHA256:
        raise ValueError('Input source changed')
    if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != SOURCE_REVISION:
        raise ValueError('Pinned AnyJev revision changed')
    if subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True).strip():
        raise ValueError('Pinned AnyJev source is dirty')
    for spec in protocol['source_bindings']:
        if sha(spec['file']) != spec['sha256']:
            raise ValueError('Pinned AnyJev source file changed')
    from development_benchmark import digest
    from anyjev_benchmark import question_specs
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != POLICY_SHA256:
        raise ValueError('Policy changed')
    specs = question_specs(policy)
    if digest(json.dumps(specs, sort_keys=True)) != SPECS_SHA256 or [s['id'] for s in specs] != list(QUESTIONS):
        raise ValueError('Questions or options changed')
    inputs = rows(INPUTS)
    if [r.get('id') for r in inputs] != [f'DEV-{n:03d}' for n in range(1, 61)] or any(set(r) != {'id', 'feedback'} for r in inputs):
        raise ValueError('Inputs are not canonical unlabeled sixty')
    return protocol, fold_map, {r['id']: r['feedback'] for r in inputs}, policy


def folds_for(ids, fold_map):
    selected = [fold for fold in fold_map['folds'] if set(fold['test_ids']) & set(ids)]
    if set().union(*(set(f['test_ids']) & set(ids) for f in selected)) != set(ids):
        raise ValueError('Smoke IDs lack outer folds')
    return selected


def verify_smoke_artifacts(smoke_rows, directory):
    """The full stage must reuse, byte for byte, heads behind reviewed smoke."""
    by_fold = {}
    for row in smoke_rows:
        fold = row.get('fold')
        if type(fold) is not int or not 1 <= fold <= 5 or not row.get('artifact_sha256'):
            raise ValueError('Smoke artifact binding missing')
        prior = by_fold.setdefault(fold, row['artifact_sha256'])
        if prior != row['artifact_sha256']:
            raise ValueError('Smoke fold changed artifact within prediction set')
    for fold, expected in by_fold.items():
        path = Path(directory) / f'fold-{fold}-artifacts.json'
        if not path.exists() or sha(path) != expected:
            raise ValueError('Smoke fold artifact changed before full collection')


def narrow_training_labels(fold, labels):
    """Return only outer-train labels; held-out labels cannot reach fit_fold."""
    train = fold['train_ids']
    test = fold['test_ids']
    if len(train) != 48 or len(test) != 12 or set(train) & set(test):
        raise ValueError('Outer train/test overlap or wrong size')
    return {record_id: labels[record_id] for record_id in train}


def fit_fold(decider, questions, fold, feedback, training_labels, journal=None):
    """Native public fit_head, with actual call arguments restricted to 48 train IDs."""
    from anyjev_cached_l1 import VALUES
    train = fold['train_ids']
    heldout = fold['test_ids']
    if len(train) != 48 or len(heldout) != 12 or set(train) & set(heldout):
        raise ValueError('Outer fold overlap or wrong cardinality')
    if set(training_labels) != set(train):
        raise ValueError('Fit must receive exactly its 48 train labels and no held-out labels')
    if set(feedback) != set(train):
        raise ValueError('Fit must receive exactly its 48 train feedback texts')
    states = [{'feedback': feedback[record_id]} for record_id in train]
    artifacts = {}
    supports = {}
    for question in questions:
        key = question.id
        if key not in QUESTIONS:
            raise ValueError('Unexpected question')
        y = [VALUES[key].index(training_labels[record_id][key]) for record_id in train]
        supports[key] = {label: y.count(i) for i, label in enumerate(VALUES[key])}
        if hasattr(decider.backend, 'expect_prompts'):
            decider.backend.expect_prompts(native_prompts(decider, question, states, random_listing=True))
        call = lambda: decider.fit_head(question, states, y, **FIT_KWARGS)
        artifacts[key] = (audited_call(journal, 'fit_head', {'fold': fold['fold'], 'question': key}, call)
                          if journal is not None else call())
        if hasattr(decider.backend, 'assert_consumed'):
            decider.backend.assert_consumed()
        if artifacts[key].get('n_calib') != 48 or not artifacts[key].get('method', '').startswith('head:'):
            raise ValueError('Native L2 head artifact invalid')
    return {'fold': fold['fold'], 'train_ids': train, 'test_ids': heldout,
            'train_class_support': supports, 'artifacts': artifacts,
            'fit_count': len(artifacts), 'fit_api': 'Decider.fit_head',
            'fit_kwargs': {**FIT_KWARGS, 'kinds': list(FIT_KWARGS['kinds'])}}


def native_prompts(decider, question, states, random_listing):
    """Build the exact prompt whitelist from feedback-only states and native readout."""
    import numpy as np
    from anyjev.readout import build_prompt, render_chat_parts
    from anyjev.state import render_state
    labels, _ = decider._labels_for(question)
    if random_listing and question.k <= decider.RANDOM_LISTING_MAX_K and not question.ordered and question.k > 1:
        rng = np.random.RandomState(0)
        perms = [list(rng.permutation(question.k)) for _ in states]
    else:
        perms = [list(range(question.k)) for _ in states]
    return [''.join(render_chat_parts(decider.backend.tokenizer,
                build_prompt(render_state(state), question, perm, decider.system, labels)))
            for state, perm in zip(states, perms)]


def guarded_backend(base):
    class Guarded(base):
        def expect_prompts(self, expected):
            if getattr(self, '_expected', None) is not None:
                raise ValueError('Prior prompt expectation was not consumed')
            self._expected = list(expected)

        def assert_consumed(self):
            if getattr(self, '_expected', None) is not None:
                raise ValueError('Expected native prompt call did not occur')

        def _check(self, prompts):
            if getattr(self, '_expected', None) != list(prompts):
                raise ValueError('Actual model prompts differ from feedback-only native rendering')
            counts = [len(self.tokenizer.encode(p, add_special_tokens=False)) for p in prompts]
            if any(n > self.context_limit or n < 1 for n in counts):
                raise ValueError('Native L2 prompt exceeds context; truncation forbidden')
            self.prompt_audit.append({'prompt_sha256': [hashlib.sha256(p.encode()).hexdigest() for p in prompts],
                                      'input_tokens': counts, 'reference_labels_in_prompt': False})

        def hidden_states_to(self, prompts, *args, **kwargs):
            self._check(prompts)
            result = super().hidden_states_to(prompts, *args, **kwargs)
            self._expected = None
            return result

        def hidden_states(self, prompts, *args, **kwargs):
            self._check(prompts)
            result = super().hidden_states(prompts, *args, **kwargs)
            self._expected = None
            return result
    return Guarded


def make_decider(backend, decider_class):
    return decider_class(backend, level='L2', adapt=False)


def predict_one(decider, questions, record_id, feedback, journal=None, fold_number=None):
    from anyjev_cached_l1 import VALUES
    from development_benchmark import valid
    state = {'feedback': feedback}
    output = {}
    diagnostics = {}
    for question in questions:
        if hasattr(decider.backend, 'expect_prompts'):
            decider.backend.expect_prompts(native_prompts(decider, question, [state], random_listing=False))
        call = lambda: decider.decide_batch([state], question, level='L2', require='L2')
        decisions = (audited_call(journal, 'predict', {'fold': fold_number, 'id': record_id,
                                                       'question': question.id}, call)
                     if journal is not None else call())
        if hasattr(decider.backend, 'assert_consumed'):
            decider.backend.assert_consumed()
        decision = decisions[0]
        probs = [float(p) for p in decision.probs]
        if len(probs) != len(VALUES[question.id]) or any(not math.isfinite(p) or p < 0 or p > 1 for p in probs) or abs(sum(probs)-1) > 1e-6:
            raise ValueError('Invalid native L2 probability dimensions')
        output[question.id] = {'probs': probs,
                               'label': VALUES[question.id][max(range(len(probs)), key=probs.__getitem__)],
                               'diagnostics': decision.diagnostics}
        diagnostics[question.id] = decision.diagnostics
    prediction = {q: output[q]['label'] for q in QUESTIONS}
    if not valid(prediction):
        raise ValueError('Invalid native L2 output')
    return {'id': record_id, 'prediction': prediction, 'questions': output,
            'diagnostics': diagnostics, 'level': 'L2', 'status': 'ok',
            'reference_labels_in_model_prompts': False}


def run(args):
    from anyjev_cached_l1 import load_labels
    from anyjev_benchmark import verify_artifact, make_questions
    protocol, fold_map, feedback, policy = verify_protocol()
    if args.model_revision != protocol['model_revision'] or args.device != 'mps' or args.dtype != 'bfloat16':
        raise ValueError('Runtime differs from frozen protocol')
    verify_artifact(args.model_path, args.model_revision)
    if args.stage == 'preflight':
        return {'protocol_sha256': PROTOCOL_SHA, 'fold_sha256': FOLD_SHA,
                'smoke_fold_ids': [f['fold'] for f in folds_for(SMOKE_IDS, fold_map)],
                'inference_performed': False, 'reference_labels_read': False}
    if not args.run_native:
        raise ValueError('Native inference requires explicit --run-native')
    if not args.run_manifest:
        raise ValueError('Native inference requires frozen --run-manifest')
    run_manifest = verify_run_manifest(args.run_manifest, args)
    run_manifest_sha = sha(args.run_manifest)
    directory = Path(args.output_dir)
    if args.stage == 'smoke':
        if directory.exists():
            raise FileExistsError('Never rerun ambiguous smoke directory')
        directory.mkdir(parents=True)
        selected_folds = folds_for(SMOKE_IDS, fold_map)
        output_path = directory / 'smoke.jsonl'
        attempts_path = directory / 'smoke.attempts.jsonl'
        review = None
    elif args.stage == 'full':
        if not directory.is_dir():
            raise ValueError('Smoke directory missing')
        output_path = directory / 'full.jsonl'
        attempts_path = directory / 'full.attempts.jsonl'
        if output_path.exists() or attempts_path.exists():
            raise FileExistsError('Never rerun ambiguous full output')
        smoke_path = directory / 'smoke.jsonl'
        review = json.loads(Path(args.smoke_review).read_text()) if args.smoke_review else None
        if not review or review.get('decision') != 'approved' or review.get('protocol_sha256') != PROTOCOL_SHA or review.get('smoke_sha256') != sha(smoke_path) or review.get('runner_sha256') != sha(Path(__file__)) or review.get('run_manifest_sha256') != run_manifest_sha:
            raise ValueError('Full collection requires root-reviewed exact smoke')
        smoke_rows = rows(smoke_path)
        if [r['id'] for r in smoke_rows] != list(SMOKE_IDS) or any(r.get('status') != 'ok' for r in smoke_rows):
            raise ValueError('Smoke coverage/status mismatch')
        verify_smoke_artifacts(smoke_rows, directory)
        selected_folds = fold_map['folds']
    else:
        raise ValueError('Unsupported stage')
    # Separate operation journal is fsynced before and after each native fit/prediction.
    # Existing output paths remain exclusive; no ambiguous work is automatically replayed.
    journal_path = directory / f'{args.stage}.operations.jsonl'
    if journal_path.exists():
        raise FileExistsError('Never rerun ambiguous operation journal')
    identity = {'configuration': protocol['configuration_id'], 'stage': args.stage,
                'run_manifest_sha256': run_manifest_sha, 'runner_sha256': sha(__file__),
                'helper_sha256': run_manifest['helper_sha256'],
                'batch_size': args.batch_size, 'max_context': args.max_context,
                'gpu_lock': str(GPU_LOCK)}
    def perform(output, journal, state):
        labels = load_labels()
        sys.path.insert(0, str(SOURCE))
        from anyjev import Decider, Question
        from anyjev.backends.hf import HFBackend
        import importlib.metadata
        import torch
        observed_versions = {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'numpy')}
        if observed_versions != protocol['baseline_precision_evidence']['runtime_versions']:
            raise ValueError('Native runtime package versions differ from frozen baseline')
        backend = guarded_backend(HFBackend)(str(args.model_path), device=args.device,
                                             dtype=args.dtype, batch_size=args.batch_size)
        backend.context_limit = min(args.max_context, backend.model.config.max_position_embeddings)
        runtime = {'python': platform.python_version(), 'platform': platform.platform(),
                   'machine': platform.machine(), 'processor': platform.processor(),
                   'package_versions': observed_versions, 'torch_mps_available': bool(torch.backends.mps.is_available()),
                   'torch_mps_built': bool(torch.backends.mps.is_built()),
                   'model_parameter_device': str(next(backend.model.parameters()).device),
                   'model_parameter_dtype': str(next(backend.model.parameters()).dtype),
                   'batch_size': args.batch_size, 'max_context': args.max_context,
                   'effective_context_limit': backend.context_limit, 'quantization': 'none',
                   'runner_sha256': sha(__file__), 'helper_sha256': run_manifest['helper_sha256'],
                   'run_manifest_sha256': run_manifest_sha}
        backend.prompt_audit = []
        if str(next(backend.model.parameters()).device).split(':')[0] != 'mps' or next(backend.model.parameters()).dtype != torch.bfloat16:
            raise ValueError('Native model device/dtype mismatch')
        questions = make_questions(policy, Question)
        if [q.id for q in questions] != list(QUESTIONS):
            raise ValueError('Question order changed')
        for fold in selected_folds:
            decider = make_decider(backend, Decider)  # fresh decider per outer fold
            artifact_path = directory / f'fold-{fold["fold"]}-artifacts.json'
            if artifact_path.exists():
                artifact_record = json.loads(artifact_path.read_text())
                if artifact_record.get('protocol_sha256') != PROTOCOL_SHA or artifact_record.get('fold_map_sha256') != FOLD_SHA or artifact_record.get('train_ids') != fold['train_ids'] or artifact_record.get('test_ids') != fold['test_ids'] or artifact_record.get('fit_count') != 4:
                    raise ValueError('Existing fold artifact provenance mismatch')
                for q in questions:
                    decider.load_artifact(q, artifact_record['artifacts'][q.id])
            else:
                if args.stage == 'full' and set(fold['test_ids']) & set(SMOKE_IDS):
                    raise ValueError('Smoke fold artifact missing; never refit ambiguous work')
                training = narrow_training_labels(fold, labels)
                train_feedback = {i: feedback[i] for i in fold['train_ids']}
                artifact_record = fit_fold(decider, questions, fold, train_feedback, training, journal)
                artifact_record.update(protocol_sha256=PROTOCOL_SHA, fold_map_sha256=FOLD_SHA,
                                       source_revision=protocol['source_revision'],
                                       model_revision=protocol['model_revision'],
                                       reference_file_sha256=sha(LABELS),
                                       prompt_audit=list(backend.prompt_audit), runtime=runtime,
                                       run_manifest_sha256=run_manifest_sha)
                exclusive_json(artifact_path, artifact_record)
            ids = [i for i in fold['test_ids'] if (i in SMOKE_IDS if args.stage == 'smoke' else i not in SMOKE_IDS)]
            for record_id in ids:
                started = time.perf_counter()
                record = predict_one(decider, questions, record_id, feedback[record_id], journal, fold["fold"])
                record.update(fold=fold['fold'], artifact_sha256=sha(artifact_path),
                              protocol_sha256=PROTOCOL_SHA, fold_map_sha256=FOLD_SHA,
                              source_revision=protocol['source_revision'],
                              model_revision=protocol['model_revision'],
                              device='mps', dtype='bfloat16', quantization='none',
                              input_sha256=hashlib.sha256(feedback[record_id].encode()).hexdigest(),
                              prompt_audit=backend.prompt_audit[-4:],
                              elapsed_seconds=time.perf_counter()-started, runtime=runtime,
                              run_manifest_sha256=run_manifest_sha)
                output.write(json.dumps(record) + '\n')
                output.flush()
                os.fsync(output.fileno())
        observed_ids = [record['id'] for record in rows(attempts_path)]
        expected_new = (list(SMOKE_IDS) if args.stage == 'smoke' else
                        [f'DEV-{n:03d}' for n in range(1, 61) if f'DEV-{n:03d}' not in SMOKE_IDS])
        if len(observed_ids) != len(expected_new) or set(observed_ids) != set(expected_new):
            raise ValueError('Native stage did not produce exact held-out coverage')
    run_journaled(attempts_path, journal_path, GPU_LOCK, identity, perform)
    runtime = json.loads(journal_path.read_text().splitlines()[-1])['runtime']
    records = rows(attempts_path)
    if args.stage == 'full':
        records = smoke_rows + records
    expected_ids = list(SMOKE_IDS) if args.stage == 'smoke' else [f'DEV-{n:03d}' for n in range(1, 61)]
    if len(records) != len(expected_ids) or len({r['id'] for r in records}) != len(expected_ids) or {r['id'] for r in records} != set(expected_ids):
        raise ValueError('Canonical out-of-fold coverage mismatch')
    ordered = {r['id']: r for r in records}
    exclusive_jsonl(output_path, [ordered[i] for i in expected_ids])
    if args.stage == 'full':
        artifact_specs = [{'fold': fold['fold'], 'file': f'fold-{fold["fold"]}-artifacts.json',
                           'sha256': sha(directory / f'fold-{fold["fold"]}-artifacts.json')}
                          for fold in fold_map['folds']]
        if len(artifact_specs) != 5 or sum(json.loads((directory / a['file']).read_text())['fit_count'] for a in artifact_specs) != 20:
            raise ValueError('Expected exactly twenty native outer-fold fits')
        exclusive_json(directory / 'collection-manifest.json',
                       {'configuration': protocol['configuration_id'], 'protocol_sha256': PROTOCOL_SHA,
                        'fold_map_sha256': FOLD_SHA, 'output_sha256': sha(output_path),
                        'rows': 60, 'held_out_once_per_id': True, 'fit_count': 20,
                        'composition': {'reviewed_smoke_ids': list(SMOKE_IDS), 'reviewed_smoke_rows': 3,
                                        'new_held_out_rows': 57, 'execution_order': 'outer_fold_order',
                                        'canonical_output_order': 'DEV-001..DEV-060',
                                        'fresh_canonical_60_inference_run': False},
                        'run_manifest_sha256': run_manifest_sha, 'runtime': runtime,
                        'fold_artifacts': artifact_specs, 'reference_labels_in_model_prompts': False,
                        'limitation': protocol['sample_size_limitation']})
    return {'stage': args.stage, 'output': str(output_path), 'sha256': sha(output_path),
            'records': len(rows(output_path)), 'inference_performed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=('preflight', 'smoke', 'full'))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--model-path', type=Path, required=True)
    parser.add_argument('--model-revision', required=True)
    parser.add_argument('--device', default='mps')
    parser.add_argument('--dtype', default='bfloat16')
    parser.add_argument('--batch-size', type=int, default=4)
    parser.add_argument('--max-context', type=int, default=4096)
    parser.add_argument('--run-native', action='store_true')
    parser.add_argument('--smoke-review')
    parser.add_argument('--run-manifest', type=Path)
    args = parser.parse_args()
    if args.stage != 'preflight' and not args.output_dir:
        parser.error('--output-dir required for native stages')
    if args.batch_size < 1 or args.max_context < 1:
        parser.error('Positive batch/context required')
    print(json.dumps(run(args)))


if __name__ == '__main__':
    main()
