#!/usr/bin/env python3
"""Codex subscription batch workflow; only policy and fictional inputs enter requests."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from development_benchmark import ROOT, KEYS, digest, read_rows, valid
import codex_benchmark as single


def batch_schema(rows):
    schema=json.loads((ROOT/'schemas/judgments.schema.json').read_text())
    schema['properties']['id']={'type':'string','enum':[r['id'] for r in rows]}
    schema['required']=['id',*KEYS]
    return {'type':'object','properties':{'records':{'type':'array','items':schema,
            'minItems':len(rows),'maxItems':len(rows)}},'required':['records'],'additionalProperties':False}


def batch_prompt(policy, rows, variant=None, parent_baseline_id=None):
    instruction,_=single.variant_instruction(policy,'batch10',variant,parent_baseline_id)
    return instruction+'\n'+json.dumps({'records':[{'id':r['id'],'feedback':r['feedback']} for r in rows]})


def parse_batch(raw, rows):
    value=json.loads(raw)
    if not isinstance(value,dict) or set(value)!={'records'} or not isinstance(value['records'],list):
        raise ValueError('Invalid batch envelope')
    records=value['records']
    if len(records)!=len(rows) or any(not isinstance(r,dict) or set(r)!={'id',*KEYS} or not isinstance(r.get('id'),str) for r in records):
        raise ValueError('Invalid batch record shape/count')
    if len({r['id'] for r in records})!=len(records) or {r['id'] for r in records}!={r['id'] for r in rows}:
        raise ValueError('Missing, duplicate or unexpected batch IDs')
    predictions={r['id']:{k:r[k] for k in KEYS} for r in records}
    if not all(valid(p) for p in predictions.values()):raise ValueError('Invalid judgments')
    return predictions


def select_inputs(rows, offset, limit):
    if type(offset) is not int or type(limit) is not int or offset < 0 or limit < 1 or offset+limit > 60:
        raise ValueError('Requested offset/limit must select1–60 records within development60')
    if len(rows)!=60 or len({row['id'] for row in rows})!=60:
        raise ValueError('Expected60 unique development input IDs')
    selected=rows[offset:offset+limit]
    if not selected or len(selected)!=limit:raise ValueError('Empty or incomplete batch selection')
    return selected


def durable_write(file, value):
    file.write(json.dumps(value)+'\n');file.flush();os.fsync(file.fileno())


def run(args):
    if single.variant_gate_or_preview(args,'batch10'):return
    single.validate_model_effort(args.model,args.effort)
    env=single.clean_environment()
    auth=subprocess.run([args.codex,'login','status'],env=env,capture_output=True,text=True)
    if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout+auth.stderr:
        raise RuntimeError('ChatGPT subscription authentication required')
    version=subprocess.run([args.codex,'--version'],env=env,capture_output=True,text=True,check=True).stdout.strip()
    record_offset=getattr(args,'offset',0)
    if record_offset % args.batch_size:raise ValueError('Continuation offset must align with configured batch size')
    rows=select_inputs(read_rows(ROOT/'data/pilot/inputs.jsonl'),record_offset,args.limit)
    if any(set(r)!={'id','feedback'} for r in rows):raise ValueError('Unexpected input metadata')
    policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    output=Path(args.output);attempt_path=Path(args.attempts);journal_path=Path(str(attempt_path)+'.journal.jsonl')
    if any(p.exists() for p in (output,attempt_path,journal_path)):raise FileExistsError('Output, attempts and journal must all be new')
    with output.open('x') as out, attempt_path.open('x') as attempts, journal_path.open('x') as journal:
        for offset in range(0,len(rows),args.batch_size):
            batch=rows[offset:offset+args.batch_size]
            batch_id='batch-'+str((record_offset+offset)//args.batch_size+1).zfill(2)
            schema=batch_schema(batch);prompt=batch_prompt(policy,batch,getattr(args,'prompt_variant',None),getattr(args,'parent_baseline_id',None))
            _,variant_audit=single.variant_instruction(policy,'batch10',getattr(args,'prompt_variant',None),getattr(args,'parent_baseline_id',None))
            attempt={'id':batch_id,'phase':args.phase,'workflow':'codex-subscription-batch',
                'requested_model':args.model,'returned_model':None,'effort':args.effort,'cli_version':version,
                'batch_size':len(batch),'configured_batch_size':args.batch_size,'controller_timeout_seconds':args.timeout,'record_order':[r['id'] for r in batch],
                'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'request_sha256':digest(prompt),
                'request':{'prompt':prompt,'output_schema':schema},'schema_sha256':digest(json.dumps(schema,sort_keys=True)),
                'policy_sha256':digest(policy),'reference_labels_read':False,'auth_mode':'ChatGPT',
                'billing_note':'Existing subscription only; API keys stripped. No paid API fallback or credit redemption.',
                'isolation_note':'Fresh ephemeral batch context; builtin CLI scaffold remains. Records share context inside batch; this is distinct from independent record inference.'}
            if variant_audit is not None:attempt['prompt_variant']=variant_audit
            start=time.perf_counter();predictions={}
            with tempfile.TemporaryDirectory(prefix='recruitment-codex-batch-',dir='/private/tmp') as temp:
                cwd=Path(temp);schema_path=cwd/'schema.json';schema_path.write_text(json.dumps(schema))
                cmd=single.command(args.codex,args.model,args.effort,cwd,schema_path)
                attempt['command']=cmd
                durable_write(journal,{'event':'request_started',**attempt})
                try:
                    process=subprocess.run(cmd,input=prompt,env=env,cwd=cwd,text=True,capture_output=True,timeout=args.timeout)
                    raw=(cwd/'response.json').read_text() if (cwd/'response.json').exists() else ''
                    parsed=single.parse_result(process.returncode,process.stdout,raw)
                    attempt.update(parsed,raw_stderr=process.stderr)
                    if parsed['status'] in ('service_error','isolation_violation'):
                        raise RuntimeError('Batch transport or isolation failure')
                    predictions=parse_batch(raw,batch)
                    attempt['status']='ok'
                except subprocess.TimeoutExpired as exc:
                    decode=lambda x:x.decode(errors='replace') if isinstance(x,bytes) else (x or '')
                    attempt.update(status='service_error',error_type='TimeoutExpired',raw_stdout=decode(exc.stdout),raw_stderr=decode(exc.stderr),raw_response=(cwd/'response.json').read_text() if (cwd/'response.json').exists() else '')
                except (ValueError,RuntimeError) as exc:
                    if attempt.get('status') not in ('service_error','isolation_violation'):attempt['status']='invalid_output'
                    attempt['error']=str(exc)
            elapsed=time.perf_counter()-start;attempt['elapsed_seconds']=elapsed
            durable_write(attempts,attempt)
            durable_write(journal,{'event':'request_completed','id':batch_id,'status':attempt['status'],'elapsed_seconds':elapsed})
            for position,row in enumerate(batch):
                record={'id':row['id'],'phase':args.phase,'status':attempt['status'],
                    'prediction':predictions.get(row['id']),'requested_model':args.model,'returned_model':None,
                    'reasoning_effort':args.effort,'surface':'Codex CLI ChatGPT subscription batch workflow',
                    'cli_version':version,'batch_id':batch_id,'batch_size':len(batch),'configured_batch_size':args.batch_size,
                    'batch_position':position,'started_utc':attempt['started_utc'],'batch_elapsed_seconds':elapsed,
                    'elapsed_seconds':elapsed/len(batch),'timing_kind':'amortized_batch_share_not_individual_latency',
                    'batch_attempt_file':str(attempt_path),'input_sha256':digest(row['feedback']),
                    'request_sha256':attempt['request_sha256'],'policy_sha256':attempt['policy_sha256']}
                out.write(json.dumps(record)+'\n')
            out.flush();os.fsync(out.fileno());print(batch_id,attempt['status'],len(batch),round(elapsed,2),flush=True)
            if attempt['status']!='ok':raise RuntimeError('Stopped after failed batch; inspect saved attempt')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--codex',default='/Applications/ChatGPT.app/Contents/Resources/codex')
    p.add_argument('--model',required=True,choices=tuple(single.SUPPORTED_EFFORTS))
    p.add_argument('--effort',required=True,choices=('low','medium','high','xhigh'))
    p.add_argument('--limit',type=int,choices=range(1,61),default=60)
    p.add_argument('--offset',type=int,choices=range(60),default=0)
    p.add_argument('--batch-size',type=int,choices=range(1,11),default=10)
    p.add_argument('--timeout',type=float,default=300)
    p.add_argument('--phase',choices=('smoke','development'),required=True)
    p.add_argument('--output',required=True);p.add_argument('--attempts',required=True)
    single.add_variant_arguments(p)
    run(p.parse_args())

if __name__=='__main__':main()
