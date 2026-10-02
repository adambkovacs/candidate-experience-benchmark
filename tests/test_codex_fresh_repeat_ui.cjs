const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feedUrl = './codex-fresh-repeats.json';
const names = [
  'codex-gpt-5.6-luna-xhigh', 'codex-gpt-6-astra-medium',
  'codex-gpt-5.6-terra-low', 'codex-gpt-5.6-terra-medium',
  'codex-gpt-6-sol-low-batch10', 'codex-gpt-6-luna-low-batch10',
];
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function score(n) {
  return {denominator: 60, valid: 60, allFour: n,
    fields: {sentiment: n, follow_up_needed: n,
      serious_concern_reported: n, testimonial_potential: n}};
}

function fresh(configuration, completed = {}) {
  const passes = {fresh1: {}, fresh2: {}, fresh3: {}};
  for (const [pass, conditions] of Object.entries(completed)) {
    for (const [condition, count] of Object.entries(conditions)) {
      passes[pass][condition] = {status: 'completed', score: score(count),
        usage: {requestCount: 6, requestSecondsTotal: 42.5,
          tokens: {input_tokens: 1200, output_tokens: 200}, actualCostUsd: null}};
    }
  }
  const missingPasses = [];
  for (const pass of ['fresh1', 'fresh2', 'fresh3']) {
    for (const condition of ['P0', 'P1', 'P2']) {
      if (!passes[pass][condition]) missingPasses.push({pass, condition, status: 'not_completed'});
    }
  }
  return {schema: 'codex-fresh-repeat-findings-v1', method: 'fresh-matched-three',
    configuration, seriesId: configuration + '-fresh-matched3',
    displayName: configuration + ' · low effort', model: 'gpt-6-sol', effort: 'low',
    servedModel: null, passOrder: ['fresh1', 'fresh2', 'fresh3'],
    conditionOrder: ['P0', 'P1', 'P2'], denominator: 60, plannedConditions: 9,
    completedConditions: 9 - missingPasses.length, missingPasses, passes,
    threePassSummary: Object.fromEntries(['P0', 'P1', 'P2'].map(c => [c, {allFour: {range: null}}])),
    withinPassPromptDeltas: [], pairwiseFlips: [], changesAcrossThreePasses: {}};
}

