#!/usr/bin/env python3
"""Offline-frozen Alex OpenJev 4B native P0 admission; no inference on import or verify."""
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
import uuid
from pathlib import Path

from anyjev_raw_repeat_admission import (append_row, canonical, durable_write,
                                         file_hash, hardware_identity, source_rows)
from development_benchmark import ROOT, KEYS, VALUES, digest, valid
from jev_benchmark import make_payload
from specialist_benchmark import nli_pairs

WORK = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work')
MODEL_ROOT = WORK / 'alex-model'
MODEL = MODEL_ROOT / 'qwen3.5-4b-nli-v2'
STAGED_MANIFEST = WORK / 'alex-4b-staged-manifest.json'
PYTHON = WORK / 'specialist-venv/bin/python'
PLAN_PATH = ROOT / 'results/repeatability-v1/alex-openjev4b-native-p0-v1/manifest.json'
HOST_LOCK = ROOT / 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock'
HISTORY = ROOT / 'results/alex-openjev4b-mps-2026-09-23'
REVISION = 'f004f37e52695d6ddfb914a64dbf93942839ba1e'
MODEL_SOURCE_SHA = '071670d0879963ee69600ed31f0f3d5a37bee314461709477e8ac0e25f33fd97'
HISTORICAL_FILES = {
    'smoke.jsonl': '80993140ab2263c23609896196e25acd8e3f6afebc8490131dd3cfdc65bddab2',
    'development.jsonl': '4150c1b8985fd1d06fb251d7473fb682e366d3622257b0429adf8563926ea373',
    'development-resume-2026-09-24.jsonl': '4c0088d27ac651351b4e86906b85a90ad397d63a57bf66e82ca0c39656484d90',
    'development-complete.jsonl': '1fb4ef119e0e5d8ac19c0aaa77aec6b1f5e3e472ae2a9288aadc6a709d13dc82',
    'interruption-2026-09-24.json': '1929d7fe0d71f5d8c74f53c074ce2b9b3fb9eb6fd33ba7bfcef4e9050319514d',
    'reconciliation.json': 'db59a5cd1075223cbcd4a331d749f6fe105dbb1ea8147b6a043b4b12a4b2a614',
}
INITIAL_SPECIALIST_COMMIT = 'eab52d385a2f03d768565f3e2e8a7c5e3a492374'
PACKAGES = ('torch', 'transformers', 'mlx', 'mlx-lm', 'laya', 'semif-phase1')
SCHEDULE = ('fresh1/P0', 'fresh2/P0', 'fresh3/P0')
MAPPING = ('Highest entailment probability among semantic label hypotheses; '
           'NLI neutral is never mapped to insufficient_information')


def read_json(path):
    return json.loads(Path(path).read_text())


def read_jsonl(path):
    data = Path(path).read_bytes()
    if not data.endswith(b'\n') or any(not line for line in data.splitlines()):
        raise ValueError(f'Incomplete JSONL: {path}')
    return [json.loads(line) for line in data.splitlines()]


def git_blob_hash(path):
    size = Path(path).stat().st_size
    result = hashlib.sha1(f'blob {size}\0'.encode())
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def verify_assets():
    manifest = read_json(STAGED_MANIFEST)
    if manifest.get('repo') != 'AlexWortega/openjev' or manifest.get('sha') != REVISION:
        raise ValueError('Alex artifact revision differs')
    expected = {str(Path(MODEL.name) / name) for name in (
        'chat_template.jinja', 'config.json', 'model.safetensors',
        'tokenizer.json', 'tokenizer_config.json', 'train_result.json')}
    siblings = manifest['siblings']
    if {item['rfilename'] for item in siblings} != expected:
        raise ValueError('Alex artifact inventory differs')
    hashes = {}
    for item in siblings:
        name = item['rfilename']
        target = MODEL_ROOT / name
        if target.stat().st_size != item['size']:
            raise ValueError(f'Alex asset size differs: {name}')
        sha = file_hash(target)
        if 'lfs' in item:
            if item['lfs']['sha256'] != sha or item['lfs']['size'] != item['size']:
                raise ValueError(f'Alex LFS asset differs: {name}')
        elif git_blob_hash(target) != item['blobId']:
            raise ValueError(f'Alex Git asset differs: {name}')
        hashes[name] = sha
    if file_hash(MODEL_ROOT / 'modeling_openjev.py') != MODEL_SOURCE_SHA:
        raise ValueError('Alex model source differs')
    return manifest, hashes


