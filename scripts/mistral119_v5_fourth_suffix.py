#!/usr/bin/env python3
"""Offline admission and reviewed execution for unsent Mistral DEV-059..060.

Preparation never allocates a child, changes the shared authority, or sends a
request. Execution requires a separate child, exact root receipt and live route.
"""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import mistral119_v3_remaining_phases as prior
import mistral119_v3_second_suffix as second
import mistral119_v3_third_suffix as third
import mistral119_v4_third_suffix_scoped_predecessor as bridge
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import mistral119_v3_smoke as smoke
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions

SCHEMA = 'mistral119-none-v5-fourth-suffix-059-060-v1'
BASE = study.BASE / 'v5-fourth-suffix-none-v1' / 'fresh1' / 'P0'
PREVIOUS = third.BASE
IDS = ('DEV-059', 'DEV-060')
PID = 'mistral119-none-v5-fresh1-p0-suffix-059-060-v1'
CAP = Decimal('0.09')
AUTHORITY_ID = 'openrouter-mistral119-none-fourth-suffix-059-060-v1'
AUTHORITY = third.AUTHORITY
SEALED = {
    'manifest.json': '42c24f348fe55f8463c292c66bf1c53620c7c9afe3b34889187829857567ec92',
    'suffix.third-terminal-pending-review.json': 'c9021643e61b48a6a3b21f70f78724e19b7366bb06e64acbd33f0ac975267cfb',
    'suffix.third-terminal-root-review.json': 'd753552e6d4b7bbd35f2f440ea44211f7197baf6df6c5c9a33bbe3329bb85e9d',
    'suffix.third-budget-reconciliation.json': 'd2d43f9cd9b36a9a19359f80994a61dced01b1f68125645d6debbaa792f472b6',
    'suffix.attempts.jsonl': '9c4339351a0d669e35a06722c56e06db12529d04416273afe1675f956a4c6bbc',
    'suffix.journal.jsonl': '04e22712b1eb1e81ea9997b19da00e153588fe9840da7e06f7263bebd2c659e2',
    'suffix.raw.jsonl': 'c621f26dc826dc76b2768357b91aa51f93e7bd99ca335e04431bbc14626a0f4b',
    'suffix.parsed.jsonl': '0748969b2b294f076f2b429e49450aee2deea77d5323be195285dff2553261b9',
}
SOURCE_PATHS = (*third.SOURCE_PATHS,
                'scripts/mistral119_v4_third_suffix_scoped_predecessor.py',
                'tests/test_mistral119_v4_third_suffix_scoped_predecessor.py',
                'scripts/mistral119_v5_fourth_suffix.py',
                'tests/test_mistral119_v5_fourth_suffix.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved(path):
    return json.loads(Path(path).read_text())


def prior_gate():
    """Check immutable third-stage bytes and its closed child before admission."""
    if any(sha(PREVIOUS / name) != digest for name, digest in SEALED.items()):
        raise ValueError('Third suffix sealed evidence differs')
    # prior.run changes these globals for a new stage. Rebuild the old manifest
    # with the old values even during its per-request verification loop.
    with patch.object(prior, 'SUFFIX_BASE', bridge.ORIGINAL_SUFFIX_BASE), \
         patch.object(prior, 'SUFFIX_CAP', bridge.ORIGINAL_SUFFIX_CAP), \
         patch.object(prior, 'SCHEMA', second.PRIOR_SCHEMA), \
         patch.object(third.terminal_builder, 'build', bridge.scoped_predecessor_build):
        old, old_digest = third.verify()
    proposal = saved(PREVIOUS / 'suffix.third-terminal-pending-review.json')
    review = saved(PREVIOUS / 'suffix.third-terminal-root-review.json')
    recon = saved(PREVIOUS / 'suffix.third-budget-reconciliation.json')
    attempts = prior.rows(PREVIOUS / 'suffix.attempts.jsonl')
    journal = prior.rows(PREVIOUS / 'suffix.journal.jsonl')
    if (old_digest != 'b0155804970144d421dfd9f633a5b26c232fda3b060c0fee0aef1975756c8aab' or
            [x['record_id'] for x in old['suffix_requests']] != list(third.IDS) or
            proposal.get('approved') is not False or
            proposal.get('stage', {}).get('valid_ids') != list(third.IDS[:4]) or
            proposal.get('stage', {}).get('failed_id') != 'DEV-058' or
            proposal.get('stage', {}).get('never_sent_ids') != list(IDS) or
            proposal.get('failure', {}).get('unknown_cost_upper_bound_usd') != str(study.RESERVE) or
            proposal.get('failure', {}).get('retry_allowed') is not False or
            proposal.get('composite', {}).get('valid') != 54 or
            proposal.get('composite', {}).get('failed') != 4 or
            proposal.get('composite', {}).get('never_sent') != 2 or
            proposal.get('composite', {}).get('failed_ids') !=
                ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058'] or
            proposal.get('composite', {}).get('score') is not None or
            review.get('approved') is not True or review.get('reviewer') != 'root' or
            review.get('proposal_sha256') != SEALED['suffix.third-terminal-pending-review.json'] or
            recon.get('event') != 'partition_reconciled' or
            recon.get('partition_id') != third.PID or
            paid.number(recon.get('unknown_upper_bound_usd')) != study.RESERVE or
            paid.number(recon.get('known_actual_usd')) != Decimal('0.000393795') or
            sha(recon['child_ledger']) != recon.get('child_sha256') or
            [x.get('id') for x in attempts] != list(third.IDS[:5]) or
            [x.get('status') for x in attempts] != ['ok'] * 4 + ['unknown_cost'] or
            [x.get('event') for x in journal[-2:]] != ['stage_stopped', 'stage_aborted'] or
            [x.get('id') for x in journal[-2:]] != ['DEV-058', 'DEV-058']):
        raise ValueError('Third suffix terminal, billing, or no-retry boundary differs')
    child_events = prior.rows(recon['child_ledger'])
    if (child_events[-2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            child_events[-2].get('record_id') not in (None, 'DEV-058') or
            child_events[-2].get('attempt_id') != attempts[-1].get('attempt_id') or
            child_events[-1].get('event') != 'partition_closed'):
        raise ValueError('Third suffix child is not sealed')
    return {'third_manifest_sha256': SEALED['manifest.json'],
            'third_terminal_sha256': SEALED['suffix.third-terminal-pending-review.json'],
            'third_review_sha256': SEALED['suffix.third-terminal-root-review.json'],
            'third_reconciliation_sha256': SEALED['suffix.third-budget-reconciliation.json'],
            'third_child_sha256': recon['child_sha256'],
            'failed_ids_preserved': ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058'],
            'unsent_ids': list(IDS), 'composite_valid': 54, 'composite_failed': 4}


def manifest_value():
    binding = prior_gate()
    plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
    frozen.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
    requests = plan['conditions']['P0']['development'][58:60]
    if ([x['record_id'] for x in requests] != list(IDS) or
            any(study.digest(json.dumps(x['payload'], sort_keys=True)) != x['request_sha256']
                for x in requests) or CAP < study.RESERVE * len(IDS)):
        raise ValueError('Frozen DEV-059..060 requests or cap differ')
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_allocation_no_dispatch',
            'configuration_id': smoke.CONFIG, 'fresh_pass': 'fresh1',
            'condition': 'P0', 'phase': 'suffix', 'reference_labels_read': False,
            'prior_gate_sha256': smoke.digest_bytes(smoke.canonical(binding)),
            'preserved_failed_ids': binding['failed_ids_preserved'],
            'frozen_plan_sha256': prior.PLAN_SHA['fresh1'],
            'frozen_execution_manifest_sha256': smoke.EXECUTION_SHA,
            'source_sha256': {name: smoke.sha(study.ROOT / name) for name in SOURCE_PATHS},
            'input_file_sha256': smoke.sha(study.ROOT / study.INPUTS),
            'per_request_full_context_reserve_usd': str(study.RESERVE),
            'two_request_full_context_upper_bound_usd': str(study.RESERVE * len(IDS)),
            'proposed_child_cap_usd': str(CAP),
            'proposed_global_hold_id': AUTHORITY_ID,
            'exact_route': {'model': study.MODEL, 'provider_tag': study.PROVIDER,
                            'context_tokens': study.CONTEXT,
                            'input_usd_per_million': str(study.INPUT_PRICE),
                            'output_usd_per_million': str(study.OUTPUT_PRICE),
                            'primary_source': 'https://openrouter.ai/api/v1/models/' +
                                              study.MODEL + '/endpoints',
                            'live_recheck_required': True},
            'suffix_requests': requests}


def prepare(base=BASE):
    value = manifest_value()
    path = Path(base) / 'manifest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        paid.durable(out, value)
    return smoke.digest_bytes(smoke.canonical(value))


def verify(base=BASE):
    value = saved(Path(base) / 'manifest.json')
    if value != manifest_value():
        raise ValueError('Fourth suffix manifest or source drift')
    return value, smoke.digest_bytes(smoke.canonical(value))


def gate(repeat, condition, phase, manifest, manifest_sha):
    if (repeat, condition, phase) != ('fresh1', 'P0', 'suffix'):
        raise ValueError('Only DEV-059..060 is admitted')
    binding = prior_gate()
    if (manifest.get('prior_gate_sha256') != smoke.digest_bytes(smoke.canonical(binding)) or
            manifest_sha != verify()[1]):
        raise ValueError('Fourth suffix predecessor or manifest differs')
    return {'prior': binding}


def partition_id(repeat, condition, phase):
    if (repeat, condition, phase) != ('fresh1', 'P0', 'suffix'):
        raise ValueError('Only DEV-059..060 has a partition')
    return PID


def global_hold_source(budget_manifest):
    path = Path(budget_manifest).resolve()
    if path != (BASE / 'suffix.budget-manifest.json').resolve():
        raise ValueError('Wrong fourth-suffix budget path')
    budget = saved(path)
    child = path.parent / (path.stem + '-' + PID + '.jsonl')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(smoke.MASTER.resolve()) or
            budget.get('partitions') != [{'id': PID, 'cap_usd': str(CAP),
                'model': study.MODEL, 'provider': study.PROVIDER,
                'reasoning': 'none', 'child_ledger': str(child)}]):
        raise ValueError('Fourth-suffix budget child differs')
    identity = {'successor_manifest_sha256': sha(BASE / 'manifest.json'),
                'budget_manifest_path': str(path), 'budget_manifest_sha256': sha(path),
                'partition_id': PID, 'child_ledger_path': str(child)}
    return smoke.digest_bytes(smoke.canonical(identity))


