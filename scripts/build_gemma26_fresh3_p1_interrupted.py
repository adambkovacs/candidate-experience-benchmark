#!/usr/bin/env python3
"""Build a reviewed, descriptive Gemma fresh3/P1 checkpoint offline."""

import argparse
import base64
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path

import build_gemma26_fresh3_checkpoint as checkpoint
import build_gemma26_postabort_findings as postabort
import build_gemma26_second_continuation_findings as second
import gemma26_fresh3_p1_dev060_suffix_v1 as suffix
import gemma26_on_fresh_repeat_execution_v2 as frozen
from development_benchmark import valid
from openrouter_budget_v3 import BudgetLedger

ROOT = Path(__file__).resolve().parents[1]
BASE = checkpoint.BASE
PUBLIC = BASE / 'fresh3-p1-interrupted-checkpoint-v1'
PROJECTION = PUBLIC / 'public-projection.json'
REVIEW = PUBLIC / 'terminal-public-review.json'
OUTPUT = Path('public-site/gemma26-fresh3-p1-interrupted-checkpoint.json')
SUFFIX_RECONCILIATION = suffix.BASE.relative_to(ROOT) / 'reconciliation.json'
SCHEMA = 'gemma26-fresh3-p1-interrupted-checkpoint-v1'
IDS = checkpoint.IDS
PUBLIC_KEYS = postabort.PUBLIC_KEYS
TOKEN_KEYS = postabort.TOKEN_KEYS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def bind(root, relative, bindings):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or any(
            'ledger' in part.lower() for part in relative.parts):
        raise ValueError('Unsafe public source path')
    target = (root / relative).resolve()
    target.relative_to(root.resolve())
    if not target.is_file():
        raise ValueError('Missing P1 public source: ' + relative.as_posix())
    value = {'path': relative.as_posix(), 'sha256': sha(target)}
    if value not in bindings:
        bindings.append(value)
    return target


