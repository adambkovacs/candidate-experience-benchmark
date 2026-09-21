#!/usr/bin/env python3
"""Local specialist adapters. Every record preserves full feedback and rubric."""
import argparse
import importlib.metadata
import json
import platform
from pathlib import Path
import time
from development_benchmark import ROOT, KEYS, VALUES, digest, read_rows, valid
from jev_benchmark import make_payload, parse_response

class CoverageError(ValueError):
    pass

def decision_rows(feedback, policy):
    p = make_payload(feedback, policy, 'not-sent', 'official')
    return [{'id': k, 'state': p['state'], 'question': p['questions'][k]['instructions'],
             'options': [{'id': label, 'description': desc} for label, desc in p['questions'][k]['criteria'].items()]}
            for k in KEYS]

def nli_pairs(feedback, policy):
    rows = decision_rows(feedback, policy)
    return [(json.dumps(row['state'], ensure_ascii=False),
             'Under the supplied policy, the answer to: ' + row['question'] + ' is ' + opt['id'] + '. ' + opt['description'])
            for row in rows for opt in row['options']]

def check_laya_coverage(agent, state, questions):
    """Compare the native sequence against an explicitly untruncated sequence.

    The upstream builder caps option text at 48 tokens and can shrink options
    even when the combined head fits (it reserves at least 16 instruction tokens).
    Checking only total lengths misses that branch.
    """
    from laya.common import build_sequence, render_options, serialize_state
    tok = agent.tok
    lengths = {}
    for key, question in questions.items():
        q = agent._to_internal(question)
        encode = lambda text: tok(text.replace(tok.mask_token, ' '), add_special_tokens=False)['input_ids']
        head = encode(q['t'] + ' question: ' + str(q['ins']))
        options = [[tok.mask_token_id] + encode(' ' + option) for option in render_options(q)]
        state_ids = encode(serialize_state(state))
        expected = [tok.cls_token_id] + head + [tok.sep_token_id]
        markers = []
        for option in options:
            markers.append(len(expected))
            expected.extend(option)
        expected += [tok.sep_token_id] + state_ids + [tok.sep_token_id]
        actual, actual_markers = build_sequence(tok, state, q,
            agent.cfg.get('max_len', 512), agent.cfg.get('head_max_len', 192))
        lengths[key] = len(expected)
        if actual != expected or actual_markers != markers:
            raise CoverageError('Laya native sequence would truncate or alter full input: ' + key +
                '; full_tokens=' + str(len(expected)) + '; emitted_tokens=' + str(len(actual)) +
                '; option_text_tokens=' + str([len(option)-1 for option in options]) +
                '; head_tokens=' + str(len(head)) + '; max_len=' + str(agent.cfg.get('max_len', 512)) +
                '; head_max_len=' + str(agent.cfg.get('head_max_len', 192)))
    return lengths

