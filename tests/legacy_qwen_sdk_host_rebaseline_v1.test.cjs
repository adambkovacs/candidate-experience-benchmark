'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {parseHost,candidate,checkReceipt}=require('../scripts/legacy_qwen_sdk_host_rebaseline_v1.cjs');

const sample={
  power:"Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t8%; charging; present: true\n",
  clamshell:'"AppleClamshellState" = No',
  memory:'System-wide memory free percentage: 46%',
  log:"2026-10-02 16:37:45 +0200 Sleep \tEntering Sleep state due to 'Clamshell Sleep'\n"+
    '2026-10-02 16:43:20 +0200 Wake  \tDarkWake to FullWake\n'+
    '2026-10-02 16:43:21 +0200 Wake Requests  \tFuture scheduled wake\n'+
    'Total Sleep/Wakes since boot at 2026-10-02 12:48:09 +0200 :1\n',
};

test('captures current boot and intervening sleep without an invented battery cutoff',()=>{
  const host=parseHost(sample);
  assert.equal(host.sleep_wakes,1);
  assert.equal(host.battery_percent,8);
  assert.match(host.last_wake,/16:43:20/);
  assert.equal(host.sleep_wake_events.length,2);
  const receipt=candidate(host,new Date('2026-10-02T14:50:00Z'));
  assert.equal(receipt.policy.battery_percentage_cutoff,null);
  assert.equal(checkReceipt(receipt,host),true);
});

test('fails closed if a new sleep occurs or AC, lid, or memory become unsafe',()=>{
  const host=parseHost(sample),receipt=candidate(host);
  assert.throws(()=>checkReceipt(receipt,{...host,sleep_wakes:2}),/slept/);
  assert.throws(()=>parseHost({...sample,power:"Now drawing from 'Battery Power'"}),/AC/);
  assert.throws(()=>parseHost({...sample,clamshell:'"AppleClamshellState" = Yes'}),/lid/);
  assert.throws(()=>parseHost({...sample,memory:'System-wide memory free percentage: 24%'}),/Memory/);
});

test('independent root approval is required for stage checks',()=>{
  const host=parseHost(sample),receipt=candidate(host);
  assert.throws(()=>checkReceipt(receipt,host,{requireApproval:true}),/Root review missing/);
  Object.assign(receipt,{approved:true,reviewer:'/root',reviewed_utc:'2026-10-02T14:50:00Z',authorized_by_root:true});
  assert.equal(checkReceipt(receipt,host,{requireApproval:true}),true);
});
