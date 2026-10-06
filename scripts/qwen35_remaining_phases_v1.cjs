#!/usr/bin/env node
'use strict';
// Successor admission for the eight Qwen3.5 phases after the descriptive
// fresh1/P0 closure. This file never converts that closure into a clean repeat.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const legacy=require('./legacy_qwen_repeat_admission.cjs');
const small=require('./small_local_repeat_admission.cjs');
const hostAdmission=require('./local_host_admission.cjs');
const suffix=require('./qwen35_p0_unsent_suffix_v1.cjs');
const parent=require('./local_prompt_execution_v1.cjs');

const ROOT=small.ROOT;
const ID='qwen3.5-4b-sdk-thinking-on';
const P0_PHASE=`${ID}/fresh1/P0`;
const SCHEMA='qwen35-remaining-phases-v1';
const COMPOSITE_SCHEMA='qwen35-p0-descriptive-composite-root-review-v1';
const OUTPUT=path.join(ROOT,'results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-remaining-phases-v1');
const MANIFEST=path.join(OUTPUT,'manifest.json');
const REVIEW_CANDIDATE=path.join(OUTPUT,'root-review-candidate.json');
const COMPOSITE=path.join(suffix.OUTPUT,'composite.root-review.json');
const IDS=Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);
const PHASES=[['fresh1','P2'],['fresh1','P1'],['fresh2','P2'],['fresh2','P1'],
  ['fresh2','P0'],['fresh3','P1'],['fresh3','P0'],['fresh3','P2']];
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

function remainingSchedule(plan){
  const config=plan.configurations[ID];
  assert(config,'Frozen Qwen3.5 configuration missing');
  return PHASES.map(([pass,condition])=>{
    legacy.phaseInfo(plan,ID,pass,condition);
    const requests=config.conditions[condition].requests;
    assert.deepEqual(requests.map(x=>x.id),IDS);
    return {pass,condition,ids:[...IDS],request_sha256:requests.map(x=>x.sha256),
      rendered_sha256:requests.map(x=>x.rendered_sha256),
      prompt_tokens:requests.map(x=>x.prompt_tokens),stages:['smoke','development']};
  });
}

function flatBindings(files){
  return Object.fromEntries(files.map(file=>{
    const binding=sourceBinding(file);
    return [binding.file,binding.sha256];
  }));
}

function verifyOriginalRootReview(plan){
  const summary=suffix.verifyOriginalEvidence(plan);
  const files=suffix.originalFiles();
  return {...summary,saved_ids:IDS.slice(0,51),bindings:flatBindings(Object.values(files))};
}

