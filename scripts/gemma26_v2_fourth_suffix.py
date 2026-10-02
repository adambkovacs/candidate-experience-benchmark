#!/usr/bin/env python3
"""Admit only fresh3/P2 Gemma26 DEV-007..016 after the sealed DEV-006 failure."""

import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path
import time

from development_benchmark import ROOT
import gemma26_on_fresh_repeat_study_v2 as study
import gemma26_on_fresh_repeat_execution_v2 as original
import gemma26_v2_continuation as first
import gemma26_v2_third_continuation as third
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'gemma26-on-v2-fourth-suffix-007-016-v1'
BASE = study.BASE / 'fourth-suffix-007-016-v1'
STAGE = BASE / 'fresh3/P2'
PARTITION_ID = 'gemma26-on-v2-fourth-suffix-007-016-v1'
CAP = Decimal('0.20')
RESERVE = third.RESERVE
IDS = tuple(f'DEV-{n:03d}' for n in range(7, 17))
REMAINDER = tuple(f'DEV-{n:03d}' for n in range(17, 61))
THIRD_SHA = '75c0be273e0bbc0803efea87312b840101fb14d08c9707c85517e4527ae23408'
THIRD_CONTROLLER_SHA = 'f4d207e16f04937dfb5cd3a4405d03d4ca100ff00609a797d35778ef98646688'
TERMINAL_SHA = 'ec2bde5d2bd380f3df56d9241d006d5ffd466bdf481497b24f6997a485eb8f4c'
TERMINAL = third.OUTPUT / 'terminal-public-after-dev006.json'
RECONCILIATION = third.OUTPUT / 'terminal-reconciliation-after-dev006.json'
CHILD = third.OUTPUT / ('budget-' + third.PARTITION_ID + '.jsonl')
SOURCES = (
    'scripts/gemma26_v2_fourth_suffix.py',
    'scripts/gemma26_v2_third_continuation.py',
    'scripts/gemma26_on_fresh_repeat_execution_v2.py',
    'scripts/gemma26_on_fresh_repeat_study_v2.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/paid_budget_partitions_v3.py',
    'scripts/openrouter_budget_v3.py',
    'scripts/prompt_admission.py',
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
    """Recheck all older evidence, then the exact sealed DEV-006 attempt."""
    third.audit_prior()
    third.verify_manifest(THIRD_SHA)
    if sha(third.__file__) != THIRD_CONTROLLER_SHA or sha(TERMINAL) != TERMINAL_SHA:
        raise ValueError('Pinned third controller or DEV-006 terminal differs')
    terminal = json.loads(TERMINAL.read_text())
    old = third.stage_paths('fresh3', 'P2', 'suffix')
    old['review'] = third.review_path('fresh3', 'P2', 'suffix')
    third.verify_review(old['review'], json.loads((third.OUTPUT / 'manifest.json').read_text()),
                        THIRD_SHA, 'fresh3', 'P2', 'suffix')
    recon = json.loads(RECONCILIATION.read_text())
    source_hashes = terminal.get('source_sha256', {})
    actual = {key: sha(path) for key, path in old.items() if key != 'review'}
    actual['child_ledger'] = sha(CHILD)
    actual['terminal_reconciliation'] = sha(RECONCILIATION)
    requests = third.selected_requests('fresh3', 'P2', 'suffix')
    claim = json.loads(old['claim'].read_text())
    journal, attempts, responses, wire = (third.rows(old[key]) for key in
                                          ('journal', 'attempts', 'responses', 'wire'))
    failed = attempts[0] if len(attempts) == 1 else {}
    request = requests[0]
    if (terminal.get('schema') != 'gemma26-on-v2-third-interruption-terminal-public-v1' or
            terminal.get('status') != 'stopped_unscored' or
            terminal.get('manifest_sha256') != THIRD_SHA or
            terminal.get('new_failed_id') != 'DEV-006' or
            terminal.get('new_stage_attempted') != 1 or
            terminal.get('new_stage_never_sent_ids') != list(IDS + REMAINDER) or
            terminal.get('score') is not None or
            terminal.get('reference_labels_read') is not False or
            source_hashes != actual or
            claim.get('manifest_sha256') != THIRD_SHA or
            claim.get('root_review_sha256') != sha(old['review']) or
            claim.get('phase') != 'suffix' or
            [x.get('event') for x in journal] != ['phase_started', 'request_intent',
                 'request_started', 'request_finished', 'phase_stopped'] or
            [x.get('id') for x in journal[1:]] != ['DEV-006'] * 4 or
            [x.get('id') for x in responses] != ['DEV-006'] or
            [x.get('id') for x in wire] != ['DEV-006'] or
            failed.get('id') != 'DEV-006' or
            failed.get('request') != request['payload'] or
            failed.get('request_sha256') != request['request_sha256'] or
            failed.get('status') != 'service_error' or
            failed.get('http_status') != 429 or
            failed.get('cost_unknown') is not True or
            failed.get('billing_ok') is not False or
            paid.number(failed.get('reserved_cost_usd')) != RESERVE or
            wire[0].get('http_status') != 429 or
            wire[0].get('attempt_id') != failed.get('attempt_id') or
            responses[0].get('attempt_id') != failed.get('attempt_id') or
            journal[2].get('attempt_id') != failed.get('attempt_id') or
            journal[3].get('attempt_id') != failed.get('attempt_id') or
            recon.get('partition_id') != third.PARTITION_ID or
            paid.number(recon.get('known_actual_usd')) != 0 or
            paid.number(recon.get('unknown_upper_bound_usd')) != RESERVE or
            recon.get('child_sha256') != sha(CHILD) or
            recon not in third.rows(third.MASTER)):
        raise ValueError('DEV-006 sealed attempt or never-sent suffix differs')
    return {'third_manifest_sha256': THIRD_SHA,
            'third_controller_sha256': THIRD_CONTROLLER_SHA,
            'terminal_sha256': TERMINAL_SHA,
            'reconciliation_sha256': sha(RECONCILIATION),
            'child_sha256': sha(CHILD),
            'failed_id': 'DEV-006', 'never_sent_ids': list(IDS + REMAINDER),
            'route_fields': {key: failed['provider_endpoint'].get(key)
                             for key in ROUTE_FIELDS}}


def selected_requests():
    plan = study.verify('fresh3', first.PLAN_SHAS['fresh3'])
    requests = plan['conditions']['P2']['development'][6:16]
    if [item.get('record_id') for item in requests] != list(IDS):
        raise ValueError('Frozen DEV-007..016 slice differs')
    for item in requests:
        if study.digest(json.dumps(item['payload'], sort_keys=True)) != item['request_sha256']:
            raise ValueError('Frozen request payload differs')
    return requests


def manifest_value():
    gate = prior_gate()
    requests = selected_requests()
    if CAP < len(requests) * RESERVE:
        raise ValueError('Ten-request worst-case reserve exceeds child cap')
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_allocation_no_dispatch',
            'configuration_id': study.CONFIG, 'fresh_pass': 'fresh3',
            'condition': 'P2', 'stage': 'suffix', 'reference_labels_read': False,
            'prior_gate_sha256': digest(gate), 'prior': gate,
            'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
            'plan_sha256': first.PLAN_SHAS['fresh3'],
            'third_manifest_sha256': THIRD_SHA,
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
        raise ValueError('Fourth suffix manifest or pinned source differs')
    return saved, sha(path)


def budget_entry(path):
    path = Path(path).resolve()
    if path != (BASE / 'budget.json').resolve():
        raise ValueError('Fourth child budget path differs')
    value = json.loads(path.read_text())
    entries = value.get('partitions')
    expected_child = BASE / ('budget-' + PARTITION_ID + '.jsonl')
    if (value.get('version') != 'paid-partitions-v1' or
            value.get('master_ledger') != str(third.MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Fourth child budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != PARTITION_ID or entry.get('cap_usd') != str(CAP) or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) !=
            (study.MODEL, study.PROVIDER, study.EFFORT) or
            Path(entry.get('child_ledger', '')).resolve() != expected_child.resolve()):
        raise ValueError('Fourth child allocation route or cap differs')
    return entry


def expected_review(manifest, manifest_sha, budget_path):
    budget_entry(budget_path)
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': manifest_sha,
            'controller_sha256': manifest['source_sha256'][SOURCES[0]],
            'prior_gate_sha256': manifest['prior_gate_sha256'],
            'budget_manifest_sha256': sha(budget_path),
            'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
            'fresh_pass': 'fresh3', 'condition': 'P2', 'stage': 'suffix',
            'ids': list(IDS),
            'request_sha256': [r['request_sha256'] for r in manifest['requests']],
            'reference_labels_sent': False}


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
        raise ValueError('Fourth suffix root receipt path differs')
    if json.loads(review_path.read_text()) != expected_review(manifest, manifest_sha, budget_path):
        raise ValueError('Fourth suffix root review differs')
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Fourth suffix already claimed; no replay')
    budget_entry(budget_path)
    plan = study.verify('fresh3', first.PLAN_SHAS['fresh3'])
    model, endpoint = checked_route(plan, manifest['prior']['route_fields'])
    ledger = partitions.open_partition(third.MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.cap != CAP or ledger.master_cap != Decimal('12.38') or
                pending or blocked or ledger.closed or ledger.accounted() + RESERVE > CAP):
            raise ValueError('Fourth child unavailable for full reserve')
        token = paid.load_key(env_file)
        STAGE.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            original.durable(out, {'schema': SCHEMA + '-claim', 'series_id': SCHEMA,
                'manifest_sha256': manifest_sha, 'review_sha256': sha(review_path),
                'budget_manifest_sha256': sha(budget_path), 'ids': list(IDS),
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
