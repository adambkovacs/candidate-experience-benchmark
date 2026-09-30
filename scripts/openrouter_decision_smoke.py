#!/usr/bin/env python3
"""Gated OpenRouter native Decisions smoke. Preparation and verify never infer.

Live execution requires a separate reviewed receipt. The shared $10 master
BudgetLedger is locked across every request; no retry is automatic.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from development_benchmark import ROOT, KEYS, read_rows
from jev_benchmark import make_payload, parse_response
from openrouter_paid_benchmark import LEDGER_PATH, durable, number, select_rows
from openrouter_budget_v2 import BudgetLedger

BASE = ROOT / 'results/route-audits/decision-smoke-20260930'
DECISIONS_URL = 'https://openrouter.ai/api/alpha/decisions'
CATALOG_URL = 'https://openrouter.ai/api/v1/models/{model}/endpoints'
RATE = Decimal('0.000000042')
ROUTES = {
    'jev': {'model': 'typesafe/jev-1.13', 'version': 'typesafe/jev-1.13-20260917',
            'tag': 'typesafe', 'provider': 'TypeSafe', 'context': 32000},
    'kev': {'model': 'jaredpalmer/kev-4b', 'version': 'jaredpalmer/kev-4b-20260924',
            'tag': 'siliconflow/fp8', 'provider': 'SiliconFlow', 'context': 8192},
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect forbidden')


OPENER = urllib.request.build_opener(NoRedirect)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def policy_text():
    return (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]


def request_payload(feedback, policy, route):
    value = make_payload(feedback, policy, route['model'], 'official')
    # Both fields are documented provider routing controls on Decisions requests.
    value['provider'] = {'only': [route['tag']], 'allow_fallbacks': False,
                         'max_price': {'prompt': 0.042, 'completion': 0, 'request': 0, 'image': 0}}
    return value


def validate_endpoint(catalog, route):
    data = catalog.get('data') if isinstance(catalog, dict) else None
    if not isinstance(data, dict) or data.get('id') != route['model']:
        raise ValueError('Catalog model identity changed')
    architecture = data.get('architecture')
    if not isinstance(architecture, dict) or architecture.get('modality') != 'text->decisions' or architecture.get('output_modalities') != ['decisions']:
        raise ValueError('Native Decisions modality unavailable')
    endpoints = data.get('endpoints')
    if not isinstance(endpoints, list) or len(endpoints) != 1:
        raise ValueError('Require exactly one endpoint for the pinned model')
    endpoint = endpoints[0]
    if not isinstance(endpoint, dict) or any((
        endpoint.get('model_id') != route['model'], endpoint.get('tag') != route['tag'],
        endpoint.get('provider_name') != route['provider'],
        endpoint.get('name') != route['provider'] + ' | ' + route['version'],
        endpoint.get('status') != 0, endpoint.get('context_length') != route['context'],
    )):
        raise ValueError('Endpoint/provider/version/context changed')
    pricing = endpoint.get('pricing')
    if not isinstance(pricing, dict) or set(pricing) != {'prompt', 'completion', 'discount'}:
        raise ValueError('Unsupported price dimensions')
    if number(pricing['prompt']) != RATE or number(pricing['completion']) != 0 or number(pricing['discount']) != 0:
        raise ValueError('Price changed')
    if endpoint.get('supported_parameters') != []:
        raise ValueError('Endpoint parameter surface changed')
    return endpoint


def bound(route):
    # Full context bound covers user input and internal/template tokens; zero
    # completion and per-request tariffs are pinned by validate_endpoint.
    return Decimal(route['context']) * RATE


def build_manifest(catalogs):
    rows = select_rows(read_rows(ROOT / 'data/pilot/inputs.jsonl'), 'smoke', 1)
    policy = policy_text()
    manifest = {'kind': 'openrouter-native-decisions-smoke-preparation-v1',
                'inference_performed': False, 'reference_labels_read': False,
                'api_url': DECISIONS_URL, 'policy_sha256': sha(policy.encode()),
                'source_sha256': sha((ROOT / 'scripts/jev_benchmark.py').read_bytes()),
                'development_source_sha256': sha((ROOT / 'scripts/development_benchmark.py').read_bytes()),
                'runner_sha256': sha((ROOT / 'scripts/openrouter_decision_smoke.py').read_bytes()),
                'master_ledger_sha256': sha((ROOT / 'scripts/openrouter_budget_v2.py').read_bytes()),
                'base_ledger_sha256': sha((ROOT / 'scripts/openrouter_paid_benchmark.py').read_bytes()),
                'input_file_sha256': sha((ROOT / 'data/pilot/inputs.jsonl').read_bytes()),
                'routes': {}}
    for name, route in ROUTES.items():
        validate_endpoint(catalogs[name], route)
        requests = []
        for row in rows:
            payload = request_payload(row['feedback'], policy, route)
            requests.append({'id': row['id'], 'input_sha256': sha(row['feedback'].encode()),
                             'payload_sha256': sha(canonical(payload)), 'payload': payload})
        manifest['routes'][name] = {
            'model': route['model'], 'expected_returned_model': route['version'],
            'provider_tag': route['tag'], 'expected_returned_provider': route['provider'],
            'context_tokens': route['context'], 'input_usd_per_token': str(RATE),
            'output_usd_per_token': '0', 'per_request_bound_usd': str(bound(route)),
            'three_request_bound_usd': str(3 * bound(route)),
            'catalog_sha256': sha(canonical(catalogs[name])), 'requests': requests}
    return manifest


def load_prepared(base=BASE):
    catalogs = {name: json.loads((base / (name + '-endpoint.json')).read_text()) for name in ROUTES}
    saved = json.loads((base / 'manifest.json').read_text())
    rebuilt = build_manifest(catalogs)
    if saved != rebuilt:
        raise ValueError('Prepared manifest differs from source or endpoint snapshots')
    return saved


def fetch_catalog(route):
    url = CATALOG_URL.format(model=route['model'])
    request = urllib.request.Request(url, headers={'Accept': 'application/json'}, method='GET')
    with OPENER.open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Catalog request failed')
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Catalog response too large')
    return json.loads(raw)


def prepare(base=BASE):
    catalogs = {name: fetch_catalog(route) for name, route in ROUTES.items()}
    manifest = build_manifest(catalogs)
    base.mkdir(parents=True, exist_ok=True)
    for name, catalog in catalogs.items():
        with (base / (name + '-endpoint.json')).open('x') as output:
            output.write(json.dumps(catalog, indent=2) + '\n')
    with (base / 'manifest.json').open('x') as output:
        output.write(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return sha(canonical(manifest))


def validate_receipt(receipt, manifest, name):
    if not isinstance(receipt, dict) or receipt.get('approved') is not True:
        raise ValueError('Reviewed admission receipt required')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Receipt must name the reviewer')
    if receipt.get('manifest_sha256') != sha(canonical(manifest)) or receipt.get('route') != name:
        raise ValueError('Receipt does not bind this exact manifest and route')
    if receipt.get('max_reservation_usd') != manifest['routes'][name]['three_request_bound_usd']:
        raise ValueError('Receipt does not bind the three-request bound')


def validate_response(body, route):
    if not isinstance(body, dict) or body.get('provider') != route['provider']:
        raise ValueError('Returned provider mismatch')
    # Reuse Jev's exact four native Choice/distribution validator by passing
    # the pinned returned version, which differs from the request alias.
    prediction = parse_response(body, route['version'])
    usage = body.get('usage')
    if not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or not 0 <= usage['input_tokens'] <= route['context']:
        raise ValueError('Missing or out-of-context token usage')
    if type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0:
        raise ValueError('Missing output token usage')
    return prediction


def response_cost(body):
    usage = body.get('usage') if isinstance(body, dict) else None
    if not isinstance(usage, dict) or 'cost' not in usage:
        return None
    try:
        return number(usage['cost'])
    except ValueError:
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def post(payload, token):
    request = urllib.request.Request(DECISIONS_URL, data=canonical(payload), method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with OPENER.open(request, timeout=60) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        raw = error.read()
    return status, raw


def execute(name, receipt_path, base=BASE, ledger_path=LEDGER_PATH):
    if name not in ROUTES:
        raise ValueError('Unknown route')
    manifest = load_prepared(base)
    receipt = json.loads(Path(receipt_path).read_text())
    validate_receipt(receipt, manifest, name)
    route = ROUTES[name]
    live_catalog = fetch_catalog(route)
    validate_endpoint(live_catalog, route)
    # The catalog also carries rolling latency and uptime. Validation above
    # pins the identity, route, modality, context and entire price schedule.
    token = os.environ.get('OPENROUTER_API_KEY')
    if not token:
        raise ValueError('OPENROUTER_API_KEY required in process environment')
    if not Path(ledger_path).is_file() or not Path(ledger_path).stat().st_size:
        raise ValueError('Existing shared master ledger required')
    attempt_path = base / (name + '-attempts.jsonl')
    ledger = BudgetLedger(ledger_path)
    try:
        amounts, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or any(p['active'] for p in ledger.partitions.values()):
            raise ValueError('Master ledger not idle')
        required = 3 * bound(route)
        if ledger.accounted() + required > ledger.cap:
            raise ValueError('Three-request bound exceeds current master cap headroom')
        with attempt_path.open('x') as attempts:
            for item in manifest['routes'][name]['requests']:
                attempt_id = ledger.reserve(bound(route), name + ':' + item['id'])
                durable(attempts, {'stage': 'reserved', 'ledger_attempt_id': attempt_id,
                    'id': item['id'], 'payload_sha256': item['payload_sha256'],
                    'reserved_cost_usd': str(bound(route)), 'cost_unknown': True})
                started_utc = utc_now()
                started_ns = time.monotonic_ns()
                try:
                    status, raw = post(item['payload'], token)
                except BaseException as error:
                    elapsed_ns = time.monotonic_ns() - started_ns
                    durable(attempts, {'stage': 'transport_error', 'attempt_id': attempt_id,
                        'id': item['id'], 'error_type': type(error).__name__,
                        'request_start_utc': started_utc, 'request_end_utc': utc_now(),
                        'client_request_elapsed_ns': elapsed_ns,
                        'reserved_cost_usd': str(bound(route)), 'cost_unknown': True})
                    raise
                elapsed_ns = time.monotonic_ns() - started_ns
                ended_utc = utc_now()
                try:
                    body = json.loads(raw)
                    parse_error = None
                except (ValueError, UnicodeDecodeError) as error:
                    body = None
                    parse_error = type(error).__name__
                actual = response_cost(body)
                record = {'stage': 'response', 'attempt_id': attempt_id, 'id': item['id'],
                    'http_status': status, 'body': body, 'parse_error_type': parse_error,
                    'raw_response_base64': base64.b64encode(raw).decode('ascii'),
                    'raw_response_sha256': sha(raw), 'raw_response_size_bytes': len(raw),
                    'request_start_utc': started_utc, 'request_end_utc': ended_utc,
                    'client_request_elapsed_ns': elapsed_ns,
                    'reserved_cost_usd': str(bound(route)), 'cost_unknown': actual is None,
                    'actual_cost_usd': str(actual) if actual is not None else None}
                durable(attempts, record)
                if actual is None:
                    raise ValueError('Unknown provider cost; reservation remains pending')
                billing_ok = ledger.settle(attempt_id, actual)
                if not billing_ok:
                    raise ValueError('Actual cost exceeded reserved bound; master ledger blocked')
                if status != 200:
                    raise ValueError('Provider returned non-200 response; no retry')
                prediction = validate_response(body, route)
                durable(attempts, {'stage': 'validated', 'attempt_id': attempt_id,
                    'id': item['id'], 'prediction': prediction, 'cost_unknown': False})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare', help='Fetch public catalogs and write input-only manifest; no inference')
    sub.add_parser('verify', help='Verify frozen manifest and source; no network or inference')
    live = sub.add_parser('execute', help='Requires separate reviewed receipt; sends three paid requests')
    live.add_argument('--route', choices=tuple(ROUTES), required=True)
    live.add_argument('--review-receipt', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare())
    elif args.command == 'verify':
        print(sha(canonical(load_prepared())))
    else:
        execute(args.route, args.review_receipt)


if __name__ == '__main__':
    main()