def expected_receipt(repeat, condition, phase, manifest, manifest_sha,
                     budget_manifest, gate_binding):
    partition_id(repeat, condition, phase)
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': manifest_sha,
            'runner_sha256': manifest['source_sha256']['scripts/mistral119_v5_fourth_suffix.py'],
            'gate_sha256': smoke.digest_bytes(smoke.canonical(gate_binding)),
            'budget_manifest_sha256': sha(budget_manifest),
            'budget_partition_id': PID, 'child_cap_usd': str(CAP),
            'global_hold_id': AUTHORITY_ID, 'global_hold_usd': str(CAP),
            'global_hold_source_sha256': global_hold_source(budget_manifest),
            'global_authority_cap_usd': str(third.AUTHORITY_CAP),
            'global_authority_approval_sha256': third.AUTHORITY_APPROVAL_SHA,
            'fresh_pass': repeat, 'condition': condition, 'phase': phase,
            'ids': list(IDS), 'reference_labels_sent': False}


def check_review(path, budget_manifest):
    if Path(path).resolve() != (BASE / 'suffix.root-review.json').resolve():
        raise ValueError('Wrong fourth-suffix root receipt path')
    manifest, digest = verify()
    binding = gate('fresh1', 'P0', 'suffix', manifest, digest)
    expected = expected_receipt('fresh1', 'P0', 'suffix', manifest, digest,
                                budget_manifest, binding)
    value = saved(path)
    head = value.get('global_authority_head_sha256')
    if (not isinstance(head, str) or len(head) != 64 or
            any(c not in '0123456789abcdef' for c in head) or
            value != {**expected, 'global_authority_head_sha256': head, 'reviewer': 'root'}):
        raise ValueError('Fourth-suffix root receipt differs')
    return value


