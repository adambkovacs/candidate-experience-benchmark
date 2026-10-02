#!/usr/bin/env python3
"""Separate, offline-planned three-pass Sonnet 5.5 subscription repeat lane."""

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
from claude_batch_benchmark import batch_schema, parse_batch_result
from development_benchmark import ROOT, digest, read_rows
import claude_repeat_roster as roster

EFFORTS = ('low', 'medium', 'high', 'xhigh')
EFFORT = 'low'
CONFIG = ''
MODEL = 'claude-sonnet-5-5'
RUNTIME = '2.1.287 (Claude Code)'
CLI = Path('/Users/adamkovacs/.local/share/claude/versions/2.1.287')
TIMEOUT = 600
BASE = Path()
ORIGINAL_BASE = ROOT / 'results/repeatability-v1/claude-sonnet55-fresh-matched3'
RECOVERED = ('low', 'pass1', 'P0')
BUILTIN_PLUGINS = {
    ('cc-plugin-agents-md', 'builtin', 'cc-plugin-agents-md@builtin'),
    ('cc-plugin-telemetry', 'builtin', 'cc-plugin-telemetry@builtin'),
    ('cc-plugin-plugin-authoring', 'builtin', 'cc-plugin-plugin-authoring@builtin'),
}
ORDERS = {'pass1': ['P0', 'P1', 'P2'], 'pass2': ['P1', 'P2', 'P0'],
          'pass3': ['P2', 'P0', 'P1']}
PREP = 'results/prompt-comparison-v1-2026-09-24/subscription-preparation-v2/sonnet5-low-first-pass-phase2-batch10-p0'


def configure(effort):
    global EFFORT, CONFIG, BASE
    if effort not in EFFORTS:
        raise ValueError('Unsupported Sonnet 5.5 effort; max and ultra excluded')
    EFFORT = effort
    CONFIG = f'sonnet55-{effort}-fresh-matched3-batch10-v2'
    BASE = ROOT / 'results/repeatability-v1/claude-sonnet55-fresh-matched3-v2' / effort


configure('low')


def isolation_ok_v2(record):
    """Exact observed Claude Code 2.1.287 builtin set; no unknown plugin."""
    plugins = record.get('init_plugins')
    if (not isinstance(plugins, list) or len(plugins) != len(BUILTIN_PLUGINS) or
            any(not isinstance(p, dict) or set(p) != {'name', 'path', 'source'}
                for p in plugins)):
        return False
    observed = {(p['name'], p['path'], p['source']) for p in plugins}
    if observed != BUILTIN_PLUGINS:
        return False
    events = record.get('raw_events', [])
    calls = [c.get('name') for event in events if isinstance(event, dict)
             for c in (event.get('message') or {}).get('content', [])
             if isinstance(c, dict) and c.get('type') == 'tool_use']
    return (record.get('init_tools') == ['StructuredOutput'] and
            record.get('init_mcp_servers') == [] and
            record.get('init_skills') == [] and
            record.get('init_model') == record.get('requested_model') == MODEL and
            record.get('assistant_models') == [MODEL] and
            record.get('returned_models') == [MODEL] and
            record.get('init_api_key_source') == 'none' and
            record.get('overage_observed') is False and
            bool(calls) and all(call == 'StructuredOutput' for call in calls))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def read_bound(binding):
    if source(binding['path']) != binding:
        raise ValueError('Frozen source changed: ' + binding['path'])


