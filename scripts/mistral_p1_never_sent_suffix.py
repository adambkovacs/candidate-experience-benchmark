#!/usr/bin/env python3
"""Hash-bound Venice repeat-2 P1 suffix. Dispatch is gated by a new root receipt."""
import argparse
import base64
import binascii
from collections import Counter
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import time
import urllib.error

import openrouter_repeat_wave as wave
import openrouter_paid_benchmark as paid

ROOT = Path(__file__).resolve().parents[1]
SPEC_ID = 'openrouter-paid-mistral-small32-24b-venice-not-applicable'
REPEAT = 'repeat2'
CONDITION = 'P1'
ORIGINAL = Path('results/repeatability-v1') / SPEC_ID
SUFFIX = ORIGINAL / REPEAT / CONDITION / 'never-sent-suffix-v1'
IDS = [f'DEV-{i:03}' for i in range(44, 61)]
PROBE_IDS = ['DEV-001', 'DEV-002', 'DEV-003']
FAILED_ID = 'DEV-043'
FAILED_ATTEMPT = '3e2007ab-bd42-4831-bd83-79b61226b8fd'
SCHEMA = 'mistral-p1-never-sent-suffix-v1'
REVIEW_SCHEMA = 'mistral-p1-suffix-root-review-v1'


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_at(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def binding(relative):
    path = file_at(relative)
    return {'path': str(relative), 'sha256': sha_bytes(path.read_bytes())}


def read_bound(item):
    path = file_at(item['path'])
    raw = path.read_bytes()
    if sha_bytes(raw) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['path'])
    return raw


def rows(raw):
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL tail')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def source_paths():
    p = ORIGINAL / REPEAT / CONDITION
    return {'manifest': ORIGINAL / REPEAT / 'manifest.json',
            'original_review': ORIGINAL / 'root-review-v1.json',
            'claim': p / 'development.claim.json',
            'journal': p / 'development.journal.jsonl',
            'attempts': p / 'development.attempts.jsonl',
            'responses': p / 'development.responses.jsonl',
            'smoke_claim': p / 'smoke.claim.json',
            'smoke_journal': p / 'smoke.journal.jsonl',
            'smoke_attempts': p / 'smoke.attempts.jsonl',
            'smoke_responses': p / 'smoke.responses.jsonl',
            'smoke_inspection': p / 'smoke-inspection.json',
            'budget_manifest': ORIGINAL / 'budget-partition-v1.json',
            'dev043_accounting': ORIGINAL / 'dev043-unknown-cost-bound-v1.json'}


def source_state(plan, bound_sources):
    source = {key: read_bound(item) for key, item in bound_sources.items()}
    attempts = rows(source['attempts'])
    journal = rows(source['journal'])
    responses = rows(source['responses'])
    requests = plan['conditions'][CONDITION]['development']
    expected = [f'DEV-{i:03}' for i in range(1, 44)]
    if [x.get('id') for x in attempts] != expected or len({x.get('attempt_id') for x in attempts}) != 43:
        raise ValueError('Original development is not the exact 43-attempt prefix')
    if [x.get('record_id') for x in requests] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Frozen plan is not the canonical 60 positions')
    for item, request in zip(attempts, requests):
        if (item.get('request_sha256'), item.get('request'), item.get('reference_labels_read')) != (
                request['request_sha256'], request['payload'], False):
            raise ValueError('Original attempt differs from frozen request')
    intents = [x for x in journal if x.get('event') == 'request_intent']
    starts = [x for x in journal if x.get('event') == 'request_started']
    finishes = [x for x in journal if x.get('event') == 'request_finished']
    if ([(x.get('id'), x.get('request_sha256')) for x in intents] !=
            [(x['id'], x['request_sha256']) for x in attempts] or
            [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in starts] !=
            [(x['id'], x['attempt_id'], x['request_sha256']) for x in attempts] or
            [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in finishes] !=
            [(x['id'], x['attempt_id'], x['status']) for x in attempts]):
        raise ValueError('Original journal and attempts differ')
    if journal[-1].get('event') != 'phase_stopped' or journal[-1].get('id') != FAILED_ID:
        raise ValueError('Original P1 did not stop at DEV-043')
    if (any(x.get('status') != 'ok' or x.get('cost_unknown') is not False or x.get('billing_ok') is not True for x in attempts[:42]) or
            attempts[-1].get('attempt_id') != FAILED_ATTEMPT or attempts[-1].get('status') != 'service_error' or
            attempts[-1].get('http_status') != 429 or attempts[-1].get('cost_unknown') is not True or
            attempts[-1].get('billing_ok') is not False or attempts[-1].get('observed_cost_usd') is not None):
        raise ValueError('Original 429 or valid prefix differs')
    if [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in responses] != [
            (x['id'], x['attempt_id'], x['request_sha256']) for x in attempts]:
        raise ValueError('Original raw sidecars do not match attempts')
    if not responses[-1].get('error_body') or responses[-1].get('http_status') != 429:
        raise ValueError('Original 429 raw evidence missing')
    inspection = json.loads(source['smoke_inspection'])
    if (inspection.get('decision') != 'accepted_unchanged' or
            inspection.get('journal_sha256') != sha_bytes(source['smoke_journal']) or
            inspection.get('attempts_sha256') != sha_bytes(source['smoke_attempts']) or
            inspection.get('responses_sha256') != sha_bytes(source['smoke_responses'])):
        raise ValueError('Original inspected smoke differs')
    smoke = rows(source['smoke_attempts'])
    if [x.get('id') for x in smoke] != PROBE_IDS or any(x.get('status') != 'ok' or x.get('cost_unknown') is not False for x in smoke):
        raise ValueError('Original smoke differs')
    return attempts


