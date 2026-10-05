#!/usr/bin/env python3
"""Separate fresh1/P1 Mistral successor after the closed, failed-position P0.

Prepare and verify are offline. Run requires a reviewed receipt, a distinct
OpenRouter child, and an atomic hold on the shared paid-work authority.
"""
import argparse
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import build_mistral119_fresh1_p0_findings as p0
import mistral119_v3_remaining_phases as prior
import mistral119_v3_third_suffix as third
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import mistral119_v3_smoke as smoke
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions

SCHEMA = 'mistral119-none-fresh1-p1-successor-v1'
BASE = study.BASE / 'p1-successor-v1'
PHASES = ('smoke', 'development')
SMOKE_CAP = study.RESERVE * 3
DEVELOPMENT_CAP = Decimal('0.25')
CAPS = {'smoke': SMOKE_CAP, 'development': DEVELOPMENT_CAP}
PID = {phase: f'mistral119-none-fresh1-p1-successor-{phase}-v1' for phase in PHASES}
AUTHORITY_ID = {phase: f'openrouter-mistral119-none-fresh1-p1-successor-{phase}-v1'
                for phase in PHASES}
AUTHORITY = third.AUTHORITY
PUBLIC_P0 = study.ROOT / 'public-site/mistral119-fresh1-p0-findings.json'
SOURCE_PATHS = (*smoke.SOURCE_PATHS,
                'scripts/mistral119_v3_remaining_phases.py',
                'scripts/mistral119_v3_third_suffix.py',
                'scripts/build_mistral119_fresh1_p0_findings.py',
                'scripts/mistral119_p1_successor_v1.py')
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
FAILED = ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058', 'DEV-060']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved(path):
    return json.loads(Path(path).read_text())


def check_phase(phase):
    if phase not in PHASES:
        raise ValueError('Only fresh1/P1 smoke and development are admitted')


def p0_gate():
    """Rebuild all five P0 segments and bind the exact published projection."""
    rebuilt = p0.build()
    if (saved(PUBLIC_P0) != rebuilt or
            rebuilt.get('schema') != p0.SCHEMA or
            rebuilt.get('configurationId') != smoke.CONFIG or
            rebuilt.get('freshPass') != 'fresh1' or
            rebuilt.get('condition') != 'P0' or
            rebuilt.get('status') != 'partial_unscored_as_repeat' or
            rebuilt.get('denominator') != 60 or
            rebuilt.get('outcomes') != {'valid': 55, 'failed': 5,
                                       'neverSent': 0, 'failedIds': FAILED} or
            rebuilt.get('usage', {}).get('unknownChargeFailedIds') != FAILED or
            rebuilt.get('lineage', {}).get('referenceLabelsSent') is not False or
            rebuilt.get('lineage', {}).get('cleanRepeatabilityClaim') is not False or
            sum(x['attempted'] for x in rebuilt['lineage']['stages']) != 60):
        raise ValueError('Closed P0 evidence or fixed-60 outcome differs')
    return {'public_projection_sha256': sha(PUBLIC_P0),
            'source_bindings': rebuilt['lineage']['sourceBindings'],
            'valid': 55, 'failed': 5, 'never_sent': 0,
            'failed_ids': FAILED, 'repeat_pass_credit': False}


def manifest_value():
    predecessor = p0_gate()
    plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
    frozen.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
    requests = plan['conditions']['P1']
    if (plan['condition_order'] != study.ORDERS['fresh1'] or
            plan['reference_labels_read'] is not False or
            [r['record_id'] for r in requests['smoke']] != IDS[:3] or
            [r['record_id'] for r in requests['development']] != IDS):
        raise ValueError('Frozen fresh1/P1 request membership differs')
    for item in requests['smoke'] + requests['development']:
        if study.digest(json.dumps(item['payload'], sort_keys=True)) != item['request_sha256']:
            raise ValueError('Frozen P1 request payload differs')
    return {'schema': SCHEMA, 'status': 'offline_prepared_pending_root_review',
            'configuration_id': smoke.CONFIG, 'fresh_pass': 'fresh1',
            'condition': 'P1', 'reference_labels_read': False,
            'reference_labels_sent': False, 'predecessor': predecessor,
            'predecessor_gate_sha256': smoke.digest_bytes(smoke.canonical(predecessor)),
            'frozen_plan_sha256': prior.PLAN_SHA['fresh1'],
            'frozen_execution_manifest_sha256': smoke.EXECUTION_SHA,
            'source_sha256': {name: sha(study.ROOT / name) for name in SOURCE_PATHS},
            'input_file_sha256': sha(study.ROOT / study.INPUTS),
            'per_request_full_context_reserve_usd': str(study.RESERVE),
            'smoke_child_cap_usd': str(SMOKE_CAP),
            'development_child_cap_usd': str(DEVELOPMENT_CAP),
            'exact_route': {'model': study.MODEL, 'provider_tag': study.PROVIDER,
                            'context_tokens': study.CONTEXT,
                            'input_usd_per_million': str(study.INPUT_PRICE),
                            'output_usd_per_million': str(study.OUTPUT_PRICE),
                            'primary_source': 'https://openrouter.ai/api/v1/models/' +
                                              study.MODEL + '/endpoints',
                            'live_recheck_required': True},
            'smoke_requests': requests['smoke'],
            'development_requests': requests['development']}


