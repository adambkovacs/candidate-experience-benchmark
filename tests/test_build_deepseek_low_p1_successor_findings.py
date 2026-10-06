"""Portable DeepSeek low P1 composite report checks."""
import json
from pathlib import Path
import shutil
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deepseek_low_p1_successor_findings as report


def test_closed_composite_retains_invalid_and_unknown():
    value = report.build()
    assert value['status'] == 'interrupted_composite_closed'
    assert value['plannedRecords'] == 60
    assert value['valid'] == 57
    assert value['outcomes'] == {'ok': 57, 'invalid_output': 2, 'service_error': 1}
    assert value['invalidIds'] == ['DEV-006', 'DEV-030']
    assert value['providerFailureIds'] == ['DEV-027']
    assert value['cleanFullPhase'] is False and value['fullCleanScore'] is None
    assert value['knownDevelopmentCostUsd'] == '0.030730605596'
    assert value['unknownCostUpperBoundUsd'] == '0.06905856'
    assert 0 <= value['allFourCorrect'] <= 57
    assert all(0 <= n <= 57 for n in value['fieldCorrect'].values())


def test_private_raw_not_a_portable_dependency():
    actual_exists = Path.exists
    private = {report.ROOT / report.PARENT_PRIVATE, report.ROOT / report.TAIL_PRIVATE}
    with mock.patch.object(Path, 'exists', autospec=True,
                           side_effect=lambda path: False if path in private else actual_exists(path)):
        value = report.build()
    bound = {row['path'] for row in value['sourceBindings']}
    assert str(report.PARENT_PRIVATE) not in bound
    assert str(report.TAIL_PRIVATE) not in bound
    assert str(report.PROJECTION) in bound
    assert str(report.PROJECTION_RECEIPT) in bound
    assert str(report.PARENT_SNAPSHOT) in bound
    assert str(report.TAIL_SNAPSHOT) in bound


def test_projection_matches_private_attempt_hashes_and_published_feed():
    projection = json.loads((ROOT / report.PROJECTION).read_text())
    assert projection['parent_private_attempts_sha256'] == report.sha(ROOT / report.PARENT_PRIVATE)
    assert projection['suffix_private_attempts_sha256'] == report.sha(ROOT / report.TAIL_PRIVATE)
    assert json.loads((ROOT / report.OUTPUT).read_text()) == report.build()


def test_project_row_rejects_changed_frozen_request():
    row = {'id': 'DEV-028', 'request_sha256': 'a', 'input_sha256': 'b',
           'instruction_sha256': 'c', 'reference_labels_read': False,
           'requested_model': 'deepseek/deepseek-v4.1-flash',
           'reasoning_effort': 'low', 'status': 'ok', 'prediction': {
               'sentiment': 'positive', 'follow_up_needed': 'no',
               'serious_concern_reported': 'no', 'testimonial_potential': 'yes'},
           'cost_unknown': False, 'billing_ok': True, 'observed_cost_usd': '0.0001'}
    frozen = {'record_id': 'DEV-028', 'request_sha256': 'different',
              'input_sha256': 'b', 'instruction_sha256': 'c'}
    with pytest.raises(ValueError, match='frozen request'):
        report.project_row(row, frozen)


def test_portable_projection_tamper_is_rejected(tmp_path):
    value = report.build()
    for item in value['sourceBindings']:
        target = tmp_path / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / item['path'], target)
    assert report.build(tmp_path) == value
    projection_path = tmp_path / report.PROJECTION
    projection = json.loads(projection_path.read_text())
    projection['positions'][0]['prediction']['sentiment'] = 'negative'
    projection_path.write_text(json.dumps(projection) + '\n')
    with pytest.raises(ValueError, match='projection_sha256|closure or projection'):
        report.build(tmp_path)