function verifySuffixRootReview(plan){
  const p=suffix.outputPaths();
  for(const file of [suffix.MANIFEST,suffix.EXECUTION_REVIEW,p.claim,p.journal,p.raw,p.records,p.completion])
    assert(fs.existsSync(file),`Suffix terminal evidence missing: ${file}`);
  const manifest=read(suffix.MANIFEST),review=read(suffix.EXECUTION_REVIEW);
  assert.equal(manifest.status,'approved','Suffix manifest is not approved');
  assert.equal(review.kind,suffix.SCHEMA+'-execution-root-review');
  assert.equal(review.approved,true,'Suffix execution review is not approved');
  assert.equal(review.authorized_by_root,true,'Suffix execution review lacks root authorization');
  assert(Number.isFinite(Date.parse(review.reviewed_utc)),'Suffix review time is invalid');
  const candidate=rel(review.candidate_file);
  assert.equal(hashFile(candidate),review.candidate_sha256,'Suffix candidate changed');
  const normalized={...review,approved:false,authorized_by_root:false,reviewer:null,reviewed_utc:null};
  delete normalized.candidate_sha256;
  assert.deepEqual(normalized,read(candidate),'Suffix review differs from its candidate');
  for(const key of ['host_baseline_file','runtime_preflight_file','route_catalog_file','route_raw_file'])
    assert.equal(hashFile(rel(review[key])),review[key.replace(/_file$/,'_sha256')],`${key} changed`);

  const claim=read(p.claim),journal=rows(p.journal),raw=rows(p.raw),saved=rows(p.records),done=read(p.completion);
  assert.equal(claim.schema,suffix.SCHEMA+'-atomic-claim');
  assert.equal(claim.phase,P0_PHASE);assert.equal(claim.stage,suffix.STAGE);
  assert.deepEqual(claim.ids,IDS.slice(52));
  assert.equal(claim.manifest_sha256,hashFile(suffix.MANIFEST));
  assert.equal(claim.controller_sha256,hashFile(path.join(ROOT,'scripts/qwen35_p0_unsent_suffix_v1.cjs')));
  assert.equal(claim.receipt_sha256,hashFile(suffix.EXECUTION_REVIEW));
  assert.equal(done.schema,suffix.SCHEMA+'-completion');
  assert.equal(done.status,'completed','Suffix terminal is not completed');
  assert.equal(done.attempted,8,'Suffix does not contain eight attempts');
  assert.equal(done.saved,8,'Suffix does not contain eight saved records');
  assert.deepEqual(done.unknown_ids,[],'Suffix contains a new unknown outcome');
  assert.deepEqual(done.original_unknown_ids,['DEV-052']);
  assert.equal(done.clean_repeat_eligible,false);
  assert.equal(done.host_check?.host_unchanged,true,'Suffix terminal host check did not pass');
  for(const key of ['journal','raw','records']) assert.equal(done[`${key}_sha256`],hashFile(p[key]));
  assert.equal(journal.length,16);assert.equal(raw.length,8);assert.equal(saved.length,8);
  assert.deepEqual(raw.map(x=>x.id),IDS.slice(52));
  assert.deepEqual(saved.map(x=>x.id),IDS.slice(52));
  const selection=legacy.stageRows(plan,ID,'P0','development').slice(52);
  const config=plan.configurations[ID];
  let invalid=0;
  for(let i=0;i<8;i++){
    assert.equal(journal[2*i].event,'started');assert.equal(journal[2*i+1].event,'finished');
    assert.equal(journal[2*i].id,selection[i].id);assert.equal(journal[2*i+1].id,selection[i].id);
    assert.equal(saved[i].request_sha256,hash(stable(selection[i].request)));
    assert.equal(saved[i].reference_labels_read,false);
    const expectedResult={identifier:config.model_identifier,path:config.artifact_path,
      bytes:config.artifact_bytes,promptTokens:selection[i].prompt_tokens,
      loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config};
    assert.deepEqual(saved[i].decision,parent.classifySdk(raw[i].result,expectedResult),
      `Suffix decision differs at ${selection[i].id}`);
    assert(['ok','invalid_output'].includes(saved[i].decision.status));
    assert.equal(journal[2*i+1].status,saved[i].decision.status);
    if(saved[i].decision.status==='invalid_output') invalid++;
  }
  assert.equal(invalid,done.invalid);
  const bindingFiles=[suffix.MANIFEST,path.join(ROOT,'scripts/qwen35_p0_unsent_suffix_v1.cjs'),
    suffix.EXECUTION_REVIEW,p.claim,p.journal,p.raw,p.records,p.completion,candidate,
    ...['host_baseline_file','runtime_preflight_file','route_catalog_file','route_raw_file'].map(k=>rel(review[k]))];
  return {status:'completed',attempted:8,saved:8,valid:8-invalid,invalid,unknown_ids:[],
    saved_ids:IDS.slice(52),bindings:flatBindings(bindingFiles)};
}

function verifyCompositeEvidence(){
  const {plan}=legacy.verifyPlan();
  return {original:verifyOriginalRootReview(plan),suffix:verifySuffixRootReview(plan)};
}

function expectedCompositeReview(evidence){
  const original=evidence.original,sfx=evidence.suffix;
  assert.equal(original.attempted,52);assert.equal(original.saved,51);
  assert.deepEqual(original.saved_ids,IDS.slice(0,51));
  assert.deepEqual(original.unknown_ids,['DEV-052']);
  assert.equal(sfx.status,'completed');assert.equal(sfx.attempted,8);
  assert.equal(sfx.saved,8,'Composite requires all eight saved suffix records');
  assert.deepEqual(sfx.saved_ids,IDS.slice(52));assert.deepEqual(sfx.unknown_ids,[]);
  const bindings={...original.bindings};
  for(const [file,digest] of Object.entries(sfx.bindings)){
    assert(bindings[file]===undefined||bindings[file]===digest,`Conflicting composite binding: ${file}`);
    bindings[file]=digest;
  }
  return {schema:COMPOSITE_SCHEMA,approved:false,reviewer:null,phase:P0_PHASE,saved:59,
    valid:original.valid+sfx.valid,invalid:original.invalid+sfx.invalid,
    unknown_ids:['DEV-052'],never_sent_ids:[],clean_repeat_eligible:false,
    reference_labels_read:false,bindings};
}

