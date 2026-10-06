#!/usr/bin/env python3
"""Build an offline, source-bound report for closed Kev native P0 passes."""
import argparse
import base64
from collections import Counter
from decimal import Decimal
from datetime import datetime
import json
from pathlib import Path
import statistics

from development_benchmark import ROOT, KEYS, VALUES, read_rows, valid
from openrouter_paid_benchmark import LEDGER_PATH
import openrouter_decision_development as first
import openrouter_decision_repeats as repeats
import openrouter_decision_smoke as smoke
import openrouter_kev_interrupted_continuation as continuation

FIRST = first.BASE
REPEATS = repeats.BASE
TAIL = continuation.BASE
OUTPUT = ROOT / 'public-site/kev-native-repeats.json'
GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
THRESHOLDS = (0.5, 0.7, 0.9)
# Matches the independently pinned development reference in build_repeat_findings.py.
REFERENCE_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'


def binding(path, relative_path=None):
    path = Path(path)
    return {'path': str(relative_path if relative_path is not None else path.relative_to(ROOT)),
            'sha256': smoke.sha(path.read_bytes())}


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, int(fraction * len(ordered) + 0.999999) - 1)]


def summarize(manifest, directory, refs, ledger_path):
    directory = Path(directory)
    proof = repeats.inspect_finished(
        manifest, directory, ledger_path,
        first.validate_receipt if manifest['pass_id'] == first.PASS_ID else repeats.validate_receipt)
    events = [json.loads(line) for line in (directory / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    truth = {row['id']: row['proposed_labels'] for row in refs}
    confusion = {key: {label: Counter() for label in VALUES[key]} for key in KEYS}
    predicted = {key: Counter() for key in KEYS}
    reference = {key: Counter() for key in KEYS}
    confidence_bins = {key: {'0-<0.5': Counter(), '0.5-<0.7': Counter(),
                              '0.7-<0.9': Counter(), '0.9-1': Counter()} for key in KEYS}
    thresholds = {key: {str(t): {'covered': 0, 'correct': 0, 'wrong': 0} for t in THRESHOLDS} for key in KEYS}
    all_four = 0
    costs = Decimal(0)
    input_tokens = output_tokens = 0
    elapsed = []
    predictions = {}
    for index, item in enumerate(manifest['requests']):
        response, checked = events[3*index+1:3*index+3]
        ident = item['id']
        prediction = checked['prediction']
        if not valid(prediction) or ident not in truth:
            raise ValueError('Invalid scored prediction or reference: ' + ident)
        predictions[ident] = prediction
        all_four += prediction == truth[ident]
        body = response['body']
        costs += smoke.response_cost(body)
        input_tokens += body['usage']['input_tokens']
        output_tokens += body['usage']['output_tokens']
        elapsed.append(response['client_request_elapsed_ns'] / 1e9)
        for key in KEYS:
            actual, chosen = truth[ident][key], prediction[key]
            reference[key][actual] += 1
            predicted[key][chosen] += 1
            confusion[key][actual][chosen] += 1
            confidence = body['answers'][key]['confidence']
            if type(confidence) not in (int, float) or not 0 <= confidence <= 1:
                raise ValueError('Invalid native reported confidence: ' + ident + ':' + key)
            bin_name = ('0-<0.5' if confidence < .5 else '0.5-<0.7' if confidence < .7
                        else '0.7-<0.9' if confidence < .9 else '0.9-1')
            confidence_bins[key][bin_name]['correct' if chosen == actual else 'wrong'] += 1
            for threshold in THRESHOLDS:
                if confidence >= threshold:
                    bucket = thresholds[key][str(threshold)]
                    bucket['covered'] += 1
                    bucket['correct' if chosen == actual else 'wrong'] += 1
    if set(predictions) != set(truth):
        raise ValueError('Pass/reference IDs differ')
    if costs != Decimal(proof['predecessor_actual_cost_usd']):
        raise ValueError('Report/provider cost differs')
    source = [binding(directory / name) for name in
              ('manifest.json', 'root-review.json', 'attempts.jsonl', 'completion.json')]
    score = {'denominator': len(truth), 'valid': len(predictions), 'allFour': all_four,
             'fields': {key: sum(confusion[key][label][label] for label in VALUES[key]) for key in KEYS}}
    return {'passId': manifest['pass_id'], 'completionStatus': 'complete',
            'score': score, 'referenceClassCounts': {k: dict(reference[k]) for k in KEYS},
            'predictedClassCounts': {k: dict(predicted[k]) for k in KEYS},
            'confusionCounts': {k: {label: dict(confusion[k][label]) for label in VALUES[k]} for k in KEYS},
            'reportedConfidenceBins': {k: {b: dict(c) for b, c in confidence_bins[k].items()} for k in KEYS},
            'reportedConfidenceThresholds': thresholds,
            'usage': {'inputTokens': input_tokens, 'outputTokens': output_tokens,
                      'actualProviderCostUsd': str(costs),
                      'clientRequestSeconds': {'total': sum(elapsed), 'median': statistics.median(elapsed),
                                               'p95': percentile(elapsed, .95), 'kind': 'client_observed_request'}},
            'sourceBindings': source,
            'evidenceUrl': GITHUB + str((directory / 'completion.json').relative_to(ROOT)),
            '_predictions': predictions}



def interrupted(manifest, directory, ledger_path):
    """Describe a terminal transport interruption without scoring partial records."""
    directory = Path(directory)
    receipt = json.loads((directory / 'root-review.json').read_text())
    repeats.validate_receipt(receipt, manifest)
    attempts_path = directory / 'attempts.jsonl'
    rows = [json.loads(line) for line in attempts_path.read_text().splitlines() if line.strip()]
    if not rows or rows[-1].get('stage') != 'transport_error':
        raise ValueError('Incomplete Kev attempt lacks a terminal transport error')
    completed = (len(rows) - 2) // 3
    if len(rows) != 3 * completed + 2 or not 0 <= completed < 60:
        raise ValueError('Interrupted Kev journal shape differs')
    ledger = [json.loads(line) for line in Path(ledger_path).read_text().splitlines() if line.strip()]
    known = Decimal(0)
    input_tokens = output_tokens = elapsed_ns = 0
    bound = smoke.bound(first.ROUTE)
    for index in range(completed):
        reserved, response, checked = rows[index*3:index*3+3]
        item = manifest['requests'][index]
        ident, attempt_id = item['id'], reserved.get('ledger_attempt_id')
        if ([r.get('stage') for r in (reserved, response, checked)] != ['reserved', 'response', 'validated'] or
            not isinstance(attempt_id, str) or
            any(r.get('id') != ident for r in (reserved, response, checked)) or
            reserved.get('payload_sha256') != item['payload_sha256'] or
            response.get('attempt_id') != attempt_id or checked.get('attempt_id') != attempt_id or
            response.get('http_status') != 200 or response.get('cost_unknown') is not False or
            checked.get('cost_unknown') is not False):
            raise ValueError('Interrupted Kev validated prefix differs')
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        body = json.loads(raw)
        cost = smoke.response_cost(body)
        if (smoke.sha(raw) != response.get('raw_response_sha256') or
            len(raw) != response.get('raw_response_size_bytes') or body != response.get('body') or
            smoke.validate_response(body, first.ROUTE) != checked.get('prediction') or
            cost is None or cost != Decimal(response['actual_cost_usd']) or cost > bound):
            raise ValueError('Interrupted Kev raw response or cost differs')
        reserves = [e for e in ledger if e.get('event') == 'reserve' and e.get('attempt_id') == attempt_id]
        settles = [e for e in ledger if e.get('event') == 'settle' and e.get('attempt_id') == attempt_id]
        if (len(reserves) != 1 or len(settles) != 1 or
            reserves[0].get('record_id') != manifest['pass_id'] + ':' + ident or
            Decimal(str(reserves[0]['usd'])) != bound or Decimal(str(settles[0]['usd'])) != cost):
            raise ValueError('Interrupted Kev known settlement differs')
        known += cost
        input_tokens += body['usage']['input_tokens']
        output_tokens += body['usage']['output_tokens']
        if type(response.get('client_request_elapsed_ns')) is not int or response['client_request_elapsed_ns'] < 0:
            raise ValueError('Interrupted Kev known request timing differs')
        elapsed_ns += response['client_request_elapsed_ns']
    reserved, error = rows[-2:]
    item = manifest['requests'][completed]
    attempt_id = reserved.get('ledger_attempt_id')
    reserves = [e for e in ledger if e.get('event') == 'reserve' and e.get('attempt_id') == attempt_id]
    settles = [e for e in ledger if e.get('event') == 'settle' and e.get('attempt_id') == attempt_id]
    if (reserved.get('stage') != 'reserved' or reserved.get('id') != item['id'] or
        reserved.get('payload_sha256') != item['payload_sha256'] or
        error.get('id') != item['id'] or error.get('attempt_id') != attempt_id or
        error.get('cost_unknown') is not True or
        error.get('error_type') != 'TimeoutError' or
        type(error.get('client_request_elapsed_ns')) is not int or error['client_request_elapsed_ns'] < 0 or
        len(reserves) != 1 or settles or
        reserves[0].get('record_id') != manifest['pass_id'] + ':' + item['id'] or
        Decimal(str(reserves[0]['usd'])) != bound):
        raise ValueError('Interrupted Kev unknown reservation differs')
    audit_path = directory / 'interruption-audit.json'
    audit = json.loads(audit_path.read_text())
    accounted = [e for e in ledger if e.get('event') == 'unknown_cost_accounted_as_upper_bound'
                 and e.get('attempt_id') == attempt_id]
    if (audit.get('pass_id') != manifest['pass_id'] or
        audit.get('attempts_sha256') != smoke.sha(attempts_path.read_bytes()) or
        audit.get('valid_count') != completed or audit.get('attempted_count') != completed + 1 or
        audit.get('unknown_record_id') != item['id'] or audit.get('unknown_attempt_id') != attempt_id or
        audit.get('never_sent_ids') != [r['id'] for r in manifest['requests'][completed+1:]] or
        Decimal(audit.get('known_actual_cost_usd', '-1')) != known or
        Decimal(audit.get('unknown_upper_bound_usd', '-1')) != bound or
        audit.get('unknown_actual_cost_usd', 'non-null') is not None or
        audit.get('full_pass_complete') is not False or len(accounted) != 1 or
        Decimal(str(accounted[0].get('usd', '-1'))) != bound or
        accounted[0].get('actual_cost_usd', 'non-null') is not None or
        accounted[0].get('evidence_sha256') != audit['attempts_sha256']):
        raise ValueError('Interrupted Kev audit or unknown-cost accounting differs')
    return {'passId': manifest['pass_id'], 'completionStatus': 'interrupted',
            'outcomes': {'valid': completed, 'transportErrorUnknownOutcome': 1,
                         'neverSent': 60 - completed - 1},
            'outcomesAsOf': 'original-interruption',
            'stoppedAt': item['id'], 'errorType': 'TimeoutError',
            'knownActualProviderCostUsd': str(known),
            'unknownCostReservationUsd': str(bound),
            'unknownCostAccounting': 'full reservation retained as unknown-cost upper bound; actual charge unknown',
            'usage': {'inputTokens': input_tokens, 'outputTokens': output_tokens,
                      'actualProviderCostUsd': str(known),
                      'clientRequestSeconds': {'total': elapsed_ns / 1e9,
                                               'unknownAttempt': error['client_request_elapsed_ns'] / 1e9,
                                               'kind': 'client_observed_request'}},
            'score': None,
            'sourceBindings': [binding(directory / name,
                Path('results/route-audits/decision-kev-repeats-20260930/fresh3') / name) for name in
                               ('manifest.json', 'root-review.json', 'attempts.jsonl', 'interruption-audit.json')],
            'evidenceUrl': GITHUB + 'results/route-audits/decision-kev-repeats-20260930/fresh3/attempts.jsonl'}


def closed_continuation(original_manifest, original_dir, tail_dir, ledger_path, third):
    """Add the separately admitted never-sent tail without claiming a clean repeat."""
    original_dir, tail_dir = Path(original_dir), Path(tail_dir)
    proof = continuation.inspect_prefix(original_manifest, original_dir, ledger_path)
    manifest = json.loads((tail_dir / 'manifest.json').read_text())
    if manifest != continuation.build_manifest(original_manifest, proof):
        raise ValueError('Kev tail manifest or immutable prefix differs')
    continuation.validate_receipt(json.loads((tail_dir / 'root-review.json').read_text()), manifest)
    attempts_path = tail_dir / 'attempts.jsonl'
    raw_attempts = attempts_path.read_bytes()
    rows = [json.loads(line) for line in raw_attempts.decode().splitlines() if line.strip()]
    if len(rows) != 3 * continuation.COUNT:
        raise ValueError('Kev tail must contain exactly 34 validated triplets')
    ledger = [json.loads(line) for line in Path(ledger_path).read_text().splitlines() if line.strip()]
    reservations = [event for event in ledger if event.get('event') == 'reserve' and
                    str(event.get('record_id', '')).startswith(continuation.PASS_ID + ':')]
    expected_record_ids = [continuation.PASS_ID + ':' + item['id'] for item in manifest['requests']]
    if len(reservations) != continuation.COUNT or [event['record_id'] for event in reservations] != expected_record_ids:
        raise ValueError('Kev tail ledger membership differs')
    known = Decimal(0)
    input_tokens = output_tokens = elapsed_ns = 0
    seen_attempts = set()
    for index, item in enumerate(manifest['requests']):
        reserved, response, validated = rows[3*index:3*index+3]
        attempt_id = reserved.get('ledger_attempt_id')
        if (not isinstance(attempt_id, str) or not attempt_id or attempt_id in seen_attempts or
            [row.get('stage') for row in (reserved, response, validated)] != ['reserved', 'response', 'validated'] or
            any(row.get('id') != item['id'] for row in (reserved, response, validated)) or
            response.get('attempt_id') != attempt_id or validated.get('attempt_id') != attempt_id or
            reserved.get('payload_sha256') != item['payload_sha256'] or
            item['payload_sha256'] != smoke.sha(smoke.canonical(item['payload'])) or
            Decimal(str(reserved.get('reserved_cost_usd', '-1'))) != smoke.bound(first.ROUTE) or
            Decimal(str(response.get('reserved_cost_usd', '-1'))) != smoke.bound(first.ROUTE) or
            reserved.get('cost_unknown') is not True or response.get('cost_unknown') is not False or
            validated.get('cost_unknown') is not False or response.get('http_status') != 200 or
            response.get('parse_error_type') is not None or
            type(response.get('client_request_elapsed_ns')) is not int or
            response['client_request_elapsed_ns'] < 0 or
            not isinstance(response.get('request_start_utc'), str) or
            not isinstance(response.get('request_end_utc'), str)):
            raise ValueError('Kev tail order, payload or timing differs')
        seen_attempts.add(attempt_id)
        started = datetime.fromisoformat(response['request_start_utc'].replace('Z', '+00:00'))
        ended = datetime.fromisoformat(response['request_end_utc'].replace('Z', '+00:00'))
        if ended < started:
            raise ValueError('Kev tail end precedes start')
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        body = json.loads(raw)
        if (smoke.sha(raw) != response.get('raw_response_sha256') or
            len(raw) != response.get('raw_response_size_bytes') or body != response.get('body') or
            body.get('model') != first.ROUTE['version'] or body.get('provider') != first.ROUTE['provider'] or
            smoke.validate_response(body, first.ROUTE) != validated.get('prediction')):
            raise ValueError('Kev tail native raw response differs')
        cost = smoke.response_cost(body)
        if (cost is None or cost != Decimal(str(response.get('actual_cost_usd', '-1'))) or
            cost > smoke.bound(first.ROUTE)):
            raise ValueError('Kev tail provider cost differs')
        events = [event for event in ledger if event.get('attempt_id') == attempt_id]
        if ([event.get('event') for event in events] != ['reserve', 'settle'] or
            events[0] != reservations[index] or
            Decimal(str(events[0].get('usd', '-1'))) != smoke.bound(first.ROUTE) or
            Decimal(str(events[1].get('usd', '-1'))) != cost):
            raise ValueError('Kev tail ledger settlement differs')
        known += cost
        input_tokens += body['usage']['input_tokens']
        output_tokens += body['usage']['output_tokens']
        elapsed_ns += response['client_request_elapsed_ns']
    completion = json.loads((tail_dir / 'completion.json').read_text())
    if (completion.get('pass_id') != continuation.PASS_ID or
        completion.get('status') != 'interrupted_series_tail_closed_not_clean_third_pass' or
        completion.get('record_count') != continuation.COUNT or
        completion.get('tail_valid_count') != continuation.COUNT or
        completion.get('original_prefix_valid_count') != 25 or
        completion.get('original_unknown_record_id') != 'DEV-026' or
        completion.get('original_unknown_attempt_id') != proof['unknown_attempt_id'] or
        completion.get('original_unknown_actual_cost_usd', 'non-null') is not None or
        Decimal(str(completion.get('original_unknown_upper_bound_usd', '-1'))) != smoke.bound(first.ROUTE) or
        completion.get('combined_observed_valid_count') != 59 or
        completion.get('clean_full_third_pass_complete') is not False or
        completion.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
        completion.get('attempts_sha256') != smoke.sha(raw_attempts) or
        Decimal(str(completion.get('tail_known_actual_cost_usd', '-1'))) != known or
        completion.get('inference_performed') is not True or
        completion.get('reference_labels_read') is not False):
        raise ValueError('Kev tail completion differs from raw and ledger evidence')
    combined_cost = Decimal(third['knownActualProviderCostUsd']) + known
    combined_input = third['usage']['inputTokens'] + input_tokens
    combined_output = third['usage']['outputTokens'] + output_tokens
    prefix_rows = [json.loads(line) for line in (original_dir / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    combined_elapsed_ns = sum(row['client_request_elapsed_ns'] for row in prefix_rows
                              if row.get('stage') == 'response') + elapsed_ns
    reconciliation = json.loads((tail_dir / 'terminal-reconciliation.json').read_text())
    if (reconciliation.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
        reconciliation.get('attempts_sha256') != smoke.sha(raw_attempts) or
        reconciliation.get('completion_sha256') != smoke.sha((tail_dir / 'completion.json').read_bytes()) or
        reconciliation.get('unknown_accounting_event_sha256') != proof['unknown_accounting_event_sha256'] or
        reconciliation.get('combined_observed_valid_count') != 59 or
        reconciliation.get('original_unknown_actual_cost_usd', 'non-null') is not None or
        reconciliation.get('clean_full_third_pass_complete') is not False or
        Decimal(str(reconciliation.get('tail_known_actual_cost_usd', '-1'))) != known or
        Decimal(str(reconciliation.get('combined_known_actual_cost_usd', '-1'))) != combined_cost or
        reconciliation.get('combined_known_input_tokens') != combined_input or
        reconciliation.get('combined_known_output_tokens') != combined_output or
        reconciliation.get('combined_known_client_request_elapsed_ns') != combined_elapsed_ns):
        raise ValueError('Kev tail terminal reconciliation differs')
    third['outcomes'] = {'valid': 59, 'transportErrorUnknownOutcome': 1, 'neverSent': 0}
    third['outcomesAsOf'] = 'continuation-closure'
    third['continuationStatus'] = 'closed'
    third['knownActualProviderCostUsd'] = str(combined_cost)
    third['usage'] = {'inputTokens': combined_input, 'outputTokens': combined_output,
                      'actualProviderCostUsd': str(combined_cost),
                      'clientRequestSeconds': {'total': combined_elapsed_ns / 1e9,
                                               'unknownAttempt': third['usage']['clientRequestSeconds']['unknownAttempt'],
                                               'kind': 'client_observed_request'}}
    third['tail'] = {'passId': continuation.PASS_ID, 'valid': continuation.COUNT,
                     'usage': {'inputTokens': input_tokens, 'outputTokens': output_tokens,
                               'actualProviderCostUsd': str(known),
                               'clientRequestSeconds': {'total': elapsed_ns / 1e9,
                                                        'kind': 'client_observed_request'}}}
    names = ('manifest.json', 'root-review.json', 'attempts.jsonl', 'completion.json',
             'terminal-reconciliation.json')
    third['sourceBindings'] += [binding(tail_dir / name,
        Path('results/route-audits/kev-fresh3-continuation-20260930') / name) for name in names]
    third['evidenceUrl'] = GITHUB + 'results/route-audits/kev-fresh3-continuation-20260930/completion.json'
    return third

def build(first_base=FIRST, repeat_base=REPEATS, ledger_path=LEDGER_PATH,
          refs_path=ROOT / 'data/pilot/proposed_labels.jsonl', tail_base=TAIL):
    first_base, repeat_base = Path(first_base), Path(repeat_base)
    first_manifest = repeats.load_first_static(first_base)
    refs_path = Path(refs_path)
    if smoke.sha(refs_path.read_bytes()) != REFERENCE_SHA256:
        raise ValueError('Frozen development reference SHA-256 differs')
    refs = read_rows(refs_path)
    ids = [item['id'] for item in first_manifest['requests']]
    if len(refs) != 60 or [row['id'] for row in refs] != ids or any(
            not valid(row.get('proposed_labels')) or row.get('split') != 'development'
            or row.get('review_status') != 'ai_reviewed_provisional' for row in refs):
        raise ValueError('Provisional development references differ from pass IDs')
    passes = {'fresh1': summarize(first_manifest, first_base, refs, ledger_path)}
    predictions = {'fresh1': passes['fresh1'].pop('_predictions')}
    for ordinal in (2, 3):
        directory = repeats.pass_dir(repeat_base, ordinal)
        completed = directory / 'completion.json'
        if not completed.exists():
            attempts = directory / 'attempts.jsonl'
            audit = directory / 'interruption-audit.json'
            if audit.exists():
                manifest = repeats.load_frozen(ordinal, repeat_base, first_base, ledger_path)
                passes['fresh' + str(ordinal)] = interrupted(manifest, directory, ledger_path)
                if ordinal == 3:
                    tail_base = Path(tail_base)
                    if (tail_base / 'completion.json').exists():
                        passes['fresh3'] = closed_continuation(
                            manifest, directory, tail_base, ledger_path, passes['fresh3'])
                    elif (tail_base / 'attempts.jsonl').exists():
                        passes['fresh3']['continuationStatus'] = 'running_unscored'
                    else:
                        passes['fresh3']['continuationStatus'] = 'not_started'
            elif attempts.exists():
                passes['fresh' + str(ordinal)] = {'passId': repeats.PASSES[ordinal],
                                                   'completionStatus': 'running', 'score': None}
            else:
                passes['fresh' + str(ordinal)] = {'passId': repeats.PASSES[ordinal],
                                                   'completionStatus': 'pending'}
            continue
        manifest = repeats.load_frozen(ordinal, repeat_base, first_base, ledger_path)
        if manifest['requests'] != first_manifest['requests'] or manifest['model'] != first_manifest['model'] or \
                manifest['provider_tag'] != first_manifest['provider_tag'] or \
                manifest['condition'] != 'native P0 Choice':
            raise ValueError('Repeat wire/model/condition differs from first pass')
        passes['fresh' + str(ordinal)] = summarize(manifest, directory, refs, ledger_path)
        predictions['fresh' + str(ordinal)] = passes['fresh' + str(ordinal)].pop('_predictions')
    completed = sum(value['completionStatus'] == 'complete' for value in passes.values())
    comparisons = {}
    for later in ('fresh2', 'fresh3'):
        if later not in predictions:
            continue
        before, after = predictions['fresh1'], predictions[later]
        comparisons['fresh1_to_' + later] = {
            'recordsWithIdenticalFourFields': sum(before[ident] == after[ident] for ident in before),
            'fieldAgreement': {key: sum(before[ident][key] == after[ident][key] for ident in before)
                               for key in KEYS},
            'denominator': len(before)}
    return {'schema': 'kev-native-repeat-findings-v1',
            'configuration': 'kev-openrouter-native-p0', 'displayName': 'Kev 4B OpenRouter native Choice',
            'model': first_manifest['model'], 'provider': first_manifest['expected_returned_provider'],
            'method': 'native-output-stability', 'conditionOrder': ['P0'],
            'referenceStatus': 'Frozen v0.2 labels remain provisional. Project owner confirmed human review of all 60 labels on 2026-10-02. This report applies no label corrections.',
            'denominator': 60, 'completedPasses': completed, 'plannedPasses': 3,
            'passOrder': ['fresh1', 'fresh2', 'fresh3'], 'passes': passes,
            'repeatComparisons': comparisons,
            'interpretation': {'reportedConfidence': 'Native response confidence, descriptive only; not a calibrated probability of correctness.',
                               'thresholds': 'Coverage and correctness are counted among field decisions with reported confidence at or above each explicit threshold. No abstention was executed.',
                               'timing': 'Client-observed request duration includes network and local work, not provider inference time.',
                               'tokens': 'Provider-reported usage; output tokens are not treated as billed output charges.',
                               'comparability': 'Only closed successor passes with the frozen native P0 request set and verified predecessor evidence are included.'},
            'referenceBinding': binding(refs_path),
            'nativePlanBinding': binding(first_base / 'native-plan.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true', help='Check saved output without writing')
    args = parser.parse_args()
    result = build()
    expected = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != expected:
            raise ValueError(f'Stale Kev native report: {args.output}')
    else:
        args.output.write_text(expected)
    print(f"{result['completedPasses']}/3 closed Kev native passes -> {args.output}")


if __name__ == '__main__':
    main()
