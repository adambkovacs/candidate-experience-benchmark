#!/usr/bin/env python3
"""Offline, separately admitted plain Mistral high fresh1/P2 plan."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import mistral119_high_plain_remaining8_v4 as prior
import mistral119_high_plain_authority_v1 as old
import openrouter_authority_release_v4 as authority

ROOT = prior.ROOT
SCHEMA = 'mistral119-high-plain-p2-v4'
CONFIG = old.CONFIG + '-independent-fresh1-p2-v4'
BASE = old.BASE / 'independent-p2-v4'
MANIFEST = BASE / 'proposal.json'
PASSES = ('fresh1',)
PHASES = (('fresh1', 'P2'),)
ORDERS = {'fresh1': ['P2']}
PARTITION_ID = SCHEMA
CHILD_CAP = Decimal('0.75')
RESERVE = old.RESERVE
PRIOR_TERMINAL = prior.BASE / 'terminal-public.json'
PRIOR_RECONCILIATION = prior.BASE / 'reconciliation.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def portable_sources():
    return prior.portable_sources()


def portable_route(sources):
    return prior.portable_route(sources)


def stopped_predecessors():
    first = json.loads((old.BASE / 'terminal-public.json').read_text())
    second = json.loads(PRIOR_TERMINAL.read_text())
    if (first.get('stage') != 'fresh1/P0/smoke' or
            first.get('status') != 'stopped_provider_rate_limit' or
            first.get('attempted_ids') != ['DEV-001'] or
            first.get('never_sent_smoke_ids') != ['DEV-002', 'DEV-003'] or
            first.get('unknown_cost_upper_bound_usd') != str(RESERVE) or
            first.get('reconciliation_sha256') != sha(old.BASE / 'reconciliation.json') or
            second.get('stage') != 'fresh1/P1/smoke' or
            second.get('status') != 'stopped_provider_rate_limit' or
            second.get('attempted_ids') != ['DEV-001'] or
            second.get('never_sent_smoke_ids') != ['DEV-002', 'DEV-003'] or
            second.get('development_requests_sent') != 0 or
            second.get('unknown_cost_upper_bound_usd') != str(RESERVE) or
            not second.get('child_sealed') or not second.get('master_reconciled')):
        raise ValueError('Stopped plain Mistral predecessors differ')
    return first, second


def plan_data(repeat):
    if repeat != 'fresh1':
        raise ValueError('Only fresh1/P2 is admitted by this plan')
    prior.verify()
    stopped_predecessors()
    previous = prior.verify_plan('fresh1', sha(prior.BASE / 'fresh1/manifest.json'))
    result = deepcopy(previous)
    result.update(schema=SCHEMA + '-plan', series_id=SCHEMA,
                  configuration_id=CONFIG, condition_order=['P2'],
                  conditions={'P2': deepcopy(previous['conditions']['P2'])},
                  execution_status='offline_independent_p2_unadmitted',
                  planned_request_count=63,
                  interrupted_predecessor='Plain fresh1/P0 and fresh1/P1 each stopped on smoke DEV-001 HTTP 429; neither is credited or replayed.',
                  partition_id=PARTITION_ID,
                  proposed_child_budget_usd=str(CHILD_CAP),
                  parent_p1_terminal_sha256=sha(PRIOR_TERMINAL),
                  parent_p1_reconciliation_sha256=sha(PRIOR_RECONCILIATION))
    result['budget_estimate'] = {
        'maximum_per_request_reserve_usd': str(RESERVE),
        'proposed_child_cap_usd': str(CHILD_CAP),
        'planned_request_count': 63,
        'simultaneous_worst_case_reservation_usd': str(RESERVE * 63),
        'allocation_policy': 'One child, sequential reservations, no top-up'}
    result['dispatch_gate'] = ('Independent three-call P2 smoke; root inspects all raw responses '
        'before 60 development calls. Preserve both stopped predecessors.')
    return result


def verify_plan(repeat, digest):
    if repeat != 'fresh1':
        raise ValueError('Only fresh1/P2 is admitted by this plan')
    path = BASE / 'fresh1/manifest.json'
    if sha(path) != digest or json.loads(path.read_text()) != plan_data(repeat):
        raise ValueError('Independent P2 plan differs')
    return json.loads(path.read_text())


def source_paths():
    return [ROOT / 'scripts' / name for name in (
        'mistral119_high_plain_p2_v4.py',
        'mistral119_high_plain_p2_v4_execution.py',
        'mistral119_high_plain_remaining8_v4.py',
        'mistral119_high_plain_remaining8_v4_execution.py',
        'openrouter_authority_release_v4.py',
        'paid_budget_partitions_v4.py',
        'qwen27_fresh_repeat_execution.py')]


def proposal_data():
    prior.verify()
    stopped_predecessors()
    plan_path = BASE / 'fresh1/manifest.json'
    verify_plan('fresh1', sha(plan_path))
    paths = source_paths() + [
        ROOT / 'tests/test_mistral119_high_plain_p2_v4.py',
        prior.MANIFEST, prior.BASE / 'fresh1/manifest.json',
        old.BASE / 'terminal-public.json', old.BASE / 'reconciliation.json',
        PRIOR_TERMINAL, PRIOR_RECONCILIATION]
    return {'schema': SCHEMA + '-proposal', 'status': 'offline_unadmitted',
        'configuration_id': CONFIG, 'stage': 'fresh1/P2',
        'model': old.study.MODEL, 'provider': old.PROVIDER,
        'reasoning_effort': 'high', 'plan_sha256': sha(plan_path),
        'previous_p0_terminal_sha256': sha(old.BASE / 'terminal-public.json'),
        'previous_p1_terminal_sha256': sha(PRIOR_TERMINAL),
        'previous_p1_reconciliation_sha256': sha(PRIOR_RECONCILIATION),
        'per_request_reserve_usd': str(RESERVE),
        'proposed_child_cap_usd': str(CHILD_CAP),
        'full_phase_completion_guaranteed': False,
        'authority_reader': authority.SCHEMA,
        'funding_pool': 'openrouter_additional',
        'partition_id': PARTITION_ID,
        'allocation_authorized': False, 'dispatch_authorized': False,
        'source_bindings': {relative(path): sha(path) for path in paths}}


def prepare():
    if BASE.exists():
        raise FileExistsError('Independent P2 plan already prepared')
    plan = plan_data('fresh1')
    path = BASE / 'fresh1/manifest.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    MANIFEST.write_text(json.dumps(proposal_data(), indent=2) + '\n')
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    for name, digest in saved['source_bindings'].items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT.resolve())
        if sha(path) != digest:
            raise ValueError('Bound independent P2 source changed: ' + name)
    if saved != proposal_data():
        raise ValueError('Independent P2 proposal differs')
    return sha(MANIFEST)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    print({'prepare': prepare, 'verify': verify}[parser.parse_args().action]())
