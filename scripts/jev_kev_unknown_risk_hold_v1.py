#!/usr/bin/env python3
"""Offline proposal and separately gated hold for three historical native-Choice unknowns."""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT
import openrouter_authority_release_v4 as authority
import paid_budget_partitions_v4 as partitions

BASE = ROOT / 'results/jev-kev-unknown-risk-hold-v1'
PLAN = BASE / 'proposal.json'
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
CLAIM = BASE / 'risk-hold.claim.json'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AUTHORITY = authority.AUTHORITY
PARTITION_ID = 'jev-kev-historical-unknown-four-context-risk-v1'
CHILD = BASE / ('budget-' + PARTITION_ID + '.jsonl')
CAP = Decimal('0.009096192')
MODEL = 'historical-kev-and-jev-unknown-risk-only'
PROVIDER = 'OpenRouter'
REASONING = 'three-historical-four-question-unknowns-no-inference'
SCHEMA = 'jev-kev-unknown-risk-hold-v1'

KEV = 'results/route-audits/decision-kev-repeats-20260930/fresh3/'
JEV_PARENT = 'results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/'
JEV_TAIL = ('results/route-audits/jev-authority-v2-20261006/'
            'p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/')

ITEMS = (
    {'model': 'jaredpalmer/kev-4b', 'provider_tag': 'siliconflow/fp8', 'context': 8192,
     'record_id': 'DEV-026', 'attempt_id': 'd85c42b2-1333-4797-8a52-d324457a2361',
     'old_usd': '0.000344064', 'known_usd': None,
     'catalog': 'results/route-audits/native-variants-recheck-20261006/kev-endpoint.raw.json',
     'request_plan': 'results/route-audits/decision-kev-development-20260930/manifest.json',
     'attempts': KEV + 'attempts.jsonl', 'audit': KEV + 'interruption-audit.json'},
    {'model': 'typesafe/jev-1.13', 'provider_tag': 'typesafe', 'context': 32000,
     'record_id': 'DEV-018', 'attempt_id': 'e99629c9-d245-477d-9845-79997b773aac',
     'old_usd': '0.001344000', 'known_usd': '0.001940694',
     'catalog': JEV_PARENT + 'fresh2/endpoint-catalog.json',
     'request_plan': 'results/route-audits/native-variants-offline-20260930/jev-openrouter-native-p2-choice-v1.json',
     'attempts': JEV_PARENT + 'fresh2/unknown-cost-evidence.jsonl',
     'terminal': JEV_PARENT + 'fresh2/terminal-public.json',
     'reconciliation': JEV_PARENT + 'fresh2/budget-reconciliation.json',
     'child': JEV_PARENT + 'fresh2.budget-jev-openrouter-native-p2-choice-v1-fresh2-full-v1.jsonl',
     'partition_id': 'jev-openrouter-native-p2-choice-v1-fresh2-full-v1'},
    {'model': 'typesafe/jev-1.13', 'provider_tag': 'typesafe', 'context': 32000,
     'record_id': 'DEV-060', 'attempt_id': '21d43248-7b5a-440b-a7bd-d803f7147b04',
     'old_usd': '0.001344000', 'known_usd': '0.004681740',
     'catalog': JEV_TAIL + 'tail/endpoint-catalog.json',
     'request_plan': 'results/route-audits/native-variants-offline-20260930/jev-openrouter-native-p2-choice-v1.json',
     'attempts': JEV_TAIL + 'tail/unknown-cost-evidence.jsonl',
     'terminal': JEV_TAIL + 'tail/terminal-public.json',
     'reconciliation': JEV_TAIL + 'tail/budget-reconciliation.json',
     'child': JEV_TAIL + 'tail.budget-jev-openrouter-native-p2-choice-v1-fresh2-dev019-060-continuation-v2.jsonl',
     'partition_id': 'jev-openrouter-native-p2-choice-v1-fresh2-dev019-060-continuation-v2'},
)

