#!/usr/bin/env python3
"""Publish closed Qwen hosted ON evidence without replaying the interrupted request."""
import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import build_additional_hosted_fresh_repeat_findings as existing
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/qwen36-on-hosted-authority-v3-v2')
CONT = BASE / 'p1-unsent-continuation-v1'
REMAINING = BASE / 'remaining-hosted-v1'
REMAINING_STAGES = (('fresh1', 'P2'), ('fresh2', 'P1'), ('fresh2', 'P2'),
                    ('fresh2', 'P0'), ('fresh3', 'P2'), ('fresh3', 'P0'),
                    ('fresh3', 'P1'))
CONFIG = 'openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2'
SERIES = CONFIG + '-fresh-matched3'
MODEL = 'qwen/qwen3.6-35b-a3b'
PROVIDER = 'akashml/fp8'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
LABELS = Path('data/pilot/proposed_labels.jsonl')
PRIVATE_HISTORICAL = frozenset((
    'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen36-35b-a3b-on/P1/smoke.jsonl',
    'results/qwen36-on-p2-final19-v4/development.jsonl',
    'results/qwen36-on-p2-final20-v3/development.jsonl',
    'results/qwen36-on-p2-final21-v2/development.jsonl',
    'results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix.jsonl',
    'results/qwen36-prompt-recovery-v1/on-p2-development.jsonl',
))


