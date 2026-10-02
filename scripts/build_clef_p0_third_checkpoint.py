#!/usr/bin/env python3
"""Build a source-bound Clef fresh3/P0 checkpoint without altering earlier cutoffs."""

import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path

import build_clef_findings as first
import build_clef_p0_repeat_findings as second
import clef_connected_app_bridge as bridge
import clef_native_preparation as prep
import clef_native_remaining as remaining

ROOT = first.ROOT
BASE = first.BASE
OUTPUT = Path('public-site/clef-p0-third-checkpoint.json')
MANIFEST = BASE / 'repeat-continuation-v1/remaining-admission-v1.json'
SECOND_FEED = second.OUTPUT
IDS = first.IDS
MODELS = first.MODELS


def stage(sources, manifest, model, labels):
    directory = BASE / model / 'fresh3/P0/development'
    smoke_dir = BASE / model / 'fresh3/P0/smoke'
    grant_path = BASE / f'repeat-continuation-v1/remaining-grants/{model}-fresh3-p0-development-grant.json'
    review_path = smoke_dir / 'smoke-review.json'
    smoke_claim = sources.json(smoke_dir / 'claim.json')
    smoke_done = sources.json(smoke_dir / 'completion.json')
    for name in ('budget.jsonl', 'journal.jsonl', 'raw.jsonl', 'records.jsonl'):
        sources.path(smoke_dir / name)
    review = sources.json(review_path)
    grant = sources.json(grant_path)
    claim = sources.json(directory / 'claim.json')
    done = sources.json(directory / 'completion.json')
    budget = sources.rows(directory / 'budget.jsonl')
    journal = sources.rows(directory / 'journal.jsonl')
    raw = sources.rows(directory / 'raw.jsonl')
    records = sources.rows(directory / 'records.jsonl')
    stage_name = remaining.stage_name(model, 'fresh3', 'P0', 'development')
    smoke_name = remaining.stage_name(model, 'fresh3', 'P0', 'smoke')
    manifest_hash = sources.hashes[str(MANIFEST)]
    grant_hash = sources.hashes[str(grant_path)]
    prior_path = BASE / model / 'fresh2/P0/development/completion.json'
    sources.path(prior_path)
    prior_hash = sources.hashes[str(prior_path)]
    planned = manifest['stages'][f'{model}/fresh3/P0']['requests']
    attempted = 60 if model == 'clef' else 1
    counts = ({'valid': 60, 'invalid_output': 0, 'service_error': 0, 'unknown_outcome': 0}
              if model == 'clef' else
              {'valid': 0, 'invalid_output': 0, 'service_error': 0, 'unknown_outcome': 1})
    if (smoke_claim.get('kind') != 'clef-native-remaining-claim-v1' or
            smoke_claim.get('model') != model or smoke_claim.get('stage') != smoke_name or
            smoke_claim.get('manifest_sha256') != manifest_hash or
            smoke_claim.get('account_id_sha256') != claim.get('account_id_sha256') or
            smoke_done.get('kind') != 'clef-native-remaining-completion-v1' or
            smoke_done.get('stage') != smoke_name or smoke_done.get('status') != 'complete' or
            smoke_done.get('attempted') != 3 or
            smoke_done.get('counts') != {'valid': 3, 'invalid_output': 0,
                'service_error': 0, 'unknown_outcome': 0} or
            smoke_done.get('never_sent') != [] or
            any(smoke_done.get(key) != sources.hashes[str(smoke_dir / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            review.get('kind') != remaining.INSPECTION_KIND or
            review.get('approved') is not True or review.get('model') != model or
            review.get('stage') != smoke_name or
            review.get('manifest_sha256') != manifest_hash or
            review.get('completion_sha256') != sources.hashes[str(smoke_dir / 'completion.json')] or
            review.get('records_sha256') != sources.hashes[str(smoke_dir / 'records.jsonl')] or
            review.get('raw_sha256') != sources.hashes[str(smoke_dir / 'raw.jsonl')] or
            review.get('decision') != 'admit_unchanged_full_stage' or
            grant.get('kind') != remaining.GRANT_KIND or grant.get('approved') is not True or
            grant.get('authorized_by_user') is not True or grant.get('model') != model or
            grant.get('stage') != stage_name or grant.get('pass') != 'fresh3' or
            grant.get('condition') != 'P0' or grant.get('phase') != 'development' or
            grant.get('manifest_sha256') != manifest_hash or
            grant.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            grant.get('smoke_review_sha256') != sources.hashes[str(review_path)] or
            grant.get('prior_completion_sha256') != prior_hash or
            grant.get('billing_source_sha256') != manifest['billing_source_sha256'][model] or
            grant.get('account_id_sha256') != claim.get('account_id_sha256') or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            grant.get('full_context_hold_usd') != str(prep.reservation_usd(model, 60)) or
            grant.get('global_authority_cap_usd') != str(remaining.CAP) or
            grant.get('global_authority_approval_sha256') != remaining.APPROVAL_SHA256 or
            claim.get('kind') != 'clef-native-remaining-claim-v1' or
            claim.get('model') != model or claim.get('stage') != stage_name or
            claim.get('manifest_sha256') != manifest_hash or
            claim.get('grant_sha256') != grant_hash or
            claim.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            claim.get('prior_completion_sha256') != prior_hash or
            claim.get('global_authority_hold_usd') != str(prep.reservation_usd(model, 60)) or
            claim.get('charge_status') != 'unknown_reserved' or
            done.get('kind') != 'clef-native-remaining-completion-v1' or
            done.get('model') != model or done.get('stage') != stage_name or
            done.get('status') != ('complete' if model == 'clef' else 'stopped') or
            done.get('attempted') != attempted or done.get('counts') != counts or
            done.get('never_sent') != list(IDS[attempted:]) or
            done.get('unknown_cost_reserved_usd') != str(prep.reservation_usd(model, attempted)) or
            any(done.get(key) != sources.hashes[str(directory / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            budget[0] != {'event': 'budget', 'cap_usd': str(prep.reservation_usd(model, 60)),
                'stage': stage_name, 'manifest_sha256': manifest_hash,
                'grant_sha256': grant_hash} or
            len(budget) != 1 + attempted or len(journal) != 3 * attempted or
            len(raw) != attempted or len(records) != attempted):
        raise ValueError(f'Incomplete or unbound Clef fresh3 stage: {model}')
    entries = []
    client_seconds = 0.0
    for index in range(attempted):
        rid = IDS[index]
        request_hash = planned[index]['payload_sha256']
        reserve, started, finished = journal[3 * index:3 * index + 3]
        raw_row, record = raw[index], records[index]
        attempt = reserve.get('attempt_id')
        outcome = 'valid' if model == 'clef' else 'unknown_outcome'
        usd = str(prep.reservation_usd(model, 1))
        if (planned[index]['id'] != rid or
                reserve != {'event': 'reserved', 'attempt_id': attempt,
                    'id': rid, 'request_sha256': request_hash, 'usd': usd} or
                started != {'event': 'started', 'attempt_id': attempt, 'id': rid} or
                finished != {'event': 'finished', 'attempt_id': attempt,
                    'id': rid, 'status': outcome} or
                budget[index + 1] != {'event': 'reserve', 'stage': stage_name,
                    'attempt_id': attempt, 'id': rid, 'usd': usd}):
            raise ValueError(f'Fresh3 request/reservation order differs: {model}/{rid}')
        bridge_dir = directory / 'app-bridge'
        paths = {name: bridge_dir / f'{attempt}.{name}.json'
                 for name in ('request', 'dispatch', 'tool-result', 'app-result')}
        ready, dispatch, tool = (sources.json(paths[name])
                                 for name in ('request', 'dispatch', 'tool-result'))
        app_bytes = sources.path(paths['app-result']).read_bytes()
        if (ready.get('kind') != bridge.KIND + '-request' or
                ready.get('attempt_id') != attempt or ready.get('id') != rid or
                ready.get('model') != model or ready.get('stage') != stage_name or
                ready.get('review_sha256') != grant_hash or
                ready.get('account_id_sha256') != claim['account_id_sha256'] or
                ready.get('request_sha256') != request_hash or
                ready.get('method') != 'POST' or
                ready.get('path') != '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[model]['route'] or
                prep.sha(prep.canonical(ready.get('body'))) != request_hash or
                dispatch.get('request_sha256') != request_hash or
                not isinstance(dispatch.get('operator'), str) or not dispatch['operator'] or
                len(tool.get('content', [])) != 1 or tool['content'][0].get('type') != 'text' or
                raw_row.get('attempt_id') != attempt or raw_row.get('id') != rid or
                raw_row.get('request_sha256') != request_hash or
                raw_row.get('redacted') is not False or
                raw_row.get('response_sha256') != prep.sha(base64.b64decode(
                    raw_row['raw_response_base64'], validate=True)) or
                record.get('attempt_id') != attempt or record.get('id') != rid or
                record.get('request_sha256') != request_hash or
                record.get('status') != outcome or
                record.get('charge_status') != 'unknown_reserved' or
                record.get('reservation_usd') != usd or
                record.get('reference_labels_read') is not False):
            raise ValueError(f'Fresh3 app/record binding differs: {model}/{rid}')
        seconds = raw_row.get('client_seconds')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Invalid client elapsed seconds')
        client_seconds += seconds
        if model == 'clef':
            reply_path = bridge_dir / f'{attempt}.response.json'
            reply = sources.json(reply_path)
            app = json.loads(app_bytes)
            parsed = prep.parse_rest_response(app, model)
            if (tool.get('isError') is not False or
                    json.loads(tool['content'][0]['text']) != app or
                    app.get('success') is not True or app.get('status') != 200 or
                    app.get('errors') != [] or app.get('result', {}).get('model') != model or
                    reply != {'kind': bridge.KIND + '-response',
                        'attempt_id': attempt, 'request_sha256': request_hash,
                        'http_status': 200,
                        'body_base64': base64.b64encode(app_bytes).decode('ascii')} or
                    raw_row.get('http_status') != 200 or
                    raw_row.get('error_type') is not None or
                    base64.b64decode(raw_row['raw_response_base64'], validate=True) != app_bytes or
                    record.get('reason') is not None or record.get('parsed') != parsed or
                    parsed.get('actual_charge_usd') is not None):
                raise ValueError(f'Fresh3 valid response differs: {rid}')
            entries.append({'id': rid, 'reference': labels[rid],
                'prediction': parsed['prediction'], 'probabilities': parsed['probabilities'],
                'confidence': parsed['confidence'], 'usage': parsed['usage']})
        else:
            tool_text = tool['content'][0]['text']
            audit_path = directory / 'external-error-audit.json'
            audit = sources.json(audit_path)
            if (tool.get('isError') is not True or
                    not isinstance(tool_text, str) or
                    '4006' not in tool_text or 'free allocation' not in tool_text.lower() or
                    app_bytes.strip() != tool_text.encode().strip() or
                    (bridge_dir / f'{attempt}.response.json').exists() or
                    raw_row.get('http_status') is not None or
                    raw_row.get('error_type') != 'TimeoutError' or
                    base64.b64decode(raw_row['raw_response_base64'], validate=True) != b'' or
                    record.get('reason') != 'transport_outcome_unknown' or
                    record.get('parsed') is not None or
                    audit.get('kind') != 'clef-native-connected-app-external-error-audit-v1' or
                    audit.get('stage') != stage_name or audit.get('id') != rid or
                    audit.get('attempt_id') != attempt or audit.get('no_replay') is not True or
                    audit.get('error_code_observed') != '4006' or
                    audit.get('outer_tool_is_error') is not True or
                    audit.get('provider_envelope_available') is not False or
                    audit.get('provider_http_status') is not None or
                    audit.get('charge_status') != 'unknown_reserved' or
                    audit.get('request_sha256') != sources.hashes[str(paths['request'])] or
                    audit.get('dispatch_sha256') != sources.hashes[str(paths['dispatch'])] or
                    audit.get('outer_tool_result_sha256') != sources.hashes[str(paths['tool-result'])] or
                    audit.get('app_result_sha256') != sources.hashes[str(paths['app-result'])] or
                    audit.get('completion_sha256') != sources.hashes[str(directory / 'completion.json')]):
                raise ValueError('Flash unknown result or retained connector error differs')
    return entries, client_seconds


def build(root=ROOT):
    root = Path(root)
    previous = second.build(root)
    sources = first.Sources(root)
    if sources.json(SECOND_FEED) != previous:
        raise ValueError('Frozen two-pass public cutoff differs from evidence')
    for name in ('scripts/build_clef_p0_third_checkpoint.py',
                 'scripts/clef_native_remaining.py', 'scripts/clef_native_preparation.py',
                 'scripts/clef_connected_app_bridge.py',
                 'results/clef-native-v1/repeat-continuation-v1/proposed-manifest.json',
                 'results/clef-native-v1/preparation.json',
                 'results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl'):
        sources.path(name)
    manifest = sources.json(MANIFEST)
    if manifest != remaining.manifest_value(root, root / BASE / 'repeat-continuation-v1/proposed-manifest.json'):
        raise ValueError('Fresh3 admission differs from frozen inputs')
    labels_path = sources.path(first.LABELS)
    if sources.hashes[str(first.LABELS)] != first.LABELS_SHA256:
        raise ValueError('Frozen reference labels changed')
    labels = {row['id']: row['proposed_labels'] for row in
              (json.loads(line) for line in labels_path.read_bytes().splitlines())}
    models = {}
    for model in MODELS:
        stage_plan = manifest['stages'][f'{model}/fresh3/P0']
        earlier = sources.json(BASE / 'repeat-continuation-v1/fresh2-p0-admission-v1.json')
        prior_completion_path = BASE / model / 'fresh2/P0/development/completion.json'
        sources.path(prior_completion_path)
        if (stage_plan['model'] != model or stage_plan['pass'] != 'fresh3' or
                stage_plan['condition'] != 'P0' or
                stage_plan['route'] != prep.MODELS[model]['route'] or
                stage_plan['requests'] != earlier['models'][model]['requests'] or
                manifest['closed_fresh2_p0_completion_sha256'][model] !=
                    sources.hashes[str(prior_completion_path)]):
            raise ValueError('Fresh3 route, request controls, or predecessor differ')
        entries, seconds = stage(sources, manifest, model, labels)
        if model == 'clef':
            prior = previous['models'][model]
            first_rows = sources.rows(BASE / model / 'fresh1/P0/development/records.jsonl')
            second_rows = sources.rows(BASE / model / 'fresh2/P0/development/records.jsonl')
            def projected(rows):
                return [{'id': row['id'], 'reference': labels[row['id']],
                         'prediction': row['parsed']['prediction'],
                         'probabilities': row['parsed']['probabilities'],
                         'confidence': row['parsed']['confidence'],
                         'usage': row['parsed']['usage']} for row in rows]
            prior_entries = {"fresh1": projected(first_rows), "fresh2": projected(second_rows)}
            scores = {field: first.field_metrics(entries, field) for field in prep.KEYS}
            all_four = sum(all(row['prediction'][field] == row['reference'][field]
                               for field in prep.KEYS) for row in entries)
            input_tokens = sum(row['usage']['input_tokens'] for row in entries)
            output_tokens = sum(row['usage'].get('output_tokens', 0) for row in entries)
            models[model] = {'status': 'complete', 'scoredCellsOfNine': 3,
                'fresh3P0': {'attempted': 60, 'valid': 60, 'failed': 0,
                    'neverSent': 0, 'allFourCorrect': all_four, 'denominator': 60,
                    'fields': scores, 'observedInputTokens': input_tokens,
                    'observedOutputTokens': output_tokens,
                    'publishedInputPriceEstimateUsd': str(Decimal(input_tokens) *
                        prep.MODELS[model]['input_usd_per_million'] / Decimal(1_000_000)),
                    'fullContextUnknownChargeHoldUsd': str(prep.reservation_usd(model, 60)),
                    'providerBilledUsd': None,
                    'clientElapsedSeconds': round(seconds, 6)},
                'p0AllFourByPass': {'fresh1': prior['fresh1']['allFourCorrect'],
                    'fresh2': prior['fresh2']['allFourCorrect'], 'fresh3': all_four},
                'sharedValidThreePassDenominator': 60,
                'threePassPredictionChangedIds': [row['id'] for index, row in enumerate(entries)
                    if any(row['prediction'] != prior_entries[name][index]['prediction']
                           for name in ('fresh1', 'fresh2'))],
                'fresh2ToFresh3': second.paired(prior_entries['fresh2'], entries),
                'fresh1ToFresh3': second.paired(prior_entries['fresh1'], entries),
                'nativeDistributionChangedIds': [row['id'] for index, row in enumerate(entries)
                    if any(row['probabilities'] != prior_entries[name][index]['probabilities']
                           for name in ('fresh1', 'fresh2'))],
                'vendorConfidenceChangedIds': [row['id'] for index, row in enumerate(entries)
                    if any(row['confidence'] != prior_entries[name][index]['confidence']
                           for name in ('fresh1', 'fresh2'))]}
        else:
            models[model] = {'status': 'stopped_unknown_outcome', 'scoredCellsOfNine': 2,
                'fresh3P0': {'attempted': 1, 'valid': 0, 'unknownOutcomeIds': ['DEV-001'],
                    'neverSentIds': list(IDS[1:]), 'score': None,
                    'fullContextUnknownChargeHoldUsd': str(prep.reservation_usd(model, 60)),
                    'attemptUnknownChargeUpperBoundUsd': str(prep.reservation_usd(model, 1)),
                    'providerBilledUsd': None,
                    'clientElapsedSeconds': round(seconds, 6),
                    'externalConnectorError': True,
                    'providerEnvelopeAvailable': False},
                'p0AllFourByPass': {'fresh1': previous['models'][model]['fresh1']['allFourCorrect'],
                    'fresh2': previous['models'][model]['fresh2']['allFourCorrect'],
                    'fresh3': None},
                'sharedValidThreePassDenominator': 0,
                'threePassPredictionChangedIds': None}
    return {'schema': 'clef-native-p0-third-checkpoint-v1',
        'referenceStatus': previous['referenceStatus'],
        'cohort': {'records': 60, 'condition': 'P0', 'plannedCellsPerModel': 9,
                   'thirdPassStatus': 'clef_complete_flash_stopped',
                   'otherConditionsCompleted': False},
        'priorTwoPassSource': str(SECOND_FEED), 'models': models,
        'definitions': {'score': 'Agreement against the frozen provisional v0.2 key on all 60 development records.',
            'unknownOutcome': 'The Flash connector returned an external error; the bounded handoff ended without a saved inference response. DEV-001 remains unknown and was not retried.',
            'nativeProbability': 'Native choice distributions are compared separately from provider confidence.',
            'cost': 'Full-context holds bound possible cost; observed-token price estimates are not provider bills.',
            'timing': 'Client elapsed time includes connected-app operator handoff, not just model inference.'},
        'sourceSha256': {**previous['sourceSha256'], **sources.hashes}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    payload = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    target = ROOT / OUTPUT
    if args.check:
        if target.read_text() != payload:
            raise ValueError('Saved Clef third-P0 checkpoint differs from evidence')
    else:
        target.write_text(payload)
    print(target)


if __name__ == '__main__':
    main()
