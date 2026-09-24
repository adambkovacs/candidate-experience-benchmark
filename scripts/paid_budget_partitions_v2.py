"""Explicit offline allocation/reconciliation of bounded paid-run budgets.

Allocation encumbers master capacity; it is not observed spending. Workers must
use hash-bound manifests. Master and child locks prevent reopening reconciled
partitions or reconciling a live run. No inference is performed here.
"""
import hashlib,json,time
from decimal import Decimal
from pathlib import Path
from openrouter_paid_benchmark import number,durable
from openrouter_budget_v2 import BudgetLedger

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def allocate(master_path,manifest_path,specs):
    master_path=Path(master_path).resolve();manifest_path=Path(manifest_path).resolve()
    if manifest_path==master_path or manifest_path.exists() or not specs:raise ValueError('Require new manifest and nonempty partition list')
    ids=[s['id'] for s in specs]
    if len(set(ids))!=len(ids) or any(not isinstance(i,str) or not i or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in i) for i in ids):raise ValueError('Invalid or duplicate partition IDs')
    entries=[]
    for s in specs:
        cap=number(s['cap_usd']);child=manifest_path.parent/(manifest_path.stem+'-'+s['id']+'.jsonl')
        if cap<=0 or child.exists() or child==master_path:raise ValueError('Invalid cap or reused child path')
        if any(not isinstance(s.get(k),str) or not s[k] for k in ('model','provider','reasoning')):raise ValueError('Require exact configuration')
        entries.append({**s,'cap_usd':str(cap),'child_ledger':str(child)})
    master=BudgetLedger(master_path)
    try:
        _,pending,blocked=master.state()
        if pending or blocked or master.closed:raise ValueError('Master has unresolved billing, is blocked or is closed')
        # Existing active allocations remain fully encumbered. Distinct additions
        # may use only unallocated master capacity while child workers hold locks.
        used_manifests={p['manifest_path'] for p in master.partitions.values()}
        used_children={p['child_ledger'] for p in master.partitions.values()}
        if str(manifest_path) in used_manifests|used_children or manifest_path.exists():raise ValueError('Manifest path cannot be reused')
        if any(e['child_ledger'] in used_children|used_manifests or Path(e['child_ledger']).exists() for e in entries):raise ValueError('Child path cannot be reused')
        if set(ids)&set(master.partitions):raise ValueError('Partition IDs cannot be reused')
        if master.accounted()+sum(number(e['cap_usd']) for e in entries)>master.cap:raise ValueError('Partitions exceed master remaining capacity')
        manifest={'version':'paid-partitions-v1','master_ledger':str(master_path),'partitions':entries}
        with manifest_path.open('x') as f:durable(f,manifest)
        digest=sha(manifest_path)
        for e in entries:
            master.append({'event':'budget_partition','partition_id':e['id'],'allocated_usd':e['cap_usd'],'manifest_path':str(manifest_path),'manifest_sha256':digest,'child_ledger':e['child_ledger'],'model':e['model'],'provider':e['provider'],'reasoning':e['reasoning']})
            with Path(e['child_ledger']).open('x') as f:durable(f,{'event':'budget','cap_usd':e['cap_usd']})
        master.state();return manifest
    finally:master.close()

def bound_entry(master,manifest_path,pid):
    path=Path(manifest_path).resolve();manifest=json.loads(path.read_text());master.state();part=master.partitions.get(pid)
    if not part or not part['active'] or part['manifest_path']!=str(path) or part['manifest_sha256']!=sha(path):raise ValueError('Inactive or mismatched partition manifest')
    if manifest.get('version')!='paid-partitions-v1' or manifest['master_ledger']!=str(Path(master.file.name).resolve()):raise ValueError('Master binding mismatch')
    entries=[x for x in manifest['partitions'] if x['id']==pid]
    if len(entries)!=1:raise ValueError('Missing unique partition')
    e=entries[0]
    if e['child_ledger']!=part['child_ledger'] or number(e['cap_usd'])!=number(part['allocated_usd']) or any(e[k]!=part[k] for k in ('model','provider','reasoning')):raise ValueError('Partition binding differs from master')
    return e

def require_child_ledger(entry):
    path=Path(entry['child_ledger'])
    if not path.is_file() or path.stat().st_size==0:
        raise ValueError('Missing or empty child ledger; refusing to recreate budget')

def open_partition(master_path,manifest_path,pid,model,provider,reasoning):
    # Bounded startup-only lock contention retry; no model call has started.
    for retry in range(30):
        try:master=BudgetLedger(master_path);break
        except BlockingIOError:
            if retry==29:raise
            time.sleep(.1)
    try:
        e=bound_entry(master,manifest_path,pid)
        if (e['model'],e['provider'],e['reasoning'])!=(model,provider,reasoning):raise ValueError('Worker configuration is outside partition')
        require_child_ledger(e)
        child=BudgetLedger(e['child_ledger'],cap_limit=number(e['cap_usd']))
        if child.closed:child.close();raise ValueError('Partition is sealed')
        child.master_cap=master.cap
        return child
    finally:master.close()

def reconcile_partition(master_path,manifest_path,pid):
    master=BudgetLedger(master_path);child=None
    try:
        e=bound_entry(master,manifest_path,pid);require_child_ledger(e);child=BudgetLedger(e['child_ledger'],cap_limit=number(e['cap_usd']))
        _,pending,blocked=child.state()
        if pending or blocked or child.partitions:raise ValueError('Child has unresolved billing or nested partitions')
        known=sum((number(x['usd']) for x in child.events if x['event']=='settle'),Decimal(0))
        unknown=sum((number(x['usd']) for x in child.events if x['event']=='unknown_cost_accounted_as_upper_bound'),Decimal(0))
        if known+unknown!=child.accounted() or known+unknown>number(e['cap_usd']):raise ValueError('Child accounting mismatch')
        if not child.closed:child.append({'event':'partition_closed','reason':'Explicit terminal reconciliation; no further requests permitted'})
        event={'event':'partition_reconciled','partition_id':pid,'known_actual_usd':str(known),'unknown_upper_bound_usd':str(unknown),'unused_allocation_released_usd':str(number(e['cap_usd'])-known-unknown),'child_ledger':e['child_ledger'],'child_sha256':sha(e['child_ledger'])}
        master.append(event);master.state();return event
    finally:
        if child:child.close()
        master.close()
