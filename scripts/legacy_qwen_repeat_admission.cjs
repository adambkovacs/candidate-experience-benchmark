#!/usr/bin/env node
// Offline preparation is read-only. The run command requires a frozen plan and a fresh reviewed receipt.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {URL} = require('node:url');
const small = require('./small_local_repeat_admission.cjs');
const parent = require('./local_prompt_execution_v1.cjs');
const frozen = require('./frozen_prompt_variants.cjs');
const predictor = require('./lmstudio_reasoning_benchmark.cjs');

const {ROOT, LOCK, hash, hashFile, read, rows, rel} = small;
const PLAN = path.join(ROOT, 'results/repeatability-v1/legacy-qwen-fresh3-v1/manifest.json');
const OUTPUT = path.join(ROOT, 'results/repeatability-v1/legacy-qwen-fresh3-v1');
const AUDIT = 'results/route-audits/legacy-six-local-20260929/catalog-audit.json';
const PARENT_MANIFEST = 'results/local-prompt-exact-v1/manifest.json';
const Q06_MANIFEST = 'results/qwen06-prompt-exact-v1/manifest.json';
const IDS = Object.freeze([
  'qwen3-0.6b-q4km-nonthinking', 'qwen3-0.6b-sdk-thinking-on',
  'qwen3-0.6b-sdk-thinking-off', 'qwen3-1.7b-sdk-thinking-on',
  'qwen3-1.7b-sdk-thinking-off', 'qwen3.5-4b-sdk-thinking-on',
]);
const SOURCES = Object.freeze({
  [IDS[0]]: {p0:'results/qwen3-0.6b-q4_k_m-2026-09-21/development-requests.jsonl',
    historical:'results/qwen3-0.6b-q4_k_m-2026-09-21/manifest.json',
    p1:'results/local-prompt-exact-v1/qwen3-0.6b-q4km-nonthinking/P1/development.jsonl',
    p2:'results/local-prompt-exact-v1/qwen3-0.6b-q4km-nonthinking/P2/development.jsonl'},
  [IDS[1]]: {p0:'results/qwen3-0.6b-sdk-thinking-2026-09-21/development.jsonl',
    historical:'results/qwen3-0.6b-sdk-thinking-2026-09-21/manifest.json',
    p1:'results/qwen06-prompt-exact-v1/thinking-on-P1/development.jsonl',
    p2:'results/qwen06-prompt-exact-v1/thinking-on-P2/development.jsonl'},
  [IDS[2]]: {p0:'results/qwen3-0.6b-sdk-nonthinking-2026-09-21/development.jsonl',
    historical:'results/qwen3-0.6b-sdk-nonthinking-2026-09-21/manifest.json',
    p1:'results/qwen06-prompt-exact-v1/thinking-off-P1/development.jsonl',
    p2:'results/qwen06-prompt-exact-v1/thinking-off-P2/development.jsonl'},
  [IDS[3]]: {p0:'results/qwen3-1.7b-2026-09-21/thinking-development.jsonl',
    historical:'results/qwen3-1.7b-2026-09-21/thinking-manifest.json',
    p1:'results/local-prompt-exact-v1/qwen3-1.7b-sdk-thinking-on/P1/development.jsonl',
    p2:'results/local-prompt-exact-v1/qwen3-1.7b-sdk-thinking-on/P2/development.jsonl'},
  [IDS[4]]: {p0:'results/qwen3-1.7b-2026-09-21/nonthinking-development.jsonl',
    historical:'results/qwen3-1.7b-2026-09-21/nonthinking-manifest.json',
    p1:'results/local-prompt-exact-v1/qwen3-1.7b-sdk-thinking-off/P1/development.jsonl',
    p2:'results/local-prompt-exact-v1/qwen3-1.7b-sdk-thinking-off/P2/development.jsonl'},
  [IDS[5]]: {p0:'results/qwen3.5-4b-2026-09-21/thinking-development.jsonl',
    historical:'results/qwen3.5-4b-2026-09-21/thinking-manifest.json',
    p1:'results/local-prompt-remaining-v2/development.jsonl',
    p2:'results/local-prompt-exact-v1/qwen3.5-4b-sdk-thinking-on/P2/development.jsonl'},
});
const stable = JSON.stringify;
const expectedIds = Array.from({length:60}, (_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);
const fileBinding = file => ({file,sha256:hashFile(rel(file))});
const timeout = id => id===IDS[0] ? 120000 : 600000;
const reserve = id => id===IDS[0] ? 512 : 4096;
const surface = id => id===IDS[0] ? 'local_http' : 'lmstudio_sdk';
const sequence = (id, pass) => {
  const first = id===IDS[0] ? ['P0','P1','P2'] : ['P0','P2','P1'];
  const offset = Number(pass.slice(-1))-1;
  return first.map((_,i)=>first[(i+offset)%3]);
};

function canonicalInputs() {
  const input = rows(rel('data/pilot/inputs.jsonl'));
  assert.deepEqual(input.map(x=>x.id),expectedIds);
  return input;
}

function sourceRows(id, condition) {
  const source = SOURCES[id];
  assert(source && ['P0','P1','P2'].includes(condition));
  return rows(rel(source[condition.toLowerCase()]));
}

function baseline(id) {
  const saved = sourceRows(id,'P0');
  assert.equal(saved.length,60);
  const inputs = canonicalInputs();
  return saved.map((row,i)=>{
    const request = id===IDS[0] ? row.body : row.request;
    assert(request && Array.isArray(request.messages));
    assert.deepEqual(request.messages.map(x=>x.role),['system','user']);
    assert.equal(JSON.parse(request.messages[1].content).feedback,inputs[i].feedback);
    if(id!==IDS[0]) {
      assert.equal(row.id,expectedIds[i]);
      assert.equal(row.reference_labels_read,false);
    }
    return request;
  });
}

function countRows(id) {
  const parentManifest = read(rel(PARENT_MANIFEST));
  const q06Manifest = read(rel(Q06_MANIFEST));
  const file = id===IDS[0] ? parentManifest.configs[id].counts_file :
    id.startsWith('qwen3-0.6b-sdk') ? q06Manifest.counts_file : parentManifest.configs[id].counts_file;
  assert(file,`No token preflight for ${id}`);
  const all = file.endsWith('.json') ? read(rel(file)) : rows(rel(file));
  const selected = all.filter(x=>x.configuration===id);
  assert.equal(selected.length,180,`Incomplete token preflight for ${id}`);
  return {file, selected};
}

function constructRequests(id) {
  const bases = baseline(id), inputs=canonicalInputs(), {file:countFile,selected:counts}=countRows(id);
  const old = read(rel(SOURCES[id].historical));
  assert.equal(old.artifact.quantization,'Q4_K_M');
  assert.equal(old.prompt_cache.enabled,true);
  assert.equal(old.prompt_cache.size_limit_mib,8192);
  const output={};
  for(const condition of ['P0','P1','P2']) {
    const historical=sourceRows(id,condition);
    if(id!==IDS[5] || condition!=='P2') assert.equal(historical.length,60);
    const byId=new Map(historical.map((row,i)=>[id===IDS[0] && condition==='P0' ? expectedIds[i] : row.id,row]));
    const requests=bases.map((base,i)=>{
      const request=structuredClone(base);
      request.messages[0].content=frozen.compose_instruction(base.messages[0].content,condition,
        {role:'system',parent_baseline_id:id}).instruction;
      const saved=byId.get(expectedIds[i]);
      if(saved) assert.deepEqual(request,id===IDS[0] && condition==='P0' ? saved.body : saved.request,
        `Historical request differs: ${id}/${condition}/${expectedIds[i]}`);
      const count=counts.find(x=>x.variant===condition && x.id===expectedIds[i]);
      assert(count && count.context===8192 && count.output_reserve===reserve(id) && count.fits_context===true);
      if(saved?.expected_prompt_tokens!==undefined) assert.equal(count.prompt_tokens,saved.expected_prompt_tokens);
      if(saved?.stats?.promptTokensCount!==undefined) assert.equal(count.prompt_tokens,saved.stats.promptTokensCount);
      assert.equal(JSON.parse(request.messages[1].content).feedback,inputs[i].feedback);
      assert.equal(request.messages.length,2);
      return {id:expectedIds[i],sha256:hash(stable(request)),prompt_tokens:count.prompt_tokens,
        rendered_sha256:count.rendered_sha256};
    });
    output[condition]={requests,history:{file:SOURCES[id][condition.toLowerCase()],sha256:hashFile(rel(SOURCES[id][condition.toLowerCase()]))}};
  }
  return {conditions:output,count_file:fileBinding(countFile),historical_manifest:fileBinding(SOURCES[id].historical),
    artifact_sha256:old.artifact.sha256,artifact_bytes:old.artifact.bytes};
}

function makePlan() {
  const parentManifest=read(rel(PARENT_MANIFEST));
  const configurations={};
  for(const id of IDS) {
    const prepared=constructRequests(id);
    const p0=baseline(id)[0], history=sourceRows(id,'P0')[0];
    const parentConfig=parentManifest.configs[id];
    const modelIdentifier=id===IDS[0] ? p0.model : history.requested_model;
    const artifactPath=parentConfig?.artifact_path ?? read(rel(Q06_MANIFEST)).model.path;
    assert.equal(prepared.artifact_sha256,parentConfig?.artifact_sha256 ?? read(rel(Q06_MANIFEST)).model.artifact_sha256);
    configurations[id]={surface:surface(id),model_identifier:modelIdentifier,artifact_path:artifactPath,
      artifact_sha256:prepared.artifact_sha256,artifact_bytes:prepared.artifact_bytes,
      historical_manifest:prepared.historical_manifest,count_file:prepared.count_file,
      timeout_ms:timeout(id),context:8192,output_reserve:reserve(id),
      schedule:['fresh1','fresh2','fresh3'].map(name=>({name,conditions:sequence(id,name)})),
      controls:id===IDS[0] ? {http_response_format:p0.response_format,sampling:{temperature:p0.temperature,
        max_tokens:p0.max_tokens,stream:p0.stream}} : {request_config:p0.config,
        load_config:history.load_config,prediction_config:history.prediction_config,
        template_sha256:history.template_sha256 ?? null},
      conditions:prepared.conditions};
  }
  const sourceFiles=new Set(['data/pilot/inputs.jsonl','schemas/judgments.schema.json',
    'scripts/frozen_prompt_variants.cjs','scripts/local_prompt_execution_v1.cjs',
    'scripts/small_local_repeat_admission.cjs','scripts/lmstudio_reasoning_benchmark.cjs',
    PARENT_MANIFEST,Q06_MANIFEST,AUDIT]);
  for(const x of Object.values(SOURCES)) Object.values(x).forEach(file=>sourceFiles.add(file));
  return {schema:'legacy-qwen-fresh3-admission-v1',status:'offline_prepared_unapproved',
    reference_labels_used_for_requests:false,historical_predictions_used_for_requests:false,
    controller_sha256:hashFile(__filename),source_sha256:Object.fromEntries([...sourceFiles].map(f=>[f,hashFile(rel(f))])),
    parent_runtime:parentManifest.runtime,configurations,
    policy:{denominator:60,smoke_ids:expectedIds.slice(0,3),cache_policy:{enabled:true,size_limit_mib:8192},
      seed_policy:'uncontrolled_sampling_no_seed',invalid_output:'retain_and_continue',
      service_or_control_failure:'stop_without_retry',lock_path:path.relative(ROOT,LOCK)}};
}

function verifyPlan() {
  const actual=read(PLAN),expected=makePlan();
  assert.deepEqual(actual,expected,'Frozen six-Qwen plan differs from sources, controller or protocol');
  return {plan:actual,sha256:hashFile(PLAN)};
}

function phaseInfo(plan,id,pass,condition) {
  const config=plan.configurations[id];
  assert(config && IDS.includes(id),'Configuration not in plan');
  const preceding=[];
  for(const entry of config.schedule) for(const c of entry.conditions) {
    if(entry.name===pass && c===condition) return {config,preceding};
    preceding.push(`${entry.name}/${c}`);
  }
  throw Error('Phase not in plan');
}

function stagePaths(id,pass,condition,stage) {
  assert(['smoke','development'].includes(stage));
  const folder=path.join(OUTPUT,id,pass,condition);
  return {folder,claim:path.join(folder,`${stage}.claim.json`),journal:path.join(folder,`${stage}.journal.jsonl`),
    raw:path.join(folder,`${stage}.raw.jsonl`),records:path.join(folder,`${stage}.records.jsonl`),
    completion:path.join(folder,`${stage}.completion.json`)};
}

function stageRows(plan,id,condition,stage) {
  assert(['smoke','development'].includes(stage));
  const prepared=constructRequests(id),expected=plan.configurations[id];
  assert.deepEqual(prepared.conditions,expected.conditions,'Request source drift');
  const bases=baseline(id), ids=stage==='smoke' ? expectedIds.slice(0,3) : expectedIds;
  return ids.map(key=>{
    const i=expectedIds.indexOf(key),request=structuredClone(bases[i]);
    request.messages[0].content=frozen.compose_instruction(bases[i].messages[0].content,condition,
      {role:'system',parent_baseline_id:id}).instruction;
    const frozenRow=expected.conditions[condition].requests[i];
    assert.equal(hash(stable(request)),frozenRow.sha256,'Frozen request differs');
    return {id:key,request,prompt_tokens:frozenRow.prompt_tokens,
      rendered_sha256:frozenRow.rendered_sha256};
  });
}

function checkPredecessor(plan,id,pass,condition,stage,paths=stagePaths) {
  const {preceding}=phaseInfo(plan,id,pass,condition);
  for(const prior of preceding) {
    const [p,c]=prior.split('/'),files=paths(id,p,c,'development');
    assert(fs.existsSync(files.completion),`Prior phase incomplete: ${prior}`);
    const terminal=read(files.completion);
    assert.equal(terminal.status,'completed',`Prior phase incomplete: ${prior}`);
    assert.equal(terminal.attempted,60);
    assert.equal(terminal.saved,60);
    for(const field of ['journal','raw','records']) assert.equal(hashFile(files[field]),terminal[`${field}_sha256`]);
  }
  if(stage==='smoke') return null;
  const smoke=paths(id,pass,condition,'smoke');
  assert(fs.existsSync(smoke.completion),'Smoke not complete');
  const terminal=read(smoke.completion);
  assert.equal(terminal.status,'completed');
  assert.equal(terminal.attempted,3);
  assert.equal(terminal.saved,3);
  for(const field of ['journal','raw','records']) assert.equal(hashFile(smoke[field]),terminal[`${field}_sha256`]);
  const inspection=path.join(smoke.folder,'smoke-inspection.json');
  assert(fs.existsSync(inspection),'Independent smoke inspection missing');
  const reviewed=read(inspection);
  assert.equal(reviewed.kind,'legacy-qwen-three-record-smoke-inspection-v1');
  assert.equal(reviewed.approved,true);
  assert.equal(reviewed.raw_sha256,terminal.raw_sha256);
  assert.equal(reviewed.records_sha256,terminal.records_sha256);
  assert.deepEqual(rows(smoke.records).map(x=>x.decision.status),['ok','ok','ok']);
  return hashFile(inspection);
}

function checkReceipt(receipt,planSha,phase,stage,config,smokeHash,now=Date.now()) {
  assert.equal(receipt.kind,'root-reviewed-legacy-qwen-stage-v1');
  assert.equal(receipt.approved,true);
  assert.equal(receipt.plan_sha256,planSha);
  assert.equal(receipt.controller_sha256,hashFile(__filename));
  assert.equal(receipt.phase,phase);
  assert.equal(receipt.stage,stage);
  assert.equal(receipt.model_identifier,config.model_identifier);
  assert.equal(receipt.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(receipt.cache_policy,{enabled:true,size_limit_mib:8192});
  assert.equal(receipt.reference_labels_read,false);
  assert.equal(receipt.exact_openrouter_route_absent,true);
  assert.match(receipt.route_catalog_file,/^results\/route-audits\/[a-zA-Z0-9_-]+\/catalog-audit\.json$/);
  assert.equal(hashFile(rel(receipt.route_catalog_file)),receipt.route_catalog_sha256);
  const audit=read(rel(receipt.route_catalog_file));
  assert.equal(audit.source,'https://openrouter.ai/api/v1/models');
  assert.equal(audit.http_status,200);
  assert.deepEqual(audit.catalog_matches,[]);
  const family=config.model_identifier.includes('qwen3.5') ? 'Qwen3.5-4B' :
    config.model_identifier.includes('1.7') ? 'Qwen3-1.7B' : 'Qwen3-0.6B';
  assert.equal(audit.exact_family_decisions?.[family]?.catalog_id_found,false);
  const rawCatalog=path.posix.join(path.posix.dirname(receipt.route_catalog_file),'catalog.raw.json');
  assert.equal(hashFile(rel(rawCatalog)),audit.raw_sha256);
  assert.equal(receipt.route_checked_utc,audit.retrieved_utc);
  const age=now-Date.parse(audit.retrieved_utc);
  assert(age>=0 && age<=5*60*1000,'Route attestation must be fresh (five minutes)');
  if(stage==='development') assert.equal(receipt.smoke_inspection_sha256,smokeHash);
  assert.equal(receipt.gpu_available,true);
  assert.equal(receipt.capacity_reviewed,true);
  assert.equal(receipt.runtime_token_preflight?.phase,phase);
  assert.equal(receipt.runtime_token_preflight?.model_identifier,config.model_identifier);
  assert.equal(receipt.runtime_token_preflight?.artifact_sha256,config.artifact_sha256);
  assert.equal(receipt.runtime_token_preflight?.context,8192);
  assert.equal(receipt.runtime_token_preflight?.output_reserve,config.output_reserve);
  assert.equal(receipt.runtime_token_preflight?.request_count,60);
  assert.equal(receipt.runtime_token_preflight?.requests_sha256,
    hash(stable(config.conditions[phase.split('/')[2]].requests)));
  // The receipt identifies the intended request set. Only a live model measurement below admits dispatch.
}

const routeFamilies = ['qwen306b','qwen317b','qwen354b'];
async function checkLiveRoute(fetcher=fetch,now=Date.now()) {
  const endpoint='https://openrouter.ai/api/v1/models';
  const response=await fetcher(new URL(endpoint),{signal:AbortSignal.timeout(15000),headers:{accept:'application/json'}});
  assert.equal(response.status,200,'Live OpenRouter route audit unavailable');
  const body=await response.json();
  assert(Array.isArray(body.data) && body.data.length>=100,'Live OpenRouter catalog malformed or incomplete');
  const matches=body.data.filter(model=>routeFamilies.some(family=>
    [model.id,model.name,model.canonical_slug,model.hugging_face_id].some(value=>
      typeof value==='string' && value.toLowerCase().replace(/[^a-z0-9]/g,'').includes(family))));
  assert.equal(matches.length,0,`Exact Qwen hosted route needs review: ${matches.map(x=>x.id).join(', ')}`);
  return {checked_ms:now,source:endpoint,model_count:body.data.length};
}

function verifyHttpThinking(logText,loadEvidence,instance) {
  assert(loadEvidence && typeof loadEvidence==='object','Current HTTP load evidence unavailable');
  assert.equal(loadEvidence.instance_reference,instance,'HTTP load evidence is for another instance');
  const lines=logText.split('\n');
  const from=loadEvidence.cache_line-1,through=loadEvidence.instance_line-1;
  assert(Number.isSafeInteger(from)&&Number.isSafeInteger(through)&&through>from,
    'Current HTTP load log boundary unavailable');
  const observations=lines.slice(from,through+1).filter(line=>/init: chat template, thinking = /.test(line));
  assert.equal(observations.length,1,'Current HTTP thinking initialization is unavailable or ambiguous');
  assert.match(observations[0],/init: chat template, thinking = 0\s*$/,
    'Current HTTP thinking initialization differs from historical nonthinking control');
  return {instance_reference:instance,log_sha256:hash(logText),line:from+lines.slice(from,through+1).findIndex(x=>x===observations[0])+1};
}

function recentLoadLogs(directory) {
  const files=fs.readdirSync(directory,{withFileTypes:true}).filter(x=>x.isDirectory())
    .flatMap(month=>fs.readdirSync(path.join(directory,month.name))
      .filter(name=>name.endsWith('.log')).map(name=>path.join(directory,month.name,name)));
  const recent=files.map(file=>({file,mtime:fs.statSync(file).mtimeMs}))
    .sort((a,b)=>b.mtime-a.mtime).slice(0,10).reverse();
  assert(recent.length,'Current LM Studio load logs unavailable');
  return recent.map(x=>fs.readFileSync(x.file,'utf8')).join('\n');
}

function checkCurrentHttpThinking(plan,runtime) {
  const directory=path.join(path.dirname(plan.parent_runtime.models_dir),'server-logs');
  return verifyHttpThinking(recentLoadLogs(directory),runtime.attestation?.load_evidence,runtime.instance);
}

async function verifyRequestRuntime(runtime,config,row) {
  const model=runtime.model;
  assert(typeof model.applyPromptTemplate==='function' && typeof model.tokenize==='function',
    'Loaded runtime has no read-only render/token API');
  const info=await model.getModelInfo();
  assert(info && info.instanceReference===runtime.instance && info.identifier===config.model_identifier &&
    info.path===config.artifact_path && info.sizeBytes===config.artifact_bytes &&
    info.contextLength===config.context && info.quantization?.name==='Q4_K_M',
    'Loaded runtime artifact or context differs');
  assert.equal(runtime.attestation?.artifact_sha256,config.artifact_sha256,'Loaded artifact hash unverified');
  const rendered=config.surface==='lmstudio_sdk' ?
    await renderSdkRequest(model,row.request) : await model.applyPromptTemplate(row.request.messages);
  assert.equal(typeof rendered,'string','Runtime did not render request');
  const renderedHash=hash(Buffer.from(rendered,'utf8'));
  assert.equal(renderedHash,row.rendered_sha256,'Runtime rendered prompt differs from frozen request');
  const tokenIds=await model.tokenize(rendered);
  assert(Array.isArray(tokenIds),'Runtime did not tokenize rendered request');
  assert.equal(tokenIds.length,row.prompt_tokens,'Runtime prompt token count differs from frozen request');
  assert(tokenIds.length+config.output_reserve<=config.context,'Runtime prompt exceeds context with output reserve');
  return {instance_reference:runtime.instance,request_sha256:hash(stable(row.request)),
    rendered_sha256:renderedHash,prompt_tokens:tokenIds.length,artifact_sha256:config.artifact_sha256};
}

// SDK 1.5.0 respond() appends this converted apiOverride layer. Its read-only
// applyPromptTemplate() RPC uses the handle stack, so supply the identical stack
// for this one awaited call and restore the original reference even on failure.
async function renderSdkRequest(model,request) {
  const original=model.internalKVConfigStack;
  assert(original && Array.isArray(original.layers) &&
    typeof model.predictionConfigInputToKVConfig==='function',
  'Pinned SDK config-aware prompt rendering unavailable');
  const override=model.predictionConfigInputToKVConfig(request.config);
  model.internalKVConfigStack={layers:[...original.layers,{layerName:'apiOverride',config:override}]};
  try { return await model.applyPromptTemplate(request.messages); }
  finally { model.internalKVConfigStack=original; }
}

function recoverUnsentStage(paths,phase,stage) {
  assert(fs.existsSync(paths.claim),'No stage claim to recover');
  assert(!fs.existsSync(paths.completion),'Stage already has a completion');
  const claim=read(paths.claim);
  assert.equal(claim.phase,phase,'Claim is for another phase');
  assert.equal(claim.stage,stage,'Claim is for another stage');
  const journal=fs.existsSync(paths.journal)?rows(paths.journal):[];
  assert.equal(journal.length,0,'Journal evidence forbids no-send recovery');
  for(const file of [paths.raw,paths.records])
    assert(!fs.existsSync(file)||fs.statSync(file).size===0,'Output evidence forbids no-send recovery');
  const completion={phase,stage,status:'stopped',reason:'initialization_failed_no_send',
    attempted:0,saved:0,invalid:0,
    journal_sha256:fs.existsSync(paths.journal)?hashFile(paths.journal):null,
    raw_sha256:fs.existsSync(paths.raw)?hashFile(paths.raw):null,
    records_sha256:fs.existsSync(paths.records)?hashFile(paths.records):null,
    finished_utc:new Date().toISOString()};
  fs.writeFileSync(paths.completion,stable(completion)+'\n',{flag:'wx'});
  return completion;
}

function durable(fd,value) { fs.writeSync(fd,stable(value)+'\n'); fs.fsyncSync(fd); }

async function runStage(plan,planSha,id,pass,condition,stage,receiptPath,deps={}) {
  const phase=`${id}/${pass}/${condition}`, {config}=phaseInfo(plan,id,pass,condition);
  const paths=(deps.paths||stagePaths)(id,pass,condition,stage);
  const smokeHash=(deps.predecessor||checkPredecessor)(plan,id,pass,condition,stage);
  (deps.admit||checkReceipt)(read(receiptPath),planSha,phase,stage,config,smokeHash);
  const selected=stageRows(plan,id,condition,stage);
  const runtime=await (deps.runtime||small.realRuntime)(plan,config);
  const checkRoute=deps.routeAudit||checkLiveRoute;
  const checkRequest=deps.verifyRequest||verifyRequestRuntime;
  let route=await checkRoute();
  if(config.surface==='local_http')
    (deps.httpThinking||checkCurrentHttpThinking)(plan,runtime);
  const preflight=[];
  for(const row of selected) preflight.push(await checkRequest(runtime,config,row));
  for(const file of Object.values(paths).filter(x=>x!==paths.folder))
    assert(!fs.existsSync(file),'Phase already claimed; no replay');
  fs.mkdirSync(paths.folder,{recursive:true});
  fs.writeFileSync(paths.claim,stable({phase,stage,plan_sha256:planSha,
    controller_sha256:hashFile(__filename),receipt_sha256:hashFile(receiptPath),
    runtime_attestation:runtime.attestation,route_audit:route,
    runtime_preflight_sha256:hash(stable(preflight)),started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  let journal,raw,records;
  const openOutput=deps.openOutput||fs.openSync;
  try {
    journal=openOutput(paths.journal,'wx');
    raw=openOutput(paths.raw,'wx');
    records=openOutput(paths.records,'wx');
  } catch(error) {
    for(const fd of [journal,raw,records]) if(fd!==undefined) fs.closeSync(fd);
    try { recoverUnsentStage(paths,phase,stage); }
    catch(recoveryError) { error.recoveryError=recoveryError; }
    throw error;
  }
  let status='stopped',reason=null,invalid=0;
  try {
    for(const row of selected) {
      if(!Number.isFinite(route.checked_ms)||Date.now()-route.checked_ms>=5*60*1000)
        route=await checkRoute();
      const measured=await checkRequest(runtime,config,row);
      assert.deepEqual(measured,preflight[selected.indexOf(row)],'Runtime request preflight changed before dispatch');
      const info=await runtime.model.getModelInfo();
      assert.equal(info.instanceReference,runtime.instance,'Loaded model instance changed');
      const attempt=crypto.randomUUID(),requestHash=hash(stable(row.request));
      durable(journal,{event:'started',attempt_id:attempt,id:row.id,request_sha256:requestHash,at:new Date().toISOString()});
      const started=process.hrtime.bigint();let response;
      try {
        response=await (deps.predict||(config.surface==='local_http'
          ? async (_model,request,ms)=>parent.httpRequest(request,ms)
          : async (model,request,ms)=>predictor.predictWithTimeout(model,request.messages,request.config,ms)))
          (runtime.model,row.request,config.timeout_ms);
      } catch(error) {
        durable(raw,{attempt_id:attempt,id:row.id,error:String(error.message),code:error.code??null,
          cancellationAcknowledged:error.cancellationAcknowledged??null,partialResult:error.partialResult??null,
          elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9,result:null});
        durable(journal,{event:'stopped_unknown',attempt_id:attempt,id:row.id,at:new Date().toISOString()});
        throw error;
      }
      durable(raw,{attempt_id:attempt,id:row.id,result:response,
        elapsed_seconds:Number(process.hrtime.bigint()-started)/1e9});
      let decision;
      try {
        const observed=await runtime.model.getModelInfo();
        decision=observed.instanceReference!==runtime.instance ?
          {status:'control_failure',reason:'loaded_instance_changed'} :
          config.surface==='local_http' ? parent.classifyHttp(response,{identifier:config.model_identifier,
            promptTokens:row.prompt_tokens}) : parent.classifySdk(response,{identifier:config.model_identifier,
            path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:row.prompt_tokens,
            loadConfig:config.controls.load_config,predictionConfig:config.controls.prediction_config});
      } catch(error) {
        durable(journal,{event:'stopped_unknown',attempt_id:attempt,id:row.id,reason:'post_response_validation_failed',
          at:new Date().toISOString()});
        throw error;
      }
      durable(records,{id:row.id,attempt_id:attempt,request_sha256:requestHash,decision,
        reference_labels_read:false,finished_utc:new Date().toISOString()});
      durable(journal,{event:'finished',attempt_id:attempt,id:row.id,status:decision.status,at:new Date().toISOString()});
      if(decision.status==='invalid_output') invalid++;
      else if(decision.status!=='ok') throw Error(`Stopped on ${decision.status} at ${row.id}`);
    }
    assert(stage!=='smoke'||invalid===0,'Smoke has invalid output; development admission refused');
    status='completed';
  } catch(error) {reason=String(error.message);throw error;}
  finally {
    for(const fd of [journal,raw,records]) fs.closeSync(fd);
    fs.writeFileSync(paths.completion,stable({phase,stage,status,reason,
      attempted:rows(paths.journal).filter(x=>x.event==='started').length,saved:rows(paths.records).length,invalid,
      journal_sha256:hashFile(paths.journal),raw_sha256:hashFile(paths.raw),
      records_sha256:hashFile(paths.records),finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  }
  return read(paths.completion);
}

const lockCode=small.lockCode.replace('SMALL_LOCAL_HOST_LOCK_HELD','LEGACY_QWEN_HOST_LOCK_HELD');
async function cli(args) {
  const [action,...rest]=args;
  if(action==='prepare') {const plan=makePlan();fs.mkdirSync(path.dirname(PLAN),{recursive:true});
    fs.writeFileSync(PLAN,stable(plan)+'\n',{flag:'wx'});console.log(hashFile(PLAN));return;}
  const {plan,sha256}=verifyPlan();
  if(action==='verify') {console.log(sha256);return;}
  if(action==='preview') {const [id,pass,condition,stage]=rest;phaseInfo(plan,id,pass,condition);
    console.log(stable({phase:`${id}/${pass}/${condition}`,stage,
      ids:stageRows(plan,id,condition,stage).map(x=>x.id)}));return;}
  if(action==='run') {execFileSync('python3',['-c',lockCode,LOCK,process.execPath,__filename,'internal-run',...rest],
    {stdio:'inherit'});return;}
  if(action==='recover-no-send') {execFileSync('python3',['-c',lockCode,LOCK,process.execPath,__filename,'internal-recover-no-send',...rest],
    {stdio:'inherit'});return;}
  if(action==='internal-recover-no-send') {
    assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use recover-no-send to acquire GPU lock');
    const [id,pass,condition,stage]=rest;
    assert(id&&pass&&condition&&stage,'Require configuration pass condition stage');
    phaseInfo(plan,id,pass,condition);
    console.log(stable(recoverUnsentStage(stagePaths(id,pass,condition,stage),
      `${id}/${pass}/${condition}`,stage)));return;
  }
  if(action==='internal-run') {assert.equal(process.env.LEGACY_QWEN_HOST_LOCK_HELD,'1','Use run to acquire GPU lock');
    const [id,pass,condition,stage,receipt]=rest;
    assert(id&&pass&&condition&&stage&&receipt,'Require configuration pass condition stage receipt');
    await runStage(plan,sha256,id,pass,condition,stage,receipt);return;}
  throw Error('Use prepare, verify, preview, run, or recover-no-send');
}
if(require.main===module) cli(process.argv.slice(2)).catch(e=>{console.error(e.message);process.exitCode=1;});
module.exports={IDS,SOURCES,PLAN,LOCK,makePlan,verifyPlan,phaseInfo,stageRows,stagePaths,
  checkPredecessor,checkReceipt,checkLiveRoute,verifyHttpThinking,verifyRequestRuntime,
  runStage,recoverUnsentStage,constructRequests,sequence,lockCode};
