#!/usr/bin/env node
// Offline-prepared successor for one stopped E4B thinking-on local repeat.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const original = require('./small_local_repeat_admission.cjs');
const parent = require('./local_prompt_execution_v1.cjs');
const predictor = require('./lmstudio_reasoning_benchmark.cjs');

const ROOT = original.ROOT;
const ID = 'gemma4-e4b-sdk-thinking-on';
const BASE = path.join(ROOT,'results/repeatability-v1/small-local-v1',ID);
const OUTPUT = path.join(BASE,'interruption-continuation-v1');
const MANIFEST = path.join(OUTPUT,'manifest.json');
const SCHEMA = 'small-local-e4b-on-interruption-continuation-v1';
const IDS = Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);
const SUFFIX = IDS.slice(39);
const SEQUENCE = [['fresh2','P2','suffix'],
  ...[['fresh2','P0'],['fresh3','P2'],['fresh3','P0'],['fresh3','P1']]
    .flatMap(([pass,condition])=>[[pass,condition,'smoke'],[pass,condition,'development']])];
const stable = JSON.stringify;
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const hashFile = original.hashFile;
const read = original.read;
const rows = original.rows;
const durable = (fd,value) => {fs.writeSync(fd,stable(value)+'\n');fs.fsyncSync(fd);};

function paths(pass,condition,stage) {
  assert(SEQUENCE.some(x=>x[0]===pass&&x[1]===condition&&x[2]===stage),'Unknown continuation stage');
  const folder=path.join(OUTPUT,pass,condition);
  return {folder,claim:path.join(folder,`${stage}.claim.json`),
    journal:path.join(folder,`${stage}.journal.jsonl`),
    raw:path.join(folder,`${stage}.raw.jsonl`),
    records:path.join(folder,`${stage}.records.jsonl`),
    completion:path.join(folder,`${stage}.completion.json`)};
}

function sourceBinding(file) {
  const full=path.resolve(file);
  assert(full.startsWith(ROOT+path.sep),'Source outside repository');
  return {file:path.relative(ROOT,full),sha256:hashFile(full)};
}

function verifyBinding(binding) {
  assert(binding&&typeof binding.file==='string'&&typeof binding.sha256==='string');
  const full=original.rel(binding.file);
  assert.equal(hashFile(full),binding.sha256,`Bound source changed: ${binding.file}`);
  return full;
}

function originalPaths() {return original.stagePaths(ID,'fresh2','P2','development');}