SOURCES = (
    'scripts/jev_kev_unknown_risk_hold_v1.py',
    'tests/test_jev_kev_unknown_risk_hold_v1.py',
    'docs/JEV_KEV_UNKNOWN_BOUND_AUDIT_2026-10-07.md',
    'docs/JEV_KEV_UNKNOWN_RISK_HOLD_PROPOSAL_2026-10-07.md',
    'scripts/openrouter_authority_release_v4.py',
    'scripts/paid_budget_partitions_v4.py',
    'scripts/paid_budget_partitions_v3.py',
    'scripts/openrouter_budget_v4.py',
    'scripts/openrouter_budget_v3.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/openrouter_budget_amendment_v3.py',
    'scripts/postapproval_authority_v3.py',
    'scripts/postapproval_authority_v2.py',
    'results/route-audits/kev-fresh3-continuation-20260930/terminal-reconciliation.json',
) + tuple(sorted({item[key] for item in ITEMS for key in (
    'catalog', 'request_plan', 'attempts', 'audit', 'terminal', 'reconciliation', 'child') if key in item}))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def historical():
    """Validate immutable attempt and old-unknown evidence, without reading live ledgers."""
    result = []
    for item in ITEMS:
        catalog = json.loads((ROOT / item['catalog']).read_text())['data']['endpoints']
        matches = [e for e in catalog if e.get('tag') == item['provider_tag'] and
                   e.get('model_id') == item['model']]
        if len(matches) != 1:
            raise ValueError('Historical route differs')
        route = matches[0]
        if (route.get('context_length') != item['context'] or
                route.get('pricing', {}).get('prompt') != '0.000000042' or
                route.get('pricing', {}).get('completion') != '0'):
            raise ValueError('Historical route price differs')
        plan = json.loads((ROOT / item['request_plan']).read_text())
        requests = plan.get('requests', [])
        if (len(requests) != 60 or
                [r['id'] for r in requests] != [f'DEV-{n:03d}' for n in range(1, 61)] or
                any(len(r['payload']['questions']) != 4 for r in requests)):
            raise ValueError('Frozen four-question requests differ')
        attempts = rows(ROOT / item['attempts'])
        old = Decimal(item['old_usd'])
        bound = Decimal(4 * item['context']) * Decimal('0.000000042')
        if bound != old * 4:
            raise ValueError('Four-context arithmetic differs')
        if item['model'].startswith('jaredpalmer/'):
            audit = json.loads((ROOT / item['audit']).read_text())
            prefix = ROOT / 'results/route-audits/kev-fresh3-continuation-20260930/terminal-reconciliation.json'
            closure = json.loads(prefix.read_text())
            matching = [r for r in attempts if r.get('id') == item['record_id']]
            if (audit.get('unknown_record_id') != item['record_id'] or
                    audit.get('unknown_attempt_id') != item['attempt_id'] or
                    audit.get('unknown_upper_bound_usd') != item['old_usd'] or
                    audit.get('attempts_sha256') != sha(ROOT / item['attempts']) or
                    closure.get('original_unknown_attempt_id') != item['attempt_id'] or
                    closure.get('original_unknown_upper_bound_usd') != item['old_usd'] or
                    len(matching) != 2 or [r['stage'] for r in matching] != ['reserved', 'transport_error'] or
                    matching[0].get('ledger_attempt_id') != item['attempt_id'] or
                    matching[0].get('reserved_cost_usd') != item['old_usd'] or
                    matching[1].get('attempt_id') != item['attempt_id'] or
                    matching[1].get('actual_cost_usd') is not None):
                raise ValueError('Historical Kev unknown differs')
        else:
            terminal = json.loads((ROOT / item['terminal']).read_text())
            reconciliation = json.loads((ROOT / item['reconciliation']).read_text())
            child = rows(ROOT / item['child'])
            match = [r for r in attempts if r.get('id') == item['record_id'] and
                     r.get('attempt_id') == item['attempt_id']]
            events = [r for r in child if r.get('attempt_id') == item['attempt_id']]
            if (len(match) != 1 or match[0].get('reserved_cost_usd') != item['old_usd'] or
                    match[0].get('cost_unknown') is not True or match[0].get('actual_cost_usd') is not None or
                    terminal.get('unknown_charge_upper_bound_usd') != item['old_usd'] or
                    terminal.get('attempts_sha256') is None or
                    reconciliation.get('event') != 'partition_reconciled' or
                    reconciliation.get('partition_id') != item['partition_id'] or
                    reconciliation.get('known_actual_usd') != item['known_usd'] or
                    reconciliation.get('unknown_upper_bound_usd') != item['old_usd'] or
                    reconciliation.get('child_sha256') != sha(ROOT / item['child']) or
                    child[-1].get('event') != 'partition_closed' or
                    [r.get('event') for r in events] != ['reserve', 'unknown_cost_accounted_as_upper_bound'] or
                    any(r.get('usd') != item['old_usd'] for r in events) or
                    events[1].get('evidence_sha256') != sha(ROOT / item['attempts'])):
                raise ValueError('Historical Jev unknown differs')
        result.append({'model': item['model'], 'provider': item['provider_tag'],
                       'record_id': item['record_id'], 'attempt_id': item['attempt_id'],
                       'old_unknown_usd': item['old_usd'], 'four_context_usd': str(bound),
                       'additional_risk_usd': str(bound - old),
                       'evidence_sha256': sha(ROOT / item['attempts'])})
    if sum((Decimal(x['additional_risk_usd']) for x in result), Decimal(0)) != CAP:
        raise ValueError('Additional risk amount differs')
    return result


