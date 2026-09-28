#!/usr/bin/env python3
"""Build an offline, source-bound OpenJev native fresh-three P0 report."""
import argparse
import base64
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import digest, valid
from jev_benchmark import parse_response

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/openjev-native-fresh-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = 'ebbc3ba4caceda68478eaa2e101be9a039e9eb441201d50c7610a8719fe585c7'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = shared.PINNED_SHA[str(LABELS)]
MODES = ('fixed', 'adaptive', 'thinking')
PASSES = ('fresh1', 'fresh2', 'fresh3')
FIELDS = shared.FIELDS
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]


def path(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    target.relative_to(root)
    return target


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
            raise ValueError(f'Source hash differs: {relative}')
        binding = {'path': str(relative), 'sha256': actual}
        if binding not in bindings:
            bindings.append(binding)
        return binding
    return bind, bindings


def source_context(root):
    bind, bindings = binder(root)
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(path(root, MANIFEST).read_text())
    if (plan.get('schema') != 'openjev-native-fresh-p0-v1'
            or plan.get('status') != 'offline_frozen_no_inference'
            or plan.get('reference_labels_used_for_requests') is not False
            or plan.get('historical_predictions_used_for_requests') is not False
            or plan.get('disposition') != 'fresh_matched_three_historical_observational'
            or plan.get('schedule') != [f'openjev-{mode}/{repeat}/P0'
                                            for mode in MODES for repeat in PASSES]
            or plan.get('stage_inputs') != {'smoke_ids': IDS[:3], 'development_count': 60}
            or plan.get('runtime', {}).get('backend') != 'mlx'
            or plan['runtime'].get('server_policy') != 'fresh server per stage, warmup on; smoke and development each restart'):
        raise ValueError('Frozen OpenJev native plan controls differ')
    native_source = next((Path(name) for name in plan['source_sha256']
                          if Path(name).name == 'openjev_native_repeat_admission.py'), None)
    if native_source is None or native_source.parent.name != 'scripts':
        raise ValueError('Frozen native source root missing')
    original_root = native_source.parent.parent
    external = {}
    for absolute, expected in plan['source_sha256'].items():
        try:
            relative = Path(absolute).relative_to(original_root)
        except ValueError:
            external[absolute] = expected
        else:
            bind(relative, expected)
    required = {'scripts/openjev_native_repeat_admission.py', 'scripts/jev_benchmark.py',
                'scripts/development_benchmark.py', 'docs/LABELING_GUIDE.md',
                'data/pilot/inputs.jsonl', 'results/openjev/setup-audit.json'}
    if not required <= {str(Path(p).relative_to(original_root)) for p in plan['source_sha256']
                        if Path(p).is_relative_to(original_root)}:
        raise ValueError('Frozen OpenJev local source bindings incomplete')
    bind(LABELS, LABELS_SHA)
    inputs = rows(root, 'data/pilot/inputs.jsonl')
    references = rows(root, LABELS)
    if ([r.get('id') for r in inputs] != IDS or [r.get('id') for r in references] != IDS
            or any(set(r) != {'id', 'feedback'} for r in inputs)
            or any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels'))
                   for r in references)):
        raise ValueError('OpenJev inputs or provisional reference membership differs')
    policy = path(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != plan['policy_prefix_sha256']:
        raise ValueError('OpenJev policy prefix differs')
    for mode in MODES:
        requests = plan['requests'][mode]
        if ([r.get('id') for r in requests] != IDS
                or any(r['input_sha256'] != digest(source['feedback'])
                       or r['request_sha256'] != digest(json.dumps(r['payload'], sort_keys=True))
                       or r['payload'].get('model') != 'openjev-0.1'
                       for r, source in zip(requests, inputs))):
            raise ValueError('Frozen OpenJev native requests differ')
    labels = {r['id']: r['proposed_labels'] for r in references}
    return plan, labels, external, bind, bindings


def controller_sha(plan):
    matches = [expected for name, expected in plan['source_sha256'].items()
               if Path(name).name == 'openjev_native_repeat_admission.py'
               and Path(name).parent.name == 'scripts']
    if len(matches) != 1:
        raise ValueError('Frozen OpenJev native controller binding is ambiguous')
    return matches[0]


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


def timing(raw):
    elapsed = [r.get('elapsed_seconds') for r in raw]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in elapsed):
        raise ValueError('OpenJev client elapsed time invalid')
    usage = [r.get('usage') for r in raw]
    def total(key):
        values = [u.get(key) if isinstance(u, dict) else None for u in usage]
        return sum(values) if all(type(v) is int and v >= 0 for v in values) else None
    return {'requestCount': len(raw), 'clientRequestSeconds': elapsed,
            'clientRequestSecondsTotal': sum(elapsed),
            'timeBasis': 'client_observed_http_wall_clock',
            'modelLoadSeconds': None, 'inferenceSeconds': None,
            'tokenBasis': 'reported_response_usage_when_available',
            'tokens': {'input_tokens': total('input_tokens'),
                       'output_tokens': total('output_tokens'),
                       'cached_input_tokens': None, 'reasoning_output_tokens': None},
            'actualCostUsd': None,
            'costNote': 'Local hardware and electricity cost not measured; HTTP usage is not a bill.'}


