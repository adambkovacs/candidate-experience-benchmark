#!/usr/bin/env python3
"""Offline-frozen, never-sent OpenRouter suffixes. Execution needs a separate root receipt."""
import argparse
import fcntl
import hashlib
import json
import os
import sys
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import openrouter_paid_benchmark as paid
from paid_budget_partitions_v2 import open_partition
from prompt_admission import audit_response

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'results/hosted-unattempted-continuation-v2'
INVENTORY = ROOT / 'results/hosted-never-sent-inventory-2026-09-24.json'
CONTRACT = 'hosted-unattempted-continuation-v2'
TARGETS = None  # Exact eligible keys are hash-bound from the frozen inventory.

DEPENDENCIES = ('openrouter_paid_benchmark.py', 'openrouter_benchmark.py',
                'paid_budget_partitions.py', 'prompt_admission.py',
                'evaluate_prompt_variants.py', 'development_benchmark.py',
                'paid_budget_partitions_v2.py', 'openrouter_budget_v2.py')


def digest(data): return hashlib.sha256(data).hexdigest()
def binding(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT)), 'sha256': digest(path.read_bytes())}
def bound(item):
    path = (ROOT / item['file']).resolve()
    path.relative_to(ROOT)
    data = path.read_bytes()
    if digest(data) != item['sha256']: raise ValueError('Source hash differs: ' + item['file'])
    return data

def json_bound(item): return json.loads(bound(item))
def lines(item): return [json.loads(line) for line in bound(item).splitlines() if line.strip()]
def ids(start): return [f'DEV-{i:03}' for i in range(start, 61)]
def endpoint_facts(endpoint):
    keys = ('tag','model_id','provider_name','quantization','context_length',
            'max_completion_tokens','max_prompt_tokens','pricing')
    return {key:endpoint.get(key) for key in keys} | {'supported_parameters':sorted(endpoint.get('supported_parameters',[]))}

def catalog_facts(model):
    return {key:model.get(key) for key in ('id','reasoning','context_length')} | {'supported_parameters':sorted(model.get('supported_parameters',[]))}

def read_inventory():
    inv = json.loads(INVENTORY.read_text())
    if inv['schema'] != 'hosted-never-sent-inventory-v1': raise ValueError('Inventory contract differs')
    for source in inv['source_bindings']:
        if digest((ROOT/source['path']).read_bytes()) != source['sha256']: raise ValueError('Inventory source differs: '+source['path'])
    return inv

def config_and_requests(manifest):
    base = json_bound(manifest['original_manifest'])
    cfg = next((x for x in base['configurations'] if x['id'] == manifest['configuration_id']), None)
    if cfg is None or cfg['controls'] != manifest['controls'] or cfg['parent_baseline_id'] != manifest['parent_baseline_id']:
        raise ValueError('Frozen configuration differs')
    condition = cfg['conditions'][manifest['condition']]
    if condition['observational_evidence'] != manifest['observational_evidence'] or condition['instruction'] != manifest['instruction']:
        raise ValueError('Original condition binding differs')
    if base['inputs'] != manifest['inputs'] or base['schema'] != manifest['schema']:
        raise ValueError('Inputs/schema binding differs')
    observation = json_bound(manifest['observational_evidence'])
    requests = observation['requests'][3:]
    if [x['record_ids'] for x in observation['requests'][:3]] != [[x] for x in ids(1)[:3]]: raise ValueError('Frozen smoke requests differ')
    if [x['record_ids'] for x in requests] != [[x] for x in ids(1)]: raise ValueError('Frozen requests are not canonical 60')
    return cfg, requests

