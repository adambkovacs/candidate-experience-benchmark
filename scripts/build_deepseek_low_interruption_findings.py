#!/usr/bin/env python3
"""Build portable, descriptive DeepSeek-low findings from terminal public snapshots.

Capture reads private evidence only after a stage closes. Ordinary build/check
uses the public snapshots and frozen hashes; it never opens live provider records.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

import build_additional_hosted_fresh_repeat_findings as additional
import build_qwen36_off_second_interruption_findings as qwen_report
import deepseek_low_fresh_repeat_admission as admission
import deepseek_low_interruption_continuation as runner
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-low-fresh3-v2')
NEW = BASE / 'interruption-continuation-v1'
MANIFEST_SHA = '358a4667f372aafcfd146f4b9c9aec5fe219e2d4359cf1d0844aed41d0315e63'
SCHEMA = 'deepseek-low-descriptive-interruption-findings-v1'
SNAPSHOT_SCHEMA = 'deepseek-low-public-terminal-stage-v1'
SERIES = 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1'
METHOD = 'descriptive-continuation-after-service-error'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
PRIVATE = {'failed_raw', 'failed_records', 'failed_journal', 'failed_claim'}
POSITION_KEYS = {'id', 'status', 'prediction', 'observed_cost_usd', 'cost_unknown',
                 'unknown_upper_bound_usd', 'usage', 'client_http_duration_seconds',
                 'http_status', 'request_sha256', 'attempt_id', 'returned_model',
                 'returned_provider', 'finish_reason'}


def file(root, relative):
    return additional.path(root, relative)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(root, relative, bindings, expected=None):
    return additional.bind(root, relative, bindings, expected)


def snapshot_path(index):
    return NEW / ('phase-03-suffix.public.json' if index == 2 else
                  f'phase-{index + 1:02d}.public.json')


def source_context(root):
    root = Path(root).resolve()
    generic = additional.build(root, configuration=admission.CONFIG)
    if len(generic['series']) != 1:
        raise ValueError('Original DeepSeek-low series absent')
    original = generic['series'][0]
    spec = next(s for s in additional.SPECS if s.admission.CONFIG == admission.CONFIG)
    old_manifest, labels, ids, _, _, old_bindings = additional.source_context(root, spec)
    bindings = list(generic['sourceBindings'])
    for item in old_bindings:
        if item not in bindings:
            bindings.append(item)
    manifest_binding = bind(root, NEW / 'manifest.json', bindings, MANIFEST_SHA)
    manifest = json.loads(file(root, NEW / 'manifest.json').read_text())
    sources = manifest.get('source_bindings') or {}
    expected_schedule = [{'phase_index': 2, 'stage': 'suffix'}] + [
        {'phase_index': i, 'stage': stage} for i in range(3, 9)
        for stage in ('smoke', 'development')]
    if (manifest.get('schema') != runner.SCHEMA or manifest.get('status') != 'FROZEN' or
            manifest.get('method') != METHOD or
            manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('configuration_id') != admission.CONFIG or
            manifest.get('schedule') != expected_schedule or
            manifest.get('phases') != old_manifest['phases'] or
            manifest.get('requests_by_condition') != old_manifest['requests_by_condition'] or
            manifest.get('route') != old_manifest['route'] or
            manifest.get('old_known_actual_usd') != '0.04109562' or
            manifest.get('old_unknown_charge_upper_bound_usd') != str(admission.RESERVE) or
            manifest.get('original_failed_id') != 'DEV-040' or
            manifest.get('original_invalid_id') != 'DEV-039' or
            manifest.get('partition_id') != 'deepseek-low-interruption-20260929' or
            manifest.get('child_cap_usd') != '0.14' or
            manifest.get('reserve_usd') != str(admission.RESERVE) or
            manifest.get('output_directory') != str(NEW) or
            manifest.get('controller', {}).get('sha256') != sha(file(root, manifest['controller']['path'])) or
            sources.get('original_manifest', {}).get('sha256') != sha(file(root, BASE / 'manifest.json'))):
        raise ValueError('Frozen continuation manifest differs')
    bind(root, manifest['controller']['path'], bindings, manifest['controller']['sha256'])
    for name, source in sources.items():
        if not isinstance(source, dict) or not isinstance(source.get('path'), str) or \
                not isinstance(source.get('sha256'), str) or len(source['sha256']) != 64:
            raise ValueError('Continuation source binding differs')
        if name not in PRIVATE:
            bind(root, source['path'], bindings, source['sha256'])
    budget = json.loads(file(root, sources['new_budget_manifest']['path']).read_text())
    partitions = budget.get('partitions') or []
    if len(partitions) != 1:
        raise ValueError('New child partition differs')
    partition = partitions[0]
    origin = Path(budget.get('master_ledger', '')).parent.parent
    if (not origin.is_absolute() or budget.get('version') != 'paid-partitions-v1' or
            budget['master_ledger'] != str(origin / 'results/openrouter-paid-budget.jsonl') or
            any(partition.get(key) != value for key, value in {
                'id': manifest['partition_id'], 'model': admission.MODEL,
                'provider': admission.PROVIDER, 'reasoning': 'low',
                'cap_usd': manifest['child_cap_usd']}.items()) or
            partition.get('child_ledger') != str(origin / NEW /
                ('budget-' + manifest['partition_id'] + '.jsonl'))):
        raise ValueError('New child route or portable budget differs')
    terminal = json.loads(file(root, sources['old_terminal_reconciliation']['path']).read_text())
    if (terminal.get('event') != 'partition_reconciled' or
            terminal.get('partition_id') != 'deepseek-low-fresh3-20260929' or
            terminal.get('child_sha256') != sources['old_child_ledger']['sha256'] or
            terminal.get('known_actual_usd') != manifest['old_known_actual_usd'] or
            terminal.get('unknown_upper_bound_usd') != manifest['old_unknown_charge_upper_bound_usd']):
        raise ValueError('Old child seal differs')
    return original, manifest, labels, ids, partition, bindings, manifest_binding


def _money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError('Invalid observed charge')
    return amount


def _row(row):
    result = {key: row[key] for key in POSITION_KEYS if key in row}
    if row.get('cost_unknown') is True:
        result['unknown_upper_bound_usd'] = str(admission.RESERVE)
    else:
        result['unknown_upper_bound_usd'] = '0'
    if 'prediction' in result and result.get('status') != 'ok':
        result.pop('prediction')
    if 'usage' in result:
        usage = result['usage'] or {}
        result['usage'] = {key: usage[key] for key in
            ('prompt_tokens', 'completion_tokens', 'total_tokens')
            if type(usage.get(key)) is int and usage[key] >= 0}
    return result


def _validate_rows(rows, expected, *, suffix=False):
    if (len(rows) != len(expected) or
            [row.get('id') for row in rows] != [item['id'] for item in expected]):
        raise ValueError('Public position membership differs')
    for index, (row, item) in enumerate(zip(rows, expected)):
        if set(row) - POSITION_KEYS or row.get('request_sha256') != item['request_sha256']:
            raise ValueError('Public request hash or fields differ')
        if suffix and index in (38, 39):
            wanted = 'invalid_output' if index == 38 else 'service_error'
            if row.get('status') != wanted:
                raise ValueError('Original failed position changed')
        elif row.get('status') not in ('ok', 'invalid_output'):
            raise ValueError('Closed position status differs')
        if row['status'] == 'ok' and not valid(row.get('prediction')):
            raise ValueError('Valid prediction missing')
        if row['status'] != 'ok' and 'prediction' in row:
            raise ValueError('Invalid position has a prediction')
        cost = row.get('observed_cost_usd')
        if cost is None:
            if row.get('cost_unknown') is not True or \
                    row.get('unknown_upper_bound_usd') != str(admission.RESERVE):
                raise ValueError('Unknown charge bound differs')
        elif row.get('cost_unknown') is not False or \
                row.get('unknown_upper_bound_usd') not in (None, '0'):
            raise ValueError('Known charge metadata differs')
        else:
            _money(cost)


def _validate_stopped(rows, expected, attempted):
    if (len(rows) != 60 or [row.get('id') for row in rows] != IDS or
            not 40 < attempted < 60 or
            rows[38].get('status') != 'invalid_output' or
            rows[39].get('status') != 'service_error' or
            rows[attempted - 1].get('status') != 'service_error' or
            rows[attempted - 1].get('cost_unknown') is not True or
            rows[attempted - 1].get('unknown_upper_bound_usd') != str(admission.RESERVE) or
            rows[attempted - 1].get('observed_cost_usd') is not None):
        raise ValueError('Stopped suffix fixed positions differ')
    for index, (row, item) in enumerate(zip(rows, expected)):
        if index >= attempted:
            if row != {'id': item['id'], 'status': 'never_sent'}:
                raise ValueError('Stopped suffix never-sent position differs')
        else:
            if set(row) - POSITION_KEYS or row.get('request_sha256') != item['request_sha256']:
                raise ValueError('Stopped suffix request hash differs')
            if index not in (38, 39, attempted - 1) and row.get('status') not in ('ok', 'invalid_output'):
                raise ValueError('Stopped suffix preceding outcome differs')
            if row['status'] == 'ok' and not valid(row.get('prediction')):
                raise ValueError('Stopped suffix valid prediction differs')
            if row['status'] != 'ok' and 'prediction' in row:
                raise ValueError('Stopped suffix invalid prediction exposed')
            if row.get('observed_cost_usd') is None:
                if row.get('cost_unknown') is not True or \
                        row.get('unknown_upper_bound_usd') != str(admission.RESERVE):
                    raise ValueError('Stopped suffix unknown bound differs')
            else:
                _money(row['observed_cost_usd'])
                if row.get('cost_unknown') is not False:
                    raise ValueError('Stopped suffix known charge differs')


def _snapshot(root, index, manifest, bindings):
    relative = snapshot_path(index)
    path = file(root, relative)
    if not path.exists():
        return None, None
    bound = bind(root, relative, bindings)
    data = json.loads(path.read_text())
    prefix_sha = data.get('budget_prefix_source_sha256')
    evidence = data.get('evidence')
    if (data.get('schema') != SNAPSHOT_SCHEMA or data.get('manifest_sha256') != MANIFEST_SHA or
            data.get('phase_index') != index or data.get('partition_id') != manifest['partition_id'] or
            data.get('source_bindings') != manifest['source_bindings'] or
            data.get('status') not in (('closed_with_service_error', 'stopped') if index == 2
                                       else ('closed',)) or
            data.get('budget_cap_usd') != manifest['child_cap_usd'] or
            type(data.get('source_event_count')) is not int or
            data['source_event_count'] != len(data.get('budget_events') or []) or
            not isinstance(prefix_sha, str) or len(prefix_sha) != 64 or
            any(ch not in '0123456789abcdef' for ch in prefix_sha) or
            not isinstance(evidence, dict)):
        raise ValueError('Public terminal snapshot differs')
    groups = {'suffix': evidence} if index == 2 else evidence
    if set(groups) != ({'suffix'} if index == 2 else {'smoke', 'development'}):
        raise ValueError('Public stage evidence groups differ')
    for stage, group in groups.items():
        if set(group) != {'claim', 'journal', 'raw', 'records', 'review'}:
            raise ValueError('Public stage evidence inventory differs')
        for part, item in group.items():
            suffix = '.root-review.json' if part == 'review' else \
                ('.claim.json' if part == 'claim' else f'.{part}.jsonl')
            expected_path = str(NEW / f'phase-{index + 1:02d}-{stage}{suffix}')
            if (not isinstance(item, dict) or set(item) != {'path', 'sha256'} or
                    item.get('path') != expected_path or
                    not isinstance(item['sha256'], str) or len(item['sha256']) != 64 or
                    any(ch not in '0123456789abcdef' for ch in item['sha256'])):
                raise ValueError('Public stage evidence hash differs')
            if part == 'review':
                bind(root, item['path'], bindings, item['sha256'])
    return data, bound


def _budget(events, rows_by_stage, cap, predecessor=None):
    if (not isinstance(events, list) or not events or
            events[0] != {'event': 'budget', 'cap_usd': cap} or
            (predecessor is not None and events[:len(predecessor)] != predecessor)):
        raise ValueError('Public budget prefix differs')
    expected = [events[0]]
    attempts = set()
    for stage in rows_by_stage:
        for row in stage:
            attempt = row.get('attempt_id')
            if not isinstance(attempt, str) or not attempt or attempt in attempts:
                raise ValueError('Duplicate public attempt')
            attempts.add(attempt)
            expected.append({'event': 'reserve', 'attempt_id': attempt,
                             'record_id': row['id'], 'usd': str(admission.RESERVE)})
            if row.get('cost_unknown'):
                expected.append({'event': 'unknown_cost_accounted_as_upper_bound',
                    'attempt_id': attempt, 'usd': str(admission.RESERVE),
                    'actual_cost_usd': None, 'evidence_sha256': row['evidence_sha256']})
            else:
                expected.append({'event': 'settle', 'attempt_id': attempt,
                                 'usd': row['observed_cost_usd']})
    if events != expected:
        raise ValueError('Public budget settlement differs')
    known = sum((_money(e['usd']) for e in events if e['event'] == 'settle'), Decimal(0))
    unknown = sum((_money(e['usd']) for e in events if
        e['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    if known + unknown > _money(cap):
        raise ValueError('Public child exposure exceeds cap')
    return known, unknown


def _stats(series, maps, ids):
    qwen_report.summaries(series, maps, ids)


def build(root=ROOT):
    root = Path(root).resolve()
    original, manifest, labels, ids, partition, bindings, manifest_binding = source_context(root)
    series = json.loads(json.dumps(original))
    series.update(schema=SCHEMA, seriesId=SERIES, method=METHOD,
        displayName='DeepSeek V4.1 Flash · OpenInference fp4 · reasoning low · interrupted descriptive continuation',
        cleanMatchedThreeEligible=False, historicalPassUsed=False)
    series['limitations'] = [
        'Fresh1/P2 was interrupted at DEV-040. Its 20 never-sent IDs describe that original checkpoint, not live suffix progress.',
        'The continuation changed dispatch timing; this is not a clean matched-three series.',
        'Original private provider error bytes are hash-bound but cannot be reconstructed from a public checkout.',
        'Portable snapshots carry child-ledger prefix hashes; a public checkout cannot rehash private ledger bytes.',
        'Known charges are provider-observed; unknown upper bounds are separate and are not invoices.',
        'Client HTTP duration is not pure provider inference time.',
        'The same 60 synthetic records recur, and provisional v0.2 references are not independent adjudication.',
        'Flip denominators include only positions valid in both passes.']
    maps = {}
    # Existing report has already validated the two closed original stages.
    for index in (0, 1):
        phase = manifest['phases'][index]
        records = additional.read_rows(file(root, BASE /
            f'phase-{index + 1:02d}-development.records.jsonl'))
        maps[(phase['repeat'], phase['condition'])] = records
    series['originalInterruptionCheckpoint'] = {
        'phase': 'fresh1/P2', 'status': 'interrupted_at_DEV-040',
        'attemptedAtInterruption': 40, 'neverSentAtInterruption': 20,
        'outcomesAtInterruption': {'ok': 38, 'invalid_output': 1,
                                  'service_error': 1, 'never_sent': 20},
        'invalidId': 'DEV-039', 'serviceErrorId': 'DEV-040',
        'knownAllAttemptCostUsd': manifest['old_known_actual_usd'],
        'unknownChargeUpperBoundUsd': manifest['old_unknown_charge_upper_bound_usd'],
        'privateEvidenceHashes': {key: manifest['source_bindings'][key]['sha256']
            for key in ('failed_claim', 'failed_journal', 'failed_raw', 'failed_records')},
        'oldTerminalReconciliation': manifest['source_bindings']['old_terminal_reconciliation']}
    suffix, suffix_binding = _snapshot(root, 2, manifest, bindings)
    rows_by_stage = []
    prefix = None
    missing = []
    accounting = {'oldKnownAllAttemptCostUsd': manifest['old_known_actual_usd'],
        'oldUnknownChargeUpperBoundUsd': manifest['old_unknown_charge_upper_bound_usd'],
        'newKnownAllAttemptCostUsd': None, 'newUnknownChargeUpperBoundUsd': None,
        'accountingStatus': 'terminal_public_snapshots_only'}
    if suffix is None:
        missing.append({'pass': 'fresh1', 'condition': 'P2', 'status': 'terminal_public_snapshot_pending'})
        series['continuationStatus'] = 'terminal_suffix_snapshot_pending'
    else:
        positions = suffix.get('positions') or []
        stopped = suffix['status'] == 'stopped'
        if stopped:
            _validate_stopped(positions, manifest['requests_by_condition']['P2'],
                              suffix.get('attempted_count'))
            if (suffix.get('attempted_count') != 49 or suffix.get('never_sent_count') != 11 or
                    positions[48].get('id') != 'DEV-049' or
                    positions[48].get('http_status') != 429 or
                    suffix.get('new_pending_unknown_reserve_usd') != '0' or
                    not isinstance(suffix.get('sealed_child'), dict)):
                raise ValueError('Second interruption terminal disposition differs')
            seal = suffix['sealed_child']
            if (seal.get('partition_id') != manifest['partition_id'] or
                    seal.get('unknown_upper_bound_usd') != str(admission.RESERVE) or
                    not isinstance(seal.get('child_sha256'), str) or
                    len(seal['child_sha256']) != 64 or
                    not isinstance(seal.get('reconciliation_sha256'), str) or
                    len(seal['reconciliation_sha256']) != 64):
                raise ValueError('Second interruption child seal differs')
        else:
            _validate_rows(positions, manifest['requests_by_condition']['P2'], suffix=True)
        if (len(positions) != 60 or positions[39].get('http_status') != 429 or
                positions[39].get('cost_unknown') is not True or
                positions[39].get('observed_cost_usd') is not None or
                suffix.get('status_counts') != dict(Counter(r['status'] for r in positions)) or
                suffix.get('old_known_actual_usd') != manifest['old_known_actual_usd'] or
                suffix.get('old_unknown_charge_upper_bound_usd') !=
                    manifest['old_unknown_charge_upper_bound_usd']):
            raise ValueError('Original interruption changed in suffix snapshot')
        rows_by_stage.append(suffix.get('budget_rows') or [])
        prefix = suffix.get('budget_events')
        known, unknown = _budget(prefix, rows_by_stage, manifest['child_cap_usd'])
        if (suffix.get('new_known_actual_usd') != str(known) or
                suffix.get('new_unknown_charge_upper_bound_usd') != str(unknown)):
            raise ValueError('Suffix accounting differs')
        if stopped and (seal.get('known_actual_usd') != str(known) or
                seal.get('unknown_upper_bound_usd') != str(unknown) or
                seal.get('unused_allocation_released_usd') !=
                    str(_money(manifest['child_cap_usd']) - known - unknown)):
            raise ValueError('Sealed child money differs from public prefix')
        accounting.update(newKnownAllAttemptCostUsd=str(known),
                          newUnknownChargeUpperBoundUsd=str(unknown))
        if stopped:
            missing.append({'pass': 'fresh1', 'condition': 'P2',
                            'status': 'stopped_at_DEV-049_unscored'})
            series['secondInterruptionCheckpoint'] = {
                'phase': 'fresh1/P2', 'status': 'terminal_stopped_at_DEV-049',
                'attemptedAtSecondInterruption': 49,
                'neverSentAtSecondInterruption': 11,
                'invalidIds': ['DEV-039'],
                'serviceErrorIds': ['DEV-040', 'DEV-049'],
                'outcomes': suffix['status_counts'],
                'newKnownAllAttemptCostUsd': str(known),
                'newUnknownChargeUpperBoundUsd': str(unknown),
                'sealedChild': seal, 'publicSnapshot': suffix_binding,
                'score': None}
            series['continuationStatus'] = 'suffix_stopped_at_DEV-049_unscored'
        else:
            score = additional.score(positions, labels, ids)
            series['passes']['fresh1']['P2'] = {'status': 'closed_with_service_error',
                'score': score, 'usage': {'requestCount': 60,
                    'knownDevelopmentCostUsd': str(sum((_money(r['observed_cost_usd']) for r in positions
                        if r.get('observed_cost_usd') is not None), Decimal(0))),
                    'unknownChargeUpperBoundUsd': str(admission.RESERVE),
                    'timingKind': 'client_http_duration_not_provider_inference'},
                'evidence': {'publicSnapshot': suffix_binding, 'privateEvidenceHashesOnly': True}}
            maps[('fresh1', 'P2')] = positions
            series['continuationStatus'] = 'suffix_closed_with_service_error'
    predecessor = prefix
    for index in range(3, 9):
        phase = manifest['phases'][index]
        fresh, condition = phase['repeat'], phase['condition']
        data, bound = _snapshot(root, index, manifest, bindings)
        if data is None:
            missing.append({'pass': fresh, 'condition': condition,
                            'status': 'terminal_public_snapshot_pending'})
            continue
        if predecessor is None or missing:
            raise ValueError('Closed later phase skips an unreported predecessor')
        smoke = data.get('smoke') or []
        development = data.get('development') or []
        if [r.get('id') for r in smoke] != IDS[:3]:
            raise ValueError('Public smoke IDs differ')
        _validate_rows(smoke, manifest['requests_by_condition'][condition][:3])
        _validate_rows(development, manifest['requests_by_condition'][condition])
        if any(row['status'] != 'ok' for row in smoke):
            raise ValueError('Closed smoke has invalid outcome')
        rows_by_stage.extend((smoke, development))
        current = data.get('budget_events')
        known, unknown = _budget(current, rows_by_stage, manifest['child_cap_usd'], predecessor)
        if data.get('new_known_actual_usd') != str(known) or \
                data.get('new_unknown_charge_upper_bound_usd') != str(unknown):
            raise ValueError('Later phase accounting differs')
        predecessor = current
        accounting.update(newKnownAllAttemptCostUsd=str(known),
                          newUnknownChargeUpperBoundUsd=str(unknown))
        series['passes'][fresh][condition] = {'status': 'completed',
            'score': additional.score(development, labels, ids),
            'usage': {'requestCount': 60,
                'knownDevelopmentCostUsd': str(sum((_money(r['observed_cost_usd']) for r in development
                    if r.get('observed_cost_usd') is not None), Decimal(0))),
                'timingKind': 'client_http_duration_not_provider_inference'},
            'evidence': {'publicSnapshot': bound, 'privateEvidenceHashesOnly': True}}
        maps[(fresh, condition)] = development
    accounting['combinedKnownAllAttemptCostUsd'] = (str(
        _money(accounting['oldKnownAllAttemptCostUsd']) +
        _money(accounting['newKnownAllAttemptCostUsd']))
        if suffix is not None else None)
    accounting['combinedUnknownChargeUpperBoundUsd'] = (str(
        _money(accounting['oldUnknownChargeUpperBoundUsd']) +
        _money(accounting['newUnknownChargeUpperBoundUsd']))
        if suffix is not None else None)
    series['budgetAccountingCumulative'] = accounting
    series['completedConditions'] = len(maps)
    series['missingPasses'] = missing
    _stats(series, maps, ids)
    return {'schema': SCHEMA, 'series': [series],
            'availableConfigurations': [admission.CONFIG], 'sourceBindings': bindings,
            'publicVerificationLimit': 'Private provider records and live child ledgers cannot be independently rehashed in a public checkout.'}


def _write_immutable(path, data):
    forbidden = {'user_id', 'raw_response', 'raw_error_response', 'body_base64',
                 'error_body', 'request', 'feedback', 'authorization', 'api_key'}
    def inspect(value):
        if isinstance(value, dict):
            if forbidden.intersection(value):
                raise ValueError('Private provider field in public snapshot')
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(data)
    content = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError('Immutable public snapshot differs')
        return path
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.public-snapshot-', delete=False) as out:
        temporary = Path(out.name)
        out.write(content); out.flush(); os.fsync(out.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()
    return path


def capture(root, index, new_reconciliation=None):
    """Export one terminal stage after private strict verification; no paid calls."""
    root = Path(root).resolve()
    if root != ROOT.resolve() or index not in range(2, 9):
        raise ValueError('Capture needs the canonical private checkout and phase 3-9')
    _, manifest, _, _, partition, _, _ = source_context(root)
    checked = runner.validate_manifest(root / NEW / 'manifest.json', MANIFEST_SHA)
    if checked != manifest:
        raise ValueError('Validated continuation manifest differs')
    if index == 2:
        projection = runner.reconcile_suffix(manifest, MANIFEST_SHA)
        if projection['status'] not in ('closed_with_service_error', 'stopped'):
            raise ValueError('Suffix is not terminally stopped or closed')
        stopped = projection['status'] == 'stopped'
        if stopped and (projection['attempted_count'] != 49 or
                projection['never_sent_count'] != 11 or
                projection['positions'][48]['id'] != 'DEV-049' or
                projection['positions'][48]['status'] != 'service_error' or
                projection['positions'][48].get('http_status') != 429 or
                projection['new_pending_unknown_reserve_usd'] != '0'):
            raise ValueError('DEV-049 terminal suffix differs')
        positions = []
        original_rows = runner.rows(root / BASE / 'phase-03-development.records.jsonl')
        suffix_rows = runner.rows(runner.stage_paths(2, 'suffix')['records'])
        for source in original_rows + suffix_rows:
            row = _row(source)
            row['request_sha256'] = source['request_sha256']
            row['attempt_id'] = source['attempt_id']
            positions.append(row)
        positions.extend({'id': rid, 'status': 'never_sent'}
                         for rid in IDS[len(positions):])
        if any({key: row.get(key) for key in ('id', 'status', 'prediction',
                    'observed_cost_usd', 'cost_unknown', 'unknown_upper_bound_usd')
                if key in row or key in projected} !=
                {key: projected.get(key) for key in ('id', 'status', 'prediction',
                    'observed_cost_usd', 'cost_unknown', 'unknown_upper_bound_usd')
                 if key in row or key in projected}
                for row, projected in zip(positions, projection['positions'])):
            raise ValueError('Private reconciliation and public positions differ')
        evidence = {name: runner.binding(path) for name, path in
            runner.stage_paths(2, 'suffix').items()}
        evidence['review'] = runner.binding(runner.review_path(2, 'suffix'))
        budget_rows = [_row(row) for row in suffix_rows]
        for row in budget_rows:
            row['evidence_sha256'] = evidence['records']['sha256']
        stage_rows = [budget_rows]
    else:
        for predecessor in range(2, index):
            if not (root / snapshot_path(predecessor)).exists():
                raise ValueError('Predecessor public snapshot absent')
        if not all(runner.strict_finished(manifest, MANIFEST_SHA, index, stage)
                   for stage in ('smoke', 'development')):
            raise ValueError('Later stage is not strictly closed')
        smoke_paths = runner.stage_paths(index, 'smoke')
        dev_paths = runner.stage_paths(index, 'development')
        smoke = [_row(row) for row in runner.rows(smoke_paths['records'])]
        development = [_row(row) for row in runner.rows(dev_paths['records'])]
        evidence = {stage: {name: runner.binding(path) for name, path in paths.items()}
            for stage, paths in (('smoke', smoke_paths), ('development', dev_paths))}
        for stage in ('smoke', 'development'):
            evidence[stage]['review'] = runner.binding(runner.review_path(index, stage))
        stage_rows = [smoke, development]
    child = root / NEW / ('budget-' + partition['id'] + '.jsonl')
    raw_lines = child.read_bytes().splitlines(keepends=True)
    if not all(line.endswith(b'\n') for line in raw_lines):
        raise ValueError('Child ledger has incomplete tail')
    # Include only the immutable prefix through this closed phase.
    previous = []
    if index > 2:
        previous = json.loads((root / snapshot_path(index - 1)).read_text())['budget_events']
    count = len(previous) + 2 * sum(len(rows) for rows in stage_rows)
    if index == 2:
        count += 1
    selected = raw_lines[:count]
    if len(selected) != count:
        raise ValueError('Child budget prefix is short')
    events = [qwen_report.prior.sanitize_event(json.loads(line)) for line in selected]
    if index == 2:
        known, unknown = _budget(events, stage_rows, manifest['child_cap_usd'])
        if (projection['new_known_actual_usd'] != str(known) or
                projection['new_unknown_charge_upper_bound_usd'] != str(unknown)):
            raise ValueError('Private suffix and budget differ')
        sealed_child = None
        if stopped:
            if new_reconciliation is None:
                raise ValueError('Stopped suffix needs reviewed child reconciliation')
            reconciliation = Path(new_reconciliation).resolve()
            reconciliation.relative_to(root)
            if reconciliation.parent != (root / NEW).resolve():
                raise ValueError('New reconciliation must be in continuation output')
            receipt = json.loads(reconciliation.read_text())
            ledger = [json.loads(line) for line in raw_lines]
            if (not ledger or ledger[-1].get('event') != 'partition_closed' or
                    receipt.get('event') != 'partition_reconciled' or
                    receipt.get('partition_id') != partition['id'] or
                    receipt.get('child_sha256') != sha(child) or
                    receipt.get('child_ledger') != str(child.resolve()) or
                    receipt.get('known_actual_usd') != str(known) or
                    receipt.get('unknown_upper_bound_usd') != str(unknown) or
                    receipt.get('unused_allocation_released_usd') !=
                        str(Decimal(manifest['child_cap_usd']) - known - unknown) or
                    receipt not in runner.rows(admission.MASTER)):
                raise ValueError('New child is not sealed and reconciled')
            sealed_child = {'partition_id': partition['id'],
                'child_sha256': sha(child),
                'reconciliation_sha256': sha(reconciliation),
                'known_actual_usd': str(known),
                'unknown_upper_bound_usd': str(unknown),
                'unused_allocation_released_usd': receipt['unused_allocation_released_usd']}
        data = {'schema': SNAPSHOT_SCHEMA, 'status': projection['status'],
            'phase_index': index, 'manifest_sha256': MANIFEST_SHA,
            'partition_id': partition['id'], 'budget_cap_usd': manifest['child_cap_usd'],
            'source_bindings': manifest['source_bindings'],
            'positions': positions, 'status_counts': dict(Counter(r['status'] for r in positions)),
            'old_known_actual_usd': manifest['old_known_actual_usd'],
            'old_unknown_charge_upper_bound_usd': manifest['old_unknown_charge_upper_bound_usd'],
            'budget_rows': budget_rows, 'new_known_actual_usd': str(known),
            'new_unknown_charge_upper_bound_usd': str(unknown),
            'new_pending_unknown_reserve_usd': projection['new_pending_unknown_reserve_usd'],
            'attempted_count': projection['attempted_count'],
            'never_sent_count': projection['never_sent_count'],
            'sealed_child': sealed_child,
            'evidence': evidence}
    else:
        previous_rows = []
        for earlier in range(2, index):
            snapshot = json.loads((root / snapshot_path(earlier)).read_text())
            previous_rows.extend([snapshot['budget_rows']] if earlier == 2 else
                                 [snapshot['smoke'], snapshot['development']])
        known, unknown = _budget(events, previous_rows + stage_rows,
                                  manifest['child_cap_usd'], previous)
        data = {'schema': SNAPSHOT_SCHEMA, 'status': 'closed',
            'phase_index': index, 'manifest_sha256': MANIFEST_SHA,
            'partition_id': partition['id'], 'budget_cap_usd': manifest['child_cap_usd'],
            'source_bindings': manifest['source_bindings'],
            'smoke': smoke, 'development': development, 'evidence': evidence,
            'new_known_actual_usd': str(known),
            'new_unknown_charge_upper_bound_usd': str(unknown)}
    data['budget_events'] = events
    data['source_event_count'] = len(events)
    data['budget_prefix_source_sha256'] = hashlib.sha256(b''.join(selected)).hexdigest()
    return _write_immutable(root / snapshot_path(index), data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'public-site/deepseek-low-continuation-repeats.json')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--capture-through-phase', type=int)
    parser.add_argument('--new-reconciliation', type=Path)
    args = parser.parse_args(argv)
    if args.capture_through_phase is not None:
        if args.check:
            parser.error('Capture cannot be combined with --check')
        capture(ROOT, args.capture_through_phase - 1, args.new_reconciliation)
        return
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError('Stale DeepSeek-low continuation report')
    else:
        args.output.write_text(content)


if __name__ == '__main__':
    main()