def nli_template():
    config = read_json(MODEL / 'config.json')
    template = config.get('nli_template')
    if (template != 'Premise: {premise}\nHypothesis: {hypothesis}'
            or config.get('id2label') != {'0': 'contradiction', '1': 'entailment', '2': 'neutral'}
            or config.get('quantization_config') is not None):
        raise ValueError('Alex NLI template or class order differs')
    return template


def native_requests(rows, policy, tokenizer, template):
    requests = []
    for row in rows:
        pairs = nli_pairs(row['feedback'], policy)
        if len(pairs) != 14:
            raise ValueError('Alex NLI must contain 14 ordered hypotheses')
        signatures = []
        for premise, hypothesis in pairs:
            rendered = template.format(premise=premise.strip(), hypothesis=hypothesis.strip())
            ids = tokenizer(rendered, truncation=False)['input_ids']
            if not 0 < len(ids) <= 4096:
                raise ValueError(f'Alex full NLI input exceeds 4096 tokens: {row["id"]}')
            signatures.append({'premise_sha256': digest(premise),
                               'hypothesis_sha256': digest(hypothesis),
                               'rendered_sha256': digest(rendered),
                               'input_ids_sha256': digest(json.dumps(ids)),
                               'input_tokens': len(ids)})
        request = {'id': row['id'], 'input_sha256': digest(row['feedback']),
                   'request_sha256': digest(json.dumps(
                       make_payload(row['feedback'], policy, 'not-sent', 'official'), sort_keys=True)),
                   'nli_inputs': signatures}
        requests.append(request)
    return requests


def project_probabilities(probabilities):
    if not isinstance(probabilities, list) or len(probabilities) != 14:
        raise ValueError('Alex raw output lacks 14 NLI rows')
    for scores in probabilities:
        if (not isinstance(scores, list) or len(scores) != 3
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       or not 0 <= value <= 1 for value in scores)
                or abs(sum(scores) - 1) > 0.001):
            raise ValueError('Alex raw NLI probabilities differ')
    prediction = {}
    offset = 0
    for key in KEYS:
        chunk = probabilities[offset:offset + len(VALUES[key])]
        prediction[key] = VALUES[key][max(range(len(chunk)), key=lambda i: chunk[i][1])]
        offset += len(chunk)
    if not valid(prediction):
        raise ValueError('Alex native prediction violates four-field schema')
    return prediction


