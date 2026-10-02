const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const site = path.join(__dirname, '../public-site');
const source = fs.readFileSync(path.join(site, 'analysis-refresh.js'), 'utf8');
async function render(payload, ok=true) {
  const target = {innerHTML:''};
  const extra = {innerHTML:''};
  vm.runInNewContext(source, {document:{getElementById:id=>id === 'analysis-refresh-table' ? target : extra},fetch:async()=>({ok,json:async()=>payload})});
  await new Promise(resolve=>setImmediate(resolve));
  return target.innerHTML;
}
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
test('unavailable or malformed analysis links the report instead of showing invented results', async()=>{
  assert.match(await render(null,false),/could not be loaded/);
  assert.match(await render({}),/could not be loaded/);
});
