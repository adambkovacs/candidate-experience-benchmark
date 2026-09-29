const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const actual = JSON.parse(fs.readFileSync(path.join(site, 'qwen36-off-continuation-findings.json'), 'utf8'));
const url = './qwen36-off-continuation-findings.json';
const id = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-continuation-v1';
const configuration = 'openrouter-paid-qwen36-35b-a3b-off';
const elements = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

const clone = value => JSON.parse(JSON.stringify(value));
const money = value => '$' + Number(value).toLocaleString('en-US',
  {minimumFractionDigits: 2, maximumFractionDigits: 8});

function historical() {
  return {schema: 'repeat-findings-v1', configuration,
    displayName: 'Historical Qwen result', denominator: 60,
    completedConditions: 1, plannedConditions: 9,
    passOrder: ['original', 'repeat2', 'repeat3'], conditionOrder: ['P0', 'P1', 'P2'],
    passes: {original: {P0: {score: actual.series[0].passes.fresh1.P0.score}}, repeat2: {}, repeat3: {}},
    threePassSummary: {}, withinPassPromptDeltas: [], pairwiseFlips: [],
    changesAcrossThreePasses: {}};
}

async function render(payload = actual, status = 200, selected = id) {
  const ui = new Map(elements.map(name => [name, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const document = {getElementById(name) { return ui.get(name); }};
  const fetch = async feed => {
    requested.push(feed);
    if (feed === url) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () => feed === './typesafe-repeats.json'
      ? {series: [historical()]} : {series: []}};
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
  return rows.find(row => row.includes(`<th scope="row">${condition}</th><td>${pass}</td>`));
}

test('descriptive continuation stays separate and displays the first P0 failure and fixed denominator', async () => {
  const ui = await render();
  const series = actual.series[0];
  assert.equal(ui.requested.filter(feed => feed === url).length, 1);
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${configuration}"`));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${id}"`));
  assert.match(ui.get('repeat-interpretation').innerHTML, /Descriptive continuation/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /59 valid outputs and one DEV-006 HTTP 429 service error out of 60/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not a clean matched-three series/);
  assert.match(ui.get('repeat-chart').innerHTML, /P0 Fresh pass 1 All four decisions: 48 out of 60/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, series.completedConditions);
  assert.match(ui.get('repeat-lead').textContent, /Failed or invalid answers remain in the score denominator/);
  assert.match(ui.get('repeat-lead').textContent, /unknown-charge upper bound for DEV-006 is not an invoice charge/);
  assert.match(ui.get('repeat-deltas').innerHTML, /Fresh pass 1 P0 to P1: 59 shared valid of 60; 1 excluded/);
  ui.select(configuration);
  assert.match(ui.get('repeat-lead').textContent, /Historical Qwen result/);
  assert.doesNotMatch(ui.get('repeat-interpretation').innerHTML, /Descriptive continuation/);
});

test('known charges and separate unknown bound appear only for scored slots', async () => {
  const ui = await render();
  const first = actual.series[0].passes.fresh1.P0;
  const row = usageRow(ui, 'P0', 'Fresh pass 1');
  assert.match(row, /<td>60<\/td>/);
  assert.ok(row.includes(first.usage.tokens.prompt_tokens.toLocaleString('en-US')));
  assert.ok(row.includes(money(first.usage.knownCostUsd)));
  assert.ok(row.includes(`Unknown charge up to ${money('0.0299008')}`));
  assert.ok(row.includes(first.usage.requestSecondsTotal.toFixed(1)));
  assert.match(row, /<td>Unavailable<\/td>/);

  const payload = clone(actual);
  payload.series[0].passes.fresh3.P0 = {status: 'not_completed',
    score: {denominator: 60, valid: 60, allFour: 60, fields: {}},
    usage: {requestCount: 60, knownCostUsd: '999.99', requestSecondsTotal: 999.9,
      tokens: {prompt_tokens: 999999, completion_tokens: 999998}}};
  const open = await render(payload);
  const pending = usageRow(open, 'P0', 'Fresh pass 3');
  assert.doesNotMatch(pending, /999|\$999/);
  assert.match(pending, /Unavailable/);
  assert.doesNotMatch(open.get('repeat-chart').innerHTML, /<strong>60<small>/);
});

test('cumulative cost chooses the latest frozen dispatch phase despite object order', async () => {
  const payload = clone(actual);
  const series = payload.series[0];
  series.passes = {fresh3: series.passes.fresh3,
    fresh2: Object.fromEntries(Object.entries(series.passes.fresh2).reverse()),
    fresh1: Object.fromEntries(Object.entries(series.passes.fresh1).reverse())};
  const order = [['fresh1','P1'], ['fresh1','P2'], ['fresh2','P2'],
    ['fresh2','P0'], ['fresh2','P1'], ['fresh3','P1'], ['fresh3','P2'], ['fresh3','P0']];
  const latest = order.map(([pass, condition]) => series.passes[pass]?.[condition])
    .filter(phase => phase?.status === 'completed' && phase.budgetAccountingCumulative).pop();
  assert.ok(latest);
  const ui = await render(payload);
  assert.ok(ui.get('repeat-lead').textContent.includes(money(latest.budgetAccountingCumulative.knownAllAttemptCostUsd)));
  assert.ok(ui.get('repeat-lead').textContent.includes(money('0.0299008')));
});

test('optional 404 is harmless, while 500 and malformed continuation data fail visibly', async () => {
  const missing = await render(null, 404, configuration);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  const failed = await render(null, 500, configuration);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const bad = clone(actual);
  const first = bad.series[0].passes.fresh1.P0;
  const examples = [
    {}, {...bad, schema: 'unexpected'},
    {...bad, series: [{...bad.series[0], seriesId: configuration}]},
    {...bad, series: [{...bad.series[0], method: 'fresh-matched-three'}]},
    {...bad, series: [{...bad.series[0], cleanMatchedThreeEligible: true}]},
    {...bad, series: [{...bad.series[0], passes: {...bad.series[0].passes,
      fresh1: {...bad.series[0].passes.fresh1, P0: {...first,
        score: {...first.score, valid: 60}}}}}]},
    {...bad, series: [{...bad.series[0], passes: {...bad.series[0].passes,
      fresh1: {...bad.series[0].passes.fresh1, P0: {...first,
        usage: {...first.usage, unknownChargeUpperBoundUsd: '0'}}}}}]},
    {...bad, series: [{...bad.series[0], withinPassPromptFlips:
      [{...bad.series[0].withinPassPromptFlips[0], denominator: 60,
        excludedIds: []}]}]},
    {...bad, series: [{...bad.series[0], passes: {...bad.series[0].passes,
      fresh1: {...bad.series[0].passes.fresh1, P1: {...bad.series[0].passes.fresh1.P1,
        status: 'closed_with_service_error'}}}}]},
    {...bad, series: [{...bad.series[0], passes: {...bad.series[0].passes,
      fresh1: {...bad.series[0].passes.fresh1, P1: {...bad.series[0].passes.fresh1.P1,
        budgetAccountingCumulative: {...bad.series[0].passes.fresh1.P1.budgetAccountingCumulative,
          unknownChargeUpperBoundUsd: '0'}}}}}]},
  ];
  for (const payload of examples) {
    const malformed = await render(payload, 200, configuration);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
