#!/usr/bin/env python3
"""Export public, development-only evidence without exposing request payloads or credentials."""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
PHASE = Path('results/prompt-comparison-v1-2026-09-24')


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def tokens(config, root=ROOT):
    paths = config.get('raw_batch_attempt_files') or config.get('attempt_files') or config.get('cost', {}).get('source_paths') or []
    if isinstance(paths, str):
        paths = [paths]
    totals = {k: None for k in ('input', 'output', 'cachedInput', 'cacheWrite', 'reasoning')}
    reported = count = 0
    seen = set()
    for name in paths:
        path = root / name
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        for row in rows(path):
            count += 1
            usage = row.get('usage') or {}
            stats = row.get('stats') or {}
            details = usage.get('prompt_tokens_details') or {}
            output_details = usage.get('completion_tokens_details') or usage.get('output_tokens_details') or {}
            vals = {
                'input': usage.get('input_tokens', usage.get('prompt_tokens', stats.get('promptTokensCount'))),
                'output': usage.get('output_tokens', usage.get('completion_tokens', stats.get('predictedTokensCount'))),
                'cachedInput': usage.get('cached_input_tokens', usage.get('cache_read_input_tokens', details.get('cached_tokens'))),
                'cacheWrite': usage.get('cache_creation_input_tokens'),
                'reasoning': output_details.get('reasoning_tokens', output_details.get('thinking_tokens')),
            }
            vals = {k: number(v) for k, v in vals.items()}
            reported += int(vals['input'] is not None and vals['output'] is not None)
            for key, val in vals.items():
                if val is not None:
                    totals[key] = (totals[key] or 0) + val
    return {**totals, 'reportedRequests': reported, 'totalRequests': count,
            'complete': count > 0 and reported == count,
            'note': 'Development requests only; batch usage counted once. Cache and reasoning counts are separately reported provider fields, not additional totals. Missing usage is not zero.'}


def surface(config):
    ident = config['id']
    model = config.get('model', '').lower()
    if 'openrouter' in ident:
        return 'OpenRouter'
    if ident.startswith('typesafe-'):
        return 'TypeSafe API'
    if ident.startswith('codex-'):
        return 'Codex subscription'
    if 'claude' in model or ident.startswith(('opus', 'sonnet', 'haiku', 'fable')):
        return 'Claude subscription'
    if 'gemini' in model or ident.startswith('gemini'):
        return 'Gemini subscription'
    return 'Local / specialist'


def metric(evaluation, all_four):
    return {**{key: evaluation['metrics'][key]['correct'] for key in FIELDS}, 'all_four': all_four}


def cost_fields(cost):
    return {'actualUsd': cost.get('total_actual_usd'), 'knownUsd': cost.get('known_actual_usd'),
            'estimatedUsd': None, 'unknownUpperBoundUsd': cost.get('unknown_reserved_upper_bound_usd'),
            'availability': cost.get('availability', 'unavailable'),
            'note': 'Development attempts only; excludes smoke. Unknown-charge bounds are not actual spending. Subscription fees and local hardware/electricity are not allocated per run.'}


def cases_for(run_id, predictions, reference_cases):
    by_id = {r['id']: r for r in predictions if r.get('id') in reference_cases}
    result = []
    for ident, base in reference_cases.items():
        source = by_id.get(ident, {})
        prediction = source.get('prediction') if source.get('status') == 'ok' else None
        if not isinstance(prediction, dict) or set(prediction) != set(FIELDS):
            prediction = None
        result.append({'configuration': run_id, 'id': ident, 'feedback': base['feedback'],
                       'reference': base['reference'], 'prediction': prediction,
                       'status': source.get('status', 'missing'),
                       'different_fields': [key for key in FIELDS if prediction is not None and prediction[key] != base['reference'][key]]})
    return result


def score_saved(predictions, root):
    from development_benchmark import score
    refs = rows(root / 'data/pilot/proposed_labels.jsonl')
    pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
    evaluation = score(refs, predictions, pairs)
    truth = {r['id']: r['proposed_labels'] for r in refs}
    all_four = sum(row.get('status') == 'ok' and row.get('prediction') == truth.get(row.get('id')) for row in predictions)
    return evaluation, all_four


def phase_run(parent, condition, evaluation, all_four, source, root, baseline, telemetry=None, cost=None,
              predictions=None, paired=False, experiment='prompt-comparison-v1', status=None):
    base = baseline.get(parent, {})
    ident = parent + '--' + condition.lower()
    if predictions is None and source and (root / source).is_file():
        predictions = rows(root / source)
    predictions = predictions or []
    telemetry = telemetry or {}
    cost = cost or {}
    source_path = root / source if source else None
    batch = any(r.get('timing_kind') == 'amortized_batch_share_not_individual_latency' for r in predictions)
    surface_name = base.get('surface') or surface({'id': parent, 'model': base.get('model', '')})
    comparable = surface_name not in ('Local / specialist',)
    seconds = [number(r.get('elapsed_seconds')) for r in predictions]
    seconds = [v for v in seconds if v is not None]
    timing_total = telemetry.get('attempt_seconds')
    if timing_total is None and len(seconds) == len(predictions) and predictions:
        timing_total = sum(seconds)
    run = {
        'id': ident, 'experimentId': parent, 'protocolId': experiment, 'parentBaselineId': parent,
        'model': base.get('model', parent), 'effort': base.get('effort', 'not applicable'),
        'surface': surface_name, 'condition': condition, 'complete': len(predictions) == 60,
        'resultStatus': status or ('complete' if len(predictions) == 60 else 'partial'),
        'pairedEligible': bool(paired), 'records': len(predictions), 'valid': evaluation['valid_outputs'],
        'metrics': metric(evaluation, all_four),
        'timing': {'totalSeconds': timing_total, 'medianSeconds': statistics.median(seconds) if len(seconds) == len(predictions) and seconds and not batch else None,
                   'p95Seconds': sorted(seconds)[math.ceil(.95 * len(seconds))-1] if len(seconds) == len(predictions) and seconds and not batch else None,
                   'kind': 'batch' if batch else 'record' if seconds else 'unavailable',
                   'requests': telemetry.get('attempts', len(predictions)),
                   'complete': timing_total is not None and (telemetry.get('attempts') is not None or len(seconds) == len(predictions)),
                   'comparableHosted': comparable and not batch,
                   'note': 'Batch wall time is for the batch, never individual-record latency.' if batch else 'Development attempt timing; local timing is diagnostic and not hosted-comparable.' if not comparable else 'Development attempt timing.'},
        'tokens': tokens({'attempt_files': cost.get('source_paths') or [source]} if source and Path(source).suffix == '.jsonl' else {}, root),
        'cost': cost_fields(cost), 'evidenceUrl': GITHUB + str(source) if source_path and source_path.is_file() else None,
    }
    if telemetry:
        for field, target in [('input_tokens', 'input'), ('output_tokens', 'output'), ('reasoning_tokens', 'reasoning')]:
            if telemetry.get(field) is not None:
                run['tokens'][target] = telemetry[field]
        if telemetry.get('attempts') is not None:
            run['tokens']['totalRequests'] = telemetry['attempts']
            run['tokens']['reportedRequests'] = telemetry['attempts'] if telemetry.get('input_tokens') is not None and telemetry.get('output_tokens') is not None else 0
            run['tokens']['complete'] = run['tokens']['reportedRequests'] == telemetry['attempts']
    return run


def closed_journal(path):
    journal = Path(str(path) + '.attempts.jsonl')
    if not journal.is_file():
        return False
    lines = rows(journal)
    return bool(lines and lines[-1].get('event') == 'terminal')


