#!/usr/bin/env python3
"""Offline public findings for the interrupted Qwen off v2 descriptive continuation."""
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

import build_additional_hosted_fresh_repeat_findings as additional
import build_deepseek_fresh_repeat_findings as common
import qwen36_off_fresh_repeat_execution_v2 as execution
import qwen36_off_fresh_repeat_admission as admission
from development_benchmark import KEYS, digest, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/qwen36-off-fresh3-v2')
LATER = BASE / 'later-phases-v1'
MANIFEST_SHA = 'efc025c5d185835aff6734030c5613cac402909fe10ec4b34a6ae09d32bf045f'
SCHEMA = 'qwen36-off-v2-descriptive-continuation-findings-v1'
SERIES = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-continuation-v1'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
POSITION_KEYS = {'id', 'status', 'request_sha256', 'prediction', 'observed_cost_usd',
                 'cost_unknown', 'billing_ok', 'client_http_duration_seconds',
                 'client_request_started_utc', 'client_request_finished_utc',
                 'http_status', 'unknown_charge_upper_bound_usd', 'usage'}


def file(root, relative):
    return common.file(root, relative)


def sha(path):
    return common.sha(path)


def bind(root, relative, bindings, expected=None):
    return common.bind(root, relative, bindings, expected)


def rows(path):
    return common.rows(path)


def prefix_path(index):
    return LATER / f'phase-{index + 1:02d}-budget-prefix.json'


def requests_match(successor, original):
    if set(successor or {}) != set(CONDITIONS):
        return False
    for condition in CONDITIONS:
        items = successor[condition]
        frozen = original[condition]
        if len(items) != 60 or len(frozen) != 60:
            return False
        for item, prior in zip(items, frozen):
            if ({key: value for key, value in item.items() if key != 'payload'} != prior or
                    digest(json.dumps(item.get('payload'), sort_keys=True)) != prior['request_sha256']):
                return False
    return True


def source_context(root):
    root = Path(root).resolve()
    bindings = []
    original, labels, ids, partition, budget_binding, old_bindings = additional.source_context(root, additional.SPECS[0])
    bindings.extend(old_bindings)
    manifest_binding = bind(root, LATER / 'manifest.json', bindings, MANIFEST_SHA)
    manifest = json.loads(file(root, LATER / 'manifest.json').read_text())
    sources = manifest.get('sources') or {}
    if (manifest.get('schema') != 'qwen36-off-v2-successors-v1' or
            manifest.get('status') != 'FROZEN' or
            manifest.get('method') != 'descriptive-continuation-after-service-error' or
            manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('successor_phase_indices') != list(range(1, 9)) or
            manifest.get('phases') != original['phases'] or
            not requests_match(manifest.get('requests_by_condition'), original['requests_by_condition']) or
            manifest.get('route') != original['route'] or
            manifest.get('partition_id') != partition['id'] or
            manifest.get('child_cap_usd') != partition['cap_usd'] or
            manifest.get('reserve_usd') != str(admission.RESERVE) or
            manifest.get('output_directory') != str(LATER) or
            manifest.get('first_phase') != {'repeat': 'fresh1', 'condition': 'P0',
                'status': 'closed_with_service_error', 'valid': 59,
                'denominator': 60, 'failed_id': 'DEV-006'} or
            sources.get('original_manifest', {}).get('sha256') != sha(file(root, BASE / 'manifest.json')) or
            sources.get('budget_manifest', {}).get('sha256') != budget_binding['sha256']):
        raise ValueError('Frozen successor manifest differs')
    for name, item in sources.items():
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise ValueError('Successor source binding differs')
        bind(root, item['path'], bindings, item['sha256'])
    bind(root, manifest['controller']['path'], bindings, manifest['controller']['sha256'])
    return manifest, labels, ids, partition, budget_binding, bindings, manifest_binding


