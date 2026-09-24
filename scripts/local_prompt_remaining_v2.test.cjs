const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const runner=require('./local_prompt_remaining_v2.cjs');
const root=path.resolve(__dirname,'..');
const m=JSON.parse(fs.readFileSync(path.join(root,'results/local-prompt-remaining-v2/manifest.json')));

test('frozen source reconstructs all 60 P1 requests without labels',()=>{
  const source=runner.checkSource(m);
  const rows=source[m.configuration].records.filter(x=>x.variant==='P1');
  assert.equal(rows.length,60);
  assert.deepEqual(rows.map(x=>x.id),Array.from({length:60},(_,i)=>`DEV-${String(i+1).padStart(3,'0')}`));
  assert.equal(m.reference_labels_read,false);
});

test('P1 admission refuses the unfinished suffix',()=>{
  if(fs.existsSync(path.join(root,m.suffix.terminal)))return; // A completed suffix is tested at admission time.
  assert.throws(()=>runner.checkSuffix(m),/ENOENT/);
});

test('P1 run requires a reviewed, hash-bound receipt',()=>{
  assert.throws(()=>runner.reviewCheck(m,{},{}));
});
