#!/usr/bin/env python3
"""Analyze all nine Qwen27 slots while retaining interrupted-run boundaries.

Seven original phases were uninterrupted. Fresh3 P0 and P1 are separately
verified composites. This report is descriptive, not a clean matched series.
"""
import argparse
import json
from pathlib import Path

import build_hosted_v2_repeat_findings as hosted
import build_qwen27_second_continuation_findings as second
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'qwen27-v2-final-descriptive-nine-findings-v1'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')


def merged_bindings(*groups):
    merged = {}
    for group in groups:
        for item in group:
            path = item['path']
            if path in merged and merged[path] != item['sha256']:
                raise ValueError('Source binding conflicts across reports: ' + path)
            merged[path] = item['sha256']
    return [{'path': path, 'sha256': digest} for path, digest in sorted(merged.items())]


def composite_rows(root, mode):
    base = second.BASE / 'interruption-continuation-v1' / mode / 'public-evidence-v1'
    stage = second.SECOND / mode / 'fresh3'
    p0 = second.first.rows(root / base / 'prefix.positions.jsonl') + \
         second.first.rows(root / base / 'suffix.positions.jsonl')
    if mode == 'medium':
        p0 += second.first.rows(root / stage / 'P0/suffix/suffix.attempts.jsonl')
        p1 = second.first.rows(root / stage /
                               'P1/development/development.attempts.jsonl')
    else:
        p1 = second.first.rows(root / base / 'p1.positions.jsonl') + \
             second.first.rows(root / stage / 'P1/suffix/suffix.attempts.jsonl')
    return p0, p1


def across_three(rows, ids):
    indexed = [{row['id']: row for row in part} for part in rows]
    shared = [rid for rid in ids if all(part[rid].get('status') == 'ok' and
              valid(part[rid].get('prediction')) for part in indexed)]
    result = {'denominator': len(shared),
              'excludedIds': [rid for rid in ids if rid not in shared]}
    for field in (*KEYS, 'fourFieldVector'):
        changed = [rid for rid in shared if len({
            tuple(part[rid]['prediction'][key] for key in KEYS)
            if field == 'fourFieldVector' else part[rid]['prediction'][field]
            for part in indexed}) > 1]
        result[field] = {'changed': len(changed), 'caseIds': changed,
                         'rate': len(changed) / len(shared) if shared else None}
    return result


