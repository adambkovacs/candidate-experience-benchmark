#!/usr/bin/env python3
"""Versioned, unsent-only Mistral119 none fresh1/P0 DEV-051..060 stage.

Preparation and verification are offline. A separately allocated child and
independent root receipt are required before the existing request lifecycle is
entered. The DEV-048 timeout and DEV-050 HTTP 429 are never sent again.
"""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import mistral119_v3_remaining_phases as prior
import mistral119_fresh_repeat_study as study
import mistral119_v3_smoke as smoke
import openrouter_paid_benchmark as paid

PRIOR_VERIFY_SUFFIX = prior.verify_suffix
PRIOR_INTERRUPTED_GATE = prior.interrupted_gate
PRIOR_PARTITION_ID = prior.partition_id
PRIOR_SCHEMA = prior.SCHEMA

SCHEMA = 'mistral119-none-v3-second-suffix-051-060-v1'
BASE = study.BASE / 'v3-second-suffix-none-v1' / 'fresh1' / 'P0'
PRIOR_BASE = prior.SUFFIX_BASE
PRIOR_TERMINAL_SHA = '5094c9cd1bed96e45c13d238d63c5075132a08f1ea38e0e41d401b7fc3a0821a'
PRIOR_RECONCILIATION_SHA = '11555128a216beca6d95a877c26f7d9241166d977b179ddac36ff2db94b6d9f0'
IDS = tuple(f'DEV-{i:03d}' for i in range(51, 61))
PID = 'mistral119-none-v3-fresh1-p0-suffix-051-060-v1'
CAP = Decimal('0.25')
SOURCE_PATHS = (*prior.SOURCE_PATHS,
                'scripts/mistral119_v3_second_suffix.py',
                'tests/test_mistral119_v3_second_suffix.py')


def prior_gate():
    """Bind both sealed predecessors before any new claim or key access."""
    original = PRIOR_INTERRUPTED_GATE()
    # The reused runner's claim schema is versioned for this stage. Its frozen
    # predecessor manifest must still be rebuilt with its original schema.
    with patch.object(prior, 'SCHEMA', PRIOR_SCHEMA):
        old_manifest, old_sha = PRIOR_VERIFY_SUFFIX()
    terminal_path = PRIOR_BASE / 'suffix.terminal-public.json'
    recon_path = PRIOR_BASE / 'suffix.budget-reconciliation.json'
    if (smoke.sha(terminal_path) != PRIOR_TERMINAL_SHA or
            smoke.sha(recon_path) != PRIOR_RECONCILIATION_SHA):
        raise ValueError('Prior DEV-050 terminal or billing evidence differs')
    terminal = json.loads(terminal_path.read_text())
    recon = json.loads(recon_path.read_text())
    files = prior.phase_files(PRIOR_BASE, 'suffix')
    actual_hashes = {path.name: smoke.sha(path) for path in files.values()}
    attempts = prior.rows(files['attempts.jsonl'])
    raw = prior.rows(files['raw.jsonl'])
    parsed = prior.rows(files['parsed.jsonl'])
    journal = prior.rows(files['journal.jsonl'])
    old_ids = [x['record_id'] for x in old_manifest['suffix_requests']]
    if (old_ids != [f'DEV-{i:03d}' for i in range(49, 61)] or
            terminal.get('schema') != 'mistral119-none-v3-suffix-interruption-v1' or
            terminal.get('manifest_sha256') != old_sha or
            terminal.get('source_sha256') != actual_hashes or
            terminal.get('status') != 'interrupted_unscored' or
            terminal.get('terminal_exit_code') != 1 or
            terminal.get('valid_ids') != ['DEV-049'] or
            terminal.get('failed_id') != 'DEV-050' or
            terminal.get('http_status') != 429 or
            terminal.get('limit_source') != 'upstream_provider_shared_pool' or
            terminal.get('unsent_ids') != list(IDS) or
            terminal.get('reference_labels_sent') is not False or
            terminal.get('score') is not None or
            terminal.get('original_DEV048_unknown_preserved') is not True or
            [x.get('id') for x in attempts] != ['DEV-049', 'DEV-050'] or
            [x.get('id') for x in raw] != ['DEV-049', 'DEV-050'] or
            [x.get('id') for x in parsed] != ['DEV-049'] or
            [x.get('event') for x in journal[-2:]] != ['stage_stopped', 'stage_aborted'] or
            [x.get('id') for x in journal[-2:]] != ['DEV-050', 'DEV-050'] or
            attempts[0].get('status') != 'ok' or
            attempts[1].get('status') != 'unknown_cost' or
            attempts[1].get('cost_unknown') is not True or
            attempts[1].get('reserved_cost_usd') != str(study.RESERVE) or
            raw[1].get('http_status') != 429 or
            raw[1].get('request_sha256') != old_manifest['suffix_requests'][1]['request_sha256'] or
            recon.get('partition_id') != PRIOR_PARTITION_ID('fresh1', 'P0', 'suffix') or
            paid.number(recon.get('known_actual_usd')) != Decimal('0.00023835') or
            paid.number(recon.get('unknown_upper_bound_usd')) != study.RESERVE or
            recon.get('child_sha256') != terminal.get('sealed_child_sha256') or
            smoke.sha(recon['child_ledger']) != recon.get('child_sha256')):
        raise ValueError('Prior DEV-050 sealed attempt or unsent suffix differs')
    return {'original_interruption_gate_sha256': smoke.digest_bytes(smoke.canonical(original)),
            'second_interruption_terminal_sha256': PRIOR_TERMINAL_SHA,
            'second_interruption_reconciliation_sha256': PRIOR_RECONCILIATION_SHA,
            'prior_manifest_sha256': old_sha, 'failed_ids': ['DEV-048', 'DEV-050'],
            'unsent_ids': list(IDS)}


