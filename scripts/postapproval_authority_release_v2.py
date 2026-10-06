#!/usr/bin/env python3
"""Reviewed, recoverable controller for the first postapproval release.

`template` prints a review form without approving anything. `verify` is
read-only. `commit` appends the reviewed release through authority v2 and
persists its receipt. None of these actions allocates a child or runs a model.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

import postapproval_authority_v2 as authority


SCHEMA = 'postapproval-authority-v2-first-release-root-review'
PROPOSAL_SCHEMA = 'postapproval-authority-v2-offline-proposal'
RELEASE_ID = 'jev-p2-fresh1-unused-v2'
HOLD_ID = 'jev-openrouter-native-p2-choice-v1-fresh1-full-v1'
RELEASE_USD = '0.073788960'
HOLD_SOURCE_SHA256 = '1be9ec2c2a5ccf011ce3dc00ef472a553fe00a3a886b7abaa8f8bbef918afa99'


def _load(path):
    value = json.loads(Path(path).read_bytes(), object_pairs_hook=authority._object)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


def _bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode()


def _proposal(path):
    proposal_path = Path(path).resolve(strict=True)
    proposal = _load(proposal_path)
    receipt = proposal.get('proposed_release_receipt')
    event = receipt.get('release_event') if isinstance(receipt, dict) else None
    if (proposal.get('schema') != PROPOSAL_SCHEMA or
            proposal.get('status') != 'proposed_not_committed' or
            proposal.get('production_authority_mutated') is not False or
            proposal.get('inference_performed') is not False or
            not isinstance(event, dict) or set(event) != authority.RELEASE_KEYS or
            (event.get('id'), event.get('hold_id'), event.get('usd'),
             event.get('hold_source_sha256')) !=
            (RELEASE_ID, HOLD_ID, RELEASE_USD, HOLD_SOURCE_SHA256) or
            event.get('prior_head_sha256') != proposal.get('authority_head_sha256_at_proposal') or
            receipt.get('old_head_sha256') != event['prior_head_sha256'] or
            proposal.get('would_be_accounted_usd') != receipt.get('accounted_usd') or
            proposal.get('would_be_available_usd') != receipt.get('available_usd') or
            not authority._digest(receipt.get('new_head_sha256')) or
            not authority._digest(proposal.get('master_head_sha256_at_proposal')) or
            not Path(proposal.get('authority_file', '')).is_absolute()):
        raise ValueError('First-release proposal differs from reviewed shape')
    return proposal_path, proposal


def review_template(proposal_path, receipt_path):
    path, proposal = _proposal(proposal_path)
    output = Path(receipt_path).resolve()
    if output == path or output == Path(proposal['authority_file']).resolve():
        raise ValueError('Release receipt cannot overwrite proposal or authority')
    event = proposal['proposed_release_receipt']['release_event']
    return {'schema': SCHEMA, 'approved': False, 'reviewer': '',
            'proposal_path': str(path), 'proposal_sha256': authority.file_sha(path),
            'controller_sha256': authority.file_sha(Path(__file__)),
            'authority_file': str(Path(proposal['authority_file']).resolve()),
            'authority_head_sha256': event['prior_head_sha256'],
            'master_ledger_path': event['master_ledger_path'],
            'master_head_sha256': proposal['master_head_sha256_at_proposal'],
            'release_event_sha256': authority.sha(authority.canonical(event)),
            'release_receipt_path': str(output),
            'global_authority_approval_sha256': authority.HEADER['approval_sha256']}


def _review(proposal_path, root_review_path, receipt_path):
    expected = review_template(proposal_path, receipt_path)
    reviewed = _load(root_review_path)
    if reviewed != {**expected, 'approved': True, 'reviewer': 'root'}:
        raise ValueError('Explicit root review differs from proposal, controller or output')
    return _proposal(proposal_path)[1]


def _find_release(authority_path, expected_event):
    """Return its exact prefix state even if later holds followed the release."""
    with authority._locked(authority_path) as handle:
        raw = handle.read()
        authority._scan(raw, baseline_head=authority.ORIGINAL_HEAD,
                        baseline_events=authority.ORIGINAL_EVENTS)
        events, pieces = authority._lines(raw)
        prefix = b''
        matches = []
        for event, piece in zip(events, pieces):
            prefix += piece
            if event.get('event') == 'release' and event.get('id') == RELEASE_ID:
                matches.append((event, prefix))
        if len(matches) > 1:
            raise ValueError('Duplicate release identity in authority')
        if not matches:
            return None
        event, prefix = matches[0]
        if event != expected_event:
            raise ValueError('Existing release differs from reviewed proposal')
        state, _, _ = authority._scan(prefix, baseline_head=authority.ORIGINAL_HEAD,
                                      baseline_events=authority.ORIGINAL_EVENTS)
        return state


def _checked_status(proposal):
    expected_receipt = proposal['proposed_release_receipt']
    event = expected_receipt['release_event']
    authority_path = Path(proposal['authority_file'])
    existing = _find_release(authority_path, event)
    if existing is not None:
        if (existing.head_sha256 != expected_receipt['new_head_sha256'] or
                str(existing.accounted_usd) != expected_receipt['accounted_usd'] or
                str(existing.available_usd) != expected_receipt['available_usd']):
            raise ValueError('Existing release prefix does not match reviewed receipt')
        return 'release_appended'
    state = authority.read_authority(authority_path)
    if state.head_sha256 != event['prior_head_sha256']:
        raise ValueError('Authority head changed before release')
    master = Path(event['master_ledger_path'])
    with master.open('rb') as handle:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if authority.sha(handle.read()) != proposal['master_head_sha256_at_proposal']:
            raise ValueError('Master head changed before release')
    if Path(proposal['authority_file']).resolve() == master.resolve():
        raise ValueError('Authority and master cannot be the same file')
    return 'ready_to_append'


def _simulate(proposal):
    """Prove the reviewed event and receipt on a temporary authority copy."""
    expected = proposal['proposed_release_receipt']
    event = expected['release_event']
    with authority._locked(proposal['authority_file']) as handle:
        raw = handle.read()
        authority._scan(raw, baseline_head=authority.ORIGINAL_HEAD,
                        baseline_events=authority.ORIGINAL_EVENTS)
        if authority.sha(raw) != event['prior_head_sha256']:
            raise ValueError('Authority changed before release simulation')
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / 'authority.jsonl'
        copy.write_bytes(raw)
        actual = authority.release_authority(
            copy, event['id'], event['hold_id'], event['usd'],
            event['prior_head_sha256'], stage_path=event['stage_path'],
            receipt_path=event['receipt_path'], manifest_path=event['manifest_path'],
            budget_manifest_path=event['budget_manifest_path'],
            child_ledger_path=event['child_ledger_path'],
            master_ledger_path=event['master_ledger_path'])
    if actual != expected:
        raise ValueError('Reviewed release differs from exact offline simulation')


def _persist_receipt(path, value):
    """Create only after release; temp fsync + hard link avoids partial receipt."""
    output = Path(path)
    raw = _bytes(value)
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError('Existing release receipt differs')
        return
    if not output.parent.is_dir():
        raise ValueError('Release receipt directory does not exist')
    descriptor, temporary = tempfile.mkstemp(prefix='.' + output.name + '.',
                                             suffix='.tmp', dir=output.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, output)
        except FileExistsError:
            if output.read_bytes() != raw:
                raise ValueError('Concurrent release receipt differs')
        directory = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def verify(proposal_path, root_review_path, receipt_path):
    proposal = _review(proposal_path, root_review_path, receipt_path)
    status = _checked_status(proposal)
    output = Path(receipt_path)
    if output.exists() and output.read_bytes() != _bytes(proposal['proposed_release_receipt']):
        raise ValueError('Existing release receipt differs')
    if status == 'ready_to_append' and output.exists():
        raise ValueError('Release receipt exists without ledger event')
    if status == 'ready_to_append':
        _simulate(proposal)
    return {'status': status, 'receipt_present': output.exists(),
            'release_id': RELEASE_ID, 'authority_head_sha256':
            authority.read_authority(proposal['authority_file']).head_sha256}


def commit(proposal_path, root_review_path, receipt_path):
    proposal = _review(proposal_path, root_review_path, receipt_path)
    status = _checked_status(proposal)
    expected = proposal['proposed_release_receipt']
    output = Path(receipt_path)
    if status == 'ready_to_append':
        if output.exists() or not output.parent.is_dir():
            raise ValueError('Receipt path is occupied or its directory is missing')
        _simulate(proposal)
        event = expected['release_event']
        actual = authority.release_authority(
            proposal['authority_file'], event['id'], event['hold_id'], event['usd'],
            event['prior_head_sha256'], stage_path=event['stage_path'],
            receipt_path=event['receipt_path'], manifest_path=event['manifest_path'],
            budget_manifest_path=event['budget_manifest_path'],
            child_ledger_path=event['child_ledger_path'],
            master_ledger_path=event['master_ledger_path'])
        if actual != expected:
            # The append is already durable; recovery must inspect it. Never
            # write a receipt that differs from the reviewed proposal.
            raise ValueError('Appended release differs from reviewed proposal')
    if _checked_status(proposal) != 'release_appended':
        raise ValueError('Release append cannot be recovered')
    _persist_receipt(output, expected)
    return {'status': 'release_receipted', 'receipt_path': str(output),
            'new_head_sha256': expected['new_head_sha256']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('template', 'verify', 'commit'))
    parser.add_argument('--proposal', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--root-review', type=Path)
    args = parser.parse_args()
    if args.action == 'template':
        result = review_template(args.proposal, args.receipt)
    else:
        if args.root_review is None:
            parser.error('verify and commit require --root-review')
        result = (verify if args.action == 'verify' else commit)(
            args.proposal, args.root_review, args.receipt)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
