#!/usr/bin/env python3
"""Gemini subscription preflight and Antigravity stream validator.

Inference is deliberately blocked until Antigravity authentication AND supported
context/tool isolation are verified. This is not a completed inference adapter.
Gemini CLI 0.60.0 was rejected by Google with UNSUPPORTED_CLIENT on 2026-09-21.
Use the official Antigravity client; never route subscription tokens to custom APIs.
Sources:
https://antigravity.google/docs/cli/install
https://antigravity.google/docs/cli/headless/
https://antigravity.google/docs/cli/reference/
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from development_benchmark import valid


def clean_environment(source=None):
    source=os.environ if source is None else source
    return {k:source[k] for k in ('HOME','PATH','TMPDIR','LANG','LC_ALL') if k in source}


def parse_stream(stdout, returncode, requested_model):
    events=[]
    malformed=False
    for line in stdout.splitlines():
        try: events.append(json.loads(line))
        except ValueError: malformed=True
    initial=[e['init'] for e in events if e.get('event')=='init' and isinstance(e.get('init'),dict)]
    results=[e['result'] for e in events if e.get('event')=='result' and isinstance(e.get('result'),dict)]
    calls=[e for e in events if e.get('step_update',{}).get('step_type')=='tool']
    available=initial[0].get('tools') if initial else None
    model=initial[0].get('model') if initial else None
    result=results[0] if len(results)==1 else {}
    prediction=result.get('structured_output')
    status='ok' if valid(prediction) else 'invalid_output'
    if returncode or malformed or len(initial)!=1 or len(results)!=1 or result.get('status')!='SUCCESS':status='service_error'
    if model is not None and model != requested_model:status='model_mismatch'
    if initial and (model is None or available is None):status='unverified_configuration'
    if calls or available:status='isolation_violation'
    return {'status':status,'prediction':prediction,'raw_events':events,
            'requested_model':requested_model,'reported_model':model,
            'served_revision':None,'available_tools':available,'tool_calls':calls,
            'usage':result.get('usage'),'cli_duration_seconds':result.get('duration_seconds')}


def preflight(executable):
    env=clean_environment()
    home=Path(env.get('HOME',str(Path.home())))
    settings_path=home/'.gemini/antigravity-cli/settings.json'
    settings=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    provider=settings.get('modelProvider')
    credits=settings.get('useG1Credits',False)
    if provider not in (None,'','antigravity') or credits is not False:
        raise RuntimeError('Subscription-only preflight requires default Antigravity provider and useG1Credits=false.')
    with tempfile.TemporaryDirectory(dir='/private/tmp',prefix='agy-preflight-') as cwd:
        version=subprocess.run([executable,'--version'],env=env,cwd=cwd,text=True,capture_output=True,timeout=20)
        models=subprocess.run([executable,'models'],env=env,cwd=cwd,text=True,capture_output=True,timeout=30)
    return {'cli_version':version.stdout.strip(),'models_returncode':models.returncode,
            'models_stdout':models.stdout,'models_stderr':models.stderr,
            'credit_overage_enabled':False,'inference_performed':False,
            'status':'blocked','blockers':['Sign in if models command requests authentication.',
            'Supported disabling of global rules, memory, skills, hooks and tools remains unverified.'],
            'notes':'The models command is a client inventory request, not a benchmark prediction.'}


def run(args):
    raise RuntimeError('Gemini inference blocked: Antigravity subscription login and supported context/tool isolation remain unverified. No requests sent.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['preflight','run'])
    p.add_argument('--agy',required=True,help='Path to the official Antigravity CLI binary')
    args=p.parse_args()
    if args.command=='preflight':print(json.dumps(preflight(args.agy),indent=2))
    else:run(args)

if __name__=='__main__':main()
