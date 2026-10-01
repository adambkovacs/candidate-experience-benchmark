#!/usr/bin/env python3
"""Describe the closed Qwen27 fresh3 continuations from a committed snapshot.

This is a separate interrupted series. It never changes the clean matched-run
report, sends requests, or reads the moving master budget ledger.
"""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path

import build_qwen27_interrupted_continuation_findings as first
import qwen27_fresh_repeat_execution_v2 as original
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/qwen27-fresh-matched3-v2')
SECOND = BASE / 'interruption-continuation-v2'
SCHEMA = 'qwen27-v2-second-continuation-findings-v1'
CONTROLLER_SCHEMA = 'qwen27-v2-second-interruption-continuation-v1'
MANIFEST_SHA = {
    'medium': '04c732fd354b25469c26360d4783657d5cd54e2a8126dbdf133c8d0dd0efd423',
    'xhigh': '06803cf07c2bfe210e423af3bfcbd346cda4d7a159dbef1543302893be2cc6fc',
}
STAGES = {
    'medium': (('P0', 'suffix', 39, 60), ('P1', 'smoke', 1, 3),
               ('P1', 'development', 1, 60)),
    'xhigh': (('P1', 'suffix', 9, 60),),
}


def bind(root, relative, bindings, expected=None):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe source path')
    path = (root / relative).resolve()
    path.relative_to(root)
    if not path.is_file():
        raise ValueError('Closed source missing: ' + str(relative))
    digest = first.sha(path)
    if expected is not None and digest != expected:
        raise ValueError('Closed source hash differs: ' + str(relative))
    item = {'path': relative.as_posix(), 'sha256': digest}
    if item not in bindings:
        bindings.append(item)
    return path


def stage_files(root, kind, condition, phase, bindings):
    base = SECOND / kind / 'fresh3' / condition / phase
    return {name: bind(root, base / (phase + '.' + suffix), bindings)
            for name, suffix in (('claim', 'claim.json'),
                                 ('review', 'root-review.json'),
                                 ('journal', 'journal.jsonl'),
                                 ('attempts', 'attempts.jsonl'),
                                 ('responses', 'responses.jsonl'))}


def checked_amount(value):
    amount = first.amount(value)
    return amount