function verifyStoppedPrefix(plan,planSha) {
  const phase=`${ID}/fresh2/P2`,p=originalPaths(),config=plan.configurations[ID];
  original.checkPredecessor(plan,ID,'fresh2','P2','development');
  for(const kind of ['claim','journal','raw','records','completion'])
    assert(fs.existsSync(p[kind]),`Stopped evidence missing: ${kind}`);
  const review=path.join(p.folder,'development.root-review.json');
  assert(fs.existsSync(review),'Original root review missing');
  const claim=read(p.claim),receipt=read(review),done=read(p.completion);
  assert.equal(claim.phase,phase);assert.equal(claim.stage,'development');
  assert.equal(claim.plan_sha256,planSha);
  assert.equal(claim.controller_sha256,hashFile(path.join(ROOT,'scripts/small_local_repeat_admission.cjs')));
  assert.equal(claim.receipt_sha256,hashFile(review));
  assert.equal(claim.runtime_attestation.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(claim.runtime_attestation.load_evidence.cache,plan.policy.cache_policy);
  assert.equal(receipt.kind,'root-reviewed-small-local-stage-v1');
  assert.equal(receipt.approved,true);assert.equal(receipt.plan_sha256,planSha);
  assert.equal(receipt.controller_sha256,claim.controller_sha256);
  assert.equal(receipt.phase,phase);assert.equal(receipt.stage,'development');
  assert.equal(receipt.model_identifier,config.model_identifier);
  assert.equal(receipt.artifact_sha256,config.artifact_sha256);
  assert.equal(receipt.reference_labels_read,false);
  assert.equal(receipt.exact_openrouter_route_absent,true);
  assert.equal(hashFile(original.rel(receipt.route_catalog_file)),receipt.route_catalog_sha256);
  assert.equal(receipt.smoke_inspection_sha256,
    hashFile(path.join(p.folder,'smoke-inspection.json')));
  assert.equal(done.phase,phase);assert.equal(done.stage,'development');
  assert.equal(done.status,'stopped');assert.equal(done.attempted,39);
  assert.equal(done.saved,38);assert.equal(done.invalid,0);
  assert.equal(done.raw_sha256,hashFile(p.raw));
  assert.equal(done.records_sha256,hashFile(p.records));
  assert.equal(done.journal_sha256,hashFile(p.journal));
  const raw=rows(p.raw),saved=rows(p.records),journal=rows(p.journal);
  const frozen=original.stageRows(plan,ID,'P2','development');
  assert.equal(raw.length,39);assert.equal(saved.length,38);assert.equal(journal.length,78);
  assert.deepEqual(raw.map(x=>x.id),IDS.slice(0,39));
  assert.deepEqual(saved.map(x=>x.id),IDS.slice(0,38));
  const attempts=new Set();
  for(let i=0;i<39;i++) {
    const rid=IDS[i],item=frozen[i],sidecar=raw[i];
    const started=journal[2*i],ended=journal[2*i+1],attempt=sidecar.attempt_id;
    assert(typeof attempt==='string'&&attempt&&!attempts.has(attempt),'Original attempt ID differs');
    attempts.add(attempt);
    assert.equal(started.event,'started');assert.equal(started.id,rid);
    assert.equal(started.attempt_id,attempt);
    assert.equal(started.request_sha256,hash(stable(item.request)));
    assert.equal(sidecar.id,rid);
    if(i<38) {
      const record=saved[i];
      assert.equal(ended.event,'finished');assert.equal(ended.id,rid);
      assert.equal(ended.attempt_id,attempt);
      assert.equal(record.id,rid);assert.equal(record.attempt_id,attempt);
      assert.equal(record.request_sha256,hash(stable(item.request)));
      assert.equal(record.reference_labels_read,false);
      assert.equal(record.decision.status,'ok');
      assert.equal(ended.status,'ok');
      assert(sidecar.result&&typeof sidecar.result==='object');
      const expected={identifier:config.model_identifier,path:config.artifact_path,
        bytes:config.artifact_bytes,promptTokens:item.prompt_tokens,
        loadConfig:item.load_config,predictionConfig:item.prediction_config};
      assert.deepEqual(record.decision,parent.classifySdk(sidecar.result,expected));
    } else {
      assert.equal(ended.event,'stopped_unknown');assert.equal(ended.id,'DEV-039');
      assert.equal(ended.attempt_id,attempt);
      assert.equal(sidecar.code,'PREDICTION_TIMEOUT');
      assert.equal(sidecar.cancellationAcknowledged,true);
      assert(sidecar.partialResult!==null&&sidecar.partialResult!==undefined);
      assert.equal(sidecar.result,null);
    }
  }
  return {phase,failed_id:'DEV-039',saved_count:38,
    never_sent_ids:SUFFIX,attempt_ids:[...attempts],
    bindings:Object.fromEntries(['claim','journal','raw','records','completion']
      .map(k=>[k,sourceBinding(p[k])]).concat([['review',sourceBinding(review)]]))};
}

function expectedManifest() {
  const {plan,sha256}=original.verifyPlan();
  const config=plan.configurations[ID];
  assert.deepEqual(config.schedule,[
    {name:'fresh1',conditions:['P0','P1','P2']},
    {name:'fresh2',conditions:['P1','P2','P0']},
    {name:'fresh3',conditions:['P2','P0','P1']}]);
  const stopped=verifyStoppedPrefix(plan,sha256);
  const previous=[];
  for(const [pass,condition] of [['fresh1','P0'],['fresh1','P1'],['fresh1','P2'],['fresh2','P1']]) {
    const p=original.stagePaths(ID,pass,condition,'development');
    const done=read(p.completion);
    assert.equal(done.status,'completed');assert.equal(done.attempted,60);assert.equal(done.saved,60);
    for(const key of ['journal','raw','records']) assert.equal(done[`${key}_sha256`],hashFile(p[key]));
    previous.push({pass,condition,completion:sourceBinding(p.completion),
      claim:sourceBinding(p.claim),journal:sourceBinding(p.journal),
      raw:sourceBinding(p.raw),records:sourceBinding(p.records)});
  }
  return {schema:SCHEMA,status:'offline_prepared_unapproved',
    method:'descriptive-interrupted-series-continuation',
    clean_matched_three_eligible:false,reference_labels_read:false,
    configuration_id:ID,plan:sourceBinding(original.PLAN),
    original_controller:sourceBinding(path.join(ROOT,'scripts/small_local_repeat_admission.cjs')),
    controller:sourceBinding(__filename),
    stopped,previous,
    schedule:SEQUENCE.map(([pass,condition,stage])=>({pass,condition,stage,
      ids:stage==='suffix'?SUFFIX:stage==='smoke'?IDS.slice(0,3):IDS,
      request_sha256:(stage==='suffix'?config.conditions.P2.requests.slice(39)
        :stage==='smoke'?config.conditions[condition].requests.slice(0,3)
          :config.conditions[condition].requests).map(x=>x.sha256)})),
    runtime:{artifact_sha256:config.artifact_sha256,model_identifier:config.model_identifier,
      timeout_ms:config.timeout_ms,cache_policy:plan.policy.cache_policy,
      parent_runtime:plan.parent_runtime},
    first_failed_id:'DEV-039',original_never_sent_ids:SUFFIX,
    retry_policy:'no replay of DEV-001 through DEV-039; stop on service/control failure',
    lock_path:path.relative(ROOT,original.LOCK)};
}

function freeze() {
  assert(!fs.existsSync(MANIFEST),'Continuation manifest already exists');
  const value=expectedManifest();
  fs.mkdirSync(OUTPUT,{recursive:true});
  fs.writeFileSync(MANIFEST,stable(value)+'\n',{flag:'wx'});
  return hashFile(MANIFEST);
}

function verifyManifest(expectedSha) {
  assert.equal(hashFile(MANIFEST),expectedSha,'Continuation manifest hash differs');
  const value=read(MANIFEST);
  assert.deepEqual(value,expectedManifest(),'Continuation manifest differs from frozen sources');
  return value;
}

function selectedRows(plan,pass,condition,stage) {
  assert(SEQUENCE.some(x=>x[0]===pass&&x[1]===condition&&x[2]===stage));
  const all=original.stageRows(plan,ID,condition,stage==='smoke'?'smoke':'development');
  return stage==='suffix'?all.slice(39):all;
}

function verifyReview(receiptPath,manifest,manifestSha,pass,condition,stage,smokeSha=null,now=Date.now()) {
  const p=paths(pass,condition,stage);
  assert.equal(path.resolve(receiptPath),path.join(p.folder,`${stage}.root-review.json`));
  const value=read(receiptPath);
  const schedule=manifest.schedule.find(x=>x.pass===pass&&x.condition===condition&&x.stage===stage);
  assert(schedule,'Stage absent from frozen schedule');
  const required={kind:SCHEMA+'-root-review',approved:true,
    manifest_sha256:manifestSha,controller_sha256:manifest.controller.sha256,
    phase:`${ID}/${pass}/${condition}`,stage,ids:schedule.ids,
    request_sha256:schedule.request_sha256,
    model_identifier:manifest.runtime.model_identifier,
    artifact_sha256:manifest.runtime.artifact_sha256,
    cache_policy:manifest.runtime.cache_policy,
    reference_labels_read:false,exact_openrouter_route_absent:true};
  for(const [key,expected] of Object.entries(required)) assert.deepEqual(value[key],expected,`Review ${key} differs`);
  const catalog=read(original.rel(value.route_catalog_file));
  assert.equal(hashFile(original.rel(value.route_catalog_file)),value.route_catalog_sha256);
  assert.equal(catalog.source,'https://openrouter.ai/api/v1/models');
  assert.deepEqual(catalog.matches,[]);
  assert(catalog.searched_name_fragments.includes('gemma-4-e4b'));
  assert.equal(value.route_checked_utc,catalog.retrieved_utc);
  assert(now-Date.parse(catalog.retrieved_utc)>=0 && now-Date.parse(catalog.retrieved_utc)<24*3600*1000,
    'Route attestation must be fresh');
  if(stage==='development') {
    assert.equal(value.smoke_inspection_sha256,smokeSha);
    assert.equal(value.smoke_all_three_valid,true);
  }
  return value;
}

function verifyCompleted(manifest,manifestSha,pass,condition,stage) {
  const p=paths(pass,condition,stage);
  for(const key of ['claim','journal','raw','records','completion'])
    assert(fs.existsSync(p[key]),`Continuation closure missing ${key}`);
  const claim=read(p.claim),done=read(p.completion),
    journal=rows(p.journal),raw=rows(p.raw),records=rows(p.records);
  const schedule=manifest.schedule.find(x=>x.pass===pass&&x.condition===condition&&x.stage===stage);
  const {plan}=original.verifyPlan();
  const config=plan.configurations[ID],selection=selectedRows(plan,pass,condition,stage);
  const review=path.join(p.folder,`${stage}.root-review.json`);
  assert(fs.existsSync(review),'Continuation root review missing');
  const receipt=read(review);
  const smokeHash=stage==='development'
    ? hashFile(path.join(p.folder,'smoke-inspection.json')):null;
  verifyReview(review,manifest,manifestSha,pass,condition,stage,smokeHash,
    Date.parse(receipt.route_checked_utc)+1000);
  assert.equal(claim.schema,SCHEMA+'-stage-claim');
  assert.equal(claim.manifest_sha256,manifestSha);
  assert.equal(claim.controller_sha256,manifest.controller.sha256);
  assert.equal(claim.receipt_sha256,hashFile(review));
  assert.equal(claim.phase,`${ID}/${pass}/${condition}`);
  assert.equal(claim.stage,stage);
  assert.deepEqual(claim.ids,schedule.ids);
  assert.equal(claim.runtime_attestation.artifact_sha256,config.artifact_sha256);
  assert.deepEqual(claim.runtime_attestation.load_evidence.cache,plan.policy.cache_policy);
  assert.equal(done.phase,claim.phase);assert.equal(done.stage,stage);
  assert.equal(done.status,'completed');
  assert.equal(done.attempted,selection.length);assert.equal(done.saved,selection.length);
  assert.equal(done.journal_sha256,hashFile(p.journal));
  assert.equal(done.raw_sha256,hashFile(p.raw));
  assert.equal(done.records_sha256,hashFile(p.records));
  assert.equal(journal.length,2*selection.length);
  assert.equal(raw.length,selection.length);assert.equal(records.length,selection.length);
  const attempts=new Set();let invalid=0;
  for(let i=0;i<selection.length;i++) {
    const item=selection[i],sidecar=raw[i],record=records[i];
    const started=journal[2*i],finished=journal[2*i+1],attempt=sidecar.attempt_id;
    assert(typeof attempt==='string'&&attempt&&!attempts.has(attempt),'Continuation attempt ID differs');
    attempts.add(attempt);
    assert.equal(item.id,schedule.ids[i]);
    assert.equal(hash(stable(item.request)),schedule.request_sha256[i]);
    assert.equal(started.event,'started');assert.equal(started.id,item.id);
    assert.equal(started.attempt_id,attempt);
    assert.equal(started.request_sha256,schedule.request_sha256[i]);
    assert.equal(sidecar.id,item.id);assert(sidecar.result&&typeof sidecar.result==='object');
    assert.equal(record.id,item.id);assert.equal(record.attempt_id,attempt);
    assert.equal(record.request_sha256,schedule.request_sha256[i]);
    assert.equal(record.reference_labels_read,false);
    const expected={identifier:config.model_identifier,path:config.artifact_path,
      bytes:config.artifact_bytes,promptTokens:item.prompt_tokens,
      loadConfig:item.load_config,predictionConfig:item.prediction_config};
    assert.deepEqual(record.decision,parent.classifySdk(sidecar.result,expected));
    assert(['ok','invalid_output'].includes(record.decision.status),'Unexpected completed outcome');
    if(record.decision.status==='invalid_output') invalid++;
    assert.equal(finished.event,'finished');assert.equal(finished.id,item.id);
    assert.equal(finished.attempt_id,attempt);
    assert.equal(finished.status,record.decision.status);
  }
  assert.equal(done.invalid,invalid);
  if(stage==='smoke') assert.equal(invalid,0);
  return {status:'completed',count:records.length,
    raw_sha256:done.raw_sha256,records_sha256:done.records_sha256,
    journal_sha256:done.journal_sha256};
}

function verifyPredecessors(manifest,manifestSha,pass,condition,stage) {
  const {plan}=original.verifyPlan();
  verifyStoppedPrefix(plan,manifest.plan.sha256);
  const index=SEQUENCE.findIndex(x=>x[0]===pass&&x[1]===condition&&x[2]===stage);
  assert(index>=0,'Stage outside continuation schedule');
  for(const [p,c,s] of SEQUENCE.slice(0,index)) verifyCompleted(manifest,manifestSha,p,c,s);
  if(stage!=='development') return null;
  const smoke=verifyCompleted(manifest,manifestSha,pass,condition,'smoke');
  const inspectionPath=path.join(paths(pass,condition,'smoke').folder,'smoke-inspection.json');
  assert(fs.existsSync(inspectionPath),'Root smoke inspection missing');
  const inspection=read(inspectionPath);
  assert.equal(inspection.kind,SCHEMA+'-smoke-inspection');
  assert.equal(inspection.approved,true);
  assert.equal(inspection.reference_labels_read,false);
  assert.equal(inspection.raw_sha256,smoke.raw_sha256);
  assert.equal(inspection.records_sha256,smoke.records_sha256);
  assert.equal(inspection.journal_sha256,smoke.journal_sha256);
  return hashFile(inspectionPath);
}

function prepare(manifestSha,pass,condition,stage,receiptPath,now=Date.now()) {
  const manifest=verifyManifest(manifestSha);
  const smokeSha=verifyPredecessors(manifest,manifestSha,pass,condition,stage);
  verifyReview(receiptPath,manifest,manifestSha,pass,condition,stage,smokeSha,now);
  const p=paths(pass,condition,stage);
  assert(!Object.values(p).some(x=>x!==p.folder&&fs.existsSync(x)),
    'Continuation stage already claimed; no replay');
  return {manifest,paths:p};
}

async function runStage(manifestSha,pass,condition,stage,receiptPath,dependencies={}) {
  if(!dependencies.prepare)
    assert.equal(process.env.SMALL_LOCAL_HOST_LOCK_HELD,'1',
      'Use run to acquire the common native host lock');
  const prepared=(dependencies.prepare||prepare)(manifestSha,pass,condition,stage,receiptPath);
  const manifest=prepared.manifest,p=prepared.paths;
  const {plan}=original.verifyPlan(),config=plan.configurations[ID];
  const schedule=manifest.schedule.find(x=>x.pass===pass&&x.condition===condition&&x.stage===stage);
  const selection=selectedRows(plan,pass,condition,stage);
  assert.deepEqual(selection.map(x=>x.id),schedule.ids);
  assert.deepEqual(selection.map(x=>hash(stable(x.request))),schedule.request_sha256);
  const runtime=await (dependencies.runtime||original.realRuntime)(plan,config);
  assert(!Object.values(p).some(x=>x!==p.folder&&fs.existsSync(x)),
    'Continuation stage already claimed; no replay');
  fs.mkdirSync(p.folder,{recursive:true});
  fs.writeFileSync(p.claim,stable({schema:SCHEMA+'-stage-claim',
    phase:`${ID}/${pass}/${condition}`,stage,ids:schedule.ids,
    manifest_sha256:manifestSha,controller_sha256:manifest.controller.sha256,
    receipt_sha256:hashFile(receiptPath),runtime_attestation:runtime.attestation,
    started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  const journal=fs.openSync(p.journal,'wx'),raw=fs.openSync(p.raw,'wx'),
    records=fs.openSync(p.records,'wx');
  let status='stopped',reason=null,invalid=0;
  try {
    for(const item of selection) {
      const info=await runtime.model.getModelInfo();
      assert.equal(info.instanceReference,runtime.instance,'Loaded model instance changed');
      const attempt=crypto.randomUUID();
      durable(journal,{event:'started',attempt_id:attempt,id:item.id,
        request_sha256:hash(stable(item.request)),at:new Date().toISOString()});
      const start=process.hrtime.bigint();let result;
      try {
        result=await (dependencies.predict||predictor.predictWithTimeout)(runtime.model,
          item.request.messages,item.request.config,config.timeout_ms);
      } catch(error) {
        durable(raw,{attempt_id:attempt,id:item.id,error:String(error.message),
          code:error.code??null,cancellationAcknowledged:error.cancellationAcknowledged??null,
          cancellationError:error.cancellationError??null,partialResult:error.partialResult??null,
          elapsed_seconds:Number(process.hrtime.bigint()-start)/1e9,result:null});
        durable(journal,{event:'stopped_unknown',attempt_id:attempt,id:item.id,
          at:new Date().toISOString()});
        throw error;
      }
      durable(raw,{attempt_id:attempt,id:item.id,result:{content:result?.content??null,
        nonReasoningContent:result?.nonReasoningContent??null,
        reasoningContent:result?.reasoningContent??null,stats:result?.stats??null,
        modelInfo:result?.modelInfo??null,loadConfig:result?.loadConfig??null,
        predictionConfig:result?.predictionConfig??null},
        elapsed_seconds:Number(process.hrtime.bigint()-start)/1e9});
      const expected={identifier:config.model_identifier,path:config.artifact_path,
        bytes:config.artifact_bytes,promptTokens:item.prompt_tokens,
        loadConfig:item.load_config,predictionConfig:item.prediction_config};
      const decision=parent.classifySdk(result,expected);
      durable(records,{id:item.id,attempt_id:attempt,
        request_sha256:hash(stable(item.request)),decision,
        reference_labels_read:false,finished_utc:new Date().toISOString()});
      durable(journal,{event:'finished',attempt_id:attempt,id:item.id,
        status:decision.status,at:new Date().toISOString()});
      if(decision.status==='invalid_output') invalid++;
      else if(decision.status!=='ok') throw Error(`Stopped on ${decision.status} at ${item.id}`);
    }
    assert(stage!=='smoke'||invalid===0,'Smoke has invalid output; development admission refused');
    status='completed';
  } catch(error) {reason=String(error.message);throw error;}
  finally {
    for(const fd of [journal,raw,records]) fs.closeSync(fd);
    fs.writeFileSync(p.completion,stable({phase:`${ID}/${pass}/${condition}`,stage,
      status,reason,attempted:rows(p.journal).filter(x=>x.event==='started').length,
      saved:rows(p.records).length,invalid,raw_sha256:hashFile(p.raw),
      records_sha256:hashFile(p.records),journal_sha256:hashFile(p.journal),
      finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
  }
  return read(p.completion);
}

async function cli(argv) {
  const [action,...args]=argv;
  if(action==='preview') {
    const manifest=expectedManifest();
    console.log(stable({schema:manifest.schema,schedule:manifest.schedule,
      failed_id:manifest.first_failed_id,never_sent_ids:manifest.original_never_sent_ids}));
    return;
  }
  if(action==='freeze') {console.log(freeze());return;}
  if(action==='verify') {verifyManifest(args[0]);console.log(args[0]);return;}
  if(action==='run') {
    assert(args.length===5,'Require manifest SHA, pass, condition, stage, receipt');
    execFileSync('python3',['-c',original.lockCode,original.LOCK,process.execPath,
      __filename,'internal-run',...args],{stdio:'inherit'});
    return;
  }
  if(action==='internal-run') {
    assert.equal(process.env.SMALL_LOCAL_HOST_LOCK_HELD,'1',
      'Use run to acquire the common native host lock');
    assert(args.length===5,'Require manifest SHA, pass, condition, stage, receipt');
    await runStage(...args);return;
  }
  throw Error('Use preview, freeze, verify, or run');
}

if(require.main===module) cli(process.argv.slice(2)).catch(error=>{
  console.error(error.message);process.exitCode=1;
});

module.exports={ROOT,ID,BASE,OUTPUT,MANIFEST,SCHEMA,IDS,SUFFIX,SEQUENCE,
  paths,sourceBinding,verifyBinding,verifyStoppedPrefix,expectedManifest,freeze,
  verifyManifest,selectedRows,verifyReview,verifyCompleted,verifyPredecessors,
  prepare,runStage};
