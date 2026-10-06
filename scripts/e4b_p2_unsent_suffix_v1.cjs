#!/usr/bin/env node
'use strict';
// Offline-prepared successor: send only DEV-053..060 of interrupted fresh2/P2.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const small=require('./small_local_repeat_admission.cjs');
const continuation=require('./small_local_e4b_on_interruption_continuation_v1.cjs');
const classifier=require('./local_prompt_execution_v1.cjs');
const predictor=require('./lmstudio_reasoning_benchmark.cjs');
const hostAdmission=require('./local_host_admission.cjs');

const ROOT=small.ROOT,ID=continuation.ID,PHASE=`${ID}/fresh2/P2`;
const SCHEMA='e4b-p2-unsent-suffix-v1',STAGE='suffix';
const OUTPUT=path.join(continuation.BASE,'p2-unsent-suffix-v1');
const MANIFEST=path.join(OUTPUT,'manifest.json');
const REVIEW=path.join(OUTPUT,'suffix.root-review.json');
const IDS=continuation.IDS,SUFFIX_IDS=IDS.slice(52);
const stable=JSON.stringify,hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const hashFile=small.hashFile,read=small.read,rows=small.rows;
const durable=(fd,value)=>{fs.writeSync(fd,stable(value)+'\n');fs.fsyncSync(fd);};
const rel=file=>small.rel(file);

function binding(file){
  const full=path.resolve(file);assert(full.startsWith(ROOT+path.sep),'Source outside repository');
  return {file:path.relative(ROOT,full),sha256:hashFile(full)};
}
function verifyBinding(value){
  assert.equal(hashFile(rel(value.file)),value.sha256,`Bound source changed: ${value.file}`);
}
function paths(base=OUTPUT){return {folder:base,
  claim:path.join(base,'suffix.claim.json'),journal:path.join(base,'suffix.journal.jsonl'),
  raw:path.join(base,'suffix.raw.jsonl'),records:path.join(base,'suffix.records.jsonl'),
  completion:path.join(base,'suffix.completion.json')};}
function assertUnclaimed(p=paths()){
  for(const [name,file] of Object.entries(p)) if(name!=='folder')
    assert(!fs.existsSync(file),`Suffix already claimed; no replay: ${file}`);
}

