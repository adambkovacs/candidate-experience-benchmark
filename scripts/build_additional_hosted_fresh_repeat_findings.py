#!/usr/bin/env python3
"""Offline findings from closed Qwen off and DeepSeek low v2 fresh-series evidence."""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import build_deepseek_fresh_repeat_findings as common
import qwen36_off_fresh_repeat_admission as qwen_admission
import qwen36_off_fresh_repeat_execution_v2 as qwen_execution
import deepseek_low_fresh_repeat_admission as low_admission
import deepseek_low_fresh_repeat_execution_v2 as low_execution
import deepseek_low_price_successor_v1 as low_price_successor
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
LABELS = common.LABELS
LABEL_SHA = common.LABEL_SHA
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')


@dataclass(frozen=True)
class Spec:
    base: Path
    admission: object
    execution: object
    series_id: str
    display_name: str
    effort: str
    provider_name: str
    quantization: str
    continue_on_invalid: bool


SPECS = (
    Spec(Path('results/repeatability-v1/qwen36-off-fresh3-v2'), qwen_admission,
         qwen_execution, 'openrouter-paid-qwen36-35b-a3b-off-fresh-matched3-v2',
         'Qwen3.6 35B A3B · AkashML fp8 · reasoning off · fresh matched three',
         'off', 'AkashML', 'fp8', False),
    Spec(Path('results/repeatability-v1/deepseek-low-fresh3-v2'), low_admission,
         low_execution, 'openrouter-paid-deepseek-v41-flash-low-fresh-matched3-v2',
         'DeepSeek V4.1 Flash · OpenInference fp4 · reasoning low · fresh matched three',
         'low', 'OpenInference', 'fp4', True),
)


def path(root, relative):
    return common.file(root, relative)


def bind(root, relative, bindings, expected=None):
    return common.bind(root, relative, bindings, expected)


def read_rows(path_value):
    return common.rows(path_value)


def sha(path_value):
    return common.sha(path_value)


def phase_prefix(spec, index):
    return spec.base / f'phase-{index + 1:02d}-budget-prefix.jsonl'


def closed(root, spec, index, stage):
    journal = path(root, spec.base / f'phase-{index + 1:02d}-{stage}.journal.jsonl')
    if not journal.exists():
        return False
    data = journal.read_bytes()
    if not data.endswith(b'\n'):
        return False
    try:
        return json.loads(data.splitlines()[-1]) == {
            'event': 'stage_completed', 'count': 3 if stage == 'smoke' else 60}
    except (ValueError, IndexError):
        return False