def manifest_value():
    gate = prior_gate()
    plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
    requests = plan['conditions']['P0']['development'][50:60]
    if [x['record_id'] for x in requests] != list(IDS):
        raise ValueError('Frozen DEV-051..060 membership differs')
    for item in requests:
        if study.digest(json.dumps(item['payload'], sort_keys=True)) != item['request_sha256']:
            raise ValueError('Frozen Mistral request bytes differ')
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_receipt_no_dispatch',
            'configuration_id': smoke.CONFIG, 'fresh_pass': 'fresh1', 'condition': 'P0',
            'phase': 'suffix', 'reference_labels_read': False,
            'prior_gate_sha256': smoke.digest_bytes(smoke.canonical(gate)),
            'frozen_plan_sha256': prior.PLAN_SHA['fresh1'],
            'frozen_execution_manifest_sha256': smoke.EXECUTION_SHA,
            'source_sha256': {name: smoke.sha(study.ROOT / name) for name in SOURCE_PATHS},
            'input_file_sha256': smoke.sha(study.ROOT / study.INPUTS),
            'per_request_full_context_reserve_usd': str(study.RESERVE),
            'child_cap_usd': str(CAP), 'suffix_requests': requests}


def prepare(base=BASE):
    value = manifest_value()
    path = Path(base) / 'manifest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        paid.durable(out, value)
    return smoke.digest_bytes(smoke.canonical(value))


def verify(base=BASE):
    saved = json.loads((Path(base) / 'manifest.json').read_text())
    if saved != manifest_value():
        raise ValueError('Second suffix manifest or source drift')
    return saved, smoke.digest_bytes(smoke.canonical(saved))


def gate(repeat, condition, phase, manifest, manifest_sha):
    if (repeat, condition, phase) != ('fresh1', 'P0', 'suffix'):
        raise ValueError('Only DEV-051..060 suffix is admitted')
    binding = prior_gate()
    if manifest.get('prior_gate_sha256') != smoke.digest_bytes(smoke.canonical(binding)):
        raise ValueError('Prior gate binding differs')
    if manifest_sha != verify()[1]:
        raise ValueError('Second suffix manifest differs')
    return {'prior': binding}


def partition_id(repeat, condition, phase):
    if (repeat, condition, phase) != ('fresh1', 'P0', 'suffix'):
        raise ValueError('Only DEV-051..060 suffix has a partition')
    return PID


def expected_receipt(repeat, condition, phase, manifest, manifest_sha,
                     budget_manifest, gate_binding):
    partition_id(repeat, condition, phase)
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': manifest_sha,
            'runner_sha256': manifest['source_sha256']['scripts/mistral119_v3_second_suffix.py'],
            'gate_sha256': smoke.digest_bytes(smoke.canonical(gate_binding)),
            'budget_manifest_sha256': smoke.sha(budget_manifest),
            'budget_partition_id': PID, 'child_cap_usd': str(CAP),
            'fresh_pass': repeat, 'condition': condition, 'phase': phase,
            'ids': list(IDS), 'reference_labels_sent': False}


def run(receipt_path, budget_manifest, *, send=None, live=None, open_child=None,
        load_key=None, env_file=None):
    """Reuse the reviewed durable lifecycle with a process-local exact binding."""
    replacements = {'SCHEMA': SCHEMA, 'SUFFIX_BASE': BASE, 'SUFFIX_CAP': CAP,
                    'verify_suffix': verify, 'gate': gate, 'partition_id': partition_id,
                    'expected_receipt': expected_receipt}
    kwargs = {'env_file': env_file}
    if send is not None: kwargs['send'] = send
    if live is not None: kwargs['live'] = live
    if open_child is not None: kwargs['open_child'] = open_child
    if load_key is not None: kwargs['load_key'] = load_key
    with patch.multiple(prior, **replacements):
        return prior.run('fresh1', 'P0', 'suffix', receipt_path, budget_manifest, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--root-review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare': print(prepare())
    elif args.action == 'verify': print(verify()[1])
    else:
        if not args.root_review_receipt or not args.budget_manifest:
            parser.error('run requires --root-review-receipt and --budget-manifest')
        run(args.root_review_receipt, args.budget_manifest, env_file=args.env_file)


if __name__ == '__main__': main()
