#!/usr/bin/env python3
"""Matched causal-model JSON generation control, not an AnyJev decision level."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import time
from anyjev_benchmark import verify_artifact
from development_benchmark import ROOT,digest,read_rows,valid
from jev_benchmark import make_payload


def control_messages(feedback,policy,variant=None,parent_baseline_id=None):
    p=make_payload(feedback,policy,'not-sent','generated-off')
    messages=p['messages']
    messages[0]['content']+='\nRequired JSON schema: '+json.dumps(p['response_format']['json_schema']['schema'])
    messages[0]['content'],_=variant_instruction(messages[0]['content'],variant,parent_baseline_id)
    return messages


def variant_instruction(instruction,variant=None,parent_baseline_id=None):
    if variant is None:
        if parent_baseline_id is not None:raise ValueError('Parent baseline requires explicit prompt variant')
        return instruction,None
    from frozen_prompt_variants import compose_instruction
    result=compose_instruction(instruction,variant,role='system',parent_baseline_id=parent_baseline_id,root=ROOT)
    return result['instruction'],result['audit']


def variant_gate_or_preview(args):
    variant=getattr(args,'prompt_variant',None);parent=getattr(args,'parent_baseline_id',None);destination=getattr(args,'variant_preview_output',None)
    if not destination:
        if variant in ('P1','P2'):raise ValueError('Phase-two protocol gates pending; use offline preview')
        if variant is not None or parent is not None:
            policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
            variant_instruction(control_messages('',policy)[0]['content'],variant,parent)
        return False
    if variant is None:raise ValueError('Preview requires explicit variant')
    rows=read_rows(ROOT/'data/pilot/inputs.jsonl')
    if len(rows)!=60 or [r['id'] for r in rows]!=[f'DEV-{i:03d}' for i in range(1,61)] or any(set(r)!={'id','feedback'} or not isinstance(r['feedback'],str) for r in rows):raise ValueError('Require exact60 input-only records')
    if type(args.limit) is not int or not 1<=args.limit<=60 or args.max_input_tokens<1 or args.max_new_tokens<1:raise ValueError('Invalid limits')
    policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    _,audit=variant_instruction(control_messages('',policy)[0]['content'],variant,parent)
    requests=[{'record_id':r['id'],'messages':control_messages(r['feedback'],policy,variant,parent),'prompt_variant':audit} for r in rows[:args.limit]]
    controls={'model_path':args.model_path,'artifact_revision':args.revision,'device':args.device,'dtype':args.dtype,'quantization':'none','enable_thinking':False,'do_sample':False,'max_new_tokens':args.max_new_tokens,'max_input_tokens':args.max_input_tokens,'add_generation_prompt':True,'add_special_tokens':False,'pad_token_id':'runtime tokenizer pad_token_id or eos_token_id; not resolved offline'}
    with open(destination,'x') as output:
        json.dump({'offline_only':True,'inference_performed':False,'reference_labels_read':False,'surface':'Matched HF generated JSON control; not AnyJev readout','instruction_role':'system','controls':controls,'runtime_identity_status':'configured only; artifact, tokenizer, template and device not loaded or verified','token_context_preflight':'not measured; no chat-template rendering or truncation performed','protocol_gates':'pending; not execution approval','requests':requests},output,indent=2);output.write('\n')
    return True


def parse_generated(text,ended):
    if not ended:return None
    try:prediction=json.loads(text)
    except (ValueError,TypeError):return None
    return prediction if valid(prediction) else None


def run(args):
    if variant_gate_or_preview(args):return
    if Path(args.output).exists():raise FileExistsError(args.output)
    manifest=verify_artifact(args.model_path,args.revision)
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    start=time.perf_counter()
    tok=AutoTokenizer.from_pretrained(args.model_path,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(args.model_path,local_files_only=True,
                    dtype=getattr(torch,args.dtype)).to(args.device).eval()
    actual_device=str(next(model.parameters()).device)
    if not actual_device.startswith(args.device):raise ValueError('Unexpected device fallback')
    load_seconds=time.perf_counter()-start
    policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    versions={p:importlib.metadata.version(p) for p in ['torch','transformers','numpy']}
    with open(args.output,'x') as out:
        for row in read_rows(ROOT/'data/pilot/inputs.jsonl')[:args.limit]:
            messages=control_messages(row['feedback'],policy,getattr(args,'prompt_variant',None),getattr(args,'parent_baseline_id',None))
            _,variant_audit=variant_instruction(control_messages('',policy)[0]['content'],getattr(args,'prompt_variant',None),getattr(args,'parent_baseline_id',None))
            rec=dict(id=row['id'],requested_model=manifest['repo'],artifact_revision=args.revision,
                     surface='Matched HF generated JSON control; not AnyJev readout',
                     device=actual_device,dtype=str(next(model.parameters()).dtype),quantization='none',
                     host=platform.platform(),config_note=args.config_note,runtime_versions=versions,
                     model_load_seconds=load_seconds,policy_sha256=digest(policy),input_sha256=digest(row['feedback']),
                     request_sha256=digest(json.dumps(messages,sort_keys=True)),enable_thinking=False,
                     do_sample=False,max_new_tokens=args.max_new_tokens,max_input_tokens=args.max_input_tokens,attempts=1,
                     prompt_placement='Rubric and JSON schema in system message; differs from AnyJev question prompt',
                     started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
            if variant_audit is not None:rec['prompt_variant']=variant_audit
            start=time.perf_counter()
            try:
                prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                inputs=tok(prompt,return_tensors='pt',add_special_tokens=False)
                n=inputs['input_ids'].shape[1]
                if n>args.max_input_tokens or n+args.max_new_tokens>model.config.max_position_embeddings:
                    raise ValueError('Full prompt or requested completion exceeds context; truncation forbidden')
                with torch.inference_mode():
                    generated=model.generate(**{k:v.to(args.device) for k,v in inputs.items()},
                            do_sample=False,max_new_tokens=args.max_new_tokens,
                            pad_token_id=tok.pad_token_id or tok.eos_token_id)
                ids=generated[0,n:].tolist();raw=tok.decode(ids,skip_special_tokens=True)
                eos=model.generation_config.eos_token_id
                eos=[eos] if isinstance(eos,int) else eos
                ended=bool(ids and ids[-1] in (eos or []))
                prediction=parse_generated(raw,ended)
                rec.update(prediction=prediction,status='ok' if prediction else 'invalid_output',
                           raw_response=raw,input_tokens=n,output_tokens=len(ids),finish_reason='stop' if ended else 'length')
            except Exception as exc:
                rec.update(prediction=None,status='service_error',error_type=type(exc).__name__,error=str(exc)[:500])
            rec['elapsed_seconds']=time.perf_counter()-start
            out.write(json.dumps(rec)+'\n');out.flush();print(row['id'],rec['status'],flush=True)
            if rec['status']=='service_error':break


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-path',required=True);p.add_argument('--revision',required=True)
    p.add_argument('--device',required=True,choices=['cpu','mps'])
    p.add_argument('--dtype',required=True,choices=['float32','bfloat16'])
    p.add_argument('--max-input-tokens',type=int,default=4096);p.add_argument('--max-new-tokens',type=int,default=4096)
    p.add_argument('--limit',type=int,choices=range(1,61),default=3)
    p.add_argument('--output',required=True);p.add_argument('--config-note',required=True)
    p.add_argument('--prompt-variant',choices=('P0','P1','P2'));p.add_argument('--parent-baseline-id');p.add_argument('--variant-preview-output',help='Exclusive offline preview; no model/tokenizer load')
    a=p.parse_args()
    if a.max_input_tokens<1 or a.max_new_tokens<1:p.error('Positive token limits required')
    run(a)

if __name__=='__main__':main()
