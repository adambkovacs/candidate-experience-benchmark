#!/usr/bin/env python3
"""Build a source-bound offline report for closed Kev native P1/P2 passes."""
import argparse
import base64
from collections import Counter
import copy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics

from development_benchmark import ROOT, KEYS, VALUES, read_rows, valid
import build_kev_native_findings as p0_report
import build_repeat_findings as shared
import openrouter_decision_smoke as decision
import openrouter_native_variants_full_v1 as runner
import openrouter_native_variants_plan as frozen


BASE = ROOT / 'results/route-audits/native-variants-full-v1-20261006'
REFERENCES = ROOT / 'data/pilot/proposed_labels.jsonl'
REFERENCE_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
CONFIGS = {
    'P1': 'kev-openrouter-native-p1-choice-v1',
    'P2': 'kev-openrouter-native-p2-choice-v1',
}
STAGES = ('fresh1', 'fresh2', 'fresh3')
OUTPUT = ROOT / 'public-site/kev-native-prompt-findings.json'
BASE_RELATIVE = BASE.relative_to(ROOT)
MASTER_RELATIVE = Path('results/openrouter-paid-budget.jsonl')


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def binding(path):
    path = Path(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': file_sha(path)}


def _archived_root(path_value, relative, label):
    """Return the saved checkout prefix after validating a canonical suffix."""
    path = Path(path_value) if isinstance(path_value, str) else Path()
    relative = Path(relative)
    if (not path.is_absolute() or len(path.parts) <= len(relative.parts) or
            path.parts[-len(relative.parts):] != relative.parts):
        raise ValueError(label + ' archived path differs')
    return path.parts[:-len(relative.parts)]


def archived_budget_identity(config, stage, manifest, budget_path, *, base=BASE):
    """Validate a closed allocation without rebasing its signed absolute paths.

    Execution receipts hash the absolute child-ledger string that existed when
    the allocation was approved. Offline verification keeps that string for the
    identity calculation, while reading the same ledger by its repository path
    in the current checkout.
    """
    paths = runner.paths(base, config, stage)
    budget_path = Path(budget_path)
    if budget_path.resolve() != paths['budget'].resolve():
        raise ValueError('Wrong archived full-pass budget path')
    budget = json.loads(budget_path.read_text())
    partition_id = manifest['passes'][STAGES.index(stage)]['partition_id']
    current_child = paths['budget'].parent / (paths['budget'].stem + '-' + partition_id + '.jsonl')
    partitions = budget.get('partitions')
    if budget.get('version') != 'paid-partitions-v1' or not isinstance(partitions, list) or len(partitions) != 1:
        raise ValueError('Archived full-pass child allocation differs')
    partition = partitions[0]
    expected = {'id': partition_id, 'cap_usd': manifest['whole_pass_bound_usd'],
                'child_ledger': partition.get('child_ledger'), 'model': manifest['model'],
                'provider': manifest['provider_tag'], 'reasoning': 'none'}
    if partition != expected or not current_child.is_file() or not current_child.stat().st_size:
        raise ValueError('Archived full-pass child allocation differs')
    master_root = _archived_root(budget.get('master_ledger'), MASTER_RELATIVE,
                                 'Budget master ledger')
    child_relative = BASE_RELATIVE / config / current_child.name
    child_root = _archived_root(partition['child_ledger'], child_relative,
                                'Budget child ledger')
    if child_root != master_root:
        raise ValueError('Archived budget paths use different checkout roots')
    identity = {'manifest_sha256': file_sha(paths['manifest']),
                'budget_manifest_sha256': file_sha(budget_path),
                'partition_id': partition_id,
                'child_ledger': partition['child_ledger'],
                'cap_usd': partition['cap_usd']}
    hold_source = hashlib.sha256(decision.canonical(identity)).hexdigest()
    return hold_source, current_child, partition['child_ledger']


def phase_state(directory):
    directory = Path(directory)
    completion = (directory / 'completion.json').is_file()
    reconciliation = (directory / 'budget-reconciliation.json').is_file()
    attempts = (directory / 'attempts.jsonl').is_file()
    if completion and reconciliation:
        return 'closed_candidate'
    if completion:
        return 'terminal_unreconciled'
    if attempts:
        return 'running_unscored'
    return 'not_started'


def _utc(value, label):
    if not isinstance(value, str):
        raise ValueError(label + ' timestamp missing')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_phase_attempts(manifest, directory):
    """Validate all raw outcomes and return report-only records.

    This function deliberately checks the completion hash before parsing rows,
    then checks the 60 exact four-event groups. A completion with a truncated
    journal cannot become a scored pass even if its hash is recomputed.
    """
    directory = Path(directory)
    completion = json.loads((directory / 'completion.json').read_text())
    attempts_path = directory / 'attempts.jsonl'
    if completion.get('attempts_sha256') != file_sha(attempts_path):
        raise ValueError('Closed phase attempts SHA differs from completion')
    rows = read_jsonl(attempts_path)
    if len(rows) != 240:
        raise ValueError('Closed phase must contain exactly 60 four-event outcomes')
    predictions = {}
    native = {}
    costs = Decimal(0)
    input_tokens = output_tokens = 0
    elapsed = []
    for index, ident in enumerate(manifest['ids']):
        reserved, started, response, parsed = rows[index * 4:index * 4 + 4]
        group = (reserved, started, response, parsed)
        attempt_id = reserved.get('attempt_id')
        if ([row.get('stage') for row in group] != ['reserved', 'started', 'response', 'parsed'] or
                any(row.get('id') != ident for row in group) or
                not isinstance(attempt_id, str) or not attempt_id or
                any(row.get('attempt_id') != attempt_id for row in group) or
                reserved.get('request_sha256') != manifest['request_sha256'][index] or
                reserved.get('cost_unknown') is not True or
                response.get('cost_unknown') is not False or
                response.get('http_status') != 200 or
                response.get('parse_error_type') is not None or
                parsed.get('valid') is not True):
            raise ValueError('Closed phase event identity or terminal outcome differs: ' + ident)
        request = base64.b64decode(started.get('request_base64', ''), validate=True)
        if hashlib.sha256(request).hexdigest() != manifest['request_sha256'][index]:
            raise ValueError('Saved request bytes differ: ' + ident)
        raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
        body = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != response.get('raw_response_sha256') or
                len(raw) != response.get('raw_response_size_bytes') or body != response.get('body') or
                body.get('model') != manifest['returned_model'] or
                body.get('provider') != manifest['provider'] or
                body.get('truncated') is True):
            raise ValueError('Raw response or route controls differ: ' + ident)
        prediction = decision.validate_response(body, decision.ROUTES['kev'])
        if prediction != parsed.get('prediction') or not valid(prediction):
            raise ValueError('Parsed prediction differs from raw response: ' + ident)
        actual = decision.response_cost(body)
        if (actual is None or Decimal(str(response.get('actual_cost_usd'))) != actual or
                type(response.get('client_request_elapsed_ns')) is not int or
                response['client_request_elapsed_ns'] < 0 or
                _utc(response.get('request_end_utc'), ident) < _utc(response.get('request_start_utc'), ident)):
            raise ValueError('Cost or client timing differs: ' + ident)
        usage = body.get('usage')
        if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
                type(usage.get('output_tokens')) is not int):
            raise ValueError('Provider token accounting differs: ' + ident)
        fields = {}
        for key in KEYS:
            answer = body['answers'][key]
            probabilities = answer.get('probabilities')
            confidence = answer.get('confidence')
            expected = set(VALUES[key])
            if (not isinstance(probabilities, dict) or set(probabilities) != expected or
                    any(type(value) not in (int, float) or not math.isfinite(value) or value < 0 or value > 1
                        for value in probabilities.values()) or
                    abs(sum(probabilities.values()) - 1) > 0.001 or
                    type(confidence) not in (int, float) or not math.isfinite(confidence) or
                    not 0 <= confidence <= 1):
                raise ValueError('Native probabilities or confidence invalid: ' + ident + ':' + key)
            fields[key] = {'choice': prediction[key], 'probabilities': probabilities,
                           'confidence': confidence}
        predictions[ident] = prediction
        native[ident] = fields
        costs += actual
        input_tokens += usage['input_tokens']
        output_tokens += usage['output_tokens']
        elapsed.append(response['client_request_elapsed_ns'] / 1e9)
    if list(predictions) != manifest['ids']:
        raise ValueError('Closed phase is missing outcomes')
    return {'predictions': predictions, 'native': native,
            'usage': {'inputTokens': input_tokens, 'outputTokens': output_tokens,
                      'actualProviderCostUsd': str(costs),
                      'clientRequestSeconds': {'total': sum(elapsed),
                                               'median': statistics.median(elapsed),
                                               'p95': sorted(elapsed)[math.ceil(.95 * len(elapsed)) - 1],
                                               'kind': 'client_observed_request'}}}


