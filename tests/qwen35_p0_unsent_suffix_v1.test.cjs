'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
const small=require('../scripts/small_local_repeat_admission.cjs');
const suffix=require('../scripts/qwen35_p0_unsent_suffix_v1.cjs');

const expectedIds=Array.from({length:8},(_,i)=>`DEV-${String(i+53).padStart(3,'0')}`);
const {plan}=legacy.verifyPlan();

test('original interruption is bound as 51 saved plus unknown DEV-052 and eight never sent',()=>{
  const evidence=suffix.verifyOriginalEvidence(plan);
  assert.deepEqual(evidence,{attempted:52,saved:51,valid:44,invalid:7,
    unknown_ids:['DEV-052'],never_sent_ids:expectedIds,clean_repeat_eligible:false});
});

test('manifest freezes only the eight never-sent P0 requests and retains the completed smoke',()=>{
  const manifest=suffix.expectedManifest();
  const frozen=plan.configurations[suffix.ID].conditions.P0.requests.slice(52);
  assert.equal(manifest.status,'offline_prepared_unapproved');
  assert.equal(manifest.method,'descriptive-interrupted-series-unsent-suffix');
  assert.equal(manifest.clean_repeat_eligible,false);
  assert.equal(manifest.smoke.replayed,false);
  assert.equal(manifest.smoke.saved,3);
  assert.deepEqual(manifest.suffix.ids,expectedIds);
  assert.deepEqual(manifest.suffix.requests,frozen);
  assert.deepEqual(suffix.selectedRows(plan).map(row=>row.id),expectedIds);
  assert(!manifest.suffix.ids.includes('DEV-052'));
  assert.deepEqual(manifest.policy.never_replay_ids,suffix.IDS.slice(0,52));
  assert.equal(new Set([...manifest.policy.never_replay_ids,...manifest.suffix.ids]).size,60);
  assert.equal(manifest.policy.never_replay_ids.length+manifest.suffix.ids.length,60);
  assert.deepEqual(manifest.original.unknown_ids,['DEV-052']);
  assert(!manifest.policy.never_replay_ids.some(id=>manifest.suffix.ids.includes(id)));
});

test('offline root-review candidate cannot authorize preflight or dispatch',async()=>{
  const ctx=suffix.verifyManifest();
  const candidate=suffix.verifyRootReviewCandidate(ctx);
  assert.equal(candidate.approved,false);
  assert.equal(candidate.authorized_by_root,false);
  assert.deepEqual(candidate.ids,expectedIds);
  const approvedCtx={...ctx,manifest:{...ctx.manifest,status:'approved',approval:{
    independent_review:true,authorized_by_root:true,reviewer:'root',reviewed_utc:'2026-10-06T10:00:00Z'}},
    manifestSha:'f'.repeat(64)};
  assert.deepEqual(suffix.verifyRootReviewCandidate(approvedCtx),candidate);
  const unapprovedCtx={...ctx,manifest:{...ctx.manifest,
    status:'offline_prepared_unapproved',approval:null}};
  await assert.rejects(suffix.preflightCandidate(unapprovedCtx),/awaits root approval/);
  assert.throws(()=>suffix.verifyExecutionReview(suffix.REVIEW_CANDIDATE,ctx,null),/fixed suffix root-review/);
});

test('injected timeout atomically claims only DEV-053, preserves raw unknown, and cannot replay',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-unsent-suffix-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const p=suffix.outputPaths(dir);
  const receipt=path.join(dir,'suffix.root-review.json');
  fs.writeFileSync(receipt,'{}\n');
  const manifest=suffix.expectedManifest();
  let calls=0;
  const error=Object.assign(new Error('fixture timeout'),{code:'PREDICTION_TIMEOUT',
    cancellationAcknowledged:true,partialResult:{reasoningContent:'partial'}});
  const dependencies={
    prepare:()=>({manifest,paths:p,receipt:{host_baseline:{boot:'fixture',sleep_wakes:0,
      lid_open:true,power_source:'ac',operational_policy:{schema:'fixture'}}}}),
    runtime:async()=>({instance:'fixture-instance',
      model:{getModelInfo:async()=>({instanceReference:'fixture-instance'})},
      attestation:{artifact_sha256:plan.configurations[suffix.ID].artifact_sha256}}),
    verifyAll:async()=>Array.from({length:60},(_,i)=>({id:`DEV-${String(i+1).padStart(3,'0')}`})),
    verifyOne:async(_runtime,_config,item)=>({id:item.id}),
    routeAudit:async()=>({checked_ms:Date.now(),source:'fixture',model_count:464}),
    currentHost:()=>({boot:'fixture',sleep_wakes:0,lid_open:true,power_source:'ac',
      operational_policy:{schema:'fixture'}}),
    verifyAfterStage:()=>({host_unchanged:true}),
    predict:async()=>{calls++;throw error;},
  };
  await assert.rejects(suffix.runSuffix('test-sha',receipt,dependencies),/fixture timeout/);
  assert.equal(calls,1);
  assert.deepEqual(small.rows(p.journal).map(x=>[x.event,x.id]),
    [['started','DEV-053'],['stopped_unknown','DEV-053']]);
  assert.equal(small.rows(p.raw)[0].partialResult.reasoningContent,'partial');
  assert.equal(fs.statSync(p.records).size,0);
  assert.equal(small.read(p.completion).status,'stopped');
  await assert.rejects(suffix.runSuffix('test-sha',receipt,dependencies),/already claimed/);
  assert.equal(calls,1);
});
