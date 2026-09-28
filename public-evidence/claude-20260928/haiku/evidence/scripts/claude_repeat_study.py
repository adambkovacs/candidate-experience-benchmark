#!/usr/bin/env python3
"""Frozen, single-configuration Claude Max repeat lane. Prepare is offline.

The only provider action is the explicit smoke/development command after a fresh
operator preflight receipt and immutable manifest have been admitted.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from claude_benchmark import clean_environment, command, require_subscription, safe_diagnostic
from claude_batch_benchmark import batch_schema, parse_batch_result, isolation_ok
from development_benchmark import ROOT, digest, read_rows

CONFIG = 'opus55-medium-batch10'
MODEL = 'claude-opus-5-5'
EFFORT = 'medium'
RUNTIME = '2.1.282 (Claude Code)'
TIMEOUT = 600
BASE = ROOT / 'results/repeatability-v1/claude-opus55-medium-batch10'
COVERAGE = 'results/repeatability-v1/coverage.json'
PAIR = f'results/prompt-comparison-v1-2026-09-24/paired-reports/{CONFIG}/paired-manifest.json'
PREP = f'results/prompt-comparison-v1-2026-09-24/subscription-preparation-v2/{CONFIG}'
ORDERS = {'repeat2':['P2','P1','P0'], 'repeat3':['P1','P0','P2']}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path':relative,'sha256':sha(path)}


def read_bound(binding):
    path = (ROOT / binding['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != binding['sha256']:
        raise ValueError('Frozen source changed: '+binding['path'])
    return path.read_bytes()


def durable(handle, value):
    handle.write(json.dumps(value,sort_keys=True,ensure_ascii=False)+'\n')
    handle.flush()
    os.fsync(handle.fileno())


def capture_text(value):
    if isinstance(value, bytes):
        value=value.decode(errors='replace')
    return safe_diagnostic(value or '')


def save_raw_capture(path, attempt, stdout, stderr, exit_code, timed_out=False):
    # Save observed CLI bytes before trying to parse an envelope. Auth output is
    # handled separately and never enters this evidence file.
    row={'schema':'claude-repeat-raw-capture-v1','repeat':attempt['repeat'],
         'condition':attempt['condition'],'phase':attempt['phase'],
         'batch_index':attempt['batch_index'],'record_ids':attempt['ids'],
         'input_sha256':attempt['input_sha256'],'exit_code':exit_code,
         'timed_out':timed_out,'stdout':capture_text(stdout),'stderr':capture_text(stderr)}
    with path.open('x') as out:
        durable(out,row)
    attempt['raw_capture_file']=path.name
    attempt['raw_capture_sha256']=sha(path)


def plan_data(repeat):
    if repeat not in ORDERS: raise ValueError('Unknown repeat')
    coverage = json.loads((ROOT/COVERAGE).read_text())
    group = next(g for g in coverage['groups'] if g['id']==CONFIG)
    if group['historical_triple_status']!='eligible_first_pass' or group['observed_condition_order']!=['P0','P2','P1'] or any(group['condition_status'][c]!='eligible_first_pass' for c in ('P0','P1','P2')):
        raise ValueError('Historical eligibility changed')
    pair = json.loads((ROOT/PAIR).read_text())
    if pair['controls']['requested_model']!=MODEL or pair['controls']['effort']!=EFFORT or pair['controls']['workflow']!='batch10':
        raise ValueError('Historical controls changed')
    rows = read_rows(ROOT/'data/pilot/inputs.jsonl')
    if len(rows)!=60 or len({r['id'] for r in rows})!=60 or any(set(r)!={'id','feedback'} for r in rows):
        raise ValueError('Input isolation failed')
    sources=[COVERAGE,PAIR,'data/pilot/inputs.jsonl','schemas/judgments.schema.json',
             'scripts/claude_batch_benchmark.py','scripts/claude_benchmark.py','scripts/claude_repeat_study.py',
             f'{PREP}/execution-manifest.json']
    conditions={}
    for condition in ('P0','P1','P2'):
        evidence=pair['conditions'][condition]['request_evidence']
        path=evidence['file']
        if sha(ROOT/path)!=evidence['sha256']: raise ValueError('Historical attempt hash changed')
        old=[json.loads(line) for line in (ROOT/path).read_text().splitlines()]
        if len(old)!=6: raise ValueError('Expected six historical batches')
        sources.append(path)
        instruction=f'{PREP}/{condition}-instruction.txt'
        sources.append(instruction)
        system=(ROOT/instruction).read_text()
        development=[]
        for index, attempt in enumerate(old):
            members=rows[index*10:(index+1)*10]
            ids=[r['id'] for r in members]
            payload=json.dumps({'records':[{'id':r['id'],'feedback':r['feedback']} for r in members]})
            expected={'system':system,'input':json.loads(payload),'schema':batch_schema(ids)}
            if attempt['request']!=expected or attempt['ids']!=ids or attempt['status']!='ok':
                raise ValueError('Historical request or outcome changed')
            if attempt['requested_model']!=MODEL or attempt['effort']!=EFFORT or attempt['batch_size']!=10 or attempt['auth_method']!='claude.ai':
                raise ValueError('Historical batch controls changed')
            if attempt['input_sha256']!=digest(payload) or attempt['policy_sha256']!=digest(system) or attempt['schema_sha256']!=digest(json.dumps(expected['schema'],sort_keys=True)):
                raise ValueError('Historical request digest changed')
            if condition!='P0':
                prep=f'{PREP}/{condition}-request-{index+1:02d}.json'
                sources.append(prep)
                if json.loads((ROOT/prep).read_text())['request']!=expected:
                    raise ValueError('Prepared request differs from historical request')
            development.append({'batch_index':index+1,'record_ids':ids,'request':expected,
                                'input_text':payload,'historical_attempt_sha256':evidence['sha256']})
        ids=[r['id'] for r in rows[:3]]
        smoke_payload=json.dumps({'records':[{'id':r['id'],'feedback':r['feedback']} for r in rows[:3]]})
        smoke={'batch_index':0,'record_ids':ids,'request':{'system':system,'input':json.loads(smoke_payload),'schema':batch_schema(ids)},'input_text':smoke_payload}
        conditions[condition]={'historical_attempts':bound(path),'smoke':smoke,'development':development}
    bindings=[bound(p) for p in dict.fromkeys(sources)]
    return {'schema':'claude-repeat-study-v1','configuration_id':CONFIG,'repeat':repeat,
            'historical_pass_order':['P0','P2','P1'],'condition_order':ORDERS[repeat],
            'model':MODEL,'effort':EFFORT,'batch_size':10,'timeout_seconds':TIMEOUT,
            'runtime_required':RUNTIME,'historical_runtime':pair['controls']['cli_version'],
            'runtime_limitation':'CLI patch differs from historical pass; hidden rendering and serving revision unavailable',
            'seed_policy':'unchanged CLI default; seed unavailable','reference_labels_read':False,
            'source_bindings':bindings,'conditions':conditions,'inference_performed':False,
            'execution':'fresh isolated CLI context per batch; zero controller retries; stop on first non-ok or ambiguous attempt'}


def prepare():
    for repeat in ORDERS:
        folder=BASE/repeat
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/'manifest.json'
        with path.open('x') as out:
            out.write(json.dumps(plan_data(repeat),indent=2,ensure_ascii=False)+'\n')
            out.flush();os.fsync(out.fileno())
        print(repeat,sha(path))


def verify_manifest(repeat,expected_hash):
    path=BASE/repeat/'manifest.json'
    if sha(path)!=expected_hash: raise ValueError('Manifest hash mismatch')
    manifest=json.loads(path.read_text())
    for binding in manifest['source_bindings']:read_bound(binding)
    if manifest!=plan_data(repeat):raise ValueError('Manifest differs from frozen reconstruction')
    return manifest


def preflight(path,expected_hash):
    path=Path(path)
    if not path.is_absolute() or sha(path)!=expected_hash:
        raise ValueError('Root preflight path/hash mismatch')
    x=json.loads(path.read_text())
    if (x.get('operator')!='root' or x.get('cli_version')!=RUNTIME or x.get('auth_method')!='claude.ai'
        or x.get('api_provider')!='firstParty' or x.get('usage_credits_off') is not True
        or x.get('extra_usage_disabled') is not True):
        raise ValueError('Subscription preflight rejected')
    for field in ('session_used_percent','weekly_used_percent'):
        value=x.get(field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<95:
            raise ValueError('Subscription quota admission rejected')
    checked=dt.datetime.fromisoformat(x['checked_utc'].replace('Z','+00:00'))
    age=(dt.datetime.now(dt.timezone.utc)-checked).total_seconds()
    if not 0<=age<=1800:raise ValueError('Subscription preflight is stale')
    return x


def paths(repeat,condition,phase):
    folder=BASE/repeat/condition
    return folder,folder/f'{phase}.claim.json',folder/f'{phase}.attempts.jsonl',folder/f'{phase}.records.jsonl',folder/f'{phase}.journal.jsonl'


def completed(repeat,condition,phase):
    folder,claim,attempts,records,journal=paths(repeat,condition,phase)
    if not all(x.exists() for x in (claim,attempts,records,journal)):return False
    lines=[json.loads(s) for s in journal.read_text().splitlines()]
    return bool(lines and lines[-1].get('event')=='phase_completed')


def require_order(repeat,condition):
    if repeat=='repeat3' and not all(completed('repeat2',c,'development') for c in ORDERS['repeat2']):
        raise ValueError('Repeat two is incomplete')
    for previous in ORDERS[repeat][:ORDERS[repeat].index(condition)]:
        if not completed(repeat,previous,'development'):
            raise ValueError('Previous condition lacks completed development')


def inspect(manifest,condition,note):
    repeat=manifest['repeat']
    folder,claim,attempts,records,journal=paths(repeat,condition,'smoke')
    if not completed(repeat,condition,'smoke'):raise ValueError('Smoke phase incomplete')
    rows=[json.loads(s) for s in records.read_text().splitlines()]
    if len(rows)!=3 or any(r['status']!='ok' for r in rows):raise ValueError('Three valid smoke records required')
    receipt=folder/'smoke-inspection.json'
    with receipt.open('x') as out:
        json.dump({'inspection':'accepted_unchanged','note':note,'attempts_sha256':sha(attempts),'records_sha256':sha(records),'journal_sha256':sha(journal),'inspected_utc':dt.datetime.now(dt.timezone.utc).isoformat()},out,indent=2)
        out.write('\n');out.flush();os.fsync(out.fileno())


def run_phase(manifest,condition,phase,cli,receipt_path,receipt_hash):
    if condition not in ('P0','P1','P2') or phase not in ('smoke','development'):raise ValueError('Unknown phase')
    repeat=manifest['repeat']
    require_order(repeat,condition)
    folder,claim,attempts_path,records_path,journal_path=paths(repeat,condition,phase)
    if any(p.exists() for p in (claim,attempts_path,records_path,journal_path)):
        raise FileExistsError('Existing phase evidence requires review; no retry')
    if phase=='development':
        smoke_folder,_,smoke_attempts,smoke_records,smoke_journal=paths(repeat,condition,'smoke')
        receipt=smoke_folder/'smoke-inspection.json'
        if not receipt.exists():raise ValueError('Inspected smoke required')
        inspection=json.loads(receipt.read_text())
        if inspection['inspection']!='accepted_unchanged' or any(inspection[k]!=sha(p) for k,p in [('attempts_sha256',smoke_attempts),('records_sha256',smoke_records),('journal_sha256',smoke_journal)]):
            raise ValueError('Smoke evidence changed after inspection')
    admission=preflight(receipt_path,receipt_hash)
    # CLI version is observable at dispatch. Do not infer patch compatibility.
    env=clean_environment()
    with tempfile.TemporaryDirectory(dir='/private/tmp') as cwd:
        auth_result=subprocess.run([cli,'--safe-mode','auth','status'],cwd=cwd,env=env,
                                   capture_output=True,text=True,check=True,timeout=30)
        require_subscription(json.loads(auth_result.stdout))
        version=subprocess.run([cli,'--version'],cwd=cwd,env=env,capture_output=True,
                               text=True,check=True,timeout=30).stdout.strip()
    if version!=RUNTIME:raise ValueError('CLI version differs from root preflight')
    folder.mkdir(parents=True,exist_ok=True)
    with claim.open('x') as out:
        json.dump({'repeat':repeat,'condition':condition,'phase':phase,'manifest_sha256':sha(BASE/repeat/'manifest.json'),'preflight_sha256':receipt_hash,'preflight_admitted':True,'usage_credits_off':admission['usage_credits_off'],'cli_version':version,'claimed_utc':dt.datetime.now(dt.timezone.utc).isoformat()},out)
        out.write('\n');out.flush();os.fsync(out.fileno())
    requests=[manifest['conditions'][condition]['smoke']] if phase=='smoke' else manifest['conditions'][condition]['development']
    with attempts_path.open('x') as attempts,records_path.open('x') as records,journal_path.open('x') as journal:
        durable(journal,{'event':'phase_started','repeat':repeat,'condition':condition,'phase':phase})
        for item in requests:
            ids=item['record_ids'];request=item['request'];payload=item['input_text']
            if request['input']!=json.loads(payload):raise ValueError('Manifest payload changed')
            cmd=command(cli,MODEL,EFFORT,request['system'],request['schema'])+['--verbose']
            started=dt.datetime.now(dt.timezone.utc).isoformat()
            durable(journal,{'event':'dispatch_intent','batch_index':item['batch_index'],'record_ids':ids,'started_utc':started})
            attempt={'repeat':repeat,'condition':condition,'phase':phase,'batch_index':item['batch_index'],'ids':ids,'batch_size':len(ids),
                     'workflow':'batch10','requested_model':MODEL,'effort':EFFORT,'cli_version':version,'request':request,
                     'policy_sha256':digest(request['system']),'input_sha256':digest(payload),
                     'schema_sha256':digest(json.dumps(request['schema'],sort_keys=True)),
                     'auth_method':'claude.ai','extra_usage_disabled_operator_verified':True,'controller_retries':0,
                     'cli_internal_retries':'not exposed','started_utc':started}
            start=time.perf_counter()
            try:
                with tempfile.TemporaryDirectory(dir='/private/tmp') as cwd:
                    result=subprocess.run(cmd,input=payload,cwd=cwd,env=env,text=True,capture_output=True,timeout=TIMEOUT)
                raw_path=folder/f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
                save_raw_capture(raw_path,attempt,result.stdout,result.stderr,result.returncode)
                attempt['exit_code']=result.returncode
                attempt['stderr']=capture_text(result.stderr)
                body=json.loads(result.stdout)
                attempt.update(parse_batch_result(body,result.returncode,ids))
                attempt['raw_events']=safe_diagnostic(body)
                if not isolation_ok(attempt):attempt.update(status='service_error',error_type='IsolationIdentityOrBillingGuard')
            except (subprocess.SubprocessError,ValueError,OSError) as exc:
                attempt.update(status='service_error',error_type=type(exc).__name__)
                if isinstance(exc,subprocess.TimeoutExpired):
                    raw_path=folder/f"{phase}.batch-{item['batch_index']:03d}.raw.jsonl"
                    save_raw_capture(raw_path,attempt,exc.stdout,exc.stderr,None,timed_out=True)
                    attempt['partial_stdout']=capture_text(exc.stdout)
                    attempt['partial_stderr']=capture_text(exc.stderr)
            attempt['elapsed_seconds']=time.perf_counter()-start
            durable(attempts,attempt)
            predictions={r['id']:{k:v for k,v in r.items() if k!='id'} for r in attempt.get('prediction',{}).get('records',[])} if attempt['status']=='ok' else {}
            for pos,rid in enumerate(ids):
                durable(records,{'id':rid,'status':attempt['status'],'prediction':predictions.get(rid),'repeat':repeat,'condition':condition,'phase':phase,
                                 'batch_index':item['batch_index'],'batch_position':pos+1,'batch_record_ids':ids,'requested_model':MODEL,'effort':EFFORT,
                                 'elapsed_seconds':attempt['elapsed_seconds']/len(ids),'timing_kind':'amortized_batch_share_not_individual_latency'})
            durable(journal,{'event':'request_completed','batch_index':item['batch_index'],'status':attempt['status'],'completed_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
            if attempt['status']!='ok':
                durable(journal,{'event':'phase_stopped','reason':attempt['status'],'batch_index':item['batch_index']})
                raise RuntimeError('Stopped on first non-ok batch; no retry')
        durable(journal,{'event':'phase_completed','request_count':len(requests),'record_count':3 if phase=='smoke' else 60})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='action',required=True)
    subs.add_parser('prepare')
    for action in ('smoke','inspect','development'):
        p=subs.add_parser(action)
        p.add_argument('--repeat',required=True,choices=tuple(ORDERS))
        p.add_argument('--condition',required=True,choices=('P0','P1','P2'))
        p.add_argument('--manifest-sha256',required=True)
        if action=='inspect':p.add_argument('--note',required=True)
        else:
            p.add_argument('--claude',required=True)
            p.add_argument('--preflight-receipt',required=True)
            p.add_argument('--preflight-sha256',required=True)
    a=parser.parse_args()
    if a.action=='prepare':prepare();return
    manifest=verify_manifest(a.repeat,a.manifest_sha256)
    if a.action=='inspect':inspect(manifest,a.condition,a.note)
    else:run_phase(manifest,a.condition,a.action,a.claude,a.preflight_receipt,a.preflight_sha256)

if __name__=='__main__':main()
