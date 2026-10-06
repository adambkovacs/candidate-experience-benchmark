"""Isolated authority, master and child fixtures for v4 release controls."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_authority_release_v4 as release


def line(value):
    return release.old.canonical(value) + b'\n'


class Ledgers:
    def __init__(self, root, monkeypatch):
        self.root = root
        self.authority = root / 'authority.jsonl'
        self.master = root / 'master.jsonl'
        header = line({'event': 'authority'})
        self.authority.write_bytes(header + line({'event': 'authority_amendment',
                                                  'review_path': 'isolated-review'}))
        self.master_events = [{'event': 'budget', 'cap_usd': '22.38'}]
        self.master.write_bytes(line(self.master_events[0]))
        self.holds = {}
        monkeypatch.setattr(release, 'MASTER', self.master)
        monkeypatch.setattr(release.old, '_scan', lambda raw, **kwargs: (
            SimpleNamespace(accounted_usd=Decimal(0)), {}, {}))
        monkeypatch.setattr(release.amendment, 'validate_event',
            lambda event, kind: {'authority': {'sha256': release.old.sha(header)},
                                 'master': {'path': str(self.master)}})
        monkeypatch.setattr(release.amendment, 'counterpart_committed',
                            lambda *args: True)

    def add(self, name, cap, *, known='0', unknown='0', closed=True):
        cap, known, unknown = map(Decimal, (cap, known, unknown))
        child = self.root / (name + '.child.jsonl')
        budget = self.root / (name + '.budget.json')
        events = [{'event': 'budget', 'cap_usd': str(cap)}]
        if known:
            events.extend(({'event': 'reserve', 'attempt_id': name + '-known',
                            'record_id': name + ':DEV-001', 'usd': str(known)},
                           {'event': 'settle', 'attempt_id': name + '-known',
                            'usd': str(known)}))
        if unknown:
            events.extend(({'event': 'reserve', 'attempt_id': name + '-unknown',
                            'record_id': name + ':DEV-002', 'usd': str(unknown)},
                           {'event': 'unknown_cost_accounted_as_upper_bound',
                            'attempt_id': name + '-unknown', 'usd': str(unknown)}))
        if closed:
            events.append({'event': 'partition_closed', 'reason': 'test closure'})
        child.write_bytes(b''.join(map(line, events)))
        entry = {'id': name, 'cap_usd': str(cap), 'child_ledger': str(child),
                 'model': 'fixture/model', 'provider': 'fixture/provider',
                 'reasoning': 'low'}
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str(self.master), 'partitions': [entry]}) + '\n')
        budget_sha = release.old.file_sha(budget)
        self.master_events.append({'event': 'budget_partition', 'partition_id': name,
            'manifest_path': str(budget), 'manifest_sha256': budget_sha,
            'child_ledger': str(child), 'allocated_usd': str(cap),
            'model': entry['model'], 'provider': entry['provider'],
            'reasoning': entry['reasoning']})
        if closed:
            self.master_events.append({'event': 'partition_reconciled',
                'partition_id': name, 'child_ledger': str(child),
                'child_sha256': release.old.file_sha(child),
                'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(unknown),
                'unused_allocation_released_usd': str(cap - known - unknown)})
        self.master.write_bytes(b''.join(map(line, self.master_events)))
        hold = {'event': 'hold', 'version': 3, 'id': name, 'usd': str(cap),
                'source_sha256': release.old.sha(name.encode()),
                'funding_pool': 'openrouter_additional', 'partition_id': name,
                'master_path': str(self.master), 'budget_manifest_path': str(budget),
                'budget_manifest_sha256': budget_sha}
        with self.authority.open('ab') as out:
            out.write(line(hold))
        self.holds[name] = (hold, child)

    def close(self, name):
        hold, child = self.holds[name]
        child.write_bytes(child.read_bytes() + line({'event': 'partition_closed',
                                                     'reason': 'test closure'}))
        self.master_events.append({'event': 'partition_reconciled',
            'partition_id': name, 'child_ledger': str(child),
            'child_sha256': release.old.file_sha(child),
            'known_actual_usd': '0', 'unknown_upper_bound_usd': '0',
            'unused_allocation_released_usd': hold['usd']})
        self.master.write_bytes(b''.join(map(line, self.master_events)))


@pytest.fixture
def ledgers(tmp_path, monkeypatch):
    return Ledgers(tmp_path, monkeypatch)


def reviewed(plan):
    return {'schema': release.SCHEMA + '-root-review', 'approved': True,
            'independent_review': True, 'reviewer': 'root',
            'plan_sha256': release.old.sha(release.old.canonical(plan)),
            'v3_consumers_quiesced': True}


def test_release_preserves_unknown_bound_and_rejects_tampering(ledgers):
    ledgers.add('closed-a', '1', known='0.10', unknown='0.05')
    plan = release.release_plan('closed-a', 'release-a', path=ledgers.authority)
    assert (plan['event']['usd'], plan['event']['known_actual_usd'],
            plan['event']['unknown_upper_bound_usd']) == ('0.85', '0.10', '0.05')
    _, holds, _ = release._scan(ledgers.authority.read_bytes())
    for key, value in (('unknown_upper_bound_usd', '0'), ('usd', '0.90'),
                       ('hold_source_sha256', '0' * 64), ('child_sha256', '0' * 64)):
        event = deepcopy(plan['event']); event[key] = value
        with pytest.raises(ValueError):
            release._release_evidence(event, holds['closed-a'])
    release.append_release(plan, reviewed(plan), path=ledgers.authority)
    state, _, used = release._scan(ledgers.authority.read_bytes())
    assert state.openrouter_available_usd == Decimal('9.85')
    assert used == {'closed-a'}
    with pytest.raises(ValueError):
        release.append_release(plan, reviewed(plan), path=ledgers.authority)


def test_first_transition_requires_all_old_children_closed(ledgers):
    ledgers.add('closed-a', '1', known='0.10')
    ledgers.add('active-old', '0.5', closed=False)
    plan = release.release_plan('closed-a', 'release-a', path=ledgers.authority)
    before = ledgers.authority.read_bytes()
    with pytest.raises(ValueError, match='receipt required'):
        release.append_release(plan, {}, path=ledgers.authority)
    with pytest.raises(ValueError, match='not uniquely reconciled'):
        release.append_release(plan, reviewed(plan), path=ledgers.authority)
    assert ledgers.authority.read_bytes() == before
    ledgers.close('active-old')
    with pytest.raises(ValueError, match='head changed'):
        release.append_release(plan, reviewed(plan), path=ledgers.authority)
    fresh = release.release_plan('closed-a', 'release-a', path=ledgers.authority)
    release.append_release(fresh, reviewed(fresh), path=ledgers.authority)


def test_later_release_allows_unrelated_active_new_v4_child(ledgers):
    ledgers.add('closed-a', '1', known='0.10')
    ledgers.add('closed-b', '0.5', unknown='0.05')
    first = release.release_plan('closed-a', 'release-a', path=ledgers.authority)
    release.append_release(first, reviewed(first), path=ledgers.authority)
    ledgers.add('new-v4-active', '0.4', closed=False)
    second = release.release_plan('closed-b', 'release-b', path=ledgers.authority)
    release.append_release(second, reviewed(second), path=ledgers.authority)
    state, _, used = release._scan(ledgers.authority.read_bytes())
    assert used == {'closed-a', 'closed-b'}
    assert state.openrouter_available_usd == Decimal('9.45')
    with pytest.raises(ValueError, match='not uniquely reconciled'):
        release.release_plan('new-v4-active', 'release-new', path=ledgers.authority)


def test_release_id_collision_and_missing_transition_refused(ledgers):
    ledgers.add('closed-a', '1', known='0.10')
    with pytest.raises(ValueError, match='Transition'):
        release.hold_authority(ledgers.authority, 'future', '0.1', 'a' * 64,
            release._scan(ledgers.authority.read_bytes())[0].head_sha256,
            stage_path=ledgers.root / 'future.claim.json', funding_pool='openrouter_additional',
            budget_path=ledgers.root / 'future.budget.json', partition_id='future')
    with pytest.raises(ValueError, match='Duplicate'):
        release.release_plan('closed-a', 'closed-a', path=ledgers.authority)
