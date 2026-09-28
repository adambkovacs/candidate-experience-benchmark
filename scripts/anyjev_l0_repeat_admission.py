#!/usr/bin/env python3
"""Offline-frozen native AnyJev L0 P0 repeats; inference only in an admitted run."""
import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import anyjev_raw_repeat_admission as shared
from anyjev_benchmark import SOURCE_REVISION, make_decider, question_specs, verify_artifact, verify_source
from development_benchmark import ROOT, KEYS, digest, valid

PLAN_PATH=ROOT/'results/repeatability-v1/anyjev-l0-p0-v1/manifest.json'
HISTORY=ROOT/'results/anyjev-qwen06-l0-mps-2026-09-23'
SCHEDULE=('repeat2/P0','repeat3/P0')
HOST_LOCK=shared.HOST_LOCK
LEVEL='L0'
REVISION=shared.REVISION
MODEL=shared.MODEL
SOURCE=shared.SOURCE
PYTHON=shared.PYTHON
STATS={'backend_calls':2,'flat_prompts':56,'shared_groups':0,'shared_prompts':0,
       'adaptive_items':0,'adaptive_shifts_total':0}


def signature(tokenizer,question,prompt,token_ids,kind,shift,probe=None):
    ids=tokenizer.encode(prompt,add_special_tokens=False)
    if len(ids)>4096:raise ValueError('Full AnyJev L0 input exceeds context')
    return {'question':question,'kind':kind,'shift':shift,'probe':probe,
            'prompt_sha256':digest(prompt),'input_ids_sha256':digest(json.dumps(ids)),
            'answer_token_ids':list(token_ids),'input_tokens':len(ids)}


def native_requests(rows,policy,tokenizer):
    """Mirror the pinned Decider's two prompt registries, without model weights."""
    from anyjev.question import Question
    from anyjev.readout import build_prompt,render_chat,resolve_labels,label_ids_for_perm
    from anyjev.calibrate.contextual import DEFAULT_PROBES
    from anyjev.calibrate.permute import cyclic_shifts
    from anyjev.state import render_state
    specs=question_specs(policy)
    questions=[Question.choice(x['text'],x['options'],name=x['id']) for x in specs]
    requests=[]
    for row in rows:
        real=[];probes=[]
        for question in questions:
            labels,ids=resolve_labels(tokenizer,question)
            for shift,perm in enumerate(cyclic_shifts(question.k)):
                answer_ids=label_ids_for_perm(question,ids,perm)
                for probe in DEFAULT_PROBES:
                    prompt=render_chat(tokenizer,build_prompt(probe,question,perm,labels=labels))
                    probes.append(signature(tokenizer,question.id,prompt,answer_ids,'probe',shift,probe))
                prompt=render_chat(tokenizer,build_prompt(render_state({'feedback':row['feedback']}),
                                                       question,perm,labels=labels))
                real.append(signature(tokenizer,question.id,prompt,answer_ids,'real',shift))
        request={'id':row['id'],'input_sha256':digest(row['feedback']),
                 'native_calls':[real,probes]}
        if len(real)+len(probes)!=56:raise ValueError('AnyJev L0 prompt count differs')
        request['request_sha256']=digest(shared.canonical(request))
        requests.append(request)
    return requests


def project_l0(raw,specs):
    if not isinstance(raw,dict) or raw.get('level')!='L0':
        raise ValueError('Native L0 level differs')
    questions=raw.get('questions')
    if not isinstance(questions,dict) or set(questions)!=set(KEYS):
        raise ValueError('Native L0 question set differs')
    prediction={}
    for spec in specs:
        item=questions[spec['id']];options=spec['options']
        distribution=item.get('distribution') if isinstance(item,dict) else None
        if (not isinstance(item,dict) or item.get('kind')!='choice' or item.get('level')!='L0'
                or not isinstance(distribution,dict) or set(distribution)!=set(options)):
            raise ValueError('Native L0 option identity differs')
        values=[distribution[option] for option in options]
        if (any(type(x) not in (int,float) or not math.isfinite(x) or x<0 or x>1 for x in values)
                or abs(sum(values)-1)>1e-6):
            raise ValueError('Native L0 distribution invalid')
        winner=options[max(range(len(values)),key=values.__getitem__)]
        confidence=item.get('confidence')
        if (item.get('answer')!=winner or type(confidence) not in (int,float)
                or not math.isfinite(confidence) or abs(confidence-max(values))>1e-9):
            raise ValueError('Native L0 answer/confidence differs')
        prediction[spec['id']]=winner.split(': ',1)[0]
    if not valid(prediction):raise ValueError('Native L0 projection invalid')
    return prediction


