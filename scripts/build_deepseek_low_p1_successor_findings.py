#!/usr/bin/env python3
"""Publish the closed DeepSeek low P1 composite from an audited projection."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-low-remaining6-price-v2/remaining5-v4')
PARENT = BASE / 'execution-adapter-v1/fresh2/P1'
SUCCESSOR = BASE / 'p1-dev028-continuation-v1'
TAIL = SUCCESSOR / 'execution-adapter-v1/fresh2/P1'
PARENT_PLAN = BASE / 'execution-adapter-v1/fresh2/manifest.json'
TAIL_PLAN = SUCCESSOR / 'execution-adapter-v1/fresh2/manifest.json'
AUDIT = PARENT / 'terminal-audit.json'
RECONCILIATION = BASE / 'reconciliation-after-dev027.json'
CLOSURE = TAIL / 'suffix-closure.json'
PARENT_SNAPSHOT = PARENT / 'terminal-ledger-snapshot.jsonl'
CLOSED_PARENT = SUCCESSOR / 'predecessor-closed-ledger-snapshot.jsonl'
TAIL_SNAPSHOT = TAIL / 'suffix-child-ledger-snapshot.jsonl'
PARENT_PRIVATE = PARENT / 'development.attempts.jsonl'
TAIL_PRIVATE = TAIL / 'development.attempts.jsonl'
PROJECTION = SUCCESSOR / 'fresh2-p1-public-projection.json'
PROJECTION_RECEIPT = SUCCESSOR / 'fresh2-p1-public-projection.receipt.json'
LABELS = Path('data/pilot/proposed_labels.jsonl')
REFERENCE_REVIEW = Path('docs/REFERENCE_REVIEW_V1.md')
VALIDATOR = Path('scripts/development_benchmark.py')
OUTPUT = Path('public-site/deepseek-low-p1-successor-findings.json')
SCRIPT = Path('scripts/build_deepseek_low_p1_successor_findings.py')
TEST = Path('tests/test_build_deepseek_low_p1_successor_findings.py')
IDS = [f'DEV-{n:03}' for n in range(1, 61)]
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported',
          'testimonial_potential')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete low P1 JSONL evidence')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def project_row(record, frozen):
    if (record.get('id') != frozen['record_id'] or
            record.get('request_sha256') != frozen['request_sha256'] or
            record.get('input_sha256') != frozen['input_sha256'] or
            record.get('instruction_sha256') != frozen['instruction_sha256'] or
            record.get('reference_labels_read') is not False or
            record.get('requested_model') != 'deepseek/deepseek-v4.1-flash' or
            record.get('reasoning_effort') != 'low'):
        raise ValueError('Low P1 attempt differs from frozen request')
    status = record['status']
    if status not in ('ok', 'invalid_output', 'service_error'):
        raise ValueError('Unexpected low P1 status')
    if status == 'ok' and (not valid(record.get('prediction')) or
                           record.get('cost_unknown') is not False or
                           record.get('billing_ok') is not True):
        raise ValueError('Valid low P1 answer or billing differs')
    if status == 'invalid_output' and (record.get('cost_unknown') is not False or
                                        record.get('billing_ok') is not True):
        raise ValueError('Intrinsic invalid low P1 billing differs')
    if status == 'service_error' and (record['id'] != 'DEV-027' or
                                      record.get('cost_unknown') is not True or
                                      record.get('observed_cost_usd') is not None or
                                      record.get('reserved_cost_usd') != '0.06905856'):
        raise ValueError('Retained low P1 provider failure differs')
    return {'id': record['id'], 'status': status,
            'prediction': record['prediction'] if status == 'ok' else None,
            'known_cost_usd': record['observed_cost_usd'],
            'unknown_upper_bound_usd': record['reserved_cost_usd'] if status == 'service_error' else None}


def prepare_projection(root=ROOT):
    """One-time sanitized export; private attempt files stay outside Git."""
    root = Path(root).resolve()
    audit = json.loads((root / AUDIT).read_text())
    closure = json.loads((root / CLOSURE).read_text())
    if (audit.get('schema') != 'deepseek-low-remaining5-v4-fresh2-p1-interruption-audit-v1' or
            closure.get('schema') != 'deepseek-low-p1-dev028-suffix-closure-v1' or
            closure.get('status') != 'suffix_closed_composite_interrupted' or
            audit.get('attempted_ids') != IDS[:27] or
            closure.get('suffix_attempted_ids') != IDS[27:] or
            audit['evidence_sha256'].get('development.attempts.jsonl') != sha(root / PARENT_PRIVATE) or
            closure['strict_phase_closure']['attempts_sha256'] != sha(root / TAIL_PRIVATE)):
        raise ValueError('Low P1 private projection source differs')
    parent = rows(root / PARENT_PRIVATE)
    tail = rows(root / TAIL_PRIVATE)
    frozen_parent = json.loads((root / PARENT_PLAN).read_text())['conditions']['P1']['development']
    frozen_tail = json.loads((root / TAIL_PLAN).read_text())['conditions']['P1']['development']
    if ([r['id'] for r in parent + tail] != IDS or
            [r['record_id'] for r in frozen_parent] != IDS or
            [r['record_id'] for r in frozen_tail] != IDS[27:]):
        raise ValueError('Low P1 projected positions differ')
    positions = [project_row(record, frozen) for record, frozen in
                 zip(parent + tail, frozen_parent[:27] + frozen_tail)]
    value = {'schema': 'deepseek-low-p1-successor-public-projection-v1',
        'configuration_id': audit.get('configuration_id') or
            json.loads((root / PARENT_PLAN).read_text())['configuration_id'],
        'stage': 'fresh2/P1',
        'clean_full_phase': False,
        'parent_private_attempts_sha256': sha(root / PARENT_PRIVATE),
        'suffix_private_attempts_sha256': sha(root / TAIL_PRIVATE),
        'parent_audit_sha256': sha(root / AUDIT),
        'suffix_closure_sha256': sha(root / CLOSURE),
        'parent_plan_sha256': sha(root / PARENT_PLAN),
        'suffix_plan_sha256': sha(root / TAIL_PLAN),
        'positions': positions,
        'verification_limit': 'The private raw responses were checked before this projection. '
            'A clean checkout verifies the bound audit, projection, ledger snapshots and plans, '
            'but cannot decode private response bodies.'}
    target = root / PROJECTION
    with target.open('x') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write('\n')
    return sha(target)


def seal_projection(root=ROOT):
    """Bind the public projection to the private attempts before archive."""
    root = Path(root).resolve()
    projection = json.loads((root / PROJECTION).read_text())
    audit = json.loads((root / AUDIT).read_text())
    closure = json.loads((root / CLOSURE).read_text())
    if (sha(root / PARENT_PRIVATE) != audit['evidence_sha256']['development.attempts.jsonl'] or
            sha(root / TAIL_PRIVATE) != closure['strict_phase_closure']['attempts_sha256'] or
            projection.get('parent_private_attempts_sha256') != sha(root / PARENT_PRIVATE) or
            projection.get('suffix_private_attempts_sha256') != sha(root / TAIL_PRIVATE)):
        raise ValueError('Private low P1 projection source differs before sealing')
    parent = rows(root / PARENT_PRIVATE)
    tail = rows(root / TAIL_PRIVATE)
    frozen_parent = json.loads((root / PARENT_PLAN).read_text())['conditions']['P1']['development']
    frozen_tail = json.loads((root / TAIL_PLAN).read_text())['conditions']['P1']['development']
    expected = [project_row(record, frozen) for record, frozen in
                zip(parent + tail, frozen_parent[:27] + frozen_tail)]
    if (len(parent) != 27 or len(tail) != 33 or
            [row['id'] for row in expected] != IDS or
            projection.get('positions') != expected):
        raise ValueError('Public low P1 projection differs from private attempts')
    labels = {row['id']: row['proposed_labels'] for row in rows(root / LABELS)}
    if list(labels) != IDS:
        raise ValueError('Frozen low P1 reference membership differs')
    valid_rows = [row for row in expected if row['status'] == 'ok']
    all_four = sum(all(row['prediction'][field] == labels[row['id']][field]
                       for field in FIELDS) for row in valid_rows)
    fields = {field: sum(row['prediction'][field] == labels[row['id']][field]
                         for row in valid_rows) for field in FIELDS}
    known = sum((Decimal(row['known_cost_usd']) for row in expected
                 if row['known_cost_usd'] is not None), Decimal())
    receipt = {'schema': 'deepseek-low-p1-public-projection-receipt-v1',
        'projection_sha256': sha(root / PROJECTION),
        'parent_audit_sha256': sha(root / AUDIT),
        'suffix_closure_sha256': sha(root / CLOSURE),
        'parent_private_attempts_sha256': sha(root / PARENT_PRIVATE),
        'suffix_private_attempts_sha256': sha(root / TAIL_PRIVATE),
        'reference_labels_sha256': sha(root / LABELS),
        'positions': 60,
        'status_counts': dict(Counter(row['status'] for row in expected)),
        'valid_count': len(valid_rows),
        'all_four_correct': all_four,
        'field_correct': fields,
        'known_development_cost_usd': str(known),
        'unknown_cost_upper_bound_usd': '0.06905856',
        'verified_against_private_originals': True}
    target = root / PROJECTION_RECEIPT
    with target.open('x') as out:
        json.dump(receipt, out, indent=2)
        out.write('\n')
    return sha(target)


def source(root, relative, bindings, expected=None):
    target = root / relative
    digest = sha(target)
    if expected is not None and digest != expected:
        raise ValueError('Low P1 bound source changed: ' + str(relative))
    bindings[str(relative)] = {'path': str(relative), 'sha256': digest}
    return digest


def build(root=ROOT):
    root = Path(root).resolve()
    if sha(root / SCRIPT) != sha(__file__) or sha(root / TEST) != sha(ROOT / TEST):
        raise ValueError('Loaded low P1 reporter differs from selected root')
    bindings = {}
    for path in (SCRIPT, TEST, VALIDATOR, AUDIT, RECONCILIATION, CLOSURE,
                 PARENT_SNAPSHOT, CLOSED_PARENT, TAIL_SNAPSHOT,
                 PARENT_PLAN, TAIL_PLAN, PROJECTION, PROJECTION_RECEIPT,
                 LABELS, REFERENCE_REVIEW):
        source(root, path, bindings)
    audit = json.loads((root / AUDIT).read_text())
    closed = json.loads((root / RECONCILIATION).read_text())['partition_reconciled']
    closure = json.loads((root / CLOSURE).read_text())
    projection = json.loads((root / PROJECTION).read_text())
    projection_receipt = json.loads((root / PROJECTION_RECEIPT).read_text())
    if (audit.get('attempted_ids') != IDS[:27] or
            audit.get('unsent_ids') != IDS[27:] or
            audit.get('valid_outputs') != 25 or
            audit.get('intrinsic_invalid', {}).get('id') != 'DEV-006' or
            audit.get('terminal_failure', {}).get('id') != 'DEV-027' or
            audit.get('terminal_failure', {}).get('cost_unknown') is not True or
            closed.get('child_sha256') != sha(root / CLOSED_PARENT) or
            closed.get('unknown_upper_bound_usd') != '0.06905856' or
            closure.get('suffix_attempted_ids') != IDS[27:] or
            closure.get('suffix_valid_count') != 32 or
            closure.get('suffix_intrinsic_invalid', [{}])[0].get('id') != 'DEV-030' or
            closure.get('suffix_unknown_cost_ids') != [] or
            closure.get('child_ledger_snapshot_sha256') != sha(root / TAIL_SNAPSHOT) or
            closure.get('clean_full_phase') is not False or
            closure.get('full_60_clean_score') is not None or
            projection.get('schema') != 'deepseek-low-p1-successor-public-projection-v1' or
            projection.get('parent_audit_sha256') != sha(root / AUDIT) or
            projection.get('suffix_closure_sha256') != sha(root / CLOSURE) or
            projection.get('parent_plan_sha256') != sha(root / PARENT_PLAN) or
            projection.get('suffix_plan_sha256') != sha(root / TAIL_PLAN) or
            projection.get('parent_private_attempts_sha256') !=
                audit['evidence_sha256']['development.attempts.jsonl'] or
            projection.get('suffix_private_attempts_sha256') !=
                closure['strict_phase_closure']['attempts_sha256'] or
            projection_receipt.get('schema') != 'deepseek-low-p1-public-projection-receipt-v1' or
            projection_receipt.get('projection_sha256') != sha(root / PROJECTION) or
            projection_receipt.get('parent_audit_sha256') != sha(root / AUDIT) or
            projection_receipt.get('suffix_closure_sha256') != sha(root / CLOSURE) or
            projection_receipt.get('parent_private_attempts_sha256') !=
                projection['parent_private_attempts_sha256'] or
            projection_receipt.get('suffix_private_attempts_sha256') !=
                projection['suffix_private_attempts_sha256'] or
            projection_receipt.get('reference_labels_sha256') != sha(root / LABELS) or
            projection_receipt.get('positions') != 60 or
            projection_receipt.get('verified_against_private_originals') is not True):
        raise ValueError('Low P1 closure or projection differs')
    for private, expected in ((PARENT_PRIVATE, projection['parent_private_attempts_sha256']),
                              (TAIL_PRIVATE, projection['suffix_private_attempts_sha256'])):
        if (root / private).exists() and sha(root / private) != expected:
            raise ValueError('Private low P1 attempts changed')
    positions = projection['positions']
    if ([row['id'] for row in positions] != IDS or
            [row['status'] for row in positions] !=
                ['ok'] * 5 + ['invalid_output'] + ['ok'] * 20 + ['service_error'] +
                ['ok'] * 2 + ['invalid_output'] + ['ok'] * 30):
        raise ValueError('Low P1 composite outcomes differ')
    known = sum((Decimal(row['known_cost_usd']) for row in positions
                 if row['known_cost_usd'] is not None), Decimal())
    if (known != Decimal(audit['known_settled_usd']) +
                 Decimal(closure['suffix_known_cost_usd']) or
            Decimal(positions[26]['unknown_upper_bound_usd']) != Decimal('0.06905856')):
        raise ValueError('Low P1 projected costs differ')
    label_rows = rows(root / LABELS)
    if [row['id'] for row in label_rows] != IDS or any(row['review_version'] != '0.2' for row in label_rows):
        raise ValueError('Frozen low P1 reference labels differ')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    valid_rows = [row for row in positions if row['status'] == 'ok']
    all_four = sum(all(row['prediction'][field] == labels[row['id']][field]
                       for field in FIELDS) for row in valid_rows)
    fields = {field: sum(row['prediction'][field] == labels[row['id']][field]
                         for row in valid_rows) for field in FIELDS}
    if (projection_receipt.get('status_counts') != dict(Counter(row['status'] for row in positions)) or
            projection_receipt.get('valid_count') != len(valid_rows) or
            projection_receipt.get('all_four_correct') != all_four or
            projection_receipt.get('field_correct') != fields or
            projection_receipt.get('known_development_cost_usd') != str(known) or
            projection_receipt.get('unknown_cost_upper_bound_usd') !=
                closed['unknown_upper_bound_usd']):
        raise ValueError('Low P1 projection receipt counts or score differ')
    return {'schema': 'deepseek-low-p1-successor-findings-v1',
        'configurationId': projection['configuration_id'],
        'stage': 'fresh2/P1',
        'status': 'interrupted_composite_closed',
        'plannedRecords': 60,
        'valid': len(valid_rows),
        'outcomes': dict(Counter(row['status'] for row in positions)),
        'allFourCorrect': all_four,
        'fieldCorrect': fields,
        'knownDevelopmentCostUsd': str(known),
        'unknownCostUpperBoundUsd': closed['unknown_upper_bound_usd'],
        'invalidIds': ['DEV-006', 'DEV-030'],
        'providerFailureIds': ['DEV-027'],
        'cleanFullPhase': False,
        'fullCleanScore': None,
        'referenceStatus': 'Frozen v0.2 provisional labels, owner checked 2026-10-02; '
            'no independent adjudication recorded.',
        'interpretation': 'DEV-001–027 came from the stopped parent. DEV-028–060 '
            'were sent once in the successor. DEV-006 and DEV-030 were intrinsic '
            'length failures; DEV-027 was a provider failure with unknown actual charge.',
        'sourceBindings': list(bindings.values()),
        'privateRawVerificationLimit': projection['verification_limit']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('project', 'seal-projection', 'build', 'check'))
    args = parser.parse_args()
    if args.action == 'project':
        print(prepare_projection())
    elif args.action == 'seal-projection':
        print(seal_projection())
    elif args.action == 'build':
        value = build()
        target = ROOT / OUTPUT
        target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        print(sha(target))
    else:
        if json.loads((ROOT / OUTPUT).read_text()) != build():
            raise ValueError('Published low P1 findings differ')
        print(sha(ROOT / OUTPUT))


if __name__ == '__main__':
    main()
