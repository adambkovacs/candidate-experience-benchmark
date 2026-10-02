#!/usr/bin/env python3
"""Build the source-bound paired Clef fresh1/fresh2 P0 repeat report."""

import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path

import build_clef_findings as first
import clef_connected_app_bridge as bridge
import clef_native_fresh2_p0 as fresh2
import clef_native_preparation as prep

ROOT = first.ROOT
BASE = first.BASE
OUTPUT = Path('public-site/clef-p0-repeat-findings.json')
SECOND_MANIFEST = BASE / 'repeat-continuation-v1/fresh2-p0-admission-v1.json'
FIRST_FEED = first.OUTPUT
MODELS = first.MODELS
IDS = first.IDS


def exact_stage(sources, model, manifest, labels):
    """Read a closed fresh2 stage, including every durable app handoff."""
    directory = BASE / model / 'fresh2/P0/development'
    grant_path = BASE / f'repeat-continuation-v1/fresh2-p0-grants/{model}-development-grant.json'
    review_path = BASE / model / 'fresh2/P0/smoke/smoke-review.json'
    smoke_dir = BASE / model / 'fresh2/P0/smoke'
    for name in ('claim.json', 'completion.json', 'journal.jsonl', 'raw.jsonl',
                 'records.jsonl', 'budget.jsonl'):
        sources.path(smoke_dir / name)
    smoke_claim = sources.json(smoke_dir / 'claim.json')
    smoke_completion = sources.json(smoke_dir / 'completion.json')
    review = sources.json(review_path)
    grant = sources.json(grant_path)
    claim = sources.json(directory / 'claim.json')
    completion = sources.json(directory / 'completion.json')
    budget = sources.rows(directory / 'budget.jsonl')
    journal = sources.rows(directory / 'journal.jsonl')
    raw = sources.rows(directory / 'raw.jsonl')
    records = sources.rows(directory / 'records.jsonl')
    manifest_hash = sources.hashes[str(SECOND_MANIFEST)]
    grant_hash = sources.hashes[str(grant_path)]
    stage = fresh2.stage_name(model, 'development')
    if (smoke_claim.get('manifest_sha256') != manifest_hash or
            smoke_claim.get('account_id_sha256') != claim.get('account_id_sha256') or
            smoke_completion.get('kind') != 'clef-native-fresh2-p0-completion-v1' or
            smoke_completion.get('model') != model or
            smoke_completion.get('stage') != fresh2.stage_name(model, 'smoke') or
            smoke_completion.get('status') != 'complete' or
            smoke_completion.get('attempted') != 3 or
            smoke_completion.get('counts') != {'valid': 3, 'invalid_output': 0,
                'service_error': 0, 'unknown_outcome': 0} or
            smoke_completion.get('never_sent') != [] or
            any(smoke_completion.get(key) != sources.hashes[str(smoke_dir / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            review.get('kind') != fresh2.INSPECTION_KIND or
            review.get('approved') is not True or review.get('model') != model or
            review.get('manifest_sha256') != manifest_hash or
            review.get('completion_sha256') != sources.hashes[str(smoke_dir / 'completion.json')] or
            review.get('records_sha256') != sources.hashes[str(smoke_dir / 'records.jsonl')] or
            review.get('raw_sha256') != sources.hashes[str(smoke_dir / 'raw.jsonl')] or
            review.get('decision') != 'admit_unchanged_full_p0' or
            grant.get('kind') != fresh2.GRANT_KIND or grant.get('approved') is not True or
            grant.get('model') != model or grant.get('phase') != 'development' or
            grant.get('stage') != stage or grant.get('manifest_sha256') != manifest_hash or
            grant.get('smoke_review_sha256') != sources.hashes[str(review_path)] or
            grant.get('controller_sha256') != sources.hashes['scripts/clef_native_fresh2_p0.py'] or
            grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            grant.get('full_context_hold_usd') != str(prep.reservation_usd(model, 60)) or
            grant.get('global_authority_approval_sha256') != fresh2.APPROVAL_SHA256 or
            grant.get('global_authority_cap_usd') != str(fresh2.CAP) or
            grant.get('account_id_sha256') != claim.get('account_id_sha256') or
            claim.get('kind') != 'clef-native-fresh2-p0-claim-v1' or
            claim.get('model') != model or claim.get('stage') != stage or
            claim.get('manifest_sha256') != manifest_hash or
            claim.get('grant_sha256') != grant_hash or
            claim.get('controller_sha256') != sources.hashes['scripts/clef_native_fresh2_p0.py'] or
            claim.get('global_authority_hold_usd') != str(prep.reservation_usd(model, 60)) or
            completion.get('kind') != 'clef-native-fresh2-p0-completion-v1' or
            completion.get('model') != model or completion.get('stage') != stage or
            completion.get('status') != 'complete' or completion.get('attempted') != 60 or
            completion.get('counts') != {'valid': 60, 'invalid_output': 0,
                'service_error': 0, 'unknown_outcome': 0} or
            completion.get('never_sent') != [] or
            completion.get('unknown_cost_reserved_usd') != str(prep.reservation_usd(model, 60)) or
            any(completion.get(key) != sources.hashes[str(directory / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            budget[0] != {'event': 'budget', 'stage': stage,
                'cap_usd': str(prep.reservation_usd(model, 60)),
                'manifest_sha256': manifest_hash, 'grant_sha256': grant_hash} or
            len(budget) != 61 or len(journal) != 180 or len(raw) != 60 or
            len(records) != 60):
        raise ValueError(f'Incomplete or unbound fresh2 P0 stage: {model}')
    entries = []
    client_seconds = 0.0
    for index, rid in enumerate(IDS):
        planned = manifest['models'][model]['requests'][index]
        reserve, started, finished = journal[3 * index:3 * index + 3]
        raw_row, record = raw[index], records[index]
        attempt = reserve.get('attempt_id')
        request_hash = planned['payload_sha256']
        usd = str(prep.reservation_usd(model, 1))
        if (planned['id'] != rid or
                reserve != {'event': 'reserved', 'attempt_id': attempt, 'id': rid,
                            'request_sha256': request_hash, 'usd': usd} or
                started != {'event': 'started', 'attempt_id': attempt, 'id': rid} or
                finished != {'event': 'finished', 'attempt_id': attempt,
                             'id': rid, 'status': 'valid'} or
                budget[index + 1] != {'event': 'reserve', 'stage': stage,
                    'attempt_id': attempt, 'id': rid, 'usd': usd}):
            raise ValueError(f'Fresh2 order/reservation mismatch: {model}/{rid}')
        bridge_dir = directory / 'app-bridge'
        paths = {name: bridge_dir / f'{attempt}.{name}.json'
                 for name in ('request', 'dispatch', 'tool-result', 'app-result', 'response')}
        ready, dispatch, tool, app, reply = (sources.json(paths[name]) for name in paths)
        app_bytes = sources.path(paths['app-result']).read_bytes()
        if (ready.get('kind') != bridge.KIND + '-request' or
                ready.get('attempt_id') != attempt or ready.get('id') != rid or
                ready.get('model') != model or ready.get('stage') != stage or
                ready.get('review_sha256') != grant_hash or
                ready.get('account_id_sha256') != claim['account_id_sha256'] or
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
                reply != {'kind': bridge.KIND + '-response', 'attempt_id': attempt,
                          'request_sha256': request_hash, 'http_status': 200,
                          'body_base64': base64.b64encode(app_bytes).decode('ascii')} or
                raw_row.get('attempt_id') != attempt or raw_row.get('id') != rid or
                raw_row.get('request_sha256') != request_hash or
                raw_row.get('http_status') != 200 or raw_row.get('redacted') is not False or
                raw_row.get('error_type') is not None or
                base64.b64decode(raw_row['raw_response_base64'], validate=True) != app_bytes or
                raw_row.get('response_sha256') != prep.sha(app_bytes) or
                record.get('attempt_id') != attempt or record.get('id') != rid or
                record.get('request_sha256') != request_hash or
                record.get('status') != 'valid' or record.get('reason') is not None or
                record.get('charge_status') != 'unknown_reserved' or
                record.get('reservation_usd') != usd or
                record.get('reference_labels_read') is not False or
                record.get('parsed') != prep.parse_rest_response(app, model)):
            raise ValueError(f'Fresh2 raw/parsed mismatch: {model}/{rid}')
        parsed = record['parsed']
        if parsed['actual_charge_usd'] is not None:
            raise ValueError('Provider charge claimed without billing evidence')
        seconds = raw_row.get('client_seconds')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Invalid client elapsed time')
        client_seconds += seconds
        entries.append({'id': rid, 'reference': labels[rid],
                        'prediction': parsed['prediction'],
                        'probabilities': parsed['probabilities'],
                        'confidence': parsed['confidence'], 'usage': parsed['usage']})
    return entries, client_seconds


def paired(first_entries, second_entries):
    if ([r['id'] for r in first_entries] != list(IDS) or
            [r['id'] for r in second_entries] != list(IDS)):
        raise ValueError('Paired membership differs')
    vector_flips, all_four_gained, all_four_lost = [], [], []
    fields = {}
    for field in prep.KEYS:
        changed, gained, lost, probability_changed, confidence_changed = [], [], [], [], []
        for a, b in zip(first_entries, second_entries):
            rid = a['id']
            if a['prediction'][field] != b['prediction'][field]:
                changed.append(rid)
            ac = a['prediction'][field] == a['reference'][field]
            bc = b['prediction'][field] == b['reference'][field]
            if not ac and bc: gained.append(rid)
            if ac and not bc: lost.append(rid)
            if a['probabilities'][field] != b['probabilities'][field]:
                probability_changed.append(rid)
            if a['confidence'][field] != b['confidence'][field]:
                confidence_changed.append(rid)
        fields[field] = {'firstCorrect': sum(a['prediction'][field] == a['reference'][field] for a in first_entries),
                         'secondCorrect': sum(b['prediction'][field] == b['reference'][field] for b in second_entries),
                         'predictionChangedIds': changed, 'becameCorrectIds': gained,
                         'becameIncorrectIds': lost,
                         'nativeDistributionChangedIds': probability_changed,
                         'vendorConfidenceChangedIds': confidence_changed}
    for a, b in zip(first_entries, second_entries):
        rid = a['id']
        if a['prediction'] != b['prediction']:
            vector_flips.append(rid)
        ac = all(a['prediction'][f] == a['reference'][f] for f in prep.KEYS)
        bc = all(b['prediction'][f] == b['reference'][f] for f in prep.KEYS)
        if not ac and bc: all_four_gained.append(rid)
        if ac and not bc: all_four_lost.append(rid)
    return {'sharedValid': 60, 'predictionVectorChangedIds': vector_flips,
            'allFourBecameCorrectIds': all_four_gained,
            'allFourBecameIncorrectIds': all_four_lost, 'fields': fields}


def build(root=ROOT):
    root = Path(root)
    first_report = first.build(root)
    sources = first.Sources(root)
    saved_first = sources.json(FIRST_FEED)
    if saved_first != first_report:
        raise ValueError('Frozen fresh1 findings feed differs from evidence')
    for name in ('scripts/clef_native_fresh2_p0.py', 'scripts/clef_native_preparation.py',
                 'scripts/clef_connected_app_bridge.py'):
        sources.path(name)
    sources.path(BASE / 'repeat-continuation-v1/proposed-manifest.json')
    sources.path(BASE / 'preparation.json')
    sources.path(BASE / 'postapproval-ledger-after-full-p0.jsonl')
    manifest = sources.json(SECOND_MANIFEST)
    if manifest != fresh2.manifest_value(root, root / BASE / 'repeat-continuation-v1/proposed-manifest.json'):
        raise ValueError('Fresh2 manifest differs from frozen controls')
    first_manifest = sources.json(BASE / 'full-p0-manifest-v1.json')
    label_rows = sources.rows(first.LABELS)
    if sources.hashes[str(first.LABELS)] != first.LABELS_SHA256:
        raise ValueError('Frozen reference changed')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    models = {}
    for model in MODELS:
        if (first_manifest['models'][model]['route'] != manifest['models'][model]['route'] or
                first_manifest['models'][model]['requests'] != manifest['models'][model]['requests'] or
                manifest['models'][model]['route'] != prep.MODELS[model]['route']):
            raise ValueError('Fresh1/fresh2 model request controls differ')
        first_rows = sources.rows(BASE / model / 'fresh1/P0/development/records.jsonl')
        first_entries = [{'id': row['id'], 'reference': labels[row['id']],
                          'prediction': row['parsed']['prediction'],
                          'probabilities': row['parsed']['probabilities'],
                          'confidence': row['parsed']['confidence'],
                          'usage': row['parsed']['usage']} for row in first_rows]
        second_entries, seconds = exact_stage(sources, model, manifest, labels)
        first_score = first_report['models'][model]
        second_fields = {f: first.field_metrics(second_entries, f) for f in prep.KEYS}
        second_all_four = sum(all(row['prediction'][f] == row['reference'][f]
                                  for f in prep.KEYS) for row in second_entries)
        if (first_score['allFourCorrect'] != sum(all(row['prediction'][f] == row['reference'][f]
                                                     for f in prep.KEYS) for row in first_entries) or
                any(first_score['fields'][f] != first.field_metrics(first_entries, f)
                    for f in prep.KEYS)):
            raise ValueError('Fresh1 records differ from frozen findings')
        input_tokens = sum(row['usage']['input_tokens'] for row in second_entries)
        output_tokens = sum(row['usage'].get('output_tokens', 0) for row in second_entries)
        models[model] = {'route': manifest['models'][model]['route'],
            'control': {'sameOrderedInputAndPayloadHashes': True,
                        'sameConnectedAppTransport': True,
                        'referenceLabelsSent': False},
            'fresh1': {'valid': 60, 'allFourCorrect': first_score['allFourCorrect'],
                       'fields': {f: first_score['fields'][f]['correct'] for f in prep.KEYS},
                       'observedInputTokens': first_score['observedInputTokens'],
                       'observedOutputTokens': first_score['observedOutputTokens'],
                       'publishedInputPriceEstimateUsd': first_score['publishedInputPriceEstimateUsd'],
                       'providerBilledUsd': None},
            'fresh2': {'valid': 60, 'allFourCorrect': second_all_four,
                       'fields': second_fields,
                       'observedInputTokens': input_tokens,
                       'observedOutputTokens': output_tokens,
                       'publishedInputPriceEstimateUsd': str(
                           Decimal(input_tokens) * prep.MODELS[model]['input_usd_per_million'] / Decimal(1_000_000)),
                       'unknownCostReservedUsd': str(prep.reservation_usd(model, 60)),
                       'providerBilledUsd': None,
                       'clientElapsedSeconds': round(seconds, 6)},
            'paired': paired(first_entries, second_entries)}
    return {'schema': 'clef-native-p0-repeat-findings-v1',
        'referenceStatus': 'Frozen provisional v0.2 key; project owner confirmed human checks of all 60 reviews on 2026-10-02',
            'cohort': {'records': 60, 'condition': 'P0', 'fullPassesPerModelCompleted': 2,
                       'requiredFullPassesPerCondition': 3,
                       'otherConditionsCompleted': False},
            'models': models,
            'definitions': {'score': 'Agreement with the frozen provisional v0.2 key. The project owner confirmed human checks of all 60 reviews; this synthetic-cohort score is not real-world hiring accuracy.',
                'paired': 'The same 60 reviews appear in both passes; changed IDs and correctness transitions use this fixed shared denominator.',
                'nativeDistribution': 'Choice probability distributions support Brier, log loss, and chosen-label reliability. They are separate from vendor confidence.',
                'vendorConfidence': 'Provider confidence has no assumed probability-calibration semantics.',
                'cost': 'Full-context holds and observed-token list-price estimates are not provider bills; provider USD charges are unavailable.',
                'timing': 'Connected-app client elapsed seconds include operator handoff and do not isolate model inference.'},
            'sourceSha256': {**first_report['sourceSha256'], **sources.hashes}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build()
    payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    path = ROOT / OUTPUT
    if args.check:
        if path.read_text() != payload:
            raise ValueError('Saved Clef P0 repeat report differs from closed evidence')
    else:
        path.write_text(payload)
    print(path)


if __name__ == '__main__':
    main()
