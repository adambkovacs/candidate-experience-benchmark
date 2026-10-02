#!/usr/bin/env python3
"""Build separately reviewed Gemma26 fresh3 P0/P1 checkpoints offline."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

import build_gemma26_continuation_findings as first
import build_gemma26_second_continuation_findings as second
import build_gemma26_postabort_findings as postabort
import build_gemma26_p2_repeat_findings as p2
import gemma26_fresh3_p0_p1_composite_successor_v1 as successor
import gemma26_on_fresh_repeat_execution_v2 as frozen
import gemma26_on_fresh_repeat_study_v2 as study
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/gemma26-on-fresh-matched3-v2')
CHECKPOINT = BASE / 'fresh3-checkpoint-v1'
SCHEMA = 'gemma26-on-v2-fresh3-checkpoint-v1'
IDS = [f'DEV-{n:03d}' for n in range(1, 61)]
FIELDS = p2.FIELDS
LABELS = first.LABELS
FIRST_FEED = Path('public-site/gemma26-continuation-findings.json')
SECOND_FEED = Path('public-site/gemma26-second-continuation-findings.json')
POSTABORT_FEED = Path('public-site/gemma26-postabort-findings.json')
P2_FEED = Path('public-site/gemma26-p2-repeat-findings.json')
OUTPUTS = {'P0': Path('public-site/gemma26-fresh3-p0-checkpoint.json'),
           'P1': Path('public-site/gemma26-fresh3-p1-checkpoint.json')}
FIRST_P0 = BASE / 'fresh1/P0/development.attempts.jsonl'
SECOND_P0_PREFIX = BASE / 'interruption-continuation-v1/fresh2/P0/development.attempts.jsonl'
SECOND_P0_SUFFIX = BASE / 'second-interruption-continuation-v1/fresh2/P0/suffix.public-summary.json'
FIRST_P1 = BASE / 'fresh1/P1/development.attempts.jsonl'
SECOND_P1 = BASE / 'interruption-continuation-v1/fresh2/P1/development.attempts.jsonl'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return first.rows(path)


def bind(root, relative, bindings, expected=None):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or any(
            'ledger' in part.lower() for part in relative.parts):
        raise ValueError('Unsafe public source path')
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError('Missing checkpoint source: ' + relative.as_posix())
    digest = sha(path)
    if expected is not None and digest != expected:
        raise ValueError('Checkpoint source hash differs: ' + relative.as_posix())
    item = {'path': relative.as_posix(), 'sha256': digest}
    if item not in bindings:
        bindings.append(item)
    return path


def upstream(feed, relative):
    matches = [entry['sha256'] for entry in feed['sourceBindings']
               if entry['path'] == relative.as_posix()]
    if len(matches) != 1:
        raise ValueError('Prior feed lacks exact checkpoint source')
    return matches[0]


def projected_rows(root, condition, bindings):
    projection_rel = CHECKPOINT / condition / 'public-projection.json'
    review_rel = CHECKPOINT / condition / 'terminal-public-review.json'
    projection_path = bind(root, projection_rel, bindings)
    review_path = bind(root, review_rel, bindings)
    projection = json.loads(projection_path.read_text())
    review = json.loads(review_path.read_text())
    source = projection.get('privateSourceSha256')
    if (projection.get('schema') != SCHEMA + '-projection-v1' or
            projection.get('condition') != condition or
            projection.get('stage') != f'fresh3/{condition}/development' or
            projection.get('manualPrivacyReviewRequired') is not True or
            projection.get('planSha256') != sha(root / BASE / 'fresh3/manifest.json') or
            projection.get('admissionManifestSha256') !=
                sha(root / BASE / 'fresh3-p0-p1-composite-successor-v1/manifest.json') or
            not isinstance(source, dict) or
            set(source) != {'claim', 'review', 'journal', 'attempts', 'responses', 'wire'} or
            any(not isinstance(value, str) or len(value) != 64 or
                any(ch not in '0123456789abcdef' for ch in value)
                for value in source.values()) or
            review != {'schema': SCHEMA + '-terminal-public-review-v1',
                       'approved': True, 'condition': condition,
                       'terminalExitCode': 0, 'attemptedCount': 60,
                       'projectionSha256': sha(projection_path),
                       'privateSourceSha256': source,
                       'reviewer': review.get('reviewer')} or
            not isinstance(review.get('reviewer'), str) or
            not review['reviewer'].strip()):
        raise ValueError('Closed phase and manual projection review differ')
    saved = projection.get('responses')
    if (not isinstance(saved, list) or len(saved) != 60 or
            [item.get('id') for item in saved] != IDS):
        raise ValueError('Third-pass projection is not fixed 60')
    # Private bytes remain unavailable in a clean public checkout. If they are
    # present in the run checkout, still reject any changed source immediately.
    folder = root / BASE / 'fresh3' / condition
    for key, digest in source.items():
        private = root / BASE / 'fresh3-p0-p1-composite-successor-v1' / (
            f'fresh3-{condition.lower()}-development.root-review.json') if key == 'review' else folder / (
                            f'development.{key}.json' if key == 'claim'
                            else f'development.{key}.jsonl')
        if private.exists() and sha(private) != digest:
            raise ValueError('Reviewed private phase source changed: ' + key)
    return saved


def normalize(saved, requests):
    if len(saved) != 60 or [r.get('id') for r in saved] != IDS:
        raise ValueError('P0/P1 pass must cover ordered DEV-001–060')
    result = {}
    for row, request in zip(saved, requests):
        request_hash = row.get('requestSha256', row.get('request_sha256'))
        if request['record_id'] != row['id'] or request_hash != request['request_sha256']:
            raise ValueError('Checkpoint request identity differs')
        status = row.get('status')
        prediction = row.get('prediction')
        if status == 'ok' and valid(prediction):
            pass
        elif status == 'service_error' and prediction is None:
            pass
        else:
            raise ValueError('Unexpected checkpoint outcome')
        result[row['id']] = {'status': status, 'prediction': prediction}
    return result


def analyze(records, labels, published):
    scores = {}
    for name in p2.PASSES:
        items = [{'id': rid, **records[name][rid]} for rid in IDS]
        score = first.score(items, labels)
        if name in published and score != published[name]:
            raise ValueError('Prior published P0/P1 score differs')
        scores[name] = score
    failures = {name: [rid for rid in IDS if records[name][rid]['status'] != 'ok']
                for name in p2.PASSES}
    if failures['fresh2'] != (['DEV-002'] if published['condition'] == 'P0' else []):
        raise ValueError('Preserved second-pass failure differs')
    shared = [rid for rid in IDS if all(records[name][rid]['status'] == 'ok'
                                       for name in p2.PASSES)]
    pairs = [('fresh1', 'fresh2'), ('fresh2', 'fresh3'), ('fresh1', 'fresh3')]
    pairwise = [p2.paired(a, b, records, labels, shared) for a, b in pairs]
    available = [p2.paired(a, b, records, labels,
                           [rid for rid in IDS if records[a][rid]['status'] == 'ok'
                            and records[b][rid]['status'] == 'ok']) for a, b in pairs]
    score_range = {metric: {'min': min(values), 'max': max(values),
                            'spread': max(values) - min(values)}
                   for metric, values in {'allFour': [s['allFour'] for s in scores.values()],
                      **{field: [s['fields'][field] for s in scores.values()]
                         for field in FIELDS}}.items()}
    return {'fixed60Scores': scores, 'fixed60Ranges': score_range,
            'failureIdsByPass': failures,
            'allThreeSharedValid': {'denominator': len(shared),
                'excludedIds': [rid for rid in IDS if rid not in shared],
                'allFourMatches': {name: sum(p2.all_match(records[name][rid]['prediction'],
                    labels[rid]) for rid in shared) for name in p2.PASSES},
                'pairwise': pairwise},
            'pairwiseAvailableValid': available,
            'classBalanceAndConfusion': {name: p2.confusion(records, labels, name)
                                         for name in p2.PASSES}}


def build(root=ROOT, cutoff='P0'):
    root = Path(root).resolve()
    if cutoff not in OUTPUTS:
        raise ValueError('Unknown checkpoint cutoff')
    bindings = []
    first_feed = json.loads(bind(root, FIRST_FEED, bindings).read_text())
    second_feed = json.loads(bind(root, SECOND_FEED, bindings).read_text())
    post_feed = json.loads(bind(root, POSTABORT_FEED, bindings).read_text())
    p2_feed = json.loads(bind(root, P2_FEED, bindings).read_text())
    if (first_feed != first.build(root) or second_feed != second.build(root) or
            post_feed != postabort.build(root) or p2_feed != p2.build(root) or
            [first_feed.get('completedConditions'), second_feed.get('completedConditions'),
             post_feed.get('completedConditions'), p2_feed.get('scoredSeriesConditions')]
            != [5, 6, 7, 7]):
        raise ValueError('Frozen prior Gemma cutoff chain differs')
    bind(root, Path('scripts/build_gemma26_fresh3_checkpoint.py'), bindings)
    admission_path = bind(root, BASE / 'fresh3-p0-p1-composite-successor-v1/manifest.json', bindings)
    admission = json.loads(admission_path.read_text())
    if admission.get('schema') != successor.SCHEMA or admission.get('stages') != [
            'fresh3/P0/smoke', 'fresh3/P0/development',
            'fresh3/P1/smoke', 'fresh3/P1/development']:
        raise ValueError('Fresh3 admission manifest differs')
    reserve = Decimal(admission['per_request_reserve_usd'])
    labels_path = bind(root, LABELS, bindings, first.LABEL_SHA)
    label_rows = rows(labels_path)
    if [row.get('id') for row in label_rows] != IDS or any(
            row.get('review_version') != '0.2' or not valid(row.get('proposed_labels'))
            for row in label_rows):
        raise ValueError('Frozen provisional references differ')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    result = {}
    for condition in ('P0', 'P1') if cutoff == 'P1' else ('P0',):
        plans = {}
        for fresh in p2.PASSES:
            path = BASE / fresh / 'manifest.json'
            plans[fresh] = json.loads(bind(root, path, bindings).read_text())
        if condition == 'P0':
            original = rows(bind(root, FIRST_P0, bindings,
                                 upstream(first_feed, FIRST_P0)))
            prefix = rows(bind(root, SECOND_P0_PREFIX, bindings,
                               upstream(second_feed, SECOND_P0_PREFIX)))
            suffix = json.loads(bind(root, SECOND_P0_SUFFIX, bindings,
                                     upstream(second_feed, SECOND_P0_SUFFIX)).read_text())['responses']
            sources = (original, prefix + suffix)
            published = {'condition': condition,
                         'fresh1': first_feed['passes']['fresh1']['P0']['score'],
                         'fresh2': second_feed['compositeP0']['score']}
        else:
            sources = (rows(bind(root, FIRST_P1, bindings, upstream(first_feed, FIRST_P1))),
                       rows(bind(root, SECOND_P1, bindings, upstream(first_feed, SECOND_P1))))
            published = {'condition': condition,
                         'fresh1': first_feed['passes']['fresh1']['P1']['score'],
                         'fresh2': first_feed['passes']['fresh2']['P1']['score']}
        third = projected_rows(root, condition, bindings)
        for row, request in zip(third, plans['fresh3']['conditions'][condition]['development']):
            second.validate_public_row(row, request, reserve)
        records = {fresh: normalize(source, plans[fresh]['conditions'][condition]['development'])
                   for fresh, source in zip(p2.PASSES, (*sources, third))}
        result[condition] = {**analyze(records, labels, published),
                             'thirdPassUsage': postabort.composite_usage(third)}
    if cutoff == 'P1':
        p0_saved = json.loads(bind(root, OUTPUTS['P0'], bindings).read_text())
        if p0_saved != build(root, 'P0'):
            raise ValueError('Earlier P0 checkpoint differs')
    return {'schema': SCHEMA, 'configuration': post_feed['configuration'],
            'cutoff': cutoff, 'denominator': 60, 'plannedConditions': 9,
            'scoredSeriesConditions': 8 if cutoff == 'P0' else 9,
            'cleanMatchedThreeEligible': False,
            'referenceStatus': post_feed['referenceStatus'],
            'method': 'descriptive-interrupted-series-checkpoint',
            'conditions': result,
            'limitations': ['Fresh2/P0 retains its DEV-002 service error.',
                'Fresh1/P2 and fresh3/P2 retain their separately documented failures.',
                'Fixed-60 scores count failed positions as unavailable. Shared-valid comparisons use their stated smaller denominators.',
                'Client request duration is not pure inference time. Provider token fields may be missing or internally inconsistent.'],
            'sourceBindings': bindings}


def export_projection(condition):
    """Private run-host export, only after exact 60-request phase closure."""
    if condition not in OUTPUTS:
        raise ValueError('Unknown checkpoint condition')
    plan_path = study.BASE / 'fresh3/manifest.json'
    plan = study.verify('fresh3', sha(plan_path))
    successor.verify()
    closure = frozen.verify_phase_closure(plan, condition, 'development')
    folder, claim, journal, attempts_path = frozen.phase_paths('fresh3', condition,
                                                                'development')
    root_review = successor.BASE / f'fresh3-{condition.lower()}-development.root-review.json'
    frozen.review_receipt(root_review, 'fresh3',
                          condition, 'development', sha(plan_path))
    request_rows = plan['conditions'][condition]['development']
    attempts = frozen.jsonl(attempts_path)
    projected = []
    for record, request in zip(attempts, request_rows):
        classified = frozen.classify(record['raw_response'],
                                     record['model_catalog_entry'],
                                     record['provider_endpoint'])
        if (record['id'] != request['record_id'] or
                record['request_sha256'] != request['request_sha256'] or
                classified['status'] != 'ok' or
                classified['prediction'] != record['prediction'] or
                record.get('response_diagnostic', {}).get('passed') is not True):
            raise ValueError('Closed phase parser or request differs')
        projected.append(second.public_row(record))
    if len(projected) != 60:
        raise ValueError('Closed phase lacks 60 projections')
    private = {'claim': sha(claim), 'review': sha(root_review),
               'journal': closure['journal_sha256'],
               'attempts': closure['attempts_sha256'],
               'responses': closure['responses_sha256'],
               'wire': closure['wire_sha256']}
    value = {'schema': SCHEMA + '-projection-v1',
             'stage': f'fresh3/{condition}/development', 'condition': condition,
             'planSha256': sha(plan_path),
             'admissionManifestSha256': sha(successor.MANIFEST),
             'manualPrivacyReviewRequired': True,
             'privateSourceSha256': private, 'responses': projected}
    target = ROOT / CHECKPOINT / condition / 'public-projection.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'build'))
    parser.add_argument('--cutoff', choices=('P0', 'P1'), default='P0')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.action == 'export':
        if args.root.resolve() != ROOT:
            raise ValueError('Private export requires live repository root')
        print(export_projection(args.cutoff))
    else:
        target = args.root / OUTPUTS[args.cutoff]
        content = json.dumps(build(args.root, args.cutoff), indent=2,
                             ensure_ascii=False) + '\n'
        if args.check:
            if target.read_text() != content:
                raise ValueError('Published Gemma checkpoint differs')
        else:
            target.write_text(content)
        print('Gemma fresh3 checkpoint built: ' + args.cutoff)


if __name__ == '__main__':
    main()
