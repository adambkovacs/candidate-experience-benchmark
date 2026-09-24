"""Observational admission for opaque hosted wrappers; no inference or label reads.

Uses gate-v1 roster/control bindings. A condition has observational_evidence:
{adapter, advertised_context:{file,sha256}, historical_usage:{file,sha256},
 prospective_rendered_tokens:null, unknown_reason, requests:[{record_ids,
 client_request:{file,sha256},request_bytes}]} in a hash-bound JSON file.
Client request bindings cover smoke first, then each complete development group.
Each file is exactly {adapter_controls,request}, reconstructed by adapter builders.
Context source contracts: saved_attempt_context_v1 {raw_attempts}, or
codex_catalogue_v1 {catalogue,raw_catalogue}; usage source is
saved_attempt_usage_v1 {raw_attempts}. Every source is file/hash bound.
Request files contain exact UTF-8 serialized outbound payloads; they must contain
complete instruction and feedback values (JSON objects or combined text).
An optional manifest_scope lists exactly the configuration IDs in this shard,
in global roster order. Full roster/inventory/schedule bindings remain mandatory;
shards never invent a subset schedule or omit source dispositions.
Admission is one input to controller launch; the schedule journal enforces order.
"""
import json
from pathlib import Path
import prompt_execution_gates as g
from frozen_prompt_variants import compose_instruction

ADAPTERS=frozenset(('openrouter_paid_v1','claude_batch_v1','codex_batch_v1'))
REQUIRED={'model','model_revision','quantization','runtime','hardware','effort',
          'sampling','output_method','parsing','retry_policy','context_tokens','output_reserve_tokens'}


def _attempts(spec,root,adapter,controls):
    from evaluate_prompt_variants import extract_controls,extract_claude_controls,extract_codex_controls
    rows=[json.loads(x) for x in g.bound(spec,root).decode().splitlines() if x.strip()]
    extractor={'openrouter_paid_v1':extract_controls,'claude_batch_v1':extract_claude_controls,'codex_batch_v1':extract_codex_controls}[adapter]
    if not rows:raise ValueError('Underlying historical attempts required')
    for row in rows:
        if extractor(row)!=controls['adapter_controls']:raise ValueError('Historical raw controls differ')
        effort=row.get('reasoning_effort') if adapter=='openrouter_paid_v1' else row.get('effort')
        runtime=row.get('runtime') if adapter=='openrouter_paid_v1' else row.get('cli_version')
        if row.get('requested_model')!=controls['model'] or effort!=controls['effort'] or runtime!=controls['runtime']:raise ValueError('Generic controls differ from raw adapter controls')
    return rows


def _usage(row,adapter):
    if adapter=='openrouter_paid_v1':
        usage=row['raw_response'].get('usage',{})
        return {'input_tokens':usage.get('prompt_tokens'),'output_tokens':usage.get('completion_tokens')}
    kind='result' if adapter=='claude_batch_v1' else 'turn.completed'
    events=[e for e in row['raw_events'] if e.get('type')==kind]
    if len(events)!=1:raise ValueError('Historical usage event ambiguity')
    usage=events[0].get('usage',{})
    if usage!=row.get('usage'):raise ValueError('Historical mirrored usage mismatch')
    value=usage.get('input_tokens')
    if adapter=='claude_batch_v1':
        parts=[usage.get(k) for k in ('input_tokens','cache_creation_input_tokens','cache_read_input_tokens')]
        value=sum(parts) if all(g.nonnegative(n) for n in parts) else None
    return {'input_tokens':value,'output_tokens':usage.get('output_tokens')}


def _context(evidence,root,adapter,controls):
    kind=evidence.get('kind')
    if adapter=='codex_batch_v1' and kind=='codex_catalogue_v1':
        catalogue=g.json_bound(evidence['catalogue'],root)
        raw=g.bound(evidence['raw_catalogue'],root)
        if catalogue.get('kind')!='codex_context_catalogue_v1' or catalogue.get('source')!='official_codex_cli_models_cache' or catalogue.get('source_sha256')!=g.sha(raw):raise ValueError('Underlying Codex catalogue binding mismatch')
        original=json.loads(raw)
        rows=[r for r in original['models'] if r.get('slug')==controls['model']]
        if len(rows)!=1:raise ValueError('Catalogue model ambiguity')
        row=rows[0];limit=row.get('context_window');percent=row.get('effective_context_window_percent')
        if not g.nonnegative(limit) or not g.nonnegative(percent) or not 0<percent<=100:raise ValueError('Catalogue context unavailable')
        return limit*percent//100
    if kind!='saved_attempt_context_v1' or adapter=='codex_batch_v1':raise ValueError('Unsupported context source contract')
    rows=_attempts(evidence['raw_attempts'],root,adapter,controls);limits=[]
    for row in rows:
        if adapter=='openrouter_paid_v1':limits.append(row['provider_endpoint']['context_length'])
        else:
            events=[e for e in row['raw_events'] if e.get('type')=='result']
            if len(events)!=1 or events[0].get('modelUsage')!=row.get('model_usage'):raise ValueError('Historical context event mismatch')
            limits.append(events[0]['modelUsage'][controls['model']]['contextWindow'])
    if len(set(limits))!=1 or not g.nonnegative(limits[0]):raise ValueError('Historical context mismatch')
    return limits[0]


