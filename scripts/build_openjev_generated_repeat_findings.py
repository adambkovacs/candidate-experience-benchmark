#!/usr/bin/env python3
"""Report only source-bound, terminal OpenJev generated fresh-three phases."""
import argparse
import base64
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import digest, valid
from openjev_prompt_execution import parse_native_response
from jev_benchmark import generated_variant_payload

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/openjev-generated-fresh-v2')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '1f0ac6d4ed4ccc31ed1b2fa4b9c570f716e202075512f78e5f212427efaa7216'
LABELS = Path('data/pilot/proposed_labels.jsonl')
MODES = ('generated-off', 'generated-on')
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
ROTATION = (('P0', 'P1', 'P2'), ('P1', 'P2', 'P0'), ('P2', 'P0', 'P1'))
SCHEDULE = [f'{mode}/{repeat}/{condition}' for mode in MODES
            for repeat, order in zip(PASSES, ROTATION) for condition in order]
FIELDS = shared.FIELDS
IDS = [f'DEV-{n:03d}' for n in range(1, 61)]


def path(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    result.relative_to(root)
    return result


def sha(filename):
    with Path(filename).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(root, relative):
    data = path(root, relative).read_bytes()
    if data and (not data.endswith(b'\n') or any(not line for line in data.splitlines())):
        raise ValueError(f'Incomplete JSONL: {relative}')
    return [json.loads(line) for line in data.splitlines()]


def binder(root):
    bindings = []
    def bind(relative, expected=None):
        relative = Path(relative)
        actual = sha(path(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Bound source differs: {relative}')
        item = {'path': str(relative), 'sha256': actual}
        if item not in bindings:
            bindings.append(item)
        return item
    return bind, bindings


def source_context(root):
    bind, bindings = binder(root)
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(path(root, MANIFEST).read_text())
    runtime = plan.get('runtime', {})
    if (plan.get('schema') != 'openjev-generated-fresh-three-v2'
            or plan.get('status') != 'offline_frozen_no_inference'
            or plan.get('disposition') != 'fresh_matched_three_historical_observational'
            or plan.get('schedule') != SCHEDULE
            or plan.get('stage_inputs') != {'smoke_ids': IDS[:3], 'development_count': 60}
            or plan.get('reference_labels_used_for_requests') is not False
            or plan.get('historical_predictions_used_for_requests') is not False
            or runtime.get('backend') != 'mlx'
            or runtime.get('configured_upstream_model_default') != 'dgemma'
            or runtime.get('logical_response_model') != 'diffusiongemma-26b'
            or runtime.get('rendered_token_hash_scope') is None
            or runtime.get('server_env_scope') is None):
        raise ValueError('Frozen generated protocol differs')
    controller = next((Path(name) for name in plan['source_sha256']
                       if Path(name).name == 'openjev_generated_repeat_admission_v2.py'), None)
    if controller is None or controller.parent.name != 'scripts':
        raise ValueError('Frozen controller source missing')
    original_root = controller.parent.parent
    for absolute, expected in plan['source_sha256'].items():
        relative = Path(absolute).relative_to(original_root)
        bind(relative, expected)
    local = {str(Path(name).relative_to(original_root)) for name in plan['source_sha256']}
    required = {'scripts/openjev_generated_repeat_admission_v2.py',
                'scripts/openjev_prompt_execution.py',
                'data/pilot/inputs.jsonl', 'docs/LABELING_GUIDE.md'}
    if not required <= local:
        raise ValueError('Generated plan omits necessary source binding')
    old = Path('results/prompt-comparison-v1-2026-09-24/openjev-generated-exact-v1')
    bind(old / 'execution-manifest.draft.json', plan['historical_manifest_sha256'])
    bind(old / 'preflight.json', plan['historical_preflight_sha256'])
    bind(LABELS, shared.PINNED_SHA[str(LABELS)])
    inputs = rows(root, 'data/pilot/inputs.jsonl')
    references = rows(root, LABELS)
    if ([r.get('id') for r in inputs] != IDS or [r.get('id') for r in references] != IDS
            or any(set(r) != {'id', 'feedback'} for r in inputs)
            or any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels'))
                   for r in references)):
        raise ValueError('Exact input and provisional reference membership differs')
    policy = path(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != plan['policy_prefix_sha256']:
        raise ValueError('Frozen policy prefix differs')
    for mode in MODES:
        for condition in CONDITIONS:
            requests = plan['requests'][mode][condition]
            if len(requests) != 60 or [r.get('id') for r in requests] != IDS:
                raise ValueError('Frozen generated requests membership differs')
            for item, source in zip(requests, inputs):
                rebuilt, audit = generated_variant_payload(source['feedback'], policy,
                    'diffusiongemma-26b', mode, condition, 'openjev-' + mode)
                if (item.get('input_sha256') != digest(source['feedback'])
                        or item.get('request_sha256') != digest(json.dumps(item['payload'], sort_keys=True))
                        or item.get('wire_body') != json.dumps(rebuilt)
                        or item.get('wire_body_sha256') != hashlib.sha256(item['wire_body'].encode()).hexdigest()
                        or item['payload'] != rebuilt or item['prompt_audit'] != audit
                        or item['payload'].get('model') != 'diffusiongemma-26b'
                        or item['prompt_audit'].get('reference_labels_read') is not False):
                    raise ValueError(f'Frozen generated request differs: {mode}/{condition}/{item.get("id")}')
    labels = {r['id']: r['proposed_labels'] for r in references}
    return plan, labels, bind, bindings


def controller_sha(plan):
    matches = [v for k, v in plan['source_sha256'].items()
               if Path(k).name == 'openjev_generated_repeat_admission_v2.py']
    if len(matches) != 1:
        raise ValueError('Ambiguous generated controller')
    return matches[0]


def stage(root, plan, phase, name, bind, expected_predecessor):
    folder = BASE / phase
    names = {'review': f'{name}.root-review.json', 'claim': f'{name}.claim.json',
             'attestation': f'{name}.server-attestation.json',
             'journal': f'{name}.journal.jsonl', 'raw': f'{name}.raw.jsonl',
             'records': f'{name}.records.jsonl', 'completion': f'{name}.completion.json'}
    evidence = {key: bind(folder / value) for key, value in names.items()}
    read = lambda key: json.loads(path(root, folder / names[key]).read_text())
    review, claim, att, end = (read(k) for k in ('review', 'claim', 'attestation', 'completion'))
    expected_count = 3 if name == 'smoke' else 60
    if (review.get('kind') != 'root-reviewed-openjev-generated-stage-v2'
            or review.get('approved') is not True or review.get('phase') != phase
            or review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA
            or review.get('controller_sha256') != controller_sha(plan)
            or review.get('predecessor_sha256') != expected_predecessor
            or review.get('reference_labels_read') is not False
            or review.get('source_commit') != plan['runtime']['source_commit']
            or review.get('artifact_manifest_sha256') != plan['artifact_manifest_sha256']
            or review.get('historical_preflight_sha256') != plan['historical_preflight_sha256']
            or review.get('server_policy') != plan['runtime']['cache_policy']
            or claim.get('phase') != phase or claim.get('stage') != name
            or claim.get('plan_sha256') != MANIFEST_SHA
            or claim.get('controller_sha256') != controller_sha(plan)
            or claim.get('receipt_sha256') != evidence['review']['sha256']
            or claim.get('reference_labels_read') is not False
            or att.get('kind') != 'openjev-generated-server-launch-observation-v2'
            or att.get('phase') != phase or att.get('stage') != name
            or att.get('source_commit') != plan['runtime']['source_commit']
            or att.get('artifact_manifest_sha256') != plan['artifact_manifest_sha256']
            or att.get('configured_server_env') != plan['runtime']['server_env']
            or att.get('configured_upstream_model_default') != 'dgemma'
            or att.get('logical_response_model') != 'diffusiongemma-26b'
            or att.get('cache_policy') != plan['runtime']['cache_policy']
            or att.get('health_observed') is not True
            or att.get('loaded_settings_measured') is not False
            or att.get('live_rendered_token_ids_measured') is not False
            or end.get('phase') != phase or end.get('stage') != name
            or end.get('plan_sha256') != MANIFEST_SHA
            or end.get('receipt_sha256') != evidence['review']['sha256']
            or end.get('server_attestation_sha256') != evidence['attestation']['sha256']
            or any(end.get(k + '_sha256') != evidence[k]['sha256']
                   for k in ('journal', 'raw', 'records'))):
        raise ValueError(f'Generated admission or hashes differ: {phase}/{name}')
    raw = rows(root, folder / names['raw'])
    records = rows(root, folder / names['records'])
    journal = rows(root, folder / names['journal'])
    planned = plan['requests'][phase.split('/')[0]][phase.split('/')[2]][:expected_count]
    stopped = end.get('status') == 'stopped'
    if (end.get('status') not in ('completed', 'stopped')
            or (not stopped and (end.get('reason') is not None or end.get('count') != expected_count
                                or end.get('attempted') != expected_count))
            or (stopped and (not isinstance(end.get('reason'), str) or not end['reason']))):
        raise ValueError('Generated stage terminal state differs')
    started = [r for r in journal if r.get('event') == 'started']
    finished = [r for r in journal if r.get('event') == 'finished']
    unknown = [r for r in journal if r.get('event') == 'stopped_unknown']
    if (end.get('attempted') != len(started) or end.get('count') != len(records)
            or len(started) > expected_count or len(raw) > len(started)
            or (not stopped and len(raw) != len(started))
            or len(raw) < len(records)
            or len(finished) != len(records) or len(unknown) != int(stopped)
            or len(journal) != len(started) + len(finished) + len(unknown)
            or [r.get('id') for r in started] != [p['id'] for p in planned[:len(started)]]
            or [r.get('id') for r in raw] != [r['id'] for r in started[:len(raw)]]
            or [r.get('id') for r in records] != [r['id'] for r in started[:len(records)]]) :
        raise ValueError('Generated stage membership differs')
    if stopped and (len(started) != len(records)+1 or unknown[0].get('id') != started[-1]['id']):
        raise ValueError('Generated unknown attempt lineage differs')
    projected = {}
    token_inputs = []
    token_outputs = []
    elapsed = []
    for i, start in enumerate(started):
        item = planned[i]
        capture = raw[i] if i < len(raw) else None
        rid, attempt = item['id'], start.get('attempt_id')
        if (not isinstance(attempt, str) or not attempt
                or start.get('request_sha256') != item['request_sha256']
                or start.get('wire_body_sha256') != item['wire_body_sha256']
                or (capture is not None and (capture.get('attempt_id') != attempt
                                             or capture.get('request_sha256') != item['request_sha256']))):
            raise ValueError(f'Generated attempt identity differs: {rid}')
        if capture is not None:
            seconds = capture.get('elapsed_seconds')
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError('Generated client elapsed time differs')
            elapsed.append(seconds)
        if i == len(records):
            if (not stopped or unknown[0].get('attempt_id') != attempt):
                raise ValueError('Generated unknown attempt not fenced')
            continue
        record, finish = records[i], finished[i]
        if (capture.get('wire_body_sha256') != item['wire_body_sha256']
                or capture.get('offline_rendered_token_ids_sha256') != item['offline_rendered_token_ids_sha256']
                or capture.get('input_tokens') != item['input_tokens']
                or capture.get('http_status') != 200 or capture.get('truncated') is not False
                or capture.get('incomplete') is not False
                or record.get('id') != rid or record.get('attempt_id') != attempt
                or record.get('request_sha256') != item['request_sha256']
                or record.get('reference_labels_read') is not False
                or finish.get('id') != rid or finish.get('attempt_id') != attempt):
            raise ValueError(f'Generated saved response identity differs: {rid}')
        response = json.loads(base64.b64decode(capture['body_base64'], validate=True))
        decision = parse_native_response(response, item['input_tokens'])
        if (decision['finish_reason'] not in ('stop', 'length')
                or (decision['finish_reason'] == 'length' and decision['status'] != 'invalid_output')
                or record.get('decision') != decision or finish.get('status') != decision['status']):
            raise ValueError(f'Generated raw projection differs: {rid}')
        projected[rid] = {'id': rid, **decision}
        token_inputs.append(decision['usage']['prompt_tokens'])
        token_outputs.append(decision['usage']['completion_tokens'])
    for j, start in enumerate(started):
        expected_finish = journal[2*j+1] if 2*j+1 < len(journal) else None
        if journal[2*j] != start or expected_finish is None or expected_finish.get('event') != ('stopped_unknown' if j == len(records) else 'finished'):
            raise ValueError('Generated journal ordering differs')
    return {'status': end['status'], 'reason': end['reason'], 'projected': projected,
            'startedIds': [r['id'] for r in started], 'rawSavedIds': [r['id'] for r in raw],
            'savedIds': [r['id'] for r in records],
            'unknownStartedIds': [r['id'] for r in started if r['id'] not in projected],
            'neverSentIds': [item['id'] for item in planned[len(started):]],
            'evidence': evidence,
            'usage': {'requestCount': len(started), 'rawCaptureCount': len(raw),
                      'rawResponseCount': sum('body_base64' in row for row in raw),
                      'clientRequestSecondsTotal': sum(elapsed) if len(elapsed) == len(started) else None,
                      'knownClientSecondsSubtotal': sum(elapsed),
                      'timeBasis': 'client_observed_http_wall_clock',
                      'modelLoadSeconds': None, 'inferenceSeconds': None,
                      'tokenBasis': 'returned_response_usage_when_available',
                      'tokens': {'input_tokens': sum(token_inputs) if not stopped else None,
                                 'output_tokens': sum(token_outputs) if not stopped else None,
                                 'knownSavedInputTokens': sum(token_inputs),
                                 'knownSavedOutputTokens': sum(token_outputs),
                                 'unknownAttemptTokens': None if stopped else 0},
                      'actualCostUsd': None}}


def inspection(root, plan, phase, smoke, bind):
    relative = BASE / phase / 'smoke-inspection.json'
    evidence = bind(relative)
    obj = json.loads(path(root, relative).read_text())
    records = obj.get('records')
    if (obj.get('kind') != 'openjev-generated-smoke-inspection-v1'
            or obj.get('approved') is not True or obj.get('phase') != phase
            or obj.get('plan_sha256') != MANIFEST_SHA
            or obj.get('raw_sha256') != smoke['evidence']['raw']['sha256']
            or obj.get('records_sha256') != smoke['evidence']['records']['sha256']
            or obj.get('reference_labels_read') is not False
            or not isinstance(records, list) or len(records) != 3):
        raise ValueError('Generated smoke inspection differs')
    for row, rid in zip(records, IDS[:3]):
        decision = smoke['projected'][rid]
        if (row.get('id') != rid or row.get('status') != decision['status']
                or row.get('prediction') != decision['prediction']
                or (decision['status'] == 'invalid_output' and not
                    (row.get('accepted_unchanged') is True and row.get('inspection_reason')))):
            raise ValueError('Generated smoke declaration differs')
    return evidence


def confusion(indexed, labels):
    return {field: {reference: dict(sorted(Counter(
                indexed[rid]['prediction'][field] if shared.outcome(indexed[rid]) == 'valid'
                else '__invalid_or_missing__' for rid in IDS
                if labels[rid][field] == reference).items()))
            for reference in sorted({labels[rid][field] for rid in IDS})}
            for field in FIELDS}


def class_counts(indexed):
    return {field: dict(sorted(Counter(indexed[rid]['prediction'][field]
             for rid in IDS if shared.outcome(indexed[rid]) == 'valid').items()))
            for field in FIELDS}


def historical(root, plan, mode, bind):
    spec = plan['historical'][mode]
    if spec.get('eligible_as_fresh_pass1') is not False:
        raise ValueError('Historical generated observation was reclassified')
    evidence = {}
    for condition in CONDITIONS:
        item = spec['conditions'][condition]
        evidence[condition] = bind(item['path'], item['sha256'])
        records = rows(root, item['path'])
        if (len(records) != 60 or [r.get('id') for r in records] != IDS
                or sum(r.get('status') == 'ok' for r in records) != item['valid']
                or sum(r.get('status') == 'invalid_output' for r in records) != item['invalid']
                or item['valid'] + item['invalid'] != 60):
            raise ValueError('Historical generated outcome membership differs')
    return {'status': 'historical_observation_excluded_from_fresh_triplet',
            'reason': spec['reason'], 'conditions': spec['conditions'], 'evidence': evidence}


def build(root=ROOT):
    root = Path(root)
    plan, labels, bind, bindings = source_context(root)
    result = {'schema': 'openjev-generated-fresh-three-report-v2',
              'manifestSha256': MANIFEST_SHA,
              'referenceBasis': 'provisional assistant-reviewed v0.2 labels',
              'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field]
                    for rid in IDS).items())) for field in FIELDS},
              'sourceBindings': bindings,
              'externalSourceBindingsRecordedInManifest': plan['external_source_sha256'],
              'assetHashesRecordedInManifest': plan['asset_sha256'],
              'provenance': {'configuredUpstreamModelDefault': 'dgemma',
                             'logicalResponseModel': 'diffusiongemma-26b',
                             'serverEnvScope': plan['runtime']['server_env_scope'],
                             'renderedTokenHashScope': plan['runtime']['rendered_token_hash_scope'],
                             'requestedOnEffectiveReasoning': plan['runtime']['requested_on_effective_reasoning']},
              'limitations': ['Historical generated observations do not count as fresh pass one.',
                              'Unexecuted v1 had a sorted-manifest payload wire-hash defect; v2 stores and sends the originally composed wire body. No v1 generated live stage exists.',
                              'Offline rendered token hashes and configured server settings are not loaded-runtime measurements.',
                              'Client HTTP wall time is not model-only inference time; local dollar cost is unmeasured.'],
              'configurations': {}}
    opened = False
    completed = {}
    for phase in SCHEDULE:
        mode, repeat, condition = phase.split('/')
        if mode not in result['configurations']:
            result['configurations'][mode] = {'historicalObservation': historical(root, plan, mode, bind),
                                               'freshPasses': {r: {} for r in PASSES},
                                               'missingPhases': [], 'pairwiseFlips': {},
                                               'withinPassPromptDifferences': {}}
        group = result['configurations'][mode]
        folder = BASE / phase
        smoke_end = folder / 'smoke.completion.json'
        dev_end = folder / 'development.completion.json'
        if path(root, dev_end).exists() or path(root, smoke_end).exists():
            smoke = stage(root, plan, phase, 'smoke', bind, None)
            if smoke['status'] != 'completed':
                group['missingPhases'].append({'pass': repeat, 'condition': condition,
                    'stage': 'smoke', 'status': 'stopped_unknown',
                    'startedIds': smoke['startedIds'], 'rawSavedIds': smoke['rawSavedIds'],
                    'savedIds': smoke['savedIds'],
                    'unknownStartedIds': smoke['unknownStartedIds'],
                    'neverSentIds': smoke['neverSentIds'], 'usage': smoke['usage'],
                    'evidence': smoke['evidence']})
                opened = True
                continue
            if path(root, dev_end).exists():
                inspected = inspection(root, plan, phase, smoke, bind)
                dev = stage(root, plan, phase, 'development', bind, inspected['sha256'])
                if dev['status'] == 'completed':
                    if opened:
                        raise ValueError('Closed generated phase follows open predecessor')
                    indexed = dev['projected']
                    group['freshPasses'][repeat][condition] = {
                        'completionStatus': 'complete', 'score': shared.score(indexed, labels, IDS),
                        'predictedClassCounts': class_counts(indexed),
                        'confusionCounts': confusion(indexed, labels), 'usage': dev['usage'],
                        'evidence': {'smoke': smoke['evidence'], 'smokeInspection': inspected,
                                     'development': dev['evidence']}}
                    completed[phase] = indexed
                    continue
                group['missingPhases'].append({'pass': repeat, 'condition': condition,
                    'stage': 'development', 'status': 'stopped_unknown',
                    'startedIds': dev['startedIds'], 'rawSavedIds': dev['rawSavedIds'],
                    'savedIds': dev['savedIds'],
                    'unknownStartedIds': dev['unknownStartedIds'],
                    'neverSentIds': dev['neverSentIds'], 'usage': dev['usage'],
                    'evidence': {'smoke': smoke['evidence'], 'smokeInspection': inspected,
                                 'development': dev['evidence']}})
            else:
                group['missingPhases'].append({'pass': repeat, 'condition': condition,
                    'status': 'smoke_complete_development_pending',
                    'evidence': {'smoke': smoke['evidence']}})
        else:
            # Live claims are not published evidence. Keep nonterminal phases
            # identical in the working tree and a clean public checkout.
            group['missingPhases'].append({'pass': repeat, 'condition': condition,
                'status': 'not_completed'})
        opened = True
    for mode, group in result['configurations'].items():
        for condition in CONDITIONS:
            indexed = {repeat: completed[f'{mode}/{repeat}/{condition}'] for repeat in PASSES
                       if f'{mode}/{repeat}/{condition}' in completed}
            group['pairwiseFlips'][condition] = [
                {'from': left, 'to': right, **shared.flip(indexed[left], indexed[right], IDS)}
                for i, left in enumerate(PASSES) if left in indexed
                for right in PASSES[i+1:] if right in indexed]
            if len(indexed) == 3:
                eligible = [rid for rid in IDS if all(shared.outcome(indexed[r][rid]) == 'valid' for r in PASSES)]
                group.setdefault('changesAcrossThreePasses', {})[condition] = {
                    'denominator': len(eligible), 'excludedIds': [rid for rid in IDS if rid not in eligible],
                    'fields': {field: [rid for rid in eligible if len({indexed[r][rid]['prediction'][field]
                                 for r in PASSES}) > 1] for field in FIELDS},
                    'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[r][rid]['prediction'][field]
                                 for field in FIELDS) for r in PASSES}) > 1]}
        for repeat in PASSES:
            same = group['freshPasses'][repeat]
            group['withinPassPromptDifferences'][repeat] = [
                {'from': 'P0', 'to': target,
                 'netScoreDelta': {
                     'allFour': same[target]['score']['allFour'] - same['P0']['score']['allFour'],
                     'fields': {field: same[target]['score']['fields'][field]
                                - same['P0']['score']['fields'][field] for field in FIELDS}},
                 **shared.flip(completed[f'{mode}/{repeat}/P0'],
                               completed[f'{mode}/{repeat}/{target}'], IDS)}
                for target in ('P1', 'P2') if 'P0' in same and target in same]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != rendered:
            raise ValueError('Generated report differs from bound sources')
    elif args.output is None:
        print(rendered, end='')
    else:
        args.output.write_text(rendered)


if __name__ == '__main__':
    main()
