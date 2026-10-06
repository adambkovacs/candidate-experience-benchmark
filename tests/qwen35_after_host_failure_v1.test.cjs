'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const continuation=require('../scripts/qwen35_after_host_failure_v1.cjs');
const previous=require('../scripts/qwen35_after_smoke_failure_v1.cjs');
const {plan}=require('../scripts/legacy_qwen_repeat_admission.cjs').verifyPlan();
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const state=continuation.verifyFrozenState();
const proposal=continuation.expectedProposal(state);
function temp(t){const p=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-host-continuation-'));
  t.after(()=>fs.rmSync(p,{recursive:true,force:true}));return p;}
function fixture(t){const dir=temp(t);for(const file of Object.values(continuation.blockedPaths()))
  fs.copyFileSync(file,path.join(dir,path.basename(file)));return dir;}
function mutate(file,fn){const d=JSON.parse(fs.readFileSync(file));fn(d);fs.writeFileSync(file,JSON.stringify(d)+'\n');}
function rewriteRows(file,fn){const d=fs.readFileSync(file,'utf8').trim().split('\n').map(JSON.parse);
  fn(d);fs.writeFileSync(file,d.map(x=>JSON.stringify(x)).join('\n')+'\n');}
function rehash(base,key){mutate(path.join(base,'smoke.completion.json'),d=>{
  d[`${key}_sha256`]=sha(path.join(base,`smoke.${key}.jsonl`));});
  mutate(path.join(base,'smoke.host-audit.json'),d=>d.completion_sha256=sha(path.join(base,'smoke.completion.json')));}

test('both terminal failures remain frozen; DEV-003 stays unknown and no full pass is credited',()=>{
  assert.equal(state.blocked.phase,`${continuation.ID}/fresh2/P1`);
  assert.equal(state.blocked.status,'host_sleep_blocked');assert.equal(state.blocked.valid,2);
  assert.equal(state.blocked.unknown,1);assert.deepEqual(state.blocked.unknown_ids,['DEV-003']);
  assert.equal(state.blocked.development_admitted,false);assert.equal(state.blocked.replay_authorized,false);
  assert.equal(state.blocked.clean_repeat_credit,false);assert.equal(Object.keys(state.blocked.bindings).length,12);
  assert.deepEqual(state.blockedP2,previous.verifyBlockedSmoke(plan));
  assert.equal(proposal.scope.prior_blocked_phase.invalid,1);
});

test('only untouched fresh2/P0 then fresh3/P1/P0/P2 are scheduled with unchanged controls',()=>{
  assert.deepEqual(proposal.scope.phases.map(x=>[x.pass,x.condition]),
    [['fresh2','P0'],['fresh3','P1'],['fresh3','P0'],['fresh3','P2']]);
  assert.equal(proposal.inference_authorized,false);assert.equal(proposal.policy.controls_unchanged,true);
  assert.equal(proposal.policy.prior_blocked_phase_development_admission,false);
  assert.equal(proposal.policy.prior_blocked_phase_replay,false);
  assert.deepEqual(proposal.runtime,state.previous.proposal.runtime);
  for(const phase of proposal.scope.phases){
    assert.deepEqual(phase.ids,continuation.IDS);assert.deepEqual(phase.request_sha256,
      plan.configurations[continuation.ID].conditions[phase.condition].requests.map(x=>x.sha256));
  }
});

test('both blocked slots are rejected and untouched phases retain predecessor ordering',t=>{
  const base=temp(t);
  assert.equal(continuation.checkContinuationPredecessor(proposal,'fresh2','P0','smoke',{base,state}),null);
  for(const condition of ['P1','P2'])for(const stage of ['smoke','development'])
    assert.throws(()=>continuation.checkContinuationPredecessor(proposal,'fresh2',condition,stage,{base,state}),/outside post-failure schedule/);
  assert.throws(()=>continuation.checkContinuationPredecessor(proposal,'fresh3','P1','smoke',{base,state}),/Prior successor phase incomplete/);
  assert.throws(()=>continuation.checkContinuationPredecessor(proposal,'fresh2','P0','development',{base,state}),/Smoke not complete/);
});