def historical_parity(root, requests, versions, template):
    directory = root / 'results/alex-openjev4b-mps-2026-09-23'
    for name, expected_hash in HISTORICAL_FILES.items():
        if file_hash(directory / name) != expected_hash:
            raise ValueError(f'Historical Alex 4B evidence differs: {name}')
    original = read_jsonl(directory / 'development.jsonl')
    resumed = read_jsonl(directory / 'development-resume-2026-09-24.jsonl')
    complete = read_jsonl(directory / 'development-complete.jsonl')
    if (len(original) != 45 or len(resumed) != 15 or len(complete) != 60
            or complete != original + resumed):
        raise ValueError('Historical Alex 4B composite differs from original plus resume')
    interruption = read_json(directory / 'interruption-2026-09-24.json')
    reconciliation = read_json(directory / 'reconciliation.json')
    if (interruption.get('saved_record_count') != 45
            or interruption.get('original_file_sha256') != HISTORICAL_FILES['development.jsonl']
            or interruption.get('unknown_attempt') != {
                'id': 'DEV-046', 'status': 'possibly_started_outcome_unknown',
                'reason': 'Original controller has no started-event journal; output is flushed only after each inference. No response or elapsed time exists for any possible in-flight attempt.'}
            or reconciliation.get('records') != 60
            or reconciliation.get('inference_seconds_total') is not None
            or reconciliation.get('source_files') != [
                {'path': 'results/alex-openjev4b-mps-2026-09-23/development.jsonl',
                 'sha256': HISTORICAL_FILES['development.jsonl']},
                {'path': 'results/alex-openjev4b-mps-2026-09-23/development-resume-2026-09-24.jsonl',
                 'sha256': HISTORICAL_FILES['development-resume-2026-09-24.jsonl']}]):
        raise ValueError('Historical Alex 4B interruption lineage differs')
    expected_order = [[key, value] for key in KEYS for value in VALUES[key]]
    for stage, saved, expected_requests in (
            ('smoke', read_jsonl(directory / 'smoke.jsonl'), requests[:3]),
            ('original development', original, requests[:45]),
            ('resumed development', resumed, requests[45:])):
        if len(saved) != len(expected_requests):
            raise ValueError(f'Historical Alex 4B {stage} length differs')
        for position, (record, request) in enumerate(zip(saved, expected_requests), 1):
            metadata = record.get('metadata') or {}
            raw = record.get('raw_response') or {}
            if (record.get('id') != request['id'] or record.get('status') != 'ok'
                    or record.get('attempts') != 1
                    or record.get('input_sha256') != request['input_sha256']
                    or record.get('request_sha256') != request['request_sha256']
                    or record.get('requested_model') != str(MODEL)
                    or record.get('artifact_revision') != REVISION
                    or record.get('surface') != 'alex local specialist'
                    or record.get('mode') != 'nli'
                    or record.get('policy_sha256') != digest(
                        (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0])
                    or record.get('runtime_versions') != versions
                    or metadata.get('device') != 'mps:0'
                    or metadata.get('dtype') != 'torch.float32'
                    or metadata.get('quantization') != 'none'
                    or metadata.get('max_tokens') != 4096
                    or metadata.get('batch_size') != 4
                    or metadata.get('input_tokens') != [x['input_tokens'] for x in request['nli_inputs']]
                    or raw.get('hypothesis_order') != expected_order
                    or raw.get('mapping') != MAPPING
                    or record.get('prediction') != project_probabilities(raw.get('nli_probabilities'))):
                raise ValueError(f'Historical Alex 4B {stage} native parity differs at {position}')
    return {'directory': 'results/alex-openjev4b-mps-2026-09-23',
            'files_sha256': HISTORICAL_FILES,
            'eligible_as_fresh_pass1': False,
            'unknown_attempt': {'id': 'DEV-046', 'status': 'possibly_started_outcome_unknown'},
            'reason': 'The old 45 plus resumed 15 output composite crossed a possible in-flight DEV-046 attempt; its outcome and elapsed time remain unknown. It is not a clean matched pass.'}


def historical_source_shape(root):
    original = subprocess.check_output(['git', '-C', str(root), 'show',
        f'{INITIAL_SPECIALIST_COMMIT}:scripts/specialist_benchmark.py'])
    current = (root / 'scripts/specialist_benchmark.py').read_bytes()
    def shape(source):
        tree = ast.parse(source)
        function = next(item for item in tree.body if isinstance(item, ast.FunctionDef)
                        and item.name == 'nli_pairs')
        return hashlib.sha256(ast.dump(function, include_attributes=False).encode()).hexdigest()
    if shape(original) != shape(current):
        raise ValueError('Native NLI pair builder changed since historical source window')
    return {'old_commit': INITIAL_SPECIALIST_COMMIT, 'nli_pairs_ast_sha256': shape(current),
            'exact_executing_revision_verified': False}


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    rows, policy = source_rows(root)
    _, asset_hashes = verify_assets()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
    template = nli_template()
    requests = native_requests(rows, policy, tokenizer, template)
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    history = historical_parity(root, requests, versions, template)
    sources = [root / name for name in (
        'scripts/alex_openjev4b_repeat_admission.py', 'scripts/anyjev_raw_repeat_admission.py',
        'scripts/specialist_benchmark.py',
        'scripts/jev_benchmark.py', 'scripts/development_benchmark.py',
        'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl')]
    return {'schema': 'alex-openjev4b-native-p0-repeat-admission-v1',
            'status': 'offline_frozen_no_inference', 'reference_labels_used': False,
            'disposition': 'fresh_matched_three_historical_observational',
            'source_sha256': {str(path): file_hash(path) for path in sources},
            'historical_source_shape': historical_source_shape(root),
            'artifact_revision': REVISION, 'model_path': str(MODEL),
            'artifact_manifest_sha256': file_hash(STAGED_MANIFEST),
            'asset_sha256': {**asset_hashes, 'modeling_openjev.py': MODEL_SOURCE_SHA},
            'nli_template': template,
            'policy_prefix_sha256': digest(policy), 'requests': requests,
            'historical': history,
            'runtime': {'python': str(PYTHON), 'platform': platform.platform(),
                        'hardware': hardware_identity(), 'packages': versions,
                        'device': 'mps:0', 'dtype': 'torch.float32',
                        'quantization': 'none', 'batch_size': 4,
                        'max_context': 4096, 'nli_class_order': [
                            'contradiction', 'entailment', 'neutral'],
                        'calibration': 'none', 'truncation': 'forbidden',
                        'failure': 'one attempt per ID; no retry or replay after uncertain start'},
            'schedule': list(SCHEDULE),
            'stage_inputs': {'smoke': {'limit': 3}, 'development': {'limit': 60}}}


