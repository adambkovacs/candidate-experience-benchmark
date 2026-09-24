#!/usr/bin/env python3
"""Versioned SemIf P2 continuation for untouched DEV-034..060.

Preflight reads frozen inputs, artifacts, source code and tokenizer locally. It
does not load model weights into MLX or call a model. --run requires a reviewed
manifest hash and a matching preflight hash. Neither mode repairs DEV-033 or
updates the original global journal.
"""
import argparse
import json
import os
import platform
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import prompt_execution_gates as gates
import semif_prompt_execution as original
from anyjev_prompt_execution import binding, exclusive, lines, utc
from development_benchmark import valid
from frozen_prompt_variants import compose_instruction
from jev_benchmark import make_payload

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / 'results/prompt-comparison-v1-2026-09-24/semif-generated-exact'
CONTINUATION = FOLDER / 'P2-continuation-v1'
MANIFEST = CONTINUATION / 'execution-manifest.draft.json'
AUDIT = FOLDER / 'P2-interruption-audit.json'
CORRECTION = FOLDER / 'P2-interruption-audit-correction-v1.json'
ORIGINAL_MANIFEST_SHA256 = '8d142d97ebe7e7422a231bae14e324adca909baad3c3917311478e5078bfba85'
ELIGIBLE = [f'DEV-{i:03d}' for i in range(34, 61)]
PREVIEW = CONTINUATION / 'preflight-DEV034-060.json'


def bound_path(spec):
    return (ROOT / spec['file']).resolve()


def validate_interruption(audit_path=AUDIT):
    """Fail if the original evidence moved or any extra record was attempted."""
    audit_path = Path(audit_path)
    audit = json.loads(audit_path.read_text())
    if audit.get('audit_type') != 'interruption_status_audit' or audit.get('status') != 'interrupted_with_unfinished_record' or audit.get('cause') != 'unknown':
        raise ValueError('Original interruption audit changed')
    source = audit['source']
    if (source.get('configuration'), source.get('condition'), source.get('stage')) != ('semif-generated-bf16', 'P2', 'development'):
        raise ValueError('Original interruption identity changed')
    correction = json.loads(CORRECTION.read_text())
    audit_binding = binding(audit_path, ROOT)
    if (correction.get('contract') != 'semif-p2-interruption-audit-correction-v1'
            or correction.get('original_audit') != audit_binding
            or correction.get('field') != 'source.original_manifest_sha256'
            or correction.get('recorded_sha256') != source['original_manifest_sha256']
            or correction.get('actual_sha256') != ORIGINAL_MANIFEST_SHA256
            or correction.get('scope') != 'Correct only the parent manifest SHA binding; preserve the original audit and all other evidence.'):
        raise ValueError('Original manifest correction binding changed')
    correction_binding = binding(CORRECTION, ROOT)
    parent = {'file': source['original_manifest'], 'sha256': ORIGINAL_MANIFEST_SHA256}
    manifest = gates.json_bound(parent, ROOT)
    saved_spec = {'file': audit['saved_output']['path'], 'sha256': audit['saved_output']['sha256']}
    events_spec = {'file': audit['events']['path'], 'sha256': audit['events']['sha256']}
    saved = lines(gates.bound(saved_spec, ROOT))
    events = lines(gates.bound(events_spec, ROOT))
    expected_saved = [f'DEV-{i:03d}' for i in range(1, 33)]
    if audit['saved_output']['row_count'] != 32 or [r.get('id') for r in saved] != expected_saved:
        raise ValueError('Original saved row set changed')
    if len(events) != 65 or audit['events']['event_count'] != 65:
        raise ValueError('Original event count changed')
    expected_events = []
    for record_id in expected_saved:
        expected_events += [('started', record_id), ('finished', record_id)]
    expected_events.append(('started', 'DEV-033'))
    if [(e.get('event'), e.get('id')) for e in events] != expected_events:
        raise ValueError('Original event sequence changed')
    unfinished = audit['events']['unfinished_started_record']
    if any(events[-1].get(k) != unfinished.get(k) for k in ('event', 'id', 'utc', 'generated_request_sha256')):
        raise ValueError('DEV-033 start evidence changed')
    if audit['events']['unfinished_record_has_finish_event'] is not False or audit['continuation_boundary']['ambiguous_id_excluded_from_automatic_replay'] != 'DEV-033':
        raise ValueError('Ambiguous DEV-033 boundary changed')
    if audit['continuation_boundary']['eligible_unattempted_ids'] != ELIGIBLE:
        raise ValueError('Continuation allowlist changed')
    if audit['terminal_record']['present_at_audit'] is not False or bound_path({'file': audit['terminal_record']['path']}).exists():
        raise ValueError('Original terminal state changed')
    if any(r.get('status') not in ('ok', 'invalid_output') for r in saved):
        raise ValueError('Original saved output status changed')
    if saved[-1].get('id') != audit['saved_output']['last_saved_id'] or saved[-1].get('status') != audit['saved_output']['last_saved_status'] or saved[-1].get('finished_utc') != audit['saved_output']['last_saved_finished_utc']:
        raise ValueError('Original final saved record changed')
    if any(e.get('generated_request_sha256') != r.get('generated_request_sha256') for e, r in zip(events[::2], saved)):
        raise ValueError('Original started request binding changed')
    if any(e.get('status') != r.get('status') for e, r in zip(events[1::2], saved)):
        raise ValueError('Original finished status changed')
    claim = audit['global_journal_claim']
    global_events = lines((ROOT / claim['path']).read_bytes())
    matches = [e for e in global_events if e.get('attempt_id') == claim['claim_id']]
    if len(matches) != 1 or any(matches[0].get(k) != claim.get(k) for k in ('seq', 'event', 'utc')):
        raise ValueError('Original global claim is no longer solely unresolved')
    return {'audit': audit, 'audit_binding': audit_binding, 'correction_binding': correction_binding,
            'parent': parent, 'parent_manifest': manifest, 'saved_binding': saved_spec, 'events_binding': events_spec}