test('unapproved proposal blocks preflight and run before runtime or new files',async t=>{
  const base=temp(t);let touched=false;
  const ctx={proposal,proposalSha:'a'.repeat(64),state,plan};
  const deps={ctx,base,runtime:async()=>{touched=true;},currentHost:()=>{touched=true;}};
  await assert.rejects(continuation.preflightCandidate(ctx,'fresh2','P0','smoke',deps),/awaits independent root approval/);
  await assert.rejects(continuation.runContinuationStage(ctx.proposalSha,'fresh2','P0','smoke',deps),/awaits independent root approval/);
  assert.equal(touched,false);assert.deepEqual(fs.readdirSync(base),[]);
});

test('reviewable preparation and checked-in proposal grant no admission',t=>{
  const dir=temp(t),proposalPath=path.join(dir,'proposal.json'),candidatePath=path.join(dir,'root-review-candidate.json');
  continuation.prepareProposal({proposalPath,candidatePath,state});
  const ctx=continuation.verifyProposal(proposalPath,state),candidate=JSON.parse(fs.readFileSync(candidatePath));
  assert.equal(ctx.proposal.status,'offline_prepared_unapproved');assert.equal(candidate.approved,false);
  assert.equal(candidate.authorized_by_root,false);assert.equal(candidate.independent_review,false);
  assert.equal(candidate.inference_authorized,false);assert.equal(candidate.proposal_sha256,ctx.proposalSha);
  assert(['offline_prepared_unapproved','approved'].includes(continuation.verifyProposal().proposal.status));
  const savedCandidate=JSON.parse(fs.readFileSync(continuation.REVIEW_CANDIDATE));
  assert.equal(savedCandidate.approved,false);assert.equal(savedCandidate.inference_authorized,false);
});

test('record hash tampering is rejected',t=>{
  const base=fixture(t);rewriteRows(path.join(base,'smoke.records.jsonl'),d=>d[0].decision.prediction.sentiment='negative');
  assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/records hash differs/);
});

test('rehashed classification tampering still fails strict raw classification',t=>{
  const base=fixture(t);rewriteRows(path.join(base,'smoke.records.jsonl'),d=>d[0].decision.prediction.sentiment='negative');
  rehash(base,'records');assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/Expected values to be strictly deep-equal/);
});

test('rehashed unknown-journal substitution cannot erase the failed attempt',t=>{
  const base=fixture(t);rewriteRows(path.join(base,'smoke.journal.jsonl'),d=>d[5].event='finished');
  rehash(base,'journal');assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/stopped_unknown/);
});

test('rehashed raw timeout substitution cannot turn DEV-003 into a result',t=>{
  const base=fixture(t);rewriteRows(path.join(base,'smoke.raw.jsonl'),d=>d[2].result={answer:'{}'});
  rehash(base,'raw');assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/strictly equal/);
});

test('host-sleep proof is required independently of terminal status',t=>{
  const base=fixture(t);mutate(path.join(base,'smoke.host-audit.json'),d=>d.after.sleep_wakes=d.before.sleep_wakes);
  assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/strictly equal/);
});

test('changed approved candidate or prior proposal binding is rejected',t=>{
  const base=fixture(t);mutate(path.join(base,'smoke.root-review.json'),d=>d.proposal_sha256='0'.repeat(64));
  mutate(path.join(base,'smoke.claim.json'),d=>d.receipt_sha256=sha(path.join(base,'smoke.root-review.json')));
  mutate(path.join(base,'smoke.host-audit.json'),d=>d.reviewed_receipt_sha256=sha(path.join(base,'smoke.root-review.json')));
  assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/strictly equal/);
});

test('prior development artifacts cannot coexist with blocked terminal smoke',t=>{
  const base=fixture(t);fs.writeFileSync(path.join(base,'development.claim.json'),'{}\n');
  assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base}),/Blocked phase was promoted/);
});