def expected_manifest():
    spec = wave.SPECS[SPEC_ID]
    sources = {key: binding(path) for key, path in source_paths().items()}
    manifest_sha = sources['manifest']['sha256']
    plan = wave.verify(spec, REPEAT, manifest_sha)
    wave.review_receipt(spec, file_at(sources['original_review']['path']), REPEAT, manifest_sha)
    source_state(plan, sources)
    if plan['provider_tag'] != spec.provider or plan['partition_cap_usd'] != spec.cap or spec.provider != 'venice/fp8':
        raise ValueError('Frozen Venice controls differ')
    return {'schema': SCHEMA, 'status': 'DRAFT', 'configuration_id': SPEC_ID,
            'repeat': REPEAT, 'condition': CONDITION, 'reference_labels_read': False,
            'controller': binding(Path('scripts') / Path(__file__).name),
            'sources': sources, 'request_ids': IDS,
            'requests': plan['conditions'][CONDITION]['development'][43:],
            'capacity_probe': {'optional': True, 'phase': 'capacity_probe',
                               'request_ids': PROBE_IDS,
                               'purpose': 'Separate route capacity observation, not development coverage'},
            'policy': {'retry_count': 0, 'failed_attempts_reused': False,
                       'stop_on_unknown_cost': True, 'canonical_denominator': 60,
                       'original_failed_id': FAILED_ID, 'original_failed_attempt_id': FAILED_ATTEMPT},
            'output_directory': str(SUFFIX)}


def validate_manifest(raw, expected_sha=None, frozen=True):
    if expected_sha is not None and sha_bytes(raw) != expected_sha:
        raise ValueError('Suffix manifest hash differs')
    manifest = json.loads(raw)
    expected = expected_manifest()
    if frozen:
        expected['status'] = 'FROZEN'
    if manifest != expected:
        raise ValueError('Suffix manifest differs from exact frozen source reconstruction')
    if [x['record_id'] for x in manifest['requests']] != IDS:
        raise ValueError('Suffix includes attempted IDs')
    return manifest


def child_ledger_path(manifest):
    budget = json.loads(read_bound(manifest['sources']['budget_manifest']))
    original = json.loads(read_bound(manifest['sources']['original_review']))
    entries = [x for x in budget['partitions'] if x['id'] == original['partition_id']]
    if len(entries) != 1 or entries[0]['cap_usd'] != '0.15':
        raise ValueError('Mistral child partition differs')
    return Path(entries[0]['child_ledger'])


