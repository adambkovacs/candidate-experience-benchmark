#!/usr/bin/env python3
"""Offline paired scoring for source-bound hosted continuation rows.

This does not synthesize missing timestamps or retry identities. Continuation
chronology is the append-only journal order and is reported as such.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parent if (HERE.parent/'scripts'/'evaluate_prompt_variants.py').exists() else Path.cwd()
sys.path.insert(0,str(REPO/'scripts'))
from development_benchmark import score, valid
from frozen_prompt_variants import compose_instruction
from evaluate_prompt_variants import (canonical_hash, extract_controls, compare,
                                       telemetry, indexed, rows_from)
from openrouter_benchmark import allowed_returned_models
from build_development_report import summarize_costs

AUDIT_DIR='results/prompt-comparison-v1-2026-09-24/paired-reports/hosted-remaining-audit-v1'
IDS=('openrouter-paid-qwen3.8-27b-medium','openrouter-paid-qwen3.8-27b-xhigh',
     'openrouter-paid-qwen36-35b-a3b-off','openrouter-paid-gemma4-26b-a4b-on',
     'openrouter-paid-deepseek-v41-flash-off','openrouter-paid-deepseek-v41-flash-low',
     'openrouter-paid-deepseek-v41-flash-high')
EXPECTED=[f'DEV-{n:03}' for n in range(1,61)]

def sha(raw):return hashlib.sha256(raw).hexdigest()
def read_bound(root,spec):
    p=(root/spec['file']).resolve();p.relative_to(root.resolve())
    raw=p.read_bytes()
    if sha(raw)!=spec['sha256']:raise ValueError('Source hash mismatch: '+spec['file'])
    return raw

def required_bound(root,path):
    p=(root/path).resolve();p.relative_to(root.resolve())
    raw=p.read_bytes();return {'file':str(p.relative_to(root.resolve())),'sha256':sha(raw)}

def json_lines(raw):
    if raw and not raw.endswith(b'\n'):raise ValueError('Incomplete JSONL terminal line')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]

def verify_row(row,rid,condition,instruction,controls,feedback,*,suffix=False,journal_hash=None):
    if row.get('id')!=rid or row.get('reference_labels_read') is not False:raise ValueError('Record identity/reference boundary mismatch')
    phase='development_suffix' if suffix else 'development'
    if row.get('phase')!=phase or (row.get('parent_baseline_id') is not None and row.get('parent_baseline_id')!=controls['parent_baseline_id']):raise ValueError('Record phase/baseline mismatch')
    aid=row.get('attempt_id')
    if not isinstance(aid,str) or not aid:raise ValueError('Missing attempt identity')
    request=row.get('request');endpoint=row.get('provider_endpoint')
    if not isinstance(request,dict) or not isinstance(endpoint,dict):raise ValueError('Missing raw request/route')
    messages=request.get('messages')
    if not isinstance(messages,list) or len(messages)!=2 or messages[0]!={'role':'system','content':instruction}:raise ValueError('Frozen instruction mismatch')
    if set(messages[1])!={'role','content'} or messages[1]['role']!='user' or json.loads(messages[1]['content'])!={'feedback':feedback}:raise ValueError('Frozen feedback mismatch')
    if {k:v for k,v in request.items() if k!='messages'}!=controls['adapter_controls']['request_controls']:raise ValueError('Request controls mismatch')
    if extract_controls(row)!=controls['adapter_controls']:raise ValueError('Adapter controls mismatch')
    if row['requested_model']!=request['model'] or endpoint.get('model_id')!=request['model'] or row['quantization']!=endpoint.get('quantization'):raise ValueError('Route/model/quantization mismatch')
    if request['provider']['only']!=[endpoint['tag']] or request['provider'].get('allow_fallbacks') is not False:raise ValueError('Fallback/provider mismatch')
    request_hash=canonical_hash(request)
    if row.get('request_sha256') is not None and row['request_sha256']!=request_hash:raise ValueError('Saved request hash mismatch')
    if journal_hash is not None and journal_hash!=request_hash:raise ValueError('Journal request hash mismatch')
    if row.get('input_sha256') is not None and row['input_sha256']!=sha(feedback.encode()):raise ValueError('Input hash mismatch')
    if row.get('policy_sha256') is not None and row['policy_sha256']!=sha(instruction.encode()):raise ValueError('Policy hash mismatch')
    schema=request['response_format']['json_schema']['schema']
    if row.get('schema_sha256') is not None and row['schema_sha256']!=sha(json.dumps(schema,sort_keys=True).encode()):raise ValueError('Schema hash mismatch')
    body=row.get('raw_response') or {};usage=body.get('usage') if isinstance(body,dict) else None
    if 'usage' in row and row['usage']!=usage:
        if not (row.get('status')!='ok' and row.get('cost_unknown') is True and usage is None and row['usage']=={}):raise ValueError('Usage mirror mismatch')
    raw_cost=usage.get('cost') if isinstance(usage,dict) else None
    if row.get('cost_unknown') is False and row.get('observed_cost_usd') is None:raise ValueError('Known cost without value')
    if row.get('observed_cost_usd') is not None:
        from decimal import Decimal
        if raw_cost is None or Decimal(str(raw_cost))!=Decimal(str(row['observed_cost_usd'])):raise ValueError('Cost mirror mismatch')
    if row.get('cost_unknown') is True and raw_cost is not None:raise ValueError('Unknown cost with raw cost')
    if row.get('status')=='ok':
        choice=(body.get('choices') or [{}])[0];message=choice.get('message') or {}
        try:parsed=json.loads(message.get('content'))
        except (ValueError,TypeError):parsed=None
        if body.get('model') not in allowed_returned_models(row['requested_model'],endpoint) or body.get('provider')!=endpoint['provider_name'] or choice.get('finish_reason')!='stop' or message.get('refusal') or message.get('tool_calls') or parsed!=row.get('prediction') or not valid(parsed):raise ValueError('Unsupported successful parse')
    elif row.get('status') not in ('invalid_output','service_error','prompt_admission_failure'):
        raise ValueError('Unknown terminal status')
    return request_hash

def verify_v2_v3(root,path,rows,config,condition):
    folder=Path(path).parent
    evidence=[]
    for name in ('frozen-manifest.json','root-review.json','attempts.jsonl','reconciliation-v1.json'):
        evidence.append(required_bound(root,str(folder/name)))
    manifest=json.loads((root/folder/'frozen-manifest.json').read_text())
    recon=json.loads((root/folder/'reconciliation-v1.json').read_text())
    if manifest['configuration_id']!=config or manifest['condition']!=condition or manifest['remaining_ids'][:len(rows)]!=[r['id'] for r in rows] or manifest['remaining_ids'][len(rows):]!=recon['remaining_never_sent_ids']:raise ValueError('Continuation manifest identity/order mismatch')
    for key,name in (('manifest','frozen-manifest.json'),('review','root-review.json'),('new_journal','attempts.jsonl'),('new_output','development.jsonl')):
        spec=recon[key]
        if spec!=required_bound(root,str(folder/name)):raise ValueError('Continuation reconciliation binding mismatch: '+key)
    if recon['configuration_id']!=config or recon['condition']!=condition or (recon['terminal_status'],recon['status']) not in (('completed_remaining_attempts','full_suffix_attempted'),('stopped','partial_stopped')) or recon['new_attempted_count']!=len(rows) or recon['combined_attempted_count']!=recon['historical_count']+len(rows):raise ValueError('Continuation not terminal/accounted')
    journal=json_lines(read_bound(root,recon['new_journal']))
    if len(journal)!=2*len(rows)+2 or journal[0].get('event')!='claimed' or journal[-1].get('event')!='finished':raise ValueError('Continuation journal incomplete')
    claim=journal[0]
    if claim.get('configuration_id')!=config or claim.get('condition')!=condition or claim.get('remaining_ids')!=manifest['remaining_ids'] or claim.get('manifest_sha256')!=recon['manifest']['sha256'] or claim.get('review_sha256')!=recon['review']['sha256']:raise ValueError('Continuation claim mismatch')
    if journal[-1].get('status')!=recon['terminal_status'] or journal[-1].get('attempted_records')!=len(rows) or journal[-1].get('output')!=recon['new_output']:raise ValueError('Continuation terminal mismatch')
    hashes={}
    for i,row in enumerate(rows):
        start,finish=journal[1+2*i:3+2*i]
        if start.get('event')!='request_started' or finish.get('event')!='request_finished' or start.get('id')!=row['id'] or finish.get('id')!=row['id'] or start.get('attempt_id')!=row['attempt_id'] or finish.get('attempt_id')!=row['attempt_id'] or finish.get('status')!=row.get('status'):raise ValueError('Continuation event/order/status mismatch')
        hashes[row['id']]=start.get('request_sha256')
    # Frozen per-position request files are separately pinned by the manifest.
    if len(manifest['request_bindings'])!=len(manifest['remaining_ids']):raise ValueError('Continuation request binding count')
    for spec in manifest['request_bindings']:
        read_bound(root,spec);evidence.append(spec)
    for spec,row in zip(manifest['request_bindings'],rows):
        req=json.loads(read_bound(root,spec))
        if req.get('request')!=row.get('request') or req.get('adapter_controls') is None:raise ValueError('Pinned continuation request mismatch')
    for spec in recon.get('historical_outputs',[]):evidence.append(spec);read_bound(root,spec)
    for key in ('original_manifest','smoke','smoke_supplement','observational_evidence','schema','inputs','instruction'):
        spec=manifest.get(key)
        if isinstance(spec,dict) and 'file' in spec:evidence.append(spec);read_bound(root,spec)
    if 'not preserved' not in manifest.get('policy',{}).get('order_limitation',''):
        raise ValueError('Continuation timing limitation not declared')
    return hashes,evidence,recon

def verify_qwen_suffix(root,path,rows):
    folder=Path(path).parent;jpath=path+'.attempts.jsonl';plan=str(folder/'off-p2-dev054-060-suffix-plan.json')
    evidence=[required_bound(root,jpath),required_bound(root,plan)]
    journal=json_lines(read_bound(root,evidence[0]))
    if len(journal)!=2*len(rows)+1 or journal[-1].get('event')!='terminal' or journal[-1].get('completed') is not True or journal[-1].get('attempted_records')!=len(rows):raise ValueError('Qwen suffix journal incomplete')
    if [r['id'] for r in rows]!=EXPECTED[-7:]:raise ValueError('Qwen suffix IDs/order mismatch')
    hashes={}
    for i,row in enumerate(rows):
        start,finish=journal[2*i:2*i+2]
        if start.get('event')!='started' or finish.get('event')!='finished' or start.get('id')!=row['id'] or finish.get('id')!=row['id'] or start.get('attempt_id')!=row['attempt_id'] or finish.get('attempt_id')!=row['attempt_id'] or finish.get('status')!=row['status'] or start.get('request')!=row.get('request') or start.get('request_sha256')!=row.get('request_sha256') or start.get('started_utc')!=row.get('started_utc'):raise ValueError('Qwen suffix attempt lineage mismatch')
        hashes[row['id']]=start['request_sha256']
    plan_hash=evidence[1]['sha256']
    if journal[-1].get('plan_sha256')!=plan_hash or any(r.get('prompt_recovery',{}).get('plan_sha256')!=plan_hash for r in rows):raise ValueError('Qwen suffix plan mismatch')
    return hashes,evidence

def evaluate_one(root,config):
    root=Path(root).resolve()
    if config not in IDS:raise ValueError('Configuration outside reviewed roster')
    index=json.loads((root/AUDIT_DIR/'index.json').read_text())
    entry=next((x for x in index['configuration_audits'] if x['configuration_id']==config),None)
    if index.get('configuration_count')!=7 or entry is None:raise ValueError('Audit index mismatch')
    audit=json.loads(read_bound(root,{'file':str(Path(AUDIT_DIR)/entry['audit']['file']),'sha256':entry['audit']['sha256']}))
    if audit['configuration_id']!=config or audit['contract']!='hosted-remaining-pair-audit-v1':raise ValueError('Audit identity mismatch')
    for spec in audit['source_bindings']:
        if spec['file']!='public-site/data.json':read_bound(root,spec)
    # v1 used the generated public export only to discover immutable raw paths.
    # Those paths and their hashes are already frozen in the audit index; do not
    # make future offline evaluation depend on an unrelated site regeneration.
    cfg=json.loads((root/f'results/hosted-prompt-preparation-2026-09-24/{config}/configuration.json').read_text())
    controls=cfg['controls']['adapter_controls'];baseline=(root/cfg['baseline_instruction']['file']).read_text()
    if sha(baseline.encode())!=cfg['baseline_instruction']['sha256']:raise ValueError('Frozen baseline changed')
    inputs=indexed(json_lines(read_bound(root,next(x for x in audit['source_bindings'] if x['file']=='data/pilot/inputs.jsonl'))),set(EXPECTED),True)
    if list(inputs)!=EXPECTED or any(set(x)!={'id','feedback'} for x in inputs.values()):raise ValueError('Frozen input order/schema mismatch')
    all_rows={};extra=[];limitations=[];protocol_gaps=[]
    for condition in ('P0','P1','P2'):
        info=audit['conditions'][condition];instruction=compose_instruction(baseline,condition,role='system',parent_baseline_id=config,root=root)['instruction']
        if info['instruction_sha256']!=sha(instruction.encode()):raise ValueError('Audited instruction changed')
        rows=[];previous=[]
        for spec in info['source_bindings']:
            block=json_lines(read_bound(root,spec));path=spec['file'];hashes={};is_suffix=path.endswith('off-p2-dev054-060-suffix.jsonl')
            if 'hosted-unattempted-continuation-v' in path:
                hashes,bound,recon=verify_v2_v3(root,path,block,config,condition);extra+=bound
                if [r['id'] for r in block]!=EXPECTED[len(rows):len(rows)+len(block)]:raise ValueError('Continuation input order mismatch')
                if [r['id'] for r in rows]!=[x['id'] for spec2 in recon['historical_outputs'] for x in json_lines(read_bound(root,spec2))]:raise ValueError('Continuation predecessor mismatch')
                limitations.append('Continuation per-request timestamps unavailable; verified append-only journal order used, without synthesized timestamps.')
                protocol_gaps.append({'condition':condition,'source':path,'control':'counterbalanced_execution_schedule','finding':'Later continuation; original condition timing/order not preserved.'})
            elif is_suffix:
                if config!='openrouter-paid-qwen36-35b-a3b-off' or condition!='P2':raise ValueError('Unexpected Qwen suffix')
                hashes,bound=verify_qwen_suffix(root,path,block);extra+=bound
                if any(r.get('prompt_recovery',{}).get('original_timing_preserved') is not False for r in block):raise ValueError('Qwen timing limitation missing')
                limitations.append('Qwen P2 development_suffix phase is source-bound never-sent continuation; original timing not preserved.')
                protocol_gaps.append({'condition':condition,'source':path,'control':'counterbalanced_execution_schedule','finding':'Later never-sent suffix; original condition timing/order not preserved.'})
            for row in block:
                if row['id'] not in EXPECTED or row['id'] in previous:raise ValueError('Duplicate/unknown record ID')
                previous.append(row['id'])
                verify_row(row,row['id'],condition,instruction,{'adapter_controls':controls,'parent_baseline_id':config},inputs[row['id']]['feedback'],suffix=is_suffix,journal_hash=hashes.get(row['id']))
            rows+=block
        if [r['id'] for r in rows]!=EXPECTED or len({r['attempt_id'] for r in rows})!=60:raise ValueError('Not exactly ordered 60 independent attempts')
        if Counter(r['status'] for r in rows)!=Counter(info['status_counts']):raise ValueError('Audit status changed')
        for spec in info['lifecycle_bindings']:read_bound(root,spec)
        all_rows[condition]={r['id']:r for r in rows}
    if not protocol_gaps:raise ValueError('Full protocol admission is not implemented for a no-suffix path')
    # Labels are opened only after every raw request and lifecycle check above.
    refs_spec=required_bound(root,'data/pilot/proposed_labels.jsonl');pairs_spec=required_bound(root,'data/pilot/pairs.json')
    refs=indexed(json_lines(read_bound(root,refs_spec)),set(EXPECTED),True)
    if any(r.get('split')!='development' or not valid(r.get('proposed_labels')) for r in refs.values()):raise ValueError('Reference schema mismatch')
    pairs=json.loads(read_bound(root,pairs_spec))
    helper_paths=('scripts/evaluate_prompt_variants.py','scripts/development_benchmark.py','scripts/frozen_prompt_variants.py','scripts/openrouter_benchmark.py','scripts/build_development_report.py')
    result={'contract':'hosted-continuation-pairs-v1','configuration_id':config,'denominator':60,
            'request_controls_verified':True,'raw_source_hashes_verified':True,'protocol_source_hashes_verified':True,
            'protocol_controls_verified':False,'smoke_inspection_gates_semantically_verified':False,
            'continuation_lifecycle_verified':True,
            'offline_pairing_supported':True,'eligible_paired_comparison':False,
            'full_protocol_eligibility':'blocked_by_observed_schedule_change' if protocol_gaps else 'additional_gate_review_required',
            'protocol_gaps':protocol_gaps,'helper_source_bindings':[required_bound(root,p) for p in helper_paths],
            'adapter_source_sha256':sha(Path(__file__).read_bytes()),
            'audit_index_sha256':sha((root/AUDIT_DIR/'index.json').read_bytes()),
            'discovery_binding_excluded_from_runtime_verification':'public-site/data.json',
            'reference_labels_read_offline':True,'reference_status':'Provisional AI-reviewed development references; not held-out human truth',
            'audit':{'file':str(Path(AUDIT_DIR)/entry['audit']['file']),'sha256':entry['audit']['sha256']},
            'references':refs_spec,'pairs':pairs_spec,'additional_evidence':sorted({(x['file'],x['sha256']) for x in extra}),
            'conditions':{},'comparisons':{},'limitations':sorted(set(limitations+['Client request duration is observational and suffix timing differs from the original schedule; it is not pure model inference latency.']))}
    for c in ('P0','P1','P2'):
        rows=list(all_rows[c].values());evaluation=score(list(refs.values()),rows,pairs)
        result['conditions'][c]={'evaluation':evaluation,'valid_count':sum(r['status']=='ok' for r in rows),
            'status_counts':dict(sorted(Counter(r['status'] for r in rows).items())),
            'all_four_correct':sum(r['status']=='ok' and r['prediction']==refs[r['id']]['proposed_labels'] for r in rows),
            'telemetry':telemetry(rows),'cost':summarize_costs(rows,[spec['file'] for spec in audit['conditions'][c]['source_bindings']]),'sources':audit['conditions'][c]['source_bindings']}
    for a,b in (('P0','P1'),('P0','P2'),('P1','P2')):
        result['comparisons'][a+'_to_'+b]=compare(all_rows[a],all_rows[b],refs)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=REPO);parser.add_argument('--configuration',choices=IDS,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();data=(json.dumps(evaluate_one(args.root,args.configuration),indent=2,ensure_ascii=False)+'\n').encode()
    if args.check:
        if args.output.read_bytes()!=data:raise SystemExit('Evaluation differs from source-bound recomputation')
    else:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(data)
if __name__=='__main__':main()
