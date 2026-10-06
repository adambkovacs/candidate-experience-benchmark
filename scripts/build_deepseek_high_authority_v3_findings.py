#!/usr/bin/env python3
"""Add independently closed DeepSeek high phases to the hosted repeat report."""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import build_qwen36_on_hosted_authority_v2_findings as existing
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-high-authority-v3')
FOLDER = BASE / 'fresh1/P0'
CONFIG = 'openrouter-paid-deepseek-v41-flash-high-authority-v3-current-price'
SERIES = CONFIG + '-fresh-matched3'
MODEL = 'deepseek/deepseek-v4.1-flash'
PROVIDER = 'open-inference/fp4'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
LABELS = Path('data/pilot/proposed_labels.jsonl')
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')


def later_stage(root, plan, repeat, condition, closure, bind, labels):
    """Verify a future stage using its own source-bound, immutable closure."""
    folder = BASE / repeat / condition
    required = {str(BASE / 'execution-manifest.json'),
                str(BASE / repeat / 'manifest.json'), str(BASE / 'public-route.json'),
                str(LABELS), 'scripts/deepseek_high_authority_v3.py',
                *(str(folder / name) for name in (
                    'development.claim.json', 'development.root-review.json',
                    'development.journal.jsonl', 'development.attempts.jsonl',
                    'development.responses.jsonl', 'smoke.attempts.jsonl',
                    'smoke.responses.jsonl', 'smoke.journal.jsonl',
                    'closure-ledger-snapshot.jsonl'))}
    if (closure.get('schema') != 'deepseek-high-authority-v3-stage-closure-root-review-v1' or
            closure.get('verdict') != 'APPROVE' or closure.get('independent_review') is not True or
            closure.get('configuration_id') != CONFIG or
            closure.get('stage') != f'{repeat}/{condition}/development' or
            closure.get('model') != MODEL or closure.get('provider') != PROVIDER or
            closure.get('frozen_continue_on_invalid_output') is not True or
            closure.get('record_count') != 60 or closure.get('unknown_cost_count') != 0 or
            not isinstance(closure.get('source_bindings'), dict) or
            not required <= closure['source_bindings'].keys() or
            str(BASE / 'budget-deepseek-high-authority-v3-fresh123.jsonl') in
            closure['source_bindings']):
        raise ValueError('DeepSeek high later-stage closure is not independently verified')
    for path, digest in closure['source_bindings'].items():
        bind(path, digest)
    snapshot = closure.get('child_ledger_at_review', {})
    snapshot_path = str(folder / 'closure-ledger-snapshot.jsonl')
    if (snapshot.get('snapshot_path') != snapshot_path or
            snapshot.get('sha256') != closure['source_bindings'][snapshot_path] or
            snapshot.get('pending_count') != 0):
        raise ValueError('DeepSeek high later-stage ledger snapshot differs')
    requests = plan['conditions'][condition]['development']
    attempts = existing.rows(root, folder / 'development.attempts.jsonl')
    responses = existing.rows(root, folder / 'development.responses.jsonl')
    journal = existing.rows(root, folder / 'development.journal.jsonl')
    smoke = existing.rows(root, folder / 'smoke.attempts.jsonl')
    ledger = existing.rows(root, snapshot_path)
    if ([x.get('record_id') for x in requests] != IDS or
            [x.get('id') for x in attempts] != IDS or
            [x.get('id') for x in responses] != IDS or
            len({x.get('attempt_id') for x in attempts}) != 60 or
            len(smoke) != 3 or len(journal) != 182 or
            any(journal[0].get(k) != v for k, v in
                (('event', 'phase_started'), ('configuration_id', CONFIG),
                 ('fresh_pass', repeat), ('condition', condition),
                 ('phase', 'development'))) or
            journal[-1].get('event') != 'phase_completed' or
            any(journal[-1].get(k) != v for k, v in
                (('configuration_id', CONFIG), ('fresh_pass', repeat),
                 ('condition', condition), ('phase', 'development'))) or
            journal[-1].get('request_count') != 60 or
            journal[-1].get('attempt_ids') != [x['attempt_id'] for x in attempts]):
        raise ValueError('DeepSeek high later-stage membership or lifecycle differs')
    events = {}
    if ledger[0] != {'event': 'budget', 'cap_usd': '0.90'}:
        raise ValueError('DeepSeek high later-stage child budget differs')
    for row in ledger[1:]:
        attempt_id = row.get('attempt_id')
        if row.get('event') not in ('reserve', 'settle') or not attempt_id:
            raise ValueError('DeepSeek high later-stage ledger event differs')
        events.setdefault(attempt_id, []).append(row)
    if (len(events) != snapshot.get('settled_attempt_count') or
            any(len(rows) != 2 or rows[0].get('event') != 'reserve' or
                rows[1].get('event') != 'settle' for rows in events.values())):
        raise ValueError('DeepSeek high later-stage ledger has unresolved attempts')
    route = json.loads(existing.file(root, BASE / 'public-route.json').read_text())
    saved_endpoint = route['selected_endpoint']
    endpoint_keys = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                     'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                     'supported_parameters')
    known = Decimal(0)
    status_counts = {}
    invalid_ids = []
    for n, (request, attempt, captured) in enumerate(zip(requests, attempts, responses)):
        rid = IDS[n]
        if (attempt.get('configuration_id') != CONFIG or
                attempt.get('fresh_pass') != repeat or attempt.get('condition') != condition or
                attempt.get('phase') != 'development' or
                attempt.get('requested_model') != MODEL or
                attempt.get('reasoning_effort') != 'high' or
                attempt.get('provider_endpoint', {}).get('tag') != PROVIDER or
                any(attempt['provider_endpoint'].get(k) != saved_endpoint.get(k)
                    for k in endpoint_keys) or
                set(attempt['provider_endpoint']['pricing']) != set(saved_endpoint['pricing']) or
                any(Decimal(str(attempt['provider_endpoint']['pricing'][k])) !=
                    Decimal(str(saved_endpoint['pricing'][k]))
                    for k in saved_endpoint['pricing'] if k not in ('prompt', 'completion')) or
                any(not Decimal(0) <= Decimal(str(attempt['provider_endpoint']['pricing'][k])) <=
                    Decimal(str(saved_endpoint['pricing'][k]))
                    for k in ('prompt', 'completion')) or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('request') != request['payload'] or
                attempt.get('input_sha256') != request['input_sha256'] or
                attempt.get('instruction_sha256') != request['instruction_sha256'] or
                hashlib.sha256(json.dumps(request['payload'], sort_keys=True).encode()).hexdigest()
                != request['request_sha256'] or
                attempt.get('manifest_sha256') != closure['source_bindings'][str(BASE / repeat / 'manifest.json')] or
                attempt.get('reference_labels_read') is not False or
                attempt.get('billing_ok') is not True or attempt.get('cost_unknown') is not False or
                attempt.get('reserved_cost_usd') != plan['per_request_reserve_usd'] or
                not Decimal(0) <= Decimal(attempt['observed_cost_usd']) <=
                Decimal(plan['per_request_reserve_usd']) or
                captured.get('id') != rid or
                captured.get('attempt_id') != attempt.get('attempt_id') or
                captured.get('request_sha256') != request['request_sha256'] or
                captured.get('http_status') != 200 or
                captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None):
            raise ValueError('DeepSeek high later-stage attempt differs from frozen request')
        body = base64.b64decode(captured['body_base64'], validate=True)
        if len(body) != captured['body_bytes_captured'] or json.loads(body) != attempt['raw_response']:
            raise ValueError('DeepSeek high later-stage raw response differs')
        raw = attempt['raw_response']
        choices = raw.get('choices')
        if (not isinstance(choices, list) or len(choices) != 1 or
                raw.get('model') != attempt.get('returned_model') or
                raw.get('model') != MODEL or raw.get('provider') != 'OpenInference' or
                raw.get('provider') != attempt.get('returned_provider') or
                raw.get('usage') != attempt.get('usage') or
                Decimal(str(raw['usage']['cost'])) != Decimal(attempt['observed_cost_usd'])):
            raise ValueError('DeepSeek high later-stage raw identity or cost differs')
        choice = choices[0]
        message = choice.get('message') or {}
        if choice.get('error') or any(message.get(k) for k in ('refusal', 'tool_calls', 'function_call')):
            raise ValueError('DeepSeek high later-stage response control differs')
        try:
            prediction = json.loads(message.get('content'))
        except (TypeError, ValueError):
            prediction = None
        status = 'ok' if valid(prediction) and choice.get('finish_reason') == 'stop' else 'invalid_output'
        if attempt.get('status') != status or attempt.get('prediction') != prediction:
            raise ValueError('DeepSeek high later-stage classification differs')
        diagnostic = attempt.get('response_diagnostic') or {}
        if status == 'ok':
            if diagnostic.get('passed') is not True:
                raise ValueError('DeepSeek high later-stage valid diagnostic differs')
        else:
            if (choice.get('finish_reason') not in ('stop', 'length') or
                    set(diagnostic.get('blockers', ())) - {'truncation:length'}):
                raise ValueError('DeepSeek high later-stage invalid is not intrinsic')
            invalid_ids.append(rid)
        for offset, event_name in ((1, 'request_intent'), (2, 'request_started'),
                                   (3, 'request_finished')):
            event = journal[1 + n*3 + offset-1]
            if event.get('event') != event_name or event.get('id') != rid:
                raise ValueError('DeepSeek high later-stage journal order differs')
            if event_name != 'request_finished' and event.get('request_sha256') != request['request_sha256']:
                raise ValueError('DeepSeek high later-stage journal request differs')
            if event_name != 'request_intent' and event.get('attempt_id') != attempt['attempt_id']:
                raise ValueError('DeepSeek high later-stage journal attempt differs')
            if event_name == 'request_finished' and (
                    event.get('status') != status or event.get('billing_ok') is not True or
                    event.get('cost_unknown') is not False or
                    event.get('observed_cost_usd') != attempt['observed_cost_usd']):
                raise ValueError('DeepSeek high later-stage journal status differs')
        pair = events.get(attempt['attempt_id'])
        if (not pair or pair[0].get('record_id') != rid or
                pair[0].get('usd') != plan['per_request_reserve_usd'] or
                pair[1].get('usd') != attempt['observed_cost_usd']):
            raise ValueError('DeepSeek high later-stage settlement differs')
        known += Decimal(attempt['observed_cost_usd'])
        status_counts[status] = status_counts.get(status, 0) + 1
    for attempt in smoke:
        pair = events.get(attempt.get('attempt_id'))
        if (not pair or pair[0].get('record_id') != attempt.get('id') or
                pair[0].get('usd') != plan['per_request_reserve_usd'] or
                pair[1].get('usd') != attempt.get('observed_cost_usd')):
            raise ValueError('DeepSeek high later-stage smoke settlement differs')
    score = existing.existing.score(attempts, labels, IDS)
    if (closure.get('status_counts') != status_counts or
            closure.get('valid_count') != score['valid'] or
            closure.get('intrinsic_invalid_ids') != invalid_ids or
            closure.get('all_four_correct_fixed_denominator') != score['allFour'] or
            closure.get('known_development_cost_usd') != str(known)):
        raise ValueError('DeepSeek high later-stage closure score or cost differs')
    usage = {'requestCount': 60, 'startedRequestCount': 60,
             'tokens': {key: sum(a['usage'][key] for a in attempts)
                        for key in ('prompt_tokens', 'completion_tokens')},
             'knownCostUsd': str(known), 'actualCostUsd': str(known),
             'unknownCostCount': 0, 'requestSecondsTotal': None}
    return {'status': 'completed_with_intrinsic_invalid' if invalid_ids else 'completed',
            'score': score, 'usage': usage}


