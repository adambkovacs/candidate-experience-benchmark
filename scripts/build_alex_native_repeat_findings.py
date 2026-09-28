#!/usr/bin/env python3
"""Build offline Alex 0.8B/4B native P0 repeat findings from closed evidence."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import alex_openjev08_repeat_admission as alex08
import alex_openjev4b_repeat_admission as alex4b
import build_repeat_findings as shared
from development_benchmark import KEYS, VALUES, digest, valid

ROOT = Path(__file__).resolve().parents[1]
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONFIGS = {
    'alex-openjev08-native-p0-v1': {'manifest_sha': '6a4821b492030360535a4218302cbd82f4e04d4677eab92afa742d317c6627cf',
        'schema': 'alex-openjev08-native-p0-repeat-admission-v1', 'controller': 'alex_openjev08_repeat_admission.py',
        'kind': 'root-reviewed-alex-openjev08-native-p0-stage-v1', 'display': 'Alex OpenJev 0.8B · native NLI',
        'historical_file': 'development.jsonl', 'module': alex08},
    'alex-openjev4b-native-p0-v1': {'manifest_sha': '2fd72a67d00bddb1ced94c71b7c585ab9481081cc927ed08fa1fe58c83303e1a',
        'schema': 'alex-openjev4b-native-p0-repeat-admission-v1', 'controller': 'alex_openjev4b_repeat_admission.py',
        'kind': 'root-reviewed-alex-openjev4b-native-p0-stage-v1', 'display': 'Alex OpenJev 4B · native NLI',
        'historical_file': 'development-complete.jsonl', 'module': alex4b},
}


def path(root, relative):
    target = (Path(root) / relative).resolve()
    target.relative_to(Path(root).resolve())
    return target


def sha(filename):
    with Path(filename).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(root, relative):
    raw = path(root, relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


def binder(root):
    bindings = []
    def bind(relative, expected=None):
        relative = Path(relative)
        actual = sha(path(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Source hash differs: {relative}')
        item = {'path': str(relative), 'sha256': actual}
        if item not in bindings:
            bindings.append(item)
        return item
    return bind, bindings


def context(root, config_id):
    root = Path(root)
    spec = CONFIGS[config_id]
    bind, bindings = binder(root)
    base = Path('results/repeatability-v1') / config_id
    bind(base / 'manifest.json', spec['manifest_sha'])
    plan = json.loads(path(root, base / 'manifest.json').read_text())
    if (plan.get('schema') != spec['schema'] or plan.get('status') != 'offline_frozen_no_inference'
            or plan.get('disposition') != 'fresh_matched_three_historical_observational'
            or plan.get('reference_labels_used') is not False
            or plan.get('schedule') != [f'{name}/P0' for name in PASSES]
            or plan.get('stage_inputs') != {'smoke': {'limit': 3}, 'development': {'limit': 60}}
            or plan.get('artifact_revision') != spec['module'].REVISION):
        raise ValueError('Frozen Alex manifest scope or schedule differs')
    runtime = plan['runtime']
    if (runtime.get('device') != 'mps:0' or runtime.get('dtype') != 'torch.float32'
            or runtime.get('quantization') != 'none' or runtime.get('batch_size') != 4
            or runtime.get('max_context') != 4096 or runtime.get('calibration') != 'none'
            or runtime.get('truncation') != 'forbidden'
            or runtime.get('nli_class_order') != ['contradiction', 'entailment', 'neutral']
            or not all((runtime.get('hardware') or {}).get(key) for key in
                       ('machine_model', 'chip_type', 'physical_memory', 'number_processors'))):
        raise ValueError('Frozen Alex native controls differ')
    source_paths = {Path(filename) for filename in plan['source_sha256']}
    original_root = next((source.parent.parent for source in source_paths
                          if source.name == spec['controller'] and source.parent.name == 'scripts'), None)
    if original_root is None:
        raise ValueError('Frozen Alex controller root missing')
    local, external = {}, {}
    for absolute, expected in plan['source_sha256'].items():
        source = Path(absolute)
        try: relative = source.relative_to(original_root)
        except ValueError: external[absolute] = expected
        else:
            bind(relative, expected)
            local[str(relative)] = expected
    needed = {'scripts/' + spec['controller'], 'scripts/anyjev_raw_repeat_admission.py',
              'scripts/specialist_benchmark.py', 'scripts/jev_benchmark.py',
              'scripts/development_benchmark.py', 'docs/LABELING_GUIDE.md',
              'data/pilot/inputs.jsonl'}
    if not needed <= set(local):
        raise ValueError('Frozen Alex local source proof incomplete')
    bind(LABELS, LABELS_SHA)
    source = rows(root, 'data/pilot/inputs.jsonl')
    label_rows = rows(root, LABELS)
    if ([r.get('id') for r in source] != IDS or
            any(set(r) != {'id', 'feedback'} or not isinstance(r['feedback'], str) for r in source)
            or [r.get('id') for r in label_rows] != IDS or
            any(r.get('review_version') != '0.2' or not valid(r.get('proposed_labels')) for r in label_rows)):
        raise ValueError('Input or provisional reference membership differs')
    policy = path(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != plan['policy_prefix_sha256']:
        raise ValueError('Frozen Alex policy prefix differs')
    if len(plan['requests']) != 60 or [x.get('id') for x in plan['requests']] != IDS:
        raise ValueError('Frozen Alex request membership differs')
    for row, request in zip(source, plan['requests']):
        if (request.get('input_sha256') != digest(row['feedback'])
                or len(request.get('nli_inputs', [])) != 14
                or any(type(item.get('input_tokens')) is not int or not 0 < item['input_tokens'] <= 4096
                       for item in request['nli_inputs'])):
            raise ValueError('Frozen Alex input or native NLI signature differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    return plan, labels, bind, bindings, external, base


def projected(spec, probabilities):
    return spec['module'].project_probabilities(probabilities)


def historical(root, plan, labels, spec, bind):
    folder = Path(plan['historical']['directory'])
    evidence = {}
    if spec['controller'] == 'alex_openjev08_repeat_admission.py':
        for filename, expected in [('smoke.jsonl', plan['historical']['smoke_sha256']),
                                   ('development.jsonl', plan['historical']['development_sha256'])]:
            evidence[filename] = bind(folder / filename, expected)
    else:
        for filename, expected in plan['historical']['files_sha256'].items():
            evidence[filename] = bind(folder / filename, expected)
        original = path(root, folder / 'development.jsonl').read_bytes()
        resumed = path(root, folder / 'development-resume-2026-09-24.jsonl').read_bytes()
        complete = path(root, folder / 'development-complete.jsonl').read_bytes()
        if original + resumed != complete or len(original.splitlines()) != 45 or len(resumed.splitlines()) != 15:
            raise ValueError('Historical Alex 4B resumed composite differs')
        if plan['historical'].get('unknown_attempt') != {'id': 'DEV-046', 'status': 'possibly_started_outcome_unknown'}:
            raise ValueError('Historical Alex 4B DEV-046 uncertainty missing')
    records = rows(root, folder / spec['historical_file'])
    if len(records) != 60 or [x.get('id') for x in records] != IDS:
        raise ValueError('Historical Alex development membership differs')
    for record, request in zip(records, plan['requests']):
        raw = record.get('raw_response') or {}
        try: prediction = projected(spec, raw.get('nli_probabilities'))
        except ValueError: prediction = None
        if (record.get('request_sha256') != request['request_sha256']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('policy_sha256') != plan['policy_prefix_sha256']
                or record.get('artifact_revision') != plan['artifact_revision']
                or record.get('requested_model') != plan['model_path']
                or record.get('status') != ('ok' if prediction is not None else 'invalid_output')
                or record.get('prediction') != prediction
                or raw.get('hypothesis_order') != [[key, label] for key in KEYS for label in VALUES[key]]
                or (record.get('metadata') or {}).get('input_tokens') !=
                   [x['input_tokens'] for x in request['nli_inputs']]):
            raise ValueError('Historical Alex raw projection or request differs')
    indexed = {x['id']: x for x in records}
    return {'status': 'observational_only', 'freshPassEligible': False,
            'score': shared.score(indexed, labels, IDS),
            'confusionCounts': confusion(indexed, labels),
            'savedPositions': 60,
            'unknownPriorAttempt': plan['historical'].get('unknown_attempt'),
            'reason': plan['historical']['reason'], 'evidence': evidence}


def stage(root, plan, spec, base, phase, stage_name, bind):
    folder = base / phase
    names = {'receipt': f'{stage_name}.root-review.json', 'claim': f'{stage_name}.claim.json',
             'journal': f'{stage_name}.journal.jsonl', 'raw': f'{stage_name}.raw.jsonl',
             'records': f'{stage_name}.records.jsonl', 'completion': f'{stage_name}.completion.json'}
    evidence = {key: bind(folder / name) for key, name in names.items()}
    receipt = json.loads(path(root, folder / names['receipt']).read_text())
    claim = json.loads(path(root, folder / names['claim']).read_text())
    completion = json.loads(path(root, folder / names['completion']).read_text())
    controller_sha = plan['source_sha256'][next(filename for filename in plan['source_sha256']
                      if Path(filename).name == spec['controller'])]
    artifact_key = str(Path(plan['model_path']).name + '/model.safetensors')
    if (receipt.get('kind') != spec['kind'] or receipt.get('approved') is not True
            or receipt.get('phase') != phase or receipt.get('stage') != stage_name
            or receipt.get('plan_sha256') != sha(path(root, base / 'manifest.json'))
            or receipt.get('controller_sha256') != controller_sha
            or receipt.get('artifact_sha256') != plan['asset_sha256'][artifact_key]
            or receipt.get('reference_labels_read') is not False
            or claim != {'phase': phase, 'stage': stage_name,
                         'plan_sha256': sha(path(root, base / 'manifest.json')),
                         'receipt_sha256': evidence['receipt']['sha256'],
                         'policy': 'exclusive one attempt; uncertain started positions are not replayed'}
            or completion != {'phase': phase, 'stage': stage_name,
                              'plan_sha256': sha(path(root, base / 'manifest.json')),
                              'count': plan['stage_inputs'][stage_name]['limit'],
                              'records_sha256': evidence['records']['sha256'],
                              'raw_sha256': evidence['raw']['sha256'],
                              'journal_sha256': evidence['journal']['sha256']}):
        raise ValueError('Alex stage receipt, claim or completion binding differs')
    raw = rows(root, folder / names['raw'])
    records = rows(root, folder / names['records'])
    journal = rows(root, folder / names['journal'])
    count = plan['stage_inputs'][stage_name]['limit']
    if (len(raw) != count or len(records) != count or
            [event.get('event') for event in journal] !=
            ['phase_started'] + ['request_started', 'request_completed'] * count + ['phase_completed']
            or journal[0] != {'event': 'phase_started', 'phase': phase, 'stage': stage_name}
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('Alex terminal stage count or event sequence differs')
    for i, (capture, record, request) in enumerate(zip(raw, records, plan['requests'][:count])):
        started, completed = journal[2*i+1:2*i+3]
        try: prediction = projected(spec, capture['nli_probabilities']); status = 'ok'
        except ValueError: prediction = None; status = 'invalid_output'
        seconds = capture.get('client_prediction_seconds')
        if (capture.get('id') != request['id'] or record.get('id') != request['id']
                or started.get('id') != request['id'] or completed.get('id') != request['id']
                or capture.get('attempt_id') != started.get('attempt_id')
                or record.get('attempt_id') != started.get('attempt_id')
                or completed.get('attempt_id') != started.get('attempt_id')
                or capture.get('request_sha256') != request['request_sha256']
                or record.get('request_sha256') != request['request_sha256']
                or record.get('input_sha256') != request['input_sha256']
                or record.get('phase') != phase or record.get('stage') != stage_name
                or started.get('request_sha256') != request['request_sha256']
                or capture.get('nli_inputs') != request['nli_inputs']
                or capture.get('hypothesis_order') != [[key, label] for key in KEYS for label in VALUES[key]]
                or record.get('raw_sha256') != digest(spec['module'].canonical(capture))
                or record.get('status') != status or record.get('prediction') != prediction
                or record.get('reference_labels_read') is not False
                or record.get('model_path') != plan['model_path']
                or record.get('artifact_revision') != plan['artifact_revision']
                or record.get('device') != plan['runtime']['device']
                or record.get('dtype') != plan['runtime']['dtype']
                or record.get('quantization') != 'none'
                or record.get('batch_size') != 4 or record.get('max_tokens') != 4096
                or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
                or record.get('client_prediction_seconds') != seconds
                or completed.get('status') != status):
            raise ValueError(f'Alex raw, record or journal binding differs at {phase}/{stage_name}/{request["id"]}')
    return records, raw, evidence


def usage(records, raw, requests):
    durations = [capture['client_prediction_seconds'] for capture in raw]
    return {'clientPredictionSeconds': sum(durations),
            'clientPredictionMeanSeconds': sum(durations) / len(durations) if durations else None,
            'nativeNliInputTokenPositions': sum(sum(row['input_tokens'] for row in request['nli_inputs'])
                                                for request in requests),
            'generatedOutputTokens': None, 'isolatedInferenceSeconds': None,
            'actualCostUsd': None, 'costKnown': False}


def class_counts(indexed):
    return {key: dict(sorted(Counter(row['prediction'][key] for row in indexed.values()
                                      if shared.outcome(row) == 'valid').items())) for key in KEYS}


def confusion(indexed, labels):
    """Count all 60 references, including invalid or missing predictions."""
    result = {}
    for field in KEYS:
        columns = (*VALUES[field], '__invalid_or_missing__')
        matrix = {actual: {predicted: 0 for predicted in columns} for actual in VALUES[field]}
        for rid in IDS:
            record = indexed.get(rid)
            predicted = (record['prediction'][field] if record is not None and
                         shared.outcome(record) == 'valid' else '__invalid_or_missing__')
            matrix[labels[rid][field]][predicted] += 1
        result[field] = matrix
    return result


def closed_repeat(root, plan, labels, spec, base, phase, bind):
    folder = base / phase
    if not path(root, folder / 'development.completion.json').exists():
        return None, None
    smoke_records, smoke_raw, smoke_evidence = stage(root, plan, spec, base, phase, 'smoke', bind)
    records, raw, development_evidence = stage(root, plan, spec, base, phase, 'development', bind)
    inspection_path = folder / 'smoke-inspection.json'
    inspection_binding = bind(inspection_path)
    inspection = json.loads(path(root, inspection_path).read_text())
    dev_receipt = json.loads(path(root, folder / 'development.root-review.json').read_text())
    if (inspection.get('phase') != phase or inspection.get('plan_sha256') != sha(path(root, base / 'manifest.json'))
            or inspection.get('smoke_records_sha256') != smoke_evidence['records']['sha256']
            or inspection.get('inspected_ids') != IDS[:3] or inspection.get('approved') is not True
            or dev_receipt.get('smoke_inspection_sha256') != inspection_binding['sha256']
            or any(record.get('status') != 'ok' for record in smoke_records)):
        raise ValueError('Alex development did not bind inspected successful smoke')
    indexed = {record['id']: record for record in records}
    entry = {'completionStatus': 'complete', 'score': shared.score(indexed, labels, IDS),
             'predictedClassCounts': class_counts(indexed),
             'confusionCounts': confusion(indexed, labels),
             'usage': usage(records, raw, plan['requests']),
             'evidence': {'smoke': smoke_evidence, 'smokeInspection': inspection_binding,
                          'development': development_evidence}}
    return entry, indexed


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build_one(root, config_id):
    spec = CONFIGS[config_id]
    plan, labels, bind, bindings, external, base = context(root, config_id)
    old = historical(root, plan, labels, spec, bind)
    data = {name: {} for name in PASSES}
    indexed = {}
    missing = []
    previous_open = False
    for name in PASSES:
        phase = f'{name}/P0'
        entry, records = closed_repeat(root, plan, labels, spec, base, phase, bind)
        if entry is None:
            folder = base / phase
            status = ('claimed_in_progress_or_interrupted' if any(path(root, folder / f'{stage}.claim.json').exists()
                      for stage in ('smoke', 'development')) else 'not_started')
            missing.append({'pass': name, 'condition': 'P0', 'status': status})
            previous_open = True
        else:
            if previous_open:
                raise ValueError('Later closed Alex pass follows an open predecessor')
            data[name]['P0'] = entry
            indexed[name] = records
    complete = [name for name in PASSES if 'P0' in data[name]]
    scores = [data[name]['P0']['score'] for name in complete]
    summary = {'P0': {'allFour': stats([score['allFour'] for score in scores]),
                      'fields': {field: stats([score['fields'][field] for score in scores]) for field in KEYS}}}
    flips = [{'condition': 'P0', 'from': left, 'to': right,
              **shared.flip(indexed[left], indexed[right], IDS)}
             for i, left in enumerate(complete) for right in complete[i+1:]]
    across = {}
    if len(complete) == 3:
        eligible = [rid for rid in IDS if all(shared.outcome(indexed[name][rid]) == 'valid' for name in complete)]
        across['P0'] = {'denominator': len(eligible), 'excludedIds': [rid for rid in IDS if rid not in eligible],
            'fields': {field: [rid for rid in eligible if len({indexed[name][rid]['prediction'][field]
                        for name in complete}) > 1] for field in KEYS},
            'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[name][rid]['prediction'][field]
                        for field in KEYS) for name in complete}) > 1]}
    limitations = ['Historical Alex outputs are observational and excluded from fresh-pass scores and flips.']
    if config_id == 'alex-openjev4b-native-p0-v1':
        limitations.append('The 4B historical composite includes an unknown prior DEV-046 attempt; its first outcome and duration are not reconstructed.')
    limitations.extend([
        'Only native P0 output stability is measured; generative P1/P2 prompts do not apply.',
        'The same 60 fictional reviews are repeated, not new independent cases.',
        'Open or in-flight phases are omitted before reading partial records.',
        'Client prediction time includes local overhead and is not isolated inference time.',
        'Native NLI input-token positions are not billed API tokens; generated output tokens are unavailable.',
        'Local hardware and electricity costs were not measured; cost is unknown, not zero.',
        'Model assets outside the repository are declared by the frozen manifest; this portable report does not rehash them.'])
    return {'schema': 'alex-native-repeat-findings-v1', 'configuration': config_id,
            'displayName': spec['display'], 'model': config_id, 'provider': 'Local native MPS',
            'method': 'native-output-stability', 'conditionOrder': ['P0'],
            'referenceVersion': '0.2', 'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'denominator': 60, 'completedConditions': len(complete), 'plannedConditions': 3,
            'passOrder': list(PASSES), 'passes': data, 'missingPasses': missing,
            'partialPasses': [], 'historicalObservation': old,
            'threePassSummary': summary, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': [],
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in IDS).items()))
                                     for field in KEYS},
            'predictedClassCounts': {name: data[name]['P0']['predictedClassCounts'] for name in complete},
            'sourceBindings': bindings, 'declaredExternalSourceHashes': external,
            'declaredModelAssetHashes': plan['asset_sha256'],
            'declaredModelArtifactManifestSha256': plan['artifact_manifest_sha256'],
            'hardware': plan['runtime']['hardware'], 'limitations': limitations}


def build(root=ROOT, configs=tuple(CONFIGS)):
    series = [build_one(Path(root), config) for config in configs]
    return {'schema': 'alex-native-repeat-report-v1', 'series': series,
            'availableConfigurations': [item['configuration'] for item in series]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    report = build()
    content = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(content)
    print('Alex native: ' + ', '.join(f"{s['configuration']} {s['completedConditions']}/3" for s in report['series']))


if __name__ == '__main__': main()
