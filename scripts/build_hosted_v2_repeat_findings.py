#!/usr/bin/env python3
"""Report only verified, closed Gemma26-on and Qwen27 v2 repeat phases.

Run against a clean export of a committed evidence cutoff. This reporter never
opens a provider connection or a mutable budget ledger.
"""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import gemma26_on_fresh_repeat_study_v2 as gemma_study
import gemma26_on_fresh_repeat_execution_v2 as gemma_execution
import qwen27_fresh_repeat_study_v2 as qwen_study
import qwen27_fresh_repeat_execution_v2 as qwen_execution
import resolve_provider_error_public_source as public_source
from development_benchmark import KEYS, valid

ROOT = Path(__file__).resolve().parents[1]
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABEL_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
SCHEMA = 'hosted-v2-fresh-repeat-findings-v1'
SPECS = (
    ('gemma26-on', gemma_study, gemma_execution, gemma_study.CONFIG),
    ('qwen27-medium', qwen_study, qwen_execution, 'openrouter-paid-qwen3.8-27b-medium'),
    ('qwen27-xhigh', qwen_study, qwen_execution, 'openrouter-paid-qwen3.8-27b-xhigh'),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    data = Path(path).read_bytes()
    if not data.endswith(b'\n') or any(not line.strip() for line in data.splitlines()):
        raise ValueError('Incomplete JSONL: ' + str(path))
    return [json.loads(line) for line in data.splitlines()]


def bind(root, relative, bindings, expected=None):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Source binding escapes the report root')
    if relative.as_posix() == 'results/openrouter-paid-budget.jsonl' or (
            relative.name.startswith('budget-partitions-v1-') and relative.suffix == '.jsonl'):
        raise ValueError('Moving budget ledger cannot be a report source')
    target = (root / relative).resolve()
    target.relative_to(root.resolve())
    if not target.is_file():
        if not public_source.is_audited(relative):
            raise ValueError('Bound source missing: ' + str(relative))
        _, value = public_source.resolve(root, relative, expected)
        if value not in bindings:
            bindings.append(value)
        return value
    actual = sha(target)
    if expected is not None and actual != expected:
        raise ValueError('Bound source changed: ' + str(relative))
    value = {'path': relative.as_posix(), 'sha256': actual}
    if value not in bindings:
        bindings.append(value)
    return value


def attested_plan_verify(root, study, qwen, config, fresh, expected_sha, bindings):
    """Verify a plan whose audited private sources have public attestations.

    The original private file is not rehashed in a public export. Exact request
    equality is checked against the bound v1 plan instead of rebuilding the
    historical audit from unavailable private bytes.
    """
    base = root / 'results/repeatability-v1' / study.SERIES
    path = plan_path(base, config, fresh, qwen)
    if sha(path) != expected_sha:
        raise ValueError('Frozen plan hash differs')
    plan = json.loads(path.read_text())
    expected_series = (study.SERIES + '-' + config.rsplit('-', 1)[-1]) if qwen else study.SERIES
    if (plan.get('series_id') != expected_series or plan.get('configuration_id') != config or
            plan.get('fresh_pass') != fresh or plan.get('condition_order') != study.ORDERS[fresh] or
            plan.get('model') != study.MODEL or plan.get('provider_tag') != study.PROVIDER or
            plan.get('max_tokens') != study.MAX_TOKENS or plan.get('temperature') != 0 or
            plan.get('stream') is not False or plan.get('continue_on_invalid_output') is not False or
            plan.get('smoke_count_per_condition') != 3 or plan.get('development_count_per_condition') != 60):
        raise ValueError('Frozen plan identity or request controls differ')
    for source in plan['source_bindings']:
        bind(root, source['path'], bindings, source['sha256'])
    original = plan['original_plan_binding']
    bind(root, original['path'], bindings, original['sha256'])
    prior = json.loads((root / original['path']).read_text())
    if (prior.get('conditions') != plan.get('conditions') or
            prior.get('configuration_id') != config or prior.get('fresh_pass') != fresh):
        raise ValueError('Frozen v2 requests differ from bound v1 plan')
    return plan


@contextmanager
def source_root(root, study, execution, qwen, master_path, bindings):
    """Use frozen verifiers against a clean export without opening its ledgers."""
    base = root / 'results/repeatability-v1' / study.SERIES
    with ExitStack() as stack:
        for module, name, value in (
                (study, 'ROOT', root), (study, 'BASE', base),
                (study, 'ORIGINAL_BASE', root / 'results/repeatability-v1' / study.ORIGINAL_SERIES),
                (execution, 'ROOT', root), (execution, 'MASTER', master_path),
                (execution, 'HOSTED_EXECUTION', root / 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json')):
            stack.enter_context(patch.object(module, name, value))
        if qwen:
            stack.enter_context(patch.object(execution, 'EXECUTION_MANIFEST', base / 'execution-manifest.json'))
        original_verify = study.verify

        def report_verify(*args):
            config, fresh, expected = args if qwen else (study.CONFIG, *args)
            try:
                return original_verify(*args)
            except FileNotFoundError:
                return attested_plan_verify(root, study, qwen, config, fresh, expected, bindings)

        stack.enter_context(patch.object(study, 'verify', report_verify))
        yield base


def score(records, labels, ids):
    indexed = {row['id']: row for row in records}
    if len(records) != len(ids) or set(indexed) != set(ids):
        raise ValueError('Closed phase does not cover exact development membership')
    predictions = {}
    for rid in ids:
        row = indexed[rid]
        if row.get('status') != 'ok' or not valid(row.get('prediction')):
            raise ValueError('Closed v2 phase contains an invalid prediction')
        predictions[rid] = row['prediction']
    fields = {field: sum(predictions[rid][field] == labels[rid][field] for rid in ids)
              for field in KEYS}
    all_four = sum(all(predictions[rid][field] == labels[rid][field] for field in KEYS)
                   for rid in ids)
    return {'denominator': len(ids), 'valid': len(ids), 'allFour': all_four,
            'fields': fields, 'outcomes': {'valid': len(ids), 'invalid_output': 0,
                                          'service_error': 0, 'never_sent': 0},
            'invalidIds': []}


def metric(values):
    present = [value for value in values if isinstance(value, int) and not isinstance(value, bool)]
    return {'sum': sum(present) if len(present) == len(values) else None,
            'reportedCount': len(present), 'missingCount': len(values) - len(present)}


def usage(records):
    keys = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    measured = {key: metric([(row.get('usage') or {}).get(key) for row in records]) for key in keys}
    reasoning = metric([((row.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens')
                        for row in records])
    costs = [row.get('observed_cost_usd') for row in records]
    known = [Decimal(str(cost)) for cost in costs if cost is not None]
    durations = [row.get('elapsed_seconds') for row in records]
    if any(not isinstance(value, (int, float)) or value < 0 for value in durations):
        raise ValueError('Closed phase has invalid client duration')
    inconsistent = sum(1 for row in records if
                       isinstance(((row.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens'), int)
                       and isinstance((row.get('usage') or {}).get('completion_tokens'), int)
                       and (row['usage']['completion_tokens_details']['reasoning_tokens'] >
                            row['usage']['completion_tokens']))
    return {'requestCount': len(records), 'requestSecondsTotal': sum(durations),
            'timingKind': 'client_request_to_record_not_provider_inference',
            'tokens': {**{key: measured[key]['sum'] for key in keys},
                       'reasoning_output_tokens': reasoning['sum']},
            'tokenAvailability': {**measured, 'providerReportedReasoningTokens': reasoning},
            'providerReasoningTokensAboveCompletionCount': inconsistent,
            'reasoningTokenNote': 'Provider-reported reasoning tokens are retained as a separate diagnostic and are not added to completion tokens.',
            'knownCostUsd': str(sum(known, Decimal(0))),
            'actualCostUsd': str(sum(known, Decimal(0))) if len(known) == len(records) else None,
            'unknownCostCount': len(records) - len(known)}


def flips(first, second, ids):
    a, b = ({row['id']: row for row in part} for part in (first, second))
    shared = [rid for rid in ids if a[rid].get('status') == b[rid].get('status') == 'ok'
              and valid(a[rid].get('prediction')) and valid(b[rid].get('prediction'))]
    result = {'denominator': len(shared), 'excludedIds': [rid for rid in ids if rid not in shared]}
    for field in (*KEYS, 'fourFieldVector'):
        changed = [rid for rid in shared if
                   (a[rid]['prediction'] if field == 'fourFieldVector' else a[rid]['prediction'][field]) !=
                   (b[rid]['prediction'] if field == 'fourFieldVector' else b[rid]['prediction'][field])]
        result[field] = {'changed': len(changed), 'caseIds': changed,
                         'rate': len(changed) / len(shared) if shared else None}
    return result


def terminal_status(path):
    if not path.is_file():
        return 'not_completed'
    data = path.read_bytes()
    if not data.endswith(b'\n'):
        return 'claimed_in_progress_or_interrupted'
    try:
        event = json.loads(data.splitlines()[-1])['event']
    except (IndexError, KeyError, ValueError):
        return 'claimed_in_progress_or_interrupted'
    return {'phase_completed': 'completed', 'phase_stopped': 'stopped_unscored',
            'phase_aborted': 'aborted_unscored'}.get(event, 'claimed_in_progress_or_interrupted')


def plan_path(base, config, fresh, qwen):
    return base / config / fresh / 'manifest.json' if qwen else base / fresh / 'manifest.json'


def phase_path(base, config, fresh, condition, qwen):
    return base / config / fresh / condition if qwen else base / fresh / condition


def build_series(root, name, study, execution, config, labels, ids, bindings):
    qwen = name.startswith('qwen27-')
    base = root / 'results/repeatability-v1' / study.SERIES
    plans = {}
    for fresh in PASSES:
        relative = plan_path(base, config, fresh, qwen).relative_to(root)
        bound = bind(root, relative, bindings)
        plans[fresh] = json.loads((root / relative).read_text())
        if plans[fresh].get('fresh_pass') != fresh or plans[fresh].get('configuration_id') != config:
            raise ValueError('Wrong frozen v2 plan identity')
        for source in plans[fresh]['source_bindings']:
            bind(root, source['path'], bindings, source['sha256'])
        original = plans[fresh].get('original_plan_binding')
        if original:
            bind(root, original['path'], bindings, original['sha256'])
    # Receipts pin the original absolute master path. It is checked, never opened.
    reviewed = next((phase_path(base, config, fresh, condition, qwen) /
                     'development.root-review.json' for fresh in PASSES for condition in CONDITIONS
                     if (phase_path(base, config, fresh, condition, qwen) /
                         'development.root-review.json').is_file()), None)
    master_path = Path(json.loads(reviewed.read_text())['master_ledger']) if reviewed else Path('/no-ledger-opened')
    with source_root(root, study, execution, qwen, master_path, bindings):
        verified = {}
        for fresh in PASSES:
            target = plan_path(base, config, fresh, qwen)
            verified[fresh] = (study.verify(config, fresh, sha(target)) if qwen
                               else study.verify(fresh, sha(target)))
        if qwen:
            manifest = base / 'execution-manifest.json'
            bind(root, manifest.relative_to(root), bindings)
            execution.verify_execution_manifest(sha(manifest))
        passes, maps, missing = {fresh: {} for fresh in PASSES}, {}, []
        for fresh in PASSES:
            for condition in CONDITIONS:
                folder = phase_path(base, config, fresh, condition, qwen)
                state = terminal_status(folder / 'development.journal.jsonl')
                if state != 'completed':
                    missing.append({'pass': fresh, 'condition': condition, 'status': state})
                    continue
                plan = verified[fresh]
                execution.require_order(plan, condition, 'development')
                receipt_path = folder / 'development.root-review.json'
                if qwen:
                    receipt, _ = execution.review_receipt(receipt_path, config, fresh, condition,
                                                          'development', sha(plan_path(base, config, fresh, qwen)))
                else:
                    receipt, _ = execution.review_receipt(receipt_path, fresh, condition,
                                                          'development', sha(plan_path(base, config, fresh, qwen)))
                bind(root, receipt['budget_manifest']['path'], bindings,
                     receipt['budget_manifest']['sha256'])
                closure = execution.verify_phase_closure(plan, condition, 'development')
                for stage in ('smoke', 'development'):
                    stage_folder = folder
                    for suffix in ('claim.json', 'journal.jsonl', 'attempts.jsonl', 'responses.jsonl'):
                        bind(root, (stage_folder / (stage + '.' + suffix)).relative_to(root), bindings)
                    if not qwen:
                        bind(root, (stage_folder / (stage + '.wire.jsonl')).relative_to(root), bindings)
                    bind(root, (stage_folder / (stage + '.root-review.json')).relative_to(root), bindings)
                bind(root, (folder / 'smoke-inspection.json').relative_to(root), bindings)
                bind(root, receipt_path.relative_to(root), bindings)
                records = read_jsonl(folder / 'development.attempts.jsonl')
                maps[(fresh, condition)] = records
                passes[fresh][condition] = {'status': 'completed', 'score': score(records, labels, ids),
                                            'usage': usage(records), 'evidence': closure,
                                            'servedRoute': {'returnedModels': dict(Counter(row['returned_model'] for row in records)),
                                                            'returnedProviders': dict(Counter(row['returned_provider'] for row in records))}}
    deltas, prompt_flips = [], []
    for fresh in PASSES:
        if (fresh, 'P0') not in maps:
            continue
        for condition in ('P1', 'P2'):
            if (fresh, condition) not in maps:
                continue
            before, after = passes[fresh]['P0']['score'], passes[fresh][condition]['score']
            deltas.append({'pass': fresh, 'from': 'P0', 'to': condition,
                           'denominator': len(ids), 'allFour': after['allFour'] - before['allFour'],
                           'fields': {f: after['fields'][f] - before['fields'][f] for f in KEYS}})
            prompt_flips.append({'pass': fresh, 'from': 'P0', 'to': condition,
                                 **flips(maps[(fresh, 'P0')], maps[(fresh, condition)], ids)})
    pairwise = [{'condition': condition, 'from': a, 'to': b,
                 **flips(maps[(a, condition)], maps[(b, condition)], ids)}
                for condition in CONDITIONS for i, a in enumerate(PASSES) for b in PASSES[i + 1:]
                if (a, condition) in maps and (b, condition) in maps]
    summary = {}
    across = {}
    for condition in CONDITIONS:
        values = [passes[fresh][condition]['score']['allFour'] for fresh in PASSES
                  if condition in passes[fresh]]
        summary[condition] = {'allFour': {'completedPasses': len(values), 'values': values,
                                         'range': [min(values), max(values)] if len(values) == 3 else None},
                              'fields': {field: {
                                  'completedPasses': sum(condition in passes[fresh] for fresh in PASSES),
                                  'values': [passes[fresh][condition]['score']['fields'][field]
                                             for fresh in PASSES if condition in passes[fresh]],
                                  'range': ([min(passes[fresh][condition]['score']['fields'][field]
                                                 for fresh in PASSES),
                                             max(passes[fresh][condition]['score']['fields'][field]
                                                 for fresh in PASSES)]
                                            if len(values) == 3 else None)} for field in KEYS}}
        if len(values) == 3:
            indexed = [{row['id']: row['prediction'] for row in maps[(fresh, condition)]}
                       for fresh in PASSES]
            across[condition] = {'denominator': len(ids), 'excludedIds': [],
                                 'fields': {field: [rid for rid in ids if
                                                    len({part[rid][field] for part in indexed}) > 1]
                                            for field in KEYS},
                                 'fourFieldVector': [rid for rid in ids if
                                                     len({tuple(part[rid][field] for field in KEYS)
                                                          for part in indexed}) > 1]}
    return {'schema': SCHEMA, 'configuration': config, 'seriesId': plans['fresh1']['series_id'],
            'displayName': ('Gemma 4 26B · DeepInfra fp8 · reasoning on' if name == 'gemma26-on'
                            else 'Qwen 3.8 27B · DeepInfra bf16 · ' + name.split('-')[-1]),
            'method': 'fresh-matched-three', 'model': study.MODEL,
            'effort': plans['fresh1']['reasoning_effort'], 'provider': study.PROVIDER,
            'conditionOrder': list(CONDITIONS), 'passOrder': list(PASSES),
            'denominator': len(ids), 'plannedConditions': 9,
            'completedConditions': len(maps), 'missingPasses': missing, 'passes': passes,
            'referenceVersion': '0.2', 'referenceStatus': 'AI-reviewed provisional; not independently adjudicated',
            'threePassSummary': summary, 'pairwiseFlips': pairwise,
            'changesAcrossThreePasses': across,
            'withinPassPromptDeltas': deltas, 'withinPassPromptFlips': prompt_flips,
            'historicalPassUsed': False,
            'limitations': ['The same 60 synthetic development comments recur in each completed phase.',
                            'Scores use provisional reference labels, not independent adjudication.',
                            'Client request-to-record duration includes transport, raw capture and billing settlement.',
                            'Costs are provider-reported usage amounts; the moving child and master ledgers are not publication sources.',
                            'Provider-reported reasoning-token detail can exceed completion tokens; it is retained separately, not added.',
                            'Serving revision and effective seed are unavailable.'] +
                           (['An audited private historical error file is represented by a verified sanitized public copy and original-hash attestation, not rehashed private bytes.']
                            if name == 'gemma26-on' else [])}


def build(root=ROOT):
    root = Path(root).resolve()
    bindings = []
    bind(root, LABELS, bindings, LABEL_SHA256)
    bind(root, Path('scripts/build_hosted_v2_repeat_findings.py'), bindings)
    labels_rows = read_jsonl(root / LABELS)
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if ([row.get('id') for row in labels_rows] != ids or
            any(row.get('review_version') != '0.2' or not valid(row.get('proposed_labels')) for row in labels_rows)):
        raise ValueError('Provisional reference corpus differs')
    labels = {row['id']: row['proposed_labels'] for row in labels_rows}
    series = [build_series(root, name, study, execution, config, labels, ids, bindings)
              for name, study, execution, config in SPECS]
    return {'schema': SCHEMA, 'series': series, 'sourceBindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build(args.root)
    content = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != content:
            raise ValueError('Published hosted v2 feed differs from closed source evidence')
    elif args.output is not None:
        args.output.write_text(content)
    print(', '.join(f"{item['configuration']} {item['completedConditions']}/9" for item in result['series']))


if __name__ == '__main__':
    main()
