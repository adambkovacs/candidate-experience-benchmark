'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {execFileSync,spawn}=require('node:child_process');
const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
const small=require('../scripts/small_local_repeat_admission.cjs');
const plan=legacy.makePlan();
const pinnedSdk=path.join(os.homedir(),
  'Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/lmstudio-sdk/node_modules/@lmstudio/sdk/dist/index.cjs');

function fixture(id,stage,predict) {
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'legacy-qwen-'));
  const paths={folder,claim:path.join(folder,`${stage}.claim.json`),journal:path.join(folder,`${stage}.journal.jsonl`),
    raw:path.join(folder,`${stage}.raw.jsonl`),records:path.join(folder,`${stage}.records.jsonl`),
    completion:path.join(folder,`${stage}.completion.json`)};
  const receipt=path.join(folder,'receipt.json');
  fs.writeFileSync(receipt,'{}\n');
  const config=plan.configurations[id];
  const dependencies={paths:()=>paths,predecessor:()=>null,admit:()=>null,
    runtime:async()=>({model:{getModelInfo:async()=>({instanceReference:'fixture'})},
      instance:'fixture',attestation:{test_only:true}}),predict,
    routeAudit:async()=>({checked_ms:Date.now(),source:'fixture'}),
    httpThinking:()=>({source:'fixture'}),
    verifyRequest:async(_runtime,_config,row)=>({request_sha256:small.hash(JSON.stringify(row.request)),
      rendered_sha256:row.rendered_sha256,prompt_tokens:row.prompt_tokens})};
  return {folder,paths,receipt,config,dependencies};
}

test('six distinct configurations have 54 fresh development phases and frozen 60-position requests',()=>{
  assert.equal(legacy.IDS.length,6);
  assert.equal(new Set(legacy.IDS).size,6);
  assert.equal(plan.reference_labels_used_for_requests,false);
  assert.equal(plan.historical_predictions_used_for_requests,false);
  let phases=0;
  for(const id of legacy.IDS) {
    const config=plan.configurations[id];
    assert.equal(config.schedule.length,3);
    for(const entry of config.schedule) {
      assert.deepEqual([...entry.conditions].sort(),['P0','P1','P2']);
      phases+=entry.conditions.length;
    }
    for(const condition of ['P0','P1','P2']) {
      assert.equal(config.conditions[condition].requests.length,60);
      const development=legacy.stageRows(plan,id,condition,'development');
      assert.deepEqual(development.map(x=>x.id),Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
      assert.deepEqual(legacy.stageRows(plan,id,condition,'smoke').map(x=>x.id),['DEV-001','DEV-002','DEV-003']);
      assert(development.every(x=>x.prompt_tokens+config.output_reserve<=config.context));
      for(const row of development) {
        assert.deepEqual(row.request.messages.map(x=>x.role),['system','user']);
        assert.deepEqual(Object.keys(JSON.parse(row.request.messages[1].content)),['feedback']);
      }
    }
  }
  assert.equal(phases,54);
  assert.equal(plan.configurations[legacy.IDS[0]].surface,'local_http');
  assert(legacy.IDS.slice(1).every(id=>plan.configurations[id].surface==='lmstudio_sdk'));
});

test('HTTP schema/512-token request and SDK template/4096-token request remain distinct',()=>{
  const http=legacy.stageRows(plan,legacy.IDS[0],'P1','smoke')[0].request;
  const sdk=legacy.stageRows(plan,legacy.IDS[1],'P1','smoke')[0].request;
  assert.equal(http.max_tokens,512);
  assert.equal(http.temperature,0);
  assert.equal(http.response_format.type,'json_schema');
  assert.equal(http.response_format.json_schema.strict,true);
  assert.equal(sdk.config.maxTokens,4096);
  assert.equal(sdk.config.temperature,0.6);
  assert.equal(sdk.config.promptTemplate.type,'jinja');
  assert.equal(plan.configurations[legacy.IDS[2]].controls.request_config.promptTemplate.jinjaPromptTemplate.template.includes('enable_thinking = false'),true);
  assert.equal(plan.configurations[legacy.IDS[1]].controls.request_config.promptTemplate.jinjaPromptTemplate.template.includes('enable_thinking = true'),true);
});

test('Qwen 3.5 P2 reconstructs the missing historical suffix but never imports an outcome',()=>{
  const id=legacy.IDS[5],config=plan.configurations[id];
  assert.equal(small.rows(small.rel(config.conditions.P2.history.file)).length,18);
  const all=legacy.stageRows(plan,id,'P2','development');
  assert.equal(all.length,60);
  assert.equal(all[18].id,'DEV-019');
  assert.equal(all[59].id,'DEV-060');
  assert(!('prediction' in all[18]));
});

test('source and request drift are detected before a phase claim',async t=>{
  const id=legacy.IDS[0],x=fixture(id,'smoke',async()=>null);
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  const tampered=structuredClone(plan);
  tampered.configurations[id].conditions.P1.requests[0].sha256='0'.repeat(64);
  assert.throws(()=>legacy.stageRows(tampered,id,'P1','smoke'),/Request source drift/);
  x.dependencies.admit=()=>{throw Error('route changed');};
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),/route changed/);
  assert.equal(fs.existsSync(x.paths.claim),false);
  x.dependencies.admit=()=>null;
  x.dependencies.runtime=async()=>{throw Error('runtime changed');};
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),/runtime changed/);
  assert.equal(fs.existsSync(x.paths.claim),false);
});

