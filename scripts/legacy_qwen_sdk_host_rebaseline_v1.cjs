#!/usr/bin/env node
'use strict';
// Operational host admission after a between-stage sleep. This does not alter model controls.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const crypto=require('node:crypto');
const {execFileSync}=require('node:child_process');

const phases=[
  'qwen3-0.6b-sdk-thinking-on/fresh3/P2',
  'qwen3-0.6b-sdk-thinking-off/fresh3/P2',
];
const sha256=b=>crypto.createHash('sha256').update(b).digest('hex');
const command=(name,args)=>execFileSync(name,args,{encoding:'utf8',timeout:120000,maxBuffer:64*1024*1024});

function parseHost({power,clamshell,memory,log},{requireAcPower=true}={}){
  const total=log.match(/Total Sleep\/Wakes since boot at (.+?)\s+:\s*(\d+)/);
  assert(total,'Host boot/sleep count unavailable');
  const boot=total[1].trim(),sleepWakes=Number(total[2]);
  assert(Number.isSafeInteger(sleepWakes) && sleepWakes>=0);
  const ac=/Now drawing from 'AC Power'/.test(power);
  const lidOpen=/"AppleClamshellState" = No/.test(clamshell);
  const memoryFree=Number(memory.match(/System-wide memory free percentage:\s*(\d+)%/)?.[1]);
  const batteryPercent=Number(power.match(/-InternalBattery-\d+.*?\b(\d+)%/)?.[1]);
  assert(ac || /Now drawing from 'Battery Power'/.test(power),'Host power source unavailable');
  if(requireAcPower) assert(ac,'Host is not on AC power');
  assert(lidOpen,'Host lid is not open');
  assert(Number.isFinite(memoryFree) && memoryFree>=25,'Memory headroom below 25% or unavailable');
  const bootMs=Date.parse(boot);
  assert(Number.isFinite(bootMs),'Host boot timestamp unavailable');
  const events=log.split('\n').filter(line=>/^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [+-]\d{4} (?:Sleep|Wake|DarkWake)\s{2,}/.test(line))
    .filter(line=>Date.parse(line.slice(0,25))>=bootMs)
    .map(line=>line.trim());
  const lastWake=[...events].reverse().find(line=>/\sWake\s/.test(line))??null;
  if(sleepWakes>0)assert(lastWake,'Wake event unavailable for nonzero sleep count');
  return {boot,sleep_wakes:sleepWakes,ac_power:ac,lid_open:lidOpen,
    memory_free_percent:memoryFree,battery_percent:Number.isFinite(batteryPercent)?batteryPercent:null,
    last_wake:lastWake,sleep_wake_events:events};
}

function currentHost(run=command,options={}){
  return parseHost({power:run('pmset',['-g','batt']),
    clamshell:run('ioreg',['-r','-k','AppleClamshellState','-d','4']),
    memory:run('memory_pressure',['-Q']),log:run('pmset',['-g','log'])},options);
}

function candidate(host,now=new Date()){
  return {kind:'legacy-qwen-sdk-host-rebaseline-v1',approved:false,reviewer:null,
    reviewed_utc:null,authorized_by_root:false,created_utc:now.toISOString(),
    scope:phases,reason:'between-stage clamshell sleep; previous zero-wake gate refused admission',
    prior_sleep_wakes:0,observed_host:host,
    policy:{require_same_boot:true,require_same_sleep_wakes:true,require_ac_power:true,
      require_open_lid:true,min_memory_free_percent:25,verify_after_stage:true,
      battery_percentage_cutoff:null}};
}

function checkReceipt(receipt,host,{requireApproval=false}={}){
  assert.equal(receipt.kind,'legacy-qwen-sdk-host-rebaseline-v1');
  assert.deepEqual(receipt.scope,phases);
  assert.deepEqual(receipt.policy,candidate(host).policy);
  assert.equal(receipt.observed_host.boot,host.boot,'Host boot changed');
  assert.equal(receipt.observed_host.sleep_wakes,host.sleep_wakes,'Host slept since rebaseline');
  assert.equal(receipt.observed_host.last_wake,host.last_wake,'Latest wake changed');
  assert.deepEqual(receipt.observed_host.sleep_wake_events,host.sleep_wake_events,'Sleep/wake event history changed');
  assert.equal(host.ac_power,true);
  assert.equal(host.lid_open,true);
  assert(host.memory_free_percent>=25);
  if(requireApproval){
    assert.equal(receipt.approved,true,'Root review missing');
    assert.equal(receipt.authorized_by_root,true);
    assert.equal(typeof receipt.reviewer,'string');assert(receipt.reviewer.length>0);
    assert(Number.isFinite(Date.parse(receipt.reviewed_utc)));
  }
  return true;
}

function main(args){
  const [action,file,stageReceiptFile]=args;
  assert(['capture','verify','check','post'].includes(action),'Use capture, verify, check, or post');
  assert(file,'Require rebaseline receipt path');
  const host=currentHost();
  if(action==='capture'){
    const receipt=candidate(host);
    fs.writeFileSync(file,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify({file,sha256:sha256(fs.readFileSync(file)),approved:false,host}));
    return;
  }
  const receipt=JSON.parse(fs.readFileSync(file,'utf8'));
  checkReceipt(receipt,host,{requireApproval:action!=='verify'});
  if(action==='check'||action==='post'){
    assert(stageReceiptFile,'Require development stage receipt path');
    const stage=JSON.parse(fs.readFileSync(stageReceiptFile,'utf8'));
    assert(phases.includes(stage.phase),'Stage outside rebaseline scope');
    assert.equal(stage.host_rebaseline_file,file);
    assert.equal(stage.host_rebaseline_sha256,sha256(fs.readFileSync(file)));
  }
  console.log(JSON.stringify({action,approved:receipt.approved,host,sha256:sha256(fs.readFileSync(file))}));
}
if(require.main===module){try{main(process.argv.slice(2));}catch(error){console.error(error.stack||error);process.exitCode=1;}}
module.exports={parseHost,currentHost,candidate,checkReceipt,phases};
