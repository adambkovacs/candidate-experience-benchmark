#!/usr/bin/env python3
"""Read sealed Codex fresh matched-three evidence and score it offline."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import codex_batch_benchmark as batch
import codex_benchmark as single
import prompt_admission
from development_benchmark import KEYS, valid, read_rows, digest

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1')
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
CONTROLLER_SHA = '2ee59eb5920dc609532838dfafa9e6a0749aa70e90bf6639c5a13a8bfe36d401'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
ORDERS = {'fresh1': ['P0', 'P1', 'P2'], 'fresh2': ['P1', 'P2', 'P0'], 'fresh3': ['P2', 'P0', 'P1']}
SPECS = {
    'codex-gpt-5.6-luna-xhigh': ('gpt-5.6-luna', 'xhigh', ('fa912545f7397df84ffe112a45875c867dfc5951c6da369912057ee57eae6ea6', 'a7cb978de381f184624f33cfbc44036b917ceb722a2a5ea45c09b360d32e93a9', 'e9c7ef5f3e4a0616248d71598eceb0270254e3bbf0218c5ab53d785d577f426f')),
    'codex-gpt-6-astra-medium': ('gpt-6-astra', 'medium', ('e2d19a88dce2db53541ebf7ad3f2fded01895c4fa651172d1278a3890fbdae27', '5e2cb5e5c892598a708d040c790eaa8b0ba39c744b4a51a291d273a75aa63982', 'c8bd9e37cbcb29cd36e8f1c5c128871b1570ea3d5764ad5d0cb6eeb6e08cef75')),
    'codex-gpt-5.6-terra-low': ('gpt-5.6-terra', 'low', ('7e0276a458f49c2c2720309379892e632f10d81db3ada312f8c6a458637ce165', '5ee49cdbc59dc8c55cb846ab664edece1bbbb38dd06ec247482efa66b37d97c0', '44a6c9f287349887fd11a3affde939c7e414083a67f479787248e13a41797ee7')),
    'codex-gpt-5.6-terra-medium': ('gpt-5.6-terra', 'medium', ('c938be80ccc7778a5d0427bc07e9d1ce23564b510b4a84f5b99f69e55d2b9ae5', 'c5398571f44dccd192331c24b311aba5abe1be3b17a02c4fc6cacbf319d97f46', 'ed93a596a758a2b54bc7f96c1bd74257afb8e9ed04ebf498bc69fedfb833d8e2')),
    'codex-gpt-6-sol-low-batch10': ('gpt-6-sol', 'low', ('9299eecedd351a38bfeae9cc2865162ca0f3ffc72d3921c27b746d4c7e2411a4', '7771e5e8a98c0822374c757180ac48f3f6e645cc4bf0b0d44981f7d9888140ca', '172f764d87ff48c1f85741a8857f2550052e81297e104bb12f2c9b3253311bbd')),
    'codex-gpt-6-luna-low-batch10': ('gpt-6-luna', 'low', ('2dbdce41e708ed36660c1256147b0e98b942ef385b70f225ffcf6ac5753d6ce8', '07e537a54488df44ec265c5b15db35674d4d43ee044edc6f04b7ecf7cd4a9f60', '5dbe98ea1bb2c5dd0f8b8ed1188cc010d5524c9413395d11ffff15a66e2f6705')),
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def target(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    result.relative_to(root)
    return result


def bind(root, relative, bindings, expected=None):
    actual = sha(target(root, relative))
    if expected is not None and actual != expected:
        raise ValueError(f'Source hash changed: {relative}')
    entry = {'path': str(relative), 'sha256': actual}
    if entry not in bindings:
        bindings.append(entry)
    return entry


def jsonl(root, relative):
    data = target(root, relative).read_bytes()
    if not data.endswith(b'\n') or any(not item.strip() for item in data.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {relative}')
    return [json.loads(item) for item in data.splitlines()]


def context(root, configs):
    bindings = []
    bind(root, LABELS, bindings, LABELS_SHA)
    bind(root, 'scripts/codex_fresh_roster.py', bindings, CONTROLLER_SHA)
    bind(root, 'scripts/codex_batch_benchmark.py', bindings)
    bind(root, 'scripts/codex_benchmark.py', bindings)
    bind(root, 'scripts/build_codex_fresh_repeat_findings.py', bindings)
    rows = jsonl(root, LABELS)
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if ([r.get('id') for r in rows] != ids or
            any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels')) for r in rows)):
        raise ValueError('Provisional reference v0.2 differs')
    labels = {r['id']: r['proposed_labels'] for r in rows}
    manifests = {}
    input_rows = read_rows(target(root, 'data/pilot/inputs.jsonl'))
    if [r.get('id') for r in input_rows] != ids or any(set(r) != {'id', 'feedback'} for r in input_rows):
        raise ValueError('Input-only membership changed')
    policy = target(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    for config in configs:
        if config not in SPECS:
            raise ValueError('Unreviewed fresh configuration')
        model, effort, hashes = SPECS[config]
        manifests[config] = {}
        for fresh, expected_hash in zip(PASSES, hashes):
            rel = BASE / (config + '-fresh-matched3') / fresh / 'manifest.json'
            bind(root, rel, bindings, expected_hash)
            plan = json.loads(target(root, rel).read_text())
            if (plan.get('schema') != 'codex-fresh-matched3-v1' or plan.get('configuration_id') != config or
                    plan.get('series_id') != config + '-fresh-matched3' or plan.get('pass') != fresh or
                    plan.get('condition_order') != ORDERS[fresh] or plan.get('model') != model or
                    plan.get('effort') != effort or plan.get('cli_path') != '/opt/homebrew/bin/codex' or
                    plan.get('cli_version') != 'codex-cli 0.156.1' or plan.get('batch_size') != 10 or
                    plan.get('timeout_seconds') != 600.0 or plan.get('reference_labels_read') is not False or
                    plan.get('historical_first_pass_used') is not False or set(plan.get('conditions', {})) != set(CONDITIONS)):
                raise ValueError(f'Frozen fresh plan controls differ: {config} {fresh}')
            for source in plan['source_bindings']:
                bind(root, source['path'], bindings, source['sha256'])
            source_digest = digest(json.dumps(plan['source_bindings'], sort_keys=True))
            for condition in CONDITIONS:
                variant = None if condition == 'P0' else condition
                parent = None if condition == 'P0' else config
                entries = [plan['conditions'][condition]['smoke'], *plan['conditions'][condition]['development']]
                if len(entries) != 7:
                    raise ValueError('Fresh plan batch count differs')
                for index, item in enumerate(entries):
                    members = input_rows[:3] if index == 0 else input_rows[(index - 1) * 10:index * 10]
                    expected = {'prompt': batch.batch_prompt(policy, members, variant, parent),
                                'output_schema': batch.batch_schema(members)}
                    if (item.get('request') != expected or item.get('record_ids') != [r['id'] for r in members] or
                            item.get('source_bindings_sha256') != source_digest or
                            item.get('request_sha256') != digest(expected['prompt']) or
                            item.get('schema_sha256') != digest(json.dumps(expected['output_schema'], sort_keys=True)) or
                            item.get('pass') != fresh or item.get('condition') != condition or
                            item.get('phase') != ('smoke' if index == 0 else 'development') or
                            item.get('batch_index') != (0 if index == 0 else index)):
                        raise ValueError('Frozen fresh prompt, schema or membership changed')
            manifests[config][fresh] = (plan, expected_hash)
    return labels, ids, manifests, bindings


def terminal_state(root, folder, phase):
    journal = target(root, folder / (phase + '.journal.jsonl'))
    # A public report must not change merely because an unclosed phase acquires
    # a claim or receives partial bytes. Read only enough to find a sealed end.
    if not journal.exists():
        return 'not_completed'
    try:
        events = jsonl(root, folder / (phase + '.journal.jsonl'))
    except (OSError, ValueError, json.JSONDecodeError):
        return 'not_completed'
    if events and events[-1].get('event') == 'phase_completed':
        return 'closed'
    return 'not_completed'


def sealed_phase(root, config, fresh, condition, phase, plan, manifest_sha, bindings):
    folder = BASE / (config + '-fresh-matched3') / fresh / condition
    expected = [plan['conditions'][condition]['smoke']] if phase == 'smoke' else plan['conditions'][condition]['development']
    claim_path = folder / (phase + '.claim.json')
    journal_path = folder / (phase + '.journal.jsonl')
    attempts_path = folder / (phase + '.attempts.jsonl')
    records_path = folder / (phase + '.records.jsonl')
    admission_path = folder / (phase + '.admission.json')
    for relative in (claim_path, journal_path, attempts_path, records_path, admission_path):
        bind(root, relative, bindings)
    claim = json.loads(target(root, claim_path).read_text())
    admission = json.loads(target(root, admission_path).read_text())
    identity = {'configuration_id': config, 'pass': fresh, 'condition': condition, 'phase': phase}
    if (claim.get('schema') != 'codex-fresh-phase-claim-v1' or
            any(claim.get(k) != v for k, v in identity.items()) or
            claim.get('manifest_sha256') != manifest_sha or
            claim.get('admission_sha256') != sha(target(root, admission_path))):
        raise ValueError('Fresh phase claim differs')
    admission_expected = {'schema': 'codex-fresh-admission-v1', 'status': 'admitted_before_dispatch',
                          'dispatch_status': 'not_asserted', **identity, 'manifest_sha256': manifest_sha,
                          'controller_sha256': CONTROLLER_SHA, 'model': plan['model'],
                          'effort': plan['effort'], 'runtime': plan['cli_version']}
    if phase == 'development':
        admission_expected['smoke_inspection_sha256'] = sha(target(root, folder / 'smoke-inspection.json'))
    if (any(admission.get(k) != v for k, v in admission_expected.items()) or
            set(admission) != set(admission_expected) | {'private_review_sha256'} or
            not isinstance(admission.get('private_review_sha256'), str) or len(admission['private_review_sha256']) != 64):
        raise ValueError('Public admission differs from frozen phase')
    events = jsonl(root, journal_path)
    names = ['phase_started'] + [name for _ in expected for name in
                                 ('request_started', 'raw_saved', 'request_completed')] + ['phase_completed']
    if ([e.get('event') for e in events] != names or
            any(events[0].get(k) != v for k, v in {'pass': fresh, 'condition': condition, 'phase': phase}.items()) or
            events[-1].get('request_count') != len(expected) or
            events[-1].get('record_count') != sum(len(r['record_ids']) for r in expected)):
        raise ValueError('Closed phase journal differs')
    attempts = jsonl(root, attempts_path)
    records = jsonl(root, records_path)
    if len(attempts) != len(expected) or len(records) != sum(len(r['record_ids']) for r in expected):
        raise ValueError('Closed phase attempt/record count differs')
    offset = 0
    for index, (planned, attempt) in enumerate(zip(expected, attempts)):
        started, raw_event, finished = events[1 + index * 3:4 + index * 3]
        batch_index = planned['batch_index']
        ids = planned['record_ids']
        if (started.get('batch_index') != batch_index or started.get('record_ids') != ids or
                raw_event.get('batch_index') != batch_index or finished.get('batch_index') != batch_index or
                finished.get('status') != 'ok'):
            raise ValueError('Journal request identity differs')
        raw_path = folder / (phase + f'.raw-{batch_index}.json')
        raw_binding = bind(root, raw_path, bindings)
        raw = json.loads(target(root, raw_path).read_text())
        if (raw_event.get('raw_sha256') != raw_binding['sha256'] or
                finished.get('raw_sha256') != raw_binding['sha256'] or
                attempt.get('raw_sidecar_sha256') != raw_binding['sha256'] or
                raw.get('transport_error') is not None or raw.get('returncode') != 0):
            raise ValueError('Raw response sidecar differs or lacks completed transport')
        parsed = single.parse_result(raw['returncode'], raw['stdout'], raw['response'])
        predictions = batch.parse_batch(raw['response'], [{'id': rid} for rid in ids])
        usage = parsed['usage']
        diagnostic = prompt_admission.audit_response({**attempt, **parsed, 'status': 'ok'},
                                                     'codex_batch_v1', 258400)
        if (parsed['status'] in ('service_error', 'isolation_violation') or
                not diagnostic['passed'] or attempt.get('response_diagnostic') != diagnostic or
                attempt.get('schema') != 'codex-fresh-attempt-v1' or
                any(attempt.get(k) != v for k, v in identity.items()) or
                attempt.get('status') != 'ok' or attempt.get('batch_index') != batch_index or
                attempt.get('record_order') != ids or attempt.get('request') != planned['request'] or
                attempt.get('request_sha256') != planned['request_sha256'] or
                attempt.get('schema_sha256') != planned['schema_sha256'] or
                attempt.get('source_bindings_sha256') != planned['source_bindings_sha256'] or
                attempt.get('manifest_sha256') != manifest_sha or
                attempt.get('requested_model') != plan['model'] or attempt.get('effort') != plan['effort'] or
                attempt.get('cli_path') != plan['cli_path'] or attempt.get('cli_version') != plan['cli_version'] or
                attempt.get('controller_timeout_seconds') != plan['timeout_seconds'] or
                attempt.get('auth_mode') != 'ChatGPT' or attempt.get('reference_labels_read') is not False or
                attempt.get('batch_predictions') != predictions or attempt.get('raw_events') != parsed['raw_events'] or
                attempt.get('usage') != usage or
                attempt.get('input_tokens') != (usage.get('input_tokens') if isinstance(usage, dict) else None) or
                attempt.get('output_tokens') != (usage.get('output_tokens') if isinstance(usage, dict) else None) or
                attempt.get('returned_model') is not None or attempt.get('cost_usd') is not None or
                attempt.get('requested_seed') is not None or attempt.get('effective_seed') is not None or
                attempt.get('model_revision') is not None or attempt.get('hardware') is not None or
                attempt.get('elapsed_seconds') != raw.get('elapsed_seconds') or
                attempt.get('started_utc') != raw.get('started_utc') or
                attempt.get('finished_utc') != raw.get('finished_utc')):
            raise ValueError('Raw response, usage or attempt projection differs')
        command = attempt.get('command')
        if not isinstance(command, list) or '--cd' not in command or '--output-schema' not in command:
            raise ValueError('Saved command missing')
        cwd = Path(command[command.index('--cd') + 1])
        schema_path = Path(command[command.index('--output-schema') + 1])
        if (not cwd.is_absolute() or schema_path != cwd / 'schema.json' or
                command != single.command(plan['cli_path'], plan['model'], plan['effort'], cwd, schema_path)):
            raise ValueError('Codex command controls differ')
        subset = records[offset:offset + len(ids)]
        for position, (rid, record) in enumerate(zip(ids, subset)):
            if (record.get('id') != rid or record.get('pass') != fresh or
                    record.get('condition') != condition or record.get('phase') != phase or
                    record.get('batch_index') != batch_index or record.get('batch_position') != position or
                    record.get('status') != 'ok' or record.get('prediction') != predictions[rid] or
                    record.get('request_sha256') != planned['request_sha256'] or
                    record.get('requested_model') != plan['model'] or record.get('effort') != plan['effort'] or
                    record.get('elapsed_seconds') != raw['elapsed_seconds'] / len(ids) or
                    record.get('timing_kind') != 'amortized_batch_share_not_individual_latency' or
                    record.get('input_sha256') != digest(next(x['feedback'] for x in read_rows(target(root, 'data/pilot/inputs.jsonl')) if x['id'] == rid))):
                raise ValueError('Record differs from raw request and prediction')
        offset += len(ids)
    return {'records': {row['id']: row for row in records}, 'attempts': attempts,
            'evidence': {'claim': {'path': str(claim_path), 'sha256': sha(target(root, claim_path))},
                         'journal': {'path': str(journal_path), 'sha256': sha(target(root, journal_path))},
                         'attempts': {'path': str(attempts_path), 'sha256': sha(target(root, attempts_path))},
                         'records': {'path': str(records_path), 'sha256': sha(target(root, records_path))},
                         'admission': {'path': str(admission_path), 'sha256': sha(target(root, admission_path))}}}


def smoke_inspection(root, config, fresh, condition, smoke, bindings):
    folder = BASE / (config + '-fresh-matched3') / fresh / condition
    path = folder / 'smoke-inspection.json'
    binding = bind(root, path, bindings)
    value = json.loads(target(root, path).read_text())
    if (value.get('schema') != 'codex-fresh-smoke-inspection-v1' or
            value.get('inspection') != 'accepted_unchanged' or not value.get('note') or
            value.get('configuration_id') != config or value.get('pass') != fresh or
            value.get('condition') != condition or
            value.get('record_ids') != ['DEV-001', 'DEV-002', 'DEV-003']):
        raise ValueError('Smoke inspection identity differs')
    for field in ('claim', 'journal', 'attempts', 'records'):
        if value.get(field + '_sha256') != smoke['evidence'][field]['sha256']:
            raise ValueError('Smoke inspection evidence hash differs')
    if value.get('raw_sha256') != sha(target(root, folder / 'smoke.raw-0.json')):
        raise ValueError('Smoke inspection raw hash differs')
    return binding


def score(records, labels, ids):
    outcome = Counter('valid' if records[rid]['status'] == 'ok' and valid(records[rid]['prediction']) else records[rid]['status'] for rid in ids)
    fields = {field: sum(records[rid]['status'] == 'ok' and records[rid]['prediction'][field] == labels[rid][field] for rid in ids) for field in KEYS}
    all_four = sum(records[rid]['status'] == 'ok' and all(records[rid]['prediction'][f] == labels[rid][f] for f in KEYS) for rid in ids)
    confusions = {field: {} for field in KEYS}
    classes = {field: Counter() for field in KEYS}
    for rid in ids:
        prediction = records[rid]['prediction'] if records[rid]['status'] == 'ok' and valid(records[rid]['prediction']) else None
        for field in KEYS:
            truth = labels[rid][field]
            label = prediction[field] if prediction else '__invalid_or_missing__'
            confusions[field].setdefault(truth, Counter())[label] += 1
            classes[field][label] += 1
    return {'denominator': 60, 'valid': outcome['valid'], 'allFour': all_four,
            'fields': fields, 'outcomes': dict(outcome),
            'invalidIds': [rid for rid in ids if records[rid]['status'] != 'ok'],
            'confusionCounts': {f: {k: dict(v) for k, v in confusions[f].items()} for f in KEYS},
            'predictedClassCounts': {f: dict(classes[f]) for f in KEYS}}


def usage(attempts):
    keys = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')
    tokens = {key: sum(a['usage'][key] for a in attempts)
              if all(isinstance(a.get('usage'), dict) and type(a['usage'].get(key)) is int for a in attempts)
              else None for key in keys}
    elapsed = [a.get('elapsed_seconds') for a in attempts]
    return {'requestCount': len(attempts), 'requestSeconds': elapsed,
            'requestSecondsTotal': sum(elapsed) if all(type(x) in (int, float) for x in elapsed) else None,
            'timingKind': 'client_batch_duration_not_pure_inference', 'tokens': tokens,
            'actualCostUsd': None, 'costNote': 'ChatGPT subscription; attributable monetary cost unavailable.'}


def flip(a, b, ids):
    eligible = [rid for rid in ids if a[rid]['status'] == b[rid]['status'] == 'ok']
    out = {'denominator': len(eligible), 'excludedIds': [rid for rid in ids if rid not in eligible]}
    for field in (*KEYS, 'fourFieldVector'):
        changed = [rid for rid in eligible if (a[rid]['prediction'] if field == 'fourFieldVector' else a[rid]['prediction'][field]) != (b[rid]['prediction'] if field == 'fourFieldVector' else b[rid]['prediction'][field])]
        out[field] = {'changed': len(changed), 'caseIds': changed, 'rate': len(changed) / len(eligible) if eligible else None}
    return out


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / 3 if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build_series(root, config, labels, ids, manifests, bindings):
    data, missing, record_maps = {}, [], {}
    for fresh in PASSES:
        data[fresh] = {}
        plan, manifest_sha = manifests[config][fresh]
        for condition in CONDITIONS:
            folder = BASE / (config + '-fresh-matched3') / fresh / condition
            state = terminal_state(root, folder, 'development')
            if state != 'closed':
                missing.append({'pass': fresh, 'condition': condition, 'status': state})
                continue
            if terminal_state(root, folder, 'smoke') != 'closed':
                raise ValueError('Development closed without sealed smoke')
            smoke = sealed_phase(root, config, fresh, condition, 'smoke', plan, manifest_sha, bindings)
            inspection = smoke_inspection(root, config, fresh, condition, smoke, bindings)
            development = sealed_phase(root, config, fresh, condition, 'development', plan, manifest_sha, bindings)
            values = development['records']
            record_maps[(fresh, condition)] = values
            data[fresh][condition] = {'status': 'completed', 'score': score(values, labels, ids),
                                      'usage': usage(development['attempts']),
                                      'evidence': {**development['evidence'], 'smoke': smoke['evidence'],
                                                   'smokeInspection': inspection}}
    prompt_deltas, prompt_flips = [], []
    for fresh in PASSES:
        if 'P0' not in data[fresh]:
            continue
        for condition in ('P1', 'P2'):
            if condition not in data[fresh]:
                continue
            a, b = data[fresh]['P0']['score'], data[fresh][condition]['score']
            prompt_deltas.append({'pass': fresh, 'from': 'P0', 'to': condition, 'denominator': 60,
                                  'allFour': b['allFour'] - a['allFour'],
                                  'fields': {f: b['fields'][f] - a['fields'][f] for f in KEYS}})
            prompt_flips.append({'pass': fresh, 'from': 'P0', 'to': condition,
                                 **flip(record_maps[(fresh, 'P0')], record_maps[(fresh, condition)], ids)})
    pairwise = []
    for condition in CONDITIONS:
        for index, left in enumerate(PASSES):
            for right in PASSES[index + 1:]:
                if (left, condition) in record_maps and (right, condition) in record_maps:
                    pairwise.append({'condition': condition, 'from': left, 'to': right,
                                     **flip(record_maps[(left, condition)], record_maps[(right, condition)], ids)})
    across = {}
    for condition in CONDITIONS:
        if not all((fresh, condition) in record_maps for fresh in PASSES):
            continue
        three = [record_maps[(fresh, condition)] for fresh in PASSES]
        eligible = [rid for rid in ids if all(v[rid]['status'] == 'ok' for v in three)]
        across[condition] = {'denominator': len(eligible), 'excludedIds': [rid for rid in ids if rid not in eligible],
                             'fields': {f: [rid for rid in eligible if len({v[rid]['prediction'][f] for v in three}) > 1] for f in KEYS},
                             'fourFieldVector': [rid for rid in eligible if len({tuple(v[rid]['prediction'][f] for f in KEYS) for v in three}) > 1]}
    ranges = {}
    for condition in CONDITIONS:
        scores = [data[fresh][condition]['score'] for fresh in PASSES if condition in data[fresh]]
        ranges[condition] = {'allFour': stats([s['allFour'] for s in scores]),
                             'fields': {f: stats([s['fields'][f] for s in scores]) for f in KEYS}}
    spread = {}
    for condition in ('P1', 'P2'):
        matched = [item for item in prompt_deltas if item['to'] == condition]
        spread[condition] = {'completedPairs': len(matched),
                             'allFourValues': [x['allFour'] for x in matched],
                             'allFourRange': [min(x['allFour'] for x in matched), max(x['allFour'] for x in matched)] if len(matched) == 3 else None,
                             'fieldRanges': {f: [min(x['fields'][f] for x in matched), max(x['fields'][f] for x in matched)] if len(matched) == 3 else None for f in KEYS}}
    model, effort, _ = SPECS[config]
    return {'schema': 'codex-fresh-repeat-findings-v1', 'configuration': config,
            'seriesId': config + '-fresh-matched3', 'displayName': model + ' · ' + effort + ' effort',
            'method': 'fresh-matched-three', 'model': model, 'effort': effort,
            'servedModel': None, 'servedModelNote': 'CLI did not expose verified served identity.',
            'conditionOrder': list(CONDITIONS), 'passOrder': list(PASSES), 'denominator': 60,
            'plannedConditions': 9, 'completedConditions': sum(map(len, data.values())),
            'missingPasses': missing, 'passes': data, 'referenceVersion': '0.2',
            'referenceStatus': 'AI-reviewed provisional; not independent adjudication',
            'referenceClassCounts': {f: dict(Counter(labels[rid][f] for rid in ids)) for f in KEYS},
            'threePassSummary': ranges, 'pairwiseFlips': pairwise,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': prompt_deltas,
            'withinPassPromptFlips': prompt_flips, 'pairedDeltaSpread': spread,
            'historicalPassUsed': False,
            'limitations': ['Historical evidence remains observational and is not fresh1.',
                            'The same 60 synthetic reviews recur in every phase.',
                            'CLI serving revision and effective seed are unavailable.',
                            'Request elapsed time is client timing, not pure inference.',
                            'Attributable subscription cost is unavailable, not zero.']}


def build(root=ROOT, configs=None):
    selected = tuple(SPECS if configs is None else configs)
    labels, ids, manifests, bindings = context(root, selected)
    series = [build_series(root, config, labels, ids, manifests, bindings) for config in selected]
    return {'schema': 'codex-fresh-repeat-findings-v1', 'series': series,
            'availableConfigurations': [row['configuration'] for row in series],
            'sourceBindings': bindings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    raw = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if args.output.read_text() != raw:
            raise ValueError('Saved Codex fresh report differs')
    else:
        args.output.write_text(raw)


if __name__ == '__main__':
    main()
