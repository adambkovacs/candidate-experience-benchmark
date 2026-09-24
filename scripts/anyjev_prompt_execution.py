"""Exact-token admission for the matched AnyJev HF generated control only.

Uses the common global roster and counterbalanced schedule, never the hosted
observational admission. Configuration.native_execution binds token_preflight,
baseline_predictions, controller_sources and a relative journal path. Conditions
bind instruction and output_paths:{smoke,development}. Development additionally
requires an independently written, hash-bound inspection via CLI. This records
inspection; it does not automatically accept intrinsic output failures.
"""
import importlib.metadata
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
import prompt_execution_gates as g
import prompt_schedule as schedule
from frozen_prompt_variants import compose_instruction

ADAPTER='anyjev_generated_exact_v1'

def utc():return datetime.now(timezone.utc).isoformat()
def binding(path,root):return {'file':str(Path(path).resolve().relative_to(root.resolve())), 'sha256':g.sha(Path(path).read_bytes())}
def exclusive(path,value):
    with Path(path).open('x') as out:json.dump(value,out,indent=2);out.write('\n')
def lines(raw):return [json.loads(x) for x in raw.decode().splitlines() if x.strip()]

def controls_from_baseline(row,context):
    return {'model':row['requested_model'],'model_revision':row['artifact_revision'],
      'quantization':row['quantization'],'runtime':row['runtime_versions'],'hardware':row['host'],
      'effort':'not_applicable','sampling':{'do_sample':row['do_sample'],'enable_thinking':row['enable_thinking']},
      'output_method':'prompted_json','parsing':'strict_json','retry_policy':'none',
      'context_tokens':context,'output_reserve_tokens':row['max_new_tokens'],
      'adapter_controls':{'device':row['device'],'dtype':row['dtype'],'max_input_tokens':row['max_input_tokens'],
                          'add_generation_prompt':True,'add_special_tokens':False}}

