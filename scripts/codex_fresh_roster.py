#!/usr/bin/env python3
"""Offline plans and separately admitted Codex subscription fresh matched-three runs.

No import, plan, prepare, verify, or inspect action contacts a model. Historical
attempts remain observations, never a first pass or a request template here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import codex_benchmark as single
import codex_batch_benchmark as batch
import prompt_admission
from development_benchmark import ROOT, digest, read_rows

CONTROLLER = Path(__file__).resolve()
CODEX = '/opt/homebrew/bin/codex'
RUNTIME = 'codex-cli 0.156.1'
TIMEOUT = 600.0
REVIEW_SCHEMA = 'codex-fresh-roster-root-review-v1'
ORDERS = {'fresh1': ['P0', 'P1', 'P2'], 'fresh2': ['P1', 'P2', 'P0'],
          'fresh3': ['P2', 'P0', 'P1']}
CONFIGS = {
    'codex-gpt-5.6-luna-xhigh': ('gpt-5.6-luna', 'xhigh', ('P1', 'P2')),
    'codex-gpt-6-astra-medium': ('gpt-6-astra', 'medium', ('P2',)),
    'codex-gpt-5.6-terra-low': ('gpt-5.6-terra', 'low', ('P1',)),
    'codex-gpt-5.6-terra-medium': ('gpt-5.6-terra', 'medium', ('P2',)),
    'codex-gpt-6-sol-low-batch10': ('gpt-6-sol', 'low', ()),
    'codex-gpt-6-luna-low-batch10': ('gpt-6-luna', 'low', ()),
}
INPUT = 'data/pilot/inputs.jsonl'
POLICY = 'docs/LABELING_GUIDE.md'
SOURCES = (INPUT, POLICY, 'schemas/judgments.schema.json',
           'prompts/variants-v1/P1-classifier.txt',
           'prompts/variants-v1/P2-classifier-sop.txt',
           'prompts/variants-v1/manifest.json',
           'scripts/codex_benchmark.py', 'scripts/codex_batch_benchmark.py',
           'scripts/prompt_controller.py', 'scripts/prompt_admission.py',
           'scripts/development_benchmark.py', 'scripts/codex_fresh_roster.py')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for part in iter(lambda: source.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        output.flush()
        os.fsync(output.fileno())


def line(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + '\n')
    handle.flush()
    os.fsync(handle.fileno())


def base_dir(config):
    if config not in CONFIGS:
        raise ValueError('Unreviewed configuration')
    return ROOT / 'results/repeatability-v1' / (config + '-fresh-matched3')


def historical_sources(config):
    conditions = CONFIGS[config][2]
    if conditions:
        return tuple('results/prompt-comparison-v1-2026-09-24/subscription-suffix-continuation-v1/reconciliation-v1/'
                     + config + '-' + condition + '.json' for condition in conditions)
    return ('results/prompt-comparison-v1-2026-09-24/paired-reports/' + config + '/ineligible-source-audit.json',)


def input_rows():
    rows = read_rows(ROOT / INPUT)
    if len(rows) != 60 or [r.get('id') for r in rows] != [f'DEV-{i:03d}' for i in range(1, 61)]:
        raise ValueError('Development membership changed')
    if any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Reference labels or unexpected fields present in request inputs')
    return rows


def plan_data(config, fresh):
    if config not in CONFIGS or fresh not in ORDERS:
        raise ValueError('Unknown config or fresh pass')
    model, effort, _ = CONFIGS[config]
    rows = input_rows()
    policy = (ROOT / POLICY).read_text().split('## Simulated routing')[0]
    bindings = [{'path': path, 'sha256': sha(ROOT / path)}
                for path in (*SOURCES, *historical_sources(config))]
    binding_hash = digest(json.dumps(bindings, sort_keys=True))
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        variant = None if condition == 'P0' else condition
        parent = None if condition == 'P0' else config
        def request(members, phase, number):
            prompt = batch.batch_prompt(policy, members, variant, parent)
            schema = batch.batch_schema(members)
            return {'pass': fresh, 'condition': condition, 'phase': phase,
                    'batch_index': number, 'record_ids': [r['id'] for r in members],
                    'request': {'prompt': prompt, 'output_schema': schema},
                    'request_sha256': digest(prompt),
                    'schema_sha256': digest(json.dumps(schema, sort_keys=True)),
                    'source_bindings_sha256': binding_hash}
        conditions[condition] = {
            'smoke': request(rows[:3], 'smoke', 0),
            'development': [request(rows[i:i + 10], 'development', i // 10 + 1)
                            for i in range(0, 60, 10)]}
    return {'schema': 'codex-fresh-matched3-v1', 'configuration_id': config,
            'series_id': config + '-fresh-matched3', 'pass': fresh,
            'condition_order': ORDERS[fresh], 'model': model, 'effort': effort,
            'cli_path': CODEX, 'cli_version': RUNTIME, 'timeout_seconds': TIMEOUT,
            'batch_size': 10, 'auth_mode': 'ChatGPT subscription',
            'seed_policy': 'CLI default; requested and effective seed unavailable',
            'reference_labels_read': False, 'historical_first_pass_used': False,
            'historical_sources': list(historical_sources(config)),
            'source_bindings': bindings, 'conditions': conditions,
            'inference_performed': False}


def prepare(config):
    root = base_dir(config)
    if root.exists() and any(root.rglob('*')):
        raise FileExistsError('Fresh series has evidence or a manifest; no implicit replacement')
    plans = {name: plan_data(config, name) for name in ORDERS}
    for name, plan in plans.items():
        write_new(root / name / 'manifest.json', plan)
    return {name: sha(root / name / 'manifest.json') for name in ORDERS}


def verify_manifest(config, fresh, expected_hash):
    path = base_dir(config) / fresh / 'manifest.json'
    if sha(path) != expected_hash:
        raise ValueError('Manifest SHA-256 differs')
    manifest = json.loads(path.read_text())
    if manifest != plan_data(config, fresh):
        raise ValueError('Manifest/source reconstruction differs')
    return manifest


def phase_paths(config, fresh, condition, phase):
    folder = base_dir(config) / fresh / condition
    return folder, folder / (phase + '.claim.json'), folder / (phase + '.journal.jsonl'), folder / (phase + '.attempts.jsonl'), folder / (phase + '.records.jsonl')


def completed(config, fresh, condition, phase):
    _, claim, journal, attempts, records = phase_paths(config, fresh, condition, phase)
    if not all(p.exists() for p in (claim, journal, attempts, records)):
        return False
    events = [json.loads(x) for x in journal.read_text().splitlines()]
    return bool(events and events[-1].get('event') == 'phase_completed')


def require_order(manifest, condition):
    config, fresh = manifest['configuration_id'], manifest['pass']
    order = ORDERS[fresh]
    if condition not in order:
        raise ValueError('Unknown condition')
    for prior_pass in list(ORDERS)[:list(ORDERS).index(fresh)]:
        for prior_condition in ORDERS[prior_pass]:
            if not completed(config, prior_pass, prior_condition, 'development'):
                raise ValueError('Prior pass lacks closed development')
    for prior in order[:order.index(condition)]:
        if not completed(config, fresh, prior, 'development'):
            raise ValueError('Prior condition lacks closed development')


def runtime_check(codex=CODEX, runner=subprocess.run):
    if str(Path(codex).resolve()) != str(Path(CODEX).resolve()):
        raise RuntimeError('CLI path differs from frozen new-series path')
    env = single.clean_environment()
    auth = runner([codex, 'login', 'status'], env=env, capture_output=True, text=True)
    if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
        raise RuntimeError('ChatGPT subscription login required')
    version = runner([codex, '--version'], env=env, capture_output=True, text=True)
    if version.returncode or version.stdout.strip() != RUNTIME:
        raise RuntimeError('Exact CLI version changed')
    help_result = runner([codex, 'exec', '--help'], env=env, capture_output=True, text=True)
    flags = ('--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check',
             '--sandbox', '--json', '--color', '--cd', '--model', '--output-schema',
             '--output-last-message')
    if help_result.returncode or any(flag not in help_result.stdout for flag in flags):
        raise RuntimeError('CLI lacks frozen command controls')
    return env


def review_gate(manifest, condition, phase, manifest_hash, receipt_path, receipt_hash, now=None):
    receipt = Path(receipt_path)
    if not receipt.is_absolute() or receipt.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Review receipt must be private and outside public repository')
    if receipt.stat().st_mode & 0o077 or receipt.parent.stat().st_mode & 0o077:
        raise ValueError('Private receipt or directory permissions are too broad')
    if len(receipt_hash) != 64 or sha(receipt) != receipt_hash:
        raise ValueError('Review receipt SHA-256 differs')
    review = json.loads(receipt.read_text())
    expected = {'schema': REVIEW_SCHEMA, 'approved': True,
                'configuration_id': manifest['configuration_id'], 'pass': manifest['pass'],
                'condition': condition, 'phase': phase, 'manifest_sha256': manifest_hash,
                'controller_sha256': sha(CONTROLLER), 'model': manifest['model'],
                'effort': manifest['effort'], 'runtime': RUNTIME, 'cli_path': CODEX}
    if any(review.get(k) != v for k, v in expected.items()):
        raise ValueError('Root review controls or identity differ')
    quota = review.get('quota') or {}
    checked = datetime.fromisoformat(quota.get('checked_at_utc', '').replace('Z', '+00:00'))
    age = ((now or datetime.now(timezone.utc)) - checked).total_seconds()
    weekly = quota.get('weekly_remaining_percent')
    short = quota.get('five_hour_remaining_percent')
    def positive(value):
        return type(value) in (float, int) and 0 < value <= 100
    if (checked.tzinfo is None or not 0 <= age <= 300 or
            quota.get('source') != 'Codex get_usage_limits' or
            quota.get('ordinary_usage_allowed') is not True or
            quota.get('spend_control_reached') is not False or
            quota.get('credits_available') is not False or
            quota.get('unlimited_credits') is not False or
            quota.get('paid_overage_disabled') is not True or
            not positive(weekly) or (short is not None and not positive(short))):
        raise ValueError('Quota admission unavailable, stale or exhausted')
    if phase == 'development':
        inspection = base_dir(manifest['configuration_id']) / manifest['pass'] / condition / 'smoke-inspection.json'
        if not inspection.exists() or review.get('smoke_inspection_sha256') != sha(inspection):
            raise ValueError('Root review lacks exact inspected smoke')
    elif review.get('smoke_inspection_sha256') is not None:
        raise ValueError('Smoke review has unexpected inspection binding')


def attest(manifest, condition, phase, manifest_hash, receipt_hash):
    folder = base_dir(manifest['configuration_id']) / manifest['pass'] / condition
    value = {'schema': 'codex-fresh-admission-v1', 'status': 'admitted_before_dispatch',
             'dispatch_status': 'not_asserted', 'configuration_id': manifest['configuration_id'],
             'pass': manifest['pass'], 'condition': condition, 'phase': phase,
             'manifest_sha256': manifest_hash, 'controller_sha256': sha(CONTROLLER),
             'private_review_sha256': receipt_hash, 'model': manifest['model'],
             'effort': manifest['effort'], 'runtime': RUNTIME}
    if phase == 'development':
        value['smoke_inspection_sha256'] = sha(folder / 'smoke-inspection.json')
    write_new(folder / (phase + '.admission.json'), value)


def inspect(manifest, condition, note):
    if not note.strip():
        raise ValueError('Actual raw/model inspection note required')
    config, fresh = manifest['configuration_id'], manifest['pass']
    folder, claim, journal, attempts, records = phase_paths(config, fresh, condition, 'smoke')
    if not completed(config, fresh, condition, 'smoke'):
        raise ValueError('Smoke phase not complete')
    events = [json.loads(x) for x in journal.read_text().splitlines()]
    attempt_rows = [json.loads(x) for x in attempts.read_text().splitlines()]
    rows = [json.loads(x) for x in records.read_text().splitlines()]
    raw = folder / 'smoke.raw-0.json'
    if ([e['event'] for e in events] != ['phase_started', 'request_started', 'raw_saved', 'request_completed', 'phase_completed'] or
            len(attempt_rows) != 1 or len(rows) != 3 or
            attempt_rows[0]['status'] != 'ok' or any(r['status'] != 'ok' for r in rows) or
            [r['id'] for r in rows] != manifest['conditions'][condition]['smoke']['record_ids'] or
            sha(raw) != attempt_rows[0]['raw_sidecar_sha256']):
        raise ValueError('Smoke evidence is not three complete valid raw records')
    receipt = {'schema': 'codex-fresh-smoke-inspection-v1', 'inspection': 'accepted_unchanged',
               'configuration_id': config, 'pass': fresh, 'condition': condition, 'note': note,
               'claim_sha256': sha(claim), 'journal_sha256': sha(journal),
               'attempts_sha256': sha(attempts), 'records_sha256': sha(records),
               'raw_sha256': sha(raw), 'record_ids': [r['id'] for r in rows]}
    write_new(folder / 'smoke-inspection.json', receipt)
    return sha(folder / 'smoke-inspection.json')


def verify_inspection(manifest, condition):
    config, fresh = manifest['configuration_id'], manifest['pass']
    folder, claim, journal, attempts, records = phase_paths(config, fresh, condition, 'smoke')
    path = folder / 'smoke-inspection.json'
    value = json.loads(path.read_text())
    expected = {'claim_sha256': claim, 'journal_sha256': journal,
                'attempts_sha256': attempts, 'records_sha256': records,
                'raw_sha256': folder / 'smoke.raw-0.json'}
    if value.get('inspection') != 'accepted_unchanged' or any(value.get(k) != sha(v) for k, v in expected.items()):
        raise ValueError('Inspected smoke evidence changed')


def real_backend(cmd, prompt, env, cwd):
    proc = subprocess.run(cmd, input=prompt, env=env, cwd=cwd, text=True,
                          capture_output=True, timeout=TIMEOUT)
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr,
            'response': (cwd / 'response.json').read_text() if (cwd / 'response.json').exists() else ''}


def run_phase(manifest, condition, phase, manifest_hash, receipt_path, receipt_hash,
              codex=CODEX, backend=None, runtime=None, now=None):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    config, fresh = manifest['configuration_id'], manifest['pass']
    if manifest != plan_data(config, fresh):
        raise ValueError('Plan/source reconstruction differs')
    if sha(base_dir(config) / fresh / 'manifest.json') != manifest_hash:
        raise ValueError('Manifest changed')
    require_order(manifest, condition)
    if phase == 'development':
        verify_inspection(manifest, condition)
    folder, claim, journal_path, attempts_path, records_path = phase_paths(config, fresh, condition, phase)
    if any(folder.glob(phase + '.*')):
        raise FileExistsError('Phase already admitted, claimed or attempted; no replay')
    review_gate(manifest, condition, phase, manifest_hash, receipt_path, receipt_hash, now)
    env = (runtime or runtime_check)(codex)
    attest(manifest, condition, phase, manifest_hash, receipt_hash)
    write_new(claim, {'schema': 'codex-fresh-phase-claim-v1', 'pass': fresh,
                      'configuration_id': config, 'condition': condition, 'phase': phase,
                      'manifest_sha256': manifest_hash, 'admission_sha256': sha(folder / (phase + '.admission.json'))})
    requests = ([manifest['conditions'][condition]['smoke']] if phase == 'smoke'
                else manifest['conditions'][condition]['development'])
    inputs = {r['id']: r for r in input_rows()}
    with journal_path.open('x') as journal, attempts_path.open('x') as attempts, records_path.open('x') as records:
        line(journal, {'event': 'phase_started', 'pass': fresh, 'condition': condition, 'phase': phase})
        for req in requests:
            ids = req['record_ids']
            if (req['pass'], req['condition'], req['phase']) != (fresh, condition, phase):
                raise ValueError('Frozen request identity mismatch')
            if digest(req['request']['prompt']) != req['request_sha256'] or digest(json.dumps(req['request']['output_schema'], sort_keys=True)) != req['schema_sha256']:
                raise ValueError('Frozen prompt/schema hash mismatch')
            line(journal, {'event': 'request_started', 'batch_index': req['batch_index'], 'record_ids': ids})
            with tempfile.TemporaryDirectory(prefix='codex-fresh-', dir='/private/tmp') as temp:
                cwd = Path(temp)
                schema_path = cwd / 'schema.json'
                schema_path.write_text(json.dumps(req['request']['output_schema']))
                cmd = single.command(codex, manifest['model'], manifest['effort'], cwd, schema_path)
                started_utc = datetime.now(timezone.utc).isoformat()
                began = time.perf_counter()
                try:
                    result = (backend or real_backend)(cmd, req['request']['prompt'], env, cwd)
                except subprocess.TimeoutExpired as exc:
                    def decode(x): return x.decode(errors='replace') if isinstance(x, bytes) else (x or '')
                    result = {'returncode': None, 'stdout': decode(exc.stdout), 'stderr': decode(exc.stderr),
                              'response': (cwd / 'response.json').read_text() if (cwd / 'response.json').exists() else '',
                              'transport_error': 'TimeoutExpired'}
                except Exception as exc:
                    line(journal, {'event': 'phase_stopped', 'reason': 'unknown_transport',
                                   'batch_index': req['batch_index'], 'error_type': type(exc).__name__})
                    raise RuntimeError('Unknown attempted request; no replay') from exc
                elapsed = time.perf_counter() - began
                finished_utc = datetime.now(timezone.utc).isoformat()
                sidecar = folder / (phase + '.raw-' + str(req['batch_index']) + '.json')
                write_new(sidecar, {'returncode': result.get('returncode'), 'stdout': result.get('stdout', ''),
                                    'stderr': result.get('stderr', ''), 'response': result.get('response', ''),
                                    'transport_error': result.get('transport_error'), 'elapsed_seconds': elapsed,
                                    'started_utc': started_utc, 'finished_utc': finished_utc})
                line(journal, {'event': 'raw_saved', 'batch_index': req['batch_index'], 'raw_sha256': sha(sidecar)})
                parsed = single.parse_result(1 if result.get('transport_error') else result.get('returncode'),
                                             result.get('stdout', ''), result.get('response', ''))
                status = parsed['status']
                predictions = {}
                if status not in ('service_error', 'isolation_violation'):
                    try:
                        predictions = batch.parse_batch(result.get('response', ''), [inputs[i] for i in ids])
                        status = 'ok'
                    except (ValueError, TypeError):
                        status = 'invalid_output'
                usage = parsed.get('usage')
                attempt = {'schema': 'codex-fresh-attempt-v1', 'configuration_id': config,
                           'pass': fresh, 'condition': condition, 'phase': phase,
                           'batch_index': req['batch_index'], 'record_order': ids,
                           'request': req['request'], 'request_sha256': req['request_sha256'],
                           'schema_sha256': req['schema_sha256'], 'manifest_sha256': manifest_hash,
                           'source_bindings_sha256': req['source_bindings_sha256'],
                           'requested_model': manifest['model'], 'returned_model': None,
                           'effort': manifest['effort'], 'cli_path': codex, 'cli_version': RUNTIME,
                           'controller_timeout_seconds': TIMEOUT, 'auth_mode': 'ChatGPT',
                           'command': cmd, 'reference_labels_read': False, 'status': status,
                           'batch_predictions': predictions if status == 'ok' else {},
                           'raw_sidecar_sha256': sha(sidecar), 'elapsed_seconds': elapsed,
                           'started_utc': started_utc, 'finished_utc': finished_utc,
                           'raw_events': parsed.get('raw_events'), 'usage': usage,
                           'input_tokens': usage.get('input_tokens') if isinstance(usage, dict) else None,
                           'output_tokens': usage.get('output_tokens') if isinstance(usage, dict) else None,
                           'cost_usd': None, 'cost_observation': 'not_exposed_by_subscription_cli',
                           'requested_seed': None, 'effective_seed': None,
                           'model_revision': None, 'hardware': None,
                           'response_diagnostic': None,
                           'timing_kind': 'client_batch_duration_not_pure_inference'}
                diagnostic = prompt_admission.audit_response({**attempt, **parsed, 'status': status}, 'codex_batch_v1', 258400)
                attempt['response_diagnostic'] = diagnostic
                if not diagnostic['passed']:
                    status = attempt['status'] = 'service_error'
                    attempt['batch_predictions'] = {}
                line(attempts, attempt)
                line(journal, {'event': 'request_completed', 'batch_index': req['batch_index'],
                               'status': status, 'raw_sha256': sha(sidecar)})
                for position, rid in enumerate(ids):
                    line(records, {'id': rid, 'pass': fresh, 'condition': condition, 'phase': phase,
                                   'batch_index': req['batch_index'], 'batch_position': position,
                                   'status': status, 'prediction': attempt['batch_predictions'].get(rid),
                                   'request_sha256': req['request_sha256'], 'input_sha256': digest(inputs[rid]['feedback']),
                                   'requested_model': manifest['model'], 'effort': manifest['effort'],
                                   'elapsed_seconds': elapsed / len(ids),
                                   'timing_kind': 'amortized_batch_share_not_individual_latency'})
                # Keep the frozen Codex batch policy: retain this batch's known
                # positions and stop before sending the next batch. No repair.
                if status != 'ok':
                    line(journal, {'event': 'phase_stopped', 'reason': status, 'batch_index': req['batch_index']})
                    raise RuntimeError('Phase stopped on first non-ok request; no replay')
        line(journal, {'event': 'phase_completed', 'request_count': len(requests),
                       'record_count': 3 if phase == 'smoke' else 60})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, choices=CONFIGS)
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('prepare')
    actions.add_parser('runtime-check')
    for action in ('smoke', 'inspect', 'development'):
        sub = actions.add_parser(action)
        sub.add_argument('--pass', dest='fresh', required=True, choices=ORDERS)
        sub.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        sub.add_argument('--manifest-sha256', required=True)
        if action == 'inspect':
            sub.add_argument('--note', required=True)
        else:
            sub.add_argument('--review-receipt', required=True)
            sub.add_argument('--review-sha256', required=True)
    args = parser.parse_args(argv)
    if args.action == 'prepare':
        for name, value in prepare(args.config).items(): print(name, value)
    elif args.action == 'runtime-check':
        runtime_check()
        print(RUNTIME, 'ChatGPT subscription controls present')
    else:
        manifest = verify_manifest(args.config, args.fresh, args.manifest_sha256)
        if args.action == 'inspect':
            print(inspect(manifest, args.condition, args.note))
        else:
            run_phase(manifest, args.condition, args.action, args.manifest_sha256,
                      args.review_receipt, args.review_sha256)


if __name__ == '__main__':
    main()
