#!/usr/bin/env python3
"""Build hash-bound, offline native P0 SemIf repeat findings from saved evidence."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import digest, valid
from jev_benchmark import make_payload
from specialist_benchmark import decision_rows

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/semif-native-mlx-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '26cc75f1676ddf72bd9730e43b0e49cf5256427c4e1ec4549fc9ea513b7372c5'
LAYA_MANIFEST = Path('results/repeatability-v1/laya-expanded-cpu-v1/manifest.json')
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
CONFIGS = ('semif-direct', 'semif-serial', 'semif-shared')
DISPLAY = {'semif-direct': 'SemIf · direct native MLX',
           'semif-serial': 'SemIf · serial native MLX',
           'semif-shared': 'SemIf · shared native MLX'}
PASSES = ('original', 'repeat2', 'repeat3')
FIELDS = shared.FIELDS
REVIEW_COMMIT = '9cca967'


def path(root, relative):
    target = (Path(root) / relative).resolve()
    target.relative_to(Path(root).resolve())
    return target


def sha(filename):
    with Path(filename).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(root, relative):
    raw = path(root, relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete or blank JSONL evidence: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


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
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(path(root, MANIFEST).read_text())
    if (plan.get('schema') != 'semif-native-mlx-p0-repeat-admission-v1'
            or plan.get('status') != 'offline_frozen_no_inference'
            or plan.get('reference_labels_used') is not False
            or set(plan.get('configurations', {})) != set(CONFIGS)
            or plan.get('schedule') != [f'{name}/repeat{repeat}/P0'
                                        for repeat in (2, 3) for name in CONFIGS]
            or plan.get('stage_inputs') != {'smoke': {'limit': 3}, 'development': {'limit': 60}}):
        raise ValueError('Frozen SemIf plan shape or schedule differs')
    runtime = plan['runtime']
    if (runtime.get('backend') != 'mlx Metal GPU' or runtime.get('quantization') != 'none'
            or runtime.get('parameter_dtypes') != ['BF16', 'FP32']
            or runtime.get('max_input_tokens') != 4096
            or not all((runtime.get('hardware') or {}).get(k) for k in
                       ('machine_model', 'chip_type', 'physical_memory', 'number_processors'))):
        raise ValueError('Frozen native runtime controls differ')
    bind(LAYA_MANIFEST, plan['laya_plan_sha256'])
    sources = {Path(name) for name in plan['source_sha256']}
    original_root = next((source.parent.parent for source in sources
                          if source.name == 'semif_repeat_admission.py'
                          and source.parent.name == 'scripts'), None)
    if original_root is None:
        raise ValueError('Frozen SemIf source root missing')
    local, external = {}, {}
    for absolute, expected in plan['source_sha256'].items():
        source = Path(absolute)
        try:
            relative = source.relative_to(original_root)
        except ValueError:
            external[absolute] = expected
        else:
            bind(relative, expected)
            local[str(relative)] = expected
    if not {'scripts/semif_repeat_admission.py', 'scripts/specialist_benchmark.py',
            'scripts/jev_benchmark.py', 'scripts/development_benchmark.py',
            'scripts/laya_repeat_admission.py', 'docs/LABELING_GUIDE.md',
            'data/pilot/inputs.jsonl'} <= set(local) or not external:
        raise ValueError('Frozen source proof incomplete')
    bind(LABELS, LABELS_SHA)
    input_rows = rows(root, 'data/pilot/inputs.jsonl')
    label_rows = rows(root, LABELS)
    ids = [f'DEV-{n:03d}' for n in range(1, 61)]
    if ([r.get('id') for r in input_rows] != ids or
            any(set(r) != {'id', 'feedback'} or not isinstance(r['feedback'], str)
                for r in input_rows) or [r.get('id') for r in label_rows] != ids or
            any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels'))
                for r in label_rows)):
        raise ValueError('Input-only membership or provisional references differ')
    policy = path(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != plan['policy_prefix_sha256']:
        raise ValueError('Frozen policy digest differs')
    requests = [{'id': row['id'], 'input_sha256': digest(row['feedback']),
                 'request_sha256': digest(json.dumps(
                     make_payload(row['feedback'], policy, 'not-sent', 'official'), sort_keys=True))}
                for row in input_rows]
    if requests != plan['requests']:
        raise ValueError('Frozen native request binding differs')
    options = [{row['id']: [choice['id'] for choice in row['options']]
                for row in decision_rows(item['feedback'], policy)} for item in input_rows]
    labels = {item['id']: item['proposed_labels'] for item in label_rows}
    return plan, ids, labels, options, external, bind, bindings


def raw_result(raw, config, options, signature):
    decisions = raw.get('decisions') if isinstance(raw, dict) else None
    if not isinstance(decisions, list) or len(decisions) != len(FIELDS):
        raise ValueError('Native raw decision count differs')
    expected_model = {**config['model_metadata'],
                      'serving_config': f"mlx-{config['mode']}-v1"}
    prediction = {}
    valid_distribution = True
    for item, field, frozen in zip(decisions, FIELDS, signature):
        if not isinstance(item, dict) or item.get('id') != field or item.get('option_ids') != options[field]:
            raise ValueError('Native raw option mapping differs')
        actual_signature = {key: item.get(key) for key in
                            ('id', 'prompt_sha256', 'input_ids_sha256', 'answer_token_ids', 'input_tokens')}
        if item.get('model') != expected_model or actual_signature != frozen:
            raise ValueError('Native raw model or request signature differs')
        values = item.get('probabilities')
        if (not isinstance(values, list) or len(values) != len(options[field])
                or any(type(x) not in (int, float) or not math.isfinite(x)
                       or not 0 <= x <= 1 for x in values)
                or abs(sum(values) - 1) > 1e-5):
            valid_distribution = False
            continue
        prediction[field] = options[field][max(range(len(values)), key=values.__getitem__)]
    return prediction if valid_distribution and valid(prediction) else None


def check_records(records, captures, plan, config, requests, options, count, historical):
    if len(records) != count or (not historical and len(captures) != count):
        raise ValueError('SemIf stage has incomplete 3/60 membership')
    load = None
    if historical:
        captures = [None] * count
    for index, (record, capture, request) in enumerate(zip(records, captures, requests[:count])):
        raw = record.get('raw_response') if historical else capture.get('raw_response')
        if not historical and (capture.get('id') != request['id']
                               or capture.get('request_sha256') != request['request_sha256']):
            raise ValueError(f'Native raw capture binding differs at {request["id"]}')
        projected = raw_result(raw, config, options[index],
                               config['native_requests'][index]['decisions'])
        status = 'ok' if projected is not None else 'invalid_output'
        elapsed = record.get('elapsed_seconds')
        model_load = record.get('model_load_seconds')
        if historical and load is None:
            load = model_load
        if (record.get('id') != request['id']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('request_sha256') != request['request_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('requested_model') != config['model_path']
                or record.get('artifact_revision') != config['artifact_revision']
                or record.get('surface') != 'semif local specialist'
                or record.get('mode') != config['mode']
                or record.get('host') != plan['runtime']['platform']
                or record.get('runtime_versions') != plan['runtime']['packages']
                or record.get('metadata') != config['model_metadata']
                or record.get('attempts') != 1 or record.get('status') != status
                or record.get('prediction') != projected
                or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0
                or (historical and (type(model_load) not in (int, float)
                                    or not math.isfinite(model_load) or model_load < 0
                                    or model_load != load))
                or (not historical and (record.get('raw_sha256') != digest(
                    json.dumps(raw, sort_keys=True)) or record.get('phase') is None
                    or record.get('stage') is None))):
            raise ValueError(f'Native record/request/raw mismatch at {request["id"]}')
        if historical and status != 'ok':
            raise ValueError('Frozen historical native pass was not valid')
    return {row['id']: row for row in records}


def class_counts(indexed, ids):
    return {field: dict(sorted(Counter(indexed[rid]['prediction'][field] for rid in ids
                                       if shared.outcome(indexed[rid]) == 'valid').items()))
            for field in FIELDS}


def usage(records, captures, historical):
    raw = ([record['raw_response'] for record in records] if historical else
           [capture['raw_response'] for capture in captures])
    elapsed = [record['elapsed_seconds'] for record in records]
    tokens = sum(item['input_tokens'] for capture in raw for item in capture['decisions'])
    load = records[0]['model_load_seconds'] if historical else None
    return {'requestCount': len(records), 'requestSeconds': elapsed,
            'requestSecondsTotal': sum(elapsed), 'modelLoadSeconds': load,
            'clientRunSecondsLowerBound': sum(elapsed) + load if load is not None else None,
            'tokens': {'input_tokens': tokens, 'output_tokens': None,
                       'cached_input_tokens': None, 'cache_write_input_tokens': None,
                       'reasoning_output_tokens': None},
            'actualCostUsd': None, 'costNote': 'Local hardware and electricity cost not measured.',
            'inferenceSeconds': None}


def historical(root, plan, ids, labels, options, config_id, bind):
    config = plan['configurations'][config_id]
    history = config['historical']
    if (history.get('eligible_as_pass1') is not True
            or history.get('host') != plan['runtime']['platform']
            or history.get('runtime_versions') != plan['runtime']['packages']
            or history.get('model_metadata') != config['model_metadata']
            or config.get('mode') != config_id.removeprefix('semif-')
            or config.get('assets_sha256') != config['model_metadata'].get('source_artifact_sha256')):
        raise ValueError('Frozen native history or model declaration differs')
    folder = Path(history['directory'])
    for stage in ('smoke', 'development'):
        bind(folder / f'{stage}.jsonl', history[f'{stage}_sha256'])
    smoke = rows(root, folder / 'smoke.jsonl')
    development = rows(root, folder / 'development.jsonl')
    check_records(smoke, None, plan, config, plan['requests'], options, 3, True)
    indexed = check_records(development, None, plan, config, plan['requests'], options, 60, True)
    entry = {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
             'predictedClassCounts': class_counts(indexed, ids),
             'usage': usage(development, None, True),
             'evidence': {'smoke': {'path': str(folder / 'smoke.jsonl'),
                                    'sha256': history['smoke_sha256']},
                          'records': {'path': str(folder / 'development.jsonl'),
                                      'sha256': history['development_sha256']},
                          'runnerGitCommit': history['runner_commit'],
                          'runnerSourceSha256': history['runner_sha256']}}
    return entry, indexed


def stage(root, plan, phase, stage_name, options, bind):
    folder = BASE / phase
    files = {key: folder / f'{stage_name}.{suffix}' for key, suffix in
             (('receipt', 'root-review.json'), ('claim', 'claim.json'),
              ('journal', 'journal.jsonl'), ('raw', 'raw.jsonl'),
              ('records', 'records.jsonl'), ('completion', 'completion.json'))}
    evidence = {key: bind(filename) for key, filename in files.items()}
    receipt = json.loads(path(root, files['receipt']).read_text())
    claim = json.loads(path(root, files['claim']).read_text())
    completion = json.loads(path(root, files['completion']).read_text())
    count = plan['stage_inputs'][stage_name]['limit']
    if (receipt.get('kind') != 'root-reviewed-semif-native-p0-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage_name or receipt.get('plan_sha256') != MANIFEST_SHA
            or not str(receipt.get('approval_basis', '')).strip()
            or receipt.get('reviewed_checkpoint_commit') != REVIEW_COMMIT):
        raise ValueError('Native stage receipt differs')
    if claim != {'phase': phase, 'stage': stage_name, 'plan_sha256': MANIFEST_SHA,
                 'receipt_sha256': evidence['receipt']['sha256'],
                 'policy': 'exclusive one attempt; uncertain started positions are not replayed'}:
        raise ValueError('Native stage claim does not bind receipt')
    if completion != {'phase': phase, 'stage': stage_name,
                       'plan_sha256': MANIFEST_SHA,
                       'output_sha256': evidence['records']['sha256'], 'count': count}:
        raise ValueError('Native completion does not bind records')
    journal = rows(root, files['journal'])
    captures = rows(root, files['raw'])
    records = rows(root, files['records'])
    indexed = check_records(records, captures, plan, plan['configurations'][phase.split('/')[0]],
                            plan['requests'], options, count, False)
    if any(record.get('phase') != phase or record.get('stage') != stage_name for record in records):
        raise ValueError('Native record phase or stage binding differs')
    if (len(journal) != 2 + 2 * count
            or journal[0] != {'event': 'phase_started', 'phase': phase, 'stage': stage_name}
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('Native journal not terminal or exact')
    for index, request in enumerate(plan['requests'][:count]):
        started, ended = journal[1 + 2 * index:3 + 2 * index]
        if (started.get('event') != 'request_started' or started.get('id') != request['id']
                or started.get('request_sha256') != request['request_sha256']
                or not started.get('started_utc')
                or ended != {'event': 'request_completed', 'id': request['id'],
                             'status': records[index]['status']}):
            raise ValueError(f'Native journal/request differs at {request["id"]}')
    return indexed, records, captures, evidence


def closed_repeat(root, plan, phase, ids, labels, options, bind):
    folder = BASE / phase
    # A live journal can end mid-line. Read only a terminal phase, never its partial files.
    if not path(root, folder / 'development.completion.json').exists():
        return None, None
    smoke, smoke_records, smoke_raw, smoke_evidence = stage(root, plan, phase, 'smoke', options, bind)
    indexed, records, captures, dev_evidence = stage(root, plan, phase, 'development', options, bind)
    inspection_path = folder / 'smoke-inspection.json'
    inspection_binding = bind(inspection_path)
    inspection = json.loads(path(root, inspection_path).read_text())
    receipt = json.loads(path(root, folder / 'development.root-review.json').read_text())
    checks = inspection.get('checks') or {}
    if (inspection.get('kind') != 'semif-native-p0-smoke-inspection-v1'
            or inspection.get('phase') != phase or inspection.get('plan_sha256') != MANIFEST_SHA
            or inspection.get('smoke_sha256') != smoke_evidence['records']['sha256']
            or inspection.get('raw_sha256') != smoke_evidence['raw']['sha256']
            or inspection.get('journal_sha256') != smoke_evidence['journal']['sha256']
            or inspection.get('inspected_ids') != ids[:3] or inspection.get('approved') is not True
            or receipt.get('smoke_inspection_sha256') != inspection_binding['sha256']
            or any(checks.get(key) is not True for key in
                   ('all_status_ok', 'raw_projection_equals_saved_prediction',
                    'native_request_signatures_equal_frozen_history',
                    'all_raw_probability_sums_within_0.00001', 'raw_saved_before_parse'))
            or checks.get('backend') != 'mlx'
            or checks.get('dtype') != ['mlx.core.bfloat16', 'mlx.core.float32']
            or checks.get('quantization') is not None
            or checks.get('model_revision') != plan['configurations'][phase.split('/')[0]]['artifact_revision']
            or any(row['status'] != 'ok' for row in smoke_records)):
        raise ValueError('Development admission does not bind inspected native smoke')
    entry = {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
             'predictedClassCounts': class_counts(indexed, ids),
             'usage': usage(records, captures, False),
             'evidence': {'smoke': smoke_evidence, 'smokeInspection': inspection_binding,
                          'development': dev_evidence}}
    return entry, indexed


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build_one(root, config_id, context):
    plan, ids, labels, options, external, bind, bindings = context
    data = {name: {} for name in PASSES}
    indexed = {}
    data['original']['P0'], indexed['original'] = historical(root, plan, ids, labels,
                                                               options, config_id, bind)
    missing = []
    previous_open = False
    for repeat in ('repeat2', 'repeat3'):
        phase = f'{config_id}/{repeat}/P0'
        entry, saved = closed_repeat(root, plan, phase, ids, labels, options, bind)
        if entry is None:
            missing.append({'pass': repeat, 'condition': 'P0', 'status': 'open_or_not_started'})
            previous_open = True
        else:
            if previous_open:
                raise ValueError('Completed native phase follows an open predecessor')
            data[repeat]['P0'] = entry
            indexed[repeat] = saved
    complete = [name for name in PASSES if 'P0' in data[name]]
    scores = [data[name]['P0']['score'] for name in complete]
    summary = {'P0': {'allFour': stats([item['allFour'] for item in scores]),
                      'fields': {field: stats([item['fields'][field] for item in scores])
                                 for field in FIELDS}}}
    flips = [{'condition': 'P0', 'from': left, 'to': right,
              **shared.flip(indexed[left], indexed[right], ids)}
             for index, left in enumerate(complete) for right in complete[index + 1:]]
    across = {}
    if len(complete) == 3:
        eligible = [rid for rid in ids if all(shared.outcome(indexed[name][rid]) == 'valid'
                                              for name in complete)]
        across['P0'] = {'denominator': len(eligible),
                        'excludedIds': [rid for rid in ids if rid not in eligible],
                        'fields': {field: [rid for rid in eligible if len({indexed[name][rid]['prediction'][field]
                                                                          for name in complete}) > 1]
                                   for field in FIELDS},
                        'fourFieldVector': [rid for rid in eligible if len({tuple(
                            indexed[name][rid]['prediction'][field] for field in FIELDS)
                            for name in complete}) > 1]}
    return {'schema': 'semif-native-repeat-findings-v1', 'configuration': config_id,
            'displayName': DISPLAY[config_id], 'model': config_id,
            'provider': 'Local native MLX', 'method': 'native-output-stability',
            'conditionOrder': ['P0'], 'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items()))
                                     for field in FIELDS},
            'denominator': 60, 'completedConditions': len(complete), 'plannedConditions': 3,
            'missingPasses': missing, 'partialPasses': [], 'passes': data,
            'threePassSummary': summary, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': [],
            'sourceBindings': list(bindings), 'declaredExternalSourceHashes': external,
            'checkpointAssetHashes': plan['configurations'][config_id]['assets_sha256'],
            'hardware': plan['runtime']['hardware'],
            'limitations': ['Only native P0 output stability is measured; generative P1/P2 prompts do not apply.',
                            'The same 60 fictional development records are repeated, not new independent cases.',
                            'Reference labels are provisional and were not used in inference.',
                            'Open or in-flight phases are omitted before reading any partial records.',
                            'Model and source files outside this repository are declared by the frozen plan; this public report does not rehash private workstation assets.',
                            'Per-record elapsed time is client observed, not controlled model-only inference time; new-phase model load is not measured.',
                            'Local hardware and electricity cost are not measured; actual cost is unknown, not zero.']}


def build(root=ROOT, configs=CONFIGS):
    root = Path(root)
    series = [build_one(root, config, source_context(root)) for config in configs]
    return {'schema': 'semif-native-repeat-report-v1', 'series': series,
            'availableConfigurations': [item['configuration'] for item in series]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale SemIf native report: {args.output}')
    else:
        args.output.write_text(content)
    print('SemIf native repeat report checked')


if __name__ == '__main__':
    main()
