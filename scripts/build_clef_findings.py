#!/usr/bin/env python3
"""Build source-bound Clef native P0 findings from two terminal 60-record runs."""

import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

import clef_native_preparation as prep
import clef_native_full_p0 as full
import clef_connected_app_bridge as bridge
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/clef-native-v1')
OUTPUT = Path('public-site/clef-findings.json')
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
MODELS = ('clef', 'clef-flash')
IDS = tuple(f'DEV-{number:03d}' for number in range(1, 61))
HIGH_CONFIDENCE = 0.8


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Sources:
    def __init__(self, root):
        self.root = Path(root)
        self.hashes = {}

    def path(self, relative):
        relative = Path(relative)
        path = (self.root / relative).resolve()
        path.relative_to(self.root.resolve())
        self.hashes[str(relative)] = sha(path)
        return path

    def json(self, relative):
        return json.loads(self.path(relative).read_bytes())

    def rows(self, relative):
        raw = self.path(relative).read_bytes()
        if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
            raise ValueError(f'Incomplete JSONL: {relative}')
        return [json.loads(line) for line in raw.splitlines()]


def field_metrics(entries, field):
    """Score full native distributions; vendor confidence stays separate."""
    choices = tuple(prep.VALUES[field])
    confusion = {reference: {prediction: 0 for prediction in choices}
                 for reference in choices}
    brier_sum = 0.0
    log_loss_sum = 0.0
    zero_truth_probability = 0
    bins = [{'count': 0, 'chosenProbabilitySum': 0.0, 'correct': 0}
            for _ in range(5)]
    vendor_errors = []
    chosen_probability_errors = []
    for item in entries:
        reference = item['reference'][field]
        prediction = item['prediction'][field]
        probabilities = item['probabilities'][field]
        vendor_confidence = item['confidence'][field]
        if (reference not in choices or prediction not in choices or
                set(probabilities) != set(choices) or
                any(type(probabilities[label]) not in (int, float) or
                        not math.isfinite(probabilities[label]) or
                        not 0 <= probabilities[label] <= 1 for label in choices) or
                not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6) or
                type(vendor_confidence) not in (int, float) or
                not math.isfinite(vendor_confidence) or
                not 0 <= vendor_confidence <= 1):
            raise ValueError('Invalid native distribution or vendor confidence')
        correct = int(prediction == reference)
        confusion[reference][prediction] += 1
        brier_sum += sum((probabilities[label] - int(label == reference)) ** 2
                         for label in choices)
        truth_probability = probabilities[reference]
        if truth_probability == 0:
            zero_truth_probability += 1
        else:
            log_loss_sum -= math.log(truth_probability)
        chosen_probability = probabilities[prediction]
        bucket = min(int(chosen_probability * 5), 4)
        bins[bucket]['count'] += 1
        bins[bucket]['chosenProbabilitySum'] += chosen_probability
        bins[bucket]['correct'] += correct
        if not correct:
            detail = {'id': item['id'], 'reference': reference,
                      'prediction': prediction,
                      'vendorConfidence': round(vendor_confidence, 6),
                      'chosenProbability': round(chosen_probability, 6)}
            if vendor_confidence >= HIGH_CONFIDENCE:
                vendor_errors.append(detail)
            if chosen_probability >= HIGH_CONFIDENCE:
                chosen_probability_errors.append(detail)
    n = len(entries)
    if n != 60:
        raise ValueError('Expected exact 60 valid predictions')
    reliability = []
    ece = 0.0
    for index, item in enumerate(bins):
        count = item['count']
        avg_probability = item['chosenProbabilitySum'] / count if count else None
        observed_accuracy = item['correct'] / count if count else None
        if count:
            ece += count / n * abs(avg_probability - observed_accuracy)
        reliability.append({'fromInclusive': index / 5,
                            'toExclusiveExceptOne': (index + 1) / 5,
                            'count': count,
                            'meanChosenProbability': round(avg_probability, 6)
                            if avg_probability is not None else None,
                            'observedAccuracy': round(observed_accuracy, 6)
                            if observed_accuracy is not None else None})
    threshold_selection = []
    for threshold in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95):
        retained = [item for item in entries if
                    item['probabilities'][field][item['prediction'][field]] >= threshold]
        matches = sum(item['prediction'][field] == item['reference'][field]
                      for item in retained)
        threshold_selection.append({'thresholdInclusive': threshold,
            'retained': len(retained), 'sentForReview': n - len(retained),
            'matchingRetained': matches, 'nonmatchingRetained': len(retained) - matches,
            'coverageOf60': round(len(retained) / n, 6),
            'agreementAmongRetained': round(matches / len(retained), 6) if retained else None})
    hits = sum(confusion[value][value] for value in choices)
    return {'valid': n, 'correct': hits, 'accuracy': round(hits / n, 6),
            'confusion': confusion,
            'nativeDistribution': {
                'multiclassBrierMean': round(brier_sum / n, 6),
                'meanNegativeLogTrueClassProbability':
                    round(log_loss_sum / n, 6) if not zero_truth_probability else None,
                'zeroTrueClassProbabilityCount': zero_truth_probability,
                'chosenLabelReliability': reliability,
                'chosenLabelEceFiveBins': round(ece, 6)},
            'vendorConfidenceHighErrors': vendor_errors,
            'chosenProbabilityHighErrors': chosen_probability_errors,
            'postHocThresholdSelection': threshold_selection}