def build(root=ROOT):
    root = Path(root).resolve()
    report = existing.build(root)
    if report.get('schema') != 'additional-hosted-fresh-repeat-findings-v1' or any(
            item.get('configuration') == CONFIG for item in report['series']):
        raise ValueError('DeepSeek high series duplicates an existing series')
    bindings = []
    bind = lambda path, digest=None: existing.bind(root, path, bindings, digest)
    read = lambda path: json.loads(existing.file(root, path).read_text())
    bind('scripts/build_deepseek_high_authority_v3_findings.py')
    bind('scripts/build_qwen36_on_hosted_authority_v2_findings.py')
    execution_path = BASE / 'execution-manifest.json'
    execution = read(execution_path)
    bind(execution_path)
    plan_path = BASE / 'fresh1/manifest.json'
    plan = read(plan_path)
    bind(plan_path, execution['plans_sha256']['fresh1'])
    if (execution.get('schema') != 'deepseek-high-authority-v3-execution' or
            execution.get('configuration_id') != CONFIG or
            plan.get('schema') != 'deepseek-high-authority-v3-plan' or
            plan.get('configuration_id') != CONFIG or plan.get('fresh_pass') != 'fresh1' or
            plan.get('model') != MODEL or plan.get('provider_tag') != PROVIDER or
            plan.get('reasoning_effort') != 'high' or
            plan.get('continue_on_invalid_output') is not True or
            plan.get('reference_labels_read') is not False):
        raise ValueError('DeepSeek high frozen identity or invalid policy differs')
    for item in plan['source_bindings']:
        bind(item['path'], item['sha256'])
    for repeat, digest in execution['plans_sha256'].items():
        bind(BASE / repeat / 'manifest.json', digest)
    bind(BASE / 'public-route.json', execution['public_route_sha256'])
    for name, digest in execution['source_code_sha256'].items():
        bind(Path('scripts') / name, digest)
    bind(LABELS, '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464')
    labels = existing.rows(root, LABELS)
    if [x.get('id') for x in labels] != IDS:
        raise ValueError('DeepSeek high labels differ')
    labels = {x['id']: x['proposed_labels'] for x in labels}
    closure_path = FOLDER / 'closure.root-review.json'
    closure = read(closure_path)
    bind(closure_path)
    if (closure.get('schema') != 'deepseek-high-authority-v3-p0-closure-root-review-v1' or
            closure.get('verdict') != 'APPROVE' or closure.get('independent_review') is not True or
            closure.get('configuration_id') != CONFIG or
            closure.get('stage') != 'fresh1/P0/development' or
            closure.get('provider') != PROVIDER or closure.get('model') != MODEL or
            closure.get('frozen_continue_on_invalid_output') is not True or
            closure.get('status_counts') != {'ok': 59, 'invalid_output': 1} or
            closure.get('intrinsic_invalid_ids') != ['DEV-030'] or
            closure.get('record_count') != 60 or closure.get('valid_count') != 59 or
            closure.get('unknown_cost_count') != 0):
        raise ValueError('DeepSeek high P0 closure is not verified')
    for path, digest in closure['source_bindings'].items():
        bind(path, digest)
    snapshot = closure['child_ledger_at_review']
    if (snapshot['snapshot_path'] != str(FOLDER / 'closure-ledger-snapshot.jsonl') or
            snapshot['sha256'] != next(x['sha256'] for x in bindings
                if x['path'] == snapshot['snapshot_path']) or
            snapshot['settled_attempt_count'] != 63 or snapshot['pending_count'] != 0):
        raise ValueError('DeepSeek high closure lacks immutable child ledger')
    ledger = existing.rows(root, snapshot['snapshot_path'])
    requests = plan['conditions']['P0']['development']
    attempts = existing.rows(root, FOLDER / 'development.attempts.jsonl')
    responses = existing.rows(root, FOLDER / 'development.responses.jsonl')
    journal = existing.rows(root, FOLDER / 'development.journal.jsonl')
    smoke = existing.rows(root, FOLDER / 'smoke.attempts.jsonl')
    if ([r['record_id'] for r in requests] != IDS or
            [a.get('id') for a in attempts] != IDS or
            [r.get('id') for r in responses] != IDS or
            len({a['attempt_id'] for a in attempts}) != 60 or
            len(journal) != 182 or journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('attempt_ids') != [a['attempt_id'] for a in attempts] or
            len(smoke) != 3 or len(ledger) != 127 or ledger[0] != {'event': 'budget', 'cap_usd': '0.90'}):
        raise ValueError('DeepSeek high phase membership or closure differs')
    known = Decimal(0)
    for request, attempt, response in zip(requests, attempts, responses):
        rid = request['record_id']
        if (attempt['configuration_id'] != CONFIG or attempt['requested_model'] != MODEL or
                attempt['reasoning_effort'] != 'high' or
                attempt['provider_endpoint']['tag'] != PROVIDER or
                attempt['request_sha256'] != request['request_sha256'] or
                attempt['request'] != request['payload'] or
                attempt['reference_labels_read'] is not False or
                attempt['cost_unknown'] is not False or attempt['billing_ok'] is not True or
                response['attempt_id'] != attempt['attempt_id'] or
                response['request_sha256'] != request['request_sha256'] or
                response['http_status'] != 200 or response['body_truncated_at_limit'] or
                response['read_error'] is not None):
            raise ValueError('DeepSeek high attempt differs from frozen request')
        body = base64.b64decode(response['body_base64'], validate=True)
        if (len(body) != response['body_bytes_captured'] or
                json.loads(body) != attempt['raw_response']):
            raise ValueError('DeepSeek high raw response differs')
        choice = attempt['raw_response']['choices'][0]
        message = choice.get('message') or {}
        try:
            prediction = json.loads(message.get('content'))
        except (TypeError, ValueError):
            prediction = None
        status = 'ok' if valid(prediction) and choice['finish_reason'] == 'stop' else 'invalid_output'
        if (attempt['status'] != status or attempt['prediction'] != prediction or
                attempt['raw_response']['provider'] != 'OpenInference' or
                attempt['raw_response']['model'] != MODEL or
                Decimal(str(attempt['raw_response']['usage']['cost'])) !=
                Decimal(attempt['observed_cost_usd'])):
            raise ValueError('DeepSeek high raw classification or charge differs')
        if rid == 'DEV-030':
            if (status != 'invalid_output' or prediction is not None or
                    choice['finish_reason'] != 'length' or
                    attempt['response_diagnostic']['blockers'] != ['truncation:length']):
                raise ValueError('DeepSeek high intrinsic invalid was repaired')
        elif status != 'ok' or attempt['response_diagnostic']['passed'] is not True:
            raise ValueError('DeepSeek high unexpected invalid result')
        known += Decimal(attempt['observed_cost_usd'])
    for n, attempt in enumerate([*smoke, *attempts]):
        reserve, settle = ledger[1 + 2*n:3 + 2*n]
        if (reserve.get('event') != 'reserve' or settle.get('event') != 'settle' or
                reserve.get('attempt_id') != attempt['attempt_id'] or
                settle.get('attempt_id') != attempt['attempt_id'] or
                reserve.get('record_id') != attempt['id'] or
                reserve.get('usd') != plan['per_request_reserve_usd'] or
                settle.get('usd') != attempt['observed_cost_usd']):
            raise ValueError('DeepSeek high immutable child settlement differs')
    score = existing.existing.score(attempts, labels, IDS)
    if (score['valid'] != 59 or score['allFour'] != 57 or
            score['invalidIds'] != ['DEV-030'] or
            score['outcomes'] != closure['status_counts'] or
            str(known) != closure['known_development_cost_usd']):
        raise ValueError('DeepSeek high source-bound score or cost differs')
    usage = {'requestCount': 60, 'startedRequestCount': 60,
             'tokens': {key: sum(a['usage'][key] for a in attempts)
                        for key in ('prompt_tokens', 'completion_tokens')},
             'knownCostUsd': str(known), 'actualCostUsd': str(known),
             'unknownCostCount': 0, 'requestSecondsTotal': None}
    passes = {'fresh1': {'P0': {'status': 'completed_with_intrinsic_invalid',
                                'score': score, 'usage': usage}},
              'fresh2': {}, 'fresh3': {}}
    for repeat in PASSES:
        for condition in CONDITIONS:
            if (repeat, condition) == ('fresh1', 'P0'):
                continue
            stage_folder = BASE / repeat / condition
            stage_closure_path = stage_folder / 'closure.root-review.json'
            if not existing.file(root, stage_closure_path).is_file():
                continue
            stage_closure = read(stage_closure_path)
            if (stage_closure.get('verdict') != 'APPROVE' or
                    stage_closure.get('independent_review') is not True):
                continue
            stage_plan_path = BASE / repeat / 'manifest.json'
            stage_plan = read(stage_plan_path)
            if (stage_plan.get('schema') != 'deepseek-high-authority-v3-plan' or
                    stage_plan.get('configuration_id') != CONFIG or
                    stage_plan.get('fresh_pass') != repeat or
                    stage_plan.get('model') != MODEL or
                    stage_plan.get('provider_tag') != PROVIDER or
                    stage_plan.get('reasoning_effort') != 'high' or
                    stage_plan.get('continue_on_invalid_output') is not True or
                    stage_plan.get('reference_labels_read') is not False):
                raise ValueError('DeepSeek high later-stage frozen plan differs')
            for item in stage_plan['source_bindings']:
                bind(item['path'], item['sha256'])
            bind(stage_closure_path)
            passes[repeat][condition] = later_stage(
                root, stage_plan, repeat, condition, stage_closure, bind, labels)
    completed = sum(len(conditions) for conditions in passes.values())
    clean = sum(phase['status'] == 'completed' for conditions in passes.values()
                for phase in conditions.values())
    series = {'schema': 'additional-hosted-fresh-repeat-findings-v1',
              'configuration': CONFIG, 'seriesId': SERIES,
              'displayName': 'DeepSeek V4.1 Flash · OpenInference fp4 · reasoning high · current-price fresh series',
              'method': 'fresh-matched-three', 'model': MODEL, 'effort': 'high',
              'provider': PROVIDER, 'denominator': 60, 'plannedConditions': 9,
              'completedConditions': completed, 'cleanCompletedConditions': clean,
              'conditionOrder': ['P0', 'P1', 'P2'],
              'passOrder': ['fresh1', 'fresh2', 'fresh3'],
              'passes': passes,
              'missingPasses': [{'pass': p, 'condition': c, 'status': 'not_published'}
                                for p in PASSES for c in CONDITIONS if c not in passes[p]],
              'threePassSummary': {}, 'pairwiseFlips': [], 'changesAcrossThreePasses': {},
              'withinPassPromptDeltas': [], 'pairedDeltaSpread': {},
              'historicalPassUsed': False, 'sourceBindings': bindings,
              'limitations': ['P0 completed all 60 requests. DEV-030 returned a length-truncated, billed output and remains invalid.',
                              'The 57/60 four-field score keeps DEV-030 in the denominator.',
                              'Provisional v0.2 references are not independent accuracy evidence.',
                              'Other phases are excluded until independently closed and source-bound.']}
    report['series'].append(series)
    report['availableConfigurations'].append(CONFIG)
    for item in bindings:
        if item not in report['sourceBindings']:
            report['sourceBindings'].append(item)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    value = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != value:
            raise ValueError('Stale DeepSeek high hosted report')
    else:
        args.output.write_text(value)
    print('DeepSeek high hosted report verified' if args.check else 'DeepSeek high hosted report written')


if __name__ == '__main__':
    main()
