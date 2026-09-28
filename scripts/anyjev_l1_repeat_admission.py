#!/usr/bin/env python3
"""Candidate direct-native AnyJev L1 outer-fold admission. No model load on import/verify.

A frozen manifest and exact root-reviewed stage receipts are required before `run`.
The historical cached-score L1 evaluation is not a pass in this fresh series.
"""
import argparse
from collections import Counter
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

import anyjev_cached_l1 as cached
import anyjev_l0_repeat_admission as l0
import anyjev_raw_repeat_admission as shared
from anyjev_benchmark import make_questions, question_specs
from development_benchmark import ROOT, KEYS, VALUES, digest, valid

BASE = ROOT / 'results/repeatability-v1/anyjev-l1-direct-native-cv5-v1'
PLAN_PATH = BASE / 'manifest.json'
L0_PLAN = ROOT / 'results/repeatability-v1/anyjev-l0-p0-v1/manifest.json'
L0_PLAN_SHA = '29095d4a527cefaac3e4169a1dfc94879a7571f909d7f8fb4b2213e32f1a3049'
FOLD_PATH = ROOT / 'results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json'
FOLD_SHA = '7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c'
PASSES = ('fresh1/P0', 'fresh2/P0', 'fresh3/P0')
SMOKE_IDS = ('DEV-001', 'DEV-002', 'DEV-003')
SOURCE = shared.SOURCE
MODEL = shared.MODEL
PYTHON = shared.PYTHON
LOCK = shared.HOST_LOCK
UPSTREAM = ('anyjev/decider.py', 'anyjev/calibrate/posthoc.py',
            'anyjev/calibrate/contextual.py', 'anyjev/calibrate/permute.py',
            'anyjev/readout.py', 'anyjev/state.py', 'anyjev/question.py',
            'anyjev/result.py', 'anyjev/backends/hf.py')
HELPERS = ('scripts/anyjev_l1_repeat_admission.py', 'scripts/anyjev_l0_repeat_admission.py',
           'scripts/anyjev_raw_repeat_admission.py', 'scripts/anyjev_cached_l1.py',
           'scripts/anyjev_benchmark.py', 'scripts/development_benchmark.py')


def sha(path):
    return shared.file_hash(path)


def canonical(value):
    return shared.canonical(value)


def fold_contract(folds):
    ids = {f'DEV-{i:03d}' for i in range(1, 61)}
    tests = [set(fold['test_ids']) for fold in folds]
    if (len(folds) != 5 or any(len(test) != 12 for test in tests)
            or set().union(*tests) != ids or sum(map(len, tests)) != 60):
        raise ValueError('Expected five disjoint 12-position outer folds')
    for fold, test in zip(folds, tests):
        if len(fold['train_ids']) != 48 or set(fold['train_ids']) != ids - test:
            raise ValueError('Outer fold must fit only complementary 48 IDs')
    smoke_folds = [fold['fold'] for fold in folds if set(fold['test_ids']) & set(SMOKE_IDS)]
    if smoke_folds != [1, 4, 5]:
        raise ValueError('Reviewed three-record smoke fold identity changed')
    return smoke_folds


def narrow_training(fold, feedback, labels):
    train, test = set(fold['train_ids']), set(fold['test_ids'])
    if (len(train) != 48 or len(test) != 12 or train & test
            or set(feedback) != train or set(labels) != train):
        raise ValueError('Fit boundary requires exactly 48 train texts and train labels')
    states = [{'feedback': feedback[rid]} for rid in fold['train_ids']]
    targets = {key: [cached.VALUES[key].index(labels[rid][key])
                     for rid in fold['train_ids']] for key in KEYS}
    return states, targets


