'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
const remaining=require('../scripts/qwen35_remaining_phases_v1.cjs');
const continuation=require('../scripts/qwen35_after_smoke_failure_v1.cjs');

const {plan}=legacy.verifyPlan();
const ids=Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);
const sha=file=>require('node:crypto').createHash('sha256').update(fs.readFileSync(file)).digest('hex');

function writeClosedStage(base,pass,condition,stage,statuses){
  const files=continuation.stagePaths(continuation.ID,pass,condition,stage,base);
  fs.mkdirSync(files.folder,{recursive:true});
  const phase=`${continuation.ID}/${pass}/${condition}`;
  fs.writeFileSync(files.journal,statuses.flatMap((_,i)=>[
    JSON.stringify({event:'started',id:ids[i]}),JSON.stringify({event:'finished',id:ids[i]})]).join('\n')+'\n');
  fs.writeFileSync(files.raw,statuses.map((_,i)=>JSON.stringify({id:ids[i]})).join('\n')+'\n');
  fs.writeFileSync(files.records,statuses.map((decision,i)=>JSON.stringify({id:ids[i],decision:{status:decision}})).join('\n')+'\n');
  const completion={phase,stage,status:'completed',reason:null,attempted:statuses.length,saved:statuses.length,
    invalid:statuses.filter(x=>x!=='ok').length,journal_sha256:sha(files.journal),raw_sha256:sha(files.raw),
    records_sha256:sha(files.records),finished_utc:'2026-10-06T12:00:00.000Z'};
  fs.writeFileSync(files.completion,JSON.stringify(completion)+'\n');
  const review=path.join(files.folder,`${stage}.root-review.json`);
  fs.writeFileSync(review,JSON.stringify({kind:continuation.SCHEMA+'-stage-root-review',approved:true})+'\n');
  fs.writeFileSync(path.join(files.folder,`${stage}.host-audit.json`),JSON.stringify({
    schema:continuation.SCHEMA+'-host-audit',status:'passed',phase,stage,error:null,
    completion_sha256:sha(files.completion),reviewed_receipt_sha256:sha(review)})+'\n');
  if(stage==='smoke') fs.writeFileSync(path.join(files.folder,'smoke-inspection.json'),JSON.stringify({
    kind:'legacy-qwen-three-record-smoke-inspection-v1',approved:true,raw_sha256:completion.raw_sha256,
    records_sha256:completion.records_sha256,completion_sha256:sha(files.completion)})+'\n');
  return files;
}

test('terminal smoke is hash-bound, classified, and never promoted to development',()=>{
  const blocked=continuation.verifyBlockedSmoke(plan);
  assert.deepEqual({phase:blocked.phase,status:blocked.status,attempted:blocked.attempted,
    saved:blocked.saved,valid:blocked.valid,invalid:blocked.invalid,
    development_admitted:blocked.development_admitted,replay_authorized:blocked.replay_authorized,
    invalid_reason_ids:blocked.invalid_reason_ids},{phase:`${continuation.ID}/fresh2/P2`,
    status:'smoke_blocked',attempted:3,saved:3,valid:2,invalid:1,
    development_admitted:false,replay_authorized:false,invalid_reason_ids:{non_json:['DEV-001']}});
  assert.equal(Object.keys(blocked.bindings).length,12);
});

test('proposal retains controls and schedules only unrelated later phases',()=>{
  const state=continuation.verifyFrozenState(),proposal=continuation.expectedProposal(state);
  assert.equal(proposal.status,'offline_prepared_unapproved');assert.equal(proposal.inference_authorized,false);
  assert.deepEqual(proposal.scope.phases.map(x=>[x.pass,x.condition]),continuation.PHASES);
  assert(!proposal.scope.phases.some(x=>x.pass==='fresh2'&&x.condition==='P2'));
  assert.equal(proposal.scope.blocked_phase.bindings.completion.sha256,
    state.blocked.bindings.completion.sha256);
  assert.equal(proposal.policy.blocked_smoke_replay,false);
  assert.equal(proposal.policy.blocked_phase_development_admission,false);
  assert.equal(proposal.policy.controls_unchanged,true);
  const old=state.prior.manifest.runtime;
  for(const key of ['model_identifier','artifact_path','artifact_sha256','artifact_bytes','context',
    'output_reserve','timeout_ms','request_config_sha256','load_config_sha256','prediction_config_sha256'])
    assert.deepEqual(proposal.runtime[key],old[key]);
  for(const phase of proposal.scope.phases){
    assert.deepEqual(phase.ids,ids);
    assert.deepEqual(phase.request_sha256,
      plan.configurations[continuation.ID].conditions[phase.condition].requests.map(x=>x.sha256));
  }
});