def local_suffix_run(root, baseline, reference_cases):
    """Return a verified public view only after the offline suffix report exists."""
    report_path = root / 'results/local-prompt-suffix-v1/reconciliation.json'
    if not report_path.is_file():
        return None
    from reconcile_local_prompt_suffix_v1 import reconcile
    report = json.loads(report_path.read_text())
    if report != reconcile(root):
        raise ValueError('Local suffix report differs from terminal-bound offline reconciliation')
    if (report['configuration'] != 'qwen3.5-4b-sdk-thinking-on' or report['variant'] != 'P2' or
        report['denominator'] != 60 or report['ambiguous_outcome_ids'] != ['DEV-019'] or
        report['coverage_complete'] is not False):
        raise ValueError('Local suffix public coverage differs')
    sources = report['sources']
    saved = rows(root / sources['original_output']['file']) + rows(root / sources['suffix_output']['file'])
    normalized = [{'id': row['id'], 'status': row['decision']['status'],
                   'prediction': row['decision'].get('prediction')} for row in saved]
    if (len(normalized) != report['saved_rows'] or
        [row['id'] for row in normalized[:18]] != [f'DEV-{i:03}' for i in range(1, 19)] or
        [row['id'] for row in normalized[18:]] != [f'DEV-{i:03}' for i in range(20, 20 + len(normalized) - 18)] or
        report['claimed_attempts'] != len(normalized) + 1 or
        report['never_sent_ids'] != [f'DEV-{i:03}' for i in range(20 + len(normalized) - 18, 61)]):
        raise ValueError('Local suffix saved rows or never-sent coverage differs')
    public_predictions = normalized[:18] + [{'id': 'DEV-019', 'status': 'ambiguous_no_saved_output',
                                             'prediction': None}] + normalized[18:]
    evaluation, all_four = score_saved(public_predictions, root)
    if (evaluation != report['evaluation'] or evaluation['valid_outputs'] != report['valid_outputs'] or
        all_four != report['all_four_correct'] or
        any(evaluation['metrics'][field]['accuracy'] != report['field_accuracy'][field] for field in FIELDS)):
        raise ValueError('Local suffix public score differs')
    run = phase_run(report['configuration'], 'P2', evaluation, all_four, report_path.relative_to(root),
                    root, baseline, predictions=public_predictions,
                    experiment='local-prompt-suffix-v1')
    resource = report['resource']
    if resource['surface'] != 'lmstudio_sdk' or resource['cost_usd'] is not None:
        raise ValueError('Local suffix resource classification differs')
    run.update({'complete': False, 'pairedEligible': False,
                'resultStatus': 'original DEV-019 outcome unknown; suffix ' + report['terminal']['status'],
                'records': report['saved_rows'], 'attemptedRecords': report['claimed_attempts'],
                'neverSent': report['never_sent_count'],
                'neverSentIds': report['never_sent_ids'],
                'ambiguousOutcomeIds': report['ambiguous_outcome_ids'],
                'statusCounts': {**report['status_counts'], 'ambiguous_no_saved_output': 1},
                'sourceViews': [{'status': 'original saved prefix and unresolved claim', 'records': 18, 'attemptedRecords': 19,
                                 'evidenceUrl': GITHUB + sources['original_output']['file']},
                                {'status': 'terminal suffix', 'records': len(saved) - 18,
                                 'evidenceUrl': GITHUB + sources['suffix_output']['file']}]})
    run['timing'].update({'totalSeconds': resource['elapsed_prediction_seconds_sum'],
                          'medianSeconds': resource['elapsed_prediction_seconds_median'],
                          'p95Seconds': None, 'kind': 'record',
                          'requests': report['saved_rows'], 'complete': False,
                          'comparableHosted': False, 'note': resource['timing_scope']})
    run['tokens'].update({'input': resource['prompt_tokens_observed_sum'],
                          'output': resource['completion_tokens_observed_sum'],
                          'reportedRequests': report['saved_rows'] - len(resource['usage_missing_record_ids']),
                          'totalRequests': report['claimed_attempts'], 'complete': False,
                          'note': 'Saved local SDK usage only; DEV-019 usage is unknown.'})
    run['cost'] = cost_fields({})
    run['cost']['note'] = resource['cost_note']
    return run, cases_for(run['id'], public_predictions, reference_cases)


def local_condition_runs(root, baseline, reference_cases):
    """Export only sealed v2/v3 local conditions with reproducible offline reports."""
    reports_dir = root / 'results/local-prompt-condition-reconciliations-v1'
    if not reports_dir.is_dir():
        return []
    from reconcile_local_prompt_conditions import (load_condition, frozen_requests,
                                                    reconcile_saved_condition)
    from development_benchmark import read_rows
    result = []
    for report_path in sorted(reports_dir.glob('*/P*.json')):
        report = json.loads(report_path.read_text())
        config, variant = report_path.parent.name, report_path.stem
        if (report.get('version') != 'local-prompt-condition-reconciliation-v1' or
            report.get('configuration') != config or report.get('variant') != variant or
            report.get('phase') != 'development' or report.get('denominator') != 60):
            raise ValueError('Unsupported local condition report: ' + str(report_path))
        condition = load_condition(root, config, variant)
        frozen = frozen_requests(root, condition)
        refs = read_rows(root / 'data/pilot/proposed_labels.jsonl')
        pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
        if report != reconcile_saved_condition(root, condition, frozen, refs, pairs):
            raise ValueError('Local condition report differs from terminal-bound offline reconciliation')
        source = report['sources']['development']['output']
        saved = rows(root / source['file'])
        if (len(saved) != report['saved_rows'] or
            report['claimed_attempts'] != len(saved) + len([
                ident for ident in report['unknown_outcome_ids'] if ident not in {row['id'] for row in saved}])):
            raise ValueError('Local condition saved/claimed coverage differs')
        normalized = [{'id': row['id'], 'status': row['decision']['status'],
                       'prediction': row['decision'].get('prediction')} for row in saved]
        saved_ids = {row['id'] for row in normalized}
        public_predictions = normalized + [
            {'id': ident, 'status': 'ambiguous_no_saved_output', 'prediction': None}
            for ident in report['unknown_outcome_ids'] if ident not in saved_ids]
        public_predictions.sort(key=lambda row: row['id'])
        evaluation, all_four = score_saved(public_predictions, root)
        if (evaluation != report['evaluation'] or evaluation['valid_outputs'] != report['valid_outputs'] or
            all_four != report['all_four_correct'] or
            report['never_sent_ids'] != [f'DEV-{i:03}' for i in range(report['claimed_attempts'] + 1, 61)] or
            report['never_sent_count'] != len(report['never_sent_ids'])):
            raise ValueError('Local condition public score or coverage differs')
        run = phase_run(config, variant, evaluation, all_four, report_path.relative_to(root),
                        root, baseline, predictions=public_predictions,
                        experiment='local-prompt-conditions-v1')
        resource = report['resource']
        development = resource['development']
        if resource['surface'] != 'lmstudio_sdk' or resource['cost_usd'] is not None:
            raise ValueError('Local condition resource classification differs')
        run.update({'complete': report['coverage_complete'], 'pairedEligible': False,
                    'resultStatus': 'terminal ' + report['terminal_status'] +
                                    ('; unresolved outcomes' if report['unknown_outcome_ids'] else ''),
                    'records': report['saved_rows'], 'attemptedRecords': report['claimed_attempts'],
                    'neverSent': report['never_sent_count'], 'neverSentIds': report['never_sent_ids'],
                    'ambiguousOutcomeIds': report['unknown_outcome_ids'],
                    'statusCounts': {**report['status_counts'],
                                     **({'ambiguous_no_saved_output': len(public_predictions) - len(saved)}
                                        if len(public_predictions) > len(saved) else {})},
                    'sourceViews': [{'status': 'terminal development evidence', 'records': len(saved),
                                     'evidenceUrl': GITHUB + source['file']}]})
        run['timing'].update({'totalSeconds': development['elapsed_prediction_seconds_sum'] if saved else None,
                              'medianSeconds': development['elapsed_prediction_seconds_median'],
                              'p95Seconds': development['elapsed_prediction_seconds_p95_nearest_rank'],
                              'kind': 'record' if saved else 'unavailable', 'requests': len(saved),
                              'complete': report['coverage_complete'] and not development['elapsed_missing_ids'],
                              'comparableHosted': False,
                              'note': 'Local device prediction time for saved development rows only; diagnostic, not hosted-comparable.'})
        run['tokens'].update({'input': development['prompt_tokens_observed_sum'],
                              'output': development['completion_tokens_observed_sum'],
                              'reportedRequests': len(saved) - len(development['usage_missing_ids']),
                              'totalRequests': report['claimed_attempts'],
                              'complete': report['coverage_complete'] and not development['usage_missing_ids'],
                              'note': 'Saved local SDK development usage only; smoke and unresolved claims excluded.'})
        run['cost'] = cost_fields({})
        run['cost']['note'] = resource['cost_note']
        result.append((run, cases_for(run['id'], public_predictions, reference_cases)))
    return result


