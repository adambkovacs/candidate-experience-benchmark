#!/usr/bin/env python3
"""Offline plan for a new Solar Decide native Choice nine-phase series."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as native
import solar_decide_offline_plan as solar
import solar_decide_risk_hold_v1 as risk
import solar_decide_unsent_smoke_v2 as suffix
import solar_decide_unsent_smoke_v2_execution as suffix_run

BASE = ROOT / 'results/solar-decide-native-full-v1'
PLAN = BASE / 'plan.json'
REVIEW = BASE / 'root-review.json'
SCHEMA = 'solar-decide-native-postinterruption-full-v1'
PHASES = tuple(f'fresh{fresh}/{condition}' for fresh in (1, 2, 3)
               for condition in ('P0', 'P1', 'P2'))
BOUND = 4 * solar.CONTEXT * max(solar.PROMPT_RATE, solar.CACHE_RATE)
SOURCE_PATHS = (
    'scripts/solar_decide_native_full_v1.py',
    'tests/test_solar_decide_native_full_v1.py',
    'scripts/solar_decide_offline_plan.py',
    'scripts/solar_decide_unsent_smoke_v2.py',
    'scripts/solar_decide_unsent_smoke_v2_execution.py',
    'scripts/solar_decide_risk_hold_v1.py',
    'scripts/jev_native_prompt_variants_v1.py',
    'scripts/jev_benchmark.py',
    'scripts/openrouter_decision_smoke.py',
    'scripts/development_benchmark.py',
    'scripts/openrouter_paid_benchmark.py',
    'data/pilot/inputs.jsonl',
    'docs/LABELING_GUIDE.md',
    'results/route-audits/solar-openrouter-endpoint-20260930.json',
    'results/solar-decide-native-smoke-v1/terminal-public.json',
    'results/solar-decide-native-smoke-v1/budget-reconciliation.json',
    'results/solar-decide-risk-hold-v1/risk-hold.claim.json',
    'results/solar-decide-unsent-smoke-v2/manifest.json',
    'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/manifest.json',
    'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/terminal-public.json',
    'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/budget-solar-decide-upstage-p0-unsent-smoke-v2.jsonl',
)


def sha(path):
    return native.sha(Path(path).read_bytes())


def prior_outcomes(root):
    """Bind the failed first smoke and closed two-request continuation separately."""
    old, reconciliation = risk.historical()
    if (old.get('smoke_attempted') != ['DEV-001'] or
            old.get('smoke_never_sent') != ['DEV-002', 'DEV-003'] or
            old.get('http_status') != 429 or
            reconciliation.get('unknown_upper_bound_usd') != str(risk.OLD_UNKNOWN)):
        raise ValueError('Original Solar failed smoke changed')
    suffix.verify()
    suffix_run.verify()
    closed_path = suffix_run.BASE / 'terminal-public.json'
    closed = json.loads((root / closed_path.relative_to(ROOT)).read_text())
    child = suffix_run.CHILD
    if (closed.get('schema') != 'solar-decide-exact-unsent-p0-smoke-v2-terminal-public' or
            closed.get('status') != 'two_exact_unsent_requests_completed_child_sealed_master_reconciled' or
            closed.get('request_ids') != ['DEV-002', 'DEV-003'] or
            closed.get('http_statuses') != [200, 200] or
            closed.get('new_attempt_statuses') != ['ok', 'ok'] or
            closed.get('new_known_actual_usd') != '0.00073290' or
            closed.get('new_unknown_upper_bound_usd') != '0' or
            closed.get('historical_dev001_unknown_upper_bound_usd') != str(risk.OLD_UNKNOWN) or
            closed.get('separate_risk_hold_usd') != str(risk.CAP) or
            closed.get('plan_sha256') != sha(suffix.PLAN) or
            closed.get('execution_manifest_sha256') != sha(suffix_run.MANIFEST) or
            closed.get('child_sha256') != sha(child) or
            closed.get('historical_terminal_sha256') != sha(risk.OLD / 'terminal-public.json') or
            closed.get('risk_claim_sha256') != sha(risk.CLAIM)):
        raise ValueError('Closed Solar two-request continuation changed')
    events = suffix_run.jsonl(child)
    if ([event.get('event') for event in events] !=
            ['budget', 'reserve', 'settle', 'reserve', 'settle', 'partition_closed'] or
            [events[i].get('record_id') for i in (1, 3)] != ['DEV-002', 'DEV-003'] or
            sum((Decimal(events[i]['usd']) for i in (2, 4)), Decimal()) !=
            Decimal(closed['new_known_actual_usd'])):
        raise ValueError('Sealed Solar successor child changed')
    return closed


def build(root=ROOT):
    root = Path(root).resolve()
    if root != ROOT:
        # The frozen Solar builders use the project root for historical inputs.
        # A future relocation adapter must check the copied sources explicitly.
        raise ValueError('Solar plan build requires the frozen project checkout')
    prior = prior_outcomes(root)
    if BOUND != Decimal('0.10485760'):
        raise ValueError('Four-question Solar reserve changed')
    originals = solar.build_plans(root)
    selected = {}
    for condition in ('P0', 'P1', 'P2'):
        config = f'solar-decide-openrouter-upstage-native-{condition.lower()}-v1'
        phase = originals[config]
        if (phase.get('provider_tag') != 'upstage' or phase.get('model') != solar.MODEL or
                phase.get('condition') != condition or phase.get('request_count') != 60 or
                phase.get('reference_labels_read') is not False or
                phase.get('input_file_sha256') != sha(root / 'data/pilot/inputs.jsonl')):
            raise ValueError('Frozen Solar input-only condition differs')
        selected[condition] = phase
    phases = []
    for name in PHASES:
        condition = name.split('/')[1]
        original = selected[condition]
        requests = original['requests']
        if ([row['id'] for row in requests] != [f'DEV-{i:03}' for i in range(1, 61)] or
                native.sha(native.canonical(requests)) != original['requests_sha256'] or
                any(native.sha(native.canonical(row['payload'])) != row['payload_sha256']
                    for row in requests)):
            raise ValueError('Solar 60-request set differs')
        phases.append({'id': name, 'condition': condition,
                       'status': 'planned_not_admitted',
                       'smoke_ids': ['DEV-001', 'DEV-002', 'DEV-003'],
                       'development_request_count': 60,
                       'requests_sha256': original['requests_sha256'],
                       'requests': requests})
    sources = {name: sha(root / name) for name in SOURCE_PATHS}
    return {'schema': SCHEMA + '-plan', 'status': 'offline_unadmitted',
        'configuration_id': 'solar-decide-upstage-native-postinterruption-full-v1',
        'series_identity': 'New nine-phase series after the failed historical smoke and its exact-unsent continuation.',
        'historical_failed_smoke': {'attempted': ['DEV-001'], 'http_status': 429,
            'unknown_upper_bound_usd': str(risk.OLD_UNKNOWN),
            'terminal_sha256': sha(risk.OLD / 'terminal-public.json')},
        'historical_exact_unsent_continuation': {'attempted': ['DEV-002', 'DEV-003'],
            'known_actual_usd': prior['new_known_actual_usd'],
            'terminal_sha256': sha(suffix_run.BASE / 'terminal-public.json')},
        'historical_smoke_reused_as_passed_three_record_gate': False,
        'historical_dev001_retried': False,
        'new_series_fresh1_p0_dev001_is_distinct_declared_request': True,
        'model': solar.MODEL, 'expected_returned_model': solar.VERSION,
        'provider': solar.PROVIDER, 'provider_tag': 'upstage',
        'api_url': native.DECISIONS_URL,
        'interface': 'native Decisions with four Choice questions',
        'reference_labels_sent': False,
        'phase_order': list(PHASES), 'phase_count': 9,
        'new_smoke_stage_count': 9, 'development_stage_count': 9,
        'new_smoke_requests_per_stage': 3,
        'development_requests_per_stage': 60,
        'context_tokens_per_question': solar.CONTEXT,
        'max_aggregate_billable_input_tokens_per_request': 4 * solar.CONTEXT,
        'per_request_conservative_reserve_usd': str(BOUND),
        'new_smoke_reserve_per_stage_usd': str(3 * BOUND),
        'full_stage_upper_bound_usd': str(60 * BOUND),
        'all_stage_request_count_including_smokes': 9 * (3 + 60),
        'all_stage_unsettled_upper_bound_usd': str(9 * (3 + 60) * BOUND),
        'rolling_budget_note': 'A proposed $1 child cannot cover every worst-case request simultaneously. Each request must reserve the full four-question bound against remaining child capacity, settle observed cost, and stop if capacity is insufficient.',
        'context_limit_note': 'The catalog does not provide an exact all-record four-question token proof; a context rejection must be retained, never truncated or repaired.',
        'stage_policy': 'Every new phase has its own three-request smoke and root raw inspection before its 60-record development stage. Stop on provider, transport, unknown-cost, or context failure; retain intrinsic invalid outputs in the 60-position denominator.',
        'seed_policy': 'No seed control; provider randomness and cache behavior remain unknown.',
        'source_sha256': sources, 'phases': phases}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'plan_sha256': sha(PLAN),
        'controller_sha256': sha(__file__), 'phase_count': 9,
        'first_gate': 'fresh1/P0 new three-request smoke',
        'historical_failed_smoke_reused': False,
        'inference_authorized': False, 'allocation_authorized': False}


def prepare():
    if PLAN.exists() or REVIEW.exists():
        raise FileExistsError('Solar full plan already prepared')
    BASE.mkdir(parents=True, exist_ok=True)
    with PLAN.open('x') as out:
        json.dump(build(), out, indent=2, ensure_ascii=False); out.write('\n')
    with REVIEW.open('x') as out:
        json.dump(review_template(), out, indent=2, sort_keys=True); out.write('\n')
    return sha(PLAN)


def verify():
    if json.loads(PLAN.read_text()) != build():
        raise ValueError('Solar full plan or bound source differs')
    review = json.loads(REVIEW.read_text())
    pending = review_template()
    approved = dict(pending, approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if review not in (pending, approved):
        raise ValueError('Solar full offline root review differs')
    return sha(PLAN)


def require_review():
    verify()
    expected = dict(review_template(), approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent Solar full plan review missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'review-template'))
    action = parser.parse_args().action
    if action == 'prepare': print(prepare())
    elif action == 'verify': print(verify())
    else: print(json.dumps(review_template(), indent=2))


if __name__ == '__main__':
    main()
