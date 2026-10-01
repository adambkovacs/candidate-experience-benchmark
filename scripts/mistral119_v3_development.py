#!/usr/bin/env python3
"""One fresh1/P0 full Mistral119 none pass after a separate inspected protocol smoke.

Preparation and verification are offline. Run requires a distinct funded v3
partition and a stage-specific root receipt. No failed historical smoke is replayed.
"""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path
import time

import mistral119_v3_smoke as smoke
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'mistral119-none-v3-fresh1-p0-development-v1'
PID = 'mistral119-none-v3-fresh1-p0-development-v1'
CAP = Decimal('0.25')
BASE = study.BASE / 'v3-development-none-v1' / 'fresh1' / 'P0'
SOURCE_PATHS = (*smoke.SOURCE_PATHS, 'scripts/mistral119_v3_development.py',
                'tests/test_mistral119_v3_development.py')
SMOKE_FILES = ('smoke.claim.json', 'smoke.journal.jsonl', 'smoke.attempts.jsonl',
               'smoke.raw.jsonl', 'smoke.parsed.jsonl')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def smoke_closure(base=smoke.BASE):
    base = Path(base)
    manifest, manifest_sha = smoke.verify(base)
    inspection_path = base / 'smoke.inspection.json'
    inspection = json.loads(inspection_path.read_text())
    if (inspection.get('schema') != 'mistral119-v3-protocol-smoke-inspection-v1' or
            inspection.get('verdict') != 'PASS' or
            inspection.get('reviewer') != 'root' or
            inspection.get('manifest_sha256') != manifest_sha or
            inspection.get('ids') != list(smoke.IDS) or
            inspection.get('raw_responses_inspected') is not True or
            inspection.get('repeat_pass_credit') is not False or
            inspection.get('development_admitted') is not False or
            manifest['reference_labels_read'] is not False):
        raise ValueError('Inspected protocol smoke identity or decision differs')
    if inspection.get('source_sha256') != {name: smoke.sha(base/name) for name in SMOKE_FILES}:
        raise ValueError('Inspected protocol smoke evidence hash differs')
    claim = json.loads((base/'smoke.claim.json').read_text())
    receipt = json.loads((base/'smoke.root-review.json').read_text())
    smoke.review_receipt(base/'smoke.root-review.json', manifest, manifest_sha,
                         base/'budget-manifest.json', base)
    if (claim.get('manifest_sha256') != manifest_sha or
            claim.get('root_review_sha256') != smoke.sha(base/'smoke.root-review.json') or
            receipt.get('reference_labels_sent') is not False or
            receipt.get('repeat_pass_credit') is not False):
        raise ValueError('Protocol smoke claim or receipt differs')
    attempts, raw, parsed = [rows(base/name) for name in SMOKE_FILES[2:]]
    journal = rows(base/'smoke.journal.jsonl')
    attempt_ids=[x.get('attempt_id') for x in attempts]
    if ([x.get('id') for x in attempts] != list(smoke.IDS) or
            [x.get('id') for x in raw] != list(smoke.IDS) or
            [x.get('id') for x in parsed] != list(smoke.IDS) or
            any(not isinstance(x,str) or not x for x in attempt_ids) or
            len(set(attempt_ids)) != 3 or
            len(journal) != 11 or journal[0].get('event') != 'stage_started' or
            journal[-1].get('event') != 'stage_completed' or
            journal[-1].get('count') != 3 or
            [x.get('event') for x in journal[1:-1]] !=
            [event for _ in smoke.IDS for event in ('request_intent','request_started','request_finished')]):
        raise ValueError('Protocol smoke did not close in exact three-request order')
    total = Decimal(0)
    plan = study.verify(smoke.CONFIG, 'fresh1', smoke.PLAN_SHA)
    original, _ = study.historical(smoke.CONFIG)
    model, endpoint = original['model_catalog_entry'], original['provider_endpoint']
    for request, attempt, wire_row, result in zip(manifest['requests'], attempts, raw, parsed):
        rid, aid = request['record_id'], attempt.get('attempt_id')
        if (attempt.get('status') != 'ok' or attempt.get('cost_unknown') is not False or
                not isinstance(aid, str) or not aid or
                any(x.get('attempt_id') != aid or x.get('id') != rid for x in (attempt,wire_row,result)) or
                wire_row.get('http_status') != 200 or wire_row.get('body_truncated_at_limit') is not False or
                wire_row.get('request_sha256') != request['request_sha256'] or
                journal[1+3*list(smoke.IDS).index(rid)].get('request_sha256') != request['request_sha256'] or
                journal[2+3*list(smoke.IDS).index(rid)].get('attempt_id') != aid or
                journal[3+3*list(smoke.IDS).index(rid)].get('attempt_id') != aid):
            raise ValueError('Protocol smoke attempt or request binding differs')
        try:
            wire = base64.b64decode(wire_row['body_base64'], validate=True)
            body = json.loads(wire)
            actual = paid.number(attempt['actual_cost_usd'])
        except (ValueError, KeyError, TypeError):
            raise ValueError('Protocol smoke response cannot be verified') from None
        classified = frozen.runner.classify(body, model, endpoint)
        diagnostic = audit_response(body, 'openrouter_paid_v1', study.CONTEXT-study.MAX_TOKENS)
        if (smoke.digest_bytes(wire) != wire_row.get('body_sha256') or
                wire_row.get('body_sha256') != attempt.get('body_sha256') or
                result.get('body_sha256') != attempt.get('body_sha256') or
                classified['status'] != 'ok' or diagnostic['passed'] is not True or
                classified['prediction'] != result.get('prediction') or
                body.get('usage') != result.get('usage') or
                paid.number(body['usage']['cost']) != actual or
                actual > study.RESERVE):
            raise ValueError('Protocol smoke parsed or billing evidence differs')
        total += actual
    if total != paid.number(inspection.get('known_cost_usd')):
        raise ValueError('Protocol smoke inspected cost differs')
    reconciliation_path = base/'budget-reconciliation.json'
    reconciliation = json.loads(reconciliation_path.read_text())
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != smoke.PID or
            paid.number(reconciliation.get('known_actual_usd')) != total or
            paid.number(reconciliation.get('unknown_upper_bound_usd')) != 0 or
            smoke.sha(reconciliation['child_ledger']) != reconciliation.get('child_sha256')):
        raise ValueError('Protocol smoke child is not sealed at known cost')
    return {'manifest_sha256':manifest_sha,
            'inspection_sha256':smoke.sha(inspection_path),
            'reconciliation_sha256':smoke.sha(reconciliation_path),
            'evidence_sha256':{name:smoke.sha(base/name) for name in SMOKE_FILES},
            'ids':list(smoke.IDS), 'valid_count':3, 'invalid_count':0,
            'known_cost_usd':str(total)}


