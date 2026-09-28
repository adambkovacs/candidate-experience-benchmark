#!/usr/bin/env python3
"""Build an offline, hash-bound P0 stability report for expanded CPU Laya."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import valid
from jev_benchmark import parse_response

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/laya-expanded-cpu-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '1a5a1eea3c18db98c81297bb1f775b9de59936cb06fc486f9b4c5f0d00094261'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
REVIEW_COMMIT = '78818f49f5130c9fe9b011d76b2950646b71971d'
CONFIGS = ('laya-english-expanded-cpu', 'laya-typed-expanded-cpu', 'laya-multilingual-expanded-cpu')
DISPLAY = {'laya-english-expanded-cpu': 'Laya English · expanded CPU',
           'laya-typed-expanded-cpu': 'Laya typed decisions · expanded CPU',
           'laya-multilingual-expanded-cpu': 'Laya multilingual · expanded CPU'}
PASSES = ('original', 'repeat2', 'repeat3')
FIELDS = shared.FIELDS
CONFIG_NOTE = 'Laya expanded P0 repeat; CPU FP32 no quantization; OMP/MKL4; 4096/head512; exact full-input guard; local pinned assets; no retry'


def path(root, relative):
    target = (root / relative).resolve()
    target.relative_to(root.resolve())
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
    if (plan.get('schema') != 'laya-expanded-cpu-p0-repeat-admission-v1'
            or plan.get('status') != 'offline_frozen_no_inference'
            or plan.get('reference_labels_used') is not False
            or set(plan.get('configurations', {})) != set(CONFIGS)
            or plan.get('schedule') != [f'{config}/repeat{repeat}/P0'
                                        for repeat in (2, 3) for config in CONFIGS]
            or plan.get('stage_inputs') != {'smoke': {'offset': 0, 'limit': 3},
                                            'development': {'offset': 0, 'limit': 60}}):
        raise ValueError('Frozen native P0 plan shape or schedule differs')
    runtime = plan['runtime']
    if (runtime.get('device'), runtime.get('dtype'), runtime.get('quantization'),
            runtime.get('max_len'), runtime.get('head_max_len'),
            runtime.get('omp_num_threads'), runtime.get('mkl_num_threads')) != (
            'cpu', 'torch.float32', 'none', 4096, 512, '4', '4'):
        raise ValueError('Frozen CPU execution controls differ')
    hardware = runtime.get('hardware') or {}
    if not all(hardware.get(k) for k in ('machine_model', 'chip_type', 'physical_memory', 'number_processors')):
        raise ValueError('Frozen hardware identity missing')
    source_paths = {Path(name) for name in plan['source_sha256']}
    original_root = next((name.parent.parent for name in source_paths
                          if name.name == 'laya_repeat_admission.py' and name.parent.name == 'scripts'), None)
    if original_root is None:
        raise ValueError('Frozen admission source root missing')
    local_sources = {}
    external_sources = {}
    for absolute, expected in plan['source_sha256'].items():
        source = Path(absolute)
        try:
            relative = source.relative_to(original_root)
        except ValueError:
            external_sources[absolute] = expected
        else:
            bind(relative, expected)
            local_sources[str(relative)] = expected
    required = {'scripts/laya_repeat_admission.py', 'scripts/specialist_benchmark.py',
                'scripts/jev_benchmark.py', 'scripts/development_benchmark.py',
                'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl'}
    if not required <= set(local_sources) or not external_sources:
        raise ValueError('Frozen source proof incomplete')
    bind(LABELS, LABELS_SHA)
    label_rows = rows(root, LABELS)
    ids = [f'DEV-{n:03d}' for n in range(1, 61)]
    if ([r.get('id') for r in label_rows] != ids
            or any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels'))
                   for r in label_rows)
            or [r.get('id') for r in plan['requests']] != ids):
        raise ValueError('Provisional reference or request membership changed')
    labels = {r['id']: r['proposed_labels'] for r in label_rows}
    return plan, ids, labels, original_root, external_sources, bind, bindings


def check_records(records, planned, config, plan, length, historical):
    if len(records) != length:
        raise ValueError('P0 evidence has incomplete 3/60 membership')
    initial_load = None
    for record, request in zip(records, planned[:length]):
        meta = record.get('metadata') or {}
        raw = record.get('raw_response')
        token_lengths = meta.get('untruncated_tokens') or {}
        usage = raw.get('usage') if isinstance(raw, dict) else None
        elapsed = record.get('elapsed_seconds')
        load = record.get('model_load_seconds')
        if initial_load is None:
            initial_load = load
        if (record.get('id') != request['id']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('request_sha256') != request['request_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('requested_model') != config['model_path']
                or record.get('artifact_revision') != config['artifact_revision']
                or record.get('surface') != 'laya local specialist'
                or record.get('mode') != 'expanded' or record.get('host') != plan['runtime']['platform']
                or record.get('runtime_versions') != plan['runtime']['packages']
                or record.get('attempts') != 1 or record.get('status') != 'ok'
                or not valid(record.get('prediction'))
                or record['prediction'] != parse_response(raw, 'laya-rl-agent')
                or meta.get('original_config') != config['original_config']
                or meta.get('effective_config') != config['effective_config']
                or meta.get('device') != 'cpu' or meta.get('dtype') != 'torch.float32'
                or meta.get('parameter_dtype') != 'torch.float32' or meta.get('quantization') != 'none'
                or meta.get('tokenizer_config_sha256_before_load') != config['assets_sha256']['tokenizer/tokenizer_config.json']
                or meta.get('tokenizer_config_sha256_after_load') != config['assets_sha256']['tokenizer/tokenizer_config.json']
                or set(token_lengths) != set(FIELDS)
                or any(type(value) is not int or not 0 < value <= 4096 for value in token_lengths.values())
                or not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int
                or usage['input_tokens'] != sum(token_lengths.values())
                or usage.get('output_tokens') != 0
                or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0
                or type(load) not in (int, float) or not math.isfinite(load) or load < 0
                or load != initial_load):
            raise ValueError(f'Laya raw/request/control evidence differs at {request["id"]}')
        if not historical and record.get('config_note') != CONFIG_NOTE:
            raise ValueError('Repeat runner configuration note differs')
    return {r['id']: r for r in records}


def usage(records):
    elapsed = [r['elapsed_seconds'] for r in records]
    input_tokens = sum(r['raw_response']['usage']['input_tokens'] for r in records)
    output_tokens = sum(r['raw_response']['usage']['output_tokens'] for r in records)
    load = records[0]['model_load_seconds']
    return {'requestCount': len(records), 'requestSeconds': elapsed,
            'requestSecondsTotal': sum(elapsed), 'modelLoadSeconds': load,
            'clientRunSecondsLowerBound': load + sum(elapsed),
            'tokens': {'input_tokens': input_tokens, 'output_tokens': output_tokens,
                       'cached_input_tokens': None, 'cache_write_input_tokens': None,
                       'reasoning_output_tokens': None},
            'actualCostUsd': None, 'costNote': 'Local CPU electricity and hardware cost not measured.',
            'inferenceSeconds': None}


def historical(root, plan, ids, labels, config_id, bind):
    config = plan['configurations'][config_id]
    history = config['historical']
    if (history.get('host') != plan['runtime']['platform']
            or history.get('runtime_versions') != plan['runtime']['packages']
            or history.get('runtime_matches_repeat') is not True
            or len(config.get('assets_sha256', {})) != 5):
        raise ValueError('Historical runtime or checkpoint declaration differs')
    folder = Path(history['directory'])
    for stage in ('smoke', 'development'):
        bind(folder / f'{stage}.jsonl', history[f'{stage}_sha256'])
    smoke = rows(root, folder / 'smoke.jsonl')
    development = rows(root, folder / 'development.jsonl')
    check_records(smoke, plan['requests'], config, plan, 3, True)
    indexed = check_records(development, plan['requests'], config, plan, 60, True)
    return {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
            'predictedClassCounts': class_counts(indexed, ids),
            'usage': usage(development),
            'evidence': {'smoke': {'path': str(folder / 'smoke.jsonl'), 'sha256': history['smoke_sha256']},
                         'records': {'path': str(folder / 'development.jsonl'), 'sha256': history['development_sha256']},
                         'runnerGitCommit': history['runner_git_commit'],
                         'runnerSourceSha256': history['runner_source_sha256']}}, indexed


def expected_argv(original_root, plan, phase, stage):
    config = plan['configurations'][phase.split('/')[0]]
    selected = plan['stage_inputs'][stage]
    output = original_root / BASE / phase / f'{stage}.jsonl'
    return [plan['runtime']['python'], str(original_root / 'scripts/specialist_benchmark.py'),
            '--kind', 'laya', '--mode', 'expanded', '--model-path', config['model_path'],
            '--revision', config['artifact_revision'], '--device', 'cpu',
            '--offset', str(selected['offset']), '--limit', str(selected['limit']),
            '--output', str(output), '--config-note', CONFIG_NOTE]


def stage(root, plan, phase, stage_name, original_root, bind):
    folder = BASE / phase
    receipt_path = folder / f'{stage_name}.root-review.json'
    intent_path = folder / f'{stage_name}.intent.json'
    output_path = folder / f'{stage_name}.jsonl'
    completion_path = folder / f'{stage_name}.completion.json'
    receipt_binding = bind(receipt_path)
    intent_binding = bind(intent_path)
    output_binding = bind(output_path)
    completion_binding = bind(completion_path)
    receipt = json.loads(path(root, receipt_path).read_text())
    intent = json.loads(path(root, intent_path).read_text())
    completion = json.loads(path(root, completion_path).read_text())
    expected_count = plan['stage_inputs'][stage_name]['limit']
    if (receipt.get('kind') != 'root-reviewed-laya-p0-stage-v1'
            or receipt.get('phase') != phase or receipt.get('stage') != stage_name
            or receipt.get('plan_sha256') != MANIFEST_SHA or receipt.get('approved') is not True
            or receipt.get('reviewed_checkpoint_commit') != REVIEW_COMMIT
            or receipt.get('created_by') != 'delegated execution agent'
            or not str(receipt.get('approval_basis', '')).strip()):
        raise ValueError('Stage root-delegated receipt differs')
    if intent != {'phase': phase, 'stage': stage_name, 'plan_sha256': MANIFEST_SHA,
                  'receipt_sha256': receipt_binding['sha256'],
                  'argv': expected_argv(original_root, plan, phase, stage_name),
                  'policy': 'one attempt; interrupted or absent output remains unknown'}:
        raise ValueError('Durable stage intent differs from frozen command')
    if completion != {'phase': phase, 'stage': stage_name, 'plan_sha256': MANIFEST_SHA,
                       'output_sha256': output_binding['sha256'], 'count': expected_count}:
        raise ValueError('Stage completion differs from exact output')
    records = rows(root, output_path)
    indexed = check_records(records, plan['requests'], plan['configurations'][phase.split('/')[0]],
                            plan, expected_count, False)
    return indexed, records, {'receipt': receipt_binding, 'intent': intent_binding,
                              'records': output_binding, 'completion': completion_binding}


def closed_repeat(root, plan, phase, ids, labels, original_root, bind):
    folder = BASE / phase
    # The terminal sidecar is the only first read for a repeat phase. In-flight
    # files may end mid-JSON line and must not enter an offline report.
    if not path(root, folder / 'development.completion.json').exists():
        return None, None
    smoke, smoke_rows, smoke_evidence = stage(root, plan, phase, 'smoke', original_root, bind)
    development, development_rows, dev_evidence = stage(root, plan, phase, 'development', original_root, bind)
    inspection_path = folder / 'smoke-inspection.json'
    inspection_binding = bind(inspection_path)
    inspection = json.loads(path(root, inspection_path).read_text())
    dev_receipt = json.loads(path(root, folder / 'development.root-review.json').read_text())
    smoke_hash = smoke_evidence['records']['sha256']
    if (inspection.get('kind') != 'laya-p0-smoke-inspection-v1'
            or inspection.get('phase') != phase or inspection.get('plan_sha256') != MANIFEST_SHA
            or inspection.get('smoke_sha256') != smoke_hash
            or inspection.get('inspected_ids') != ids[:3] or inspection.get('approved') is not True
            or dev_receipt.get('smoke_inspection_sha256') != inspection_binding['sha256']):
        raise ValueError('Development admission does not bind inspected smoke')
    checks = inspection.get('checks') or {}
    required = ('all_status_ok', 'raw_choices_equal_predictions',
                'all_raw_probability_sums_within_0.001', 'untruncated_full_coverage',
                'tokenizer_config_unchanged')
    if any(checks.get(key) is not True for key in required):
        raise ValueError('Smoke inspection claims incomplete checks')
    if (checks.get('device'), checks.get('dtype'), checks.get('parameter_dtype'),
            checks.get('quantization'), checks.get('effective_max_len'),
            checks.get('effective_head_max_len'), checks.get('raw_model')) != (
            'cpu', 'torch.float32', 'torch.float32', 'none', 4096, 512, 'laya-rl-agent'):
        raise ValueError('Smoke inspection controls differ')
    entry = {'completionStatus': 'complete', 'score': shared.score(development, labels, ids),
             'predictedClassCounts': class_counts(development, ids),
             'usage': usage(development_rows),
             'evidence': {'smoke': smoke_evidence, 'smokeInspection': inspection_binding,
                          'development': dev_evidence}}
    return entry, development


def class_counts(indexed, ids):
    return {field: dict(sorted(Counter(indexed[rid]['prediction'][field]
                                       for rid in ids if shared.outcome(indexed[rid]) == 'valid').items()))
            for field in FIELDS}


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build_one(root, config_id, context):
    plan, ids, labels, original_root, external_sources, bind, _ = context
    data = {name: {} for name in PASSES}
    indexed = {}
    historical_entry, indexed['original'] = historical(root, plan, ids, labels, config_id, bind)
    data['original']['P0'] = historical_entry
    missing = []
    previous_open = False
    for repeat in ('repeat2', 'repeat3'):
        phase = f'{config_id}/{repeat}/P0'
        entry, records = closed_repeat(root, plan, phase, ids, labels, original_root, bind)
        if entry is None:
            missing.append({'pass': repeat, 'condition': 'P0', 'status': 'open_or_not_started'})
            previous_open = True
        else:
            if previous_open:
                raise ValueError('Later completed phase follows an open predecessor')
            data[repeat]['P0'] = entry
            indexed[repeat] = records
    complete = [name for name in PASSES if 'P0' in data[name]]
    scores = [data[name]['P0']['score'] for name in complete]
    summary = {'P0': {'allFour': stats([score['allFour'] for score in scores]),
                      'fields': {field: stats([score['fields'][field] for score in scores])
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
    return {'schema': 'laya-native-repeat-findings-v1', 'configuration': config_id,
            'displayName': DISPLAY[config_id], 'model': config_id,
            'provider': 'Local native CPU', 'method': 'native-output-stability',
            'conditionOrder': ['P0'], 'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items()))
                                     for field in FIELDS},
            'denominator': 60, 'completedConditions': len(complete), 'plannedConditions': 3,
            'missingPasses': missing, 'partialPasses': [], 'passes': data,
            'threePassSummary': summary, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': [],
            'sourceBindings': list(context[-1]),
            'declaredExternalSourceHashes': external_sources,
            'checkpointAssetHashes': plan['configurations'][config_id]['assets_sha256'],
            'hardware': plan['runtime']['hardware'],
            'interpretation': [
                'This native P0 procedure scores fixed answer options. P1 and P2 chat prompts are not equivalent operations for this configuration.',
                'Valid means all four categorical answers were returned in the expected format. Agreement requires those answers to match the provisional references.',
                'Unchanged answers can still disagree with the rubric. Compare the all-four and individual-field scores alongside the number of changed reviews.',
                'Durations include client and runtime overhead on this Mac. Pure inference time and local hardware/electricity cost were not measured.'
            ],
            'limitations': ['Only native P0 output stability is measured; generative P1/P2 prompts do not apply.',
                            'The same 60 fictional development records are repeated, not new independent cases.',
                            'Reference labels are provisional and were not used in inference.',
                            'Open or in-flight phases are omitted before reading any partial records.',
                            'Local checkpoint bytes and Laya source outside this repository are declared by the frozen admission plan; this public report does not rehash private workstation assets.',
                            'Per-record elapsed time and model load are client observations, not controlled model-only inference time. OS cache, CPU contention and effective seed are not fully observed.',
                            'Local hardware and electricity cost were not measured; actual cost is unknown, not zero.']}


def build(root=ROOT, configs=CONFIGS):
    root = Path(root)
    series = [build_one(root, config, source_context(root)) for config in configs]
    return {'schema': 'laya-native-repeat-report-v1', 'series': series,
            'availableConfigurations': [item['configuration'] for item in series]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale Laya native report: {args.output}')
    else:
        args.output.write_text(content)
    print('Laya native repeat report checked')


if __name__ == '__main__':
    main()