function verifyHistory(plan,planSha){
  const first=continuation.verifyStoppedPrefix(plan,planSha);
  assert.equal(first.failed_id,'DEV-039');assert.equal(first.saved_count,38);
  const previous=continuation.paths('fresh2','P2','suffix');
  const review=path.join(previous.folder,'suffix.root-review.json');
  for(const file of [...['claim','journal','raw','records','completion'].map(k=>previous[k]),review])
    assert(fs.existsSync(file),`Prior continuation evidence missing: ${file}`);
  const oldManifest=read(continuation.MANIFEST),oldSha=hashFile(continuation.MANIFEST);
  assert.deepEqual(oldManifest,continuation.expectedManifest(),'Prior continuation plan differs');
  const claim=read(previous.claim),done=read(previous.completion),receipt=read(review);
  assert.equal(claim.schema,continuation.SCHEMA+'-stage-claim');
  assert.equal(claim.phase,PHASE);assert.equal(claim.stage,'suffix');
  assert.equal(claim.manifest_sha256,oldSha);
  assert.equal(claim.controller_sha256,hashFile(path.join(ROOT,'scripts/small_local_e4b_on_interruption_continuation_v1.cjs')));
  assert.equal(claim.receipt_sha256,hashFile(review));
  assert.equal(receipt.approved,true);assert.equal(receipt.phase,PHASE);
  assert.deepEqual(receipt.ids,IDS.slice(39));
  assert.equal(receipt.reference_labels_read,false);
  assert.equal(done.status,'stopped');assert.equal(done.attempted,13);
  assert.equal(done.saved,12);assert.equal(done.invalid,0);
  for(const key of ['journal','raw','records']) assert.equal(done[`${key}_sha256`],hashFile(previous[key]));
  const selected=small.stageRows(plan,ID,'P2','development');
  const journal=rows(previous.journal),raw=rows(previous.raw),saved=rows(previous.records);
  assert.equal(journal.length,26);assert.equal(raw.length,13);assert.equal(saved.length,12);
  assert.deepEqual(raw.map(x=>x.id),IDS.slice(39,52));
  assert.deepEqual(saved.map(x=>x.id),IDS.slice(39,51));
  const attempts=new Set();
  for(let i=0;i<13;i++){
    const item=selected[39+i],sidecar=raw[i],start=journal[2*i],end=journal[2*i+1];
    assert.equal(item.id,IDS[39+i]);assert.equal(sidecar.id,item.id);
    assert(typeof sidecar.attempt_id==='string'&&sidecar.attempt_id&&!attempts.has(sidecar.attempt_id));
    attempts.add(sidecar.attempt_id);
    assert.equal(start.event,'started');assert.equal(start.id,item.id);
    assert.equal(start.attempt_id,sidecar.attempt_id);
    assert.equal(start.request_sha256,hash(stable(item.request)));
    assert.equal(end.id,item.id);assert.equal(end.attempt_id,sidecar.attempt_id);
    if(i<12){
      const record=saved[i];assert.equal(end.event,'finished');assert.equal(end.status,'ok');
      assert.equal(record.id,item.id);assert.equal(record.attempt_id,sidecar.attempt_id);
      assert.equal(record.request_sha256,hash(stable(item.request)));
      assert.equal(record.reference_labels_read,false);
      assert.deepEqual(record.decision,classifier.classifySdk(sidecar.result,{
        identifier:plan.configurations[ID].model_identifier,
        path:plan.configurations[ID].artifact_path,bytes:plan.configurations[ID].artifact_bytes,
        promptTokens:item.prompt_tokens,loadConfig:item.load_config,
        predictionConfig:item.prediction_config}));
      assert.equal(record.decision.status,'ok');
    }else{
      assert.equal(item.id,'DEV-052');assert.equal(end.event,'stopped_unknown');
      assert.equal(sidecar.code,'PREDICTION_TIMEOUT');
      assert.equal(sidecar.cancellationAcknowledged,true);assert(sidecar.partialResult);
      assert.equal(sidecar.result,null);
    }
  }
  const smoke=small.stagePaths(ID,'fresh2','P2','smoke');
  const inspection=path.join(smoke.folder,'smoke-inspection.json');
  const smokeDone=read(smoke.completion),inspectionValue=read(inspection);
  assert.equal(smokeDone.status,'completed');assert.equal(smokeDone.attempted,3);
  assert.equal(smokeDone.saved,3);assert.equal(smokeDone.invalid,0);
  assert.equal(inspectionValue.approved,true);assert.equal(inspectionValue.reference_labels_read,false);
  for(const key of ['journal','raw','records']){
    assert.equal(smokeDone[`${key}_sha256`],hashFile(smoke[key]));
    if(key!=='journal') assert.equal(inspectionValue[`${key}_sha256`],hashFile(smoke[key]));
  }
  return {original_unknown_ids:['DEV-039','DEV-052'],saved:50,
    never_sent_ids:SUFFIX_IDS,clean_repeat_eligible:false,
    original: first.bindings,
    continuation:{manifest:binding(continuation.MANIFEST),
      ...Object.fromEntries(['claim','journal','raw','records','completion']
        .map(k=>[k,binding(previous[k])])),review:binding(review)},
    smoke:{claim:binding(smoke.claim),completion:binding(smoke.completion),
      inspection:binding(inspection),records:binding(smoke.records)}};
}