def expected_plan():
    """Read and hash pinned text/tokenizer/assets; never load model weights or score."""
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    l0_plan, l0_sha = l0.verify_plan()
    if l0_sha != L0_PLAN_SHA or sha(L0_PLAN) != L0_PLAN_SHA:
        raise ValueError('Pinned L0 prompt-signature plan differs')
    fold_map = cached.verify_fold_file(FOLD_PATH, FOLD_SHA)
    folds = fold_map['folds']
    fold_contract(folds)
    labels = cached.load_labels()
    rows, policy = shared.source_rows()
    if digest(policy) != l0_plan['policy_prefix_sha256']:
        raise ValueError('Policy differs from native prompt plan')
    specs = question_specs(policy)
    if digest(json.dumps(specs, sort_keys=True)) != l0_plan['question_specs_sha256']:
        raise ValueError('Question text/options differ from native prompt plan')
    if [row['id'] for row in rows] != [item['id'] for item in l0_plan['requests']]:
        raise ValueError('Native prompt plan membership differs')
    feedback = {row['id']: row['feedback'] for row in rows}
    fit_requests = []
    for fold in folds:
        train_feedback = {rid: feedback[rid] for rid in fold['train_ids']}
        train_labels = {rid: labels[rid] for rid in fold['train_ids']}
        _, targets = narrow_training(fold, train_feedback, train_labels)
        for key in KEYS:
            fit_requests.append({'fold': fold['fold'], 'question': key, 'train_ids': fold['train_ids'],
                'train_input_sha256': digest(canonical([train_feedback[rid] for rid in fold['train_ids']])),
                'train_label_indices_sha256': digest(canonical(targets[key])), 'n_calib': 48})
    return {'schema': 'anyjev-l1-direct-native-cv5-candidate-v1',
        'status': 'frozen_plan_requires_stage_receipts', 'configuration': 'anyjev-qwen06-l1-direct-native-cv5',
        'fresh_passes': list(PASSES), 'smoke_ids': list(SMOKE_IDS), 'smoke_folds': [1, 4, 5],
        'full_new_heldout_count': 57, 'fold_sha256': FOLD_SHA, 'l0_prompt_plan_sha256': L0_PLAN_SHA,
        'input_sha256': cached.INPUT_SHA256, 'reference_sha256': cached.REFERENCE_SHA256,
        'policy_prefix_sha256': l0_plan['policy_prefix_sha256'],
        'question_specs_sha256': l0_plan['question_specs_sha256'],
        'model_id': l0_plan['model_id'], 'model_path': l0_plan['model_path'],
        'model_revision': l0_plan['artifact_revision'],
        'asset_sha256': l0_plan['asset_sha256'],
        'source_revision': l0_plan['source_revision'],
        'source_sha256': {name: sha(ROOT / name) for name in HELPERS},
        'upstream_sha256': {name: sha(SOURCE / name) for name in UPSTREAM},
        'folds': folds, 'fit_requests': fit_requests,
        'heldout_requests': [{'id': item['id'], 'input_sha256': item['input_sha256'],
                              'prompt_sha256': item['request_sha256']}
                             for item in l0_plan['requests']],
        'runtime': {'python': str(PYTHON), 'platform': platform.platform(),
                    'hardware': shared.hardware_identity(),
                    'packages': {name: importlib.metadata.version(name) for name in shared.PACKAGES},
                    'device': 'mps:0', 'dtype': 'torch.bfloat16', 'batch_size': 4,
                    'max_context': 4096, 'quantization': 'none'},
        'calibration': {'api': 'Decider.calibrate(question, 48 feedback-only states, 48 option indices, level="L1")',
                        'prior': 'content_free', 'prior_strength': 1.0,
                        'shared_prefix': False, 'adaptive_shifts': False,
                        'fresh_decider_per_fold_fit': True, 'fresh_decider_per_heldout_id': True,
                        'fit_calls_per_pass': 20, 'heldout_question_calls_per_pass': 240,
                        'artifact_policy': 'fresh four-question artifact per fold and pass; never inherit cached L1 or L2',
                        'label_boundary': 'code-enforced 48-train-only fit; worker process can read all 60 provisional labels'},
        'execution': {'host_lock': str(LOCK), 'smoke': 'three held-out IDs and folds 1/4/5',
                      'development': 'reuse reviewed smoke outputs/artifacts; fit folds 2/3; predict 57 other IDs',
                      'failure': 'one attempt per operation; started/uncertain call never replayed',
                      'cost': 'local native operation; no provider charge'}}


