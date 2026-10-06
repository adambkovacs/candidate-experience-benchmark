const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const original=require('../scripts/small_local_repeat_admission.cjs');
const recovery=require('../scripts/small_local_e4b_on_interruption_continuation_v1.cjs');

const {plan,sha256}=original.verifyPlan();

test('stopped prefix remains 38 saved and DEV-039 unknown with exact hashes',()=>{
  const prefix=recovery.verifyStoppedPrefix(plan,sha256);
  assert.equal(prefix.failed_id,'DEV-039');
  assert.equal(prefix.saved_count,38);
  assert.equal(prefix.attempt_ids.length,39);
  assert.deepEqual(prefix.never_sent_ids,recovery.IDS.slice(39));
  for(const binding of Object.values(prefix.bindings)) recovery.verifyBinding(binding);
});

test('versioned schedule selects only never-sent DEV-040 through DEV-060 first',()=>{
  const manifest=recovery.expectedManifest();
  assert.equal(manifest.schema,recovery.SCHEMA);
  assert.equal(manifest.clean_matched_three_eligible,false);
  assert.equal(manifest.reference_labels_read,false);
  assert.equal(manifest.status,'offline_prepared_unapproved');
  assert.equal(manifest.schedule.length,9);
  assert.deepEqual(manifest.schedule.map(x=>[x.pass,x.condition,x.stage]),
    recovery.SEQUENCE);
  assert.deepEqual(manifest.schedule[0].ids,recovery.IDS.slice(39));
  assert.deepEqual(manifest.schedule[0].request_sha256,
    plan.configurations[recovery.ID].conditions.P2.requests.slice(39).map(x=>x.sha256));
  assert.deepEqual(recovery.selectedRows(plan,'fresh2','P2','suffix').map(x=>x.id),
    recovery.IDS.slice(39));
  assert.deepEqual(recovery.selectedRows(plan,'fresh2','P0','smoke').map(x=>x.id),
    recovery.IDS.slice(0,3));
  assert.throws(()=>recovery.selectedRows(plan,'fresh2','P2','development'),
    /Unknown continuation stage|assert/);
});

test('later stage refuses absent completed suffix and cannot bypass predecessor',t=>{
  const manifest=recovery.expectedManifest();
  const manifestSha=original.hashFile(recovery.MANIFEST);
  assert.equal(recovery.verifyPredecessors(manifest,manifestSha,'fresh2','P2','suffix'),null);
  const absent=recovery.paths('fresh2','P2','suffix').claim;
  const exists=fs.existsSync;
  t.mock.method(fs,'existsSync',file=>file===absent?false:exists(file));
  assert.throws(()=>recovery.verifyPredecessors(manifest,manifestSha,'fresh2','P0','smoke'),
    /Continuation closure missing/);
});

test('offline injected failure claims only DEV-040, preserves partial, and cannot replay',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'e4b-continuation-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const stage='suffix';
  const p={folder:dir,claim:path.join(dir,`${stage}.claim.json`),
    journal:path.join(dir,`${stage}.journal.jsonl`),
    raw:path.join(dir,`${stage}.raw.jsonl`),
    records:path.join(dir,`${stage}.records.jsonl`),
    completion:path.join(dir,`${stage}.completion.json`)};
  const receipt=path.join(dir,'review.json');fs.writeFileSync(receipt,'{}\n');
  const manifest=recovery.expectedManifest();
  let calls=0;
  const error=Object.assign(new Error('fixture timeout'),{code:'PREDICTION_TIMEOUT',
    cancellationAcknowledged:true,partialResult:{reasoningContent:'partial'}});
  const dependencies={prepare:()=>({manifest,paths:p}),
    runtime:async()=>({instance:'fixture-instance',
      model:{getModelInfo:async()=>({instanceReference:'fixture-instance'})},
      attestation:{artifact_sha256:plan.configurations[recovery.ID].artifact_sha256,
        load_evidence:{cache:plan.policy.cache_policy}}}),
    predict:async()=>{calls++;throw error;}};
  await assert.rejects(recovery.runStage('test-sha','fresh2','P2','suffix',receipt,dependencies),
    /fixture timeout/);
  assert.equal(calls,1);
  assert.deepEqual(original.rows(p.journal).map(x=>[x.event,x.id]),
    [['started','DEV-040'],['stopped_unknown','DEV-040']]);
  assert.equal(original.rows(p.raw)[0].partialResult.reasoningContent,'partial');
  assert.equal(original.rows(p.records).length,0);
  assert.equal(original.read(p.completion).status,'stopped');
  await assert.rejects(recovery.runStage('test-sha','fresh2','P2','suffix',receipt,dependencies),
    /already claimed/);
  assert.equal(calls,1);
});