def terminal_model(sources, model, manifest, labels, development_ledger):
    directory = BASE / model / 'fresh1/P0/development'
    grant_path = BASE / f'{model}-full-p0-grant.json'
    grant = sources.json(grant_path)
    claim = sources.json(directory / 'claim.json')
    completion = sources.json(directory / 'completion.json')
    journal = sources.rows(directory / 'journal.jsonl')
    raw = sources.rows(directory / 'raw.jsonl')
    records = sources.rows(directory / 'records.jsonl')
    if (grant.get('approved') is not True or grant.get('model') != model or
            grant.get('manifest_sha256') != sources.hashes[str(BASE / 'full-p0-manifest-v1.json')] or
            grant.get('controller_sha256') != sources.hashes['scripts/clef_native_full_p0.py'] or
            grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            claim.get('model') != model or claim.get('stage') != full.STAGE or
            claim.get('grant_sha256') != sources.hashes[str(grant_path)] or
            claim.get('manifest_sha256') != grant['manifest_sha256'] or
            claim.get('controller_sha256') != grant['controller_sha256'] or
            claim.get('account_id_sha256') != grant['account_id_sha256'] or
            completion != {'kind': 'clef-native-full-p0-completion-v1',
                           'model': model, 'stage': full.STAGE, 'status': 'complete',
                           'attempted': 60,
                           'counts': {'valid': 60, 'invalid_output': 0,
                                      'service_error': 0, 'unknown_outcome': 0},
                           'never_sent': [],
                           'claim_sha256': sources.hashes[str(directory / 'claim.json')],
                           'journal_sha256': sources.hashes[str(directory / 'journal.jsonl')],
                           'raw_sha256': sources.hashes[str(directory / 'raw.jsonl')],
                           'records_sha256': sources.hashes[str(directory / 'records.jsonl')],
                           'unknown_cost_reserved_usd': str(prep.reservation_usd(model, 60))} or
            len(journal) != 180 or len(raw) != 60 or len(records) != 60):
        raise ValueError(f'Incomplete or unbound Clef development stage: {model}')
    entries = []
    for index, rid in enumerate(IDS):
        planned = manifest['models'][model]['requests'][index]
        reserve, started, finished = journal[3 * index:3 * index + 3]
        raw_row, record = raw[index], records[index]
        attempt_id = reserve.get('attempt_id')
        request_hash = planned['payload_sha256']
        matching_budget = development_ledger[1 + (0 if model == 'clef' else 60) + index]
        if (planned['id'] != rid or
                reserve != {'event': 'reserved', 'attempt_id': attempt_id,
                            'id': rid, 'request_sha256': request_hash,
                            'usd': str(prep.reservation_usd(model, 1))} or
                started != {'event': 'started', 'attempt_id': attempt_id, 'id': rid} or
                finished != {'event': 'finished', 'attempt_id': attempt_id,
                             'id': rid, 'status': 'valid'} or
                matching_budget != {'event': 'reserve', 'attempt_id': attempt_id,
                                    'model': model, 'id': rid, 'stage': full.STAGE,
                                    'usd': reserve['usd']}):
            raise ValueError(f'Clef order/reservation mismatch: {model}/{rid}')
        bridge_dir = directory / 'app-bridge'
        paths = {name: bridge_dir / f'{attempt_id}.{name}.json'
                 for name in ('request', 'dispatch', 'tool-result', 'app-result', 'response')}
        ready, dispatch, tool, app, reply = (sources.json(paths[name]) for name in paths)
        app_bytes = sources.path(paths['app-result']).read_bytes()
        if (ready.get('kind') != bridge.KIND + '-request' or
                ready.get('attempt_id') != attempt_id or ready.get('id') != rid or
                ready.get('model') != model or ready.get('stage') != full.STAGE or
                ready.get('review_sha256') != sources.hashes[str(grant_path)] or
                ready.get('account_id_sha256') != grant['account_id_sha256'] or
                ready.get('request_sha256') != request_hash or
                ready.get('method') != 'POST' or
                ready.get('path') != '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[model]['route'] or
                prep.sha(prep.canonical(ready.get('body'))) != request_hash or
                dispatch.get('request_sha256') != request_hash or
                not isinstance(dispatch.get('operator'), str) or not dispatch['operator'] or
                tool.get('isError') is not False or len(tool.get('content', [])) != 1 or
                tool['content'][0].get('type') != 'text' or
                json.loads(tool['content'][0]['text']) != app or
                app.get('status') != 200 or app.get('success') is not True or
                app.get('errors') != [] or app.get('result', {}).get('model') != model or
                reply != {'kind': bridge.KIND + '-response', 'attempt_id': attempt_id,
                          'request_sha256': request_hash, 'http_status': 200,
                          'body_base64': base64.b64encode(app_bytes).decode('ascii')} or
                raw_row.get('attempt_id') != attempt_id or raw_row.get('id') != rid or
                raw_row.get('request_sha256') != request_hash or
                raw_row.get('http_status') != 200 or raw_row.get('redacted') is not False or
                raw_row.get('error_type') is not None or
                base64.b64decode(raw_row['raw_response_base64'], validate=True) != app_bytes or
                raw_row.get('response_sha256') != prep.sha(app_bytes) or
                record.get('attempt_id') != attempt_id or record.get('id') != rid or
                record.get('request_sha256') != request_hash or
                record.get('status') != 'valid' or record.get('reason') is not None or
                record.get('charge_status') != 'unknown_reserved' or
                record.get('reservation_usd') != reserve['usd'] or
                record.get('reference_labels_read') is not False or
                record.get('parsed') != prep.parse_rest_response(app, model)):
            raise ValueError(f'Clef raw/parsed mismatch: {model}/{rid}')
        parsed = record['parsed']
        if parsed['actual_charge_usd'] is not None:
            raise ValueError('Provider charge claimed without billing evidence')
        entries.append({'id': rid, 'reference': labels[rid],
                        'prediction': parsed['prediction'],
                        'probabilities': parsed['probabilities'],
                        'confidence': parsed['confidence'],
                        'usage': parsed['usage']})
    fields = {field: field_metrics(entries, field) for field in prep.KEYS}
    all_four = sum(all(item['prediction'][field] == item['reference'][field]
                       for field in prep.KEYS) for item in entries)
    return {'stage': full.STAGE, 'records': 60, 'valid': 60, 'failed': 0,
            'neverSent': 0, 'allFourCorrect': all_four,
            'allFourAccuracy': round(all_four / 60, 6), 'fields': fields,
            'observedInputTokens': sum(item['usage']['input_tokens'] for item in entries),
            'observedOutputTokens': sum(item['usage'].get('output_tokens', 0) for item in entries),
            'publishedInputPriceEstimateUsd': str(
                Decimal(sum(item['usage']['input_tokens'] for item in entries)) *
                prep.MODELS[model]['input_usd_per_million'] / Decimal(1_000_000)),
            'unknownCostReservedUsd': str(prep.reservation_usd(model, 60)),
            'providerBilledUsd': None,
            'predictionById': {item['id']: item['prediction'] for item in entries},
            'allFourCorrectIds': [item['id'] for item in entries if all(
                item['prediction'][field] == item['reference'][field]
                for field in prep.KEYS)]}


