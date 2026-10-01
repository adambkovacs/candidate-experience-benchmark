#!/usr/bin/env python3
"""Distinct Mistral119 none protocol smoke on never-sent DEV-002..004.

Prepare/verify are offline. Run requires a reviewed receipt and a fresh v3
$12.38-master child. This is not a repeat-pass smoke or development admission.
"""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from development_benchmark import ROOT
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import openrouter_paid_benchmark as paid
import openrouter_benchmark as transport
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'mistral119-none-v3-protocol-smoke-v1'
CONFIG = 'openrouter-paid-mistral-small4-119b-none'
STAGE = 'protocol-smoke-never-sent-002-004'
IDS = ('DEV-002', 'DEV-003', 'DEV-004')
PLAN_SHA = 'fbfa58d15d3aeff20d819c8e37bba8d16e0e5c53775cb0c1f11b404149f34f07'
EXECUTION_SHA = '13a898d5adbaa17e5267e18d1368edd1cd7c819d8a724a2c72e9ebdfae7bfe1a'
PID = 'mistral119-none-v3-protocol-smoke-v1'
CAP = study.RESERVE * 3
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
BASE = study.BASE / 'v3-protocol-smoke-none-v1'
SOURCE_PATHS = (
    'scripts/mistral119_v3_smoke.py', 'tests/test_mistral119_v3_smoke.py',
    'scripts/mistral119_fresh_repeat_study.py',
    'scripts/mistral119_fresh_repeat_execution.py',
    'scripts/qwen27_fresh_repeat_execution.py',
    'scripts/openrouter_paid_benchmark.py', 'scripts/openrouter_benchmark.py',
    'scripts/paid_budget_partitions_v3.py', 'scripts/openrouter_budget_v3.py',
    'scripts/prompt_admission.py', 'scripts/development_benchmark.py',
    'scripts/frozen_prompt_variants.py',
)
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def sha(path):
    return study.sha(Path(path))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def history_bindings():
    original, count = study.historical(CONFIG)
    sources = study.CONFIGS[CONFIG]['historical_smokes']
    if count != 5:
        raise ValueError('Expected five distinct historical failed smokes')
    for path in sources:
        attempts = study.jsonl(path)
        if len(attempts) != 1 or attempts[0]['id'] != 'DEV-001':
            raise ValueError('Historical smoke membership differs')
    return {name: sha(ROOT / name) for name in sources}


def manifest_value():
    plan = study.verify(CONFIG, 'fresh1', PLAN_SHA)
    frozen.runner.verify_execution_manifest(EXECUTION_SHA)
    history = history_bindings()
    requests = plan['conditions']['P0']['development'][1:4]
    if [x['record_id'] for x in requests] != list(IDS):
        raise ValueError('New protocol smoke is not exact never-sent membership')
    if [x['record_id'] for x in plan['conditions']['P0']['smoke']] != ['DEV-001','DEV-002','DEV-003']:
        raise ValueError('Original planned smoke membership changed')
    for item in requests:
        if study.digest(json.dumps(item['payload'], sort_keys=True)) != item['request_sha256']:
            raise ValueError('Frozen request payload changed')
        if set(item['payload']['messages'][1]) != {'role','content'}:
            raise ValueError('Unexpected user request fields')
    return {
        'schema': SCHEMA, 'status': 'prepared_not_admitted', 'inference_performed': False,
        'reference_labels_read': False, 'purpose': 'separate_provider_protocol_validation',
        'not_a_repeat_pass': True, 'configuration_id': CONFIG, 'stage': STAGE,
        'model': study.MODEL, 'provider_tag': study.PROVIDER,
        'provider_name': study.PROVIDER_NAME, 'effort': 'none',
        'endpoint': transport.BASE + '/chat/completions',
        'frozen_fresh1_plan_sha256': PLAN_SHA,
        'frozen_execution_manifest_sha256': EXECUTION_SHA,
        'historical_dev001_failed_smoke_count': 5,
        'historical_failed_smoke_source_sha256': history,
        'source_sha256': {name: sha(ROOT / name) for name in SOURCE_PATHS},
        'input_file_sha256': sha(ROOT / study.INPUTS),
        'ids': list(IDS), 'request_count': 3,
        'per_request_full_context_reserve_usd': str(study.RESERVE),
        'full_three_request_admission_usd': str(CAP),
        'budget_master_cap_usd': '12.38', 'budget_partition_id': PID,
        'requests': requests,
    }