def manifest_value():
    plan = study.verify(smoke.CONFIG, 'fresh1', smoke.PLAN_SHA)
    frozen.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
    gate = smoke_closure()
    requests = plan['conditions']['P0']['development']
    if len(requests) != 60 or [x['record_id'] for x in requests] != [f'DEV-{i:03d}' for i in range(1,61)]:
        raise ValueError('Frozen full development membership differs')
    for request in requests:
        if study.digest(json.dumps(request['payload'],sort_keys=True)) != request['request_sha256']:
            raise ValueError('Frozen full request payload differs')
    return {'schema':SCHEMA, 'status':'prepared_not_admitted',
            'configuration_id':smoke.CONFIG, 'fresh_pass':'fresh1', 'condition':'P0',
            'phase':'development', 'reference_labels_read':False,
            'frozen_plan_sha256':smoke.PLAN_SHA,
            'frozen_execution_manifest_sha256':smoke.EXECUTION_SHA,
            'protocol_smoke_gate':gate,
            'source_sha256':{name:smoke.sha(study.ROOT/name) for name in SOURCE_PATHS},
            'input_file_sha256':smoke.sha(study.ROOT/study.INPUTS),
            'ids':[x['record_id'] for x in requests], 'request_count':60,
            'per_request_full_context_reserve_usd':str(study.RESERVE),
            'proposed_child_cap_usd':str(CAP), 'budget_master_cap_usd':'12.38',
            'budget_partition_id':PID, 'requests':requests}


