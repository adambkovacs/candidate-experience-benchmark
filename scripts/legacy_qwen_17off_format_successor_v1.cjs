#!/usr/bin/env node
'use strict';
// Exact-phase successor. Frozen requests, classifier, and stage writer remain unchanged.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const legacy=require('./legacy_qwen_repeat_admission.cjs');
const small=require('./small_local_repeat_admission.cjs');
const prior=require('./legacy_qwen_sdk_format_successor_v1.cjs');
const hostAdmission=require('./local_host_admission.cjs');
const ROOT=small.ROOT,ID='qwen3-1.7b-sdk-thinking-off',PASS='fresh3',CONDITION='P2';
const PHASE=`${ID}/${PASS}/${CONDITION}`,STAGE='development';
const DIR=path.join(ROOT,'results/repeatability-v1/legacy-qwen-17off-format-successor-v1');
const MANIFEST=path.join(DIR,'manifest.json');
const INSPECTION_CANDIDATE=path.join(DIR,'smoke-inspection-candidate.json');
const INSPECTION=path.join(DIR,'smoke-inspection.json');
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const rows=file=>fs.readFileSync(file,'utf8').trim().split('\n').map(JSON.parse);
const hashFile=small.hashFile,rel=file=>path.join(ROOT,file);
const smokePaths=()=>legacy.stagePaths(ID,PASS,CONDITION,'smoke');
function receiptCandidatePath(stamp){
  assert.match(stamp,/^\d{8}T\d{9}Z$/,'Invalid preflight timestamp');
  return path.join(DIR,`development-receipt-candidate-${stamp}.json`);
}
function receiptCandidateFromReview(receipt){
  const relative=receipt.successor_candidate_file;
  assert.match(relative,
    /^results\/repeatability-v1\/legacy-qwen-17off-format-successor-v1\/development-receipt-candidate-\d{8}T\d{9}Z\.json$/);
  return rel(relative);
}

