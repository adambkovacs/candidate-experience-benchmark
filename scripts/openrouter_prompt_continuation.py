#!/usr/bin/env python3
"""Explicit remaining-record amendment; never modifies or retries original attempts."""
import argparse
import fcntl
import hashlib
import json
import os
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote
import openrouter_paid_benchmark as paid
import prompt_execution_gates as gates
from prompt_controller import Guard
from prompt_admission import audit_response
from paid_budget_partitions import open_partition

ROOT=paid.ROOT
CONTRACT='openrouter-prompt-remaining-records-v1'
POLICY={'continue_output_length':True,'retry_failed_records':False,'output_tokens':4096,'denominator':60,
        'order_limitation':'Remaining records execute after both original conditions; original counterbalanced timing is not preserved.',
        'stop_on':['provider_error','unknown_billing','input_context_overflow','identity_violation','tool_call','refusal','other_invalid_output']}

def binding(path,root=ROOT):
    path=Path(path).resolve();return {'file':str(path.relative_to(root.resolve())),'sha256':gates.sha(path.read_bytes())}

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def original_guard(manifest,root):
    m=gates.json_bound(manifest['original_manifest'],root)
    cid=manifest['configuration_id'];v=manifest['condition'];c=next(x for x in m['configurations'] if x['id']==cid)
    controls=c['controls'];ac=controls['adapter_controls'];sup=manifest['original_smoke_supplement']
    args=SimpleNamespace(phase='development',prompt_variant=v,prompt_configuration_id=cid,
        prompt_execution_manifest=str(root/manifest['original_manifest']['file']),prompt_execution_manifest_sha256=manifest['original_manifest']['sha256'],
        prompt_schedule_journal=str(root/m['execution_journal']),prompt_smoke_supplement=str(root/sup['file']),prompt_smoke_supplement_sha256=sup['sha256'],
        model=controls['model'],reasoning=controls['effort'],parent_baseline_id=c['parent_baseline_id'],timeout=c['controller_timeout_seconds'],
        max_tokens=controls['output_reserve_tokens'],start=1,output=str(root/manifest['output']))
    return Guard(args,'openrouter_paid_v1',root/c['controller']['file'],root)

def remaining(original,requests):
    ids=[r['id'] for r in original];all_ids=[r['record_ids'][0] for r in requests]
    if not original or len(ids)>=60 or len(set(ids))!=len(ids) or ids!=all_ids[:len(ids)]:raise ValueError('Original attempts are not a unique proper prefix')
    last=original[-1];raw=last.get('raw_response') or {};choices=raw.get('choices') or []
    if last.get('status')=='ok' or last.get('cost_unknown') or not last.get('billing_ok') or len(choices)!=1 or choices[0].get('finish_reason')!='length':raise ValueError('Only known-billing output-length original stops qualify')
    diagnostics=audit_response(last,'openrouter_paid_v1',None)
    if diagnostics['blockers']!=['truncation:length']:raise ValueError('Original stop has additional violations')
    message=choices[0].get('message') or {}
    if choices[0].get('error') or message.get('tool_calls') or message.get('function_call') or message.get('refusal'):raise ValueError('Original stop is not intrinsic output-length exhaustion')
    return requests[len(ids):]

def response_diagnostics(record,limit):
    result=audit_response(record,'openrouter_paid_v1',limit)
    blockers=[b for b in result['blockers'] if b!='truncation:length']
    raw=record.get('raw_response') or {};choices=raw.get('choices') or []
    if raw.get('error') or len(choices)!=1:blockers.append('provider_error_or_ambiguous_choices')
    if len(choices)==1:
        choice=choices[0];message=choice.get('message') or {}
        if choice.get('error') or choice.get('finish_reason') not in ('stop','length'):blockers.append('provider_error_or_unexpected_finish')
        if message.get('tool_calls') or message.get('function_call'):blockers.append('tool_call')
        if message.get('refusal'):blockers.append('refusal')
    if record.get('cost_unknown') or not record.get('billing_ok'):blockers.append('unknown_or_invalid_billing')
    if record.get('status') not in ('ok','invalid_output'):blockers.append('non_intrinsic_failure')
    if record.get('status')=='invalid_output' and not (len(choices)==1 and choices[0].get('finish_reason')=='length'):blockers.append('other_invalid_output')
    return {**result,'passed':not blockers,'blockers':sorted(set(blockers)),
            'output_budget_exhausted':len(choices)==1 and choices[0].get('finish_reason')=='length',
            'protocol_amendment':CONTRACT}

