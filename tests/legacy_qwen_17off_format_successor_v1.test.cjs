'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
const small=require('../scripts/small_local_repeat_admission.cjs');
const successor=require('../scripts/legacy_qwen_17off_format_successor_v1.cjs');

const ID='qwen3-1.7b-sdk-thinking-off',PASS='fresh3',CONDITION='P2';
const folder=legacy.stagePaths(ID,PASS,CONDITION,'smoke').folder;
const lines=file=>fs.readFileSync(file,'utf8').trim().split('\n').map(JSON.parse);

test('manifest binds the exact phase and rejects other phases',()=>{
  const ctx=successor.verifyManifest();
  assert.deepEqual(ctx.manifest.scope,{configuration:ID,pass:PASS,condition:CONDITION,stage:'development'});
  assert.throws(()=>successor.assertScope(ID,'fresh2',CONDITION,'development'));
  assert.throws(()=>successor.assertScope(ID,PASS,'P1','development'));
  assert.throws(()=>successor.assertScope('qwen3-1.7b-sdk-thinking-on',PASS,CONDITION,'development'));
});

test('fresh preflight candidates have distinct names and cannot escape successor directory',()=>{
  const first=successor.receiptCandidatePath('20261005T192356123Z');
  const second=successor.receiptCandidatePath('20261005T192356124Z');
  assert.notEqual(first,second);
  assert.match(first,/legacy-qwen-17off-format-successor-v1\/development-receipt-candidate-20261005T192356123Z\.json$/);
  assert.throws(()=>successor.receiptCandidatePath('../other'));
});

test('retained stopped smoke is exactly two valid and one intrinsic format failure',()=>{
  const ctx=successor.verifyManifest();
  const checked=successor.validateSmokeEvidence(ctx);
  assert.equal(checked.invalid,1);
  assert.deepEqual(checked.details.map(x=>[x.id,x.status,x.reason]),[
    ['DEV-001','ok',null],['DEV-002','ok',null],['DEV-003','invalid_output','non_json']]);
  const candidate=successor.inspectionCandidate(ctx);
  assert.equal(candidate.approved,false);
  assert.equal(candidate.smoke_replayed,false);
  assert.equal(candidate.output_repaired,false);
  assert.equal(candidate.intrinsic_invalid_count,1);
  assert.equal(candidate.raw_sha256,'25c829658bd90ab2b95c7b3d5e3eca790354751a754a33d5b0fed5118868df59');
});

test('changed SDK controls and provider error cannot pass intrinsic-output admission',()=>{
  const ctx=successor.verifyManifest();
  const paths=legacy.stagePaths(ID,PASS,CONDITION,'smoke');
  const data={completion:JSON.parse(fs.readFileSync(paths.completion)),
    claim:JSON.parse(fs.readFileSync(paths.claim)),journal:lines(paths.journal),
    raw:lines(paths.raw),records:lines(paths.records),config:ctx.plan.configurations[ID],
    requestRows:legacy.stageRows(ctx.plan,ID,CONDITION,'smoke').map(row=>({
      request_sha256:small.hash(JSON.stringify(row.request)),prompt_tokens:row.prompt_tokens}))};
  data.raw[2].result.predictionConfig.fields.find(x=>x.key==='llm.prediction.temperature').value=0.2;
  assert.throws(()=>successor.validateSmokeData(data));
  data.raw=lines(paths.raw);
  data.raw[2].error='provider unavailable';
  assert.throws(()=>successor.validateSmokeData(data));
});

test('unapproved successor cannot dispatch and original smoke remains unclaimed for replay',async()=>{
  const ctx=successor.verifyManifest();
  ctx.manifest={...ctx.manifest,status:'offline_prepared_unapproved',approval:null};
  await assert.rejects(successor.dispatch(ctx,ID,PASS,CONDITION,'development','not-a-receipt'),
    /awaits independent review/);
  assert.equal(fs.existsSync(folder+'/smoke.completion.json'),true);
});
