#!/usr/bin/env python3
"""Validate closed native Jev conditions and score them offline against development labels."""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
import statistics

from development_benchmark import ROOT, KEYS, read_rows, score, digest
from jev_benchmark import PRICE_MODEL, parse_response, reserve_cost, usage_cost
import jev_native_prompt_variants_v1 as native

DEFAULT_DIRECTORY = ROOT / 'results/jev-native-prompt-variants-v1'
GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def binding(path):
    path = Path(path)
    try:
        name = str(path.relative_to(ROOT))
    except ValueError:
        name = str(path)
    return {'file': name, 'sha256': native.sha_bytes(path.read_bytes())}


def nearest(values, share):
    return sorted(values)[math.ceil(share * len(values)) - 1]


def validate_phase(directory, variant, phase, manifest, manifest_sha):
    attempted_path = directory / f'{variant}-{phase}.jsonl'
    journal_path = directory / f'{variant}-{phase}.attempts.jsonl'
    attempted, events = lines(attempted_path), lines(journal_path)
    ids = list(native.SMOKE_IDS) if phase == 'smoke' else [f'DEV-{i:03}' for i in range(1, 61)]
    if [row.get('id') for row in attempted] != ids or len(events) != 2 * len(ids) + 1:
        raise ValueError(f'{variant} {phase} lacks exactly {len(ids)} ordered, closed requests')
    terminal = events[-1]
    if terminal != {'event': 'terminal', 'phase': phase, 'variant': variant,
                    'manifest_sha256': manifest_sha, 'status': 'complete', 'stop_reason': None,
                    'expected_requests': len(ids), 'finished_requests': len(ids)}:
        raise ValueError(f'{variant} {phase} has no matching complete terminal')
    input_rows = native.load_inputs()
    policy = native.load_policy()
    seen_attempts = set()
    for index, (row, ident) in enumerate(zip(attempted, ids)):
        original = input_rows[int(ident[4:]) - 1]
        exact_request = native.payload(original['feedback'], policy, variant)
        planned = manifest['requests'][variant][int(ident[4:]) - 1]
        request_sha = digest(json.dumps(exact_request, sort_keys=True))
        attempt_id = row.get('budget_attempt_id')
        if (row.get('status') not in ('ok', 'invalid_output') or row.get('phase') != phase or
                row.get('variant') != variant or row.get('manifest_sha256') != manifest_sha or
                row.get('requested_model') != PRICE_MODEL or row.get('returned_model') != PRICE_MODEL or
                row.get('request') != exact_request or row.get('request_sha256') != request_sha or
                request_sha != planned['request_sha256'] or
                row.get('reserved_cost_usd') != planned['reserve_usd'] or
                attempt_id in seen_attempts or not isinstance(attempt_id, str) or
                row.get('cost_unknown') is not False or
                row.get('provider_reported_inference_seconds') is not None):
            raise ValueError(f'{variant} {phase} request or response control differs: {ident}')
        seen_attempts.add(attempt_id)
        raw = row.get('raw_response')
        if not isinstance(raw, dict):
            raise ValueError(f'{variant} {phase} missing raw response: {ident}')
        try:
            parsed = parse_response(raw, PRICE_MODEL)
            expected_status = 'ok'
        except (ValueError, TypeError, KeyError, IndexError):
            parsed, expected_status = None, 'invalid_output'
        if parsed != row.get('prediction') or expected_status != row.get('status'):
            raise ValueError(f'{variant} {phase} raw response mismatch: {ident}')
        usage = raw.get('usage')
        if not isinstance(usage, dict) or row.get('usage') != usage or usage_cost(raw) is None:
            raise ValueError(f'{variant} {phase} lacks provider usage: {ident}')
        if (row.get('estimated_usage_cost_usd') != str(usage_cost(raw)) or
                row.get('reported_input_tokens') != usage.get('input_tokens') or
                row.get('reported_output_tokens') != usage.get('output_tokens') or
                row.get('reported_reasoning_tokens') != usage.get('reasoning_tokens')):
            raise ValueError(f'{variant} {phase} token or cost estimate mismatch: {ident}')
        duration, call = row.get('elapsed_seconds'), row.get('client_http_call_seconds')
        if (not isinstance(duration, (int, float)) or isinstance(duration, bool) or
                not math.isfinite(duration) or duration < 0 or
                not isinstance(call, (int, float)) or isinstance(call, bool) or
                not math.isfinite(call) or not 0 <= call <= duration):
            raise ValueError(f'{variant} {phase} invalid timing: {ident}')
        started, finished = events[2 * index:2 * index + 2]
        if (started != {'event': 'started', 'id': ident, 'attempt_id': attempt_id,
                        'request_sha256': request_sha, 'reserved_cost_usd': str(reserve_cost(exact_request))} or
                finished != {'event': 'finished', 'id': ident, 'attempt_id': attempt_id,
                             'status': row['status'], 'elapsed_seconds': duration}):
            raise ValueError(f'{variant} {phase} journal mismatch: {ident}')
    return attempted, [binding(attempted_path), binding(journal_path)]