def report_series(root, name, study, execution, config, labels, ids,
                  second_report, bindings):
    original = hosted.build_series(root, name, study, execution, config,
                                   labels, ids, bindings)
    mode = name.rsplit('-', 1)[-1]
    new = second_report['series'][mode]
    missing = {(item['pass'], item['condition']) for item in original['missingPasses']}
    if (original['completedConditions'] != 7 or
            missing != {('fresh3', 'P0'), ('fresh3', 'P1')} or
            new['configurationId'] != config or
            new['cleanMatchedThreeEligible'] is not False):
        raise ValueError('Seven original phases and two composites do not match')
    p0, p1 = composite_rows(root, mode)
    maps = {}
    for fresh in PASSES:
        for condition in CONDITIONS:
            if (fresh, condition) in missing:
                continue
            folder = (root / second.BASE / config / fresh / condition /
                      'development.attempts.jsonl')
            maps[(fresh, condition)] = hosted.read_jsonl(folder)
            if hosted.score(maps[(fresh, condition)], labels, ids) != \
                    original['passes'][fresh][condition]['score']:
                raise ValueError('Original closed score differs from verified record map')
    for condition, rows in (('P0', p0), ('P1', p1)):
        if second.score(rows, labels, 1 if condition == 'P0' else 0) != \
                new['conditions'][condition]['score']:
            raise ValueError('Interrupted composite differs from verified score')
        maps[('fresh3', condition)] = rows
        original['passes']['fresh3'][condition] = {
            'status': 'completed_interrupted_composite',
            'score': new['conditions'][condition]['score'],
            'usage': new['conditions'][condition]['usage']}
    if len(maps) != 9:
        raise ValueError('Nine phase maps are not present')
    within_deltas, within_flips = [], []
    for fresh in PASSES:
        for condition in ('P1', 'P2'):
            before = original['passes'][fresh]['P0']['score']
            after = original['passes'][fresh][condition]['score']
            within_deltas.append({
                'pass': fresh, 'from': 'P0', 'to': condition, 'denominator': 60,
                'allFour': after['allFour'] - before['allFour'],
                'fields': {field: after['fields'][field] - before['fields'][field]
                           for field in KEYS}})
            within_flips.append({'pass': fresh, 'from': 'P0', 'to': condition,
                                 **hosted.flips(maps[(fresh, 'P0')],
                                                maps[(fresh, condition)], ids)})
    pairwise = [{'condition': condition, 'from': a, 'to': b,
                 **hosted.flips(maps[(a, condition)], maps[(b, condition)], ids)}
                for condition in CONDITIONS for index, a in enumerate(PASSES)
                for b in PASSES[index+1:]]
    summaries, across = {}, {}
    for condition in CONDITIONS:
        scores = [original['passes'][fresh][condition]['score'] for fresh in PASSES]
        summary = {'allFour': {'values': [s['allFour'] for s in scores],
                               'range': [min(s['allFour'] for s in scores),
                                         max(s['allFour'] for s in scores)]},
                   'fields': {field: {
                       'values': [s['fields'][field] for s in scores],
                       'range': [min(s['fields'][field] for s in scores),
                                 max(s['fields'][field] for s in scores)]}
                              for field in KEYS}}
        summaries[condition] = summary
        across[condition] = across_three([maps[(fresh, condition)]
                                          for fresh in PASSES], ids)
    return {'configuration': config, 'seriesId': config + '-descriptive-nine-v1',
            'displayName': 'Qwen 27B ' + mode + ' · interrupted nine-slot analysis',
            'method': 'descriptive-nine-with-interrupted-composites',
            'cleanMatchedThreeEligible': False, 'denominator': 60,
            'plannedConditions': 9, 'scoredConditions': 9,
            'originalUninterruptedConditions': 7,
            'interruptedCompositeSlots': ['fresh3/P0', 'fresh3/P1'],
            'originalP0FailedId': new['originalP0FailedId'],
            'originalP0UnknownCostUpperBoundUsd':
                new['originalP0UnknownCostUpperBoundUsd'],
            'passOrder': list(PASSES), 'conditionOrder': list(CONDITIONS),
            'passes': original['passes'], 'threePassSummary': summaries,
            'pairwiseFlips': pairwise, 'changesAcrossThreePasses': across,
            'withinPassPromptDeltas': within_deltas,
            'withinPassPromptFlips': within_flips}


def build(root=ROOT):
    root = Path(root).resolve(strict=True)
    source_bindings = []
    hosted.bind(root, Path('scripts') / Path(__file__).name, source_bindings,
                hosted.sha(__file__))
    hosted.bind(root, 'scripts/build_hosted_v2_repeat_findings.py',
                source_bindings, hosted.sha(hosted.__file__))
    labels_path = hosted.bind(root, hosted.LABELS, source_bindings,
                              hosted.LABEL_SHA256)
    labels_rows = hosted.read_jsonl(root / labels_path['path'])
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if ([row.get('id') for row in labels_rows] != ids or
            any(row.get('review_version') != '0.2' or
                not valid(row.get('proposed_labels')) for row in labels_rows)):
        raise ValueError('Provisional references differ')
    labels = {row['id']: row['proposed_labels'] for row in labels_rows}
    execution_manifest = json.loads((root / second.BASE /
                                     'execution-manifest.json').read_text())
    for filename, digest in execution_manifest['source_code_sha256'].items():
        hosted.bind(root, Path('scripts') / filename, source_bindings, digest)
    second_report = second.build(root)
    rows = [report_series(root, name, study, execution, config, labels, ids,
                          second_report, source_bindings)
            for name, study, execution, config in hosted.SPECS[1:]]
    bindings = merged_bindings(source_bindings, second_report['sourceBindings'])
    return {'schema': SCHEMA, 'method': 'descriptive-nine-with-interrupted-composites',
            'denominator': 60, 'cleanMatchedThreeEligible': False,
            'referenceStatus': 'AI-authored provisional; not independently human-adjudicated',
            'series': rows, 'sourceBindings': bindings,
            'limits': ['The same 60 fictional comments recur in each phase.',
                       'Two fresh3 conditions combine separate dispatches; neither is a clean matched pass.',
                       'The original P0 failed requests were not retried; each retains an unknown-charge upper bound.',
                       'Answer-change denominators include only comments with valid answers in every compared phase.',
                       'Client request time includes transport and service overhead.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(args.root), indent=2, sort_keys=True) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != content:
            raise ValueError('Qwen27 descriptive nine-slot report differs')
    elif args.output:
        args.output.write_text(content)
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
