#!/usr/bin/env python3
"""Build the public Liquid native Choice summary from listed closed phases."""
import argparse
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
import build_liquid_d1_native_full_findings as phase_report
import liquid_d1_full_execution_v1 as full

OUTPUT = ROOT / 'public-site/liquid-d1-native-full-findings.json'
# Deliberately explicit: a live or merely smoked phase is never auto-published.
CLOSED_STAGES = ('fresh1/P0', 'fresh1/P1', 'fresh1/P2',
                 'fresh2/P0', 'fresh2/P1', 'fresh2/P2',
                 'fresh3/P0', 'fresh3/P1', 'fresh3/P2')


def condition_summary(stages, condition):
    selected = [(stage, item) for stage, item in stages.items()
                if stage.endswith('/' + condition)]
    scores = [item['all_four_correct'] for _, item in selected]
    field_ranges = {key: {'min': min(item['fields'][key]['correct'] for _, item in selected),
                          'max': max(item['fields'][key]['correct'] for _, item in selected)}
                    for key in KEYS}
    flips = []
    if len(selected) >= 2:
        by_stage = {stage: {row['id']: row['prediction'] for row in item['records']}
                    for stage, item in selected}
        first_ids = [row['id'] for row in selected[0][1]['records']]
        for ident in first_ids:
            fields = [key for key in KEYS if len({by_stage[stage][ident][key]
                                                   for stage, _ in selected}) > 1]
            if fields:
                flips.append({'id': ident, 'fields': fields,
                              'choices_by_stage': {stage: {key: by_stage[stage][ident][key]
                                                           for key in fields}
                                                   for stage, _ in selected}})
    return {'closed_passes': [stage.split('/')[0] for stage, _ in selected],
            'closed_pass_count': len(selected),
            'all_four_correct_range': {'min': min(scores), 'max': max(scores),
                                       'denominator': 60},
            'fields_correct_ranges': field_ranges,
            'choice_flip_record_count': len(flips),
            'choice_flips': flips}


def paired_prompt_comparison(left, right, truth, left_stage, right_stage):
    """Compare only record IDs with valid public predictions in both phases."""
    def indexed(item):
        rows = item['records']
        by_id = {row['id']: row['prediction'] for row in rows}
        if len(by_id) != len(rows) or any(
                ident not in truth or set(prediction) != set(KEYS) or
                any(prediction[key] not in VALUES[key] for key in KEYS)
                for ident, prediction in by_id.items()):
            raise ValueError('Liquid paired public record differs')
        return by_id

    left_by_id, right_by_id = indexed(left), indexed(right)
    shared = sorted(left_by_id.keys() & right_by_id.keys())
    left_only = sorted(left_by_id.keys() - right_by_id.keys())
    right_only = sorted(right_by_id.keys() - left_by_id.keys())
    changed = []
    field_flips = {key: [] for key in KEYS}
    field_gains = {key: [] for key in KEYS}
    field_losses = {key: [] for key in KEYS}
    all_four_gains, all_four_losses = [], []
    field_left = {key: 0 for key in KEYS}
    field_right = {key: 0 for key in KEYS}
    all_four_left = all_four_right = 0
    for ident in shared:
        before, after, reference = left_by_id[ident], right_by_id[ident], truth[ident]
        flipped = [key for key in KEYS if before[key] != after[key]]
        if flipped:
            changed.append({'id': ident, 'fields': flipped,
                            'left_choices': {key: before[key] for key in flipped},
                            'right_choices': {key: after[key] for key in flipped}})
            for key in flipped:
                field_flips[key].append(ident)
        before_all = all(before[key] == reference[key] for key in KEYS)
        after_all = all(after[key] == reference[key] for key in KEYS)
        all_four_left += before_all
        all_four_right += after_all
        if not before_all and after_all:
            all_four_gains.append(ident)
        elif before_all and not after_all:
            all_four_losses.append(ident)
        for key in KEYS:
            before_correct = before[key] == reference[key]
            after_correct = after[key] == reference[key]
            field_left[key] += before_correct
            field_right[key] += after_correct
            if not before_correct and after_correct:
                field_gains[key].append(ident)
            elif before_correct and not after_correct:
                field_losses[key].append(ident)
    return {'left': left_stage, 'right': right_stage,
            'shared_valid': len(shared), 'left_only_ids': left_only,
            'right_only_ids': right_only,
            'changed_record_count': len(changed), 'changed_records': changed,
            'label_flips_by_field': {key: {'count': len(field_flips[key]),
                                           'ids': field_flips[key]} for key in KEYS},
            'all_four': {'left_correct': all_four_left, 'right_correct': all_four_right,
                         'gained_ids': all_four_gains, 'lost_ids': all_four_losses},
            'fields': {key: {'left_correct': field_left[key],
                             'right_correct': field_right[key],
                             'gained_ids': field_gains[key],
                             'lost_ids': field_losses[key]} for key in KEYS}}