def source_context(root, spec):
    bindings = []
    manifest_path = spec.base / 'manifest.json'
    bind(root, manifest_path, bindings)
    manifest = json.loads(path(root, manifest_path).read_text())
    plan_path = Path(manifest['admission_plan'])
    bind(root, plan_path, bindings, manifest['admission_plan_sha256'])
    plan = json.loads(path(root, plan_path).read_text())
    admission = spec.admission
    if (manifest.get('schema') != 'affordable-hosted-fresh3-execution-v2' or
            manifest.get('configuration_id') != admission.CONFIG or
            manifest.get('series') != 'fresh-matched3' or
            plan.get('schema') != 'affordable-hosted-repeat-admission-v1' or
            plan.get('historical_first_pass_eligible') is not False or
            any(manifest.get(key) != plan.get(key) for key in
                ('configuration_id', 'series', 'phases', 'requests_by_condition',
                 'budget', 'route', 'source_bindings')) or
            len(manifest.get('phases', [])) != 9 or plan.get('request_count') != 567 or
            plan.get('orders') != {key: list(value) for key, value in admission.ORDERS.items()}):
        raise ValueError('Frozen v2 plan or manifest differs')
    ids = [f'DEV-{number:03d}' for number in range(1, 61)]
    schedule = [(fresh, condition) for fresh, order in admission.ORDERS.items()
                for condition in order]
    if any((phase.get('repeat'), phase.get('condition')) != schedule[index] or
           phase.get('smoke_ids') != ids[:3] or phase.get('development_ids') != ids
           for index, phase in enumerate(manifest['phases'])):
        raise ValueError('Frozen nine-phase schedule differs')
    for condition in CONDITIONS:
        if [item.get('id') for item in manifest['requests_by_condition'][condition]] != ids:
            raise ValueError('Frozen request membership differs')
    route = manifest['route']
    expected_route = {'model': admission.MODEL, 'provider': admission.PROVIDER,
                      'provider_name': spec.provider_name, 'quantization': spec.quantization,
                      'reasoning_effort': spec.effort, 'temperature': 0,
                      'max_tokens': 4096, 'continue_on_invalid_output': spec.continue_on_invalid,
                      'fallbacks': False}
    if any(route.get(key) != value for key, value in expected_route.items()):
        raise ValueError('Frozen route differs')
    for source in manifest['source_bindings']:
        if source['path'] not in spec.execution.MUTABLE:
            bind(root, source['path'], bindings, source['sha256'])
    for source in manifest['code_bindings']:
        bind(root, source['path'], bindings, source['sha256'])
    own_code = 'scripts/' + Path(spec.execution.__file__).name
    if not any(source['path'] == own_code for source in manifest['code_bindings']):
        raise ValueError('v2 runner code binding absent')
    bind(root, LABELS, bindings, LABEL_SHA)
    label_rows = read_rows(path(root, LABELS))
    if ([row.get('id') for row in label_rows] != ids or
            any(row.get('review_version') != '0.2' or
                not valid(row.get('proposed_labels')) for row in label_rows)):
        raise ValueError('Provisional reference v0.2 differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    budget_path = spec.base / 'budget.json'
    budget_binding = bind(root, budget_path, bindings)
    budget = json.loads(path(root, budget_path).read_text())
    origin = Path(budget.get('master_ledger', '')).parent.parent
    matches = [part for part in budget.get('partitions', []) if
               (part.get('model'), part.get('provider'), part.get('reasoning')) ==
               (admission.MODEL, admission.PROVIDER, spec.effort)]
    if len(matches) != 1:
        raise ValueError('Expected one exact child partition')
    partition = matches[0]
    child_relative = spec.base / ('budget-' + partition['id'] + '.jsonl')
    from openrouter_paid_benchmark import number
    if (not origin.is_absolute() or budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(origin / 'results/openrouter-paid-budget.jsonl') or
            partition.get('child_ledger') != str(origin / child_relative) or
            not admission.RESERVE <= number(partition['cap_usd']) <= admission.CAP):
        raise ValueError('Frozen child partition differs')
    return manifest, labels, ids, partition, budget_binding, bindings


def price_amendment(root, spec, manifest_sha, index, name, review_path, records, bindings):
    """Require the versioned price receipt when a closed stage used lower metadata."""
    if spec.admission is not low_admission:
        return None
    prices = {row['provider_endpoint']['pricing']['prompt'] for row in records}
    if prices == {low_price_successor.OLD_PROMPT_PRICE}:
        return None
    if prices != {low_price_successor.NEW_PROMPT_PRICE}:
        raise ValueError('Closed DeepSeek stage has unreviewed or mixed prompt prices')
    stem = spec.base / f'phase-{index + 1:02d}-{name}'
    supplement = Path(str(stem) + '.price-amendment.root-review.json')
    controller = Path('scripts/deepseek_low_price_successor_v1.py')
    tests = Path('tests/test_deepseek_low_price_successor_v1.py')
    audit = spec.base / 'lower-price-endpoint-audit-v1.json'
    for source in (controller, tests, audit):
        if not path(root, source).is_file():
            raise ValueError('Amended stage lacks bound successor source or route audit')
    if not path(root, supplement).is_file():
        raise ValueError('Amended stage lacks supplemental root review')
    audited_endpoint = json.loads(path(root, audit).read_text())['selected_endpoint']
    critical = ('tag', 'provider_name', 'quantization', 'model_id',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')
    if any(any(row['provider_endpoint'].get(key) != audited_endpoint.get(key)
               for key in critical) for row in records):
        raise ValueError('Amended stage endpoint differs from reviewed route controls')
    with patch.object(low_price_successor, 'ROOT', Path(root).resolve()), \
         patch.object(low_price_successor, 'BASE', path(root, spec.base)), \
         patch.object(low_price_successor, 'ROUTE_AUDIT', path(root, audit)), \
         patch.object(low_price_successor, '__file__', str(path(root, controller))), \
         patch.object(low_execution, 'ROOT', Path(root).resolve()), \
         patch.object(low_execution, '__file__', str(path(root, 'scripts/deepseek_low_fresh_repeat_execution_v2.py'))):
        low_price_successor.verify_amendment(
            index, name, manifest_sha, path(root, review_path), path(root, supplement))
    evidence = {'amendmentReview': bind(root, supplement, bindings),
                'successorController': bind(root, controller, bindings),
                'successorTests': bind(root, tests, bindings),
                'routeAudit': bind(root, audit, bindings)}
    return {'historicalPromptPriceUsdPerToken': low_price_successor.OLD_PROMPT_PRICE,
            'observedPromptPriceUsdPerToken': low_price_successor.NEW_PROMPT_PRICE,
            'evidence': evidence}


def stage(root, spec, manifest, partition, budget_binding, index, name, bindings, snapshot):
    stem = spec.base / f'phase-{index + 1:02d}-{name}'
    review_path = Path(str(stem) + '.root-review.json')
    review_binding = bind(root, review_path, bindings)
    review = json.loads(path(root, review_path).read_text())
    manifest_sha = sha(path(root, spec.base / 'manifest.json'))
    expected = {'approved': True, 'manifest_sha256': manifest_sha,
                'budget_manifest_sha256': budget_binding['sha256'],
                'partition_id': partition['id'], 'phase_index': index,
                'stage': name, 'runner_sha256': sha(path(root, 'scripts/' +
                                                        Path(spec.execution.__file__).name))}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact stage review receipt differs')
    if name == 'development':
        smoke = spec.base / f'phase-{index + 1:02d}-smoke'
        inspection = review.get('smoke_inspection') or {}
        if (inspection.get('approved') is not True or inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + key + '_sha256') !=
                    sha(path(root, Path(str(smoke) + '.' + key + '.jsonl')))
                    for key in ('records', 'journal', 'raw'))):
            raise ValueError('Development review lacks exact smoke inspection')
    with patch.object(spec.execution, 'ROOT', Path(root).resolve()):
        if not spec.execution.finished(manifest, path(root, spec.base), index, name,
                                       manifest_sha, budget_binding['sha256'], partition['id']):
            raise ValueError(f'Closed {name} stage fails strict runner verification')
    paths = {part: Path(str(stem) + suffix) for part, suffix in
             (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
              ('raw', '.raw.jsonl'), ('records', '.records.jsonl'))}
    for item in paths.values():
        bind(root, item, bindings)
    evidence = {part: {'path': str(item), 'sha256': sha(path(root, item))}
                for part, item in paths.items()}
    evidence['review'] = review_binding
    records = read_rows(path(root, paths['records']))
    amendment = price_amendment(root, spec, manifest_sha, index, name,
                                review_path, records, bindings)
    proof = common.settlement_proof(partition, records, snapshot, phase_prefix(spec, index),
                                    records[-1] if name == 'development' else None)
    if amendment is not None:
        evidence.update(amendment['evidence'])
        evidence.update({key: amendment[key] for key in
                         ('historicalPromptPriceUsdPerToken',
                          'observedPromptPriceUsdPerToken')})
    return records, evidence, proof, amendment


