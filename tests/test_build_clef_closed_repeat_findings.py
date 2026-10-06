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
    assert all(len(cell['fieldMetrics']) == 4 for cell in data['cells'])
    assert all(cell['inputTokensObserved'] > 0 for cell in data['cells']
               if cell['valid'])


def test_saved_feed_exact_and_source_bound():
    data = report.build()
    saved = json.loads((report.ROOT / report.OUTPUT).read_bytes())
    assert saved == data
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