def validate_continuation_manifest(manifest, evidence):
    parent = evidence['parent_manifest']
    metadata = manifest.get('continuation')
    if not isinstance(metadata, dict) or metadata.get('version') != 'semif-p2-continuation-v1':
        raise ValueError('Continuation version missing')
    if metadata.get('status') != 'draft_review_required' or metadata.get('parent_manifest') != evidence['parent'] or metadata.get('interruption_audit') != evidence['audit_binding'] or metadata.get('interruption_audit_correction') != evidence['correction_binding']:
        raise ValueError('Continuation parent/audit binding changed')
    if metadata.get('original_saved_output') != evidence['saved_binding'] or metadata.get('original_events') != evidence['events_binding']:
        raise ValueError('Continuation original evidence binding changed')
    if metadata.get('order_deviation') != 'P2 development skips completed DEV-001..032 and leaves started DEV-033 unresolved; execute only DEV-034..060 in original record order':
        raise ValueError('Continuation order deviation changed')
    if metadata.get('eligible_unattempted_ids') != ELIGIBLE or metadata.get('ambiguous_id') != 'DEV-033' or metadata.get('canonical_denominator') != 60:
        raise ValueError('Continuation coverage policy changed')
    if metadata.get('original_global_journal_unchanged') is not True or metadata.get('execution_requires_explicit_reviewed_manifest_and_preflight_hashes') is not True:
        raise ValueError('Continuation execution policy changed')
    if metadata.get('controller_source', {}).get('file') != 'scripts/semif_prompt_continuation.py':
        raise ValueError('Continuation controller source binding missing')
    gates.bound(metadata['controller_source'], ROOT)
    # These are the only modifications to the original execution manifest.
    rebuilt = json.loads(json.dumps(parent))
    config = rebuilt['configurations'][0]
    config['conditions']['P2']['output_paths']['development'] = str((CONTINUATION / 'development-DEV034-060.jsonl').relative_to(ROOT))
    config['native_execution']['journal'] = str((CONTINUATION / 'execution-journal.jsonl').relative_to(ROOT))
    rebuilt['continuation'] = metadata
    if rebuilt != manifest:
        raise ValueError('Frozen execution controls or sources changed')
    if manifest['configurations'][0]['conditions']['P2']['output_paths']['development'] == parent['configurations'][0]['conditions']['P2']['output_paths']['development']:
        raise ValueError('Continuation output overlaps original')


