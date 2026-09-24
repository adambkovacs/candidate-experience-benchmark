#!/usr/bin/env python3
"""Offline, fail-closed P0/P1/P2 audit for exact local SDK prompt conditions."""
import argparse
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, read_rows, score, valid
from evaluate_prompt_variants import compare
from reconcile_local_prompt_conditions import (PARENT_MANIFEST, V3_MANIFEST,
    digest, frozen_requests, load_condition, reconcile_saved_condition)

IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
DEST = Path('results/local-prompt-pairs-v1')


def rows(path):
    data = Path(path).read_bytes()
    if not data.endswith(b'\n'):
        raise ValueError('Incomplete JSONL evidence: ' + str(path))
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def hash_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()


def saved_cli_commit(value):
    if not isinstance(value, str):
        return None
    return value.removeprefix('CLI commit: ')


def saved_hardware_model(hardware):
    if not isinstance(hardware, dict):
        return None
    return hardware.get('identifier') or hardware.get('model')


def source(root, relative, expected=None):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    if expected is not None and digest(path) != expected:
        raise ValueError('Frozen source hash mismatch: ' + str(relative))
    return path


def visible_controls(row):
    info = row['model_info']
    return {'request_config': row['request']['config'], 'load_config': row['load_config'],
            'prediction_config': row['prediction_config'],
            'model_info': {key: value for key, value in info.items() if key != 'instanceReference'}}


def equal_visible_controls(left, right):
    a, b = visible_controls(left), visible_controls(right)
    for key in a:
        if a[key] != b[key]:
            raise ValueError('Different visible ' + key.replace('_', ' '))
    return a


def audit_native_split(row):
    """Check that SDK raw content supports its saved reasoning/nonreasoning split."""
    raw, reasoning, non = (row.get(k) for k in
                           ('raw_response', 'reasoning_content', 'non_reasoning_content'))
    if not all(isinstance(value, str) for value in (raw, reasoning, non)):
        raise ValueError('SDK native response split unavailable')
    parsing = row['request']['config']['reasoningParsing']
    permitted = {non} if reasoning == '' else set()
    if parsing.get('enabled') is True:
        start, end = parsing['startString'], parsing['endString']
        permitted.update((start + reasoning + end + non, reasoning + end + non))
        if non == '':
            permitted.update((start + reasoning, reasoning))
    if raw not in permitted or (parsing.get('enabled') is False and reasoning):
        raise ValueError('SDK raw response does not support saved split')


