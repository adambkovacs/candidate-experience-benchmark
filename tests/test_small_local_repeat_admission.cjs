const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync,spawn} = require('node:child_process');
const admission = require('../scripts/small_local_repeat_admission.cjs');

const plan = admission.makePlan();
const [e2bOff, e2bOn, e4bOff, e4bOn, qwen] = admission.NAMES;
const phase = (id, pass, condition) => `${id}/${pass}/${condition}`;

function fixture(id, pass, condition, stage, predict) {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'small-local-repeat-'));
  const paths = () => ({folder, claim:path.join(folder,`${stage}.claim.json`),
    journal:path.join(folder,`${stage}.journal.jsonl`),raw:path.join(folder,`${stage}.raw.jsonl`),
    records:path.join(folder,`${stage}.records.jsonl`),completion:path.join(folder,`${stage}.completion.json`)});
  const receiptFile = path.join(folder,'review.json');
  fs.writeFileSync(receiptFile, JSON.stringify({kind:'test-only'}));
  const config = plan.configurations[id];
  const historic = admission.rows(admission.rel(config.conditions[condition].source.file));
  let i = 0;
  const validPredict = async () => {
    const saved = historic[i++];
    return {content:saved.raw_response,nonReasoningContent:saved.non_reasoning_content,
      reasoningContent:saved.reasoning_content,stats:saved.stats,modelInfo:saved.model_info,
      loadConfig:saved.load_config,predictionConfig:saved.prediction_config};
  };
  const dependencies = {paths,predecessor:()=>null,admit:()=>null,
    runtime:async () => ({model:{getModelInfo:async () => ({instanceReference:'test-instance'})},
      instance:'test-instance',attestation:{test_only:true}}),predict:predict || validPredict};
  return {folder,paths:paths(),receiptFile,dependencies};
}

test('five exact dispositions and balanced condition schedules', () => {
  assert.deepEqual(admission.NAMES,[e2bOff,e2bOn,e4bOff,e4bOn,qwen]);
  for (const id of admission.NAMES) {
    const config = plan.configurations[id];
    assert.equal(config.schedule.length,3);
    for (const item of config.schedule) assert.deepEqual([...item.conditions].sort(),['P0','P1','P2']);
    for (const condition of ['P0','P1','P2']) {
      assert.equal(config.conditions[condition].requests.length,60);
      assert.deepEqual(admission.stageRows(plan,id,condition,'smoke').map(x=>x.id),['DEV-001','DEV-002','DEV-003']);
      const first=admission.stageRows(plan,id,condition,'smoke')[0];
      assert.deepEqual(Object.keys(JSON.parse(first.request.messages[1].content)),['feedback']);
      assert.deepEqual(first.request.messages.map(x=>x.role),['system','user']);
      assert.deepEqual(admission.stageRows(plan,id,condition,'development').map(x=>x.id),
        Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
    }
  }
  assert.match(plan.configurations[e4bOff].disposition,/fresh_matched_three/);
  assert.match(plan.configurations[e4bOn].disposition,/fresh_matched_three/);
  assert.equal(plan.reference_labels_used_for_requests,false);
  assert.equal(plan.historical_predictions_used_for_requests,false);
});

test('three-record smoke writes intent and raw evidence before parsed records; replay is refused',async t => {
  const x=fixture(e2bOff,'fresh2','P2','smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  const terminal=await admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies);
  assert.equal(terminal.status,'completed');
  assert.equal(terminal.attempted,3);
  assert.equal(terminal.saved,3);
  assert.equal(admission.rows(x.paths.raw).length,3);
  assert.deepEqual(admission.rows(x.paths.records).map(x=>x.decision.status),['ok','ok','ok']);
  assert.deepEqual(admission.rows(x.paths.journal).map(x=>x.event),
    ['started','finished','started','finished','started','finished']);
  await assert.rejects(admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies),/already claimed/);
});

test('unknown prediction failure retains started intent and partial response, then stops without retry',async t => {
  const error=Object.assign(new Error('timeout'),{code:'PREDICTION_TIMEOUT',
    cancellationAcknowledged:false,partialResult:{content:'partial output'}});
  const x=fixture(e2bOff,'fresh2','P2','smoke',async()=>{throw error;});
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  await assert.rejects(admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies),/timeout/);
  assert.equal(admission.read(x.paths.completion).status,'stopped');
  assert.equal(admission.read(x.paths.completion).attempted,1);
  assert.equal(admission.rows(x.paths.records).length,0);
  assert.equal(admission.rows(x.paths.raw)[0].partialResult.content,'partial output');
  assert.deepEqual(admission.rows(x.paths.journal).map(x=>x.event),['started','stopped_unknown']);
});

