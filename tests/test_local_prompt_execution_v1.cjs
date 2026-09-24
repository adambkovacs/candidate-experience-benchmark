const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const os = require('node:os');
const path = require('node:path');
const controller = require('../scripts/local_prompt_execution_v1.cjs');

const manifest = JSON.parse(fs.readFileSync('results/local-prompt-exact-v1/manifest.json','utf8'));
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const decision = {sentiment:'positive',follow_up_needed:'no',serious_concern_reported:'no',testimonial_potential:'yes'};

test('all nine frozen source sets validate without reading labels or importing the SDK', () => {
  const source = controller.sourceCheck(manifest);
  assert.equal(Object.keys(source).length,9);
  for (const value of Object.values(source)) {
    assert.equal(value.records.length,180);
    assert.equal(value.counts.size,180);
    assert(value.records.every(row => row.composition_audit.reference_labels_read === false));
  }
});

test('source hash drift fails before any model access', () => {
  const changed = structuredClone(manifest);
  changed.source_sha256['data/pilot/inputs.jsonl'] = '0'.repeat(64);
  assert.throws(() => controller.sourceCheck(changed),/Source drift: data\/pilot\/inputs.jsonl/);
});

test('SDK response admits only exact native controls and strict raw JSON', () => {
  const expected={identifier:'m',path:'a.gguf',bytes:123,promptTokens:71,
    predictionConfig:{fields:[{key:'x',value:1}]},loadConfig:{fields:[{key:'y',value:2}]}};
  const result={modelInfo:{identifier:'m',path:'a.gguf',sizeBytes:123,contextLength:8192,quantization:{name:'Q4_K_M'}},
    predictionConfig:{fields:[{key:'x',value:1}]},loadConfig:{fields:[{key:'y',value:2}]},
    stats:{promptTokensCount:71,stopReason:'eosFound'},content:JSON.stringify(decision),
    nonReasoningContent:JSON.stringify(decision)};
  assert.deepEqual(controller.classifySdk(result,expected),{status:'ok',prediction:decision});
  assert.equal(controller.classifySdk({...result,nonReasoningContent:'```json\n'+JSON.stringify(decision)+'\n```'},expected).status,'invalid_output');
  assert.deepEqual(controller.classifySdk({...result,stats:{...result.stats,promptTokensCount:72}},expected),
    {status:'control_failure',reason:'prompt_token_count'});
  assert.deepEqual(controller.classifySdk({...result,modelInfo:{...result.modelInfo,identifier:'other'},nonReasoningContent:'bad'},expected),
    {status:'control_failure',reason:'model_identity'});
});

test('HTTP response checks model and native prompt count before classifying content', () => {
  const expected={identifier:'m',promptTokens:70};
  const body={model:'m',usage:{prompt_tokens:70},choices:[{message:{content:JSON.stringify(decision)},finish_reason:'stop'}]};
  assert.deepEqual(controller.classifyHttp({httpStatus:200,body},expected),{status:'ok',prediction:decision});
  assert.deepEqual(controller.classifyHttp({httpStatus:200,body:{...body,model:'other'}},expected),
    {status:'control_failure',reason:'returned_model'});
  assert.deepEqual(controller.classifyHttp({httpStatus:200,body:{...body,usage:{prompt_tokens:71}}},expected),
    {status:'control_failure',reason:'prompt_token_count'});
  assert.equal(controller.classifyHttp({httpStatus:200,body:{...body,choices:[{message:{content:'```json\n{}\n```'},finish_reason:'stop'}]}},expected).status,'invalid_output');
  assert.equal(controller.classifyHttp({httpStatus:429,body:{error:'busy'}},expected).status,'service_failure');
});

test('smoke journal must pair exact attempt and output hashes, including intrinsic invalids', () => {
  const rows=[],events=[];
  for(let i=1;i<=3;i++) {
    const id=`DEV-${String(i).padStart(3,'0')}`;
    const row={id,configuration:'unit',variant:'P1',phase:'smoke',attempt_id:`attempt-${i}`,
      request_sha256:sha(id),decision:{status:i===2?'invalid_output':'ok'}};
    rows.push(row);
    events.push({event:'started',id,attempt_id:row.attempt_id,request_sha256:row.request_sha256},
      {event:'finished',id,attempt_id:row.attempt_id,status:row.decision.status,
        output_sha256:sha(JSON.stringify(row))});
  }
  controller.validateSmoke(rows,events,'unit','P1');
  events[3].output_sha256='0'.repeat(64);
  assert.throws(() => controller.validateSmoke(rows,events,'unit','P1'));
});

test('linked local schedule refuses a later smoke without prior terminal', () => {
  const plan={config_order:['fixture-a','fixture-b'],configs:{'fixture-a':{conditions:['P1']},'fixture-b':{conditions:['P1']}}};
  controller.orderCheck(plan,'fixture-a','P1','smoke');
  assert.throws(() => controller.orderCheck(plan,'fixture-b','P1','smoke'),/ENOENT/);
});

test('lms ps parallelism is parsed from the PARALLEL column, not a substring of context', () => {
  const header='IDENTIFIER                           MODEL                                STATUS    SIZE         CONTEXT    PARALLEL    DEVICE    TTL    ';
  const first='recruitment-qwen3-0.6b-q4km          qwen3-0.6b                           IDLE      484.22 MB    8192       1           Local            ';
  const second=first.replace('8192       1           Local','8192       2           Local');
  assert.match(controller.requireLoadedModel(`\n${header}\n${first}\n`,'recruitment-qwen3-0.6b-q4km'),/8192\s+1\s+Local/);
  assert.throws(() => controller.requireLoadedModel(`\n${header}\n${second}\n`,'recruitment-qwen3-0.6b-q4km'),/Loaded parallelism mismatch/);
  assert.throws(() => controller.requireLoadedModel(`\n${header}\n${first.replace('8192','16384')}\n`,'recruitment-qwen3-0.6b-q4km'),/Loaded context mismatch/);
});

test('zero-claim preflight failure leaves retryable empty run paths and preserves claim evidence', () => {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'local-prompt-preflight-test-'));
  try {
    const output=path.join(dir,'smoke.jsonl'),journal=path.join(dir,'smoke.attempts.jsonl');
    const preflightTerminal=path.join(dir,'preflight-id.terminal.json');
    fs.writeFileSync(output,'');fs.writeFileSync(journal,'');
    controller.finishPreflightAttempt({output,journal,preflightTerminal},{id:'id',configuration:'fixture',
      variant:'P1',phase:'smoke',started:true,claimStarted:false,manifestHash:'m',
      preflightHash:'p',controllerHash:'c',error:'CLI cold',runtime:null});
    assert(!fs.existsSync(output) && !fs.existsSync(journal));
    assert.equal(JSON.parse(fs.readFileSync(preflightTerminal)).status,'failed_before_request');
    assert.equal(JSON.parse(fs.readFileSync(preflightTerminal)).stopped_reason,'CLI cold');
    assert(!fs.existsSync(path.join(dir,'smoke.terminal.json')));
    fs.writeFileSync(output,'');fs.writeFileSync(journal,'{"event":"started"}\n');
    assert.throws(() => controller.clearEmptyUnclaimed(output,journal,false),/Nonempty unclaimed attempt evidence/);
    assert(fs.existsSync(output) && fs.existsSync(journal));
    controller.clearEmptyUnclaimed(output,journal,true);
    assert(fs.existsSync(output) && fs.existsSync(journal));
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
