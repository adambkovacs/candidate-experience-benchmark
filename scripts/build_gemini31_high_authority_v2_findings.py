#!/usr/bin/env python3
"""Add independently closed Gemini 3.1 high authority-v2 phases to the public feed."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import build_gemini_repeat_findings as report
import gemini31_high_authority_v2 as authority

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/gemini31-high-authority-v2')
CONFIG = 'gemini31-pro-preview-high-p0-openrouter-v3'
CONDITIONS = ('P0', 'P1', 'P2')
REPEATS = ('repeat2', 'repeat3')
REQUIRED_SOURCES = ('repeat_manifest', 'development_claim', 'root_review_receipt',
                    'smoke_inspection', 'development_journal', 'development_attempts',
                    'development_responses', 'development_records', 'proposed_labels',
                    'closure_controller')
REQUIRED_CHECKS = ('frozen_plan_reconstructed_from_bound_sources',
                   'claim_matches_saved_root_review_receipt',
                   'saved_root_review_and_budget_manifest_validated',
                   'exact_six_canonical_development_requests',
                   'exact_60_ordered_records',
                   'frozen_endpoint_and_strict_classifier_match_attempt_predictions',
                   'raw_base64_body_equals_attempt_raw_response',
                   'all_six_batches_completed',
                   'one_matching_reserve_and_settlement_per_attempt',
                   'reference_labels_not_read_during_inference')


def _file(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Gemini closure source escapes report root')
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def _closure(root, repeat, condition):
    relative = BASE / CONFIG / repeat / condition / 'closure.review.json'
    path = _file(root, relative)
    if not path.exists():
        return None
    receipt = json.loads(path.read_text())
    checks = receipt.get('checks')
    metrics = receipt.get('metrics')
    sources = receipt.get('source_hashes')
    if (receipt.get('schema') != 'gemini31-high-authority-v2-closure-review-v1' or
            receipt.get('verdict') != 'APPROVE' or
            (receipt.get('configuration_id'), receipt.get('repeat'),
             receipt.get('condition'), receipt.get('phase')) !=
            (CONFIG, repeat, condition, 'development') or
            not isinstance(checks, dict) or not set(REQUIRED_CHECKS) <= set(checks) or
            not all(v is True for v in checks.values()) or
            not (checks.get('authority_v3_hold_and_saved_root_review_gate_validated') is True or
                 checks.get('authority_v2_live_ledger_not_reread_due_to_concurrent_nonblocking_lock') is True) or
            not isinstance(metrics, dict) or metrics.get('requests') != 6 or
            metrics.get('records') != 60 or metrics.get('all_four_denominator') != 60 or
            not isinstance(sources, dict) or not set(REQUIRED_SOURCES) <= set(sources)):
        raise ValueError('Gemini authority closure receipt is not approved and complete')
    for name in REQUIRED_SOURCES:
        source = sources[name]
        if (not isinstance(source, dict) or not isinstance(source.get('path'), str) or
                not isinstance(source.get('sha256'), str) or
                report._sha(_file(root, source['path'])) != source['sha256']):
            raise ValueError('Gemini authority closure source differs: ' + name)
    return {'path': relative.as_posix(), 'sha256': report._sha(path)}, metrics


def build(root=ROOT):
    root = Path(root).resolve()
    ordinary = report.build(root, include_recovered_low=True)
    if ordinary.get('schema') != 'gemini-repeat-series-v1' or any(
            item.get('configuration') == CONFIG for item in ordinary['series']):
        raise ValueError('Gemini authority configuration duplicates a published series')
    closures = {}
    for repeat in REPEATS:
        for condition in CONDITIONS:
            found = _closure(root, repeat, condition)
            if repeat == 'repeat2' and found is None:
                raise ValueError('Gemini authority repeat2 closure is missing')
            if found is not None:
                closures[(repeat, condition)] = found

    original_terminal = report._terminal

    def admitted_terminal(report_root, relative):
        relative = Path(relative)
        if (relative.name in ('smoke.journal.jsonl', 'development.journal.jsonl') and
                relative.parts[:len(BASE.parts) + 1] == (*BASE.parts, CONFIG)):
            repeat, condition = relative.parts[len(BASE.parts) + 1:len(BASE.parts) + 3]
            if (repeat, condition) not in closures:
                return None
        return original_terminal(report_root, relative)

    def authority_controller(config):
        if config != CONFIG:
            raise ValueError('Unexpected Gemini authority configuration')
        return authority.runner

    with (patch.object(report, 'BASE', BASE),
          patch.object(report, '_controller', authority_controller),
          patch.object(report, '_terminal', admitted_terminal)):
        series = report.build_series(CONFIG, root)
    for (repeat, condition), (binding, metrics) in closures.items():
        phase = series['passes'][repeat].get(condition)
        if (not phase or phase.get('completionStatus') != 'complete' or
                phase['score']['allFour'] != metrics.get('all_four_matches') or
                phase['score']['valid'] != metrics.get('valid_records') or
                phase['score']['outcomes']['invalid_output'] != metrics.get('invalid_records') or
                phase['usage']['knownCostUsd'] != metrics.get('development_observed_cost_usd')):
            raise ValueError('Gemini authority closure metrics differ from report')
        series['sourceBindings'].append(binding)
    if series['completedConditions'] != 3 + len(closures):
        raise ValueError('Gemini authority closed-condition count differs')
    ordinary['series'].append(series)
    if len({item['configuration'] for item in ordinary['series']}) != len(ordinary['series']):
        raise ValueError('Gemini report duplicates a configuration')
    return ordinary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    value = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != value:
            raise ValueError('Stale Gemini authority public report: ' + str(args.output))
    else:
        args.output.write_text(value)
    print('Gemini authority public report verified' if args.check else 'Gemini authority public report written')


if __name__ == '__main__':
    main()