def score(records, labels, ids):
    indexed = {row['id']: row for row in records}
    valid_ids = [rid for rid in ids if indexed[rid]['status'] == 'ok']
    fields = {field: sum(indexed[rid]['prediction'][field] == labels[rid][field]
                         for rid in valid_ids) for field in KEYS}
    confusion = {field: {} for field in KEYS}
    classes = {field: Counter() for field in KEYS}
    for rid in valid_ids:
        for field in KEYS:
            truth, prediction = labels[rid][field], indexed[rid]['prediction'][field]
            confusion[field].setdefault(truth, Counter())[prediction] += 1
            classes[field][prediction] += 1
    return {'denominator': len(ids), 'valid': len(valid_ids),
            'allFour': sum(all(indexed[rid]['prediction'][field] == labels[rid][field]
                           for field in KEYS) for rid in valid_ids),
            'fields': fields, 'outcomes': dict(Counter(row['status'] for row in records)),
            'invalidIds': [rid for rid in ids if rid not in valid_ids],
            'confusionCounts': {field: {truth: dict(counts) for truth, counts in confusion[field].items()}
                                for field in KEYS},
            'predictedClassCounts': {field: dict(classes[field]) for field in KEYS}}


def flip(first, second, ids):
    a, b = ({row['id']: row for row in part} for part in (first, second))
    shared = [rid for rid in ids if a[rid]['status'] == b[rid]['status'] == 'ok']
    result = {'denominator': len(shared), 'excludedIds': [rid for rid in ids if rid not in shared]}
    for field in (*KEYS, 'fourFieldVector'):
        changed = [rid for rid in shared if
                   (a[rid]['prediction'] if field == 'fourFieldVector' else a[rid]['prediction'][field]) !=
                   (b[rid]['prediction'] if field == 'fourFieldVector' else b[rid]['prediction'][field])]
        result[field] = {'changed': len(changed), 'caseIds': changed,
                         'rate': len(changed) / len(shared) if shared else None}
    return result


def stats(values):
    return common.stats(values)