def audit_p0(root, parent, configuration):
    """Verify the historical single-record baseline, including original journal."""
    root = Path(root).resolve()
    config = parent['configs'][configuration]
    if config['surface'] != 'lmstudio_sdk':
        raise ValueError('P0 is not an SDK single-record baseline')
    baseline = Path(config['baseline_file'])
    manifest_path = Path(config['baseline_manifest_file'])
    for path in (baseline, manifest_path, Path('data/pilot/inputs.jsonl')):
        source(root, path, parent['source_sha256'][str(path)])
    journal_path = Path(str(baseline) + '.attempts.jsonl')
    manifest = json.loads(source(root, manifest_path).read_text())
    saved = rows(source(root, baseline))
    events = rows(source(root, journal_path))
    inputs = rows(source(root, Path('data/pilot/inputs.jsonl')))
    if ([x['id'] for x in inputs] != IDS or [x['id'] for x in saved] != IDS or len(events) != 120):
        raise ValueError('P0 lacks 60 ordered records or 120 journal events')
    if (manifest.get('status') != 'complete' or manifest.get('unique_records') != 60 or
        manifest.get('prediction_sha256') != digest(root / baseline) or
        manifest.get('valid_outputs') != sum(x.get('status') == 'ok' for x in saved) or
        manifest.get('thinking') not in ('on', 'off') or
        saved_cli_commit(manifest.get('lms_commit')) != parent['runtime']['cli_commit'] or
        manifest.get('lm_studio') != parent['runtime']['lm_studio_version'] or
        manifest.get('selected_gguf_runtime') != parent['runtime']['selected_engine'] or
        saved_hardware_model(manifest.get('hardware')) != parent['hardware']['model_identifier'] or
        manifest.get('artifact', {}).get('sha256') != config['artifact_sha256'] or
        manifest['artifact'].get('bytes') != config['artifact_bytes'] or
        manifest['artifact'].get('quantization') != 'Q4_K_M'):
        raise ValueError('P0 manifest does not bind frozen model/runtime/results')
    statuses = {}
    attempts = set()
    previous_started = None
    for i, (row, input_row) in enumerate(zip(saved, inputs)):
        start, finish = events[2 * i:2 * i + 2]
        model = row.get('model_info') or {}
        if (row.get('id') != input_row['id'] or row.get('requested_model') != config['identifier'] or
            row.get('surface') != 'LM Studio JavaScript SDK' or
            row.get('thinking') != manifest['thinking'] or
            row.get('artifact_sha256') != config['artifact_sha256'] or
            row.get('artifact_path') != config['artifact_path'] or
            row.get('template_sha256') != manifest.get('template_sha256') or
            row.get('format') != manifest.get('format') or
            row.get('timeout_seconds') * 1000 != config['timeout_ms'] or
            model.get('identifier') != config['identifier'] or
            model.get('path') != config['artifact_path'] or
            model.get('sizeBytes') != config['artifact_bytes'] or
            model.get('contextLength') != 8192 or
            (model.get('quantization') or {}).get('name') != 'Q4_K_M' or
            row.get('input_sha256') != hashlib.sha256(input_row['feedback'].encode()).hexdigest() or
            row.get('reference_labels_read') is not False):
            raise ValueError('P0 row model/input/control mismatch')
        if (row['attempt_id'] in attempts or
            not isinstance(row.get('started_utc'), str) or
            (previous_started is not None and row['started_utc'] < previous_started)):
            raise ValueError('P0 attempt ID or chronology mismatch')
        attempts.add(row['attempt_id'])
        previous_started = row['started_utc']
        messages = row['request']['messages']
        if (len(messages) != 2 or [x.get('role') for x in messages] != ['system', 'user'] or
            json.loads(messages[1]['content']) != {'feedback': input_row['feedback']} or
            messages[0]['content'] != saved[0]['request']['messages'][0]['content']):
            raise ValueError('P0 request role or input isolation mismatch')
        if ((start.get('event'), finish.get('event')) != ('started', 'finished') or any(
                event.get('id') != row['id'] or event.get('attempt_id') != row['attempt_id']
                for event in (start, finish)) or start.get('request_sha256') != hash_json(row['request']) or
                finish.get('status') != row.get('status')):
            raise ValueError('P0 journal/request linkage mismatch')
        audit_native_split(row)
        try:
            parsed = json.loads(row.get('non_reasoning_content'))
        except (TypeError, ValueError):
            parsed = None
        complete_json = valid(parsed) and row.get('stats', {}).get('stopReason') in ('eosFound', 'stopStringFound')
        if row['status'] == 'ok':
            if (not valid(parsed) or parsed != row.get('prediction') or
                row.get('stats', {}).get('stopReason') not in ('eosFound', 'stopStringFound')):
                raise ValueError('P0 valid output unsupported by raw response')
        elif row['status'] != 'invalid_output' or row.get('prediction') is not None:
            raise ValueError('P0 unsupported outcome status')
        elif complete_json:
            raise ValueError('P0 invalid status contradicts valid native JSON and normal stop')
        equal_visible_controls(saved[0], row)
        statuses[row['status']] = statuses.get(row['status'], 0) + 1
    return {'rows': saved, 'manifest': manifest, 'controls': visible_controls(saved[0]),
            'statuses': statuses,
            'sources': {name: {'file': str(path), 'sha256': digest(root / path)} for name, path in
                [('output', baseline), ('journal', journal_path), ('manifest', manifest_path)]}}