def verify_plan():
    actual = shared.read_json(PLAN_PATH)
    if actual != expected_plan():
        raise ValueError('Frozen L1 manifest differs from current source, runtime, or controls')
    if actual.get('status') != 'frozen_plan_requires_stage_receipts':
        raise ValueError('L1 manifest status differs')
    return actual, sha(PLAN_PATH)


def phase_dir(phase):
    if phase not in PASSES:
        raise ValueError('Phase outside three fresh L1 passes')
    return BASE.joinpath(*phase.split('/'))


def operation_signatures(l0_plan, ids, question):
    """Calibration has one probe set plus the train states; test has one state."""
    by_id = {item['id']: item for item in l0_plan['requests']}
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Empty or duplicate native operation IDs')
    first = by_id[ids[0]]
    probes = [item for item in first['native_calls'][1] if item['question'] == question]
    real = [item for rid in ids for item in by_id[rid]['native_calls'][0]
            if item['question'] == question]
    return probes + real


def signature_key(item):
    return item['prompt_sha256'], tuple(item['answer_token_ids']), item['input_tokens']


def capturing_backend(base):
    """Persist each native backend return before Decider can fit, parse, or project it."""
    class CapturingBackend(base):
        capture_path = None
        operation_id = None
        expected = None

        def begin(self, operation_id, signatures, capture_path):
            if self.expected is not None:
                raise ValueError('Prior native operation remains incomplete')
            self.operation_id = operation_id
            self.capture_path = capture_path
            self.expected = Counter(signature_key(item) for item in signatures)

        def finish(self):
            if self.expected is None or any(self.expected.values()):
                raise ValueError('Native prompt set incomplete')
            self.expected = None
            self.operation_id = None

        def next_token_logprobs(self, prompts, token_ids):
            if self.expected is None or len(prompts) != len(token_ids):
                raise ValueError('Unadmitted native prompt call')
            signatures = []
            for prompt, ids in zip(prompts, token_ids):
                tokens = self.tokenizer.encode(prompt, add_special_tokens=False)
                item = {'prompt_sha256': digest(prompt), 'answer_token_ids': list(ids),
                        'input_tokens': len(tokens)}
                key = signature_key(item)
                if item['input_tokens'] > self.context_limit or self.expected[key] <= 0:
                    raise ValueError('Native prompt/token identity differs from frozen plan')
                self.expected[key] -= 1
                signatures.append(item)
            values = super().next_token_logprobs(prompts, token_ids)
            raw = [list(map(float, row)) for row in values]
            shared.append_row(self.capture_path, {'kind': 'backend_return', 'operation_id': self.operation_id,
                                                  'signatures': signatures, 'logprobs': raw})
            return values
    return CapturingBackend


def call_and_capture(folder, kind, op_id, signatures, backend, callback):
    journal = folder / 'journal.jsonl'
    raw_path = folder / 'raw.jsonl'
    shared.append_row(journal, {'event': 'operation_started', 'kind': kind, 'operation_id': op_id})
    backend.begin(op_id, signatures, raw_path)
    try:
        response = callback()
        body = json.loads(json.dumps(response, default=lambda value: value.tolist()))
        shared.append_row(raw_path, {'kind': kind, 'operation_id': op_id, 'response': body})
        backend.finish()
    except BaseException as exc:
        shared.append_row(journal, {'event': 'operation_stopped', 'kind': kind, 'operation_id': op_id,
                                    'error_type': type(exc).__name__})
        raise
    shared.append_row(journal, {'event': 'operation_returned', 'kind': kind, 'operation_id': op_id})
    return body


def check_artifact(artifact, question, model):
    prior = artifact.get('prior') if isinstance(artifact, dict) else None
    if (not isinstance(artifact, dict) or artifact.get('model') != model
            or artifact.get('question') != question.key or artifact.get('method') != 'temperature'
            or artifact.get('n_calib') != 48 or artifact.get('prior_method') != 'content_free'
            or artifact.get('prior_strength') != 1.0 or type(artifact.get('temperature')) not in (int, float)
            or not math.isfinite(artifact['temperature']) or artifact['temperature'] <= 0
            or not isinstance(prior, list) or len(prior) != question.k
            or any(not isinstance(row, list) or len(row) != question.k for row in prior)):
        raise ValueError('Native L1 artifact identity, prior, or temperature invalid')
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
           for row in prior for value in row):
        raise ValueError('Native L1 frozen prior invalid')