test('invalid smoke output remains in evidence and refuses development admission',async t => {
  const x=fixture(e2bOff,'fresh2','P2','smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  const config=plan.configurations[e2bOff];
  const saved=admission.rows(admission.rel(config.conditions.P2.source.file));
  let index=0;
  x.dependencies.predict=async()=>{
    const row=saved[index++];
    return {content:'not JSON',nonReasoningContent:'not JSON',reasoningContent:null,
      stats:row.stats,modelInfo:row.model_info,loadConfig:row.load_config,
      predictionConfig:row.prediction_config};
  };
  await assert.rejects(admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies),/Smoke has invalid output/);
  const terminal=admission.read(x.paths.completion);
  assert.equal(terminal.status,'stopped');
  assert.equal(terminal.attempted,3);
  assert.equal(terminal.invalid,3);
  assert.deepEqual(admission.rows(x.paths.records).map(x=>x.decision.status),
    ['invalid_output','invalid_output','invalid_output']);
  assert.equal(admission.rows(x.paths.raw).length,3);
});

test('admission or runtime drift fails before a phase claim',async t => {
  const x=fixture(e2bOff,'fresh2','P2','smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  x.dependencies.admit=()=>{throw Error('source or cache control drift');};
  await assert.rejects(admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies),/control drift/);
  assert.equal(fs.existsSync(x.paths.claim),false);
  x.dependencies.admit=()=>null;
  x.dependencies.runtime=async()=>{throw Error('runtime drift');};
  await assert.rejects(admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies),/runtime drift/);
  assert.equal(fs.existsSync(x.paths.claim),false);
});

test('load-time cache evidence is tied to the current instance and exact 8192 MiB limit', () => {
  const target='/models/gemma4-e2b.gguf', ref='instance-new';
  const log=[
    '[INFO] LlamaV4::load called with model path: /models/old.gguf',
    'load_model: prompt cache is enabled, size limit: 1024 MiB',
    `[INFO] LlamaV4::load called with model path: ${target}`,
    'load_model: loading model /models/gemma4-e2b.gguf',
    'load_model: prompt cache is enabled, size limit: 8192 MiB',
    `[INFO][Endpoint=getModelInfo] {"instanceReference":"${ref}"}`,
  ].join('\n');
  assert.deepEqual(admission.inspectLoadEvidence(log,target,ref).cache,
    {enabled:true,size_limit_mib:8192});
  assert.throws(()=>admission.inspectLoadEvidence(log.replace('size limit: 8192 MiB','size limit: 4096 MiB'),target,ref),/cache state or size/);
  assert.throws(()=>admission.inspectLoadEvidence(log,target,'other-instance'),/does not link current SDK instance/);
  assert.throws(()=>admission.inspectLoadEvidence(log+'\n[INFO] LlamaV4::load called with model path: /models/other.gguf',target,ref),/Newest loaded model/);
});

test('selected backend is observed without claiming loaded-instance engine proof', async t => {
  const engine='llama.cpp-mac-arm64-apple-metal-advsimd@2.22.0';
  const selected=[{model_format:'gguf',name:'llama.cpp-mac-arm64-apple-metal-advsimd',version:'2.22.0'}];
  assert.equal(admission.selectedBackendPreference(selected,engine).loaded_instance_version_verified,false);
  assert.throws(()=>admission.selectedBackendPreference([{...selected[0],version:'2.23.0'}],engine),/Selected GGUF backend differs/);
  const x=fixture(e2bOff,'fresh2','P2','smoke');
  t.after(()=>fs.rmSync(x.folder,{recursive:true,force:true}));
  x.dependencies.runtime=async()=>{
    admission.selectedBackendPreference([{...selected[0],version:'2.23.0'}],engine);
  };
  await assert.rejects(admission.runStage(plan,'test-plan',e2bOff,'fresh2','P2','smoke',x.receiptFile,x.dependencies),/Selected GGUF backend differs/);
  assert.equal(fs.existsSync(x.paths.claim),false);
});