def history_attempts(manifest):
    observed = []
    ledgers = {x['file']: lines(x) for x in manifest['historical_ledgers']}
    for history in manifest['histories']:
        raw = lines(history['output']); journal = lines(history['journal'])
        starts = [x for x in journal if x.get('event') in ('started','request_started')]
        finishes = [x for x in journal if x.get('event') in ('finished','request_finished') and x.get('id')]
        if [(x['id'],x['attempt_id']) for x in starts] != [(x['id'],x['attempt_id']) for x in raw]:
            raise ValueError('Historical started requests differ from raw output')
        if [(x['id'],x['attempt_id']) for x in finishes] != [(x['id'],x['attempt_id']) for x in raw]:
            raise ValueError('Historical finished requests differ from raw output')
        if history.get('kind') == 'continuation' and (journal[-1].get('event'),journal[-1].get('status')) != ('finished','stopped'):
            raise ValueError('Prior continuation lacks stopped terminal')
        for row in raw:
            attempt = row['attempt_id']
            matches = [(name,event) for name,events in ledgers.items() for event in events
                       if event.get('attempt_id') == attempt and event.get('event') in ('settle','unknown_cost_accounted_as_upper_bound')]
            if len(matches) != 1: raise ValueError('Historical billing not uniquely settled/full-bound: '+row['id'])
            _,event = matches[0]
            if row.get('cost_unknown'):
                if event['event'] != 'unknown_cost_accounted_as_upper_bound' or paid.number(event['usd']) != paid.number(row['reserved_cost_usd']):
                    raise ValueError('Unknown historical cost not fully bound: '+row['id'])
            elif event['event'] != 'settle' or paid.number(event['usd']) != paid.number(row['observed_cost_usd']):
                raise ValueError('Historical known cost mismatch: '+row['id'])
            observed.append(row['id'])
    if observed != ids(1)[:len(observed)] or len(set(observed)) != len(observed):
        raise ValueError('Historical records are not one unique canonical prefix')
    return observed

def may_continue(record, diagnostics, continue_invalid):
    raw = record.get('raw_response') or {}
    choices = raw.get('choices') or []
    if (record.get('cost_unknown') or not record.get('billing_ok') or raw.get('error') or
        len(choices) != 1 or record.get('status') in ('service_error','identity_violation','control_violation')):
        return False
    choice = choices[0]; message = choice.get('message') or {}
    if (choice.get('error') or message.get('tool_calls') or message.get('function_call') is not None or message.get('refusal') or
        choice.get('finish_reason') not in ('stop','length')):
        return False
    if record.get('status') == 'ok' and choice.get('finish_reason') == 'stop':
        return not diagnostics['blockers']
    return bool(continue_invalid and record.get('status') == 'invalid_output' and
                choice.get('finish_reason') == 'length' and diagnostics['blockers'] == ['truncation:length'])

