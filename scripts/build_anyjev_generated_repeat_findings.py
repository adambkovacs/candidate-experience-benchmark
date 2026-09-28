#!/usr/bin/env python3
"""Build an offline, source-bound report for the fresh AnyJev generated control."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from anyjev_generation_control import parse_generated
from anyjev_raw_repeat_admission import canonical
from development_benchmark import digest, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/anyjev-generated-p0p1p2-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '7f6a55b26129d8a742e03ecf7e1d2477bbd9b7b2bdde41d4f6a8fa96104f095b'
SCHEDULE = ('fresh1/P0', 'fresh1/P1', 'fresh1/P2', 'fresh2/P1', 'fresh2/P2', 'fresh2/P0', 'fresh3/P2', 'fresh3/P0', 'fresh3/P1')
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
HISTORICAL = {'P0': 0, 'P1': 0, 'P2': 30}


def location(root, relative):
    target = (Path(root) / relative).resolve()
    target.relative_to(Path(root).resolve())
    return target


def sha(filename):
    with Path(filename).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(root, relative):
    raw = location(root, relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


def binder(root):
    bindings = []
    def bind(relative, expected=None):
        relative = Path(relative)
        actual = sha(location(root, relative))
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
    plan = json.loads(location(root, MANIFEST).read_text())
    if (plan.get('schema') != 'anyjev-generated-fresh-three-p0p1p2-v1'
            or plan.get('status') != 'offline_frozen_no_inference'
            or plan.get('surface') != 'Matched HF generated JSON control; not AnyJev readout'
            or plan.get('reference_labels_used') is not False
            or plan.get('schedule') != list(SCHEDULE)
            or plan.get('stage_inputs') != {'smoke': {'limit': 3}, 'development': {'limit': 60}}
            or plan.get('model_id') != 'Qwen/Qwen3-0.6B'
            or plan.get('artifact_revision') != 'c1899de289a04d12100db370d81485cdf75e47ca'
            or plan.get('runtime', {}).get('device') != 'mps:0'
            or plan['runtime'].get('dtype') != 'torch.bfloat16'
            or plan['runtime'].get('do_sample') is not False
            or plan['runtime'].get('enable_thinking') is not False
            or plan['runtime'].get('max_input_tokens') != 4096
            or plan['runtime'].get('max_new_tokens') != 4096
            or plan['runtime'].get('context_tokens') != 40960
            or plan.get('historical', {}).get('first_pass_eligible') is not False):
        raise ValueError('Frozen generated plan shape or controls differ')
    required = {'scripts/anyjev_generated_repeat_admission.py', 'scripts/anyjev_generation_control.py',
                'scripts/anyjev_raw_repeat_admission.py', 'scripts/development_benchmark.py',
                'docs/LABELING_GUIDE.md', 'data/pilot/inputs.jsonl'}
    if not required <= set(plan.get('source_sha256', {})):
        raise ValueError('Frozen local source proof incomplete')
    for name, expected in plan['source_sha256'].items():
        bind(name, expected)
    bind('results/anyjev-generated-phase2-token-preflight-2026-09-23.json', plan['token_preflight_sha256'])
    bind('results/prompt-comparison-v1-2026-09-24/anyjev-generated-exact/execution-manifest.json', plan['exact_execution_manifest_sha256'])
    label_path = Path('data/pilot/proposed_labels.jsonl')
    bind(label_path, shared.PINNED_SHA[str(label_path)])
    inputs = rows(root, 'data/pilot/inputs.jsonl')
    references = rows(root, label_path)
    if ([x.get('id') for x in inputs] != IDS or [x.get('id') for x in references] != IDS
            or any(set(x) != {'id', 'feedback'} or not isinstance(x['feedback'], str) for x in inputs)
            or any(x.get('review_version') != '0.2' or not valid(x.get('proposed_labels')) for x in references)):
        raise ValueError('Frozen input or provisional reference membership differs')
    for condition in CONDITIONS:
        requests = plan.get('requests', {}).get(condition, [])
        if ([x.get('id') for x in requests] != IDS
                or any(request.get('input_sha256') != digest(row['feedback'])
                       or not isinstance(request.get('input_tokens'), int)
                       or not 0 < request['input_tokens'] <= 4096
                       or request['input_tokens'] + 4096 > 40960
                       or any(not isinstance(request.get(key), str) or len(request[key]) != 64
                              for key in ('messages_sha256', 'rendered_prompt_sha256', 'input_ids_sha256'))
                       for request, row in zip(requests, inputs))):
            raise ValueError(f'Frozen generated requests differ: {condition}')
    policy = location(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != plan['policy_prefix_sha256']:
        raise ValueError('Frozen generated policy differs')
    labels = {x['id']: x['proposed_labels'] for x in references}
    return plan, labels, bind, bindings


def class_counts(indexed):
    return {field: dict(sorted(Counter(indexed[rid]['prediction'][field] for rid in IDS
                if shared.outcome(indexed[rid]) == 'valid').items())) for field in FIELDS}


def confusion_counts(indexed, labels):
    return {field: {reference: dict(sorted(Counter(
        indexed[rid]['prediction'][field] if shared.outcome(indexed[rid]) == 'valid'
        else '__invalid_or_missing__' for rid in IDS if labels[rid][field] == reference).items()))
        for reference in sorted({labels[rid][field] for rid in IDS})} for field in FIELDS}


def timing(captures, historical=False):
    if historical:
        times = [x.get('elapsed_seconds') for x in captures]
        inputs = [x.get('input_tokens') for x in captures]
        outputs = [x.get('output_tokens') for x in captures]
    else:
        times = [x.get('client_generation_seconds') for x in captures]
        inputs = [x.get('input_tokens') for x in captures]
        outputs = [x.get('output_tokens') for x in captures]
    if any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in times):
        raise ValueError('Client duration differs')
    def total(values):
        return sum(values) if all(type(v) is int and v >= 0 for v in values) else None
    return {'requestCount': len(captures), 'requestSeconds': times, 'requestSecondsTotal': sum(times),
            'tokens': {'input_tokens': total(inputs), 'output_tokens': total(outputs),
                       'cached_input_tokens': None, 'cache_write_input_tokens': None,
                       'reasoning_output_tokens': None},
            'actualCostUsd': None, 'inferenceSeconds': None,
            'costNote': 'Local hardware and electricity cost not measured.'}


def historical_observation(root, plan, labels, bind):
    history = plan['historical']
    if history.get('historical_only') is not True or history.get('first_pass_eligible') is not False:
        raise ValueError('Historical eligibility differs')
    conditions = {}
    for condition in CONDITIONS:
        declared = history['conditions'][condition]
        evidence = bind(declared['file'], declared['sha256'])
        records = rows(root, declared['file'])
        requests = plan['requests'][condition]
        if (len(records) != 60 or [r.get('id') for r in records] != IDS
                or declared.get('saved') != 60 or declared.get('valid') != HISTORICAL[condition]
                or declared.get('intrinsic_invalid') != 60-HISTORICAL[condition]):
            raise ValueError('Historical generated membership differs')
        for record, request in zip(records, requests):
            prediction = parse_generated(record.get('raw_response'), record.get('finish_reason') == 'stop')
            if (record.get('status') != ('ok' if prediction else 'invalid_output')
                    or record.get('prediction') != prediction or record.get('attempts') != 1
                    or record.get('input_sha256') != request['input_sha256']
                    or record.get('request_sha256') != request['messages_sha256']
                    or record.get('input_tokens') != request['input_tokens']
                    or record.get('requested_model') != plan['model_id']
                    or record.get('artifact_revision') != plan['artifact_revision']
                    or record.get('device') != 'mps:0' or record.get('dtype') != 'torch.bfloat16'
                    or record.get('quantization') != 'none'
                    or record.get('do_sample') is not False or record.get('enable_thinking') is not False
                    or record.get('max_input_tokens') != 4096 or record.get('max_new_tokens') != 4096
                    or record.get('policy_sha256') != plan['policy_prefix_sha256']
                    or (condition != 'P0' and
                        (digest(json.dumps(record.get('messages'), sort_keys=True)) != request['messages_sha256']
                         or record.get('rendered_prompt_sha256') != request['rendered_prompt_sha256']))):
                raise ValueError(f'Historical generated row differs: {condition}/{request["id"]}')
        indexed = {x['id']: x for x in records}
        score = shared.score(indexed, labels, IDS)
        if score['valid'] != HISTORICAL[condition]:
            raise ValueError('Historical generated outcome count differs')
        conditions[condition] = {'score': score, 'predictedClassCounts': class_counts(indexed),
                                 'confusionCounts': confusion_counts(indexed, labels),
                                 'usage': timing(records, historical=True), 'evidence': {'records': evidence}}
    return {'eligibleAsFreshPass': False, 'reason': history['reason'], 'conditions': conditions}


def stage(root, plan, phase, stage_name, bind):
    folder = BASE / phase
    files = {key: folder / f'{stage_name}.{suffix}' for key, suffix in
             (('receipt', 'root-review.json'), ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'), ('completion', 'completion.json'))}
    evidence = {key: bind(name) for key, name in files.items()}
    receipt = json.loads(location(root, files['receipt']).read_text())
    claim = json.loads(location(root, files['claim']).read_text())
    completion = json.loads(location(root, files['completion']).read_text())
    if (receipt.get('kind') != 'root-reviewed-anyjev-generated-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage_name or receipt.get('plan_sha256') != MANIFEST_SHA
            or receipt.get('controller_sha256') != plan['source_sha256']['scripts/anyjev_generated_repeat_admission.py']
            or receipt.get('artifact_sha256') != plan['asset_sha256']['model.safetensors']
            or receipt.get('reference_labels_read') is not False
            or claim != {'phase': phase, 'stage': stage_name, 'plan_sha256': MANIFEST_SHA,
                         'receipt_sha256': evidence['receipt']['sha256'],
                         'policy': 'exclusive one attempt; uncertain started positions are not replayed'}
            or completion != {'phase': phase, 'stage': stage_name, 'plan_sha256': MANIFEST_SHA,
                              'count': plan['stage_inputs'][stage_name]['limit'],
                              'records_sha256': evidence['records']['sha256'],
                              'raw_sha256': evidence['raw']['sha256'],
                              'journal_sha256': evidence['journal']['sha256']}):
        raise ValueError('Generated stage admission or completion differs')
    captures = rows(root, files['raw'])
    records = rows(root, files['records'])
    journal = rows(root, files['journal'])
    count = plan['stage_inputs'][stage_name]['limit']
    if (len(captures) != count or len(records) != count
            or [x.get('event') for x in journal] !=
            ['phase_started'] + ['request_started', 'request_completed'] * count + ['phase_completed']
            or journal[0] != {'event': 'phase_started', 'phase': phase, 'stage': stage_name}
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('Generated terminal stage membership differs')
    requests = plan['requests'][phase.split('/')[1]]
    for i, (capture, record, request) in enumerate(zip(captures, records, requests)):
        started, completed = journal[2*i+1:2*i+3]
        ids = capture.get('generated_token_ids')
        eos = capture.get('eos_token_ids')
        if (not isinstance(ids, list) or any(type(x) is not int or x < 0 for x in ids)
                or not isinstance(eos, list) or any(type(x) is not int or x < 0 for x in eos)):
            raise ValueError('Generated raw token fields differ')
        ended = bool(ids and ids[-1] in eos)
        prediction = parse_generated(capture.get('raw_response'), ended)
        status = 'ok' if prediction else 'invalid_output'
        seconds = capture.get('client_generation_seconds')
        if (capture.get('id') != request['id'] or record.get('id') != request['id']
                or started.get('id') != request['id'] or completed.get('id') != request['id']
                or not isinstance(started.get('attempt_id'), str) or not started['attempt_id']
                or capture.get('attempt_id') != started['attempt_id']
                or record.get('attempt_id') != started['attempt_id']
                or completed.get('attempt_id') != started['attempt_id']
                or capture.get('messages_sha256') != request['messages_sha256']
                or digest(json.dumps(capture.get('messages'), sort_keys=True)) != request['messages_sha256']
                or started.get('messages_sha256') != request['messages_sha256']
                or capture.get('rendered_prompt_sha256') != request['rendered_prompt_sha256']
                or capture.get('input_ids_sha256') != request['input_ids_sha256']
                or capture.get('input_tokens') != request['input_tokens']
                or capture.get('output_tokens') != len(ids)
                or not isinstance(capture.get('raw_response'), str)
                or capture.get('finish_reason') != ('stop' if ended else 'length')
                or record.get('raw_sha256') != digest(canonical(capture))
                or record.get('input_sha256') != request['input_sha256']
                or record.get('messages_sha256') != request['messages_sha256']
                or record.get('status') != status or record.get('prediction') != prediction
                or record.get('phase') != phase or record.get('stage') != stage_name
                or record.get('reference_labels_read') is not False
                or record.get('model_id') != plan['model_id']
                or record.get('artifact_revision') != plan['artifact_revision']
                or record.get('device') != 'mps:0' or record.get('dtype') != 'torch.bfloat16'
                or record.get('do_sample') is not False or record.get('enable_thinking') is not False
                or record.get('client_generation_seconds') != seconds
                or completed.get('status') != status
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError(f'Generated output binding failed at {phase}/{request["id"]}')
    return {x['id']: x for x in records}, captures, records, evidence


def closed_phase(root, plan, phase, labels, bind):
    folder = BASE / phase
    if not location(root, folder / 'development.completion.json').exists():
        return None, None
    smoke_indexed, _, smoke_records, smoke_evidence = stage(root, plan, phase, 'smoke', bind)
    indexed, captures, _, development_evidence = stage(root, plan, phase, 'development', bind)
    inspection_path = folder / 'smoke-inspection.json'
    inspection_evidence = bind(inspection_path)
    inspection = json.loads(location(root, inspection_path).read_text())
    receipt = json.loads(location(root, folder / 'development.root-review.json').read_text())
    declarations = inspection.get('records')
    if (inspection.get('phase') != phase or inspection.get('plan_sha256') != MANIFEST_SHA
            or inspection.get('smoke_records_sha256') != smoke_evidence['records']['sha256']
            or inspection.get('approved') is not True
            or receipt.get('smoke_inspection_sha256') != inspection_evidence['sha256']
            or not isinstance(declarations, list) or len(declarations) != 3):
        raise ValueError('Generated smoke inspection differs')
    for observed, declared in zip(smoke_records, declarations):
        if (declared.get('id') != observed['id'] or declared.get('status') != observed['status']
                or declared.get('prediction') != observed['prediction']
                or declared.get('raw_sha256') != observed['raw_sha256']
                or (observed['status'] == 'invalid_output' and
                    (declared.get('accepted_unchanged') is not True
                     or declared.get('failure_class') != 'intrinsic_schema'
                     or not declared.get('inspection_reason')))):
            raise ValueError('Generated smoke inspection declaration differs')
    score = shared.score(indexed, labels, IDS)
    return {'completionStatus': 'complete', 'score': score,
            'predictedClassCounts': class_counts(indexed),
            'confusionCounts': confusion_counts(indexed, labels),
            'usage': timing(captures),
            'evidence': {'smoke': {**smoke_evidence, 'inspection': inspection_evidence},
                         'development': development_evidence}}, indexed


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values)/len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build(root=ROOT):
    root = Path(root)
    plan, labels, bind, bindings = source_context(root)
    historical = historical_observation(root, plan, labels, bind)
    data = {name: {} for name in PASSES}
    indexed = {}
    missing = []
    previous_open = False
    for phase in SCHEDULE:
        name, condition = phase.split('/')
        entry, records = closed_phase(root, plan, phase, labels, bind)
        if entry is None:
            folder = BASE / phase
            claimed = any(location(root, folder / f'{stage}.claim.json').exists()
                          for stage in ('smoke', 'development'))
            missing.append({'pass': name, 'condition': condition,
                            'status': 'claimed_in_progress_or_interrupted' if claimed else 'not_started'})
            previous_open = True
        else:
            if previous_open:
                raise ValueError('Later closed generated phase follows open predecessor')
            data[name][condition] = entry
            indexed[phase] = records
    summaries = {}
    across = {}
    flips = []
    for condition in CONDITIONS:
        complete = [name for name in PASSES if condition in data[name]]
        scores = [data[name][condition]['score'] for name in complete]
        summaries[condition] = {'allFour': stats([x['allFour'] for x in scores]),
                                'fields': {field: stats([x['fields'][field] for x in scores]) for field in FIELDS}}
        for i, left in enumerate(complete):
            for right in complete[i+1:]:
                flips.append({'condition': condition, 'from': left, 'to': right,
                              **shared.flip(indexed[f'{left}/{condition}'], indexed[f'{right}/{condition}'], IDS)})
        if len(complete) == 3:
            eligible = [rid for rid in IDS if all(shared.outcome(indexed[f'{name}/{condition}'][rid]) == 'valid'
                                                 for name in complete)]
            across[condition] = {'denominator': len(eligible),
                'excludedIds': [rid for rid in IDS if rid not in eligible],
                'fields': {field: [rid for rid in eligible if len({indexed[f'{name}/{condition}'][rid]['prediction'][field]
                          for name in complete}) > 1] for field in FIELDS},
                'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[f'{name}/{condition}'][rid]['prediction'][field]
                         for field in FIELDS) for name in complete}) > 1]}
    deltas = []
    prompt_flips = []
    for name in PASSES:
        for condition in ('P1', 'P2'):
            if 'P0' not in data[name] or condition not in data[name]:
                continue
            left = data[name]['P0']['score']; right = data[name][condition]['score']
            deltas.append({'pass': name, 'from': 'P0', 'to': condition,
                           'allFour': right['allFour']-left['allFour'],
                           'fields': {f: right['fields'][f]-left['fields'][f] for f in FIELDS}})
            prompt_flips.append({'pass': name, 'from': 'P0', 'to': condition,
                                 **shared.flip(indexed[f'{name}/P0'], indexed[f'{name}/{condition}'], IDS)})
    return {'schema': 'anyjev-generated-repeat-findings-v1',
            'configuration': 'anyjev-qwen06-generated-fresh-three',
            'displayName': 'Qwen3 0.6B · generated JSON control',
            'model': plan['model_id'], 'provider': 'Local native MPS',
            'method': 'generated-json-control', 'conditionOrder': list(CONDITIONS),
            'passOrder': list(PASSES), 'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'denominator': 60, 'plannedConditions': 9,
            'completedConditions': sum(len(x) for x in data.values()),
            'passes': data, 'missingPasses': missing, 'partialPasses': [],
            'historicalObservation': historical,
            'referenceClassCounts': {f: dict(sorted(Counter(labels[rid][f] for rid in IDS).items())) for f in FIELDS},
            'threePassSummary': summaries, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across,
            'withinPassPromptDeltas': deltas, 'withinPassPromptFlips': prompt_flips,
            'sourceBindings': bindings,
            'declaredModelAssetHashes': plan['asset_sha256'],
            'declaredModelArtifactManifestSha256': plan['artifact_manifest_sha256'],
            'limitations': [
                'The historical generated observations are ineligible as a fresh first pass because P0 prompt bytes were reconstructed, so they are reported separately.',
                'Only completed phases with verified smoke, inspection, admission, raw, projection, journal, and completion evidence are scored.',
                'Portable reporting checks saved token counts and finish status but does not decode generated token IDs with the private tokenizer.',
                'The frozen manifest declares model asset hashes; this portable report does not rehash private model files.',
                'Client generation time includes overhead and is not isolated inference time; local hardware and electricity cost are unknown.',
                'Provisional v0.2 references are not independent adjudication.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    report = build()
    value = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != value:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(value)
    print(f"{report['configuration']} {report['completedConditions']}/9")


if __name__ == '__main__':
    main()
