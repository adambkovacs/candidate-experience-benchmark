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
  assert.match(view.cutoffs,/All 9 planned runs now have results, including failed requests in the 60-review totals/);
  assert.match(view.cutoffs,/57, 56, 56 of 60/);
  assert.match(view.cutoffs,/P0 scores are 59, 56, 58 of 60/);
  assert.match(view.cutoffs,/P1 scores are 58, 58, 57 of 60/);
  assert.match(view.cutoffs,/Fresh3 has 59 valid answers and preserves DEV-059/);
  assert.match(view.cutoffs,/On the 59 reviews with valid answers in all three P1 passes/);
  assert.match(view.cutoffs,/each pass matched all four fields on 57, 57, 57/);
  assert.match(view.cutoffs,/lower 60-review score reflects the unavailable DEV-059 answer/);
  assert.doesNotMatch(view.cutoffs,/full fresh3 P0 and P1 results are absent/);
  assert.match(view.cutoffs,/2 of 57 shared-valid reviews changed a decision/);
  assert.match(view.cutoffs,/DEV-005 and DEV-006/);
  assert.match(view.cutoffs,/The series remains interrupted/);
  assert.match(view.cutoffs,/Clef native P0/);
  assert.match(view.cutoffs,/third pass has 2 unknown outcomes and 58 reviews that have not been sent/);
  assert.match(view.cutoffs,/Neither attempt returned a usable answer/);
  assert.match(view.cutoffs,/CLEF_FLASH_P0_SUFFIX_CHECKPOINT_2026-10-05.md/);
  assert.match(view.cutoffs,/53\/60/);
  assert.match(view.cutoffs,/45\/60/);
  assert.match(view.cutoffs,/At the P0 checkpoint, Clef had 3\/9 planned runs scored/);
  assert.match(view.cutoffs,/At the P0 checkpoint, Clef Flash had two completed P0 passes, scoring 45\/60 and 45\/60/);
  assert.match(view.cutoffs,/59 reviews were never sent/);
  assert.match(view.cutoffs,/so it has no third P0 score/);
  assert.match(view.cutoffs,/no changed four-field answer, native probability dictionary or vendor confidence value/);
  assert.match(view.cutoffs,/Clef P1, first pass/);
  assert.match(view.cutoffs,/52\/60 versus 53\/60/);
  assert.match(view.cutoffs,/0\.03472656/);
  assert.match(view.cutoffs,/Clef Flash P1/);
  assert.match(view.cutoffs,/All three passes returned 60 valid answers and scored 47\/60/);
  assert.match(view.cutoffs,/Two reviews became all-four matches \(DEV-027 and DEV-044\) and none lost one/);
  assert.match(view.cutoffs,/P1 passes describe repeat variation/);
  assert.match(view.cutoffs,/Clef Flash P2/);
  assert.match(view.cutoffs,/46, 46, 46 out of 60/);
  assert.match(view.cutoffs,/P2 gained a full match on DEV-058 versus P1, but lost matches on DEV-027 and DEV-032/);
  assert.match(view.cutoffs,/Mistral 119B fresh1 P0/);
  assert.match(view.cutoffs,/40\/60 records, or 40\/55 among valid answers/);
  assert.match(view.cutoffs,/five failures remain in the denominator/);
  assert.match(view.cutoffs,/interrupted single pass, not a completed repeat result/);
  assert.match(view.cutoffs,/Mistral 119B fresh1 P0 attempted all 60 reviews: 55 were valid and 5 failed/);
  assert.match(view.cutoffs,/Its other required conditions remain unfinished/);
  assert.match(view.cutoffs,/DeepSeek low has a separate interrupted result/);
  assert.match(view.cutoffs,/href="\.\/gemma26-p2-repeat-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/gemma26-fresh3-p1-interrupted-checkpoint\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-p0-repeat-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-p0-third-checkpoint\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-flash-p1-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/mistral119-fresh1-p0-findings\.json"/);
  assert.doesNotMatch(view.cutoffs,/href="public-site\//);
  assert.match(view.cutoffs,/Qwen1.7B, first pass/);
  assert.match(view.cutoffs,/base task scored 24\/60, classifier instructions 12\/60, and decision rules 8\/60/);
  assert.match(view.cutoffs,/P0, P1 and P2 each need one final pass/);
  assert.match(view.cutoffs,/30 of the 58 reviews/);
  assert.match(view.cutoffs,/23 of 60 reviews changed a label/);
  assert.match(view.cutoffs,/11 of 60 reviews changing a label/);
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
