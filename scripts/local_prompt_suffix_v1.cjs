#!/usr/bin/env node
// Separate DEV-020..060 continuation. The original DEV-019 remains unresolved.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const os=require('node:os');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const parent=require('./local_prompt_execution_v1.cjs');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,'results/local-prompt-suffix-v1');
const manifestPath=path.join(dir,'manifest.json');
const parentDir=path.join(root,'results/local-prompt-exact-v1');
const cliPath='/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms';
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const shaFile=file=>sha(fs.readFileSync(file));
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const lines=file=>fs.readFileSync(file,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const stable=value=>JSON.stringify(value);
const id=n=>`DEV-${String(n).padStart(3,'0')}`;
const expectedSuffix=Array.from({length:41},(_,i)=>id(i+20));
function repoPath(relative) {
  assert(typeof relative==='string' && !path.isAbsolute(relative) && !relative.split('/').includes('..'));
  const full=path.resolve(root,relative);assert(full.startsWith(root+path.sep));return full;
}
function append(fd,value) {fs.writeSync(fd,stable(value)+'\n');fs.fsyncSync(fd);}
function originalEvidence(m) {
  const b=m.binding;
  for(const [key,field] of [['parent_manifest','parent_manifest_sha256'],['parent_preflight','parent_preflight_sha256'],
    ['parent_controller','parent_controller_sha256'],['parent_review','parent_review_sha256'],
    ['interruption_audit','interruption_audit_sha256'],['original_output','original_output_sha256'],
    ['original_journal','original_journal_sha256'],['original_smoke_inspection','original_smoke_inspection_sha256']])
    assert.equal(shaFile(repoPath(b[key])),b[field],`${key} drift`);
  assert(!fs.existsSync(repoPath(b.original_terminal)),'Original terminal unexpectedly exists');
  const audit=read(repoPath(b.interruption_audit));
  assert.equal(audit.evidence.development_output_sha256,b.original_output_sha256);
  assert.equal(audit.evidence.development_journal_sha256,b.original_journal_sha256);
  assert.equal(audit.evidence.gpu_lock_sha256,b.stale_lock_sha256);
  assert.equal(audit.process.pid_present,false);
  assert.equal(audit.process.matching_controller_process_present,false);
  assert.equal(audit.unfinished.id,'DEV-019');
  assert.equal(audit.unfinished.retry_authorized,false);
  assert.equal(audit.untouched.count,41);
  const rows=lines(repoPath(b.original_output)),events=lines(repoPath(b.original_journal));
  const parentManifest=read(repoPath(b.parent_manifest));
  validateOriginalRows(rows,events,m,b,audit,parentManifest);
  return parentManifest;
}
function validateOriginalRows(rows,events,m,b,audit,parentManifest) {
  assert.equal(rows.length,18);assert.equal(events.length,37);
  for(let i=0;i<18;i++) {
    const row=rows[i],start=events[2*i],finish=events[2*i+1];
    assert.equal(row.id,id(i+1));assert.equal(row.configuration,m.configuration);
    assert.equal(row.variant,m.variant);assert.equal(row.phase,'development');
    assert(['ok','invalid_output'].includes(row.decision.status));
    assert.equal(row.manifest_sha256,b.parent_manifest_sha256);
    assert.equal(row.preflight_sha256,b.parent_preflight_sha256);
    assert.equal(row.controller_sha256,b.parent_controller_sha256);
    assert.equal(start.event,'started');assert.equal(finish.event,'finished');
    assert.equal(start.id,row.id);assert.equal(finish.id,row.id);
    assert.equal(start.attempt_id,row.attempt_id);assert.equal(finish.attempt_id,row.attempt_id);
    assert.equal(start.request_sha256,row.request_sha256);
    assert.equal(finish.status,row.decision.status);
    assert.equal(finish.output_sha256,sha(Buffer.from(stable(row))));
  }
  assert.equal(rows.filter(row=>row.decision.status==='ok').length,14);
  const pending=events[36];
  assert.equal(pending.event,'started');assert.equal(pending.id,'DEV-019');
  assert.equal(pending.attempt_id,audit.unfinished.attempt_id);
  assert.equal(pending.request_sha256,audit.unfinished.request_sha256);
  assert.equal(pending.manifest_sha256,b.parent_manifest_sha256);
  assert.equal(pending.preflight_sha256,b.parent_preflight_sha256);
  assert.equal(pending.timeout_ms,600000);
  assert.deepEqual(m.allowed_ids,expectedSuffix);
  assert.equal(m.configuration,'qwen3.5-4b-sdk-thinking-on');
  assert.equal(m.variant,'P2');assert.equal(m.phase,'development_suffix');
  assert.equal(m.reference_labels_read,false);assert.equal(m.retries,0);
  assert.equal(m.timeout_ms,parentManifest.configs[m.configuration].timeout_ms);
  assert.equal(m.timeout_ms,600000);
  assert.equal(parentManifest.configs[m.configuration].surface,'lmstudio_sdk');
}
function sourceAndSuffix(m) {
  assert.equal(m.version,'local-prompt-suffix-v1');
  assert.equal(shaFile(__filename),m.controller_sha256,'Suffix controller drift');
  const p=originalEvidence(m);
  const source=parent.sourceCheck(p); // Pure input-only reconstruction; no reference labels or model.
  const selected=source[m.configuration].records.filter(row=>row.variant===m.variant);
  assert.deepEqual(selected.map(row=>row.id),Array.from({length:60},(_,i)=>id(i+1)));
  const suffix=selected.slice(19);
  assert.deepEqual(suffix.map(row=>row.id),m.allowed_ids);
  return {parentManifest:p,source:source[m.configuration],records:suffix};
}
function approval(m,args) {
  assert.equal(args['approved-manifest-sha256'],shaFile(manifestPath));
  assert(args['review-receipt'] && args['review-receipt-sha256']);
  assert(args['lock-release-receipt'] && args['lock-release-receipt-sha256']);
  const reviewFile=repoPath(args['review-receipt']);
  const releaseFile=repoPath(args['lock-release-receipt']);
  assert.equal(shaFile(reviewFile),args['review-receipt-sha256']);
  assert.equal(shaFile(releaseFile),args['lock-release-receipt-sha256']);
  const review=read(reviewFile),release=read(releaseFile);
  assert.equal(review.approved_for_execution,true);
  assert.equal(review.manifest_sha256,shaFile(manifestPath));
  assert.equal(review.controller_sha256,shaFile(__filename));
  assert.equal(review.interruption_audit_sha256,m.binding.interruption_audit_sha256);
  assert.equal(review.lock_release_receipt_sha256,shaFile(releaseFile));
  assert.deepEqual(review.allowed_ids,m.allowed_ids);
  assert.equal(release.original_lock_sha256,m.binding.stale_lock_sha256);
  assert.equal(release.interruption_audit_sha256,m.binding.interruption_audit_sha256);
  assert.equal(release.pid_absent_verified,true);
  assert.equal(release.lock_removed,true);
  assert(!fs.existsSync(repoPath(m.local_gpu_lock_file)),'GPU lock still exists');
}
async function hashArtifact(file) {
  const digest=crypto.createHash('sha256');
  for await(const chunk of fs.createReadStream(file,{highWaterMark:8*1024*1024})) digest.update(chunk);
  return digest.digest('hex');
}
async function execute(m,prepared,args) {
  approval(m,args);
  const config=prepared.parentManifest.configs[m.configuration];
  const outputPath=path.join(dir,'development-suffix.jsonl');
  const journalPath=path.join(dir,'development-suffix.attempts.jsonl');
  const terminalPath=path.join(dir,'development-suffix.terminal.json');
  assert(![outputPath,journalPath,terminalPath].some(fs.existsSync),'Suffix evidence exists; no replay');
  const lockPath=repoPath(m.local_gpu_lock_file);
  const lock=fs.openSync(lockPath,'wx');
  const preflightId=crypto.randomUUID();
  let output,journal,claimed=false,holdLock=false,complete=false,errorText=null,runtime=null;
  const manifestHash=shaFile(manifestPath),controllerHash=shaFile(__filename);
  const preflightStarted=path.join(dir,`preflight-${preflightId}.started.json`);
  const preflightTerminal=path.join(dir,`preflight-${preflightId}.terminal.json`);
  try {
    append(lock,{pid:process.pid,configuration:m.configuration,variant:m.variant,phase:m.phase,
      suffix_manifest_sha256:manifestHash,started_utc:new Date().toISOString()});
    fs.writeFileSync(preflightStarted,stable({preflight_id:preflightId,manifest_sha256:manifestHash,
      controller_sha256:controllerHash,started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    assert.equal(execFileSync(cliPath,['--version'],{encoding:'utf8',timeout:15000}).trim(),
      `CLI commit: ${prepared.parentManifest.runtime.cli_commit}`);
    const engines=execFileSync(cliPath,['runtime','ls'],{encoding:'utf8',timeout:15000});
    assert(engines.split('\n').some(line=>line.startsWith(prepared.parentManifest.runtime.selected_engine)&&line.includes('✓')&&line.includes('GGUF')));
    const ps=execFileSync(cliPath,['ps'],{encoding:'utf8',timeout:15000});
    const loaded=parent.requireLoadedModel(ps,config.identifier,config.context,1);
    const hardware={model_identifier:execFileSync('/usr/sbin/sysctl',['-n','hw.model'],{encoding:'utf8'}).trim(),
      chip:execFileSync('/usr/sbin/sysctl',['-n','machdep.cpu.brand_string'],{encoding:'utf8'}).trim(),
      architecture:os.arch()};
    assert.deepEqual(hardware,prepared.parentManifest.hardware);
    const artifact=path.join(prepared.parentManifest.runtime.models_dir,config.artifact_path);
    assert.equal(await hashArtifact(artifact),config.artifact_sha256,'Artifact drift');
    const {LMStudioClient}=require(prepared.parentManifest.runtime.sdk_path);
    const model=new LMStudioClient().llm.createDynamicHandle(config.identifier);
    const info=await model.getModelInfo();
    assert(info && info.identifier===config.identifier && info.path===config.artifact_path &&
      info.sizeBytes===config.artifact_bytes && info.contextLength===8192 && info.quantization?.name==='Q4_K_M');
    runtime={cli_commit:prepared.parentManifest.runtime.cli_commit,
      selected_engine:prepared.parentManifest.runtime.selected_engine,
      lm_studio_version:prepared.parentManifest.runtime.lm_studio_version,
      loaded_model_line:loaded.trim(),hardware,artifact_sha256:config.artifact_sha256,surface:config.surface};
    const predictor=require(repoPath('scripts/lmstudio_reasoning_benchmark.cjs')).predictWithTimeout;
    for(const record of prepared.records) {
      const before=await model.getModelInfo();
      assert.equal(before?.instanceReference,info.instanceReference,'Loaded instance changed');
      const baseline=prepared.source.baseline.get(record.id);
      const counted=prepared.source.counts.get(`${record.variant}/${record.id}`);
      const request={messages:record.messages,config:baseline.request.config};
      const requestHash=sha(Buffer.from(stable(request)));
      assert.equal(requestHash,record.request_sha256);
      const attempt=crypto.randomUUID();
      if(output===undefined) {journal=fs.openSync(journalPath,'wx');output=fs.openSync(outputPath,'wx');}
      claimed=true;
      append(journal,{event:'started',attempt_id:attempt,id:record.id,configuration:m.configuration,
        variant:m.variant,phase:m.phase,request_sha256:requestHash,
        manifest_sha256:manifestHash,parent_manifest_sha256:m.binding.parent_manifest_sha256,
        controller_sha256:controllerHash,timeout_ms:m.timeout_ms,at:new Date().toISOString()});
      const started=performance.now();let response=null,decision;
      try {
        response=await predictor(model,record.messages,baseline.request.config,m.timeout_ms);
        const after=await model.getModelInfo();
        if(after?.instanceReference!==info.instanceReference)
          decision={status:'control_failure',reason:'loaded_instance_changed'};
        else decision=parent.classifySdk(response,{identifier:config.identifier,path:config.artifact_path,
          bytes:config.artifact_bytes,promptTokens:counted.prompt_tokens+config.native_token_delta,
          predictionConfig:baseline.prediction_config,loadConfig:baseline.load_config});
      } catch(error) {
        if(error.code==='PREDICTION_TIMEOUT' && error.cancellationAcknowledged!==true) holdLock=true;
        decision={status:error.code==='PREDICTION_TIMEOUT'?'timeout':'service_failure',
          reason:String(error.message),cancellation_acknowledged:error.cancellationAcknowledged??null};
      }
      const row={id:record.id,configuration:m.configuration,variant:m.variant,phase:m.phase,
        attempt_id:attempt,manifest_sha256:manifestHash,parent_manifest_sha256:m.binding.parent_manifest_sha256,
        interruption_audit_sha256:m.binding.interruption_audit_sha256,controller_sha256:controllerHash,
        timeout_ms:m.timeout_ms,runtime_attestation:runtime,request,request_sha256:requestHash,
        rendered_sha256:counted.rendered_sha256,expected_prompt_tokens:counted.prompt_tokens+config.native_token_delta,
        reference_labels_read:false,model_identifier:config.identifier,model_path:config.artifact_path,
        raw_response:response?.content??null,non_reasoning_content:response?.nonReasoningContent??null,
        reasoning_content:response?.reasoningContent??null,stats:response?.stats??null,
        model_info:response?.modelInfo??null,load_config:response?.loadConfig??null,
        prediction_config:response?.predictionConfig??null,decision,
        elapsed_seconds:(performance.now()-started)/1000,finished_utc:new Date().toISOString()};
      append(output,row);
      append(journal,{event:'finished',attempt_id:attempt,id:record.id,status:decision.status,
        output_sha256:sha(Buffer.from(stable(row))),at:new Date().toISOString()});
      console.log(m.configuration,m.variant,m.phase,record.id,decision.status);
      if(['control_failure','service_failure','timeout'].includes(decision.status))
        throw Error(`Stopped after ${record.id}: ${decision.reason}`);
    }
    complete=true;
  } catch(error) {errorText=String(error.message);throw error;}
  finally {
    if(journal!==undefined) fs.closeSync(journal);
    if(output!==undefined) fs.closeSync(output);
    if(!claimed) {
      for(const file of [outputPath,journalPath]) {
        if(fs.existsSync(file)) {assert.equal(fs.statSync(file).size,0);fs.unlinkSync(file);}
      }
    }
    fs.writeFileSync(preflightTerminal,stable({preflight_id:preflightId,
      status:claimed?'passed':'failed_before_request',first_request_claimed:claimed,
      manifest_sha256:manifestHash,controller_sha256:controllerHash,
      runtime_attestation:runtime,stopped_reason:claimed?null:errorText,
      finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    if(claimed) {
      const rows=lines(outputPath),events=lines(journalPath);
      fs.writeFileSync(terminalPath,stable({configuration:m.configuration,variant:m.variant,
        phase:m.phase,status:complete?'completed':'stopped',manifest_sha256:manifestHash,
        controller_sha256:controllerHash,canonical_denominator:60,parent_saved_rows:18,
        ambiguous_original_id:'DEV-019',requested_suffix_records:41,
        claimed_attempts:events.filter(x=>x.event==='started').length,
        finished_attempts:events.filter(x=>x.event==='finished').length,saved_rows:rows.length,
        ok_rows:rows.filter(x=>x.decision.status==='ok').length,
        invalid_output_rows:rows.filter(x=>x.decision.status==='invalid_output').length,
        ambiguous_timeout:holdLock,timeout_ms:m.timeout_ms,runtime_attestation:runtime,
        output_sha256:shaFile(outputPath),journal_sha256:shaFile(journalPath),
        stopped_reason:errorText,finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    }
    fs.closeSync(lock);
    if(!holdLock) fs.unlinkSync(lockPath);
  }
}
async function main() {
  const args=parent.argsFrom(process.argv.slice(2));
  const m=read(manifestPath);
  const prepared=sourceAndSuffix(m);
  if(args.mode==='validate') {
    console.log(stable({validated:true,allowed_ids:m.allowed_ids.length,
      first:m.allowed_ids[0],last:m.allowed_ids.at(-1),
      manifest_sha256:shaFile(manifestPath),controller_sha256:shaFile(__filename)}));return;
  }
  if(args.mode==='run') return execute(m,prepared,args);
  throw Error('Use --mode validate or --mode run');
}
if(require.main===module) main().catch(error=>{console.error(error.message);process.exitCode=1;});
module.exports={expectedSuffix,validateOriginalRows,originalEvidence,sourceAndSuffix,approval};
