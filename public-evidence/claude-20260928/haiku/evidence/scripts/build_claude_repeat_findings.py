#!/usr/bin/env python3
"""Build an offline report for the Opus 5.5 medium Claude subscription repeats."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
import claude_repeat_study as study
from claude_batch_benchmark import parse_batch_result, isolation_ok
from claude_benchmark import safe_diagnostic
from development_benchmark import digest, valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/claude-opus55-medium-batch10')
LABELS = Path('data/pilot/proposed_labels.jsonl')
PASSES = ('original', 'repeat2', 'repeat3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS


def _file(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(root, relative):
    raw = _file(root, relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete evidence: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


def _binder(root):
    sources = []

    def bind(relative, expected=None):
        relative = Path(relative)
        actual = _sha(_file(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Source hash changed: {relative}')
        result = {'path': str(relative), 'sha256': actual}
        if result not in sources:
            sources.append(result)
        return result

    return bind, sources


def _money(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _usage(attempts):
    tokens = {}
    for name, keys in {
        'input_tokens': ('input_tokens',),
        'cache_creation_input_tokens': ('cache_creation_input_tokens',),
        'cache_read_input_tokens': ('cache_read_input_tokens',),
        'output_tokens': ('output_tokens',),
        'thinking_tokens': ('output_tokens_details', 'thinking_tokens'),
    }.items():
        values = []
        for attempt in attempts:
            value = attempt.get('usage')
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            values.append(value)
        tokens[name] = sum(values) if values and all(type(x) is int and x >= 0 for x in values) else None
    seconds = [attempt.get('elapsed_seconds') for attempt in attempts]
    seconds_total = (sum(seconds) if seconds and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in seconds) else None)
    estimates = [_money(attempt.get('cli_estimated_api_equivalent_usd')) for attempt in attempts]
    estimate = str(sum(estimates, Decimal(0))) if estimates and all(x is not None for x in estimates) else None
    return {'requestCount': len(attempts), 'requestSeconds': seconds,
            'requestSecondsTotal': seconds_total, 'requestTimeKind': 'client_wall_clock',
            'inferenceSeconds': None, 'tokens': tokens,
            'cliListPriceEstimateUsd': estimate, 'actualCostUsd': None,
            'costNote': 'CLI API-equivalent list-price estimate; subscription billing and quota consumed are unknown.'}


def _source_context(root):
    bind, sources = _binder(root)
    bind(LABELS, shared.PINNED_SHA[str(LABELS)])
    label_rows = _rows(root, LABELS)
    ids = [row['id'] for row in label_rows]
    if ids != [f'DEV-{i:03d}' for i in range(1, 61)] or any(row.get('review_version') != '0.2' for row in label_rows):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    bind(study.COVERAGE)
    bind(study.PAIR)
    pair = json.loads(_file(root, study.PAIR).read_text())
    if pair.get('parent_baseline_id') != study.CONFIG or pair.get('controls', {}).get('requested_model') != study.MODEL:
        raise ValueError('Historical Claude configuration changed')
    if (pair['controls'].get('effort'), pair['controls'].get('workflow'), pair['controls'].get('auth_method')) != (study.EFFORT, 'batch10', 'claude.ai'):
        raise ValueError('Historical Claude controls changed')
    plans = {}
    for repeat in ('repeat2', 'repeat3'):
        relative = BASE / repeat / 'manifest.json'
        plan_binding = bind(relative)
        plan = json.loads(_file(root, relative).read_text())
        if plan != study.plan_data(repeat):
            raise ValueError(f'Frozen Claude plan changed: {repeat}')
        for item in plan['source_bindings']:
            bind(item['path'], item['sha256'])
        plans[repeat] = (plan, plan_binding)
    return ids, labels, pair, plans, bind, sources


def _historical(root, condition, pair, plan, ids, labels, bind):
    sources = pair['conditions'][condition]
    record_binding = bind(sources['predictions']['file'], sources['predictions']['sha256'])
    attempt_binding = bind(sources['request_evidence']['file'], sources['request_evidence']['sha256'])
    records = _rows(root, record_binding['path'])
    attempts = _rows(root, attempt_binding['path'])
    if len(records) != 60 or [r.get('id') for r in records] != ids or len(attempts) != 6:
        raise ValueError('Historical Claude membership changed')
    indexed = {}
    for index, attempt in enumerate(attempts):
        planned = plan['conditions'][condition]['development'][index]
        members = ids[index*10:(index+1)*10]
        if (attempt.get('request'), attempt.get('ids'), attempt.get('status'),
                attempt.get('requested_model'), attempt.get('effort'), attempt.get('auth_method')) != (
                planned['request'], members, 'ok', study.MODEL, study.EFFORT, 'claude.ai'):
            raise ValueError('Historical Claude attempt differs from frozen plan')
        prediction = attempt.get('prediction')
        if not isinstance(prediction, dict) or not isinstance(prediction.get('records'), list):
            raise ValueError('Historical Claude prediction missing')
        by_id = {r.get('id'): r for r in prediction['records'] if isinstance(r, dict)}
        if len(by_id) != 10 or set(by_id) != set(members):
            raise ValueError('Historical Claude batch prediction membership changed')
        for pos, rid in enumerate(members):
            record = records[index*10+pos]
            predicted = {k:v for k,v in by_id[rid].items() if k != 'id'}
            if (record.get('id'), record.get('prediction'), record.get('status'),
                    record.get('batch_record_ids'), record.get('requested_model'), record.get('effort')) != (
                    rid, predicted, 'ok', members, study.MODEL, study.EFFORT) or not valid(predicted):
                raise ValueError('Historical Claude record differs from batch')
            indexed[rid] = record
    return {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
            'usage': _usage(attempts), 'evidence': {'records': record_binding, 'attempts': attempt_binding}}, indexed


def _terminal(root, journal):
    path = _file(root, journal)
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        if not raw.endswith(b'\n'):
            return None
        events = [json.loads(line) for line in raw.splitlines()]
    except (ValueError, OSError):
        return None
    if not events or events[-1].get('event') not in ('phase_completed', 'phase_stopped'):
        return None
    return events


def _phase(root, base, repeat, condition, phase, plan, plan_hash, ids, labels, bind):
    folder = base / repeat / condition
    journal_path = folder / f'{phase}.journal.jsonl'
    events = _terminal(root, journal_path)
    if events is None:
        return None, 'open_or_not_started', None
    expected_requests = [plan['conditions'][condition]['smoke']] if phase == 'smoke' else plan['conditions'][condition]['development']
    claim_path = folder / f'{phase}.claim.json'
    attempts_path = folder / f'{phase}.attempts.jsonl'
    records_path = folder / f'{phase}.records.jsonl'
    claim = json.loads(_file(root, claim_path).read_text())
    if (claim.get('repeat'), claim.get('condition'), claim.get('phase'), claim.get('manifest_sha256'),
            claim.get('preflight_admitted'), claim.get('usage_credits_off'), claim.get('cli_version')) != (
            repeat, condition, phase, plan_hash, True, True, study.RUNTIME):
        raise ValueError('Claude claim differs from frozen admission')
    claim_binding = bind(claim_path)
    journal_binding = bind(journal_path)
    attempt_binding = bind(attempts_path)
    record_binding = bind(records_path)
    attempts = _rows(root, attempts_path)
    records = _rows(root, records_path)
    if not events or events[0] != {'event':'phase_started','repeat':repeat,'condition':condition,'phase':phase}:
        raise ValueError('Claude phase start differs')
    if len(attempts) > len(expected_requests) or len(events) != 2*len(attempts)+2:
        raise ValueError('Claude journal/attempt count differs')
    if [event.get('event') for event in events] != ['phase_started', *['dispatch_intent','request_completed']*len(attempts), events[-1]['event']]:
        raise ValueError('Claude journal sequence differs')
    indexed = {}
    raw_bindings = []
    for index, attempt in enumerate(attempts):
        planned = expected_requests[index]
        members = planned['record_ids']
        started, finished = events[1+2*index:3+2*index]
        if (started.get('batch_index'), started.get('record_ids'), finished.get('batch_index'), finished.get('status')) != (
                planned['batch_index'], members, planned['batch_index'], attempt.get('status')):
            raise ValueError('Claude dispatch journal differs from attempt')
        if (attempt.get('repeat'), attempt.get('condition'), attempt.get('phase'), attempt.get('batch_index'),
                attempt.get('ids'), attempt.get('request'), attempt.get('input_sha256'),
                attempt.get('requested_model'), attempt.get('effort'), attempt.get('auth_method'),
                attempt.get('cli_version'), attempt.get('controller_retries')) != (
                repeat, condition, phase, planned['batch_index'], members, planned['request'],
                digest(planned['input_text']), study.MODEL, study.EFFORT, 'claude.ai', study.RUNTIME, 0):
            raise ValueError('Claude attempt differs from frozen request')
        raw_path = folder / attempt['raw_capture_file']
        if raw_path.name != f"{phase}.batch-{planned['batch_index']:03d}.raw.jsonl":
            raise ValueError('Claude raw capture path changed')
        raw_binding = bind(raw_path, attempt['raw_capture_sha256'])
        raw_bindings.append(raw_binding)
        raw = _rows(root, raw_path)
        if len(raw) != 1:
            raise ValueError('Claude raw capture count differs')
        raw = raw[0]
        if (raw.get('repeat'), raw.get('condition'), raw.get('phase'), raw.get('batch_index'),
                raw.get('record_ids'), raw.get('input_sha256'), raw.get('exit_code'), raw.get('timed_out')) != (
                repeat, condition, phase, planned['batch_index'], members, attempt['input_sha256'],
                attempt.get('exit_code'), attempt.get('error_type')=='TimeoutExpired'):
            raise ValueError('Claude raw capture differs from attempt')
        if raw['timed_out'] and attempt.get('status')!='service_error':
            raise ValueError('Claude timeout has successful status')
        try:
            parsed_body = json.loads(raw['stdout'])
            parsed = parse_batch_result(parsed_body, raw['exit_code'], members)
        except ValueError:
            parsed_body = parsed = None
        if parsed is None:
            if attempt['status']!='service_error' or any(attempt.get(key) is not None for key in (
                    'prediction','usage','model_usage','cli_estimated_api_equivalent_usd')):
                raise ValueError('Claude attempt claims parsed fields absent from CLI capture')
        else:
            if attempt['status'] in ('ok','invalid_output') and parsed['status'] != attempt['status']:
                raise ValueError('Claude status differs from saved CLI capture')
            for key in ('prediction','raw_response','usage','model_usage','returned_models',
                        'init_model','init_tools','init_mcp_servers','init_skills','init_plugins',
                        'assistant_models','overage_observed','rate_limit_events',
                        'cli_duration_ms','cli_api_duration_ms','cli_estimated_api_equivalent_usd'):
                if parsed.get(key) != attempt.get(key):
                    raise ValueError(f'Claude {key} differs from saved CLI capture')
            if attempt.get('raw_events')!=safe_diagnostic(parsed_body):
                raise ValueError('Claude parsed events differ from saved CLI capture')
            if attempt['status']=='ok' and not isolation_ok({**attempt, 'raw_events': safe_diagnostic(parsed_body)}):
                raise ValueError('Claude saved CLI capture fails isolation')
        if attempt['status'] not in ('ok','invalid_output','service_error'):
            raise ValueError('Unknown Claude attempt status')
        positions = records[index*len(members):(index+1)*len(members)] if phase == 'smoke' else records[index*10:(index+1)*10]
        if len(positions) != len(members):
            raise ValueError('Claude record count differs from batch')
        predictions = {row['id']:{k:v for k,v in row.items() if k!='id'} for row in attempt.get('prediction',{}).get('records',[])} if attempt['status']=='ok' else {}
        if attempt['status']=='ok' and (len(predictions)!=len(members) or set(predictions)!=set(members)):
            raise ValueError('Claude successful prediction membership differs')
        for pos, record in enumerate(positions):
            rid=members[pos]
            if (record.get('id'),record.get('status'),record.get('prediction'),record.get('repeat'),
                    record.get('condition'),record.get('phase'),record.get('batch_index'),
                    record.get('batch_position'),record.get('batch_record_ids')) != (
                    rid,attempt['status'],predictions.get(rid),repeat,condition,phase,
                    planned['batch_index'],pos+1,members):
                raise ValueError('Claude record differs from saved attempt')
            indexed[rid]=record
    if len(records) != sum(len(expected_requests[index]['record_ids']) for index in range(len(attempts))):
        raise ValueError('Claude record evidence has extra rows')
    completed = events[-1]['event']=='phase_completed'
    if completed:
        if len(attempts)!=len(expected_requests) or any(a['status']!='ok' for a in attempts) or (
                events[-1].get('request_count'),events[-1].get('record_count')) != (len(expected_requests),3 if phase=='smoke' else 60):
            raise ValueError('Claude completed phase is incomplete')
    elif (not attempts or attempts[-1]['status']=='ok' or
          events[-1].get('batch_index') != expected_requests[len(attempts)-1]['batch_index']):
        raise ValueError('Claude stopped phase lacks a failed attempt')
    if phase == 'development':
        for rid in ids:
            indexed.setdefault(rid,{'id':rid,'status':'never_sent','prediction':None})
        score = shared.score(indexed, labels, ids)
    else:
        score = None
    evidence = {'claim':claim_binding,'journal':journal_binding,'attempts':attempt_binding,
                'records':record_binding,'rawCaptures':raw_bindings}
    return {'completionStatus':'complete' if completed else 'partial',
            'terminalEvent':events[-1]['event'], 'finishedRequests':len(attempts),
            'score':score,'usage':_usage(attempts),'evidence':evidence}, None, indexed


def _stats(values):
    return {'completedPasses':len(values),'values':values,
            'mean':sum(values)/len(values) if len(values)==3 else None,
            'range':[min(values),max(values)] if len(values)==3 else None}


def build(root=ROOT):
    root=Path(root)
    ids,labels,pair,plans,bind,sources=_source_context(root)
    data={name:{} for name in PASSES}
    indexed={name:{} for name in PASSES}
    missing=[];partial=[]
    for condition in CONDITIONS:
        entry, records=_historical(root,condition,pair,plans['repeat2'][0],ids,labels,bind)
        data['original'][condition]=entry
        indexed['original'][condition]=records
    for repeat in ('repeat2','repeat3'):
        plan,plan_binding=plans[repeat]
        for condition in CONDITIONS:
            smoke,_,_=_phase(root,BASE,repeat,condition,'smoke',plan,plan_binding['sha256'],ids,labels,bind)
            if smoke is None or smoke['completionStatus']!='complete':
                missing.append({'pass':repeat,'condition':condition,'status':'smoke_open_or_incomplete'})
                continue
            inspection_path=BASE/repeat/condition/'smoke-inspection.json'
            if not _file(root,inspection_path).exists():
                missing.append({'pass':repeat,'condition':condition,'status':'smoke_uninspected'})
                continue
            inspection=json.loads(_file(root,inspection_path).read_text())
            if (inspection.get('inspection'),inspection.get('attempts_sha256'),inspection.get('records_sha256'),inspection.get('journal_sha256')) != (
                    'accepted_unchanged',smoke['evidence']['attempts']['sha256'],
                    smoke['evidence']['records']['sha256'],smoke['evidence']['journal']['sha256']):
                raise ValueError('Claude smoke inspection differs from evidence')
            bind(inspection_path)
            entry,reason,records=_phase(root,BASE,repeat,condition,'development',plan,plan_binding['sha256'],ids,labels,bind)
            if entry is None:
                missing.append({'pass':repeat,'condition':condition,'status':reason})
                continue
            data[repeat][condition]=entry
            if entry['completionStatus']=='partial':
                partial.append({'pass':repeat,'condition':condition,'terminalEvent':entry['terminalEvent'],
                                'finishedRequests':entry['finishedRequests']})
            else:
                indexed[repeat][condition]=records
    def full(pass_name,condition):
        return condition in data[pass_name] and data[pass_name][condition]['completionStatus']=='complete'
    deltas=[]
    for name in PASSES:
        for target in ('P1','P2'):
            if full(name,'P0') and full(name,target):
                a,b=data[name]['P0']['score'],data[name][target]['score']
                deltas.append({'pass':name,'from':'P0','to':target,'denominator':60,
                               'allFour':b['allFour']-a['allFour'],
                               'fields':{field:b['fields'][field]-a['fields'][field] for field in FIELDS}})
    spread={}
    for target in ('P1','P2'):
        entries=[x for x in deltas if x['to']==target]
        spread[target]={'completedPairs':len(entries),'allFourValues':[x['allFour'] for x in entries],
                        'allFourRange':[min(x['allFour'] for x in entries),max(x['allFour'] for x in entries)] if len(entries)==3 else None,
                        'fieldRanges':{field:[min(x['fields'][field] for x in entries),max(x['fields'][field] for x in entries)] if len(entries)==3 else None for field in FIELDS}}
    flips=[];ranges={};across={}
    for condition in CONDITIONS:
        for i,left in enumerate(PASSES):
            for right in PASSES[i+1:]:
                if full(left,condition) and full(right,condition):
                    flips.append({'condition':condition,'from':left,'to':right,
                                  **shared.flip(indexed[left][condition],indexed[right][condition],ids)})
        scores=[data[name][condition]['score'] for name in PASSES if full(name,condition)]
        ranges[condition]={'allFour':_stats([x['allFour'] for x in scores]),
                           'fields':{field:_stats([x['fields'][field] for x in scores]) for field in FIELDS}}
        if all(full(name,condition) for name in PASSES):
            eligible=[rid for rid in ids if all(shared.outcome(indexed[name][condition][rid])=='valid' for name in PASSES)]
            across[condition]={'denominator':len(eligible),'excludedIds':[rid for rid in ids if rid not in eligible],
                               'fields':{field:[rid for rid in eligible if len({indexed[name][condition][rid]['prediction'][field] for name in PASSES})>1] for field in FIELDS},
                               'fourFieldVector':[rid for rid in eligible if len({tuple(indexed[name][condition][rid]['prediction'][field] for field in FIELDS) for name in PASSES})>1]}
    return {'schema':'claude-repeat-findings-v1','configuration':study.CONFIG,
            'displayName':'Claude Opus 5.5 · medium effort · batch 10','model':study.MODEL,'effort':study.EFFORT,
            'provider':'Claude subscription','referenceVersion':'0.2',
            'referenceStatus':'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts':{field:dict(sorted(Counter(labels[rid][field] for rid in ids).items())) for field in FIELDS},
            'denominator':60,'completedConditions':sum(full(name,condition) for name in PASSES for condition in CONDITIONS),
            'plannedConditions':9,'missingPasses':missing,'partialPasses':partial,'passes':data,
            'threePassSummary':ranges,'pairwiseFlips':flips,'changesAcrossThreePasses':across,
            'withinPassPromptDeltas':deltas,'pairedDeltaSpread':spread,'sourceBindings':sources,
            'limitations':['This report covers one Claude configuration, not the full Claude roster.',
                           'The same 60 synthetic development records appear in every pass.',
                           'Partial terminal phases retain missing outcomes in the 60-record denominator; open phases are excluded.',
                           'Historical and repeat CLI patch versions differ. Serving revision and effective seed are unavailable.',
                           'Request duration is client wall-clock time, not model-only inference time.',
                           'CLI list-price estimates are not subscription charges. Actual billed cost and quota consumed are unknown.']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    content=json.dumps(build(ROOT),indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not args.output.exists() or args.output.read_text()!=content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(content)
    print('Claude Opus 5.5 medium report checked')


if __name__=='__main__':main()