def first_phase(root, manifest, labels, bindings):
    source = manifest['sources']['suffix_reconciliation']
    bind(root, source['path'], bindings, source['sha256'])
    projected = json.loads(file(root, source['path']).read_text())
    positions = projected.get('positions') or []
    expected = manifest['requests_by_condition']['P0']
    if (projected.get('schema') != 'qwen36-off-v2-never-sent-suffix-v1-reconciliation' or
            projected.get('configuration') != admission.CONFIG or
            projected.get('phase') != 'fresh1/P0' or
            projected.get('status') != 'closed_with_service_error' or
            projected.get('denominator') != 60 or projected.get('valid') != 59 or
            projected.get('observed_valid_positions') != 59 or
            projected.get('status_counts') != {'ok': 59, 'service_error': 1} or
            projected.get('strict_complete_pass') is not False or
            projected.get('historical_failed_id') != 'DEV-006' or
            projected.get('original_manifest_sha256') != manifest['sources']['original_manifest']['sha256'] or
            projected.get('suffix_manifest_sha256') != manifest['sources']['suffix_manifest']['sha256'] or
            projected.get('pending_unknown_reserve_usd') != '0' or
            projected.get('unknown_charge_upper_bound_usd') != str(admission.RESERVE) or
            len(positions) != 60 or [row.get('id') for row in positions] != IDS):
        raise ValueError('Public first-phase reconciliation differs')
    for index, (row, frozen) in enumerate(zip(positions, expected)):
        if (set(row) - POSITION_KEYS or row.get('request_sha256') != frozen['request_sha256'] or
                row.get('status') != ('service_error' if index == 5 else 'ok') or
                type(row.get('client_http_duration_seconds')) not in (int, float) or
                not math.isfinite(row['client_http_duration_seconds']) or
                row['client_http_duration_seconds'] < 0):
            raise ValueError('Public first-phase position differs')
        if index == 5:
            if (row.get('prediction') is not None or row.get('http_status') != 429 or
                    row.get('observed_cost_usd') is not None or
                    row.get('unknown_charge_upper_bound_usd') != str(admission.RESERVE) or
                    row.get('cost_unknown') is not True or row.get('billing_ok') is not False):
                raise ValueError('Failed DEV-006 changed')
        elif (not valid(row.get('prediction')) or row.get('cost_unknown') is not False or
              row.get('billing_ok') is not True or row.get('observed_cost_usd') is None or
              row.get('unknown_charge_upper_bound_usd') is not None):
            raise ValueError('Valid first-phase position differs')
    evidence = projected.get('evidence') or {}
    if (evidence.get('development_records', {}).get('sha256') is None or
            evidence.get('smoke_records', {}).get('sha256') is None):
        raise ValueError('Private evidence hashes absent')
    known = sum((Decimal(row['observed_cost_usd']) for row in positions
                 if row.get('observed_cost_usd') is not None), Decimal(0))
    if known > Decimal(projected['known_actual_usd']):
        raise ValueError('Known first-phase costs exceed all observed charges')
    score = additional.score(positions, labels, IDS)
    return positions, projected, score


def public_usage(records, unknown_bound='0'):
    lengths = [row['client_http_duration_seconds'] for row in records]
    known = sum((Decimal(row['observed_cost_usd']) for row in records
                 if row.get('observed_cost_usd') is not None), Decimal(0))
    token_keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    return {'requestCount': len(records), 'requestSeconds': lengths,
            'requestSecondsTotal': sum(lengths),
            'timingKind': 'client_http_duration_not_provider_inference',
            'tokens': {key: sum(row['usage'][key] for row in records
                                if type((row.get('usage') or {}).get(key)) is int)
                       for key in token_keys},
            'tokensMissingRequestCount': {key: sum(type((row.get('usage') or {}).get(key)) is not int
                                                    for row in records) for key in token_keys},
            'knownCostUsd': str(known), 'unknownCostCount': sum(row.get('cost_unknown') is True for row in records),
            'unknownChargeUpperBoundUsd': unknown_bound,
            'costNote': 'Known USD costs are observed provider charges; the upper bound is not an invoice charge.'}


