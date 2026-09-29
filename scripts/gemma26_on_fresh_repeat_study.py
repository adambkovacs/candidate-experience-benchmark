#!/usr/bin/env python3
"""Offline frozen plan for a new Gemma 26B A4B reasoning-on matched-three series.

This planner performs no provider or budget calls. Dispatch requires a new reviewed
execution controller, fresh endpoint check, and a child partition in the master ledger.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows

CONFIG = 'openrouter-paid-gemma4-26b-a4b-on'
SERIES = 'gemma26-on-fresh-matched3-v1'
MODEL = 'google/gemma-4-26b-a4b-it'
PROVIDER = 'deepinfra/fp8'
PROVIDER_NAME = 'DeepInfra'
QUANTIZATION = 'fp8'
EFFORT = 'on'
INPUT_PRICE = Decimal('0.07')
OUTPUT_PRICE = Decimal('0.34')
CONTEXT = 262144
MAX_TOKENS = 4096
TIMEOUT = 300.0
PROPOSED_CHILD_USD = Decimal('0.40')
BASE = ROOT / 'results/repeatability-v1' / SERIES
AUDIT = 'results/prompt-comparison-v1-2026-09-24/paired-reports/hosted-remaining-audit-v1/openrouter-paid-gemma4-26b-a4b-on.json'
HOSTED = 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
INPUTS = 'data/pilot/inputs.jsonl'
PROMPT_DIR = 'results/hosted-prompt-preparation-2026-09-24/openrouter-paid-gemma4-26b-a4b-on'
ORDERS = {
    'fresh1': ['P0', 'P1', 'P2'],
    'fresh2': ['P1', 'P2', 'P0'],
    'fresh3': ['P2', 'P0', 'P1'],
}
CONDITIONS = ('P0', 'P1', 'P2')
SMOKES = {
    'P0': 'results/openrouter-gemma26-on-2026-09-23/smoke.jsonl',
    'P1': 'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-gemma4-26b-a4b-on/P1/smoke.jsonl',
    'P2': 'results/prompt-comparison-v1-2026-09-24/runs/openrouter-paid-gemma4-26b-a4b-on/P2/smoke.jsonl',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_jsonl(relative):
    path = ROOT / relative
    return [json.loads(line) for line in path.read_text().splitlines()]


def historical_data():
    audit = json.loads((ROOT / AUDIT).read_text())
    hosted = json.loads((ROOT / HOSTED).read_text())
    config = [x for x in hosted['configurations'] if x.get('id') == CONFIG]
    if audit.get('configuration_id') != CONFIG or len(config) != 1:
        raise ValueError('Missing exact Gemma on historical audit/configuration')
    cfg = config[0]
    controls = cfg['controls']['adapter_controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
            controls['quantization'], controls['reasoning_effort']) != (
            MODEL, PROVIDER, PROVIDER_NAME, QUANTIZATION, EFFORT):
        raise ValueError('Historical exact route differs')
    rc = controls['request_controls']
    if (rc['model'], rc['temperature'], rc['max_tokens'], rc['stream']) != (MODEL, 0, MAX_TOKENS, False):
        raise ValueError('Historical sampling/output controls differ')
    if rc['provider'] != {'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
                          'max_price': {'prompt': float(INPUT_PRICE), 'completion': float(OUTPUT_PRICE),
                                        'request': 0, 'image': 0}}:
        raise ValueError('Historical provider/cost guard differs')
    if rc.get('reasoning') != {'enabled': True} or rc['response_format']['type'] != 'json_schema' or not rc['response_format']['json_schema']['strict']:
        raise ValueError('Historical reasoning/schema control differs')
    return audit, cfg


def source_rows(audit, condition):
    bindings = audit['conditions'][condition]['source_bindings']
    result = {}
    for binding in bindings:
        if sha(ROOT / binding['file']) != binding['sha256']:
            raise ValueError('Historical source hash changed: ' + binding['file'])
        rows = read_jsonl(binding['file'])
        for row in rows:
            if row['id'] in result:
                raise ValueError('Duplicate historical condition record: ' + row['id'])
            result[row['id']] = row
    return bindings, result


def build_condition(audit, inputs, condition):
    bindings, rows = source_rows(audit, condition)
    journal_hashes = {}
    if condition == 'P2':
        for relative in (
            'results/hosted-unattempted-continuation-v2/openrouter-paid-gemma4-26b-a4b-on-p2/attempts.jsonl',
            'results/hosted-unattempted-continuation-v3/openrouter-paid-gemma4-26b-a4b-on-p2/attempts.jsonl',
        ):
            if any(x['file'] == relative for x in audit['conditions'][condition]['lifecycle_bindings']):
                for event in read_jsonl(relative):
                    if event.get('event') == 'request_started':
                        journal_hashes[event['attempt_id']] = event['request_sha256']
    expected = [item['id'] for item in inputs]
    if set(rows) != set(expected) or len(rows) != 60:
        raise ValueError('Historical condition does not account for exact 60-ID roster')
    prompt_file = f'{PROMPT_DIR}/{condition}/instruction.txt' if condition != 'P0' else f'{PROMPT_DIR}/baseline.txt'
    instruction = (ROOT / prompt_file).read_text()
    requests = []
    for position, item in enumerate(inputs, 1):
        old = rows[item['id']]
        payload = old.get('request')
        if not isinstance(payload, dict):
            raise ValueError('Historical request missing for ' + item['id'])
        if set(payload) != {'model', 'temperature', 'max_tokens', 'stream', 'provider',
                            'response_format', 'reasoning', 'messages'}:
            raise ValueError('Historical request has unexpected fields for ' + item['id'])
        messages = payload.get('messages')
        if messages != [
            {'role': 'system', 'content': instruction},
            {'role': 'user', 'content': json.dumps({'feedback': item['feedback']})},
        ]:
            raise ValueError('Prompt or input differs for ' + condition + '/' + item['id'])
        request_hash = digest(json.dumps(payload, sort_keys=True))
        saved_hash = old.get('request_sha256') or journal_hashes.get(old.get('attempt_id'))
        if saved_hash != request_hash:
            raise ValueError('Historical payload digest mismatch for ' + item['id'])
        if old.get('reference_labels_read') is not False:
            raise ValueError('Historical reference-isolation marker missing')
        endpoint = old.get('provider_endpoint') or {}
        if (old.get('requested_model'), old.get('reasoning_effort'), old.get('quantization'),
                endpoint.get('tag'), endpoint.get('provider_name'), endpoint.get('context_length')) != (
                MODEL, EFFORT, QUANTIZATION, PROVIDER, PROVIDER_NAME, CONTEXT):
            raise ValueError('Historical endpoint identity differs for ' + item['id'])
        if (payload.get('model'), payload.get('temperature'), payload.get('max_tokens'),
                payload.get('stream'), payload.get('provider'), payload.get('reasoning')) != (
                MODEL, 0, MAX_TOKENS, False,
                {'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
                 'max_price': {'prompt': float(INPUT_PRICE), 'completion': float(OUTPUT_PRICE), 'request': 0, 'image': 0}},
                {'enabled': True}):
            raise ValueError('Historical payload control differs for ' + item['id'])
        requests.append({
            'position': position, 'record_id': item['id'], 'payload': payload,
            'request_sha256': request_hash, 'input_sha256': digest(item['feedback']),
            'instruction_sha256': digest(instruction),
            'historical_outcome_excluded': old.get('status'),
        })
    return {'instruction': bind(prompt_file), 'historical_attempts': bindings,
            'smoke': requests[:3], 'development': requests}


def estimate(audit):
    known = Decimal(0)
    unknown_bound = Decimal(0)
    calls = 0
    for condition in CONDITIONS:
        bindings, rows = source_rows(audit, condition)
        sources = [r for r in rows.values()]
        sources += read_jsonl(SMOKES[condition])
        calls += len(sources)
        for row in sources:
            known += Decimal(str(row.get('observed_cost_usd') or 0))
            if row.get('cost_unknown'):
                unknown_bound += Decimal(str(row.get('reserved_cost_usd') or 0))
    full_calls = 3 * 3 * (60 + 3)
    per_call_reserve = Decimal(CONTEXT) * INPUT_PRICE / Decimal(1_000_000) + Decimal(MAX_TOKENS) * OUTPUT_PRICE / Decimal(1_000_000)
    known_three_pass = known * 3
    unknown_three_pass = unknown_bound * 3
    return {
        'historical_one_pass_known_development_and_smoke_usd': str(known),
        'historical_one_pass_unknown_charge_bounds_usd': str(unknown_bound),
        'three_pass_known_charge_proxy_usd': str(known_three_pass),
        'three_pass_unknown_bound_sensitivity_usd': str(unknown_three_pass),
        'three_pass_known_plus_historical_unknown_sensitivity_usd': str(known_three_pass + unknown_three_pass),
        'proposed_child_cap_usd': str(PROPOSED_CHILD_USD),
        'proposed_cap_margin_vs_known_plus_unknown_sensitivity_usd': str(PROPOSED_CHILD_USD - known_three_pass - unknown_three_pass),
        'maximum_per_request_reserve_usd': str(per_call_reserve),
        'calls_per_full_series': full_calls,
        'all_calls_reserved_at_maximum_usd': str(per_call_reserve * full_calls),
        'historical_attempt_rows_in_cost_proxy': calls,
        'reservation_policy': 'Reserve each call sequentially against the reviewed child; settle known charges, retain the full reserve for unknown charges, and stop when the next full reserve does not fit. The all-calls full-context amount is a stress bound, not a spend forecast.',
        'uncertainty': 'The historical charge proxy is not a future cost guarantee. The P2 historical pass has two HTTP service failures with unknown-charge bounds; they are included only as a sensitivity, not projected as normal spend.',
    }


def plan_data(repeat):
    if repeat not in ORDERS:
        raise ValueError('Unknown fresh pass')
    audit, cfg = historical_data()
    inputs = read_rows(ROOT / INPUTS)
    if len(inputs) != 60 or any(set(row) != {'id', 'feedback'} for row in inputs):
        raise ValueError('Input roster changed or includes extra fields')
    conditions = {condition: build_condition(audit, inputs, condition) for condition in CONDITIONS}
    evidence_paths = [AUDIT, HOSTED, INPUTS, 'schemas/judgments.schema.json',
                    'docs/REPEATABILITY_PLAN.md', 'scripts/gemma26_on_fresh_repeat_study.py',
                      'scripts/gemma26_on_fresh_repeat_execution.py',
                      'scripts/openrouter_paid_benchmark.py', 'scripts/paid_budget_partitions_v2.py',
                      'scripts/openrouter_benchmark.py',
                      'scripts/openrouter_budget_v2.py', 'scripts/prompt_admission.py']
    for condition in CONDITIONS:
        evidence_paths.extend(b['file'] for b in audit['conditions'][condition]['source_bindings'])
        evidence_paths.extend(b['file'] for b in audit['conditions'][condition]['lifecycle_bindings'])
        evidence_paths.append(SMOKES[condition])
        evidence_paths.append(conditions[condition]['instruction']['path'])
    bindings = [bind(path) for path in dict.fromkeys(evidence_paths)]
    return {
        'schema': 'hosted-fresh-matched-three-plan-v1', 'series_id': SERIES,
        'configuration_id': CONFIG, 'fresh_pass': repeat,
        'condition_order': ORDERS[repeat], 'model': MODEL, 'provider_tag': PROVIDER,
        'provider_name': PROVIDER_NAME, 'quantization': QUANTIZATION,
        'reasoning_effort': EFFORT, 'context_reservation_tokens': CONTEXT,
        'max_tokens': MAX_TOKENS, 'temperature': 0, 'stream': False,
        'timeout_seconds': TIMEOUT, 'workflow': 'single_record_fresh_context',
        'retry_policy': 'no retries or replays; preserve every failed or unknown outcome',
        'continue_on_invalid_output': False,
        'timing_definition': 'elapsed_seconds is request-to-record duration: starts before durable request_started journal fsync; includes provider call, raw-response fsync, billing settlement and response audit; ends before attempt-row and request-finished journal fsync.',
        'smoke_count_per_condition': 3, 'development_count_per_condition': 60,
        'reference_labels_read': False, 'seed_policy': 'No explicit seed in historical payload; requested/effective seed unavailable',
        'historical_status': 'descriptive_only_schedule_changed; this is a distinct new series and does not repair or replace historical outcomes',
        'execution_status': 'offline_prepared_no_inference_no_allocation',
        'child_partition_cap_proposed_usd': str(PROPOSED_CHILD_USD),
        'budget_estimate': estimate(audit), 'conditions': conditions,
        'source_bindings': bindings,
        'dispatch_gate': 'Independent controller review, exact root receipt for each fresh-pass/condition/phase, live exact endpoint/status/pricing/control check, and a $0.40 child partition required before any call; one condition at a time, inspect all three raw smoke outcomes before its development stage.',
    }


def prepare():
    BASE.mkdir(parents=True, exist_ok=True)
    for fresh_pass in ORDERS:
        folder = BASE / fresh_pass
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'manifest.json'
        value = json.dumps(plan_data(fresh_pass), indent=2, ensure_ascii=False) + '\n'
        with path.open('x') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        print(fresh_pass, sha(path), path)


def verify(fresh_pass, expected_sha):
    path = BASE / fresh_pass / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    value = json.loads(path.read_text())
    for binding in value['source_bindings']:
        source = (ROOT / binding['path']).resolve()
        source.relative_to(ROOT.resolve())
        if sha(source) != binding['sha256']:
            raise ValueError('Bound source changed: ' + binding['path'])
    if value != plan_data(fresh_pass):
        raise ValueError('Frozen plan differs from source reconstruction')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    check = sub.add_parser('verify')
    check.add_argument('--fresh-pass', choices=tuple(ORDERS), required=True)
    check.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    else:
        verify(args.fresh_pass, args.manifest_sha256)
        print('verified', args.fresh_pass)


if __name__ == '__main__':
    main()
