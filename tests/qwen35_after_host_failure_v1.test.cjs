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

// Synthetic evidence stays in memory. Load a separate controller instance with
// read-only file adapters so neither global fs nor the live run is changed.
function positiveTransitionFixture(stage){
  const Module=require('node:module');
  const small=require('../scripts/small_local_repeat_admission.cjs');
  const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
  const classifier=require('../scripts/local_prompt_execution_v1.cjs');
  const contents=new Map();
  const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
  const put=(file,value)=>contents.set(file,Buffer.from(typeof value==='string'?value:JSON.stringify(value)+'\n'));
  const bytes=file=>contents.has(file)?contents.get(file):fs.readFileSync(file);
  const hashFile=file=>contents.has(file)?digest(contents.get(file)):small.hashFile(file);
  const read=file=>JSON.parse(bytes(file).toString('utf8'));
  const rows=file=>bytes(file).toString('utf8').split('\n').filter(Boolean).map(JSON.parse);
  const filename=require.resolve('../scripts/qwen35_after_host_failure_v1.cjs');
  const isolated=new Module(filename,module);
  isolated.filename=filename;isolated.paths=module.paths;
  const nativeRequire=isolated.require.bind(isolated);
  isolated.require=id=>{
    if(id==='node:fs') return {...fs,existsSync:file=>contents.has(file)||fs.existsSync(file),
      writeFileSync:()=>{throw Error('Positive transition fixture must not write files');}};
    if(id==='./small_local_repeat_admission.cjs') return {...small,hashFile,read,rows};
    return nativeRequire(id);
  };
  isolated._compile(fs.readFileSync(filename,'utf8'),filename);
  const controller=isolated.exports;
  const approved={...controller.expectedProposal(state),status:'approved',approval:{
    authorized_by_root:true,independent_review:true,reviewer:'root',reviewed_utc:'2026-10-06T12:00:00.000Z'}};
  put(controller.PROPOSAL,approved);
  const ctx=controller.verifyProposal(),config=ctx.plan.configurations[controller.ID];
  const base=path.join(controller.OUTPUT,'positive-transition-fixture');
  const files=controller.stagePaths(controller.ID,'fresh2','P0',stage,base);
  const phase=`${controller.ID}/fresh2/P0`,count=stage==='smoke'?3:60;
  const priorReview=small.read(controller.blockedPaths().review);
  const priorPreflight=small.read(path.join(controller.ROOT,priorReview.runtime_preflight_file));
  const seed=small.rows(controller.blockedPaths().raw)[0].result;
  const candidateFile=path.join(files.folder,`${stage}.candidate.json`);
  const reviewFile=path.join(files.folder,`${stage}.root-review.json`);
  const runtimeFile=path.join(files.folder,`${stage}.runtime-preflight.json`);
  const measured=config.conditions.P0.requests.map(request=>({id:request.id,
    instance_reference:priorReview.runtime_token_preflight.observed_instance_reference,
    request_sha256:request.sha256,rendered_sha256:request.rendered_sha256,
    prompt_tokens:request.prompt_tokens,artifact_sha256:config.artifact_sha256}));
  put(runtimeFile,{phase,stage,runtime:priorPreflight.runtime,measurements:measured});
  const review={...priorReview,kind:controller.SCHEMA+'-stage-root-review',
    proposal_sha256:ctx.proposalSha,controller_sha256:ctx.proposal.frozen.continuation_controller.sha256,
    prior_manifest_sha256:ctx.proposal.frozen.prior_manifest.sha256,
    blocked_completion_sha256:ctx.proposal.scope.blocked_phase.bindings.completion.sha256,
    prior_blocked_completion_sha256:ctx.proposal.scope.prior_blocked_phase.bindings.completion.sha256,
    previous_proposal_sha256:ctx.proposal.frozen.previous_proposal.sha256,
    phase,stage,ids:controller.IDS.slice(0,count),
    request_sha256:config.conditions.P0.requests.slice(0,count).map(x=>x.sha256),
    candidate_file:path.relative(controller.ROOT,candidateFile),
    runtime_preflight_file:path.relative(controller.ROOT,runtimeFile),runtime_preflight_sha256:hashFile(runtimeFile),
    runtime_token_preflight:{...priorReview.runtime_token_preflight,
      requests_sha256:digest(JSON.stringify(config.conditions.P0.requests)),
      observed_preflight_sha256:digest(JSON.stringify(measured))}};
  delete review.candidate_sha256;
  put(candidateFile,{...review,approved:false,authorized_by_root:false,reviewer:null,reviewed_utc:null});
  review.candidate_sha256=hashFile(candidateFile);put(reviewFile,review);
  const saved=[],raw=[],journal=[];
  for(let i=0;i<count;i++){
    const id=controller.IDS[i],request=config.conditions.P0.requests[i],result=structuredClone(seed);
    const attempt_id=`synthetic-${stage}-${i}`;result.stats.promptTokensCount=request.prompt_tokens;
    const decision=classifier.classifySdk(result,{identifier:config.model_identifier,path:config.artifact_path,
      bytes:config.artifact_bytes,promptTokens:request.prompt_tokens,
      loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config});
    assert.equal(decision.status,'ok','Synthetic result must pass strict SDK classification');
    saved.push({id,attempt_id,request_sha256:request.sha256,reference_labels_read:false,decision});
    raw.push({id,attempt_id,result});
    journal.push({event:'started',id,attempt_id,request_sha256:request.sha256},
      {event:'finished',id,attempt_id,status:decision.status});
  }
  for(const [key,value] of Object.entries({records:saved,raw,journal}))
    put(files[key],value.map(x=>JSON.stringify(x)).join('\n')+'\n');
  const completion={phase,stage,status:'completed',attempted:count,saved:count,invalid:0};
  for(const key of ['records','raw','journal'])completion[key+'_sha256']=hashFile(files[key]);
  put(files.completion,completion);
  put(files.claim,{phase,stage,plan_sha256:hashFile(legacy.PLAN),
    controller_sha256:hashFile(path.join(controller.ROOT,'scripts/legacy_qwen_repeat_admission.cjs')),
    receipt_sha256:hashFile(reviewFile),runtime_attestation:priorPreflight.runtime,
    runtime_preflight_sha256:digest(JSON.stringify(measured.slice(0,count).map(({id,...value})=>value))),
    started_utc:review.route_checked_utc});
  const auditFile=path.join(files.folder,`${stage}.host-audit.json`);
  put(auditFile,{schema:controller.SCHEMA+'-host-audit',status:'passed',phase,stage,error:null,
    before:review.host_baseline,after:review.host_baseline,host_check:{host_unchanged:true},
    completion_sha256:hashFile(files.completion),reviewed_receipt_sha256:hashFile(reviewFile)});
  const inspectionFile=path.join(files.folder,'smoke-inspection.json');
  if(stage==='smoke')put(inspectionFile,{kind:'legacy-qwen-three-record-smoke-inspection-v1',
    approved:true,reviewer:'root',reviewed_utc:review.reviewed_utc,reference_labels_sent:false,
    ids:controller.IDS.slice(0,3),raw_sha256:completion.raw_sha256,records_sha256:completion.records_sha256,
    completion_sha256:hashFile(files.completion)});
  return {controller,ctx,base,contents,inspectionFile,auditFile,read,put,hashFile};
}

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

