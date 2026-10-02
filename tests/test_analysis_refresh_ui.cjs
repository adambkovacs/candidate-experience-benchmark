const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const site = path.join(__dirname, '../public-site');
const source = fs.readFileSync(path.join(site, 'analysis-refresh.js'), 'utf8');
async function renderState(payload, ok=true) {
  const target = {innerHTML:''};
  const summary = {innerHTML:''};
  const cutoffs = {innerHTML:''};
  vm.runInNewContext(source, {document:{getElementById:id=>({
    'analysis-refresh-table':target,
    'analysis-refresh-summary':summary,
    'analysis-refresh-cutoffs':cutoffs,
  }[id] || null)},fetch:async()=>({ok,json:async()=>payload})});
  await new Promise(resolve=>setImmediate(resolve));
  return {table:target.innerHTML,summary:summary.innerHTML,cutoffs:cutoffs.innerHTML};
}
async function render(payload, ok=true) { return (await renderState(payload,ok)).table; }
test('latest effort table uses source ranges, changed-review counts and nine-run costs', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const html = await render(report);
  assert.match(html,/Sonnet 5.5/);
  assert.equal(report.claude.allThreePassPromptGainCount.P1,0);
  assert.equal(report.claude.allThreePassPromptGainCount.P2,0);
  for(const effort of ['low','medium','high','xhigh']) {
    assert.match(html,new RegExp(`<th scope="row">${effort}</th>`));
    const row=report.sonnet55.byEffort[effort];
    assert.ok(html.includes('$'+Number(row.usage.developmentApiEquivalentUsd).toFixed(3)));
  }
  // Current editorial claims must be reviewed if the source cohort changes.
  assert.ok(Object.values(report.sonnet55.byEffort.xhigh.conditions).every(c=>c.scores.length===3&&c.scores.every(n=>n===58)));
  const page=fs.readFileSync(path.join(site,'index.html'),'utf8');
  assert.match(page,/estimates are not subscription charges/);
  assert.match(page,/same 60 reviews/);
});
test('analysis page shows Gemma composite, Clef and local Qwen as separate cohorts', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const view = await renderState(report);
  assert.match(view.summary,/21 Claude setups/);
  assert.match(view.cutoffs,/Gemma 26B/);
  assert.match(view.cutoffs,/7\/9 conditions scored/);
  assert.match(view.cutoffs,/57, 56, 56 out of 60/);
  assert.match(view.cutoffs,/2 of 57 shared-valid comments changed a decision/);
  assert.match(view.cutoffs,/DEV-005 and DEV-006/);
  assert.match(view.cutoffs,/not a clean matched-three experiment/);
  assert.match(view.cutoffs,/Clef native P0/);
  assert.match(view.cutoffs,/53\/60/);
  assert.match(view.cutoffs,/45\/60/);
  assert.match(view.cutoffs,/two full passes per model/);
  assert.match(view.cutoffs,/Neither model changed a four-field answer among 60 paired comments/);
  assert.match(view.cutoffs,/href="\.\/gemma26-p2-repeat-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-p0-repeat-findings\.json"/);
  assert.doesNotMatch(view.cutoffs,/href="public-site\//);
  assert.match(view.cutoffs,/Small Qwen SDK/);
  assert.match(view.cutoffs,/58 valid and 2 invalid/);
  assert.match(view.cutoffs,/5 valid and 55 invalid/);
  assert.match(view.cutoffs,/separate from hosted Qwen 27B/);
  assert.doesNotMatch(view.cutoffs,/latest Gemma and DeepSeek continuations remain unscored/);
});
test('unavailable or malformed analysis links the report instead of showing invented results', async()=>{
  assert.match(await render(null,false),/could not be loaded/);
  assert.match(await render({}),/could not be loaded/);
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  delete report.newerCohorts.clefNativeP0;
  assert.match(await render(report),/could not be loaded/);
});
