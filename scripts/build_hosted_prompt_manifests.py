#!/usr/bin/env python3
"""Build offline OpenRouter condition fragments from full source evidence.

Never freezes a subset, runs inference, reads references, or allocates money.
An optional root-supplied full roster/inventory supplies the global schedule;
otherwise scheduling stays absent until the root merges all adapter fragments.
"""
import argparse,json,re
from pathlib import Path
from build_prompt_pairing_draft import COMPLETE,file_bytes
from development_benchmark import digest
from evaluate_prompt_variants import extract_controls,audit_requests
from frozen_prompt_variants import compose_instruction,MANIFEST_SHA256
from openrouter_paid_benchmark import ALLOWED_MODELS,make_payload
from prompt_admission import expected_request
from prompt_execution_gates import canonical
ROOT=Path(__file__).resolve().parents[1]


def build(root,source_snapshot,output_directory,roster=None,inventory=None):
    root=Path(root).resolve();output=(root/output_directory).resolve();output.relative_to(root)
    if output.exists():raise FileExistsError('Exclusive preparation directory required')
    if bool(roster)!=bool(inventory):raise ValueError('Full roster and inventory must be supplied together')
    def source(name):
        raw=file_bytes(root,str(name));return {'file':str(name),'sha256':digest(raw.decode())},raw
    snapshot_spec,snapshot_raw=source(source_snapshot);snapshot=json.loads(snapshot_raw)
    entries=snapshot if isinstance(snapshot,list) else snapshot['configurations']
    configs=[r.get('configuration',r) for r in entries];byid={r['id']:r for r in configs}
    if not configs or len(byid)!=len(configs):raise ValueError('Full source snapshot needs unique configurations')
    inp_spec,inp_raw=source('data/pilot/inputs.jsonl');inputs=[json.loads(x) for x in inp_raw.decode().splitlines() if x.strip()]
    if [r.get('id') for r in inputs]!=[f'DEV-{i:03}' for i in range(1,61)] or any(set(r)!={'id','feedback'} for r in inputs):raise ValueError('Require exactly60 ordered input-only records')
    lookup={r['id']:r for r in inputs};schema_spec,schema_raw=source('schemas/judgments.schema.json');schema=json.loads(schema_raw)
    bundle_spec,bundle_raw=source('prompts/variants-v1/manifest.json')
    if bundle_spec['sha256']!=MANIFEST_SHA256:raise ValueError('Frozen prompt bundle changed')
    controller_spec,_=source('scripts/openrouter_paid_benchmark.py')
    roster_spec=inventory_spec=None;order=None;selected=None
    if roster:
        roster_spec,raw=source(roster);roster_rows=json.loads(raw)['entries'];inventory_spec,raw=source(inventory);inventory_rows=json.loads(raw)['entries']
        for rows in (roster_rows,inventory_rows):
            if len(rows)!=len(byid) or {r['id'] for r in rows}!=set(byid):raise ValueError('Root roster/inventory must retain the full source identity set')
        if any(r.get('state') not in ('scheduled','blocked','excluded') or not r.get('reason') for r in roster_rows):raise ValueError('Each root roster disposition needs a reason')
        if any(r.get('disposition') not in ('completed','blocked','excluded','executable') or not r.get('reason') for r in inventory_rows):raise ValueError('Each source disposition needs a reason')
        selected={r['parent_baseline_id']:r for r in roster_rows if r['state']=='scheduled'}
        if len(selected)!=sum(r['state']=='scheduled' for r in roster_rows):raise ValueError('Duplicate scheduled parent requires explicit deduplication')
        scheduled=[r for r in roster_rows if r['state']=='scheduled'];order=[{'id':r['id'],'conditions':['P1','P2'] if i%2==0 else ['P2','P1']} for i,r in enumerate(scheduled)]
    output.mkdir(parents=True)
    def write(name,value,text=False):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as f:f.write(value if text else json.dumps(value,indent=2)+'\n')
        return {'file':str(path.relative_to(root)),'sha256':digest(path.read_text())}
    fragments=[];blocked=[];untouched=[]
    for entry in configs:
        parent_id=entry['id']
        if entry.get('model') not in ALLOWED_MODELS:
            untouched.append(parent_id);continue
        if entry.get('status') not in COMPLETE or not entry.get('predictions_file'):
            blocked.append({'id':parent_id,'reason':entry.get('notes') or 'No complete development evidence','source_status':entry.get('status')});continue
        if selected is not None and parent_id not in selected:
            blocked.append({'id':parent_id,'reason':'Not scheduled in root full roster','source_status':entry.get('status')});continue
        cid=selected[parent_id]['id'] if selected is not None else parent_id
        if not re.fullmatch(r'[A-Za-z0-9._-]+',cid):raise ValueError('Unsafe configuration filename')
        try:
            names=entry.get('attempt_files') or [entry['predictions_file']];sources=[];raw=[]
            for name in names:
                spec,data=source(name);sources.append(spec);raw.extend(json.loads(line) for line in data.decode().splitlines() if line.strip())
            if len(raw)!=60 or [r['id'] for r in raw]!=list(lookup):raise ValueError('Require 60 original ordered attempts; retries need explicit selection review')
            first=raw[0];policy=first['request']['messages'][0]['content'];adapter=extract_controls(first)
            pred_spec,pred_raw=source(entry['predictions_file']);predictions={r['id']:r for r in (json.loads(line) for line in pred_raw.decode().splitlines() if line.strip())}
            if set(predictions)!=set(lookup):raise ValueError('Incomplete selected P0 coverage')
            audit_requests(raw,predictions,lookup,policy,adapter,'first_chronological',[])
            contexts={r['provider_endpoint']['context_length'] for r in raw};timeouts={r.get('request_timeout_seconds') for r in raw}
            if len(contexts)!=1 or len(timeouts)!=1 or None in timeouts:raise ValueError('Historical context or timeout changed; explicit control review required')
            endpoint=first['provider_endpoint'];model=first['model_catalog_entry'];request=first['request'];prices=request['provider']['max_price']
            if request['response_format']['json_schema']['schema']!=schema:raise ValueError('Historical schema differs')
            for row in raw:
                p=make_payload(first['requested_model'],endpoint,lookup[row['id']]['feedback'],policy,schema,first['reasoning_effort'],request['max_tokens'],prices['prompt'],prices['completion'],model)
                if p!=row['request']:raise ValueError('Historical request differs from current exact reconstruction')
            controls={'adapter_controls':adapter,'model':first['requested_model'],'model_revision':None,'quantization':first['quantization'],'runtime':first['runtime'],'hardware':first['hardware'],'effort':first['reasoning_effort'],'sampling':{'temperature':request['temperature']},'output_method':'json_schema','parsing':'strict_json','retry_policy':first['retry_policy'],'context_tokens':next(iter(contexts)),'output_reserve_tokens':request['max_tokens']}
            ch=canonical(controls);prefix=cid+'/';history=write(prefix+'historical-attempts.jsonl',''.join(json.dumps(r)+'\n' for r in raw),True)
            continuation=[{'record_id':r['id'],'enabled':r.get('continue_on_invalid_output',False)} for r in raw]
            mixed=len({r['enabled'] for r in continuation})>1
            aliases=[{'record_id':r['id'],'original':r['surface'],'canonical':adapter['surface'],'reason':'Exact legacy descriptive cap label migration; all substantive request controls unchanged'} for r in raw if r.get('surface')!=adapter['surface']]
            provenance=write(prefix+'parent-provenance.json',{'original_attempt_sources':sources,'selected_predictions':pred_spec,'source_snapshot':snapshot_spec,'surface_label_migrations':aliases,'historical_continuation':continuation,'historical_continuation_changed':mixed,'comparison_basis':'Observational matched model/request controls; historical continuation policy changed' if mixed else 'Matched model/request and continuation controls','known_failures_retained':sum(r['status']!='ok' for r in raw),'baseline_rerun_required':False,'raw_sources_modified':False,'reference_labels_read':False})
            config={'id':cid,'parent_baseline_id':parent_id,'role':'system','controller':controller_spec,'controller_timeout_seconds':next(iter(timeouts)),'continue_on_invalid_output':any(r['enabled'] for r in continuation),'controls':controls,'controls_sha256':ch,'baseline_instruction':write(prefix+'baseline.txt',policy,True),'parent_baseline':write(prefix+'parent.json',{'id':parent_id,'context_unit':'single_record','controls_sha256':ch,'baseline_instruction_sha256':digest(policy),'provenance':provenance}),'batch_membership':[[r['id']] for r in inputs],'conditions':{}}
            context=write(prefix+'historical-context.json',{'kind':'saved_attempt_context_v1','raw_attempts':history});usage=write(prefix+'historical-usage.json',{'kind':'saved_attempt_usage_v1','raw_attempts':history})
            for variant in ('P1','P2'):
                instruction=compose_instruction(policy,variant,role='system',parent_baseline_id=parent_id,root=root)['instruction'];evidence={'adapter':'openrouter_paid_v1','condition':variant,'parent_baseline_id':parent_id,'controls_sha256':ch,'instruction_sha256':digest(instruction),'inputs_sha256':inp_spec['sha256'],'schema_sha256':schema_spec['sha256'],'prospective_rendered_tokens':None,'unknown_reason':'Provider tokenizer and hidden rendering unavailable; client bytes are not a token bound','advertised_context':context,'historical_usage':usage,'requests':[]}
                for n,row in enumerate(inputs[:3]+inputs):
                    spec=write(prefix+variant+f'/request-{n:02}.json',expected_request('openrouter_paid_v1',instruction,[row],controls));evidence['requests'].append({'record_ids':[row['id']],'client_request':spec,'request_bytes':len((root/spec['file']).read_bytes())})
                config['conditions'][variant]={'instruction':write(prefix+variant+'/instruction.txt',instruction,True),'observational_evidence':write(prefix+variant+'/observational-evidence.json',evidence)}
            binding=write(prefix+'configuration.json',config);fragments.append({'id':cid,'parent_baseline_id':parent_id,'configuration':binding,'provenance':provenance,'historical_continuation_changed':mixed})
        except (ValueError,KeyError,TypeError) as error:
            blocked.append({'id':parent_id,'reason':str(error),'source_status':entry.get('status'),'baseline_rerun_required':False})
    schedule_spec=write('global-schedule-draft.json',{'order':order}) if order is not None else None
    index={'contract':'hosted-prompt-preparation-v1','status':'DRAFT_NOT_FROZEN','frozen_utc':None,'inference_performed':False,'reference_labels_read':False,'source_snapshot':snapshot_spec,'full_source_count':len(configs),'inputs':inp_spec,'schema':schema_spec,'prompt_bundle':bundle_spec,'controller':controller_spec,'full_roster':roster_spec,'full_source_inventory':inventory_spec,'global_schedule':schedule_spec,'configurations':fragments,'blocked_hosted_candidates':blocked,'other_adapter_ids':untouched,'required_before_execution':['Root merges all adapter fragments with the full reconciled roster and source inventory','Root freezes one global alternating schedule and immutable gate-v1 manifest with execution_journal','Reverify pinned controller and source hashes at freeze','Existing paid budget partitions allocated centrally within remaining $5 aggregate cap','Condition smoke must be run, inspected and bound by separate hash-pinned prompt-smoke-supplement-v1 before development','Unknown hosted tokens and historical continuation differences remain explicitly observational']}
    write('index.json',index);return index


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-snapshot',required=True);p.add_argument('--output-directory',required=True);p.add_argument('--roster');p.add_argument('--source-inventory');a=p.parse_args()
    result=build(ROOT,a.source_snapshot,a.output_directory,a.roster,a.source_inventory)
    print(json.dumps({'status':result['status'],'source_count':result['full_source_count'],'prepared':len(result['configurations']),'blocked_hosted':len(result['blocked_hosted_candidates']),'inference_performed':False}))
if __name__=='__main__':main()
