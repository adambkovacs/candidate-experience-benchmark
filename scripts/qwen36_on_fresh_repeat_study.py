#!/usr/bin/env python3
"""Reconstruct an offline Qwen 3.6 reasoning-on matched-three admission plan."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows

CONFIG = 'openrouter-paid-qwen36-35b-a3b-on'
SERIES = 'qwen36-on-fresh-matched3-v1'
MODEL = 'qwen/qwen3.6-35b-a3b'
PROVIDER = 'akashml/fp8'
PROVIDER_NAME = 'AkashML'
QUANTIZATION = 'fp8'
INPUT_PRICE = Decimal('0.10')
OUTPUT_PRICE = Decimal('0.90')
CONTEXT = 262144
MAX_TOKENS = 4096
TIMEOUT = 300
PROPOSED_CHILD_USD = Decimal('1.50')
BASE = ROOT / 'results/repeatability-v1' / SERIES
PREP = 'results/hosted-prompt-preparation-2026-09-24/' + CONFIG
HOSTED = 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
INPUTS = 'data/pilot/inputs.jsonl'
ORDERS = {
    'fresh1': ['P0', 'P1', 'P2'],
    'fresh2': ['P1', 'P2', 'P0'],
    'fresh3': ['P2', 'P0', 'P1'],
}
CONDITIONS = ('P0', 'P1', 'P2')
SOURCES = {
    'P0': [PREP + '/historical-attempts.jsonl'],
    'P1': ['results/qwen36-prompt-recovery-v1/on-p1-development.jsonl'],
    'P2': [
        'results/qwen36-prompt-recovery-v1/on-p2-development.jsonl',
        'results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix.jsonl',
        'results/qwen36-on-p2-final21-v2/development.jsonl',
        'results/qwen36-on-p2-final20-v3/development.jsonl',
        'results/qwen36-on-p2-final19-v4/development.jsonl',
        'results/qwen36-on-p2-never-sent-episodes-v1/episode-001/attempts.jsonl',
        'results/qwen36-on-p2-never-sent-episodes-v1/episode-002/attempts.jsonl',
    ],
}
SMOKES = {
    'P0': ['results/openrouter-qwen35-on-2026-09-23/smoke.jsonl'],
    'P1': [
        'results/prompt-comparison-v1-2026-09-24/runs/' + CONFIG + '/P1/smoke.jsonl',
        'results/qwen36-prompt-recovery-v1/on-p1-smoke.jsonl',
    ],
    'P2': ['results/qwen36-prompt-recovery-v1/on-p2-smoke.jsonl'],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_jsonl(relative):
    return [json.loads(line) for line in (ROOT / relative).read_text().splitlines() if line.strip()]


def historical_data():
    hosted = json.loads((ROOT / HOSTED).read_text())
    matches = [x for x in hosted['configurations'] if x.get('id') == CONFIG]
    if len(matches) != 1:
        raise ValueError('Exact historical configuration missing or duplicated')
    cfg = matches[0]
    controls = cfg['controls']['adapter_controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
            controls['quantization'], controls['reasoning_effort'], controls['workflow']) != (
            MODEL, PROVIDER, PROVIDER_NAME, QUANTIZATION, 'on', 'single_record'):
        raise ValueError('Historical route or workflow differs')
    rc = controls['request_controls']
    if rc != expected_controls() or cfg['controller_timeout_seconds'] != TIMEOUT or cfg['continue_on_invalid_output'] is not False:
        raise ValueError('Historical request or failure controls differ')
    return cfg


def expected_controls():
    cfg = json.loads((ROOT / (PREP + '/configuration.json')).read_text())
    rc = cfg['controls']['adapter_controls']['request_controls']
    expected_provider = {
        'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
        'max_price': {'prompt': float(INPUT_PRICE), 'completion': float(OUTPUT_PRICE), 'request': 0, 'image': 0},
    }
    if (set(rc), rc['model'], rc['temperature'], rc['max_tokens'], rc['stream'],
            rc['provider'], rc['reasoning']) != (
            {'model', 'temperature', 'max_tokens', 'stream', 'provider', 'response_format', 'reasoning'},
            MODEL, 0, MAX_TOKENS, False, expected_provider, {'enabled': True}):
        raise ValueError('Prepared request controls differ')
    fmt = rc['response_format']
    if fmt.get('type') != 'json_schema' or fmt.get('json_schema', {}).get('strict') is not True:
        raise ValueError('Prepared strict schema missing')
    if fmt['json_schema']['schema'] != json.loads((ROOT / 'schemas/judgments.schema.json').read_text()):
        raise ValueError('Prepared schema differs from source')
    return rc


def input_rows():
    rows = read_rows(ROOT / INPUTS)
    if len(rows) != 60 or [r['id'] for r in rows] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Frozen input roster differs')
    if any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Input row contains non-input fields')
    return rows


def instruction_file(condition):
    return PREP + ('/baseline.txt' if condition == 'P0' else f'/{condition}/instruction.txt')


def source_rows(condition):
    rows = {}
    for relative in SOURCES[condition]:
        for row in read_jsonl(relative):
            record_id = row.get('id')
            if record_id in rows:
                raise ValueError('Duplicate historical attempt: ' + str(record_id))
            rows[record_id] = row
    if set(rows) != {f'DEV-{i:03}' for i in range(1, 61)}:
        raise ValueError('Historical attempts do not cover exactly 60 positions: ' + condition)
    return rows


def build_condition(condition, inputs):
    rows = source_rows(condition)
    instruction = (ROOT / instruction_file(condition)).read_text()
    controls = expected_controls()
    requests = []
    for position, item in enumerate(inputs, 1):
        record_id = item['id']
        row = rows[record_id]
        payload = row.get('request')
        if not isinstance(payload, dict) or set(payload) != set(controls) | {'messages'}:
            raise ValueError('Historical request body missing or changed: ' + condition + '/' + record_id)
        if {key: payload[key] for key in controls} != controls:
            raise ValueError('Historical request controls differ: ' + condition + '/' + record_id)
        if payload['messages'] != [
            {'role': 'system', 'content': instruction},
            {'role': 'user', 'content': json.dumps({'feedback': item['feedback']})},
        ]:
            raise ValueError('Historical prompt or input differs: ' + condition + '/' + record_id)
        request_hash = digest(json.dumps(payload, sort_keys=True))
        if row.get('request_sha256') != request_hash or row.get('reference_labels_read') is not False:
            raise ValueError('Historical request hash or label isolation missing: ' + condition + '/' + record_id)
        endpoint = row.get('provider_endpoint') or {}
        pricing = endpoint.get('pricing') or {}
        if (row.get('requested_model'), row.get('reasoning_effort'), endpoint.get('tag'),
                endpoint.get('provider_name'), endpoint.get('quantization'),
                endpoint.get('context_length'), endpoint.get('status')) != (
                MODEL, 'on', PROVIDER, PROVIDER_NAME, QUANTIZATION, CONTEXT, 0):
            raise ValueError('Historical endpoint differs: ' + condition + '/' + record_id)
        if (Decimal(str(pricing.get('prompt'))), Decimal(str(pricing.get('completion')))) != (
                INPUT_PRICE / 1_000_000, OUTPUT_PRICE / 1_000_000):
            raise ValueError('Historical price differs: ' + condition + '/' + record_id)
        if condition != 'P0':
            prepared = json.loads((ROOT / f'{PREP}/{condition}/request-{position + 2:02}.json').read_text())
            if prepared.get('request') != payload or prepared.get('adapter_controls') != json.loads((ROOT / (PREP + '/configuration.json')).read_text())['controls']['adapter_controls']:
                raise ValueError('Frozen prepared request differs: ' + condition + '/' + record_id)
        requests.append({
            'position': position, 'record_id': record_id, 'payload': payload,
            'request_sha256': request_hash, 'input_sha256': digest(item['feedback']),
            'instruction_sha256': digest(instruction),
            'historical_outcome_excluded': row['status'],
        })
    return {'instruction': bind(instruction_file(condition)),
            'historical_attempts': [bind(p) for p in SOURCES[condition]],
            'smoke': requests[:3], 'development': requests}


def estimate():
    known = Decimal(0)
    unknown = Decimal(0)
    count = 0
    for condition in CONDITIONS:
        for relative in SOURCES[condition] + SMOKES[condition]:
            for row in read_jsonl(relative):
                count += 1
                if row.get('observed_cost_usd') is not None:
                    known += Decimal(str(row['observed_cost_usd']))
                if row.get('cost_unknown'):
                    bound = row.get('reserved_cost_usd')
                    if bound is None:
                        raise ValueError('Unknown charge lacks reserved bound: ' + relative)
                    unknown += Decimal(str(bound))
    reserve = (CONTEXT * INPUT_PRICE + MAX_TOKENS * OUTPUT_PRICE) / 1_000_000
    calls = 3 * 3 * (60 + 3)
    return {
        'historical_attempt_rows_in_proxy': count,
        'historical_one_pass_known_charges_usd': str(known),
        'historical_one_pass_unknown_charge_bounds_usd': str(unknown),
        'three_pass_known_charge_proxy_usd': str(known * 3),
        'three_pass_unknown_bound_sensitivity_usd': str(unknown * 3),
        'three_pass_known_plus_unknown_sensitivity_usd': str((known + unknown) * 3),
        'proposed_child_budget_usd': str(PROPOSED_CHILD_USD),
        'proposed_margin_over_proxy_plus_sensitivity_usd': str(PROPOSED_CHILD_USD - (known + unknown) * 3),
        'maximum_per_request_reserve_usd': str(reserve),
        'calls_per_full_series': calls,
        'all_calls_at_maximum_reserve_usd': str(reserve * calls),
        'uncertainty': 'Historical charges are only a proxy. Unknown-charge bounds are separate sensitivity, not forecast spending. Every future request needs its own full reserve before dispatch.',
    }


def plan_data(fresh_pass):
    if fresh_pass not in ORDERS:
        raise ValueError('Unknown fresh pass')
    historical_data()
    inputs = input_rows()
    conditions = {condition: build_condition(condition, inputs) for condition in CONDITIONS}
    p2_counts = Counter(r['historical_outcome_excluded'] for r in conditions['P2']['development'])
    if p2_counts != {'ok': 54, 'service_error': 6}:
        raise ValueError('Historical P2 54/6 accounting changed')
    evidence = [HOSTED, PREP + '/configuration.json', INPUTS, 'schemas/judgments.schema.json',
                'docs/REPEATABILITY_PLAN.md', 'docs/QWEN36_ON_P2_EPISODES.md']
    for condition in CONDITIONS:
        evidence += SOURCES[condition] + SMOKES[condition] + [instruction_file(condition)]
        if condition != 'P0':
            evidence += [f'{PREP}/{condition}/request-{i + 2:02}.json' for i in range(1, 61)]
    return {
        'schema': 'hosted-fresh-matched-three-plan-v1', 'series_id': SERIES,
        'configuration_id': CONFIG, 'fresh_pass': fresh_pass,
        'condition_order': ORDERS[fresh_pass], 'model': MODEL,
        'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
        'quantization': QUANTIZATION, 'reasoning_effort': 'on',
        'temperature': 0, 'max_tokens': MAX_TOKENS, 'stream': False,
        'context_reservation_tokens': CONTEXT, 'timeout_seconds': TIMEOUT,
        'workflow': 'single_record_fresh_context',
        'continue_on_invalid_output': False,
        'retry_policy': 'No retries or replays; retain every invalid, failed or unknown outcome.',
        'seed_policy': 'No explicit seed in saved request; requested and effective seed unavailable.',
        'reference_labels_read': False,
        'smoke_count_per_condition': 3, 'development_count_per_condition': 60,
        'historical_p2_outcomes_preserved': dict(p2_counts),
        'historical_status': 'Descriptive only: interrupted suffix schedule; no old attempt counts as a fresh pass.',
        'execution_status': 'offline_prepared_no_inference_no_allocation',
        'aggregate_openrouter_cap_usd': '10',
        'proposed_child_budget_usd': str(PROPOSED_CHILD_USD),
        'budget_estimate': estimate(), 'conditions': conditions,
        'source_bindings': [bind(p) for p in dict.fromkeys(evidence)],
        'dispatch_gate': 'Independent controller review, exact live endpoint and controls, funded child partition and stage receipts required. Inspect each three-record smoke before development. Stop before an unfunded call.',
    }


def prepare():
    for fresh_pass in ORDERS:
        folder = BASE / fresh_pass
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'manifest.json'
        with target.open('x') as stream:
            json.dump(plan_data(fresh_pass), stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        print(fresh_pass, sha(target), target)


def verify(fresh_pass, expected_sha):
    target = BASE / fresh_pass / 'manifest.json'
    if sha(target) != expected_sha:
        raise ValueError('Manifest SHA-256 mismatch')
    manifest = json.loads(target.read_text())
    for binding in manifest['source_bindings']:
        if bind(binding['path']) != binding:
            raise ValueError('Bound source changed: ' + binding['path'])
    if manifest != plan_data(fresh_pass):
        raise ValueError('Manifest differs from source reconstruction')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'estimate'))
    parser.add_argument('--fresh-pass', choices=tuple(ORDERS))
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'estimate':
        print(json.dumps(estimate(), indent=2))
    else:
        if not args.fresh_pass or not args.manifest_sha256:
            parser.error('verify requires --fresh-pass and --manifest-sha256')
        verify(args.fresh_pass, args.manifest_sha256)
        print('verified', args.fresh_pass)


if __name__ == '__main__':
    main()
