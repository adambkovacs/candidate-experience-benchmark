#!/usr/bin/env python3
"""Offline manifests for the eight remaining Mistral119 none repeat phases.

This module does not dispatch requests or issue receipts. Each phase needs a
fresh three-request smoke, root inspection, and separately admitted full pass.
"""
import argparse
import base64
import json
from decimal import Decimal
from pathlib import Path
import time

import mistral119_v3_smoke as smoke
import mistral119_v3_development as first
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA='mistral119-none-v3-remaining-phase-plan-v1'
STAGES=(('fresh1','P1'),('fresh1','P2'),('fresh2','P1'),('fresh2','P2'),
        ('fresh2','P0'),('fresh3','P2'),('fresh3','P0'),('fresh3','P1'))
PLAN_SHA={
    'fresh1':'fbfa58d15d3aeff20d819c8e37bba8d16e0e5c53775cb0c1f11b404149f34f07',
    'fresh2':'eb06e3fd1ae23ee293e5566b4e869ab82f1d96e257bc98aaf170a7b48fa456e3',
    'fresh3':'776bcda87ca54e3afce3c4c1c563e1a9edc96bcf7242d7987883801c6a547743',
}
SMOKE_CAP=study.RESERVE*3
DEVELOPMENT_CAP=Decimal('0.25')
BASE=study.BASE/'v3-remaining-none-v1'
FIRST_BASE=study.BASE/'v3-development-none-v1'/'fresh1'/'P0'
SUFFIX_BASE=BASE/'fresh1'/'P0-suffix-049-060'
SUFFIX_CAP=Decimal('0.25')
INTERRUPTION_SHA='710352d03d341e48d17b0d33a0cca585c5e0d00af5eebd57cec1dadd9cd5f5c3'
SOURCE_PATHS=(*smoke.SOURCE_PATHS,
              'scripts/mistral119_v3_development.py',
              'tests/test_mistral119_v3_development.py',
              'scripts/mistral119_v3_remaining_phases.py',
              'tests/test_mistral119_v3_remaining_phases.py')


def stage_index(repeat,condition):
    try:return STAGES.index((repeat,condition))
    except ValueError:raise ValueError('Stage is outside eight declared phases') from None


def predecessor(repeat,condition):
    index=stage_index(repeat,condition)
    return ('fresh1','P0') if index==0 else STAGES[index-1]


def folder(repeat,condition,base=BASE):
    stage_index(repeat,condition)
    return Path(base)/repeat/condition


def suffix_manifest_value():
    plan=study.verify(smoke.CONFIG,'fresh1',PLAN_SHA['fresh1'])
    frozen.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
    if smoke.sha(FIRST_BASE/'development.terminal-public.json')!=INTERRUPTION_SHA:
        raise ValueError('Original interrupted P0 terminal evidence differs')
    requests=plan['conditions']['P0']['development'][48:60]
    if [x['record_id'] for x in requests]!=[f'DEV-{i:03d}' for i in range(49,61)]:
        raise ValueError('Original unsent suffix membership differs')
    for request in requests:
        if study.digest(json.dumps(request['payload'],sort_keys=True))!=request['request_sha256']:
            raise ValueError('Frozen suffix request body differs')
    return {'schema':SCHEMA+'-suffix','status':'offline_prepared_no_receipt_no_dispatch',
            'configuration_id':smoke.CONFIG,'fresh_pass':'fresh1','condition':'P0',
            'phase':'suffix','reference_labels_read':False,'original_failed_id':'DEV-048',
            'original_interruption_sha256':INTERRUPTION_SHA,
            'frozen_plan_sha256':PLAN_SHA['fresh1'],
            'frozen_execution_manifest_sha256':smoke.EXECUTION_SHA,
            'source_sha256':{name:smoke.sha(study.ROOT/name) for name in SOURCE_PATHS},
            'input_file_sha256':smoke.sha(study.ROOT/study.INPUTS),
            'per_request_full_context_reserve_usd':str(study.RESERVE),
            'child_cap_usd':str(SUFFIX_CAP), 'suffix_requests':requests}


def prepare_suffix(base=SUFFIX_BASE):
    value=suffix_manifest_value();path=Path(base)/'manifest.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as out:paid.durable(out,value)
    return smoke.digest_bytes(smoke.canonical(value))