def validate(manifest,root=ROOT,require_frozen=True):
    if manifest['contract']!=CONTRACT or manifest['policy']!=POLICY:raise ValueError('Unsupported amendment')
    if require_frozen:
        if manifest['status']!='FROZEN':raise ValueError('Draft cannot infer')
        if gates.stamp(manifest['frozen_utc']).timestamp()>time.time():raise ValueError('Freeze is in future')
    gates.bound(manifest['controller'],root)
    if (root/manifest['controller']['file']).resolve()!=Path(__file__).resolve():raise ValueError('Controller differs')
    for item in manifest['dependencies']:gates.bound(item,root)
    guard=original_guard(manifest,root)
    original=[json.loads(x) for x in gates.bound(manifest['original_attempts'],root).decode().splitlines() if x.strip()]
    requests=remaining(original,guard.requests)
    if manifest['remaining_requests']!=requests:raise ValueError('Amendment request subset differs')
    if guard.controls['output_reserve_tokens']!=4096:raise ValueError('Output budget changed')
    snapshot=gates.bound(manifest['original_journal_snapshot'],root)
    events=[json.loads(x) for x in snapshot.decode().splitlines() if x.strip()]
    import prompt_schedule as schedule
    original_manifest=gates.json_bound(manifest['original_manifest'],root)
    schedule._replay(events,original_manifest['schedule'],schedule._schedule(original_manifest['schedule'],root),root)
    for condition,raw_binding in manifest['terminal_original_conditions'].items():
        gates.bound(raw_binding,root)
        claims=[e for e in events if e.get('event')=='claimed' and e.get('configuration_id')==manifest['configuration_id'] and e.get('condition')==condition and e.get('stage')=='development']
        if len(claims)!=1:raise ValueError('Missing original condition claim')
        done=[e for e in events if e.get('event')=='finished' and e.get('attempt_id')==claims[0]['attempt_id']]
        if len(done)!=1 or raw_binding not in done[0]['evidence']:raise ValueError('Original condition not terminal and bound')
    if set(manifest['terminal_original_conditions'])!={'P1','P2'}:raise ValueError('Both original conditions required')
    if manifest['original_attempts']!=manifest['terminal_original_conditions'][manifest['condition']]:raise ValueError('Original source differs')
    for key in ('output','journal'):
        p=(root/manifest[key]).resolve();p.relative_to(root.resolve())
    return guard,original,requests

