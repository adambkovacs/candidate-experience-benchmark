#!/usr/bin/env python3
"""Publish the nine closed Tev native Choice runs from checked evidence."""
import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
import tev_full_execution_v1 as full
import tev_smoke_v1 as smoke

BASE = Path('results/tev-native-v1/full-v1')
PROJECTION = BASE / 'public-projection.json'
RECEIPT = BASE / 'public-projection.receipt.json'
OUTPUT = Path('public-site/tev-native-full-findings.json')
STAGES = full.PHASES
THRESHOLDS = (0.9, 0.99)


def sha(path):
    return full.sha(path)


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True)
        out.write('\n')


def truth_rows(root):
    rows = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    if len(rows) != 60 or [row['id'] for row in rows] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Frozen Tev reference set differs')
    return {row['id']: row['proposed_labels'] for row in rows}


def source_paths(stage):
    folder = BASE / stage
    return {name: folder / ('development.' + name) for name in
            ('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl',
             'closure-audit.json', 'ledger-snapshot.jsonl')}


def checked_private_stage(stage):
    folder = full.BASE / stage
    full.verify_phase_closure(stage, 'development')
    receipt = json.loads((folder / 'development.closure-audit.json').read_text())
    paths = source_paths(stage)
    for name, relpath in paths.items():
        if name == 'closure-audit.json':
            continue
        if receipt['source_sha256'].get(str(relpath)) != sha(ROOT / relpath):
            raise ValueError('Tev closure source differs: ' + stage + '/' + name)
    if (receipt['status'] != 'closed' or receipt['request_count'] != 60 or
            receipt['valid_native_responses'] != 60 or receipt['intrinsic_invalid_count'] or
            receipt['provider_failures'] or receipt['unknown_cost_attempts'] or
            receipt['unknown_upper_bound_usd'] != '0' or
            receipt['ledger_snapshot_sha256'] != sha(folder / 'development.ledger-snapshot.jsonl')):
        raise ValueError('Tev stage is not a closed 60-answer run')
    raw, attempts, parsed = (full.jsonl(ROOT / paths[name]) for name in
                             ('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl'))
    if len(raw) != len(attempts) or len(raw) != len(parsed):
        raise ValueError('Tev private stage row count differs')
    rows = []
    known = Decimal(0)
    for index, (record, attempt, prediction) in enumerate(zip(raw, attempts, parsed), 1):
        ident = f'DEV-{index:03}'
        body = json.loads(base64.b64decode(record['response_base64'], validate=True))
        decoded, optional = smoke.validate_returned(body)
        cost = full.native.response_cost(body)
        if (record['id'] != ident or attempt['id'] != ident or prediction['id'] != ident or
                full.native.sha(base64.b64decode(record['response_base64'], validate=True)) !=
                record['response_sha256'] or attempt['status'] != 'ok' or
                prediction['prediction'] != decoded or prediction['optional'] != optional or
                prediction['input_tokens'] != body['usage']['input_tokens'] or
                prediction['output_tokens'] != body['usage']['output_tokens'] or
                Decimal(prediction['actual_cost_usd']) != cost):
            raise ValueError('Tev raw response or parsed prediction differs')
        known += cost
        rows.append({'id': ident, 'prediction': decoded, 'optional': optional,
                     'input_tokens': prediction['input_tokens'],
                     'output_tokens': prediction['output_tokens'],
                     'actual_cost_usd': prediction['actual_cost_usd'],
                     'request_sha256': record['payload_sha256'],
                     'response_sha256': record['response_sha256']})
    if len(rows) != 60 or str(known) != receipt['known_actual_usd']:
        raise ValueError('Tev private stage cost differs')
    return {'stage': stage, 'records': rows,
            'known_actual_usd': receipt['known_actual_usd'],
            'source_sha256': {name: sha(ROOT / path) for name, path in paths.items()}}