def qwen06_sdk_runs(root, baseline, reference_cases):
    """Publish sealed Qwen 0.6B SDK variants from their frozen, scored sources."""
    folder = root / 'results/qwen06-prompt-exact-v1'
    manifest_path = folder / 'manifest.json'
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text())
    conditions = ('thinking-on-P2', 'thinking-on-P1', 'thinking-off-P1', 'thinking-off-P2')
    if manifest.get('version') != 'qwen06-prompt-exact-v1' or manifest.get('conditions') != list(conditions):
        raise ValueError('Unsupported Qwen06 SDK prompt manifest')
    manifest_sha = digest(manifest_path)
    controller_sha = digest(root / 'scripts/qwen06_prompt_execution.cjs')
    preflight_path = folder / 'preflight.json'
    preflight_sha = digest(preflight_path)
    preflight = json.loads(preflight_path.read_text())
    if (manifest.get('controller_sha256') != controller_sha or
        preflight.get('manifest_sha256') != manifest_sha or
        preflight.get('controller_sha256') != controller_sha):
        raise ValueError('Qwen06 SDK frozen controller or preflight mismatch')
    for relative, expected in manifest['source_sha256'].items():
        source = root / relative
        if not source.is_file() or digest(source) != expected:
            raise ValueError('Qwen06 SDK frozen source mismatch: ' + relative)
    expected_ids = [f'DEV-{index:03}' for index in range(1, 61)]
    if manifest['record_ids'] != expected_ids:
        raise ValueError('Qwen06 SDK canonical record IDs differ')
    result = []
    for name in conditions:
        condition_folder = folder / name
        terminal_path = condition_folder / 'development.terminal.json'
        if not terminal_path.is_file():
            continue  # An open or unstarted condition has no public development score.
        terminal = json.loads(terminal_path.read_text())
        if (terminal.get('condition') != name or terminal.get('phase') != 'development' or
            terminal.get('status') != 'completed' or terminal.get('ambiguous_timeout') is not False or
            any(terminal.get(key) != 60 for key in ('requested_records','claimed_attempts',
                                                  'finished_attempts','saved_rows')) or
            terminal.get('manifest_sha256') != manifest_sha or
            terminal.get('preflight_sha256') != preflight_sha or
            terminal.get('controller_sha256') != controller_sha):
            raise ValueError('Qwen06 SDK development terminal is not complete and bound: ' + name)
        output_path = condition_folder / 'development.jsonl'
        journal_path = condition_folder / 'development.attempts.jsonl'
        evaluation_path = condition_folder / 'development-evaluation.json'
        output_sha, journal_sha = digest(output_path), digest(journal_path)
        if terminal['output_sha256'] != output_sha or terminal['journal_sha256'] != journal_sha:
            raise ValueError('Qwen06 SDK terminal output or journal hash mismatch: ' + name)
        evaluation = json.loads(evaluation_path.read_text())
        if (evaluation.get('version') != 'qwen06-prompt-development-evaluation-v1' or
            evaluation.get('condition') != name or evaluation.get('terminal_status') != 'completed' or
            evaluation.get('reference_labels_read_offline_after_inference') is not True or
            evaluation.get('reference_labels_sent_to_model') is not False):
            raise ValueError('Qwen06 SDK offline evaluation metadata mismatch: ' + name)
        required_sources = {'development.jsonl','development.attempts.jsonl','development.terminal.json',
                            'data/pilot/proposed_labels.jsonl','data/pilot/pairs.json',
                            'scripts/development_benchmark.py'}
        if not required_sources <= set(evaluation['source_sha256']):
            raise ValueError('Qwen06 SDK offline evaluation lacks source bindings: ' + name)
        for relative, expected in evaluation['source_sha256'].items():
            source = condition_folder / relative if '/' not in relative else root / relative
            if not source.is_file() or digest(source) != expected:
                raise ValueError('Qwen06 SDK evaluation source mismatch: ' + relative)
        raw_lines = [line for line in output_path.read_bytes().splitlines() if line.strip()]
        saved = [json.loads(line) for line in raw_lines]
        journal = rows(journal_path)
        if len(saved) != 60 or len(journal) != 120 or [row['id'] for row in saved] != expected_ids:
            raise ValueError('Qwen06 SDK saved coverage or journal length mismatch: ' + name)
        normalized = []
        for index, (row, raw) in enumerate(zip(saved, raw_lines)):
            started, finished = journal[2*index:2*index+2]
            request_sha = hashlib.sha256(json.dumps(row['request'], ensure_ascii=False,
                                                  separators=(',', ':')).encode()).hexdigest()
            if (row.get('condition') != name or row.get('phase') != 'development' or
                row.get('manifest_sha256') != manifest_sha or row.get('preflight_sha256') != preflight_sha or
                row.get('controller_sha256') != controller_sha or row.get('reference_labels_read') is not False or
                row.get('model_identifier') != manifest['model']['identifier'] or
                row.get('model_path') != manifest['model']['path'] or
                row.get('runtime_attestation') != terminal['runtime_attestation'] or
                row['runtime_attestation'].get('selected_engine') != manifest['runtime']['selected_engine'] or
                row.get('request_sha256') != request_sha or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                any(event.get('id') != row['id'] or event.get('attempt_id') != row['attempt_id']
                    for event in (started, finished)) or
                started.get('request_sha256') != request_sha or
                finished.get('status') != row['decision']['status'] or
                finished.get('output_sha256') != hashlib.sha256(raw).hexdigest()):
                raise ValueError('Qwen06 SDK row and attempt journal mismatch: ' + name)
            normalized.append({'id': row['id'], 'status': row['decision']['status'],
                               'prediction': row['decision'].get('prediction')})
        checked, all_four = score_saved(normalized, root)
        invalid = [row['id'] for row in normalized if row['status'] != 'ok']
        if (checked != evaluation['score'] or all_four != evaluation['all_four_correct'] or
            evaluation['records'] != 60 or evaluation['valid_outputs'] != checked['valid_outputs'] or
            evaluation['invalid_output_ids'] != invalid or
            terminal['ok_rows'] != checked['valid_outputs'] or
            terminal['invalid_output_rows'] != len(invalid) or
            any(evaluation['per_field_correct'][key] != checked['metrics'][key]['correct'] for key in FIELDS)):
            raise ValueError('Qwen06 SDK offline score differs from saved evidence: ' + name)
        parent = 'qwen3-0.6b-sdk-thinking-' + ('on' if 'thinking-on' in name else 'off')
        variant = name[-2:]
        if parent not in baseline:
            raise ValueError('Qwen06 SDK baseline is missing: ' + parent)
        run = phase_run(parent, variant, checked, all_four, output_path.relative_to(root), root,
                        baseline, predictions=normalized, experiment='qwen06-prompt-exact-v1')
        elapsed = [number(row.get('elapsed_seconds')) for row in saved]
        prompt_tokens = [number((row.get('stats') or {}).get('promptTokensCount')) for row in saved]
        output_tokens = [number((row.get('stats') or {}).get('predictedTokensCount')) for row in saved]
        if (None in elapsed or None in prompt_tokens or None in output_tokens or
            abs(sum(elapsed) - evaluation['sum_record_elapsed_seconds']) > 1e-6 or
            sum(prompt_tokens) != evaluation['total_prompt_tokens'] or
            sum(output_tokens) != evaluation['total_predicted_tokens']):
            raise ValueError('Qwen06 SDK resource totals differ: ' + name)
        run['timing'].update({'totalSeconds': sum(elapsed), 'medianSeconds': statistics.median(elapsed),
                              'p95Seconds': sorted(elapsed)[math.ceil(.95*60)-1], 'requests': 60,
                              'complete': True, 'comparableHosted': False,
                              'note': 'Local device prediction time; diagnostic, not hosted-comparable.'})
        run['tokens'].update({'input': sum(prompt_tokens), 'output': sum(output_tokens),
                              'reportedRequests': 60, 'totalRequests': 60, 'complete': True})
        run['cost']['note'] = 'Local execution; no provider bill. Device costs unmeasured.'
        run['resultStatus'] = 'terminal completed; intrinsic invalid outputs retained'
        result.append((run, cases_for(run['id'], normalized, reference_cases)))
    return result


def amended_roster(root, entries, runs):
    """Apply a documented future-local disposition without changing the frozen roster."""
    path = root / PHASE / 'roster-amendment-hosted-first-v1.json'
    if not path.is_file():
        return entries
    amendment = json.loads(path.read_text())
    frozen_path = root / PHASE / 'roster.json'
    if (amendment.get('version') != 'prompt-roster-hosted-first-amendment-v1' or
        amendment.get('frozen_roster_file') != str(PHASE / 'roster.json') or
        amendment.get('frozen_roster_sha256') != digest(frozen_path)):
        raise ValueError('Hosted-first roster amendment is not bound to frozen roster')
    expected = {'qwen3-8b-sdk-thinking-on':'openrouter-qwen3-8b-on-json-object-p0',
                'qwen3-8b-sdk-thinking-off':'openrouter-qwen3-8b-off-json-object-p0',
                'qwen3.8-27b-sdk-thinking-low':'openrouter-qwen27-low-darkbloom-fp4'}
    changes = amendment['changes']
    if {item['local_configuration_id']: item['hosted_configuration_id'] for item in changes} != expected or len(changes) != 3:
        raise ValueError('Hosted-first amendment does not name the exact separate configurations')
    by_id = {item['id']: item for item in entries}
    run_ids = {item['id'] for item in runs}
    for change in changes:
        local, hosted = change['local_configuration_id'], change['hosted_configuration_id']
        if (change['conditions'] != ['P1','P2'] or change['disposition'] != 'excluded' or
            local not in by_id or by_id[local]['state'] != 'scheduled' or
            not all(hosted + suffix in run_ids for suffix in ('','--p1','--p2')) or
            not all((root / source).is_file() for source in change['hosted_evidence'])):
            raise ValueError('Hosted-first amendment evidence or original state mismatch: ' + local)
        by_id[local] = {**by_id[local], 'state':'excluded',
                        'reason':'Future local prompt requests excluded under hosted-first direction. '
                                 'The separate hosted configuration is not runtime or quantization equivalent.',
                        'hosted_configuration_id': hosted}
    return list(by_id.values())