def build_series(root, spec):
    manifest, labels, ids, partition, budget_binding, bindings = source_context(root, spec)
    data = {fresh: {} for fresh in PASSES}
    maps, missing = {}, []
    expected_budget = [{'event': 'budget', 'cap_usd': partition['cap_usd']}]
    for index, phase in enumerate(manifest['phases']):
        fresh, condition = phase['repeat'], phase['condition']
        if not closed(root, spec, index, 'development'):
            missing.append({'pass': fresh, 'condition': condition, 'status': 'not_completed'})
            continue
        if missing:
            raise ValueError('Closed phase skips an incomplete predecessor')
        if not closed(root, spec, index, 'smoke'):
            raise ValueError('Development closed without completed smoke')
        snapshot_path = phase_prefix(spec, index)
        snapshot_binding = bind(root, snapshot_path, bindings)
        snapshot = path(root, snapshot_path)
        smoke, smoke_evidence, smoke_budget, smoke_amendment = stage(
            root, spec, manifest, partition, budget_binding, index, 'smoke', bindings, snapshot)
        development, evidence, budget, development_amendment = stage(
            root, spec, manifest, partition, budget_binding, index, 'development', bindings, snapshot)
        expected_budget.extend(common.settlement_events(smoke))
        expected_budget.extend(common.settlement_events(development))
        if read_rows(snapshot) != expected_budget:
            raise ValueError('Budget prefix has missing, extra, or reordered events')
        maps[(fresh, condition)] = development
        served_route = {'requestedModel': spec.admission.MODEL,
                        'providerTag': spec.admission.PROVIDER,
                        'returnedModels': dict(Counter(row['returned_model'] for row in development)),
                        'returnedProviders': dict(Counter(row['returned_provider'] for row in development)),
                        'providerEndpoint': manifest['route']}
        if development_amendment is not None:
            served_route.update({key: development_amendment[key] for key in
                                 ('historicalPromptPriceUsdPerToken',
                                  'observedPromptPriceUsdPerToken')})
        data[fresh][condition] = {'status': 'completed', 'score': score(development, labels, ids),
                                  'usage': common.usage(development),
                                  'servedRoute': served_route,
                                  'evidence': {**evidence, 'smoke': smoke_evidence,
                                               'budgetPrefix': snapshot_binding,
                                               'budgetSettlement': budget,
                                               'smokeBudgetSettlement': smoke_budget}}
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
                           'fields': {field: variant['fields'][field] - baseline['fields'][field]
                                      for field in KEYS}})
            prompt_flips.append({'pass': fresh, 'from': 'P0', 'to': condition,
                                 **flip(maps[(fresh, 'P0')], maps[(fresh, condition)], ids)})
    pairwise = [{'condition': condition, 'from': a, 'to': b,
                 **flip(maps[(a, condition)], maps[(b, condition)], ids)}
                for condition in CONDITIONS for i, a in enumerate(PASSES) for b in PASSES[i + 1:]
                if (a, condition) in maps and (b, condition) in maps]
    ranges = {condition: {
        'allFour': stats([data[fresh][condition]['score']['allFour'] for fresh in PASSES
                          if condition in data[fresh]]),
        'fields': {field: stats([data[fresh][condition]['score']['fields'][field]
                                 for fresh in PASSES if condition in data[fresh]]) for field in KEYS}}
        for condition in CONDITIONS}
    across = {}
    for condition in CONDITIONS:
        if not all((fresh, condition) in maps for fresh in PASSES):
            continue
        indexed = [{row['id']: row for row in maps[(fresh, condition)]} for fresh in PASSES]
        shared = [rid for rid in ids if all(part[rid]['status'] == 'ok' for part in indexed)]
        across[condition] = {'denominator': len(shared),
                             'excludedIds': [rid for rid in ids if rid not in shared],
                             'fields': {field: [rid for rid in shared if
                                                 len({part[rid]['prediction'][field]
                                                      for part in indexed}) > 1] for field in KEYS},
                             'fourFieldVector': [rid for rid in shared if
                                                 len({tuple(part[rid]['prediction'][field] for field in KEYS)
                                                      for part in indexed}) > 1]}
    spread = {}
    for condition in ('P1', 'P2'):
        paired = [item for item in deltas if item['to'] == condition]
        spread[condition] = {'completedPairs': len(paired),
                             'allFourValues': [item['allFour'] for item in paired],
                             'allFourRange': [min(item['allFour'] for item in paired),
                                              max(item['allFour'] for item in paired)] if len(paired) == 3 else None,
                             'fieldRanges': {field: [min(item['fields'][field] for item in paired),
                                                     max(item['fields'][field] for item in paired)]
                                             if len(paired) == 3 else None for field in KEYS}}
    series = {'schema': 'additional-hosted-fresh-repeat-findings-v1',
              'configuration': spec.admission.CONFIG, 'seriesId': spec.series_id,
              'displayName': spec.display_name, 'method': 'fresh-matched-three',
              'model': spec.admission.MODEL, 'effort': spec.effort,
              'provider': spec.admission.PROVIDER, 'route': manifest['route'],
              'servedModel': None,
              'servedModelNote': 'Per-request returned model and provider are saved in sealed records.',
              'conditionOrder': list(CONDITIONS), 'passOrder': list(PASSES),
              'denominator': len(ids), 'plannedConditions': 9,
              'completedConditions': len(maps), 'missingPasses': missing,
              'passes': data, 'referenceVersion': '0.2',
              'referenceStatus': 'AI-reviewed provisional; not independent adjudication',
              'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field]
                                          for rid in ids).items())) for field in KEYS},
              'threePassSummary': ranges, 'pairwiseFlips': pairwise,
              'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
              'withinPassPromptFlips': prompt_flips, 'pairedDeltaSpread': spread,
              'historicalPassUsed': False,
              'limitations': ['The same 60 synthetic development records recur in every pass.',
                              'Provisional v0.2 references are not independent adjudication.',
                              'Client HTTP duration includes transport, not pure provider inference.',
                              'Serving revision and effective seed are unavailable.',
                              'Flip denominators include only records valid in both compared passes.']}
    return series, bindings


