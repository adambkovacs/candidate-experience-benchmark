#!/usr/bin/env python3
"""Offline-frozen AnyJev raw P0 repeat admission; no inference on import or verify."""
import argparse
import ast
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, digest, read_rows, valid
from anyjev_benchmark import (SOURCE_REVISION, extract_prediction, guarded_backend_class,
                              make_decider, question_specs, verify_artifact, verify_source)

WORK = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work')
MODEL = WORK / 'anyjev-qwen06-model'
SOURCE = WORK / 'anyjev-source'
PYTHON = WORK / 'specialist-venv/bin/python'
PLAN_PATH = ROOT / 'results/repeatability-v1/anyjev-raw-p0-v1/manifest.json'
HOST_LOCK = ROOT / 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock'
HISTORY = ROOT / 'results/anyjev-qwen06-raw-mps-2026-09-23'
HISTORICAL_RUNNER_COMMIT = '9f0dda66b633c9d185fccf459b45c65234354ceb'
REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
PACKAGES = ('torch', 'transformers', 'numpy')
SCHEDULE = ('repeat2/P0', 'repeat3/P0')


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n'


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def durable_write(path, value):
    path = Path(path)
    with path.open('x') as stream:
        stream.write(canonical(value))
        stream.flush(); os.fsync(stream.fileno())
    sync_dir(path.parent)


def append_row(path, value):
    path = Path(path)
    new = not path.exists()
    with path.open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    if new: sync_dir(path.parent)


def hardware_identity():
    """Machine controls only; never persist serial or account identifiers."""
    try:
        result = subprocess.run(['system_profiler', 'SPHardwareDataType', '-json'],
                                capture_output=True, text=True, timeout=20, check=True)
        overview = json.loads(result.stdout)['SPHardwareDataType'][0]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        overview = {}
    return {key: overview.get(key) for key in
            ('machine_model', 'chip_type', 'physical_memory', 'number_processors')}


def source_rows(root=ROOT):
    rows = read_rows(root / 'data/pilot/inputs.jsonl')
    if len(rows) != 60 or [row.get('id') for row in rows] != [f'DEV-{i:03d}' for i in range(1, 61)]:
        raise ValueError('Expected exact ordered 60 development IDs')
    if any(set(row) != {'id', 'feedback'} or not isinstance(row['feedback'], str)
           or not row['feedback'].strip() for row in rows):
        raise ValueError('Development source must be input-only')
    policy = (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    return rows, policy


def native_requests(rows, policy, tokenizer):
    """Render the pinned raw readout without loading model weights or scoring tokens."""
    from anyjev.question import Question
    from anyjev.readout import build_prompt, render_chat, resolve_labels
    from anyjev.state import render_state
    specs = question_specs(policy)
    questions = [Question.choice(spec['text'], spec['options'], name=spec['id']) for spec in specs]
    requests = []
    for row in rows:
        signatures = []
        for question in questions:
            labels, token_ids = resolve_labels(tokenizer, question)
            prompt = render_chat(tokenizer, build_prompt(render_state({'feedback': row['feedback']}),
                                question, list(range(question.k)), labels=labels))
            input_ids = tokenizer.encode(prompt, add_special_tokens=False)
            if len(input_ids) > 4096:
                raise ValueError(f"Full AnyJev input exceeds context: {row['id']}/{question.id}")
            signatures.append({'id': question.id, 'prompt_sha256': digest(prompt),
                'input_ids_sha256': digest(json.dumps(input_ids)),
                'answer_token_ids': list(token_ids), 'input_tokens': len(input_ids)})
        request = {'id': row['id'], 'input_sha256': digest(row['feedback']),
                   'native_decisions': signatures}
        request['request_sha256'] = digest(canonical(request))
        requests.append(request)
    return requests


def function_shape(source, name):
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise ValueError(f'Expected one source function {name}')
    return digest(ast.dump(matches[0], include_attributes=False))


def project_raw(raw, specs):
    questions = raw.get('questions') if isinstance(raw, dict) else None
    if not isinstance(raw, dict) or raw.get('level') != 'raw' or not isinstance(questions, dict) or set(questions) != set(KEYS):
        raise ValueError('Native raw decision set differs')
    prediction = {}
    for spec in specs:
        item = questions[spec['id']]
        options = spec['options']
        distribution = item.get('distribution') if isinstance(item, dict) else None
        if (not isinstance(item, dict) or item.get('kind') != 'choice' or item.get('level') != 'raw'
                or not isinstance(distribution, dict) or set(distribution) != set(options)):
            raise ValueError('Native option identity differs')
        values = [distribution[option] for option in options]
        if (any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 or x > 1 for x in values)
                or abs(sum(values) - 1) > 1e-6):
            raise ValueError('Native probability distribution invalid')
        winner = options[max(range(len(values)), key=values.__getitem__)]
        confidence = item.get('confidence')
        if (item.get('answer') != winner or type(confidence) not in (int, float)
                or not math.isfinite(confidence) or abs(confidence - max(values)) > 1e-9):
            raise ValueError('Native answer/confidence mirror differs')
        prediction[spec['id']] = winner.split(': ', 1)[0]
    if not valid(prediction):
        raise ValueError('Native projection violates four-field schema')
    return prediction


