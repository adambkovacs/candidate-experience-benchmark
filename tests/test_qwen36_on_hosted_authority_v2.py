"""Offline route/lifecycle/money tests exclusively on real temporary ledgers."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import qwen36_on_hosted_authority_v2 as s
import test_openrouter_budget_amendment_v3 as budget_fixture
import test_qwen36_on_fresh_repeat_execution as old_tests

@pytest.fixture(scope='module')
def plan():return s.plan_data('fresh1')

@pytest.fixture(scope='module')
def route():
    value=s.route_snapshot();return value['model'],value['endpoint']

def test_frozen_plans_proxy_and_isolation(plan):
    old=s.study.verify('fresh1',s.sha(s.study.BASE/'fresh1/manifest.json'))
    assert plan['conditions']==old['conditions']
    assert plan['historical_p2_outcomes_preserved']=={'ok':54,'service_error':6}
    assert plan['budget_estimate']['three_pass_known_plus_unknown_sensitivity_usd']=='1.2408645'
    assert plan['budget_estimate']['all_calls_at_maximum_reserve_usd']=='16.9537536'
    assert plan['configuration_id']!=old['configuration_id']
    assert plan['full_series_completion_guaranteed'] is False and plan['reference_labels_read'] is False

def test_saved_route_rebuilds_sixty_payloads(plan,route):
    model,endpoint=route
    with patch.object(s.paid,'fetch',side_effect=[{'data':[model]},{'data':{'id':s.study.MODEL,'endpoints':[endpoint]}}]):
        assert s.live_controls(plan,'P0')==(model,endpoint,s.RESERVE)

@pytest.mark.parametrize('key,value',[('status',-2),('quantization','fp4'),('tag','other/fp8'),('context_length',262143),('supported_parameters',['max_tokens'])])
def test_changed_controls_fail(route,key,value):
    model,endpoint=route;changed=deepcopy(endpoint);changed[key]=value
    with pytest.raises(ValueError):s.check_route(model,changed,model,endpoint)

def test_price_and_model_frozen_operational_stats_excluded(route):
    model,endpoint=route;changed=deepcopy(endpoint);changed['uptime_last_30m']=90
    s.check_route(model,changed,model,endpoint)
    changed['pricing']['prompt']='0.00000010001'
    with pytest.raises(ValueError):s.check_route(model,changed,model,endpoint)
    different=deepcopy(model);different['canonical_slug']='different-model'
    with pytest.raises(ValueError):s.check_route(different,endpoint,model,endpoint)

class Fixture:
    def __init__(self,plan,route,mp):
        self.b=budget_fixture.AdditionalOpenRouterBudgetTest();self.b.setUp();self.b.activate()
        self.base=self.b.base/'qwen';self.base.mkdir();self.master=self.b.master;self.auth=self.b.auth
        self.model,self.endpoint=route;self.sent=[];self.responses=[]
        for name,value in [('BASE',self.base),('MASTER',self.master),('AUTHORITY',self.auth),('EXECUTION',self.base/'execution-manifest.json')]:mp.setattr(s,name,value)
        s.EXECUTION.write_text('{"offline_fixture":true}\n');self.plans={}
        for repeat in s.study.ORDERS:
            value=deepcopy(plan);value['fresh_pass']=repeat;value['condition_order']=s.study.ORDERS[repeat]
            path=self.base/repeat/'manifest.json';path.parent.mkdir();path.write_text(json.dumps(value));self.plans[repeat]=value
        mp.setattr(s,'verify_plan',lambda repeat,digest:self.plans[repeat]);mp.setattr(s,'verify',lambda:{'fixture':True})
        mp.setattr(s,'live_controls',lambda plan,condition:(self.model,self.endpoint,s.RESERVE))
        read=s.authority.read_authority;scan=s.authority._scan;hold=s.authority.hold_authority
        mp.setattr(s.authority,'read_authority',lambda path:read(path,**self.b.baseline))
        mp.setattr(s.authority,'_scan',lambda raw,**kwargs:scan(raw,**(kwargs or self.b.baseline)))
        mp.setattr(s.authority,'hold_authority',lambda *a,**k:hold(*a,**k,**self.b.baseline))
        s.partitions.allocate(self.master,self.base/'budget.json',[{'id':s.PARTITION_ID,'cap_usd':str(s.CAP),'model':s.study.MODEL,'provider':s.study.PROVIDER,'reasoning':'on'}])
        self.core=s._private_runner();mp.setattr(self.core,'audit_response',lambda *a:{'passed':True,'blockers':[]})
        mp.setattr(self.core.paid,'load_key',lambda env:'synthetic-offline-key')
        def opener(request,timeout):
            self.sent.append(json.loads(request.data));return old_tests.FakeResponse(json.dumps(self.responses.pop(0)).encode())
        mp.setattr(self.core.transport.OPENER,'open',opener)
    def body(self,cost='0.0001',invalid=False):
        return {'model':s.study.MODEL,'provider':s.study.PROVIDER_NAME,'usage':{'cost':cost,'prompt_tokens':100,'completion_tokens':20},'choices':[{'finish_reason':'stop','message':{'content':'invalid' if invalid else json.dumps(old_tests.PREDICTION)}}]}
    def review(self,repeat='fresh1',condition='P0',phase='smoke'):
        value=s.stage_receipt(repeat,condition,phase,self.base/'budget.json');value.update(approved=True,independent_review=True,authorized_by_root=True,reviewer='root')
        path=self.base/repeat/condition/(phase+'.root-review.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(value));return path
    def run(self,phase,responses,repeat='fresh1',condition='P0'):
        self.responses=list(responses);review=self.review(repeat,condition,phase)
        return self.core.execute(s.CONFIG,repeat,condition,phase,s.sha(self.base/repeat/'manifest.json'),review)
    def ledger(self):return s.partitions.open_partition(self.master,self.base/'budget.json',s.PARTITION_ID,s.study.MODEL,s.study.PROVIDER,'on')

@pytest.fixture
def fixture(plan,route,monkeypatch):
    f=Fixture(plan,route,monkeypatch)
    try:yield f
    finally:f.b.doCleanups()

def test_smoke_inspection_development_next_condition_no_replay(fixture):
    f=fixture;assert f.run('smoke',[f.body()]*3)
    with pytest.raises(ValueError,match='Inspected smoke'):f.core.require_order(f.plans['fresh1'],'P0','development')
    f.core.inspect(s.CONFIG,'fresh1','P0',s.sha(f.base/'fresh1/manifest.json'),'Three raw outcomes inspected.')
    assert f.run('development',[f.body()]*60);f.core.verify_phase_closure(f.plans['fresh1'],'P0','development')
    assert f.run('smoke',[f.body()]*3,condition='P1')
    holds=[json.loads(x) for x in f.auth.read_text().splitlines() if json.loads(x).get('funding_pool')=='openrouter_additional']
    assert len(holds)==1 and holds[0]['usd']=='1.50' and len(f.sent)==66
    with pytest.raises(FileExistsError):f.run('development',[],condition='P0')
    with pytest.raises(ValueError,match='Earlier fresh pass incomplete'):f.run('smoke',[],repeat='fresh2',condition='P1')

@pytest.mark.parametrize('unknown,invalid',[(True,False),(False,True)])
def test_unknown_and_invalid_stop(fixture,unknown,invalid):
    f=fixture;assert not f.run('smoke',[f.body(None if unknown else '0.0001',invalid)]);assert len(f.sent)==1
    rows=f.core.jsonl(f.base/'fresh1/P0/smoke.attempts.jsonl');ledger=f.ledger()
    try:
        if unknown:assert rows[0]['cost_unknown'] is True and len(ledger.state()[1])==1 and ledger.accounted()==s.RESERVE
        else:assert rows[0]['status']=='invalid_output' and ledger.accounted()==Decimal('0.0001')
    finally:ledger.close()
    with pytest.raises(FileExistsError):f.run('smoke',[])

def test_capacity_stop_before_unfunded_request(fixture):
    f=fixture
    # Admit the normal fresh whole-series hold, then spend to the boundary in
    # this synthetic fixture. No live requests or real ledger writes occur.
    receipt=json.loads(f.review().read_text());ledger=f.core.budget_gate(receipt,f.base/'budget.json',s.CONFIG)
    try:
        aid=ledger.reserve(Decimal('1.46'),'SYNTHETIC-PRIOR');ledger.settle(aid,Decimal('1.46'))
    finally:ledger.close()
    assert not f.run('smoke',[f.body('0.0299')]);assert len(f.sent)==1
    events=f.core.jsonl(f.base/'fresh1/P0/smoke.journal.jsonl')
    assert events[-1]['event']=='phase_stopped' and events[-1]['reason']=='insufficient_capacity' and events[-1]['next_unsent_id']=='DEV-002'
    ledger=f.ledger()
    try:assert ledger.accounted()==Decimal('1.4899') and not ledger.state()[1]
    finally:ledger.close()

def test_unapproved_receipt_before_key_or_transport(fixture):
    f=fixture;review=f.review();value=json.loads(review.read_text());value['independent_review']=False;review.write_text(json.dumps(value))
    with patch.object(f.core.paid,'load_key') as key:
        with pytest.raises(ValueError,match='root stage receipt'):f.core.execute(s.CONFIG,'fresh1','P0','smoke',s.sha(f.base/'fresh1/manifest.json'),review)
        key.assert_not_called()
    assert not f.sent and not (f.base/'fresh1/P0/smoke.claim.json').exists()

def test_private_globals_unchanged():
    before={k:getattr(s.frozen.runner,k) for k in ('study','budget_gate','execute','review_receipt')};core=s._private_runner()
    assert core.partitions is s.partitions and {k:getattr(s.frozen.runner,k) for k in before}==before
