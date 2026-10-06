#!/usr/bin/env python3
"""Offline Jev v2 proposals and a separately reviewed execution bridge.

No command here allocates a child partition or releases an authority hold.
``run`` requires a root receipt, a preallocated exact child, and the live
v2 authority head. The old request, parser, response, and stop loop is loaded
into a private module so other runners retain their original globals.
"""
from __future__ import annotations

import argparse
import base64
from decimal import Decimal
import fcntl
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from development_benchmark import ROOT
import openrouter_decision_smoke as decision
import openrouter_jev_native_full_v1 as jev
import openrouter_jev_native_p0_full_v1 as p0
import openrouter_jev_p2_fresh2_suffix_v1 as suffix
import openrouter_native_variants_full_v1 as full
import openrouter_native_variants_plan as frozen
import openrouter_native_variants_v2 as smoke_v2
import postapproval_authority_v2 as authority_v2


BASE = ROOT / 'results/route-audits/jev-authority-v2-20261006'
TAIL_BASE = BASE / 'p2-fresh2-unsent-continuation'
TAIL_STAGE = 'tail'
TAIL_PARTITION = suffix.CONFIG + '-fresh2-DEV019-060-continuation-v2'
TAIL_SCHEMA = 'jev-openrouter-native-p2-fresh2-tail-v2'
COMPOSITE = BASE / 'p2-fresh2-composite.json'
COMPOSITE_REVIEW = BASE / 'p2-fresh2-composite.root-review.json'
AUTHORITY = smoke_v2.AUTHORITY
MASTER = full.MASTER
EXECUTION_LOCK = BASE / '.jev-execution.lock'


def _digest(path):
    return smoke_v2.file_sha(path)


def _write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    return _digest(path)


def _original_base(config):
    return p0.BASE if config == p0.CONFIG else jev.BASE


def _original_adapter(config):
    return p0 if config == p0.CONFIG else jev


def _source_bound(config, *, base=BASE, root=ROOT):
    if config not in (*jev.CONFIGS, p0.CONFIG):
        raise ValueError('Only frozen Jev P0/P1/P2 configurations are supported')
    adapter = _original_adapter(config)
    original_base = _original_base(config)
    old = adapter.verify(config, original_base, root=root)
    new = adapter.verify(config, base, root=root)
    old_path = full.paths(original_base, config)['manifest']
    new_path = full.paths(base, config)['manifest']
    if old != new or old_path.read_bytes() != new_path.read_bytes():
        raise ValueError('V2 proposal differs from frozen Jev manifest')
    return new, _digest(old_path)


def prepare(config, *, base=BASE, root=ROOT):
    """Copy only reviewed immutable inputs into an isolated proposal root."""
    adapter = _original_adapter(config)
    adapter.verify(config, _original_base(config), root=root)
    adapter.prepare(config, base, root=root)
    if config in jev.CONFIGS:
        for key in ('context', 'inspection'):
            old = full.paths(jev.BASE, config)[key]
            if old.is_file():
                new = full.paths(base, config)[key]
                with new.open('xb') as handle:
                    handle.write(old.read_bytes())
    return _source_bound(config, base=base, root=root)[1]


def _full_predecessor(config, stage, manifest, *, base=BASE):
    if config == p0.CONFIG:
        return p0.predecessor(config, stage, manifest, base=base)
    if stage == 'fresh1':
        raise ValueError('Historical Jev fresh1 is already complete')
    if stage == 'fresh2':
        raise ValueError('Historical Jev fresh2 is already attempted')
    if stage != 'fresh3':
        raise ValueError('Unknown Jev pass')
    if config == suffix.CONFIG:
        composite = verify_composite_review(base=base)
        return {'smoke_completion_sha256': manifest['smoke_proof']['completion_sha256'],
                'interrupted_fresh2_composite_sha256': _digest(Path(base) / COMPOSITE.relative_to(BASE)),
                'interrupted_fresh2_review_sha256': _digest(Path(base) / COMPOSITE_REVIEW.relative_to(BASE)),
                'interrupted_fresh2_status': composite['status'],
                'clean_repeat_credit': False}
    # P1 fresh2 has 59 valid and one saved invalid response. Its exact
    # historical completion is an admissible predecessor, without repair.
    return full.predecessor(config, stage, manifest, base=jev.BASE)


