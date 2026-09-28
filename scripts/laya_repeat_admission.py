#!/usr/bin/env python3
"""Offline-frozen admission for expanded CPU Laya P0 repeats only."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from development_benchmark import ROOT, KEYS, digest, read_rows, valid
from jev_benchmark import make_payload, parse_response

BASE = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work')
MODEL_ROOT = BASE / 'laya-model'
SOURCE_ROOT = BASE / 'laya-source/laya'
VENV_PYTHON = BASE / 'specialist-venv/bin/python'
PLAN_PATH = ROOT / 'results/repeatability-v1/laya-expanded-cpu-v1/manifest.json'
ASSETS = ('encoder/config.json', 'model.safetensors', 'rl_agent_config.json',
          'tokenizer/tokenizer.json', 'tokenizer/tokenizer_config.json')
PACKAGES = ('torch', 'transformers', 'mlx', 'mlx-lm', 'laya', 'semif-phase1')
CONFIGS = {
    'laya-english-expanded-cpu': ('laya-english-expanded-cpu-2026-09-23', '.', '91b646d'),
    'laya-typed-expanded-cpu': ('laya-typed-expanded-cpu-2026-09-23', 'typed-decisions', 'adc1fb8'),
    'laya-multilingual-expanded-cpu': ('laya-multilingual-expanded-cpu-2026-09-24', 'multilingual', 'e147bac'),
}


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def read_json(path):
    return json.loads(Path(path).read_text())


def hardware_identity():
    """Read public machine controls without retaining serial or account identifiers."""
    try:
        result = subprocess.run(['system_profiler', 'SPHardwareDataType', '-json'],
                                capture_output=True, text=True, timeout=20, check=True)
        overview = json.loads(result.stdout)['SPHardwareDataType'][0]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        overview = {}
    return {key: overview.get(key) for key in
            ('machine_model', 'chip_type', 'physical_memory', 'number_processors')}


def rows_and_policy(root=ROOT):
    rows = read_rows(root / 'data/pilot/inputs.jsonl')
    if len(rows) != 60 or [r.get('id') for r in rows] != [f'DEV-{i:03d}' for i in range(1, 61)]:
        raise ValueError('Expected exactly 60 ordered development IDs')
    if any(set(row) != {'id', 'feedback'} or not isinstance(row['feedback'], str) for row in rows):
        raise ValueError('Development source must be input-only')
    policy = (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    requests = [{'id': row['id'], 'input_sha256': digest(row['feedback']),
                 'request_sha256': digest(json.dumps(make_payload(row['feedback'], policy, 'not-sent', 'official'), sort_keys=True))}
                for row in rows]
    return rows, policy, requests


def check_history(root, directory, model_path, revision, requests, policy):
    folder = root / 'results' / directory
    hashes = {}
    original_config = effective_config = versions = host = None
    for stage, length in (('smoke', 3), ('development', 60)):
        path = folder / (stage + '.jsonl')
        records = [json.loads(line) for line in path.read_text().splitlines()]
        if len(records) != length:
            raise ValueError(f'{directory} {stage} has {len(records)} records, expected {length}')
        for index, (record, request) in enumerate(zip(records, requests), 1):
            meta = record.get('metadata') or {}
            effective = meta.get('effective_config') or {}
            if original_config is None:
                original_config, effective_config, versions, host = (
                    meta.get('original_config'), effective, record.get('runtime_versions'), record.get('host'))
            if (record.get('id') != request['id'] or record.get('input_sha256') != request['input_sha256']
                    or record.get('request_sha256') != request['request_sha256']
                    or record.get('policy_sha256') != digest(policy)
                    or record.get('requested_model') != str(model_path)
                    or record.get('artifact_revision') != revision
                    or record.get('surface') != 'laya local specialist' or record.get('mode') != 'expanded'
                    or record.get('attempts') != 1 or record.get('status') != 'ok'
                    or not valid(record.get('prediction'))
                    or record['prediction'] != parse_response(record.get('raw_response'), 'laya-rl-agent')
                    or meta.get('device') != 'cpu' or meta.get('dtype') != 'torch.float32'
                    or meta.get('parameter_dtype') != 'torch.float32' or meta.get('quantization') != 'none'
                    or effective.get('max_len') != 4096 or effective.get('head_max_len') != 512
                    or set((meta.get('untruncated_tokens') or {})) != set(KEYS)
                    or max(meta['untruncated_tokens'].values()) > 4096
                    or meta.get('tokenizer_config_sha256_before_load') != meta.get('tokenizer_config_sha256_after_load')):
                raise ValueError(f'Historical {directory} {stage} record {index} fails source/control/raw binding')
            if (meta.get('original_config') != original_config or effective != effective_config
                    or record.get('runtime_versions') != versions or record.get('host') != host):
                raise ValueError(f'Historical {directory} {stage} controls drift at record {index}')
        hashes[stage + '_sha256'] = file_hash(path)
    return dict(hashes, host=host, runtime_versions=versions)


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    rows, policy, requests = rows_and_policy(root)
    revisions = set()
    configurations = {}
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    laya_origin = importlib.util.find_spec('laya').origin
    if Path(laya_origin).resolve() != (SOURCE_ROOT / '__init__.py').resolve():
        raise ValueError('Installed Laya import does not use pinned local source')
    for config_id, (directory, subdir, historical_commit) in CONFIGS.items():
        model = MODEL_ROOT / subdir
        historical = json.loads((root / 'results' / directory / 'development.jsonl').read_text().splitlines()[0])
        revision = historical['artifact_revision']
        revisions.add(revision)
        assets = {name: file_hash(model / name) for name in ASSETS}
        history = check_history(root, directory, model, revision, requests, policy)
        if history['host'] != platform.platform() or history['runtime_versions'] != versions:
            raise ValueError(f'Historical {config_id} runtime does not match repeat runtime')
        historical_runner = subprocess.check_output(
            ['git', '-C', str(root), 'show', f'{historical_commit}:scripts/specialist_benchmark.py'])
        configurations[config_id] = {
            'model_path': str(model), 'artifact_revision': revision,
            'assets_sha256': assets,
            'historical': {'directory': f'results/{directory}', 'runner_git_commit': historical_commit,
                           'runner_source_sha256': hashlib.sha256(historical_runner).hexdigest(), **history,
                           'runtime_matches_repeat': (history['host'] == platform.platform()
                                                      and history['runtime_versions'] == versions)},
            'original_config': historical['metadata']['original_config'],
            'effective_config': historical['metadata']['effective_config'],
        }
    if len(revisions) != 1:
        raise ValueError('Historical Laya revisions differ')
    return {
        'schema': 'laya-expanded-cpu-p0-repeat-admission-v1',
        'status': 'offline_frozen_no_inference',
        'scope': 'P0 only; three expanded CPU configurations; original nonexpanded length failures stay separate',
        'source_sha256': {str(path): file_hash(path) for path in (
            root / 'scripts/laya_repeat_admission.py', root / 'scripts/specialist_benchmark.py', root / 'scripts/jev_benchmark.py',
            root / 'scripts/development_benchmark.py', root / 'docs/LABELING_GUIDE.md',
            root / 'data/pilot/inputs.jsonl', *sorted(SOURCE_ROOT.glob('*.py')))},
        'policy_prefix_sha256': digest(policy),
        'requests': requests,
        'runtime': {'python': str(VENV_PYTHON), 'platform': platform.platform(),
                    'laya_origin': laya_origin,
                    'hardware': hardware_identity(), 'packages': versions,
                    'device': 'cpu', 'dtype': 'torch.float32', 'quantization': 'none',
                    'omp_num_threads': '4', 'mkl_num_threads': '4',
                    'max_len': 4096, 'head_max_len': 512,
                    'seed': 'none explicitly set; upstream model.eval() and CPU forward; effective historical seed unknown',
                    'cache': 'local pinned checkpoint only; HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1 for new passes',
                    'failure': 'one attempt per selected ID; no retry, fallback, truncation or continuation after uncertain interruption'},
        'configurations': configurations,
        'schedule': [f'{config_id}/repeat{repeat}/P0' for repeat in (2, 3) for config_id in CONFIGS],
        'stage_inputs': {'smoke': {'offset': 0, 'limit': 3}, 'development': {'offset': 0, 'limit': 60}},
        'reference_labels_used': False,
    }


def verify_plan(path=PLAN_PATH):
    actual = read_json(path)
    expected = expected_plan()
    if actual != expected:
        raise ValueError('Frozen plan differs from current sources, assets, history, or runtime')
    return actual, file_hash(path)


def phase_paths(phase):
    config, repeat, variant = phase.split('/')
    if config not in CONFIGS or repeat not in ('repeat2', 'repeat3') or variant != 'P0':
        raise ValueError('Phase outside frozen expanded Laya P0 schedule')
    return PLAN_PATH.parent / config / repeat / variant


def stage_command(plan, phase, stage):
    if phase not in plan['schedule'] or stage not in ('smoke', 'development'):
        raise ValueError('Unknown phase or stage')
    config = plan['configurations'][phase.split('/')[0]]
    stage_input = plan['stage_inputs'][stage]
    output = phase_paths(phase) / (stage + '.jsonl')
    return [str(VENV_PYTHON), str(ROOT / 'scripts/specialist_benchmark.py'),
            '--kind', 'laya', '--mode', 'expanded', '--model-path', config['model_path'],
            '--revision', config['artifact_revision'], '--device', 'cpu',
            '--offset', str(stage_input['offset']), '--limit', str(stage_input['limit']),
            '--output', str(output), '--config-note',
            'Laya expanded P0 repeat; CPU FP32 no quantization; OMP/MKL4; 4096/head512; exact full-input guard; local pinned assets; no retry']


def check_stage_receipt(phase, stage, plan_sha, receipt_path):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-laya-p0-stage-v1' or receipt.get('phase') != phase
            or receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha
            or receipt.get('approved') is not True):
        raise ValueError('Missing exact root-reviewed stage admission')
    folder = phase_paths(phase)
    if stage == 'development':
        smoke_completion = read_json(folder / 'smoke.completion.json')
        if (smoke_completion.get('plan_sha256') != plan_sha
                or smoke_completion.get('output_sha256') != file_hash(folder / 'smoke.jsonl')
                or smoke_completion.get('count') != 3):
            raise ValueError('Verified smoke completion required before development')
        inspection_path = folder / 'smoke-inspection.json'
        inspection = read_json(inspection_path)
        if (receipt.get('smoke_inspection_sha256') != file_hash(inspection_path)
                or inspection.get('phase') != phase or inspection.get('plan_sha256') != plan_sha
                or inspection.get('smoke_sha256') != file_hash(folder / 'smoke.jsonl')
                or inspection.get('inspected_ids') != [f'DEV-{i:03d}' for i in range(1, 4)]
                or inspection.get('approved') is not True):
            raise ValueError('Smoke inspection does not bind exact three saved records')
    return receipt


def check_predecessors(plan, plan_sha, phase):
    """Require every earlier declared phase to have verified 60-record evidence."""
    if phase not in plan['schedule']:
        raise ValueError('Phase outside frozen schedule')
    for prior in plan['schedule'][:plan['schedule'].index(phase)]:
        folder = phase_paths(prior)
        try:
            completion = read_json(folder / 'development.completion.json')
            actual_hash = verify_output(plan, prior, 'development')
        except (OSError, ValueError, KeyError) as exc:
            raise ValueError(f'Predecessor {prior} lacks verified completion') from exc
        if (completion.get('phase') != prior or completion.get('stage') != 'development'
                or completion.get('plan_sha256') != plan_sha
                or completion.get('output_sha256') != actual_hash or completion.get('count') != 60):
            raise ValueError(f'Predecessor {prior} completion does not bind its verified output')


def verify_output(plan, phase, stage):
    path = phase_paths(phase) / (stage + '.jsonl')
    records = [json.loads(line) for line in path.read_text().splitlines()]
    expected = plan['requests'][:plan['stage_inputs'][stage]['limit']]
    if len(records) != len(expected):
        raise ValueError('Output is incomplete; preserve partial file and do not replay')
    config = plan['configurations'][phase.split('/')[0]]
    for record, request in zip(records, expected):
        meta = record.get('metadata') or {}
        if (record.get('id') != request['id'] or record.get('request_sha256') != request['request_sha256']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('requested_model') != config['model_path']
                or record.get('artifact_revision') != config['artifact_revision']
                or record.get('surface') != 'laya local specialist' or record.get('mode') != 'expanded'
                or record.get('host') != plan['runtime']['platform']
                or record.get('runtime_versions') != plan['runtime']['packages']
                or record.get('status') != 'ok' or record.get('attempts') != 1
                or not valid(record.get('prediction'))
                or record['prediction'] != parse_response(record.get('raw_response'), 'laya-rl-agent')
                or meta.get('device') != 'cpu' or meta.get('dtype') != 'torch.float32'
                or meta.get('parameter_dtype') != 'torch.float32' or meta.get('quantization') != 'none'
                or meta.get('original_config') != config['original_config']
                or meta.get('effective_config') != config['effective_config']
                or set((meta.get('untruncated_tokens') or {})) != set(KEYS)
                or max(meta['untruncated_tokens'].values()) > 4096
                or meta.get('tokenizer_config_sha256_before_load') != config['assets_sha256']['tokenizer/tokenizer_config.json']
                or meta.get('tokenizer_config_sha256_after_load') != config['assets_sha256']['tokenizer/tokenizer_config.json']):
            raise ValueError(f'Output binding failed at {request["id"]}; preserve evidence')
    return file_hash(path)


def _run_stage_locked(plan, plan_sha, phase, stage, receipt):
    check_predecessors(plan, plan_sha, phase)
    check_stage_receipt(phase, stage, plan_sha, receipt)
    if stage == 'development':
        verified_smoke_hash = verify_output(plan, phase, 'smoke')
        if read_json(phase_paths(phase) / 'smoke.completion.json').get('output_sha256') != verified_smoke_hash:
            raise ValueError('Smoke completion differs from verified raw records')
    folder = phase_paths(phase)
    folder.mkdir(parents=True, exist_ok=True)
    intent = folder / (stage + '.intent.json')
    output = folder / (stage + '.jsonl')
    completion = folder / (stage + '.completion.json')
    if intent.exists() or output.exists() or completion.exists():
        raise FileExistsError('Stage already attempted; no automatic retry')
    command = stage_command(plan, phase, stage)
    with intent.open('x') as stream:
        stream.write(canonical({'phase': phase, 'stage': stage, 'plan_sha256': plan_sha,
                                'receipt_sha256': file_hash(receipt), 'argv': command,
                                'policy': 'one attempt; interrupted or absent output remains unknown'}))
        stream.flush(); os.fsync(stream.fileno())
    fd = os.open(folder, os.O_RDONLY); os.fsync(fd); os.close(fd)
    env = dict(os.environ, OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f'Runner exited {result.returncode}; preserve intent and partial output')
    result_hash = verify_output(plan, phase, stage)
    with output.open('rb') as stream: os.fsync(stream.fileno())
    with completion.open('x') as stream:
        stream.write(canonical({'phase': phase, 'stage': stage, 'plan_sha256': plan_sha,
                                'output_sha256': result_hash, 'count': plan['stage_inputs'][stage]['limit']}))
        stream.flush(); os.fsync(stream.fileno())
    fd = os.open(folder, os.O_RDONLY); os.fsync(fd); os.close(fd)


def run_stage(plan, plan_sha, phase, stage, receipt):
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_path = PLAN_PATH.parent / 'execution.lock'
    with lock_path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another Laya repeat phase owns the global execution lock') from exc
        try:
            return _run_stage_locked(plan, plan_sha, phase, stage, receipt)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'verify', 'command', 'run'))
    parser.add_argument('--phase')
    parser.add_argument('--stage', choices=('smoke', 'development'))
    parser.add_argument('--receipt')
    args = parser.parse_args(argv)
    if args.action == 'freeze':
        PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PLAN_PATH.open('x') as stream:
            stream.write(canonical(expected_plan()))
        print(file_hash(PLAN_PATH))
        return
    plan, plan_sha = verify_plan()
    if args.action == 'verify':
        print(plan_sha)
        return
    if not args.phase or not args.stage:
        parser.error('Phase and stage required')
    if args.action == 'command':
        print(json.dumps(stage_command(plan, args.phase, args.stage)))
        return
    if not args.receipt:
        parser.error('Root-reviewed stage receipt required for run')
    run_stage(plan, plan_sha, args.phase, args.stage, args.receipt)


if __name__ == '__main__':
    main()
