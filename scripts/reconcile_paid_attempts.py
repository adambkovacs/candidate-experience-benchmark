#!/usr/bin/env python3
"""Offline reconciliation of explicitly ordered terminal paid development attempts.

Never calls a model or reads reference labels. Raw files remain immutable. Later
source files supersede earlier attempts for an ID, including later failures.
All raw files remain in registry timing evidence. This helper does not edit a
registry, evaluate labels, settle the budget ledger, or resume inference.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from development_benchmark import ROOT,digest,read_rows,valid
from openrouter_paid_benchmark import validate_rows,number
from openrouter_benchmark import allowed_returned_models


def relative(path,root):
    return str(path.resolve().relative_to(root.resolve()))

def reconcile(paths,input_path,root=ROOT,allow_partial=False,allow_timeout_change=False,legacy_timeouts=None):
    paths=[Path(p).resolve() for p in paths];root=Path(root).resolve()
    if not paths or len(set(paths))!=len(paths):raise ValueError('Require distinct ordered attempt sources')
    inputs={r['id']:r['feedback'] for r in validate_rows(read_rows(input_path))}
    overrides=legacy_timeouts or {}
    if set(overrides)-set(map(str,paths)):raise ValueError('Timeout override does not name a source')
    sources=[];seen_attempts=set();seen_contents=set();latest={};first=None;timeouts=set();legacy=[]
    cost=Decimal(0);unknown=Decimal(0);unknown_attempts=[];seconds=0;previous_time=None;attempt_count=0
    for path in paths:
        name=relative(path,root)
        if any('smoke' in part.lower() for part in path.parts):raise ValueError('Smoke cannot supply development attempts')
        raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if not raw or not raw.endswith(b'\n'):raise ValueError('Source is empty or lacks terminal newline')
        if sha in seen_contents:raise ValueError('Duplicate source content')
        seen_contents.add(sha);rows=[json.loads(line) for line in raw.decode().splitlines()]
        previous_id=0
        for row in rows:
            rid=row.get('id');attempt=row.get('attempt_id')
            if rid not in inputs or row.get('phase')!='development':raise ValueError('Unknown ID or non-development phase')
            current_id=int(rid.split('-')[1])
            if current_id<=previous_id:raise ValueError('Each source must have increasing unique IDs')
            previous_id=current_id
            if not isinstance(attempt,str) or not attempt or attempt in seen_attempts:raise ValueError('Missing or duplicate attempt ID')
            seen_attempts.add(attempt)
            stamp=datetime.fromisoformat(row['started_utc'].replace('Z','+00:00'))
            if stamp.tzinfo is None or (previous_time is not None and stamp<previous_time):raise ValueError('Source order must follow attempt chronology')
            previous_time=stamp
            elapsed=row.get('elapsed_seconds')
            if isinstance(elapsed,bool) or not isinstance(elapsed,(int,float)) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid attempt duration')
            seconds+=elapsed
            timeout=row.get('request_timeout_seconds')
            if timeout is None:
                if str(path) not in overrides:raise ValueError('Legacy missing timeout requires explicit source override')
                timeout=overrides[str(path)]
                if not any(x['source']==name for x in legacy):legacy.append({'source':name,'seconds':timeout,'basis':'Explicit operator launch evidence; absent from original attempt'})
            elif str(path) in overrides:raise ValueError('Cannot override recorded timeout')
            if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:raise ValueError('Invalid timeout')
            timeouts.add(timeout)
            if len(timeouts)>1 and not allow_timeout_change:raise ValueError('Timeout change requires explicit flag')
            request=row['request'];messages=request['messages'];endpoint=row['provider_endpoint']
            if len(messages)!=2 or set(messages[0])!={'role','content'} or messages[0]['role']!='system' or set(messages[1])!={'role','content'} or messages[1]['role']!='user':raise ValueError('Unexpected request messages')
            if json.loads(messages[1]['content'])!={'feedback':inputs[rid]}:raise ValueError('Feedback mismatch or extra inference metadata')
            schema=request['response_format']['json_schema']['schema']
            if row.get('request_sha256')!=digest(json.dumps(request,sort_keys=True)):raise ValueError('Request hash mismatch')
            if row.get('policy_sha256')!=digest(messages[0]['content']) or row.get('schema_sha256')!=digest(json.dumps(schema,sort_keys=True)) or row.get('input_sha256')!=digest(inputs[rid]):raise ValueError('Policy/schema/input hash mismatch')
            if row.get('reference_labels_read') is not False:raise ValueError('Missing label-isolation evidence')
            if request['model']!=row['requested_model'] or endpoint['model_id']!=row['requested_model']:raise ValueError('Model mismatch')
            if row['quantization']!=endpoint.get('quantization'):raise ValueError('Quantization mismatch')
            if request['provider']['only']!=[endpoint['tag']] or request['provider'].get('allow_fallbacks') is not False:raise ValueError('Provider control mismatch')
            if row['status']=='ok':
                if not valid(row.get('prediction')) or row.get('returned_model') not in allowed_returned_models(row['requested_model'],endpoint) or row.get('returned_provider')!=endpoint['provider_name']:raise ValueError('Successful prediction identity/schema invalid')
            invariant={'model':row['requested_model'],'provider_tag':endpoint['tag'],'provider_name':endpoint['provider_name'],'quantization':row['quantization'],
                'reasoning_effort':row['reasoning_effort'],'policy_sha256':row['policy_sha256'],'schema_sha256':row['schema_sha256'],
                'system_message':messages[0],'request_controls':{k:v for k,v in request.items() if k!='messages'},
                'runtime':row.get('runtime'),'surface':row.get('surface'),'hardware':row.get('hardware')}
            if first is None:first=invariant
            elif invariant!=first:raise ValueError('Cross-configuration attempt mix')
            if row.get('cost_unknown') is True:
                if row.get('observed_cost_usd') is not None:raise ValueError('Unknown cost cannot also be observed')
                bound=number(row['reserved_cost_usd']);unknown+=bound
                unknown_attempts.append({'attempt_id':attempt,'record_id':rid,'source':name,'reserved_upper_bound_usd':str(bound),'actual_cost_usd':None})
            elif row.get('cost_unknown') is False:
                cost+=number(row['observed_cost_usd'])
            else:raise ValueError('Missing cost state')
            selected=dict(row);selected['reconciliation_source']={'file':name,'sha256':sha,'attempt_id':attempt}
            latest[rid]=selected;attempt_count+=1
        sources.append({'file':name,'sha256':sha,'attempts':len(rows)})
    missing=sorted(set(inputs)-set(latest))
    if missing and not allow_partial:raise ValueError('Missing development IDs: '+','.join(missing))
    # Detect inputs still being appended during this operation; caller must also
    # explicitly confirm all source processes are terminal before invoking CLI.
    for path,source in zip(paths,sources):
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Source changed during reconciliation')
    selected=[latest[rid] for rid in sorted(latest)]
    audit={'status':'partial' if missing else 'complete_attempt_coverage','selection_rule':'Latest attempt in explicitly ordered chronological sources per ID; never best-result selection',
        'records':len(selected),'total_attempts':attempt_count,'missing_ids':missing,'sources':sources,'configuration':first,
        'input_file':relative(Path(input_path),root),'input_file_sha256':hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
        'timeout_values_seconds':sorted(timeouts),'timeout_change_explicitly_allowed':allow_timeout_change,'legacy_timeout_overrides':legacy,
        'total_attempt_seconds':seconds,'costs':{'known_actual_usd':str(cost),'unknown_reserved_upper_bound_usd':str(unknown),'known_plus_unknown_upper_bound_usd':str(cost+unknown),
            'unknown_attempts':unknown_attempts,'basis':'All source attempts, including superseded attempts. Unknown bounds come from raw reservations, not observed costs; this helper does not independently audit or change ledger finalization.'},
        'registry_fields':{'attempt_phase':'development','attempt_files':[x['file'] for x in sources]},
        'reference_labels_read':False,'source_files_modified':False}
    return selected,audit

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',action='append',required=True,help='Terminal raw development file; repeat in chronological order')
    p.add_argument('--output',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--allow-partial',action='store_true');p.add_argument('--allow-timeout-change',action='store_true')
    p.add_argument('--legacy-timeout',action='append',default=[],metavar='SOURCE=SECONDS')
    p.add_argument('--terminal-sources-confirmed',action='store_true',required=True)
    args=p.parse_args();output=Path(args.output).resolve();manifest=Path(args.manifest).resolve()
    sources=[Path(x).resolve() for x in args.source]
    if output==manifest or output in sources or manifest in sources or output.exists() or manifest.exists():raise ValueError('Require distinct new output/manifest paths')
    relative(output,ROOT);relative(manifest,ROOT)
    overrides={}
    for item in args.legacy_timeout:
        path,seconds=item.rsplit('=',1);key=str(Path(path).resolve())
        if key in overrides:raise ValueError('Duplicate timeout override')
        overrides[key]=float(seconds)
    rows,audit=reconcile(sources,ROOT/'data/pilot/inputs.jsonl',ROOT,args.allow_partial,args.allow_timeout_change,overrides)
    encoded=''.join(json.dumps(row)+'\n' for row in rows)
    audit['predictions_file']=relative(output,ROOT);audit['prediction_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
    audit['registry_fields']['predictions_file']=audit['predictions_file']
    # Registry is a reviewable fragment only; never modify shared registries here.
    with open(output,'x') as f:f.write(encoded)
    with open(manifest,'x') as f:json.dump(audit,f,indent=2);f.write('\n')
    print(json.dumps({'records':len(rows),'attempts':audit['total_attempts'],'status':audit['status'],'manifest':str(manifest)}))
if __name__=='__main__':main()
