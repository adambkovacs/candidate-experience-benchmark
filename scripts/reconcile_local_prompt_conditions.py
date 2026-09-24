#!/usr/bin/env python3
"""Offline reconciliation for the scoped local P1 and its ten exact local successors.

No model clients are imported. A condition needs a terminal before it can be
scored; an open journal or a missing terminal is not a completed attempt.
"""
import argparse
import hashlib
import json
import math
import statistics
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from development_benchmark import KEYS, read_rows, score, valid

ROOT = Path(__file__).resolve().parents[1]
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PARENT_MANIFEST = Path('results/local-prompt-exact-v1/manifest.json')
PARENT_CONTROLLER = Path('scripts/local_prompt_execution_v1.cjs')
V2_MANIFEST = Path('results/local-prompt-remaining-v2/manifest.json')
V2_CONTROLLER = Path('scripts/local_prompt_remaining_v2.cjs')
V3_MANIFEST = Path('results/local-prompt-tail-v3/manifest.json')
V3_CONTROLLER = Path('scripts/local_prompt_tail_v3.cjs')
DEST = Path('results/local-prompt-condition-reconciliations-v1')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_path(root, relative):
    p = Path(relative)
    if p.is_absolute() or '..' in p.parts:
        raise ValueError(f'Unsafe source path: {relative}')
    full = (root / p).resolve()
    full.relative_to(root.resolve())
    return full


def bound_json(root, relative, expected=None):
    p = checked_path(root, relative)
    actual = digest(p)
    if expected is not None and actual != expected:
        raise ValueError(f'Source hash drift: {relative}')
    return json.loads(p.read_text()), actual


