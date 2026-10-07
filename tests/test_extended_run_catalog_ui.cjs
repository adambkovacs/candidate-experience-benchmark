const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const root=path.resolve(__dirname,'..');
const app=fs.readFileSync(path.join(root,'public-site/app.js'),'utf8');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'public-site/extended-run-catalog-v1.json'),'utf8'));
const adapterSource=app.replace('  init();\n})();','  globalThis.__extendedCatalogRuns=extendedCatalogRuns;\n})();');
assert.notEqual(adapterSource,app);
const context={document:{},URL};
context.globalThis=context;
vm.runInNewContext(adapterSource,context);
const adapt=context.__extendedCatalogRuns;

test('report-backed saved stages enter the unified explorer without invented costs',()=>{
  const accepted=adapt(catalog,[]);
  assert.equal(accepted.length,catalog.runCount);
  assert.ok(accepted.length>300);
  assert.ok(accepted.every(run=>run.records===60&&run.sourceOnlyDetails));
  assert.ok(accepted.some(run=>run.cost.actualUsd===null));
  assert.ok(accepted.some(run=>run.repeatPass==='fresh2'));
});

test('catalog adapter fails closed on source drift, duplicate IDs and wrong denominator',()=>{
  const drift=structuredClone(catalog);
  drift.runs[0].sourceRecordSha256='0'.repeat(64);
  assert.equal(adapt(drift,[]).length,0);
  assert.equal(adapt(catalog,[{id:catalog.runs[0].id}]).length,0);
  const denominator=structuredClone(catalog);
  denominator.runs[0].records=59;
  assert.equal(adapt(denominator,[]).length,0);
});

test('every catalog report link points to its declared public source hash',()=>{
  const prefix='https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  for(const run of catalog.runs){
    assert.ok(run.sourceRecordsUrl.startsWith(prefix));
    assert.equal(run.sourceRecordSha256,catalog.sourceSha256[run.sourceRecordsUrl.slice(prefix.length)]);
  }
});
