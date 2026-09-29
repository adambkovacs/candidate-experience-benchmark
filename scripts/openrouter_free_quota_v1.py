#!/usr/bin/env python3
"""Private, project-wide conservative admission for OpenRouter free-model calls.

This accounts only for calls made by this project. Other account activity is
unobservable; a provider 429 still stops the owning benchmark phase.
"""
import fcntl
import json
import os
from pathlib import Path
import time

QUOTA_DIR = Path('/private/tmp/candidate-benchmark-openrouter-free-quota-v1')
LEDGER = QUOTA_DIR / 'events.jsonl'
DAILY_LIMIT = 1000
MINUTE_LIMIT = 20
DAY_SECONDS = 86400
MINUTE_SECONDS = 60
START_INTERVAL_SECONDS = 3.1


def _private_file(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('Free quota directory must be private 0700')
    old_umask = os.umask(0o077)
    try:
        out = path.open('a+')
    finally:
        os.umask(old_umask)
    if path.stat().st_mode & 0o077:
        out.close()
        raise ValueError('Free quota ledger must be private 0600')
    fcntl.flock(out, fcntl.LOCK_EX)
    out.seek(0)
    events = [json.loads(line) for line in out if line.strip()]
    if any(e.get('event') not in ('stage_reserved', 'call_started') or
           not isinstance(e.get('at'), (float, int)) or not isinstance(e.get('stage'), str)
           for e in events):
        out.close()
        raise ValueError('Free quota ledger event invalid')
    return out, events


def _append(out, event):
    out.seek(0, os.SEEK_END)
    out.write(json.dumps(event, sort_keys=True) + '\n')
    out.flush(); os.fsync(out.fileno())


def admit_stage(stage, calls, path=LEDGER, now=None, provider_remaining=None):
    """Atomically reserve the *entire* 3- or 60-call phase for 24 hours."""
    if not isinstance(stage, str) or not stage or type(calls) is not int or calls not in (3, 60):
        raise ValueError('Exact free benchmark phase and count required')
    if type(provider_remaining) is not int or provider_remaining < 0:
        raise ValueError('Provider free-model remaining count required')
    now = time.time() if now is None else now
    out, events = _private_file(path)
    try:
        if any(e['stage'] == stage for e in events):
            raise ValueError('Free quota stage already reserved; no replay')
        if any(e['at'] > now for e in events):
            raise ValueError('Free quota ledger clock moved backward')
        active = [e for e in events if e['event'] == 'stage_reserved' and now - DAY_SECONDS < e['at'] <= now]
        if any(type(e.get('calls')) is not int or e['calls'] not in (3, 60) for e in active):
            raise ValueError('Invalid reserved stage count')
        outstanding = sum(e['calls'] - sum(x['event'] == 'call_started' and x['stage'] == e['stage']
                                           for x in events) for e in active)
        started_today = sum(e['event'] == 'call_started' and now - DAY_SECONDS < e['at'] <= now
                            for e in events)
        if outstanding < 0 or started_today + outstanding + calls > DAILY_LIMIT:
            raise ValueError('Known project free-call rolling-day capacity exhausted')
        recently_started = sum(e['event'] == 'call_started' and now - MINUTE_SECONDS < e['at'] <= now
                               for e in events)
        if outstanding < 0 or outstanding + recently_started + calls > provider_remaining:
            raise ValueError('Provider free-model daily capacity below reserved stage needs')
        _append(out, {'event': 'stage_reserved', 'stage': stage, 'calls': calls, 'at': now})
    finally:
        out.close()


def start_call(stage, record_id, path=LEDGER, clock=time.time, sleep=time.sleep):
    """Atomically mark a call before network; pace all free configurations together."""
    if not isinstance(stage, str) or not stage or not isinstance(record_id, str) or not record_id:
        raise ValueError('Exact stage and record required')
    while True:
        now = clock()
        out, events = _private_file(path)
        try:
            reservations = [e for e in events if e['event'] == 'stage_reserved' and e['stage'] == stage]
            if len(reservations) != 1 or not 0 <= now - reservations[0]['at'] < DAY_SECONDS:
                raise ValueError('Free quota stage reservation missing or expired')
            stage_calls = [e for e in events if e['event'] == 'call_started' and e['stage'] == stage]
            if len(stage_calls) >= reservations[0]['calls'] or any(e.get('record_id') == record_id for e in stage_calls):
                raise ValueError('Free quota call count exhausted or record replayed')
            recent = [e['at'] for e in events if e['event'] == 'call_started' and now - MINUTE_SECONDS < e['at'] <= now]
            recent.sort()
            wait = 0.0
            if recent:
                wait = max(wait, recent[-1] + START_INTERVAL_SECONDS - now)
            if len(recent) >= MINUTE_LIMIT:
                wait = max(wait, recent[-MINUTE_LIMIT] + MINUTE_SECONDS - now)
            if wait <= 0:
                _append(out, {'event': 'call_started', 'stage': stage, 'record_id': record_id, 'at': now})
                return
        finally:
            out.close()
        sleep(wait + .01)
