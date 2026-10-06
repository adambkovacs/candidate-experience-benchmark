"""Original $10 shared pool plus a separately reviewed OpenRouter-only $10.

New holds never release funds automatically. Original v2 releases remain
source-verified; unknowns and every historical byte stay accounted for.
"""
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import postapproval_authority_v2 as old
import openrouter_budget_amendment_v3 as amendment

SHARED_CAP = Decimal('10.00')
OPENROUTER_ADDITIONAL_CAP = Decimal('10.00')


@dataclass(frozen=True)
class Snapshot:
    head_sha256: str
    shared_accounted_usd: Decimal
    openrouter_accounted_usd: Decimal
    shared_available_usd: Decimal
    openrouter_available_usd: Decimal
    amendment_complete: bool

    @property
    def accounted_usd(self):
        return self.shared_accounted_usd + self.openrouter_accounted_usd


def _binding(budget_path, partition_id, amount, master_path, *, fresh=False):
    from openrouter_budget_v4 import BudgetLedger
    import paid_budget_partitions_v4 as partitions
    budget_path = Path(budget_path).resolve()
    manifest = json.loads(budget_path.read_text())
    if Path(manifest.get('master_ledger', '')).resolve() != Path(master_path).resolve():
        raise ValueError('Additional pool requires the exact OpenRouter master')
    master = BudgetLedger(master_path)
    try:
        part = master.partitions.get(partition_id)
        entries = [e for e in manifest.get('partitions', []) if e.get('id') == partition_id]
        if (not part or len(entries) != 1 or manifest.get('version') != 'paid-partitions-v1' or
                part['manifest_path'] != str(budget_path) or part['manifest_sha256'] != partitions.sha(budget_path) or
                Decimal(part['allocated_usd']) != amount or entries[0]['cap_usd'] != part['allocated_usd'] or
                any(entries[0].get(k) != part[k] for k in ('child_ledger', 'model', 'provider', 'reasoning'))):
            raise ValueError('OpenRouter partition binding differs')
        if fresh:
            partitions.require_child_ledger(entries[0])
            child = Path(entries[0]['child_ledger'])
            if not part['active'] or child.read_text().splitlines() != [json.dumps({'event': 'budget', 'cap_usd': str(amount)})]:
                raise ValueError('Additional hold requires a fresh allocated OpenRouter child')
    finally:
        master.close()
    return {'budget_manifest_path': str(budget_path), 'budget_manifest_sha256': partitions.sha(budget_path),
            'partition_id': partition_id, 'master_path': str(Path(master_path).resolve())}


def _scan(raw, *, baseline_head=old.ORIGINAL_HEAD, baseline_events=old.ORIGINAL_EVENTS):
    events, pieces = old._lines(raw)
    indices = [i for i, event in enumerate(events) if event.get('event') == 'authority_amendment']
    if len(indices) > 1:
        raise ValueError('Duplicate authority amendment')
    split = indices[0] if indices else len(events)
    original, holds, _ = old._scan(b''.join(pieces[:split]), baseline_head=baseline_head,
                                  baseline_events=baseline_events)
    shared, earmarked = original.accounted_usd, Decimal(0)
    complete = False
    if indices:
        proposal = amendment.validate_event(events[split], 'authority')
        if proposal['authority']['sha256'] != old.sha(b''.join(pieces[:split])):
            raise ValueError('Reviewed authority prefix differs')
        complete = amendment.counterpart_committed(proposal, events[split]['review_path'], 'master')
        for event in events[split + 1:]:
            pool = event.get('funding_pool')
            keys = {'event', 'version', 'id', 'usd', 'source_sha256', 'funding_pool'}
            if pool == 'openrouter_additional':
                keys |= {'budget_manifest_path', 'budget_manifest_sha256', 'partition_id', 'master_path'}
            if (set(event) != keys or event.get('event') != 'hold' or event.get('version') != 3 or
                    not isinstance(event.get('id'), str) or not event['id'] or event['id'] in holds or
                    not old._digest(event.get('source_sha256'))):
                raise ValueError('Invalid, duplicate or unsupported v3 hold')
            amount = old._money(event['usd'], positive=True)
            if pool == 'shared':
                shared += amount
            elif pool == 'openrouter_additional':
                if not complete or event['id'] != event['partition_id'] or event['master_path'] != proposal['master']['path']:
                    raise ValueError('Additional OpenRouter pool is unavailable or misbound')
                if amendment.sha(event['budget_manifest_path']) != event['budget_manifest_sha256']:
                    raise ValueError('OpenRouter hold budget changed')
                # Existing holds remain charged even after their child is sealed.
                budget = json.loads(Path(event['budget_manifest_path']).read_text())
                selected = [e for e in budget['partitions'] if e['id'] == event['partition_id']]
                if budget['master_ledger'] != event['master_path'] or len(selected) != 1 or Decimal(selected[0]['cap_usd']) != amount:
                    raise ValueError('OpenRouter hold provenance differs')
                earmarked += amount
            else:
                raise ValueError('Unknown funding pool')
            holds[event['id']] = event
            if shared > SHARED_CAP or earmarked > OPENROUTER_ADDITIONAL_CAP:
                raise ValueError('Earmarked or shared authority cap exceeded')
    return Snapshot(old.sha(raw), shared, earmarked, SHARED_CAP - shared,
                    OPENROUTER_ADDITIONAL_CAP - earmarked if complete else Decimal(0), complete), holds


def read_authority(path, **baseline):
    with old._locked(path) as handle:
        return _scan(handle.read(), **baseline)[0]


def hold_authority(path, hold_id, amount, source, expected_head, *, stage_path,
                   funding_pool='shared', budget_path=None, partition_id=None, **baseline):
    amount = old._money(str(amount), positive=True)
    if not isinstance(hold_id, str) or not hold_id or not old._digest(source):
        raise ValueError('Invalid hold identity')
    with old._locked(path) as handle:
        raw = handle.read(); state, holds = _scan(raw, **baseline)
        if state.head_sha256 != expected_head or hold_id in holds or Path(stage_path).exists():
            raise ValueError('Stale head, duplicate hold or claimed stage')
        if not state.amendment_complete:
            raise ValueError('Reviewed joint amendment not complete')
        event = {'event': 'hold', 'version': 3, 'id': hold_id, 'usd': str(amount),
                 'source_sha256': source, 'funding_pool': funding_pool}
        if funding_pool == 'shared':
            if amount > state.shared_available_usd:
                raise ValueError('Original shared authority cap exhausted')
        elif funding_pool == 'openrouter_additional':
            if amount > state.openrouter_available_usd or hold_id != partition_id:
                raise ValueError('Additional OpenRouter authority cap exhausted or wrong partition')
            events, _ = old._lines(raw)
            amended = next(e for e in events if e.get('event') == 'authority_amendment')
            proposal = amendment.validate_event(amended, 'authority')
            event.update(_binding(budget_path, partition_id, amount, proposal['master']['path'], fresh=True))
        else:
            raise ValueError('Unknown funding pool')
        old._append(handle, event)
        return event