def check_history(root, rows, policy, requests, versions, manifest):
    specs = question_specs(policy)
    question_hash = digest(json.dumps(specs, sort_keys=True))
    hashes = {}; host = None; config = None
    for stage, count in (('smoke', 3), ('development', 60)):
        path = root / 'results/anyjev-qwen06-raw-mps-2026-09-23' / f'{stage}.jsonl'
        saved = read_jsonl(path)
        if len(saved) != count:
            raise ValueError(f'Historical AnyJev {stage} is incomplete')
        for index, (record, request) in enumerate(zip(saved, requests), 1):
            row_config = {key: record.get(key) for key in ('requested_model', 'artifact_revision',
                'surface', 'level', 'source_revision', 'host', 'runtime_versions', 'device', 'dtype',
                'quantization', 'batch_size', 'max_context', 'prior', 'prior_applied',
                'prior_strength', 'shared_prefix', 'adaptive_shifts', 'fresh_decider_per_record',
                'reference_labels_used', 'calibration_artifacts_loaded', 'prompt_placement')}
            if config is None: config = row_config; host = record.get('host')
            if (record.get('id') != request['id'] or record.get('status') != 'ok'
                    or record.get('attempts') != 1 or record.get('input_sha256') != request['input_sha256']
                    or record.get('policy_sha256') != digest(policy)
                    or record.get('question_specs_sha256') != question_hash
                    or record.get('prompt_token_counts') != [x['input_tokens'] for x in request['native_decisions']]
                    or record.get('backend_stats') != {'backend_calls': 1, 'flat_prompts': 4,
                        'shared_groups': 0, 'shared_prompts': 0, 'adaptive_items': 0, 'adaptive_shifts_total': 0}
                    or row_config != config or record.get('prediction') != project_raw(record.get('raw_response'), specs)):
                raise ValueError(f'Historical AnyJev {stage} row {index} fails native parity')
        hashes[f'{stage}_sha256'] = file_hash(path)
    if (host != platform.platform() or config['runtime_versions'] != versions
            or config['requested_model'] != manifest['repo'] or config['artifact_revision'] != REVISION
            or config['surface'] != 'AnyJev local transformers' or config['level'] != 'raw'
            or config['source_revision'] != SOURCE_REVISION or config['device'] != 'mps:0'
            or config['dtype'] != 'torch.bfloat16' or config['quantization'] != 'none'
            or config['batch_size'] != 4 or config['max_context'] != 4096
            or config['prior'] != 'content_free' or config['prior_applied'] is not False
            or config['prior_strength'] != 1.0 or config['shared_prefix'] is not False
            or config['adaptive_shifts'] is not False or config['fresh_decider_per_record'] is not True
            or config['reference_labels_used'] is not False or config['calibration_artifacts_loaded'] is not False):
        raise ValueError('Historical AnyJev runtime/control does not match repeat configuration')
    return {'directory': 'results/anyjev-qwen06-raw-mps-2026-09-23', **hashes,
        'runner_commit': HISTORICAL_RUNNER_COMMIT, 'host': host, 'runtime_versions': versions,
        'controls': config, 'eligible_as_pass1': True,
        'parity_limit': 'Historical records saved prompt lengths, not prompt hashes; pinned runner/source/tokenizer and all 240 lengths match.'}


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    rows, policy = source_rows(root)
    if verify_source(SOURCE) != SOURCE_REVISION:
        raise ValueError('AnyJev source revision changed')
    historical_runner = subprocess.check_output(['git', '-C', str(root), 'show',
        f'{HISTORICAL_RUNNER_COMMIT}:scripts/anyjev_benchmark.py'])
    if hashlib.sha256(historical_runner).hexdigest() != file_hash(root / 'scripts/anyjev_benchmark.py'):
        raise ValueError('Historical AnyJev runner is not the current adapter')
    for path, name in (('scripts/specialist_benchmark.py', 'decision_rows'),
                       ('scripts/jev_benchmark.py', 'make_payload')):
        old = subprocess.check_output(['git', '-C', str(root), 'show', f'{HISTORICAL_RUNNER_COMMIT}:{path}'])
        if function_shape(old, name) != function_shape((root / path).read_bytes(), name):
            raise ValueError(f'Historical native request builder changed: {path}/{name}')
    manifest = verify_artifact(MODEL, REVISION)
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    sys.path.insert(0, str(SOURCE))
    from transformers import AutoTokenizer
    import anyjev
    if not Path(anyjev.__file__).resolve().is_relative_to(SOURCE):
        raise ValueError('Unexpected AnyJev import source')
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
    requests = native_requests(rows, policy, tokenizer)
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    history = check_history(root, rows, policy, requests, versions, manifest)
    asset_hashes = {item['rfilename']: file_hash(MODEL / item['rfilename']) for item in manifest['siblings']}
    sources = [root / name for name in ('scripts/anyjev_raw_repeat_admission.py',
        'scripts/anyjev_benchmark.py', 'scripts/specialist_benchmark.py',
        'scripts/jev_benchmark.py', 'scripts/development_benchmark.py',
        'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl')]
    return {'schema': 'anyjev-raw-native-p0-repeat-admission-v1',
        'status': 'offline_frozen_no_inference', 'reference_labels_used': False,
        'source_sha256': {str(path): file_hash(path) for path in sources},
        'source_revision': SOURCE_REVISION, 'source_import': str(Path(anyjev.__file__).resolve()),
        'artifact_revision': REVISION, 'model_path': str(MODEL), 'model_id': manifest['repo'],
        'artifact_manifest_sha256': file_hash(MODEL / 'download-manifest.json'),
        'asset_sha256': asset_hashes, 'policy_prefix_sha256': digest(policy),
        'question_specs_sha256': digest(json.dumps(question_specs(policy), sort_keys=True)),
        'requests': requests, 'historical': {**history,
            'runner_sha256': hashlib.sha256(historical_runner).hexdigest()},
        'runtime': {'python': str(PYTHON), 'platform': platform.platform(),
            'hardware': hardware_identity(), 'packages': versions, 'device': 'mps:0',
            'dtype': 'torch.bfloat16', 'batch_size': 4, 'max_context': 4096,
            'quantization': 'none', 'level': 'raw', 'prior': 'content_free',
            'prior_strength': 1.0, 'shared_prefix': False, 'adaptive_shifts': False,
            'seed': 'no explicit seed; model.eval() and raw option-logit readout',
            'cache': 'fresh Decider per record; no probes used at raw level; local pinned files only',
            'failure': 'one attempt per selected ID; no retry, fallback or replay after uncertain start'},
        'schedule': list(SCHEDULE), 'stage_inputs': {'smoke': {'limit': 3},
            'development': {'limit': 60}}}


