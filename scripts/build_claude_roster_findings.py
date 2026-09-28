#!/usr/bin/env python3
"""Build offline, source-bound repeat findings for completed Fable 5.1 roster lanes."""
import argparse
from collections import Counter
import json
from pathlib import Path

import build_claude_repeat_findings as opus
import build_repeat_findings as shared
import claude_repeat_roster as roster
from claude_batch_benchmark import parse_batch_result, isolation_ok
from claude_benchmark import safe_diagnostic
from development_benchmark import digest, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/claude-roster-v1')
CONFIGS = tuple(f'fable51-{effort}-phase2-batch10-p0' for effort in ('low', 'medium', 'high', 'xhigh'))
PASSES = ('original', 'repeat2', 'repeat3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS


def _source_context(root, config):
    bind, sources = opus._binder(root)
    bind(opus.LABELS, shared.PINNED_SHA[str(opus.LABELS)])
    rows = opus._rows(root, opus.LABELS)
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if [row.get('id') for row in rows] != ids or any(row.get('review_version') != '0.2' for row in rows):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels = {row['id']: row['proposed_labels'] for row in rows}
    if config not in CONFIGS:
        raise ValueError('Configuration outside Fable report scope')
    bind(roster.COVERAGE)
    pair_path = Path(roster.PAIRS) / config / 'paired-manifest.json'
    bind(pair_path)
    pair = json.loads(opus._file(root, pair_path).read_text())
    model, effort = roster.ROSTER[config]
    controls = pair.get('controls', {})
    if (pair.get('parent_baseline_id') != config or controls.get('requested_model') != model or
            controls.get('effort') != effort or controls.get('workflow') != 'batch10' or
            controls.get('auth_method') != 'claude.ai' or
            controls.get('cli_version') != roster.HISTORICAL_RUNTIME or
            controls.get('controller_retries') != 0):
        raise ValueError('Historical Fable controls changed')
    plans = {}
    for repeat in ('repeat2', 'repeat3'):
        path = BASE / config / repeat / 'manifest.json'
        binding = bind(path)
        plan = json.loads(opus._file(root, path).read_text())
        if plan != roster.plan_data(config, repeat):
            raise ValueError('Frozen Fable plan differs from reconstruction')
        for source in plan['source_bindings']:
            bind(source['path'], source['sha256'])
        plans[repeat] = (plan, binding)
    return ids, labels, pair, plans, bind, sources


def _historical(root, config, condition, pair, plan, ids, labels, bind):
    model, effort = roster.ROSTER[config]
    source = pair['conditions'][condition]
    record_binding = bind(source['predictions']['file'], source['predictions']['sha256'])
    attempt_binding = bind(source['request_evidence']['file'], source['request_evidence']['sha256'])
    records = opus._rows(root, record_binding['path'])
    attempts = opus._rows(root, attempt_binding['path'])
    if len(records) != 60 or [row.get('id') for row in records] != ids or len(attempts) != 6:
        raise ValueError('Historical Fable membership changed')
    indexed = {}
    for index, attempt in enumerate(attempts):
        planned = plan['conditions'][condition]['development'][index]
        members = ids[index * 10:(index + 1) * 10]
        if (attempt.get('request'), attempt.get('ids'), attempt.get('status'),
                attempt.get('requested_model'), attempt.get('effort'), attempt.get('auth_method'),
                attempt.get('cli_version'), attempt.get('controller_retries'),
                attempt.get('input_sha256'), attempt.get('policy_sha256')) != (
                planned['request'], members, 'ok', model, effort, 'claude.ai',
                roster.HISTORICAL_RUNTIME, 0, digest(planned['input_text']),
                digest(planned['request']['system'])):
            raise ValueError('Historical Fable attempt differs from frozen plan')
        prediction = attempt.get('prediction')
        if not isinstance(prediction, dict) or not isinstance(prediction.get('records'), list):
            raise ValueError('Historical Fable batch prediction missing')
        by_id = {row.get('id'): row for row in prediction['records'] if isinstance(row, dict)}
        if len(by_id) != 10 or set(by_id) != set(members):
            raise ValueError('Historical Fable batch prediction membership changed')
        for pos, rid in enumerate(members):
            row = records[index * 10 + pos]
            predicted = {key: value for key, value in by_id[rid].items() if key != 'id'}
            if (row.get('id'), row.get('prediction'), row.get('status'),
                    row.get('batch_record_ids'), row.get('requested_model'), row.get('effort')) != (
                    rid, predicted, 'ok', members, model, effort) or not valid(predicted):
                raise ValueError('Historical Fable record differs from batch')
            indexed[rid] = row
    return {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
            'usage': opus._usage(attempts),
            'evidence': {'records': record_binding, 'attempts': attempt_binding}}, indexed


def _phase(root, config, repeat, condition, phase, plan, plan_binding, ids, labels, bind):
    folder = BASE / config / repeat / condition
    journal_path = folder / f'{phase}.journal.jsonl'
    events = opus._terminal(root, journal_path)
    if events is None:
        return None, 'open_or_not_started', None
    requests = ([plan['conditions'][condition]['smoke']] if phase == 'smoke' else
                plan['conditions'][condition]['development'])
    claim_path = folder / f'{phase}.claim.json'
    attempts_path = folder / f'{phase}.attempts.jsonl'
    records_path = folder / f'{phase}.records.jsonl'
    review_path = folder / f'{phase}-root-review-v1.json'
    claim = json.loads(opus._file(root, claim_path).read_text())
    if (set(claim) != {'configuration_id', 'repeat', 'condition', 'phase', 'manifest_sha256',
                       'root_review_sha256', 'private_preflight_sha256', 'cli_version', 'claimed_utc'} or
            (claim['configuration_id'], claim['repeat'], claim['condition'], claim['phase'],
             claim['manifest_sha256'], claim['cli_version']) !=
            (config, repeat, condition, phase, plan_binding['sha256'], roster.RUNTIME)):
        raise ValueError('Fable claim differs from frozen admission')
    review_binding = bind(review_path, claim['root_review_sha256'])
    review = json.loads(opus._file(root, review_path).read_text())
    source_hashes = {Path(item['path']): item['sha256'] for item in plan['source_bindings']}
    allowed = {'schema', 'approved', 'configuration_id', 'repeat', 'manifest_sha256',
               'controller_sha256', 'mechanics_sha256', 'private_preflight_sha256',
               'cli_path', 'cli_version', 'approved_phases', 'review_note'}
    if (set(review) != allowed or review.get('schema') != 'claude-repeat-roster-root-review-v1' or
            review.get('approved') is not True or review.get('configuration_id') != config or
            review.get('repeat') != repeat or review.get('manifest_sha256') != plan_binding['sha256'] or
            review.get('controller_sha256') != source_hashes[Path('scripts/claude_repeat_roster.py')] or
            review.get('mechanics_sha256') != source_hashes[Path('scripts/claude_repeat_study.py')] or
            review.get('private_preflight_sha256') != claim['private_preflight_sha256'] or
            review.get('cli_path') != str(roster.CLI) or review.get('cli_version') != roster.RUNTIME or
            review.get('approved_phases') != [{'condition': condition, 'phase': phase}] or
            not str(review.get('review_note', '')).strip()):
        raise ValueError('Fable root review differs from claim or plan')
    claim_binding = bind(claim_path)
    journal_binding = bind(journal_path)
    attempt_binding = bind(attempts_path)
    record_binding = bind(records_path)
    attempts = opus._rows(root, attempts_path)
    records = opus._rows(root, records_path)
    if not events or any(events[0].get(k) != v for k, v in
                         {'event': 'phase_started', 'repeat': repeat, 'condition': condition,
                          'phase': phase}.items()):
        raise ValueError('Fable phase start differs')
    if len(attempts) > len(requests) or len(events) != 2 * len(attempts) + 2 or [
            event.get('event') for event in events] != [
            'phase_started', *['dispatch_intent', 'request_completed'] * len(attempts),
            events[-1]['event']]:
        raise ValueError('Fable journal sequence differs')
    model, effort = roster.ROSTER[config]
    indexed = {}
    raw_bindings = []
    for index, attempt in enumerate(attempts):
        planned = requests[index]
        members = planned['record_ids']
        started, finished = events[1 + 2 * index:3 + 2 * index]
        if (started.get('batch_index'), started.get('record_ids'),
                finished.get('batch_index'), finished.get('status')) != (
                planned['batch_index'], members, planned['batch_index'], attempt.get('status')):
            raise ValueError('Fable dispatch journal differs from attempt')
        if (attempt.get('configuration_id'), attempt.get('repeat'), attempt.get('condition'),
                attempt.get('phase'), attempt.get('batch_index'), attempt.get('ids'),
                attempt.get('request'), attempt.get('input_sha256'),
                attempt.get('policy_sha256'), attempt.get('schema_sha256'),
                attempt.get('requested_model'), attempt.get('effort'),
                attempt.get('auth_method'), attempt.get('cli_version'),
                attempt.get('controller_retries')) != (
                config, repeat, condition, phase, planned['batch_index'], members,
                planned['request'], digest(planned['input_text']),
                digest(planned['request']['system']),
                digest(json.dumps(planned['request']['schema'], sort_keys=True)),
                model, effort, 'claude.ai', roster.RUNTIME, 0):
            raise ValueError('Fable attempt differs from frozen request')
        if attempt.get('actual_billed_usd') is not None or attempt.get('subscription_quota_consumed') is not None:
            raise ValueError('Fable attempt claims subscription billing or quota attribution')
        raw_path = folder / attempt['raw_capture_file']
        if raw_path.name != f"{phase}.batch-{planned['batch_index']:03d}.raw.jsonl":
            raise ValueError('Fable raw capture path changed')
        raw_binding = bind(raw_path, attempt['raw_capture_sha256'])
        raw_bindings.append(raw_binding)
        raw = opus._rows(root, raw_path)
        if len(raw) != 1:
            raise ValueError('Fable raw capture count differs')
        raw = raw[0]
        if (raw.get('schema'), raw.get('repeat'), raw.get('condition'), raw.get('phase'),
                raw.get('batch_index'), raw.get('record_ids'), raw.get('input_sha256'),
                raw.get('exit_code'), raw.get('timed_out')) != (
                'claude-repeat-raw-capture-v1', repeat, condition, phase,
                planned['batch_index'], members, attempt['input_sha256'],
                attempt.get('exit_code'), attempt.get('error_type') == 'TimeoutExpired'):
            raise ValueError('Fable raw capture differs from attempt')
        try:
            body = json.loads(raw['stdout'])
            parsed = parse_batch_result(body, raw['exit_code'], members)
        except (ValueError, TypeError):
            body = parsed = None
        if parsed is None:
            if attempt['status'] != 'service_error' or any(attempt.get(key) is not None for key in (
                    'prediction', 'usage', 'model_usage', 'cli_estimated_api_equivalent_usd')):
                raise ValueError('Fable attempt claims parsed fields absent from CLI capture')
        else:
            if attempt['status'] in ('ok', 'invalid_output') and parsed['status'] != attempt['status']:
                raise ValueError('Fable status differs from CLI capture')
            for key in ('prediction', 'raw_response', 'usage', 'model_usage', 'returned_models',
                        'init_model', 'init_tools', 'init_mcp_servers', 'init_skills', 'init_plugins',
                        'assistant_models', 'overage_observed', 'rate_limit_events',
                        'cli_duration_ms', 'cli_api_duration_ms', 'cli_estimated_api_equivalent_usd'):
                if parsed.get(key) != attempt.get(key):
                    raise ValueError(f'Fable {key} differs from CLI capture')
            if attempt.get('raw_events') != safe_diagnostic(body):
                raise ValueError('Fable parsed events differ from CLI capture')
            if attempt['status'] == 'ok' and not isolation_ok({**attempt, 'raw_events': safe_diagnostic(body)}):
                raise ValueError('Fable CLI capture fails isolation')
        if attempt['status'] not in ('ok', 'invalid_output', 'service_error'):
            raise ValueError('Unknown Fable attempt status')
        positions = (records[index * len(members):(index + 1) * len(members)] if phase == 'smoke'
                     else records[index * 10:(index + 1) * 10])
        if len(positions) != len(members):
            raise ValueError('Fable record count differs from batch')
        predictions = ({row['id']: {key: value for key, value in row.items() if key != 'id'}
                        for row in attempt.get('prediction', {}).get('records', [])}
                       if attempt['status'] == 'ok' else {})
        if attempt['status'] == 'ok' and (len(predictions) != len(members) or set(predictions) != set(members)):
            raise ValueError('Fable successful prediction membership differs')
        for pos, record in enumerate(positions):
            rid = members[pos]
            if (record.get('id'), record.get('status'), record.get('prediction'),
                    record.get('repeat'), record.get('condition'), record.get('phase'),
                    record.get('batch_index'), record.get('batch_position'),
                    record.get('batch_record_ids'), record.get('requested_model'),
                    record.get('effort')) != (
                    rid, attempt['status'], predictions.get(rid), repeat, condition, phase,
                    planned['batch_index'], pos + 1, members, model, effort):
                raise ValueError('Fable record differs from saved attempt')
            indexed[rid] = record
    if len(records) != sum(len(requests[index]['record_ids']) for index in range(len(attempts))):
        raise ValueError('Fable record evidence has extra rows')
    complete = events[-1]['event'] == 'phase_completed'
    if complete:
        if len(attempts) != len(requests) or any(attempt['status'] != 'ok' for attempt in attempts) or (
                events[-1].get('request_count'), events[-1].get('record_count')) != (
                len(requests), 3 if phase == 'smoke' else 60):
            raise ValueError('Fable completed phase is incomplete')
    elif (not attempts or attempts[-1]['status'] == 'ok' or
          events[-1].get('batch_index') != requests[len(attempts) - 1]['batch_index']):
        raise ValueError('Fable stopped phase lacks a failed attempt')
    if phase == 'development':
        for rid in ids:
            indexed.setdefault(rid, {'id': rid, 'status': 'never_sent', 'prediction': None})
        score = shared.score(indexed, labels, ids)
    else:
        score = None
    evidence = {'claim': claim_binding, 'rootReview': review_binding,
                'journal': journal_binding, 'attempts': attempt_binding,
                'records': record_binding, 'rawCaptures': raw_bindings}
    return {'completionStatus': 'complete' if complete else 'partial',
            'terminalEvent': events[-1]['event'], 'finishedRequests': len(attempts),
            'score': score, 'usage': opus._usage(attempts), 'evidence': evidence}, None, indexed


def _build_one(root, config):
    ids, labels, pair, plans, bind, sources = _source_context(root, config)
    data = {name: {} for name in PASSES}
    indexed = {name: {} for name in PASSES}
    missing = []
    partial = []
    for condition in CONDITIONS:
        entry, records = _historical(root, config, condition, pair, plans['repeat2'][0], ids, labels, bind)
        data['original'][condition] = entry
        indexed['original'][condition] = records
    for repeat in ('repeat2', 'repeat3'):
        plan, plan_binding = plans[repeat]
        for condition in CONDITIONS:
            smoke, _, _ = _phase(root, config, repeat, condition, 'smoke', plan, plan_binding, ids, labels, bind)
            if smoke is None or smoke['completionStatus'] != 'complete':
                missing.append({'pass': repeat, 'condition': condition, 'status': 'smoke_open_or_incomplete'})
                continue
            inspection_path = BASE / config / repeat / condition / 'smoke-inspection.json'
            if not opus._file(root, inspection_path).exists():
                missing.append({'pass': repeat, 'condition': condition, 'status': 'smoke_uninspected'})
                continue
            inspection = json.loads(opus._file(root, inspection_path).read_text())
            if (inspection.get('inspection'), inspection.get('attempts_sha256'),
                    inspection.get('records_sha256'), inspection.get('journal_sha256')) != (
                    'accepted_unchanged', smoke['evidence']['attempts']['sha256'],
                    smoke['evidence']['records']['sha256'], smoke['evidence']['journal']['sha256']):
                raise ValueError('Fable smoke inspection differs from evidence')
            bind(inspection_path)
            entry, reason, records = _phase(root, config, repeat, condition, 'development',
                                            plan, plan_binding, ids, labels, bind)
            if entry is None:
                missing.append({'pass': repeat, 'condition': condition, 'status': reason})
                continue
            data[repeat][condition] = entry
            if entry['completionStatus'] == 'partial':
                partial.append({'pass': repeat, 'condition': condition,
                                'terminalEvent': entry['terminalEvent'],
                                'finishedRequests': entry['finishedRequests']})
            else:
                indexed[repeat][condition] = records
    def full(pass_name, condition):
        return condition in data[pass_name] and data[pass_name][condition]['completionStatus'] == 'complete'
    deltas = []
    for pass_name in PASSES:
        for target in ('P1', 'P2'):
            if full(pass_name, 'P0') and full(pass_name, target):
                first, second = data[pass_name]['P0']['score'], data[pass_name][target]['score']
                deltas.append({'pass': pass_name, 'from': 'P0', 'to': target, 'denominator': 60,
                               'allFour': second['allFour'] - first['allFour'],
                               'fields': {field: second['fields'][field] - first['fields'][field]
                                          for field in FIELDS}})
    spread = {}
    for target in ('P1', 'P2'):
        entries = [item for item in deltas if item['to'] == target]
        spread[target] = {'completedPairs': len(entries),
                          'allFourValues': [item['allFour'] for item in entries],
                          'allFourRange': [min(item['allFour'] for item in entries),
                                           max(item['allFour'] for item in entries)] if len(entries) == 3 else None,
                          'fieldRanges': {field: [min(item['fields'][field] for item in entries),
                                                  max(item['fields'][field] for item in entries)]
                                          if len(entries) == 3 else None for field in FIELDS}}
    flips = []
    ranges = {}
    across = {}
    for condition in CONDITIONS:
        for index, left in enumerate(PASSES):
            for right in PASSES[index + 1:]:
                if full(left, condition) and full(right, condition):
                    flips.append({'condition': condition, 'from': left, 'to': right,
                                  **shared.flip(indexed[left][condition], indexed[right][condition], ids)})
        scores = [data[name][condition]['score'] for name in PASSES if full(name, condition)]
        ranges[condition] = {'allFour': opus._stats([score['allFour'] for score in scores]),
                             'fields': {field: opus._stats([score['fields'][field] for score in scores])
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
    model, effort = roster.ROSTER[config]
    return {'schema': 'claude-roster-repeat-findings-v1', 'configuration': config,
            'displayName': f'Claude Fable 5.1 · {effort} effort · batch 10',
            'model': model, 'effort': effort, 'provider': 'Claude subscription',
            'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items()))
                                     for field in FIELDS},
            'denominator': 60,
            'completedConditions': sum(full(name, condition) for name in PASSES for condition in CONDITIONS),
            'plannedConditions': 9, 'missingPasses': missing, 'partialPasses': partial,
            'passes': data, 'threePassSummary': ranges, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
            'pairedDeltaSpread': spread, 'sourceBindings': sources,
            'limitations': ['This report covers one Fable 5.1 effort setting; other configurations are separate series.',
                            'The same 60 synthetic development records appear in every pass.',
                            'Partial terminal phases keep missing outcomes in the 60-record denominator; open phases are excluded.',
                            'Historical and repeat CLI patch versions differ. Serving revision and effective seed are unavailable.',
                            'Request duration is client wall-clock time, not model-only inference time.',
                            'CLI list-price estimates are not subscription charges. Actual billed cost and quota consumed are unknown.']}


def build(root=ROOT, configs=CONFIGS):
    root = Path(root)
    return {'schema': 'claude-roster-repeat-report-v1',
            'series': [_build_one(root, config) for config in configs]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(ROOT), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(content)
    print('Claude Fable 5.1 roster report checked')


if __name__ == '__main__':
    main()
