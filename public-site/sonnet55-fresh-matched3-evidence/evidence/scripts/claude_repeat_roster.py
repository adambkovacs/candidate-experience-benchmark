#!/usr/bin/env python3
"""Offline-planned Claude subscription repeats for the remaining batch-10 roster.

No inference occurs during roster, prepare, or verify. Smoke and development
require a frozen manifest, a phase-specific root review, and a fresh private
subscription preflight whose contents never enter public evidence.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from claude_batch_benchmark import batch_schema, isolation_ok, parse_batch_result
from development_benchmark import ROOT, digest, read_rows

RUNTIME = '2.1.282 (Claude Code)'
HISTORICAL_RUNTIME = '2.1.280 (Claude Code)'
CLI = Path('/Users/adamkovacs/.local/share/claude/versions/2.1.282')
TIMEOUT = 600
BASE_ROOT = ROOT / 'results/repeatability-v1/claude-roster-v1'
COVERAGE = 'results/repeatability-v1/coverage.json'
PAIRS = 'results/prompt-comparison-v1-2026-09-24/paired-reports'
PREPARATION = 'results/prompt-comparison-v1-2026-09-24/subscription-preparation-v2'
INPUTS = 'data/pilot/inputs.jsonl'
ROSTER = {
    'fable51-low-phase2-batch10-p0': ('claude-fable-5-1', 'low'),
    'fable51-medium-phase2-batch10-p0': ('claude-fable-5-1', 'medium'),
    'fable51-high-phase2-batch10-p0': ('claude-fable-5-1', 'high'),
    'fable51-xhigh-phase2-batch10-p0': ('claude-fable-5-1', 'xhigh'),
    'opus5-low-phase2-batch10-p0': ('claude-opus-5', 'low'),
    'opus5-medium-phase2-batch10-p0': ('claude-opus-5', 'medium'),
    'opus5-high-phase2-batch10-p0': ('claude-opus-5', 'high'),
    'opus5-xhigh-phase2-batch10-p0': ('claude-opus-5', 'xhigh'),
    'opus55-low-batch10': ('claude-opus-5-5', 'low'),
    'opus55-high-batch10': ('claude-opus-5-5', 'high'),
    'opus55-xhigh-batch10': ('claude-opus-5-5', 'xhigh'),
    'sonnet5-low-first-pass-phase2-batch10-p0': ('claude-sonnet-5', 'low'),
    'sonnet5-medium-phase2-batch10-p0': ('claude-sonnet-5', 'medium'),
    'sonnet5-high-phase2-batch10-p0': ('claude-sonnet-5', 'high'),
    'sonnet5-xhigh-phase2-batch10-p0': ('claude-sonnet-5', 'xhigh'),
}


def mechanics():
    """Load a private module instance; never mutate the completed Opus lane."""
    source = ROOT / 'scripts/claude_repeat_study.py'
    spec = importlib.util.spec_from_file_location('_claude_roster_mechanics', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': str(relative), 'sha256': sha(path)}


def read_source(binding):
    actual = source(binding['path'])
    if actual != binding:
        raise ValueError('Frozen source changed: ' + str(binding['path']))
    return (ROOT / binding['path']).read_bytes()


def base(config):
    if config not in ROSTER:
        raise ValueError('Configuration outside eligible Claude roster')
    return BASE_ROOT / config


def orders(historical):
    if historical not in (['P0', 'P1', 'P2'], ['P0', 'P2', 'P1']):
        raise ValueError('Historical Claude condition order differs')
    return {'repeat2': historical[1:] + historical[:1],
            'repeat3': historical[2:] + historical[:2]}


def plan_data(config, repeat):
    if config not in ROSTER or repeat not in ('repeat2', 'repeat3'):
        raise ValueError('Configuration or repeat outside eligible Claude roster')
    model, effort = ROSTER[config]
    coverage = json.loads((ROOT / COVERAGE).read_text())
    matches = [g for g in coverage['groups'] if g['id'] == config]
    if len(matches) != 1:
        raise ValueError('Coverage group missing or duplicated')
    group = matches[0]
    historical = group.get('observed_condition_order')
    rotation = orders(historical)
    if (group.get('route') != 'Claude subscription' or group.get('model') != model or
            group.get('historical_triple_status') != 'eligible_first_pass' or
            any(group['condition_status'].get(c) != 'eligible_first_pass'
                for c in ('P0', 'P1', 'P2'))):
        raise ValueError('Historical Claude eligibility changed')
    pair_path = f'{PAIRS}/{config}/paired-manifest.json'
    pair = json.loads((ROOT / pair_path).read_text())
    controls = pair['controls']
    if (pair.get('parent_baseline_id') != config or
            controls.get('requested_model') != model or controls.get('effort') != effort or
            controls.get('workflow') != 'batch10' or
            controls.get('cli_version') != HISTORICAL_RUNTIME or
            controls.get('auth_method') != 'claude.ai' or
            controls.get('controller_retries') != 0 or
            controls.get('extra_usage_disabled_operator_verified') is not True):
        raise ValueError('Historical Claude controls changed')
    inputs = read_rows(ROOT / INPUTS)
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if (len(inputs) != 60 or [r.get('id') for r in inputs] != ids or
            any(set(r) != {'id', 'feedback'} for r in inputs)):
        raise ValueError('Claude input membership or isolation differs')
    prep = f'{PREPARATION}/{config}'
    paths = [COVERAGE, pair_path, INPUTS, 'schemas/judgments.schema.json',
             'scripts/claude_batch_benchmark.py', 'scripts/claude_benchmark.py',
             'scripts/claude_repeat_study.py', 'scripts/claude_repeat_roster.py',
             f'{prep}/execution-manifest.json']
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        evidence = pair['conditions'][condition]['request_evidence']
        if source(evidence['file'])['sha256'] != evidence['sha256']:
            raise ValueError('Historical Claude attempt hash changed')
        old = [json.loads(line) for line in (ROOT / evidence['file']).read_text().splitlines()]
        if len(old) != 6:
            raise ValueError('Expected six historical Claude batches')
        paths.append(evidence['file'])
        instruction = f'{prep}/{condition}-instruction.txt'
        paths.append(instruction)
        system = (ROOT / instruction).read_text()
        development = []
        for index, attempt in enumerate(old):
            members = inputs[index * 10:(index + 1) * 10]
            member_ids = [r['id'] for r in members]
            payload = json.dumps({'records': [{'id': r['id'], 'feedback': r['feedback']}
                                               for r in members]})
            request = {'system': system, 'input': json.loads(payload),
                       'schema': batch_schema(member_ids)}
            if (attempt.get('request') != request or attempt.get('ids') != member_ids or
                    attempt.get('status') != 'ok' or attempt.get('requested_model') != model or
                    attempt.get('effort') != effort or attempt.get('batch_size') != 10 or
                    attempt.get('auth_method') != 'claude.ai' or
                    attempt.get('input_sha256') != digest(payload) or
                    attempt.get('policy_sha256') != digest(system) or
                    attempt.get('schema_sha256') != digest(json.dumps(request['schema'], sort_keys=True))):
                raise ValueError('Historical Claude request, outcome, or parsing controls differ')
            parsed = parse_batch_result(attempt.get('raw_response'),
                                        attempt.get('exit_code'), member_ids)
            if (parsed.get('status') != 'ok' or parsed.get('prediction') !=
                    attempt.get('prediction') or not isolation_ok(attempt)):
                raise ValueError('Historical Claude batch cannot be reproduced from raw output')
            if condition != 'P0':
                prepared = f'{prep}/{condition}-request-{index + 1:02d}.json'
                paths.append(prepared)
                if json.loads((ROOT / prepared).read_text())['request'] != request:
                    raise ValueError('Prepared Claude request differs from historical request')
            development.append({'batch_index': index + 1, 'record_ids': member_ids,
                                'request': request, 'input_text': payload,
                                'historical_attempt_sha256': evidence['sha256']})
        smoke_ids = ids[:3]
        smoke_payload = json.dumps({'records': [{'id': r['id'], 'feedback': r['feedback']}
                                                 for r in inputs[:3]]})
        smoke = {'batch_index': 0, 'record_ids': smoke_ids,
                 'request': {'system': system, 'input': json.loads(smoke_payload),
                             'schema': batch_schema(smoke_ids)},
                 'input_text': smoke_payload}
        conditions[condition] = {'historical_attempts': source(evidence['file']),
                                 'smoke': smoke, 'development': development}
    return {'schema': 'claude-repeat-roster-v1', 'configuration_id': config,
            'repeat': repeat, 'historical_pass_order': historical,
            'condition_order': rotation[repeat], 'model': model, 'effort': effort,
            'batch_size': 10, 'timeout_seconds': TIMEOUT, 'runtime_required': RUNTIME,
            'historical_runtime': HISTORICAL_RUNTIME,
            'runtime_limitation': 'CLI patch differs from historical pass; hidden rendering and serving revision unavailable',
            'seed_policy': 'unchanged CLI default; seed unavailable',
            'reference_labels_read': False,
            'source_bindings': [source(p) for p in dict.fromkeys(paths)],
            'conditions': conditions, 'inference_performed': False,
            'execution': 'fresh isolated CLI context per batch; zero controller retries; stop on first non-ok or ambiguous attempt'}


def prepare(config):
    for repeat in ('repeat2', 'repeat3'):
        path = base(config) / repeat / 'manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            out.write(json.dumps(plan_data(config, repeat), indent=2, ensure_ascii=False) + '\n')
            out.flush()
            os.fsync(out.fileno())
        print(repeat, sha(path))


def verify_manifest(config, repeat, expected_hash):
    path = base(config) / repeat / 'manifest.json'
    if sha(path) != expected_hash:
        raise ValueError('Manifest hash mismatch')
    manifest = json.loads(path.read_text())
    for binding in manifest['source_bindings']:
        read_source(binding)
    if manifest != plan_data(config, repeat):
        raise ValueError('Manifest differs from frozen reconstruction')
    return manifest


def phase_paths(config, repeat, condition, phase):
    folder = base(config) / repeat / condition
    return (folder, folder / f'{phase}.claim.json', folder / f'{phase}.attempts.jsonl',
            folder / f'{phase}.records.jsonl', folder / f'{phase}.journal.jsonl')


def completed(config, repeat, condition, phase):
    _, claim, attempts, records, journal = phase_paths(config, repeat, condition, phase)
    if not all(p.exists() for p in (claim, attempts, records, journal)):
        return False
    lines = [json.loads(line) for line in journal.read_text().splitlines()]
    return bool(lines and lines[-1].get('event') == 'phase_completed')


def require_order(manifest, condition):
    config, repeat = manifest['configuration_id'], manifest['repeat']
    order = manifest['condition_order']
    if condition not in order:
        raise ValueError('Condition outside frozen order')
    if repeat == 'repeat3' and not all(completed(config, 'repeat2', c, 'development')
                                       for c in orders(manifest['historical_pass_order'])['repeat2']):
        raise ValueError('Repeat two incomplete')
    for earlier in order[:order.index(condition)]:
        if not completed(config, repeat, earlier, 'development'):
            raise ValueError('Previous condition incomplete: ' + earlier)


def private_preflight(path, expected_hash, old):
    candidate = Path(path)
    if not candidate.is_absolute():
        raise ValueError('Private preflight requires an absolute path')
    try:
        candidate.resolve().relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError('Private subscription preflight cannot live in public repository')
    return old.preflight(candidate, expected_hash)


def root_review(path, expected_hash, manifest, preflight_hash):
    candidate = Path(path)
    if not candidate.is_absolute() or sha(candidate) != expected_hash:
        raise ValueError('Root review path/hash mismatch')
    review = json.loads(candidate.read_text())
    allowed = {'schema', 'approved', 'configuration_id', 'repeat', 'manifest_sha256',
               'controller_sha256', 'mechanics_sha256', 'private_preflight_sha256',
               'cli_path', 'cli_version', 'approved_phases', 'review_note'}
    if set(review) != allowed:
        raise ValueError('Public root review must contain admission hashes only')
    if (review.get('schema') != 'claude-repeat-roster-root-review-v1' or
            review.get('approved') is not True or
            review.get('configuration_id') != manifest['configuration_id'] or
            review.get('repeat') != manifest['repeat'] or
            review.get('manifest_sha256') != sha(base(manifest['configuration_id']) /
                                                manifest['repeat'] / 'manifest.json') or
            review.get('controller_sha256') != sha(ROOT / 'scripts/claude_repeat_roster.py') or
            review.get('mechanics_sha256') != sha(ROOT / 'scripts/claude_repeat_study.py') or
            review.get('private_preflight_sha256') != preflight_hash or
            review.get('cli_path') != str(CLI) or review.get('cli_version') != RUNTIME or
            not isinstance(review.get('approved_phases'), list) or
            not str(review.get('review_note', '')).strip()):
        raise ValueError('Claude roster root review differs')
    return review


def inspect(manifest, condition, note):
    config, repeat = manifest['configuration_id'], manifest['repeat']
    folder, _, attempts, records, journal = phase_paths(config, repeat, condition, 'smoke')
    if not note.strip() or not completed(config, repeat, condition, 'smoke'):
        raise ValueError('Completed smoke and inspection note required')
    rows = [json.loads(line) for line in records.read_text().splitlines()]
    if len(rows) != 3 or any(row.get('status') != 'ok' for row in rows):
        raise ValueError('Three valid smoke records required')
    receipt = folder / 'smoke-inspection.json'
    with receipt.open('x') as out:
        json.dump({'inspection': 'accepted_unchanged', 'note': note,
                   'attempts_sha256': sha(attempts), 'records_sha256': sha(records),
                   'journal_sha256': sha(journal),
                   'inspected_utc': dt.datetime.now(dt.timezone.utc).isoformat()}, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())


def run_phase(manifest, condition, phase, cli, review_path, review_hash,
              preflight_path, preflight_hash):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    config, repeat = manifest['configuration_id'], manifest['repeat']
    frozen = base(config) / repeat / 'manifest.json'
    if manifest != verify_manifest(config, repeat, sha(frozen)):
        raise ValueError('Unverified Claude roster manifest')
    require_order(manifest, condition)
    folder, claim, attempts_path, records_path, journal_path = phase_paths(
        config, repeat, condition, phase)
    if any(p.exists() for p in (claim, attempts_path, records_path, journal_path)):
        raise FileExistsError('Existing phase evidence requires review; no retry')
    if phase == 'development':
        smoke_folder, _, smoke_attempts, smoke_records, smoke_journal = phase_paths(
            config, repeat, condition, 'smoke')
        inspection = smoke_folder / 'smoke-inspection.json'
        if not inspection.exists():
            raise ValueError('Inspected smoke required')
        saved = json.loads(inspection.read_text())
        if saved.get('inspection') != 'accepted_unchanged' or any(
                saved.get(key) != sha(path) for key, path in (
                    ('attempts_sha256', smoke_attempts), ('records_sha256', smoke_records),
                    ('journal_sha256', smoke_journal))):
            raise ValueError('Smoke evidence changed after inspection')
    review = root_review(review_path, review_hash, manifest, preflight_hash)
    if {'condition': condition, 'phase': phase} not in review['approved_phases']:
        raise ValueError('Root review did not admit this phase')
    old = mechanics()
    private_preflight(preflight_path, preflight_hash, old)
    if Path(cli).resolve() != CLI.resolve() or not CLI.is_file():
        raise ValueError('Claude CLI path differs from pinned installation')
    env = old.clean_environment()
    with tempfile.TemporaryDirectory(dir='/private/tmp') as cwd:
        auth = subprocess.run([cli, '--safe-mode', 'auth', 'status'], cwd=cwd, env=env,
                              capture_output=True, text=True, check=True, timeout=30)
        old.require_subscription(json.loads(auth.stdout))
        version = subprocess.run([cli, '--version'], cwd=cwd, env=env,
                                 capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    if version != RUNTIME:
        raise ValueError('Claude CLI version differs from pinned runtime')
    folder.mkdir(parents=True, exist_ok=True)
    manifest_hash = sha(base(config) / repeat / 'manifest.json')
    with claim.open('x') as out:
        json.dump({'configuration_id': config, 'repeat': repeat, 'condition': condition,
                   'phase': phase, 'manifest_sha256': manifest_hash,
                   'root_review_sha256': review_hash,
                   'private_preflight_sha256': preflight_hash,
                   'cli_version': version,
                   'claimed_utc': dt.datetime.now(dt.timezone.utc).isoformat()}, out)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    requests = ([manifest['conditions'][condition]['smoke']] if phase == 'smoke' else
                manifest['conditions'][condition]['development'])
    with attempts_path.open('x') as attempts, records_path.open('x') as records, journal_path.open('x') as journal:
        old.durable(journal, {'event': 'phase_started', 'repeat': repeat,
                              'condition': condition, 'phase': phase})
        for item in requests:
            ids, request, payload = item['record_ids'], item['request'], item['input_text']
            if request['input'] != json.loads(payload):
                raise ValueError('Manifest payload changed')
            cmd = old.command(cli, manifest['model'], manifest['effort'],
                              request['system'], request['schema']) + ['--verbose']
            started = dt.datetime.now(dt.timezone.utc).isoformat()
            old.durable(journal, {'event': 'dispatch_intent', 'batch_index': item['batch_index'],
                                  'record_ids': ids, 'started_utc': started})
            attempt = {'configuration_id': config, 'repeat': repeat, 'condition': condition,
                       'phase': phase, 'batch_index': item['batch_index'], 'ids': ids,
                       'batch_size': len(ids), 'workflow': 'batch10',
                       'requested_model': manifest['model'], 'effort': manifest['effort'],
                       'cli_version': version, 'request': request,
                       'policy_sha256': digest(request['system']),
                       'input_sha256': digest(payload),
                       'schema_sha256': digest(json.dumps(request['schema'], sort_keys=True)),
                       'auth_method': 'claude.ai', 'controller_retries': 0,
                       'cli_internal_retries': 'not exposed', 'started_utc': started}
            start = time.perf_counter()
            try:
                with tempfile.TemporaryDirectory(dir='/private/tmp') as cwd:
                    result = subprocess.run(cmd, input=payload, cwd=cwd, env=env, text=True,
                                            capture_output=True, timeout=TIMEOUT)
                raw_path = folder / f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
                old.save_raw_capture(raw_path, attempt, result.stdout, result.stderr,
                                     result.returncode)
                attempt['exit_code'] = result.returncode
                attempt['stderr'] = old.capture_text(result.stderr)
                body = json.loads(result.stdout)
                attempt.update(old.parse_batch_result(body, result.returncode, ids))
                attempt['raw_events'] = old.safe_diagnostic(body)
                if not old.isolation_ok(attempt):
                    attempt.update(status='service_error',
                                   error_type='IsolationIdentityOrBillingGuard')
            except (subprocess.SubprocessError, ValueError, OSError) as exc:
                attempt.update(status='service_error', error_type=type(exc).__name__)
                if isinstance(exc, subprocess.TimeoutExpired):
                    raw_path = folder / f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
                    old.save_raw_capture(raw_path, attempt, exc.stdout, exc.stderr,
                                         None, timed_out=True)
                    attempt['partial_stdout'] = old.capture_text(exc.stdout)
                    attempt['partial_stderr'] = old.capture_text(exc.stderr)
            attempt['elapsed_seconds'] = time.perf_counter() - start
            old.durable(attempts, attempt)
            predictions = ({r['id']: {k: v for k, v in r.items() if k != 'id'}
                            for r in attempt.get('prediction', {}).get('records', [])}
                           if attempt['status'] == 'ok' else {})
            for pos, rid in enumerate(ids):
                old.durable(records, {'id': rid, 'status': attempt['status'],
                                      'prediction': predictions.get(rid), 'repeat': repeat,
                                      'condition': condition, 'phase': phase,
                                      'batch_index': item['batch_index'],
                                      'batch_position': pos + 1, 'batch_record_ids': ids,
                                      'requested_model': manifest['model'],
                                      'effort': manifest['effort'],
                                      'elapsed_seconds': attempt['elapsed_seconds'] / len(ids),
                                      'timing_kind': 'amortized_batch_share_not_individual_latency'})
            old.durable(journal, {'event': 'request_completed',
                                  'batch_index': item['batch_index'],
                                  'status': attempt['status'],
                                  'completed_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
            if attempt['status'] != 'ok':
                old.durable(journal, {'event': 'phase_stopped',
                                      'reason': attempt['status'],
                                      'batch_index': item['batch_index']})
                raise RuntimeError('Stopped on first non-ok batch; no retry')
        old.durable(journal, {'event': 'phase_completed', 'request_count': len(requests),
                              'record_count': 3 if phase == 'smoke' else 60})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('roster')
    for action in ('prepare', 'verify', 'inspect', 'smoke', 'development'):
        p = sub.add_parser(action)
        p.add_argument('--config', required=True, choices=tuple(ROSTER))
        if action != 'prepare':
            p.add_argument('--repeat', required=True, choices=('repeat2', 'repeat3'))
            p.add_argument('--manifest-sha256', required=True)
        if action in ('inspect', 'smoke', 'development'):
            p.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        if action == 'inspect':
            p.add_argument('--note', required=True)
        if action in ('smoke', 'development'):
            p.add_argument('--claude', required=True)
            p.add_argument('--root-review', required=True)
            p.add_argument('--root-review-sha256', required=True)
            p.add_argument('--preflight-receipt', required=True)
            p.add_argument('--preflight-sha256', required=True)
    args = parser.parse_args(argv)
    if args.action == 'roster':
        for config, (model, effort) in ROSTER.items():
            print(config, model, effort)
        return
    if args.action == 'prepare':
        prepare(args.config)
        return
    manifest = verify_manifest(args.config, args.repeat, args.manifest_sha256)
    if args.action == 'verify':
        print('verified')
    elif args.action == 'inspect':
        inspect(manifest, args.condition, args.note)
    else:
        run_phase(manifest, args.condition, args.action, args.claude,
                  args.root_review, args.root_review_sha256,
                  args.preflight_receipt, args.preflight_sha256)


if __name__ == '__main__':
    main()
