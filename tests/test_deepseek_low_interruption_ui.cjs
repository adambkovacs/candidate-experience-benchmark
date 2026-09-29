const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const actual = JSON.parse(fs.readFileSync(path.join(site, 'deepseek-low-continuation-repeats.json'), 'utf8'));
const url = './deepseek-low-continuation-repeats.json';
const id = 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1';
const configuration = 'openrouter-paid-deepseek-v41-flash-low';
const genericId = 'openrouter-paid-deepseek-v41-flash-low-fresh-matched3-v2';
const elements = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];
const clone = value => JSON.parse(JSON.stringify(value));
const generic = {schema: 'additional-hosted-fresh-repeat-findings-v1',
  configuration, seriesId: genericId, method: 'fresh-matched-three',
  displayName: 'DeepSeek low preliminary fresh passes', denominator: 60,
  completedConditions: 2, plannedConditions: 9, passOrder: ['fresh1','fresh2','fresh3'],
  conditionOrder: ['P0','P1','P2'], passes: {fresh1:{},fresh2:{},fresh3:{}},
  threePassSummary: {}, withinPassPromptDeltas: [], pairwiseFlips: [],
  changesAcrossThreePasses: {}};
const historical = {...generic, schema: 'repeat-findings-v1',
  configuration: 'openrouter-paid-deepseek-v41-flash-off',
  seriesId: 'historical-other-configuration', method: 'historical',
  displayName: 'Historical DeepSeek off'};

async function render(payload = actual, status = 200, selected = id) {
  const ui = new Map(elements.map(name => [name, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const document = {getElementById(name) { return ui.get(name); }};
  const fetch = async feed => {
    requested.push(feed);
    if (feed === url) return {ok: status === 200, status, json: async () => payload};
    if (feed === './additional-hosted-fresh-repeats.json') return {ok: true, status: 200,
      json: async () => ({schema: 'additional-hosted-fresh-repeat-findings-v1',
        series: [clone(generic)]})};
    if (feed === './typesafe-repeats.json') return {ok: true, status: 200,
      json: async () => ({series: [clone(historical)]})};
    return {ok: true, status: 200, json: async () => ({series: []})};
  };
  ui.get('repeat-config').value = selected;
  ui.get('repeat-field').value = 'allFour';
  ui.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: name => ui.get(name), requested, select(value) {
    ui.get('repeat-config').value = value;
    ui.get('repeat-config').change();
  }};
}

function usageRow(ui, condition, pass) {
  const rows = ui.get('repeat-usage-body').innerHTML.match(/<tr>.*?<\/tr>/g) || [];
  return rows.find(row => row.includes(`<th scope="row">${condition}</th><td>${pass}`));
}

test('descriptive feed replaces duplicate preliminary low series and keeps other configurations', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(feed => feed === url).length, 1);
  const selector = ui.get('repeat-results').innerHTML;
  assert.match(selector, new RegExp(`value="${id}"`));
  assert.doesNotMatch(selector, new RegExp(`value="${genericId}"`));
  assert.match(selector, /value="openrouter-paid-deepseek-v41-flash-off"/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not a clean matched-three series/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/repeat-bar-row/g) || []).length, 9);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /Stopped: 46 valid, 1 invalid, 2 service errors, 11 unsent; no score/);
  assert.match(ui.get('repeat-lead').textContent, /2 of 9 planned/);
  assert.match(ui.get('repeat-lead').textContent, /P0 Fresh pass 1: 59\/60 valid responses/);
  ui.select('openrouter-paid-deepseek-v41-flash-off');
  assert.match(ui.get('repeat-lead').textContent, /Historical DeepSeek off/);
});

test('P2 stays unscored with partial usage and separate unknown bounds', async () => {
  const ui = await render();
  const row = usageRow(ui, 'P2', 'Fresh pass 1');
  assert.match(row, /stopped, unscored/);
  assert.match(row, /49 attempted/);
  assert.match(row, /Partial; see accounting note above/);
  assert.doesNotMatch(row, /0\.2138112/);
  assert.match(ui.get('repeat-lead').textContent, /DEV-040 and DEV-049 each retain a separate unknown-charge upper bound/);
  assert.match(ui.get('repeat-lead').textContent, /private provider bytes cannot be rechecked here/);
  assert.match(ui.get('repeat-deltas').innerHTML, /Not completed/);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /P2 Fresh pass 1.*?<meter/);
});

test('optional 404 retains preliminary series; 500 and malformed feed fail visibly', async () => {
  const missing = await render(null, 404, genericId);
  assert.match(missing.get('repeat-results').innerHTML, new RegExp(`value="${genericId}"`));
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, new RegExp(`value="${id}"`));
  const failed = await render(null, 500, id);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const bad = [];
  let item = clone(actual); item.schema = 'wrong'; bad.push(item);
  item = clone(actual); item.series[0].seriesId = genericId; bad.push(item);
  item = clone(actual); item.series[0].method = 'fresh-matched-three'; bad.push(item);
  item = clone(actual); item.series[0].cleanMatchedThreeEligible = true; bad.push(item);
  item = clone(actual); item.series[0].passes.fresh1.P2 = {score: {denominator: 60}}; bad.push(item);
  item = clone(actual); item.series[0].secondInterruptionCheckpoint.score = {denominator: 60}; bad.push(item);
  item = clone(actual); item.series[0].secondInterruptionCheckpoint.outcomes.never_sent = 0; bad.push(item);
  item = clone(actual); item.series[0].secondInterruptionCheckpoint.sealedChild.known_actual_usd = '0'; bad.push(item);
  item = clone(actual); item.series[0].budgetAccountingCumulative.combinedUnknownChargeUpperBoundUsd = '0'; bad.push(item);
  item = clone(actual); item.series[0].secondInterruptionCheckpoint.publicSnapshot.sha256 = '0'; bad.push(item);
  for (const payload of bad) {
    const ui = await render(payload, 200, id);
    assert.match(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