def historical(root, plan, mode, labels, bind):
    spec = plan['historical'][mode]
    if spec.get('eligible_as_fresh_pass1') is not False:
        raise ValueError('Historical OpenJev observation was reclassified')
    folder = Path(spec['directory'])
    evidence = {name: bind(folder / name, expected)
                for name, expected in spec['files_sha256'].items()}
    chosen = 'development-reconciled.jsonl' if mode == 'fixed' else 'development.jsonl'
    records = rows(root, folder / chosen)
    if len(records) != 60 or [r.get('id') for r in records] != IDS:
        raise ValueError('Historical OpenJev membership differs')
    indexed = {}
    for record, request in zip(records, plan['requests'][mode]):
        if (record.get('status') != 'ok' or record.get('mode') != mode
                or record.get('surface') != 'openjev'
                or record.get('requested_model') != 'openjev-0.1'
                or record.get('question_version') != 'recruitment-four-choice-v2'
                or record.get('question_order') != list(FIELDS)
                or record.get('request_sha256') != request['request_sha256']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('local_extensions') != {k: request['payload'][k]
                     for k in ('steps', 'samples', 'think', 'sequential') if k in request['payload']}
                or record.get('prediction') != parse_response(record.get('raw_response'), 'openjev-0.1')):
            raise ValueError(f'Historical OpenJev raw projection differs: {record.get("id")}')
        indexed[record['id']] = record
    if mode == 'fixed':
        first = rows(root, folder / 'development.jsonl')
        continuation = rows(root, folder / 'development-continuation.jsonl')
        interruption = json.loads(path(root, folder / 'interruption.json').read_text())
        if (len(first) != 7 or len(continuation) != 53 or continuation[0]['id'] != 'DEV-008'
                or first + continuation != records
                or interruption.get('completed_ids') != IDS[:7]
                or interruption.get('next_record') != 'DEV-008'
                or interruption.get('next_request_started_or_completed') is not None
                or interruption.get('unrecorded_attempt_latency') is not None):
            raise ValueError('Historical fixed interruption lineage differs')
    else:
        interruption = None
    return {'status': 'historical_observation_excluded_from_fresh_triplet',
            'reason': spec['reason'], 'score': shared.score(indexed, labels, IDS),
            'predictedClassCounts': class_counts(indexed), 'confusionCounts': confusion(indexed, labels),
            'usage': timing(records), 'evidence': evidence,
            'interruption': ({'completedBeforeInterruption': 7,
                              'nextRecord': 'DEV-008',
                              'unrecordedAttemptPossible': True,
                              'unrecordedAttemptSeconds': None,
                              'knownClientSecondsExcludeUnrecordedAttempt': True}
                             if interruption is not None else None)}, indexed