def prepare(base=BASE):
    base = Path(base)
    value = manifest_value()
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'manifest.json').open('x') as out:
        paid.durable(out, value)
    return digest_bytes(canonical(value))


def verify(base=BASE):
    saved = json.loads((Path(base) / 'manifest.json').read_text())
    rebuilt = manifest_value()
    if saved != rebuilt:
        raise ValueError('Mistral v3 smoke manifest or source drift')
    return saved, digest_bytes(canonical(saved))


def expected_receipt(manifest, digest, budget_manifest):
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'manifest_sha256': digest,
            'runner_sha256': manifest['source_sha256']['scripts/mistral119_v3_smoke.py'],
            'budget_manifest_sha256': sha(budget_manifest),
            'budget_partition_id': PID, 'child_cap_usd': str(CAP),
            'ids': list(IDS), 'reference_labels_sent': False,
            'repeat_pass_credit': False}


def review_receipt(path, manifest, digest, budget_manifest, base):
    if Path(path).resolve() != (Path(base) / 'smoke.root-review.json').resolve():
        raise ValueError('Wrong root review receipt path')
    value = json.loads(Path(path).read_text())
    if any(value.get(k) != v for k,v in expected_receipt(manifest,digest,budget_manifest).items()):
        raise ValueError('Mistral root review receipt differs')
    if not isinstance(value.get('reviewer'),str) or not value['reviewer'].strip():
        raise ValueError('Named root reviewer required')
    return value


