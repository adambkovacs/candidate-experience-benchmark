#!/usr/bin/env python3
"""Publish the three closed Solar first-pass runs from checked private evidence."""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
import solar_decide_native_full_execution_v2 as execution

BASE = Path('results/solar-decide-native-full-v1/execution-adapter-v2')
STAGES = ('fresh1/P0', 'fresh1/P1', 'fresh1/P2')
PROJECTION = BASE / 'first-pass.public-projection.json'
RECEIPT = BASE / 'first-pass.public-projection.receipt.json'
OUTPUT = Path('public-site/solar-decide-first-pass-findings.json')
PRIVATE_SUFFIXES = ('development.raw.jsonl', 'development.parsed.jsonl',
                    'development.attempts.jsonl', 'development.journal.jsonl')


def digest(path):
    return execution.sha(path)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write('\n')


def truth(root):
    data = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    ids = [f'DEV-{index:03}' for index in range(1, 61)]
    if len(data) != 60 or [row['id'] for row in data] != ids:
        raise ValueError('Frozen Solar reference set differs')
    return {row['id']: row['proposed_labels'] for row in data}


def private_stage(stage):
    closure = execution.verify_phase_closure(stage, 'development')
    execution.verify_phase_closure(stage, 'smoke')
    execution.require_inspection(stage)
    folder = ROOT / BASE / stage
    raw = rows(folder / 'development.raw.jsonl')
    parsed = rows(folder / 'development.parsed.jsonl')
    attempts = rows(folder / 'development.attempts.jsonl')
    if len(raw) != len(parsed) or len(raw) != len(attempts) or len(raw) != 60:
        raise ValueError('Solar private stage length differs')
    plan = execution.phase(stage)
    records = []
    for index, (record, output, attempt, request) in enumerate(
            zip(raw, parsed, attempts, plan['requests']), 1):
        ident = f'DEV-{index:03}'
        wire = base64.b64decode(record['response_base64'], validate=True)
        body = json.loads(wire)
        usage, cost = execution.checked_body(body)
        prediction = execution.parse_response(body, execution.solar.VERSION)
        if (record['id'] != ident or output['id'] != ident or attempt['id'] != ident or
                request['id'] != ident or record['payload_sha256'] != request['payload_sha256'] or
                digest_bytes(wire) != record['response_sha256'] or
                attempt['status'] != 'ok' or attempt['cost_unknown'] is not False or
                output['prediction'] != prediction or output['usage'] != usage or
                Decimal(output['actual_cost_usd']) != cost or
                Decimal(attempt['actual_cost_usd']) != cost):
            raise ValueError('Solar private response, cost, or request differs')
        records.append({'id': ident, 'prediction': prediction,
                        'input_tokens': usage['input_tokens'],
                        'output_tokens': usage['output_tokens'],
                        'actual_cost_usd': str(cost),
                        'request_sha256': request['payload_sha256'],
                        'response_sha256': record['response_sha256']})
    public = json.loads((folder / 'development.public-score.json').read_text())
    ref = truth(ROOT)
    correct = sum(all(row['prediction'][key] == ref[row['id']][key] for key in KEYS)
                  for row in records)
    cost = sum((Decimal(row['actual_cost_usd']) for row in records), Decimal(0))
    if (public['stage'] != stage or public['all_four_correct'] != correct or
            Decimal(public['known_development_cost_usd']) != cost or
            public['source_sha256']['development_raw_private'] != closure['raw_sha256'] or
            public['source_sha256']['development_parsed_private'] != closure['parsed_sha256'] or
            public['source_sha256']['development_attempts'] != closure['attempts_sha256'] or
            public['valid_development_answers'] != 60 or
            public['unknown_cost_attempts'] != 0):
        raise ValueError('Solar safe score differs from private closure')
    return {'stage': stage, 'records': records,
            'known_development_cost_usd': str(cost)}


def digest_bytes(value):
    return execution.native.sha(value)


def source_paths():
    paths = ['scripts/build_solar_decide_native_first_pass_findings.py',
             'tests/test_build_solar_decide_native_first_pass_findings.py',
             'results/solar-decide-native-full-v1/plan.json',
             str(BASE / 'manifest.json'),
             'data/pilot/proposed_labels.jsonl',
             'docs/CLEF_FINDINGS_2026-10-02.md']
    for stage in STAGES:
        folder = BASE / stage
        paths.extend(str(folder / name) for name in (
            'development.public-score.json', 'development.root-review.json',
            'smoke-inspection.json', 'development.claim.json',
            *PRIVATE_SUFFIXES))
    return paths


