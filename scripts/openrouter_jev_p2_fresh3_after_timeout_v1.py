#!/usr/bin/env python3
"""Separate Jev P2 fresh3 bridge after a fully attempted, interrupted fresh2.

Preparation and verification are offline. A later `run` still requires an
independent root receipt, exact child allocation, live route/context checks,
v2 authority head, and the unchanged frozen request/response core.
"""
from __future__ import annotations

import argparse
import base64
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as decision
import openrouter_jev_authority_v2 as bridge
import openrouter_jev_p2_fresh2_suffix_v1 as suffix
import openrouter_native_variants_full_v1 as full
import openrouter_native_variants_plan as frozen
import openrouter_native_variants_v2 as smoke_v2
import postapproval_authority_v2 as authority


CONFIG = suffix.CONFIG
STAGE = 'fresh3'
BASE = bridge.BASE
PROPOSAL = BASE / 'p2-fresh3-after-timeout-v1' / 'proposal.json'
SCHEMA = 'jev-p2-fresh3-after-timeout-v1'


def _sha(path):
    return smoke_v2.file_sha(path)


def _rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Evidence stream has no terminal newline')
    return [json.loads(row, object_pairs_hook=authority._object) for row in raw.splitlines()]


def _master_events(master_path):
    with Path(master_path).open('rb') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return authority._lines(handle.read())[0]


