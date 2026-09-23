#!/usr/bin/env python3
"""Pinned local AnyJev raw/L0 comparison; no calibration, training or generation."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import time
from development_benchmark import ROOT, KEYS, VALUES, digest, read_rows, valid
from specialist_benchmark import decision_rows

SOURCE_REVISION = '3cd8c6fcd9e90fc04214575ade6779da1e3f3704'


def question_specs(policy):
    # Policy lives in each question so content-free probes remove only feedback,
    # not the rubric. Static criterion labels are not per-record reference labels.
    return [{'id': r['id'], 'text': policy + '\n\n' + r['question'],
             'options': [o['id'] + ': ' + o['description'] for o in r['options']]}
            for r in decision_rows('', policy)]


def make_questions(policy, question_class):
    return [question_class.choice(r['text'], r['options'], name=r['id'])
            for r in question_specs(policy)]


def make_decider(backend, level, decider_class):
    if level not in ('raw', 'L0'):
        raise ValueError('Only label-free raw and L0 are allowed')
    return decider_class(backend, level=level, prior='content_free', prior_strength=1.0,
                        shared_prefix=False, adaptive_shifts=False, adapt=False)


def extract_prediction(result, questions, level):
    if result.level != level:
        raise ValueError('Unexpected result level')
    if len(result) != len(KEYS):
        raise ValueError('Unexpected number of decisions')
    prediction = {}
    for q in questions:
        d = result[q.id]
        probs = [float(p) for p in d.probs]
        if d.level != level or len(probs) != len(VALUES[q.id]):
            raise ValueError('Invalid decision level or option count')
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in probs) or abs(sum(probs)-1) > 1e-6:
            raise ValueError('Invalid probability distribution')
        prediction[q.id] = VALUES[q.id][max(range(len(probs)), key=probs.__getitem__)]
    if not valid(prediction):
        raise ValueError('Invalid prediction')
    return prediction


def verify_artifact(folder, revision):
    folder = Path(folder)
    manifest = json.loads((folder/'download-manifest.json').read_text())
    if manifest['sha'] != revision:
        raise ValueError('Artifact revision mismatch')
    files = manifest['siblings']
    if not any(f['rfilename'].endswith('.safetensors') for f in files):
        raise ValueError('No causal model weights declared')
    for f in files:
        p = folder/f['rfilename']
        if not p.is_file() or p.stat().st_size != f['size']:
            raise ValueError('Incomplete artifact: '+f['rfilename'])
        expected = f.get('lfs', {}).get('sha256')
        if expected:
            actual = hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
        else:
            expected = f.get('blobId')
            data = p.read_bytes()
            actual = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if not expected or actual != expected:
            raise ValueError('Artifact checksum mismatch: '+f['rfilename'])
    architectures = json.loads((folder/'config.json').read_text()).get('architectures', [])
    if not architectures or any(not a.endswith('ForCausalLM') for a in architectures):
        raise ValueError('A causal-LM artifact is required; classifier weights are not interchangeable')
    return manifest


def guarded_backend_class(base):
    class GuardedBackend(base):
        def next_token_logprobs(self, prompts, token_ids):
            counts = [len(self.tokenizer.encode(p, add_special_tokens=False)) for p in prompts]
            if any(n > self.context_limit for n in counts):
                raise ValueError('Full AnyJev input exceeds context; truncation forbidden')
            self.prompt_token_counts.extend(counts)
            return super().next_token_logprobs(prompts, token_ids)
    return GuardedBackend


def verify_source(source):
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
    if revision != SOURCE_REVISION:
        raise ValueError('AnyJev source revision mismatch')
    dirty = subprocess.check_output(['git','-C',str(source),'status','--porcelain'], text=True).strip()
    if dirty:
        raise ValueError('AnyJev source has uncommitted files')
    return revision


def run(args):
    if Path(args.output).exists():
        raise FileExistsError(args.output)
    source = Path(args.source).resolve()
    revision = verify_source(source)
    manifest = verify_artifact(args.model_path, args.revision)
    sys.path.insert(0, str(source))
    from anyjev import Decider, Question
    from anyjev.backends.hf import HFBackend
    import anyjev
    if not Path(anyjev.__file__).resolve().is_relative_to(source):
        raise ValueError('Unexpected AnyJev import source')
    start = time.perf_counter()
    backend = guarded_backend_class(HFBackend)(args.model_path, device=args.device,
                    dtype=args.dtype, batch_size=args.batch_size)
    backend.context_limit = min(args.max_context, backend.model.config.max_position_embeddings)
    backend.prompt_token_counts = []
    actual_device = str(next(backend.model.parameters()).device)
    if not actual_device.startswith(args.device):
        raise ValueError('Unexpected backend device fallback')
    load_seconds = time.perf_counter()-start
    policy = (ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    questions = make_questions(policy, Question)
    versions = {p: importlib.metadata.version(p) for p in ['torch','transformers','numpy']}
    with open(args.output, 'x') as out:
        for row in read_rows(ROOT/'data/pilot/inputs.jsonl')[:args.limit]:
            decider = make_decider(backend, args.level, Decider)  # fresh state/probe cache per record
            backend.prompt_token_counts = []
            record = dict(id=row['id'], requested_model=manifest['repo'], artifact_revision=args.revision,
                          surface='AnyJev local transformers', level=args.level,
                          source_revision=revision, policy_sha256=digest(policy),
                          input_sha256=digest(row['feedback']), question_specs_sha256=digest(json.dumps(question_specs(policy),sort_keys=True)),
                          host=platform.platform(), config_note=args.config_note, runtime_versions=versions,
                          device=actual_device, dtype=str(next(backend.model.parameters()).dtype), quantization='none',
                          batch_size=args.batch_size, max_context=backend.context_limit, model_load_seconds=load_seconds,
                          prior='content_free', prior_applied=args.level=='L0', prior_strength=1.0, shared_prefix=False, adaptive_shifts=False,
                          score_interpretation='Normalized label-token ranking scores; not calibrated correctness probabilities',
                          prompt_placement='Full rubric in user question; native AnyJev decision system instruction',
                          fresh_decider_per_record=True, reference_labels_used=False, calibration_artifacts_loaded=False,
                          attempts=1, started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
            start = time.perf_counter()
            try:
                result = decider.decide({'feedback':row['feedback']}, questions, level=args.level)
                record.update(prediction=extract_prediction(result,questions,args.level),status='ok',
                              raw_response=result.to_dict(), diagnostics={d.question.id:d.diagnostics for d in result},
                              backend_stats=dict(decider.stats), prompt_token_counts=list(backend.prompt_token_counts))
            except Exception as exc:
                record.update(prediction=None,status='service_error',error_type=type(exc).__name__,error=str(exc)[:500])
            record['elapsed_seconds']=time.perf_counter()-start
            out.write(json.dumps(record,default=lambda value:value.tolist())+'\n');out.flush();print(row['id'],record['status'],flush=True)
            if record['status']!='ok':break


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True)
    p.add_argument('--model-path',required=True)
    p.add_argument('--revision',required=True)
    p.add_argument('--level',required=True,choices=['raw','L0'])
    p.add_argument('--device',choices=['cpu','mps'],required=True)
    p.add_argument('--dtype',choices=['float32','bfloat16'],required=True)
    p.add_argument('--batch-size',type=int,default=4)
    p.add_argument('--max-context',type=int,default=4096)
    p.add_argument('--limit',type=int,choices=range(1,61),default=3)
    p.add_argument('--output',required=True)
    p.add_argument('--config-note',required=True)
    a=p.parse_args()
    if a.batch_size<1 or a.max_context<1:p.error('Positive batch size and context required')
    run(a)

if __name__=='__main__':main()
