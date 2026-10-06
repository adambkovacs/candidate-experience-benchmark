#!/usr/bin/env python3
"""Audit the stopped low price-v2 P2 prefix and propose only unsent IDs."""
import argparse
import base64
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path

import deepseek_low_remaining6_execution_v1 as adapter
from development_benchmark import valid

ROOT = adapter.ROOT
BASE = adapter.BASE
FOLDER = BASE / 'fresh2/P2'
OUTPUT = adapter.proposal.BASE / 'fresh2-p2-dev005-interruption.audit-candidate.json'
LEDGER_SNAPSHOT = FOLDER / 'interruption-ledger-snapshot.jsonl'
SCHEMA = 'deepseek-low-remaining6-price-v2-dev005-interruption-v1'
SENT = [f'DEV-{n:03}' for n in range(1, 6)]
UNSENT = [f'DEV-{n:03}' for n in range(6, 61)]


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError('Incomplete interruption evidence: ' + str(path))
    return [json.loads(line) for line in raw.splitlines()]


def validate_prefix(plan, journal, attempts, responses):
    planned = plan['conditions']['P2']['development']
    if ([row['record_id'] for row in planned] != adapter.proposal.IDS or
            [row.get('id') for row in attempts] != SENT or
            [row.get('id') for row in responses] != SENT or
            len(journal) != 17 or
            any(journal[0].get(key) != value for key, value in
                {'event': 'phase_started', 'configuration_id': adapter.proposal.CONFIG,
                 'fresh_pass': 'fresh2', 'condition': 'P2', 'phase': 'development'}.items()) or
            journal[-1].get('event') != 'phase_stopped' or
            journal[-1].get('id') != 'DEV-005' or
            journal[-1].get('reason') != 'service_error' or
            any(row.get('event') == 'phase_completed' for row in journal)):
        raise ValueError('Stopped low prefix or lifecycle differs')
    for n, (request, attempt, response) in enumerate(zip(planned, attempts, responses)):
        rid = SENT[n]
        if (attempt.get('configuration_id') != adapter.proposal.CONFIG or
                attempt.get('fresh_pass') != 'fresh2' or
                attempt.get('condition') != 'P2' or
                attempt.get('phase') != 'development' or
                attempt.get('manifest_sha256') != sha(BASE / 'fresh2/manifest.json') or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('request') != request['payload'] or
                attempt.get('input_sha256') != request['input_sha256'] or
                attempt.get('instruction_sha256') != request['instruction_sha256'] or
                attempt.get('reference_labels_read') is not False or
                attempt.get('reserved_cost_usd') != str(adapter.proposal.RESERVE) or
                response.get('attempt_id') != attempt.get('attempt_id') or
                response.get('request_sha256') != request['request_sha256'] or
                response.get('body_truncated_at_limit') is not False or
                response.get('read_error') is not None):
            raise ValueError('Stopped low attempt differs from frozen request')
        for offset, event in enumerate(('request_intent', 'request_started',
                                        'request_finished'), start=1):
            actual = journal[1 + n * 3 + offset - 1]
            if (actual.get('event') != event or actual.get('id') != rid or
                    (event != 'request_finished' and
                     actual.get('request_sha256') != request['request_sha256']) or
                    (event != 'request_intent' and
                     actual.get('attempt_id') != attempt.get('attempt_id'))):
                raise ValueError('Stopped low journal order differs')
        body = base64.b64decode(response.get('body_base64', ''), validate=True)
        if len(body) != response.get('body_bytes_captured'):
            raise ValueError('Stopped low raw response length differs')
        if n < 4:
            if (attempt.get('status') != 'ok' or
                    attempt.get('billing_ok') is not True or
                    attempt.get('cost_unknown') is not False or
                    attempt.get('observed_cost_usd') is None or
                    attempt.get('response_diagnostic', {}).get('passed') is not True or
                    not valid(attempt.get('prediction')) or
                    response.get('http_status') != 200 or
                    json.loads(body) != attempt.get('raw_response')):
                raise ValueError('Known low prefix response differs')
        elif (attempt.get('status') != 'service_error' or
              attempt.get('billing_ok') is not False or
              attempt.get('cost_unknown') is not True or
              attempt.get('observed_cost_usd') is not None or
              response.get('http_status') != 429):
            raise ValueError('DEV-005 unknown-cost provider failure was changed')
        finished = journal[3 + n * 3]
        if (finished.get('status') != attempt.get('status') or
                finished.get('billing_ok') != attempt.get('billing_ok') or
                finished.get('cost_unknown') != attempt.get('cost_unknown') or
                finished.get('observed_cost_usd') != attempt.get('observed_cost_usd')):
            raise ValueError('Stopped low journal billing differs')
    if len({row.get('attempt_id') for row in attempts}) != 5:
        raise ValueError('Stopped low attempt identities duplicate')
    return [row['request_sha256'] for row in planned[5:]]


