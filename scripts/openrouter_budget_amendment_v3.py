"""Prepare/review/activate the additional OpenRouter $10, without inference.

Activation appends to the same two locked inodes. A partial activation can only
finish the exact reviewed second append. New earmarked capacity requires both.
"""
import argparse
from datetime import datetime
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
import postapproval_authority_v2 as old
from development_benchmark import ROOT

SCHEMA = 'openrouter-additional-ten-amendment-v3'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
BASE = ROOT / 'results/route-audits/openrouter-additional-ten-amendment-v3-20261006'
SPEC = {'additional_openrouter_usd': '10.00', 'old_master_cap_usd': '12.38',
        'new_master_cap_usd': '22.38', 'original_shared_cap_usd': '10.00',
        'new_total_authority_cap_usd': '20.00', 'funding_scope': 'openrouter_only',
        'prior_0_55_request_superseded': True, 'prior_0_55_request_additive': False}
SOURCES = ('openrouter_budget_v4.py', 'paid_budget_partitions_v4.py',
           'postapproval_authority_v3.py', 'openrouter_budget_amendment_v3.py',
           'openrouter_budget_v3.py', 'paid_budget_partitions_v3.py', 'postapproval_authority_v2.py',
           'openrouter_paid_benchmark.py', 'development_benchmark.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return old.canonical(value) + b'\n'


def _master_state(raw):
    from openrouter_budget_v3 import BudgetLedger
    events, _ = old._lines(raw)
    budget = object.__new__(BudgetLedger)
    budget.events = events
    budget.cap_limit = Decimal('12.38')
    _, pending, blocked = budget.state()
    if budget.cap != Decimal('12.38') or pending or blocked or budget.closed:
        raise ValueError('Original master must be idle, unblocked and at $12.38')
    return budget


def prepare(proposal_path=BASE / 'proposal.json', *, master_path=MASTER, authority_path=AUTHORITY,
            baseline_head=old.ORIGINAL_HEAD, baseline_events=old.ORIGINAL_EVENTS):
    master_path, authority_path = Path(master_path).resolve(), Path(authority_path).resolve()
    with old._locked(authority_path) as auth:
        authority_raw = auth.read()
        authority_state, _, _ = old._scan(authority_raw, baseline_head=baseline_head,
                                         baseline_events=baseline_events)
        with master_path.open('rb') as master:
            fcntl.flock(master, fcntl.LOCK_EX | fcntl.LOCK_NB)
            master_raw = master.read()
            budget = _master_state(master_raw)
    value = {'schema': SCHEMA, 'status': 'offline_prepared_unapproved', 'inference_authorized': False,
             'authorization_provenance': 'Root handoff: user explicitly authorized an additional OpenRouter $10 on 2026-10-06',
             'spec': SPEC, 'baseline_head': baseline_head, 'baseline_events': baseline_events,
             'master': {'path': str(master_path), 'sha256': old.sha(master_raw), 'bytes': len(master_raw),
                        'accounted_usd': str(budget.accounted())},
             'authority': {'path': str(authority_path), 'sha256': authority_state.head_sha256,
                           'bytes': len(authority_raw), 'accounted_usd': str(authority_state.accounted_usd)},
             'sources': {name: {'path': str(Path(__file__).with_name(name)),
                                'sha256': sha(Path(__file__).with_name(name))} for name in SOURCES}}
    proposal_path = Path(proposal_path)
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    with proposal_path.open('x') as handle:
        json.dump(value, handle, indent=2); handle.write('\n')
    candidate = proposal_path.with_name('root-review-candidate.json')
    with candidate.open('x') as handle:
        json.dump({'schema': SCHEMA + '-root-review', 'approved': False, 'independent_review': False,
                   'authorized_by_root': False, 'reviewer': None, 'reviewed_utc': None,
                   'proposal_path': str(proposal_path.resolve()), 'proposal_sha256': sha(proposal_path)}, handle, indent=2)
        handle.write('\n')
    return value


def review_value(review_path):
    review = json.loads(Path(review_path).read_text())
    if (review.get('schema') != SCHEMA + '-root-review' or review.get('approved') is not True or
            review.get('independent_review') is not True or review.get('authorized_by_root') is not True or
            review.get('reviewer') != 'root'):
        raise ValueError('Independent root amendment approval required')
    datetime.fromisoformat(review['reviewed_utc'])
    if sha(review['proposal_path']) != review.get('proposal_sha256'):
        raise ValueError('Reviewed proposal changed')
    proposal = json.loads(Path(review['proposal_path']).read_text())
    if proposal.get('schema') != SCHEMA or proposal.get('spec') != SPEC:
        raise ValueError('Only the exact additional OpenRouter $10 is authorized')
    for name in SOURCES:
        binding = proposal['sources'][name]
        if Path(binding['path']).resolve() != Path(__file__).with_name(name).resolve() or sha(binding['path']) != binding['sha256']:
            raise ValueError('Reviewed amendment source changed')
    return proposal, review


def event_value(kind, review_path):
    _, review = review_value(review_path)
    common = {'amendment_schema': SCHEMA, 'proposal_path': review['proposal_path'],
              'proposal_sha256': review['proposal_sha256'], 'review_path': str(Path(review_path).resolve()),
              'review_sha256': sha(review_path)}
    if kind == 'master':
        return {'event': 'cap_amendment', 'previous_cap_usd': '12.38', 'cap_usd': '22.38',
                'reason': 'User authorized additional OpenRouter $10; earlier $0.55 request superseded', **common}
    if kind == 'authority':
        return {'event': 'authority_amendment', 'shared_cap_usd': '10.00',
                'openrouter_additional_cap_usd': '10.00', 'total_cap_usd': '20.00', **common}
    raise ValueError('Unknown amendment ledger')


def validate_event(event, kind):
    proposal, _ = review_value(event['review_path'])
    if event != event_value(kind, event['review_path']):
        raise ValueError('Amendment event differs from reviewed exact caps')
    return proposal


def counterpart_committed(proposal, review_path, kind):
    target = proposal[kind]
    raw = Path(target['path']).read_bytes()
    if old.sha(raw[:target['bytes']]) != target['sha256']:
        raise ValueError('Original ledger prefix changed')
    tail = raw[target['bytes']:]
    old._lines(raw)
    return tail.startswith(canonical(event_value(kind, review_path)))


def activate(review_path):
    proposal, _ = review_value(review_path)
    # Same lock order as authority admission. No inference or allocation here.
    with old._locked(proposal['authority']['path']) as authority:
        authority_raw = authority.read()
        authority_event = canonical(event_value('authority', review_path))
        a = proposal['authority']
        if authority_raw != authority_raw[:a['bytes']] or old.sha(authority_raw) != a['sha256']:
            if old.sha(authority_raw[:a['bytes']]) != a['sha256'] or authority_raw[a['bytes']:] != authority_event:
                raise ValueError('Authority head changed beyond recoverable amendment')
        else:
            old._scan(authority_raw, baseline_head=proposal['baseline_head'], baseline_events=proposal['baseline_events'])
        with Path(proposal['master']['path']).open('r+b') as master:
            fcntl.flock(master, fcntl.LOCK_EX | fcntl.LOCK_NB)
            master_raw = master.read(); m = proposal['master']
            master_event = canonical(event_value('master', review_path))
            master_done = old.sha(master_raw[:m['bytes']]) == m['sha256'] and master_raw[m['bytes']:] == master_event
            if not master_done and old.sha(master_raw) != m['sha256']:
                raise ValueError('Master head changed')
            authority_done = authority_raw[a['bytes']:] == authority_event
            if authority_done and master_done:
                raise ValueError('Amendment already complete')
            if not master_done:
                _master_state(master_raw)
            if not authority_done:
                old._append(authority, event_value('authority', review_path))
            if not master_done:
                old._append(master, event_value('master', review_path))
    return {'schema': SCHEMA + '-activation', 'master_cap_usd': '22.38',
            'shared_cap_usd': '10.00', 'openrouter_additional_cap_usd': '10.00',
            'master_sha256': sha(proposal['master']['path']), 'authority_sha256': sha(proposal['authority']['path'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'activate'))
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(json.dumps(prepare()))
    elif args.review:
        print(json.dumps(activate(args.review)))
    else:
        parser.error('activate requires --review')


if __name__ == '__main__':
    main()