def project_decision(raw, spec):
    options = spec['options']
    distribution = raw.get('distribution') if isinstance(raw, dict) else None
    if (not isinstance(raw, dict) or raw.get('kind') != 'choice' or raw.get('level') != 'L1'
            or not isinstance(distribution, dict) or set(distribution) != set(options)):
        raise ValueError('Native L1 decision shape differs')
    probs = [distribution[option] for option in options]
    if (any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 or x > 1 for x in probs)
            or abs(sum(probs) - 1) > 1e-6):
        raise ValueError('Native L1 probabilities invalid')
    winner = options[max(range(len(probs)), key=probs.__getitem__)]
    confidence = raw.get('confidence')
    if (raw.get('answer') != winner or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or abs(confidence - max(probs)) > 1e-8):
        raise ValueError('Native L1 answer/confidence differs')
    return winner.split(': ', 1)[0]


def verify_stage(plan, plan_sha, phase, stage):
    folder = phase_dir(phase)
    completion = shared.read_json(folder / f'{stage}.completion.json')
    claim_path = folder / f'{stage}.claim.json'
    claim = shared.read_json(claim_path)
    receipt_path = Path(claim['receipt_path'])
    if (completion.get('claim_sha256') != sha(claim_path) or claim.get('phase') != phase
            or claim.get('stage') != stage or claim.get('plan_sha256') != plan_sha
            or claim.get('receipt_sha256') != sha(receipt_path)):
        raise ValueError('L1 claim or root-review receipt binding differs')
    check_receipt_fields = shared.read_json(receipt_path)
    if (check_receipt_fields.get('kind') != 'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1'
            or check_receipt_fields.get('approved') is not True
            or check_receipt_fields.get('phase') != phase
            or check_receipt_fields.get('stage') != stage
            or check_receipt_fields.get('plan_sha256') != plan_sha):
        raise ValueError('L1 root-review receipt changed after admission')
    if stage == 'development':
        check_receipt(plan, plan_sha, phase, stage, receipt_path)
    paths = {key: folder / f'{stage}.{suffix}' for key, suffix in
             [('journal', 'journal.jsonl'), ('raw', 'raw.jsonl'), ('records', 'records.jsonl')]}
    if (completion.get('plan_sha256') != plan_sha or completion.get('phase') != phase
            or completion.get('stage') != stage or
            completion.get('hashes') != {key: sha(path) for key, path in paths.items()}):
        raise ValueError('L1 stage completion/evidence hash differs')
    records = shared.read_jsonl(paths['records'])
    expected = 3 if stage == 'smoke' else 57
    wanted = ([rid for fold in plan['folds'] for rid in fold['test_ids'] if rid in SMOKE_IDS]
              if stage == 'smoke' else [rid for fold in plan['folds']
                     for rid in fold['test_ids'] if rid not in SMOKE_IDS])
    if len(records) != expected or [item.get('id') for item in records] != wanted:
        raise ValueError('L1 stage held-out membership differs')
    raw = shared.read_jsonl(paths['raw'])
    journal = shared.read_jsonl(paths['journal'])
    if not journal or journal[-1] != {'event': 'stage_completed', 'count': expected}:
        raise ValueError('L1 stage journal incomplete')
    final_rows = [item for item in raw if item.get('kind') in ('calibration', 'decision')]
    final = {(item['kind'], item['operation_id']): item['response'] for item in final_rows}
    started = [(item.get('kind'), item.get('operation_id')) for item in journal
               if item.get('event') == 'operation_started']
    returned = [(item.get('kind'), item.get('operation_id')) for item in journal
                if item.get('event') == 'operation_returned']
    if (started != returned or len(final_rows) != len(final) or len(final) != len(started)
            or set(final) != set(started)):
        raise ValueError('L1 operation intent/raw/return lineage differs')
    l0_plan = shared.read_json(L0_PLAN)
    specs = {spec['id']: spec for spec in question_specs((ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0])}
    backend_events = [item for item in raw if item.get('kind') == 'backend_return']
    if len(raw) != len(final_rows) + len(backend_events):
        raise ValueError('Unknown L1 raw event kind')
    for kind, op_id in started:
        parts = op_id.split('/')
        if kind == 'calibration':
            fold_no = int(parts[3].removeprefix('fold-'))
            question = parts[-1]
            ids = next(fold['train_ids'] for fold in plan['folds'] if fold['fold'] == fold_no)
        else:
            question = parts[-1]
            ids = [parts[-2]]
        expected_signatures = Counter(signature_key(item) for item in operation_signatures(l0_plan, ids, question))
        actual_signatures = Counter()
        observed = [item for item in backend_events if item.get('operation_id') == op_id]
        if not observed:
            raise ValueError('L1 native backend raw output missing')
        for event in observed:
            if len(event.get('signatures', [])) != len(event.get('logprobs', [])):
                raise ValueError('L1 native logits/signature count differs')
            for signature, logits in zip(event['signatures'], event['logprobs']):
                actual_signatures[signature_key(signature)] += 1
                if (len(logits) != len(specs[question]['options']) or
                        any(type(value) not in (int, float) or not math.isfinite(value) for value in logits)):
                    raise ValueError('L1 native logits invalid')
        if actual_signatures != expected_signatures:
            raise ValueError('L1 native prompt/token raw lineage differs')
    for record in records:
        rid = record['id']
        decisions = {key: final.get(('decision', f'{phase}/{stage}/{rid}/{key}')) for key in KEYS}
        try: prediction = {key: project_decision(decisions[key], specs[key]) for key in KEYS}
        except ValueError: prediction = None
        artifact_entry = next((entry for entry in completion.get('artifacts', [])
                               if entry['fold'] == record.get('fold')), None)
        if (artifact_entry is None or record.get('artifact_sha256') != artifact_entry['sha256']
                or record.get('reference_labels_in_prompt') is not False
                or record.get('status') != ('ok' if prediction is not None else 'invalid_output')
                or record.get('prediction') != prediction or
                record.get('input_sha256') != next(item['input_sha256'] for item in l0_plan['requests'] if item['id'] == rid)):
            raise ValueError('L1 projected record differs from durable raw decision')
    for entry in completion.get('artifacts', []):
        artifact_set = shared.read_json(folder / entry['file'])
        fold = next(item for item in plan['folds'] if item['fold'] == entry['fold'])
        if (sha(folder / entry['file']) != entry['sha256'] or artifact_set.get('phase') != phase
                or artifact_set.get('fold') != entry['fold'] or artifact_set.get('train_ids') != fold['train_ids']
                or artifact_set.get('test_ids') != fold['test_ids']
                or artifact_set.get('plan_sha256') != plan_sha):
            raise ValueError('L1 fold artifact changed')
        if stage == 'smoke' or entry['fold'] not in (1, 4, 5):
            for question in KEYS:
                op_id = f'{phase}/{stage}/fold-{entry["fold"]}/calibrate/{question}'
                if artifact_set['artifacts'][question] != final.get(('calibration', op_id)):
                    raise ValueError('L1 fold artifact differs from durable calibration response')
    if stage == 'development':
        smoke_sha = verify_stage(plan, plan_sha, phase, 'smoke')
        if completion.get('smoke_completion_sha256') != smoke_sha:
            raise ValueError('L1 full stage lost reviewed smoke lineage')
        smoke_records = shared.read_jsonl(folder / 'smoke.records.jsonl')
        if (len(smoke_records) != 3 or len({item['id'] for item in smoke_records + records}) != 60):
            raise ValueError('L1 full pass lacks 60 unique out-of-fold positions')
    return sha(folder / f'{stage}.completion.json')


