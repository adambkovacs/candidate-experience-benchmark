#!/usr/bin/env python3
"""Deterministic offline roster snapshot. No references, model calls or freeze."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REGISTRIES=('results/local-run-registry.json','results/codex-run-registry.json','results/claude-subscription-2026-09-21/run-registry.json','results/gemini-run-registry.json','results/openrouter-paid-run-registry.json','results/specialist-run-registry.json')
GENERATED_SPECIALISTS=frozenset(('openjev-generated-off','openjev-generated-on','semif-generated-bf16','anyjev-qwen06-generated-control'))
DIRECT_SPECIALISTS=frozenset(('typesafe-jev113-v2','openjev-fixed','openjev-adaptive','openjev-thinking','semif-direct','semif-serial','semif-shared','alex-openjev08','alex-openjev4b','laya-english','laya-typed','laya-multilingual','laya-english-expanded-cpu','laya-typed-expanded-cpu','laya-multilingual-expanded-cpu','anyjev-qwen06-raw','anyjev-qwen06-l0','anyjev-qwen06-l1','anyjev-qwen06-l2','salesrlagent'))
COMPLETE=frozenset(('complete','completed','complete_with_output_failure','complete_with_service_failure','completed_with_service_failure','completed_with_initialization_retries','completed_after_transport_recovery','completed_after_infrastructure_recovery'))
EVIDENCE_KEYS=('predictions_file','partial_predictions_file','attempt_files','raw_batch_attempt_files','batch_audit_files','smoke_files','request_journal_files','reconciliation_manifest')

def file_bytes(root,relative):
    path=(root/relative).resolve();path.relative_to(root.resolve())
    # The builder never needs these evaluator-owned data sources.
    if path.name in ('proposed_labels.jsonl','pairs.json') or 'reference' in path.name.lower():raise ValueError('Reference evidence is outside roster scope')
    return path.read_bytes()

def method(registry,config):
    ident=config['id']
    if ident=='rules-v1':return 'deterministic_baseline'
    if registry.endswith('specialist-run-registry.json'):
        if ident in GENERATED_SPECIALISTS or ident.startswith('openrouter-'):return 'generative'
        if ident in DIRECT_SPECIALISTS:return 'direct_specialist'
        return 'unknown'
    if registry in REGISTRIES[:-1]:return 'generative'
    return 'unknown'

def build(root=ROOT,registries=REGISTRIES):
    root=Path(root);cache={}
    def evidence(path):
        if path not in cache:
            try:
                raw=file_bytes(root,path);cache[path]=({'file':path,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'available':True},raw)
            except FileNotFoundError:cache[path]=({'file':path,'sha256':None,'available':False,'reason':'Declared file missing'},None)
        return cache[path]
    input_meta,input_raw=evidence('data/pilot/inputs.jsonl');inputs=[json.loads(x) for x in input_raw.decode().splitlines() if x.strip()]
    known={r['id'] for r in inputs}
    if len(inputs)!=60 or len(known)!=60 or any(set(r)!={'id','feedback'} for r in inputs):raise ValueError('Require exact60 input-only records')
    result=[];sources=[];seen=set()
    for registry in registries:
        source,raw=evidence(registry);sources.append(source)
        if raw is None:raise ValueError('Registry missing')
        for index,config in enumerate(json.loads(raw)):
            ident=config['id']
            if ident in seen:raise ValueError('Duplicate configuration ID: '+ident)
            seen.add(ident);kind=method(registry,config);reason=[];paths=[]
            for key in EVIDENCE_KEYS:
                value=config.get(key)
                if isinstance(value,str):paths.append(value)
                elif isinstance(value,list):paths.extend(value)
            artifacts=[evidence(p)[0] for p in sorted(set(paths))]
            coverage={'exact_60_input_ids':False,'prediction_records':0,'valid_status_records':0}
            prediction=config.get('predictions_file')
            if prediction:
                _,rawpred=evidence(prediction)
                if rawpred is not None:
                    records=[json.loads(x) for x in rawpred.decode().splitlines() if x.strip()];ids=[r.get('id') for r in records]
                    coverage={'exact_60_input_ids':len(ids)==60 and len(set(ids))==60 and set(ids)==known,'prediction_records':len(ids),'valid_status_records':sum(r.get('status')=='ok' for r in records)}
                    if any(r.get('phase')=='smoke' for r in records) or 'smoke' in Path(prediction).name:coverage['exact_60_input_ids']=False;reason.append('Smoke evidence cannot serve as development P0')
            effort=config.get('effort')
            if effort in ('max','ultra') or config.get('status')=='excluded_by_user':category='historical_future_exclusion';reason.append('User excluded max/ultra or explicitly disabled this configuration; history retained')
            elif kind in ('direct_specialist','deterministic_baseline'):category=kind;reason.append('Native decision or deterministic method is not converted into a generative prompt experiment')
            elif kind=='unknown':category='pending_method_verification';reason.append('Method classification is unknown; never assumed generative or eligible')
            elif config.get('status') in COMPLETE and coverage['exact_60_input_ids'] and all(a['available'] for a in artifacts):category='eligible_generative_baseline_candidate';reason.append('Complete development60 view available; failures retained. Candidate for evidence review only, not execution eligibility')
            else:category='pending_generative_candidate';reason.append('Registry status: '+str(config.get('status'))+'. Baseline incomplete, unresolved, replaced on another surface, or declared evidence missing; preserve configuration pending reconciliation. Source notes retain the concrete dependency')
            result.append({'id':ident,'source_registry':registry,'source_registry_sha256':source['sha256'],'source_entry_index':index,'configuration':config,'method_class':kind,'draft_category':category,'reasons':reason,'coverage':coverage,'evidence':artifacts,'eligible_paired_comparison':False,'remaining_gates':['baseline scope resolution','exact controls and request evidence audit','reproducible runtime identity','token/context preflight','explicit overlapping-view selection','frozen roster and counterbalanced schedule','condition smoke inspection','quota/destination/budget verification']})
    groups=[['sonnet5-low-first-pass','sonnet5-low-with-retry']]
    # Identical prediction paths are explicit evidence overlap, not independent views.
    by_path={}
    for r in result:
        p=r['configuration'].get('predictions_file')
        if p:by_path.setdefault(p,[]).append(r['id'])
    groups.extend(v for v in by_path.values() if len(v)>1)
    overlaps=[]
    for group in groups:
        members=sorted(set(group)&seen)
        if len(members)<2:continue
        overlaps.append({'members':members,'selection':'unresolved; no primary view selected','reason':'Known alternate attempt views or identical prediction artifact'})
        for row in result:
            if row['id'] in members:
                row['underlying_draft_category']=row['draft_category'];row['draft_category']='overlapping_baseline_view';row['reasons'].append('Alternate views must not count as independent paired experiments')
    return {'version':'prompt-pairing-draft-v1','status':'DRAFT_NOT_FROZEN','inference_performed':False,'reference_labels_read':False,'eligible_paired_comparison':False,'source_registries':sources,'input_source':input_meta,'counts':dict(sorted(Counter(r['draft_category'] for r in result).items())),'configuration_count':len(result),'overlapping_views':overlaps,'configurations':result,'freeze_requirements':'Refresh source hashes after baseline jobs finish or scope is explicitly resolved. Review every entry, select overlapping views, bind exact requests/settings and attempt selection, verify token fit and existing authorization/budget limits without inventing renewed approval, then create a separately versioned frozen manifest and counterbalanced schedule. This draft is not an evaluator manifest or execution approval.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();value=build()
    with open(a.output,'x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'configurations':value['configuration_count'],'counts':value['counts'],'status':value['status']}))
if __name__=='__main__':main()