def build(root=ROOT, configuration=None):
    root = Path(root).resolve()
    series, bindings, missing_series = [], [], []
    for spec in SPECS:
        if configuration is not None and spec.admission.CONFIG != configuration:
            continue
        if not path(root, spec.base / 'manifest.json').exists():
            if any(path(root, spec.base).glob('phase-*')):
                raise ValueError('Stage evidence exists without a v2 manifest')
            missing_series.append({'configuration': spec.admission.CONFIG,
                                   'seriesId': spec.series_id, 'status': 'manifest_absent'})
            continue
        if not path(root, spec.base / 'budget.json').exists():
            if any(path(root, spec.base).glob('phase-*')):
                raise ValueError('Stage evidence exists without a budget manifest')
            missing_series.append({'configuration': spec.admission.CONFIG,
                                   'seriesId': spec.series_id, 'status': 'budget_absent'})
            continue
        result, sources = build_series(root, spec)
        series.append(result)
        for source in sources:
            if source not in bindings:
                bindings.append(source)
    return {'schema': 'additional-hosted-fresh-repeat-findings-v1', 'series': series,
            'availableConfigurations': [item['configuration'] for item in series],
            'missingSeries': missing_series, 'sourceBindings': bindings}


def capture_prefix(root, spec, index):
    """Create one immutable prefix after exact closure; never copy the live ledger to a report."""
    root = Path(root).resolve()
    manifest, _, _, partition, budget_binding, bindings = source_context(root, spec)
    if not 0 <= index < len(manifest['phases']):
        raise ValueError('Phase index outside frozen schedule')
    for previous in range(index + 1):
        if not closed(root, spec, previous, 'smoke') or not closed(root, spec, previous, 'development'):
            raise ValueError('Cannot snapshot an open phase or skip a predecessor')
    target = path(root, phase_prefix(spec, index))
    records = read_rows(path(root, spec.base / f'phase-{index + 1:02d}-development.records.jsonl'))
    final_attempt = records[-1]['attempt_id']
    live = path(root, spec.base / ('budget-' + partition['id'] + '.jsonl'))
    complete = live.read_bytes().splitlines(keepends=True)
    prefix, found = [], False
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
    if index and not content.startswith(path(root, phase_prefix(spec, index - 1)).read_bytes()):
        raise ValueError('Budget prefix does not extend previous phase')
    with tempfile.TemporaryDirectory() as tempdir:
        candidate = Path(tempdir) / 'candidate.jsonl'
        candidate.write_bytes(content)
        expected = [{'event': 'budget', 'cap_usd': partition['cap_usd']}]
        for phase in range(index + 1):
            snapshot = path(root, phase_prefix(spec, phase)) if phase < index else candidate
            for name in ('smoke', 'development'):
                selected, _, _, _ = stage(root, spec, manifest, partition, budget_binding,
                                       phase, name, bindings, snapshot)
                expected.extend(common.settlement_events(selected))
        if read_rows(candidate) != expected:
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
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--configuration', choices=[spec.admission.CONFIG for spec in SPECS])
    args = parser.parse_args(argv)
    content = json.dumps(build(configuration=args.configuration), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale additional hosted fresh report: {args.output}')
    else:
        args.output.write_text(content)


if __name__ == '__main__':
    main()
