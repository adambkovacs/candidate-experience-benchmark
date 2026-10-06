#!/usr/bin/env python3
"""Cloudflare-only admission adapter for the five never-sent Clef stages.

The old request loop, payloads, response capture, and connected-app handoff
remain frozen. This adapter changes only the reviewed authority and grant gate.
"""

import argparse
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import threading

import clef_cloudflare_authority_v1 as historical
import clef_native_remaining as frozen
import clef_native_preparation as prep
import clef_native_smoke_runner as smoke
import clef_connected_app_bridge as bridge

ROOT = prep.ROOT
BASE = ROOT / 'results/clef-native-v1/cloudflare-budget-v1'
PLAN = BASE / 'remaining-clef-plan.json'
LEDGER = BASE / 'authority.jsonl'
HISTORICAL = historical.RECEIPT
KIND = 'clef-cloudflare-remaining-adapter-v1'
LEDGER_KIND = 'clef-cloudflare-authority-v1'
CAP = Decimal('10.00')
ALLOWED = tuple(f'clef/{repeat}/{condition}' for repeat, condition in (
    ('fresh1', 'P2'), ('fresh2', 'P1'), ('fresh2', 'P2'),
    ('fresh3', 'P1'), ('fresh3', 'P2')))
SOURCE_FILES = (
    'scripts/clef_native_remaining_cloudflare_v1.py',
    'scripts/clef_native_remaining.py',
    'scripts/clef_native_preparation.py',
    'scripts/clef_native_smoke_runner.py',
    'scripts/clef_connected_app_bridge.py',
    'scripts/development_benchmark.py',
    'scripts/jev_benchmark.py',
    'scripts/jev_native_prompt_variants_v1.py',
)
_RUN_LOCK = threading.Lock()


def digest(path):
    return historical.sha(Path(path).read_bytes())


def plan_value(root=ROOT):
    root = Path(root)
    receipt = json.loads((root / HISTORICAL.relative_to(ROOT)).read_bytes())
    if receipt != historical.audit(root) or receipt['total_upper_bound_usd'] != '0.259584':
        raise ValueError('Historical Clef upper bound changed')
    manifest, manifest_hash = frozen.checked_manifest(
        root / frozen.MANIFEST.relative_to(ROOT), root=root,
        proposal_path=root / frozen.PROPOSAL.relative_to(ROOT))
    if set(ALLOWED) - set(manifest['stages']):
        raise ValueError('Never-sent Clef stages absent from frozen manifest')
    return {'kind': KIND, 'status': 'offline_no_allocation_no_inference',
            'cap_usd': str(CAP), 'historical_upper_bound_usd': receipt['total_upper_bound_usd'],
            'historical_receipt_sha256': digest(root / HISTORICAL.relative_to(ROOT)),
            'frozen_manifest_sha256': manifest_hash,
            'allowed_stages': list(ALLOWED),
            'source_bindings': {name: digest(root / name) for name in SOURCE_FILES},
            'reference_labels_sent': False,
            'transport': 'mcp__codex_apps__cloudflare_execute'}


def checked_plan(path=PLAN, *, root=ROOT):
    raw = Path(path).read_bytes()
    saved = json.loads(raw)
    if saved != plan_value(root):
        raise ValueError('Reviewed Cloudflare Clef plan differs')
    return saved, historical.sha(raw)


def initial_header(plan_hash, review_hash):
    receipt = json.loads(HISTORICAL.read_bytes())
    return {'event': 'budget', 'kind': LEDGER_KIND, 'cap_usd': str(CAP),
            'historical_upper_bound_usd': receipt['total_upper_bound_usd'],
            'historical_receipt_sha256': digest(HISTORICAL),
            'plan_sha256': plan_hash, 'initialization_review_sha256': review_hash}


def initialize(review_path, *, path=LEDGER, plan_path=PLAN):
    _, plan_hash = checked_plan(plan_path)
    raw = Path(review_path).read_bytes()
    review = json.loads(raw)
    if (review != {'kind': LEDGER_KIND + '-initialization-review',
                   'approved': True, 'reviewer': '/root',
                   'cap_usd': str(CAP), 'plan_sha256': plan_hash,
                   'historical_receipt_sha256': digest(HISTORICAL)}):
        raise ValueError('Exact reviewed Cloudflare initialization required')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        smoke.durable(stream, initial_header(plan_hash, historical.sha(raw)))
    return digest(path)


