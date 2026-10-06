#!/usr/bin/env python3
"""Reviewed, non-inference budget hold for the prior Solar unknown-cost gap."""
import argparse
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as native
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority
import solar_decide_offline_plan as solar

BASE = ROOT / 'results/solar-decide-risk-hold-v1'
PLAN = BASE / 'proposal.json'
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
CLAIM = BASE / 'risk-hold.claim.json'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AUTHORITY = authority.AUTHORITY
PARTITION_ID = 'solar-decide-prior-unknown-risk-v1'
CHILD = BASE / ('budget-' + PARTITION_ID + '.jsonl')
CAP = Decimal('0.07864320')
OLD_UNKNOWN = Decimal('0.02621440')
FOUR_QUESTION_BOUND = Decimal('0.10485760')
REASONING = 'historical-unknown-cost-risk-only-no-inference'
SCHEMA = 'solar-decide-risk-hold-v1'
OLD = ROOT / 'results/solar-decide-native-smoke-v1'
SOURCES = ('scripts/solar_decide_risk_hold_v1.py',
           'tests/test_solar_decide_risk_hold_v1.py',
           'docs/SOLAR_DECIDE_RESERVE_AUDIT_2026-10-06.md',
           'scripts/solar_decide_smoke_v1.py',
           'scripts/solar_decide_offline_plan.py',
           'scripts/openrouter_authority_release_v4.py',
           'scripts/paid_budget_partitions_v4.py',
           'scripts/paid_budget_partitions_v3.py',
           'scripts/openrouter_budget_v4.py',
           'scripts/openrouter_budget_v3.py',
           'scripts/postapproval_authority_v3.py',
           'scripts/postapproval_authority_v2.py',
           'results/solar-decide-native-smoke-v1/terminal-public.json',
           'results/solar-decide-native-smoke-v1/budget-reconciliation.json',
           'results/solar-decide-native-smoke-v1/budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl')


def sha(path):
    return native.sha(Path(path).read_bytes())