def interrupted_predecessor(*, base=BASE, master_path=bridge.MASTER):
    """Prove all 60 positions attempted, with both unknown bounds retained."""
    parent = suffix.inspect_parent()
    tail_base = Path(base) / bridge.TAIL_BASE.relative_to(bridge.BASE)
    manifest = bridge.verify_tail(base=tail_base)
    p = full.paths(tail_base, CONFIG, bridge.TAIL_STAGE)
    stage = p['stage']
    if (stage / 'completion.json').exists():
        raise ValueError('Interrupted tail unexpectedly has completion')
    core = bridge._tail_core(base=tail_base)
    context = core.context_proof(CONFIG, manifest, base=tail_base)
    inspection = core.smoke_inspection(CONFIG, manifest, base=tail_base)
    prior = core.predecessor(CONFIG, bridge.TAIL_STAGE, manifest, base=tail_base)
    source = core.budget_identity(CONFIG, bridge.TAIL_STAGE, manifest, p['budget'],
                                  base=tail_base, master=master_path)
    core.validate_receipt(CONFIG, bridge.TAIL_STAGE, manifest, p['receipt'],
                          p['budget'], context, inspection, prior, source, base=tail_base)
    if _sha(stage / 'review-receipt.json') != _sha(p['receipt']):
        raise ValueError('Tail review receipt changed after admission')
    terminal = json.loads((stage / 'terminal-public.json').read_bytes(),
                          object_pairs_hook=authority._object)
    attempts_path = stage / 'attempts.jsonl'
    attempts = _rows(attempts_path)
    unknown_path = stage / 'unknown-cost-evidence.jsonl'
    unknown = _rows(unknown_path)
    expected_ids = suffix.IDS
    if (terminal != {'schema': 'jev-native-tail-interruption-v2',
                     'configuration_id': CONFIG, 'stage': bridge.TAIL_STAGE,
                     'status': 'stopped_transport_timeout', 'attempted': 42,
                     'saved_responses': 41, 'valid_count': 40,
                     'invalid_ids': ['DEV-040'], 'unknown_ids': ['DEV-060'],
                     'never_sent_ids': [], 'known_actual_cost_usd': '0.004681740',
                     'unknown_charge_upper_bound_usd': str(suffix.BOUND),
                     'attempts_sha256': _sha(attempts_path),
                     'reference_labels_read': False, 'replayed_failed_request': False,
                     'clean_repeat_credit': False} or len(attempts) != 41*4 + 3 or
            len(unknown) != 1 or unknown[0] != attempts[-1]):
        raise ValueError('Tail terminal or unknown evidence differs')
    original = frozen.build_plan()[CONFIG]['requests'][18:]
    if ([item['id'] for item in original] != expected_ids or
            [item['payload_sha256'] for item in original] != manifest['request_sha256'] or
            manifest['original_manifest_sha256'] != _sha(full.paths(bridge.jev.BASE, CONFIG)['manifest'])):
        raise ValueError('Tail requests differ from frozen full P2')
    budget = json.loads(p['budget'].read_bytes(), object_pairs_hook=authority._object)
    entries = budget.get('partitions')
    if (budget.get('master_ledger') != str(Path(master_path).resolve()) or
            budget.get('version') != 'paid-partitions-v1' or
            not isinstance(entries, list) or len(entries) != 1 or
            entries[0].get('id') != bridge.TAIL_PARTITION or
            Decimal(entries[0].get('cap_usd', '-1')) != suffix.TAIL_BOUND):
        raise ValueError('Tail partition budget differs')
    child_path = Path(entries[0]['child_ledger'])
    if child_path != p['budget'].parent / (p['budget'].stem + '-' + bridge.TAIL_PARTITION + '.jsonl'):
        raise ValueError('Tail child path differs')
    with Path(master_path).open('rb') as master, child_path.open('rb') as child:
        fcntl.flock(master, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(child, fcntl.LOCK_EX | fcntl.LOCK_NB)
        master_events = authority._lines(master.read())[0]
        child_raw = child.read()
    child_events = authority._lines(child_raw)[0]
    if (len(child_events) != 86 or
            child_events[0] != {'event': 'budget', 'cap_usd': str(suffix.TAIL_BOUND)} or
            child_events[-1].get('event') != 'partition_closed'):
        raise ValueError('Tail child is not closed for all 42 attempts')
    route = decision.ROUTES['jev']
    known = Decimal(0)
    invalid = []
    for index, item in enumerate(original[:41]):
        rid = item['id']
        group = attempts[4*index:4*index+4]
        reserve, started, response, parsed = group
        aid = reserve.get('attempt_id')
        request = base64.b64decode(started.get('request_base64', ''), validate=True)
        raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
        body = json.loads(raw)
        cost = decision.response_cost(body)
        if ([row.get('stage') for row in group] != ['reserved','started','response','parsed'] or
                any(row.get('id') != rid or row.get('attempt_id') != aid for row in group) or
                reserve.get('request_sha256') != item['payload_sha256'] or
                request != decision.canonical(item['payload']) or
                response.get('http_status') != 200 or response.get('cost_unknown') is not False or
                response.get('raw_response_sha256') != decision.sha(raw) or
                response.get('body') != body or body.get('model') != route['version'] or
                body.get('provider') != route['provider'] or
                cost is None or response.get('actual_cost_usd') != str(cost) or
                child_events[1+2*index] != {'event': 'reserve', 'attempt_id': aid,
                    'record_id': bridge.TAIL_PARTITION + ':' + rid, 'usd': str(suffix.BOUND)} or
                child_events[2+2*index] != {'event': 'settle', 'attempt_id': aid, 'usd': str(cost)}):
            raise ValueError('Tail request, response or settlement differs: ' + rid)
        known += cost
        if parsed.get('valid') is True:
            if decision.validate_response(body, route) != parsed.get('prediction'):
                raise ValueError('Tail valid parsed result differs: ' + rid)
        elif parsed.get('valid') is False:
            try:
                decision.validate_response(body, route)
            except ValueError as error:
                if str(error) != parsed.get('reason'):
                    raise ValueError('Tail invalid reason differs: ' + rid) from error
            else:
                raise ValueError('Tail marked a valid raw response invalid: ' + rid)
            invalid.append(rid)
        else:
            raise ValueError('Tail result lacks validity: ' + rid)
    reserve, started, failed = attempts[-3:]
    rid = 'DEV-060'
    aid = reserve.get('attempt_id')
    request = base64.b64decode(started.get('request_base64', ''), validate=True)
    if ([row.get('stage') for row in (reserve, started, failed)] !=
            ['reserved', 'started', 'transport_error'] or
            any(row.get('id') != rid or row.get('attempt_id') != aid for row in
                (reserve, started, failed)) or
            reserve.get('request_sha256') != original[-1]['payload_sha256'] or
            request != decision.canonical(original[-1]['payload']) or
            failed.get('error_type') != 'TimeoutError' or
            failed.get('cost_unknown') is not True or
            failed.get('reserved_cost_usd') != str(suffix.BOUND) or
            child_events[83] != {'event': 'reserve', 'attempt_id': aid,
                'record_id': bridge.TAIL_PARTITION + ':' + rid, 'usd': str(suffix.BOUND)} or
            child_events[84].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            child_events[84].get('attempt_id') != aid or
            child_events[84].get('usd') != str(suffix.BOUND) or
            child_events[84].get('actual_cost_usd') is not None or
            child_events[84].get('evidence_sha256') != _sha(unknown_path) or
            Path(child_events[84].get('evidence_path', '')).resolve() != unknown_path.resolve()):
        raise ValueError('DEV-060 timeout or unknown charge bound differs')
    if invalid != ['DEV-040'] or known != Decimal('0.004681740'):
        raise ValueError('Tail invalid outcome or known charge differs')
    reconciliation_path = stage / 'budget-reconciliation.json'
    reconciliation = json.loads(reconciliation_path.read_bytes(),
                                object_pairs_hook=authority._object)
    if (reconciliation != {'event': 'partition_reconciled',
            'partition_id': bridge.TAIL_PARTITION, 'known_actual_usd': str(known),
            'unknown_upper_bound_usd': str(suffix.BOUND),
            'unused_allocation_released_usd': str(suffix.TAIL_BOUND-known-suffix.BOUND),
            'child_ledger': str(child_path), 'child_sha256': hashlib.sha256(child_raw).hexdigest()} or
            sum(row == reconciliation for row in master_events) != 1):
        raise ValueError('Tail child/master reconciliation differs')
    parent_reconciliation = json.loads((suffix.PARENT / 'budget-reconciliation.json').read_bytes())
    if sum(row == parent_reconciliation for row in master_events) != 1:
        raise ValueError('Parent child/master reconciliation differs')
    return {'schema': SCHEMA + '-predecessor-proof', 'configuration_id': CONFIG,
            'prior_stage': 'fresh2', 'status': 'interrupted_all_60_attempted',
            'clean_repeat_credit': False, 'total_positions': 60,
            'valid_count': 57, 'intrinsic_invalid_ids': ['DEV-040'],
            'unknown_charge_ids': [suffix.UNKNOWN, 'DEV-060'],
            'never_sent_ids': [], 'parent_evidence': parent,
            'parent_terminal_sha256': _sha(suffix.PARENT / 'terminal-public.json'),
            'parent_reconciliation_sha256': _sha(suffix.PARENT / 'budget-reconciliation.json'),
            'tail_manifest_sha256': _sha(full.paths(tail_base, CONFIG)['manifest']),
            'tail_review_sha256': _sha(p['receipt']),
            'tail_terminal_sha256': _sha(stage / 'terminal-public.json'),
            'tail_attempts_sha256': _sha(attempts_path),
            'tail_unknown_evidence_sha256': _sha(unknown_path),
            'tail_reconciliation_sha256': _sha(reconciliation_path),
            'tail_child_sha256': hashlib.sha256(child_raw).hexdigest(),
            'known_actual_cost_usd': str(Decimal(parent['known_actual_cost_usd'])+known),
            'retained_unknown_upper_bound_usd': str(Decimal(parent['unknown_charge_upper_bound_usd'])+suffix.BOUND),
            'reference_labels_read': False}


def proposal(*, base=BASE):
    manifest, original_sha = bridge._source_bound(CONFIG, base=base)
    predecessor = interrupted_predecessor(base=base)
    core = bridge._full_core(CONFIG, base=base)
    context_sha = core.context_proof(CONFIG, manifest, base=base)
    inspection_sha = core.smoke_inspection(CONFIG, manifest, base=base)
    return {'schema': SCHEMA + '-offline-proposal', 'status': 'proposed_not_admitted',
            'configuration_id': CONFIG, 'stage': STAGE, 'inference_performed': False,
            'new_authority_hold_or_budget_allocation': False,
            'clean_repeat_credit': False,
            'original_manifest_sha256': original_sha,
            'v2_manifest_sha256': _sha(full.paths(base, CONFIG)['manifest']),
            'frozen_request_set_sha256': manifest['request_set_sha256'],
            'frozen_core_sha256': _sha(full.__file__),
            'bridge_sha256': _sha(bridge.__file__),
            'wrapper_sha256': _sha(__file__),
            'authority_module_sha256': _sha(authority.__file__),
            'context_proof_sha256': context_sha,
            'smoke_inspection_sha256': inspection_sha,
            'predecessor_proof': predecessor,
            'predecessor_proof_sha256': decision.sha(decision.canonical(predecessor)),
            'global_authority_cap_usd': '10.00',
            'master_cap_usd': '12.38',
            'whole_pass_bound_usd': manifest['whole_pass_bound_usd'],
            'required_before_run': ['new exact child allocation', 'root-reviewed fresh3 receipt',
                                    'live route, context, smoke, authority and master checks']}


def prepare(path=PROPOSAL, *, base=BASE):
    value = proposal(base=base)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    return _sha(path)


def verify(path=PROPOSAL, *, base=BASE):
    expected = proposal(base=base)
    if Path(path).read_bytes() != (json.dumps(expected, indent=2, ensure_ascii=False)+'\n').encode():
        raise ValueError('Saved fresh3 proposal differs from sources')
    return expected


def _core(*, base=BASE, proposal_path=PROPOSAL):
    core = bridge._full_core(CONFIG, base=base)
    original_expected = core.expected_receipt

    def predecessor(config, stage, manifest, *, base=base):
        if config != CONFIG or stage != STAGE:
            raise ValueError('Only Jev P2 fresh3 is supported')
        saved = verify(proposal_path, base=base)
        source = interrupted_predecessor(base=base)
        if (source != saved['predecessor_proof'] or
                manifest['request_set_sha256'] != saved['frozen_request_set_sha256']):
            raise ValueError('Interrupted predecessor or frozen requests changed')
        return source

    def expected(config, stage, manifest, budget_path, context_sha, inspection_sha,
                 predecessor_proof, hold_source, *, base=base):
        value = original_expected(config, stage, manifest, budget_path, context_sha,
                                  inspection_sha, predecessor_proof, hold_source, base=base)
        value['fresh3_after_timeout_wrapper_sha256'] = _sha(__file__)
        value['fresh3_after_timeout_proposal_sha256'] = _sha(proposal_path)
        value['fresh3_after_timeout_predecessor_sha256'] = decision.sha(
            decision.canonical(predecessor_proof))
        return value

    core.predecessor = predecessor
    core.expected_receipt = expected
    return core


def expected_review(budget_path, *, base=BASE, proposal_path=PROPOSAL):
    core = _core(base=base, proposal_path=proposal_path)
    manifest = core.verify(CONFIG, base)
    context_sha = core.context_proof(CONFIG, manifest, base=base)
    inspection_sha = core.smoke_inspection(CONFIG, manifest, base=base)
    prior = core.predecessor(CONFIG, STAGE, manifest, base=base)
    source = core.budget_identity(CONFIG, STAGE, manifest, budget_path,
                                  base=base, master=bridge.MASTER)
    return core.expected_receipt(CONFIG, STAGE, manifest, budget_path,
                                 context_sha, inspection_sha, prior, source, base=base)


def execute(receipt_path, budget_path, *, base=BASE, proposal_path=PROPOSAL,
            authority_path=bridge.AUTHORITY, **kwargs):
    """Use the frozen bridge checks with only the predecessor substituted."""
    core = _core(base=base, proposal_path=proposal_path)
    lock_path = Path(base) / bridge.EXECUTION_LOCK.relative_to(bridge.BASE)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = json.loads(Path(receipt_path).read_bytes(), object_pairs_hook=authority._object)
        if receipt.get('global_authority_head_sha256') != authority.read_authority(authority_path).head_sha256:
            raise ValueError('Stale v2 authority head before transport')
        return core.execute(CONFIG, STAGE, receipt_path, budget_path, base=base,
                            authority=authority_path, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'review', 'run'))
    parser.add_argument('--proposal', type=Path, default=PROPOSAL)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--root-review', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare(args.proposal))
    elif args.action == 'verify':
        print(json.dumps(verify(args.proposal)['predecessor_proof'], indent=2))
    elif args.action == 'review':
        if args.budget_manifest is None:
            parser.error('review needs --budget-manifest')
        print(json.dumps(expected_review(args.budget_manifest, proposal_path=args.proposal), indent=2))
    else:
        if args.budget_manifest is None or args.root_review is None:
            parser.error('run needs --budget-manifest and --root-review')
        print(json.dumps(execute(args.root_review, args.budget_manifest,
                                 proposal_path=args.proposal), indent=2))


if __name__ == '__main__':
    main()
