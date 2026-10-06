#!/usr/bin/env python3
"""Read-only source-bound reconciliation proposal for the separate Clef cap.

This module deliberately has no ledger-writing or inference command. A later
reviewed admission adapter may consume its exact receipt.
"""

import argparse
import base64
from collections import Counter
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path

import clef_native_preparation as prep

ROOT = prep.ROOT
BASE = ROOT / 'results/clef-native-v1'
LEGACY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
RECEIPT = BASE / 'cloudflare-budget-v1/historical-upper-bound.json'
HOLD_SNAPSHOT = BASE / 'cloudflare-budget-v1/historical-cloudflare-holds.json'
CAP = Decimal('10.00')
NEURONS_PER_MILLION = {'clef': Decimal(21818), 'clef-flash': Decimal(8182)}
NEURON_USD_PER_THOUSAND = Decimal('0.011')
PRICE_SOURCE = 'https://developers.cloudflare.com/workers-ai/platform/pricing/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    raw = path.read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Nonterminal evidence file')
    return [json.loads(line) for line in raw.splitlines()]


def money(value):
    if type(value) is not str:
        raise ValueError('Invalid money representation')
    result = Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid money amount')
    return result


def stage_paths(base):
    required = set()
    for model, pairs in (
        ('clef', [('fresh1', 'P0'), ('fresh1', 'P1'), ('fresh2', 'P0'), ('fresh3', 'P0')]),
        ('clef-flash', [(f'fresh{i}', f'P{j}') for i in (1, 2, 3) for j in (0, 1, 2)]),
    ):
        for repeat, condition in pairs:
            for phase in ('smoke', 'development'):
                required.add(base / model / repeat / condition / phase)
    required.add(base / 'clef-flash/fresh3/P0/development-suffix-v1')
    actual = {p.parent for p in base.glob('*/fresh*/P*/*/completion.json')}
    if actual != required:
        raise ValueError('Historical Clef stage set changed')
    return sorted(required)


def request_ceiling(model, tokens):
    if type(tokens) is not int or tokens < 0 or tokens > prep.CONTEXT_TOKENS:
        raise ValueError('Invalid billed input tokens')
    token_rate = prep.MODELS[model]['input_usd_per_million']
    neuron_rate = NEURONS_PER_MILLION[model] * NEURON_USD_PER_THOUSAND / Decimal(1000)
    rate = max(token_rate, neuron_rate)
    return (Decimal(tokens) * rate).to_integral_value(rounding=ROUND_CEILING) / Decimal(1_000_000)