def file(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Qwen report source escapes root')
    result = (root / relative).resolve()
    result.relative_to(root.resolve())
    return result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(root, relative, bindings, expected=None):
    actual = sha(file(root, relative))
    if expected is not None and actual != expected:
        raise ValueError('Qwen report source hash differs: ' + str(relative))
    item = {'path': str(relative), 'sha256': actual}
    if item not in bindings:
        bindings.append(item)
    return item


def rows(root, relative):
    raw = file(root, relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError('Incomplete Qwen evidence: ' + str(relative))
    return [json.loads(line) for line in raw.splitlines()]


def stage(root, folder, requests, ids, bindings, phase='development'):
    paths = {kind: folder / (phase + '.' + kind + '.jsonl') for kind in
             ('attempts', 'responses', 'journal')}
    for path in paths.values():
        bind(root, path, bindings)
    attempts = rows(root, paths['attempts'])
    responses = rows(root, paths['responses'])
    if [a.get('id') for a in attempts] != ids or len(set(ids)) != len(ids):
        raise ValueError('Qwen attempt membership differs')
    indexed = {r.get('attempt_id'): r for r in responses}
    if len(indexed) != len(responses) or None in indexed:
        raise ValueError('Qwen raw attempt identity differs')
    known = Decimal(0)
    for attempt, request in zip(attempts, requests):
        rid = attempt['id']
        if (request['record_id'] != rid or attempt.get('configuration_id') != CONFIG or
                attempt.get('requested_model') != MODEL or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('request') != request['payload'] or
                attempt.get('reference_labels_read') is not False):
            raise ValueError('Qwen attempt differs from frozen request')
        if attempt['status'] == 'ok':
            if not valid(attempt.get('prediction')) or attempt.get('cost_unknown') is not False:
                raise ValueError('Qwen valid result or cost state differs')
            response = indexed.pop(attempt['attempt_id'], None)
            if not isinstance(response, dict) or response.get('id') != rid or response.get('request_sha256') != request['request_sha256']:
                raise ValueError('Qwen raw response missing')
            body = base64.b64decode(response['body_base64'], validate=True)
            if (response.get('http_status') != 200 or response.get('body_truncated_at_limit') or
                    response.get('body_bytes_captured') != len(body) or
                    json.loads(body) != attempt.get('raw_response')):
                raise ValueError('Qwen raw response differs from saved attempt')
            known += Decimal(str(attempt['observed_cost_usd']))
        elif (rid != 'DEV-049' or attempt.get('cost_unknown') is not True or
              attempt.get('prediction') is not None or attempt['attempt_id'] in indexed):
            raise ValueError('Qwen unknown outcome was repaired or substituted')
    if indexed:
        raise ValueError('Qwen unexpected raw response exists')
    return attempts, known


def closed_remaining_stage(root, execution, repeat, condition, labels, bindings):
    folder = REMAINING / CONFIG / repeat / condition
    receipt_path = folder / 'closure.review.json'
    if not file(root, receipt_path).exists():
        return None
    receipt = json.loads(file(root, receipt_path).read_text())
    bind(root, receipt_path, bindings)
    metrics = receipt.get('metrics') or {}
    checks = receipt.get('checks') or {}
    sources = receipt.get('source_bindings') or {}
    plan_path = REMAINING / CONFIG / repeat / 'manifest.json'
    plan = json.loads(file(root, plan_path).read_text())
    original_plan_path = BASE / repeat / 'manifest.json'
    original = json.loads(file(root, original_plan_path).read_text())
    bind(root, plan_path, bindings, execution['plans_sha256'][repeat])
    bind(root, original_plan_path, bindings, execution['source_bindings']['original_plan_' + repeat]['sha256'])
    if (plan.get('configuration_id') != CONFIG or plan.get('fresh_pass') != repeat or
            plan.get('conditions') != original.get('conditions') or
            plan.get('reference_labels_read') is not False or
            (repeat, condition) not in REMAINING_STAGES or
            receipt.get('schema') != 'qwen36-on-remaining-hosted-phase-closure-v1' or
            receipt.get('verdict') != 'APPROVE' or
            (receipt.get('configuration_id'), receipt.get('fresh_pass'),
             receipt.get('condition'), receipt.get('phase')) !=
            (CONFIG, repeat, condition, 'development') or
            not all(checks.get(key) is True for key in (
                'frozen_successor_plan_and_execution_verified',
                'smoke_and_development_verified_by_private_runner',
                'sixty_ordered_requests_and_raw_strict_outputs_valid',
                'terminal_phase_completed',
                'one_matching_reserve_and_settlement_per_attempt')) or
            checks.get('reference_labels_read_during_inference') is not False or
            sources.get('ledger_snapshot', {}).get('path') != str(
                REMAINING / f'budget-at-{repeat}-{condition.lower()}-closure.jsonl')):
        raise ValueError('Qwen remaining hosted closure identity or controls differ')
    required = {'execution_manifest': REMAINING / 'execution-manifest.json',
                repeat + '_plan': plan_path,
                'budget_manifest': REMAINING / 'budget.json',
                'ledger_snapshot': REMAINING / f'budget-at-{repeat}-{condition.lower()}-closure.jsonl',
                'smoke_claim': folder / 'smoke.claim.json',
                'smoke_root_review': folder / 'smoke.root-review.json',
                'smoke_inspection': folder / 'smoke-inspection.json',
                'smoke_journal': folder / 'smoke.journal.jsonl',
                'smoke_attempts': folder / 'smoke.attempts.jsonl',
                'smoke_responses': folder / 'smoke.responses.jsonl',
                'development_claim': folder / 'development.claim.json',
                'development_root_review': folder / 'development.root-review.json',
                'development_journal': folder / 'development.journal.jsonl',
                'development_attempts': folder / 'development.attempts.jsonl',
                'development_responses': folder / 'development.responses.jsonl',
                'reference_labels': LABELS,
                'controller': Path('scripts/qwen36_on_remaining_hosted_v1.py'),
                'verifier': Path('scripts/qwen27_fresh_repeat_execution.py')}
    if set(sources) != set(required):
        raise ValueError('Qwen remaining hosted closure source set differs')
    for name, path in required.items():
        if sources[name].get('path') != str(path):
            raise ValueError('Qwen remaining hosted closure source path differs')
        bind(root, path, bindings, sources[name]['sha256'])
    snapshot = rows(root, required['ledger_snapshot'])
    if not snapshot or snapshot[0] != {'event': 'budget', 'cap_usd': '1.00'}:
        raise ValueError('Qwen remaining hosted child snapshot differs')
    attempts_by_phase = {}
    costs = {}
    for phase, expected_ids in (('smoke', IDS[:3]), ('development', IDS)):
        requests = plan['conditions'][condition][phase]
        attempts, cost = stage(root, folder, requests, expected_ids, bindings,
                               phase=phase)
        claim = json.loads(file(root, folder / (phase + '.claim.json')).read_text())
        events = rows(root, folder / (phase + '.journal.jsonl'))
        if ((claim.get('configuration_id'), claim.get('fresh_pass'),
             claim.get('condition'), claim.get('phase')) !=
            (CONFIG, repeat, condition, phase) or
                claim.get('manifest_sha256') != sha(file(root, plan_path)) or
                events[-1].get('event') != 'phase_completed' or
                (events[-1].get('configuration_id'), events[-1].get('fresh_pass'),
                 events[-1].get('condition'), events[-1].get('phase')) !=
                (CONFIG, repeat, condition, phase) or
                events[-1].get('request_count') != len(expected_ids) or
                events[-1].get('attempt_ids') != [a['attempt_id'] for a in attempts]):
            raise ValueError('Qwen remaining hosted phase closure differs')
        for attempt in attempts:
            body = attempt['raw_response']
            choices = body.get('choices')
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError('Qwen remaining hosted strict output differs')
            choice = choices[0]
            message = choice.get('message') or {}
            if ((attempt.get('configuration_id'), attempt.get('fresh_pass'),
                 attempt.get('condition'), attempt.get('phase')) !=
                (CONFIG, repeat, condition, phase) or
                    attempt['status'] != 'ok' or attempt.get('billing_ok') is not True or
                    attempt.get('reference_labels_read') is not False or
                    choice.get('finish_reason') != 'stop' or
                    any(message.get(key) for key in ('refusal', 'tool_calls', 'function_call')) or
                    choice.get('error') or
                    json.loads(message['content']) != attempt['prediction'] or
                    Decimal(str(body['usage']['cost'])) != Decimal(attempt['observed_cost_usd']) or
                    body.get('provider') != plan['provider_name'] or
                    attempt.get('returned_model') != body.get('model')):
                raise ValueError('Qwen remaining hosted strict output differs')
            reserves = [event for event in snapshot if event.get('event') == 'reserve'
                        and event.get('attempt_id') == attempt['attempt_id']]
            settles = [event for event in snapshot if event.get('event') == 'settle'
                       and event.get('attempt_id') == attempt['attempt_id']]
            if (len(reserves) != 1 or len(settles) != 1 or
                    reserves[0].get('record_id') != attempt['id'] or
                    Decimal(reserves[0]['usd']) != Decimal(attempt['reserved_cost_usd']) or
                    Decimal(settles[0]['usd']) != Decimal(attempt['observed_cost_usd'])):
                raise ValueError('Qwen remaining hosted settlement differs')
        attempts_by_phase[phase] = attempts
        costs[phase] = cost
    score = existing.score(attempts_by_phase['development'], labels, IDS)
    if (metrics.get('smoke_attempts') != 3 or metrics.get('development_attempts') != 60 or
            metrics.get('valid_records') != 60 or metrics.get('invalid_records') != 0 or
            metrics.get('all_four_denominator') != 60 or
            metrics.get('all_four_matches') != score['allFour'] or
            metrics.get('development_observed_cost_usd') != str(costs['development']) or
            metrics.get('smoke_observed_cost_usd') != str(costs['smoke']) or
            metrics.get('smoke_plus_development_observed_cost_usd') !=
            str(costs['smoke'] + costs['development']) or
            metrics.get('child_events_at_closure') != len(snapshot) or
            metrics.get('child_reservations_at_closure') !=
            sum(event.get('event') == 'reserve' for event in snapshot) or
            metrics.get('child_settlements_at_closure') !=
            sum(event.get('event') == 'settle' for event in snapshot)):
        raise ValueError('Qwen remaining hosted closure metrics differ')
    return attempts_by_phase['development'], costs['development'], score


def build(root=ROOT):
    root = Path(root).resolve()
    old = existing.build(root, configuration='openrouter-paid-deepseek-v41-flash-low')
    if old.get('schema') != 'additional-hosted-fresh-repeat-findings-v1' or any(
            s.get('configuration') == CONFIG for s in old['series']):
        raise ValueError('Qwen hosted series duplicates an existing series')
    bindings = []
    bind(root, 'scripts/build_qwen36_on_hosted_authority_v2_findings.py', bindings)
    bind(root, 'scripts/build_additional_hosted_fresh_repeat_findings.py', bindings)
    execution_path = BASE / 'execution-manifest.json'
    execution = json.loads(file(root, execution_path).read_text())
    bind(root, execution_path, bindings)
    plan_path = BASE / 'fresh1/manifest.json'
    plan = json.loads(file(root, plan_path).read_text())
    bind(root, plan_path, bindings, execution['plans_sha256']['fresh1'])
    if (execution.get('configuration_id') != CONFIG or plan.get('configuration_id') != CONFIG or
            plan.get('model') != MODEL or plan.get('provider_tag') != PROVIDER or
            plan.get('fresh_pass') != 'fresh1' or plan.get('reference_labels_read') is not False):
        raise ValueError('Qwen hosted plan identity differs')
    for item in plan['source_bindings']:
        if item['path'] in PRIVATE_HISTORICAL:
            if not isinstance(item.get('sha256'), str) or len(item['sha256']) != 64:
                raise ValueError('Private historical Qwen source hash missing from frozen plan')
            continue
        bind(root, item['path'], bindings, item['sha256'])
    for repeat, digest in execution['plans_sha256'].items():
        bind(root, BASE / repeat / 'manifest.json', bindings, digest)
    bind(root, BASE / 'public-route.json', bindings, execution['public_route_sha256'])
    for name, digest in execution['source_code_sha256'].items():
        bind(root, Path('scripts') / name, bindings, digest)
    bind(root, LABELS, bindings, '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464')
    label_rows = rows(root, LABELS)
    if [row.get('id') for row in label_rows] != IDS:
        raise ValueError('Qwen label membership differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    p0_folder = BASE / 'fresh1/P0'
    p0_closure_path = p0_folder / 'closure.root-review.json'
    p0_closure = json.loads(file(root, p0_closure_path).read_text())
    bind(root, p0_closure_path, bindings)
    if (p0_closure.get('schema') != 'qwen36-hosted-root-closure-v1' or
            p0_closure.get('configuration_id') != CONFIG or
            p0_closure.get('stage') != 'fresh1/P0/development' or
            p0_closure.get('frozen_closure_validator_passed') is not True or
            p0_closure.get('record_count') != 60):
        raise ValueError('Qwen P0 closure is not independently verified')
    for name, digest in p0_closure['sources'].items():
        bind(root, p0_folder / name, bindings, digest)
    p0, p0_cost = stage(root, p0_folder, plan['conditions']['P0']['development'], IDS, bindings)
    if any(a['status'] != 'ok' for a in p0) or str(p0_cost) != p0_closure['observed_cost_usd']:
        raise ValueError('Qwen P0 closure differs from requests or charges')
    cont_path = CONT / 'manifest.json'
    continuation = json.loads(file(root, cont_path).read_text())
    bind(root, cont_path, bindings)
    closure_path = CONT / 'closure.review.json'
    closure = json.loads(file(root, closure_path).read_text())
    bind(root, closure_path, bindings)
    if (continuation.get('schema') != 'qwen36-on-p1-unsent-continuation-v1' or
            continuation.get('configuration_id') != CONFIG or
            continuation.get('never_sent_ids') != IDS[49:] or
            continuation.get('parent_unknown_attempted_id') != 'DEV-049' or
            closure.get('schema') != 'qwen36-on-p1-unsent-closure-review-v1' or
            closure.get('verdict') != 'CLOSED_11_VALID' or closure.get('clean_full_phase') is not False or
            closure.get('manifest_sha256') != sha(file(root, cont_path)) or
            closure.get('configuration_id') != CONFIG or closure.get('model') != MODEL or
            closure.get('provider') != PROVIDER or closure.get('composite_unknown_ids') != ['DEV-049'] or
            closure.get('composite_denominator') != 60 or closure.get('composite_valid') != 59 or
            closure.get('suffix_ids') != IDS[49:]):
        raise ValueError('Qwen P1 descriptive closure differs')
    for item in continuation['source_bindings'].values():
        bind(root, item['path'], bindings, item['sha256'])
    for name, item in closure['source_bindings'].items():
        if name == 'new_child_ledger_at_review' and not item['path'].endswith('budget-before-reconciliation.jsonl'):
            raise ValueError('Qwen closure binds an active child ledger')
        bind(root, item['path'], bindings, item['sha256'])
    parent, parent_cost = stage(root, BASE / 'fresh1/P1', plan['conditions']['P1']['development'][:49], IDS[:49], bindings)
    suffix, suffix_cost = stage(root, CONT / 'fresh1/P1', continuation['requests'], IDS[49:], bindings)
    if ([a['status'] for a in parent] != ['ok'] * 48 + [parent[-1]['status']] or
            parent[-1]['status'] == 'ok' or any(a['status'] != 'ok' for a in suffix) or
            str(parent_cost) != closure['parent_p1_known_cost_usd'] or
            str(suffix_cost) != closure['suffix_known_cost_usd']):
        raise ValueError('Qwen interrupted P1 attempts or charges differ')
    p0_score = existing.score(p0, labels, IDS)
    composite = [*parent, *suffix]
    p1_score = existing.score(composite, labels, IDS)
    if (p0_score['allFour'] != 54 or p0_score['valid'] != 60 or
            p1_score['allFour'] != closure['composite_all_four_correct'] or
            p1_score['valid'] != 59 or
            p1_score['fields'] != closure['reference_score']['field_correct'] or
            str(parent_cost + suffix_cost) != closure['composite_known_p1_cost_usd']):
        raise ValueError('Qwen source-bound score or cost differs')
    def usage(attempts, cost, unknown=False):
        return {'requestCount': len(attempts), 'startedRequestCount': len(attempts),
                'tokens': {key: sum(a['usage'][key] for a in attempts)
                           if all(type(a.get('usage', {}).get(key)) is int for a in attempts) else None
                           for key in ('prompt_tokens', 'completion_tokens')},
                'knownCostUsd': str(cost), 'actualCostUsd': None if unknown else str(cost),
                'unknownCostCount': int(unknown), 'requestSecondsTotal': None}
    series = {'schema': 'additional-hosted-fresh-repeat-findings-v1',
              'configuration': CONFIG, 'seriesId': SERIES,
              'displayName': 'Qwen3.6 35B A3B · AkashML fp8 · reasoning on · hosted fresh series',
              'method': 'fresh-matched-three', 'model': MODEL, 'effort': 'on',
              'provider': PROVIDER, 'denominator': 60, 'plannedConditions': 9,
              'completedConditions': 1, 'conditionOrder': ['P0', 'P1', 'P2'],
              'cleanMatchedThreeEligible': False,
              'passOrder': ['fresh1', 'fresh2', 'fresh3'],
              'passes': {'fresh1': {
                  'P0': {'status': 'completed', 'score': p0_score, 'usage': usage(p0, p0_cost)},
                  'P1': {'status': 'completed_interrupted_composite', 'score': p1_score,
                         'usage': usage(composite, parent_cost + suffix_cost, True),
                         'unknownChargeUpperBoundUsd': closure['parent_unknown_charge_upper_bound_usd']}},
                  'fresh2': {}, 'fresh3': {}},
              'missingPasses': [{'pass': 'fresh1', 'condition': 'P1', 'status': 'interrupted_descriptive'},
                                *({'pass': p, 'condition': c, 'status': 'not_started'}
                                   for p in ('fresh1', 'fresh2', 'fresh3') for c in ('P0', 'P1', 'P2')
                                   if (p, c) not in (('fresh1', 'P0'), ('fresh1', 'P1')))],
              'threePassSummary': {}, 'pairwiseFlips': [], 'changesAcrossThreePasses': {},
              'withinPassPromptDeltas': [], 'pairedDeltaSpread': {},
              'historicalPassUsed': False, 'sourceBindings': bindings,
              'publicVerificationLimit': 'Six private historical Qwen controls remain hash-declared in the frozen plan; this public report scores only the source-bound current-authority P0 and P1 evidence.',
              'limitations': ['The same 60 synthetic development records recur in every pass.',
                              'P1 combines 48 original valid answers and 11 separately sent valid answers; DEV-049 remains an unknown timeout.',
                              'The 52/60 P1 agreement is descriptive and earns no clean repeat credit.',
                              'Provisional v0.2 references are not independent accuracy evidence.',
                              'The $0.0299008 unknown-charge bound is retained separately from known charges.']}
    remaining_execution_path = REMAINING / 'execution-manifest.json'
    remaining_execution = json.loads(file(root, remaining_execution_path).read_text())
    bind(root, remaining_execution_path, bindings)
    if (remaining_execution.get('schema') != 'qwen36-on-remaining-hosted-v1-execution' or
            remaining_execution.get('configuration_id') != CONFIG or
            remaining_execution.get('clean_matched_three_eligible') is not False or
            remaining_execution.get('predecessor', {}).get('p1_composite') !=
            'descriptive_59_valid_1_unknown' or
            [(item.get('fresh_pass'), item.get('condition'))
             for item in remaining_execution.get('schedule', [])] != list(REMAINING_STAGES) or
            remaining_execution.get('partition_id') != 'qwen36-on-remaining-hosted-v1'):
        raise ValueError('Qwen remaining hosted execution identity differs')
    found_gap = False
    for repeat, condition in REMAINING_STAGES:
        result = closed_remaining_stage(root, remaining_execution, repeat, condition,
                                        labels, bindings)
        if result is None:
            found_gap = True
            continue
        if found_gap:
            raise ValueError('Qwen remaining hosted closure skips a prior stage')
        attempts, cost, score = result
        series['passes'][repeat][condition] = {
            'status': 'completed', 'score': score, 'usage': usage(attempts, cost)}
        series['completedConditions'] += 1
        series['missingPasses'] = [item for item in series['missingPasses']
                                   if (item['pass'], item['condition']) != (repeat, condition)]
    if 'P2' in series['passes']['fresh1']:
        p2_score = series['passes']['fresh1']['P2']['score']
        series['withinPassPromptDeltas'].append({
            'pass': 'fresh1', 'from': 'P0', 'to': 'P2', 'denominator': 60,
            'allFour': p2_score['allFour'] - p0_score['allFour'],
            'fields': {key: p2_score['fields'][key] - p0_score['fields'][key]
                       for key in KEYS},
            'scope': 'descriptive matched first pass; interrupted P1 excluded'})
    series['publicVerificationLimit'] = (
        'Six private historical Qwen controls remain hash-declared in the frozen plan; '
        'this public report scores only independently closed current-authority phases. '
        'The interrupted P1 composite remains descriptive.')
    series['limitations'].append(
        'Remaining hosted phases use a separate child; each published phase binds its '
        'closure receipt and immutable child-ledger snapshot.')
    old['series'].append(series)
    old['availableConfigurations'].append(CONFIG)
    for item in bindings:
        if item not in old['sourceBindings']:
            old['sourceBindings'].append(item)
    return old


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    value = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != value:
            raise ValueError('Stale Qwen hosted public report')
    else:
        args.output.write_text(value)
    print('Qwen hosted public report verified' if args.check else 'Qwen hosted public report written')


if __name__ == '__main__':
    main()