def build(root=ROOT):
    root = Path(root)
    # Never publish a partial two-model study while either stage is live.
    for model in MODELS:
        if not (root / BASE / model / 'fresh1/P0/development/completion.json').is_file():
            raise ValueError(f'Clef development stage not terminal: {model}')
    sources = Sources(root)
    labels_path = sources.path(LABELS)
    if sources.hashes[str(LABELS)] != LABELS_SHA256:
        raise ValueError('Frozen v0.2 reference labels changed')
    label_rows = [json.loads(line) for line in labels_path.read_bytes().splitlines()]
    if ([row.get('id') for row in label_rows] != list(IDS) or
            any(row.get('review_version') != '0.2' or
                not valid(row.get('proposed_labels')) for row in label_rows)):
        raise ValueError('Reference membership or schema differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    for path in ('scripts/clef_native_preparation.py',
                 'scripts/clef_native_full_p0.py',
                 'scripts/clef_connected_app_bridge.py',
                 'scripts/inspect_clef_native_smoke.py'):
        sources.path(path)
    manifest = sources.json(BASE / 'full-p0-manifest-v1.json')
    if manifest != full.manifest_value():
        raise ValueError('Full P0 manifest differs from frozen inputs')
    smoke_inspection = sources.json(BASE / 'smoke-inspection-v1.json')
    authority = sources.rows(BASE / 'postapproval-ledger-after-full-p0.jsonl')
    budget = sources.rows(BASE / 'development-budget.jsonl')
    smoke_budget_path = BASE / 'budget.jsonl'
    gemma_budget_path = full.GEMMA_BUDGET.relative_to(root)
    sources.path(smoke_budget_path)
    sources.path(gemma_budget_path)
    if (manifest.get('kind') != 'clef-native-full-p0-manifest-v1' or
            manifest.get('records') != 60 or manifest.get('stage') != full.STAGE or
            manifest.get('controller_sha256') != sources.hashes['scripts/clef_native_full_p0.py'] or
            manifest.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            manifest.get('smoke_inspector_sha256') != sources.hashes['scripts/inspect_clef_native_smoke.py'] or
            manifest.get('smoke_inspection_sha256') != sources.hashes[str(BASE / 'smoke-inspection-v1.json')] or
            smoke_inspection.get('status') != 'six_valid_unknown_charge' or
            authority[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                             'cap_usd': '10.00', 'decision_key': full.AUTHORITY_KEY,
                             'approval_sha256': full.APPROVAL_SHA256} or
            len(budget) != 121 or
            budget[0] != {'event': 'budget', 'cap_usd': '1.30',
                          'manifest_sha256': sources.hashes[str(BASE / 'full-p0-manifest-v1.json')],
                          'global_authority_approval_sha256': full.APPROVAL_SHA256}):
        raise ValueError('Clef manifest or shared budget provenance differs')
    holds = {event['id']: event for event in authority[1:]}
    if len(holds) != len(authority) - 1:
        raise ValueError('Duplicate global authority hold')
    for hold_id, hold_usd, source_path in (
            ('cloudflare-initial-smoke', '0.064884', smoke_budget_path),
            ('openrouter-gemma-fifth', '0.60', gemma_budget_path)):
        if holds.get(hold_id) != {'event': 'hold', 'id': hold_id,
                                  'usd': hold_usd,
                                  'source_sha256': sources.hashes[str(source_path)]}:
            raise ValueError('Global carry hold differs')
    for model in MODELS:
        grant_path = BASE / f'{model}-full-p0-grant.json'
        grant = sources.json(grant_path)
        billing_path = BASE / f'{model}-billing-source.md'
        billing_source = sources.path(billing_path).read_text()
        rate = prep.MODELS[model]['input_usd_per_million']
        if (grant['billing_source_sha256'][model] != sources.hashes[str(billing_path)] or
                f'${rate} per M input tokens' not in billing_source):
            raise ValueError('Published model price source differs')
        if holds.get('cloudflare-' + model + '-fresh1-p0-development') != {
                'event': 'hold', 'id': 'cloudflare-' + model + '-fresh1-p0-development',
                'usd': str(prep.reservation_usd(model, 60)),
                'source_sha256': sources.hashes[str(grant_path)]}:
            raise ValueError('Global model hold differs')
    if sum(Decimal(event['usd']) for event in authority[1:]) > full.GLOBAL_CAP:
        raise ValueError('Global authority cap exceeded')
    if sum(Decimal(event['usd']) for event in budget[1:]) != sum(
            (prep.reservation_usd(model, 60) for model in MODELS), Decimal(0)):
        raise ValueError('Cloudflare development reservations differ')
    models = {model: terminal_model(sources, model, manifest, labels, budget)
              for model in MODELS}
    paired_ids = [rid for rid in IDS if models['clef']['predictionById'][rid] !=
                  models['clef-flash']['predictionById'][rid]]
    paired_all_four = Counter(
        ('correct' if rid in models['clef']['allFourCorrectIds'] else 'incorrect',
         'correct' if rid in models['clef-flash']['allFourCorrectIds'] else 'incorrect')
        for rid in IDS)
    for model in MODELS:
        del models[model]['predictionById']
        del models[model]['allFourCorrectIds']
    return {'schema': 'clef-native-p0-findings-v1',
            'referenceStatus': 'Frozen provisional v0.2 key; project owner confirmed human checks of all 60 reviews on 2026-10-02; not an independently adjudicated ground truth',
            'cohort': {'records': 60, 'pass': 'fresh1', 'condition': 'P0',
                       'configurationCount': 2, 'fullPassesPerModelCompleted': 1},
            'models': models,
            'paired': {'predictionVectorDisagreementCount': len(paired_ids),
                       'predictionVectorDisagreementIds': paired_ids,
                       'allFour': {f'{left}_{right}': paired_all_four[(left, right)]
                                   for left in ('correct', 'incorrect')
                                   for right in ('correct', 'incorrect')}},
            'calibrationDefinitions': {
                'multiclassBrierMean': 'Mean over 60 valid records of sum over labels (native probability minus one-hot reference)^2; lower is better, range 0 to 2.',
                'meanNegativeLogTrueClassProbability': 'Mean -ln(native probability assigned to reference label); null if any true-label probability is exactly zero.',
                'chosenLabelReliability': 'Five fixed bins of the native probability assigned to the returned choice versus that choice\'s observed accuracy; the final bin includes 1.',
                'chosenLabelEceFiveBins': 'Sum of bin fraction times absolute mean chosen probability minus observed accuracy; descriptive with 60 records.',
                'vendorConfidence': 'Separate provider field. Its semantics are not assumed to equal a chosen-label probability; no probability calibration is computed from it.',
                'highThresholdInclusive': HIGH_CONFIDENCE},
            'cost': {'smokeUnknownChargeHoldUsd': '0.064884',
                     'developmentUnknownChargeHoldUsd': str(sum(
                         (prep.reservation_usd(model, 60) for model in MODELS), Decimal(0))),
                     'providerBilledUsd': None,
                     'note': 'Full-context holds are budget bounds; published input-price estimates use observed tokens and are not provider charges.'},
            'timing': {'inferenceLatencyAvailable': False,
                       'reason': 'Client elapsed seconds include connected-app operator handoff.'},
            'sourceSha256': sources.hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build()
    payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    output = ROOT / OUTPUT
    if args.check:
        if output.read_text() != payload:
            raise ValueError('Saved Clef findings differ from current evidence')
        print(output)
    else:
        output.write_text(payload)
        print(output)


if __name__ == '__main__':
    main()
