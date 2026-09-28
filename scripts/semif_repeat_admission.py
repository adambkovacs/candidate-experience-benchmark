#!/usr/bin/env python3
"""Frozen, offline-planned SemIf native P0 repeats. No inference on import or verify."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from development_benchmark import ROOT, KEYS, digest, read_rows, valid
from jev_benchmark import make_payload
from specialist_benchmark import decision_rows
import laya_repeat_admission as laya

WORK = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work')
MODEL = WORK / 'semif-model'
SOURCE = WORK / 'semif-source'
PYTHON = WORK / 'specialist-venv/bin/python'
PLAN_PATH = ROOT / 'results/repeatability-v1/semif-native-mlx-v1/manifest.json'
HOST_LOCK = ROOT / 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock'
MODES = {'semif-direct': 'direct', 'semif-serial': 'serial', 'semif-shared': 'shared'}
HISTORY = {name: f'results/semif-{mode}-bf16-2026-09-23' for name, mode in MODES.items()}
PACKAGES = ('torch', 'transformers', 'mlx', 'mlx-lm', 'laya', 'semif-phase1')
REVISION = '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a'
SOURCE_COMMIT = 'ca3ba65f142967030ecb453346e94d6f476a69df'
HISTORICAL_RUNNER_COMMIT = '724efe57cdfb3fdbfedc161f24912a25450791b2'


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n'


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def durable_write(path, value):
    path = Path(path)
    with path.open('x') as stream:
        stream.write(canonical(value))
        stream.flush(); os.fsync(stream.fileno())
    sync_dir(path.parent)


def append_row(path, value):
    with Path(path).open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def source_rows(root=ROOT):
    rows = read_rows(root / 'data/pilot/inputs.jsonl')
    if len(rows) != 60 or [x.get('id') for x in rows] != [f'DEV-{i:03d}' for i in range(1, 61)]:
        raise ValueError('Expected exact ordered 60 development IDs')
    if any(set(x) != {'id', 'feedback'} or not isinstance(x['feedback'], str) for x in rows):
        raise ValueError('Development input must contain only id and feedback')
    policy = (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    requests = [{'id': row['id'], 'input_sha256': digest(row['feedback']),
                 'request_sha256': digest(json.dumps(make_payload(row['feedback'], policy, 'not-sent', 'official'), sort_keys=True))}
                for row in rows]
    return rows, policy, requests


def expected_options(feedback, policy):
    return {row['id']: [x['id'] for x in row['options']] for row in decision_rows(feedback, policy)}


def project_raw(raw, options):
    decisions = raw.get('decisions') if isinstance(raw, dict) else None
    if not isinstance(decisions, list) or len(decisions) != len(KEYS):
        raise ValueError('Invalid native decision set')
    result = {}
    for item, key in zip(decisions, KEYS):
        labels = options[key]
        values = item.get('probabilities') if isinstance(item, dict) else None
        if (item.get('id') != key or item.get('option_ids') != labels
                or not isinstance(values, list) or len(values) != len(labels)
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)
                or abs(sum(values) - 1) > 1e-5):
            raise ValueError('Invalid native option distribution')
        result[key] = labels[max(range(len(labels)), key=values.__getitem__)]
    if not valid(result):
        raise ValueError('Native projection violates four-field schema')
    return result


def check_raw_controls(raw, options, metadata, mode):
    decisions = raw.get('decisions') if isinstance(raw, dict) else None
    if not isinstance(decisions, list) or len(decisions) != len(KEYS):
        raise ValueError('Native raw decision count differs')
    expected_model = {**metadata, 'serving_config': f'mlx-{mode}-v1'}
    for item, key in zip(decisions, KEYS):
        if (not isinstance(item, dict) or item.get('id') != key
                or item.get('option_ids') != options[key]
                or item.get('model') != expected_model
                or type(item.get('input_tokens')) is not int
                or not 0 < item['input_tokens'] <= 4096
                or not isinstance(item.get('prompt_sha256'), str)
                or not isinstance(item.get('input_ids_sha256'), str)
                or not isinstance(item.get('answer_token_ids'), list)):
            raise ValueError('Native raw model, prompt or context control differs')


def native_signature(raw):
    return [{'id': item['id'], 'prompt_sha256': item['prompt_sha256'],
             'input_ids_sha256': item['input_ids_sha256'],
             'answer_token_ids': item['answer_token_ids'], 'input_tokens': item['input_tokens']}
            for item in raw['decisions']]


def check_history(root, mode, requests, rows, policy, assets, versions):
    folder = root / HISTORY[f'semif-{mode}']
    hashes = {}
    host = first_metadata = None
    for stage, count in (('smoke', 3), ('development', 60)):
        path = folder / f'{stage}.jsonl'
        saved = [json.loads(line) for line in path.read_text().splitlines()]
        if len(saved) != count:
            raise ValueError(f'Historical SemIf {mode} {stage} incomplete')
        for index, (record, request, source) in enumerate(zip(saved, requests, rows), 1):
            meta = record.get('metadata') or {}
            if host is None:
                host = record.get('host')
                first_metadata = meta
            if (record.get('id') != request['id'] or record.get('status') != 'ok'
                    or record.get('attempts') != 1 or record.get('surface') != 'semif local specialist'
                    or record.get('mode') != mode or record.get('requested_model') != str(MODEL)
                    or record.get('artifact_revision') != REVISION
                    or record.get('input_sha256') != request['input_sha256']
                    or record.get('request_sha256') != request['request_sha256']
                    or record.get('policy_sha256') != digest(policy)
                    or record.get('host') != host or record.get('runtime_versions') != versions
                    or meta.get('source_artifact_sha256') != assets
                    or meta != first_metadata
                    or meta.get('revision') != REVISION or meta.get('backend') != 'mlx'
                    or meta.get('quantization') is not None
                    or meta.get('dtype') != ['mlx.core.bfloat16', 'mlx.core.float32']
                    or record.get('prediction') != project_raw(record.get('raw_response'), expected_options(source['feedback'], policy))):
                raise ValueError(f'Historical SemIf {mode} {stage} row {index} has control or raw mismatch')
            check_raw_controls(record['raw_response'], expected_options(source['feedback'], policy), meta, mode)
        hashes[f'{stage}_sha256'] = file_hash(path)
    if host != platform.platform():
        raise ValueError('SemIf historical host differs from current host')
    return dict(hashes, host=host, runtime_versions=versions, model_metadata=first_metadata)


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    rows, policy, requests = source_rows(root)
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    origin = importlib.util.find_spec('semif_phase1').origin
    if Path(origin).resolve() != (SOURCE / 'src/semif_phase1/__init__.py').resolve():
        raise ValueError('SemIf import is not pinned local source')
    if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != SOURCE_COMMIT:
        raise ValueError('SemIf source commit drift')
    if subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain']):
        raise ValueError('SemIf source checkout is dirty')
    first = read_jsonl(root / HISTORY['semif-direct'] / 'development.jsonl')[0]
    assets = first['metadata']['source_artifact_sha256']
    if set(assets) != {p.name for p in MODEL.iterdir() if p.is_file()}:
        raise ValueError('SemIf local artifact file set drift')
    for name, expected in assets.items():
        if file_hash(MODEL / name) != expected:
            raise ValueError(f'SemIf artifact changed: {name}')
    historical_runner = subprocess.check_output(['git', '-C', str(root), 'show',
        f'{HISTORICAL_RUNNER_COMMIT}:scripts/specialist_benchmark.py'])
    configurations = {}
    for name, mode in MODES.items():
        history = check_history(root, mode, requests, rows, policy, assets, versions)
        development = read_jsonl(root / HISTORY[name] / 'development.jsonl')
        smoke = read_jsonl(root / HISTORY[name] / 'smoke.jsonl')
        native_requests = [{'id': record['id'], 'decisions': native_signature(record['raw_response'])}
                           for record in development]
        if any(native_signature(row['raw_response']) != native_requests[index]['decisions']
               for index, row in enumerate(smoke)):
            raise ValueError(f'Historical SemIf {mode} smoke differs from development native request')
        configurations[name] = {'mode': mode, 'model_path': str(MODEL), 'artifact_revision': REVISION,
            'assets_sha256': assets, 'model_metadata': history['model_metadata'],
            'native_requests': native_requests,
            'historical': {'directory': HISTORY[name], **history,
                'runner_commit': HISTORICAL_RUNNER_COMMIT,
                'runner_sha256': hashlib.sha256(historical_runner).hexdigest(),
                'eligible_as_pass1': True}}
    source_files = [root / x for x in ('scripts/semif_repeat_admission.py', 'scripts/specialist_benchmark.py',
        'scripts/jev_benchmark.py', 'scripts/development_benchmark.py', 'scripts/laya_repeat_admission.py',
        'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl')]
    source_files += sorted((SOURCE / 'src/semif_phase1').glob('*.py'))
    return {'schema': 'semif-native-mlx-p0-repeat-admission-v1',
        'status': 'offline_frozen_no_inference', 'reference_labels_used': False,
        'source_sha256': {str(path): file_hash(path) for path in source_files},
        'laya_plan_sha256': file_hash(laya.PLAN_PATH),
        'policy_prefix_sha256': digest(policy), 'requests': requests,
        'runtime': {'python': str(PYTHON), 'platform': platform.platform(), 'semif_origin': origin,
            'hardware': laya.hardware_identity(), 'packages': versions,
            'backend': 'mlx Metal GPU', 'parameter_dtypes': ['BF16', 'FP32'], 'quantization': 'none',
            'max_input_tokens': 4096, 'seed': 'no explicit seed; native model.eval() option logits',
            'cache': '256 MiB inactive allocator limit; no cross-record model state in direct/serial/shared',
            'failure': 'one call per ID; no retry, fallback, or replay of uncertain started attempt'},
        'configurations': configurations,
        'schedule': [f'{name}/repeat{repeat}/P0' for repeat in (2, 3) for name in MODES],
        'stage_inputs': {'smoke': {'limit': 3}, 'development': {'limit': 60}}}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def verify_plan(path=None):
    if path is None: path = PLAN_PATH
    actual = read_json(path)
    if actual != expected_plan():
        raise ValueError('Frozen SemIf plan differs from source, history, assets or runtime')
    return actual, file_hash(path)


def phase_path(phase):
    parts = phase.split('/')
    if len(parts) != 3 or parts[0] not in MODES or parts[1] not in ('repeat2', 'repeat3') or parts[2] != 'P0':
        raise ValueError('Phase outside SemIf native P0 schedule')
    return PLAN_PATH.parent.joinpath(*parts)


def check_laya_closed():
    plan = read_json(laya.PLAN_PATH)
    sha = file_hash(laya.PLAN_PATH)
    for phase in plan['schedule']:
        folder = laya.phase_paths(phase)
        completion = read_json(folder / 'development.completion.json')
        output_hash = laya.verify_output(plan, phase, 'development')
        if (completion.get('phase') != phase or completion.get('stage') != 'development'
                or completion.get('plan_sha256') != sha or completion.get('output_sha256') != output_hash
                or completion.get('count') != 60):
            raise ValueError(f'Laya predecessor incomplete: {phase}')
    return sha


def check_predecessors(plan, plan_sha, phase):
    if phase not in plan['schedule']:
        raise ValueError('Phase outside frozen SemIf schedule')
    for prior in plan['schedule'][:plan['schedule'].index(phase)]:
        folder = phase_path(prior)
        completion = read_json(folder / 'development.completion.json')
        actual = verify_output(plan, prior, 'development')
        if (completion.get('phase') != prior or completion.get('stage') != 'development'
                or completion.get('plan_sha256') != plan_sha or completion.get('output_sha256') != actual
                or completion.get('count') != 60):
            raise ValueError(f'Predecessor {prior} is not verified complete')


def check_receipt(plan_sha, phase, stage, receipt_path):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-semif-native-p0-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha):
        raise ValueError('Missing exact root-reviewed SemIf stage receipt')
    if stage == 'development':
        folder = phase_path(phase)
        completion = read_json(folder / 'smoke.completion.json')
        smoke_hash = verify_output(read_json(PLAN_PATH), phase, 'smoke')
        smoke_records = read_jsonl(folder / 'smoke.records.jsonl')
        inspection_path = folder / 'smoke-inspection.json'
        inspection = read_json(inspection_path)
        if (completion.get('output_sha256') != smoke_hash or completion.get('count') != 3
                or completion.get('plan_sha256') != plan_sha
                or any(record.get('status') != 'ok' for record in smoke_records)
                or receipt.get('smoke_inspection_sha256') != file_hash(inspection_path)
                or inspection.get('phase') != phase or inspection.get('plan_sha256') != plan_sha
                or inspection.get('smoke_sha256') != smoke_hash
                or inspection.get('inspected_ids') != [f'DEV-{i:03d}' for i in range(1, 4)]
                or inspection.get('approved') is not True):
            raise ValueError('Development requires exact inspected smoke')
    return receipt


def score_raw(backend, model, tokenizer, metadata, mode, feedback, policy):
    rows = decision_rows(feedback, policy)
    if mode == 'direct':
        decisions = [backend.score(model, tokenizer, row, metadata, 4096) for row in rows]
    elif mode == 'serial':
        scorer = backend.SerialPrefixScorer(model, tokenizer, metadata, 4096)
        decisions = [scorer.score(row) for row in rows]
    elif mode == 'shared':
        decisions, _timing = backend.score_shared(model, tokenizer, rows, metadata, 4096)
    else:
        raise ValueError('Unknown native SemIf mode')
    return {'decisions': decisions}


def verify_output(plan, phase, stage):
    folder = phase_path(phase)
    records = read_jsonl(folder / f'{stage}.records.jsonl')
    raw = read_jsonl(folder / f'{stage}.raw.jsonl')
    journal = read_jsonl(folder / f'{stage}.journal.jsonl')
    count = plan['stage_inputs'][stage]['limit']
    if len(records) != count or len(raw) != count or journal[-1].get('event') != 'phase_completed':
        raise ValueError('SemIf stage incomplete; preserve partial evidence')
    rows, policy, requests = source_rows()
    config = plan['configurations'][phase.split('/')[0]]
    for index, (record, capture, request, source) in enumerate(zip(records, raw, requests, rows)):
        check_raw_controls(capture['raw_response'], expected_options(source['feedback'], policy),
                           record.get('metadata') or {}, config['mode'])
        expected_prediction = None
        try:
            expected_prediction = project_raw(capture['raw_response'], expected_options(source['feedback'], policy))
            expected_status = 'ok'
        except ValueError:
            expected_status = 'invalid_output'
        if (record.get('id') != request['id'] or capture.get('id') != request['id']
                or capture.get('request_sha256') != request['request_sha256']
                or record.get('request_sha256') != request['request_sha256']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('mode') != config['mode'] or record.get('requested_model') != config['model_path']
                or record.get('artifact_revision') != config['artifact_revision']
                or record.get('runtime_versions') != plan['runtime']['packages']
                or record.get('host') != plan['runtime']['platform']
                or native_signature(capture['raw_response']) != config['native_requests'][index]['decisions']
                or record.get('metadata') != config['model_metadata']
                or (record.get('metadata') or {}).get('source_artifact_sha256') != config['assets_sha256']
                or (record.get('metadata') or {}).get('dtype') != ['mlx.core.bfloat16', 'mlx.core.float32']
                or (record.get('metadata') or {}).get('quantization') is not None
                or record.get('raw_sha256') != digest(json.dumps(capture['raw_response'], sort_keys=True))
                or record.get('prediction') != expected_prediction
                or record.get('status') != expected_status or record.get('attempts') != 1):
            raise ValueError(f'SemIf output binding failed at row {index + 1}')
    if len([x for x in journal if x.get('event') == 'request_started']) != count:
        raise ValueError('SemIf journal request count differs from output')
    return file_hash(folder / f'{stage}.records.jsonl')


def _run_locked(plan, plan_sha, phase, stage, receipt_path):
    if phase not in plan['schedule'] or stage not in ('smoke', 'development'):
        raise ValueError('Stage outside frozen SemIf schedule')
    if check_laya_closed() != plan['laya_plan_sha256']:
        raise ValueError('Laya plan changed')
    check_predecessors(plan, plan_sha, phase)
    check_receipt(plan_sha, phase, stage, receipt_path)
    folder = phase_path(phase)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f'{stage}.{suffix}').exists() for suffix in
           ('claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl', 'completion.json')):
        raise FileExistsError('SemIf stage already attempted; no retry')
    config = plan['configurations'][phase.split('/')[0]]
    durable_write(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'receipt_sha256': file_hash(receipt_path),
        'policy': 'exclusive one attempt; uncertain started positions are not replayed'})
    append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_started', 'phase': phase, 'stage': stage})
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['OMP_NUM_THREADS'] = '4'; os.environ['MKL_NUM_THREADS'] = '4'
    from semif_phase1 import mlx_backend as backend
    model, tokenizer, metadata = backend.load_model(config['model_path'], config['artifact_revision'], None)
    if (metadata != config['model_metadata']
            or metadata.get('source_artifact_sha256') != config['assets_sha256']
            or metadata.get('quantization') is not None
            or metadata.get('dtype') != ['mlx.core.bfloat16', 'mlx.core.float32']
            or metadata.get('backend') != 'mlx'):
        raise ValueError('Loaded SemIf model differs from frozen controls')
    rows, policy, requests = source_rows()
    count = plan['stage_inputs'][stage]['limit']
    for row, request in zip(rows[:count], requests[:count]):
        append_row(folder / f'{stage}.journal.jsonl', {'event': 'request_started', 'id': row['id'],
            'request_sha256': request['request_sha256'], 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        started = time.perf_counter()
        try:
            raw = score_raw(backend, model, tokenizer, metadata, config['mode'], row['feedback'], policy)
        except Exception as exc:
            append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_stopped', 'id': row['id'],
                'error_type': type(exc).__name__, 'charge': 'not applicable; local inference'})
            raise RuntimeError('Native scoring failed; retain started unknown without replay') from exc
        append_row(folder / f'{stage}.raw.jsonl', {'id': row['id'],
            'request_sha256': request['request_sha256'], 'raw_response': raw})
        try:
            check_raw_controls(raw, expected_options(row['feedback'], policy), metadata, config['mode'])
        except ValueError as exc:
            append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_stopped', 'id': row['id'],
                'error_type': 'NativeControlMismatch'})
            raise RuntimeError('Native raw control mismatch; retain evidence without replay') from exc
        try:
            prediction = project_raw(raw, expected_options(row['feedback'], policy))
            status = 'ok'
        except ValueError:
            prediction = None; status = 'invalid_output'
        record = {'id': row['id'], 'status': status, 'prediction': prediction, 'attempts': 1,
            'phase': phase, 'stage': stage, 'mode': config['mode'], 'surface': 'semif local specialist',
            'requested_model': config['model_path'], 'artifact_revision': config['artifact_revision'],
            'host': plan['runtime']['platform'], 'runtime_versions': plan['runtime']['packages'],
            'input_sha256': request['input_sha256'], 'policy_sha256': plan['policy_prefix_sha256'],
            'request_sha256': request['request_sha256'], 'raw_sha256': digest(json.dumps(raw, sort_keys=True)),
            'elapsed_seconds': time.perf_counter() - started, 'metadata': metadata}
        append_row(folder / f'{stage}.records.jsonl', record)
        append_row(folder / f'{stage}.journal.jsonl', {'event': 'request_completed', 'id': row['id'], 'status': status})
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
        try: return _run_locked(plan, plan_sha, phase, stage, receipt_path)
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
        print(canonical({'phase': args.phase, 'stage': args.stage, 'mode': plan['configurations'][args.phase.split('/')[0]]['mode'],
            'model_path': str(MODEL), 'revision': REVISION, 'max_input_tokens': 4096,
            'ids': [x['id'] for x in plan['requests'][:plan['stage_inputs'][args.stage]['limit']]],
            'offline_only': True}))
        return
    if not args.receipt: parser.error('Root-reviewed stage receipt required')
    run_stage(plan, plan_sha, args.phase, args.stage, args.receipt)


if __name__ == '__main__': main()
