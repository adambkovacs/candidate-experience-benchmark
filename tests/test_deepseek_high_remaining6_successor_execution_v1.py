"""Offline high successor admission and exact request boundaries."""
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_high_remaining6_successor_execution_v1 as candidate


def test_only_unsent_first_development_and_declared_later_phases():
    first = candidate.plan_data('fresh2')
    suffix = first['conditions']['P2']['development']
    assert len(suffix) == 33
    assert [row['record_id'] for row in suffix] == [f'DEV-{n:03}' for n in range(28, 61)]
    assert [row['position'] for row in suffix] == list(range(33))
    assert [row['record_id'] for row in first['conditions']['P2']['smoke']] == [
        'DEV-028', 'DEV-029', 'DEV-030']
    assert first['conditions']['P2']['clean_full_phase'] is False
    assert first['conditions']['P2']['suffix_completion_descriptive_only'] is True
    assert first['condition_order'] == ['P2', 'P0', 'P1']
    assert candidate.plan_data('fresh3')['condition_order'] == ['P1', 'P2', 'P0']
    for repeat, condition in candidate.PHASES[1:]:
        plan = candidate.plan_data(repeat)
        assert len(plan['conditions'][condition]['development']) == 60


def test_request_payload_hashes_and_high_interface_unchanged():
    first = candidate.plan_data('fresh2')
    source = candidate.report.portable_plan('fresh2',
        candidate.sha(candidate.prior.BASE / 'fresh2/manifest.json'))
    for actual, original in zip(first['conditions']['P2']['development'],
                                source['conditions']['P2']['development'][27:]):
        assert actual['payload'] == original['payload']
        assert actual['request_sha256'] == original['request_sha256']
        assert actual['input_sha256'] == original['input_sha256']
        assert actual['instruction_sha256'] == original['instruction_sha256']
    assert first['configuration_id'] == candidate.prior.proposal.CONFIG
    assert candidate.authority.SCHEMA == 'openrouter-authority-release-v4'


def test_stage_order_does_not_consume_wrong_parent_clean_closure():
    core = candidate.repaired_core()
    first = candidate.plan_data('fresh2')
    with mock.patch.object(candidate.prior, 'verify_plan',
                           side_effect=AssertionError('old v3 clean closure')):
        core.require_order(first, 'P2', 'smoke')
    with pytest.raises(ValueError, match='outside high successor order'):
        core.require_order(first, 'P9', 'smoke')


def test_successor_inspection_accepts_exact_dev028_to_dev030(tmp_path):
    core = candidate.repaired_core()
    plan = candidate.verify_plan('fresh2',
        candidate.sha(candidate.BASE / 'fresh2/manifest.json'))
    folder = tmp_path / 'smoke'
    folder.mkdir()
    journal = folder / 'smoke.journal.jsonl'
    attempts = folder / 'smoke.attempts.jsonl'
    raw = folder / 'smoke.responses.jsonl'
    journal.write_text('{}\n')
    rows = [{'id': f'DEV-{n:03}', 'attempt_id': f'attempt-{n}',
             'status': 'ok', 'billing_ok': True, 'cost_unknown': False}
            for n in (28, 29, 30)]
    attempts.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    raw.write_text(''.join(json.dumps({'attempt_id': row['attempt_id']}) + '\n'
                           for row in rows))
    bindings = {'manifest_sha256': candidate.sha(candidate.BASE / 'fresh2/manifest.json')}
    with mock.patch.object(core, 'phase_paths', return_value=(
            folder, folder / 'smoke.claim.json', journal, attempts)), \
         mock.patch.object(core, 'verify_phase_closure', return_value=bindings):
        inspected = core.inspect(candidate.prior.proposal.CONFIG, 'fresh2', 'P2',
                                 candidate.sha(candidate.BASE / 'fresh2/manifest.json'),
                                 'Raw JSON and billing inspected')
    assert [row['record_id'] for row in plan['conditions']['P2']['smoke']] == [
        'DEV-028', 'DEV-029', 'DEV-030']
    assert inspected['decision'] == 'accepted_unchanged'
    assert json.loads((folder / 'smoke-inspection.json').read_text()) == inspected


def test_budget_gate_requires_v4_transition_before_any_hold():
    core = candidate.repaired_core()
    ledger = mock.Mock()
    ledger.cap = candidate.CHILD_CAP
    ledger.master_cap = Decimal('22.38')
    ledger.closed = False
    ledger.state.return_value = ({}, {}, False)
    ledger.accounted.return_value = Decimal(0)
    locked = mock.MagicMock()
    locked.__enter__.return_value.read.return_value = b'v3-only'
    snapshot = SimpleNamespace(head_sha256='head')
    with mock.patch.object(candidate, 'exact_budget_entry'), \
         mock.patch.object(candidate.partitions, 'open_partition', return_value=ledger), \
         mock.patch.object(candidate.authority.old, '_locked', return_value=locked), \
         mock.patch.object(candidate.authority, '_scan', return_value=(snapshot, {}, set())):
        with pytest.raises(ValueError, match='V4 transition'):
            core.budget_gate({'global_authority_head_sha256': 'head'},
                             candidate.BUDGET, candidate.prior.proposal.CONFIG)
    ledger.close.assert_called_once()


@pytest.mark.parametrize('name', [
    'scripts/postapproval_authority_v2.py',
    'scripts/qwen27_fresh_repeat_execution.py',
    'scripts/deepseek_high_v3_closure_bridge.py',
])
def test_transitive_runtime_drift_invalidates_adapter(name):
    saved = json.loads(candidate.MANIFEST.read_text())
    assert name in saved['source_bindings']
    actual_sha = candidate.sha
    with mock.patch.object(candidate, 'sha', side_effect=lambda path:
            '0' * 64 if Path(path).name == Path(name).name
            else actual_sha(path)):
        with pytest.raises(ValueError, match='Bound high successor source changed'):
            candidate.verify()