def prepare(root=ROOT):
    root = Path(root).resolve()
    if root != ROOT.resolve():
        raise ValueError('Private Solar preparation requires the execution checkout')
    stages = [private_stage(stage) for stage in STAGES]
    projection = {'schema': 'solar-decide-first-pass-public-projection-v1',
                  'stages': stages, 'reference_labels_sent': False,
                  'private_raw_checked_at_prepare': True}
    write_new(root / PROJECTION, projection)
    source_hashes = {name: digest(root / name) for name in source_paths()}
    receipt = {'schema': 'solar-decide-first-pass-public-projection-receipt-v1',
               'projection_sha256': digest(root / PROJECTION),
               'source_sha256': source_hashes,
               'private_raw_checked_at_prepare': True,
               'portable_limit': 'Absent private raw files are checked by archived hash, not decoded again.'}
    write_new(root / RECEIPT, receipt)
    write_new(root / OUTPUT, build(root))
    return digest(root / OUTPUT)


def portable_projection(root):
    receipt = json.loads((root / RECEIPT).read_text())
    projection = json.loads((root / PROJECTION).read_text())
    if (receipt.get('schema') != 'solar-decide-first-pass-public-projection-receipt-v1' or
            receipt.get('projection_sha256') != digest(root / PROJECTION) or
            receipt.get('private_raw_checked_at_prepare') is not True or
            projection.get('schema') != 'solar-decide-first-pass-public-projection-v1' or
            projection.get('reference_labels_sent') is not False or
            projection.get('private_raw_checked_at_prepare') is not True or
            [item['stage'] for item in projection['stages']] != list(STAGES) or
            set(receipt.get('source_sha256', {})) != set(source_paths())):
        raise ValueError('Solar projection receipt differs')
    for name, expected in receipt['source_sha256'].items():
        path = root / name
        if path.exists():
            if digest(path) != expected:
                raise ValueError('Solar source changed: ' + name)
        elif not name.endswith(PRIVATE_SUFFIXES):
            raise ValueError('Required Solar public source missing: ' + name)
    labels = truth(root)
    plan = json.loads((root / 'results/solar-decide-native-full-v1/plan.json').read_text())
    by_stage = {item['id']: item for item in plan['phases']}
    for stage in projection['stages']:
        name = stage['stage']
        public = json.loads((root / BASE / name / 'development.public-score.json').read_text())
        records = stage['records']
        requests = by_stage[name]['requests']
        if (len(records) != 60 or [row['id'] for row in records] != list(labels) or
                public['status'] != 'closed' or public['denominator'] != 60 or
                public['valid_development_answers'] != 60 or
                public['unknown_cost_attempts'] != 0):
            raise ValueError('Solar projected denominator or closed status differs')
        total = Decimal(0)
        for row, request in zip(records, requests):
            if (set(row) != {'id', 'prediction', 'input_tokens', 'output_tokens',
                             'actual_cost_usd', 'request_sha256', 'response_sha256'} or
                    row['id'] != request['id'] or row['request_sha256'] != request['payload_sha256'] or
                    set(row['prediction']) != set(KEYS) or
                    any(row['prediction'][key] not in VALUES[key] for key in KEYS) or
                    type(row['input_tokens']) is not int or
                    not 0 <= row['input_tokens'] <= 4 * execution.solar.CONTEXT or
                    type(row['output_tokens']) is not int or row['output_tokens'] < 0 or
                    not isinstance(row['response_sha256'], str) or len(row['response_sha256']) != 64):
                raise ValueError('Solar projected answer differs')
            amount = Decimal(row['actual_cost_usd'])
            if amount != Decimal(row['input_tokens']) * execution.solar.PROMPT_RATE:
                raise ValueError('Solar projected token charge differs')
            total += amount
        score = sum(all(row['prediction'][key] == labels[row['id']][key] for key in KEYS)
                    for row in records)
        if (score != public['all_four_correct'] or
                {key: sum(row['prediction'][key] == labels[row['id']][key]
                          for row in records) for key in KEYS} != public['fields_correct'] or
                total != Decimal(public['known_development_cost_usd']) or
                total != Decimal(stage['known_development_cost_usd']) or
                public['source_sha256']['development_raw_private'] !=
                    receipt['source_sha256'][str(BASE / name / 'development.raw.jsonl')] or
                public['source_sha256']['development_parsed_private'] !=
                    receipt['source_sha256'][str(BASE / name / 'development.parsed.jsonl')] or
                public['source_sha256']['development_attempts'] !=
                    receipt['source_sha256'][str(BASE / name / 'development.attempts.jsonl')]):
            raise ValueError('Solar projected score, cost, or closure differs')
    return projection


