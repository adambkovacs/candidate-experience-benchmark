"""Offline gates for eight unopened plain Mistral high repeat stages."""
from copy import deepcopy
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_high_plain_remaining8_v4 as proposal
import mistral119_high_plain_remaining8_v4_execution as executor
from openrouter_budget_v4 import BudgetLedger


def test_exact_eight_stages_exclude_interrupted_p0():
    assert proposal.PHASES == (
        ('fresh1', 'P1'), ('fresh1', 'P2'),
        ('fresh2', 'P1'), ('fresh2', 'P2'), ('fresh2', 'P0'),
        ('fresh3', 'P2'), ('fresh3', 'P0'), ('fresh3', 'P1'))
    assert sum(len(proposal.plan_data(r)['conditions']) for r in proposal.PASSES) == 8
    assert proposal.plan_data('fresh1')['condition_order'] == ['P1', 'P2']
    assert proposal.CHILD_CAP == Decimal('0.75')
    assert proposal.CHILD_CAP < proposal.RESERVE * 8 * 63
    with pytest.raises(ValueError):
        proposal.plan_data('fresh4')


@pytest.mark.parametrize('repeat,condition', proposal.PHASES)
def test_only_provider_tag_changes_in_frozen_requests(repeat, condition):
    actual = proposal.plan_data(repeat)['conditions'][condition]
    frozen = proposal.old.study.verify(proposal.old.OLD_CONFIG, repeat,
        proposal.sha(proposal.original_path(repeat)))['conditions'][condition]
    for phase, count in (('smoke', 3), ('development', 60)):
        assert len(actual[phase]) == count
        for changed, original in zip(actual[phase], frozen[phase]):
            assert changed['record_id'] == original['record_id']
            expected = deepcopy(original['payload'])
            expected['provider']['only'] = ['mistral']
            assert changed['payload'] == expected
            assert changed['input_sha256'] == original['input_sha256']
            assert changed['instruction_sha256'] == original['instruction_sha256']
            assert changed['request_sha256'] == proposal.old.study.digest(
                json.dumps(expected, sort_keys=True))


def test_proposal_binds_transitive_money_and_runtime_sources():
    saved = json.loads(proposal.MANIFEST.read_text())
    assert proposal.verify() == proposal.sha(proposal.MANIFEST)
    for name in ('scripts/qwen27_fresh_repeat_execution.py',
                 'scripts/openrouter_authority_release_v4.py',
                 'scripts/postapproval_authority_v2.py',
                 'scripts/paid_budget_partitions_v4.py',
                 'scripts/mistral119_high_plain_remaining8_v4_execution.py'):
        assert name in saved['source_bindings']
    actual_sha = proposal.sha
    with mock.patch.object(proposal, 'sha', side_effect=lambda path:
            '0' * 64 if Path(path).name == 'openrouter_budget_v4.py'
            else actual_sha(path)):
        with pytest.raises(ValueError, match='Bound plain Mistral source changed'):
            proposal.verify()


def test_first_stage_order_excludes_old_failed_smoke():
    core = executor.private_core()
    first = proposal.verify_plan('fresh1',
        proposal.sha(proposal.BASE / 'fresh1/manifest.json'))
    with mock.patch.object(core, 'verify_phase_closure',
                           side_effect=AssertionError('old failed smoke consumed')):
        core.require_order(first, 'P1', 'smoke')
    with pytest.raises(ValueError, match='outside eight unopened'):
        core.require_order(first, 'P0', 'smoke')


def test_next_stage_requires_strict_previous_closure():
    core = executor.private_core()
    second = proposal.verify_plan('fresh1',
        proposal.sha(proposal.BASE / 'fresh1/manifest.json'))
    with mock.patch.object(core, 'verify_phase_closure',
                           side_effect=ValueError('unfinished P1')) as closure:
        with pytest.raises(ValueError, match='unfinished P1'):
            core.require_order(second, 'P2', 'smoke')
    closure.assert_called_once()


