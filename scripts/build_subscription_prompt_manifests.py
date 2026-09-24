"""Prepare subscription prompt shards from a full frozen roster, entirely offline.

No references, model calls, or baseline reruns. Strict raw baseline auditing may
leave a named parent blocked; the global roster and its condition order remain.
Codex catalogue source is an explicitly labelled context-field projection of the
local official cache, retaining its original SHA but excluding identity/prompts.
"""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
import prompt_admission as admission
import prompt_execution_gates as g
import evaluate_prompt_variants as evaluator
from frozen_prompt_variants import compose_instruction


def binding(path,root):
    path=Path(path).resolve();return {'file':str(path.relative_to(root.resolve())),'sha256':g.sha(path.read_bytes())}


def write(path,value,root,text=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as output:output.write(value if text else json.dumps(value,indent=2)+'\n')
    return binding(path,root)


def read_rows(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def catalogue_projection(cache,output,root):
    raw=cache.read_bytes();data=json.loads(raw)
    names={'gpt-6-astra','gpt-6-sol','gpt-6-luna','gpt-5.6-luna','gpt-5.6-sol','gpt-5.6-terra'}
    rows=[{k:r.get(k) for k in ('slug','context_window','effective_context_window_percent','max_context_window')} for r in data['models'] if r['slug'] in names]
    if {r['slug'] for r in rows}!=names:raise ValueError('Required Codex models missing from official cache')
    projection=write(output/'codex-context-source-projection.json',{'kind':'official_codex_context_projection_v1','original_cache_sha256':g.sha(raw),'original_fetched_at':data.get('fetched_at'),'projection_fields':['slug','context_window','effective_context_window_percent','max_context_window'],'models':rows,'limitations':'Only context fields copied from local official cache. Original identity and model instruction text excluded; this is not the full cache.'},root)
    catalogue=write(output/'codex-context-catalogue.json',{'kind':'codex_context_catalogue_v1','source':'official_codex_cli_models_cache','source_sha256':projection['sha256'],'source_representation':'context-field projection, not full original cache','original_cache_sha256':g.sha(raw),'models':rows},root)
    return {'kind':'codex_catalogue_v1','catalogue':catalogue,'raw_catalogue':projection},rows


def prepare_parent(entry,roster_entry,root,out,inputs,context_source,context_rows):
    parent=entry['configuration'];cid=roster_entry['id'];parent_id=roster_entry['parent_baseline_id']
    adapter='codex_batch_v1' if parent['model'].startswith('gpt-') else 'claude_batch_v1'
    extractor=evaluator.extract_codex_controls if adapter=='codex_batch_v1' else evaluator.extract_claude_controls
    auditor=evaluator.audit_codex_batches if adapter=='codex_batch_v1' else evaluator.audit_claude_batches
    rawfiles=parent.get('raw_batch_attempt_files')
    if not rawfiles:raise ValueError('Batch raw attempt sources unavailable')
    snapshot={item['file']:item['sha256'] for item in entry['evidence'] if item.get('available')}
    used=[*rawfiles,parent['predictions_file']]
    for name in used:
        if name not in snapshot or binding(root/name,root)['sha256']!=snapshot[name]:raise ValueError('Source snapshot mismatch: '+name)
    rows=[r for name in rawfiles for r in read_rows(root/name)]
    if not rows:raise ValueError('No historical attempts')
    controls=extractor(rows[0])
    policy=(root/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if adapter=='codex_batch_v1':
        from codex_benchmark import baseline_instruction
        base=baseline_instruction(policy,'batch10')
    else:base=rows[0]['request']['system']
    retries=[];seen=set()
    for row in rows:
        ids=tuple(row['record_order'] if adapter=='codex_batch_v1' else row['ids'])
        aid=(row.get('attempt_id') or str(row.get('id'))+'@'+str(row.get('started_utc'))) if adapter=='codex_batch_v1' else row.get('attempt_id',row.get('batch_id'))
        if ids in seen:retries.append(aid)
        seen.add(ids)
    predictions=read_rows(root/parent['predictions_file'])
    if len(predictions)!=60 or {r['id'] for r in predictions}!={r['id'] for r in inputs}:raise ValueError('Parent prediction coverage is not exactly60')
    # Retrospective retry IDs retain already performed attempts; this never
    # authorizes a new retry or silently selects a different P0 result.
    audited=auditor(rows,{r['id']:r for r in predictions},{r['id']:r for r in inputs},base,controls,'latest_chronological',retries)
    representative=next((r for r in rows if r.get('status')=='ok' and r.get('raw_events')),None)
    if representative is None:raise ValueError('No successful raw native usage evidence')
    directory=out/cid;directory.mkdir()
    historical=write(directory/'historical-context-usage-attempt.jsonl',json.dumps(representative)+'\n',root,text=True)
    source_audit=write(directory/'parent-evidence-audit.json',{'parent_baseline_id':parent_id,'adapter':adapter,'raw_attempt_sources':[binding(root/f,root) for f in rawfiles],'predictions':binding(root/parent['predictions_file'],root),'strict_raw_audit_passed':True,'retained_attempts':len(audited),'historical_retry_ids':retries,'selection':'latest_chronological','representative_source_index':rows.index(representative),'representative_is_only_for_context_and_usage_not_coverage':True,'reference_labels_read':False},root)
    if adapter=='codex_batch_v1':
        model_context=next(r for r in context_rows if r['slug']==parent['model']);context=model_context['context_window']*model_context['effective_context_window_percent']//100
        reserve=None;context_evidence=context_source;timeout=controls['controller_timeout_seconds'];role='cli_combined_prompt'
    else:
        native=representative['model_usage'][parent['model']];context=native['contextWindow'];reserve=native['maxOutputTokens'];context_evidence={'kind':'saved_attempt_context_v1','raw_attempts':historical};timeout=600;role='system'
    generic={'model':parent['model'],'model_revision':None,'quantization':None,'runtime':representative['cli_version'],'hardware':{'provider':None,'client':None,'limitation':'Historical subscription batch controller did not record hardware'},'effort':parent['effort'],'sampling':{'temperature':None,'seed':None,'source':'unchanged subscription defaults; values not exposed'},'output_method':'CLI structured batch schema','parsing':'strict JSON batch; no repair','retry_policy':'Stop on first non-ok batch; no automatic controller retries. Preserve historical explicit retries.','context_tokens':context,'output_reserve_tokens':reserve,'adapter_controls':controls}
    if adapter=='codex_batch_v1':generic['output_reserve_source']='unexposed_cli_default_unchanged'
    else:generic['output_reserve_source']='saved native modelUsage.maxOutputTokens; unchanged CLI default ceiling'
    ch=g.canonical(generic)
    config={'id':cid,'parent_baseline_id':parent_id,'role':role,'baseline_instruction':write(directory/'P0-instruction.txt',base,root,text=True),'parent_baseline':write(directory/'parent.json',{'id':parent_id,'context_unit':'batch10','controls_sha256':ch,'baseline_instruction_sha256':g.sha(base.encode()),'evidence_audit':source_audit},root),'controls':generic,'controls_sha256':ch,'controller':binding(root/'scripts'/('codex_batch_benchmark.py' if adapter=='codex_batch_v1' else 'claude_batch_benchmark.py'),root),'controller_timeout_seconds':timeout,'batch_membership':[[r['id'] for r in inputs[i:i+10]] for i in range(0,60,10)],'conditions':{}}
    context_spec=write(directory/'advertised-context.json',context_evidence,root)
    history_spec=write(directory/'historical-usage.json',{'kind':'saved_attempt_usage_v1','raw_attempts':historical},root)
    groups=[inputs[:3],*[inputs[i:i+10] for i in range(0,60,10)]]
    for variant in ('P1','P2'):
        instruction=compose_instruction(base,variant,role=role,parent_baseline_id=parent_id,root=root)['instruction']
        instruction_spec=write(directory/(variant+'-instruction.txt'),instruction,root,text=True)
        evidence={'adapter':adapter,'condition':variant,'parent_baseline_id':parent_id,'controls_sha256':ch,'instruction_sha256':g.sha(instruction.encode()),'inputs_sha256':binding(root/'data/pilot/inputs.jsonl',root)['sha256'],'schema_sha256':binding(root/'schemas/judgments.schema.json',root)['sha256'],'prospective_rendered_tokens':None,'unknown_reason':'Subscription provider scaffold and exact prospective rendered token count are not exposed; observational comparison only.','advertised_context':context_spec,'historical_usage':history_spec,'requests':[]}
        for n,group in enumerate(groups):
            payload=admission.expected_request(adapter,instruction,group,generic)
            request=write(directory/(variant+'-request-'+str(n).zfill(2)+'.json'),payload,root)
            evidence['requests'].append({'record_ids':[r['id'] for r in group],'client_request':request,'request_bytes':len(g.bound(request,root))})
        config['conditions'][variant]={'instruction':instruction_spec,'observational_evidence':write(directory/(variant+'-observational-evidence.json'),evidence,root)}
    return config


def build(root,freeze_path,cache,out):
    root=Path(root).resolve();out=Path(out).resolve();out.relative_to(root)
    if out.exists():raise FileExistsError('Use a new preparation output directory')
    freeze=json.loads(Path(freeze_path).read_text())
    if freeze.get('contract')!='prompt-global-roster-v1':raise ValueError('Full frozen roster required')
    source=g.json_bound(freeze['source_snapshot'],root)
    inventory=g.json_bound(freeze['source_inventory'],root);roster=g.json_bound(freeze['roster'],root);g.json_bound(freeze['schedule'],root)
    inputs=read_rows(root/'data/pilot/inputs.jsonl')
    if [r.get('id') for r in inputs]!=[f'DEV-{n:03}' for n in range(1,61)] or any(set(r)!={'id','feedback'} for r in inputs):raise ValueError('Existing input-only development60 required')
    out.mkdir(parents=True)
    context_source,context_rows=catalogue_projection(Path(cache),out,root)
    entries={e['id']:e for e in source['configurations']};prepared=[];blocked=[]
    for roster_entry in roster['entries']:
        if roster_entry['state']!='scheduled':continue
        entry=entries[roster_entry['parent_baseline_id']];model=entry['configuration'].get('model','')
        if not model.startswith(('gpt-','claude-')):continue
        try:
            config=prepare_parent(entry,roster_entry,root,out,inputs,context_source,context_rows)
            manifest={'contract':'prompt-execution-gates-v1','frozen_utc':datetime.now(timezone.utc).isoformat(),'global_roster_freeze':binding(Path(freeze_path),root),'inputs':binding(root/'data/pilot/inputs.jsonl',root),'schema':binding(root/'schemas/judgments.schema.json',root),'prompt_bundle':binding(root/'prompts/variants-v1/manifest.json',root),'roster':freeze['roster'],'source_inventory':freeze['source_inventory'],'schedule':freeze['schedule'],'execution_journal':freeze['execution_journal'],'manifest_scope':[config['id']],'configurations':[config]}
            # Every smoke request is validated offline before exposing a shard.
            for variant in ('P1','P2'):admission.admit_smoke(manifest,root,config['id'],variant)
            spec=write(out/config['id']/'execution-manifest.json',manifest,root)
            prepared.append({'id':config['id'],'parent_baseline_id':config['parent_baseline_id'],'manifest':spec,'model':model,'effort':config['controls']['effort'],'runtime':config['controls']['runtime'],'adapter':context_source if False else ('codex_batch_v1' if model.startswith('gpt-') else 'claude_batch_v1')})
        except (ValueError,KeyError,TypeError,StopIteration) as exc:
            blocked.append({'id':roster_entry['id'],'parent_baseline_id':roster_entry['parent_baseline_id'],'reason':str(exc),'next_step':'Review preserved parent evidence; do not rerun or fabricate missing evidence automatically.'})
    result={'status':'offline_prepared_not_run','global_roster_freeze':binding(Path(freeze_path),root),'prepared':prepared,'blocked':blocked,'inference_performed':False,'reference_labels_read':False}
    write(out/'preparation-index.json',result,root)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--roster-freeze',type=Path,required=True);p.add_argument('--codex-cache',type=Path,required=True);p.add_argument('--output-directory',type=Path,required=True);a=p.parse_args()
    result=build(a.root,a.roster_freeze,a.codex_cache,a.output_directory)
    print(json.dumps({'prepared':len(result['prepared']),'blocked':result['blocked'],'inference_performed':False}))
if __name__=='__main__':main()
