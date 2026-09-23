#!/usr/bin/env python3
"""Offline structural validator for prompt-execution-gates-v1.

Top-level: contract, frozen_utc, inputs/schema/prompt_bundle/roster/schedule/source_inventory
(each a relative {file,sha256}), configurations (nonempty list).
Inventory: {entries:[{id, disposition:completed|blocked|excluded|executable,
reason}]} accounts for every roster entry. Roster: {entries:[{id,parent_baseline_id,
state:scheduled|blocked|excluded,reason}]}. No executable baseline may remain.
Schedule: {order:[{id,conditions:[P1,P2]|[P2,P1]}]}, alternating by roster order.
Configuration: id,parent_baseline_id,role,baseline_instruction:{file,sha256},
parent_baseline:{file,sha256},controls,controls_sha256,batch_membership,conditions.
Controls must declare model, model_revision, quantization, runtime, hardware, effort,
sampling, output_method, parsing, retry_policy, context_tokens, output_reserve_tokens.
Unknown values remain declarations, never verified runtime evidence.
Parent artifact: {id,context_unit,controls_sha256,baseline_instruction_sha256}.
Conditions P0/P1/P2: instruction:{file,sha256}, token_evidence:{file,sha256},
smoke_evidence:{file,sha256}, development_not_before (UTC timestamp).
Token artifact: condition, parent_baseline_id, controls_sha256,instruction_sha256,
inputs_sha256,schema_sha256,method:exact_rendered|conservative_bound,
wrapper_coverage:complete,measured_utc,tokenizer:{file,sha256},
requests:[{record_ids,input_tokens,output_reserve_tokens,context_tokens}],
raw_measurements:{file,sha256},bound_basis (required for conservative_bound).
Smoke artifact: same condition/identity/hash bindings, started_utc,finished_utc,
inspected_utc,inspection:passed|accepted_unchanged,records:[{id,status,prediction}],
Intrinsic-invalid records additionally require failure_class:intrinsic_schema,
accepted_unchanged:true and nonempty inspection_reason. Transport, identity and
truncation failures block. Historical P0 may predate the new freeze; P1/P2 may not.
raw_attempts:{file,sha256},inspector (nonempty string).

All paths are rooted and hash-bound. No references are read. This module verifies
STRUCTURE only: runtime measurement/smoke extractors are intentionally not yet
implemented. It ALWAYS returns execution_allowed:false with concrete blockers.
Hashes bind supplied bytes. Git freeze records and actual chronology are the experimental record; this structural module does not enforce controller launch order.
Controllers must not treat structural validity as execution permission.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from development_benchmark import valid
from frozen_prompt_variants import compose_instruction,MANIFEST_SHA256


def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return sha(json.dumps(value,sort_keys=True).encode())
def stamp(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.tzinfo is None:raise ValueError()
        return result
    except (ValueError,AttributeError,TypeError):raise ValueError('Timezone-aware timestamp required') from None

def bound(spec,root):
    if not isinstance(spec,dict) or set(spec)!={'file','sha256'}:raise ValueError('Exact file/hash source binding required')
    path=(root/spec['file']).resolve();path.relative_to(root.resolve())
    # This gate never needs evaluation references, even when supplied maliciously.
    if any(x in path.name.lower() for x in ('reference','proposed_labels','pairs.json')):raise ValueError('Reference source forbidden')
    raw=path.read_bytes()
    if sha(raw)!=spec['sha256']:raise ValueError('Source hash mismatch: '+spec['file'])
    return raw

def json_bound(spec,root):return json.loads(bound(spec,root))
def nonnegative(value):return type(value) is int and value>=0

def validate(manifest,root):
    root=Path(root)
    if manifest.get('contract')!='prompt-execution-gates-v1':raise ValueError('Unknown execution gate contract')
    frozen=stamp(manifest['frozen_utc'])
    inputs=[json.loads(x) for x in bound(manifest['inputs'],root).decode().splitlines() if x.strip()]
    ids=[x.get('id') for x in inputs]
    if ids!=[f'DEV-{i:03}' for i in range(1,61)] or any(set(x)!={'id','feedback'} or not isinstance(x['feedback'],str) for x in inputs):raise ValueError('Exact ordered input-only development60 required')
    json_bound(manifest['schema'],root)
    if manifest['prompt_bundle']['sha256']!=MANIFEST_SHA256:raise ValueError('Frozen prompt bundle mismatch')
    bound(manifest['prompt_bundle'],root)
    roster=json_bound(manifest['roster'],root)['entries'];inventory=json_bound(manifest['source_inventory'],root)['entries']
    rid=[r['id'] for r in roster];iid=[r['id'] for r in inventory]
    if not rid or len(set(rid))!=len(rid) or len(set(iid))!=len(iid) or set(rid)!=set(iid):raise ValueError('Complete unique source inventory/roster reconciliation required')
    for item in inventory:
        if item.get('disposition') not in ('completed','blocked','excluded') or not item.get('reason'):raise ValueError('Executable or unexplained baseline work remains')
    for item in roster:
        if item.get('state') not in ('scheduled','blocked','excluded') or not item.get('reason'):raise ValueError('Explicit roster disposition required')
        original=next(x for x in inventory if x['id']==item['id'])
        if item['state']=='scheduled' and original['disposition']!='completed':raise ValueError('Blocked/excluded baseline cannot be scheduled')
    scheduled=[r for r in roster if r['state']=='scheduled'];configs=manifest['configurations']
    if not scheduled or [c['id'] for c in configs]!=[r['id'] for r in scheduled]:raise ValueError('Configuration order differs from frozen roster')
    schedule=json_bound(manifest['schedule'],root)['order']
    expected=[{'id':r['id'],'conditions':['P1','P2'] if i%2==0 else ['P2','P1']} for i,r in enumerate(scheduled)]
    if schedule!=expected:raise ValueError('Fixed counterbalanced schedule mismatch')
    checked=[]
    for index,c in enumerate(configs):
        parent=json_bound(c['parent_baseline'],root);baseline=bound(c['baseline_instruction'],root).decode()
        if c['parent_baseline_id']!=scheduled[index]['parent_baseline_id'] or parent['id']!=c['parent_baseline_id']:raise ValueError('Parent baseline identity mismatch')
        required_controls={'model','model_revision','quantization','runtime','hardware','effort','sampling','output_method','parsing','retry_policy','context_tokens','output_reserve_tokens'}
        if not required_controls.issubset(c['controls']):raise ValueError('Complete paired control declarations required')
        if canonical(c['controls'])!=c['controls_sha256'] or parent['controls_sha256']!=c['controls_sha256'] or parent['baseline_instruction_sha256']!=sha(baseline.encode()):raise ValueError('Parent controls/instruction mismatch')
        size=10 if parent['context_unit']=='batch10' else 1 if parent['context_unit']=='single_record' else 0
        if not size:raise ValueError('Unsupported context unit')
        groups=[ids[n:n+size] for n in range(0,60,size)]
        if c['batch_membership']!=groups or set(c['conditions'])!={'P0','P1','P2'}:raise ValueError('Condition membership mismatch')
        times={}
        for variant,condition in c['conditions'].items():
            instruction=compose_instruction(baseline,variant,role=c['role'],parent_baseline_id=c['parent_baseline_id'],root=root)['instruction']
            if bound(condition['instruction'],root).decode()!=instruction:raise ValueError('Exact frozen instruction composition mismatch')
            token=json_bound(condition['token_evidence'],root);smoke=json_bound(condition['smoke_evidence'],root)
            bindings={'condition':variant,'parent_baseline_id':c['parent_baseline_id'],'controls_sha256':c['controls_sha256'],'instruction_sha256':sha(instruction.encode()),'inputs_sha256':manifest['inputs']['sha256'],'schema_sha256':manifest['schema']['sha256']}
            if any(e.get(k)!=v for e in (token,smoke) for k,v in bindings.items()):raise ValueError('Condition evidence binding mismatch')
            if token.get('method') not in ('exact_rendered','conservative_bound') or token.get('wrapper_coverage')!='complete':raise ValueError('Opaque/estimated token coverage cannot establish fit')
            if token['method']=='conservative_bound' and not token.get('bound_basis'):raise ValueError('Conservative bound needs a justified basis')
            bound(token['tokenizer'],root);bound(token['raw_measurements'],root)
            measurements=token['requests']
            if [x['record_ids'] for x in measurements]!=groups:raise ValueError('Token evidence must cover every request')
            for x in measurements:
                if not all(nonnegative(x[k]) for k in ('input_tokens','output_reserve_tokens','context_tokens')) or x['output_reserve_tokens']<1 or x['input_tokens']+x['output_reserve_tokens']>x['context_tokens']:raise ValueError('Insufficient context or invalid token evidence')
                if x['output_reserve_tokens']!=c['controls']['output_reserve_tokens'] or x['context_tokens']!=c['controls']['context_tokens']:raise ValueError('Condition token budgets differ from paired controls')
            started=stamp(smoke['started_utc']);finished=stamp(smoke['finished_utc']);inspected=stamp(smoke['inspected_utc']);development=stamp(condition['development_not_before']);measured=stamp(token['measured_utc'])
            if not measured<=started<=finished<=inspected<development:raise ValueError('Token/smoke inspection must precede development')
            if variant!='P0' and measured<frozen:raise ValueError('New condition evidence must follow the freeze')
            records=smoke['records']
            if [r.get('id') for r in records]!=ids[:3] or smoke.get('inspection') not in ('passed','accepted_unchanged') or not smoke.get('inspector'):raise ValueError('Three explicitly inspected smoke records required')
            for record in records:
                if record.get('status')=='ok' and valid(record.get('prediction')):continue
                if not (record.get('status')=='invalid_output' and record.get('failure_class')=='intrinsic_schema' and record.get('accepted_unchanged') is True and record.get('inspection_reason') and smoke.get('inspection')=='accepted_unchanged'):
                    raise ValueError('Smoke transport/identity/truncation or unaccepted output failure blocks development')
            bound(smoke['raw_attempts'],root);times[variant]=development
        first,second=expected[index]['conditions']
        if times[first]>=times[second]:raise ValueError('Development schedule contradicts counterbalance order')
        checked.append(c['id'])
    return {'contract':'prompt-execution-gates-v1','structural_checks_passed':True,'execution_allowed':False,'eligible_paired_comparison':False,'configurations':checked,'blockers':['Runtime token measurement verification is not implemented; declarations and hash-bound raw files alone are insufficient.','Runtime smoke request/response, exact controls and inspection verification is not implemented.','Actual launch-order enforcement and Git freeze/chronology verification are not implemented in this structural module.'],'reference_labels_read':False,'inference_performed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=validate(json.loads(a.manifest.read_text()),a.root);result['manifest_sha256']=sha(a.manifest.read_bytes())
    with a.output.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps({'structural_checks_passed':True,'execution_allowed':False}))
if __name__=='__main__':main()