def build(args):
    base=ROOT/'results/prompt-comparison-v1-2026-09-24';source=base/'hosted-execution.json';m=json.loads(source.read_text());folder=base/'runs'/args.configuration/args.condition
    dest=Path(args.destination);dest.mkdir(parents=True,exist_ok=False)
    snap=dest/'original-journal-snapshot.jsonl'
    with (ROOT/m['execution_journal']).open('rb') as source_journal:
        fcntl.flock(source_journal,fcntl.LOCK_SH)
        snapshot=source_journal.read()
        fcntl.flock(source_journal,fcntl.LOCK_UN)
    snap.write_bytes(snapshot)
    manifest={'contract':CONTRACT,'status':'DRAFT','configuration_id':args.configuration,'condition':args.condition,'policy':POLICY,
        'controller':binding(__file__),'dependencies':[binding(ROOT/'scripts'/name) for name in ['openrouter_paid_benchmark.py','prompt_controller.py','prompt_admission.py','prompt_execution_gates.py','prompt_schedule.py','paid_budget_partitions.py','frozen_prompt_variants.py','evaluate_prompt_variants.py']],
        'original_manifest':binding(source),'original_smoke_supplement':binding(folder/'smoke-supplement.json'),
        'original_attempts':binding(folder/'development.jsonl'),'original_journal_snapshot':binding(snap),
        'terminal_original_conditions':{v:binding(base/'runs'/args.configuration/v/'development.jsonl') for v in ['P1','P2']},
        'budget_partition_manifest':binding(Path(args.budget_manifest)),'budget_partition_id':args.partition,
        'output':str((dest/'development.jsonl').relative_to(ROOT)),'journal':str((dest/'amendment-journal.jsonl').relative_to(ROOT))}
    guard=original_guard(manifest,ROOT);manifest['remaining_requests']=remaining(rows(folder/'development.jsonl'),guard.requests)
    validate(manifest,require_frozen=False)
    with (dest/'draft-manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
    print('DRAFT',args.configuration,args.condition,len(manifest['remaining_requests']))

def execute(args):
    p=Path(args.manifest);raw=p.read_bytes()
    if gates.sha(raw)!=args.sha256:raise ValueError('Amendment manifest hash differs')
    manifest=json.loads(raw);guard,original,requests=validate(manifest)
    output=ROOT/manifest['output'];journal=ROOT/manifest['journal']
    if output.exists() or journal.exists():raise FileExistsError('Never replay amendment')
    controls=guard.controls;ac=controls['adapter_controls'];first=gates.json_bound(requests[0]['client_request'],ROOT)['request'];provider=first['provider']['only'][0];prices=first['provider']['max_price']
    token=paid.load_key(args.env_file)
    model,endpoint=paid.select_endpoint(controls['model'],provider,paid.fetch('/models',timeout=guard.args.timeout),paid.fetch('/models/'+quote(controls['model'],safe='/')+'/endpoints',timeout=guard.args.timeout),prices['prompt'],prices['completion'])
    paid.check_paid_phase_two(SimpleNamespace(start=1,budget_partition_manifest=manifest['budget_partition_manifest']['file'],budget_partition_id=manifest['budget_partition_id'],model=controls['model'],reasoning=controls['effort'],max_tokens=4096),controls,endpoint)
    actual_args=SimpleNamespace(model=controls['model'],reasoning=controls['effort'])
    inputs={r['id']:r for r in paid.read_rows(ROOT/'data/pilot/inputs.jsonl')};policy=gates.bound(guard.condition['instruction'],ROOT).decode();schema=json.loads((ROOT/'schemas/judgments.schema.json').read_text())
    for req in requests:
        payload=paid.make_payload(controls['model'],endpoint,inputs[req['record_ids'][0]]['feedback'],policy,schema,controls['effort'],4096,prices['prompt'],prices['completion'],model)
        if {'request':payload,'adapter_controls':paid.paid_adapter_controls(actual_args,endpoint,payload)}!=gates.json_bound(req['client_request'],ROOT):raise ValueError('Live request controls differ')
    gates.bound(manifest['budget_partition_manifest'],ROOT)
    reserve=paid.reservation(endpoint,4096,prices['prompt'],prices['completion']);ledger=None
    with journal.open('x') as audit:
        paid.durable(audit,{'event':'claimed','manifest_sha256':args.sha256,'configuration_id':manifest['configuration_id'],'condition':manifest['condition'],'remaining_ids':[r['record_ids'][0] for r in requests],'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        completed=False;count=0
        try:
            ledger=open_partition(paid.LEDGER_PATH,ROOT/manifest['budget_partition_manifest']['file'],manifest['budget_partition_id'],controls['model'],provider,controls['effort'])
            with output.open('x') as out:
                for req in requests:
                    rid=req['record_ids'][0];payload=gates.json_bound(req['client_request'],ROOT)['request'];attempt=ledger.reserve(reserve,rid);start=time.perf_counter();actual=None
                    record={'id':rid,'phase':'development','requested_model':controls['model'],'provider_endpoint':endpoint,'model_catalog_entry':model,'request':payload,'attempt_id':attempt,'reference_labels_read':False,'surface':'OpenRouter paid HTTP','hardware':'Remote provider undisclosed','runtime':'OpenRouter HTTP v1','quantization':endpoint.get('quantization'),'reasoning_effort':controls['effort'],'retry_policy':'none; exclusive files; every attempt reserves against shared cap','continue_on_invalid_output':True,'reserved_cost_usd':str(reserve),'amendment_manifest_sha256':args.sha256,'protocol_amendment':CONTRACT,'prompt_variant':{'variant':manifest['condition'],'parent_baseline_id':guard.config['parent_baseline_id']}}
                    paid.durable(audit,{'event':'request_started','id':rid,'attempt_id':attempt,'request_sha256':gates.sha(json.dumps(payload,sort_keys=True).encode())})
                    try:
                        body=paid.fetch('/chat/completions',token,payload,guard.args.timeout);body=json.loads(json.dumps(body).replace(token,'[REDACTED]'));record['raw_response']=body;record['usage']=body.get('usage') or {};record['returned_model']=body.get('model');record['returned_provider']=body.get('provider')
                        if record['usage'].get('cost') is not None:actual=paid.number(record['usage']['cost'])
                        choices=body.get('choices') or [];choice=choices[0] if len(choices)==1 else {};message=choice.get('message') or {};record['finish_reason']=choice.get('finish_reason')
                        try:prediction=json.loads(message.get('content'))
                        except (ValueError,TypeError):prediction=None
                        record['prediction']=prediction;record['status']='ok' if paid.valid(prediction) and choice.get('finish_reason')=='stop' else 'invalid_output'
                        if body.get('model') not in paid.allowed_returned_models(controls['model'],endpoint) or body.get('provider')!=endpoint['provider_name']:record.update(status='identity_violation',identity_violation=True)
                    except Exception as exc:
                        record.update(status='service_error',error_type=type(exc).__name__)
                        if isinstance(exc,urllib.error.HTTPError):
                            record['http_status']=exc.code
                            try:record['raw_error_response']=json.loads(exc.read(1000000).decode().replace(token,'[REDACTED]'))
                            except (ValueError,UnicodeError):pass
                    billing=ledger.settle(attempt,actual);record.update(elapsed_seconds=time.perf_counter()-start,observed_cost_usd=str(actual) if actual is not None else None,cost_unknown=actual is None,billing_ok=billing)
                    record['amendment_response_diagnostics']=response_diagnostics(record,controls['context_tokens']-4096)
                    paid.durable(out,record);paid.durable(audit,{'event':'request_finished','id':rid,'attempt_id':attempt,'status':record['status']});count+=1;print(rid,record['status'],flush=True)
                    if not record['amendment_response_diagnostics']['passed']:break
                else:completed=True
        finally:
            if ledger is not None:ledger.close()
            paid.durable(audit,{'event':'finished','status':'completed_remaining_attempts' if completed else 'stopped','attempted_records':count,'canonical_denominator':60,'original_failed_records_retained':True,'output':binding(output) if output.exists() else None})

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True);b=sub.add_parser('build');b.add_argument('--configuration',required=True);b.add_argument('--condition',choices=['P1','P2'],required=True);b.add_argument('--partition',required=True);b.add_argument('--budget-manifest',required=True);b.add_argument('--destination',required=True);r=sub.add_parser('run');r.add_argument('--manifest',required=True);r.add_argument('--sha256',required=True);r.add_argument('--env-file');args=parser.parse_args();(build if args.command=='build' else execute)(args)
if __name__=='__main__':main()
