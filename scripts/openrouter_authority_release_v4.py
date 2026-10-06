#!/usr/bin/env python3
"""Versioned OpenRouter-only authority releases after v3 users quiesce.

This module does not run inference or allocate a budget partition. Its release
writer requires an exact independent root receipt and a sealed, reconciled
child. Existing v3 readers cannot read v4 release events; do not append while
any v3 runner may still need the authority ledger.
"""
import argparse
from dataclasses import dataclass
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path

import openrouter_budget_amendment_v3 as amendment
import postapproval_authority_v2 as old
import postapproval_authority_v3 as v3

AUTHORITY = amendment.AUTHORITY
MASTER = amendment.MASTER
SCHEMA = 'openrouter-authority-release-v4'
RELEASE_KEYS = {'event', 'version', 'id', 'hold_id', 'usd', 'funding_pool',
                'hold_source_sha256', 'prior_head_sha256', 'budget_manifest_sha256',
                'master_partition_event_sha256', 'master_reconciliation_event_sha256',
                'child_sha256', 'known_actual_usd', 'unknown_upper_bound_usd'}


@dataclass(frozen=True)
class Snapshot:
    head_sha256: str
    shared_accounted_usd: Decimal
    openrouter_accounted_usd: Decimal
    shared_available_usd: Decimal
    openrouter_available_usd: Decimal
    amendment_complete: bool


