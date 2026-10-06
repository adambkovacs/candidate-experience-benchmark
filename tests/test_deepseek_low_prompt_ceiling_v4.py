"""Rate-ceiling gate and real temporary-ledger dispatch, with no live calls."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_prompt_ceiling_v4 as s
import test_openrouter_budget_amendment_v3 as budget_fixture


@pytest.fixture(scope='module')
def evidence():
    model, endpoint = s.prior._historical_current_price().route_context()
    live = json.loads(s.REFUSAL.read_text())
    return model, endpoint, live


@pytest.fixture(scope='module')
def proposal(): return s.manifest_value()


@pytest.mark.parametrize('rate', ['0', '0.000000001', '0.000000021421', '0.000000055'])
def test_prompt_rates_within_original_ceiling_keep_reserve(evidence, rate):
    model, endpoint, live = evidence; candidate = deepcopy(endpoint)
    candidate['pricing']['prompt'] = rate
    s.check_controls(model, candidate, model, endpoint)
    assert s.paid.reservation(candidate,4096,s.INPUT_CEILING,s.OUTPUT_CEILING) == s.RESERVE


@pytest.mark.parametrize('rate', ['-0.000000001', '0.000000055001', 'NaN', 'Infinity'])
def test_invalid_or_over_ceiling_prompt_rates_fail(evidence, rate):
    model, endpoint, live = evidence; candidate = deepcopy(endpoint)
    candidate['pricing']['prompt'] = rate
    with pytest.raises(ValueError): s.check_controls(model, candidate, model, endpoint)


@pytest.mark.parametrize('key,value', [('completion','0.00000132001'),
    ('input_cache_read','0.0000000164'), ('discount',1)])
def test_other_prices_remain_exact(evidence,key,value):
    model, endpoint, live = evidence; candidate = deepcopy(endpoint)
    candidate['pricing'][key] = value
    with pytest.raises(ValueError): s.check_controls(model,candidate,model,endpoint)


@pytest.mark.parametrize('key,value', [('status',-2),('context_length',1048575),
    ('quantization','fp8'),('tag','other/fp4'),('supported_parameters',['max_tokens'])])
def test_actual_execution_controls_remain_frozen(evidence,key,value):
    model, endpoint, live = evidence; candidate = deepcopy(endpoint); candidate[key] = value
    with pytest.raises(ValueError): s.check_controls(model,candidate,model,endpoint)


def test_operational_statistics_are_observed_not_admission_controls(evidence):
    model, endpoint, live = evidence; candidate = deepcopy(live['endpoint'])
    candidate.update(uptime_last_30m=95,latency_last_30m=12,throughput_last_30m=99)
    s.check_controls(live['model'],candidate,model,endpoint)
    changed = deepcopy(live['model']); changed['canonical_slug'] = 'different-model-date'
    with pytest.raises(ValueError): s.check_controls(changed,candidate,model,endpoint)


def test_saved_price_decrease_passes_full_gate_with_identical_request_hashes(evidence,proposal):
    model, endpoint, live = evidence
    catalog = {'data':[live['model']]}
    endpoints = {'data':{'id':s.admission.MODEL,'endpoints':[live['endpoint']]}}
    with patch.object(s.paid,'fetch',side_effect=[catalog,endpoints]), \
         patch.object(s,'verify',return_value=proposal):
        assert s.live_controls() == (live['model'],live['endpoint'])
    assert proposal['requests'] == s.prior.verify()['requests']
    assert proposal['price_admission']['payload_change'] is False
    assert proposal['price_admission']['reservation_change'] is False
    assert proposal['child_cap_usd'] == '0.6307840'
    assert proposal['exact_live_rates_usd_per_token']['prompt'] == live['endpoint']['pricing']['prompt']
    assert proposal['current_public_route']['pricing'] == live['endpoint']['pricing']


def test_private_runner_bytecode_and_partition_identity(evidence):
    core = s._private_core(); previous = s.prior._private_core()
    assert core.run.__code__ == previous.run.__code__
    assert core.PARTITION_ID == s.PARTITION_ID
    assert core.BASE == s.BASE and core.live_controls is s.live_controls
    assert core.hold_authority is not previous.hold_authority


def test_new_partition_reaches_dispatch_and_unknown_stops_with_full_earmarked_hold(proposal,evidence):
    fixture = budget_fixture.AdditionalOpenRouterBudgetTest(); fixture.setUp()
    try:
        fixture.activate(); base = fixture.base/'prompt-ceiling'; base.mkdir()
        manifest=base/'manifest.json'; manifest.write_text(json.dumps(proposal)); budget=base/'budget.json'
        live=evidence[2]; sent=[]; original_hold=s.authority.hold_authority
        def hold(*args,**kwargs):
            assert args[1] == s.PARTITION_ID and kwargs['partition_id'] == s.PARTITION_ID
            assert kwargs['funding_pool'] == 'openrouter_additional'
            return original_hold(*args,**kwargs,**fixture.baseline)
        def transport(payload,token,timeout,raw,rid,attempt,request_sha):
            assert s.prior.prior.digest(json.dumps(payload,sort_keys=True)) == request_sha
            sent.append(rid); s.paid.durable(raw,{'id':rid,'attempt_id':attempt})
            return {'usage':{},'model':s.admission.MODEL,'provider':'OpenInference'}
        with patch.object(s,'BASE',base),patch.object(s,'MANIFEST',manifest), \
             patch.object(s.admission,'MASTER',fixture.master),patch.object(s,'verify',return_value=proposal), \
             patch.object(s,'live_controls',return_value=(live['model'],live['endpoint'])):
            core=s._private_core(); core.AUTHORITY=fixture.auth
            s.partitions.allocate(fixture.master,budget,[{'id':s.PARTITION_ID,'cap_usd':str(s.CHILD_CAP),
                'model':s.admission.MODEL,'provider':s.admission.PROVIDER,'reasoning':'low'}])
            source=core.global_hold_source(budget); head=fixture.snapshot().head_sha256
            review=base/'suffix.root-review.json'
            review.write_text(json.dumps({'schema':s.SCHEMA+'-root-review','approved':True,'reviewer':'root',
                'manifest_sha256':s.sha(manifest),'controller_sha256':s.sha(s.__file__),
                'prior_terminal_sha256':core.PRIOR_TERMINAL_SHA,'budget_manifest_sha256':s.sha(budget),
                'partition_id':s.PARTITION_ID,'child_cap_usd':str(s.CHILD_CAP),'ids':s.IDS,
                'request_sha256':[r['request_sha256'] for r in proposal['requests']],
                'global_authority_head_sha256':head,'global_hold_source_sha256':source}))
            with patch.object(s,'_private_core',return_value=core), \
                 patch.object(s.authority,'hold_authority',side_effect=hold), \
                 patch.object(s.paid,'load_key',return_value='synthetic-offline-key'), \
                 patch.object(core.transport,'fetch_recorded',side_effect=transport), \
                 patch.object(core.prior,'_body_result',return_value=('ok',{},None,'stop')):
                result=s.run(review,budget)
            assert sent == ['DEV-051']
            assert result == {'completed':False,'status':'unknown_cost','stopped_id':'DEV-051'}
            assert fixture.snapshot().openrouter_accounted_usd == s.CHILD_CAP
            with patch.object(s.paid,'load_key') as key:
                with pytest.raises(FileExistsError): core.run(review,budget)
                key.assert_not_called()
    finally: fixture.doCleanups()
