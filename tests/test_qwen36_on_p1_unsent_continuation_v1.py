"""Offline guards for the Qwen3.6 ON P1 never-sent suffix."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qwen36_on_p1_unsent_continuation_v1 as suffix


def test_parent_audit_selects_only_never_sent_requests():
    original, selected = suffix.audit_parent()
    assert original['configuration_id'] == suffix.parent.CONFIG
    assert [x['record_id'] for x in selected] == [f'DEV-{n:03}' for n in range(50, 61)]
    assert all(x['request_sha256'] == original['conditions']['P1']['development'][n-1]['request_sha256']
               for n, x in enumerate(selected, 50))


def test_parent_audit_rejects_any_attempt_of_first_suffix_id(tmp_path):
    for name in suffix.OLD_FILES:
        (tmp_path / name).write_bytes((suffix.OLD / name).read_bytes())
    path = tmp_path / 'development.attempts.jsonl'
    with path.open('a') as out:
        out.write(json.dumps({'id': 'DEV-050'}) + '\n')
    with mock.patch.object(suffix, 'OLD', tmp_path), pytest.raises(ValueError, match='attempted membership'):
        suffix.audit_parent()


def test_parent_audit_rejects_changed_request_identity(tmp_path):
    for name in suffix.OLD_FILES:
        (tmp_path / name).write_bytes((suffix.OLD / name).read_bytes())
    path = tmp_path / 'development.attempts.jsonl'
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    rows[48]['request_sha256'] = '0' * 64
    path.write_text(''.join(json.dumps(x) + '\n' for x in rows))
    with mock.patch.object(suffix, 'OLD', tmp_path), pytest.raises(ValueError, match='request, attempt or journal'):
        suffix.audit_parent()


def test_proposal_is_offline_and_parent_requires_finalization():
    manifest = suffix.expected_manifest()
    assert manifest['status'] == 'offline_proposal_unapproved'
    assert manifest['inference_authorized'] is False
    assert manifest['never_sent_ids'] == [f'DEV-{n:03}' for n in range(50, 61)]
    assert len(manifest['requests']) == 11
    assert suffix.CAP == 11 * suffix.parent.RESERVE
    assert all(name in manifest['source_bindings'] for name in (
        'smoke.claim.json', 'smoke.journal.jsonl', 'smoke.attempts.jsonl',
        'smoke.responses.jsonl', 'smoke-inspection.json'))


def test_pending_parent_accounting_blocks_admission_even_after_future_reconciliation():
    class PendingChild:
        closed = False
        def state(self):
            return {}, {'pending-attempt'}, False
        def close(self):
            pass
    with mock.patch.object(suffix.budget, 'BudgetLedger', return_value=PendingChild()):
        with pytest.raises(ValueError, match='Parent child is not conservatively closed'):
            suffix.finalized_parent()


def test_private_runner_uses_separate_folder_and_only_eleven_requests():
    manifest_sha = suffix.study.sha(suffix.MANIFEST)
    core = suffix.private_runner(manifest_sha)
    plan = core.study.verify(suffix.parent.CONFIG, 'fresh1', manifest_sha)
    assert [r['record_id'] for r in plan['conditions']['P1']['development']] == [
        f'DEV-{n:03}' for n in range(50, 61)]
    assert core.phase_paths(suffix.parent.CONFIG, 'fresh1', 'P1', 'development')[0] == (
        suffix.BASE / 'fresh1/P1')
    # Successful offline order admission must inspect the original smoke path,
    # not ask the suffix runner to find a smoke in its new output folder.
    with mock.patch.object(suffix, 'finalized_parent') as finalized, \
         mock.patch.object(core, 'verify_phase_closure', side_effect=AssertionError('wrong suffix smoke path')):
        core.require_order(plan, 'P1', 'development')
    finalized.assert_called_once_with()