def arguments(manifest_sha):
    controls = json.loads(MANIFEST.read_text())['configurations'][0]['controls']
    return SimpleNamespace(prompt_variant='P2', parent_baseline_id='semif-generated-bf16',
        execution_manifest=str(MANIFEST), execution_manifest_sha256=manifest_sha,
        execution_configuration='semif-generated-bf16', execution_stage='development',
        execution_journal=str(CONTINUATION / 'execution-journal.jsonl'),
        output=str(CONTINUATION / 'development-DEV034-060.jsonl'), limit=60,
        kind='semif', mode='generated', bits=None, offset=0, device='mps', max_tokens=4096,
        revision=controls['model_revision'], model_path=controls['model'],
        smoke_inspection=str(FOLDER / 'P2-smoke-inspection.json'),
        smoke_inspection_sha256=gates.sha((FOLDER / 'P2-smoke-inspection.json').read_bytes()),
        config_note='SemIf P2 continuation v1; DEV034-060 only; DEV033 unresolved; same native MLX BF16+FP32 controls; no repair or retries')


def offline_preflight(manifest_sha):
    evidence = validate_interruption()
    manifest = json.loads(MANIFEST.read_text())
    validate_continuation_manifest(manifest, evidence)
    args = arguments(manifest_sha)
    plan = original.load_plan(args, ROOT)
    original.verify_local_sources(plan, args)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    measured = original.exact_token_check(plan, args, tok)
    original_smoke_plan = dict(plan, manifest_binding=evidence['parent'],
        condition=evidence['parent_manifest']['configurations'][0]['conditions']['P2'])
    original.inspect_smoke(original_smoke_plan, args, tok)
    records = measured['records']
    if [r['id'] for r in records] != [f'DEV-{i:03d}' for i in range(1, 61)]:
        raise ValueError('Exact P2 token preflight lacks 60 records')
    selected = records[33:]
    if [r['id'] for r in selected] != ELIGIBLE:
        raise ValueError('Continuation token membership differs')
    report = {'contract': 'semif-p2-continuation-preflight-v1', 'measured_utc': utc(),
        'manifest': plan['manifest_binding'], 'parent_manifest': evidence['parent'],
        'interruption_audit': evidence['audit_binding'], 'interruption_audit_correction': evidence['correction_binding'],
        'eligible_unattempted_ids': ELIGIBLE,
        'ambiguous_id_excluded': 'DEV-033', 'canonical_denominator': 60,
        'all60_P2_tokens_sha256': gates.canonical(records), 'selected_records': selected,
        'all180_exact_rendered_tokens_verified': True, 'model_loaded': False,
        'inference_performed': False, 'reference_labels_read': False}
    return args, plan, report


def verify_review_receipt(receipt_path, receipt_sha, manifest_sha, preflight_sha):
    """Bind a separate human review decision to the exact frozen inputs."""
    if not receipt_path or not receipt_sha:
        raise ValueError('Run requires a root-review execution receipt and its SHA-256')
    receipt_path = Path(receipt_path).resolve()
    if receipt_path.parent != CONTINUATION.resolve() or not receipt_path.is_file():
        raise ValueError('Root-review receipt must be a file in the continuation directory')
    if gates.sha(receipt_path.read_bytes()) != receipt_sha:
        raise ValueError('Root-review receipt hash mismatch')
    receipt = json.loads(receipt_path.read_text())
    expected = {'contract': 'semif-p2-continuation-root-review-v1',
                'decision': 'approved_for_remaining_27',
                'manifest': {'file': str(MANIFEST.relative_to(ROOT)), 'sha256': manifest_sha},
                'preflight': {'file': str(PREVIEW.relative_to(ROOT)), 'sha256': preflight_sha},
                'interruption_audit_correction': binding(CORRECTION, ROOT),
                'eligible_unattempted_ids': ELIGIBLE,
                'ambiguous_id_excluded': 'DEV-033', 'canonical_denominator': 60}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Root-review receipt does not approve these exact continuation inputs')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip() or not isinstance(receipt.get('reviewed_utc'), str) or not receipt['reviewed_utc'].strip():
        raise ValueError('Root-review receipt lacks reviewer or review time')


