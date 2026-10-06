#!/usr/bin/env python3
"""Audit three completed Liquid smoke calls and freeze their child-ledger prefix."""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT
import liquid_d1_native_v1 as liquid
import liquid_d1_smoke_v1 as smoke
import openrouter_decision_smoke as native

BASE = ROOT / 'results/liquid-d1-native-v1'
SNAPSHOT = 'smoke.closure-ledger-snapshot.jsonl'
RECEIPT = 'smoke.closure-audit.json'
PUBLIC = 'smoke.public.json'
EVIDENCE = ('plan.json', 'endpoint-public.json', 'budget-manifest.json',
            'smoke.root-review.json', 'smoke.claim.json', 'smoke.journal.jsonl',
            'smoke.raw.jsonl', 'smoke.attempts.jsonl', 'smoke.parsed.jsonl')


def rows(raw):
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL evidence')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def read_rows(path):
    return rows(path.read_bytes())


def receipt_value(base=BASE, ledger_bytes=None):
    base = Path(base)
    plan, plan_sha = liquid.verify(base, ROOT)
    budget = base / 'budget-manifest.json'
    smoke.verify_review(base / 'smoke.root-review.json', plan, plan_sha, budget, base)
    smoke.verify_hold(plan_sha, budget)
    manifest = json.loads(budget.read_text())
    entries = [p for p in manifest['partitions'] if p['id'] == smoke.PARTITION_ID]
    if (len(entries) != 1 or manifest['master_ledger'] != str(smoke.MASTER.resolve()) or
            entries[0]['model'] != liquid.MODEL or entries[0]['provider'] != liquid.PROVIDER or
            entries[0]['reasoning'] != smoke.REASONING or
            Decimal(entries[0]['cap_usd']) != liquid.SMOKE_BOUND):
        raise ValueError('Liquid child allocation differs')
    child = Path(entries[0]['child_ledger'])
    if child.resolve() != (base / 'budget-manifest-liquid-d1-native-fresh1-p0-smoke-v1.jsonl').resolve():
        raise ValueError('Unexpected Liquid child path')
    if ledger_bytes is None:
        ledger_bytes = (base / SNAPSHOT).read_bytes()
    ledger = rows(ledger_bytes)
    expected_ids = plan['smoke_ids']
    phase = next(p for p in plan['phases'] if p['id'] == 'fresh1/P0')
    expected_requests = phase['requests'][:3]
    claim = json.loads((base / 'smoke.claim.json').read_text())
    if (claim.get('plan_sha256') != plan_sha or
            claim.get('root_review_sha256') != smoke.sha_path(base / 'smoke.root-review.json') or
            claim.get('budget_manifest_sha256') != smoke.sha_path(budget) or
            claim.get('reference_labels_sent') is not False):
        raise ValueError('Smoke claim does not bind review, budget and input-only plan')
    journal = read_rows(base / 'smoke.journal.jsonl')
    raw = read_rows(base / 'smoke.raw.jsonl')
    attempts = read_rows(base / 'smoke.attempts.jsonl')
    parsed = read_rows(base / 'smoke.parsed.jsonl')
    if (len(journal) != 8 or len(raw) != 3 or len(attempts) != 3 or len(parsed) != 3 or
            len(ledger) != 7 or journal[0].get('event') != 'stage_started' or
            journal[0].get('plan_sha256') != plan_sha or
            journal[-1].get('event') != 'stage_completed' or journal[-1].get('count') != 3 or
            ledger[0] != {'event': 'budget', 'cap_usd': str(liquid.SMOKE_BOUND)}):
        raise ValueError('Smoke terminal sequence or ledger length differs')
    audited = []
    total = Decimal(0)
    for index, request in enumerate(expected_requests):
        rid = expected_ids[index]
        intent, started = journal[1 + index * 2:3 + index * 2]
        record, attempt, prediction = raw[index], attempts[index], parsed[index]
        reserve, settle = ledger[1 + index * 2:3 + index * 2]
        aid = started.get('attempt_id')
        if (rid != request['id'] or intent.get('event') != 'request_intent' or
                started.get('event') != 'request_started' or
                intent.get('id') != rid or started.get('id') != rid or
                intent.get('payload_sha256') != request['payload_sha256'] or
                record.get('id') != rid or record.get('attempt_id') != aid or
                record.get('payload_sha256') != request['payload_sha256'] or
                attempt.get('id') != rid or attempt.get('attempt_id') != aid or
                prediction.get('id') != rid or prediction.get('attempt_id') != aid or
                reserve.get('event') != 'reserve' or reserve.get('record_id') != rid or
                reserve.get('attempt_id') != aid or Decimal(reserve['usd']) != liquid.BOUND or
                settle.get('event') != 'settle' or settle.get('attempt_id') != aid or
                record.get('http_status') != 200 or attempt.get('status') != 'ok' or
                attempt.get('cost_unknown') is not False):
            raise ValueError('Smoke request/attempt/ledger identity differs: ' + rid)
        live_endpoint = base64.b64decode(started['live_endpoint_base64'], validate=True)
        if native.sha(live_endpoint) != started['live_endpoint_sha256']:
            raise ValueError('Live endpoint hash differs')
        liquid.validate_catalog(json.loads(live_endpoint))
        wire = base64.b64decode(record['response_base64'], validate=True)
        if native.sha(wire) != record['response_sha256']:
            raise ValueError('Raw response hash differs')
        body = json.loads(wire)
        actual = native.response_cost(body)
        inferred = smoke.validate_returned(body)
        tokens = body['usage']['input_tokens']
        if (actual is None or actual != Decimal(tokens) * liquid.RATE or
                actual != Decimal(settle['usd']) or actual != Decimal(attempt['actual_cost_usd']) or
                actual != Decimal(prediction['actual_cost_usd']) or actual > liquid.BOUND or
                prediction['prediction'] != inferred or
                native.sha(native.canonical(request['payload'])) != request['payload_sha256']):
            raise ValueError('Smoke bill, response or frozen request differs: ' + rid)
        total += actual
        audited.append({'id': rid, 'http_status': 200, 'returned_model': body['model'],
                        'returned_provider': body['provider'], 'input_tokens': tokens,
                        'output_tokens': body['usage']['output_tokens'],
                        'actual_cost_usd': str(actual), 'four_choice_questions_valid': True,
                        'payload_sha256': request['payload_sha256'],
                        'response_sha256': record['response_sha256']})
    hashes = {name: smoke.sha_path(base / name) for name in EVIDENCE}
    return {'kind': 'liquid-d1-native-smoke-closure-audit-v1', 'status': 'three_record_smoke_closed',
            'full_60_result': False, 'scored_against_references': False,
            'plan_sha256': plan_sha, 'audit_source_sha256': smoke.sha_path(ROOT / 'scripts/liquid_d1_smoke_audit_v1.py'),
            'source_sha256': plan['source_sha256'], 'evidence_sha256': hashes,
            'child_ledger_snapshot_sha256': native.sha(ledger_bytes),
            'child_cap_usd': str(liquid.SMOKE_BOUND), 'known_actual_usd': str(total),
            'unknown_upper_bound_usd': '0', 'expected_unused_child_usd': str(liquid.SMOKE_BOUND - total),
            'records': audited, 'attempts': 3, 'valid_native_responses': 3,
            'source_provenance_limit': 'Outbound request bytes are bound by runner source and journal hashes; no independent network echo exists.'}


