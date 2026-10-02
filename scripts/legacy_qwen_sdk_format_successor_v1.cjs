#!/usr/bin/env node
// Separate admission policy for controlled SDK smoke with intrinsic invalid output.
// The frozen request constructor, predictor, classifier, and stage writer remain unchanged.
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const legacy=require('./legacy_qwen_repeat_admission.cjs');
const small=require('./small_local_repeat_admission.cjs');
const classifier=require('./local_prompt_execution_v1.cjs');

const ROOT=small.ROOT;
const MANIFEST=path.join(ROOT,'results/repeatability-v1/legacy-qwen-sdk-format-successor-v1/manifest.json');
const IDS=['qwen3-0.6b-sdk-thinking-on','qwen3-0.6b-sdk-thinking-off'];
const smokeIds=['DEV-001','DEV-002','DEV-003'];
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const rows=file=>fs.readFileSync(file,'utf8').split('\n').filter(Boolean).map(JSON.parse);
const rel=file=>path.join(ROOT,file);
const hashFile=small.hashFile;
const normalized=fields=>Object.fromEntries((fields||[]).map(x=>[x.key,x.value]).sort((a,b)=>a[0].localeCompare(b[0])));
const inspectionPath=paths=>path.join(paths.folder,'smoke-format-successor-inspection.json');

function verifyManifest(){
  const manifest=read(MANIFEST);
  assert.equal(manifest.schema,'legacy-qwen-sdk-format-successor-v1');
  assert(['offline_prepared_unapproved','approved'].includes(manifest.status));
  if(manifest.status==='approved'){
    assert.equal(manifest.approval?.independent_review,true);
    assert.equal(manifest.approval?.authorized_by_root,true);
    assert.equal(typeof manifest.approval?.reviewer,'string');
    assert(manifest.approval.reviewer.length>0);
    assert.equal(typeof manifest.approval?.reviewed_utc,'string');
    assert(Number.isFinite(Date.parse(manifest.approval.reviewed_utc)));
  }else assert.equal(manifest.approval,null);
  for(const key of ['frozen_plan','frozen_controller','frozen_classifier'])
    assert.equal(hashFile(rel(manifest[key].file)),manifest[key].sha256,`${key} changed`);
  const {plan,sha256:planSha}=legacy.verifyPlan();
  assert.equal(planSha,manifest.frozen_plan.sha256);
  assert.deepEqual(Object.keys(manifest.configurations).sort(),[...IDS].sort());
  for(const id of IDS){
    const frozen=plan.configurations[id],bound=manifest.configurations[id];
    assert.equal(frozen.surface,'lmstudio_sdk');
    assert.deepEqual(bound.schedule,frozen.schedule);
    assert.equal(bound.artifact_sha256,frozen.artifact_sha256);
    assert.deepEqual(bound.load_config,frozen.controls.load_config);
    assert.equal(bound.prediction_config_sha256,small.hash(JSON.stringify(frozen.controls.prediction_config)));
    for(const item of Object.values(manifest.initial_smoke_bindings[id]))
      assert.equal(hashFile(rel(item.file)),item.sha256,`Initial smoke changed: ${item.file}`);
  }
  assert.deepEqual(manifest.policy.accepted_smoke_decisions,['ok','invalid_output']);
  assert.deepEqual(manifest.policy.accepted_invalid_reasons,['non_json','schema']);
  assert.equal(manifest.policy.smoke_replay,false);
  assert.equal(manifest.policy.output_repair,false);
  assert.equal(manifest.policy.references_in_requests,false);
  assert.equal(manifest.policy.native_lock,plan.policy.lock_path);
  return {manifest,manifestSha:hashFile(MANIFEST),plan,planSha};
}

