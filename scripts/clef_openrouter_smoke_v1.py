#!/usr/bin/env python3
"""Gated three-review OpenRouter native Decisions smoke for a declared stage.

No allocation is made here. A reviewed receipt, existing funded child, and
matching OpenRouter authority hold are required before any POST.
"""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from development_benchmark import ROOT, KEYS
from jev_benchmark import parse_response
from openrouter_paid_benchmark import durable
import openrouter_decision_smoke as native
import openrouter_budget_v4
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority
import clef_openrouter_native_v1 as plan_v1


MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
MAX_BODY = 2_000_000
REASONING = 'native-decisions-smoke'


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def partition_id(key, stage):
    if key not in plan_v1.MODELS or stage not in {f'{p}/{c}' for p in plan_v1.PASSES for c in plan_v1.CONDITIONS}:
        raise ValueError('Unknown native smoke partition')
    return f'clef-openrouter-v1-{key}-{stage.replace("/", "-").lower()}-smoke'


def stage_dir(root, key, stage):
    partition_id(key, stage)
    return Path(root) / plan_v1.BASE / key / stage


def hold_source(plan_sha, budget_path, key, stage):
    return native.sha(native.canonical({
        'kind': 'clef-openrouter-native-smoke-hold-v1',
        'plan_sha256': plan_sha, 'budget_manifest_sha256': sha_path(budget_path),
        'partition_id': partition_id(key, stage),
        'three_request_bound_usd': str(plan_v1.bound(key, 3)),
    }))


def verify_review(path, plan_sha, budget_path, key, stage, root=ROOT):
    folder = stage_dir(root, key, stage)
    if Path(path).resolve() != (folder / 'smoke.root-review.json').resolve():
        raise ValueError('Wrong stage root-review path')
    receipt = json.loads(Path(path).read_text())
    expected = {
        'kind': 'clef-openrouter-native-smoke-root-review-v1', 'approved': True,
        'model_key': key, 'stage': stage, 'plan_sha256': plan_sha,
        'runner_sha256': sha_path(Path(root) / 'scripts/clef_openrouter_smoke_v1.py'),
        'budget_manifest_sha256': sha_path(budget_path),
        'partition_id': partition_id(key, stage),
        'authority_hold_source_sha256': hold_source(plan_sha, budget_path, key, stage),
        'three_request_bound_usd': str(plan_v1.bound(key, 3)),
        'smoke_ids': list(plan_v1.SMOKE_IDS), 'reference_labels_sent': False,
    }
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError('Root review does not bind exact route, stage, runner and budget')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Named root reviewer required')
    return receipt


def verify_hold(plan_sha, budget_path, key, stage, authority_path=AUTHORITY, master=MASTER):
    pid = partition_id(key, stage)
    with authority.old._locked(authority_path) as handle:
        _, holds, released = authority._scan(handle.read())
        hold = holds.get(pid)
        if (not hold or pid in released or hold.get('version') != 3 or
                hold.get('funding_pool') != 'openrouter_additional' or
                hold.get('usd') != str(plan_v1.bound(key, 3)) or
                hold.get('source_sha256') != hold_source(plan_sha, budget_path, key, stage) or
                hold.get('budget_manifest_sha256') != sha_path(budget_path) or
                hold.get('budget_manifest_path') != str(Path(budget_path).resolve()) or
                hold.get('master_path') != str(Path(master).resolve()) or
                hold.get('partition_id') != pid):
            raise ValueError('Exact additional OpenRouter authority hold missing')


def fetch_endpoint(key):
    spec = plan_v1.MODELS[key]
    url = f"https://openrouter.ai/api/v1/models/{spec['model']}/endpoints"
    request = urllib.request.Request(url, headers={'Accept': 'application/json'}, method='GET')
    with native.OPENER.open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Native endpoint GET failed')
        raw = response.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Native endpoint catalog too large')
    return raw, json.loads(raw)


def verify_live_endpoint(key, body, pinned):
    wrapper = {'source': f"https://openrouter.ai/api/v1/models/{plan_v1.MODELS[key]['model']}/endpoints",
               'checked_utc': now(), 'inference_requests': 0, 'response': body}
    live = plan_v1.validate_catalog(key, wrapper)
    critical = ('name', 'model_id', 'provider_name', 'tag', 'context_length',
                'max_completion_tokens', 'max_prompt_tokens', 'quantization',
                'supported_parameters', 'pricing', 'status')
    if any(live.get(k) != pinned.get(k) for k in critical):
        raise ValueError('Native endpoint differs from frozen route or tariff')
    return live


