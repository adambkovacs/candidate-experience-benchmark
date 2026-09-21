#!/usr/bin/env python3
"""Offline report only. Reads reference labels; never performs inference or network calls."""
import argparse
import csv
import hashlib
import json
import math
import statistics
from pathlib import Path
from development_benchmark import ROOT, KEYS, read_rows, score, valid



def validate_development_dataset(inputs, refs):
    input_ids = [row['id'] for row in inputs]
    reference_ids = [row['id'] for row in refs]
    if (len(input_ids) != 60 or len(reference_ids) != 60 or
            len(set(input_ids)) != 60 or len(set(reference_ids)) != 60 or
            set(input_ids) != set(reference_ids)):
        raise ValueError('Development report requires exactly60 unique matched input/reference IDs')
    if any(row.get('split') != 'development' or not valid(row.get('proposed_labels')) for row in refs):
        raise ValueError('References must contain valid development labels')


def reject_smoke_artifact(name, rows):
    if any('smoke' in part.lower() for part in Path(name).parts):
        raise ValueError('Smoke artifact cannot supply development predictions or timing: ' + str(name))
    if any(row.get('phase', 'development') != 'development' for row in rows):
        raise ValueError('Artifact row phase must be development: ' + str(name))


def load_timing_attempts(config, known_ids, root=ROOT):
    """Read explicitly declared development evidence, counting each attempt once.

    Reclassification changes judgments, not the underlying timed request. A retry
    must retain its own start timestamp (or provider request/attempt identifier).
    Timestamp-free deterministic baselines remain valid.
    """
    if config.get('attempt_phase') != 'development':
        raise ValueError('Registry attempt_phase must explicitly equal development')
    paths = config.get('attempt_files', [config['predictions_file']])
    if not isinstance(paths, list) or not paths:
        raise ValueError('attempt_files must be a nonempty list')
    seen_paths, seen_contents, seen_attempts = set(), set(), set()
    attempts = []
    for name in paths:
        path = (root / name).resolve()
        if path in seen_paths:
            raise ValueError('Repeated attempt path: ' + str(name))
        seen_paths.add(path)
        if 'smoke' in path.name.lower() or any('smoke' in part.lower() for part in Path(name).parts[:-1]):
            raise ValueError('Smoke artifact cannot supply development timing: ' + str(name))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen_contents:
            raise ValueError('Repeated attempt content: ' + str(name))
        seen_contents.add(digest)
        for row in read_rows(path):
            record_id = row.get('id')
            if record_id not in known_ids:
                raise ValueError('Unknown development record ID: ' + str(record_id))
            if row.get('phase', 'development') != 'development':
                raise ValueError('Attempt row phase must be development: ' + str(name))
            elapsed = row.get('elapsed_seconds')
            if elapsed is not None and (isinstance(elapsed, bool) or
                    not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0):
                raise ValueError('Invalid elapsed_seconds: ' + str(name))
            # Prefer recorded request identity. Do not key by the input hash:
            # every genuine retry of a record deliberately has the same input.
            start = row.get('started_utc') or row.get('started_at')
            request_id = row.get('request_id') or row.get('attempt_id')
            if start or request_id:
                identity = ('request', record_id, start, request_id, elapsed)
            else:
                # Raw fields survive status/prediction/audit reclassification.
                raw = {key: value for key, value in row.items()
                       if key.startswith('raw_') or key in ('elapsed_seconds', 'usage', 'stats', 'returncode')}
                identity = ('raw', record_id, json.dumps(raw, sort_keys=True, separators=(',', ':')))
            if identity in seen_attempts:
                raise ValueError('Repeated raw attempt: ' + str(record_id) + ' in ' + str(name))
            seen_attempts.add(identity)
            attempts.append(row)
    return attempts


