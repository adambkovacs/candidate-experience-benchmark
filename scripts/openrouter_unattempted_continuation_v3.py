#!/usr/bin/env python3
"""Offline v3 lineage extension for the three closed HTTP-429 suffixes."""
import argparse
import datetime
import fcntl
import hashlib
import json
from pathlib import Path

import openrouter_unattempted_continuation as base

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'results/hosted-unattempted-continuation-v3'
INVENTORY=DEST/'inventory.json'
CONTRACT='hosted-unattempted-continuation-v3'
TARGETS={('qwen27-low-hosted-addendum-v1','P1'),('qwen27-low-hosted-addendum-v1','P2'),
         ('openrouter-paid-gemma4-26b-a4b-on','P2')}


def configure():
    base.DEST=DEST;base.INVENTORY=INVENTORY;base.CONTRACT=CONTRACT
    base.read_inventory=read_inventory

def read_inventory():
    inv=json.loads(INVENTORY.read_text())
    if inv['schema']!='hosted-never-sent-inventory-v2' or len(inv['candidate_conditions'])!=3:
        raise ValueError('V3 inventory contract differs')
    if {(x['configuration_id'],x['condition']) for x in inv['candidate_conditions']}!=TARGETS:
        raise ValueError('V3 inventory target set differs')
    for item in inv['source_bindings']:
        if base.digest((ROOT/item['path']).read_bytes())!=item['sha256']:
            raise ValueError('V3 inventory source differs: '+item['path'])
    return inv

def validate(manifest,frozen=True):
    configure()
    if manifest['contract']!=CONTRACT:raise ValueError('V3 contract differs')
    if base.bound(manifest['extension_controller'])!=Path(__file__).read_bytes():
        raise ValueError('V3 wrapper source differs')
    prior=base.json_bound(manifest['lineage_v2_manifest'])
    report=base.json_bound(manifest['lineage_v2_reconciliation'])
    if prior['contract']!='hosted-unattempted-continuation-v2' or report['contract']!='hosted-unattempted-continuation-reconciliation-v1':
        raise ValueError('V2 lineage contract differs')
    if report['status']!='partial_stopped' or not report['partition_reconciled_event']:
        raise ValueError('V2 predecessor is not terminal and sealed')
    if manifest['histories'][-1]['output']!=report['new_output'] or manifest['histories'][-1]['journal']!=report['new_journal']:
        raise ValueError('V2 output/journal lineage differs')
    if manifest['remaining_ids']!=report['remaining_never_sent_ids']:
        raise ValueError('V3 suffix differs from sealed V2 report')
    return base.validate(manifest,frozen)

def build(args):
    configure();inv=read_inventory();key=(args.inventory_configuration_id,args.condition)
    if key not in TARGETS:raise ValueError('Outside three V3 targets')
    candidate=next(x for x in inv['candidate_conditions'] if (x['configuration_id'],x['condition'])==key)
    v2folder=ROOT/'results/hosted-unattempted-continuation-v2'/(key[0]+'-'+key[1].lower())
    predecessor=json.loads((v2folder/'frozen-manifest.json').read_text())
    report=json.loads((v2folder/'reconciliation-v1.json').read_text())
    assert predecessor['inventory_configuration_id']==key[0] and predecessor['condition']==key[1]
    source=ROOT/predecessor['original_manifest']['file'];original=json.loads(source.read_text())
    cfg=next(x for x in original['configurations'] if x['id']==predecessor['configuration_id'])
    histories=predecessor['histories']+[{'kind':'continuation','output':base.binding(v2folder/'development.jsonl'),
                                          'journal':base.binding(v2folder/'attempts.jsonl')}]
    observed=[r['id'] for h in histories for r in base.lines(h['output'])]
    directory=DEST/(key[0]+'-'+key[1].lower());directory.mkdir(parents=True,exist_ok=False)
    ledger_paths=set()
    for history in histories:
        for row in base.lines(history['output']):
            if row.get('budget_ledger'):ledger_paths.add((ROOT/row['budget_ledger']).resolve())
    receipt=json.loads((v2folder/'root-review.json').read_text())
    partition=json.loads((ROOT/receipt['budget_partition_manifest']['file']).read_text())
    ledger_paths.add(Path(next(x for x in partition['partitions'] if x['id']==receipt['budget_partition_id'])['child_ledger']).resolve())
    ledgers=[]
    for n,path in enumerate(sorted(ledger_paths)):
        with path.open('rb') as source_ledger:
            fcntl.flock(source_ledger,fcntl.LOCK_SH);snapshot=source_ledger.read();fcntl.flock(source_ledger,fcntl.LOCK_UN)
        snap=directory/f'historical-ledger-{n}.jsonl';snap.write_bytes(snapshot);ledgers.append(base.binding(snap))
    observation=cfg['conditions'][key[1]]['observational_evidence']
    m={'contract':CONTRACT,'status':'DRAFT','reference_labels_read':False,
       'extension_controller':base.binding(__file__),'lineage_v2_manifest':base.binding(v2folder/'frozen-manifest.json'),
       'lineage_v2_reconciliation':base.binding(v2folder/'reconciliation-v1.json'),
       'inventory':base.binding(INVENTORY),'inventory_configuration_id':key[0],
       'configuration_id':predecessor['configuration_id'],'condition':key[1],
       'controller':base.binding(ROOT/'scripts/openrouter_unattempted_continuation.py'),
       'dependencies':predecessor['dependencies'],'original_manifest':predecessor['original_manifest'],
       'controls':predecessor['controls'],'parent_baseline_id':predecessor['parent_baseline_id'],
       'observational_evidence':observation,'instruction':predecessor['instruction'],
       'inputs':predecessor['inputs'],'schema':predecessor['schema'],
       'source_evidence':[{'file':x['path'],'sha256':x['sha256']} for x in candidate['evidence']],
       'histories':histories,'historical_ledgers':ledgers,
       'smoke':predecessor['smoke'],'smoke_supplement':predecessor['smoke_supplement'],
       'endpoint_facts':predecessor['endpoint_facts'],'catalog_facts':predecessor['catalog_facts'],
       'remaining_ids':candidate['candidate_never_sent_ids'],
       'request_bindings':[x['client_request'] for x in json.loads((ROOT/observation['file']).read_text())['requests'][3+len(observed):]],
       'output':str((directory/'development.jsonl').relative_to(ROOT)),
       'journal':str((directory/'attempts.jsonl').relative_to(ROOT)),
       'policy':predecessor['policy']}
    validate(m,False)
    with (directory/'draft-manifest.json').open('x') as out:json.dump(m,out,indent=2);out.write('\n')
    print(directory/'draft-manifest.json',len(m['remaining_ids']))

def execute(args):
    configure()
    raw=Path(args.manifest).read_bytes()
    if base.digest(raw)!=args.sha256:raise ValueError('V3 manifest hash differs')
    validate(json.loads(raw))
    return base.execute(args)

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
        if base.digest(raw)!=args.sha256:raise ValueError('V3 manifest hash differs')
        validate(json.loads(raw));print('validated')
if __name__=='__main__':main()