def post(payload, token):
    request = urllib.request.Request(native.DECISIONS_URL, data=native.canonical(payload),
        method='POST', headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with native.OPENER.open(request, timeout=60) as response:
            status, raw = response.status, response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Native response too large; reservation remains unknown')
    return status, raw


def validate_returned(key, body):
    spec = plan_v1.MODELS[key]
    if not isinstance(body, dict) or body.get('provider') != spec['provider']:
        raise ValueError('Returned native provider differs')
    prediction = parse_response(body, spec['model'])
    usage = body.get('usage')
    if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= len(KEYS) * spec['context'] or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Native token usage missing or outside reviewed context')
    return prediction


def run(key, stage, receipt_path, budget_path, *, root=ROOT, master=MASTER,
        authority_path=AUTHORITY, fetch=fetch_endpoint, send=post,
        open_child=partitions.open_partition):
    root, budget_path = Path(root), Path(budget_path)
    plan, plan_sha = plan_v1.verify(root)
    receipt_path = Path(receipt_path)
    verify_review(receipt_path, plan_sha, budget_path, key, stage, root)
    verify_hold(plan_sha, budget_path, key, stage, authority_path, master)
    folder = stage_dir(root, key, stage)
    paths = {name: folder / ('smoke.' + name) for name in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Native smoke already claimed; no replay')
    _, live = fetch(key)
    verify_live_endpoint(key, live, plan['models'][key]['endpoint'])
    spec = plan_v1.MODELS[key]
    ledger = open_child(master, budget_path, partition_id(key, stage),
                        spec['model'], spec['provider'], REASONING)
    try:
        if ledger.master_cap != openrouter_budget_v4.CAP:
            raise ValueError('OpenRouter master cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + plan_v1.bound(key, 3) > ledger.cap:
            raise ValueError('Native child lacks the three-request smoke bound')
        token = os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required in process environment')
        folder.mkdir(parents=True, exist_ok=True)
        with paths['claim.json'].open('x') as out:
            durable(out, {'kind': 'clef-openrouter-native-smoke-claim-v1',
                          'plan_sha256': plan_sha, 'root_review_sha256': sha_path(receipt_path),
                          'budget_manifest_sha256': sha_path(budget_path), 'claimed_utc': now(),
                          'model_key': key, 'stage': stage, 'reference_labels_sent': False})
        condition = stage.split('/')[1]
        items = plan['models'][key]['requests'][condition][:3]
        with paths['journal.jsonl'].open('x') as journal, paths['raw.jsonl'].open('x') as raw_file, \
                paths['attempts.jsonl'].open('x') as attempts, paths['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'stage_started', 'utc': now(), 'plan_sha256': plan_sha})
            for item in items:
                rid = item['id']
                try:
                    plan_v1.verify(root)
                    verify_hold(plan_sha, budget_path, key, stage, authority_path, master)
                    route_raw, route = fetch(key)
                    verify_live_endpoint(key, route, plan['models'][key]['endpoint'])
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Native smoke payload drift')
                    if ledger.accounted() + plan_v1.bound(key, 1) > ledger.cap:
                        raise ValueError('Native child lacks next full-context reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                                      'payload_sha256': item['payload_sha256'], 'utc': now()})
                    attempt = ledger.reserve(plan_v1.bound(key, 1), rid)
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                      'live_endpoint_sha256': native.sha(route_raw), 'utc': now()})
                    started, t0 = now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                                           'error_type': type(error).__name__, 'cost_unknown': True,
                                           'reserved_cost_usd': str(plan_v1.bound(key, 1)),
                                           'request_started_utc': started, 'request_ended_utc': now(),
                                           'client_request_elapsed_ns': time.perf_counter_ns() - t0})
                        raise
                    ended, elapsed = now(), time.perf_counter_ns() - t0
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
                                           'reserved_cost_usd': str(plan_v1.bound(key, 1))})
                        raise ValueError('Native cost unknown; full reservation retained')
                    if not ledger.settle(attempt, actual):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'over_bound',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Observed native cost exceeded reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Native provider HTTP error; no retry')
                    try:
                        prediction = validate_returned(key, body)
                    except ValueError:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'invalid_native_response',
                                           'actual_cost_usd': str(actual)})
                        raise
                    durable(parsed, {'id': rid, 'attempt_id': attempt, 'prediction': prediction,
                                     'input_tokens': body['usage']['input_tokens'],
                                     'output_tokens': body['usage']['output_tokens'],
                                     'actual_cost_usd': str(actual)})
                    durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'ok',
                                       'actual_cost_usd': str(actual), 'cost_unknown': False})
                except BaseException as error:
                    durable(journal, {'event': 'stage_stopped', 'id': rid,
                                      'error_type': type(error).__name__, 'utc': now()})
                    raise
            durable(journal, {'event': 'stage_completed', 'utc': now(), 'count': 3})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('key', choices=tuple(plan_v1.MODELS))
    parser.add_argument('stage')
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    run(args.key, args.stage, args.receipt, args.budget)


if __name__ == '__main__':
    main()