def prepare(base=None):
    base = BASE if base is None else Path(base)
    value = manifest_value()
    path = Path(base) / 'manifest.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        paid.durable(out, value)
    return smoke.digest_bytes(smoke.canonical(value))


def verify(repeat='fresh1', condition='P1', base=None):
    if (repeat, condition) != ('fresh1', 'P1'):
        raise ValueError('Only fresh1/P1 is admitted')
    base = BASE if base is None else Path(base)
    value = saved(Path(base) / 'manifest.json')
    if value != manifest_value():
        raise ValueError('P1 successor manifest or P0 source differs')
    return value, smoke.digest_bytes(smoke.canonical(value))


def gate(repeat, condition, phase, manifest, manifest_sha):
    check_phase(phase)
    if (repeat, condition) != ('fresh1', 'P1') or manifest_sha != verify()[1]:
        raise ValueError('Wrong P1 successor stage or manifest')
    predecessor = p0_gate()
    if (manifest['predecessor'] != predecessor or
            manifest['predecessor_gate_sha256'] !=
            smoke.digest_bytes(smoke.canonical(predecessor))):
        raise ValueError('P0 predecessor source differs')
    result = {'predecessor': predecessor}
    if phase == 'development':
        with patch.object(prior, 'folder', lambda *_: BASE):
            result['smoke'] = prior.smoke_inspection(repeat, condition,
                                                     manifest, manifest_sha)
    return result


def budget_identity(phase, budget_manifest):
    check_phase(phase)
    path = Path(budget_manifest).resolve()
    if path != (BASE / f'{phase}.budget-manifest.json').resolve():
        raise ValueError('Wrong P1 budget manifest path')
    budget = saved(path)
    child = path.parent / (path.stem + '-' + PID[phase] + '.jsonl')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(smoke.MASTER.resolve()) or
            budget.get('partitions') != [{'id': PID[phase],
                'cap_usd': str(CAPS[phase]), 'model': study.MODEL,
                'provider': study.PROVIDER, 'reasoning': 'none',
                'child_ledger': str(child)}]):
        raise ValueError('P1 child partition differs')
    identity = {'successor_manifest_sha256': sha(BASE / 'manifest.json'),
                'budget_manifest_path': str(path),
                'budget_manifest_sha256': sha(path),
                'partition_id': PID[phase], 'child_ledger_path': str(child)}
    return smoke.digest_bytes(smoke.canonical(identity))


def expected_receipt(phase, manifest, manifest_sha, budget_manifest, binding):
    check_phase(phase)
    requests = manifest[phase + '_requests']
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': manifest_sha,
            'runner_sha256': manifest['source_sha256']['scripts/mistral119_p1_successor_v1.py'],
            'gate_sha256': smoke.digest_bytes(smoke.canonical(binding)),
            'budget_manifest_sha256': sha(budget_manifest),
            'budget_partition_id': PID[phase], 'child_cap_usd': str(CAPS[phase]),
            'global_hold_id': AUTHORITY_ID[phase],
            'global_hold_usd': str(CAPS[phase]),
            'global_hold_source_sha256': budget_identity(phase, budget_manifest),
            'global_authority_cap_usd': str(third.AUTHORITY_CAP),
            'global_authority_approval_sha256': third.AUTHORITY_APPROVAL_SHA,
            'fresh_pass': 'fresh1', 'condition': 'P1', 'phase': phase,
            'ids': [x['record_id'] for x in requests],
            'reference_labels_sent': False}


def review_receipt(path, repeat, condition, phase, manifest, manifest_sha,
                   budget_manifest, binding):
    if ((repeat, condition) != ('fresh1', 'P1') or
            Path(path).resolve() != (BASE / f'{phase}.root-review.json').resolve()):
        raise ValueError('Wrong P1 root receipt path')
    expected = expected_receipt(phase, manifest, manifest_sha, budget_manifest, binding)
    receipt = saved(path)
    head = receipt.get('global_authority_head_sha256')
    if (not isinstance(head, str) or len(head) != 64 or
            any(c not in '0123456789abcdef' for c in head) or
            receipt != {**expected, 'global_authority_head_sha256': head,
                        'reviewer': 'root'}):
        raise ValueError('P1 root receipt differs')
    return receipt