def verify_stage(root, kind, manifest, condition, phase, start, end,
                 planned, child_events, bindings):
    files = stage_files(root, kind, condition, phase, bindings)
    review, claim = (json.loads(files[k].read_text()) for k in ('review', 'claim'))
    stage = f'fresh3/{condition}/{phase}'
    selected = planned[start-1:end]
    ids = [f'DEV-{i:03d}' for i in range(start, end + 1)]
    manifest_stage = next((s for s in manifest['schedule'] if s['stage'] == stage), None)
    if (manifest_stage != {'stage': stage, 'ids': ids,
                           'request_sha256': [r['request_sha256'] for r in selected]} or
            review.get('schema') != CONTROLLER_SCHEMA + '-stage-review' or
            review.get('approved') is not True or
            review.get('configuration_id') != manifest['configuration_id'] or
            review.get('series_id') != manifest['series_id'] or
            review.get('stage') != stage or
            review.get('ids') != ids or
            review.get('request_sha256') != manifest_stage['request_sha256'] or
            review.get('manifest_sha256') != MANIFEST_SHA[kind] or
            review.get('controller_sha256') !=
                manifest['source_bindings']['controller']['sha256'] or
            review.get('new_budget_manifest_sha256') !=
                manifest['source_bindings']['new_budget_manifest']['sha256'] or
            review.get('old_child_sha256') !=
                manifest['source_bindings']['old_child']['sha256'] or
            review.get('first_child_sha256') !=
                manifest['source_bindings']['first_child']['sha256'] or
            review.get('first_reconciliation_sha256') !=
                manifest['source_bindings']['first_reconciliation']['sha256'] or
            review.get('partition_id') != manifest['partition_id'] or
            review.get('child_cap_usd') != manifest['child_cap_usd'] or
            claim.get('series_id') != manifest['series_id'] or
            claim.get('configuration_id') != manifest['configuration_id'] or
            claim.get('stage') != stage or
            claim.get('manifest_sha256') != MANIFEST_SHA[kind] or
            claim.get('root_review_sha256') != first.sha(files['review'])):
        raise ValueError('Closed stage plan, review, or claim differs: ' + stage)
    attempts, wire, journal = (first.rows(files[k]) for k in
                               ('attempts', 'responses', 'journal'))
    if ([r.get('id') for r in attempts] != ids or
            [r.get('id') for r in wire] != ids or
            len({r.get('attempt_id') for r in attempts}) != len(ids) or
            len(journal) != 2 + 4 * len(ids) or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('request_count') != len(ids) or
            journal[-1].get('attempt_ids') != [r['attempt_id'] for r in attempts]):
        raise ValueError('Stage is not exactly closed in frozen order: ' + stage)
    public = []
    for i, (request, row, captured) in enumerate(zip(selected, attempts, wire)):
        rid, aid = request['record_id'], row['attempt_id']
        route, intent, started, finished = journal[1+4*i:5+4*i]
        amount = checked_amount(row.get('observed_cost_usd'))
        if (rid != row.get('id') or row.get('series_id') != manifest['series_id'] or
                row.get('configuration_id') != manifest['configuration_id'] or
                row.get('stage') != stage or
                row.get('manifest_sha256') != MANIFEST_SHA[kind] or
                row.get('request') != request['payload'] or
                any(row.get(key) != request[key] for key in
                    ('request_sha256', 'input_sha256', 'instruction_sha256')) or
                row.get('reference_labels_read') is not False or
                row.get('status') != 'ok' or not valid(row.get('prediction')) or
                row.get('billing_ok') is not True or row.get('cost_unknown') is not False or
                checked_amount(row.get('reserved_cost_usd')) != Decimal(manifest['reserve_usd']) or
                amount > Decimal(manifest['reserve_usd']) or
                route.get('event') != 'route_observed' or route.get('id') != rid or
                route.get('model_catalog_entries') != [row.get('model_catalog_entry')] or
                route.get('provider_endpoints') != [row.get('provider_endpoint')] or
                [(e.get('event'), e.get('id'), e.get('attempt_id')) for e in
                 (intent, started, finished)] != [
                    ('request_intent', rid, None), ('request_started', rid, aid),
                    ('request_finished', rid, aid)] or
                intent.get('request_sha256') != request['request_sha256'] or
                started.get('request_sha256') != request['request_sha256'] or
                finished.get('status') != 'ok' or
                finished.get('billing_ok') is not True or
                finished.get('cost_unknown') is not False or
                checked_amount(finished.get('observed_cost_usd')) != amount or
                [event for event in child_events if event.get('attempt_id') == aid] != [
                    {'event': 'reserve', 'attempt_id': aid, 'record_id': rid,
                     'usd': manifest['reserve_usd']},
                    {'event': 'settle', 'attempt_id': aid,
                     'usd': row['observed_cost_usd']}] or
                captured.get('id') != rid or captured.get('attempt_id') != aid or
                captured.get('request_sha256') != request['request_sha256'] or
                captured.get('http_status') != 200 or
                captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None):
            raise ValueError('Closed attempt, route, or billing differs: ' + rid)
        try:
            decoded = json.loads(base64.b64decode(captured['body_base64'], validate=True))
        except (KeyError, ValueError, TypeError):
            raise ValueError('Captured body cannot be decoded: ' + rid) from None
        classified = original.classify(decoded, row['model_catalog_entry'],
                                       row['provider_endpoint'])
        if (decoded != row.get('raw_response') or
                any(row.get(key) != value for key, value in classified.items()) or
                checked_amount((decoded.get('usage') or {}).get('cost')) != amount or
                row.get('response_diagnostic', {}).get('passed') is not True):
            raise ValueError('Captured body or parsed result differs: ' + rid)
        public.append(first.public_position(row))
    return public


def score(rows, labels, service_errors):
    indexed = {row['id']: row for row in rows}
    if len(rows) != 60 or set(indexed) != set(first.IDS):
        raise ValueError('Composite does not cover exactly 60 positions')
    valid_rows = [row for row in rows if row['status'] == 'ok']
    if len(valid_rows) != 60 - service_errors:
        raise ValueError('Composite validity differs')
    fields = {key: sum(row['prediction'][key] == labels[row['id']][key]
                       for row in valid_rows) for key in KEYS}
    all_four = sum(all(row['prediction'][key] == labels[row['id']][key]
                       for key in KEYS) for row in valid_rows)
    return {'denominator': 60, 'valid': len(valid_rows),
            'serviceErrors': service_errors, 'invalidOutputs': 0, 'neverSent': 0,
            'allFour': all_four, 'fields': fields}


