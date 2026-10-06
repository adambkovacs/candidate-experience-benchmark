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


def stage(root, folder, requests, ids, bindings):
    paths = {kind: folder / ('development.' + kind + '.jsonl') for kind in
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
