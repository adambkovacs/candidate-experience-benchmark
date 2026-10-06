#!/usr/bin/env python3
"""Rebuild the public DeepSeek-low 60-position descriptive continuation."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

import build_additional_hosted_fresh_repeat_findings as scoring
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-low-fresh3-v2')
NEW = BASE / 'current-price-authority-v3-051-060/prompt-ceiling-v4'
PRIOR = Path('public-site/deepseek-low-third-interruption-findings.json')
PRIOR_SHA = 'd00e5100c085160e126956db8f4335a944859d6bf9b7a527cb84ebb7d2b9b60e'
PROJECTION = BASE / 'second-interruption-continuation-v1/phase-03-suffix.public.json'
PROJECTION_SHA = '8d2814c5c58f695f7741897fdbf7db2308e4344d5b95c8bfe5b25dbf283f5346'
CLOSURE_SHA = '988a75191e407db1de51b6fcb67898c0d6baae4994c2cd4e1dc3272883ecbfa3'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
SUFFIX = IDS[50:]


def bind(root, relative, expected, bindings):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Source path is not archive relative')
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'Source hash differs: {relative}')
    entry = {'path': str(relative), 'sha256': expected}
    if entry not in bindings:
        bindings.append(entry)
    return path


def jsonl(path):
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete source JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def build(root=ROOT):
    root = Path(root).resolve()
    sources = []
    old = json.loads(bind(root, PRIOR, PRIOR_SHA, sources).read_text())
    projection = json.loads(bind(root, PROJECTION, PROJECTION_SHA, sources).read_text())
    closure = json.loads(bind(root, NEW / 'closure.root-review.json', CLOSURE_SHA, sources).read_text())
    if (old.get('schema') != 'deepseek-low-third-interruption-findings-v1' or
            len(old.get('series', [])) != 1 or
            old['series'][0].get('thirdInterruptionCheckpoint', {}).get('outcomes') !=
            {'ok': 46, 'invalid_output': 1, 'service_error': 3, 'never_sent': 10} or
            projection.get('status_counts') !=
            {'ok': 46, 'invalid_output': 1, 'service_error': 3, 'never_sent': 10} or
            projection.get('denominator') != 60 or
            closure.get('schema') != 'deepseek-prompt-ceiling-v4-root-closure' or
            closure.get('completed') is not True or closure.get('ids') != SUFFIX or
            closure.get('raw_response_and_request_hashes_verified') is not True or
            closure.get('strict_predictions_verified') is not True):
        raise ValueError('Prior or final closure evidence differs')
    stage_hashes = closure.get('sources') or {}
    required = ('manifest.json', 'suffix.root-review.json', 'suffix.claim.json',
                'suffix.journal.jsonl', 'suffix.raw.jsonl', 'suffix.records.jsonl')
    if set(stage_hashes) != set(required):
        raise ValueError('Final closure source inventory differs')
    paths = {name: bind(root, NEW / name, stage_hashes[name], sources) for name in required}
    manifest = json.loads(paths['manifest.json'].read_text())
    claim = json.loads(paths['suffix.claim.json'].read_text())
    journal = jsonl(paths['suffix.journal.jsonl'])
    rows = jsonl(paths['suffix.records.jsonl'])
    if (manifest.get('schema') != 'deepseek-low-prompt-ceiling-v4' or
            manifest.get('method') != 'descriptive_continuation_not_clean_matched_three' or
            manifest.get('model') != 'deepseek/deepseek-v4.1-flash' or
            manifest.get('provider_tag') != 'open-inference/fp4' or
            manifest.get('reasoning_effort') != 'low' or manifest.get('ids') != SUFFIX or
            manifest.get('reference_labels_read') is not False or
            claim.get('manifest_sha256') != stage_hashes['manifest.json'] or
            claim.get('review_sha256') != stage_hashes['suffix.root-review.json'] or
            claim.get('ids') != SUFFIX or
            not journal or journal[-1] != {'event': 'stage_completed', 'count': 10} or
            [row.get('id') for row in rows] != SUFFIX or
            [request.get('id') for request in manifest.get('requests', [])] != SUFFIX):
        raise ValueError('Final suffix identity or completion differs')
    for row, request in zip(rows, manifest['requests']):
        if (row.get('status') != 'ok' or not valid(row.get('prediction')) or
                row.get('request_sha256') != request['request_sha256'] or
                row.get('input_sha256') != request['input_sha256'] or
                row.get('policy_sha256') != request['instruction_sha256'] or
                row.get('reference_labels_read') is not False or
                row.get('requested_model') != manifest['model'] or
                row.get('returned_model') != manifest['model'] or
                row.get('cost_unknown') is not False or row.get('billing_ok') is not True):
            raise ValueError('Final suffix request or prediction differs')
    previous = projection.get('positions')
    if (not isinstance(previous, list) or [row.get('id') for row in previous] != IDS or
            any(row != {'id': rid, 'status': 'never_sent'} for rid, row in zip(SUFFIX, previous[50:]))):
        raise ValueError('Prior 60-position projection differs')
    positions = previous[:50] + [{'id': row['id'], 'status': 'ok',
                                  'prediction': row['prediction'],
                                  'observed_cost_usd': row['observed_cost_usd'],
                                  'client_http_duration_seconds': row['client_http_duration_seconds'],
                                  'usage': {key: row.get('usage', {}).get(key)
                                            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens',
                                                        'completion_tokens_details')}}
                                 for row in rows]
    if (len(positions) != 60 or [row['id'] for row in positions] != IDS or
            dict(Counter(row['status'] for row in positions)) !=
            {'ok': 56, 'invalid_output': 1, 'service_error': 3}):
        raise ValueError('Final 60-position denominator differs')
    labels_path = bind(root, scoring.LABELS, scoring.LABEL_SHA, sources)
    label_rows = jsonl(labels_path)
    if [row.get('id') for row in label_rows] != IDS:
        raise ValueError('Reference membership differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    score = scoring.score(positions, labels, IDS)
    if score['valid'] != 56 or score['invalidIds'] != ['DEV-039', 'DEV-040', 'DEV-049', 'DEV-050']:
        raise ValueError('Final scored denominator differs')
    previous_series = old['series'][0]
    passes = previous_series['passes']['fresh1']
    comparisons = []
    for condition in ('P0', 'P1'):
        archived = passes[condition]
        item = archived['evidence']['records']
        baseline = jsonl(bind(root, item['path'], item['sha256'], sources))
        if [row.get('id') for row in baseline] != IDS:
            raise ValueError('Paired baseline membership differs')
        if scoring.score(baseline, labels, IDS) != archived['score']:
            raise ValueError('Paired baseline score differs from public history')
        flips = scoring.flip(baseline, positions, IDS)
        comparisons.append({'from': condition, 'to': 'P2',
                            'fixedDenominator': 60,
                            'allFourDifference': score['allFour'] - archived['score']['allFour'],
                            'fieldDifferences': {key: score['fields'][key] - archived['score']['fields'][key]
                                                 for key in KEYS},
                            'sharedValidChanges': flips})
    p0, p1 = (passes[c]['score'] for c in ('P0', 'P1'))
    comparisons.insert(0, {'from': 'P0', 'to': 'P1', 'fixedDenominator': 60,
                           'allFourDifference': p1['allFour'] - p0['allFour'],
                           'fieldDifferences': {key: p1['fields'][key] - p0['fields'][key] for key in KEYS},
                           'sharedValidChanges': next(item for item in previous_series['withinPassPromptFlips']
                                                      if item['pass'] == 'fresh1' and item['to'] == 'P1')})
    token_keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    usage = {key: {'observedCount': sum(type((row.get('usage') or {}).get(key)) is int for row in positions),
                   'missingCount': sum(type((row.get('usage') or {}).get(key)) is not int for row in positions),
                   'observedSum': sum((row.get('usage') or {}).get(key, 0) or 0 for row in positions
                                      if type((row.get('usage') or {}).get(key)) is int)} for key in token_keys}
    reasoning = [((row.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens')
                 for row in positions]
    usage['reasoning_tokens'] = {
        'observedCount': sum(type(value) is int for value in reasoning),
        'missingCount': sum(type(value) is not int for value in reasoning),
        'observedSum': sum(value for value in reasoning if type(value) is int)}
    observed_costs = [Decimal(str(row['observed_cost_usd'])) for row in positions
                      if row.get('observed_cost_usd') is not None]
    durations = [row.get('client_http_duration_seconds') for row in positions]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
           for value in durations):
        raise ValueError('Client request timing differs')
    usage['observedCostUsd'] = str(sum(observed_costs, Decimal(0)))
    usage['observedCostCount'] = len(observed_costs)
    usage['unknownCostCount'] = 60 - len(observed_costs)
    usage['clientRequestSecondsTotal'] = sum(durations)
    usage['clientRequestTimingCount'] = len(durations)
    usage['timingKind'] = 'client_http_duration_not_provider_inference'
    if closure['score'] != scoring.score(rows, labels, SUFFIX):
        # Closure uses "valid" as its outcome label, whereas the public scorer uses "ok".
        normalized = dict(closure['score'])
        normalized['outcomes'] = {'ok': 10}
        if normalized != scoring.score(rows, labels, SUFFIX):
            raise ValueError('Reviewed final suffix score differs')
    return {'schema': 'deepseek-low-final-suffix-findings-v1',
            'series': [{'seriesId': previous_series['seriesId'],
                        'displayName': previous_series['displayName'],
                        'model': previous_series['model'], 'effort': 'low',
                        'provider': previous_series['provider'],
                        'method': 'descriptive_continuation_not_clean_matched_three',
                        'cleanMatchedThreeEligible': False, 'denominator': 60,
                        'referenceClassCounts': {key: dict(Counter(labels[rid][key]
                                                        for rid in IDS)) for key in KEYS},
                        'historicalFirstPass': {'P0': p0, 'P1': p1, 'P2': score},
                        'finalP2Outcomes': dict(Counter(row['status'] for row in positions)),
                        'finalSuffix': {'ids': SUFFIX, 'valid': 10, 'allFour': 10,
                                        'score': scoring.score(rows, labels, SUFFIX),
                                        'observedCostUsd': str(sum((Decimal(str(row['observed_cost_usd']))
                                                                    for row in rows), Decimal(0))),
                                        'tokens': {key: sum((row.get('usage') or {}).get(key, 0)
                                                            for row in rows) for key in token_keys},
                                        'clientRequestSecondsTotal': sum(
                                            row['client_http_duration_seconds'] for row in rows)},
                        'withinPassComparisons': comparisons,
                        'p2ObservedUsage': usage,
                        'remainingFullRepeatPhases': previous_series['missingPasses'][1:],
                        'limitations': ['P2 combines the original interrupted phase with three separate continuations; it is descriptive, not a clean matched repeat.',
                                        'The four nonvalid positions remain in the fixed 60-review denominator.',
                                        'Token sums include only fields present in the saved public projection and final suffix. Historical total and reasoning token fields were not projected.',
                                        'Three earlier service errors have unknown charges, excluded from observed cost totals.']}],
            'sourceBindings': sources,
            'publicVerificationLimit': 'The final DEV-051 to DEV-060 request and raw response evidence is tracked in the public repository at commit a002196e. Earlier private request and raw response history remains available only through public projections and source hashes.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(build(args.root), indent=2, ensure_ascii=False) + '\n'
    if args.output:
        if args.output.exists():
            raise SystemExit('Refusing to overwrite an existing public feed')
        args.output.write_text(result)
    else:
        print(result, end='')


if __name__ == '__main__':
    main()