def check_history(root,rows,policy,requests,versions,manifest):
    specs=question_specs(policy);question_hash=digest(json.dumps(specs,sort_keys=True))
    config=None;hashes={}
    for stage,count in (('smoke',3),('development',60)):
        path=root/'results/anyjev-qwen06-l0-mps-2026-09-23'/f'{stage}.jsonl'
        saved=shared.read_jsonl(path)
        if len(saved)!=count:raise ValueError('Historical L0 stage is incomplete')
        for index,(record,request) in enumerate(zip(saved,requests),1):
            row_config={key:record.get(key) for key in ('requested_model','artifact_revision',
                'surface','level','source_revision','host','runtime_versions','device','dtype',
                'quantization','batch_size','max_context','prior','prior_applied','prior_strength',
                'shared_prefix','adaptive_shifts','fresh_decider_per_record',
                'reference_labels_used','calibration_artifacts_loaded','prompt_placement')}
            if config is None:config=row_config
            expected_counts=[x['input_tokens'] for call in request['native_calls'] for x in call]
            if (record.get('id')!=request['id'] or record.get('status')!='ok'
                    or record.get('attempts')!=1 or record.get('input_sha256')!=request['input_sha256']
                    or record.get('policy_sha256')!=digest(policy)
                    or record.get('question_specs_sha256')!=question_hash
                    or record.get('prompt_token_counts')!=expected_counts
                    or record.get('backend_stats')!=STATS or row_config!=config
                    or record.get('prediction')!=project_l0(record.get('raw_response'),specs)):
                raise ValueError(f'Historical AnyJev L0 {stage} row {index} fails native parity')
        hashes[f'{stage}_sha256']=shared.file_hash(path)
    if (config['host']!=platform.platform() or config['runtime_versions']!=versions
            or config['requested_model']!=manifest['repo'] or config['artifact_revision']!=REVISION
            or config['surface']!='AnyJev local transformers' or config['level']!='L0'
            or config['source_revision']!=SOURCE_REVISION or config['device']!='mps:0'
            or config['dtype']!='torch.bfloat16' or config['quantization']!='none'
            or config['batch_size']!=4 or config['max_context']!=4096
            or config['prior']!='content_free' or config['prior_applied'] is not True
            or config['prior_strength']!=1.0 or config['shared_prefix'] is not False
            or config['adaptive_shifts'] is not False or config['fresh_decider_per_record'] is not True
            or config['reference_labels_used'] is not False
            or config['calibration_artifacts_loaded'] is not False):
        raise ValueError('Historical AnyJev L0 runtime/control differs')
    return {'directory':'results/anyjev-qwen06-l0-mps-2026-09-23',**hashes,
            'runner_commit':shared.HISTORICAL_RUNNER_COMMIT,'controls':config,
            'eligible_as_pass1':True,
            'parity_limit':'Historical records saved all 56 prompt lengths, not prompt hashes; source/tokenizer reconstruction is pinned.'}


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve()!=PYTHON.resolve():
        raise ValueError('Use pinned specialist-venv Python')
    rows,policy=shared.source_rows(root)
    if verify_source(SOURCE)!=SOURCE_REVISION:raise ValueError('AnyJev source revision changed')
    old=subprocess.check_output(['git','-C',str(root),'show',
        f'{shared.HISTORICAL_RUNNER_COMMIT}:scripts/anyjev_benchmark.py'])
    if hashlib.sha256(old).hexdigest()!=shared.file_hash(root/'scripts/anyjev_benchmark.py'):
        raise ValueError('Historical AnyJev runner differs')
    for path,name in (('scripts/specialist_benchmark.py','decision_rows'),
                      ('scripts/jev_benchmark.py','make_payload')):
        prior=subprocess.check_output(['git','-C',str(root),'show',
            f'{shared.HISTORICAL_RUNNER_COMMIT}:{path}'])
        if shared.function_shape(prior,name)!=shared.function_shape((root/path).read_bytes(),name):
            raise ValueError('Historical native request builder changed')
    manifest=verify_artifact(MODEL,REVISION)
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    sys.path.insert(0,str(SOURCE))
    from transformers import AutoTokenizer
    import anyjev
    if not Path(anyjev.__file__).resolve().is_relative_to(SOURCE):
        raise ValueError('Unexpected AnyJev source')
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True)
    requests=native_requests(rows,policy,tokenizer)
    versions={name:importlib.metadata.version(name) for name in shared.PACKAGES}
    history=check_history(root,rows,policy,requests,versions,manifest)
    sources=[root/name for name in ('scripts/anyjev_l0_repeat_admission.py',
        'scripts/anyjev_raw_repeat_admission.py','scripts/anyjev_benchmark.py',
        'scripts/specialist_benchmark.py','scripts/jev_benchmark.py',
        'scripts/development_benchmark.py','docs/LABELING_GUIDE.md','data/pilot/inputs.jsonl')]
    return {'schema':'anyjev-l0-native-p0-repeat-admission-v1',
        'status':'offline_frozen_no_inference','reference_labels_used':False,
        'source_sha256':{str(path):shared.file_hash(path) for path in sources},
        'source_revision':SOURCE_REVISION,'source_import':str(Path(anyjev.__file__).resolve()),
        'artifact_revision':REVISION,'model_path':str(MODEL),'model_id':manifest['repo'],
        'artifact_manifest_sha256':shared.file_hash(MODEL/'download-manifest.json'),
        'asset_sha256':{x['rfilename']:shared.file_hash(MODEL/x['rfilename']) for x in manifest['siblings']},
        'policy_prefix_sha256':digest(policy),
        'question_specs_sha256':digest(json.dumps(question_specs(policy),sort_keys=True)),
        'requests':requests,'historical':{**history,'runner_sha256':hashlib.sha256(old).hexdigest()},
        'runtime':{'python':str(PYTHON),'platform':platform.platform(),
            'hardware':shared.hardware_identity(),'packages':versions,'device':'mps:0',
            'dtype':'torch.bfloat16','batch_size':4,'max_context':4096,'quantization':'none',
            'level':'L0','prior':'content_free','prior_strength':1.0,
            'probe_order':['N/A','','[MASK]'],'cyclic_shifts':'all options in source order',
            'shared_prefix':False,'adaptive_shifts':False,
            'seed':'no explicit seed; model.eval(), full cyclic shifts and content-free probes',
            'cache':'fresh Decider, content-free probe cache and running prior per record',
            'failure':'one attempt per ID; no retry, fallback or replay after uncertain start'},
        'schedule':list(SCHEDULE),'stage_inputs':{'smoke':{'limit':3},'development':{'limit':60}}}


