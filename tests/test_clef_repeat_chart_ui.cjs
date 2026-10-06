const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '../public-site');
const source = fs.readFileSync(path.join(site, 'clef-repeat-chart.js'), 'utf8');
const report = JSON.parse(fs.readFileSync(path.join(site, 'clef-closed-repeat-findings.json'), 'utf8'));

async function render(data = report, ok = true) {
  const host = { innerHTML: '<p>Fallback evidence text</p>' };
  let url;
  vm.runInNewContext(source, {
    document: { getElementById: id => id === 'clef-repeat-chart' ? host : null },
    fetch: async (requested) => { url = requested; return { ok, json: async () => data }; },
  });
  await new Promise(resolve => setImmediate(resolve));
  return { html: host.innerHTML, url };
}

test('the nine cells retain clean scores and separate interruption states', async () => {
  const { html, url } = await render();
  assert.equal(url, './clef-closed-repeat-findings.json');
  assert.match(html, /<table>/);
  assert.match(html, /<th scope="row">/);
  assert.match(html, /<th scope="col">Pass 3<\/th>/);
  assert.match(html, /role="region"[^>]+tabindex="0"/);
  assert.equal((html.match(/class="clef-repeat-track"/g) || []).length, 7);
  assert.equal((html.match(/class="clef-repeat-interrupted"/g) || []).length, 2);
  for (const [score, count] of [[53, 3], [52, 1], [51, 2], [49, 1]]) {
    assert.equal((html.match(new RegExp(`<strong>${score}<span> \/ 60<\/span><\/strong>`, 'g')) || []).length, count);
  }
  assert.match(html, /59 valid · 1 unknown/);
  assert.match(html, /48 known four-label matches/);
  assert.match(html, /1 unknown · 59 not sent/);
  assert.doesNotMatch(html, /<strong>0<span> \/ 60/);
  assert.equal((html.match(/<strong>Interrupted<\/strong>/g) || []).length, 2);
  assert.match(html, /Seven full runs\. Two interrupted\./);
  assert.match(html, /all four answers matched the provisional reference, out of the same 60 reviews/);
  assert.match(html, /P0 stayed fixed/);
  assert.match(html, /P1 changed once/);
  assert.match(html, /Only one P2 run returned all 60 answers/);
  assert.match(html, /The other two were interrupted/);
  assert.match(html, /Source data and per-run evidence/);
  assert.match(html, /href="\.\/clef-closed-repeat-findings\.json"/);
});

test('changed or unavailable evidence leaves the fallback intact', async () => {
  const stale = structuredClone(report);
  stale.cells.find(c => c.condition === 'P2' && c.repeat === 'fresh3').agreementOf60 = 0;
  assert.equal((await render(stale)).html, '<p>Fallback evidence text</p>');
  assert.equal((await render(report, false)).html, '<p>Fallback evidence text</p>');
  const incomplete = structuredClone(report);
  incomplete.cells.pop();
  assert.equal((await render(incomplete)).html, '<p>Fallback evidence text</p>');
  const changedFlip = structuredClone(report);
  changedFlip.cleanRepeatFlips.find(f => f.condition === 'P1' && f.left === 'fresh1').anyFieldChanged = 2;
  assert.equal((await render(changedFlip)).html, '<p>Fallback evidence text</p>');
});

test('mobile and reduced-motion rules remain scoped to the component', () => {
  const css = fs.readFileSync(path.join(site, 'clef-repeat-chart.css'), 'utf8');
  assert.match(css, /\.clef-repeat-scroll\s*\{[^}]*overflow-x:\s*auto/);
  assert.match(css, /@media \(max-width: 700px\)/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /\.clef-repeat-scroll:focus-visible/);
});
