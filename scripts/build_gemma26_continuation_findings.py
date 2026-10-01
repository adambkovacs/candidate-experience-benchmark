#!/usr/bin/env python3
"""Build a public, read-only account of the interrupted Gemma26 continuation.

Run against a clean archive of immutable evidence. This module never opens a
budget ledger, private original P2 attempts, or a provider connection.
"""
import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/gemma26-on-fresh-matched3-v2')
CONT = BASE / 'interruption-continuation-v1'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABEL_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
SCHEMA = 'gemma26-on-v2-interrupted-continuation-findings-v1'
CONT_SCHEMA = 'gemma26-on-v2-interruption-continuation-v1'
IDS = [f'DEV-{n:03d}' for n in range(1, 61)]
ORDER = [(a, b) for a in ('fresh1', 'fresh2', 'fresh3') for b in ('P0', 'P1', 'P2')]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    blob = Path(path).read_bytes()
    if not blob.endswith(b'\n') or any(not line for line in blob.splitlines()):
        raise ValueError('Incomplete JSONL: ' + str(path))
    return [json.loads(line) for line in blob.splitlines()]


def bound(root, relative, bindings, expected=None):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or any(
            'ledger' in part.lower() for part in relative.parts):
        raise ValueError('Unsafe public source path')
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError('Public source missing: ' + str(relative))
    value = digest(path)
    if expected is not None and value != expected:
        raise ValueError('Public source hash differs: ' + str(relative))
    item = {'path': relative.as_posix(), 'sha256': value}
    if item not in bindings:
        bindings.append(item)
    return path


def stage_files(root, folder, stage, bindings, expected=None):
    files = {}
    for name, suffix in (('claim', 'claim.json'), ('review', 'root-review.json'),
                         ('journal', 'journal.jsonl'), ('attempts', 'attempts.jsonl'),
                         ('responses', 'responses.jsonl'), ('wire', 'wire.jsonl')):
        rel = folder / f'{stage}.{suffix}'
        files[name] = bound(root, rel, bindings, expected.get(name) if expected else None)
    return files


def verify_inspection(root, folder, files, bindings, schema, series, plan_sha,
                      fresh=None, condition=None):
    path = bound(root, folder / 'smoke-inspection.json', bindings)
    value = json.loads(path.read_text())
    required = {'schema': schema, 'series_id': series,
                'decision': 'accepted_unchanged', 'manifest_sha256': plan_sha,
                **{name + '_sha256': digest(files[name]) for name in
                   ('journal', 'attempts', 'responses', 'wire')}}
    if fresh is not None:
        required.update({'fresh_pass': fresh, 'condition': condition})
    if any(value.get(k) != v for k, v in required.items()):
        raise ValueError('Smoke inspection is not bound to closed raw evidence')


