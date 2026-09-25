#!/usr/bin/env python3
"""Validate closed Gemini OpenRouter batch evidence and export development results offline."""
import argparse
from decimal import Decimal
import json
import math
from pathlib import Path
import statistics

from codex_batch_benchmark import parse_batch
from development_benchmark import ROOT, KEYS, read_rows, score, valid
from gemini_openrouter_batch_v2 import (PROVIDER, PROVIDER_NAME, ROSTER, binding,
                                         bound, canon, prepared_requests, sha)
import gemini_openrouter_batch_v3 as v3
from openrouter_benchmark import allowed_returned_models

GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
DEFAULT_FOLDER = ROOT
IDS = [f'DEV-{i:03}' for i in range(1, 61)]


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid reported cost')
    return result


def evidence_url(path):
    try:
        return GITHUB + str(Path(path).resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return None


def closed_candidate(folder):
    journal = folder / 'development-journal.jsonl'
    if not journal.is_file():
        return False
    original = rows(journal)
    if original and original[-1].get('completed') is True:
        return True
    suffix = folder / 'development-continuation-v1-journal.jsonl'
    if not suffix.is_file():
        return False
    continuation = rows(suffix)
    return bool(continuation and continuation[-1].get('completed') is True)


def _metadata(attempt, folder, phase, source, manifest):
    metadata = attempt.get('generation_metadata')
    if metadata is not None:
        return metadata
    if attempt.get('status') != 'identity_unverified':
        return None
    if phase == 'smoke':
        proof_name = 'smoke-recovery-proof-v1.json'
        metadata_name = 'smoke-recovered-generation-metadata.json'
        required = ('manifest.json', 'smoke-attempts.jsonl', 'smoke-records.jsonl',
                    'smoke-journal.jsonl', metadata_name)
        schema = 'gemini-openrouter-smoke-recovery-proof-v1'
        terminal_key = 'original_smoke_terminal'
    elif phase == 'development' and attempt.get('batch_index') == 1:
        proof_name = 'development-prefix-recovery-proof-v1.json'
        metadata_name = 'development-batch1-recovered-generation-metadata.json'
        required = ('manifest.json', 'development-attempts.jsonl', 'development-records.jsonl',
                    'development-journal.jsonl', 'smoke-recovery-proof-v1.json', metadata_name)
        schema = 'gemini-openrouter-development-prefix-proof-v1'
        terminal_key = 'original_development_terminal'
    else:
        return None
    proof_path = folder / proof_name
    if not proof_path.is_file():
        return None
    proof = json.loads(proof_path.read_text())
    if (proof.get('schema') != schema or
            proof.get('configuration_id') != manifest['configuration_id'] or
            proof.get('model') != manifest['model'] or proof.get('effort') != manifest['effort'] or
            (phase == 'development' and proof.get('batch_index') != 1) or
            proof.get('attempt_id') != attempt['attempt_id'] or
            proof.get('generation_id') != attempt.get('generation_id') or
            proof.get('observed_cost_usd') != attempt.get('observed_cost_usd') or
            proof.get(terminal_key) != 'identity_unverified'):
        raise ValueError('Recovery proof identity mismatch')
    for name in required:
        item = proof['source_bindings'][name]
        if bound(item) != (folder / name).resolve():
            raise ValueError('Recovery proof source path mismatch')
    saved = json.loads((folder / metadata_name).read_text())
    if proof.get('recovered_metadata') != saved:
        raise ValueError('Recovery metadata mismatch')
    source.append(binding(proof_path))
    source.append(binding(folder / metadata_name))
    return saved


def _validate_phase(folder, manifest, manifest_sha, phase, inputs, source):
    n = 1 if phase == 'smoke' else 6
    plans = manifest['requests'][:1] if phase == 'smoke' else manifest['requests'][1:]
    attempts_path = folder / f'{phase}-attempts.jsonl'
    records_path = folder / f'{phase}-records.jsonl'
    journal_path = folder / f'{phase}-journal.jsonl'
    attempts, records, journal = rows(attempts_path), rows(records_path), rows(journal_path)
    stitched = False
    if phase == 'development' and journal[-1:] != [{
            'event': 'terminal', 'phase': 'development', 'expected_batches': 6,
            'started_batches': 6, 'finished_batches': 6, 'completed': True,
            'reason': 'completed'}]:
        prefix_terminal = {'event': 'terminal', 'phase': 'development', 'expected_batches': 6,
                           'started_batches': 1, 'finished_batches': 1,
                           'completed': False, 'reason': 'identity_unverified'}
        if (len(attempts) == 1 and len(records) == 10 and len(journal) == 4 and
                journal[-1] == prefix_terminal):
            suffix_paths = [folder / f'development-continuation-v1-{kind}.jsonl'
                            for kind in ('attempts', 'records', 'journal')]
            if not all(p.is_file() for p in suffix_paths):
                raise ValueError('Development prefix exists without closed continuation')
            suffix_attempts, suffix_records, suffix_journal = map(rows, suffix_paths)
            suffix_terminal = {'event': 'terminal', 'phase': 'development',
                               'expected_batches': 5, 'started_batches': 5,
                               'finished_batches': 5, 'completed': True,
                               'reason': 'completed'}
            if (len(suffix_attempts) != 5 or len(suffix_records) != 50 or
                    len(suffix_journal) != 16 or suffix_journal[-1] != suffix_terminal):
                raise ValueError('Development continuation lacks closed five-batch terminal')
            attempts += suffix_attempts
            records += suffix_records
            journal = journal[:-1] + suffix_journal[:-1] + [
                {'event': 'terminal', 'phase': phase, 'expected_batches': 6,
                 'started_batches': 6, 'finished_batches': 6,
                 'completed': True, 'reason': 'completed'}]
            source.extend(binding(p) for p in suffix_paths)
            source.extend(binding(ROOT / name) for name in (
                'scripts/gemini_openrouter_metadata_recovery_v1.py',
                'scripts/gemini_openrouter_prefix_continuation_v1.py'))
            stitched = True
    expected_ids = IDS[:3] if phase == 'smoke' else IDS
    terminal = {'event': 'terminal', 'phase': phase, 'expected_batches': n,
                'started_batches': n, 'finished_batches': n,
                'completed': True, 'reason': 'completed'}
    recovered_smoke_terminal = {'event': 'terminal', 'phase': 'smoke', 'expected_batches': 1,
                                'started_batches': 1, 'finished_batches': 1,
                                'completed': False, 'reason': 'identity_unverified'}
    terminal_ok = journal[-1:] == [terminal] or (phase == 'smoke' and
        journal[-1:] == [recovered_smoke_terminal] and
        (folder / 'smoke-recovery-proof-v1.json').is_file())
    if len(attempts) != n or len(records) != len(expected_ids) or not terminal_ok:
        raise ValueError(f'{phase} lacks a closed {n}-batch terminal')
    if len(journal) != 3*n + 1 or [r.get('id') for r in records] != expected_ids:
        raise ValueError(f'{phase} attempt, record, or journal count/order differs')
    input_map = {r['id']: r for r in inputs}
    seen_attempts, seen_generations = set(), set()
    effective = []
    metadata_values = []
    for index, (attempt, planned) in enumerate(zip(attempts, plans)):
        ids = planned['record_ids']
        group = [input_map[i] for i in ids]
        batch_index = index if phase == 'smoke' else index + 1
        attempt_id = attempt.get('attempt_id')
        if not isinstance(attempt_id, str) or not attempt_id or attempt_id in seen_attempts:
            raise ValueError('Missing or reused attempt ID')
        seen_attempts.add(attempt_id)
        if (attempt.get('ids') != ids or attempt.get('phase') != phase or
                attempt.get('batch_index') != batch_index or
                attempt.get('model') != manifest['model'] or attempt.get('effort') != manifest['effort'] or
                attempt.get('provider') != PROVIDER or attempt.get('manifest_sha256') != manifest_sha or
                attempt.get('request') != planned['payload'] or
                attempt.get('request_sha256') != planned['payload_sha256'] or
                sha(canon(attempt['request'])) != planned['payload_sha256'] or
                attempt.get('reserved_cost_usd') != planned['reserve_usd'] or
                attempt.get('reference_labels_read') is not False or
                attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                attempt.get('status') not in ('ok', 'invalid_output', 'identity_unverified')):
            raise ValueError(f'{phase} frozen request or billing mismatch: batch {batch_index}')
        if attempt['status'] == 'identity_unverified' and phase != 'smoke' and not (stitched and index == 0):
            raise ValueError('Development identity was not verified')
        endpoint = attempt.get('requested_endpoint')
        expected_endpoint = next(e for e in json.loads(bound(manifest['endpoints']).read_text())['data']['endpoints'] if e.get('tag') == PROVIDER)
        if endpoint != expected_endpoint:
            raise ValueError('Requested endpoint differs from frozen endpoint')
        raw = attempt.get('raw_response')
        if not isinstance(raw, dict) or attempt.get('generation_id') != raw.get('id'):
            raise ValueError('Missing raw response or generation identity')
        generation_id = raw.get('id')
        if not isinstance(generation_id, str) or not generation_id or generation_id in seen_generations:
            raise ValueError('Missing or duplicate generation ID')
        seen_generations.add(generation_id)
        allowed = allowed_returned_models(manifest['model'], endpoint)
        if (raw.get('model') not in allowed or raw.get('provider') not in (None, PROVIDER_NAME) or
                attempt.get('returned_model') != raw.get('model') or
                attempt.get('returned_provider') != raw.get('provider') or
                attempt.get('allowed_returned_models') != sorted(allowed)):
            raise ValueError('Returned model/provider identity mismatch')
        metadata = _metadata(attempt, folder, phase, source, manifest)
        if metadata is not None:
            if (metadata.get('id') != generation_id or metadata.get('model') not in allowed or
                    metadata.get('provider_name') != PROVIDER_NAME or
                    metadata.get('num_fetches') not in (None, 0) or
                    metadata.get('num_search_results') not in (None, 0)):
                raise ValueError('Generation metadata identity/control mismatch')
            duration = metadata.get('generation_time')
            if duration is not None:
                if not finite_number(duration):
                    raise ValueError('Invalid provider generation duration')
                metadata_values.append(duration / 1000)
        elif attempt['status'] != 'identity_unverified' and raw.get('provider') != PROVIDER_NAME:
            raise ValueError('Batch without metadata lacks exact observed provider')
        usage = raw.get('usage')
        if not isinstance(usage, dict) or attempt.get('usage') != usage:
            raise ValueError('Batch usage differs from raw response')
        reported_cost = usage.get('cost')
        if reported_cost is not None and money(reported_cost) != money(attempt['observed_cost_usd']):
            raise ValueError('Observed cost differs from provider usage')
        if metadata is not None and metadata.get('total_cost') is not None and money(metadata['total_cost']) != money(attempt['observed_cost_usd']):
            raise ValueError('Observed cost differs from generation metadata')
        choices = raw.get('choices')
        if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('error'):
            raise ValueError('Missing clean response choice')
        choice = choices[0]
        message = choice.get('message') or {}
        if message.get('tool_calls') or message.get('function_call') or message.get('refusal'):
            raise ValueError('Forbidden tool or refusal in completed batch')
        if any((usage.get('server_tool_use_details') or {}).values()):
            raise ValueError('Server tool use in completed batch')
        try:
            parsed = parse_batch(message.get('content'), group)
        except (ValueError, TypeError):
            parsed = None
        effective_status = ('ok' if parsed is not None and choice.get('finish_reason') == 'stop'
                            else 'invalid_output')
        if attempt['status'] == 'ok' and (effective_status != 'ok' or attempt.get('predictions') != parsed):
            raise ValueError('Saved valid predictions differ from raw response')
        if attempt['status'] == 'invalid_output' and effective_status != 'invalid_output':
            raise ValueError('Saved invalid-output status differs from raw response')
        if attempt['status'] == 'identity_unverified' and metadata is None:
            raise ValueError('Unrecovered identity cannot enter completed report')
        if attempt['status'] == 'identity_unverified':
            proof_name = ('smoke-recovery-proof-v1.json' if phase == 'smoke'
                          else 'development-prefix-recovery-proof-v1.json')
            proof = json.loads((folder / proof_name).read_text())
            if proof.get('predictions') != parsed or effective_status != 'ok':
                raise ValueError('Recovery predictions differ from raw response')
        if journal[3*index] != {'event': 'intent', 'phase': phase, 'ids': ids,
                               'payload_sha256': planned['payload_sha256'], 'reserve_usd': planned['reserve_usd']}:
            raise ValueError('Intent journal differs from frozen request')
        if journal[3*index+1] != {'event': 'started', 'attempt_id': attempt_id,
                                 'ids': ids, 'started_utc': attempt['started_utc']}:
            raise ValueError('Started journal differs from attempt')
        if journal[3*index+2] != {'event': 'finished', 'attempt_id': attempt_id,
                                 'status': attempt['status'], 'billing_ok': True}:
            raise ValueError('Finished journal differs from attempt')
        for position, ident in enumerate(ids):
            record = records[(0 if phase == 'smoke' else index*10) + position]
            if (record.get('id') != ident or record.get('phase') != phase or
                    record.get('status') != attempt['status'] or
                    record.get('prediction') != (attempt.get('predictions') or {}).get(ident) or
                    record.get('model') != manifest['model'] or record.get('effort') != manifest['effort'] or
                    record.get('batch_index') != batch_index or record.get('batch_size') != len(ids) or
                    record.get('batch_position') != position or
                    record.get('generation_id') != generation_id or
                    record.get('request_sha256') != planned['payload_sha256']):
                raise ValueError('Saved record differs from batch attempt: ' + ident)
            effective.append({**record, 'status': effective_status,
                              'prediction': parsed.get(ident) if effective_status == 'ok' else None})
    source.extend(binding(path) for path in (attempts_path, records_path, journal_path))
    return effective, attempts, metadata_values


def _comparison(before, after, refs, inputs):
    truth = {r['id']: r['proposed_labels'] for r in refs}
    feedback = {r['id']: r['feedback'] for r in inputs}
    old = {r['id']: r['prediction'] if r['status'] == 'ok' else None for r in before}
    new = {r['id']: r['prediction'] if r['status'] == 'ok' else None for r in after}
    changed = [ident for ident in IDS if old[ident] != new[ident]]
    return {'bothValid': sum(old[i] is not None and new[i] is not None for i in IDS),
            'changedRecordCount': len(changed),
            'allFourWrongToCorrect': [i for i in changed if old[i] != truth[i] and new[i] == truth[i]],
            'allFourCorrectToWrong': [i for i in changed if old[i] == truth[i] and new[i] != truth[i]],
            'cases': [{'id': i, 'from_state': 'valid' if old[i] else 'invalid_output',
                       'to_state': 'valid' if new[i] else 'invalid_output',
                       'from_prediction': old[i], 'to_prediction': new[i],
                       'reference': truth[i], 'feedback': feedback[i]} for i in changed]}


def _one(folder, refs, pairs, inputs):
    manifest_path = folder / 'manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    schema = manifest.get('schema')
    if schema not in ('gemini-openrouter-batch-v2', 'gemini-openrouter-batch-v3') or manifest.get('model') not in ROSTER:
        raise ValueError('Unexpected Gemini manifest')
    if manifest.get('effort') not in ROSTER[manifest['model']] or manifest.get('variant') not in ('P0', 'P1', 'P2') or manifest.get('provider') != PROVIDER:
        raise ValueError('Invalid Gemini configuration')
    controller = 'scripts/gemini_openrouter_batch_' + schema.rsplit('-', 1)[-1] + '.py'
    if (manifest.get('reference_labels_read') is not False or
            manifest.get('no_automatic_retry') is not True or
            manifest.get('source_bindings', {}).get('controller', {}).get('path') != controller):
        raise ValueError('Frozen controller or input-only control differs')
    source = [binding(manifest_path)]
    for item in manifest['source_bindings'].values():
        bound(item)
        source.append(item)
    if manifest.get('parent_p0'):
        if manifest['variant'] == 'P0':
            raise ValueError('P0 cannot have a parent')
        for key in ('manifest', 'development_records', 'development_attempts', 'development_journal'):
            item = manifest['parent_p0'][key]
            bound(item)
            source.append(item)
        parent = json.loads(bound(manifest['parent_p0']['manifest']).read_text())
        if (parent.get('schema') != schema or parent.get('variant') != 'P0' or
                parent.get('model') != manifest['model'] or parent.get('effort') != manifest['effort'] or
                parent.get('configuration_id') != manifest['parent_p0']['baseline_id']):
            raise ValueError('Hosted P0 parent binding differs')
    elif manifest['variant'] != 'P0':
        raise ValueError('P1/P2 lacks hosted P0 parent')
    endpoint = next(e for e in json.loads(bound(manifest['endpoints']).read_text())['data']['endpoints'] if e.get('tag') == PROVIDER)
    planner = prepared_requests if schema.endswith('v2') else v3.prepared_requests
    if planner(manifest['model'], manifest['effort'], manifest['variant'],
                         manifest['parent_p0']['baseline_id'] if manifest.get('parent_p0') else manifest['configuration_id'], endpoint) != manifest['requests']:
        raise ValueError('Frozen requests differ from exact payload builder')
    for item in (manifest['catalog'], manifest['endpoints']):
        bound(item)
        source.append(item)
    manifest_sha = sha(manifest_bytes)
    _validate_phase(folder, manifest, manifest_sha, 'smoke', inputs, source)
    predictions, attempts, durations = _validate_phase(folder, manifest, manifest_sha, 'development', inputs, source)
    evaluated = score(refs, predictions, pairs)
    counts = {key: evaluated['metrics'][key]['correct'] for key in KEYS}
    counts['all_four'] = sum(r['status'] == 'ok' and r['prediction'] == ref['proposed_labels']
                             for r, ref in zip(predictions, refs))
    token_keys = {'input': 'prompt_tokens', 'output': 'completion_tokens'}
    tokens = {key: sum(a['usage'].get(field, 0) for a in attempts if isinstance(a['usage'].get(field), int))
              for key, field in token_keys.items()}
    tokens.update({'cachedInput': sum(((a['usage'].get('prompt_tokens_details') or {}).get('cached_tokens') or 0) for a in attempts),
                   'cacheWrite': sum(((a['usage'].get('prompt_tokens_details') or {}).get('cache_write_tokens') or 0) for a in attempts),
                   'reasoning': sum(((a['usage'].get('completion_tokens_details') or {}).get('reasoning_tokens') or 0) for a in attempts),
                   'reportedRequests': sum(all(isinstance(a['usage'].get(field), int) for field in token_keys.values()) for a in attempts),
                   'totalRequests': len(attempts), 'complete': all(all(isinstance(a['usage'].get(field), int) for field in token_keys.values()) for a in attempts),
                   'note': 'Development batch usage counted once per batch; missing provider usage is unknown.'})
    known = sum((money(a['observed_cost_usd']) for a in attempts), Decimal('0'))
    ident = manifest['configuration_id']
    run = {'id': ident, 'experimentId': manifest['parent_p0']['baseline_id'] if manifest.get('parent_p0') else ident,
           'protocolId': 'gemini-openrouter-hosted-batch10-' + schema.rsplit('-', 1)[-1],
           'parentBaselineId': manifest['parent_p0']['baseline_id'] if manifest.get('parent_p0') else None,
           'model': manifest['model'], 'effort': manifest['effort'], 'surface': 'OpenRouter Gemini hosted batch10',
           'condition': manifest['variant'], 'complete': True,
           'resultStatus': 'complete; observational hosted batch comparison',
           'pairedEligible': False, 'records': 60, 'valid': evaluated['valid_outputs'],
           'metrics': counts,
           'timing': {'kind': 'batch', 'requests': 6, 'complete': True,
                      'providerGenerationSeconds': statistics.median(durations) if durations else None,
                      'providerGenerationReportedRequests': len(durations),
                      'providerGenerationTotalRequests': 6,
                      'providerGenerationBasis': 'Median OpenRouter generation_time in seconds, converted from milliseconds; each duration covers a batch, not one record or pure inference.',
                      'providerGenerationSource': 'https://openrouter.ai/docs/api/api-reference/generations/get-generation',
                      'inferenceSeconds': None,
                      'inferenceBasis': 'Pure provider inference duration is unavailable.'},
           'tokens': tokens,
           'cost': {'actualUsd': float(known), 'knownUsd': float(known), 'estimatedUsd': None,
                    'unknownUpperBoundUsd': '0', 'availability': 'complete',
                    'note': 'Observed provider cost for six development batches; smoke excluded.'},
           'evidenceUrl': evidence_url(folder / 'development-attempts.jsonl')}
    truth = {r['id']: r['proposed_labels'] for r in refs}
    feedback = {r['id']: r['feedback'] for r in inputs}
    cases = [{'configuration': ident, 'id': r['id'], 'feedback': feedback[r['id']],
              'reference': truth[r['id']], 'prediction': r['prediction'], 'status': r['status'],
              'different_fields': [k for k in KEYS if r['prediction'] is not None and r['prediction'][k] != truth[r['id']][k]]}
             for r in predictions]
    return manifest, run, cases, predictions, source


def build(root_or_folder=DEFAULT_FOLDER):
    path = Path(root_or_folder)
    if (path / 'manifest.json').is_file():
        folders = [path]
    else:
        roots = ([path / 'results/gemini-openrouter-prep-v2',
                  path / 'results/gemini-openrouter-prep-v3']
                 if path == ROOT else [path])
        folders = sorted(p.parent for base in roots if base.is_dir()
                         for p in base.rglob('manifest.json') if closed_candidate(p.parent))
    refs = read_rows(ROOT / 'data/pilot/proposed_labels.jsonl')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if [r['id'] for r in refs] != IDS or [r['id'] for r in inputs] != IDS:
        raise ValueError('Development inputs/references differ from exact60')
    pairs = json.loads((ROOT / 'data/pilot/pairs.json').read_text())
    results = [_one(folder, refs, pairs, inputs) for folder in folders]
    by_key = {(m['model'], m['effort'], m['variant']): (m, run, cases, predictions)
              for m, run, cases, predictions, _ in results}
    if len(by_key) != len(results):
        raise ValueError('Duplicate model, effort, and variant configuration')
    public_pairs = []
    for (model, effort, variant), (m, run, cases, predictions) in by_key.items():
        if variant != 'P0':
            parent = by_key.get((model, effort, 'P0'))
            if parent is None or parent[0]['configuration_id'] != m['parent_p0']['baseline_id']:
                raise ValueError('P1/P2 lacks matching completed hosted P0')
    for (model, effort, variant), (m, run, cases, predictions) in by_key.items():
        if variant != 'P0':
            continue
        comparisons = {}
        for other in ('P1', 'P2'):
            target = by_key.get((model, effort, other))
            if target:
                comparisons[f'P0_to_{other}'] = _comparison(predictions, target[3], refs, inputs)
        if (model, effort, 'P1') in by_key and (model, effort, 'P2') in by_key:
            comparisons['P1_to_P2'] = _comparison(by_key[(model, effort, 'P1')][3], by_key[(model, effort, 'P2')][3], refs, inputs)
        if comparisons:
            public_pairs.append({'id': m['configuration_id'], 'model': model, 'effort': effort,
                                 'eligible': False, 'conditions': {v: by_key[(model, effort, v)][1]['metrics']
                                                            for v in ('P0', 'P1', 'P2') if (model, effort, v) in by_key},
                                 'comparisons': comparisons,
                                 'comparisonLimit': 'One pass per condition; prompt variant effects remain observational.'})
    source = [binding(ROOT / name) for name in ('data/pilot/inputs.jsonl', 'data/pilot/proposed_labels.jsonl', 'data/pilot/pairs.json',
                                                 'scripts/build_gemini_openrouter_report_v1.py')]
    source.extend(item for result in results for item in result[4])
    return {'kind': 'gemini-openrouter-hosted-batch-report-v1',
            'reference_status': 'AI-reviewed provisional; development only',
            'causal_claim_supported': False,
            'comparison_limit': 'One pass per condition; hosted P0/P1/P2 are observational comparisons.',
            'source_bindings': source, 'public_runs': [r[1] for r in results],
            'public_cases': [c for r in results for c in r[2]],
            'public_pairs': public_pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT_FOLDER)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.directory)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


if __name__ == '__main__':
    main()