def validate(manifest, frozen=True):
    if manifest['contract'] != CONTRACT or manifest['reference_labels_read'] is not False: raise ValueError('Unsupported contract')
    if frozen and manifest['status'] != 'FROZEN': raise ValueError('Manifest not frozen')
    if Path(manifest['controller']['file']) != Path('scripts/openrouter_unattempted_continuation.py') or bound(manifest['controller']) != Path(__file__).read_bytes():
        raise ValueError('Controller differs')
    for dependency in manifest['dependencies']: bound(dependency)
    inv = json_bound(manifest['inventory'])
    if inv != read_inventory(): raise ValueError('Inventory drift')
    key = (manifest['inventory_configuration_id'],manifest['condition'])
    if manifest['configuration_id'] != ('openrouter-qwen27-low-darkbloom-fp4' if key[0] == 'qwen27-low-hosted-addendum-v1' else key[0]): raise ValueError('Configuration mapping differs')
    candidate = next((x for x in inv['candidate_conditions'] if (x['configuration_id'],x['condition']) == key),None)
    if candidate is None or candidate['candidate_never_sent_ids'] != manifest['remaining_ids']:
        raise ValueError('Candidate inventory differs')
    if sorted(manifest['source_evidence'],key=lambda x:x['file']) != sorted([{'file':x['path'],'sha256':x['sha256']} for x in candidate['evidence']],key=lambda x:x['file']):
        raise ValueError('Candidate source evidence differs')
    for source in manifest['source_evidence']: bound(source)
    cfg,requests = config_and_requests(manifest)
    history = history_attempts(manifest)
    if manifest['remaining_ids'] != ids(len(history)+1) or not history or len(history)>=60:
        raise ValueError('Remaining IDs differ from exact historical suffix')
    if manifest['request_bindings'] != [x['client_request'] for x in requests[len(history):]]:
        raise ValueError('Request binding suffix differs')
    for rid,item in zip(manifest['remaining_ids'],manifest['request_bindings']):
        payload = json_bound(item)
        if payload['request']['model'] != manifest['controls']['model']:
            raise ValueError('Model differs: '+rid)
        if payload['adapter_controls'] != manifest['controls']['adapter_controls']:
            raise ValueError('Request controls differ: '+rid)
    smoke = lines(manifest['smoke'])
    if [x['id'] for x in smoke] != ids(1)[:3] or any(x.get('status') != 'ok' or x.get('cost_unknown') or x.get('reference_labels_read') is not False for x in smoke):
        raise ValueError('Passed 3-record smoke absent')
    if any(endpoint_facts(x['provider_endpoint']) != manifest['endpoint_facts'] or catalog_facts(x['model_catalog_entry']) != manifest['catalog_facts'] for x in smoke):
        raise ValueError('Smoke endpoint/catalog controls differ')
    supplement = json_bound(manifest['smoke_supplement'])
    if supplement.get('configuration_id') != manifest['configuration_id'] or supplement.get('condition') != manifest['condition']:
        raise ValueError('Smoke supplement differs')
    inspection=json_bound(supplement['smoke_evidence'])
    if inspection.get('inspection') != 'passed' or inspection.get('raw_attempts') != manifest['smoke']:
        raise ValueError('Root-inspected smoke evidence differs')
    for key in ('output','journal'):
        path = (ROOT/manifest[key]).resolve(); path.relative_to(DEST)
    return cfg, requests

