#!/usr/bin/env python3
"""Reviewed, one-shot Solar Decide native P0 smoke; preparation is offline.

No allocation or inference occurs during prepare/verify. Run needs a distinct
already allocated v3 child and an exact root review receipt. No retries.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from development_benchmark import ROOT
from openrouter_paid_benchmark import durable, number, load_key
import openrouter_decision_smoke as native
import paid_budget_partitions_v3 as partitions
import solar_decide_offline_plan as solar

KIND = 'solar-decide-openrouter-upstage-native-p0-smoke-v1'
PLAN_ID = 'solar-decide-openrouter-upstage-native-p0-v1'
PARTITION_ID = 'solar-decide-upstage-p0-smoke-v1'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
DEFAULT_BASE = ROOT / 'results/solar-decide-native-smoke-v1'
PUBLIC_AUDIT = ROOT / 'results/route-audits/solar-decide-public-20261001'
SOURCE_PATHS = (
    'scripts/solar_decide_offline_plan.py', 'scripts/openrouter_decision_smoke.py',
    'scripts/jev_benchmark.py', 'scripts/paid_budget_partitions_v3.py',
    'scripts/openrouter_budget_v3.py', 'scripts/openrouter_paid_benchmark.py',
    'scripts/openrouter_benchmark.py', 'scripts/solar_decide_smoke_v1.py',
)
BOUND = solar.CONTEXT * max(solar.PROMPT_RATE, solar.CACHE_RATE) + Decimal(471859) * solar.OUTPUT_RATE
THREE_BOUND = 3 * BOUND
ENDPOINT_URL = native.CATALOG_URL.format(model=solar.MODEL)
MAX_BODY = 2_000_000


def sha(path):
    return native.sha(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def fetch_endpoint():
    request = urllib.request.Request(ENDPOINT_URL, headers={'Accept': 'application/json'}, method='GET')
    with native.OPENER.open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Solar endpoint lookup failed')
        raw = response.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Solar endpoint response too large')
    value = json.loads(raw)
    solar.validate_catalog(value)
    return raw, value


def manifest_value(root=ROOT, audit=PUBLIC_AUDIT):
    root, audit = Path(root), Path(audit)
    plan = solar.build_plans(root)[PLAN_ID]
    if plan['status'] != 'prepared_not_admitted' or plan['condition'] != 'P0' or plan['provider_tag'] != 'upstage':
        raise ValueError('Solar prepared plan identity differs')
    audit_raw = (audit / 'endpoints.json').read_bytes()
    solar.validate_catalog(json.loads(audit_raw))
    requests = plan['requests'][:3]
    if len(requests) != 3 or [r['id'] for r in requests] != plan['smoke_ids']:
        raise ValueError('Solar first three inputs differ')
    for request in requests:
        if native.sha(native.canonical(request['payload'])) != request['payload_sha256']:
            raise ValueError('Solar frozen payload differs')
    return {
        'kind': KIND, 'status': 'prepared_not_admitted', 'reference_labels_read': False,
        'model': solar.MODEL, 'expected_returned_model': solar.VERSION,
        'provider': solar.PROVIDER, 'provider_tag': 'upstage', 'api_url': native.DECISIONS_URL,
        'condition': 'P0', 'plan_sha256': native.sha(native.canonical(plan)),
        'plan_source_sha256': plan['source_sha256'],
        'source_sha256': {name: sha(root / name) for name in SOURCE_PATHS},
        'input_file_sha256': plan['input_file_sha256'], 'policy_sha256': plan['policy_sha256'],
        'saved_endpoint_sha256': plan['endpoint_snapshot']['sha256'],
        'fresh_public_endpoint_sha256': native.sha(audit_raw),
        'fresh_public_audit_path': str(audit.relative_to(root)),
        'per_request_full_context_bound_usd': str(BOUND),
        'three_record_bound_usd': str(THREE_BOUND),
        'budget_master_cap_usd': '12.38', 'budget_partition_id': PARTITION_ID,
        'smoke_ids': [r['id'] for r in requests], 'requests': requests,
    }


def prepare(base=DEFAULT_BASE, root=ROOT, audit=PUBLIC_AUDIT):
    base = Path(base)
    value = manifest_value(root, audit)
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'manifest.json').open('x') as out:
        durable(out, value)
    return native.sha(native.canonical(value))


def verify(base=DEFAULT_BASE, root=ROOT, audit=PUBLIC_AUDIT):
    path = Path(base) / 'manifest.json'
    saved = json.loads(path.read_text())
    rebuilt = manifest_value(root, audit)
    if saved != rebuilt:
        raise ValueError('Solar smoke manifest or source drift')
    return saved, native.sha(native.canonical(saved))


def expected_receipt(manifest, digest, budget_manifest):
    return {'kind': KIND + '-root-review', 'approved': True,
            'manifest_sha256': digest, 'runner_sha256': manifest['source_sha256']['scripts/solar_decide_smoke_v1.py'],
            'budget_manifest_sha256': sha(budget_manifest), 'budget_partition_id': PARTITION_ID,
            'smoke_ids': manifest['smoke_ids'], 'three_record_bound_usd': str(THREE_BOUND),
            'reference_labels_sent': False}


def verify_receipt(path, manifest, digest, budget_manifest, base):
    path = Path(path).resolve()
    if path != (Path(base) / 'smoke.root-review.json').resolve():
        raise ValueError('Wrong Solar root review path')
    receipt = json.loads(path.read_text())
    if any(receipt.get(k) != v for k, v in expected_receipt(manifest, digest, budget_manifest).items()):
        raise ValueError('Solar root review receipt differs')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Named root reviewer required')
    return receipt


def post(payload, token):
    request = urllib.request.Request(native.DECISIONS_URL, data=native.canonical(payload), method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with native.OPENER.open(request, timeout=60) as response:
            status, raw = response.status, response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Solar response too large; cost remains unknown')
    return status, raw


def validate_returned(body):
    route = {'version': solar.VERSION, 'provider': solar.PROVIDER, 'context': solar.CONTEXT}
    return native.validate_response(body, route)


def run(receipt_path, budget_manifest, base=DEFAULT_BASE, root=ROOT,
        audit=PUBLIC_AUDIT, env_file=None, fetch=fetch_endpoint, send=post,
        open_child=partitions.open_partition):
    base, budget_manifest = Path(base), Path(budget_manifest)
    manifest, digest = verify(base, root, audit)
    verify_receipt(receipt_path, manifest, digest, budget_manifest, base)
    paths = {name: base / ('smoke.' + name) for name in ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Solar smoke already claimed; no replay')
    # First public check and full three-request admission occur before a claim.
    _, initial_route = fetch()
    solar.validate_catalog(initial_route)
    ledger = open_child(MASTER, budget_manifest, PARTITION_ID, solar.MODEL, solar.PROVIDER, 'native-decisions-P0-smoke')
    try:
        if ledger.master_cap != Decimal('12.38'):
            raise ValueError('Solar master cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + THREE_BOUND > ledger.cap:
            raise ValueError('Solar child lacks full three-request bound')
        token = load_key(env_file)
        with paths['claim.json'].open('x') as out:
            durable(out, {'kind': KIND, 'manifest_sha256': digest,
                          'root_review_sha256': sha(receipt_path),
                          'budget_manifest_sha256': sha(budget_manifest),
                          'claimed_utc': now(), 'reference_labels_sent': False})
        with paths['journal.jsonl'].open('x') as journal, paths['raw.jsonl'].open('x') as raw_file, \
             paths['attempts.jsonl'].open('x') as attempts, paths['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'stage_started', 'utc': now(), 'manifest_sha256': digest})
            for item in manifest['requests']:
                rid = item['id']
                try:
                    # Recheck source and critical live endpoint before every request.
                    verify(base, root, audit)
                    route_raw, route = fetch()
                    solar.validate_catalog(route)
                    if ledger.accounted() + BOUND > ledger.cap:
                        raise ValueError('Solar child has insufficient reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                                      'payload_sha256': item['payload_sha256'], 'utc': now()})
                    attempt = ledger.reserve(BOUND, rid)
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                      'payload_sha256': item['payload_sha256'],
                                      'live_endpoint_sha256': native.sha(route_raw),
                                      'live_endpoint_base64': base64.b64encode(route_raw).decode('ascii'),
                                      'utc': now()})
                    started = now(); t0 = time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                                           'error_type': type(error).__name__, 'cost_unknown': True,
                                           'reserved_cost_usd': str(BOUND), 'utc': now()})
                        durable(journal, {'event': 'stage_stopped', 'id': rid,
                                          'reason': 'transport_outcome_unknown', 'utc': now()})
                        raise
                    ended = now(); elapsed = time.perf_counter_ns() - t0
                    durable(raw_file, {'id': rid, 'attempt_id': attempt,
                                       'payload_sha256': item['payload_sha256'], 'http_status': status,
                                       'response_sha256': native.sha(wire),
                                       'response_base64': base64.b64encode(wire).decode('ascii'),
                                       'request_started_utc': started, 'request_ended_utc': ended,
                                       'client_request_elapsed_ns': elapsed})
                    try:
                        body = json.loads(wire)
                    except (ValueError, UnicodeDecodeError):
                        body = None
                    actual = native.response_cost(body)
                    if actual is None:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'unknown_cost',
                                           'http_status': status, 'cost_unknown': True,
                                           'reserved_cost_usd': str(BOUND)})
                        durable(journal, {'event': 'stage_stopped', 'id': rid,
                                          'reason': 'unknown_cost', 'utc': now()})
                        raise ValueError('Unknown Solar cost; full reservation retained')
                    billing_ok = ledger.settle(attempt, actual)
                    if not billing_ok:
                        durable(attempts, {'id': rid, 'attempt_id': attempt,
                                           'status': 'observed_cost_over_bound',
                                           'http_status': status, 'cost_unknown': False,
                                           'reserved_cost_usd': str(BOUND),
                                           'actual_cost_usd': str(actual)})
                        durable(journal, {'event': 'stage_stopped', 'id': rid,
                                          'reason': 'observed_cost_over_bound', 'utc': now()})
                        raise ValueError('Solar ledger blocked by observed cost')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                                           'http_status': status, 'cost_unknown': False,
                                           'actual_cost_usd': str(actual)})
                        durable(journal, {'event': 'stage_stopped', 'id': rid,
                                          'reason': 'http_error', 'utc': now()})
                        raise ValueError('Solar provider returned HTTP error; no retry')
                    try:
                        prediction = validate_returned(body)
                    except ValueError as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'invalid_native_response',
                                           'error_type': type(error).__name__, 'cost_unknown': False,
                                           'actual_cost_usd': str(actual)})
                        durable(journal, {'event': 'stage_stopped', 'id': rid,
                                          'reason': 'invalid_native_response', 'utc': now()})
                        raise
                    durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'ok',
                                       'http_status': status, 'cost_unknown': False,
                                       'actual_cost_usd': str(actual),
                                       'response_sha256': native.sha(wire)})
                    durable(parsed, {'id': rid, 'attempt_id': attempt, 'prediction': prediction,
                                     'returned_model': body['model'], 'returned_provider': body['provider'],
                                     'response_sha256': native.sha(wire), 'usage': body['usage']})
                    durable(journal, {'event': 'request_finished', 'id': rid,
                                      'attempt_id': attempt, 'utc': now()})
                except BaseException:
                    raise
            durable(journal, {'event': 'stage_completed', 'utc': now(), 'count': 3})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--base', type=Path, default=DEFAULT_BASE)
    check = sub.add_parser('verify'); check.add_argument('--base', type=Path, default=DEFAULT_BASE)
    live = sub.add_parser('run'); live.add_argument('--base', type=Path, default=DEFAULT_BASE)
    live.add_argument('--root-review-receipt', type=Path, required=True)
    live.add_argument('--budget-manifest', type=Path, required=True)
    live.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare': print(prepare(args.base))
    elif args.command == 'verify': print(verify(args.base)[1])
    else: run(args.root_review_receipt, args.budget_manifest, args.base, env_file=args.env_file)


if __name__ == '__main__':
    main()
