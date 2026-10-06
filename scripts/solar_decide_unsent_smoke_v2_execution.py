#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for the two never-sent Solar P0 smoke IDs."""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
from jev_benchmark import parse_response
from openrouter_paid_benchmark import durable, load_key
import openrouter_decision_smoke as native
import openrouter_authority_release_v4 as authority
import paid_budget_partitions_v4 as partitions
import solar_decide_offline_plan as solar
import solar_decide_risk_hold_v1 as risk
import solar_decide_smoke_v1 as old
import solar_decide_unsent_smoke_v2 as proposal

BASE = proposal.BASE / 'execution-adapter-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
CHILD = BASE / 'budget-solar-decide-upstage-p0-unsent-smoke-v2.jsonl'
STAGE_REVIEW = BASE / 'smoke.root-review.json'
PARTITION_ID = 'solar-decide-upstage-p0-unsent-smoke-v2'
CAP = Decimal('0.21')
BOUND = proposal.BOUND
REASONING = 'native-decisions-P0-exact-unsent-two'
SCHEMA = 'solar-decide-exact-unsent-p0-smoke-v2-execution'
SOURCES = ('scripts/solar_decide_unsent_smoke_v2_execution.py',
           'tests/test_solar_decide_unsent_smoke_v2_execution.py',
           'scripts/solar_decide_unsent_smoke_v2.py',
           'scripts/solar_decide_risk_hold_v1.py',
           'scripts/solar_decide_smoke_v1.py',
           'scripts/solar_decide_offline_plan.py',
           'scripts/jev_benchmark.py',
           'scripts/openrouter_decision_smoke.py',
           'scripts/openrouter_paid_benchmark.py',
           'scripts/openrouter_benchmark.py',
           'scripts/development_benchmark.py',
           'scripts/openrouter_authority_release_v4.py',
           'scripts/openrouter_budget_amendment_v3.py',
           'scripts/postapproval_authority_v3.py',
           'scripts/postapproval_authority_v2.py',
           'scripts/paid_budget_partitions_v4.py',
           'scripts/paid_budget_partitions_v3.py',
           'scripts/openrouter_budget_v4.py',
           'scripts/openrouter_budget_v3.py',
           'scripts/openrouter_budget_v2.py',
           'results/solar-decide-unsent-smoke-v2/manifest.json',
           'results/solar-decide-risk-hold-v1/proposal.json',
           'results/solar-decide-risk-hold-v1/root-review.json',
           'results/solar-decide-risk-hold-v1/budget.json',
           'results/solar-decide-risk-hold-v1/risk-hold.claim.json',
           'results/solar-decide-native-smoke-v1/terminal-public.json',
           'results/solar-decide-native-smoke-v1/budget-reconciliation.json')


def sha(path):
    return native.sha(Path(path).read_bytes())


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')


def jsonl(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete Solar JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def risk_archived():
    claim = json.loads(risk.CLAIM.read_text())
    if (claim.get('status') != 'active_risk_hold_no_inference' or
            claim.get('proposal_sha256') != risk.verify() or
            claim.get('review_sha256') != sha(risk.REVIEW) or
            claim.get('budget_manifest_sha256') != sha(risk.BUDGET) or
            claim.get('historical_child_sha256') !=
            sha(risk.OLD / 'budget-manifest-solar-decide-upstage-p0-smoke-v1.jsonl') or
            claim.get('usd') != str(risk.CAP) or claim.get('new_requests') != 0 or
            claim.get('known_charge_usd') != '0'):
        raise ValueError('Reviewed Solar risk hold archive differs')
    return claim


def manifest_value():
    plan_sha = proposal.verify()
    risk_archived()
    if BOUND != Decimal('0.10485760') or CAP < 2*BOUND:
        raise ValueError('Solar two-request reserve or child cap differs')
    return {'schema': SCHEMA + '-manifest', 'status': 'offline_unadmitted',
        'plan_sha256': plan_sha, 'request_ids': ['DEV-002','DEV-003'],
        'old_unknown_id_no_replay': 'DEV-001', 'model': solar.MODEL,
        'provider': solar.PROVIDER, 'provider_tag': 'upstage',
        'expected_returned_model': solar.VERSION,
        'partition_id': PARTITION_ID, 'proposed_child_cap_usd': str(CAP),
        'per_request_reserve_usd': str(BOUND),
        'two_request_reserve_usd': str(2*BOUND),
        'risk_partition_id': risk.PARTITION_ID,
        'risk_hold_usd': str(risk.CAP),
        'funding_pool': 'openrouter_additional',
        'reference_labels_sent': False,
        'provider_failure_policy': 'Stop at first provider/unknown/intrinsic failure; no retry or model substitution.',
        'source_sha256': {name: sha(ROOT / name) for name in SOURCES}}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__),
        'partition_id': PARTITION_ID, 'proposed_child_cap_usd': str(CAP),
        'request_ids': ['DEV-002','DEV-003']}