def validate_baseline(manifest):
    rows = lines(native.BASELINE)
    inputs, policy = native.load_inputs(), native.load_policy()
    if [r.get('id') for r in rows] != [r['id'] for r in inputs]:
        raise ValueError('P0 record order differs from frozen inputs')
    for row, original, planned in zip(rows, inputs, manifest['requests']['P0']):
        request_sha = digest(json.dumps(native.payload(original['feedback'], policy, 'P0'), sort_keys=True))
        if (row.get('status') != 'ok' or row.get('request_sha256') != request_sha or
                request_sha != planned['request_sha256'] or row.get('returned_model') != PRICE_MODEL or
                parse_response(row.get('raw_response'), PRICE_MODEL) != row.get('prediction')):
            raise ValueError('P0 baseline differs from saved request or response: ' + original['id'])
    attempts = lines(ROOT / 'results/openjev/typesafe-development-v2.jsonl') + \
               lines(ROOT / 'results/openjev/typesafe-development-v2-continuation.jsonl')
    if (len(attempts) != 61 or sum(r.get('status') == 'ok' for r in attempts) != 60 or
            len([r for r in attempts if r.get('status') == 'service_error']) != 1 or
            [r.get('id') for r in attempts if r.get('status') == 'service_error'] != ['DEV-046']):
        raise ValueError('Raw P0 61-attempt history differs')
    successes = [r for r in attempts if r.get('status') == 'ok']
    if [r['id'] for r in successes] != [r['id'] for r in rows]:
        raise ValueError('Raw P0 success order differs from reconciled records')
    failure = next(r for r in attempts if r.get('status') == 'service_error')
    if failure.get('cost_unknown') is not True or not failure.get('reserved_cost_usd'):
        raise ValueError('P0 failed attempt lacks unknown-cost reservation')
    for selected, raw in zip(rows, successes):
        if any(selected.get(key) != raw.get(key) for key in
               ('request_sha256', 'budget_attempt_id', 'prediction', 'raw_response', 'usage')):
            raise ValueError('P0 reconciliation differs from successful raw attempt: ' + raw['id'])
        expected_time = raw['elapsed_seconds'] + (failure['elapsed_seconds'] if raw['id'] == 'DEV-046' else 0)
        if not math.isclose(selected['elapsed_seconds'], expected_time, abs_tol=1e-9):
            raise ValueError('P0 reconciled request time differs: ' + raw['id'])
    return rows, attempts


def metrics(refs, predictions, pairs):
    evaluated = score(refs, predictions, pairs)
    truth = {r['id']: r['proposed_labels'] for r in refs}
    all_four = sum(r.get('status') == 'ok' and r.get('prediction') == truth[r['id']]
                   for r in predictions)
    simple = {key: evaluated['metrics'][key]['correct'] for key in KEYS}
    return evaluated, {**simple, 'all_four': all_four}


