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
raw_attempts:{file,sha256},inspector (nonempty string), optional extractor.
extractor=openrouter_paid_v1 requires controls.adapter_controls using the paired
evaluator extract_controls contract, native system role, single-record context,
strict_json parsing, json_schema output and sampling:{temperature}.
Claude/Codex extractors require raw_predictions:{file,sha256}, controls.adapter_controls
from the corresponding strict evaluator extractor, runtime equal to saved cli_version,
and batch10 parent context (the inspected smoke itself contains exactly three records).

All paths are rooted and hash-bound. No references are read. This module verifies
STRUCTURE plus explicit OpenRouter/Claude/Codex raw smoke verification. Other smoke
surfaces and runtime token measurement remain unimplemented. It ALWAYS returns execution_allowed:false with concrete blockers.
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

def verify_openrouter_smoke(smoke,inputs,instruction,schema,controls,role,root):
    """Verify three original paid-adapter requests; no retry selection or repair."""
    from evaluate_prompt_variants import audit_requests,extract_controls
    from openrouter_benchmark import allowed_returned_models
    from datetime import timedelta
    import math
    raw=[json.loads(line) for line in bound(smoke['raw_attempts'],root).decode().splitlines() if line.strip()]
    selected={r['id']:r for r in inputs[:3]}
    if role!='system' or len(raw)!=3 or [r.get('id') for r in raw]!=list(selected) or any(r.get('phase')!='smoke' for r in raw):raise ValueError('Require exactly three original ordered OpenRouter smoke attempts')
    if 'adapter_controls' not in controls:raise ValueError('OpenRouter paired adapter controls required')
    expected=controls['adapter_controls']
    for row,inspected in zip(raw,smoke['records']):
        body=row.get('raw_response');endpoint=row['provider_endpoint'];request=row['request']
        if row.get('status') not in ('ok','invalid_output') or not isinstance(body,dict) or body.get('error'):raise ValueError('OpenRouter transport failure blocks smoke')
        choices=body.get('choices')
        if not isinstance(choices,list) or len(choices)!=1:raise ValueError('OpenRouter response choice ambiguity')
        choice=choices[0];message=choice.get('message',{})
        if choice.get('finish_reason')!='stop' or message.get('refusal') or message.get('tool_calls') or message.get('function_call') or choice.get('error'):raise ValueError('OpenRouter truncation/refusal/tool failure blocks smoke')
        if body.get('model') not in allowed_returned_models(row['requested_model'],endpoint) or body.get('provider')!=endpoint['provider_name']:raise ValueError('OpenRouter model/provider mismatch')
        for field,actual in [('returned_model',body.get('model')),('returned_provider',body.get('provider')),('finish_reason',choice.get('finish_reason'))]:
            if row.get(field)!=actual:raise ValueError('OpenRouter mirrored identity/finish mismatch')
        try:prediction=json.loads(message.get('content'))
        except (ValueError,TypeError):prediction=None
        status='ok' if valid(prediction) else 'invalid_output'
        if row.get('prediction')!=prediction or row.get('status')!=status or inspected.get('id')!=row['id'] or inspected.get('status')!=status or inspected.get('prediction')!=prediction:raise ValueError('Inspected smoke does not match strict raw output')
        if status=='invalid_output' and not (smoke.get('inspection')=='accepted_unchanged' and inspected.get('failure_class')=='intrinsic_schema' and inspected.get('accepted_unchanged') is True and inspected.get('inspection_reason')):raise ValueError('Intrinsic schema failure requires unchanged inspection acceptance')
        if row.get('reference_labels_read') is not False or row.get('schema_sha256')!=canonical(schema):raise ValueError('OpenRouter schema/reference isolation mismatch')
        required_format={'type':'json_schema','json_schema':{'name':'judgments','strict':True,'schema':schema}}
        if request.get('response_format')!=required_format:raise ValueError('OpenRouter output schema mismatch')
        mapped={'model':row['requested_model'],'effort':row['reasoning_effort'],'quantization':row['quantization'],'runtime':row.get('runtime'),'hardware':row.get('hardware'),'retry_policy':row['retry_policy'],'output_reserve_tokens':request['max_tokens'],'context_tokens':endpoint['context_length']}
        if any(controls.get(k)!=v for k,v in mapped.items()):raise ValueError('OpenRouter generic/adapter control mismatch')
        if controls.get('sampling')!={'temperature':request['temperature']} or controls.get('output_method')!='json_schema' or controls.get('parsing')!='strict_json':raise ValueError('OpenRouter sampling/output method mismatch')
        elapsed=row.get('elapsed_seconds')
        if isinstance(elapsed,bool) or not isinstance(elapsed,(int,float)) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('OpenRouter elapsed evidence invalid')
        started=stamp(row['started_utc'])
        if started<stamp(smoke['started_utc']) or started+timedelta(seconds=elapsed)>stamp(smoke['finished_utc']):raise ValueError('OpenRouter raw chronology outside inspected smoke interval')
    # Reuse the evaluator's body hashes, exact policy/input, provider controls,
    # mirrored billing, attempt identity and chronological ordering checks.
    normalized=[{**r,'phase':'development'} for r in raw]
    audit_requests(normalized,{r['id']:r for r in normalized},selected,instruction,expected,'first_chronological',[])
    return {'extractor':'openrouter_paid_v1','verified':True,'attempts':3,'intrinsic_invalid_outputs':sum(r['status']=='invalid_output' for r in raw),'raw_sha256':smoke['raw_attempts']['sha256']}