def check_receipt(plan, plan_sha, phase, stage, receipt_path):
    receipt = shared.read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha):
        raise ValueError('Missing exact root-reviewed L1 stage receipt')
    if stage == 'development':
        smoke_sha = verify_stage(plan, plan_sha, phase, 'smoke')
        inspection_path = phase_dir(phase) / 'smoke-inspection.json'
        inspection = shared.read_json(inspection_path)
        if (receipt.get('smoke_inspection_sha256') != sha(inspection_path)
                or inspection.get('approved') is not True or inspection.get('phase') != phase
                or inspection.get('plan_sha256') != plan_sha or inspection.get('smoke_completion_sha256') != smoke_sha
                or inspection.get('inspected_ids') != list(SMOKE_IDS)):
            raise ValueError('L1 development requires exact inspected smoke and artifacts')
    return receipt


def check_predecessors(plan, plan_sha, phase):
    for prior in PASSES[:PASSES.index(phase)]:
        verify_stage(plan, plan_sha, prior, 'development')


def load_backend(plan, capture_path):
    """The only model-load path; called after lock, receipt, and exclusive claim."""
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    sys.path.insert(0, str(SOURCE))
    from anyjev import Decider, Question
    from anyjev.backends.hf import HFBackend
    backend = capturing_backend(HFBackend)(str(MODEL), device='mps', dtype='bfloat16', batch_size=4)
    backend.context_limit = min(4096, backend.model.config.max_position_embeddings)
    if (backend.context_limit != 4096 or str(next(backend.model.parameters()).device) != 'mps:0'
            or str(next(backend.model.parameters()).dtype) != 'torch.bfloat16'):
        raise ValueError('Loaded L1 backend differs from frozen controls')
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    return backend, Decider, make_questions(policy, Question)