def build(args):
    inv = read_inventory();key = (args.inventory_configuration_id,args.condition)
    if not any((x['configuration_id'],x['condition']) == key for x in inv['candidate_conditions']): raise ValueError('Outside eligible inventory')
    candidate = next(x for x in inv['candidate_conditions'] if (x['configuration_id'],x['condition']) == key)
    base = ROOT/'results/prompt-comparison-v1-2026-09-24'
    qwen = key[0] == 'qwen27-low-hosted-addendum-v1'
    source = base/('qwen27-low-hosted-addendum-v1/execution-manifest.json' if qwen else 'hosted-execution.json')
    original = json.loads(source.read_text()); cfg = next(x for x in original['configurations'] if x['id']==('openrouter-qwen27-low-darkbloom-fp4' if qwen else key[0]))
    if qwen:
        phase = base/'qwen27-low-hosted-addendum-v1'; prefix = f'{args.condition}-'
        histories = [{'kind':'original','output':binding(phase/(prefix+'development.jsonl')),
                      'journal':binding(phase/(prefix+'development.jsonl.attempts.jsonl'))}]
        smoke = binding(phase/(prefix+'smoke.jsonl')); supplement = binding(phase/(prefix+'smoke-supplement.json'))
    else:
        phase = base/'runs'/key[0]/key[1]
        histories = [{'kind':'original','output':binding(phase/'development.jsonl'),
                      'journal':binding(phase/'development.jsonl.attempts.jsonl')}]
        prior = base/'hosted-continuations-v1'/('low-P2' if key[0].endswith('-low') else 'high-P1')
        if any('hosted-continuations-v1' in x['path'] for x in candidate['evidence']):
            histories.append({'kind':'continuation','output':binding(prior/'development.jsonl'),
                              'journal':binding(prior/'amendment-journal.jsonl')})
        smoke_path=phase/'smoke.jsonl'
        if not smoke_path.exists(): smoke_path=phase/'smoke-after-launch-failure.jsonl'
        smoke = binding(smoke_path); supplement = binding(phase/'smoke-supplement.json')
    ledger_paths = set()
    for entry in histories:
        for row in lines(entry['output']):
            if row.get('budget_ledger'): ledger_paths.add((ROOT/row['budget_ledger']).resolve())
    if qwen: ledger_paths.add((base/'qwen27-low-hosted-addendum-v1/budget-manifest-v1-qwen27-low-prompts-v1.jsonl').resolve())
    elif any(h['kind']=='continuation' for h in histories):
        prior_manifest=json.loads((prior/'execution-manifest.json').read_text())
        part=json.loads((ROOT/prior_manifest['budget_partition_manifest']['file']).read_text())
        ledger_paths.add(Path(next(x for x in part['partitions'] if x['id']==prior_manifest['budget_partition_id'])['child_ledger']).resolve())
    directory=DEST/(key[0]+'-'+key[1].lower());directory.mkdir(parents=True,exist_ok=False)
    ledgers=[]
    for n,path in enumerate(sorted(ledger_paths)):
        with path.open('rb') as source_ledger:
            fcntl.flock(source_ledger,fcntl.LOCK_SH); snapshot=source_ledger.read(); fcntl.flock(source_ledger,fcntl.LOCK_UN)
        snap=directory/f'historical-ledger-{n}.jsonl';snap.write_bytes(snapshot);ledgers.append(binding(snap))
    observation=cfg['conditions'][key[1]]['observational_evidence']
    observed=[row['id'] for h in histories for row in lines(h['output'])]
    manifest={'contract':CONTRACT,'status':'DRAFT','reference_labels_read':False,
              'inventory':binding(INVENTORY),'inventory_configuration_id':key[0],
              'configuration_id':cfg['id'],'condition':key[1],
              'controller':binding(__file__),'dependencies':[binding(ROOT/'scripts'/name) for name in DEPENDENCIES],
              'original_manifest':binding(source),'controls':cfg['controls'],'parent_baseline_id':cfg['parent_baseline_id'],
              'observational_evidence':observation,'instruction':cfg['conditions'][key[1]]['instruction'],
              'inputs':original['inputs'],'schema':original['schema'],
              'source_evidence':[{'file':x['path'],'sha256':x['sha256']} for x in candidate['evidence']],
              'histories':histories,'historical_ledgers':ledgers,'smoke':smoke,'smoke_supplement':supplement,
              'endpoint_facts':endpoint_facts(lines(smoke)[0]['provider_endpoint']),
              'catalog_facts':catalog_facts(lines(smoke)[0]['model_catalog_entry']),
              'remaining_ids':candidate['candidate_never_sent_ids'],
              'request_bindings':[x['client_request'] for x in json.loads((ROOT/observation['file']).read_text())['requests'][3+len(observed):]],
              'output':str((directory/'development.jsonl').relative_to(ROOT)),
              'journal':str((directory/'attempts.jsonl').relative_to(ROOT)),
              'policy':{'retry':False,'failed_records_retained':True,'canonical_denominator':60,
                        'order_limitation':'Suffix executes later; original counterbalanced timing is not preserved.',
                        'stop_on':['service_error','unknown_cost','identity_or_control_violation','nonintrinsic_invalid_output'],
                        'continue_on_intrinsic_invalid_output':cfg['continue_on_invalid_output']}}
    validate(manifest,False)
    path=directory/'draft-manifest.json'
    with path.open('x') as out: json.dump(manifest,out,indent=2);out.write('\n')
    print(path, len(manifest['remaining_ids']))