def _validate_closure(condition, config, stage, manifest, base):
    paths = runner.paths(base, config, stage)
    directory = paths['stage']
    context_sha = runner.context_proof(config, manifest, base=base)
    inspection_sha = runner.smoke_inspection(config, manifest, base=base)
    prior = runner.predecessor(config, stage, manifest, base=base)
    hold_source, child, archived_child = archived_budget_identity(
        config, stage, manifest, paths['budget'], base=base)
    receipt = runner.validate_receipt(config, stage, manifest, paths['receipt'], paths['budget'],
                                      context_sha, inspection_sha, prior, hold_source, base=base)
    completion_path = directory / 'completion.json'
    completion = json.loads(completion_path.read_text())
    expected = {'schema': runner.SCHEMA + '-completion', 'configuration_id': config,
                'stage': stage, 'ids': runner.IDS, 'valid_count': 60,
                'invalid_count': 0, 'invalid_ids': [],
                'manifest_sha256': file_sha(paths['manifest']),
                'context_proof_sha256': context_sha,
                'smoke_inspection_sha256': inspection_sha,
                'predecessor_proof': prior,
                'receipt_sha256': file_sha(paths['receipt']),
                'budget_manifest_sha256': file_sha(paths['budget']),
                'endpoint_catalog_sha256': file_sha(directory / 'endpoint-catalog.json'),
                'attempts_sha256': file_sha(directory / 'attempts.jsonl'),
                'known_actual_cost_usd': completion.get('known_actual_cost_usd'),
                'reference_labels_read': False}
    if completion != expected or file_sha(directory / 'review-receipt.json') != file_sha(paths['receipt']):
        raise ValueError(f'{condition} {stage} completion or copied receipt binding differs')
    parsed = validate_phase_attempts(manifest, directory)
    if Decimal(parsed['usage']['actualProviderCostUsd']) != Decimal(completion['known_actual_cost_usd']):
        raise ValueError(f'{condition} {stage} scored/provider cost differs')
    reconciliation_path = directory / 'budget-reconciliation.json'
    reconciliation = json.loads(reconciliation_path.read_text())
    expected_partition = config + '-' + stage + '-full-v1'
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != expected_partition or
            Decimal(reconciliation.get('known_actual_usd', '-1')) != Decimal(completion['known_actual_cost_usd']) or
            Decimal(reconciliation.get('unknown_upper_bound_usd', '-1')) != 0 or
            reconciliation.get('child_ledger') != archived_child or
            reconciliation.get('child_sha256') != file_sha(child)):
        raise ValueError(f'{condition} {stage} budget reconciliation differs')
    sources = [binding(paths['manifest']), binding(paths['context']), binding(paths['inspection']),
               binding(paths['receipt']), binding(paths['budget']), binding(child),
               binding(directory / 'review-receipt.json'), binding(directory / 'endpoint-catalog.json'),
               binding(directory / 'attempts.jsonl'), binding(completion_path), binding(reconciliation_path)]
    return completion, receipt, parsed, sources


