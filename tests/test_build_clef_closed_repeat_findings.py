"""Closed-only Clef repeat report checks, including interrupted P2 denominators."""

import json
from pathlib import Path
import shutil

import pytest

import build_clef_closed_repeat_findings as report


def test_all_declared_cells_and_interrupted_boundaries():
    data = report.build()
    assert len(data['cells']) == 9
    assert data['completeCleanCells'] == 7
    assert data['interruptedCells'] == 2
    by_key = {f"{cell['repeat']}/{cell['condition']}": cell
              for cell in data['cells']}
    first = by_key['fresh1/P2']
    assert first['status'] == 'interrupted_composite'
    assert (first['attempted'], first['valid'], first['unknownOutcome'],
            first['neverSent']) == (60, 59, 1, 0)
    assert first['agreementOf60'] is None
    last = by_key['fresh3/P2']
    assert last['status'] == 'interrupted_provider'
    assert (last['attempted'], last['valid'], last['unknownOutcome'],
            last['neverSent']) == (1, 0, 1, 59)
    assert last['agreementOf60'] is None
    assert last['inputTariffEstimateUsd'] is None
    assert all(cell['valid'] == 60 and cell['agreementOf60'] is not None
               for cell in data['cells'] if cell['status'] == 'complete')
    assert len(data['cleanRepeatFlips']) == 6
    assert len(data['matchedPromptDifferences']) == 5
    assert len(data['promptComparisonExclusions']) == 4
    assert all(len(cell['fieldMetrics']) == 4 for cell in data['cells'])
    assert all(cell['inputTokensObserved'] > 0 for cell in data['cells']
               if cell['valid'])


def test_matched_prompt_correctness_transitions_keep_full_denominators():
    data = report.build()
    pairs = {(item['repeat'], item['left'], item['right']): item
             for item in data['matchedPromptDifferences']}
    assert set(pairs) == {
        ('fresh1', 'P0', 'P1'), ('fresh2', 'P0', 'P1'),
        ('fresh2', 'P0', 'P2'), ('fresh2', 'P1', 'P2'),
        ('fresh3', 'P0', 'P1')}
    assert (pairs['fresh1', 'P0', 'P1']['becameAllFourCorrectIds'],
            pairs['fresh1', 'P0', 'P1']['lostAllFourCorrectIds']) == (
                ['DEV-056'], ['DEV-013', 'DEV-014'])
    assert (pairs['fresh2', 'P0', 'P2']['becameAllFourCorrectIds'],
            pairs['fresh2', 'P0', 'P2']['lostAllFourCorrectIds']) == (
                [], ['DEV-013', 'DEV-014', 'DEV-018', 'DEV-035'])
    for pair in pairs.values():
        assert pair['denominator'] == pair['sharedValidDenominator'] == 60
        assert pair['excludedInvalidOrUnknownIds'] == []
        assert pair['gainedAllFour'] == len(pair['becameAllFourCorrectIds'])
        assert pair['lostAllFour'] == len(pair['lostAllFourCorrectIds'])
        assert pair['rightAllFour'] - pair['leftAllFour'] == (
            pair['gainedAllFour'] - pair['lostAllFour'])
    excluded = data['promptComparisonExclusions']
    assert {(item['repeat'], item['left'], item['right']) for item in excluded} == {
        ('fresh1', 'P0', 'P2'), ('fresh1', 'P1', 'P2'),
        ('fresh3', 'P0', 'P2'), ('fresh3', 'P1', 'P2')}
    assert all(item['comparisonDenominator'] is None for item in excluded)
    assert all(item['runOutcomes']['P2']['unknownOutcome'] == 1 for item in excluded)
    assert [item['runOutcomes']['P2']['neverSent'] for item in excluded] == [0, 0, 59, 59]


def test_saved_feed_exact_and_source_bound():
    data = report.build()
    saved = json.loads((report.ROOT / report.OUTPUT).read_bytes())
    assert saved == data
    assert (report.ROOT / report.OUTPUT).read_bytes() == (
        report.ROOT / 'public-site/clef-closed-repeat-findings.json').read_bytes()
    assert 'actualChargedUsd' not in json.dumps(data)
    assert str(report.SNAPSHOT) in data['sourceBindings']
    assert str(report.QUOTA) in data['sourceBindings']


def test_tampered_terminal_record_refused(tmp_path):
    root = tmp_path / 'checkout'
    source = report.ROOT
    for name in report.build()['sourceBindings']:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    copied = root / report.BASE / 'clef/fresh2/P2/development/records.jsonl'
    lines = copied.read_text().splitlines()
    row = json.loads(lines[0]); row['status'] = 'unknown_outcome'
    lines[0] = json.dumps(row)
    copied.write_text('\n'.join(lines) + '\n')
    with pytest.raises(ValueError):
        report.build(root)


def test_alternate_checkout_cannot_claim_unexecuted_prompt_module(tmp_path):
    root = tmp_path / 'checkout'
    for name in report.build()['sourceBindings']:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report.ROOT / name, target)
    source = root / 'scripts/jev_native_prompt_variants_v1.py'
    source.write_bytes(source.read_bytes() + b'\n# Changed only in copied checkout.\n')
    with pytest.raises(ValueError, match='Executed prompt module differs'):
        report.build(root)
