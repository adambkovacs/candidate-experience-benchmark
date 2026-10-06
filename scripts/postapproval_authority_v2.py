#!/usr/bin/env python3
"""Versioned, source-bound accounting for the existing $10 authority file.

This module has no production entry point. A controller must explicitly call
hold_authority or release_authority after its own review and admission checks.
The same inode is locked and appended; historical bytes are never replaced.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import json
import os
from pathlib import Path


CAP = Decimal('10.00')
HEADER = {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
          'cap_usd': '10.00',
          'decision_key': 'candidate-experience-benchmark/user-ten-dollar-tests-20261002',
          'approval_sha256': '57d5ff76acd14f85d5e600c6527c310fc08f4eb66d45b1c25b9d778d770aaf8f'}
# The independently audited original header and all 47 historical holds.
ORIGINAL_HEAD = '4516e72a3fafd52da879655bb4923ff6ef8852532002cf7baefd2c55ed9c4423'
ORIGINAL_EVENTS = 48
RELEASE_KEYS = {'event', 'version', 'id', 'hold_id', 'usd', 'hold_source_sha256',
                'prior_head_sha256', 'stage_path', 'receipt_path', 'manifest_path',
                'budget_manifest_path', 'completion_sha256', 'attempts_sha256',
                'receipt_sha256', 'manifest_sha256', 'budget_manifest_sha256',
                'reconciliation_sha256', 'child_ledger_path', 'child_sha256',
                'master_ledger_path', 'master_partition_event_sha256',
                'master_reconciliation_event_sha256'}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _lines(raw: bytes):
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('Authority file lacks a complete terminal line')
    pieces = raw.splitlines(keepends=True)
    if any(not piece.strip() for piece in pieces):
        raise ValueError('Blank authority event')
    return [json.loads(piece, object_pairs_hook=_object) for piece in pieces], pieces


def _money(value, *, positive=False):
    if not isinstance(value, str):
        raise ValueError('Amount must be a decimal string')
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('Invalid authority amount') from error
    if not amount.is_finite() or amount < 0 or (positive and amount == 0):
        raise ValueError('Invalid authority amount')
    return amount


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _path(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError('Evidence path must be absolute')
    path = Path(value)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Evidence file missing or symlinked')
    return path


@dataclass(frozen=True)
class Snapshot:
    head_sha256: str
    gross_usd: Decimal
    released_usd: Decimal
    accounted_usd: Decimal
    available_usd: Decimal
    hold_count: int
    release_count: int


def _evidence(event, hold):
    """Recheck the sealed OpenRouter full-pass chain named by a release."""
    if set(event) != RELEASE_KEYS or event['event'] != 'release' or event['version'] != 2:
        raise ValueError('Unknown authority release structure')
    if any(not _digest(event[key]) for key in RELEASE_KEYS if key.endswith('_sha256')):
        raise ValueError('Invalid release digest')
    if not isinstance(event['id'], str) or not event['id'] or not isinstance(event['hold_id'], str):
        raise ValueError('Invalid release identity')
    if event['hold_id'] != hold['id'] or event['hold_source_sha256'] != hold['source_sha256']:
        raise ValueError('Release names the wrong original hold')
    amount = _money(event['usd'], positive=True)
    stage = Path(event['stage_path'])
    if not stage.is_absolute() or stage.is_symlink() or not stage.is_dir():
        raise ValueError('Stage is missing or redirected')
    receipt_path = _path(event['receipt_path'])
    manifest_path = _path(event['manifest_path'])
    budget_path = _path(event['budget_manifest_path'])
    child_path = _path(event['child_ledger_path'])
    master_path = _path(event['master_ledger_path'])
    if receipt_path.parent != stage.parent or budget_path.parent != stage.parent:
        raise ValueError('Stage review and budget must be siblings of terminal stage')
    completion_path = _path(str(stage / 'completion.json'))
    attempts_path = _path(str(stage / 'attempts.jsonl'))
    reconciliation_path = _path(str(stage / 'budget-reconciliation.json'))
    stage_receipt_path = _path(str(stage / 'review-receipt.json'))
    pairs = ((receipt_path, 'receipt_sha256'), (manifest_path, 'manifest_sha256'),
             (budget_path, 'budget_manifest_sha256'),
             (completion_path, 'completion_sha256'), (attempts_path, 'attempts_sha256'),
             (reconciliation_path, 'reconciliation_sha256'), (child_path, 'child_sha256'))
    if any(file_sha(path) != event[key] for path, key in pairs):
        raise ValueError('Released stage evidence changed')
    if file_sha(stage_receipt_path) != event['receipt_sha256']:
        raise ValueError('Stage review receipt changed')
    receipt = json.loads(receipt_path.read_bytes(), object_pairs_hook=_object)
    manifest = json.loads(manifest_path.read_bytes(), object_pairs_hook=_object)
    budget = json.loads(budget_path.read_bytes(), object_pairs_hook=_object)
    completion = json.loads(completion_path.read_bytes(), object_pairs_hook=_object)
    reconciliation = json.loads(reconciliation_path.read_bytes(), object_pairs_hook=_object)
    pid = hold['id']
    if (not isinstance(receipt.get('schema'), str) or
            not receipt['schema'].endswith('-root-review') or
            receipt.get('approved') is not True or receipt.get('reviewer') != 'root' or
            receipt.get('global_hold_id') != pid or
            receipt.get('global_hold_source_sha256') != hold['source_sha256'] or
            receipt.get('global_authority_approval_sha256') != HEADER['approval_sha256'] or
            receipt.get('global_authority_cap_usd') != HEADER['cap_usd'] or
            _money(receipt.get('global_hold_usd')) != _money(hold['usd']) or
            receipt.get('partition_id') != pid or
            receipt.get('manifest_sha256') != event['manifest_sha256'] or
            receipt.get('budget_manifest_sha256') != event['budget_manifest_sha256'] or
            receipt.get('stage') != stage.name or
            receipt.get('configuration_id') != stage.parent.name):
        raise ValueError('Review receipt does not bind this hold and stage')
    declared_cap = manifest.get('whole_pass_bound_usd',
                                manifest.get('whole_suffix_full_context_bound_usd'))
    declared_partitions = manifest.get('passes',
                                       [{'stage': manifest.get('stage'),
                                         'partition_id': manifest.get('partition_id')}])
    ids = receipt.get('ids')
    if (manifest.get('configuration_id') != stage.parent.name or
            _money(declared_cap) != _money(hold['usd']) or
            not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or
            manifest.get('ids') != ids or
            sum(p.get('stage') == stage.name and p.get('partition_id') == pid
                for p in declared_partitions) != 1):
        raise ValueError('Full-pass manifest does not bind partition')
    if (not isinstance(completion.get('schema'), str) or
            not completion['schema'].endswith('-completion') or
            completion.get('configuration_id') != stage.parent.name or
            completion.get('stage') != stage.name or
            completion.get('valid_count') != len(ids) or completion.get('invalid_count') != 0 or
            completion.get('invalid_ids') != [] or completion.get('ids') != ids or
            completion.get('attempts_sha256') != event['attempts_sha256'] or
            completion.get('receipt_sha256') != event['receipt_sha256'] or
            completion.get('manifest_sha256') != event['manifest_sha256'] or
            completion.get('budget_manifest_sha256') != event['budget_manifest_sha256'] or
            completion.get('reference_labels_read') is not False):
        raise ValueError('Full-pass terminal completion differs')
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(master_path) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Child budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != pid or entry.get('child_ledger') != str(child_path) or
            _money(entry.get('cap_usd')) != _money(hold['usd']) or
            receipt.get('child_cap_usd') != entry['cap_usd'] or
            manifest.get('model') != entry.get('model') or
            manifest.get('provider_tag') != entry.get('provider') or
            entry.get('reasoning') != 'none'):
        raise ValueError('Child budget identity differs')
    source = sha(canonical({'manifest_sha256': event['manifest_sha256'],
                            'budget_manifest_sha256': event['budget_manifest_sha256'],
                            'partition_id': pid, 'child_ledger': str(child_path),
                            'cap_usd': entry['cap_usd']}))
    if source != hold['source_sha256']:
        raise ValueError('Original hold source cannot be reproduced')
    # Match the master -> child lock order used by partition reconciliation.
    # A concurrent worker or reconciler makes admission fail closed.
    with master_path.open('rb') as master_handle, child_path.open('rb') as child_handle:
        fcntl.flock(master_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(child_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        master_raw = master_handle.read()
        child_raw = child_handle.read()
        if sha(child_raw) != event['child_sha256']:
            raise ValueError('Child changed during locked evidence read')
    child_events, _ = _lines(child_raw)
    if (child_events[0] != {'event': 'budget', 'cap_usd': entry['cap_usd']} or
            child_events[-1].get('event') != 'partition_closed' or
            sum(e.get('event') == 'partition_closed' for e in child_events) != 1):
        raise ValueError('Child is not sealed')
    pending = {}
    reserved = {}
    settled = {}
    known = unknown = Decimal(0)
    for item in child_events[1:-1]:
        kind = item.get('event')
        if kind == 'reserve':
            aid = item.get('attempt_id')
            if aid in pending or not isinstance(aid, str):
                raise ValueError('Duplicate child reservation')
            pending[aid] = _money(item.get('usd'), positive=True)
            reserved[aid] = (item.get('record_id'), pending[aid])
        elif kind == 'settle':
            aid = item.get('attempt_id')
            if aid not in pending:
                raise ValueError('Unmatched child settlement')
            value = _money(item.get('usd'))
            if value > pending.pop(aid):
                raise ValueError('Child settlement exceeds reserve')
            settled[aid] = value
            known += value
        elif kind == 'unknown_cost_accounted_as_upper_bound':
            aid = item.get('attempt_id')
            if aid not in pending or _money(item.get('usd')) != pending.pop(aid):
                raise ValueError('Unknown child charge bound changed')
            unknown += _money(item['usd'])
        else:
            raise ValueError('Unknown child event')
    if pending:
        raise ValueError('Child has unresolved reservations')
    attempts, _ = _lines(attempts_path.read_bytes())
    if len(attempts) != 4*len(ids) or len(reserved) != len(ids) or len(settled) != len(ids):
        raise ValueError('Terminal attempts do not match closed child')
    observed = set()
    for i, rid in enumerate(ids):
        group = attempts[4*i:4*i+4]
        aid = group[0].get('attempt_id')
        if ([x.get('stage') for x in group] != ['reserved', 'started', 'response', 'parsed'] or
                any(x.get('id') != rid or x.get('attempt_id') != aid for x in group) or
                aid in observed or aid not in reserved or aid not in settled or
                reserved[aid] != (pid + ':' + rid, _money(group[0].get('reserved_cost_usd'))) or
                group[2].get('http_status') != 200 or
                group[2].get('cost_unknown') is not False or
                _money(group[2].get('actual_cost_usd')) != settled[aid] or
                group[3].get('valid') is not True):
            raise ValueError('Terminal attempt and child settlement differ')
        observed.add(aid)
    if observed != set(reserved):
        raise ValueError('Child contains attempts absent from terminal stage')
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != pid or
            reconciliation.get('child_ledger') != str(child_path) or
            reconciliation.get('child_sha256') != event['child_sha256'] or
            _money(reconciliation.get('known_actual_usd')) != known or
            _money(reconciliation.get('unknown_upper_bound_usd')) != unknown or
            _money(reconciliation.get('unused_allocation_released_usd')) != amount or
            known + unknown + amount != _money(hold['usd']) or
            _money(completion.get('known_actual_cost_usd')) != known):
        raise ValueError('Closed child reconciliation differs from release')
    master_events, _ = _lines(master_raw)
    allocations = [(i, e) for i, e in enumerate(master_events)
                   if e.get('event') == 'budget_partition' and e.get('partition_id') == pid]
    reconciled = [(i, e) for i, e in enumerate(master_events)
                  if e.get('event') == 'partition_reconciled' and e.get('partition_id') == pid]
    if len(allocations) != 1 or len(reconciled) != 1 or allocations[0][0] >= reconciled[0][0]:
        raise ValueError('Master partition is absent or duplicated')
    allocation, closed = allocations[0][1], reconciled[0][1]
    if (sha(canonical(allocation)) != event['master_partition_event_sha256'] or
            sha(canonical(closed)) != event['master_reconciliation_event_sha256'] or
            closed != reconciliation or allocation.get('manifest_path') != str(budget_path) or
            allocation.get('manifest_sha256') != event['budget_manifest_sha256'] or
            allocation.get('child_ledger') != str(child_path) or
            _money(allocation.get('allocated_usd')) != _money(hold['usd'])):
        raise ValueError('Master reconciliation does not bind child')
    return amount


def _scan(raw, *, baseline_head, baseline_events, verify_sources=True):
    events, pieces = _lines(raw)
    if events[0] != HEADER or len(events) < baseline_events:
        raise ValueError('Shared authority provenance differs')
    if sha(b''.join(pieces[:baseline_events])) != baseline_head:
        raise ValueError('Original authority history changed')
    holds = {}
    releases = {}
    gross = released = Decimal(0)
    prefix = b''
    for i, (event, piece) in enumerate(zip(events, pieces)):
        if i == 0:
            prefix += piece
            continue
        if event.get('event') == 'hold':
            if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                    not isinstance(event['id'], str) or not event['id'] or
                    event['id'] in holds or not _digest(event['source_sha256'])):
                raise ValueError('Invalid or duplicate authority hold')
            amount = _money(event['usd'], positive=True)
            holds[event['id']] = event
            gross += amount
        elif event.get('event') == 'release':
            if (event.get('hold_id') not in holds or event.get('id') in releases or
                    event.get('prior_head_sha256') != sha(prefix) or
                    event.get('hold_id') in (r['hold_id'] for r in releases.values())):
                raise ValueError('Duplicate, stale or orphan release')
            amount = _evidence(event, holds[event['hold_id']]) if verify_sources else _money(event['usd'], positive=True)
            if amount > _money(holds[event['hold_id']]['usd']):
                raise ValueError('Release exceeds hold')
            releases[event['id']] = event
            released += amount
        else:
            raise ValueError('Unknown authority event')
        if gross - released > CAP or gross - released < 0:
            raise ValueError('Authority cap or balance violated')
        prefix += piece
    return Snapshot(sha(raw), gross, released, gross - released,
                    CAP - gross + released, len(holds), len(releases)), holds, releases


@contextmanager
def _locked(path):
    # r+b never creates or truncates; flock is on the authority inode itself.
    with Path(path).open('r+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield handle


def _append(handle, event):
    raw = (json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
    handle.seek(0, os.SEEK_END)
    if handle.write(raw) != len(raw):
        raise OSError('Incomplete authority append')
    handle.flush()
    os.fsync(handle.fileno())
    return raw


def read_authority(path, *, baseline_head=ORIGINAL_HEAD, baseline_events=ORIGINAL_EVENTS):
    with _locked(path) as handle:
        return _scan(handle.read(), baseline_head=baseline_head,
                     baseline_events=baseline_events)[0]


def verify_joint_headroom(authority_path, master_path, requested_usd,
                          expected_authority_head, expected_master_head, *,
                          baseline_head=ORIGINAL_HEAD, baseline_events=ORIGINAL_EVENTS):
    """Read-only, locked preflight for a later separately reviewed allocation.

    This snapshot is not an allocation and grants no right to dispatch. The
    controller must recheck both heads while committing its own admission.
    """
    requested = _money(str(requested_usd), positive=True)
    with _locked(authority_path) as handle:
        authority_state, _, _ = _scan(handle.read(), baseline_head=baseline_head,
                                      baseline_events=baseline_events)
        if authority_state.head_sha256 != expected_authority_head or requested > authority_state.available_usd:
            raise ValueError('Authority head stale or capacity exhausted')
        with Path(master_path).open('rb') as master_handle:
            fcntl.flock(master_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw = master_handle.read()
            if sha(raw) != expected_master_head:
                raise ValueError('Master head changed')
            events, _ = _lines(raw)
            if events[0].get('event') != 'budget':
                raise ValueError('Master provenance differs')
            from openrouter_budget_v3 import BudgetLedger
            budget = object.__new__(BudgetLedger)
            budget.events = events
            budget.cap_limit = Decimal('12.38')
            _, pending, blocked = budget.state()
            accounted = budget.accounted()
            if (budget.cap != Decimal('12.38') or pending or blocked or budget.closed or
                    any(part['active'] for part in budget.partitions.values()) or
                    accounted + requested > budget.cap):
                raise ValueError('Master has no clean capacity for requested partition')
            return {'authority_head_sha256': authority_state.head_sha256,
                    'master_head_sha256': sha(raw), 'requested_usd': str(requested),
                    'authority_available_usd': str(authority_state.available_usd),
                    'master_available_usd': str(budget.cap - accounted)}


def hold_authority(path, hold_id, amount, source, expected_head, *, stage_path,
                   baseline_head=ORIGINAL_HEAD, baseline_events=ORIGINAL_EVENTS):
    """Same signature as the old native hold, with v2 net accounting."""
    amount = _money(str(amount), positive=True)
    if not isinstance(hold_id, str) or not hold_id or not _digest(source):
        raise ValueError('Invalid hold identity')
    with _locked(path) as handle:
        raw = handle.read()
        state, holds, _ = _scan(raw, baseline_head=baseline_head,
                                baseline_events=baseline_events)
        if state.head_sha256 != expected_head or hold_id in holds or Path(stage_path).exists():
            raise ValueError('Stale head, duplicate hold or claimed stage')
        if amount > state.available_usd:
            raise ValueError('Authority cap exhausted')
        event = {'event': 'hold', 'id': hold_id, 'usd': str(amount), 'source_sha256': source}
        _append(handle, event)
        return event


def release_authority(path, release_id, hold_id, amount, expected_head, *, stage_path,
                      receipt_path, manifest_path, budget_manifest_path,
                      child_ledger_path, master_ledger_path,
                      baseline_head=ORIGINAL_HEAD, baseline_events=ORIGINAL_EVENTS):
    """Append one full-unused release; return a reconstructible review receipt.

    This function is intentionally separate from hold admission. The caller
    must separately authorize and verify any new paid work.
    """
    with _locked(path) as handle:
        raw = handle.read()
        state, holds, releases = _scan(raw, baseline_head=baseline_head,
                                       baseline_events=baseline_events)
        if state.head_sha256 != expected_head or hold_id not in holds or release_id in releases:
            raise ValueError('Stale head, missing hold or duplicate release')
        if any(r['hold_id'] == hold_id for r in releases.values()):
            raise ValueError('Hold already released')
        stage = Path(stage_path).resolve()
        receipt = Path(receipt_path).resolve()
        manifest = Path(manifest_path).resolve()
        budget = Path(budget_manifest_path).resolve()
        child = Path(child_ledger_path).resolve()
        master = Path(master_ledger_path).resolve()
        master_events, _ = _lines(master.read_bytes())
        allocation = [e for e in master_events if e.get('event') == 'budget_partition' and e.get('partition_id') == hold_id]
        reconciled = [e for e in master_events if e.get('event') == 'partition_reconciled' and e.get('partition_id') == hold_id]
        if len(allocation) != 1 or len(reconciled) != 1:
            raise ValueError('Master partition is not uniquely reconciled')
        event = {'event': 'release', 'version': 2, 'id': release_id, 'hold_id': hold_id,
                 'usd': str(_money(str(amount), positive=True)),
                 'hold_source_sha256': holds[hold_id]['source_sha256'],
                 'prior_head_sha256': expected_head, 'stage_path': str(stage),
                 'receipt_path': str(receipt), 'manifest_path': str(manifest),
                 'budget_manifest_path': str(budget),
                 'completion_sha256': file_sha(stage / 'completion.json'),
                 'attempts_sha256': file_sha(stage / 'attempts.jsonl'),
                 'receipt_sha256': file_sha(receipt), 'manifest_sha256': file_sha(manifest),
                 'budget_manifest_sha256': file_sha(budget),
                 'reconciliation_sha256': file_sha(stage / 'budget-reconciliation.json'),
                 'child_ledger_path': str(child), 'child_sha256': file_sha(child),
                 'master_ledger_path': str(master),
                 'master_partition_event_sha256': sha(canonical(allocation[0])),
                 'master_reconciliation_event_sha256': sha(canonical(reconciled[0]))}
        _evidence(event, holds[hold_id])
        # A checked second read catches normal unlocked edits to stage sources.
        _evidence(event, holds[hold_id])
        new_raw = raw + _append(handle, event)
        return {'schema': 'postapproval-authority-v2-release-receipt',
                'release_event': event, 'old_head_sha256': expected_head,
                'new_head_sha256': sha(new_raw), 'accounted_usd': str(state.accounted_usd - _money(event['usd'])),
                'available_usd': str(state.available_usd + _money(event['usd']))}