def hold_authority(expected_head, budget_manifest, source):
    if source != global_hold_source(budget_manifest):
        raise ValueError('Reviewed global hold source differs')
    with AUTHORITY.open('r+') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = file.read().encode()
        if hashlib.sha256(raw).hexdigest() != expected_head:
            raise ValueError('Global authority head changed')
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not events or events[0] != {'event': 'authority',
                'kind': 'postapproval-paid-work-v1', 'cap_usd': str(third.AUTHORITY_CAP),
                'decision_key': third.AUTHORITY_DECISION_KEY,
                'approval_sha256': third.AUTHORITY_APPROVAL_SHA}:
            raise ValueError('Shared paid-work authority differs')
        holds = events[1:]
        desired = {'event': 'hold', 'id': AUTHORITY_ID,
                   'source_sha256': source, 'usd': str(CAP)}
        total = sum((paid.number(x['usd']) for x in holds), Decimal(0))
        existing = [x for x in holds if x.get('id') == AUTHORITY_ID]
        if (any(x.get('event') != 'hold' for x in holds) or
                len({x.get('id') for x in holds}) != len(holds) or
                total > third.AUTHORITY_CAP or (existing and existing != [desired])):
            raise ValueError('Shared authority cap or hold differs')
        if not existing:
            if total + CAP > third.AUTHORITY_CAP:
                raise ValueError('Shared authority cannot fit fourth suffix')
            file.seek(0, 2)
            paid.durable(file, desired)


