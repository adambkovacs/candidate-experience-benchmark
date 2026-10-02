#!/usr/bin/env python3
"""Admit only never-sent fresh3/P2 Gemma26 DEV-054..060 after the aborted prefix."""

import argparse
import base64
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
import gemma26_on_fresh_repeat_study_v2 as study
import gemma26_on_fresh_repeat_execution_v2 as original
import gemma26_v2_continuation as first
import gemma26_v2_third_continuation as third
import gemma26_v2_fifth_suffix as fifth
import gemma26_v2_final_suffix as final
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'gemma26-on-v2-postabort-suffix-054-060-v1'
BASE = study.BASE / 'postabort-suffix-054-060-v1'
STAGE = BASE / 'fresh3/P2'
PARTITION_ID = final.PARTITION_ID
CAP = final.CAP
RESERVE = final.RESERVE
IDS = tuple(f'DEV-{n:03d}' for n in range(54, 61))
REMAINDER = ()
AUDIT = BASE / 'preflight-abort-after-dev053.json'
AUDIT_SHA = '0e972081d6cc0d1dd0a3adc90e1095ba69ab2e7fea282e36bc57d0719311cb7b'
BUDGET = final.BASE / 'budget.json'
CHILD = final.BASE / ('budget-' + PARTITION_ID + '.jsonl')
AUTHORITY = final.AUTHORITY
AUTHORITY_CAP = final.AUTHORITY_CAP
AUTHORITY_HOLD_ID = final.AUTHORITY_HOLD_ID
AUTHORITY_APPROVAL_SHA = final.AUTHORITY_APPROVAL_SHA
AUTHORITY_DECISION_KEY = final.AUTHORITY_DECISION_KEY
AUTHORITY_SNAPSHOT = final.AUTHORITY_SNAPSHOT
AUTHORITY_SNAPSHOT_SHA = final.AUTHORITY_SNAPSHOT_SHA
SOURCES = (
    'scripts/gemma26_v2_postabort_054_060.py',
    'scripts/gemma26_v2_final_suffix.py',
    'scripts/gemma26_v2_fifth_suffix.py',
    'scripts/gemma26_v2_third_continuation.py',
    'scripts/gemma26_on_fresh_repeat_execution_v2.py',
    'scripts/gemma26_on_fresh_repeat_study_v2.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/paid_budget_partitions_v3.py',
    'scripts/openrouter_budget_v3.py',
    'scripts/prompt_admission.py',
    'results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl',
)
ROUTE_FIELDS = final.ROUTE_FIELDS


def sha(path):
    return third.sha(path)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    import hashlib
    return hashlib.sha256(canonical(value)).hexdigest()


def stage_paths():
    return {key: STAGE / f'suffix.{extension}' for key, extension in {
        'claim': 'claim.json', 'journal': 'journal.jsonl',
        'attempts': 'attempts.jsonl', 'responses': 'responses.jsonl',
        'wire': 'wire.jsonl'}.items()}


