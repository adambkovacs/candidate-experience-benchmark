"""Exercise both low-adapter review states without changing frozen admission files.

The source-bound historical test assumes the pre-admission review template. It
can be invoked with a temporary review fixture after admission, while this
module also checks the current approved gate. Pages CI selects explicit
unittest modules and does not select either low-adapter pytest module.
"""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_remaining6_execution_v1 as adapter
from tests import test_deepseek_low_remaining6_execution_v1 as archived


def test_frozen_pre_admission_gate_with_isolated_review(tmp_path):
    review = tmp_path / 'root-review.json'
    review.write_text(json.dumps(adapter.review_template()) + '\n')
    with mock.patch.object(adapter, 'REVIEW', review):
        archived.test_manifest_binding_review_gate_and_prepare_refusal()


def test_approved_gate_with_isolated_review(tmp_path):
    review = tmp_path / 'root-review.json'
    approved = adapter.review_template()
    approved.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    review.write_text(json.dumps(approved) + '\n')
    with mock.patch.object(adapter, 'REVIEW', review):
        adapter.require_review()
        approved['manifest_sha256'] = '0' * 64
        review.write_text(json.dumps(approved) + '\n')
        with pytest.raises(ValueError, match='review missing or mismatched'):
            adapter.require_review()