async function render(freshFeed, status = 200, selected = names[0] + '-fresh-matched3', pricing = {series: []}, cliEstimate = null, pendingPrice = false) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const document = {getElementById(id) { return elements.get(id); }};
  const historical = {...fresh(names[0], {fresh1: {P0: 5}}),
    schema: 'repeat-findings-v1', method: undefined, seriesId: undefined,
    displayName: 'Historical same configuration', passOrder: ['original', 'repeat2', 'repeat3'],
    passes: {original: {P0: {score: score(5), usage: {requestCount: 6,
      cliListPriceEstimateUsd: cliEstimate}}}, repeat2: {}, repeat3: {}}};
  const fetch = async url => {
    requested.push(url);
    if (url === feedUrl) return {ok: status === 200, status, json: async () => freshFeed};
    if (url === './subscription-price-estimates.json') return pendingPrice
      ? new Promise(() => {}) : {ok: true, status: 200, json: async () => pricing};
    return {ok: true, status: 200, json: async () => url === './typesafe-repeats.json'
      ? {series: [historical]} : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console,
    ...(pendingPrice ? {setTimeout: callback => {setImmediate(callback); return 1;},
      clearTimeout() {}} : {})}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  if (pendingPrice) await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested, select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

test('fresh Codex usage shows API-equivalent public-rate estimate and unknown charge', async () => {
  const config = 'codex-gpt-6-sol-low-batch10';
  const key = config + ':fresh1:P0';
  const payload = {schema: 'codex-fresh-repeat-findings-v1',
    series: names.map(name => fresh(name, name === config ? {fresh1: {P0: 55}} : {}))};
  const pricing = {schema: 'subscription-price-estimates-v1',
    repeatPhases: {[key]: {model: 'gpt-6-sol', scope: 'repeat_development_phase',
      estimateUsd: '0.0074333', estimateStatus: 'complete',
      rate: {checkedDate: '2026-10-02',
        sourceUrl: 'https://developers.openai.com/api/docs/models/gpt-6-sol'}}},
    repeatSeries: {[config]: {model: 'gpt-6-sol', totalPhases: 9,
      fullSeriesEstimateUsd: null}}};
  const ui = await render(payload, 200, config + '-fresh-matched3', pricing);
  const html = ui.get('repeat-usage-body').innerHTML;
  assert.match(html, /\$0\.0074333/);
  assert.match(html, /Current public-rate estimate, 2026-10-02/);
  assert.match(html, /Public rate ↗/);
  assert.match(ui.get('repeat-results').innerHTML, /Reasoning tokens are already in output/);
  assert.match(html, /Cache read: Unavailable/);
  assert.match(html, /Unavailable<\/td><td>\$0\.0074333/);
});

test('unpriced current rate retains the saved CLI estimate as a separate figure', async () => {
  const config = names[0];
  const pricing = {schema: 'subscription-price-estimates-v1',
    repeatPhases: {[`${config}:original:P0`]: {model: 'gpt-6-sol',
      scope: 'repeat_development_phase', estimateUsd: null,
      estimateStatus: 'cache_write_duration_unknown',
      rate: {checkedDate: '2026-10-02',
        sourceUrl: 'https://developers.openai.com/api/docs/models/gpt-6-sol'}}}};
  const ui = await render({series: []}, 200, config, pricing, '0.042984');
  const html = ui.get('repeat-usage-body').innerHTML;
  assert.match(html, /Current public-rate estimate.*cache write duration unknown/);
  assert.match(html, /Saved CLI API-equivalent estimate: \$0\.042984/);
});

test('a pending optional price fetch does not hold required repeat results', async () => {
  const ui = await render({schema: 'codex-fresh-repeat-findings-v1',
    series: names.map(name => fresh(name, name === names[0] ? {fresh1: {P0: 35}} : {}))},
  200, names[0] + '-fresh-matched3', {series: []}, null, true);
  assert.match(ui.get('repeat-results').innerHTML, /Model and test setup/);
});

test('six fresh Codex series remain separate from same-ID historical result', async () => {
  const payload = {schema: 'codex-fresh-repeat-findings-v1',
    series: names.map((name, index) => fresh(name, index === 0 ? {fresh1: {P0: 35, P1: 33}} : {}))};
  const ui = await render(payload);
  assert.equal(ui.requested.filter(url => url === feedUrl).length, 1);
  for (const name of names) {
    assert.match(ui.get('repeat-results').innerHTML, new RegExp(name + '-fresh-matched3'));
  }
  assert.match(ui.get('repeat-results').innerHTML, /value="codex-gpt-5\.6-luna-xhigh"/);
  assert.match(ui.get('repeat-results').innerHTML, /value="codex-gpt-5\.6-luna-xhigh-fresh-matched3"/);
  assert.match(ui.get('repeat-lead').textContent, /2 of 9 planned prompt\/pass combinations/);
  assert.match(ui.get('repeat-lead').textContent, /Earlier results remain separate and are not pass one/);
  assert.match(ui.get('repeat-lead').textContent, /served model identity and revision, effective seed and attributable subscription cost are unavailable/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /Fresh pass 1/);
  assert.match(ui.get('repeat-chart').innerHTML, /Not completed/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /42\.5/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);
  ui.select(names[0]);
  assert.match(ui.get('repeat-lead').textContent, /Historical same configuration/);
  assert.doesNotMatch(ui.get('repeat-lead').textContent, /three fresh Codex subscription passes/);
});

test('unclosed fresh slots cannot display stale score, usage or inspect links', async () => {
  const item = fresh(names[0], {fresh1: {P0: 35}});
  item.passes.fresh2.P0 = {status: 'not_completed', score: score(60),
    usage: {requestCount: 6, requestSecondsTotal: 999, actualCostUsd: 100}};
  item.changesAcrossThreePasses.P0 = {denominator: 60, fourFieldVector: ['DEV-001'],
    excludedIds: [], fields: {sentiment: ['DEV-001']}};
  const ui = await render({schema: 'codex-fresh-repeat-findings-v1', series: [item]});
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /<strong>60<small>/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /999\.0|\$100/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-001/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
});

test('missing unpublished feed is optional; server failure is visible', async () => {
  const missing = await render(null, 404, names[0]);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const failed = await render(null, 500, names[0]);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const malformed = await render({series: [fresh(names[0])]}, 200, names[0]);
  assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});

test('feed-supplied three-pass range and flip counts render without invented values', async () => {
  const item = fresh(names[0], {fresh1: {P0: 35}, fresh2: {P0: 36}, fresh3: {P0: 34}});
  item.threePassSummary.P0.allFour.range = [34, 36];
  item.pairwiseFlips = [{condition: 'P0', from: 'fresh1', to: 'fresh2',
    denominator: 60, fourFieldVector: {changed: 1}}];
  item.changesAcrossThreePasses.P0 = {denominator: 60, fourFieldVector: ['DEV-001'],
    excludedIds: [], fields: {sentiment: ['DEV-001']}};
  const ui = await render({schema: 'codex-fresh-repeat-findings-v1', series: [item]});
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>34–36<\/strong>/);
  assert.match(ui.get('repeat-flips').innerHTML, /Fresh pass 1 to Fresh pass 2: 1 \/ 60 changed/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
});

test('closed invalid positions keep the 60-record denominator', async () => {
  const item = fresh(names[0], {fresh1: {P0: 31}});
  item.passes.fresh1.P0.score.valid = 59;
  const ui = await render({schema: 'codex-fresh-repeat-findings-v1', series: [item]});
  assert.match(ui.get('repeat-lead').textContent, /P0 Fresh pass 1: 59\/60 valid responses/);
  assert.match(ui.get('repeat-chart').innerHTML, /<strong>31<small> \/ 60/);
});
