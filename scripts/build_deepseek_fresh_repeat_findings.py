#!/usr/bin/env python3
"""Build an offline report from sealed DeepSeek Flash fresh-matched-three stages."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import affordable_hosted_repeat_execution as execution
import affordable_hosted_repeat_admission as admission
import resolve_provider_error_public_source as public_source
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-flash-off-fresh3-v1')
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABEL_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
SERIES = 'openrouter-paid-deepseek-v41-flash-off-fresh-matched3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file(root, relative):
    root = Path(root).resolve()
    if public_source.is_audited(relative):
        return public_source.resolve(root, relative)[0]
    path = (root / relative).resolve()
    path.relative_to(root)
    return path


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete JSONL: {path}')
    return [json.loads(line) for line in raw.splitlines()]


def bind(root, relative, bindings, expected=None):
    if public_source.is_audited(relative):
        _, value = public_source.resolve(root, relative, expected)
        if value not in bindings:
            bindings.append(value)
        return value
    actual = sha(file(root, relative))
    if expected is not None and actual != expected:
        raise ValueError(f'Source hash changed: {relative}')
    value = {'path': str(relative), 'sha256': actual}
    if value not in bindings:
        bindings.append(value)
    return value


def source_context(root):
    bindings = []
    manifest_path = BASE / 'manifest.json'
    bind(root, manifest_path, bindings)
    manifest = json.loads(file(root, manifest_path).read_text())
    plan_path = Path(manifest['admission_plan'])
    bind(root, plan_path, bindings, manifest['admission_plan_sha256'])
    plan = json.loads(file(root, plan_path).read_text())
    if (manifest.get('schema') != 'affordable-hosted-fresh3-execution-v1' or
            manifest.get('configuration_id') != admission.CONFIG or
            manifest.get('series') != 'fresh-matched3' or
            plan.get('schema') != 'affordable-hosted-repeat-admission-v1' or
            plan.get('historical_first_pass_eligible') is not False or
            any(manifest.get(k) != plan.get(k) for k in ('configuration_id', 'series', 'phases',
                                                         'requests_by_condition', 'budget', 'route', 'source_bindings')) or
            len(manifest['phases']) != 9 or plan.get('request_count') != 567 or
            plan.get('orders') != {k: list(v) for k, v in admission.ORDERS.items()}):
        raise ValueError('Frozen DeepSeek plan or manifest differs')
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    scheduled = [(repeat, condition) for repeat, order in admission.ORDERS.items() for condition in order]
    if any((phase.get('repeat'), phase.get('condition')) != scheduled[i] or
           phase.get('smoke_ids') != ids[:3] or phase.get('development_ids') != ids
           for i, phase in enumerate(manifest['phases'])):
        raise ValueError('Frozen nine-phase schedule differs')
    for condition in CONDITIONS:
        items = manifest['requests_by_condition'][condition]
        if [item['id'] for item in items] != ids:
            raise ValueError('Frozen request membership differs')
    route = manifest['route']
    if any(route.get(k) != v for k, v in {'model': admission.MODEL, 'provider': admission.PROVIDER,
            'provider_name': 'OpenInference', 'quantization': 'fp4', 'reasoning_effort': 'off',
            'temperature': 0, 'max_tokens': 4096, 'fallbacks': False}.items()):
        raise ValueError('Frozen DeepSeek route differs')
    # The shared master ledger is an admission-time snapshot, not a report input.
    for source in manifest['source_bindings']:
        if source['path'] not in execution.MUTABLE:
            bind(root, source['path'], bindings, source['sha256'])
    for source in manifest['code_bindings']:
        bind(root, source['path'], bindings, source['sha256'])
    bind(root, LABELS, bindings, LABEL_SHA)
    labels_rows = rows(file(root, LABELS))
    if ([r.get('id') for r in labels_rows] != ids or
            any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels')) for r in labels_rows)):
        raise ValueError('Provisional reference v0.2 differs')
    labels = {r['id']: r['proposed_labels'] for r in labels_rows}
    budget_path = BASE / 'budget.json'
    budget_binding = bind(root, budget_path, bindings)
    budget = json.loads(file(root, budget_path).read_text())
    partitions = budget.get('partitions', [])
    if len(partitions) != 1:
        raise ValueError('Expected one frozen child partition')
    partition = partitions[0]
    origin = Path(budget.get('master_ledger', '')).parent.parent
    child_relative = BASE / ('budget-' + partition['id'] + '.jsonl')
    if (not origin.is_absolute() or
            budget.get('version') != 'paid-partitions-v1' or
            any(partition.get(k) != v for k, v in {'model': admission.MODEL,
                'provider': admission.PROVIDER, 'reasoning': 'off',
                'cap_usd': str(admission.CAP)}.items()) or
            partition.get('child_ledger') != str(origin / child_relative) or
            budget.get('master_ledger') != str(origin / 'results/openrouter-paid-budget.jsonl')):
        raise ValueError('Frozen child partition differs')
    return manifest, labels, ids, partition, budget_binding, bindings


def closed(root, index, stage):
    path = file(root, BASE / f'phase-{index + 1:02d}-{stage}.journal.jsonl')
    if not path.exists():
        return False
    # An open journal may be concurrently appended. No partial-phase claims enter output.
    data = path.read_bytes()
    if not data.endswith(b'\n'):
        return False
    try:
        last = json.loads(data.splitlines()[-1])
    except (ValueError, IndexError):
        return False
    return last == {'event': 'stage_completed', 'count': 3 if stage == 'smoke' else 60}


def prefix_path(index):
    return BASE / f'phase-{index + 1:02d}-budget-prefix.jsonl'


def settlement_events(records):
    events = []
    for row in records:
        events.extend((
            {'event': 'reserve', 'attempt_id': row['attempt_id'],
             'record_id': row['id'], 'usd': row['reserved_cost_usd']},
            {'event': 'settle', 'attempt_id': row['attempt_id'],
             'usd': row['observed_cost_usd']}))
    return events


def settlement_proof(partition, attempts, snapshot, snapshot_relative, terminal_attempt=None):
    events = rows(snapshot)
    if not events or events[0] != {'event': 'budget', 'cap_usd': partition['cap_usd']}:
        raise ValueError('Child budget header differs')
    if terminal_attempt is not None and events[-1] != {
            'event': 'settle', 'attempt_id': terminal_attempt['attempt_id'],
            'usd': terminal_attempt['observed_cost_usd']}:
        raise ValueError('Budget prefix does not end at closed development stage')
    wanted = {row['attempt_id']: row for row in attempts}
    if len(wanted) != len(attempts):
        raise ValueError('Repeated attempt ID')
    matched = {attempt: [] for attempt in wanted}
    for event in events[1:]:
        attempt = event.get('attempt_id')
        if attempt in matched:
            matched[attempt].append(event)
    for attempt, row in wanted.items():
        reserve, settle = matched[attempt] if len(matched[attempt]) == 2 else (None, None)
        if (reserve != {'event': 'reserve', 'attempt_id': attempt, 'record_id': row['id'],
                        'usd': row['reserved_cost_usd']} or
                settle != {'event': 'settle', 'attempt_id': attempt,
                           'usd': row['observed_cost_usd']}):
            raise ValueError('Closed attempt lacks exact child-budget settlement')
    # The report binds the complete immutable prefix, not the live child ledger.
    selected = [event for event in events if event.get('attempt_id') in wanted]
    return {'path': str(snapshot_relative),
            'settledAttempts': len(attempts),
            'selectedEventsSha256': hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest()}


def stage(root, manifest, partition, budget_binding, index, name, bindings, snapshot):
    stem = BASE / f'phase-{index + 1:02d}-{name}'
    review_path = Path(str(stem) + '.root-review.json')
    review_binding = bind(root, review_path, bindings)
    review = json.loads(file(root, review_path).read_text())
    manifest_sha = sha(file(root, BASE / 'manifest.json'))
    expected = {'approved': True, 'manifest_sha256': manifest_sha,
                'budget_manifest_sha256': budget_binding['sha256'],
                'partition_id': partition['id'], 'phase_index': index,
                'stage': name, 'runner_sha256': sha(file(root, 'scripts/affordable_hosted_repeat_execution.py'))}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact stage review receipt differs')
    if name == 'development':
        smoke = BASE / f'phase-{index + 1:02d}-smoke'
        inspection = review.get('smoke_inspection') or {}
        if (inspection.get('approved') is not True or inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + k + '_sha256') != sha(file(root, Path(str(smoke) + '.' + k + '.jsonl')))
                    for k in ('records', 'journal', 'raw'))):
            raise ValueError('Development review lacks exact smoke inspection')
    with patch.object(execution, 'ROOT', Path(root).resolve()):
        if not execution.finished(manifest, file(root, BASE), index, name,
                                  manifest_sha, budget_binding['sha256'], partition['id']):
            raise ValueError(f'Closed {name} stage fails strict runner verification')
    paths = {part: Path(str(stem) + suffix) for part, suffix in
             (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
              ('raw', '.raw.jsonl'), ('records', '.records.jsonl'))}
    for path in paths.values():
        bind(root, path, bindings)
    evidence = {part: {'path': str(path), 'sha256': sha(file(root, path))}
                for part, path in paths.items()}
    evidence['review'] = review_binding
    records = rows(file(root, paths['records']))
    proof = settlement_proof(partition, records, snapshot, prefix_path(index),
                             records[-1] if name == 'development' else None)
    return records, evidence, proof


def score(records, labels, ids):
    indexed = {row['id']: row for row in records}
    fields = {field: sum(indexed[rid]['prediction'][field] == labels[rid][field] for rid in ids)
              for field in KEYS}
    confusion = {field: {} for field in KEYS}
    classes = {field: Counter() for field in KEYS}
    for rid in ids:
        for field in KEYS:
            truth, predicted = labels[rid][field], indexed[rid]['prediction'][field]
            confusion[field].setdefault(truth, Counter())[predicted] += 1
            classes[field][predicted] += 1
    return {'denominator': len(ids), 'valid': len(ids),
            'allFour': sum(all(indexed[rid]['prediction'][f] == labels[rid][f] for f in KEYS) for rid in ids),
            'fields': fields, 'outcomes': {'valid': len(ids)}, 'invalidIds': [],
            'confusionCounts': {f: {truth: dict(counts) for truth, counts in confusion[f].items()} for f in KEYS},
            'predictedClassCounts': {f: dict(classes[f]) for f in KEYS}}


def usage(records):
    durations = [row['client_http_duration_seconds'] for row in records]
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in durations):
        raise ValueError('Invalid client HTTP duration')
    tokens = {key: (sum(row['usage'][key] for row in records)
                    if all(type(row.get('usage', {}).get(key)) is int for row in records) else None)
              for key in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    costs = [Decimal(row['observed_cost_usd']) for row in records]
    return {'requestCount': len(records), 'requestSeconds': durations,
            'requestSecondsTotal': sum(durations), 'timingKind': 'client_http_duration_not_provider_inference',
            'tokens': tokens, 'knownCostUsd': str(sum(costs, Decimal(0))),
            'actualCostUsd': str(sum(costs, Decimal(0))), 'unknownCostCount': 0,
            'costNote': 'USD amounts are observed provider usage charges; missing usage fields remain null.'}


def flip(a, b, ids):
    indexed_a, indexed_b = ({row['id']: row for row in part} for part in (a, b))
    result = {'denominator': len(ids), 'excludedIds': []}
    for field in (*KEYS, 'fourFieldVector'):
        changed = [rid for rid in ids if (indexed_a[rid]['prediction'] if field == 'fourFieldVector' else indexed_a[rid]['prediction'][field]) !=
                   (indexed_b[rid]['prediction'] if field == 'fourFieldVector' else indexed_b[rid]['prediction'][field])]
        result[field] = {'changed': len(changed), 'caseIds': changed,
                         'rate': len(changed) / len(ids)}
    return result


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / 3 if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build(root=ROOT):
    root = Path(root).resolve()
    manifest, labels, ids, partition, budget_binding, bindings = source_context(root)
    data = {fresh: {} for fresh in PASSES}
    maps, missing = {}, []
    expected_budget = [{'event': 'budget', 'cap_usd': partition['cap_usd']}]
    for index, phase in enumerate(manifest['phases']):
        fresh, condition = phase['repeat'], phase['condition']
        if not closed(root, index, 'development'):
            missing.append({'pass': fresh, 'condition': condition, 'status': 'not_completed'})
            continue
        if not closed(root, index, 'smoke'):
            raise ValueError('Development closed without completed smoke')
        snapshot = file(root, prefix_path(index))
        snapshot_binding = bind(root, prefix_path(index), bindings)
        smoke, smoke_evidence, smoke_budget = stage(root, manifest, partition, budget_binding, index, 'smoke', bindings, snapshot)
        development, evidence, budget = stage(root, manifest, partition, budget_binding, index, 'development', bindings, snapshot)
        expected_budget.extend(settlement_events(smoke))
        expected_budget.extend(settlement_events(development))
        if rows(snapshot) != expected_budget:
            raise ValueError('Budget prefix has missing, extra, or reordered events')
        maps[(fresh, condition)] = development
        data[fresh][condition] = {'status': 'completed', 'score': score(development, labels, ids),
                                  'usage': usage(development),
                                  'servedRoute': {'requestedModel': admission.MODEL, 'providerTag': admission.PROVIDER,
                                                  'returnedModels': dict(Counter(row['returned_model'] for row in development)),
                                                  'returnedProviders': dict(Counter(row['returned_provider'] for row in development)),
                                                  'providerEndpoint': manifest['route']},
                                  'evidence': {**evidence, 'smoke': smoke_evidence,
                                               'budgetPrefix': snapshot_binding,
                                               'budgetSettlement': budget, 'smokeBudgetSettlement': smoke_budget}}
    deltas, prompt_flips = [], []
    for fresh in PASSES:
        if 'P0' not in data[fresh]:
            continue
        for condition in ('P1', 'P2'):
            if condition not in data[fresh]:
                continue
            baseline, variant = data[fresh]['P0']['score'], data[fresh][condition]['score']
            deltas.append({'pass': fresh, 'from': 'P0', 'to': condition, 'denominator': len(ids),
                           'allFour': variant['allFour'] - baseline['allFour'],
                           'fields': {f: variant['fields'][f] - baseline['fields'][f] for f in KEYS}})
            prompt_flips.append({'pass': fresh, 'from': 'P0', 'to': condition,
                                 **flip(maps[(fresh, 'P0')], maps[(fresh, condition)], ids)})
    pairwise = [{'condition': condition, 'from': a, 'to': b,
                 **flip(maps[(a, condition)], maps[(b, condition)], ids)}
                for condition in CONDITIONS for i, a in enumerate(PASSES) for b in PASSES[i+1:]
                if (a, condition) in maps and (b, condition) in maps]
    ranges = {condition: {'allFour': stats([data[f][condition]['score']['allFour'] for f in PASSES if condition in data[f]]),
                          'fields': {field: stats([data[f][condition]['score']['fields'][field]
                                                   for f in PASSES if condition in data[f]]) for field in KEYS}}
              for condition in CONDITIONS}
    across = {}
    for condition in CONDITIONS:
        if not all((fresh, condition) in maps for fresh in PASSES):
            continue
        indexed = [{row['id']: row['prediction'] for row in maps[(fresh, condition)]} for fresh in PASSES]
        across[condition] = {'denominator': len(ids), 'excludedIds': [],
                             'fields': {field: [rid for rid in ids if len({part[rid][field] for part in indexed}) > 1]
                                        for field in KEYS},
                             'fourFieldVector': [rid for rid in ids if len({tuple(part[rid][f] for f in KEYS) for part in indexed}) > 1]}
    spread = {}
    for condition in ('P1', 'P2'):
        matched = [item for item in deltas if item['to'] == condition]
        spread[condition] = {'completedPairs': len(matched), 'allFourValues': [x['allFour'] for x in matched],
                             'allFourRange': [min(x['allFour'] for x in matched), max(x['allFour'] for x in matched)] if len(matched) == 3 else None,
                             'fieldRanges': {f: [min(x['fields'][f] for x in matched), max(x['fields'][f] for x in matched)] if len(matched) == 3 else None for f in KEYS}}
    series = {'schema': 'deepseek-fresh-repeat-findings-v1', 'configuration': admission.CONFIG,
              'seriesId': SERIES, 'displayName': 'DeepSeek V4.1 Flash · OpenInference fp4 · reasoning off · fresh matched three',
              'method': 'fresh-matched-three', 'model': admission.MODEL, 'effort': 'off',
              'provider': admission.PROVIDER, 'route': manifest['route'], 'servedModel': None,
              'servedModelNote': 'Per-request returned model and provider are saved in sealed records.',
              'conditionOrder': list(CONDITIONS), 'passOrder': list(PASSES), 'denominator': len(ids),
              'plannedConditions': 9, 'completedConditions': len(maps), 'missingPasses': missing,
              'passes': data, 'referenceVersion': '0.2',
              'referenceStatus': 'AI-reviewed provisional; not independent adjudication',
              'referenceClassCounts': {f: dict(sorted(Counter(labels[rid][f] for rid in ids).items())) for f in KEYS},
              'threePassSummary': ranges, 'pairwiseFlips': pairwise,
              'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
              'withinPassPromptFlips': prompt_flips, 'pairedDeltaSpread': spread,
              'historicalPassUsed': False,
              'limitations': ['The same 60 synthetic development records recur in every pass.',
                              'Provisional v0.2 references are not independent adjudication.',
                              'Client HTTP duration includes transport and is not provider inference time.',
                              'Serving revision and effective seed are unavailable.']}
    return {'schema': 'deepseek-fresh-repeat-findings-v1', 'series': [series],
            'availableConfigurations': [admission.CONFIG], 'sourceBindings': bindings}


def capture_prefix(root, index):
    """Copy a verified, closed ledger prefix once; never publish the live ledger."""
    root = Path(root).resolve()
    manifest, _, _, partition, budget_binding, bindings = source_context(root)
    if not 0 <= index < len(manifest['phases']):
        raise ValueError('Phase index outside frozen schedule')
    for prior in range(index + 1):
        if not closed(root, prior, 'smoke') or not closed(root, prior, 'development'):
            raise ValueError('Cannot snapshot an open phase or skip a predecessor')
    target = file(root, prefix_path(index))
    final_records = rows(file(root, BASE / f'phase-{index + 1:02d}-development.records.jsonl'))
    final_attempt = final_records[-1]['attempt_id']
    live = file(root, BASE / ('budget-' + partition['id'] + '.jsonl'))
    complete = live.read_bytes().splitlines(keepends=True)
    prefix = []
    found = False
    for line in complete:
        if not line.endswith(b'\n'):
            break
        prefix.append(line)
        event = json.loads(line)
        if event.get('event') == 'settle' and event.get('attempt_id') == final_attempt:
            found = True
            break
    if not found:
        raise ValueError('Closed development stage lacks final settlement')
    content = b''.join(prefix)
    if index:
        previous = file(root, prefix_path(index - 1)).read_bytes()
        if not content.startswith(previous):
            raise ValueError('Budget prefix does not extend previous phase')
    with tempfile.TemporaryDirectory() as tempdir:
        candidate = Path(tempdir) / 'candidate.jsonl'
        candidate.write_bytes(content)
        expected = [{'event': 'budget', 'cap_usd': partition['cap_usd']}]
        for phase in range(index + 1):
            snapshot = file(root, prefix_path(phase)) if phase < index else candidate
            for name in ('smoke', 'development'):
                records, _, _ = stage(root, manifest, partition, budget_binding,
                                      phase, name, bindings, snapshot)
                expected.extend(settlement_events(records))
        if rows(candidate) != expected:
            raise ValueError('Budget prefix has missing, extra, or reordered events')
    if target.exists():
        if target.read_bytes() != content:
            raise FileExistsError('Immutable budget prefix differs: ' + str(target))
        return target
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.budget-prefix-', delete=False) as out:
        temporary = Path(out.name)
        out.write(content)
        out.flush()
        os.fsync(out.fileno())
    try:
        os.link(temporary, target)
    finally:
        temporary.unlink()
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--capture-prefix-through-phase', type=int,
                        help='Copy the closed child-budget prefix through phase 1-9')
    args = parser.parse_args(argv)
    if args.capture_prefix_through_phase is not None:
        if args.output or args.check:
            parser.error('Prefix capture cannot be combined with report output or check')
        capture_prefix(ROOT, args.capture_prefix_through_phase - 1)
        return
    if args.output is None:
        parser.error('--output is required for a report')
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale DeepSeek fresh report: {args.output}')
    else:
        args.output.write_text(content)


if __name__ == '__main__':
    main()