def require_unknown_accounted(manifest):
    ledger = child_ledger_path(manifest)
    events = rows(ledger.read_bytes())
    reserves = [e for e in events if e.get('event') == 'reserve' and e.get('attempt_id') == FAILED_ATTEMPT]
    accounted = [e for e in events if e.get('event') == 'unknown_cost_accounted_as_upper_bound' and e.get('attempt_id') == FAILED_ATTEMPT]
    if len(reserves) != 1 or reserves[0].get('record_id') != FAILED_ID or len(accounted) != 1:
        raise ValueError('DEV-043 must be explicitly accounted at full upper bound')
    event = accounted[0]
    if event != json.loads(read_bound(manifest['sources']['dev043_accounting'])):
        raise ValueError('DEV-043 ledger event differs from immutable accounting receipt')
    if (paid.number(reserves[0]['usd']) != paid.number(event['usd']) or
            event.get('actual_cost_usd') is not None or
            event.get('evidence_sha256') != manifest['sources']['attempts']['sha256'] or
            Path(event.get('evidence_path', '')).resolve() != file_at(manifest['sources']['attempts']['path']) or
            not event.get('reason')):
        raise ValueError('DEV-043 upper-bound accounting evidence differs')
    if any(e.get('event') == 'settle' and e.get('attempt_id') == FAILED_ATTEMPT for e in events):
        raise ValueError('DEV-043 is not a known settled charge')
    return event


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError('UTC time required')
    try:
        moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('Invalid UTC time') from None
    if moment.tzinfo != timezone.utc:
        raise ValueError('UTC time required')
    return moment


def validate_review(review_raw, manifest_sha, manifest, phase, now=None):
    receipt = json.loads(review_raw)
    allowed = {'capacity_probe', 'development'}
    if (receipt.get('schema') != REVIEW_SCHEMA or receipt.get('approved') is not True or
            receipt.get('manifest_sha256') != manifest_sha or
            receipt.get('original_review_sha256') != manifest['sources']['original_review']['sha256'] or
            receipt.get('budget_manifest_sha256') != manifest['sources']['budget_manifest']['sha256'] or
            receipt.get('controller_sha256') != manifest['controller']['sha256'] or
            receipt.get('partition_id') != 'mistral32-repeat-v1' or
            not isinstance(receipt.get('approved_phases'), list) or
            not set(receipt['approved_phases']) <= allowed or phase not in receipt['approved_phases'] or
            not isinstance(receipt.get('cooldown_note'), str) or not receipt['cooldown_note'].strip() or
            receipt.get('capacity_probe_policy') not in ('required', 'waived_with_reason')):
        raise ValueError('New explicit suffix root review missing or mismatched')
    if receipt['capacity_probe_policy'] == 'waived_with_reason' and not str(receipt.get('probe_waiver_reason', '')).strip():
        raise ValueError('Capacity probe waiver needs a reason')
    start = parse_utc(receipt.get('cooldown_not_before_utc'))
    if (now or datetime.now(timezone.utc)) < start:
        raise ValueError('Provider cooldown admission time has not arrived')
    if phase == 'development' and receipt['capacity_probe_policy'] == 'required':
        inspection = receipt.get('capacity_probe_inspection')
        if not isinstance(inspection, dict) or 'path' not in inspection or 'sha256' not in inspection:
            raise ValueError('Root-inspected capacity probe binding required')
        proof = json.loads(read_bound(inspection))
        if (proof.get('schema') != 'mistral-p1-capacity-probe-inspection-v1' or
                proof.get('decision') != 'accepted_unchanged' or proof.get('manifest_sha256') != manifest_sha):
            raise ValueError('Capacity probe has not been accepted')
        for kind in ('journal', 'attempts', 'responses'):
            if proof.get(kind + '_sha256') != sha_bytes(phase_paths('capacity_probe')[kind].read_bytes()):
                raise ValueError('Capacity probe changed after inspection')
    return receipt


def phase_paths(phase):
    if phase not in ('capacity_probe', 'development'):
        raise ValueError('Unsupported phase')
    base = ROOT / SUFFIX
    return {kind: base / (phase + '.' + name) for kind, name in (
        ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
        ('attempts', 'attempts.jsonl'), ('responses', 'responses.jsonl'))}


