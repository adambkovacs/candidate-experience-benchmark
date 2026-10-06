#!/usr/bin/env python3
"""Exact DEV-002–060 continuation of interrupted Clef fresh1/P2 development.

The frozen request loop remains unchanged. This version only narrows its input
slice, gives the suffix a new output directory and authority identity, and
binds the stopped parent. It never replays DEV-001.
"""

import argparse
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import threading

import clef_cloudflare_authority_v1 as historical
import clef_native_preparation as prep
import clef_native_remaining as frozen
import clef_native_remaining_cloudflare_v1 as prior
import clef_native_remaining_cloudflare_v2 as inventory
import clef_native_smoke_runner as smoke

ROOT = prep.ROOT
BASE = prior.BASE / 'exact-unsent-v1'
PLAN = BASE / 'plan.json'
GRANT_KIND = 'clef-native-p2-exact-unsent-v1-grant'
KIND = 'clef-native-p2-exact-unsent-v1'
PARENT = frozen.BASE / 'clef/fresh1/P2/development'
SMOKE_REVIEW = prior.BASE / 'fresh1-p2-smoke-review.json'
IDS = prep.IDS[1:]
HOLD_ID = 'cloudflare-only-clef-fresh1-p2-development-exact-unsent-v1'
SOURCE_FILES = (
    'scripts/clef_native_p2_exact_unsent_v1.py',
    'scripts/clef_native_remaining.py',
    'scripts/clef_native_remaining_cloudflare_v1.py',
    'scripts/clef_native_remaining_cloudflare_v2.py',
    'scripts/clef_cloudflare_authority_v1.py',
    'scripts/clef_cloudflare_operator_v1.py',
    'scripts/clef_cloudflare_dispatcher_v1.js',
    'scripts/clef_native_preparation.py',
    'scripts/clef_connected_app_bridge.py',
    'scripts/clef_native_smoke_runner.py',
)
PARENT_FILES = ('claim.json', 'budget.jsonl', 'journal.jsonl', 'raw.jsonl',
                'records.jsonl', 'completion.json')
_LOCK = threading.Lock()


def digest(path):
    return historical.sha(Path(path).read_bytes())