def usage(rows):
    known = [checked_amount(row['observed_cost_usd']) for row in rows
             if row.get('observed_cost_usd') is not None]
    token_keys = ('prompt_tokens', 'completion_tokens', 'total_tokens',
                  'provider_reported_reasoning_tokens')
    tokens = {}
    for key in token_keys:
        values = [(row.get('usage') or {}).get(key) for row in rows]
        present = [v for v in values if type(v) is int and v >= 0]
        if any(v is not None and (type(v) is not int or v < 0) for v in values):
            raise ValueError('Invalid provider token count')
        tokens[key] = {'sum': sum(present) if len(present) == len(values) else None,
                       'reportedCount': len(present),
                       'missingCount': len(values) - len(present)}
    return {'knownObservedCostUsd': str(sum(known, Decimal(0))),
            'unknownCostCount': len(rows) - len(known),
            'clientRequestToRecordSeconds': sum(first.duration(r.get('elapsed_seconds'))
                                                for r in rows),
            'timingKind': 'client_request_to_record_not_pure_inference',
            'tokens': tokens}


def build(root=ROOT):
    root = Path(root).resolve(strict=True)
    earlier = first.build(root)
    bindings = list(earlier['sourceBindings'])
    bind(root, Path('scripts') / Path(__file__).name, bindings,
         first.sha(__file__))
    bind(root, 'scripts/qwen27_v2_second_continuation.py', bindings,
         '57d25e0ec69e2e7ef197e61fb43271d5459330a05a101e9a6502d64692cf4909')
    labels = {row['id']: row['proposed_labels']
              for row in first.rows(root / first.LABELS)}
    result = {}
    for kind in ('medium', 'xhigh'):
        config = 'openrouter-paid-qwen3.8-27b-' + kind
        parent = SECOND / kind
        manifest_file = bind(root, parent / 'manifest.json', bindings,
                             MANIFEST_SHA[kind])
        manifest = json.loads(manifest_file.read_text())
        expected_stages = [f'fresh3/{cond}/{phase}'
                           for cond, phase, _, _ in STAGES[kind]]
        if (manifest.get('schema') != CONTROLLER_SCHEMA or
                manifest.get('series_id') != CONTROLLER_SCHEMA + '-' + kind or
                manifest.get('configuration_id') != config or
                manifest.get('clean_matched_three_eligible') is not False or
                manifest.get('reference_labels_read') is not False or
                manifest.get('failed_attempted_id') != first.FAILED[kind][0] or
                manifest.get('reserve_usd') != '0.047001600' or
                [s.get('stage') for s in manifest.get('schedule', [])] != expected_stages):
            raise ValueError('Second continuation manifest identity differs')
        plan = json.loads(bind(root, BASE / config / 'fresh3/manifest.json', bindings,
                               first.PLAN_SHA[kind]).read_text())
        budget_info = manifest['source_bindings']['new_budget_manifest']
        budget_manifest = json.loads(bind(root, budget_info['path'], bindings,
                                          budget_info['sha256']).read_text())
        partition = manifest['partition_id']
        ledger = bind(root, parent / ('budget-' + partition + '.jsonl'), bindings)
        events = first.rows(ledger)
        reconciliation = json.loads(bind(root,
            parent / 'terminal-reconciliation-after-completion.json', bindings).read_text())
        if (events[0] != {'event': 'budget', 'cap_usd': manifest['child_cap_usd']} or
                events[-1].get('event') != 'partition_closed' or
                set(event['event'] for event in events) !=
                    {'budget', 'reserve', 'settle', 'partition_closed'} or
                reconciliation.get('event') != 'partition_reconciled' or
                reconciliation.get('partition_id') != partition or
                reconciliation.get('child_sha256') != first.sha(ledger) or
                reconciliation.get('unknown_upper_bound_usd') != '0' or
                len(budget_manifest.get('partitions', [])) != 1 or
                budget_manifest['partitions'][0].get('id') != partition or
                budget_manifest['partitions'][0].get('cap_usd') !=
                    manifest['child_cap_usd'] or
                Path(budget_manifest['partitions'][0].get('child_ledger', '')).name !=
                    ledger.name):
            raise ValueError('Second child budget closure differs')
        stage_rows = {}
        for condition, phase, start, end in STAGES[kind]:
            planned = plan['conditions'][condition]['smoke' if phase == 'smoke'
                                                     else 'development']
            stage_rows[(condition, phase)] = verify_stage(
                root, kind, manifest, condition, phase, start, end,
                planned, events, bindings)
        attempt_ids = [row['attempt_id'] for rows in stage_rows.values()
                       for row in rows]
        charged_ids = [event['attempt_id'] for event in events
                       if event['event'] == 'settle']
        if (len(events) != 2 + 2 * len(attempt_ids) or
                len(set(attempt_ids)) != len(attempt_ids) or
                charged_ids != attempt_ids):
            raise ValueError('Second child charges do not cover exactly the admitted stages')
        charged = sum((checked_amount(e['usd']) for e in events
                       if e['event'] == 'settle'), Decimal(0))
        if (checked_amount(reconciliation.get('known_actual_usd')) != charged or
                charged + checked_amount(reconciliation.get('unused_allocation_released_usd')) !=
                    checked_amount(manifest['child_cap_usd'])):
            raise ValueError('Second child reconciliation amount differs')
        earlier_dir = first.CONT / kind / 'public-evidence-v1'
        earlier_rows = {name: first.rows(root / earlier_dir / (name + '.positions.jsonl'))
                        for name in ('prefix', 'suffix')}
        p0 = earlier_rows['prefix'] + earlier_rows['suffix']
        if kind == 'medium':
            p0 += stage_rows[('P0', 'suffix')]
            p1 = stage_rows[('P1', 'development')]
        else:
            p1 = first.rows(root / earlier_dir / 'p1.positions.jsonl') + \
                stage_rows[('P1', 'suffix')]
        for condition, rows, failures in (('P0', p0, 1), ('P1', p1, 0)):
            if ([r['id'] for r in rows] != first.IDS or
                    len({r.get('attempt_id') for r in rows}) != 60):
                raise ValueError('Composite membership or duplicate attempt differs')
        if p0[first.FAILED[kind][1]]['status'] != 'service_error':
            raise ValueError('Original failed P0 attempt was replaced')
        if kind == 'medium' and earlier['series'][kind]['suffixSaved'] != 16:
            raise ValueError('Medium first continuation is not the pinned partial stage')
        if kind == 'xhigh' and earlier['series'][kind]['laterP1']['saved'] != 8:
            raise ValueError('Xhigh first P1 prefix is not the pinned partial stage')
        result[kind] = {'configurationId': config,
                        'cleanMatchedThreeEligible': False,
                        'originalP0FailedId': first.FAILED[kind][0],
                        'originalP0UnknownCostUpperBoundUsd': '0.047001600',
                        'secondChildKnownCostUsd': str(charged),
                        'secondChildUnknownCostUpperBoundUsd': '0',
                        'conditions': {
                            'P0': {'status': 'completed_interrupted_composite',
                                   'score': score(p0, labels, 1), 'usage': usage(p0)},
                            'P1': {'status': 'completed_interrupted_composite',
                                   'score': score(p1, labels, 0), 'usage': usage(p1)}}}
    return {'schema': SCHEMA, 'method': 'descriptive_interrupted_composites',
            'denominator': 60, 'cleanMatchedThreeEligible': False,
            'referenceStatus': 'AI-authored provisional; not independently human-adjudicated',
            'series': result, 'sourceBindings': bindings,
            'limits': ['The original failed P0 attempt was not retried.',
                       'Fresh3 P0 and P1 combine separately dispatched stages; they are not clean matched passes.',
                       'The original failed P0 charge remains an upper bound, not observed spending.',
                       'Client request-to-record time is not isolated model inference time.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(args.root), indent=2, sort_keys=True) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != content:
            raise ValueError('Qwen27 second-continuation report differs from bound evidence')
    elif args.output:
        args.output.write_text(content)
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
