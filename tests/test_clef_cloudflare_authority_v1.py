"""Offline checks for the historical Cloudflare Clef money boundary."""

import json
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import clef_cloudflare_authority_v1 as audit


def test_saved_proposal_rebuilds_exactly():
    saved = json.loads(audit.RECEIPT.read_bytes())
    assert audit.audit() == saved
    assert saved['historical_hold_usd'] == '7.656482'
    assert saved['successful_response_upper_bound_usd'] == '0.247786'
    assert saved['retained_unknown_usd'] == '0.011798'
    assert saved['total_upper_bound_usd'] == '0.259584'
    assert len(saved['stages']) == 27
    assert sum(s['attempted'] for s in saved['stages']) == 761


def test_unknown_positions_keep_full_reserved_amount():
    saved = audit.audit()
    stopped = [s for s in saved['stages'] if Decimal(s['retained_unknown_usd'])]
    assert [(s['stage'], s['attempted'], s['retained_unknown_usd']) for s in stopped] == [
        ('clef-flash/fresh3/P0/development', 1, '0.005899'),
        ('clef-flash/fresh3/P0/development-suffix-v1', 1, '0.005899'),
    ]


def test_stage_raw_drift_fails_closed(tmp_path):
    source = audit.BASE / 'clef/fresh1/P1/smoke'
    target = tmp_path / 'results/clef-native-v1/clef/fresh1/P1/smoke'
    target.mkdir(parents=True)
    for name in ('completion.json', 'claim.json', 'journal.jsonl', 'raw.jsonl', 'records.jsonl'):
        (target / name).write_bytes((source / name).read_bytes())
    audit.audit_stage(target, tmp_path)
    with (target / 'raw.jsonl').open('ab') as stream:
        stream.write(b'\n')
    with pytest.raises(ValueError, match='binding'):
        audit.audit_stage(target, tmp_path)


def test_price_bound_and_invalid_usage():
    assert audit.request_ceiling('clef', 65536) == Decimal('0.015729')
    assert audit.request_ceiling('clef-flash', 65536) == Decimal('0.005899')
    with pytest.raises(ValueError, match='tokens'):
        audit.request_ceiling('clef', 65537)
