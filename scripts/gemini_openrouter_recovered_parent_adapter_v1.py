#!/usr/bin/env python3
"""Admit one recovered v2 hosted P0 as an input-only parent for v3 P1/P2.

This controller never reads reference labels and never sends inference requests.
The resulting manifest is run with the unchanged v3 paid controller.
"""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path

import gemini_openrouter_batch_v3 as v3
from gemini_openrouter_prefix_continuation_v1 import validate_prefix
from codex_batch_benchmark import parse_batch
from development_benchmark import ROOT, read_rows
from openrouter_benchmark import allowed_returned_models

PARENT_MODEL = 'google/gemini-3.8-flash'
PARENT_EFFORT = 'low'
ADMISSION_SCHEMA = 'gemini-openrouter-recovered-p0-admission-v1'
FILE_STEM = 'recovered-p0-v1'


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path, rows):
    with path.open('x') as handle:
        for row in rows:
            v3.durable(handle, row)


def admitted_baseline(parent_manifest):
    path = v3.inside(parent_manifest)
    folder = path.parent
    manifest = json.loads(path.read_text())
    if (manifest.get('schema'), manifest.get('variant'), manifest.get('model'), manifest.get('effort')) != (
            'gemini-openrouter-batch-v2', 'P0', PARENT_MODEL, PARENT_EFFORT):
        raise ValueError('Adapter accepts only the recovered hosted 3.8 Flash low P0')
    prefix_path = folder / 'development-prefix-recovery-proof-v1.json'
    prefix = validate_prefix(path, prefix_path)
    original_attempt = read_jsonl(folder / 'development-attempts.jsonl')[0]
    original_journal = read_jsonl(folder / 'development-journal.jsonl')
    suffix_attempts_path = folder / 'development-continuation-v1-attempts.jsonl'
    suffix_records_path = folder / 'development-continuation-v1-records.jsonl'
    suffix_journal_path = folder / 'development-continuation-v1-journal.jsonl'
    suffix_attempts = read_jsonl(suffix_attempts_path)
    suffix_records = read_jsonl(suffix_records_path)
    suffix_journal = read_jsonl(suffix_journal_path)
    if len(suffix_attempts) != 5 or len(suffix_records) != 50 or len(suffix_journal) != 16:
        raise ValueError('Recovered parent lacks five complete suffix batches')
    if suffix_journal[-1] != {'event': 'terminal', 'phase': 'development', 'expected_batches': 5,
                              'started_batches': 5, 'finished_batches': 5,
                              'completed': True, 'reason': 'completed'}:
        raise ValueError('Recovered parent suffix did not close')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if [r.get('id') for r in inputs] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Development input order drift')
    catalog = json.loads(v3.bound(manifest['catalog']).read_text())
    endpoints = json.loads(v3.bound(manifest['endpoints']).read_text())
    _, endpoint = v3.check_catalog(PARENT_MODEL, PARENT_EFFORT, catalog, endpoints)
    allowed = allowed_returned_models(PARENT_MODEL, endpoint)
    canon_attempts = [{**original_attempt, 'status': 'ok', 'predictions': prefix['predictions'],
                       'admission_original_status': 'identity_unverified',
                       'admission_prefix_proof_sha256': v3.sha(prefix_path.read_bytes())}]
    canon_records = []
    for pos, ident in enumerate(manifest['requests'][1]['record_ids']):
        canon_records.append({'id': ident, 'status': 'ok', 'prediction': prefix['predictions'][ident],
                              'batch_index': 1, 'original_status': 'identity_unverified',
                              'generation_id': prefix['generation_id'], 'batch_position': pos})
    canon_journal = original_journal[:2] + [{**original_journal[2], 'status': 'ok',
                                             'admission_original_status': 'identity_unverified'}]
    seen_generations = {prefix['generation_id']}
    seen_attempts = {prefix['attempt_id']}
    for index, (attempt, planned) in enumerate(zip(suffix_attempts, manifest['requests'][2:]), start=2):
        ids = planned['record_ids']
        if (attempt.get('batch_index') != index or attempt.get('ids') != ids or
                attempt.get('phase') != 'development' or attempt.get('model') != PARENT_MODEL or
                attempt.get('effort') != PARENT_EFFORT or attempt.get('provider') != v3.PROVIDER or
                attempt.get('manifest_sha256') != v3.sha(path.read_bytes()) or
                attempt.get('request') != planned['payload'] or
                attempt.get('request_sha256') != planned['payload_sha256'] or
                v3.sha(v3.canon(attempt['request'])) != planned['payload_sha256'] or
                attempt.get('reserved_cost_usd') != planned['reserve_usd'] or
                attempt.get('reference_labels_read') is not False or
                attempt.get('billing_ok') is not True or attempt.get('cost_unknown') is not False or
                attempt.get('status') not in ('ok', 'invalid_output')):
            raise ValueError('Suffix batch differs from exact frozen plan or billing')
        if attempt.get('requested_endpoint') != endpoint:
            raise ValueError('Suffix endpoint differs from frozen endpoint')
        raw = attempt.get('raw_response')
        if not isinstance(raw, dict) or attempt.get('generation_id') != raw.get('id'):
            raise ValueError('Suffix raw generation ID mismatch')
        if (raw.get('model') not in allowed or raw.get('provider') != v3.PROVIDER_NAME or
                attempt.get('returned_model') != raw.get('model') or
                attempt.get('returned_provider') != raw.get('provider')):
            raise ValueError('Suffix provider or model identity mismatch')
        if raw['id'] in seen_generations or attempt.get('attempt_id') in seen_attempts:
            raise ValueError('Duplicate suffix generation or attempt ID')
        seen_generations.add(raw['id'])
        seen_attempts.add(attempt['attempt_id'])
        usage = raw.get('usage') or {}
        if attempt.get('usage') != usage or v3.price(usage.get('cost')) != v3.price(attempt['observed_cost_usd']):
            raise ValueError('Suffix observed cost differs from provider usage')
        if any((usage.get('server_tool_use_details') or {}).values()):
            raise ValueError('Suffix server tools used')
        choices = raw.get('choices')
        if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('error'):
            raise ValueError('Suffix choice missing or errored')
        message = choices[0].get('message') or {}
        if message.get('tool_calls') or message.get('function_call') or message.get('refusal'):
            raise ValueError('Suffix output violated tool or refusal controls')
        group = inputs[(index - 1) * 10:index * 10]
        try:
            predictions = parse_batch(message.get('content'), group)
        except (ValueError, TypeError):
            predictions = None
        expected_status = 'ok' if predictions is not None and choices[0].get('finish_reason') == 'stop' else 'invalid_output'
        if attempt['status'] != expected_status or (expected_status == 'ok' and attempt.get('predictions') != predictions):
            raise ValueError('Suffix saved status or predictions differ from raw response')
        recorded = suffix_records[(index - 2) * 10:(index - 1) * 10]
        for pos, (item, ident) in enumerate(zip(recorded, ids)):
            if (item.get('id') != ident or item.get('phase') != 'development' or
                    item.get('status') != expected_status or
                    item.get('prediction') != (predictions or {}).get(ident) or
                    item.get('model') != PARENT_MODEL or item.get('effort') != PARENT_EFFORT or
                    item.get('batch_index') != index or item.get('batch_size') != 10 or
                    item.get('batch_position') != pos or item.get('generation_id') != raw['id'] or
                    item.get('request_sha256') != planned['payload_sha256']):
                raise ValueError('Suffix record differs from frozen batch')
            canon_records.append({'id': ident, 'status': expected_status,
                                  'prediction': (predictions or {}).get(ident),
                                  'batch_index': index, 'original_status': expected_status,
                                  'generation_id': raw['id'], 'batch_position': pos})
        journal_group = suffix_journal[3 * (index - 2):3 * (index - 1)]
        if journal_group != [
                {'event': 'intent', 'phase': 'development', 'ids': ids,
                 'payload_sha256': planned['payload_sha256'], 'reserve_usd': planned['reserve_usd']},
                {'event': 'started', 'attempt_id': attempt['attempt_id'], 'ids': ids,
                 'started_utc': attempt['started_utc']},
                {'event': 'finished', 'attempt_id': attempt['attempt_id'],
                 'status': expected_status, 'billing_ok': True}]:
            raise ValueError('Suffix journal differs from saved attempt')
        canon_attempts.append(attempt)
        canon_journal.extend(journal_group)
    canon_journal.append({'event': 'terminal', 'phase': 'development', 'expected_batches': 6,
                          'started_batches': 6, 'finished_batches': 6, 'completed': True,
                          'reason': 'completed'})
    if len(canon_attempts) != 6 or [r['id'] for r in canon_records] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Recovered parent did not reconcile all 60 inputs')
    source = {name: v3.binding(folder / name) for name in (
        'manifest.json', 'smoke-recovery-proof-v1.json',
        'development-prefix-recovery-proof-v1.json', 'development-attempts.jsonl',
        'development-records.jsonl', 'development-journal.jsonl',
        'development-batch1-recovered-generation-metadata.json',
        'development-continuation-v1-attempts.jsonl',
        'development-continuation-v1-records.jsonl',
        'development-continuation-v1-journal.jsonl',
        'development-suffix-approval-v1.json')}
    return manifest, source, canon_attempts, canon_records, canon_journal


