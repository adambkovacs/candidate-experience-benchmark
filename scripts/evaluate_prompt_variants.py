#!/usr/bin/env python3
"""Offline P0/P1/P2 evaluation. Only this evaluator reads reference labels.

Manifest contract prompt-pairs-v1 (paths relative to --root): inputs, references,
pairs, baseline_instruction each {file,sha256}; parent_baseline_id, role; controls
and controls_sha256; allow_missing_outputs boolean; attempt_selection
latest_chronological|first_chronological; retry_authorizations mapping condition
to exact explicitly authorized retry attempt IDs; conditions P0/P1/P2 each
{predictions:{file,sha256}, extractor:openrouter_paid_v1|declared_only,
 request_evidence:{file,sha256}}. request_evidence is required for the extractor.
The baseline text plus frozen additions define each expected instruction exactly.
Other surfaces remain declared_only, never eligible audited paired comparisons.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation
from development_benchmark import ROOT,KEYS,digest,score,valid
from frozen_prompt_variants import compose_instruction
from openrouter_benchmark import allowed_returned_models
from build_development_report import summarize_costs


def canonical_hash(value):return digest(json.dumps(value,sort_keys=True))

def bound_read(spec,root):
    path=(root/spec['file']).resolve();path.relative_to(root.resolve())
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=spec['sha256']:raise ValueError('Source hash mismatch: '+spec['file'])
    return raw

def rows_from(raw):return [json.loads(line) for line in raw.decode().splitlines() if line.strip()]

def indexed(rows,known,complete=False):
    result={}
    for row in rows:
        rid=row.get('id')
        if rid not in known or rid in result:raise ValueError('Unknown or duplicate record ID')
        result[rid]=row
    if complete and set(result)!=known:raise ValueError('Require exactly60 unique IDs')
    return result

def extract_controls(row):
    request=row['request'];endpoint=row['provider_endpoint']
    return {'requested_model':row['requested_model'],'provider_tag':endpoint['tag'],'provider_name':endpoint['provider_name'],
        'quantization':row['quantization'],'reasoning_effort':row['reasoning_effort'],
        'request_controls':{k:v for k,v in request.items() if k!='messages'},
        'runtime':row.get('runtime'),'hardware':row.get('hardware'),'surface':row.get('surface'),
        'retry_policy':row['retry_policy'],'workflow':'single_record'}

def audit_requests(rawrows,predictions,inputs,text,controls,selection,retry_authorizations):
    if not rawrows:raise ValueError('No raw request evidence to verify')
    attempts={};by_record={};request_order=[];previous_time=None;retry_ids=[]
    if not isinstance(retry_authorizations,list) or len(set(retry_authorizations))!=len(retry_authorizations):raise ValueError('Invalid retry authorization list')
    for row in rawrows:
        rid=row.get('id');aid=row.get('attempt_id')
        if rid not in inputs or row.get('phase')!='development' or not aid or aid in attempts:raise ValueError('Invalid request audit identity/phase')
        try:stamp=datetime.fromisoformat(row['started_utc'].replace('Z','+00:00'))
        except (KeyError,ValueError,AttributeError):raise ValueError('Missing or invalid attempt timestamp') from None
        if stamp.tzinfo is None or (previous_time is not None and stamp<previous_time):raise ValueError('Nonmonotonic attempt chronology')
        previous_time=stamp
        if rid in by_record:
            if stamp<=by_record[rid][-1][0] or aid not in retry_authorizations:raise ValueError('Retry needs later timestamp and explicit authorization')
            retry_ids.append(aid)
        else:request_order.append(rid)
        by_record.setdefault(rid,[]).append((stamp,row))
        attempts[aid]=row
        request=row['request'];endpoint=row['provider_endpoint']
        expected=[{'role':'system','content':text},{'role':'user','content':json.dumps({'feedback':inputs[rid]['feedback']})}]
        # Compare user JSON structurally; exact instruction and role bytes stay fixed.
        messages=request.get('messages',[])
        if len(messages)!=2 or messages[0]!=expected[0] or set(messages[1])!={'role','content'} or messages[1]['role']!='user' or json.loads(messages[1]['content'])!={'feedback':inputs[rid]['feedback']}:raise ValueError('Actual instruction/role/feedback mismatch')
        if row.get('input_sha256')!=digest(inputs[rid]['feedback']):raise ValueError('Actual input hash mismatch')
        if row.get('request_sha256')!=canonical_hash(request):raise ValueError('Actual request hash mismatch')
        if row['requested_model']!=request['model'] or endpoint['model_id']!=request['model'] or row['quantization']!=endpoint.get('quantization'):raise ValueError('Actual model/quantization mismatch')
        if request['provider']['only']!=[endpoint['tag']] or request['provider'].get('allow_fallbacks') is not False:raise ValueError('Actual provider controls mismatch')
        if extract_controls(row)!=controls:raise ValueError('Actual controls differ from paired manifest')
        body=row.get('raw_response') or {}
        raw_usage=body.get('usage')
        if 'usage' in row and row['usage']!=raw_usage:raise ValueError('Mirrored usage differs from raw response')
        raw_cost=raw_usage.get('cost') if isinstance(raw_usage,dict) else None
        observed=row.get('observed_cost_usd')
        if row.get('cost_unknown') is False and observed is None:raise ValueError('Known cost claim requires observed raw cost')
        if observed is not None:
            try:
                actual=Decimal(str(raw_cost));claimed=Decimal(str(observed))
            except InvalidOperation:raise ValueError('Observed cost lacks raw evidence') from None
            if isinstance(raw_cost,bool) or isinstance(observed,bool) or not actual.is_finite() or actual<0 or claimed!=actual:raise ValueError('Observed cost differs from raw response')
        if row.get('cost_unknown') is True and raw_cost is not None:raise ValueError('Unknown cost conflicts with reported raw cost')
        if row.get('status')=='ok':
            body=row.get('raw_response',{});choice=body.get('choices',[{}])[0];message=choice.get('message',{})
            try:parsed=json.loads(message.get('content'))
            except (ValueError,TypeError):parsed=None
            if body.get('model') not in allowed_returned_models(row['requested_model'],endpoint) or body.get('provider')!=endpoint['provider_name'] or choice.get('finish_reason')!='stop' or message.get('refusal') or message.get('tool_calls') or parsed!=row.get('prediction'):raise ValueError('Success not supported by raw response')
    if set(retry_ids)!=set(retry_authorizations):raise ValueError('Retry authorization must match observed retries exactly')
    if request_order!=list(inputs):raise ValueError('Record request order differs from frozen input order')
    for rid,row in predictions.items():
        selected=by_record.get(rid,[])
        chosen=selected[-1 if selection=='latest_chronological' else 0][1] if selected else None
        if chosen is None or row.get('attempt_id')!=chosen['attempt_id']:raise ValueError('Prediction violates predeclared attempt selection')
        original=attempts.get(row.get('attempt_id'))
        if original is None or original['id']!=rid or original.get('status')!=row.get('status') or original.get('prediction')!=row.get('prediction'):raise ValueError('Prediction lacks matching raw attempt')
    return list(attempts.values())

def usable(row):return row is not None and row.get('status')=='ok' and valid(row.get('prediction'))

def state(row):
    if row is None:return 'missing'
    if usable(row):return 'valid'
    return 'invalid_schema' if row.get('status')=='ok' else str(row.get('status','unknown_failure'))

def telemetry(rows):
    def total(extract):
        values=[extract(r) for r in rows]
        if not values or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values):return None
        return sum(values)
    return {'attempts':len(rows),'input_tokens':total(lambda r:(r.get('usage') or {}).get('prompt_tokens')),
        'output_tokens':total(lambda r:(r.get('usage') or {}).get('completion_tokens')),
        'reasoning_tokens':total(lambda r:((r.get('usage') or {}).get('completion_tokens_details') or {}).get('reasoning_tokens')),
        'attempt_seconds':total(lambda r:r.get('elapsed_seconds')),
        'note':'All audited attempts where available, including superseded retries. Any missing value makes its aggregate unknown; no missing-to-zero substitution.'}

def compare(left,right,refs):
    fields={k:{'valid_label_transitions':{},'changed_ids':[],'wrong_to_correct':[],'correct_to_wrong':[]} for k in KEYS}
    result={'denominator':60,'both_valid':0,'fields':fields,'valid_to_failed':[],'failed_to_valid':[],'both_failed':[],
            'failure_transitions':{},'all_four_wrong_to_correct':[],'all_four_correct_to_wrong':[],'cases':[]}
    for rid,ref in refs.items():
        a=left.get(rid);b=right.get(rid);sa=state(a);sb=state(b);truth=ref['proposed_labels']
        if usable(a) and usable(b):
            result['both_valid']+=1
            pa=a['prediction'];pb=b['prediction']
            for key in KEYS:
                f=fields[key];transition=pa[key]+' -> '+pb[key];f['valid_label_transitions'][transition]=f['valid_label_transitions'].get(transition,0)+1
                if pa[key]!=pb[key]:f['changed_ids'].append(rid)
                if pa[key]!=truth[key] and pb[key]==truth[key]:f['wrong_to_correct'].append(rid)
                if pa[key]==truth[key] and pb[key]!=truth[key]:f['correct_to_wrong'].append(rid)
            if pa!=truth and pb==truth:result['all_four_wrong_to_correct'].append(rid)
            if pa==truth and pb!=truth:result['all_four_correct_to_wrong'].append(rid)
        else:
            transition=sa+' -> '+sb;result['failure_transitions'].setdefault(transition,[]).append(rid)
            result['valid_to_failed' if usable(a) else 'failed_to_valid' if usable(b) else 'both_failed'].append(rid)
        if sa!=sb or (a or {}).get('prediction')!=(b or {}).get('prediction'):
            result['cases'].append({'id':rid,'from_state':sa,'to_state':sb,'from_prediction':(a or {}).get('prediction'),'to_prediction':(b or {}).get('prediction'),'reference':truth})
    result['changed_record_count']=len(result['cases'])
    return result

def evaluate(manifest,root=ROOT):
    root=Path(root)
    if manifest.get('contract')!='prompt-pairs-v1' or set(manifest.get('conditions',{}))!={'P0','P1','P2'}:raise ValueError('Unsupported pair manifest')
    if manifest.get('attempt_selection') not in ('latest_chronological','first_chronological'):raise ValueError('Explicit chronological attempt selection required')
    if not isinstance(manifest.get('retry_authorizations'),dict) or set(manifest['retry_authorizations'])-{'P0','P1','P2'}:raise ValueError('Explicit per-condition retry authorization map required')
    if type(manifest.get('allow_missing_outputs')) is not bool:raise ValueError('Explicit missing-output policy required')
    expected={f'DEV-{i:03}' for i in range(1,61)}
    inputs=indexed(rows_from(bound_read(manifest['inputs'],root)),expected,True)
    if any(set(row)!={'id','feedback'} or not isinstance(row['feedback'],str) for row in inputs.values()):raise ValueError('Invalid development inputs')
    # Reference access starts here and stays in this offline evaluator.
    refs=indexed(rows_from(bound_read(manifest['references'],root)),expected,True)
    if any(row.get('split')!='development' or not valid(row.get('proposed_labels')) for row in refs.values()):raise ValueError('Invalid development references')
    pairs=json.loads(bound_read(manifest['pairs'],root))
    if len({pair['id'] for pair in pairs})!=len(pairs):raise ValueError('Duplicate controlled pair IDs')
    for pair in pairs:
        if len(set(pair['record_ids']))!=2 or len(pair['record_ids'])!=2 or set(pair['record_ids'])-expected or set(pair['invariant_fields']+pair['changed_fields'])!=set(KEYS):raise ValueError('Invalid controlled pair')
    base=bound_read(manifest['baseline_instruction'],root).decode();controls=manifest['controls']
    if canonical_hash(controls)!=manifest['controls_sha256']:raise ValueError('Control hash mismatch')
    if controls.get('reasoning_effort') in ('max','ultra') or controls.get('request_controls',{}).get('reasoning',{}).get('effort') in ('max','ultra'):raise ValueError('Max/ultra excluded from new comparisons')
    result={'contract':'prompt-pairs-v1','manifest_sha256':canonical_hash(manifest),'parent_baseline_id':manifest['parent_baseline_id'],
        'denominator':60,'conditions':{},'comparisons':{},'controls_verified':True,'eligible_paired_comparison':False,
        'attempt_selection':manifest['attempt_selection'],
        'protocol_verification':{'status':'incomplete','missing_audit_capabilities':['token/context preflight','smoke inspection gates','pre-inference frozen roster','counterbalanced execution schedule'],'note':'Controls verification alone does not establish full protocol eligibility. These gate extractors are not implemented.'},
        'reference_status':'Provisional AI-reviewed development references; not held-out human truth','reference_labels_read_offline':True}
    indexes={}
    for variant,condition in manifest['conditions'].items():
        composition=compose_instruction(base,variant,role=manifest['role'],parent_baseline_id=manifest['parent_baseline_id'],root=root)
        predictions=indexed(rows_from(bound_read(condition['predictions'],root)),expected,not manifest['allow_missing_outputs']);indexes[variant]=predictions
        if condition['extractor']=='openrouter_paid_v1':
            if manifest['role']!='system':raise ValueError('OpenRouter extractor requires native system role')
            rawrows=rows_from(bound_read(condition['request_evidence'],root));attempts=audit_requests(rawrows,predictions,inputs,composition['instruction'],controls,manifest['attempt_selection'],manifest['retry_authorizations'].get(variant,[]))
            verification='verified_against_hash_bound_raw_requests'
        elif condition['extractor']=='declared_only':
            attempts=[];verification='unavailable';result['controls_verified']=False
        else:raise ValueError('Unsupported request evidence extractor')
        omitted=[]
        for rid in sorted(expected-set(predictions)):
            matching=[row for row in attempts if row['id']==rid]
            chosen=matching[-1 if manifest['attempt_selection']=='latest_chronological' else 0] if matching else None
            omitted.append({'id':rid,'selected_audited_attempt_id':chosen.get('attempt_id') if chosen else None,'selected_audited_status':chosen.get('status') if chosen else None,'scored_as':'missing','note':'Explicit missing-output allowance does not excuse omission or establish full paired eligibility.'})
        evaluation=score(list(refs.values()),list(predictions.values()),pairs)
        all_four=sum(usable(row) and row['prediction']==refs[rid]['proposed_labels'] for rid,row in predictions.items())
        result['conditions'][variant]={'evaluation':evaluation,'all_four_correct':all_four,'actual_controls_verification':verification,
            'omitted_predictions':omitted,'prompt_provenance':composition['audit'],'prompt_bytes_added':composition['audit']['composed_instruction_bytes']-len(base.encode()),
            'prompt_token_overhead':None,'telemetry':telemetry(attempts),'cost':summarize_costs(attempts,[condition['request_evidence']['file']] if attempts else []),
            'evidence':condition}
    for a,b in [('P0','P1'),('P0','P2'),('P1','P2')]:
        comparison=compare(indexes[a],indexes[b],refs)
        for case in comparison['cases']:case['feedback']=inputs[case['id']]['feedback']
        result['comparisons'][a+'_to_'+b]=comparison
    result['limitations']=['Manifest assertions alone do not verify actual controls. Any unavailable extractor makes controls verification unavailable. Full protocol eligibility also requires separate gate evidence and remains incomplete in this bounded evaluator.',
        'Failed or missing outputs stay in denominator60; valid-label transitions exclude failures and report them separately.',
        'Unknown hardware/provider revision remains unknown even when declared identically. Historical baseline reuse and single stochastic passes do not establish causal improvement.',
        'Prompt bytes are not token counts; token overhead is unavailable until separately measured.']
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True,type=Path);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise FileExistsError('Never overwrite a paired evaluation')
    manifest=json.loads(a.manifest.read_text());result=evaluate(manifest,a.root)
    result['manifest_file_sha256']=hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    with a.output.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps({'output':str(a.output),'eligible_paired_comparison':result['eligible_paired_comparison']}))
if __name__=='__main__':main()
