#!/usr/bin/env python3
"""Offline, input-only fresh-three admission for DeepSeek V4.1 Flash high.

This prepares evidence-bound requests. It never loads a key, allocates budget,
or sends a model request. A separate reviewed execution controller is required.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows

CONFIG = 'openrouter-paid-deepseek-v41-flash-high'
SERIES = 'deepseek-high-fresh-matched3-v1'
MODEL = 'deepseek/deepseek-v4.1-flash'
PROVIDER = 'open-inference/fp4'
PROVIDER_NAME = 'OpenInference'
QUANTIZATION = 'fp4'
EFFORT = 'high'
CONTEXT = 1048576
MAX_TOKENS = 4096
TIMEOUT = 300.0
OLD_PROMPT = Decimal('0.0000001')
CURRENT_PROMPT = Decimal('0.00000003')
COMPLETION = Decimal('0.0000005')
RESERVE = Decimal('0.1069056')
PROPOSED_CHILD = Decimal('0.90')
BASE = ROOT / 'results/repeatability-v1' / SERIES
HOSTED = 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
AUDIT = ('results/prompt-comparison-v1-2026-09-24/paired-reports/'
         'hosted-remaining-audit-v1/' + CONFIG + '.json')
ROUTE_AUDIT = 'results/repeatability-v1/deepseek-low-fresh3-v2/lower-price-endpoint-audit-v1.json'
INPUTS = 'data/pilot/inputs.jsonl'
PREP = 'results/hosted-prompt-preparation-2026-09-24/' + CONFIG
CONDITIONS = ('P0', 'P1', 'P2')
ORDERS = {'fresh1': ('P0', 'P1', 'P2'),
          'fresh2': ('P2', 'P0', 'P1'),
          'fresh3': ('P1', 'P2', 'P0')}
SMOKES = {
    'P0': 'results/openrouter-parallel-deepseek-flash-high-2026-09-23/smoke.jsonl',
    'P1': 'results/prompt-comparison-v1-2026-09-24/runs/' + CONFIG + '/P1/smoke-after-launch-failure.jsonl',
    'P2': 'results/prompt-comparison-v1-2026-09-24/runs/' + CONFIG + '/P2/smoke.jsonl',
}
EXPECTED_STATUSES = {
    'P0': {'ok': 56, 'invalid_output': 4},
    'P1': {'ok': 56, 'invalid_output': 2, 'prompt_admission_failure': 1, 'service_error': 1},
    'P2': {'ok': 58, 'invalid_output': 1, 'service_error': 1},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def rows(relative):
    return [json.loads(line) for line in (ROOT / relative).read_text().splitlines() if line.strip()]


def sources():
    audit = json.loads((ROOT / AUDIT).read_text())
    hosted = json.loads((ROOT / HOSTED).read_text())
    matches = [x for x in hosted['configurations'] if x.get('id') == CONFIG]
    if audit.get('configuration_id') != CONFIG or len(matches) != 1:
        raise ValueError('Missing exact historical high-effort configuration/audit')
    config = matches[0]
    controls = config['controls']['adapter_controls']
    rc = controls['request_controls']
    expected_provider = {'only': [PROVIDER], 'allow_fallbacks': False,
                         'require_parameters': True,
                         'max_price': {'prompt': 0.1, 'completion': 0.5,
                                       'request': 0, 'image': 0}}
    if ((controls['requested_model'], controls['provider_tag'],
          controls['provider_name'], controls['quantization'],
          controls['reasoning_effort'], controls['workflow']) !=
        (MODEL, PROVIDER, PROVIDER_NAME, QUANTIZATION, EFFORT, 'single_record') or
        config['controller_timeout_seconds'] != TIMEOUT or
        config['continue_on_invalid_output'] is not True or
        rc.get('model') != MODEL or rc.get('temperature') != 0 or
        rc.get('max_tokens') != MAX_TOKENS or rc.get('stream') is not False or
        rc.get('reasoning') != {'enabled': True, 'effort': EFFORT} or
        rc.get('provider') != expected_provider or
        rc.get('response_format', {}).get('type') != 'json_schema' or
        rc['response_format']['json_schema'].get('strict') is not True or
        rc['response_format']['json_schema']['schema'] !=
          json.loads((ROOT / 'schemas/judgments.schema.json').read_text())):
        raise ValueError('Historical high-effort request/parser/failure controls differ')
    route = json.loads((ROOT / ROUTE_AUDIT).read_text())
    endpoint = route.get('selected_endpoint', {})
    if (route.get('model_id') != MODEL or route.get('provider_tag') != PROVIDER or
        Decimal(str(route.get('admitted_prompt_price_usd_per_token'))) != CURRENT_PROMPT or
        endpoint.get('status') != 0 or endpoint.get('tag') != PROVIDER or
        endpoint.get('model_id') != MODEL or
        Decimal(str(endpoint.get('pricing', {}).get('prompt'))) != CURRENT_PROMPT or
        Decimal(str(endpoint.get('pricing', {}).get('completion'))) != COMPLETION or
        'high' not in route.get('model_reasoning', {}).get('supported_efforts', [])):
        raise ValueError('Saved public route observation lacks exact high support or current price')
    return audit, config, rc


def input_rows():
    result = read_rows(ROOT / INPUTS)
    if (len(result) != 60 or
        [x.get('id') for x in result] != [f'DEV-{i:03d}' for i in range(1, 61)] or
        any(set(x) != {'id', 'feedback'} for x in result)):
        raise ValueError('Frozen input-only 60-record order differs')
    return result


def instruction_file(condition):
    return PREP + ('/baseline.txt' if condition == 'P0'
                   else '/' + condition + '/instruction.txt')


def historical_rows(audit, condition):
    condition_audit = audit['conditions'][condition]
    found = {}
    for item in condition_audit['source_bindings']:
        relative = item['file']
        if sha(ROOT / relative) != item['sha256']:
            raise ValueError('Historical source hash changed: ' + relative)
        for row in rows(relative):
            record_id = row.get('id')
            if record_id in found:
                raise ValueError('Duplicate historical attempt: ' + str(record_id))
            found[record_id] = row
    for item in condition_audit.get('lifecycle_bindings', []):
        if sha(ROOT / item['file']) != item['sha256']:
            raise ValueError('Historical lifecycle source changed: ' + item['file'])
    if set(found) != {f'DEV-{i:03d}' for i in range(1, 61)}:
        raise ValueError('Historical attempts do not cover exactly 60 positions')
    if dict(Counter(row.get('status') for row in found.values())) != EXPECTED_STATUSES[condition]:
        raise ValueError('Historical invalid/failure positions changed')
    return found


def condition_data(audit, controls, inputs, condition):
    historical = historical_rows(audit, condition)
    instruction = (ROOT / instruction_file(condition)).read_text()
    requests = []
    for position, item in enumerate(inputs, 1):
        rid = item['id']
        old = historical[rid]
        payload = old.get('request')
        if (not isinstance(payload, dict) or
            set(payload) != set(controls) | {'messages'} or
            {key: payload[key] for key in controls} != controls or
            payload['messages'] != [
                {'role': 'system', 'content': instruction},
                {'role': 'user', 'content': json.dumps({'feedback': item['feedback']})},
            ]):
            raise ValueError('Saved request bytes/controls/input differ: ' + condition + '/' + rid)
        request_hash = digest(json.dumps(payload, sort_keys=True))
        if (old.get('request_sha256') not in (None, request_hash) or
            old.get('reference_labels_read') is not False or
            old.get('requested_model') != MODEL or
            old.get('reasoning_effort') != EFFORT):
            raise ValueError('Historical request hash, route or label boundary differs: ' + condition + '/' + rid)
        endpoint = old.get('provider_endpoint') or {}
        pricing = endpoint.get('pricing') or {}
        if ((endpoint.get('tag'), endpoint.get('provider_name'),
             endpoint.get('quantization'), endpoint.get('status'),
             endpoint.get('context_length')) !=
            (PROVIDER, PROVIDER_NAME, QUANTIZATION, 0, CONTEXT) or
            Decimal(str(pricing.get('prompt'))) != OLD_PROMPT or
            Decimal(str(pricing.get('completion'))) != COMPLETION):
            raise ValueError('Historical endpoint or price differs: ' + condition + '/' + rid)
        requests.append({'position': position, 'record_id': rid, 'payload': payload,
                         'request_sha256': request_hash,
                         'saved_request_hash_present': old.get('request_sha256') is not None,
                         'input_sha256': digest(item['feedback']),
                         'instruction_sha256': digest(instruction),
                         'historical_outcome_excluded': old['status']})
    descriptors = audit['conditions'][condition]
    return {'instruction': bind(instruction_file(condition)),
            'historical_attempts': descriptors['source_bindings'],
            'historical_lifecycle': descriptors.get('lifecycle_bindings', []),
            'smoke': requests[:3], 'development': requests}


def estimate(audit, conditions=None):
    if conditions is None:
        _, _, controls = sources()
        inputs = input_rows()
        conditions = {condition: condition_data(audit, controls, inputs, condition)
                      for condition in CONDITIONS}
    known = Decimal(0)
    unknown = Decimal(0)
    count = 0
    for condition in CONDITIONS:
        observed = list(historical_rows(audit, condition).values()) + rows(SMOKES[condition])
        smoke = rows(SMOKES[condition])
        if len(smoke) != 3 or [x.get('id') for x in smoke] != [f'DEV-{i:03d}' for i in range(1, 4)]:
            raise ValueError('Historical smoke does not have exact first three IDs')
        for row, expected in zip(smoke, conditions[condition]['smoke']):
            endpoint = row.get('provider_endpoint') or {}
            pricing = endpoint.get('pricing') or {}
            if (row.get('request') != expected['payload'] or
                row.get('request_sha256') != expected['request_sha256'] or
                row.get('reference_labels_read') is not False or
                row.get('requested_model') != MODEL or row.get('reasoning_effort') != EFFORT or
                (endpoint.get('tag'), endpoint.get('provider_name'),
                 endpoint.get('quantization'), endpoint.get('status'),
                 endpoint.get('context_length')) !=
                (PROVIDER, PROVIDER_NAME, QUANTIZATION, 0, CONTEXT) or
                Decimal(str(pricing.get('prompt'))) != OLD_PROMPT or
                Decimal(str(pricing.get('completion'))) != COMPLETION):
                raise ValueError('Historical smoke request or route differs: ' + condition)
        count += len(observed)
        for row in observed:
            cost = row.get('observed_cost_usd')
            if cost is not None:
                known += Decimal(str(cost))
            if row.get('cost_unknown') is True:
                if cost is not None or Decimal(str(row.get('reserved_cost_usd'))) != RESERVE:
                    raise ValueError('Unknown historical cost lacks exact reserve bound')
                unknown += RESERVE
            elif cost is None:
                raise ValueError('Historical missing charge is not marked unknown')
    proxy = known * 3
    sensitivity = unknown * 3
    return {'historical_attempt_rows_in_proxy': count,
            'historical_one_pass_known_cost_usd': str(known),
            'historical_one_pass_unknown_reserve_bound_usd': str(unknown),
            'three_pass_known_charge_proxy_usd': str(proxy),
            'three_pass_unknown_bound_sensitivity_usd': str(sensitivity),
            'three_pass_known_plus_unknown_sensitivity_usd': str(proxy + sensitivity),
            'proposed_child_budget_usd': str(PROPOSED_CHILD),
            'proposed_margin_over_proxy_plus_sensitivity_usd': str(PROPOSED_CHILD - proxy - sensitivity),
            'per_request_maximum_reserve_usd': str(RESERVE),
            'calls_per_full_series': 567,
            'all_requests_max_reserve_stress_usd': str(RESERVE * 567),
            'uncertainty': 'Known historical charges are a proxy, not a bill forecast. Unknown cost retains the full reserved upper bound separately. Each future request needs its own reserve before dispatch.'}


def plan_data(fresh_pass):
    if fresh_pass not in ORDERS:
        raise ValueError('Unknown fresh pass')
    audit, _, controls = sources()
    inputs = input_rows()
    conditions = {condition: condition_data(audit, controls, inputs, condition)
                  for condition in CONDITIONS}
    evidence = [HOSTED, AUDIT, ROUTE_AUDIT, INPUTS, 'schemas/judgments.schema.json',
                'docs/HOSTED_REMAINING_PAIR_AUDIT_2026-09-28.md',
                'docs/REPEATABILITY_PLAN.md',
                'scripts/deepseek_high_fresh_repeat_study.py',
                'tests/test_deepseek_high_fresh_repeat_study.py']
    for condition in CONDITIONS:
        evidence.append(instruction_file(condition))
        evidence.append(SMOKES[condition])
        evidence.extend(item['file'] for item in conditions[condition]['historical_attempts'])
        evidence.extend(item['file'] for item in conditions[condition]['historical_lifecycle'])
    return {'schema': 'deepseek-high-fresh-matched-three-plan-v1',
            'series_id': SERIES, 'configuration_id': CONFIG, 'fresh_pass': fresh_pass,
            'condition_order': list(ORDERS[fresh_pass]),
            'model': MODEL, 'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
            'quantization': QUANTIZATION, 'reasoning_effort': EFFORT,
            'temperature': 0, 'max_tokens': MAX_TOKENS, 'stream': False,
            'context_reservation_tokens': CONTEXT, 'timeout_seconds': TIMEOUT,
            'workflow': 'single_record_fresh_context',
            'continue_on_invalid_output': True,
            'retry_policy': 'No retries or replays. Preserve every invalid, failed, or unknown result.',
            'reference_labels_read': False,
            'historical_status': 'Descriptive only: interrupted continuation schedule. No old attempt counts as a fresh pass.',
            'historical_endpoint_prompt_price_usd_per_token': format(OLD_PROMPT, 'f'),
            'current_saved_route_prompt_price_usd_per_token': format(CURRENT_PROMPT, 'f'),
            'current_route_observation_only': True,
            'execution_status': 'offline_prepared_no_inference_no_allocation',
            'aggregate_openrouter_cap_usd': '10',
            'proposed_child_budget_usd': str(PROPOSED_CHILD),
            'budget_estimate': estimate(audit, conditions),
            'historical_development_statuses': EXPECTED_STATUSES,
            'conditions': conditions,
            'source_bindings': [bind(p) for p in dict.fromkeys(evidence)],
            'dispatch_gate': 'Independent execution-controller review, fresh exact endpoint/status/price/high-reasoning check, funded child partition, per-stage root receipts and inspected three-record smokes required before any development call.'}


def prepare():
    for name in ORDERS:
        folder = BASE / name
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'manifest.json'
        with target.open('x') as stream:
            json.dump(plan_data(name), stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        print(name, sha(target), target)


def verify(fresh_pass, expected_sha):
    target = BASE / fresh_pass / 'manifest.json'
    if sha(target) != expected_sha:
        raise ValueError('Manifest SHA-256 mismatch')
    manifest = json.loads(target.read_text())
    for binding in manifest['source_bindings']:
        if bind(binding['path']) != binding:
            raise ValueError('Bound source changed: ' + binding['path'])
    if manifest != plan_data(fresh_pass):
        raise ValueError('Manifest differs from exact source reconstruction')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'estimate'))
    parser.add_argument('--fresh-pass', choices=tuple(ORDERS))
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'estimate':
        print(json.dumps(estimate(sources()[0]), indent=2))
    else:
        if not args.fresh_pass or not args.sha256:
            parser.error('verify needs --fresh-pass and --sha256')
        verify(args.fresh_pass, args.sha256)
        print(json.dumps({'verified': True, 'fresh_pass': args.fresh_pass,
                          'manifest_sha256': args.sha256}))


if __name__ == '__main__':
    main()
