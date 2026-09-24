const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const suffix=require('../scripts/local_prompt_suffix_v1.cjs');
const root=path.resolve(__dirname,'..');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'results/local-prompt-suffix-v1/manifest.json'),'utf8'));
const read=rel=>JSON.parse(fs.readFileSync(path.join(root,rel),'utf8'));
const lines=rel=>fs.readFileSync(path.join(root,rel),'utf8').trim().split('\n').map(JSON.parse);
const fixture=()=>({m:structuredClone(manifest),b:structuredClone(manifest.binding),
  audit:read(manifest.binding.interruption_audit),
  parent:read(manifest.binding.parent_manifest),
  rows:lines(manifest.binding.original_output),events:lines(manifest.binding.original_journal)});

test('exact suffix starts at untouched DEV-020 and has 41 input-only requests',()=>{
  const got=suffix.sourceAndSuffix(manifest);
  assert.deepEqual(got.records.map(x=>x.id),suffix.expectedSuffix);
  assert.equal(got.records.length,41);
  assert(got.records.every(x=>x.variant==='P2' && x.messages.map(m=>m.role).join(',')==='system,user'));
});
test('original audit binds 18 rows and unresolved DEV-019',()=>{
  const f=fixture();
  suffix.validateOriginalRows(f.rows,f.events,f.m,f.b,f.audit,f.parent);
  assert.equal(f.events.at(-1).id,'DEV-019');
  assert.equal(f.events.at(-1).event,'started');
  assert.equal(f.rows.at(-1).id,'DEV-018');
});
test('extra started attempt closes the untouched suffix',()=>{
  const f=fixture();f.events.push({...f.events.at(-1),id:'DEV-020'});
  assert.throws(()=>suffix.validateOriginalRows(f.rows,f.events,f.m,f.b,f.audit,f.parent));
});
test('forged finish hash is rejected',()=>{
  const f=fixture();f.events[1].output_sha256='0'.repeat(64);
  assert.throws(()=>suffix.validateOriginalRows(f.rows,f.events,f.m,f.b,f.audit,f.parent));
});
test('replay of DEV-019 is excluded even when list length stays 41',()=>{
  const f=fixture();f.m.allowed_ids[0]='DEV-019';
  assert.throws(()=>suffix.validateOriginalRows(f.rows,f.events,f.m,f.b,f.audit,f.parent));
});
test('original output hash drift is rejected',()=>{
  const f=fixture();f.m.binding.original_output_sha256='0'.repeat(64);
  assert.throws(()=>suffix.originalEvidence(f.m));
});
test('run cannot pass review gate without root receipts and lock release',()=>{
  assert.throws(()=>suffix.approval(manifest,{'approved-manifest-sha256':crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'results/local-prompt-suffix-v1/manifest.json'))).digest('hex')}));
});