def build(registries, output):
    input_rows = read_rows(ROOT/'data/pilot/inputs.jsonl')
    refs = read_rows(ROOT/'data/pilot/proposed_labels.jsonl')
    validate_development_dataset(input_rows, refs)
    inputs = {r['id']: r['feedback'] for r in input_rows}
    pairs = json.loads((ROOT/'data/pilot/pairs.json').read_text())
    summaries, cases, seen = [], [], set()
    for registry in registries:
        for config in json.loads(Path(registry).read_text()):
            if config['id'] in seen:
                raise ValueError('Duplicate configuration: '+config['id'])
            seen.add(config['id'])
            summary = dict(config)
            path = config.get('predictions_file')
            if not path:
                summaries.append(summary)
                continue
            predictions = read_rows(ROOT/path)
            reject_smoke_artifact(path, predictions)
            evaluation = score(refs, predictions, pairs)
            index = {r['id']: r for r in predictions}
            attempts = load_timing_attempts(config, set(inputs))
            durations = {}
            for attempt in attempts:
                elapsed = attempt.get('elapsed_seconds')
                if elapsed is not None:
                    durations.setdefault(attempt['id'], []).append(elapsed)
            totals = sorted(sum(values) for values in durations.values())
            summary.update(evaluation=evaluation, prediction_records=len(predictions),
                prediction_sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),
                attempt_records=len(attempts),
                exact_match=sum(r.get('status')=='ok' and r.get('prediction')==ref['proposed_labels']
                    for ref in refs for r in [index.get(ref['id'], {})]),
                timing={'attempt_phase':'development', 'provenance_note':'Unique development attempts only; smoke and duplicate evidence rejected.', 'timed_records':len(totals), 'sum_record_seconds':sum(totals),
                    'median_seconds':statistics.median(totals) if totals else None,
                    'p95_nearest_rank_seconds':totals[math.ceil(.95*len(totals))-1] if totals else None,
                    'note':'Per-record end-to-end time, summing listed attempts. Not wall-clock batch time. Separately recorded model_load_seconds is excluded; these are not cold-start timings. Compare within execution surface only.'})
            for ref in refs:
                row = index.get(ref['id'], {})
                prediction = row.get('prediction')
                usable = row.get('status')=='ok' and valid(prediction)
                differences = [key for key in KEYS if not usable or prediction[key]!=ref['proposed_labels'][key]]
                cases.append({'configuration':config['id'], 'id':ref['id'],
                    'feedback':inputs[ref['id']], 'reference':ref['proposed_labels'],
                    'prediction':prediction, 'status':row.get('status','missing'),
                    'different_fields':differences,
                    'classification':'output_or_service_failure' if not usable else 'reference_disagreement' if differences else 'agreement'})
            summaries.append(summary)
    output.mkdir(parents=True, exist_ok=True)
    (output/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    (output/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    lines=['# Development benchmark: observed configurations','',
        'All judgments are compared against provisional, same-assistant AI-reviewed labels on the same 60 synthetic development records. These are not human ground truth or held-out results. The remaining 340 records are ungenerated.','',
        'Each cell below is a count out of 60. Missing or failed outputs count as incorrect; partial configurations must not be ranked against complete ones. Retry-inclusive rows are separate views of the same configuration, not independent experiments.','',
        '| Configuration | Status | Valid | Sentiment | Follow-up | Serious concern | Testimonial | All four |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for item in summaries:
        e=item.get('evaluation')
        cells=[str(e['valid_outputs'])]+[str(e['metrics'][k]['correct']) for k in KEYS]+[str(item['exact_match'])] if e else ['—']*6
        lines.append('| '+' | '.join([item['id'],item['status']]+cells)+' |')
    lines += ['', 'Timing includes process/runtime and transport overhead as applicable. Cached prompts, local power mode, and CLI wrappers differ. Do not interpret a cross-surface latency ranking as model-only speed.', '']
    for item in summaries:
        lines += ['**'+item['id']+'**', '', str(item.get('notes','')), '']
        if item.get('predictions_file'):
            lines += ['Evidence: `'+item['predictions_file']+'`; SHA-256 `'+item['prediction_sha256']+'`.', '']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    with (output/'judgment-counts.csv').open('w',newline='') as file:
        writer=csv.writer(file,lineterminator="\n");writer.writerow(['configuration','status','valid',*KEYS,'exact_match','denominator'])
        for item in summaries:
            e=item.get('evaluation')
            if e:writer.writerow([item['id'],item['status'],e['valid_outputs'],*[e['metrics'][k]['correct'] for k in KEYS],item['exact_match'],60])
    template=(ROOT/'scripts/report_template.html').read_text()
    payload=json.dumps({'summaries':summaries,'cases':cases}).replace('<','\\u003c')
    (output/'explorer.html').write_text(template.replace('__BENCHMARK_DATA__',payload))
    print(json.dumps({'configurations':len(summaries),'case_rows':len(cases),'output':str(output)}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry',action='append',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();build(a.registry,a.output)
