#!/usr/bin/env python3
"""Offline Qwen3.8 27B plans under the amended $12.38 budget.

No provider API or budget ledger is opened here. A separate reviewed execution
controller and live route check are required before any request is sent.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows

MODEL = 'qwen/qwen3.8-27b'
PROVIDER = 'deepinfra/bf16'
PROVIDER_NAME = 'DeepInfra'
QUANTIZATION = 'bf16'
INPUT_PRICE = Decimal('0.15')
OUTPUT_PRICE = Decimal('1.875')
CONTEXT = 262144
MAX_TOKENS = 4096
TIMEOUT = 300.0
SERIES = 'qwen27-fresh-matched3-v2'
ORIGINAL_SERIES = 'qwen27-fresh-matched3-v1'
AUDIT_DIR = 'results/prompt-comparison-v1-2026-09-24/paired-reports/hosted-remaining-audit-v1'
HOSTED = 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
INPUTS = 'data/pilot/inputs.jsonl'
PREP_DIR = 'results/hosted-prompt-preparation-2026-09-24'
ROUNDS = ('fresh1', 'fresh2', 'fresh3')
ORDERS = {
    'fresh1': ['P0', 'P1', 'P2'],
    'fresh2': ['P1', 'P2', 'P0'],
    'fresh3': ['P2', 'P0', 'P1'],
}
CONDITIONS = ('P0', 'P1', 'P2')
CONFIGS = {
    'openrouter-paid-qwen3.8-27b-medium': {
        'effort': 'medium', 'historical_continue_on_invalid': True,
        'proposed_child_budget': Decimal('1.00'),
        'smokes': {
            'P0': 'results/openrouter-partition-qwen27-medium-2026-09-23/smoke.jsonl',
            'P1': 'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen3.8-27b-medium/P1/smoke.jsonl',
            'P2': 'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen3.8-27b-medium/P2/smoke-after-launch-failure.jsonl',
        },
    },
    'openrouter-paid-qwen3.8-27b-xhigh': {
        'effort': 'xhigh', 'historical_continue_on_invalid': False,
        'proposed_child_budget': Decimal('0.80'),
        'smokes': {
            'P0': 'results/openrouter-partition-qwen27-xhigh-2026-09-23/smoke.jsonl',
            'P1': 'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen3.8-27b-xhigh/P1/smoke.jsonl',
            'P2': 'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-qwen3.8-27b-xhigh/P2/smoke.jsonl',
        },
    },
}
BASE = ROOT / 'results/repeatability-v1' / SERIES
ORIGINAL_BASE = ROOT / 'results/repeatability-v1' / ORIGINAL_SERIES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_jsonl(relative):
    path = ROOT / relative
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit_path(config_id):
    return f'{AUDIT_DIR}/{config_id}.json'


def input_feedback():
    rows = read_rows(ROOT / INPUTS)
    if len(rows) != 60 or any(set(row) != {'id', 'feedback'} for row in rows):
        raise ValueError('Input roster must contain only the 60 id/feedback rows')
    if [row['id'] for row in rows] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Input ID order differs from the frozen 60-record order')
    return {row['id']: row['feedback'] for row in rows}


def historical_data(config_id):
    if config_id not in CONFIGS:
        raise ValueError('Unsupported exact Qwen27 configuration')
    spec = CONFIGS[config_id]
    audit_file = audit_path(config_id)
    audit = json.loads((ROOT / audit_file).read_text())
    hosted = json.loads((ROOT / HOSTED).read_text())
    configurations = [c for c in hosted['configurations'] if c.get('id') == config_id]
    if audit.get('configuration_id') != config_id or len(configurations) != 1:
        raise ValueError('Missing or duplicate configuration-level historical audit')
    cfg = configurations[0]
    controls = cfg['controls']['adapter_controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
            controls['quantization'], controls['reasoning_effort'], controls['workflow']) != (
            MODEL, PROVIDER, PROVIDER_NAME, QUANTIZATION, spec['effort'], 'single_record'):
        raise ValueError('Historical route, effort, or request-unit controls differ')
    rc = controls['request_controls']
    if (rc.get('model'), rc.get('temperature'), rc.get('max_tokens'), rc.get('stream'),
            rc.get('reasoning')) != (MODEL, 0, MAX_TOKENS, False,
                                     {'enabled': True, 'effort': spec['effort']}):
        raise ValueError('Historical model/sampling/output/reasoning controls differ')
    if rc.get('provider') != {
        'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
        'max_price': {'prompt': float(INPUT_PRICE), 'completion': float(OUTPUT_PRICE), 'request': 0, 'image': 0},
    }:
        raise ValueError('Historical provider and price guard differ')
    response = rc.get('response_format', {})
    if response.get('type') != 'json_schema' or response.get('json_schema', {}).get('strict') is not True:
        raise ValueError('Historical output parser is not the expected strict schema')
    if (cfg.get('continue_on_invalid_output') is not spec['historical_continue_on_invalid'] or
            cfg.get('controller_timeout_seconds') != TIMEOUT):
        raise ValueError('Historical failure policy or timeout differs')
    return audit, cfg


def source_rows(audit, condition):
    descriptors = audit['conditions'][condition]['source_bindings']
    rows = {}
    for descriptor in descriptors:
        path = ROOT / descriptor['file']
        if sha(path) != descriptor['sha256']:
            raise ValueError('Historical row source hash changed: ' + descriptor['file'])
        for row in read_jsonl(descriptor['file']):
            record_id = row.get('id')
            if record_id in rows:
                raise ValueError('Duplicate historical source record: ' + str(record_id))
            rows[record_id] = row
    journals = {}
    for descriptor in audit['conditions'][condition].get('lifecycle_bindings', []):
        if descriptor['file'].endswith('attempts.jsonl'):
            if sha(ROOT / descriptor['file']) != descriptor['sha256']:
                raise ValueError('Historical attempt journal hash changed: ' + descriptor['file'])
            for event in read_jsonl(descriptor['file']):
                if event.get('event') == 'request_started' and event.get('attempt_id'):
                    previous = journals.get(event['attempt_id'])
                    if previous is not None and previous != event.get('request_sha256'):
                        raise ValueError('Conflicting request journal hashes for one attempt')
                    journals[event['attempt_id']] = event.get('request_sha256')
    return descriptors, rows, journals


def validate_historical_request(row, feedback, condition, record_id, expected_instruction=None, journal_hashes=None):
    payload = row.get('request')
    if not isinstance(payload, dict):
        raise ValueError('Historical request body proof missing for ' + condition + '/' + record_id)
    expected_fields = {'model', 'temperature', 'max_tokens', 'stream', 'provider',
                       'response_format', 'reasoning', 'messages'}
    if set(payload) != expected_fields:
        raise ValueError('Historical request body fields differ for ' + condition + '/' + record_id)
    expected_messages = [
        {'role': 'system', 'content': expected_instruction},
        {'role': 'user', 'content': json.dumps({'feedback': feedback})},
    ]
    if expected_instruction is None or payload['messages'] != expected_messages:
        raise ValueError('Historical request prompt or input mismatch for ' + condition + '/' + record_id)
    expected_provider = {
        'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
        'max_price': {'prompt': float(INPUT_PRICE), 'completion': float(OUTPUT_PRICE), 'request': 0, 'image': 0},
    }
    if (payload.get('model'), payload.get('temperature'), payload.get('max_tokens'),
            payload.get('stream'), payload.get('provider'), payload.get('reasoning')) != (
            MODEL, 0, MAX_TOKENS, False, expected_provider,
            {'enabled': True, 'effort': CONFIGS[row.get('_configuration_id', '')]['effort']}):
        raise ValueError('Historical request controls mismatch for ' + condition + '/' + record_id)
    fmt = payload['response_format']
    if fmt.get('type') != 'json_schema' or fmt.get('json_schema', {}).get('strict') is not True:
        raise ValueError('Historical strict output schema mismatch for ' + condition + '/' + record_id)
    actual_digest = digest(json.dumps(payload, sort_keys=True))
    saved_digest = row.get('request_sha256')
    if not saved_digest and journal_hashes:
        saved_digest = journal_hashes.get(row.get('attempt_id'))
    if saved_digest != actual_digest:
        raise ValueError('Historical request digest proof missing or mismatched for ' + condition + '/' + record_id)
    if row.get('reference_labels_read') is not False:
        raise ValueError('Historical label-isolation marker missing for ' + condition + '/' + record_id)
    endpoint = row.get('provider_endpoint') or {}
    if (row.get('requested_model'), row.get('reasoning_effort'), row.get('quantization'),
            endpoint.get('tag'), endpoint.get('provider_name'), endpoint.get('quantization'),
            endpoint.get('status'), endpoint.get('context_length')) != (
            MODEL, CONFIGS[row['_configuration_id']]['effort'], QUANTIZATION,
            PROVIDER, PROVIDER_NAME, QUANTIZATION, 0, CONTEXT):
        raise ValueError('Historical exact endpoint identity/status mismatch for ' + condition + '/' + record_id)
    pricing = endpoint.get('pricing') or {}
    if (Decimal(str(pricing.get('prompt'))) != INPUT_PRICE / Decimal(1_000_000) or
            Decimal(str(pricing.get('completion'))) != OUTPUT_PRICE / Decimal(1_000_000)):
        raise ValueError('Historical endpoint price differs for ' + condition + '/' + record_id)
    return actual_digest


def build_condition(config_id, audit, feedback, condition):
    spec = CONFIGS[config_id]
    descriptors, rows, journals = source_rows(audit, condition)
    if set(rows) != set(feedback) or len(rows) != 60:
        raise ValueError('Historical source does not prove all 60 exact IDs for ' + condition)
    prompt_file = (f'{PREP_DIR}/{config_id}/baseline.txt' if condition == 'P0'
                   else f'{PREP_DIR}/{config_id}/{condition}/instruction.txt')
    instruction = (ROOT / prompt_file).read_text()
    requests = []
    for position, record_id in enumerate(feedback, 1):
        row = dict(rows[record_id], _configuration_id=config_id)
        request_hash = validate_historical_request(
            row, feedback[record_id], condition, record_id,
            expected_instruction=instruction, journal_hashes=journals)
        requests.append({
            'position': position,
            'record_id': record_id,
            'payload': row['request'],
            'request_sha256': request_hash,
            'input_sha256': digest(feedback[record_id]),
            'instruction_sha256': digest(instruction),
            'historical_outcome_excluded': row.get('status'),
        })
    return {'instruction': bind(prompt_file), 'historical_attempts': descriptors,
            'smoke': requests[:3], 'development': requests}


def estimate(config_id, audit=None):
    if config_id not in CONFIGS:
        raise ValueError('Unsupported exact Qwen27 configuration')
    if audit is None:
        audit, _ = historical_data(config_id)
    known = Decimal(0)
    unknown_bound = Decimal(0)
    observed_rows = 0
    for condition in CONDITIONS:
        _, rows, _ = source_rows(audit, condition)
        observed = list(rows.values())
        smoke_rows = read_jsonl(CONFIGS[config_id]['smokes'][condition])
        if len(smoke_rows) != 3:
            raise ValueError('Historical smoke evidence must contain exactly three rows: ' + condition)
        observed.extend(smoke_rows)
        observed_rows += len(observed)
        for row in observed:
            if row.get('observed_cost_usd') is not None:
                known += Decimal(str(row['observed_cost_usd']))
            if row.get('cost_unknown'):
                unknown_bound += Decimal(str(row.get('reserved_cost_usd') or '0'))
    reserve = (Decimal(CONTEXT) * INPUT_PRICE + Decimal(MAX_TOKENS) * OUTPUT_PRICE) / Decimal(1_000_000)
    known_three = known * 3
    unknown_three = unknown_bound * 3
    child = CONFIGS[config_id]['proposed_child_budget']
    full_calls = 3 * 3 * (60 + 3)
    return {
        'historical_one_pass_known_cost_usd': str(known),
        'historical_one_pass_unknown_bound_usd': str(unknown_bound),
        'three_pass_known_charge_proxy_usd': str(known_three),
        'three_pass_unknown_bound_sensitivity_usd': str(unknown_three),
        'three_pass_known_plus_unknown_sensitivity_usd': str(known_three + unknown_three),
        'proposed_child_budget_usd': str(child),
        'margin_over_known_plus_unknown_sensitivity_usd': str(child - known_three - unknown_three),
        'per_request_maximum_reserve_usd': format(reserve, '.9f'),
        'calls_per_full_series': full_calls,
        'all_requests_max_reserve_stress_usd': format(reserve * full_calls, '.9f'),
        'historical_rows_in_cost_proxy': observed_rows,
        'reservation_policy': 'Reserve one request at a time from the child partition; settle known charges, retain the full reserve for unknown charges, and stop before a request that does not fit. Full-context reservations for every call are a stress bound, not a spend forecast.',
        'uncertainty': 'Historical charge totals are a proxy, not a bill forecast. Unknown-charge bounds are reported separately and are not projected as ordinary known spend.',
    }


def plan_data(config_id, fresh_pass):
    if fresh_pass not in ORDERS:
        raise ValueError('Unknown fresh pass')
    audit, _ = historical_data(config_id)
    spec = CONFIGS[config_id]
    feedback = input_feedback()
    conditions = {condition: build_condition(config_id, audit, feedback, condition)
                  for condition in CONDITIONS}
    original_path = ORIGINAL_BASE / config_id / fresh_pass / 'manifest.json'
    original = json.loads(original_path.read_text())
    expected_series = ORIGINAL_SERIES + '-' + config_id.rsplit('-', 1)[-1]
    controls = {
        'configuration_id': config_id, 'condition_order': ORDERS[fresh_pass],
        'model': MODEL, 'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
        'quantization': QUANTIZATION, 'reasoning_effort': spec['effort'],
        'context_reservation_tokens': CONTEXT, 'max_tokens': MAX_TOKENS,
        'temperature': 0, 'stream': False, 'timeout_seconds': TIMEOUT,
        'workflow': 'single_record_fresh_context',
        'historical_continue_on_invalid_output': spec['historical_continue_on_invalid'],
        'continue_on_invalid_output': False,
        'smoke_count_per_condition': 3, 'development_count_per_condition': 60,
        'reference_labels_read': False,
        'proposed_child_budget_usd': str(spec['proposed_child_budget']),
    }
    if (original.get('series_id') != expected_series or
            original.get('conditions') != conditions or
            any(original.get(key) != value for key, value in controls.items())):
        raise ValueError('Distinct series must preserve original payloads and controls')
    original_binding = bind(str(original_path.relative_to(ROOT)))
    evidence = [audit_path(config_id), HOSTED, INPUTS,
                'schemas/judgments.schema.json', 'docs/REPEATABILITY_PLAN.md',
                'docs/HOSTED_REMAINING_PAIR_AUDIT_2026-09-28.md',
                'scripts/qwen27_fresh_repeat_study_v2.py',
                'scripts/qwen27_fresh_repeat_execution_v2.py',
                'tests/test_qwen27_budget1238.py',
                'scripts/openrouter_paid_benchmark.py', 'scripts/paid_budget_partitions_v3.py',
                'scripts/openrouter_budget_v3.py', 'scripts/prompt_admission.py',
                original_binding['path']]
    for condition in CONDITIONS:
        evidence.extend(item['file'] for item in audit['conditions'][condition]['source_bindings'])
        evidence.extend(item['file'] for item in audit['conditions'][condition].get('lifecycle_bindings', []))
        evidence.append(spec['smokes'][condition])
        evidence.append(conditions[condition]['instruction']['path'])
    return {
        'schema': 'qwen27-fresh-matched-three-plan-v1',
        'series_id': SERIES + '-' + config_id.rsplit('-', 1)[-1],
        'configuration_id': config_id,
        'fresh_pass': fresh_pass,
        'condition_order': ORDERS[fresh_pass],
        'model': MODEL, 'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
        'quantization': QUANTIZATION, 'reasoning_effort': spec['effort'],
        'context_reservation_tokens': CONTEXT, 'max_tokens': MAX_TOKENS,
        'temperature': 0, 'stream': False, 'timeout_seconds': TIMEOUT,
        'workflow': 'single_record_fresh_context',
        'retry_policy': 'No retries or replays. Preserve every failed, invalid, or unknown outcome.',
        'historical_continue_on_invalid_output': spec['historical_continue_on_invalid'],
        'continue_on_invalid_output': False,
        'timing_definition': 'elapsed_seconds is request-to-record duration: starts before durable request_started journal fsync; includes provider call, raw-response fsync, billing settlement and response audit; ends before attempt-row and request-finished journal fsync.',
        'smoke_count_per_condition': 3, 'development_count_per_condition': 60,
        'reference_labels_read': False,
        'seed_policy': 'No explicit seed in the historical request; requested and effective seed unavailable.',
        'historical_status': 'Descriptive historical series only. This fresh schedule is separate and does not replace prior invalid or failed outcomes or the v1 fresh plans.',
        'execution_status': 'offline_prepared_no_inference_no_allocation',
        'proposed_child_budget_usd': str(spec['proposed_child_budget']),
        'aggregate_cap_usd': '12.38',
        'budget_estimate': estimate(config_id, audit),
        'conditions': conditions,
        'original_plan_binding': original_binding,
        'source_bindings': [bind(path) for path in dict.fromkeys(evidence)],
        'dispatch_gate': 'Independent controller review, a live exact endpoint/status/pricing/control check, and an approved child partition are required before dispatch. Run one condition at a time; inspect each phase smoke raw output before its development requests.',
    }


def prepare():
    BASE.mkdir(parents=True, exist_ok=True)
    for config_id in CONFIGS:
        for fresh_pass in ROUNDS:
            folder = BASE / config_id / fresh_pass
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'manifest.json'
            value = json.dumps(plan_data(config_id, fresh_pass), indent=2, ensure_ascii=False) + '\n'
            with path.open('x') as output:
                output.write(value)
                output.flush()
                os.fsync(output.fileno())
            print(config_id, fresh_pass, sha(path), path)


def verify(config_id, fresh_pass, expected_sha):
    path = BASE / config_id / fresh_pass / 'manifest.json'
    if not path.is_file():
        raise ValueError('Manifest missing')
    if sha(path) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    manifest = json.loads(path.read_text())
    for source in manifest['source_bindings']:
        bound_path = (ROOT / source['path']).resolve()
        bound_path.relative_to(ROOT.resolve())
        if sha(bound_path) != source['sha256']:
            raise ValueError('Bound source changed: ' + source['path'])
    if manifest != plan_data(config_id, fresh_pass):
        raise ValueError('Frozen manifest differs from source reconstruction')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'estimate'))
    parser.add_argument('--configuration-id', choices=tuple(CONFIGS))
    parser.add_argument('--fresh-pass', choices=ROUNDS)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'estimate':
        if not args.configuration_id:
            parser.error('--configuration-id required for estimate')
        print(json.dumps(estimate(args.configuration_id), indent=2))
    else:
        if not args.configuration_id or not args.fresh_pass or not args.sha256:
            parser.error('verify requires --configuration-id, --fresh-pass, and --sha256')
        verify(args.configuration_id, args.fresh_pass, args.sha256)
        print(json.dumps({'verified': True, 'configuration_id': args.configuration_id,
                          'fresh_pass': args.fresh_pass, 'manifest_sha256': args.sha256}, indent=2))


if __name__ == '__main__':
    main()