def _full_expected(base_expected, config, stage, manifest, budget_path,
                   context_sha, inspection_sha, predecessor_proof, hold_source,
                   *, base=BASE):
    value = base_expected(config, stage, manifest, budget_path, context_sha,
                          inspection_sha, predecessor_proof, hold_source, base=base)
    value['bridge_sha256'] = _digest(__file__)
    value['authority_module_sha256'] = _digest(authority_v2.__file__)
    value['frozen_execution_core_sha256'] = _digest(full.__file__)
    value['frozen_execution_adapter_sha256'] = _digest(_original_adapter(config).__file__)
    value['original_manifest_sha256'] = _digest(full.paths(_original_base(config), config)['manifest'])
    value['original_request_set_sha256'] = manifest['request_set_sha256']
    if config == p0.CONFIG:
        value['p0_adapter_sha256'] = _digest(p0.__file__)
        value['jev_evidence_helper_sha256'] = _digest(jev.__file__)
    else:
        value['execution_adapter_sha256'] = _digest(jev.__file__)
    return value


def _private_core():
    spec = importlib.util.spec_from_file_location('_jev_v2_private_full_core', full.__file__)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    # A namespace copy keeps the historical smoke module unchanged in this
    # process and in any concurrent process that imported it already.
    private_smoke = SimpleNamespace(**vars(smoke_v2))
    private_smoke.hold_authority = authority_v2.hold_authority
    core.smoke_v2 = private_smoke
    return core


def _full_core(config, *, base=BASE, root=ROOT):
    core = _private_core()
    base_expected = core.expected_receipt
    adapter = _original_adapter(config)

    def verify(conf, source_base=base, *, root=root, smoke_base=smoke_v2.BASE):
        manifest, _ = _source_bound(conf, base=source_base, root=root)
        return manifest

    def expected(conf, stage, manifest, budget_path, context_sha, inspection_sha,
                 predecessor_proof, hold_source, *, base=base):
        return _full_expected(base_expected, conf, stage, manifest, budget_path,
                              context_sha, inspection_sha, predecessor_proof,
                              hold_source, base=base)

    core.verify = verify
    core.expected_receipt = expected
    core.predecessor = _full_predecessor
    if config == p0.CONFIG:
        core.smoke_inspection = p0.smoke_inspection
        core.frozen = p0._P0Plan
    return core


def tail_manifest(*, root=ROOT):
    """Regenerate the exact 42 original requests and immutable parent proof."""
    proposal = suffix.build_manifest(root=root)
    original = frozen.build_plan(root)[suffix.CONFIG]
    requests = original['requests'][18:]
    if ([x['id'] for x in requests] != suffix.IDS or
            proposal['request_sha256'] != [x['payload_sha256'] for x in requests] or
            suffix.UNKNOWN in suffix.IDS or
            Decimal(proposal['whole_suffix_full_context_bound_usd']) != Decimal('0.056448000')):
        raise ValueError('Tail is not the exact never-sent 42')
    old = jev.verify(suffix.CONFIG, jev.BASE, root=root)
    return {'schema': TAIL_SCHEMA + '-offline-plan', 'status': 'proposed_not_admitted',
            'inference_performed': False, 'reference_labels_read': False,
            'configuration_id': suffix.CONFIG, 'route': 'jev', 'condition': 'P2',
            'model': old['model'], 'provider': old['provider'],
            'provider_tag': old['provider_tag'], 'returned_model': old['returned_model'],
            'context_tokens': old['context_tokens'],
            'request_set_sha256': decision.sha(decision.canonical(requests)),
            'ids': suffix.IDS, 'request_sha256': proposal['request_sha256'],
            'per_request_full_context_bound_usd': proposal['per_request_full_context_bound_usd'],
            'whole_pass_bound_usd': proposal['whole_suffix_full_context_bound_usd'],
            'budget_master_cap_usd': '12.38', 'global_authority_cap_usd': '10.00',
            'passes': [{'stage': TAIL_STAGE, 'partition_id': TAIL_PARTITION,
                        'status': 'proposed_not_admitted'}],
            'original_manifest_sha256': _digest(full.paths(jev.BASE, suffix.CONFIG)['manifest']),
            'original_request_set_sha256': original['requests_sha256'],
            'original_request_sha256': proposal['original_request_sha256'],
            'parent_evidence': proposal['parent_evidence'],
            'parent_terminal_status': 'stopped_http_429',
            'attempted_unknown_id': suffix.UNKNOWN,
            'continuation_is_clean_repeat': False,
            'frozen_execution_core_sha256': _digest(full.__file__),
            'frozen_execution_adapter_sha256': _digest(jev.__file__),
            'frozen_suffix_proposal_sha256': _digest(suffix.__file__),
            'bridge_sha256': _digest(__file__),
            'authority_module_sha256': _digest(authority_v2.__file__)}