def prepare(root=ROOT):
    root = Path(root).resolve()
    if root != ROOT.resolve():
        raise ValueError('Private Tev preparation requires the execution checkout')
    terminal = json.loads((root / BASE / 'terminal-reconciliation.json').read_text())
    if (terminal['status'] != 'nine_phases_closed_child_sealed_master_reconciled' or
            terminal['development_phases'] != 9 or terminal['unknown_upper_bound_usd'] != '0' or
            terminal['child_ledger_sha256'] != sha(full.CHILD)):
        raise ValueError('Tev full terminal reconciliation differs')
    stages = [checked_private_stage(stage) for stage in STAGES]
    projection = {'schema': 'tev-native-full-public-projection-v1',
                  'stages': stages, 'reference_labels_sent': False,
                  'private_raw_verification': 'All 540 private raw responses were decoded and checked during preparation.'}
    write_new(root / PROJECTION, projection)
    sources = {'scripts/build_tev_native_full_findings.py': sha(__file__),
               'tests/test_build_tev_native_full_findings.py': sha(root / 'tests/test_build_tev_native_full_findings.py'),
               str(BASE / 'manifest.json'): sha(root / BASE / 'manifest.json'),
               str(BASE / 'terminal-reconciliation.json'): sha(root / BASE / 'terminal-reconciliation.json'),
               str(BASE / ('budget-' + full.PARTITION_ID + '.jsonl')): sha(full.CHILD),
               'data/pilot/proposed_labels.jsonl': sha(root / 'data/pilot/proposed_labels.jsonl')}
    for stage in stages:
        for name, digest in stage['source_sha256'].items():
            sources[str(source_paths(stage['stage'])[name])] = digest
    write_new(root / RECEIPT, {'schema': 'tev-native-full-public-projection-receipt-v1',
              'projection_sha256': sha(root / PROJECTION), 'source_sha256': sources,
              'private_raw_checked_at_prepare': True,
              'portable_limit': 'Absent private raw bytes are checked by archived hash, not decoded again.'})
    value = build(root)
    write_new(root / OUTPUT, value)
    return sha(root / OUTPUT)


def field_summary(rows, truth, key):
    confusion = {reference: {choice: 0 for choice in VALUES[key]} for reference in VALUES[key]}
    for row in rows:
        confusion[truth[row['id']][key]][row['prediction'][key]] += 1
    threshold_rows = {}
    for threshold in THRESHOLDS:
        eligible = [row for row in rows if row['optional'][key]['confidence'] is not None and
                    row['optional'][key]['confidence'] >= threshold]
        correct = sum(row['prediction'][key] == truth[row['id']][key] for row in eligible)
        threshold_rows[str(threshold)] = {'retained': len(eligible),
            'correct_retained': correct, 'confidently_wrong': len(eligible) - correct,
            'missing_confidence': sum(row['optional'][key]['confidence'] is None for row in rows)}
    return {'correct': sum(confusion[value][value] for value in VALUES[key]),
            'denominator': len(rows), 'confusion_reference_by_choice': confusion,
            'native_confidence_thresholds': threshold_rows,
            'confidence_available': sum(row['optional'][key]['confidence_available'] for row in rows),
            'probabilities_available': sum(row['optional'][key]['probabilities_available'] for row in rows)}


def compare(left, right):
    a = {row['id']: row['prediction'] for row in left['records']}
    b = {row['id']: row['prediction'] for row in right['records']}
    if set(a) != set(b):
        raise ValueError('Tev matched comparison records differ')
    changed = [ident for ident in sorted(a) if a[ident] != b[ident]]
    return {'left': left['stage'], 'right': right['stage'],
            'records_with_any_changed_answer': len(changed),
            'changed_record_ids': changed,
            'changed_fields': {key: sum(a[ident][key] != b[ident][key] for ident in a)
                               for key in KEYS}}