def plan_data(pass_name):
    if pass_name not in ORDERS:
        raise ValueError('Unknown Sonnet 5.5 pass')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if (len(inputs) != 60 or [r.get('id') for r in inputs] != ids or
            any(set(row) != {'id', 'feedback'} for row in inputs)):
        raise ValueError('Sonnet 5.5 input membership or isolation differs')
    original_manifest = ORIGINAL_BASE / EFFORT / pass_name / 'manifest.json'
    original = json.loads(original_manifest.read_text())
    if (original.get('model') != MODEL or original.get('effort') != EFFORT or
            original.get('pass') != pass_name or
            original.get('condition_order') != ORDERS[pass_name] or
            original.get('runtime_required') != RUNTIME):
        raise ValueError('Original Sonnet 5.5 manifest controls changed')
    paths = ['data/pilot/inputs.jsonl', 'schemas/judgments.schema.json',
             'scripts/development_benchmark.py',
             'scripts/claude_benchmark.py', 'scripts/claude_batch_benchmark.py',
             'scripts/claude_repeat_study.py', 'scripts/claude_repeat_roster.py',
             'scripts/claude_sonnet55_matched3.py',
             'scripts/claude_sonnet55_matched3_v2.py',
             str(original_manifest.relative_to(ROOT))]
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        instruction_path = f'{PREP}/{condition}-instruction.txt'
        instruction = (ROOT / instruction_path).read_text()
        paths.append(instruction_path)
        development = []
        for index in range(6):
            members = inputs[index * 10:(index + 1) * 10]
            member_ids = [row['id'] for row in members]
            payload = json.dumps({'records': [{'id': row['id'], 'feedback': row['feedback']}
                                               for row in members]})
            development.append({'batch_index': index + 1, 'record_ids': member_ids,
                                'request': {'system': instruction, 'input': json.loads(payload),
                                            'schema': batch_schema(member_ids)},
                                'input_text': payload})
        first = inputs[:3]
        smoke_ids = [r['id'] for r in first]
        smoke_payload = json.dumps({'records': [{'id': r['id'], 'feedback': r['feedback']}
                                                for r in first]})
        smoke = {'batch_index': 0, 'record_ids': smoke_ids,
                 'request': {'system': instruction, 'input': json.loads(smoke_payload),
                             'schema': batch_schema(smoke_ids)},
                 'input_text': smoke_payload}
        conditions[condition] = {'smoke': smoke, 'development': development}
        if conditions[condition] != original['conditions'][condition]:
            raise ValueError('V2 Sonnet request differs from original frozen request')
    return {'schema': 'claude-sonnet55-fresh-matched3-v2', 'configuration_id': CONFIG,
            'pass': pass_name, 'condition_order': ORDERS[pass_name],
            'model': MODEL, 'effort': EFFORT, 'batch_size': 10,
            'timeout_seconds': TIMEOUT, 'runtime_required': RUNTIME,
            'seed_policy': 'unchanged CLI default; seed unavailable',
            'prompt_source': 'existing batch10 P0/P1/P2 instruction bytes',
            'original_manifest': source(str(original_manifest.relative_to(ROOT))),
            'recovered_smoke': list(RECOVERED) if (EFFORT, pass_name) == RECOVERED[:2] else None,
            'reference_labels_read': False,
            'source_bindings': [source(p) for p in dict.fromkeys(paths)],
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


def offline_admission_path():
    return BASE / 'pass1/P0/offline-smoke-admission.json'


def offline_admission_data():
    if EFFORT != 'low':
        raise ValueError('Only the first low/P0 smoke has retained raw evidence')
    manifest_path = BASE / 'pass1/manifest.json'
    manifest = verify_manifest('pass1', sha(manifest_path))
    original_folder = ORIGINAL_BASE / 'low/pass1/P0'
    names = ('smoke.claim.json', 'smoke.attempts.jsonl', 'smoke.records.jsonl',
             'smoke.journal.jsonl', 'smoke.batch-000.raw.jsonl',
             'smoke.root-review.json')
    files = {name: original_folder / name for name in names}
    attempt_rows = [json.loads(line) for line in files['smoke.attempts.jsonl'].read_text().splitlines()]
    record_rows = [json.loads(line) for line in files['smoke.records.jsonl'].read_text().splitlines()]
    journal = [json.loads(line) for line in files['smoke.journal.jsonl'].read_text().splitlines()]
    raw_rows = [json.loads(line) for line in files['smoke.batch-000.raw.jsonl'].read_text().splitlines()]
    if len(attempt_rows) != 1 or len(raw_rows) != 1 or len(record_rows) != 3:
        raise ValueError('Original smoke evidence count differs')
    attempt, raw = attempt_rows[0], raw_rows[0]
    smoke = manifest['conditions']['P0']['smoke']
    ids = smoke['record_ids']
    if (attempt.get('status') != 'service_error' or
            attempt.get('error_type') != 'IsolationIdentityOrBillingGuard' or
            attempt.get('request') != smoke['request'] or
            attempt.get('ids') != ids or
            attempt.get('requested_model') != MODEL or
            attempt.get('effort') != EFFORT or
            attempt.get('cli_version') != RUNTIME or
            attempt.get('raw_capture_file') != 'smoke.batch-000.raw.jsonl' or
            attempt.get('raw_capture_sha256') != sha(files['smoke.batch-000.raw.jsonl']) or
            raw.get('schema') != 'claude-repeat-raw-capture-v1' or
            raw.get('repeat') != 'pass1' or raw.get('condition') != 'P0' or
            raw.get('phase') != 'smoke' or raw.get('batch_index') != 0 or
            raw.get('record_ids') != ids or raw.get('exit_code') != 0 or
            raw.get('timed_out') is not False or
            raw.get('input_sha256') != digest(smoke['input_text']) or
            [row.get('id') for row in record_rows] != ids or
            any(row.get('status') != 'service_error' or row.get('prediction') is not None
                for row in record_rows) or
            not journal or journal[-1].get('event') != 'phase_stopped' or
            journal[-1].get('reason') != 'service_error'):
        raise ValueError('Original guard-failed smoke evidence differs')
    body = json.loads(raw['stdout'])
    parsed = parse_batch_result(body, raw['exit_code'], ids)
    checked = {**parsed, 'requested_model': MODEL, 'raw_events': safe_diagnostic(body)}
    if (parsed.get('status') != 'ok' or parsed.get('prediction') != attempt.get('prediction') or
            checked['raw_events'] != attempt.get('raw_events') or
            not isolation_ok_v2(checked)):
        raise ValueError('Retained raw smoke fails v2 parsing or exact isolation guard')
    return {
        'schema': 'claude-sonnet55-v2-offline-smoke-admission-v1',
        'configuration_id': CONFIG, 'pass': 'pass1', 'condition': 'P0',
        'phase': 'smoke', 'admission': 'accepted_offline_from_retained_raw',
        'original_status': 'service_error',
        'original_error_type': 'IsolationIdentityOrBillingGuard',
        'reparsed_status': 'ok', 'v2_isolation_ok': True,
        'record_ids': ids, 'requested_model': MODEL, 'effort': EFFORT,
        'cli_version': RUNTIME,
        'observed_builtin_plugins': [list(t) for t in sorted(BUILTIN_PLUGINS)],
        'source_manifest_sha256': sha(ORIGINAL_BASE / 'low/pass1/manifest.json'),
        'v2_manifest_sha256': sha(manifest_path),
        'v2_controller_sha256': sha(ROOT / 'scripts/claude_sonnet55_matched3_v2.py'),
        'original_evidence_sha256': {name: sha(path) for name, path in files.items()},
        'reference_labels_read': False, 'inference_performed': False,
        'original_attempt_preserved': True,
        'limitation': 'Builtin plugin-authoring hidden prompt effects are not independently observable.'}


def verify_offline_admission():
    path = offline_admission_path()
    if not path.exists():
        raise FileNotFoundError('Offline smoke admission sidecar missing')
    saved = json.loads(path.read_text())
    if saved != offline_admission_data():
        raise ValueError('Offline smoke admission differs from retained evidence')
    return saved


def offline_admit():
    value = offline_admission_data()
    path = offline_admission_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    verify_offline_admission()
    print(sha(path))


def completed(pass_name, condition, phase):
    if (EFFORT, pass_name, condition) == RECOVERED and phase == 'smoke':
        if not offline_admission_path().exists():
            return False
        verify_offline_admission()
        return True
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
            raise ValueError('Previous Sonnet 5.5 pass incomplete')
    for earlier in order[:order.index(condition)]:
        if not completed(pass_name, earlier, 'development'):
            raise ValueError('Previous condition incomplete: ' + earlier)


def private_preflight(path, expected_hash):
    candidate = Path(path)
    if not candidate.is_absolute() or sha(candidate) != expected_hash:
        raise ValueError('Private preflight path/hash mismatch')
    try:
        candidate.resolve().relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError('Private subscription preflight cannot live in public repository')
    receipt = json.loads(candidate.read_text())
    if (receipt.get('operator') != 'root' or receipt.get('cli_version') != RUNTIME or
            receipt.get('auth_method') != 'claude.ai' or
            receipt.get('api_provider') != 'firstParty' or
            receipt.get('usage_credits_off') is not True or
            receipt.get('extra_usage_disabled') is not True):
        raise ValueError('Subscription preflight rejected')
    for field in ('session_used_percent', 'weekly_used_percent'):
        value = receipt.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 95:
            raise ValueError('Subscription quota admission rejected')
    checked = dt.datetime.fromisoformat(receipt['checked_utc'].replace('Z', '+00:00'))
    age = (dt.datetime.now(dt.timezone.utc) - checked).total_seconds()
    if not 0 <= age <= 1800:
        raise ValueError('Subscription preflight is stale')
    return receipt


def root_review(path, expected_hash, manifest, preflight_hash,
                condition, phase, smoke_evidence_hash):
    candidate = Path(path)
    if not candidate.is_absolute() or sha(candidate) != expected_hash:
        raise ValueError('Root review path/hash mismatch')
    review = json.loads(candidate.read_text())
    allowed = {'schema', 'approved', 'configuration_id', 'pass', 'manifest_sha256',
               'controller_sha256', 'mechanics_sha256', 'roster_sha256',
               'private_preflight_sha256', 'cli_path', 'cli_version',
               'approved_phases', 'smoke_evidence_sha256', 'review_note'}
    if set(review) != allowed:
        raise ValueError('Public root review must contain admission hashes only')
    if (review.get('schema') != 'claude-sonnet55-fresh-matched3-v2-root-review-v1' or
            review.get('approved') is not True or
            review.get('configuration_id') != CONFIG or
            review.get('pass') != manifest['pass'] or
            review.get('manifest_sha256') != sha(BASE / manifest['pass'] / 'manifest.json') or
            review.get('controller_sha256') != sha(ROOT / 'scripts/claude_sonnet55_matched3_v2.py') or
            review.get('mechanics_sha256') != sha(ROOT / 'scripts/claude_repeat_study.py') or
            review.get('roster_sha256') != sha(ROOT / 'scripts/claude_repeat_roster.py') or
            review.get('private_preflight_sha256') != preflight_hash or
            review.get('cli_path') != str(CLI) or review.get('cli_version') != RUNTIME or
            review.get('approved_phases') != [{'condition': condition, 'phase': phase}] or
            review.get('smoke_evidence_sha256') != smoke_evidence_hash or
            not str(review.get('review_note', '')).strip()):
        raise ValueError('Sonnet 5.5 root review differs')
    return review


def inspect(manifest, condition, note):
    pass_name = manifest['pass']
    if (EFFORT, pass_name, condition) == RECOVERED:
        raise ValueError('Original smoke retained through offline admission; no v2 smoke inspection')
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
    if (EFFORT, pass_name, condition) == RECOVERED and phase == 'smoke':
        raise ValueError('Original smoke already dispatched; no v2 replay')
    if manifest != verify_manifest(pass_name, sha(BASE / pass_name / 'manifest.json')):
        raise ValueError('Unverified Sonnet 5.5 manifest')
    require_order(manifest, condition)
    folder, claim, attempts, records, journal = phase_paths(pass_name, condition, phase)
    if any(p.exists() for p in (claim, attempts, records, journal)):
        raise FileExistsError('Existing phase evidence requires review; no retry')
    smoke_evidence_hash = None
    if phase == 'development':
        if (EFFORT, pass_name, condition) == RECOVERED:
            verify_offline_admission()
            smoke_evidence_hash = sha(offline_admission_path())
        else:
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
            smoke_evidence_hash = sha(inspection)
    root_review(review_path, review_hash, manifest, preflight_hash,
                condition, phase, smoke_evidence_hash)
    private_preflight(preflight_path, preflight_hash)
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
                if not isolation_ok_v2(attempt):
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
    summary = {'schema': 'claude-sonnet55-fresh-matched3-v2-report-v1', 'configuration_id': CONFIG,
               'reference_labels_read': False,
               'passes': {}}
    for pass_name, order in ORDERS.items():
        manifest_path = BASE / pass_name / 'manifest.json'
        if manifest_path.exists():
            verify_manifest(pass_name, sha(manifest_path))
        conditions = {}
        for condition in order:
            phases = {}
            for phase in ('smoke', 'development'):
                if (EFFORT, pass_name, condition) == RECOVERED and phase == 'smoke':
                    if offline_admission_path().exists():
                        verify_offline_admission()
                        phases[phase] = {'state': 'offline_admitted_original_guard_failure',
                                         'original_records': 3,
                                         'original_status': 'service_error',
                                         'reparsed_raw_status': 'ok',
                                         'admission_sha256': sha(offline_admission_path())}
                    else:
                        phases[phase] = {'state': 'original_guard_failure_pending_offline_review',
                                         'original_records': 3}
                    continue
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
                    raise ValueError('Unknown saved Sonnet 5.5 status')
                expected = [f'DEV-{i:03d}' for i in range(1, 4 if phase == 'smoke' else 61)]
                actual = [r.get('id') for r in saved_records]
                if actual != expected[:len(actual)]:
                    raise ValueError('Saved Sonnet 5.5 record order differs')
                counts = {status: sum(r.get('status') == status for r in saved_records)
                          for status in sorted(known)}
                closed = bool(events and events[-1].get('event') == 'phase_completed')
                if closed and (len(saved_records) != len(expected) or
                               len(saved_attempts) != (1 if phase == 'smoke' else 6)):
                    raise ValueError('Sonnet 5.5 phase closure lacks full evidence')
                phases[phase] = {'state': 'completed' if closed else 'stopped_or_ambiguous',
                                 'records': len(saved_records), 'counts': counts,
                                 'raw_capture_count': sum(bool(a.get('raw_capture_file'))
                                                          for a in saved_attempts)}
            conditions[condition] = phases
        summary['passes'][pass_name] = conditions
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--effort', required=True, choices=EFFORTS)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    sub.add_parser('offline-admit')
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
    configure(args.effort)
    if args.action == 'prepare':
        prepare(); return
    if args.action == 'offline-admit':
        offline_admit(); return
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