def prepare(base=BASE):
    base=Path(base);value=manifest_value();base.mkdir(parents=True,exist_ok=True)
    with (base/'manifest.json').open('x') as out:paid.durable(out,value)
    return smoke.digest_bytes(smoke.canonical(value))


def verify(base=BASE):
    saved=json.loads((Path(base)/'manifest.json').read_text())
    if saved!=manifest_value():raise ValueError('Mistral v3 development manifest or gate drift')
    return saved,smoke.digest_bytes(smoke.canonical(saved))


def expected_receipt(manifest,digest,budget_manifest):
    return {'schema':SCHEMA+'-root-review','approved':True,'manifest_sha256':digest,
            'runner_sha256':manifest['source_sha256']['scripts/mistral119_v3_development.py'],
            'protocol_smoke_inspection_sha256':manifest['protocol_smoke_gate']['inspection_sha256'],
            'budget_manifest_sha256':smoke.sha(budget_manifest),'budget_partition_id':PID,
            'child_cap_usd':str(CAP),'ids':manifest['ids'],
            'reference_labels_sent':False,'stage':'fresh1/P0/development'}


def review_receipt(path,manifest,digest,budget_manifest,base):
    if Path(path).resolve()!=(Path(base)/'development.root-review.json').resolve():
        raise ValueError('Wrong development root receipt path')
    value=json.loads(Path(path).read_text())
    if any(value.get(k)!=v for k,v in expected_receipt(manifest,digest,budget_manifest).items()):
        raise ValueError('Mistral development root receipt differs')
    if not isinstance(value.get('reviewer'),str) or not value['reviewer'].strip():
        raise ValueError('Named root reviewer required')
    return value