def prepare_tail(*, base=TAIL_BASE, root=ROOT):
    return _write_new(full.paths(base, suffix.CONFIG)['manifest'], tail_manifest(root=root))


def verify_tail(*, base=TAIL_BASE, root=ROOT):
    value = tail_manifest(root=root)
    path = full.paths(base, suffix.CONFIG)['manifest']
    if path.read_bytes() != (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Tail proposal differs from exact frozen requests or parent')
    return value


class _TailPlan:
    @staticmethod
    def build_plan(root=ROOT):
        original = frozen.build_plan(root)[suffix.CONFIG]
        rows = original['requests'][18:]
        if [x['id'] for x in rows] != suffix.IDS:
            raise ValueError('Frozen tail IDs changed')
        return {suffix.CONFIG: {'requests': rows,
                                'requests_sha256': decision.sha(decision.canonical(rows))}}


def _tail_context(config, manifest, *, base=TAIL_BASE):
    if config != suffix.CONFIG or manifest['ids'] != suffix.IDS:
        raise ValueError('Wrong tail context')
    jev.verify(config, jev.BASE)
    original = full.paths(jev.BASE, config)['context']
    proof = json.loads(original.read_text())
    old = jev.verify(config, jev.BASE)
    if (proof.get('request_set_sha256') != manifest['original_request_set_sha256'] or
            old['ids'] != full.IDS or
            old['request_sha256'] != manifest['original_request_sha256']):
        raise ValueError('Original all-60 context proof differs')
    # The frozen estimate also covers these same 42 payload hashes.
    full.context_proof(config, old, base=jev.BASE)
    return _digest(original)


def _tail_inspection(config, manifest, *, base=TAIL_BASE):
    old = jev.verify(config, jev.BASE)
    return full.smoke_inspection(config, old, base=jev.BASE)


def _tail_predecessor(config, stage, manifest, *, base=TAIL_BASE):
    if config != suffix.CONFIG or stage != TAIL_STAGE:
        raise ValueError('Unknown tail identity')
    source = suffix.inspect_parent()
    if (source != manifest['parent_evidence'] or
            source['unknown_attempted_id'] != suffix.UNKNOWN or
            source['never_sent_ids'] != suffix.IDS):
        raise ValueError('Closed interrupted parent changed')
    return {'parent_terminal_sha256': source['parent_source_sha256']['terminal-public.json'],
            'parent_attempts_sha256': source['parent_source_sha256']['attempts.jsonl'],
            'parent_child_sha256': source['parent_source_sha256']['child_ledger'],
            'attempted_unknown_id': suffix.UNKNOWN,
            'continuation_ids': suffix.IDS, 'clean_repeat_credit': False}


def _tail_core(*, base=TAIL_BASE):
    core = _private_core()
    base_expected = core.expected_receipt
    core.PASSES = (TAIL_STAGE,)
    core.IDS = suffix.IDS
    core.SCHEMA = TAIL_SCHEMA
    core.frozen = _TailPlan

    def verify(conf, source_base=base, *, root=ROOT, smoke_base=smoke_v2.BASE):
        if conf != suffix.CONFIG:
            raise ValueError('Wrong tail configuration')
        return verify_tail(base=source_base, root=root)

    def expected(conf, stage, manifest, budget_path, context_sha, inspection_sha,
                 predecessor_proof, hold_source, *, base=base):
        value = base_expected(conf, stage, manifest, budget_path, context_sha,
                              inspection_sha, predecessor_proof, hold_source, base=base)
        for key in ('original_manifest_sha256', 'original_request_set_sha256',
                    'original_request_sha256', 'parent_evidence', 'parent_terminal_status',
                    'attempted_unknown_id', 'continuation_is_clean_repeat',
                    'frozen_execution_core_sha256', 'frozen_execution_adapter_sha256',
                    'frozen_suffix_proposal_sha256', 'bridge_sha256',
                    'authority_module_sha256'):
            value[key] = manifest[key]
        return value

    core.verify = verify
    core.context_proof = _tail_context
    core.smoke_inspection = _tail_inspection
    core.predecessor = _tail_predecessor
    core.expected_receipt = expected
    return core


def expected_review(config, stage, budget_path, *, base=BASE):
    """Build a reviewable receipt body after an exact child is allocated."""
    is_tail = stage == TAIL_STAGE
    source_base = Path(base) / TAIL_BASE.relative_to(BASE) if is_tail else base
    core = _tail_core(base=source_base) if is_tail else _full_core(config, base=source_base)
    manifest = core.verify(config, source_base)
    context_sha = core.context_proof(config, manifest, base=source_base)
    inspection_sha = core.smoke_inspection(config, manifest, base=source_base)
    prior = core.predecessor(config, stage, manifest, base=source_base)
    source = core.budget_identity(config, stage, manifest, budget_path,
                                  base=source_base, master=MASTER)
    return core.expected_receipt(config, stage, manifest, budget_path,
                                 context_sha, inspection_sha, prior, source,
                                 base=source_base)


def execute(config, stage, receipt_path, budget_path, *, base=BASE, **kwargs):
    """Dispatch only with root receipt and the exact preallocated child."""
    if stage == TAIL_STAGE:
        if config != suffix.CONFIG:
            raise ValueError('Only P2 fresh2 has a tail')
        source_base = Path(base) / TAIL_BASE.relative_to(BASE)
        core = _tail_core(base=source_base)
    else:
        source_base = base
        core = _full_core(config, base=source_base)
    # One Jev worker at a time after the observed HTTP 429. The cloned core
    # checks the exact receipt, request plan, route catalogue, $12.38 child
    # and v2 $10 hold before the first transport call.
    lock_path = Path(base) / EXECUTION_LOCK.relative_to(BASE)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        authority_path = kwargs.pop('authority', AUTHORITY)
        receipt = json.loads(Path(receipt_path).read_text())
        if (receipt.get('global_authority_head_sha256') !=
                authority_v2.read_authority(authority_path).head_sha256):
            raise ValueError('Stale v2 authority head before transport')
        return core.execute(config, stage, receipt_path, budget_path,
                            base=source_base, authority=authority_path, **kwargs)


def build_composite(*, base=BASE):
    """Close analysis of all 60 positions without changing the parent run."""
    suffix.inspect_parent()
    tail_base = Path(base) / TAIL_BASE.relative_to(BASE)
    manifest = verify_tail(base=tail_base)
    stage = full.paths(tail_base, suffix.CONFIG, TAIL_STAGE)['stage']
    completion = json.loads((stage / 'completion.json').read_text())
    attempts_path = stage / 'attempts.jsonl'
    attempts = [json.loads(line) for line in attempts_path.read_text().splitlines() if line]
    budget_path = full.paths(tail_base, suffix.CONFIG, TAIL_STAGE)['budget']
    receipt_path = full.paths(tail_base, suffix.CONFIG, TAIL_STAGE)['receipt']
    core = _tail_core(base=tail_base)
    context_sha = core.context_proof(suffix.CONFIG, manifest, base=tail_base)
    inspection_sha = core.smoke_inspection(suffix.CONFIG, manifest, base=tail_base)
    prior = core.predecessor(suffix.CONFIG, TAIL_STAGE, manifest, base=tail_base)
    hold_source = core.budget_identity(suffix.CONFIG, TAIL_STAGE, manifest,
                                       budget_path, base=tail_base, master=MASTER)
    core.validate_receipt(suffix.CONFIG, TAIL_STAGE, manifest, receipt_path,
                          budget_path, context_sha, inspection_sha, prior,
                          hold_source, base=tail_base)
    if (completion.get('schema') != TAIL_SCHEMA + '-completion' or
            completion.get('configuration_id') != suffix.CONFIG or
            completion.get('stage') != TAIL_STAGE or
            completion.get('ids') != suffix.IDS or
            completion.get('manifest_sha256') != _digest(full.paths(tail_base, suffix.CONFIG)['manifest']) or
            completion.get('receipt_sha256') != _digest(receipt_path) or
            completion.get('budget_manifest_sha256') != _digest(budget_path) or
            _digest(stage / 'review-receipt.json') != _digest(receipt_path) or
            completion.get('reference_labels_read') is not False or
            completion.get('attempts_sha256') != _digest(attempts_path) or
            len(attempts) != 4 * 42 or
            completion.get('valid_count', -1) + completion.get('invalid_count', -1) != 42):
        raise ValueError('Tail has no complete 42-position terminal')
    invalid = []
    known = Decimal(0)
    original = frozen.build_plan()[suffix.CONFIG]['requests'][18:]
    route = decision.ROUTES['jev']
    for index, rid in enumerate(suffix.IDS):
        group = attempts[4*index:4*index+4]
        item = original[index]
        request = base64.b64decode(group[1].get('request_base64', ''), validate=True)
        raw = base64.b64decode(group[2].get('raw_response_base64', ''), validate=True)
        body = json.loads(raw)
        cost = decision.response_cost(body)
        if ([x.get('stage') for x in group] != ['reserved', 'started', 'response', 'parsed'] or
                any(x.get('id') != rid for x in group) or
                len({x.get('attempt_id') for x in group}) != 1 or
                item['id'] != rid or group[0].get('request_sha256') != item['payload_sha256'] or
                request != decision.canonical(item['payload']) or
                group[2].get('http_status') != 200 or
                group[2].get('raw_response_sha256') != decision.sha(raw) or
                group[2].get('body') != body or
                body.get('model') != route['version'] or body.get('provider') != route['provider'] or
                group[2].get('cost_unknown') is not False or
                cost is None or group[2].get('actual_cost_usd') != str(cost) or
                type(group[3].get('valid')) is not bool):
            raise ValueError('Tail attempt stream differs')
        known += cost
        if group[3]['valid'] and decision.validate_response(body, route) != group[3].get('prediction'):
            raise ValueError('Tail parsed prediction differs from raw')
        if not group[3]['valid']:
            invalid.append(rid)
    if (completion['invalid_ids'] != invalid or
            completion['valid_count'] != 42-len(invalid) or
            Decimal(completion['known_actual_cost_usd']) != known):
        raise ValueError('Tail completion counts or cost differ')
    budget = json.loads(budget_path.read_text())
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(MASTER) or
            not isinstance(entries, list) or len(entries) != 1 or
            entries[0].get('id') != TAIL_PARTITION or
            Decimal(entries[0].get('cap_usd', '-1')) != suffix.TAIL_BOUND):
        raise ValueError('Tail budget identity differs')
    child_path = Path(entries[0].get('child_ledger', ''))
    expected_child = budget_path.parent / (budget_path.stem + '-' + TAIL_PARTITION + '.jsonl')
    if child_path != expected_child or child_path.is_symlink():
        raise ValueError('Tail child path differs')
    child = [json.loads(line) for line in child_path.read_text().splitlines() if line]
    if (len(child) != 2 + 2*42 or
            child[0] != {'event': 'budget', 'cap_usd': str(suffix.TAIL_BOUND)} or
            child[-1].get('event') != 'partition_closed'):
        raise ValueError('Tail child is not closed for 42 attempts')
    for index, rid in enumerate(suffix.IDS):
        group = attempts[4*index:4*index+4]
        aid = group[0]['attempt_id']
        if (child[1+2*index] != {'event': 'reserve', 'attempt_id': aid,
                                 'record_id': TAIL_PARTITION + ':' + rid,
                                 'usd': str(suffix.BOUND)} or
                child[2+2*index] != {'event': 'settle', 'attempt_id': aid,
                                     'usd': group[2]['actual_cost_usd']}):
            raise ValueError('Tail child and attempts differ')
    reconciliation_path = stage / 'budget-reconciliation.json'
    reconciliation = json.loads(reconciliation_path.read_text())
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != TAIL_PARTITION or
            reconciliation.get('child_ledger') != str(child_path) or
            reconciliation.get('child_sha256') != _digest(child_path) or
            Decimal(reconciliation.get('known_actual_usd', '-1')) != known or
            Decimal(reconciliation.get('unknown_upper_bound_usd', '-1')) != 0 or
            Decimal(reconciliation.get('unused_allocation_released_usd', '-1')) !=
            suffix.TAIL_BOUND - known):
        raise ValueError('Tail partition reconciliation differs')
    master = [json.loads(line) for line in MASTER.read_text().splitlines() if line]
    if sum(event == reconciliation for event in master) != 1:
        raise ValueError('Master lacks unique tail reconciliation')
    return {'schema': TAIL_SCHEMA + '-60-record-composite',
            'status': 'interrupted_parent_with_unsent_continuation',
            'clean_repeat_credit': False, 'configuration_id': suffix.CONFIG,
            'pass': 'fresh2', 'ids': full.IDS,
            'valid_count': 17 + completion['valid_count'],
            'invalid_count': 1 + completion['invalid_count'],
            'invalid_ids': [suffix.UNKNOWN, *invalid],
            'attempted_unknown_id': suffix.UNKNOWN,
            'unknown_charge_upper_bound_usd': str(suffix.BOUND),
            'parent_terminal_sha256': suffix.PINNED['terminal-public.json'],
            'parent_attempts_sha256': suffix.PINNED['attempts.jsonl'],
            'tail_manifest_sha256': _digest(full.paths(tail_base, suffix.CONFIG)['manifest']),
            'tail_completion_sha256': _digest(stage / 'completion.json'),
            'tail_attempts_sha256': _digest(attempts_path),
            'tail_reconciliation_sha256': _digest(reconciliation_path),
            'tail_child_sha256': _digest(child_path),
            'reference_labels_read': False}


