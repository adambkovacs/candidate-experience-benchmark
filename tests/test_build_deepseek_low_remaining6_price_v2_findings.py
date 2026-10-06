"""Descriptive revised-price low P2 reporting from the sealed projection."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deepseek_low_remaining6_price_v2_findings as report


def portable_tree(tmp_path):
    for relative in (report.PROJECTION, report.CORRECTION, report.AUDIT,
                     report.PARENT_PLAN, report.SUFFIX_PLAN, report.LABELS,
                     Path('scripts/build_deepseek_low_remaining6_price_v2_findings.py'),
                     Path('tests/test_build_deepseek_low_remaining6_price_v2_findings.py'),
                     Path('scripts/development_benchmark.py')):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def test_source_bound_60_position_descriptive_result_is_portable(tmp_path):
    built = report.build(portable_tree(tmp_path))
    item = built['series'][0]
    assert item['score']['denominator'] == 60
    assert item['score']['valid'] == 59
    assert item['score']['allFour'] == 57
    assert item['score']['fields'] == {'sentiment': 59, 'follow_up_needed': 58,
                                     'serious_concern_reported': 57,
                                     'testimonial_potential': 59}
    assert item['score']['invalidIds'] == ['DEV-005']
    assert item['cleanMatchedRepeatEligible'] is False
    assert item['developmentKnownCostUsd'] == '0.030564226637'
    assert item['developmentUnknownCostUpperBoundUsd'] == '0.06905856'
    assert set(built['privateAttemptSourceSha256']) == {str(report.PARENT_ATTEMPTS),
                                                        str(report.SUFFIX_ATTEMPTS)}
    assert set(item['score']['confusionCounts']) == set(item['score']['fields'])
    assert set(item['score']['predictedClassCounts']) == set(item['score']['fields'])


def test_changed_projection_prediction_rejected_even_if_hash_updated(tmp_path):
    root = portable_tree(tmp_path)
    path = root / report.PROJECTION
    value = json.loads(path.read_text())
    value['positions'][0]['prediction']['sentiment'] = 'negative'
    path.write_text(json.dumps(value) + '\n')
    updated = hashlib.sha256(path.read_bytes()).hexdigest()
    with mock.patch.object(report, 'PROJECTION_SHA', updated):
        with pytest.raises(ValueError, match='reviewed values'):
            report.build(root)


def test_changed_cost_correction_rejected(tmp_path):
    root = portable_tree(tmp_path)
    path = root / report.CORRECTION
    value = json.loads(path.read_text())
    value['corrected_value_usd'] = '0.031550332637'
    path.write_text(json.dumps(value) + '\n')
    with pytest.raises(ValueError, match='corrected cost'):
        report.build(root)


def test_published_bytes_equal_rebuild():
    expected = json.dumps(report.build(), indent=2, ensure_ascii=False) + '\n'
    assert (ROOT / report.OUTPUT).read_text() == expected
