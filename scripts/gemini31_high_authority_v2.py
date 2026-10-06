#!/usr/bin/env python3
"""Source-bound Gemini 3.1 Pro high repeats under the amended OpenRouter cap.

This bridge reuses the frozen repeat mechanics while requiring a separately
reviewed OpenRouter-only authority hold. Preparing plans is offline.
"""
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority

PATH = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location('_gemini31_high_frozen_repeat_v2', PATH.with_name('gemini_repeat_roster.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

runner.BASE = runner.ROOT / 'results/repeatability-v1/gemini31-high-authority-v2'
runner.SCHEMA = 'gemini31-pro-preview-high-repeat-authority-v2'
runner.REVIEW_SCHEMA = 'gemini31-pro-preview-high-repeat-authority-review-v2'
runner.CONFIGS = {
    'gemini31-pro-preview-high-p0-openrouter-v3': (
        'gemini31-pro-preview-high', 'google/gemini-3.1-pro-preview', 'high',
        'g31-pro-high-repeat-authority-v2', '2.00'),
}
runner.SOURCE_CODE = (*runner.SOURCE_CODE,
                      'scripts/gemini31_high_authority_v2.py',
                      'scripts/paid_budget_partitions_v4.py',
                      'scripts/paid_budget_partitions_v3.py',
                      'scripts/openrouter_budget_v4.py',
                      'scripts/openrouter_budget_amendment_v3.py',
                      'scripts/postapproval_authority_v3.py',
                      'scripts/postapproval_authority_v2.py')
runner.open_partition = partitions.open_partition
AUTHORITY = runner.ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
_original_review_gate = runner.review_gate


def review_gate(plan, phase, condition, review_path, plan_sha):
    budget_path = _original_review_gate(plan, phase, condition, review_path, plan_sha)
    snapshot = authority.read_authority(AUTHORITY)
    if not snapshot.amendment_complete:
        raise ValueError('Reviewed OpenRouter authority amendment is incomplete')
    receipt = json.loads(runner.path_inside(review_path).read_text())
    if receipt.get('authority_ledger') != str(AUTHORITY):
        raise ValueError('Root review does not name the authority ledger')
    events = runner.lines(AUTHORITY)
    holds = [event for event in events if event.get('event') == 'hold'
             and event.get('id') == plan['partition_id']]
    if len(holds) != 1:
        raise ValueError('Exact Gemini authority hold missing or duplicated')
    hold = holds[0]
    source_sha = runner.digest(runner.plan_path(plan['configuration_id'], 'repeat2').read_bytes())
    if (hold.get('version') != 3 or hold.get('funding_pool') != 'openrouter_additional'
            or hold.get('source_sha256') != source_sha
            or Decimal(hold['usd']) != Decimal(plan['proposed_partition_cap_usd'])
            or hold.get('budget_manifest_path') != str(budget_path)
            or hold.get('budget_manifest_sha256') != runner.digest(budget_path.read_bytes())
            or hold.get('partition_id') != plan['partition_id']
            or hold.get('master_path') != str(runner.MASTER)):
        raise ValueError('Gemini authority hold differs from plan and reviewed child')
    return budget_path


runner.review_gate = review_gate
_original_run = runner.run


def run(plan_path_value, plan_sha, review_path, condition, phase, env_file=None):
    plan = runner.validate_plan(plan_path_value, plan_sha)
    runner.require_order(plan, condition, phase)
    budget_path = review_gate(plan, phase, condition, review_path, plan_sha)
    request = plan['conditions'][condition]['requests'][0 if phase == 'smoke' else 1]
    child = partitions.open_partition(runner.MASTER, budget_path, plan['partition_id'],
                                      plan['model'], runner.v3.PROVIDER, plan['effort'])
    try:
        _, pending, blocked = child.state()
        if pending or blocked or child.accounted() + Decimal(request['reserve_usd']) > child.cap:
            raise ValueError('Gemini child cannot reserve first phase request; no phase claim')
    finally:
        child.close()
    return _original_run(plan_path_value, plan_sha, review_path, condition, phase, env_file)


runner.run = run

if __name__ == '__main__':
    runner.main()
