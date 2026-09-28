const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const actual = JSON.parse(fs.readFileSync(path.join(site, 'deepseek-fresh-repeats.json'), 'utf8'));
const feedUrl = './deepseek-fresh-repeats.json';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function clone(value) { return JSON.parse(JSON.stringify(value)); }

function historical() {
  const item = actual.series[0];
  return {schema: 'repeat-findings-v1', configuration: item.configuration,
    displayName: 'Historical DeepSeek result', denominator: 60,
    completedConditions: 1, plannedConditions: 9,
    passOrder: ['original', 'repeat2', 'repeat3'], conditionOrder: ['P0', 'P1', 'P2'],
    passes: {original: {P0: {score: item.passes.fresh1.P0.score}}, repeat2: {}, repeat3: {}},
    threePassSummary: {}, withinPassPromptDeltas: [], pairwiseFlips: [],
    changesAcrossThreePasses: {}};
}

async function render(payload = actual, status = 200, selected = actual.series[0].seriesId) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    requested.push(url);
    if (url === feedUrl) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () => url === './typesafe-repeats.json'
      ? {series: [historical()]} : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested, select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

function usageRow(ui, condition, pass) {
  const rows = ui.get('repeat-usage-body').innerHTML.match(/<tr>.*?<\/tr>/g) || [];
  return rows.find(row => row.includes(`<th scope="row">${condition}</th><td>${pass}</td>`));
}

test('actual DeepSeek fresh feed is separate from historical same-ID result and shows only closed scores', async () => {
  const item = actual.series[0];
  assert.equal(actual.schema, 'deepseek-fresh-repeat-findings-v1');
  assert.equal(item.completedConditions, 2);
  const ui = await render();
  assert.equal(ui.requested.filter(url => url === feedUrl).length, 1);
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${item.configuration}"`));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${item.seriesId}"`));
  assert.match(ui.get('repeat-lead').textContent, /2 of 9 planned prompt\/pass combinations/);
  assert.match(ui.get('repeat-lead').textContent, /Earlier results remain separate and are not pass one/);
  assert.match(ui.get('repeat-lead').textContent, /Costs are provider-reported charges/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /P0 Fresh pass 1 All four decisions: 48 out of 60/);
  assert.match(ui.get('repeat-chart').innerHTML, /P1 Fresh pass 1 All four decisions: 47 out of 60/);
  assert.match(ui.get('repeat-chart').innerHTML, /Not completed/);
  ui.select(item.configuration);
  assert.match(ui.get('repeat-lead').textContent, /Historical DeepSeek result/);
  assert.doesNotMatch(ui.get('repeat-lead').textContent, /three fresh hosted passes/);
});

test('actual provider tokens, charges, and client duration appear in closed development rows', async () => {
  const ui = await render();
  for (const condition of ['P0', 'P1']) {
    const usage = actual.series[0].passes.fresh1[condition].usage;
    const row = usageRow(ui, condition, 'Fresh pass 1');
    assert.ok(row, `${condition} development usage row exists`);
    assert.ok(row.includes('>60</td>'), `${condition} request count`);
    assert.ok(row.includes(usage.tokens.prompt_tokens.toLocaleString('en-US')), `${condition} prompt tokens`);
    assert.ok(row.includes(usage.tokens.completion_tokens.toLocaleString('en-US')), `${condition} completion tokens`);
    const cost = '$' + Number(usage.actualCostUsd).toLocaleString('en-US',
      {minimumFractionDigits: 2, maximumFractionDigits: 8});
    assert.ok(row.includes(cost), `${condition} observed provider charge`);
    assert.ok(row.includes(usage.requestSecondsTotal.toFixed(1)), `${condition} client HTTP seconds`);
    assert.match(row, /<td>Unavailable<\/td>/, `${condition} has no invented token-price estimate`);
  }
  assert.match(usageRow(ui, 'P2', 'Fresh pass 1'), /Unavailable/);
});

test('an unclosed slot cannot expose stale score, tokens, charge, or duration', async () => {
  const payload = clone(actual);
  payload.series[0].passes.fresh1.P2 = {status: 'not_completed',
    score: {denominator: 60, valid: 60, allFour: 60, fields: {}},
    usage: {requestCount: 60, requestSecondsTotal: 999.9,
      tokens: {prompt_tokens: 999999, completion_tokens: 999998}, actualCostUsd: '999.99'}};
  const ui = await render(payload);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /<strong>60<small>/);
  const row = usageRow(ui, 'P2', 'Fresh pass 1');
  assert.ok(row);
  assert.doesNotMatch(row, /999|\$999/);
  assert.match(row, /Unavailable/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
});

test('optional 404 remains usable; 500 and malformed DeepSeek payloads fail visibly', async () => {
  const missing = await render(null, 404, actual.series[0].configuration);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const failed = await render(null, 500, actual.series[0].configuration);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  for (const payload of [
    {series: [actual.series[0]]},
    {...actual, schema: 'unexpected'},
    {...actual, series: [{...actual.series[0], seriesId: 'historical-id'}]},
    {...actual, series: [{...actual.series[0], method: 'historical'}]},
  ]) {
    const malformed = await render(payload, 200, actual.series[0].configuration);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