test('HTTP smoke records raw responses before decisions and refuses replay',async t=>{
  const id=legacy.IDS[0],x=fixture(id,'smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  let index=0;
  x.dependencies.predict=async(_model,request)=>{
    const row=legacy.stageRows(plan,id,'P0','smoke')[index++];
    assert.deepEqual(request,row.request);
    return {httpStatus:200,rawBody:'{"ok":true}',body:{model:x.config.model_identifier,
      usage:{prompt_tokens:row.prompt_tokens},choices:[{message:{content:JSON.stringify({
        sentiment:'positive',follow_up_needed:'no',serious_concern_reported:'no',testimonial_potential:'yes'})},
        finish_reason:'stop'}]}};
  };
  const terminal=await legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies);
  assert.equal(terminal.status,'completed');
  assert.equal(terminal.attempted,3);
  assert.deepEqual(small.rows(x.paths.journal).map(x=>x.event),
    ['started','finished','started','finished','started','finished']);
  assert.equal(small.rows(x.paths.raw).length,3);
  assert.deepEqual(small.rows(x.paths.records).map(x=>x.decision.status),['ok','ok','ok']);
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),/already claimed/);
});

test('SDK control failure stops, while invalid smoke remains saved and blocks development',async t=>{
  const id=legacy.IDS[1],x=fixture(id,'smoke',async()=>({content:'{}',nonReasoningContent:'{}',
    modelInfo:{identifier:'wrong'},stats:{promptTokensCount:1}}));
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),/control_failure/);
  assert.equal(small.read(x.paths.completion).attempted,1);
  assert.equal(small.rows(x.paths.raw).length,1);
  assert.equal(small.rows(x.paths.records)[0].decision.status,'control_failure');
  const y=fixture(legacy.IDS[0],'smoke',async(_model,request)=>({httpStatus:200,
    body:{model:request.model,usage:{prompt_tokens:legacy.stageRows(plan,legacy.IDS[0],'P0','smoke')[0].prompt_tokens},
      choices:[{message:{content:'not json'},finish_reason:'stop'}]}}));
  t.after(()=>fs.rmSync(y.folder,{recursive:true,force:true}));
  await assert.rejects(legacy.runStage(plan,'test',legacy.IDS[0],'fresh1','P0','smoke',y.receipt,y.dependencies),
    /Smoke has invalid output|control_failure/);
  assert.equal(small.read(y.paths.completion).status,'stopped');
  assert.equal(small.rows(y.paths.records)[0].decision.status,'invalid_output');
});

test('SDK smoke uses the frozen request and observed controls',async t=>{
  const id=legacy.IDS[1],x=fixture(id,'smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  let index=0;
  x.dependencies.predict=async(_model,request)=>{
    const row=legacy.stageRows(plan,id,'P0','smoke')[index++];
    assert.deepEqual(request,row.request);
    return {content:'{}',nonReasoningContent:JSON.stringify({sentiment:'neutral',follow_up_needed:'no',
      serious_concern_reported:'no',testimonial_potential:'no'}),reasoningContent:'',
      modelInfo:{identifier:x.config.model_identifier,path:x.config.artifact_path,
        sizeBytes:x.config.artifact_bytes,contextLength:8192,quantization:{name:'Q4_K_M'}},
      stats:{promptTokensCount:row.prompt_tokens,stopReason:'eosFound'},
      loadConfig:x.config.controls.load_config,predictionConfig:x.config.controls.prediction_config};
  };
  const terminal=await legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies);
  assert.equal(terminal.status,'completed');
  assert.deepEqual(small.rows(x.paths.records).map(x=>x.decision.status),['ok','ok','ok']);
});

