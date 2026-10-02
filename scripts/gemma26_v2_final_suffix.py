#!/usr/bin/env python3
"""Admit only fresh3/P2 Gemma26 DEV-047..060 after the sealed DEV-046 suffix."""

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
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'gemma26-on-v2-final-suffix-047-060-v1'
BASE = study.BASE / 'final-suffix-047-060-v1'
STAGE = BASE / 'fresh3/P2'
PARTITION_ID = 'gemma26-on-v2-final-suffix-047-060-v1'
CAP = Decimal('0.30')
RESERVE = fifth.RESERVE
IDS = tuple(f'DEV-{n:03d}' for n in range(47, 61))
REMAINDER = ()
FIFTH_SHA = '0e9d7347c6210b501cbc3b2dd601909d9f75ed560f68d5881e9f9de13efd4ca2'
FIFTH_CONTROLLER_SHA = '3ebccf62dc1eabe9e09c665e8f457cf5e97d6a3c8f34024e47d47b6b9ed566c8'
TERMINAL_SHA = '0feaf71c7040eae7b5edecb010fb016f0706a8ec27e1678f1c5365c070acdab4'
TERMINAL = fifth.BASE / 'terminal-reconciliation-after-dev046.json'
CHILD = fifth.BASE / ('budget-' + fifth.PARTITION_ID + '.jsonl')
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
AUTHORITY_CAP = Decimal('10.00')
AUTHORITY_HOLD_ID = 'openrouter-gemma-final-047-060'
AUTHORITY_APPROVAL_SHA = '57d5ff76acd14f85d5e600c6527c310fc08f4eb66d45b1c25b9d778d770aaf8f'
AUTHORITY_DECISION_KEY = 'candidate-experience-benchmark/user-ten-dollar-tests-20261002'
AUTHORITY_SNAPSHOT = ROOT / 'results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl'
AUTHORITY_SNAPSHOT_SHA = '8df9eb02d667acad771ade2d2258e0344bf5178a52da07083d4a4bb30b7b6685'
SOURCES = (
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
ROUTE_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')


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
    """Recheck the sealed DEV-046 stage and its inherited failed attempts."""
    fifth.verify()
    if (sha(fifth.__file__) != FIFTH_CONTROLLER_SHA or
            sha(fifth.BASE / 'manifest.json') != FIFTH_SHA or
            sha(TERMINAL) != TERMINAL_SHA):
        raise ValueError('Pinned fifth controller, manifest or terminal differs')
    terminal = json.loads(TERMINAL.read_text())
    old = fifth.stage_paths()
    old['root_review'] = fifth.STAGE / 'suffix.root-review.json'
    old['budget_manifest'] = fifth.BASE / 'budget.json'
    old['child_ledger'] = CHILD
    actual = {key: sha(path) for key, path in old.items()}
    claim = json.loads(old['claim'].read_text())
    journal, attempts, responses, wire = (third.rows(old[key]) for key in
                                          ('journal', 'attempts', 'responses', 'wire'))
    prior_manifest = json.loads((fifth.BASE / 'manifest.json').read_text())
    if json.loads(old['root_review'].read_text()) != fifth.expected_review(
            prior_manifest, FIFTH_SHA, old['budget_manifest']):
        raise ValueError('Fifth root review differs')
    event = terminal.get('budget_reconciliation', {})
    if (terminal.get('schema') !=
            'gemma26-on-v2-fifth-suffix-terminal-reconciliation-v1' or
            terminal.get('status') != 'terminal_completed_partial_phase_unscored' or
            terminal.get('partition_id') != fifth.PARTITION_ID or
            terminal.get('stage') != 'fresh3/P2/suffix' or
            terminal.get('manifest_sha256') != FIFTH_SHA or
            terminal.get('attempted_ids') != list(fifth.IDS) or
            terminal.get('counts') != {'valid': 30, 'failed': 0,
                                       'never_sent_stage': 0} or
            terminal.get('next_never_sent_ids') != list(IDS + REMAINDER) or
            terminal.get('score') is not None or
            terminal.get('reference_labels_read') is not False or
            terminal.get('source_sha256') != actual or
            claim.get('manifest_sha256') != FIFTH_SHA or
            claim.get('review_sha256') != actual['root_review'] or
            claim.get('budget_manifest_sha256') != actual['budget_manifest'] or
            claim.get('ids') != list(fifth.IDS) or
            len(attempts) != len(fifth.IDS) or
            [x.get('id') for x in attempts] != list(fifth.IDS) or
            [x.get('id') for x in responses] != list(fifth.IDS) or
            [x.get('id') for x in wire] != list(fifth.IDS) or
            [x.get('event') for x in journal] != ['phase_started'] +
            [event for _ in fifth.IDS for event in
             ('request_intent', 'request_started', 'request_finished')] +
            ['phase_completed'] or
            journal[-1].get('ids') != list(fifth.IDS) or
            any(a.get('status') != 'ok' or a.get('billing_ok') is not True or
                a.get('cost_unknown') is not False or
                a.get('request') != expected['payload'] or
                a.get('request_sha256') != expected['request_sha256'] or
                a.get('attempt_id') != response.get('attempt_id') or
                a.get('attempt_id') != captured.get('attempt_id') or
                captured.get('http_status') != 200
                for a, response, captured, expected in
                zip(attempts, responses, wire, prior_manifest['requests'])) or
            event.get('event') != 'partition_reconciled' or
            event.get('partition_id') != fifth.PARTITION_ID or
            paid.number(event.get('known_actual_usd')) !=
                sum((paid.number(a['observed_cost_usd']) for a in attempts), Decimal(0)) or
            paid.number(event.get('unknown_upper_bound_usd')) != 0 or
            paid.number(event.get('unused_allocation_released_usd')) !=
                fifth.CAP - paid.number(event['known_actual_usd']) or
            event.get('child_sha256') != actual['child_ledger'] or
            event not in third.rows(third.MASTER)):
        raise ValueError('DEV-046 sealed stage or never-sent suffix differs')
    return {'fifth_manifest_sha256': FIFTH_SHA,
            'fifth_controller_sha256': FIFTH_CONTROLLER_SHA,
            'terminal_sha256': TERMINAL_SHA,
            'child_sha256': actual['child_ledger'],
            'last_sent_id': 'DEV-046', 'never_sent_ids': list(IDS + REMAINDER),
            'route_fields': {key: attempts[-1]['provider_endpoint'].get(key)
                             for key in ROUTE_FIELDS}}


def selected_requests():
    plan = study.verify('fresh3', first.PLAN_SHAS['fresh3'])
    requests = plan['conditions']['P2']['development'][46:60]
    if [item.get('record_id') for item in requests] != list(IDS):
        raise ValueError('Frozen DEV-047..060 slice differs')
    for item in requests:
        if study.digest(json.dumps(item['payload'], sort_keys=True)) != item['request_sha256']:
            raise ValueError('Frozen request payload differs')
    return requests


def manifest_value():
    gate = prior_gate()
    requests = selected_requests()
    if CAP < len(requests) * RESERVE:
        raise ValueError('Fourteen-request worst-case reserve exceeds child cap')
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_allocation_no_dispatch',
            'configuration_id': study.CONFIG, 'fresh_pass': 'fresh3',
            'condition': 'P2', 'stage': 'suffix', 'reference_labels_read': False,
            'prior_gate_sha256': digest(gate), 'prior': gate,
            'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
            'plan_sha256': first.PLAN_SHAS['fresh3'],
            'fifth_manifest_sha256': FIFTH_SHA,
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
    if path != (BASE / 'budget.json').resolve():
        raise ValueError('Final child budget path differs')
    value = json.loads(path.read_text())
    entries = value.get('partitions')
    expected_child = BASE / ('budget-' + PARTITION_ID + '.jsonl')
    if (value.get('version') != 'paid-partitions-v1' or
            value.get('master_ledger') != str(third.MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Final child budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != PARTITION_ID or entry.get('cap_usd') != str(CAP) or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) !=
            (study.MODEL, study.PROVIDER, study.EFFORT) or
            Path(entry.get('child_ledger', '')).resolve() != expected_child.resolve()):
        raise ValueError('Final child allocation route or cap differs')
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
            'global_authority_hold_id': AUTHORITY_HOLD_ID,
            'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
            'fresh_pass': 'fresh3', 'condition': 'P2', 'stage': 'suffix',
            'ids': list(IDS),
            'request_sha256': [r['request_sha256'] for r in manifest['requests']],
            'reference_labels_sent': False}


