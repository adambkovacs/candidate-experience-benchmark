#!/usr/bin/env node
'use strict';
// Current operational policy. Historical rebaseline receipts retain their original rules.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const crypto=require('node:crypto');
const historical=require('./legacy_qwen_sdk_host_rebaseline_v1.cjs');
const policyFile=path.join(__dirname,'../config/local-execution.json');
function currentHost(run){
  const bytes=fs.readFileSync(policyFile),policy=JSON.parse(bytes);
  assert.equal(policy.schema,'local-execution-policy-v1');
  assert.equal(typeof policy.allow_battery_power,'boolean');
  const host=historical.currentHost(run,{requireAcPower:!policy.allow_battery_power});
  return {...host,power_source:host.ac_power?'ac':'battery',
    operational_policy:{...policy,sha256:crypto.createHash('sha256').update(bytes).digest('hex')}};
}
function verifyAfterStage(before,after){
  assert.equal(after.boot,before.boot,'Host boot changed');
  assert.equal(after.sleep_wakes,before.sleep_wakes,'Host slept during stage');
  assert.equal(after.lid_open,true,'Host lid is not open');
  assert.deepEqual(after.operational_policy,before.operational_policy,'Host admission policy changed');
  return {host_unchanged:true,power_source_changed:before.power_source!==after.power_source,
    power_source_before:before.power_source,power_source_after:after.power_source};
}
if(require.main===module) console.log(JSON.stringify(currentHost(),null,2));
module.exports={currentHost,verifyAfterStage};