def hold_authority(phase, expected_head, source):
    check_phase(phase)
    with AUTHORITY.open('r+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = handle.read().encode()
        current_head = hashlib.sha256(raw).hexdigest()
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not events or events[0] != {'event': 'authority',
                'kind': 'postapproval-paid-work-v1',
                'cap_usd': str(third.AUTHORITY_CAP),
                'decision_key': third.AUTHORITY_DECISION_KEY,
                'approval_sha256': third.AUTHORITY_APPROVAL_SHA}:
            raise ValueError('Wrong shared paid-work authority')
        holds, total = set(), Decimal(0)
        existing = None
        for event in events[1:]:
            if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                    event['event'] != 'hold' or event['id'] in holds or
                    not isinstance(event['usd'], str)):
                raise ValueError('Malformed or duplicate shared hold')
            amount = Decimal(event['usd'])
            if not amount.is_finite() or amount <= 0:
                raise ValueError('Invalid shared hold amount')
            holds.add(event['id'])
            total += amount
            if event['id'] == AUTHORITY_ID[phase]:
                existing = event
        if total > third.AUTHORITY_CAP:
            raise ValueError('Shared authority exhausted')
        desired = {'event': 'hold', 'id': AUTHORITY_ID[phase],
                   'source_sha256': source, 'usd': str(CAPS[phase])}
        if existing is not None:
            if existing != desired:
                raise ValueError('Existing P1 hold differs from approved stage')
            if any(path.exists() for path in prior.phase_files(BASE, phase).values()):
                raise FileExistsError('P1 stage evidence exists; hold cannot authorize replay')
            return 'existing'
        if current_head != expected_head:
            raise ValueError('Cross-provider authority head changed')
        if total + CAPS[phase] > third.AUTHORITY_CAP:
            raise ValueError('Shared authority exhausted')
        handle.seek(0, 2)
        paid.durable(handle, desired)
        return 'new'


def run(phase, receipt_path, budget_manifest, *, send=None, live=None,
        open_child=None, load_key=None, env_file=None):
    check_phase(phase)
    manifest, digest = verify()
    binding = gate('fresh1', 'P1', phase, manifest, digest)
    receipt = review_receipt(receipt_path, 'fresh1', 'P1', phase,
                             manifest, digest, budget_manifest, binding)
    # The lock closes the gap between checking for a claim and reusing an
    # identical pre-dispatch hold after a crash or transient child-open error.
    with (BASE / f'{phase}.admission.lock').open('a+b') as admission:
        fcntl.flock(admission, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if any(path.exists() for path in prior.phase_files(BASE, phase).values()):
            raise FileExistsError('P1 stage already claimed; no replay')
        plan = study.verify(smoke.CONFIG, 'fresh1', prior.PLAN_SHA['fresh1'])
        live_fn = live if live is not None else frozen.live_controls
        model, endpoint, reserve = live_fn(plan, 'P1')
        if (model.get('id') != study.MODEL or endpoint.get('tag') != study.PROVIDER or
                reserve != study.RESERVE):
            raise ValueError('Exact route or full request reserve differs')
        source = budget_identity(phase, budget_manifest)
        open_fn = open_child if open_child is not None else partitions.open_partition
        ledger = open_fn(smoke.MASTER, budget_manifest, PID[phase],
                         study.MODEL, study.PROVIDER, 'none')
        try:
            _, pending, blocked = ledger.state()
            if (ledger.master_cap != Decimal('12.38') or
                    ledger.cap != CAPS[phase] or ledger.accounted() != 0 or
                    pending or blocked or ledger.closed):
                raise ValueError('P1 child partition is not fresh and funded')
        finally:
            ledger.close()
        key_fn = load_key if load_key is not None else paid.load_key
        key_fn(env_file)
        hold_authority(phase, receipt['global_authority_head_sha256'], source)
        kwargs = {'env_file': env_file}
        for name, value in (('send', send), ('live', live),
                            ('open_child', open_child), ('load_key', load_key)):
            if value is not None:
                kwargs[name] = value
        with patch.multiple(prior, SCHEMA=SCHEMA, BASE=BASE, folder=lambda *_: BASE,
                            verify=verify, gate=gate,
                            partition_id=lambda *args: PID[phase],
                            review_receipt=review_receipt, SMOKE_CAP=SMOKE_CAP,
                            DEVELOPMENT_CAP=DEVELOPMENT_CAP):
            return prior.run('fresh1', 'P1', phase, receipt_path,
                             budget_manifest, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--phase', choices=PHASES)
    parser.add_argument('--root-review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        print(verify()[1])
    else:
        if not args.phase or not args.root_review_receipt or not args.budget_manifest:
            parser.error('run requires --phase, --root-review-receipt and --budget-manifest')
        run(args.phase, args.root_review_receipt, args.budget_manifest,
            env_file=args.env_file)


if __name__ == '__main__':
    main()
