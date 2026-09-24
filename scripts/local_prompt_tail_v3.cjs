#!/usr/bin/env node
// Exact local P1/P2 tail: ten frozen conditions after Qwen3.5-4B thinking-on/P1.
// Input-only until an independently reviewed phase is admitted.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const parent=require('./local_prompt_execution_v1.cjs');
const root=path.resolve(__dirname,'..');
const dir=path.join(root,'results/local-prompt-tail-v3');
const manifestPath=path.join(dir,'manifest.json');
const parentManifestPath=path.join(root,'results/local-prompt-exact-v1/manifest.json');
const cliPath='/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms';
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const shaFile=p=>sha(fs.readFileSync(p));
const stable=x=>JSON.stringify(x);
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const lines=p=>fs.readFileSync(p,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const ids=()=>Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`);
function file(p){assert.equal(typeof p,'string');assert(!path.isAbsolute(p)&&!p.split('/').includes('..'),'Unsafe path');const full=path.resolve(root,p);assert(full.startsWith(root+path.sep),'Path outside repository');return full;}
function phaseDir(c){return path.join(dir,c.configuration,c.variant);}
function conditionIndex(m,configuration,variant){return m.conditions.findIndex(x=>x.configuration===configuration&&x.variant===variant);}
function checkSource(m) {
  assert.equal(m.version,'local-prompt-tail-v3');
  assert.equal(m.status,'DRAFT_PENDING_ROOT_REVIEW_NO_INFERENCE');
  assert.equal(m.reference_labels_read,false);assert.equal(m.inference_performed,false);
  assert.equal(shaFile(__filename),m.controller_sha256,'Controller drift');
  assert.equal(shaFile(parentManifestPath),m.parent.manifest_sha256,'Parent manifest drift');
  assert.equal(shaFile(path.join(root,'scripts/local_prompt_execution_v1.cjs')),m.parent.controller_sha256,'Parent controller drift');
  assert.equal(shaFile(file(m.parent.review)),m.parent.review_sha256,'Parent review drift');
  assert.equal(shaFile(file(m.predecessor.manifest)),m.predecessor.manifest_sha256,'P1 predecessor manifest drift');
  assert.equal(shaFile(path.join(root,'scripts/local_prompt_remaining_v2.cjs')),m.predecessor.controller_sha256,'P1 predecessor controller drift');
  const pm=read(parentManifestPath),source=parent.sourceCheck(pm);
  const order=pm.config_order.flatMap(configuration=>pm.configs[configuration].conditions.map(variant=>({configuration,variant})));
  const predecessorIndex=order.findIndex(x=>x.configuration===m.predecessor.configuration&&x.variant===m.predecessor.variant);
  assert(predecessorIndex>=0);
  assert.deepEqual(m.conditions.map(({configuration,variant})=>({configuration,variant})),order.slice(predecessorIndex+1));
  assert.equal(m.conditions.length,10);
  assert.equal(new Set(m.conditions.map(x=>`${x.configuration}/${x.variant}`)).size,10);
  for(const c of m.conditions) {
    assert.equal(pm.configs[c.configuration].surface,'lmstudio_sdk');
    assert.equal(typeof c.exact_hosted_model,'string');assert(c.exact_hosted_model.length>0);
    assert.deepEqual(source[c.configuration].records.filter(x=>x.variant===c.variant).map(x=>x.id),ids());
  }
  return source;
}
function verifyCompleted(manifest,source,c,base,expectedManifest,expectedController) {
  const terminalPath=path.join(base,'development.terminal.json');
  const outputPath=path.join(base,'development.jsonl');
  const journalPath=path.join(base,'development.attempts.jsonl');
  const t=read(terminalPath);
  assert.equal(t.configuration,c.configuration);assert.equal(t.variant,c.variant);
  assert.equal(t.phase,'development');assert.equal(t.status,'completed');
  assert.equal(t.manifest_sha256,expectedManifest);assert.equal(t.controller_sha256,expectedController);
  assert.equal(t.requested_records,60);assert.equal(t.saved_rows,60);
  assert.equal(t.claimed_attempts,60);assert.equal(t.finished_attempts,60);
  assert.equal(t.ambiguous_timeout,false);
  assert.equal(t.output_sha256,shaFile(outputPath));assert.equal(t.journal_sha256,shaFile(journalPath));
  const saved=lines(outputPath),events=lines(journalPath),frozen=source[c.configuration].records.filter(x=>x.variant===c.variant);
  assert.deepEqual(saved.map(x=>x.id),ids());assert.equal(events.length,120);
  for(let i=0;i<60;i++) {
    const row=saved[i],start=events[2*i],finish=events[2*i+1];
    assert.equal(row.configuration,c.configuration);assert.equal(row.variant,c.variant);assert.equal(row.phase,'development');
    assert.equal(row.manifest_sha256,expectedManifest);assert.equal(row.controller_sha256,expectedController);
    assert.equal(row.request_sha256,frozen[i].request_sha256);
    assert.equal(sha(Buffer.from(stable(row.request))),frozen[i].request_sha256);
    assert(['ok','invalid_output'].includes(row.decision.status));
    assert.equal(start.event,'started');assert.equal(finish.event,'finished');
    assert.equal(start.id,row.id);assert.equal(finish.id,row.id);
    assert.equal(start.attempt_id,row.attempt_id);assert.equal(finish.attempt_id,row.attempt_id);
    assert.equal(start.request_sha256,row.request_sha256);assert.equal(finish.status,row.decision.status);
    assert.equal(finish.output_sha256,sha(Buffer.from(stable(row))));
  }
  return {terminal_sha256:shaFile(terminalPath),output_sha256:shaFile(outputPath),journal_sha256:shaFile(journalPath)};
}
function checkPredecessor(m,source,index) {
  assert(Number.isInteger(index)&&index>=0&&index<m.conditions.length);
  if(index===0)return verifyCompleted(m,source,m.predecessor,file(m.predecessor.output_dir),m.predecessor.manifest_sha256,m.predecessor.controller_sha256);
  const previous=m.conditions[index-1];
  return verifyCompleted(m,source,previous,phaseDir(previous),shaFile(manifestPath),shaFile(__filename));
}
function validateRouteEvidence(c,r,now=Date.now()){
  assert.equal(r.configuration,c.configuration);
  assert.equal(r.exact_model,c.exact_hosted_model);
  assert.deepEqual(r.exact_routes,[],'Exact hosted route now available; local execution not admitted');
  assert.equal(r.source,'https://openrouter.ai/api/v1/models');
  const checked=Date.parse(r.checked_utc);
  assert(Number.isFinite(checked),'Missing route check timestamp');
  assert(checked<=now+5*60*1000,'Future route check timestamp');
  assert(now-checked<=24*60*60*1000,'Hosted availability check older than 24 hours');
}
function checkRoute(m,c,receipt){
  const rp=file(receipt.route_evidence);
  assert.equal(shaFile(rp),receipt.route_evidence_sha256);
  validateRouteEvidence(c,read(rp));
}
function reviewCheck(m,c,phase,args,predecessor){
  assert.equal(args['approved-manifest-sha256'],shaFile(manifestPath));
  assert(args['review-receipt']&&args['review-receipt-sha256']);
  const p=file(args['review-receipt']);assert.equal(shaFile(p),args['review-receipt-sha256']);
  const r=read(p);
  assert.equal(r.approved_for_execution,true);
  assert.equal(r.manifest_sha256,shaFile(manifestPath));assert.equal(r.controller_sha256,shaFile(__filename));
  assert.equal(r.configuration,c.configuration);assert.equal(r.variant,c.variant);
  assert.equal(r.predecessor_terminal_sha256,predecessor.terminal_sha256);
  assert.equal(r.predecessor_output_sha256,predecessor.output_sha256);
  assert.equal(r.predecessor_journal_sha256,predecessor.journal_sha256);
  assert(r.approved_phases?.includes(phase));
  checkRoute(m,c,r);
  if(phase==='development') {
    assert(args['inspection-receipt']&&args['inspection-receipt-sha256']);
    const ip=file(args['inspection-receipt']);assert.equal(shaFile(ip),args['inspection-receipt-sha256']);
    const inspection=read(ip),base=phaseDir(c),terminal=read(path.join(base,'smoke.terminal.json'));
    assert.equal(inspection.configuration,c.configuration);assert.equal(inspection.variant,c.variant);
    assert.equal(inspection.accepted_for_development,true);assert.equal(inspection.smoke_ids_inspected,3);
    assert.equal(terminal.status,'completed');assert.equal(terminal.saved_rows,3);assert.equal(terminal.finished_attempts,3);
    assert.equal(terminal.ambiguous_timeout,false);
    assert.equal(inspection.smoke_output_sha256,shaFile(path.join(base,'smoke.jsonl')));
    assert.equal(inspection.smoke_journal_sha256,shaFile(path.join(base,'smoke.attempts.jsonl')));
    assert.equal(inspection.smoke_terminal_sha256,shaFile(path.join(base,'smoke.terminal.json')));
    parent.validateSmoke(lines(path.join(base,'smoke.jsonl')),lines(path.join(base,'smoke.attempts.jsonl')),c.configuration,c.variant);
  }
}
async function hashArtifact(p){const h=crypto.createHash('sha256');for await(const chunk of fs.createReadStream(p,{highWaterMark:8*1024*1024}))h.update(chunk);return h.digest('hex');}
function durable(fd,x){fs.writeSync(fd,stable(x)+'\n');fs.fsyncSync(fd);}
async function run(m,source,c,args) {
  assert(['smoke','development'].includes(args.phase));
  const index=conditionIndex(m,c.configuration,c.variant),predecessor=checkPredecessor(m,source,index);
  reviewCheck(m,c,args.phase,args,predecessor);
  const base=phaseDir(c),outputPath=path.join(base,`${args.phase}.jsonl`),journalPath=path.join(base,`${args.phase}.attempts.jsonl`),terminalPath=path.join(base,`${args.phase}.terminal.json`);
  assert(![outputPath,journalPath,terminalPath].some(fs.existsSync),'Existing output/journal/terminal; no replay');
  fs.mkdirSync(base,{recursive:true});
  const pm=read(parentManifestPath),config=pm.configs[c.configuration],selected=source[c.configuration].records.filter(x=>x.variant===c.variant);
  const records=args.phase==='smoke'?selected.slice(0,3):selected;
  const lockPath=file(pm.local_gpu_lock_file),lock=fs.openSync(lockPath,'wx');
  const preflightId=crypto.randomUUID(),startedPath=path.join(base,`preflight-${preflightId}.started.json`),finishedPath=path.join(base,`preflight-${preflightId}.terminal.json`);
  const manifestHash=shaFile(manifestPath),controllerHash=shaFile(__filename);
  let output,journal,holdLock=false,complete=false,errorText=null,runtime=null,claimed=false;
  try {
    fs.writeSync(lock,stable({pid:process.pid,controller:'local-prompt-tail-v3',configuration:c.configuration,variant:c.variant,phase:args.phase,started_utc:new Date().toISOString()}));fs.fsyncSync(lock);
    fs.writeFileSync(startedPath,stable({preflight_id:preflightId,configuration:c.configuration,variant:c.variant,phase:args.phase,manifest_sha256:manifestHash,controller_sha256:controllerHash,predecessor_terminal_sha256:predecessor.terminal_sha256,started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    assert.equal(execFileSync(cliPath,['--version'],{encoding:'utf8',timeout:15000}).trim(),`CLI commit: ${pm.runtime.cli_commit}`);
    const runtimes=execFileSync(cliPath,['runtime','ls'],{encoding:'utf8',timeout:15000});
    assert(runtimes.split('\n').some(x=>x.startsWith(pm.runtime.selected_engine)&&x.includes('✓')&&x.includes('GGUF')));
    const loaded=parent.requireLoadedModel(execFileSync(cliPath,['ps'],{encoding:'utf8',timeout:15000}),config.identifier,8192,1);
    const hardware={model_identifier:execFileSync('/usr/sbin/sysctl',['-n','hw.model'],{encoding:'utf8'}).trim(),chip:execFileSync('/usr/sbin/sysctl',['-n','machdep.cpu.brand_string'],{encoding:'utf8'}).trim(),architecture:require('node:os').arch()};
    assert.deepEqual(hardware,pm.hardware);
    assert.equal(await hashArtifact(path.join(pm.runtime.models_dir,config.artifact_path)),config.artifact_sha256);
    const {LMStudioClient}=require(pm.runtime.sdk_path);
    const model=new LMStudioClient().llm.createDynamicHandle(config.identifier),info=await model.getModelInfo();
    assert(info&&info.identifier===config.identifier&&info.path===config.artifact_path&&info.sizeBytes===config.artifact_bytes&&info.contextLength===8192&&info.quantization?.name==='Q4_K_M');
    runtime={cli_commit:pm.runtime.cli_commit,selected_engine:pm.runtime.selected_engine,lm_studio_version:pm.runtime.lm_studio_version,loaded_model_line:loaded.trim(),hardware,artifact_sha256:config.artifact_sha256,surface:config.surface};
    for(const record of records) {
      const before=await model.getModelInfo();assert.equal(before?.instanceReference,info.instanceReference,'Loaded instance changed');
      const baseline=source[c.configuration].baseline.get(record.id),counted=source[c.configuration].counts.get(`${c.variant}/${record.id}`);
      const request={messages:record.messages,config:baseline.request.config},requestHash=sha(Buffer.from(stable(request)));
      assert.equal(requestHash,record.request_sha256);
      const attempt=crypto.randomUUID();
      if(output===undefined){journal=fs.openSync(journalPath,'wx');output=fs.openSync(outputPath,'wx');}
      claimed=true;
      durable(journal,{event:'started',attempt_id:attempt,id:record.id,configuration:c.configuration,variant:c.variant,phase:args.phase,request_sha256:requestHash,manifest_sha256:manifestHash,controller_sha256:controllerHash,timeout_ms:config.timeout_ms,at:new Date().toISOString()});
      const started=performance.now();let response=null,decision;
      try {
        response=await require('./lmstudio_reasoning_benchmark.cjs').predictWithTimeout(model,record.messages,baseline.request.config,config.timeout_ms);
        const after=await model.getModelInfo();
        decision=after?.instanceReference!==info.instanceReference?{status:'control_failure',reason:'loaded_instance_changed'}:parent.classifySdk(response,{identifier:config.identifier,path:config.artifact_path,bytes:config.artifact_bytes,promptTokens:counted.prompt_tokens+config.native_token_delta,predictionConfig:baseline.prediction_config,loadConfig:baseline.load_config});
      }catch(e){if(e.code==='PREDICTION_TIMEOUT'&&e.cancellationAcknowledged!==true)holdLock=true;decision={status:e.code==='PREDICTION_TIMEOUT'?'timeout':'service_failure',reason:String(e.message),cancellation_acknowledged:e.cancellationAcknowledged??null};}
      const row={id:record.id,configuration:c.configuration,variant:c.variant,phase:args.phase,attempt_id:attempt,manifest_sha256:manifestHash,controller_sha256:controllerHash,predecessor_terminal_sha256:predecessor.terminal_sha256,timeout_ms:config.timeout_ms,runtime_attestation:runtime,request,request_sha256:requestHash,rendered_sha256:counted.rendered_sha256,expected_prompt_tokens:counted.prompt_tokens+config.native_token_delta,reference_labels_read:false,model_identifier:config.identifier,model_path:config.artifact_path,raw_response:response?.content??null,non_reasoning_content:response?.nonReasoningContent??null,reasoning_content:response?.reasoningContent??null,stats:response?.stats??null,model_info:response?.modelInfo??null,load_config:response?.loadConfig??null,prediction_config:response?.predictionConfig??null,decision,elapsed_seconds:(performance.now()-started)/1000,finished_utc:new Date().toISOString()};
      durable(output,row);durable(journal,{event:'finished',attempt_id:attempt,id:record.id,status:decision.status,output_sha256:sha(Buffer.from(stable(row))),at:new Date().toISOString()});
      console.log(c.configuration,c.variant,args.phase,record.id,decision.status);
      if(['control_failure','service_failure','timeout'].includes(decision.status))throw Error(`Stopped after ${record.id}: ${decision.reason}`);
    }
    complete=true;
  }catch(e){errorText=String(e.message);throw e;}
  finally {
    if(output!==undefined)fs.closeSync(output);if(journal!==undefined)fs.closeSync(journal);
    if(!claimed)for(const p of [outputPath,journalPath])if(fs.existsSync(p)){assert.equal(fs.statSync(p).size,0);fs.unlinkSync(p);}
    fs.writeFileSync(finishedPath,stable({preflight_id:preflightId,status:claimed?'passed':'failed_before_request',first_request_claimed:claimed,manifest_sha256:manifestHash,controller_sha256:controllerHash,runtime_attestation:runtime,stopped_reason:claimed?null:errorText,finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    if(claimed){const saved=lines(outputPath),events=lines(journalPath);fs.writeFileSync(terminalPath,stable({configuration:c.configuration,variant:c.variant,phase:args.phase,status:complete?'completed':'stopped',manifest_sha256:manifestHash,controller_sha256:controllerHash,predecessor_terminal_sha256:predecessor.terminal_sha256,requested_records:records.length,claimed_attempts:events.filter(x=>x.event==='started').length,finished_attempts:events.filter(x=>x.event==='finished').length,saved_rows:saved.length,ok_rows:saved.filter(x=>x.decision.status==='ok').length,invalid_output_rows:saved.filter(x=>x.decision.status==='invalid_output').length,ambiguous_timeout:holdLock,timeout_ms:config.timeout_ms,runtime_attestation:runtime,output_sha256:shaFile(outputPath),journal_sha256:shaFile(journalPath),stopped_reason:errorText,finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});}
    fs.closeSync(lock);if(!holdLock)fs.unlinkSync(lockPath);
  }
}
async function main(){const args=parent.argsFrom(process.argv.slice(2)),m=read(manifestPath),source=checkSource(m);if(args.mode==='validate'){console.log(stable({validated:true,conditions:m.conditions.length,manifest_sha256:shaFile(manifestPath),controller_sha256:shaFile(__filename)}));return;}assert(args.config&&args.variant,'--config and --variant required');const index=conditionIndex(m,args.config,args.variant);assert(index>=0,'Condition not in frozen ten-condition tail');const c=m.conditions[index];if(args.mode==='admission'){console.log(stable({admitted:true,configuration:c.configuration,variant:c.variant,...checkPredecessor(m,source,index)}));return;}if(args.mode==='run')return run(m,source,c,args);throw Error('Use --mode validate, admission, or run');}
if(require.main===module)main().catch(e=>{console.error(e.message);process.exitCode=1;});
module.exports={checkSource,checkPredecessor,checkRoute,validateRouteEvidence,reviewCheck,conditionIndex};
