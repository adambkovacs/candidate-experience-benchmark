#!/usr/bin/env python3
"""Build an offline, source-bound Clef Flash P1 checkpoint projection."""

import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path

import build_clef_findings as first
import clef_connected_app_bridge as bridge
import clef_native_full_p0 as full_p0
import clef_native_preparation as prep
import clef_native_remaining as remaining

ROOT = first.ROOT
BASE = Path('results/clef-native-v1')
MANIFEST = BASE / 'repeat-continuation-v1/remaining-admission-v1.json'
PROPOSAL = BASE / 'repeat-continuation-v1/proposed-manifest.json'
P0_MANIFEST = BASE / 'full-p0-manifest-v1.json'
P0_REPORT = first.OUTPUT
OUTPUT = Path('results/clef-native-v1/clef-flash-p1-findings-public.json')
MODEL = 'clef-flash'
PASS = 'fresh1'
CONDITION = 'P1'
STAGE = f'{MODEL}/{PASS}/{CONDITION}/development'
IDS = first.IDS


class Sources(first.Sources):
    """Hash each consumed source while parsing it."""


def project_records(records, labels):
    if [row.get('id') for row in records] != list(IDS):
        raise ValueError('Record IDs or order differ from frozen 60-record cohort')
    projected = []
    for row in records:
        parsed = row.get('parsed')
        if not isinstance(parsed, dict):
            raise ValueError('Missing parsed valid response')
        projected.append({'id': row['id'], 'reference': labels[row['id']],
                          'prediction': parsed['prediction'],
                          'probabilities': parsed['probabilities'],
                          'confidence': parsed['confidence'],
                          'usage': parsed['usage']})
    return projected