def admission_object(parent_manifest, output_dir):
    manifest, source, attempts, records, journal = admitted_baseline(parent_manifest)
    folder = v3.inside(output_dir)
    return {'schema': ADMISSION_SCHEMA, 'baseline_id': manifest['configuration_id'],
            'model': PARENT_MODEL, 'effort': PARENT_EFFORT,
            'source_bindings': source,
            'reconciled_attempts': v3.binding(folder / (FILE_STEM + '-attempts.jsonl')),
            'reconciled_records': v3.binding(folder / (FILE_STEM + '-records.jsonl')),
            'reconciled_journal': v3.binding(folder / (FILE_STEM + '-journal.jsonl')),
            'total_batches': len(attempts), 'total_records': len(records),
            'reference_labels_read': False}


def admit(args):
    folder = v3.inside(args.output_dir)
    if folder.exists():
        raise FileExistsError('Admission output directory must be new')
    manifest, source, attempts, records, journal = admitted_baseline(args.parent_p0)
    folder.mkdir(parents=True)
    write_jsonl(folder / (FILE_STEM + '-attempts.jsonl'), attempts)
    write_jsonl(folder / (FILE_STEM + '-records.jsonl'), records)
    write_jsonl(folder / (FILE_STEM + '-journal.jsonl'), journal)
    proof = admission_object(args.parent_p0, folder)
    path = folder / (FILE_STEM + '-admission.json')
    with path.open('x') as handle:
        handle.write(json.dumps(proof, indent=2, ensure_ascii=False) + '\n')
        handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({'admission': str(path), 'sha256': v3.sha(path.read_bytes()),
                      'baseline_id': proof['baseline_id'], 'records': proof['total_records']}))


