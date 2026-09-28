#!/usr/bin/env python3
"""One offline planner and gated Codex repeat dispatcher for the remaining eligible roster.

No model call occurs on import, inventory, prepare, or inspect. Each CLI invocation
loads a private copy of the frozen execution runner and selects one configuration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import codex_batch_benchmark as batch_runner
from development_benchmark import ROOT, digest, read_rows

CONTROLLER = Path(__file__).resolve()
FROZEN_RUNNER = CONTROLLER.with_name('codex_repeat_study.py')
COVERAGE = 'results/repeatability-v1/coverage.json'
RUNTIME = 'codex-cli 0.155.0-alpha.16.4'
PREVIOUS_RUNTIME = 'codex-cli 0.155.0-alpha.16.3'
P0_RUNTIME = 'codex-cli 0.155.0-alpha.16'
REVIEW_SCHEMA = 'codex-repeat-roster-root-review-v1'
QUOTA_MAX_AGE_SECONDS = 300

# Exact reviewed historical roster, excluding dedicated Luna-medium and Sol-high
# controllers. Sol-medium is admitted by its separate coverage addendum.
CONFIGS = (
    'codex-gpt-5.6-luna-high',
    'codex-gpt-5.6-luna-low-phase2-batch10-p0',
    'codex-gpt-5.6-luna-medium',
    'codex-gpt-5.6-sol-high',
    'codex-gpt-5.6-sol-low',
    'codex-gpt-5.6-sol-medium',
    'codex-gpt-5.6-sol-xhigh',
    'codex-gpt-5.6-terra-high',
    'codex-gpt-5.6-terra-xhigh',
    'codex-gpt-6-astra-high',
    'codex-gpt-6-astra-low-phase2-batch10-p0',
    'codex-gpt-6-astra-xhigh',
    'codex-gpt-6-luna-high-batch10',
    'codex-gpt-6-luna-xhigh-batch10',
    'codex-gpt-6-sol-xhigh-batch10',
)


def paths(config):
    if config not in CONFIGS:
        raise ValueError('Configuration has no reviewed roster lane')
    base = ROOT / 'results/repeatability-v1' / config
    pair = f'results/prompt-comparison-v1-2026-09-24/paired-reports/{config}/paired-manifest.json'
    execution = f'results/prompt-comparison-v1-2026-09-24/subscription-codex-runtime163-v1/{config}/execution-manifest.json'
    return base, pair, execution


def private_runner():
    spec = importlib.util.spec_from_file_location('_codex_repeat_roster_private', FROZEN_RUNNER)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def schedule(historical):
    if len(historical) != 3 or set(historical) != {'P0', 'P1', 'P2'} or historical[0] != 'P0':
        raise ValueError('Unsupported historical condition order')
    return {'repeat2': historical[1:] + historical[:1],
            'repeat3': historical[2:] + historical[:2]}


def plan_data(config, repeat, runner=None):
    base, pair_path, execution_path = paths(config)
    if runner is None:
        runner = private_runner()
    coverage = json.loads((ROOT / COVERAGE).read_text())
    matches = [x for x in coverage['groups'] if x.get('id') == config]
    if len(matches) != 1:
        raise ValueError('Historical coverage identity missing or duplicated')
    entry = matches[0]
    historical_order = entry.get('observed_condition_order')
    orders = schedule(historical_order)
    if repeat not in orders:
        raise ValueError('Unknown repeat')
    if (entry.get('historical_triple_status') != 'eligible_first_pass' or
            any(entry.get('condition_status', {}).get(c) != 'eligible_first_pass' for c in historical_order) or
            any(entry.get('additional_passes_if_admitted', {}).get(c) != 2 for c in historical_order)):
        raise ValueError('Historical triple is not eligible for two additional passes')
    pair = json.loads((ROOT / pair_path).read_text())
    controls = pair['controls']
    old_p0 = pair['historical_controls']
    model, effort, timeout = controls['requested_model'], controls['effort'], controls['controller_timeout_seconds']
    if (effort not in ('low', 'medium', 'high', 'xhigh') or
            model not in ('gpt-5.6-luna', 'gpt-5.6-sol', 'gpt-5.6-terra',
                          'gpt-6-astra', 'gpt-6-luna', 'gpt-6-sol') or
            timeout != 600.0 or pair.get('parent_baseline_id') != config or
            entry.get('model') != model or entry.get('route') != 'Codex subscription' or
            entry.get('comparison_eligible_in_export') is not True):
        raise ValueError('Historical model, effort, timeout or baseline changed')
    expected = {'requested_model': model, 'effort': effort, 'cli_version': PREVIOUS_RUNTIME,
                'configured_batch_size': 10, 'controller_timeout_seconds': timeout,
                'auth_mode': 'ChatGPT'}
    if any(controls.get(key) != value for key, value in expected.items()):
        raise ValueError('Historical paired controls changed')
    expected['cli_version'] = P0_RUNTIME
    if any(old_p0.get(key) != value for key, value in expected.items()):
        raise ValueError('Historical P0 controls changed')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if (len(inputs) != 60 or [r.get('id') for r in inputs] != [f'DEV-{i:03d}' for i in range(1, 61)] or
            any(set(r) != {'id', 'feedback'} for r in inputs)):
        raise ValueError('Input membership or reference isolation changed')
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    sources = [pair_path, execution_path, COVERAGE, 'data/pilot/inputs.jsonl',
               'docs/LABELING_GUIDE.md', 'schemas/judgments.schema.json',
               'prompts/variants-v1/P1-classifier.txt', 'prompts/variants-v1/P2-classifier-sop.txt',
               'prompts/variants-v1/manifest.json', 'scripts/codex_benchmark.py',
               'scripts/codex_batch_benchmark.py', 'scripts/prompt_admission.py',
               'scripts/codex_repeat_study.py', 'scripts/codex_repeat_roster.py']
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        source = pair['conditions'][condition]['request_evidence']
        source_path = source['file']
        if source_path != entry['source_paths'][condition]['attempts']:
            raise ValueError('Coverage and paired attempt source differ')
        if runner.filehash(ROOT / source_path) != source['sha256']:
            raise ValueError('Historical attempt binding changed')
        original = [json.loads(line) for line in (ROOT / source_path).read_text().splitlines()]
        if len(original) != 6:
            raise ValueError('Historical condition lacks six batches')
        requests = []
        for index, old in enumerate(original):
            members = inputs[index * 10:(index + 1) * 10]
            variant = None if condition == 'P0' else condition
            parent = None if condition == 'P0' else config
            prompt = batch_runner.batch_prompt(policy, members, variant, parent)
            schema = batch_runner.batch_schema(members)
            if (old.get('request') != {'prompt': prompt, 'output_schema': schema} or
                    old.get('record_order') != [r['id'] for r in members] or
                    old.get('request_sha256') != digest(prompt) or
                    old.get('schema_sha256') != digest(json.dumps(schema, sort_keys=True))):
                raise ValueError('Historical prompt, schema or batch membership changed')
            runtime = P0_RUNTIME if condition == 'P0' else PREVIOUS_RUNTIME
            if (old.get('requested_model'), old.get('effort'), old.get('cli_version'),
                    old.get('configured_batch_size'), old.get('controller_timeout_seconds'),
                    old.get('policy_sha256'), old.get('auth_mode'), old.get('status'),
                    old.get('reference_labels_read')) != (
                    model, effort, runtime, 10, timeout, digest(policy), 'ChatGPT', 'ok', False):
                raise ValueError('Historical request controls or outcome changed')
            requests.append({'repeat': repeat, 'condition': condition, 'phase': 'development',
                             'batch_index': index + 1, 'record_ids': [r['id'] for r in members],
                             'request': old['request'], 'request_sha256': old['request_sha256'],
                             'schema_sha256': old['schema_sha256'],
                             'historical_attempt_file_sha256': source['sha256']})
        members = inputs[:3]
        prompt = batch_runner.batch_prompt(policy, members, None if condition == 'P0' else condition,
                                           None if condition == 'P0' else config)
        schema = batch_runner.batch_schema(members)
        smoke = {'repeat': repeat, 'condition': condition, 'phase': 'smoke', 'batch_index': 0,
                 'record_ids': [r['id'] for r in members],
                 'request': {'prompt': prompt, 'output_schema': schema},
                 'request_sha256': digest(prompt),
                 'schema_sha256': digest(json.dumps(schema, sort_keys=True)),
                 'historical_attempt_file_sha256': source['sha256']}
        conditions[condition] = {'historical_attempts': runner.bound(source_path),
                                 'smoke': smoke, 'development': requests}
        sources.append(source_path)
    bindings = [runner.bound(path) for path in dict.fromkeys(sources)]
    source_digest = hashlib.sha256(json.dumps(bindings, sort_keys=True).encode()).hexdigest()
    for item in conditions.values():
        for request in [item['smoke'], *item['development']]:
            request['source_bindings_sha256'] = source_digest
    return {'schema': 'codex-repeat-study-v1', 'configuration_id': config, 'repeat': repeat,
            'historical_pass_order': historical_order, 'condition_order': orders[repeat],
            'model': model, 'effort': effort, 'batch_size': 10, 'timeout_seconds': timeout,
            'surface': 'Codex CLI ChatGPT subscription', 'reference_labels_read': False,
            'seed_policy': 'unchanged CLI default; requested and effective seed unavailable',
            'runtime_amendment': {'from': PREVIOUS_RUNTIME, 'historical_p0': P0_RUNTIME,
                                  'to': RUNTIME, 'basis': 'Accepted CLI patch continuation; live CLI and quota require dispatch check',
                                  'limit': 'Patch equivalence, hidden CLI wrapper and serving revision remain observational.'},
            'source_bindings': bindings, 'conditions': conditions,
            'execution': 'fresh ephemeral context per smoke or ten-record batch; stop on first non-ok request; no automatic retry or output repair',
            'inference_performed': False}


def configured_runner(config):
    base, pair, execution = paths(config)
    runner = private_runner()
    plan = lambda repeat: plan_data(config, repeat, runner)
    first = plan('repeat2')
    orders = schedule(first['historical_pass_order'])
    for key, value in {'CONFIG': config, 'BASE': base, 'PAIR': pair, 'EXECUTION': execution,
                       'MODEL': first['model'], 'EFFORT': first['effort'],
                       'TIMEOUT': first['timeout_seconds'], 'PREVIOUS_RUNTIME': PREVIOUS_RUNTIME,
                       'RUNTIME': RUNTIME, 'ORDERS': orders, 'plan_data': plan}.items():
        setattr(runner, key, value)
    return runner


def review_gate(runner, manifest, repeat, condition, phase, path, expected_hash, now=None):
    receipt = Path(path)
    if not receipt.is_absolute():
        raise ValueError('Private root review receipt must use an absolute path')
    receipt = receipt.resolve()
    if receipt.is_relative_to(ROOT.resolve()):
        raise ValueError('Quota receipt must remain outside the public repository')
    if len(expected_hash) != 64 or any(ch not in '0123456789abcdef' for ch in expected_hash):
        raise ValueError('Root review hash must be SHA-256 hex')
    if runner.filehash(receipt) != expected_hash:
        raise ValueError('Root review receipt hash changed')
    review = json.loads(receipt.read_text())
    quota = review.get('quota') or {}
    checked = datetime.fromisoformat(quota.get('checked_at_utc', '').replace('Z', '+00:00'))
    current = now or datetime.now(timezone.utc)
    age = (current - checked).total_seconds()
    if (review.get('schema'), review.get('approved'), review.get('configuration_id'),
            review.get('repeat'), review.get('condition'), review.get('phase'),
            review.get('manifest_sha256'), review.get('controller_sha256'),
            review.get('model'), review.get('effort'), review.get('runtime')) != (
            REVIEW_SCHEMA, True, manifest['configuration_id'], repeat, condition, phase,
            runner.filehash(runner.BASE / repeat / 'manifest.json'), runner.filehash(CONTROLLER),
            manifest['model'], manifest['effort'], RUNTIME):
        raise ValueError('Root review identity or exact controls differ')
    if (quota.get('source') != 'Codex get_usage_limits' or
            quota.get('ordinary_usage_allowed') is not True or
            quota.get('spend_control_reached') is not False or
            not isinstance(quota.get('weekly_remaining_percent'), (int, float)) or
            isinstance(quota['weekly_remaining_percent'], bool) or
            not 0 < quota['weekly_remaining_percent'] <= 100 or
            checked.tzinfo is None or not 0 <= age <= QUOTA_MAX_AGE_SECONDS):
        raise ValueError('Codex quota admission is stale, exhausted or unverifiable')
    short = quota.get('five_hour_remaining_percent')
    if short is not None and (isinstance(short, bool) or not isinstance(short, (int, float)) or not 0 < short <= 100):
        raise ValueError('Codex short-window quota is exhausted or invalid')
    inspection = runner.BASE / repeat / condition / 'smoke-inspection.json'
    if phase == 'development':
        if not inspection.exists() or review.get('smoke_inspection_sha256') != runner.filehash(inspection):
            raise ValueError('Development root review lacks exact smoke inspection')
    elif review.get('smoke_inspection_sha256') is not None:
        raise ValueError('Smoke review cannot carry development inspection')
    return review


def attest_admission(runner, manifest, repeat, condition, phase, review_hash):
    """Persist only admission proof; the frozen runner owns dispatch evidence."""
    folder = runner.BASE / repeat / condition
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{phase}.admission-{review_hash}.json'
    value = {'schema': 'codex-repeat-roster-admission-v1',
             'status': 'admitted_before_dispatch', 'dispatch_status': 'not_asserted',
             'configuration_id': manifest['configuration_id'], 'repeat': repeat,
             'condition': condition, 'phase': phase, 'model': manifest['model'],
             'effort': manifest['effort'], 'runtime': RUNTIME,
             'manifest_sha256': runner.filehash(runner.BASE / repeat / 'manifest.json'),
             'controller_sha256': runner.filehash(CONTROLLER),
             'private_review_sha256': review_hash}
    if phase == 'development':
        value['smoke_inspection_sha256'] = runner.filehash(folder / 'smoke-inspection.json')
    raw = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    try:
        with path.open('x') as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        if path.read_text() != raw:
            raise ValueError('Existing admission attestation differs') from None
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, choices=CONFIGS)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('prepare')
    runtime = actions.add_parser('runtime-check')
    runtime.add_argument('--codex', default='/Applications/ChatGPT.app/Contents/Resources/codex')
    for action in ('smoke', 'inspect', 'development'):
        phase = actions.add_parser(action)
        phase.add_argument('--repeat', required=True, choices=('repeat2', 'repeat3'))
        phase.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        phase.add_argument('--manifest-sha256', required=True)
        if action == 'inspect':
            phase.add_argument('--note', required=True)
        else:
            phase.add_argument('--codex', default='/Applications/ChatGPT.app/Contents/Resources/codex')
            phase.add_argument('--review-receipt', required=True)
            phase.add_argument('--review-sha256', required=True)
    args = parser.parse_args(argv)
    runner = configured_runner(args.config)
    if args.action == 'prepare':
        runner.prepare()
        return
    if args.action == 'runtime-check':
        _, version = runner.runtime_check(args.codex)
        print(version, 'ChatGPT subscription auth and flags present')
        return
    manifest = runner.verify_manifest(args.repeat, args.manifest_sha256)
    if args.action == 'inspect':
        runner.inspect(manifest, args.condition, args.note)
        return
    review_gate(runner, manifest, args.repeat, args.condition, args.action,
                args.review_receipt, args.review_sha256)
    attest_admission(runner, manifest, args.repeat, args.condition, args.action,
                     args.review_sha256)
    runner.run_phase(manifest, args.condition, args.action, args.codex)


if __name__ == '__main__':
    main()
