#!/usr/bin/env python3
"""Verify closed small-local repeat phases and score them offline."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/small-local-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '48ff89983f1acb5b8450c0ed8698cae127ec6d533f324be904a3f01a0bdd3619'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
FIELDS = shared.FIELDS
PASSES = ('fresh1', 'fresh2', 'fresh3')


def path(root, relative):
    target = (root / relative).resolve()
    target.relative_to(root.resolve())
    return target


def sha(filename):
    with Path(filename).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(root, relative):
    data = path(root, relative).read_bytes()
    if not data.endswith(b'\n') or any(not line.strip() for line in data.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {relative}')
    return [json.loads(line) for line in data.splitlines()]


def partial_rows(root, relative):
    data = path(root, relative).read_bytes()
    if not data:
        return []
    if not data.endswith(b'\n') or any(not line.strip() for line in data.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {relative}')
    return [json.loads(line) for line in data.splitlines()]


def bind_route(review, bind):
    source = review.get('route_catalog_file')
    expected = review.get('route_catalog_sha256')
    if not isinstance(source, str) or not isinstance(expected, str):
        raise ValueError('Stage review lacks route audit binding')
    return bind(source, expected)


def binder(root):
    bindings = []

    def bind(relative, expected=None):
        relative = Path(relative)
        actual = sha(path(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Source hash differs: {relative}')
        binding = {'path': str(relative), 'sha256': actual}
        if binding not in bindings:
            bindings.append(binding)
        return binding

    return bind, bindings


def context(root, configs):
    bind, bindings = binder(root)
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(path(root, MANIFEST).read_text())
    if (plan.get('schema') != 'small-local-repeat-admission-v1'
            or plan.get('status') != 'offline_prepared_unapproved'
            or plan.get('reference_labels_used_for_requests') is not False
            or plan.get('historical_predictions_used_for_requests') is not False
            or set(plan.get('configurations', {})) != {
                'gemma4-e2b-sdk-thinking-off', 'gemma4-e2b-sdk-thinking-on',
                'gemma4-e4b-sdk-thinking-off', 'gemma4-e4b-sdk-thinking-on',
                'qwen3.5-4b-sdk-thinking-off'}
            or plan.get('policy', {}).get('denominator') != 60
            or plan['policy'].get('smoke_ids') != ['DEV-001', 'DEV-002', 'DEV-003']):
        raise ValueError('Frozen small-local plan differs')
    bind('scripts/small_local_repeat_admission.cjs', plan['controller_sha256'])
    for name, expected in plan['source_sha256'].items():
        bind(name, expected)
    bind(LABELS, LABELS_SHA)
    ids = [f'DEV-{n:03d}' for n in range(1, 61)]
    label_rows = rows(root, LABELS)
    if ([r.get('id') for r in label_rows] != ids
            or any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels'))
                   for r in label_rows)):
        raise ValueError('Provisional reference v0.2 differs')
    labels = {r['id']: r['proposed_labels'] for r in label_rows}
    for config_id in configs:
        config = plan['configurations'][config_id]
        if ([s['name'] for s in config['schedule']] != list(PASSES)
                or any(set(s['conditions']) != {'P0', 'P1', 'P2'} for s in config['schedule'])
                or config['disposition'] != 'fresh_matched_three_historical_pass_observational'):
            raise ValueError('Fresh matched schedule differs')
        for name in ('historical_manifest', 'paired_report'):
            source = config[name]
            bind(source['file'], source['sha256'])
        for condition in ('P0', 'P1', 'P2'):
            source = config['conditions'][condition]['source']
            bind(source['file'], source['sha256'])
            planned = config['conditions'][condition]['requests']
            saved = rows(root, source['file'])
            if ([r['id'] for r in planned] != ids or [r['id'] for r in saved] != ids
                    or any(r.get('reference_labels_read') is not False for r in saved)
                    or any(hashlib.sha256(json.dumps(r['request'], separators=(',', ':'),
                                            ensure_ascii=False).encode()).hexdigest() != p['sha256']
                           for r, p in zip(saved, planned))):
                raise ValueError('Frozen request evidence differs')
    return plan, ids, labels, bind, bindings


def _normalized(config):
    return {field['key']: field['value'] for field in config['fields']}


def classify(raw, config, request):
    result = raw['result']
    info = result['modelInfo']
    stats = result['stats']
    if (info['identifier'] != config['model_identifier']
            or info['path'] != config['artifact_path']
            or info['sizeBytes'] != config['artifact_bytes']
            or info['contextLength'] != 8192
            or info['quantization']['name'] != 'Q4_K_M'
            or _normalized(result['loadConfig']) != _normalized(config['controls']['load_config'])
            or _normalized(result['predictionConfig']) != _normalized(config['controls']['prediction_config'])
            or stats['promptTokensCount'] != request['prompt_tokens']):
        raise ValueError('Raw model, controls or prompt count differ')
    if not isinstance(result.get('content'), str) or not isinstance(result.get('nonReasoningContent'), str):
        raise ValueError('Completed phase contains malformed SDK result')
    try:
        parsed = json.loads(result['nonReasoningContent'])
    except (TypeError, json.JSONDecodeError):
        return {'status': 'invalid_output', 'reason': 'non_json'}
    if not valid(parsed):
        return {'status': 'invalid_output', 'reason': 'schema'}
    if stats['stopReason'] not in ('eosFound', 'stopStringFound'):
        return {'status': 'invalid_output', 'reason': 'stop_reason'}
    return {'status': 'ok', 'prediction': parsed}


def stage(root, plan, config_id, phase, condition, name, bind):
    folder = BASE / phase
    files = {key: folder / f'{name}.{suffix}' for key, suffix in
             [('review', 'root-review.json'), ('claim', 'claim.json'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('journal', 'journal.jsonl'), ('completion', 'completion.json')]}
    evidence = {key: bind(filename) for key, filename in files.items()}
    review = json.loads(path(root, files['review']).read_text())
    evidence['routeAudit'] = bind_route(review, bind)
    claim = json.loads(path(root, files['claim']).read_text())
    terminal = json.loads(path(root, files['completion']).read_text())
    config = plan['configurations'][config_id]
    count = 3 if name == 'smoke' else 60
    if (review.get('kind') != 'root-reviewed-small-local-stage-v1'
            or review.get('approved') is not True or review.get('phase') != phase
            or review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA
            or review.get('controller_sha256') != plan['controller_sha256']
            or review.get('model_identifier') != config['model_identifier']
            or review.get('artifact_sha256') != config['artifact_sha256']
            or review.get('reference_labels_read') is not False
            or claim.get('phase') != phase or claim.get('stage') != name
            or claim.get('plan_sha256') != MANIFEST_SHA
            or claim.get('controller_sha256') != plan['controller_sha256']
            or claim.get('receipt_sha256') != evidence['review']['sha256']
            or claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256']
            or claim['runtime_attestation'].get('load_evidence', {}).get('cache') != {'enabled': True, 'size_limit_mib': 8192}
            or claim['runtime_attestation'].get('selected_backend_preference', {}).get('loaded_instance_version_verified') is not False
            or claim['runtime_attestation'].get('loaded_engine_version') is not None
            or claim['runtime_attestation'].get('loaded_engine_version_status') != 'unavailable_from_read_only_instance_surfaces'
            or terminal.get('phase') != phase or terminal.get('stage') != name
            or terminal.get('status') != 'completed' or terminal.get('reason') is not None
            or terminal.get('attempted') != count or terminal.get('saved') != count
            or terminal.get('raw_sha256') != evidence['raw']['sha256']
            or terminal.get('records_sha256') != evidence['records']['sha256']
            or terminal.get('journal_sha256') != evidence['journal']['sha256']):
        raise ValueError(f'Closed phase evidence differs: {phase}/{name}')
    raw = rows(root, files['raw'])
    records = rows(root, files['records'])
    journal = rows(root, files['journal'])
    ids = (plan['policy']['smoke_ids'] if name == 'smoke'
           else [f'DEV-{i:03d}' for i in range(1, 61)])
    if len(raw) != count or len(records) != count or len(journal) != 2 * count:
        raise ValueError('Closed phase has incomplete rows')
    planned = {r['id']: r for r in config['conditions'][condition]['requests']}
    invalid = 0
    for i, rid in enumerate(ids):
        r, saved, start, finish = raw[i], records[i], journal[2*i], journal[2*i+1]
        request = planned[rid]
        elapsed = r.get('elapsed_seconds')
        if (r.get('id') != rid or saved.get('id') != rid
                or start.get('event') != 'started' or finish.get('event') != 'finished'
                or start.get('id') != rid or finish.get('id') != rid
                or not r.get('attempt_id') or saved.get('attempt_id') != r['attempt_id']
                or start.get('attempt_id') != r['attempt_id']
                or finish.get('attempt_id') != r['attempt_id']
                or saved.get('request_sha256') != request['sha256']
                or start.get('request_sha256') != request['sha256']
                or saved.get('reference_labels_read') is not False
                or type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError(f'Raw/record/journal identity differs: {phase}/{rid}')
        decision = classify(r, config, request)
        if saved.get('decision') != decision or finish.get('status') != decision['status']:
            raise ValueError(f'Parsed decision differs from raw: {phase}/{rid}')
        if decision['status'] == 'invalid_output':
            invalid += 1
        elif decision['status'] != 'ok':
            raise ValueError('Completed phase has control or service failure')
    if terminal.get('invalid') != invalid or (name == 'smoke' and invalid):
        raise ValueError('Invalid-output count differs')
    return records, raw, evidence


def usage(raw):
    elapsed = [r['elapsed_seconds'] for r in raw]
    stats = [r['result']['stats'] for r in raw]
    def total(key):
        values = [s.get(key) for s in stats]
        return sum(values) if all(type(v) is int and v >= 0 for v in values) else None
    return {'requestCount': len(raw), 'clientRequestSeconds': elapsed,
            'clientRequestSecondsTotal': sum(elapsed), 'timeBasis': 'client_observed_wall_clock',
            'modelLoadSeconds': None, 'inferenceSeconds': None,
            'loadedEngineVersion': None,
            'loadedEngineVersionStatus': 'unavailable_from_read_only_instance_surfaces',
            'tokens': {'input_tokens': total('promptTokensCount'),
                       'output_tokens': total('predictedTokensCount'),
                       'total_tokens': total('totalTokensCount'),
                       'cached_input_tokens': None, 'cache_write_input_tokens': None,
                       'reasoning_output_tokens': None},
            'actualCostUsd': None}


def stopped_stage(root, plan, phase, name, bind):
    folder = BASE / phase
    files = {key: folder / f'{name}.{suffix}' for key, suffix in
             [('review', 'root-review.json'), ('claim', 'claim.json'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('journal', 'journal.jsonl'), ('completion', 'completion.json')]}
    evidence = {key: bind(filename) for key, filename in files.items()}
    review = json.loads(path(root, files['review']).read_text())
    evidence['routeAudit'] = bind_route(review, bind)
    claim = json.loads(path(root, files['claim']).read_text())
    terminal = json.loads(path(root, files['completion']).read_text())
    raw = partial_rows(root, files['raw'])
    records = partial_rows(root, files['records'])
    journal = partial_rows(root, files['journal'])
    started = [r for r in journal if r.get('event') == 'started']
    if (review.get('kind') != 'root-reviewed-small-local-stage-v1'
            or review.get('approved') is not True or review.get('phase') != phase
            or review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA
            or review.get('controller_sha256') != plan['controller_sha256']
            or review.get('reference_labels_read') is not False
            or claim.get('phase') != phase or claim.get('stage') != name
            or claim.get('plan_sha256') != MANIFEST_SHA
            or claim.get('controller_sha256') != plan['controller_sha256']
            or claim.get('receipt_sha256') != evidence['review']['sha256']
            or terminal.get('phase') != phase or terminal.get('stage') != name
            or terminal.get('status') != 'stopped'
            or not isinstance(terminal.get('reason'), str) or not terminal['reason']
            or terminal.get('raw_sha256') != evidence['raw']['sha256']
            or terminal.get('records_sha256') != evidence['records']['sha256']
            or terminal.get('journal_sha256') != evidence['journal']['sha256']
            or terminal.get('attempted') != len(started)
            or terminal.get('saved') != len(records)
            or not 0 <= len(records) <= len(raw) <= len(started)):
        raise ValueError(f'Stopped phase evidence differs: {phase}/{name}')
    started_ids = [r['id'] for r in started]
    raw_ids = [r['id'] for r in raw]
    saved_ids = [r['id'] for r in records]
    condition = phase.split('/')[-1]
    config_id = phase.split('/')[0]
    planned = {r['id']: r for r in plan['configurations'][config_id]['conditions'][condition]['requests']}
    expected_ids = (plan['policy']['smoke_ids'] if name == 'smoke'
                    else [f'DEV-{i:03d}' for i in range(1, 61)])
    failed_ids = list(dict.fromkeys(
        [r['id'] for r in records if r.get('decision', {}).get('status') != 'ok']
        + [r['id'] for r in journal if r.get('event') == 'stopped_unknown']))
    attempt_by_id = {r['id']: r.get('attempt_id') for r in started}
    if (started_ids != expected_ids[:len(started)]
            or raw_ids != started_ids[:len(raw)]
            or saved_ids != raw_ids[:len(records)]
            or any(not r.get('attempt_id') or r.get('request_sha256') != planned[r['id']]['sha256']
                   for r in started)
            or any(r.get('attempt_id') != attempt_by_id[r['id']] for r in raw + records)
            or any(r.get('request_sha256') != planned[r['id']]['sha256']
                   or r.get('reference_labels_read') is not False for r in records)
            or any(r.get('id') not in attempt_by_id
                   or r.get('attempt_id') != attempt_by_id.get(r.get('id'))
                   or r.get('event') not in ('started', 'finished', 'stopped_unknown')
                   for r in journal)
            or any(rid not in started_ids for rid in failed_ids)):
        raise ValueError('Stopped phase attempt IDs differ')
    return {'pass': phase.split('/')[-2], 'condition': phase.split('/')[-1],
            'stage': name, 'status': 'stopped', 'attempted': len(started),
            'saved': len(records), 'startedIds': started_ids,
            'rawSavedIds': raw_ids, 'savedIds': saved_ids,
            'unknownStartedIds': [rid for rid in started_ids if rid not in saved_ids],
            'failedIds': failed_ids, 'reason': terminal['reason'], 'evidence': evidence}


def _snapshot_bytes(root, relative):
    filename = path(root, relative)
    if not filename.exists():
        return None
    return filename.read_bytes()


def _mutable_group_snapshot(root, folder, name):
    paths = {key: folder / f'{name}.{key}.jsonl' for key in ('journal', 'raw', 'records')}
    first = {key: _snapshot_bytes(root, relative) for key, relative in paths.items()}
    second = {key: _snapshot_bytes(root, relative) for key, relative in paths.items()}
    if first != second:
        return None, [], False
    parsed = {}
    bindings = []
    for key, data in second.items():
        if data is None:
            parsed[key] = []
            continue
        if data and (not data.endswith(b'\n') or any(not line.strip() for line in data.splitlines())):
            return None, [], False
        try:
            parsed[key] = [json.loads(line) for line in data.splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, [], False
        bindings.append({'path': str(paths[key]), 'sha256': hashlib.sha256(data).hexdigest(),
                         'mutableSnapshot': True})
    return parsed, bindings, True


def claimed_stage(root, plan, config_id, phase, condition, name, bind):
    folder = BASE / phase
    review_file = folder / f'{name}.root-review.json'
    claim_file = folder / f'{name}.claim.json'
    review_binding = bind(review_file)
    claim_binding = bind(claim_file)
    review = json.loads(path(root, review_file).read_text())
    claim = json.loads(path(root, claim_file).read_text())
    config = plan['configurations'][config_id]
    route_binding = bind_route(review, bind)
    if (review.get('kind') != 'root-reviewed-small-local-stage-v1'
            or review.get('approved') is not True or review.get('phase') != phase
            or review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA
            or review.get('controller_sha256') != plan['controller_sha256']
            or review.get('model_identifier') != config['model_identifier']
            or review.get('artifact_sha256') != config['artifact_sha256']
            or review.get('reference_labels_read') is not False
            or claim.get('phase') != phase or claim.get('stage') != name
            or claim.get('plan_sha256') != MANIFEST_SHA
            or claim.get('controller_sha256') != plan['controller_sha256']
            or claim.get('receipt_sha256') != review_binding['sha256']
            or claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256']):
        raise ValueError('Claimed phase admission evidence differs')
    snapshots, bindings, stable = _mutable_group_snapshot(root, folder, name)
    result = {'pass': phase.split('/')[-2], 'condition': condition, 'stage': name,
              'status': 'claimed_in_progress_or_interrupted',
              'snapshotStatus': 'stable_unsealed' if stable else 'unstable_partial_bytes',
              'claim': claim_binding, 'review': review_binding, 'routeAudit': route_binding,
              'snapshotBindings': bindings if stable else []}
    if not stable:
        result.update({'startedIds': None, 'rawSavedIds': None, 'savedIds': None,
                       'unknownStartedIds': None, 'failedIds': None})
        return result
    journal = snapshots['journal']
    raw = snapshots['raw']
    records = snapshots['records']
    planned = {r['id']: r for r in config['conditions'][condition]['requests']}
    expected_ids = (plan['policy']['smoke_ids'] if name == 'smoke'
                    else [f'DEV-{i:03d}' for i in range(1, 61)])
    started = [r for r in journal if r.get('event') == 'started']
    started_ids = [r.get('id') for r in started]
    raw_ids = [r.get('id') for r in raw]
    saved_ids = [r.get('id') for r in records]
    if (started_ids != expected_ids[:len(started)]
            or raw_ids != started_ids[:len(raw)]
            or saved_ids != raw_ids[:len(records)]
            or len(journal) > 2 * len(started)):
        raise ValueError('Claimed phase snapshot membership differs')
    attempt_by_id = {r['id']: r.get('attempt_id') for r in started}
    for row in started:
        if (not row.get('attempt_id')
                or row.get('request_sha256') != planned[row['id']]['sha256']):
            raise ValueError('Claimed phase started intent differs')
    for row in raw + records:
        if row.get('attempt_id') != attempt_by_id[row['id']]:
            raise ValueError('Claimed phase raw/record attribution differs')
    for row in records:
        if (row.get('request_sha256') != planned[row['id']]['sha256']
                or row.get('reference_labels_read') is not False):
            raise ValueError('Claimed phase record source differs')
    for row in journal:
        if (row.get('id') not in attempt_by_id
                or row.get('attempt_id') != attempt_by_id[row['id']]
                or row.get('event') not in ('started', 'finished', 'stopped_unknown')):
            raise ValueError('Claimed phase journal attribution differs')
    failed_ids = list(dict.fromkeys(
        [r['id'] for r in records if r.get('decision', {}).get('status') != 'ok']
        + [r['id'] for r in journal if r.get('event') == 'stopped_unknown']))
    result.update({'startedIds': started_ids, 'rawSavedIds': raw_ids,
                   'savedIds': saved_ids,
                   'unknownStartedIds': [rid for rid in started_ids if rid not in saved_ids],
                   'failedIds': failed_ids})
    return result


def build_one(root, config_id, ctx):
    plan, ids, labels, bind, bindings = ctx
    config = plan['configurations'][config_id]
    passes = {name: {} for name in PASSES}
    indexed = {}
    missing = []
    partial = []
    for scheduled in config['schedule']:
        name = scheduled['name']
        for condition in scheduled['conditions']:
            phase = f'{config_id}/{name}/{condition}'
            folder = BASE / phase
            dev_terminal_path = folder / 'development.completion.json'
            smoke_terminal_path = folder / 'smoke.completion.json'
            if path(root, dev_terminal_path).exists():
                dev_status = json.loads(path(root, dev_terminal_path).read_text()).get('status')
                if dev_status == 'stopped':
                    partial.append(stopped_stage(root, plan, phase, 'development', bind))
                    continue
            elif path(root, smoke_terminal_path).exists():
                smoke_status = json.loads(path(root, smoke_terminal_path).read_text()).get('status')
                if smoke_status == 'stopped':
                    partial.append(stopped_stage(root, plan, phase, 'smoke', bind))
                    continue
            if not path(root, dev_terminal_path).exists():
                dev_claim = folder / 'development.claim.json'
                smoke_claim = folder / 'smoke.claim.json'
                if path(root, dev_claim).exists():
                    partial.append(claimed_stage(root, plan, config_id, phase,
                                                 condition, 'development', bind))
                elif path(root, smoke_claim).exists() and not path(root, smoke_terminal_path).exists():
                    partial.append(claimed_stage(root, plan, config_id, phase,
                                                 condition, 'smoke', bind))
                else:
                    stage_name = 'development' if path(root, smoke_terminal_path).exists() else 'smoke'
                    stages_to_check = (stage_name, 'development') if stage_name == 'smoke' else ('development',)
                    if any(path(root, folder / f'{candidate}.{kind}.jsonl').exists()
                           for candidate in stages_to_check
                           for kind in ('journal', 'raw', 'records')):
                        raise ValueError('Unclaimed stage has mutable evidence')
                    entry = {'pass': name, 'condition': condition, 'stage': stage_name,
                             'status': 'unclaimed_never_started'}
                    if stage_name == 'development':
                        _, _, smoke_evidence = stage(root, plan, config_id, phase,
                                                      condition, 'smoke', bind)
                        entry['smokeEvidence'] = smoke_evidence
                    missing.append(entry)
                continue
            smoke, _, smoke_evidence = stage(root, plan, config_id, phase, condition, 'smoke', bind)
            development, raw, dev_evidence = stage(root, plan, config_id, phase, condition,
                                                    'development', bind)
            inspection_file = folder / 'smoke-inspection.json'
            inspection = json.loads(path(root, inspection_file).read_text())
            inspection_binding = bind(inspection_file)
            review = json.loads(path(root, folder / 'development.root-review.json').read_text())
            if (inspection.get('kind') != 'small-local-three-record-smoke-inspection-v1'
                    or inspection.get('approved') is not True
                    or inspection.get('raw_sha256') != smoke_evidence['raw']['sha256']
                    or inspection.get('records_sha256') != smoke_evidence['records']['sha256']
                    or inspection.get('reference_labels_sent') is not False
                    or review.get('smoke_inspection_sha256') != inspection_binding['sha256']
                    or review.get('smoke_all_three_valid') is not True
                    or any(r['decision']['status'] != 'ok' for r in smoke)):
                raise ValueError('Development does not bind valid inspected smoke')
            parsed = {r['id']: {'status': r['decision']['status'],
                                'prediction': r['decision'].get('prediction')} for r in development}
            entry = {'completionStatus': 'complete', 'score': shared.score(parsed, labels, ids),
                     'predictedClassCounts': {field: dict(sorted(Counter(
                         parsed[rid]['prediction'][field] for rid in ids
                         if shared.outcome(parsed[rid]) == 'valid').items())) for field in FIELDS},
                     'usage': usage(raw),
                     'evidence': {'smoke': smoke_evidence, 'smokeInspection': inspection_binding,
                                  'development': dev_evidence}}
            passes[name][condition] = entry
            indexed[name, condition] = parsed
    summaries = {}
    flips = []
    across = {}
    for condition in ('P0', 'P1', 'P2'):
        complete = [name for name in PASSES if condition in passes[name]]
        scores = [passes[name][condition]['score'] for name in complete]
        def stats(values):
            return {'completedPasses': len(values), 'values': values,
                    'range': [min(values), max(values)] if len(values) == 3 else None}
        summaries[condition] = {'allFour': stats([s['allFour'] for s in scores]),
                                'fields': {field: stats([s['fields'][field] for s in scores])
                                           for field in FIELDS}}
        if len(complete) == 3:
            for i, left in enumerate(PASSES):
                for right in PASSES[i+1:]:
                    flips.append({'condition': condition, 'from': left, 'to': right,
                                  **shared.flip(indexed[left, condition], indexed[right, condition], ids)})
            eligible = [rid for rid in ids if all(shared.outcome(indexed[name, condition][rid]) == 'valid'
                                                   for name in PASSES)]
            across[condition] = {'denominator': len(eligible),
                                 'excludedIds': [rid for rid in ids if rid not in eligible],
                                 'fields': {field: [rid for rid in eligible if len({
                                     indexed[name, condition][rid]['prediction'][field]
                                     for name in PASSES}) > 1] for field in FIELDS},
                                 'fourFieldVector': [rid for rid in eligible if len({tuple(
                                     indexed[name, condition][rid]['prediction'][field]
                                     for field in FIELDS) for name in PASSES}) > 1]}
    return {'schema': 'small-local-closed-phase-findings-v1', 'configuration': config_id,
            'method': 'fresh-matched-local-output-stability', 'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'denominator': 60, 'plannedConditions': 9,
            'completedConditions': sum(len(x) for x in passes.values()),
            'missingPasses': missing, 'partialPasses': partial, 'passes': passes,
            'threePassSummary': summaries,
            'pairwiseFlips': flips, 'changesAcrossThreePasses': across,
            'historicalStatus': 'observational_not_part_of_fresh_matched_three',
            'sourceBindings': list(bindings), 'artifactSha256': config['artifact_sha256'],
            'limitations': ['Only terminal phases are scored; in-flight bytes are excluded.',
                            'The same 60 fictional reviews are repeated, not new cases.',
                            'Reference v0.2 labels are provisional and were read only offline.',
                            'Client request durations include runtime overhead; pure inference and model load times were not measured.',
                            'Loaded engine version is unverified; selected backend is only an observation.',
                            'Local hardware and electricity cost were not measured; unknown is not zero.']}


def build(root=ROOT, configs=None):
    root = Path(root)
    if configs is None:
        configs = tuple(json.loads(path(root, MANIFEST).read_text())['configurations'])
    return {'schema': 'small-local-closed-phase-report-v1',
            'series': [build_one(root, config, context(root, (config,))) for config in configs]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale small-local report: {args.output}')
    else:
        args.output.write_text(content)
    print('Small-local closed-phase report checked')


if __name__ == '__main__':
    main()