def proposal_value():
    items = historical()
    return {'schema': SCHEMA + '-proposal', 'status': 'offline_unadmitted',
            'purpose': 'Additional cap encumbrance for three historical unknowns; no inference or charge claimed.',
            'partition_id': PARTITION_ID, 'model': MODEL, 'provider': PROVIDER,
            'reasoning': REASONING, 'funding_pool': 'openrouter_additional',
            'items': items, 'previously_retained_usd': str(sum(
                (Decimal(i['old_unknown_usd']) for i in items), Decimal(0))),
            'additional_risk_hold_usd': str(CAP), 'new_requests_authorized': False,
            'new_cost_event_authorized': False,
            'release_policy': 'Keep active until separately reviewed billing resolution; do not release unused child allocation while risk remains.',
            'source_sha256': {name: sha(ROOT / name) for name in SOURCES}}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False, 'reviewer': None,
            'proposal_sha256': sha(PLAN), 'controller_sha256': sha(__file__),
            'amount_usd': str(CAP), 'partition_id': PARTITION_ID,
            'funding_pool': 'openrouter_additional'}


def prepare():
    if BASE.exists():
        raise FileExistsError('Risk-hold proposal already exists')
    value = proposal_value()
    BASE.mkdir(parents=True)
    with PLAN.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True); out.write('\n')
    with REVIEW.open('x') as out:
        json.dump(review_template(), out, indent=2, sort_keys=True); out.write('\n')
    return sha(PLAN)


def verify():
    if json.loads(PLAN.read_text()) != proposal_value():
        raise ValueError('Historical evidence, source, or proposal changed')
    return sha(PLAN)


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Root and independent risk-hold review missing')


def current_master_retention():
    """Fail closed if current master no longer contains exactly the old liabilities."""
    events = rows(MASTER)
    kev = ITEMS[0]
    original = [e for e in events if e.get('attempt_id') == kev['attempt_id']]
    if ([e.get('event') for e in original] != ['reserve', 'unknown_cost_accounted_as_upper_bound'] or
            any(e.get('usd') != kev['old_usd'] for e in original) or
            original[0].get('record_id') != 'kev-openrouter-native-p0-fresh3:DEV-026' or
            original[1].get('actual_cost_usd') is not None or
            original[1].get('evidence_sha256') != sha(ROOT / kev['attempts'])):
        raise ValueError('Old Kev master reservation is absent or changed')
    for item in ITEMS[1:]:
        reconciled = [e for e in events if e.get('event') == 'partition_reconciled' and
                      e.get('partition_id') == item['partition_id']]
        if (len(reconciled) != 1 or reconciled[0].get('known_actual_usd') != item['known_usd'] or
                reconciled[0].get('unknown_upper_bound_usd') != item['old_usd'] or
                reconciled[0].get('child_sha256') != sha(ROOT / item['child'])):
            raise ValueError('Old Jev partition reconciliation is absent or changed')