def expected_request(adapter,instruction,rows,controls):
    """Exact client envelope, including visible execution controls outside payload."""
    if adapter=='claude_batch_v1':
        from claude_batch_benchmark import batch_schema
        request={'system':instruction,'input':{'records':rows},'schema':batch_schema([r['id'] for r in rows])}
    elif adapter=='codex_batch_v1':
        from codex_batch_benchmark import batch_schema
        request={'prompt':instruction+'\n'+json.dumps({'records':rows}),'output_schema':batch_schema(rows)}
    elif adapter=='openrouter_paid_v1':
        if len(rows)!=1:raise ValueError('OpenRouter requires one record')
        request={**controls['adapter_controls']['request_controls'],'messages':[{'role':'system','content':instruction},{'role':'user','content':json.dumps({'feedback':rows[0]['feedback']})}]}
    else:raise ValueError('Unsupported request builder')
    return {'adapter_controls':controls['adapter_controls'],'request':request}


def _checked(manifest,root,configuration_id,condition):
    root=Path(root)
    if manifest.get('contract')!='prompt-execution-gates-v1' or condition not in ('P1','P2'):
        raise ValueError('Expected frozen gate-v1 and a new condition')
    g.stamp(manifest['frozen_utc'])
    inputs=[json.loads(x) for x in g.bound(manifest['inputs'],root).decode().splitlines() if x.strip()]
    ids=[r.get('id') for r in inputs]
    if ids!=[f'DEV-{i:03}' for i in range(1,61)] or any(set(r)!={'id','feedback'} or not isinstance(r['feedback'],str) for r in inputs):
        raise ValueError('Exactly 60 ordered input-only records required')
    schema=g.json_bound(manifest['schema'],root)
    if manifest['prompt_bundle']['sha256']!=g.MANIFEST_SHA256:raise ValueError('Frozen bundle mismatch')
    g.bound(manifest['prompt_bundle'],root)
    roster=g.json_bound(manifest['roster'],root)['entries']
    inventory=g.json_bound(manifest['source_inventory'],root)['entries']
    rid=[r['id'] for r in roster];iid=[r['id'] for r in inventory]
    if not rid or len(set(rid))!=len(rid) or len(set(iid))!=len(iid) or set(rid)!=set(iid):raise ValueError('Unreconciled roster')
    for r in inventory:
        if r.get('disposition') not in ('completed','blocked','excluded') or not r.get('reason'):raise ValueError('Executable baseline work remains')
    for r in roster:
        if r.get('state') not in ('scheduled','blocked','excluded') or not r.get('reason'):raise ValueError('Unexplained roster disposition')
        if r['state']=='scheduled' and next(x for x in inventory if x['id']==r['id'])['disposition']!='completed':raise ValueError('Incomplete scheduled parent')
    scheduled=[r for r in roster if r['state']=='scheduled']
    configs=manifest['configurations']
    scheduled_ids=[r['id'] for r in scheduled];config_ids=[c['id'] for c in configs]
    scope=manifest.get('manifest_scope')
    if scope is None:
        if config_ids!=scheduled_ids:raise ValueError('Configuration roster differs')
    elif not isinstance(scope,list) or not scope or len(set(scope))!=len(scope) or scope!=config_ids or scope!=[i for i in scheduled_ids if i in scope]:
        raise ValueError('Manifest scope must exactly name an ordered subset of the full scheduled roster')
    expected=[{'id':r['id'],'conditions':['P1','P2'] if i%2==0 else ['P2','P1']} for i,r in enumerate(scheduled)]
    if g.json_bound(manifest['schedule'],root)['order']!=expected:raise ValueError('Counterbalance schedule mismatch')
    matches=[c for c in configs if c['id']==configuration_id]
    if len(matches)!=1:raise ValueError('Configuration not scheduled')
    c=matches[0];r=next(x for x in scheduled if x['id']==configuration_id)
    controls=c['controls'];parent=g.json_bound(c['parent_baseline'],root)
    baseline=g.bound(c['baseline_instruction'],root).decode()
    if not REQUIRED.issubset(controls) or controls.get('effort') in ('max','ultra'):raise ValueError('Missing or prohibited controls')
    if g.canonical(controls)!=c['controls_sha256'] or parent['controls_sha256']!=c['controls_sha256']:raise ValueError('Paired controls mismatch')
    if parent['id']!=c['parent_baseline_id'] or parent['id']!=r['parent_baseline_id'] or parent['baseline_instruction_sha256']!=g.sha(baseline.encode()):raise ValueError('Parent binding mismatch')
    size={'single_record':1,'batch10':10}.get(parent['context_unit'])
    if size is None:raise ValueError('Unsupported context unit')
    groups=[ids[n:n+size] for n in range(0,60,size)]
    if c['batch_membership']!=groups:raise ValueError('Batch boundaries changed')
    instruction=compose_instruction(baseline,condition,role=c['role'],parent_baseline_id=parent['id'],root=root)['instruction']
    cond=c['conditions'][condition]
    if g.bound(cond['instruction'],root).decode()!=instruction:raise ValueError('Frozen instruction mismatch')
    evidence=g.json_bound(cond['observational_evidence'],root)
    adapter=evidence.get('adapter')
    if adapter not in ADAPTERS:raise ValueError('Local/exact-tokenizer surfaces cannot use observational admission')
    canonical_schema=json.loads((Path(__file__).resolve().parents[1]/'schemas/judgments.schema.json').read_text())
    if schema!=canonical_schema:raise ValueError('Schema differs from unchanged runner contract')
    if adapter=='openrouter_paid_v1':
        request_controls=controls['adapter_controls']['request_controls']
        required_format={'type':'json_schema','json_schema':{'name':'judgments','strict':True,'schema':schema}}
        if request_controls.get('response_format')!=required_format or request_controls.get('model')!=controls['model'] or request_controls.get('max_tokens')!=controls['output_reserve_tokens']:raise ValueError('OpenRouter frozen request control mismatch')
    if (adapter=='openrouter_paid_v1')!=(size==1):raise ValueError('Adapter context unit mismatch')
    if c['role']!=('cli_combined_prompt' if adapter=='codex_batch_v1' else 'system'):raise ValueError('Adapter role mismatch')
    bindings={'condition':condition,'parent_baseline_id':parent['id'],'controls_sha256':c['controls_sha256'],'instruction_sha256':g.sha(instruction.encode()),'inputs_sha256':manifest['inputs']['sha256'],'schema_sha256':manifest['schema']['sha256']}
    if any(evidence.get(k)!=v for k,v in bindings.items()):raise ValueError('Observational evidence binding mismatch')
    if evidence.get('prospective_rendered_tokens','missing') is not None or not evidence.get('unknown_reason'):raise ValueError('Unavailable prospective tokens must remain null with reason')
    advertised=g.json_bound(evidence['advertised_context'],root)
    history_spec=g.json_bound(evidence['historical_usage'],root)
    if history_spec.get('kind')!='saved_attempt_usage_v1':raise ValueError('Unsupported historical usage source contract')
    history={'requests':[_usage(r,adapter) for r in _attempts(history_spec['raw_attempts'],root,adapter,controls)]}
    limit=controls['context_tokens'];reserve=controls['output_reserve_tokens']
    if reserve is None:
        if adapter!='codex_batch_v1' or controls.get('output_reserve_source')!='unexposed_cli_default_unchanged':raise ValueError('Unknown output reserve unsupported without unchanged opaque CLI evidence')
    elif not g.nonnegative(reserve) or reserve<1:raise ValueError('Invalid output reserve')
    if limit is not None and (not g.nonnegative(limit) or limit<=(reserve or 0)):raise ValueError('Invalid context limit')
    if _context(advertised,root,adapter,controls)!=limit:raise ValueError('Underlying context differs from frozen limit')
    for row in history['requests']:
        for key in ('input_tokens','output_tokens'):
            if key not in row or (row[key] is not None and not g.nonnegative(row[key])):raise ValueError('Invalid historical usage')
        if limit is not None and row['input_tokens'] is not None and row['input_tokens']+(reserve or 0)>limit:raise ValueError('Historical evidence exceeds unchanged context')
    requests=evidence['requests']
    smoke_groups=[[x] for x in ids[:3]] if size==1 else [ids[:3]]
    if [x['record_ids'] for x in requests]!=smoke_groups+groups:raise ValueError('Complete smoke and development requests required')
    lookup={r['id']:r['feedback'] for r in inputs}
    for request in requests:
        raw=g.bound(request['client_request'],root)
        if request.get('request_bytes')!=len(raw):raise ValueError('Client request byte mismatch')
        expected=expected_request(adapter,instruction,[{'id':i,'feedback':lookup[i]} for i in request['record_ids']],controls)
        if json.loads(raw)!=expected:raise ValueError('Client payload or controls differ from exact reconstruction')
    return c,cond,evidence,inputs,schema,instruction,bindings


