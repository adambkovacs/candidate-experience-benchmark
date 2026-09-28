#!/usr/bin/env python3
"""Build a source-bound offline P0 stability report for native AnyJev raw."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import anyjev_raw_repeat_admission as admission
import build_repeat_findings as shared
from anyjev_benchmark import question_specs
from development_benchmark import digest, valid

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('results/repeatability-v1/anyjev-raw-p0-v1')
MANIFEST=BASE/'manifest.json'
MANIFEST_SHA='1748a977513608c0a753f0d64bf98d02ca647ae3c478a8647bf2dac938be8346'
LABELS=Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA=shared.PINNED_SHA[str(LABELS)]
PASSES=('original','repeat2','repeat3')
FIELDS=shared.FIELDS
STATS={'backend_calls':1,'flat_prompts':4,'shared_groups':0,'shared_prompts':0,
       'adaptive_items':0,'adaptive_shifts_total':0}


def path(root,relative):
    target=(Path(root)/relative).resolve()
    target.relative_to(Path(root).resolve())
    return target


def sha(filename):
    with Path(filename).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def rows(root,relative):
    raw=path(root,relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete JSONL evidence: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


def binder(root):
    bindings=[]
    def bind(relative,expected=None):
        relative=Path(relative)
        actual=sha(path(root,relative))
        if expected is not None and actual!=expected:raise ValueError(f'Source hash differs: {relative}')
        item={'path':str(relative),'sha256':actual}
        if item not in bindings:bindings.append(item)
        return item
    return bind,bindings


def source_context(root):
    bind,bindings=binder(root)
    bind(MANIFEST,MANIFEST_SHA)
    plan=json.loads(path(root,MANIFEST).read_text())
    if (plan.get('schema')!='anyjev-raw-native-p0-repeat-admission-v1'
            or plan.get('status')!='offline_frozen_no_inference'
            or plan.get('reference_labels_used') is not False
            or plan.get('schedule')!=['repeat2/P0','repeat3/P0']
            or plan.get('stage_inputs')!={'smoke':{'limit':3},'development':{'limit':60}}
            or plan.get('runtime',{}).get('level')!='raw'
            or plan['runtime'].get('device')!='mps:0'
            or plan['runtime'].get('dtype')!='torch.bfloat16'
            or plan['runtime'].get('batch_size')!=4
            or plan['runtime'].get('max_context')!=4096
            or plan['runtime'].get('quantization')!='none'
            or plan['runtime'].get('shared_prefix') is not False
            or plan['runtime'].get('adaptive_shifts') is not False
            or plan['historical'].get('eligible_as_pass1') is not True):
        raise ValueError('Frozen AnyJev raw plan shape or controls differ')
    sources={Path(name) for name in plan['source_sha256']}
    original_root=next((name.parent.parent for name in sources
                        if name.name=='anyjev_raw_repeat_admission.py' and name.parent.name=='scripts'),None)
    if original_root is None:raise ValueError('Frozen AnyJev source root missing')
    local={};external={}
    for absolute,expected in plan['source_sha256'].items():
        source=Path(absolute)
        try:relative=source.relative_to(original_root)
        except ValueError:external[absolute]=expected
        else:
            bind(relative,expected);local[str(relative)]=expected
    required={'scripts/anyjev_raw_repeat_admission.py','scripts/anyjev_benchmark.py',
              'scripts/specialist_benchmark.py','scripts/jev_benchmark.py',
              'scripts/development_benchmark.py','docs/LABELING_GUIDE.md',
              'data/pilot/inputs.jsonl'}
    if not required<=set(local):raise ValueError('Frozen AnyJev local source proof incomplete')
    bind(LABELS,LABELS_SHA)
    inputs=rows(root,'data/pilot/inputs.jsonl')
    references=rows(root,LABELS)
    ids=[f'DEV-{n:03d}' for n in range(1,61)]
    if ([x.get('id') for x in inputs]!=ids or [x.get('id') for x in references]!=ids
            or [x.get('id') for x in plan['requests']]!=ids
            or any(set(x)!={'id','feedback'} or not isinstance(x['feedback'],str) for x in inputs)
            or any(x.get('review_version')!='0.2' or not valid(x.get('proposed_labels')) for x in references)):
        raise ValueError('AnyJev input or provisional reference membership differs')
    policy=path(root,'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy)!=plan['policy_prefix_sha256']:
        raise ValueError('AnyJev policy differs')
    specs=question_specs(policy)
    if digest(json.dumps(specs,sort_keys=True))!=plan['question_specs_sha256']:
        raise ValueError('AnyJev question specification differs')
    if any(request.get('input_sha256')!=digest(row['feedback']) or
           len(request.get('native_decisions',[]))!=4 or
           any(x.get('id')!=field for x,field in zip(request['native_decisions'],FIELDS))
           for request,row in zip(plan['requests'],inputs)):
        raise ValueError('AnyJev frozen input or native request differs')
    labels={x['id']:x['proposed_labels'] for x in references}
    return plan,ids,labels,specs,external,original_root,bind,bindings


def projected(raw,specs):
    return admission.project_raw(raw,specs)


def timing(records,historical):
    durations=[x.get('elapsed_seconds') for x in records]
    if any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in durations):
        raise ValueError('AnyJev client duration invalid')
    load=records[0].get('model_load_seconds') if historical else None
    if historical and (type(load) not in (int,float) or not math.isfinite(load) or load<0
                       or any(x.get('model_load_seconds')!=load for x in records)):
        raise ValueError('AnyJev historical model-load duration differs')
    tokens=sum(sum(x['prompt_token_counts']) for x in records) if historical else None
    return {'requestCount':len(records),'requestSeconds':durations,
            'requestSecondsTotal':sum(durations),'modelLoadSeconds':load,
            'clientRunSecondsLowerBound':sum(durations)+load if load is not None else None,
            'tokens':{'input_tokens':tokens,'output_tokens':None,'cached_input_tokens':None,
                      'cache_write_input_tokens':None,'reasoning_output_tokens':None},
            'actualCostUsd':None,'costNote':'Local hardware and electricity cost not measured.',
            'inferenceSeconds':None}


def class_counts(indexed,ids):
    return {field:dict(sorted(Counter(indexed[rid]['prediction'][field] for rid in ids
                if shared.outcome(indexed[rid])=='valid').items())) for field in FIELDS}


def historical(root,plan,ids,labels,specs,original_root,bind):
    history=plan['historical'];folder=Path(history['directory'])
    if (history.get('host')!=plan['runtime']['platform']
            or history.get('runtime_versions')!=plan['runtime']['packages']
            or history.get('runner_sha256')!=plan['source_sha256'][str(original_root/'scripts/anyjev_benchmark.py')]):
        raise ValueError('AnyJev historical source or runtime differs')
    for stage in ('smoke','development'):bind(folder/f'{stage}.jsonl',history[f'{stage}_sha256'])
    smoke=rows(root,folder/'smoke.jsonl');development=rows(root,folder/'development.jsonl')
    for records,count in ((smoke,3),(development,60)):
        if len(records)!=count:raise ValueError('Historical AnyJev membership incomplete')
        for record,request in zip(records,plan['requests'][:count]):
            raw=record.get('raw_response')
            if (record.get('id')!=request['id'] or record.get('status')!='ok'
                    or record.get('attempts')!=1 or record.get('prediction')!=projected(raw,specs)
                    or record.get('input_sha256')!=request['input_sha256']
                    or record.get('policy_sha256')!=plan['policy_prefix_sha256']
                    or record.get('question_specs_sha256')!=plan['question_specs_sha256']
                    or record.get('prompt_token_counts')!=[x['input_tokens'] for x in request['native_decisions']]
                    or record.get('backend_stats')!=STATS
                    or record.get('requested_model')!=plan['model_id']
                    or record.get('artifact_revision')!=plan['artifact_revision']
                    or record.get('host')!=plan['runtime']['platform']
                    or record.get('runtime_versions')!=plan['runtime']['packages']
                    or record.get('device')!='mps:0' or record.get('dtype')!='torch.bfloat16'
                    or record.get('level')!='raw' or record.get('prior_applied') is not False
                    or record.get('fresh_decider_per_record') is not True
                    or record.get('reference_labels_used') is not False):
                raise ValueError(f'Historical AnyJev raw row differs: {request["id"]}')
    indexed={x['id']:x for x in development}
    return {'completionStatus':'complete','score':shared.score(indexed,labels,ids),
            'predictedClassCounts':class_counts(indexed,ids),'usage':timing(development,True),
            'evidence':{'smoke':{'path':str(folder/'smoke.jsonl'),'sha256':history['smoke_sha256']},
                        'records':{'path':str(folder/'development.jsonl'),'sha256':history['development_sha256']},
                        'runnerGitCommit':history['runner_commit'],
                        'runnerSourceSha256':history['runner_sha256']}},indexed


def stage(root,plan,phase,stage_name,specs,bind):
    folder=BASE/phase
    files={key:folder/f'{stage_name}.{suffix}' for key,suffix in
           (('receipt','root-review.json'),('claim','claim.json'),('journal','journal.jsonl'),
            ('raw','raw.jsonl'),('records','records.jsonl'),('completion','completion.json'))}
    evidence={key:bind(filename) for key,filename in files.items()}
    receipt=json.loads(path(root,files['receipt']).read_text())
    claim=json.loads(path(root,files['claim']).read_text())
    completion=json.loads(path(root,files['completion']).read_text())
    if (receipt.get('kind')!='root-reviewed-anyjev-raw-native-p0-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase')!=phase
            or receipt.get('stage')!=stage_name or receipt.get('plan_sha256')!=MANIFEST_SHA
            or claim!={'phase':phase,'stage':stage_name,'plan_sha256':MANIFEST_SHA,
                       'receipt_sha256':evidence['receipt']['sha256'],
                       'policy':'exclusive one attempt; uncertain started positions are not replayed'}
            or completion!={'phase':phase,'stage':stage_name,'plan_sha256':MANIFEST_SHA,
                            'output_sha256':evidence['records']['sha256'],
                            'count':plan['stage_inputs'][stage_name]['limit']}):
        raise ValueError('AnyJev stage admission or completion differs')
    captures=rows(root,files['raw']);records=rows(root,files['records']);journal=rows(root,files['journal'])
    count=plan['stage_inputs'][stage_name]['limit']
    if (len(captures)!=count or len(records)!=count or len(journal)!=2+2*count
            or journal[0]!={'event':'phase_started','phase':phase,'stage':stage_name}
            or journal[-1]!={'event':'phase_completed','count':count}):
        raise ValueError('AnyJev terminal stage membership differs')
    for index,(capture,record,request) in enumerate(zip(captures,records,plan['requests'][:count])):
        started,finished=journal[1+index*2:3+index*2]
        try:prediction=projected(capture.get('raw_response'),specs);status='ok'
        except ValueError:prediction=None;status='invalid_output'
        duration=record.get('elapsed_seconds')
        if (capture.get('id')!=request['id'] or record.get('id')!=request['id']
                or capture.get('request_sha256')!=request['request_sha256']
                or record.get('request_sha256')!=request['request_sha256']
                or capture.get('native_decisions')!=request['native_decisions']
                or capture.get('prompt_token_counts')!=[x['input_tokens'] for x in request['native_decisions']]
                or capture.get('backend_stats')!=STATS
                or record.get('raw_sha256')!=digest(admission.canonical(capture))
                or record.get('status')!=status or record.get('prediction')!=prediction
                or record.get('phase')!=phase or record.get('stage')!=stage_name
                or record.get('attempts')!=1 or record.get('level')!='raw'
                or record.get('input_sha256')!=request['input_sha256']
                or record.get('policy_sha256')!=plan['policy_prefix_sha256']
                or record.get('question_specs_sha256')!=plan['question_specs_sha256']
                or record.get('requested_model')!=plan['model_id']
                or record.get('artifact_revision')!=plan['artifact_revision']
                or record.get('host')!=plan['runtime']['platform']
                or record.get('runtime_versions')!=plan['runtime']['packages']
                or record.get('device')!='mps:0' or record.get('dtype')!='torch.bfloat16'
                or type(duration) not in (int,float) or not math.isfinite(duration) or duration<0
                or started.get('event')!='request_started' or started.get('id')!=request['id']
                or started.get('request_sha256')!=request['request_sha256'] or not started.get('started_utc')
                or finished!={'event':'request_completed','id':request['id'],'status':status}):
            raise ValueError(f'AnyJev raw output binding differs: {request["id"]}')
    return {x['id']:x for x in records},records,captures,evidence


def check_smoke_inspection(root,phase,ids,smoke_records,smoke_evidence,bind):
    folder=BASE/phase
    inspection_path=folder/'smoke-inspection.json'
    inspection_binding=bind(inspection_path)
    inspection=json.loads(path(root,inspection_path).read_text())
    receipt=json.loads(path(root,folder/'development.root-review.json').read_text())
    if (inspection.get('phase')!=phase or inspection.get('plan_sha256')!=MANIFEST_SHA
            or inspection.get('smoke_sha256')!=smoke_evidence['records']['sha256']
            or inspection.get('inspected_ids')!=ids[:3]
            or inspection.get('approved') is not True
            or receipt.get('smoke_inspection_sha256')!=inspection_binding['sha256']
            or any(x.get('status')!='ok' for x in smoke_records)):
        raise ValueError('AnyJev development lacks bound inspected smoke')
    if 'raw_sha256' in inspection and inspection['raw_sha256']!=smoke_evidence['raw']['sha256']:
        raise ValueError('AnyJev inspected smoke raw hash differs')
    return inspection_binding


def closed_repeat(root,plan,phase,ids,labels,specs,bind):
    folder=BASE/phase
    # Do not parse a live or interrupted stage; its final JSONL line may be incomplete.
    if not path(root,folder/'development.completion.json').exists():return None,None
    smoke,smoke_records,smoke_raw,smoke_evidence=stage(root,plan,phase,'smoke',specs,bind)
    indexed,records,captures,development_evidence=stage(root,plan,phase,'development',specs,bind)
    inspection_binding=check_smoke_inspection(root,phase,ids,smoke_records,smoke_evidence,bind)
    return {'completionStatus':'complete','score':shared.score(indexed,labels,ids),
            'predictedClassCounts':class_counts(indexed,ids),
            'usage':repeat_usage(records,captures),
            'evidence':{'smoke':smoke_evidence,'smokeInspection':inspection_binding,
                        'development':development_evidence}},indexed


def repeat_usage(records,captures):
    usage=timing(records,False)
    usage['tokens']['input_tokens']=sum(sum(x['prompt_token_counts']) for x in captures)
    return usage


def stats(values):
    return {'completedPasses':len(values),'values':values,
            'mean':sum(values)/len(values) if len(values)==3 else None,
            'range':[min(values),max(values)] if len(values)==3 else None}


def build(root=ROOT):
    root=Path(root)
    plan,ids,labels,specs,external,original_root,bind,bindings=source_context(root)
    data={name:{} for name in PASSES};indexed={};missing=[]
    data['original']['P0'],indexed['original']=historical(root,plan,ids,labels,specs,original_root,bind)
    previous_open=False
    for name in ('repeat2','repeat3'):
        entry,records=closed_repeat(root,plan,f'{name}/P0',ids,labels,specs,bind)
        if entry is None:
            folder=BASE/name/'P0'
            claimed=any(path(root,folder/f'{stage}.claim.json').exists()
                        for stage in ('smoke','development'))
            missing.append({'pass':name,'condition':'P0',
                            'status':'claimed_in_progress_or_interrupted' if claimed else 'not_started'})
            previous_open=True
        else:
            if previous_open:raise ValueError('Later closed AnyJev pass follows open predecessor')
            data[name]['P0']=entry;indexed[name]=records
    complete=[name for name in PASSES if 'P0' in data[name]]
    scores=[data[name]['P0']['score'] for name in complete]
    ranges={'P0':{'allFour':stats([x['allFour'] for x in scores]),
                  'fields':{field:stats([x['fields'][field] for x in scores]) for field in FIELDS}}}
    flips=[{'condition':'P0','from':left,'to':right,
            **shared.flip(indexed[left],indexed[right],ids)}
           for position,left in enumerate(complete) for right in complete[position+1:]]
    across={}
    if len(complete)==3:
        eligible=[rid for rid in ids if all(shared.outcome(indexed[name][rid])=='valid' for name in complete)]
        across['P0']={'denominator':len(eligible),'excludedIds':[rid for rid in ids if rid not in eligible],
            'fields':{field:[rid for rid in eligible if len({indexed[name][rid]['prediction'][field]
                    for name in complete})>1] for field in FIELDS},
            'fourFieldVector':[rid for rid in eligible if len({tuple(indexed[name][rid]['prediction'][field]
                    for field in FIELDS) for name in complete})>1]}
    return {'schema':'anyjev-raw-native-repeat-findings-v1','configuration':'anyjev-qwen06-raw',
        'displayName':'AnyJev Qwen3 0.6B · raw native readout','model':plan['model_id'],
        'provider':'Local native MPS','method':'native-output-stability','conditionOrder':['P0'],
        'referenceVersion':'0.2','referenceStatus':'AI reviewed provisional, not independent adjudication',
        'denominator':60,'completedConditions':len(complete),'plannedConditions':3,
        'passOrder':list(PASSES),
        'passes':data,'missingPasses':missing,'partialPasses':[],
        'threePassSummary':ranges,'pairwiseFlips':flips,'changesAcrossThreePasses':across,
        'withinPassPromptDeltas':[],'predictedClassCounts':{name:data[name]['P0']['predictedClassCounts'] for name in complete},
        'sourceBindings':bindings,'declaredExternalSourceHashes':external,
        'declaredModelAssetHashes':plan['asset_sha256'],
        'declaredModelArtifactManifestSha256':plan['artifact_manifest_sha256'],
        'declaredAnyJevSourceRevision':plan['source_revision'],
        'interpretation':['This is a native raw option-logit readout with one P0 condition. Matching predictions across passes show observed stability on these comments, not correctness.',
                          'The historical run saved prompt lengths but not prompt hashes. Its prompt identity was reconstructed from pinned source and tokenizer.',
                          'Client request time includes runtime overhead; isolated inference time and local hardware cost are unavailable.'],
        'limitations':['Historical prompts were reconstructed from pinned source and tokenizer; saved rows contain lengths, not prompt hashes.',
                       'Native raw P0 has no generative P1/P2 condition.',
                       'Client wall-clock request time is not isolated inference time.',
                       'Local hardware and electricity costs were not measured.',
                       'Local model assets are declared by the frozen admission manifest; this portable report does not rehash private model files.',
                       'Provisional v0.2 references are not independent adjudication.']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    report=build()
    value=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not args.output.exists() or args.output.read_text()!=value:
            raise ValueError(f'Stale report: {args.output}')
    else:args.output.write_text(value)
    print(f"{report['configuration']} {report['completedConditions']}/3")


if __name__=='__main__':main()