def ledger_prefix(raw, smoke, development):
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete low child ledger')
    events = [json.loads(line) for line in raw.splitlines()]
    attempts = [*smoke, *development]
    if (events[0] != {'event': 'budget', 'cap_usd': '0.75'} or
            len(attempts) != 8 or len(events) != 16 or
            [row.get('id') for row in smoke] != SENT[:3]):
        raise ValueError('Low child ledger prefix differs')
    known = Decimal(0)
    for n, attempt in enumerate(attempts):
        reserve = events[1 + 2*n]
        if reserve != {'event': 'reserve', 'attempt_id': attempt['attempt_id'],
                       'record_id': attempt['id'],
                       'usd': attempt['reserved_cost_usd']}:
            raise ValueError('Low child ledger reserve differs')
        if n == 7:
            if (attempt['id'] != 'DEV-005' or attempt['cost_unknown'] is not True or
                    attempt.get('observed_cost_usd') is not None):
                raise ValueError('Low unknown reservation was changed')
            break
        settle = events[2 + 2*n]
        if (settle != {'event': 'settle', 'attempt_id': attempt['attempt_id'],
                       'usd': attempt['observed_cost_usd']} or
                attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                not Decimal(0) <= Decimal(attempt['observed_cost_usd']) <=
                    Decimal(attempt['reserved_cost_usd'])):
            raise ValueError('Low child ledger settlement differs')
        known += Decimal(attempt['observed_cost_usd'])
    return known


def audit():
    adapter.verify()
    plan = adapter.verify_plan('fresh2', sha(BASE / 'fresh2/manifest.json'))
    claim = json.loads((FOLDER / 'development.claim.json').read_text())
    if (claim.get('configuration_id') != adapter.proposal.CONFIG or
            claim.get('fresh_pass') != 'fresh2' or claim.get('condition') != 'P2' or
            claim.get('phase') != 'development' or
            claim.get('manifest_sha256') != sha(BASE / 'fresh2/manifest.json')):
        raise ValueError('Low stopped claim differs')
    journal = rows(FOLDER / 'development.journal.jsonl')
    attempts = rows(FOLDER / 'development.attempts.jsonl')
    responses = rows(FOLDER / 'development.responses.jsonl')
    smoke = rows(FOLDER / 'smoke.attempts.jsonl')
    unsent_hashes = validate_prefix(plan, journal, attempts, responses)
    with adapter.CHILD_LEDGER.open('rb') as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        ledger = handle.read()
        fcntl.flock(handle, fcntl.LOCK_UN)
    known = ledger_prefix(ledger, smoke, attempts)
    paths = [adapter.proposal.MANIFEST, adapter.MANIFEST,
             BASE / 'fresh2/manifest.json', adapter.BUDGET,
             FOLDER / 'development.claim.json',
             *(FOLDER / ('development.' + kind + '.jsonl')
               for kind in ('journal', 'attempts', 'responses')),
             FOLDER / 'smoke.claim.json', FOLDER / 'smoke.root-review.json',
             FOLDER / 'smoke-inspection.json',
             *(FOLDER / ('smoke.' + kind + '.jsonl')
               for kind in ('journal', 'attempts', 'responses')),
             ROOT / 'scripts/deepseek_low_remaining6_unsent_v1.py',
             ROOT / 'tests/test_deepseek_low_remaining6_unsent_v1.py']
    bindings = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    bindings[str(LEDGER_SNAPSHOT.relative_to(ROOT))] = sha_bytes(ledger)
    return {'schema': SCHEMA, 'status': 'stopped_unknown_cost',
            'configuration_id': adapter.proposal.CONFIG,
            'stage': 'fresh2/P2/development',
            'terminal_phase_completed': False,
            'completed_score': None,
            'sent_ids': SENT, 'known_valid_prefix_ids': SENT[:4],
            'unknown_cost_ids': ['DEV-005'],
            'unknown_reserved_usd': str(adapter.proposal.RESERVE),
            'known_child_settled_usd': str(known),
            'next_unsent_id': 'DEV-006', 'unsent_ids': UNSENT,
            'continuation': {'status': 'offline_proposal_unadmitted',
                'repeat': 'fresh2', 'condition': 'P2',
                'development_ids': UNSENT,
                'request_sha256': unsent_hashes,
                'no_retry_ids': SENT,
                'new_allocation_authorized': False,
                'dispatch_authorized': False,
                'price_control_configuration': adapter.proposal.CONFIG},
            'private_evidence_bindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('audit', 'prepare'))
    args = parser.parse_args()
    value = audit()
    if args.action == 'prepare':
        if OUTPUT.exists():
            raise FileExistsError('Low interruption candidate already prepared')
        with adapter.CHILD_LEDGER.open('rb') as source:
            fcntl.flock(source, fcntl.LOCK_SH)
            snapshot = source.read()
            fcntl.flock(source, fcntl.LOCK_UN)
        if sha_bytes(snapshot) != value['private_evidence_bindings'][
                str(LEDGER_SNAPSHOT.relative_to(ROOT))]:
            raise ValueError('Low child ledger changed during interruption audit')
        if LEDGER_SNAPSHOT.exists():
            if LEDGER_SNAPSHOT.read_bytes() != snapshot:
                raise ValueError('Saved low interruption snapshot differs')
        else:
            with LEDGER_SNAPSHOT.open('xb') as handle:
                handle.write(snapshot)
        with OUTPUT.open('x') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
        print(sha(OUTPUT))
    else:
        print(json.dumps({key: value[key] for key in (
            'schema', 'status', 'stage', 'terminal_phase_completed',
            'known_valid_prefix_ids', 'unknown_cost_ids',
            'unknown_reserved_usd', 'next_unsent_id')}, indent=2))


if __name__ == '__main__':
    main()
