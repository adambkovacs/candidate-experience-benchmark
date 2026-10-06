#!/usr/bin/env python3
"""Reviewed Clef P2 predecessor from one unknown parent and 59 valid suffixes.

This bridge verifies saved evidence only. It changes the frozen predecessor
lookup for the exact fresh2/P2 call; request bytes, grants, budget and dispatch
remain under the existing Cloudflare controller.
"""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import threading

import clef_native_p2_exact_unsent_v1 as suffix
import clef_native_preparation as prep
import clef_native_remaining as frozen
import clef_native_remaining_cloudflare_v1 as authority
import clef_native_remaining_cloudflare_v2 as inventory

ROOT = prep.ROOT
SUFFIX_DIR = suffix.BASE / 'clef/fresh1/P2/development'
PLAN = suffix.PLAN
GRANT = suffix.BASE / 'grant.json'
AUTHORITY_SNAPSHOT = suffix.BASE / 'authority-after-completion.jsonl'
REVIEW = suffix.BASE / 'composite-predecessor-review-v1.json'
FILES = ('claim.json', 'budget.jsonl', 'journal.jsonl', 'raw.jsonl',
         'records.jsonl', 'completion.json')
KIND = 'clef-native-p2-composite-predecessor-review-v1'
_LOCK = threading.Lock()


def digest(path):
    return prep.sha(Path(path).read_bytes())


def rows(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines()]


def coverage(parent_records, suffix_records, requests):
    """Keep DEV-001 unknown and never mistake the successor for a clean pass."""
    parent_ids = [record.get('id') for record in parent_records]
    suffix_ids = [record.get('id') for record in suffix_records]
    expected_suffix = list(prep.IDS[1:])
    if (parent_ids != ['DEV-001'] or
            parent_records[0].get('status') != 'unknown_outcome' or
            parent_records[0].get('reference_labels_read') is not False or
            suffix_ids != expected_suffix or
            [request.get('id') for request in requests] != expected_suffix or
            any(record.get('status') != 'valid' or
                record.get('reference_labels_read') is not False or
                record.get('request_sha256') != request['payload_sha256']
                for record, request in zip(suffix_records, requests)) or
            len(set(parent_ids + suffix_ids)) != 60 or
            set(parent_ids + suffix_ids) != set(prep.IDS)):
        raise ValueError('Clef composite coverage is not one unknown plus exact 59 valid')
    return {'ordered_ids': list(prep.IDS), 'unknown_ids': ['DEV-001'],
            'valid_ids': expected_suffix, 'valid': 59, 'unknown_outcome': 1,
            'invalid_output': 0, 'service_error': 0,
            'status': 'closed_composite_not_clean'}