test('unknown request outcome keeps a started journal event and cannot be replayed',async t=>{
  const x=fixture(legacy.IDS[0],'smoke',async()=>{
    throw Object.assign(Error('timeout'),{code:'PREDICTION_TIMEOUT',cancellationAcknowledged:false,
      partialResult:{rawBody:'partial'}});
  });
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  await assert.rejects(legacy.runStage(plan,'test',legacy.IDS[0],'fresh1','P0','smoke',x.receipt,x.dependencies),/timeout/);
  assert.deepEqual(small.rows(x.paths.journal).map(x=>x.event),['started','stopped_unknown']);
  assert.equal(small.rows(x.paths.raw)[0].partialResult.rawBody,'partial');
  assert.equal(small.read(x.paths.completion).status,'stopped');
  await assert.rejects(legacy.runStage(plan,'test',legacy.IDS[0],'fresh1','P0','smoke',x.receipt,x.dependencies),/already claimed/);
});

test('a failure after raw response capture remains an unknown stopped attempt',async t=>{
  const id=legacy.IDS[0],x=fixture(id,'smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  let probes=0;
  x.dependencies.runtime=async()=>({model:{getModelInfo:async()=>{
    if(++probes===2) throw Error('lost instance after response');
    return {instanceReference:'fixture'};
  }},instance:'fixture',attestation:{test_only:true}});
  x.dependencies.predict=async()=>({httpStatus:200,body:{}});
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),
    /lost instance after response/);
  assert.equal(small.rows(x.paths.raw).length,1);
  assert.deepEqual(small.rows(x.paths.journal).map(x=>x.event),['started','stopped_unknown']);
  assert.equal(small.read(x.paths.completion).saved,0);
});

test('missing smoke and predecessor fixtures block admission regardless of saved workspace results',t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'legacy-qwen-missing-predecessor-'));
  t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const paths=(_id,pass,condition,stage)=>({folder,completion:path.join(folder,`${pass}-${condition}-${stage}.completion.json`)});
  assert.throws(()=>legacy.checkPredecessor(plan,legacy.IDS[0],'fresh1','P0','development',paths),/Smoke not complete/);
  assert.throws(()=>legacy.checkPredecessor(plan,legacy.IDS[0],'fresh1','P1','smoke',paths),/Prior phase incomplete/);
});

test('current route receipt is required and becomes stale after five minutes',()=>{
  const id=legacy.IDS[0],config=plan.configurations[id],audit=small.read(small.rel(
    'results/route-audits/legacy-six-local-20260929/catalog-audit.json'));
  const receipt={kind:'root-reviewed-legacy-qwen-stage-v1',approved:true,plan_sha256:'plan',
    controller_sha256:small.hashFile(path.join(small.ROOT,'scripts/legacy_qwen_repeat_admission.cjs')),
    phase:`${id}/fresh1/P0`,stage:'smoke',model_identifier:config.model_identifier,
    artifact_sha256:config.artifact_sha256,cache_policy:{enabled:true,size_limit_mib:8192},
    reference_labels_read:false,exact_openrouter_route_absent:true,
    route_catalog_file:'results/route-audits/legacy-six-local-20260929/catalog-audit.json',
    route_catalog_sha256:small.hashFile(small.rel('results/route-audits/legacy-six-local-20260929/catalog-audit.json')),
    route_checked_utc:audit.retrieved_utc,gpu_available:true,capacity_reviewed:true,
    runtime_token_preflight:{phase:`${id}/fresh1/P0`,model_identifier:config.model_identifier,
      artifact_sha256:config.artifact_sha256,context:8192,output_reserve:512,request_count:60,
      requests_sha256:small.hash(JSON.stringify(config.conditions.P0.requests)),checked_utc:audit.retrieved_utc}};
  legacy.checkReceipt(receipt,'plan',receipt.phase,'smoke',config,null,Date.parse(audit.retrieved_utc)+1000);
  assert.throws(()=>legacy.checkReceipt(receipt,'plan',receipt.phase,'smoke',config,null,
    Date.parse(audit.retrieved_utc)+5*60*1000+1),/Route attestation must be fresh/);
  assert.throws(()=>legacy.checkReceipt({...receipt,gpu_available:false},'plan',receipt.phase,'smoke',config,null,
    Date.parse(audit.retrieved_utc)+1000));
  assert.throws(()=>legacy.checkReceipt({...receipt,runtime_token_preflight:{...receipt.runtime_token_preflight,
    requests_sha256:'0'.repeat(64)}},'plan',receipt.phase,'smoke',config,null,
    Date.parse(audit.retrieved_utc)+1000));
});