def verify_plan():
    saved = read_json(PLAN_PATH)
    current = expected_plan()
    if saved != current:
        raise ValueError('Frozen Alex plan differs from source, assets, history or runtime')
    return saved, file_hash(PLAN_PATH)


def phase_path(phase):
    return PLAN_PATH.parent.joinpath(*phase.split('/'))


def check_predecessors(plan, plan_sha, phase):
    for earlier in plan['schedule'][:plan['schedule'].index(phase)]:
        folder = phase_path(earlier)
        terminal = read_json(folder / 'development.completion.json')
        output_sha = verify_output(plan, earlier, 'development')
        if (terminal.get('phase') != earlier or terminal.get('stage') != 'development'
                or terminal.get('plan_sha256') != plan_sha
                or terminal.get('records_sha256') != output_sha
                or terminal.get('raw_sha256') != file_hash(folder / 'development.raw.jsonl')
                or terminal.get('journal_sha256') != file_hash(folder / 'development.journal.jsonl')
                or terminal.get('count') != 60):
            raise ValueError(f'Predecessor {earlier} not closed')


def check_receipt(plan, plan_sha, phase, stage, receipt_path):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-alex-openjev4b-native-p0-stage-v1'
            or receipt.get('approved') is not True
            or receipt.get('phase') != phase or receipt.get('stage') != stage
            or receipt.get('plan_sha256') != plan_sha
            or receipt.get('controller_sha256') != file_hash(__file__)
            or receipt.get('artifact_sha256') != plan['asset_sha256'][
                str(Path(MODEL.name) / 'model.safetensors')]
            or receipt.get('reference_labels_read') is not False):
        raise ValueError('Missing exact root-reviewed Alex stage receipt')
    if stage == 'development':
        folder = phase_path(phase)
        smoke_sha = verify_output(plan, phase, 'smoke')
        terminal = read_json(folder / 'smoke.completion.json')
        inspection_path = folder / 'smoke-inspection.json'
        inspection = read_json(inspection_path)
        smoke = read_jsonl(folder / 'smoke.records.jsonl')
        if (terminal.get('phase') != phase or terminal.get('stage') != 'smoke'
                or terminal.get('plan_sha256') != plan_sha
                or terminal.get('records_sha256') != smoke_sha
                or terminal.get('raw_sha256') != file_hash(folder / 'smoke.raw.jsonl')
                or terminal.get('journal_sha256') != file_hash(folder / 'smoke.journal.jsonl')
                or terminal.get('count') != 3
                or receipt.get('smoke_inspection_sha256') != file_hash(inspection_path)
                or inspection.get('phase') != phase
                or inspection.get('plan_sha256') != plan_sha
                or inspection.get('smoke_records_sha256') != smoke_sha
                or inspection.get('approved') is not True
                or inspection.get('inspected_ids') != [f'DEV-{i:03d}' for i in range(1, 4)]
                or any(record.get('status') != 'ok' for record in smoke)):
            raise ValueError('Development requires exact inspected successful smoke')
    return receipt


