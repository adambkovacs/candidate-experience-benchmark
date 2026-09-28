#!/usr/bin/env python3
"""Offline Jev repeat admission audit. This module cannot dispatch or reserve."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, digest
from jev_benchmark import PRICE_MODEL, QUESTION_VERSION, parse_response, usage_cost
import jev_native_prompt_variants_v1 as native
from build_jev_native_prompt_report_v1 import validate_phase

BASE = ROOT / 'results/jev-native-prompt-variants-v1'
P0_PREFIX = ROOT / 'results/openjev/typesafe-development-v2.jsonl'
P0_CONTINUATION = ROOT / 'results/openjev/typesafe-development-v2-continuation.jsonl'
P0_SMOKE = ROOT / 'results/openjev/typesafe-smoke-v2.jsonl'
CAP = Decimal('1')
ORDERS = {'repeat2': ('P1', 'P2', 'P0'), 'repeat3': ('P2', 'P0', 'P1')}
IDS = [f'DEV-{i:03}' for i in range(1, 61)]
SMOKE_IDS = IDS[:3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def lines(path):
    raw = Path(path).read_bytes()
    if raw and (not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines())):
        raise ValueError('Incomplete Jev evidence: ' + str(path))
    return [json.loads(line) for line in raw.splitlines()]


def historical_p0(manifest):
    prefix, continuation = lines(P0_PREFIX), lines(P0_CONTINUATION)
    if ([r.get('id') for r in prefix] != IDS[:46] or
            [r.get('id') for r in continuation] != IDS[45:] or
            len(prefix) + len(continuation) != 61):
        raise ValueError('P0 is not the exact 46-attempt prefix plus 15-attempt continuation')
    all_attempts = prefix + continuation
    first = []
    seen = set()
    inputs, policy = native.load_inputs(), native.load_policy()
    policy_sha = digest(policy)
    attempt_ids = set()
    for row in all_attempts:
        rid = row['id']
        index = int(rid[4:]) - 1
        payload = native.payload(inputs[index]['feedback'], policy, 'P0')
        planned = manifest['requests']['P0'][index]
        request_sha = digest(json.dumps(payload, sort_keys=True))
        if (row.get('request_sha256') != request_sha or planned['request_sha256'] != request_sha or
                row.get('input_sha256') != digest(inputs[index]['feedback']) or
                row.get('policy_sha256') != policy_sha or
                row.get('questions_sha256') != digest(json.dumps(payload['questions'], sort_keys=True)) or
                row.get('question_order') != list(KEYS) or row.get('question_version') != QUESTION_VERSION or
                row.get('surface') != 'typesafe' or row.get('mode') != 'official' or
                row.get('requested_model') != PRICE_MODEL or row.get('retry_policy') != 'none' or
                row.get('local_extensions') != {} or row.get('reserved_cost_usd') != planned['reserve_usd'] or
                row.get('cost_unknown') is not (row.get('status') == 'service_error')):
            raise ValueError('P0 request controls or billing state differ: ' + rid)
        attempt = row.get('budget_attempt_id')
        if not isinstance(attempt, str) or not attempt or attempt in attempt_ids:
            raise ValueError('P0 budget attempt identity missing or reused')
        attempt_ids.add(attempt)
        if row.get('status') == 'ok':
            raw = row.get('raw_response')
            if (not isinstance(raw, dict) or row.get('returned_model') != PRICE_MODEL or
                    parse_response(raw, PRICE_MODEL) != row.get('prediction') or
                    row.get('estimated_usage_cost_usd') != str(usage_cost(raw))):
                raise ValueError('P0 successful response differs from raw Jev evidence: ' + rid)
        elif (rid != 'DEV-046' or row.get('status') != 'service_error' or
              row.get('error_type') != 'RemoteDisconnected' or row.get('raw_response') is not None or
              row.get('estimated_usage_cost_usd') is not None):
            raise ValueError('Unexpected P0 failure: ' + rid)
        if rid not in seen:
            first.append(row)
            seen.add(rid)
    if [r['id'] for r in first] != IDS or (
            [(r['id'], r['status']) for r in all_attempts if r['id'] == 'DEV-046'] !=
            [('DEV-046', 'service_error'), ('DEV-046', 'ok')]):
        raise ValueError('P0 first-attempt selector does not cover 60 distinct positions')
    return first, all_attempts


def historical_variants(manifest, manifest_sha):
    out = {}
    for variant in ('P1', 'P2'):
        native.receipt(BASE / f'{variant}-plan-review.json', 'jev-native-plan-review-v1', manifest_sha, variant)
        smoke, _ = validate_phase(BASE, variant, 'smoke', manifest, manifest_sha)
        native.receipt(BASE / f'{variant}-smoke-inspection.json', 'jev-native-smoke-inspection-v1',
                       manifest_sha, variant, sha(BASE / f'{variant}-smoke.jsonl'))
        development, _ = validate_phase(BASE, variant, 'development', manifest, manifest_sha)
        if Counter(x['status'] for x in smoke) != {'ok': 3} or (
                Counter(x['status'] for x in development) != {'ok': 59, 'invalid_output': 1}):
            raise ValueError('Historical Jev variant outcomes differ')
        out[variant] = (smoke, development)
    return out


def historical_p0_smoke(manifest):
    rows = lines(P0_SMOKE)
    if [x.get('id') for x in rows] != SMOKE_IDS:
        raise ValueError('Historical P0 smoke lacks three ordered positions')
    inputs, policy = native.load_inputs(), native.load_policy()
    for index, row in enumerate(rows):
        payload = native.payload(inputs[index]['feedback'], policy, 'P0')
        planned = manifest['requests']['P0'][index]
        raw = row.get('raw_response')
        if (row.get('status') != 'ok' or row.get('surface') != 'typesafe' or
                row.get('mode') != 'official' or row.get('requested_model') != PRICE_MODEL or
                row.get('returned_model') != PRICE_MODEL or row.get('retry_policy') != 'none' or
                row.get('request_sha256') != digest(json.dumps(payload, sort_keys=True)) or
                row.get('request_sha256') != planned['request_sha256'] or
                row.get('reserved_cost_usd') != planned['reserve_usd'] or
                row.get('cost_unknown') is not False or not isinstance(raw, dict) or
                parse_response(raw, PRICE_MODEL) != row.get('prediction') or
                row.get('estimated_usage_cost_usd') != str(usage_cost(raw))):
            raise ValueError('Historical P0 smoke differs from frozen request or response')
    return rows


def validate_wire_variants(manifest):
    inputs, policy = native.load_inputs(), native.load_policy()
    for index, row in enumerate(inputs):
        payloads = {condition: native.payload(row['feedback'], policy, condition)
                    for condition in ('P0', 'P1', 'P2')}
        baseline = payloads['P0']
        for condition, payload in payloads.items():
            expected = manifest['requests'][condition][index]
            if expected['request_sha256'] != digest(json.dumps(payload, sort_keys=True)) or (
                    expected['reserve_usd'] != str(native.reserve_cost(payload))):
                raise ValueError('Frozen Jev request or reservation differs: ' + condition + '/' + row['id'])
            if condition == 'P0':
                continue
            if {key: value for key, value in payload.items() if key != 'questions'} != (
                    {key: value for key, value in baseline.items() if key != 'questions'}):
                raise ValueError('Native Jev non-question wire fields differ')
            if list(payload['questions']) != list(baseline['questions']):
                raise ValueError('Native Jev question order differs')
            for key in KEYS:
                before = baseline['questions'][key]
                after = payload['questions'][key]
                addition = native.P1 + (native.P2[key] if condition == 'P2' else '')
                if ({k: v for k, v in before.items() if k != 'instructions'} !=
                        {k: v for k, v in after.items() if k != 'instructions'} or
                        after['instructions'] != before['instructions'] + addition):
                    raise ValueError('Native Jev changed a field beyond question instructions')


def ledger_snapshot(attempts):
    events = lines(native.LEDGER)
    budgets = [e for e in events if e.get('event') == 'budget']
    if len(budgets) != 1 or Decimal(budgets[0]['cap_usd']) != CAP:
        raise ValueError('Existing TypeSafe ledger cap differs')
    reserved, settled = {}, {}
    for event in events:
        kind = event.get('event')
        if kind == 'reserve':
            attempt = event['attempt_id']
            if attempt in reserved:
                raise ValueError('Duplicate TypeSafe reservation')
            amount = Decimal(event['usd'])
            if not amount.is_finite() or amount <= 0:
                raise ValueError('Invalid TypeSafe reservation')
            reserved[attempt] = amount
        elif kind == 'settle':
            attempt = event['attempt_id']
            amount = Decimal(event['usd'])
            if attempt not in reserved or attempt in settled or not amount.is_finite() or amount < 0:
                raise ValueError('Invalid TypeSafe settlement')
            settled[attempt] = amount
        elif kind != 'budget':
            raise ValueError('Unexpected TypeSafe ledger event')
    for row in attempts:
        attempt = row['budget_attempt_id']
        if attempt not in reserved or reserved[attempt] != Decimal(row['reserved_cost_usd']):
            raise ValueError('Historical Jev attempt lacks exact reservation')
        if row.get('cost_unknown') is True:
            if attempt in settled:
                raise ValueError('Unknown Jev attempt was silently settled')
        elif attempt not in settled or settled[attempt] != Decimal(row['estimated_usage_cost_usd']):
            raise ValueError('Known Jev attempt settlement differs')
    pending = sorted(set(reserved) - set(settled))
    accounted = sum((settled.get(key, reserved[key]) for key in reserved), Decimal(0))
    if accounted > CAP:
        raise ValueError('Existing TypeSafe cap already exceeded')
    return {'cap_usd': str(CAP), 'accounted_usd': str(accounted),
            'remaining_usd': str(CAP - accounted), 'pending_attempt_ids': pending,
            'pending_upper_usd': str(sum((reserved[key] for key in pending), Decimal(0))),
            'ledger': bind(native.LEDGER)}


def plan():
    manifest_path = BASE / 'input-only-manifest.json'
    manifest, manifest_sha = native.read_frozen_manifest(manifest_path)
    validate_wire_variants(manifest)
    first_p0, all_p0 = historical_p0(manifest)
    p0_smoke = historical_p0_smoke(manifest)
    variants = historical_variants(manifest, manifest_sha)
    all_historical = p0_smoke + all_p0 + [row for pair in variants.values() for phase in pair for row in phase]
    budget = ledger_snapshot(all_historical)
    if len(budget['pending_attempt_ids']) != 1 or (
            budget['pending_attempt_ids'][0] != first_p0[45]['budget_attempt_id'] or
            Decimal(budget['pending_upper_usd']) != Decimal(first_p0[45]['reserved_cost_usd'])):
        raise ValueError('Historical DEV-046 is not the sole pending upper bound')
    by_condition = {}
    for condition in ('P0', 'P1', 'P2'):
        requests = manifest['requests'][condition]
        smoke = requests[:3]
        upper = sum((Decimal(x['reserve_usd']) for x in smoke + requests), Decimal(0))
        by_condition[condition] = {'smoke_ids': SMOKE_IDS, 'development_ids': IDS,
                                   'requests': requests, 'smoke_plus_development_upper_usd': str(upper)}
    per_pass = sum((Decimal(by_condition[c]['smoke_plus_development_upper_usd']) for c in by_condition), Decimal(0))
    two_pass = 2 * per_pass
    fresh_three = 3 * per_pass
    accounted = Decimal(budget['accounted_usd'])
    if accounted + two_pass > CAP:
        raise ValueError('Original-plus-two Jev plan exceeds existing $1 ledger cap')
    sources = [bind(x) for x in (manifest_path, P0_SMOKE, P0_PREFIX, P0_CONTINUATION,
                                native.BASELINE, native.INPUTS, native.POLICY,
                                BASE / 'P1-smoke.jsonl', BASE / 'P1-smoke.attempts.jsonl',
                                BASE / 'P1-development.jsonl', BASE / 'P1-development.attempts.jsonl',
                                BASE / 'P1-smoke-inspection.json',
                                BASE / 'P2-smoke.jsonl', BASE / 'P2-smoke.attempts.jsonl',
                                BASE / 'P2-development.jsonl', BASE / 'P2-development.attempts.jsonl',
                                BASE / 'P2-smoke-inspection.json',
                                ROOT / 'scripts/jev_benchmark.py',
                                ROOT / 'scripts/jev_native_prompt_variants_v1.py',
                                ROOT / 'scripts/typesafe_repeat_study.py')]
    return {'schema': 'typesafe-jev-repeat-offline-admission-v1', 'dispatch_authorized': False,
            'configuration_id': 'typesafe-jev113-v2', 'model': PRICE_MODEL,
            'endpoint': 'https://api.typesafe.ai/v1/systemone',
            'request_unit': 'one feedback with four parallel Choice questions',
            'historical_selection': {'P0': {'policy': 'first_attempt_per_id',
                                            'status_counts': dict(sorted(Counter(x['status'] for x in first_p0).items())),
                                            'failed_id': 'DEV-046',
                                            'failed_attempt_id': first_p0[45]['budget_attempt_id'],
                                            'later_manual_retry_id': 'DEV-046',
                                            'later_manual_retry_attempt_id': all_p0[46]['budget_attempt_id'],
                                            'retry_excluded_from_first_pass': True},
                                     'P1': {'policy': 'saved_complete_no_retry', 'status_counts': {'ok': 59, 'invalid_output': 1}},
                                     'P2': {'policy': 'saved_complete_no_retry', 'status_counts': {'ok': 59, 'invalid_output': 1}}},
            'future_passes': [{'repeat': repeat, 'condition_order': list(order),
                               'conditions': {condition: by_condition[condition] for condition in order}}
                              for repeat, order in ORDERS.items()],
            'controls': {'question_version': QUESTION_VERSION, 'question_order': list(KEYS),
                         'same_wire_payload_per_record_condition': True,
                         'native_choice_instructions_only': True,
                         'no_automatic_retry': True, 'reference_labels_read': False,
                         'continuation_policy': 'After a stop, explicit review may admit never-sent IDs only; the failed first attempt remains in the 60-position pass.',
                         'smoke_count_per_condition': 3, 'development_count_per_condition': 60,
                         'invalid_outputs_preserved': True, 'service_errors_preserved': True,
                         'provider_inference_seconds': None},
            'budget_snapshot': budget,
            'upper_bounds_usd': {'one_pass': str(per_pass), 'two_more_passes': str(two_pass),
                                 'accounted_plus_two': str(accounted + two_pass),
                                 'headroom_after_two': str(CAP - accounted - two_pass),
                                 'fresh_three_passes': str(fresh_three),
                                 'fresh_three_fits': accounted + fresh_three <= CAP},
            'source_bindings': sources,
            'limits': ['Offline admission snapshot only; recompute after any TypeSafe ledger or source change.',
                       'P0 first pass selects the first attempt at every ID; the manual DEV-046 success is separate.',
                       'The two future passes still require an independently reviewed no-retry runner, root admission, smoke inspection, and live model/price checks.',
                       'Reservation is a client upper bound, not a provider spending guarantee or invoice.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Create an offline JSON admission draft at a new path')
    args = parser.parse_args()
    value = plan()
    data = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        with args.output.open('x') as out:
            out.write(data)
        print(args.output)
    else:
        print(json.dumps({'historical_selection': value['historical_selection'],
                          'budget_snapshot': value['budget_snapshot'],
                          'upper_bounds_usd': value['upper_bounds_usd']}, indent=2))


if __name__ == '__main__':
    main()