def budget_accounting(events):
    known = sum((Decimal(event['usd']) for event in events if event['event'] == 'settle'), Decimal(0))
    unknown = sum((Decimal(event['usd']) for event in events
                   if event['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    return {'knownAllAttemptCostUsd': str(known),
            'unknownChargeUpperBoundUsd': str(unknown),
            'accountedExposureUsd': str(known + unknown),
            'chargeKind': 'provider_observed_plus_separate_unknown_upper_bound'}


def sanitize_event(event):
    kind = event.get('event')
    keys = {'budget': ('event', 'cap_usd'),
            'reserve': ('event', 'attempt_id', 'record_id', 'usd'),
            'settle': ('event', 'attempt_id', 'usd'),
            'unknown_cost_accounted_as_upper_bound':
                ('event', 'attempt_id', 'usd', 'actual_cost_usd', 'evidence_sha256')}
    if kind not in keys:
        raise ValueError('Unexpected child-budget event in prefix')
    return {key: event[key] for key in keys[kind]}


def baseline_events(events, projection, partition):
    if not events or events[0] != {'event': 'budget', 'cap_usd': partition['cap_usd']}:
        raise ValueError('Budget prefix header differs')
    cursor = 1
    attempts = set()
    total = Decimal(0)
    for rid in IDS[:3] + IDS:
        if cursor + 1 >= len(events):
            raise ValueError('Budget prefix lacks original or suffix attempts')
        reserved = events[cursor]
        if (reserved.get('event') != 'reserve' or reserved.get('record_id') != rid or
                reserved.get('usd') != str(admission.RESERVE) or
                reserved.get('attempt_id') in attempts):
            raise ValueError('Original and suffix budget order differs')
        attempts.add(reserved['attempt_id'])
        next_event = events[cursor + 1]
        if rid == 'DEV-006' and cursor > 7:
            expected = {'event': 'unknown_cost_accounted_as_upper_bound',
                'attempt_id': reserved['attempt_id'], 'usd': str(admission.RESERVE),
                'actual_cost_usd': None,
                'evidence_sha256': projection['evidence']['development_records']['sha256']}
            if next_event != expected:
                raise ValueError('Full DEV-006 unknown bound differs')
        elif (next_event.get('event') != 'settle' or
              next_event.get('attempt_id') != reserved['attempt_id']):
            raise ValueError('Original and suffix settlement differs')
        else:
            amount = Decimal(next_event['usd'])
            if amount < 0:
                raise ValueError('Negative observed charge')
            if cursor > 6:
                position = projection['positions'][IDS.index(rid)]
                if next_event['usd'] != position['observed_cost_usd']:
                    raise ValueError('First-phase observed charge differs')
            total += amount
        cursor += 2
    if total != Decimal(projection['known_actual_usd']):
        raise ValueError('First-phase known budget charges differ')
    return cursor, attempts


def validate_prefix(root, relative, projection, partition, earlier, stages, supplied=None):
    data = supplied if supplied is not None else json.loads(file(root, relative).read_text())
    events = data.get('events') or []
    if (data.get('schema') != 'qwen36-off-v2-public-child-prefix-v1' or
            type(data.get('sourceEventCount')) is not int or
            data['sourceEventCount'] != len(events) or
            not isinstance(data.get('sourcePrefixSha256'), str) or
            len(data['sourcePrefixSha256']) != 64 or
            any(event != sanitize_event(event) for event in events)):
        raise ValueError('Portable budget prefix differs')
    cursor, attempts = baseline_events(events, projection, partition)
    if earlier and events[:len(earlier)] != earlier:
        raise ValueError('Budget prefix does not extend predecessor')
    for records in stages:
        for row in records:
            attempt = row['attempt_id']
            if attempt in attempts:
                raise ValueError('Budget attempt ID repeated across phases')
            expected = [{'event': 'reserve', 'attempt_id': attempt,
                         'record_id': row['id'], 'usd': row['reserved_cost_usd']},
                        {'event': 'settle', 'attempt_id': attempt,
                         'usd': row['observed_cost_usd']}]
            if events[cursor:cursor + 2] != expected:
                raise ValueError('Later phase budget settlement differs')
            attempts.add(attempt)
            cursor += 2
    if cursor != len(events):
        raise ValueError('Budget prefix has unclaimed events')
    accounting = budget_accounting(events)
    if Decimal(accounting['accountedExposureUsd']) > Decimal(partition['cap_usd']):
        raise ValueError('Portable budget prefix exceeds child cap')
    return events


def stage(root, manifest, partition, budget_binding, index, name, bindings):
    stem = LATER / f'phase-{index + 1:02d}-{name}'
    review_relative = Path(str(stem) + '.root-review.json')
    bind(root, review_relative, bindings)
    review = json.loads(file(root, review_relative).read_text())
    expected = {'schema': 'qwen36-off-v2-successors-v1-stage-review', 'approved': True,
                'manifest_sha256': MANIFEST_SHA,
                'controller_sha256': manifest['controller']['sha256'],
                'original_manifest_sha256': manifest['sources']['original_manifest']['sha256'],
                'suffix_reconciliation_sha256': manifest['sources']['suffix_reconciliation']['sha256'],
                'budget_manifest_sha256': budget_binding['sha256'],
                'partition_id': partition['id'], 'phase_index': index, 'stage': name}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError('Successor stage review differs')
    if name == 'development':
        smoke = LATER / f'phase-{index + 1:02d}-smoke'
        inspection = review.get('smoke_inspection') or {}
        if (inspection.get('approved') is not True or
                inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + key + '_sha256') !=
                    sha(file(root, Path(str(smoke) + '.' + key + '.jsonl')))
                    for key in ('records', 'journal', 'raw'))):
            raise ValueError('Development lacks inspected smoke')
    with patch.object(execution, 'ROOT', Path(root).resolve()):
        if not execution.finished(manifest, file(root, LATER), index, name, MANIFEST_SHA,
                                  budget_binding['sha256'], partition['id']):
            raise ValueError('Closed successor stage fails strict runner verification')
    evidence = {}
    for part, suffix in (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
                         ('raw', '.raw.jsonl'), ('records', '.records.jsonl')):
        relative = Path(str(stem) + suffix)
        evidence[part] = bind(root, relative, bindings)
    evidence['review'] = {'path': str(review_relative), 'sha256': sha(file(root, review_relative))}
    return rows(file(root, evidence['records']['path'])), evidence


