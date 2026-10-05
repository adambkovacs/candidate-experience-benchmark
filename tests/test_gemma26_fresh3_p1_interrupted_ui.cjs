const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const read = name => JSON.parse(fs.readFileSync(path.join(site, name), 'utf8'));
const feeds = Object.fromEntries([
  'gemma26-continuation-findings.json',
  'gemma26-second-continuation-findings.json',
  'gemma26-postabort-findings.json',
  'gemma26-p2-repeat-findings.json',
  'gemma26-fresh3-p0-checkpoint.json',
  'gemma26-fresh3-p1-interrupted-checkpoint.json',
].map(name => [`./${name}`, read(name)]));
const latestId = 'gemma26-on-v2-fresh3-p1-interrupted-checkpoint-v1';
const p0Id = 'gemma26-on-v2-fresh3-p0-checkpoint-v1';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
  'repeat-flips', 'repeat-usage-body'];

async function render(checkpoint = feeds['./gemma26-fresh3-p1-interrupted-checkpoint.json'],
  status = 200, selected = latestId) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    if (url === './gemma26-fresh3-p1-interrupted-checkpoint.json')
      return {ok: status === 200, status, json: async () => checkpoint};
    const feed = feeds[url];
    return feed ? {ok: true, status: 200, json: async () => feed}
      : {ok: true, status: 200, json: async () => ({series: []})};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P1';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

test('latest Gemma entry shows nine descriptive scores and P1 paired changes', async () => {
  const ui = await render();
  const page = ui.get('repeat-results').innerHTML;
  for (const id of [latestId, p0Id,
    feeds['./gemma26-postabort-findings.json'].seriesId])
    assert.ok(page.includes(`value="${id}"`), id);
  assert.match(page, /interrupted P1 checkpoint \(9 of 9\)/);
  assert.match(ui.get('repeat-summary').textContent, /all 9 planned phases/);
  assert.match(ui.get('repeat-summary').textContent, /58, 58 and 57/);
  assert.match(ui.get('repeat-summary').textContent, /60, 60 and 59/);
  assert.match(ui.get('repeat-summary').textContent, /DEV-059/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 9);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>57–58<\/strong>/);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /No full result in this checkpoint/);
  assert.match(ui.get('repeat-flips').innerHTML, /1 \/ 59/);
  assert.match(ui.get('repeat-flips').innerHTML, /0 \/ 59 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-013/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-059/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /gemma26-fresh3-p1-interrupted-checkpoint\.json/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /earlier P0 checkpoint/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /\$0\.01941923 known/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /96,727 reported/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /DEV-059 charge unknown/);
  ui.get('repeat-field').value = 'serious_concern_reported';
  ui.get('repeat-field').change();
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-013/);
  ui.get('repeat-field').value = 'allFour';
  ui.get('repeat-field').change();
  ui.get('repeat-condition').value = 'P0';
  ui.get('repeat-condition').change();
  assert.match(ui.get('repeat-flips').innerHTML, /4 \/ 59/);
  ui.get('repeat-condition').value = 'P2';
  ui.get('repeat-condition').change();
  assert.match(ui.get('repeat-flips').innerHTML, /2 \/ 57/);
  ui.select(p0Id);
  assert.match(ui.get('repeat-summary').textContent, /8 of 9 phases/);
  ui.select(feeds['./gemma26-postabort-findings.json'].seriesId);
  assert.match(ui.get('repeat-summary').textContent, /7 of 9 phases/);
});

test('absent latest feed keeps P0 cutoff; malformed or failed feed fails visibly', async () => {
  const absent = await render(null, 404, p0Id);
  assert.match(absent.get('repeat-summary').textContent, /8 of 9 phases/);
  const failed = await render(null, 500, p0Id);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const sourceFeed = feeds['./gemma26-fresh3-p1-interrupted-checkpoint.json'];
  for (const bad of [
    {...sourceFeed, scoredSeriesConditions: 8},
    {...sourceFeed, conditions: {...sourceFeed.conditions, P1: {
      ...sourceFeed.conditions.P1, failureIdsByPass: {
        ...sourceFeed.conditions.P1.failureIdsByPass, fresh3: []}}}},
  ]) {
    const malformed = await render(bad);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
