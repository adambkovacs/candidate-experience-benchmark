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


def control_messages(feedback,policy):
    p=make_payload(feedback,policy,'not-sent','generated-off')
    messages=p['messages']
    messages[0]['content']+='\nRequired JSON schema: '+json.dumps(p['response_format']['json_schema']['schema'])
    return messages


def parse_generated(text,ended):
    if not ended:return None
    try:prediction=json.loads(text)
    except (ValueError,TypeError):return None
    return prediction if valid(prediction) else None


def run(args):
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
            messages=control_messages(row['feedback'],policy)
            rec=dict(id=row['id'],requested_model=manifest['repo'],artifact_revision=args.revision,
                     surface='Matched HF generated JSON control; not AnyJev readout',
                     device=actual_device,dtype=str(next(model.parameters()).dtype),quantization='none',
                     host=platform.platform(),config_note=args.config_note,runtime_versions=versions,
                     model_load_seconds=load_seconds,policy_sha256=digest(policy),input_sha256=digest(row['feedback']),
                     request_sha256=digest(json.dumps(messages,sort_keys=True)),enable_thinking=False,
                     do_sample=False,max_new_tokens=args.max_new_tokens,max_input_tokens=args.max_input_tokens,attempts=1,
                     prompt_placement='Rubric and JSON schema in system message; differs from AnyJev question prompt',
                     started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
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
    a=p.parse_args()
    if a.max_input_tokens<1 or a.max_new_tokens<1:p.error('Positive token limits required')
    run(a)

if __name__=='__main__':main()
