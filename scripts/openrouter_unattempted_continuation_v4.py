#!/usr/bin/env python3
"""Thin offline lineage extension for Qwen27 low P2 DEV-056..060 only."""
import argparse,hashlib,json
from pathlib import Path
import openrouter_unattempted_continuation as base

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'results/hosted-unattempted-continuation-v4'
INVENTORY=DEST/'inventory.json'
CONTRACT='hosted-unattempted-continuation-v4'
KEY=('qwen27-low-hosted-addendum-v1','P2')

def read_inventory():
    inv=json.loads(INVENTORY.read_text())
    if inv['schema']!='hosted-never-sent-inventory-v3' or len(inv['candidate_conditions'])!=1:
        raise ValueError('V4 inventory contract differs')
    c=inv['candidate_conditions'][0]
    if (c['configuration_id'],c['condition'])!=KEY or c['candidate_never_sent_ids']!=base.ids(56):
        raise ValueError('V4 candidate differs from exact five')
    for x in inv['source_bindings']:
        if base.digest((ROOT/x['path']).read_bytes())!=x['sha256']:
            raise ValueError('V4 source differs: '+x['path'])
    return inv

def configure():
    base.DEST=DEST;base.INVENTORY=INVENTORY;base.CONTRACT=CONTRACT;base.read_inventory=read_inventory

def validate(m,frozen=True):
    configure()
    if m['contract']!=CONTRACT or base.bound(m['extension_controller'])!=Path(__file__).read_bytes():
        raise ValueError('V4 wrapper differs')
    prior=base.json_bound(m['lineage_v3_manifest']);report=base.json_bound(m['lineage_v3_reconciliation'])
    if prior['contract']!='hosted-unattempted-continuation-v3' or report['contract']!='hosted-unattempted-continuation-v3-reconciliation-v1':
        raise ValueError('V3 lineage contract differs')
    base.bound(prior['extension_controller'])
    if report['status']!='partial_stopped' or report['terminal_status']!='stopped' or not report['partition_reconciled_event']:
        raise ValueError('V3 predecessor not sealed and stopped')
    if m['histories'][-1]['output']!=report['new_output'] or m['histories'][-1]['journal']!=report['new_journal']:
        raise ValueError('V3 output/journal lineage differs')
    if m['remaining_ids']!=report['remaining_never_sent_ids'] or m['remaining_ids']!=base.ids(56):
        raise ValueError('V4 suffix differs from sealed V3 report')
    last=base.lines(m['histories'][-1]['output'])[-1]
    if last['id']!='DEV-055' or last['status']!='service_error' or not last['cost_unknown']:
        raise ValueError('DEV-055 attempted timeout must remain excluded')
    return base.validate(m,frozen)

def build():
    configure();candidate=read_inventory()['candidate_conditions'][0]
    previous=ROOT/'results/hosted-unattempted-continuation-v3/qwen27-low-hosted-addendum-v1-p2'
    prior=json.loads((previous/'frozen-manifest.json').read_text())
    report=json.loads((previous/'reconciliation-v1.json').read_text())
    directory=DEST/'qwen27-low-hosted-addendum-v1-p2';directory.mkdir(parents=True,exist_ok=False)
    histories=prior['histories']+[{'kind':'continuation','output':base.binding(previous/'development.jsonl'),
                                   'journal':base.binding(previous/'attempts.jsonl')}]
    receipt=json.loads((previous/'root-review.json').read_text())
    partition=json.loads((ROOT/receipt['budget_partition_manifest']['file']).read_text())
    child=Path(next(x for x in partition['partitions'] if x['id']==receipt['budget_partition_id'])['child_ledger'])
    observed=[r['id'] for h in histories for r in base.lines(h['output'])]
    observation=base.json_bound(prior['observational_evidence'])
    m={**prior,'contract':CONTRACT,'status':'DRAFT','inventory':base.binding(INVENTORY),
       'extension_controller':base.binding(__file__),
       'lineage_v3_manifest':base.binding(previous/'frozen-manifest.json'),
       'lineage_v3_reconciliation':base.binding(previous/'reconciliation-v1.json'),
       'source_evidence':[{'file':x['path'],'sha256':x['sha256']} for x in candidate['evidence']],
       'histories':histories,'historical_ledgers':prior['historical_ledgers']+[base.binding(child)],
       'remaining_ids':candidate['candidate_never_sent_ids'],
       'request_bindings':[x['client_request'] for x in observation['requests'][3+len(observed):]],
       'output':str((directory/'development.jsonl').relative_to(ROOT)),
       'journal':str((directory/'attempts.jsonl').relative_to(ROOT))}
    m.pop('lineage_v2_manifest',None);m.pop('lineage_v2_reconciliation',None);m.pop('frozen_utc',None)
    validate(m,False)
    with (directory/'draft-manifest.json').open('x') as f:json.dump(m,f,indent=2);f.write('\n')
    print(directory/'draft-manifest.json',len(m['remaining_ids']))

def execute(args):
    configure();raw=Path(args.manifest).read_bytes()
    if base.digest(raw)!=args.sha256:raise ValueError('V4 manifest hash differs')
    validate(json.loads(raw));return base.execute(args)

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('build')
    v=sub.add_parser('validate');v.add_argument('--manifest',required=True);v.add_argument('--sha256',required=True)
    e=sub.add_parser('execute');e.add_argument('--manifest',required=True);e.add_argument('--sha256',required=True);e.add_argument('--review',required=True);e.add_argument('--env-file')
    a=p.parse_args()
    if a.command=='build':build()
    elif a.command=='execute':execute(a)
    else:
        raw=Path(a.manifest).read_bytes()
        if base.digest(raw)!=a.sha256:raise ValueError('V4 manifest hash differs')
        validate(json.loads(raw));print('validated')
if __name__=='__main__':main()