def verify_plan():
    actual = read_json(PLAN_PATH)
    if actual != expected_plan():
        raise ValueError('Frozen AnyJev plan differs from source, assets, history or runtime')
    return actual, file_hash(PLAN_PATH)


def phase_path(phase):
    if phase not in SCHEDULE:
        raise ValueError('Phase outside frozen AnyJev raw P0 schedule')
    return PLAN_PATH.parent.joinpath(*phase.split('/'))


def check_predecessors(plan, plan_sha, phase):
    for predecessor in plan['schedule'][:plan['schedule'].index(phase)]:
        folder = phase_path(predecessor)
        completion = read_json(folder / 'development.completion.json')
        output_hash = verify_output(plan, predecessor, 'development')
        if (completion.get('phase') != predecessor or completion.get('stage') != 'development'
                or completion.get('plan_sha256') != plan_sha or completion.get('output_sha256') != output_hash
                or completion.get('count') != 60):
            raise ValueError(f'Predecessor {predecessor} lacks verified development closure')


def check_receipt(plan, plan_sha, phase, stage, receipt_path):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-anyjev-raw-native-p0-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha):
        raise ValueError('Missing exact root-reviewed AnyJev stage receipt')
    if stage == 'development':
        folder = phase_path(phase)
        completion = read_json(folder / 'smoke.completion.json')
        smoke_hash = verify_output(plan, phase, 'smoke')
        records = read_jsonl(folder / 'smoke.records.jsonl')
        inspection_path = folder / 'smoke-inspection.json'
        inspection = read_json(inspection_path)
        if (completion.get('phase') != phase or completion.get('stage') != 'smoke'
                or completion.get('plan_sha256') != plan_sha or completion.get('output_sha256') != smoke_hash
                or completion.get('count') != 3 or any(x.get('status') != 'ok' for x in records)
                or receipt.get('smoke_inspection_sha256') != file_hash(inspection_path)
                or inspection.get('phase') != phase or inspection.get('plan_sha256') != plan_sha
                or inspection.get('smoke_sha256') != smoke_hash
                or inspection.get('inspected_ids') != [f'DEV-{i:03d}' for i in range(1, 4)]
                or inspection.get('approved') is not True):
            raise ValueError('Development requires exact inspected successful smoke')
    return receipt