def run(receipt_path, budget_manifest, *, send=None, live=None, open_child=None,
        load_key=None, env_file=None):
    receipt = check_review(receipt_path, budget_manifest)
    files = prior.phase_files(BASE, 'suffix')
    if any(path.exists() for path in files.values()):
        raise FileExistsError('Fourth suffix already claimed; no replay')
    plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
    live_fn = live if live is not None else frozen.live_controls
    model, endpoint, reserve = live_fn(plan, 'P0')
    if (model.get('id') != study.MODEL or endpoint.get('tag') != study.PROVIDER or
            reserve != study.RESERVE):
        raise ValueError('Exact route or full reserve differs')
    open_fn = open_child if open_child is not None else partitions.open_partition
    ledger = open_fn(smoke.MASTER, budget_manifest, PID,
                     study.MODEL, study.PROVIDER, 'none')
    try:
        _, pending, blocked = ledger.state()
        if (ledger.master_cap != Decimal('12.38') or ledger.cap != CAP or
                ledger.accounted() != 0 or pending or blocked or ledger.closed):
            raise ValueError('Fourth-suffix child differs or is not fresh')
    finally:
        ledger.close()
    hold_authority(receipt['global_authority_head_sha256'], budget_manifest,
                   receipt['global_hold_source_sha256'])
    replacements = {'SCHEMA': SCHEMA, 'SUFFIX_BASE': BASE, 'SUFFIX_CAP': CAP,
                    'verify_suffix': verify, 'gate': gate, 'partition_id': partition_id,
                    'expected_receipt': expected_receipt}
    kwargs = {'env_file': env_file}
    for name, value in [('send', send), ('live', live), ('open_child', open_child),
                        ('load_key', load_key)]:
        if value is not None:
            kwargs[name] = value
    with patch.multiple(prior, **replacements):
        return prior.run('fresh1', 'P0', 'suffix', receipt_path, budget_manifest,
                         **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--root-review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        print(verify()[1])
    else:
        if not args.root_review_receipt or not args.budget_manifest:
            parser.error('run requires --root-review-receipt and --budget-manifest')
        run(args.root_review_receipt, args.budget_manifest, env_file=args.env_file)


if __name__ == '__main__':
    main()
