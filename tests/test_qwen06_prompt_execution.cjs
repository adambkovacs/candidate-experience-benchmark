const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const controller = fs.existsSync(path.join(__dirname,'qwen06_prompt_execution.cjs')) ?
  path.join(__dirname,'qwen06_prompt_execution.cjs') : path.join(__dirname,'../scripts/qwen06_prompt_execution.cjs');
const {parseResult, sourceCheck, preflight, validateSmokeRows, validatePriorTerminal,
  validateFeedback,validateComposition} = require(controller);
const sha = value => crypto.createHash('sha256').update(value).digest('hex');

const repo = '/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo';
const baseline = JSON.parse(fs.readFileSync(path.join(repo,'results/qwen3-0.6b-sdk-thinking-2026-09-21/development.jsonl'),'utf8').split('\n')[0]);
const answer = JSON.stringify({sentiment:'positive',follow_up_needed:'no',serious_concern_reported:'no',testimonial_potential:'yes'});
const expected = {prompt_tokens:1738,observed_prediction_config:baseline.prediction_config,observed_load_config:baseline.load_config};
const mock = () => ({modelInfo:structuredClone(baseline.model_info),predictionConfig:structuredClone(baseline.prediction_config),
  loadConfig:structuredClone(baseline.load_config),stats:{promptTokensCount:1738,stopReason:'eosFound'},
  content:answer,nonReasoningContent:answer});

test('valid native response is accepted only with exact inherited controls', () => {
  assert.equal(parseResult(mock(),expected).status,'ok');
  const bad = mock();bad.predictionConfig.fields.find(f=>f.key==='llm.prediction.temperature').value=0;
  assert.deepEqual(parseResult(bad,expected),{status:'control_failure',reason:'prediction_config'});
  const badLoad = mock();badLoad.loadConfig.fields.find(f=>f.key==='llm.load.contextLength').value=4096;
  assert.deepEqual(parseResult(badLoad,expected),{status:'control_failure',reason:'load_config'});
});

test('model identity and prompt-token discrepancy stop even when JSON is valid', () => {
  const badModel = mock();badModel.modelInfo.path='other/model.gguf';
  assert.deepEqual(parseResult(badModel,expected),{status:'control_failure',reason:'model_identity'});
  const badCount = mock();badCount.stats.promptTokensCount=1739;
  assert.deepEqual(parseResult(badCount,expected),{status:'control_failure',reason:'prompt_token_count'});
});

test('intrinsic malformed outputs remain observations', () => {
  const malformed = mock();malformed.content='not JSON';malformed.nonReasoningContent='not JSON';
  assert.deepEqual(parseResult(malformed,expected),{status:'invalid_output',reason:'non_json'});
  const schema = mock();schema.content='{}';schema.nonReasoningContent='{}';
  assert.deepEqual(parseResult(schema,expected),{status:'invalid_output',reason:'schema'});
  const stopped = mock();stopped.stats.stopReason='maxPredictedTokensReached';
  assert.deepEqual(parseResult(stopped,expected),{status:'invalid_output',reason:'stop_reason'});
});

test('frozen source and zero-route gates reject tampering before SDK import', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(repo,'results/qwen06-prompt-exact-v1/manifest.json'),'utf8'));
  const checked = sourceCheck(manifest);
  assert.equal(checked.render.length,360);
  assert.equal(preflight(manifest).context_fit,360);
  const tampered = structuredClone(manifest);
  tampered.source_sha256[tampered.render_file]='0'.repeat(64);
  assert.throws(()=>sourceCheck(tampered),/Source drift/);
  const changed = structuredClone(manifest);
  changed.conditions.reverse();
  assert.throws(()=>sourceCheck(changed));
});

test('development gate requires three completed smoke attempts with no control failure', () => {
  const ids=['DEV-001','DEV-002','DEV-003'];
  const rows=ids.map((id,i)=>({id,condition:'thinking-on-P2',phase:'smoke',
    attempt_id:`00000000-0000-4000-8000-${String(i+1).padStart(12,'0')}`,
    request:{messages:[{role:'user',content:id}],config:{}},decision:{status:'ok'}}));
  for(const row of rows) row.request_sha256=sha(JSON.stringify(row.request));
  const journal=rows.flatMap(row=>[
    {event:'started',id:row.id,attempt_id:row.attempt_id,request_sha256:row.request_sha256},
    {event:'finished',id:row.id,attempt_id:row.attempt_id,status:row.decision.status,output_sha256:sha(JSON.stringify(row))}]);
  assert.doesNotThrow(()=>validateSmokeRows(rows,journal,'thinking-on-P2'));
  const failed=structuredClone(rows);failed[1].decision.status='control_failure';
  assert.throws(()=>validateSmokeRows(failed,journal,'thinking-on-P2'),/control failure/);
  assert.throws(()=>validateSmokeRows(rows,journal.slice(0,-1),'thinking-on-P2'));
  const forged=structuredClone(journal);forged[1].output_sha256='0'.repeat(64);
  assert.throws(()=>validateSmokeRows(rows,forged,'thinking-on-P2'));
  const other=structuredClone(journal);other[1].attempt_id='00000000-0000-4000-8000-999999999999';
  assert.throws(()=>validateSmokeRows(rows,other,'thinking-on-P2'));
});

test('original schedule order requires prior condition terminal before next smoke', () => {
  const good={condition:'thinking-on-P2',phase:'development',status:'completed',finished_attempts:60,
    saved_rows:60,ambiguous_timeout:false,manifest_sha256:'abc'};
  assert.doesNotThrow(()=>validatePriorTerminal(good,'thinking-on-P2','abc'));
  assert.throws(()=>validatePriorTerminal({...good,status:'stopped'},'thinking-on-P2','abc'));
  assert.throws(()=>validatePriorTerminal({...good,saved_rows:59},'thinking-on-P2','abc'));
});

test('canonical feedback and exact frozen system composition reject tampering', () => {
  const render=JSON.parse(fs.readFileSync(path.join(repo,'results/qwen06-sdk-token-preflight-2026-09-24/rendered-prompts.json')));
  const base=render.find(row=>row.configuration==='qwen3-0.6b-sdk-thinking-on'&&row.variant==='P0'&&row.id==='DEV-001');
  const variant=render.find(row=>row.configuration==='qwen3-0.6b-sdk-thinking-on'&&row.variant==='P2'&&row.id==='DEV-001');
  const feedback=JSON.parse(base.messages[1].content).feedback;
  const {compose_instruction}=require(path.join(repo,'scripts/frozen_prompt_variants.cjs'));
  assert.doesNotThrow(()=>validateFeedback(variant,feedback));
  assert.doesNotThrow(()=>validateComposition(variant,base,compose_instruction));
  const changed=structuredClone(variant);changed.messages[1].content=JSON.stringify({feedback:'altered'});
  assert.throws(()=>validateFeedback(changed,feedback),/Canonical feedback mismatch/);
  const changedSystem=structuredClone(variant);changedSystem.messages[0].content+=' altered';
  assert.throws(()=>validateComposition(changedSystem,base,compose_instruction),/Composed instruction mismatch/);
});
