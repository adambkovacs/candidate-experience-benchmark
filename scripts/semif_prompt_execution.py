"""Exact native SemIf generated-control prompt execution; no direct-mode changes.
Historical P0 generated messages/token counts were not retained. P0 remains
source-reconstructed, never upgraded to full historical wire verification.
"""
import importlib.metadata
import json
import os
import platform
import time
from pathlib import Path
import prompt_execution_gates as g
import prompt_schedule as schedule
from frozen_prompt_variants import compose_instruction
from jev_benchmark import make_payload
from development_benchmark import valid
from anyjev_prompt_execution import utc,binding,exclusive,lines
ADAPTER='semif_generated_exact_v1'

def controls_from_baseline(row,context):
    metadata=row['metadata']
    return {'model':row['requested_model'],'model_revision':row['artifact_revision'],'quantization':metadata['quantization'],'runtime':row['runtime_versions'],'hardware':row['host'],'effort':'not_applicable','sampling':{'temperature':metadata['temperature'],'enable_thinking':metadata['enable_thinking']},'output_method':'prompted_json','parsing':'strict_json','retry_policy':'none','context_tokens':context,'output_reserve_tokens':metadata['max_tokens'],'adapter_controls':{'backend':'mlx','device':'gpu','dtype':metadata['dtype'],'max_input_tokens':4096,'allocator_cache_limit_bytes':metadata['allocator_cache_limit_bytes'],'mlx_lm_source':metadata['mlx_lm_source'],'source_artifact_sha256':metadata['source_artifact_sha256'],'add_generation_prompt':True,'generation_tokenization':'stream_generate native BOS-aware special-token rule'},'historical_prompt_evidence':'source_reconstructed; saved P0 hash is decision intent, not generated messages'}

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
    needed={'scripts/specialist_benchmark.py','scripts/semif_prompt_execution.py','scripts/anyjev_prompt_execution.py','scripts/frozen_prompt_variants.py','scripts/prompt_schedule.py','scripts/prompt_execution_gates.py','scripts/jev_benchmark.py','scripts/development_benchmark.py'}
    if not needed.issubset({x['file'] for x in sources}):raise ValueError('Controller source freeze incomplete')
    for x in sources:g.bound(x,root)
    preflight=g.json_bound(native['token_preflight'],root);baseline=lines(g.bound(native['baseline_predictions'],root))
    if [r.get('id') for r in baseline]!=ids:raise ValueError('Baseline60 binding differs')
    if controls_from_baseline(baseline[0],preflight['settings']['model_context_metadata'])!=controls:raise ValueError('Declared native controls differ from actual P0')
    if any(controls_from_baseline(x,controls['context_tokens'])!=controls or x['status'] not in ('ok','invalid_output') or x['raw_response']['finish_reason']!='stop' for x in baseline):raise ValueError('Baseline controls/coverage differ')
    from specialist_benchmark import generated_messages as control_messages
    policy=(root/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    base=control_messages('',policy)[0]['content']
    if g.bound(c['baseline_instruction'],root).decode()!=base or parent['baseline_instruction_sha256']!=g.sha(base.encode()):raise ValueError('Baseline instruction differs')
    condition=c['conditions'][args.prompt_variant]
    instruction=compose_instruction(base,args.prompt_variant,role='system',parent_baseline_id=parent['id'],root=root)['instruction']
    if g.bound(condition['instruction'],root).decode()!=instruction:raise ValueError('Condition instruction differs')
    for row,saved in zip(rows,baseline):
        if saved['input_sha256']!=g.sha(row['feedback'].encode()) or saved['policy_sha256']!=g.sha(policy.encode()) or saved['request_sha256']!=g.canonical(make_payload(row['feedback'],policy,'not-sent','official')):raise ValueError('Baseline request/input drift')
    if args.execution_stage not in ('smoke','development') or args.limit!={'smoke':3,'development':60}[args.execution_stage]:raise ValueError('Stage must be smoke3 or development60')
    journal=(root/native['journal']).resolve();journal.relative_to(root.resolve())
    if Path(args.execution_journal).resolve()!=journal:raise ValueError('Frozen journal path differs')
    output=(root/condition['output_paths'][args.execution_stage]).resolve();output.relative_to(root.resolve())
    if Path(args.output).resolve()!=output or output.exists():raise ValueError('Frozen output differs or already exists')
    if args.kind!='semif' or args.mode!='generated' or args.bits is not None or getattr(args,'offset',0)!=0 or args.device!='mps' or args.revision!=controls['model_revision'] or args.max_tokens!=4096 or args.model_path!=baseline[0]['requested_model']:raise ValueError('CLI controls differ from baseline freeze')
    if platform.platform()!=controls['hardware']:raise ValueError('Host platform differs from baseline')
    if {p:importlib.metadata.version(p) for p in controls['runtime']}!=controls['runtime']:raise ValueError('Native runtime differs')
    if any(os.environ.get(k)!='4' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS')):raise ValueError('Preserve baseline OMP/MKL4')
    return {'root':root,'manifest':manifest,'manifest_binding':spec,'configuration':c,'condition':condition,'rows':rows,'baseline':baseline,'preflight':preflight,'policy':policy,'instruction':instruction,'journal':journal,'output':output,'variant':args.prompt_variant,'stage':args.execution_stage}

def verify_local_sources(plan,args):
    """Hash original weights and the actual installed native render/generate code."""
    folder=Path(args.model_path);controls=plan['configuration']['controls']
    if not folder.is_dir():raise ValueError('Existing local artifact required; downloads forbidden')
    for name,expected in controls['adapter_controls']['source_artifact_sha256'].items():
        path=(folder/name).resolve();path.relative_to(folder.resolve())
        import hashlib
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:raise ValueError('SemIf artifact changed: '+name)
    pre=plan['preflight']
    if pre['artifact_revision']!=args.revision:raise ValueError('Preflight revision differs')
    if g.sha((folder/'download-manifest.json').read_bytes())!=pre['artifact_manifest_sha256']:raise ValueError('Artifact manifest differs')
    source=pre['source_hashes'];required=('mlx_backend.py','generate.py','tokenizer_utils.py')
    for name in required:
        found=[(Path(p),sha) for p,sha in source.items() if Path(p).name==name]
        if len(found)!=1 or g.sha(found[0][0].read_bytes())!=found[0][1]:raise ValueError('Native source changed: '+name)
    from semif_phase1 import mlx_backend
    backend=Path(mlx_backend.__file__).resolve()
    expected=next(Path(p).resolve() for p in source if Path(p).name=='mlx_backend.py')
    if backend!=expected:raise ValueError('Different native backend imported')
    import importlib.util
    spec=importlib.util.find_spec('mlx_lm')
    if spec is None or Path(spec.origin).parent.resolve()!=next(Path(p).parent.resolve() for p in source if Path(p).name=='generate.py'):raise ValueError('Different MLX-LM package selected')
    if {p:importlib.metadata.version(p) for p in pre['runtime_versions']}!=pre['runtime_versions']:raise ValueError('Tokenizer/runtime changed')

def exact_token_check(plan,args,tok):
    from specialist_benchmark import generated_messages
    pre=plan['preflight'];c=plan['configuration'];records=[]
    config=json.loads((Path(args.model_path)/'config.json').read_text())
    if config['text_config']['max_position_embeddings']!=c['controls']['context_tokens']:raise ValueError('Artifact context differs')
    for variant in ('P0','P1','P2'):
        saved=pre['conditions'][variant]['records']
        if [x['id'] for x in saved]!=[x['id'] for x in plan['rows']]:raise ValueError('Complete180 token measurements required')
        for row,evidence in zip(plan['rows'],saved):
            messages=generated_messages(row['feedback'],plan['policy'],variant,c['parent_baseline_id'])
            prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
            guard=tok.encode(prompt);add=tok.bos_token is None or not prompt.startswith(tok.bos_token);ids=tok.encode(prompt,add_special_tokens=add)
            actual={'messages_sha256':g.canonical(messages),'rendered_prompt_sha256':g.sha(prompt.encode()),'guard_input_tokens':len(guard),'generation_input_tokens':len(ids),'generation_token_ids_sha256':g.sha(json.dumps(ids).encode()),'generation_add_special_tokens':add}
            if guard!=ids or any(evidence.get(k)!=v for k,v in actual.items()):raise ValueError('Exact native guard/generation token mismatch')
            if len(guard)>4096 or len(ids)+2048>c['controls']['context_tokens']:raise ValueError('Unchanged context/reserve exceeded')
            if variant==plan['variant']:records.append({'id':row['id'],**actual})
    return {'adapter':ADAPTER,'condition':plan['variant'],'measured_utc':utc(),'manifest':plan['manifest_binding'],'exact_rendered_tokens_verified':True,'records':records,'historical_P0_evidence':'Source reconstruction only; no historical generated-message/count parity claimed.','reference_labels_read':False}

def parse(text,ended):
    if not ended:return None
    try:return json.loads(text)
    except (ValueError,TypeError):return None

def inspect_smoke(plan,args,tok):
    from specialist_benchmark import generated_messages
    root=plan['root'];path=getattr(args,'smoke_inspection',None);sha=getattr(args,'smoke_inspection_sha256',None)
    if not path or not sha:raise ValueError('Development requires independent smoke inspection')
    spec={'file':str(Path(path).resolve().relative_to(root.resolve())),'sha256':sha};inspection=g.json_bound(spec,root);raw=lines(g.bound(inspection['raw_attempts'],root))
    if inspection['raw_attempts']!=binding(root/plan['condition']['output_paths']['smoke'],root) or inspection.get('manifest')!=plan['manifest_binding'] or inspection.get('condition')!=plan['variant'] or not inspection.get('inspector'):raise ValueError('Smoke inspection identity differs')
    when=g.stamp(inspection['inspected_utc'])
    if not g.stamp(plan['manifest']['frozen_utc'])<when<=g.stamp(utc()) or len(raw)!=3 or len(inspection['records'])!=3:raise ValueError('Inspection chronology/coverage differs')
    for row,expected,declared,evidence in zip(raw,plan['rows'][:3],inspection['records'],plan['preflight']['conditions'][plan['variant']]['records']):
        if row['id']!=expected['id'] or row.get('execution_stage')!='smoke' or row.get('execution_manifest')!=plan['manifest_binding'] or row.get('native_controls')!=plan['configuration']['controls']:raise ValueError('Smoke execution identity differs')
        if controls_from_baseline(row,plan['configuration']['controls']['context_tokens'])!=row['native_controls']:raise ValueError('Observed smoke runtime differs')
        if not g.stamp(plan['manifest']['frozen_utc'])<=g.stamp(row['started_utc'])<=g.stamp(row['finished_utc'])<when:raise ValueError('Smoke inspection predates output')
        messages=generated_messages(expected['feedback'],plan['policy'],plan['variant'],plan['configuration']['parent_baseline_id']);prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        if row['messages']!=messages or row['generated_request_sha256']!=g.canonical(messages) or row['rendered_prompt_sha256']!=g.sha(prompt.encode()) or row['input_tokens']!=evidence['generation_input_tokens']:raise ValueError('Smoke exact request differs')
        pieces=row.get('stream_events',[])
        if not pieces or pieces[-1]['finish_reason']!='stop' or pieces[-1]['token'] not in row['eos_token_ids'] or any(x['prompt_tokens']!=row['input_tokens'] for x in pieces):raise ValueError('Native smoke truncation/token mismatch')
        rawtext=''.join(x['text'] for x in pieces)
        if row['raw_response']!={'content':rawtext,'finish_reason':'stop'}:raise ValueError('Native raw response mirror differs')
        prediction=parse(rawtext,True);status='ok' if valid(prediction) else 'invalid_output'
        if any(row[k]!=v for k,v in [('prediction',prediction),('status',status)]) or any(declared.get(k)!=row[k] for k in ['id','status','prediction']):raise ValueError('Strict smoke parse differs')
        if status=='invalid_output' and not(declared.get('accepted_unchanged') is True and declared.get('failure_class')=='intrinsic_schema' and declared.get('inspection_reason')):raise ValueError('Intrinsic failure requires unchanged acceptance')
    return spec


def execute(args,root):
    from specialist_benchmark import generated_messages
    plan=load_plan(args,root);verify_local_sources(plan,args)
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(args.model_path,local_files_only=True)
    measured=exact_token_check(plan,args,tok);output=plan['output'];root=plan['root'];c=plan['configuration'];controls=c['controls']
    preflight=output.with_name(output.name+'.token-preflight.json');exclusive(preflight,measured)
    if plan['stage']=='development':
        inspection=inspect_smoke(plan,args,tok);claim=schedule.claim(plan['manifest']['schedule'],plan['journal'],c['id'],plan['variant'],'inspected_admission',root)
        schedule.finish(plan['manifest']['schedule'],plan['journal'],claim['attempt_id'],'completed',[inspection,binding(preflight,root),plan['manifest_binding']],root)
    claim=schedule.claim(plan['manifest']['schedule'],plan['journal'],c['id'],plan['variant'],plan['stage'],root)
    events=output.with_name(output.name+'.events.jsonl');terminal=output.with_name(output.name+'.terminal.json');count=0;completed=False
    try:
        from semif_phase1 import mlx_backend as backend
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        started=time.perf_counter();model,native_tok,metadata=backend.load_model(args.model_path,args.revision,args.bits);load_seconds=time.perf_counter()-started
        expected_meta=plan['baseline'][0]['metadata'];actual_meta=dict(metadata,enable_thinking=False,max_tokens=2048,temperature=0)
        if actual_meta!=expected_meta:raise ValueError('Effective native metadata differs from P0')
        # Check the actual MLX tokenizer wrapper as well as the offline HF one.
        exact_token_check(plan,args,native_tok)
        with output.open('x') as out,events.open('x') as journal:
            for row,evidence in zip(plan['rows'][:args.limit],measured['records']):
                messages=generated_messages(row['feedback'],plan['policy'],plan['variant'],c['parent_baseline_id']);prompt=native_tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                if g.sha(prompt.encode())!=evidence['rendered_prompt_sha256'] or len(native_tok.encode(prompt))!=evidence['generation_input_tokens']:raise ValueError('Live native prompt differs from preflight')
                rec={'id':row['id'],'requested_model':args.model_path,'artifact_revision':args.revision,'surface':'semif local specialist','mode':'generated','host':platform.platform(),'runtime_versions':controls['runtime'],'config_note':args.config_note,'model_load_seconds':load_seconds,'input_sha256':g.sha(row['feedback'].encode()),'policy_sha256':g.sha(plan['policy'].encode()),'request_sha256':g.canonical(make_payload(row['feedback'],plan['policy'],'not-sent','official')),'request_hash_limitation':'Legacy intent hash retained; generated_request_sha256 binds actual messages.','generated_request_sha256':g.canonical(messages),'messages':messages,'rendered_prompt_sha256':evidence['rendered_prompt_sha256'],'input_tokens':evidence['generation_input_tokens'],'metadata':actual_meta,'attempts':1,'execution_manifest':plan['manifest_binding'],'execution_stage':plan['stage'],'native_controls':controls,'schedule_attempt_id':claim['attempt_id'],'reference_labels_read':False,'prompt_variant':compose_instruction(g.bound(c['baseline_instruction'],root).decode(),plan['variant'],role='system',parent_baseline_id=c['parent_baseline_id'],root=root)['audit'],'started_utc':utc()}
                journal.write(json.dumps({'event':'started','id':row['id'],'utc':rec['started_utc'],'generated_request_sha256':rec['generated_request_sha256']})+'\n');journal.flush();os.fsync(journal.fileno());start=time.perf_counter()
                try:
                    pieces=list(stream_generate(model,native_tok,prompt,max_tokens=2048,sampler=make_sampler(temp=0)))
                    stream=[{k:getattr(x,k) for k in ['text','token','from_draft','prompt_tokens','generation_tokens','finish_reason']} for x in pieces]
                    raw=''.join(x.text for x in pieces);finish=pieces[-1].finish_reason if pieces else None;prediction=parse(raw,finish=='stop')
                    rec.update(raw_response={'content':raw,'finish_reason':finish},stream_events=stream,eos_token_ids=list(native_tok.eos_token_ids),prediction=prediction,status='ok' if valid(prediction) else 'invalid_output',output_tokens=pieces[-1].generation_tokens if pieces else 0)
                    if any(x.prompt_tokens!=rec['input_tokens'] for x in pieces):raise ValueError('Actual native generation token count differs')
                except Exception as exc:rec.update(prediction=None,status='service_error',error_type=type(exc).__name__,error=str(exc)[:500])
                rec.update(elapsed_seconds=time.perf_counter()-start,finished_utc=utc());out.write(json.dumps(rec)+'\n');out.flush();os.fsync(out.fileno());count+=1
                journal.write(json.dumps({'event':'finished','id':row['id'],'utc':rec['finished_utc'],'status':rec['status']})+'\n');journal.flush();os.fsync(journal.fileno());print(row['id'],rec['status'],flush=True)
                if rec['status']=='service_error' or rec.get('raw_response',{}).get('finish_reason')!='stop':break
            completed=count==args.limit and rec['status']!='service_error' and rec.get('raw_response',{}).get('finish_reason')=='stop'
    except BaseException as exc:
        exclusive(terminal,{'status':'stopped','exception':type(exc).__name__,'error':str(exc)[:500],'records_saved':count,'utc':utc(),'manifest':plan['manifest_binding']});schedule.finish(plan['manifest']['schedule'],plan['journal'],claim['attempt_id'],'stopped',[binding(terminal,root),binding(preflight,root)],root);raise
    exclusive(terminal,{'status':'completed' if completed else 'stopped','records_saved':count,'utc':utc(),'manifest':plan['manifest_binding']})
    schedule.finish(plan['manifest']['schedule'],plan['journal'],claim['attempt_id'],'completed' if completed else 'stopped',[binding(output,root),binding(events,root),binding(terminal,root),binding(preflight,root)],root)