function validateSmokeData({completion,claim,journal,raw,records,config,requestRows}){
  assert.equal(completion.stage,'smoke');
  assert.equal(completion.attempted,3);
  assert.equal(completion.saved,3);
  assert.equal(raw.length,3);
  assert.equal(records.length,3);
  assert.equal(journal.length,6);
  assert.deepEqual(raw.map(x=>x.id),smokeIds);
  assert.deepEqual(records.map(x=>x.id),smokeIds);
  assert.deepEqual(journal.map(x=>x.id),smokeIds.flatMap(x=>[x,x]));
  assert.deepEqual(journal.map(x=>x.event),['started','finished','started','finished','started','finished']);
  assert.equal(claim.phase,completion.phase);
  assert.equal(claim.stage,'smoke');
  const instance=claim.runtime_attestation?.load_evidence?.instance_reference;
  assert.equal(typeof instance,'string');
  const expectedLoad=normalized(config.controls.load_config.fields);
  const expectedPrediction=normalized(config.controls.prediction_config.fields);
  let invalid=0;
  const details=[];
  for(let i=0;i<3;i++){
    const rr=raw[i],record=records[i],start=journal[2*i],finish=journal[2*i+1];
    assert.equal(rr.attempt_id,record.attempt_id);
    assert.equal(start.attempt_id,record.attempt_id);
    assert.equal(finish.attempt_id,record.attempt_id);
    assert.equal(finish.status,record.decision.status);
    assert.equal(record.reference_labels_read,false);
    assert.equal(record.request_sha256,requestRows[i].request_sha256);
    assert.equal(start.request_sha256,record.request_sha256);
    assert.equal(rr.error,undefined,'Raw response has a provider or runtime error');
    const result=rr.result,info=result?.modelInfo,stats=result?.stats;
    assert(info && stats && typeof result.content==='string' &&
      typeof result.nonReasoningContent==='string' && typeof result.reasoningContent==='string',
      'Raw SDK transport or content malformed');
    assert.equal(info.instanceReference,instance,'Loaded instance changed');
    assert.equal(info.identifier,config.model_identifier);
    assert.equal(info.path,config.artifact_path);
    assert.equal(info.sizeBytes,config.artifact_bytes);
    assert.equal(info.contextLength,8192);
    assert.equal(info.quantization?.name,'Q4_K_M');
    assert.deepEqual(normalized(result.loadConfig?.fields),expectedLoad);
    assert.deepEqual(normalized(result.predictionConfig?.fields),expectedPrediction);
    assert.equal(stats.promptTokensCount,requestRows[i].prompt_tokens);
    assert(['eosFound','stopStringFound'].includes(stats.stopReason),'Unknown stop reason');
    assert(Number.isInteger(stats.predictedTokensCount) && stats.predictedTokensCount>=0);
    const expected=classifier.classifySdk(result,{identifier:config.model_identifier,
      path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:requestRows[i].prompt_tokens,
      loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config});
    assert.deepEqual(record.decision,expected,'Saved decision differs from frozen classifier');
    assert(['ok','invalid_output'].includes(expected.status),'Non-intrinsic smoke decision');
    if(expected.status==='invalid_output'){
      assert(['non_json','schema'].includes(expected.reason),'Invalid output reason is not admitted');
      invalid++;
    }
    details.push({id:rr.id,status:expected.status,reason:expected.reason??null,
      prompt_tokens:stats.promptTokensCount,stop_reason:stats.stopReason,
      model_instance:info.instanceReference});
  }
  assert.equal(completion.invalid,invalid);
  if(invalid){
    assert.equal(completion.status,'stopped');
    assert.equal(completion.reason,'Smoke has invalid output; development admission refused');
  }else{
    assert.equal(completion.status,'completed');
    assert.equal(completion.reason,null);
  }
  return {invalid,details};
}

function validateSmokeEvidence(plan,id,pass,condition){
  assert(IDS.includes(id));
  const paths=legacy.stagePaths(id,pass,condition,'smoke');
  const completion=read(paths.completion),claim=read(paths.claim);
  assert.equal(completion.phase,`${id}/${pass}/${condition}`);
  const contents={journal:rows(paths.journal),raw:rows(paths.raw),records:rows(paths.records)};
  for(const field of ['journal','raw','records'])
    assert.equal(hashFile(paths[field]),completion[`${field}_sha256`],`Smoke ${field} hash changed`);
  assert.equal(hashFile(path.join(paths.folder,'smoke.root-review.json')),claim.receipt_sha256);
  assert.equal(claim.plan_sha256,hashFile(rel('results/repeatability-v1/legacy-qwen-fresh3-v1/manifest.json')));
  assert.equal(claim.controller_sha256,hashFile(rel('scripts/legacy_qwen_repeat_admission.cjs')));
  const requestRows=legacy.stageRows(plan,id,condition,'smoke').map(row=>({
    request_sha256:small.hash(JSON.stringify(row.request)),prompt_tokens:row.prompt_tokens}));
  const checked=validateSmokeData({completion,claim,...contents,config:plan.configurations[id],requestRows});
  return {paths,completion,claim,...checked,binding:{completion_sha256:hashFile(paths.completion),
    claim_sha256:hashFile(paths.claim),journal_sha256:completion.journal_sha256,
    raw_sha256:completion.raw_sha256,records_sha256:completion.records_sha256}};
}

function inspectionCandidate(plan,id,pass,condition){
  const checked=validateSmokeEvidence(plan,id,pass,condition);
  const original=path.join(checked.paths.folder,'smoke-inspection.json');
  return {kind:'legacy-qwen-sdk-format-successor-inspection-v1',approved:false,
    reviewer:null,reviewed_utc:null,independent_review:false,authorized_by_root:false,
    phase:`${id}/${pass}/${condition}`,stage:'smoke',
    scope:'intrinsic_invalid_output_with_exact_transport_and_controls',
    reference_labels_read:false,semantic_correctness_claimed:false,output_repaired:false,
    smoke_replayed:false,control_and_transport_verified:true,
    intrinsic_invalid_count:checked.invalid,details:checked.details,
    ...(fs.existsSync(original)?{original_inspection_sha256:hashFile(original)}:{}),
    ...checked.binding};
}

