#!/usr/bin/env python3
"""Verify saved Perplexity Decider evidence and build a text-free public projection."""

import argparse
import base64
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS
from openrouter_budget_v4 import BudgetLedger
import perplexity_decider_full_v1 as full
import perplexity_decider_plan_v1 as route


PROJECTION = full.BASE / 'public-projection.json'
FINDINGS = full.BASE / 'findings.json'
LABELS = Path('data/pilot/proposed_labels.jsonl')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def source(root, path):
    path = Path(path)
    return str(path.relative_to(root)), digest(path)


def phase(root, folder, name, ids, expected_requests, stage, route_sha, full_sha):
    paths = {part: folder / f'{name}.{part}' for part in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    claim = json.loads(paths['claim.json'].read_text())
    claim_ok = (claim.get('model_key') == 'decider' and
                claim.get('stage') == stage and
                claim.get('reference_labels_sent') is False and
                ((name == 'smoke' and stage == 'fresh1/P0' and
                  claim.get('kind') == 'perplexity-decider-native-smoke-claim-v1' and
                  claim.get('plan_sha256') == route_sha) or
                 (claim.get('kind') == 'perplexity-decider-native-full-phase-claim-v1' and
                  claim.get('phase') == name and
                  claim.get('route_plan_sha256') == route_sha and
                  claim.get('full_plan_sha256') == full_sha)))
    if not claim_ok:
        raise ValueError(f'Phase claim differs: {folder}/{name}')
    raw, attempts, parsed, journal = (read_jsonl(paths[part]) for part in
                                      ('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl', 'journal.jsonl'))
    if ([row['id'] for row in raw] != ids or
            [row['id'] for row in attempts] != ids or
            [row['id'] for row in parsed] != ids or
            journal[-1].get('event') != 'stage_completed' or
            journal[-1].get('count') != len(ids) or
            len([row for row in journal if row.get('event') == 'request_started']) != len(ids)):
        raise ValueError(f'Incomplete or unordered phase: {folder}/{name}')
    records = []
    for original, attempt, outcome, expected in zip(raw, attempts, parsed, expected_requests):
        wire = base64.b64decode(original['response_base64'], validate=True)
        response = json.loads(wire)
        prediction = full.validate_returned('decider', response)
        usage = response['usage']
        observed_cost = Decimal(str(usage.get('cost')))
        expected_cost = Decimal(usage['input_tokens']) * route.MODELS['decider']['rate']
        if (original.get('http_status') != 200 or digest_bytes(wire) != original['response_sha256'] or
                original['id'] != expected['id'] or
                original['payload_sha256'] != expected['payload_sha256'] or
                digest_bytes(route.native.canonical(expected['payload'])) != expected['payload_sha256'] or
                attempt.get('status') != 'ok' or attempt.get('cost_unknown') is not False or
                not (original['attempt_id'] == attempt['attempt_id'] == outcome['attempt_id']) or
                Decimal(str(attempt['actual_cost_usd'])) != Decimal(str(outcome['actual_cost_usd'])) or
                outcome['prediction'] != prediction or
                outcome['input_tokens'] != usage['input_tokens'] or
                outcome['output_tokens'] != usage['output_tokens'] or
                observed_cost != Decimal(str(outcome['actual_cost_usd'])) or
                observed_cost != expected_cost):
            raise ValueError(f'Invalid saved response: {folder}/{name}/{original["id"]}')
        records.append({'id': original['id'], 'prediction': outcome['prediction'],
                        'input_tokens': outcome['input_tokens'],
                        'output_tokens': outcome['output_tokens'],
                        'actual_cost_usd': str(Decimal(str(outcome['actual_cost_usd']))),
                        'request_sha256': original['payload_sha256'],
                        'response_sha256': original['response_sha256']})
    bindings = dict(source(root, path) for path in paths.values())
    return {'records': records,
            'known_cost_usd': str(sum((Decimal(row['actual_cost_usd']) for row in records), Decimal(0))),
            'source_sha256': bindings,
            'claim': claim}


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def closed_child(root, manifest):
    value = json.loads(manifest.read_text())
    if value.get('version') != 'paid-partitions-v1' or len(value.get('partitions', [])) != 1:
        raise ValueError('Partition manifest changed')
    entry = value['partitions'][0]
    child = Path(entry['child_ledger'])
    ledger = BudgetLedger(child, cap_limit=Decimal(str(entry['cap_usd'])))
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or not ledger.closed:
            raise ValueError('Partition is not terminally sealed')
        settled = sum((Decimal(str(event['usd'])) for event in ledger.events
                       if event['event'] == 'settle'), Decimal(0))
        unknown = sum((Decimal(str(event['usd'])) for event in ledger.events
                       if event['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
        if settled + unknown != ledger.accounted():
            raise ValueError('Partition accounting differs')
        return {'known_actual_usd': str(settled),
                'unknown_upper_bound_usd': str(unknown),
                'source_sha256': dict([source(root, manifest), source(root, child)])}
    finally:
        ledger.close()


def build(root=ROOT):
    root = Path(root).resolve()
    _, full_sha = full.verify(root)
    route_plan, route_sha = route.verify(root)
    full.verify_global_review(root, full_sha)
    labels = {row['id']: row['proposed_labels'] for row in read_jsonl(root / LABELS)}
    if set(labels) != set(route.IDS):
        raise ValueError('Frozen reference ID set differs')
    stages = []
    scores = []
    predictions = {}
    development = Decimal(0)
    smoke = Decimal(0)
    for repeat in route.PASSES:
        for condition in route.CONDITIONS:
            stage = f'{repeat}/{condition}'
            folder = full.stage_dir(root, 'decider', stage)
            inspection_sha = full.verify_smoke_inspection(root, 'decider', stage,
                                                           route_sha, full_sha)
            smoke_folder = (root / route.BASE / 'decider' / stage if stage == 'fresh1/P0'
                            else folder)
            expected = route_plan['models']['decider']['requests'][condition]
            smoke_result = phase(root, smoke_folder, 'smoke', list(route.SMOKE_IDS),
                                 expected[:3], stage, route_sha, full_sha)
            dev_result = phase(root, folder, 'development', list(route.IDS),
                               expected, stage, route_sha, full_sha)
            if (dev_result['claim'].get('full_plan_sha256') != full_sha or
                    dev_result['claim'].get('route_plan_sha256') != route_sha):
                raise ValueError(f'Development claim changed: {stage}')
            development += Decimal(dev_result['known_cost_usd'])
            smoke += Decimal(smoke_result['known_cost_usd'])
            predictions[stage] = {row['id']: row['prediction'] for row in dev_result['records']}
            field_scores = {key: sum(row['prediction'][key] == labels[row['id']][key]
                                     for row in dev_result['records']) for key in KEYS}
            all_four = sum(all(row['prediction'][key] == labels[row['id']][key]
                               for key in KEYS) for row in dev_result['records'])
            scores.append({'stage': stage, 'denominator': 60, 'valid': 60,
                           'all_four_correct': all_four, 'field_correct': field_scores,
                           'mismatch_ids': [row['id'] for row in dev_result['records']
                                            if any(row['prediction'][key] != labels[row['id']][key]
                                                   for key in KEYS)]})
            stages.append({'stage': stage, 'status': 'closed',
                           'smoke_count': 3, 'development_count': 60,
                           'known_smoke_cost_usd': smoke_result['known_cost_usd'],
                           'known_development_cost_usd': dev_result['known_cost_usd'],
                           'smoke_inspection_sha256': inspection_sha,
                           'source_sha256': {**smoke_result['source_sha256'],
                                             **dev_result['source_sha256'],
                                             **dict([source(root, smoke_folder / 'smoke.root-inspection.json')])},
                           'records': dev_result['records']})
    first = closed_child(root, root / route.BASE / 'decider/fresh1/P0/smoke-budget.json')
    full_child = closed_child(root, root / full.BASE / 'full-budget.json')
    if (first['unknown_upper_bound_usd'] != '0' or full_child['unknown_upper_bound_usd'] != '0' or
            Decimal(first['known_actual_usd']) + Decimal(full_child['known_actual_usd']) != development + smoke):
        raise ValueError('Sealed child accounting differs from saved outcomes')
    repeatability = {condition: all(predictions[f'fresh1/{condition}'] ==
                                    predictions[f'{repeat}/{condition}']
                                    for repeat in route.PASSES[1:])
                     for condition in route.CONDITIONS}
    projection = {'schema': 'perplexity-decider-native-public-projection-v1',
                  'model': route.MODELS['decider']['model'],
                  'returned_model': route.MODELS['decider']['returned_model'],
                  'provider': route.MODELS['decider']['provider'],
                  'reference_labels_sent': False,
                  'private_raw_checked_at_prepare': True,
                  'route_plan_sha256': route_sha,
                  'full_plan_sha256': full_sha,
                  'stages': stages,
                  'sealed_budget_children': {'initial_smoke': first, 'full_v2': full_child}}
    findings = {'schema': 'perplexity-decider-native-findings-v1',
                'projection_sha256': digest_bytes(canonical(projection)),
                'reference_sha256': dict([source(root, root / LABELS)]),
                'reference_status': 'proposed_labels_not_final_adjudication',
                'development_stages_closed': 9, 'development_valid': 540,
                'development_planned': 540, 'smoke_valid': 27,
                'known_development_cost_usd': str(development),
                'known_smoke_cost_usd': str(smoke),
                'known_total_cost_usd': str(development + smoke),
                'unknown_cost_upper_bound_usd': '0',
                'field_key_order': list(KEYS),
                'scores': scores, 'repeat_identical_by_condition': repeatability}
    return projection, findings


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check'))
    args = parser.parse_args()
    projection, findings = build()
    for path, value in ((ROOT / PROJECTION, projection), (ROOT / FINDINGS, findings)):
        if args.action == 'write':
            path.write_bytes(canonical(value))
        elif path.read_bytes() != canonical(value):
            raise ValueError(f'Projection differs from saved sources: {path}')
    print('perplexity-decider-projection', args.action,
          findings['development_valid'], findings['smoke_valid'],
          findings['known_total_cost_usd'])


if __name__ == '__main__':
    main()