def _master_child(hold):
    """Read an exact partition and its sealed child under master -> child locks."""
    if (hold.get('funding_pool') != 'openrouter_additional' or
            hold.get('id') != hold.get('partition_id') or
            hold.get('master_path') != str(MASTER)):
        raise ValueError('Release requires an exact earmarked OpenRouter hold')
    budget_path = Path(hold['budget_manifest_path'])
    if old.file_sha(budget_path) != hold['budget_manifest_sha256']:
        raise ValueError('Held budget manifest changed')
    budget = json.loads(budget_path.read_bytes(), object_pairs_hook=old._object)
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(MASTER) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Held budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != hold['id'] or
            old._money(entry.get('cap_usd')) != old._money(hold['usd']) or
            not isinstance(entry.get('child_ledger'), str)):
        raise ValueError('Held child identity or cap differs')
    child_path = Path(entry['child_ledger'])
    if (not child_path.is_absolute() or child_path.is_symlink() or
            child_path.resolve() != child_path or
            not child_path.is_file()):
        raise ValueError('Held child path is missing or redirected')
    with MASTER.open('rb') as master, child_path.open('rb') as child:
        fcntl.flock(master, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(child, fcntl.LOCK_EX | fcntl.LOCK_NB)
        master_events, _ = old._lines(master.read())
        child_raw = child.read()
    allocation = [e for e in master_events if e.get('event') == 'budget_partition'
                  and e.get('partition_id') == hold['id']]
    reconciled = [e for e in master_events if e.get('event') == 'partition_reconciled'
                  and e.get('partition_id') == hold['id']]
    if len(allocation) != 1 or len(reconciled) != 1:
        raise ValueError('Held partition is not uniquely reconciled')
    allocation, closed = allocation[0], reconciled[0]
    if (allocation.get('manifest_path') != str(budget_path) or
            allocation.get('manifest_sha256') != hold['budget_manifest_sha256'] or
            allocation.get('child_ledger') != str(child_path) or
            allocation.get('allocated_usd') != hold['usd'] or
            any(entry.get(key) != allocation.get(key)
                for key in ('child_ledger', 'model', 'provider', 'reasoning')) or
            closed.get('child_ledger') != str(child_path) or
            closed.get('child_sha256') != old.sha(child_raw)):
        raise ValueError('Master partition or reconciliation differs from held child')
    events, _ = old._lines(child_raw)
    if (events[0] != {'event': 'budget', 'cap_usd': hold['usd']} or
            events[-1].get('event') != 'partition_closed' or
            sum(e.get('event') == 'partition_closed' for e in events) != 1):
        raise ValueError('Held child is not sealed')
    pending = {}
    known = unknown = Decimal(0)
    for item in events[1:-1]:
        kind, aid = item.get('event'), item.get('attempt_id')
        if kind == 'reserve':
            if not isinstance(aid, str) or not aid or aid in pending:
                raise ValueError('Duplicate or invalid child reservation')
            pending[aid] = old._money(item.get('usd'), positive=True)
        elif kind in ('settle', 'unknown_cost_accounted_as_upper_bound'):
            if aid not in pending:
                raise ValueError('Unmatched child cost event')
            amount = old._money(item.get('usd'))
            reserve = pending.pop(aid)
            if amount > reserve or (kind == 'unknown_cost_accounted_as_upper_bound'
                                    and amount != reserve):
                raise ValueError('Child cost exceeds or weakens reservation')
            if kind == 'settle':
                known += amount
            else:
                unknown += amount
        else:
            raise ValueError('Unknown child budget event')
    if pending:
        raise ValueError('Held child has unresolved reservations')
    unused = old._money(closed.get('unused_allocation_released_usd'), positive=True)
    if (old._money(closed.get('known_actual_usd')) != known or
            old._money(closed.get('unknown_upper_bound_usd')) != unknown or
            known + unknown + unused != old._money(hold['usd'])):
        raise ValueError('Held child and master cost accounting differ')
    return {'hold_id': hold['id'], 'hold_usd': hold['usd'],
            'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(unknown),
            'unused_allocation_usd': str(unused),
            'budget_manifest_sha256': hold['budget_manifest_sha256'],
            'master_partition_event_sha256': old.sha(old.canonical(allocation)),
            'master_reconciliation_event_sha256': old.sha(old.canonical(closed)),
            'child_sha256': old.sha(child_raw)}


def _release_evidence(event, hold):
    if (set(event) != RELEASE_KEYS or event.get('event') != 'release' or
            event.get('version') != 4 or event.get('funding_pool') != 'openrouter_additional' or
            event.get('hold_id') != hold.get('id') or
            event.get('hold_source_sha256') != hold.get('source_sha256') or
            not isinstance(event.get('id'), str) or not event['id']):
        raise ValueError('Invalid v4 release identity or source')
    evidence = _master_child(hold)
    checks = {'usd': 'unused_allocation_usd', 'budget_manifest_sha256': 'budget_manifest_sha256',
              'master_partition_event_sha256': 'master_partition_event_sha256',
              'master_reconciliation_event_sha256': 'master_reconciliation_event_sha256',
              'child_sha256': 'child_sha256', 'known_actual_usd': 'known_actual_usd',
              'unknown_upper_bound_usd': 'unknown_upper_bound_usd'}
    if any(event[key] != evidence[value] for key, value in checks.items()):
        raise ValueError('V4 release differs from sealed child or master reconciliation')
    return old._money(event['usd'], positive=True)


def _scan(raw):
    events, pieces = old._lines(raw)
    amendments = [i for i, e in enumerate(events) if e.get('event') == 'authority_amendment']
    if len(amendments) != 1:
        raise ValueError('Exact amended authority required')
    split = amendments[0]
    original, holds, _ = old._scan(b''.join(pieces[:split]),
                                  baseline_head=old.ORIGINAL_HEAD,
                                  baseline_events=old.ORIGINAL_EVENTS)
    reviewed = amendment.validate_event(events[split], 'authority')
    if (reviewed['authority']['sha256'] != old.sha(b''.join(pieces[:split])) or
            not amendment.counterpart_committed(reviewed, events[split]['review_path'], 'master')):
        raise ValueError('Joint amendment provenance differs')
    shared, earmarked = original.accounted_usd, Decimal(0)
    released = set()
    release_ids = set()
    prefix = b''.join(pieces[:split + 1])
    for event, piece in zip(events[split + 1:], pieces[split + 1:]):
        if event.get('event') == 'hold':
            pool = event.get('funding_pool')
            keys = {'event', 'version', 'id', 'usd', 'source_sha256', 'funding_pool'}
            if pool == 'openrouter_additional':
                keys |= {'budget_manifest_path', 'budget_manifest_sha256',
                         'partition_id', 'master_path'}
            if (set(event) != keys or event.get('version') != 3 or
                    not isinstance(event.get('id'), str) or not event['id'] or
                    event['id'] in holds or event['id'] in release_ids or
                    not old._digest(event.get('source_sha256'))):
                raise ValueError('Invalid or duplicate post-amendment hold')
            amount = old._money(event['usd'], positive=True)
            if pool == 'shared':
                shared += amount
            elif pool == 'openrouter_additional':
                if (event['id'] != event['partition_id'] or
                        event['master_path'] != reviewed['master']['path'] or
                        amendment.sha(event['budget_manifest_path']) != event['budget_manifest_sha256']):
                    raise ValueError('Earmarked hold provenance differs')
                budget = json.loads(Path(event['budget_manifest_path']).read_text())
                entries = [x for x in budget.get('partitions', [])
                           if x.get('id') == event['partition_id']]
                if (budget.get('master_ledger') != event['master_path'] or
                        len(entries) != 1 or
                        old._money(entries[0].get('cap_usd')) != amount):
                    raise ValueError('Earmarked hold budget differs')
                earmarked += amount
            else:
                raise ValueError('Unknown funding pool')
            holds[event['id']] = event
        elif event.get('event') == 'release':
            hid = event.get('hold_id')
            if (hid not in holds or hid in released or event.get('id') in release_ids or
                    event.get('id') in holds or
                    event.get('prior_head_sha256') != old.sha(prefix)):
                raise ValueError('Duplicate, stale or orphan v4 release')
            earmarked -= _release_evidence(event, holds[hid])
            released.add(hid)
            release_ids.add(event['id'])
        else:
            raise ValueError('Unsupported amended authority event')
        if not 0 <= shared <= v3.SHARED_CAP or not 0 <= earmarked <= v3.OPENROUTER_ADDITIONAL_CAP:
            raise ValueError('Authority pool cap or balance violated')
        prefix += piece
    return Snapshot(old.sha(raw), shared, earmarked,
                    v3.SHARED_CAP - shared, v3.OPENROUTER_ADDITIONAL_CAP - earmarked,
                    True), holds, released


def read_authority(path=AUTHORITY):
    with old._locked(path) as handle:
        return _scan(handle.read())[0]


def release_plan(hold_id, release_id, *, path=AUTHORITY):
    with old._locked(path) as handle:
        raw = handle.read()
        state, holds, released = _scan(raw)
        if hold_id not in holds or hold_id in released or not release_id:
            raise ValueError('Hold missing, already released, or release ID absent')
        hold = holds[hold_id]
        evidence = _master_child(hold)
        event = {'event': 'release', 'version': 4, 'id': release_id,
                 'hold_id': hold_id, 'usd': evidence['unused_allocation_usd'],
                 'funding_pool': 'openrouter_additional',
                 'hold_source_sha256': hold['source_sha256'],
                 'prior_head_sha256': state.head_sha256,
                 **{key: evidence[key] for key in (
                     'budget_manifest_sha256', 'master_partition_event_sha256',
                     'master_reconciliation_event_sha256', 'child_sha256',
                     'known_actual_usd', 'unknown_upper_bound_usd')}}
        _release_evidence(event, hold)
        _scan(raw + old.canonical(event) + b'\n')
        return {'schema': SCHEMA + '-plan', 'status': 'unapproved_no_ledger_write',
                'authority_head_sha256': state.head_sha256,
                'master_head_sha256': old.file_sha(MASTER),
                'controller_sha256': old.file_sha(Path(__file__)),
                'event': event}


def append_release(plan, review, *, path=AUTHORITY):
    """One durable event per reviewed call; never auto-approves a candidate."""
    if (review != {'schema': SCHEMA + '-root-review', 'approved': True,
                   'independent_review': True, 'reviewer': 'root',
                   'plan_sha256': old.sha(old.canonical(plan)),
                   'v3_consumers_quiesced': True}):
        raise ValueError('Exact independent v4 transition receipt required')
    if plan.get('controller_sha256') != old.file_sha(Path(__file__)):
        raise ValueError('Release controller changed after review')
    with old._locked(path) as handle:
        raw = handle.read()
        state, holds, released = _scan(raw)
        event = plan['event']
        if (state.head_sha256 != plan['authority_head_sha256'] or
                old.file_sha(MASTER) != plan['master_head_sha256'] or
                event['hold_id'] in released):
            raise ValueError('Authority or master head changed after review')
        # Only the first release transitions away from v3 readers. Later v4
        # holds may be active while an unrelated sealed child is released.
        if not released:
            for hold in holds.values():
                if hold.get('funding_pool') == 'openrouter_additional':
                    _master_child(hold)
        _release_evidence(event, holds[event['hold_id']])
        new_line = old.canonical(event) + b'\n'
        _scan(raw + new_line)
        handle.seek(0, os.SEEK_END)
        if handle.write(new_line) != len(new_line):
            raise OSError('Incomplete v4 release append')
        handle.flush(); os.fsync(handle.fileno())
        return old.sha(raw + new_line)


def review_template(plan):
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'reviewer': None,
            'plan_sha256': old.sha(old.canonical(plan)),
            'v3_consumers_quiesced': False}


