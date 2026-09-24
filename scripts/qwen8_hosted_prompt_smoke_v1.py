#!/usr/bin/env python3
"""Offline-gated Qwen8 P1/P2 smoke runner through unchanged hosted adapter."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import qwen8_hosted_adapter as adapter
import paid_budget_partitions_v2 as partitions_v2
from openrouter_paid_benchmark import number, reservation, select_rows

ROOT=Path(__file__).resolve().parents[1]
CAP=number('0.06')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source(binding):
    path=(ROOT/binding['file']).resolve();path.relative_to(ROOT)
    if sha(path)!=binding['sha256']:raise ValueError('Prompt smoke source hash mismatch: '+binding['file'])
    return path


def prepare(plan_path,plan_sha,budget_path=None,partition_id=None,review_path=None):
    plan_path=Path(plan_path).resolve();plan_path.relative_to(ROOT)
    if sha(plan_path)!=plan_sha:raise ValueError('Prompt smoke plan hash mismatch')
    plan=json.loads(plan_path.read_text());mode=plan.get('reasoning');variant=plan.get('variant')
    if plan.get('schema')!='qwen8-hosted-prompt-smoke-v1' or mode not in ('off','on') or variant not in ('P1','P2') or plan.get('phase')!='smoke3' or plan.get('model')!=adapter.MODEL or plan.get('provider')!=adapter.PROVIDER or plan.get('response_format')!='json_object':raise ValueError('Prompt smoke condition drift')
    if plan.get('record_ids')!=['DEV-001','DEV-002','DEV-003'] or plan.get('reference_labels_read') is not False or plan.get('automatic_retries') is not False or plan.get('continue_on_invalid_output') is not True:raise ValueError('Prompt smoke protocol drift')
    paths={key:source(value) for key,value in plan['sources'].items()}
    if paths['adapter']!=Path(adapter.__file__).resolve() or paths['partition_v2']!=Path(partitions_v2.__file__).resolve():raise ValueError('Bound code differs from loaded code')
    manifest=json.loads(paths['preview_manifest'].read_text())
    matches=[c for c in manifest['configs'] if c['file']==paths['preview'].name]
    if len(matches)!=1 or any(matches[0].get(k)!=v for k,v in (('reasoning',mode),('variant',variant),('phase','smoke3'),('rows',3))) or matches[0]['file_sha256']!=sha(paths['preview']):raise ValueError('Frozen preview differs')
    model,endpoint,_=adapter.load_saved();schema=json.loads(adapter.SCHEMA_PATH.read_text())
    text,audit=adapter.instruction(schema,variant,mode)
    if audit!=matches[0]['prompt_audit']:raise ValueError('Prompt audit differs')
    inputs=select_rows(adapter.read_rows(adapter.INPUT_PATH),'smoke',1)
    rows=[json.loads(line) for line in paths['preview'].read_text().splitlines() if line.strip()]
    if [r.get('id') for r in rows]!=plan['record_ids']:raise ValueError('Prompt smoke IDs differ')
    for row,item in zip(rows,inputs):
        expected=adapter.payload(model,endpoint,item['feedback'],text,mode)
        if row.get('request')!=expected or row.get('request_sha256')!=adapter.sha(adapter.canonical(expected)) or row.get('input_sha256')!=adapter.sha(item['feedback'].encode()) or row.get('reference_labels_read') is not False or row.get('inference_performed') is not False:raise ValueError('Prompt smoke request differs')
    reserve=reservation(endpoint,adapter.MAX_TOKENS,adapter.INPUT_CEILING,adapter.OUTPUT_CEILING)
    if reserve*3>CAP or plan.get('per_call_reserve_usd')!=str(reserve) or plan.get('three_call_bound_usd')!=str(reserve*3) or plan.get('proposed_partition_cap_usd')!=str(CAP):raise ValueError('Prompt smoke reserve bound differs')
    output=(ROOT/plan['output']).resolve();output.relative_to(ROOT)
    if output.exists() or Path(str(output)+'.attempts.jsonl').exists():raise FileExistsError('Prompt smoke output already exists; no replay')
    if budget_path is None and partition_id is None and review_path is None:return plan,paths,None
    if not budget_path or not partition_id or not review_path:raise ValueError('Execution requires budget, partition and root review')
    budget_path=Path(budget_path).resolve();review_path=Path(review_path).resolve();budget_path.relative_to(ROOT);review_path.relative_to(ROOT)
    receipt=json.loads(review_path.read_text())
    if receipt.get('approved') is not True or receipt.get('prompt_smoke_plan_sha256')!=plan_sha or receipt.get('wrapper_sha256')!=sha(__file__) or receipt.get('budget_manifest_sha256')!=sha(budget_path) or receipt.get('partition_id')!=partition_id or receipt.get('continue_on_invalid_output') is not True:raise ValueError('Missing exact root review')
    entries=[e for e in json.loads(budget_path.read_text()).get('partitions',[]) if e.get('id')==partition_id]
    if len(entries)!=1 or any(entries[0].get(k)!=v for k,v in (('model',adapter.MODEL),('provider',adapter.PROVIDER),('reasoning',mode))) or not reserve*3<=number(entries[0].get('cap_usd'))<=CAP:raise ValueError('Prompt smoke budget partition differs')
    adapter.reviewed_preview(paths['preview'],review_path)
    return plan,paths,(budget_path,partition_id,review_path)


def execute(plan,paths,budget):
    budget_path,partition_id,review_path=budget
    args=SimpleNamespace(preview_file=str(paths['preview']),review_receipt=str(review_path),partition_manifest=str(budget_path),partition_id=partition_id,output=str(ROOT/plan['output']),env_file=plan['env_file'],timeout=300)
    old=sys.modules.get('paid_budget_partitions')
    try:
        sys.modules['paid_budget_partitions']=partitions_v2
        adapter.execute(args)
    finally:
        if old is None:sys.modules.pop('paid_budget_partitions',None)
        else:sys.modules['paid_budget_partitions']=old


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--budget-partition-manifest');p.add_argument('--budget-partition-id');p.add_argument('--review')
    a=p.parse_args()
    if not a.execute and any((a.budget_partition_manifest,a.budget_partition_id,a.review)):raise ValueError('Budget arguments require --execute')
    plan,paths,budget=prepare(a.plan,a.sha256,a.budget_partition_manifest,a.budget_partition_id,a.review)
    if a.execute:execute(plan,paths,budget)
    else:print(json.dumps({'preflight':'ok','reasoning':plan['reasoning'],'variant':plan['variant'],'three_call_bound_usd':plan['three_call_bound_usd']}))

if __name__=='__main__':main()
