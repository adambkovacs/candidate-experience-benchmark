#!/usr/bin/env python3
"""Additive Luna P0 full gate over the preserved DEV001 + exact-two smoke evidence.

The frozen common full runner remains unchanged. This wrapper only substitutes
an independently reviewed composite smoke inspection for Luna fresh1/P0.
"""

import argparse
import json
from pathlib import Path

from development_benchmark import ROOT
import clef_openrouter_full_v1 as common
import clef_openrouter_luna_smoke_v2 as luna
import openrouter_decision_smoke as native


BASE = Path('results/clef-openrouter-v1/luna-full-v2')
PLAN = BASE / 'plan.json'
REVIEW = BASE / 'root-review.json'
KEY = 'luna-decisions'
STAGE = 'fresh1/P0'


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def build(root=ROOT):
    root = Path(root)
    _, common_sha = common.verify(root)
    _, luna_sha = luna.verify(root)
    return {'schema': 'clef-openrouter-luna-full-composite-gate-v2',
            'status': 'prepared_not_admitted', 'inference_performed': False,
            'allocation_performed': False, 'reference_labels_sent': False,
            'key': KEY, 'stage': STAGE, 'phase': 'development',
            'common_full_plan_sha256': common_sha,
            'luna_exact_two_plan_sha256': luna_sha,
            'wrapper_sha256': sha_path(root / 'scripts/clef_openrouter_luna_full_v2.py'),
            'gate': 'Independent dated-model validation of original DEV001 raw plus valid exact DEV002–003 suffix; original invalid_native_response remains preserved; root inspection binds composite evidence.',
            'execution': 'Frozen common full runner with this source-bound inspection gate; no smoke replay.'}


def verify(root=ROOT):
    value = build(root)
    if json.loads((Path(root) / PLAN).read_text()) != value:
        raise ValueError('Luna composite full gate differs from bound sources')
    return value, native.sha(native.canonical(value))


def verify_composite_review(root=ROOT):
    root = Path(root)
    plan, plan_sha = verify(root)
    projection, projection_sha = luna.composite_inspection(root)
    if ([row['id'] for row in projection['rows']] != ['DEV-001', 'DEV-002', 'DEV-003'] or
            projection.get('original_dev001_status_preserved') != 'invalid_native_response' or
            projection.get('dated_model') != luna.DATED_MODEL):
        raise ValueError('Luna composite does not preserve exact three-response lineage')
    receipt = json.loads((root / REVIEW).read_text())
    expected = {'kind': 'clef-openrouter-luna-full-composite-root-review-v2',
                'approved': True, 'wrapper_plan_sha256': plan_sha,
                'wrapper_plan_file_sha256': sha_path(root / PLAN),
                'common_full_plan_sha256': plan['common_full_plan_sha256'],
                'luna_exact_two_plan_sha256': plan['luna_exact_two_plan_sha256'],
                'composite_inspection_sha256': projection_sha,
                'original_dev001_status_preserved': 'invalid_native_response',
                'valid_ids': ['DEV-001', 'DEV-002', 'DEV-003']}
    if (any(receipt.get(key) != value for key, value in expected.items()) or
            not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip()):
        raise ValueError('Root composite inspection approval missing or changed')
    return sha_path(root / REVIEW)


def run(budget_path, *, root=ROOT, **kwargs):
    root = Path(root)
    verify_composite_review(root)
    original = common.verify_smoke_inspection
    def composite_gate(inner_root, key, stage, route_sha, full_sha):
        if key != KEY or stage != STAGE:
            return original(inner_root, key, stage, route_sha, full_sha)
        value, _ = verify(inner_root)
        if value['common_full_plan_sha256'] != full_sha:
            raise ValueError('Frozen full-plan identity changed')
        return verify_composite_review(inner_root)
    common.verify_smoke_inspection = composite_gate
    try:
        common.run(KEY, STAGE, budget_path, phase='development', root=root, **kwargs)
    finally:
        common.verify_smoke_inspection = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check', 'run'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--budget', type=Path)
    args = parser.parse_args()
    if args.action == 'run':
        if not args.budget:
            parser.error('run requires --budget')
        run(args.budget, root=args.root)
        return
    value = build(args.root)
    target = args.root / PLAN
    if args.action == 'write':
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(target.read_text()) != value:
        raise SystemExit('Luna composite full plan changed')
    print(native.sha(native.canonical(value)))


if __name__ == '__main__':
    main()