def local_pair_reports(root, runs, reference_cases):
    """Admit audited local prompt comparisons without inferring eligibility from coverage."""
    directory = root / 'results/local-prompt-pairs-v1'
    if not directory.is_dir():
        return []
    from evaluate_local_prompt_pairs_v1 import evaluate
    by_run = {run['id']: run for run in runs}
    result = []
    for report_path in sorted(directory.glob('*.json')):
        report = json.loads(report_path.read_text())
        config = report_path.stem
        if (report.get('version') != 'local-prompt-pairs-v1' or
            report.get('configuration') != config or
            report.get('eligible_paired_comparison') is not True or
            report.get('controls_verified') is not True or
            report.get('denominator') != 60 or
            set(report.get('conditions', {})) != {'P0', 'P1', 'P2'} or
            set(report.get('comparisons', {})) != {'P0_to_P1', 'P0_to_P2', 'P1_to_P2'} or
            not report.get('historical_p0_limitation')):
            raise ValueError('Unsupported local prompt pair report: ' + str(report_path))
        if report != evaluate(root, config):
            raise ValueError('Local prompt pair report differs from offline evidence audit')
        conditions = {}
        matching = {}
        for condition in ('P0', 'P1', 'P2'):
            run_id = config if condition == 'P0' else config + '--' + condition.lower()
            run = by_run.get(run_id)
            if run is None or run['condition'] != condition or not run['complete']:
                raise ValueError('Audited local pair has no matching complete public run')
            value = report['conditions'][condition]
            binding = (value['sources']['output'] if condition == 'P0' else
                       value['sources']['development']['output'])
            source_file = root / binding['file']
            if hashlib.sha256(source_file.read_bytes()).hexdigest() != binding['sha256']:
                raise ValueError('Local pair source hash mismatch')
            saved = rows(source_file)
            predictions = saved if condition == 'P0' else [
                {'id': row['id'], 'status': row['decision']['status'],
                 'prediction': row['decision'].get('prediction')} for row in saved]
            evaluation, all_four = score_saved(predictions, root)
            if (evaluation != value['evaluation'] or run['valid'] != evaluation['valid_outputs'] or
                any(run['metrics'][field] != evaluation['metrics'][field]['correct'] for field in FIELDS) or
                run['metrics']['all_four'] != all_four):
                raise ValueError('Audited local pair differs from public condition score')
            conditions[condition] = {'valid': evaluation['valid_outputs'], **metric(evaluation, all_four)}
            matching[condition] = run
        comparisons = {}
        for name, comparison in report['comparisons'].items():
            cases = []
            for case in comparison['cases']:
                reference = reference_cases.get(case['id'])
                if reference is None or reference['reference'] != case['reference']:
                    raise ValueError('Local pair changed case differs from public reference')
                cases.append({**{key: case[key] for key in
                                  ('id', 'from_state', 'to_state', 'from_prediction',
                                   'to_prediction', 'reference')},
                              'feedback': reference['feedback']})
            comparisons[name] = {'bothValid': comparison['both_valid'],
                                 'changedRecordCount': comparison['changed_record_count'],
                                 'allFourWrongToCorrect': comparison['all_four_wrong_to_correct'],
                                 'allFourCorrectToWrong': comparison['all_four_correct_to_wrong'],
                                 'cases': cases}
        for run in matching.values():
            run['pairedEligible'] = True
            run['comparisonLimitation'] = report['historical_p0_limitation']
            run['resultStatus'] = (run.get('resultStatus') or 'complete') + '; ' + report['historical_p0_limitation']
        result.append({'id': config, 'model': matching['P0']['model'], 'eligible': True,
                       'conditions': conditions, 'comparisons': comparisons,
                       'sourceStatus': 'hash-verified saved report',
                       'protocol': report['protocol'],
                       'historicalP0Limitation': report['historical_p0_limitation'],
                       'referenceStatus': report['reference_status'],
                       'evidenceUrl': GITHUB + str(report_path.relative_to(root))})
    return result