def prior_gate():
    """Bind the original aborted phase, all seven valid calls, and the unsent tail."""
    final.verify()
    if sha(AUDIT) != AUDIT_SHA:
        raise ValueError('Pinned postabort terminal audit differs')
    audit = json.loads(AUDIT.read_text())
    original_paths = final.stage_paths()
    sources = {
        'controller': final.__file__,
        'manifest': final.BASE / 'manifest.json',
        'budget_manifest': BUDGET,
        'root_review': final.STAGE / 'suffix.root-review.json',
        **original_paths,
    }
    if any(sha(path) != audit['source_sha256'].get(key)
           for key, path in sources.items()):
        raise ValueError('Original seven-call source or abort changed')
    journal, attempts, responses, wire = (third.rows(original_paths[key])
        for key in ('journal', 'attempts', 'responses', 'wire'))
    old_manifest = json.loads((final.BASE / 'manifest.json').read_text())
    old_claim = json.loads(original_paths['claim'].read_text())
    sent = [f'DEV-{n:03d}' for n in range(47, 54)]
    expected_events = ['phase_started'] + [e for _ in sent for e in
        ('request_intent', 'request_started', 'request_finished')] + ['phase_aborted']
    if (audit.get('schema') != 'gemma26-on-v2-postabort-preflight-audit-v1' or
            audit.get('status') != 'aborted_after_seven_valid_before_dev054_request_intent' or
            audit.get('counts') != {'valid': 7, 'failed': 0, 'never_sent_stage': 7} or
            audit.get('attempted_ids') != sent or
            audit.get('next_never_sent_ids') != list(IDS) or
            audit.get('reference_labels_read') is not False or
            audit.get('score') is not None or
            audit.get('partition_id') != PARTITION_ID or
            audit.get('manifest_sha256') != sha(final.BASE / 'manifest.json') or
            audit.get('child_prefix_event_count') != 15 or
            audit.get('unknown_charge_upper_bound_usd') != '0' or
            old_claim.get('ids') != list(final.IDS) or
            old_claim.get('manifest_sha256') != audit['manifest_sha256'] or
            [x.get('event') for x in journal] != expected_events or
            journal[-1] != audit.get('journal_terminal_event') or
            [x.get('id') for x in attempts] != sent or
            [x.get('id') for x in responses] != sent or
            [x.get('id') for x in wire] != sent or
            any(a.get('status') != 'ok' or a.get('billing_ok') is not True or
                a.get('cost_unknown') is not False or
                a.get('request') != expected['payload'] or
                a.get('request_sha256') != expected['request_sha256'] or
                a.get('attempt_id') != r.get('attempt_id') or
                a.get('attempt_id') != w.get('attempt_id') or
                w.get('http_status') != 200
                for a, r, w, expected in zip(attempts, responses, wire,
                                               old_manifest['requests'][:7])) or
            sum((paid.number(a['observed_cost_usd']) for a in attempts),
                Decimal(0)) != paid.number(audit['known_actual_usd'])):
        raise ValueError('Original terminal prefix or never-sent IDs differ')
    # The child grows under the successor. Its historical prefix must not.
    raw_lines = CHILD.read_bytes().splitlines(keepends=True)
    if (len(raw_lines) < 15 or
            hashlib.sha256(b''.join(raw_lines[:15])).hexdigest() !=
            audit['child_prefix_sha256']):
        raise ValueError('Original child budget prefix differs')
    return {'audit_sha256': AUDIT_SHA,
            'original_manifest_sha256': audit['manifest_sha256'],
            'child_prefix_sha256': audit['child_prefix_sha256'],
            'last_sent_id': 'DEV-053', 'never_sent_ids': list(IDS),
            'route_fields': {key: attempts[-1]['provider_endpoint'].get(key)
                             for key in ROUTE_FIELDS}}


def selected_requests():
    plan = study.verify('fresh3', first.PLAN_SHAS['fresh3'])
    requests = plan['conditions']['P2']['development'][53:60]
    if [item.get('record_id') for item in requests] != list(IDS):
        raise ValueError('Frozen DEV-054..060 slice differs')
    for item in requests:
        if study.digest(json.dumps(item['payload'], sort_keys=True)) != item['request_sha256']:
            raise ValueError('Frozen request payload differs')
    return requests


def manifest_value():
    gate = prior_gate()
    requests = selected_requests()
    if CAP < len(requests) * RESERVE:
        raise ValueError('Seven-request worst-case reserve exceeds remaining child cap')
    return {'schema': SCHEMA, 'status': 'offline_prepared_reuse_active_allocation_no_dispatch',
            'configuration_id': study.CONFIG, 'fresh_pass': 'fresh3',
            'condition': 'P2', 'stage': 'suffix', 'reference_labels_read': False,
            'prior_gate_sha256': digest(gate), 'prior': gate,
            'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
            'plan_sha256': first.PLAN_SHAS['fresh3'],
            'original_manifest_sha256': gate['original_manifest_sha256'],
            'postabort_audit_sha256': AUDIT_SHA,
            'child_cap_usd': str(CAP), 'per_request_reserve_usd': str(RESERVE),
            'partition_id': PARTITION_ID,
            'ids': list(IDS), 'remaining_unsent_after_success': list(REMAINDER),
            'requests': requests}