def value():
    plan, plan_hash = suffix.checked_plan()
    parent_bindings = suffix.parent_bindings()
    completion = json.loads((SUFFIX_DIR / 'completion.json').read_bytes())
    expected_counts = {'valid': 59, 'invalid_output': 0,
                       'service_error': 0, 'unknown_outcome': 0}
    if (completion.get('kind') != 'clef-native-remaining-completion-v1' or
            completion.get('model') != 'clef' or
            completion.get('stage') != 'clef/fresh1/P2/development' or
            completion.get('status') != 'complete' or
            completion.get('attempted') != 59 or
            completion.get('counts') != expected_counts or
            completion.get('never_sent') != [] or
            completion.get('unknown_cost_reserved_usd') != plan['authority_hold_usd']):
        raise ValueError('Exact Clef suffix is not complete')
    suffix_bindings = {str((SUFFIX_DIR / name).relative_to(ROOT)): digest(SUFFIX_DIR / name)
                       for name in FILES}
    for name, key in (('claim.json', 'claim_sha256'),
                      ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'),
                      ('records.jsonl', 'records_sha256')):
        if suffix_bindings[str((SUFFIX_DIR / name).relative_to(ROOT))] != completion.get(key):
            raise ValueError('Clef suffix completion binding differs')
    grant = json.loads(GRANT.read_bytes())
    claim = json.loads((SUFFIX_DIR / 'claim.json').read_bytes())
    parent_claim = json.loads((suffix.PARENT / 'claim.json').read_bytes())
    account_hash = claim.get('account_id_sha256')
    if (claim.get('kind') != 'clef-native-remaining-claim-v1' or
            claim.get('model') != 'clef' or
            claim.get('stage') != 'clef/fresh1/P2/development' or
            claim.get('manifest_sha256') != plan_hash or
            claim.get('grant_sha256') != digest(GRANT) or
            claim.get('controller_sha256') != digest(frozen.__file__) or
            claim.get('prior_completion_sha256') is not None or
            claim.get('global_authority_hold_usd') != plan['authority_hold_usd'] or
            not isinstance(account_hash, str) or len(account_hash) != 64 or
            any(char not in '0123456789abcdef' for char in account_hash) or
            account_hash != grant.get('account_id_sha256') or
            account_hash != parent_claim.get('account_id_sha256') or
            grant.get('kind') != suffix.GRANT_KIND or
            grant.get('approved') is not True or
            grant.get('authorized_by_user') is not True or
            grant.get('reviewer') != '/root' or
            grant.get('stage') != 'clef/fresh1/P2/development-exact-unsent-v1' or
            grant.get('plan_sha256') != plan_hash or
            grant.get('controller_sha256') != digest(suffix.__file__) or
            grant.get('frozen_manifest_sha256') != plan['frozen_manifest_sha256'] or
            grant.get('transport') != 'mcp__codex_apps__cloudflare_execute' or
            grant.get('global_authority_cap_usd') != str(authority.CAP) or
            grant.get('authority_hold_id') != suffix.HOLD_ID or
            grant.get('full_context_hold_usd') != plan['authority_hold_usd'] or
            grant.get('parent_completion_sha256') != parent_bindings[str(
                (suffix.PARENT / 'completion.json').relative_to(ROOT))]):
        raise ValueError('Clef suffix claim or grant differs')
    parent_records = rows(suffix.PARENT / 'records.jsonl')
    suffix_records = rows(SUFFIX_DIR / 'records.jsonl')
    suffix_raw = rows(SUFFIX_DIR / 'raw.jsonl')
    suffix_budget = rows(SUFFIX_DIR / 'budget.jsonl')
    suffix_journal = rows(SUFFIX_DIR / 'journal.jsonl')
    result = coverage(parent_records, suffix_records, plan['requests'])
    if (len(suffix_raw) != 59 or
            len(suffix_budget) != 60 or
            suffix_budget[0].get('event') != 'budget' or
            suffix_budget[0].get('manifest_sha256') != plan_hash or
            suffix_budget[0].get('grant_sha256') != digest(GRANT) or
            [event.get('id') for event in suffix_budget[1:]] != result['valid_ids'] or
            any(event.get('event') != 'reserve' or
                event.get('usd') != str(prep.reservation_usd('clef', 1)) or
                event.get('attempt_id') != record.get('attempt_id')
                for event, record in zip(suffix_budget[1:], suffix_records)) or
            len(suffix_journal) != 177 or
            any([event.get('event') for event in suffix_journal[index*3:index*3+3]] !=
                ['reserved', 'started', 'finished'] or
                any(event.get('id') != record.get('id') or
                    event.get('attempt_id') != record.get('attempt_id')
                    for event in suffix_journal[index*3:index*3+3])
                or suffix_journal[index*3].get('request_sha256') != record.get('request_sha256')
                or suffix_journal[index*3+2].get('status') != 'valid'
                for index, record in enumerate(suffix_records)) or
            [record.get('id') for record in suffix_raw] != result['valid_ids'] or
            any(raw.get('request_sha256') != record.get('request_sha256') or
                raw.get('attempt_id') != record.get('attempt_id') or
                raw.get('http_status') != 200 or raw.get('error_type') is not None
                for raw, record in zip(suffix_raw, suffix_records))):
        raise ValueError('Clef suffix raw and parsed identities differ')
    snapshot = AUTHORITY_SNAPSHOT.read_bytes()
    if not authority.LEDGER.read_bytes().startswith(snapshot):
        raise ValueError('Clef suffix authority snapshot is not a live ledger prefix')
    events = rows(AUTHORITY_SNAPSHOT)
    holds = [event for event in events if event.get('id') == suffix.HOLD_ID]
    if (len(holds) != 1 or holds[0] != {'event': 'hold', 'id': suffix.HOLD_ID,
                                      'usd': plan['authority_hold_usd'],
                                      'grant_sha256': digest(GRANT)}):
        raise ValueError('Exact Clef suffix hold differs')
    bindings = {**parent_bindings, **suffix_bindings}
    for path in (PLAN, GRANT, AUTHORITY_SNAPSHOT, frozen.MANIFEST,
                 inventory.REVIEW, Path(__file__)):
        bindings[str(path.relative_to(ROOT))] = digest(path)
    return {'kind': KIND, 'approved': True, 'reviewer': '/root',
            'status': 'closed_composite_not_clean',
            'permitted_next_stage': 'clef/fresh2/P2',
            'account_id_sha256': account_hash,
            'coverage': result, 'source_bindings': dict(sorted(bindings.items())),
            'bridge_sha256': digest(__file__),
            'scope': 'predecessor_only_no_request_budget_or_dispatch_change'}