def build(root=ROOT):
    root = Path(root).resolve()
    for module in (phase_report, full):
        path = root / 'scripts' / Path(module.__file__).name
        if full.sha(path) != full.sha(module.__file__):
            raise ValueError('Loaded Liquid report/controller source differs from selected root')
    stages = {}
    projected_bindings = []
    for stage in CLOSED_STAGES:
        phase_report.portable_check(stage=stage, root=root)
        path = root / 'results/liquid-d1-native-v1/full-v1' / stage / 'development.public.json'
        item = json.loads(path.read_text())
        if (item['configuration']['pass'] + '/' + item['configuration']['condition'] != stage or
                item['record_count'] != 60 or item['valid_outputs'] != 60 or
                item['intrinsic_invalid_count'] != 0 or
                item['unknown_upper_bound_usd'] != '0'):
            raise ValueError('Liquid closed public phase differs: ' + stage)
        stages[stage] = item
        projected_bindings.append({'path': str(path.relative_to(root)), 'sha256': full.sha(path)})
    phase_rows = {stage: {'all_four_correct': item['all_four_correct'],
                          'fields_correct': {key: item['fields'][key]['correct'] for key in KEYS},
                          'confusion_reference_by_choice': {
                              key: item['fields'][key]['confusion_reference_by_choice']
                              for key in KEYS},
                          'usage': {'input_tokens': sum(row['usage']['input_tokens']
                                                        for row in item['records']),
                                    'output_tokens': sum(row['usage']['output_tokens']
                                                         for row in item['records'])},
                          'provider_confidence_thresholds_by_field': {
                              key: item['fields'][key]['provider_confidence_thresholds']
                              for key in KEYS},
                          'known_actual_usd': item['known_actual_usd'],
                          'public_projection_sha256': projected_bindings[index]['sha256']}
                  for index, (stage, item) in enumerate(stages.items())}
    references = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    truth = {row['id']: row['proposed_labels'] for row in references}
    if len(truth) != len(references):
        raise ValueError('Liquid reference IDs differ')
    prompt_pairs = (('P0', 'P1'), ('P1', 'P2'), ('P0', 'P2'))
    paired = {f'{fresh}/{left}_vs_{fresh}/{right}': paired_prompt_comparison(
                  stages[f'{fresh}/{left}'], stages[f'{fresh}/{right}'], truth,
                  f'{fresh}/{left}', f'{fresh}/{right}')
              for fresh in ('fresh1', 'fresh2', 'fresh3')
              for left, right in prompt_pairs}
    needed = [Path('scripts/build_liquid_d1_native_full_findings.py'),
              Path('scripts/build_liquid_d1_native_full_aggregate.py'),
              Path('scripts/development_benchmark.py'),
              Path('scripts/jev_native_prompt_variants_v1.py'),
              Path('scripts/openrouter_benchmark.py'),
              Path('scripts/openrouter_budget_v2.py'),
              Path('results/liquid-d1-native-v1/full-v1/manifest.json'),
              Path('data/pilot/proposed_labels.jsonl'),
              Path('data/pilot/pairs.json'),
              Path('docs/CLEF_FINDINGS_2026-10-02.md')]
    needed += [Path(name) for name in full.SOURCES]
    for stage in CLOSED_STAGES:
        folder = Path('results/liquid-d1-native-v1/full-v1') / stage
        needed += [folder / name for name in
                   ('development.public.json', 'development.closure-audit.json',
                    'development.closure-ledger-snapshot.jsonl', 'development.score.json')]
    seen = set()
    source_bindings = []
    for relative in needed:
        if relative not in seen:
            seen.add(relative)
            source_bindings.append({'path': str(relative), 'sha256': full.sha(root / relative)})
    return {'kind': 'liquid-d1-native-full-findings-v1',
            'configuration': {'model': full.liquid.MODEL,
                              'returned_model': full.liquid.VERSION,
                              'provider': full.liquid.PROVIDER,
                              'interface': 'native four Choice questions'},
            'planned_development_stages': list(full.PHASES),
            'planned_stage_count': len(full.PHASES),
            'closed_development_stages': list(CLOSED_STAGES),
            'closed_stage_count': len(CLOSED_STAGES),
            'unpublished_development_stages': [stage for stage in full.PHASES
                                               if stage not in CLOSED_STAGES],
            'phases': phase_rows,
            'conditions': {condition: condition_summary(stages, condition)
                           for condition in ('P0', 'P1', 'P2')},
            'matched_prompt_comparisons': paired,
            'reference_status': 'Frozen provisional v0.2 development labels; owner-confirmed human checks on 2026-10-02, without independent adjudication.',
            'interpretation': 'Scores show agreement with the frozen synthetic development reference. Choice flips compare completed passes only. Provider confidence thresholds in each phase are descriptive, not calibrated.',
            'private_raw_limit': 'Portable checks bind each projection to a closure receipt and saved raw hash; they cannot reparse private response bytes in a clean checkout.',
            'sourceBindings': source_bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check'))
    args = parser.parse_args()
    expected = build()
    if args.action == 'write':
        with OUTPUT.open('x') as out:
            out.write(json.dumps(expected, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(OUTPUT.read_text()) != expected:
        raise ValueError('Liquid public aggregate differs from closed phases')
    print(full.sha(OUTPUT))


if __name__ == '__main__':
    main()