test('unapproved proposal blocks preflight before runtime or filesystem mutation',async()=>{
  const state=continuation.verifyFrozenState();let touched=false;
  const ctx={proposal:continuation.expectedProposal(state),state,plan,proposalSha:'p'.repeat(64)};
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-after-failure-unapproved-'));
  try{
    await assert.rejects(continuation.preflightCandidate(ctx,'fresh2','P1','smoke',{
      base:dir,runtime:async()=>{touched=true;}}),/awaits independent root approval/);
    assert.equal(touched,false);assert.deepEqual(fs.readdirSync(dir),[]);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('predecessor bypasses only the exact blocked slot and still orders later phases',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-after-failure-pred-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const state=continuation.verifyFrozenState(),proposal=continuation.expectedProposal(state);
  assert.equal(continuation.checkContinuationPredecessor(proposal,'fresh2','P1','smoke',{base:dir,state}),null);
  assert.throws(()=>continuation.checkContinuationPredecessor(proposal,'fresh2','P2','smoke',{base:dir,state}),
    /outside post-failure schedule|cannot be replayed/);
  assert.throws(()=>continuation.checkContinuationPredecessor(proposal,'fresh2','P0','smoke',{base:dir,state}),
    /Prior successor phase incomplete/);
  assert.throws(()=>continuation.checkContinuationPredecessor(proposal,'fresh2','P1','development',{base:dir,state}),
    /Smoke not complete/);
});

test('completed continuation smoke admits its development transition and continuation audit schema',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-after-failure-transition-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const state=continuation.verifyFrozenState(),proposal=continuation.expectedProposal(state);
  writeClosedStage(dir,'fresh2','P1','smoke',['ok','ok','ok']);
  assert.doesNotThrow(()=>continuation.checkContinuationPredecessor(
    proposal,'fresh2','P1','development',{base:dir,state}));
  const audit=path.join(dir,'fresh2','P1','smoke.host-audit.json');
  const changed=JSON.parse(fs.readFileSync(audit));changed.schema=remaining.SCHEMA+'-host-audit';
  fs.writeFileSync(audit,JSON.stringify(changed)+'\n');
  assert.throws(()=>continuation.checkContinuationPredecessor(
    proposal,'fresh2','P1','development',{base:dir,state}),/actual.*qwen35-remaining-phases-v1-host-audit|Expected values to be strictly equal/);
});

test('completed continuation development unlocks the next scheduled smoke',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-after-failure-next-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const state=continuation.verifyFrozenState(),proposal=continuation.expectedProposal(state);
  writeClosedStage(dir,'fresh2','P1','development',Array(60).fill('ok'));
  assert.doesNotThrow(()=>continuation.checkContinuationPredecessor(
    proposal,'fresh2','P0','smoke',{base:dir,state}));
});

test('proposal preparation creates reviewable files but grants no admission',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-after-failure-prepare-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const proposalPath=path.join(dir,'proposal.json'),candidatePath=path.join(dir,'root-review-candidate.json');
  continuation.prepareProposal({proposalPath,candidatePath});
  const proposal=JSON.parse(fs.readFileSync(proposalPath));
  const candidate=JSON.parse(fs.readFileSync(candidatePath));
  assert.equal(proposal.status,'offline_prepared_unapproved');assert.equal(proposal.approval,null);
  assert.equal(candidate.approved,false);assert.equal(candidate.authorized_by_root,false);
  assert.equal(candidate.independent_review,false);assert.equal(candidate.inference_authorized,false);
  assert.equal(candidate.blocked_smoke_replay,false);assert.equal(candidate.blocked_development_admission,false);
});

test('checked-in proposal matches current sources and remains unapproved',()=>{
  const ctx=continuation.verifyProposal();
  const candidate=JSON.parse(fs.readFileSync(continuation.REVIEW_CANDIDATE));
  assert.equal(ctx.proposal.status,'offline_prepared_unapproved');
  assert.equal(ctx.proposal.approval,null);assert.equal(ctx.proposal.inference_authorized,false);
  assert.equal(candidate.proposal_sha256,ctx.proposalSha);
  assert.equal(candidate.controller_sha256,ctx.proposal.frozen.continuation_controller.sha256);
  assert.equal(candidate.approved,false);assert.equal(candidate.authorized_by_root,false);
  assert.equal(candidate.independent_review,false);assert.equal(candidate.inference_authorized,false);
});

test('tampering with a bound blocked record is rejected',t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qwen35-after-failure-tamper-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  for(const file of Object.values(continuation.blockedPaths())) fs.copyFileSync(file,path.join(dir,path.basename(file)));
  const records=path.join(dir,'smoke.records.jsonl');
  const content=fs.readFileSync(records,'utf8').replace('"reason":"non_json"','"reason":"schema"');
  fs.writeFileSync(records,content);
  assert.throws(()=>continuation.verifyBlockedSmoke(plan,{base:dir}),/records hash differs|non_json/);
});
