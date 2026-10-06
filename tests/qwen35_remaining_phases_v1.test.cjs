'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
const remaining=require('../scripts/qwen35_remaining_phases_v1.cjs');

const {plan}=legacy.verifyPlan();
const phases=[['fresh1','P2'],['fresh1','P1'],['fresh2','P2'],['fresh2','P1'],
  ['fresh2','P0'],['fresh3','P1'],['fresh3','P0'],['fresh3','P2']];
const ids=Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);

function evidence(){
  return {original:{attempted:52,saved:51,valid:44,invalid:7,unknown_ids:['DEV-052'],
      saved_ids:ids.slice(0,51),bindings:{'original/interruption.root-review.json':'a'.repeat(64)}},
    suffix:{status:'completed',attempted:8,saved:8,valid:6,invalid:2,unknown_ids:[],
      saved_ids:ids.slice(52),bindings:{'suffix/suffix.completion.json':'b'.repeat(64)}}};
}

test('remaining schedule preserves the exact eight frozen phases and request hashes',()=>{
  const schedule=remaining.remainingSchedule(plan);
  assert.deepEqual(schedule.map(x=>[x.pass,x.condition]),phases);
  for(const entry of schedule){
    assert.deepEqual(entry.ids,ids);
    assert.deepEqual(entry.request_sha256,
      plan.configurations[remaining.ID].conditions[entry.condition].requests.map(x=>x.sha256));
    assert.deepEqual(entry.stages,['smoke','development']);
  }
});

test('composite schema accounts for all 60 positions while preserving one unknown and non-clean status',()=>{
  const candidate=remaining.expectedCompositeReview(evidence());
  assert.equal(candidate.schema,'qwen35-p0-descriptive-composite-root-review-v1');
  assert.equal(candidate.phase,'qwen3.5-4b-sdk-thinking-on/fresh1/P0');
  assert.equal(candidate.saved,59);
  assert.equal(candidate.valid,50);
  assert.equal(candidate.invalid,9);
  assert.deepEqual(candidate.unknown_ids,['DEV-052']);
  assert.equal(candidate.saved+candidate.unknown_ids.length,60);
  assert.equal(candidate.clean_repeat_eligible,false);
  const approved={...candidate,approved:true,reviewer:'root',reviewed_utc:'2026-10-06T10:00:00Z'};
  assert.deepEqual(remaining.validateCompositeReview(approved,evidence()),approved);
  assert.throws(()=>remaining.validateCompositeReview({...approved,unknown_ids:[]},evidence()),/differs/);
  const incomplete=evidence();incomplete.suffix.saved=7;
  assert.throws(()=>remaining.expectedCompositeReview(incomplete),/eight saved/);
});

test('manifest preparation refuses missing or unreviewed terminal composite evidence',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-remaining-prepare-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const manifestPath=path.join(dir,'manifest.json'),compositePath=path.join(dir,'composite.json');
  assert.throws(()=>remaining.prepareManifest({manifestPath,compositePath}),/Composite review missing/);
  fs.writeFileSync(compositePath,JSON.stringify(remaining.expectedCompositeReview(evidence()))+'\n');
  assert.throws(()=>remaining.prepareManifest({manifestPath,compositePath,
    verifyEvidence:()=>evidence()}),/not approved/);
  assert.equal(fs.existsSync(manifestPath),false);
});

test('first successor smoke accepts only the reviewed composite; later stages require successor closures',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-remaining-pred-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const manifest={schedule:remaining.remainingSchedule(plan)};
  const composite={...remaining.expectedCompositeReview(evidence()),approved:true,
    reviewer:'root',reviewed_utc:'2026-10-06T10:00:00Z'};
  const deps={base:dir,verifyComposite:()=>composite};
  assert.equal(remaining.checkSuccessorPredecessor(manifest,'fresh1','P2','smoke',deps),null);
  assert.throws(()=>remaining.checkSuccessorPredecessor(manifest,'fresh1','P1','smoke',deps),
    /Prior successor phase incomplete/);
  assert.throws(()=>remaining.checkSuccessorPredecessor(manifest,'fresh1','P2','development',deps),
    /Smoke not complete/);
});