def validate_admission(path):
    path = v3.inside(path)
    saved = json.loads(path.read_text())
    if saved.get('schema') != ADMISSION_SCHEMA or saved.get('model') != PARENT_MODEL or saved.get('effort') != PARENT_EFFORT:
        raise ValueError('Unexpected recovered P0 admission proof')
    parent_manifest = v3.bound(saved['source_bindings']['manifest.json'])
    expected = admission_object(parent_manifest, path.parent)
    if saved != expected:
        raise ValueError('Recovered P0 admission proof or evidence changed')
    _, _, attempts, records, journal = admitted_baseline(parent_manifest)
    if read_jsonl(v3.bound(saved['reconciled_attempts'])) != attempts or read_jsonl(v3.bound(saved['reconciled_records'])) != records or read_jsonl(v3.bound(saved['reconciled_journal'])) != journal:
        raise ValueError('Saved reconciled P0 artifacts differ from validated evidence')
    return saved


def prepare(args):
    if args.variant not in ('P1', 'P2'):
        raise ValueError('Adapter prepares only P1 or P2')
    if not args.configuration_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.configuration_id):
        raise ValueError('Invalid configuration ID')
    if args.timeout <= 0 or args.timeout > 1800:
        raise ValueError('Invalid bounded timeout')
    output = v3.inside(args.output_dir)
    if output.exists():
        raise FileExistsError('Preparation output directory must be new')
    admission_path = v3.inside(args.admission)
    proof = validate_admission(admission_path)
    parent_manifest = v3.bound(proof['source_bindings']['manifest.json'])
    parent = {'manifest': v3.binding(parent_manifest),
              'development_records': proof['reconciled_records'],
              'development_attempts': proof['reconciled_attempts'],
              'development_journal': proof['reconciled_journal'],
              'admission_proof': v3.binding(admission_path),
              'baseline_id': proof['baseline_id']}
    cat = v3.PREP / 'catalog.json'
    ep = v3.PREP / 'gemini-3.8-flash-endpoints.json'
    catalog = json.loads(cat.read_text())
    endpoints = json.loads(ep.read_text())
    _, endpoint = v3.check_catalog(PARENT_MODEL, PARENT_EFFORT, catalog, endpoints)
    requests = v3.prepared_requests(PARENT_MODEL, PARENT_EFFORT, args.variant, proof['baseline_id'], endpoint)
    source_files = {'inputs': 'data/pilot/inputs.jsonl', 'policy': 'docs/LABELING_GUIDE.md',
                    'schema': 'schemas/judgments.schema.json',
                    'controller': 'scripts/gemini_openrouter_batch_v3.py',
                    'adapter': 'scripts/gemini_openrouter_recovered_parent_adapter_v1.py',
                    'batch_prompt': 'scripts/codex_batch_benchmark.py',
                    'frozen_variants': 'scripts/frozen_prompt_variants.py',
                    'variant_manifest': 'prompts/variants-v1/manifest.json',
                    'P1_text': 'prompts/variants-v1/P1-classifier.txt',
                    'P2_text': 'prompts/variants-v1/P2-classifier-sop.txt'}
    sources = {name: v3.binding(ROOT / file) for name, file in source_files.items()}
    sources['recovered_p0_admission_proof'] = v3.binding(admission_path)
    output.mkdir(parents=True)
    manifest = {'schema': 'gemini-openrouter-batch-v3', 'configuration_id': args.configuration_id,
                'model': PARENT_MODEL, 'effort': PARENT_EFFORT, 'variant': args.variant,
                'provider': v3.PROVIDER, 'parent_p0': parent, 'source_bindings': sources,
                'catalog': v3.binding(cat), 'endpoints': v3.binding(ep),
                'max_output_tokens': v3.MAX_OUTPUT, 'input_allowance_tokens': v3.ALLOWANCE_TOKENS,
                'timeout_seconds': args.timeout, 'requests': requests,
                'reference_labels_read': False, 'no_automatic_retry': True,
                'workflow': 'OpenRouter hosted batch10; smoke3 then development60',
                'source_urls': ['https://openrouter.ai/api/v1/models',
                                'https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints',
                                'https://openrouter.ai/docs/guides/features/plugins/overview']}
    path = output / 'manifest.json'
    with path.open('x') as handle:
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
        handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({'manifest': str(path), 'sha256': v3.sha(path.read_bytes()),
                      'per_request_reserve_usd': [r['reserve_usd'] for r in requests]}))


