const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const site=path.resolve(__dirname,'../public-site');
const report=JSON.parse(fs.readFileSync(path.join(site,'supplemental-decision-runs-v1.json'),'utf8'));
const source=fs.readFileSync(path.join(site,'app.js'),'utf8').replace('  init();\n})();','  globalThis.adapter={supplementalDecisionRuns,experimentId,costRows,missing,tallyNote,comparisonNote};\n})();');
function api(){const c={document:{querySelector:()=>null},URL};vm.runInNewContext(source,c);return c.adapter;}
test('all closed native run views remain selectable with separate OpenRouter groups',()=>{
 const a=api(),runs=a.supplementalDecisionRuns(report);
 assert.equal(runs.length,report.runs.length);
 assert.equal(runs.filter(r=>/^(solar-decide|liquid-d1|tev1-4b)-native-/.test(r.id)).length,27);
 assert.equal(runs.filter(r=>/-openrouter-native-/.test(r.id)).length,27);
 assert.equal(runs.filter(r=>/^perplexity-decider-native-/.test(r.id)).length,9);
 assert.equal(new Set(runs.map(a.experimentId)).size,21);
 assert.deepEqual(runs.filter(r=>r.id.startsWith('solar')).map(r=>r.metrics.all_four),[55,53,53,53,52,52,54,51,52]);
 const final=runs.find(r=>r.id==='solar-decide-native-fresh3-p2');
 assert.equal(final.complete,false);assert.equal(final.valid,59);assert.equal(a.missing(final),"1");assert.match(a.tallyNote(final),/59 of 60 saved, 1 without/);assert.equal(final.pairedEligible,false);assert.match(a.comparisonNote(final),/59 shared answers/);
 assert.equal(final.tokens.reportedRequests,59);assert.equal(final.cost.unknownUpperBoundUsd,.10485760);
 assert.ok(runs.every(r=>r.timing.inferenceSeconds===null&&r.cost.actualUsd===null&&r.sourceOnlyDetails));
 const luna=runs.find(r=>r.id==='luna-decisions-openrouter-native-fresh1-p0');
 assert.equal(luna.returnedModel,'openai/gpt-6-luna-decisions-20261006');
 assert.equal(luna.metrics.all_four,49);
 assert.equal(luna.timing.requests,60);
 const flash=runs.find(r=>r.id==='clef-flash-openrouter-native-fresh3-p2');
 assert.equal(flash.complete,false);assert.equal(flash.valid,59);assert.equal(flash.metrics.all_four,45);
 assert.equal(flash.cost.unknownUpperBoundUsd,.02359296);
 assert.match(flash.resultStatus,/DEV039/);
 const perplexity=runs.find(r=>r.id==='perplexity-decider-native-fresh1-p0');
 assert.equal(perplexity.model,'perplexity/pplx-decider-v1-27b');
 assert.equal(perplexity.returnedModel,'perplexity/pplx-decider-v1-27b-20261001');
 assert.equal(perplexity.provider,'Perplexity');
 assert.equal(perplexity.metrics.all_four,54);
 assert.equal(perplexity.timing.requests,0);
 assert.equal(perplexity.timing.totalSeconds,null);
});
test('bad coverage or ID collisions cannot become partial scored additions',()=>{
 const a=api();
 for(const mutate of [r=>r.runs[0].valid=59,r=>r.runs.find(x=>x.id==='solar-decide-native-fresh3-p2').complete=true,r=>r.runs[0].cost.knownUsd=-1,r=>r.runs[0].sourceRecordSha256='bad',r=>r.runs[1].id=r.runs[0].id,
   r=>r.runs.find(x=>x.id==='luna-decisions-openrouter-native-fresh1-p0').returnedModel='openai/gpt-6-luna-decisions',
   r=>r.runs.find(x=>x.id==='clef-flash-openrouter-native-fresh3-p2').cost.unknownUpperBoundUsd=0,
   r=>r.runs.find(x=>x.id==='clef-flash-openrouter-native-fresh3-p2').valid=60,
   r=>r.runs.find(x=>x.id==='perplexity-decider-native-fresh1-p0').returnedModel='perplexity/pplx-decider-v1-27b',
   r=>r.runs.find(x=>x.id==='perplexity-decider-native-fresh1-p0').timing.requests=60,
   r=>r.runs.splice(r.runs.findIndex(x=>x.id==='perplexity-decider-native-fresh3-p2'),1),
   r=>r.runs.splice(r.runs.findIndex(x=>x.id==='solar-decide-native-fresh1-p0'),1)]){
  const r=structuredClone(report);mutate(r);assert.equal(a.supplementalDecisionRuns(r).length,0);
 }
 assert.equal(a.supplementalDecisionRuns(report,[{id:report.runs[0].id}]).length,0);
});
test('a duplicate OpenRouter repeat cannot replace an earlier run',()=>{
 const a=api(),future=structuredClone(report);
 const previous=future.runs.find(r=>r.id==='clef-openrouter-native-fresh1-p0');
 future.runs.push({...previous,id:'clef-openrouter-native-fresh2-p0',
   experimentId:'clef-openrouter-native-fresh2-p0',parentBaselineId:null,repeatPass:'fresh2'});
 assert.equal(a.supplementalDecisionRuns(future).length,0);
});
test('new native rows classify as decision interfaces without invented training lineage',()=>{
 const c={};vm.runInNewContext(fs.readFileSync(path.join(site,'model-categories.js'),'utf8'),c);
 for(const r of report.runs){const t=c.BenchmarkCategories.classify(r);assert.equal(t.category,'decision');assert.equal(t.interfaceKind,'native');assert.equal(t.trainingLineage,'unknown');}
});
