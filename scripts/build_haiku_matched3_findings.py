#!/usr/bin/env python3
"""Build source-bound findings for the separate fresh matched-three Haiku lane."""

import argparse
from collections import Counter
import json
from pathlib import Path

import build_claude_repeat_findings as opus
import build_repeat_findings as shared
import claude_haiku_matched3 as haiku
from claude_batch_benchmark import parse_batch_result, isolation_ok
from claude_benchmark import safe_diagnostic
from development_benchmark import digest

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/claude-haiku-fresh-matched3')
OUTPUT = Path('public-site/haiku-fresh-matched3.json')
PASSES = ('pass1', 'pass2', 'pass3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS


def _context(root):
    bind, sources = opus._binder(root)
    for path in ('scripts/build_haiku_matched3_findings.py',
                 'scripts/build_claude_repeat_findings.py',
                 'scripts/build_repeat_findings.py',
                 'scripts/development_benchmark.py'):
        bind(path)
    bind(opus.LABELS, shared.PINNED_SHA[str(opus.LABELS)])
    labels_rows = opus._rows(root, opus.LABELS)
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if ([row.get('id') for row in labels_rows] != ids or
            any(row.get('review_version') != '0.2' for row in labels_rows)):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels = {row['id']: row['proposed_labels'] for row in labels_rows}
    historical = bind(haiku.RECONCILIATION)
    reconciliation = json.loads(opus._file(root, haiku.RECONCILIATION).read_text())
    if (reconciliation.get('counts') != {'original_valid': 10,
                                         'original_failed_attempted': 10,
                                         'suffix_valid': 40,
                                         'suffix_failed_attempted': 0,
                                         'never_sent': 0} or
            reconciliation.get('valid_prediction_count') != 50):
        raise ValueError('Historical Haiku disposition differs')
    plans = {}
    for name in PASSES:
        path = BASE / name / 'manifest.json'
        binding = bind(path)
        plan = json.loads(opus._file(root, path).read_text())
        if plan != haiku.plan_data(name):
            raise ValueError('Frozen Haiku plan differs from reconstruction')
        for source in plan['source_bindings']:
            bind(source['path'], source['sha256'])
        plans[name] = (plan, binding)
    return ids, labels, historical, plans, bind, sources


def _phase(root, name, condition, phase, plan, plan_binding, ids, labels, bind):
    folder = BASE / name / condition
    journal = folder / f'{phase}.journal.jsonl'
    events = opus._terminal(root, journal)
    if events is None:
        return None, 'open_or_not_started', None
    requests = ([plan['conditions'][condition]['smoke']] if phase == 'smoke' else
                plan['conditions'][condition]['development'])
    claim_path = folder / f'{phase}.claim.json'
    attempts_path = folder / f'{phase}.attempts.jsonl'
    records_path = folder / f'{phase}.records.jsonl'
    review_path = folder / f'{phase}.root-review.json'
    claim = json.loads(opus._file(root, claim_path).read_text())
    if (set(claim) != {'configuration_id', 'pass', 'condition', 'phase', 'manifest_sha256',
                       'root_review_sha256', 'private_preflight_sha256', 'cli_version',
                       'claimed_utc'} or
            (claim['configuration_id'], claim['pass'], claim['condition'], claim['phase'],
             claim['manifest_sha256'], claim['cli_version']) != (
                 haiku.CONFIG, name, condition, phase, plan_binding['sha256'], haiku.RUNTIME)):
        raise ValueError('Haiku claim differs from frozen admission')
    review_binding = bind(review_path, claim['root_review_sha256'])
    review = json.loads(opus._file(root, review_path).read_text())
    source_hashes = {Path(item['path']): item['sha256'] for item in plan['source_bindings']}
    allowed = {'schema', 'approved', 'configuration_id', 'pass', 'manifest_sha256',
               'controller_sha256', 'mechanics_sha256', 'roster_sha256',
               'private_preflight_sha256', 'cli_path', 'cli_version',
               'approved_phases', 'review_note'}
    if (set(review) != allowed or
            review.get('schema') != 'claude-haiku-fresh-matched3-root-review-v1' or
            review.get('approved') is not True or review.get('configuration_id') != haiku.CONFIG or
            review.get('pass') != name or review.get('manifest_sha256') != plan_binding['sha256'] or
            review.get('controller_sha256') != source_hashes[Path('scripts/claude_haiku_matched3.py')] or
            review.get('mechanics_sha256') != source_hashes[Path('scripts/claude_repeat_study.py')] or
            review.get('roster_sha256') != source_hashes[Path('scripts/claude_repeat_roster.py')] or
            review.get('private_preflight_sha256') != claim['private_preflight_sha256'] or
            review.get('cli_path') != str(haiku.CLI) or review.get('cli_version') != haiku.RUNTIME or
            review.get('approved_phases') != [{'condition': condition, 'phase': phase}] or
            not str(review.get('review_note', '')).strip()):
        raise ValueError('Haiku root review differs from claim or plan')
    bindings = {'claim': bind(claim_path), 'rootReview': review_binding,
                'journal': bind(journal), 'attempts': bind(attempts_path),
                'records': bind(records_path)}
    attempts = opus._rows(root, attempts_path)
    records = opus._rows(root, records_path)
    if (events[0] != {'event': 'phase_started', 'pass': name,
                      'condition': condition, 'phase': phase} or
            len(attempts) > len(requests) or len(events) != 2 * len(attempts) + 2 or
            [event.get('event') for event in events] != [
                'phase_started', *['dispatch_intent', 'request_completed'] * len(attempts),
                events[-1]['event']]):
        raise ValueError('Haiku journal sequence differs')
    indexed = {}
    raw_bindings = []
    for index, attempt in enumerate(attempts):
        planned = requests[index]
        members = planned['record_ids']
        started, finished = events[1 + 2 * index:3 + 2 * index]
        if (started.get('batch_index'), started.get('record_ids'),
                finished.get('batch_index'), finished.get('status')) != (
                planned['batch_index'], members, planned['batch_index'], attempt.get('status')):
            raise ValueError('Haiku dispatch journal differs from attempt')
        if (attempt.get('configuration_id'), attempt.get('pass'), attempt.get('repeat'),
                attempt.get('condition'), attempt.get('phase'), attempt.get('batch_index'),
                attempt.get('ids'), attempt.get('request'), attempt.get('input_sha256'),
                attempt.get('policy_sha256'), attempt.get('schema_sha256'),
                attempt.get('requested_model'), attempt.get('effort'),
                attempt.get('auth_method'), attempt.get('cli_version'),
                attempt.get('controller_retries'), attempt.get('reference_labels_read')) != (
                haiku.CONFIG, name, name, condition, phase, planned['batch_index'], members,
                planned['request'], digest(planned['input_text']),
                digest(planned['request']['system']),
                digest(json.dumps(planned['request']['schema'], sort_keys=True)),
                haiku.MODEL, haiku.EFFORT, 'claude.ai', haiku.RUNTIME, 0, False):
            raise ValueError('Haiku attempt differs from frozen request')
        if attempt.get('actual_billed_usd') is not None or attempt.get('subscription_quota_consumed') is not None:
            raise ValueError('Haiku attempt asserts unavailable billing attribution')
        raw_path = folder / attempt['raw_capture_file']
        if raw_path.name != f"{phase}.batch-{planned['batch_index']:03d}.raw.jsonl":
            raise ValueError('Haiku raw capture path changed')
        raw_binding = bind(raw_path, attempt['raw_capture_sha256'])
        raw_bindings.append(raw_binding)
        raw = opus._rows(root, raw_path)
        if len(raw) != 1:
            raise ValueError('Haiku raw capture count differs')
        raw = raw[0]
        if (raw.get('schema'), raw.get('repeat'), raw.get('condition'), raw.get('phase'),
                raw.get('batch_index'), raw.get('record_ids'), raw.get('input_sha256'),
                raw.get('exit_code'), raw.get('timed_out')) != (
                'claude-repeat-raw-capture-v1', name, condition, phase,
                planned['batch_index'], members, attempt['input_sha256'],
                attempt.get('exit_code'), attempt.get('error_type') == 'TimeoutExpired'):
            raise ValueError('Haiku raw capture differs from attempt')
        try:
            body = json.loads(raw['stdout'])
            parsed = parse_batch_result(body, raw['exit_code'], members)
        except (ValueError, TypeError):
            body = parsed = None
        if parsed is None:
            if attempt['status'] != 'service_error' or any(attempt.get(key) is not None for key in (
                    'prediction', 'usage', 'model_usage', 'cli_estimated_api_equivalent_usd')):
                raise ValueError('Haiku attempt claims fields absent from raw capture')
        else:
            if attempt['status'] in ('ok', 'invalid_output') and parsed['status'] != attempt['status']:
                raise ValueError('Haiku status differs from raw capture')
            if (attempt['status'] == 'service_error' and parsed['status'] != 'service_error' and
                    (attempt.get('error_type') != 'IsolationIdentityOrBillingGuard' or
                     isolation_ok({**attempt, 'raw_events': safe_diagnostic(body)}))):
                raise ValueError('Haiku service error lacks failed identity guard')
            for key in ('prediction', 'raw_response', 'usage', 'model_usage', 'returned_models',
                        'init_model', 'init_tools', 'init_mcp_servers', 'init_skills', 'init_plugins',
                        'assistant_models', 'overage_observed', 'rate_limit_events',
                        'cli_duration_ms', 'cli_api_duration_ms', 'cli_estimated_api_equivalent_usd'):
                if parsed.get(key) != attempt.get(key):
                    raise ValueError(f'Haiku {key} differs from raw capture')
            if attempt.get('raw_events') != safe_diagnostic(body):
                raise ValueError('Haiku parsed events differ from raw capture')
            if attempt['status'] == 'ok' and not isolation_ok({**attempt, 'raw_events': safe_diagnostic(body)}):
                raise ValueError('Haiku raw capture fails isolation')
        if attempt['status'] not in ('ok', 'invalid_output', 'service_error'):
            raise ValueError('Unknown Haiku attempt status')
        positions = records[index * len(members):(index + 1) * len(members)]
        predictions = ({row['id']: {key: value for key, value in row.items() if key != 'id'}
                        for row in attempt.get('prediction', {}).get('records', [])}
                       if attempt['status'] == 'ok' else {})
        if attempt['status'] == 'ok' and (len(predictions) != len(members) or set(predictions) != set(members)):
            raise ValueError('Haiku prediction membership differs')
        if len(positions) != len(members):
            raise ValueError('Haiku record count differs from batch')
        for pos, record in enumerate(positions):
            rid = members[pos]
            if (record.get('id'), record.get('status'), record.get('prediction'),
                    record.get('pass'), record.get('condition'), record.get('phase'),
                    record.get('batch_index'), record.get('batch_position'),
                    record.get('batch_record_ids'), record.get('requested_model'),
                    record.get('effort')) != (
                    rid, attempt['status'], predictions.get(rid), name, condition, phase,
                    planned['batch_index'], pos + 1, members, haiku.MODEL, haiku.EFFORT):
                raise ValueError('Haiku record differs from saved attempt')
            indexed[rid] = record
    if len(records) != sum(len(requests[i]['record_ids']) for i in range(len(attempts))):
        raise ValueError('Haiku record evidence has extra rows')
    complete = events[-1]['event'] == 'phase_completed'
    if complete:
        if (len(attempts) != len(requests) or any(a['status'] != 'ok' for a in attempts) or
                (events[-1].get('request_count'), events[-1].get('record_count')) != (
                    len(requests), 3 if phase == 'smoke' else 60)):
            raise ValueError('Haiku completed phase is incomplete')
    elif (not attempts or attempts[-1]['status'] == 'ok' or
          events[-1].get('batch_index') != requests[len(attempts) - 1]['batch_index']):
        raise ValueError('Haiku stopped phase lacks failed attempt')
    if phase == 'development':
        for rid in ids:
            indexed.setdefault(rid, {'id': rid, 'status': 'never_sent', 'prediction': None})
        score = shared.score(indexed, labels, ids)
    else:
        score = None
    bindings['rawCaptures'] = raw_bindings
    return {'completionStatus': 'complete' if complete else 'partial',
            'terminalEvent': events[-1]['event'], 'finishedRequests': len(attempts),
            'score': score, 'usage': opus._usage(attempts), 'evidence': bindings}, None, indexed


def build(root=ROOT):
    root = Path(root)
    ids, labels, historical, plans, bind, sources = _context(root)
    data = {name: {} for name in PASSES}
    indexed = {name: {} for name in PASSES}
    missing = []
    partial = []
    for name in PASSES:
        plan, plan_binding = plans[name]
        for condition in CONDITIONS:
            smoke, _, _ = _phase(root, name, condition, 'smoke', plan, plan_binding,
                                 ids, labels, bind)
            if smoke is None or smoke['completionStatus'] != 'complete':
                missing.append({'pass': name, 'condition': condition,
                                'status': 'smoke_open_or_incomplete'})
                continue
            inspection_path = BASE / name / condition / 'smoke-inspection.json'
            if not opus._file(root, inspection_path).exists():
                missing.append({'pass': name, 'condition': condition,
                                'status': 'smoke_uninspected'})
                continue
            inspection = json.loads(opus._file(root, inspection_path).read_text())
            if (inspection.get('inspection'), inspection.get('attempts_sha256'),
                    inspection.get('records_sha256'), inspection.get('journal_sha256')) != (
                    'accepted_unchanged', smoke['evidence']['attempts']['sha256'],
                    smoke['evidence']['records']['sha256'], smoke['evidence']['journal']['sha256']):
                raise ValueError('Haiku smoke inspection differs from evidence')
            bind(inspection_path)
            entry, reason, records = _phase(root, name, condition, 'development',
                                            plan, plan_binding, ids, labels, bind)
            if entry is None:
                missing.append({'pass': name, 'condition': condition, 'status': reason})
                continue
            data[name][condition] = entry
            if entry['completionStatus'] == 'partial':
                partial.append({'pass': name, 'condition': condition,
                                'terminalEvent': entry['terminalEvent'],
                                'finishedRequests': entry['finishedRequests']})
            else:
                indexed[name][condition] = records
    def full(name, condition):
        return condition in data[name] and data[name][condition]['completionStatus'] == 'complete'
    deltas = []
    for name in PASSES:
        for target in ('P1', 'P2'):
            if full(name, 'P0') and full(name, target):
                a, b = data[name]['P0']['score'], data[name][target]['score']
                deltas.append({'pass': name, 'from': 'P0', 'to': target, 'denominator': 60,
                               'allFour': b['allFour'] - a['allFour'],
                               'fields': {field: b['fields'][field] - a['fields'][field]
                                          for field in FIELDS}})
    spread = {}
    for target in ('P1', 'P2'):
        entries = [x for x in deltas if x['to'] == target]
        spread[target] = {'completedPairs': len(entries),
                          'allFourValues': [x['allFour'] for x in entries],
                          'allFourRange': [min(x['allFour'] for x in entries),
                                           max(x['allFour'] for x in entries)] if len(entries) == 3 else None,
                          'fieldRanges': {field: [min(x['fields'][field] for x in entries),
                                                  max(x['fields'][field] for x in entries)]
                                          if len(entries) == 3 else None for field in FIELDS}}
    flips = []
    ranges = {}
    across = {}
    for condition in CONDITIONS:
        for i, left in enumerate(PASSES):
            for right in PASSES[i + 1:]:
                if full(left, condition) and full(right, condition):
                    flips.append({'condition': condition, 'from': left, 'to': right,
                                  **shared.flip(indexed[left][condition], indexed[right][condition], ids)})
        scores = [data[name][condition]['score'] for name in PASSES if full(name, condition)]
        ranges[condition] = {'allFour': opus._stats([x['allFour'] for x in scores]),
                             'fields': {field: opus._stats([x['fields'][field] for x in scores])
                                        for field in FIELDS}}
        if all(full(name, condition) for name in PASSES):
            eligible = [rid for rid in ids if all(shared.outcome(indexed[name][condition][rid]) == 'valid'
                                                  for name in PASSES)]
            across[condition] = {'denominator': len(eligible),
                                 'excludedIds': [rid for rid in ids if rid not in eligible],
                                 'fields': {field: [rid for rid in eligible if len({
                                     indexed[name][condition][rid]['prediction'][field]
                                     for name in PASSES}) > 1] for field in FIELDS},
                                 'fourFieldVector': [rid for rid in eligible if len({tuple(
                                     indexed[name][condition][rid]['prediction'][field] for field in FIELDS)
                                     for name in PASSES}) > 1]}
    return {'schema': 'claude-haiku-fresh-matched3-findings-v1',
            'configuration': haiku.CONFIG,
            'historicalConfiguration': haiku.HISTORICAL,
            'historicalContext': {'firstPassEligible': False,
                                  'P1': {'validPredictions': 50,
                                         'attemptedTransportFailures': 10,
                                         'failureIds': [f'DEV-{i:03d}' for i in range(11, 21)]},
                                  'evidence': historical},
            'displayName': 'Claude Haiku 4.5 · fresh matched three · batch 10',
            'passOrder': list(PASSES),
            'model': haiku.MODEL, 'effort': haiku.EFFORT,
            'provider': 'Claude subscription', 'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items()))
                                     for field in FIELDS},
            'denominator': 60, 'completedConditions': sum(full(name, condition)
                for name in PASSES for condition in CONDITIONS),
            'plannedConditions': 9, 'missingPasses': missing, 'partialPasses': partial,
            'passes': data, 'threePassSummary': ranges, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
            'pairedDeltaSpread': spread, 'sourceBindings': sources,
            'limitations': [
                'The historical Haiku P1 transport failure is retained separately; it is not pass one in this new series.',
                'The same 60 synthetic development records appear in all three passes.',
                'Partial terminal phases keep missing outcomes in the 60-record denominator; open phases are excluded.',
                'CLI internal retries, serving revision, hidden rendering, and effective seed are not controlled or fully observable.',
                'Request duration is client wall-clock time, not model-only inference time.',
                'CLI list-price estimates are not subscription charges. Actual billed cost and quota consumed are unknown.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(ROOT), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print('Haiku fresh matched-three report checked')


if __name__ == '__main__':
    main()