def verify_plan():
    actual=shared.read_json(PLAN_PATH)
    if actual!=expected_plan():raise ValueError('Frozen AnyJev L0 plan differs')
    return actual,shared.file_hash(PLAN_PATH)


def phase_path(phase):
    if phase not in SCHEDULE:raise ValueError('Phase outside frozen L0 schedule')
    return PLAN_PATH.parent.joinpath(*phase.split('/'))


def verify_output(plan,phase,stage):
    folder=phase_path(phase);count=plan['stage_inputs'][stage]['limit']
    captures=shared.read_jsonl(folder/f'{stage}.raw.jsonl')
    records=shared.read_jsonl(folder/f'{stage}.records.jsonl')
    journal=shared.read_jsonl(folder/f'{stage}.journal.jsonl')
    if (len(captures)!=count or len(records)!=count or not journal
            or journal[-1]!={'event':'phase_completed','count':count}
            or [x.get('event') for x in journal]!=
               ['phase_started']+['request_started','request_completed']*count+['phase_completed']):
        raise ValueError('AnyJev L0 stage incomplete; preserve partial evidence')
    _,policy=shared.source_rows();specs=question_specs(policy)
    for index,(capture,record,request) in enumerate(zip(captures,records,plan['requests'])):
        try:prediction=project_l0(capture.get('raw_response'),specs);status='ok'
        except ValueError:prediction=None;status='invalid_output'
        if (capture.get('id')!=request['id'] or record.get('id')!=request['id']
                or capture.get('request_sha256')!=request['request_sha256']
                or record.get('request_sha256')!=request['request_sha256']
                or capture.get('native_calls')!=request['native_calls']
                or capture.get('prompt_token_counts')!=[x['input_tokens'] for call in request['native_calls'] for x in call]
                or capture.get('backend_stats')!=STATS
                or record.get('raw_sha256')!=digest(shared.canonical(capture))
                or record.get('input_sha256')!=request['input_sha256']
                or record.get('policy_sha256')!=plan['policy_prefix_sha256']
                or record.get('question_specs_sha256')!=plan['question_specs_sha256']
                or record.get('phase')!=phase or record.get('stage')!=stage
                or record.get('requested_model')!=plan['model_id']
                or record.get('artifact_revision')!=plan['artifact_revision']
                or record.get('host')!=plan['runtime']['platform']
                or record.get('runtime_versions')!=plan['runtime']['packages']
                or record.get('device')!=plan['runtime']['device']
                or record.get('dtype')!=plan['runtime']['dtype'] or record.get('level')!='L0'
                or record.get('attempts')!=1 or record.get('status')!=status
                or record.get('prediction')!=prediction
                or journal[1+index*2].get('id')!=request['id']
                or journal[1+index*2].get('request_sha256')!=request['request_sha256']
                or journal[2+index*2].get('id')!=request['id']
                or journal[2+index*2].get('status')!=status):
            raise ValueError(f'AnyJev L0 output binding failed at row {index+1}')
    return shared.file_hash(folder/f'{stage}.records.jsonl')


