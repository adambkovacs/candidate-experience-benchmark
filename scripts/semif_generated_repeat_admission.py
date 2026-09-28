#!/usr/bin/env python3
"""Offline-frozen SemIf generated P0/P1/P2 fresh-three admission.

Only freeze and verify are preparation. Run requires a separate reviewed receipt
for one stage and makes one local native call per input under the shared host lock.
"""
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
import time
from pathlib import Path

from development_benchmark import ROOT, read_rows, valid
from specialist_benchmark import generated_messages
from semif_prompt_execution import parse as strict_parse
from semif_repeat_admission import WORK, MODEL, SOURCE, PYTHON, HOST_LOCK, REVISION
from frozen_prompt_variants import compose_instruction

PLAN_PATH = ROOT / 'results/repeatability-v1/semif-generated-fresh-v1/manifest.json'
HISTORICAL_MANIFEST = ROOT / 'results/prompt-comparison-v1-2026-09-24/semif-generated-exact/execution-manifest.json'
HISTORICAL_MANIFEST_SHA = '8d142d97ebe7e7422a231bae14e324adca909baad3c3917311478e5078bfba85'
AUDIT = ROOT / 'docs/GENERATED_SPECIALIST_REPEAT_NEXT_ADMISSION_2026-09-28.md'
PACKAGES = ('torch', 'transformers', 'mlx', 'mlx-lm', 'laya', 'semif-phase1')
SOURCE_COMMIT = 'ca3ba65f142967030ecb453346e94d6f476a69df'
SCHEDULE = [f'fresh{number}/{condition}' for number, order in
            ((1, ('P0', 'P2', 'P1')), (2, ('P1', 'P0', 'P2')), (3, ('P2', 'P1', 'P0')))
            for condition in order]
_HISTORY_SHA = {
    'P0': 'b32d4d78c85ccc24af4b136294db2b6679da39e8dbbcce3a744656297d468df9',
    'P1': '197decf85c8e30f075cd7402c632bf136347b212941cc0808ba35fe2ace281df',
    'P2_reconciliation': '5e48a5ade7b8e4b5aee53aa1fd76c9ca3de4b6af1c8bfcd8cc9dc128ccf161af',
}
_HISTORY = {
    'P0': 'results/semif-generated-bf16-2026-09-23/development.jsonl',
    'P1': 'results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P1-development.jsonl',
    'P2_initial': 'results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P2-development.jsonl',
    'P2_reconciliation': 'results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P2-continuation-v1/reconciliation.json',
}
_STARTED_IN_PROCESS = False


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def new_json(path, value):
    with Path(path).open('x') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    sync_dir(Path(path).parent)


def append(path, value):
    with Path(path).open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def read_json(path):
    return json.loads(Path(path).read_text())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def bound(root, binding):
    path = (Path(root) / binding['file']).resolve()
    path.relative_to(Path(root).resolve())
    if file_hash(path) != binding['sha256']:
        raise ValueError('Bound source changed: ' + binding['file'])
    return path


