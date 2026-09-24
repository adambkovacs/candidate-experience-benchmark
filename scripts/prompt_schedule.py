"""Append-only prompt schedule journal. Admission validity belongs to controllers.

schedule_spec is a rooted {file,sha256} binding to JSON {order:[{id,conditions}]}.
Conditions alternate P1/P2 by configuration order. Each condition runs stages
smoke, inspected_admission, development, each with claim/finish. A stopped
stage terminates that condition; it never permits a retry. Completed smoke is
not inspected admission. Different configurations may progress concurrently.
The file lock covers replay and one durable append, not the inference duration.
Hash chains detect accidental alteration, not a malicious writer recomputing
an entire journal: this is an execution record, not a signed trust boundary.
"""
import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import prompt_execution_gates as g

STAGES=('smoke','inspected_admission','development')

def _stamp():return datetime.now(timezone.utc).isoformat()
def _digest(event):return g.canonical({k:v for k,v in event.items() if k!='event_sha256'})

def _schedule(spec,root):
    document=g.json_bound(spec,Path(root));order=document['order']
    ids=[r['id'] for r in order]
    if not ids or len(set(ids))!=len(ids) or any(not isinstance(i,str) or not i for i in ids):raise ValueError('Unique nonempty scheduled configurations required')
    for n,row in enumerate(order):
        expected=['P1','P2'] if n%2==0 else ['P2','P1']
        if set(row)!={'id','conditions'} or row['conditions']!=expected:raise ValueError('Frozen alternating schedule required')
    return {r['id']:r['conditions'] for r in order}


def _eligible(state,order,cid,condition,stage):
    if cid not in order or condition not in order[cid] or stage not in STAGES:raise ValueError('Unknown configuration/condition/stage')
    current=state.setdefault(cid,{})
    conditions=order[cid]
    if condition==conditions[1]:
        previous=current.get(conditions[0],{})
        if not any(x.get('status')=='stopped' for x in previous.values()) and previous.get('development',{}).get('status')!='completed':raise ValueError('Previous condition is not terminal')
    phases=current.setdefault(condition,{})
    if stage in phases:raise ValueError('Duplicate phase or unmatched start; no automatic retry')
    if any(x.get('status') in ('running','stopped') for x in phases.values()):raise ValueError('Condition has unmatched start or is stopped')
    for preceding in STAGES[:STAGES.index(stage)]:
        if phases.get(preceding,{}).get('status')!='completed':raise ValueError('Phase order requires completed prior stage')
    return phases


def _replay(events,spec,order,root):
    state={};attempts={};previous=None;previous_time=None
    for index,event in enumerate(events):
        if event.get('seq')!=index or event.get('previous_sha256')!=previous or event.get('event_sha256')!=_digest(event):raise ValueError('Journal sequence/hash chain mismatch')
        timestamp=g.stamp(event['utc'])
        if previous_time is not None and timestamp<previous_time:raise ValueError('Journal chronology reversed')
        previous_time=timestamp;previous=event['event_sha256']
        common={'seq','previous_sha256','event_sha256','utc','event'}
        if index==0:
            if set(event)!=common|{'schedule'} or event.get('event')!='initialized' or event['schedule']!=spec:raise ValueError('Immutable journal schedule binding mismatch')
            continue
        kind=event.get('event');aid=event.get('attempt_id')
        if not isinstance(aid,str) or not aid:raise ValueError('Attempt identity missing')
        if kind=='claimed':
            if set(event)!=common|{'attempt_id','configuration_id','condition','stage'} or aid in attempts:raise ValueError('Forged/duplicate claim')
            phases=_eligible(state,order,event['configuration_id'],event['condition'],event['stage'])
            record={'attempt_id':aid,'status':'running'};phases[event['stage']]=record;attempts[aid]=record
        elif kind=='finished':
            if set(event)!=common|{'attempt_id','status','evidence'} or aid not in attempts or attempts[aid]['status']!='running':raise ValueError('Unmatched or duplicate finish')
            if event['status'] not in ('completed','stopped') or not isinstance(event['evidence'],list) or not event['evidence']:raise ValueError('Terminal status and bound evidence required')
            for binding in event['evidence']:g.bound(binding,Path(root))
            attempts[aid]['status']=event['status']
        else:raise ValueError('Unknown journal event')
    return state,attempts


def _append(handle,events,event):
    now=_stamp()
    if events and g.stamp(now)<g.stamp(events[-1]['utc']):raise ValueError('System clock predates journal; reconcile before launch')
    event={'seq':len(events),'previous_sha256':events[-1]['event_sha256'] if events else None,'utc':now,**event}
    event['event_sha256']=_digest(event)
    raw=(json.dumps(event,sort_keys=True,separators=(',',':'))+'\n').encode()
    handle.seek(0,os.SEEK_END)
    if handle.write(raw)!=len(raw):raise OSError('Incomplete journal append')
    handle.flush();os.fsync(handle.fileno());events.append(event)
    return event


@contextmanager
def _locked(journal):
    path=Path(journal);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as handle:
        deadline=time.monotonic()+2.0
        while True:
            try:
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic()>=deadline:
                    raise RuntimeError('Schedule journal is locked by another operation') from None
                time.sleep(.025)
        try:
            handle.seek(0);raw=handle.read()
            if raw and not raw.endswith(b'\n'):raise ValueError('Incomplete journal tail; manual reconciliation required')
            events=[json.loads(line) for line in raw.splitlines()]
            yield handle,events
        finally:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def claim(schedule_spec,journal,configuration_id,condition,stage,root):
    order=_schedule(schedule_spec,root)
    with _locked(journal) as (handle,events):
        state,_=_replay(events,schedule_spec,order,root)
        _eligible(state,order,configuration_id,condition,stage)
        if not events:_append(handle,events,{'event':'initialized','schedule':schedule_spec})
        return _append(handle,events,{'event':'claimed','attempt_id':str(uuid.uuid4()),'configuration_id':configuration_id,'condition':condition,'stage':stage})


def finish(schedule_spec,journal,attempt_id,status,evidence,root):
    order=_schedule(schedule_spec,root)
    if status not in ('completed','stopped') or not isinstance(evidence,list) or not evidence:raise ValueError('Terminal status and nonempty bound evidence list required')
    for binding in evidence:g.bound(binding,Path(root))
    with _locked(journal) as (handle,events):
        _,attempts=_replay(events,schedule_spec,order,root)
        if attempt_id not in attempts or attempts[attempt_id]['status']!='running':raise ValueError('Unmatched or duplicate finish')
        return _append(handle,events,{'event':'finished','attempt_id':attempt_id,'status':status,'evidence':evidence})