function validateCompositeReview(receipt,evidence){
  assert.equal(receipt.approved,true,'Composite review is not approved');
  assert.equal(receipt.reviewer,'root','Composite review is not approved by root');
  assert(Number.isFinite(Date.parse(receipt.reviewed_utc)),'Composite review time is invalid');
  const normalized={...receipt,approved:false,reviewer:null};
  delete normalized.reviewed_utc;
  assert.deepEqual(normalized,expectedCompositeReview(evidence),'Composite review differs from terminal evidence');
  return receipt;
}

function verifyCompositeReview(compositePath=COMPOSITE,{verifyEvidence=verifyCompositeEvidence}={}){
  assert(fs.existsSync(compositePath),`Composite review missing: ${compositePath}`);
  const evidence=verifyEvidence(),receipt=validateCompositeReview(read(compositePath),evidence);
  for(const [file,digest] of Object.entries(receipt.bindings))
    assert.equal(hashFile(rel(file)),digest,`Composite binding changed: ${file}`);
  return {receipt,evidence,sha256:hashFile(compositePath),file:path.relative(ROOT,compositePath)};
}

function expectedManifest(compositeCtx,plan=legacy.verifyPlan().plan){
  const config=plan.configurations[ID];
  return {schema:SCHEMA,status:'offline_prepared_unapproved',approval:null,
    method:'descriptive-p0-successor',reference_labels_read:false,clean_repeat_eligible:false,
    scope:{configuration:ID,phases:remainingSchedule(plan)},
    composite:{file:compositeCtx.file,sha256:compositeCtx.sha256,schema:COMPOSITE_SCHEMA,
      unknown_ids:['DEV-052'],saved:59,clean_repeat_eligible:false},
    frozen:{plan:sourceBinding(legacy.PLAN),legacy_controller:sourceBinding(path.join(ROOT,'scripts/legacy_qwen_repeat_admission.cjs')),
      request_constructor:sourceBinding(path.join(ROOT,'scripts/frozen_prompt_variants.cjs')),
      classifier:sourceBinding(path.join(ROOT,'scripts/local_prompt_execution_v1.cjs')),
      predictor:sourceBinding(path.join(ROOT,'scripts/lmstudio_reasoning_benchmark.cjs')),
      runtime_admission:sourceBinding(path.join(ROOT,'scripts/small_local_repeat_admission.cjs')),
      host_admission:sourceBinding(path.join(ROOT,'scripts/local_host_admission.cjs')),
      suffix_controller:sourceBinding(path.join(ROOT,'scripts/qwen35_p0_unsent_suffix_v1.cjs')),
      successor_controller:sourceBinding(__filename)},
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
    policy:{unknown_ids:['DEV-052'],p0_never_replay_ids:IDS,successor_stage_replay:false,
      invalid_output:'retain_and_continue',service_or_control_failure:'stop_without_retry',
      output_repair:false,shared_lock:path.relative(ROOT,legacy.LOCK),
      current_local_battery_policy:true,continuation_does_not_restore_clean_repeat_credit:true}};
}

function normalizedManifest(manifest){
  const copy=structuredClone(manifest);copy.status='offline_prepared_unapproved';copy.approval=null;return copy;
}

function prepareManifest({manifestPath=MANIFEST,compositePath=COMPOSITE,verifyEvidence=verifyCompositeEvidence}={}){
  assert(!fs.existsSync(manifestPath),'Remaining-phase manifest already exists');
  const candidatePath=path.join(path.dirname(manifestPath),path.basename(REVIEW_CANDIDATE));
  assert(!fs.existsSync(candidatePath),'Remaining-phase review candidate already exists');
  const compositeCtx=verifyCompositeReview(compositePath,{verifyEvidence});
  const manifest=expectedManifest(compositeCtx);
  fs.mkdirSync(path.dirname(manifestPath),{recursive:true});
  fs.writeFileSync(manifestPath,stable(manifest)+'\n',{flag:'wx'});
  const candidate={kind:SCHEMA+'-design-root-review',approved:false,authorized_by_root:false,
    independent_review:false,reviewer:null,reviewed_utc:null,
    manifest_sha256:hashFile(manifestPath),controller_sha256:manifest.frozen.successor_controller.sha256,
    composite_sha256:compositeCtx.sha256,phases:manifest.scope.phases.map(x=>[x.pass,x.condition]),
    unknown_ids:['DEV-052'],reference_labels_read:false,replay_authorized:false,
    clean_repeat_credit:false,inference_authorized:false};
  fs.writeFileSync(candidatePath,JSON.stringify(candidate,null,2)+'\n',{flag:'wx'});
  return {manifest_sha256:hashFile(manifestPath),review_candidate_sha256:hashFile(candidatePath)};
}

