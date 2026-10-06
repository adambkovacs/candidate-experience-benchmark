"""Frozen predecessor and no-replay checks for the low P1 tail proposal."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_low_p1_dev028_successor_v1 as candidate


def test_exact_unsent_and_later_phase_membership():
    plan = candidate.proposal_data()
    assert plan['no_retry_ids'] == [f'DEV-{n:03}' for n in range(1, 28)]
    assert plan['development_suffix_ids'] == [f'DEV-{n:03}' for n in range(28, 61)]
    assert [(x['fresh_pass'], x['condition']) for x in plan['later_phase_order']] == [
        ('fresh3', 'P1'), ('fresh3', 'P2'), ('fresh3', 'P0')]
    assert all(len(x) == 60 for x in plan['later_phase_request_sha256'].values())
    assert plan['clean_full_p1_score'] is None
    assert not plan['allocation_authorized'] and not plan['dispatch_authorized']


def test_sealed_child_and_unknown_bound_are_required():
    candidate.predecessor_closed()
    real = candidate.sha
    with mock.patch.object(candidate, 'sha', side_effect=lambda p:
            '0' * 64 if Path(p) == candidate.CLOSED else real(p)):
        with pytest.raises(ValueError, match='sealed child'):
            candidate.predecessor_closed()


def test_terminal_evidence_is_source_bound():
    saved = json.loads(candidate.MANIFEST.read_text())
    assert saved == candidate.proposal_data()
    assert candidate.verify() == candidate.sha(candidate.MANIFEST)
    for path in (candidate.AUDIT, candidate.SNAPSHOT, candidate.RECONCILIATION,
                 candidate.CLOSED):
        assert candidate.relative(path) in saved['source_bindings']
    for path in (candidate.ATTEMPTS, candidate.RESPONSES, candidate.JOURNAL,
                 candidate.CHILD):
        assert candidate.relative(path) not in saved['source_bindings']


def test_portable_proposal_uses_immutable_evidence_without_private_raw():
    absent = {candidate.ATTEMPTS, candidate.RESPONSES, candidate.JOURNAL,
              candidate.CHILD}
    actual_exists = Path.exists
    with mock.patch.object(Path, 'exists', autospec=True,
                           side_effect=lambda path: False if path in absent else actual_exists(path)):
        plan = candidate.proposal_data()
    assert plan['development_suffix_ids'] == candidate.UNSENT