def prepare_composite(*, base=BASE):
    return _write_new(Path(base) / COMPOSITE.relative_to(BASE), build_composite(base=base))


def verify_composite(*, base=BASE):
    expected = build_composite(base=base)
    path = Path(base) / COMPOSITE.relative_to(BASE)
    if path.read_bytes() != (json.dumps(expected, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Saved interrupted composite differs')
    return expected


def verify_composite_review(*, base=BASE):
    composite = verify_composite(base=base)
    path = Path(base) / COMPOSITE_REVIEW.relative_to(BASE)
    review = json.loads(path.read_text())
    if review != {'schema': TAIL_SCHEMA + '-60-record-composite-root-review',
                  'approved': True, 'reviewer': 'root',
                  'configuration_id': suffix.CONFIG, 'pass': 'fresh2',
                  'composite_sha256': _digest(Path(base) / COMPOSITE.relative_to(BASE)),
                  'parent_terminal_sha256': suffix.PINNED['terminal-public.json'],
                  'attempted_unknown_id': suffix.UNKNOWN,
                  'clean_repeat_credit': False}:
        raise ValueError('Root review of interrupted composite differs')
    return composite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'prepare-tail',
                                          'verify-tail', 'prepare-composite',
                                          'verify-composite', 'run'))
    parser.add_argument('--configuration', choices=(*jev.CONFIGS, p0.CONFIG))
    parser.add_argument('--stage', choices=(*full.PASSES, TAIL_STAGE))
    parser.add_argument('--review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    args = parser.parse_args()
    if args.action in ('prepare', 'verify', 'run') and args.configuration is None:
        parser.error('configuration required')
    if args.action == 'prepare':
        print(prepare(args.configuration))
    elif args.action == 'verify':
        print(_source_bound(args.configuration)[1])
    elif args.action == 'prepare-tail':
        print(prepare_tail())
    elif args.action == 'verify-tail':
        print(verify_tail()['whole_pass_bound_usd'])
    elif args.action == 'prepare-composite':
        print(prepare_composite())
    elif args.action == 'verify-composite':
        print(verify_composite()['status'])
    else:
        if args.stage is None or args.review_receipt is None or args.budget_manifest is None:
            parser.error('run requires stage, review receipt and budget manifest')
        print(json.dumps(execute(args.configuration, args.stage, args.review_receipt,
                                 args.budget_manifest), indent=2))


if __name__ == '__main__':
    main()