def public_value(receipt):
    return {'kind': 'liquid-d1-native-smoke-public-v1', 'status': receipt['status'],
            'model': liquid.MODEL, 'provider': liquid.PROVIDER, 'version': liquid.VERSION,
            'condition': 'P0', 'pass': 'fresh1', 'smoke_records': 3,
            'valid_native_responses': receipt['valid_native_responses'],
            'known_actual_usd': receipt['known_actual_usd'],
            'full_60_result': False, 'scored_against_references': False,
            'input_tokens_by_record': {r['id']: r['input_tokens'] for r in receipt['records']},
            'plan_sha256': receipt['plan_sha256'],
            'closure_receipt_sha256': native.sha(native.canonical(receipt))}


def prepare(base=BASE):
    base = Path(base)
    if any((base / name).exists() for name in (SNAPSHOT, RECEIPT, PUBLIC)):
        raise FileExistsError('Liquid closure outputs already exist')
    budget = json.loads((base / 'budget-manifest.json').read_text())
    selected = [p for p in budget['partitions'] if p['id'] == smoke.PARTITION_ID]
    if len(selected) != 1:
        raise ValueError('Exact Liquid child missing')
    child = Path(selected[0]['child_ledger'])
    first = child.read_bytes()
    receipt = receipt_value(base, first)
    if child.read_bytes() != first:
        raise ValueError('Liquid child changed during audit')
    with (base / SNAPSHOT).open('xb') as out:
        out.write(first)
    with (base / RECEIPT).open('x') as out:
        out.write(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    with (base / PUBLIC).open('x') as out:
        out.write(json.dumps(public_value(receipt), indent=2) + '\n')
    return native.sha(native.canonical(receipt))


def verify(base=BASE):
    base = Path(base)
    receipt = receipt_value(base)
    if json.loads((base / RECEIPT).read_text()) != receipt or json.loads((base / PUBLIC).read_text()) != public_value(receipt):
        raise ValueError('Liquid closure receipt or public projection differs')
    return native.sha(native.canonical(receipt))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'verify'))
    args = parser.parse_args()
    print(prepare() if args.operation == 'prepare' else verify())


if __name__ == '__main__':
    main()