def stage(root, plan, phase, name, bind):
    folder = BASE / phase
    names = {'review': f'{name}.root-review.json', 'claim': f'{name}.claim.json',
             'journal': f'{name}.journal.jsonl', 'raw': f'{name}.raw.jsonl',
             'records': f'{name}.records.jsonl', 'completion': f'{name}.completion.json'}
    evidence = {kind: bind(folder / filename) for kind, filename in names.items()}
    review = json.loads(path(root, folder / names['review']).read_text())
    claim = json.loads(path(root, folder / names['claim']).read_text())
    end = json.loads(path(root, folder / names['completion']).read_text())
    count = 3 if name == 'smoke' else 60
    if (review.get('kind') != 'root-reviewed-openjev-native-stage-v1'
            or review.get('approved') is not True or review.get('phase') != phase
            or review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA
            or review.get('controller_sha256') != controller_sha(plan)
            or review.get('reference_labels_read') is not False
            or review.get('source_commit') != plan['runtime']['source_commit']
            or review.get('artifact_manifest_sha256') != plan['artifact_manifest_sha256']
            or claim.get('phase') != phase or claim.get('stage') != name
            or claim.get('plan_sha256') != MANIFEST_SHA
            or claim.get('controller_sha256') != review['controller_sha256']
            or claim.get('receipt_sha256') != evidence['review']['sha256']
            or claim.get('reference_labels_read') is not False
            or end.get('phase') != phase or end.get('stage') != name
            or end.get('status') != 'completed' or end.get('reason') is not None
            or end.get('count') != count or end.get('attempted') != count
            or end.get('plan_sha256') != MANIFEST_SHA
            or end.get('receipt_sha256') != evidence['review']['sha256']
            or any(end.get(k + '_sha256') != evidence[k]['sha256']
                   for k in ('journal', 'raw', 'records'))):
        raise ValueError(f'Closed OpenJev stage admission or hashes differ: {phase}/{name}')
    raw = rows(root, folder / names['raw'])
    records = rows(root, folder / names['records'])
    journal = rows(root, folder / names['journal'])
    mode = phase.split('/')[0].removeprefix('openjev-')
    planned = plan['requests'][mode][:count]
    if len(raw) != count or len(records) != count or len(journal) != 2 * count:
        raise ValueError('Closed OpenJev stage membership differs')
    for i, request in enumerate(planned):
        capture, record = raw[i], records[i]
        started, finished = journal[2*i:2*i+2]
        rid = request['id']
        if (capture.get('id') != rid or record.get('id') != rid
                or not capture.get('attempt_id')
                or record.get('attempt_id') != capture['attempt_id']
                or started.get('event') != 'started' or started.get('id') != rid
                or started.get('attempt_id') != capture['attempt_id']
                or finished.get('event') != 'finished' or finished.get('id') != rid
                or finished.get('attempt_id') != capture['attempt_id']
                or any(row.get('request_sha256') != request['request_sha256']
                       for row in (capture, record, started))
                or record.get('reference_labels_read') is not False
                or capture.get('http_status') != 200 or capture.get('truncated') is not False
                or capture.get('incomplete') is not False):
            raise ValueError(f'OpenJev raw/record/journal identity differs: {phase}/{rid}')
        body = None
        try:
            body = json.loads(base64.b64decode(capture['body_base64'], validate=True))
            decision = {'status': 'ok', 'prediction': parse_response(body, 'openjev-0.1')}
        except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
            decision = {'status': 'invalid_output', 'reason': type(error).__name__}
        if record.get('decision') != decision or finished.get('status') != decision['status']:
            raise ValueError(f'OpenJev saved projection differs from raw: {phase}/{rid}')
        elapsed = capture.get('elapsed_seconds')
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('OpenJev client elapsed time invalid')
        capture['usage'] = body.get('usage') if isinstance(body, dict) else None
    if name == 'smoke' and any(r['decision']['status'] != 'ok' for r in records):
        raise ValueError('Closed OpenJev smoke contains invalid output')
    return {r['id']: {'id': r['id'], **r['decision']} for r in records}, raw, evidence