def closed(root, index, name):
    relative = LATER / f'phase-{index + 1:02d}-{name}.journal.jsonl'
    path = file(root, relative)
    if not path.exists():
        return False
    data = path.read_bytes()
    if not data.endswith(b'\n'):
        return False
    try:
        return json.loads(data.splitlines()[-1]) == {
            'event': 'stage_completed', 'count': 3 if name == 'smoke' else 60}
    except (ValueError, IndexError):
        return False


def build(root=ROOT):
    root = Path(root).resolve()
    manifest, labels, ids, partition, budget_binding, bindings, manifest_binding = source_context(root)
    first_rows, projection, first_score = first_phase(root, manifest, labels, bindings)
    data = {fresh: {} for fresh in PASSES}
    first_source = {'reconciliation': manifest['sources']['suffix_reconciliation'],
                    'successorManifest': manifest_binding,
                    'privateEvidenceHashesOnly': True}
    data['fresh1']['P0'] = {'status': 'closed_with_service_error', 'score': first_score,
                            'usage': {**public_usage(first_rows, str(admission.RESERVE)),
                                      'knownAllAttemptCostUsd': projection['known_actual_usd']},
                            'evidence': first_source}
    maps = {('fresh1', 'P0'): first_rows}
    missing = []
    previous_events = None
    completed_stages = []
    found_execution_gap = False
    found_reporting_gap = False
    for index in range(1, 9):
        phase = manifest['phases'][index]
        fresh, condition = phase['repeat'], phase['condition']
        if not closed(root, index, 'development'):
            missing.append({'pass': fresh, 'condition': condition, 'status': 'not_completed'})
            found_execution_gap = True
            continue
        if found_execution_gap:
            raise ValueError('Closed successor phase skips an incomplete predecessor')
        if found_reporting_gap or not file(root, prefix_path(index)).exists():
            missing.append({'pass': fresh, 'condition': condition,
                            'status': 'budget_prefix_absent_or_prior_unreported'})
            found_reporting_gap = True
            continue
        if not closed(root, index, 'smoke'):
            raise ValueError('Development closed without successor smoke')
        smoke, smoke_evidence = stage(root, manifest, partition, budget_binding, index, 'smoke', bindings)
        development, evidence = stage(root, manifest, partition, budget_binding, index, 'development', bindings)
        snapshot_relative = prefix_path(index)
        snapshot_binding = bind(root, snapshot_relative, bindings)
        previous_events = validate_prefix(root, snapshot_relative, projection, partition,
                                          previous_events, completed_stages + [smoke, development])
        completed_stages.extend((smoke, development))
        maps[(fresh, condition)] = development
        data[fresh][condition] = {'status': 'completed',
            'score': additional.score(development, labels, ids),
            'usage': public_usage(development),
            'budgetAccountingCumulative': budget_accounting(previous_events),
            'evidence': {**evidence, 'smoke': smoke_evidence,
                         'budgetPrefix': snapshot_binding}}
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
    pairwise = [{'condition': condition, 'from': a, 'to': b,
                 **additional.flip(maps[(a, condition)], maps[(b, condition)], ids)}
                for condition in CONDITIONS for pos, a in enumerate(PASSES) for b in PASSES[pos + 1:]
                if (a, condition) in maps and (b, condition) in maps]
    ranges = {condition: {'allFour': additional.stats([data[f][condition]['score']['allFour']
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
    spread = {}
    for condition in ('P1', 'P2'):
        paired = [item for item in deltas if item['to'] == condition]
        spread[condition] = {'completedPairs': len(paired),
            'allFourValues': [item['allFour'] for item in paired],
            'allFourRange': [min(item['allFour'] for item in paired),
                             max(item['allFour'] for item in paired)] if len(paired) == 3 else None,
            'fieldRanges': {field: [min(item['fields'][field] for item in paired),
                max(item['fields'][field] for item in paired)] if len(paired) == 3 else None
                for field in KEYS}}
    series = {'schema': SCHEMA, 'configuration': admission.CONFIG, 'seriesId': SERIES,
        'displayName': 'Qwen3.6 35B A3B · AkashML fp8 · reasoning off · descriptive continuation',
        'method': 'descriptive-continuation-after-service-error',
        'cleanMatchedThreeEligible': False, 'model': admission.MODEL,
        'effort': 'off', 'provider': admission.PROVIDER, 'route': manifest['route'],
        'conditionOrder': list(CONDITIONS), 'passOrder': list(PASSES),
        'denominator': 60, 'plannedConditions': 9, 'completedConditions': len(maps),
        'missingPasses': missing, 'passes': data, 'referenceVersion': '0.2',
        'referenceStatus': 'AI-reviewed provisional; not independent adjudication',
        'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field]
            for rid in ids).items())) for field in KEYS},
        'threePassSummary': ranges, 'pairwiseFlips': pairwise,
        'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
        'withinPassPromptFlips': prompt_flips, 'pairedDeltaSpread': spread,
        'historicalPassUsed': False,
        'limitations': ['DEV-006 remains a service error in the fixed 60-position first pass.',
            'The suffix changed dispatch timing; this is not a clean matched-three series.',
            'Original private failure bytes cannot be independently reproduced from the public checkout.',
            'Portable child-budget snapshots retain the source-prefix hash; a public checkout cannot rehash the live child ledger.',
            'The same 60 synthetic development records recur in every pass.',
            'Provisional v0.2 references are not independent adjudication.',
            'Client HTTP duration includes transport, not pure provider inference.',
            'Unknown-charge upper bounds are not observed provider charges.',
            'Flip denominators include only records valid in both compared passes.']}
    return {'schema': SCHEMA, 'series': [series], 'availableConfigurations': [admission.CONFIG],
            'sourceBindings': bindings}


