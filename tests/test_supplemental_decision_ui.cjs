const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const site=path.resolve(__dirname,'../public-site');
const report=JSON.parse(fs.readFileSync(path.join(site,'supplemental-decision-runs-v1.json'),'utf8'));
const source=fs.readFileSync(path.join(site,'app.js'),'utf8').replace('  init();\n})();','  globalThis.adapter={supplementalDecisionRuns,experimentId,costRows};\n})();');
function api(){const c={document:{querySelector:()=>null},URL};vm.runInNewContext(source,c);return c.adapter;}
test('all 21 closed native runs remain selectable with same-pass prompt groups',()=>{
 const a=api(),runs=a.supplementalDecisionRuns(report);
 assert.equal(runs.length,21);
 assert.equal(new Set(runs.map(a.experimentId)).size,7);
 assert.deepEqual(runs.filter(r=>r.id.startsWith('solar')).map(r=>r.metrics.all_four),[55,53,53]);
 assert.ok(runs.every(r=>r.timing.inferenceSeconds===null&&r.cost.actualUsd===null&&r.sourceOnlyDetails));
});
test('bad coverage or ID collisions cannot become partial scored additions',()=>{
 const a=api();
 for(const mutate of [r=>r.runs[0].valid=59,r=>r.runs[0].cost.knownUsd=-1,r=>r.runs[0].sourceRecordSha256='bad',r=>r.runs[1].id=r.runs[0].id]){
  const r=structuredClone(report);mutate(r);assert.equal(a.supplementalDecisionRuns(r).length,0);
 }
 assert.equal(a.supplementalDecisionRuns(report,[{id:report.runs[0].id}]).length,0);
});
test('new native rows classify as decision interfaces without invented training lineage',()=>{
 const c={};vm.runInNewContext(fs.readFileSync(path.join(site,'model-categories.js'),'utf8'),c);
 for(const r of report.runs){const t=c.BenchmarkCategories.classify(r);assert.equal(t.category,'decision');assert.equal(t.interfaceKind,'native');assert.equal(t.trainingLineage,'unknown');}
});