test('live route audit rejects a newly listed exact family and malformed catalogs',async()=>{
  const reply=data=>async()=>({status:200,json:async()=>({data:[...Array.from({length:100},
    (_,i)=>({id:`unrelated/model-${i}`})),...data]})});
  const clear=await legacy.checkLiveRoute(reply([{id:'qwen/qwen3-8b'}]),100);
  assert.equal(clear.checked_ms,100);
  await assert.rejects(legacy.checkLiveRoute(reply([{id:'qwen/qwen3-0.6b'}]),100),
    /Exact Qwen hosted route needs review/);
  await assert.rejects(legacy.checkLiveRoute(reply([{name:'Qwen 3.5 4B'}]),100),
    /Exact Qwen hosted route needs review/);
  await assert.rejects(legacy.checkLiveRoute(async()=>({status:200,json:async()=>({wrong:[]})}),100),
    /catalog malformed/);
});

test('loaded model rendering, token count, artifact, and context bind the request before dispatch',async()=>{
  const config=plan.configurations[legacy.IDS[0]],request={messages:[{role:'system',content:'a'},
    {role:'user',content:'b'}]},rendered='runtime rendered prompt';
  const row={request,rendered_sha256:small.hash(Buffer.from(rendered)),prompt_tokens:4};
  const info={instanceReference:'current',identifier:config.model_identifier,path:config.artifact_path,
    sizeBytes:config.artifact_bytes,contextLength:8192,quantization:{name:'Q4_K_M'}};
  const runtime={instance:'current',attestation:{artifact_sha256:config.artifact_sha256},
    model:{getModelInfo:async()=>info,applyPromptTemplate:async()=>rendered,
      tokenize:async()=>[1,2,3,4]}};
  const checked=await legacy.verifyRequestRuntime(runtime,config,row);
  assert.equal(checked.prompt_tokens,4);
  await assert.rejects(legacy.verifyRequestRuntime({...runtime,model:{...runtime.model,
    applyPromptTemplate:async()=>rendered+' drift'}},config,row),/rendered prompt differs/);
  await assert.rejects(legacy.verifyRequestRuntime({...runtime,model:{...runtime.model,
    tokenize:async()=>[1,2,3]}},config,row),/token count differs/);
  await assert.rejects(legacy.verifyRequestRuntime({...runtime,attestation:{artifact_sha256:'wrong'}},config,row),
    /artifact hash unverified/);
  await assert.rejects(legacy.verifyRequestRuntime({...runtime,model:{getModelInfo:async()=>
    ({...info,contextLength:4096}),applyPromptTemplate:async()=>rendered,tokenize:async()=>[1,2,3,4]}},
  config,row),/artifact or context differs/);
});

test('SDK preflight uses the exact converted respond override and restores the handle stack',async()=>{
  const {LMStudioClient}=require(pinnedSdk);
  const client=new LMStudioClient({disableConnection:true});
  const model=client.llm.createDynamicHandle('fixture');
  const original=model.internalKVConfigStack;
  const id=legacy.IDS[1],config=plan.configurations[id];
  const frozen=legacy.stageRows(plan,id,'P0','smoke')[0];
  let sentStack,renderStack;
  model.internalPredict=(_history,stack)=>{sentStack=stack;};
  model.respond(frozen.request.messages,frozen.request.config);
  assert.equal(sentStack.layers.at(-1).layerName,'apiOverride');
  const rendered='same SDK prompt';
  model.port={callRpc:async(method,params)=>{
    assert.equal(method,'applyPromptTemplate');
    renderStack=params.predictionConfigStack;
    return {formatted:rendered};
  }};
  model.getModelInfo=async()=>({instanceReference:'fixture',identifier:config.model_identifier,
    path:config.artifact_path,sizeBytes:config.artifact_bytes,contextLength:config.context,
    quantization:{name:'Q4_K_M'}});
  model.tokenize=async()=>Array.from({length:frozen.prompt_tokens},(_,i)=>i);
  const row={...frozen,rendered_sha256:small.hash(Buffer.from(rendered))};
  const runtime={model,instance:'fixture',attestation:{artifact_sha256:config.artifact_sha256}};
  await legacy.verifyRequestRuntime(runtime,config,row);
  assert.deepEqual(renderStack,sentStack);
  assert.strictEqual(model.internalKVConfigStack,original);
  model.port.callRpc=async()=>{throw Error('render failed');};
  await assert.rejects(legacy.verifyRequestRuntime(runtime,config,row),/render failed/);
  assert.strictEqual(model.internalKVConfigStack,original);
});