def resource_summary(attempts, *, unknown_upper='0'):
    durations = [r['elapsed_seconds'] for r in attempts]
    input_tokens = [r.get('reported_input_tokens', (r.get('usage') or {}).get('input_tokens')) for r in attempts]
    output_tokens = [r.get('reported_output_tokens', (r.get('usage') or {}).get('output_tokens')) for r in attempts]
    known = [Decimal(str(r['estimated_usage_cost_usd'])) for r in attempts
             if r.get('estimated_usage_cost_usd') is not None]
    available = sum(isinstance(v, int) for v in input_tokens)
    return {
        'timing': {'totalSeconds': sum(durations), 'medianSeconds': statistics.median(durations),
                   'p95Seconds': nearest(durations, .95), 'kind': 'record', 'requests': len(attempts),
                   'complete': True, 'comparableHosted': True,
                   'providerInferenceSeconds': None,
                   'note': 'Client-observed request attempts, including network and local work. Provider inference duration unavailable; summed requests are not one inference.'},
        'tokens': {'input': sum(v for v in input_tokens if isinstance(v, int)),
                   'output': sum(v for v in output_tokens if isinstance(v, int)),
                   'cachedInput': None, 'cacheWrite': None, 'reasoning': None,
                   'reportedRequests': available, 'totalRequests': len(attempts),
                   'complete': available == len(attempts),
                   'note': 'Reported development input/output usage; missing failed-request usage is unknown.'},
        'cost': {'actualUsd': None, 'knownUsd': None, 'estimatedUsd': float(sum(known)),
                 'unknownUpperBoundUsd': unknown_upper,
                 'availability': 'partial' if unknown_upper != '0' else 'estimate_only',
                 'note': 'Input-token price estimate, not a provider billing receipt. Development only; smoke excluded.'},
    }


def comparison(before, after, refs, inputs):
    old = {r['id']: r.get('prediction') if r['status'] == 'ok' else None for r in before}
    new = {r['id']: r.get('prediction') if r['status'] == 'ok' else None for r in after}
    truth = {r['id']: r['proposed_labels'] for r in refs}
    feedback = {r['id']: r['feedback'] for r in inputs}
    changed = [ident for ident in old if old[ident] != new[ident]]
    transitions = {key: {} for key in KEYS}
    for ident in old:
        for key in KEYS:
            a, b = (old[ident] or {}).get(key, 'invalid_output'), (new[ident] or {}).get(key, 'invalid_output')
            if a != b:
                label = a + ' -> ' + b
                transitions[key][label] = transitions[key].get(label, 0) + 1
    return {'bothValid': sum(old[i] is not None and new[i] is not None for i in old), 'changedRecordCount': len(changed),
            'fieldTransitions': transitions,
            'allFourWrongToCorrect': [i for i in changed if old[i] != truth[i] and new[i] == truth[i]],
            'allFourCorrectToWrong': [i for i in changed if old[i] == truth[i] and new[i] != truth[i]],
            'cases': [{'id': i, 'from_state': 'valid' if old[i] is not None else 'invalid_output', 'to_state': 'valid' if new[i] is not None else 'invalid_output',
                       'from_prediction': old[i], 'to_prediction': new[i],
                       'reference': truth[i], 'feedback': feedback[i]} for i in changed]}


