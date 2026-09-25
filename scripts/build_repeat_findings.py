#!/usr/bin/env python3
"""Build hash-bound, offline reports for completed Codex prompt repeat series."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'codex-gpt-6-luna-medium-batch10'
SOL_CONFIG = 'codex-gpt-6-sol-high-batch10'
SOL_MEDIUM_CONFIG = 'codex-gpt-6-sol-medium-batch10'
REPEAT_ROOT = Path('results/repeatability-v1')
PAIR_ROOT = Path('results/prompt-comparison-v1-2026-09-24/paired-reports')
SERIES = ((CONFIG, 'GPT-6 Luna · medium effort'), (SOL_CONFIG, 'GPT-6 Sol · high effort'), (SOL_MEDIUM_CONFIG, 'GPT-6 Sol · medium effort'))
LABELS = Path('data/pilot/proposed_labels.jsonl')
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
CONDITIONS = ('P0', 'P1', 'P2')
PASSES = ('original', 'repeat2', 'repeat3')
PINNED_SHA = {
    str(LABELS): '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464',
    str(REPEAT_ROOT / CONFIG / 'repeat2/manifest.json'): 'ac6b282c5527ea1a263fd26c474e09b9475d36c7666b6bbde122166e72aca1f3',
    str(REPEAT_ROOT / CONFIG / 'repeat3/manifest.json'): 'b29ff4b0de2712beaacd66680bf6efdcc3f4ad6293df176477d6b01759b74c45',
    str(REPEAT_ROOT / SOL_CONFIG / 'repeat2/manifest.json'): 'a8ea850980a39ebc723c09e31d11c7e5a85701f3bb248b1d39630d630be07a48',
    str(REPEAT_ROOT / SOL_CONFIG / 'repeat3/manifest.json'): '5572258506b20d3308e504399b4deea337fe1642325b37453d87076871152c1e',
    str(REPEAT_ROOT / SOL_MEDIUM_CONFIG / 'repeat2/manifest.json'): '2a2ea73fee8c393c44d8224f15a5d58ff5e29bae3bb05df53d058967e5b46cc3',
    str(REPEAT_ROOT / SOL_MEDIUM_CONFIG / 'repeat3/manifest.json'): 'b708bc3cbaba4cbde3210f3ce476dc6b6c315860ca666fc5c928279b9ff70b6c',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def binding(path, expected=None):
    resolved = (ROOT / path).resolve()
    resolved.relative_to(ROOT.resolve())
    digest = sha(resolved)
    if expected is not None and digest != expected:
        raise ValueError(f'Source SHA changed: {path}')
    return {'path': str(path), 'sha256': digest}


def completed_repeat(folder, repeat, condition, manifest_sha):
    """Read only the journal until a terminal completion signal is present."""
    journal = folder / 'development.journal.jsonl'
    if not (ROOT / journal).exists():
        return False
    try:
        events = rows(ROOT / journal)
    except (ValueError, OSError):
        return False
    if not events or events[-1].get('event') != 'phase_completed':
        return False
    if events[-1].get('request_count') != 6 or events[-1].get('record_count') != 60:
        raise ValueError(f'Invalid terminal counts: {journal}')
    if len(events) != 14 or [e['event'] for e in events] != ['phase_started', *['request_started', 'request_completed'] * 6, 'phase_completed']:
        raise ValueError(f'Invalid completed journal: {journal}')
    for index in range(6):
        started, finished = events[1 + index * 2:3 + index * 2]
        if started['batch_index'] != finished['batch_index'] or finished['status'] != 'ok' or started['manifest_sha256'] != manifest_sha:
            raise ValueError(f'Invalid completed request: {journal}')
    claim = json.loads((ROOT / folder / 'development.claim.json').read_text())
    if claim['manifest_sha256'] != manifest_sha or claim['repeat'] != repeat or claim['condition'] != condition:
        raise ValueError(f'Claim mismatch: {folder}')
    return True


def validate_evidence(records, attempts, ids, condition, repeat, manifest=None):
    if len(records) != 60 or len(attempts) != 6 or len({r['id'] for r in records}) != 60:
        raise ValueError(f'Incomplete/duplicate evidence: {repeat} {condition}')
    if [r['id'] for r in records] != ids:
        raise ValueError(f'Record order changed: {repeat} {condition}')
    for index, attempt in enumerate(attempts):
        members = ids[index * 10:(index + 1) * 10]
        if attempt['record_order'] != members or attempt['batch_size'] != 10:
            raise ValueError(f'Batch membership changed: {repeat} {condition}')
        if manifest is not None:
            planned = manifest['conditions'][condition]['development'][index]
            if attempt['manifest_sha256'] != manifest['_sha256'] or attempt['request_sha256'] != planned['request_sha256'] or attempt['schema_sha256'] != planned['schema_sha256']:
                raise ValueError(f'Request binding changed: {repeat} {condition}')
        for record in records[index * 10:(index + 1) * 10]:
            if record['request_sha256'] != attempt['request_sha256'] or record['status'] != attempt['status']:
                raise ValueError(f'Record/attempt disagreement: {repeat} {condition}')
            if manifest is not None and record['prediction'] != attempt['batch_predictions'].get(record['id']):
                raise ValueError(f'Prediction differs from completed attempt: {repeat} {condition}')
            if manifest is not None and (record['repeat'] != repeat or record['condition'] != condition or record['phase'] != 'development'):
                raise ValueError(f'Record identity changed: {repeat} {condition}')
    return {r['id']: r for r in records}


def outcome(record):
    prediction = record.get('prediction')
    if record.get('status') == 'ok' and isinstance(prediction, dict) and all(prediction.get(f) is not None for f in FIELDS):
        return 'valid'
    if record.get('status') == 'ok':
        return 'invalid_output'
    status = record.get('status')
    if status in ('invalid_output', 'refusal', 'timeout', 'service_error', 'isolation_violation', 'unknown_started', 'never_sent'):
        return status
    return 'other_error'


def score(records, labels, ids):
    counts = Counter(outcome(records[rid]) for rid in ids)
    by_field = {f: sum(outcome(records[rid]) == 'valid' and records[rid]['prediction'][f] == labels[rid][f] for rid in ids) for f in FIELDS}
    all_four = sum(outcome(records[rid]) == 'valid' and all(records[rid]['prediction'][f] == labels[rid][f] for f in FIELDS) for rid in ids)
    return {'denominator': 60, 'valid': counts['valid'], 'allFour': all_four, 'fields': by_field,
            'outcomes': {key: counts[key] for key in ('valid', 'invalid_output', 'refusal', 'timeout', 'service_error', 'isolation_violation', 'other_error', 'unknown_started', 'never_sent')},
            'invalidIds': [rid for rid in ids if outcome(records[rid]) != 'valid']}


def flip(a, b, ids):
    valid = [rid for rid in ids if outcome(a[rid]) == outcome(b[rid]) == 'valid']
    excluded = [rid for rid in ids if rid not in valid]
    result = {'denominator': len(valid), 'excludedIds': excluded}
    for field in (*FIELDS, 'fourFieldVector'):
        changed = [rid for rid in valid if (a[rid]['prediction'] if field == 'fourFieldVector' else a[rid]['prediction'][field]) != (b[rid]['prediction'] if field == 'fourFieldVector' else b[rid]['prediction'][field])]
        result[field] = {'changed': len(changed), 'rate': len(changed) / len(valid) if valid else None, 'caseIds': changed}
    return result


def usage(attempts):
    keys = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')
    token_totals = {key: sum(a['usage'][key] for a in attempts) if all(isinstance(a.get('usage'), dict) and isinstance(a['usage'].get(key), int) for a in attempts) else None for key in keys}
    elapsed = [a.get('elapsed_seconds') for a in attempts]
    return {'requestCount': len(attempts), 'requestSeconds': elapsed, 'requestSecondsTotal': sum(elapsed) if all(isinstance(x, (int, float)) for x in elapsed) else None,
            'tokens': token_totals, 'actualCostUsd': None, 'costNote': 'ChatGPT subscription; attributable request cost unavailable.'}


def build_series(config, display_name):
    base = REPEAT_ROOT / config
    pair_path = PAIR_ROOT / config / 'paired-manifest.json'
    sources = []
    labels_binding = binding(LABELS, PINNED_SHA[str(LABELS)]); sources.append(labels_binding)
    label_rows = rows(ROOT / LABELS)
    ids = [r['id'] for r in label_rows]
    if len(ids) != 60 or len(set(ids)) != 60 or any(r.get('review_version') != '0.2' for r in label_rows):
        raise ValueError('Expected 60 unique provisional v0.2 references')
    labels = {r['id']: r['proposed_labels'] for r in label_rows}
    pair_binding = binding(pair_path); sources.append(pair_binding)
    pair = json.loads((ROOT / pair_path).read_text())
    if pair['parent_baseline_id'] != config:
        raise ValueError(f'Historical paired configuration mismatch: {config}')
    data = {}; missing = []
    for pass_name in PASSES:
        data[pass_name] = {}
        manifest = None
        if pass_name != 'original':
            manifest_path = base / pass_name / 'manifest.json'
            manifest_binding = binding(manifest_path, PINNED_SHA[str(manifest_path)]); sources.append(manifest_binding)
            manifest = json.loads((ROOT / manifest_path).read_text()); manifest['_sha256'] = manifest_binding['sha256']
            if manifest['configuration_id'] != config or manifest['repeat'] != pass_name:
                raise ValueError('Manifest identity changed')
            if manifest['model'] != pair['controls']['requested_model'] or manifest['effort'] != pair['controls']['effort'] or manifest['batch_size'] != pair['controls']['configured_batch_size']:
                raise ValueError(f'Manifest controls differ from historical pair: {config}')
            for item in manifest['source_bindings']:
                binding(item['path'], item['sha256'])
        for condition in CONDITIONS:
            if pass_name == 'original':
                source = pair['conditions'][condition]
                record_binding = binding(source['predictions']['file'], source['predictions']['sha256'])
                attempt_binding = binding(source['request_evidence']['file'], source['request_evidence']['sha256'])
                journal_binding = None
            else:
                folder = base / pass_name / condition
                if not completed_repeat(folder, pass_name, condition, manifest['_sha256']):
                    missing.append({'pass': pass_name, 'condition': condition, 'status': 'incomplete_or_not_started'})
                    continue
                record_binding = binding(folder / 'development.records.jsonl')
                attempt_binding = binding(folder / 'development.attempts.jsonl')
                journal_binding = binding(folder / 'development.journal.jsonl')
                claim_binding = binding(folder / 'development.claim.json')
            records = rows(ROOT / record_binding['path']); attempts = rows(ROOT / attempt_binding['path'])
            indexed = validate_evidence(records, attempts, ids, condition, pass_name, manifest)
            entry = {'score': score(indexed, labels, ids), 'usage': usage(attempts), 'evidence': {'records': record_binding, 'attempts': attempt_binding}}
            if journal_binding:
                entry['evidence']['journal'] = journal_binding
                entry['evidence']['claim'] = claim_binding
            data[pass_name][condition] = entry
            sources.extend([record_binding, attempt_binding] + ([journal_binding, claim_binding] if journal_binding else []))
    pair_deltas = []
    for pass_name in PASSES:
        for target in ('P1', 'P2'):
            if 'P0' not in data[pass_name] or target not in data[pass_name]:
                continue
            baseline = data[pass_name]['P0']['score']; variant = data[pass_name][target]['score']
            pair_deltas.append({'pass': pass_name, 'from': 'P0', 'to': target, 'denominator': 60,
                                'allFour': variant['allFour'] - baseline['allFour'],
                                'fields': {field: variant['fields'][field] - baseline['fields'][field] for field in FIELDS}})
    paired_spread = {}
    for target in ('P1', 'P2'):
        entries = [d for d in pair_deltas if d['to'] == target]
        paired_spread[target] = {'completedPairs': len(entries), 'allFourValues': [d['allFour'] for d in entries],
                                 'allFourRange': [min(d['allFour'] for d in entries), max(d['allFour'] for d in entries)] if len(entries) == 3 else None,
                                 'fieldRanges': {f: [min(d['fields'][f] for d in entries), max(d['fields'][f] for d in entries)] if len(entries) == 3 else None for f in FIELDS}}
    flips = []
    for condition in CONDITIONS:
        for i, left in enumerate(PASSES):
            for right in PASSES[i + 1:]:
                if condition not in data[left] or condition not in data[right]: continue
                a = {r['id']: r for r in rows(ROOT / data[left][condition]['evidence']['records']['path'])}
                b = {r['id']: r for r in rows(ROOT / data[right][condition]['evidence']['records']['path'])}
                flips.append({'condition': condition, 'from': left, 'to': right, **flip(a, b, ids)})
    ranges = {}
    for condition in CONDITIONS:
        entries = [data[p][condition]['score'] for p in PASSES if condition in data[p]]
        def stats(values): return {'completedPasses': len(values), 'values': values, 'mean': sum(values)/len(values) if len(values) == 3 else None, 'range': [min(values), max(values)] if len(values) == 3 else None}
        ranges[condition] = {'allFour': stats([e['allFour'] for e in entries]), 'fields': {f: stats([e['fields'][f] for e in entries]) for f in FIELDS}}
    across = {}
    for condition in CONDITIONS:
        if any(condition not in data[p] for p in PASSES): continue
        triplet = [{r['id']: r for r in rows(ROOT / data[p][condition]['evidence']['records']['path'])} for p in PASSES]
        eligible = [rid for rid in ids if all(outcome(run[rid]) == 'valid' for run in triplet)]
        across[condition] = {'denominator': len(eligible), 'excludedIds': [rid for rid in ids if rid not in eligible],
                             'fields': {f: [rid for rid in eligible if len({run[rid]['prediction'][f] for run in triplet}) > 1] for f in FIELDS},
                             'fourFieldVector': [rid for rid in eligible if len({tuple(run[rid]['prediction'][f] for f in FIELDS) for run in triplet}) > 1]}
    return {'schema': 'repeat-findings-v1', 'configuration': config, 'displayName': display_name,
            'model': pair['controls']['requested_model'], 'effort': pair['controls']['effort'],
            'historicalControls': pair.get('historical_controls', pair['controls']),
            'repeatRuntimeAmendment': manifest['runtime_amendment'],
            'referenceVersion': '0.2', 'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items())) for field in FIELDS},
            'denominator': 60, 'completedConditions': sum(len(x) for x in data.values()), 'plannedConditions': 9, 'missingPasses': missing,
            'passes': data, 'threePassSummary': ranges, 'pairwiseFlips': flips, 'changesAcrossThreePasses': across,
            'withinPassPromptDeltas': pair_deltas, 'pairedDeltaSpread': paired_spread, 'sourceBindings': sources,
            'limitations': ['Same 60 synthetic records in every pass; observations are dependent.', 'Original CLI and repeat CLI differ by accepted patch amendment; equivalence is unproven.', 'Provider serving revision and effective seed are unavailable.', 'Batch timing is request timing; per-record shares are not independent latency.', 'Subscription request cost is unknown, not zero.']}


def build():
    reports = [build_series(config, display) for config, display in SERIES]
    # Keep the original Luna view at the top level for saved clients. All comparisons
    # in `series` have separate 60-record denominators and their own source bindings.
    for report in reports:
        insights = []
        for condition in CONDITIONS:
            summary = report['threePassSummary'][condition]['allFour']
            changes = report['changesAcrossThreePasses'].get(condition)
            if summary['range'] is not None and changes is not None:
                lo, hi = summary['range']
                insights.append(f"{condition} matched all four references on {lo} to {hi} of 60 comments per pass; {len(changes['fourFieldVector'])} comments changed at least one decision across the three passes.")
        for condition in ('P1', 'P2'):
            deltas = [x['allFour'] for x in report['withinPassPromptDeltas'] if x['to'] == condition]
            if len(deltas) == 3:
                direction = 'changed direction across passes' if min(deltas) < 0 < max(deltas) else 'did not improve agreement in every pass' if min(deltas) <= 0 else 'improved agreement in all three observed passes'
                insights.append(f"{condition} versus P0 {direction}: changes were {', '.join(f'{x:+d}' for x in deltas)} matches out of 60. Three passes do not establish a reliable future effect.")
        report['interpretation'] = insights
    return {**reports[0], 'series': reports, 'availableConfigurations': [r['configuration'] for r in reports]}


def markdown_series(report):
    lines = [f"## {report['displayName']}", '', f"Completed conditions: {report['completedConditions']}/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.", '',
             '| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for pass_name in PASSES:
        for condition in CONDITIONS:
            entry = report['passes'][pass_name].get(condition)
            if entry is None:
                lines.append(f'| {pass_name} | {condition} | missing | missing | missing | missing | missing | missing | missing | missing | missing |')
                continue
            s=entry['score']; u=entry['usage']; f=s['fields']; t=u['tokens']
            lines.append(f"| {pass_name} | {condition} | {s['valid']}/60 | {s['allFour']}/60 | {f['sentiment']}/60 | {f['follow_up_needed']}/60 | {f['serious_concern_reported']}/60 | {f['testimonial_potential']}/60 | {u['requestSecondsTotal']:.1f} | {t['input_tokens']} | {t['output_tokens']} |")
    lines.extend(['', 'Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):', ''])
    for d in report['withinPassPromptDeltas']:
        lines.append(f"- {d['pass']} {d['to']}: all four {d['allFour']:+d}; " + ', '.join(f'{f} {d["fields"][f]:+d}' for f in FIELDS) + '.')
    lines.extend(['', 'Three-pass scores (mean and range appear when all three passes are complete):', ''])
    for condition in CONDITIONS:
        summary = report['threePassSummary'][condition]
        for name, stats in [('all four', summary['allFour']), *((f, summary['fields'][f]) for f in FIELDS)]:
            values = ', '.join(str(x) for x in stats['values'])
            mean = f"{stats['mean']:.2f}" if stats['mean'] is not None else 'pending'
            spread = f"{stats['range'][0]} to {stats['range'][1]}" if stats['range'] is not None else 'pending'
            lines.append(f'- {condition} {name}: {values} of 60; mean {mean}; range {spread}.')
    lines.extend(['', 'Paired P1/P2 minus P0 all-four spread:', ''])
    for target, item in report['pairedDeltaSpread'].items():
        values = ', '.join(f'{x:+d}' for x in item['allFourValues'])
        spread = f"{item['allFourRange'][0]:+d} to {item['allFourRange'][1]:+d}" if item['allFourRange'] else 'pending'
        lines.append(f"- {target}: {values}; three-pair range {spread}.")
    lines.extend(['', 'Reference class counts (60 records):', ''])
    for field, counts in report['referenceClassCounts'].items():
        lines.append(f"- {field}: " + ', '.join(f'{label} {count}' for label, count in counts.items()))
    lines.extend(['', 'Completed pass comparisons, changed labels among records valid in both passes:', '',
                  '| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |',
                  '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |'])
    for row in report['pairwiseFlips']:
        cell = lambda key: f"{row[key]['changed']}/{row['denominator']}"
        lines.append(f"| {row['condition']} | {row['from']} to {row['to']} | {row['denominator']}/60 | {cell('fourFieldVector')} | {cell('sentiment')} | {cell('follow_up_needed')} | {cell('serious_concern_reported')} | {cell('testimonial_potential')} |")
    lines.extend(['', 'The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.', '', 'Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.', '', 'The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.', '', 'Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).'])
    return '\n'.join(lines) + '\n'


def markdown(report):
    intro = '# Prompt repeat findings\n\nEach configuration is a separate series on the same 60 development records. Scores and pass counts are reported within each configuration.\n\n'
    return intro + '\n'.join(markdown_series(series) + '\nObserved patterns:\n\n' + '\n\n'.join(series['interpretation']) + '\n' for series in report['series'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check outputs without writing')
    args = parser.parse_args()
    report = build()
    outputs = {ROOT / 'public-site/repeats.json': json.dumps(report, indent=2, ensure_ascii=False) + '\n', ROOT / 'docs/REPEAT_FINDINGS.md': markdown(report)}
    for path, value in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != value: raise ValueError(f'Stale report: {path}')
        else:
            path.write_text(value)
    print('; '.join(f"{r['configuration']}: {r['completedConditions']}/9 complete" for r in report['series']))


if __name__ == '__main__': main()