def verify_suffix(base=SUFFIX_BASE):
    saved=json.loads((Path(base)/'manifest.json').read_text())
    if saved!=suffix_manifest_value():raise ValueError('Mistral suffix manifest or source drift')
    return saved,smoke.digest_bytes(smoke.canonical(saved))


def manifest_value(repeat,condition):
    previous=predecessor(repeat,condition)
    plan=study.verify(smoke.CONFIG,repeat,PLAN_SHA[repeat])
    frozen.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
    if plan['condition_order']!=study.ORDERS[repeat] or plan['reference_labels_read'] is not False:
        raise ValueError('Frozen repeat order or reference isolation changed')
    smoke_requests=plan['conditions'][condition]['smoke']
    development=plan['conditions'][condition]['development']
    expected=[f'DEV-{i:03d}' for i in range(1,61)]
    if ([r['record_id'] for r in smoke_requests]!=expected[:3] or
            [r['record_id'] for r in development]!=expected):
        raise ValueError('Frozen smoke or development membership changed')
    for request in development:
        if (study.digest(json.dumps(request['payload'],sort_keys=True))!=request['request_sha256'] or
                set(request['payload']['messages'][1])!={'role','content'} or
                request['payload']['messages'][1]['role']!='user'):
            raise ValueError('Frozen request body changed')
    return {
        'schema':SCHEMA,'status':'offline_prepared_no_receipt_no_dispatch',
        'configuration_id':smoke.CONFIG,'fresh_pass':repeat,'condition':condition,
        'previous_full_phase':{'fresh_pass':previous[0],'condition':previous[1]},
        'frozen_plan_sha256':PLAN_SHA[repeat],
        'frozen_execution_manifest_sha256':smoke.EXECUTION_SHA,
        'reference_labels_read':False,'repeat_pass_credit':'only_after_full_60_verified',
        'smoke_gate':'three_sent_then_root_raw_inspection_before_development',
        'development_gate':'separately_reviewed_receipt_after_smoke_inspection',
        'smoke_child_cap_usd':str(SMOKE_CAP),
        'development_child_cap_usd':str(DEVELOPMENT_CAP),
        'per_request_full_context_reserve_usd':str(study.RESERVE),
        'source_sha256':{name:smoke.sha(study.ROOT/name) for name in SOURCE_PATHS},
        'input_file_sha256':smoke.sha(study.ROOT/study.INPUTS),
        'smoke_requests':smoke_requests,'development_requests':development,
    }


def prepare(repeat,condition,base=BASE):
    value=manifest_value(repeat,condition)
    path=folder(repeat,condition,base)/'manifest.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as out:paid.durable(out,value)
    return smoke.digest_bytes(smoke.canonical(value))


def verify(repeat,condition,base=BASE):
    path=folder(repeat,condition,base)/'manifest.json'
    saved=json.loads(path.read_text())
    if saved!=manifest_value(repeat,condition):
        raise ValueError('Mistral remaining-phase manifest or source drift')
    return saved,smoke.digest_bytes(smoke.canonical(saved))


def phase_files(stage_folder,phase):
    return {name:Path(stage_folder)/(phase+'.'+name) for name in
            ('claim.json','journal.jsonl','attempts.jsonl','raw.jsonl','parsed.jsonl')}