def score(predictions, truth, ids):
    records = {ident: {'status': 'ok', 'prediction': predictions[ident]} for ident in ids}
    return shared.score(records, truth, ids)


def compare(a, b, ids):
    fields = {}
    for key in KEYS:
        changed = [ident for ident in ids if a['predictions'][ident][key] != b['predictions'][ident][key]]
        probability = [ident for ident in ids if a['native'][ident][key]['probabilities'] !=
                       b['native'][ident][key]['probabilities']]
        confidence = [ident for ident in ids if a['native'][ident][key]['confidence'] !=
                      b['native'][ident][key]['confidence']]
        fields[key] = {'choiceChanged': len(changed), 'choiceChangedIds': changed,
                       'nativeProbabilityDictionaryChanged': len(probability),
                       'nativeProbabilityDictionaryChangedIds': probability,
                       'vendorConfidenceChanged': len(confidence),
                       'vendorConfidenceChangedIds': confidence}
    vectors = [ident for ident in ids if a['predictions'][ident] != b['predictions'][ident]]
    probability_any = sorted({ident for key in KEYS for ident in fields[key]['nativeProbabilityDictionaryChangedIds']})
    confidence_any = sorted({ident for key in KEYS for ident in fields[key]['vendorConfidenceChangedIds']})
    return {'denominator': len(ids), 'fourFieldVectorChanges': len(vectors),
            'fourFieldVectorChangedIds': vectors, 'fields': fields,
            'nativeProbabilityDictionaryChanges': len(probability_any),
            'nativeProbabilityDictionaryChangedIds': probability_any,
            'vendorConfidenceChanges': len(confidence_any),
            'vendorConfidenceChangedIds': confidence_any}