def evaluate(root, configuration):
    root = Path(root).resolve()
    parent_path = source(root, PARENT_MANIFEST)
    parent = json.loads(parent_path.read_text())
    tail_path = source(root, V3_MANIFEST)
    tail = json.loads(tail_path.read_text())
    order = [(c['configuration'], c['variant']) for c in tail['conditions']]
    scheduled = [v for c, v in order if c == configuration]
    if len(scheduled) != 2 or set(scheduled) != {'P1', 'P2'}:
        raise ValueError('Configuration lacks both exact tail conditions')
    schedule_path = Path(parent['schedule_file'])
    source(root, schedule_path, parent['source_sha256'][str(schedule_path)])
    schedule = json.loads((root / schedule_path).read_text())
    entry = [x for x in schedule['order'] if x['id'] == configuration]
    if len(entry) != 1 or entry[0]['conditions'] != scheduled:
        raise ValueError('Frozen condition order differs from global schedule')
    base = audit_p0(root, parent, configuration)
    refs = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
    audited = {}
    for variant in ('P1', 'P2'):
        condition = load_condition(root, configuration, variant)
        frozen = frozen_requests(root, condition)
        report_path = DEST.parent / 'local-prompt-condition-reconciliations-v1' / configuration / (variant + '.json')
        saved_report = json.loads(source(root, report_path).read_text())
        actual = reconcile_saved_condition(root, condition, frozen, refs, pairs)
        if saved_report != actual or not actual['coverage_complete'] or actual['terminal_status'] != 'completed' or actual['unknown_outcome_ids'] or actual['never_sent_ids']:
            raise ValueError(variant + ' scorer report is absent, partial or differs from actual evidence')
        output_path = root / condition.directory / 'development.jsonl'
        saved = rows(output_path)
        if len(saved) != 60 or [x['id'] for x in saved] != IDS:
            raise ValueError(variant + ' lacks ordered 60 saved requests')
        for i, (p0, row) in enumerate(zip(base['rows'], saved)):
            equal_visible_controls(p0, row)
            audit_native_split(row)
            if row['request']['messages'][1] != p0['request']['messages'][1]:
                raise ValueError(variant + ' feedback or user role differs from P0')
            if row['request'] != frozen[i]['request']:
                raise ValueError(variant + ' request differs from frozen prompt')
        runtime = actual['resource']['runtime_attestation']
        if (runtime['cli_commit'] != saved_cli_commit(base['manifest']['lms_commit']) or
            runtime['lm_studio_version'] != base['manifest']['lm_studio'] or
            runtime['selected_engine'] != base['manifest']['selected_gguf_runtime'] or
            runtime['artifact_sha256'] != parent['configs'][configuration]['artifact_sha256']):
            raise ValueError(variant + ' runtime differs from historical P0')
        audited[variant] = {'report': actual, 'rows': saved, 'report_file': str(report_path)}
    indexes = {'P0': {r['id']: {'id': r['id'], 'status': r['status'], 'prediction': r.get('prediction')}
                      for r in base['rows']}}
    for variant in ('P1', 'P2'):
        indexes[variant] = {r['id']: {'id': r['id'], 'status': r['decision']['status'],
                            'prediction': r['decision'].get('prediction')} for r in audited[variant]['rows']}
    references = {r['id']: r for r in refs}
    comparisons = {a + '_to_' + b: compare(indexes[a], indexes[b], references)
                   for a, b in [('P0', 'P1'), ('P0', 'P2'), ('P1', 'P2')]}
    return {'version': 'local-prompt-pairs-v1', 'configuration': configuration,
            'eligible_paired_comparison': True, 'controls_verified': True,
            'protocol': 'observational local single-record development comparison',
            'denominator': 60, 'condition_order': scheduled,
            'historical_p0_limitation': 'P0 ran earlier than P1/P2. Time, cache and stochastic sampling are not controlled.',
            'reference_status': 'AI-reviewed provisional development labels; not held-out human truth',
            'conditions': {'P0': {'evaluation': score(refs, list(indexes['P0'].values()), pairs),
                                  'sources': base['sources']},
                           **{v: {'evaluation': audited[v]['report']['evaluation'],
                                  'sources': {'scorer_report': {'file': audited[v]['report_file'],
                                      'sha256': digest(root / audited[v]['report_file'])},
                                      'development': audited[v]['report']['sources']['development']}}
                              for v in ('P1', 'P2')}},
            'comparisons': comparisons,
            'sources': {'parent_manifest': {'file': str(PARENT_MANIFEST), 'sha256': digest(parent_path)},
                        'tail_manifest': {'file': str(V3_MANIFEST), 'sha256': digest(tail_path)},
                        'schedule': {'file': str(schedule_path), 'sha256': digest(root / schedule_path)}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = evaluate(ROOT, args.config)
    if args.write:
        path = ROOT / DEST / (args.config + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            json.dump(report, out, indent=2)
            out.write('\n')
        print(path.relative_to(ROOT), digest(path))
    else:
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