def budget_manifest_path(stage_folder,phase):
    if phase not in ('smoke','development','suffix'):
        raise ValueError('Unknown phase budget manifest')
    return Path(stage_folder)/(phase+'.budget-manifest.json')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def closed_phase(stage_folder,phase,requests,manifest_sha):
    """Reconstruct a completed known-billed phase from its private source bytes."""
    files=phase_files(stage_folder,phase)
    claim=json.loads(files['claim.json'].read_text())
    receipt_path=Path(stage_folder)/(phase+'.root-review.json')
    budget_path=budget_manifest_path(stage_folder,phase)
    receipt=json.loads(receipt_path.read_text())
    journal=rows(files['journal.jsonl'])
    attempts,raw,parsed=(rows(files[x]) for x in ('attempts.jsonl','raw.jsonl','parsed.jsonl'))
    ids=[x['record_id'] for x in requests]
    count=len(ids)
    if (claim.get('manifest_sha256')!=manifest_sha or claim.get('ids')!=ids or
            claim.get('root_review_sha256')!=smoke.sha(receipt_path) or
            claim.get('budget_manifest_sha256')!=smoke.sha(budget_path) or
            claim.get('gate_sha256')!=receipt.get('gate_sha256') or
            receipt.get('manifest_sha256')!=manifest_sha or
            receipt.get('ids')!=ids or receipt.get('reference_labels_sent') is not False or
            [x.get('id') for x in attempts]!=ids or
            [x.get('id') for x in raw]!=ids or
            [x.get('id') for x in parsed]!=ids or
            len(journal)!=3*count+2 or
            journal[0].get('event')!='stage_started' or
            journal[-1].get('event')!='stage_completed' or
            journal[-1].get('count')!=count):
        raise ValueError('Closed phase identity, membership or terminal event differs')
    original,_=study.historical(smoke.CONFIG)
    model,endpoint=original['model_catalog_entry'],original['provider_endpoint']
    attempt_ids=[];total=Decimal(0)
    for index,(request,attempt,wire_row,result) in enumerate(zip(requests,attempts,raw,parsed)):
        rid,aid=request['record_id'],attempt.get('attempt_id')
        expected_events=('request_intent','request_started','request_finished')
        events=journal[1+3*index:4+3*index]
        if (not isinstance(aid,str) or not aid or
                attempt.get('status')!='ok' or attempt.get('cost_unknown') is not False or
                attempt.get('reserved_cost_usd',str(study.RESERVE))!=str(study.RESERVE) or
                any(x.get('attempt_id')!=aid for x in (attempt,wire_row,result)) or
                any(x.get('event')!=event or x.get('id')!=rid
                    for x,event in zip(events,expected_events)) or
                events[0].get('request_sha256')!=request['request_sha256'] or
                events[1].get('request_sha256')!=request['request_sha256'] or
                any(x.get('attempt_id')!=aid for x in events[1:]) or
                wire_row.get('http_status')!=200 or
                wire_row.get('body_truncated_at_limit') is not False or
                wire_row.get('request_sha256')!=request['request_sha256']):
            raise ValueError('Closed phase attempt or request binding differs')
        try:
            wire=base64.b64decode(wire_row['body_base64'],validate=True)
            body=json.loads(wire)
            cost=paid.number(attempt['actual_cost_usd'])
            extracted=frozen.runner.classify(body,model,endpoint)
            diagnostic=audit_response(body,'openrouter_paid_v1',study.CONTEXT-study.MAX_TOKENS)
        except (ValueError,TypeError,KeyError,AttributeError):
            raise ValueError('Closed phase raw response cannot be verified') from None
        if (smoke.digest_bytes(wire)!=wire_row.get('body_sha256') or
                attempt.get('body_sha256')!=wire_row.get('body_sha256') or
                result.get('body_sha256')!=wire_row.get('body_sha256') or
                extracted['status']!='ok' or diagnostic['passed'] is not True or
                extracted['prediction']!=result.get('prediction') or
                result.get('returned_model')!=body.get('model') or
                result.get('returned_provider')!=body.get('provider') or
                result.get('usage')!=body.get('usage') or
                paid.number(body['usage']['cost'])!=cost or cost>study.RESERVE):
            raise ValueError('Closed phase parsed response or billing differs')
        total+=cost;attempt_ids.append(aid)
    if len(set(attempt_ids))!=count:
        raise ValueError('Closed phase attempt IDs repeat')
    reconciliation_path=Path(stage_folder)/(phase+'.budget-reconciliation.json')
    reconciliation=json.loads(reconciliation_path.read_text())
    if (reconciliation.get('event')!='partition_reconciled' or
            reconciliation.get('partition_id')!=receipt.get('budget_partition_id') or
            paid.number(reconciliation.get('known_actual_usd'))!=total or
            paid.number(reconciliation.get('unknown_upper_bound_usd'))!=0 or
            smoke.sha(reconciliation['child_ledger'])!=reconciliation.get('child_sha256')):
        raise ValueError('Closed phase child is not sealed at known cost')
    return {'manifest_sha256':manifest_sha,
            'source_sha256':{name:smoke.sha(path) for name,path in files.items()},
            'budget_reconciliation_sha256':smoke.sha(reconciliation_path),
            'count':count,'known_cost_usd':str(total),'ids':ids}


