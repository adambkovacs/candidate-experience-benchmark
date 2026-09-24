#!/usr/bin/env node
// Scoped continuation for Qwen3.5-4B thinking-on/P1 after the P2 gap.
// This controller never reads reference labels or retries the unresolved DEV-019.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const parent=require('./local_prompt_execution_v1.cjs');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,'results/local-prompt-remaining-v2');
const manifestPath=path.join(dir,'manifest.json');
const parentManifestPath=path.join(root,'results/local-prompt-exact-v1/manifest.json');
const cliPath='/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms';
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const shaFile=p=>sha(fs.readFileSync(p));
const stable=x=>JSON.stringify(x);
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const lines=p=>fs.readFileSync(p,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const file=p=>{assert.equal(typeof p,'string');assert(!path.isAbsolute(p)&&!p.split('/').includes('..'),'Unsafe path');const full=path.resolve(root,p);assert(full.startsWith(root+path.sep),'Path outside repository');return full;};
function checkSource(manifest) {
  assert.equal(manifest.version,'local-prompt-remaining-v2');
  assert.equal(manifest.status,'DRAFT_PENDING_ROOT_REVIEW_NO_INFERENCE');
  assert.equal(manifest.configuration,'qwen3.5-4b-sdk-thinking-on');
  assert.equal(manifest.variant,'P1');
  assert.equal(manifest.reference_labels_read,false);
  assert.equal(manifest.inference_performed,false);
  assert.equal(shaFile(__filename),manifest.controller_sha256,'Controller drift');
  assert.equal(shaFile(parentManifestPath),manifest.parent.manifest_sha256,'Parent manifest drift');
  assert.equal(shaFile(path.join(root,'scripts/local_prompt_execution_v1.cjs')),manifest.parent.controller_sha256,'Parent controller drift');
  assert.equal(shaFile(file(manifest.parent.review)),manifest.parent.review_sha256,'Parent review drift');
  assert.equal(shaFile(file(manifest.parent.interruption_audit)),manifest.parent.interruption_audit_sha256,'Interruption audit drift');
  assert.equal(shaFile(file(manifest.parent.original_output)),manifest.parent.original_output_sha256,'Original output drift');
  assert.equal(shaFile(file(manifest.parent.original_journal)),manifest.parent.original_journal_sha256,'Original journal drift');
  assert.equal(shaFile(file(manifest.hosted_availability)),manifest.hosted_availability_sha256,'Route evidence drift');
  const source=parent.sourceCheck(read(parentManifestPath));
  const original=lines(file(manifest.parent.original_output));
  const journal=lines(file(manifest.parent.original_journal));
  assert.deepEqual(original.map(x=>x.id),Array.from({length:18},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
  assert.equal(journal.length,37);
  for(let i=0;i<18;i++) {
    const a=journal[2*i],b=journal[2*i+1],row=original[i];
    assert.equal(a.event,'started');assert.equal(b.event,'finished');
    assert.equal(a.id,row.id);assert.equal(b.id,row.id);
    assert.equal(a.attempt_id,row.attempt_id);assert.equal(b.attempt_id,row.attempt_id);
    assert.equal(b.output_sha256,sha(Buffer.from(stable(row))));
  }
  assert.equal(journal[36].event,'started');assert.equal(journal[36].id,'DEV-019');
  assert.equal(journal[36].attempt_id,manifest.parent.ambiguous_attempt_id);
  assert(!fs.existsSync(file(manifest.parent.original_terminal)),'Original P2 terminal unexpectedly exists');
  assert.deepEqual(source[manifest.configuration].records.filter(x=>x.variant==='P1').map(x=>x.id),
    Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
  return source;
}
function checkSuffix(manifest,source) {
  assert.equal(shaFile(file(manifest.suffix.manifest)),manifest.suffix.manifest_sha256,'Suffix manifest drift');
  assert.equal(shaFile(path.join(root,'scripts/local_prompt_suffix_v1.cjs')),manifest.suffix.controller_sha256,'Suffix controller drift');
  const suffix=read(file(manifest.suffix.terminal));
  assert.equal(suffix.configuration,manifest.configuration);
  assert.equal(suffix.variant,'P2');
  assert.equal(suffix.phase,'development_suffix');
  assert.equal(suffix.manifest_sha256,manifest.suffix.manifest_sha256);
  assert.equal(suffix.controller_sha256,manifest.suffix.controller_sha256);
  assert.equal(suffix.ambiguous_original_id,'DEV-019');
  assert.equal(suffix.status,'completed');
  assert.equal(suffix.parent_saved_rows,18);
  assert.equal(suffix.requested_suffix_records,41);
  assert.equal(suffix.saved_rows,41);
  assert.equal(suffix.finished_attempts,41);
  assert.equal(suffix.ambiguous_timeout,false);
  const output=file(manifest.suffix.output),journal=file(manifest.suffix.journal);
  assert.equal(suffix.output_sha256,shaFile(output));
  assert.equal(suffix.journal_sha256,shaFile(journal));
  const rows=lines(output),events=lines(journal);
  assert.deepEqual(rows.map(x=>x.id),Array.from({length:41},(_,i)=>`DEV-${String(i+20).padStart(3,'0')}`));
  assert.equal(events.length,82);
  for(let i=0;i<41;i++) {
    const row=rows[i],start=events[2*i],finish=events[2*i+1];
    const frozen=source[manifest.configuration].records.find(x=>x.variant==='P2'&&x.id===row.id);
    assert(frozen);
    assert.equal(row.configuration,manifest.configuration);assert.equal(row.variant,'P2');
    assert.equal(row.phase,'development_suffix');
    assert.equal(row.manifest_sha256,manifest.suffix.manifest_sha256);
    assert.equal(row.controller_sha256,manifest.suffix.controller_sha256);
    assert.equal(row.request_sha256,frozen.request_sha256);
    assert.equal(sha(Buffer.from(stable(row.request))),frozen.request_sha256);
    assert.equal(start.event,'started');assert.equal(finish.event,'finished');
    assert.equal(start.id,row.id);assert.equal(finish.id,row.id);
    assert.equal(start.request_sha256,frozen.request_sha256);
    assert.equal(start.attempt_id,row.attempt_id);assert.equal(finish.attempt_id,row.attempt_id);
    assert.equal(finish.output_sha256,sha(Buffer.from(stable(row))));
    assert.equal(finish.status,row.decision.status);
    assert(['ok','invalid_output'].includes(row.decision.status));
  }
  return {terminal_sha256:shaFile(file(manifest.suffix.terminal)),output_sha256:shaFile(output),journal_sha256:shaFile(journal)};
}
function reviewCheck(manifest,args,suffix) {
  assert.equal(args['approved-manifest-sha256'],shaFile(manifestPath));
  assert(args['review-receipt']&&args['review-receipt-sha256']);
  const p=file(args['review-receipt']);assert.equal(shaFile(p),args['review-receipt-sha256']);
  const receipt=read(p);
  assert.equal(receipt.approved_for_execution,true);
  assert.equal(receipt.manifest_sha256,shaFile(manifestPath));
  assert.equal(receipt.controller_sha256,shaFile(__filename));
  assert.equal(receipt.original_interruption_audit_sha256,manifest.parent.interruption_audit_sha256);
  assert.equal(receipt.suffix_terminal_sha256,suffix.terminal_sha256);
  assert.equal(receipt.suffix_output_sha256,suffix.output_sha256);
  assert.equal(receipt.suffix_journal_sha256,suffix.journal_sha256);
  assert.equal(receipt.ambiguous_dev019_excluded,true);
  assert(receipt.approved_phases?.includes(args.phase));
  if(args.phase==='development') {
    assert(args['inspection-receipt']&&args['inspection-receipt-sha256']);
    const ip=file(args['inspection-receipt']);assert.equal(shaFile(ip),args['inspection-receipt-sha256']);
    const inspection=read(ip);
    assert.equal(inspection.configuration,manifest.configuration);
    assert.equal(inspection.variant,manifest.variant);
    assert.equal(inspection.accepted_for_development,true);
    assert.equal(inspection.smoke_ids_inspected,3);
    assert.equal(inspection.smoke_output_sha256,shaFile(path.join(dir,'smoke.jsonl')));
    assert.equal(inspection.smoke_journal_sha256,shaFile(path.join(dir,'smoke.attempts.jsonl')));
    const terminal=read(path.join(dir,'smoke.terminal.json'));
    assert.equal(terminal.status,'completed');
    assert.equal(terminal.saved_rows,3);assert.equal(terminal.finished_attempts,3);
    assert.equal(terminal.ambiguous_timeout,false);
    assert.equal(inspection.smoke_terminal_sha256,shaFile(path.join(dir,'smoke.terminal.json')));
    parent.validateSmoke(lines(path.join(dir,'smoke.jsonl')),lines(path.join(dir,'smoke.attempts.jsonl')),manifest.configuration,manifest.variant);
  }
}
async function hashArtifact(p){const h=crypto.createHash('sha256');for await(const chunk of fs.createReadStream(p,{highWaterMark:8*1024*1024})) h.update(chunk);return h.digest('hex');}
function durable(fd,x){fs.writeSync(fd,stable(x)+'\n');fs.fsyncSync(fd);}
async function run(manifest,source,args) {
  assert(['smoke','development'].includes(args.phase));
  const suffix=checkSuffix(manifest,source);
  reviewCheck(manifest,args,suffix);
  const outputPath=path.join(dir,`${args.phase}.jsonl`),journalPath=path.join(dir,`${args.phase}.attempts.jsonl`),terminalPath=path.join(dir,`${args.phase}.terminal.json`);
  assert(![outputPath,journalPath,terminalPath].some(fs.existsSync),'Existing output/journal/terminal; no replay');
  const parentManifest=read(parentManifestPath),config=parentManifest.configs[manifest.configuration];
  const rows=source[manifest.configuration].records.filter(x=>x.variant===manifest.variant);
  const selected=args.phase==='smoke'?rows.slice(0,3):rows;
  const lockPath=file(parentManifest.local_gpu_lock_file);
  const lock=fs.openSync(lockPath,'wx');
  let output,journal,holdLock=false,completed=false,errorText=null,runtime=null,claimStarted=false;
  const preflightId=crypto.randomUUID(),startedPath=path.join(dir,`preflight-${preflightId}.started.json`),finishedPath=path.join(dir,`preflight-${preflightId}.terminal.json`);
  const manifestHash=shaFile(manifestPath);
  try {
    fs.writeSync(lock,stable({pid:process.pid,controller:'local-prompt-remaining-v2',config:manifest.configuration,variant:manifest.variant,phase:args.phase,started_utc:new Date().toISOString()}));fs.fsyncSync(lock);
    fs.writeFileSync(startedPath,stable({preflight_id:preflightId,manifest_sha256:manifestHash,controller_sha256:shaFile(__filename),phase:args.phase,started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    assert.equal(execFileSync(cliPath,['--version'],{encoding:'utf8',timeout:15000}).trim(),`CLI commit: ${parentManifest.runtime.cli_commit}`);
    const runtimes=execFileSync(cliPath,['runtime','ls'],{encoding:'utf8',timeout:15000});
    assert(runtimes.split('\n').some(x=>x.startsWith(parentManifest.runtime.selected_engine)&&x.includes('✓')&&x.includes('GGUF')));
    const loaded=parent.requireLoadedModel(execFileSync(cliPath,['ps'],{encoding:'utf8',timeout:15000}),config.identifier,8192,1);
    const hardware={model_identifier:execFileSync('/usr/sbin/sysctl',['-n','hw.model'],{encoding:'utf8'}).trim(),chip:execFileSync('/usr/sbin/sysctl',['-n','machdep.cpu.brand_string'],{encoding:'utf8'}).trim(),architecture:require('node:os').arch()};
    assert.deepEqual(hardware,parentManifest.hardware);
    assert.equal(await hashArtifact(path.join(parentManifest.runtime.models_dir,config.artifact_path)),config.artifact_sha256);
    const {LMStudioClient}=require(parentManifest.runtime.sdk_path);
    const model=new LMStudioClient().llm.createDynamicHandle(config.identifier),info=await model.getModelInfo();
    assert(info&&info.identifier===config.identifier&&info.path===config.artifact_path&&info.sizeBytes===config.artifact_bytes&&info.contextLength===8192&&info.quantization?.name==='Q4_K_M');
    runtime={cli_commit:parentManifest.runtime.cli_commit,selected_engine:parentManifest.runtime.selected_engine,lm_studio_version:parentManifest.runtime.lm_studio_version,loaded_model_line:loaded.trim(),hardware,artifact_sha256:config.artifact_sha256,surface:config.surface};
    for(const record of selected) {
      const before=await model.getModelInfo();assert.equal(before?.instanceReference,info.instanceReference,'Loaded instance changed');
      const baseline=source[manifest.configuration].baseline.get(record.id),counted=source[manifest.configuration].counts.get(`P1/${record.id}`);
      const request={messages:record.messages,config:baseline.request.config},requestHash=sha(Buffer.from(stable(request)));
      assert.equal(requestHash,record.request_sha256);
      const attempt=crypto.randomUUID();
      if(output===undefined){journal=fs.openSync(journalPath,'wx');output=fs.openSync(outputPath,'wx');}
      claimStarted=true;
      durable(journal,{event:'started',attempt_id:attempt,id:record.id,configuration:manifest.configuration,variant:'P1',phase:args.phase,request_sha256:requestHash,manifest_sha256:manifestHash,timeout_ms:config.timeout_ms,at:new Date().toISOString()});
      const started=performance.now();let response=null,decision;
      try {
        response=await require('./lmstudio_reasoning_benchmark.cjs').predictWithTimeout(model,record.messages,baseline.request.config,config.timeout_ms);
        const after=await model.getModelInfo();
        decision=after?.instanceReference!==info.instanceReference?{status:'control_failure',reason:'loaded_instance_changed'}:parent.classifySdk(response,{identifier:config.identifier,path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:counted.prompt_tokens+config.native_token_delta,predictionConfig:baseline.prediction_config,loadConfig:baseline.load_config});
      } catch(e) {if(e.code==='PREDICTION_TIMEOUT'&&e.cancellationAcknowledged!==true) holdLock=true;decision={status:e.code==='PREDICTION_TIMEOUT'?'timeout':'service_failure',reason:String(e.message),cancellation_acknowledged:e.cancellationAcknowledged??null};}
      const row={id:record.id,configuration:manifest.configuration,variant:'P1',phase:args.phase,attempt_id:attempt,manifest_sha256:manifestHash,controller_sha256:shaFile(__filename),timeout_ms:config.timeout_ms,runtime_attestation:runtime,request,request_sha256:requestHash,rendered_sha256:counted.rendered_sha256,expected_prompt_tokens:counted.prompt_tokens+config.native_token_delta,reference_labels_read:false,model_identifier:config.identifier,model_path:config.artifact_path,raw_response:response?.content??null,non_reasoning_content:response?.nonReasoningContent??null,reasoning_content:response?.reasoningContent??null,http_status:null,stats:response?.stats??null,model_info:response?.modelInfo??null,load_config:response?.loadConfig??null,prediction_config:response?.predictionConfig??null,decision,elapsed_seconds:(performance.now()-started)/1000,finished_utc:new Date().toISOString()};
      durable(output,row);durable(journal,{event:'finished',attempt_id:attempt,id:record.id,status:decision.status,output_sha256:sha(Buffer.from(stable(row))),at:new Date().toISOString()});
      console.log(manifest.configuration,'P1',args.phase,record.id,decision.status);
      if(['control_failure','service_failure','timeout'].includes(decision.status)) throw Error(`Stopped after ${record.id}: ${decision.reason}`);
    }
    completed=true;
  } catch(e){errorText=String(e.message);throw e;}
  finally {
    if(output!==undefined)fs.closeSync(output);if(journal!==undefined)fs.closeSync(journal);
    if(!claimStarted){for(const p of [outputPath,journalPath])if(fs.existsSync(p)){assert.equal(fs.statSync(p).size,0);fs.unlinkSync(p);}}
    fs.writeFileSync(finishedPath,stable({preflight_id:preflightId,status:claimStarted?'passed':'failed_before_request',first_request_claimed:claimStarted,stopped_reason:claimStarted?null:errorText,runtime_attestation:runtime,finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    if(claimStarted){const saved=lines(outputPath),events=lines(journalPath);fs.writeFileSync(terminalPath,stable({configuration:manifest.configuration,variant:'P1',phase:args.phase,status:completed?'completed':'stopped',manifest_sha256:manifestHash,controller_sha256:shaFile(__filename),requested_records:selected.length,claimed_attempts:events.filter(x=>x.event==='started').length,finished_attempts:events.filter(x=>x.event==='finished').length,saved_rows:saved.length,ok_rows:saved.filter(x=>x.decision.status==='ok').length,invalid_output_rows:saved.filter(x=>x.decision.status==='invalid_output').length,ambiguous_timeout:holdLock,timeout_ms:config.timeout_ms,runtime_attestation:runtime,output_sha256:shaFile(outputPath),journal_sha256:shaFile(journalPath),stopped_reason:errorText,finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});}
    fs.closeSync(lock);if(!holdLock)fs.unlinkSync(lockPath);
  }
}
async function main(){const args=parent.argsFrom(process.argv.slice(2)),manifest=read(manifestPath),source=checkSource(manifest);if(args.mode==='validate'){console.log(stable({validated:true,configuration:manifest.configuration,variant:manifest.variant,manifest_sha256:shaFile(manifestPath)}));return;}if(args.mode==='admission'){console.log(stable({admitted:true,...checkSuffix(manifest,source)}));return;}if(args.mode==='run')return run(manifest,source,args);throw Error('Use --mode validate, admission, or run');}
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=1;});
module.exports={checkSource,checkSuffix,reviewCheck};
