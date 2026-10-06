#!/usr/bin/env python3
"""Publish source-bound closed DeepSeek low fresh3 stages and paired comparisons."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import KEYS, valid
import build_deepseek_low_p1_successor_findings as old_builder

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-low-remaining6-price-v2/remaining5-v4/p1-dev028-continuation-v1')
EXEC = BASE / 'execution-adapter-v1'
PARENT_EXEC = Path('results/repeatability-v1/deepseek-low-remaining6-price-v2/remaining5-v4/execution-adapter-v1')
OLD_PROJECTION = BASE / 'fresh2-p1-public-projection.json'
OLD_RECEIPT = BASE / 'fresh2-p1-public-projection.receipt.json'
LABELS = Path('data/pilot/proposed_labels.jsonl')
REVIEW = Path('docs/REFERENCE_REVIEW_V1.md')
SCRIPT = Path('scripts/build_deepseek_low_fresh3_findings.py')
TEST = Path('tests/test_build_deepseek_low_fresh3_findings.py')
VALIDATOR = Path('scripts/development_benchmark.py')
OUTPUT = Path('public-site/deepseek-low-fresh3-findings.json')
OLD_FEED = Path('public-site/deepseek-low-p1-successor-findings.json')
FINAL_RECONCILIATION = BASE / 'reconciliation-final.json'
FINAL_CHILD = BASE / 'budget-deepseek-low-p1-dev028-successor-v1.jsonl'
CONDITIONS = ('P1', 'P2', 'P0')
IDS = tuple(f'DEV-{n:03d}' for n in range(1, 61))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete DeepSeek low JSONL evidence')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def stage_path(condition, name):
    return EXEC / 'fresh3' / condition / name


def stage_snapshot_path(condition):
    name = ('child-ledger-snapshot-at-development-closure.jsonl' if condition == 'P1'
            else 'development-child-ledger-snapshot.jsonl')
    return stage_path(condition, name)


def parent_p0_path(name):
    return PARENT_EXEC / 'fresh2/P0' / name


def project_one(row, frozen):
    if (row.get('id') != frozen['record_id'] or
            row.get('request_sha256') != frozen['request_sha256'] or
            row.get('input_sha256') != frozen['input_sha256'] or
            row.get('instruction_sha256') != frozen['instruction_sha256'] or
            row.get('reference_labels_read') is not False or
            row.get('requested_model') != 'deepseek/deepseek-v4.1-flash' or
            row.get('returned_model') != 'deepseek/deepseek-v4.1-flash' or
            row.get('returned_provider') != 'OpenInference' or
            row.get('reasoning_effort') != 'low' or
            row.get('status') not in ('ok', 'invalid_output') or
            row.get('billing_ok') is not True or row.get('cost_unknown') is not False or
            not isinstance(row.get('observed_cost_usd'), str)):
        raise ValueError('Fresh3 private attempt differs from exact request or billing')
    if row['status'] == 'ok' and not valid(row.get('prediction')):
        raise ValueError('Fresh3 valid prediction differs')
    return {'id': row['id'], 'status': row['status'],
            'prediction': row['prediction'] if row['status'] == 'ok' else None,
            'known_cost_usd': row['observed_cost_usd']}


def score_positions(positions, labels):
    good = [row for row in positions if row['status'] == 'ok']
    return {'valid': len(good),
            'all_four_correct': sum(all(row['prediction'][k] == labels[row['id']][k]
                                        for k in KEYS) for row in good),
            'field_correct': {k: sum(row['prediction'][k] == labels[row['id']][k]
                                      for row in good) for k in KEYS},
            'outcomes': dict(Counter(row['status'] for row in positions)),
            'known_cost_usd': str(sum((Decimal(row['known_cost_usd']) for row in positions), Decimal()))}


def labels_at(root):
    references = rows(root / LABELS)
    if tuple(row['id'] for row in references) != IDS or any(not valid(row['proposed_labels']) for row in references):
        raise ValueError('Frozen references differ')
    return {row['id']: row['proposed_labels'] for row in references}


def prepare_stage(condition, root=ROOT):
    """One-time private-source projection and seal; never replace an existing file."""
    root = Path(root).resolve()
    if condition not in CONDITIONS:
        raise ValueError('Undeclared fresh3 condition')
    plan_path = EXEC / 'fresh3/manifest.json'
    frozen = json.loads((root / plan_path).read_text())['conditions'][condition]['development']
    source = stage_path(condition, 'development.attempts.jsonl')
    closure_path = stage_path(condition, 'development-closure.json')
    score_path = stage_path(condition, 'development-score.json')
    closure = json.loads((root / closure_path).read_text())
    saved_score = json.loads((root / score_path).read_text())
    private = rows(root / source)
    if (tuple(row['id'] for row in private) != IDS or
            tuple(row['record_id'] for row in frozen) != IDS or
            closure['strict_development_closure']['attempts_sha256'] != sha(root / source) or
            closure['attempted'] != 60 or closure['valid'] != sum(row['status'] == 'ok' for row in private) or
            closure['unknown_cost_ids'] or closure['provider_failures'] or
            saved_score['private_attempts_sha256'] != sha(root / source) or
            saved_score['closure_sha256'] != sha(root / closure_path)):
        raise ValueError('Fresh3 closure or private attempts differ')
    positions = [project_one(row, expected) for row, expected in zip(private, frozen)]
    measures = score_positions(positions, labels_at(root))
    if (measures['valid'] != saved_score['valid'] or
            measures['all_four_correct'] != saved_score['all_four_correct'] or
            measures['field_correct'] != saved_score['field_correct'] or
            measures['known_cost_usd'] != closure['development_known_cost_usd']):
        raise ValueError('Fresh3 offline score differs from private attempts')
    projection = {'schema': 'deepseek-low-fresh3-public-projection-v1',
        'stage': f'fresh3/{condition}', 'plan_sha256': sha(root / plan_path),
        'closure_sha256': sha(root / closure_path), 'score_sha256': sha(root / score_path),
        'private_attempts_sha256': sha(root / source), 'positions': positions,
        'verification_limit': 'Private attempts were verified before export; a clean checkout cannot decode omitted raw responses.'}
    projection_path = root / stage_path(condition, 'public-projection.json')
    with projection_path.open('x') as out:
        json.dump(projection, out, indent=2); out.write('\n')
    receipt = {'schema': 'deepseek-low-fresh3-public-projection-receipt-v1',
        'stage': f'fresh3/{condition}', 'projection_sha256': sha(projection_path),
        'private_attempts_sha256': sha(root / source),
        'closure_sha256': sha(root / closure_path), 'score_sha256': sha(root / score_path),
        'reference_labels_sha256': sha(root / LABELS), 'positions': 60,
        'outcomes': measures['outcomes'], 'valid': measures['valid'],
        'all_four_correct': measures['all_four_correct'],
        'field_correct': measures['field_correct'],
        'known_development_cost_usd': measures['known_cost_usd'],
        'verified_against_private_originals': True}
    receipt_path = root / stage_path(condition, 'public-projection.receipt.json')
    with receipt_path.open('x') as out:
        json.dump(receipt, out, indent=2); out.write('\n')
    return sha(receipt_path)


def prepare_parent_p0(root=ROOT):
    """Seal the independently closed earlier P0 phase for the repeat comparison."""
    root = Path(root).resolve()
    plan_path = PARENT_EXEC / 'fresh2/manifest.json'
    closure_path = parent_p0_path('development-closure.json')
    score_path = parent_p0_path('development-score.json')
    source = parent_p0_path('development.attempts.jsonl')
    closure = json.loads((root / closure_path).read_text())
    saved_score = json.loads((root / score_path).read_text())
    private = rows(root / source)
    frozen = json.loads((root / plan_path).read_text())['conditions']['P0']['development']
    if (tuple(row['id'] for row in private) != IDS or
            tuple(row['record_id'] for row in frozen) != IDS or
            closure['strict_development_closure']['attempts_sha256'] != sha(root / source) or
            saved_score['private_attempts_sha256'] != sha(root / source) or
            saved_score['closure_sha256'] != sha(root / closure_path) or
            closure['attempted'] != 60 or closure['valid'] != 59 or
            closure['unknown_cost_ids'] or closure['provider_failures']):
        raise ValueError('Earlier P0 closure or private attempts differ')
    positions = [project_one(row, expected) for row, expected in zip(private, frozen)]
    measures = score_positions(positions, labels_at(root))
    if (measures['valid'] != saved_score['valid'] or
            measures['all_four_correct'] != saved_score['all_four_correct'] or
            measures['field_correct'] != saved_score['field_correct'] or
            measures['known_cost_usd'] != closure['development_known_cost_usd']):
        raise ValueError('Earlier P0 private score differs')
    projection_path = root / parent_p0_path('public-projection.json')
    projection = {'schema': 'deepseek-low-parent-p0-public-projection-v1',
        'stage': 'fresh2/P0', 'plan_sha256': sha(root / plan_path),
        'closure_sha256': sha(root / closure_path), 'score_sha256': sha(root / score_path),
        'private_attempts_sha256': sha(root / source), 'positions': positions,
        'verification_limit': 'Private attempts were verified before export; a clean checkout cannot decode omitted raw responses.'}
    with projection_path.open('x') as out:
        json.dump(projection, out, indent=2); out.write('\n')
    receipt_path = root / parent_p0_path('public-projection.receipt.json')
    receipt = {'schema': 'deepseek-low-parent-p0-public-projection-receipt-v1',
        'stage': 'fresh2/P0', 'projection_sha256': sha(projection_path),
        'private_attempts_sha256': sha(root / source),
        'closure_sha256': sha(root / closure_path), 'score_sha256': sha(root / score_path),
        'reference_labels_sha256': sha(root / LABELS), 'positions': 60,
        'outcomes': measures['outcomes'], 'valid': measures['valid'],
        'all_four_correct': measures['all_four_correct'],
        'field_correct': measures['field_correct'],
        'known_development_cost_usd': measures['known_cost_usd'],
        'verified_against_private_originals': True}
    with receipt_path.open('x') as out:
        json.dump(receipt, out, indent=2); out.write('\n')
    return sha(receipt_path)


def bind(root, path, bindings):
    digest = sha(root / path)
    bindings[str(path)] = {'path': str(path), 'sha256': digest}
    return digest


def load_stage(condition, root, bindings, labels):
    closure_path = stage_path(condition, 'development-closure.json')
    score_path = stage_path(condition, 'development-score.json')
    projection_path = stage_path(condition, 'public-projection.json')
    receipt_path = stage_path(condition, 'public-projection.receipt.json')
    for path in (closure_path, score_path, projection_path, receipt_path,
                 stage_snapshot_path(condition),
                 stage_path(condition, 'smoke-inspection.json'),
                 stage_path(condition, 'smoke.root-review.json'),
                 stage_path(condition, 'development.root-review.json')):
        bind(root, path, bindings)
    closure = json.loads((root / closure_path).read_text())
    saved_score = json.loads((root / score_path).read_text())
    projection = json.loads((root / projection_path).read_text())
    receipt = json.loads((root / receipt_path).read_text())
    positions = projection['positions']
    if (projection.get('schema') != 'deepseek-low-fresh3-public-projection-v1' or
            projection.get('stage') != f'fresh3/{condition}' or
            projection.get('plan_sha256') != sha(root / EXEC / 'fresh3/manifest.json') or
            projection.get('closure_sha256') != sha(root / closure_path) or
            projection.get('score_sha256') != sha(root / score_path) or
            receipt.get('schema') != 'deepseek-low-fresh3-public-projection-receipt-v1' or
            receipt.get('stage') != f'fresh3/{condition}' or
            receipt.get('projection_sha256') != sha(root / projection_path) or
            receipt.get('private_attempts_sha256') != projection.get('private_attempts_sha256') or
            receipt.get('private_attempts_sha256') != closure['strict_development_closure']['attempts_sha256'] or
            receipt.get('closure_sha256') != sha(root / closure_path) or
            receipt.get('score_sha256') != sha(root / score_path) or
            receipt.get('reference_labels_sha256') != sha(root / LABELS) or
            receipt.get('verified_against_private_originals') is not True or
            closure.get('child_ledger_snapshot_sha256') != sha(root / stage_snapshot_path(condition)) or
            len(positions) != 60 or tuple(row['id'] for row in positions) != IDS):
        raise ValueError('Fresh3 source-bound projection receipt differs')
    for row in positions:
        if (row['status'] not in ('ok', 'invalid_output') or
                (row['status'] == 'ok' and not valid(row['prediction'])) or
                (row['status'] == 'invalid_output' and row['prediction'] is not None)):
            raise ValueError('Fresh3 projected status or prediction differs')
    measures = score_positions(positions, labels)
    if (receipt['positions'] != 60 or receipt['outcomes'] != measures['outcomes'] or
            receipt['valid'] != measures['valid'] or
            receipt['all_four_correct'] != measures['all_four_correct'] or
            receipt['field_correct'] != measures['field_correct'] or
            receipt['known_development_cost_usd'] != measures['known_cost_usd'] or
            saved_score['all_four_correct'] != measures['all_four_correct'] or
            saved_score['field_correct'] != measures['field_correct'] or
            saved_score['valid'] != measures['valid'] or
            closure['attempted'] != 60 or closure['valid'] != measures['valid'] or
            closure['development_known_cost_usd'] != measures['known_cost_usd'] or
            closure['unknown_cost_ids'] or closure['provider_failures']):
        raise ValueError('Fresh3 projection score or closure differs')
    private_path = root / stage_path(condition, 'development.attempts.jsonl')
    if private_path.exists() and sha(private_path) != receipt['private_attempts_sha256']:
        raise ValueError('Local private fresh3 attempts differ from sealed projection')
    return positions, measures


def load_parent_p0(root, bindings, labels):
    plan_path = PARENT_EXEC / 'fresh2/manifest.json'
    closure_path = parent_p0_path('development-closure.json')
    score_path = parent_p0_path('development-score.json')
    projection_path = parent_p0_path('public-projection.json')
    receipt_path = parent_p0_path('public-projection.receipt.json')
    snapshot_path = parent_p0_path('closure-ledger-snapshot.jsonl')
    for path in (plan_path, closure_path, score_path, projection_path, receipt_path,
                 snapshot_path, parent_p0_path('smoke-inspection.json'),
                 parent_p0_path('smoke.root-review.json'),
                 parent_p0_path('development.root-review.json')):
        bind(root, path, bindings)
    closure = json.loads((root / closure_path).read_text())
    score = json.loads((root / score_path).read_text())
    projection = json.loads((root / projection_path).read_text())
    receipt = json.loads((root / receipt_path).read_text())
    positions = projection['positions']
    if (projection.get('schema') != 'deepseek-low-parent-p0-public-projection-v1' or
            projection.get('stage') != 'fresh2/P0' or
            projection.get('plan_sha256') != sha(root / plan_path) or
            projection.get('closure_sha256') != sha(root / closure_path) or
            projection.get('score_sha256') != sha(root / score_path) or
            receipt.get('schema') != 'deepseek-low-parent-p0-public-projection-receipt-v1' or
            receipt.get('stage') != 'fresh2/P0' or
            receipt.get('projection_sha256') != sha(root / projection_path) or
            receipt.get('private_attempts_sha256') != projection.get('private_attempts_sha256') or
            receipt.get('private_attempts_sha256') != closure['strict_development_closure']['attempts_sha256'] or
            receipt.get('closure_sha256') != sha(root / closure_path) or
            receipt.get('score_sha256') != sha(root / score_path) or
            receipt.get('reference_labels_sha256') != sha(root / LABELS) or
            receipt.get('verified_against_private_originals') is not True or
            closure.get('child_ledger_snapshot_sha256') != sha(root / snapshot_path) or
            len(positions) != 60 or tuple(row['id'] for row in positions) != IDS):
        raise ValueError('Earlier P0 source-bound projection receipt differs')
    for row in positions:
        if (row['status'] not in ('ok', 'invalid_output') or
                (row['status'] == 'ok' and not valid(row['prediction'])) or
                (row['status'] == 'invalid_output' and row['prediction'] is not None)):
            raise ValueError('Earlier P0 projected status or prediction differs')
    measures = score_positions(positions, labels)
    if (receipt['positions'] != 60 or receipt['outcomes'] != measures['outcomes'] or
            receipt['valid'] != measures['valid'] or
            receipt['all_four_correct'] != measures['all_four_correct'] or
            receipt['field_correct'] != measures['field_correct'] or
            receipt['known_development_cost_usd'] != measures['known_cost_usd'] or
            score['all_four_correct'] != measures['all_four_correct'] or
            score['field_correct'] != measures['field_correct'] or
            score['valid'] != measures['valid'] or
            closure['attempted'] != 60 or closure['valid'] != measures['valid'] or
            closure['development_known_cost_usd'] != measures['known_cost_usd'] or
            closure['unknown_cost_ids'] or closure['provider_failures']):
        raise ValueError('Earlier P0 projection score or closure differs')
    private_path = root / parent_p0_path('development.attempts.jsonl')
    if private_path.exists() and sha(private_path) != receipt['private_attempts_sha256']:
        raise ValueError('Local earlier P0 attempts differ from sealed projection')
    return positions, measures


def paired(left, right, labels):
    a = {row['id']: row for row in left if row['status'] == 'ok'}
    b = {row['id']: row for row in right if row['status'] == 'ok'}
    shared = [record_id for record_id in IDS if record_id in a and record_id in b]
    flips = {k: [record_id for record_id in shared
                  if a[record_id]['prediction'][k] != b[record_id]['prediction'][k]] for k in KEYS}
    def all_four(position, record_id):
        return all(position[record_id]['prediction'][key] == labels[record_id][key] for key in KEYS)
    return {'shared_valid': len(shared), 'excluded_ids': [record_id for record_id in IDS if record_id not in shared],
            'all_four_left': sum(all_four(a, record_id) for record_id in shared),
            'all_four_right': sum(all_four(b, record_id) for record_id in shared),
            'field_correct_left': {key: sum(a[record_id]['prediction'][key] == labels[record_id][key]
                                            for record_id in shared) for key in KEYS},
            'field_correct_right': {key: sum(b[record_id]['prediction'][key] == labels[record_id][key]
                                             for record_id in shared) for key in KEYS},
            'all_four_wrong_to_correct': [record_id for record_id in shared if not all_four(a, record_id) and all_four(b, record_id)],
            'all_four_correct_to_wrong': [record_id for record_id in shared if all_four(a, record_id) and not all_four(b, record_id)],
            'label_flips': {key: {'count': len(ids), 'ids': ids} for key, ids in flips.items()}}


def build(root=ROOT):
    root = Path(root).resolve()
    if sha(root / SCRIPT) != sha(__file__) or sha(root / TEST) != sha(ROOT / TEST):
        raise ValueError('Loaded fresh3 reporter differs from selected root')
    bindings = {}
    for path in (SCRIPT, TEST, VALIDATOR, LABELS, REVIEW, OLD_PROJECTION,
                 OLD_RECEIPT, OLD_FEED, EXEC / 'fresh3/manifest.json',
                 FINAL_RECONCILIATION, FINAL_CHILD):
        bind(root, path, bindings)
    final = json.loads((root / FINAL_RECONCILIATION).read_text())
    reconciled = final['partition_reconciled']
    if (final.get('schema') != 'deepseek-low-p1-dev028-successor-final-reconciliation-v1' or
            final.get('authority_hold_released') is not False or
            final.get('final_p0_closure_sha256') != sha(root / stage_path('P0', 'development-closure.json')) or
            reconciled.get('partition_id') != 'deepseek-low-p1-dev028-successor-v1' or
            reconciled.get('child_sha256') != sha(root / FINAL_CHILD) or
            reconciled.get('known_actual_usd') != '0.099872777706' or
            reconciled.get('unknown_upper_bound_usd') != '0' or
            reconciled.get('unused_allocation_released_usd') != '0.400127222294'):
        raise ValueError('Final low successor child reconciliation differs')
    saved_old = json.loads((root / OLD_FEED).read_text())
    if old_builder.build(root) != saved_old:
        raise ValueError('Previously published low P1 report differs')
    for item in saved_old['sourceBindings']:
        path = Path(item['path'])
        if bind(root, path, bindings) != item['sha256']:
            raise ValueError('Previously bound low P1 evidence changed')
    labels = labels_at(root)
    old = json.loads((root / OLD_PROJECTION).read_text())
    old_receipt = json.loads((root / OLD_RECEIPT).read_text())
    if (old.get('schema') != 'deepseek-low-p1-successor-public-projection-v1' or
            old.get('stage') != 'fresh2/P1' or
            old_receipt.get('projection_sha256') != sha(root / OLD_PROJECTION) or
            old_receipt.get('verified_against_private_originals') is not True or
            old_receipt.get('valid_count') != 57 or
            tuple(row['id'] for row in old['positions']) != IDS):
        raise ValueError('Frozen fresh2/P1 projection differs')
    stages = {}; positions = {}
    for condition in CONDITIONS:
        positions[condition], measures = load_stage(condition, root, bindings, labels)
        stages[condition] = {'attempted': 60, 'valid': measures['valid'],
            'outcomes': measures['outcomes'], 'allFourCorrect': measures['all_four_correct'],
            'fieldCorrect': measures['field_correct'], 'knownDevelopmentCostUsd': measures['known_cost_usd'],
            'invalidIds': [row['id'] for row in positions[condition] if row['status'] != 'ok']}
    earlier_p0, earlier_p0_measures = load_parent_p0(root, bindings, labels)
    earlier_p0_summary = {'attempted': 60, 'valid': earlier_p0_measures['valid'],
        'outcomes': earlier_p0_measures['outcomes'],
        'allFourCorrect': earlier_p0_measures['all_four_correct'],
        'fieldCorrect': earlier_p0_measures['field_correct'],
        'knownDevelopmentCostUsd': earlier_p0_measures['known_cost_usd'],
        'invalidIds': [row['id'] for row in earlier_p0 if row['status'] != 'ok']}
    comparisons = {}
    for left, right in (('P1', 'P2'), ('P1', 'P0'), ('P2', 'P0')):
        comparisons[f'fresh3/{left}_vs_fresh3/{right}'] = paired(positions[left], positions[right], labels)
    comparisons['fresh2/P1_vs_fresh3/P1'] = paired(old['positions'], positions['P1'], labels)
    comparisons['fresh2/P0_vs_fresh3/P0'] = paired(earlier_p0, positions['P0'], labels)
    result = {'schema': 'deepseek-low-fresh3-findings-v1',
        'configurationId': 'openrouter-paid-deepseek-v41-flash-low-remaining6-price-v2',
        'status': 'three_fresh3_phases_closed', 'stages': stages,
        'earlierClosedFresh2P0': earlier_p0_summary, 'comparisons': comparisons,
        'referenceStatus': 'Frozen provisional v0.2 labels; owner confirmed human checks on 2026-10-02, without independent adjudication.',
        'privateRawVerificationLimit': 'Private attempts were checked at projection sealing. Clean checkouts verify bound closures, projections, receipts and scores, but cannot re-decode omitted raw responses.',
        'sourceBindings': list(bindings.values())}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare-stage', 'prepare-parent-p0', 'check', 'build'))
    parser.add_argument('--condition', choices=CONDITIONS)
    args = parser.parse_args()
    if args.action == 'prepare-stage':
        if not args.condition: parser.error('prepare-stage requires --condition')
        print(prepare_stage(args.condition)); return
    if args.action == 'prepare-parent-p0':
        print(prepare_parent_p0()); return
    result = build()
    if args.action == 'build':
        (ROOT / OUTPUT).write_text(json.dumps(result, indent=2) + '\n')
    elif (ROOT / OUTPUT).exists() and json.loads((ROOT / OUTPUT).read_text()) != result:
        raise ValueError('Published DeepSeek low fresh3 findings differ')
    print(json.dumps({'stages': {k:v['valid'] for k,v in result['stages'].items()},
                      'source_bindings': len(result['sourceBindings'])}))


if __name__ == '__main__':
    main()