def load_frozen_native_plans(root=ROOT):
    plans = frozen.build_plan(root)
    return plans[CONFIGS['P1']]['requests'], plans[CONFIGS['P2']]['requests']


def verify_native_prompt_equivalence(p1_requests, p2_requests):
    if len(p1_requests) != 60 or len(p2_requests) != 60:
        raise ValueError('Native prompt variants do not contain 60 requests')
    changed = {key: 0 for key in KEYS}
    for one, two in zip(p1_requests, p2_requests):
        if one['id'] != two['id'] or one['feedback_sha256'] != two['feedback_sha256'] or \
                one['p0_payload_sha256'] != two['p0_payload_sha256']:
            raise ValueError('Native prompt identity controls differ')
        left, right = copy.deepcopy(one['payload']), copy.deepcopy(two['payload'])
        for key in KEYS:
            if left['questions'][key]['instructions'] != right['questions'][key]['instructions']:
                changed[key] += 1
            left['questions'][key].pop('instructions')
            right['questions'][key].pop('instructions')
        if left != right:
            raise ValueError('Native prompt non-instruction controls differ')
    if any(count != 60 for count in changed.values()):
        raise ValueError('Native prompt instruction contrast is incomplete')
    return {'verified': True, 'denominator': 60,
            'meaning': 'P1 and P2 share feedback, policy, criteria, labels, label order, route, and parser. Only each native Choice question instruction differs.',
            'instructionDifferencesByField': changed,
            'wireEquivalence': 'Native Choice analogues of the prompt conditions; not byte-identical chat prompts.'}


