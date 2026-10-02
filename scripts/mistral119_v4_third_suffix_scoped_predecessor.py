#!/usr/bin/env python3
"""Reviewed execution bridge for the already allocated Mistral DEV-054..060 suffix.

The v3 stage and its manifest remain frozen. This bridge restores the original
predecessor constants only while rebuilding predecessor evidence, and verifies
the existing exact shared hold without adding another hold.
"""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import mistral119_v3_third_suffix as stage
import mistral119_v3_remaining_phases as prior
import openrouter_paid_benchmark as paid

SCHEMA = 'mistral119-none-v4-third-suffix-scoped-predecessor-v1'
BASE = stage.BASE
REVIEW = BASE / 'suffix.v4-root-review.json'
ORIGINAL_BUILD = stage.terminal_builder.build
ORIGINAL_SUFFIX_BASE = prior.SUFFIX_BASE
ORIGINAL_SUFFIX_CAP = prior.SUFFIX_CAP
V3_RUNNER_SHA = '2bff60db50b276ee163496277072e43956a0ef2e0c429137bf71f5c1e59d2129'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scoped_predecessor_build(*args, **kwargs):
    """Rebuild old evidence with its own immutable path and child cap."""
    if (ORIGINAL_SUFFIX_CAP != Decimal('0.25') or
            ORIGINAL_SUFFIX_BASE != stage.second.PRIOR_BASE):
        raise ValueError('Original predecessor constants differ')
    with patch.object(prior, 'SUFFIX_BASE', ORIGINAL_SUFFIX_BASE), \
            patch.object(prior, 'SUFFIX_CAP', ORIGINAL_SUFFIX_CAP):
        return ORIGINAL_BUILD(*args, **kwargs)


def expected_review(old_receipt, budget_manifest):
    manifest, digest = stage.verify()
    if (sha(stage.study.ROOT / 'scripts/mistral119_v3_third_suffix.py') != V3_RUNNER_SHA or
            digest != 'b0155804970144d421dfd9f633a5b26c232fda3b060c0fee0aef1975756c8aab'):
        raise ValueError('Frozen v3 runner or manifest differs')
    old = stage.saved(old_receipt)
    source = stage.global_hold_source(budget_manifest, stage.PID)
    child = stage.saved(budget_manifest)['partitions'][0]['child_ledger']
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'reviewer': 'root', 'wrapper_sha256': sha(__file__),
            'v3_runner_sha256': V3_RUNNER_SHA,
            'v3_manifest_sha256': sha(BASE / 'manifest.json'),
            'v3_manifest_digest': digest,
            'v3_root_receipt_sha256': sha(old_receipt),
            'budget_manifest_sha256': sha(budget_manifest),
            'existing_global_hold_id': stage.AUTHORITY_ID,
            'existing_global_hold_source_sha256': source,
            'existing_child_ledger_path': child,
            'old_receipt_authority_head_sha256': old['global_authority_head_sha256'],
            'prior_terminal_sha256': stage.TERMINAL_SHA,
            'prior_reconciliation_sha256': stage.RECON_SHA,
            'ids': list(stage.IDS), 'reference_labels_sent': False}


def check_review(review, old_receipt, budget_manifest):
    if Path(review).resolve() != REVIEW.resolve():
        raise ValueError('Wrong v4 root execution receipt path')
    value = stage.saved(review)
    head = value.get('existing_authority_head_sha256')
    if (not isinstance(head, str) or len(head) != 64 or
            any(char not in '0123456789abcdef' for char in head) or
            value != {**expected_review(old_receipt, budget_manifest),
                      'existing_authority_head_sha256': head}):
        raise ValueError('V4 root execution receipt differs')
    return value


def verify_existing_hold(old_head, budget_manifest, source, *, review):
    """Replace v3's pre-hold append step only for this already held child."""
    if (old_head != review['old_receipt_authority_head_sha256'] or
            source != review['existing_global_hold_source_sha256'] or
            source != stage.global_hold_source(budget_manifest, stage.PID)):
        raise ValueError('Existing hold binding differs')
    with stage.AUTHORITY.open('r') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = file.read().encode()
        if hashlib.sha256(raw).hexdigest() != review['existing_authority_head_sha256']:
            raise ValueError('Existing shared authority head changed')
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not events or events[0] != {'event': 'authority',
                'kind': 'postapproval-paid-work-v1',
                'cap_usd': str(stage.AUTHORITY_CAP),
                'decision_key': stage.AUTHORITY_DECISION_KEY,
                'approval_sha256': stage.AUTHORITY_APPROVAL_SHA}:
            raise ValueError('Shared paid-work authority differs')
        holds = events[1:]
        if (any(event.get('event') != 'hold' for event in holds) or
                len({event.get('id') for event in holds}) != len(holds) or
                sum((paid.number(event['usd']) for event in holds), Decimal(0)) >
                stage.AUTHORITY_CAP or
                [event for event in holds if event.get('id') == stage.AUTHORITY_ID] !=
                [{'event': 'hold', 'id': stage.AUTHORITY_ID,
                  'source_sha256': source, 'usd': str(stage.CAP)}]):
            raise ValueError('Existing exact child hold differs')


def run(review, old_receipt, budget_manifest, *, send=None, live=None,
        open_child=None, load_key=None, env_file=None):
    if (Path(old_receipt).resolve() != (BASE / 'suffix.root-review.json').resolve() or
            Path(budget_manifest).resolve() !=
            (BASE / 'suffix.budget-manifest.json').resolve()):
        raise ValueError('V4 may reuse only the allocated v3 child and receipt')
    with patch.object(stage.terminal_builder, 'build', scoped_predecessor_build):
        reviewed = check_review(review, old_receipt, budget_manifest)
        stage.check_review(old_receipt, budget_manifest)
        files = prior.phase_files(BASE, 'suffix')
        if any(path.exists() for path in files.values()):
            raise FileExistsError('Third suffix already claimed; no replay')
        kwargs = {'env_file': env_file}
        for name, value in [('send', send), ('live', live),
                            ('open_child', open_child), ('load_key', load_key)]:
            if value is not None:
                kwargs[name] = value
        with patch.object(stage, 'hold_authority',
                lambda head, budget, source: verify_existing_hold(
                    head, budget, source, review=reviewed)):
            return stage.run(old_receipt, budget_manifest, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'run'))
    parser.add_argument('--v4-root-review-receipt', type=Path)
    parser.add_argument('--root-review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    old = args.root_review_receipt or BASE / 'suffix.root-review.json'
    budget = args.budget_manifest or BASE / 'suffix.budget-manifest.json'
    if args.action == 'verify':
        print(json.dumps(expected_review(old, budget), sort_keys=True))
    else:
        if not args.v4_root_review_receipt:
            parser.error('run requires --v4-root-review-receipt')
        run(args.v4_root_review_receipt, old, budget, env_file=args.env_file)


if __name__ == '__main__':
    main()
