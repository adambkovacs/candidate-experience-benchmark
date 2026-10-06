#!/usr/bin/env python3
"""Publish source-bound Clef native repeat findings from terminal evidence only."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
from decimal import Decimal
from itertools import combinations

import clef_native_preparation as prep


ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/clef-native-v1')
OUTPUT = Path('results/clef-native-v1/clef-closed-repeat-findings-public.json')
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
IDS = [f'DEV-{number:03d}' for number in range(1, 61)]
CELLS = tuple((f'fresh{repeat}', f'P{condition}')
              for repeat in (1, 2, 3) for condition in (0, 1, 2))
GRANTS = {
    'fresh1/P0': BASE / 'clef-full-p0-grant.json',
    'fresh1/P1': BASE / 'repeat-continuation-v1/remaining-grants/clef-fresh1-p1-development-grant.json',
    'fresh1/P2': BASE / 'cloudflare-budget-v1/fresh1-p2-development-grant.json',
    'fresh2/P0': BASE / 'repeat-continuation-v1/fresh2-p0-grants/clef-development-grant.json',
    'fresh2/P1': BASE / 'cloudflare-budget-v1/fresh2-p1-development-grant.json',
    'fresh2/P2': BASE / 'cloudflare-budget-v1/fresh2-p2-development-grant.json',
    'fresh3/P0': BASE / 'repeat-continuation-v1/remaining-grants/clef-fresh3-p0-development-grant.json',
    'fresh3/P1': BASE / 'cloudflare-budget-v1/fresh3-p1-development-grant.json',
    'fresh3/P2': BASE / 'cloudflare-budget-v1/fresh3-p2-development-grant.json',
}
CONTROLLERS = {
    'fresh1/P0': ('clef_native_full_p0.py', 'clef_native_full_p0.py'),
    'fresh1/P1': ('clef_native_remaining.py', 'clef_native_remaining.py'),
    'fresh1/P2': ('clef_native_remaining.py', 'clef_native_remaining_cloudflare_v1.py'),
    'fresh2/P0': ('clef_native_fresh2_p0.py', 'clef_native_fresh2_p0.py'),
    'fresh2/P1': ('clef_native_remaining.py', 'clef_native_remaining_cloudflare_v1.py'),
    'fresh2/P2': ('clef_native_remaining.py', 'clef_native_remaining_cloudflare_v1.py'),
    'fresh3/P0': ('clef_native_remaining.py', 'clef_native_remaining.py'),
    'fresh3/P1': ('clef_native_remaining.py', 'clef_native_remaining_cloudflare_v1.py'),
    'fresh3/P2': ('clef_native_remaining.py', 'clef_native_remaining_cloudflare_v1.py'),
}
SUFFIX = BASE / 'cloudflare-budget-v1/exact-unsent-v1/clef/fresh1/P2/development'
SUFFIX_GRANT = BASE / 'cloudflare-budget-v1/exact-unsent-v1/grant.json'
SUFFIX_PLAN = BASE / 'cloudflare-budget-v1/exact-unsent-v1/plan.json'
QUOTA = BASE / 'cloudflare-budget-v1/fresh3-p2-quota-interruption-public.json'
SNAPSHOT = BASE / 'cloudflare-budget-v1/authority-after-fresh3-p2-interruption.jsonl'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class Sources:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.hashes = {}

    def path(self, relative):
        relative = Path(relative)
        path = (self.root / relative).resolve()
        path.relative_to(self.root)
        raw = path.read_bytes()
        self.hashes[str(relative)] = digest(raw)
        return raw

    def json(self, relative):
        return json.loads(self.path(relative))

    def rows(self, relative):
        raw = self.path(relative)
        if not raw.endswith(b'\n') or not raw.splitlines():
            raise ValueError(f'Incomplete JSONL: {relative}')
        return [json.loads(line) for line in raw.splitlines()]


def checked_labels(sources):
    rows = sources.rows(LABELS)
    if (sources.hashes[str(LABELS)] != LABELS_SHA256 or
            len(rows) != 60 or [row.get('id') for row in rows] != IDS):
        raise ValueError('Frozen proposed label key changed')
    if any(row.get('review_status') != 'ai_reviewed_provisional' or
           row.get('reviewer_labels') is not None or
           set(row.get('proposed_labels', {})) != set(prep.VALUES) for row in rows):
        raise ValueError('Reference status or fields changed')
    return {row['id']: row['proposed_labels'] for row in rows}


def field_summaries(predictions, labels):
    result = {}
    for field, values in prep.VALUES.items():
        reference = {value: 0 for value in values}
        predicted = {value: 0 for value in values}
        confusion = {value: {choice: 0 for choice in values} for value in values}
        for rid, choice in predictions.items():
            truth, output = labels[rid][field], choice[field]
            if truth not in reference or output not in predicted:
                raise ValueError('Choice outside frozen native label vocabulary')
            reference[truth] += 1
            predicted[output] += 1
            confusion[truth][output] += 1
        result[field] = {'referenceBalanceAmongValid': reference,
                         'predictionBalance': predicted,
                         'confusion': confusion,
                         'matchedAmongValid': sum(confusion[value][value] for value in values)}
    return result


def compared_predictions(left, right):
    if sorted(left) != IDS or sorted(right) != IDS:
        raise ValueError('Only exact 60-record clean runs may be compared')
    per_field = {field: 0 for field in prep.VALUES}
    any_field = 0
    for rid in IDS:
        changed = False
        for field in prep.VALUES:
            if left[rid][field] != right[rid][field]:
                per_field[field] += 1
                changed = True
        any_field += changed
    return {'denominator': 60, 'anyFieldChanged': any_field,
            'perFieldChanged': per_field}


def compared_all_four(left, right, labels):
    if sorted(left) != IDS or sorted(right) != IDS:
        raise ValueError('Correctness changes require exact 60-record clean pairs')
    gained = [rid for rid in IDS if left[rid] != labels[rid] and right[rid] == labels[rid]]
    lost = [rid for rid in IDS if left[rid] == labels[rid] and right[rid] != labels[rid]]
    left_matches = sum(left[rid] == labels[rid] for rid in IDS)
    right_matches = sum(right[rid] == labels[rid] for rid in IDS)
    if right_matches - left_matches != len(gained) - len(lost):
        raise ValueError('Matched correctness transition arithmetic differs')
    return {'sharedValidDenominator': 60, 'excludedInvalidOrUnknownIds': [],
            'leftAllFour': left_matches, 'rightAllFour': right_matches,
            'becameAllFourCorrectIds': gained, 'lostAllFourCorrectIds': lost,
            'gainedAllFour': len(gained), 'lostAllFour': len(lost),
            'allFourDelta': right_matches - left_matches}


def audit_stage(sources, directory, *, condition, rows, policy, labels,
                ids=IDS, grant_path=None, controllers=None, grant_stage=None):
    claim = sources.json(directory / 'claim.json')
    completion = sources.json(directory / 'completion.json')
    budget_path = directory / 'budget.jsonl'
    shared_budget = directory == BASE / 'clef/fresh1/P0/development'
    if shared_budget:
        budget_path = BASE / 'development-budget.jsonl'
    budget = sources.rows(budget_path)
    reserves = ([row for row in budget[1:] if row.get('model') == 'clef']
                if shared_budget else budget[1:])
    journal = sources.rows(directory / 'journal.jsonl')
    raw = sources.rows(directory / 'raw.jsonl')
    records = sources.rows(directory / 'records.jsonl')
    for name, key in [('claim.json', 'claim_sha256'),
                      ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'),
                      ('records.jsonl', 'records_sha256')]:
        if completion.get(key) != sources.hashes[str(directory / name)]:
            raise ValueError(f'Terminal hash mismatch: {directory}/{name}')
    n = completion.get('attempted')
    if (claim.get('model') != 'clef' or claim.get('stage') != completion.get('stage') or
            completion.get('model') != 'clef' or
            completion.get('status') not in ('complete', 'stopped') or
            type(n) is not int or not 1 <= n <= len(ids) or
            len(raw) != n or len(records) != n or len(journal) != 3 * n or
            len(reserves) != n or budget[0].get('event') != 'budget' or
            completion.get('never_sent') != ids[n:] or
            sum(completion.get('counts', {}).values()) != n or
            set(completion.get('counts', {})) !=
            {'valid', 'invalid_output', 'service_error', 'unknown_outcome'}):
        raise ValueError(f'Incomplete or changed terminal stage: {directory}')
    if grant_path is not None:
        grant = sources.json(grant_path)
        if controllers is None:
            raise ValueError('Controller source bindings required')
        claim_controller = Path('scripts') / controllers[0]
        grant_controller = Path('scripts') / controllers[1]
        sources.path(claim_controller)
        sources.path(grant_controller)
        if (claim.get('grant_sha256') != sources.hashes[str(grant_path)] or
                grant.get('approved') is not True or
                grant.get('model') != 'clef' or
                grant.get('stage') != (grant_stage or completion['stage']) or
                claim.get('account_id_sha256') != grant.get('account_id_sha256') or
                claim.get('controller_sha256') != sources.hashes[str(claim_controller)] or
                grant.get('controller_sha256') != sources.hashes[str(grant_controller)]):
            raise ValueError(f'Grant or account binding changed: {directory}')
    expected_reserve = str(prep.reservation_usd('clef', 1))
    matches = 0
    predictions = {}
    input_tokens = output_tokens = 0
    status_counts = {key: 0 for key in ('valid', 'invalid_output', 'service_error', 'unknown_outcome')}
    for index, rid in enumerate(ids[:n]):
        record, raw_row = records[index], raw[index]
        reserved, started, finished = journal[index * 3:index * 3 + 3]
        held = reserves[index]
        request_hash = prep.sha(prep.canonical(
            prep.request_payload(rows[index]['feedback'], policy, 'clef', condition)))
        attempt = record.get('attempt_id')
        if (record.get('id') != rid or raw_row.get('id') != rid or
                record.get('request_sha256') != request_hash or
                raw_row.get('request_sha256') != request_hash or
                record.get('reference_labels_read') is not False or
                record.get('reservation_usd') != expected_reserve or
                record.get('charge_status') != 'unknown_reserved' or
                reserved.get('event') != 'reserved' or started.get('event') != 'started' or
                finished.get('event') != 'finished' or
                held.get('event') != 'reserve' or held.get('usd') != expected_reserve or
                reserved.get('usd') != expected_reserve or
                any(item.get('attempt_id') != attempt or item.get('id') != rid
                    for item in (raw_row, reserved, started, finished, held)) or
                reserved.get('request_sha256') != request_hash or
                finished.get('status') != record.get('status')):
            raise ValueError(f'Attempt identity, order or reservation changed: {directory}/{rid}')
        status = record['status']
        if status not in status_counts:
            raise ValueError('Unknown outcome type')
        status_counts[status] += 1
        response = base64.b64decode(raw_row['raw_response_base64'], validate=True)
        if raw_row.get('response_sha256') != prep.sha(response):
            raise ValueError('Raw response hash changed')
        if status == 'valid':
            envelope = json.loads(response)
            parsed = prep.parse_rest_response(envelope, 'clef')
            if (raw_row.get('http_status') != 200 or raw_row.get('error_type') is not None or
                    record.get('reason') is not None or parsed != record.get('parsed') or
                    parsed.get('actual_charge_usd') is not None):
                raise ValueError('Valid raw response differs from parsed record')
            matches += int(parsed['prediction'] == labels[rid])
            predictions[rid] = parsed['prediction']
            usage = parsed.get('usage')
            if (not isinstance(usage, dict) or
                    type(usage.get('input_tokens')) is not int or
                    type(usage.get('output_tokens')) is not int or
                    usage['input_tokens'] < 0 or usage['output_tokens'] < 0):
                raise ValueError('Missing exact provider token usage')
            input_tokens += usage['input_tokens']
            output_tokens += usage['output_tokens']
        elif status == 'unknown_outcome':
            if (raw_row.get('http_status') is not None or response or
                    record.get('parsed') is not None or record.get('reason') !=
                    'transport_outcome_unknown'):
                raise ValueError('Unknown attempt gained a model output')
        elif record.get('parsed') is not None:
            raise ValueError('Invalid or provider-failed attempt gained a prediction')
    if (status_counts != completion['counts'] or
            (completion['status'] == 'complete') != (n == len(ids))):
        raise ValueError('Terminal totals differ')
    return {'attempted': n, 'valid': status_counts['valid'],
            'invalidOutput': status_counts['invalid_output'],
            'serviceError': status_counts['service_error'],
            'unknownOutcome': status_counts['unknown_outcome'],
            'neverSent': len(ids) - n, 'matchedAllFour': matches,
            'fieldMetrics': field_summaries(predictions, labels),
            'inputTokensObserved': input_tokens,
            'outputTokensObserved': output_tokens,
            'inputTariffEstimateUsd': (str(Decimal(input_tokens) *
                prep.MODELS['clef']['input_usd_per_million'] / Decimal(1_000_000))
                if input_tokens else None),
            'reservationUpperBoundUsd': str(prep.reservation_usd('clef', n)),
            'completionSource': str(directory / 'completion.json'),
            '_predictions': predictions}


def build(root=ROOT):
    sources = Sources(root)
    for name in ('scripts/build_clef_closed_repeat_findings.py',
                 'tests/test_build_clef_closed_repeat_findings.py',
                 'scripts/clef_native_preparation.py'):
        copied = sources.path(name)
        if copied != (ROOT / name).read_bytes():
            raise ValueError('Executed reporter source differs from requested checkout')
    for path in prep.SOURCE_FILES:
        copied = sources.path(path)
        if path.suffix == '.py' and copied != (ROOT / path).read_bytes():
            raise ValueError('Executed prompt module differs from requested checkout')
    sources.path('docs/REFERENCE_REVIEW_V1.md')
    sources.path('docs/CLEF_FINDINGS_2026-10-02.md')
    sources.path('docs/CLEF_PROMPT_CORRECTNESS_TRANSITIONS_2026-10-07.md')
    sources.path(BASE / 'clef-billing-source.md')
    labels = checked_labels(sources)
    rows, policy = prep.inputs_and_policy(Path(root))
    if [row['id'] for row in rows] != IDS:
        raise ValueError('Development inputs changed')
    cells = []
    clean_predictions = {}
    for repeat, condition in CELLS:
        key = f'{repeat}/{condition}'
        directory = BASE / 'clef' / repeat / condition / 'development'
        audited = audit_stage(sources, directory, condition=condition,
                              rows=rows, policy=policy, labels=labels,
                              grant_path=GRANTS[key], controllers=CONTROLLERS[key])
        if key == 'fresh1/P2':
            suffix = audit_stage(sources, SUFFIX, condition=condition, rows=rows[1:],
                                 policy=policy, labels=labels, ids=IDS[1:],
                                 grant_path=SUFFIX_GRANT,
                                 controllers=('clef_native_remaining.py',
                                              'clef_native_p2_exact_unsent_v1.py'),
                                 grant_stage='clef/fresh1/P2/development-exact-unsent-v1')
            plan = sources.json(SUFFIX_PLAN)
            if (audited['attempted'] != 1 or audited['unknownOutcome'] != 1 or
                    suffix['attempted'] != 59 or suffix['valid'] != 59 or
                    suffix['neverSent'] != 0 or
                    [item['id'] for item in plan.get('requests', [])] != IDS[1:]):
                raise ValueError('Clef P2 composite boundary changed')
            audited = {'attempted': 60, 'valid': 59, 'invalidOutput': 0,
                       'serviceError': 0, 'unknownOutcome': 1, 'neverSent': 0,
                       'matchedAllFour': suffix['matchedAllFour'],
                       'fieldMetrics': suffix['fieldMetrics'],
                       'inputTokensObserved': suffix['inputTokensObserved'],
                       'outputTokensObserved': suffix['outputTokensObserved'],
                       'inputTariffEstimateUsd': suffix['inputTariffEstimateUsd'],
                       'reservationUpperBoundUsd': str(
                           prep.reservation_usd('clef', 60)),
                       'completionSource': str(directory / 'completion.json'),
                       'suffixCompletionSource': str(SUFFIX / 'completion.json'),
                       '_predictions': suffix['_predictions']}
            status = 'interrupted_composite'
        elif key == 'fresh3/P2':
            quota = sources.json(QUOTA)
            sources.path(SNAPSHOT)
            quota_bindings = {
                'completion': directory / 'completion.json',
                'claim': directory / 'claim.json',
                'budget': directory / 'budget.jsonl',
                'journal': directory / 'journal.jsonl',
                'raw': directory / 'raw.jsonl',
                'records': directory / 'records.jsonl',
                'grant': GRANTS[key],
                'smoke_inspection': BASE / 'cloudflare-budget-v1/fresh3-p2-smoke-review.json',
                'authority_snapshot': SNAPSHOT,
            }
            for binding, path in quota_bindings.items():
                if quota.get('source_sha256', {}).get(binding) != digest(sources.path(path)):
                    raise ValueError(f'Quota projection binding changed: {binding}')
            if (quota.get('source_sha256', {}).get('completion') !=
                    sources.hashes[str(directory / 'completion.json')] or
                    quota.get('source_sha256', {}).get('authority_snapshot') !=
                    sources.hashes[str(SNAPSHOT)] or
                    quota.get('unknown_reserved_usd') != '0.015729' or
                    quota.get('never_sent_count') != 59 or
                    quota.get('provider_tool_error_code') != '4006' or
                    audited['attempted'] != 1 or audited['unknownOutcome'] != 1):
                raise ValueError('Quota interruption projection changed')
            status = 'interrupted_provider'
        else:
            if audited['valid'] != 60 or audited['neverSent'] != 0:
                raise ValueError('Expected complete clean Clef stage')
            status = 'complete'
        predictions = audited.pop('_predictions')
        if status == 'complete':
            clean_predictions[key] = predictions
        cells.append({'repeat': repeat, 'condition': condition, 'status': status,
                      **audited,
                      'agreementOf60': round(audited['matchedAllFour'] / 60, 6)
                          if status == 'complete' else None})
    repeat_flips = []
    for condition in ('P0', 'P1', 'P2'):
        repeats = [repeat for repeat in ('fresh1', 'fresh2', 'fresh3')
                   if f'{repeat}/{condition}' in clean_predictions]
        for left, right in combinations(repeats, 2):
            repeat_flips.append({'condition': condition, 'left': left, 'right': right,
                **compared_predictions(clean_predictions[f'{left}/{condition}'],
                                       clean_predictions[f'{right}/{condition}'])})
    prompt_differences = []
    prompt_exclusions = []
    by_cell = {(cell['repeat'], cell['condition']): cell for cell in cells}
    for repeat in ('fresh1', 'fresh2', 'fresh3'):
        for left, right in combinations(('P0', 'P1', 'P2'), 2):
            left_key, right_key = f'{repeat}/{left}', f'{repeat}/{right}'
            if left_key not in clean_predictions or right_key not in clean_predictions:
                prompt_exclusions.append({'repeat': repeat, 'left': left, 'right': right,
                    'comparisonDenominator': None,
                    'reason': 'At least one run lacks 60 valid answers; no clean paired prompt comparison.',
                    'runOutcomes': {condition: {
                        'status': by_cell[(repeat, condition)]['status'],
                        'valid': by_cell[(repeat, condition)]['valid'],
                        'invalidOutput': by_cell[(repeat, condition)]['invalidOutput'],
                        'serviceError': by_cell[(repeat, condition)]['serviceError'],
                        'unknownOutcome': by_cell[(repeat, condition)]['unknownOutcome'],
                        'neverSent': by_cell[(repeat, condition)]['neverSent']}
                        for condition in (left, right)}})
                continue
            before, after = clean_predictions[left_key], clean_predictions[right_key]
            prompt_differences.append({'repeat': repeat, 'left': left, 'right': right,
                **compared_predictions(before, after),
                **compared_all_four(before, after, labels)})
    return {'kind': 'clef-closed-repeat-findings-public-v1',
            'model': 'clef', 'declaredCells': 9, 'completeCleanCells': 7,
            'interruptedCells': 2, 'referenceStatus':
                'Frozen provisional v0.2 key; the owner confirmed human checks of all 60 reviews on 2026-10-02. Scores measure agreement with that key.',
            'scoreMeaning': 'Exact four-label agreement with the frozen proposed key; interrupted cells have no clean 60-record score.',
            'costMeaning': 'Input-token tariff estimate covers only saved valid responses; unknown attempts retain a separate full-context reservation. Neither figure is a provider invoice or verified charge.',
            'sourceLinks': {
                'referenceKey': 'data/pilot/proposed_labels.jsonl',
                'referenceReview': 'docs/REFERENCE_REVIEW_V1.md',
                'priorClefFindings': 'docs/CLEF_FINDINGS_2026-10-02.md',
                'promptCorrectnessTransitions': 'docs/CLEF_PROMPT_CORRECTNESS_TRANSITIONS_2026-10-07.md',
                'modelPricing': 'https://developers.cloudflare.com/workers-ai/models/clef/'},
            'cells': cells, 'cleanRepeatFlips': repeat_flips,
            'matchedPromptDifferences': prompt_differences,
            'promptComparisonExclusions': prompt_exclusions,
            'sourceBindings': sources.hashes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('write', 'check'))
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = json.dumps(build(args.root), sort_keys=True, indent=2) + '\n'
    target = args.root / OUTPUT
    if args.command == 'check':
        if target.read_text() != result:
            raise ValueError('Saved Clef repeat feed differs from source-bound terminal evidence')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result)
    print(digest(result.encode()))


if __name__ == '__main__':
    main()