def checked_review(path=REVIEW):
    path = Path(path)
    if json.loads(path.read_bytes()) != value():
        raise ValueError('Exact root-reviewed Clef composite predecessor required')
    return digest(path)


@contextmanager
def predecessor_bridge(review_hash):
    original = frozen.predecessor_hash

    def checked(model, repeat, condition, manifest_hash, base=frozen.BASE):
        if (model, repeat, condition) != ('clef', 'fresh2', 'P2'):
            return original(model, repeat, condition, manifest_hash, base)
        if Path(base) != frozen.BASE:
            raise ValueError('Changed Clef predecessor evidence root')
        if manifest_hash != frozen.checked_manifest(frozen.MANIFEST)[1]:
            raise ValueError('Changed Clef frozen manifest')
        return review_hash

    frozen.predecessor_hash = checked
    try:
        yield
    finally:
        frozen.predecessor_hash = original


def run_stage(model, repeat, condition, phase, grant_path, *, review_path=REVIEW,
              **options):
    if ((model, repeat, condition) != ('clef', 'fresh2', 'P2') or
            phase not in ('smoke', 'development') or
            Path(review_path) != REVIEW or
            set(options) - {'env_file', 'environment', 'wait_seconds',
                            'smoke_review_path', 'transport', 'billing_source'}):
        raise ValueError('Only the reviewed Clef fresh2/P2 predecessor is bridged')
    with _LOCK:
        review_hash = checked_review(review_path)
        grant = json.loads(Path(grant_path).read_bytes())
        if grant.get('account_id_sha256') != value()['account_id_sha256']:
            raise ValueError('Clef successor account differs from composite predecessor')
        with predecessor_bridge(review_hash):
            return inventory.run_stage(model, repeat, condition, phase,
                                       grant_path, **options)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('print-review', 'verify', 'run'))
    parser.add_argument('--review', type=Path, default=REVIEW)
    parser.add_argument('--phase', choices=('smoke', 'development'))
    parser.add_argument('--grant', type=Path)
    parser.add_argument('--smoke-review', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.command == 'print-review':
        print(json.dumps(value(), sort_keys=True, indent=2))
    elif args.command == 'verify':
        print(checked_review(args.review))
    else:
        if args.phase is None or args.grant is None:
            raise ValueError('Exact Clef fresh2/P2 phase and grant required')
        print(json.dumps(run_stage('clef', 'fresh2', 'P2', args.phase, args.grant,
                                   review_path=args.review,
                                   smoke_review_path=args.smoke_review,
                                   env_file=args.env_file), indent=2))


if __name__ == '__main__':
    main()
