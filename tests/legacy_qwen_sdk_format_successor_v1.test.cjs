'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const legacy=require('../scripts/legacy_qwen_repeat_admission.cjs');
const small=require('../scripts/small_local_repeat_admission.cjs');
const successor=require('../scripts/legacy_qwen_sdk_format_successor_v1.cjs');

const ids=['qwen3-0.6b-sdk-thinking-on','qwen3-0.6b-sdk-thinking-off'];
const {plan}=successor.verifyManifest();
const load=id=>{
  const paths=legacy.stagePaths(id,'fresh1','P0','smoke');
  const lines=file=>fs.readFileSync(file,'utf8').trim().split('\n').map(JSON.parse);
  const requestRows=legacy.stageRows(plan,id,'P0','smoke').map(row=>({
    request_sha256:small.hash(JSON.stringify(row.request)),prompt_tokens:row.prompt_tokens}));
  return {completion:JSON.parse(fs.readFileSync(paths.completion,'utf8')),
    claim:JSON.parse(fs.readFileSync(paths.claim,'utf8')),
    journal:lines(paths.journal),raw:lines(paths.raw),records:lines(paths.records),
    config:plan.configurations[id],requestRows};
};

for(const [id,count] of [[ids[0],2],[ids[1],3]]){
  test(`retained ${id} smoke has ${count} intrinsic invalid outputs with exact controls`,()=>{
    assert.equal(successor.validateSmokeEvidence(plan,id,'fresh1','P0').invalid,count);
    const candidate=successor.inspectionCandidate(plan,id,'fresh1','P0');
    assert.equal(candidate.approved,false);
    assert.equal(candidate.intrinsic_invalid_count,count);
    assert.equal(candidate.control_and_transport_verified,true);
  });
}

test('changed load field cannot pass even when saved decision says invalid output',()=>{
  const data=load(ids[0]);
  data.raw[0].result.loadConfig.fields.find(x=>x.key==='llm.load.numParallelSessions').value=4;
  assert.throws(()=>successor.validateSmokeData(data));
});

test('provider or control failure cannot be relabeled as intrinsic invalid output',()=>{
  const data=load(ids[1]);
  data.records[0].decision={status:'control_failure',reason:'load_config'};
  assert.throws(()=>successor.validateSmokeData(data));
  const withError=load(ids[1]);
  withError.raw[0].error='provider unavailable';
  assert.throws(()=>successor.validateSmokeData(withError));
});

test('unknown stop reason and incomplete journal cannot pass transport review',()=>{
  const data=load(ids[1]);
  data.raw[0].result.stats.stopReason='unknown';
  assert.throws(()=>successor.validateSmokeData(data));
  const missing=load(ids[1]);
  missing.journal.pop();
  assert.throws(()=>successor.validateSmokeData(missing));
});

test('approved successor inspection binds the retained smoke evidence',()=>{
  for(const id of ids){
    assert.equal(successor.inspectionCandidate(plan,id,'fresh1','P0').approved,false);
    assert.match(successor.successorPredecessor(plan,id,'fresh1','P0','development'),/^[0-9a-f]{64}$/);
  }
});

test('unapproved manifest refuses dispatch before any inference',async()=>{
  const ctx=successor.verifyManifest();
  ctx.manifest={...ctx.manifest,status:'offline_prepared_unapproved',approval:null};
  await assert.rejects(successor.dispatch(ctx,ids[0],'fresh1','P0','development','not-a-receipt'));
});
