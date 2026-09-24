#!/usr/bin/env python3
"""Exact Qwen8 full60 gate after separately inspected P0 recovery smokes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import qwen8_hosted_adapter as adapter
import paid_budget_partitions_v2 as partitions_v2
from openrouter_paid_benchmark import number, reservation, select_rows

ROOT = Path(__file__).resolve().parents[1]
MAX_PARTITION = number('1.05')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(binding):
    path = (ROOT / binding['file']).resolve()
    path.relative_to(ROOT)
    if sha(path) != binding['sha256']:
        raise ValueError('Full60 source hash mismatch: ' + binding['file'])
    return path


def prepare(plan_path, plan_sha, budget_path=None, partition_id=None, review_path=None):
    plan_path = Path(plan_path).resolve()
    plan_path.relative_to(ROOT)
    if sha(plan_path) != plan_sha:
        raise ValueError('Full60 plan hash mismatch')
    plan = json.loads(plan_path.read_text())
    mode = plan.get('reasoning')
    if plan.get('schema') != 'qwen8-hosted-full60-v1' or mode not in ('off','on') or plan.get('phase') != 'full60' or plan.get('variant') != 'P0' or plan.get('model') != adapter.MODEL or plan.get('provider') != adapter.PROVIDER or plan.get('response_format') != 'json_object':
        raise ValueError('Full60 condition drift')
    if plan.get('reference_labels_read') is not False or plan.get('continue_on_invalid_output') is not True or plan.get('automatic_retries') is not False or plan.get('record_ids') != [f'DEV-{i:03}' for i in range(1,61)]:
        raise ValueError('Full60 protocol drift')
    paths = {key: source(binding) for key,binding in plan['sources'].items()}
    if paths['adapter'] != Path(adapter.__file__).resolve() or paths['partition_v2'] != Path(partitions_v2.__file__).resolve():
        raise ValueError('Loaded code differs from bound source')
    preview_manifest = json.loads(paths['preview_manifest'].read_text())
    configs = [x for x in preview_manifest['configs'] if x['file'] == paths['preview'].name]
    if len(configs) != 1 or any(configs[0].get(k) != v for k,v in (('reasoning',mode),('variant','P0'),('phase','full60'),('rows',60))) or configs[0]['file_sha256'] != sha(paths['preview']):
        raise ValueError('Frozen full60 preview differs')
    model, endpoint, _ = adapter.load_saved()
    schema = json.loads(adapter.SCHEMA_PATH.read_text())
    text, audit = adapter.instruction(schema, 'P0', mode)
    if audit != configs[0]['prompt_audit']:
        raise ValueError('Prompt audit differs')
    inputs = select_rows(adapter.read_rows(adapter.INPUT_PATH), 'development', 1)
    rows = [json.loads(line) for line in paths['preview'].read_text().splitlines() if line.strip()]
    if len(rows) != 60 or [x['id'] for x in rows] != plan['record_ids']:
        raise ValueError('Noncanonical full60 preview')
    for row, item in zip(rows, inputs):
        expected = adapter.payload(model, endpoint, item['feedback'], text, mode)
        if row['request'] != expected or row['request_sha256'] != adapter.sha(adapter.canonical(expected)) or row['input_sha256'] != adapter.sha(item['feedback'].encode()) or row.get('reference_labels_read') is not False or row.get('inference_performed') is not False:
            raise ValueError('Full60 request or input drift')
    smoke = [json.loads(line) for line in paths['smoke'].read_text().splitlines() if line.strip()]
    statuses = ['ok']*3 if mode == 'off' else ['invalid_output']*3
    if [r.get('id') for r in smoke] != plan['record_ids'][:3] or [r.get('status') for r in smoke] != statuses:
        raise ValueError('Inspected smoke outcome differs')
    smoke_preview = [json.loads(line) for line in paths['smoke_preview'].read_text().splitlines() if line.strip()]
    for i,r in enumerate(smoke):
        choices = r.get('raw_response',{}).get('choices')
        if not isinstance(choices,list) or len(choices)!=1:
            raise ValueError('Smoke choice control failure')
        choice=choices[0];message=choice.get('message') or {}
        if r.get('returned_model') != adapter.MODEL or r.get('returned_provider') != 'Alibaba' or r.get('finish_reason') != 'stop' or choice.get('error') or message.get('tool_calls') or message.get('function_call') or message.get('refusal') or r.get('cost_unknown') is not False or r.get('billing_ok') is not True or r.get('observed_cost_usd') is None:
            raise ValueError('Smoke control or billing failure')
        if r.get('request') != smoke_preview[i]['request'] or r.get('request_sha256') != smoke_preview[i]['request_sha256'] or r.get('request',{}).get('reasoning') != {'enabled':mode=='on'} or r['request'].get('response_format') != {'type':'json_object'} or r['request']['provider']['only'] != ['alibaba'] or r['request']['provider']['allow_fallbacks'] is not False:
            raise ValueError('Smoke request control drift')
        if mode == 'on' and (not isinstance(r.get('prediction'),str) or json.loads(message.get('content')) != r['prediction']):
            raise ValueError('Intrinsic invalid-output evidence differs')
    events = [json.loads(line) for line in paths['smoke_journal'].read_text().splitlines() if line.strip()]
    if not events or events[-1].get('event') != 'terminal' or events[-1].get('completed') is not True or events[-1].get('attempted_records') != 3:
        raise ValueError('Inspected smoke not terminal complete')
    inspection = json.loads(paths['inspection'].read_text())
    if inspection.get('schema') != 'qwen8-smoke-inspection-v1' or inspection.get('reasoning') != mode or inspection.get('smoke_sha256') != sha(paths['smoke']) or inspection.get('journal_sha256') != sha(paths['smoke_journal']) or inspection.get('statuses') != statuses or inspection.get('control_and_billing_passed') is not True:
        raise ValueError('Smoke inspection differs')
    reserve = reservation(endpoint, adapter.MAX_TOKENS, adapter.INPUT_CEILING, adapter.OUTPUT_CEILING)
    if plan.get('per_call_reserve_usd') != str(reserve) or plan.get('full60_bound_usd') != str(reserve*60) or reserve*60 > MAX_PARTITION or plan.get('proposed_partition_cap_usd') != str(MAX_PARTITION):
        raise ValueError('Full60 reserve bound differs')
    output = (ROOT / plan['output']).resolve()
    output.relative_to(ROOT)
    if output.exists() or Path(str(output)+'.attempts.jsonl').exists():
        raise FileExistsError('Full60 output already exists; no replay')
    if budget_path is None and partition_id is None and review_path is None:
        return plan, paths, None
    if not budget_path or not partition_id or not review_path:
        raise ValueError('Execution requires budget, partition and root review')
    budget_path=Path(budget_path).resolve();review_path=Path(review_path).resolve()
    budget_path.relative_to(ROOT);review_path.relative_to(ROOT)
    receipt=json.loads(review_path.read_text())
    if receipt.get('approved') is not True or receipt.get('full60_plan_sha256') != plan_sha or receipt.get('wrapper_sha256') != sha(__file__) or receipt.get('budget_manifest_sha256') != sha(budget_path) or receipt.get('partition_id') != partition_id:
        raise ValueError('Missing exact root review')
    if receipt.get('continue_on_invalid_output') is not True or receipt.get('smoke_inspection') != {'decision':'approved','reasoning':mode,'variant':'P0','evidence_path':str(paths['smoke']),'evidence_sha256':sha(paths['smoke'])}:
        raise ValueError('Root smoke inspection differs')
    entries=[e for e in json.loads(budget_path.read_text()).get('partitions',[]) if e.get('id')==partition_id]
    if len(entries)!=1 or any(entries[0].get(k)!=v for k,v in (('model',adapter.MODEL),('provider',adapter.PROVIDER),('reasoning',mode))) or not reserve*60 <= number(entries[0].get('cap_usd')) <= MAX_PARTITION:
        raise ValueError('Full60 budget partition differs')
    # The unchanged adapter checks this same receipt against its frozen preview.
    adapter.reviewed_preview(paths['preview'],review_path)
    return plan, paths, (budget_path,partition_id,review_path)


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
    p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--budget-partition-manifest');p.add_argument('--budget-partition-id');p.add_argument('--review')
    a=p.parse_args()
    if not a.execute and any((a.budget_partition_manifest,a.budget_partition_id,a.review)):
        raise ValueError('Budget arguments require --execute')
    plan,paths,budget=prepare(a.plan,a.sha256,a.budget_partition_manifest,a.budget_partition_id,a.review)
    if a.execute:execute(plan,paths,budget)
    else:print(json.dumps({'preflight':'ok','reasoning':plan['reasoning'],'ids':len(plan['record_ids']),'full60_bound_usd':plan['full60_bound_usd']}))

if __name__=='__main__':main()
