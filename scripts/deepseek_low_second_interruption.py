#!/usr/bin/env python3
"""Second versioned DeepSeek low continuation after DEV-049 HTTP 429.

Only DEV-050 through DEV-060 may be sent before the six later phases. The
original and first-continuation attempts and their unknown bounds are immutable.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import quote

import deepseek_low_fresh_repeat_admission as admission
import deepseek_low_fresh_repeat_execution_v2 as original
import deepseek_low_price_successor_v1 as prior_lower_price
import deepseek_low_price_successor_v2 as lower_price
from development_benchmark import ROOT, digest, read_rows, valid
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
import deepseek_low_interruption_continuation as first
import qwen27_fresh_repeat_execution as captured_transport
from openrouter_benchmark import allowed_returned_models

BASE = ROOT / 'results/repeatability-v1/deepseek-low-fresh3-v2'
PREVIOUS = BASE / 'interruption-continuation-v1'
OUTPUT = BASE / 'second-interruption-continuation-v1'
SCHEMA = 'deepseek-low-second-interruption-v1'
PARTITION_ID = 'deepseek-low-second-interruption-20261001'
FIRST_PARTITION_ID = 'deepseek-low-interruption-20260929'
FIRST_MANIFEST_SHA = '358a4667f372aafcfd146f4b9c9aec5fe219e2d4359cf1d0844aed41d0315e63'
FIRST_EVIDENCE_SHA = {
    'claim': '47c644de444cd728b2e65ee2a28c90ff7b7b7b75b0911ccef69496e132d23510',
    'journal': '48a69861a3a4abc3db4aca78955f63375b74306b5f06d3a839fe0584e72d4a98',
    'raw': 'ae999e2423c39e907c29c558b01434197745a38b519e3db9e3892f550a8c34bc',
    'records': '74576ce61c4a55dc44eb3b29529fe4570310221d7344238207fc1ac94e7e69ee'}
FIRST_RECON_SHA = '98688979ac725ae424b943817bd9ae495c98c22efa790cc62a827e243967556c'
FIRST_CHILD_SHA = 'b73bc7adb2bfb5cdb5d7658f2207bc949bff994b433f289218808ad2fc9bc8d4'
RESERVE = admission.RESERVE
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
IDS = [f'DEV-{n:03d}' for n in range(1, 61)]
SEQUENCE = ((2, 'suffix'),) + tuple((i, stage) for i in range(3, 9)
    for stage in ('smoke', 'development'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    data = Path(path).read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('Incomplete JSONL evidence')
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def read_bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['path'])
    return path


def selected_ids(index, stage):
    if (index, stage) not in SEQUENCE:
        raise ValueError('Stage outside never-sent continuation schedule')
    if stage == 'suffix':
        return IDS[49:]
    return IDS[:3] if stage == 'smoke' else IDS


def original_manifest():
    path = BASE / 'manifest.json'
    return original.load_manifest(path, lower_price.MANIFEST_SHA)


def _body_result(body, endpoint):
    if not isinstance(body, dict):
        raise ValueError('Original raw response is not an object')
    choices = body.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError('Original raw response has wrong choice count')
    choice = choices[0]
    message = choice.get('message') or {}
    try:
        prediction = json.loads(message.get('content'))
    except (ValueError, TypeError):
        prediction = None
    status = ('ok' if valid(prediction) and choice.get('finish_reason') == 'stop'
        and not choice.get('error') and not message.get('refusal')
        and not message.get('tool_calls') and not message.get('function_call')
        else 'invalid_output')
    if body.get('model') not in allowed_returned_models(admission.MODEL, endpoint):
        status = 'model_mismatch'
    if body.get('provider') != endpoint['provider_name']:
        status = 'provider_mismatch'
    usage = body.get('usage') or {}
    actual = str(paid.number(usage['cost'])) if usage.get('cost') is not None else None
    return status, prediction, actual, choice.get('finish_reason')


def verify_stopped_prefix():
    """Read-only verification of both immutable stopped prefixes."""
    original_prefix = first.verify_stopped_prefix()
    first.verify_old_seal(BASE / 'terminal-reconciliation-after-dev040.json', original_prefix)
    manifest = first.validate_manifest(PREVIOUS / 'manifest.json', FIRST_MANIFEST_SHA)
    for key, expected in FIRST_EVIDENCE_SHA.items():
        if sha(first.stage_paths(2, 'suffix')[key]) != expected:
            raise ValueError('First continuation evidence hash changed: ' + key)
    projection = first.reconcile_suffix(manifest, FIRST_MANIFEST_SHA)
    if (projection['status'] != 'stopped' or
            projection['status_counts'] != {'ok': 46, 'invalid_output': 1,
                                            'service_error': 2, 'never_sent': 11} or
            projection['positions'][48]['id'] != 'DEV-049' or
            projection['positions'][48]['status'] != 'service_error' or
            [p['id'] for p in projection['positions'][49:]] != IDS[49:]):
        raise ValueError('First continuation stopped prefix differs')
    evidence = {key: binding(first.stage_paths(2, 'suffix')[key])
                for key in FIRST_EVIDENCE_SHA}
    records = rows(first.stage_paths(2, 'suffix')['records'])
    if ([r['id'] for r in records] != IDS[40:49] or
            records[-1].get('http_status') != 429 or
            records[-1].get('cost_unknown') is not True):
        raise ValueError('DEV-049 attempt differs')
    return {'original': original_prefix, 'attempted_ids': IDS[:49],
            'remaining_ids': IDS[49:], 'failed_id': 'DEV-049',
            'failed_attempt_id': records[-1]['attempt_id'],
            'invalid_ids': ['DEV-039'], 'prior_service_errors': ['DEV-040', 'DEV-049'],
            'records_sha256': FIRST_EVIDENCE_SHA['records'], 'evidence': evidence,
            'first_manifest': binding(PREVIOUS / 'manifest.json'),
            'first_review': binding(first.review_path(2, 'suffix'))}


def verify_old_seal(reconciliation_path, prefix):
    """Verify first child's full DEV-049 bound and terminal master event."""
    child = PREVIOUS / f'budget-{FIRST_PARTITION_ID}.jsonl'
    reconciliation_path = Path(reconciliation_path).resolve()
    if (reconciliation_path != (PREVIOUS / 'terminal-reconciliation-after-dev049.json').resolve() or
            sha(child) != FIRST_CHILD_SHA or sha(reconciliation_path) != FIRST_RECON_SHA):
        raise ValueError('First child seal or reconciliation hash differs')
    events = rows(child)
    charges = [e for e in events if e.get('attempt_id') == prefix['failed_attempt_id']]
    expected_reserve = {'event': 'reserve', 'attempt_id': prefix['failed_attempt_id'],
                        'record_id': 'DEV-049', 'usd': str(RESERVE)}
    if (len(charges) != 2 or charges[0] != expected_reserve or
            charges[1].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            charges[1].get('usd') != str(RESERVE) or
            charges[1].get('actual_cost_usd') is not None or
            charges[1].get('evidence_sha256') != prefix['records_sha256'] or
            Path(charges[1].get('evidence_path', '')).resolve() !=
                first.stage_paths(2, 'suffix')['records'].resolve() or
            events[-1].get('event') != 'partition_closed'):
        raise ValueError('DEV-049 unknown bound or child seal differs')
    known = sum((paid.number(e['usd']) for e in events if e['event'] == 'settle'), Decimal(0))
    unknown = sum((paid.number(e['usd']) for e in events
                   if e['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    if (known, unknown, paid.number(events[0]['cap_usd'])) != (
            Decimal('0.00202348'), RESERVE, Decimal('0.14')):
        raise ValueError('First child accounting differs')
    event = json.loads(reconciliation_path.read_text())
    expected = {'event': 'partition_reconciled',
                'partition_id': FIRST_PARTITION_ID,
                'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(unknown),
                'unused_allocation_released_usd': str(Decimal('0.14') - known - unknown),
                'child_ledger': str(child.resolve()), 'child_sha256': sha(child)}
    if event != expected or event not in rows(admission.MASTER):
        raise ValueError('First child master reconciliation differs')
    return {'old_child_ledger': binding(child),
            'old_terminal_reconciliation': binding(reconciliation_path),
            'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(unknown),
            'released_usd': expected['unused_allocation_released_usd']}


def budget_entry(path, require_fresh=False, require_dispatch=False):
    """Check v3 master allocation and child terminal lifecycle read-only."""
    path = Path(path).resolve()
    if path != (OUTPUT / 'budget.json').resolve():
        raise ValueError('Second child budget path differs')
    data = json.loads(path.read_text())
    entries = data.get('partitions')
    if (data.get('version') != 'paid-partitions-v1' or
            data.get('master_ledger') != str(admission.MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Second child manifest differs')
    entry = entries[0]
    cap = paid.number(entry.get('cap_usd'))
    child = OUTPUT / ('budget-' + PARTITION_ID + '.jsonl')
    if (entry.get('id') != PARTITION_ID or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) !=
                (admission.MODEL, admission.PROVIDER, 'low') or
            cap < RESERVE or cap > Decimal('12.38') or
            Path(entry.get('child_ledger', '')).resolve() != child.resolve()):
        raise ValueError('Second child route, cap or path differs')
    master = rows(admission.MASTER)
    if (not master or master[0].get('event') != 'budget' or
            master[0].get('cap_usd') not in ('1', '5', '10', '12.38')):
        raise ValueError('Approved v3 master cap differs')
    current_cap = master[0]['cap_usd']
    for event in master[1:]:
        if event.get('event') == 'cap_amendment':
            if event.get('previous_cap_usd') != current_cap:
                raise ValueError('Approved v3 cap amendment chain differs')
            current_cap = event.get('cap_usd')
    if current_cap != '12.38':
        raise ValueError('Approved v3 master cap differs')
    allocations = [e for e in master if e.get('event') == 'budget_partition' and
                   e.get('partition_id') == PARTITION_ID]
    expected_allocation = {'allocated_usd': entry['cap_usd'],
        'manifest_path': str(path), 'manifest_sha256': sha(path),
        'child_ledger': str(child.resolve()), 'model': admission.MODEL,
        'provider': admission.PROVIDER, 'reasoning': 'low'}
    if len(allocations) != 1 or any(allocations[0].get(k) != v
                                    for k, v in expected_allocation.items()):
        raise ValueError('Second child allocation absent or changed')
    events = rows(child)
    if not events or events[0] != {'event': 'budget', 'cap_usd': entry['cap_usd']}:
        raise ValueError('Second child opening differs')
    reconciliations = [e for e in master if e.get('event') == 'partition_reconciled'
                       and e.get('partition_id') == PARTITION_ID]
    closed = [i for i, e in enumerate(events) if e.get('event') == 'partition_closed']
    if require_fresh and (reconciliations or closed or len(events) != 1):
        raise ValueError('Second child is spent, sealed or reconciled')
    if require_dispatch and (reconciliations or closed):
        raise ValueError('Second child is sealed or reconciled')
    if reconciliations or closed:
        if len(reconciliations) != 1 or closed != [len(events) - 1]:
            raise ValueError('Second child terminal lifecycle differs')
        pending = {}
        known = unknown = Decimal(0)
        for event in events[1:-1]:
            kind, attempt = event.get('event'), event.get('attempt_id')
            if kind == 'reserve':
                amount = paid.number(event.get('usd'))
                if pending or not attempt or amount != RESERVE:
                    raise ValueError('Second child reservation lifecycle differs')
                pending[attempt] = amount
            elif kind == 'settle':
                amount = paid.number(event.get('usd'))
                if attempt not in pending or not Decimal(0) <= amount <= pending[attempt]:
                    raise ValueError('Second child settlement lifecycle differs')
                known += amount
                del pending[attempt]
            elif kind == 'unknown_cost_accounted_as_upper_bound':
                amount = paid.number(event.get('usd'))
                if (attempt not in pending or amount != pending[attempt] or
                        event.get('actual_cost_usd') is not None or
                        not event.get('reason') or not event.get('evidence_path') or
                        not event.get('evidence_sha256')):
                    raise ValueError('Second child unknown lifecycle differs')
                unknown += amount
                del pending[attempt]
            else:
                raise ValueError('Second child terminal event differs')
        if pending or known + unknown > cap:
            raise ValueError('Second child terminal accounting differs')
        expected = {'event': 'partition_reconciled', 'partition_id': PARTITION_ID,
            'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(unknown),
            'unused_allocation_released_usd': str(cap - known - unknown),
            'child_ledger': str(child.resolve()), 'child_sha256': sha(child)}
        if reconciliations[0] != expected:
            raise ValueError('Second child terminal reconciliation differs')
    return entry


def expected_manifest(budget_path, first_reconciliation_path, require_fresh=False):
    prefix = verify_stopped_prefix()
    old = verify_old_seal(first_reconciliation_path, prefix)
    lower_price.verify_route_audit()
    entry = budget_entry(budget_path, require_fresh=require_fresh)
    original_plan = original_manifest()
    sources = {'original_manifest': binding(BASE / 'manifest.json'),
        'original_controller': binding(original.__file__),
        'first_controller': binding(first.__file__),
        'first_manifest': prefix['first_manifest'],
        'first_review': prefix['first_review'],
        'lower_price_controller': binding(prior_lower_price.__file__),
        'second_price_controller': binding(lower_price.__file__),
        'bounded_byte_transport': binding(captured_transport.__file__),
        'lower_price_route_audit': binding(prior_lower_price.ROUTE_AUDIT),
        'second_price_route_audit': binding(lower_price.ROUTE_AUDIT),
        'second_price_raw_models': binding(lower_price.RAW_MODELS),
        'second_price_raw_endpoints': binding(lower_price.RAW_ENDPOINTS),
        'v3_partition_controller': binding(partitions.__file__),
        'v3_budget_controller': binding(__import__('openrouter_budget_v3').__file__),
        'new_budget_manifest': binding(budget_path),
        'first_child_ledger': old['old_child_ledger'],
        'first_terminal_reconciliation': old['old_terminal_reconciliation']}
    sources.update({'first_suffix_' + key: value
                    for key, value in prefix['evidence'].items()})
    sources.update({'original_failed_' + key: value
                    for key, value in prefix['original']['evidence'].items()})
    sources['original_terminal_reconciliation'] = binding(
        BASE / 'terminal-reconciliation-after-dev040.json')
    for index, stage in ((i, st) for i in range(3) for st in ('smoke', 'development')
                         if (i, st) != (2, 'development')):
        for kind, path in original.paths(BASE, index, stage).items():
            sources[f'phase_{index + 1:02d}_{stage}_{kind}'] = binding(path)
    return {'schema': SCHEMA, 'status': 'FROZEN',
        'method': 'descriptive-second-interruption-continuation',
        'clean_matched_three_eligible': False,
        'configuration_id': admission.CONFIG,
        'schedule': [{'phase_index': i, 'stage': st} for i, st in SEQUENCE],
        'phases': original_plan['phases'],
        'requests_by_condition': original_plan['requests_by_condition'],
        'route': original_plan['route'],
        'original_failed_id': 'DEV-040', 'first_suffix_failed_id': 'DEV-049',
        'original_invalid_id': 'DEV-039',
        'original_known_actual_usd': '0.04109562',
        'first_known_actual_usd': '0.00202348',
        'original_unknown_charge_upper_bound_usd': str(RESERVE),
        'first_unknown_charge_upper_bound_usd': old['unknown_upper_bound_usd'],
        'source_bindings': sources, 'controller': binding(__file__),
        'output_directory': str(OUTPUT.resolve().relative_to(ROOT.resolve())),
        'partition_id': entry['id'], 'child_cap_usd': entry['cap_usd'],
        'reserve_usd': str(RESERVE), 'reference_labels_read': False,
        'retry_policy': 'no retries, repairs or replay of DEV-001 through DEV-049'}


def freeze(manifest_path, budget_path, first_reconciliation_path):
    manifest_path = Path(manifest_path).resolve()
    if manifest_path != (OUTPUT / 'manifest.json').resolve() or manifest_path.exists():
        raise ValueError('Require a new second-continuation manifest path')
    manifest = expected_manifest(budget_path, first_reconciliation_path,
                                 require_fresh=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with manifest_path.open('x') as out:
        json.dump(manifest, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return manifest


def validate_manifest(path, expected_sha):
    path = Path(path).resolve()
    if path != (OUTPUT / 'manifest.json').resolve() or sha(path) != expected_sha:
        raise ValueError('Second continuation manifest path or hash differs')
    manifest = json.loads(path.read_text())
    sources = manifest['source_bindings']
    for item in sources.values():
        read_bound(item)
    if manifest != expected_manifest(read_bound(sources['new_budget_manifest']),
                                     read_bound(sources['first_terminal_reconciliation'])):
        raise ValueError('Second continuation manifest differs from sealed sources')
    return manifest


def stage_paths(index, stage):
    selected_ids(index, stage)
    return original.paths(OUTPUT, index, stage)


def review_path(index, stage):
    selected_ids(index, stage)
    return OUTPUT / f'phase-{index + 1:02d}-{stage}.root-review.json'


def selected_items(manifest, index, stage):
    ids = selected_ids(index, stage)
    phase = manifest['phases'][index]
    frozen = manifest['requests_by_condition'][phase['condition']]
    if [item['id'] for item in frozen] != IDS:
        raise ValueError('Frozen 60-ID membership changed')
    return frozen[49:] if stage == 'suffix' else frozen[:len(ids)]


def verify_review(path, manifest, manifest_sha, index, stage):
    path = Path(path).resolve()
    if path != review_path(index, stage).resolve():
        raise ValueError('Exact root review path differs')
    receipt = json.loads(path.read_text())
    expected = {'schema': SCHEMA + '-stage-review', 'approved': True,
        'manifest_sha256': manifest_sha,
        'controller_sha256': manifest['controller']['sha256'],
        'first_terminal_reconciliation_sha256':
            manifest['source_bindings']['first_terminal_reconciliation']['sha256'],
        'new_budget_manifest_sha256':
            manifest['source_bindings']['new_budget_manifest']['sha256'],
        'partition_id': manifest['partition_id'],
        'child_cap_usd': manifest['child_cap_usd'],
        'phase_index': index, 'stage': stage, 'ids': selected_ids(index, stage)}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Stage review does not bind exact sources and budget')
    return receipt


def _new_charge_events(manifest):
    budget = read_bound(manifest['source_bindings']['new_budget_manifest'])
    entry = budget_entry(budget)
    ledger_path = Path(entry['child_ledger'])
    events = rows(ledger_path)
    if not events or events[0] != {'event': 'budget', 'cap_usd': manifest['child_cap_usd']}:
        raise ValueError('New child ledger opening differs')
    return events


def strict_finished(manifest, manifest_sha, index, stage):
    """Check complete new stage against frozen requests, raw bytes and charges."""
    p = stage_paths(index, stage)
    if not all(path.is_file() for path in p.values()):
        return False
    try:
        review = review_path(index, stage)
        verify_review(review, manifest, manifest_sha, index, stage)
        claim = json.loads(p['claim'].read_text())
        phase = manifest['phases'][index]
        expected_claim = {'schema': SCHEMA + '-stage-claim',
            'manifest_sha256': manifest_sha, 'review_sha256': sha(review),
            'budget_manifest_sha256': manifest['source_bindings']['new_budget_manifest']['sha256'],
            'partition_id': manifest['partition_id'], 'phase_index': index,
            'repeat': phase['repeat'], 'condition': phase['condition'],
            'stage': stage, 'ids': selected_ids(index, stage)}
        if any(claim.get(key) != value for key, value in expected_claim.items()):
            return False
        events, raw, records = (rows(p[k]) for k in ('journal', 'raw', 'records'))
        items = selected_items(manifest, index, stage)
        if (len(records) != len(items) or len(raw) != len(items) or
                [r.get('id') for r in records] != selected_ids(index, stage) or
                events[0] != {'event': 'stage_claimed', 'claim_sha256': sha(p['claim'])} or
                events[-1] != {'event': 'stage_completed', 'count': len(items)} or
                len(events) != 2 + 3 * len(items)):
            return False
        charge_events = _new_charge_events(manifest)
        attempts = set()
        raw_lines = p['raw'].read_bytes().splitlines(keepends=True)
        for pos, (item, row, sidecar) in enumerate(zip(items, records, raw)):
            attempt = row.get('attempt_id')
            if not isinstance(attempt, str) or not attempt or attempt in attempts:
                return False
            attempts.add(attempt)
            started, saved, ended = events[1 + 3 * pos:4 + 3 * pos]
            if (started != {'event': 'request_started', 'attempt_id': attempt,
                    'id': item['id'], 'request_sha256': item['request_sha256'],
                    'reserved_cost_usd': str(RESERVE)} or
                    saved != {'event': 'raw_saved', 'attempt_id': attempt,
                        'raw_sha256': hashlib.sha256(b''.join(raw_lines[:pos + 1])).hexdigest()} or
                    ended != {'event': 'request_finished', 'attempt_id': attempt,
                        'id': item['id'], 'status': row.get('status'),
                        'billing_ok': row.get('billing_ok')} or
                    row.get('request_sha256') != item['request_sha256'] or
                    digest(json.dumps(row.get('request'), sort_keys=True)) != item['request_sha256'] or
                    row.get('input_sha256') != item['input_sha256'] or
                    row.get('policy_sha256') != item['instruction_sha256'] or
                    row.get('requested_model') != admission.MODEL or
                    row.get('reasoning_effort') != 'low' or
                    row.get('provider_endpoint', {}).get('tag') != admission.PROVIDER or
                    row.get('reference_labels_read') is not False or
                    row.get('budget_partition_id') != manifest['partition_id'] or
                    row.get('reserved_cost_usd') != str(RESERVE) or
                    sidecar.get('id') != item['id'] or
                    sidecar.get('attempt_id') != attempt or
                    sidecar.get('request_sha256') != item['request_sha256'] or
                    sidecar.get('http_status') != 200 or
                    sidecar.get('body_truncated_at_limit') is not False or
                    sidecar.get('read_error') is not None or
                    row.get('cost_unknown') is not False or
                    row.get('billing_ok') is not True or
                    row.get('continue_on_invalid_output') is not True):
                return False
            body = json.loads(base64.b64decode(sidecar['body_base64'], validate=True))
            status, prediction, actual, finish = _body_result(body, row['provider_endpoint'])
            if (actual is None or row.get('raw_response') != body or
                    row.get('status') != status or
                    (stage == 'smoke' and status != 'ok') or
                    status not in ('ok', 'invalid_output') or
                    row.get('prediction') != prediction or
                    row.get('finish_reason') != finish or
                    row.get('usage') != body.get('usage') or
                    row.get('returned_model') != body.get('model') or
                    row.get('returned_provider') != body.get('provider') or
                    row.get('observed_cost_usd') != actual or
                    [e for e in charge_events if e.get('attempt_id') == attempt] != [
                        {'event': 'reserve', 'attempt_id': attempt,
                         'record_id': item['id'], 'usd': str(RESERVE)},
                        {'event': 'settle', 'attempt_id': attempt, 'usd': actual}]):
                return False
        return True
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OSError):
        return False


def reconcile_suffix(manifest, manifest_sha):
    """Return an allowlisted 60-position projection; raw bytes stay private."""
    verify_stopped_prefix()
    p = stage_paths(2, 'suffix')
    if not p['claim'].exists():
        if any(p[k].exists() for k in ('journal', 'raw', 'records')):
            raise ValueError('Suffix evidence exists without a claim')
        new, status = [], 'not_started'
    else:
        if not all(path.is_file() for path in p.values()):
            raise ValueError('Claimed suffix evidence is incomplete')
        claim = json.loads(p['claim'].read_text())
        receipt = review_path(2, 'suffix')
        verify_review(receipt, manifest, manifest_sha, 2, 'suffix')
        phase = manifest['phases'][2]
        expected_claim = {'schema': SCHEMA + '-stage-claim',
            'manifest_sha256': manifest_sha, 'review_sha256': sha(receipt),
            'budget_manifest_sha256': manifest['source_bindings']['new_budget_manifest']['sha256'],
            'partition_id': manifest['partition_id'], 'phase_index': 2,
            'repeat': phase['repeat'], 'condition': phase['condition'],
            'stage': 'suffix', 'ids': IDS[49:]}
        if any(claim.get(key) != value for key, value in expected_claim.items()):
            raise ValueError('Suffix claim changed')
        events, raw, new = (rows(p[k]) for k in ('journal', 'raw', 'records'))
        if ([r.get('id') for r in new] != IDS[49:49 + len(new)] or
                len(raw) != len(new) or len(new) > 11 or
                len(events) != 2 + 3 * len(new) or
                events[0] != {'event': 'stage_claimed', 'claim_sha256': sha(p['claim'])}):
            raise ValueError('Suffix ordered attempts or journal count changed')
        charge_events = _new_charge_events(manifest)
        raw_lines = p['raw'].read_bytes().splitlines(keepends=True)
        attempts = set()
        for pos, (row, sidecar) in enumerate(zip(new, raw)):
            item = selected_items(manifest, 2, 'suffix')[pos]
            attempt = row.get('attempt_id')
            if not isinstance(attempt, str) or not attempt or attempt in attempts:
                raise ValueError('Suffix attempt ID missing or duplicated')
            attempts.add(attempt)
            started, saved, ended = events[1 + 3 * pos:4 + 3 * pos]
            if (started != {'event': 'request_started', 'attempt_id': attempt,
                    'id': item['id'], 'request_sha256': item['request_sha256'],
                    'reserved_cost_usd': str(RESERVE)} or
                    saved != {'event': 'raw_saved', 'attempt_id': attempt,
                        'raw_sha256': hashlib.sha256(b''.join(raw_lines[:pos + 1])).hexdigest()} or
                    ended != {'event': 'request_finished', 'attempt_id': attempt,
                        'id': item['id'], 'status': row.get('status'),
                        'billing_ok': row.get('billing_ok')} or
                    sidecar.get('id') != item['id'] or
                    sidecar.get('attempt_id') != attempt or
                    sidecar.get('request_sha256') != item['request_sha256'] or
                    row.get('request_sha256') != item['request_sha256'] or
                    digest(json.dumps(row.get('request'), sort_keys=True)) != item['request_sha256'] or
                    row.get('input_sha256') != item['input_sha256'] or
                    row.get('policy_sha256') != item['instruction_sha256'] or
                    row.get('requested_model') != admission.MODEL or
                    row.get('reasoning_effort') != 'low' or
                    row.get('provider_endpoint', {}).get('tag') != admission.PROVIDER or
                    row.get('budget_partition_id') != manifest['partition_id'] or
                    row.get('reference_labels_read') is not False or
                    row.get('reserved_cost_usd') != str(RESERVE)):
                raise ValueError('Suffix request, raw or journal evidence differs')
            charges = [e for e in charge_events if e.get('attempt_id') == attempt]
            expected_reserve = {'event': 'reserve', 'attempt_id': attempt,
                'record_id': item['id'], 'usd': str(RESERVE)}
            actual = row.get('observed_cost_usd')
            if actual is None:
                if (row.get('cost_unknown') is not True or
                        row.get('billing_ok') is not False or not charges or
                        charges[0] != expected_reserve):
                    raise ValueError('Suffix unknown charge differs')
                if len(charges) == 2:
                    upper = charges[1]
                    if (upper.get('event') != 'unknown_cost_accounted_as_upper_bound' or
                            upper.get('usd') != str(RESERVE) or
                            upper.get('evidence_sha256') != sha(p['records']) or
                            Path(upper.get('evidence_path', '')).resolve() != p['records'].resolve()):
                        raise ValueError('Suffix unknown upper bound differs')
                elif len(charges) != 1:
                    raise ValueError('Suffix unknown charge event count differs')
            elif (row.get('cost_unknown') is not False or
                  charges != [expected_reserve,
                      {'event': 'settle', 'attempt_id': attempt,
                       'usd': str(paid.number(actual))}]):
                raise ValueError('Suffix known charge differs')
            if sidecar.get('http_status') == 200 and sidecar.get('read_error') is None \
                    and sidecar.get('body_truncated_at_limit') is False:
                try:
                    body = json.loads(base64.b64decode(sidecar['body_base64'], validate=True))
                except (ValueError, TypeError):
                    body = None
                if body is not None and isinstance(body, dict):
                    try:
                        expected_status, prediction, body_cost, finish = _body_result(
                            body, row['provider_endpoint'])
                    except (ValueError, TypeError, AttributeError, KeyError, IndexError):
                        # The execution loop preserves a parseable object with
                        # invalid choice structure as a service error. Keep its
                        # failed position and the charge observed before parse.
                        usage = body.get('usage') or {}
                        try:
                            body_cost = (str(paid.number(usage['cost'])) if isinstance(usage, dict) and
                                usage.get('cost') is not None else None)
                        except (ValueError, TypeError, KeyError, AttributeError):
                            body_cost = None
                        expected_billing = body_cost is not None and paid.number(body_cost) <= RESERVE
                        expected_status = ('billing_blocked' if body_cost is not None and
                            not expected_billing else 'service_error')
                        if (row.get('status') != expected_status or
                                row.get('raw_response') != body or
                                row.get('usage') != usage or
                                row.get('observed_cost_usd') != body_cost or
                                row.get('billing_ok') is not expected_billing):
                            raise ValueError('Malformed suffix object differs') from None
                    else:
                        observed_status = ('billing_blocked' if body_cost is not None and
                            row.get('billing_ok') is False else expected_status)
                        if (row.get('status') != observed_status or
                                row.get('raw_response') != body or
                                row.get('prediction') != prediction or
                                row.get('finish_reason') != finish or
                                row.get('usage') != body.get('usage') or
                                row.get('observed_cost_usd') != body_cost):
                            raise ValueError('Suffix parsed response differs')
                elif row.get('status') != 'service_error':
                    raise ValueError('Malformed suffix body status differs')
            elif (row.get('status') != 'service_error' or
                  row.get('http_status') != sidecar.get('http_status')):
                raise ValueError('Suffix transport error differs')
        last = events[-1]
        if (len(new) == 11 and last == {'event': 'stage_completed', 'count': 11}
                and strict_finished(manifest, manifest_sha, 2, 'suffix')):
            status = 'closed_with_prior_service_errors'
        elif (len(new) < 11 and last == {'event': 'admission_stopped',
                'next_unsent_id': IDS[49 + len(new)], 'reason': 'child_cap'} and
                all(r.get('status') in ('ok', 'invalid_output') and
                    r.get('billing_ok') is True for r in new)):
            status = 'admission_stopped'
        elif (new and last == {'event': 'stage_stopped', 'id': new[-1]['id'],
                'reason': new[-1]['status']} and
                all(r.get('status') in ('ok', 'invalid_output') and
                    r.get('billing_ok') is True for r in new[:-1])):
            status = 'stopped'
        else:
            raise ValueError('Suffix terminal state differs')
    def project(row):
        result = {'id': row['id'], 'status': row['status'],
            'observed_cost_usd': row.get('observed_cost_usd'),
            'cost_unknown': row.get('cost_unknown') is True,
            'unknown_upper_bound_usd': str(RESERVE) if row.get('cost_unknown') else '0'}
        if row['status'] == 'ok':
            result['prediction'] = row.get('prediction')
        usage = row.get('usage') or {}
        result['usage'] = {k: usage[k] for k in ('prompt_tokens', 'completion_tokens')
                           if type(usage.get(k)) is int and usage[k] >= 0}
        if type(row.get('client_http_duration_seconds')) in (int, float):
            result['client_http_duration_seconds'] = row['client_http_duration_seconds']
        if type(row.get('http_status')) is int:
            result['http_status'] = row['http_status']
        return result
    old = (rows(BASE / 'phase-03-development.records.jsonl') +
           rows(first.stage_paths(2, 'suffix')['records']))
    positions = [project(row) for row in old + new]
    positions += [{'id': rid, 'status': 'never_sent'} for rid in IDS[len(positions):]]
    if len(positions) != 60 or positions[38]['status'] != 'invalid_output' or \
            positions[39]['status'] != 'service_error' or \
            positions[48]['status'] != 'service_error':
        raise ValueError('Composite fixed-60 positions changed')
    known = sum((paid.number(row['observed_cost_usd']) for row in new
        if row.get('observed_cost_usd') is not None), Decimal(0))
    unknown = sum((RESERVE for row in new if row.get('cost_unknown') is True), Decimal(0))
    pending = Decimal(0)
    if new:
        charge_events = _new_charge_events(manifest)
        for row in new:
            if row.get('cost_unknown') is True and len([event for event in charge_events
                    if event.get('attempt_id') == row['attempt_id']]) == 1:
                pending += RESERVE
    return {'schema': SCHEMA + '-suffix-projection', 'status': status,
        'method': manifest['method'], 'denominator': 60,
        'clean_matched_three_eligible': False,
        'original_failed_id': 'DEV-040', 'first_suffix_failed_id': 'DEV-049',
        'original_invalid_id': 'DEV-039',
        'original_known_actual_usd': '0.04109562',
        'first_known_actual_usd': '0.00202348',
        'original_unknown_charge_upper_bound_usd': str(RESERVE),
        'first_unknown_charge_upper_bound_usd': str(RESERVE),
        'new_known_actual_usd': str(known),
        'new_unknown_charge_upper_bound_usd': str(unknown),
        'new_pending_unknown_reserve_usd': str(pending),
        'attempted_count': len(positions) - sum(p['status'] == 'never_sent' for p in positions),
        'never_sent_count': sum(p['status'] == 'never_sent' for p in positions),
        'status_counts': {kind: sum(p['status'] == kind for p in positions)
                          for kind in sorted({p['status'] for p in positions})},
        'positions': positions,
        'manifest_sha256': manifest_sha,
        'source_hashes': {k: v['sha256'] for k, v in manifest['source_bindings'].items()},
        'private_evidence_note': 'Original error bytes remain private; hashes bind them.'}


def prepare(manifest_path, manifest_sha, budget_path, index, stage, review):
    manifest = validate_manifest(manifest_path, manifest_sha)
    selected_ids(index, stage)
    if Path(budget_path).resolve() != read_bound(
            manifest['source_bindings']['new_budget_manifest']):
        raise ValueError('New budget binding differs')
    receipt = verify_review(review, manifest, manifest_sha, index, stage)
    if budget_entry(budget_path, require_dispatch=True)['cap_usd'] != manifest['child_cap_usd']:
        raise ValueError('New child cap changed')
    position = SEQUENCE.index((index, stage))
    for previous_index, previous_stage in SEQUENCE[:position]:
        if previous_stage == 'suffix':
            if reconcile_suffix(manifest, manifest_sha)['status'] != 'closed_with_prior_service_errors':
                raise ValueError('DEV-050 through DEV-060 suffix is not closed')
        elif not strict_finished(manifest, manifest_sha, previous_index, previous_stage):
            raise ValueError('Previous scheduled stage is not strictly closed')
    if stage == 'development':
        smoke = stage_paths(index, 'smoke')
        inspection = receipt.get('smoke_inspection') or {}
        if (inspection.get('approved') is not True or
                inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + key + '_sha256') != sha(smoke[key])
                    for key in ('records', 'journal', 'raw'))):
            raise ValueError('Actual three-response smoke inspection differs')
    target = stage_paths(index, stage)
    if any(path.exists() for path in target.values()):
        raise FileExistsError('Stage already claimed; no replay')
    return manifest, target


def _rebuild_requests(manifest, index, stage, endpoint, model_info):
    history, controls, historical_endpoint, historical_model = admission.source_state()
    phase = manifest['phases'][index]
    condition = phase['condition']
    policy_source = (history['baseline_instruction'] if condition == 'P0'
                     else history['conditions'][condition]['instruction'])
    policy = (ROOT / policy_source['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    inputs = __import__('development_benchmark').read_rows(admission.INPUTS)
    if [row['id'] for row in inputs] != IDS:
        raise ValueError('Current input membership changed')
    items = selected_items(manifest, index, stage)
    selected = inputs[49:] if stage == 'suffix' else inputs[:len(items)]
    rebuilt = []
    for row, item in zip(selected, items):
        payload = paid.make_payload(admission.MODEL, endpoint, row['feedback'],
            policy, schema, 'low', 4096, paid.number('0.1'), paid.number('0.5'), model_info)
        historical = paid.make_payload(admission.MODEL, historical_endpoint,
            row['feedback'], policy, schema, 'low', 4096,
            paid.number('0.1'), paid.number('0.5'), historical_model)
        if (row['id'] != item['id'] or payload != historical or
                digest(json.dumps(payload, sort_keys=True)) != item['request_sha256'] or
                digest(row['feedback']) != item['input_sha256'] or
                digest(policy) != item['instruction_sha256']):
            raise ValueError('Frozen request differs before paid call')
        rebuilt.append((row, item, payload))
    return rebuilt


def _capture_error(raw, rid, attempt, request_sha, exc, token):
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code
        try:
            body, length, truncated, redacted, read_error = \
                captured_transport.response_bytes(exc, token)
            headers = captured_transport.safe_headers(exc, token)
        except Exception as read_exc:
            body, length, truncated, redacted = b'', 0, False, False
            read_error, headers = type(read_exc).__name__, {}
    else:
        body, length, truncated, redacted, read_error = b'', 0, False, False, None
        status, headers = None, {}
    paid.durable(raw, {'id': rid, 'attempt_id': attempt,
        'request_sha256': request_sha, 'http_status': status,
        'response_headers': headers,
        'body_base64': base64.b64encode(body).decode('ascii'),
        'body_bytes_captured': length, 'body_truncated_at_limit': truncated,
        'body_token_redacted': redacted, 'read_error': read_error,
        'transport_error': type(exc).__name__,
        'received_utc': datetime.now(timezone.utc).isoformat()})


def execute(manifest_path, manifest_sha, budget_path, index, stage, review,
            env_file=None):
    manifest, target = prepare(manifest_path, manifest_sha, budget_path,
                               index, stage, review)
    if captured_transport.MAX_RESPONSE_BYTES != MAX_RESPONSE_BYTES:
        raise ValueError('Reviewed bounded response limit differs')
    original.verify_sources(original_manifest())
    # Metadata-only checks precede key access, child lock, claim, and inference.
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') + '/endpoints',
                           timeout=300)
    phase = manifest['phases'][index]
    lower_price.checked_live_context(original_manifest(), phase,
        'development' if stage == 'suffix' else stage, catalog, endpoints)
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, paid.number('0.1'), paid.number('0.5'))
    selected = _rebuild_requests(manifest, index, stage, endpoint, model)
    ledger = partitions.open_partition(admission.MASTER, budget_path,
        manifest['partition_id'], admission.MODEL, admission.PROVIDER, 'low')
    try:
        if ledger.cap != paid.number(manifest['child_cap_usd']):
            raise ValueError('Actual child cap differs from root-reviewed cap')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed:
            raise ValueError('New child budget has unresolved billing or is closed')
        token = paid.load_key(env_file)
        claim = {'schema': SCHEMA + '-stage-claim', 'manifest_sha256': manifest_sha,
            'review_sha256': sha(review),
            'budget_manifest_sha256': sha(budget_path),
            'partition_id': manifest['partition_id'], 'phase_index': index,
            'repeat': phase['repeat'], 'condition': phase['condition'],
            'stage': stage, 'ids': selected_ids(index, stage)}
        original.atomic_json(target['claim'], claim)
        with (target['journal'].open('x') as journal,
              target['raw'].open('x') as raw,
              target['records'].open('x') as records):
            paid.durable(journal, {'event': 'stage_claimed',
                                   'claim_sha256': sha(target['claim'])})
            for input_row, item, payload in selected:
                for source in manifest['source_bindings'].values():
                    read_bound(source)
                read_bound(manifest['controller'])
                rid = item['id']
                if digest(json.dumps(payload, sort_keys=True)) != item['request_sha256']:
                    raise ValueError('Request changed immediately before reservation')
                try:
                    attempt = ledger.reserve(RESERVE, rid)
                except ValueError as exc:
                    if 'cap reached' not in str(exc):
                        raise
                    paid.durable(journal, {'event': 'admission_stopped',
                        'next_unsent_id': rid, 'reason': 'child_cap'})
                    return {'completed': False, 'status': 'child_cap',
                            'next_unsent_id': rid}
                paid.durable(journal, {'event': 'request_started',
                    'attempt_id': attempt, 'id': rid,
                    'request_sha256': item['request_sha256'],
                    'reserved_cost_usd': str(RESERVE)})
                row = {'id': rid, 'repeat': phase['repeat'],
                    'condition': phase['condition'],
                    'phase': 'development' if stage == 'suffix' else stage,
                    'attempt_id': attempt, 'request': payload,
                    'request_sha256': item['request_sha256'],
                    'input_sha256': item['input_sha256'],
                    'policy_sha256': item['instruction_sha256'],
                    'requested_model': admission.MODEL,
                    'provider_endpoint': endpoint, 'model_catalog_entry': model,
                    'reference_labels_read': False,
                    'reserved_cost_usd': str(RESERVE),
                    'budget_partition_id': manifest['partition_id'],
                    'reasoning_effort': 'low',
                    'continue_on_invalid_output': True, 'retry_policy': 'none'}
                actual = None
                before = raw.tell()
                row['client_request_started_utc'] = datetime.now(timezone.utc).isoformat()
                started = time.monotonic()
                try:
                    body = captured_transport.fetch_recorded(payload, token, 300,
                        raw, rid, attempt, item['request_sha256'])
                    if not isinstance(body, dict):
                        raise ValueError('Response JSON root is not an object')
                    row['raw_response'] = body
                    usage = body.get('usage') or {}
                    row['usage'] = usage
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                    status, prediction, _cost, finish = _body_result(body, endpoint)
                    row.update(status=status, prediction=prediction,
                        returned_model=body.get('model'),
                        returned_provider=body.get('provider'), finish_reason=finish)
                except Exception as exc:
                    if raw.tell() == before:
                        _capture_error(raw, rid, attempt, item['request_sha256'], exc, token)
                    row.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        row['http_status'] = exc.code
                finally:
                    row['client_http_duration_seconds'] = time.monotonic() - started
                    row['client_request_finished_utc'] = datetime.now(timezone.utc).isoformat()
                    row['timing_boundary'] = ('Client request through durable raw capture; '
                        'includes local I/O and excludes later billing and record writes.')
                paid.durable(journal, {'event': 'raw_saved', 'attempt_id': attempt,
                    'raw_sha256': sha(target['raw'])})
                billing_ok = ledger.settle(attempt, actual)
                if actual is not None and not billing_ok:
                    row['status'] = 'billing_blocked'
                row.update(observed_cost_usd=str(actual) if actual is not None else None,
                           cost_unknown=actual is None, billing_ok=billing_ok)
                paid.durable(records, row)
                paid.durable(journal, {'event': 'request_finished',
                    'attempt_id': attempt, 'id': rid,
                    'status': row['status'], 'billing_ok': billing_ok})
                if (row['status'] not in ('ok', 'invalid_output') or
                        (stage == 'smoke' and row['status'] != 'ok') or
                        actual is None or not billing_ok):
                    paid.durable(journal, {'event': 'stage_stopped', 'id': rid,
                        'reason': row['status']})
                    return {'completed': False, 'status': row['status'],
                            'stopped_id': rid}
            paid.durable(journal, {'event': 'stage_completed', 'count': len(selected)})
            return {'completed': True, 'count': len(selected)}
    finally:
        ledger.close()


def project_original():
    """Sanitized 49-position historical projection; no completed-pass score."""
    prefix = verify_stopped_prefix()
    seal = verify_old_seal(PREVIOUS / 'terminal-reconciliation-after-dev049.json', prefix)
    source_hashes = {'original_manifest': sha(BASE / 'manifest.json'),
        'first_manifest': FIRST_MANIFEST_SHA,
        **{'first_suffix_' + key: value for key, value in FIRST_EVIDENCE_SHA.items()},
        'first_child_ledger': seal['old_child_ledger']['sha256'],
        'first_terminal_reconciliation':
            seal['old_terminal_reconciliation']['sha256']}
    projection = reconcile_suffix({'method': 'descriptive-second-interruption-continuation',
        'source_bindings': {key: {'sha256': value} for key, value in source_hashes.items()}},
        None)
    if (projection['status'] != 'not_started' or projection['attempted_count'] != 49 or
            projection['never_sent_count'] != 11):
        raise ValueError('Historical-only projection cannot include new suffix evidence')
    projection['completed_pass'] = False
    return projection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify-prefix', 'project-original',
                                          'freeze', 'validate', 'execute-stage',
                                          'reconcile-suffix'))
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--budget', type=Path)
    parser.add_argument('--old-reconciliation', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--phase-index', type=int)
    parser.add_argument('--stage', choices=('suffix', 'smoke', 'development'))
    parser.add_argument('--review', type=Path)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'verify-prefix':
        result = verify_stopped_prefix()
        print(json.dumps({k: result[k] for k in ('failed_id', 'invalid_ids', 'remaining_ids')}))
    elif args.action == 'project-original':
        print(json.dumps(project_original(), indent=2))
    elif args.action == 'freeze':
        if not all((args.manifest, args.budget, args.old_reconciliation)):
            parser.error('freeze needs --manifest, --budget, --old-reconciliation')
        freeze(args.manifest, args.budget, args.old_reconciliation)
        print(json.dumps({'manifest_sha256': sha(args.manifest)}))
    elif args.action == 'validate':
        if not args.manifest or not args.sha256:
            parser.error('validate needs --manifest and --sha256')
        validate_manifest(args.manifest, args.sha256)
        print(json.dumps({'validated': True}))
    elif args.action == 'reconcile-suffix':
        if not args.manifest or not args.sha256:
            parser.error('reconcile-suffix needs --manifest and --sha256')
        manifest = validate_manifest(args.manifest, args.sha256)
        print(json.dumps(reconcile_suffix(manifest, args.sha256), indent=2))
    else:
        if not all((args.manifest, args.sha256, args.budget, args.review)) or \
                args.phase_index is None or args.stage is None:
            parser.error('execute-stage needs manifest, sha256, budget, review, index and stage')
        print(json.dumps(execute(args.manifest, args.sha256, args.budget,
            args.phase_index, args.stage, args.review, args.env_file)))


if __name__ == '__main__':
    main()