def run_locked(plan, plan_sha, phase, stage, receipt_path):
    check_predecessors(plan, plan_sha, phase)
    check_receipt(plan, plan_sha, phase, stage, receipt_path)
    folder = phase_dir(phase)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f'{stage}.{suffix}').exists() for suffix in
           ('claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl', 'completion.json')):
        raise FileExistsError('L1 stage already attempted; no replay')
    shared.durable_write(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'receipt_path': str(receipt_path.resolve()),
        'receipt_sha256': sha(receipt_path),
        'policy': 'started native operation never automatically replayed'})
    stage_folder = folder / stage
    stage_folder.mkdir(exist_ok=False)
    shared.append_row(stage_folder / 'journal.jsonl', {'event': 'stage_started', 'phase': phase, 'stage': stage})
    backend, Decider, questions = load_backend(plan, stage_folder / 'raw.jsonl')
    l0_plan = shared.read_json(L0_PLAN)
    input_rows, policy = shared.source_rows()
    feedback = {row['id']: row['feedback'] for row in input_rows}
    labels = cached.load_labels()  # code boundary: only 48 train labels are passed to calibrate
    specs = {spec['id']: spec for spec in question_specs(policy)}
    artifacts = []
    records = []
    selected = [fold for fold in plan['folds'] if stage == 'development' or
                set(fold['test_ids']) & set(SMOKE_IDS)]
    for fold in selected:
        fold_no = fold['fold']
        artifact_file = folder / f'fold-{fold_no}-artifacts.json'
        if stage == 'development' and fold_no in (1, 4, 5):
            smoke_completion = shared.read_json(folder / 'smoke.completion.json')
            entry = next(item for item in smoke_completion['artifacts'] if item['fold'] == fold_no)
            if sha(artifact_file) != entry['sha256']:
                raise ValueError('Smoke L1 artifact changed before development')
            artifact_set = shared.read_json(artifact_file)
        else:
            if artifact_file.exists():
                raise FileExistsError('L1 fold artifact already exists; no refit')
            decider = Decider(backend, level='L1', prior='content_free', prior_strength=1.0,
                              shared_prefix=False, adaptive_shifts=False, adapt=False)
            train_feedback = {rid: feedback[rid] for rid in fold['train_ids']}
            train_labels = {rid: labels[rid] for rid in fold['train_ids']}
            states, targets = narrow_training(fold, train_feedback, train_labels)
            fitted = {}
            for question in questions:
                key = question.id
                op_id = f'{phase}/{stage}/fold-{fold_no}/calibrate/{key}'
                signatures = operation_signatures(l0_plan, fold['train_ids'], key)
                response = call_and_capture(stage_folder, 'calibration', op_id, signatures, backend,
                    lambda q=question, y=targets[key]: decider.calibrate(q, states, y, level='L1'))
                check_artifact(response, question, backend.name)
                fitted[key] = response
            artifact_set = {'phase': phase, 'fold': fold_no, 'train_ids': fold['train_ids'],
                            'test_ids': fold['test_ids'], 'fit_api': 'Decider.calibrate',
                            'artifacts': fitted, 'plan_sha256': plan_sha}
            shared.durable_write(artifact_file, artifact_set)
        artifacts.append({'fold': fold_no, 'file': artifact_file.name, 'sha256': sha(artifact_file)})
        wanted = [rid for rid in fold['test_ids'] if (rid in SMOKE_IDS if stage == 'smoke' else rid not in SMOKE_IDS)]
        for rid in wanted:
            decider = Decider(backend, level='L1', prior='content_free', prior_strength=1.0,
                              shared_prefix=False, adaptive_shifts=False, adapt=False)
            results = {}
            for question in questions:
                decider.load_artifact(question, artifact_set['artifacts'][question.id])
                op_id = f'{phase}/{stage}/{rid}/{question.id}'
                signatures = operation_signatures(l0_plan, [rid], question.id)
                response = call_and_capture(stage_folder, 'decision', op_id, signatures, backend,
                    lambda q=question: decider.decide_batch([{'feedback': feedback[rid]}], q,
                                                              level='L1', require='L1')[0].to_dict())
                results[question.id] = response
            try: prediction = {key: project_decision(results[key], specs[key]) for key in KEYS}
            except ValueError: prediction = None
            status = 'ok' if prediction is not None else 'invalid_output'
            record = {'id': rid, 'fold': fold_no, 'phase': phase, 'stage': stage,
                'status': status, 'prediction': prediction, 'artifact_sha256': sha(artifact_file),
                'input_sha256': digest(feedback[rid]), 'reference_labels_in_prompt': False}
            shared.append_row(stage_folder / 'records.jsonl', record)
            records.append(record)
    expected = 3 if stage == 'smoke' else 57
    if len(records) != expected:
        raise ValueError('L1 stage missing held-out predictions')
    shared.append_row(stage_folder / 'journal.jsonl', {'event': 'stage_completed', 'count': expected})
    for kind, suffix in (('journal', 'journal.jsonl'), ('raw', 'raw.jsonl'), ('records', 'records.jsonl')):
        source = stage_folder / suffix
        target = folder / f'{stage}.{suffix}'
        os.link(source, target)
        shared.sync_dir(folder)
    completion = {'phase': phase, 'stage': stage, 'plan_sha256': plan_sha, 'count': expected,
        'claim_sha256': sha(folder / f'{stage}.claim.json'),
        'hashes': {key: sha(folder / f'{stage}.{suffix}') for key, suffix in
                   [('journal', 'journal.jsonl'), ('raw', 'raw.jsonl'), ('records', 'records.jsonl')]},
        'artifacts': artifacts}
    if stage == 'development':
        completion['smoke_completion_sha256'] = sha(folder / 'smoke.completion.json')
        completion['combined_heldout_count'] = 60
    shared.durable_write(folder / f'{stage}.completion.json', completion)
    verify_stage(plan, plan_sha, phase, stage)
    return sha(folder / f'{stage}.completion.json')


def run_stage(phase, stage, receipt_path):
    if phase not in PASSES or stage not in ('smoke', 'development'):
        raise ValueError('Stage outside frozen L1 schedule')
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise RuntimeError('Another native phase owns the host lock') from exc
        try:
            plan, plan_sha = verify_plan()
            return run_locked(plan, plan_sha, phase, stage, Path(receipt_path))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('candidate', 'verify', 'run'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--phase')
    parser.add_argument('--stage', choices=('smoke', 'development'))
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'candidate':
        if not args.output: parser.error('--output required')
        shared.durable_write(args.output, expected_plan())
        print(sha(args.output))
    elif args.action == 'verify':
        _, plan_sha = verify_plan()
        print(plan_sha)
    else:
        if not args.phase or not args.stage or not args.receipt:
            parser.error('run requires exact phase, stage, and receipt')
        print(run_stage(args.phase, args.stage, args.receipt))


if __name__ == '__main__':
    main()
