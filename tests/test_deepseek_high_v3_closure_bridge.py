"""Offline checks for the separately bound v3 DeepSeek closure adapter."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_high_v3_closure_bridge as repair


def test_repaired_closure_accepts_exact_saved_p0_with_invalid_output():
    result, counts = repair.verify_p0()
    assert counts == {'ok': 59, 'invalid_output': 1}
    assert result['manifest_sha256'] == repair.study.sha(repair.bridge.BASE / 'fresh1/manifest.json')
    assert result['attempts_sha256'] == repair.study.sha(repair.P0 / 'development.attempts.jsonl')
    assert repair.bridge.verify()['schema'] == repair.bridge.SCHEMA + '-execution'


def test_repaired_order_admits_p1_smoke_and_requires_its_inspection():
    core = repair.repaired_core()
    plan = repair.bridge.verify_plan('fresh1', repair.study.sha(repair.bridge.BASE / 'fresh1/manifest.json'))
    core.require_order(plan, 'P1', 'smoke')
    with mock.patch.object(core, 'verify_phase_closure', side_effect=ValueError('smoke closure missing')):
        with pytest.raises(ValueError, match='smoke closure missing'):
            core.require_order(plan, 'P1', 'development')


def test_bridge_manifest_bound_and_review_gate(tmp_path):
    manifest = repair.verify(repair.study.sha(repair.MANIFEST))
    assert manifest['status'] == 'offline_verified_unapproved'
    assert manifest['inference_authorized'] is False
    assert manifest['retained_intrinsic_invalid_id'] == 'DEV-030'
    assert all(repair.bound(source) for source in manifest['source_bindings'].values())
    pending = tmp_path / 'root-review.json'
    pending.write_text(json.dumps(repair.review_template()) + '\n')
    with mock.patch.object(repair, 'REVIEW', pending):
        with pytest.raises(ValueError, match='review missing'):
            repair.require_review()