def prepare():
    if BASE.exists():
        raise FileExistsError('Solar unsent executor already prepared')
    value = manifest_value()
    BASE.mkdir(parents=True)
    with MANIFEST.open('x') as out:
        json.dump(value,out,indent=2,sort_keys=True);out.write('\n')
    with REVIEW.open('x') as out:
        json.dump(review_template(),out,indent=2,sort_keys=True);out.write('\n')
    return sha(MANIFEST)


def verify():
    if json.loads(MANIFEST.read_text()) != manifest_value():
        raise ValueError('Solar unsent execution manifest or source changed')
    return sha(MANIFEST)


def require_review():
    expected = review_template()
    expected.update(approved=True,independent_review=True,
                    authorized_by_root=True,reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent Solar two-request execution review missing')


def exact_budget():
    entry = {'id': PARTITION_ID, 'cap_usd': str(CAP),
             'child_ledger': str(CHILD), 'model': solar.MODEL,
             'provider': solar.PROVIDER, 'reasoning': REASONING}
    expected = {'version': 'paid-partitions-v1', 'master_ledger': str(risk.MASTER),
                'partitions': [entry]}
    if json.loads(BUDGET.read_text()) != expected:
        raise ValueError('Exact Solar successor child differs')
    return entry


def hold_source():
    return native.sha(native.canonical({'schema': SCHEMA + '-hold',
        'manifest_sha256': sha(MANIFEST), 'budget_manifest_path': str(BUDGET),
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'risk_claim_sha256': sha(risk.CLAIM)}))


def verify_holds():
    risk_archived(); risk.budget_entry()
    with authority.old._locked(risk.AUTHORITY) as handle:
        snapshot, holds, released = authority._scan(handle.read())
    expected = ((risk.PARTITION_ID, risk.CAP, risk.hold_source(), risk.BUDGET),
                (PARTITION_ID, CAP, hold_source(), BUDGET))
    for partition_id, cap, source, budget in expected:
        hold = holds.get(partition_id)
        if (partition_id in released or not hold or hold.get('usd') != str(cap) or
                hold.get('source_sha256') != source or
                hold.get('funding_pool') != 'openrouter_additional' or
                hold.get('budget_manifest_path') != str(budget) or
                hold.get('budget_manifest_sha256') != sha(budget) or
                hold.get('partition_id') != partition_id or
                hold.get('master_path') != str(risk.MASTER)):
            raise ValueError('Exact active Solar v4 hold missing: ' + partition_id)
    return snapshot


def stage_template():
    verify(); require_review(); exact_budget()
    snapshot = verify_holds()
    return {'schema': SCHEMA + '-stage-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__), 'plan_sha256': sha(proposal.PLAN),
        'budget_manifest_sha256': sha(BUDGET),
        'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
        'per_request_reserve_usd': str(BOUND),
        'risk_claim_sha256': sha(risk.CLAIM),
        'authority_head_sha256': snapshot.head_sha256,
        'request_ids': ['DEV-002','DEV-003']}


def require_stage_review():
    expected = stage_template()
    expected.update(approved=True,independent_review=True,
                    authorized_by_root=True,reviewer='root')
    if json.loads(STAGE_REVIEW.read_text()) != expected:
        raise ValueError('Solar exact two-request root stage review missing')


def live_route(fetch=old.fetch_endpoint):
    route_raw, route = fetch()
    selected = solar.validate_catalog(route)['upstage']
    saved = json.loads((proposal.OLD / 'manifest.json').read_text())['requests'][1]['payload']
    if (saved['provider'] != {'only':['upstage'],'allow_fallbacks':False,
            'max_price':{'prompt':0.05,'completion':0,'request':0,'image':0}} or
            selected['tag'] != 'upstage'):
        raise ValueError('Solar exact provider route differs')
    return route_raw, route


def validate_returned(body):
    if not isinstance(body,dict) or body.get('provider') != solar.PROVIDER:
        raise ValueError('Solar returned provider differs')
    prediction = parse_response(body, solar.VERSION)
    usage = body.get('usage')
    if (not isinstance(usage,dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= 4*solar.CONTEXT or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Solar four-question usage differs')
    actual = native.response_cost(body)
    if actual is None or actual > Decimal(usage['input_tokens']) * solar.PROMPT_RATE:
        raise ValueError('Solar reported cost exceeds pinned input price')
    return prediction,actual


def execute(*, fetch=old.fetch_endpoint, send=old.post, env_file=None):
    require_stage_review()
    paths = {name: BASE / ('smoke.' + name) for name in
             ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Solar exact-unsent smoke already claimed; no replay')
    live_route(fetch)
    ledger = partitions.open_partition(risk.MASTER,BUDGET,PARTITION_ID,
                                        solar.MODEL,solar.PROVIDER,REASONING)
    try:
        _,pending,blocked = ledger.state()
        if (ledger.cap != CAP or ledger.master_cap != Decimal('22.38') or
                pending or blocked or ledger.closed or ledger.accounted()+2*BOUND>CAP):
            raise ValueError('Solar successor child lacks full two-request reserve')
        token = load_key(env_file)
        plan = json.loads(proposal.PLAN.read_text())
        with paths['claim.json'].open('x') as out:
            durable(out,{'schema':SCHEMA+'-claim','manifest_sha256':sha(MANIFEST),
                'root_review_sha256':sha(STAGE_REVIEW),'request_ids':['DEV-002','DEV-003'],
                'reference_labels_sent':False,'utc':utc()})
        with paths['journal.jsonl'].open('x') as journal, paths['raw.jsonl'].open('x') as raw, \
             paths['attempts.jsonl'].open('x') as attempts, paths['parsed.jsonl'].open('x') as parsed:
            durable(journal,{'event':'stage_started','utc':utc(),'manifest_sha256':sha(MANIFEST)})
            for item in plan['requests']:
                rid = item['id']
                # The child lock is held here. Re-reading v4 authority could
                # take the master lock and deadlock with concurrent reconciliation.
                # Both holds were checked before opening the active child.
                verify()
                live_raw, _ = live_route(fetch)
                if ledger.accounted()+BOUND>ledger.cap:
                    durable(journal,{'event':'stage_stopped','next_unsent_id':rid,
                                     'reason':'insufficient_capacity','utc':utc()})
                    return False
                durable(journal,{'event':'request_intent','id':rid,
                    'payload_sha256':item['payload_sha256'],'utc':utc()})
                attempt = ledger.reserve(BOUND,rid)
                durable(journal,{'event':'request_started','id':rid,'attempt_id':attempt,
                    'payload_sha256':item['payload_sha256'],'live_endpoint_sha256':native.sha(live_raw),
                    'live_endpoint_base64':base64.b64encode(live_raw).decode('ascii'),'utc':utc()})
                started = utc(); t0=time.perf_counter_ns()
                try:
                    status,wire = send(item['payload'],token)
                except BaseException as error:
                    durable(attempts,{'id':rid,'attempt_id':attempt,'status':'transport_error',
                        'error_type':type(error).__name__,'cost_unknown':True,
                        'reserved_cost_usd':str(BOUND)})
                    durable(journal,{'event':'stage_stopped','id':rid,
                        'reason':'transport_outcome_unknown','utc':utc()})
                    raise
                raw_entry = {'id':rid,'attempt_id':attempt,
                    'payload_sha256':item['payload_sha256'],'http_status':status,
                    'response_sha256':native.sha(wire),
                    'response_base64':base64.b64encode(wire).decode('ascii'),
                    'request_started_utc':started,'request_ended_utc':utc(),
                    'client_request_elapsed_ns':time.perf_counter_ns()-t0}
                durable(raw,raw_entry)
                try: body = json.loads(wire)
                except (UnicodeDecodeError,ValueError): body = None
                actual = native.response_cost(body)
                if actual is None:
                    durable(attempts,{'id':rid,'attempt_id':attempt,'status':'unknown_cost',
                        'http_status':status,'cost_unknown':True,'reserved_cost_usd':str(BOUND)})
                    durable(journal,{'event':'stage_stopped','id':rid,
                        'reason':'unknown_cost','utc':utc()})
                    return False
                billing_ok = ledger.settle(attempt,actual)
                if not billing_ok:
                    durable(attempts,{'id':rid,'attempt_id':attempt,'status':'observed_cost_over_bound',
                        'http_status':status,'cost_unknown':False,'actual_cost_usd':str(actual)})
                    durable(journal,{'event':'stage_stopped','id':rid,
                        'reason':'observed_cost_over_bound','utc':utc()})
                    return False
                if status != 200:
                    durable(attempts,{'id':rid,'attempt_id':attempt,'status':'http_error',
                        'http_status':status,'cost_unknown':False,'actual_cost_usd':str(actual)})
                    durable(journal,{'event':'stage_stopped','id':rid,
                        'reason':'provider_http_error','utc':utc()})
                    return False
                try: prediction, validated_cost = validate_returned(body)
                except (ValueError,TypeError):
                    durable(attempts,{'id':rid,'attempt_id':attempt,'status':'invalid_native',
                        'http_status':status,'cost_unknown':False,'actual_cost_usd':str(actual)})
                    durable(journal,{'event':'stage_stopped','id':rid,
                        'reason':'invalid_native','utc':utc()})
                    return False
                if validated_cost != actual:
                    raise ValueError('Solar validated cost changed')
                durable(attempts,{'id':rid,'attempt_id':attempt,'status':'ok',
                    'http_status':status,'cost_unknown':False,'actual_cost_usd':str(actual),
                    'response_sha256':native.sha(wire)})
                durable(parsed,{'id':rid,'attempt_id':attempt,'prediction':prediction,
                    'returned_model':body['model'],'returned_provider':body['provider'],
                    'response_sha256':native.sha(wire),'usage':body['usage']})
                durable(journal,{'event':'request_finished','id':rid,
                    'attempt_id':attempt,'utc':utc()})
            durable(journal,{'event':'stage_completed','count':2,'utc':utc()})
        return True
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','verify','review-template',
                                           'stage-template','live-check','smoke'))
    parser.add_argument('--env-file')
    action = parser.parse_args()
    if action.action == 'prepare': print(prepare())
    elif action.action == 'verify': print(verify())
    elif action.action == 'review-template': print(json.dumps(review_template(),indent=2))
    elif action.action == 'stage-template': print(json.dumps(stage_template(),indent=2))
    elif action.action == 'live-check':
        verify(); live_route(); print(json.dumps({'inference_sent':False,
            'model':solar.MODEL,'provider_tag':'upstage','per_request_reserve_usd':str(BOUND)}))
    else: print(execute(env_file=action.env_file))


if __name__ == '__main__':
    main()