def run(receipt_path,budget_manifest,base=BASE,send=smoke.post,
        live=frozen.live_controls,open_child=partitions.open_partition,
        load_key=paid.load_key,env_file=None):
    base,budget_manifest=Path(base),Path(budget_manifest)
    manifest,digest=verify(base)
    review_receipt(receipt_path,manifest,digest,budget_manifest,base)
    paths={name:base/('development.'+name) for name in
           ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Mistral v3 development already claimed')
    plan=study.verify(smoke.CONFIG,'fresh1',smoke.PLAN_SHA)
    model,endpoint,reserve=live(plan,'P0')
    if reserve!=study.RESERVE:raise ValueError('Live Mistral reserve differs')
    ledger=open_child(smoke.MASTER,budget_manifest,PID,study.MODEL,study.PROVIDER,'none')
    try:
        _,pending,blocked=ledger.state()
        if (ledger.master_cap!=Decimal('12.38') or ledger.cap!=CAP or
                ledger.accounted()!=0 or pending or blocked or ledger.closed or
                ledger.cap<study.RESERVE):
            raise ValueError('Fresh development child lacks one full reserve')
        token=load_key(env_file)
        with paths['claim.json'].open('x') as out:
            paid.durable(out,{'schema':SCHEMA+'-claim','manifest_sha256':digest,
                              'root_review_sha256':smoke.sha(receipt_path),
                              'budget_manifest_sha256':smoke.sha(budget_manifest),
                              'ids':manifest['ids'],'claimed_utc':smoke.now()})
        with paths['journal.jsonl'].open('x') as journal,paths['raw.jsonl'].open('x') as raw_file,\
             paths['attempts.jsonl'].open('x') as attempts,paths['parsed.jsonl'].open('x') as parsed:
            paid.durable(journal,{'event':'stage_started','utc':smoke.now(),'count':60})
            for item in manifest['requests']:
                rid=item['record_id']
                try:
                    verify(base)
                    model,endpoint,current_reserve=live(plan,'P0')
                    if current_reserve!=study.RESERVE:raise ValueError('Live Mistral reserve changed')
                    if ledger.accounted()+study.RESERVE>ledger.cap:
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'insufficient_full_reserve','utc':smoke.now()})
                        raise ValueError('Mistral child lacks next full reserve')
                    paid.durable(journal,{'event':'request_intent','id':rid,
                                         'request_sha256':item['request_sha256'],'utc':smoke.now()})
                    aid=ledger.reserve(study.RESERVE,rid)
                    paid.durable(journal,{'event':'request_started','id':rid,
                                         'attempt_id':aid,'request_sha256':item['request_sha256'],
                                         'live_endpoint':endpoint,'utc':smoke.now()})
                    started=smoke.now();t0=time.perf_counter_ns()
                    try:status,wire,oversized=send(item['payload'],token)
                    except BaseException as error:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'transport_error',
                                               'error_type':type(error).__name__,
                                               'cost_unknown':True,'reserved_cost_usd':str(study.RESERVE)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'transport_outcome_unknown','utc':smoke.now()})
                        raise
                    paid.durable(raw_file,{'id':rid,'attempt_id':aid,'http_status':status,
                                           'request_sha256':item['request_sha256'],
                                           'body_base64':base64.b64encode(wire).decode(),
                                           'body_sha256':smoke.digest_bytes(wire),
                                           'body_truncated_at_limit':oversized,
                                           'started_utc':started,'ended_utc':smoke.now(),
                                           'client_request_elapsed_ns':time.perf_counter_ns()-t0})
                    try:body=json.loads(wire) if not oversized else None
                    except (ValueError,UnicodeDecodeError):body=None
                    usage=body.get('usage') if isinstance(body,dict) else None
                    try:actual=paid.number(usage['cost']) if isinstance(usage,dict) and usage.get('cost') is not None else None
                    except ValueError:actual=None
                    if actual is None:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'unknown_cost',
                                               'http_status':status,'cost_unknown':True,
                                               'reserved_cost_usd':str(study.RESERVE)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'unknown_cost','utc':smoke.now()})
                        raise ValueError('Unknown Mistral cost; full reserve retained')
                    billing_ok=ledger.settle(aid,actual)
                    if not billing_ok:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'observed_cost_over_bound',
                                               'http_status':status,'cost_unknown':False,
                                               'reserved_cost_usd':str(study.RESERVE),
                                               'actual_cost_usd':str(actual)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'observed_cost_over_bound','utc':smoke.now()})
                        raise ValueError('Observed Mistral cost blocked child')
                    if status!=200:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'http_error',
                                               'http_status':status,'cost_unknown':False,
                                               'actual_cost_usd':str(actual)})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'http_error','utc':smoke.now()})
                        raise ValueError('Mistral HTTP error; no retry')
                    try:
                        classified=(frozen.runner.classify(body,model,endpoint)
                                    if isinstance(body,dict) else {'status':'malformed_response'})
                        diagnostic=audit_response(body,'openrouter_paid_v1',study.CONTEXT-study.MAX_TOKENS)
                    except (TypeError,ValueError,AttributeError,KeyError):
                        classified={'status':'malformed_response'}
                        diagnostic={'passed':False,'blockers':['malformed_response']}
                    if classified['status']!='ok' or not diagnostic['passed']:
                        paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'invalid_response',
                                               'response_status':classified['status'],
                                               'cost_unknown':False,'actual_cost_usd':str(actual),
                                               'diagnostic':diagnostic})
                        paid.durable(journal,{'event':'stage_stopped','id':rid,
                                              'reason':'invalid_response','utc':smoke.now()})
                        raise ValueError('Invalid Mistral output; no repair or retry')
                    paid.durable(attempts,{'id':rid,'attempt_id':aid,'status':'ok',
                                           'cost_unknown':False,'actual_cost_usd':str(actual),
                                           'body_sha256':smoke.digest_bytes(wire)})
                    paid.durable(parsed,{'id':rid,'attempt_id':aid,
                                         'prediction':classified['prediction'],
                                         'returned_model':body['model'],
                                         'returned_provider':body['provider'],
                                         'usage':usage,'body_sha256':smoke.digest_bytes(wire)})
                    paid.durable(journal,{'event':'request_finished','id':rid,
                                         'attempt_id':aid,'utc':smoke.now()})
                except BaseException as error:
                    paid.durable(journal,{'event':'stage_aborted','id':rid,
                                          'error_type':type(error).__name__,'utc':smoke.now()})
                    raise
            paid.durable(journal,{'event':'stage_completed','count':60,'utc':smoke.now()})
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
