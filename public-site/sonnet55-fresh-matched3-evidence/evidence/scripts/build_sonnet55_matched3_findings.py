#!/usr/bin/env python3
"""Build a public-safe, source-bound Sonnet 5.5 matched-three snapshot offline."""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import math
import re

import build_claude_repeat_findings as opus
import build_repeat_findings as shared
import claude_sonnet55_matched3_v2 as lane
from claude_batch_benchmark import parse_batch_result
from claude_benchmark import safe_diagnostic
from development_benchmark import digest
from export_claude_public_evidence import verify_public

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/claude-sonnet55-fresh-matched3-v2')
OUTPUT = Path('public-site/sonnet55-fresh-matched3.json')
EFFORTS = ('low', 'medium', 'high', 'xhigh')
PASSES = ('pass1', 'pass2', 'pass3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS
PRICES = {'input': Decimal('2'), 'output': Decimal('10'),
          'cache5mWrite': Decimal('2.5'), 'cache1hWrite': Decimal('4'),
          'cacheRead': Decimal('0.2')}
PRICE_URL = 'https://platform.claude.com/docs/en/models/sonnet-5-5/overview'


def _context(root):
    bind, sources = opus._binder(root)
    for path in ('scripts/build_sonnet55_matched3_findings.py',
                 'scripts/build_claude_repeat_findings.py',
                 'scripts/build_repeat_findings.py',
                 'scripts/development_benchmark.py'):
        bind(path)
    bind(opus.LABELS, shared.PINNED_SHA[str(opus.LABELS)])
    label_rows = opus._rows(root, opus.LABELS)
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if ([row.get('id') for row in label_rows] != ids or
            any(row.get('review_version') != '0.2' for row in label_rows)):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    plans = {}
    for effort in EFFORTS:
        lane.configure(effort)
        for name in PASSES:
            path = BASE / effort / name / 'manifest.json'
            plan_binding = bind(path)
            plan = json.loads(opus._file(root, path).read_text())
            if plan != lane.plan_data(name):
                raise ValueError('Frozen Sonnet 5.5 v2 plan differs from reconstruction')
            for source in plan['source_bindings']:
                bind(source['path'], source['sha256'])
            plans[effort, name] = (plan, plan_binding)
    return ids, labels, plans, bind, sources


def _price(attempt):
    usage = attempt.get('usage')
    cache = usage.get('cache_creation') if isinstance(usage, dict) else None
    if not isinstance(cache, dict):
        raise ValueError('Sonnet 5.5 cache duration detail missing')
    counts = {'input': usage.get('input_tokens'), 'output': usage.get('output_tokens'),
              'cache5mWrite': cache.get('ephemeral_5m_input_tokens'),
              'cache1hWrite': cache.get('ephemeral_1h_input_tokens'),
              'cacheRead': usage.get('cache_read_input_tokens')}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError('Sonnet 5.5 token usage missing or invalid')
    if usage.get('cache_creation_input_tokens') != counts['cache5mWrite'] + counts['cache1hWrite']:
        raise ValueError('Sonnet 5.5 cache creation count differs')
    amount = sum((Decimal(counts[name]) * rate for name, rate in PRICES.items()), Decimal(0)) / 1_000_000
    reported = opus._money(attempt.get('cli_estimated_api_equivalent_usd'))
    model_usage = attempt.get('model_usage', {}).get(lane.MODEL, {})
    model_reported = opus._money(model_usage.get('costUSD'))
    if (reported is None or model_reported is None or
            abs(reported - amount) > Decimal('0.0000001') or
            abs(model_reported - amount) > Decimal('0.0000001') or
            model_usage.get('canonicalModel') != lane.MODEL or
            model_usage.get('costBasis') != 'list' or
            model_usage.get('provider') != 'firstParty'):
        raise ValueError('CLI Sonnet 5.5 list-price estimate or identity differs')
    return counts, amount


def _usage(attempts):
    usage = opus._usage(attempts)
    priced = [_price(attempt) for attempt in attempts if isinstance(attempt.get('usage'), dict)]
    usage['unpricedRequests'] = len(attempts) - len(priced)
    usage['tokensByPriceCategory'] = {
        name: (sum(counts[name] for counts, _ in priced)
               if len(priced) == len(attempts) else None) for name in PRICES}
    exact_total = sum((amount for _, amount in priced), Decimal(0))
    usage['calculatedApiEquivalentUsd'] = str(exact_total) if len(priced) == len(attempts) else None
    usage['cliListPriceEstimateUsd'] = str(exact_total) if len(priced) == len(attempts) else None
    usage['priceUsdPerMillionTokens'] = {key: str(value) for key, value in PRICES.items()}
    usage['priceSource'] = PRICE_URL
    durations = [attempt.get('cli_api_duration_ms') for attempt in attempts]
    usage['cliReportedApiSeconds'] = (sum(durations) / 1000 if durations and
        all(type(value) in (int, float) and math.isfinite(value) and value >= 0
            for value in durations) else None)
    usage['cliApiDurationNote'] = 'CLI-reported API duration; not pure model inference time.'
    return usage


def _recovered_smoke(root, plan, bind):
    path = BASE / 'low/pass1/P0/offline-smoke-admission.json'
    binding = bind(path)
    sidecar = json.loads(opus._file(root, path).read_text())
    if (sidecar.get('schema') != 'claude-sonnet55-v2-offline-smoke-admission-v1' or
            sidecar.get('configuration_id') != plan['configuration_id'] or
            sidecar.get('admission') != 'accepted_offline_from_retained_raw' or
            sidecar.get('original_status') != 'service_error' or
            sidecar.get('reparsed_status') != 'ok' or
            sidecar.get('v2_isolation_ok') is not True or
            sidecar.get('reference_labels_read') is not False or
            sidecar.get('inference_performed') is not False or
            sidecar.get('v2_manifest_sha256') != opus._sha(opus._file(root, BASE / 'low/pass1/manifest.json')) or
            sidecar.get('v2_controller_sha256') != opus._sha(opus._file(root, 'scripts/claude_sonnet55_matched3_v2.py'))):
        raise ValueError('Sonnet 5.5 offline smoke admission differs')
    originals = sidecar.get('original_evidence_sha256', {})
    required = {'smoke.claim.json', 'smoke.attempts.jsonl', 'smoke.records.jsonl',
                'smoke.journal.jsonl', 'smoke.batch-000.raw.jsonl', 'smoke.root-review.json'}
    if set(originals) != required:
        raise ValueError('Original Sonnet smoke evidence bindings differ')
    folder = Path('results/repeatability-v1/claude-sonnet55-fresh-matched3/low/pass1/P0')
    evidence = {name: bind(folder / name, originals[name]) for name in sorted(required)}
    attempt = opus._rows(root, folder / 'smoke.attempts.jsonl')
    records = opus._rows(root, folder / 'smoke.records.jsonl')
    journal = opus._rows(root, folder / 'smoke.journal.jsonl')
    raw = opus._rows(root, folder / 'smoke.batch-000.raw.jsonl')
    if (len(attempt) != 1 or len(raw) != 1 or len(records) != 3 or
            attempt[0].get('status') != 'service_error' or
            attempt[0].get('error_type') != 'IsolationIdentityOrBillingGuard' or
            journal[-1].get('event') != 'phase_stopped' or
            [record.get('status') for record in records] != ['service_error'] * 3):
        raise ValueError('Original Sonnet smoke failure accounting differs')
    body = json.loads(raw[0]['stdout'])
    planned = plan['conditions']['P0']['smoke']
    parsed = parse_batch_result(body, raw[0]['exit_code'], planned['record_ids'])
    if (parsed['status'] != 'ok' or parsed['prediction'] != attempt[0].get('prediction') or
            not lane.isolation_ok_v2({**parsed, 'raw_events': safe_diagnostic(body),
                                      'requested_model': lane.MODEL}) or
            attempt[0].get('raw_capture_sha256') != evidence['smoke.batch-000.raw.jsonl']['sha256']):
        raise ValueError('Original Sonnet smoke raw output fails v2 admission')
    _price(attempt[0])
    return {'state': 'offline_admitted_original_guard_failure',
            'originalStatus': 'service_error', 'offlineRawStatus': 'ok',
            'recordCount': 3, 'requestCount': 1,
            'usage': _usage(attempt),
            'evidence': {'admission': binding, 'original': evidence}}


def _phase(root, effort, name, condition, phase, plan, plan_binding, bind):
    folder = BASE / effort / name / condition
    journal_path = folder / f'{phase}.journal.jsonl'
    path = opus._file(root, journal_path)
    if not path.exists():
        return {'state': 'not_started', 'score': None}, None
    events = opus._terminal(root, journal_path)
    if events is None:
        return {'state': 'running_or_ambiguous', 'score': None}, None
    requests = ([plan['conditions'][condition]['smoke']] if phase == 'smoke' else
                plan['conditions'][condition]['development'])
    claim_path = folder / f'{phase}.claim.json'
    review_path = folder / f'{phase}.root-review.json'
    attempt_path = folder / f'{phase}.attempts.jsonl'
    records_path = folder / f'{phase}.records.jsonl'
    claim = json.loads(opus._file(root, claim_path).read_text())
    review_binding = bind(review_path, claim.get('root_review_sha256'))
    review = json.loads(opus._file(root, review_path).read_text())
    source_hashes = {Path(item['path']): item['sha256'] for item in plan['source_bindings']}
    smoke_hash = None
    if phase == 'development':
        if (effort, name, condition) == lane.RECOVERED:
            smoke_path = BASE / 'low/pass1/P0/offline-smoke-admission.json'
        else:
            smoke_path = folder / 'smoke-inspection.json'
        smoke_hash = bind(smoke_path)['sha256']
        if smoke_path.name == 'smoke-inspection.json':
            inspection = json.loads(opus._file(root, smoke_path).read_text())
            if inspection.get('inspection') != 'accepted_unchanged':
                raise ValueError('Sonnet smoke inspection differs')
            for key, filename in (('attempts_sha256', 'smoke.attempts.jsonl'),
                                  ('records_sha256', 'smoke.records.jsonl'),
                                  ('journal_sha256', 'smoke.journal.jsonl')):
                if inspection.get(key) != opus._sha(opus._file(root, folder / filename)):
                    raise ValueError('Sonnet smoke inspection hash differs')
    if (claim.get('configuration_id') != plan['configuration_id'] or
            claim.get('pass') != name or claim.get('condition') != condition or
            claim.get('phase') != phase or
            claim.get('manifest_sha256') != plan_binding['sha256'] or
            claim.get('cli_version') != lane.RUNTIME or
            review.get('schema') != 'claude-sonnet55-fresh-matched3-v2-root-review-v1' or
            review.get('approved') is not True or
            review.get('configuration_id') != plan['configuration_id'] or
            review.get('pass') != name or
            review.get('manifest_sha256') != plan_binding['sha256'] or
            review.get('controller_sha256') != source_hashes[Path('scripts/claude_sonnet55_matched3_v2.py')] or
            review.get('mechanics_sha256') != source_hashes[Path('scripts/claude_repeat_study.py')] or
            review.get('roster_sha256') != source_hashes[Path('scripts/claude_repeat_roster.py')] or
            review.get('private_preflight_sha256') != claim.get('private_preflight_sha256') or
            review.get('cli_path') != str(lane.CLI) or
            review.get('cli_version') != lane.RUNTIME or
            review.get('approved_phases') != [{'condition': condition, 'phase': phase}] or
            review.get('smoke_evidence_sha256') != smoke_hash):
        raise ValueError('Sonnet v2 claim or root review differs from plan')
    bindings = {'claim': bind(claim_path), 'rootReview': review_binding,
                'journal': bind(journal_path), 'attempts': bind(attempt_path),
                'records': bind(records_path)}
    attempts = opus._rows(root, attempt_path)
    records = opus._rows(root, records_path)
    if (events[0] != {'event': 'phase_started', 'pass': name,
                      'condition': condition, 'phase': phase} or
            len(attempts) > len(requests) or
            len(events) != 2 * len(attempts) + 2 or
            [event.get('event') for event in events] != [
                'phase_started', *['dispatch_intent', 'request_completed'] * len(attempts),
                events[-1]['event']]):
        raise ValueError('Sonnet v2 journal sequence differs')
    raw_bindings = []
    for index, attempt in enumerate(attempts):
        planned = requests[index]
        members = planned['record_ids']
        started, finished = events[1 + 2 * index:3 + 2 * index]
        if ((started.get('batch_index'), started.get('record_ids'),
             finished.get('batch_index'), finished.get('status')) !=
                (planned['batch_index'], members, planned['batch_index'], attempt.get('status')) or
            (attempt.get('configuration_id'), attempt.get('pass'), attempt.get('repeat'),
             attempt.get('condition'), attempt.get('phase'), attempt.get('batch_index'),
             attempt.get('ids'), attempt.get('request'), attempt.get('input_sha256'),
             attempt.get('policy_sha256'), attempt.get('schema_sha256'),
             attempt.get('requested_model'), attempt.get('effort'),
             attempt.get('auth_method'), attempt.get('cli_version'),
             attempt.get('controller_retries'), attempt.get('reference_labels_read')) !=
                (plan['configuration_id'], name, name, condition, phase,
                 planned['batch_index'], members, planned['request'],
                 digest(planned['input_text']), digest(planned['request']['system']),
                 digest(json.dumps(planned['request']['schema'], sort_keys=True)),
                 lane.MODEL, effort, 'claude.ai', lane.RUNTIME, 0, False)):
            raise ValueError('Sonnet v2 attempt differs from frozen request')
        if attempt.get('actual_billed_usd') is not None or attempt.get('subscription_quota_consumed') is not None:
            raise ValueError('Sonnet attempt claims unavailable subscription billing')
        raw_path = folder / f"{phase}.batch-{planned['batch_index']:03d}.raw.jsonl"
        captured = attempt.get('raw_capture_file') is not None
        if captured:
            if (attempt['raw_capture_file'] != raw_path.name or
                    not isinstance(attempt.get('raw_capture_sha256'), str) or
                    re.fullmatch(r'[0-9a-f]{64}', attempt['raw_capture_sha256']) is None):
                raise ValueError('Sonnet v2 raw capture filename or hash differs')
            raw_binding = bind(raw_path, attempt.get('raw_capture_sha256'))
            raw_bindings.append(raw_binding)
            raw_rows = opus._rows(root, raw_path)
            if len(raw_rows) != 1:
                raise ValueError('Sonnet v2 raw capture count differs')
            raw = raw_rows[0]
            if (raw.get('schema'), raw.get('repeat'), raw.get('condition'),
                    raw.get('phase'), raw.get('batch_index'), raw.get('record_ids'),
                    raw.get('input_sha256'), raw.get('exit_code'), raw.get('timed_out')) != (
                        'claude-repeat-raw-capture-v1', name, condition, phase,
                        planned['batch_index'], members, attempt['input_sha256'],
                        attempt.get('exit_code'),
                        attempt.get('error_type') == 'TimeoutExpired'):
                raise ValueError('Sonnet v2 raw capture differs from attempt')
            try:
                body = json.loads(raw['stdout'])
                parsed = parse_batch_result(body, raw['exit_code'], members)
            except (ValueError, TypeError):
                body = parsed = None
        else:
            if (attempt.get('status') != 'service_error' or
                    attempt.get('raw_capture_sha256') is not None or
                    opus._file(root, raw_path).exists()):
                raise ValueError('Sonnet v2 missing raw capture differs from failure')
            body = parsed = None
        if parsed is None:
            if attempt['status'] != 'service_error' or any(attempt.get(key) is not None for key in (
                    'prediction', 'usage', 'model_usage', 'cli_estimated_api_equivalent_usd')):
                raise ValueError('Sonnet v2 unparseable capture claims parsed output')
        else:
            diagnostic = safe_diagnostic(body)
            guarded = lane.isolation_ok_v2({**parsed, 'raw_events': diagnostic,
                                            'requested_model': lane.MODEL})
            if ((attempt['status'] in ('ok', 'invalid_output') and
                    (attempt['status'] != parsed['status'] or not guarded)) or
                    (attempt['status'] == 'service_error' and parsed['status'] != 'service_error' and
                     (attempt.get('error_type') != 'IsolationIdentityOrBillingGuard' or guarded)) or
                    attempt.get('raw_events') != diagnostic or
                    any(attempt.get(key) != parsed.get(key) for key in (
                        'prediction', 'usage', 'model_usage', 'returned_models',
                        'init_model', 'init_tools', 'init_mcp_servers', 'init_skills',
                        'init_plugins', 'assistant_models', 'overage_observed',
                        'cli_duration_ms', 'cli_api_duration_ms',
                        'cli_estimated_api_equivalent_usd'))):
                raise ValueError('Sonnet v2 parsed raw capture or isolation differs')
        if attempt['status'] not in ('ok', 'invalid_output', 'service_error'):
            raise ValueError('Unknown Sonnet v2 attempt status')
        positions = records[index * len(members):(index + 1) * len(members)]
        predictions = ({row['id']: {key: value for key, value in row.items() if key != 'id'}
                        for row in attempt['prediction']['records']}
                       if attempt['status'] == 'ok' else {})
        if (len(positions) != len(members) or
                (attempt['status'] == 'ok' and set(predictions) != set(members))):
            raise ValueError('Sonnet v2 response membership differs')
        for pos, record in enumerate(positions):
            rid = members[pos]
            if (record.get('id'), record.get('status'), record.get('prediction'),
                    record.get('pass'), record.get('condition'), record.get('phase'),
                    record.get('batch_index'), record.get('batch_position'),
                    record.get('batch_record_ids'), record.get('requested_model'),
                    record.get('effort')) != (
                        rid, attempt['status'], predictions.get(rid), name, condition, phase,
                        planned['batch_index'], pos + 1, members, lane.MODEL, effort):
                raise ValueError('Sonnet v2 record differs from saved attempt')
        if isinstance(attempt.get('usage'), dict):
            _price(attempt)
    if len(records) != sum(len(requests[i]['record_ids']) for i in range(len(attempts))):
        raise ValueError('Sonnet v2 record evidence has extra rows')
    complete = events[-1]['event'] == 'phase_completed'
    if complete:
        if (len(attempts) != len(requests) or any(a['status'] != 'ok' for a in attempts) or
                (events[-1].get('request_count'), events[-1].get('record_count')) !=
                    (len(requests), 3 if phase == 'smoke' else 60)):
            raise ValueError('Sonnet v2 completed phase lacks full valid evidence')
    elif (not attempts or attempts[-1]['status'] == 'ok' or
          events[-1].get('event') != 'phase_stopped'):
        raise ValueError('Sonnet v2 stopped phase differs')
    bindings['rawCaptures'] = raw_bindings
    entry = {'state': 'complete' if complete else 'stopped', 'score': None,
             'recordCount': len(records), 'requestCount': len(attempts),
             'usage': _usage(attempts), 'evidence': bindings}
    if complete and phase == 'development':
        indexed = {record['id']: record for record in records}
        entry['score'] = indexed
        return entry, indexed
    return entry, None


def build(root=ROOT):
    root = Path(root)
    ids, labels, plans, bind, sources = _context(root)
    cells = {effort: {name: {} for name in PASSES} for effort in EFFORTS}
    indexed = {}
    for effort in EFFORTS:
        lane.configure(effort)
        for name in PASSES:
            plan, plan_binding = plans[effort, name]
            for condition in CONDITIONS:
                if (effort, name, condition) == lane.RECOVERED:
                    smoke = _recovered_smoke(root, plan, bind)
                else:
                    smoke, _ = _phase(root, effort, name, condition, 'smoke',
                                      plan, plan_binding, bind)
                development, records = _phase(root, effort, name, condition, 'development',
                                              plan, plan_binding, bind)
                if development['state'] == 'complete':
                    if smoke['state'] not in ('complete', 'offline_admitted_original_guard_failure'):
                        raise ValueError('Closed development lacks admitted smoke')
                    development['score'] = shared.score(records, labels, ids)
                    indexed[effort, name, condition] = records
                cells[effort][name][condition] = {'smoke': smoke, 'development': development}
    def scored(effort, name, condition):
        return cells[effort][name][condition]['development']['score'] is not None
    summaries, flips, deltas, spreads = {}, [], [], {}
    for effort in EFFORTS:
        summaries[effort], spreads[effort] = {}, {}
        for condition in CONDITIONS:
            for i, left in enumerate(PASSES):
                for right in PASSES[i + 1:]:
                    if scored(effort, left, condition) and scored(effort, right, condition):
                        flips.append({'effort': effort, 'condition': condition,
                                      'from': left, 'to': right,
                                      **shared.flip(indexed[effort, left, condition],
                                                    indexed[effort, right, condition], ids)})
            scores = [cells[effort][name][condition]['development']['score']
                      for name in PASSES if scored(effort, name, condition)]
            summaries[effort][condition] = {
                'allFour': opus._stats([x['allFour'] for x in scores]),
                'fields': {field: opus._stats([x['fields'][field] for x in scores])
                           for field in FIELDS}}
        for name in PASSES:
            for target in ('P1', 'P2'):
                if scored(effort, name, 'P0') and scored(effort, name, target):
                    baseline = cells[effort][name]['P0']['development']['score']
                    variant = cells[effort][name][target]['development']['score']
                    deltas.append({'effort': effort, 'pass': name, 'from': 'P0', 'to': target,
                                   'denominator': 60,
                                   'allFour': variant['allFour'] - baseline['allFour'],
                                   'fields': {field: variant['fields'][field] - baseline['fields'][field]
                                              for field in FIELDS}})
        for target in ('P1', 'P2'):
            observed = [item for item in deltas if item['effort'] == effort and item['to'] == target]
            spreads[effort][target] = {'completedPairs': len(observed),
                'allFourRange': ([min(item['allFour'] for item in observed),
                                  max(item['allFour'] for item in observed)]
                                 if len(observed) == 3 else None),
                'fieldRanges': {field: ([min(item['fields'][field] for item in observed),
                                         max(item['fields'][field] for item in observed)]
                                        if len(observed) == 3 else None) for field in FIELDS}}
    return {'schema': 'claude-sonnet55-fresh-matched3-findings-v1',
            'displayName': 'Claude Sonnet 5.5 · fresh matched three · batch 10',
            'model': lane.MODEL, 'provider': 'Claude subscription',
            'efforts': list(EFFORTS), 'passOrder': list(PASSES),
            'conditionOrder': list(CONDITIONS), 'plannedCells': 36,
            'completedCells': sum(scored(e, p, c) for e in EFFORTS
                                  for p in PASSES for c in CONDITIONS),
            'denominatorPerCell': 60, 'referenceVersion': '0.2',
            'referenceStatus': 'Frozen provisional v0.2 key; project owner confirmed human checks of all 60 reviews on 2026-10-02',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items()))
                                     for field in FIELDS},
            'originalGuardFailure': {'effort': 'low', 'pass': 'pass1', 'condition': 'P0',
                'originalStatus': 'service_error', 'replayed': False,
                'offlineAdmission': 'separate v2 sidecar; original evidence unchanged'},
            'cells': cells, 'threePassSummary': summaries,
            'pairwiseFlips': flips, 'withinPassPromptDeltas': deltas,
            'pairedDeltaSpread': spreads, 'sourceBindings': sources,
            'pricing': {'unit': 'USD per million tokens',
                        'rates': {key: str(value) for key, value in PRICES.items()},
                        'source': PRICE_URL, 'batchApiDiscountApplied': False,
                        'note': 'CLI batch of ten reviews is one ordinary request, not Anthropic Message Batches API.'},
            'limitations': [
                'All 36 cells remain in view; open cells have no score.',
                'The original low/P0 smoke ended as a guard failure and is retained separately.',
                'Hidden builtin plugin-authoring prompt effects, serving revision, CLI internal retries, and effective seed are not fully observable.',
                'Client wall-clock and CLI API duration are not pure model inference time.',
                'API-equivalent list-price estimates are not subscription charges; actual billed cost and quota consumed are unavailable.',
                'The same 60 synthetic development reviews are reused, not independent new observations.']}