def terminal_review(stage_folder,binding,phase='development',count=60):
    path=Path(stage_folder)/(phase+'.terminal-review.json')
    value=json.loads(path.read_text())
    if (value.get('schema')!='mistral119-v3-development-terminal-review-v1' or
            value.get('reviewer')!='root' or value.get('terminal_exit_code')!=0 or
            value.get('manifest_sha256')!=binding['manifest_sha256'] or
            value.get('source_sha256')!=binding['source_sha256'] or
            value.get('budget_reconciliation_sha256')!=binding['budget_reconciliation_sha256'] or
            value.get('valid_count')!=count or value.get('invalid_count')!=0 or
            value.get('ids')!=binding['ids']):
        raise ValueError('Root-verified predecessor terminal closure differs')
    return smoke.sha(path)


def interrupted_gate():
    manifest,manifest_sha=first.verify(FIRST_BASE)
    terminal_path=FIRST_BASE/'development.terminal-public.json'
    if smoke.sha(terminal_path)!=INTERRUPTION_SHA:
        raise ValueError('Original P0 interruption hash differs')
    terminal=json.loads(terminal_path.read_text())
    files=phase_files(FIRST_BASE,'development')
    actual_hashes={path.name:smoke.sha(path) for path in files.values()}
    actual_hashes['development.root-review.json']=smoke.sha(FIRST_BASE/'development.root-review.json')
    attempts,raw,parsed=(rows(files[name]) for name in ('attempts.jsonl','raw.jsonl','parsed.jsonl'))
    journal=rows(files['journal.jsonl'])
    ids=[f'DEV-{i:03d}' for i in range(1,61)]
    if (terminal.get('manifest_sha256')!=manifest_sha or
            terminal.get('original_session')!=17315 or
            terminal.get('terminal_exit_code')!=1 or
            terminal.get('source_sha256')!=actual_hashes or
            terminal.get('status')!='interrupted_unscored' or
            terminal.get('valid_count')!=47 or terminal.get('invalid_count')!=0 or
            terminal.get('unknown_outcome_count')!=1 or terminal.get('unknown_id')!='DEV-048' or
            terminal.get('unsent_ids')!=ids[48:] or terminal.get('score') is not None or
            terminal.get('reference_labels_sent') is not False or
            [x.get('id') for x in attempts]!=ids[:48] or
            [x.get('id') for x in raw]!=ids[:47] or
            [x.get('id') for x in parsed]!=ids[:47] or
            len(journal)!=146 or journal[-1].get('event')!='stage_aborted' or
            journal[-1].get('id')!='DEV-048' or
            attempts[-1].get('status')!='transport_error' or
            attempts[-1].get('cost_unknown') is not True or
            attempts[-1].get('reserved_cost_usd')!=str(study.RESERVE)):
        raise ValueError('Original P0 interrupted attempts or terminal state differ')
    known=Decimal(0)
    original,_=study.historical(smoke.CONFIG)
    model,endpoint=original['model_catalog_entry'],original['provider_endpoint']
    for index,(request,attempt,wire_row,result) in enumerate(
            zip(manifest['requests'][:47],attempts[:47],raw,parsed)):
        aid=attempt.get('attempt_id')
        if (attempt.get('status')!='ok' or attempt.get('cost_unknown') is not False or
                not isinstance(aid,str) or not aid or
                any(x.get('attempt_id')!=aid for x in (attempt,wire_row,result)) or
                wire_row.get('request_sha256')!=request['request_sha256'] or
                wire_row.get('http_status')!=200 or
                wire_row.get('body_truncated_at_limit') is not False or
                [x.get('event') for x in journal[1+3*index:4+3*index]]!=
                ['request_intent','request_started','request_finished']):
            raise ValueError('Original P0 valid prefix binding differs')
        try:
            wire=base64.b64decode(wire_row['body_base64'],validate=True)
            body=json.loads(wire)
            predicted=frozen.runner.classify(body,model,endpoint)
            cost=paid.number(body['usage']['cost'])
        except (ValueError,TypeError,KeyError,AttributeError):
            raise ValueError('Original P0 valid raw response cannot be verified') from None
        if (smoke.digest_bytes(wire)!=attempt.get('body_sha256') or
                wire_row.get('body_sha256')!=attempt.get('body_sha256') or
                result.get('body_sha256')!=attempt.get('body_sha256') or
                predicted['status']!='ok' or predicted['prediction']!=result.get('prediction') or
                result.get('returned_model')!=body.get('model') or
                result.get('returned_provider')!=body.get('provider') or
                result.get('usage')!=body.get('usage') or
                audit_response(body,'openrouter_paid_v1',study.CONTEXT-study.MAX_TOKENS)['passed'] is not True or
                cost!=paid.number(attempt['actual_cost_usd']) or cost>study.RESERVE):
            raise ValueError('Original P0 valid response or cost differs')
        known+=cost
    reconciliation=json.loads((FIRST_BASE/'budget-reconciliation.json').read_text())
    if (known!=paid.number(terminal['known_cost_usd']) or
            paid.number(terminal['unknown_cost_upper_bound_usd'])!=study.RESERVE or
            reconciliation.get('partition_id')!=first.PID or
            paid.number(reconciliation.get('known_actual_usd'))!=known or
            paid.number(reconciliation.get('unknown_upper_bound_usd'))!=study.RESERVE or
            smoke.sha(reconciliation['child_ledger'])!=reconciliation.get('child_sha256') or
            terminal.get('sealed_child_sha256')!=reconciliation.get('child_sha256')):
        raise ValueError('Original P0 sealed unknown accounting differs')
    review_path=FIRST_BASE/'development.interruption-review.json'
    review=json.loads(review_path.read_text())
    if (review.get('schema')!='mistral119-v3-development-interruption-review-v1' or
            review.get('reviewer')!='root' or review.get('verdict')!='accepted_unchanged' or
            review.get('terminal_public_sha256')!=INTERRUPTION_SHA or
            review.get('failed_id')!='DEV-048' or
            review.get('permitted_unsent_ids')!=ids[48:] or
            review.get('unknown_upper_bound_usd')!=str(study.RESERVE) or
            review.get('no_replay_of_failed_id') is not True):
        raise ValueError('Root interruption review gate missing or differs')
    return {'terminal_public_sha256':INTERRUPTION_SHA,
            'interruption_review_sha256':smoke.sha(review_path),
            'budget_reconciliation_sha256':smoke.sha(FIRST_BASE/'budget-reconciliation.json'),
            'valid_count':47,'unknown_id':'DEV-048','unsent_ids':ids[48:]}