function verifyManifest(manifestPath=MANIFEST,compositePath=COMPOSITE,deps={}){
  const compositeCtx=(deps.verifyComposite||verifyCompositeReview)(compositePath,
    deps.verifyEvidence?{verifyEvidence:deps.verifyEvidence}:undefined);
  const manifest=read(manifestPath);
  assert(['offline_prepared_unapproved','approved'].includes(manifest.status));
  if(manifest.status==='approved'){
    assert.equal(manifest.approval?.authorized_by_root,true);
    assert.equal(manifest.approval?.independent_review,true);
    assert.equal(manifest.approval?.reviewer,'root');
    assert(Number.isFinite(Date.parse(manifest.approval?.reviewed_utc)));
  }else assert.equal(manifest.approval,null);
  assert.deepEqual(normalizedManifest(manifest),expectedManifest(compositeCtx),
    'Remaining-phase manifest differs from frozen sources or composite');
  return {manifest,manifestSha:hashFile(manifestPath),plan:legacy.verifyPlan().plan,composite:compositeCtx};
}

function stagePaths(_id,pass,condition,stage,base=OUTPUT){
  assert(['smoke','development'].includes(stage));
  const folder=path.join(base,pass,condition);
  return {folder,claim:path.join(folder,`${stage}.claim.json`),journal:path.join(folder,`${stage}.journal.jsonl`),
    raw:path.join(folder,`${stage}.raw.jsonl`),records:path.join(folder,`${stage}.records.jsonl`),
    completion:path.join(folder,`${stage}.completion.json`)};
}

function verifyClosedStage(files,phase,stage){
  assert(fs.existsSync(files.completion),stage==='smoke'?'Smoke not complete':`Prior successor phase incomplete: ${phase}`);
  const done=read(files.completion),count=stage==='smoke'?3:60;
  assert.equal(done.status,'completed',stage==='smoke'?'Smoke not complete':`Prior successor phase incomplete: ${phase}`);
  assert.equal(done.attempted,count);assert.equal(done.saved,count);
  for(const key of ['journal','raw','records']) assert.equal(done[`${key}_sha256`],hashFile(files[key]));
  const audit=path.join(files.folder,`${stage}.host-audit.json`);
  assert(fs.existsSync(audit),`${stage} host audit missing`);
  const checked=read(audit);
  assert.equal(checked.schema,SCHEMA+'-host-audit');assert.equal(checked.status,'passed');
  assert.equal(checked.completion_sha256,hashFile(files.completion));
  if(stage==='smoke'){
    const inspection=path.join(files.folder,'smoke-inspection.json');
    assert(fs.existsSync(inspection),'Independent smoke inspection missing');
    const reviewed=read(inspection);
    assert.equal(reviewed.kind,'legacy-qwen-three-record-smoke-inspection-v1');
    assert.equal(reviewed.approved,true);assert.equal(reviewed.raw_sha256,done.raw_sha256);
    assert.equal(reviewed.records_sha256,done.records_sha256);
    assert.deepEqual(rows(files.records).map(x=>x.decision.status),['ok','ok','ok']);
    return hashFile(inspection);
  }
  return hashFile(files.completion);
}

function checkSuccessorPredecessor(manifest,pass,condition,stage,deps={}){
  assert(['smoke','development'].includes(stage));
  (deps.verifyComposite||verifyCompositeReview)();
  const schedule=manifest.schedule||manifest.scope?.phases;
  assert(Array.isArray(schedule),'Successor schedule missing');
  const index=schedule.findIndex(x=>x.pass===pass&&x.condition===condition);
  assert(index>=0,'Phase is outside remaining schedule');
  const base=deps.base||OUTPUT,paths=deps.paths||((id,p,c,s)=>stagePaths(id,p,c,s,base));
  for(let i=0;i<index;i++){
    const prior=schedule[i],phase=`${ID}/${prior.pass}/${prior.condition}`;
    verifyClosedStage(paths(ID,prior.pass,prior.condition,'development'),phase,'development');
  }
  if(stage==='smoke') return null;
  return verifyClosedStage(paths(ID,pass,condition,'smoke'),`${ID}/${pass}/${condition}`,'smoke');
}

