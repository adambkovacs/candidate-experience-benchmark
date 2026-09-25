#!/usr/bin/env python3
"""Offline Gemma 26 off repeat plan. This file makes no provider or budget calls.

Execution requires a separately reviewed controller. A manifest generated here
is a frozen request plan, not a launch approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows

CONFIG = 'openrouter-paid-gemma4-26b-a4b-off'
MODEL = 'google/gemma-4-26b-a4b-it'
PROVIDER = 'deepinfra/fp8'
EFFORT = 'off'
BASE = ROOT / 'results/repeatability-v1' / CONFIG
PAIR = f'results/prompt-comparison-v1-2026-09-24/paired-reports/{CONFIG}/paired-manifest.json'
COVERAGE = 'results/repeatability-v1/coverage.json'
WAVE = 'results/repeatability-v1/paid-wave-preflight-v1.json'
ORDERS = {'repeat2': ['P2', 'P1', 'P0'], 'repeat3': ['P1', 'P0', 'P2']}
HISTORICAL_ORDER = ['P0', 'P2', 'P1']
CAP_USD = '0.20'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_bound(binding):
    path = (ROOT / binding['path']).resolve()
    path.relative_to(ROOT.resolve())
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != binding['sha256']:
        raise ValueError('Source changed: ' + binding['path'])
    return raw


def source_requests(condition, pair, inputs):
    evidence = pair['conditions'][condition]['request_evidence']
    path = evidence['file']
    if sha(ROOT / path) != evidence['sha256']:
        raise ValueError('Historical request evidence changed')
    rows = [json.loads(line) for line in (ROOT / path).read_text().splitlines()]
    if len(rows) != 60 or [r['id'] for r in rows] != [x['id'] for x in inputs]:
        raise ValueError('Historical 60-record order changed')
    expected_controls = pair['controls']['request_controls']
    requests = []
    for idx, (old, item) in enumerate(zip(rows, inputs), 1):
        if old['status'] != 'ok' or old['reference_labels_read'] is not False:
            raise ValueError('Historical outcome or reference isolation changed')
        payload = old['request']
        for key, value in expected_controls.items():
            if payload.get(key) != value:
                raise ValueError('Historical payload control changed: ' + key)
        if set(payload) != set(expected_controls) | {'messages'}:
            raise ValueError('Historical payload fields changed')
        if payload['messages'] != [
                {'role': 'system', 'content': payload['messages'][0]['content']},
                {'role': 'user', 'content': json.dumps({'feedback': item['feedback']})}]:
            raise ValueError('Historical role placement or feedback changed')
        if old['request_sha256'] != digest(json.dumps(payload, sort_keys=True)):
            raise ValueError('Historical request digest changed')
        if old['requested_model'] != MODEL or old['reasoning_effort'] != EFFORT or old['quantization'] != 'fp8':
            raise ValueError('Historical model controls changed')
        if old['provider_endpoint']['tag'] != PROVIDER or old['provider_endpoint']['provider_name'] != 'DeepInfra':
            raise ValueError('Historical provider changed')
        if old['policy_sha256'] != digest(payload['messages'][0]['content']) or old['input_sha256'] != digest(item['feedback']):
            raise ValueError('Historical instruction or input hash changed')
        requests.append({'position': idx, 'record_id': item['id'], 'payload': payload,
                         'request_sha256': old['request_sha256'], 'input_sha256': old['input_sha256'],
                         'instruction_sha256': old['policy_sha256'], 'source_attempt_sha256': evidence['sha256']})
    return requests, path


def plan_data(repeat):
    if repeat not in ORDERS:
        raise ValueError('Unknown repeat')
    pair = json.loads((ROOT / PAIR).read_text())
    cover = json.loads((ROOT / COVERAGE).read_text())
    wave = json.loads((ROOT / WAVE).read_text())
    group = next(x for x in cover['groups'] if x['id'] == CONFIG)
    entry = next(x for x in wave['configurations'] if x['id'] == CONFIG)
    if group['historical_triple_status'] != 'eligible_first_pass' or group['observed_condition_order'] != HISTORICAL_ORDER:
        raise ValueError('Historical repeat eligibility changed')
    if entry['paired_manifest'] != bind(PAIR) or entry['proposed_partition_cap_usd'] != CAP_USD:
        raise ValueError('Wave proposal or paired manifest changed')
    if entry['public_route']['status'] != 'verified_public_endpoint' or entry['controls']['provider_tag'] != PROVIDER:
        raise ValueError('Exact public route not verified')
    controls = pair['controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
        controls['quantization'], controls['reasoning_effort'], controls['workflow']) != (
            MODEL, PROVIDER, 'DeepInfra', 'fp8', EFFORT, 'single_record'):
        raise ValueError('Paired route controls changed')
    rc = controls['request_controls']
    if rc['temperature'] != 0 or rc['max_tokens'] != 4096 or rc['stream'] is not False:
        raise ValueError('Sampling or output limit changed')
    if rc['provider'] != {'only': [PROVIDER], 'allow_fallbacks': False,
                          'require_parameters': True,
                          'max_price': {'prompt': 0.07, 'completion': 0.34, 'request': 0, 'image': 0}}:
        raise ValueError('Provider guard changed')
    if rc['reasoning'] != {'enabled': False} or rc['response_format']['type'] != 'json_schema' or rc['response_format']['json_schema']['strict'] is not True:
        raise ValueError('Reasoning or parser guard changed')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if len(inputs) != 60 or any(set(row) != {'id', 'feedback'} for row in inputs):
        raise ValueError('Input isolation failed')
    conditions = {}
    paths = [PAIR, COVERAGE, WAVE, 'data/pilot/inputs.jsonl', 'schemas/judgments.schema.json',
             'docs/REPEATABILITY_PLAN.md', 'scripts/openrouter_repeat_study.py',
             'scripts/openrouter_paid_benchmark.py', 'scripts/paid_budget_partitions_v2.py',
             'scripts/openrouter_budget_v2.py', 'scripts/prompt_admission.py']
    for condition in ('P0', 'P1', 'P2'):
        requests, source = source_requests(condition, pair, inputs)
        if entry['historical_request_evidence'][condition] != pair['conditions'][condition]['request_evidence']:
            raise ValueError('Wave request source differs')
        paths.append(source)
        conditions[condition] = {'historical_attempts': bind(source),
                                 'smoke': requests[:3], 'development': requests}
    bindings = [bind(path) for path in dict.fromkeys(paths)]
    return {'schema': 'openrouter-paid-repeat-plan-v1', 'configuration_id': CONFIG,
            'repeat': repeat, 'historical_pass_order': HISTORICAL_ORDER,
            'condition_order': ORDERS[repeat], 'model': MODEL, 'provider_tag': PROVIDER,
            'reasoning_effort': EFFORT, 'partition_cap_usd': CAP_USD,
            'input_count': 60, 'request_unit': 'single_record_fresh_context',
            'smoke_count_per_condition': 3, 'max_tokens': 4096,
            'seed_policy': 'No explicit seed in historical payload; requested and effective seed unavailable',
            'reference_labels_read': False,
            'repeat_status': 'offline_prepared_no_inference',
            'dispatch_gate': 'Separate reviewed runner, root review receipt, live endpoint and budget partition required',
            'source_bindings': bindings, 'conditions': conditions}


def prepare():
    BASE.mkdir(parents=True, exist_ok=True)
    for repeat in ORDERS:
        folder = BASE / repeat
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'manifest.json'
        raw = json.dumps(plan_data(repeat), indent=2, ensure_ascii=False) + '\n'
        with path.open('x') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        print(repeat, sha(path), path)


def verify(repeat, expected_sha):
    path = BASE / repeat / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    value = json.loads(path.read_text())
    for binding in value['source_bindings']:
        read_bound(binding)
    if value != plan_data(repeat):
        raise ValueError('Manifest differs from frozen source reconstruction')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    check = sub.add_parser('verify')
    check.add_argument('--repeat', choices=tuple(ORDERS), required=True)
    check.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    else:
        verify(args.repeat, args.manifest_sha256)
        print('verified', args.repeat)


if __name__ == '__main__':
    main()