test('unapproved remaining-phases manifest blocks live preflight before any runtime check',async()=>{
  const manifest={status:'offline_prepared_unapproved'};
  let touched=false;
  await assert.rejects(remaining.preflightCandidate({manifest},'fresh1','P2','smoke',{
    runtime:async()=>{touched=true;}}),/awaits root approval/);
  assert.equal(touched,false);
});

test('successor run delegates through legacy hooks and accepts a reread equivalent receipt',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-remaining-run-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const p=remaining.stagePaths(remaining.ID,'fresh1','P2','smoke',dir);
  fs.mkdirSync(p.folder,{recursive:true});
  const reviewPath=path.join(p.folder,'smoke.root-review.json');
  fs.writeFileSync(reviewPath,'{}\n');
  const measured=ids.map(id=>({id}));
  const measuredHash=require('node:crypto').createHash('sha256')
    .update(JSON.stringify(measured)).digest('hex');
  const receipt={runtime_token_preflight:{observed_preflight_sha256:measuredHash,
    observed_instance_reference:'instance-1'}};
  const host={boot:'boot-1',sleep_wakes:10,lid_open:true,
    operational_policy:{schema:'local-execution-policy-v1',allow_battery_power:true,sha256:'x'},
    power_source:'battery'};
  const ctx={manifest:{status:'approved',schedule:remaining.remainingSchedule(plan)},
    manifestSha:'m'.repeat(64),plan,composite:{sha256:'c'.repeat(64)}};
  const original=legacy.runStage;let delegated=false,routeChecks=0;
  legacy.runStage=async(_plan,_planSha,_id,_pass,_condition,_stage,_review,hooks)=>{
    delegated=true;
    hooks.predecessor();
    hooks.admit(structuredClone(receipt));
    assert.equal((await hooks.runtime()).instance,'instance-1');
    assert.deepEqual(await hooks.routeAudit(),{checked_ms:1});
    assert.deepEqual(await hooks.routeAudit(),{checked_ms:2});
    fs.writeFileSync(p.completion,JSON.stringify({status:'completed'})+'\n',{flag:'wx'});
    return {status:'completed'};
  };
  t.after(()=>{legacy.runStage=original;});
  const result=await remaining.runSuccessorStage(ctx.manifestSha,'fresh1','P2','smoke',{
    ctx,base:dir,verifyComposite:()=>({approved:true}),verifyStageReview:()=>({receipt,
      reviewPath,current:host,paths:p}),runtime:async()=>({instance:'instance-1'}),
    verifyAll:async()=>measured,routeAudit:async()=>({checked_ms:++routeChecks}),currentHost:()=>host});
  assert.equal(delegated,true);
  assert.equal(routeChecks,2);
  assert.deepEqual(result,{status:'completed'});
  const audit=JSON.parse(fs.readFileSync(path.join(p.folder,'smoke.host-audit.json'),'utf8'));
  assert.equal(audit.status,'passed');
  assert.equal(audit.host_check.host_unchanged,true);
});

test('live route audit ignores unrelated Qwen sizes but blocks the exact target',async()=>{
  const data=Array.from({length:100},(_,i)=>({id:`fixture/model-${i}`}));
  data.push({id:'qwen/qwen3-0.6b'},{id:'qwen/qwen3-1.7b'});
  const fetcher=async()=>({status:200,text:async()=>JSON.stringify({data})});
  const result=await remaining.checkExactLiveRoute(fetcher);
  assert.equal(result.model_count,102);assert(Number.isFinite(result.checked_ms));
  data.push({id:'qwen/qwen3.5-4b'});
  await assert.rejects(remaining.checkExactLiveRoute(fetcher),/Exact Qwen3.5-4B hosted route/);
});