def source_rows(root=ROOT):
    rows = read_rows(Path(root) / 'data/pilot/inputs.jsonl')
    if len(rows) != 60 or [r.get('id') for r in rows] != [f'DEV-{i:03d}' for i in range(1, 61)]:
        raise ValueError('Exactly 60 ordered input IDs required')
    if any(set(r) != {'id', 'feedback'} or not isinstance(r['feedback'], str) or not r['feedback'] for r in rows):
        raise ValueError('Only input ID and feedback may enter requests')
    policy = (Path(root) / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    return rows, policy


def runtime_and_assets(historical):
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Pinned specialist-venv Python required')
    if not MODEL.is_dir() or not SOURCE.is_dir():
        raise ValueError('Existing model and source required; downloads forbidden')
    if subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != SOURCE_COMMIT:
        raise ValueError('SemIf source revision changed')
    if subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain']):
        raise ValueError('SemIf source checkout is dirty')
    origin = importlib.util.find_spec('semif_phase1').origin
    if Path(origin).resolve() != (SOURCE / 'src/semif_phase1/__init__.py').resolve():
        raise ValueError('SemIf import differs')
    controls = historical['configurations'][0]['controls']
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    if versions != controls['runtime'] or controls['model_revision'] != REVISION:
        raise ValueError('SemIf runtime or revision differs from historical controls')
    assets = controls['adapter_controls']['source_artifact_sha256']
    if set(assets) != {x.name for x in MODEL.iterdir() if x.is_file()}:
        raise ValueError('SemIf asset file set changed')
    for name, expected in assets.items():
        if file_hash(MODEL / name) != expected:
            raise ValueError('SemIf asset changed: ' + name)
    native = read_json(ROOT / 'results/repeatability-v1/semif-native-mlx-v1/manifest.json')
    for config in native['configurations'].values():
        if config['assets_sha256'] != assets or config['artifact_revision'] != REVISION:
            raise ValueError('Generated and native SemIf weights differ')
    preflight = read_json(bound(ROOT, historical['configurations'][0]['native_execution']['token_preflight']))
    if (preflight['artifact_revision'] != REVISION
            or any(importlib.metadata.version(name) != version for name, version in preflight['runtime_versions'].items())):
        raise ValueError('Historical generated token preflight runtime differs')
    source_hashes = preflight['source_hashes']
    # Historical hashes describe prior execution. Pin the current installed code
    # separately so an editable runtime cannot drift behind an unchanged version.
    current_sources = {}
    for name in ('mlx_backend.py', 'generate.py', 'tokenizer_utils.py'):
        matching = [path for path in source_hashes if Path(path).name == name]
        if len(matching) != 1 or not Path(matching[0]).is_file():
            raise ValueError('Required native runtime source missing: ' + name)
        current_sources[matching[0]] = file_hash(matching[0])
    from semif_phase1 import mlx_backend
    if Path(mlx_backend.__file__).resolve() != Path(next(path for path in current_sources if Path(path).name == 'mlx_backend.py')).resolve():
        raise ValueError('Loaded SemIf backend path differs')
    mlx_spec = importlib.util.find_spec('mlx_lm')
    if mlx_spec is None or Path(mlx_spec.origin).parent.resolve() != Path(next(path for path in current_sources if Path(path).name == 'generate.py')).parent.resolve():
        raise ValueError('Loaded MLX-LM package path differs')
    from laya_repeat_admission import hardware_identity
    return {'python': str(PYTHON), 'platform': platform.platform(), 'hardware': hardware_identity(),
            'packages': versions, 'semif_source_commit': SOURCE_COMMIT,
            'semif_origin': origin, 'assets_sha256': assets,
            'historical_source_hashes': source_hashes, 'current_source_hashes': current_sources,
            'native_plan_sha256': file_hash(ROOT / 'results/repeatability-v1/semif-native-mlx-v1/manifest.json')}


def historical_evidence(root, historical):
    if file_hash(HISTORICAL_MANIFEST) != HISTORICAL_MANIFEST_SHA:
        raise ValueError('Historical generated manifest changed')
    evidence = {name: {'file': path, 'sha256': file_hash(Path(root) / path)} for name, path in _HISTORY.items()}
    if any(evidence[name]['sha256'] != expected for name, expected in _HISTORY_SHA.items()):
        raise ValueError('Historical SemIf generated evidence hash differs from audit')
    reconciliation = read_json(root / _HISTORY['P2_reconciliation'])
    if (reconciliation['ambiguous_unfinished_id'] != 'DEV-033'
            or reconciliation['records_with_saved_output'] != 59
            or reconciliation['valid_outputs'] != 57
            or reconciliation['intrinsic_invalid_outputs'] != 2
            or reconciliation['automatic_replay_performed'] is not False
            or reconciliation['original_saved_ids'] != [f'DEV-{i:03d}' for i in range(1, 33)]
            or reconciliation['continuation_saved_ids'] != [f'DEV-{i:03d}' for i in range(34, 61)]):
        raise ValueError('Historical P2 unknown or saved outcomes differ')
    continued = reconciliation['continuation_evidence']['predictions']
    bound(root, continued)
    evidence['P2_continuation'] = continued
    if len(jsonl(root / continued['file'])) != 27:
        raise ValueError('Historical P2 continuation evidence differs')
    if len(jsonl(root / _HISTORY['P2_initial'])) != 32:
        raise ValueError('Historical P2 original evidence differs')
    if len(jsonl(root / _HISTORY['P0'])) != 60 or len(jsonl(root / _HISTORY['P1'])) != 60:
        raise ValueError('Historical P0/P1 evidence differs')
    return evidence


def token_request(tokenizer, messages):
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    guard = tokenizer.encode(prompt)
    add = tokenizer.bos_token is None or not prompt.startswith(tokenizer.bos_token)
    ids = tokenizer.encode(prompt, add_special_tokens=add)
    if guard != ids or len(ids) > 4096 or len(ids) + 2048 > 262144:
        raise ValueError('Generated prompt exceeds exact guard or context')
    return {'messages_sha256': sha(json.dumps(messages, sort_keys=True).encode()), 'rendered_prompt_sha256': sha(prompt.encode()),
            'input_token_ids_sha256': sha(json.dumps(ids).encode()), 'input_tokens': len(ids),
            'generation_add_special_tokens': add}


def expected_plan(root=ROOT):
    root = Path(root)
    historical = read_json(HISTORICAL_MANIFEST)
    if historical['manifest_scope'] != ['semif-generated-bf16']:
        raise ValueError('Historical manifest scope changed')
    config = historical['configurations'][0]
    controls = config['controls']
    if (config['id'] != 'semif-generated-bf16' or config['parent_baseline_id'] != config['id']
            or controls['sampling'] != {'temperature': 0, 'enable_thinking': False}
            or controls['adapter_controls']['max_input_tokens'] != 4096
            or controls['output_reserve_tokens'] != 2048 or controls['parsing'] != 'strict_json'
            or controls['retry_policy'] != 'none' or controls['adapter_controls']['dtype'] != ['mlx.core.bfloat16', 'mlx.core.float32']):
        raise ValueError('Historical SemIf generated controls differ')
    rows, policy = source_rows(root)
    evidence = historical_evidence(root, historical)
    runtime = runtime_and_assets(historical)
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
    if read_json(MODEL / 'config.json')['text_config']['max_position_embeddings'] != controls['context_tokens']:
        raise ValueError('Artifact context differs')
    baseline = generated_messages('', policy)[0]['content']
    for condition, saved in [('P1', jsonl(root / _HISTORY['P1'])),
                             ('P2', jsonl(root / _HISTORY['P2_initial']) +
                              jsonl(root / evidence['P2_continuation']['file']))]:
        by_id = {record['id']: record for record in saved}
        for row in rows:
            if row['id'] == 'DEV-033' and condition == 'P2':
                continue
            actual = generated_messages(row['feedback'], policy, condition, config['parent_baseline_id'])
            prior = by_id[row['id']]
            if prior['messages'] != actual or prior['generated_request_sha256'] != sha(json.dumps(actual, sort_keys=True).encode()):
                raise ValueError('Saved historical generated message differs: ' + condition + '/' + row['id'])
    if bound(root, config['baseline_instruction']).read_text() != baseline:
        raise ValueError('Historical baseline instruction differs')
    requests = {}
    for condition in ('P0', 'P1', 'P2'):
        instruction = compose_instruction(baseline, condition, role='system',
                                          parent_baseline_id=config['parent_baseline_id'], root=root)['instruction']
        if condition != 'P0' and bound(root, config['conditions'][condition]['instruction']).read_text() != instruction:
            raise ValueError('Historical generated variant instruction differs')
        requests[condition] = []
        for row in rows:
            messages = generated_messages(row['feedback'], policy, condition, config['parent_baseline_id'])
            requests[condition].append({'id': row['id'], 'input_sha256': sha(row['feedback'].encode()),
                **token_request(tokenizer, messages)})
    source_files = ('scripts/semif_generated_repeat_admission.py', 'scripts/semif_prompt_execution.py',
                    'scripts/specialist_benchmark.py', 'scripts/frozen_prompt_variants.py',
                    'scripts/jev_benchmark.py', 'scripts/development_benchmark.py',
                    'scripts/semif_repeat_admission.py', 'scripts/laya_repeat_admission.py',
                    'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl',
                    'prompts/variants-v1/manifest.json', 'prompts/variants-v1/P1-classifier.txt',
                    'prompts/variants-v1/P2-classifier-sop.txt')
    return {'schema': 'semif-generated-fresh-three-admission-v1', 'status': 'offline_candidate_no_live_receipts',
            'reference_labels_read': False,
            'historical': {'eligible_as_first_pass': False, 'disposition': 'observational_only',
                           'unknown_started_id': 'DEV-033', 'saved_P2': 59, 'valid_P2': 57,
                           'intrinsic_invalid_P2': 2, 'evidence': evidence,
                           'execution_manifest': {'file': str(HISTORICAL_MANIFEST.relative_to(root)),
                                                  'sha256': HISTORICAL_MANIFEST_SHA}},
            'same_weights_native_control': {'native_manifest_sha256': runtime['native_plan_sha256'],
                'artifact_revision': REVISION,
                'reason': 'Same verified MLX artifact and revision; native option scoring and prompted generation remain different interfaces.'},
            'inputs': {'file': 'data/pilot/inputs.jsonl', 'sha256': file_hash(root / 'data/pilot/inputs.jsonl')},
            'policy_prefix_sha256': sha(policy.encode()),
            'source_sha256': {path: file_hash(root / path) for path in source_files},
            'runtime': runtime, 'model_path': str(MODEL), 'artifact_revision': REVISION,
            'controls': controls, 'requests': requests, 'schedule': SCHEDULE,
            'stage_inputs': {'smoke': {'limit': 3}, 'development': {'limit': 60}},
            'service_policy': {'fresh_process_each_stage': True, 'fresh_model_load_each_stage': True,
                'cache': 'No persistent service or cross-stage KV cache; each stream_generate call begins a fresh request cache. MLX inactive allocator limit remains 256 MiB.',
                'seed': 'No explicit seed; temperature 0 and thinking disabled. Nondeterminism is measured, not assumed absent.',
                'failure': 'One attempt per ID; durable intent and streamed raw events before parse. A fully observed length finish is retained invalid and the phase continues. An incomplete stream or uncertain started request stops without replay.',
                'order': 'P0/P2/P1, then P1/P0/P2, then P2/P1/P0; one global GPU-host stage at a time.'}}


def verify_plan(path=PLAN_PATH):
    actual = read_json(path)
    if actual != expected_plan():
        raise ValueError('Frozen generated plan differs from source, assets, history or runtime')
    return actual, file_hash(path)


def phase_path(phase):
    if phase not in SCHEDULE:
        raise ValueError('Phase outside frozen generated schedule')
    return PLAN_PATH.parent.joinpath(*phase.split('/'))


def verify_runtime_sources(plan):
    for path, expected in plan['runtime']['current_source_hashes'].items():
        if file_hash(path) != expected:
            raise ValueError('Current native runtime source changed: ' + path)


def check_predecessors(plan, plan_sha, phase):
    if phase not in plan['schedule'] or plan['schedule'] != SCHEDULE:
        raise ValueError('Generated phase schedule changed')
    for previous in plan['schedule'][:plan['schedule'].index(phase)]:
        folder = phase_path(previous)
        completion = read_json(folder / 'development.completion.json')
        output_hash = verify_output(plan, previous, 'development')
        if (completion.get('phase') != previous or completion.get('stage') != 'development'
                or completion.get('plan_sha256') != plan_sha
                or completion.get('output_sha256') != output_hash or completion.get('count') != 60):
            raise ValueError('Generated predecessor incomplete: ' + previous)


def check_receipt(plan, plan_sha, phase, stage, receipt_path):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-semif-generated-fresh-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha
            or receipt.get('controller_sha256') != file_hash(__file__)
            or receipt.get('reference_labels_read') is not False):
        raise ValueError('Exact reviewed SemIf generated stage receipt required')
    if stage == 'development':
        folder = phase_path(phase)
        completion = read_json(folder / 'smoke.completion.json')
        smoke_hash = verify_output(plan, phase, 'smoke')
        inspection_path = folder / 'smoke-inspection.json'
        inspection = read_json(inspection_path)
        if (completion.get('plan_sha256') != plan_sha or completion.get('phase') != phase
                or completion.get('count') != 3 or completion.get('output_sha256') != smoke_hash
                or receipt.get('smoke_inspection_sha256') != file_hash(inspection_path)
                or inspection.get('phase') != phase or inspection.get('plan_sha256') != plan_sha
                or inspection.get('smoke_sha256') != smoke_hash
                or inspection.get('inspected_ids') != [f'DEV-{i:03d}' for i in range(1, 4)]
                or inspection.get('approved') is not True
                or not inspection.get('inspector')):
            raise ValueError('Development requires separately inspected three-record smoke')
        records = jsonl(folder / 'smoke.records.jsonl')
        if any(record.get('status') != 'ok' for record in records):
            if not (inspection.get('accepted_unchanged_invalids') is True
                    and all(record['status'] in ('ok', 'invalid_output') for record in records)
                    and inspection.get('failure_class') == 'intrinsic_schema'
                    and inspection.get('inspection_reason')):
                raise ValueError('Intrinsic invalid smoke requires explicit unchanged acceptance')
    return receipt