def check_public(output_dir, root=ROOT):
    """Verify the published projection without reading any private original."""
    root = Path(root).resolve()
    report = verify_public(Path(output_dir), root)
    if (report.get('schema') != 'claude-sonnet55-fresh-matched3-findings-v1' or
            report.get('plannedCells') != 36 or report.get('denominatorPerCell') != 60 or
            report.get('efforts') != list(EFFORTS) or
            report.get('passOrder') != list(PASSES) or
            report.get('conditionOrder') != list(CONDITIONS)):
        raise ValueError('Public Sonnet 5.5 report frame differs')
    label_bindings = [item for item in report['sourceBindings']
                      if item.get('originalPath') == str(opus.LABELS)]
    if len(label_bindings) != 1:
        raise ValueError('Public Sonnet 5.5 reference binding missing')
    labels_path = root / label_bindings[0]['path']
    label_rows = [json.loads(line) for line in labels_path.read_text().splitlines()]
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if [row.get('id') for row in label_rows] != ids:
        raise ValueError('Public Sonnet 5.5 references differ')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    completed = 0
    for effort in EFFORTS:
        for name in PASSES:
            for condition in CONDITIONS:
                cell = report['cells'][effort][name][condition]
                development = cell['development']
                if development['state'] != 'complete':
                    if development['score'] is not None:
                        raise ValueError('Open public Sonnet 5.5 cell is scored')
                    continue
                if cell['smoke']['state'] not in ('complete', 'offline_admitted_original_guard_failure'):
                    raise ValueError('Public Sonnet 5.5 development lacks smoke admission')
                records_path = root / development['evidence']['records']['path']
                rows = [json.loads(line) for line in records_path.read_text().splitlines()]
                if len(rows) != 60 or [row['id'] for row in rows] != ids:
                    raise ValueError('Public Sonnet 5.5 score membership differs')
                score = shared.score({row['id']: row for row in rows}, labels, ids)
                if score != development['score']:
                    raise ValueError('Public Sonnet 5.5 score differs from projected records')
                completed += 1
    if completed != report['completedCells']:
        raise ValueError('Public Sonnet 5.5 completion count differs')
    original = report['cells']['low']['pass1']['P0']['smoke']
    if (original['state'] != 'offline_admitted_original_guard_failure' or
            original['originalStatus'] != 'service_error' or
            original['offlineRawStatus'] != 'ok' or
            report['originalGuardFailure']['replayed'] is not False):
        raise ValueError('Public Sonnet 5.5 original guard failure differs')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--check-public', type=Path,
                        help='Verify exported public evidence without private originals')
    args = parser.parse_args(argv)
    if args.check_public is not None:
        check_public(args.check_public)
        print('Sonnet 5.5 public evidence checked')
        return
    content = json.dumps(build(ROOT), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print('Sonnet 5.5 matched-three report checked')


if __name__ == '__main__':
    main()