test('approved completed smoke admits development through strict historical admission',()=>{
  const f=positiveTransitionFixture('smoke');
  assert.equal(f.ctx.proposal.status,'approved');
  assert.equal(f.controller.checkContinuationPredecessor(f.ctx.proposal,'fresh2','P0','development',
    {base:f.base,state:f.ctx.state}),f.hashFile(f.inspectionFile));
  f.contents.delete(f.inspectionFile);
  assert.throws(()=>f.controller.checkContinuationPredecessor(f.ctx.proposal,'fresh2','P0','development',
    {base:f.base,state:f.ctx.state}),/Independent smoke inspection missing/);
  assert.equal(fs.existsSync(f.base),false,'Synthetic stage must never reach disk');
});

test('approved completed development unlocks the next scheduled smoke',()=>{
  const f=positiveTransitionFixture('development');
  assert.equal(f.ctx.proposal.status,'approved');
  assert.equal(f.controller.checkContinuationPredecessor(f.ctx.proposal,'fresh3','P1','smoke',
    {base:f.base,state:f.ctx.state}),null);
  f.put(f.auditFile,{...f.read(f.auditFile),status:'failed'});
  assert.throws(()=>f.controller.checkContinuationPredecessor(f.ctx.proposal,'fresh3','P1','smoke',
    {base:f.base,state:f.ctx.state}),/passed/);
  assert.equal(fs.existsSync(f.base),false,'Synthetic stage must never reach disk');
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