def check_predecessors(plan,plan_sha,phase):
    for predecessor in plan['schedule'][:plan['schedule'].index(phase)]:
        folder=phase_path(predecessor)
        completion=shared.read_json(folder/'development.completion.json')
        output_hash=verify_output(plan,predecessor,'development')
        if (completion.get('phase')!=predecessor or completion.get('stage')!='development'
                or completion.get('plan_sha256')!=plan_sha
                or completion.get('output_sha256')!=output_hash or completion.get('count')!=60):
            raise ValueError('Predecessor lacks verified L0 development closure')


def check_receipt(plan,plan_sha,phase,stage,receipt_path):
    receipt=shared.read_json(receipt_path)
    if (receipt.get('kind')!='root-reviewed-anyjev-l0-native-p0-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase')!=phase
            or receipt.get('stage')!=stage or receipt.get('plan_sha256')!=plan_sha):
        raise ValueError('Missing exact root-reviewed AnyJev L0 receipt')
    if stage=='development':
        folder=phase_path(phase)
        completion=shared.read_json(folder/'smoke.completion.json')
        smoke_hash=verify_output(plan,phase,'smoke')
        records=shared.read_jsonl(folder/'smoke.records.jsonl')
        inspection_path=folder/'smoke-inspection.json'
        inspection=shared.read_json(inspection_path)
        if (completion.get('phase')!=phase or completion.get('stage')!='smoke'
                or completion.get('plan_sha256')!=plan_sha or completion.get('output_sha256')!=smoke_hash
                or completion.get('count')!=3 or any(x.get('status')!='ok' for x in records)
                or receipt.get('smoke_inspection_sha256')!=shared.file_hash(inspection_path)
                or inspection.get('phase')!=phase or inspection.get('plan_sha256')!=plan_sha
                or inspection.get('smoke_sha256')!=smoke_hash
                or inspection.get('inspected_ids')!=[f'DEV-{i:03d}' for i in range(1,4)]
                or inspection.get('approved') is not True):
            raise ValueError('Development requires exact inspected successful L0 smoke')
    return receipt


