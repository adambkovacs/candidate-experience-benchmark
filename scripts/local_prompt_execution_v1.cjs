#!/usr/bin/env node
// Frozen local P1/P2 continuation. Reference labels are never read here.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const http = require('node:http');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const runDir = path.join(root, 'results/local-prompt-exact-v1');
const manifestPath = path.join(runDir, 'manifest.json');
const preflightPath = path.join(runDir, 'preflight-summary.json');
const cliPath = '/Applications/LM Studio.app/Contents/Resources/app/.webpack/lms';
const decisionKeys = ['sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const shaFile = filename => sha(fs.readFileSync(filename));
const readJson = filename => JSON.parse(fs.readFileSync(filename,'utf8'));
const readJsonl = filename => fs.readFileSync(filename,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const stable = value => JSON.stringify(value);
const rel = filename => {
  assert.equal(typeof filename,'string');
  assert(!path.isAbsolute(filename) && !filename.split('/').includes('..'),'Unsafe path');
  const full = path.resolve(root,filename);
  assert(full.startsWith(root+path.sep),'Path outside repository');
  return full;
};
function argsFrom(argv) {
  const args={};
  for(let i=0;i<argv.length;i+=2) {
    assert(argv[i]?.startsWith('--') && i+1<argv.length,'Expected --key value pairs');
    assert(!Object.hasOwn(args,argv[i].slice(2)),'Duplicate argument');
    args[argv[i].slice(2)]=argv[i+1];
  }
  return args;
}
function requireLoadedModel(ps,identifier,expectedContext=8192,expectedParallel=1) {
  const lines=ps.split('\n').map(line=>line.trim()).filter(Boolean);
  const header=lines.shift()?.split(/\s{2,}/);
  assert(header,'Missing lms ps header');
  const identifierIndex=header.indexOf('IDENTIFIER');
  const contextIndex=header.indexOf('CONTEXT');
  const parallelIndex=header.indexOf('PARALLEL');
  assert(identifierIndex>=0 && contextIndex>=0 && parallelIndex>=0,'Missing lms ps columns');
  const matches=lines.map(line=>({line,columns:line.split(/\s{2,}/)}))
    .filter(row=>row.columns[identifierIndex]===identifier);
  assert.equal(matches.length,1,'Loaded model missing or duplicated');
  const row=matches[0];
  assert.equal(row.columns[contextIndex],String(expectedContext),'Loaded context mismatch');
  assert.equal(row.columns[parallelIndex],String(expectedParallel),'Loaded parallelism mismatch');
  return row.line;
}
function normalizedFields(value) {
  return Object.fromEntries((value?.fields || []).map(field=>[field.key,field.value]).sort((a,b)=>a[0].localeCompare(b[0])));
}
function validPrediction(value) {
  return value && typeof value==='object' && !Array.isArray(value) &&
    stable(Object.keys(value).sort())===stable([...decisionKeys].sort()) && decisionKeys.every(key=>
      (key==='sentiment' ? ['positive','negative','mixed','neutral','insufficient_information'] :
        ['yes','no','insufficient_information']).includes(value[key]));
}
function classifySdk(result,expected) {
  const info=result?.modelInfo;
  if(!info || info.identifier!==expected.identifier || info.path!==expected.path ||
     info.sizeBytes!==expected.bytes || info.contextLength!==8192 || info.quantization?.name!=='Q4_K_M')
    return {status:'control_failure',reason:'model_identity'};
  if(stable(normalizedFields(result.predictionConfig))!==stable(normalizedFields(expected.predictionConfig)))
    return {status:'control_failure',reason:'prediction_config'};
  if(stable(normalizedFields(result.loadConfig))!==stable(normalizedFields(expected.loadConfig)))
    return {status:'control_failure',reason:'load_config'};
  if(result.stats?.promptTokensCount!==expected.promptTokens)
    return {status:'control_failure',reason:'prompt_token_count'};
  if(typeof result.content!=='string' || typeof result.nonReasoningContent!=='string')
    return {status:'service_failure',reason:'malformed_sdk_result'};
  let parsed;
  try { parsed=JSON.parse(result.nonReasoningContent); }
  catch { return {status:'invalid_output',reason:'non_json'}; }
  if(!validPrediction(parsed)) return {status:'invalid_output',reason:'schema'};
  if(!['eosFound','stopStringFound'].includes(result.stats?.stopReason))
    return {status:'invalid_output',reason:'stop_reason'};
  return {status:'ok',prediction:parsed};
}
function classifyHttp(response,expected) {
  if(!response || response.httpStatus!==200 || !response.body || typeof response.body!=='object')
    return {status:'service_failure',reason:'http_response'};
  const body=response.body;
  if(body.model!==expected.identifier) return {status:'control_failure',reason:'returned_model'};
  if(body.usage?.prompt_tokens!==expected.promptTokens)
    return {status:'control_failure',reason:'prompt_token_count'};
  const choices=body.choices;
  if(!Array.isArray(choices) || choices.length!==1 || !choices[0]?.message ||
     typeof choices[0].message.content!=='string') return {status:'service_failure',reason:'malformed_http_result'};
  let parsed;
  try { parsed=JSON.parse(choices[0].message.content); }
  catch { return {status:'invalid_output',reason:'non_json'}; }
  if(!validPrediction(parsed)) return {status:'invalid_output',reason:'schema'};
  if(choices[0].finish_reason!=='stop' || choices[0].message.refusal)
    return {status:'invalid_output',reason:'finish_or_refusal'};
  return {status:'ok',prediction:parsed};
}
function appendDurable(fd,record) {
  fs.writeSync(fd,stable(record)+'\n');
  fs.fsyncSync(fd);
}
function clearEmptyUnclaimed(outputPath,journalPath,claimStarted) {
  if(claimStarted) return;
  const existing=[outputPath,journalPath].filter(fs.existsSync);
  for(const filename of existing)
    assert.equal(fs.statSync(filename).size,0,'Nonempty unclaimed attempt evidence');
  for(const filename of existing) fs.unlinkSync(filename);
}
function finishPreflightAttempt(paths,details) {
  clearEmptyUnclaimed(paths.output,paths.journal,details.claimStarted);
  if(details.started) fs.writeFileSync(paths.preflightTerminal,stable({
    preflight_id:details.id,configuration:details.configuration,variant:details.variant,
    phase:details.phase,status:details.claimStarted?'passed':'failed_before_request',
    manifest_sha256:details.manifestHash,preflight_sha256:details.preflightHash,
    controller_sha256:details.controllerHash,first_request_claimed:details.claimStarted,
    stopped_reason:details.claimStarted?null:details.error,
    runtime_attestation:details.runtime,finished_utc:new Date().toISOString()})+'\n',{flag:'wx'});
}
function canonicalFeedback() {
  const inputs=readJsonl(rel('data/pilot/inputs.jsonl'));
  assert.deepEqual(inputs.map(row=>row.id),Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
  assert(inputs.every(row=>stable(Object.keys(row).sort())===stable(['feedback','id'])));
  return new Map(inputs.map(row=>[row.id,row.feedback]));
}
function sourceCheck(manifest) {
  assert.equal(manifest.version,'local-prompt-exact-v1');
  assert.equal(manifest.reference_labels_read,false);
  assert.equal(manifest.inference_performed,false);
  assert.equal(manifest.runtime.sdk_sha256,shaFile(manifest.runtime.sdk_path));
  assert.equal(manifest.runtime.cli_sha256,shaFile(cliPath));
  assert.equal(manifest.runtime.app_plist_sha256,shaFile(manifest.runtime.app_plist_path));
  for(const [filename,expected] of Object.entries(manifest.source_sha256))
    assert.equal(shaFile(rel(filename)),expected,`Source drift: ${filename}`);
  assert.equal(shaFile(__filename),manifest.controller_sha256,'Controller drift');
  assert.equal(shaFile(preflightPath),manifest.preflight_sha256,'Preflight drift');
  const preflight=readJson(preflightPath);
  assert.equal(preflight.total_configs,9);
  assert.equal(preflight.total_rendered_condition_records,1620);
  assert.equal(preflight.total_context_fits,1620);
  assert.equal(preflight.reference_labels_read,false);
  assert.equal(preflight.inference_performed,false);
  const roster=readJson(rel(manifest.roster_file)).entries;
  const schedule=readJson(rel(manifest.schedule_file)).order;
  const selected=schedule.filter(item=>Object.hasOwn(manifest.configs,item.id));
  assert.equal(selected.length,9);
  assert.deepEqual(selected.map(item=>item.id),manifest.config_order);
  assert.deepEqual(selected.map(item=>item.conditions),manifest.config_order.map(id=>manifest.configs[id].conditions));
  assert(manifest.config_order.every(id=>roster.some(item=>item.id===id && item.state==='scheduled')));
  const feedback=canonicalFeedback();
  const {compose_instruction}=require(rel('scripts/frozen_prompt_variants.cjs'));
  const sdkRows=readJsonl(rel(manifest.sdk_rendered_file));
  const httpRows=readJsonl(rel(manifest.http_messages_file));
  const httpRendered=readJsonl(rel(manifest.http_rendered_file));
  assert.equal(sdkRows.length,1440);assert.equal(httpRows.length,180);assert.equal(httpRendered.length,180);
  const httpRenderMap=new Map(httpRendered.map(row=>[`${row.configuration}/${row.variant}/${row.id}`,row]));
  assert.equal(httpRenderMap.size,180);
  const source={};
  for(const id of manifest.config_order) {
    const config=manifest.configs[id];
    const baseline=readJsonl(rel(config.baseline_file));
    const parentManifest=readJson(rel(config.baseline_manifest_file));
    assert.equal(parentManifest.artifact.sha256,config.artifact_sha256);
    assert.equal(parentManifest.artifact.bytes,config.artifact_bytes);
    assert.equal(`${parentManifest.artifact.repo}/${parentManifest.artifact.file}`,config.artifact_path);
    assert.equal(parentManifest.artifact.quantization,'Q4_K_M');
    assert.deepEqual(baseline.map(row=>row.id),Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
    assert(baseline.every(row=>row.requested_model===config.identifier));
    if(config.surface==='local_http')
      assert(baseline.every(row=>row.surface==='LM Studio local HTTP' && row.temperature===0 && row.max_tokens===512));
    else assert(baseline.every(row=>row.surface==='LM Studio JavaScript SDK'));
    const baselineHash=shaFile(rel(config.baseline_file));
    const p0=new Map(baseline.map(row=>[row.id,row]));
    const records=(config.surface==='local_http' ? httpRows : sdkRows).filter(row=>row.configuration===id);
    const counts=readJsonl(rel(config.counts_file)).filter(row=>row.configuration===id);
    assert.equal(records.length,180);assert.equal(counts.length,180);
    const countMap=new Map(counts.map(row=>[`${row.variant}/${row.id}`,row]));
    assert.equal(countMap.size,180);
    for(const variant of ['P0','P1','P2']) {
      const subset=records.filter(row=>row.variant===variant);
      assert.deepEqual(subset.map(row=>row.id),baseline.map(row=>row.id));
      for(const record of subset) {
        const base=p0.get(record.id);
        assert.equal(record.source_file,config.baseline_file);
        assert.equal(record.source_sha256,baselineHash);
        assert.deepEqual(record.messages.map(m=>m.role),['system','user']);
        assert.deepEqual(JSON.parse(record.messages[1].content),{feedback:feedback.get(record.id)});
        const original=config.surface==='local_http' ? manifest.http_p0_instruction : base.request.messages[0].content;
        const composed=compose_instruction(original,variant,{role:'system',parent_baseline_id:id});
        assert.equal(record.messages[0].content,composed.instruction);
        assert.deepEqual(record.composition_audit,composed.audit);
        if(config.surface==='local_http') {
          assert.equal(base.policy_sha256,sha(Buffer.from(original)));
          assert.equal(base.usage.prompt_tokens,variant==='P0'?record.saved_p0_prompt_tokens:base.usage.prompt_tokens);
          const hr=httpRenderMap.get(`${id}/${variant}/${record.id}`);
          assert(hr && hr.messages_sha256===record.messages_sha256);
          assert.equal(sha(Buffer.from(stable(record.messages))),record.messages_sha256);
          assert.equal(sha(Buffer.from(hr.rendered)),hr.rendered_sha256);
        } else {
          assert.deepEqual(record.messages[1],base.request.messages[1]);
          assert.equal(sha(Buffer.from(stable({messages:record.messages,config:base.request.config}))),record.request_sha256);
          assert.equal(sha(Buffer.from(record.rendered)),record.rendered_sha256);
          assert.deepEqual(base.request.config,baseline[0].request.config);
          assert.equal(base.model_info.identifier,config.identifier);
          assert.equal(base.model_info.path,config.artifact_path);
          assert.equal(base.model_info.sizeBytes,config.artifact_bytes);
          assert.equal(base.model_info.quantization?.name,'Q4_K_M');
        }
        const counted=countMap.get(`${variant}/${record.id}`);
        assert(counted && counted.rendered_sha256===(config.surface==='local_http' ?
          httpRenderMap.get(`${id}/${variant}/${record.id}`).rendered_sha256 : record.rendered_sha256));
        assert.equal(counted.saved_p0_prompt_tokens,record.saved_p0_prompt_tokens);
        assert.equal(counted.output_reserve,config.output_reserve);
        assert.equal(counted.context,8192);
        assert.equal(counted.p0_delta,variant==='P0'?config.native_token_delta:null);
        assert(counted.prompt_tokens+config.native_token_delta+config.output_reserve<=8192);
      }
    }
    source[id]={records,baseline:p0,counts:countMap};
  }
  return source;
}
function orderCheck(manifest,id,variant,phase) {
  const order=manifest.config_order.flatMap(name=>manifest.configs[name].conditions.map(value=>[name,value]));
  const index=order.findIndex(([name,value])=>name===id && value===variant);
  assert(index>=0,'Not scheduled');
  if(phase==='smoke' && index>0) {
    const [priorId,priorVariant]=order[index-1];
    const terminal=readJson(path.join(runDir,priorId,priorVariant,'development.terminal.json'));
    assert.equal(terminal.status,'completed');
    assert.equal(terminal.saved_rows,60);
    assert.equal(terminal.finished_attempts,60);
    assert.equal(terminal.ambiguous_timeout,false);
    assert.equal(terminal.manifest_sha256,shaFile(manifestPath));
  }
}
function validateSmoke(rows,events,id,variant) {
  assert.deepEqual(rows.map(row=>row.id),['DEV-001','DEV-002','DEV-003']);
  assert.equal(events.length,6);
  for(let i=0;i<3;i++) {
    const row=rows[i],start=events[i*2],finish=events[i*2+1];
    assert.equal(row.configuration,id);assert.equal(row.variant,variant);assert.equal(row.phase,'smoke');
    assert(['ok','invalid_output'].includes(row.decision.status));
    assert.equal(start.event,'started');assert.equal(finish.event,'finished');
    assert.equal(start.attempt_id,row.attempt_id);assert.equal(finish.attempt_id,row.attempt_id);
    assert.equal(start.request_sha256,row.request_sha256);
    assert.equal(finish.output_sha256,sha(Buffer.from(stable(row))));
    assert.equal(finish.status,row.decision.status);
  }
}
function reviewCheck(manifest,opts) {
  assert.equal(opts['approved-manifest-sha256'],shaFile(manifestPath));
  assert.equal(opts['approved-preflight-sha256'],shaFile(preflightPath));
  assert(opts['review-receipt'] && opts['review-receipt-sha256']);
  const receiptPath=rel(opts['review-receipt']);
  assert.equal(shaFile(receiptPath),opts['review-receipt-sha256']);
  const receipt=readJson(receiptPath);
  assert.equal(receipt.approved_for_execution,true);
  assert.equal(receipt.manifest_sha256,shaFile(manifestPath));
  assert.equal(receipt.preflight_sha256,shaFile(preflightPath));
  assert.equal(receipt.controller_sha256,shaFile(__filename));
  assert(receipt.approved_conditions?.some(x=>x.config===opts.config && x.variant===opts.variant));
  assert(receipt.approved_phases?.includes(opts.phase));
  if(opts.phase==='development') {
    assert(opts['inspection-receipt'] && opts['inspection-receipt-sha256']);
    const inspectionPath=rel(opts['inspection-receipt']);
    assert.equal(shaFile(inspectionPath),opts['inspection-receipt-sha256']);
    const inspection=readJson(inspectionPath);
    assert.equal(inspection.config,opts.config);assert.equal(inspection.variant,opts.variant);
    assert.equal(inspection.accepted_for_development,true);
    assert.equal(inspection.smoke_ids_inspected,3);
    const dir=path.join(runDir,opts.config,opts.variant);
    assert.equal(inspection.smoke_output_sha256,shaFile(path.join(dir,'smoke.jsonl')));
    assert.equal(inspection.smoke_journal_sha256,shaFile(path.join(dir,'smoke.attempts.jsonl')));
    validateSmoke(readJsonl(path.join(dir,'smoke.jsonl')),readJsonl(path.join(dir,'smoke.attempts.jsonl')),opts.config,opts.variant);
  }
}
async function hashArtifact(file) {
  const digest=crypto.createHash('sha256');
  for await(const chunk of fs.createReadStream(file,{highWaterMark:8*1024*1024})) digest.update(chunk);
  return digest.digest('hex');
}
function httpRequest(payload,timeoutMs) {
  return new Promise((resolve,reject)=>{
    const body=Buffer.from(stable(payload));
    const headers={'Content-Type':'application/json','Content-Length':String(body.length)};
    if(process.env.LM_STUDIO_API_KEY) headers.Authorization=`Bearer ${process.env.LM_STUDIO_API_KEY}`;
    const req=http.request({hostname:'127.0.0.1',port:1234,path:'/v1/chat/completions',method:'POST',headers},res=>{
      const chunks=[];res.on('data',chunk=>chunks.push(chunk));res.on('end',()=>{
        const raw=Buffer.concat(chunks).toString('utf8');let parsed=null;
        try {parsed=JSON.parse(raw);} catch {}
        resolve({httpStatus:res.statusCode,rawBody:raw,body:parsed});
      });
    });
    req.setTimeout(timeoutMs,()=>req.destroy(Object.assign(Error('HTTP request timed out'),
      {code:'PREDICTION_TIMEOUT',cancellationAcknowledged:false})));
    req.on('error',reject);req.end(body);
  });
}
async function run(manifest,source,opts) {
  const config=manifest.configs[opts.config];
  assert(config && config.conditions.includes(opts.variant));
  assert(['smoke','development'].includes(opts.phase));
  reviewCheck(manifest,opts);
  orderCheck(manifest,opts.config,opts.variant,opts.phase);
  const dir=path.join(runDir,opts.config,opts.variant);
  const outputPath=path.join(dir,`${opts.phase}.jsonl`);
  const journalPath=path.join(dir,`${opts.phase}.attempts.jsonl`);
  const terminalPath=path.join(dir,`${opts.phase}.terminal.json`);
  assert(![outputPath,journalPath,terminalPath].some(fs.existsSync),'Existing output/journal/terminal; no replay');
  fs.mkdirSync(dir,{recursive:true});
  const lockPath=rel(manifest.local_gpu_lock_file);
  const lock=fs.openSync(lockPath,'wx');
  const preflightId=crypto.randomUUID();
  const preflightStartedPath=path.join(dir,`preflight-${preflightId}.started.json`);
  const preflightTerminalPath=path.join(dir,`preflight-${preflightId}.terminal.json`);
  let output,journal,holdLock=false,completed=false,terminalError=null,runtime=null;
  let preflightStarted=false,claimStarted=false;
  const manifestHash=shaFile(manifestPath),preflightHash=shaFile(preflightPath);
  const selected=source[opts.config].records.filter(row=>row.variant===opts.variant);
  const records=opts.phase==='smoke' ? selected.slice(0,3) : selected;
  try {
    fs.writeSync(lock,stable({pid:process.pid,config:opts.config,variant:opts.variant,phase:opts.phase,started_utc:new Date().toISOString()}));fs.fsyncSync(lock);
    fs.writeFileSync(preflightStartedPath,stable({preflight_id:preflightId,configuration:opts.config,
      variant:opts.variant,phase:opts.phase,manifest_sha256:manifestHash,
      preflight_sha256:preflightHash,controller_sha256:shaFile(__filename),
      started_utc:new Date().toISOString()})+'\n',{flag:'wx'});
    preflightStarted=true;
    const version=execFileSync(cliPath,['--version'],{encoding:'utf8',timeout:15000}).trim();
    assert.equal(version,`CLI commit: ${manifest.runtime.cli_commit}`);
    const runtimes=execFileSync(cliPath,['runtime','ls'],{encoding:'utf8',timeout:15000});
    assert(runtimes.split('\n').some(line=>line.startsWith(manifest.runtime.selected_engine)&&line.includes('✓')&&line.includes('GGUF')));
    const ps=execFileSync(cliPath,['ps'],{encoding:'utf8',timeout:15000});
    const loaded=requireLoadedModel(ps,config.identifier,config.context,1);
    const hardware={model_identifier:execFileSync('/usr/sbin/sysctl',['-n','hw.model'],{encoding:'utf8'}).trim(),
      chip:execFileSync('/usr/sbin/sysctl',['-n','machdep.cpu.brand_string'],{encoding:'utf8'}).trim(),
      architecture:require('node:os').arch()};
    assert.deepEqual(hardware,manifest.hardware);
    const artifact=path.join(manifest.runtime.models_dir,config.artifact_path);
    assert.equal(await hashArtifact(artifact),config.artifact_sha256,'Artifact drift');
    const {LMStudioClient}=require(manifest.runtime.sdk_path);
    const model=new LMStudioClient().llm.createDynamicHandle(config.identifier);
    const info=await model.getModelInfo();
    assert(info && info.identifier===config.identifier && info.path===config.artifact_path &&
      info.sizeBytes===config.artifact_bytes && info.contextLength===8192 && info.quantization?.name==='Q4_K_M');
    runtime={cli_commit:manifest.runtime.cli_commit,selected_engine:manifest.runtime.selected_engine,
      lm_studio_version:manifest.runtime.lm_studio_version,loaded_model_line:loaded.trim(),hardware,
      artifact_sha256:config.artifact_sha256,surface:config.surface};
    for(const record of records) {
      const before=await model.getModelInfo();
      assert.equal(before?.instanceReference,info.instanceReference,'Loaded instance changed');
      const baseline=source[opts.config].baseline.get(record.id);
      const counted=source[opts.config].counts.get(`${record.variant}/${record.id}`);
      const request=config.surface==='local_http' ?
        {model:config.identifier,temperature:0,max_tokens:512,stream:false,messages:record.messages,
          response_format:{type:'json_schema',json_schema:{name:'judgments',strict:true,
            schema:readJson(rel(manifest.schema_file))}}} :
        {messages:record.messages,config:baseline.request.config};
      const requestHash=sha(Buffer.from(stable(request)));
      if(config.surface==='lmstudio_sdk') assert.equal(requestHash,record.request_sha256);
      const attempt=crypto.randomUUID();
      if(output===undefined) {
        journal=fs.openSync(journalPath,'wx');
        output=fs.openSync(outputPath,'wx');
      }
      claimStarted=true;
      appendDurable(journal,{event:'started',attempt_id:attempt,id:record.id,configuration:opts.config,
        variant:opts.variant,phase:opts.phase,request_sha256:requestHash,manifest_sha256:manifestHash,
        preflight_sha256:preflightHash,timeout_ms:config.timeout_ms,at:new Date().toISOString()});
      const started=performance.now();let response=null,decision;
      try {
        response=config.surface==='local_http' ? await httpRequest(request,config.timeout_ms) :
          await require(rel('scripts/lmstudio_reasoning_benchmark.cjs')).predictWithTimeout(
            model,record.messages,baseline.request.config,config.timeout_ms);
        const after=await model.getModelInfo();
        if(after?.instanceReference!==info.instanceReference) decision={status:'control_failure',reason:'loaded_instance_changed'};
        else {
          const expected={identifier:config.identifier,path:config.artifact_path,bytes:config.artifact_bytes,
            promptTokens:counted.prompt_tokens+config.native_token_delta,
            predictionConfig:baseline.prediction_config,loadConfig:baseline.load_config};
          decision=config.surface==='local_http' ? classifyHttp(response,expected) : classifySdk(response,expected);
        }
      } catch(error) {
        if(error.code==='PREDICTION_TIMEOUT' && error.cancellationAcknowledged!==true) holdLock=true;
        decision={status:error.code==='PREDICTION_TIMEOUT'?'timeout':'service_failure',reason:String(error.message),
          cancellation_acknowledged:error.cancellationAcknowledged??null};
      }
      const row={id:record.id,configuration:opts.config,variant:opts.variant,phase:opts.phase,
        attempt_id:attempt,manifest_sha256:manifestHash,preflight_sha256:preflightHash,
        controller_sha256:shaFile(__filename),timeout_ms:config.timeout_ms,runtime_attestation:runtime,
        request,request_sha256:requestHash,rendered_sha256:counted.rendered_sha256,
        expected_prompt_tokens:counted.prompt_tokens+config.native_token_delta,reference_labels_read:false,
        model_identifier:config.identifier,model_path:config.artifact_path,
        raw_response:config.surface==='local_http' ? response?.rawBody??null : response?.content??null,
        non_reasoning_content:config.surface==='local_http' ? response?.body?.choices?.[0]?.message?.content??null :
          response?.nonReasoningContent??null,
        reasoning_content:config.surface==='local_http' ? null : response?.reasoningContent??null,
        http_status:config.surface==='local_http' ? response?.httpStatus??null : null,
        stats:config.surface==='local_http' ? response?.body?.usage??null : response?.stats??null,
        model_info:config.surface==='local_http' ? response?.body?.model??null : response?.modelInfo??null,
        load_config:config.surface==='local_http' ? null : response?.loadConfig??null,
        prediction_config:config.surface==='local_http' ? null : response?.predictionConfig??null,
        decision,elapsed_seconds:(performance.now()-started)/1000,finished_utc:new Date().toISOString()};
      appendDurable(output,row);
      appendDurable(journal,{event:'finished',attempt_id:attempt,id:record.id,status:decision.status,
        output_sha256:sha(Buffer.from(stable(row))),at:new Date().toISOString()});
      console.log(opts.config,opts.variant,opts.phase,record.id,decision.status);
      if(['control_failure','service_failure','timeout'].includes(decision.status))
        throw Error(`Stopped after ${record.id}: ${decision.reason}`);
    }
    completed=true;
  } catch(error) {terminalError=String(error.message);throw error;}
  finally {
    if(journal!==undefined) fs.closeSync(journal);
    if(output!==undefined) fs.closeSync(output);
    finishPreflightAttempt({output:outputPath,journal:journalPath,
      preflightTerminal:preflightTerminalPath},{id:preflightId,configuration:opts.config,
      variant:opts.variant,phase:opts.phase,started:preflightStarted,claimStarted,
      manifestHash,preflightHash,controllerHash:shaFile(__filename),error:terminalError,runtime});
    if(claimStarted) {
      const rows=fs.existsSync(outputPath)?readJsonl(outputPath):[];
      const events=fs.existsSync(journalPath)?readJsonl(journalPath):[];
      const terminal={configuration:opts.config,variant:opts.variant,phase:opts.phase,
        status:completed?'completed':'stopped',manifest_sha256:manifestHash,preflight_sha256:preflightHash,
        controller_sha256:shaFile(__filename),requested_records:records.length,
        claimed_attempts:events.filter(event=>event.event==='started').length,
        finished_attempts:events.filter(event=>event.event==='finished').length,saved_rows:rows.length,
        ok_rows:rows.filter(row=>row.decision.status==='ok').length,
        invalid_output_rows:rows.filter(row=>row.decision.status==='invalid_output').length,
        ambiguous_timeout:holdLock,timeout_ms:config.timeout_ms,runtime_attestation:runtime,
        output_sha256:fs.existsSync(outputPath)?shaFile(outputPath):null,
        journal_sha256:fs.existsSync(journalPath)?shaFile(journalPath):null,
        stopped_reason:terminalError,finished_utc:new Date().toISOString()};
      fs.writeFileSync(terminalPath,stable(terminal)+'\n',{flag:'wx'});
    }
    fs.closeSync(lock);
    if(!holdLock) fs.unlinkSync(lockPath);
  }
}
async function main() {
  const args=argsFrom(process.argv.slice(2));
  const manifest=readJson(manifestPath);
  const source=sourceCheck(manifest);
  if(args.mode==='validate') {console.log(stable({validated:true,configs:Object.keys(source).length,
    manifest_sha256:shaFile(manifestPath),preflight_sha256:shaFile(preflightPath)}));return;}
  if(args.mode==='run') return run(manifest,source,args);
  throw Error('Use --mode validate or --mode run');
}
if(require.main===module) main().catch(error=>{console.error(error.message);process.exitCode=1;});
module.exports={argsFrom,requireLoadedModel,clearEmptyUnclaimed,finishPreflightAttempt,validPrediction,classifySdk,classifyHttp,sourceCheck,orderCheck,validateSmoke,reviewCheck,httpRequest};
