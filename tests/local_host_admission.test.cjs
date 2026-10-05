'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const current=require('../scripts/local_host_admission.cjs');
const historical=require('../scripts/legacy_qwen_sdk_host_rebaseline_v1.cjs');
const input={power:"Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1)\t80%; discharging; present: true",clamshell:'"AppleClamshellState" = No',memory:'System-wide memory free percentage: 46%',log:'Total Sleep/Wakes since boot at 2026-10-05 12:00:00 +0200 :0'};
const run=(name,args)=>name==='ioreg'?input.clamshell:name==='memory_pressure'?input.memory:args[1]==='batt'?input.power:input.log;
test('current setting allows battery and records truthful source; historical AC policy remains strict',()=>{
 const h=current.currentHost(run);assert.equal(h.ac_power,false);assert.equal(h.power_source,'battery');assert.equal(h.battery_percent,80);
 assert.equal(h.operational_policy.allow_battery_power,true);assert.match(h.operational_policy.sha256,/^[a-f0-9]{64}$/);
 assert.throws(()=>historical.parseHost(input),/AC power/);
 assert.equal(current.verifyAfterStage(h,h).power_source_changed,false);
 assert.equal(current.verifyAfterStage(h,{...h,power_source:'ac',ac_power:true}).power_source_changed,true);
 assert.throws(()=>current.verifyAfterStage(h,{...h,sleep_wakes:1}),/slept/);
});
test('battery permission does not bypass missing source, lid or memory checks',()=>{
 assert.throws(()=>historical.parseHost({...input,power:'unavailable'},{requireAcPower:false}),/source unavailable/);
 assert.throws(()=>historical.parseHost({...input,clamshell:'"AppleClamshellState" = Yes'},{requireAcPower:false}),/lid/);
 assert.throws(()=>historical.parseHost({...input,memory:'System-wide memory free percentage: 24%'},{requireAcPower:false}),/Memory/);
});
