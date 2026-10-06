"""Closed-child source gates for the unadmitted low-v2 suffix proposal."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_remaining6_successor_v1 as successor


def test_closed_child_proposal_preserves_unknown_and_exact_unsent_suffix():
    proposal = successor.proposal_data()
    assert proposal['status'] == 'offline_proposal_unadmitted'
    assert proposal['predecessor_child_closed'] is True
    assert proposal['predecessor_unknown_cost_id'] == 'DEV-005'
    assert proposal['predecessor_unknown_cost_upper_bound_usd'] == '0.06905856'
    assert proposal['no_retry_ids'] == [f'DEV-{n:03}' for n in range(1, 6)]
    assert proposal['development_suffix_ids'] == [f'DEV-{n:03}' for n in range(6, 61)]
    assert len(proposal['development_suffix_request_sha256']) == 55
    assert len(proposal['later_phase_order']) == 5
    assert proposal['new_child_partition_id'] is None
    assert proposal['allocation_authorized'] is False
    assert proposal['dispatch_authorized'] is False
    assert successor.relative(successor.CHILD) in proposal['source_bindings']
    assert successor.relative(successor.RECONCILIATION) in proposal['source_bindings']


def test_predecessor_receipt_or_closed_child_change_refuses_successor(tmp_path):
    receipt = json.loads(successor.RECONCILIATION.read_text())
    receipt['partition_reconciled']['unknown_upper_bound_usd'] = '0'
    changed = tmp_path / 'receipt.json'
    changed.write_text(json.dumps(receipt) + '\n')
    with mock.patch.object(successor, 'RECONCILIATION', changed):
        with pytest.raises(ValueError, match='full unknown bound'):
            successor.proposal_data()
    child = tmp_path / 'child.jsonl'
    child.write_bytes(successor.CHILD.read_bytes() + b'{}\n')
    with mock.patch.object(successor, 'CHILD', child):
        with pytest.raises(ValueError, match='source differs'):
            successor.proposal_data()


def test_prepared_manifest_is_source_bound_and_exclusive():
    assert successor.verify() == successor.sha(successor.MANIFEST)
    with pytest.raises(FileExistsError):
        successor.prepare()