def verify_output(plan, phase, stage):
    folder = phase_path(phase)
    count = plan['stage_inputs'][stage]['limit']
    records = jsonl(folder / f'{stage}.records.jsonl')
    raw = jsonl(folder / f'{stage}.raw.jsonl')
    events = jsonl(folder / f'{stage}.events.jsonl')
    journal = jsonl(folder / f'{stage}.journal.jsonl')
    if (len(records) != count or len(raw) != count
            or journal[0].get('event') != 'phase_started'
            or journal[-1].get('event') != 'phase_completed'
            or [x['id'] for x in journal if x['event'] == 'request_started'] != [f'DEV-{i:03d}' for i in range(1, count + 1)]):
        raise ValueError('Generated stage incomplete; preserve partial evidence')
    rows, policy = source_rows()
    condition = phase.split('/')[1]
    expected = plan['requests'][condition]
    expected_metadata = jsonl(ROOT / _HISTORY['P0'])[0]['metadata']
    positions = [next((i for i, r in enumerate(expected[:count]) if r['id'] == event.get('id')), -1) for event in events]
    if any(i < 0 for i in positions) or positions != sorted(positions):
        raise ValueError('Generated stream event identity or order differs')
    for index, (record, capture, request, source) in enumerate(zip(records, raw, expected, rows)):
        ident = request['id']
        chunks = [event for event in events if event.get('id') == ident]
        if (record.get('id') != ident or capture.get('id') != ident
                or record.get('phase') != phase or record.get('stage') != stage
                or record.get('request_sha256') != request['messages_sha256']
                or capture.get('request_sha256') != request['messages_sha256']
                or record.get('rendered_prompt_sha256') != request['rendered_prompt_sha256']
                or record.get('input_token_ids_sha256') != request['input_token_ids_sha256']
                or record.get('input_tokens') != request['input_tokens']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('artifact_revision') != REVISION
                or record.get('runtime_versions') != plan['runtime']['packages']
                or record.get('host') != plan['runtime']['platform']
                or record.get('metadata') != capture.get('metadata')
                or record.get('metadata') != expected_metadata
                or capture.get('raw_response') != {'content': ''.join(x['text'] for x in chunks),
                                                  'finish_reason': chunks[-1]['finish_reason'] if chunks else None}
                or capture.get('stream_events_sha256') != sha(''.join(canonical(x) for x in chunks).encode())
                or record.get('raw_sha256') != sha(canonical(capture['raw_response']).encode())):
            raise ValueError(f'Generated output binding failed at {ident}')
        text = capture['raw_response']['content']; finish = capture['raw_response']['finish_reason']
        if finish not in ('stop', 'length'):
            raise ValueError('Completed generated stage includes incomplete stream at ' + ident)
        prediction = strict_parse(text, finish == 'stop')
        status = 'ok' if valid(prediction) else 'invalid_output'
        if record.get('status') != status or record.get('prediction') != prediction:
            raise ValueError('Generated parser projection differs at ' + ident)
        if any(x.get('prompt_tokens') != request['input_tokens'] for x in chunks):
            raise ValueError('Generated token count differs at ' + ident)
    return file_hash(folder / f'{stage}.records.jsonl')


