#!/usr/bin/env python3
"""Offline nine-stage gate for Perplexity Decider; no allocation or inference."""

import argparse
import json
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as native
import perplexity_decider_plan_v1 as route


PLAN = route.BASE / 'full-plan.json'
STAGES = tuple(f'{fresh}/{condition}' for fresh in route.PASSES for condition in route.CONDITIONS)


def build(root=ROOT):
    root = Path(root)
    route_plan, route_sha = route.verify(root)
    model = route_plan['models']['decider']
    return {
        'schema': 'perplexity-decider-full-gate-v1',
        'status': 'prepared_not_admitted',
        'inference_performed': False,
        'allocation_performed': False,
        'reference_labels_read': False,
        'route_plan_sha256': route_sha,
        'runner_sha256': native.sha((root / 'scripts/perplexity_decider_full_plan_v1.py').read_bytes()),
        'model': model['model'],
        'provider': model['provider'],
        'expected_returned_model': model['expected_returned_model'],
        'stages': list(STAGES),
        'development_ids': list(route.IDS),
        'smoke_ids': list(route.SMOKE_IDS),
        'requests_sha256': {condition: native.sha(native.canonical(model['requests'][condition]))
                            for condition in route.CONDITIONS},
        'per_request_four_context_bound_usd': str(route.bound('decider', 1)),
        'proposed_development_child_usd': '0.75',
        'proposed_child_status': 'proposal_only_no_allocation',
        'budget_gate': 'Use the existing $22.38 OpenRouter ceiling. Reserve one request at a time and settle actual cost. Stop when the next full reserve cannot fit; retain unknown holds.',
        'stage_gate': 'Each 60-review stage requires its own closed three-review smoke, saved raw answers, independent inspection and a root admission before development dispatch.',
        'replay_policy': 'Never replay a dispatched review; preserve invalid, failed, unknown and unsent positions.',
        'development_runner_status': 'not_prepared_no_dispatch',
    }


def verify(root=ROOT):
    root = Path(root)
    expected = build(root)
    if json.loads((root / PLAN).read_text()) != expected:
        raise ValueError('Perplexity full plan or source changed')
    return expected, native.sha(native.canonical(expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check'))
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    value = build(args.root)
    target = args.root / PLAN
    if args.action == 'write':
        with target.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(target.read_text()) != value:
        raise SystemExit('Perplexity full plan changed')
    print(native.sha(native.canonical(value)))


if __name__ == '__main__':
    main()