def load_plan(args,root):
    """No tokenizer, model, references or network accessed here."""
    root=Path(root)
    if args.prompt_variant not in ('P1','P2'):raise ValueError('Exact admission only supports new P1/P2 conditions')
    required=('execution_manifest','execution_manifest_sha256','execution_configuration','execution_stage','execution_journal')
    if any(not getattr(args,k,None) for k in required):raise ValueError('Phase-two gates require a frozen execution manifest and stage')
    spec={'file':str(Path(args.execution_manifest).resolve().relative_to(root.resolve())),'sha256':args.execution_manifest_sha256}
    manifest=g.json_bound(spec,root)
    if manifest.get('contract')!='prompt-execution-gates-v1':raise ValueError('Wrong global freeze contract')
    frozen=g.stamp(manifest['frozen_utc'])
    if frozen>g.stamp(utc()):raise ValueError('Freeze timestamp is in the future')
    rows=lines(g.bound(manifest['inputs'],root));ids=[r.get('id') for r in rows]
    if ids!=[f'DEV-{i:03d}' for i in range(1,61)] or any(set(r)!={'id','feedback'} or not isinstance(r['feedback'],str) for r in rows):raise ValueError('Exact input-only60 required')
    if g.bound(manifest['inputs'],root)!=(root/'data/pilot/inputs.jsonl').read_bytes():raise ValueError('Frozen inputs differ from controller input')
    if g.json_bound(manifest['schema'],root)!=json.loads((root/'schemas/judgments.schema.json').read_text()):raise ValueError('Frozen output schema changed')
    if manifest['prompt_bundle']['sha256']!=g.MANIFEST_SHA256:raise ValueError('Frozen bundle differs')
    g.bound(manifest['prompt_bundle'],root)
    roster=g.json_bound(manifest['roster'],root)['entries'];inventory=g.json_bound(manifest['source_inventory'],root)['entries']
    rid=[x['id'] for x in roster];iid=[x['id'] for x in inventory]
    if not rid or len(set(rid))!=len(rid) or len(set(iid))!=len(iid) or set(rid)!=set(iid):raise ValueError('Unreconciled global inventory')
    for x in inventory:
        if x.get('disposition') not in ('completed','blocked','excluded') or not x.get('reason'):raise ValueError('Executable baseline remains')
    for x in roster:
        if x.get('state') not in ('scheduled','blocked','excluded') or not x.get('reason'):raise ValueError('Roster disposition missing')
        if x['state']=='scheduled' and next(i for i in inventory if i['id']==x['id'])['disposition']!='completed':raise ValueError('Scheduled parent incomplete')
    scheduled=[x for x in roster if x['state']=='scheduled'];configs=manifest['configurations']
    config_ids=[x['id'] for x in configs];scheduled_ids=[x['id'] for x in scheduled];scope=manifest.get('manifest_scope')
    if scope is None:
        if config_ids!=scheduled_ids:raise ValueError('Configuration roster order differs')
    elif not isinstance(scope,list) or not scope or len(set(scope))!=len(scope) or scope!=config_ids or scope!=[i for i in scheduled_ids if i in scope]:raise ValueError('Manifest scope must be an ordered subset of full roster')
    expected=[{'id':x['id'],'conditions':['P1','P2'] if i%2==0 else ['P2','P1']} for i,x in enumerate(scheduled)]
    if g.json_bound(manifest['schedule'],root)['order']!=expected:raise ValueError('Counterbalance differs')
    matches=[x for x in configs if x['id']==args.execution_configuration]
    if len(matches)!=1:raise ValueError('Configuration not scheduled')
    c=matches[0];native=c['native_execution'];controls=c['controls'];parent=g.json_bound(c['parent_baseline'],root)
    if native.get('adapter')!=ADAPTER or c['role']!='system':raise ValueError('Not the supported generated control')
    if parent['context_unit']!='single_record' or parent['id']!=c['parent_baseline_id'] or args.parent_baseline_id!=parent['id']:raise ValueError('Parent context/identity differs')
    r=next(x for x in scheduled if x['id']==c['id'])
    if r['parent_baseline_id']!=parent['id']:raise ValueError('Roster parent differs')
    if c['batch_membership']!=[[i] for i in ids]:raise ValueError('Native context grouping changed')
    if g.canonical(controls)!=c['controls_sha256'] or parent['controls_sha256']!=c['controls_sha256']:raise ValueError('Control binding mismatch')
    sources=native['controller_sources']
    needed={'scripts/anyjev_generation_control.py','scripts/anyjev_prompt_execution.py','scripts/anyjev_benchmark.py','scripts/frozen_prompt_variants.py','scripts/prompt_schedule.py','scripts/prompt_execution_gates.py','scripts/jev_benchmark.py','scripts/development_benchmark.py'}
    if not needed.issubset({x['file'] for x in sources}):raise ValueError('Controller source freeze incomplete')
    for x in sources:g.bound(x,root)
    preflight=g.json_bound(native['token_preflight'],root);baseline=lines(g.bound(native['baseline_predictions'],root))
    if preflight['baseline_sha256']!=native['baseline_predictions']['sha256'] or [r.get('id') for r in baseline]!=ids:raise ValueError('Baseline60 binding differs')
    if controls_from_baseline(baseline[0],preflight['settings']['model_max_position_embeddings'])!=controls:raise ValueError('Declared native controls differ from actual P0')
    if any(controls_from_baseline(x,controls['context_tokens'])!=controls or x['status'] not in ('ok','invalid_output') or x['finish_reason']!='stop' for x in baseline):raise ValueError('Baseline controls/coverage differ')
    from anyjev_generation_control import control_messages
    policy=(root/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    base=control_messages('',policy)[0]['content']
    if g.bound(c['baseline_instruction'],root).decode()!=base or parent['baseline_instruction_sha256']!=g.sha(base.encode()):raise ValueError('Baseline instruction differs')
    condition=c['conditions'][args.prompt_variant]
    instruction=compose_instruction(base,args.prompt_variant,role='system',parent_baseline_id=parent['id'],root=root)['instruction']
    if g.bound(condition['instruction'],root).decode()!=instruction:raise ValueError('Condition instruction differs')
    for row,saved in zip(rows,baseline):
        if saved['input_sha256']!=g.sha(row['feedback'].encode()) or saved['policy_sha256']!=g.sha(policy.encode()) or saved['request_sha256']!=g.canonical(control_messages(row['feedback'],policy)):raise ValueError('Baseline request/input drift')
    if args.execution_stage not in ('smoke','development') or args.limit!={'smoke':3,'development':60}[args.execution_stage]:raise ValueError('Stage must be smoke3 or development60')
    journal=(root/native['journal']).resolve();journal.relative_to(root.resolve())
    if Path(args.execution_journal).resolve()!=journal:raise ValueError('Frozen journal path differs')
    output=(root/condition['output_paths'][args.execution_stage]).resolve();output.relative_to(root.resolve())
    if Path(args.output).resolve()!=output or output.exists():raise ValueError('Frozen output differs or already exists')
    expected_cli=(controls['model_revision'],controls['adapter_controls']['device'].split(':')[0],controls['adapter_controls']['dtype'].removeprefix('torch.'),controls['adapter_controls']['max_input_tokens'],controls['output_reserve_tokens'])
    if (args.revision,args.device,args.dtype,args.max_input_tokens,args.max_new_tokens)!=expected_cli:raise ValueError('CLI controls differ from baseline freeze')
    if platform.platform()!=controls['hardware']:raise ValueError('Host platform differs from baseline')
    if {p:importlib.metadata.version(p) for p in controls['runtime']}!=controls['runtime']:raise ValueError('Native runtime differs')
    if any(os.environ.get(k)!='4' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS')):raise ValueError('Preserve baseline OMP/MKL4')
    return {'root':root,'manifest':manifest,'manifest_binding':spec,'configuration':c,'condition':condition,'rows':rows,'baseline':baseline,'preflight':preflight,'policy':policy,'instruction':instruction,'journal':journal,'output':output,'variant':args.prompt_variant,'stage':args.execution_stage}

def exact_token_check(plan,args,tok):
    """Render ALL60 with the real pinned tokenizer and check P0/P1/P2 evidence."""
    from anyjev_generation_control import control_messages
    root=Path(args.model_path);pre=plan['preflight'];c=plan['configuration'];controls=c['controls']
    if g.sha((root/'download-manifest.json').read_bytes())!=pre['artifact_manifest_sha256']:raise ValueError('Artifact manifest differs from token preflight')
    for name,expected in pre['artifact_files'].items():
        path=(root/name).resolve();path.relative_to(root.resolve())
        if g.sha(path.read_bytes())!=expected:raise ValueError('Tokenizer/config file changed')
    if {p:importlib.metadata.version(p) for p in pre['runtime_versions']}!=pre['runtime_versions']:raise ValueError('Tokenizer runtime changed')
    if pre['artifact_revision']!=args.revision or pre['artifact_repo']!=controls['model']:raise ValueError('Preflight model differs')
    actual_config=json.loads((root/'config.json').read_text())
    if actual_config['max_position_embeddings']!=controls['context_tokens']:raise ValueError('Artifact context differs')
    verified=[]
    for variant in ('P0','P1','P2'):
        saved=pre['conditions'][variant]['records']
        if [r['id'] for r in saved]!=[r['id'] for r in plan['rows']]:raise ValueError('Token preflight incomplete')
        for row,evidence in zip(plan['rows'],saved):
            messages=control_messages(row['feedback'],plan['policy'],variant,c['parent_baseline_id'])
            prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            tokens=tok.encode(prompt,add_special_tokens=False)
            values={'input_sha256':g.sha(row['feedback'].encode()),'messages_sha256':g.canonical(messages),'rendered_prompt_sha256':g.sha(prompt.encode()),'input_tokens':len(tokens)}
            if any(evidence.get(k)!=v for k,v in values.items()):raise ValueError('Exact rendered token preflight mismatch')
            if len(tokens)>args.max_input_tokens or len(tokens)+args.max_new_tokens>controls['context_tokens']:raise ValueError('Exact full prompt exceeds unchanged context')
            if variant=='P0' and plan['baseline'][int(row['id'].split('-')[1])-1]['input_tokens']!=len(tokens):raise ValueError('Historical P0 token count differs')
            if variant==plan['variant']:verified.append({'id':row['id'],**values})
    return {'adapter':ADAPTER,'condition':plan['variant'],'measured_utc':utc(),'manifest':plan['manifest_binding'],'exact_rendered_tokens_verified':True,'reference_labels_read':False,'records':verified,'pad_token_id':tok.pad_token_id or tok.eos_token_id,'model_context_tokens':controls['context_tokens']}

def inspect_smoke(plan,args,tok):
    """Verify independent inspection against full saved native request/output."""
    from anyjev_generation_control import control_messages,parse_generated
    root=plan['root'];c=plan['configuration'];controls=c['controls']
    path=getattr(args,'smoke_inspection',None);sha=getattr(args,'smoke_inspection_sha256',None)
    if not path or not sha:raise ValueError('Development requires separately recorded smoke inspection')
    spec={'file':str(Path(path).resolve().relative_to(root.resolve())),'sha256':sha};inspection=g.json_bound(spec,root)
    raw=lines(g.bound(inspection['raw_attempts'],root))
    smoke_path=(root/plan['condition']['output_paths']['smoke']).resolve()
    if inspection['raw_attempts']!=binding(smoke_path,root):raise ValueError('Inspection raw smoke differs from frozen output')
    if inspection.get('manifest')!=plan['manifest_binding'] or inspection.get('condition')!=plan['variant'] or not inspection.get('inspector'):raise ValueError('Inspection identity missing')
    if g.stamp(inspection['inspected_utc'])>g.stamp(utc()) or g.stamp(inspection['inspected_utc'])<=g.stamp(plan['manifest']['frozen_utc']):raise ValueError('Inspection chronology differs')
    if len(raw)!=3 or len(inspection['records'])!=3:raise ValueError('Smoke3 required')
    generation=json.loads((Path(args.model_path)/'generation_config.json').read_text());eos=generation['eos_token_id'];eos=[eos] if isinstance(eos,int) else eos
    token_rows=plan['preflight']['conditions'][plan['variant']]['records']
    for row,expected,declared,evidence in zip(raw,plan['rows'][:3],inspection['records'],token_rows):
        if row['id']!=expected['id'] or row.get('finish_reason')!='stop' or row.get('status') not in ('ok','invalid_output'):raise ValueError('Smoke identity/service/truncation failure')
        if row.get('execution_manifest')!=plan['manifest_binding'] or row.get('execution_stage')!='smoke' or row.get('native_controls')!=controls:raise ValueError('Smoke execution controls differ')
        if g.stamp(row['finished_utc'])>=g.stamp(inspection['inspected_utc']):raise ValueError('Inspection predates smoke completion')
        messages=control_messages(expected['feedback'],plan['policy'],plan['variant'],c['parent_baseline_id'])
        if row.get('messages')!=messages or row['request_sha256']!=g.canonical(messages):raise ValueError('Smoke request bytes differ')
        if controls_from_baseline(row,controls['context_tokens'])!=controls:raise ValueError('Smoke actual runtime differs from freeze')
        if row.get('eos_token_ids')!=eos or not row.get('generated_token_ids') or row['generated_token_ids'][-1] not in eos or row.get('output_tokens')!=len(row['generated_token_ids']) or tok.decode(row['generated_token_ids'],skip_special_tokens=True)!=row['raw_response']:raise ValueError('Smoke raw token termination/decoding differs')
        prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        if row.get('rendered_prompt_sha256')!=g.sha(prompt.encode()) or row.get('input_tokens')!=len(tok.encode(prompt,add_special_tokens=False)) or row['input_tokens']!=evidence['input_tokens']:raise ValueError('Smoke rendered token mismatch')
        if g.stamp(row['started_utc'])<g.stamp(plan['manifest']['frozen_utc']) or g.stamp(row['finished_utc'])<g.stamp(row['started_utc']):raise ValueError('Smoke chronology invalid')
        prediction=parse_generated(row['raw_response'],True);status='ok' if prediction else 'invalid_output'
        if row['prediction']!=prediction or row['status']!=status or declared.get('id')!=row['id'] or declared.get('status')!=status or declared.get('prediction')!=prediction:raise ValueError('Inspected smoke does not match strict raw parsing')
        if status=='invalid_output' and not (declared.get('accepted_unchanged') is True and declared.get('failure_class')=='intrinsic_schema' and declared.get('inspection_reason')):raise ValueError('Intrinsic failure needs explicit unchanged acceptance')
    return spec

def execute(args,root):
    """Smoke3 or development60; exclusive artifacts and no automatic retries."""
    from anyjev_generation_control import verify_artifact,control_messages,variant_instruction,parse_generated
    plan=load_plan(args,root);root=plan['root'];c=plan['configuration'];controls=c['controls'];output=plan['output']
    artifact=verify_artifact(args.model_path,args.revision)
    if artifact['repo']!=controls['model']:raise ValueError('Pinned artifact model differs')
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    tok=AutoTokenizer.from_pretrained(args.model_path,local_files_only=True)
    measured=exact_token_check(plan,args,tok)
    preflight_path=output.with_name(output.name+'.token-preflight.json');exclusive(preflight_path,measured)
    inspection=None
    if plan['stage']=='development':
        inspection=inspect_smoke(plan,args,tok)
        inspected=schedule.claim(plan['manifest']['schedule'],plan['journal'],c['id'],plan['variant'],'inspected_admission',root)
        schedule.finish(plan['manifest']['schedule'],plan['journal'],inspected['attempt_id'],'completed',[inspection,binding(preflight_path,root),plan['manifest_binding']],root)
    claim=schedule.claim(plan['manifest']['schedule'],plan['journal'],c['id'],plan['variant'],plan['stage'],root)
    events=output.with_name(output.name+'.events.jsonl');terminal=output.with_name(output.name+'.terminal.json');completed=False;count=0
    try:
        load_start=time.perf_counter()
        model=AutoModelForCausalLM.from_pretrained(args.model_path,local_files_only=True,dtype=getattr(torch,args.dtype)).to(args.device).eval()
        device=str(next(model.parameters()).device);dtype=str(next(model.parameters()).dtype)
        if device!=controls['adapter_controls']['device'] or dtype!=controls['adapter_controls']['dtype'] or model.config.max_position_embeddings!=controls['context_tokens']:raise ValueError('Effective local device/dtype/context changed')
        load_seconds=time.perf_counter()-load_start
        with output.open('x') as out,events.open('x') as journal:
            for row,evidence in zip(plan['rows'][:args.limit],measured['records']):
                messages=control_messages(row['feedback'],plan['policy'],plan['variant'],c['parent_baseline_id'])
                _,audit=variant_instruction(control_messages('',plan['policy'])[0]['content'],plan['variant'],c['parent_baseline_id'])
                prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                inputs=tok(prompt,return_tensors='pt',add_special_tokens=False);n=inputs['input_ids'].shape[1]
                if n!=evidence['input_tokens'] or g.sha(prompt.encode())!=evidence['rendered_prompt_sha256']:raise ValueError('Live rendered request differs from exact preflight')
                rec={'id':row['id'],'requested_model':artifact['repo'],'artifact_revision':args.revision,'surface':'Matched HF generated JSON control; not AnyJev readout','device':device,'dtype':dtype,'quantization':'none','host':platform.platform(),'runtime_versions':controls['runtime'],'config_note':args.config_note,'model_load_seconds':load_seconds,'input_sha256':g.sha(row['feedback'].encode()),'policy_sha256':g.sha(plan['policy'].encode()),'request_sha256':g.canonical(messages),'messages':messages,'rendered_prompt_sha256':g.sha(prompt.encode()),'input_tokens':n,'enable_thinking':False,'do_sample':False,'max_input_tokens':args.max_input_tokens,'max_new_tokens':args.max_new_tokens,'attempts':1,'prompt_variant':audit,'execution_manifest':plan['manifest_binding'],'execution_stage':plan['stage'],'native_controls':controls,'schedule_attempt_id':claim['attempt_id'],'reference_labels_read':False,'started_utc':utc()}
                journal.write(json.dumps({'event':'started','id':row['id'],'utc':rec['started_utc'],'request_sha256':rec['request_sha256']})+'\n');journal.flush();os.fsync(journal.fileno())
                start=time.perf_counter()
                try:
                    with torch.inference_mode():generated=model.generate(**{k:v.to(args.device) for k,v in inputs.items()},do_sample=False,max_new_tokens=args.max_new_tokens,pad_token_id=measured['pad_token_id'])
                    token_ids=generated[0,n:].tolist();raw=tok.decode(token_ids,skip_special_tokens=True);eos=model.generation_config.eos_token_id;eos=[eos] if isinstance(eos,int) else eos
                    ended=bool(token_ids and token_ids[-1] in (eos or []));prediction=parse_generated(raw,ended)
                    rec.update(prediction=prediction,status='ok' if prediction else 'invalid_output',raw_response=raw,generated_token_ids=token_ids,eos_token_ids=eos,output_tokens=len(token_ids),finish_reason='stop' if ended else 'length')
                except Exception as exc:rec.update(prediction=None,status='service_error',error_type=type(exc).__name__,error=str(exc)[:500])
                rec.update(elapsed_seconds=time.perf_counter()-start,finished_utc=utc());out.write(json.dumps(rec)+'\n');out.flush();os.fsync(out.fileno());count+=1
                journal.write(json.dumps({'event':'finished','id':row['id'],'utc':rec['finished_utc'],'status':rec['status']})+'\n');journal.flush();os.fsync(journal.fileno());print(row['id'],rec['status'],flush=True)
                if rec['status']=='service_error' or rec.get('finish_reason')!='stop':break
            completed=count==args.limit and rec.get('finish_reason')=='stop' and rec['status']!='service_error'
    except BaseException as exc:
        exclusive(terminal,{'status':'stopped','exception':type(exc).__name__,'error':str(exc)[:500],'records_saved':count,'utc':utc(),'manifest':plan['manifest_binding']})
        schedule.finish(plan['manifest']['schedule'],plan['journal'],claim['attempt_id'],'stopped',[binding(terminal,root),binding(preflight_path,root)],root)
        raise
    exclusive(terminal,{'status':'completed' if completed else 'stopped','records_saved':count,'utc':utc(),'manifest':plan['manifest_binding'],'intrinsic_invalid_outputs_retained':True})
    schedule.finish(plan['manifest']['schedule'],plan['journal'],claim['attempt_id'],'completed' if completed else 'stopped',[binding(output,root),binding(events,root),binding(terminal,root),binding(preflight_path,root)],root)