def build(directory=DEFAULT_DIRECTORY):
    directory = Path(directory)
    manifest_path = directory / 'input-only-manifest.json'
    manifest, manifest_sha = native.read_frozen_manifest(manifest_path)
    source = [binding(manifest_path), binding(native.BASELINE), binding(native.INPUTS), binding(native.POLICY)]
    source.extend(binding(ROOT / name) for name in ('scripts/jev_native_prompt_variants_v1.py', 'scripts/jev_benchmark.py', 'scripts/development_benchmark.py', 'scripts/build_jev_native_prompt_report_v1.py'))
    conditions = {}
    for variant in ('P1', 'P2'):
        review = directory / f'{variant}-plan-review.json'
        native.receipt(review, 'jev-native-plan-review-v1', manifest_sha, variant)
        smoke, smoke_sources = validate_phase(directory, variant, 'smoke', manifest, manifest_sha)
        inspection = directory / f'{variant}-smoke-inspection.json'
        native.receipt(inspection, 'jev-native-smoke-inspection-v1', manifest_sha,
                       variant, native.sha_bytes((directory / f'{variant}-smoke.jsonl').read_bytes()))
        development, dev_sources = validate_phase(directory, variant, 'development', manifest, manifest_sha)
        if {r['budget_attempt_id'] for r in smoke} & {r['budget_attempt_id'] for r in development}:
            raise ValueError('Smoke and development reuse a budget attempt ID: ' + variant)
        conditions[variant] = development
        source.extend([binding(review), *smoke_sources, binding(inspection), *dev_sources])
    p0, raw_p0 = validate_baseline(manifest)
    conditions['P0'] = p0
    source.extend([binding(ROOT / 'results/openjev/typesafe-development-v2.jsonl'),
                   binding(ROOT / 'results/openjev/typesafe-development-v2-continuation.jsonl')])
    refs_path, pairs_path = ROOT / 'data/pilot/proposed_labels.jsonl', ROOT / 'data/pilot/pairs.json'
    refs, pairs, inputs = read_rows(refs_path), json.loads(pairs_path.read_text()), native.load_inputs()
    if [r['id'] for r in refs] != [r['id'] for r in inputs]:
        raise ValueError('Offline references differ from development inputs')
    source.extend([binding(refs_path), binding(pairs_path)])
    evaluated, summary, public_runs, public_cases = {}, {}, [], []
    truth = {r['id']: r['proposed_labels'] for r in refs}
    feedback = {r['id']: r['feedback'] for r in inputs}
    for variant in ('P0', 'P1', 'P2'):
        predictions = conditions[variant]
        evaluated[variant], counts = metrics(refs, predictions, pairs)
        summary[variant] = {'valid': evaluated[variant]['valid_outputs'], **counts,
                            'pair_checks': evaluated[variant]['pair_checks'],
                            'serious_concerns': evaluated[variant]['serious_concerns']}
        ident = 'typesafe-jev113-v2' + ('' if variant == 'P0' else '--' + variant.lower())
        unknown = next(r['reserved_cost_usd'] for r in raw_p0 if r['status'] == 'service_error')
        resources = resource_summary(raw_p0 if variant == 'P0' else predictions,
                                     unknown_upper=unknown if variant == 'P0' else '0')
        public_runs.append({'id': ident, 'experimentId': 'typesafe-jev113-v2',
                            'protocolId': 'jev-native-choice-instruction-sensitivity-v1',
                            'parentBaselineId': None if variant == 'P0' else 'typesafe-jev113-v2',
                            'model': PRICE_MODEL, 'effort': 'not applicable', 'surface': 'TypeSafe API',
                            'condition': variant, 'complete': True, 'resultStatus': 'complete; observational native comparison',
                            'pairedEligible': False, 'records': 60, 'valid': summary[variant]['valid'],
                            'metrics': counts, **resources,
                            'evidenceUrl': GITHUB + ('results/openjev/typesafe-development-v2-reconciled.jsonl' if variant == 'P0'
                                                     else f'results/jev-native-prompt-variants-v1/{variant}-development.jsonl')})
        for row in predictions:
            ident_row = row['id']
            public_cases.append({'configuration': ident, 'id': ident_row, 'feedback': feedback[ident_row],
                                 'reference': truth[ident_row], 'prediction': row.get('prediction'), 'status': row['status'],
                                 'different_fields': [key for key in KEYS if row.get('prediction') is not None and row['prediction'][key] != truth[ident_row][key]]})
    pair = {'id': 'typesafe-jev113-v2', 'model': PRICE_MODEL, 'eligible': False,
            'conditions': {key: {k: v for k, v in summary[key].items() if k not in ('pair_checks', 'serious_concerns')}
                           for key in ('P0', 'P1', 'P2')},
            'comparisons': {'P0_to_P1': comparison(p0, conditions['P1'], refs, inputs),
                            'P0_to_P2': comparison(p0, conditions['P2'], refs, inputs),
                            'P1_to_P2': comparison(conditions['P1'], conditions['P2'], refs, inputs)},
            'sourceStatus': 'Hash-verified, observational native instruction comparison; historical P0',
            'evidenceUrl': GITHUB + 'results/jev-native-prompt-variants-v1/report.json'}
    return {'kind': 'jev-native-choice-instruction-report-v1', 'manifest_sha256': manifest_sha,
            'reference_status': 'AI-reviewed provisional; development only',
            'causal_claim_supported': False,
            'comparison_limit': 'Historical P0 and one pass per condition do not isolate time or stochastic effects.',
            'source_bindings': source, 'summary': summary,
            'public_runs': public_runs, 'public_cases': public_cases, 'public_pair': pair}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.directory)
    with args.output.open('x') as out:
        json.dump(result, out, indent=2, ensure_ascii=False)
        out.write('\n')


if __name__ == '__main__':
    main()