def hold_authority(path, hold_id, amount, source, expected_head, *, stage_path,
                   funding_pool, budget_path, partition_id):
    """Future reviewed adapters use this after the v4 transition, never v3."""
    amount = old._money(str(amount), positive=True)
    if (funding_pool != 'openrouter_additional' or hold_id != partition_id or
            not isinstance(hold_id, str) or not hold_id or not old._digest(source)):
        raise ValueError('Only exact earmarked v4 holds are supported')
    with old._locked(path) as handle:
        raw = handle.read()
        state, holds, released = _scan(raw)
        if (not released or state.head_sha256 != expected_head or
                hold_id in holds or Path(stage_path).exists() or
                amount > state.openrouter_available_usd):
            raise ValueError('Transition, head, identity, stage or capacity differs')
        event = {'event': 'hold', 'version': 3, 'id': hold_id,
                 'usd': str(amount), 'source_sha256': source,
                 'funding_pool': funding_pool,
                 **v3._binding(budget_path, partition_id, amount, MASTER, fresh=True)}
        line = old.canonical(event) + b'\n'
        _scan(raw + line)
        handle.seek(0, os.SEEK_END)
        if handle.write(line) != len(line):
            raise OSError('Incomplete post-transition hold append')
        handle.flush(); os.fsync(handle.fileno())
        return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'verify', 'review-template', 'append'))
    parser.add_argument('--hold-id')
    parser.add_argument('--release-id')
    parser.add_argument('--plan-file', type=Path)
    parser.add_argument('--review-file', type=Path)
    args = parser.parse_args()
    if args.action == 'verify':
        print(read_authority().head_sha256)
    elif args.action == 'plan':
        if not args.hold_id or not args.release_id:
            parser.error('plan requires --hold-id and --release-id')
        print(json.dumps(release_plan(args.hold_id, args.release_id), indent=2))
    else:
        if not args.plan_file:
            parser.error('review-template/append requires --plan-file')
        plan = json.loads(args.plan_file.read_text(), object_pairs_hook=old._object)
        if args.action == 'review-template':
            print(json.dumps(review_template(plan), indent=2))
        else:
            if not args.review_file:
                parser.error('append requires --review-file')
            review = json.loads(args.review_file.read_text(), object_pairs_hook=old._object)
            print(append_release(plan, review))


if __name__ == '__main__':
    main()
