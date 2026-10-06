#!/usr/bin/env node
'use strict';
// Separate continuation after terminal fresh2/P1 host-sleep failure; both prior failures remain frozen.
// The blocked phase is preserved and is never replayed or promoted to development.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const legacy=require('./legacy_qwen_repeat_admission.cjs');
const small=require('./small_local_repeat_admission.cjs');
const hostAdmission=require('./local_host_admission.cjs');
const remaining=require('./qwen35_remaining_phases_v1.cjs');
const suffix=require('./qwen35_p0_unsent_suffix_v1.cjs');
const parent=require('./local_prompt_execution_v1.cjs');
const previous=require('./qwen35_after_smoke_failure_v1.cjs');

const ROOT=small.ROOT;
const ID=remaining.ID;
const SCHEMA='qwen35-after-host-failure-v1';
const PRIOR_OUTPUT=previous.OUTPUT;
const OUTPUT=path.join(ROOT,'results/repeatability-v1/legacy-qwen-fresh3-v1',SCHEMA);
const PROPOSAL=path.join(OUTPUT,'proposal.json');
const REVIEW_CANDIDATE=path.join(OUTPUT,'root-review-candidate.json');
const BLOCKED={pass:'fresh2',condition:'P1'};
const BLOCKED_FOLDER=path.join(PRIOR_OUTPUT,BLOCKED.pass,BLOCKED.condition);
const PHASES=[['fresh2','P0'],['fresh3','P1'],['fresh3','P0'],['fresh3','P2']];
const IDS=remaining.IDS;
const stable=JSON.stringify;
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const hashFile=small.hashFile;
const read=small.read;
const rows=small.rows;
const rel=file=>path.join(ROOT,file);

function sourceBinding(file){
  const full=path.resolve(file);
  assert(full.startsWith(ROOT+path.sep),'Bound file is outside repository');
  assert(fs.existsSync(full),`Bound file missing: ${full}`);
  return {file:path.relative(ROOT,full),sha256:hashFile(full)};
}

function blockedPaths(base=BLOCKED_FOLDER){
  return {review:path.join(base,'smoke.root-review.json'),claim:path.join(base,'smoke.claim.json'),
    journal:path.join(base,'smoke.journal.jsonl'),raw:path.join(base,'smoke.raw.jsonl'),
    records:path.join(base,'smoke.records.jsonl'),completion:path.join(base,'smoke.completion.json'),
    hostAudit:path.join(base,'smoke.host-audit.json')};
}

