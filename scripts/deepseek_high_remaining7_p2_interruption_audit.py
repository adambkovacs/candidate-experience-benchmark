"""Archive a sanitized, source-bound audit of the stopped high fresh2/P2 stage.

This script reads the child ledger and stage files. It never settles, reconciles,
allocates, or calls a model. It creates two immutable evidence files exclusively.
"""

from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/repeatability-v1/deepseek-high-remaining7-price-v1'
ADAPTER = BASE / 'execution-adapter-v1'
STAGE = ADAPTER / 'fresh2/P2'
CHILD = BASE / 'budget-deepseek-high-remaining7-price-v1.jsonl'
SNAPSHOT = STAGE / 'interruption-child-ledger-snapshot.jsonl'
UNKNOWN_EVIDENCE = STAGE / 'interruption-unknown-cost-evidence.jsonl'
RECEIPT = STAGE / 'interruption.audit.json'
BOUND = Decimal('0.06905856')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows(data: bytes) -> list[dict]:
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def exclusive(path: Path, data: bytes) -> None:
    try:
        with path.open('xb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError(f'Existing immutable evidence differs: {path}')


def audit() -> dict:
    plan_path = ADAPTER / 'fresh2/manifest.json'
    journal_path = STAGE / 'development.journal.jsonl'
    attempts_path = STAGE / 'development.attempts.jsonl'
    raw_path = STAGE / 'development.responses.jsonl'
    claim_path = STAGE / 'development.claim.json'
    review_path = STAGE / 'development.root-review.json'
    source_paths = [plan_path, journal_path, attempts_path, raw_path,
                    claim_path, review_path]
    source = {p.name: p.read_bytes() for p in source_paths}
    plan = json.loads(source[plan_path.name])
    claim = json.loads(source[claim_path.name])
    review = json.loads(source[review_path.name])
    planned = plan['conditions']['P2']['development']
    if len(planned) != 60 or [item['record_id'] for item in planned] != [
            f'DEV-{position:03d}' for position in range(1, 61)]:
        raise ValueError('Frozen 60-request plan/order differs')
    if claim['manifest_sha256'] != sha(source[plan_path.name]) or (
            review['plan_sha256'] != sha(source[plan_path.name])):
        raise ValueError('Claim/review no longer bind frozen plan')
    journal = rows(source[journal_path.name])
    attempts = rows(source[attempts_path.name])
    raw = rows(source[raw_path.name])
    if len(attempts) != 27 or len(raw) != 27 or len(journal) != 83:
        raise ValueError('Expected terminal 27-attempt prefix missing')
    if journal[0].get('event') != 'phase_started' or journal[-1].get('event') != 'phase_stopped' or (
            journal[-1].get('id'), journal[-1].get('reason')) != ('DEV-027', 'service_error'):
        raise ValueError('Stopped terminal journal not found')
    for index, (attempt, response) in enumerate(zip(attempts, raw)):
        item = planned[index]
        expected_id = f'DEV-{index + 1:03d}'
        if (attempt.get('id') != expected_id or response.get('id') != expected_id or
                attempt.get('attempt_id') != response.get('attempt_id') or
                attempt.get('request_sha256') != item['request_sha256'] or
                response.get('request_sha256') != item['request_sha256'] or
                attempt.get('manifest_sha256') != sha(source[plan_path.name])):
            raise ValueError(f'Frozen attempt/response binding differs: {expected_id}')
        intent, started, finished = journal[1 + index * 3:4 + index * 3]
        if ([x.get('event') for x in (intent, started, finished)] !=
                ['request_intent', 'request_started', 'request_finished'] or
                any(x.get('id') != expected_id for x in (intent, started, finished)) or
                started.get('attempt_id') != attempt['attempt_id'] or
                finished.get('attempt_id') != attempt['attempt_id'] or
                finished.get('status') != attempt.get('status')):
            raise ValueError(f'Journal binding differs: {expected_id}')
        if index < 26 and (attempt.get('status') != 'ok' or response.get('http_status') != 200 or
                           attempt.get('cost_unknown') is not False):
            raise ValueError(f'Completed prefix differs: {expected_id}')
    failed = attempts[-1]
    if (failed.get('status') != 'service_error' or failed.get('http_status') != 429 or
            raw[-1].get('http_status') != 429 or failed.get('cost_unknown') is not True or
            failed.get('observed_cost_usd') is not None or
            Decimal(str(failed.get('reserved_cost_usd'))) != BOUND):
        raise ValueError('DEV-027 HTTP 429 or unknown-cost bound differs')

    live_ledger = CHILD.read_bytes()
    ledger = rows(live_ledger)
    reserves = {x['attempt_id']: Decimal(x['usd']) for x in ledger if x['event'] == 'reserve'}
    settles = {x['attempt_id']: Decimal(x['usd']) for x in ledger if x['event'] == 'settle'}
    if len(reserves) != len([x for x in ledger if x['event'] == 'reserve']) or (
            len(settles) != len([x for x in ledger if x['event'] == 'settle'])):
        raise ValueError('Duplicate ledger event')
    open_reserves = {key: value for key, value in reserves.items() if key not in settles}
    if open_reserves != {failed['attempt_id']: BOUND}:
        raise ValueError('Unknown-cost child reserve differs')
    for attempt in attempts[:26]:
        attempt_id = attempt['attempt_id']
        if (reserves.get(attempt_id) != BOUND or
                settles.get(attempt_id) != Decimal(str(attempt['observed_cost_usd']))):
            raise ValueError(f'Child settlement differs: {attempt["id"]}')
    known_stage = sum((Decimal(str(x['observed_cost_usd'])) for x in attempts[:26]), Decimal())
    known_child = sum(settles.values(), Decimal())
    if CHILD.read_bytes() != live_ledger:
        raise ValueError('Child ledger changed during audit')
    exclusive(SNAPSHOT, live_ledger)
    if sha(SNAPSHOT.read_bytes()) != sha(live_ledger):
        raise ValueError('Child snapshot differs')
    unknown_evidence = (json.dumps({
        'id': 'DEV-027', 'attempt_id': failed['attempt_id'],
        'cost_unknown': True, 'reserved_cost_usd': str(BOUND),
        'source_attempts_sha256': sha(source[attempts_path.name]),
    }, sort_keys=True) + '\n').encode()
    exclusive(UNKNOWN_EVIDENCE, unknown_evidence)
    receipt = {
        'schema': 'deepseek-high-remaining7-fresh2-p2-interruption-audit-v1',
        'status': 'stopped_no_full_phase_score',
        'configuration_id': plan['configuration_id'],
        'stage': 'fresh2/P2/development',
        'planned': 60,
        'attempted': 27,
        'valid_saved': 26,
        'failed': [{'id': 'DEV-027', 'attempt_id': failed['attempt_id'],
                    'status': 'service_error', 'http_status': 429,
                    'cost_unknown': True, 'reserved_upper_bound_usd': str(BOUND)}],
        'unsent': [{'id': item['record_id'], 'request_sha256': item['request_sha256'],
                    'input_sha256': item['input_sha256'],
                    'instruction_sha256': item['instruction_sha256']}
                   for item in planned[27:]],
        'stage_known_cost_usd': str(known_stage),
        'child_cumulative_known_cost_usd': str(known_child),
        'child_open_unknown_reserve_usd': str(BOUND),
        'child_cumulative_accounted_usd': str(known_child + BOUND),
        'child_reconciled': False,
        'source_sha256': {p.name: sha(source[p.name]) for p in source_paths},
        'child_ledger_snapshot_sha256': sha(live_ledger),
        'unknown_cost_evidence_sha256': sha(unknown_evidence),
        'policy': 'Do not replay DEV-001 through DEV-027. Unsent DEV-028 through DEV-060 require separate admission.',
    }
    if len(receipt['unsent']) != 33:
        raise ValueError('Unsent suffix differs')
    encoded = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    exclusive(RECEIPT, encoded)
    return receipt


if __name__ == '__main__':
    result = audit()
    print(json.dumps({k: result[k] for k in ('status', 'attempted', 'valid_saved',
        'stage_known_cost_usd', 'child_cumulative_known_cost_usd',
        'child_open_unknown_reserve_usd', 'child_cumulative_accounted_usd')}, sort_keys=True))
