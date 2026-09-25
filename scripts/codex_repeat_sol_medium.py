#!/usr/bin/env python3
"""Frozen GPT-6 Sol medium repeat lane; preparation is offline.

Reuse the reviewed Luna runner for execution while keeping its historical
source untouched. Configuration changes here are process-local globals.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import codex_batch_benchmark as batch_runner
from development_benchmark import ROOT, digest, read_rows

_runner_path = Path(__file__).with_name('codex_repeat_study.py')
_runner_spec = importlib.util.spec_from_file_location('_codex_repeat_sol_medium_runner', _runner_path)
runner = importlib.util.module_from_spec(_runner_spec)
_runner_spec.loader.exec_module(runner)

CONFIG = 'codex-gpt-6-sol-medium-batch10'
BASE = ROOT / 'results/repeatability-v1' / CONFIG
PAIR = f'results/prompt-comparison-v1-2026-09-24/paired-reports/{CONFIG}/paired-manifest.json'
EXECUTION = f'results/prompt-comparison-v1-2026-09-24/subscription-codex-runtime163-v1/{CONFIG}/execution-manifest.json'
AUDIT = 'results/repeatability-v1/sol-medium-eligibility-audit.json'
ELIGIBILITY_DOC = 'docs/SOL_MEDIUM_ELIGIBILITY.md'
HISTORICAL_ORDER = ['P0', 'P2', 'P1']
ORDERS = {'repeat2': ['P2', 'P1', 'P0'], 'repeat3': ['P1', 'P0', 'P2']}
MODEL, EFFORT, TIMEOUT = 'gpt-6-sol', 'medium', 600.0
PREVIOUS_RUNTIME = 'codex-cli 0.155.0-alpha.16.3'
P0_RUNTIME = 'codex-cli 0.155.0-alpha.16'
RUNTIME = 'codex-cli 0.155.0-alpha.16.4'


def plan_data(repeat):
    if repeat not in ORDERS:
        raise ValueError('Unknown repeat')
    pair = json.loads((ROOT / PAIR).read_text())
    audit = json.loads((ROOT / AUDIT).read_text())
    decision = audit['historical_repeat_decision']
    if audit['schema'] != 'sol-medium-eligibility-audit-v1' or audit['configuration_id'] != CONFIG:
        raise ValueError('Eligibility audit identity changed')
    if any(decision[c] != 'eligible_first_pass' or decision['additional_full_condition_passes'][c] != 2
           for c in ('P0', 'P1', 'P2')) or decision['total_additional_60_record_conditions'] != 6:
        raise ValueError('Historical repeat decision changed')
    if not audit['paired_audit']['eligible_paired_comparison'] or audit['coverage_gap']['frozen_coverage_lists_configuration']:
        raise ValueError('Eligibility or coverage addendum changed')
    if sorted(('P0', 'P1', 'P2'), key=lambda c: audit['conditions'][c]['first_request_started_utc']) != HISTORICAL_ORDER:
        raise ValueError('Observed historical order changed')
    if audit['sources']['paired_manifest'] != {'file': PAIR, 'sha256': runner.filehash(ROOT / PAIR)}:
        raise ValueError('Paired manifest audit binding changed')
    if audit['sources']['execution_manifest'] != {'file': EXECUTION, 'sha256': runner.filehash(ROOT / EXECUTION)}:
        raise ValueError('Execution manifest audit binding changed')
    controls = pair['controls']
    historical = pair['historical_controls']
    expected = {'requested_model': MODEL, 'effort': EFFORT, 'cli_version': PREVIOUS_RUNTIME,
                'configured_batch_size': 10, 'controller_timeout_seconds': TIMEOUT,
                'auth_mode': 'ChatGPT'}
    if any(controls.get(k) != v for k, v in expected.items()):
        raise ValueError('Original paired controls changed')
    if historical['cli_version'] != P0_RUNTIME or any(historical.get(k) != v for k, v in expected.items() if k != 'cli_version'):
        raise ValueError('Historical P0 controls changed')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if len(inputs) != 60 or any(set(row) != {'id', 'feedback'} for row in inputs):
        raise ValueError('Input isolation failed')
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    sources = [PAIR, EXECUTION, AUDIT, ELIGIBILITY_DOC, runner.COVERAGE,
               'data/pilot/inputs.jsonl',
               'docs/LABELING_GUIDE.md', 'schemas/judgments.schema.json',
               'prompts/variants-v1/P1-classifier.txt', 'prompts/variants-v1/P2-classifier-sop.txt',
               'prompts/variants-v1/manifest.json', 'scripts/codex_benchmark.py',
               'scripts/codex_batch_benchmark.py', 'scripts/prompt_admission.py',
               'scripts/codex_repeat_study.py', 'scripts/codex_repeat_sol_medium.py']
    for name, source in audit['sources'].items():
        if name == 'references_offline_only':
            continue
        if runner.filehash(ROOT / source['file']) != source['sha256']:
            raise ValueError('Eligibility source changed: ' + name)
        sources.append(source['file'])
    conditions = {}
    for condition in HISTORICAL_ORDER:
        source = pair['conditions'][condition]['request_evidence']
        source_path = source['file']
        if audit['conditions'][condition]['raw_requests'] != source:
            raise ValueError('Eligibility raw request binding changed')
        if audit['conditions'][condition]['saved_development_batches'] != 6 or audit['conditions'][condition]['development_positions'] != 60:
            raise ValueError('Historical batch counts changed')
        if runner.filehash(ROOT / source_path) != source['sha256']:
            raise ValueError('Historical attempt binding changed')
        original = [json.loads(line) for line in (ROOT / source_path).read_text().splitlines()]
        if len(original) != 6:
            raise ValueError('Historical condition lacks six batches')
        requests = []
        for idx, old in enumerate(original):
            members = inputs[idx * 10:(idx + 1) * 10]
            variant = None if condition == 'P0' else condition
            parent = None if condition == 'P0' else CONFIG
            prompt = batch_runner.batch_prompt(policy, members, variant, parent)
            schema = batch_runner.batch_schema(members)
            if old['request'] != {'prompt': prompt, 'output_schema': schema} or old['record_order'] != [r['id'] for r in members]:
                raise ValueError('Saved request differs from regenerated frozen request')
            if old['request_sha256'] != digest(prompt) or old['schema_sha256'] != digest(json.dumps(schema, sort_keys=True)):
                raise ValueError('Historical request hash differs')
            expected_runtime = P0_RUNTIME if condition == 'P0' else PREVIOUS_RUNTIME
            if (old['requested_model'] != MODEL or old['effort'] != EFFORT or old['cli_version'] != expected_runtime
                    or old['configured_batch_size'] != 10 or old['controller_timeout_seconds'] != TIMEOUT
                    or old['policy_sha256'] != digest(policy) or old['auth_mode'] != 'ChatGPT'):
                raise ValueError('Historical request controls differ')
            if old['status'] != 'ok' or old['reference_labels_read'] is not False:
                raise ValueError('Historical pass has unhandled outcome or reference exposure')
            requests.append({'repeat': repeat, 'condition': condition, 'phase': 'development',
                             'batch_index': idx + 1, 'record_ids': [r['id'] for r in members],
                             'request': old['request'], 'request_sha256': old['request_sha256'],
                             'schema_sha256': old['schema_sha256'],
                             'historical_attempt_file_sha256': source['sha256']})
        smoke_members = inputs[:3]
        smoke_prompt = batch_runner.batch_prompt(policy, smoke_members,
                                                 None if condition == 'P0' else condition,
                                                 None if condition == 'P0' else CONFIG)
        smoke_schema = batch_runner.batch_schema(smoke_members)
        smoke = {'repeat': repeat, 'condition': condition, 'phase': 'smoke', 'batch_index': 0,
                 'record_ids': [r['id'] for r in smoke_members],
                 'request': {'prompt': smoke_prompt, 'output_schema': smoke_schema},
                 'request_sha256': digest(smoke_prompt),
                 'schema_sha256': digest(json.dumps(smoke_schema, sort_keys=True)),
                 'historical_attempt_file_sha256': source['sha256']}
        conditions[condition] = {'historical_attempts': runner.bound(source_path),
                                 'smoke': smoke, 'development': requests}
        sources.append(source_path)
        instruction = audit['conditions'][condition]['instruction']
        if runner.filehash(ROOT / instruction['file']) != instruction['sha256']:
            raise ValueError('Historical instruction binding changed')
        sources.append(instruction['file'])
    bindings = [runner.bound(path) for path in dict.fromkeys(sources)]
    source_digest = hashlib.sha256(json.dumps(bindings, sort_keys=True).encode()).hexdigest()
    for item in conditions.values():
        for request in [item['smoke'], *item['development']]:
            request['source_bindings_sha256'] = source_digest
    return {'schema': 'codex-repeat-study-v1', 'configuration_id': CONFIG, 'repeat': repeat,
            'historical_pass_order': HISTORICAL_ORDER, 'condition_order': ORDERS[repeat],
            'model': MODEL, 'effort': EFFORT, 'batch_size': 10, 'timeout_seconds': TIMEOUT,
            'surface': 'Codex CLI ChatGPT subscription', 'reference_labels_read': False,
            'seed_policy': 'unchanged CLI default; requested and effective seed unavailable',
            'eligibility_addendum': AUDIT,
            'runtime_amendment': {'from': PREVIOUS_RUNTIME, 'historical_p0': P0_RUNTIME,
                                  'to': RUNTIME, 'basis': 'User accepted CLI patch continuation; live flags and subscription quota require check before execution',
                                  'limit': 'Patch equivalence, hidden CLI wrapper and serving revision remain observational.'},
            'source_bindings': bindings, 'conditions': conditions,
            'execution': 'fresh ephemeral context per smoke or ten-record batch; stop on first non-ok request; no automatic retry or output repair',
            'inference_performed': False}


def configure_runner():
    """Bind only the private runner module, never the canonical import."""
    for key, value in {'CONFIG': CONFIG, 'BASE': BASE, 'PAIR': PAIR, 'EXECUTION': EXECUTION,
                       'MODEL': MODEL, 'EFFORT': EFFORT, 'TIMEOUT': TIMEOUT,
                       'PREVIOUS_RUNTIME': PREVIOUS_RUNTIME, 'RUNTIME': RUNTIME,
                       'ORDERS': ORDERS, 'plan_data': plan_data}.items():
        setattr(runner, key, value)


if __name__ == '__main__':
    configure_runner()
    runner.main()