def portable_check(root=ROOT):
    root = Path(root).resolve()
    receipt = json.loads((root / RECEIPT).read_text())
    projection = json.loads((root / PROJECTION).read_text())
    if (receipt.get('schema') != 'tev-native-full-public-projection-receipt-v1' or
            receipt.get('projection_sha256') != sha(root / PROJECTION) or
            receipt.get('private_raw_checked_at_prepare') is not True or
            projection.get('schema') != 'tev-native-full-public-projection-v1' or
            projection.get('reference_labels_sent') is not False or
            [stage['stage'] for stage in projection['stages']] != list(STAGES)):
        raise ValueError('Tev public projection receipt differs')
    for name, digest in receipt['source_sha256'].items():
        path = root / name
        if path.is_file() and sha(path) != digest:
            raise ValueError('Tev public source changed: ' + name)
        if not path.is_file() and not name.endswith(('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')):
            raise ValueError('Required Tev public source missing: ' + name)
    terminal = json.loads((root / BASE / 'terminal-reconciliation.json').read_text())
    if (terminal['status'] != 'nine_phases_closed_child_sealed_master_reconciled' or
            terminal['development_phases'] != 9 or terminal['unknown_upper_bound_usd'] != '0' or
            terminal['child_ledger_sha256'] != receipt['source_sha256'].get(str(BASE / ('budget-' + full.PARTITION_ID + '.jsonl')))):
        raise ValueError('Tev terminal receipt differs')
    truth = truth_rows(root)
    for stage in projection['stages']:
        name = stage['stage']
        folder = root / BASE / name
        closure = json.loads((folder / 'development.closure-audit.json').read_text())
        if (closure['status'] != 'closed' or closure['valid_native_responses'] != 60 or
                closure['unknown_upper_bound_usd'] != '0' or
                stage['known_actual_usd'] != closure['known_actual_usd'] or
                terminal['stage_sources'][name]['development_closure_sha256'] !=
                    sha(folder / 'development.closure-audit.json') or
                terminal['stage_sources'][name]['development_ledger_snapshot_sha256'] !=
                    sha(folder / 'development.ledger-snapshot.jsonl') or
                stage['source_sha256'] != {k: receipt['source_sha256'][str(v)]
                 for k, v in source_paths(name).items()}):
            raise ValueError('Tev projected stage closure differs')
        rows = stage['records']
        if len(rows) != 60 or [row['id'] for row in rows] != list(truth):
            raise ValueError('Tev public 60-record denominator differs')
        total = Decimal(0)
        for row in rows:
            if (set(row) != {'id', 'prediction', 'optional', 'input_tokens', 'output_tokens',
                            'actual_cost_usd', 'request_sha256', 'response_sha256'} or
                    set(row['prediction']) != set(KEYS) or set(row['optional']) != set(KEYS) or
                    any(row['prediction'][key] not in VALUES[key] for key in KEYS) or
                    any(type(row[t]) is not int for t in ('input_tokens','output_tokens')) or
                    not 0 <= row['input_tokens'] <= full.tev.QUESTION_COUNT * full.tev.CONTEXT or
                    row['output_tokens'] < 0):
                raise ValueError('Tev public record differs')
            for key in KEYS:
                option = row['optional'][key]
                if set(option) != {'probabilities', 'confidence', 'probabilities_available', 'confidence_available'}:
                    raise ValueError('Tev public native option differs')
                if (option['confidence_available'] != (option['confidence'] is not None) or
                        option['probabilities_available'] != (option['probabilities'] is not None)):
                    raise ValueError('Tev public native availability differs')
                if option['confidence'] is not None and (type(option['confidence']) not in (float,int) or
                        not math.isfinite(option['confidence']) or not 0 <= option['confidence'] <= 1):
                    raise ValueError('Tev public native confidence differs')
                probs = option['probabilities']
                if probs is not None and (set(probs) != set(VALUES[key]) or
                        any(type(p) not in (float,int) or not math.isfinite(p) or not 0 <= p <= 1
                            for p in probs.values()) or abs(sum(probs.values()) - 1) > .001):
                    raise ValueError('Tev public native probabilities differ')
            cost = Decimal(row['actual_cost_usd'])
            if cost != Decimal(row['input_tokens']) * full.tev.RATE:
                raise ValueError('Tev public token price differs')
            total += cost
        raw_path = folder / 'development.raw.jsonl'
        if raw_path.is_file():
            raw = full.jsonl(raw_path)
            if len(raw) != 60:
                raise ValueError('Tev private raw row count differs')
            for recorded, projected in zip(raw, rows):
                body_bytes = base64.b64decode(recorded['response_base64'], validate=True)
                body = json.loads(body_bytes)
                decoded, options = smoke.validate_returned(body)
                if (recorded['id'] != projected['id'] or
                        full.native.sha(body_bytes) != recorded['response_sha256'] or
                        recorded['response_sha256'] != projected['response_sha256'] or
                        recorded['payload_sha256'] != projected['request_sha256'] or
                        decoded != projected['prediction'] or options != projected['optional'] or
                        body['usage']['input_tokens'] != projected['input_tokens'] or
                        body['usage']['output_tokens'] != projected['output_tokens']):
                    raise ValueError('Tev private raw/public projection differs')
        if str(total) != stage['known_actual_usd']:
            raise ValueError('Tev public stage total differs')
    return projection