def capture_prefix(root, index):
    """After strict stage closure, create a portable immutable child-ledger prefix."""
    root = Path(root).resolve()
    if index not in range(1, 9):
        raise ValueError('Successor index required')
    manifest, _, _, partition, budget_binding, _, _ = source_context(root)
    projection = json.loads(file(root, manifest['sources']['suffix_reconciliation']['path']).read_text())
    if not closed(root, index, 'smoke') or not closed(root, index, 'development'):
        raise ValueError('Cannot capture incomplete successor stage')
    for earlier in range(1, index):
        if not closed(root, earlier, 'development') or not file(root, prefix_path(earlier)).exists():
            raise ValueError('Cannot skip predecessor budget prefix')
    stage_rows = []
    for phase in range(1, index + 1):
        for name in ('smoke', 'development'):
            selected, _ = stage(root, manifest, partition, budget_binding, phase, name, [])
            stage_rows.append(selected)
    last = stage_rows[-1][-1]['attempt_id']
    ledger = file(root, BASE / ('budget-' + partition['id'] + '.jsonl'))
    lines = ledger.read_bytes().splitlines(keepends=True)
    source_lines = []
    for line in lines:
        if not line.endswith(b'\n'):
            break
        source_lines.append(line)
        event = json.loads(line)
        if event.get('event') == 'settle' and event.get('attempt_id') == last:
            break
    else:
        raise ValueError('Final successor settlement absent from child ledger')
    events = [sanitize_event(json.loads(line)) for line in source_lines]
    prior_events = (json.loads(file(root, prefix_path(index - 1)).read_text())['events']
                    if index > 1 else None)
    payload = {'schema': 'qwen36-off-v2-public-child-prefix-v1',
               'sourceEventCount': len(events),
               'sourcePrefixSha256': hashlib.sha256(b''.join(source_lines)).hexdigest(),
               'events': events}
    target = file(root, prefix_path(index))
    validate_prefix(root, prefix_path(index), projection, partition, prior_events, stage_rows, payload)
    content = json.dumps(payload, indent=2) + '\n'
    if target.exists():
        if target.read_text() != content:
            raise FileExistsError('Immutable budget prefix differs')
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
            parser.error('Prefix capture cannot be combined with report output or check')
        capture_prefix(ROOT, args.capture_prefix_through_phase - 1)
        return
    if args.output is None:
        parser.error('--output is required for a report')
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError('Stale Qwen descriptive continuation report')
    else:
        args.output.write_text(content)


if __name__ == '__main__':
    main()