def hold_new_authority(path, expected_head_sha, review_sha):
    """Append a conservative cross-provider hold while holding the ledger lock."""
    if sha(AUTHORITY_SNAPSHOT) != AUTHORITY_SNAPSHOT_SHA:
        raise ValueError('Postapproval authority snapshot changed')
    baseline = [json.loads(line) for line in AUTHORITY_SNAPSHOT.read_bytes().splitlines()]
    with Path(path).open('r+') as ledger:
        fcntl.flock(ledger, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = ledger.read().encode()
        if (not raw or not raw.endswith(b'\n') or
                hashlib.sha256(raw).hexdigest() != expected_head_sha):
            raise ValueError('Reviewed global authority head changed')
        events = [json.loads(line) for line in raw.splitlines()]
        if (events[:len(baseline)] != baseline or
                events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                              'cap_usd': str(AUTHORITY_CAP),
                              'decision_key': AUTHORITY_DECISION_KEY,
                              'approval_sha256': AUTHORITY_APPROVAL_SHA}):
            raise ValueError('Cross-provider authority provenance changed')
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
        if AUTHORITY_HOLD_ID in seen or total + CAP > AUTHORITY_CAP:
            raise ValueError('Global postapproval authority exhausted or duplicate')
        ledger.seek(0, os.SEEK_END)
        original.durable(ledger, {'event': 'hold', 'id': AUTHORITY_HOLD_ID,
                                  'usd': str(CAP), 'source_sha256': review_sha})


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
        raise ValueError('Final suffix root receipt path differs')
    review = json.loads(review_path.read_text())
    if review != expected_review(manifest, manifest_sha, budget_path,
                                 review.get('global_authority_head_sha256')):
        raise ValueError('Final suffix root review differs')
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Final suffix already claimed; no replay')
    budget_entry(budget_path)
    plan = study.verify('fresh3', first.PLAN_SHAS['fresh3'])
    model, endpoint = checked_route(plan, manifest['prior']['route_fields'])
    ledger = partitions.open_partition(third.MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.cap != CAP or ledger.master_cap != Decimal('12.38') or
                pending or blocked or ledger.closed or ledger.accounted() + RESERVE > CAP):
            raise ValueError('Final child unavailable for full reserve')
        token = paid.load_key(env_file)
        hold_new_authority(AUTHORITY, review['global_authority_head_sha256'],
                           sha(review_path))
        STAGE.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            original.durable(out, {'schema': SCHEMA + '-claim', 'series_id': SCHEMA,
                'manifest_sha256': manifest_sha, 'review_sha256': sha(review_path),
                'budget_manifest_sha256': sha(budget_path), 'ids': list(IDS),
                'global_authority_hold_id': AUTHORITY_HOLD_ID,
                'global_authority_hold_usd': str(CAP),
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
                    raise ValueError('Prior failed attempt changed')
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