def parent_bindings():
    completion = json.loads((PARENT / 'completion.json').read_bytes())
    expected = {'valid': 0, 'invalid_output': 0, 'service_error': 0,
                'unknown_outcome': 1}
    if (completion.get('kind') != 'clef-native-remaining-completion-v1' or
            completion.get('model') != 'clef' or
            completion.get('stage') != 'clef/fresh1/P2/development' or
            completion.get('status') != 'stopped' or
            completion.get('attempted') != 1 or completion.get('counts') != expected or
            completion.get('never_sent') != list(IDS) or
            completion.get('unknown_cost_reserved_usd') != str(prep.reservation_usd('clef', 1))):
        raise ValueError('Parent stage is not exact one-unknown interruption')
    bindings = {str((PARENT / name).relative_to(ROOT)): digest(PARENT / name)
                for name in PARENT_FILES}
    for name, key in [('claim.json', 'claim_sha256'), ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'), ('records.jsonl', 'records_sha256')]:
        if bindings[str((PARENT / name).relative_to(ROOT))] != completion[key]:
            raise ValueError('Interrupted parent file changed')
    claim = json.loads((PARENT / 'claim.json').read_bytes())
    budget = historical.rows(PARENT / 'budget.jsonl')
    journal = historical.rows(PARENT / 'journal.jsonl')
    raw = historical.rows(PARENT / 'raw.jsonl')
    records = historical.rows(PARENT / 'records.jsonl')
    old_manifest_hash = digest(frozen.MANIFEST)
    first_request = frozen.read_json(frozen.MANIFEST)['stages']['clef/fresh1/P2']['requests'][0]
    if (claim.get('manifest_sha256') != old_manifest_hash or
            claim.get('grant_sha256') != digest(prior.BASE / 'fresh1-p2-development-grant.json') or
            claim.get('global_authority_hold_usd') != str(prep.reservation_usd('clef', 60)) or
            len(budget) != 2 or budget[1].get('event') != 'reserve' or
            budget[1].get('id') != 'DEV-001' or
            len(journal) != 3 or [x.get('event') for x in journal] !=
            ['reserved', 'started', 'finished'] or
            len(raw) != 1 or len(records) != 1 or
            raw[0].get('id') != 'DEV-001' or
            raw[0].get('request_sha256') != first_request['payload_sha256'] or
            raw[0].get('http_status') is not None or
            raw[0].get('error_type') != 'TimeoutError' or
            raw[0].get('raw_response_base64') != '' or
            records[0].get('status') != 'unknown_outcome' or
            records[0].get('id') != 'DEV-001' or
            records[0].get('request_sha256') != first_request['payload_sha256'] or
            len({x['attempt_id'] for x in [budget[1], *journal, *raw, *records]}) != 1):
        raise ValueError('Interrupted parent attempt differs')
    return bindings


def plan_value():
    inventory.verify()
    bindings = parent_bindings()
    manifest, manifest_hash = frozen.checked_manifest(frozen.MANIFEST)
    rows, policy = prep.inputs_and_policy()
    requests = manifest['stages']['clef/fresh1/P2']['requests'][1:]
    if ([x['id'] for x in requests] != list(IDS) or
            any(x['input_sha256'] != prep.sha(row['feedback'].encode()) or
                x['payload_sha256'] != prep.sha(prep.canonical(
                    prep.request_payload(row['feedback'], policy, 'clef', 'P2')))
                for x, row in zip(requests, rows[1:]))):
        raise ValueError('Never-sent suffix differs from frozen request bytes')
    return {'kind': KIND, 'status': 'offline_no_allocation_no_inference',
            'model': 'clef', 'pass': 'fresh1', 'condition': 'P2',
            'phase': 'development-exact-unsent-v1', 'request_ids': list(IDS),
            'requests': requests, 'parent_file_bindings': bindings,
            'frozen_manifest_sha256': manifest_hash,
            'smoke_review_sha256': digest(SMOKE_REVIEW),
            'inventory_bridge_review_sha256': digest(inventory.REVIEW),
            'source_bindings': {name: digest(ROOT / name) for name in SOURCE_FILES},
            'authority_hold_id': HOLD_ID,
            'authority_hold_usd': str(prep.reservation_usd('clef', len(IDS))),
            'reference_labels_sent': False,
            'transport': 'mcp__codex_apps__cloudflare_execute'}


def checked_plan(path=PLAN):
    saved = json.loads(Path(path).read_bytes())
    if saved != plan_value():
        raise ValueError('Exact unsent Clef plan differs')
    return saved, digest(path)


class SuffixAuthority(prior.AuthorityLedger):
    def hold(self, model, repeat, condition, phase, grant_hash):
        if (model, repeat, condition, phase) != ('clef', 'fresh1', 'P2', 'development'):
            raise ValueError('Unapproved Clef suffix identity')
        amount = prep.reservation_usd('clef', len(IDS))
        if HOLD_ID in self.ids or self.total + amount > prior.CAP:
            raise ValueError('Duplicate suffix or Cloudflare $10 cap exhausted')
        smoke.durable(self.stream, {'event': 'hold', 'id': HOLD_ID,
                                    'usd': str(amount), 'grant_sha256': grant_hash})
        self.ids.add(HOLD_ID)
        self.total += amount


def checked_suffix_grant(path, *, model, repeat, condition, phase, manifest_hash,
                         account_id, wait_seconds, smoke_review_hash,
                         prior_completion_hash, billing_fetcher=smoke.billing_fetch,
                         plan_pair=None):
    plan, plan_hash = plan_pair or checked_plan()
    grant = json.loads(Path(path).read_bytes())
    expected = grant_value(account_id, grant.get('global_authority_ledger_sha256_at_admission'),
                           wait_seconds, plan_pair=(plan, plan_hash))
    if ((model, repeat, condition, phase) != ('clef', 'fresh1', 'P2', 'development') or
            manifest_hash != plan_hash or prior_completion_hash is not None or
            smoke_review_hash != plan['smoke_review_sha256'] or
            grant != expected or
            prep.sha(billing_fetcher(prep.MODELS['clef']['source'])) !=
            expected['billing_source_sha256']):
        raise ValueError('Exact reviewed Clef suffix grant required')
    return grant, digest(path)


def grant_value(account_id, authority_head, wait_seconds=300, *, plan_pair=None):
    plan, plan_hash = plan_pair or checked_plan()
    if (not isinstance(authority_head, str) or len(authority_head) != 64 or
            type(wait_seconds) is not int or not 1 <= wait_seconds <= 600):
        raise ValueError('Exact successor authority head and wait required')
    return {'kind': GRANT_KIND, 'approved': True, 'reviewer': '/root',
                'authorized_by_user': True, 'model': 'clef', 'pass': 'fresh1',
                'condition': 'P2', 'phase': 'development',
                'stage': 'clef/fresh1/P2/development-exact-unsent-v1',
                'plan_sha256': plan_hash,
                'controller_sha256': digest(__file__),
                'frozen_manifest_sha256': plan['frozen_manifest_sha256'],
                'parent_completion_sha256': plan['parent_file_bindings'][str(
                    (PARENT / 'completion.json').relative_to(ROOT))],
                'account_id_sha256': prep.sha(account_id.encode('ascii')),
                'transport': 'mcp__codex_apps__cloudflare_execute',
                'authority_hold_id': HOLD_ID,
                'full_context_hold_usd': plan['authority_hold_usd'],
                'global_authority_cap_usd': str(prior.CAP),
                'smoke_review_sha256': plan['smoke_review_sha256'],
                'prior_completion_sha256': None,
                'exhaustion_policy': 'pause', 'wait_seconds': wait_seconds,
                'billing_source_sha256': frozen.read_json(frozen.PROPOSAL)
                    ['published_rate_sources']['clef']['sha256'],
                'global_authority_ledger_sha256_at_admission': authority_head}


@contextmanager
def suffix_bindings():
    old_ids, old_rows = prep.IDS, prep.inputs_and_policy
    old_manifest = frozen.checked_manifest
    old_review = frozen.checked_smoke_review
    old_grant = frozen.checked_grant
    old_authority = frozen.AuthorityLedger
    plan, plan_hash = checked_plan()
    manifest, _ = old_manifest(frozen.MANIFEST)
    sliced = json.loads(json.dumps(manifest))
    sliced['stages']['clef/fresh1/P2']['requests'] = plan['requests']
    rows, policy = old_rows()
    def manifest_check(path, *, root=ROOT, proposal_path=frozen.PROPOSAL):
        if Path(path) != frozen.MANIFEST or Path(root) != ROOT or Path(proposal_path) != frozen.PROPOSAL:
            raise ValueError('Changed Clef suffix manifest source')
        return sliced, plan_hash
    def rows_check(root=ROOT):
        if Path(root) != ROOT:
            raise ValueError('Changed Clef suffix input root')
        return rows[1:], policy
    def review_check(path, *, model, repeat, condition, manifest_hash, account_id, base):
        if manifest_hash != plan_hash or Path(path) != SMOKE_REVIEW:
            raise ValueError('Changed predecessor smoke review')
        return old_review(path, model=model, repeat=repeat, condition=condition,
                          manifest_hash=plan['frozen_manifest_sha256'],
                          account_id=account_id, base=frozen.BASE)
    def grant_check(path, **kwargs):
        return checked_suffix_grant(path, plan_pair=(plan, plan_hash), **kwargs)
    class BoundSuffixAuthority(SuffixAuthority):
        def __init__(self, *args):
            # Frozen authority revalidates the old 27-stage plan. Restore its
            # original input view solely for that read-only validation.
            current_ids, current_rows = prep.IDS, prep.inputs_and_policy
            current_manifest = frozen.checked_manifest
            prep.IDS, prep.inputs_and_policy = old_ids, old_rows
            frozen.checked_manifest = old_manifest
            try:
                super().__init__(*args)
            finally:
                prep.IDS, prep.inputs_and_policy = current_ids, current_rows
                frozen.checked_manifest = current_manifest
    prep.IDS = IDS
    prep.inputs_and_policy = rows_check
    frozen.checked_manifest = manifest_check
    frozen.checked_smoke_review = review_check
    frozen.checked_grant = grant_check
    frozen.AuthorityLedger = BoundSuffixAuthority
    try:
        yield
    finally:
        prep.IDS, prep.inputs_and_policy = old_ids, old_rows
        frozen.checked_manifest = old_manifest
        frozen.checked_smoke_review = old_review
        frozen.checked_grant = old_grant
        frozen.AuthorityLedger = old_authority


def run(grant_path, *, authority_path=prior.LEDGER, base=BASE, environment=None,
        transport=None, billing_source=None, wait_seconds=300):
    with _LOCK, inventory.historical_inventory(), suffix_bindings():
        return frozen.run_stage('clef', 'fresh1', 'P2', 'development', frozen.MANIFEST,
                                grant_path, base=base, authority_path=authority_path,
                                environment=environment, transport=transport,
                                billing_source=billing_source,
                                smoke_review_path=SMOKE_REVIEW,
                                wait_seconds=wait_seconds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'verify'))
    args = parser.parse_args()
    if args.command == 'prepare':
        if PLAN.exists():
            raise ValueError('Exact unsent plan already exists')
        BASE.mkdir(parents=True, exist_ok=True)
        PLAN.write_text(json.dumps(plan_value(), sort_keys=True, indent=2) + '\n')
    print(checked_plan()[1])


if __name__ == '__main__':
    main()