def post(payload, token):
    request = urllib.request.Request(transport.BASE + '/chat/completions',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    try:
        with transport.OPENER.open(request, timeout=study.TIMEOUT) as response:
            status,raw=response.status,response.read(MAX_RESPONSE_BYTES+1)
    except urllib.error.HTTPError as error:
        status,raw=error.code,error.read(MAX_RESPONSE_BYTES+1)
    oversized=len(raw)>MAX_RESPONSE_BYTES
    raw=raw[:MAX_RESPONSE_BYTES].replace(token.encode(),b'[REDACTED]')
    return status,raw,oversized


def run(receipt_path,budget_manifest,base=BASE,send=post,
        live=frozen.live_controls,open_child=partitions.open_partition,load_key=paid.load_key,
        env_file=None):
    base,budget_manifest=Path(base),Path(budget_manifest)
    manifest,digest=verify(base)
    review_receipt(receipt_path,manifest,digest,budget_manifest,base)
    paths={name:base/('smoke.'+name) for name in
           ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Mistral v3 protocol smoke already claimed')
    plan=study.verify(CONFIG,'fresh1',PLAN_SHA)
    model,endpoint,reserve=live(plan,'P0')
    if reserve!=study.RESERVE:
        raise ValueError('Live Mistral reserve differs')
    ledger=open_child(MASTER,budget_manifest,PID,study.MODEL,study.PROVIDER,'none')
    try:
        _,pending,blocked=ledger.state()
        if (ledger.master_cap!=Decimal('12.38') or ledger.cap!=CAP or
                ledger.accounted()!=0 or pending or blocked or ledger.closed):
            raise ValueError('Fresh v3 child lacks full three-request admission')
        token=load_key(env_file)
        with paths['claim.json'].open('x') as out:
            paid.durable(out,{'schema':SCHEMA+'-claim','manifest_sha256':digest,
                              'root_review_sha256':sha(receipt_path),
                              'budget_manifest_sha256':sha(budget_manifest),
                              'ids':list(IDS),'claimed_utc':now()})
        with paths['journal.jsonl'].open('x') as journal,paths['raw.jsonl'].open('x') as raw_file,\
             paths['attempts.jsonl'].open('x') as attempts,paths['parsed.jsonl'].open('x') as parsed:
            paid.durable(journal,{'event':'stage_started','utc':now(),'ids':list(IDS)})
            for item in manifest['requests']:
                rid=item['record_id']
                try:
                    verify(base)
                    model,endpoint,current_reserve=live(plan,'P0')
                    if current_reserve!=study.RESERVE:
                        raise ValueError('Live Mistral reserve changed')
                    if ledger.accounted()+study.RESERVE>ledger.cap:
                        raise ValueError('Mistral child cannot reserve next request')
                    paid.durable(journal,{'event':'request_intent','id':rid,
                                         'request_sha256':item['request_sha256'],'utc':now()})
                    aid=ledger.reserve(study.RESERVE,rid)
                    paid.durable(journal,{'event':'request_started','id':rid,
                                         'attempt_id':aid,'request_sha256':item['request_sha256'],
                                         'live_endpoint':endpoint,'utc':now()})
                    started=now();t0=time.perf_counter_ns()
                    try: status,wire,oversized=send(item['payload'],token)
                    except BaseException as error:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'transport_error',
                                               'error_type':type(error).__name__,
                                               'cost_unknown':True,'reserved_cost_usd':str(study.RESERVE)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'transport_outcome_unknown','utc':now()})
                        raise
                    paid.durable(raw_file,{'id':rid,'attempt_id':aid,'http_status':status,
                                           'request_sha256':item['request_sha256'],
                                           'body_base64':base64.b64encode(wire).decode(),
                                           'body_sha256':digest_bytes(wire),
                                           'body_truncated_at_limit':oversized,
                                           'started_utc':started,'ended_utc':now(),
                                           'client_request_elapsed_ns':time.perf_counter_ns()-t0})
                    try: body=json.loads(wire) if not oversized else None
                    except (ValueError,UnicodeDecodeError):body=None
                    usage=body.get('usage') if isinstance(body,dict) else None
                    try: actual=paid.number(usage['cost']) if isinstance(usage,dict) and usage.get('cost') is not None else None
                    except ValueError:actual=None
                    if actual is None:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'unknown_cost',
                                               'http_status':status,'cost_unknown':True,
                                               'reserved_cost_usd':str(study.RESERVE)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,'reason':'unknown_cost','utc':now()})
                        raise ValueError('Unknown Mistral cost; full reserve retained')
                    billing_ok=ledger.settle(aid,actual)
                    if not billing_ok:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'observed_cost_over_bound',
                                               'http_status':status,'cost_unknown':False,
                                               'reserved_cost_usd':str(study.RESERVE),
                                               'actual_cost_usd':str(actual)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,'reason':'observed_cost_over_bound','utc':now()})
                        raise ValueError('Observed Mistral cost blocked child')
                    if status!=200:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'http_error',
                                               'http_status':status,'cost_unknown':False,
                                               'actual_cost_usd':str(actual)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,'reason':'http_error','utc':now()})
                        raise ValueError('Mistral HTTP error; no retry')
                    try:
                        classified=(frozen.runner.classify(body,model,endpoint)
                                    if isinstance(body,dict) else {'status':'malformed_response'})
                        diagnostic=audit_response(body,'openrouter_paid_v1',study.CONTEXT-study.MAX_TOKENS)
                    except (TypeError, ValueError, AttributeError, KeyError):
                        classified={'status':'malformed_response'}
                        diagnostic={'passed':False,'blockers':['malformed_response']}
                    if classified['status']!='ok' or not diagnostic['passed']:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'invalid_response',
                                               'response_status':classified['status'],
                                               'cost_unknown':False,'actual_cost_usd':str(actual),
                                               'diagnostic':diagnostic})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,'reason':'invalid_response','utc':now()})
                        raise ValueError('Invalid Mistral output; no repair or retry')
                    paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'ok',
                                           'cost_unknown':False,'actual_cost_usd':str(actual),
                                           'body_sha256':digest_bytes(wire)})
                    paid.durable(parsed,{'id':rid,'attempt_id':aid,'prediction':classified['prediction'],
                                         'returned_model':body['model'],'returned_provider':body['provider'],
                                         'usage':usage,'body_sha256':digest_bytes(wire)})
                    paid.durable(journal,{'event':'request_finished','id':rid,'attempt_id':aid,'utc':now()})
                except BaseException as error:
                    paid.durable(journal,{'event':'stage_aborted','id':rid,
                                          'error_type':type(error).__name__,'utc':now()})
                    raise
            paid.durable(journal,{'event':'stage_completed','count':3,'utc':now(),
                                  'repeat_pass_credit':False})
    finally:ledger.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--base',type=Path,default=BASE)
    a=sub.add_parser('verify');a.add_argument('--base',type=Path,default=BASE)
    a=sub.add_parser('run');a.add_argument('--base',type=Path,default=BASE)
    a.add_argument('--root-review-receipt',type=Path,required=True)
    a.add_argument('--budget-manifest',type=Path,required=True)
    a.add_argument('--env-file',type=Path)
    args=p.parse_args()
    if args.command=='prepare':print(prepare(args.base))
    elif args.command=='verify':print(verify(args.base)[1])
    else:run(args.root_review_receipt,args.budget_manifest,args.base,env_file=args.env_file)

if __name__=='__main__':main()