def verify_subscription_smoke(smoke,inputs,instruction,controls,role,root):
    """One fresh batch of three; original raw and exploded evidence both bound."""
    from evaluate_prompt_variants import audit_claude_batches,audit_codex_batches
    from datetime import timedelta
    import math
    raw=[json.loads(x) for x in bound(smoke['raw_attempts'],root).decode().splitlines() if x.strip()]
    predictions=[json.loads(x) for x in bound(smoke['raw_predictions'],root).decode().splitlines() if x.strip()]
    ids=[r['id'] for r in inputs[:3]];kind=smoke['extractor']
    if len(raw)!=1 or [r.get('id') for r in predictions]!=ids:raise ValueError('Subscription smoke requires exactly one retained batch and three ordered outputs')
    row=raw[0]
    if row.get('phase')!='smoke' or row.get('status') not in ('ok','invalid_output'):raise ValueError('Subscription smoke transport/isolation failure')
    if controls.get('model')!=row.get('requested_model') or controls.get('effort')!=row.get('effort') or controls.get('runtime')!=row.get('cli_version'):raise ValueError('Subscription generic model/effort/runtime controls mismatch')
    if kind=='claude_batch_v1':
        if role!='system' or row.get('controller_retries')!=0:raise ValueError('Claude smoke role/controller retry mismatch')
        audit=audit_claude_batches
        limitation='Historical full CLI command/environment and provider scaffold are not captured. Native internal retry count is not exposed.'
    elif kind=='codex_batch_v1':
        if role!='cli_combined_prompt' or row.get('recovered_transport_errors'):raise ValueError('Codex smoke role/recovered retry requires separate audit')
        audit=audit_codex_batches
        limitation='Requested model and saved CLI command are verified; returned model revision and hidden scaffold are not exposed.'
        # Codex exposes no finish reason proving an invalid JSON response was
        # not truncated. Retain it, but do not upgrade it to intrinsic failure.
        if row['status']=='invalid_output':raise ValueError('Codex invalid smoke lacks independently exposed non-truncation evidence')
    else:raise ValueError('Unknown subscription smoke extractor')
    adapter=controls.get('adapter_controls')
    if not isinstance(adapter,dict):raise ValueError('Subscription adapter controls required')
    audited=audit(raw,{r['id']:r for r in predictions},{r['id']:r for r in inputs[:3]},instruction,adapter,'first_chronological',[],evidence_phase='smoke',batch_size=3)
    for declared,actual in zip(smoke['records'],predictions):
        if any(declared.get(k)!=actual.get(k) for k in ('id','status','prediction')):raise ValueError('Subscription inspection differs from raw linked output')
        if actual['status']=='invalid_output' and not (smoke.get('inspection')=='accepted_unchanged' and declared.get('failure_class')=='intrinsic_schema' and declared.get('accepted_unchanged') is True and declared.get('inspection_reason')):raise ValueError('Intrinsic failure acceptance missing')
    elapsed=row.get('elapsed_seconds')
    if isinstance(elapsed,bool) or not isinstance(elapsed,(int,float)) or not math.isfinite(elapsed) or elapsed<0:raise ValueError('Invalid subscription smoke elapsed time')
    started=stamp(row['started_utc'])
    if started<stamp(smoke['started_utc']) or started+timedelta(seconds=elapsed)>stamp(smoke['finished_utc']):raise ValueError('Subscription raw attempt outside inspection interval')
    return {'extractor':kind,'verified':True,'attempts':len(audited),'records':3,'raw_sha256':smoke['raw_attempts']['sha256'],'predictions_sha256':smoke['raw_predictions']['sha256'],'limitations':limitation}


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
    checked=[];smoke_verifications=[];unsupported_smoke=False
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
            bound(smoke['raw_attempts'],root)
            if smoke.get('extractor')=='openrouter_paid_v1':
                if parent['context_unit']!='single_record':raise ValueError('OpenRouter paid smoke requires single-record context')
                smoke_verifications.append({'configuration':c['id'],'condition':variant,**verify_openrouter_smoke(smoke,inputs,instruction,json_bound(manifest['schema'],root),c['controls'],c['role'],root)})
            elif smoke.get('extractor') in ('claude_batch_v1','codex_batch_v1'):
                if parent['context_unit']!='batch10':raise ValueError('Subscription smoke must parent a batch10 baseline')
                canonical_schema=json.loads((Path(__file__).resolve().parents[1]/'schemas/judgments.schema.json').read_text())
                if json_bound(manifest['schema'],root)!=canonical_schema:raise ValueError('Subscription declared schema differs from strict batch schema source')
                smoke_verifications.append({'configuration':c['id'],'condition':variant,**verify_subscription_smoke(smoke,inputs,instruction,c['controls'],c['role'],root)})
            elif smoke.get('extractor') in (None,'declared_only'):unsupported_smoke=True
            else:raise ValueError('Unsupported smoke extractor')
            times[variant]=development
        first,second=expected[index]['conditions']
        if times[first]>=times[second]:raise ValueError('Development schedule contradicts counterbalance order')
        checked.append(c['id'])
    return {'contract':'prompt-execution-gates-v1','structural_checks_passed':True,'execution_allowed':False,'eligible_paired_comparison':False,'configurations':checked,'smoke_verifications':smoke_verifications,'blockers':['Runtime token measurement verification is not implemented; declarations and hash-bound raw files alone are insufficient.',*(['Runtime smoke request/response verification is unavailable for one or more declared-only conditions.'] if unsupported_smoke else []),'Actual launch-order enforcement and Git freeze/chronology verification are not implemented in this structural module.'],'reference_labels_read':False,'inference_performed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=validate(json.loads(a.manifest.read_text()),a.root);result['manifest_sha256']=sha(a.manifest.read_bytes())
    with a.output.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps({'structural_checks_passed':True,'execution_allowed':False}))
if __name__=='__main__':main()