def run(args, plan, report, preflight_sha, receipt_path=None, receipt_sha=None):
    verify_review_receipt(receipt_path, receipt_sha, plan['manifest_binding']['sha256'], preflight_sha)
    if not PREVIEW.exists() or gates.sha(PREVIEW.read_bytes()) != preflight_sha:
        raise ValueError('Reviewed preflight hash mismatch')
    saved_preflight = json.loads(PREVIEW.read_text())
    for key in ('contract', 'manifest', 'parent_manifest', 'interruption_audit', 'eligible_unattempted_ids',
                'interruption_audit_correction', 'ambiguous_id_excluded', 'canonical_denominator',
                'all60_P2_tokens_sha256', 'selected_records'):
        if saved_preflight.get(key) != report.get(key):
            raise ValueError('Current preflight differs from reviewed preflight: ' + key)
    output = plan['output']; events = output.with_name(output.name + '.events.jsonl')
    terminal = output.with_name(output.name + '.terminal.json')
    journal = CONTINUATION / 'execution-journal.jsonl'
    if any(p.exists() for p in (output, events, terminal, journal)):
        raise ValueError('Continuation output or journal already exists')
    from specialist_benchmark import generated_messages
    from semif_phase1 import mlx_backend as backend
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler
    started = time.perf_counter()
    model, native_tok, metadata = backend.load_model(args.model_path, args.revision, args.bits)
    load_seconds = time.perf_counter() - started
    controls = plan['configuration']['controls']
    actual_meta = dict(metadata, enable_thinking=False, max_tokens=2048, temperature=0)
    if actual_meta != plan['baseline'][0]['metadata']:
        raise ValueError('Effective native metadata differs from frozen baseline')
    original.exact_token_check(plan, args, native_tok)
    attempt_id = str(uuid.uuid4())
    count = 0
    with output.open('x') as out, events.open('x') as event_file, journal.open('x') as local_journal:
        local_journal.write(json.dumps({'event': 'continuation_started', 'attempt_id': attempt_id,
            'utc': utc(), 'manifest': plan['manifest_binding'], 'eligible_ids': ELIGIBLE,
            'ambiguous_id_excluded': 'DEV-033'}) + '\n')
        local_journal.flush(); os.fsync(local_journal.fileno())
        try:
            for row, token in zip(plan['rows'][33:], report['selected_records']):
                if row['id'] != token['id'] or row['id'] not in ELIGIBLE:
                    raise ValueError('Continuation record escaped allowlist')
                messages = generated_messages(row['feedback'], plan['policy'], 'P2', plan['configuration']['parent_baseline_id'])
                prompt = native_tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
                if gates.sha(prompt.encode()) != token['rendered_prompt_sha256'] or len(native_tok.encode(prompt)) != token['generation_input_tokens']:
                    raise ValueError('Native request differs from exact preflight')
                rec = {'id': row['id'], 'requested_model': args.model_path, 'artifact_revision': args.revision,
                    'surface': 'semif local specialist', 'mode': 'generated', 'host': platform.platform(),
                    'runtime_versions': controls['runtime'], 'config_note': args.config_note,
                    'model_load_seconds': load_seconds, 'input_sha256': gates.sha(row['feedback'].encode()),
                    'policy_sha256': gates.sha(plan['policy'].encode()),
                    'request_sha256': gates.canonical(make_payload(row['feedback'], plan['policy'], 'not-sent', 'official')),
                    'request_hash_limitation': 'Legacy intent hash retained; generated_request_sha256 binds actual messages.',
                    'generated_request_sha256': gates.canonical(messages), 'messages': messages,
                    'rendered_prompt_sha256': token['rendered_prompt_sha256'], 'input_tokens': token['generation_input_tokens'],
                    'metadata': actual_meta, 'attempts': 1, 'execution_manifest': plan['manifest_binding'],
                    'parent_execution_manifest': report['parent_manifest'], 'execution_stage': 'development_continuation',
                    'native_controls': controls, 'continuation_attempt_id': attempt_id,
                    'reference_labels_read': False,
                    'prompt_variant': compose_instruction(gates.bound(plan['configuration']['baseline_instruction'], ROOT).decode(),
                        'P2', role='system', parent_baseline_id=plan['configuration']['parent_baseline_id'], root=ROOT)['audit'],
                    'started_utc': utc()}
                event_file.write(json.dumps({'event': 'started', 'id': row['id'], 'utc': rec['started_utc'],
                    'generated_request_sha256': rec['generated_request_sha256']}) + '\n')
                event_file.flush(); os.fsync(event_file.fileno())
                call_started = time.perf_counter()
                try:
                    pieces = list(stream_generate(model, native_tok, prompt, max_tokens=2048, sampler=make_sampler(temp=0)))
                    stream = [{k: getattr(x, k) for k in ('text', 'token', 'from_draft', 'prompt_tokens', 'generation_tokens', 'finish_reason')} for x in pieces]
                    raw = ''.join(x.text for x in pieces); finish = pieces[-1].finish_reason if pieces else None
                    prediction = original.parse(raw, finish == 'stop')
                    rec.update(raw_response={'content': raw, 'finish_reason': finish}, stream_events=stream,
                        eos_token_ids=list(native_tok.eos_token_ids), prediction=prediction,
                        status='ok' if valid(prediction) else 'invalid_output',
                        output_tokens=pieces[-1].generation_tokens if pieces else 0)
                    if any(x.prompt_tokens != rec['input_tokens'] for x in pieces):
                        raise ValueError('Native generation token count differs')
                except Exception as exc:
                    rec.update(prediction=None, status='service_error', error_type=type(exc).__name__, error=str(exc)[:500])
                rec.update(elapsed_seconds=time.perf_counter() - call_started, finished_utc=utc())
                out.write(json.dumps(rec) + '\n'); out.flush(); os.fsync(out.fileno()); count += 1
                event_file.write(json.dumps({'event': 'finished', 'id': row['id'], 'utc': rec['finished_utc'],
                    'status': rec['status']}) + '\n')
                event_file.flush(); os.fsync(event_file.fileno())
                print(row['id'], rec['status'], flush=True)
                if rec['status'] == 'service_error' or rec.get('raw_response', {}).get('finish_reason') != 'stop':
                    break
            completed = count == len(ELIGIBLE) and rec['status'] != 'service_error' and rec.get('raw_response', {}).get('finish_reason') == 'stop'
            state = 'completed_remaining27' if completed else 'stopped'
        except BaseException as exc:
            state = 'stopped'
            local_journal.write(json.dumps({'event': 'continuation_stopped', 'attempt_id': attempt_id,
                'utc': utc(), 'records_saved': count, 'exception': type(exc).__name__, 'error': str(exc)[:500]}) + '\n')
            local_journal.flush(); os.fsync(local_journal.fileno())
            exclusive(terminal, {'status': state, 'records_saved': count, 'expected_remaining': 27,
                'ambiguous_id': 'DEV-033', 'utc': utc(), 'manifest': plan['manifest_binding']})
            raise
        local_journal.write(json.dumps({'event': 'continuation_finished', 'attempt_id': attempt_id,
            'utc': utc(), 'records_saved': count, 'status': state}) + '\n')
        local_journal.flush(); os.fsync(local_journal.fileno())
    exclusive(terminal, {'status': state, 'records_saved': count, 'expected_remaining': 27,
        'ambiguous_id': 'DEV-033', 'utc': utc(), 'manifest': plan['manifest_binding']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--preflight', action='store_true', help='Offline hashes and tokenizer check; no model load')
    action.add_argument('--run', action='store_true', help='Run only after review of manifest and preflight hashes')
    parser.add_argument('--approved-manifest-sha256', required=True)
    parser.add_argument('--approved-preflight-sha256', help='Required with --run')
    parser.add_argument('--review-receipt', help='Separate root-review execution receipt; required with --run')
    parser.add_argument('--review-receipt-sha256', help='SHA-256 of root-review receipt; required with --run')
    cli = parser.parse_args()
    if cli.run and not cli.approved_preflight_sha256:
        parser.error('--run requires --approved-preflight-sha256')
    if cli.run and (not cli.review_receipt or not cli.review_receipt_sha256):
        parser.error('--run requires --review-receipt and --review-receipt-sha256')
    os.environ.update(OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    if gates.sha(MANIFEST.read_bytes()) != cli.approved_manifest_sha256:
        raise ValueError('Reviewed continuation manifest hash mismatch')
    args, plan, report = offline_preflight(cli.approved_manifest_sha256)
    if cli.preflight:
        if PREVIEW.exists():
            raise FileExistsError(PREVIEW)
        exclusive(PREVIEW, report)
        print(json.dumps({'preflight': binding(PREVIEW, ROOT), 'eligible_ids': ELIGIBLE,
            'model_loaded': False, 'inference_performed': False}, indent=2))
    else:
        run(args, plan, report, cli.approved_preflight_sha256, cli.review_receipt, cli.review_receipt_sha256)


if __name__ == '__main__':
    main()