def historical():
    terminal = json.loads((OLD / 'terminal-public.json').read_text())
    reconciled = json.loads((OLD / 'budget-reconciliation.json').read_text())
    child = [json.loads(line) for line in
             (OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl').read_text().splitlines()]
    if (terminal.get('status') != 'stopped_after_first_request' or
            terminal.get('smoke_attempted') != ['DEV-001'] or
            terminal.get('smoke_never_sent') != ['DEV-002', 'DEV-003'] or
            terminal.get('http_status') != 429 or
            terminal.get('unknown_cost_upper_bound_usd') != str(OLD_UNKNOWN) or
            reconciled.get('event') != 'partition_reconciled' or
            reconciled.get('known_actual_usd') != '0' or
            reconciled.get('unknown_upper_bound_usd') != str(OLD_UNKNOWN) or
            reconciled.get('child_sha256') != sha(OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl') or
            child[-1].get('event') != 'partition_closed' or
            len(child) != 4 or child[1].get('event') != 'reserve' or
            child[2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            Decimal(child[1].get('usd', '-1')) != OLD_UNKNOWN or
            Decimal(child[2].get('usd', '-1')) != OLD_UNKNOWN):
        raise ValueError('Historical Solar unknown attempt differs')
    return terminal, reconciled


def proposal_value():
    historical()
    if (solar.MODEL != 'upstage/solar-decide' or solar.PROVIDER != 'Upstage' or
            solar.CONTEXT != 524288 or solar.PROMPT_RATE != Decimal('0.00000005') or
            len(solar.p0_payload('test', 'policy', 'upstage')['questions']) != 4 or
            FOUR_QUESTION_BOUND != 4 * solar.CONTEXT * solar.PROMPT_RATE or
            CAP != FOUR_QUESTION_BOUND - OLD_UNKNOWN):
        raise ValueError('Solar conservative four-question risk arithmetic differs')
    return {'schema': SCHEMA + '-proposal', 'status': 'offline_unadmitted',
            'purpose': 'Additional cap encumbrance for one historical unknown-cost request; no new inference or charge claimed.',
            'model': solar.MODEL, 'provider': solar.PROVIDER, 'funding_pool': 'openrouter_additional',
            'partition_id': PARTITION_ID, 'reasoning': REASONING,
            'historical_unknown_upper_bound_usd': str(OLD_UNKNOWN),
            'conservative_four_question_bound_usd': str(FOUR_QUESTION_BOUND),
            'additional_risk_hold_usd': str(CAP),
            'old_attempt_id': 'DEV-001', 'old_unsent_ids': ['DEV-002','DEV-003'],
            'new_requests_authorized': False, 'new_cost_event_authorized': False,
            'release_policy': 'Keep active until separately reviewed billing resolution; never use ordinary unused-child release while risk remains.',
            'source_sha256': {name: sha(ROOT / name) for name in SOURCES}}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'proposal_sha256': sha(PLAN),
            'controller_sha256': sha(__file__), 'amount_usd': str(CAP),
            'partition_id': PARTITION_ID, 'funding_pool': 'openrouter_additional'}


def prepare():
    if BASE.exists():
        raise FileExistsError('Solar risk hold proposal already exists')
    value = proposal_value()
    BASE.mkdir(parents=True)
    with PLAN.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True); out.write('\n')
    with REVIEW.open('x') as out:
        json.dump(review_template(), out, indent=2, sort_keys=True); out.write('\n')
    return sha(PLAN)


def verify():
    if json.loads(PLAN.read_text()) != proposal_value():
        raise ValueError('Solar risk hold proposal or source changed')
    return sha(PLAN)


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent Solar risk hold review missing')


def budget_entry():
    manifest = json.loads(BUDGET.read_text())
    entry = {'id': PARTITION_ID, 'cap_usd': str(CAP), 'child_ledger': str(CHILD),
             'model': solar.MODEL, 'provider': solar.PROVIDER, 'reasoning': REASONING}
    if (manifest != {'version': 'paid-partitions-v1', 'master_ledger': str(MASTER),
                     'partitions': [entry]}):
        raise ValueError('Solar risk-only partition differs')
    child = partitions.open_partition(MASTER, BUDGET, PARTITION_ID,
                                      solar.MODEL, solar.PROVIDER, REASONING)
    try:
        if child.closed or len(child.events) != 1 or child.events[0] != {'event':'budget','cap_usd':str(CAP)}:
            raise ValueError('Risk-only child was used or sealed')
    finally:
        child.close()
    return entry


def hold_source():
    return native.sha(native.canonical({'schema': SCHEMA + '-hold',
        'proposal_sha256': sha(PLAN), 'budget_manifest_path': str(BUDGET),
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'historical_child_sha256':
        sha(OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl')}))


def admit():
    """Root-reviewed entry. A failed hold leaves an encumbered, unused child."""
    verify(); require_review()
    with (BASE / '.admit.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if CLAIM.exists():
            raise FileExistsError('Solar risk hold already admitted')
        old_sha = sha(OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl')
        state = authority.read_authority(AUTHORITY)
        if state.openrouter_available_usd < CAP:
            raise ValueError('Insufficient OpenRouter-only authority for risk hold')
        if not BUDGET.exists():
            partitions.allocate(MASTER, BUDGET, [{'id': PARTITION_ID, 'cap_usd': str(CAP),
                'model': solar.MODEL, 'provider': solar.PROVIDER, 'reasoning': REASONING}])
        budget_entry()
        with authority.old._locked(AUTHORITY) as handle:
            head, holds, released = authority._scan(handle.read())
        if PARTITION_ID in released:
            raise ValueError('Risk hold was released before billing resolution')
        if PARTITION_ID not in holds:
            authority.hold_authority(AUTHORITY, PARTITION_ID, str(CAP), hold_source(),
                head.head_sha256, stage_path=CLAIM, funding_pool='openrouter_additional',
                budget_path=BUDGET, partition_id=PARTITION_ID)
        else:
            hold = holds[PARTITION_ID]
            if (hold.get('usd') != str(CAP) or hold.get('source_sha256') != hold_source() or
                    hold.get('funding_pool') != 'openrouter_additional'):
                raise ValueError('Existing Solar risk hold differs')
        if sha(OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl') != old_sha:
            raise ValueError('Historical Solar child changed during admission')
        result = {'schema': SCHEMA + '-admission', 'status': 'active_risk_hold_no_inference',
                  'proposal_sha256': sha(PLAN), 'review_sha256': sha(REVIEW),
                  'budget_manifest_sha256': sha(BUDGET), 'child_sha256': sha(CHILD),
                  'historical_child_sha256': old_sha, 'hold_source_sha256': hold_source(),
                  'usd': str(CAP), 'new_requests': 0, 'known_charge_usd': '0'}
        with CLAIM.open('x') as out:
            json.dump(result, out, indent=2, sort_keys=True); out.write('\n')
            out.flush(); os.fsync(out.fileno())
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','verify','review-template','admit'))
    action = parser.parse_args().action
    if action == 'prepare': print(prepare())
    elif action == 'verify': print(verify())
    elif action == 'review-template': print(json.dumps(review_template(), indent=2))
    else: print(json.dumps(admit(), indent=2))


if __name__ == '__main__':
    main()