def admit_smoke(manifest,root,configuration_id,condition):
    c,cond,evidence,*_= _checked(manifest,root,configuration_id,condition)
    return {'stage':'smoke','admitted':True,'configuration_id':configuration_id,'condition':condition,
            'observational':True,'fully_verified_controls':False,'prospective_rendered_tokens':None,'output_reserve_tokens':c['controls']['output_reserve_tokens'],
            'unknown_reason':evidence['unknown_reason'],'request_bytes':[r['request_bytes'] for r in evidence['requests']],
            'manifest_sha256':g.canonical(manifest),'reference_labels_read':False,
            'limitations':['Client bytes are not a token bound; hidden provider rendering is unknown.',
                           'Controller must enforce frozen schedule and transmit the bound request bytes.']}


def audit_response(raw,adapter,context_limit):
    """Inspect exposed metadata only; never interpret model prose as diagnostics."""
    if adapter not in ADAPTERS:raise ValueError('Unsupported observational adapter')
    blockers=[];usage=[]
    def visit(value):
        if isinstance(value,list):
            for item in value:visit(item)
        elif isinstance(value,dict):
            if 'input_tokens' in value and any(k in value for k in ('cache_read_input_tokens','cache_creation_input_tokens')):
                counts=[value.get(k,0) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens')]
                if all(g.nonnegative(n) for n in counts):
                    total=sum(counts);usage.append(total)
                    if context_limit is not None and total>context_limit:blockers.append('observed context overflow including cached input')
                else:blockers.append('invalid cached input usage')
            for key,item in value.items():
                if key in ('finish_reason','stop_reason') and item in ('length','max_tokens','max_output_tokens','context_length_exceeded','model_context_window_exceeded'):blockers.append('truncation:'+str(item))
                if key in ('compacted','truncated','context_overflow','identity_violation','control_violation') and item is True:blockers.append(key)
                if key in ('type','code','subtype') and isinstance(item,str) and item in ('context_length_exceeded','context_window_exceeded','context_compacted','context_compaction','compact_boundary','thread.compacted','compaction','compaction.completed'):blockers.append(item)
                if key in ('prompt_tokens','input_tokens') and item is not None:
                    if not g.nonnegative(item):blockers.append('invalid input usage')
                    else:
                        usage.append(item)
                        if context_limit is not None and item>context_limit:blockers.append('observed context overflow')
                if key not in ('content','text','result','prediction','feedback'):visit(item)
    visit(raw)
    return {'passed':not blockers,'blockers':sorted(set(blockers)),'observed_input_tokens':usage or None,
            'observational':True,'fully_verified_controls':False}


def admit_development(manifest,root,configuration_id,condition,smoke_verifier=None):
    root=Path(root)
    c,cond,evidence,inputs,schema,instruction,bindings=_checked(manifest,root,configuration_id,condition)
    smoke=g.json_bound(cond['smoke_evidence'],root)
    if any(smoke.get(k)!=v for k,v in bindings.items()):raise ValueError('Smoke condition binding mismatch')
    adapter=evidence['adapter']
    selected=g.verify_openrouter_smoke if adapter=='openrouter_paid_v1' else g.verify_subscription_smoke
    if smoke_verifier is not None and smoke_verifier is not selected:raise ValueError('Custom smoke verifier cannot override code-selected verification')
    if smoke.get('extractor')!=adapter:raise ValueError('Smoke extractor differs from adapter')
    if not g.stamp(manifest['frozen_utc'])<=g.stamp(smoke['started_utc'])<=g.stamp(smoke['finished_utc'])<=g.stamp(smoke['inspected_utc'])<g.stamp(cond['development_not_before']):raise ValueError('Smoke chronology invalid')
    if smoke.get('inspection') not in ('passed','accepted_unchanged') or not smoke.get('inspector') or len(smoke.get('records',[]))!=3:raise ValueError('Three inspected smoke responses required')
    if adapter=='openrouter_paid_v1':
        verification=selected(smoke,inputs,instruction,schema,c['controls'],c['role'],root)
    else:
        canonical_schema=json.loads((Path(__file__).resolve().parents[1]/'schemas/judgments.schema.json').read_text())
        if schema!=canonical_schema:raise ValueError('Subscription schema differs from actual runner')
        verification=selected(smoke,inputs,instruction,c['controls'],c['role'],root)
    raw=[json.loads(line) for line in g.bound(smoke['raw_attempts'],root).decode().splitlines() if line.strip()]
    limit=c['controls']['context_tokens']
    input_limit=None if limit is None else limit-(c['controls']['output_reserve_tokens'] or 0)
    diagnostics=[audit_response(row,adapter,input_limit) for row in raw]
    if not all(x['passed'] for x in diagnostics):raise ValueError('Observed smoke diagnostic blocks development: '+str(diagnostics))
    result=admit_smoke(manifest,root,configuration_id,condition)
    result.update(stage='development',smoke_verification=verification,response_diagnostics=diagnostics)
    return result