def build(root=ROOT):
    root = Path(root).resolve()
    projection = portable_check(root)
    truth = truth_rows(root)
    stage_values = []
    for stage in projection['stages']:
        rows = stage['records']
        fields = {key: field_summary(rows, truth, key) for key in KEYS}
        stage_values.append({'stage': stage['stage'], 'records': 60, 'valid_answers': 60,
            'all_four_correct': sum(all(row['prediction'][key] == truth[row['id']][key] for key in KEYS)
                                    for row in rows),
            'fields': fields, 'input_tokens': sum(row['input_tokens'] for row in rows),
            'output_tokens': sum(row['output_tokens'] for row in rows),
            'known_actual_usd': stage['known_actual_usd']})
    by_stage = {stage['stage']: stage for stage in projection['stages']}
    repeat_comparisons = [compare(by_stage[f'fresh{a}/{condition}'], by_stage[f'fresh{a+1}/{condition}'])
        for condition in ('P0','P1','P2') for a in (1,2)]
    prompt_comparisons = [compare(by_stage[f'fresh{a}/P0'], by_stage[f'fresh{a}/P1'])
        for a in (1,2,3)] + [compare(by_stage[f'fresh{a}/P1'], by_stage[f'fresh{a}/P2'])
        for a in (1,2,3)]
    terminal = json.loads((root / BASE / 'terminal-reconciliation.json').read_text())
    return {'schema': 'tev-native-full-findings-v1', 'status': 'nine_closed_development_runs',
        'configuration': {'model': full.tev.MODEL, 'returned_model': full.tev.VERSION,
            'provider': full.tev.PROVIDER, 'interface': 'four native Choice questions'},
        'stage_order': list(STAGES), 'stages': stage_values,
        'repeat_comparisons': repeat_comparisons, 'matched_prompt_comparisons': prompt_comparisons,
        'development_records': 540, 'development_valid_answers': 540,
        'development_known_actual_usd': str(sum((Decimal(s['known_actual_usd']) for s in stage_values), Decimal(0))),
        'child_all_requests': {'settled': terminal['settled_requests'],
            'known_actual_usd': terminal['known_actual_usd'],
            'unknown_upper_bound_usd': terminal['unknown_upper_bound_usd'],
            'includes_eight_three_request_smokes': True,
            'unused_allocation_released_usd': terminal['unused_allocation_released_usd']},
        'cost_scope': 'Known model inference charge from provider token usage; excludes local client work. Development cost excludes 24 in-child smoke calls; child total includes them.',
        'confidence_note': 'Native provider confidence and probabilities describe these answers. Threshold counts use the same 60 records per run; they are not calibrated or externally validated.',
        'reference_status': 'Frozen provisional development labels; no independent adjudication.',
        'verification_boundary': 'The public checker verifies a preparation-time receipt, checked source hashes, token prices and offline scores. If private raw files are absent, it cannot independently decode those response bytes.',
        'source_bindings': {'projection_sha256': sha(root / PROJECTION),
            'projection_receipt_sha256': sha(root / RECEIPT),
            'terminal_reconciliation_sha256': sha(root / BASE / 'terminal-reconciliation.json'),
            'reference_sha256': sha(root / 'data/pilot/proposed_labels.jsonl')}}


def check(root=ROOT):
    root = Path(root).resolve()
    expected = build(root)
    if json.loads((root / OUTPUT).read_text()) != expected:
        raise ValueError('Published Tev findings differ')
    return sha(root / OUTPUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','check'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else check())


if __name__ == '__main__':
    main()