def failed_public_row(record, request):
    status = record.get('status')
    if (record.get('id') != request['record_id'] or
            record.get('request_sha256') != request['request_sha256'] or
            record.get('request') != request['payload'] or
            record.get('reference_labels_read') is not False or
            status not in ('service_error', 'invalid_output', 'prompt_admission_failure',
                           'control_violation', 'model_mismatch', 'provider_mismatch')):
        raise ValueError('Failed P1 attempt differs from frozen request')
    duration = record.get('elapsed_seconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError('Invalid failed P1 client duration')
    cost = record.get('observed_cost_usd')
    if cost is not None:
        amount = Decimal(str(cost))
        if not amount.is_finite() or not 0 <= amount <= suffix.RESERVE:
            raise ValueError('Invalid failed P1 observed cost')
        cost = str(amount)
    return {'id': record['id'], 'requestSha256': record['request_sha256'],
            'status': status, 'prediction': None, 'observedCostUsd': cost,
            'clientSeconds': duration, 'tokens': {key: None for key in TOKEN_KEYS}}


def private_suffix_gate():
    """Require one terminal DEV060 attempt and its separately sealed child."""
    manifest, manifest_sha = suffix.verify()
    suffix.prior_gate()
    paths = suffix.stage_paths()
    if not all(path.is_file() for path in paths.values()):
        raise ValueError('DEV060 terminal stage is not present')
    claim = json.loads(paths['claim'].read_text())
    events, attempts, responses, wire = (rows(paths[key]) for key in
                                        ('journal', 'attempts', 'responses', 'wire'))
    review_path = suffix.STAGE / 'suffix.root-review.json'
    review = json.loads(review_path.read_text())
    if review != suffix.expected_review(manifest, manifest_sha, suffix.BASE / 'budget.json',
                                        review.get('global_authority_head_sha256')):
        raise ValueError('DEV060 root stage review differs')
    if (claim.get('manifest_sha256') != manifest_sha or
            claim.get('review_sha256') != sha(review_path) or
            claim.get('ids') != ['DEV-060'] or
            [item.get('event') for item in events] !=
            ['phase_started', 'request_intent', 'request_started',
             'request_finished', events[-1].get('event')] or
            events[-1].get('event') not in ('phase_completed', 'phase_stopped') or
            [item.get('id') for item in attempts] != ['DEV-060'] or
            [item.get('id') for item in responses] not in ([], ['DEV-060']) or
            [item.get('id') for item in wire] not in ([], ['DEV-060'])):
        raise ValueError('DEV060 terminal lifecycle differs')
    attempt = attempts[0]
    request = manifest['request']
    if (attempt.get('id') != 'DEV-060' or
            attempt.get('request_sha256') != request['request_sha256'] or
            attempt.get('request') != request['payload'] or
            attempt.get('attempt_id') != events[2].get('attempt_id') or
            attempt.get('attempt_id') != events[3].get('attempt_id') or
            events[-1].get('event') != ('phase_completed' if frozen.continue_record(
                attempt, 'development') else 'phase_stopped')):
        raise ValueError('DEV060 terminal request or outcome differs')
    if attempt['status'] == 'ok':
        if (len(responses) != 1 or len(wire) != 1 or
                responses[0].get('attempt_id') != attempt['attempt_id'] or
                wire[0].get('attempt_id') != attempt['attempt_id'] or
                wire[0].get('http_status') != 200 or
                wire[0].get('read_error') is not None or
                wire[0].get('body_truncated_at_limit') is not False or
                json.loads(base64.b64decode(wire[0]['body_base64'], validate=True)) !=
                responses[0].get('raw_response') or
                responses[0].get('raw_response') != attempt.get('raw_response') or
                frozen.classify(attempt['raw_response'], attempt['model_catalog_entry'],
                                attempt['provider_endpoint'])['prediction'] != attempt.get('prediction') or
                attempt.get('response_diagnostic', {}).get('passed') is not True or
                Decimal(str(attempt['observed_cost_usd'])) !=
                Decimal(str(attempt['raw_response']['usage']['cost']))):
            raise ValueError('DEV060 raw response, parser or reported cost differs')
    elif attempt.get('status') == 'service_error':
        if (attempt.get('prediction') is not None or
                attempt.get('observed_cost_usd') is not None and
                Decimal(str(attempt['observed_cost_usd'])) > suffix.RESERVE):
            raise ValueError('DEV060 service error fields differ')
    elif attempt.get('status') not in ('invalid_output', 'prompt_admission_failure',
                                      'control_violation', 'model_mismatch',
                                      'provider_mismatch'):
        raise ValueError('Unexpected DEV060 terminal status')
    budget_path = suffix.BASE / 'budget.json'
    entry = suffix.budget_entry(budget_path)
    child_path = Path(entry['child_ledger'])
    if not child_path.is_file():
        raise ValueError('DEV060 child ledger missing')
    child = BudgetLedger(child_path, cap_limit=suffix.CAP)
    try:
        _, pending, blocked = child.state()
        reserves = [event for event in child.events if event.get('event') == 'reserve']
        settlements = [event for event in child.events if event.get('event') == 'settle']
        unknown = [event for event in child.events
                   if event.get('event') == 'unknown_cost_accounted_as_upper_bound']
        if (pending or blocked or not child.closed or len(reserves) != 1 or
                reserves[0].get('record_id') != 'DEV-060' or
                reserves[0].get('attempt_id') != attempt['attempt_id'] or
                Decimal(str(reserves[0]['usd'])) != suffix.RESERVE or
                len(settlements) + len(unknown) != 1):
            raise ValueError('DEV060 child settlement or seal missing')
        if attempt.get('cost_unknown') is True:
            if (len(unknown) != 1 or unknown[0].get('attempt_id') != attempt['attempt_id'] or
                    Decimal(str(unknown[0]['usd'])) != suffix.RESERVE or
                    unknown[0].get('evidence_sha256') != sha(paths['attempts'])):
                raise ValueError('DEV060 unknown-cost upper bound missing')
        elif (len(settlements) != 1 or settlements[0].get('attempt_id') != attempt['attempt_id'] or
              Decimal(str(settlements[0]['usd'])) != Decimal(str(attempt['observed_cost_usd']))):
            raise ValueError('DEV060 known cost settlement differs')
        accounted = child.accounted()
    finally:
        child.close()
    master = BudgetLedger(frozen.MASTER)
    try:
        _, pending, blocked = master.state()
        part = master.partitions.get(suffix.PARTITION_ID)
        reconciliations = [event for event in master.events
                           if event.get('event') == 'partition_reconciled' and
                           event.get('partition_id') == suffix.PARTITION_ID]
        if (pending or blocked or not part or part['active'] or len(reconciliations) != 1 or
                reconciliations[0].get('child_sha256') != sha(child_path) or
                Decimal(str(reconciliations[0]['known_actual_usd'])) +
                Decimal(str(reconciliations[0]['unknown_upper_bound_usd'])) != accounted):
            raise ValueError('DEV060 master reconciliation missing')
    finally:
        master.close()
    return attempt, {name: sha(path) for name, path in paths.items()}, \
        {'review': sha(review_path), 'budget': sha(budget_path),
         'child': sha(child_path)}


def export_projection():
    """Private export only; root must inspect the allowlist before publication."""
    suffix.prior_gate()
    manifest, _ = suffix.verify()
    plan, _ = suffix.selected_request()
    request_rows = plan['conditions']['P1']['development']
    original = rows(suffix.old_paths()['attempts'])
    last, suffix_hashes, suffix_other = private_suffix_gate()
    if len(original) != 59 or [row.get('id') for row in original] != IDS[:59]:
        raise ValueError('Original P1 prefix differs')
    projected = []
    for record, request in zip([*original, last], request_rows):
        if record['status'] == 'ok':
            row = second.public_row(record)
        else:
            row = failed_public_row(record, request)
        projected.append(row)
    if ([row['id'] for row in projected] != IDS or
            [row['id'] for row in projected if row['status'] != 'ok'][:1] != ['DEV-059']):
        raise ValueError('P1 projection does not account for fixed 60')
    value = {'schema': SCHEMA + '-projection-v1',
             'status': 'awaiting_manual_public_review',
             'condition': 'P1', 'stage': 'fresh3/P1/composite-development',
             'planSha256': manifest['plan_sha256'],
             'dev060ManifestSha256': sha(suffix.MANIFEST),
             'originalTerminalSha256': sha(suffix.TERMINAL),
             'originalRootReviewSha256': sha(suffix.TERMINAL_REVIEW),
             'originalReconciliationSha256': sha(suffix.OLD_RECONCILIATION),
             'manualPrivacyReviewRequired': True,
             'privateSourceSha256': {'original': suffix.prior_gate()['prefix_sha256'],
                                    'suffix': suffix_hashes, 'suffixOther': suffix_other},
             'responses': projected}
    target = ROOT / PROJECTION
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as file:
        json.dump(value, file, indent=2, ensure_ascii=False)
        file.write('\n')
        file.flush(); os.fsync(file.fileno())
    return target


def public_projection(root, bindings):
    path = bind(root, PROJECTION, bindings)
    review_path = bind(root, REVIEW, bindings)
    value = json.loads(path.read_text())
    review = json.loads(review_path.read_text())
    source = value.get('privateSourceSha256')
    if (value.get('schema') != SCHEMA + '-projection-v1' or
            value.get('condition') != 'P1' or
            value.get('stage') != 'fresh3/P1/composite-development' or
            value.get('manualPrivacyReviewRequired') is not True or
            value.get('planSha256') != sha(root / BASE / 'fresh3/manifest.json') or
            value.get('dev060ManifestSha256') != sha(root / suffix.MANIFEST.relative_to(ROOT)) or
            value.get('originalTerminalSha256') != sha(root / suffix.TERMINAL.relative_to(ROOT)) or
            value.get('originalRootReviewSha256') != sha(root / suffix.TERMINAL_REVIEW.relative_to(ROOT)) or
            value.get('originalReconciliationSha256') != sha(root / suffix.OLD_RECONCILIATION.relative_to(ROOT)) or
            not isinstance(source, dict) or set(source) != {'original', 'suffix', 'suffixOther'} or
            set(source['original']) != set(suffix.PREFIX_FILES) or
            set(source['suffix']) != set(suffix.PREFIX_FILES) or
            set(source['suffixOther']) != {'review', 'budget', 'child'} or
            any(not isinstance(item, str) or len(item) != 64 for group in source.values()
                for item in group.values()) or
            review != {'schema': SCHEMA + '-terminal-public-review-v1',
                       'approved': True, 'reviewer': 'root',
                       'terminalExitCode': 0, 'attemptedCount': 60,
                       'projectionSha256': sha(path),
                       'privateSourceSha256': source}):
        raise ValueError('P1 public projection or root privacy review differs')
    saved = value.get('responses')
    if not isinstance(saved, list) or len(saved) != 60 or [r.get('id') for r in saved] != IDS:
        raise ValueError('P1 projection lacks ordered fixed 60 rows')
    for key, relative in (('original', BASE / 'fresh3/P1'),
                          ('suffix', suffix.STAGE.relative_to(ROOT))):
        for name, expected in source[key].items():
            path_private = root / relative / (
                ('development.' if key == 'original' else 'suffix.') +
                ('claim.json' if name == 'claim' else name + '.jsonl'))
            if path_private.exists() and sha(path_private) != expected:
                raise ValueError('Reviewed private P1 source changed: ' + key + '/' + name)
    return saved


def normalize_third(saved, requests):
    if len(saved) != 60 or [row.get('id') for row in saved] != IDS:
        raise ValueError('P1 composite must retain all 60 positions')
    normalized = {}
    for row, request in zip(saved, requests):
        if (not isinstance(row, dict) or set(row) != PUBLIC_KEYS or
                row.get('requestSha256') != request['request_sha256'] or
                not isinstance(row.get('tokens'), dict) or
                set(row['tokens']) != set(TOKEN_KEYS) or
                type(row.get('clientSeconds')) not in (int, float) or
                not math.isfinite(row['clientSeconds']) or row['clientSeconds'] < 0):
            raise ValueError('P1 public row differs from frozen request')
        if row['status'] == 'ok':
            second.validate_public_row(row, request, suffix.RESERVE)
        elif (row['status'] not in ('service_error', 'invalid_output',
                                   'prompt_admission_failure', 'control_violation',
                                   'model_mismatch', 'provider_mismatch') or
              row['prediction'] is not None or
              any(value is not None for value in row['tokens'].values()) or
              row['id'] not in ('DEV-059', 'DEV-060')):
            raise ValueError('Unexpected P1 failed public row')
        else:
            cost = row['observedCostUsd']
            if cost is not None:
                amount = Decimal(str(cost))
                if not amount.is_finite() or not 0 <= amount <= suffix.RESERVE:
                    raise ValueError('P1 failed public cost differs')
        normalized[row['id']] = {'status': row['status'],
                                 'prediction': row['prediction']}
    if saved[58]['status'] != 'service_error':
        raise ValueError('Preserved DEV059 failure missing')
    if saved[58]['observedCostUsd'] is not None:
        raise ValueError('DEV059 unknown charge cannot become known in projection')
    return normalized


def build(root=ROOT):
    root = Path(root).resolve()
    bindings = []
    p0 = json.loads(bind(root, checkpoint.OUTPUTS['P0'], bindings).read_text())
    if p0 != checkpoint.build(root, 'P0'):
        raise ValueError('Frozen P0 checkpoint differs')
    first = json.loads(bind(root, checkpoint.FIRST_FEED, bindings).read_text())
    for relative in (BASE / 'fresh3/manifest.json',
                     suffix.MANIFEST.relative_to(ROOT),
                     suffix.TERMINAL.relative_to(ROOT),
                     suffix.TERMINAL_REVIEW.relative_to(ROOT),
                     suffix.OLD_RECONCILIATION.relative_to(ROOT),
                     Path('scripts/gemma26_fresh3_p1_dev060_suffix_v1.py'),
                     Path('scripts/build_gemma26_fresh3_p1_interrupted.py')):
        bind(root, relative, bindings)
    saved = public_projection(root, bindings)
    reconciliation = json.loads(bind(root, SUFFIX_RECONCILIATION, bindings).read_text())
    projection = json.loads((root / PROJECTION).read_text())
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != suffix.PARTITION_ID or
            reconciliation.get('child_sha256') !=
                projection['privateSourceSha256']['suffixOther']['child'] or
            Decimal(str(reconciliation.get('known_actual_usd'))) !=
                Decimal(str(saved[-1]['observedCostUsd'])) or
            Decimal(str(reconciliation.get('unknown_upper_bound_usd'))) != 0 or
            Decimal(str(reconciliation.get('unused_allocation_released_usd'))) +
                Decimal(str(reconciliation.get('known_actual_usd'))) != suffix.CAP):
        raise ValueError('DEV060 reconciliation differs from reviewed projection')
    plans = {name: json.loads(bind(root, BASE / name / 'manifest.json', bindings).read_text())
             for name in checkpoint.p2.PASSES}
    original = rows(bind(root, checkpoint.FIRST_P1, bindings))
    second_pass = rows(bind(root, checkpoint.SECOND_P1, bindings))
    labels = {row['id']: row['proposed_labels'] for row in
              rows(bind(root, checkpoint.LABELS, bindings))}
    if len(labels) != 60 or sha(root / checkpoint.LABELS) != checkpoint.first.LABEL_SHA:
        raise ValueError('Frozen provisional labels differ')
    records = {'fresh1': checkpoint.normalize(original,
                   plans['fresh1']['conditions']['P1']['development']),
               'fresh2': checkpoint.normalize(second_pass,
                   plans['fresh2']['conditions']['P1']['development']),
               'fresh3': normalize_third(saved,
                   plans['fresh3']['conditions']['P1']['development'])}
    published = {'condition': 'P1',
                 'fresh1': first['passes']['fresh1']['P1']['score'],
                 'fresh2': first['passes']['fresh2']['P1']['score']}
    analysis = checkpoint.analyze(records, labels, published)
    analysis['thirdPassUsage'] = postabort.composite_usage(saved)
    conditions = {'P0': p0['conditions']['P0'], 'P1': analysis}
    return {'schema': SCHEMA, 'configuration': p0['configuration'],
            'cutoff': 'P1_interrupted_after_DEV060', 'denominator': 60,
            'plannedConditions': 9, 'scoredSeriesConditions': 9,
            'cleanMatchedThreeEligible': False,
            'referenceStatus': p0['referenceStatus'],
            'method': 'descriptive-interrupted-series-checkpoint',
            'conditions': conditions,
            'limitations': [
                'Fresh3/P1 preserves the DEV059 unknown outcome and its full charge upper bound.',
                'Fixed-60 scores count failed positions as unavailable; shared-valid comparisons use their stated denominators.',
                'A score against provisional v0.2 labels is not adjudicated ground-truth accuracy.',
                'Provider-reported cost and tokens are not an independently verified invoice or pure inference time.'],
            'sourceBindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'build'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.action == 'export':
        if args.root.resolve() != ROOT:
            raise ValueError('Private export requires live repository root')
        print(export_projection())
        return
    target = args.root / OUTPUT
    content = json.dumps(build(args.root), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if target.read_text() != content:
            raise ValueError('Published P1 interrupted checkpoint differs')
    else:
        target.write_text(content)
    print('Gemma fresh3/P1 interrupted checkpoint built')


if __name__ == '__main__':
    main()
