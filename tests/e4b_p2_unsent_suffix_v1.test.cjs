'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const small=require('../scripts/small_local_repeat_admission.cjs');
const suffix=require('../scripts/e4b_p2_unsent_suffix_v1.cjs');

const {plan,sha256}=small.verifyPlan();
const ids=Array.from({length:8},(_,i)=>`DEV-${String(53+i).padStart(3,'0')}`);

test('both stopped attempts remain unknown and only eight requests were never sent',()=>{
  const history=suffix.verifyHistory(plan,sha256);
  assert.equal(history.saved,50);
  assert.deepEqual(history.original_unknown_ids,['DEV-039','DEV-052']);
  assert.deepEqual(history.never_sent_ids,ids);
  assert.equal(history.clean_repeat_eligible,false);
  for(const group of [history.original,history.continuation,history.smoke])
    for(const item of Object.values(group))suffix.verifyBinding(item);
});

test('manifest binds frozen E4B P2 request hashes, settings and no-replay boundary',()=>{
  const manifest=suffix.expectedManifest(),config=plan.configurations[suffix.ID];
  assert.equal(manifest.status,'offline_prepared_unapproved');
  assert.equal(manifest.approval,null);
  assert.equal(manifest.clean_repeat_eligible,false);
  assert.deepEqual(manifest.suffix.ids,ids);
  assert.deepEqual(manifest.suffix.requests,config.conditions.P2.requests.slice(52));
  assert.deepEqual(suffix.selectedRows(plan).map(x=>x.id),ids);
  assert.deepEqual(manifest.policy.never_replay_ids,suffix.IDS.slice(0,52));
  assert.equal(new Set([...manifest.policy.never_replay_ids,...ids]).size,60);
  assert.equal(manifest.runtime.artifact_sha256,config.artifact_sha256);
  assert.equal(manifest.runtime.timeout_ms,config.timeout_ms);
  assert.deepEqual(manifest.runtime.cache_policy,plan.policy.cache_policy);
});

test('exact hosted family audit is fresh and rejects E4B even in a catalog name',async()=>{
  const base=Array.from({length:100},(_,i)=>({id:`other/model-${i}`,name:`Other ${i}`}));
  const fetcher=data=>async()=>({status:200,text:async()=>JSON.stringify({data})});
  const now=Date.parse('2026-10-06T12:00:00Z');
  const good=await suffix.fetchRouteEvidence(fetcher(base),now);
  suffix.verifyRoute(good.audit,now+1000);
  assert.throws(()=>suffix.verifyRoute(good.audit,now+5*60*1000),/fresh/);
  const hosted=[...base,{id:'vendor/unrelated',name:'Gemma-4-E4B Instruct'}];
  await assert.rejects(suffix.fetchRouteEvidence(fetcher(hosted),now),/hosted route needs review/);
});

test('read-only SDK render and token drift fail against frozen P2 controls',async()=>{
  const config=plan.configurations[suffix.ID],row=suffix.selectedRows(plan)[0];
  const model={internalKVConfigStack:{layers:[]},
    predictionConfigInputToKVConfig:value=>value,
    applyPromptTemplate:async()=>'{rendered}',
    tokenize:async()=>Array(row.prompt_tokens).fill(1),
    getModelInfo:async()=>({instanceReference:'fixture-instance',
      identifier:config.model_identifier,path:config.artifact_path,
      sizeBytes:config.artifact_bytes,contextLength:8192,quantization:{name:'Q4_K_M'}})};
  const runtime={model,instance:'fixture-instance',
    attestation:{artifact_sha256:config.artifact_sha256}};
  const measured=await suffix.verifyRequestRuntime(runtime,config,row,plan);
  assert.equal(measured.prompt_tokens,row.prompt_tokens);
  assert.equal(model.internalKVConfigStack.layers.length,0);
  model.tokenize=async()=>Array(row.prompt_tokens+1).fill(1);
  await assert.rejects(suffix.verifyRequestRuntime(runtime,config,row,plan),
    /Runtime prompt token count differs/);
});