def prepare():
    path = BASE / 'manifest.json'
    value = manifest_value()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        import os
        os.fsync(out.fileno())
    return sha(path)


def verify():
    path = BASE / 'manifest.json'
    saved = json.loads(path.read_text())
    if saved != manifest_value():
        raise ValueError('Final suffix manifest or pinned source differs')
    return saved, sha(path)


def budget_entry(path):
    path = Path(path).resolve()
    if path != BUDGET.resolve():
        raise ValueError('Existing final child budget path differs')
    entry = final.budget_entry(path)
    if sha(path) != json.loads(AUDIT.read_text())['source_sha256']['budget_manifest']:
        raise ValueError('Original allocation manifest differs')
    return entry


def expected_review(manifest, manifest_sha, budget_path, authority_head_sha):
    budget_entry(budget_path)
    if (not isinstance(authority_head_sha, str) or len(authority_head_sha) != 64 or
            any(char not in '0123456789abcdef' for char in authority_head_sha)):
        raise ValueError('Reviewed global authority head hash required')
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': manifest_sha,
            'controller_sha256': manifest['source_sha256'][SOURCES[0]],
            'prior_gate_sha256': manifest['prior_gate_sha256'],
            'budget_manifest_sha256': sha(budget_path),
            'global_authority_head_sha256': authority_head_sha,
            'global_authority_approval_sha256': AUTHORITY_APPROVAL_SHA,
            'global_authority_hold_usd': str(CAP),
            'postabort_audit_sha256': AUDIT_SHA,
            'global_authority_hold_id': AUTHORITY_HOLD_ID,
            'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
            'fresh_pass': 'fresh3', 'condition': 'P2', 'stage': 'suffix',
            'ids': list(IDS),
            'request_sha256': [r['request_sha256'] for r in manifest['requests']],
            'reference_labels_sent': False}


def check_existing_authority(path, expected_head_sha):
    """Read the already approved hold under a lock; never append a second hold."""
    if sha(AUTHORITY_SNAPSHOT) != AUTHORITY_SNAPSHOT_SHA:
        raise ValueError('Postapproval authority snapshot changed')
    baseline = [json.loads(line) for line in AUTHORITY_SNAPSHOT.read_bytes().splitlines()]
    with Path(path).open('rb') as ledger:
        fcntl.flock(ledger, fcntl.LOCK_SH | fcntl.LOCK_NB)
        raw = ledger.read()
        if (not raw or not raw.endswith(b'\n') or
                hashlib.sha256(raw).hexdigest() != expected_head_sha):
            raise ValueError('Reviewed global authority head changed')
        events = [json.loads(line) for line in raw.splitlines()]
        if (events[:len(baseline)] != baseline or
                events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                              'cap_usd': str(AUTHORITY_CAP),
                              'decision_key': AUTHORITY_DECISION_KEY,
                              'approval_sha256': AUTHORITY_APPROVAL_SHA}):
            raise ValueError('Global authority provenance changed')
        total = Decimal(0)
        seen = set()
        for event in events[1:]:
            if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                    event['event'] != 'hold' or event['id'] in seen or
                    not isinstance(event['source_sha256'], str) or
                    len(event['source_sha256']) != 64):
                raise ValueError('Malformed or duplicate global hold')
            amount = Decimal(event['usd'])
            if not amount.is_finite() or amount <= 0:
                raise ValueError('Invalid global hold amount')
            seen.add(event['id'])
            total += amount
        audit = json.loads(AUDIT.read_text())
        existing = audit['existing_global_hold']
        if (existing not in events or existing['id'] != AUTHORITY_HOLD_ID or
                existing['usd'] != str(CAP) or total > AUTHORITY_CAP or
                hashlib.sha256(canonical(existing)).hexdigest() !=
                audit['global_hold_event_sha256']):
            raise ValueError('Existing global hold missing, changed, or cap exceeded')