def build_runner(args):
    if args.kind == 'semif':
        from semif_phase1 import mlx_backend as m
        model, tok, metadata = m.load_model(args.model_path,args.revision,args.bits)
        def infer(feedback, policy):
            rows=decision_rows(feedback,policy)
            if args.mode=='generated':
                from mlx_lm import stream_generate
                from mlx_lm.sample_utils import make_sampler
                payload=make_payload(feedback,policy,'not-sent','generated-off')
                messages=payload['messages']
                messages[0]['content']+='\nRequired JSON schema: '+json.dumps(payload['response_format']['json_schema']['schema'])
                prompt=tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
                if len(tok.encode(prompt))>args.max_tokens:raise CoverageError('Generated-label prompt exceeds configured context')
                pieces=list(stream_generate(model,tok,prompt,max_tokens=2048,sampler=make_sampler(temp=0)))
                raw=''.join(x.text for x in pieces)
                try:prediction=json.loads(raw)
                except ValueError:prediction=None
                if not pieces or pieces[-1].finish_reason!='stop':prediction=None
                return prediction,{'content':raw,'finish_reason':pieces[-1].finish_reason if pieces else None},dict(metadata,enable_thinking=False,max_tokens=2048,temperature=0)
            if args.mode=='shared': raw,timing=m.score_shared(model,tok,rows,metadata,args.max_tokens)
            elif args.mode=='serial':
                scorer=m.SerialPrefixScorer(model,tok,metadata,args.max_tokens)
                raw=[scorer.score(row) for row in rows]
            else:raw=[m.score(model,tok,row,metadata,args.max_tokens) for row in rows]
            prediction={r['id']:r['option_ids'][max(range(len(r['probabilities'])),key=r['probabilities'].__getitem__)] for r in raw}
            return prediction, {'decisions':raw}, metadata
        return infer
    if args.kind=='laya':
        import laya
        tokenizer_config=Path(args.model_path)/'tokenizer/tokenizer_config.json'
        tokenizer_before=digest(tokenizer_config.read_text())
        agent=laya.load(args.model_path,device=args.device)
        tokenizer_after=digest(tokenizer_config.read_text())
        if str(agent.device)!=args.device:raise RuntimeError('Unexpected device fallback during model load')
        original=dict(agent.cfg)
        if args.mode=='expanded':
            capacity=getattr(agent.model.encoder.config,'max_position_embeddings',0)
            if capacity < 4096:raise CoverageError('Encoder does not support expanded4096 context')
            agent.cfg.update(max_len=4096,head_max_len=512)
        def infer(feedback,policy):
            p=make_payload(feedback,policy,'laya','official')
            lengths=check_laya_coverage(agent,p['state'],p['questions'])
            result=agent.predict(p['state'],p['questions'])
            if str(agent.device)!=args.device:raise RuntimeError('Unexpected runtime device fallback')
            prediction=parse_response(result,'laya-rl-agent')
            return prediction,result,{'original_config':original,'effective_config':agent.cfg,'device':str(agent.device),'dtype':str(agent.dtype),'untruncated_tokens':lengths,
                'tokenizer_config_sha256_before_load':tokenizer_before,'tokenizer_config_sha256_after_load':tokenizer_after,
                'quantization':'none','parameter_dtype':str(next(agent.model.parameters()).dtype),
                'coverage_check':'Exact native sequence and option markers equal full untruncated tokens'}
        return infer
    if args.kind=='alex':
        import sys
        import torch
        sys.path.insert(0,str(Path(args.model_path).parent))
        from modeling_openjev import OpenJevCrossEncoder
        agent=OpenJevCrossEncoder(args.model_path,device=args.device,dtype=torch.float32,bs=4,max_len=4096)
        def infer(feedback,policy):
            pairs=nli_pairs(feedback,policy)
            lengths=[len(agent.tok(agent.template.format(premise=p,hypothesis=h),truncation=False)['input_ids']) for p,h in pairs]
            if max(lengths)>4096:raise CoverageError('NLI input exceeds trained4096-token context')
            probabilities=agent.predict(pairs).tolist()
            result={};offset=0
            for key in KEYS:
                scores=probabilities[offset:offset+len(VALUES[key])]
                result[key]=VALUES[key][max(range(len(scores)),key=lambda i:scores[i][1])]
                offset+=len(scores)
            return result,{'nli_probabilities':probabilities,'hypothesis_order':[(k,v) for k in KEYS for v in VALUES[k]],
                           'mapping':'Highest entailment probability among semantic label hypotheses; NLI neutral is never mapped to insufficient_information'}, {'device':args.device,'dtype':'float32','max_tokens':4096,'input_tokens':lengths,'batch_size':4}
        return infer
    raise ValueError('Unknown specialist')

def run(args):
    if Path(args.output).exists():raise FileExistsError(args.output)
    policy=(ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    rows=read_rows(ROOT/'data/pilot/inputs.jsonl')[:args.limit]
    load_start=time.perf_counter()
    infer=build_runner(args)
    load_seconds=time.perf_counter()-load_start
    versions={}
    for package in ['torch','transformers','mlx','mlx-lm','laya','semif-phase1']:
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:pass
    with open(args.output,'x') as out:
        for row in rows:
            record={'id':row['id'],'requested_model':args.model_path,'artifact_revision':args.revision,
                    'surface':args.kind+' local specialist','mode':args.mode,'host':platform.platform(),
                    'config_note':args.config_note,'runtime_versions':versions,'model_load_seconds':load_seconds,
                    'policy_sha256':digest(policy),'input_sha256':digest(row['feedback']),
                    'request_sha256':digest(json.dumps(make_payload(row['feedback'],policy,'not-sent','official'),sort_keys=True)),
                    'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'attempts':1}
            start=time.perf_counter()
            try:
                prediction,raw,metadata=infer(row['feedback'],policy)
                record.update(prediction=prediction,raw_response=raw,metadata=metadata,status='ok' if valid(prediction) else 'invalid_output')
            except CoverageError as exc:
                record.update(prediction=None,status='unsupported_length',error=str(exc))
            except Exception as exc:
                record.update(prediction=None,status='service_error',error_type=type(exc).__name__,error=str(exc)[:500])
            record['elapsed_seconds']=time.perf_counter()-start
            out.write(json.dumps(record)+'\n');out.flush();print(row['id'],record['status'],flush=True)
            if record['status']=='service_error':break

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',required=True,choices=['semif','laya','alex'])
    p.add_argument('--mode',required=True,choices=['direct','serial','shared','generated','default','expanded','nli'])
    p.add_argument('--model-path',required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--bits',type=int,choices=[4,8])
    p.add_argument('--device',default='mps',choices=['mps','cpu'])
    p.add_argument('--max-tokens',type=int,default=4096)
    p.add_argument('--limit',type=int,default=3,choices=range(1,61))
    p.add_argument('--output',required=True)
    p.add_argument('--config-note',required=True)
    args=p.parse_args()
    allowed={'semif':{'direct','serial','shared','generated'},'laya':{'default','expanded'},'alex':{'nli'}}
    if args.mode not in allowed[args.kind]:p.error('Mode does not match specialist')
    run(args)

if __name__=='__main__':main()