test('real runtime guard checks actual cache and selected backend before any prediction',async () => {
  const config=plan.configurations[e2bOff], runtime=plan.parent_runtime;
  const ref='current-instance';
  const model={getModelInfo:async()=>({identifier:config.model_identifier,path:config.artifact_path,
    sizeBytes:config.artifact_bytes,contextLength:8192,quantization:{name:'Q4_K_M'},instanceReference:ref})};
  const full=path.join(runtime.models_dir,config.artifact_path);
  const log=`[INFO] LlamaV4::load called with model path: ${full}\nload_model: prompt cache is enabled, size limit: 8192 MiB\n[Endpoint=getModelInfo] {"instanceReference":"${ref}"}\n`;
  const selected={model_format:'gguf',name:'llama.cpp-mac-arm64-apple-metal-advsimd',version:'2.22.0'};
  const probes={model,backendPreferences:[selected],hashFile:file=>file===full?config.artifact_sha256:
    file===runtime.sdk_path?runtime.sdk_sha256:
    file===runtime.app_plist_path?runtime.app_plist_sha256:runtime.cli_sha256,
  loadLogs:()=>log,execFileSync:(file,args)=>{
    const cmd=args.join(' ');
    if(cmd==='--version')return `CLI commit: ${runtime.cli_commit}\n`;
    if(cmd==='runtime ls')return `${runtime.selected_engine}  ✓  GGUF\n`;
    if(cmd==='ps')return `IDENTIFIER  MODEL  STATE  CONTEXT  PARALLEL\n${config.model_identifier}  model  IDLE  8192  1\n`;
    if(cmd==='-n hw.model')return 'Mac16,5\n';
    if(cmd==='-n machdep.cpu.brand_string')return 'Apple M4 Max\n';
    throw Error(`Unexpected read-only command ${file} ${cmd}`);
  }};
  const attested=await admission.realRuntime(plan,config,probes);
  assert.equal(attested.attestation.load_evidence.cache.size_limit_mib,8192);
  assert.equal(attested.attestation.selected_backend_preference.loaded_instance_version_verified,false);
  assert.equal(attested.attestation.loaded_engine_version,null);
  await assert.rejects(admission.realRuntime(plan,config,{...probes,loadLogs:()=>log.replace('8192 MiB','4096 MiB')}),/cache state or size/);
  await assert.rejects(admission.realRuntime(plan,config,{...probes,backendPreferences:[{...selected,version:'2.23.0'}]}),/Selected GGUF backend differs/);
});

test('root receipt binds exact cache limit and fresh route',()=>{
  const id=e2bOff, config=plan.configurations[id], phaseId=phase(id,'fresh2','P2');
  const route='results/route-audits/local-historical-small-models-20260928/catalog-audit.json';
  const catalog=admission.read(admission.rel(route));
  const receipt={kind:'root-reviewed-small-local-stage-v1',approved:true,
    plan_sha256:'test-plan',controller_sha256:admission.hashFile(path.join(admission.ROOT,'scripts/small_local_repeat_admission.cjs')),
    phase:phaseId,stage:'smoke',model_identifier:config.model_identifier,
    artifact_sha256:config.artifact_sha256,cache_policy:{enabled:true,size_limit_mib:8192},
    reference_labels_read:false,exact_openrouter_route_absent:true,route_catalog_file:route,
    route_catalog_sha256:admission.hashFile(admission.rel(route)),route_checked_utc:catalog.retrieved_utc};
  const now=Date.parse(catalog.retrieved_utc)+1000;
  admission.checkReceipt(receipt,'test-plan',phaseId,'smoke',config,null,now);
  assert.throws(()=>admission.checkReceipt({...receipt,cache_policy:{enabled:true,size_limit_mib:4096}},'test-plan',phaseId,'smoke',config,null,now),/deep-equal/);
  assert.throws(()=>admission.checkReceipt(receipt,'test-plan',phaseId,'smoke',config,null,now+25*3600*1000),/Route attestation must be fresh/);
});

test('common native host lock excludes a second process', async t => {
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'small-local-lock-'));
  t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const lock=path.join(folder,'host.lock');
  const owner=spawn('python3',['-c','import fcntl,os,sys,time\nfd=os.open(sys.argv[1],os.O_CREAT|os.O_RDWR,0o600)\nfcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\nprint("ready",flush=True)\ntime.sleep(2)',lock],{stdio:['ignore','pipe','pipe']});
  t.after(()=>owner.kill());
  await new Promise((resolve,reject)=>{
    owner.stdout.once('data',data=>data.toString().includes('ready')?resolve():reject(Error('No lock owner')));
    owner.once('error',reject);
  });
  assert.throws(()=>execFileSync('python3',['-c',admission.lockCode,lock,process.execPath,'-e','process.exit(0)'],{stdio:'pipe'}),
    error=>error.status===73);
});

test('development requires completed three-valid smoke with root inspection',() => {
  assert.throws(()=>admission.checkPredecessor(plan,e2bOff,'fresh2','P0','development'),/Prior phase incomplete|Smoke not complete/);
});