def export(root=ROOT):
    root = Path(root)
    summary = json.loads((root / 'results/comparison/summary.json').read_text())
    baseline = {}
    runs = []
    for config in summary:
        evaluation = config.get('evaluation')
        if not evaluation:
            continue
        timing = config.get('timing') or {}
        batch = timing.get('workflow') == 'batch'
        kind = 'batch' if batch else 'record' if timing.get('timed_records') else 'unavailable'
        timing_complete = timing.get('all_attempt_timing_complete', batch)
        cost = config.get('cost') or {}
        ident = config['id']
        run = {
            'id': ident, 'experimentId': ident, 'protocolId': 'baseline-v1', 'parentBaselineId': None,
            'model': config.get('model', ident), 'effort': config.get('effort') or 'not applicable',
            'surface': surface(config), 'condition': 'P0',
            'complete': config.get('prediction_records') == 60 and 'partial' not in config.get('status', '') and not config.get('status', '').startswith(('blocked', 'stopped')),
            'resultStatus': config.get('status', 'unknown'), 'pairedEligible': False,
            'records': config.get('prediction_records', 0), 'valid': evaluation['valid_outputs'],
            'metrics': metric(evaluation, config['exact_match']),
            'timing': {'totalSeconds': timing.get('sum_batch_request_seconds' if batch else 'sum_record_seconds') if timing_complete else None,
                       'medianSeconds': timing.get('batch_median_seconds' if batch else 'median_seconds') if timing_complete else None,
                       'p95Seconds': timing.get('batch_p95_nearest_rank_seconds' if batch else 'p95_nearest_rank_seconds') if timing_complete else None,
                       'kind': kind, 'requests': timing.get('batch_requests') if batch else timing.get('timed_records'),
                       'complete': bool(timing_complete), 'comparableHosted': surface(config) != 'Local / specialist' and not batch,
                       'note': ('Batch wall time is for the batch, never individual-record latency. ' if batch else 'Local timing is diagnostic and not hosted-comparable. ' if surface(config) == 'Local / specialist' else '') + timing.get('note', 'Timing unavailable.')},
            'tokens': tokens(config, root), 'cost': cost_fields(cost),
            'evidenceUrl': GITHUB + config['predictions_file'],
        }
        if ident == 'typesafe-jev113-v2':
            attempts = [row for path in config['attempt_files'] for row in rows(root / path)]
            elapsed = [number(row.get('elapsed_seconds')) for row in attempts]
            elapsed = [v for v in elapsed if v is not None]
            estimates = [Decimal(str(row['estimated_usage_cost_usd'])) for row in attempts if row.get('estimated_usage_cost_usd') is not None]
            run['timing'].update({'totalSeconds': sum(elapsed) if len(elapsed) == len(attempts) else None,
                                  'medianSeconds': statistics.median(elapsed) if len(elapsed) == len(attempts) else None,
                                  'medianReconciledRecordSeconds': timing.get('median_seconds'),
                                  'p95Seconds': sorted(elapsed)[math.ceil(.95 * len(elapsed))-1] if len(elapsed) == len(attempts) else None,
                                  'requests': len(attempts), 'complete': len(elapsed) == len(attempts), 'comparableHosted': True,
                                  'note': '61 development attempts including the retained failed transport attempt (30.7416 s). The separate reconciled-record median covers 60 valid final records. No smoke time included.'})
            run['cost']['estimatedUsd'] = float(sum(estimates)) if len(estimates) == len(attempts)-1 else None
            run['cost']['note'] = 'Usage-price estimate for development attempts with usage; provider actual charge unavailable. Excludes separate smoke estimate ($0.000294294). One failed transport attempt has unknown charge.'
            smoke = rows(root / 'results/openjev/typesafe-smoke-v2.jsonl')
            run['smokeEstimatedUsd'] = float(sum(Decimal(str(row['estimated_usage_cost_usd'])) for row in smoke))
        runs.append(run)
        baseline[ident] = run

    all_cases = json.loads((root / 'results/comparison/cases.json').read_text())
    allowed = set(baseline)
    cases = [{key: c[key] for key in ('configuration', 'id', 'feedback', 'reference', 'prediction', 'status', 'different_fields')}
             for c in all_cases if c['configuration'] in allowed]
    reference_cases = {c['id']: c for c in all_cases if c['configuration'] == all_cases[0]['configuration']}
    # The Haiku batch P0 has a saved 60-record evaluation but was not in the
    # central summary or a completed paired report.
    haiku_parent = 'haiku45-not_applicable-phase2-batch10-p0'
    haiku_folder = root / 'results/subscription-batch-p0-2026-09-23' / haiku_parent
    haiku_path = haiku_folder / 'development.jsonl'
    haiku_predictions = rows(haiku_path)
    haiku_evaluation = json.loads((haiku_folder / 'evaluation.json').read_text())
    haiku_checked, haiku_four = score_saved(haiku_predictions, root)
    if len(haiku_predictions) != 60 or haiku_checked['valid_outputs'] != haiku_evaluation['valid_outputs'] or any(haiku_checked['metrics'][key]['correct'] != haiku_evaluation['metrics'][key]['correct'] for key in FIELDS):
        raise ValueError('Haiku batch P0 score mismatch')
    haiku_run = phase_run(haiku_parent, 'P0', haiku_evaluation, haiku_four, haiku_path.relative_to(root), root,
                          baseline, predictions=haiku_predictions, experiment='subscription-batch-p0-v1')
    haiku_run.update({'id': haiku_parent, 'parentBaselineId': None,
                      'model': haiku_predictions[0]['requested_model'], 'effort': haiku_predictions[0]['effort'],
                      'surface': 'Claude subscription'})
    baseline[haiku_parent] = haiku_run
    runs.append(haiku_run)
    cases.extend(cases_for(haiku_parent, haiku_predictions, reference_cases))

    phase_dir = root / PHASE
    reports = {}
    pairs = []
    for path in sorted((phase_dir / 'paired-reports').glob('*/evaluation.json')):
        report = json.loads(path.read_text())
        for value in report['conditions'].values():
            for kind in ('predictions', 'request_evidence'):
                binding = value['evidence'].get(kind)
                if binding:
                    source_file = root / binding['file']
                    if not source_file.is_file() or hashlib.sha256(source_file.read_bytes()).hexdigest() != binding['sha256']:
                        raise ValueError('Paired report source hash mismatch: ' + str(path))
        parent = report['parent_baseline_id']
        reports[parent] = report
        conditions = {}
        for condition, value in report['conditions'].items():
            conditions[condition] = {'valid': value['evaluation']['valid_outputs'], **metric(value['evaluation'], value['all_four_correct'])}
            if condition == 'P0':
                if parent in baseline:
                    baseline[parent]['pairedEligible'] = bool(report.get('eligible_paired_comparison'))
                else:
                    source = value['evidence']['predictions']['file']
                    predictions = rows(root / source)
                    run = phase_run(parent, 'P0', value['evaluation'], value['all_four_correct'], Path(source), root, baseline,
                                    telemetry=value.get('telemetry'), cost=value.get('cost'), predictions=predictions,
                                    paired=report.get('eligible_paired_comparison') is True)
                    run.update({'id': parent, 'model': predictions[0].get('requested_model', parent),
                                'effort': predictions[0].get('effort', 'not applicable'),
                                'surface': surface({'id': parent, 'model': predictions[0].get('requested_model', '')}),
                                'parentBaselineId': None})
                    baseline[parent] = run
                    runs.append(run)
                    cases.extend(cases_for(parent, predictions, reference_cases))
                continue
            if condition not in ('P1', 'P2'):
                continue
            source = value['evidence']['predictions']['file']
            predictions = rows(root / source)
            run = phase_run(parent, condition, value['evaluation'], value['all_four_correct'], Path(source), root, baseline,
                            telemetry=value.get('telemetry'), cost=value.get('cost'), predictions=predictions,
                            paired=report.get('eligible_paired_comparison') is True)
            runs.append(run)
            cases.extend(cases_for(run['id'], predictions, reference_cases))
        comparisons = {}
        if report.get('eligible_paired_comparison') is True:
            for name, comparison in report['comparisons'].items():
                comparisons[name] = {'bothValid': comparison.get('both_valid'),
                                     'changedRecordCount': comparison.get('changed_record_count'),
                                     'allFourWrongToCorrect': comparison.get('all_four_wrong_to_correct'),
                                     'allFourCorrectToWrong': comparison.get('all_four_correct_to_wrong'),
                                     'cases': [{k: case[k] for k in ('id', 'from_state', 'to_state', 'from_prediction', 'to_prediction', 'reference', 'feedback')} for case in comparison.get('cases', [])]}
        pairs.append({'id': parent, 'model': baseline.get(parent, {}).get('model', parent),
                      'eligible': report.get('eligible_paired_comparison') is True, 'conditions': conditions,
                      'comparisons': comparisons, 'sourceStatus': 'hash-verified saved report',
                      'evidenceUrl': GITHUB + str(path.relative_to(root))})

    present = {run['id'] for run in runs}
    for path in sorted((phase_dir / 'runs').glob('*/P*/development.jsonl')):
        condition = path.parent.name
        parent = path.parent.parent.name
        ident = parent + '--' + condition.lower()
        if ident in present or condition not in ('P1', 'P2'):
            continue
        evaluation_path = path.parent / 'evaluation.json'
        if not evaluation_path.is_file() and not (path.parent / 'completion-sidecar.json').is_file() and not closed_journal(path):
            continue
        predictions = rows(path)
        if not predictions:
            continue
        if evaluation_path.is_file():
            evaluation = json.loads(evaluation_path.read_text())
            _, all_four = score_saved(predictions, root)
        else:
            evaluation, all_four = score_saved(predictions, root)
        relative = path.relative_to(root)
        run = phase_run(parent, condition, evaluation, all_four, relative, root, baseline, predictions=predictions)
        runs.append(run)
        cases.extend(cases_for(ident, predictions, reference_cases))
        present.add(ident)

    from build_native_prompt_summary import export as native_export
    native = native_export(root)
    native = {key: native[key] for key in ('denominator', 'strictPairedComparisonEligible', 'referenceNote', 'limitations', 'conditions')}
    for row in native['conditions']:
        ident = row['id'] if row['condition'] == 'P0' else row['id'] + '--' + row['condition'].lower()
        if ident in present or (row['condition'] == 'P0' and ident in baseline):
            continue
        run = phase_run(row['id'], row['condition'],
                        {'valid_outputs': row['valid'], 'metrics': {key: {'correct': row['correct'][key]} for key in FIELDS}},
                        row['correct']['all_four'], None, root, baseline, experiment='native-descriptive-v1',
                        status='descriptive')
        run.update({'id': ident, 'complete': row['saved'] == 60, 'records': row['saved'],
                    'metrics': row['correct'], 'evidenceUrl': GITHUB + row['sourceBindings'][0]['file']})
        runs.append(run)
        native_predictions = []
        for binding in row['sourceBindings']:
            source_file = root / binding['file']
            if hashlib.sha256(source_file.read_bytes()).hexdigest() != binding['sha256']:
                raise ValueError('Native source hash mismatch: ' + binding['file'])
            native_predictions.extend(rows(source_file))
        cases.extend(cases_for(ident, native_predictions, reference_cases))
        present.add(ident)

    # Local exact-prompt evaluations are closed and carry a hash of the raw
    # development output. Preserve intrinsic invalid rows as completed attempts.
    for evaluation_path in sorted((root / 'results/local-prompt-exact-v1').glob('*/P*/offline-evaluation.json')):
        item = json.loads(evaluation_path.read_text())
        source_path = evaluation_path.parent / 'development.jsonl'
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != item['source_sha256']['development_output']:
            raise ValueError('Local prompt evaluation source hash mismatch: ' + str(evaluation_path))
        predictions = rows(source_path)
        if len(predictions) != item['coverage']['saved_rows']:
            raise ValueError('Local prompt evaluation coverage mismatch: ' + str(evaluation_path))
        for name, digest in (('development.terminal.json', item['source_sha256']['development_terminal']),
                             ('development.attempts.jsonl', item['source_sha256']['development_journal'])):
            bound = evaluation_path.parent / name
            if hashlib.sha256(bound.read_bytes()).hexdigest() != digest:
                raise ValueError('Local closed-source hash mismatch: ' + str(bound))
        normalized_predictions = [{'id': row['id'], 'status': row.get('decision', {}).get('status'),
                                   'prediction': row.get('decision', {}).get('prediction')} for row in predictions]
        checked_score, checked_four = score_saved(normalized_predictions, root)
        if checked_score['valid_outputs'] != item['score']['valid_outputs'] or checked_four != item['coverage']['all_four_correct'] or any(checked_score['metrics'][key]['correct'] != item['score']['metrics'][key]['correct'] for key in FIELDS):
            raise ValueError('Local offline score mismatch: ' + str(evaluation_path))
        parent, condition = item['configuration'], item['variant']
        relative = source_path.relative_to(root)
        run = phase_run(parent, condition, item['score'], item['coverage']['all_four_correct'], relative,
                        root, baseline, predictions=predictions, experiment='local-prompt-exact-v1')
        resource = item['resource']
        run['timing'].update({'totalSeconds': resource['elapsed_prediction_seconds_sum'],
                              'medianSeconds': resource['elapsed_prediction_seconds_median'],
                              'p95Seconds': resource['elapsed_prediction_seconds_p95_nearest_rank'],
                              'requests': len(predictions), 'complete': True, 'comparableHosted': False,
                              'note': 'Local device prediction time; diagnostic, not hosted-comparable.'})
        run['tokens'].update({'input': resource['prompt_tokens_observed_sum'],
                              'output': resource['completion_tokens_observed_sum'],
                              'reportedRequests': len(predictions) - len(resource['usage_missing_record_ids']),
                              'totalRequests': len(predictions),
                              'complete': not resource['usage_missing_record_ids']})
        run['cost']['note'] = 'Local execution; API charge not applicable. Device costs unmeasured.'
        runs.append(run)
        cases.extend(cases_for(run['id'], normalized_predictions, reference_cases))

    local_suffix = local_suffix_run(root, baseline, reference_cases)
    if local_suffix is not None:
        run, local_cases = local_suffix
        if run['id'] in {item['id'] for item in runs}:
            raise ValueError('Local suffix duplicates an existing public run')
        runs.append(run)
        cases.extend(local_cases)

    for run, local_cases in local_condition_runs(root, baseline, reference_cases):
        if run['id'] in {item['id'] for item in runs}:
            raise ValueError('Local condition duplicates an existing public run')
        runs.append(run)
        cases.extend(local_cases)

    for run, local_cases in qwen06_sdk_runs(root, baseline, reference_cases):
        if run['id'] in {item['id'] for item in runs}:
            raise ValueError('Qwen06 SDK condition duplicates an existing public run')
        runs.append(run)
        cases.extend(local_cases)

    # Original Qwen3.6 P0 baselines were completed before the bounded prompt
    # recovery and are separate evidence from its P1/P2 runs.
    for mode in ('on', 'off'):
        parent = 'openrouter-paid-qwen36-35b-a3b-' + mode
        if parent in baseline:
            continue
        folder = root / ('results/openrouter-qwen35-' + mode + '-2026-09-23')
        path = folder / 'development.jsonl'
        predictions = rows(path)
        evaluation = json.loads((folder / 'evaluation.json').read_text())
        checked, all_four = score_saved(predictions, root)
        if len(predictions) != 60 or checked['valid_outputs'] != evaluation['valid_outputs'] or any(checked['metrics'][key]['correct'] != evaluation['metrics'][key]['correct'] for key in FIELDS):
            raise ValueError('Qwen36 P0 score mismatch: ' + mode)
        run = phase_run(parent, 'P0', evaluation, all_four, path.relative_to(root), root,
                        baseline, predictions=predictions, experiment='qwen36-original-p0-v1')
        run.update({'id': parent, 'parentBaselineId': None, 'model': predictions[0]['requested_model'],
                    'effort': mode, 'surface': 'OpenRouter'})
        observed = [Decimal(str(row['observed_cost_usd'])) for row in predictions if row.get('observed_cost_usd') is not None]
        run['cost'].update({'actualUsd': float(sum(observed)) if len(observed) == len(predictions) else None,
                            'knownUsd': float(sum(observed)) if observed else None,
                            'availability': 'complete' if len(observed) == len(predictions) else 'partial'})
        runs.append(run)
        cases.extend(cases_for(parent, predictions, reference_cases))
        baseline[parent] = run

    # Closed, hash-scored Qwen3.5 35B recovery results are descriptive: the
    # original P0/P1/P2 protocol did not complete as a paired comparison.
    qwen36_dir = root / 'results/qwen36-prompt-recovery-v1'
    qwen36_score = json.loads((qwen36_dir / 'full60-offline-score-v1.json').read_text())
    for key, result in qwen36_score['conditions'].items():
        mode, variant = key.split('-')
        parent = 'openrouter-paid-qwen36-35b-a3b-' + mode
        path = qwen36_dir / (key + '-development.jsonl')
        if not path.is_file() or not closed_journal(path):
            continue
        predictions = rows(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != result['result_sha256'] or len(predictions) != result['attempted_records']:
            raise ValueError('Qwen36 score source mismatch: ' + key)
        relative = path.relative_to(root)
        observed = Decimal(result['known_observed_cost_usd'])
        unknown = Decimal(result['unknown_reserved_upper_bound_usd'])
        run = phase_run(parent, variant.upper(), result['evaluation'], result['all_four_correct'], relative, root,
                        baseline, predictions=predictions, experiment='qwen36-recovery-v1', status=result['terminal']['terminal_status'])
        run['model'] = predictions[0].get('requested_model', parent)
        run['effort'] = mode
        run['cost'].update({'actualUsd': float(observed) if not unknown else None,
                            'knownUsd': float(observed), 'unknownUpperBoundUsd': str(unknown),
                            'availability': 'complete' if not unknown else 'partial',
                            'note': 'Known observed development charges only. Unknown service-error reserve is not actual spending; smoke excluded.'})
        runs.append(run)
        cases.extend(cases_for(run['id'], predictions, reference_cases))

    # Only terminal Qwen3 8B condition files are admitted. An active partial
    # file has no terminal event and is deliberately absent from this snapshot.
    qwen8_dir = root / 'results/qwen8-hosted-prompt-full60-prep-v1'
    for path in sorted(qwen8_dir.glob('*-full60-results.jsonl')):
        if not closed_journal(path):
            continue
        predictions = rows(path)
        if not predictions:
            continue
        parent = predictions[0].get('parent_baseline_id')
        variant = predictions[0].get('prompt_variant')
        condition = variant.get('variant') if isinstance(variant, dict) else variant
        if not parent or condition not in ('P1', 'P2'):
            continue
        evaluation, all_four = score_saved(predictions, root)
        relative = path.relative_to(root)
        run = phase_run(parent, condition, evaluation, all_four, relative, root, baseline,
                        predictions=predictions, experiment='qwen8-hosted-recovery-v1')
        observed = [Decimal(str(r['observed_cost_usd'])) for r in predictions if r.get('observed_cost_usd') is not None]
        unknown = [r for r in predictions if r.get('cost_unknown')]
        run['cost'].update({'actualUsd': float(sum(observed)) if len(observed) == len(predictions) and not unknown else None,
                            'knownUsd': float(sum(observed)) if observed else None,
                            'availability': 'complete' if len(observed) == len(predictions) and not unknown else 'partial',
                            'note': 'Observed development charges from the terminal result file; smoke excluded.'})
        runs.append(run)
        cases.extend(cases_for(run['id'], predictions, reference_cases))

    def replace_with_reconciliation(run, predictions, evidence_sources):
        previous = next((old for old in runs if old['id'] == run['id']), None)
        if previous:
            run['sourceViews'] = previous.get('sourceViews', []) + [{'status': 'prior saved view', 'records': previous['records'],
                                   'valid': previous['valid'], 'evidenceUrl': previous['evidenceUrl']}]
            runs.remove(previous)
            cases[:] = [case for case in cases if case['configuration'] != run['id']]
        run['evidenceSources'] = [GITHUB + str(path) for path in evidence_sources]
        run['complete'] = len(predictions) == 60
        run['resultStatus'] = 'reconciled complete' if len(predictions) == 60 else 'reconciled partial'
        run['pairedEligible'] = False
        runs.append(run)
        cases.extend(cases_for(run['id'], predictions, reference_cases))

    # A frozen final-ten reconciliation gives disjoint saved IDs for each
    # hosted lane. Replace the earlier partial view, retaining its provenance.
    final_ten = json.loads((root / 'results/hosted-unattempted-continuation-v4/final-ten/summary.json').read_text())
    if final_ten['contract'] != 'hosted-final-ten-aggregate-v1' or final_ten['status'] != 'ALL_TEN_CANONICAL_60_RECONCILED':
        raise ValueError('Unsupported hosted final-ten reconciliation')
    for lane in final_ten['lanes']:
        score_binding = lane['score']
        score_path = root / score_binding['file']
        if hashlib.sha256(score_path.read_bytes()).hexdigest() != score_binding['sha256']:
            raise ValueError('Hosted final-ten score hash mismatch: ' + str(score_path))
        score_report = json.loads(score_path.read_text())
        predictions = []
        source_paths = []
        for binding in lane['source_files']:
            path = root / binding['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != binding['sha256']:
                raise ValueError('Hosted final-ten source hash mismatch: ' + str(path))
            if path.suffix == '.jsonl':
                predictions.extend(rows(path))
                source_paths.append(Path(binding['file']))
        evaluation, all_four = score_saved(predictions, root)
        if len(predictions) != lane['attempted'] or evaluation['valid_outputs'] != lane['valid_outputs'] or all_four != lane['all_four_correct'] or any(evaluation['metrics'][key]['correct'] != score_report['score']['metrics'][key]['correct'] for key in FIELDS):
            raise ValueError('Hosted final-ten reconciliation mismatch: ' + lane['configuration_id'])
        source_parent, condition = lane['configuration_id'], lane['condition']
        # The addendum is a recovery folder, not a new baseline configuration.
        parent = 'openrouter-qwen27-low-darkbloom-fp4' if source_parent == 'qwen27-low-hosted-addendum-v1' else source_parent
        run = phase_run(parent, condition, evaluation, all_four, Path(score_binding['file']), root,
                        baseline, predictions=predictions, experiment='hosted-final-ten-v1')
        run['surface'] = 'OpenRouter'
        run['model'] = predictions[0].get('requested_model', run['model'])
        if source_parent != parent:
            run['sourceConfigurationId'] = source_parent
        run['timing']['comparableHosted'] = run['timing']['kind'] != 'batch'
        run['tokens'] = tokens({'attempt_files': [str(path) for path in source_paths]}, root)
        costs = [Decimal(str(row['observed_cost_usd'])) for row in predictions if row.get('observed_cost_usd') is not None]
        unknown = [Decimal(str(row.get('reserved_cost_usd') or 0)) for row in predictions if row.get('cost_unknown')]
        run['cost'].update({'actualUsd': float(sum(costs)) if len(costs) == len(predictions) and not unknown else None,
                            'knownUsd': float(sum(costs)) if costs else None,
                            'unknownUpperBoundUsd': str(sum(unknown)) if unknown else None,
                            'availability': 'complete' if len(costs) == len(predictions) and not unknown else 'partial',
                            'note': 'Known observed charges across hash-bound disjoint original and continuation attempts; unresolved charges are bounds, not spending.'})
        replace_with_reconciliation(run, predictions, source_paths)

    # Subscription suffix reconciliations preserve ten originally attempted,
    # ambiguous records and fill only never-sent IDs. No failed row is retried.
    for index_path in (phase_dir / 'subscription-suffix-continuation-v1/reconciliation-v1/index.json',
                       phase_dir / 'subscription-suffix-continuation-v2-haiku/reconciliation-v1/index.json'):
        suffix_index = json.loads(index_path.read_text())
        if suffix_index['contract'] != 'subscription-suffix-reconciliation-index-v1':
            raise ValueError('Unsupported subscription suffix reconciliation')
        for entry in suffix_index['conditions']:
            binding = entry['report']
            report_path = root / binding['file']
            if hashlib.sha256(report_path.read_bytes()).hexdigest() != binding['sha256']:
                raise ValueError('Subscription suffix report hash mismatch: ' + str(report_path))
            report = json.loads(report_path.read_text())
            source_paths = []
            for name, source in report['source_bindings'].items():
                path = root / source['file']
                if hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
                    raise ValueError('Subscription suffix source hash mismatch: ' + str(path))
                if name in ('original_output', 'suffix_output'):
                    source_paths.append(Path(source['file']))
            predictions = report['rows']
            evaluation, all_four = score_saved(predictions, root)
            if len(predictions) != 60 or evaluation['valid_outputs'] != entry['valid_prediction_count'] or report['counts']['never_sent'] != entry['never_sent_count']:
                raise ValueError('Subscription suffix score mismatch: ' + report['configuration_id'])
            parent, condition = report['configuration_id'], report['condition']
            run = phase_run(parent, condition, evaluation, all_four, Path(binding['file']), root,
                            baseline, predictions=predictions, experiment='subscription-suffix-v1')
            batches = report['batch_timing']['original'] + report['batch_timing']['suffix']
            seconds = [number(batch.get('elapsed_seconds')) for batch in batches]
            run['timing'].update({'totalSeconds': sum(seconds) if all(v is not None for v in seconds) else None,
                                  'medianSeconds': statistics.median(seconds) if all(v is not None for v in seconds) else None,
                                  'p95Seconds': sorted(seconds)[math.ceil(.95 * len(seconds))-1] if all(v is not None for v in seconds) else None,
                                  'kind': 'batch', 'requests': len(batches), 'complete': all(v is not None for v in seconds),
                                  'comparableHosted': False,
                                  'note': 'Six sequential batch attempts; original failed batch retained. Batch latency is not individual-record latency, and original alternating timing was not preserved.'})
            run['tokens'] = tokens({'attempt_files': [report['source_bindings'][key]['file'] for key in ('original_attempts', 'suffix_attempts')]}, root)
            run['cost'] = cost_fields({})
            replace_with_reconciliation(run, predictions, source_paths)

    inventory_path = phase_dir / 'subscription-stopped-inventory-v1/inventory.json'
    inventory = json.loads(inventory_path.read_text())
    if inventory['schema'] != 'subscription-stopped-inventory-v1':
        raise ValueError('Unsupported stopped subscription inventory')
    terra = next(entry for entry in inventory['conditions'] if entry['configuration_id'] == 'codex-gpt-5.6-terra-low' and entry['condition'] == 'P2')
    for binding in terra['evidence_files']:
        source_file = root / binding['path']
        if hashlib.sha256(source_file.read_bytes()).hexdigest() != binding['sha256']:
            raise ValueError('Terra stopped source hash mismatch: ' + str(source_file))
    original_path = phase_dir / 'runs/codex-gpt-5.6-terra-low/P2/development.jsonl'
    terra_predictions = rows(original_path)
    if len(terra_predictions) != 60 or sum(row.get('status') == 'ok' for row in terra_predictions) != terra['valid_count'] or terra['never_sent_count'] != 0 or {row['id'] for row in terra_predictions if row.get('status') != 'ok'} != set(terra['ambiguous_attempted_ids']):
        raise ValueError('Terra stopped original coverage mismatch')
    terra_evaluation, terra_all_four = score_saved(terra_predictions, root)
    terra_run = phase_run('codex-gpt-5.6-terra-low', 'P2', terra_evaluation, terra_all_four,
                          original_path.relative_to(root), root, baseline, predictions=terra_predictions,
                          experiment='subscription-stopped-original-v1')
    batch_seconds = [number(batch.get('elapsed_seconds')) for batch in terra['attempted_batch_order']]
    terra_run['timing'].update({'totalSeconds': sum(batch_seconds), 'medianSeconds': statistics.median(batch_seconds),
                                'p95Seconds': sorted(batch_seconds)[math.ceil(.95 * len(batch_seconds))-1],
                                'kind': 'batch', 'requests': len(batch_seconds), 'complete': True,
                                'comparableHosted': False,
                                'note': 'Five completed batches and one retained failed attempted batch. Ten original attempted IDs remain ambiguous; no retry or suffix.'})
    terra_run['tokens'] = tokens({'attempt_files': [terra['evidence_files'][0]['path']]}, root)
    terra_run['cost'] = cost_fields({})
    terra_run['evidenceSources'] = [GITHUB + str(inventory_path.relative_to(root)),
                                    GITHUB + str(original_path.relative_to(root))]
    terra_run['resultStatus'] = 'completed attempted coverage; ten ambiguous'
    replace_with_reconciliation(terra_run, terra_predictions, [original_path.relative_to(root)])
    terra_run['resultStatus'] = 'complete original attempted coverage; ten ambiguous'

    # Only frozen offline suffix reports enter the public snapshot. Their
    # source bindings retain failed and interrupted attempts without retry.
    suffix_reports = root / 'results/hosted-final-suffix-reconciled-v1'
    for report_path in sorted(suffix_reports.glob('*.json')) if suffix_reports.is_dir() else []:
        report = json.loads(report_path.read_text())
        if report.get('contract') != 'hosted-final-suffix-reconciliation-v1' or report.get('eligible_paired_comparison') is not False:
            raise ValueError('Unsupported hosted suffix report: ' + str(report_path))
        sources = report['sources']
        bindings = [sources[key] for key in ('original', 'original_journal', 'suffix', 'suffix_journal', 'plan')]
        if sources.get('interruption'):
            bindings.append(sources['interruption'])
        bindings.extend([sources['budget']['manifest'], sources['budget']['child']])
        for binding in bindings:
            source_path = root / binding['file']
            if hashlib.sha256(source_path.read_bytes()).hexdigest() != binding['sha256']:
                raise ValueError('Hosted suffix source hash mismatch: ' + binding['file'])
        original = rows(root / sources['original']['file'])
        suffix = rows(root / sources['suffix']['file'])
        interruption = rows(root / sources['interruption']['file']) if sources.get('interruption') else []
        predictions = original + interruption + suffix
        evaluation, all_four = score_saved(predictions, root)
        if (len(predictions) != report['attempted'] or evaluation['valid_outputs'] != report['valid_outputs'] or
                all_four != report['all_four_correct'] or report['never_sent_count'] != 60 - len(predictions) or
                [row['id'] for row in predictions] != [f'DEV-{i:03}' for i in range(1, len(predictions)+1)]):
            raise ValueError('Hosted suffix score or coverage mismatch: ' + str(report_path))
        parent = report['configuration_id']
        run = phase_run(parent, 'P2', evaluation, all_four, report_path.relative_to(root), root,
                        baseline, predictions=predictions, experiment='hosted-final-suffix-v1')
        run['tokens'] = tokens({'attempt_files': [sources['original']['file'], sources['suffix']['file']]}, root)
        reported = [number(row.get('elapsed_seconds')) for row in predictions]
        elapsed = [value for value in reported if value is not None]
        run['timing'].update({'totalSeconds': report['timing']['sum_reported_attempt_seconds'],
                              'medianSeconds': statistics.median(elapsed) if len(elapsed) == len(predictions) else None,
                              'p95Seconds': sorted(elapsed)[math.ceil(.95*len(elapsed))-1] if len(elapsed) == len(predictions) else None,
                              'kind': 'record', 'requests': len(predictions),
                              'complete': len(elapsed) == len(predictions), 'comparableHosted': True,
                              'note': 'Per-request development elapsed only; missing interruption time is unknown, and original counterbalanced schedule was not preserved.'})
        cost = report['cost']
        run['cost'].update({'actualUsd': float(cost['actual_total_usd']) if cost['actual_total_usd'] is not None else None,
                            'knownUsd': float(cost['known_observed_usd']),
                            'unknownUpperBoundUsd': cost['unknown_reserved_upper_bound_usd'],
                            'availability': 'complete' if cost['actual_total_usd'] is not None else 'partial',
                            'note': cost['note']})
        run['neverSent'] = report['never_sent_count']
        run['statusCounts'] = report['status_counts']
        replace_with_reconciliation(run, predictions,
                                    [Path(sources['original']['file']), Path(sources['suffix']['file'])] +
                                    ([Path(sources['interruption']['file'])] if sources.get('interruption') else []))

    # A second, separately sealed suffix supersedes the v1 stopped-on view.
    v2_report_path = root / 'results/hosted-final-suffix-reconciled-v2/qwen36-on-p2.json'
    if v2_report_path.is_file():
        report = json.loads(v2_report_path.read_text())
        if report.get('contract') != 'qwen36-on-p2-final21-reconciliation-v2' or report.get('eligible_paired_comparison') is not False:
            raise ValueError('Unsupported Qwen36 final21 report')
        sources = report['sources']
        bindings = [sources[key] for key in ('plan', 'original', 'original_journal', 'suffix_v1',
                                             'suffix_v1_journal', 'prior_report', 'suffix_v2', 'suffix_v2_journal')]
        bindings.extend((sources['budget']['manifest'], sources['budget']['child']))
        for binding in bindings:
            path = root / binding['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != binding['sha256']:
                raise ValueError('Qwen36 final21 source hash mismatch: ' + binding['file'])
        prior = json.loads((root / sources['prior_report']['file']).read_text())
        if prior.get('attempted') != 39 or prior.get('valid_outputs') != 37:
            raise ValueError('Qwen36 final21 prior report differs')
        predictions = rows(root / sources['original']['file']) + rows(root / sources['suffix_v1']['file']) + rows(root / sources['suffix_v2']['file'])
        evaluation, all_four = score_saved(predictions, root)
        if (len(predictions) != report['attempted'] or evaluation['valid_outputs'] != report['valid_outputs'] or
                all_four != report['all_four_correct'] or report['never_sent_count'] != 60 - len(predictions) or
                [row['id'] for row in predictions] != [f'DEV-{i:03}' for i in range(1, len(predictions)+1)]):
            raise ValueError('Qwen36 final21 score or coverage mismatch')
        run = phase_run(report['configuration_id'], 'P2', evaluation, all_four, v2_report_path.relative_to(root),
                        root, baseline, predictions=predictions, experiment='hosted-final-suffix-v2')
        source_paths = [Path(sources[key]['file']) for key in ('original', 'suffix_v1', 'suffix_v2')]
        run['tokens'] = tokens({'attempt_files': [str(path) for path in source_paths]}, root)
        elapsed = [number(row.get('elapsed_seconds')) for row in predictions]
        known_elapsed = [value for value in elapsed if value is not None]
        run['timing'].update({'totalSeconds': report['timing']['sum_reported_attempt_seconds'],
                              'medianSeconds': statistics.median(known_elapsed) if len(known_elapsed) == len(predictions) else None,
                              'p95Seconds': sorted(known_elapsed)[math.ceil(.95*len(known_elapsed))-1] if len(known_elapsed) == len(predictions) else None,
                              'kind': 'record', 'requests': len(predictions),
                              'complete': len(known_elapsed) == len(predictions), 'comparableHosted': True,
                              'note': 'Per-request development elapsed only; original counterbalanced schedule was not preserved.'})
        cost = report['cost']
        run['cost'].update({'actualUsd': float(cost['actual_total_usd']) if cost['actual_total_usd'] is not None else None,
                            'knownUsd': float(cost['known_observed_usd']),
                            'unknownUpperBoundUsd': cost['unknown_reserved_upper_bound_usd'],
                            'availability': 'complete' if cost['actual_total_usd'] is not None else 'partial',
                            'note': cost['note']})
        run['neverSent'] = report['never_sent_count']
        run['statusCounts'] = report['status_counts']
        replace_with_reconciliation(run, predictions, source_paths + [Path(sources['prior_report']['file'])])

    # A third sealed, never-sent-only suffix supersedes the v2 DEV-040 failure view.
    v3_report_path = root / 'results/hosted-final-suffix-reconciled-v3/qwen36-on-p2.json'
    if v3_report_path.is_file():
        from build_qwen36_on_p2_v3_reconciliation import reconcile as reconcile_v3
        report = json.loads(v3_report_path.read_text())
        sources = report['sources']
        recomputed = reconcile_v3(root, root / sources['budget']['manifest']['file'],
                                  sources['budget']['partition_id'], root / sources['review']['file'])
        if report != recomputed:
            raise ValueError('Qwen36 final20 report differs from sealed offline reconciliation')
        if (report.get('contract') != 'qwen36-on-p2-final20-reconciliation-v3' or
            report.get('configuration_id') != 'openrouter-paid-qwen36-35b-a3b-on' or
            report.get('condition') != 'P2' or report.get('eligible_paired_comparison') is not False):
            raise ValueError('Unsupported Qwen36 final20 report')
        source_paths = [Path(sources[key]['file']) for key in
                        ('original', 'suffix_v1', 'suffix_v2', 'suffix_v3')]
        predictions = [row for path in source_paths for row in rows(root / path)]
        evaluation, all_four = score_saved(predictions, root)
        if (len(predictions) != report['attempted'] or
            [row['id'] for row in predictions] != [f'DEV-{i:03}' for i in range(1, 42)] or
            evaluation != report['evaluation'] or
            evaluation['valid_outputs'] != report['valid_outputs'] or
            all_four != report['all_four_correct'] or
            report['never_sent_ids'] != [f'DEV-{i:03}' for i in range(42, 61)]):
            raise ValueError('Qwen36 final20 public score or coverage differs')
        run = phase_run(report['configuration_id'], 'P2', evaluation, all_four,
                        v3_report_path.relative_to(root), root, baseline,
                        predictions=predictions, experiment='hosted-final-suffix-v3')
        run['tokens'] = tokens({'attempt_files': [str(path) for path in source_paths]}, root)
        elapsed = [number(row.get('elapsed_seconds')) for row in predictions]
        known_elapsed = [value for value in elapsed if value is not None]
        run['timing'].update({'totalSeconds': report['timing']['sum_reported_attempt_seconds'],
                              'medianSeconds': statistics.median(known_elapsed) if len(known_elapsed) == len(predictions) else None,
                              'p95Seconds': sorted(known_elapsed)[math.ceil(.95*len(known_elapsed))-1] if len(known_elapsed) == len(predictions) else None,
                              'kind': 'record', 'requests': len(predictions),
                              'complete': len(known_elapsed) == len(predictions), 'comparableHosted': True,
                              'note': 'Per-request development elapsed only; original counterbalanced schedule was not preserved.'})
        cost = report['cost']
        run['cost'].update({'actualUsd': float(cost['actual_total_usd']) if cost['actual_total_usd'] is not None else None,
                            'knownUsd': float(cost['known_observed_usd']),
                            'unknownUpperBoundUsd': cost['unknown_reserved_upper_bound_usd'],
                            'availability': 'complete' if cost['actual_total_usd'] is not None else 'partial',
                            'note': cost['note']})
        run['neverSent'] = report['never_sent_count']
        run['neverSentIds'] = report['never_sent_ids']
        run['statusCounts'] = report['status_counts']
        replace_with_reconciliation(run, predictions, source_paths + [Path(sources['prior_report']['file'])])

    roster = []
    roster_entries = amended_roster(root, json.loads((phase_dir / 'roster.json').read_text())['entries'], runs)
    for entry in roster_entries:
        raw_reason = entry['reason'].lower()
        if 'native decision method' in raw_reason or 'deterministic rule' in raw_reason:
            reason = 'Prompt variants are not applicable to this native decision method.'
        elif 'batch10' in raw_reason or 'alternate views' in raw_reason:
            reason = 'The saved baseline and prompt run controls are not comparable.'
        elif entry['state'] == 'scheduled':
            reason = 'Selected for prompt evaluation; saved result status is shown separately.'
        elif entry['state'] == 'blocked':
            reason = 'No eligible completed prompt comparison is available.'
        else:
            reason = 'Outside the paired prompt comparison scope.'
        roster.append({'id': entry['id'], 'parentBaselineId': entry['parent_baseline_id'],
                       'disposition': entry['state'], 'reason': entry.get('reason') if entry.get('hosted_configuration_id') else reason,
                       **({'hostedConfigurationId': entry['hosted_configuration_id']}
                          if entry.get('hosted_configuration_id') else {})})

    pairs.extend(local_pair_reports(root, runs, reference_cases))

    ids = [run['id'] for run in runs]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate public run IDs')
    for run in runs:
        if run['experimentId'] != (run['parentBaselineId'] or run['id']):
            raise ValueError('Public experiment must identify one configuration')
    return {'nativeComparisons': native, 'generatedAt': datetime.now(timezone.utc).isoformat(),
            'denominator': 60,
            'referenceNote': '60 synthetic development records. References drafted and reviewed by the same AI assistant; no independent human adjudication. Agreement is descriptive, not real-world hiring accuracy.',
            'runs': runs, 'cases': cases, 'promptComparisons': pairs, 'roster': roster}


def main():
    value = export()
    destination = ROOT / 'public-site/data.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({'runs': len(value['runs']), 'cases': len(value['cases']),
                      'promptComparisons': len(value['promptComparisons']), 'output': str(destination)}))


if __name__ == '__main__':
    main()