function successorPredecessor(plan,id,pass,condition,stage){
  if(stage==='smoke')return legacy.checkPredecessor(plan,id,pass,condition,stage);
  assert.equal(stage,'development');
  // Use the original preceding-phase gate without invoking its all-ok smoke gate.
  legacy.checkPredecessor(plan,id,pass,condition,'smoke');
  const candidate=inspectionCandidate(plan,id,pass,condition);
  const file=inspectionPath(legacy.stagePaths(id,pass,condition,'smoke'));
  const inspection=read(file);
  assert.equal(inspection.approved,true,'Independent successor smoke review missing');
  assert.equal(inspection.independent_review,true);
  assert.equal(inspection.authorized_by_root,true);
  assert.equal(typeof inspection.reviewer,'string');
  assert(inspection.reviewer.length>0);
  assert.equal(typeof inspection.reviewed_utc,'string');
  assert(Number.isFinite(Date.parse(inspection.reviewed_utc)));
  const smokeReceipt=read(path.join(legacy.stagePaths(id,pass,condition,'smoke').folder,'smoke.root-review.json'));
  assert.notEqual(inspection.reviewer,smokeReceipt.reviewer,'Smoke reviewer cannot self-approve successor inspection');
  const reviewed={...inspection,approved:false,reviewer:null,reviewed_utc:null,
    independent_review:false,authorized_by_root:false};
  assert.deepEqual(reviewed,candidate,'Successor inspection differs from current raw evidence');
  return hashFile(file);
}

function checkSuccessorReceipt(receipt,ctx,phase,stage,config,smokeHash){
  assert.equal(receipt.successor_manifest_sha256,ctx.manifestSha);
  assert.equal(receipt.successor_controller_sha256,hashFile(__filename));
  assert.equal(receipt.successor_admission_policy,'legacy-qwen-sdk-format-successor-v1');
  assert.equal(receipt.authorized_by_root,true);
  assert.equal(typeof receipt.reviewer,'string');
  assert(receipt.reviewer.length>0);
  legacy.checkReceipt(receipt,ctx.planSha,phase,stage,config,smokeHash);
}

async function dispatch(ctx,id,pass,condition,stage,receiptPath){
  assert.equal(ctx.manifest.status,'approved','Successor manifest awaits independent review');
  assert(IDS.includes(id));
  legacy.phaseInfo(ctx.plan,id,pass,condition);
  assert(['smoke','development'].includes(stage));
  const paths=legacy.stagePaths(id,pass,condition,stage);
  for(const key of ['claim','journal','raw','records','completion'])
    assert(!fs.existsSync(paths[key]),`Stage already claimed; no replay: ${paths[key]}`);
  const phase=`${id}/${pass}/${condition}`;
  const config=ctx.plan.configurations[id];
  await legacy.runStage(ctx.plan,ctx.planSha,id,pass,condition,stage,receiptPath,{
    predecessor:(_plan,_id,_pass,_condition,_stage)=>successorPredecessor(ctx.plan,id,pass,condition,stage),
    admit:(receipt,planSha,p,s,c,smokeHash)=>{
      assert.equal(planSha,ctx.planSha);
      assert.equal(p,phase);assert.equal(s,stage);assert.equal(c,config);
      checkSuccessorReceipt(receipt,ctx,phase,stage,config,smokeHash);
    }});
}

async function main(args){
  const [action,...rest]=args,ctx=verifyManifest();
  if(action==='verify'){console.log(JSON.stringify({manifest_sha256:ctx.manifestSha,status:ctx.manifest.status,configurations:IDS}));return;}
  if(action==='preview'){
    const [id,pass,condition,stage]=rest;
    assert(IDS.includes(id));legacy.phaseInfo(ctx.plan,id,pass,condition);
    console.log(JSON.stringify({phase:`${id}/${pass}/${condition}`,stage,ids:legacy.stageRows(ctx.plan,id,condition,stage).map(x=>x.id)}));return;
  }
  if(action==='inspect-candidate'){
    const [id,pass,condition]=rest;
    assert(IDS.includes(id));legacy.phaseInfo(ctx.plan,id,pass,condition);
    const file=inspectionPath(legacy.stagePaths(id,pass,condition,'smoke'));
    fs.writeFileSync(file,JSON.stringify(inspectionCandidate(ctx.plan,id,pass,condition),null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify({file,sha256:hashFile(file),approved:false}));return;
  }
  if(action==='run'){
    assert.equal(ctx.manifest.status,'approved','Successor manifest awaits independent review');
    execFileSync('python3',['-c',legacy.lockCode,legacy.LOCK,process.execPath,__filename,'internal-run',...rest],{stdio:'inherit'});return;
  }
  if(action==='internal-run'){
    assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use run for native GPU lock');
    const [id,pass,condition,stage,receipt]=rest;
    assert(id&&pass&&condition&&stage&&receipt,'Require configuration pass condition stage receipt');
    await dispatch(ctx,id,pass,condition,stage,receipt);
    return;
  }
  throw Error('Use verify, preview, inspect-candidate, or run');
}
if(require.main===module)main(process.argv.slice(2)).catch(e=>{console.error(e.stack||e);process.exitCode=1});
module.exports={verifyManifest,validateSmokeData,validateSmokeEvidence,inspectionCandidate,
  successorPredecessor,checkSuccessorReceipt,dispatch,inspectionPath};