function assertUnclaimed(files){
  for(const [key,file] of Object.entries(files)) if(key!=='folder')
    assert(!fs.existsSync(file),`Phase already claimed; no replay: ${file}`);
}

async function verifyAllRequests(runtime,plan,condition){
  const config=plan.configurations[ID],selected=legacy.stageRows(plan,ID,condition,'development'),measured=[];
  assert.equal(selected.length,60);
  for(const row of selected) measured.push({id:row.id,...await legacy.verifyRequestRuntime(runtime,config,row)});
  assert.deepEqual(measured.map(x=>x.id),IDS);
  return measured;
}

function stamp(now=new Date()){return now.toISOString().replace(/[-:.]/g,'');}

async function preflightCandidate(ctx=verifyManifest(),pass,condition,stage,deps={}){
  assert.equal(ctx.manifest.status,'approved','Remaining-phase manifest awaits root approval');
  if(Object.keys(deps).length===0) assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1',
    'Use locked preflight command');
  checkSuccessorPredecessor(ctx.manifest,pass,condition,stage,deps);
  const p=stagePaths(ID,pass,condition,stage,deps.base||OUTPUT);assertUnclaimed(p);
  const host=(deps.currentHost||hostAdmission.currentHost)();
  const config=ctx.plan.configurations[ID];
  const runtime=await (deps.runtime||small.realRuntime)(ctx.plan,config);
  const measured=await (deps.verifyAll||verifyAllRequests)(runtime,ctx.plan,condition);
  assert.equal(measured.length,60,'All 60 requests require live render/token checks');
  const route=await (deps.routeEvidence||suffix.fetchRouteEvidence)();
  fs.mkdirSync(p.folder,{recursive:true});
  const tag=stamp(),prefix=path.join(p.folder,`${stage}-${tag}`);
  const hostFile=prefix+'.host-baseline.json',runtimeFile=prefix+'.runtime-preflight.json';
  const routeRawFile=prefix+'.route.raw.json',routeAuditFile=prefix+'.route.audit.json';
  const candidateFile=prefix+'.root-review-candidate.json';
  fs.writeFileSync(hostFile,JSON.stringify(host,null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(runtimeFile,JSON.stringify({phase:`${ID}/${pass}/${condition}`,stage,
    runtime:runtime.attestation,measurements:measured},null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(routeRawFile,route.raw,{flag:'wx'});
  fs.writeFileSync(routeAuditFile,JSON.stringify(route.audit,null,2)+'\n',{flag:'wx'});
  const phase=ctx.manifest.scope.phases.find(x=>x.pass===pass&&x.condition===condition);
  const candidate={kind:SCHEMA+'-stage-root-review',approved:false,authorized_by_root:false,
    reviewer:null,reviewed_utc:null,candidate_file:path.relative(ROOT,candidateFile),
    manifest_sha256:ctx.manifestSha,controller_sha256:ctx.manifest.frozen.successor_controller.sha256,
    composite_sha256:ctx.composite.sha256,phase:`${ID}/${pass}/${condition}`,stage,
    ids:stage==='smoke'?IDS.slice(0,3):IDS,
    request_sha256:stage==='smoke'?phase.request_sha256.slice(0,3):phase.request_sha256,
    model_identifier:config.model_identifier,artifact_sha256:config.artifact_sha256,
    artifact_bytes:config.artifact_bytes,quantization:'Q4_K_M',surface:'lmstudio_sdk',
    request_config_sha256:ctx.manifest.runtime.request_config_sha256,
    load_config_sha256:ctx.manifest.runtime.load_config_sha256,
    prediction_config_sha256:ctx.manifest.runtime.prediction_config_sha256,
    cache_policy:ctx.manifest.runtime.cache_policy,reference_labels_read:false,
    unknown_ids:['DEV-052'],clean_repeat_credit:false,
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
  const candidate=read(rel(receipt.candidate_file));
  assert.equal(hashFile(rel(receipt.candidate_file)),receipt.candidate_sha256);
  const normalized={...receipt,approved:false,authorized_by_root:false,reviewer:null,reviewed_utc:null};
  delete normalized.candidate_sha256;
  assert.deepEqual(normalized,candidate,'Reviewed stage receipt differs from candidate');
  assert.equal(receipt.manifest_sha256,ctx.manifestSha);
  assert.equal(receipt.controller_sha256,ctx.manifest.frozen.successor_controller.sha256);
  assert.equal(receipt.composite_sha256,ctx.composite.sha256);
  assert.equal(receipt.phase,`${ID}/${pass}/${condition}`);assert.equal(receipt.stage,stage);
  const config=ctx.plan.configurations[ID];
  const scheduled=ctx.manifest.scope.phases.find(x=>x.pass===pass&&x.condition===condition);
  assert(scheduled,'Reviewed stage is outside the successor schedule');
  assert.deepEqual(receipt.ids,stage==='smoke'?IDS.slice(0,3):IDS);
  assert.deepEqual(receipt.request_sha256,
    stage==='smoke'?scheduled.request_sha256.slice(0,3):scheduled.request_sha256);
  assert.equal(receipt.model_identifier,config.model_identifier);
  assert.equal(receipt.artifact_sha256,config.artifact_sha256);
  assert.equal(receipt.artifact_bytes,config.artifact_bytes);
  assert.equal(receipt.quantization,'Q4_K_M');assert.equal(receipt.surface,'lmstudio_sdk');
  assert.equal(receipt.request_config_sha256,ctx.manifest.runtime.request_config_sha256);
  assert.equal(receipt.load_config_sha256,ctx.manifest.runtime.load_config_sha256);
  assert.equal(receipt.prediction_config_sha256,ctx.manifest.runtime.prediction_config_sha256);
  assert.deepEqual(receipt.cache_policy,ctx.manifest.runtime.cache_policy);
  assert.equal(receipt.reference_labels_read,false);assert.deepEqual(receipt.unknown_ids,['DEV-052']);
  assert.equal(receipt.clean_repeat_credit,false);
  assert.equal(receipt.runtime_token_preflight?.request_count,60);
  assert.equal(receipt.runtime_token_preflight?.requests_sha256,
    hash(stable(config.conditions[condition].requests)));
  assert.equal(receipt.exact_openrouter_route_absent,true);
  for(const key of ['host_baseline_file','runtime_preflight_file','route_catalog_file','route_raw_file'])
    assert.equal(hashFile(rel(receipt[key])),receipt[key.replace(/_file$/,'_sha256')],`${key} changed`);
  const age=now-Date.parse(receipt.route_checked_utc);
  assert(age>=0&&age<300000,'Route attestation must be fresh (five minutes)');
  const routeAudit=read(rel(receipt.route_catalog_file));
  assert.equal(routeAudit.source,'https://openrouter.ai/api/v1/models');
  assert.deepEqual(routeAudit.catalog_matches,[]);
  assert.equal(routeAudit.exact_family_decisions?.['Qwen3.5-4B']?.catalog_id_found,false);
  assert.equal(routeAudit.retrieved_utc,receipt.route_checked_utc);
  const current=(deps.currentHost||hostAdmission.currentHost)();
  hostAdmission.verifyAfterStage(receipt.host_baseline,current);
  return {receipt,reviewPath,current,paths:p};
}

async function checkExactLiveRoute(fetcher=fetch){
  const {audit}=await suffix.fetchRouteEvidence(fetcher);
  return {checked_ms:Date.parse(audit.retrieved_utc),source:audit.source,model_count:audit.model_count};
}

async function runSuccessorStage(manifestSha,pass,condition,stage,deps={}){
  if(!deps.ctx) assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use run to acquire shared native host lock');
  const ctx=deps.ctx||verifyManifest();assert.equal(ctx.manifestSha,manifestSha,'Approved manifest hash differs');
  assert.equal(ctx.manifest.status,'approved','Remaining-phase manifest awaits root approval');
  checkSuccessorPredecessor(ctx.manifest,pass,condition,stage,deps);
  const admitted=(deps.verifyStageReview||verifyStageReview)(ctx,pass,condition,stage,Date.now(),deps);
  assertUnclaimed(admitted.paths);
  const config=ctx.plan.configurations[ID];
  const runtime=await (deps.runtime||small.realRuntime)(ctx.plan,config);
  const measured=await (deps.verifyAll||verifyAllRequests)(runtime,ctx.plan,condition);
  assert.equal(hash(stable(measured)),admitted.receipt.runtime_token_preflight.observed_preflight_sha256,
    'Runtime render/token preflight changed since root review');
  assert.equal(runtime.instance,admitted.receipt.runtime_token_preflight.observed_instance_reference,
    'Loaded model instance changed since root review');
  const checkRoute=deps.routeAudit||checkExactLiveRoute;
  const route=await checkRoute();let suppliedInitialRoute=false;
  let completion,error;
  try{
    completion=await legacy.runStage(ctx.plan,hashFile(legacy.PLAN),ID,pass,condition,stage,
      admitted.reviewPath,{paths:()=>admitted.paths,
        predecessor:()=>checkSuccessorPredecessor(ctx.manifest,pass,condition,stage,deps),
        admit:receipt=>assert.deepEqual(receipt,admitted.receipt),runtime:async()=>runtime,
        routeAudit:async()=>{
          if(!suppliedInitialRoute){suppliedInitialRoute=true;return route;}
          return checkRoute();
        },verifyRequest:deps.verifyRequest||legacy.verifyRequestRuntime,
        predict:deps.predict});
  }catch(caught){error=caught;}
  let after=null,hostCheck=null,hostError=null;
  try{after=(deps.currentHost||hostAdmission.currentHost)();hostCheck=hostAdmission.verifyAfterStage(admitted.current,after);}
  catch(caught){hostError=caught;}
  const audit={schema:SCHEMA+'-host-audit',status:hostError?'failed':'passed',
    phase:`${ID}/${pass}/${condition}`,stage,before:admitted.current,after,host_check:hostCheck,
    error:hostError?String(hostError.message):null,
    completion_sha256:fs.existsSync(admitted.paths.completion)?hashFile(admitted.paths.completion):null,
    reviewed_receipt_sha256:hashFile(admitted.reviewPath),finished_utc:new Date().toISOString()};
  fs.writeFileSync(path.join(admitted.paths.folder,`${stage}.host-audit.json`),stable(audit)+'\n',{flag:'wx'});
  if(error) throw error;if(hostError) throw hostError;return completion;
}

async function main(argv){
  const [action,...args]=argv;
  if(action==='preview'){
    const {plan}=legacy.verifyPlan();console.log(JSON.stringify({phases:remainingSchedule(plan),composite:COMPOSITE}));return;
  }
  if(action==='prepare'){console.log(JSON.stringify(prepareManifest()));return;}
  if(action==='verify'){const ctx=verifyManifest();console.log(JSON.stringify({status:ctx.manifest.status,
    manifest_sha256:ctx.manifestSha,composite_sha256:ctx.composite.sha256}));return;}
  if(action==='preflight-candidate'||action==='run'){
    execFileSync('python3',['-c',legacy.lockCode,legacy.LOCK,process.execPath,__filename,
      action==='run'?'internal-run':'internal-preflight',...args],{stdio:'inherit'});return;
  }
  if(action==='internal-preflight'){
    assert.equal(args.length,3,'Require pass condition stage');
    console.log(JSON.stringify(await preflightCandidate(verifyManifest(),...args)));return;
  }
  if(action==='internal-run'){
    assert.equal(args.length,4,'Require manifest SHA, pass, condition, stage');
    await runSuccessorStage(...args);return;
  }
  throw Error('Use preview, prepare, verify, preflight-candidate, or run');
}
if(require.main===module)main(process.argv.slice(2)).catch(error=>{console.error(error.stack||error);process.exitCode=1;});

module.exports={ROOT,ID,P0_PHASE,SCHEMA,COMPOSITE_SCHEMA,OUTPUT,MANIFEST,REVIEW_CANDIDATE,
  COMPOSITE,IDS,PHASES,sourceBinding,remainingSchedule,verifyCompositeEvidence,
  expectedCompositeReview,validateCompositeReview,verifyCompositeReview,expectedManifest,
  prepareManifest,verifyManifest,stagePaths,verifyClosedStage,checkSuccessorPredecessor,
  assertUnclaimed,verifyAllRequests,preflightCandidate,verifyStageReview,checkExactLiveRoute,runSuccessorStage};
