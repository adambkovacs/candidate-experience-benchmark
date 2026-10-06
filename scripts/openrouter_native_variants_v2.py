#!/usr/bin/env python3
"""Separate, receipt-gated Kev/Jev native Choice smokes on the amended ledgers.

Preparation and verification are offline. Full passes deliberately have no
dispatch path until a reviewed all-record context proof and smoke inspection
are implemented in a later version.
"""
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
import openrouter_decision_smoke as decision
import openrouter_native_variants_plan as frozen
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions

BASE = ROOT / 'results/route-audits/native-variants-v2-20261006'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
MASTER = paid.LEDGER_PATH
AUTHORITY_CAP = Decimal('10.00')
AUTHORITY_DECISION_KEY = 'candidate-experience-benchmark/user-ten-dollar-tests-20261002'
AUTHORITY_APPROVAL_SHA = '57d5ff76acd14f85d5e600c6527c310fc08f4eb66d45b1c25b9d778d770aaf8f'
SCHEMA = 'openrouter-native-choice-smoke-v2'
IDS = ('DEV-001', 'DEV-002', 'DEV-003')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def paths(base, config):
    base = Path(base)
    return {'manifest': base / (config + '.json'), 'budget': base / config / 'budget.json',
            'receipt': base / config / 'smoke.root-review.json',
            'stage': base / config / 'smoke', 'lock': base / config / 'smoke.admission.lock'}


