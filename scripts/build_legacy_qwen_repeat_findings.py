#!/usr/bin/env python3
"""Build source-bound, offline findings for the legacy Qwen fresh-three plan."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/legacy-qwen-fresh3-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '7ef8c42a5fd66308e46c0dd885d92373bdbe3ba0e4aa7bdecf58298b82dd80c0'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
OUTPUT = Path('public-site/legacy-qwen-repeats.json')
TARGET = 'qwen3-0.6b-q4km-nonthinking'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
IDS = tuple(f'DEV-{i:03d}' for i in range(1, 61))
CONFIGS = (TARGET, 'qwen3-0.6b-sdk-thinking-on', 'qwen3-0.6b-sdk-thinking-off',
           'qwen3-1.7b-sdk-thinking-on', 'qwen3-1.7b-sdk-thinking-off',
           'qwen3.5-4b-sdk-thinking-on')
DISPLAY_NAMES = {
    TARGET: 'Qwen3 0.6B · HTTP · thinking off',
    'qwen3-0.6b-sdk-thinking-on': 'Qwen3 0.6B · SDK · thinking on',
    'qwen3-0.6b-sdk-thinking-off': 'Qwen3 0.6B · SDK · thinking off',
    'qwen3-1.7b-sdk-thinking-on': 'Qwen3 1.7B · SDK · thinking on',
    'qwen3-1.7b-sdk-thinking-off': 'Qwen3 1.7B · SDK · thinking off',
    'qwen3.5-4b-sdk-thinking-on': 'Qwen3.5 4B · SDK · thinking on',
}
FIELDS = shared.FIELDS


def file_at(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(root, relative):
    payload = file_at(root, relative).read_bytes()
    if not payload.endswith(b'\n') or any(not line.strip() for line in payload.splitlines()):
        raise ValueError(f'Incomplete JSONL source: {relative}')
    return [json.loads(line) for line in payload.splitlines()]


def binder(root):
    bindings = {}

    def bind(relative, expected=None):
        name = str(relative)
        actual = sha(file_at(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Source hash differs: {name}')
        bindings[name] = actual
        return actual

    return bind, bindings


def load_context(root):
    bind, bindings = binder(root)
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(file_at(root, MANIFEST).read_text())
    if (plan.get('schema') != 'legacy-qwen-fresh3-admission-v1' or
            plan.get('status') != 'offline_prepared_unapproved' or
            set(plan.get('configurations', {})) != set(CONFIGS) or
            plan.get('reference_labels_used_for_requests') is not False or
            plan.get('historical_predictions_used_for_requests') is not False or
            plan.get('policy', {}).get('denominator') != 60 or
            plan['policy'].get('smoke_ids') != list(IDS[:3])):
        raise ValueError('Frozen legacy Qwen plan differs')
    bind('scripts/legacy_qwen_repeat_admission.cjs', plan['controller_sha256'])
    for name, expected in plan['source_sha256'].items():
        bind(name, expected)
    bind(LABELS, LABELS_SHA)
    label_rows = read_rows(root, LABELS)
    if ([row.get('id') for row in label_rows] != list(IDS) or
            any(row.get('review_version') != '0.2' or not valid(row.get('proposed_labels'))
                for row in label_rows)):
        raise ValueError('Frozen v0.2 reference membership differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    for name in CONFIGS:
        config = plan['configurations'][name]
        schedule = config.get('schedule', [])
        expected_order = ([['P0', 'P1', 'P2'], ['P1', 'P2', 'P0'], ['P2', 'P0', 'P1']]
                          if name == TARGET else
                          [['P0', 'P2', 'P1'], ['P2', 'P1', 'P0'], ['P1', 'P0', 'P2']])
        if ([item.get('name') for item in schedule] != list(PASSES) or
                [item.get('conditions') for item in schedule] != expected_order or
                set(config.get('conditions', {})) != set(CONDITIONS)):
            raise ValueError(f'Legacy Qwen schedule differs: {name}')
        historical = config['historical_manifest']
        bind(historical['file'], historical['sha256'])
        for condition in CONDITIONS:
            planned = config['conditions'][condition]['requests']
            if [row.get('id') for row in planned] != list(IDS):
                raise ValueError(f'Frozen request membership differs: {name}/{condition}')
    return plan, labels, bind, bindings


def classify_http(raw, config, request):
    response = raw.get('result')
    if not isinstance(response, dict) or response.get('httpStatus') != 200:
        return {'status': 'service_failure', 'reason': 'http_response'}
    body = response.get('body')
    if not isinstance(body, dict) or json.loads(response.get('rawBody', 'null')) != body:
        return {'status': 'service_failure', 'reason': 'malformed_http_result'}
    if body.get('model') != config['model_identifier']:
        return {'status': 'control_failure', 'reason': 'returned_model'}
    if body.get('usage', {}).get('prompt_tokens') != request['prompt_tokens']:
        return {'status': 'control_failure', 'reason': 'prompt_token_count'}
    choices = body.get('choices')
    if (not isinstance(choices, list) or len(choices) != 1 or
            not isinstance(choices[0].get('message'), dict) or
            not isinstance(choices[0]['message'].get('content'), str)):
        return {'status': 'service_failure', 'reason': 'malformed_http_result'}
    try:
        prediction = json.loads(choices[0]['message']['content'])
    except json.JSONDecodeError:
        return {'status': 'invalid_output', 'reason': 'non_json'}
    if not valid(prediction):
        return {'status': 'invalid_output', 'reason': 'schema'}
    if choices[0].get('finish_reason') != 'stop' or choices[0]['message'].get('refusal'):
        return {'status': 'invalid_output', 'reason': 'finish_or_refusal'}
    return {'status': 'ok', 'prediction': prediction}


def closed_stage(root, plan, config_id, repeat, condition, name, bind):
    phase = f'{config_id}/{repeat}/{condition}'
    folder = BASE / phase
    files = {key: folder / f'{name}.{suffix}' for key, suffix in
             (('review', 'root-review.json'), ('claim', 'claim.json'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('journal', 'journal.jsonl'), ('completion', 'completion.json'))}
    evidence = {key: {'path': str(path), 'sha256': bind(path)} for key, path in files.items()}
    review = json.loads(file_at(root, files['review']).read_text())
    claim = json.loads(file_at(root, files['claim']).read_text())
    completion = json.loads(file_at(root, files['completion']).read_text())
    route = review.get('route_catalog_file')
    evidence['routeAudit'] = {'path': route, 'sha256': bind(route, review.get('route_catalog_sha256'))}
    config = plan['configurations'][config_id]
    count = 3 if name == 'smoke' else 60
    if (review.get('kind') != 'root-reviewed-legacy-qwen-stage-v1' or
            review.get('approved') is not True or review.get('phase') != phase or
            review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA or
            review.get('controller_sha256') != plan['controller_sha256'] or
            review.get('model_identifier') != config['model_identifier'] or
            review.get('artifact_sha256') != config['artifact_sha256'] or
            review.get('reference_labels_read') is not False or
            claim.get('phase') != phase or claim.get('stage') != name or
            claim.get('plan_sha256') != MANIFEST_SHA or
            claim.get('controller_sha256') != plan['controller_sha256'] or
            claim.get('receipt_sha256') != evidence['review']['sha256'] or
            claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256'] or
            claim['runtime_attestation'].get('load_evidence', {}).get('cache') != plan['policy']['cache_policy'] or
            completion.get('phase') != phase or completion.get('stage') != name or
            completion.get('status') != 'completed' or completion.get('reason') is not None or
            completion.get('attempted') != count or completion.get('saved') != count or
            completion.get('raw_sha256') != evidence['raw']['sha256'] or
            completion.get('records_sha256') != evidence['records']['sha256'] or
            completion.get('journal_sha256') != evidence['journal']['sha256']):
        raise ValueError(f'Closed stage evidence differs: {phase}/{name}')
    raw = read_rows(root, files['raw'])
    records = read_rows(root, files['records'])
    journal = read_rows(root, files['journal'])
    if len(raw) != count or len(records) != count or len(journal) != 2 * count:
        raise ValueError(f'Closed stage membership differs: {phase}/{name}')
    planned = config['conditions'][condition]['requests']
    ids = IDS[:3] if name == 'smoke' else IDS
    invalid = 0
    for index, rid in enumerate(ids):
        wire, saved = raw[index], records[index]
        started, finished = journal[2 * index:2 * index + 2]
        request = planned[index]
        elapsed = wire.get('elapsed_seconds')
        if (wire.get('id') != rid or saved.get('id') != rid or
                not isinstance(wire.get('attempt_id'), str) or not wire['attempt_id'] or
                saved.get('attempt_id') != wire['attempt_id'] or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                started.get('id') != rid or finished.get('id') != rid or
                started.get('attempt_id') != wire['attempt_id'] or
                finished.get('attempt_id') != wire['attempt_id'] or
                started.get('request_sha256') != request['sha256'] or
                saved.get('request_sha256') != request['sha256'] or
                saved.get('reference_labels_read') is not False or
                type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError(f'Raw/record/journal identity differs: {phase}/{rid}')
        decision = classify_http(wire, config, request)
        if saved.get('decision') != decision or finished.get('status') != decision['status']:
            raise ValueError(f'Parsed decision differs from raw: {phase}/{rid}')
        if decision['status'] == 'invalid_output':
            invalid += 1
        elif decision['status'] != 'ok':
            raise ValueError(f'Closed stage has service or control failure: {phase}/{rid}')
    if completion.get('invalid') != invalid or (name == 'smoke' and invalid):
        raise ValueError(f'Invalid count differs: {phase}/{name}')
    return records, raw, evidence


def usage(raw):
    elapsed = [row['elapsed_seconds'] for row in raw]
    bodies = [row['result']['body'] for row in raw]
    def total(*keys):
        values = []
        for body in bodies:
            value = body['usage']
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            if type(value) is not int or value < 0:
                return None
            values.append(value)
        return sum(values)
    return {'requestCount': len(raw), 'clientRequestSecondsTotal': sum(elapsed),
            'timeBasis': 'client_observed_wall_clock', 'inferenceSeconds': None,
            'modelLoadSeconds': None, 'actualCostUsd': None,
            'tokens': {'input_tokens': total('prompt_tokens'),
                       'output_tokens': total('completion_tokens'),
                       'total_tokens': total('total_tokens'),
                       'reasoning_output_tokens': total('completion_tokens_details', 'reasoning_tokens')}}


def class_counts(predictions, labels):
    """Count valid predictions and their frozen-reference confusion by field."""
    eligible = [rid for rid in IDS if shared.outcome(predictions[rid]) == 'valid']
    predicted = {field: dict(sorted(Counter(
        predictions[rid]['prediction'][field] for rid in eligible).items()))
        for field in FIELDS}
    confusion = {field: {reference: dict(sorted(Counter(
        predictions[rid]['prediction'][field] for rid in eligible
        if labels[rid][field] == reference).items()))
        for reference in sorted({labels[rid][field] for rid in IDS})}
        for field in FIELDS}
    return predicted, confusion


def summary(passes, parsed):
    by_condition = {}
    flips = []
    across = {}
    for condition in CONDITIONS:
        complete = [repeat for repeat in PASSES if condition in passes[repeat]]
        scores = [passes[repeat][condition]['score'] for repeat in complete]
        def stats(values):
            return {'completedPasses': len(values), 'values': values,
                    'range': [min(values), max(values)] if len(values) == 3 else None}
        by_condition[condition] = {'allFour': stats([score['allFour'] for score in scores]),
                                   'fields': {field: stats([score['fields'][field] for score in scores])
                                              for field in FIELDS}}
        for i, left in enumerate(complete):
            for right in complete[i + 1:]:
                flips.append({'condition': condition, 'from': left, 'to': right,
                              **shared.flip(parsed[left, condition], parsed[right, condition], IDS)})
        if len(complete) == 3:
            eligible = [rid for rid in IDS if all(shared.outcome(parsed[repeat, condition][rid]) == 'valid'
                                                  for repeat in PASSES)]
            across[condition] = {'denominator': len(eligible),
                                 'excludedIds': [rid for rid in IDS if rid not in eligible],
                                 'fields': {field: [rid for rid in eligible if len({
                                     parsed[repeat, condition][rid]['prediction'][field]
                                     for repeat in PASSES}) > 1] for field in FIELDS},
                                 'fourFieldVector': [rid for rid in eligible if len({tuple(
                                     parsed[repeat, condition][rid]['prediction'][field]
                                     for field in FIELDS) for repeat in PASSES}) > 1]}
    return by_condition, flips, across


def build(root=ROOT):
    root = Path(root)
    plan, labels, bind, bindings = load_context(root)
    context_bindings = dict(bindings)
    series = []
    for config_id in CONFIGS:
        config = plan['configurations'][config_id]
        passes = {repeat: {} for repeat in PASSES}
        parsed = {}
        missing = []
        for scheduled in config['schedule']:
            repeat = scheduled['name']
            for condition in scheduled['conditions']:
                folder = BASE / config_id / repeat / condition
                completion_file = folder / 'development.completion.json'
                if config_id != TARGET or not file_at(root, completion_file).exists():
                    missing.append({'pass': repeat, 'condition': condition,
                                    'status': 'not_in_closed_snapshot'})
                    continue
                completion = json.loads(file_at(root, completion_file).read_text())
                if completion.get('status') != 'completed':
                    missing.append({'pass': repeat, 'condition': condition,
                                    'status': 'not_in_closed_snapshot'})
                    continue
                smoke, _, smoke_evidence = closed_stage(root, plan, config_id, repeat,
                                                         condition, 'smoke', bind)
                development, raw, dev_evidence = closed_stage(root, plan, config_id, repeat,
                                                               condition, 'development', bind)
                inspection_file = folder / 'smoke-inspection.json'
                inspection = json.loads(file_at(root, inspection_file).read_text())
                inspection_sha = bind(inspection_file)
                review = json.loads(file_at(root, folder / 'development.root-review.json').read_text())
                if (inspection.get('kind') != 'legacy-qwen-three-record-smoke-inspection-v1' or
                        inspection.get('approved') is not True or
                        inspection.get('raw_sha256') != smoke_evidence['raw']['sha256'] or
                        inspection.get('records_sha256') != smoke_evidence['records']['sha256'] or
                        inspection.get('reference_labels_sent') is not False or
                        review.get('smoke_inspection_sha256') != inspection_sha or
                        any(row['decision']['status'] != 'ok' for row in smoke)):
                    raise ValueError(f'Development smoke admission differs: {config_id}/{repeat}/{condition}')
                predictions = {row['id']: {'status': row['decision']['status'],
                                           'prediction': row['decision'].get('prediction')}
                               for row in development}
                predicted_counts, confusion = class_counts(predictions, labels)
                entry = {'completionStatus': 'complete',
                         'score': shared.score(predictions, labels, IDS),
                         'predictedClassCounts': predicted_counts,
                         'classConfusion': confusion,
                         'usage': usage(raw),
                         'evidence': {'smoke': smoke_evidence,
                                      'smokeInspection': {'path': str(inspection_file), 'sha256': inspection_sha},
                                      'development': dev_evidence}}
                passes[repeat][condition] = entry
                parsed[repeat, condition] = predictions
        by_condition, flips, across = summary(passes, parsed)
        series.append({'schema': 'legacy-qwen-closed-phase-findings-v1',
                       'configuration': config_id, 'displayName': DISPLAY_NAMES[config_id],
                       'method': 'fresh-matched-local-output-stability',
                       'referenceVersion': '0.2', 'referenceStatus': 'provisional_human_checked',
                       'referenceClassCounts': {field: dict(sorted(Counter(
                           labels[rid][field] for rid in IDS).items())) for field in FIELDS},
                       'denominator': 60, 'plannedConditions': 9,
                       'completedConditions': sum(len(group) for group in passes.values()),
                       'missingPasses': missing, 'partialPasses': [], 'passes': passes,
                       'threePassSummary': by_condition, 'pairwiseFlips': flips,
                       'changesAcrossThreePasses': across,
                       'historicalStatus': 'observational_not_part_of_fresh_matched_three',
                       'sourceBindings': [{'path': name, 'sha256': digest}
                                          for name, digest in sorted((bindings if config_id == TARGET
                                                                      else context_bindings).items())],
                       'artifactSha256': config['artifact_sha256'],
                       'executionControls': {'surface': config['surface'],
                           'modelIdentifier': config['model_identifier'],
                           'context': config['context'], 'outputReserve': config['output_reserve'],
                           'timeoutMs': config['timeout_ms'], 'sampling': config['controls'].get('sampling'),
                           'seedPolicy': plan['policy']['seed_policy'],
                           'cachePolicy': plan['policy']['cache_policy']},
                       'limitations': ['The same 60 synthetic reviews are repeated, not new independent cases.',
                           'Reference v0.2 labels were applied offline after model requests.',
                           'Client request durations include runtime and transport overhead; pure inference time is unavailable.',
                           'Local hardware and electricity cost were not measured; unknown is not zero.']})
    return {'schema': 'legacy-qwen-closed-phase-report-v1', 'series': series}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    output = file_at(ROOT, args.output)
    if args.check:
        if not output.exists() or output.read_text() != content:
            raise ValueError(f'Stale legacy Qwen report: {output}')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    print(f'Legacy Qwen report: {output}')


if __name__ == '__main__':
    main()