def validate_smoke(sources, manifest, claim, grant, directory, repeat):
    smoke_dir = directory.parent / 'smoke'
    claim_path = smoke_dir / 'claim.json'
    completion_path = smoke_dir / 'completion.json'
    review_path = smoke_dir / 'root-smoke-review.json'
    smoke_claim = sources.json(claim_path)
    completion = sources.json(completion_path)
    review = sources.json(review_path)
    budget = sources.rows(smoke_dir / 'budget.jsonl')
    journal = sources.rows(smoke_dir / 'journal.jsonl')
    raw = sources.rows(smoke_dir / 'raw.jsonl')
    records = sources.rows(smoke_dir / 'records.jsonl')
    manifest_hash = sources.hashes[str(MANIFEST)]
    smoke_grant_path = BASE / f'repeat-continuation-v1/remaining-grants/clef-flash-{repeat}-p1-smoke-grant.json'
    smoke_grant = sources.json(smoke_grant_path)
    smoke_stage = f'{MODEL}/{repeat}/{CONDITION}/smoke'
    prior_completion_hash = remaining.predecessor_hash(
        MODEL, repeat, CONDITION, manifest_hash, base=sources.root / BASE)
    planned = manifest['stages'][f'{MODEL}/{repeat}/{CONDITION}']['requests']
    if (smoke_claim.get('kind') != 'clef-native-remaining-claim-v1' or
            smoke_claim.get('model') != MODEL or smoke_claim.get('stage') != smoke_stage or
            smoke_claim.get('manifest_sha256') != manifest_hash or
            smoke_claim.get('prior_completion_sha256') != prior_completion_hash or
            smoke_claim.get('account_id_sha256') != claim.get('account_id_sha256') or
            smoke_claim.get('grant_sha256') != sources.hashes[str(smoke_grant_path)] or
            completion.get('kind') != 'clef-native-remaining-completion-v1' or
            completion.get('model') != MODEL or completion.get('stage') != smoke_stage or
            completion.get('status') != 'complete' or completion.get('attempted') != 3 or
            completion.get('counts') != {'valid': 3, 'invalid_output': 0,
                'service_error': 0, 'unknown_outcome': 0} or completion.get('never_sent') != [] or
            any(completion.get(key) != sources.hashes[str(smoke_dir / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            review.get('kind') != remaining.INSPECTION_KIND or
            review.get('approved') is not True or review.get('model') != MODEL or
            review.get('stage') != smoke_stage or review.get('manifest_sha256') != manifest_hash or
            review.get('completion_sha256') != sources.hashes[str(completion_path)] or
            review.get('records_sha256') != sources.hashes[str(smoke_dir / 'records.jsonl')] or
            review.get('raw_sha256') != sources.hashes[str(smoke_dir / 'raw.jsonl')] or
            review.get('decision') != 'admit_unchanged_full_stage' or
            not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip() or
            smoke_grant.get('kind') != remaining.GRANT_KIND or
            smoke_grant.get('approved') is not True or
            smoke_grant.get('authorized_by_user') is not True or
            smoke_grant.get('model') != MODEL or smoke_grant.get('stage') != smoke_stage or
            smoke_grant.get('pass') != repeat or smoke_grant.get('condition') != CONDITION or
            smoke_grant.get('phase') != 'smoke' or
            smoke_grant.get('manifest_sha256') != manifest_hash or
            smoke_grant.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            smoke_grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            smoke_grant.get('billing_source_sha256') != manifest['billing_source_sha256'][MODEL] or
            smoke_grant.get('account_id_sha256') != claim.get('account_id_sha256') or
            smoke_grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            smoke_grant.get('global_authority_cap_usd') != str(remaining.CAP) or
            smoke_grant.get('global_authority_approval_sha256') != remaining.APPROVAL_SHA256 or
            smoke_grant.get('exhaustion_policy') != 'pause' or
            type(smoke_grant.get('wait_seconds')) is not int or
            not 1 <= smoke_grant['wait_seconds'] <= 600 or
            smoke_grant.get('prior_completion_sha256') != prior_completion_hash or
            smoke_grant.get('full_context_hold_usd') != str(prep.reservation_usd(MODEL, 3)) or
            smoke_grant.get('smoke_review_sha256') is not None or
            not isinstance(smoke_grant.get('global_authority_ledger_sha256_at_admission'), str) or
            not isinstance(smoke_grant.get('reviewer'), str) or not smoke_grant['reviewer'].strip() or
            budget[0] != {'event': 'budget', 'stage': smoke_stage,
                'cap_usd': str(prep.reservation_usd(MODEL, 3)),
                'manifest_sha256': manifest_hash,
                'grant_sha256': sources.hashes[str(smoke_grant_path)]} or
            len(budget) != 4 or len(journal) != 9 or len(raw) != 3 or len(records) != 3):
        raise ValueError('Incomplete or unbound P1 smoke evidence')
    for index, rid in enumerate(prep.SMOKE_IDS):
        plan = planned[index]
        record = records[index]
        if (plan['id'] != rid or record.get('id') != rid or
                record.get('status') != 'valid' or
                record.get('reference_labels_read') is not False or
                record.get('request_sha256') != plan['payload_sha256']):
            raise ValueError('P1 smoke record differs from frozen requests')
    return sources.hashes[str(review_path)]


def validate_stage(sources, manifest, labels, p0_claim, repeat, prior_completion_hash):
    directory = BASE / MODEL / repeat / CONDITION / 'development'
    stage = f'{MODEL}/{repeat}/{CONDITION}/development'
    grant_path = BASE / f'repeat-continuation-v1/remaining-grants/clef-flash-{repeat}-p1-development-grant.json'
    grant = sources.json(grant_path)
    claim = sources.json(directory / 'claim.json')
    completion = sources.json(directory / 'completion.json')
    budget = sources.rows(directory / 'budget.jsonl')
    journal = sources.rows(directory / 'journal.jsonl')
    raw = sources.rows(directory / 'raw.jsonl')
    records = sources.rows(directory / 'records.jsonl')
    manifest_hash = sources.hashes[str(MANIFEST)]
    smoke_review_hash = validate_smoke(sources, manifest, claim, grant, directory, repeat)
    planned = manifest['stages'][f'{MODEL}/{repeat}/{CONDITION}']['requests']
    expected_counts = {'valid': 60, 'invalid_output': 0,
                       'service_error': 0, 'unknown_outcome': 0}
    if (grant.get('kind') != remaining.GRANT_KIND or grant.get('approved') is not True or
            grant.get('authorized_by_user') is not True or grant.get('model') != MODEL or
            grant.get('stage') != stage or grant.get('pass') != repeat or
            grant.get('condition') != CONDITION or grant.get('phase') != 'development' or
            grant.get('manifest_sha256') != manifest_hash or
            grant.get('controller_sha256') != sources.hashes['scripts/clef_native_remaining.py'] or
            grant.get('bridge_sha256') != sources.hashes['scripts/clef_connected_app_bridge.py'] or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            grant.get('billing_source_sha256') != manifest['billing_source_sha256'][MODEL] or
            grant.get('exhaustion_policy') != 'pause' or
            type(grant.get('wait_seconds')) is not int or
            not 1 <= grant['wait_seconds'] <= 600 or
            grant.get('full_context_hold_usd') != str(prep.reservation_usd(MODEL, 60)) or
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
            claim.get('global_authority_hold_usd') != str(prep.reservation_usd(MODEL, 60)) or
            claim.get('charge_status') != 'unknown_reserved' or
            claim.get('account_id_sha256') != p0_claim.get('account_id_sha256') or
            completion.get('kind') != 'clef-native-remaining-completion-v1' or
            completion.get('model') != MODEL or completion.get('stage') != stage or
            completion.get('status') != 'complete' or completion.get('attempted') != 60 or
            completion.get('counts') != expected_counts or completion.get('never_sent') != [] or
            completion.get('unknown_cost_reserved_usd') != str(prep.reservation_usd(MODEL, 60)) or
            any(completion.get(key) != sources.hashes[str(directory / name)]
                for name, key in [('claim.json', 'claim_sha256'),
                    ('journal.jsonl', 'journal_sha256'), ('raw.jsonl', 'raw_sha256'),
                    ('records.jsonl', 'records_sha256')]) or
            budget[0] != {'event': 'budget', 'cap_usd': str(prep.reservation_usd(MODEL, 60)),
                'grant_sha256': sources.hashes[str(grant_path)],
                'manifest_sha256': manifest_hash, 'stage': stage} or
            len(budget) != 61 or len(journal) != 180 or len(raw) != 60 or len(records) != 60):
        raise ValueError('Incomplete or unbound P1 development completion')
    entries = []
    elapsed = 0.0
    for index, rid in enumerate(IDS):
        plan = planned[index]
        reserve, started, finished = journal[3 * index:3 * index + 3]
        raw_row, record = raw[index], records[index]
        attempt = reserve.get('attempt_id')
        req_hash = plan['payload_sha256']
        per_request = str(prep.reservation_usd(MODEL, 1))
        bridge_dir = directory / 'app-bridge'
        paths = {name: bridge_dir / f'{attempt}.{name}.json'
                 for name in ('request', 'dispatch', 'tool-result', 'app-result', 'response')}
        ready, dispatch, tool, app, reply = (sources.json(paths[name]) for name in paths)
        app_bytes = sources.path(paths['app-result']).read_bytes()
        seconds = raw_row.get('client_seconds')
        if (plan['id'] != rid or
                reserve != {'event': 'reserved', 'attempt_id': attempt, 'id': rid,
                    'request_sha256': req_hash, 'usd': per_request} or
                started != {'event': 'started', 'attempt_id': attempt, 'id': rid} or
                finished != {'event': 'finished', 'attempt_id': attempt,
                    'id': rid, 'status': 'valid'} or
                budget[index + 1] != {'event': 'reserve', 'stage': stage,
                    'attempt_id': attempt, 'id': rid, 'usd': per_request} or
                ready.get('kind') != bridge.KIND + '-request' or
                ready.get('attempt_id') != attempt or ready.get('id') != rid or
                ready.get('model') != MODEL or ready.get('stage') != stage or
                ready.get('review_sha256') != sources.hashes[str(grant_path)] or
                ready.get('account_id_sha256') != claim.get('account_id_sha256') or
                ready.get('request_sha256') != req_hash or ready.get('method') != 'POST' or
                ready.get('path') != '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[MODEL]['route'] or
                prep.sha(prep.canonical(ready.get('body'))) != req_hash or
                dispatch.get('request_sha256') != req_hash or
                not isinstance(dispatch.get('operator'), str) or not dispatch['operator'] or
                tool.get('isError') is not False or len(tool.get('content', [])) != 1 or
                tool['content'][0].get('type') != 'text' or
                json.loads(tool['content'][0]['text']) != app or
                app.get('status') != 200 or app.get('success') is not True or
                app.get('errors') != [] or app.get('result', {}).get('model') != MODEL or
                reply != {'kind': bridge.KIND + '-response', 'attempt_id': attempt,
                    'request_sha256': req_hash, 'http_status': 200,
                    'body_base64': base64.b64encode(app_bytes).decode('ascii')} or
                raw_row.get('attempt_id') != attempt or raw_row.get('id') != rid or
                raw_row.get('request_sha256') != req_hash or raw_row.get('http_status') != 200 or
                raw_row.get('redacted') is not False or raw_row.get('error_type') is not None or
                base64.b64decode(raw_row['raw_response_base64'], validate=True) != app_bytes or
                raw_row.get('response_sha256') != prep.sha(app_bytes) or
                record.get('attempt_id') != attempt or record.get('id') != rid or
                record.get('request_sha256') != req_hash or record.get('status') != 'valid' or
                record.get('reason') is not None or record.get('charge_status') != 'unknown_reserved' or
                record.get('reservation_usd') != per_request or
                record.get('reference_labels_read') is not False or
                record.get('parsed') != prep.parse_rest_response(app, MODEL) or
                record['parsed'].get('actual_charge_usd') is not None or
                type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError(f'P1 app, response, or reservation binding differs: {rid}')
        elapsed += seconds
        parsed = record['parsed']
        entries.append({'id': rid, 'reference': labels[rid],
                        'prediction': parsed['prediction'],
                        'probabilities': parsed['probabilities'],
                        'confidence': parsed['confidence'], 'usage': parsed['usage']})
    return entries, elapsed


def compare(first_entries, second_entries, first_label, second_label, interpretation):
    if ([row['id'] for row in first_entries] != list(IDS) or
            [row['id'] for row in second_entries] != list(IDS)):
        raise ValueError('Comparison membership differs')
    fields = {}
    p0_all = p1_all = 0
    changed_vector = []
    all4_gain, all4_loss = [], []
    probability_changes, confidence_changes = [], []
    for a, b in zip(first_entries, second_entries):
        a_all = all(a['prediction'][f] == a['reference'][f] for f in prep.KEYS)
        b_all = all(b['prediction'][f] == b['reference'][f] for f in prep.KEYS)
        p0_all += a_all
        p1_all += b_all
        if a['prediction'] != b['prediction']:
            changed_vector.append(a['id'])
        if not a_all and b_all:
            all4_gain.append(a['id'])
        if a_all and not b_all:
            all4_loss.append(a['id'])
        if a['probabilities'] != b['probabilities']:
            probability_changes.append(a['id'])
        if a['confidence'] != b['confidence']:
            confidence_changes.append(a['id'])
    for field in prep.KEYS:
        changed, gained, lost, dist_changed, conf_changed = [], [], [], [], []
        for a, b in zip(first_entries, second_entries):
            if a['prediction'][field] != b['prediction'][field]:
                changed.append(a['id'])
            a_correct = a['prediction'][field] == a['reference'][field]
            b_correct = b['prediction'][field] == b['reference'][field]
            if not a_correct and b_correct:
                gained.append(a['id'])
            if a_correct and not b_correct:
                lost.append(a['id'])
            if a['probabilities'][field] != b['probabilities'][field]:
                dist_changed.append(a['id'])
            if a['confidence'][field] != b['confidence'][field]:
                conf_changed.append(a['id'])
        fields[field] = {'firstCorrect': sum(x['prediction'][field] == x['reference'][field] for x in first_entries),
            'secondCorrect': sum(x['prediction'][field] == x['reference'][field] for x in second_entries),
            'predictionChangedIds': changed, 'becameCorrectIds': gained,
            'becameIncorrectIds': lost,
            'nativeDistributionChangedIds': dist_changed,
            'vendorConfidenceChangedIds': conf_changed}
    return {'firstPass': first_label, 'secondPass': second_label,
        'sharedValid': 60, 'firstAllFourCorrect': p0_all,
        'secondAllFourCorrect': p1_all, 'allFourDelta': p1_all - p0_all,
        'predictionVectorChangedIds': changed_vector,
        'allFourBecameCorrectIds': all4_gain,
        'allFourBecameIncorrectIds': all4_loss,
        'nativeDistributionsChangedIds': probability_changes,
        'vendorConfidenceChangedIds': confidence_changes,
        'fields': fields,
        'interpretation': interpretation}


def build(root=ROOT):
    root = Path(root)
    sources = Sources(root)
    # Verify the existing frozen P0 report and both exact request plans.
    p0_report = first.build(root)
    saved_p0 = sources.json(P0_REPORT)
    if p0_report != saved_p0:
        raise ValueError('Frozen fresh1 P0 findings differ from source evidence')
    for relative in ('scripts/build_clef_findings.py',
                     'scripts/build_clef_flash_p1_findings.py',
                     'scripts/build_clef_p0_repeat_findings.py',
                     'scripts/clef_native_preparation.py',
                     'scripts/clef_native_remaining.py',
                     'scripts/clef_connected_app_bridge.py',
                     'scripts/jev_benchmark.py',
                     'scripts/jev_native_prompt_variants_v1.py',
                     'results/clef-native-v1/preparation.json', PROPOSAL,
                     BASE / 'clef-flash-billing-source.md'):
        sources.path(relative)
    p0_manifest = sources.json(P0_MANIFEST)
    if p0_manifest != full_p0.manifest_value():
        raise ValueError('Frozen P0 manifest differs from input-only plan')
    manifest = sources.json(MANIFEST)
    if manifest != remaining.manifest_value(root, root / PROPOSAL):
        raise ValueError('Remaining-stage manifest differs from frozen inputs')
    if (manifest['stages'][f'{MODEL}/{PASS}/{CONDITION}']['route'] != prep.MODELS[MODEL]['route'] or
            len(manifest['stages'][f'{MODEL}/{PASS}/{CONDITION}']['requests']) != 60 or
            p0_manifest['models'][MODEL]['route'] != prep.MODELS[MODEL]['route']):
        raise ValueError('P0/P1 model route or request membership differs')
    billing_path = BASE / 'clef-flash-billing-source.md'
    if sources.hashes[str(billing_path)] != manifest['billing_source_sha256'][MODEL]:
        raise ValueError('Saved Clef Flash billing source differs from frozen rate hash')
    label_path = sources.path(first.LABELS)
    if sources.hashes[str(first.LABELS)] != first.LABELS_SHA256:
        raise ValueError('Frozen reference labels changed')
    label_rows = [json.loads(line) for line in label_path.read_bytes().splitlines()]
    if ([row.get('id') for row in label_rows] != list(IDS) or
            any(row.get('review_version') != '0.2' or
                not first.valid(row.get('proposed_labels')) for row in label_rows)):
        raise ValueError('Reference membership or schema differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    p0_dir = BASE / MODEL / 'fresh1/P0/development'
    p0_claim = sources.json(p0_dir / 'claim.json')
    p0_records = sources.rows(p0_dir / 'records.jsonl')
    p0_entries = project_records(p0_records, labels)
    # The first-pass builder fully checked P0 attempts. Bind its exact P0 inputs too.
    p0_sources = p0_report['sourceSha256']
    for relative in (p0_dir / 'claim.json', p0_dir / 'completion.json',
                     p0_dir / 'journal.jsonl', p0_dir / 'raw.jsonl',
                     p0_dir / 'records.jsonl'):
        sources.path(relative)
        if p0_sources.get(str(relative)) != sources.hashes[str(relative)]:
            raise ValueError('Matched P0 evidence differs from audited P0 report')
    fresh1_entries, fresh1_elapsed = validate_stage(sources, manifest, labels,
                                                    p0_claim, 'fresh1', None)
    manifest_hash = sources.hashes[str(MANIFEST)]
    fresh2_completion_hash = remaining.predecessor_hash(
        MODEL, 'fresh2', CONDITION, manifest_hash, base=root / BASE)
    fresh2_entries, fresh2_elapsed = validate_stage(sources, manifest, labels,
        p0_claim, 'fresh2', fresh2_completion_hash)
    fresh3_completion_hash = remaining.predecessor_hash(
        MODEL, 'fresh3', CONDITION, manifest_hash, base=root / BASE)
    fresh3_entries, fresh3_elapsed = validate_stage(sources, manifest, labels,
        p0_claim, 'fresh3', fresh3_completion_hash)
    p0_score = p0_report['models'][MODEL]
    fresh1_fields = {field: first.field_metrics(fresh1_entries, field) for field in prep.KEYS}
    fresh2_fields = {field: first.field_metrics(fresh2_entries, field) for field in prep.KEYS}
    fresh3_fields = {field: first.field_metrics(fresh3_entries, field) for field in prep.KEYS}
    fresh1_all = sum(all(row['prediction'][field] == row['reference'][field]
                     for field in prep.KEYS) for row in fresh1_entries)
    fresh2_all = sum(all(row['prediction'][field] == row['reference'][field]
                     for field in prep.KEYS) for row in fresh2_entries)
    fresh3_all = sum(all(row['prediction'][field] == row['reference'][field]
                     for field in prep.KEYS) for row in fresh3_entries)
    if (p0_score['valid'] != 60 or p0_score['failed'] != 0 or
            [row['id'] for row in p0_entries] != [row['id'] for row in fresh1_entries] or
            [row['id'] for row in fresh1_entries] != [row['id'] for row in fresh2_entries] or
            [row['id'] for row in fresh2_entries] != [row['id'] for row in fresh3_entries]):
        raise ValueError('P0/P1 shared-valid comparison is not exactly 60 records')
    requests_p0 = p0_manifest['models'][MODEL]['requests']
    requests_p1 = manifest['stages'][f'{MODEL}/{PASS}/{CONDITION}']['requests']
    if ([r['id'] for r in requests_p0] != [r['id'] for r in requests_p1] or
            [r['input_sha256'] for r in requests_p0] != [r['input_sha256'] for r in requests_p1] or
            [r['payload_sha256'] for r in requests_p0] == [r['payload_sha256'] for r in requests_p1]):
        raise ValueError('P0/P1 are not matched on inputs or lack the declared prompt change')
    fresh1_tokens = sum(row['usage']['input_tokens'] for row in fresh1_entries)
    fresh2_tokens = sum(row['usage']['input_tokens'] for row in fresh2_entries)
    fresh3_tokens = sum(row['usage']['input_tokens'] for row in fresh3_entries)
    fresh1_output_tokens = sum(row['usage'].get('output_tokens', 0) for row in fresh1_entries)
    fresh2_output_tokens = sum(row['usage'].get('output_tokens', 0) for row in fresh2_entries)
    fresh3_output_tokens = sum(row['usage'].get('output_tokens', 0) for row in fresh3_entries)
    price = prep.MODELS[MODEL]['input_usd_per_million']
    fresh1_phase = {'stage': STAGE, 'attempted': 60,
        'counts': {'valid': 60, 'invalidOutput': 0, 'serviceError': 0,
                   'unknownOutcome': 0, 'neverSent': 0},
        'allFourCorrect': fresh1_all, 'allFourDenominator': 60,
        'allFourAccuracy': round(fresh1_all / 60, 6), 'fields': fresh1_fields,
        'observedInputTokens': fresh1_tokens,
        'observedOutputTokens': fresh1_output_tokens,
        'clientElapsedSeconds': round(fresh1_elapsed, 6)}
    fresh2_phase = {'stage': f'{MODEL}/fresh2/{CONDITION}/development',
        'attempted': 60,
        'counts': {'valid': 60, 'invalidOutput': 0, 'serviceError': 0,
                   'unknownOutcome': 0, 'neverSent': 0},
        'allFourCorrect': fresh2_all, 'allFourDenominator': 60,
        'allFourAccuracy': round(fresh2_all / 60, 6), 'fields': fresh2_fields,
        'observedInputTokens': fresh2_tokens,
        'observedOutputTokens': fresh2_output_tokens,
        'clientElapsedSeconds': round(fresh2_elapsed, 6)}
    fresh3_phase = {'stage': f'{MODEL}/fresh3/{CONDITION}/development',
        'attempted': 60,
        'counts': {'valid': 60, 'invalidOutput': 0, 'serviceError': 0,
                   'unknownOutcome': 0, 'neverSent': 0},
        'allFourCorrect': fresh3_all, 'allFourDenominator': 60,
        'allFourAccuracy': round(fresh3_all / 60, 6), 'fields': fresh3_fields,
        'observedInputTokens': fresh3_tokens,
        'observedOutputTokens': fresh3_output_tokens,
        'clientElapsedSeconds': round(fresh3_elapsed, 6)}
    return {'schema': 'clef-flash-p1-findings-v1',
        'referenceStatus': p0_report['referenceStatus'],
        'configuration': {'model': MODEL, 'route': prep.MODELS[MODEL]['route'],
            'pass': PASS, 'condition': CONDITION,
            'contextTokens': prep.CONTEXT_TOKENS,
            'transport': 'Cloudflare connected app',
            'referenceLabelsSent': False},
        'phase': fresh1_phase,
        'phaseByPass': {'fresh1': fresh1_phase, 'fresh2': fresh2_phase,
                        'fresh3': fresh3_phase},
        'controls': {'matchedFresh1P0': {'auditPassed': True,
            'sharedValid': 60, 'sameModelAndRoute': True,
            'sameOrderedInputsAndReferences': True,
            'sameNativeChoiceInterface': True,
            'sameConnectedAppTransport': True,
            'sameFreshPass': True,
            'declaredPromptConditionDiffers': True,
            'p0AllFourCorrect': p0_score['allFourCorrect'],
            'p1AllFourCorrect': fresh1_all,
            'comparison': compare(p0_entries, fresh1_entries,
                'fresh1/P0', 'fresh1/P1',
                'Matched prompt-condition comparison on the same 60 records. Descriptive, not a repeatability estimate.' )},
            'p1Repeatability': compare(fresh1_entries, fresh2_entries,
                'fresh1/P1', 'fresh2/P1',
                'Separately dispatched P1 passes on the same 60 records. Pairwise comparisons are descriptive.'),
            'p1Fresh1Fresh3': compare(fresh1_entries, fresh3_entries,
                'fresh1/P1', 'fresh3/P1',
                'Pairwise comparison across separately dispatched P1 passes; descriptive.'),
            'p1Fresh2Fresh3': compare(fresh2_entries, fresh3_entries,
                'fresh2/P1', 'fresh3/P1',
                'Pairwise comparison across separately dispatched P1 passes; descriptive.'),
            'requiredFullPassesPerCondition': 3,
            'fullPassesCompleted': 3},
        'cost': {'publishedInputUsdPerMillion': str(price),
            'publishedInputPriceEstimateUsd': str(Decimal(fresh1_tokens) * price / Decimal(1_000_000)),
            'publishedInputPriceEstimateUsdByPass': {
                'fresh1': str(Decimal(fresh1_tokens) * price / Decimal(1_000_000)),
                'fresh2': str(Decimal(fresh2_tokens) * price / Decimal(1_000_000)),
                'fresh3': str(Decimal(fresh3_tokens) * price / Decimal(1_000_000))},
            'fullContextUnknownChargeHoldUsd': str(prep.reservation_usd(MODEL, 60)),
            'providerBilledUsd': None,
            'note': 'The token-price estimate is not a provider bill. The full-context hold is a reservation bound.'},
        'timing': {'inferenceLatencyAvailable': False,
            'includesConnectedAppHandoff': True,
            'note': 'Client elapsed seconds include connected-app operator handoff and do not measure pure inference latency.'},
        'metrics': {'nativeChoiceProbabilities': 'Scored as distributions separately from the provider confidence field.',
            'vendorConfidence': 'Reported separately; no calibration meaning is assumed.',
            'confidenceErrors': 'Both vendor confidence and probability assigned to the chosen label are shown for incorrect predictions at or above 0.8.'},
        'sourceSha256': sources.hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    payload = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    target = ROOT / OUTPUT
    if args.check:
        if target.read_text() != payload:
            raise ValueError('Saved Clef Flash P1 projection differs from current evidence')
    else:
        target.write_text(payload)
    print(target)


if __name__ == '__main__':
    main()