def composite_gate():
    interrupted=interrupted_gate()
    manifest,manifest_sha=verify_suffix()
    suffix=closed_phase(SUFFIX_BASE,'suffix',manifest['suffix_requests'],manifest_sha)
    suffix['terminal_review_sha256']=terminal_review(SUFFIX_BASE,suffix,'suffix',12)
    path=FIRST_BASE/'development.composite-review.json'
    review=json.loads(path.read_text())
    if (review.get('schema')!='mistral119-v3-p0-composite-review-v1' or
            review.get('reviewer')!='root' or review.get('verdict')!='accepted_with_unknown' or
            review.get('interruption_gate_sha256')!=smoke.digest_bytes(smoke.canonical(interrupted)) or
            review.get('suffix_gate_sha256')!=smoke.digest_bytes(smoke.canonical(suffix)) or
            review.get('valid_count')!=59 or review.get('unknown_id')!='DEV-048' or
            review.get('total_positions')!=60 or review.get('score') is not None):
        raise ValueError('P0 composite retains unknown position and root review')
    return {'interrupted':interrupted,'suffix':suffix,'composite_review_sha256':smoke.sha(path)}


def predecessor_gate(repeat,condition):
    previous=predecessor(repeat,condition)
    if previous==('fresh1','P0'):
        return {'fresh_pass':'fresh1','condition':'P0','composite':composite_gate()}
    stage_folder=folder(*previous)
    manifest,manifest_sha=verify(*previous)
    requests=manifest['development_requests']
    binding=closed_phase(stage_folder,'development',requests,manifest_sha)
    binding['terminal_review_sha256']=terminal_review(stage_folder,binding)
    binding['fresh_pass'],binding['condition']=previous
    return binding