def test_three_record_smoke_inspection_reaches_bound_closure(tmp_path):
    core = executor.private_core()
    folder = tmp_path / 'smoke'
    folder.mkdir()
    journal = folder / 'smoke.journal.jsonl'
    attempts = folder / 'smoke.attempts.jsonl'
    raw = folder / 'smoke.responses.jsonl'
    journal.write_text('{}\n')
    rows = [{'id': f'DEV-{n:03}', 'attempt_id': f'attempt-{n}',
             'status': 'ok', 'billing_ok': True, 'cost_unknown': False}
            for n in (1, 2, 3)]
    attempts.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    raw.write_text(''.join(json.dumps({'attempt_id': row['attempt_id']}) + '\n'
                           for row in rows))
    digest = proposal.sha(proposal.BASE / 'fresh1/manifest.json')
    with mock.patch.object(core, 'phase_paths', return_value=(
            folder, folder / 'smoke.claim.json', journal, attempts)), \
         mock.patch.object(core, 'verify_phase_closure', return_value={
             'manifest_sha256': digest,
             'journal_sha256': proposal.sha(journal),
             'attempts_sha256': proposal.sha(attempts),
             'responses_sha256': proposal.sha(raw)}):
        inspected = core.inspect(proposal.CONFIG, 'fresh1', 'P1', digest,
                                 'Root inspected three raw JSON responses')
    assert inspected['decision'] == 'accepted_unchanged'
    assert json.loads((folder / 'smoke-inspection.json').read_text()) == inspected


def test_v4_gate_fails_closed_before_transition():
    core = executor.private_core()
    ledger = mock.Mock()
    ledger.cap = proposal.CHILD_CAP
    ledger.master_cap = Decimal('22.38')
    ledger.closed = False
    ledger.state.return_value = ({}, {}, False)
    ledger.accounted.return_value = Decimal(0)
    locked = mock.MagicMock()
    locked.__enter__.return_value.read.return_value = b'v3-only'
    snapshot = SimpleNamespace(head_sha256='head')
    with mock.patch.object(executor, 'exact_budget_entry'), \
         mock.patch.object(executor.partitions, 'open_partition', return_value=ledger), \
         mock.patch.object(executor.authority.old, '_locked', return_value=locked), \
         mock.patch.object(executor.authority, '_scan', return_value=(snapshot, {}, set())):
        with pytest.raises(ValueError, match='V4 transition'):
            core.budget_gate({'global_authority_head_sha256': 'head'},
                             executor.BUDGET, proposal.CONFIG)
    ledger.close.assert_called_once()


def test_first_stage_execution_reaches_key_gate_without_old_smoke_or_dispatch():
    core = executor.private_core()
    digest = proposal.sha(proposal.BASE / 'fresh1/manifest.json')
    sentinel = RuntimeError('key gate reached')
    ledger = mock.Mock()
    with mock.patch.object(core, 'review_receipt', return_value=({}, executor.BUDGET)), \
         mock.patch.object(core, 'live_controls', return_value=({}, {}, proposal.RESERVE)), \
         mock.patch.object(core, 'budget_gate', return_value=ledger), \
         mock.patch.object(core.paid, 'load_key', side_effect=sentinel):
        with pytest.raises(RuntimeError, match='key gate reached'):
            core.execute(proposal.CONFIG, 'fresh1', 'P1', 'smoke', digest,
                         proposal.BASE / 'fresh1/P1/smoke.root-review.json')
    ledger.close.assert_called_once()
    assert not (proposal.BASE / 'fresh1/P1/smoke.claim.json').exists()