def capture_http_error(exc, token, responses, rid, attempt, request_sha):
    """Save bounded HTTP error evidence even if the body read ends early."""
    read_error = None
    try:
        raw = exc.read(wave.MAX_RESPONSE_BYTES + 1)
    except http.client.IncompleteRead as interrupted:
        raw = interrupted.partial
        read_error = 'IncompleteRead'
    clipped = len(raw) > wave.MAX_RESPONSE_BYTES
    body = raw[:wave.MAX_RESPONSE_BYTES].replace(token.encode(), b'[REDACTED]')
    details = {'http_status': exc.code,
               'error_body': body.decode('utf-8', errors='replace'),
               'error_headers': {key: str(exc.headers[key]).replace(token, '[REDACTED]')
                                 for key in ('x-request-id', 'request-id', 'retry-after', 'cf-ray')
                                 if exc.headers is not None and exc.headers.get(key) is not None},
               'body_truncated_at_limit': clipped, 'read_error': read_error}
    paid.durable(responses, {'id': rid, 'attempt_id': attempt,
                             'request_sha256': request_sha, **details, 'received_utc': wave.utc()})
    return details


def dispatch(manifest_path, manifest_sha, review_path, phase, env_file=None):
    raw = Path(manifest_path).read_bytes()
    manifest = validate_manifest(raw, manifest_sha)
    require_unknown_accounted(manifest)
    review_raw = Path(review_path).read_bytes()
    validate_review(review_raw, manifest_sha, manifest, phase)
    spec = wave.SPECS[SPEC_ID]
    plan = wave.verify(spec, REPEAT, manifest['sources']['manifest']['sha256'])
    paths = phase_paths(phase)
    if phase == 'capacity_probe' and any(path.exists() for path in phase_paths('development').values()):
        raise FileExistsError('Development was already claimed; no later capacity probe')
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Phase was already claimed; no replay')
    if phase == 'development':
        probe = phase_paths('capacity_probe')
        if any(path.exists() for path in probe.values()) and json.loads(review_raw)['capacity_probe_policy'] != 'required':
            raise ValueError('Existing capacity probe requires explicit inspection')
    model, endpoint, reserve = wave.live_controls(spec, plan, CONDITION)
    original_review = json.loads(read_bound(manifest['sources']['original_review']))
    budget_path = file_at(manifest['sources']['budget_manifest']['path'])
    ledger = wave.budget_gate(spec, original_review, budget_path)
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked:
            raise ValueError('Unresolved or blocked child budget')
        token = paid.load_key(env_file)
        selected = (plan['conditions'][CONDITION]['smoke'] if phase == 'capacity_probe'
                    else manifest['requests'])
        paths['journal'].parent.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as claim:
            paid.durable(claim, {'schema': SCHEMA + '-claim', 'phase': phase,
                                 'manifest_sha256': manifest_sha, 'review_sha256': sha_bytes(review_raw),
                                 'request_ids': [x['record_id'] for x in selected], 'utc': wave.utc()})
        complete = True
        with paths['journal'].open('x') as audit, paths['attempts'].open('x') as output, paths['responses'].open('x') as responses:
            paid.durable(audit, {'event': 'phase_started', 'phase': phase, 'manifest_sha256': manifest_sha, 'utc': wave.utc()})
            try:
                for request in selected:
                    rid = request['record_id']
                    if phase == 'development' and rid not in IDS:
                        raise ValueError('Attempted original ID cannot be dispatched')
                    paid.durable(audit, {'event': 'request_intent', 'id': rid,
                                         'request_sha256': request['request_sha256'], 'utc': wave.utc()})
                    attempt = ledger.reserve(reserve, rid)
                    paid.durable(audit, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                         'request_sha256': request['request_sha256'], 'utc': wave.utc()})
                    record = {'id': rid, 'repeat': REPEAT, 'condition': CONDITION, 'phase': phase,
                              'attempt_id': attempt, 'request': request['payload'],
                              'request_sha256': request['request_sha256'], 'manifest_sha256': manifest_sha,
                              'provider_endpoint': endpoint, 'model_catalog_entry': model,
                              'requested_model': spec.model, 'reasoning_effort': spec.effort,
                              'reference_labels_read': False, 'reserved_cost_usd': str(reserve),
                              'request_timeout_seconds': spec.timeout, 'started_utc': wave.utc()}
                    actual = None
                    start = time.perf_counter()
                    try:
                        body = wave.fetch_recorded(request['payload'], token, spec.timeout, responses,
                                                   rid, attempt, request['request_sha256'])
                        body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                        record['raw_response'] = body
                        if isinstance(body, dict):
                            usage = body.get('usage') or {}
                            if isinstance(usage, dict) and usage.get('cost') is not None:
                                actual = paid.number(usage['cost'])
                            record.update(wave.classify(spec, body, endpoint))
                        else:
                            record['status'] = 'control_violation'
                    except Exception as exc:
                        record.update(status='service_error', error_type=type(exc).__name__)
                        if isinstance(exc, urllib.error.HTTPError):
                            record.update(capture_http_error(exc, token, responses, rid,
                                                             attempt, request['request_sha256']))
                    billing_ok = ledger.settle(attempt, actual)
                    record.update(elapsed_seconds=time.perf_counter() - start,
                                  observed_cost_usd=str(actual) if actual is not None else None,
                                  cost_unknown=actual is None, billing_ok=billing_ok)
                    if isinstance(record.get('raw_response'), dict):
                        diagnostic = wave.audit_response(record, 'openrouter_paid_v1', endpoint['context_length'] - 4096)
                        record['response_diagnostic'] = diagnostic
                        if not diagnostic['passed'] and record['status'] == 'ok':
                            record['status'] = 'prompt_admission_failure'
                    paid.durable(output, record)
                    paid.durable(audit, {'event': 'request_finished', 'id': rid, 'attempt_id': attempt,
                                         'status': record['status'], 'billing_ok': billing_ok,
                                         'cost_unknown': record['cost_unknown'], 'utc': wave.utc()})
                    may_continue = (record['status'] == 'ok' and billing_ok and not record['cost_unknown']
                                    and record.get('response_diagnostic', {}).get('passed') is True)
                    if phase == 'development' and not may_continue:
                        may_continue = wave.continue_record(spec, record, 'development')
                    if not may_continue:
                        complete = False
                        paid.durable(audit, {'event': 'phase_stopped', 'id': rid, 'reason': record['status'], 'utc': wave.utc()})
                        break
                if complete:
                    paid.durable(audit, {'event': 'phase_completed', 'phase': phase,
                                         'request_count': len(selected), 'utc': wave.utc()})
            finally:
                lines = rows(paths['journal'].read_bytes())
                if lines and lines[-1].get('event') not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                    paid.durable(audit, {'event': 'phase_aborted', 'reason': 'exception_or_interruption', 'utc': wave.utc()})
        return complete
    finally:
        ledger.close()