def audit_stage(directory, root):
    completion_path = directory / 'completion.json'
    completion = json.loads(completion_path.read_bytes())
    model = directory.relative_to(root / 'results/clef-native-v1').parts[0]
    if completion.get('model') != model or model not in prep.MODELS:
        raise ValueError('Wrong historical model')
    files = {}
    for name, key in [('claim.json', 'claim_sha256'), ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'), ('records.jsonl', 'records_sha256')]:
        digest = sha((directory / name).read_bytes())
        if completion.get(key) != digest:
            raise ValueError('Historical completion binding changed')
        files[str((directory / name).relative_to(root))] = digest
    files[str(completion_path.relative_to(root))] = sha(completion_path.read_bytes())
    journal, raw, records = (rows(directory / name) for name in
                             ('journal.jsonl', 'raw.jsonl', 'records.jsonl'))
    attempted = completion.get('attempted')
    if (type(attempted) is not int or len(raw) != attempted or len(records) != attempted or
            len(journal) != 3 * attempted or attempted > (3 if directory.name == 'smoke' else 60) or
            sum(completion.get('counts', {}).values()) != attempted or
            Counter(r['status'] for r in records) != Counter({k: v for k, v in completion['counts'].items() if v})):
        raise ValueError('Historical attempt count mismatch')
    known = unknown = Decimal(0)
    ids = []
    for i, (wire, record) in enumerate(zip(raw, records)):
        reserved, started, finished = journal[3*i:3*i+3]
        rid = record.get('id')
        if (rid in ids or rid not in prep.IDS or
                reserved.get('event') != 'reserved' or started.get('event') != 'started' or
                finished.get('event') != 'finished' or
                any(item.get('id') != rid or item.get('attempt_id') != record.get('attempt_id')
                    for item in (reserved, started, finished, wire)) or
                wire.get('request_sha256') != record.get('request_sha256') or
                reserved.get('request_sha256') != record.get('request_sha256') or
                money(record.get('reservation_usd')) != prep.reservation_usd(model, 1) or
                money(reserved.get('usd')) != prep.reservation_usd(model, 1) or
                record.get('charge_status') != 'unknown_reserved' or
                finished.get('status') != record.get('status') or
                type(wire.get('redacted')) is not bool):
            raise ValueError('Historical attempt binding changed')
        ids.append(rid)
        response = base64.b64decode(wire['raw_response_base64'], validate=True)
        if sha(response) != wire.get('response_sha256'):
            raise ValueError('Historical raw response hash changed')
        if wire.get('http_status') == 200 and wire.get('error_type') is None:
            envelope = json.loads(response)
            result = envelope.get('result')
            usage = result.get('usage') if isinstance(result, dict) else None
            if (envelope.get('success') is not True or not isinstance(usage, dict) or
                    type(usage.get('output_tokens')) is not int or usage['output_tokens'] != 0):
                raise ValueError('No bounded successful response usage')
            bound = request_ceiling(model, usage.get('input_tokens'))
            if bound > prep.reservation_usd(model, 1):
                raise ValueError('Usage exceeds frozen request reservation')
            known += bound
        else:
            if record.get('status') != 'unknown_outcome':
                raise ValueError('Failed response has no preserved unknown')
            unknown += prep.reservation_usd(model, 1)
    if (ids != list(prep.IDS[:attempted]) and
            not (directory.name == 'development-suffix-v1' and ids == ['DEV-002'])):
        raise ValueError('Historical ordered IDs changed')
    if money(completion.get('unknown_cost_reserved_usd')) != prep.reservation_usd(model, attempted):
        raise ValueError('Historical completion reservation changed')
    return {'stage': str(directory.relative_to(root / 'results/clef-native-v1')),
            'attempted': attempted, 'bounded_usd': str(known),
            'retained_unknown_usd': str(unknown), 'files': files}


def audit(root=ROOT):
    root = Path(root)
    snapshot = root / HOLD_SNAPSHOT.relative_to(ROOT)
    holds = json.loads(snapshot.read_bytes())
    if len(holds) != 26 or len({h['id'] for h in holds}) != 26:
        raise ValueError('Historical Cloudflare hold set changed')
    legacy = root / LEGACY.relative_to(ROOT)
    if legacy.exists():
        events = rows(legacy)
        active = [event for event in events if event.get('event') == 'hold' and
                  event.get('id', '').startswith('cloudflare-')]
        if active != holds:
            raise ValueError('Active Cloudflare holds differ from archived projection')
    allocated = sum((money(h['usd']) for h in holds), Decimal(0))
    if allocated != Decimal('7.656482'):
        raise ValueError('Historical Cloudflare hold total changed')
    stages = [audit_stage(p, root) for p in stage_paths(root / 'results/clef-native-v1')]
    expected_holds = {}
    for stage in stages:
        parts = stage['stage'].split('/')
        model, repeat, condition, phase = parts
        directory = root / 'results/clef-native-v1' / stage['stage']
        claim = json.loads((directory / 'claim.json').read_bytes())
        if repeat == 'fresh1' and condition == 'P0' and phase == 'smoke':
            continue
        hold_id = f'cloudflare-{model}-{repeat}-{condition.lower()}-{phase}'
        amount = prep.reservation_usd(model, 3 if phase == 'smoke' else
                                      (59 if phase == 'development-suffix-v1' else 60))
        expected_holds[hold_id] = (amount, claim['grant_sha256'])
    first = ('cloudflare-initial-smoke',
             prep.reservation_usd('clef', 3) + prep.reservation_usd('clef-flash', 3))
    if {h['id'] for h in holds} != {first[0], *expected_holds}:
        raise ValueError('Historical hold identities differ')
    for hold in holds:
        if hold['id'] == first[0]:
            if money(hold['usd']) != first[1]:
                raise ValueError('Initial smoke hold changed')
        else:
            amount, grant = expected_holds[hold['id']]
            if money(hold['usd']) != amount or hold.get('source_sha256') != grant:
                raise ValueError('Historical stage hold differs from completed claim')
    bounded = sum((money(s['bounded_usd']) for s in stages), Decimal(0))
    unknown = sum((money(s['retained_unknown_usd']) for s in stages), Decimal(0))
    if sum(s['attempted'] for s in stages) != 761 or unknown != Decimal('0.011798'):
        raise ValueError('Historical attempt or unknown boundary changed')
    return {'kind': 'clef-cloudflare-historical-upper-bound-v1',
            'status': 'offline_review_only_no_ledger_release', 'cap_usd': str(CAP),
            'historical_hold_usd': str(allocated), 'successful_response_upper_bound_usd': str(bounded),
            'retained_unknown_usd': str(unknown), 'total_upper_bound_usd': str(bounded + unknown),
            'pricing_source': PRICE_SOURCE,
            'rates': {m: {'usd_per_million_input': str(prep.MODELS[m]['input_usd_per_million']),
                          'neurons_per_million_input': str(NEURONS_PER_MILLION[m])}
                      for m in prep.MODELS},
            'cloudflare_holds_sha256': sha(snapshot.read_bytes()),
            'auditor_sha256': sha(Path(__file__).read_bytes()),
            'preparation_source_sha256': sha((root / 'scripts/clef_native_preparation.py').read_bytes()),
            'stages': stages}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('propose', 'verify'))
    parser.add_argument('--output', type=Path, default=RECEIPT)
    args = parser.parse_args()
    expected = audit()
    if args.command == 'propose':
        if args.output.exists():
            raise ValueError('Proposal already exists')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(expected, indent=2, sort_keys=True) + '\n')
    elif json.loads(args.output.read_bytes()) != expected:
        raise ValueError('Historical reconciliation proposal differs')
    print(sha(args.output.read_bytes()))


if __name__ == '__main__':
    main()
