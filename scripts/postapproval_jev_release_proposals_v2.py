#!/usr/bin/env python3
"""Prepare and, only with root review, commit the Jev P1 fresh1 unused hold.

P1 fresh2 is reported as unsupported: the reviewed authority v2 verifier
requires every terminal result valid. This script never releases fresh2.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import fcntl
import json
from pathlib import Path
import tempfile

from development_benchmark import ROOT
import postapproval_authority_v2 as authority
import postapproval_authority_release_v2 as first_controller


AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
BASE = ROOT / 'results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1'
OUT = ROOT / 'results/route-audits/postapproval-jev-releases-v2-20261006'
HOLD_ID = 'jev-openrouter-native-p1-choice-v1-fresh1-full-v1'
RELEASE_ID = 'jev-p1-fresh1-unused-v2'
AMOUNT = '0.074235000'
SOURCE = 'e98524b0cc4d4924ef03ab351ca9772fa3aa2c940cb017be7ed1fc411748ba38'
SCHEMA = 'postapproval-jev-p1-fresh1-release-v2-proposal'
REVIEW_SCHEMA = 'postapproval-jev-p1-fresh1-release-v2-root-review'


def _load(path):
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=authority._object)
    if not isinstance(value, dict):
        raise ValueError('Expected JSON object')
    return value


def _paths(stage_name):
    stage = BASE / stage_name
    pid = f'jev-openrouter-native-p1-choice-v1-{stage_name}-full-v1'
    return {'stage': stage, 'receipt': BASE / f'{stage_name}.root-review.json',
            'manifest': BASE.parent / 'jev-openrouter-native-p1-choice-v1.json',
            'budget': BASE / f'{stage_name}.budget.json',
            'child': BASE / f'{stage_name}.budget-{pid}.jsonl', 'pid': pid}


def _master_snapshot(path):
    with Path(path).open('rb') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = handle.read()
    events, _ = authority._lines(raw)
    return authority.sha(raw), events


def _fresh2_unsupported(master_events):
    p = _paths('fresh2')
    completion = _load(p['stage'] / 'completion.json')
    reconciliation = _load(p['stage'] / 'budget-reconciliation.json')
    receipt = _load(p['receipt'])
    child_raw = p['child'].read_bytes()
    child, _ = authority._lines(child_raw)
    attempts_raw = (p['stage'] / 'attempts.jsonl').read_bytes()
    attempts, _ = authority._lines(attempts_raw)
    master_rows = [event for event in master_events if
                   event.get('event') == 'partition_reconciled' and
                   event.get('partition_id') == p['pid']]
    known = sum((Decimal(event['usd']) for event in child if event.get('event') == 'settle'), Decimal(0))
    unknown = sum((Decimal(event['usd']) for event in child if
                   event.get('event') == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    invalid = [event for event in attempts if event.get('stage') == 'parsed' and
               event.get('valid') is False]
    if (completion.get('valid_count') != 59 or completion.get('invalid_count') != 1 or
            completion.get('invalid_ids') != ['DEV-056'] or
            completion.get('attempts_sha256') != authority.sha(attempts_raw) or
            completion.get('receipt_sha256') != authority.file_sha(p['receipt']) or
            len(attempts) != 240 or len(invalid) != 1 or invalid[0].get('id') != 'DEV-056' or
            len(child) != 122 or child[-1].get('event') != 'partition_closed' or
            sum(e.get('event') == 'reserve' for e in child) != 60 or
            sum(e.get('event') == 'settle' for e in child) != 60 or
            receipt.get('global_hold_id') != p['pid'] or
            receipt.get('global_hold_usd') != '0.080640000' or
            reconciliation.get('child_ledger') != str(p['child']) or
            reconciliation.get('child_sha256') != authority.sha(child_raw) or
            Decimal(reconciliation.get('known_actual_usd')) != known or
            Decimal(reconciliation.get('unknown_upper_bound_usd')) != unknown or
            known + unknown + Decimal(reconciliation.get('unused_allocation_released_usd')) != Decimal('0.080640000') or
            len(master_rows) != 1 or master_rows[0] != reconciliation):
        raise ValueError('P1 fresh2 closed-stage evidence changed')
    return {'schema': 'postapproval-jev-p1-fresh2-v2-unsupported-release-proof',
            'status': 'unsupported_no_release_event', 'hold_id': p['pid'],
            'hold_usd': '0.080640000', 'known_actual_usd': str(known),
            'unknown_upper_bound_usd': str(unknown),
            'child_unused_usd': reconciliation['unused_allocation_released_usd'],
            'invalid_ids': completion['invalid_ids'],
            'invalid_reason': invalid[0].get('reason'),
            'reason': 'Reviewed authority v2 requires every terminal result valid and settled; DEV-056 is intrinsically invalid.',
            'completion_sha256': authority.file_sha(p['stage'] / 'completion.json'),
            'attempts_sha256': authority.sha(attempts_raw),
            'child_sha256': authority.sha(child_raw),
            'reconciliation_sha256': authority.file_sha(p['stage'] / 'budget-reconciliation.json'),
            'master_reconciliation_event_sha256': authority.sha(authority.canonical(master_rows[0]))}


def _simulate(raw, master_path):
    p = _paths('fresh1')
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / 'authority.jsonl'
        copy.write_bytes(raw)
        result = authority.release_authority(
            copy, RELEASE_ID, HOLD_ID, AMOUNT, authority.sha(raw),
            stage_path=p['stage'], receipt_path=p['receipt'], manifest_path=p['manifest'],
            budget_manifest_path=p['budget'], child_ledger_path=p['child'],
            master_ledger_path=master_path)
        authority.read_authority(copy)
    if (result['release_event']['hold_source_sha256'] != SOURCE or
            result['release_event']['usd'] != AMOUNT):
        raise ValueError('P1 fresh1 release differs from pinned evidence')
    return result


def build(authority_path=AUTHORITY, master_path=MASTER):
    authority_path = Path(authority_path).resolve()
    master_path = Path(master_path).resolve()
    with authority._locked(authority_path) as handle:
        raw = handle.read()
        state, _, releases = authority._scan(raw, baseline_head=authority.ORIGINAL_HEAD,
                                             baseline_events=authority.ORIGINAL_EVENTS)
        if HOLD_ID in (event['hold_id'] for event in releases.values()):
            raise ValueError('P1 fresh1 hold already released')
    master_head, master_events = _master_snapshot(master_path)
    proposed = _simulate(raw, master_path)
    fresh2 = _fresh2_unsupported(master_events)
    if (authority.read_authority(authority_path).head_sha256 != state.head_sha256 or
            _master_snapshot(master_path)[0] != master_head):
        raise ValueError('Ledger head changed while preparing proposal')
    proposal = {'schema': SCHEMA, 'status': 'proposed_not_committed',
                'authority_file': str(authority_path), 'authority_head_sha256': state.head_sha256,
                'master_ledger_path': str(master_path), 'master_head_sha256': master_head,
                'old_accounted_usd': str(state.accounted_usd),
                'old_available_usd': str(state.available_usd),
                'proposed_release_receipt': proposed, 'inference_performed': False,
                'production_ledgers_mutated': False}
    return proposal, fresh2


def prepare(output_dir=OUT, *, authority_path=AUTHORITY, master_path=MASTER):
    output = Path(output_dir)
    proposal, unsupported = build(authority_path, master_path)
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / 'fresh1-proposal.json', output / 'fresh2-unsupported.json')
    if any(path.exists() for path in targets):
        raise FileExistsError('Proposal exists; use a new output directory for a fresh head')
    for path, value in zip(targets, (proposal, unsupported)):
        with path.open('x') as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'proposal_path': str(targets[0]), 'unsupported_path': str(targets[1]),
            'authority_head_sha256': proposal['authority_head_sha256']}


def _proposal(path):
    value = _load(path)
    event = (value.get('proposed_release_receipt') or {}).get('release_event')
    if (value.get('schema') != SCHEMA or value.get('status') != 'proposed_not_committed' or
            value.get('production_ledgers_mutated') is not False or
            value.get('inference_performed') is not False or
            not isinstance(event, dict) or
            (event.get('id'), event.get('hold_id'), event.get('usd'),
             event.get('hold_source_sha256')) != (RELEASE_ID, HOLD_ID, AMOUNT, SOURCE) or
            event.get('prior_head_sha256') != value.get('authority_head_sha256') or
            event.get('master_ledger_path') != value.get('master_ledger_path')):
        raise ValueError('P1 fresh1 proposal differs')
    return value


def template(proposal_path, receipt_path):
    proposal_path = Path(proposal_path).resolve(strict=True)
    proposal = _proposal(proposal_path)
    receipt_path = Path(receipt_path).resolve()
    if receipt_path in (proposal_path, Path(proposal['authority_file']).resolve()):
        raise ValueError('Receipt path collides with source')
    event = proposal['proposed_release_receipt']['release_event']
    return {'schema': REVIEW_SCHEMA, 'approved': False, 'reviewer': '',
            'proposal_path': str(proposal_path),
            'proposal_sha256': authority.file_sha(proposal_path),
            'controller_sha256': authority.file_sha(Path(__file__)),
            'receipt_writer_sha256': authority.file_sha(Path(first_controller.__file__)),
            'authority_file': proposal['authority_file'],
            'authority_head_sha256': proposal['authority_head_sha256'],
            'master_ledger_path': proposal['master_ledger_path'],
            'master_head_sha256': proposal['master_head_sha256'],
            'release_event_sha256': authority.sha(authority.canonical(event)),
            'release_receipt_path': str(receipt_path),
            'global_authority_approval_sha256': authority.HEADER['approval_sha256']}


def _review(proposal_path, review_path, receipt_path):
    expected = template(proposal_path, receipt_path)
    if _load(review_path) != {**expected, 'approved': True, 'reviewer': 'root'}:
        raise ValueError('P1 fresh1 root review differs')
    return _proposal(proposal_path)


def _release_status(proposal):
    event = proposal['proposed_release_receipt']['release_event']
    with authority._locked(proposal['authority_file']) as handle:
        raw = handle.read()
        authority._scan(raw, baseline_head=authority.ORIGINAL_HEAD,
                        baseline_events=authority.ORIGINAL_EVENTS)
        events, pieces = authority._lines(raw)
        prefix = b''
        matches = []
        for row, piece in zip(events, pieces):
            prefix += piece
            if row.get('event') == 'release' and row.get('id') == RELEASE_ID:
                matches.append((row, prefix))
        if matches:
            if len(matches) != 1 or matches[0][0] != event:
                raise ValueError('Existing release differs')
            state, _, _ = authority._scan(matches[0][1],
                                          baseline_head=authority.ORIGINAL_HEAD,
                                          baseline_events=authority.ORIGINAL_EVENTS)
            receipt = proposal['proposed_release_receipt']
            if (state.head_sha256 != receipt['new_head_sha256'] or
                    str(state.accounted_usd) != receipt['accounted_usd'] or
                    str(state.available_usd) != receipt['available_usd']):
                raise ValueError('Existing release prefix differs')
            return 'release_appended'
        if authority.sha(raw) != proposal['authority_head_sha256']:
            raise ValueError('Authority head changed')
    if _master_snapshot(proposal['master_ledger_path'])[0] != proposal['master_head_sha256']:
        raise ValueError('Master head changed')
    return 'ready_to_append'


def verify(proposal_path, review_path, receipt_path):
    proposal = _review(proposal_path, review_path, receipt_path)
    status = _release_status(proposal)
    output = Path(receipt_path)
    expected = first_controller._bytes(proposal['proposed_release_receipt'])
    if output.exists() and output.read_bytes() != expected:
        raise ValueError('Existing receipt differs')
    if status == 'ready_to_append':
        if output.exists():
            raise ValueError('Receipt exists without release')
        fresh, unsupported = build(proposal['authority_file'], proposal['master_ledger_path'])
        if fresh != proposal:
            raise ValueError('Proposal no longer matches exact source simulation')
    return {'status': status, 'receipt_present': output.exists()}


def commit(proposal_path, review_path, receipt_path):
    proposal = _review(proposal_path, review_path, receipt_path)
    state = verify(proposal_path, review_path, receipt_path)
    expected = proposal['proposed_release_receipt']
    output = Path(receipt_path)
    if state['status'] == 'ready_to_append':
        if not output.parent.is_dir():
            raise ValueError('Receipt directory missing')
        event = expected['release_event']
        actual = authority.release_authority(
            proposal['authority_file'], event['id'], event['hold_id'], event['usd'],
            event['prior_head_sha256'], stage_path=event['stage_path'],
            receipt_path=event['receipt_path'], manifest_path=event['manifest_path'],
            budget_manifest_path=event['budget_manifest_path'],
            child_ledger_path=event['child_ledger_path'],
            master_ledger_path=event['master_ledger_path'])
        if actual != expected:
            raise ValueError('Appended release differs from reviewed receipt')
    if _release_status(proposal) != 'release_appended':
        raise ValueError('Release append not recoverable')
    first_controller._persist_receipt(output, expected)
    return {'status': 'release_receipted', 'receipt_path': str(output),
            'new_head_sha256': expected['new_head_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'template', 'verify', 'commit'))
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--proposal', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--root-review', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.output)
    else:
        if args.proposal is None or args.receipt is None:
            parser.error('template, verify and commit need --proposal and --receipt')
        if args.action == 'template':
            result = template(args.proposal, args.receipt)
        else:
            if args.root_review is None:
                parser.error('verify and commit need --root-review')
            fn = verify if args.action == 'verify' else commit
            result = fn(args.proposal, args.root_review, args.receipt)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