def inspect_probe(manifest_path, manifest_sha, review_path, note):
    if not note.strip():
        raise ValueError('Inspection note required')
    manifest = validate_manifest(Path(manifest_path).read_bytes(), manifest_sha)
    validate_review(Path(review_path).read_bytes(), manifest_sha, manifest, 'capacity_probe')
    paths = phase_paths('capacity_probe')
    journal, attempts, responses = [rows(paths[kind].read_bytes()) for kind in ('journal', 'attempts', 'responses')]
    plan = wave.verify(wave.SPECS[SPEC_ID], REPEAT, manifest['sources']['manifest']['sha256'])
    requests = plan['conditions'][CONDITION]['smoke']
    starts = [x for x in journal if x.get('event') == 'request_started']
    finishes = [x for x in journal if x.get('event') == 'request_finished']
    if (journal[-1].get('event') != 'phase_completed' or
            [x.get('id') for x in attempts] != PROBE_IDS or
            [x.get('id') for x in responses] != PROBE_IDS or
            [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in starts] !=
            [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in attempts] or
            [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in finishes] !=
            [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in attempts] or
            [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in responses] !=
            [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in attempts] or
            any(x.get('request') != request['payload'] or x.get('request_sha256') != request['request_sha256']
                or x.get('reference_labels_read') is not False or x.get('phase') != 'capacity_probe'
                or x.get('status') != 'ok' or x.get('billing_ok') is not True or x.get('cost_unknown') is not False
                for x, request in zip(attempts, requests)) or
            any(x.get('body_truncated_at_limit') or x.get('read_error') or 'body_base64' not in x for x in responses)):
        raise ValueError('Capacity probe is not three intact attributed valid calls')
    for row, sidecar in zip(attempts, responses):
        try:
            captured = json.loads(base64.b64decode(sidecar['body_base64'], validate=True))
        except (ValueError, binascii.Error):
            raise ValueError('Capacity probe raw bytes malformed') from None
        if captured != row.get('raw_response'):
            raise ValueError('Capacity probe attempt differs from raw bytes')
    ledger_events = rows(child_ledger_path(manifest).read_bytes())
    for row in attempts:
        settlements = [x for x in ledger_events if x.get('attempt_id') == row['attempt_id'] and x.get('event') == 'settle']
        if len(settlements) != 1 or paid.number(settlements[0]['usd']) != paid.number(row.get('observed_cost_usd')):
            raise ValueError('Capacity probe charge differs from child ledger')
    receipt = {'schema': 'mistral-p1-capacity-probe-inspection-v1', 'decision': 'accepted_unchanged',
               'note': note, 'manifest_sha256': manifest_sha,
               **{kind + '_sha256': sha_bytes(paths[kind].read_bytes()) for kind in ('journal', 'attempts', 'responses')}}
    with (ROOT / SUFFIX / 'capacity-probe-inspection.json').open('x') as out:
        json.dump(receipt, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return receipt


def reconcile(manifest_path, manifest_sha):
    manifest = validate_manifest(Path(manifest_path).read_bytes(), manifest_sha)
    source_state(wave.verify(wave.SPECS[SPEC_ID], REPEAT, manifest['sources']['manifest']['sha256']), manifest['sources'])
    require_unknown_accounted(manifest)
    original = rows(read_bound(manifest['sources']['attempts']))
    paths = phase_paths('development')
    if not paths['claim'].exists():
        if any(paths[k].exists() for k in ('journal', 'attempts', 'responses')):
            raise ValueError('Suffix evidence exists without claim')
        suffix_rows, started, terminal, raw = [], [], 'not_started', []
    else:
        claim = json.loads(paths['claim'].read_text())
        if claim.get('manifest_sha256') != manifest_sha or claim.get('request_ids') != IDS:
            raise ValueError('Suffix claim binding differs')
        journal = rows(paths['journal'].read_bytes())
        suffix_rows = rows(paths['attempts'].read_bytes())
        raw = rows(paths['responses'].read_bytes())
        started = [x for x in journal if x.get('event') == 'request_started']
        finished = [x for x in journal if x.get('event') == 'request_finished']
        if ([x.get('id') for x in started] != IDS[:len(started)] or
                len({x.get('attempt_id') for x in started}) != len(started) or
                [x.get('id') for x in suffix_rows] != IDS[:len(suffix_rows)] or
                [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in finished] !=
                [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in suffix_rows] or
                [(x.get('id'), x.get('attempt_id'), x.get('request_sha256')) for x in started[:len(suffix_rows)]] !=
                [(x['id'], x['attempt_id'], x['request_sha256']) for x in suffix_rows] or
                len(started) > len(suffix_rows) + 1):
            raise ValueError('Suffix journal, attempt prefix or IDs differ')
        for row, request in zip(suffix_rows, manifest['requests']):
            if (row.get('request') != request['payload'] or row.get('request_sha256') != request['request_sha256'] or
                    row.get('reference_labels_read') is not False or row.get('phase') != 'development' or
                    row.get('manifest_sha256') != manifest_sha):
                raise ValueError('Suffix request or identity differs from frozen plan')
            if row.get('status') == 'ok' and (row.get('billing_ok') is not True or row.get('cost_unknown') is not False):
                raise ValueError('Valid suffix output lacks known billing')
            if row.get('cost_unknown') is True and row.get('billing_ok') is not False:
                raise ValueError('Unknown suffix cost cannot be billed')
        for sidecar in raw:
            match = next((x for x in started if x.get('attempt_id') == sidecar.get('attempt_id')), None)
            if match is None or sidecar.get('id') != match['id'] or sidecar.get('request_sha256') != match['request_sha256']:
                raise ValueError('Suffix raw response attribution differs')
        if len(raw) > len(started) or len({x.get('attempt_id') for x in raw}) != len(raw):
            raise ValueError('Duplicate suffix raw response')
        terminal = journal[-1].get('event') if journal else 'empty'
        if terminal == 'phase_completed' and (len(suffix_rows) != 17 or len(started) != 17):
            raise ValueError('Completed suffix lacks 17 attempts')
    ledger_events = rows(child_ledger_path(manifest).read_bytes())
    marker = json.loads(read_bound(manifest['sources']['dev043_accounting']))
    if ledger_events.count(marker) != 1:
        raise ValueError('DEV-043 accounting marker missing from child ledger')
    later_events = ledger_events[ledger_events.index(marker) + 1:]
    started_attempts = {x['attempt_id'] for x in started}
    closed_attempts = {e.get('attempt_id') for e in later_events
                       if e.get('event') in ('settle', 'unknown_cost_accounted_as_upper_bound')}
    next_id = IDS[len(started)] if len(started) < len(IDS) else None
    suffix_reserves = [e for e in later_events if e.get('event') == 'reserve' and
                       (e.get('attempt_id') in started_attempts or
                        (e.get('record_id') == next_id and e.get('attempt_id') not in closed_attempts))]
    if len({e.get('attempt_id') for e in suffix_reserves}) != len(suffix_reserves) or len({e.get('record_id') for e in suffix_reserves}) != len(suffix_reserves):
        raise ValueError('Suffix budget contains duplicate attempts or record IDs')
    reserved = {e['attempt_id']: e for e in suffix_reserves}
    if any(x.get('attempt_id') not in reserved or reserved[x['attempt_id']]['record_id'] != x['id'] for x in started):
        raise ValueError('Started suffix request lacks matching budget reservation')
    unmatched = [e for e in suffix_reserves if e['attempt_id'] not in {x['attempt_id'] for x in started}]
    if len(unmatched) > 1 or (unmatched and unmatched[0]['record_id'] != IDS[len(started)]):
        raise ValueError('Unmatched suffix reservation is outside next position')
    for row in suffix_rows:
        settlements = [e for e in later_events if e.get('attempt_id') == row['attempt_id'] and e.get('event') in ('settle', 'unknown_cost_accounted_as_upper_bound')]
        if row.get('cost_unknown') is False:
            if len(settlements) != 1 or settlements[0]['event'] != 'settle' or paid.number(settlements[0]['usd']) != paid.number(row.get('observed_cost_usd')):
                raise ValueError('Suffix known charge differs from child ledger')
        elif row.get('cost_unknown') is True:
            if settlements and (len(settlements) != 1 or settlements[0]['event'] != 'unknown_cost_accounted_as_upper_bound' or paid.number(settlements[0]['usd']) != paid.number(row['reserved_cost_usd'])):
                raise ValueError('Suffix unknown charge accounting differs')
        else:
            raise ValueError('Suffix cost state missing')
        sidecar = next((x for x in raw if x['attempt_id'] == row['attempt_id']), None)
        if ('raw_response' in row or 'error_body' in row) and sidecar is None:
            raise ValueError('Suffix saved response lacks raw sidecar')
        if sidecar is not None and any(key in row and sidecar.get(key) != row[key] for key in ('error_body', 'http_status', 'error_headers')):
            raise ValueError('Suffix raw sidecar differs from attempt')
        if 'raw_response' in row:
            if sidecar is None or 'body_base64' not in sidecar or sidecar.get('body_truncated_at_limit') or sidecar.get('read_error'):
                raise ValueError('Suffix response bytes missing or incomplete')
            try:
                captured = json.loads(base64.b64decode(sidecar['body_base64'], validate=True))
            except (ValueError, binascii.Error):
                raise ValueError('Suffix response bytes malformed') from None
            if captured != row['raw_response']:
                raise ValueError('Suffix saved response differs from raw bytes')
    indexed = {x['id']: {'status': x['status'], 'attempt_id': x['attempt_id']} for x in original + suffix_rows}
    for item in started[len(suffix_rows):]:
        indexed[item['id']] = {'status': 'unknown_started', 'attempt_id': item['attempt_id']}
    for item in unmatched:
        indexed[item['record_id']] = {'status': 'unknown_reserved', 'attempt_id': item['attempt_id']}
    for rid in [f'DEV-{i:03}' for i in range(1, 61)]:
        indexed.setdefault(rid, {'status': 'never_sent'})
    if len(indexed) != 60 or indexed[FAILED_ID]['status'] != 'service_error':
        raise ValueError('Composite coverage differs')
    counts = Counter(x['status'] for x in indexed.values())
    closed = counts['never_sent'] == counts['unknown_started'] == counts['unknown_reserved'] == 0
    coverage = ('closed_with_historical_service_error' if counts == {'ok': 59, 'service_error': 1}
                else 'closed_with_failures') if closed else 'partial'
    return {'schema': SCHEMA + '-reconciliation', 'manifest_sha256': manifest_sha,
            'original_terminal': 'phase_stopped', 'suffix_terminal': terminal,
            'coverage_status': coverage,
            'strict_complete_pass': False, 'denominator': 60,
            'status_counts': dict(sorted(counts.items())),
            'unknown_started_ids': [rid for rid, value in indexed.items() if value['status'] == 'unknown_started'],
            'unknown_reserved_ids': [rid for rid, value in indexed.items() if value['status'] == 'unknown_reserved'],
            'never_sent_ids': [rid for rid, value in indexed.items() if value['status'] == 'never_sent'],
            'positions': [{'id': rid, **indexed[rid]} for rid in [f'DEV-{i:03}' for i in range(1, 61)]],
            'evidence': {'original_attempts': manifest['sources']['attempts'],
                         'original_journal': manifest['sources']['journal'],
                         'suffix_claim_sha256': sha_bytes(paths['claim'].read_bytes()) if paths['claim'].exists() else None,
                         'suffix_journal_sha256': sha_bytes(paths['journal'].read_bytes()) if paths['journal'].exists() else None,
                         'suffix_attempts_sha256': sha_bytes(paths['attempts'].read_bytes()) if paths['attempts'].exists() else None,
                         'suffix_responses_sha256': sha_bytes(paths['responses'].read_bytes()) if paths['responses'].exists() else None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    freeze = sub.add_parser('freeze')
    freeze.add_argument('--draft', required=True)
    for action in ('validate', 'reconcile', 'capacity-probe', 'development', 'inspect-probe'):
        p = sub.add_parser(action)
        p.add_argument('--manifest', required=True)
        p.add_argument('--sha256', required=True)
        if action in ('capacity-probe', 'development', 'inspect-probe'):
            p.add_argument('--review', required=True)
        if action in ('capacity-probe', 'development'):
            p.add_argument('--env-file')
        if action == 'inspect-probe':
            p.add_argument('--note', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        value = expected_manifest()
        path = ROOT / SUFFIX / 'draft-manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            json.dump(value, out, indent=2)
            out.write('\n')
        print(path)
    elif args.action == 'freeze':
        raw = Path(args.draft).read_bytes()
        validate_manifest(raw, frozen=False)
        value = json.loads(raw)
        value['status'] = 'FROZEN'
        path = ROOT / SUFFIX / 'frozen-manifest.json'
        with path.open('x') as out:
            json.dump(value, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        print(path, sha_bytes(path.read_bytes()))
    elif args.action == 'validate':
        validate_manifest(Path(args.manifest).read_bytes(), args.sha256)
        print('validated')
    elif args.action == 'reconcile':
        report = reconcile(args.manifest, args.sha256)
        print(json.dumps(report, indent=2))
    elif args.action == 'inspect-probe':
        inspect_probe(args.manifest, args.sha256, args.review, args.note)
        print('inspected')
    else:
        phase = 'capacity_probe' if args.action == 'capacity-probe' else 'development'
        print('completed' if dispatch(args.manifest, args.sha256, args.review, phase, args.env_file) else 'stopped')


if __name__ == '__main__':
    main()