def closed_repeat(root, plan, mode, repeat, labels, bind):
    phase = f'openjev-{mode}/{repeat}/P0'
    folder = BASE / phase
    if not path(root, folder / 'development.completion.json').exists():
        return None, None
    smoke, _, smoke_evidence = stage(root, plan, phase, 'smoke', bind)
    inspection = bind(folder / 'smoke-inspection.json')
    inspected = json.loads(path(root, folder / 'smoke-inspection.json').read_text())
    development, raw, development_evidence = stage(root, plan, phase, 'development', bind)
    if (inspected.get('kind') != 'openjev-native-smoke-inspection-v1'
            or inspected.get('approved') is not True or inspected.get('phase') != phase
            or inspected.get('plan_sha256') != MANIFEST_SHA
            or inspected.get('raw_sha256') != smoke_evidence['raw']['sha256']
            or inspected.get('records_sha256') != smoke_evidence['records']['sha256']
            or inspected.get('reference_labels_read') is not False
            or json.loads(path(root, folder / 'development.root-review.json').read_text()).get('predecessor_sha256') != inspection['sha256']
            or json.loads(path(root, folder / 'smoke.root-review.json').read_text()).get('predecessor_sha256') is not None):
        raise ValueError('OpenJev smoke inspection or predecessor receipt differs')
    return {'completionStatus': 'complete', 'score': shared.score(development, labels, IDS),
            'predictedClassCounts': class_counts(development),
            'confusionCounts': confusion(development, labels),
            'usage': timing(raw),
            'evidence': {'smoke': smoke_evidence, 'smokeInspection': inspection,
                         'development': development_evidence}}, development