def jsonl(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError(f'Incomplete JSONL line: {path}')
    chunks = [line for line in raw.splitlines() if line.strip()]
    return [json.loads(line) for line in chunks], [hashlib.sha256(line).hexdigest() for line in chunks]


def audit_predecessor(root, condition):
    """Bind a tail condition to the actual sealed prior development evidence."""
    if condition.manifest_file != V3_MANIFEST:
        return None
    manifest, _ = bound_json(root, V3_MANIFEST, condition.manifest_sha256)
    order = [(c['configuration'], c['variant']) for c in manifest['conditions']]
    index = order.index((condition.configuration, condition.variant))
    if index == 0:
        previous = manifest['predecessor']
        base = checked_path(root, previous['output_dir'])
        manifest_hash, controller_hash = previous['manifest_sha256'], previous['controller_sha256']
    else:
        previous = manifest['conditions'][index - 1]
        base = checked_path(root, str(Path('results/local-prompt-tail-v3') /
                                      previous['configuration'] / previous['variant']))
        manifest_hash, controller_hash = condition.manifest_sha256, condition.controller_sha256
    files = {'terminal': base / 'development.terminal.json',
             'output': base / 'development.jsonl',
             'journal': base / 'development.attempts.jsonl'}
    hashes = {name: digest(path) for name, path in files.items()}
    terminal = json.loads(files['terminal'].read_text())
    if (terminal.get('configuration'), terminal.get('variant'), terminal.get('phase'),
        terminal.get('status')) != (previous['configuration'], previous['variant'],
                                    'development', 'completed'):
        raise ValueError('Predecessor has no completed development terminal')
    if (terminal.get('manifest_sha256') != manifest_hash or
        terminal.get('controller_sha256') != controller_hash or
        terminal.get('output_sha256') != hashes['output'] or
        terminal.get('journal_sha256') != hashes['journal'] or
        any(terminal.get(k) != 60 for k in ('requested_records', 'saved_rows',
                                           'claimed_attempts', 'finished_attempts')) or
        terminal.get('ambiguous_timeout') is not False):
        raise ValueError('Predecessor terminal or source hash mismatch')
    rows, line_hashes = jsonl(files['output'])
    events, _ = jsonl(files['journal'])
    if ([r.get('id') for r in rows] != IDS or len(events) != 120 or
        any(r.get('manifest_sha256') != manifest_hash or
            r.get('controller_sha256') != controller_hash or
            (r.get('decision') or {}).get('status') not in ('ok', 'invalid_output')
            for r in rows)):
        raise ValueError('Predecessor output is not the completed frozen condition')
    for i, row in enumerate(rows):
        start, finish = events[2 * i:2 * i + 2]
        if ((start.get('event'), finish.get('event')) != ('started', 'finished') or any(
                event.get('id') != row['id'] or event.get('attempt_id') != row.get('attempt_id')
                for event in (start, finish)) or finish.get('status') != row['decision']['status'] or
                finish.get('output_sha256') != line_hashes[i] or
                start.get('request_sha256') != row.get('request_sha256')):
            raise ValueError('Predecessor journal/output linkage mismatch')
    return {'hashes': hashes, 'sources': {name: {'file': str(path.relative_to(root)),
                                               'sha256': hashes[name]}
                                         for name, path in files.items()}}


@dataclass(frozen=True)
class Condition:
    configuration: str
    variant: str
    directory: Path
    manifest_file: Path
    controller_file: Path
    manifest_sha256: str
    controller_sha256: str
    parent: dict


def load_condition(root, configuration, variant):
    root = Path(root).resolve()
    if variant not in ('P1', 'P2'):
        raise ValueError('Variant must be P1 or P2')
    v2, v2_hash = bound_json(root, V2_MANIFEST)
    v3, v3_hash = bound_json(root, V3_MANIFEST)
    parent, parent_hash = bound_json(root, PARENT_MANIFEST)
    if (v2.get('version'), v3.get('version'), parent.get('version')) != (
            'local-prompt-remaining-v2', 'local-prompt-tail-v3', 'local-prompt-exact-v1'):
        raise ValueError('Unexpected manifest version')
    for manifest in (v2, v3):
        if (manifest['parent']['manifest_sha256'] != parent_hash or
            manifest['parent']['controller_sha256'] != digest(root / PARENT_CONTROLLER)):
            raise ValueError('Frozen parent source drift')
    if (v3['predecessor']['manifest_sha256'] != v2_hash or
        v3['predecessor']['controller_sha256'] != digest(root / V2_CONTROLLER)):
        raise ValueError('Scoped P1 source drift')
    if configuration == v2['configuration'] and variant == v2['variant']:
        manifest_file, controller_file, manifest, manifest_hash = V2_MANIFEST, V2_CONTROLLER, v2, v2_hash
        directory = Path('results/local-prompt-remaining-v2')
    elif {'configuration': configuration, 'variant': variant} in [
            {k: row[k] for k in ('configuration', 'variant')} for row in v3['conditions']]:
        manifest_file, controller_file, manifest, manifest_hash = V3_MANIFEST, V3_CONTROLLER, v3, v3_hash
        directory = Path('results/local-prompt-tail-v3') / configuration / variant
    else:
        raise ValueError('Condition outside reviewed v2/v3 allowlists')
    controller_hash = digest(root / controller_file)
    if manifest['controller_sha256'] != controller_hash:
        raise ValueError('Controller source drift')
    config = parent['configs'].get(configuration)
    if not config or variant not in config['conditions'] or config['surface'] != 'lmstudio_sdk':
        raise ValueError('Condition not a frozen local SDK configuration')
    return Condition(configuration, variant, directory, manifest_file,
                     controller_file, manifest_hash, controller_hash, parent)


def frozen_requests(root, condition):
    """Rebuild selected input-only requests without testing today's installed SDK."""
    code = r'''const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const root=process.argv[1],c=process.argv[2],v=process.argv[3];
const file=p=>{assert(!path.isAbsolute(p)&&!p.split('/').includes('..'));return path.join(root,p)};
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const read=p=>JSON.parse(fs.readFileSync(file(p),'utf8'));
const lines=p=>fs.readFileSync(file(p),'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const m=read('results/local-prompt-exact-v1/manifest.json'),cfg=m.configs[c];
assert.equal(m.version,'local-prompt-exact-v1');assert(cfg&&cfg.surface==='lmstudio_sdk');
assert(cfg.conditions.includes(v));
for(const p of ['data/pilot/inputs.jsonl',m.sdk_rendered_file,cfg.baseline_file,
                cfg.baseline_manifest_file,cfg.counts_file,
                'prompts/variants-v1/P1-classifier.txt','prompts/variants-v1/P2-classifier-sop.txt',
                'scripts/frozen_prompt_variants.cjs']) {
  assert.equal(hash(fs.readFileSync(file(p))),m.source_sha256[p],`Source drift: ${p}`);
}
const {compose_instruction}=require(file('scripts/frozen_prompt_variants.cjs'));
const feedback=new Map(lines('data/pilot/inputs.jsonl').map(x=>[x.id,x.feedback]));
const baseline=new Map(lines(cfg.baseline_file).map(x=>[x.id,x]));
const counts=new Map(lines(cfg.counts_file).filter(x=>x.configuration===c).map(x=>[x.variant+'/'+x.id,x]));
const records=lines(m.sdk_rendered_file).filter(x=>x.configuration===c&&x.variant===v);
const baseHash=hash(fs.readFileSync(file(cfg.baseline_file)));
assert.equal(records.length,60);assert.equal(baseline.size,60);assert.equal(feedback.size,60);
const rows=records.map((x,i)=>{
  assert.equal(x.id,`DEV-${String(i+1).padStart(3,'0')}`);
  const b=baseline.get(x.id),counted=counts.get(v+'/'+x.id);
  assert(b&&counted);assert.equal(x.source_file,cfg.baseline_file);assert.equal(x.source_sha256,baseHash);
  assert.deepEqual(JSON.parse(x.messages[1].content),{feedback:feedback.get(x.id)});
  const composed=compose_instruction(b.request.messages[0].content,v,{role:'system',parent_baseline_id:c});
  assert.equal(x.messages[0].content,composed.instruction);assert.deepEqual(x.composition_audit,composed.audit);
  const request={messages:x.messages,config:b.request.config};
  assert.equal(hash(Buffer.from(JSON.stringify(request))),x.request_sha256);
  assert.equal(hash(Buffer.from(x.rendered)),x.rendered_sha256);
  assert.equal(counted.rendered_sha256,x.rendered_sha256);
  assert.equal(counted.output_reserve,cfg.output_reserve);assert.equal(counted.context,cfg.context);
  assert(counted.prompt_tokens+cfg.native_token_delta+cfg.output_reserve<=cfg.context);
  return {id:x.id,request,request_sha256:x.request_sha256,
    rendered_sha256:counted.rendered_sha256,
    expected_prompt_tokens:counted.prompt_tokens+cfg.native_token_delta,
    prediction_config:b.prediction_config,load_config:b.load_config};
});
process.stdout.write(JSON.stringify(rows));'''
    result = subprocess.run(['node', '-e', code, str(root), condition.configuration,
                             condition.variant], capture_output=True, text=True, timeout=60,
                            check=True, cwd=root)
    rows = json.loads(result.stdout)
    if [row['id'] for row in rows] != IDS:
        raise ValueError('Frozen request reconstruction differs from 60 canonical IDs')
    return rows


def audit_runtime(row, terminal, config, parent, expected):
    runtime = row.get('runtime_attestation')
    if runtime != terminal.get('runtime_attestation') or not isinstance(runtime, dict):
        raise ValueError('Runtime attestation differs from terminal')
    if any(runtime.get(k) != v for k, v in {
            'cli_commit': parent['runtime']['cli_commit'],
            'selected_engine': parent['runtime']['selected_engine'],
            'lm_studio_version': parent['runtime']['lm_studio_version'],
            'hardware': parent['hardware'], 'artifact_sha256': config['artifact_sha256'],
            'surface': 'lmstudio_sdk'}.items()):
        raise ValueError('Frozen runtime or artifact mismatch')
    loaded = runtime.get('loaded_model_line')
    if not isinstance(loaded, str) or config['identifier'] not in loaded:
        raise ValueError('Loaded model identity missing from runtime')
    if (row.get('model_identifier') != config['identifier'] or
        row.get('model_path') != config['artifact_path'] or
        row.get('timeout_ms') != config['timeout_ms'] or
        row.get('rendered_sha256') != expected['rendered_sha256'] or
        row.get('expected_prompt_tokens') != expected['expected_prompt_tokens'] or
        row.get('reference_labels_read') is not False):
        raise ValueError('Frozen request/model controls differ')
    if row.get('request') != expected['request'] or row.get('request_sha256') != expected['request_sha256']:
        raise ValueError('Actual request differs from frozen reconstruction')
    status = (row.get('decision') or {}).get('status')
    if status in ('ok', 'invalid_output'):
        info = row.get('model_info') or {}
        if (info.get('identifier') != config['identifier'] or
            info.get('path') != config['artifact_path'] or
            info.get('sizeBytes') != config['artifact_bytes'] or
            info.get('contextLength') != 8192 or
            (info.get('quantization') or {}).get('name') != 'Q4_K_M' or
            row.get('prediction_config') != expected['prediction_config'] or
            row.get('load_config') != expected['load_config']):
            raise ValueError('Returned model, quantization, context or SDK config mismatch')
        stats = row.get('stats') or {}
        if stats.get('promptTokensCount') != expected['expected_prompt_tokens']:
            raise ValueError('Native prompt token count mismatch')
        non = row.get('non_reasoning_content')
        try:
            parsed = json.loads(non) if isinstance(non, str) else None
        except (TypeError, ValueError):
            parsed = None
        if status == 'ok' and (not valid(parsed) or parsed != row['decision'].get('prediction') or
                               stats.get('stopReason') not in ('eosFound', 'stopStringFound')):
            raise ValueError('Valid outcome does not match strict native response')
        if status == 'invalid_output' and valid(parsed) and stats.get('stopReason') in ('eosFound', 'stopStringFound'):
            raise ValueError('Invalid outcome contradicts strict native response')
    elif status not in ('control_failure', 'service_failure', 'timeout'):
        raise ValueError('Unknown saved outcome status')


def audit_phase(root, condition, phase, frozen, predecessor=None):
    base = root / condition.directory
    output = base / f'{phase}.jsonl'
    journal = base / f'{phase}.attempts.jsonl'
    terminal_path = base / f'{phase}.terminal.json'
    if not terminal_path.exists():
        raise ValueError(f'No terminal for {condition.configuration}/{condition.variant}/{phase}; live or unstarted')
    terminal = json.loads(terminal_path.read_text())
    rows, line_hashes = jsonl(output)
    events, _ = jsonl(journal)
    if (terminal.get('configuration'), terminal.get('variant'), terminal.get('phase')) != (
            condition.configuration, condition.variant, phase):
        raise ValueError('Terminal identity mismatch')
    if (terminal.get('manifest_sha256') != condition.manifest_sha256 or
        terminal.get('controller_sha256') != condition.controller_sha256 or
        terminal.get('output_sha256') != digest(output) or
        terminal.get('journal_sha256') != digest(journal)):
        raise ValueError('Terminal/source hash mismatch')
    if predecessor and terminal.get('predecessor_terminal_sha256') != predecessor['hashes']['terminal']:
        raise ValueError('Terminal predecessor hash mismatch')
    if terminal.get('status') not in ('completed', 'stopped'):
        raise ValueError('Unsealed terminal state')
    config = condition.parent['configs'][condition.configuration]
    runtime = terminal.get('runtime_attestation') or {}
    if (terminal.get('timeout_ms') != config['timeout_ms'] or
        runtime.get('cli_commit') != condition.parent['runtime']['cli_commit'] or
        runtime.get('selected_engine') != condition.parent['runtime']['selected_engine'] or
        runtime.get('lm_studio_version') != condition.parent['runtime']['lm_studio_version'] or
        runtime.get('hardware') != condition.parent['hardware'] or
        runtime.get('artifact_sha256') != config['artifact_sha256'] or
        runtime.get('surface') != 'lmstudio_sdk' or
        config['identifier'] not in runtime.get('loaded_model_line', '')):
        raise ValueError('Terminal runtime/model controls differ from frozen source')
    expected_ids = IDS[:3] if phase == 'smoke' else IDS
    selected = frozen[:3] if phase == 'smoke' else frozen
    if [r.get('id') for r in rows] != expected_ids[:len(rows)] or len(rows) > len(selected):
        raise ValueError('Output IDs differ from canonical prefix')
    if terminal.get('requested_records') != len(selected) or terminal.get('saved_rows') != len(rows):
        raise ValueError('Terminal row count mismatch')
    if len(events) not in (2 * len(rows), 2 * len(rows) + 1):
        raise ValueError('Journal has unmatched or missing attempt events')
    pending = [events[-1]['id']] if len(events) % 2 else []
    if not rows and not pending:
        raise ValueError('Terminal contains no finished or claimed request')
    if pending and (len(rows) == len(selected) or
                    events[-1].get('event') != 'started' or
                    events[-1].get('id') != expected_ids[len(rows)] or
                    events[-1].get('request_sha256') != selected[len(rows)]['request_sha256'] or
                    events[-1].get('manifest_sha256') != condition.manifest_sha256 or
                    not events[-1].get('attempt_id')):
        raise ValueError('Unfinished attempt differs from next frozen request')
    statuses = Counter()
    for i, (row, frozen_row) in enumerate(zip(rows, selected)):
        start, finish = events[2 * i:2 * i + 2]
        status = (row.get('decision') or {}).get('status')
        if (row.get('configuration'), row.get('variant'), row.get('phase')) != (
                condition.configuration, condition.variant, phase):
            raise ValueError('Output identity mismatch')
        if row.get('manifest_sha256') != condition.manifest_sha256 or row.get('controller_sha256') != condition.controller_sha256:
            raise ValueError('Output source binding mismatch')
        if predecessor and row.get('predecessor_terminal_sha256') != predecessor['hashes']['terminal']:
            raise ValueError('Output predecessor hash mismatch')
        if (start.get('event'), finish.get('event')) != ('started', 'finished') or any(
                e.get('id') != row['id'] or e.get('attempt_id') != row.get('attempt_id') for e in (start, finish)):
            raise ValueError('Attempt identity mismatch')
        if (start.get('request_sha256') != frozen_row['request_sha256'] or
            start.get('manifest_sha256') != condition.manifest_sha256 or
            finish.get('output_sha256') != line_hashes[i] or finish.get('status') != status):
            raise ValueError('Request or output journal hash mismatch')
        audit_runtime(row, terminal, config, condition.parent, frozen_row)
        statuses[status] += 1
    if (terminal.get('claimed_attempts') != len(rows) + len(pending) or
        terminal.get('finished_attempts') != len(rows) or
        terminal.get('ok_rows') != statuses['ok'] or
        terminal.get('invalid_output_rows') != statuses['invalid_output']):
        raise ValueError('Terminal attempt/status counts mismatch')
    if terminal['status'] == 'completed':
        if (len(rows) != len(selected) or pending or terminal.get('ambiguous_timeout') is not False or
            terminal.get('stopped_reason') is not None or
            any(statuses[s] for s in ('control_failure', 'service_failure', 'timeout'))):
            raise ValueError('Completed terminal contains gaps or stopping failure')
    elif len(rows) == len(selected) and not pending and not any(statuses[s] for s in ('control_failure', 'service_failure', 'timeout')):
        raise ValueError('Stopped terminal lacks a stopping failure')
    if terminal['status'] == 'stopped' and not terminal.get('stopped_reason'):
        raise ValueError('Stopped terminal lacks reason')
    return {'rows': rows, 'events': events, 'terminal': terminal, 'pending': pending,
            'statuses': statuses, 'sources': {k: {'file': str(p.relative_to(root)), 'sha256': digest(p)}
                for k, p in [('output', output), ('journal', journal), ('terminal', terminal_path)]}}


def usage_and_timing(rows):
    missing_usage, prompt_tokens, completion_tokens, elapsed = [], 0, 0, []
    missing_elapsed = []
    for row in rows:
        stats = row.get('stats') or {}
        p, c = stats.get('promptTokensCount'), stats.get('predictedTokensCount')
        if type(p) is int and type(c) is int and p >= 0 and c >= 0:
            prompt_tokens += p
            completion_tokens += c
        else:
            missing_usage.append(row['id'])
        t = row.get('elapsed_seconds')
        if isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) and t >= 0:
            elapsed.append(t)
        else:
            missing_elapsed.append(row['id'])
    return {'request_count': len(rows), 'prompt_tokens_observed_sum': prompt_tokens,
            'completion_tokens_observed_sum': completion_tokens, 'usage_missing_ids': missing_usage,
            'elapsed_prediction_seconds_observed_count': len(elapsed),
            'elapsed_prediction_seconds_sum': sum(elapsed),
            'elapsed_prediction_seconds_median': statistics.median(elapsed) if elapsed else None,
            'elapsed_prediction_seconds_p95_nearest_rank': sorted(elapsed)[math.ceil(.95 * len(elapsed)) - 1] if elapsed else None,
            'elapsed_missing_ids': missing_elapsed}