def comparison(left, right):
    a = {row['id']: row['prediction'] for row in left['records']}
    b = {row['id']: row['prediction'] for row in right['records']}
    if set(a) != set(b):
        raise ValueError('Solar paired records differ')
    changed = [ident for ident in a if a[ident] != b[ident]]
    return {'left': left['stage'], 'right': right['stage'],
            'paired_records': 60, 'records_with_any_changed_answer': len(changed),
            'changed_record_ids': changed,
            'changed_fields': {key: sum(a[ident][key] != b[ident][key] for ident in a)
                               for key in KEYS}}


def prompt_control_check(root, left, right):
    plan = json.loads((root / 'results/solar-decide-native-full-v1/plan.json').read_text())
    by_stage = {item['id']: item for item in plan['phases']}
    a, b = (by_stage[name]['requests'] for name in (left, right))
    if len(a) != len(b) or len(a) != 60:
        raise ValueError('Solar prompt comparison length differs')
    for before, after in zip(a, b):
        x, y = before['payload'], after['payload']
        if (before['id'] != after['id'] or
                set(x) != {'model', 'state', 'questions', 'provider'} or
                set(y) != set(x) or
                x['model'] != y['model'] or x['state'] != y['state'] or
                x['provider'] != y['provider'] or x['questions'] == y['questions']):
            raise ValueError('Solar matched prompt controls differ')


def build(root=ROOT):
    root = Path(root).resolve()
    projection = portable_projection(root)
    labels = truth(root)
    stages = []
    by_stage = {item['stage']: item for item in projection['stages']}
    prompt_control_check(root, 'fresh1/P0', 'fresh1/P1')
    prompt_control_check(root, 'fresh1/P1', 'fresh1/P2')
    for item in projection['stages']:
        records = item['records']
        fields = {}
        for key in KEYS:
            confusion = {ref: {choice: 0 for choice in VALUES[key]} for ref in VALUES[key]}
            for row in records:
                confusion[labels[row['id']][key]][row['prediction'][key]] += 1
            fields[key] = {'correct': sum(confusion[value][value] for value in VALUES[key]),
                           'confusion_reference_by_choice': confusion}
        public = json.loads((root / BASE / item['stage'] / 'development.public-score.json').read_text())
        stages.append({'stage': item['stage'], 'records': 60, 'valid_answers': 60,
                       'all_four_correct': public['all_four_correct'], 'fields': fields,
                       'input_tokens': sum(row['input_tokens'] for row in records),
                       'output_tokens': sum(row['output_tokens'] for row in records),
                       'known_development_cost_usd': item['known_development_cost_usd'],
                       'known_smoke_cost_usd': public['known_smoke_cost_usd']})
    return {'schema': 'solar-decide-first-pass-findings-v1',
            'status': 'three_closed_first_pass_runs',
            'configuration': {'model': execution.solar.MODEL,
                              'returned_model': execution.solar.VERSION,
                              'provider': execution.solar.PROVIDER,
                              'interface': 'four native Choice questions'},
            'stage_order': list(STAGES), 'stages': stages,
            'paired_prompt_comparisons': [comparison(by_stage['fresh1/P0'], by_stage['fresh1/P1']),
                                          comparison(by_stage['fresh1/P1'], by_stage['fresh1/P2'])],
            'development_records': 180, 'valid_development_answers': 180,
            'known_development_cost_usd': str(sum((Decimal(s['known_development_cost_usd'])
                                                   for s in stages), Decimal(0))),
            'known_smoke_cost_usd': str(sum((Decimal(s['known_smoke_cost_usd'])
                                             for s in stages), Decimal(0))),
            'unknown_cost_attempts': 0,
            'cost_scope': 'Known model inference charge from provider usage. Development and three-record smoke charges are listed separately; local client time is excluded.',
            'comparison_scope': 'These are paired answer changes on the same 60 reviews in one pass. They do not establish a repeatable prompt gain.',
            'reference_status': 'Frozen provisional v0.2 development labels; the project owner confirmed human checks of all 60 reviews on 2026-10-02. Scores measure agreement with that key.',
            'verification_boundary': 'Private raw responses were decoded when the public projection was prepared. A copy without those raw files can verify archived hashes, scores and prices, but cannot decode the responses again.',
            'source_bindings': {'projection_sha256': digest(root / PROJECTION),
                                'projection_receipt_sha256': digest(root / RECEIPT),
                                'reference_sha256': digest(root / 'data/pilot/proposed_labels.jsonl')}}


def check(root=ROOT):
    root = Path(root).resolve()
    if json.loads((root / OUTPUT).read_text()) != build(root):
        raise ValueError('Published Solar first-pass findings differ')
    return digest(root / OUTPUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'check'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else check())


if __name__ == '__main__':
    main()