function assertScope(id,pass,condition,stage){
  assert.equal(id,ID,'Configuration outside successor scope');
  assert.equal(pass,PASS,'Pass outside successor scope');
  assert.equal(condition,CONDITION,'Condition outside successor scope');
  assert.equal(stage,STAGE,'Stage outside successor scope');
}
function verifyManifest(){
  const manifest=read(MANIFEST);
  assert.equal(manifest.schema,'legacy-qwen-17off-format-successor-v1');
  assert(['offline_prepared_unapproved','approved'].includes(manifest.status));
  assert.deepEqual(manifest.scope,{configuration:ID,pass:PASS,condition:CONDITION,stage:STAGE});
  if(manifest.status==='approved'){
    assert.equal(manifest.approval?.independent_review,true);
    assert.equal(manifest.approval?.authorized_by_root,true);
    assert.equal(typeof manifest.approval?.reviewer,'string');
    assert(manifest.approval.reviewer.length>0);
    assert(Number.isFinite(Date.parse(manifest.approval.reviewed_utc)));
  }else assert.equal(manifest.approval,null);
  for(const key of ['frozen_plan','frozen_controller','frozen_classifier'])
    assert.equal(hashFile(rel(manifest[key].file)),manifest[key].sha256,`${key} changed`);
  const {plan,sha256:planSha}=legacy.verifyPlan(),config=plan.configurations[ID];
  assert.equal(planSha,manifest.frozen_plan.sha256);
  assert.equal(config.surface,'lmstudio_sdk');
  assert.equal(config.artifact_sha256,manifest.artifact_sha256);
  assert.equal(small.hash(JSON.stringify(config.controls.prediction_config)),manifest.prediction_config_sha256);
  legacy.phaseInfo(plan,ID,PASS,CONDITION);
  assert.deepEqual(manifest.policy,{accepted_smoke_decisions:['ok','invalid_output'],
    accepted_invalid_reasons:['non_json','schema'],smoke_replay:false,output_repair:false,
    references_in_requests:false,native_lock:plan.policy.lock_path});
  const p=smokePaths();
  for(const [key,digest] of Object.entries(manifest.initial_smoke_bindings)){
    const file=key==='review'?path.join(p.folder,'smoke.root-review.json'):p[key];
    assert.equal(hashFile(file),digest,`Retained smoke ${key} changed`);
  }
  return {manifest,manifestSha:hashFile(MANIFEST),plan,planSha};
}
function validateSmokeEvidence(ctx){
  const p=smokePaths(),completion=read(p.completion),claim=read(p.claim);
  assert.equal(completion.phase,PHASE);assert.equal(claim.phase,PHASE);
  assert.equal(completion.status,'stopped');
  assert.equal(completion.reason,'Smoke has invalid output; development admission refused');
  assert.equal(claim.plan_sha256,ctx.planSha);
  assert.equal(claim.controller_sha256,ctx.plan.controller_sha256);
  assert.equal(hashFile(path.join(p.folder,'smoke.root-review.json')),claim.receipt_sha256);
  for(const key of ['journal','raw','records'])
    assert.equal(hashFile(p[key]),completion[`${key}_sha256`]);
  const requestRows=legacy.stageRows(ctx.plan,ID,CONDITION,'smoke').map(row=>({
    request_sha256:small.hash(JSON.stringify(row.request)),prompt_tokens:row.prompt_tokens}));
  const checked=prior.validateSmokeData({completion,claim,journal:rows(p.journal),raw:rows(p.raw),
    records:rows(p.records),config:ctx.plan.configurations[ID],requestRows});
  assert.equal(checked.invalid,1);
  assert.deepEqual(checked.details.map(x=>[x.id,x.status,x.reason]),[
    ['DEV-001','ok',null],['DEV-002','ok',null],['DEV-003','invalid_output','non_json']]);
  return {...checked,binding:{review_sha256:hashFile(path.join(p.folder,'smoke.root-review.json')),
    completion_sha256:hashFile(p.completion),claim_sha256:hashFile(p.claim),
    journal_sha256:hashFile(p.journal),raw_sha256:hashFile(p.raw),records_sha256:hashFile(p.records)}};
}
function inspectionCandidate(ctx){
  const checked=validateSmokeEvidence(ctx);
  return {kind:'legacy-qwen-17off-format-successor-inspection-v1',phase:PHASE,stage:'smoke',
    approved:false,reviewer:null,reviewed_utc:null,independent_review:false,
    authorized_by_root:false,scope:'intrinsic_invalid_output_with_exact_transport_and_controls',
    reference_labels_read:false,semantic_correctness_claimed:false,output_repaired:false,
    smoke_replayed:false,control_and_transport_verified:true,
    intrinsic_invalid_count:checked.invalid,details:checked.details,...checked.binding};
}
function successorPredecessor(ctx){
  legacy.checkPredecessor(ctx.plan,ID,PASS,CONDITION,'smoke');
  const inspection=read(INSPECTION),candidate=inspectionCandidate(ctx);
  assert.equal(inspection.approved,true,'Independent smoke inspection missing');
  assert.equal(inspection.independent_review,true);
  assert.equal(inspection.authorized_by_root,true);
  assert.equal(typeof inspection.reviewer,'string');assert(inspection.reviewer.length>0);
  assert(Number.isFinite(Date.parse(inspection.reviewed_utc)));
  assert.notEqual(inspection.reviewer,read(path.join(smokePaths().folder,'smoke.root-review.json')).reviewer,
    'Smoke reviewer cannot self-approve successor inspection');
  assert.deepEqual({...inspection,approved:false,reviewer:null,reviewed_utc:null,
    independent_review:false,authorized_by_root:false},candidate,'Inspection differs from raw evidence');
  return hashFile(INSPECTION);
}
function checkSuccessorReceipt(receipt,ctx,smokeHash){
  const candidate=read(receiptCandidateFromReview(receipt));
  assert.equal(receipt.authorized_by_root,true);
  assert.equal(typeof receipt.reviewer,'string');assert(receipt.reviewer.length>0);
  assert(Number.isFinite(Date.parse(receipt.reviewed_utc)));
  assert.deepEqual({...receipt,approved:false,reviewer:null,reviewed_utc:null,
    authorized_by_root:false},candidate,'Development receipt differs from candidate');
  assert.equal(receipt.successor_manifest_sha256,ctx.manifestSha);
  assert.equal(receipt.successor_controller_sha256,hashFile(__filename));
  assert.equal(receipt.successor_admission_policy,'legacy-qwen-17off-format-successor-v1');
  legacy.checkReceipt(receipt,ctx.planSha,PHASE,STAGE,ctx.plan.configurations[ID],smokeHash);
}
async function dispatch(ctx,id,pass,condition,stage,receiptPath){
  assertScope(id,pass,condition,stage);
  assert.equal(ctx.manifest.status,'approved','Successor manifest awaits independent review');
  const p=legacy.stagePaths(id,pass,condition,stage);
  for(const key of ['claim','journal','raw','records','completion'])
    assert(!fs.existsSync(p[key]),`Stage already claimed; no replay: ${p[key]}`);
  await legacy.runStage(ctx.plan,ctx.planSha,id,pass,condition,stage,receiptPath,{
    predecessor:()=>successorPredecessor(ctx),
    admit:(receipt,planSha,phase,actualStage,config,smokeHash)=>{
      assert.equal(planSha,ctx.planSha);assert.equal(phase,PHASE);assert.equal(actualStage,STAGE);
      assert.equal(config,ctx.plan.configurations[ID]);
      checkSuccessorReceipt(receipt,ctx,smokeHash);
    }});
}
async function preflightCandidate(ctx){
  assert.equal(ctx.manifest.status,'approved','Successor manifest awaits independent review');
  const smokeHash=successorPredecessor(ctx),p=legacy.stagePaths(ID,PASS,CONDITION,STAGE);
  assert(!fs.existsSync(p.claim)&&!fs.existsSync(p.completion),'Development already attempted');
  const config=ctx.plan.configurations[ID],host=hostAdmission.currentHost();
  const runtime=await small.realRuntime(ctx.plan,config);
  const measured=[];
  for(const row of legacy.stageRows(ctx.plan,ID,CONDITION,STAGE))
    measured.push(await legacy.verifyRequestRuntime(runtime,config,row));
  const response=await fetch('https://openrouter.ai/api/v1/models',
    {signal:AbortSignal.timeout(15000),headers:{accept:'application/json'}});
  assert.equal(response.status,200,'Live route audit unavailable');
  const raw=await response.text(),body=JSON.parse(raw);
  assert(Array.isArray(body.data)&&body.data.length>=100,'Live route catalog incomplete');
  const families={'Qwen3-0.6B':'qwen306b','Qwen3-1.7B':'qwen317b','Qwen3.5-4B':'qwen354b'};
  const matches=body.data.filter(m=>Object.values(families).some(f=>
    [m.id,m.name,m.canonical_slug,m.hugging_face_id].some(v=>typeof v==='string'&&
      v.toLowerCase().replace(/[^a-z0-9]/g,'').includes(f))));
  assert.equal(matches.length,0,'Hosted route requires review');
  const stamp=new Date().toISOString().replace(/[-:.]/g,'');
  const candidateFile=receiptCandidatePath(stamp);
  assert(!fs.existsSync(candidateFile),'Preflight candidate already exists');
  const auditDir=`results/route-audits/qwen17off-fresh3-P2-development-successor-${stamp}`;
  fs.mkdirSync(rel(auditDir),{recursive:true});
  fs.writeFileSync(rel(auditDir+'/catalog.raw.json'),raw,{flag:'wx'});
  const audit={source:'https://openrouter.ai/api/v1/models',retrieved_utc:new Date().toISOString(),
    http_status:200,raw_sha256:small.hash(raw),model_count:body.data.length,catalog_matches:matches,
    exact_family_decisions:Object.fromEntries(Object.keys(families).map(f=>[f,
      {catalog_id_found:false,matching_ids:[],endpoint_query:'not_applicable_no_catalog_id'}]))};
  fs.writeFileSync(rel(auditDir+'/catalog-audit.json'),JSON.stringify(audit,null,2)+'\n',{flag:'wx'});
  const preflightFile=`results/repeatability-v1/legacy-qwen-17off-format-successor-v1/development-preflight-${stamp}.json`;
  fs.writeFileSync(rel(preflightFile),JSON.stringify({phase:PHASE,stage:STAGE,host,
    runtime:runtime.attestation,measurements:measured},null,2)+'\n',{flag:'wx'});
  const receipt={kind:'root-reviewed-legacy-qwen-stage-v1',approved:false,reviewer:null,
    reviewed_utc:null,authorized_by_root:false,plan_sha256:ctx.planSha,
    controller_sha256:hashFile(rel('scripts/legacy_qwen_repeat_admission.cjs')),
    phase:PHASE,stage:STAGE,model_identifier:config.model_identifier,
    artifact_sha256:config.artifact_sha256,cache_policy:{enabled:true,size_limit_mib:8192},
    reference_labels_read:false,exact_openrouter_route_absent:true,
    route_catalog_file:auditDir+'/catalog-audit.json',
    route_catalog_sha256:hashFile(rel(auditDir+'/catalog-audit.json')),
    route_checked_utc:audit.retrieved_utc,gpu_available:true,capacity_reviewed:true,
    capacity_evidence:host,preflight_file:preflightFile,preflight_sha256:hashFile(rel(preflightFile)),
    smoke_inspection_sha256:smokeHash,successor_manifest_sha256:ctx.manifestSha,
    successor_controller_sha256:hashFile(__filename),
    successor_admission_policy:'legacy-qwen-17off-format-successor-v1',
    successor_candidate_file:path.relative(ROOT,candidateFile),
    runtime_token_preflight:{phase:PHASE,model_identifier:config.model_identifier,
      artifact_sha256:config.artifact_sha256,context:8192,output_reserve:config.output_reserve,
      request_count:60,requests_sha256:small.hash(JSON.stringify(config.conditions[CONDITION].requests)),
      observed_preflight_sha256:small.hash(JSON.stringify(measured)),
      observed_instance_reference:runtime.instance}};
  fs.writeFileSync(candidateFile,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  return {candidate:candidateFile,phase:PHASE,requests:measured.length,
    routeModels:body.data.length,host:{power_source:host.power_source,battery_percent:host.battery_percent}};
}
async function main(args){
  const [action,...rest]=args,ctx=verifyManifest();
  if(action==='verify'){
    console.log(JSON.stringify({status:ctx.manifest.status,phase:PHASE,
      manifest_sha256:ctx.manifestSha,smoke:validateSmokeEvidence(ctx).details}));return;
  }
  if(action==='inspect-candidate'){
    fs.writeFileSync(INSPECTION_CANDIDATE,JSON.stringify(inspectionCandidate(ctx),null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify({candidate:INSPECTION_CANDIDATE,approved:false,
      sha256:hashFile(INSPECTION_CANDIDATE)}));return;
  }
  if(action==='preflight-candidate'||action==='run'){
    assert.equal(ctx.manifest.status,'approved','Successor manifest awaits independent review');
    execFileSync('python3',['-c',legacy.lockCode,legacy.LOCK,process.execPath,__filename,
      action==='run'?'internal-run':'internal-preflight',...rest],{stdio:'inherit'});return;
  }
  if(action==='internal-preflight'||action==='internal-run'){
    assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use locked public command');
    if(action==='internal-preflight'){console.log(JSON.stringify(await preflightCandidate(ctx)));return;}
    const [id,pass,condition,stage,receipt]=rest;
    assert(receipt,'Require reviewed development receipt path');
    await dispatch(ctx,id,pass,condition,stage,receipt);return;
  }
  throw Error('Use verify, inspect-candidate, preflight-candidate, or run');
}
if(require.main===module)main(process.argv.slice(2)).catch(e=>{console.error(e.stack||e);process.exitCode=1});
module.exports={verifyManifest,assertScope,validateSmokeData:prior.validateSmokeData,
  validateSmokeEvidence,inspectionCandidate,successorPredecessor,checkSuccessorReceipt,
  dispatch,preflightCandidate,receiptCandidatePath,INSPECTION_CANDIDATE,INSPECTION};
