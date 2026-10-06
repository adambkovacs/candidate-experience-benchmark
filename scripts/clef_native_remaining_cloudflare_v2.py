#!/usr/bin/env python3
"""Post-smoke historical inventory bridge for the reviewed Clef controller.

Only the historical stage discovery changes: exact historical evidence remains
verified by the frozen auditor, while declared new completions may coexist.
"""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import threading

import clef_cloudflare_authority_v1 as historical
import clef_native_remaining_cloudflare_v1 as prior

ROOT = prior.ROOT
BASE = prior.BASE
REVIEW = BASE / 'historical-inventory-bridge-review.json'
KIND = 'clef-cloudflare-historical-inventory-bridge-v2'
_LOCK = threading.Lock()


def inventory_paths(base):
    """Allow only declared later completions beside exact historical stages."""
    base = Path(base)
    receipt = json.loads(prior.HISTORICAL.read_bytes())
    historical_paths = {base / stage['stage'] for stage in receipt['stages']}
    new_paths = {base / identity / phase for identity in prior.ALLOWED
                 for phase in ('smoke', 'development')}
    actual = {p.parent for p in base.glob('*/fresh*/P*/*/completion.json')}
    if not historical_paths <= actual or not actual <= historical_paths | new_paths:
        raise ValueError('Historical or declared Clef completion inventory changed')
    return sorted(historical_paths)


@contextmanager
def historical_inventory():
    previous = historical.stage_paths
    historical.stage_paths = inventory_paths
    try:
        yield
    finally:
        historical.stage_paths = previous


def review_value():
    return {'kind': KIND, 'approved': True, 'reviewer': '/root',
            'historical_receipt_sha256': prior.digest(prior.HISTORICAL),
            'frozen_plan_sha256': prior.digest(prior.PLAN),
            'frozen_controller_sha256': prior.digest(prior.__file__),
            'bridge_sha256': prior.digest(__file__),
            'allowed_new_stages': list(prior.ALLOWED),
            'scope': 'historical_inventory_only_no_request_or_budget_change'}


def verify(review_path=REVIEW):
    if json.loads(Path(review_path).read_bytes()) != review_value():
        raise ValueError('Exact root-reviewed inventory bridge required')
    with _LOCK, historical_inventory():
        prior.checked_plan()
    return prior.digest(review_path)


def run_stage(model, repeat, condition, phase, grant_path, *, review_path=REVIEW,
              **options):
    if json.loads(Path(review_path).read_bytes()) != review_value():
        raise ValueError('Exact root-reviewed inventory bridge required')
    with _LOCK, historical_inventory():
        prior.checked_plan()
        return prior.run_stage(model, repeat, condition, phase, grant_path, **options)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('verify', 'run'))
    parser.add_argument('--model', default='clef')
    parser.add_argument('--pass', dest='repeat')
    parser.add_argument('--condition')
    parser.add_argument('--phase')
    parser.add_argument('--grant', type=Path)
    parser.add_argument('--smoke-review', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        print(verify())
    else:
        if None in (args.repeat, args.condition, args.phase, args.grant):
            raise ValueError('Exact stage and grant required')
        print(json.dumps(run_stage(args.model, args.repeat, args.condition,
                                   args.phase, args.grant,
                                   smoke_review_path=args.smoke_review,
                                   env_file=args.env_file), indent=2))


if __name__ == '__main__':
    main()
