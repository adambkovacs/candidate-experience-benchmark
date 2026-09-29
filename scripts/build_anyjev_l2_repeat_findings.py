#!/usr/bin/env python3
"""Build the source-bound native AnyJev L2 outer-CV5 repeat report offline."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(os.environ.get('ANYJEV_L2_REPORT_ROOT', Path(__file__).resolve().parents[1]))
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import build_repeat_findings as shared
from development_benchmark import valid

BASE = Path('results/repeatability-v1/anyjev-l2-cv5-v1')
HISTORY = Path('results/anyjev-l2-cv5-hf517-v1-2026-09-24')
PLAN = BASE / 'repeat2-plan.json'
PLAN_SHA = '970343ad62fa8c3d43bea7e732d4746c98707ed5202baca3e5a32692736ff7d7'
RUN_MANIFEST = BASE / 'repeat2-run-manifest.json'
CONTROLLER = Path('scripts/anyjev_l2_repeat_admission.py')
BASE_RUNNER = Path('scripts/anyjev_l2_cv.py')
PROTOCOL = Path('results/anyjev-l2-protocol-2026-09-24/protocol-v3.json')
FOLDS = Path('results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json')
LABELS = Path('data/pilot/proposed_labels.jsonl')
INPUTS = Path('data/pilot/inputs.jsonl')
FIELDS = shared.FIELDS
PASSES = ('original', 'repeat2', 'repeat3')
IDS = [f'DEV-{n:03d}' for n in range(1, 61)]
SMOKE_IDS = IDS[:3]
HISTORICAL = {
    str(PROTOCOL): 'fc0e4092d3ad99fe6bc70dd800c516ee7a141c2cf055b16511b4834a6dc7c92d',
    str(FOLDS): '7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c',
    str(HISTORY / 'full.jsonl'): '42c5ec0fb172bb33e4cff3b49bd44406332fc1e594cca3bfdc5e6c82dc1ee17e',
    str(HISTORY / 'collection-manifest.json'): '41d27495291170ddd312e9a3e81a4fc23806b515d2e7879d44d0823620d83ab1',
}


def path(root, relative):
    target = (Path(root) / relative).resolve()
    target.relative_to(Path(root).resolve())
    return target


def sha(target):
    with Path(target).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def load_json(root, relative):
    return json.loads(path(root, relative).read_text())


def rows(root, relative):
    data = path(root, relative).read_bytes()
    if not data or not data.endswith(b'\n') or any(not x.strip() for x in data.splitlines()):
        raise ValueError(f'Incomplete JSONL: {relative}')
    return [json.loads(line) for line in data.splitlines()]


def binder(root):
    bindings = []
    def bind(relative, expected=None):
        relative = Path(relative)
        actual = sha(path(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Source hash differs: {relative}')
        item = {'path': str(relative), 'sha256': actual}
        if item not in bindings:
            bindings.append(item)
        return item
    return bind, bindings


def source_context(root):
    bind, bindings = binder(root)
    for source in ('scripts/build_anyjev_l2_repeat_findings.py',
                   'scripts/build_repeat_findings.py',
                   'scripts/development_benchmark.py'):
        bind(source)
    for name, expected in HISTORICAL.items():
        bind(name, expected)
    bind(PLAN, PLAN_SHA)
    plan = load_json(root, PLAN)
    if (plan.get('contract') != 'anyjev-l2-repeat-plan-v1' or plan.get('phase') != 'repeat2'
            or plan.get('status') != 'unexecuted_root_review_pending'
            or plan.get('historical_full_sha256') != HISTORICAL[str(HISTORY / 'full.jsonl')]
            or plan.get('historical_collection_sha256') != HISTORICAL[str(HISTORY / 'collection-manifest.json')]
            or plan.get('protocol_sha256') != HISTORICAL[str(PROTOCOL)]
            or plan.get('fold_sha256') != HISTORICAL[str(FOLDS)]
            or plan.get('smoke_ids') != SMOKE_IDS
            or plan.get('stage_sequence') != ['smoke', 'full']
            or plan.get('planned_smoke_new_rows') != 3
            or plan.get('planned_full_additional_rows') != 57
            or plan.get('full_uses_smoke_rows_and_heads') is not True
            or plan.get('references_in_heldout_requests') is not False
            or plan.get('no_automatic_retry') is not True
            or plan.get('label_boundary') != 'code-enforced 48 train labels per fold; no OS isolation'):
        raise ValueError('Frozen L2 plan or controls differ')
    bind(CONTROLLER, plan['controller_sha256'])
    bind(BASE_RUNNER, plan['base_runner_sha256'])
    bind(RUN_MANIFEST, plan['run_manifest_sha256'])
    if Path(plan['run_manifest']).name != RUN_MANIFEST.name or Path(plan['output_dir']).name != 'repeat2':
        raise ValueError('Frozen output or manifest identity differs')
    bind(LABELS, shared.PINNED_SHA[str(LABELS)])
    bind(INPUTS, plan['input_sha256'])
    labels_rows = rows(root, LABELS)
    input_rows = rows(root, INPUTS)
    if [x.get('id') for x in labels_rows] != IDS or [x.get('id') for x in input_rows] != IDS:
        raise ValueError('Held-out input/reference membership differs')
    if any(x.get('review_version') != '0.2' or not valid(x.get('proposed_labels')) for x in labels_rows):
        raise ValueError('Provisional reference shape differs')
    labels = {x['id']: x['proposed_labels'] for x in labels_rows}
    inputs = {x['id']: x['feedback'] for x in input_rows}
    folds = load_json(root, FOLDS)['folds']
    if (len(folds) != 5 or sorted(x['fold'] for x in folds) != list(range(1, 6))
            or sorted(rid for fold in folds for rid in fold['test_ids']) != IDS
            or any(len(fold['train_ids']) != 48 or len(fold['test_ids']) != 12 or
                   set(fold['train_ids']) & set(fold['test_ids']) for fold in folds)):
        raise ValueError('Outer-fold membership differs')
    fold_of = {rid: fold['fold'] for fold in folds for rid in fold['test_ids']}
    original_root = Path(plan['output_dir']).parents[3]
    return plan, labels, inputs, fold_of, original_root, bind, bindings


def validate_record(record, rid, *, plan, input_text, fold, artifact_sha, run_sha):
    if (record.get('id') != rid or record.get('level') != 'L2'
            or record.get('status') not in ('ok', 'invalid_output')
            or record.get('reference_labels_in_model_prompts') is not False
            or record.get('fold') != fold or record.get('artifact_sha256') != artifact_sha
            or record.get('protocol_sha256') != plan['protocol_sha256']
            or record.get('fold_map_sha256') != plan['fold_sha256']
            or record.get('source_revision') != plan['source_revision']
            or record.get('model_revision') != plan['model_revision']
            or record.get('device') != 'mps' or record.get('dtype') != 'bfloat16'
            or record.get('quantization') != 'none'
            or record.get('input_sha256') != hashlib.sha256(input_text.encode()).hexdigest()
            or record.get('run_manifest_sha256') != run_sha):
        raise ValueError(f'L2 record identity/controls differ: {rid}')
    prediction = record.get('prediction')
    questions = record.get('questions')
    if record['status'] == 'ok':
        if not valid(prediction) or set(questions or {}) != set(FIELDS):
            raise ValueError(f'L2 valid prediction shape differs: {rid}')
        for field in FIELDS:
            q = questions[field]
            probs = q.get('probs')
            if (q.get('label') != prediction[field] or not isinstance(probs, list)
                    or not probs or any(type(p) not in (int, float) or not math.isfinite(p)
                                        or p < 0 or p > 1 for p in probs)
                    or abs(sum(probs) - 1) > 1e-6
                    or q.get('diagnostics') != record['diagnostics'][field]):
                raise ValueError(f'L2 native question projection differs: {rid}/{field}')
    elif valid(prediction):
        raise ValueError('Valid L2 prediction marked invalid')
    elapsed = record.get('elapsed_seconds')
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError(f'L2 client timing missing or invalid: {rid}')
    audit = record.get('prompt_audit')
    if (not isinstance(audit, list) or len(audit) != 4 or
            any(x.get('reference_labels_in_prompt') is not False or
                not isinstance(x.get('prompt_sha256'), list) or len(x['prompt_sha256']) != 1
                for x in audit)):
        raise ValueError(f'L2 prompt audit differs: {rid}')


def validate_collection(root, folder, full, smoke, artifacts, plan, run_sha, bind):
    collection_name = folder / 'collection-manifest.json'
    collection = load_json(root, collection_name)
    if (collection.get('protocol_sha256') != plan['protocol_sha256']
            or collection.get('fold_map_sha256') != plan['fold_sha256']
            or collection.get('output_sha256') != bind(folder / 'full.jsonl')['sha256']
            or collection.get('rows') != 60 or collection.get('held_out_once_per_id') is not True
            or collection.get('fit_count') != 20 or collection.get('run_manifest_sha256') != run_sha
            or collection.get('reference_labels_in_model_prompts') is not False
            or collection.get('composition') != {'reviewed_smoke_ids': SMOKE_IDS,
                'reviewed_smoke_rows': 3, 'new_held_out_rows': 57,
                'execution_order': 'outer_fold_order',
                'canonical_output_order': 'DEV-001..DEV-060',
                'fresh_canonical_60_inference_run': False}
            or collection.get('fold_artifacts') != artifacts
            or full[:3] != smoke):
        raise ValueError('L2 full collection lineage differs')
    return bind(collection_name)


def validate_artifacts(root, folder, fold_of, plan, run_sha, bind):
    artifacts = []
    for number in range(1, 6):
        name = f'fold-{number}-artifacts.json'
        relative = folder / name
        digest = bind(relative)['sha256']
        item = load_json(root, relative)
        heldout = [rid for rid in IDS if fold_of[rid] == number]
        if (item.get('fold') != number or item.get('test_ids') != heldout
                or len(item.get('train_ids', [])) != 48
                or set(item['train_ids']) != set(IDS) - set(heldout)
                or item.get('fit_count') != 4
                or set(item.get('artifacts', {})) != set(FIELDS)
                or item.get('protocol_sha256') != plan['protocol_sha256']
                or item.get('fold_map_sha256') != plan['fold_sha256']
                or item.get('model_revision') != plan['model_revision']
                or item.get('run_manifest_sha256') != run_sha):
            raise ValueError(f'L2 fold artifact identity differs: {number}')
        artifacts.append({'fold': number, 'file': name, 'sha256': digest})
    return artifacts


def historical(root, plan, inputs, fold_of, bind):
    folder = HISTORY
    smoke = rows(root, folder / 'smoke.jsonl')
    full = rows(root, folder / 'full.jsonl')
    if [x.get('id') for x in smoke] != SMOKE_IDS or [x.get('id') for x in full] != IDS:
        raise ValueError('Historical L2 held-out membership differs')
    collection = load_json(root, folder / 'collection-manifest.json')
    run_sha = collection['run_manifest_sha256']
    review_name = folder / 'root-full-review-v1.json'
    review = load_json(root, review_name)
    if (review.get('decision') != 'approved' or review.get('protocol_sha256') != plan['protocol_sha256']
            or review.get('smoke_sha256') != bind(folder / 'smoke.jsonl')['sha256']
            or review.get('runner_sha256') != plan['base_runner_sha256']
            or review.get('run_manifest_sha256') != run_sha):
        raise ValueError('Historical L2 reviewed smoke lineage differs')
    bind(review_name)
    smoke_attempts = rows(root, folder / 'smoke.attempts.jsonl')
    full_attempts = rows(root, folder / 'full.attempts.jsonl')
    if (sorted(x['id'] for x in smoke_attempts) != SMOKE_IDS
            or {json.dumps(x, sort_keys=True) for x in smoke_attempts} !=
               {json.dumps(x, sort_keys=True) for x in smoke}
            or sorted(x['id'] for x in full_attempts) != IDS[3:]
            or {json.dumps(x, sort_keys=True) for x in full_attempts} !=
               {json.dumps(x, sort_keys=True) for x in full[3:]}):
        raise ValueError('Historical L2 attempt/collection composition differs')
    for stage, count in (('smoke', 3), ('full', 57)):
        bind(folder / f'{stage}.attempts.jsonl')
        events = rows(root, folder / f'{stage}.operations.jsonl')
        bind(folder / f'{stage}.operations.jsonl')
        terminal = events[-1]
        if (terminal.get('event') != 'terminal' or terminal.get('status') != 'completed'
                or terminal.get('completed_prediction_records') != count
                or terminal.get('run_manifest_sha256') != run_sha):
            raise ValueError(f'Historical L2 {stage} terminal lineage differs')
    artifacts = validate_artifacts(root, folder, fold_of, plan, run_sha, bind)
    validate_collection(root, folder, full, smoke, artifacts, plan, run_sha, bind)
    for record in full:
        rid = record['id']
        validate_record(record, rid, plan=plan, input_text=inputs[rid], fold=fold_of[rid],
                        artifact_sha=artifacts[fold_of[rid]-1]['sha256'], run_sha=run_sha)
    return full, {'evidence': {'full': bind(folder / 'full.jsonl'),
                               'collection': bind(folder / 'collection-manifest.json'),
                               'smoke': bind(folder / 'smoke.jsonl')},
                  'instrumentation': 'historical_staged_native_procedure; no wrapper raw captures'}


def _external_relative(root, original_root, item, expected=None, required_parent=None):
    if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
        raise ValueError('Wrapper external binding malformed')
    old = Path(item['path'])
    if expected is not None and old != expected:
        raise ValueError('Wrapper external path differs')
    relative = old.relative_to(original_root)
    if required_parent is not None and relative.parent != required_parent:
        raise ValueError('Wrapper review path escapes phase folder')
    return relative


def completed_stage(root, phase, stage, plan_name, plan, original_root, bind):
    folder = BASE / phase
    completion_name = folder / f'{stage}.repeat-completion.json'
    completion = load_json(root, completion_name)
    if (completion.get('contract') != 'anyjev-l2-repeat-completion-v1'
            or completion.get('phase') != phase or completion.get('stage') != stage
            or completion.get('status') != 'completed'
            or completion.get('controller_sha256') != plan['controller_sha256']):
        raise ValueError('L2 wrapper completion identity differs')
    names = [f'{stage}.raw.jsonl', f'{stage}.operations.jsonl',
             f'{stage}.attempts.jsonl', f'{stage}.jsonl']
    names += ([f'fold-{n}-artifacts.json' for n in (1, 4, 5)] if stage == 'smoke' else
              ['collection-manifest.json', 'smoke.repeat-completion.json'] +
              [f'fold-{n}-artifacts.json' for n in range(1, 6)])
    if set(completion.get('stage_bindings', {})) != set(names):
        raise ValueError('L2 wrapper stage bindings differ')
    evidence = {'completion': bind(completion_name)}
    for name in names:
        evidence[name] = bind(folder / name, completion['stage_bindings'][name])
    external = completion.get('external_bindings')
    if not isinstance(external, dict) or set(external) != {'plan', 'review', 'run_manifest', 'base_runner'}:
        raise ValueError('L2 wrapper external bindings differ')
    expected = {'plan': original_root / plan_name,
                'review': original_root / BASE / f'{phase}-{stage}.root-review.json',
                'run_manifest': Path(plan['run_manifest']),
                'base_runner': original_root / BASE_RUNNER}
    for key, absolute in expected.items():
        relative = _external_relative(root, original_root, external[key], absolute,
                                      BASE if key == 'review' else None)
        evidence[key] = bind(relative, external[key]['sha256'])
    if external['plan']['sha256'] != bind(plan_name)['sha256'] or external['base_runner']['sha256'] != plan['base_runner_sha256'] or external['run_manifest']['sha256'] != plan['run_manifest_sha256']:
        raise ValueError('L2 wrapper source bindings differ')
    review = load_json(root, _external_relative(root, original_root, external['review'],
                            expected=expected['review'], required_parent=BASE))
    if any(review.get(k) != v for k, v in {'decision': 'approved', 'phase': phase,
            'stage': stage, 'plan_sha256': external['plan']['sha256'],
            'controller_sha256': plan['controller_sha256'],
            'scope': 'one native L2 stage only'}.items()):
        raise ValueError('L2 stage review differs')
    if stage == 'full':
        smoke_completion = folder / 'smoke.repeat-completion.json'
        if (completion.get('smoke_completion_sha256') != bind(smoke_completion)['sha256']
                or completion.get('base_smoke_review_sha256') is None):
            raise ValueError('L2 smoke dependency changed')
        smoke_review_absolute = Path(completion.get('base_smoke_review_path', ''))
        expected_smoke_review = original_root / BASE / f'{phase}-smoke-inspection.json'
        if smoke_review_absolute != expected_smoke_review:
            raise ValueError('L2 base smoke review path differs')
        evidence['baseSmokeReview'] = bind(smoke_review_absolute.relative_to(original_root),
                                           completion['base_smoke_review_sha256'])
        base_review = load_json(root, smoke_review_absolute.relative_to(original_root))
        if (base_review.get('decision') != 'approved'
                or base_review.get('protocol_sha256') != plan['protocol_sha256']
                or base_review.get('smoke_sha256') != bind(folder / 'smoke.jsonl')['sha256']
                or base_review.get('runner_sha256') != plan['base_runner_sha256']
                or base_review.get('run_manifest_sha256') != plan['run_manifest_sha256']):
            raise ValueError('L2 base smoke review controls differ')
        if (review.get('smoke_raw_sha256') != bind(folder / 'smoke.raw.jsonl')['sha256']
                or review.get('smoke_rows_sha256') != bind(folder / 'smoke.jsonl')['sha256']
                or review.get('smoke_completion_sha256') != bind(smoke_completion)['sha256']):
            raise ValueError('L2 full review lacks exact inspected smoke')
    raw = rows(root, folder / f'{stage}.raw.jsonl')
    events = rows(root, folder / f'{stage}.operations.jsonl')
    expected_new = 3 if stage == 'smoke' else 57
    expected_fits = 12 if stage == 'smoke' else 8
    if (not events or events[0].get('event') != 'run_started'
            or events[0].get('stage') != stage
            or events[0].get('run_manifest_sha256') != plan['run_manifest_sha256']
            or events[0].get('runner_sha256') != plan['base_runner_sha256']
            or events[-1].get('event') != 'terminal'
            or events[-1].get('status') != 'completed'
            or events[-1].get('completed_prediction_records') != expected_new
            or events[-1].get('native_fit_calls_completed') != expected_fits
            or events[-1].get('native_prediction_calls_completed') != expected_new * 4
            or events[-1].get('run_manifest_sha256') != plan['run_manifest_sha256']
            or any(event.get('status') == 'failed' for event in events)):
        raise ValueError('L2 base native journal is not terminal complete')
    finished = [e for e in events if e.get('event') == 'finished' and
                e.get('status') == 'ok' and e.get('operation') in ('fit_head', 'predict')]
    if len(raw) != len(finished) or len(raw) != (24 if stage == 'smoke' else 236):
        raise ValueError('L2 raw/operation count differs')
    for capture, event in zip(raw, finished):
        if (capture.get('operation') != event.get('operation') or
                capture.get('identity') != {key: event.get(key) for key in capture.get('identity', {})}):
            raise ValueError('L2 raw native operation identity differs')
    if completion.get('raw_sha256') != evidence[f'{stage}.raw.jsonl']['sha256']:
        raise ValueError('L2 wrapper raw digest differs')
    return evidence, raw


def repeat(root, phase, plan_name, plan, labels, inputs, fold_of, original_root, bind):
    folder = BASE / phase
    if not path(root, folder / 'full.repeat-completion.json').exists():
        return None, {'pass': phase, 'condition': 'P0',
                      'status': 'not_completed'}
    smoke_evidence, smoke_raw = completed_stage(root, phase, 'smoke', plan_name, plan, original_root, bind)
    full_evidence, full_raw = completed_stage(root, phase, 'full', plan_name, plan, original_root, bind)
    smoke = rows(root, folder / 'smoke.jsonl')
    full = rows(root, folder / 'full.jsonl')
    smoke_attempts = rows(root, folder / 'smoke.attempts.jsonl')
    full_attempts = rows(root, folder / 'full.attempts.jsonl')
    if ([x.get('id') for x in smoke] != SMOKE_IDS
            or sorted(x.get('id') for x in smoke_attempts) != SMOKE_IDS
            or [x.get('id') for x in full] != IDS
            or sorted(x.get('id') for x in full_attempts) != IDS[3:]
            or {json.dumps(x, sort_keys=True) for x in smoke_attempts} !=
               {json.dumps(x, sort_keys=True) for x in smoke}
            or full[:3] != smoke
            or {json.dumps(x, sort_keys=True) for x in full[3:]} !=
               {json.dumps(x, sort_keys=True) for x in full_attempts}):
        raise ValueError('L2 smoke/full held-out composition differs')
    artifacts = validate_artifacts(root, folder, fold_of, plan, plan['run_manifest_sha256'], bind)
    validate_collection(root, folder, full, smoke, artifacts, plan,
                        plan['run_manifest_sha256'], bind)
    captures = smoke_raw + full_raw
    raw_predict = {(item['identity']['id'], item['identity']['question']): item['result']
                   for item in captures if item['operation'] == 'predict'}
    if len(raw_predict) != 60 * 4:
        raise ValueError('L2 raw prediction membership differs')
    raw_fit = {(item['identity']['fold'], item['identity']['question']): item['result']
               for item in captures if item['operation'] == 'fit_head'}
    if len(raw_fit) != 20:
        raise ValueError('L2 raw fit membership differs')
    for number in range(1, 6):
        artifact = load_json(root, folder / f'fold-{number}-artifacts.json')
        for field in FIELDS:
            if raw_fit[(number, field)] != artifact['artifacts'][field]:
                raise ValueError(f'L2 raw fit artifact differs: {number}/{field}')
    for record in full:
        rid = record['id']
        validate_record(record, rid, plan=plan, input_text=inputs[rid], fold=fold_of[rid],
                        artifact_sha=artifacts[fold_of[rid]-1]['sha256'],
                        run_sha=plan['run_manifest_sha256'])
        for field in FIELDS:
            decision = raw_predict[(rid, field)]
            if (not isinstance(decision, list) or len(decision) != 1
                    or decision[0].get('level') != 'L2'
                    or decision[0].get('probs') != record['questions'][field]['probs']
                    or decision[0].get('diagnostics') != record['questions'][field]['diagnostics']):
                raise ValueError(f'L2 raw prediction differs from row: {rid}/{field}')
    return (full, {'evidence': {'smoke': smoke_evidence, 'full': full_evidence},
                   'instrumentation': 'wrapper raw-before-projection and terminal native journals'}), None


def usage(records):
    seconds = [x['elapsed_seconds'] for x in records]
    return {'requestCount': len(records), 'requestSeconds': seconds,
            'requestSecondsTotal': sum(seconds), 'inferenceSeconds': None,
            'tokens': {key: None for key in ('input_tokens', 'output_tokens',
                'cached_input_tokens', 'cache_write_input_tokens', 'reasoning_output_tokens')},
            'actualCostUsd': None,
            'costNote': 'Local hardware and electricity cost not measured; no token totals recorded.'}


def class_counts(indexed):
    return {field: dict(sorted(Counter(indexed[rid]['prediction'][field] for rid in IDS
            if shared.outcome(indexed[rid]) == 'valid').items())) for field in FIELDS}


def confusion_counts(indexed, labels):
    return {field: {reference: dict(sorted(Counter(
        indexed[rid]['prediction'][field] if shared.outcome(indexed[rid]) == 'valid'
        else '__invalid_or_missing__'
        for rid in IDS if labels[rid][field] == reference).items()))
        for reference in sorted({labels[rid][field] for rid in IDS})} for field in FIELDS}


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / 3 if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def repeat3_sources(root, repeat2_plan, original_root, bind):
    """Bind the separately frozen third pass and its completed predecessor."""
    name = BASE / 'repeat3-plan.json'
    run_name = BASE / 'repeat3-run-manifest.json'
    bind(name)
    plan = load_json(root, name)
    allowed_changes = {'phase', 'output_dir', 'run_manifest', 'run_manifest_sha256',
                       'prior_completion_sha256'}
    if (set(plan) != set(repeat2_plan) | {'prior_completion_sha256'}
            or any(plan[key] != value for key, value in repeat2_plan.items()
                   if key not in allowed_changes)
            or plan.get('phase') != 'repeat3'
            or plan.get('output_dir') != str(original_root / BASE / 'repeat3')
            or plan.get('run_manifest') != str(original_root / run_name)
            or plan.get('prior_completion_sha256') !=
               bind(BASE / 'repeat2/full.repeat-completion.json')['sha256']):
        raise ValueError('Repeat3 frozen plan or predecessor differs')
    bind(run_name, plan['run_manifest_sha256'])
    run = load_json(root, run_name)
    previous_run = load_json(root, RUN_MANIFEST)
    stable = ('contract', 'protocol_sha256', 'fold_sha256', 'runner_sha256',
              'helper_sha256', 'source_revision', 'model_revision', 'model_path',
              'device', 'dtype', 'quantization', 'batch_size', 'max_context',
              'gpu_lock', 'smoke_ids', 'full_collection', 'compatibility',
              'historical_collection_sha256')
    if (any(run.get(key) != previous_run.get(key) for key in stable)
            or run.get('repeat_phase') != 'repeat3'
            or run.get('output_dir') != plan['output_dir']):
        raise ValueError('Repeat3 run controls differ')
    return plan, name


def build(root=ROOT):
    root = Path(root)
    plan, labels, inputs, fold_of, original_root, bind, bindings = source_context(root)
    data = {name: {} for name in PASSES}
    indexed = {}
    records, detail = historical(root, plan, inputs, fold_of, bind)
    indexed['original'] = {x['id']: x for x in records}
    data['original']['P0'] = {'completionStatus': 'complete', 'score': shared.score(indexed['original'], labels, IDS),
                              'predictedClassCounts': class_counts(indexed['original']),
                              'usage': usage(records), **detail}
    missing = []
    repeat2, state = repeat(root, 'repeat2', PLAN, plan, labels, inputs, fold_of, original_root, bind)
    if repeat2 is None:
        missing.append(state)
    else:
        records, detail = repeat2
        indexed['repeat2'] = {x['id']: x for x in records}
        data['repeat2']['P0'] = {'completionStatus': 'complete',
            'score': shared.score(indexed['repeat2'], labels, IDS),
            'predictedClassCounts': class_counts(indexed['repeat2']),
            'usage': usage(records), **detail}
    repeat3_plan = BASE / 'repeat3-plan.json'
    if not path(root, repeat3_plan).exists():
        if path(root, BASE / 'repeat3').exists():
            raise ValueError('Repeat3 evidence exists without frozen plan')
        missing.append({'pass': 'repeat3', 'condition': 'P0', 'status': 'plan_not_frozen'})
    else:
        if repeat2 is None:
            raise ValueError('Repeat3 plan exists before verified repeat2 completion')
        plan3, name3 = repeat3_sources(root, plan, original_root, bind)
        repeat3, state = repeat(root, 'repeat3', name3, plan3, labels, inputs,
                                fold_of, original_root, bind)
        if repeat3 is None:
            missing.append(state)
        else:
            records, detail = repeat3
            indexed['repeat3'] = {x['id']: x for x in records}
            data['repeat3']['P0'] = {'completionStatus': 'complete',
                'score': shared.score(indexed['repeat3'], labels, IDS),
                'predictedClassCounts': class_counts(indexed['repeat3']),
                'usage': usage(records), **detail}
    complete = [name for name in PASSES if 'P0' in data[name]]
    scores = [data[name]['P0']['score'] for name in complete]
    flips = [{'condition': 'P0', 'from': left, 'to': right,
              **shared.flip(indexed[left], indexed[right], IDS)}
             for n, left in enumerate(complete) for right in complete[n+1:]]
    ranges = {'P0': {'allFour': stats([x['allFour'] for x in scores]),
                      'fields': {field: stats([x['fields'][field] for x in scores]) for field in FIELDS}}}
    across = {}
    if len(complete) == 3:
        eligible = [rid for rid in IDS if all(shared.outcome(indexed[name][rid]) == 'valid'
                    for name in complete)]
        across['P0'] = {'denominator': len(eligible),
            'excludedIds': [rid for rid in IDS if rid not in eligible],
            'fields': {field: [rid for rid in eligible if len({indexed[name][rid]['prediction'][field]
                       for name in complete}) > 1] for field in FIELDS},
            'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[name][rid]['prediction'][field]
                       for field in FIELDS) for name in complete}) > 1]}
    return {'schema': 'anyjev-l2-native-repeat-findings-v1',
        'configuration': 'anyjev-qwen06-native-l2-outer-cv5-hf517-adapter-v1',
        'displayName': 'AnyJev Qwen3 0.6B · native L2 outer CV5',
        'provider': 'Local native MPS', 'method': 'native-output-stability',
        'conditionOrder': ['P0'], 'passOrder': list(PASSES),
        'referenceVersion': '0.2',
        'referenceStatus': 'AI reviewed provisional, not independent adjudication',
        'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in IDS).items()))
                                 for field in FIELDS},
        'confusionCounts': {name: confusion_counts(indexed[name], labels) for name in complete},
        'confusionOrientation': 'rows: provisional reference; columns: observed prediction',
        'denominator': 60, 'completedConditions': len(complete), 'plannedConditions': 3,
        'passes': data, 'missingPasses': missing, 'partialPasses': [],
        'threePassSummary': ranges, 'pairwiseFlips': flips,
        'changesAcrossThreePasses': across, 'withinPassPromptDeltas': [],
        'predictedClassCounts': {name: data[name]['P0']['predictedClassCounts'] for name in complete},
        'sourceBindings': bindings,
        'declaredModelAssetHashes': plan['model_assets'],
        'declaredModelArtifactManifestSha256': plan['model_asset_manifest_sha256'],
        'declaredAnyJevSourceRevision': plan['source_revision'],
        'interpretation': [
            'L2 refits a native decision head on 48 training records within each of five outer folds. Each held-out record is scored once; the full set reuses three reviewed smoke outputs and heads.',
            'The historical pass established the staged native procedure; new repeats add raw-before-projection and wrapper completion evidence. This instrumentation difference is disclosed.',
            'Client elapsed time includes local runtime overhead. Native token totals, isolated inference time, and local hardware cost were not measured.'],
        'limitations': [
            'Training labels are confined by code to each fold, without operating-system isolation.',
            'Historical and new instrumentation differ; model/source/runtime controls are frozen by the plan.',
            'Only P0 applies to this native calibration method.',
            'Provisional v0.2 references are not independent adjudication.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    value = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != value:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(value)
    print('AnyJev L2 report built')


if __name__ == '__main__':
    main()