class AuthorityLedger:
    """Single Cloudflare cap, locked across concurrent admission processes."""

    def __init__(self, path, _old_snapshot, expected_head):
        self.path = Path(path)
        self.stream = self.path.open('r+b')
        try:
            fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.stream.seek(0)
            raw = self.stream.read()
            if historical.sha(raw) != expected_head:
                raise ValueError('Cloudflare authority head changed')
            events = historical.rows(self.path)
            _, plan_hash = checked_plan()
            header = events[0]
            if (header.get('event') != 'budget' or header.get('kind') != LEDGER_KIND or
                    header.get('cap_usd') != str(CAP) or
                    header.get('historical_upper_bound_usd') != '0.259584' or
                    header.get('historical_receipt_sha256') != digest(HISTORICAL) or
                    header.get('plan_sha256') != plan_hash or
                    not isinstance(header.get('initialization_review_sha256'), str) or
                    len(header['initialization_review_sha256']) != 64 or len(events) < 1):
                raise ValueError('Wrong Cloudflare-only authority header')
            self.ids = set()
            self.total = historical.money(header['historical_upper_bound_usd'])
            for event in events[1:]:
                if (set(event) != {'event', 'id', 'usd', 'grant_sha256'} or
                        event['event'] != 'hold' or event['id'] in self.ids or
                        not isinstance(event['grant_sha256'], str) or
                        len(event['grant_sha256']) != 64):
                    raise ValueError('Malformed or duplicate Cloudflare hold')
                self.ids.add(event['id'])
                self.total += historical.money(event['usd'])
            if self.total > CAP:
                raise ValueError('Cloudflare $10 cap exhausted')
            self.stream.seek(0, os.SEEK_END)
        except BaseException:
            self.stream.close()
            raise

    def hold(self, model, repeat, condition, phase, grant_hash):
        stage = f'{model}/{repeat}/{condition}'
        if stage not in ALLOWED or phase not in ('smoke', 'development'):
            raise ValueError('Unapproved Cloudflare Clef stage')
        identity = f'cloudflare-only-{model}-{repeat}-{condition.lower()}-{phase}'
        amount = prep.reservation_usd(model, 3 if phase == 'smoke' else 60)
        if identity in self.ids or self.total + amount > CAP:
            raise ValueError('Duplicate stage or Cloudflare $10 cap exhausted')
        smoke.durable(self.stream, {'event': 'hold', 'id': identity,
                                    'usd': str(amount), 'grant_sha256': grant_hash})
        self.ids.add(identity)
        self.total += amount

    def close(self):
        self.stream.close()


def checked_grant(path, *, model, repeat, condition, phase, manifest_hash,
                  account_id, wait_seconds, smoke_review_hash,
                  prior_completion_hash, billing_fetcher=smoke.billing_fetch):
    _, plan_hash = checked_plan()
    if f'{model}/{repeat}/{condition}' not in ALLOWED:
        raise ValueError('Stage not in Cloudflare-only plan')
    raw = Path(path).read_bytes()
    grant = json.loads(raw)
    expected = {'kind': KIND + '-stage-grant', 'approved': True,
                'authorized_by_user': True, 'reviewer': '/root',
                'model': model, 'pass': repeat, 'condition': condition,
                'phase': phase, 'stage': f'{model}/{repeat}/{condition}/{phase}',
                'plan_sha256': plan_hash, 'frozen_manifest_sha256': manifest_hash,
                'historical_receipt_sha256': digest(HISTORICAL),
                'controller_sha256': digest(__file__),
                'account_id_sha256': prep.sha(account_id.encode('ascii')),
                'transport': 'mcp__codex_apps__cloudflare_execute',
                'full_context_hold_usd': str(prep.reservation_usd(model, 3 if phase == 'smoke' else 60)),
                'global_authority_cap_usd': str(CAP),
                'smoke_review_sha256': smoke_review_hash,
                'prior_completion_sha256': prior_completion_hash,
                'exhaustion_policy': 'pause', 'wait_seconds': wait_seconds,
                'billing_source_sha256': frozen.read_json(frozen.PROPOSAL)['published_rate_sources'][model]['sha256']}
    if (not isinstance(grant, dict) or set(grant) != set(expected) |
            {'global_authority_ledger_sha256_at_admission'} or
            any(grant.get(k) != value for k, value in expected.items()) or
            not isinstance(grant.get('global_authority_ledger_sha256_at_admission'), str) or
            len(grant['global_authority_ledger_sha256_at_admission']) != 64):
        raise ValueError('Exact reviewed Cloudflare-only stage grant required')
    if prep.sha(billing_fetcher(prep.MODELS[model]['source'])) != grant['billing_source_sha256']:
        raise ValueError('Frozen model billing source changed')
    return grant, historical.sha(raw)


def run_stage(model, repeat, condition, phase, grant_path, *,
              plan_path=PLAN, authority_path=LEDGER, **options):
    checked_plan(plan_path)
    if f'{model}/{repeat}/{condition}' not in ALLOWED:
        raise ValueError('Previously completed or unplanned Clef stage')
    # The frozen controller retains exact request construction, stage evidence,
    # smoke inspection, and the durable connected-app response handoff.
    with _RUN_LOCK:
        prior_authority, prior_grant = frozen.AuthorityLedger, frozen.checked_grant
        frozen.AuthorityLedger, frozen.checked_grant = AuthorityLedger, checked_grant
        try:
            return frozen.run_stage(model, repeat, condition, phase,
                                    frozen.MANIFEST, grant_path,
                                    authority_path=authority_path, **options)
        finally:
            frozen.AuthorityLedger, frozen.checked_grant = prior_authority, prior_grant


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'verify', 'initialize', 'run'))
    parser.add_argument('--review', type=Path)
    parser.add_argument('--model', default='clef')
    parser.add_argument('--pass', dest='repeat')
    parser.add_argument('--condition')
    parser.add_argument('--phase')
    parser.add_argument('--grant', type=Path)
    parser.add_argument('--smoke-review', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        if PLAN.exists():
            raise ValueError('Cloudflare plan already exists')
        PLAN.write_text(json.dumps(plan_value(), indent=2, sort_keys=True) + '\n')
        print(digest(PLAN))
    elif args.command == 'verify':
        print(checked_plan()[1])
    elif args.command == 'initialize':
        if args.review is None:
            raise ValueError('Initialization review required')
        print(initialize(args.review))
    else:
        if None in (args.repeat, args.condition, args.phase, args.grant):
            raise ValueError('Exact stage and grant required')
        print(json.dumps(run_stage(args.model, args.repeat, args.condition,
                                   args.phase, args.grant,
                                   env_file=args.env_file,
                                   smoke_review_path=args.smoke_review), indent=2))


if __name__ == '__main__':
    main()