def load_backend(plan):
    """Only model-load path, reached after the lock, receipt and exclusive claim."""
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
    sys.path.insert(0,str(SOURCE))
    from anyjev import Decider,Question
    from anyjev.backends.hf import HFBackend
    class CapturingBackend(shared.guarded_backend_class(HFBackend)):
        expected_calls=None
        observed_calls=None
        def next_token_logprobs(self,prompts,token_ids):
            index=len(self.observed_calls)
            expected=self.expected_calls[index] if index<len(self.expected_calls) else []
            actual=[]
            for item,prompt,ids in zip(expected,prompts,token_ids):
                actual.append(signature(self.tokenizer,item['question'],prompt,ids,
                                        item['kind'],item['shift'],item['probe']))
            if actual!=expected or len(prompts)!=len(expected):
                raise ValueError('Native L0 prompt/probe identity differs')
            self.observed_calls.append(actual)
            return super().next_token_logprobs(prompts,token_ids)
    backend=CapturingBackend(str(MODEL),device='mps',dtype='bfloat16',batch_size=4)
    backend.context_limit=min(4096,backend.model.config.max_position_embeddings)
    backend.prompt_token_counts=[]
    if (backend.context_limit!=4096 or str(next(backend.model.parameters()).device)!='mps:0'
            or str(next(backend.model.parameters()).dtype)!='torch.bfloat16'):
        raise ValueError('Loaded L0 backend differs from frozen controls')
    _,policy=shared.source_rows()
    questions=[Question.choice(x['text'],x['options'],name=x['id']) for x in question_specs(policy)]
    return backend,Decider,questions