def project_capture(capture, specs):
    return project_raw(capture.get('raw_response'), specs)


def verify_output(plan, phase, stage):
    folder = phase_path(phase)
    captures = read_jsonl(folder / f'{stage}.raw.jsonl')
    records = read_jsonl(folder / f'{stage}.records.jsonl')
    journal = read_jsonl(folder / f'{stage}.journal.jsonl')
    count = plan['stage_inputs'][stage]['limit']
    if (len(captures) != count or len(records) != count or not journal
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('AnyJev stage incomplete; preserve partial evidence')
    rows, policy = source_rows()
    specs = question_specs(policy)
    if ([x.get('event') for x in journal] !=
            ['phase_started'] + ['request_started', 'request_completed'] * count + ['phase_completed']):
        raise ValueError('AnyJev journal event order differs')
    started = journal[1:-1:2]
    completed = journal[2:-1:2]
    for index, (capture, record, request) in enumerate(zip(captures, records, plan['requests'])):
        expected = None
        try: expected = project_capture(capture, specs); status = 'ok'
        except ValueError: status = 'invalid_output'
        if (capture.get('id') != request['id'] or record.get('id') != request['id']
                or capture.get('request_sha256') != request['request_sha256']
                or record.get('request_sha256') != request['request_sha256']
                or capture.get('native_decisions') != request['native_decisions']
                or capture.get('prompt_token_counts') != [x['input_tokens'] for x in request['native_decisions']]
                or capture.get('backend_stats') != {'backend_calls': 1, 'flat_prompts': 4,
                    'shared_groups': 0, 'shared_prompts': 0, 'adaptive_items': 0, 'adaptive_shifts_total': 0}
                or record.get('raw_sha256') != digest(canonical(capture))
                or record.get('input_sha256') != request['input_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('question_specs_sha256') != plan['question_specs_sha256']
                or record.get('phase') != phase or record.get('stage') != stage
                or record.get('requested_model') != plan['model_id']
                or record.get('artifact_revision') != plan['artifact_revision']
                or record.get('host') != plan['runtime']['platform']
                or record.get('runtime_versions') != plan['runtime']['packages']
                or record.get('device') != plan['runtime']['device']
                or record.get('dtype') != plan['runtime']['dtype']
                or record.get('level') != 'raw' or record.get('attempts') != 1
                or record.get('status') != status or record.get('prediction') != expected
                or started[index].get('id') != request['id']
                or started[index].get('request_sha256') != request['request_sha256']
                or completed[index].get('id') != request['id']
                or completed[index].get('status') != status):
            raise ValueError(f'AnyJev output binding failed at row {index + 1}')
    return file_hash(folder / f'{stage}.records.jsonl')


def load_backend(plan):
    """The only model-load path; called after lock, receipt, and exclusive claim."""
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['OMP_NUM_THREADS'] = '4'; os.environ['MKL_NUM_THREADS'] = '4'
    sys.path.insert(0, str(SOURCE))
    from anyjev import Decider, Question
    from anyjev.backends.hf import HFBackend
    class CapturingBackend(guarded_backend_class(HFBackend)):
        expected_signatures = None
        observed_signatures = None

        def next_token_logprobs(self, prompts, token_ids):
            actual = [{'id': item['id'], 'prompt_sha256': digest(prompt),
                'input_ids_sha256': digest(json.dumps(self.tokenizer.encode(prompt, add_special_tokens=False))),
                'answer_token_ids': list(ids),
                'input_tokens': len(self.tokenizer.encode(prompt, add_special_tokens=False))}
                for item, prompt, ids in zip(self.expected_signatures or [], prompts, token_ids)]
            if actual != self.expected_signatures or len(prompts) != len(self.expected_signatures or []):
                raise ValueError('Native prompt/token identity differs from frozen plan')
            self.observed_signatures = actual
            return super().next_token_logprobs(prompts, token_ids)

    backend = CapturingBackend(str(MODEL), device='mps', dtype='bfloat16', batch_size=4)
    backend.context_limit = min(4096, backend.model.config.max_position_embeddings)
    backend.prompt_token_counts = []
    if (backend.context_limit != 4096 or str(next(backend.model.parameters()).device) != 'mps:0'
            or str(next(backend.model.parameters()).dtype) != 'torch.bfloat16'):
        raise ValueError('Loaded AnyJev backend differs from frozen controls')
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    questions = [Question.choice(spec['text'], spec['options'], name=spec['id'])
                 for spec in question_specs(policy)]
    return backend, Decider, questions


def _run_locked(plan, plan_sha, phase, stage, receipt_path):
    if phase not in plan['schedule'] or stage not in ('smoke', 'development'):
        raise ValueError('Stage outside frozen AnyJev raw P0 schedule')
    check_predecessors(plan, plan_sha, phase)
    check_receipt(plan, plan_sha, phase, stage, receipt_path)
    folder = phase_path(phase)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f'{stage}.{suffix}').exists() for suffix in
           ('claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl', 'completion.json')):
        raise FileExistsError('AnyJev stage already attempted; no retry')
    durable_write(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'receipt_sha256': file_hash(receipt_path),
        'policy': 'exclusive one attempt; uncertain started positions are not replayed'})
    append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_started', 'phase': phase, 'stage': stage})
    backend, decider_class, questions = load_backend(plan)
    rows, policy = source_rows()
    count = plan['stage_inputs'][stage]['limit']
    specs = question_specs(policy)
    for row, request in zip(rows[:count], plan['requests'][:count]):
        backend.expected_signatures = request['native_decisions']
        backend.observed_signatures = None
        backend.prompt_token_counts = []
        decider = make_decider(backend, 'raw', decider_class)
        append_row(folder / f'{stage}.journal.jsonl', {'event': 'request_started', 'id': row['id'],
            'request_sha256': request['request_sha256'],
            'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        started = time.perf_counter()
        try:
            result = decider.decide({'feedback': row['feedback']}, questions, level='raw')
            if backend.observed_signatures != request['native_decisions']:
                raise ValueError('Native scoring did not read expected prompts')
            capture = {'id': row['id'], 'request_sha256': request['request_sha256'],
                'native_decisions': backend.observed_signatures, 'raw_response': result.to_dict(),
                'diagnostics': {item.question.id: item.diagnostics for item in result},
                'backend_stats': dict(decider.stats),
                'prompt_token_counts': list(backend.prompt_token_counts)}
            capture = json.loads(json.dumps(capture, default=lambda value: value.tolist()))
        except Exception as exc:
            append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_stopped', 'id': row['id'],
                'error_type': type(exc).__name__, 'charge': 'not applicable; local inference'})
            raise RuntimeError('AnyJev scoring/capture failed; retain started unknown without replay') from exc
        append_row(folder / f'{stage}.raw.jsonl', capture)
        try: prediction = project_capture(capture, specs); status = 'ok'
        except ValueError: prediction = None; status = 'invalid_output'
        record = {'id': row['id'], 'phase': phase, 'stage': stage, 'status': status,
            'prediction': prediction, 'attempts': 1, 'request_sha256': request['request_sha256'],
            'input_sha256': request['input_sha256'], 'policy_sha256': plan['policy_prefix_sha256'],
            'question_specs_sha256': plan['question_specs_sha256'],
            'requested_model': plan['model_id'], 'artifact_revision': plan['artifact_revision'],
            'host': plan['runtime']['platform'], 'runtime_versions': plan['runtime']['packages'],
            'device': plan['runtime']['device'], 'dtype': plan['runtime']['dtype'], 'level': 'raw',
            'raw_sha256': digest(canonical(capture)), 'elapsed_seconds': time.perf_counter() - started}
        append_row(folder / f'{stage}.records.jsonl', record)
        append_row(folder / f'{stage}.journal.jsonl', {'event': 'request_completed',
            'id': row['id'], 'status': status})
    append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_completed', 'count': count})
    output_hash = verify_output(plan, phase, stage)
    durable_write(folder / f'{stage}.completion.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'output_sha256': output_hash, 'count': count})
    return output_hash


def run_stage(plan, plan_sha, phase, stage, receipt_path):
    HOST_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with HOST_LOCK.open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise RuntimeError('Another native phase owns the host lock') from exc
        try:
            current, current_sha = verify_plan()
            if current_sha != plan_sha or current != plan:
                raise ValueError('AnyJev plan changed after admission')
            return _run_locked(plan, plan_sha, phase, stage, receipt_path)
        finally: fcntl.flock(lock, fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'verify', 'command', 'run'))
    parser.add_argument('--phase'); parser.add_argument('--stage', choices=('smoke', 'development'))
    parser.add_argument('--receipt')
    args = parser.parse_args(argv)
    if args.action == 'freeze':
        PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        durable_write(PLAN_PATH, expected_plan()); print(file_hash(PLAN_PATH)); return
    plan, plan_sha = verify_plan()
    if args.action == 'verify': print(plan_sha); return
    if args.phase not in plan['schedule'] or args.stage not in ('smoke', 'development'):
        parser.error('Exact frozen phase and stage required')
    if args.action == 'command':
        print(canonical({'phase': args.phase, 'stage': args.stage,
            'ids': [x['id'] for x in plan['requests'][:plan['stage_inputs'][args.stage]['limit']]],
            'offline_only': True, 'model_path': str(MODEL), 'revision': REVISION, 'level': 'raw'}))
        return
    if not args.receipt: parser.error('Root-reviewed stage receipt required')
    run_stage(plan, plan_sha, args.phase, args.stage, args.receipt)


if __name__ == '__main__': main()
