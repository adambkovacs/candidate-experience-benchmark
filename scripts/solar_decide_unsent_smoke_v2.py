#!/usr/bin/env python3
"""Offline exact-unsent Solar P0 native Choice smoke proposal."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as native
import solar_decide_offline_plan as solar
import solar_decide_risk_hold_v1 as risk

BASE = ROOT / 'results/solar-decide-unsent-smoke-v2'
PLAN = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
OLD = ROOT / 'results/solar-decide-native-smoke-v1'
SCHEMA = 'solar-decide-exact-unsent-p0-smoke-v2'
BOUND = 4 * solar.CONTEXT * max(solar.PROMPT_RATE, solar.CACHE_RATE)
SOURCES = ('scripts/solar_decide_unsent_smoke_v2.py',
           'tests/test_solar_decide_unsent_smoke_v2.py',
           'scripts/solar_decide_risk_hold_v1.py',
           'results/solar-decide-risk-hold-v1/proposal.json',
           'docs/SOLAR_DECIDE_RESERVE_AUDIT_2026-10-06.md',
           'scripts/solar_decide_offline_plan.py',
           'scripts/solar_decide_smoke_v1.py',
           'results/solar-decide-native-smoke-v1/manifest.json',
           'results/solar-decide-native-smoke-v1/terminal-public.json',
           'results/solar-decide-native-smoke-v1/budget-reconciliation.json',
           'results/solar-decide-native-smoke-v1/budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl')


def sha(path):
    return native.sha(Path(path).read_bytes())


def manifest_value():
    risk.verify()
    terminal, reconciled = risk.historical()
    old = json.loads((OLD / 'manifest.json').read_text())
    if (old.get('kind') != 'solar-decide-openrouter-upstage-native-p0-smoke-v1' or
            old.get('smoke_ids') != ['DEV-001','DEV-002','DEV-003'] or
            len(old.get('requests', [])) != 3 or
            [row['id'] for row in old['requests']] != old['smoke_ids'] or
            old.get('model') != solar.MODEL or old.get('provider_tag') != 'upstage' or
            terminal['smoke_never_sent'] != ['DEV-002','DEV-003'] or
            reconciled['unknown_upper_bound_usd'] != str(risk.OLD_UNKNOWN) or
            BOUND != risk.FOUR_QUESTION_BOUND):
        raise ValueError('Solar exact-unsent predecessor or reserve differs')
    originals = old['requests'][1:]
    rows = solar.build_plans(ROOT)['solar-decide-openrouter-upstage-native-p0-v1']['requests'][1:3]
    if len(rows) != 2 or rows != originals or any(native.sha(native.canonical(x['payload'])) != x['payload_sha256']
                                               for x in originals):
        raise ValueError('Solar DEV-002/003 payloads differ from frozen P0')
    return {'schema': SCHEMA, 'status': 'offline_unadmitted',
        'configuration': 'upstage/solar-decide native Choice P0 exact-unsent continuation',
        'model': solar.MODEL, 'expected_returned_model': solar.VERSION,
        'provider': solar.PROVIDER, 'provider_tag': 'upstage',
        'api_url': native.DECISIONS_URL, 'question_count': 4,
        'original_unknown_id_not_replayed': 'DEV-001',
        'request_ids': ['DEV-002','DEV-003'], 'request_count': 2,
        'requests': originals, 'reference_labels_sent': False,
        'per_request_four_question_reserve_usd': str(BOUND),
        'two_request_reserve_usd': str(2*BOUND),
        'historical_unknown_usd_unchanged': str(risk.OLD_UNKNOWN),
        'separate_risk_hold_required_usd': str(risk.CAP),
        'risk_hold_partition_id': risk.PARTITION_ID,
        'new_partition_required': True, 'full_phase_score_authorized': False,
        'provider_failure_policy': 'Stop without retry; keep unknown cost and unsent positions distinct.',
        'source_sha256': {name: sha(ROOT / name) for name in SOURCES}}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'manifest_sha256': sha(PLAN),
            'controller_sha256': sha(__file__),
            'request_ids': ['DEV-002','DEV-003'],
            'two_request_reserve_usd': str(2*BOUND),
            'risk_hold_partition_id': risk.PARTITION_ID}


def prepare():
    if BASE.exists():
        raise FileExistsError('Solar exact-unsent proposal already exists')
    value = manifest_value()
    BASE.mkdir(parents=True)
    with PLAN.open('x') as out:
        json.dump(value, out, indent=2, sort_keys=True); out.write('\n')
    with REVIEW.open('x') as out:
        json.dump(review_template(), out, indent=2, sort_keys=True); out.write('\n')
    return sha(PLAN)


def verify():
    if json.loads(PLAN.read_text()) != manifest_value():
        raise ValueError('Solar exact-unsent proposal or source changed')
    return sha(PLAN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','verify','review-template'))
    action = parser.parse_args().action
    if action == 'prepare': print(prepare())
    elif action == 'verify': print(verify())
    else: print(json.dumps(review_template(), indent=2))


if __name__ == '__main__':
    main()