def _run_locked(plan,plan_sha,phase,stage,receipt_path):
    if phase not in plan['schedule'] or stage not in ('smoke','development'):
        raise ValueError('Stage outside frozen AnyJev L0 schedule')
    check_predecessors(plan,plan_sha,phase)
    check_receipt(plan,plan_sha,phase,stage,receipt_path)
    folder=phase_path(phase);folder.mkdir(parents=True,exist_ok=True)
    if any((folder/f'{stage}.{suffix}').exists() for suffix in
           ('claim.json','journal.jsonl','raw.jsonl','records.jsonl','completion.json')):
        raise FileExistsError('AnyJev L0 stage already attempted; no retry')
    shared.durable_write(folder/f'{stage}.claim.json',{'phase':phase,'stage':stage,
        'plan_sha256':plan_sha,'receipt_sha256':shared.file_hash(receipt_path),
        'policy':'exclusive one attempt; uncertain started positions are not replayed'})
    shared.append_row(folder/f'{stage}.journal.jsonl',{'event':'phase_started','phase':phase,'stage':stage})
    backend,decider_class,questions=load_backend(plan)
    rows,policy=shared.source_rows();specs=question_specs(policy)
    count=plan['stage_inputs'][stage]['limit']
    for row,request in zip(rows[:count],plan['requests'][:count]):
        backend.expected_calls=request['native_calls'];backend.observed_calls=[]
        backend.prompt_token_counts=[]
        decider=make_decider(backend,'L0',decider_class)
        shared.append_row(folder/f'{stage}.journal.jsonl',{'event':'request_started','id':row['id'],
            'request_sha256':request['request_sha256'],
            'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        started=time.perf_counter()
        try:
            result=decider.decide({'feedback':row['feedback']},questions,level='L0')
            if backend.observed_calls!=request['native_calls']:
                raise ValueError('Native L0 scoring did not read every expected prompt/probe')
            capture={'id':row['id'],'request_sha256':request['request_sha256'],
                'native_calls':backend.observed_calls,'raw_response':result.to_dict(),
                'diagnostics':{item.question.id:item.diagnostics for item in result},
                'backend_stats':dict(decider.stats),
                'prompt_token_counts':list(backend.prompt_token_counts)}
            capture=json.loads(json.dumps(capture,default=lambda value:value.tolist()))
        except Exception as exc:
            shared.append_row(folder/f'{stage}.journal.jsonl',{'event':'phase_stopped','id':row['id'],
                'error_type':type(exc).__name__,'charge':'not applicable; local inference'})
            raise RuntimeError('AnyJev L0 scoring/capture failed; retain started unknown without replay') from exc
        shared.append_row(folder/f'{stage}.raw.jsonl',capture)
        try:prediction=project_l0(capture['raw_response'],specs);status='ok'
        except ValueError:prediction=None;status='invalid_output'
        record={'id':row['id'],'phase':phase,'stage':stage,'status':status,
            'prediction':prediction,'attempts':1,'request_sha256':request['request_sha256'],
            'input_sha256':request['input_sha256'],'policy_sha256':plan['policy_prefix_sha256'],
            'question_specs_sha256':plan['question_specs_sha256'],
            'requested_model':plan['model_id'],'artifact_revision':plan['artifact_revision'],
            'host':plan['runtime']['platform'],'runtime_versions':plan['runtime']['packages'],
            'device':plan['runtime']['device'],'dtype':plan['runtime']['dtype'],'level':'L0',
            'raw_sha256':digest(shared.canonical(capture)),
            'elapsed_seconds':time.perf_counter()-started}
        shared.append_row(folder/f'{stage}.records.jsonl',record)
        shared.append_row(folder/f'{stage}.journal.jsonl',{'event':'request_completed',
            'id':row['id'],'status':status})
    shared.append_row(folder/f'{stage}.journal.jsonl',{'event':'phase_completed','count':count})
    output_hash=verify_output(plan,phase,stage)
    shared.durable_write(folder/f'{stage}.completion.json',{'phase':phase,'stage':stage,
        'plan_sha256':plan_sha,'output_sha256':output_hash,'count':count})
    return output_hash


def run_stage(plan,plan_sha,phase,stage,receipt_path):
    HOST_LOCK.parent.mkdir(parents=True,exist_ok=True)
    with HOST_LOCK.open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise RuntimeError('Another native phase owns the host lock') from exc
        try:
            current,current_sha=verify_plan()
            if current_sha!=plan_sha or current!=plan:raise ValueError('AnyJev L0 plan changed')
            return _run_locked(plan,plan_sha,phase,stage,receipt_path)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','verify','command','run'))
    parser.add_argument('--phase');parser.add_argument('--stage',choices=('smoke','development'))
    parser.add_argument('--receipt');args=parser.parse_args(argv)
    if args.action=='freeze':
        PLAN_PATH.parent.mkdir(parents=True,exist_ok=True)
        shared.durable_write(PLAN_PATH,expected_plan());print(shared.file_hash(PLAN_PATH));return
    plan,plan_sha=verify_plan()
    if args.action=='verify':print(plan_sha);return
    if args.phase not in plan['schedule'] or args.stage not in ('smoke','development'):
        parser.error('Exact frozen phase and stage required')
    if args.action=='command':
        print(shared.canonical({'phase':args.phase,'stage':args.stage,
            'ids':[x['id'] for x in plan['requests'][:plan['stage_inputs'][args.stage]['limit']]],
            'offline_only':True,'model_path':str(MODEL),'revision':REVISION,'level':'L0'}));return
    if not args.receipt:parser.error('Root-reviewed stage receipt required')
    run_stage(plan,plan_sha,args.phase,args.stage,args.receipt)


if __name__=='__main__':main()