def _run_locked(plan, plan_sha, phase, stage, receipt_path, *, load=None, generate=None, sampler=None):
    global _STARTED_IN_PROCESS
    if _STARTED_IN_PROCESS:
        raise RuntimeError('Each stage requires a fresh process')
    _STARTED_IN_PROCESS = True
    verify_runtime_sources(plan)
    check_predecessors(plan, plan_sha, phase)
    check_receipt(plan, plan_sha, phase, stage, receipt_path)
    folder = phase_path(phase)
    folder.mkdir(parents=True, exist_ok=True)
    if any((folder / f'{stage}.{suffix}').exists() for suffix in
           ('claim.json', 'journal.jsonl', 'events.jsonl', 'raw.jsonl', 'records.jsonl', 'completion.json')):
        raise FileExistsError('Generated stage already attempted; no retry')
    new_json(folder / f'{stage}.claim.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'receipt_sha256': file_hash(receipt_path),
        'controller_sha256': file_hash(__file__), 'policy': 'one attempt; unknown started positions never replayed'})
    append(folder / f'{stage}.journal.jsonl', {'event': 'phase_started', 'phase': phase, 'stage': stage})
    os.environ['HF_HUB_OFFLINE'] = '1'; os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['OMP_NUM_THREADS'] = '4'; os.environ['MKL_NUM_THREADS'] = '4'
    if load is None:
        from semif_phase1 import mlx_backend
        load = mlx_backend.load_model
    if generate is None:
        from mlx_lm import stream_generate
        generate = stream_generate
    if sampler is None:
        from mlx_lm.sample_utils import make_sampler
        sampler = make_sampler
    model, tokenizer, metadata = load(str(MODEL), REVISION, None)
    from transformers import AutoTokenizer
    offline_tokenizer = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
    expected_meta = jsonl(ROOT / _HISTORY['P0'])[0]['metadata']
    actual_meta = dict(metadata, enable_thinking=False, max_tokens=2048, temperature=0)
    if actual_meta != expected_meta:
        raise ValueError('Loaded generated SemIf metadata differs from historical freeze')
    rows, policy = source_rows()
    condition = phase.split('/')[1]
    count = plan['stage_inputs'][stage]['limit']
    for row, request in zip(rows[:count], plan['requests'][condition][:count]):
        messages = generated_messages(row['feedback'], policy, condition, 'semif-generated-bf16')
        identity = {key: value for key, value in request.items() if key not in ('id', 'input_sha256')}
        if token_request(offline_tokenizer, messages) != identity or token_request(tokenizer, messages) != identity:
            raise ValueError('Live generated token request differs before dispatch')
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        append(folder / f'{stage}.journal.jsonl', {'event': 'request_started', 'id': row['id'],
            'request_sha256': request['messages_sha256'], 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        started = time.perf_counter(); chunks = []
        try:
            for piece in generate(model, tokenizer, prompt, max_tokens=2048, sampler=sampler(temp=0)):
                event = {'id': row['id'], 'text': piece.text, 'token': piece.token,
                         'from_draft': piece.from_draft, 'prompt_tokens': piece.prompt_tokens,
                         'generation_tokens': piece.generation_tokens, 'finish_reason': piece.finish_reason}
                append(folder / f'{stage}.events.jsonl', event); chunks.append(event)
        except BaseException as exc:
            append(folder / f'{stage}.journal.jsonl', {'event': 'phase_stopped', 'id': row['id'],
                'error_type': type(exc).__name__, 'started_outcome': 'unknown_no_replay'})
            raise
        raw = {'content': ''.join(x['text'] for x in chunks),
               'finish_reason': chunks[-1]['finish_reason'] if chunks else None}
        capture = {'id': row['id'], 'request_sha256': request['messages_sha256'],
                   'metadata': actual_meta, 'raw_response': raw,
                   'stream_events_sha256': sha(''.join(canonical(x) for x in chunks).encode())}
        append(folder / f'{stage}.raw.jsonl', capture)
        if raw['finish_reason'] not in ('stop', 'length'):
            append(folder / f'{stage}.journal.jsonl', {'event': 'phase_stopped', 'id': row['id'],
                'error_type': 'IncompleteGeneration', 'started_outcome': 'raw_saved_no_replay',
                'finish_reason': raw['finish_reason']})
            raise RuntimeError('Generated stream has no complete terminal; raw saved, no replay')
        prediction = strict_parse(raw['content'], raw['finish_reason'] == 'stop')
        status = 'ok' if valid(prediction) else 'invalid_output'
        record = {'id': row['id'], 'phase': phase, 'stage': stage, 'status': status,
                  'prediction': prediction, 'attempts': 1, 'request_sha256': request['messages_sha256'],
                  'rendered_prompt_sha256': request['rendered_prompt_sha256'],
                  'input_token_ids_sha256': request['input_token_ids_sha256'],
                  'input_tokens': request['input_tokens'], 'input_sha256': request['input_sha256'],
                  'policy_sha256': plan['policy_prefix_sha256'], 'artifact_revision': REVISION,
                  'runtime_versions': plan['runtime']['packages'], 'host': plan['runtime']['platform'],
                  'metadata': actual_meta, 'raw_sha256': sha(canonical(raw).encode()),
                  'elapsed_seconds': time.perf_counter() - started,
                  'output_tokens': chunks[-1]['generation_tokens'] if chunks else 0}
        append(folder / f'{stage}.records.jsonl', record)
        append(folder / f'{stage}.journal.jsonl', {'event': 'request_completed', 'id': row['id'], 'status': status})
    append(folder / f'{stage}.journal.jsonl', {'event': 'phase_completed', 'count': count})
    output_hash = verify_output(plan, phase, stage)
    new_json(folder / f'{stage}.completion.json', {'phase': phase, 'stage': stage,
        'plan_sha256': plan_sha, 'output_sha256': output_hash, 'count': count})
    return output_hash


def run_stage(plan, plan_sha, phase, stage, receipt_path, **fake_transport):
    if phase not in plan['schedule'] or stage not in ('smoke', 'development'):
        raise ValueError('Stage outside frozen generated schedule')
    HOST_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with HOST_LOCK.open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise RuntimeError('Another native stage owns the GPU host') from exc
        try: return _run_locked(plan, plan_sha, phase, stage, receipt_path, **fake_transport)
        finally: fcntl.flock(lock, fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'verify', 'command', 'run'))
    parser.add_argument('--phase'); parser.add_argument('--stage', choices=('smoke', 'development'))
    parser.add_argument('--receipt')
    args = parser.parse_args(argv)
    if args.action == 'freeze':
        PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        new_json(PLAN_PATH, expected_plan()); print(file_hash(PLAN_PATH)); return
    plan, plan_sha = verify_plan()
    if args.action == 'verify': print(plan_sha); return
    if args.phase not in plan['schedule'] or args.stage not in ('smoke', 'development'):
        parser.error('Exact phase and stage required')
    if args.action == 'command':
        print(canonical({'phase': args.phase, 'stage': args.stage,
            'ids': [x['id'] for x in plan['requests'][args.phase.split('/')[1]][:plan['stage_inputs'][args.stage]['limit']]],
            'offline_only': True, 'model_load': False}))
        return
    if not args.receipt: parser.error('Root-reviewed stage receipt required')
    run_stage(plan, plan_sha, args.phase, args.stage, args.receipt)


if __name__ == '__main__': main()
