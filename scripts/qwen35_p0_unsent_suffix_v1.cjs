#!/usr/bin/env node
'use strict';
// Offline-prepared continuation for the eight requests never sent after the
// interrupted Qwen3.5 fresh1/P0 development stage. DEV-052 remains unknown.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const legacy=require('./legacy_qwen_repeat_admission.cjs');
const small=require('./small_local_repeat_admission.cjs');
const parent=require('./local_prompt_execution_v1.cjs');
const predictor=require('./lmstudio_reasoning_benchmark.cjs');
const hostAdmission=require('./local_host_admission.cjs');

const ROOT=small.ROOT;
const ID='qwen3.5-4b-sdk-thinking-on';
const PASS='fresh1';
const CONDITION='P0';
const PHASE=`${ID}/${PASS}/${CONDITION}`;
const STAGE='development_suffix';
const SCHEMA='qwen35-p0-unsent-suffix-v1';
const ORIGINAL=path.join(ROOT,'results/repeatability-v1/legacy-qwen-fresh3-v1',ID,PASS,CONDITION);
const OUTPUT=path.join(ROOT,'results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-p0-unsent-suffix-v1');
const MANIFEST=path.join(OUTPUT,'manifest.json');
const REVIEW_CANDIDATE=path.join(OUTPUT,'root-review-candidate.json');
const EXECUTION_REVIEW=path.join(OUTPUT,'suffix.root-review.json');
const IDS=Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);
const SUFFIX_IDS=IDS.slice(52);
const stable=JSON.stringify;
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const hashFile=small.hashFile;
const read=small.read;
const rows=small.rows;
const rel=file=>path.join(ROOT,file);
const durable=(fd,value)=>{fs.writeSync(fd,stable(value)+'\n');fs.fsyncSync(fd);};

function sourceBinding(file){
  const full=path.resolve(file);
  assert(full.startsWith(ROOT+path.sep),'Source outside repository');
  return {file:path.relative(ROOT,full),sha256:hashFile(full)};
}
function outputPaths(base=OUTPUT){
  return {folder:base,claim:path.join(base,'suffix.claim.json'),
    journal:path.join(base,'suffix.journal.jsonl'),raw:path.join(base,'suffix.raw.jsonl'),
    records:path.join(base,'suffix.records.jsonl'),completion:path.join(base,'suffix.completion.json')};
}
function originalFiles(){
  return {claim:path.join(ORIGINAL,'development.claim.json'),
    journal:path.join(ORIGINAL,'development.journal.jsonl'),
    raw:path.join(ORIGINAL,'development.raw.jsonl'),
    records:path.join(ORIGINAL,'development.records.jsonl'),
    completion:path.join(ORIGINAL,'development.completion.json'),
    review:path.join(ORIGINAL,'development.root-review.json'),
    host_audit:path.join(ORIGINAL,'interruption.host-audit.json'),
    interruption_review:path.join(ORIGINAL,'interruption.root-review.json'),
    smoke_claim:path.join(ORIGINAL,'smoke.claim.json'),
    smoke_journal:path.join(ORIGINAL,'smoke.journal.jsonl'),
    smoke_raw:path.join(ORIGINAL,'smoke.raw.jsonl'),
    smoke_records:path.join(ORIGINAL,'smoke.records.jsonl'),
    smoke_completion:path.join(ORIGINAL,'smoke.completion.json'),
    smoke_review:path.join(ORIGINAL,'smoke.root-review.json'),
    smoke_inspection:path.join(ORIGINAL,'smoke-inspection.json')};
}