def verify_rows(files, ids, hashes, series, plan_sha, phase, pass_name, condition,
                stopped=False):
    claim, review = (json.loads(files[k].read_text()) for k in ('claim', 'review'))
    if (claim.get('series_id') != series or claim.get('fresh_pass') != pass_name or
            claim.get('condition') != condition or claim.get('phase') != phase or
            claim.get('manifest_sha256') != plan_sha or
            claim.get('root_review_sha256') != digest(files['review']) or
            review.get('approved') is not True):
        raise ValueError('Stage claim or review differs')
    attempts, responses, wires, journal = (rows(files[k]) for k in
                                            ('attempts', 'responses', 'wire', 'journal'))
    if ([x.get('id') for x in attempts] != ids or
            [x.get('id') for x in responses] != ids or
            [x.get('id') for x in wires] != ids or
            [x.get('request_sha256') for x in attempts] != hashes or
            len({x.get('attempt_id') for x in attempts}) != len(ids)):
        raise ValueError('Stage membership, request hashes or unique attempts differ')
    if (journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != ('phase_stopped' if stopped else 'phase_completed') or
            (not stopped and (journal[-1].get('request_count') != len(ids) or
                              journal[-1].get('attempt_ids') != [x['attempt_id'] for x in attempts]))):
        raise ValueError('Stage terminal event differs')
    expected_events = 2 + 3 * len(ids)
    if len(journal) != expected_events:
        raise ValueError('Stage journal lifecycle length differs')
    for i, (rid, request_sha, attempt, response, wire) in enumerate(
            zip(ids, hashes, attempts, responses, wires)):
        aid = attempt['attempt_id']
        if (attempt.get('id') != rid or attempt.get('series_id') != series or
                attempt.get('manifest_sha256') != plan_sha or
                attempt.get('reference_labels_read') is not False or
                response.get('id') != rid or response.get('attempt_id') != aid or
                response.get('request_sha256') != request_sha or
                wire.get('id') != rid or wire.get('attempt_id') != aid or
                wire.get('request_sha256') != request_sha or
                wire.get('body_truncated_at_limit') is not False or wire.get('read_error') is not None or
                [x.get('event') for x in journal[1 + 3*i:4 + 3*i]] !=
                ['request_intent', 'request_started', 'request_finished'] or
                journal[1 + 3*i].get('id') != rid or
                journal[1 + 3*i].get('request_sha256') != request_sha or
                journal[2 + 3*i].get('id') != rid or
                journal[2 + 3*i].get('attempt_id') != aid or
                journal[3 + 3*i].get('id') != rid or
                journal[3 + 3*i].get('attempt_id') != aid or
                journal[3 + 3*i].get('status') != attempt.get('status') or
                journal[3 + 3*i].get('billing_ok') != attempt.get('billing_ok') or
                journal[3 + 3*i].get('cost_unknown') != attempt.get('cost_unknown') or
                journal[3 + 3*i].get('observed_cost_usd') != attempt.get('observed_cost_usd')):
            raise ValueError('Stage lifecycle or request binding differs at ' + rid)
        if attempt.get('status') == 'ok':
            if (response.get('raw_response') != attempt.get('raw_response') or
                    wire.get('http_status') != 200 or
                    json.loads(base64.b64decode(wire['body_base64'], validate=True)) != attempt['raw_response'] or
                    attempt.get('cost_unknown') is not False or
                    attempt.get('observed_cost_usd') is None or
                    Decimal(str(attempt['observed_cost_usd'])) < 0 or
                    Decimal(str(attempt['observed_cost_usd'])) >
                    Decimal(str(attempt['reserved_cost_usd'])) or
                    Decimal(str(attempt['observed_cost_usd'])) !=
                    Decimal(str((attempt['raw_response'].get('usage') or {}).get('cost')))):
                raise ValueError('Stage response binding differs at ' + rid)
        elif not stopped or attempt.get('status') != 'service_error' or rid != 'DEV-007':
            raise ValueError('Unexpected failure or missing original service error')
    return attempts


