#!/usr/bin/env python3
"""Build hash-bound, offline reports for completed Codex prompt repeat series."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import codex_batch_benchmark as batch_runner
import codex_repeat_roster as roster

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'codex-gpt-6-luna-medium-batch10'
SOL_CONFIG = 'codex-gpt-6-sol-high-batch10'
SOL_MEDIUM_CONFIG = 'codex-gpt-6-sol-medium-batch10'
REPEAT_ROOT = Path('results/repeatability-v1')
PAIR_ROOT = Path('results/prompt-comparison-v1-2026-09-24/paired-reports')
SERIES = ((CONFIG, 'GPT-6 Luna · medium effort'), (SOL_CONFIG, 'GPT-6 Sol · high effort'), (SOL_MEDIUM_CONFIG, 'GPT-6 Sol · medium effort'))
ROSTER_SERIES = (
    ('codex-gpt-5.6-luna-high', 'GPT-5.6 Luna · high effort'),
    ('codex-gpt-5.6-luna-low-phase2-batch10-p0', 'GPT-5.6 Luna · low effort'),
    ('codex-gpt-5.6-luna-medium', 'GPT-5.6 Luna · medium effort'),
    ('codex-gpt-5.6-sol-high', 'GPT-5.6 Sol · high effort'),
)
LABELS = Path('data/pilot/proposed_labels.jsonl')
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
CONDITIONS = ('P0', 'P1', 'P2')
PASSES = ('original', 'repeat2', 'repeat3')
PINNED_SHA = {
    str(LABELS): '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464',
    str(REPEAT_ROOT / CONFIG / 'repeat2/manifest.json'): 'ac6b282c5527ea1a263fd26c474e09b9475d36c7666b6bbde122166e72aca1f3',
    str(REPEAT_ROOT / CONFIG / 'repeat3/manifest.json'): 'b29ff4b0de2712beaacd66680bf6efdcc3f4ad6293df176477d6b01759b74c45',
    str(REPEAT_ROOT / SOL_CONFIG / 'repeat2/manifest.json'): 'a8ea850980a39ebc723c09e31d11c7e5a85701f3bb248b1d39630d630be07a48',
    str(REPEAT_ROOT / SOL_CONFIG / 'repeat3/manifest.json'): '5572258506b20d3308e504399b4deea337fe1642325b37453d87076871152c1e',
    str(REPEAT_ROOT / SOL_MEDIUM_CONFIG / 'repeat2/manifest.json'): '2a2ea73fee8c393c44d8224f15a5d58ff5e29bae3bb05df53d058967e5b46cc3',
    str(REPEAT_ROOT / SOL_MEDIUM_CONFIG / 'repeat3/manifest.json'): 'b708bc3cbaba4cbde3210f3ce476dc6b6c315860ca666fc5c928279b9ff70b6c',
    str(REPEAT_ROOT / 'codex-gpt-5.6-luna-high/repeat2/manifest.json'): '1c3e7bfc838660cd81d164e14c99c96a15dfe0dcb1109d00d88acff98cda7454',
    str(REPEAT_ROOT / 'codex-gpt-5.6-luna-high/repeat3/manifest.json'): 'a717166bc151c62e13423bf868d1d59daa30f451092015ab8aa588f7b7b6bd33',
    str(REPEAT_ROOT / 'codex-gpt-5.6-luna-low-phase2-batch10-p0/repeat2/manifest.json'): '5a21bbd04fbff23885869c786e24e6fcc1cd4e363fe0747e1d76efbe9abf40a1',
    str(REPEAT_ROOT / 'codex-gpt-5.6-luna-low-phase2-batch10-p0/repeat3/manifest.json'): '5ca19eb89b33598b80a4062d71a13e4fb0bc29c2ac0bf25c27cc55bcb8a686eb',
    str(REPEAT_ROOT / 'codex-gpt-5.6-luna-medium/repeat2/manifest.json'): '60be74ccb8aa4599026ac874e06dd5dae75008b6b4d9cbfe7418199333721670',
    str(REPEAT_ROOT / 'codex-gpt-5.6-luna-medium/repeat3/manifest.json'): '19e8a057dfb9e7fe1d38c55d92003047ca372d009548f22dd0a20ed2c857b23e',
    str(REPEAT_ROOT / 'codex-gpt-5.6-sol-high/repeat2/manifest.json'): '01e2100721ab9bc140cb8fb1b440bf7c9e040aa509ef9bd6ba9e42ab50622fe6',
    str(REPEAT_ROOT / 'codex-gpt-5.6-sol-high/repeat3/manifest.json'): '8fe9ffed84d41a7351858d5bf2f6595c23a99d1afa72942326b09d403f83f72c',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def binding(path, expected=None):
    resolved = (ROOT / path).resolve()
    resolved.relative_to(ROOT.resolve())
    digest = sha(resolved)
    if expected is not None and digest != expected:
        raise ValueError(f'Source SHA changed: {path}')
    return {'path': str(path), 'sha256': digest}


def completed_repeat(folder, repeat, condition, manifest_sha):
    """Read only the journal until a terminal completion signal is present."""
    journal = folder / 'development.journal.jsonl'
    if not (ROOT / journal).exists():
        return False
    try:
        events = rows(ROOT / journal)
    except (ValueError, OSError):
        return False
    if not events or events[-1].get('event') != 'phase_completed':
        return False
    if events[-1].get('request_count') != 6 or events[-1].get('record_count') != 60:
        raise ValueError(f'Invalid terminal counts: {journal}')
    if len(events) != 14 or [e['event'] for e in events] != ['phase_started', *['request_started', 'request_completed'] * 6, 'phase_completed']:
        raise ValueError(f'Invalid completed journal: {journal}')
    for index in range(6):
        started, finished = events[1 + index * 2:3 + index * 2]
        if started['batch_index'] != finished['batch_index'] or finished['status'] != 'ok' or started['manifest_sha256'] != manifest_sha:
            raise ValueError(f'Invalid completed request: {journal}')
    claim = json.loads((ROOT / folder / 'development.claim.json').read_text())
    if claim['manifest_sha256'] != manifest_sha or claim['repeat'] != repeat or claim['condition'] != condition:
        raise ValueError(f'Claim mismatch: {folder}')
    return True


def validate_evidence(records, attempts, ids, condition, repeat, manifest=None):
    if len(records) != 60 or len(attempts) != 6 or len({r['id'] for r in records}) != 60:
        raise ValueError(f'Incomplete/duplicate evidence: {repeat} {condition}')
    if [r['id'] for r in records] != ids:
        raise ValueError(f'Record order changed: {repeat} {condition}')
    for index, attempt in enumerate(attempts):
        members = ids[index * 10:(index + 1) * 10]
        if attempt['record_order'] != members or attempt['batch_size'] != 10:
            raise ValueError(f'Batch membership changed: {repeat} {condition}')
        if manifest is not None:
            planned = manifest['conditions'][condition]['development'][index]
            if attempt['manifest_sha256'] != manifest['_sha256'] or attempt['request_sha256'] != planned['request_sha256'] or attempt['schema_sha256'] != planned['schema_sha256']:
                raise ValueError(f'Request binding changed: {repeat} {condition}')
        for record in records[index * 10:(index + 1) * 10]:
            if record['request_sha256'] != attempt['request_sha256'] or record['status'] != attempt['status']:
                raise ValueError(f'Record/attempt disagreement: {repeat} {condition}')
            if manifest is not None and record['prediction'] != attempt['batch_predictions'].get(record['id']):
                raise ValueError(f'Prediction differs from completed attempt: {repeat} {condition}')
            if manifest is not None and (record['repeat'] != repeat or record['condition'] != condition or record['phase'] != 'development'):
                raise ValueError(f'Record identity changed: {repeat} {condition}')
    return {r['id']: r for r in records}


def outcome(record):
    prediction = record.get('prediction')
    if record.get('status') == 'ok' and isinstance(prediction, dict) and all(prediction.get(f) is not None for f in FIELDS):
        return 'valid'
    if record.get('status') == 'ok':
        return 'invalid_output'
    status = record.get('status')
    if status in ('invalid_output', 'refusal', 'timeout', 'service_error', 'isolation_violation', 'unknown_started', 'never_sent'):
        return status
    return 'other_error'


def score(records, labels, ids):
    counts = Counter(outcome(records[rid]) for rid in ids)
    by_field = {f: sum(outcome(records[rid]) == 'valid' and records[rid]['prediction'][f] == labels[rid][f] for rid in ids) for f in FIELDS}
    all_four = sum(outcome(records[rid]) == 'valid' and all(records[rid]['prediction'][f] == labels[rid][f] for f in FIELDS) for rid in ids)
    return {'denominator': 60, 'valid': counts['valid'], 'allFour': all_four, 'fields': by_field,
            'outcomes': {key: counts[key] for key in ('valid', 'invalid_output', 'refusal', 'timeout', 'service_error', 'isolation_violation', 'other_error', 'unknown_started', 'never_sent')},
            'invalidIds': [rid for rid in ids if outcome(records[rid]) != 'valid']}


def flip(a, b, ids):
    valid = [rid for rid in ids if outcome(a[rid]) == outcome(b[rid]) == 'valid']
    excluded = [rid for rid in ids if rid not in valid]
    result = {'denominator': len(valid), 'excludedIds': excluded}
    for field in (*FIELDS, 'fourFieldVector'):
        changed = [rid for rid in valid if (a[rid]['prediction'] if field == 'fourFieldVector' else a[rid]['prediction'][field]) != (b[rid]['prediction'] if field == 'fourFieldVector' else b[rid]['prediction'][field])]
        result[field] = {'changed': len(changed), 'rate': len(changed) / len(valid) if valid else None, 'caseIds': changed}
    return result


def usage(attempts):
    keys = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')
    token_totals = {key: sum(a['usage'][key] for a in attempts) if all(isinstance(a.get('usage'), dict) and isinstance(a['usage'].get(key), int) for a in attempts) else None for key in keys}
    elapsed = [a.get('elapsed_seconds') for a in attempts]
    return {'requestCount': len(attempts), 'requestSeconds': elapsed, 'requestSecondsTotal': sum(elapsed) if all(isinstance(x, (int, float)) for x in elapsed) else None,
            'tokens': token_totals, 'actualCostUsd': None, 'costNote': 'ChatGPT subscription; attributable request cost unavailable.'}


def build_series(config, display_name):
    base = REPEAT_ROOT / config
    pair_path = PAIR_ROOT / config / 'paired-manifest.json'
    sources = []
    labels_binding = binding(LABELS, PINNED_SHA[str(LABELS)]); sources.append(labels_binding)
    label_rows = rows(ROOT / LABELS)
    ids = [r['id'] for r in label_rows]
    if len(ids) != 60 or len(set(ids)) != 60 or any(r.get('review_version') != '0.2' for r in label_rows):
        raise ValueError('Expected 60 unique provisional v0.2 references')
    labels = {r['id']: r['proposed_labels'] for r in label_rows}
    pair_binding = binding(pair_path); sources.append(pair_binding)
    pair = json.loads((ROOT / pair_path).read_text())
    if pair['parent_baseline_id'] != config:
        raise ValueError(f'Historical paired configuration mismatch: {config}')
    data = {}; missing = []
    for pass_name in PASSES:
        data[pass_name] = {}
        manifest = None
        if pass_name != 'original':
            manifest_path = base / pass_name / 'manifest.json'
            manifest_binding = binding(manifest_path, PINNED_SHA[str(manifest_path)]); sources.append(manifest_binding)
            manifest = json.loads((ROOT / manifest_path).read_text()); manifest['_sha256'] = manifest_binding['sha256']
            if manifest['configuration_id'] != config or manifest['repeat'] != pass_name:
                raise ValueError('Manifest identity changed')
            if manifest['model'] != pair['controls']['requested_model'] or manifest['effort'] != pair['controls']['effort'] or manifest['batch_size'] != pair['controls']['configured_batch_size']:
                raise ValueError(f'Manifest controls differ from historical pair: {config}')
            for item in manifest['source_bindings']:
                binding(item['path'], item['sha256'])
        for condition in CONDITIONS:
            if pass_name == 'original':
                source = pair['conditions'][condition]
                record_binding = binding(source['predictions']['file'], source['predictions']['sha256'])
                attempt_binding = binding(source['request_evidence']['file'], source['request_evidence']['sha256'])
                journal_binding = None
            else:
                folder = base / pass_name / condition
                if not completed_repeat(folder, pass_name, condition, manifest['_sha256']):
                    missing.append({'pass': pass_name, 'condition': condition, 'status': 'incomplete_or_not_started'})
                    continue
                record_binding = binding(folder / 'development.records.jsonl')
                attempt_binding = binding(folder / 'development.attempts.jsonl')
                journal_binding = binding(folder / 'development.journal.jsonl')
                claim_binding = binding(folder / 'development.claim.json')
            records = rows(ROOT / record_binding['path']); attempts = rows(ROOT / attempt_binding['path'])
            indexed = validate_evidence(records, attempts, ids, condition, pass_name, manifest)
            entry = {'score': score(indexed, labels, ids), 'usage': usage(attempts), 'evidence': {'records': record_binding, 'attempts': attempt_binding}}
            if journal_binding:
                entry['evidence']['journal'] = journal_binding
                entry['evidence']['claim'] = claim_binding
            data[pass_name][condition] = entry
            sources.extend([record_binding, attempt_binding] + ([journal_binding, claim_binding] if journal_binding else []))
    pair_deltas = []
    for pass_name in PASSES:
        for target in ('P1', 'P2'):
            if 'P0' not in data[pass_name] or target not in data[pass_name]:
                continue
            baseline = data[pass_name]['P0']['score']; variant = data[pass_name][target]['score']
            pair_deltas.append({'pass': pass_name, 'from': 'P0', 'to': target, 'denominator': 60,
                                'allFour': variant['allFour'] - baseline['allFour'],
                                'fields': {field: variant['fields'][field] - baseline['fields'][field] for field in FIELDS}})
    paired_spread = {}
    for target in ('P1', 'P2'):
        entries = [d for d in pair_deltas if d['to'] == target]
        paired_spread[target] = {'completedPairs': len(entries), 'allFourValues': [d['allFour'] for d in entries],
                                 'allFourRange': [min(d['allFour'] for d in entries), max(d['allFour'] for d in entries)] if len(entries) == 3 else None,
                                 'fieldRanges': {f: [min(d['fields'][f] for d in entries), max(d['fields'][f] for d in entries)] if len(entries) == 3 else None for f in FIELDS}}
    flips = []
    for condition in CONDITIONS:
        for i, left in enumerate(PASSES):
            for right in PASSES[i + 1:]:
                if condition not in data[left] or condition not in data[right]: continue
                a = {r['id']: r for r in rows(ROOT / data[left][condition]['evidence']['records']['path'])}
                b = {r['id']: r for r in rows(ROOT / data[right][condition]['evidence']['records']['path'])}
                flips.append({'condition': condition, 'from': left, 'to': right, **flip(a, b, ids)})
    ranges = {}
    for condition in CONDITIONS:
        entries = [data[p][condition]['score'] for p in PASSES if condition in data[p]]
        def stats(values): return {'completedPasses': len(values), 'values': values, 'mean': sum(values)/len(values) if len(values) == 3 else None, 'range': [min(values), max(values)] if len(values) == 3 else None}
        ranges[condition] = {'allFour': stats([e['allFour'] for e in entries]), 'fields': {f: stats([e['fields'][f] for e in entries]) for f in FIELDS}}
    across = {}
    for condition in CONDITIONS:
        if any(condition not in data[p] for p in PASSES): continue
        triplet = [{r['id']: r for r in rows(ROOT / data[p][condition]['evidence']['records']['path'])} for p in PASSES]
        eligible = [rid for rid in ids if all(outcome(run[rid]) == 'valid' for run in triplet)]
        across[condition] = {'denominator': len(eligible), 'excludedIds': [rid for rid in ids if rid not in eligible],
                             'fields': {f: [rid for rid in eligible if len({run[rid]['prediction'][f] for run in triplet}) > 1] for f in FIELDS},
                             'fourFieldVector': [rid for rid in eligible if len({tuple(run[rid]['prediction'][f] for f in FIELDS) for run in triplet}) > 1]}
    return {'schema': 'repeat-findings-v1', 'configuration': config, 'displayName': display_name,
            'model': pair['controls']['requested_model'], 'effort': pair['controls']['effort'],
            'historicalControls': pair.get('historical_controls', pair['controls']),
            'repeatRuntimeAmendment': manifest['runtime_amendment'],
            'referenceVersion': '0.2', 'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items())) for field in FIELDS},
            'denominator': 60, 'completedConditions': sum(len(x) for x in data.values()), 'plannedConditions': 9, 'missingPasses': missing,
            'passes': data, 'threePassSummary': ranges, 'pairwiseFlips': flips, 'changesAcrossThreePasses': across,
            'withinPassPromptDeltas': pair_deltas, 'pairedDeltaSpread': paired_spread, 'sourceBindings': sources,
            'limitations': ['Same 60 synthetic records in every pass; observations are dependent.', 'Original CLI and repeat CLI differ by accepted patch amendment; equivalence is unproven.', 'Provider serving revision and effective seed are unavailable.', 'Batch timing is request timing; per-record shares are not independent latency.', 'Subscription request cost is unknown, not zero.']}


def validate_roster_phase(config, repeat, condition, phase, manifest, inspection_binding=None):
    """Bind sealed roster evidence, including saved raw output and public admission."""
    folder = REPEAT_ROOT / config / repeat / condition
    prefix = folder / phase
    claim_binding = binding(Path(str(prefix) + '.claim.json'))
    journal_binding = binding(Path(str(prefix) + '.journal.jsonl'))
    attempt_binding = binding(Path(str(prefix) + '.attempts.jsonl'))
    record_binding = binding(Path(str(prefix) + '.records.jsonl'))
    claim = json.loads((ROOT / claim_binding['path']).read_text())
    identity = {'repeat': repeat, 'condition': condition, 'phase': phase}
    if any(claim.get(k) != v for k, v in identity.items()) or claim.get('manifest_sha256') != manifest['_sha256']:
        raise ValueError(f'Roster claim identity changed: {prefix}')
    expected_requests = ([manifest['conditions'][condition]['smoke']] if phase == 'smoke'
                         else manifest['conditions'][condition]['development'])
    expected_count = len(expected_requests)
    events = rows(ROOT / journal_binding['path'])
    if ([event.get('event') for event in events] !=
            ['phase_started', *['request_started', 'request_completed'] * expected_count, 'phase_completed'] or
            any(events[0].get(k) != v or events[-1].get(k) != v for k, v in identity.items()) or
            events[0].get('runtime') != roster.RUNTIME or
            events[-1].get('request_count') != expected_count or
            events[-1].get('record_count') != sum(len(x['record_ids']) for x in expected_requests)):
        raise ValueError(f'Roster journal is not a sealed phase: {prefix}')
    attempts = rows(ROOT / attempt_binding['path'])
    records = rows(ROOT / record_binding['path'])
    if len(attempts) != expected_count or len(records) != sum(len(x['record_ids']) for x in expected_requests):
        raise ValueError(f'Roster evidence count changed: {prefix}')
    source_digest = hashlib.sha256(json.dumps(manifest['source_bindings'], sort_keys=True).encode()).hexdigest()
    record_offset = 0
    for index, (attempt, planned) in enumerate(zip(attempts, expected_requests)):
        started, finished = events[1 + index * 2:3 + index * 2]
        expected = {**identity, 'batch_index': planned['batch_index']}
        if any(attempt.get(k) != v or started.get(k) != v or finished.get(k) != v for k, v in expected.items()):
            raise ValueError(f'Roster attempt/journal identity changed: {prefix}')
        if (attempt.get('configuration_id') != config or attempt.get('manifest_sha256') != manifest['_sha256'] or
                attempt.get('request') != planned['request'] or attempt.get('request_sha256') != planned['request_sha256'] or
                attempt.get('schema_sha256') != planned['schema_sha256'] or
                attempt.get('historical_attempt_file_sha256') != planned['historical_attempt_file_sha256'] or
                attempt.get('source_bindings') != manifest['source_bindings'] or
                attempt.get('source_bindings_sha256') != source_digest or
                planned['source_bindings_sha256'] != source_digest or
                attempt.get('record_order') != planned['record_ids'] or
                attempt.get('batch_size') != len(planned['record_ids']) or
                attempt.get('configured_batch_size') != manifest['batch_size'] or
                attempt.get('controller_timeout_seconds') != manifest['timeout_seconds'] or
                attempt.get('requested_model') != manifest['model'] or attempt.get('effort') != manifest['effort'] or
                attempt.get('cli_version') != roster.RUNTIME or attempt.get('auth_mode') != 'ChatGPT' or
                attempt.get('reference_labels_read') is not False or attempt.get('status') != 'ok' or
                started.get('manifest_sha256') != manifest['_sha256'] or
                started.get('request_sha256') != planned['request_sha256'] or finished.get('status') != 'ok'):
            raise ValueError(f'Roster request controls or binding changed: {prefix}')
        members = [{'id': rid} for rid in planned['record_ids']]
        try:
            parsed = batch_runner.parse_batch(attempt['raw_response'], members)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'Roster raw response is invalid: {prefix}') from exc
        if parsed != attempt.get('batch_predictions'):
            raise ValueError(f'Roster raw response differs from predictions: {prefix}')
        for position, rid in enumerate(planned['record_ids']):
            record = records[record_offset + position]
            if (any(record.get(k) != v for k, v in identity.items()) or
                    record.get('id') != rid or record.get('batch_index') != planned['batch_index'] or
                    record.get('batch_position') != position or record.get('status') != 'ok' or
                    record.get('prediction') != parsed[rid] or
                    record.get('request_sha256') != planned['request_sha256'] or
                    record.get('source_attempt_sha256') != planned['historical_attempt_file_sha256'] or
                    record.get('requested_model') != manifest['model'] or
                    record.get('reasoning_effort') != manifest['effort'] or
                    record.get('cli_version') != roster.RUNTIME):
                raise ValueError(f'Roster record differs from raw attempt: {prefix}')
        record_offset += len(planned['record_ids'])
    admissions = list((ROOT / folder).glob(f'{phase}.admission-*.json'))
    if len(admissions) != 1:
        raise ValueError(f'Expected one public roster admission: {prefix}')
    admission_path = admissions[0].relative_to(ROOT)
    admission_binding = binding(admission_path)
    admission = json.loads(admissions[0].read_text())
    review_hash = admissions[0].stem.removeprefix(f'{phase}.admission-')
    expected_admission = {'schema': 'codex-repeat-roster-admission-v1',
                          'status': 'admitted_before_dispatch', 'dispatch_status': 'not_asserted',
                          'configuration_id': config, **identity, 'model': manifest['model'],
                          'effort': manifest['effort'], 'runtime': roster.RUNTIME,
                          'manifest_sha256': manifest['_sha256'],
                          'controller_sha256': PINNED_ROSTER_CONTROLLER,
                          'private_review_sha256': review_hash}
    if phase == 'development':
        expected_admission['smoke_inspection_sha256'] = inspection_binding['sha256']
    if len(review_hash) != 64 or any(c not in '0123456789abcdef' for c in review_hash) or admission != expected_admission:
        raise ValueError(f'Public roster admission identity changed: {prefix}')
    return {'claim': claim_binding, 'journal': journal_binding, 'attempts': attempt_binding,
            'records': record_binding, 'admission': admission_binding}


def build_roster_series(config, display_name):
    report = build_series(config, display_name)
    controller_binding = binding(Path('scripts/codex_repeat_roster.py'), PINNED_ROSTER_CONTROLLER)
    report['sourceBindings'].append(controller_binding)
    for repeat in ('repeat2', 'repeat3'):
        manifest_path = REPEAT_ROOT / config / repeat / 'manifest.json'
        manifest = json.loads((ROOT / manifest_path).read_text())
        if manifest != roster.plan_data(config, repeat):
            raise ValueError(f'Roster manifest differs from audited plan: {manifest_path}')
        manifest['_sha256'] = PINNED_SHA[str(manifest_path)]
        for source in manifest['source_bindings']:
            item = binding(Path(source['path']), source['sha256'])
            if item not in report['sourceBindings']:
                report['sourceBindings'].append(item)
        for condition in report['passes'][repeat]:
            smoke = validate_roster_phase(config, repeat, condition, 'smoke', manifest)
            inspection_path = REPEAT_ROOT / config / repeat / condition / 'smoke-inspection.json'
            inspection_binding = binding(inspection_path)
            inspection = json.loads((ROOT / inspection_path).read_text())
            if (inspection.get('schema') != 'codex-repeat-smoke-inspection-v1' or
                    inspection.get('repeat') != repeat or inspection.get('condition') != condition or
                    inspection.get('inspection') != 'accepted_unchanged' or
                    inspection.get('record_ids') != manifest['conditions'][condition]['smoke']['record_ids'] or
                    any(inspection.get(f'{key}_sha256') != smoke[key]['sha256'] for key in ('attempts', 'records', 'journal'))):
                raise ValueError(f'Roster smoke inspection differs from saved evidence: {inspection_path}')
            development = validate_roster_phase(config, repeat, condition, 'development', manifest, inspection_binding)
            entry = report['passes'][repeat][condition]
            if any(entry['evidence'][key] != development[key] for key in ('claim', 'journal', 'attempts', 'records')):
                raise ValueError(f'Roster report evidence changed: {repeat} {condition}')
            entry['evidence'].update({'smoke': smoke, 'smokeInspection': inspection_binding,
                                      'admission': development['admission']})
            report['sourceBindings'].extend([*smoke.values(), inspection_binding, development['admission']])
    return report


PINNED_ROSTER_CONTROLLER = '5a83711e5b87f3535c581ed69f247632834d50bc309825933bb51ac71e0527de'


def build():
    reports = ([build_series(config, display) for config, display in SERIES] +
               [build_roster_series(config, display) for config, display in ROSTER_SERIES])
    # Keep the original Luna view at the top level for saved clients. All comparisons
    # in `series` have separate 60-record denominators and their own source bindings.
    for report in reports:
        insights = []
        for condition in CONDITIONS:
            summary = report['threePassSummary'][condition]['allFour']
            changes = report['changesAcrossThreePasses'].get(condition)
            if summary['range'] is not None and changes is not None:
                lo, hi = summary['range']
                insights.append(f"{condition} matched all four references on {lo} to {hi} of 60 comments per pass; {len(changes['fourFieldVector'])} comments changed at least one decision across the three passes.")
        for condition in ('P1', 'P2'):
            deltas = [x['allFour'] for x in report['withinPassPromptDeltas'] if x['to'] == condition]
            if len(deltas) == 3:
                direction = 'changed direction across passes' if min(deltas) < 0 < max(deltas) else 'did not improve agreement in every pass' if min(deltas) <= 0 else 'improved agreement in all three observed passes'
                insights.append(f"{condition} versus P0 {direction}: changes were {', '.join(f'{x:+d}' for x in deltas)} matches out of 60. Three passes do not establish a reliable future effect.")
        report['interpretation'] = insights
    return {**reports[0], 'series': reports, 'availableConfigurations': [r['configuration'] for r in reports]}


def markdown_series(report):
    lines = [f"## {report['displayName']}", '', f"Completed conditions: {report['completedConditions']}/9. Reference: provisional v0.2 labels on the same 60 synthetic development records.", '',
             '| Pass | Condition | Valid | All four | Sentiment | Follow-up | Serious concern | Testimonial | Request seconds | Input tokens | Output tokens |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for pass_name in PASSES:
        for condition in CONDITIONS:
            entry = report['passes'][pass_name].get(condition)
            if entry is None:
                lines.append(f'| {pass_name} | {condition} | missing | missing | missing | missing | missing | missing | missing | missing | missing |')
                continue
            s=entry['score']; u=entry['usage']; f=s['fields']; t=u['tokens']
            lines.append(f"| {pass_name} | {condition} | {s['valid']}/60 | {s['allFour']}/60 | {f['sentiment']}/60 | {f['follow_up_needed']}/60 | {f['serious_concern_reported']}/60 | {f['testimonial_potential']}/60 | {u['requestSecondsTotal']:.1f} | {t['input_tokens']} | {t['output_tokens']} |")
    lines.extend(['', 'Prompt changes within each completed pass (P1/P2 minus P0, points out of 60):', ''])
    for d in report['withinPassPromptDeltas']:
        lines.append(f"- {d['pass']} {d['to']}: all four {d['allFour']:+d}; " + ', '.join(f'{f} {d["fields"][f]:+d}' for f in FIELDS) + '.')
    lines.extend(['', 'Three-pass scores (mean and range appear when all three passes are complete):', ''])
    for condition in CONDITIONS:
        summary = report['threePassSummary'][condition]
        for name, stats in [('all four', summary['allFour']), *((f, summary['fields'][f]) for f in FIELDS)]:
            values = ', '.join(str(x) for x in stats['values'])
            mean = f"{stats['mean']:.2f}" if stats['mean'] is not None else 'pending'
            spread = f"{stats['range'][0]} to {stats['range'][1]}" if stats['range'] is not None else 'pending'
            lines.append(f'- {condition} {name}: {values} of 60; mean {mean}; range {spread}.')
    lines.extend(['', 'Paired P1/P2 minus P0 all-four spread:', ''])
    for target, item in report['pairedDeltaSpread'].items():
        values = ', '.join(f'{x:+d}' for x in item['allFourValues'])
        spread = f"{item['allFourRange'][0]:+d} to {item['allFourRange'][1]:+d}" if item['allFourRange'] else 'pending'
        lines.append(f"- {target}: {values}; three-pair range {spread}.")
    lines.extend(['', 'Reference class counts (60 records):', ''])
    for field, counts in report['referenceClassCounts'].items():
        lines.append(f"- {field}: " + ', '.join(f'{label} {count}' for label, count in counts.items()))
    lines.extend(['', 'Completed pass comparisons, changed labels among records valid in both passes:', '',
                  '| Condition | Passes | Comparable | Four-field vector | Sentiment | Follow-up | Serious concern | Testimonial |',
                  '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |'])
    for row in report['pairwiseFlips']:
        cell = lambda key: f"{row[key]['changed']}/{row['denominator']}"
        lines.append(f"| {row['condition']} | {row['from']} to {row['to']} | {row['denominator']}/60 | {cell('fourFieldVector')} | {cell('sentiment')} | {cell('follow_up_needed')} | {cell('serious_concern_reported')} | {cell('testimonial_potential')} |")
    lines.extend(['', 'The JSON gives excluded IDs and changed record IDs for each comparison, plus changes across all three passes.', '', 'Actual per-request subscription cost is unknown. Request durations are six batch durations per completed condition, not 60 independent latencies.', '', 'The accepted Codex CLI patch amendment does not establish runtime equivalence. Hidden serving revision and effective seed are unavailable. The reference labels are provisional, and these 60 repeated records are not 180 independent cases.', '', 'Source paths and SHA-256 hashes for the labels, historical manifest, completed records, attempts, journals and completion claims are in [repeats.json](../public-site/repeats.json).'])
    return '\n'.join(lines) + '\n'


def markdown(report):
    intro = '# Prompt repeat findings\n\nEach configuration is a separate series on the same 60 development records. Scores and pass counts are reported within each configuration.\n\n'
    return (intro + '\n'.join(markdown_series(series) + ('\nObserved patterns:\n\n' + '\n\n'.join(series['interpretation']) if series['interpretation'] else '') for series in report['series'])).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check outputs without writing')
    args = parser.parse_args()
    report = build()
    outputs = {ROOT / 'public-site/repeats.json': json.dumps(report, indent=2, ensure_ascii=False) + '\n', ROOT / 'docs/REPEAT_FINDINGS.md': markdown(report)}
    for path, value in outputs.items():
        if args.check:
            if not path.exists() or path.read_text() != value: raise ValueError(f'Stale report: {path}')
        else:
            path.write_text(value)
    print('; '.join(f"{r['configuration']}: {r['completedConditions']}/9 complete" for r in report['series']))


if __name__ == '__main__': main()
