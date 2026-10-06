#!/usr/bin/env python3
"""Build a descriptive DeepSeek low P2 result from a sealed 60-position projection."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-low-remaining6-price-v2')
SUCCESSOR = BASE / 'unsent-continuation-v1'
PROJECTION = SUCCESSOR / 'fresh2-p2-sanitized-projection-v1.json'
CORRECTION = SUCCESSOR / 'fresh2-p2-development-cost-correction.json'
AUDIT = SUCCESSOR / 'fresh2-p2-suffix-closure-audit.json'
PARENT_PLAN = BASE / 'execution-adapter-v1/fresh2/manifest.json'
SUFFIX_PLAN = SUCCESSOR / 'execution-adapter-v1/fresh2/manifest.json'
PARENT_ATTEMPTS = BASE / 'execution-adapter-v1/fresh2/P2/development.attempts.jsonl'
SUFFIX_ATTEMPTS = SUCCESSOR / 'execution-adapter-v1/fresh2/P2/development.attempts.jsonl'
LABELS = Path('data/pilot/proposed_labels.jsonl')
OUTPUT = Path('public-site/deepseek-low-remaining6-price-v2-findings.json')
IDS = [f'DEV-{i:03}' for i in range(1, 61)]
PROJECTION_SHA = '639d49c6e6b011c11d3497831164f9bd3cf51a4cc07e6fd4cd5a7126c4198c62'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete DeepSeek low JSONL source')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def relpath(path):
    return str(path)


def correction_and_audit(root):
    correction = json.loads((root / CORRECTION).read_text())
    audit = json.loads((root / AUDIT).read_text())
    if (correction.get('schema') != 'deepseek-low-fresh2-p2-cost-correction-v1' or
            correction.get('ledger_changed') is not False or
            correction.get('unknown_cost_ids') != ['DEV-005'] or
            correction.get('unknown_upper_bound_usd') != '0.06905856' or
            audit.get('schema') != 'deepseek-low-successor-fresh2-p2-closure-audit-v1' or
            audit.get('status') != 'suffix_closed_composite_interrupted' or
            audit.get('clean_full_phase') is not False or
            audit.get('full_60_clean_score') is not None or
            audit.get('composite_unknown_cost_ids') != ['DEV-005'] or
            audit.get('suffix_attempt_count') != 55 or audit.get('suffix_valid_count') != 55 or
            audit.get('suffix_known_actual_usd') != correction['suffix_development_known_usd'] or
            Decimal(correction['parent_development_known_usd']) +
                Decimal(correction['suffix_development_known_usd']) !=
                Decimal(correction['corrected_value_usd']) or
            Decimal(correction['original_value_usd']) -
                Decimal(correction['excluded_parent_smoke_usd']) !=
                Decimal(correction['corrected_value_usd'])):
        raise ValueError('Low descriptive closure or corrected cost differs')
    bound = {item['path']: item['sha256'] for item in correction['sources']}
    if (bound.get(str(PARENT_ATTEMPTS)) is None or
            bound.get(str(SUFFIX_ATTEMPTS)) !=
                audit['stage_evidence_sha256'][str(SUFFIX_ATTEMPTS)] or
            bound.get(str(AUDIT)) != sha(root / AUDIT)):
        raise ValueError('Low attempt source hashes differ')
    return correction, audit, bound


def prepare_projection(root=ROOT):
    """One-time review projection from private attempts; never overwrite it."""
    root = Path(root).resolve()
    correction, audit, bound = correction_and_audit(root)
    for name in (PARENT_ATTEMPTS, SUFFIX_ATTEMPTS):
        if sha(root / name) != bound[str(name)]:
            raise ValueError('Private attempt source changed: ' + str(name))
    parent = rows(root / PARENT_ATTEMPTS)
    suffix = rows(root / SUFFIX_ATTEMPTS)
    first = json.loads((root / PARENT_PLAN).read_text())['conditions']['P2']['development']
    second = json.loads((root / SUFFIX_PLAN).read_text())['conditions']['P2']['development']
    if ([r['id'] for r in parent] != IDS[:5] or
            [r['id'] for r in suffix] != IDS[5:] or
            [r['record_id'] for r in first] != IDS or
            [r['record_id'] for r in second] != IDS[5:] or
            audit['development_closure']['manifest_sha256'] != sha(root / SUFFIX_PLAN)):
        raise ValueError('Low parent/suffix membership or plan differs')
    projected = []
    for record, request in zip(parent + suffix, first[:5] + second):
        if (record.get('id') != request['record_id'] or
                record.get('request_sha256') != request['request_sha256'] or
                record.get('input_sha256') != request['input_sha256'] or
                record.get('instruction_sha256') != request['instruction_sha256'] or
                record.get('reference_labels_read') is not False or
                record.get('requested_model') != 'deepseek/deepseek-v4.1-flash' or
                record.get('reasoning_effort') != 'low'):
            raise ValueError('Low attempt differs from frozen request')
        if record['id'] == 'DEV-005':
            if (record.get('status') != 'service_error' or
                    record.get('cost_unknown') is not True or
                    record.get('reserved_cost_usd') != correction['unknown_upper_bound_usd']):
                raise ValueError('Original unknown DEV-005 differs')
            projected.append({'id': record['id'], 'status': 'service_error',
                              'prediction': None, 'known_cost_usd': None,
                              'unknown_upper_bound_usd': correction['unknown_upper_bound_usd']})
        else:
            if (record.get('status') != 'ok' or not valid(record.get('prediction')) or
                    record.get('billing_ok') is not True or
                    record.get('cost_unknown') is not False):
                raise ValueError('Known low response differs')
            projected.append({'id': record['id'], 'status': 'ok',
                              'prediction': record['prediction'],
                              'known_cost_usd': record['observed_cost_usd']})
    if (sum((Decimal(row['known_cost_usd']) for row in projected
             if row['known_cost_usd'] is not None), Decimal()) !=
            Decimal(correction['corrected_value_usd'])):
        raise ValueError('Projected development cost differs from correction')
    value = {'schema': 'deepseek-low-remaining6-price-v2-sanitized-projection-v1',
        'configuration_id': audit['configuration_id'], 'fresh_pass': 'fresh2',
        'condition': 'P2', 'clean_full_phase': False,
        'private_attempt_source_sha256': {str(name): bound[str(name)]
            for name in (PARENT_ATTEMPTS, SUFFIX_ATTEMPTS)},
        'parent_plan_sha256': sha(root / PARENT_PLAN),
        'suffix_plan_sha256': sha(root / SUFFIX_PLAN),
        'closure_audit_sha256': sha(root / AUDIT),
        'cost_correction_sha256': sha(root / CORRECTION),
        'positions': projected,
        'provenance_limit': 'Private attempts were checked when this projection was created. Earlier closure receipts bind raw responses; a clean checkout cannot independently decode the private bodies.'}
    path = root / PROJECTION
    with path.open('x') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write('\n')
    return sha(path)


def score(positions, labels):
    usable = [row for row in positions if row['status'] == 'ok']
    fields = {field: sum(row['prediction'][field] == labels[row['id']][field]
                         for row in usable) for field in KEYS}
    confusion = {field: {} for field in KEYS}
    classes = {field: Counter() for field in KEYS}
    for row in usable:
        for field in KEYS:
            truth, predicted = labels[row['id']][field], row['prediction'][field]
            confusion[field].setdefault(truth, Counter())[predicted] += 1
            classes[field][predicted] += 1
    return {'denominator': 60, 'valid': len(usable),
        'allFour': sum(all(row['prediction'][field] == labels[row['id']][field]
                           for field in KEYS) for row in usable),
        'fields': fields, 'outcomes': dict(Counter(row['status'] for row in positions)),
        'invalidIds': [row['id'] for row in positions if row['status'] != 'ok'],
        'confusionCounts': {field: {truth: dict(counts) for truth, counts in confusion[field].items()}
                            for field in KEYS},
        'predictedClassCounts': {field: dict(classes[field]) for field in KEYS}}


def build(root=ROOT):
    root = Path(root).resolve()
    correction, audit, bound = correction_and_audit(root)
    if sha(root / PROJECTION) != PROJECTION_SHA:
        raise ValueError('Frozen public projection changed')
    projection = json.loads((root / PROJECTION).read_text())
    if (projection.get('schema') != 'deepseek-low-remaining6-price-v2-sanitized-projection-v1' or
            projection.get('configuration_id') != audit['configuration_id'] or
            projection.get('clean_full_phase') is not False or
            projection.get('private_attempt_source_sha256') !=
                {str(name): bound[str(name)] for name in (PARENT_ATTEMPTS, SUFFIX_ATTEMPTS)} or
            projection.get('parent_plan_sha256') != sha(root / PARENT_PLAN) or
            projection.get('suffix_plan_sha256') != sha(root / SUFFIX_PLAN) or
            projection.get('closure_audit_sha256') != sha(root / AUDIT) or
            projection.get('cost_correction_sha256') != sha(root / CORRECTION)):
        raise ValueError('Projection provenance differs')
    positions = projection['positions']
    if ([row.get('id') for row in positions] != IDS or
            any(set(row) != {'id', 'status', 'prediction', 'known_cost_usd'}
                for row in positions if row['id'] != 'DEV-005') or
            positions[4] != {'id': 'DEV-005', 'status': 'service_error',
                              'prediction': None, 'known_cost_usd': None,
                              'unknown_upper_bound_usd': correction['unknown_upper_bound_usd']} or
            any(row['status'] != 'ok' or not valid(row['prediction']) or
                Decimal(row['known_cost_usd']) < 0
                for row in positions if row['id'] != 'DEV-005') or
            sum((Decimal(row['known_cost_usd']) for row in positions
                 if row['known_cost_usd'] is not None), Decimal()) !=
                Decimal(correction['corrected_value_usd'])):
        raise ValueError('Projection membership, prediction or cost differs')
    labels_raw = rows(root / LABELS)
    if ([row.get('id') for row in labels_raw] != IDS or
            any(row.get('review_version') != '0.2' or
                not valid(row.get('proposed_labels')) for row in labels_raw)):
        raise ValueError('Reference labels differ')
    labels = {row['id']: row['proposed_labels'] for row in labels_raw}
    result = score(positions, labels)
    if (result['valid'] != 59 or result['allFour'] != 57 or
            result['fields'] != {'sentiment': 59, 'follow_up_needed': 58,
                'serious_concern_reported': 57, 'testimonial_potential': 59} or
            result['outcomes'] != {'ok': 59, 'service_error': 1} or
            result['invalidIds'] != ['DEV-005']):
        raise ValueError('Source-bound low score differs from reviewed values')
    paths = (PROJECTION, CORRECTION, AUDIT, PARENT_PLAN, SUFFIX_PLAN, LABELS,
             Path('scripts/build_deepseek_low_remaining6_price_v2_findings.py'),
             Path('tests/test_build_deepseek_low_remaining6_price_v2_findings.py'),
             Path('scripts/development_benchmark.py'))
    return {'schema': 'deepseek-low-remaining6-price-v2-findings-v1',
        'series': [{'seriesId': audit['configuration_id'],
            'displayName': 'DeepSeek V4.1 Flash low, revised-price P2 continuation',
            'model': 'deepseek/deepseek-v4.1-flash', 'provider': 'OpenInference fp4',
            'effort': 'low', 'pass': 'fresh2', 'condition': 'P2',
            'method': 'descriptive_interrupted_phase_plus_closed_suffix',
            'cleanMatchedRepeatEligible': False,
            'score': result,
            'developmentKnownCostUsd': correction['corrected_value_usd'],
            'developmentUnknownCostUpperBoundUsd': correction['unknown_upper_bound_usd'],
            'predecessorUnknownCostId': 'DEV-005',
            'completedSuffixCount': 55,
            'limitations': ['The original DEV-005 provider failure has unknown cost and no usable prediction.',
                'The DEV-006–060 continuation was a separately funded, closed child. The combined 60 positions are descriptive, not a clean uninterrupted repeat.',
                'Private raw responses are not present in a clean checkout; the projection records hashes checked against the retained private attempts at creation.']}],
        'sourceBindings': [{'path': str(path), 'sha256': sha(root / path)} for path in paths],
        'privateAttemptSourceSha256': projection['private_attempt_source_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare-projection', 'build', 'verify'))
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    if args.action == 'prepare-projection':
        print(prepare_projection(args.root)); return
    data = json.dumps(build(args.root), indent=2, ensure_ascii=False) + '\n'
    if args.action == 'build':
        target = args.root / OUTPUT
        with target.open('x') as out: out.write(data)
        print(sha(target)); return
    if (args.root / OUTPUT).read_text() != data:
        raise ValueError('Published low findings differ from source-bound rebuild')
    print(sha(args.root / OUTPUT))


if __name__ == '__main__':
    main()