function selectedRows(plan){
  const selected=small.stageRows(plan,ID,'P2','development').slice(52);
  assert.deepEqual(selected.map(x=>x.id),SUFFIX_IDS);
  return selected;
}
function contextLength(config){
  const fields=config.controls.load_config.fields;
  const context=fields.find(x=>x.key==='llm.load.contextLength')?.value;
  assert.equal(context,8192,'Frozen context differs');
  return context;
}
function outputReserve(config,plan){
  const selected=small.stageRows(plan,ID,'P2','development');
  const reserves=new Set(selected.map(x=>x.request.config.maxTokens));
  assert.equal(reserves.size,1,'Frozen output reserve differs among P2 requests');
  const reserve=[...reserves][0];
  assert(Number.isSafeInteger(reserve)&&reserve>0,'Frozen output reserve unavailable');
  return reserve;
}
async function renderRequest(model,request){
  const original=model.internalKVConfigStack;
  assert(original&&Array.isArray(original.layers)&&
    typeof model.predictionConfigInputToKVConfig==='function'&&
    typeof model.applyPromptTemplate==='function',
    'Pinned SDK config-aware prompt rendering unavailable');
  const override=model.predictionConfigInputToKVConfig(request.config);
  model.internalKVConfigStack={layers:[...original.layers,{layerName:'apiOverride',config:override}]};
  try{return await model.applyPromptTemplate(request.messages);}
  finally{model.internalKVConfigStack=original;}
}
async function verifyRequestRuntime(runtime,config,row,plan,protocol=null){
  protocol??={context:contextLength(config),reserve:outputReserve(config,plan),
    requestConfig:small.stageRows(plan,ID,'P2','development')[0].request.config};
  const model=runtime.model,info=await model.getModelInfo();
  assert.equal(info.instanceReference,runtime.instance,'Loaded instance changed during preflight');
  assert.equal(info.identifier,config.model_identifier);
  assert.equal(info.path,config.artifact_path);
  assert.equal(info.sizeBytes,config.artifact_bytes);
  assert.equal(info.contextLength,protocol.context);
  assert.equal(info.quantization?.name,'Q4_K_M');
  assert.equal(runtime.attestation.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(row.load_config,config.controls.load_config,'Frozen load settings differ');
  assert.deepEqual(row.prediction_config,config.controls.prediction_config,'Frozen prediction settings differ');
  assert.deepEqual(row.request.config,protocol.requestConfig,'Frozen request settings differ');
  assert.equal(hash(stable(row.request)),config.conditions.P2.requests[Number(row.id.slice(4))-1].sha256);
  const rendered=await renderRequest(model,row.request);
  assert.equal(typeof rendered,'string','SDK did not render frozen request');
  assert(typeof model.tokenize==='function','SDK read-only tokenizer unavailable');
  const tokenIds=await model.tokenize(rendered);
  assert(Array.isArray(tokenIds),'SDK tokenization failed');
  assert.equal(tokenIds.length,row.prompt_tokens,'Runtime prompt token count differs from frozen request');
  assert(tokenIds.length+protocol.reserve<=protocol.context,
    'Runtime prompt exceeds context with frozen output reserve');
  return {id:row.id,instance_reference:runtime.instance,request_sha256:hash(stable(row.request)),
    rendered_sha256:hash(Buffer.from(rendered,'utf8')),prompt_tokens:tokenIds.length,
    context:protocol.context,output_reserve:protocol.reserve,
    artifact_sha256:config.artifact_sha256};
}
async function verifyAllRequests(runtime,plan){
  const config=plan.configurations[ID],all=small.stageRows(plan,ID,'P2','development');
  assert.equal(all.length,60);
  const protocol={context:contextLength(config),reserve:all[0].request.config.maxTokens,
    requestConfig:all[0].request.config};
  assert.equal(protocol.reserve,outputReserve(config,plan));
  const measured=[];
  for(const row of all)measured.push(await verifyRequestRuntime(runtime,config,row,plan,protocol));
  assert.deepEqual(measured.map(x=>x.id),IDS);
  return measured;
}
async function verifySuffixRequests(runtime,plan){
  const config=plan.configurations[ID],selection=selectedRows(plan);
  const protocol={context:contextLength(config),reserve:outputReserve(config,plan),
    requestConfig:selection[0].request.config};
  const measured=[];
  for(const row of selection)measured.push(await verifyRequestRuntime(runtime,config,row,plan,protocol));
  return measured;
}
function expectedManifest(){
  const {plan,sha256}=small.verifyPlan(),config=plan.configurations[ID];
  const history=verifyHistory(plan,sha256),selection=selectedRows(plan);
  assert.deepEqual(selection.map(x=>hash(stable(x.request))),
    config.conditions.P2.requests.slice(52).map(x=>x.sha256));
  return {schema:SCHEMA,status:'offline_prepared_unapproved',approval:null,
    method:'descriptive-interrupted-series-unsent-suffix',clean_repeat_eligible:false,
    reference_labels_read:false,phase:PHASE,stage:STAGE,
    frozen:{plan:binding(small.PLAN),original_controller:binding(path.join(ROOT,'scripts/small_local_repeat_admission.cjs')),
      continuation_controller:binding(path.join(ROOT,'scripts/small_local_e4b_on_interruption_continuation_v1.cjs')),
      classifier:binding(path.join(ROOT,'scripts/local_prompt_execution_v1.cjs')),
      predictor:binding(path.join(ROOT,'scripts/lmstudio_reasoning_benchmark.cjs')),
      host_admission:binding(path.join(ROOT,'scripts/local_host_admission.cjs'))},
    controller:binding(__filename),history,
    suffix:{ids:SUFFIX_IDS,requests:config.conditions.P2.requests.slice(52),
      output_files:Object.fromEntries(Object.entries(paths()).filter(([k])=>k!=='folder')
        .map(([k,file])=>[k,path.relative(ROOT,file)]))},
    runtime:{model_identifier:config.model_identifier,artifact_path:config.artifact_path,
      artifact_sha256:config.artifact_sha256,artifact_bytes:config.artifact_bytes,
      quantization:'Q4_K_M',surface:'lmstudio_sdk',timeout_ms:config.timeout_ms,
      context:contextLength(config),output_reserve:outputReserve(config,plan),
      request_config_sha256:hash(stable(selection[0].request.config)),
      load_config_sha256:hash(stable(config.controls.load_config)),
      prediction_config_sha256:hash(stable(config.controls.prediction_config)),
      cache_policy:plan.policy.cache_policy,parent_runtime:plan.parent_runtime},
    policy:{unknown_ids:['DEV-039','DEV-052'],never_replay_ids:IDS.slice(0,52),
      invalid_output:'retain_and_continue',failure:'stop_without_retry',
      output_repair:false,smoke_replay:false,
      shared_lock:path.relative(ROOT,small.LOCK)}};
}
function normalized(manifest){return {...manifest,status:'offline_prepared_unapproved',approval:null};}
function verifyManifest(){
  const manifest=read(MANIFEST),expected=expectedManifest();
  assert(['offline_prepared_unapproved','approved'].includes(manifest.status));
  if(manifest.status==='approved'){
    assert.equal(manifest.approval?.independent_review,true);
    assert.equal(manifest.approval?.authorized_by_root,true);
    assert.equal(typeof manifest.approval?.reviewer,'string');
    assert(Number.isFinite(Date.parse(manifest.approval?.reviewed_utc)));
  }else assert.equal(manifest.approval,null);
  assert.deepEqual(normalized(manifest),expected,'Manifest differs from frozen evidence');
  return {manifest,manifestSha:hashFile(MANIFEST),plan:small.verifyPlan().plan};
}
function freeze(){
  assert(!fs.existsSync(MANIFEST),'Suffix manifest already exists');
  const value=expectedManifest();fs.mkdirSync(OUTPUT,{recursive:true});
  fs.writeFileSync(MANIFEST,stable(value)+'\n',{flag:'wx'});
  return hashFile(MANIFEST);
}

async function fetchRouteEvidence(fetcher=fetch,now=Date.now()){
  const endpoint='https://openrouter.ai/api/v1/models';
  const response=await fetcher(endpoint,{signal:AbortSignal.timeout(15000),headers:{accept:'application/json'}});
  assert.equal(response.status,200,'Live OpenRouter catalog unavailable');
  const raw=await response.text(),body=JSON.parse(raw);
  assert(Array.isArray(body.data)&&body.data.length>=100,'Live OpenRouter catalog incomplete');
  const matches=body.data.filter(model=>[model.id,model.name,model.canonical_slug,model.hugging_face_id]
    .some(value=>typeof value==='string'&&/gemma[\W_]*4[\W_]*e4b/i.test(value)));
  assert.equal(matches.length,0,`Exact Gemma 4 E4B hosted route needs review: ${matches.map(x=>x.id).join(', ')}`);
  return {raw,audit:{source:endpoint,retrieved_utc:new Date(now).toISOString(),http_status:200,
    raw_sha256:hash(raw),model_count:body.data.length,matches}};
}
function verifyRoute(audit,now=Date.now()){
  assert.equal(audit.source,'https://openrouter.ai/api/v1/models');
  assert.equal(audit.http_status,200);assert(audit.model_count>=100);
  assert.deepEqual(audit.matches,[]);
  const age=now-Date.parse(audit.retrieved_utc);
  assert(Number.isFinite(age)&&age>=0&&age<5*60*1000,'Exact hosted route audit must be fresh');
}
function verifyReview(file,ctx,currentHost,now=Date.now()){
  assert.equal(path.resolve(file),REVIEW,'Use fixed suffix root-review path');
  const receipt=read(file),config=ctx.plan.configurations[ID];
  assert.equal(receipt.kind,SCHEMA+'-root-review');
  assert.equal(receipt.approved,true);assert.equal(receipt.authorized_by_root,true);
  assert.equal(receipt.manifest_sha256,ctx.manifestSha);
  assert.equal(receipt.controller_sha256,ctx.manifest.controller.sha256);
  assert.equal(receipt.phase,PHASE);assert.equal(receipt.stage,STAGE);
  assert.deepEqual(receipt.ids,SUFFIX_IDS);
  assert.deepEqual(receipt.request_sha256,ctx.manifest.suffix.requests.map(x=>x.sha256));
  assert.equal(receipt.model_identifier,config.model_identifier);
  assert.equal(receipt.artifact_sha256,config.artifact_sha256);
  assert.equal(receipt.reference_labels_read,false);
  assert.equal(receipt.smoke_replayed,false);
  assert.equal(receipt.exact_openrouter_route_absent,true);
  for(const key of ['host_baseline','runtime_preflight','route_catalog','route_raw']){
    const fileKey=key+'_file',shaKey=key+'_sha256';
    assert.equal(hashFile(rel(receipt[fileKey])),receipt[shaKey],`${key} changed`);
  }
  const audit=read(rel(receipt.route_catalog_file));verifyRoute(audit,now);
  assert.equal(hashFile(rel(receipt.route_raw_file)),audit.raw_sha256);
  assert.equal(receipt.route_checked_utc,audit.retrieved_utc);
  const runtime=read(rel(receipt.runtime_preflight_file));
  assert.equal(runtime.artifact_sha256,config.artifact_sha256);
  assert.equal(runtime.instance_reference,receipt.instance_reference);
  assert.equal(runtime.request_count,60);
  assert.deepEqual(runtime.measurements.map(x=>x.id),IDS);
  assert.equal(hash(stable(runtime.measurements)),receipt.runtime_token_preflight.observed_sha256);
  assert.equal(receipt.runtime_token_preflight.request_count,60);
  assert.equal(receipt.runtime_token_preflight.requests_sha256,
    hash(stable(config.conditions.P2.requests)));
  assert.equal(receipt.runtime_token_preflight.context,ctx.manifest.runtime.context);
  assert.equal(receipt.runtime_token_preflight.output_reserve,ctx.manifest.runtime.output_reserve);
  assert.deepEqual(read(rel(receipt.host_baseline_file)),receipt.host_baseline);
  hostAdmission.verifyAfterStage(receipt.host_baseline,currentHost);
  return receipt;
}
function prepare(manifestSha,reviewPath,now=Date.now(),deps={}){
  const ctx=verifyManifest();assert.equal(ctx.manifestSha,manifestSha);
  assert.equal(ctx.manifest.status,'approved','Manifest awaits root approval');
  assertUnclaimed();
  const host=(deps.currentHost||hostAdmission.currentHost)();
  const review=verifyReview(reviewPath,ctx,host,now);
  return {...ctx,host,review,p:paths()};
}
async function preflight(deps={}){
  assert.equal(process.env.SMALL_LOCAL_HOST_LOCK_HELD,'1','Use locked preflight command');
  const ctx=verifyManifest();assert.equal(ctx.manifest.status,'approved','Manifest awaits root approval');
  assertUnclaimed();
  const host=(deps.currentHost||hostAdmission.currentHost)();
  const config=ctx.plan.configurations[ID];
  const runtime=await (deps.runtime||small.realRuntime)(ctx.plan,config);
  const info=await runtime.model.getModelInfo();
  assert.equal(info.instanceReference,runtime.instance);
  assert.equal(runtime.attestation.artifact_sha256,config.artifact_sha256);
  const measured=await (deps.verifyAll||verifyAllRequests)(runtime,ctx.plan);
  assert.equal(measured.length,60,'All 60 frozen P2 requests require runtime render/token checks');
  assert.deepEqual(measured.map(x=>x.id),IDS);
  const route=await (deps.routeEvidence||fetchRouteEvidence)();verifyRoute(route.audit);
  const stamp=new Date().toISOString().replace(/[-:.]/g,'');
  const hostFile=path.join(OUTPUT,`host-baseline-${stamp}.json`);
  const runtimeFile=path.join(OUTPUT,`runtime-preflight-${stamp}.json`);
  const routeRaw=path.join(OUTPUT,`route-catalog-${stamp}.raw.json`);
  const routeAudit=path.join(OUTPUT,`route-catalog-${stamp}.audit.json`);
  fs.writeFileSync(hostFile,JSON.stringify(host,null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(runtimeFile,JSON.stringify({artifact_sha256:config.artifact_sha256,
    instance_reference:runtime.instance,request_count:60,
    measurements:measured,attestation:runtime.attestation},null,2)+'\n',{flag:'wx'});
  fs.writeFileSync(routeRaw,route.raw,{flag:'wx'});
  fs.writeFileSync(routeAudit,JSON.stringify(route.audit,null,2)+'\n',{flag:'wx'});
  const candidate={kind:SCHEMA+'-root-review',approved:false,authorized_by_root:false,
    manifest_sha256:ctx.manifestSha,controller_sha256:ctx.manifest.controller.sha256,
    phase:PHASE,stage:STAGE,ids:SUFFIX_IDS,
    request_sha256:ctx.manifest.suffix.requests.map(x=>x.sha256),
    model_identifier:config.model_identifier,artifact_sha256:config.artifact_sha256,
    reference_labels_read:false,smoke_replayed:false,exact_openrouter_route_absent:true,
    host_baseline_file:path.relative(ROOT,hostFile),host_baseline_sha256:hashFile(hostFile),host_baseline:host,
    runtime_preflight_file:path.relative(ROOT,runtimeFile),runtime_preflight_sha256:hashFile(runtimeFile),
    instance_reference:runtime.instance,
    runtime_token_preflight:{request_count:60,
      requests_sha256:hash(stable(config.conditions.P2.requests)),
      observed_sha256:hash(stable(measured)),context:ctx.manifest.runtime.context,
      output_reserve:ctx.manifest.runtime.output_reserve},
    route_catalog_file:path.relative(ROOT,routeAudit),route_catalog_sha256:hashFile(routeAudit),
    route_raw_file:path.relative(ROOT,routeRaw),route_raw_sha256:hashFile(routeRaw),
    route_checked_utc:route.audit.retrieved_utc};
  const candidateFile=path.join(OUTPUT,`suffix-review-candidate-${stamp}.json`);
  fs.writeFileSync(candidateFile,JSON.stringify(candidate,null,2)+'\n',{flag:'wx'});
  return {candidate:path.relative(ROOT,candidateFile),ids:SUFFIX_IDS,approved:false};
}

async function runSuffix(manifestSha,reviewPath,deps={}){
  if(!deps.prepare) assert.equal(process.env.SMALL_LOCAL_HOST_LOCK_HELD,'1','Use locked run command');
  const state=(deps.prepare||prepare)(manifestSha,reviewPath,Date.now(),deps);
  const config=state.plan.configurations[ID],selection=selectedRows(state.plan),p=state.p;
  assert.deepEqual(selection.map(x=>hash(stable(x.request))),state.manifest.suffix.requests.map(x=>x.sha256));
  const runtime=await (deps.runtime||small.realRuntime)(state.plan,config);
  assert.equal(runtime.instance,state.review.instance_reference,'Loaded model instance changed since review');
  assert.equal(runtime.attestation.artifact_sha256,config.artifact_sha256);
  const observed=await (deps.verifySuffix||verifySuffixRequests)(runtime,state.plan);
  const reviewed=state.reviewedMeasurements??
    read(rel(state.review.runtime_preflight_file)).measurements.slice(52);
  assert.equal(observed.length,8,'All eight suffix prompts require runtime preflight');
  assert.deepEqual(observed,reviewed,'Suffix runtime rendering or token count changed since root review');
  let route=await (deps.routeEvidence||fetchRouteEvidence)();verifyRoute(route.audit);
  (deps.verifyAfterStage||hostAdmission.verifyAfterStage)(state.host,
    (deps.currentHost||hostAdmission.currentHost)());
  assertUnclaimed(p);fs.mkdirSync(p.folder,{recursive:true});
  fs.writeFileSync(p.claim,stable({schema:SCHEMA+'-claim',phase:PHASE,stage:STAGE,ids:SUFFIX_IDS,
    manifest_sha256:manifestSha,controller_sha256:state.manifest.controller.sha256,
    review_sha256:hashFile(reviewPath),runtime_attestation:runtime.attestation,
    route_audit:route.audit,host_baseline:state.host,started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  let journal,raw,records;
  try{journal=fs.openSync(p.journal,'wx');raw=fs.openSync(p.raw,'wx');records=fs.openSync(p.records,'wx');}
  catch(error){for(const fd of [journal,raw,records]) if(fd!==undefined)fs.closeSync(fd);throw error;}
  let status='stopped',reason=null,invalid=0,hostAfter=null,hostCheck=null;
  try{
    for(const item of selection){
      if(Date.now()-Date.parse(route.audit.retrieved_utc)>=5*60*1000)
        route=await (deps.routeEvidence||fetchRouteEvidence)();
      verifyRoute(route.audit);
      const info=await runtime.model.getModelInfo();
      assert.equal(info.instanceReference,runtime.instance,'Loaded model instance changed');
      assert.equal(info.identifier,config.model_identifier);assert.equal(info.path,config.artifact_path);
      const attempt=crypto.randomUUID(),requestHash=hash(stable(item.request));
      durable(journal,{event:'started',attempt_id:attempt,id:item.id,request_sha256:requestHash,at:new Date().toISOString()});
      const started=process.hrtime.bigint();let result;
      try{result=await (deps.predict||predictor.predictWithTimeout)(runtime.model,
        item.request.messages,item.request.config,config.timeout_ms);}
      catch(error){
        durable(raw,{attempt_id:attempt,id:item.id,error:String(error.message),code:error.code??null,
          cancellationAcknowledged:error.cancellationAcknowledged??null,
          cancellationError:error.cancellationError??null,partialResult:error.partialResult??null,
          elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9,result:null});
        durable(journal,{event:'stopped_unknown',attempt_id:attempt,id:item.id,at:new Date().toISOString()});
        throw error;
      }
      durable(raw,{attempt_id:attempt,id:item.id,result:{content:result?.content??null,
        nonReasoningContent:result?.nonReasoningContent??null,reasoningContent:result?.reasoningContent??null,
        stats:result?.stats??null,modelInfo:result?.modelInfo??null,
        loadConfig:result?.loadConfig??null,predictionConfig:result?.predictionConfig??null},
        elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9});
      const decision=classifier.classifySdk(result,{identifier:config.model_identifier,
        path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:item.prompt_tokens,
        loadConfig:item.load_config,predictionConfig:item.prediction_config});
      durable(records,{id:item.id,attempt_id:attempt,request_sha256:requestHash,decision,
        reference_labels_read:false,finished_utc:new Date().toISOString()});
      durable(journal,{event:'finished',attempt_id:attempt,id:item.id,status:decision.status,at:new Date().toISOString()});
      if(decision.status==='invalid_output')invalid++;
      else if(decision.status!=='ok')throw Error(`Stopped on ${decision.status} at ${item.id}`);
    }
    hostAfter=(deps.currentHost||hostAdmission.currentHost)();
    hostCheck=(deps.verifyAfterStage||hostAdmission.verifyAfterStage)(state.host,hostAfter);
    status='completed';
  }catch(error){reason=String(error.message);throw error;}
  finally{
    if(hostAfter===null){
      try{hostAfter=(deps.currentHost||hostAdmission.currentHost)();
        hostCheck=(deps.verifyAfterStage||hostAdmission.verifyAfterStage)(state.host,hostAfter);}
      catch(error){hostCheck={host_unchanged:false,error:String(error.message)};}
    }
    for(const fd of [journal,raw,records])fs.closeSync(fd);
    fs.writeFileSync(p.completion,stable({schema:SCHEMA+'-completion',phase:PHASE,stage:STAGE,
      status,reason,attempted:rows(p.journal).filter(x=>x.event==='started').length,
      saved:rows(p.records).length,invalid,
      unknown_ids:rows(p.journal).filter(x=>x.event==='stopped_unknown').map(x=>x.id),
      original_unknown_ids:['DEV-039','DEV-052'],clean_repeat_eligible:false,
      host_after:hostAfter,host_check:hostCheck,
      journal_sha256:hashFile(p.journal),raw_sha256:hashFile(p.raw),records_sha256:hashFile(p.records),
      finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  }
  return read(p.completion);
}
async function main(argv){
  const [action,...args]=argv;
  if(action==='preview'){const m=expectedManifest();console.log(stable({phase:m.phase,ids:m.suffix.ids,
    request_sha256:m.suffix.requests.map(x=>x.sha256),history:m.history}));return;}
  if(action==='freeze'){console.log(freeze());return;}
  if(action==='verify'){const ctx=verifyManifest();console.log(stable({status:ctx.manifest.status,
    manifest_sha256:ctx.manifestSha,ids:ctx.manifest.suffix.ids}));return;}
  if(action==='preflight'||action==='run'){
    execFileSync('python3',['-c',small.lockCode,small.LOCK,process.execPath,__filename,
      action==='run'?'internal-run':'internal-preflight',...args],{stdio:'inherit'});return;
  }
  if(action==='internal-preflight'){console.log(stable(await preflight()));return;}
  if(action==='internal-run'){
    assert.equal(args.length,2,'Require manifest SHA and root review path');
    await runSuffix(args[0],args[1]);return;
  }
  throw Error('Use preview, freeze, verify, preflight, or run');
}
if(require.main===module)main(process.argv.slice(2)).catch(error=>{console.error(error.stack||error);process.exitCode=1;});
module.exports={ROOT,ID,PHASE,SCHEMA,STAGE,OUTPUT,MANIFEST,REVIEW,IDS,SUFFIX_IDS,
  binding,verifyBinding,paths,assertUnclaimed,verifyHistory,selectedRows,expectedManifest,
  verifyManifest,freeze,contextLength,outputReserve,renderRequest,verifyRequestRuntime,
  verifyAllRequests,verifySuffixRequests,fetchRouteEvidence,verifyRoute,verifyReview,
  prepare,preflight,runSuffix};