def budget_entry():
    entry = {'id': PARTITION_ID, 'cap_usd': str(CAP), 'child_ledger': str(CHILD),
             'model': MODEL, 'provider': PROVIDER, 'reasoning': REASONING}
    expected = {'version': 'paid-partitions-v1', 'master_ledger': str(MASTER),
                'partitions': [entry]}
    if json.loads(BUDGET.read_text()) != expected:
        raise ValueError('Risk-only partition manifest differs')
    child = partitions.open_partition(MASTER, BUDGET, PARTITION_ID, MODEL, PROVIDER, REASONING)
    try:
        if child.closed or len(child.events) != 1 or child.events[0] != {'event': 'budget', 'cap_usd': str(CAP)}:
            raise ValueError('Risk-only child was used or sealed')
    finally:
        child.close()
    return entry


def hold_source():
    value = {'schema': SCHEMA + '-hold', 'proposal_sha256': sha(PLAN),
             'budget_manifest_path': str(BUDGET), 'budget_manifest_sha256': sha(BUDGET),
             'partition_id': PARTITION_ID, 'cap_usd': str(CAP),
             'historical_child_sha256': [sha(ROOT / item['child']) for item in ITEMS[1:]],
             'historical_kev_attempts_sha256': sha(ROOT / ITEMS[0]['attempts'])}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def admit():
    """Only after a separate reviewed receipt; never dispatches inference."""
    verify(); require_review()
    with (BASE / '.admit.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if CLAIM.exists():
            raise FileExistsError('Risk hold already admitted')
        current_master_retention()
        state = authority.read_authority(AUTHORITY)
        with authority.old._locked(AUTHORITY) as handle:
            _, holds, released = authority._scan(handle.read())
        if PARTITION_ID in released:
            raise ValueError('Risk hold was released before billing resolution')
        if PARTITION_ID not in holds and state.openrouter_available_usd < CAP:
            raise ValueError('Insufficient OpenRouter-only authority for risk hold')
        if not BUDGET.exists():
            partitions.allocate(MASTER, BUDGET, [{'id': PARTITION_ID, 'cap_usd': str(CAP),
                'model': MODEL, 'provider': PROVIDER, 'reasoning': REASONING}])
        budget_entry()
        current_master_retention()
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
                    hold.get('funding_pool') != 'openrouter_additional' or
                    hold.get('budget_manifest_path') != str(BUDGET) or
                    hold.get('budget_manifest_sha256') != sha(BUDGET) or
                    hold.get('partition_id') != PARTITION_ID or
                    hold.get('master_path') != str(MASTER)):
                raise ValueError('Existing risk hold differs')
        result = {'schema': SCHEMA + '-admission', 'status': 'active_risk_hold_no_inference',
                  'proposal_sha256': sha(PLAN), 'review_sha256': sha(REVIEW),
                  'budget_manifest_sha256': sha(BUDGET), 'child_sha256': sha(CHILD),
                  'hold_source_sha256': hold_source(), 'usd': str(CAP),
                  'new_requests': 0, 'known_charge_usd': '0'}
        with CLAIM.open('x') as out:
            json.dump(result, out, indent=2, sort_keys=True); out.write('\n')
            out.flush(); os.fsync(out.fileno())
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'review-template', 'admit'))
    action = parser.parse_args().action
    if action == 'prepare': print(prepare())
    elif action == 'verify': print(verify())
    elif action == 'review-template': print(json.dumps(review_template(), indent=2))
    else: print(json.dumps(admit(), indent=2))


if __name__ == '__main__':
    main()