def build(base=BASE, refs_path=REFERENCES):
    refs_path = Path(refs_path)
    if file_sha(refs_path) != REFERENCE_SHA256:
        raise ValueError('Frozen development reference SHA-256 differs')
    refs = read_rows(refs_path)
    ids = [row['id'] for row in refs]
    if (ids != runner.IDS or len(set(ids)) != 60 or
            any(row.get('split') != 'development' or not valid(row.get('proposed_labels')) for row in refs)):
        raise ValueError('Frozen development reference membership differs')
    truth = {row['id']: row['proposed_labels'] for row in refs}
    p1_requests, p2_requests = load_frozen_native_plans()
    equivalence = verify_native_prompt_equivalence(p1_requests, p2_requests)
    conditions, private, sources, excluded = {}, {}, [binding(refs_path)], []
    for condition, config in CONFIGS.items():
        manifest = runner.verify(config, base)
        if (manifest['condition'] != condition or manifest['route'] != 'kev' or
                manifest['ids'] != ids or manifest['reference_labels_read'] is not False):
            raise ValueError(condition + ' full-pass manifest controls differ')
        sources.append(binding(runner.paths(base, config)['manifest']))
        passes, private[condition] = {}, {}
        for stage in STAGES:
            directory = runner.paths(base, config, stage)['stage']
            state = phase_state(directory)
            if state != 'closed_candidate':
                excluded.append({'condition': condition, 'stage': stage, 'status': state})
                continue
            completion, receipt, parsed, phase_sources = _validate_closure(
                condition, config, stage, manifest, base)
            phase_score = score(parsed['predictions'], truth, ids)
            passes[stage] = {'completionStatus': 'complete', 'score': phase_score,
                             'usage': parsed['usage'], 'sourceBindings': phase_sources}
            private[condition][stage] = parsed
            sources.extend(phase_sources)
        comparisons = []
        closed = [stage for stage in STAGES if stage in private[condition]]
        for index, first in enumerate(closed):
            for second in closed[index + 1:]:
                comparisons.append({'from': first, 'to': second,
                                    **compare(private[condition][first], private[condition][second], ids)})
        all_four = [passes[stage]['score']['allFour'] for stage in closed]
        conditions[condition] = {'completedPasses': len(closed), 'plannedPasses': 3,
                                 'passOrder': list(STAGES), 'passes': passes,
                                 'repeatComparisons': comparisons,
                                 'repeatVariation': {'available': len(closed) >= 2,
                                    'allFourRange': [min(all_four), max(all_four)] if all_four else None,
                                    'fieldRanges': {key: [min(passes[s]['score']['fields'][key] for s in closed),
                                                          max(passes[s]['score']['fields'][key] for s in closed)]
                                                    if closed else None for key in KEYS}}}
    paired = []
    for stage in STAGES:
        if stage in private['P1'] and stage in private['P2']:
            item = compare(private['P1'][stage], private['P2'][stage], ids)
            item.update({'stage': stage,
                         'scoreDeltaP2MinusP1': {
                            'allFour': conditions['P2']['passes'][stage]['score']['allFour'] -
                                       conditions['P1']['passes'][stage]['score']['allFour'],
                            'fields': {key: conditions['P2']['passes'][stage]['score']['fields'][key] -
                                      conditions['P1']['passes'][stage]['score']['fields'][key] for key in KEYS}}})
            paired.append(item)
    historical = p0_report.build()
    if (historical['model'] != conditions_manifest_model(base) or
            historical['provider'] != 'SiliconFlow'):
        raise ValueError('Historical P0 model/provider controls differ')
    p0_clean, p0_comparisons = {}, {}
    for stage in ('fresh1', 'fresh2'):
        item = historical['passes'].get(stage)
        if item and item.get('completionStatus') == 'complete' and item['score']['valid'] == 60:
            p0_clean[stage] = {'score': item['score'], 'usage': item['usage'],
                               'sourceBindings': item['sourceBindings']}
            p0_comparisons[stage] = {
                condition: {'allFourDeltaVsP0': conditions[condition]['passes'][stage]['score']['allFour'] - item['score']['allFour'],
                            'fieldDeltaVsP0': {key: conditions[condition]['passes'][stage]['score']['fields'][key] - item['score']['fields'][key]
                                               for key in KEYS}}
                for condition in ('P1', 'P2') if stage in conditions[condition]['passes']}
    return {'schema': 'kev-native-prompt-findings-v1',
            'displayName': 'Kev 4B OpenRouter native Choice prompt findings',
            'denominator': 60, 'conditionOrder': ['P1', 'P2'],
            'referenceStatus': 'Frozen provisional v0.2 development labels; scoring is offline.',
            'nativePromptEquivalence': equivalence, 'conditions': conditions,
            'pairedP1P2': paired, 'excludedPasses': excluded,
            'historicalP0': {'controlsVerified': True,
                             'comparisonScope': 'Separate descriptive baseline; only clean closed P0 fresh1/fresh2 are eligible.',
                             'cleanComparisons': p0_clean, 'scoreDeltas': p0_comparisons,
                             'interruptedThirdExcluded': True},
            'interpretation': {
                'nativeChoiceProbabilities': 'Full native Choice probability dictionaries are retained and compared separately from categorical answers.',
                'vendorConfidence': 'Provider confidence is retained separately. It is not treated as the chosen-label probability or a calibrated correctness probability.',
                'timing': 'Client-observed request duration includes network and local work; it is not provider inference time.',
                'tokens': 'Token counts are provider-reported usage.',
                'cost': 'Cost is observed provider cost reconciled against the closed child ledger.',
                'repeatPower': 'Three closed passes describe observed repeat variation for these exact requests. They do not determine performance on new records or another route.'},
            'referenceBinding': binding(refs_path),
            'sourceBindings': unique_bindings(sources)}


def conditions_manifest_model(base):
    manifests = [json.loads((Path(base) / (config + '.json')).read_text()) for config in CONFIGS.values()]
    models = {item['model'] for item in manifests}
    if len(models) != 1:
        raise ValueError('P1/P2 requested models differ')
    return models.pop()


def unique_bindings(items):
    result = {}
    for item in items:
        prior = result.get(item['path'])
        if prior is not None and prior != item:
            raise ValueError('Conflicting source binding: ' + item['path'])
        result[item['path']] = item
    return [result[key] for key in sorted(result)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build()
    expected = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.is_file() or args.output.read_text() != expected:
            raise ValueError('Saved Kev native prompt report differs from verified evidence')
    else:
        args.output.write_text(expected)
    print(f"Kev native prompt report: P1={result['conditions']['P1']['completedPasses']}/3, "
          f"P2={result['conditions']['P2']['completedPasses']}/3 -> {args.output}")


if __name__ == '__main__':
    main()