def load_backend(plan):
    """Only model-load entry point, after lock, receipt, claim and asset verification."""
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['OMP_NUM_THREADS'] = '4'
    os.environ['MKL_NUM_THREADS'] = '4'
    sys.path.insert(0, str(MODEL_ROOT))
    import torch
    import modeling_openjev
    if Path(modeling_openjev.__file__).resolve() != (MODEL_ROOT / 'modeling_openjev.py').resolve():
        raise ValueError('Unexpected Alex model source')
    agent = modeling_openjev.OpenJevCrossEncoder(str(MODEL), device='mps',
        dtype=torch.float32, bs=4, max_len=4096)
    parameter = next(agent.model.parameters())
    if (str(parameter.device) != 'mps:0' or str(parameter.dtype) != 'torch.float32'
            or agent.bs != 4 or agent.max_len != 4096
            or agent.template != plan['nli_template']):
        raise ValueError('Loaded Alex runtime differs from frozen MPS FP32 controls')
    return agent


def verify_output(plan, phase, stage):
    folder = phase_path(phase)
    raw = read_jsonl(folder / f'{stage}.raw.jsonl')
    records = read_jsonl(folder / f'{stage}.records.jsonl')
    journal = read_jsonl(folder / f'{stage}.journal.jsonl')
    count = plan['stage_inputs'][stage]['limit']
    if (len(raw) != count or len(records) != count
            or [row.get('event') for row in journal] !=
            ['phase_started'] + ['request_started', 'request_completed'] * count + ['phase_completed']
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('Alex stage incomplete; preserve partial evidence')
    for i, (capture, record, request) in enumerate(zip(raw, records, plan['requests'])):
        started, completed = journal[2*i+1:2*i+3]
        try:
            prediction = project_probabilities(capture['nli_probabilities'])
            status = 'ok'
        except ValueError:
            prediction = None; status = 'invalid_output'
        if (capture.get('id') != request['id'] or record.get('id') != request['id']
                or started.get('id') != request['id']
                or completed.get('id') != request['id']
                or capture.get('attempt_id') != started.get('attempt_id')
                or record.get('attempt_id') != started.get('attempt_id')
                or completed.get('attempt_id') != started.get('attempt_id')
                or capture.get('request_sha256') != request['request_sha256']
                or record.get('request_sha256') != request['request_sha256']
                or started.get('request_sha256') != request['request_sha256']
                or capture.get('nli_inputs') != request['nli_inputs']
                or capture.get('hypothesis_order') != [[key, value] for key in KEYS for value in VALUES[key]]
                or record.get('raw_sha256') != digest(canonical(capture))
                or record.get('status') != status or record.get('prediction') != prediction
                or record.get('reference_labels_read') is not False
                or record.get('model_path') != plan['model_path']
                or record.get('artifact_revision') != plan['artifact_revision']
                or record.get('device') != plan['runtime']['device']
                or record.get('dtype') != plan['runtime']['dtype']
                or record.get('quantization') != 'none'
                or record.get('batch_size') != 4 or record.get('max_tokens') != 4096
                or type(capture.get('client_prediction_seconds')) not in (int, float)
                or not math.isfinite(capture['client_prediction_seconds'])
                or capture['client_prediction_seconds'] < 0
                or completed.get('status') != status):
            raise ValueError(f'Alex output binding failed at row {i + 1}')
    return file_hash(folder / f'{stage}.records.jsonl')


def _run_locked(plan, plan_sha, phase, stage, receipt_path):
    if phase not in plan['schedule'] or stage not in ('smoke', 'development'):
        raise ValueError('Stage outside frozen Alex native P0 schedule')
    check_predecessors(plan, plan_sha, phase)
    check_receipt(plan, plan_sha, phase, stage, receipt_path)
    folder = phase_path(phase)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f'{stage}.{suffix}').exists() for suffix in
           ('claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl', 'completion.json')):
        raise FileExistsError('Alex stage already attempted; no replay')
    durable_write(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'receipt_sha256': file_hash(receipt_path),
        'policy': 'exclusive one attempt; uncertain started positions are not replayed'})
    append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_started',
        'phase': phase, 'stage': stage})
    agent = load_backend(plan)
    rows, policy = source_rows()
    count = plan['stage_inputs'][stage]['limit']
    for row, request in zip(rows[:count], plan['requests'][:count]):
        pairs = nli_pairs(row['feedback'], policy)
        signatures = native_requests([row], policy, agent.tok, agent.template)[0]['nli_inputs']
        if signatures != request['nli_inputs']:
            raise ValueError('Alex native NLI input/token identity differs before dispatch')
        attempt = str(uuid.uuid4())
        append_row(folder / f'{stage}.journal.jsonl', {'event': 'request_started',
            'id': row['id'], 'attempt_id': attempt,
            'request_sha256': request['request_sha256']})
        start = time.perf_counter()
        try:
            probabilities = agent.predict(pairs).tolist()
            capture = {'id': row['id'], 'attempt_id': attempt,
                'request_sha256': request['request_sha256'],
                'nli_inputs': signatures,
                'hypothesis_order': [[key, value] for key in KEYS for value in VALUES[key]],
                'nli_probabilities': probabilities,
                'client_prediction_seconds': time.perf_counter() - start}
            capture = json.loads(json.dumps(capture))
        except Exception as exc:
            append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_stopped',
                'id': row['id'], 'attempt_id': attempt, 'error_type': type(exc).__name__,
                'cost': 'unknown local hardware/electricity'})
            raise RuntimeError('Alex prediction/capture failed; retain started unknown without replay') from exc
        append_row(folder / f'{stage}.raw.jsonl', capture)
        try: prediction = project_probabilities(probabilities); status = 'ok'
        except ValueError: prediction = None; status = 'invalid_output'
        record = {'id': row['id'], 'attempt_id': attempt, 'phase': phase, 'stage': stage,
            'status': status, 'prediction': prediction, 'request_sha256': request['request_sha256'],
            'input_sha256': request['input_sha256'], 'raw_sha256': digest(canonical(capture)),
            'reference_labels_read': False,
            'model_path': str(MODEL), 'artifact_revision': REVISION,
            'device': 'mps:0', 'dtype': 'torch.float32', 'quantization': 'none',
            'batch_size': 4, 'max_tokens': 4096,
            'client_prediction_seconds': capture['client_prediction_seconds']}
        append_row(folder / f'{stage}.records.jsonl', record)
        append_row(folder / f'{stage}.journal.jsonl', {'event': 'request_completed',
            'id': row['id'], 'attempt_id': attempt, 'status': status})
    append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_completed', 'count': count})
    records_sha = verify_output(plan, phase, stage)
    durable_write(folder / f'{stage}.completion.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'count': count, 'records_sha256': records_sha,
        'raw_sha256': file_hash(folder / f'{stage}.raw.jsonl'),
        'journal_sha256': file_hash(folder / f'{stage}.journal.jsonl')})
    return records_sha


def run_stage(plan, plan_sha, phase, stage, receipt_path):
    HOST_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with HOST_LOCK.open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise RuntimeError('Another native phase owns the host lock') from exc
        try:
            current, current_sha = verify_plan()
            if current_sha != plan_sha or current != plan:
                raise ValueError('Alex plan changed after admission')
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
        durable_write(PLAN_PATH, expected_plan())
        print(file_hash(PLAN_PATH))
        return
    plan, plan_sha = verify_plan()
    if args.action == 'verify':
        print(plan_sha)
        return
    if args.phase not in plan['schedule'] or args.stage not in ('smoke', 'development'):
        parser.error('Exact frozen phase and stage required')
    if args.action == 'command':
        print(canonical({'phase': args.phase, 'stage': args.stage,
            'ids': [x['id'] for x in plan['requests'][:plan['stage_inputs'][args.stage]['limit']]],
            'offline_only': True, 'model_path': str(MODEL), 'revision': REVISION}))
        return
    if not args.receipt: parser.error('Root-reviewed stage receipt required')
    run_stage(plan, plan_sha, args.phase, args.stage, args.receipt)


if __name__ == '__main__': main()
