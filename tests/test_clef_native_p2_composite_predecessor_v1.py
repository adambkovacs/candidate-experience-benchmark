"""Read-only checks for the Clef one-unknown plus 59-valid predecessor."""

from copy import deepcopy
import json

import pytest

import clef_native_p2_composite_predecessor_v1 as bridge
import clef_native_remaining as frozen


def reviewed_file(tmp_path):
    path = tmp_path / 'review.json'
    path.write_text(json.dumps(bridge.value(), sort_keys=True, indent=2) + '\n')
    return path


def test_current_parent_and_suffix_cover_exact_60_without_clean_status():
    result = bridge.value()
    coverage = result['coverage']
    assert result['status'] == coverage['status'] == 'closed_composite_not_clean'
    assert coverage['unknown_ids'] == ['DEV-001']
    assert coverage['valid_ids'] == list(bridge.prep.IDS[1:])
    assert coverage['ordered_ids'] == list(bridge.prep.IDS)
    assert (coverage['valid'], coverage['unknown_outcome']) == (59, 1)
    assert result['source_bindings'][str(bridge.AUTHORITY_SNAPSHOT.relative_to(bridge.ROOT))] == \
        bridge.digest(bridge.AUTHORITY_SNAPSHOT)
    assert result['source_bindings'][str((bridge.SUFFIX_DIR / 'completion.json').relative_to(bridge.ROOT))] == \
        bridge.digest(bridge.SUFFIX_DIR / 'completion.json')


def test_missing_duplicate_or_reclassified_parent_and_suffix_are_rejected():
    parent = bridge.rows(bridge.suffix.PARENT / 'records.jsonl')
    suffix = bridge.rows(bridge.SUFFIX_DIR / 'records.jsonl')
    plan, _ = bridge.suffix.checked_plan()
    assert bridge.coverage(parent, suffix, plan['requests'])['valid'] == 59
    with pytest.raises(ValueError, match='coverage'):
        bridge.coverage(parent, suffix[:-1], plan['requests'])
    duplicated = deepcopy(suffix)
    duplicated[1]['id'] = duplicated[0]['id']
    with pytest.raises(ValueError, match='coverage'):
        bridge.coverage(parent, duplicated, plan['requests'])
    clean_claim = deepcopy(parent)
    clean_claim[0]['status'] = 'valid'
    with pytest.raises(ValueError, match='coverage'):
        bridge.coverage(clean_claim, suffix, plan['requests'])


def test_review_binds_current_evidence_and_rejects_drift(tmp_path, monkeypatch):
    path = reviewed_file(tmp_path)
    assert bridge.checked_review(path) == bridge.digest(path)
    changed = json.loads(path.read_text())
    changed['coverage']['unknown_outcome'] = 0
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match='root-reviewed'):
        bridge.checked_review(path)
    path = reviewed_file(tmp_path)
    original = bridge.digest
    monkeypatch.setattr(bridge, 'digest', lambda item: '0' * 64
                        if item == bridge.AUTHORITY_SNAPSHOT else original(item))
    with pytest.raises(ValueError, match='root-reviewed'):
        bridge.checked_review(path)


def test_run_wrapper_changes_only_exact_predecessor_and_restores_hook(tmp_path, monkeypatch):
    path = reviewed_file(tmp_path)
    monkeypatch.setattr(bridge, 'REVIEW', path)
    next_grant = tmp_path / 'next-grant.json'
    next_grant.write_text(json.dumps({'account_id_sha256': bridge.value()['account_id_sha256']}))
    original = frozen.predecessor_hash
    observed = []

    def no_dispatch(model, repeat, condition, phase, grant_path, **options):
        observed.append((model, repeat, condition, phase, grant_path))
        manifest_hash = frozen.checked_manifest(frozen.MANIFEST)[1]
        assert frozen.predecessor_hash(model, repeat, condition, manifest_hash) == \
            bridge.digest(path)
        return {'verified_predecessor_only': True}

    monkeypatch.setattr(bridge.inventory, 'run_stage', no_dispatch)
    assert bridge.run_stage('clef', 'fresh2', 'P2', 'smoke', next_grant,
                            review_path=path) == {'verified_predecessor_only': True}
    assert observed == [('clef', 'fresh2', 'P2', 'smoke', next_grant)]
    assert frozen.predecessor_hash is original
    with pytest.raises(ValueError, match='Only the reviewed'):
        bridge.run_stage('clef', 'fresh2', 'P1', 'smoke', next_grant,
                         review_path=path)
    with pytest.raises(ValueError, match='Only the reviewed'):
        bridge.run_stage('clef', 'fresh2', 'P2', 'smoke', next_grant,
                         review_path=path, authority_path=tmp_path / 'fake-ledger')
    with pytest.raises(ValueError, match='Only the reviewed'):
        bridge.run_stage('clef', 'fresh2', 'P2', 'smoke', next_grant,
                         review_path=tmp_path / 'other-review.json')
    next_grant.write_text(json.dumps({'account_id_sha256': '0' * 64}))
    with pytest.raises(ValueError, match='account differs'):
        bridge.run_stage('clef', 'fresh2', 'P2', 'smoke', next_grant,
                         review_path=path)
    assert len(observed) == 1
