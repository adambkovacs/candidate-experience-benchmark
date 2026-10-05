const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const analysis = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
const read = name => JSON.parse(fs.readFileSync(path.join(site, name), 'utf8'));
const saved = {
  './gemma26-continuation-findings.json': read('gemma26-continuation-findings.json'),
  './gemma26-second-continuation-findings.json': read('gemma26-second-continuation-findings.json'),
  './gemma26-postabort-findings.json': read('gemma26-postabort-findings.json'),
  './gemma26-p2-repeat-findings.json': read('gemma26-p2-repeat-findings.json'),
};

async function render(current = analysis, currentStatus = 200) {
  const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
    'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
    'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
    'repeat-flips', 'repeat-usage-body', 'repeat-clef-current'];
  const elements = new Map(ids.map(id => [id, {innerHTML:'', textContent:'', value:'',
    addEventListener(type, listener) { this[type] = listener; }}]));
  elements.get('repeat-config').value = saved['./gemma26-postabort-findings.json'].seriesId;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P2';
  const fetch = async url => url === './analysis-refresh.json'
    ? {ok: currentStatus === 200, status: currentStatus, json: async () => current}
    : {ok: true, status: 200, json: async () => saved[url] || {series:[]}};
  vm.runInNewContext(source, {document:{getElementById:id=>elements.get(id)}, fetch, console},
    {filename:'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  return elements.get('repeat-clef-current');
}

test('current Clef matrix renders six condition rows from the analysis feed', async () => {
  const panel = await render();
  const html = panel.innerHTML;
  assert.equal((html.match(/<tr>/g) || []).length, 7); // Header plus six body rows.
  assert.match(html, /Current Clef native-choice repeat status/);
  assert.match(html, /all-four matches out of 60 reviews/);
  assert.match(html, /native choice variant/);
  assert.match(html, /<th scope="row">Clef<\/th><td>P0<\/td>[\s\S]*53\/60[\s\S]*53\/60[\s\S]*53\/60/);
  assert.match(html, /<th scope="row">Clef<\/th><td>P1<\/td>[\s\S]*52\/60[\s\S]*Pending[\s\S]*Pending/);
  assert.match(html, /<th scope="row">Clef<\/th><td>P2<\/td>(?:[\s\S]*Pending){3}/);
  assert.match(html, /<th scope="row">Clef Flash<\/th><td>P1<\/td>(?:[\s\S]*47\/60){3}/);
  assert.match(html, /<th scope="row">Clef Flash<\/th><td>P2<\/td>(?:[\s\S]*46\/60){3}/);
  assert.match(html, /clef-p0-third-checkpoint\.json/);
  assert.match(html, /CLEF_P1_FIRST_PASS_2026-10-05\.md/);
  assert.match(html, /clef-flash-p1-findings\.json/);
  assert.match(html, /clef-flash-p2-findings\.json/);
  assert.doesNotMatch(html, /quota|account|budget/i);
});

test('latest Flash P0 pass stays interrupted and has no third score', async () => {
  const html = (await render()).innerHTML;
  const row = html.match(/<th scope="row">Clef Flash<\/th><td>P0<\/td>([\s\S]*?)<\/tr>/)?.[1] || '';
  assert.match(row, /45\/60/);
  assert.equal((row.match(/45\/60/g) || []).length, 2);
  assert.match(row, /Interrupted/);
  assert.match(row, /2 unknown outcomes; 58 never sent; no score/);
  assert.doesNotMatch(row, /53\/60|46\/60|47\/60/);
});

test('missing or malformed current feed fails visibly', async () => {
  const missing = await render(null, 404);
  assert.match(missing.textContent, /matrix is unavailable because its analysis feed is missing or changed/);

  const malformed = structuredClone(analysis);
  malformed.newerCohorts.latestFlashP0Interruption.score = {allFour:60, denominator:60};
  const changed = await render(malformed);
  assert.match(changed.textContent, /matrix is unavailable because its analysis feed is missing or changed/);
  assert.equal(changed.innerHTML, '');
});

test('extra analysis sources preserve matrix and duplicate review IDs fail visibly', async () => {
  const extended = structuredClone(analysis);
  extended.sources.push({path:'public-site/future-analysis.json',sha256:'a'.repeat(64)});
  assert.match((await render(extended)).innerHTML, /53\/60/);
  const duplicate = structuredClone(analysis);
  duplicate.newerCohorts.latestFlashP0Interruption.neverSentIds[0] = 'DEV-001';
  assert.match((await render(duplicate)).textContent, /matrix is unavailable/);
});