function verifyOriginalEvidence(plan){
  const files=originalFiles(),config=plan.configurations[ID];
  assert(config,'Frozen Qwen3.5 configuration missing');
  for(const file of Object.values(files)) assert(fs.existsSync(file),`Original evidence missing: ${file}`);
  const planSha=hashFile(legacy.PLAN),controllerSha=hashFile(path.join(ROOT,'scripts/legacy_qwen_repeat_admission.cjs'));
  const claim=read(files.claim),done=read(files.completion),review=read(files.review);
  assert.equal(claim.phase,PHASE);assert.equal(claim.stage,'development');
  assert.equal(claim.plan_sha256,planSha);assert.equal(claim.controller_sha256,controllerSha);
  assert.equal(claim.receipt_sha256,hashFile(files.review));
  assert.equal(claim.runtime_attestation.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(claim.runtime_attestation.load_evidence.cache,plan.policy.cache_policy);
  assert.match(claim.runtime_attestation.loaded,/recruitment-qwen3\.5-4b-q4km\s+qwen3\.5-4b\s+IDLE/);
  assert.equal(done.phase,PHASE);assert.equal(done.stage,'development');
  assert.equal(done.status,'stopped');
  assert.equal(done.reason,'Prediction exceeded 600000ms; cancellation requested');
  assert.equal(done.attempted,52);assert.equal(done.saved,51);assert.equal(done.invalid,7);
  for(const key of ['journal','raw','records']) assert.equal(done[`${key}_sha256`],hashFile(files[key]));
  assert.equal(review.kind,'root-reviewed-legacy-qwen-stage-v1');assert.equal(review.approved,true);
  assert.equal(review.plan_sha256,planSha);assert.equal(review.controller_sha256,controllerSha);
  assert.equal(review.phase,PHASE);assert.equal(review.stage,'development');
  assert.equal(review.model_identifier,config.model_identifier);
  assert.equal(review.artifact_sha256,config.artifact_sha256);
  assert.equal(review.reference_labels_read,false);
  assert.equal(review.runtime_token_preflight.request_count,60);
  assert.equal(review.runtime_token_preflight.requests_sha256,
    hash(stable(config.conditions.P0.requests)));

  const selection=legacy.stageRows(plan,ID,CONDITION,'development');
  const journal=rows(files.journal),raw=rows(files.raw),saved=rows(files.records);
  assert.equal(selection.length,60);assert.equal(journal.length,104);
  assert.equal(raw.length,52);assert.equal(saved.length,51);
  assert.deepEqual(raw.map(x=>x.id),IDS.slice(0,52));
  assert.deepEqual(saved.map(x=>x.id),IDS.slice(0,51));
  const attempts=new Set();let invalid=0;
  for(let i=0;i<52;i++){
    const item=selection[i],sidecar=raw[i],started=journal[2*i],ended=journal[2*i+1];
    assert.equal(item.id,IDS[i]);assert.equal(sidecar.id,item.id);
    assert(typeof sidecar.attempt_id==='string'&&sidecar.attempt_id&&!attempts.has(sidecar.attempt_id));
    attempts.add(sidecar.attempt_id);
    assert.equal(started.event,'started');assert.equal(started.id,item.id);
    assert.equal(started.attempt_id,sidecar.attempt_id);
    assert.equal(started.request_sha256,hash(stable(item.request)));
    assert.equal(ended.id,item.id);assert.equal(ended.attempt_id,sidecar.attempt_id);
    if(i<51){
      const record=saved[i];
      assert.equal(ended.event,'finished');assert.equal(record.id,item.id);
      assert.equal(record.attempt_id,sidecar.attempt_id);
      assert.equal(record.request_sha256,hash(stable(item.request)));
      assert.equal(record.reference_labels_read,false);
      const expected={identifier:config.model_identifier,path:config.artifact_path,
        bytes:config.artifact_bytes,promptTokens:item.prompt_tokens,
        loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config};
      assert.deepEqual(record.decision,parent.classifySdk(sidecar.result,expected));
      assert(['ok','invalid_output'].includes(record.decision.status));
      assert.equal(ended.status,record.decision.status);
      if(record.decision.status==='invalid_output') invalid++;
    }else{
      assert.equal(ended.event,'stopped_unknown');assert.equal(item.id,'DEV-052');
      assert.equal(sidecar.code,'PREDICTION_TIMEOUT');
      assert.equal(sidecar.error,'Prediction exceeded 600000ms; cancellation requested');
      assert.equal(sidecar.cancellationAcknowledged,true);assert(sidecar.partialResult);
      assert.equal(sidecar.result,null);
    }
  }
  assert.equal(invalid,7);

  legacy.checkPredecessor(plan,ID,PASS,CONDITION,'development');
  const smokeDone=read(files.smoke_completion),smokeInspection=read(files.smoke_inspection);
  assert.equal(smokeDone.status,'completed');assert.equal(smokeDone.attempted,3);
  assert.equal(smokeDone.saved,3);assert.equal(smokeDone.invalid,0);
  assert.deepEqual(rows(files.smoke_records).map(x=>x.decision.status),['ok','ok','ok']);
  assert.equal(smokeInspection.approved,true);assert.equal(smokeInspection.reference_labels_sent,false);

  const audit=read(files.host_audit),interruption=read(files.interruption_review);
  assert.equal(audit.schema,'qwen35-interruption-host-audit-v1');
  assert.equal(audit.before.sleep_wakes,92);assert.equal(audit.after.sleep_wakes,93);
  assert.equal(audit.same_boot,true);assert.equal(audit.sleep_count_changed,true);
  assert.equal(audit.after.ac_power,true);assert.equal(audit.after.lid_open,true);
  assert.equal(audit.after.memory_free_percent,80);
  assert.equal(audit.stage_events.length,2);
  assert.match(audit.stage_events[0],/Low Power Sleep.*Using Batt \(Charge:1%\)/);
  assert.match(audit.stage_events[1],/Wake.*Using AC/);
  assert.equal(Date.parse(audit.stage_events[0].slice(0,25)),Date.parse('2026-10-05T20:44:22Z'));
  assert.equal(Date.parse(audit.stage_events[1].slice(0,25)),Date.parse('2026-10-06T07:58:24Z'));
  assert.equal(interruption.schema,'qwen35-interruption-root-review-v1');
  assert.equal(interruption.terminal_exit_code,1);
  assert.equal(interruption.completion_sha256,hashFile(files.completion));
  assert.equal(interruption.host_audit_sha256,hashFile(files.host_audit));
  assert.equal(interruption.saved,51);assert.equal(interruption.valid,44);assert.equal(interruption.invalid,7);
  assert.deepEqual(interruption.unknown_ids,['DEV-052']);
  assert.deepEqual(interruption.never_sent_ids,SUFFIX_IDS);
  assert.equal(interruption.reference_labels_read,false);
  assert.equal(interruption.clean_repeat_eligible,false);assert.equal(interruption.replay_authorized,false);
  assert.equal(interruption.runtime_after_stop,'LM Studio CLI reports exact benchmark model IDLE');
  return {attempted:52,saved:51,valid:44,invalid:7,unknown_ids:['DEV-052'],
    never_sent_ids:SUFFIX_IDS,clean_repeat_eligible:false};
}

function expectedManifest(){
  const {plan}=legacy.verifyPlan(),config=plan.configurations[ID],original=verifyOriginalEvidence(plan);
  const files=originalFiles();
  const originalBindings=Object.fromEntries(Object.entries(files).map(([key,file])=>[key,sourceBinding(file)]));
  const suffixRequests=config.conditions.P0.requests.slice(52);
  assert.deepEqual(suffixRequests.map(x=>x.id),SUFFIX_IDS);
  return {schema:SCHEMA,status:'offline_prepared_unapproved',approval:null,
    method:'descriptive-interrupted-series-unsent-suffix',clean_repeat_eligible:false,
    reference_labels_read:false,scope:{configuration:ID,pass:PASS,condition:CONDITION,stage:STAGE},
    frozen:{plan:sourceBinding(legacy.PLAN),controller:sourceBinding(path.join(ROOT,'scripts/legacy_qwen_repeat_admission.cjs')),
      classifier:sourceBinding(path.join(ROOT,'scripts/local_prompt_execution_v1.cjs')),
      predictor:sourceBinding(path.join(ROOT,'scripts/lmstudio_reasoning_benchmark.cjs')),
      host_admission:sourceBinding(path.join(ROOT,'scripts/local_host_admission.cjs'))},
    controller:sourceBinding(__filename),original:{...original,bindings:originalBindings},
    smoke:{replayed:false,saved:3,valid:3,inspection:originalBindings.smoke_inspection,
      completion:originalBindings.smoke_completion,raw:originalBindings.smoke_raw,
      records:originalBindings.smoke_records},
    suffix:{ids:SUFFIX_IDS,requests:suffixRequests,
      output_files:Object.fromEntries(Object.entries(outputPaths()).filter(([k])=>k!=='folder')
        .map(([k,file])=>[k,path.relative(ROOT,file)]))},
    runtime:{model_identifier:config.model_identifier,artifact_path:config.artifact_path,
      artifact_sha256:config.artifact_sha256,artifact_bytes:config.artifact_bytes,
      quantization:'Q4_K_M',surface:'lmstudio_sdk',timeout_ms:config.timeout_ms,
      context:config.context,output_reserve:config.output_reserve,
      cache_policy:plan.policy.cache_policy,request_config_sha256:hash(stable(config.controls.request_config)),
      load_config_sha256:hash(stable(config.controls.load_config)),
      prediction_config_sha256:hash(stable(config.controls.prediction_config)),
      template_sha256:config.controls.template_sha256,parent_runtime:plan.parent_runtime},
    preflight:{request_count:60,requests_sha256:hash(stable(config.conditions.P0.requests)),
      require_live_render_and_token_count:true,require_loaded_artifact_hash:true,
      require_exact_hosted_route_absent:true,require_fresh_host_baseline:true},
    policy:{unknown_ids:['DEV-052'],never_replay_ids:IDS.slice(0,52),
      no_failed_or_unknown_replay:true,invalid_output:'retain_and_continue',
      service_or_control_failure:'stop_without_retry',smoke_replay:false,
      output_repair:false,shared_lock:path.relative(ROOT,legacy.LOCK),
      continuation_does_not_restore_clean_repeat_credit:true}};
}

function normalizedManifest(manifest){
  const copy=structuredClone(manifest);
  copy.status='offline_prepared_unapproved';copy.approval=null;
  return copy;
}
function verifyManifest(){
  const manifest=read(MANIFEST),expected=expectedManifest();
  assert(['offline_prepared_unapproved','approved'].includes(manifest.status));
  if(manifest.status==='approved'){
    assert.equal(manifest.approval?.independent_review,true);
    assert.equal(manifest.approval?.authorized_by_root,true);
    assert.equal(typeof manifest.approval?.reviewer,'string');assert(manifest.approval.reviewer.length>0);
    assert(Number.isFinite(Date.parse(manifest.approval.reviewed_utc)));
  }else assert.equal(manifest.approval,null);
  assert.deepEqual(normalizedManifest(manifest),expected,'Suffix manifest differs from frozen evidence');
  return {manifest,manifestSha:hashFile(MANIFEST),designSha:hash(stable(expected)),plan:legacy.verifyPlan().plan};
}
function expectedRootReviewCandidate(ctx){
  const offlineManifestSha=hash(stable(normalizedManifest(ctx.manifest))+'\n');
  return {kind:SCHEMA+'-design-root-review',approved:false,authorized_by_root:false,
    independent_review:false,reviewer:null,reviewed_utc:null,
    manifest_design_sha256:ctx.designSha,offline_manifest_sha256:offlineManifestSha,
    controller_sha256:ctx.manifest.controller.sha256,scope:ctx.manifest.scope,
    ids:ctx.manifest.suffix.ids,request_sha256:ctx.manifest.suffix.requests.map(x=>x.sha256),
    original_interruption_review_sha256:ctx.manifest.original.bindings.interruption_review.sha256,
    original_unknown_ids:['DEV-052'],original_never_sent_ids:SUFFIX_IDS,
    retained_smoke_inspection_sha256:ctx.manifest.smoke.inspection.sha256,
    reference_labels_read:false,smoke_replayed:false,output_repaired:false,
    clean_repeat_credit:false,live_preflight_performed:false,inference_authorized:false};
}
function verifyRootReviewCandidate(ctx){
  const candidate=read(REVIEW_CANDIDATE);
  assert.deepEqual(candidate,expectedRootReviewCandidate(ctx),'Design review candidate differs');
  return candidate;
}
function freeze(){
  assert(!fs.existsSync(MANIFEST)&&!fs.existsSync(REVIEW_CANDIDATE),'Suffix preparation already exists');
  fs.mkdirSync(OUTPUT,{recursive:true});
  fs.writeFileSync(MANIFEST,stable(expectedManifest())+'\n',{flag:'wx'});
  const ctx=verifyManifest();
  fs.writeFileSync(REVIEW_CANDIDATE,JSON.stringify(expectedRootReviewCandidate(ctx),null,2)+'\n',{flag:'wx'});
  return {manifest_sha256:ctx.manifestSha,review_candidate_sha256:hashFile(REVIEW_CANDIDATE)};
}

function selectedRows(plan){
  const selected=legacy.stageRows(plan,ID,CONDITION,'development').slice(52);
  assert.deepEqual(selected.map(x=>x.id),SUFFIX_IDS);
  return selected;
}
async function verifyAllRequests(runtime,plan){
  const config=plan.configurations[ID],all=legacy.stageRows(plan,ID,CONDITION,'development'),measured=[];
  assert.equal(all.length,60);
  for(const row of all) measured.push({id:row.id,...await legacy.verifyRequestRuntime(runtime,config,row)});
  assert.deepEqual(measured.map(x=>x.id),IDS);
  return measured;
}
async function fetchRouteEvidence(fetcher=fetch,now=Date.now()){
  const endpoint='https://openrouter.ai/api/v1/models';
  const response=await fetcher(endpoint,{signal:AbortSignal.timeout(15000),headers:{accept:'application/json'}});
  assert.equal(response.status,200,'Live OpenRouter route audit unavailable');
  const raw=await response.text(),body=JSON.parse(raw);
  assert(Array.isArray(body.data)&&body.data.length>=100,'Live OpenRouter catalog incomplete');
  const needle='qwen354b';
  const matches=body.data.filter(model=>[model.id,model.name,model.canonical_slug,model.hugging_face_id]
    .some(value=>typeof value==='string'&&value.toLowerCase().replace(/[^a-z0-9]/g,'').includes(needle)));
  assert.equal(matches.length,0,`Exact Qwen3.5-4B hosted route needs review: ${matches.map(x=>x.id).join(', ')}`);
  return {raw,audit:{source:endpoint,retrieved_utc:new Date(now).toISOString(),http_status:200,
    raw_sha256:hash(raw),model_count:body.data.length,catalog_matches:matches,
    exact_family_decisions:{'Qwen3.5-4B':{catalog_id_found:false,matching_ids:[],
      endpoint_query:'not_applicable_no_catalog_id'}}}};
}
function stamp(now=new Date()){return now.toISOString().replace(/[-:.]/g,'');}
function assertUnclaimed(paths=outputPaths()){
  for(const [key,file] of Object.entries(paths)) if(key!=='folder')
    assert(!fs.existsSync(file),`Suffix already claimed; no replay: ${file}`);
}

async function preflightCandidate(ctx=verifyManifest(),deps={}){
  assert.equal(ctx.manifest.status,'approved','Suffix manifest awaits root approval');
  if(Object.keys(deps).length===0) assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1',
    'Use the locked preflight command');
  verifyOriginalEvidence(ctx.plan);assertUnclaimed();
  const host=(deps.currentHost||hostAdmission.currentHost)();
  const config=ctx.plan.configurations[ID];
  const runtime=await (deps.runtime||small.realRuntime)(ctx.plan,config);
  const measured=await (deps.verifyAll||verifyAllRequests)(runtime,ctx.plan);
  assert.equal(measured.length,60,'All 60 requests require live render/token checks');
  const route=await (deps.routeEvidence||fetchRouteEvidence)();
  const created=new Date(),tag=stamp(created);
  const hostFile=path.join(OUTPUT,`host-baseline-${tag}.json`);
  const preflightFile=path.join(OUTPUT,`runtime-preflight-${tag}.json`);
  const routeRawFile=path.join(OUTPUT,`route-catalog-${tag}.raw.json`);
  const routeAuditFile=path.join(OUTPUT,`route-catalog-${tag}.audit.json`);
  const candidateFile=path.join(OUTPUT,`suffix-root-review-candidate-${tag}.json`);
  fs.writeFileSync(hostFile,JSON.stringify(host,null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(preflightFile,JSON.stringify({phase:PHASE,stage:STAGE,
    runtime:runtime.attestation,measurements:measured},null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(routeRawFile,route.raw,{flag:'wx'});
  fs.writeFileSync(routeAuditFile,JSON.stringify(route.audit,null,2)+'\n',{flag:'wx'});
  const requestHashes=ctx.manifest.suffix.requests.map(x=>x.sha256);
  const candidate={kind:SCHEMA+'-execution-root-review',approved:false,authorized_by_root:false,
    reviewer:null,reviewed_utc:null,candidate_file:path.relative(ROOT,candidateFile),
    manifest_sha256:ctx.manifestSha,controller_sha256:ctx.manifest.controller.sha256,
    phase:PHASE,stage:STAGE,ids:SUFFIX_IDS,request_sha256:requestHashes,
    model_identifier:config.model_identifier,artifact_sha256:config.artifact_sha256,
    artifact_bytes:config.artifact_bytes,quantization:'Q4_K_M',surface:'lmstudio_sdk',
    request_config_sha256:ctx.manifest.runtime.request_config_sha256,
    load_config_sha256:ctx.manifest.runtime.load_config_sha256,
    prediction_config_sha256:ctx.manifest.runtime.prediction_config_sha256,
    cache_policy:ctx.manifest.runtime.cache_policy,reference_labels_read:false,
    smoke_replayed:false,retained_smoke_inspection_sha256:ctx.manifest.smoke.inspection.sha256,
    original_interruption_review_sha256:ctx.manifest.original.bindings.interruption_review.sha256,
    unknown_ids:['DEV-052'],never_sent_ids:SUFFIX_IDS,clean_repeat_credit:false,
    host_baseline_file:path.relative(ROOT,hostFile),host_baseline_sha256:hashFile(hostFile),host_baseline:host,
    runtime_preflight_file:path.relative(ROOT,preflightFile),runtime_preflight_sha256:hashFile(preflightFile),
    runtime_token_preflight:{request_count:60,
      requests_sha256:hash(stable(config.conditions.P0.requests)),
      observed_preflight_sha256:hash(stable(measured)),observed_instance_reference:runtime.instance},
    exact_openrouter_route_absent:true,route_catalog_file:path.relative(ROOT,routeAuditFile),
    route_catalog_sha256:hashFile(routeAuditFile),route_raw_file:path.relative(ROOT,routeRawFile),
    route_raw_sha256:hashFile(routeRawFile),route_checked_utc:route.audit.retrieved_utc};
  fs.writeFileSync(candidateFile,JSON.stringify(candidate,null,2)+'\n',{flag:'wx'});
  return {candidate:path.relative(ROOT,candidateFile),candidate_sha256:hashFile(candidateFile),
    requests_checked:measured.length,ids:SUFFIX_IDS,approved:false};
}

function verifyExecutionReview(receiptPath,ctx,currentHost,now=Date.now()){
  assert.equal(path.resolve(receiptPath),EXECUTION_REVIEW,'Use the fixed suffix root-review path');
  const receipt=read(receiptPath);
  assert.equal(receipt.kind,SCHEMA+'-execution-root-review');
  assert.equal(receipt.approved,true,'Execution review is not approved');
  assert.equal(receipt.authorized_by_root,true,'Execution review lacks root authorization');
  assert.equal(typeof receipt.reviewer,'string');assert(receipt.reviewer.length>0);
  assert(Number.isFinite(Date.parse(receipt.reviewed_utc)));
  const candidateFile=rel(receipt.candidate_file),candidate=read(candidateFile);
  assert.equal(hashFile(candidateFile),receipt.candidate_sha256);
  const normalized={...receipt,approved:false,authorized_by_root:false,reviewer:null,reviewed_utc:null};
  delete normalized.candidate_sha256;
  assert.deepEqual(normalized,candidate,'Reviewed receipt differs from preflight candidate');
  assert.equal(receipt.manifest_sha256,ctx.manifestSha);
  assert.equal(receipt.controller_sha256,ctx.manifest.controller.sha256);
  assert.deepEqual(receipt.ids,SUFFIX_IDS);
  assert.deepEqual(receipt.request_sha256,ctx.manifest.suffix.requests.map(x=>x.sha256));
  assert.equal(receipt.runtime_token_preflight.request_count,60);
  assert.equal(receipt.runtime_token_preflight.requests_sha256,
    hash(stable(ctx.plan.configurations[ID].conditions.P0.requests)));
  for(const key of ['host_baseline_file','runtime_preflight_file','route_catalog_file','route_raw_file']){
    const digestKey=key.replace(/_file$/,'_sha256');
    assert.equal(hashFile(rel(receipt[key])),receipt[digestKey],`${key} changed`);
  }
  const audit=read(rel(receipt.route_catalog_file));
  assert.equal(audit.source,'https://openrouter.ai/api/v1/models');
  assert.deepEqual(audit.catalog_matches,[]);assert.equal(audit.exact_family_decisions['Qwen3.5-4B'].catalog_id_found,false);
  assert.equal(receipt.route_checked_utc,audit.retrieved_utc);
  const age=now-Date.parse(audit.retrieved_utc);
  assert(age>=0&&age<5*60*1000,'Route attestation must be fresh (five minutes)');
  assert.deepEqual(read(rel(receipt.host_baseline_file)),receipt.host_baseline);
  hostAdmission.verifyAfterStage(receipt.host_baseline,currentHost);
  return receipt;
}
function prepare(manifestSha,receiptPath,now=Date.now(),deps={}){
  const ctx=verifyManifest();
  assert.equal(ctx.manifestSha,manifestSha,'Approved manifest hash differs');
  assert.equal(ctx.manifest.status,'approved','Suffix manifest awaits root approval');
  verifyOriginalEvidence(ctx.plan);assertUnclaimed();
  const current=(deps.currentHost||hostAdmission.currentHost)();
  const receipt=verifyExecutionReview(receiptPath,ctx,current,now);
  return {manifest:ctx.manifest,plan:ctx.plan,receipt,paths:outputPaths(),host:current};
}

async function runSuffix(manifestSha,receiptPath,dependencies={}){
  if(!dependencies.prepare) assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1',
    'Use run to acquire the shared native host lock');
  const prepared=(dependencies.prepare||prepare)(manifestSha,receiptPath,Date.now(),dependencies);
  const manifest=prepared.manifest,plan=prepared.plan||legacy.verifyPlan().plan,p=prepared.paths;
  const config=plan.configurations[ID],selection=selectedRows(plan);
  assert.deepEqual(selection.map(x=>hash(stable(x.request))),manifest.suffix.requests.map(x=>x.sha256));
  const currentHost=dependencies.currentHost||hostAdmission.currentHost;
  const verifyAfter=dependencies.verifyAfterStage||hostAdmission.verifyAfterStage;
  const runtime=await (dependencies.runtime||small.realRuntime)(plan,config);
  const measured=await (dependencies.verifyAll||verifyAllRequests)(runtime,plan);
  assert.equal(measured.length,60,'All 60 requests require live render/token checks');
  if(prepared.receipt.runtime_token_preflight?.observed_preflight_sha256)
    assert.equal(hash(stable(measured)),prepared.receipt.runtime_token_preflight.observed_preflight_sha256,
      'Runtime render/token preflight changed since root review');
  if(prepared.receipt.runtime_token_preflight?.observed_instance_reference)
    assert.equal(runtime.instance,prepared.receipt.runtime_token_preflight.observed_instance_reference,
      'Loaded model instance changed since root review');
  let route=await (dependencies.routeAudit||legacy.checkLiveRoute)();
  assertUnclaimed(p);fs.mkdirSync(p.folder,{recursive:true});
  fs.writeFileSync(p.claim,stable({schema:SCHEMA+'-atomic-claim',phase:PHASE,stage:STAGE,
    ids:SUFFIX_IDS,manifest_sha256:manifestSha,controller_sha256:manifest.controller.sha256,
    receipt_sha256:hashFile(receiptPath),runtime_attestation:runtime.attestation,
    runtime_preflight_sha256:hash(stable(measured)),route_audit:route,host_baseline:prepared.host,
    started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  let journal,raw,records;
  try{
    journal=fs.openSync(p.journal,'wx');raw=fs.openSync(p.raw,'wx');records=fs.openSync(p.records,'wx');
  }catch(error){
    for(const fd of [journal,raw,records]) if(fd!==undefined) fs.closeSync(fd);
    throw error;
  }
  let status='stopped',reason=null,invalid=0,hostAfter=null,hostCheck=null;
  try{
    for(let i=0;i<selection.length;i++){
      const item=selection[i];
      if(!Number.isFinite(route.checked_ms)||Date.now()-route.checked_ms>=5*60*1000)
        route=await (dependencies.routeAudit||legacy.checkLiveRoute)();
      const observed=await (dependencies.verifyOne||legacy.verifyRequestRuntime)(runtime,config,item);
      const expected=measured[52+i];
      assert.deepEqual(observed.id===undefined?{id:item.id,...observed}:observed,expected,
        'Runtime request preflight changed before dispatch');
      const info=await runtime.model.getModelInfo();
      assert.equal(info.instanceReference,runtime.instance,'Loaded model instance changed');
      const attempt=crypto.randomUUID(),requestHash=hash(stable(item.request));
      durable(journal,{event:'started',attempt_id:attempt,id:item.id,request_sha256:requestHash,
        at:new Date().toISOString()});
      const started=process.hrtime.bigint();let result;
      try{
        result=await (dependencies.predict||predictor.predictWithTimeout)(runtime.model,
          item.request.messages,item.request.config,config.timeout_ms);
      }catch(error){
        durable(raw,{attempt_id:attempt,id:item.id,error:String(error.message),code:error.code??null,
          cancellationAcknowledged:error.cancellationAcknowledged??null,
          cancellationError:error.cancellationError??null,partialResult:error.partialResult??null,
          elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9,result:null});
        durable(journal,{event:'stopped_unknown',attempt_id:attempt,id:item.id,at:new Date().toISOString()});
        throw error;
      }
      durable(raw,{attempt_id:attempt,id:item.id,result:{content:result?.content??null,
        nonReasoningContent:result?.nonReasoningContent??null,reasoningContent:result?.reasoningContent??null,
        stats:result?.stats??null,modelInfo:result?.modelInfo??null,loadConfig:result?.loadConfig??null,
        predictionConfig:result?.predictionConfig??null},elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9});
      const expectedResult={identifier:config.model_identifier,path:config.artifact_path,
        bytes:config.artifact_bytes,promptTokens:item.prompt_tokens,
        loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config};
      const decision=parent.classifySdk(result,expectedResult);
      durable(records,{id:item.id,attempt_id:attempt,request_sha256:requestHash,decision,
        source_phase:PHASE,continuation_schema:SCHEMA,reference_labels_read:false,
        finished_utc:new Date().toISOString()});
      durable(journal,{event:'finished',attempt_id:attempt,id:item.id,status:decision.status,
        at:new Date().toISOString()});
      if(decision.status==='invalid_output') invalid++;
      else if(decision.status!=='ok') throw Error(`Stopped on ${decision.status} at ${item.id}`);
    }
    hostAfter=currentHost();hostCheck=verifyAfter(prepared.host,hostAfter);
    status='completed';
  }catch(error){reason=String(error.message);throw error;}
  finally{
    for(const fd of [journal,raw,records]) fs.closeSync(fd);
    fs.writeFileSync(p.completion,stable({schema:SCHEMA+'-completion',phase:PHASE,stage:STAGE,
      status,reason,attempted:rows(p.journal).filter(x=>x.event==='started').length,
      saved:rows(p.records).length,invalid,unknown_ids:rows(p.journal).filter(x=>x.event==='stopped_unknown').map(x=>x.id),
      original_unknown_ids:['DEV-052'],clean_repeat_eligible:false,host_after:hostAfter,host_check:hostCheck,
      journal_sha256:hashFile(p.journal),raw_sha256:hashFile(p.raw),records_sha256:hashFile(p.records),
      finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  }
  return read(p.completion);
}

async function main(argv){
  const [action,...args]=argv;
  if(action==='freeze'){console.log(JSON.stringify(freeze()));return;}
  if(action==='verify'){
    const ctx=verifyManifest(),candidate=verifyRootReviewCandidate(ctx);
    console.log(JSON.stringify({status:ctx.manifest.status,manifest_sha256:ctx.manifestSha,
      review_candidate_sha256:hashFile(REVIEW_CANDIDATE),ids:candidate.ids}));return;
  }
  if(action==='preview'){
    const manifest=expectedManifest();console.log(JSON.stringify({scope:manifest.scope,
      ids:manifest.suffix.ids,requests:manifest.suffix.requests,original:manifest.original}));return;
  }
  if(action==='preflight-candidate'||action==='run'){
    execFileSync('python3',['-c',legacy.lockCode,legacy.LOCK,process.execPath,__filename,
      action==='run'?'internal-run':'internal-preflight',...args],{stdio:'inherit'});return;
  }
  if(action==='internal-preflight'){
    assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use locked preflight command');
    console.log(JSON.stringify(await preflightCandidate()));return;
  }
  if(action==='internal-run'){
    assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use locked run command');
    assert.equal(args.length,2,'Require approved manifest SHA and root review path');
    await runSuffix(args[0],args[1]);return;
  }
  throw Error('Use freeze, verify, preview, preflight-candidate, or run');
}
if(require.main===module)main(process.argv.slice(2)).catch(error=>{
  console.error(error.stack||error);process.exitCode=1;
});

module.exports={ROOT,ID,PASS,CONDITION,PHASE,STAGE,SCHEMA,ORIGINAL,OUTPUT,MANIFEST,
  REVIEW_CANDIDATE,EXECUTION_REVIEW,IDS,SUFFIX_IDS,sourceBinding,outputPaths,
  originalFiles,verifyOriginalEvidence,expectedManifest,verifyManifest,
  expectedRootReviewCandidate,verifyRootReviewCandidate,freeze,selectedRows,
  verifyAllRequests,fetchRouteEvidence,assertUnclaimed,preflightCandidate,
  verifyExecutionReview,prepare,runSuffix};