def build_manifest(config, *, root=ROOT, frozen_base=frozen.ROOT / 'results/route-audits/native-variants-offline-20260930'):
    original = frozen.build_plan(root)[config]
    source = Path(frozen_base) / (config + '.json')
    if source.read_bytes() != (json.dumps(original, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Frozen input manifest changed')
    route = decision.ROUTES[original['route']]
    requests = original['requests'][:3]
    if [r['id'] for r in requests] != list(IDS):
        raise ValueError('Smoke identities changed')
    for item in requests:
        if sha(decision.canonical(item['payload'])) != item['payload_sha256']:
            raise ValueError('Frozen request bytes changed')
    bound = decision.bound(route)
    return {'schema': SCHEMA + '-offline-plan', 'status': 'prepared_not_admitted',
            'inference_performed': False, 'reference_labels_read': False,
            'configuration_id': config, 'route': original['route'],
            'condition': original['condition'], 'model': route['model'],
            'provider': route['provider'], 'provider_tag': route['tag'],
            'returned_model': route['version'], 'context_tokens': route['context'],
            'frozen_manifest_path': str(source.relative_to(root)),
            'frozen_manifest_sha256': file_sha(source),
            'frozen_requests_sha256': original['requests_sha256'],
            'smoke_ids': list(IDS), 'request_sha256': [r['payload_sha256'] for r in requests],
            'per_request_full_context_bound_usd': str(bound),
            'smoke_bound_usd': str(3 * bound),
            'full_pass_bound_usd': str(60 * bound),
            'partition_id': config + '-smoke-v2',
            'global_hold_id': config + '-smoke-v2',
            'budget_master_cap_usd': '12.38', 'global_authority_cap_usd': str(AUTHORITY_CAP),
            'admission': {'reviewed_receipt_required': True,
                          'fresh_endpoint_required': True,
                          'child_allocation_required': True,
                          'global_hold_required': True,
                          'provider_accepted_all60_context_proof': False,
                          'inspected_smoke': False,
                          'full_pass_dispatch_enabled': False}}


def prepare(base=BASE, *, root=ROOT):
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    result = {}
    for config in frozen.build_plan(root):
        path = paths(base, config)['manifest']
        if path.exists():
            raise FileExistsError('Offline plan already exists')
        value = build_manifest(config, root=root)
        with path.open('x') as handle:
            handle.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        result[config] = file_sha(path)
    return result


def verify(config, base=BASE, *, root=ROOT):
    expected = build_manifest(config, root=root)
    path = paths(base, config)['manifest']
    if path.read_bytes() != (json.dumps(expected, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Offline smoke plan differs')
    return expected


def budget_identity(config, manifest, budget_path, *, base=BASE, master=MASTER):
    p = paths(base, config)
    if Path(budget_path).resolve() != p['budget'].resolve():
        raise ValueError('Wrong budget manifest path')
    budget = json.loads(Path(budget_path).read_text())
    child = p['budget'].parent / ('budget-' + manifest['partition_id'] + '.jsonl')
    entry = {'id': manifest['partition_id'], 'cap_usd': manifest['smoke_bound_usd'],
             'child_ledger': str(child.resolve()), 'model': manifest['model'],
             'provider': manifest['provider_tag'], 'reasoning': 'none'}
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(Path(master).resolve()) or
            budget.get('partitions') != [entry]):
        raise ValueError('Exact child allocation differs')
    if not child.is_file() or not child.stat().st_size:
        raise ValueError('Allocated child ledger absent')
    identity = {'manifest_sha256': file_sha(p['manifest']),
                'budget_manifest_sha256': file_sha(budget_path),
                'partition_id': manifest['partition_id'],
                'child_ledger': str(child.resolve()), 'cap_usd': entry['cap_usd']}
    return sha(decision.canonical(identity))


def expected_receipt(config, manifest, budget_path, hold_source, *, base=BASE):
    p = paths(base, config)
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'reviewer': 'root', 'configuration_id': config, 'stage': 'smoke',
            'manifest_sha256': file_sha(p['manifest']),
            'runner_sha256': file_sha(__file__),
            'budget_manifest_sha256': file_sha(budget_path),
            'partition_id': manifest['partition_id'],
            'child_cap_usd': manifest['smoke_bound_usd'],
            'global_hold_id': manifest['global_hold_id'],
            'global_hold_usd': manifest['smoke_bound_usd'],
            'global_hold_source_sha256': hold_source,
            'global_authority_cap_usd': str(AUTHORITY_CAP),
            'global_authority_approval_sha256': AUTHORITY_APPROVAL_SHA,
            'ids': list(IDS), 'request_sha256': manifest['request_sha256'],
            'reference_labels_sent': False}


def validate_receipt(config, manifest, receipt_path, budget_path, hold_source, *, base=BASE):
    p = paths(base, config)
    if Path(receipt_path).resolve() != p['receipt'].resolve():
        raise ValueError('Wrong review receipt path')
    receipt = json.loads(Path(receipt_path).read_text())
    head = receipt.get('global_authority_head_sha256')
    if (not isinstance(head, str) or len(head) != 64 or
            any(c not in '0123456789abcdef' for c in head) or
            receipt != {**expected_receipt(config, manifest, budget_path, hold_source, base=base),
                        'global_authority_head_sha256': head}):
        raise ValueError('Exact independent smoke review differs')
    return receipt


def hold_authority(path, hold_id, amount, source, expected_head, *, stage_path):
    """Lock the monotonic cross-provider authority and bind one stage hold."""
    with Path(path).open('r+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = handle.read().encode()
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if (not raw.endswith(b'\n') or not events or
                events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                              'cap_usd': str(AUTHORITY_CAP),
                              'decision_key': AUTHORITY_DECISION_KEY,
                              'approval_sha256': AUTHORITY_APPROVAL_SHA}):
            raise ValueError('Shared authority provenance differs')
        holds = {}
        total = Decimal(0)
        for event in events[1:]:
            if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                    event['event'] != 'hold' or event['id'] in holds):
                raise ValueError('Shared authority hold structure differs')
            value = Decimal(event['usd'])
            if not value.is_finite() or value <= 0:
                raise ValueError('Shared authority amount differs')
            holds[event['id']] = event
            total += value
        desired = {'event': 'hold', 'id': hold_id, 'usd': str(amount),
                   'source_sha256': source}
        if total > AUTHORITY_CAP or (hold_id in holds and holds[hold_id] != desired):
            raise ValueError('Shared authority conflict or exhausted')
        if Path(stage_path).exists():
            raise FileExistsError('Native stage already claimed; no replay')
        if hold_id not in holds:
            if sha(raw) != expected_head or total + amount > AUTHORITY_CAP:
                raise ValueError('Shared authority head changed or cap exhausted')
            handle.seek(0, os.SEEK_END)
            paid.durable(handle, desired)
        return desired


def execute(config, stage, receipt_path, budget_path, *, base=BASE, root=ROOT,
            master=MASTER, authority=AUTHORITY, catalog_fetch=decision.fetch_catalog,
            transport=decision.post, token=None, open_child=partitions.open_partition):
    if stage != 'smoke':
        raise ValueError('Full-pass dispatch blocked: reviewed provider-accepted all-60 context proof and inspected three-record smoke required')
    manifest = verify(config, base, root=root)
    p = paths(base, config)
    hold_source = budget_identity(config, manifest, budget_path, base=base, master=master)
    receipt = validate_receipt(config, manifest, receipt_path, budget_path, hold_source, base=base)
    if p['stage'].exists():
        raise FileExistsError('Native stage already claimed; no replay')
    route = decision.ROUTES[manifest['route']]
    catalog = catalog_fetch(route)
    decision.validate_endpoint(catalog, route)
    token = os.environ.get('OPENROUTER_API_KEY') if token is None else token
    if not token:
        raise ValueError('OPENROUTER_API_KEY required')
    p['lock'].parent.mkdir(parents=True, exist_ok=True)
    with p['lock'].open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if p['stage'].exists():
            raise FileExistsError('Native stage already claimed; no replay')
        ledger = open_child(master, budget_path, manifest['partition_id'],
                            manifest['model'], manifest['provider_tag'], 'none')
        try:
            _, pending, blocked = ledger.state()
            amount = Decimal(manifest['per_request_full_context_bound_usd'])
            cap = Decimal(manifest['smoke_bound_usd'])
            if (ledger.master_cap != Decimal('12.38') or ledger.cap != cap or
                    pending or blocked or ledger.closed or ledger.accounted() + cap > ledger.cap):
                raise ValueError('Exact allocated child cannot cover whole smoke')
            # Rebuild under the stage lock, then freeze the approved wire bytes.
            # A normal input/policy edit between initial verification and this
            # point must stop before the authority hold or any request.
            current_plan = frozen.build_plan(root)[config]
            if (current_plan['requests_sha256'] != manifest['frozen_requests_sha256'] or
                    sha(decision.canonical(current_plan['requests'])) != manifest['frozen_requests_sha256'] or
                    [item['id'] for item in current_plan['requests'][:3]] != manifest['smoke_ids'] or
                    [item['payload_sha256'] for item in current_plan['requests'][:3]] != manifest['request_sha256']):
                raise ValueError('Current input requests differ from reviewed smoke manifest')
            approved = []
            for item in current_plan['requests'][:3]:
                request = decision.canonical(item['payload'])
                if sha(request) != item['payload_sha256']:
                    raise ValueError('Current native request bytes differ from reviewed manifest')
                approved.append((item['id'], item['payload_sha256'], request))
            hold_authority(authority, manifest['global_hold_id'], cap, hold_source,
                           receipt['global_authority_head_sha256'], stage_path=p['stage'])
            p['stage'].mkdir(exist_ok=False)
            (p['stage'] / 'review-receipt.json').write_bytes(Path(receipt_path).read_bytes())
            (p['stage'] / 'endpoint-catalog.json').write_bytes(decision.canonical(catalog))
            known = Decimal(0)
            with (p['stage'] / 'attempts.jsonl').open('x') as attempts:
                for record_id, request_sha, request in approved:
                    payload = json.loads(request)
                    if sha(request) != request_sha:
                        raise ValueError('Approved wire bytes differ before reservation')
                    attempt = ledger.reserve(amount, manifest['partition_id'] + ':' + record_id)
                    paid.durable(attempts, {'stage': 'reserved', 'id': record_id,
                        'attempt_id': attempt, 'request_sha256': request_sha,
                        'reserved_cost_usd': str(amount), 'cost_unknown': True})
                    started = decision.utc_now()
                    paid.durable(attempts, {'stage': 'started', 'id': record_id,
                        'attempt_id': attempt, 'request_start_utc': started,
                        'request_base64': base64.b64encode(request).decode(), 'cost_unknown': True})
                    start_ns = time.monotonic_ns()
                    try:
                        status, raw = transport(payload, token)
                    except BaseException as error:
                        paid.durable(attempts, {'stage': 'transport_error', 'id': record_id,
                            'attempt_id': attempt, 'error_type': type(error).__name__,
                            'request_end_utc': decision.utc_now(),
                            'client_request_elapsed_ns': time.monotonic_ns() - start_ns,
                            'reserved_cost_usd': str(amount), 'cost_unknown': True})
                        raise
                    try:
                        body = json.loads(raw)
                        parse_error = None
                    except (ValueError, UnicodeDecodeError) as error:
                        body, parse_error = None, type(error).__name__
                    actual = decision.response_cost(body)
                    paid.durable(attempts, {'stage': 'response', 'id': record_id,
                        'attempt_id': attempt, 'http_status': status,
                        'raw_response_base64': base64.b64encode(raw).decode(),
                        'raw_response_sha256': sha(raw), 'body': body,
                        'parse_error_type': parse_error,
                        'request_start_utc': started, 'request_end_utc': decision.utc_now(),
                        'client_request_elapsed_ns': time.monotonic_ns() - start_ns,
                        'reserved_cost_usd': str(amount), 'cost_unknown': actual is None,
                        'actual_cost_usd': str(actual) if actual is not None else None})
                    if actual is None:
                        raise ValueError('Unknown provider cost; reservation remains pending')
                    if not ledger.settle(attempt, actual):
                        raise ValueError('Actual cost exceeded reserve; child blocked')
                    known += actual
                    if status != 200:
                        paid.durable(attempts, {'stage': 'parsed', 'id': record_id,
                            'attempt_id': attempt, 'valid': False, 'reason': 'non_200_http'})
                        raise ValueError('Provider returned non-200; no retry')
                    try:
                        prediction = decision.validate_response(body, route)
                    except ValueError as error:
                        paid.durable(attempts, {'stage': 'parsed', 'id': record_id,
                            'attempt_id': attempt, 'valid': False, 'reason': str(error)})
                        raise
                    paid.durable(attempts, {'stage': 'parsed', 'id': record_id,
                        'attempt_id': attempt, 'valid': True, 'prediction': prediction})
            completion = {'schema': SCHEMA + '-completion', 'configuration_id': config,
                'stage': 'smoke', 'ids': list(IDS), 'valid_count': 3,
                'manifest_sha256': file_sha(p['manifest']),
                'receipt_sha256': file_sha(receipt_path),
                'budget_manifest_sha256': file_sha(budget_path),
                'endpoint_catalog_sha256': file_sha(p['stage'] / 'endpoint-catalog.json'),
                'attempts_sha256': file_sha(p['stage'] / 'attempts.jsonl'),
                'known_actual_cost_usd': str(known), 'reference_labels_read': False}
            (p['stage'] / 'completion.json').write_text(json.dumps(completion, indent=2) + '\n')
            return completion
        finally:
            ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--configuration')
    parser.add_argument('--stage', default='smoke')
    parser.add_argument('--review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(json.dumps(prepare(), indent=2))
    elif args.action == 'verify':
        if not args.configuration:
            parser.error('--configuration required')
        print(json.dumps(verify(args.configuration)['admission'], indent=2))
    else:
        if not args.configuration or not args.review_receipt or not args.budget_manifest:
            parser.error('run requires configuration, review receipt and budget manifest')
        print(json.dumps(execute(args.configuration, args.stage, args.review_receipt,
                                 args.budget_manifest), indent=2))


if __name__ == '__main__':
    main()
