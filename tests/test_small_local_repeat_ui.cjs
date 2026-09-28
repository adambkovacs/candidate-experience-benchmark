const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const localUrl = './small-local-repeats.json';
const ids = [
  'repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro',
  'repeat-deltas', 'repeat-flips', 'repeat-usage-body',
];
const names = [
  'gemma4-e2b-sdk-thinking-off', 'gemma4-e2b-sdk-thinking-on',
  'gemma4-e4b-sdk-thinking-off', 'gemma4-e4b-sdk-thinking-on',
  'qwen3.5-4b-sdk-thinking-off',
];

function score(n) {
  return {denominator: 60, valid: 60, allFour: n,
    fields: {sentiment: n, follow_up_needed: n,
      serious_concern_reported: n, testimonial_potential: n}};
}

function series(configuration, completed = {}) {
  const passes = {fresh1: {}, fresh2: {}, fresh3: {}};
  for (const [pass, conditions] of Object.entries(completed)) {
    for (const [condition, count] of Object.entries(conditions)) {
      passes[pass][condition] = {completionStatus: 'complete', score: score(count),
        usage: {requestCount: 60, clientRequestSecondsTotal: 42.3,
          timeBasis: 'client_observed_wall_clock',
          tokens: {input_tokens: 97000, output_tokens: 2000}, actualCostUsd: null}};
    }
  }
  return {configuration, method: 'fresh-matched-local-output-stability',
    completedConditions: Object.values(completed).reduce((n, x) => n + Object.keys(x).length, 0),
    plannedConditions: 9, denominator: 60, passes,
    threePassSummary: {P0: {allFour: {range: null}}, P1: {allFour: {range: null}},
      P2: {allFour: {range: null}}}, pairwiseFlips: [], changesAcrossThreePasses: {},
    historicalStatus: 'observational_not_part_of_fresh_matched_three',
    missingPasses: [], partialPasses: []};
}

async function render(localFeed, status = 200, existingFeed = {series: []}) {
  const elements = new Map(ids.map(id => [id, {
    innerHTML: '', textContent: '', value: '',
    addEventListener(type, listener) { this[type] = listener; },
  }]));
  const document = {getElementById(id) { return elements.get(id); }};
  const requested = [];
  const fetch = async url => {
    requested.push(url);
    if (url === localUrl) return {ok: status === 200, status,
      json: async () => localFeed};
    return {ok: true, status: 200, json: async () =>
      url === './typesafe-repeats.json' ? existingFeed : {series: []}};
  };
  elements.get('repeat-config').value = names[0];
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested};
}

test('five local configurations show fresh passes with closed-only scores', async () => {
  const payload = {series: names.map((name, i) =>
    series(name, i === 0 ? {fresh1: {P0: 35, P1: 33}} : {}))};
  payload.series[0].passes.fresh2.P2 = {completionStatus: 'claimed', score: score(60),
    usage: {requestCount: 60, clientRequestSecondsTotal: 999}};
  const ui = await render(payload);
  assert.equal(ui.requested.filter(url => url === localUrl).length, 1);
  for (const name of names) assert.match(ui.get('repeat-results').innerHTML, new RegExp(name));
  assert.match(ui.get('repeat-lead').textContent, /2 of 9 planned prompt\/pass combinations/);
  assert.match(ui.get('repeat-lead').textContent, /three fresh local passes/);
  assert.match(ui.get('repeat-lead').textContent, /Earlier local results are observational/);
  assert.match(ui.get('repeat-lead').textContent, /loaded engine version, model load time and local cost are unknown/);
  const chart = ui.get('repeat-chart').innerHTML;
  assert.equal((chart.match(/class="repeat-bar-row"/g) || []).length, 9);
  assert.match(chart, /Fresh pass 1/);
  assert.match(chart, /Fresh pass 3/);
  assert.doesNotMatch(chart, />Pass 1</);
  assert.match(chart, /Not completed/);
  assert.equal((chart.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-deltas').innerHTML, /<td>-2<\/td>/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /42\.3/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);
});

test('three-pass local changes render only when the feed supplies them', async () => {
  const item = series(names[0], {fresh1: {P0: 35}, fresh2: {P0: 36}, fresh3: {P0: 34}});
  item.threePassSummary.P0.allFour.range = [34, 36];
  item.changesAcrossThreePasses.P0 = {denominator: 60, fourFieldVector: ['DEV-001'],
    excludedIds: [], fields: {sentiment: ['DEV-001']}};
  item.pairwiseFlips = [{condition: 'P0', from: 'fresh1', to: 'fresh2',
    denominator: 60, fourFieldVector: {changed: 1}}];
  const ui = await render({series: [item]});
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>34–36<\/strong>/);
  assert.match(ui.get('repeat-flips').innerHTML, /Fresh pass 1 to Fresh pass 2: 1 \/ 60 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-001/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
});

test('only an unpublished local feed 404 is optional', async () => {
  const old = {series: [series(names[0], {fresh1: {P0: 35}})]};
  const missing = await render(null, 404, old);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const unavailable = await render(null, 500, old);
  assert.match(unavailable.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});