function verifyBlockedSmoke(plan,{base=BLOCKED_FOLDER,prior=previous.verifyProposal()}={}){
  const files=blockedPaths(base);
  for(const file of Object.values(files)) assert(fs.existsSync(file),`Blocked smoke evidence missing: ${file}`);
  const done=read(files.completion),audit=read(files.hostAudit),review=read(files.review),claim=read(files.claim);
  const raw=rows(files.raw),records=rows(files.records),journal=rows(files.journal);
  const config=plan.configurations[ID],requests=config.conditions.P1.requests.slice(0,3);
  assert.equal(prior.proposal.status,'approved','Previous continuation must be approved');
  assert.equal(done.phase,`${ID}/fresh2/P1`);assert.equal(done.stage,'smoke');
  assert.equal(done.status,'stopped');
  assert.equal(done.reason,`Prediction exceeded ${config.timeout_ms}ms; cancellation requested`);
  assert.equal(done.attempted,3);assert.equal(done.saved,2);assert.equal(done.invalid,0);
  for(const key of ['journal','raw','records'])
    assert.equal(done[`${key}_sha256`],hashFile(files[key]),`${key} hash differs`);
  assert.equal(audit.schema,previous.SCHEMA+'-host-audit');assert.equal(audit.status,'failed');
  assert.equal(audit.phase,done.phase);assert.equal(audit.stage,'smoke');
  assert.equal(audit.completion_sha256,hashFile(files.completion));
  assert.equal(audit.reviewed_receipt_sha256,hashFile(files.review));assert.equal(audit.host_check,null);
  assert.match(audit.error,/^Host slept during stage/);
  assert.equal(audit.after.boot,audit.before.boot);
  assert.equal(audit.after.sleep_wakes,audit.before.sleep_wakes+1);
  assert.deepEqual(audit.before.operational_policy,audit.after.operational_policy);
  assert.throws(()=>hostAdmission.verifyAfterStage(audit.before,audit.after),/Host slept during stage/);
  assert.equal(review.kind,previous.SCHEMA+'-stage-root-review');assert.equal(review.approved,true);
  assert.equal(review.authorized_by_root,true);assert.equal(review.reviewer,'root');
  assert(Number.isFinite(Date.parse(review.reviewed_utc)));
  assert.equal(review.phase,done.phase);assert.equal(review.stage,'smoke');
  assert.deepEqual(review.ids,IDS.slice(0,3));assert.equal(review.reference_labels_read,false);
  assert.deepEqual(review.request_sha256,requests.map(x=>x.sha256));
  assert.equal(review.proposal_sha256,prior.proposalSha);
  assert.equal(review.controller_sha256,prior.proposal.frozen.continuation_controller.sha256);
  assert.equal(review.prior_manifest_sha256,prior.proposal.frozen.prior_manifest.sha256);
  assert.equal(review.blocked_completion_sha256,prior.state.blocked.bindings.completion.sha256);
  assert.equal(review.blocked_phase_clean_credit,false);assert.equal(review.individually_clean_phase,true);
  const candidate=rel(review.candidate_file);
  assert.equal(hashFile(candidate),review.candidate_sha256,'Blocked smoke candidate changed');
  const normalized={...review,approved:false,authorized_by_root:false,reviewer:null,reviewed_utc:null};
  delete normalized.candidate_sha256;assert.deepEqual(normalized,read(candidate));
  for(const key of ['host_baseline_file','runtime_preflight_file','route_catalog_file','route_raw_file'])
    assert.equal(hashFile(rel(review[key])),review[key.replace(/_file$/,'_sha256')],`${key} changed`);
  assert.deepEqual(review.host_baseline,read(rel(review.host_baseline_file)));
  hostAdmission.verifyAfterStage(review.host_baseline,audit.before);
  for(const key of ['model_identifier','artifact_sha256','artifact_bytes']) assert.equal(review[key],config[key]);
  for(const key of ['request_config','load_config','prediction_config'])
    assert.equal(review[`${key}_sha256`],hash(stable(config.controls[key])));
  assert.deepEqual(review.cache_policy,plan.policy.cache_policy);
  assert.equal(review.quantization,'Q4_K_M');assert.equal(review.surface,'lmstudio_sdk');
  assert.equal(review.runtime_token_preflight.request_count,60);
  assert.equal(review.runtime_token_preflight.requests_sha256,hash(stable(config.conditions.P1.requests)));
  const preflight=read(rel(review.runtime_preflight_file));
  assert.equal(preflight.phase,done.phase);assert.equal(preflight.stage,'smoke');
  assert.equal(preflight.measurements.length,60);
  assert.deepEqual(preflight.measurements.map(x=>x.id),IDS);
  for(let i=0;i<60;i++){
    const measured=preflight.measurements[i],request=config.conditions.P1.requests[i];
    assert.equal(measured.request_sha256,request.sha256);
    assert.equal(measured.rendered_sha256,request.rendered_sha256);
    assert.equal(measured.prompt_tokens,request.prompt_tokens);
    assert.equal(measured.artifact_sha256,config.artifact_sha256);
    assert.equal(measured.instance_reference,review.runtime_token_preflight.observed_instance_reference);
  }
  assert.equal(claim.runtime_preflight_sha256,
    hash(stable(preflight.measurements.slice(0,3).map(({id,...measured})=>measured))));
  assert.equal(hash(stable(preflight.measurements)),review.runtime_token_preflight.observed_preflight_sha256);
  // LM Studio appends to the engine log between preflight and dispatch. Its whole-file
  // hash is observational; stable load/cache/instance evidence must remain identical.
  const stableAttestation=value=>{
    const copy=structuredClone(value);assert.match(copy.load_evidence.log_sha256,/^[a-f0-9]{64}$/);
    delete copy.load_evidence.log_sha256;return copy;
  };
  assert.deepEqual(stableAttestation(preflight.runtime),stableAttestation(claim.runtime_attestation));
  assert.equal(claim.runtime_attestation.load_evidence.instance_reference,
    review.runtime_token_preflight.observed_instance_reference);
  const routeAudit=read(rel(review.route_catalog_file));
  assert.equal(review.exact_openrouter_route_absent,true);
  assert.equal(routeAudit.source,'https://openrouter.ai/api/v1/models');
  assert.equal(routeAudit.retrieved_utc,review.route_checked_utc);assert.deepEqual(routeAudit.catalog_matches,[]);
  assert.equal(routeAudit.exact_family_decisions?.['Qwen3.5-4B']?.catalog_id_found,false);
  const routeAge=Date.parse(claim.started_utc)-Date.parse(review.route_checked_utc);
  assert(routeAge>=0&&routeAge<300000,'Prior route was stale at dispatch');
  assert.equal(claim.phase,done.phase);assert.equal(claim.stage,'smoke');
  assert.equal(claim.plan_sha256,hashFile(legacy.PLAN));
  assert.equal(claim.controller_sha256,hashFile(path.join(ROOT,'scripts/legacy_qwen_repeat_admission.cjs')));
  assert.equal(claim.receipt_sha256,hashFile(files.review));
  assert.equal(claim.runtime_attestation.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(claim.runtime_attestation.load_evidence.cache,plan.policy.cache_policy);
  assert.equal(raw.length,3);assert.equal(records.length,2);assert.equal(journal.length,6);
  for(let i=0;i<3;i++){
    const started=journal[2*i],finished=journal[2*i+1];
    assert.equal(started.event,'started');assert.equal(started.id,IDS[i]);
    assert.equal(started.request_sha256,requests[i].sha256);
    assert.equal(finished.id,IDS[i]);assert.equal(finished.attempt_id,started.attempt_id);
    if(i===2){
      assert.equal(finished.event,'stopped_unknown');
      const wire=raw[i];assert.equal(wire.id,IDS[i]);assert.equal(wire.attempt_id,started.attempt_id);
      assert.equal(wire.result,null);assert.equal(wire.code,'PREDICTION_TIMEOUT');
      assert.equal(wire.error,done.reason);assert.equal(wire.cancellationAcknowledged,true);
      assert.equal(wire.partialResult.stats.stopReason,'userStopped');
      assert.equal(wire.partialResult.nonReasoningContent,'');
      const info=wire.partialResult.modelInfo;
      assert.equal(info.identifier,config.model_identifier);assert.equal(info.path,config.artifact_path);
      assert.equal(info.sizeBytes,config.artifact_bytes);assert.equal(info.contextLength,config.context);
      assert.equal(info.quantization.name,'Q4_K_M');
      assert.equal(info.instanceReference,review.runtime_token_preflight.observed_instance_reference);
      const fields=value=>Object.fromEntries(value.fields.map(x=>[x.key,x.value]));
      assert.deepEqual(fields(wire.partialResult.loadConfig),fields(config.controls.load_config));
      assert.deepEqual(fields(wire.partialResult.predictionConfig),fields(config.controls.prediction_config));
      continue;
    }
    const saved=records[i],wire=raw[i];
    assert.equal(wire.id,IDS[i]);assert.equal(saved.id,IDS[i]);
    assert.equal(saved.attempt_id,started.attempt_id);assert.equal(wire.attempt_id,started.attempt_id);
    assert.equal(saved.request_sha256,requests[i].sha256);assert.equal(saved.reference_labels_read,false);
    assert.equal(finished.event,'finished');assert.equal(finished.status,'ok');assert.equal(saved.decision.status,'ok');
    assert.deepEqual(saved.decision,parent.classifySdk(wire.result,{identifier:config.model_identifier,
      path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:requests[i].prompt_tokens,
      loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config}));
  }
  for(const stage of ['smoke','development']){
    const names=stage==='smoke'?['smoke-inspection.json']:['development.claim.json','development.journal.jsonl',
      'development.raw.jsonl','development.records.jsonl','development.completion.json'];
    for(const name of names) assert(!fs.existsSync(path.join(base,name)),`Blocked phase was promoted: ${name}`);
  }
  return {phase:done.phase,status:'host_sleep_blocked',development_admitted:false,replay_authorized:false,
    attempted:3,saved:2,valid:2,invalid:0,unknown:1,unknown_ids:['DEV-003'],clean_repeat_credit:false,
    bindings:Object.fromEntries([...Object.entries(files).map(([name,file])=>[name,sourceBinding(file)]),
      ['candidate',sourceBinding(candidate)],['hostBaseline',sourceBinding(rel(review.host_baseline_file))],
      ['runtimePreflight',sourceBinding(rel(review.runtime_preflight_file))],
      ['routeAudit',sourceBinding(rel(review.route_catalog_file))],['routeRaw',sourceBinding(rel(review.route_raw_file))]])};
}

function schedule(plan){
  const config=plan.configurations[ID];assert(config,'Frozen Qwen3.5 configuration missing');
  return PHASES.map(([pass,condition])=>{
    legacy.phaseInfo(plan,ID,pass,condition);
    const requests=config.conditions[condition].requests;
    assert.deepEqual(requests.map(x=>x.id),IDS);
    return {pass,condition,ids:[...IDS],request_sha256:requests.map(x=>x.sha256),
      rendered_sha256:requests.map(x=>x.rendered_sha256),prompt_tokens:requests.map(x=>x.prompt_tokens),
      stages:['smoke','development']};
  });
}

function predecessorBindings(){
  const result={};
  for(const condition of ['P2','P1']){
    const folder=path.join(remaining.OUTPUT,'fresh1',condition);
    for(const name of ['development.root-review.json','development.claim.json','development.journal.jsonl',
      'development.raw.jsonl','development.records.jsonl','development.completion.json','development.host-audit.json']){
      const binding=sourceBinding(path.join(folder,name));result[`${condition}/${name}`]=binding;
    }
  }
  return result;
}

function verifyFrozenState(){
  const previousCtx=previous.verifyProposal();
  assert.equal(previousCtx.proposal.status,'approved','Previous continuation is not approved');
  const prior=previousCtx.state.prior;
  const blocked=verifyBlockedSmoke(prior.plan,{prior:previousCtx});
  for(const [base,pass,condition] of [[remaining.OUTPUT,'fresh2','P2'],[previous.OUTPUT,'fresh2','P1']]){
    const files=stagePaths(ID,pass,condition,'development',base);remaining.assertUnclaimed(files);
    assert(!fs.existsSync(path.join(files.folder,'development.root-review.json')),
      'A blocked smoke must not have development admission');
  }
  // The new output directory is intentionally excluded: it acquires its own claims after approval.
  for(const [pass,condition] of PHASES) for(const base of [remaining.OUTPUT,previous.OUTPUT])
    for(const stage of ['smoke','development']) remaining.assertUnclaimed(stagePaths(ID,pass,condition,stage,base));
  return {prior,blocked,previous:previousCtx,blockedP2:previousCtx.state.blocked,
    predecessors:previousCtx.state.predecessors};
}

function expectedProposal(state=verifyFrozenState()){
  const {plan}=state.prior,config=plan.configurations[ID];
  return {schema:SCHEMA,status:'offline_prepared_unapproved',approval:null,
    purpose:'continue-untouched-phases-after-terminal-host-sleep-failure',
    inference_authorized:false,reference_labels_read:false,
    scope:{configuration:ID,blocked_phase:state.blocked,prior_blocked_phase:state.blockedP2,phases:schedule(plan)},
    frozen:{previous_proposal:sourceBinding(previous.PROPOSAL),
      previous_controller:sourceBinding(path.join(ROOT,'scripts/qwen35_after_smoke_failure_v1.cjs')),
      plan:sourceBinding(legacy.PLAN),prior_manifest:sourceBinding(remaining.MANIFEST),
      prior_controller:sourceBinding(path.join(ROOT,'scripts/qwen35_remaining_phases_v1.cjs')),
      continuation_controller:sourceBinding(__filename),request_constructor:sourceBinding(path.join(ROOT,'scripts/frozen_prompt_variants.cjs')),
      classifier:sourceBinding(path.join(ROOT,'scripts/local_prompt_execution_v1.cjs')),
      predictor:sourceBinding(path.join(ROOT,'scripts/lmstudio_reasoning_benchmark.cjs')),
      runtime_admission:sourceBinding(path.join(ROOT,'scripts/small_local_repeat_admission.cjs')),
      host_admission:sourceBinding(path.join(ROOT,'scripts/local_host_admission.cjs')),
      completed_predecessors:state.predecessors},
    runtime:{model_identifier:config.model_identifier,artifact_path:config.artifact_path,
      artifact_sha256:config.artifact_sha256,artifact_bytes:config.artifact_bytes,
      quantization:'Q4_K_M',surface:'lmstudio_sdk',context:config.context,
      output_reserve:config.output_reserve,timeout_ms:config.timeout_ms,
      cache_policy:plan.policy.cache_policy,request_config_sha256:hash(stable(config.controls.request_config)),
      load_config_sha256:hash(stable(config.controls.load_config)),
      prediction_config_sha256:hash(stable(config.controls.prediction_config)),
      template_sha256:config.controls.template_sha256,parent_runtime:plan.parent_runtime},
    preflight:{request_count:60,require_live_render_and_token_count:true,
      require_loaded_artifact_hash:true,require_exact_hosted_route_absent:true,
      require_fresh_host_baseline:true,route_freshness_ms:300000},
    policy:{blocked_phase:`${ID}/fresh2/P1`,blocked_phase_status:'host_sleep_blocked',
      prior_blocked_phase:`${ID}/fresh2/P2`,prior_blocked_phase_replay:false,
      prior_blocked_phase_development_admission:false,prior_blocked_phase_clean_credit:false,
      blocked_phase_clean_credit:false,blocked_phase_development_admission:false,
      blocked_smoke_replay:false,unrelated_phase_bypass_only:true,
      invalid_output:'retain_and_continue',service_or_control_failure:'stop_without_retry',
      output_repair:false,controls_unchanged:true,shared_lock:path.relative(ROOT,legacy.LOCK),
      require_independent_root_review:true}};
}

function normalizedProposal(value){
  const copy=structuredClone(value);copy.status='offline_prepared_unapproved';copy.approval=null;return copy;
}

function prepareProposal({proposalPath=PROPOSAL,candidatePath=REVIEW_CANDIDATE,state=verifyFrozenState()}={}){
  assert(!fs.existsSync(proposalPath),'Continuation proposal already exists');
  assert(!fs.existsSync(candidatePath),'Continuation review candidate already exists');
  const proposal=expectedProposal(state);fs.mkdirSync(path.dirname(proposalPath),{recursive:true});
  fs.writeFileSync(proposalPath,JSON.stringify(proposal,null,2)+'\n',{flag:'wx'});
  const candidate={kind:SCHEMA+'-design-root-review',approved:false,authorized_by_root:false,
    independent_review:false,reviewer:null,reviewed_utc:null,
    proposal_sha256:hashFile(proposalPath),controller_sha256:proposal.frozen.continuation_controller.sha256,
    prior_manifest_sha256:proposal.frozen.prior_manifest.sha256,
    blocked_completion_sha256:proposal.scope.blocked_phase.bindings.completion.sha256,
    blocked_phase:proposal.scope.blocked_phase.phase,blocked_status:'host_sleep_blocked',
    prior_blocked_completion_sha256:proposal.scope.prior_blocked_phase.bindings.completion.sha256,
    previous_proposal_sha256:proposal.frozen.previous_proposal.sha256,
    prior_blocked_smoke_replay:false,prior_blocked_development_admission:false,
    blocked_smoke_replay:false,blocked_development_admission:false,
    phases:proposal.scope.phases.map(x=>[x.pass,x.condition]),controls_unchanged:true,
    inference_authorized:false};
  fs.writeFileSync(candidatePath,JSON.stringify(candidate,null,2)+'\n',{flag:'wx'});
  return {proposal_sha256:hashFile(proposalPath),review_candidate_sha256:hashFile(candidatePath)};
}

function verifyProposal(proposalPath=PROPOSAL,state=verifyFrozenState()){
  const proposal=read(proposalPath);
  assert(['offline_prepared_unapproved','approved'].includes(proposal.status));
  if(proposal.status==='approved'){
    assert.equal(proposal.approval?.authorized_by_root,true);
    assert.equal(proposal.approval?.independent_review,true);
    assert.equal(proposal.approval?.reviewer,'root');
    assert(Number.isFinite(Date.parse(proposal.approval?.reviewed_utc)));
  }else assert.equal(proposal.approval,null);
  assert.deepEqual(normalizedProposal(proposal),expectedProposal(state),
    'Continuation proposal differs from frozen sources or terminal smoke');
  return {proposal,proposalSha:hashFile(proposalPath),plan:state.prior.plan,state};
}

function stagePaths(_id,pass,condition,stage,base=OUTPUT){
  return remaining.stagePaths(_id,pass,condition,stage,base);
}

function verifyClosedContinuationStage(files,phase,stage){
  assert(['smoke','development'].includes(stage));
  assert(fs.existsSync(files.completion),stage==='smoke'?'Smoke not complete':`Prior successor phase incomplete: ${phase}`);
  const done=read(files.completion),count=stage==='smoke'?3:60;
  assert.equal(done.phase,phase);assert.equal(done.stage,stage);
  assert.equal(done.status,'completed',stage==='smoke'?'Smoke not complete':`Prior successor phase incomplete: ${phase}`);
  assert.equal(done.attempted,count);assert.equal(done.saved,count);
  for(const key of ['journal','raw','records']){
    assert(fs.existsSync(files[key]),`${stage} ${key} missing`);
    assert.equal(done[`${key}_sha256`],hashFile(files[key]),`${stage} ${key} hash differs`);
  }
  const auditPath=path.join(files.folder,`${stage}.host-audit.json`);
  assert(fs.existsSync(auditPath),`${stage} host audit missing`);
  const audit=read(auditPath);
  assert.equal(audit.schema,SCHEMA+'-host-audit');assert.equal(audit.status,'passed');
  assert.equal(audit.phase,phase);assert.equal(audit.stage,stage);assert.equal(audit.error,null);
  assert.equal(audit.completion_sha256,hashFile(files.completion));
  const reviewPath=path.join(files.folder,`${stage}.root-review.json`);
  assert(fs.existsSync(reviewPath),`${stage} root review missing`);
  assert.equal(audit.reviewed_receipt_sha256,hashFile(reviewPath));
  const review=read(reviewPath),ctx=verifyProposal();
  const match=ctx.proposal.scope.phases.find(x=>`${ID}/${x.pass}/${x.condition}`===phase);
  assert(match,'Closed phase is outside continuation schedule');
  // Recheck historical admission at its recorded route time, without consulting the live host.
  verifyStageReview(ctx,match.pass,match.condition,stage,Date.parse(review.route_checked_utc)+1,
    {base:path.dirname(path.dirname(files.folder)),currentHost:()=>audit.before});
  assert.equal(audit.host_check?.host_unchanged,true);
  hostAdmission.verifyAfterStage(audit.before,audit.after);
  const claim=read(files.claim),config=ctx.plan.configurations[ID];
  assert.equal(claim.phase,phase);assert.equal(claim.stage,stage);
  assert.equal(claim.plan_sha256,hashFile(legacy.PLAN));
  assert.equal(claim.controller_sha256,hashFile(path.join(ROOT,'scripts/legacy_qwen_repeat_admission.cjs')));
  assert.equal(claim.receipt_sha256,hashFile(reviewPath));
  assert.equal(claim.runtime_attestation.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(claim.runtime_attestation.load_evidence.cache,ctx.plan.policy.cache_policy);
  const records=rows(files.records),raw=rows(files.raw),journal=rows(files.journal);
  assert.equal(records.length,count);assert.equal(raw.length,count);assert.equal(journal.length,count*2);
  const requests=config.conditions[match.condition].requests.slice(0,count);
  for(let i=0;i<count;i++){
    const saved=records[i],wire=raw[i],started=journal[2*i],finished=journal[2*i+1];
    assert.equal(saved.id,IDS[i]);assert.equal(wire.id,IDS[i]);assert.equal(saved.attempt_id,wire.attempt_id);
    assert.equal(saved.request_sha256,requests[i].sha256);assert.equal(saved.reference_labels_read,false);
    assert.equal(started.event,'started');assert.equal(finished.event,'finished');
    assert.equal(started.id,IDS[i]);assert.equal(finished.id,IDS[i]);
    assert.equal(started.attempt_id,wire.attempt_id);assert.equal(finished.attempt_id,wire.attempt_id);
    assert.equal(started.request_sha256,requests[i].sha256);assert.equal(finished.status,saved.decision.status);
    assert(['ok','invalid_output'].includes(saved.decision.status));
    assert.deepEqual(saved.decision,parent.classifySdk(wire.result,{identifier:config.model_identifier,
      path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:requests[i].prompt_tokens,
      loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config}));
  }
  assert.equal(done.invalid,records.filter(x=>x.decision.status==='invalid_output').length);
  if(stage==='smoke'){
    const inspectionPath=path.join(files.folder,'smoke-inspection.json');
    assert(fs.existsSync(inspectionPath),'Independent smoke inspection missing');
    const inspection=read(inspectionPath);
    assert.equal(inspection.kind,'legacy-qwen-three-record-smoke-inspection-v1');
    assert.equal(inspection.approved,true);assert.equal(inspection.reviewer,'root');
    assert(Number.isFinite(Date.parse(inspection.reviewed_utc)));assert.equal(inspection.reference_labels_sent,false);
    assert.deepEqual(inspection.ids,IDS.slice(0,3));assert.equal(inspection.raw_sha256,done.raw_sha256);
    assert.equal(inspection.records_sha256,done.records_sha256);
    assert.equal(inspection.completion_sha256,hashFile(files.completion));
    assert.deepEqual(rows(files.records).map(x=>x.decision.status),['ok','ok','ok']);
    return hashFile(inspectionPath);
  }
  return hashFile(files.completion);
}

function checkContinuationPredecessor(proposal,pass,condition,stage,{base=OUTPUT,state=verifyFrozenState()}={}){
  assert(['smoke','development'].includes(stage));
  assert.equal(state.blocked.status,'host_sleep_blocked');
  assert.equal(state.blockedP2.status,'smoke_blocked');assert.equal(state.blockedP2.replay_authorized,false);assert.equal(state.blocked.replay_authorized,false);
  const phases=proposal.scope.phases,index=phases.findIndex(x=>x.pass===pass&&x.condition===condition);
  assert(index>=0,'Phase is outside post-failure schedule');
  assert(!(pass===BLOCKED.pass&&condition===BLOCKED.condition),'Blocked phase cannot be replayed');
  for(let i=0;i<index;i++){
    const prior=phases[i],phase=`${ID}/${prior.pass}/${prior.condition}`;
    verifyClosedContinuationStage(stagePaths(ID,prior.pass,prior.condition,'development',base),phase,'development');
  }
  if(stage==='smoke') return null;
  return verifyClosedContinuationStage(stagePaths(ID,pass,condition,'smoke',base),
    `${ID}/${pass}/${condition}`,'smoke');
}

async function verifyAllRequests(runtime,plan,condition){
  return remaining.verifyAllRequests(runtime,plan,condition);
}
function stamp(now=new Date()){return now.toISOString().replace(/[-:.]/g,'');}

async function preflightCandidate(ctx=verifyProposal(),pass,condition,stage,deps={}){
  assert.equal(ctx.proposal.status,'approved','Continuation proposal awaits independent root approval');
  if(Object.keys(deps).length===0) assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use locked preflight command');
  checkContinuationPredecessor(ctx.proposal,pass,condition,stage,{base:deps.base||OUTPUT,state:ctx.state});
  const p=stagePaths(ID,pass,condition,stage,deps.base||OUTPUT);remaining.assertUnclaimed(p);
  const host=(deps.currentHost||hostAdmission.currentHost)();
  const config=ctx.plan.configurations[ID];
  const runtime=await (deps.runtime||small.realRuntime)(ctx.plan,config);
  const measured=await (deps.verifyAll||verifyAllRequests)(runtime,ctx.plan,condition);
  assert.equal(measured.length,60,'All 60 requests require live render/token checks');
  const route=await (deps.routeEvidence||suffix.fetchRouteEvidence)();
  fs.mkdirSync(p.folder,{recursive:true});
  const prefix=path.join(p.folder,`${stage}-${stamp()}`);
  const hostFile=prefix+'.host-baseline.json',runtimeFile=prefix+'.runtime-preflight.json';
  const routeRawFile=prefix+'.route.raw.json',routeAuditFile=prefix+'.route.audit.json';
  const candidateFile=prefix+'.root-review-candidate.json';
  fs.writeFileSync(hostFile,JSON.stringify(host,null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(runtimeFile,JSON.stringify({phase:`${ID}/${pass}/${condition}`,stage,
    runtime:runtime.attestation,measurements:measured},null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(routeRawFile,route.raw,{flag:'wx'});
  fs.writeFileSync(routeAuditFile,JSON.stringify(route.audit,null,2)+'\n',{flag:'wx'});
  const phase=ctx.proposal.scope.phases.find(x=>x.pass===pass&&x.condition===condition);
  const candidate={kind:SCHEMA+'-stage-root-review',approved:false,authorized_by_root:false,
    reviewer:null,reviewed_utc:null,candidate_file:path.relative(ROOT,candidateFile),
    proposal_sha256:ctx.proposalSha,controller_sha256:ctx.proposal.frozen.continuation_controller.sha256,
    prior_manifest_sha256:ctx.proposal.frozen.prior_manifest.sha256,
    blocked_completion_sha256:ctx.proposal.scope.blocked_phase.bindings.completion.sha256,
    prior_blocked_completion_sha256:ctx.proposal.scope.prior_blocked_phase.bindings.completion.sha256,
    previous_proposal_sha256:ctx.proposal.frozen.previous_proposal.sha256,
    phase:`${ID}/${pass}/${condition}`,stage,ids:stage==='smoke'?IDS.slice(0,3):IDS,
    request_sha256:stage==='smoke'?phase.request_sha256.slice(0,3):phase.request_sha256,
    model_identifier:config.model_identifier,artifact_sha256:config.artifact_sha256,
    artifact_bytes:config.artifact_bytes,quantization:'Q4_K_M',surface:'lmstudio_sdk',
    request_config_sha256:ctx.proposal.runtime.request_config_sha256,
    load_config_sha256:ctx.proposal.runtime.load_config_sha256,
    prediction_config_sha256:ctx.proposal.runtime.prediction_config_sha256,
    cache_policy:ctx.proposal.runtime.cache_policy,reference_labels_read:false,
    blocked_phase_clean_credit:false,individually_clean_phase:true,
    host_baseline_file:path.relative(ROOT,hostFile),host_baseline_sha256:hashFile(hostFile),host_baseline:host,
    runtime_preflight_file:path.relative(ROOT,runtimeFile),runtime_preflight_sha256:hashFile(runtimeFile),
    runtime_token_preflight:{request_count:60,requests_sha256:hash(stable(config.conditions[condition].requests)),
      observed_preflight_sha256:hash(stable(measured)),observed_instance_reference:runtime.instance},
    exact_openrouter_route_absent:true,route_catalog_file:path.relative(ROOT,routeAuditFile),
    route_catalog_sha256:hashFile(routeAuditFile),route_raw_file:path.relative(ROOT,routeRawFile),
    route_raw_sha256:hashFile(routeRawFile),route_checked_utc:route.audit.retrieved_utc};
  fs.writeFileSync(candidateFile,JSON.stringify(candidate,null,2)+'\n',{flag:'wx'});
  return {candidate:path.relative(ROOT,candidateFile),candidate_sha256:hashFile(candidateFile),
    requests_checked:60,phase:candidate.phase,stage,approved:false};
}

function verifyStageReview(ctx,pass,condition,stage,now=Date.now(),deps={}){
  const p=stagePaths(ID,pass,condition,stage,deps.base||OUTPUT);
  const reviewPath=path.join(p.folder,`${stage}.root-review.json`),receipt=read(reviewPath);
  assert.equal(receipt.kind,SCHEMA+'-stage-root-review');assert.equal(receipt.approved,true);
  assert.equal(receipt.authorized_by_root,true);assert.equal(receipt.reviewer,'root');
  assert(Number.isFinite(Date.parse(receipt.reviewed_utc)));
  const candidate=read(rel(receipt.candidate_file));assert.equal(hashFile(rel(receipt.candidate_file)),receipt.candidate_sha256);
  const normalized={...receipt,approved:false,authorized_by_root:false,reviewer:null,reviewed_utc:null};
  delete normalized.candidate_sha256;assert.deepEqual(normalized,candidate,'Reviewed stage receipt differs from candidate');
  assert.equal(receipt.proposal_sha256,ctx.proposalSha);
  assert.equal(receipt.controller_sha256,ctx.proposal.frozen.continuation_controller.sha256);
  assert.equal(receipt.prior_manifest_sha256,ctx.proposal.frozen.prior_manifest.sha256);
  assert.equal(receipt.blocked_completion_sha256,ctx.proposal.scope.blocked_phase.bindings.completion.sha256);
  assert.equal(receipt.prior_blocked_completion_sha256,ctx.proposal.scope.prior_blocked_phase.bindings.completion.sha256);
  assert.equal(receipt.previous_proposal_sha256,ctx.proposal.frozen.previous_proposal.sha256);
  assert.equal(receipt.phase,`${ID}/${pass}/${condition}`);assert.equal(receipt.stage,stage);
  const config=ctx.plan.configurations[ID],scheduled=ctx.proposal.scope.phases.find(x=>x.pass===pass&&x.condition===condition);
  assert(scheduled,'Reviewed stage is outside post-failure schedule');
  assert.deepEqual(receipt.ids,stage==='smoke'?IDS.slice(0,3):IDS);
  assert.deepEqual(receipt.request_sha256,stage==='smoke'?scheduled.request_sha256.slice(0,3):scheduled.request_sha256);
  assert.equal(receipt.model_identifier,config.model_identifier);assert.equal(receipt.artifact_sha256,config.artifact_sha256);
  assert.equal(receipt.artifact_bytes,config.artifact_bytes);assert.equal(receipt.quantization,'Q4_K_M');
  assert.equal(receipt.surface,'lmstudio_sdk');assert.equal(receipt.reference_labels_read,false);
  assert.equal(receipt.request_config_sha256,ctx.proposal.runtime.request_config_sha256);
  assert.equal(receipt.load_config_sha256,ctx.proposal.runtime.load_config_sha256);
  assert.equal(receipt.prediction_config_sha256,ctx.proposal.runtime.prediction_config_sha256);
  assert.deepEqual(receipt.cache_policy,ctx.proposal.runtime.cache_policy);
  assert.equal(receipt.blocked_phase_clean_credit,false);assert.equal(receipt.individually_clean_phase,true);
  assert.equal(receipt.runtime_token_preflight?.request_count,60);
  assert.equal(receipt.runtime_token_preflight?.requests_sha256,hash(stable(config.conditions[condition].requests)));
  assert.equal(receipt.exact_openrouter_route_absent,true);
  for(const key of ['host_baseline_file','runtime_preflight_file','route_catalog_file','route_raw_file'])
    assert.equal(hashFile(rel(receipt[key])),receipt[key.replace(/_file$/,'_sha256')],`${key} changed`);
  const age=now-Date.parse(receipt.route_checked_utc);assert(age>=0&&age<300000,'Route attestation must be fresh (five minutes)');
  const routeAudit=read(rel(receipt.route_catalog_file));
  assert.equal(routeAudit.source,'https://openrouter.ai/api/v1/models');assert.deepEqual(routeAudit.catalog_matches,[]);
  assert.equal(routeAudit.exact_family_decisions?.['Qwen3.5-4B']?.catalog_id_found,false);
  assert.equal(routeAudit.retrieved_utc,receipt.route_checked_utc);
  const current=(deps.currentHost||hostAdmission.currentHost)();hostAdmission.verifyAfterStage(receipt.host_baseline,current);
  return {receipt,reviewPath,current,paths:p};
}

async function runContinuationStage(proposalSha,pass,condition,stage,deps={}){
  if(!deps.ctx) assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use run to acquire shared native host lock');
  const ctx=deps.ctx||verifyProposal();assert.equal(ctx.proposalSha,proposalSha,'Approved proposal hash differs');
  assert.equal(ctx.proposal.status,'approved','Continuation proposal awaits independent root approval');
  checkContinuationPredecessor(ctx.proposal,pass,condition,stage,{base:deps.base||OUTPUT,state:ctx.state});
  const admitted=(deps.verifyStageReview||verifyStageReview)(ctx,pass,condition,stage,Date.now(),deps);
  remaining.assertUnclaimed(admitted.paths);
  const config=ctx.plan.configurations[ID],runtime=await (deps.runtime||small.realRuntime)(ctx.plan,config);
  const measured=await (deps.verifyAll||verifyAllRequests)(runtime,ctx.plan,condition);
  assert.equal(hash(stable(measured)),admitted.receipt.runtime_token_preflight.observed_preflight_sha256,
    'Runtime render/token preflight changed since root review');
  assert.equal(runtime.instance,admitted.receipt.runtime_token_preflight.observed_instance_reference,
    'Loaded model instance changed since root review');
  const checkRoute=deps.routeAudit||remaining.checkExactLiveRoute,route=await checkRoute();let supplied=false;
  let completion,error;
  try{
    completion=await legacy.runStage(ctx.plan,hashFile(legacy.PLAN),ID,pass,condition,stage,admitted.reviewPath,
      {paths:()=>admitted.paths,predecessor:()=>checkContinuationPredecessor(ctx.proposal,pass,condition,stage,
          {base:deps.base||OUTPUT,state:ctx.state}),admit:r=>assert.deepEqual(r,admitted.receipt),runtime:async()=>runtime,
        routeAudit:async()=>{if(!supplied){supplied=true;return route;}return checkRoute();},
        verifyRequest:deps.verifyRequest||legacy.verifyRequestRuntime,predict:deps.predict});
  }catch(caught){error=caught;}
  let after=null,hostCheck=null,hostError=null;
  try{after=(deps.currentHost||hostAdmission.currentHost)();hostCheck=hostAdmission.verifyAfterStage(admitted.current,after);}
  catch(caught){hostError=caught;}
  const audit={schema:SCHEMA+'-host-audit',status:hostError?'failed':'passed',phase:`${ID}/${pass}/${condition}`,
    stage,before:admitted.current,after,host_check:hostCheck,error:hostError?String(hostError.message):null,
    completion_sha256:fs.existsSync(admitted.paths.completion)?hashFile(admitted.paths.completion):null,
    reviewed_receipt_sha256:hashFile(admitted.reviewPath),finished_utc:new Date().toISOString()};
  fs.writeFileSync(path.join(admitted.paths.folder,`${stage}.host-audit.json`),stable(audit)+'\n',{flag:'wx'});
  if(error) throw error;if(hostError) throw hostError;return completion;
}

async function main(argv){
  const [action,...args]=argv;
  if(action==='preview'){const state=verifyFrozenState();console.log(JSON.stringify(expectedProposal(state),null,2));return;}
  if(action==='prepare'){console.log(JSON.stringify(prepareProposal()));return;}
  if(action==='verify'){const ctx=verifyProposal();console.log(JSON.stringify({status:ctx.proposal.status,
    proposal_sha256:ctx.proposalSha,blocked_phase:ctx.state.blocked.phase}));return;}
  if(action==='preflight-candidate'||action==='run'){
    execFileSync('python3',['-c',legacy.lockCode,legacy.LOCK,process.execPath,__filename,
      action==='run'?'internal-run':'internal-preflight',...args],{stdio:'inherit'});return;
  }
  if(action==='internal-preflight'){
    assert.equal(args.length,3,'Require pass condition stage');
    console.log(JSON.stringify(await preflightCandidate(verifyProposal(),...args)));return;
  }
  if(action==='internal-run'){
    assert.equal(args.length,4,'Require proposal SHA, pass, condition, stage');
    await runContinuationStage(...args);return;
  }
  throw Error('Use preview, prepare, verify, preflight-candidate, or run');
}
if(require.main===module)main(process.argv.slice(2)).catch(error=>{console.error(error.stack||error);process.exitCode=1;});

module.exports={ROOT,ID,SCHEMA,PRIOR_OUTPUT,OUTPUT,PROPOSAL,REVIEW_CANDIDATE,BLOCKED,PHASES,IDS,
  sourceBinding,blockedPaths,verifyBlockedSmoke,schedule,predecessorBindings,verifyFrozenState,
  expectedProposal,prepareProposal,verifyProposal,stagePaths,verifyClosedContinuationStage,checkContinuationPredecessor,
  verifyAllRequests,preflightCandidate,verifyStageReview,runContinuationStage};
