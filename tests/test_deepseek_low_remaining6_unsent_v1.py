"""Offline guards for the interrupted low price-v2 continuation proposal."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_remaining6_unsent_v1 as stopped


def test_continuation_is_only_exact_unsent_suffix():
    plan = stopped.adapter.plan_data('fresh2')
    frozen = plan['conditions']['P2']['development']
    assert stopped.SENT == [row['record_id'] for row in frozen[:5]]
    assert stopped.UNSENT == [row['record_id'] for row in frozen[5:]]
    assert len(stopped.UNSENT) == 55
    assert not set(stopped.SENT) & set(stopped.UNSENT)


def test_saved_stopped_prefix_binds_raw_and_frozen_requests():
    plan = stopped.adapter.verify_plan('fresh2',
        stopped.sha(stopped.BASE / 'fresh2/manifest.json'))
    journal = stopped.rows(stopped.FOLDER / 'development.journal.jsonl')
    attempts = stopped.rows(stopped.FOLDER / 'development.attempts.jsonl')
    responses = stopped.rows(stopped.FOLDER / 'development.responses.jsonl')
    hashes = stopped.validate_prefix(plan, journal, attempts, responses)
    assert hashes == [row['request_sha256'] for row in
                      plan['conditions']['P2']['development'][5:]]
    assert len(hashes) == 55


def test_unknown_reservation_is_never_settled_or_retried():
    attempts = [
        {'id': f'DEV-{n:03}', 'attempt_id': f'attempt-{n}',
         'reserved_cost_usd': '0.06905856',
         'observed_cost_usd': '0.0002' if n < 8 else None,
         'billing_ok': n < 8, 'cost_unknown': n == 8}
        for n in range(1, 9)]
    smoke, development = attempts[:3], attempts[3:]
    development[-1]['id'] = 'DEV-005'
    events = [{'event': 'budget', 'cap_usd': '0.75'}]
    for attempt in attempts:
        events.append({'event': 'reserve', 'attempt_id': attempt['attempt_id'],
                       'record_id': attempt['id'], 'usd': '0.06905856'})
        if attempt is not attempts[-1]:
            events.append({'event': 'settle', 'attempt_id': attempt['attempt_id'],
                           'usd': '0.0002'})
    raw = ''.join(json.dumps(event) + '\n' for event in events).encode()
    assert str(stopped.ledger_prefix(raw, smoke, development)) == '0.0014'
    with pytest.raises(ValueError, match='prefix differs'):
        stopped.ledger_prefix(raw + b'{}\n', smoke, development)
    changed = [dict(event) for event in events]
    changed[14]['usd'] = '0.0001'
    with pytest.raises(ValueError, match='settlement differs'):
        stopped.ledger_prefix(''.join(json.dumps(event) + '\n' for event in changed).encode(),
                              smoke, development)
