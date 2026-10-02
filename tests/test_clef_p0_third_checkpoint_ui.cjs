const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const read = name => JSON.parse(fs.readFileSync(path.join(site, name), 'utf8'));
const first = read('gemma26-continuation-findings.json');
const second = read('gemma26-second-continuation-findings.json');
const latest = read('gemma26-postabort-findings.json');
const comparison = read('gemma26-p2-repeat-findings.json');
const checkpoint = read('clef-p0-third-checkpoint.json');

async function render(third = checkpoint, thirdStatus = 200) {
  const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
    'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
    'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
    'repeat-flips', 'repeat-usage-body', 'repeat-clef-third'];
  const elements = new Map(ids.map(id => [id, {innerHTML:'', textContent:'', value:'',
    addEventListener(type, listener) { this[type] = listener; }}]));
  elements.get('repeat-config').value = latest.seriesId;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P2';
  const saved = {
    './gemma26-continuation-findings.json': first,
    './gemma26-second-continuation-findings.json': second,
    './gemma26-postabort-findings.json': latest,
    './gemma26-p2-repeat-findings.json': comparison,
    './clef-p0-third-checkpoint.json': third,
  };
  const fetch = async url => url === './clef-p0-third-checkpoint.json'
    ? {ok: thirdStatus === 200, status: thirdStatus, json: async () => third}
    : {ok: true, status: 200, json: async () => saved[url] || {series:[]}};
  vm.runInNewContext(source, {document:{getElementById:id=>elements.get(id)}, fetch, console},
    {filename:'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  return elements;
}

test('repeat page shows Clef third-P0 coverage and keeps Flash unscored', async () => {
  const panel = (await render()).get('repeat-clef-third').innerHTML;
  assert.match(panel, /Clef has <strong>3 of 9<\/strong> planned runs scored/);
  assert.match(panel, /53\/60/);
  assert.match(panel, /at reported precision/);
  assert.match(panel, /Clef Flash has <strong>2 of 9<\/strong> planned runs scored/);
  assert.match(panel, /one unknown outcome; 59 reviews were never sent/);
  assert.match(panel, /no third score/);
  assert.match(panel, /href="\.\/clef-p0-third-checkpoint\.json"/);
  assert.doesNotMatch(panel, /free allocation|quota|4006/i);
});

test('changed or missing checkpoint cannot display a third score', async () => {
  const altered = structuredClone(checkpoint);
  altered.models['clef-flash'].fresh3P0.score = {allFourCorrect:60};
  const changed = (await render(altered)).get('repeat-clef-third');
  assert.match(changed.textContent, /checkpoint is unavailable/);
  const missing = (await render(null, 404)).get('repeat-clef-third');
  assert.match(missing.textContent, /checkpoint is unavailable/);
});