def verify_stopped_continuation(root, manifest, manifest_sha, spec, bindings):
    """Verify a stopped, unscored phase without reading or publishing error text."""
    fresh, condition, stage = (spec[k] for k in ('fresh_pass', 'condition', 'stage'))
    folder = CONT / fresh / condition
    files = stage_files(root, folder, stage, bindings)
    claim, review = (json.loads(files[k].read_text()) for k in ('claim', 'review'))
    source = manifest['source_bindings']
    if (claim.get('series_id') != CONT_SCHEMA or claim.get('fresh_pass') != fresh or
            claim.get('condition') != condition or claim.get('phase') != stage or
            claim.get('manifest_sha256') != manifest_sha or
            claim.get('root_review_sha256') != digest(files['review']) or
            review.get('schema') != CONT_SCHEMA + '-stage-review' or
            review.get('approved') is not True or review.get('series_id') != CONT_SCHEMA or
            review.get('manifest_sha256') != manifest_sha or
            review.get('controller_sha256') != source['controller']['sha256'] or
            review.get('old_reconciliation_sha256') != source['old_reconciliation']['sha256'] or
            review.get('stage') != f'{fresh}/{condition}/{stage}' or
            review.get('ids') != spec['ids'] or
            review.get('request_sha256') != spec['request_sha256']):
        raise ValueError('Stopped continuation claim or review differs')
    attempts, raw, wire, journal = (rows(files[k]) for k in
                                    ('attempts', 'responses', 'wire', 'journal'))
    count = len(attempts)
    if (count < 2 or count >= len(spec['ids']) or
            [r.get('id') for r in attempts] != spec['ids'][:count] or
            [r.get('request_sha256') for r in attempts] != spec['request_sha256'][:count] or
            [r.get('id') for r in raw] != spec['ids'][:count - 1] or
            [r.get('id') for r in wire] != spec['ids'][:count - 1] or
            len({r.get('attempt_id') for r in attempts}) != count or
            len(journal) != 2 + 3 * count or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_stopped' or
            journal[-1].get('id') != spec['ids'][count - 1] or
            journal[-1].get('reason') != 'service_error'):
        raise ValueError('Stopped continuation membership or lifecycle differs')
    plan_path = bound(root, BASE / fresh / 'manifest.json', bindings,
                      source['original_plan_' + fresh]['sha256'])
    planned = json.loads(plan_path.read_text())['conditions'][condition]['development']
    for i, attempt in enumerate(attempts):
        rid = spec['ids'][i]
        aid = attempt.get('attempt_id')
        events = journal[1 + 3*i:4 + 3*i]
        if (not isinstance(aid, str) or not aid or
                attempt.get('series_id') != CONT_SCHEMA or
                attempt.get('manifest_sha256') != manifest_sha or
                attempt.get('reference_labels_read') is not False or
                Decimal(str(attempt.get('reserved_cost_usd'))) !=
                Decimal(manifest['reserve_usd']) or
                attempt.get('request') != planned[i]['payload'] or
                attempt.get('request_sha256') != planned[i]['request_sha256'] or
                [event.get('event') for event in events] !=
                ['request_intent', 'request_started', 'request_finished'] or
                events[0].get('id') != rid or
                events[0].get('request_sha256') != spec['request_sha256'][i] or
                events[1].get('id') != rid or events[1].get('attempt_id') != aid or
                events[1].get('request_sha256') != spec['request_sha256'][i] or
                events[2].get('id') != rid or events[2].get('attempt_id') != aid or
                events[2].get('status') != attempt.get('status') or
                events[2].get('billing_ok') != attempt.get('billing_ok') or
                events[2].get('cost_unknown') != attempt.get('cost_unknown') or
                events[2].get('observed_cost_usd') != attempt.get('observed_cost_usd')):
            raise ValueError('Stopped continuation request or journal differs at ' + rid)
        if i < count - 1:
            response, captured = raw[i], wire[i]
            if (attempt.get('status') != 'ok' or attempt.get('billing_ok') is not True or
                    attempt.get('cost_unknown') is not False or
                    attempt.get('observed_cost_usd') is None or
                    not Decimal(0) <= Decimal(str(attempt['observed_cost_usd'])) <=
                    Decimal(manifest['reserve_usd']) or
                    Decimal(str(attempt['observed_cost_usd'])) !=
                    Decimal(str((attempt.get('raw_response', {}).get('usage') or {}).get('cost'))) or
                    response.get('attempt_id') != aid or
                    response.get('request_sha256') != spec['request_sha256'][i] or
                    response.get('raw_response') != attempt.get('raw_response') or
                    captured.get('attempt_id') != aid or captured.get('http_status') != 200 or
                    captured.get('request_sha256') != spec['request_sha256'][i] or
                    captured.get('body_truncated_at_limit') is not False or
                    captured.get('read_error') is not None or
                    json.loads(base64.b64decode(captured['body_base64'], validate=True)) !=
                    attempt.get('raw_response')):
                raise ValueError('Stopped continuation known response differs at ' + rid)
        elif (attempt.get('status') != 'service_error' or
              attempt.get('billing_ok') is not False or
              attempt.get('cost_unknown') is not True or
              attempt.get('observed_cost_usd') is not None):
            raise ValueError('Stopped continuation unknown-cost failure differs')
    return {'pass': fresh, 'condition': condition, 'status': 'stopped_unscored',
            'score': None, 'attempted': count, 'validOutputCount': count - 1,
            'serviceErrorCount': 1, 'failedId': spec['ids'][count - 1],
            'neverSentCount': len(spec['ids']) - count,
            'neverSentIds': spec['ids'][count:],
            'usage': usage(attempts, Decimal(manifest['reserve_usd']))}


def score(records, labels):
    by_id = {r['id']: r for r in records}
    if len(by_id) != len(records) or not set(by_id).issubset(IDS):
        raise ValueError('Duplicate or unknown development record')
    outcomes = Counter()
    fields = {field: 0 for field in KEYS}
    all_four = 0
    valid_ids = []
    for rid in IDS:
        row = by_id.get(rid)
        if row is None:
            outcomes['never_sent'] += 1
        elif row.get('status') == 'ok' and valid(row.get('prediction')):
            outcomes['valid'] += 1
            valid_ids.append(rid)
            for field in KEYS:
                fields[field] += row['prediction'][field] == labels[rid][field]
            all_four += all(row['prediction'][field] == labels[rid][field] for field in KEYS)
        elif row.get('status') == 'service_error':
            outcomes['service_error'] += 1
        else:
            outcomes['invalid_output'] += 1
    return {'denominator': 60, 'saved': len(records), 'valid': outcomes['valid'],
            'allFour': all_four, 'fields': fields,
            'outcomes': {key: outcomes[key] for key in
                         ('valid', 'invalid_output', 'service_error', 'never_sent')},
            'validIds': valid_ids,
            'scoreKind': 'fixed_60_partial_tally' if outcomes['never_sent'] else 'fixed_60'}