def stopped_stage(root, plan, phase, name, bind):
    folder = BASE / phase
    names = {'review': f'{name}.root-review.json', 'claim': f'{name}.claim.json',
             'journal': f'{name}.journal.jsonl', 'raw': f'{name}.raw.jsonl',
             'records': f'{name}.records.jsonl', 'completion': f'{name}.completion.json'}
    evidence = {kind: bind(folder / filename) for kind, filename in names.items()}
    review = json.loads(path(root, folder / names['review']).read_text())
    claim = json.loads(path(root, folder / names['claim']).read_text())
    end = json.loads(path(root, folder / names['completion']).read_text())
    journal = rows(root, folder / names['journal'])
    raw = rows(root, folder / names['raw'])
    records = rows(root, folder / names['records'])
    started = [r for r in journal if r.get('event') == 'started']
    finished = [r for r in journal if r.get('event') == 'finished']
    unknown = [r for r in journal if r.get('event') == 'stopped_unknown']
    expected = IDS[:3] if name == 'smoke' else IDS
    mode = phase.split('/')[0].removeprefix('openjev-')
    planned = {r['id']: r for r in plan['requests'][mode]}
    started_ids = [r.get('id') for r in started]
    raw_ids = [r.get('id') for r in raw]
    saved_ids = [r.get('id') for r in records]
    attempt_by_id = {r['id']: r.get('attempt_id') for r in started}
    if (review.get('kind') != 'root-reviewed-openjev-native-stage-v1'
            or review.get('approved') is not True or review.get('phase') != phase
            or review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA
            or review.get('controller_sha256') != controller_sha(plan)
            or review.get('reference_labels_read') is not False
            or review.get('source_commit') != plan['runtime']['source_commit']
            or review.get('artifact_manifest_sha256') != plan['artifact_manifest_sha256']
            or claim.get('phase') != phase or claim.get('stage') != name
            or claim.get('plan_sha256') != MANIFEST_SHA
            or claim.get('controller_sha256') != controller_sha(plan)
            or claim.get('receipt_sha256') != evidence['review']['sha256']
            or claim.get('reference_labels_read') is not False
            or end.get('phase') != phase or end.get('stage') != name
            or end.get('status') != 'stopped' or not isinstance(end.get('reason'), str)
            or not end['reason'] or end.get('plan_sha256') != MANIFEST_SHA
            or end.get('receipt_sha256') != evidence['review']['sha256']
            or end.get('attempted') != len(started) or end.get('count') != len(records)
            or any(end.get(key + '_sha256') != evidence[key]['sha256']
                   for key in ('journal', 'raw', 'records'))
            or started_ids != expected[:len(started)]
            or raw_ids != started_ids[:len(raw)]
            or saved_ids != raw_ids[:len(records)]
            or len(started) > len(expected) or len(raw) > len(started)
            or len(records) > len(raw) or len(finished) != len(records)
            or len(unknown) > 1 or len(journal) != len(started)+len(finished)+len(unknown)
            or any(not r.get('attempt_id') or r.get('request_sha256') != planned[r['id']]['request_sha256']
                   for r in started)
            or any(r.get('attempt_id') != attempt_by_id.get(r.get('id')) for r in raw+records+finished+unknown)
            or any(r.get('request_sha256') != planned[r['id']]['request_sha256'] for r in raw+records)
            or any(r.get('reference_labels_read') is not False for r in records)):
        raise ValueError(f'Stopped OpenJev stage evidence differs: {phase}/{name}')
    failed = list(dict.fromkeys(
        [r['id'] for r in records if r.get('decision', {}).get('status') != 'ok']
        + [r['id'] for r in unknown]))
    return {'pass': phase.split('/')[1], 'condition': 'P0', 'stage': name,
            'status': 'stopped', 'reason': end['reason'],
            'attempted': len(started), 'saved': len(records),
            'startedIds': started_ids, 'rawSavedIds': raw_ids, 'savedIds': saved_ids,
            'unknownStartedIds': [rid for rid in started_ids if rid not in saved_ids],
            'failedIds': failed, 'evidence': evidence}


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values)/len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build(root=ROOT):
    root = Path(root)
    plan, labels, external, bind, bindings = source_context(root)
    result = {'schema': 'openjev-native-fresh-three-report-v1',
              'referenceBasis': 'provisional assistant-reviewed v0.2 labels',
              'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field]
                    for rid in IDS).items())) for field in FIELDS},
              'manifestSha256': MANIFEST_SHA, 'configurations': {},
              'sourceBindings': bindings, 'externalSourceBindingsRecordedInManifest': external,
              'limitations': ['Historical observations are excluded from fresh triplets.',
                              'Client HTTP wall time is not model-only inference time.',
                              'Local attributable dollar cost and actual adaptive rereads are unavailable.']}
    global_open = False
    for mode in MODES:
        historical_entry, _ = historical(root, plan, mode, labels, bind)
        fresh = {}; indexed = {}; missing = []; open_before = False
        for repeat in PASSES:
            phase = f'openjev-{mode}/{repeat}/P0'
            folder = BASE / phase
            dev_terminal = folder / 'development.completion.json'
            smoke_terminal = folder / 'smoke.completion.json'
            end_path = dev_terminal if path(root, dev_terminal).exists() else smoke_terminal
            end = json.loads(path(root, end_path).read_text()) if path(root, end_path).exists() else None
            if end is not None and end.get('status') == 'stopped':
                missing.append(stopped_stage(root, plan, phase,
                                             'development' if end_path == dev_terminal else 'smoke', bind))
                open_before = True
                global_open = True
                continue
            entry, records = closed_repeat(root, plan, mode, repeat, labels, bind)
            if entry is None:
                claimed = any(path(root, folder / f'{name}.claim.json').exists()
                              for name in ('smoke', 'development'))
                missing.append({'pass': repeat, 'condition': 'P0',
                                'status': 'claimed_in_progress_or_interrupted' if claimed else 'not_started'})
                open_before = True
                global_open = True
            else:
                if open_before or global_open:
                    raise ValueError('Closed OpenJev phase follows an open predecessor')
                fresh[repeat] = entry; indexed[repeat] = records
        scores = [fresh[name]['score'] for name in PASSES if name in fresh]
        flips = [{'from': left, 'to': right, **shared.flip(indexed[left], indexed[right], IDS)}
                 for i, left in enumerate(PASSES) if left in indexed
                 for right in PASSES[i+1:] if right in indexed]
        across = None
        if len(indexed) == 3:
            eligible = [rid for rid in IDS if all(shared.outcome(indexed[name][rid]) == 'valid'
                                             for name in PASSES)]
            across = {'denominator': len(eligible), 'excludedIds': [rid for rid in IDS if rid not in eligible],
                      'fields': {field: [rid for rid in eligible if len({indexed[name][rid]['prediction'][field]
                                 for name in PASSES}) > 1] for field in FIELDS},
                      'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[name][rid]['prediction'][field]
                                 for field in FIELDS) for name in PASSES}) > 1]}
        result['configurations'][mode] = {'configuration': f'openjev-{mode}',
            'historicalObservation': historical_entry, 'freshPasses': fresh,
            'missingPasses': missing, 'pairwiseFlips': flips,
            'threePassSummary': {'P0': {'allFour': stats([s['allFour'] for s in scores]),
                                  'fields': {field: stats([s['fields'][field] for s in scores])
                                             for field in FIELDS}}},
            'changesAcrossThreePasses': across}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != result:
            raise ValueError('OpenJev native report differs from bound sources')
    elif args.output is None:
        print(result, end='')
    else:
        args.output.write_text(result)


if __name__ == '__main__':
    main()