def run(args):
    manifest_path = v3.inside(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('schema'), manifest.get('model'), manifest.get('effort'), manifest.get('variant')) != (
            'gemini-openrouter-batch-v3', PARENT_MODEL, PARENT_EFFORT, manifest.get('variant')) or manifest.get('variant') not in ('P1', 'P2'):
        raise ValueError('Adapter run requires a recovered 3.8 Flash low P1/P2 manifest')
    parent = manifest.get('parent_p0') or {}
    proof_path = v3.bound(parent['admission_proof'])
    proof = validate_admission(proof_path)
    if (proof['baseline_id'] != parent.get('baseline_id') or
            proof['reconciled_records'] != parent.get('development_records') or
            proof['reconciled_attempts'] != parent.get('development_attempts') or
            proof['reconciled_journal'] != parent.get('development_journal') or
            proof['source_bindings']['manifest.json'] != parent.get('manifest')):
        raise ValueError('Recovered P0 parent binding mismatch')
    if manifest.get('source_bindings', {}).get('recovered_p0_admission_proof') != parent['admission_proof']:
        raise ValueError('Admission proof missing from frozen source bindings')
    v3.run(args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    a = sub.add_parser('admit', help='Offline input-only P0 reconciliation')
    a.add_argument('--parent-p0', required=True)
    a.add_argument('--output-dir', required=True)
    p = sub.add_parser('prepare', help='Offline P1/P2 manifest for unchanged v3 runner')
    p.add_argument('--admission', required=True)
    p.add_argument('--variant', required=True, choices=('P1', 'P2'))
    p.add_argument('--configuration-id', required=True)
    p.add_argument('--timeout', type=float, default=300)
    p.add_argument('--output-dir', required=True)
    r = sub.add_parser('run', help='Paid v3 run after revalidating recovered P0 admission')
    r.add_argument('--manifest', required=True)
    r.add_argument('--manifest-sha256', required=True)
    r.add_argument('--phase', required=True, choices=('smoke', 'development'))
    r.add_argument('--budget-manifest', required=True)
    r.add_argument('--partition-id', required=True)
    r.add_argument('--approval', required=True)
    r.add_argument('--smoke-inspection')
    r.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'admit': admit(args)
    elif args.command == 'prepare': prepare(args)
    else: run(args)


if __name__ == '__main__':
    main()