test('injected timeout captures only DEV-053 and a second run cannot replay it',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'e4b-p2-unsent-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const p=suffix.paths(dir),receipt=path.join(dir,'review.json');
  fs.writeFileSync(receipt,'{}\n');
  const manifest=suffix.expectedManifest();
  const host={boot:'fixture',sleep_wakes:0,lid_open:true,power_source:'battery',
    operational_policy:{schema:'fixture'}};
  const runtime={instance:'fixture-instance',
    model:{getModelInfo:async()=>({instanceReference:'fixture-instance',
      identifier:plan.configurations[suffix.ID].model_identifier,
      path:plan.configurations[suffix.ID].artifact_path})},
    attestation:{artifact_sha256:plan.configurations[suffix.ID].artifact_sha256}};
  const audit={source:'https://openrouter.ai/api/v1/models',retrieved_utc:new Date().toISOString(),
    http_status:200,model_count:100,matches:[]};
  const reviewed=ids.map(id=>({id,prompt_tokens:1}));
  let calls=0;
  const error=Object.assign(new Error('fixture timeout'),{code:'PREDICTION_TIMEOUT',
    cancellationAcknowledged:true,partialResult:{reasoningContent:'partial'}});
  const deps={prepare:()=>({manifest,plan,p,host,review:{instance_reference:runtime.instance},
      reviewedMeasurements:reviewed}),
    runtime:async()=>runtime,routeEvidence:async()=>({audit}),
    verifySuffix:async()=>reviewed,
    currentHost:()=>host,verifyAfterStage:()=>({host_unchanged:true}),
    predict:async()=>{calls++;throw error;}};
  await assert.rejects(suffix.runSuffix('test-sha',receipt,deps),/fixture timeout/);
  assert.equal(calls,1);
  assert.deepEqual(small.rows(p.journal).map(x=>[x.event,x.id]),
    [['started','DEV-053'],['stopped_unknown','DEV-053']]);
  assert.equal(small.rows(p.raw)[0].partialResult.reasoningContent,'partial');
  assert.equal(small.rows(p.records).length,0);
  const completion=small.read(p.completion);
  assert.equal(completion.status,'stopped');
  assert.deepEqual(completion.original_unknown_ids,['DEV-039','DEV-052']);
  assert.deepEqual(completion.unknown_ids,['DEV-053']);
  assert.equal(completion.host_check.host_unchanged,true);
  await assert.rejects(suffix.runSuffix('test-sha',receipt,deps),/already claimed/);
  assert.equal(calls,1);
});

test('changed suffix rendering blocks before claim and before predictor',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'e4b-p2-drift-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const p=suffix.paths(dir),receipt=path.join(dir,'review.json');fs.writeFileSync(receipt,'{}\n');
  const host={boot:'fixture',sleep_wakes:0,lid_open:true,operational_policy:{schema:'fixture'}};
  const config=plan.configurations[suffix.ID];
  const runtime={instance:'fixture-instance',attestation:{artifact_sha256:config.artifact_sha256}};
  const baseline=ids.map(id=>({id,rendered_sha256:'a'.repeat(64),prompt_tokens:2700}));
  const changed=structuredClone(baseline);changed[0].prompt_tokens++;
  let calls=0;
  const deps={prepare:()=>({manifest:suffix.expectedManifest(),plan,p,host,
      review:{instance_reference:runtime.instance},reviewedMeasurements:baseline}),
    runtime:async()=>runtime,verifySuffix:async()=>changed,
    predict:async()=>{calls++;throw Error('Predictor must not run');}};
  await assert.rejects(suffix.runSuffix('test-sha',receipt,deps),/rendering or token count changed/);
  assert.equal(calls,0);assert.equal(fs.existsSync(p.claim),false);
});

test('eight fixture completions close with exact ordered requests and durable hashes',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'e4b-p2-complete-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const p=suffix.paths(dir),receipt=path.join(dir,'review.json');fs.writeFileSync(receipt,'{}\n');
  const config=plan.configurations[suffix.ID],selection=suffix.selectedRows(plan);
  const host={boot:'fixture',sleep_wakes:0,lid_open:true,operational_policy:{schema:'fixture'}};
  const runtime={instance:'fixture-instance',
    model:{getModelInfo:async()=>({instanceReference:'fixture-instance',
      identifier:config.model_identifier,path:config.artifact_path})},
    attestation:{artifact_sha256:config.artifact_sha256}};
  const reviewed=ids.map(id=>({id,prompt_tokens:1}));
  const audit={source:'https://openrouter.ai/api/v1/models',retrieved_utc:new Date().toISOString(),
    http_status:200,model_count:100,matches:[]};
  let calls=0;
  const prediction=JSON.stringify({sentiment:'positive',follow_up_needed:'no',
    serious_concern_reported:'no',testimonial_potential:'yes'});
  const deps={prepare:()=>({manifest:suffix.expectedManifest(),plan,p,host,
      review:{instance_reference:runtime.instance},reviewedMeasurements:reviewed}),
    runtime:async()=>runtime,verifySuffix:async()=>reviewed,
    routeEvidence:async()=>({audit}),currentHost:()=>host,
    verifyAfterStage:()=>({host_unchanged:true}),
    predict:async()=>{const row=selection[calls++];return {content:prediction,
      nonReasoningContent:prediction,reasoningContent:'',
      modelInfo:{identifier:config.model_identifier,path:config.artifact_path,
        sizeBytes:config.artifact_bytes,contextLength:8192,quantization:{name:'Q4_K_M'}},
      loadConfig:row.load_config,predictionConfig:row.prediction_config,
      stats:{promptTokensCount:row.prompt_tokens,stopReason:'eosFound'}};}};
  const done=await suffix.runSuffix('test-sha',receipt,deps);
  assert.equal(calls,8);assert.equal(done.status,'completed');
  assert.equal(done.attempted,8);assert.equal(done.saved,8);assert.equal(done.invalid,0);
  assert.deepEqual(small.rows(p.raw).map(x=>x.id),ids);
  assert.deepEqual(small.rows(p.records).map(x=>x.decision.status),Array(8).fill('ok'));
  assert.deepEqual(done.unknown_ids,[]);
  for(const key of ['raw','records','journal'])assert.equal(done[`${key}_sha256`],small.hashFile(p[key]));
});
