const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const read = name => JSON.parse(fs.readFileSync(path.join(site, name), 'utf8'));
const feeds = {
  './gemma26-continuation-findings.json': read('gemma26-continuation-findings.json'),
  './gemma26-second-continuation-findings.json': read('gemma26-second-continuation-findings.json'),
  './gemma26-postabort-findings.json': read('gemma26-postabort-findings.json'),
  './gemma26-p2-repeat-findings.json': read('gemma26-p2-repeat-findings.json'),
  './gemma26-fresh3-p0-checkpoint.json': read('gemma26-fresh3-p0-checkpoint.json'),
};
const latestId = 'gemma26-on-v2-fresh3-p0-checkpoint-v1';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
  'repeat-flips', 'repeat-usage-body'];

async function render(checkpoint = feeds['./gemma26-fresh3-p0-checkpoint.json'], status = 200,
  selected = latestId) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    if (url === './gemma26-fresh3-p0-checkpoint.json')
      return {ok: status === 200, status, json: async () => checkpoint};
    const feed = feeds[url];
    return feed ? {ok: true, status: 200, json: async () => feed}
      : {ok: true, status: 200, json: async () => ({series: []})};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

test('P0 checkpoint adds eight scored phases and preserves three historical cutoffs', async () => {
  const ui = await render();
  const page = ui.get('repeat-results').innerHTML;
  for (const id of [latestId, ...['gemma26-continuation-findings.json',
    'gemma26-second-continuation-findings.json', 'gemma26-postabort-findings.json'].map(
    name => feeds[`./${name}`].seriesId)]) assert.ok(page.includes(`value="${id}"`), id);
  assert.match(page, /P0 checkpoint \(8 of 9\)/);
  assert.match(ui.get('repeat-summary').textContent, /8 of 9 phases/);
  assert.match(ui.get('repeat-summary').textContent, /59, 56 and 58/);
  assert.match(ui.get('repeat-summary').textContent, /60, 59 and 60/);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>56–59<\/strong>/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 8);
  assert.match(ui.get('repeat-chart').innerHTML, /No full result in this checkpoint/);
  assert.match(ui.get('repeat-flips').innerHTML, /4 \/ 59/);
  assert.match(ui.get('repeat-flips').innerHTML, /4 \/ 59 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /3 \/ 59 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /1 \/ 59 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-002/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /gemma26-fresh3-p0-checkpoint\.json/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /earlier P2 cutoff/);
  assert.doesNotMatch(ui.get('repeat-interpretation').innerHTML, /P1 remains unsent/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /\$0\.01918032 reported/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /87,568 reported/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /provider bill unavailable/);
  ui.get('repeat-field').value = 'sentiment';
  ui.get('repeat-field').change();
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-005/);
  assert.match(ui.get('repeat-flips').innerHTML, /2 \/ 59 changed/);
  ui.select(feeds['./gemma26-postabort-findings.json'].seriesId);
  assert.match(ui.get('repeat-summary').textContent, /7 of 9 phases/);
  assert.match(ui.get('repeat-chart').innerHTML, /Not sent/);
});

test('missing checkpoint preserves prior cutoff; corrupt checkpoint fails visibly', async () => {
  const prior = feeds['./gemma26-postabort-findings.json'].seriesId;
  const absent = await render(null, 404, prior);
  assert.match(absent.get('repeat-summary').textContent, /7 of 9 phases/);
  const failed = await render(null, 500, prior);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const sourceFeed = feeds['./gemma26-fresh3-p0-checkpoint.json'];
  for (const bad of [
    {...sourceFeed, scoredSeriesConditions: 9},
    {...sourceFeed, conditions: {P0: {...sourceFeed.conditions.P0,
      allThreeSharedValid: {...sourceFeed.conditions.P0.allThreeSharedValid, denominator: 60}}}},
  ]) {
    const malformed = await render(bad);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
