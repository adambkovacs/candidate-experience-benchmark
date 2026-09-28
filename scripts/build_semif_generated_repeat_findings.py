#!/usr/bin/env python3
"""Build offline, source-bound findings for SemIf's fresh generated three-pass study."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import valid
from semif_prompt_execution import parse as strict_parse

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/semif-generated-fresh-v1')
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = 'b5b13e48cd92979404aeb35beb2f17adf738f8358b22a5f5f5a4a90e7c66ed38'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n'


def inside(root, relative):
    target = (Path(root) / relative).resolve()
    target.relative_to(Path(root).resolve())
    return target


def load_jsonl(path):
    raw = Path(path).read_bytes()
    if not raw or not raw.endswith(b'\n') or any(not line for line in raw.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {path}')
    return [json.loads(line) for line in raw.splitlines()]


def binder(root):
    bindings = []
    def bind(relative, expected=None):
        relative = Path(relative)
        raw = inside(root, relative).read_bytes()
        actual = digest(raw)
        if expected is not None and expected != actual:
            raise ValueError(f'Bound source changed: {relative}')
        item = {'path': str(relative), 'sha256': actual}
        if item not in bindings:
            bindings.append(item)
        return item
    return bind, bindings


def source_context(root):
    bind, bindings = binder(root)
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(inside(root, MANIFEST).read_text())
    expected_schedule = [f'fresh{name}/{condition}' for name, order in
                         ((1, ('P0', 'P2', 'P1')), (2, ('P1', 'P0', 'P2')),
                          (3, ('P2', 'P1', 'P0'))) for condition in order]
    if (plan.get('schema') != 'semif-generated-fresh-three-admission-v1'
            or plan.get('status') != 'offline_candidate_no_live_receipts'
            or plan.get('reference_labels_read') is not False
            or plan.get('schedule') != expected_schedule
            or plan.get('stage_inputs') != {'smoke': {'limit': 3}, 'development': {'limit': 60}}
            or plan.get('historical', {}).get('eligible_as_first_pass') is not False
            or plan['historical'].get('unknown_started_id') != 'DEV-033'
            or [plan['historical'].get(k) for k in ('saved_P2', 'valid_P2', 'intrinsic_invalid_P2')] != [59, 57, 2]):
        raise ValueError('Frozen generated plan or historical exclusion differs')
    for name, expected in plan['source_sha256'].items():
        bind(name, expected)
    bind(plan['inputs']['file'], plan['inputs']['sha256'])
    bind(plan['historical']['execution_manifest']['file'],
         plan['historical']['execution_manifest']['sha256'])
    for item in plan['historical']['evidence'].values():
        bind(item['file'], item['sha256'])
    bind(LABELS, LABELS_SHA)
    inputs = load_jsonl(inside(root, plan['inputs']['file']))
    references = load_jsonl(inside(root, LABELS))
    ids = [f'DEV-{n:03d}' for n in range(1, 61)]
    if ([row.get('id') for row in inputs] != ids or
            any(set(row) != {'id', 'feedback'} or not isinstance(row['feedback'], str)
                for row in inputs) or
            [row.get('id') for row in references] != ids or
            any(row.get('review_version') != '0.2' or not valid(row.get('proposed_labels'))
                for row in references)):
        raise ValueError('Frozen development membership or provisional references differ')
    for condition in CONDITIONS:
        requests = plan['requests'][condition]
        if ([item.get('id') for item in requests] != ids or
                any(item.get('input_sha256') != digest(row['feedback'].encode())
                    for item, row in zip(requests, inputs))):
            raise ValueError('Frozen input-only request membership differs')
    history = plan['historical']['evidence']
    metadata = load_jsonl(inside(root, history['P0']['file']))[0]['metadata']
    return plan, ids, {row['id']: row['proposed_labels'] for row in references}, metadata, bind, bindings


def stage(root, plan, phase, name, plan_sha, metadata, bind):
    folder = BASE / phase
    files = {key: folder / f'{name}.{suffix}' for key, suffix in
             (('receipt', 'root-review.json'), ('claim', 'claim.json'),
              ('journal', 'journal.jsonl'), ('events', 'events.jsonl'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('completion', 'completion.json'))}
    evidence = {key: bind(path) for key, path in files.items()}
    receipt = json.loads(inside(root, files['receipt']).read_text())
    claim = json.loads(inside(root, files['claim']).read_text())
    completion = json.loads(inside(root, files['completion']).read_text())
    count = plan['stage_inputs'][name]['limit']
    expected = plan['requests'][phase.split('/')[1]][:count]
    if (receipt.get('kind') != 'root-reviewed-semif-generated-fresh-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != name or receipt.get('plan_sha256') != plan_sha
            or receipt.get('controller_sha256') != plan['source_sha256']['scripts/semif_generated_repeat_admission.py']
            or receipt.get('reference_labels_read') is not False):
        raise ValueError('Generated stage review receipt differs')
    if claim != {'phase': phase, 'stage': name, 'plan_sha256': plan_sha,
                 'receipt_sha256': evidence['receipt']['sha256'],
                 'controller_sha256': plan['source_sha256']['scripts/semif_generated_repeat_admission.py'],
                 'policy': 'one attempt; unknown started positions never replayed'}:
        raise ValueError('Generated stage claim differs')
    if completion != {'phase': phase, 'stage': name, 'plan_sha256': plan_sha,
                      'output_sha256': evidence['records']['sha256'], 'count': count}:
        raise ValueError('Generated stage completion differs')
    journal = load_jsonl(inside(root, files['journal']))
    events = load_jsonl(inside(root, files['events']))
    captures = load_jsonl(inside(root, files['raw']))
    records = load_jsonl(inside(root, files['records']))
    if (len(records) != count or len(captures) != count
            or len(journal) != 2 + 2 * count
            or journal[0] != {'event': 'phase_started', 'phase': phase, 'stage': name}
            or journal[-1] != {'event': 'phase_completed', 'count': count}):
        raise ValueError('Generated stage incomplete')
    indices = {request['id']: i for i, request in enumerate(expected)}
    positions = [indices.get(event.get('id'), -1) for event in events]
    if -1 in positions or positions != sorted(positions):
        raise ValueError('Generated stream events out of order')
    for index, (request, record, capture) in enumerate(zip(expected, records, captures)):
        ident = request['id']
        started, ended = journal[1 + 2 * index:3 + 2 * index]
        if (started.get('event') != 'request_started' or started.get('id') != ident
                or started.get('request_sha256') != request['messages_sha256']
                or not started.get('started_utc')
                or ended != {'event': 'request_completed', 'id': ident, 'status': record.get('status')}):
            raise ValueError(f'Generated journal differs at {ident}')
        chunks = [event for event in events if event['id'] == ident]
        if not chunks or any(event.get('prompt_tokens') != request['input_tokens'] for event in chunks):
            raise ValueError(f'Generated token events differ at {ident}')
        raw = {'content': ''.join(event['text'] for event in chunks),
               'finish_reason': chunks[-1]['finish_reason']}
        if (raw['finish_reason'] not in ('stop', 'length')
                or capture != {'id': ident, 'request_sha256': request['messages_sha256'],
                               'metadata': metadata, 'raw_response': raw,
                               'stream_events_sha256': digest(''.join(canonical(event) for event in chunks).encode())}):
            raise ValueError(f'Generated raw stream differs at {ident}')
        prediction = strict_parse(raw['content'], raw['finish_reason'] == 'stop')
        status = 'ok' if valid(prediction) else 'invalid_output'
        expected_fields = {'id': ident, 'phase': phase, 'stage': name, 'status': status,
                           'prediction': prediction, 'attempts': 1,
                           'request_sha256': request['messages_sha256'],
                           'rendered_prompt_sha256': request['rendered_prompt_sha256'],
                           'input_token_ids_sha256': request['input_token_ids_sha256'],
                           'input_tokens': request['input_tokens'],
                           'input_sha256': request['input_sha256'],
                           'policy_sha256': plan['policy_prefix_sha256'],
                           'artifact_revision': plan['artifact_revision'],
                           'runtime_versions': plan['runtime']['packages'],
                           'host': plan['runtime']['platform'], 'metadata': metadata,
                           'raw_sha256': digest(canonical(raw).encode())}
        if any(record.get(key) != value for key, value in expected_fields.items()):
            raise ValueError(f'Generated projection differs at {ident}')
        for key in ('elapsed_seconds', 'output_tokens'):
            value = record.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError(f'Generated measured {key} differs at {ident}')
        if record['output_tokens'] != chunks[-1]['generation_tokens']:
            raise ValueError(f'Generated output token mirror differs at {ident}')
    return {record['id']: record for record in records}, records, evidence


def complete_phase(root, plan, phase, ids, labels, metadata, bind):
    folder = BASE / phase
    if not inside(root, folder / 'development.completion.json').exists():
        return None, None
    plan_sha = MANIFEST_SHA
    smoke, smoke_rows, smoke_evidence = stage(root, plan, phase, 'smoke', plan_sha, metadata, bind)
    records, rows, dev_evidence = stage(root, plan, phase, 'development', plan_sha, metadata, bind)
    inspection_path = folder / 'smoke-inspection.json'
    inspection_binding = bind(inspection_path)
    inspection = json.loads(inside(root, inspection_path).read_text())
    receipt = json.loads(inside(root, folder / 'development.root-review.json').read_text())
    if (inspection.get('phase') != phase or inspection.get('plan_sha256') != plan_sha
            or inspection.get('smoke_sha256') != smoke_evidence['records']['sha256']
            or inspection.get('inspected_ids') != ids[:3]
            or inspection.get('approved') is not True or not inspection.get('inspector')
            or receipt.get('smoke_inspection_sha256') != inspection_binding['sha256']):
        raise ValueError('Generated development lacks inspected smoke')
    if any(row['status'] != 'ok' for row in smoke_rows):
        if not (inspection.get('accepted_unchanged_invalids') is True
                and inspection.get('failure_class') == 'intrinsic_schema'
                and inspection.get('inspection_reason')):
            raise ValueError('Generated intrinsic invalid smoke not accepted unchanged')
    usage = {'requestCount': len(rows),
             'requestSeconds': [row['elapsed_seconds'] for row in rows],
             'requestSecondsTotal': sum(row['elapsed_seconds'] for row in rows),
             'clientRunSecondsLowerBound': sum(row['elapsed_seconds'] for row in rows),
             'inferenceSeconds': None,
             'tokens': {'input_tokens': sum(row['input_tokens'] for row in rows),
                        'output_tokens': sum(row['output_tokens'] for row in rows),
                        'cached_input_tokens': None, 'cache_write_input_tokens': None,
                        'reasoning_output_tokens': None},
             'actualCostUsd': None,
             'costNote': 'Local hardware and electricity cost not measured.'}
    classes = {field: dict(sorted(Counter(records[rid]['prediction'][field]
                           for rid in ids if shared.outcome(records[rid]) == 'valid').items()))
               for field in FIELDS}
    confusion = {field: {truth: dict(sorted(Counter(records[rid]['prediction'][field]
                if shared.outcome(records[rid]) == 'valid' else '__invalid_or_missing__'
                for rid in ids if labels[rid][field] == truth).items()))
                for truth in sorted({labels[rid][field] for rid in ids})}
                for field in FIELDS}
    return {'completionStatus': 'complete', 'score': shared.score(records, labels, ids),
            'predictedClassCounts': classes, 'confusionCounts': confusion, 'usage': usage,
            'evidence': {'smoke': smoke_evidence, 'smokeInspection': inspection_binding,
                         'development': dev_evidence}}, records


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / 3 if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build(root=ROOT):
    root = Path(root)
    plan, ids, labels, metadata, bind, bindings = source_context(root)
    data = {name: {} for name in PASSES}
    indexed = {}
    missing = []
    first_open = False
    for phase in plan['schedule']:
        pass_name, condition = phase.split('/')
        entry, records = complete_phase(root, plan, phase, ids, labels, metadata, bind)
        if entry is None:
            folder = BASE / phase
            claimed = any(inside(root, folder / f'{stage}.claim.json').exists()
                          for stage in ('smoke', 'development'))
            missing.append({'pass': pass_name, 'condition': condition,
                            'status': 'claimed_in_progress_or_interrupted' if claimed else 'not_started'})
            first_open = True
        else:
            if first_open:
                raise ValueError('Closed generated phase follows an open predecessor')
            data[pass_name][condition] = entry
            indexed[phase] = records
    deltas = []
    for name in PASSES:
        if 'P0' not in data[name]:
            continue
        for condition in ('P1', 'P2'):
            if condition in data[name]:
                a, b = data[name]['P0']['score'], data[name][condition]['score']
                deltas.append({'pass': name, 'from': 'P0', 'to': condition,
                               'denominator': 60, 'allFour': b['allFour'] - a['allFour'],
                               'fields': {field: b['fields'][field] - a['fields'][field]
                                          for field in FIELDS}})
    prompt_flips = [{'pass': name, 'from': 'P0', 'to': condition,
                     **shared.flip(indexed[f'{name}/P0'], indexed[f'{name}/{condition}'], ids)}
                    for name in PASSES for condition in ('P1', 'P2')
                    if f'{name}/P0' in indexed and f'{name}/{condition}' in indexed]
    flips = [{'condition': condition, 'from': left, 'to': right,
              **shared.flip(indexed[f'{left}/{condition}'], indexed[f'{right}/{condition}'], ids)}
             for condition in CONDITIONS for i, left in enumerate(PASSES)
             for right in PASSES[i + 1:]
             if f'{left}/{condition}' in indexed and f'{right}/{condition}' in indexed]
    summary = {condition: {'allFour': stats([data[name][condition]['score']['allFour']
                                             for name in PASSES if condition in data[name]]),
                           'fields': {field: stats([data[name][condition]['score']['fields'][field]
                                                    for name in PASSES if condition in data[name]])
                                      for field in FIELDS}}
               for condition in CONDITIONS}
    changes = {}
    for condition in CONDITIONS:
        if not all(f'{name}/{condition}' in indexed for name in PASSES):
            continue
        triplet = [indexed[f'{name}/{condition}'] for name in PASSES]
        eligible = [rid for rid in ids if all(shared.outcome(run[rid]) == 'valid' for run in triplet)]
        changes[condition] = {'denominator': len(eligible),
                              'excludedIds': [rid for rid in ids if rid not in eligible],
                              'fields': {field: [rid for rid in eligible if len({run[rid]['prediction'][field]
                                                                                for run in triplet}) > 1]
                                         for field in FIELDS},
                              'fourFieldVector': [rid for rid in eligible if len({tuple(
                                  run[rid]['prediction'][field] for field in FIELDS) for run in triplet}) > 1]}
    series = {'schema': 'semif-generated-fresh-repeat-findings-v1',
              'configuration': 'semif-generated-fresh-v1',
              'displayName': 'SemIf · generated MLX · fresh three-pass',
              'model': 'semif-generated-bf16', 'provider': 'Local native MLX',
              'method': 'fresh-native-generated-repeat', 'conditionOrder': list(CONDITIONS),
              'passOrder': list(PASSES), 'referenceVersion': '0.2',
              'referenceStatus': 'AI reviewed provisional, not independent adjudication',
              'confusionOrientation': 'rows: provisional reference; columns: observed prediction',
              'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field]
                                            for rid in ids).items())) for field in FIELDS},
              'denominator': 60, 'completedConditions': len(indexed),
              'plannedConditions': 9, 'missingPasses': missing, 'partialPasses': [],
              'passes': data, 'threePassSummary': summary,
              'pairwiseFlips': flips, 'changesAcrossThreePasses': changes,
              'withinPassPromptDeltas': deltas, 'withinPassPromptFlips': prompt_flips,
              'sourceBindings': bindings,
              'declaredExternalSourceHashes': plan['runtime']['current_source_hashes'],
              'checkpointAssetHashes': plan['runtime']['assets_sha256'],
              'hardware': plan['runtime']['hardware'],
              'historicalObservationalOnly': {'eligibleAsFirstPass': False,
                                               'unknownStartedId': 'DEV-033',
                                               'savedP2': 59, 'validP2': 57,
                                               'intrinsicInvalidP2': 2},
              'limitations': ['Historical generated runs are observational and excluded from fresh three-pass scores.',
                              'The same 60 fictional development records are repeated; passes are dependent.',
                              'Reference labels are provisional and were excluded from inference requests.',
                              'Open or interrupted stages are unscored; unknown starts are never replayed.',
                              'External model and runtime files are declared by the frozen plan, not rehashed in a clean checkout.',
                              'Elapsed time is client observed, not isolated model inference time.',
                              'Local hardware and electricity cost are unmeasured; unknown is not zero.']}
    return {'schema': 'semif-generated-fresh-repeat-report-v1', 'series': [series],
            'availableConfigurations': [series['configuration']]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale SemIf generated report: {args.output}')
    else:
        args.output.write_text(content)
    print('SemIf generated repeat report checked')


if __name__ == '__main__':
    main()