def execute(args):
    raw=Path(args.manifest).read_bytes()
    if digest(raw)!=args.sha256:raise ValueError('Manifest hash differs')
    manifest=json.loads(raw);cfg,_=validate(manifest)
    receipt=json.loads(Path(args.review).read_text())
    if receipt.get('contract')!='hosted-unattempted-root-review-v1' or receipt.get('manifest_sha256')!=args.sha256 or receipt.get('approved') is not True:
        raise ValueError('Root receipt absent/differs')
    if [manifest['inventory_configuration_id'],manifest['condition']] not in receipt.get('approved_conditions',[]):
        raise ValueError('Condition not approved')
    budget=receipt['budget_partition_manifest']; bound(budget)
    partition=receipt['budget_partition_id']
    output=ROOT/manifest['output'];journal=ROOT/manifest['journal']
    if output.exists() or journal.exists():raise FileExistsError('No replay or overwrite')
    controls=manifest['controls'];ac=controls['adapter_controls'];first=json_bound(manifest['request_bindings'][0])['request']
    provider=first['provider']['only'][0];prices=first['provider']['max_price'];timeout=cfg['controller_timeout_seconds']
    inputs={x['id']:x for x in paid.read_rows(ROOT/manifest['inputs']['file'])}
    policy=bound(manifest['instruction']).decode();schema=json_bound(manifest['schema'])
    token=paid.load_key(args.env_file)
    model,endpoint=paid.select_endpoint(controls['model'],provider,paid.fetch('/models',timeout=timeout),
        paid.fetch('/models/'+quote(controls['model'],safe='/')+'/endpoints',timeout=timeout),prices['prompt'],prices['completion'])
    if endpoint_facts(endpoint) != manifest['endpoint_facts'] or catalog_facts(model) != manifest['catalog_facts']:
        raise ValueError('Live endpoint controls, prices, or catalog capabilities differ from inspected smoke')
    paid.check_paid_phase_two(SimpleNamespace(start=1,budget_partition_manifest=budget['file'],budget_partition_id=partition,
        model=controls['model'],reasoning=controls['effort'],max_tokens=controls['output_reserve_tokens']),controls,endpoint)
    actual_args=SimpleNamespace(model=controls['model'],reasoning=controls['effort'])
    for rid,item in zip(manifest['remaining_ids'],manifest['request_bindings']):
        payload=paid.make_payload(controls['model'],endpoint,inputs[rid]['feedback'],policy,schema,controls['effort'],
           controls['output_reserve_tokens'],prices['prompt'],prices['completion'],model)
        if {'request':payload,'adapter_controls':paid.paid_adapter_controls(actual_args,endpoint,payload)}!=json_bound(item):
            raise ValueError('Live request differs from frozen exact request: '+rid)
    reserve=paid.reservation(endpoint,controls['output_reserve_tokens'],prices['prompt'],prices['completion'])
    ledger=None;count=0;terminal='stopped'
    with journal.open('x') as audit:
        paid.durable(audit,{'event':'claimed','manifest_sha256':args.sha256,'review_sha256':digest(Path(args.review).read_bytes()),
            'budget_partition_manifest_sha256':budget['sha256'],'budget_partition_id':partition,
            'configuration_id':manifest['configuration_id'],'condition':manifest['condition'],
            'remaining_ids':manifest['remaining_ids'],'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
        try:
            ledger=open_partition(paid.LEDGER_PATH,ROOT/budget['file'],partition,controls['model'],provider,controls['effort'])
            with output.open('x') as out:
                for rid,item in zip(manifest['remaining_ids'],manifest['request_bindings']):
                    payload=json_bound(item)['request'];attempt=ledger.reserve(reserve,rid);start=time.perf_counter();actual=None
                    record={'id':rid,'phase':'development','requested_model':controls['model'],'provider_endpoint':endpoint,
                        'model_catalog_entry':model,'request':payload,'attempt_id':attempt,'reference_labels_read':False,
                        'surface':'OpenRouter paid HTTP','hardware':'Remote provider undisclosed','runtime':'OpenRouter HTTP v1',
                        'quantization':endpoint.get('quantization'),'reasoning_effort':controls['effort'],'retry_policy':'none; exclusive files; every attempt reserves against shared cap',
                        'reserved_cost_usd':str(reserve),'continuation_manifest_sha256':args.sha256,'condition':manifest['condition'],
                        'parent_baseline_id':cfg['parent_baseline_id'],'request_timeout_seconds':timeout}
                    paid.durable(audit,{'event':'request_started','id':rid,'attempt_id':attempt,'request_sha256':digest(json.dumps(payload,sort_keys=True).encode())})
                    try:
                        body=paid.fetch('/chat/completions',token,payload,timeout)
                        body=json.loads(json.dumps(body).replace(token,'[REDACTED]'))
                        record['raw_response']=body;record['usage']=body.get('usage') or {};record['returned_model']=body.get('model');record['returned_provider']=body.get('provider')
                        if record['usage'].get('cost') is not None:actual=paid.number(record['usage']['cost'])
                        choices=body.get('choices') or [];choice=choices[0] if len(choices)==1 else {};message=choice.get('message') or {}
                        record['finish_reason']=choice.get('finish_reason')
                        try:prediction=json.loads(message.get('content'))
                        except (ValueError,TypeError):prediction=None
                        record['prediction']=prediction;record['status']='ok' if paid.valid(prediction) and choice.get('finish_reason')=='stop' else 'invalid_output'
                        if body.get('error') or len(choices)!=1 or choice.get('error') or message.get('tool_calls') or message.get('function_call') is not None or message.get('refusal') or choice.get('finish_reason') not in ('stop','length'):
                            record['status']='control_violation';record['control_violation']=True
                        if body.get('model') not in paid.allowed_returned_models(controls['model'],endpoint) or body.get('provider')!=endpoint['provider_name']:
                            record.update(status='identity_violation',identity_violation=True)
                    except Exception as exc:
                        record.update(status='service_error',error_type=type(exc).__name__)
                        if isinstance(exc,urllib.error.HTTPError):
                            record['http_status']=exc.code
                            try:record['raw_error_response']=json.loads(exc.read(1000000).decode().replace(token,'[REDACTED]'))
                            except (ValueError,UnicodeError):pass
                    billing=ledger.settle(attempt,actual)
                    record.update(elapsed_seconds=time.perf_counter()-start,observed_cost_usd=str(actual) if actual is not None else None,
                                  cost_unknown=actual is None,billing_ok=billing)
                    diagnostics=audit_response(record,'openrouter_paid_v1',controls['context_tokens']-controls['output_reserve_tokens'])
                    record['response_diagnostics']=diagnostics
                    paid.durable(out,record);paid.durable(audit,{'event':'request_finished','id':rid,'attempt_id':attempt,'status':record['status']});count+=1
                    print(rid,record['status'],flush=True)
                    if not may_continue(record,diagnostics,cfg['continue_on_invalid_output']):break
                else:terminal='completed_remaining_attempts'
        finally:
            if ledger is not None:ledger.close()
            paid.durable(audit,{'event':'finished','status':terminal,'attempted_records':count,'canonical_denominator':60,
                'historical_failed_records_retained':True,'output':binding(output) if output.exists() else None})

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--inventory-configuration-id',required=True);b.add_argument('--condition',choices=('P1','P2'),required=True)
    v=sub.add_parser('validate');v.add_argument('--manifest',required=True);v.add_argument('--sha256',required=True)
    e=sub.add_parser('execute');e.add_argument('--manifest',required=True);e.add_argument('--sha256',required=True);e.add_argument('--review',required=True);e.add_argument('--env-file')
    args=parser.parse_args()
    if args.command=='build':build(args)
    elif args.command=='execute':execute(args)
    else:
        raw=Path(args.manifest).read_bytes()
        if digest(raw)!=args.sha256:raise ValueError('Manifest hash differs')
        validate(json.loads(raw));print('validated')
if __name__=='__main__':main()
