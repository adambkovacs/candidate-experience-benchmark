#!/usr/bin/env python3
"""Versioned, unsent-only Mistral119 none fresh1/P0 DEV-054..060 stage.

Preparation and verification are offline. A separate allocation, global hold,
and root receipt are required before the frozen durable request loop can run.
"""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import build_mistral119_second_suffix_terminal as terminal_builder
import mistral119_v3_second_suffix as second
import mistral119_v3_remaining_phases as prior
import mistral119_fresh_repeat_study as study
import mistral119_v3_smoke as smoke
import mistral119_fresh_repeat_execution as frozen
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions

SCHEMA = 'mistral119-none-v3-third-suffix-054-060-v1'
BASE = study.BASE / 'v3-third-suffix-none-v1' / 'fresh1' / 'P0'
SECOND_BASE = second.BASE
TERMINAL_SHA = '07e7a2ae939612f25f3c74a42c54cf96c9ef22c76fa27484f76bd8007b54c892'
RECON_SHA = '7875324d3808eea81437b9b5422febaeefb3cd3f3f7f72e2699c7821ebd1aa58'
IDS = tuple(f'DEV-{i:03d}' for i in range(54, 61))
PID = 'mistral119-none-v3-fresh1-p0-suffix-054-060-v1'
CAP = Decimal('0.30')
AUTHORITY = study.ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
AUTHORITY_ID = 'openrouter-mistral119-none-third-suffix-054-060-v1'
AUTHORITY_CAP = Decimal('10.00')
AUTHORITY_APPROVAL_SHA = '57d5ff76acd14f85d5e600c6527c310fc08f4eb66d45b1c25b9d778d770aaf8f'
AUTHORITY_DECISION_KEY = 'candidate-experience-benchmark/user-ten-dollar-tests-20261002'
SOURCE_PATHS = (*second.SOURCE_PATHS,
                'scripts/build_mistral119_second_suffix_terminal.py',
                'tests/test_build_mistral119_second_suffix_terminal.py',
                'scripts/mistral119_v3_third_suffix.py',
                'tests/test_mistral119_v3_third_suffix.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved(path):
    return json.loads(Path(path).read_text())


def prior_gate():
    """Rebuild all predecessors and bind the terminal three-failure boundary."""
    rebuilt = terminal_builder.build()
    terminal_path = SECOND_BASE / 'suffix.terminal-public.json'
    recon_path = SECOND_BASE / 'suffix.budget-reconciliation.json'
    if (sha(terminal_path) != TERMINAL_SHA or sha(recon_path) != RECON_SHA or
            saved(terminal_path) != rebuilt or
            rebuilt.get('status') != 'interrupted_unscored' or
            rebuilt.get('valid_ids') != ['DEV-051', 'DEV-052'] or
            rebuilt.get('failed_id') != 'DEV-053' or
            rebuilt.get('http_status') != 429 or
            rebuilt.get('limit_source') != 'upstream_provider_shared_pool' or
            rebuilt.get('earlier_failed_ids_preserved') != ['DEV-048', 'DEV-050'] or
            rebuilt.get('unsent_ids') != list(IDS) or
            rebuilt.get('composite_valid_count') != 50 or
            rebuilt.get('composite_failed_count') != 3 or
            rebuilt.get('composite_never_sent_count') != 7 or
            rebuilt.get('composite_score') is not None or
            rebuilt.get('reference_labels_sent') is not False or
            rebuilt.get('sealed_child_sha256') != saved(recon_path).get('child_sha256')):
        raise ValueError('Second suffix terminal, billing, or unsent boundary differs')
    return {'second_terminal_sha256': TERMINAL_SHA,
            'second_reconciliation_sha256': RECON_SHA,
            'second_manifest_sha256': sha(SECOND_BASE / 'manifest.json'),
            'preserved_failed_ids': ['DEV-048', 'DEV-050', 'DEV-053'],
            'unsent_ids': list(IDS), 'composite_valid_count': 50,
            'composite_failed_count': 3}


def manifest_value():
    binding = prior_gate()
    plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
    frozen.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
    requests = plan['conditions']['P0']['development'][53:60]
    if ([item['record_id'] for item in requests] != list(IDS) or
            any(study.digest(json.dumps(item['payload'], sort_keys=True)) !=
                item['request_sha256'] for item in requests) or
            CAP < study.RESERVE * len(IDS)):
        raise ValueError('Frozen DEV-054..060 requests or full-context cap differ')
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_receipt_no_dispatch',
            'configuration_id': smoke.CONFIG, 'fresh_pass': 'fresh1',
            'condition': 'P0', 'phase': 'suffix', 'reference_labels_read': False,
            'prior_gate_sha256': smoke.digest_bytes(smoke.canonical(binding)),
            'prior_terminal_sha256': TERMINAL_SHA,
            'prior_reconciliation_sha256': RECON_SHA,
            'preserved_failed_ids': binding['preserved_failed_ids'],
            'frozen_plan_sha256': prior.PLAN_SHA['fresh1'],
            'frozen_execution_manifest_sha256': smoke.EXECUTION_SHA,
            'source_sha256': {name: smoke.sha(study.ROOT / name) for name in SOURCE_PATHS},
            'input_file_sha256': smoke.sha(study.ROOT / study.INPUTS),
            'per_request_full_context_reserve_usd': str(study.RESERVE),
            'seven_request_full_context_upper_bound_usd': str(study.RESERVE * len(IDS)),
            'child_cap_usd': str(CAP),
            'global_hold_id': AUTHORITY_ID, 'global_hold_usd': str(CAP),
            'exact_route': {'model': study.MODEL, 'provider_tag': study.PROVIDER,
                            'context_tokens': study.CONTEXT,
                            'input_usd_per_million': str(study.INPUT_PRICE),
                            'output_usd_per_million': str(study.OUTPUT_PRICE),
                            'primary_source': 'https://openrouter.ai/api/v1/models/' +
                                              study.MODEL + '/endpoints',
                            'checked_date_utc': '2026-10-02',
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
    saved_value = saved(Path(base) / 'manifest.json')
    if saved_value != manifest_value():
        raise ValueError('Third suffix manifest or source drift')
    return saved_value, smoke.digest_bytes(smoke.canonical(saved_value))


def gate(repeat, condition, phase, manifest, manifest_sha):
    if (repeat, condition, phase) != ('fresh1', 'P0', 'suffix'):
        raise ValueError('Only DEV-054..060 suffix is admitted')
    binding = prior_gate()
    if (manifest.get('prior_gate_sha256') != smoke.digest_bytes(smoke.canonical(binding)) or
            manifest_sha != verify()[1]):
        raise ValueError('Prior boundary or third suffix manifest differs')
    return {'prior': binding}


def partition_id(repeat, condition, phase):
    if (repeat, condition, phase) != ('fresh1', 'P0', 'suffix'):
        raise ValueError('Only DEV-054..060 suffix has a partition')
    return PID


def global_hold_source(budget_manifest, partition_id_value):
    """Bind the shared hold to one exact future child and reviewed manifest."""
    budget_path = Path(budget_manifest).resolve()
    if budget_path != (BASE / 'suffix.budget-manifest.json').resolve():
        raise ValueError('Wrong third-suffix budget manifest path')
    budget = saved(budget_path)
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(smoke.MASTER.resolve()) or
            partition_id_value != PID):
        raise ValueError('Third-suffix budget manifest identity differs')
    entries = budget.get('partitions')
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError('One exact third-suffix child required')
    entry = entries[0]
    expected_child = budget_path.parent / (budget_path.stem + '-' + PID + '.jsonl')
    if (entry.get('id') != PID or entry.get('cap_usd') != str(CAP) or
            entry.get('model') != study.MODEL or entry.get('provider') != study.PROVIDER or
            entry.get('reasoning') != 'none' or
            entry.get('child_ledger') != str(expected_child)):
        raise ValueError('Third-suffix child controls differ')
    identity = {'successor_manifest_sha256': sha(BASE / 'manifest.json'),
                'budget_manifest_path': str(budget_path),
                'budget_manifest_sha256': sha(budget_path),
                'partition_id': PID, 'child_ledger_path': str(expected_child)}
    return hashlib.sha256(json.dumps(identity, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def expected_receipt(repeat, condition, phase, manifest, manifest_sha,
                     budget_manifest, gate_binding):
    partition_id(repeat, condition, phase)
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': manifest_sha,
            'runner_sha256': manifest['source_sha256']['scripts/mistral119_v3_third_suffix.py'],
            'gate_sha256': smoke.digest_bytes(smoke.canonical(gate_binding)),
            'budget_manifest_sha256': smoke.sha(budget_manifest),
            'budget_partition_id': PID, 'child_cap_usd': str(CAP),
            'global_hold_id': AUTHORITY_ID,
            'global_hold_usd': str(CAP),
            'global_hold_source_sha256': global_hold_source(budget_manifest, PID),
            'global_authority_cap_usd': str(AUTHORITY_CAP),
            'global_authority_approval_sha256': AUTHORITY_APPROVAL_SHA,
            'fresh_pass': repeat, 'condition': condition, 'phase': phase,
            'ids': list(IDS), 'reference_labels_sent': False}


def check_review(path, budget_manifest):
    receipt_path = Path(path)
    if receipt_path.resolve() != (BASE / 'suffix.root-review.json').resolve():
        raise ValueError('Wrong third-suffix receipt path')
    manifest, digest = verify()
    binding = gate('fresh1', 'P0', 'suffix', manifest, digest)
    expected = expected_receipt('fresh1', 'P0', 'suffix', manifest, digest,
                                budget_manifest, binding)
    value = saved(receipt_path)
    head = value.get('global_authority_head_sha256')
    reviewer = value.get('reviewer')
    if (not isinstance(head, str) or len(head) != 64 or
            any(char not in '0123456789abcdef' for char in head) or
            not isinstance(reviewer, str) or not reviewer.strip() or
            value != {**expected, 'global_authority_head_sha256': head,
                      'reviewer': reviewer}):
        raise ValueError('Independent exact-child root receipt differs')
    return value


def hold_authority(expected_head, budget_manifest, expected_source):
    source = global_hold_source(budget_manifest, PID)
    if source != expected_source:
        raise ValueError('Reviewed global hold source differs')
    with AUTHORITY.open('r+') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        file.seek(0)
        raw = file.read().encode()
        if hashlib.sha256(raw).hexdigest() != expected_head:
            raise ValueError('Global authority head changed')
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not events or events[0] != {'event': 'authority',
                                      'kind': 'postapproval-paid-work-v1',
                                      'cap_usd': str(AUTHORITY_CAP),
                                      'decision_key': AUTHORITY_DECISION_KEY,
                                      'approval_sha256': AUTHORITY_APPROVAL_SHA}:
            raise ValueError('Shared paid-work authority differs')
        holds = [event for event in events[1:] if event.get('event') == 'hold']
        if (len(holds) != len(events) - 1 or
                len({event.get('id') for event in holds}) != len(holds)):
            raise ValueError('Shared authority event structure differs')
        total = sum((paid.number(event['usd']) for event in holds), Decimal(0))
        desired = {'event': 'hold', 'id': AUTHORITY_ID,
                   'source_sha256': source, 'usd': str(CAP)}
        existing = [event for event in holds if event['id'] == AUTHORITY_ID]
        if total > AUTHORITY_CAP or (existing and existing != [desired]):
            raise ValueError('Shared authority cap or existing Mistral hold differs')
        if not existing:
            if total + CAP > AUTHORITY_CAP:
                raise ValueError('Shared authority cannot fit Mistral hold')
            file.seek(0, 2)
            paid.durable(file, desired)


def run(receipt_path, budget_manifest, *, send=None, live=None, open_child=None,
        load_key=None, env_file=None):
    """Use the frozen durable lifecycle after exact review and shared hold."""
    manifest, digest = verify()
    binding = gate('fresh1', 'P0', 'suffix', manifest, digest)
    receipt = check_review(receipt_path, budget_manifest)
    files = prior.phase_files(BASE, 'suffix')
    if any(path.exists() for path in files.values()):
        raise FileExistsError('Third suffix already claimed; no replay')
    plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
    live_function = live if live is not None else frozen.live_controls
    model, endpoint, reserve = live_function(plan, 'P0')
    if (model.get('id') != study.MODEL or endpoint.get('tag') != study.PROVIDER or
            reserve != study.RESERVE):
        raise ValueError('Fresh exact route or full-context reserve differs')
    open_function = open_child if open_child is not None else partitions.open_partition
    ledger = open_function(smoke.MASTER, budget_manifest, PID,
                           study.MODEL, study.PROVIDER, 'none')
    try:
        _, pending, blocked = ledger.state()
        if (ledger.master_cap != Decimal('12.38') or ledger.cap != CAP or
                ledger.accounted() != 0 or pending or blocked or ledger.closed):
            raise ValueError('Allocated child differs or is not fresh')
    finally:
        ledger.close()
    hold_authority(receipt['global_authority_head_sha256'], budget_manifest,
                   receipt['global_hold_source_sha256'])
    replacements = {'SCHEMA': SCHEMA, 'SUFFIX_BASE': BASE, 'SUFFIX_CAP': CAP,
                    'verify_suffix': verify, 'gate': gate,
                    'partition_id': partition_id, 'expected_receipt': expected_receipt}
    kwargs = {'env_file': env_file}
    if send is not None: kwargs['send'] = send
    if live is not None: kwargs['live'] = live
    if open_child is not None: kwargs['open_child'] = open_child
    if load_key is not None: kwargs['load_key'] = load_key
    with patch.multiple(prior, **replacements):
        return prior.run('fresh1', 'P0', 'suffix', receipt_path,
                         budget_manifest, **kwargs)


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
