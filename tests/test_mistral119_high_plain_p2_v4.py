"""Offline checks for the independent, never-started Mistral P2 stage."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_high_plain_p2_v4 as proposal
import mistral119_high_plain_p2_v4_execution as executor
from openrouter_budget_v4 import BudgetLedger


def test_only_p2_and_exact_frozen_requests():
    assert proposal.PHASES == (('fresh1', 'P2'),)
    plan = proposal.plan_data('fresh1')
    old = proposal.prior.verify_plan('fresh1', proposal.sha(
        proposal.prior.BASE / 'fresh1/manifest.json'))
    assert plan['condition_order'] == ['P2']
    assert list(plan['conditions']) == ['P2']
    for phase, count in [('smoke', 3), ('development', 60)]:
        current = plan['conditions']['P2'][phase]
        frozen = old['conditions']['P2'][phase]
        assert len(current) == count
        assert current == frozen
    with pytest.raises(ValueError, match='Only fresh1/P2'):
        proposal.plan_data('fresh2')


def test_stopped_p0_p1_are_bound_and_not_credited():
    first, second = proposal.stopped_predecessors()
    assert first['attempted_ids'] == second['attempted_ids'] == ['DEV-001']
    assert first['never_sent_smoke_ids'] == second['never_sent_smoke_ids'] == [
        'DEV-002', 'DEV-003']
    assert proposal.verify() == proposal.sha(proposal.MANIFEST)
    saved = json.loads(proposal.MANIFEST.read_text())
    for name in ['scripts/mistral119_high_plain_p2_v4_execution.py',
                 'scripts/openrouter_authority_release_v4.py',
                 'scripts/qwen27_fresh_repeat_execution.py',
                 str(proposal.PRIOR_TERMINAL.relative_to(ROOT)),
                 str(proposal.PRIOR_RECONCILIATION.relative_to(ROOT))]:
        assert name in saved['source_bindings']
    real = proposal.sha
    with mock.patch.object(proposal, 'sha', side_effect=lambda path:
            '0' * 64 if Path(path).name == 'terminal-public.json' else real(path)):
        with pytest.raises(ValueError, match='Bound independent P2 source changed'):
            proposal.verify()


def test_p2_smoke_has_no_stopped_p1_predecessor_gate(tmp_path):
    core = executor.private_core()
    plan = proposal.verify_plan('fresh1', proposal.sha(
        proposal.BASE / 'fresh1/manifest.json'))
    with mock.patch.object(core, 'verify_phase_closure',
                           side_effect=AssertionError('P1 improperly credited')):
        core.require_order(plan, 'P2', 'smoke')
    with pytest.raises(ValueError, match='outside independent'):
        core.require_order(plan, 'P1', 'smoke')
    with mock.patch.object(core, 'phase_paths', return_value=(
            tmp_path, tmp_path / 'smoke.claim.json',
            tmp_path / 'smoke.journal.jsonl', tmp_path / 'smoke.attempts.jsonl')):
        with pytest.raises(FileNotFoundError):
            core.require_order(plan, 'P2', 'development')


def test_full_requires_exact_three_response_inspection(tmp_path):
    core = executor.private_core()
    plan = proposal.verify_plan('fresh1', proposal.sha(
        proposal.BASE / 'fresh1/manifest.json'))
    digest = proposal.sha(proposal.BASE / 'fresh1/manifest.json')
    journal = tmp_path / 'smoke.journal.jsonl'
    attempts = tmp_path / 'smoke.attempts.jsonl'
    raw = tmp_path / 'smoke.responses.jsonl'
    for path in (journal, attempts, raw):
        path.write_text('{}\n')
    bindings = {'manifest_sha256': digest, 'journal_sha256': proposal.sha(journal),
                'attempts_sha256': proposal.sha(attempts),
                'responses_sha256': proposal.sha(raw)}
    paths = (tmp_path, tmp_path / 'smoke.claim.json', journal, attempts)
    with mock.patch.object(core, 'phase_paths', return_value=paths), \
         mock.patch.object(core, 'verify_phase_closure', return_value=bindings):
        with pytest.raises(FileNotFoundError):
            core.require_order(plan, 'P2', 'development')
        (tmp_path / 'smoke-inspection.json').write_text(json.dumps({
            'decision': 'accepted_unchanged', 'configuration_id': proposal.CONFIG,
            'manifest_sha256': digest, 'journal_sha256': proposal.sha(journal),
            'attempts_sha256': proposal.sha(attempts),
            'responses_sha256': proposal.sha(raw)}) + '\n')
        core.require_order(plan, 'P2', 'development')
        raw.write_text('{"changed":true}\n')
        with pytest.raises(ValueError, match='inspection differs'):
            core.require_order(plan, 'P2', 'development')


@pytest.mark.parametrize('fail_first', [False, True])
def test_real_temp_child_mock_http_smoke_no_replay(tmp_path, fail_first):
    plan_path = tmp_path / 'fresh1/manifest.json'
    plan_path.parent.mkdir()
    plan_path.write_bytes((proposal.BASE / 'fresh1/manifest.json').read_bytes())
    digest = proposal.sha(plan_path)
    child_path = tmp_path / 'budget-child.jsonl'
    ledger = BudgetLedger(child_path, cap_limit=proposal.CHILD_CAP)
    ledger.close()
    budget_path = tmp_path / 'budget.json'
    budget_path.write_text('{}\n')
    folder = tmp_path / 'fresh1/P2'
    folder.mkdir(parents=True)
    review_path = folder / 'smoke.root-review.json'
    route = proposal.portable_route(proposal.portable_sources())
    model, endpoint = route['model'], route['selected_endpoint']
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
        if fail_first:
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
        receipt = executor.stage_receipt('fresh1', 'P2', 'smoke')
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
            assert core.execute(proposal.CONFIG, 'fresh1', 'P2', 'smoke',
                                digest, review_path) is (not fail_first)
            with pytest.raises(FileExistsError, match='already claimed'):
                core.execute(proposal.CONFIG, 'fresh1', 'P2', 'smoke',
                             digest, review_path)
    rows = [json.loads(line) for line in child_path.read_text().splitlines()]
    attempts = [json.loads(line) for line in (
        folder / 'smoke.attempts.jsonl').read_text().splitlines()]
    assert len(sent) == (1 if fail_first else 3)
    assert sent == [row['payload'] for row in proposal.plan_data('fresh1')
                    ['conditions']['P2']['smoke'][:len(sent)]]
    assert [row['id'] for row in attempts] == [
        f'DEV-{number:03}' for number in range(1, len(sent) + 1)]
    assert sum(row['event'] == 'reserve' for row in rows) == len(sent)
    assert sum(row['event'] == 'settle' for row in rows) == (
        0 if fail_first else 3)
    if fail_first:
        assert attempts[0]['cost_unknown'] is True
        check = BudgetLedger(child_path, cap_limit=proposal.CHILD_CAP)
        try:
            _, pending, _ = check.state()
            assert len(pending) == 1
        finally:
            check.close()


def test_clean_archive_verifies_without_private_historical_smokes(tmp_path):
    if not (ROOT / '.git').exists():
        assert proposal.verify() == proposal.sha(proposal.MANIFEST)
        return
    archive = tmp_path / 'repo.tar'
    with archive.open('wb') as out:
        subprocess.run(['git', 'archive', '--format=tar', 'HEAD'], cwd=ROOT,
                       stdout=out, check=True)
    clean = tmp_path / 'clean'
    clean.mkdir()
    subprocess.run(['tar', '-xf', str(archive), '-C', str(clean)], check=True)
    candidate = [
        'scripts/mistral119_high_plain_p2_v4.py',
        'scripts/mistral119_high_plain_p2_v4_execution.py',
        'tests/test_mistral119_high_plain_p2_v4.py',
        str(proposal.BASE.relative_to(ROOT) / 'proposal.json'),
        str(proposal.BASE.relative_to(ROOT) / 'fresh1/manifest.json')]
    for name in candidate:
        target = clean / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    assert not (clean / 'results/mistral119-recovery-prep-v1/high-smoke.jsonl').exists()
    result = subprocess.run([sys.executable,
        'scripts/mistral119_high_plain_p2_v4_execution.py', 'verify'],
        cwd=clean, env=dict(os.environ, PYTHONPATH=str(clean / 'scripts')),
        text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
