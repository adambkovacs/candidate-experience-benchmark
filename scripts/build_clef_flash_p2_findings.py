#!/usr/bin/env python3
"""Build an offline, source-bound Clef Flash fresh1/P2 findings projection."""

import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path

import build_clef_findings as first
import build_clef_flash_p1_findings as p1
import clef_connected_app_bridge as bridge
import clef_native_preparation as prep
import clef_native_remaining as remaining

ROOT = first.ROOT
Sources = p1.Sources
BASE = Path('results/clef-native-v1')
MANIFEST = BASE / 'repeat-continuation-v1/remaining-admission-v1.json'
PROPOSAL = BASE / 'repeat-continuation-v1/proposed-manifest.json'
P1_OUTPUT = Path('results/clef-native-v1/clef-flash-p1-findings-public.json')
OUTPUT = Path('results/clef-native-v1/clef-flash-p2-findings-public.json')
MODEL = 'clef-flash'
PASS = 'fresh1'
CONDITION = 'P2'


def validate_smoke(sources, manifest, claim, directory, repeat):
    smoke_dir = directory.parent / 'smoke'
    claim_path, completion_path = smoke_dir / 'claim.json', smoke_dir / 'completion.json'
    review_path = smoke_dir / 'root-smoke-review.json'
    smoke_claim, completion, review = (sources.json(p) for p in
                                       (claim_path, completion_path, review_path))
    budget = sources.rows(smoke_dir / 'budget.jsonl')
    journal = sources.rows(smoke_dir / 'journal.jsonl')
    raw = sources.rows(smoke_dir / 'raw.jsonl')
    records = sources.rows(smoke_dir / 'records.jsonl')
    manifest_hash = sources.hashes[str(MANIFEST)]
    grant_path = BASE / f'repeat-continuation-v1/remaining-grants/clef-flash-{repeat}-p2-smoke-grant.json'
    grant = sources.json(grant_path)
    stage = f'{MODEL}/{repeat}/{CONDITION}/smoke'
    prior_hash = remaining.predecessor_hash(
        MODEL, repeat, CONDITION, manifest_hash, base=sources.root / BASE)
    planned = manifest['stages'][f'{MODEL}/{repeat}/{CONDITION}']['requests']
    if (smoke_claim.get('kind') != 'clef-native-remaining-claim-v1' or
            smoke_claim.get('model') != MODEL or smoke_claim.get('stage') != stage or
            smoke_claim.get('manifest_sha256') != manifest_hash or
            smoke_claim.get('prior_completion_sha256') != prior_hash or
            smoke_claim.get('account_id_sha256') != claim.get('account_id_sha256') or
            smoke_claim.get('grant_sha256') != sources.hashes[str(grant_path)] or
            completion.get('kind') != 'clef-native-remaining-completion-v1' or
            completion.get('model') != MODEL or completion.get('stage') != stage or
            completion.get('status') != 'complete' or completion.get('attempted') != 3 or
            completion.get('counts') != {'valid': 3, 'invalid_output': 0,
                'service_error': 0, 'unknown_outcome': 0} or completion.get('never_sent') != [] or
            any(completion.get(key) != sources.hashes[str(smoke_dir / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            review.get('kind') != remaining.INSPECTION_KIND or
            review.get('approved') is not True or review.get('model') != MODEL or
            review.get('stage') != stage or review.get('manifest_sha256') != manifest_hash or
            review.get('completion_sha256') != sources.hashes[str(completion_path)] or
            review.get('records_sha256') != sources.hashes[str(smoke_dir / 'records.jsonl')] or
            review.get('raw_sha256') != sources.hashes[str(smoke_dir / 'raw.jsonl')] or
            review.get('decision') != 'admit_unchanged_full_stage' or
            not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip() or
            grant.get('kind') != remaining.GRANT_KIND or grant.get('approved') is not True or
            grant.get('authorized_by_user') is not True or grant.get('model') != MODEL or
            grant.get('stage') != stage or grant.get('pass') != repeat or
            grant.get('condition') != CONDITION or grant.get('phase') != 'smoke' or
            grant.get('manifest_sha256') != manifest_hash or
            grant.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            grant.get('billing_source_sha256') != manifest['billing_source_sha256'][MODEL] or
            grant.get('account_id_sha256') != claim.get('account_id_sha256') or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            grant.get('global_authority_cap_usd') != str(remaining.CAP) or
            grant.get('global_authority_approval_sha256') != remaining.APPROVAL_SHA256 or
            grant.get('exhaustion_policy') != 'pause' or type(grant.get('wait_seconds')) is not int or
            not 1 <= grant['wait_seconds'] <= 600 or
            grant.get('prior_completion_sha256') != prior_hash or
            grant.get('full_context_hold_usd') != str(prep.reservation_usd(MODEL, 3)) or
            grant.get('smoke_review_sha256') is not None or
            not isinstance(grant.get('global_authority_ledger_sha256_at_admission'), str) or
            not isinstance(grant.get('reviewer'), str) or not grant['reviewer'].strip() or
            budget[0] != {'event': 'budget', 'stage': stage,
                'cap_usd': str(prep.reservation_usd(MODEL, 3)),
                'manifest_sha256': manifest_hash, 'grant_sha256': sources.hashes[str(grant_path)]} or
            len(budget) != 4 or len(journal) != 9 or len(raw) != 3 or len(records) != 3):
        raise ValueError('Incomplete or unbound P2 smoke evidence')
    for index, rid in enumerate(prep.SMOKE_IDS):
        plan, record = planned[index], records[index]
        if (plan['id'] != rid or record.get('id') != rid or record.get('status') != 'valid' or
                record.get('reference_labels_read') is not False or
                record.get('request_sha256') != plan['payload_sha256']):
            raise ValueError('P2 smoke record differs from frozen requests')
    return sources.hashes[str(review_path)]


def validate_stage(sources, manifest, labels, predecessor_claim, repeat, prior_completion_hash):
    directory = BASE / MODEL / repeat / CONDITION / 'development'
    stage = f'{MODEL}/{repeat}/{CONDITION}/development'
    grant_path = BASE / f'repeat-continuation-v1/remaining-grants/clef-flash-{repeat}-p2-development-grant.json'
    grant = sources.json(grant_path)
    claim, completion = (sources.json(directory / f) for f in ('claim.json', 'completion.json'))
    budget, journal, raw, records = (sources.rows(directory / f) for f in
        ('budget.jsonl', 'journal.jsonl', 'raw.jsonl', 'records.jsonl'))
    manifest_hash = sources.hashes[str(MANIFEST)]
    smoke_review_hash = validate_smoke(sources, manifest, claim, directory, repeat)
    planned = manifest['stages'][f'{MODEL}/{repeat}/{CONDITION}']['requests']
    hold = str(prep.reservation_usd(MODEL, 60))
    if (grant.get('kind') != remaining.GRANT_KIND or grant.get('approved') is not True or
            grant.get('authorized_by_user') is not True or grant.get('model') != MODEL or
            grant.get('stage') != stage or grant.get('pass') != repeat or
            grant.get('condition') != CONDITION or grant.get('phase') != 'development' or
            grant.get('manifest_sha256') != manifest_hash or
            grant.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            grant.get('billing_source_sha256') != manifest['billing_source_sha256'][MODEL] or
            grant.get('exhaustion_policy') != 'pause' or type(grant.get('wait_seconds')) is not int or
            not 1 <= grant['wait_seconds'] <= 600 or grant.get('full_context_hold_usd') != hold or
            grant.get('global_authority_cap_usd') != str(remaining.CAP) or
            grant.get('global_authority_approval_sha256') != remaining.APPROVAL_SHA256 or
            grant.get('smoke_review_sha256') != smoke_review_hash or
            grant.get('prior_completion_sha256') != prior_completion_hash or
            not isinstance(grant.get('global_authority_ledger_sha256_at_admission'), str) or
            len(grant['global_authority_ledger_sha256_at_admission']) != 64 or
            not isinstance(grant.get('reviewer'), str) or not grant['reviewer'].strip() or
            claim.get('kind') != 'clef-native-remaining-claim-v1' or
            claim.get('model') != MODEL or claim.get('stage') != stage or
            claim.get('grant_sha256') != sources.hashes[str(grant_path)] or
            claim.get('manifest_sha256') != manifest_hash or
            claim.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            claim.get('prior_completion_sha256') != prior_completion_hash or
            claim.get('global_authority_hold_usd') != hold or
            claim.get('charge_status') != 'unknown_reserved' or
            claim.get('account_id_sha256') != predecessor_claim.get('account_id_sha256') or
            completion.get('kind') != 'clef-native-remaining-completion-v1' or
            completion.get('model') != MODEL or completion.get('stage') != stage or
            completion.get('status') != 'complete' or completion.get('attempted') != 60 or
            completion.get('counts') != {'valid': 60, 'invalid_output': 0,
                'service_error': 0, 'unknown_outcome': 0} or completion.get('never_sent') != [] or
            completion.get('unknown_cost_reserved_usd') != hold or
            any(completion.get(key) != sources.hashes[str(directory / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            budget[0] != {'event': 'budget', 'cap_usd': hold,
                'grant_sha256': sources.hashes[str(grant_path)],
                'manifest_sha256': manifest_hash, 'stage': stage} or
            len(budget) != 61 or len(journal) != 180 or len(raw) != 60 or len(records) != 60):
        raise ValueError('Incomplete or unbound P2 development completion')
    entries, elapsed = [], 0.0
    for index, rid in enumerate(first.IDS):
        plan = planned[index]
        reserve, started, finished = journal[3*index:3*index+3]
        raw_row, record = raw[index], records[index]
        attempt = reserve.get('attempt_id')
        request_hash = plan['payload_sha256']
        per_request = str(prep.reservation_usd(MODEL, 1))
        bridge_dir = directory / 'app-bridge'
        paths = {name: bridge_dir / f'{attempt}.{name}.json'
                 for name in ('request', 'dispatch', 'tool-result', 'app-result', 'response')}
        ready, dispatch, tool, app, reply = (sources.json(paths[name]) for name in paths)
        app_bytes = sources.path(paths['app-result']).read_bytes()
        seconds = raw_row.get('client_seconds')
        if (plan['id'] != rid or reserve != {'event': 'reserved', 'attempt_id': attempt,
                'id': rid, 'request_sha256': request_hash, 'usd': per_request} or
                started != {'event': 'started', 'attempt_id': attempt, 'id': rid} or
                finished != {'event': 'finished', 'attempt_id': attempt, 'id': rid, 'status': 'valid'} or
                budget[index+1] != {'event': 'reserve', 'stage': stage,
                    'attempt_id': attempt, 'id': rid, 'usd': per_request} or
                ready.get('kind') != bridge.KIND + '-request' or ready.get('attempt_id') != attempt or
                ready.get('id') != rid or ready.get('model') != MODEL or ready.get('stage') != stage or
                ready.get('review_sha256') != sources.hashes[str(grant_path)] or
                ready.get('account_id_sha256') != claim.get('account_id_sha256') or
                ready.get('request_sha256') != request_hash or ready.get('method') != 'POST' or
                ready.get('path') != '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[MODEL]['route'] or
                prep.sha(prep.canonical(ready.get('body'))) != request_hash or
                dispatch.get('request_sha256') != request_hash or
                not isinstance(dispatch.get('operator'), str) or not dispatch['operator'] or
                tool.get('isError') is not False or len(tool.get('content', [])) != 1 or
                tool['content'][0].get('type') != 'text' or json.loads(tool['content'][0]['text']) != app or
                app.get('status') != 200 or app.get('success') is not True or app.get('errors') != [] or
                app.get('result', {}).get('model') != MODEL or
                reply != {'kind': bridge.KIND + '-response', 'attempt_id': attempt,
                    'request_sha256': request_hash, 'http_status': 200,
                    'body_base64': base64.b64encode(app_bytes).decode('ascii')} or
                raw_row.get('attempt_id') != attempt or raw_row.get('id') != rid or
                raw_row.get('request_sha256') != request_hash or raw_row.get('http_status') != 200 or
                raw_row.get('redacted') is not False or raw_row.get('error_type') is not None or
                base64.b64decode(raw_row['raw_response_base64'], validate=True) != app_bytes or
                raw_row.get('response_sha256') != prep.sha(app_bytes) or
                record.get('attempt_id') != attempt or record.get('id') != rid or
                record.get('request_sha256') != request_hash or record.get('status') != 'valid' or
                record.get('reason') is not None or record.get('charge_status') != 'unknown_reserved' or
                record.get('reservation_usd') != per_request or record.get('reference_labels_read') is not False or
                record.get('parsed') != prep.parse_rest_response(app, MODEL) or
                record['parsed'].get('actual_charge_usd') is not None or
                type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError(f'P2 app, response, or reservation binding differs: {rid}')
        elapsed += seconds
        parsed = record['parsed']
        entries.append({'id': rid, 'reference': labels[rid], 'prediction': parsed['prediction'],
            'probabilities': parsed['probabilities'], 'confidence': parsed['confidence'],
            'usage': parsed['usage']})
    return entries, elapsed


def build(root=ROOT):
    root = Path(root)
    sources = p1.Sources(root)

    # Validate prior checkpoints using their own builders before comparing them.
    saved_p1 = sources.json(P1_OUTPUT)
    old_condition = p1.CONDITION
    p1.CONDITION = 'P1'
    try:
        current_p1 = p1.build(root)
    finally:
        p1.CONDITION = old_condition
    if saved_p1 != current_p1:
        raise ValueError('Saved P1 findings differ from its source evidence')
    p0_report = first.build(root)
    if p0_report != sources.json(first.OUTPUT):
        raise ValueError('Saved P0 findings differ from its source evidence')

    for relative in ('scripts/build_clef_findings.py',
                     'scripts/build_clef_flash_p1_findings.py',
                     'scripts/build_clef_flash_p2_findings.py',
                     'scripts/clef_native_preparation.py',
                     'scripts/clef_native_remaining.py',
                     'scripts/clef_connected_app_bridge.py',
                     'scripts/jev_benchmark.py',
                     'scripts/jev_native_prompt_variants_v1.py',
                     'results/clef-native-v1/preparation.json', PROPOSAL,
                     BASE / 'clef-flash-billing-source.md'):
        sources.path(relative)
    manifest = sources.json(MANIFEST)
    if manifest != remaining.manifest_value(root, root / PROPOSAL):
        raise ValueError('Remaining-stage manifest differs from frozen inputs')
    p2_plan = manifest['stages'][f'{MODEL}/{PASS}/{CONDITION}']
    if (p2_plan.get('route') != prep.MODELS[MODEL]['route'] or
            len(p2_plan.get('requests', [])) != 60):
        raise ValueError('P2 model route or request membership differs')
    billing_path = BASE / 'clef-flash-billing-source.md'
    if sources.hashes[str(billing_path)] != manifest['billing_source_sha256'][MODEL]:
        raise ValueError('Saved Clef Flash billing source differs from frozen rate hash')

    label_path = sources.path(first.LABELS)
    if sources.hashes[str(first.LABELS)] != first.LABELS_SHA256:
        raise ValueError('Frozen reference labels changed')
    label_rows = [json.loads(line) for line in label_path.read_bytes().splitlines()]
    if ([row.get('id') for row in label_rows] != list(first.IDS) or
            any(row.get('review_version') != '0.2' or
                not first.valid(row.get('proposed_labels')) for row in label_rows)):
        raise ValueError('Reference membership or schema differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}

    p0_dir = BASE / MODEL / 'fresh1/P0/development'
    p1_dir = BASE / MODEL / 'fresh1/P1/development'
    p2_dir = BASE / MODEL / 'fresh1/P2/development'
    p0_claim = sources.json(p0_dir / 'claim.json')
    p0_entries = p1.project_records(sources.rows(p0_dir / 'records.jsonl'), labels)
    p1_entries = p1.project_records(sources.rows(p1_dir / 'records.jsonl'), labels)

    p2_fresh1_entries, fresh1_elapsed = validate_stage(
        sources, manifest, labels, p0_claim, 'fresh1', None)
    fresh1_completion_hash = sources.hashes[str(p2_dir / 'completion.json')]
    p2_fresh2_entries, fresh2_elapsed = validate_stage(
        sources, manifest, labels, p0_claim, 'fresh2', fresh1_completion_hash)
    fresh2_completion_hash = sources.hashes[str(BASE / MODEL / 'fresh2/P2/development/completion.json')]
    p2_fresh3_entries, fresh3_elapsed = validate_stage(
        sources, manifest, labels, p0_claim, 'fresh3', fresh2_completion_hash)

    if ([row['id'] for row in p0_entries] != [row['id'] for row in p1_entries] or
            [row['id'] for row in p1_entries] != [row['id'] for row in p2_fresh1_entries] or
            [row['id'] for row in p2_fresh1_entries] !=
            [row['id'] for row in p2_fresh2_entries] or
            [row['id'] for row in p2_fresh2_entries] != [row['id'] for row in p2_fresh3_entries]):
        raise ValueError('P0/P1/P2 comparison membership differs')
    p0_manifest = sources.json(BASE / 'full-p0-manifest-v1.json')
    p1_manifest = sources.json(MANIFEST)
    p0_requests = p0_manifest['models'][MODEL]['requests']
    p1_requests = p1_manifest['stages'][f'{MODEL}/fresh1/P1']['requests']
    p2_requests = p1_manifest['stages'][f'{MODEL}/fresh1/P2']['requests']
    for prior_requests in (p0_requests, p1_requests):
        if ([r['id'] for r in prior_requests] != [r['id'] for r in p2_requests] or
                [r['input_sha256'] for r in prior_requests] !=
                [r['input_sha256'] for r in p2_requests] or
                [r['payload_sha256'] for r in prior_requests] ==
                [r['payload_sha256'] for r in p2_requests]):
            raise ValueError('P2 does not have the same inputs and a distinct prompt payload')

    def phase(repeat, entries, elapsed):
        field_metrics = {field: first.field_metrics(entries, field) for field in prep.KEYS}
        all_correct = sum(all(row['prediction'][field] == row['reference'][field]
                              for field in prep.KEYS) for row in entries)
        input_tokens = sum(row['usage']['input_tokens'] for row in entries)
        output_tokens = sum(row['usage'].get('output_tokens', 0) for row in entries)
        return {'stage': f'{MODEL}/{repeat}/{CONDITION}/development', 'attempted': 60,
            'counts': {'valid': 60, 'invalidOutput': 0, 'serviceError': 0,
                       'unknownOutcome': 0, 'neverSent': 0},
            'allFourCorrect': all_correct, 'allFourDenominator': 60,
            'allFourAccuracy': round(all_correct / 60, 6), 'fields': field_metrics,
            'observedInputTokens': input_tokens, 'observedOutputTokens': output_tokens,
            'clientElapsedSeconds': round(elapsed, 6)}

    fresh1_phase = phase('fresh1', p2_fresh1_entries, fresh1_elapsed)
    fresh2_phase = phase('fresh2', p2_fresh2_entries, fresh2_elapsed)
    fresh3_phase = phase('fresh3', p2_fresh3_entries, fresh3_elapsed)
    price = prep.MODELS[MODEL]['input_usd_per_million']
    p1_comparison = p1.compare(p1_entries, p2_fresh1_entries, 'fresh1/P1', 'fresh1/P2',
        'Matched prompt-condition comparison on the same 60 records; descriptive.')

    return {
        'schema': 'clef-flash-p2-findings-v1',
        'referenceStatus': saved_p1['referenceStatus'],
        'configuration': {'model': MODEL, 'route': prep.MODELS[MODEL]['route'],
            'pass': PASS, 'condition': CONDITION,
            'contextTokens': prep.CONTEXT_TOKENS,
            'transport': 'Cloudflare connected app', 'referenceLabelsSent': False},
        'phase': fresh1_phase,
        'phaseByPass': {'fresh1': fresh1_phase, 'fresh2': fresh2_phase,
                        'fresh3': fresh3_phase},
        'controls': {'sharedValid': 60,
            'sameModelAndRoute': True,
            'sameOrderedInputsAndReferences': True,
            'sameNativeChoiceInterface': True,
            'sameConnectedAppTransport': True,
            'declaredPromptConditionDiffers': True,
            'matchedFresh1P0': p1.compare(p0_entries, p2_fresh1_entries,
                'fresh1/P0', 'fresh1/P2',
                'Matched prompt-condition comparison on the same 60 records; descriptive.'),
            'matchedFresh1P1': p1_comparison,
            'p2Repeatability': p1.compare(p2_fresh1_entries, p2_fresh2_entries,
                'fresh1/P2', 'fresh2/P2',
                'Separately dispatched P2 passes on the same 60 records; pairwise comparisons are descriptive.'),
            'p2Fresh1Fresh3': p1.compare(p2_fresh1_entries, p2_fresh3_entries,
                'fresh1/P2', 'fresh3/P2',
                'Pairwise comparison across separately dispatched P2 passes; descriptive.'),
            'p2Fresh2Fresh3': p1.compare(p2_fresh2_entries, p2_fresh3_entries,
                'fresh2/P2', 'fresh3/P2',
                'Pairwise comparison across separately dispatched P2 passes; descriptive.'),
            'requiredFullPassesPerCondition': 3, 'fullPassesCompleted': 3},
        'cost': {'publishedInputUsdPerMillion': str(price),
            'publishedInputPriceEstimateUsd': str(
                Decimal(fresh1_phase['observedInputTokens']) * price / Decimal(1_000_000)),
            'publishedInputPriceEstimateUsdByPass': {
                'fresh1': str(Decimal(fresh1_phase['observedInputTokens']) * price / Decimal(1_000_000)),
                'fresh2': str(Decimal(fresh2_phase['observedInputTokens']) * price / Decimal(1_000_000)),
                'fresh3': str(Decimal(fresh3_phase['observedInputTokens']) * price / Decimal(1_000_000))},
            'fullContextUnknownChargeHoldUsd': str(prep.reservation_usd(MODEL, 60)),
            'providerBilledUsd': None,
            'note': 'The token-price estimate is not a provider bill. The full-context hold is a reservation bound.'},
        'timing': {'inferenceLatencyAvailable': False,
            'includesConnectedAppHandoff': True,
            'note': 'Client elapsed seconds include connected-app operator handoff and do not measure pure inference latency.'},
        'sourceSha256': sources.hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    payload = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    target = ROOT / OUTPUT
    if args.check:
        if target.read_text() != payload:
            raise ValueError('Saved Clef Flash P2 projection differs from current evidence')
    else:
        target.write_text(payload)
    print(target)


if __name__ == '__main__':
    main()