def reconcile_saved_condition(root, condition, frozen, refs, pairs):
    """Pure evidence reconciliation. Synthetic tests pass a temporary root and frozen rows."""
    root = Path(root).resolve()
    if [x['id'] for x in frozen] != IDS or [x['id'] for x in refs] != IDS:
        raise ValueError('Frozen requests or provisional references lack canonical 60')
    review_path = root / condition.directory / 'execution-review-root.json'
    review = json.loads(review_path.read_text())
    predecessor = audit_predecessor(root, condition)
    if (review.get('approved_for_execution') is not True or
        review.get('manifest_sha256') != condition.manifest_sha256 or
        review.get('controller_sha256') != condition.controller_sha256 or
        not {'smoke', 'development'}.issubset(set(review.get('approved_phases', [])))):
        raise ValueError('Execution review does not bind both phases and actual sources')
    if condition.manifest_file == V3_MANIFEST and (review.get('configuration'), review.get('variant')) != (
            condition.configuration, condition.variant):
        raise ValueError('Execution review belongs to another tail condition')
    if predecessor and any(review.get('predecessor_' + name + '_sha256') != predecessor['hashes'][name]
                           for name in ('terminal', 'output', 'journal')):
        raise ValueError('Execution review predecessor hash mismatch')
    smoke = audit_phase(root, condition, 'smoke', frozen, predecessor)
    if smoke['terminal']['status'] != 'completed':
        raise ValueError('Development requires completed three-record smoke')
    base = root / condition.directory
    inspection_path = base / 'smoke-inspection.json'
    inspection = json.loads(inspection_path.read_text())
    if ((inspection.get('configuration'), inspection.get('variant')) != (
            condition.configuration, condition.variant) or
        inspection.get('accepted_for_development') is not True or
        inspection.get('smoke_ids_inspected') != 3 or
        inspection.get('smoke_output_sha256') != smoke['sources']['output']['sha256'] or
        inspection.get('smoke_journal_sha256') != smoke['sources']['journal']['sha256'] or
        inspection.get('smoke_terminal_sha256') != smoke['sources']['terminal']['sha256']):
        raise ValueError('Smoke inspection does not bind completed smoke')
    development = audit_phase(root, condition, 'development', frozen, predecessor)
    rows = development['rows']
    predictions = [{'id': r['id'], 'status': r['decision']['status'],
        **({'prediction': r['decision']['prediction']} if r['decision']['status'] == 'ok' else {})} for r in rows]
    evaluation = score(refs, predictions, pairs)
    truth = {r['id']: r['proposed_labels'] for r in refs}
    all_four = sum(r['decision']['status'] == 'ok' and r['decision']['prediction'] == truth[r['id']] for r in rows)
    unknown = development['pending'][:]
    for r in rows:
        if r['decision']['status'] == 'timeout' and r['decision'].get('cancellation_acknowledged') is not True:
            unknown.append(r['id'])
    unknown = list(dict.fromkeys(unknown))
    never_sent = IDS[len(rows) + len(development['pending']):]
    coverage_complete = not unknown and not never_sent and len(rows) == 60
    source_files = {'manifest': condition.manifest_file, 'controller': condition.controller_file,
                    'parent_manifest': PARENT_MANIFEST, 'parent_controller': PARENT_CONTROLLER,
                    'execution_review': review_path.relative_to(root),
                    'smoke_inspection': inspection_path.relative_to(root),
                    'provisional_references': Path('data/pilot/proposed_labels.jsonl'),
                    'pairs': Path('data/pilot/pairs.json'),
                    'evaluator': Path('scripts/development_benchmark.py'),
                    'reconciler': Path('scripts/reconcile_local_prompt_conditions.py')}
    config = condition.parent['configs'][condition.configuration]
    source_files.update({'frozen_inputs': Path('data/pilot/inputs.jsonl'),
                         'frozen_rendered': Path(condition.parent['sdk_rendered_file']),
                         'frozen_counts': Path(config['counts_file']),
                         'frozen_baseline': Path(config['baseline_file']),
                         'frozen_baseline_manifest': Path(config['baseline_manifest_file']),
                         'prompt_p1': Path('prompts/variants-v1/P1-classifier.txt'),
                         'prompt_p2': Path('prompts/variants-v1/P2-classifier-sop.txt'),
                         'prompt_composer': Path('scripts/frozen_prompt_variants.cjs')})
    source = {key: {'file': str(p), 'sha256': digest(root / p)} for key, p in source_files.items()}
    return {'version': 'local-prompt-condition-reconciliation-v1',
            'configuration': condition.configuration, 'variant': condition.variant,
            'phase': 'development', 'denominator': 60,
            'terminal_status': development['terminal']['status'],
            'saved_rows': len(rows), 'claimed_attempts': development['terminal']['claimed_attempts'],
            'finished_attempts': development['terminal']['finished_attempts'],
            'status_counts': dict(development['statuses']),
            'unknown_outcome_ids': unknown, 'never_sent_ids': never_sent,
            'never_sent_count': len(never_sent), 'coverage_complete': coverage_complete,
            'valid_outputs': evaluation['valid_outputs'], 'all_four_correct': all_four,
            'evaluation': evaluation, 'reference_status': 'AI-reviewed provisional; development only',
            'resource': {'surface': 'lmstudio_sdk', 'cost_usd': None,
                'cost_note': 'Local inference; no provider bill. Electricity and device amortization unmeasured.',
                'runtime_attestation': development['terminal']['runtime_attestation'],
                'timeout_ms': development['terminal']['timeout_ms'],
                'development': usage_and_timing(rows), 'smoke': usage_and_timing(smoke['rows'])},
            'sources': {**source, 'smoke': smoke['sources'], 'development': development['sources'],
                        **({'predecessor': predecessor['sources']} if predecessor else {})}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--variant', choices=('P1', 'P2'), required=True)
    parser.add_argument('--write', action='store_true', help='Write a new immutable report; never overwrite.')
    args = parser.parse_args()
    root = ROOT
    condition = load_condition(root, args.config, args.variant)
    # Refuse an open/unstarted development phase before reading labels or output.
    if not (root / condition.directory / 'development.terminal.json').exists():
        raise SystemExit('No development terminal; live or unstarted condition is not scored')
    frozen = frozen_requests(root, condition)
    refs = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
    report = reconcile_saved_condition(root, condition, frozen, refs, pairs)
    if args.write:
        dest = root / DEST / args.config / f'{args.variant}.json'
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('x') as out:
            json.dump(report, out, indent=2)
            out.write('\n')
        print(dest.relative_to(root), digest(dest))
    else:
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