@pytest.mark.parametrize('unknown', [False, True])
def test_real_temp_child_mock_http_smoke_settles_or_stops_without_replay(tmp_path, unknown):
    """Use the actual patched core and durable child, with only HTTP mocked."""
    plan_path = tmp_path / 'fresh1/manifest.json'
    plan_path.parent.mkdir()
    plan_path.write_bytes((proposal.BASE / 'fresh1/manifest.json').read_bytes())
    digest = proposal.sha(plan_path)
    child_path = tmp_path / 'budget-child.jsonl'
    ledger = BudgetLedger(child_path, cap_limit=proposal.CHILD_CAP)
    ledger.close()
    budget_path = tmp_path / 'budget.json'
    budget_path.write_text('{}\n')
    folder = tmp_path / 'fresh1/P1'
    folder.mkdir(parents=True)
    review_path = folder / 'smoke.root-review.json'
    saved_route = proposal.old.route_snapshot()
    model, endpoint = saved_route['model'], saved_route['selected_endpoint']
    answer = {'sentiment': 'positive', 'follow_up_needed': 'no',
              'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
    body = {'model': proposal.old.study.MODEL, 'provider': 'Mistral',
            'choices': [{'finish_reason': 'stop',
                         'message': {'content': json.dumps(answer)}}],
            'usage': {'cost': '0.001'}}
    wire = json.dumps(body).encode()
    sent = []

    class Response(io.BytesIO):
        status = 200
        def __init__(self):
            super().__init__(wire)
            self.headers = {'content-type': 'application/json',
                            'content-length': str(len(wire))}

    def mock_open(request, timeout):
        sent.append(json.loads(request.data))
        if unknown:
            raise urllib.error.HTTPError(request.full_url, 429,
                'upstream shared pool', {'content-type': 'application/json'},
                io.BytesIO(b'{"error":"upstream shared pool"}'))
        return Response()

    with mock.patch.object(executor, 'BASE', tmp_path), \
         mock.patch.object(executor, 'BUDGET', budget_path), \
         mock.patch.object(executor, 'require_review'), \
         mock.patch.object(executor, 'exact_budget_entry'), \
         mock.patch.object(executor.authority, 'read_authority',
                           return_value=SimpleNamespace(head_sha256='test-head')):
        receipt = executor.stage_receipt('fresh1', 'P1', 'smoke')
        receipt.update(approved=True, independent_review=True,
                       authorized_by_root=True, reviewer='root')
        review_path.write_text(json.dumps(receipt) + '\n')
        core = executor.private_core()
        def open_child(*_):
            return BudgetLedger(child_path, cap_limit=proposal.CHILD_CAP)
        with mock.patch.object(core, 'live_controls',
                               return_value=(model, endpoint, proposal.RESERVE)), \
             mock.patch.object(core, 'budget_gate', side_effect=open_child), \
             mock.patch.object(core.paid, 'load_key', return_value='test-token'), \
             mock.patch.object(core.transport.OPENER, 'open', side_effect=mock_open), \
             mock.patch.object(core, 'audit_response', return_value={'passed': True}):
            assert core.execute(proposal.CONFIG, 'fresh1', 'P1', 'smoke',
                                digest, review_path) is (not unknown)
            with pytest.raises(FileExistsError, match='already claimed'):
                core.execute(proposal.CONFIG, 'fresh1', 'P1', 'smoke',
                             digest, review_path)
    rows = [json.loads(line) for line in child_path.read_text().splitlines()]
    attempts = [json.loads(line) for line in (folder / 'smoke.attempts.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in (folder / 'smoke.journal.jsonl').read_text().splitlines()]
    assert len(sent) == (1 if unknown else 3)
    assert sent == [row['payload'] for row in proposal.plan_data('fresh1')
                    ['conditions']['P1']['smoke'][:len(sent)]]
    assert [row['id'] for row in attempts] == [f'DEV-{i:03}' for i in range(1, len(sent) + 1)]
    assert sum(row['event'] == 'reserve' for row in rows) == len(sent)
    assert sum(row['event'] == 'settle' for row in rows) == (0 if unknown else 3)
    assert events[-1]['event'] == ('phase_stopped' if unknown else 'phase_completed')
    if unknown:
        assert attempts[0]['cost_unknown'] is True
        check = BudgetLedger(child_path, cap_limit=proposal.CHILD_CAP)
        try:
            _, pending, _ = check.state()
            assert len(pending) == 1
        finally:
            check.close()
    else:
        assert all(row['billing_ok'] is True and row['status'] == 'ok' for row in attempts)


def test_sequential_capacity_patch_is_present_without_dispatch():
    core = executor.private_core()
    assert core.execute.__code__.co_filename == str(Path(executor.__file__))
    assert 'insufficient_capacity' in core.execute.__code__.co_consts
    assert proposal.verify() == proposal.sha(proposal.MANIFEST)
