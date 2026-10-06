"""Offline report gates for archived high exact-unsent continuation evidence."""
import json
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deepseek_high_remaining6_successor_findings as report


def copied_root(tmp_path):
    published = report.build()
    for item in published['sourceBindings']:
        source = ROOT / item['path']
        target = tmp_path / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path


def test_archived_suffix_and_full_phases_stay_separate():
    result = report.build()
    assert result['publishedClosedStages'] == ['fresh2/P2', 'fresh2/P0', 'fresh2/P1', 'fresh3/P1', 'fresh3/P2']
    assert result['matchedCleanRepeatEligible'] is False
    composite = result['phases']['fresh2/P2']
    assert composite['status'] == 'interrupted_composite_descriptive_only'
    assert composite['score']['denominator'] == 60
    assert (composite['score']['valid'], composite['score']['allFour']) == (59, 56)
    assert composite['score']['invalidIds'] == ['DEV-027']
    assert composite['knownDevelopmentCostUsd'] == '0.028609033890'
    assert composite['unknownCostUpperBoundUsd'] == '0.06905856'
    p0 = result['phases']['fresh2/P0']
    assert p0['status'] == 'completed_with_intrinsic_invalid'
    assert (p0['score']['valid'], p0['score']['allFour']) == (59, 58)
    assert p0['score']['invalidIds'] == ['DEV-006']
    assert p0['knownDevelopmentCostUsd'] == '0.031520474702'
    p1 = result['phases']['fresh2/P1']
    assert p1['status'] == 'completed'
    assert (p1['score']['valid'], p1['score']['allFour']) == (60, 58)
    assert p1['score']['invalidIds'] == []
    assert p1['knownDevelopmentCostUsd'] == '0.0277482953'


def test_published_bytes_match_archived_sources():
    assert json.loads((ROOT / report.OUTPUT).read_text()) == report.build()


def test_selected_root_rebuilds_and_rejects_tampered_raw(tmp_path):
    root = copied_root(tmp_path)
    assert report.build(root) == report.build()
    raw = root / report.EXECUTION / 'fresh2/P0/development.responses.jsonl'
    raw.write_bytes(raw.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='source hash differs'):
        report.build(root)


def test_selected_root_rejects_different_reporter(tmp_path):
    root = copied_root(tmp_path)
    builder = root / 'scripts/build_deepseek_high_remaining6_successor_findings.py'
    builder.write_bytes(builder.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='reporter differs'):
        report.build(root)


def test_unfinished_future_phase_is_not_promoted():
    result = report.build()
    assert 'fresh3/P0' not in result['phases']


def test_parent_projection_keeps_private_provider_responses_out_of_bundle(tmp_path):
    root = copied_root(tmp_path)
    private = root / report.PARENT / 'development.responses.jsonl'
    assert not private.exists()
    projection = json.loads((root / report.PARENT / 'development.public.json').read_text())
    assert all(set(row) == {'id', 'status', 'prediction', 'cost_unknown',
                            'observed_cost_usd'} for row in projection['attempts'])
    assert projection['attempts'][-1]['id'] == 'DEV-027'
    assert projection['attempts'][-1]['cost_unknown'] is True
    assert report.build(root)['phases']['fresh2/P2']['score']['allFour'] == 56


def test_parent_projection_rejects_changed_provenance(tmp_path):
    root = copied_root(tmp_path)
    path = root / report.PARENT / 'development.public.json'
    projection = json.loads(path.read_text())
    projection['source_sha256']['development.attempts.jsonl'] = '0' * 64
    path.write_text(json.dumps(projection))
    with pytest.raises(ValueError, match='projection provenance differs'):
        report.build(root)


def test_parent_projection_rejects_prediction_change_without_private_raw(tmp_path):
    root = copied_root(tmp_path)
    path = root / report.PARENT / 'development.public.json'
    projection = json.loads(path.read_text())
    projection['attempts'][0]['prediction']['sentiment'] = 'negative'
    path.write_text(json.dumps(projection))
    with pytest.raises(ValueError, match='projection receipt differs'):
        report.build(root)


def test_equal_scores_preserve_record_level_changes():
    result = report.build()
    for key in ('p1TwoPassRepeat', 'fresh3PromptChange'):
        assert result[key]['allFourScores'] == [58, 58]
        assert result[key]['changedRecordIds'] == ['DEV-030']
        assert result[key]['changedRecords'] == 1
        assert result[key]['denominator'] == 60
    assert result['phases']['fresh3/P1']['fieldCorrect']['serious_concern_reported'] == 58
    assert result['phases']['fresh3/P2']['fieldCorrect']['serious_concern_reported'] == 59
