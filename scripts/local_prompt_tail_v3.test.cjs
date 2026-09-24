const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const runner=require('./local_prompt_tail_v3.cjs');
const root=path.resolve(__dirname,'..');
const m=JSON.parse(fs.readFileSync(path.join(root,'results/local-prompt-tail-v3/manifest.json')));

test('exact ten-condition tail matches frozen source records',()=>{
  const source=runner.checkSource(m);
  assert.equal(m.conditions.length,10);
  for(const c of m.conditions){
    assert.equal(source[c.configuration].records.filter(x=>x.variant===c.variant).length,60);
  }
  assert.equal(m.reference_labels_read,false);
});

test('first tail condition requires completed scoped P1 predecessor',()=>{
  if(fs.existsSync(path.join(root,m.predecessor.output_dir,'development.terminal.json')))return;
  const source=runner.checkSource(m);
  assert.throws(()=>runner.checkPredecessor(m,source,0),/ENOENT/);
});

test('unscheduled condition cannot be selected',()=>{
  assert.equal(runner.conditionIndex(m,'qwen3.5-4b-sdk-thinking-on','P2'),-1);
  assert.equal(runner.conditionIndex(m,'qwen3.5-4b-sdk-thinking-off','P1'),0);
});

test('unreviewed execution is refused before a request',()=>{
  assert.throws(()=>runner.reviewCheck(m,m.conditions[0],'smoke',{},{}));
});

test('hosted route admission requires a fresh exact zero-route observation',()=>{
  const c=m.conditions[0],now=Date.parse('2026-09-24T22:00:00Z');
  const valid={configuration:c.configuration,exact_model:c.exact_hosted_model,
    exact_routes:[],source:'https://openrouter.ai/api/v1/models',checked_utc:'2026-09-24T21:00:00Z'};
  assert.doesNotThrow(()=>runner.validateRouteEvidence(c,valid,now));
  assert.throws(()=>runner.validateRouteEvidence(c,{...valid,exact_routes:['provider/model']},now));
  assert.throws(()=>runner.validateRouteEvidence(c,{...valid,checked_utc:'2026-09-23T20:00:00Z'},now));
  assert.throws(()=>runner.validateRouteEvidence(c,{...valid,configuration:m.conditions[2].configuration},now));
});
