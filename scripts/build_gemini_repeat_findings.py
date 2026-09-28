#!/usr/bin/env python3
"""Build offline repeat findings for frozen Gemini configurations."""
import argparse
import base64
import binascii
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
import gemini_repeat_study as study
import gemini_repeat_roster as roster
from gemini_repeat_high import runner as high_roster
import gemini38_low_repeat as recovered_low
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1')
LABELS = Path('data/pilot/proposed_labels.jsonl')
PASSES = ('original', 'repeat2', 'repeat3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS


def _controller(config):
    if config in study.CONFIGS:
        return study
    if config in roster.CONFIGS:
        return roster
    if config in high_roster.CONFIGS:
        return high_roster
    if config in recovered_low.CONFIGS:
        return recovered_low
    raise ValueError('Configuration outside frozen Gemini controllers')


def _path(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(root, relative):
    raw = _path(root, relative).read_bytes()
    if raw and (not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines())):
        raise ValueError(f'Incomplete evidence: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


def _binder(root):
    sources=[]
    def bind(relative, expected=None):
        relative=Path(relative)
        actual=_sha(_path(root,relative))
        if expected is not None and actual!=expected:
            raise ValueError(f'Source hash changed: {relative}')
        item={'path':str(relative),'sha256':actual}
        if item not in sources:sources.append(item)
        return item
    return bind,sources


def _money(value):
    if value is None or isinstance(value,bool):return None
    try:amount=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):return None
    return amount if amount.is_finite() and amount>=0 else None


def _number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0


def _usage(attempts,pending=0):
    token_keys={'input_tokens':('prompt_tokens',),'output_tokens':('completion_tokens',),
                'cached_input_tokens':('prompt_tokens_details','cached_tokens'),
                'cache_write_input_tokens':('prompt_tokens_details','cache_write_tokens'),
                'reasoning_output_tokens':('completion_tokens_details','reasoning_tokens')}
    tokens={}
    for name,keys in token_keys.items():
        values=[]
        for attempt in attempts:
            value=attempt.get('raw_response')
            value=value.get('usage') if isinstance(value,dict) else None
            for key in keys:value=value.get(key) if isinstance(value,dict) else None
            values.append(value)
        tokens[name]=sum(values) if values and all(type(x) is int and x>=0 for x in values) else None
    known=[_money(a.get('observed_cost_usd')) for a in attempts if a.get('cost_unknown') is False]
    if any(x is None for x in known):raise ValueError('Gemini known cost is invalid')
    unknown=len(attempts)-len(known)+pending
    durations=[a.get('elapsed_seconds') for a in attempts]
    seconds=sum(durations) if durations and all(_number(x) for x in durations) else None
    return {'requestCount':len(attempts),'startedRequestCount':len(attempts)+pending,
            'requestSeconds':durations,'requestSecondsTotal':seconds,
            'requestTimeKind':'client_wall_clock_if_recorded','inferenceSeconds':None,
            'tokens':tokens,'knownCostUsd':str(sum(known,Decimal(0))),
            'actualCostUsd':str(sum(known,Decimal(0))) if unknown==0 else None,
            'unknownCostCount':unknown,
            'costNote':'USD amounts come from saved provider usage; unknown charges are not zero.'}


def _source_context(root,config):
    bind,sources=_binder(root)
    bind(LABELS,shared.PINNED_SHA[str(LABELS)])
    label_rows=_rows(root,LABELS)
    ids=[r['id'] for r in label_rows]
    if ids!=[f'DEV-{i:03d}' for i in range(1,61)] or any(r.get('review_version')!='0.2' for r in label_rows):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels={r['id']:r['proposed_labels'] for r in label_rows}
    plans={}
    for repeat in ('repeat2','repeat3'):
        relative=BASE/config/repeat/'manifest.json'
        item=bind(relative)
        plan=json.loads(_path(root,relative).read_text())
        if plan!=_controller(config).expected_plan(config,repeat):
            raise ValueError(f'Frozen Gemini plan changed: {config} {repeat}')
        for source in plan['source_bindings'].values():bind(source['path'],source['sha256'])
        for condition in CONDITIONS:
            for source in plan['conditions'][condition]['historical'].values():
                bind(source['path'],source['sha256'])
        plans[repeat]=(plan,item)
    return ids,labels,plans,bind,sources


def _check_attempt(attempt,request,plan,condition,phase):
    ids=request['record_ids']
    if (attempt.get('phase'),attempt.get('ids'),attempt.get('batch_index'),
            attempt.get('request'),attempt.get('request_sha256'),attempt.get('model'),
            attempt.get('effort'),attempt.get('provider'),attempt.get('reference_labels_read')) != (
            phase,ids,0 if phase=='smoke' else request['_index'],request['payload'],
            request['payload_sha256'],plan['model'],plan['effort'],plan['provider'],False):
        raise ValueError('Gemini attempt differs from frozen request')
    if not isinstance(attempt.get('attempt_id'),str) or not attempt['attempt_id']:
        raise ValueError('Gemini attempt ID missing')
    if attempt.get('status') not in ('ok','invalid_output','control_violation','identity_violation','service_error'):
        raise ValueError('Unknown Gemini attempt status')
    if attempt.get('reserved_cost_usd')!=request['reserve_usd']:
        raise ValueError('Gemini reserve differs from frozen plan')
    if type(attempt.get('billing_ok')) is not bool or type(attempt.get('cost_unknown')) is not bool:
        raise ValueError('Gemini billing state missing')
    raw=attempt.get('raw_response')
    raw_usage=raw.get('usage') if isinstance(raw,dict) else None
    observed=_money(attempt.get('observed_cost_usd'))
    raw_cost=_money(raw_usage.get('cost')) if isinstance(raw_usage,dict) else None
    if attempt['cost_unknown']:
        if attempt.get('observed_cost_usd') is not None or attempt['billing_ok']:
            raise ValueError('Gemini unknown charge was settled')
    elif observed is None or raw_cost!=observed:
        raise ValueError('Gemini observed charge differs from raw usage')
    if 'usage' in attempt and attempt['usage']!=raw_usage:
        raise ValueError('Gemini usage differs from raw response')
    if attempt['status'] in ('ok','invalid_output') and not isinstance(raw,dict):
        raise ValueError('Gemini healthy attempt lacks raw response')
    if attempt['status']=='ok':
        predicted=attempt.get('predictions')
        if not isinstance(predicted,dict) or set(predicted)!=set(ids) or any(not valid(x) for x in predicted.values()):
            raise ValueError('Gemini successful batch prediction differs')
    if attempt.get('elapsed_seconds') is not None and not _number(attempt['elapsed_seconds']):
        raise ValueError('Gemini request duration invalid')


def _saved_prediction(attempt,rid):
    # The runner preserves parsed labels even when a non-stop finish makes the batch invalid.
    return attempt.get('predictions',{}).get(rid)


def _historical(root,plan,condition,ids,labels,bind):
    if config_is_recovered_low(plan) and condition=='P0':
        return _recovered_p0(root,plan,ids,labels,bind)
    history=plan['conditions'][condition]['historical']
    attempts=_rows(root,history['development_attempts']['path'])
    records=_rows(root,history['development_records']['path'])
    if len(attempts)!=6 or len(records)!=60 or [r.get('id') for r in records]!=ids:
        raise ValueError('Historical Gemini membership differs')
    indexed={}
    for index,attempt in enumerate(attempts):
        request={**plan['conditions'][condition]['requests'][index+1], '_index':index+1}
        _check_attempt(attempt,request,plan,condition,'development')
        if attempt.get('status') not in ('ok','invalid_output') or not attempt['billing_ok'] or attempt['cost_unknown']:
            raise ValueError('Historical Gemini phase is not complete')
        members=request['record_ids']
        for position,rid in enumerate(members):
            record=records[index*10+position]
            expected=_saved_prediction(attempt,rid)
            if (record.get('id'),record.get('phase'),record.get('batch_index'),
                    record.get('batch_position'),record.get('status'),record.get('prediction'),
                    record.get('model'),record.get('effort'),record.get('request_sha256')) != (
                    rid,'development',index+1,position,attempt['status'],expected,
                    plan['model'],plan['effort'],attempt['request_sha256']):
                raise ValueError('Historical Gemini record differs from batch')
            indexed[rid]=record
    return {'completionStatus':'complete','score':shared.score(indexed,labels,ids),
            'usage':_usage(attempts),'evidence':{key:history[key] for key in (
                'development_records','development_attempts','development_journal','manifest')}},indexed


def config_is_recovered_low(plan):
    return plan.get('configuration_id') in recovered_low.CONFIGS


def _recovered_p0(root,plan,ids,labels,bind):
    history=plan['conditions']['P0']['historical']
    admission=history['recovered_admission']
    proof=recovered_low.recovered.validate_admission(_path(root,admission['path']))
    if (_sha(_path(root,admission['path']))!=admission['sha256']
            or proof['reconciled_attempts']!=history['development_attempts']
            or proof['reconciled_records']!=history['development_records']
            or proof['reconciled_journal']!=history['development_journal']
            or proof['baseline_id']!=plan['original_p0_baseline_id']):
        raise ValueError('Recovered Gemini P0 admission differs from frozen history')
    attempts=_rows(root,history['development_attempts']['path'])
    records=_rows(root,history['development_records']['path'])
    journal=_rows(root,history['development_journal']['path'])
    if len(attempts)!=6 or len(records)!=60 or [row.get('id') for row in records]!=ids:
        raise ValueError('Recovered Gemini P0 membership differs')
    if (len(journal)!=19 or journal[-1]!={'event':'terminal','phase':'development',
            'expected_batches':6,'started_batches':6,'finished_batches':6,
            'completed':True,'reason':'completed'}):
        raise ValueError('Recovered Gemini P0 terminal differs')
    catalog=json.loads(_path(root,plan['conditions']['P0']['catalog']['path']).read_text())
    endpoints=json.loads(_path(root,plan['conditions']['P0']['endpoints']['path']).read_text())
    _,endpoint=study.v3.check_catalog(plan['model'],plan['effort'],catalog,endpoints)
    indexed={}
    for index,attempt in enumerate(attempts):
        request={**plan['conditions']['P0']['requests'][index+1],'_index':index+1}
        _check_attempt(attempt,request,plan,'P0','development')
        raw=attempt.get('raw_response')
        if (attempt.get('status') not in ('ok','invalid_output') or attempt['billing_ok'] is not True
                or attempt['cost_unknown'] is not False or not isinstance(raw,dict)
                or attempt.get('generation_id')!=raw.get('id')
                or attempt.get('returned_model')!=raw.get('model')
                or attempt.get('returned_provider')!=raw.get('provider')
                or attempt.get('requested_endpoint')!=endpoint):
            raise ValueError('Recovered Gemini P0 provider or billing identity differs')
        parsed=study.classify(plan,request,raw,endpoint)
        if (parsed.get('status'),parsed.get('predictions'))!=(attempt['status'],attempt.get('predictions')):
            raise ValueError('Recovered Gemini P0 prediction differs from raw response')
        members=request['record_ids']
        for position,rid in enumerate(members):
            record=records[index*10+position]
            expected={'id':rid,'status':attempt['status'],
                'prediction':_saved_prediction(attempt,rid),'batch_index':index+1,
                'original_status':attempt.get('admission_original_status',attempt['status']),
                'generation_id':attempt['generation_id'],'batch_position':position}
            if record!=expected:raise ValueError('Recovered Gemini P0 record differs from admitted raw batch')
            indexed[rid]=record
    return {'completionStatus':'complete','score':shared.score(indexed,labels,ids),
            'usage':_usage(attempts),'evidence':{key:history[key] for key in (
                'development_records','development_attempts','development_journal','manifest','recovered_admission')}},indexed


def _terminal(root,relative):
    path=_path(root,relative)
    if not path.exists():return None
    try:
        raw=path.read_bytes()
        if not raw.endswith(b'\n'):return None
        events=[json.loads(row) for row in raw.splitlines()]
    except (ValueError,OSError):return None
    if not events or events[-1].get('event') not in ('phase_completed','phase_stopped','phase_aborted'):
        return None
    return events


def _review(root,folder,phase,plan,plan_hash,condition,claim,bind):
    candidates=list(_path(root,folder).glob('*.json'))
    matching=[p for p in candidates if _sha(p)==claim.get('review_sha256')]
    if len(matching)!=1:raise ValueError('Gemini exact root review receipt missing')
    relative=matching[0].relative_to(root.resolve())
    binding=bind(relative,claim['review_sha256'])
    review=json.loads(matching[0].read_text())
    if (review.get('schema'),review.get('approved'),review.get('configuration_id'),
            review.get('repeat'),review.get('condition'),review.get('phase'),
            review.get('plan_sha256'),review.get('controller_sha256'),
            review.get('partition_id'),review.get('partition_cap_usd')) != (
            _controller(plan['configuration_id']).REVIEW_SCHEMA,True,plan['configuration_id'],plan['repeat'],condition,phase,
            plan_hash,plan['source_bindings']['controller']['sha256'],plan['partition_id'],plan['proposed_partition_cap_usd']):
        raise ValueError('Gemini root review controls differ')
    for repeat in ('repeat2','repeat3'):
        target=BASE/plan['configuration_id']/repeat/'manifest.json'
        if review.get('plan_sha256_by_repeat',{}).get(repeat)!=_sha(_path(root,target)):
            raise ValueError('Gemini root review plan set differs')
    budget=review.get('budget_manifest')
    if not isinstance(budget,dict) or set(budget)!={'path','sha256'}:
        raise ValueError('Gemini root review lacks budget binding')
    bind(budget['path'],budget['sha256'])
    if phase=='development':
        inspection=folder/'smoke-inspection.json'
        if review.get('smoke_inspection_sha256')!=_sha(_path(root,inspection)):
            raise ValueError('Gemini development review lacks inspected smoke binding')
    elif review.get('smoke_inspection_sha256') is not None:
        raise ValueError('Gemini smoke review carries development approval')
    return binding


def _raw(raw,attempt,request):
    ids=request['record_ids']
    raw_ids=raw.get('id') if raw.get('body_base64') else raw.get('record_ids')
    expected_ids=','.join(ids) if raw.get('body_base64') else ids
    if (raw_ids,raw.get('attempt_id'),raw.get('request_sha256')) != (
            expected_ids,attempt['attempt_id'],request['payload_sha256']):
        raise ValueError('Gemini raw response identity differs')
    if raw.get('body_base64'):
        try:body=base64.b64decode(raw['body_base64'],validate=True)
        except (binascii.Error,ValueError):raise ValueError('Gemini raw response encoding invalid') from None
        if (raw.get('http_status')!=200 or raw.get('body_truncated_at_limit') or raw.get('read_error') or
                raw.get('body_bytes_captured')!=len(body)):
            raise ValueError('Gemini raw response incomplete')
        try:decoded=json.loads(body)
        except ValueError:decoded=None
        if decoded!=attempt.get('raw_response'):
            if decoded is not None or attempt.get('raw_response') is not None:
                raise ValueError('Gemini raw response differs from parsed attempt')
        return decoded
    if (raw.get('http_status'),raw.get('error_body'),raw.get('error_headers'),
            raw.get('read_error'),raw.get('body_truncated_at_limit')) != (
            attempt.get('http_status'),attempt.get('error_body'),attempt.get('error_headers'),
            attempt.get('read_error'),attempt.get('body_truncated_at_limit')):
        raise ValueError('Gemini raw HTTP error differs from attempt')
    if attempt.get('status') not in ('service_error','control_violation','identity_violation'):
        raise ValueError('Gemini healthy attempt lacks response bytes')
    return None


def _phase(root,plan,plan_hash,condition,phase,ids,labels,bind):
    folder=BASE/plan['configuration_id']/plan['repeat']/condition
    journal_path=folder/f'{phase}.journal.jsonl'
    events=_terminal(root,journal_path)
    if events is None:return None,'open_or_not_started',None
    paths={name:folder/f'{phase}.{name}.jsonl' for name in ('attempts','responses','records')}
    paths.update(claim=folder/f'{phase}.claim.json',journal=journal_path)
    bindings={name:bind(path) for name,path in paths.items()}
    claims=_rows(root,paths['claim'])
    if len(claims)!=1:raise ValueError('Gemini phase claim count differs')
    claim=claims[0]
    if (claim.get('schema'),claim.get('plan_sha256'),claim.get('condition'),claim.get('phase')) != (
            _controller(plan['configuration_id']).SCHEMA+'-claim',plan_hash,condition,phase):
        raise ValueError('Gemini phase claim differs')
    bindings['rootReview']=_review(root,folder,phase,plan,plan_hash,condition,claim,bind)
    attempts=_rows(root,paths['attempts'])
    responses=_rows(root,paths['responses'])
    records=_rows(root,paths['records'])
    requests=plan['conditions'][condition]['requests'][:1] if phase=='smoke' else plan['conditions'][condition]['requests'][1:]
    if (not events or events[0].get('event')!='phase_started' or events[0].get('phase')!=phase or
            events[0].get('condition')!=condition or events[0].get('expected_batches')!=len(requests)):
        raise ValueError('Gemini journal start differs')
    cursor=1
    for index,attempt in enumerate(attempts):
        request={**requests[index], '_index':index+1}
        if cursor+2>=len(events):raise ValueError('Gemini journal lacks finished request')
        intent,started,finished=events[cursor:cursor+3]
        if (intent.get('event'),started.get('event'),finished.get('event'),
                intent.get('record_ids'),started.get('record_ids'),
                intent.get('request_sha256'),started.get('request_sha256'),
                started.get('attempt_id'),finished.get('attempt_id'),
                finished.get('status'),finished.get('billing_ok'),finished.get('cost_unknown')) != (
                'request_intent','request_started','request_finished',request['record_ids'],
                request['record_ids'],request['payload_sha256'],request['payload_sha256'],
                attempt.get('attempt_id'),attempt.get('attempt_id'),attempt.get('status'),
                attempt.get('billing_ok'),attempt.get('cost_unknown')):
            raise ValueError('Gemini journal differs from finished attempt')
        cursor+=3
        _check_attempt(attempt,request,plan,condition,phase)
        if (attempt.get('repeat'),attempt.get('condition'),attempt.get('plan_sha256')) != (
                plan['repeat'],condition,plan_hash):
            raise ValueError('Gemini repeat attempt identity differs')
    if len(attempts)>len(requests):raise ValueError('Gemini attempt count exceeds plan')
    pending=None
    trailing=events[cursor:-1]
    if trailing:
        if events[-1].get('event')!='phase_aborted' or len(attempts)>=len(requests):
            raise ValueError('Gemini terminal journal has extra dispatch')
        request=requests[len(attempts)]
        if len(trailing)==1 and trailing[0].get('event')=='request_intent':
            if trailing[0].get('record_ids')!=request['record_ids'] or trailing[0].get('request_sha256')!=request['payload_sha256']:
                raise ValueError('Gemini unresolved intent differs')
        elif len(trailing)==2 and [x.get('event') for x in trailing]==['request_intent','request_started']:
            if (trailing[0].get('record_ids'),trailing[0].get('request_sha256'),
                    trailing[1].get('record_ids'),trailing[1].get('request_sha256')) != (
                    request['record_ids'],request['payload_sha256'],request['record_ids'],request['payload_sha256']):
                raise ValueError('Gemini unresolved started request differs')
            pending={'attempt_id':trailing[1].get('attempt_id'),'record_ids':request['record_ids']}
            if not pending['attempt_id']:raise ValueError('Gemini pending attempt ID missing')
        else:raise ValueError('Gemini aborted journal tail differs')
    elif events[-1].get('event')=='phase_aborted' and len(events)!=cursor+1:
        raise ValueError('Gemini aborted journal differs')
    by_attempt={}
    for response in responses:
        attempt_id=response.get('attempt_id')
        if not isinstance(attempt_id,str) or attempt_id in by_attempt:
            raise ValueError('Gemini raw response attempt ID reused')
        by_attempt[attempt_id]=response
    expected_response_ids={a['attempt_id'] for a in attempts if a['attempt_id'] in by_attempt}
    for attempt in attempts:
        if attempt['attempt_id'] not in by_attempt and (attempt.get('status')!='service_error' or
                attempt.get('raw_response') is not None or attempt.get('cost_unknown') is not True):
            raise ValueError('Gemini finished attempt lacks required raw response')
    if pending is not None and pending['attempt_id'] in by_attempt:expected_response_ids.add(pending['attempt_id'])
    if set(by_attempt)!=expected_response_ids:
        raise ValueError('Gemini raw response count or identity differs')
    if pending is not None and pending['attempt_id'] in by_attempt:
        response=by_attempt[pending['attempt_id']]
        planned=requests[len(attempts)]
        if (response.get('attempt_id'),response.get('request_sha256'),
                response.get('id',response.get('record_ids'))) != (
                pending['attempt_id'],planned['payload_sha256'],
                ','.join(pending['record_ids']) if response.get('body_base64') else pending['record_ids']):
            raise ValueError('Gemini pending raw response differs from frozen request')
    indexed={};offset=0
    endpoint_catalog=json.loads(_path(root,plan['conditions'][condition]['catalog']['path']).read_text())
    endpoint_rows=json.loads(_path(root,plan['conditions'][condition]['endpoints']['path']).read_text())
    _,endpoint=study.v3.check_catalog(plan['model'],plan['effort'],endpoint_catalog,endpoint_rows)
    for index,attempt in enumerate(attempts):
        request={**requests[index], '_index':index+1}
        response=by_attempt.get(attempt['attempt_id'])
        decoded=_raw(response,attempt,request) if response is not None else None
        if attempt['status'] in ('ok','invalid_output'):
            if not isinstance(decoded,dict):raise ValueError('Gemini model output has no parsed raw body')
            parsed=study.classify(plan,request,decoded,endpoint)
            if (parsed.get('status'),parsed.get('predictions')) != (
                    attempt['status'],attempt.get('predictions')):
                raise ValueError('Gemini prediction differs from raw response')
        members=request['record_ids']
        group=records[offset:offset+len(members)]
        if len(group)!=len(members):raise ValueError('Gemini record count differs')
        for position,rid in enumerate(members):
            row=group[position]
            prediction=_saved_prediction(attempt,rid)
            if (row.get('id'),row.get('status'),row.get('prediction'),row.get('phase'),
                    row.get('batch_index'),row.get('batch_position'),row.get('attempt_id'),
                    row.get('request_sha256')) != (
                    rid,attempt['status'],prediction,phase,attempt['batch_index'],position,
                    attempt['attempt_id'],attempt['request_sha256']):
                raise ValueError('Gemini record differs from saved attempt')
            indexed[rid]=row
        offset+=len(members)
    if len(records)!=offset:raise ValueError('Gemini record evidence has extra rows')
    terminal=events[-1]
    complete=terminal['event']=='phase_completed'
    if complete:
        if (len(attempts)!=len(requests) or len(responses)!=len(requests) or
                terminal.get('phase')!=phase or terminal.get('batch_count')!=len(requests) or
                any(a['status'] not in ('ok','invalid_output') or a['billing_ok'] is not True or
                    a['cost_unknown'] is not False for a in attempts)):
            raise ValueError('Gemini completed phase lacks expected settled batches')
    elif terminal['event']=='phase_stopped':
        if (not attempts or attempts[-1]['status'] in ('ok','invalid_output') and attempts[-1]['billing_ok'] is True or
                terminal.get('attempt_id')!=attempts[-1]['attempt_id']):
            raise ValueError('Gemini stopped phase lacks failed batch')
    if pending is not None:
        for rid in pending['record_ids']:
            indexed[rid]={'id':rid,'status':'unknown_started','prediction':None}
    if phase=='development':
        for rid in ids:indexed.setdefault(rid,{'id':rid,'status':'never_sent','prediction':None})
        score=shared.score(indexed,labels,ids)
    else:score=None
    bindings['rawResponseCount']=len(responses)
    return {'completionStatus':'complete' if complete else 'partial',
            'terminalEvent':terminal['event'],'finishedRequests':len(attempts),
            'score':score,'usage':_usage(attempts,int(pending is not None)),
            'evidence':bindings},None,indexed


def _stats(values):
    return {'completedPasses':len(values),'values':values,
            'mean':sum(values)/len(values) if len(values)==3 else None,
            'range':[min(values),max(values)] if len(values)==3 else None}


def _recovered_budget(root,config,plans,bind):
    folder=BASE/config
    reconciliation_path=folder/'budget-reconciliation-v1.json'
    reconciliation=json.loads(_path(root,reconciliation_path).read_text())
    child_path=folder/'budget-partition-v1-g38-low-recovered-repeat-v1.jsonl'
    expected_child_suffix='/' + str(child_path)
    if (reconciliation.get('event')!='partition_reconciled'
            or reconciliation.get('partition_id')!=plans['repeat2'][0]['partition_id']
            or not isinstance(reconciliation.get('child_ledger'),str)
            or not reconciliation['child_ledger'].endswith(expected_child_suffix)):
        raise ValueError('Recovered Gemini budget reconciliation identity differs')
    bind(reconciliation_path)
    child_binding=bind(child_path,reconciliation.get('child_sha256'))
    events=_rows(root,child_path)
    cap=_money(plans['repeat2'][0]['proposed_partition_cap_usd'])
    if (len(events)!=86 or events[0]!={'event':'budget','cap_usd':str(cap)}
            or events[-1]!={'event':'partition_closed',
                    'reason':'Explicit terminal reconciliation; no further requests permitted'}):
        raise ValueError('Recovered Gemini budget ledger is not closed as planned')
    attempts=[]
    for repeat in ('repeat2','repeat3'):
        plan=plans[repeat][0]
        if (plan['partition_id']!=reconciliation['partition_id'] or
                _money(plan['proposed_partition_cap_usd'])!=cap):
            raise ValueError('Recovered Gemini repeat budgets differ')
        for condition in plan['condition_order']:
            for phase in ('smoke','development'):
                attempts.extend(_rows(root,folder/repeat/condition/f'{phase}.attempts.jsonl'))
    if len(attempts)!=42 or len({a.get('attempt_id') for a in attempts})!=42:
        raise ValueError('Recovered Gemini budget attempt count differs')
    actual=Decimal(0)
    for index,attempt in enumerate(attempts):
        reserve,settle=events[1+index*2:3+index*2]
        observed=_money(attempt.get('observed_cost_usd'))
        if (attempt.get('cost_unknown') is not False or observed is None
                or reserve!={'event':'reserve','attempt_id':attempt['attempt_id'],
                              'record_id':','.join(attempt['ids']),
                              'usd':attempt['reserved_cost_usd']}
                or settle!={'event':'settle','attempt_id':attempt['attempt_id'],
                             'usd':attempt['observed_cost_usd']}):
            raise ValueError('Recovered Gemini budget ledger differs from requests')
        actual+=observed
    if (_money(reconciliation.get('known_actual_usd'))!=actual
            or _money(reconciliation.get('unknown_upper_bound_usd'))!=0
            or _money(reconciliation.get('unused_allocation_released_usd'))!=cap-actual):
        raise ValueError('Recovered Gemini budget totals differ')
    return {'partitionId':reconciliation['partition_id'],'capUsd':str(cap),
            'knownActualUsd':str(actual),'unknownUpperBoundUsd':'0',
            'unusedAllocationReleasedUsd':str(cap-actual),'childLedger':child_binding}


def build_series(config,root=ROOT):
    root=Path(root)
    ids,labels,plans,bind,sources=_source_context(root,config)
    data={name:{} for name in PASSES};indexed={name:{} for name in PASSES}
    missing=[];partial=[]
    for condition in CONDITIONS:
        entry,records=_historical(root,plans['repeat2'][0],condition,ids,labels,bind)
        data['original'][condition]=entry;indexed['original'][condition]=records
    for repeat in ('repeat2','repeat3'):
        plan,plan_binding=plans[repeat]
        for condition in CONDITIONS:
            smoke,_,_=_phase(root,plan,plan_binding['sha256'],condition,'smoke',ids,labels,bind)
            if smoke is None or smoke['completionStatus']!='complete':
                missing.append({'pass':repeat,'condition':condition,'status':'smoke_open_or_incomplete'})
                continue
            folder=BASE/config/repeat/condition
            inspection_path=folder/'smoke-inspection.json'
            if not _path(root,inspection_path).exists():
                missing.append({'pass':repeat,'condition':condition,'status':'smoke_uninspected'})
                continue
            inspection=json.loads(_path(root,inspection_path).read_text())
            if (inspection.get('schema'),inspection.get('decision'),inspection.get('plan_sha256')) != (
                    'gemini-repeat-smoke-inspection-v1','accepted_unchanged',plan_binding['sha256']):
                raise ValueError('Gemini smoke inspection identity differs')
            for key in ('journal','attempts','responses','records'):
                if inspection.get(key+'_sha256')!=smoke['evidence'][key]['sha256']:
                    raise ValueError('Gemini smoke inspection source differs')
            bind(inspection_path)
            entry,reason,records=_phase(root,plan,plan_binding['sha256'],condition,'development',ids,labels,bind)
            if entry is None:
                missing.append({'pass':repeat,'condition':condition,'status':reason})
                continue
            data[repeat][condition]=entry
            if entry['completionStatus']=='partial':
                partial.append({'pass':repeat,'condition':condition,'terminalEvent':entry['terminalEvent'],
                                'finishedRequests':entry['finishedRequests']})
            else:indexed[repeat][condition]=records
    def full(name,condition):
        return condition in data[name] and data[name][condition]['completionStatus']=='complete'
    deltas=[]
    for name in PASSES:
        for target in ('P1','P2'):
            if full(name,'P0') and full(name,target):
                a,b=data[name]['P0']['score'],data[name][target]['score']
                deltas.append({'pass':name,'from':'P0','to':target,'denominator':60,
                               'allFour':b['allFour']-a['allFour'],
                               'fields':{f:b['fields'][f]-a['fields'][f] for f in FIELDS}})
    spread={}
    for target in ('P1','P2'):
        entries=[x for x in deltas if x['to']==target]
        spread[target]={'completedPairs':len(entries),'allFourValues':[x['allFour'] for x in entries],
                        'allFourRange':[min(x['allFour'] for x in entries),max(x['allFour'] for x in entries)] if len(entries)==3 else None,
                        'fieldRanges':{f:[min(x['fields'][f] for x in entries),max(x['fields'][f] for x in entries)] if len(entries)==3 else None for f in FIELDS}}
    flips=[];ranges={};across={}
    for condition in CONDITIONS:
        for index,left in enumerate(PASSES):
            for right in PASSES[index+1:]:
                if full(left,condition) and full(right,condition):
                    flips.append({'condition':condition,'from':left,'to':right,
                                  **shared.flip(indexed[left][condition],indexed[right][condition],ids)})
        scores=[data[name][condition]['score'] for name in PASSES if full(name,condition)]
        ranges[condition]={'allFour':_stats([x['allFour'] for x in scores]),
                           'fields':{f:_stats([x['fields'][f] for x in scores]) for f in FIELDS}}
        if all(full(name,condition) for name in PASSES):
            eligible=[rid for rid in ids if all(shared.outcome(indexed[name][condition][rid])=='valid' for name in PASSES)]
            across[condition]={'denominator':len(eligible),'excludedIds':[rid for rid in ids if rid not in eligible],
                               'fields':{f:[rid for rid in eligible if len({indexed[name][condition][rid]['prediction'][f] for name in PASSES})>1] for f in FIELDS},
                               'fourFieldVector':[rid for rid in eligible if len({tuple(indexed[name][condition][rid]['prediction'][f] for f in FIELDS) for name in PASSES})>1]}
    budget=None
    if config in recovered_low.CONFIGS:
        if not all(full(name,condition) for name in PASSES for condition in CONDITIONS):
            raise ValueError('Recovered Gemini repeat lane is not fully closed')
        budget=_recovered_budget(root,config,plans,bind)
    model=plans['repeat2'][0]['model']
    effort=plans['repeat2'][0]['effort']
    result={'schema':'gemini-repeat-findings-v1','configuration':config,
            'displayName':model+' · '+effort+' effort · OpenRouter batch 10',
            'model':model,'effort':effort,'provider':'google-ai-studio',
            'referenceVersion':'0.2','referenceStatus':'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts':{f:dict(sorted(Counter(labels[rid][f] for rid in ids).items())) for f in FIELDS},
            'denominator':60,'completedConditions':sum(full(name,c) for name in PASSES for c in CONDITIONS),
            'plannedConditions':9,'missingPasses':missing,'partialPasses':partial,'passes':data,
            'threePassSummary':ranges,'pairwiseFlips':flips,'changesAcrossThreePasses':across,
            'withinPassPromptDeltas':deltas,'pairedDeltaSpread':spread,'sourceBindings':sources,
            'limitations':['Each Gemini configuration is a separate series on the same 60 synthetic records.',
                           'Partial terminal phases retain failed and missing outcomes in the 60-record denominator; open phases are excluded.',
                           'Provisional v0.2 references are not independent adjudication.',
                           'Serving revision and effective seed are unavailable.',
                           'Request duration is unavailable where the runner did not record it; it is not inference time.',
                           'Unknown request charges and token fields are unavailable, not zero.']}
    if budget is not None:result['budgetReconciliation']=budget
    return result


def build(root=ROOT,include_recovered_low=False):
    configs=(*study.CONFIGS,*roster.CONFIGS,*high_roster.CONFIGS)
    if include_recovered_low:configs+=tuple(recovered_low.CONFIGS)
    return {'schema':'gemini-repeat-series-v1',
            'series':[build_series(config,root) for config in configs
                      if config in study.CONFIGS or all((Path(root)/BASE/config/r/'manifest.json').exists() for r in ('repeat2','repeat3'))]}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--include-recovered-low',action='store_true')
    args=parser.parse_args(argv)
    report=build(ROOT,include_recovered_low=True) if args.include_recovered_low else build(ROOT)
    value=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not args.output.exists() or args.output.read_text()!=value:
            raise ValueError(f'Stale report: {args.output}')
    else:args.output.write_text(value)
    print(', '.join(f"{x['configuration']} {x['completedConditions']}/9" for x in report['series']))


if __name__=='__main__':main()
