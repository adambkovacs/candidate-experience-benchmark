#!/usr/bin/env python3
"""Reconcile the three Gemma 26B P2 passes from closed public evidence."""
import argparse
import hashlib
import json
from pathlib import Path

import build_gemma26_continuation_findings as first_report
import build_gemma26_second_continuation_findings as second_report
import build_gemma26_postabort_findings as third_report
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/gemma26-on-fresh-matched3-v2')
OUTPUT = Path('public-site/gemma26-p2-repeat-findings.json')
SCHEMA = 'gemma26-on-v2-p2-descriptive-repeat-findings-v1'
IDS = [f'DEV-{number:03d}' for number in range(1, 61)]
PASSES = ('fresh1', 'fresh2', 'fresh3')
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported',
          'testimonial_potential')
CHOICES = {
    'sentiment': ('positive', 'negative', 'mixed', 'neutral',
                  'insufficient_information'),
    'follow_up_needed': ('yes', 'no', 'insufficient_information'),
    'serious_concern_reported': ('yes', 'no', 'insufficient_information'),
    'testimonial_potential': ('yes', 'no', 'insufficient_information'),
}
FIRST_FEED = Path('public-site/gemma26-continuation-findings.json')
SECOND_FEED = Path('public-site/gemma26-second-continuation-findings.json')
THIRD_FEED = Path('public-site/gemma26-postabort-findings.json')
PREFIX = BASE / 'interruption-continuation-v1/public-prefix-v1/development.attempts.jsonl'
FIRST_SUFFIX = BASE / 'interruption-continuation-v1/fresh1/P2/suffix.attempts.jsonl'
SECOND_ATTEMPTS = BASE / 'interruption-continuation-v1/fresh2/P2/development.attempts.jsonl'
THIRD_PROJECTION = BASE / 'postabort-suffix-054-060-v1/public-composite-projection.json'
THIRD_REVIEW = BASE / 'postabort-suffix-054-060-v1/public-composite-review.json'
LABELS = Path('data/pilot/proposed_labels.jsonl')
SCHEMA_FILE = Path('schemas/judgments.schema.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(root, relative, bindings, upstream=()):
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe source path')
    target = (root / relative).resolve()
    target.relative_to(root.resolve())
    if not target.is_file():
        raise ValueError('Missing public evidence: ' + relative.as_posix())
    actual = digest(target)
    if upstream and not any(item.get('path') == relative.as_posix() and
                            item.get('sha256') == actual for item in upstream):
        raise ValueError('Prior public source binding differs: ' + relative.as_posix())
    bindings.append({'path': relative.as_posix(), 'sha256': actual})
    return target


def json_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def normalized(rows, requests, allow_projection=False):
    if len(rows) != 60 or [row.get('id') for row in rows] != IDS:
        raise ValueError('P2 pass must contain ordered DEV-001–060 once each')
    result = {}
    for row, request in zip(rows, requests):
        request_hash = row.get('requestSha256' if allow_projection else 'request_sha256')
        if (request.get('record_id') != row['id'] or
                request.get('request_sha256') != request_hash or
                (not allow_projection and row.get('reference_labels_read') is not False) or
                (allow_projection and 'reference_labels_read' in row)):
            raise ValueError('P2 request identity or blind inference changed')
        status = row.get('status')
        prediction = row.get('prediction')
        if status == 'ok':
            if not valid(prediction):
                raise ValueError('Claimed valid answer has invalid schema')
        elif status != 'service_error' or prediction is not None:
            raise ValueError('Unexpected P2 outcome')
        result[row['id']] = {'status': status, 'prediction': prediction}
    return result


def all_match(prediction, label):
    return all(prediction[field] == label[field] for field in FIELDS)


def paired(left, right, records, labels, ids):
    changed = []
    per_field = {field: {'changedIds': [], 'gainedMatchIds': [],
                         'lostMatchIds': []} for field in FIELDS}
    gained, lost = [], []
    for rid in ids:
        a, b = records[left][rid]['prediction'], records[right][rid]['prediction']
        if any(a[field] != b[field] for field in FIELDS):
            changed.append(rid)
        if not all_match(a, labels[rid]) and all_match(b, labels[rid]):
            gained.append(rid)
        if all_match(a, labels[rid]) and not all_match(b, labels[rid]):
            lost.append(rid)
        for field in FIELDS:
            if a[field] != b[field]:
                per_field[field]['changedIds'].append(rid)
            if a[field] != labels[rid][field] and b[field] == labels[rid][field]:
                per_field[field]['gainedMatchIds'].append(rid)
            if a[field] == labels[rid][field] and b[field] != labels[rid][field]:
                per_field[field]['lostMatchIds'].append(rid)
    return {'from': left, 'to': right, 'denominator': len(ids),
            'changedFourFieldVectorIds': changed,
            'changedFourFieldVectorCount': len(changed),
            'gainedAllFourMatchIds': gained, 'lostAllFourMatchIds': lost,
            'fields': per_field}


def confusion(records, labels, pass_name):
    output = {}
    for field in FIELDS:
        options = CHOICES[field]
        matrix = {truth: {prediction: 0 for prediction in (*options, 'unavailable')}
                  for truth in options}
        predicted = {value: 0 for value in options}
        reference = {value: 0 for value in options}
        for rid in IDS:
            truth = labels[rid][field]
            reference[truth] += 1
            row = records[pass_name][rid]
            answer = row['prediction'][field] if row['status'] == 'ok' else 'unavailable'
            matrix[truth][answer] += 1
            if answer != 'unavailable':
                predicted[answer] += 1
        output[field] = {'referenceClassBalance': reference,
                         'predictedClassBalanceValidOnly': predicted,
                         'unavailable': sum(matrix[truth]['unavailable'] for truth in options),
                         'confusion': matrix}
    return output


def analyze(records, labels, published_scores):
    scores = {}
    for pass_name in PASSES:
        rows = [{'id': rid, **records[pass_name][rid]} for rid in IDS]
        score = first_report.score(rows, labels)
        if score != published_scores[pass_name] or score['scoreKind'] != 'fixed_60':
            raise ValueError('P2 score differs from published fixed-60 evidence')
        scores[pass_name] = score
    failures = {name: [rid for rid in IDS if records[name][rid]['status'] != 'ok']
                for name in PASSES}
    if failures != {'fresh1': ['DEV-007'], 'fresh2': [],
                    'fresh3': ['DEV-005', 'DEV-006']}:
        raise ValueError('Preserved P2 service failures differ')
    common = [rid for rid in IDS if all(records[name][rid]['status'] == 'ok'
                                         for name in PASSES)]
    if len(common) != 57:
        raise ValueError('All-three shared-valid denominator differs')
    pairs = [(PASSES[0], PASSES[1]), (PASSES[1], PASSES[2]),
             (PASSES[0], PASSES[2])]
    paired_common = [paired(a, b, records, labels, common) for a, b in pairs]
    paired_available = [paired(a, b, records, labels,
                               [rid for rid in IDS if records[a][rid]['status'] == 'ok'
                                and records[b][rid]['status'] == 'ok']) for a, b in pairs]
    per_record = []
    for rid in common:
        distinct = {tuple(records[name][rid]['prediction'][field] for field in FIELDS)
                    for name in PASSES}
        if len(distinct) > 1:
            per_record.append({'id': rid, 'changedFields': [field for field in FIELDS
                               if len({records[name][rid]['prediction'][field]
                                       for name in PASSES}) > 1],
                               'allFourReferenceMatch': {name: all_match(
                                   records[name][rid]['prediction'], labels[rid])
                                   for name in PASSES}})
    dimensions = {'allFour': {name: scores[name]['allFour'] for name in PASSES}}
    dimensions.update({field: {name: scores[name]['fields'][field]
                               for name in PASSES} for field in FIELDS})
    ranges = {metric: {'min': min(values.values()), 'max': max(values.values()),
                       'spread': max(values.values()) - min(values.values())}
              for metric, values in dimensions.items()}
    return {'fixed60Scores': scores, 'fixed60Ranges': ranges,
            'failureIdsByPass': failures,
            'allThreeSharedValid': {'denominator': len(common),
                'excludedIds': [rid for rid in IDS if rid not in common],
                'allFourMatches': {name: sum(all_match(records[name][rid]['prediction'],
                    labels[rid]) for rid in common) for name in PASSES},
                'changedRecords': per_record,
                'pairwise': paired_common},
            'pairwiseAvailableValid': paired_available,
            'classBalanceAndConfusion': {name: confusion(records, labels, name)
                                         for name in PASSES}}


def build(root=ROOT):
    root = Path(root).resolve()
    bindings = []
    first_feed = json.loads(bound(root, FIRST_FEED, bindings).read_text())
    second_feed = json.loads(bound(root, SECOND_FEED, bindings).read_text())
    third_feed = json.loads(bound(root, THIRD_FEED, bindings).read_text())
    if (first_feed.get('schema') != first_report.SCHEMA or
            second_feed.get('schema') != second_report.SCHEMA or
            third_feed.get('schema') != third_report.SCHEMA or
            [first_feed.get('completedConditions'),
             second_feed.get('completedConditions'),
             third_feed.get('completedConditions')] != [5, 6, 7] or
            any(feed.get('cleanMatchedThreeEligible') is not False
                for feed in (first_feed, second_feed, third_feed))):
        raise ValueError('Public Gemma cutoff chain differs')
    for feed, expected in ((first_feed, first_report.build(root)),
                           (second_feed, second_report.build(root)),
                           (third_feed, third_report.build(root))):
        if feed != expected:
            raise ValueError('Published Gemma cutoff differs from closed evidence')
    prefix = json_rows(bound(root, PREFIX, bindings, first_feed['sourceBindings']))
    suffix = json_rows(bound(root, FIRST_SUFFIX, bindings, first_feed['sourceBindings']))
    second = json_rows(bound(root, SECOND_ATTEMPTS, bindings, first_feed['sourceBindings']))
    projection = json.loads(bound(root, THIRD_PROJECTION, bindings,
                                 third_feed['sourceBindings']).read_text())
    review = json.loads(bound(root, THIRD_REVIEW, bindings,
                             third_feed['sourceBindings']).read_text())
    if (projection.get('schema') != third_report.SCHEMA + '-projection-v1' or
            projection.get('status') != 'awaiting_manual_public_review' or
            review != {'schema': third_report.SCHEMA + '-public-review-v1',
                       'approved': True,
                       'projectionSha256': digest(root / THIRD_PROJECTION)}):
        raise ValueError('Third pass public projection lacks review')
    label_rows = json_rows(bound(root, LABELS, bindings, third_feed['sourceBindings']))
    if ([row.get('id') for row in label_rows] != IDS or
            any(row.get('review_version') != '0.2' or
                not valid(row.get('proposed_labels')) for row in label_rows)):
        raise ValueError('Frozen provisional labels differ')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    schema = json.loads(bound(root, SCHEMA_FILE, bindings).read_text())
    if any(tuple(schema['properties'][field]['enum']) != CHOICES[field]
           for field in FIELDS):
        raise ValueError('Judgment class vocabulary differs')
    records = {}
    for name, rows in (('fresh1', prefix + suffix), ('fresh2', second),
                       ('fresh3', projection['responses'])):
        plan_path = BASE / name / 'manifest.json'
        upstream = first_feed['sourceBindings'] if name != 'fresh3' else third_feed['sourceBindings']
        plan = json.loads(bound(root, plan_path, bindings, upstream).read_text())
        if plan.get('reference_labels_read') is not False:
            raise ValueError('Frozen plan was not blind')
        records[name] = normalized(rows, plan['conditions']['P2']['development'],
                                   allow_projection=name == 'fresh3')
    analysis = analyze(records, labels, {
        'fresh1': first_feed['passes']['fresh1']['P2']['score'],
        'fresh2': first_feed['passes']['fresh2']['P2']['score'],
        'fresh3': third_feed['fresh3P2']['score']})
    bound(root, Path('scripts/build_gemma26_p2_repeat_findings.py'), bindings)
    return {'schema': SCHEMA, 'configuration': third_feed['configuration'],
            'condition': 'P2', 'method': 'descriptive-interrupted-three-pass-comparison',
            'cleanMatchedThreeEligible': False, 'denominator': 60,
            'completedP2Passes': 3, 'scoredSeriesConditions': 7,
            'referenceStatus': third_feed['referenceStatus'],
            'timingKind': third_feed['timingKind'],
            **analysis, 'sourceBindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(build(args.root), indent=2, ensure_ascii=False) + '\n'
    target = args.root / args.output
    if args.check:
        if target.read_text() != content:
            raise ValueError('Published Gemma P2 comparison differs from bound evidence')
    else:
        target.write_text(content)
    print('Gemma 26B P2 descriptive comparison: three fixed-60 scores')


if __name__ == '__main__':
    main()
