"""Offline publication gates for the separate high price-control configuration."""
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deepseek_high_remaining7_price_findings as report


def test_no_receipt_keeps_prior_public_series_unchanged(tmp_path):
    with mock.patch.object(report, 'folder_for', return_value=tmp_path):
        assert report.build() == report.previous.build(ROOT)


def test_separate_configuration_and_exact_source_contract():
    assert report.CONFIG != report.adapter.prior.CONFIG
    assert report.adapter.proposal.PHASES[0] == ('fresh1', 'P2')
    sources = report.required_sources('fresh1', 'P2')
    assert report.relative(report.adapter.MANIFEST) in sources
    assert report.relative(report.adapter.proposal.MANIFEST) in sources
    assert report.relative(report.BASE / 'fresh1/manifest.json') in sources
    assert report.relative(report.folder_for('fresh1', 'P2') /
                           'closure-ledger-snapshot.jsonl') in sources
    assert report.relative(report.adapter.CHILD_LEDGER) not in sources
    with pytest.raises(ValueError, match='outside remaining'):
        report.folder_for('fresh1', 'P0')


def test_ledger_requires_each_exact_reserve_and_settlement():
    attempt = {'id': 'DEV-001', 'attempt_id': 'attempt-one',
               'reserved_cost_usd': '0.06905856',
               'observed_cost_usd': '0.00042',
               'billing_ok': True, 'cost_unknown': False}
    events = [{'event': 'budget', 'cap_usd': '1.00'},
              {'event': 'reserve', 'attempt_id': 'attempt-one',
               'record_id': 'DEV-001', 'usd': '0.06905856'},
              {'event': 'settle', 'attempt_id': 'attempt-one',
               'usd': '0.00042'}]
    raw = ''.join(json.dumps(row) + '\n' for row in events).encode()
    assert report.ledger_evidence(raw, [attempt]) == (1, Decimal('0.00042'))
    changed = [dict(row) for row in events]
    changed[2]['usd'] = '0.00041'
    with pytest.raises(ValueError, match='reserve or settlement'):
        report.ledger_evidence(''.join(json.dumps(row) + '\n'
                          for row in changed).encode(), [attempt])
    with pytest.raises(ValueError, match='prefix or event count'):
        report.ledger_evidence(raw + raw.splitlines()[-1] + b'\n', [attempt])
    with pytest.raises(ValueError, match='Incomplete'):
        report.ledger_evidence(raw[:-1], [attempt])


def test_closure_gate_rejects_unbound_or_unapproved_receipt(tmp_path):
    folder = tmp_path / 'fresh1' / 'P2'
    folder.mkdir(parents=True)
    receipt = folder / 'closure.review.json'
    receipt.write_text(json.dumps({'schema': report.SCHEMA,
                                   'verdict': 'APPROVE',
                                   'source_bindings': {}}) + '\n')
    with mock.patch.object(report, 'folder_for', return_value=folder), \
         mock.patch.object(report, 'required_sources',
                           return_value={'README.md': ROOT / 'README.md'}):
        with pytest.raises(ValueError, match='source set'):
            report.verified_closure('fresh1', 'P2', [])


def test_smoke_inspection_must_bind_saved_evidence(tmp_path):
    (tmp_path / 'smoke-inspection.json').write_text(json.dumps({
        'decision': 'accepted_unchanged', 'configuration_id': report.CONFIG,
        'manifest_sha256': 'a', 'journal_sha256': 'b',
        'attempts_sha256': 'c', 'responses_sha256': 'd'}) + '\n')
    report.inspected_smoke(tmp_path, {'manifest_sha256': 'a',
        'journal_sha256': 'b', 'attempts_sha256': 'c', 'responses_sha256': 'd'})
    with pytest.raises(ValueError, match='binding changed'):
        report.inspected_smoke(tmp_path, {'manifest_sha256': 'x',
            'journal_sha256': 'b', 'attempts_sha256': 'c', 'responses_sha256': 'd'})