def checked_route(plan, expected):
    model, endpoint, reserve = original.live_controls(plan, 'P2')
    if (reserve != RESERVE or
            any(endpoint.get(key) != expected.get(key) for key in ROUTE_FIELDS)):
        raise ValueError('Exact Gemma endpoint or reserve changed')
    return model, endpoint


def run(review_path, budget_path, env_file=None):
    manifest, manifest_sha = verify()
    paths = stage_paths()
    review_path = Path(review_path).resolve()
    if review_path != (STAGE / 'suffix.root-review.json').resolve():
        raise ValueError('Postabort suffix root receipt path differs')
    review = json.loads(review_path.read_text())
    if review != expected_review(manifest, manifest_sha, budget_path,
                                 review.get('global_authority_head_sha256')):
        raise ValueError('Postabort suffix root review differs')
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Postabort suffix already claimed; no replay')
    budget_entry(budget_path)
    plan = study.verify('fresh3', first.PLAN_SHAS['fresh3'])
    model, endpoint = checked_route(plan, manifest['prior']['route_fields'])
    ledger = partitions.open_partition(third.MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        _, pending, blocked = ledger.state()
        audit = json.loads(AUDIT.read_text())
        if (ledger.cap != CAP or ledger.master_cap != Decimal('12.38') or
                pending or blocked or ledger.closed or
                len(ledger.events) != audit['child_prefix_event_count'] or
                sha(CHILD) != audit['child_prefix_sha256'] or
                ledger.accounted() != paid.number(audit['known_actual_usd']) or
                ledger.accounted() + len(IDS) * RESERVE > CAP):
            raise ValueError('Existing child unavailable for seven-call reserve')
        token = paid.load_key(env_file)
        check_existing_authority(AUTHORITY, review['global_authority_head_sha256'])
        STAGE.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            original.durable(out, {'schema': SCHEMA + '-claim', 'series_id': SCHEMA,
                'manifest_sha256': manifest_sha, 'review_sha256': sha(review_path),
                'budget_manifest_sha256': sha(budget_path), 'ids': list(IDS),
                'global_authority_hold_id': AUTHORITY_HOLD_ID,
                'global_authority_hold_usd': str(CAP),
                'postabort_audit_sha256': AUDIT_SHA,
                'claimed_utc': original.utc()})
        completed = True
        with paths['journal'].open('x') as journal, paths['attempts'].open('x') as attempts, \
             paths['responses'].open('x') as responses, paths['wire'].open('x') as wire:
            original.durable(journal, {'event': 'phase_started', 'series_id': SCHEMA,
                'fresh_pass': 'fresh3', 'condition': 'P2', 'stage': 'suffix',
                'claim_sha256': sha(paths['claim']), 'utc': original.utc()})
            for request in manifest['requests']:
                for name, expected in manifest['source_sha256'].items():
                    if sha(ROOT / name) != expected:
                        raise ValueError('Pinned runtime source changed: ' + name)
                if digest(prior_gate()) != manifest['prior_gate_sha256']:
                    raise ValueError('Postabort terminal prefix changed')
                model, endpoint = checked_route(plan, manifest['prior']['route_fields'])
                if (ledger.accounted() + RESERVE > CAP):
                    completed = False
                    original.durable(journal, {'event': 'phase_stopped',
                        'id': request['record_id'], 'reason': 'child_cap_before_send',
                        'utc': original.utc()})
                    break
                rid = request['record_id']
                original.durable(journal, {'event': 'request_intent', 'id': rid,
                    'request_sha256': request['request_sha256'], 'utc': original.utc()})
                attempt_id = ledger.reserve(RESERVE, rid)
                original.durable(journal, {'event': 'request_started', 'id': rid,
                    'attempt_id': attempt_id, 'request_sha256': request['request_sha256'],
                    'utc': original.utc()})
                record = {'id': rid, 'series_id': SCHEMA, 'fresh_pass': 'fresh3',
                    'condition': 'P2', 'phase': 'suffix', 'attempt_id': attempt_id,
                    'request': request['payload'], 'request_sha256': request['request_sha256'],
                    'manifest_sha256': manifest_sha, 'requested_model': study.MODEL,
                    'reasoning_effort': study.EFFORT, 'provider_endpoint': endpoint,
                    'model_catalog_entry': model, 'reference_labels_read': False,
                    'reserved_cost_usd': str(RESERVE), 'budget_partition_id': PARTITION_ID,
                    'started_utc': original.utc()}
                actual = None
                started = time.perf_counter()
                wire_before = wire.tell()
                try:
                    body = original.fetch_captured(request['payload'], token, wire, rid,
                                                   attempt_id, request['request_sha256'])
                    record['raw_response'] = body
                    original.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                        'request_sha256': request['request_sha256'],
                        'raw_response': body, 'received_utc': original.utc()})
                    if isinstance(body, dict):
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            actual = paid.number(usage['cost'])
                    record.update(original.classify(body, model, endpoint))
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, original.CapturedHTTPError):
                        record.update(http_status=exc.status, error_body=exc.body,
                                      error_headers=exc.headers)
                        original.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                            'request_sha256': request['request_sha256'],
                            'http_status': exc.status, 'error_body': exc.body,
                            'error_headers': exc.headers, 'received_utc': original.utc()})
                    elif wire.tell() > wire_before:
                        original.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                            'request_sha256': request['request_sha256'],
                            'capture_error': type(exc).__name__,
                            'received_utc': original.utc()})
                billing_ok = ledger.settle(attempt_id, actual)
                record.update(elapsed_seconds=time.perf_counter() - started,
                    timing_boundary='Client request through raw capture and billing settlement; not pure inference time.',
                    observed_cost_usd=str(actual) if actual is not None else None,
                    cost_unknown=actual is None, billing_ok=billing_ok)
                if record.get('raw_response') is not None:
                    diagnostic = audit_response(record, 'openrouter_paid_v1',
                                                endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                original.durable(attempts, record)
                original.durable(journal, {'event': 'request_finished', 'id': rid,
                    'attempt_id': attempt_id, 'status': record['status'],
                    'billing_ok': billing_ok, 'cost_unknown': record['cost_unknown'],
                    'observed_cost_usd': record['observed_cost_usd'], 'utc': original.utc()})
                if not original.continue_record(record, 'development'):
                    completed = False
                    original.durable(journal, {'event': 'phase_stopped', 'id': rid,
                        'reason': record['status'], 'utc': original.utc()})
                    break
            if completed:
                original.durable(journal, {'event': 'phase_completed',
                    'request_count': len(IDS), 'ids': list(IDS),
                    'utc': original.utc()})
        return completed
    finally:
        if paths['journal'].exists():
            events = third.rows(paths['journal'])
            if not events or events[-1].get('event') not in (
                    'phase_completed', 'phase_stopped', 'phase_aborted'):
                with paths['journal'].open('a') as out:
                    original.durable(out, {'event': 'phase_aborted',
                        'reason': 'exception_or_interruption', 'utc': original.utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--root-review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        print(verify()[1])
    else:
        if not args.root_review_receipt or not args.budget_manifest:
            parser.error('run requires --root-review-receipt and --budget-manifest')
        print(json.dumps({'completed': run(args.root_review_receipt,
                                           args.budget_manifest, args.env_file)}))


if __name__ == '__main__':
    main()