def usage(records, unknown_bound=Decimal(0)):
    def metric(values):
        present = [v for v in values if type(v) is int]
        return {'sum': sum(present) if len(present) == len(values) else None,
                'reportedCount': len(present), 'missingCount': len(values) - len(present)}
    token_keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    tokens = {k: metric([(r.get('usage') or {}).get(k) for r in records]) for k in token_keys}
    tokens['providerReportedReasoningTokens'] = metric([
        ((r.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens')
        for r in records])
    known = [Decimal(str(r['observed_cost_usd'])) for r in records
             if r.get('observed_cost_usd') is not None]
    unknown = sum(r.get('observed_cost_usd') is None for r in records)
    durations = [r.get('elapsed_seconds') for r in records]
    if any(type(v) not in (int, float) or v < 0 for v in durations):
        raise ValueError('Invalid client request duration')
    return {'requestCount': len(records), 'requestSecondsTotal': sum(durations),
            'timingKind': 'client_request_to_record_not_provider_inference',
            'tokenAvailability': tokens, 'knownCostUsd': str(sum(known, Decimal(0))),
            'actualCostUsd': str(sum(known, Decimal(0))) if unknown == 0 else None,
            'unknownCostCount': unknown,
            'unknownCostUpperBoundUsd': str(unknown_bound) if unknown else '0'}


def build(root=ROOT):
    root = Path(root).resolve()
    bindings = []
    bound(root, Path('scripts/build_gemma26_continuation_findings.py'), bindings)
    label_rows = rows(bound(root, LABELS, bindings, LABEL_SHA))
    if ([r.get('id') for r in label_rows] != IDS or
            any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels'))
                for r in label_rows)):
        raise ValueError('Provisional labels differ')
    labels = {r['id']: r['proposed_labels'] for r in label_rows}
    manifest_path = bound(root, CONT / 'manifest.json', bindings)
    manifest_sha = digest(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('schema') != CONT_SCHEMA or manifest.get('status') != 'FROZEN' or
            manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('original_failed_id') != 'DEV-007' or
            manifest.get('original_never_sent_ids') != IDS[7:] or
            manifest.get('reference_labels_read') is not False):
        raise ValueError('Unexpected continuation identity or source policy')
    prefix_folder = CONT / 'public-prefix-v1'
    export_path = bound(root, prefix_folder / 'export-manifest.json', bindings)
    export = json.loads(export_path.read_text())
    if (export.get('schema') != CONT_SCHEMA + '-public-prefix-export' or
            export.get('manual_privacy_review_required') is not True or
            {m.get('kind') for m in export.get('mappings', [])} != {'attempts', 'responses', 'wire'}):
        raise ValueError('Public prefix attestation differs')
    source = manifest['source_bindings']
    if (export.get('prefix_claim_sha256') != source['stopped_claim']['sha256'] or
            export.get('prefix_journal_sha256') != source['stopped_journal']['sha256']):
        raise ValueError('Original stopped prefix attestation differs')
    public_prefix = {}
    for mapping in export['mappings']:
        kind = mapping['kind']
        if (mapping['private']['sha256'] != source['stopped_' + kind]['sha256'] or
                mapping['public']['path'] != str(prefix_folder / f'development.{kind}.jsonl')):
            raise ValueError('Public prefix mapping differs')
        public_prefix[kind] = bound(root, mapping['public']['path'], bindings,
                                    mapping['public']['sha256'])
    old_claim = bound(root, source['stopped_claim']['path'], bindings,
                      source['stopped_claim']['sha256'])
    old_journal = bound(root, source['stopped_journal']['path'], bindings,
                        source['stopped_journal']['sha256'])
    old_review = bound(root, source['stopped_review']['path'], bindings,
                       source['stopped_review']['sha256'])
    old_plan_path = bound(root, BASE / 'fresh1/manifest.json', bindings,
                          source['original_plan_fresh1']['sha256'])
    old_plan = json.loads(old_plan_path.read_text())
    prefix_files = {'claim': old_claim, 'journal': old_journal, 'review': old_review,
                    **public_prefix}
    prefix_requests = old_plan['conditions']['P2']['development'][:7]
    prefix = verify_rows(prefix_files, IDS[:7],
                         [x['request_sha256'] for x in prefix_requests],
                         old_plan['series_id'], digest(old_plan_path), 'development',
                         'fresh1', 'P2', stopped=True)
    if ([r['status'] for r in prefix] != ['ok'] * 6 + ['service_error'] or
            any(r.get('request') != p['payload'] for r, p in zip(prefix, prefix_requests)) or
            prefix[-1].get('cost_unknown') is not True or
            prefix[-1].get('observed_cost_usd') is not None):
        raise ValueError('Original DEV-007 failure differs')
    for condition in ('P0', 'P1', 'P2'):
        folder = BASE / 'fresh1' / condition
        expected = ({key.split('_smoke_')[1]: val['sha256'] for key, val in source.items()
                     if key.startswith('fresh1_P2_smoke_') and
                     key.split('_smoke_')[1] in ('claim', 'journal', 'attempts', 'responses', 'wire')}
                    if condition == 'P2' else None)
        smoke_files = stage_files(root, folder, 'smoke', bindings, expected)
        planned = old_plan['conditions'][condition]['smoke']
        smoke_records = verify_rows(smoke_files, [r['record_id'] for r in planned],
                                    [r['request_sha256'] for r in planned],
                                    old_plan['series_id'], digest(old_plan_path),
                                    'smoke', 'fresh1', condition)
        if any(r.get('request') != p['payload'] for r, p in zip(smoke_records, planned)):
            raise ValueError('Original smoke payload differs')
        verify_inspection(root, folder, smoke_files, bindings,
                          'openrouter-repeat-smoke-inspection-v2',
                          old_plan['series_id'], digest(old_plan_path),
                          'fresh1', condition)
    stages = {(s['fresh_pass'], s['condition'], s['stage']): s for s in manifest['stages']}
    if len(stages) != 13 or ('fresh1', 'P2', 'suffix') not in stages:
        raise ValueError('Continuation schedule differs')
    completed = {}
    stopped_phases = []
    for key, spec in stages.items():
        fresh, condition, stage = key
        folder = CONT / fresh / condition
        journal = root / folder / f'{stage}.journal.jsonl'
        if not journal.is_file():
            continue
        journal_rows = rows(journal)
        if journal_rows and journal_rows[-1].get('event') == 'phase_stopped':
            if key != ('fresh2', 'P0', 'development') or stopped_phases:
                raise ValueError('Unexpected stopped continuation phase')
            stopped_phases.append(verify_stopped_continuation(
                root, manifest, manifest_sha, spec, bindings))
            continue
        if not journal_rows or journal_rows[-1].get('event') != 'phase_completed':
            continue
        files = stage_files(root, folder, stage, bindings)
        review = json.loads(files['review'].read_text())
        if (review.get('schema') != CONT_SCHEMA + '-stage-review' or
                review.get('series_id') != CONT_SCHEMA or
                review.get('manifest_sha256') != manifest_sha or
                review.get('stage') != f'{fresh}/{condition}/{stage}' or
                review.get('ids') != spec['ids'] or
                review.get('request_sha256') != spec['request_sha256'] or
                review.get('controller_sha256') != source['controller']['sha256'] or
                review.get('old_reconciliation_sha256') != source['old_reconciliation']['sha256']):
            raise ValueError('Continuation review differs')
        attempts = verify_rows(files, spec['ids'], spec['request_sha256'],
                               CONT_SCHEMA, manifest_sha, stage, fresh, condition)
        if stage == 'development':
            prior_folder = CONT / fresh / condition
            prior = stage_files(root, prior_folder, 'smoke', bindings)
            verify_inspection(root, prior_folder, prior, bindings,
                              CONT_SCHEMA + '-smoke-inspection',
                              CONT_SCHEMA, manifest_sha)
        if any(r.get('status') != 'ok' or r.get('billing_ok') is not True or
               r.get('cost_unknown') is not False for r in attempts):
            raise ValueError('Continuation stage contains failed settlement')
        plan_path = bound(root, BASE / fresh / 'manifest.json', bindings,
                          source['original_plan_' + fresh]['sha256'])
        plan = json.loads(plan_path.read_text())
        planned = plan['conditions'][condition]['smoke' if stage == 'smoke' else 'development']
        selected = planned[7:] if stage == 'suffix' else planned
        if ([r['record_id'] for r in selected] != spec['ids'] or
                [r['request_sha256'] for r in selected] != spec['request_sha256'] or
                any(a.get('request') != p['payload'] for a, p in zip(attempts, selected))):
            raise ValueError('Continuation payload differs from frozen original plan')
        completed[key] = attempts
    # Only an uninterrupted prefix of scheduled stages can be published.
    seen_gap = False
    for key in stages:
        if key not in completed:
            seen_gap = True
        elif seen_gap:
            raise ValueError('Completed continuation stage follows an unclosed predecessor')
    if ('fresh1', 'P2', 'suffix') not in completed:
        raise ValueError('First suffix is not closed')
    passes = {p: {} for p in ('fresh1', 'fresh2', 'fresh3')}
    missing = []
    for fresh, condition in ORDER:
        if fresh == 'fresh1' and condition in ('P0', 'P1'):
            plan = old_plan
            folder = BASE / fresh / condition
            files = stage_files(root, folder, 'development', bindings, {
                key.split('_development_')[1]: val['sha256'] for key, val in source.items()
                if key.startswith(f'fresh1_{condition}_development_') and
                key.split('_development_')[1] in ('claim', 'journal', 'attempts', 'responses', 'wire')})
            planned = plan['conditions'][condition]['development']
            records = verify_rows(files, IDS, [r['request_sha256'] for r in planned],
                                  plan['series_id'], digest(old_plan_path), 'development',
                                  fresh, condition)
            if any(r.get('request') != p['payload'] for r, p in zip(records, planned)):
                raise ValueError('Original completed payload differs')
        elif fresh == 'fresh1' and condition == 'P2':
            records = prefix + completed[('fresh1', 'P2', 'suffix')]
        elif (fresh, condition, 'development') in completed:
            records = completed[(fresh, condition, 'development')]
        else:
            stopped = next((item for item in stopped_phases if
                            (item['pass'], item['condition']) == (fresh, condition)), None)
            missing.append({'pass': fresh, 'condition': condition,
                            'status': 'stopped_unscored' if stopped else
                            'not_completed_in_public_cutoff'})
            continue
        if [r['id'] for r in records] != IDS:
            raise ValueError('Composite development membership differs')
        bound_amount = (Decimal(manifest['old_unknown_upper_bound_usd'])
                        if (fresh, condition) == ('fresh1', 'P2') else Decimal(0))
        passes[fresh][condition] = {'status': 'completed_interrupted' if
                                    (fresh, condition) == ('fresh1', 'P2') else 'completed',
                                    'score': score(records, labels),
                                    'usage': usage(records, bound_amount),
                                    'servedRoute': {'returnedModels': dict(Counter(r.get('returned_model') for r in records if r.get('returned_model'))),
                                                    'returnedProviders': dict(Counter(r.get('returned_provider') for r in records if r.get('returned_provider')))}}
    return {'schema': SCHEMA, 'seriesId': CONT_SCHEMA,
            'configuration': manifest['configuration_id'],
            'method': 'descriptive-interrupted-series-continuation',
            'cleanMatchedThreeEligible': False,
            'denominator': 60, 'plannedConditions': 9,
            'completedConditions': sum(len(v) for v in passes.values()),
            'originalFailedId': 'DEV-007', 'originalFailureStatus': 'service_error',
            'originalNeverSentBeforeContinuation': IDS[7:],
            'missingPasses': missing, 'stoppedPhases': stopped_phases,
            'passes': passes,
            'referenceStatus': 'AI-reviewed provisional; not independently adjudicated',
            'limitations': ['The same 60 synthetic development comments recur in each completed phase.',
                            'DEV-007 failed in the original P2 attempt; the continuation did not replay it.',
                            'The first P2 pass combines a stopped original prefix and a separately dispatched suffix.',
                            'A sanitized public copy attests the original prefix; private provider error bytes are not a publication source.',
                            'The unknown original charge is bounded, not an observed cost.',
                            'Token fields are provider reported and may be missing; client duration is not pure inference time.',
                            'This interrupted series is not a clean matched-three repeat.'],
            'sourceBindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build(args.root)
    content = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != content:
            raise ValueError('Published continuation feed differs from bound evidence')
    elif args.output:
        args.output.write_text(content)
    print(f"Gemma26 interrupted continuation {result['completedConditions']}/9")


if __name__ == '__main__':
    main()
