#!/usr/bin/env python3
"""Offline-frozen fresh-three AnyJev HF generation control; run needs a stage receipt."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import sys
import time
import uuid
from pathlib import Path

import anyjev_raw_repeat_admission as shared
from anyjev_benchmark import verify_artifact
from anyjev_generation_control import control_messages, parse_generated
from development_benchmark import ROOT, digest

WORK = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work')
MODEL = WORK / 'anyjev-qwen06-model'
PYTHON = WORK / 'specialist-venv/bin/python'
PLAN_PATH = ROOT / 'results/repeatability-v1/anyjev-generated-p0p1p2-v1/manifest.json'
HOST_LOCK = shared.HOST_LOCK
REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
PARENT = 'anyjev-qwen06-generated-control'
MODEL_ID = 'Qwen/Qwen3-0.6B'
TOKEN_PREFLIGHT = ROOT / 'results/anyjev-generated-phase2-token-preflight-2026-09-23.json'
EXACT_MANIFEST = ROOT / 'results/prompt-comparison-v1-2026-09-24/anyjev-generated-exact/execution-manifest.json'
TOKEN_PREFLIGHT_SHA = 'df1c9d77fca4f4e161fdc136ae17ff3be00d8cdb90f72c849793e5aca01e49b2'
EXACT_MANIFEST_SHA = 'd05e1aae78553ad885aa35b9b91f4849a9b59fae3ffc94b4abec9bc3f3c5870f'
HISTORY = {
    'P0': ('results/anyjev-qwen06-generated-mps-2026-09-23/development.jsonl',
           '0018a1e2f7db62f2d65af1fdb59ff8194f11d6af57b5d164801dcd425fe18d14', 0),
    'P1': ('results/prompt-comparison-v1-2026-09-24/anyjev-generated-exact/P1-development.jsonl',
           '1909242d779350d36ffec32da66459363d03e6f5ee5602e5c22123fe6545236d', 0),
    'P2': ('results/prompt-comparison-v1-2026-09-24/anyjev-generated-exact/P2-development.jsonl',
           '1b432869380647970046e3cd33c34bdc3bfb68ddaef021c52f02b53f194339c9', 30),
}
SCHEDULE = ('fresh1/P0', 'fresh1/P1', 'fresh1/P2',
            'fresh2/P1', 'fresh2/P2', 'fresh2/P0',
            'fresh3/P2', 'fresh3/P0', 'fresh3/P1')
PACKAGES = ('torch', 'transformers', 'numpy')
MAX_INPUT = 4096
MAX_NEW = 4096
CONTEXT = 40960


def file_hash(path):
    return shared.file_hash(path)


def read_json(path):
    return shared.read_json(path)


def read_jsonl(path):
    data = Path(path).read_bytes()
    if not data.endswith(b'\n') or any(not line for line in data.splitlines()):
        raise ValueError(f'Incomplete JSONL: {path}')
    return [json.loads(line) for line in data.splitlines()]


def _asset_hashes(manifest):
    return {item['rfilename']: file_hash(MODEL / item['rfilename'])
            for item in manifest['siblings']}


def request_signatures(rows, policy, tok):
    out = {}
    for condition in ('P0', 'P1', 'P2'):
        signatures = []
        for row in rows:
            messages = control_messages(row['feedback'], policy, condition, PARENT)
            prompt = tok.apply_chat_template(messages, tokenize=False,
                                             add_generation_prompt=True, enable_thinking=False)
            ids = tok.encode(prompt, add_special_tokens=False)
            if not 0 < len(ids) <= MAX_INPUT or len(ids) + MAX_NEW > CONTEXT:
                raise ValueError(f'Full generated prompt exceeds frozen bounds: {condition}/{row["id"]}')
            signatures.append({'id': row['id'], 'input_sha256': digest(row['feedback']),
                               'messages_sha256': digest(json.dumps(messages, sort_keys=True)),
                               'rendered_prompt_sha256': digest(prompt),
                               'input_ids_sha256': digest(json.dumps(ids)),
                               'input_tokens': len(ids)})
        out[condition] = signatures
    return out


def verify_history(rows, policy, signatures):
    if file_hash(TOKEN_PREFLIGHT) != TOKEN_PREFLIGHT_SHA or file_hash(EXACT_MANIFEST) != EXACT_MANIFEST_SHA:
        raise ValueError('Historical generated preflight or manifest bytes differ')
    preflight = read_json(TOKEN_PREFLIGHT)
    if (preflight.get('artifact_revision') != REVISION
            or preflight.get('artifact_repo') != MODEL_ID
            or preflight.get('settings', {}).get('max_input_tokens') != MAX_INPUT
            or preflight['settings'].get('max_new_tokens') != MAX_NEW
            or preflight['settings'].get('model_max_position_embeddings') != CONTEXT):
        raise ValueError('Historical generated controls differ')
    for condition in ('P0', 'P1', 'P2'):
        saved = preflight['conditions'][condition]['records']
        if len(saved) != 60:
            raise ValueError('Historical token preflight incomplete')
        for expected, actual in zip(signatures[condition], saved):
            for key in ('id', 'input_sha256', 'messages_sha256',
                        'rendered_prompt_sha256', 'input_tokens'):
                if expected[key] != actual.get(key):
                    raise ValueError(f'Historical generated token reconstruction differs: {condition}')
    history = {}
    for condition, (name, expected_sha, expected_ok) in HISTORY.items():
        path = ROOT / name
        if file_hash(path) != expected_sha:
            raise ValueError(f'Historical generated output differs: {condition}')
        saved = read_jsonl(path)
        if ([r.get('id') for r in saved] != [r['id'] for r in rows]
                or sum(r.get('status') == 'ok' for r in saved) != expected_ok
                or any(r.get('status') not in ('ok', 'invalid_output')
                       or r.get('attempts') != 1
                       or r.get('input_sha256') != digest(row['feedback'])
                       or r.get('policy_sha256') != digest(policy)
                       or r.get('request_sha256') != signature['messages_sha256']
                       or r.get('input_tokens') != signature['input_tokens']
                       or r.get('requested_model') != MODEL_ID
                       or r.get('artifact_revision') != REVISION
                       or r.get('device') != 'mps:0'
                       or r.get('dtype') != 'torch.bfloat16'
                       or r.get('quantization') != 'none'
                       or r.get('do_sample') is not False
                       or r.get('enable_thinking') is not False
                       or r.get('max_input_tokens') != MAX_INPUT
                       or r.get('max_new_tokens') != MAX_NEW
                       or (condition != 'P0' and
                           (digest(json.dumps(r.get('messages'), sort_keys=True)) != signature['messages_sha256']
                            or r.get('rendered_prompt_sha256') != signature['rendered_prompt_sha256']))
                       or r.get('prediction') != parse_generated(r.get('raw_response'),
                                                                   r.get('finish_reason') == 'stop')
                       for r, row, signature in zip(saved, rows, signatures[condition]))):
            raise ValueError(f'Historical generated outcome lineage differs: {condition}')
        history[condition] = {'file': name, 'sha256': expected_sha,
                              'saved': 60, 'valid': expected_ok,
                              'intrinsic_invalid': 60 - expected_ok}
    return {'historical_only': True,
            'first_pass_eligible': False,
            'reason': 'P0 saved no generated messages or rendered prompt hash; the exact preflight is a source reconstruction.',
            'conditions': history}


def expected_plan():
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    rows, policy = shared.source_rows()
    manifest = verify_artifact(MODEL, REVISION)
    if manifest.get('repo') != MODEL_ID:
        raise ValueError('Generated model identity differs')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
    config = read_json(MODEL / 'config.json')
    if config.get('max_position_embeddings') != CONTEXT:
        raise ValueError('Generated model context differs')
    signatures = request_signatures(rows, policy, tok)
    history = verify_history(rows, policy, signatures)
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    source_names = ('scripts/anyjev_generated_repeat_admission.py',
                    'scripts/anyjev_raw_repeat_admission.py',
                    'scripts/anyjev_benchmark.py',
                    'scripts/anyjev_generation_control.py',
                    'scripts/anyjev_prompt_execution.py',
                    'scripts/frozen_prompt_variants.py',
                    'scripts/jev_benchmark.py',
                    'scripts/development_benchmark.py',
                    'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl')
    return {'schema': 'anyjev-generated-fresh-three-p0p1p2-v1',
            'status': 'offline_frozen_no_inference',
            'surface': 'Matched HF generated JSON control; not AnyJev readout',
            'reference_labels_used': False,
            'source_sha256': {name: file_hash(ROOT / name) for name in source_names},
            'artifact_revision': REVISION, 'model_id': MODEL_ID,
            'model_path': str(MODEL),
            'artifact_manifest_sha256': file_hash(MODEL / 'download-manifest.json'),
            'asset_sha256': _asset_hashes(manifest),
            'historical': history, 'token_preflight_sha256': TOKEN_PREFLIGHT_SHA,
            'exact_execution_manifest_sha256': EXACT_MANIFEST_SHA,
            'policy_prefix_sha256': digest(policy),
            'requests': signatures,
            'runtime': {'python': str(PYTHON), 'platform': platform.platform(),
                        'hardware': shared.hardware_identity(), 'packages': versions,
                        'device': 'mps:0', 'dtype': 'torch.bfloat16',
                        'quantization': 'none', 'do_sample': False,
                        'enable_thinking': False, 'add_generation_prompt': True,
                        'add_special_tokens': False, 'max_input_tokens': MAX_INPUT,
                        'max_new_tokens': MAX_NEW, 'context_tokens': CONTEXT,
                        'pad_token_policy': 'tokenizer pad_token_id or eos_token_id',
                        'parse': 'strict JSON; fences and incomplete output remain invalid',
                        'failure': 'one attempt per ID; no retry or replay after uncertain start'},
            'schedule': list(SCHEDULE),
            'stage_inputs': {'smoke': {'limit': 3}, 'development': {'limit': 60}}}


def verify_plan():
    saved = read_json(PLAN_PATH)
    current = expected_plan()
    if saved != current:
        raise ValueError('Frozen generated plan differs from source, assets, history or runtime')
    return saved, file_hash(PLAN_PATH)


def phase_path(phase):
    if phase not in SCHEDULE:
        raise ValueError('Stage outside generated schedule')
    return PLAN_PATH.parent.joinpath(*phase.split('/'))


def verify_output(plan, phase, stage, tok):
    folder = phase_path(phase)
    count = plan['stage_inputs'][stage]['limit']
    raw = read_jsonl(folder / f'{stage}.raw.jsonl')
    records = read_jsonl(folder / f'{stage}.records.jsonl')
    journal = read_jsonl(folder / f'{stage}.journal.jsonl')
    if (len(raw) != count or len(records) != count
            or [x.get('event') for x in journal] !=
            ['phase_started'] + ['request_started', 'request_completed'] * count + ['phase_completed']
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('Generated stage incomplete; preserve partial evidence')
    condition = phase.split('/')[1]
    for i, (capture, record, request) in enumerate(zip(raw, records, plan['requests'][condition])):
        started, completed = journal[2*i+1:2*i+3]
        ids = capture.get('generated_token_ids')
        eos = capture.get('eos_token_ids')
        if not isinstance(ids, list) or not isinstance(eos, list):
            raise ValueError('Generated raw tokens absent')
        ended = bool(ids and ids[-1] in eos)
        prediction = parse_generated(capture.get('raw_response'), ended)
        status = 'ok' if prediction else 'invalid_output'
        if (capture.get('id') != request['id'] or record.get('id') != request['id']
                or started.get('id') != request['id'] or completed.get('id') != request['id']
                or capture.get('attempt_id') != started.get('attempt_id')
                or record.get('attempt_id') != started.get('attempt_id')
                or completed.get('attempt_id') != started.get('attempt_id')
                or capture.get('messages_sha256') != request['messages_sha256']
                or digest(json.dumps(capture.get('messages'), sort_keys=True)) != request['messages_sha256']
                or started.get('messages_sha256') != request['messages_sha256']
                or capture.get('rendered_prompt_sha256') != request['rendered_prompt_sha256']
                or capture.get('input_ids_sha256') != request['input_ids_sha256']
                or capture.get('input_tokens') != request['input_tokens']
                or capture.get('output_tokens') != len(ids)
                or tok.decode(ids, skip_special_tokens=True) != capture.get('raw_response')
                or capture.get('finish_reason') != ('stop' if ended else 'length')
                or record.get('raw_sha256') != digest(shared.canonical(capture))
                or record.get('input_sha256') != request['input_sha256']
                or record.get('messages_sha256') != request['messages_sha256']
                or record.get('status') != status or record.get('prediction') != prediction
                or record.get('phase') != phase or record.get('stage') != stage
                or record.get('reference_labels_read') is not False
                or record.get('model_id') != plan['model_id']
                or record.get('artifact_revision') != plan['artifact_revision']
                or record.get('device') != 'mps:0' or record.get('dtype') != 'torch.bfloat16'
                or record.get('do_sample') is not False
                or record.get('enable_thinking') is not False
                or completed.get('status') != status
                or type(capture.get('client_generation_seconds')) not in (int, float)
                or not math.isfinite(capture['client_generation_seconds'])
                or capture['client_generation_seconds'] < 0):
            raise ValueError(f'Generated output binding failed at row {i+1}')
    return file_hash(folder / f'{stage}.records.jsonl')


def check_predecessors(plan, plan_sha, phase, tok):
    for earlier in plan['schedule'][:plan['schedule'].index(phase)]:
        folder = phase_path(earlier)
        terminal = read_json(folder / 'development.completion.json')
        records_sha = verify_output(plan, earlier, 'development', tok)
        if (terminal.get('phase') != earlier or terminal.get('stage') != 'development'
                or terminal.get('plan_sha256') != plan_sha
                or terminal.get('records_sha256') != records_sha
                or terminal.get('raw_sha256') != file_hash(folder / 'development.raw.jsonl')
                or terminal.get('journal_sha256') != file_hash(folder / 'development.journal.jsonl')
                or terminal.get('count') != 60):
            raise ValueError(f'Generated predecessor {earlier} not closed')


def check_receipt(plan, plan_sha, phase, stage, receipt_path, tok):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-anyjev-generated-stage-v1'
            or receipt.get('approved') is not True
            or receipt.get('phase') != phase or receipt.get('stage') != stage
            or receipt.get('plan_sha256') != plan_sha
            or receipt.get('controller_sha256') != file_hash(__file__)
            or receipt.get('artifact_sha256') != plan['asset_sha256']['model.safetensors']
            or receipt.get('reference_labels_read') is not False):
        raise ValueError('Missing exact root-reviewed generated stage receipt')
    if stage == 'development':
        folder = phase_path(phase)
        smoke_sha = verify_output(plan, phase, 'smoke', tok)
        terminal = read_json(folder / 'smoke.completion.json')
        inspection_path = folder / 'smoke-inspection.json'
        inspection = read_json(inspection_path)
        smoke = read_jsonl(folder / 'smoke.records.jsonl')
        declarations = inspection.get('records')
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
                or not isinstance(declarations, list) or len(declarations) != 3):
            raise ValueError('Development requires exact generated smoke inspection')
        for observed, declared in zip(smoke, declarations):
            if (declared.get('id') != observed['id']
                    or declared.get('status') != observed['status']
                    or declared.get('prediction') != observed['prediction']
                    or declared.get('raw_sha256') != observed['raw_sha256']
                    or (observed['status'] == 'invalid_output' and
                        (declared.get('accepted_unchanged') is not True
                         or declared.get('failure_class') != 'intrinsic_schema'
                         or not declared.get('inspection_reason')))):
                raise ValueError('Generated smoke inspection does not preserve raw outcome')
    return receipt


def load_backend(plan):
    """Only weight-load entry point, after lock, receipt and exclusive claim."""
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['OMP_NUM_THREADS'] = '4'
    os.environ['MKL_NUM_THREADS'] = '4'
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(str(MODEL), local_files_only=True,
                                                 dtype=torch.bfloat16).to('mps').eval()
    parameter = next(model.parameters())
    if (str(parameter.device) != 'mps:0' or str(parameter.dtype) != 'torch.bfloat16'
            or model.config.max_position_embeddings != CONTEXT):
        raise ValueError('Generated effective device, dtype or context differs')
    return tok, model, torch


def _run_locked(plan, plan_sha, phase, stage, receipt_path, tok):
    if phase not in plan['schedule'] or stage not in ('smoke', 'development'):
        raise ValueError('Stage outside frozen generated schedule')
    check_predecessors(plan, plan_sha, phase, tok)
    check_receipt(plan, plan_sha, phase, stage, receipt_path, tok)
    folder = phase_path(phase)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f'{stage}.{suffix}').exists() for suffix in
           ('claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl', 'completion.json')):
        raise FileExistsError('Generated stage already attempted; no replay')
    shared.durable_write(folder / f'{stage}.claim.json', {
        'phase': phase, 'stage': stage, 'plan_sha256': plan_sha,
        'receipt_sha256': file_hash(receipt_path),
        'policy': 'exclusive one attempt; uncertain started positions are not replayed'})
    shared.append_row(folder / f'{stage}.journal.jsonl', {
        'event': 'phase_started', 'phase': phase, 'stage': stage})
    backend_tok, model, torch = load_backend(plan)
    rows, policy = shared.source_rows()
    condition = phase.split('/')[1]
    count = plan['stage_inputs'][stage]['limit']
    for row, request in zip(rows[:count], plan['requests'][condition][:count]):
        messages = control_messages(row['feedback'], policy, condition, PARENT)
        prompt = backend_tok.apply_chat_template(messages, tokenize=False,
                                                  add_generation_prompt=True, enable_thinking=False)
        ids = backend_tok.encode(prompt, add_special_tokens=False)
        if (digest(json.dumps(messages, sort_keys=True)) != request['messages_sha256']
                or digest(prompt) != request['rendered_prompt_sha256']
                or digest(json.dumps(ids)) != request['input_ids_sha256']
                or len(ids) != request['input_tokens']):
            raise ValueError('Generated request identity differs before dispatch')
        inputs = backend_tok(prompt, return_tensors='pt', add_special_tokens=False)
        if (inputs['input_ids'].shape[1] != len(ids)
                or inputs['input_ids'][0].tolist() != ids):
            raise ValueError('Generated tensor input differs from frozen tokens')
        attempt = str(uuid.uuid4())
        shared.append_row(folder / f'{stage}.journal.jsonl', {
            'event': 'request_started', 'id': row['id'], 'attempt_id': attempt,
            'messages_sha256': request['messages_sha256']})
        start = time.perf_counter()
        try:
            with torch.inference_mode():
                output = model.generate(**{key: value.to('mps') for key, value in inputs.items()},
                                        do_sample=False, max_new_tokens=MAX_NEW,
                                        pad_token_id=backend_tok.pad_token_id or backend_tok.eos_token_id)
            generated_ids = output[0, len(ids):].tolist()
            raw_text = backend_tok.decode(generated_ids, skip_special_tokens=True)
            eos = model.generation_config.eos_token_id
            eos = [eos] if isinstance(eos, int) else eos
            capture = {'id': row['id'], 'attempt_id': attempt,
                       'messages': messages, 'messages_sha256': request['messages_sha256'],
                       'rendered_prompt_sha256': request['rendered_prompt_sha256'],
                       'input_ids_sha256': request['input_ids_sha256'],
                       'input_tokens': len(ids), 'generated_token_ids': generated_ids,
                       'raw_response': raw_text, 'eos_token_ids': eos or [],
                       'output_tokens': len(generated_ids),
                       'finish_reason': 'stop' if generated_ids and generated_ids[-1] in (eos or []) else 'length',
                       'client_generation_seconds': time.perf_counter() - start}
            capture = json.loads(json.dumps(capture))
        except Exception as exc:
            shared.append_row(folder / f'{stage}.journal.jsonl', {
                'event': 'phase_stopped', 'id': row['id'], 'attempt_id': attempt,
                'error_type': type(exc).__name__, 'cost': 'unknown local hardware/electricity'})
            raise RuntimeError('Generated capture failed; retain started unknown without replay') from exc
        shared.append_row(folder / f'{stage}.raw.jsonl', capture)
        prediction = parse_generated(capture['raw_response'], capture['finish_reason'] == 'stop')
        status = 'ok' if prediction else 'invalid_output'
        record = {'id': row['id'], 'attempt_id': attempt, 'phase': phase, 'stage': stage,
                  'status': status, 'prediction': prediction,
                  'raw_sha256': digest(shared.canonical(capture)),
                  'input_sha256': request['input_sha256'],
                  'messages_sha256': request['messages_sha256'],
                  'reference_labels_read': False,
                  'model_id': MODEL_ID, 'artifact_revision': REVISION,
                  'device': 'mps:0', 'dtype': 'torch.bfloat16',
                  'do_sample': False, 'enable_thinking': False,
                  'client_generation_seconds': capture['client_generation_seconds']}
        shared.append_row(folder / f'{stage}.records.jsonl', record)
        shared.append_row(folder / f'{stage}.journal.jsonl', {
            'event': 'request_completed', 'id': row['id'], 'attempt_id': attempt,
            'status': status})
    shared.append_row(folder / f'{stage}.journal.jsonl', {'event': 'phase_completed', 'count': count})
    records_sha = verify_output(plan, phase, stage, backend_tok)
    shared.durable_write(folder / f'{stage}.completion.json', {
        'phase': phase, 'stage': stage, 'plan_sha256': plan_sha, 'count': count,
        'records_sha256': records_sha,
        'raw_sha256': file_hash(folder / f'{stage}.raw.jsonl'),
        'journal_sha256': file_hash(folder / f'{stage}.journal.jsonl')})
    return records_sha


def run_stage(plan, plan_sha, phase, stage, receipt_path):
    HOST_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with HOST_LOCK.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another native phase owns the host lock') from exc
        try:
            current, current_sha = verify_plan()
            if current_sha != plan_sha or current != plan:
                raise ValueError('Generated plan changed after admission')
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            from transformers import AutoTokenizer
            tok = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
            return _run_locked(plan, plan_sha, phase, stage, receipt_path, tok)
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
        shared.durable_write(PLAN_PATH, expected_plan())
        print(file_hash(PLAN_PATH))
        return
    plan, plan_sha = verify_plan()
    if args.action == 'verify':
        print(plan_sha)
        return
    if args.phase not in plan['schedule'] or args.stage not in ('smoke', 'development'):
        parser.error('Exact frozen phase and stage required')
    if args.action == 'command':
        condition = args.phase.split('/')[1]
        print(shared.canonical({'phase': args.phase, 'stage': args.stage,
            'ids': [x['id'] for x in plan['requests'][condition][:plan['stage_inputs'][args.stage]['limit']]],
            'offline_only': True, 'model_id': MODEL_ID, 'revision': REVISION}))
        return
    if not args.receipt:
        parser.error('Root-reviewed stage receipt required')
    run_stage(plan, plan_sha, args.phase, args.stage, args.receipt)


if __name__ == '__main__':
    main()
