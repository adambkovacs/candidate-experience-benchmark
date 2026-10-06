"""Post-smoke historical inventory remains exact while new stages close."""

import json
from pathlib import Path

import pytest

import clef_native_remaining_cloudflare_v2 as bridge


def test_completed_smoke_does_not_invalidate_historical_receipt():
    # In a clean checkout this stage is absent; in the live checkout it may be
    # closed. Both states must preserve the exact historical receipt.
    with bridge.historical_inventory():
        assert bridge.prior.checked_plan()[1] == bridge.prior.digest(bridge.prior.PLAN)
        assert bridge.historical.audit()['total_upper_bound_usd'] == '0.259584'


def test_later_declared_completion_is_allowed_but_unplanned_one_is_not(tmp_path):
    stages = json.loads(bridge.prior.HISTORICAL.read_bytes())['stages']
    for stage in stages:
        path = tmp_path / stage['stage'] / 'completion.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    later = tmp_path / 'clef/fresh3/P2/development/completion.json'
    later.parent.mkdir(parents=True)
    later.write_text('{}')
    assert len(bridge.inventory_paths(tmp_path)) == len(stages)
    rogue = tmp_path / 'clef/fresh1/P0/development-suffix-v9/completion.json'
    rogue.parent.mkdir(parents=True)
    rogue.write_text('{}')
    with pytest.raises(ValueError, match='inventory changed'):
        bridge.inventory_paths(tmp_path)


def test_missing_historical_completion_and_bound_hash_fail_closed(tmp_path, monkeypatch):
    stages = json.loads(bridge.prior.HISTORICAL.read_bytes())['stages']
    for stage in stages[1:]:
        path = tmp_path / stage['stage'] / 'completion.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    with pytest.raises(ValueError, match='inventory changed'):
        bridge.inventory_paths(tmp_path)
    # The old receipt still checks every historical file hash, not just names.
    old_digest = bridge.prior.digest
    monkeypatch.setattr(bridge.prior, 'digest', lambda path: '0' * 64 if Path(path) == bridge.prior.HISTORICAL else old_digest(path))
    with bridge.historical_inventory(), pytest.raises(ValueError, match='Reviewed Cloudflare Clef plan differs'):
        bridge.prior.checked_plan()
