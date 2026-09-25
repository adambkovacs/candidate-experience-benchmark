#!/usr/bin/env python3
"""One exact Codex subscription repeat lane. Plan is offline; run requires a frozen manifest.

This is deliberately scoped to codex-gpt-6-luna-medium-batch10. It reuses the
historical Codex command, parser and batch composition without touching the old
scheduler or evidence. No API-key environment variables enter the subprocess.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import codex_benchmark as single
import codex_batch_benchmark as batch_runner
import prompt_admission
from development_benchmark import ROOT, digest, read_rows

CONFIG = 'codex-gpt-6-luna-medium-batch10'
BASE = ROOT / 'results/repeatability-v1' / CONFIG
PAIR = f'results/prompt-comparison-v1-2026-09-24/paired-reports/{CONFIG}/paired-manifest.json'
EXECUTION = f'results/prompt-comparison-v1-2026-09-24/subscription-codex-runtime163-v1/{CONFIG}/execution-manifest.json'
COVERAGE = 'results/repeatability-v1/coverage.json'
RUNTIME = 'codex-cli 0.155.0-alpha.16.4'
PREVIOUS_RUNTIME = 'codex-cli 0.155.0-alpha.16.3'
MODEL = 'gpt-6-luna'
EFFORT = 'medium'
TIMEOUT = 600.0
ORDERS = {'repeat2': ['P2', 'P1', 'P0'], 'repeat3': ['P1', 'P0', 'P2']}

def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bound(relative):
    path = ROOT / relative
    return {'path': relative, 'sha256': filehash(path)}

def read_bound(binding):
    path = (ROOT / binding['path']).resolve()
    path.relative_to(ROOT.resolve())
    if filehash(path) != binding['sha256']:
        raise ValueError('Source changed: ' + binding['path'])
    return path.read_bytes()

def durable_line(handle, row):
    handle.write(json.dumps(row, sort_keys=True) + '\n')
    handle.flush()
    os.fsync(handle.fileno())

def plan_data(repeat):
    if repeat not in ORDERS: raise ValueError('Unknown repeat')
    pair = json.loads((ROOT / PAIR).read_text())
    cover = json.loads((ROOT / COVERAGE).read_text())
    entry = next(x for x in cover['groups'] if x['id'] == CONFIG)
    if entry['historical_triple_status'] != 'eligible_first_pass' or entry['observed_condition_order'] != ['P0','P2','P1']:
        raise ValueError('Historical pass or order was amended; re-audit')
    if pair['controls']['cli_version'] != PREVIOUS_RUNTIME or pair['controls']['requested_model'] != MODEL or pair['controls']['effort'] != EFFORT:
        raise ValueError('Original paired controls changed')
    if pair['controls']['controller_timeout_seconds'] != TIMEOUT or pair['controls']['configured_batch_size'] != 10:
        raise ValueError('Batch or timeout changed')
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if len(inputs) != 60 or any(set(x) != {'id','feedback'} for x in inputs): raise ValueError('Input isolation failed')
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    conditions = {}
    sources = [PAIR, EXECUTION, COVERAGE, 'data/pilot/inputs.jsonl', 'docs/LABELING_GUIDE.md',
               'schemas/judgments.schema.json', 'prompts/variants-v1/P1-classifier.txt',
               'prompts/variants-v1/P2-classifier-sop.txt', 'prompts/variants-v1/manifest.json',
               'scripts/codex_benchmark.py', 'scripts/codex_batch_benchmark.py',
               'scripts/prompt_admission.py', 'scripts/codex_repeat_study.py']
    for condition in ('P0','P1','P2'):
        source = pair['conditions'][condition]['request_evidence']
        source_path = source['file']
        if filehash(ROOT / source_path) != source['sha256']: raise ValueError('Historical attempt binding changed')
        original = [json.loads(line) for line in (ROOT / source_path).read_text().splitlines()]
        if len(original) != 6: raise ValueError('Historical condition lacks six batches')
        requests = []
        for idx, old in enumerate(original):
            members = inputs[idx*10:(idx+1)*10]
            variant = None if condition == 'P0' else condition
            parent = None if condition == 'P0' else CONFIG
            prompt = batch_runner.batch_prompt(policy, members, variant, parent)
            schema = batch_runner.batch_schema(members)
            if old['request'] != {'prompt': prompt, 'output_schema': schema} or old['record_order'] != [r['id'] for r in members]:
                raise ValueError('Saved request differs from regenerated frozen request')
            if old['request_sha256'] != digest(prompt) or old['schema_sha256'] != digest(json.dumps(schema,sort_keys=True)):
                raise ValueError('Historical request hash differs')
            expected_runtime = pair.get('historical_controls',pair['controls'])['cli_version'] if condition=='P0' else PREVIOUS_RUNTIME
            if (old['requested_model']!=MODEL or old['effort']!=EFFORT or old['cli_version']!=expected_runtime
                or old['configured_batch_size']!=10 or old['controller_timeout_seconds']!=TIMEOUT
                or old['policy_sha256']!=digest(policy) or old['auth_mode']!='ChatGPT'):
                raise ValueError('Historical request controls differ')
            if old['status'] != 'ok' or old['reference_labels_read'] is not False:
                raise ValueError('Historical pass has unhandled outcome or reference exposure')
            requests.append({'repeat':repeat,'condition':condition,'phase':'development','batch_index':idx+1,
                             'record_ids':[r['id'] for r in members], 'request':old['request'],
                             'request_sha256':old['request_sha256'],'schema_sha256':old['schema_sha256'],
                             'historical_attempt_file_sha256':source['sha256']})
        smoke_members = inputs[:3]
        smoke_prompt = batch_runner.batch_prompt(policy,smoke_members,None if condition=='P0' else condition,None if condition=='P0' else CONFIG)
        smoke_schema = batch_runner.batch_schema(smoke_members)
        smoke = {'repeat':repeat,'condition':condition,'phase':'smoke','batch_index':0,
                 'record_ids':[r['id'] for r in smoke_members],
                 'request':{'prompt':smoke_prompt,'output_schema':smoke_schema},
                 'request_sha256':digest(smoke_prompt),'schema_sha256':digest(json.dumps(smoke_schema,sort_keys=True)),
                 'historical_attempt_file_sha256':source['sha256']}
        conditions[condition] = {'historical_attempts':bound(source_path),'smoke':smoke,'development':requests}
        sources.append(source_path)
    bindings = [bound(path) for path in dict.fromkeys(sources)]
    source_digest = hashlib.sha256(json.dumps(bindings,sort_keys=True).encode()).hexdigest()
    for item in conditions.values():
        for request in [item['smoke'],*item['development']]:request['source_bindings_sha256']=source_digest
    return {'schema':'codex-repeat-study-v1','configuration_id':CONFIG,'repeat':repeat,
            'historical_pass_order':['P0','P2','P1'],'condition_order':ORDERS[repeat],
            'model':MODEL,'effort':EFFORT,'batch_size':10,'timeout_seconds':TIMEOUT,
            'surface':'Codex CLI ChatGPT subscription','reference_labels_read':False,
            'seed_policy':'unchanged CLI default; requested and effective seed unavailable',
            'runtime_amendment':{'from':PREVIOUS_RUNTIME,'to':RUNTIME,
                'basis':'User accepted CLI patch continuation; live help and exact command flags checked on 2026-09-25',
                'limit':'A patch change is recorded, not proven equivalent; hidden CLI wrapper and serving revision remain observational.'},
            'source_bindings':bindings,'conditions':conditions,
            'execution':'fresh ephemeral context per smoke or ten-record batch; stop on first non-ok request; no automatic retry or output repair',
            'inference_performed':False}

def prepare():
    BASE.mkdir(parents=True, exist_ok=True)
    for repeat in ORDERS:
        folder = BASE / repeat
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'manifest.json'
        value = plan_data(repeat)
        raw = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
        with path.open('x') as out:
            out.write(raw)
            out.flush(); os.fsync(out.fileno())
        print(repeat, filehash(path), path)

def verify_manifest(repeat, expected_hash):
    if repeat not in ORDERS: raise ValueError('Unknown repeat')
    path = BASE / repeat / 'manifest.json'
    if filehash(path) != expected_hash: raise ValueError('Manifest hash mismatch')
    manifest = json.loads(path.read_text())
    if manifest['repeat'] != repeat or manifest['configuration_id'] != CONFIG or manifest['condition_order'] != ORDERS[repeat]:
        raise ValueError('Manifest identity or schedule changed')
    for binding in manifest['source_bindings']: read_bound(binding)
    if manifest != plan_data(repeat): raise ValueError('Manifest no longer matches audited sources')
    return manifest

def runtime_check(codex):
    env = single.clean_environment()
    auth = subprocess.run([codex,'login','status'],env=env,capture_output=True,text=True,check=False)
    if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
        raise RuntimeError('ChatGPT subscription authentication required')
    version = subprocess.run([codex,'--version'],env=env,capture_output=True,text=True,check=True).stdout.strip()
    if version != RUNTIME: raise RuntimeError(f'Live CLI {version} differs from explicit repeat amendment {RUNTIME}')
    help_result = subprocess.run([codex,'exec','--help'],env=env,capture_output=True,text=True,check=True)
    for flag in ('--ignore-user-config','--ignore-rules','--ephemeral','--skip-git-repo-check','--sandbox','--json','--color','--cd','--model','--output-schema','--output-last-message'):
        if flag not in help_result.stdout: raise RuntimeError('Live CLI lacks required command flag: ' + flag)
    return env, version

def phase_paths(repeat, condition, phase):
    folder = BASE / repeat / condition
    return folder, folder / f'{phase}.attempts.jsonl', folder / f'{phase}.records.jsonl', folder / f'{phase}.journal.jsonl'

def inspect(manifest, condition, note):
    repeat = manifest['repeat']
    folder, attempts, records, journal = phase_paths(repeat,condition,'smoke')
    receipt = folder / 'smoke-inspection.json'
    if receipt.exists(): raise FileExistsError('Smoke inspection already exists')
    if not note.strip(): raise ValueError('Inspection note required')
    if not all(p.exists() for p in (attempts,records,journal)): raise FileNotFoundError('Smoke evidence incomplete')
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    if [e['event'] for e in events] != ['phase_started','request_started','request_completed','phase_completed']:
        raise ValueError('Smoke journal is not a complete one-request phase')
    rows = [json.loads(line) for line in records.read_text().splitlines()]
    attempt_rows = [json.loads(line) for line in attempts.read_text().splitlines()]
    if len(rows)!=3 or len(attempt_rows)!=1 or attempt_rows[0]['status']!='ok' or any(r['status']!='ok' or not r['prediction'] for r in rows):
        raise ValueError('Three valid smoke records required')
    value={'schema':'codex-repeat-smoke-inspection-v1','repeat':repeat,'condition':condition,
           'inspection':'accepted_unchanged','note':note,'attempts_sha256':filehash(attempts),
           'records_sha256':filehash(records),'journal_sha256':filehash(journal),
           'record_ids':[r['id'] for r in rows]}
    with receipt.open('x') as out:json.dump(value,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
    print(receipt, filehash(receipt))

def require_previous(manifest, condition):
    if manifest['repeat']=='repeat3':
        for prior in ORDERS['repeat2']:
            _, _, _, prior_journal = phase_paths('repeat2',prior,'development')
            if not prior_journal.exists() or json.loads(prior_journal.read_text().splitlines()[-1])['event']!='phase_completed':
                raise ValueError('Repeat two is incomplete: '+prior)
    order = manifest['condition_order']
    if condition not in order: raise ValueError('Condition not scheduled')
    for previous in order[:order.index(condition)]:
        folder, attempts, records, journal = phase_paths(manifest['repeat'],previous,'development')
        if not journal.exists() or json.loads(journal.read_text().splitlines()[-1])['event']!='phase_completed':
            raise ValueError('Previous condition lacks completed development: '+previous)

def run_phase(manifest, condition, phase, codex):
    if condition not in ('P0','P1','P2') or phase not in ('smoke','development'):raise ValueError('Unknown condition or phase')
    require_previous(manifest,condition)
    repeat = manifest['repeat']
    folder, attempts_path, records_path, journal_path = phase_paths(repeat,condition,phase)
    if any(p.exists() for p in (attempts_path,records_path,journal_path)):
        raise FileExistsError('Phase evidence already exists; no implicit retry')
    if phase == 'development':
        receipt = folder / 'smoke-inspection.json'
        if not receipt.exists(): raise ValueError('Inspected smoke required')
        inspection = json.loads(receipt.read_text())
        smoke_folder, smoke_attempts, smoke_records, smoke_journal = phase_paths(repeat,condition,'smoke')
        if inspection['inspection']!='accepted_unchanged' or inspection['attempts_sha256']!=filehash(smoke_attempts) or inspection['records_sha256']!=filehash(smoke_records) or inspection['journal_sha256']!=filehash(smoke_journal):
            raise ValueError('Smoke inspection binding changed')
    env, version = runtime_check(codex)
    requests = [manifest['conditions'][condition]['smoke']] if phase=='smoke' else manifest['conditions'][condition]['development']
    folder.mkdir(parents=True,exist_ok=True)
    claim = folder / f'{phase}.claim.json'
    with claim.open('x') as claimed:
        json.dump({'repeat':repeat,'condition':condition,'phase':phase,'manifest_sha256':filehash(BASE/repeat/'manifest.json'),
                   'claimed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},claimed)
        claimed.write('\n');claimed.flush();os.fsync(claimed.fileno())
    # Exclusive creation plus a started entry makes interruption visible. A stopped
    # phase is never resumed by this runner; a separately reviewed recovery is needed.
    with journal_path.open('x') as journal, attempts_path.open('x') as attempts, records_path.open('x') as records:
        durable_line(journal,{'event':'phase_started','repeat':repeat,'condition':condition,'phase':phase,'runtime':version})
        for request in requests:
            if request['repeat']!=repeat or request['condition']!=condition or request['phase']!=phase: raise ValueError('Request identity mismatch')
            source_digest=hashlib.sha256(json.dumps(manifest['source_bindings'],sort_keys=True).encode()).hexdigest()
            if request['source_bindings_sha256']!=source_digest:
                raise ValueError('Request source bindings changed')
            if digest(request['request']['prompt'])!=request['request_sha256'] or digest(json.dumps(request['request']['output_schema'],sort_keys=True))!=request['schema_sha256']:
                raise ValueError('Request bytes changed')
            with tempfile.TemporaryDirectory(prefix='recruitment-codex-repeat-',dir='/private/tmp') as temp:
                cwd=Path(temp);schema_path=cwd/'schema.json'
                schema_path.write_text(json.dumps(request['request']['output_schema']))
                cmd=single.command(codex,MODEL,EFFORT,cwd,schema_path)
                attempt={'repeat':repeat,'configuration_id':CONFIG,'condition':condition,'phase':phase,
                    'batch_index':request['batch_index'],'record_order':request['record_ids'],
                    'request':request['request'],'request_sha256':request['request_sha256'],
                    'schema_sha256':request['schema_sha256'],'source_bindings':manifest['source_bindings'],
                    'historical_attempt_file_sha256':request['historical_attempt_file_sha256'],
                    'source_bindings_sha256':request['source_bindings_sha256'],
                    'manifest_sha256':filehash(BASE/repeat/'manifest.json'),
                    'workflow':'codex-subscription-batch','requested_model':MODEL,'effort':EFFORT,
                    'cli_version':version,'returned_model':None,'configured_batch_size':10,'batch_size':len(request['record_ids']),
                    'controller_timeout_seconds':TIMEOUT,'auth_mode':'ChatGPT','command':cmd,
                    'reference_labels_read':False,'policy_sha256':digest((ROOT/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]),
                    'billing_note':'ChatGPT subscription only; API keys removed; no overage or credit redemption.',
                    'isolation_note':'Fresh ephemeral batch context; built-in CLI wrapper remains observational.',
                    'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
                durable_line(journal,{'event':'request_started',**attempt})
                start=time.perf_counter()
                try:
                    proc=subprocess.run(cmd,input=request['request']['prompt'],env=env,cwd=cwd,text=True,capture_output=True,timeout=TIMEOUT)
                    raw=(cwd/'response.json').read_text() if (cwd/'response.json').exists() else ''
                    parsed=single.parse_result(proc.returncode,proc.stdout,raw)
                    attempt.update(parsed,raw_stderr=proc.stderr)
                    if parsed['status'] in ('service_error','isolation_violation'):
                        attempt['status']=parsed['status']
                    else:
                        member_rows=[{'id':r['id'],'feedback':r['feedback']} for r in read_rows(ROOT/'data/pilot/inputs.jsonl') if r['id'] in request['record_ids']]
                        try:
                            predictions=batch_runner.parse_batch(raw,member_rows)
                            attempt['status']='ok'
                        except (ValueError,TypeError) as exc:
                            predictions={};attempt['status']='invalid_output';attempt['error']=str(exc)
                    attempt['batch_predictions']=predictions if attempt['status']=='ok' else {}
                except subprocess.TimeoutExpired as exc:
                    decode=lambda value:value.decode(errors='replace') if isinstance(value,bytes) else (value or '')
                    attempt.update(status='service_error',error_type='TimeoutExpired',raw_stdout=decode(exc.stdout),raw_stderr=decode(exc.stderr),
                                   raw_response=(cwd/'response.json').read_text() if (cwd/'response.json').exists() else '',prediction=None,batch_predictions={})
                attempt['elapsed_seconds']=time.perf_counter()-start
                diagnostic=prompt_admission.audit_response(attempt,'codex_batch_v1',258400)
                attempt['response_diagnostic']=diagnostic
                if not diagnostic['passed']:attempt['status']='service_error';attempt['error_type']='PromptContextDiagnostic';attempt['batch_predictions']={}
                durable_line(attempts,attempt)
                durable_line(journal,{'event':'request_completed','repeat':repeat,'condition':condition,'phase':phase,
                                     'batch_index':request['batch_index'],'status':attempt['status'],'elapsed_seconds':attempt['elapsed_seconds']})
                for position,rid in enumerate(request['record_ids']):
                    durable_line(records,{'id':rid,'repeat':repeat,'condition':condition,'phase':phase,
                        'batch_index':request['batch_index'],'batch_position':position,'status':attempt['status'],
                        'prediction':attempt['batch_predictions'].get(rid),'request_sha256':request['request_sha256'],
                        'requested_model':MODEL,'returned_model':None,'reasoning_effort':EFFORT,'cli_version':version,
                        'policy_sha256':attempt['policy_sha256'],'input_sha256':digest(next(r['feedback'] for r in read_rows(ROOT/'data/pilot/inputs.jsonl') if r['id']==rid)),
                        'batch_size':len(request['record_ids']),'configured_batch_size':10,
                        'source_attempt_sha256':request['historical_attempt_file_sha256'],
                        'elapsed_seconds':attempt['elapsed_seconds']/len(request['record_ids']),
                        'timing_kind':'amortized_batch_share_not_individual_latency'})
                if attempt['status']!='ok':
                    durable_line(journal,{'event':'phase_stopped','reason':attempt['status'],'batch_index':request['batch_index']})
                    raise RuntimeError('Phase stopped on first non-ok request; inspect durable evidence')
        durable_line(journal,{'event':'phase_completed','repeat':repeat,'condition':condition,'phase':phase,
                             'request_count':len(requests),'record_count':3 if phase=='smoke' else 60})
    print('completed',repeat,condition,phase)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='action',required=True)
    subs.add_parser('prepare')
    check=subs.add_parser('runtime-check');check.add_argument('--codex',default='/Applications/ChatGPT.app/Contents/Resources/codex')
    for action in ('smoke','inspect','development'):
        p=subs.add_parser(action)
        p.add_argument('--repeat',required=True,choices=tuple(ORDERS))
        p.add_argument('--condition',required=True,choices=('P0','P1','P2'))
        p.add_argument('--manifest-sha256',required=True)
        if action in ('smoke','development'):p.add_argument('--codex',default='/Applications/ChatGPT.app/Contents/Resources/codex')
        else:p.add_argument('--note',required=True)
    args=parser.parse_args()
    if args.action=='prepare':prepare();return
    if args.action=='runtime-check':
        _,version=runtime_check(args.codex);print(version,'ChatGPT subscription auth and required flags present');return
    manifest=verify_manifest(args.repeat,args.manifest_sha256)
    if args.action=='inspect':inspect(manifest,args.condition,args.note)
    else:run_phase(manifest,args.condition,args.action,args.codex)

if __name__=='__main__': main()