def smoke_inspection(repeat,condition,manifest,manifest_sha):
    stage_folder=folder(repeat,condition)
    binding=closed_phase(stage_folder,'smoke',manifest['smoke_requests'],manifest_sha)
    path=stage_folder/'smoke.inspection.json'
    value=json.loads(path.read_text())
    if (value.get('schema')!='mistral119-v3-phase-smoke-inspection-v1' or
            value.get('reviewer')!='root' or value.get('verdict')!='PASS' or
            value.get('raw_responses_inspected') is not True or
            value.get('terminal_exit_code')!=0 or
            value.get('manifest_sha256')!=manifest_sha or
            value.get('source_sha256')!=binding['source_sha256'] or
            value.get('budget_reconciliation_sha256')!=binding['budget_reconciliation_sha256'] or
            value.get('ids')!=binding['ids'] or
            value.get('valid_count')!=3 or value.get('invalid_count')!=0 or
            paid.number(value.get('known_cost_usd'))!=paid.number(binding['known_cost_usd'])):
        raise ValueError('Current smoke raw inspection or terminal closure differs')
    binding['inspection_sha256']=smoke.sha(path)
    return binding


def gate(repeat,condition,phase,manifest,manifest_sha):
    if phase=='suffix':
        if (repeat,condition)!=('fresh1','P0'):
            raise ValueError('Suffix is exact first P0 only')
        return {'interrupted':interrupted_gate()}
    if phase not in ('smoke','development'):raise ValueError('Unknown phase')
    predecessor_binding=predecessor_gate(repeat,condition)
    result={'predecessor':predecessor_binding}
    if phase=='development':
        result['smoke']=smoke_inspection(repeat,condition,manifest,manifest_sha)
    return result


def partition_id(repeat,condition,phase):
    if phase=='suffix' and (repeat,condition)==('fresh1','P0'):
        return 'mistral119-none-v3-fresh1-p0-suffix-049-060-v1'
    stage_index(repeat,condition)
    if phase not in ('smoke','development'):raise ValueError('Unknown phase')
    return 'mistral119-none-v3-'+repeat+'-'+condition.lower()+'-'+phase+'-v1'


def expected_receipt(repeat,condition,phase,manifest,manifest_sha,budget_manifest,gate_binding):
    requests=manifest[phase+'_requests']
    cap=SMOKE_CAP if phase=='smoke' else SUFFIX_CAP if phase=='suffix' else DEVELOPMENT_CAP
    return {'schema':'mistral119-none-v3-remaining-stage-review-v1','approved':True,
            'manifest_sha256':manifest_sha,
            'runner_sha256':manifest['source_sha256']['scripts/mistral119_v3_remaining_phases.py'],
            'gate_sha256':smoke.digest_bytes(smoke.canonical(gate_binding)),
            'budget_manifest_sha256':smoke.sha(budget_manifest),
            'budget_partition_id':partition_id(repeat,condition,phase),
            'child_cap_usd':str(cap),'fresh_pass':repeat,'condition':condition,
            'phase':phase,'ids':[x['record_id'] for x in requests],
            'reference_labels_sent':False}


def review_receipt(path,repeat,condition,phase,manifest,manifest_sha,budget_manifest,gate_binding):
    stage_folder=SUFFIX_BASE if phase=='suffix' else folder(repeat,condition)
    if Path(path).resolve()!=(stage_folder/(phase+'.root-review.json')).resolve():
        raise ValueError('Wrong phase root receipt path')
    value=json.loads(Path(path).read_text())
    expected=expected_receipt(repeat,condition,phase,manifest,manifest_sha,budget_manifest,gate_binding)
    if any(value.get(key)!=wanted for key,wanted in expected.items()):
        raise ValueError('Root phase receipt differs')
    if not isinstance(value.get('reviewer'),str) or not value['reviewer'].strip():
        raise ValueError('Named root reviewer required')
    return value


