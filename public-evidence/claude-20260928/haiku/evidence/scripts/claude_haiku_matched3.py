#!/usr/bin/env python3
"""Separate, offline-planned three-pass Haiku subscription repeat lane."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from claude_benchmark import clean_environment, command, require_subscription, safe_diagnostic
from claude_batch_benchmark import batch_schema, isolation_ok, parse_batch_result
from development_benchmark import ROOT, digest, read_rows
import claude_repeat_roster as roster

CONFIG = 'haiku45-fresh-matched3-batch10'
HISTORICAL = 'haiku45-not_applicable-phase2-batch10-p0'
MODEL = 'claude-haiku-4-5-20251001'
EFFORT = 'not_applicable'
RUNTIME = roster.RUNTIME
CLI = roster.CLI
TIMEOUT = roster.TIMEOUT
BASE = ROOT / 'results/repeatability-v1/claude-haiku-fresh-matched3'
ORDERS = {'pass1': ['P0', 'P1', 'P2'], 'pass2': ['P1', 'P2', 'P0'],
          'pass3': ['P2', 'P0', 'P1']}
PREP = f'results/prompt-comparison-v1-2026-09-24/subscription-preparation-v1/{HISTORICAL}'
ORIGINAL = f'results/prompt-comparison-v1-2026-09-24/runs/{HISTORICAL}'
SUFFIX = (f'results/prompt-comparison-v1-2026-09-24/'
          f'subscription-suffix-continuation-v2-haiku/runs/{HISTORICAL}/P1')
RECONCILIATION = (f'results/prompt-comparison-v1-2026-09-24/'
                  f'subscription-suffix-continuation-v2-haiku/reconciliation-v1/{HISTORICAL}-P1.json')
P0_ATTEMPTS = f'results/subscription-batch-p0-2026-09-23/{HISTORICAL}/development.jsonl.batches.jsonl'
P2_ATTEMPTS = f'{ORIGINAL}/P2/development.jsonl.batches.jsonl'
P1_ATTEMPTS = f'{ORIGINAL}/P1/development.jsonl.batches.jsonl'
P1_SUFFIX_ATTEMPTS = f'{SUFFIX}/development-suffix.jsonl.batches.jsonl'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_bound(binding):
    if source(binding['path']) != binding:
        raise ValueError('Frozen source changed: ' + binding['path'])


def rows_of(relative):
    return [json.loads(line) for line in (ROOT / relative).read_text().splitlines() if line.strip()]


def _historical_requests(inputs, condition, instruction):
    if condition == 'P0':
        paths = [P0_ATTEMPTS]
    elif condition == 'P1':
        paths = [P1_ATTEMPTS, P1_SUFFIX_ATTEMPTS]
    else:
        paths = [P2_ATTEMPTS]
    old = [attempt for path in paths for attempt in rows_of(path)]
    if len(old) != 6:
        raise ValueError('Historical Haiku batch membership differs')
    by_ids = {tuple(a.get('ids', [])): a for a in old}
    if len(by_ids) != 6:
        raise ValueError('Historical Haiku batch membership duplicated')
    development = []
    for index in range(6):
        members = inputs[index * 10:(index + 1) * 10]
        ids = [row['id'] for row in members]
        payload = json.dumps({'records': [{'id': row['id'], 'feedback': row['feedback']}
                                          for row in members]})
        request = {'system': instruction, 'input': json.loads(payload),
                   'schema': batch_schema(ids)}
        previous = by_ids.get(tuple(ids))
        if (previous is None or previous.get('request') != request or
                previous.get('requested_model') != MODEL or
                previous.get('effort') != EFFORT or previous.get('batch_size') != 10 or
                previous.get('auth_method') != 'claude.ai' or
                previous.get('input_sha256') != digest(payload) or
                previous.get('policy_sha256') != digest(instruction) or
                previous.get('schema_sha256') != digest(json.dumps(request['schema'], sort_keys=True))):
            raise ValueError('Historical Haiku request or controls differ')
        if condition == 'P1':
            expected = 'service_error' if index == 1 else 'ok'
            if previous.get('status') != expected:
                raise ValueError('Historical Haiku P1 failure lineage differs')
            if index == 1 and (previous.get('error_type') != 'IsolationIdentityOrBillingGuard' or
                    previous.get('exit_code') != 1 or
                    previous.get('raw_response', {}).get('structured_output') is not None or
                    previous.get('raw_response', {}).get('is_error') is not True or
                    'ENOTFOUND' not in previous.get('raw_response', {}).get('result', '')):
                raise ValueError('Historical Haiku transport failure differs')
        elif previous.get('status') != 'ok':
            raise ValueError('Historical Haiku successful request differs')
        if condition != 'P0':
            prepared = f'{PREP}/{condition}-request-{index + 1:02d}.json'
            if json.loads((ROOT / prepared).read_text())['request'] != request:
                raise ValueError('Prepared Haiku request differs')
        development.append({'batch_index': index + 1, 'record_ids': ids,
                            'request': request, 'input_text': payload})
    return development, paths


def plan_data(pass_name):
    if pass_name not in ORDERS:
        raise ValueError('Unknown Haiku pass')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if (len(inputs) != 60 or [r.get('id') for r in inputs] != ids or
            any(set(row) != {'id', 'feedback'} for row in inputs)):
        raise ValueError('Haiku input membership or isolation differs')
    reconciliation = json.loads((ROOT / RECONCILIATION).read_text())
    if (reconciliation.get('counts') != {'original_valid': 10,
                                         'original_failed_attempted': 10,
                                         'suffix_valid': 40,
                                         'suffix_failed_attempted': 0,
                                         'never_sent': 0} or
            reconciliation.get('valid_prediction_count') != 50):
        raise ValueError('Historical Haiku failure accounting differs')
    paths = ['data/pilot/inputs.jsonl', 'schemas/judgments.schema.json',
             'scripts/claude_benchmark.py', 'scripts/claude_batch_benchmark.py',
             'scripts/claude_repeat_study.py', 'scripts/claude_repeat_roster.py',
             'scripts/claude_haiku_matched3.py', f'{PREP}/execution-manifest.json',
             RECONCILIATION, f'{ORIGINAL}/P1/development.jsonl',
             f'{ORIGINAL}/P1/development.jsonl.attempts.jsonl']
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        instruction_path = f'{PREP}/{condition}-instruction.txt'
        instruction = (ROOT / instruction_path).read_text()
        development, historical_paths = _historical_requests(inputs, condition, instruction)
        paths.extend([instruction_path, *historical_paths])
        if condition != 'P0':
            paths.extend(f'{PREP}/{condition}-request-{n:02d}.json' for n in range(1, 7))
        first = inputs[:3]
        smoke_ids = [r['id'] for r in first]
        smoke_payload = json.dumps({'records': [{'id': r['id'], 'feedback': r['feedback']}
                                                for r in first]})
        smoke = {'batch_index': 0, 'record_ids': smoke_ids,
                 'request': {'system': instruction, 'input': json.loads(smoke_payload),
                             'schema': batch_schema(smoke_ids)},
                 'input_text': smoke_payload}
        conditions[condition] = {'smoke': smoke, 'development': development,
                                 'historical_attempts': [source(p) for p in historical_paths]}
    return {'schema': 'claude-haiku-fresh-matched3-v1', 'configuration_id': CONFIG,
            'historical_configuration_id': HISTORICAL, 'pass': pass_name,
            'condition_order': ORDERS[pass_name], 'model': MODEL, 'effort': EFFORT,
            'batch_size': 10, 'timeout_seconds': TIMEOUT,
            'runtime_required': RUNTIME, 'historical_runtime': '2.1.280 (Claude Code)',
            'runtime_limitation': 'New matched series uses CLI 2.1.282; hidden rendering and serving revision unavailable',
            'seed_policy': 'unchanged CLI default; seed unavailable',
            'historical_disposition': 'Preserve original P1 ten attempted ENOTFOUND failures separately; no replay',
            'reference_labels_read': False, 'source_bindings': [source(p) for p in dict.fromkeys(paths)],
            'conditions': conditions, 'inference_performed': False,
            'execution': 'fresh isolated CLI context per batch; zero controller retries; stop on first non-ok or ambiguous attempt'}


def prepare():
    for pass_name in ORDERS:
        path = BASE / pass_name / 'manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            out.write(json.dumps(plan_data(pass_name), indent=2, ensure_ascii=False) + '\n')
            out.flush(); os.fsync(out.fileno())
        print(pass_name, sha(path))


def verify_manifest(pass_name, expected_hash):
    path = BASE / pass_name / 'manifest.json'
    if sha(path) != expected_hash:
        raise ValueError('Manifest hash mismatch')
    manifest = json.loads(path.read_text())
    for binding in manifest['source_bindings']:
        read_bound(binding)
    if manifest != plan_data(pass_name):
        raise ValueError('Manifest differs from frozen reconstruction')
    return manifest


def phase_paths(pass_name, condition, phase):
    folder = BASE / pass_name / condition
    return (folder, folder / f'{phase}.claim.json', folder / f'{phase}.attempts.jsonl',
            folder / f'{phase}.records.jsonl', folder / f'{phase}.journal.jsonl')


def completed(pass_name, condition, phase):
    _, claim, attempts, records, journal = phase_paths(pass_name, condition, phase)
    if not all(p.exists() for p in (claim, attempts, records, journal)):
        return False
    lines = [json.loads(line) for line in journal.read_text().splitlines()]
    return bool(lines and lines[-1].get('event') == 'phase_completed')


def require_order(manifest, condition):
    pass_name = manifest['pass']
    order = manifest['condition_order']
    if condition not in order:
        raise ValueError('Condition outside frozen order')
    if pass_name != 'pass1':
        previous = 'pass1' if pass_name == 'pass2' else 'pass2'
        if not all(completed(previous, c, 'development') for c in ORDERS[previous]):
            raise ValueError('Previous Haiku pass incomplete')
    for earlier in order[:order.index(condition)]:
        if not completed(pass_name, earlier, 'development'):
            raise ValueError('Previous condition incomplete: ' + earlier)


def root_review(path, expected_hash, manifest, preflight_hash):
    candidate = Path(path)
    if not candidate.is_absolute() or sha(candidate) != expected_hash:
        raise ValueError('Root review path/hash mismatch')
    review = json.loads(candidate.read_text())
    allowed = {'schema', 'approved', 'configuration_id', 'pass', 'manifest_sha256',
               'controller_sha256', 'mechanics_sha256', 'roster_sha256',
               'private_preflight_sha256', 'cli_path', 'cli_version',
               'approved_phases', 'review_note'}
    if set(review) != allowed:
        raise ValueError('Public root review must contain admission hashes only')
    if (review.get('schema') != 'claude-haiku-fresh-matched3-root-review-v1' or
            review.get('approved') is not True or
            review.get('configuration_id') != CONFIG or
            review.get('pass') != manifest['pass'] or
            review.get('manifest_sha256') != sha(BASE / manifest['pass'] / 'manifest.json') or
            review.get('controller_sha256') != sha(ROOT / 'scripts/claude_haiku_matched3.py') or
            review.get('mechanics_sha256') != sha(ROOT / 'scripts/claude_repeat_study.py') or
            review.get('roster_sha256') != sha(ROOT / 'scripts/claude_repeat_roster.py') or
            review.get('private_preflight_sha256') != preflight_hash or
            review.get('cli_path') != str(CLI) or review.get('cli_version') != RUNTIME or
            not isinstance(review.get('approved_phases'), list) or
            not str(review.get('review_note', '')).strip()):
        raise ValueError('Haiku root review differs')
    return review


def inspect(manifest, condition, note):
    pass_name = manifest['pass']
    folder, _, attempts, records, journal = phase_paths(pass_name, condition, 'smoke')
    if not note.strip() or not completed(pass_name, condition, 'smoke'):
        raise ValueError('Completed smoke and inspection note required')
    saved = [json.loads(line) for line in records.read_text().splitlines()]
    if len(saved) != 3 or any(r.get('status') != 'ok' for r in saved):
        raise ValueError('Three valid smoke records required')
    receipt = folder / 'smoke-inspection.json'
    with receipt.open('x') as out:
        json.dump({'inspection': 'accepted_unchanged', 'note': note,
                   'attempts_sha256': sha(attempts), 'records_sha256': sha(records),
                   'journal_sha256': sha(journal),
                   'inspected_utc': dt.datetime.now(dt.timezone.utc).isoformat()}, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())


def _admit(manifest, condition, phase, cli, review_path, review_hash,
           preflight_path, preflight_hash):
    pass_name = manifest['pass']
    if manifest != verify_manifest(pass_name, sha(BASE / pass_name / 'manifest.json')):
        raise ValueError('Unverified Haiku manifest')
    require_order(manifest, condition)
    folder, claim, attempts, records, journal = phase_paths(pass_name, condition, phase)
    if any(p.exists() for p in (claim, attempts, records, journal)):
        raise FileExistsError('Existing phase evidence requires review; no retry')
    if phase == 'development':
        smoke_folder, _, smoke_attempts, smoke_records, smoke_journal = phase_paths(
            pass_name, condition, 'smoke')
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
    roster.private_preflight(preflight_path, preflight_hash, roster.mechanics())
    if Path(cli).resolve() != CLI.resolve() or not CLI.is_file():
        raise ValueError('Claude CLI path differs from pinned installation')
    return folder, claim, attempts, records, journal


def run_phase(manifest, condition, phase, cli, review_path, review_hash,
              preflight_path, preflight_hash):
    if condition not in ('P0', 'P1', 'P2') or phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    folder, claim, attempts_path, records_path, journal_path = _admit(
        manifest, condition, phase, cli, review_path, review_hash,
        preflight_path, preflight_hash)
    env = clean_environment()
    with tempfile.TemporaryDirectory(dir='/private/tmp') as cwd:
        auth = subprocess.run([cli, '--safe-mode', 'auth', 'status'], cwd=cwd, env=env,
                              capture_output=True, text=True, check=True, timeout=30)
        require_subscription(json.loads(auth.stdout))
        version = subprocess.run([cli, '--version'], cwd=cwd, env=env,
                                 capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    if version != RUNTIME:
        raise ValueError('Claude CLI version differs from pinned runtime')
    pass_name = manifest['pass']
    old = roster.mechanics()
    folder.mkdir(parents=True, exist_ok=True)
    with claim.open('x') as out:
        json.dump({'configuration_id': CONFIG, 'pass': pass_name, 'condition': condition,
                   'phase': phase, 'manifest_sha256': sha(BASE / pass_name / 'manifest.json'),
                   'root_review_sha256': review_hash, 'private_preflight_sha256': preflight_hash,
                   'cli_version': version, 'claimed_utc': dt.datetime.now(dt.timezone.utc).isoformat()}, out)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    requests = ([manifest['conditions'][condition]['smoke']] if phase == 'smoke' else
                manifest['conditions'][condition]['development'])
    with attempts_path.open('x') as attempts, records_path.open('x') as records, journal_path.open('x') as journal:
        old.durable(journal, {'event': 'phase_started', 'pass': pass_name,
                              'condition': condition, 'phase': phase})
        for item in requests:
            ids, request, payload = item['record_ids'], item['request'], item['input_text']
            if request['input'] != json.loads(payload):
                raise ValueError('Manifest payload changed')
            cmd = command(cli, MODEL, EFFORT, request['system'], request['schema']) + ['--verbose']
            started = dt.datetime.now(dt.timezone.utc).isoformat()
            old.durable(journal, {'event': 'dispatch_intent',
                                  'batch_index': item['batch_index'],
                                  'record_ids': ids, 'started_utc': started})
            attempt = {'configuration_id': CONFIG, 'pass': pass_name, 'repeat': pass_name,
                       'condition': condition,
                       'phase': phase, 'batch_index': item['batch_index'], 'ids': ids,
                       'batch_size': len(ids), 'workflow': 'batch10', 'requested_model': MODEL,
                       'effort': EFFORT, 'cli_version': version, 'request': request,
                       'policy_sha256': digest(request['system']), 'input_sha256': digest(payload),
                       'schema_sha256': digest(json.dumps(request['schema'], sort_keys=True)),
                       'auth_method': 'claude.ai', 'controller_retries': 0,
                       'cli_internal_retries': 'not exposed', 'reference_labels_read': False,
                       'started_utc': started}
            started_clock = time.perf_counter()
            try:
                with tempfile.TemporaryDirectory(dir='/private/tmp') as cwd:
                    result = subprocess.run(cmd, input=payload, cwd=cwd, env=env, text=True,
                                            capture_output=True, timeout=TIMEOUT)
                raw_path = folder / f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
                old.save_raw_capture(raw_path, attempt, result.stdout,
                                     result.stderr, result.returncode)
                attempt['exit_code'] = result.returncode
                attempt['stderr'] = safe_diagnostic(result.stderr)
                body = json.loads(result.stdout)
                attempt.update(parse_batch_result(body, result.returncode, ids))
                attempt['raw_events'] = safe_diagnostic(body)
                if not isolation_ok(attempt):
                    attempt.update(status='service_error', error_type='IsolationIdentityOrBillingGuard')
            except (subprocess.SubprocessError, ValueError, OSError) as exc:
                attempt.update(status='service_error', error_type=type(exc).__name__)
                if isinstance(exc, subprocess.TimeoutExpired):
                    raw_path = folder / f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
                    old.save_raw_capture(raw_path, attempt, exc.stdout,
                                         exc.stderr, None, timed_out=True)
                    attempt['partial_stdout'] = old.capture_text(exc.stdout)
                    attempt['partial_stderr'] = old.capture_text(exc.stderr)
            attempt['elapsed_seconds'] = time.perf_counter() - started_clock
            old.durable(attempts, attempt)
            predictions = ({r['id']: {k: v for k, v in r.items() if k != 'id'}
                            for r in attempt.get('prediction', {}).get('records', [])}
                           if attempt['status'] == 'ok' else {})
            for pos, rid in enumerate(ids):
                old.durable(records, {'id': rid, 'status': attempt['status'],
                    'prediction': predictions.get(rid), 'pass': pass_name, 'condition': condition,
                    'phase': phase, 'batch_index': item['batch_index'], 'batch_position': pos + 1,
                    'batch_record_ids': ids, 'requested_model': MODEL, 'effort': EFFORT,
                    'elapsed_seconds': attempt['elapsed_seconds'] / len(ids),
                    'timing_kind': 'amortized_batch_share_not_individual_latency'})
            old.durable(journal, {'event': 'request_completed',
                'batch_index': item['batch_index'], 'status': attempt['status'],
                'completed_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
            if attempt['status'] != 'ok':
                old.durable(journal, {'event': 'phase_stopped',
                    'reason': attempt['status'], 'batch_index': item['batch_index']})
                raise RuntimeError('Stopped on first non-ok batch; no retry')
        old.durable(journal, {'event': 'phase_completed',
            'request_count': len(requests), 'record_count': 3 if phase == 'smoke' else 60})


def report():
    """Read only: preserve incomplete and failed phases in the public-safe summary."""
    summary = {'schema': 'claude-haiku-fresh-matched3-report-v1', 'configuration_id': CONFIG,
               'historical_failure_retained': True, 'reference_labels_read': False,
               'passes': {}}
    for pass_name, order in ORDERS.items():
        manifest_path = BASE / pass_name / 'manifest.json'
        if manifest_path.exists():
            verify_manifest(pass_name, sha(manifest_path))
        conditions = {}
        for condition in order:
            phases = {}
            for phase in ('smoke', 'development'):
                folder, claim, attempts, records, journal = phase_paths(
                    pass_name, condition, phase)
                if not claim.exists():
                    phases[phase] = {'state': 'not_started', 'records': 0}
                    continue
                if not all(p.exists() for p in (attempts, records, journal)):
                    phases[phase] = {'state': 'ambiguous', 'records': None}
                    continue
                saved_attempts = [json.loads(x) for x in attempts.read_text().splitlines() if x.strip()]
                saved_records = [json.loads(x) for x in records.read_text().splitlines() if x.strip()]
                events = [json.loads(x) for x in journal.read_text().splitlines() if x.strip()]
                if any(a.get('raw_capture_file') and sha(folder / a['raw_capture_file']) !=
                       a.get('raw_capture_sha256') for a in saved_attempts):
                    raise ValueError('Raw capture changed')
                known = {'ok', 'invalid_output', 'service_error'}
                if any(r.get('status') not in known for r in saved_records):
                    raise ValueError('Unknown saved Haiku status')
                expected = [f'DEV-{i:03d}' for i in range(1, 4 if phase == 'smoke' else 61)]
                actual = [r.get('id') for r in saved_records]
                if actual != expected[:len(actual)]:
                    raise ValueError('Saved Haiku record order differs')
                counts = {status: sum(r.get('status') == status for r in saved_records)
                          for status in sorted(known)}
                closed = bool(events and events[-1].get('event') == 'phase_completed')
                if closed and (len(saved_records) != len(expected) or
                               len(saved_attempts) != (1 if phase == 'smoke' else 6)):
                    raise ValueError('Haiku phase closure lacks full evidence')
                phases[phase] = {'state': 'completed' if closed else 'stopped_or_ambiguous',
                                 'records': len(saved_records), 'counts': counts,
                                 'raw_capture_count': sum(bool(a.get('raw_capture_file'))
                                                          for a in saved_attempts)}
            conditions[condition] = phases
        summary['passes'][pass_name] = conditions
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    sub.add_parser('report')
    for action in ('verify', 'inspect', 'smoke', 'development'):
        p = sub.add_parser(action)
        p.add_argument('--pass', dest='pass_name', required=True, choices=tuple(ORDERS))
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
    if args.action == 'prepare':
        prepare(); return
    if args.action == 'report':
        print(json.dumps(report(), indent=2)); return
    manifest = verify_manifest(args.pass_name, args.manifest_sha256)
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
