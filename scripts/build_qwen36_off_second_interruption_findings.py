#!/usr/bin/env python3
"""Portable public Qwen off findings after two retained service errors."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import build_qwen36_off_continuation_findings as prior
import build_additional_hosted_fresh_repeat_findings as additional
import qwen36_off_fresh_repeat_execution_v2 as execution
import qwen36_off_fresh_repeat_admission as admission
from development_benchmark import KEYS, digest, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = prior.BASE
NEW = BASE / 'second-interruption-v1'
MANIFEST_SHA = 'a83ab134a5926840b527c70f6c02cc4df02dea782053eace5e611f867386b51a'
BUDGET_SHA = '76f1745a4316065bafb42f2dc1fee9ae14cbb84cd803f96386e6161ec37ad902'
PROJECTION_SHA = 'f659750f71e4b612eba1ded11b3e008d14f250ec5aef73f89c2d6e46ea960e53'
SCHEMA = 'qwen36-off-v2-second-interruption-findings-v1'
SERIES = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-two-interruptions-v1'
METHOD = 'descriptive-continuation-after-two-service-errors'
IDS = prior.IDS
PASSES = prior.PASSES
CONDITIONS = prior.CONDITIONS
OLD_UNKNOWN = Decimal('0.0598016')
CAP = Decimal('0.06')
PRIVATE_SOURCES = {'failed_claim', 'failed_journal', 'failed_raw',
                   'failed_records', 'failed_review'}
POSITION_KEYS = prior.POSITION_KEYS


def file(root, relative):
    return prior.file(root, relative)


def sha(path):
    return prior.sha(path)


def bind(root, relative, bindings, expected=None):
    return prior.bind(root, relative, bindings, expected)


def rows(path):
    return prior.rows(path)


def projection_path():
    return NEW / 'suffix-reconciliation.json'


def prefix_path(index):
    return NEW / ('phase-07-suffix-budget-prefix.json' if index == 6 else
                  f'phase-{index + 1:02d}-budget-prefix.json')


def source_context(root):
    root = Path(root).resolve()
    old_report = prior.build(root)
    old_series = old_report['series'][0]
    old_manifest, labels, ids, _, _, old_bindings, old_manifest_binding = prior.source_context(root)
    bindings = list(old_report['sourceBindings'])
    manifest_binding = bind(root, NEW / 'manifest.json', bindings, MANIFEST_SHA)
    manifest = json.loads(file(root, NEW / 'manifest.json').read_text())
    expected_schedule = [{'phase_index': i, 'stage': stage} for i, stage in
        ((6, 'suffix'), (7, 'smoke'), (7, 'development'), (8, 'smoke'), (8, 'development'))]
    sources = manifest.get('sources') or {}
    if (manifest.get('schema') != 'qwen36-off-v2-second-interruption-v1' or
            manifest.get('status') != 'FROZEN' or manifest.get('configuration') != admission.CONFIG or
            manifest.get('method') != METHOD or manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('old_failed_ids') != ['DEV-006', 'DEV-031'] or
            manifest.get('old_unknown_charge_upper_bound_usd') != str(OLD_UNKNOWN) or
            manifest.get('schedule') != expected_schedule or
            manifest.get('phases') != old_manifest['phases'] or
            manifest.get('route') != old_manifest['route'] or
            not prior.requests_match(manifest.get('requests_by_condition'),
                                     json.loads(file(root, BASE / 'manifest.json').read_text())['requests_by_condition']) or
            manifest.get('partition_id') != 'qwen36-off-second-interruption-20260929' or
            manifest.get('child_cap_usd') != str(CAP) or
            manifest.get('reserve_usd') != str(admission.RESERVE) or
            manifest.get('output_directory') != str(NEW) or
            sources.get('successor_manifest', {}).get('sha256') != old_manifest_binding['sha256'] or
            sources.get('old_child_ledger', {}).get('sha256') !=
                '6113a30b7e73b354e229845f9553d54d657dddae51d2b2c36aed4c370f71771e' or
            sources.get('old_terminal_reconciliation', {}).get('sha256') !=
                '95b4ce0da5672b30856313510684318608ab3456f829eed61a53c0043e29188c'):
        raise ValueError('Frozen second-interruption manifest differs')
    for name, item in sources.items():
        if (not isinstance(item, dict) or not isinstance(item.get('path'), str) or
                not isinstance(item.get('sha256'), str) or len(item['sha256']) != 64):
            raise ValueError('Second-interruption source binding differs')
        # The original failed stage and its smoke were bound at freeze time but
        # are not needed to reproduce the sanitized public projection.
        if name not in PRIVATE_SOURCES and not name.startswith('phase_07_'):
            bind(root, item['path'], bindings, item['sha256'])
    bind(root, manifest['controller']['path'], bindings, manifest['controller']['sha256'])
    budget_binding = bind(root, NEW / 'budget.json', bindings, BUDGET_SHA)
    if sources['new_budget_manifest'] != budget_binding:
        raise ValueError('New child budget binding differs')
    budget = json.loads(file(root, NEW / 'budget.json').read_text())
    entries = budget.get('partitions') or []
    if len(entries) != 1:
        raise ValueError('New child partition membership differs')
    partition = entries[0]
    origin = Path(budget.get('master_ledger', '')).parent.parent
    if (not origin.is_absolute() or budget.get('version') != 'paid-partitions-v1' or
            budget['master_ledger'] != str(origin / 'results/openrouter-paid-budget.jsonl') or
            any(partition.get(k) != v for k, v in {'id': manifest['partition_id'],
                'model': admission.MODEL, 'provider': admission.PROVIDER,
                'reasoning': 'off', 'cap_usd': str(CAP)}.items()) or
            partition.get('child_ledger') != str(origin / NEW /
                ('budget-' + manifest['partition_id'] + '.jsonl'))):
        raise ValueError('New child route or portable budget differs')
    terminal = json.loads(file(root, sources['old_terminal_reconciliation']['path']).read_text())
    if (terminal.get('event') != 'partition_reconciled' or
            terminal.get('partition_id') != old_manifest['partition_id'] or
            terminal.get('child_sha256') != sources['old_child_ledger']['sha256'] or
            terminal.get('known_actual_usd') != '0.0575207' or
            terminal.get('unknown_upper_bound_usd') != str(OLD_UNKNOWN) or
            terminal.get('unused_allocation_released_usd') != '0.0326777'):
        raise ValueError('Old sealed child accounting differs')
    return old_series, old_manifest, manifest, labels, ids, partition, bindings, manifest_binding


def closed(root, index, stage):
    path = file(root, NEW / f'phase-{index + 1:02d}-{stage}.journal.jsonl')
    if not path.exists():
        return False
    data = path.read_bytes()
    if not data.endswith(b'\n'):
        return False
    try:
        return json.loads(data.splitlines()[-1]) == {
            'event': 'stage_completed', 'count': 3 if stage == 'smoke' else 60}
    except (ValueError, IndexError):
        return False


def suffix_projection(root, manifest, bindings):
    path = file(root, projection_path())
    if not path.exists():
        return None, None
    bound = bind(root, projection_path(), bindings, PROJECTION_SHA)
    projection = json.loads(path.read_text())
    positions = projection.get('positions') or []
    evidence = projection.get('evidence') or {}
    if (projection.get('schema') != 'qwen36-off-v2-second-interruption-v1-suffix-reconciliation' or
            projection.get('method') != METHOD or
            projection.get('status') != 'closed_with_service_error' or
            projection.get('denominator') != 60 or
            projection.get('valid') != 59 or
            projection.get('observed_valid_positions') != 59 or
            projection.get('strict_complete_pass') is not False or
            projection.get('old_failed_ids') != ['DEV-006', 'DEV-031'] or
            projection.get('status_counts') != {'ok': 59, 'service_error': 1} or
            projection.get('old_unknown_charge_upper_bound_usd') != str(OLD_UNKNOWN) or
            projection.get('new_unknown_charge_upper_bound_usd') != '0' or
            projection.get('new_pending_unknown_reserve_usd') != '0' or
            projection.get('manifest_sha256') != MANIFEST_SHA or
            len(positions) != 60 or [p.get('id') for p in positions] != IDS):
        raise ValueError('New suffix public reconciliation is not closed 59/60')
    for name in ('failed_claim', 'failed_journal', 'failed_raw', 'failed_records',
                 'failed_review', 'old_child_ledger', 'old_terminal_reconciliation'):
        if evidence.get(name) != manifest['sources'][name]:
            raise ValueError('Private or old source evidence hash differs')
    for name in ('claim', 'journal', 'raw', 'records', 'suffix_review'):
        item = evidence.get(name)
        if not isinstance(item, dict):
            raise ValueError('New suffix evidence binding absent')
        bind(root, item['path'], bindings, item['sha256'])
    expected = manifest['requests_by_condition']['P1']
    for index, (row, item) in enumerate(zip(positions, expected)):
        if (set(row) - POSITION_KEYS or row.get('request_sha256') != item['request_sha256'] or
                row.get('status') != ('service_error' if index == 30 else 'ok') or
                type(row.get('client_http_duration_seconds')) not in (int, float) or
                not math.isfinite(row['client_http_duration_seconds']) or
                row['client_http_duration_seconds'] < 0):
            raise ValueError('New suffix position differs')
        if index == 30:
            if (row.get('prediction') is not None or row.get('http_status') != 429 or
                    row.get('observed_cost_usd') is not None or
                    row.get('unknown_charge_upper_bound_usd') != str(admission.RESERVE) or
                    row.get('cost_unknown') is not True or row.get('billing_ok') is not False):
                raise ValueError('Failed DEV-031 changed')
        elif (not valid(row.get('prediction')) or row.get('cost_unknown') is not False or
              row.get('billing_ok') is not True or row.get('observed_cost_usd') is None or
              row.get('unknown_charge_upper_bound_usd') is not None):
            raise ValueError('Valid suffix position differs')
    # The projection includes 30 old successful P1 calls and 29 new successful ones.
    new_known = sum((Decimal(row['observed_cost_usd']) for row in positions[31:]), Decimal(0))
    if new_known != Decimal(projection.get('new_known_actual_usd', '-1')):
        raise ValueError('New suffix known charges differ')
    return positions, bound


def accounting(events):
    known = sum((Decimal(e['usd']) for e in events if e['event'] == 'settle'), Decimal(0))
    unknown = sum((Decimal(e['usd']) for e in events if
                   e['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    if known + unknown > CAP:
        raise ValueError('New child exposure exceeds cap')
    return {'oldKnownAllAttemptCostUsd': '0.0575207',
            'oldUnknownChargeUpperBoundUsd': str(OLD_UNKNOWN),
            'newKnownAllAttemptCostUsd': str(known),
            'newUnknownChargeUpperBoundUsd': str(unknown),
            'combinedKnownAllAttemptCostUsd': str(Decimal('0.0575207') + known),
            'combinedUnknownChargeUpperBoundUsd': str(OLD_UNKNOWN + unknown),
            'chargeKind': 'provider_observed_plus_separate_unknown_upper_bounds'}


def validate_prefix(root, index, positions, partition, earlier, stage_rows, bindings, supplied=None):
    relative = prefix_path(index)
    payload = supplied if supplied is not None else json.loads(file(root, relative).read_text())
    events = payload.get('events') or []
    if (payload.get('schema') != 'qwen36-off-v2-second-public-child-prefix-v1' or
            type(payload.get('sourceEventCount')) is not int or
            payload['sourceEventCount'] != len(events) or
            not isinstance(payload.get('sourcePrefixSha256'), str) or
            len(payload['sourcePrefixSha256']) != 64 or
            any(e != prior.sanitize_event(e) for e in events) or
            not events or events[0] != {'event': 'budget', 'cap_usd': str(CAP)} or
            (earlier is not None and events[:len(earlier)] != earlier)):
        raise ValueError('Portable new-child prefix differs')
    cursor, seen = 1, set()
    for row in positions[31:]:
        reserved, settled = events[cursor:cursor + 2] if cursor + 2 <= len(events) else (None, None)
        if (reserved is None or settled is None or
                reserved.get('event') != 'reserve' or reserved.get('record_id') != row['id'] or
                reserved.get('usd') != str(admission.RESERVE) or
                reserved.get('attempt_id') in seen or
                settled != {'event': 'settle', 'attempt_id': reserved['attempt_id'],
                            'usd': row['observed_cost_usd']}):
            raise ValueError('New suffix child-budget settlement differs')
        seen.add(reserved['attempt_id']); cursor += 2
    for stage in stage_rows:
        for row in stage:
            attempt = row['attempt_id']
            if (attempt in seen or events[cursor:cursor + 2] != [
                    {'event': 'reserve', 'attempt_id': attempt, 'record_id': row['id'],
                     'usd': row['reserved_cost_usd']},
                    {'event': 'settle', 'attempt_id': attempt,
                     'usd': row['observed_cost_usd']}]):
                raise ValueError('New later stage child-budget settlement differs')
            seen.add(attempt); cursor += 2
    if cursor != len(events):
        raise ValueError('Unclaimed new-child budget events')
    if partition['cap_usd'] != str(CAP):
        raise ValueError('New partition cap differs')
    result = accounting(events)
    if supplied is None:
        bind(root, relative, bindings)
    return events, result


def stage(root, manifest, partition, index, name, bindings):
    stem = NEW / f'phase-{index + 1:02d}-{name}'
    review_relative = Path(str(stem) + '.root-review.json')
    bind(root, review_relative, bindings)
    review = json.loads(file(root, review_relative).read_text())
    expected = {'schema': 'qwen36-off-v2-second-interruption-v1-stage-review',
        'approved': True, 'manifest_sha256': MANIFEST_SHA,
        'controller_sha256': manifest['controller']['sha256'],
        'old_child_ledger_sha256': manifest['sources']['old_child_ledger']['sha256'],
        'old_terminal_reconciliation_sha256': manifest['sources']['old_terminal_reconciliation']['sha256'],
        'new_budget_manifest_sha256': BUDGET_SHA,
        'partition_id': partition['id'], 'phase_index': index, 'stage': name,
        'ids': IDS[:3] if name == 'smoke' else IDS}
    if any(review.get(k) != v for k, v in expected.items()):
        raise ValueError('New stage review differs')
    if name == 'development':
        smoke = NEW / f'phase-{index + 1:02d}-smoke'
        inspection = review.get('smoke_inspection') or {}
        if (inspection.get('approved') is not True or
                inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + k + '_sha256') !=
                    sha(file(root, Path(str(smoke) + '.' + k + '.jsonl')))
                    for k in ('records', 'journal', 'raw'))):
            raise ValueError('New development smoke inspection differs')
    with patch.object(execution, 'ROOT', Path(root).resolve()):
        if not execution.finished(manifest, file(root, NEW), index, name,
                MANIFEST_SHA, BUDGET_SHA, partition['id']):
            raise ValueError('New closed stage fails strict runner verification')
    evidence = {}
    for part, suffix in (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
                         ('raw', '.raw.jsonl'), ('records', '.records.jsonl')):
        relative = Path(str(stem) + suffix)
        evidence[part] = bind(root, relative, bindings)
    evidence['review'] = {'path': str(review_relative),
                          'sha256': sha(file(root, review_relative))}
    return rows(file(root, evidence['records']['path'])), evidence


def summaries(series, maps, ids):
    data = series['passes']
    deltas, prompt_flips = [], []
    for fresh in PASSES:
        if 'P0' not in data[fresh]:
            continue
        for condition in ('P1', 'P2'):
            if condition not in data[fresh]:
                continue
            baseline, variant = data[fresh]['P0']['score'], data[fresh][condition]['score']
            deltas.append({'pass': fresh, 'from': 'P0', 'to': condition,
                'denominator': 60, 'allFour': variant['allFour'] - baseline['allFour'],
                'fields': {key: variant['fields'][key] - baseline['fields'][key] for key in KEYS}})
            prompt_flips.append({'pass': fresh, 'from': 'P0', 'to': condition,
                **additional.flip(maps[(fresh, 'P0')], maps[(fresh, condition)], ids)})
    series['withinPassPromptDeltas'] = deltas
    series['withinPassPromptFlips'] = prompt_flips
    series['pairwiseFlips'] = [{'condition': condition, 'from': a, 'to': b,
        **additional.flip(maps[(a, condition)], maps[(b, condition)], ids)}
        for condition in CONDITIONS for pos, a in enumerate(PASSES) for b in PASSES[pos + 1:]
        if (a, condition) in maps and (b, condition) in maps]
    series['threePassSummary'] = {condition: {
        'allFour': additional.stats([data[f][condition]['score']['allFour']
            for f in PASSES if condition in data[f]]),
        'fields': {field: additional.stats([data[f][condition]['score']['fields'][field]
            for f in PASSES if condition in data[f]]) for field in KEYS}}
        for condition in CONDITIONS}
    across = {}
    for condition in CONDITIONS:
        if not all((fresh, condition) in maps for fresh in PASSES):
            continue
        indexed = [{row['id']: row for row in maps[(fresh, condition)]} for fresh in PASSES]
        shared = [rid for rid in ids if all(part[rid]['status'] == 'ok' for part in indexed)]
        across[condition] = {'denominator': len(shared),
            'excludedIds': [rid for rid in ids if rid not in shared],
            'fields': {field: [rid for rid in shared if
                len({part[rid]['prediction'][field] for part in indexed}) > 1] for field in KEYS},
            'fourFieldVector': [rid for rid in shared if
                len({tuple(part[rid]['prediction'][field] for field in KEYS) for part in indexed}) > 1]}
    series['changesAcrossThreePasses'] = across
    series['pairedDeltaSpread'] = {condition: {'completedPairs': len(paired),
        'allFourValues': [item['allFour'] for item in paired],
        'allFourRange': [min(item['allFour'] for item in paired),
                         max(item['allFour'] for item in paired)] if len(paired) == 3 else None,
        'fieldRanges': {field: [min(item['fields'][field] for item in paired),
            max(item['fields'][field] for item in paired)] if len(paired) == 3 else None
            for field in KEYS}}
        for condition in ('P1', 'P2')
        for paired in [[item for item in deltas if item['to'] == condition]]}


def build(root=ROOT):
    root = Path(root).resolve()
    old, old_manifest, manifest, labels, ids, partition, bindings, manifest_binding = source_context(root)
    series = json.loads(json.dumps(old))
    series.update(schema=SCHEMA, seriesId=SERIES, method=METHOD,
        displayName='Qwen3.6 35B A3B · AkashML fp8 · reasoning off · two-error descriptive continuation',
        cleanMatchedThreeEligible=False, historicalPassUsed=False)
    series['limitations'] = [
        'DEV-006 and DEV-031 remain service errors in their fixed 60-position phases.',
        'Two interrupted suffixes changed dispatch timing; this is not a clean matched-three series.',
        'Original private error bytes are hash-bound but cannot be reproduced from a public checkout.',
        'Portable child-budget snapshots retain source-prefix hashes; public checkouts cannot rehash live ledger prefixes.',
        'The same 60 synthetic development records recur in every pass.',
        'Provisional v0.2 references are not independent adjudication.',
        'Client HTTP duration includes transport, not pure provider inference.',
        'Unknown-charge upper bounds are not observed provider charges.',
        'Flip denominators include only records valid in both compared passes.']
    maps = {('fresh1', 'P0'): json.loads(file(root, old_manifest['sources']['suffix_reconciliation']['path']).read_text())['positions']}
    for index in range(1, 6):
        phase = old_manifest['phases'][index]
        if phase['condition'] in series['passes'][phase['repeat']]:
            maps[(phase['repeat'], phase['condition'])] = rows(file(root, prior.LATER /
                f'phase-{index + 1:02d}-development.records.jsonl'))
    missing = []
    positions, projection_binding = suffix_projection(root, manifest, bindings)
    new_prefix = None
    stage_rows = []
    execution_gap = positions is None
    reporting_gap = positions is not None and not file(root, prefix_path(6)).exists()
    if positions is None or not file(root, prefix_path(6)).exists():
        missing.append({'pass': 'fresh3', 'condition': 'P1',
                        'status': 'not_completed' if positions is None else 'budget_prefix_absent'})
    else:
        new_prefix, accounting_result = validate_prefix(root, 6, positions, partition,
            None, [], bindings)
        score = additional.score(positions, labels, ids)
        usage = prior.public_usage(positions, str(OLD_UNKNOWN))
        usage['newKnownCostUsd'] = str(sum((Decimal(r['observed_cost_usd'])
            for r in positions[31:]), Decimal(0)))
        usage['knownAllAttemptCostUsd'] = accounting_result['combinedKnownAllAttemptCostUsd']
        series['passes']['fresh3']['P1'] = {'status': 'closed_with_service_error',
            'score': score, 'usage': usage, 'budgetAccountingCumulative': accounting_result,
            'evidence': {'reconciliation': projection_binding,
                         'secondManifest': manifest_binding,
                         'newBudgetPrefix': {'path': str(prefix_path(6)),
                                             'sha256': sha(file(root, prefix_path(6)))},
                         'privateEvidenceHashesOnly': True}}
        maps[('fresh3', 'P1')] = positions
    for index in (7, 8):
        phase = manifest['phases'][index]
        fresh, condition = phase['repeat'], phase['condition']
        if not closed(root, index, 'development'):
            missing.append({'pass': fresh, 'condition': condition, 'status': 'not_completed'})
            execution_gap = True
            continue
        if execution_gap:
            raise ValueError('Closed later phase skips incomplete public predecessor')
        if reporting_gap or not file(root, prefix_path(index)).exists():
            missing.append({'pass': fresh, 'condition': condition,
                            'status': 'budget_prefix_absent_or_prior_unreported'})
            reporting_gap = True
            continue
        if not closed(root, index, 'smoke'):
            raise ValueError('New development closed without smoke')
        smoke, smoke_evidence = stage(root, manifest, partition, index, 'smoke', bindings)
        dev, evidence = stage(root, manifest, partition, index, 'development', bindings)
        previous_rows = stage_rows + [smoke, dev]
        new_prefix, accounting_result = validate_prefix(root, index, positions,
            partition, new_prefix, previous_rows, bindings)
        stage_rows = previous_rows
        data = {'status': 'completed', 'score': additional.score(dev, labels, ids),
            'usage': prior.public_usage(dev), 'budgetAccountingCumulative': accounting_result,
            'evidence': {**evidence, 'smoke': smoke_evidence,
                         'newBudgetPrefix': {'path': str(prefix_path(index)),
                                             'sha256': sha(file(root, prefix_path(index)))}}}
        series['passes'][fresh][condition] = data
        maps[(fresh, condition)] = dev
    series['completedConditions'] = len(maps)
    series['missingPasses'] = missing
    series['secondInterruption'] = {'oldFailedIds': ['DEV-006', 'DEV-031'],
        'retainedOldUnknownBounds': [
            {'phase': 'fresh1/P0', 'id': 'DEV-006', 'status': 'service_error',
             'upperBoundUsd': str(admission.RESERVE)},
            {'phase': 'fresh3/P1', 'id': 'DEV-031', 'status': 'service_error',
             'upperBoundUsd': str(admission.RESERVE)}],
        'oldUnknownChargeUpperBoundUsd': str(OLD_UNKNOWN),
        'oldSealedChildSha256': manifest['sources']['old_child_ledger']['sha256'],
        'newChildCapUsd': str(CAP), 'newBudgetManifest': manifest['sources']['new_budget_manifest'],
        'secondManifest': manifest_binding}
    summaries(series, maps, ids)
    return {'schema': SCHEMA, 'series': [series],
        'availableConfigurations': [admission.CONFIG], 'sourceBindings': bindings}


def capture_prefix(root, index):
    """Capture a portable prefix only after the named stage is strictly closed."""
    root = Path(root).resolve()
    if index not in (6, 7, 8):
        raise ValueError('Only second-interruption closed phases have new prefixes')
    _, _, manifest, _, _, partition, _, _ = source_context(root)
    projection, _ = suffix_projection(root, manifest, [])
    if projection is None:
        raise ValueError('Suffix not closed')
    previous = None
    stages = []
    for stage_index in range(6, index + 1):
        if stage_index > 6:
            if not (closed(root, stage_index, 'smoke') and
                    closed(root, stage_index, 'development')):
                raise ValueError('Later phase not strictly closed')
            for name in ('smoke', 'development'):
                records, _ = stage(root, manifest, partition, stage_index, name, [])
                stages.append(records)
        if stage_index < index:
            previous = json.loads(file(root, prefix_path(stage_index)).read_text())['events']
    child = file(root, NEW / ('budget-' + partition['id'] + '.jsonl'))
    lines = child.read_bytes().splitlines(keepends=True)
    if not all(line.endswith(b'\n') for line in lines):
        raise ValueError('Child ledger has incomplete tail')
    event_count = 1 + 58 + sum(2 * len(stage) for stage in stages)
    source_lines = lines[:event_count]
    if len(source_lines) != event_count:
        raise ValueError('Child ledger lacks full closed prefix')
    events = [prior.sanitize_event(json.loads(line)) for line in source_lines]
    payload = {'schema': 'qwen36-off-v2-second-public-child-prefix-v1',
        'sourceEventCount': len(events),
        'sourcePrefixSha256': hashlib.sha256(b''.join(source_lines)).hexdigest(),
        'events': events}
    validate_prefix(root, index, projection, partition, previous, stages, [], payload)
    target = file(root, prefix_path(index))
    content = json.dumps(payload, indent=2) + '\n'
    if target.exists():
        if target.read_text() != content:
            raise FileExistsError('Immutable new-child budget prefix differs')
        return target
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.budget-prefix-', delete=False) as out:
        temporary = Path(out.name)
        out.write(content.encode()); out.flush(); os.fsync(out.fileno())
    try:
        os.link(temporary, target)
    finally:
        temporary.unlink()
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--capture-prefix-through-phase', type=int)
    args = parser.parse_args(argv)
    if args.capture_prefix_through_phase is not None:
        if args.output or args.check:
            parser.error('Prefix capture cannot be combined with reporting')
        capture_prefix(ROOT, args.capture_prefix_through_phase - 1)
        return
    if args.output is None:
        parser.error('--output is required for report')
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError('Stale second-interruption report')
    else:
        args.output.write_text(content)


if __name__ == '__main__':
    main()