def run(repeat,condition,phase,receipt_path,budget_manifest,
        send=smoke.post,live=frozen.live_controls,
        open_child=partitions.open_partition,load_key=paid.load_key,env_file=None):
    stage_folder=SUFFIX_BASE if phase=='suffix' and (repeat,condition)==('fresh1','P0') else folder(repeat,condition)
    budget_manifest=Path(budget_manifest)
    if budget_manifest.resolve()!=budget_manifest_path(stage_folder,phase).resolve():
        raise ValueError('Phase budget manifest must reside in its exact stage folder')
    manifest,manifest_sha=(verify_suffix() if phase=='suffix' else verify(repeat,condition))
    gate_binding=gate(repeat,condition,phase,manifest,manifest_sha)
    review_receipt(receipt_path,repeat,condition,phase,manifest,manifest_sha,
                   budget_manifest,gate_binding)
    files=phase_files(stage_folder,phase)
    if any(path.exists() for path in files.values()):
        raise FileExistsError('Mistral phase already claimed')
    plan=study.verify(smoke.CONFIG,repeat,PLAN_SHA[repeat])
    model,endpoint,reserve=live(plan,condition)
    if reserve!=study.RESERVE:raise ValueError('Live Mistral reserve differs')
    cap=SMOKE_CAP if phase=='smoke' else SUFFIX_CAP if phase=='suffix' else DEVELOPMENT_CAP
    ledger=open_child(smoke.MASTER,budget_manifest,partition_id(repeat,condition,phase),
                      study.MODEL,study.PROVIDER,'none')
    try:
        _,pending,blocked=ledger.state()
        if (ledger.master_cap!=Decimal('12.38') or ledger.cap!=cap or
                ledger.accounted()!=0 or pending or blocked or ledger.closed or
                ledger.cap<study.RESERVE):
            raise ValueError('Fresh phase child lacks full request admission')
        token=load_key(env_file)
        requests=manifest[phase+'_requests']
        ids=[x['record_id'] for x in requests]
        with files['claim.json'].open('x') as out:
            paid.durable(out,{'schema':SCHEMA+'-claim','manifest_sha256':manifest_sha,
                              'root_review_sha256':smoke.sha(receipt_path),
                              'budget_manifest_sha256':smoke.sha(budget_manifest),
                              'gate_sha256':smoke.digest_bytes(smoke.canonical(gate_binding)),
                              'ids':ids,'claimed_utc':smoke.now()})
        with files['journal.jsonl'].open('x') as journal,files['raw.jsonl'].open('x') as raw_file,\
             files['attempts.jsonl'].open('x') as attempts,files['parsed.jsonl'].open('x') as parsed:
            paid.durable(journal,{'event':'stage_started','utc':smoke.now(),'count':len(requests)})
            for item in requests:
                rid=item['record_id']
                try:
                    if phase=='suffix':verify_suffix()
                    else:verify(repeat,condition)
                    gate(repeat,condition,phase,manifest,manifest_sha)
                    model,endpoint,current_reserve=live(plan,condition)
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
            paid.durable(journal,{'event':'stage_completed','count':len(requests),'utc':smoke.now()})
    finally:ledger.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','verify','run'))
    p.add_argument('fresh_pass',choices=tuple(study.ORDERS))
    p.add_argument('condition',choices=study.CONDITIONS)
    p.add_argument('--phase',choices=('smoke','development','suffix'))
    p.add_argument('--base',type=Path,default=BASE)
    p.add_argument('--root-review-receipt',type=Path)
    p.add_argument('--budget-manifest',type=Path)
    p.add_argument('--env-file',type=Path)
    args=p.parse_args()
    if args.action=='prepare':
        if (args.fresh_pass,args.condition)==('fresh1','P0'):
            print(prepare_suffix())
        else:print(prepare(args.fresh_pass,args.condition,args.base))
    elif args.action=='verify':
        if (args.fresh_pass,args.condition)==('fresh1','P0'):
            print(verify_suffix()[1])
        else:print(verify(args.fresh_pass,args.condition,args.base)[1])
    else:
        if not args.phase or not args.root_review_receipt or not args.budget_manifest:
            p.error('run requires --phase, --root-review-receipt and --budget-manifest')
        run(args.fresh_pass,args.condition,args.phase,args.root_review_receipt,
            args.budget_manifest,env_file=args.env_file)


if __name__=='__main__':main()
