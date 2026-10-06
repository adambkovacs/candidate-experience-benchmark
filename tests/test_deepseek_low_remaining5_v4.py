"""Offline proof for the five untouched DeepSeek low phases."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_low_remaining5_v4 as proposal


def test_predecessor_is_sealed_and_retains_original_unknown_cost():
    audit = proposal.predecessor_closed()
    assert audit['suffix_attempt_count'] == audit['suffix_valid_count'] == 55
    assert audit['composite_unknown_cost_ids'] == ['DEV-005']
    assert audit['full_60_clean_score'] is None


def test_exact_five_unclaimed_frozen_phases_only():
    result = proposal.proposal_data(require_unclaimed=True)
    assert [(row['fresh_pass'], row['condition']) for row in result['remaining_phase_order']] == list(proposal.PHASES)
    assert set(result['phase_request_sha256']) == {f'{a}/{b}' for a, b in proposal.PHASES}
    assert all(len(hashes) == 60 for hashes in result['phase_request_sha256'].values())
    assert result['predecessor_unknown_cost_upper_bound_usd'] == '0.06905856'
    assert result['dispatch_authorized'] is False


def test_forged_settlement_rejected(tmp_path):
    rows = proposal.SNAPSHOT.read_text().splitlines()
    event = json.loads(rows[2])
    assert event['event'] == 'settle'
    event['usd'] = '0.06905857'
    rows[2] = json.dumps(event)
    altered = tmp_path / 'snapshot.jsonl'
    altered.write_text('\n'.join(rows) + '\n')
    with mock.patch.object(proposal, 'SNAPSHOT', altered):
        with pytest.raises(ValueError):
            proposal.predecessor_closed()


def test_changed_frozen_request_rejected():
    source = json.loads((proposal.PREDECESSOR_PLAN / 'fresh2/manifest.json').read_text())
    changed = deepcopy(source)
    changed['conditions']['P0']['development'][0]['payload']['max_tokens'] += 1
    with mock.patch.object(proposal, 'json', wraps=json) as reader:
        original_loads = json.loads
        def changed_source(raw, *args, **kwargs):
            value = original_loads(raw, *args, **kwargs)
            if value == source:
                return changed
            return value
        reader.loads.side_effect = changed_source
        with pytest.raises(ValueError, match='payload identity'):
            proposal.proposal_data()