test('failed output initialization seals a proven no-send claim and never replays it',async t=>{
  const id=legacy.IDS[0],x=fixture(id,'smoke',async()=>{throw Error('must not dispatch');});
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  let opens=0;
  x.dependencies.openOutput=(file,flag)=>{
    if(++opens===2) throw Object.assign(Error('disk full'),{code:'ENOSPC'});
    return fs.openSync(file,flag);
  };
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),
    /disk full/);
  assert.equal(fs.existsSync(x.paths.claim),true);
  assert.equal(fs.existsSync(x.paths.journal),true);
  assert.equal(fs.existsSync(x.paths.raw),false);
  assert.equal(small.read(x.paths.completion).reason,'initialization_failed_no_send');
  assert.equal(small.read(x.paths.completion).attempted,0);
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),
    /already claimed/);
});

test('manual no-send recovery preserves orphaned artifacts and rejects send evidence',async t=>{
  const id=legacy.IDS[0],x=fixture(id,'smoke',async()=>null);
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  const phase=`${id}/fresh1/P0`;
  fs.writeFileSync(x.paths.claim,JSON.stringify({phase,stage:'smoke'}));
  fs.writeFileSync(x.paths.journal,'');
  assert.equal(legacy.recoverUnsentStage(x.paths,phase,'smoke').attempted,0);
  assert.equal(fs.existsSync(x.paths.claim),true);
  assert.throws(()=>legacy.recoverUnsentStage(x.paths,phase,'smoke'),/already has a completion/);
  fs.unlinkSync(x.paths.completion);
  fs.writeFileSync(x.paths.journal,'{"event":"started"}\n');
  assert.throws(()=>legacy.recoverUnsentStage(x.paths,phase,'smoke'),/Journal evidence/);
  fs.writeFileSync(x.paths.journal,'');
  fs.writeFileSync(x.paths.raw,'{"partial":"response"}\n');
  assert.throws(()=>legacy.recoverUnsentStage(x.paths,phase,'smoke'),/Output evidence/);
});

test('HTTP nonthinking control must be observed in the current instance load window',()=>{
  const evidence={instance_reference:'current',cache_line:2,instance_line:5};
  const logs=['load','cache','init: chat template, thinking = 0','other',
    'instanceReference current'].join('\n');
  assert.equal(legacy.verifyHttpThinking(logs,evidence,'current').line,3);
  assert.throws(()=>legacy.verifyHttpThinking(logs.replace('thinking = 0','thinking = 1'),
    evidence,'current'),/differs/);
  assert.throws(()=>legacy.verifyHttpThinking(logs.replace('init: chat template, thinking = 0',''),
    evidence,'current'),/unavailable or ambiguous/);
  assert.throws(()=>legacy.verifyHttpThinking(logs,evidence,'other'),/another instance/);
});

test('failed live preflight or live route check leaves no phase claim',async t=>{
  const id=legacy.IDS[0],x=fixture(id,'smoke',async()=>{throw Error('must not dispatch');});
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  x.dependencies.verifyRequest=async()=>{throw Error('render mismatch');};
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),
    /render mismatch/);
  assert.equal(fs.existsSync(x.paths.claim),false);
  x.dependencies.verifyRequest=async(_runtime,_config,row)=>({prompt_tokens:row.prompt_tokens});
  x.dependencies.routeAudit=async()=>{throw Error('route unavailable');};
  await assert.rejects(legacy.runStage(plan,'test',id,'fresh1','P0','smoke',x.receipt,x.dependencies),
    /route unavailable/);
  assert.equal(fs.existsSync(x.paths.claim),false);
});

test('single GPU lease excludes another process',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'legacy-qwen-lock-'));
  t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const lock=path.join(folder,'host.lock');
  const owner=spawn('python3',['-c','import fcntl,os,sys,time\nfd=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600)\nfcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\nprint("ready",flush=True)\ntime.sleep(3)',lock],{stdio:['ignore','pipe','pipe']});
  t.after(()=>owner.kill());
  await new Promise((resolve,reject)=>{owner.stdout.once('data',data=>data.toString().includes('ready')?resolve():reject(Error('No owner')));owner.once('error',reject);});
  assert.throws(()=>execFileSync('python3',['-c',legacy.lockCode,lock,process.execPath,'-e','process.exit(0)'],{stdio:'pipe'}),
    error=>error.status===73);
});
