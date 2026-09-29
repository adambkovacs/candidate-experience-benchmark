const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const actual = JSON.parse(fs.readFileSync(path.join(site, 'qwen36-off-second-interruption-findings.json'), 'utf8'));
const url = './qwen36-off-second-interruption-findings.json';
const archive = './qwen36-off-continuation-findings.json';
const id = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-two-interruptions-v1';
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

test('final descriptive continuation replaces active six-phase feed and retains two failures', async () => {
  const ui = await render();
  const series = actual.series[0];
  assert.equal(ui.requested.filter(feed => feed === url).length, 1);
  assert.ok(!ui.requested.includes(archive));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${configuration}"`));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${id}"`));
  assert.match(ui.get('repeat-interpretation').innerHTML, /Descriptive continuation after two service errors/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /DEV-006/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /DEV-031/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not a clean matched-three series/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 9);
  assert.equal(series.completedConditions, 9);
  assert.match(ui.get('repeat-lead').textContent, /P0 Fresh pass 1: 59\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /P1 Fresh pass 3: 59\/60 valid responses/);
  assert.match(ui.get('repeat-deltas').innerHTML, /Fresh pass 3 P0 to P1: 59 shared valid of 60; 1 excluded/);
  ui.select(configuration);
  assert.match(ui.get('repeat-lead').textContent, /Historical Qwen result/);
  assert.doesNotMatch(ui.get('repeat-interpretation').innerHTML, /two service errors/);
});

test('known charges and separate per-request unknown bounds remain distinct', async () => {
  const ui = await render();
  const first = actual.series[0].passes.fresh1.P0;
  const failedP1 = actual.series[0].passes.fresh3.P1;
  const firstRow = usageRow(ui, 'P0', 'Fresh pass 1');
  const secondRow = usageRow(ui, 'P1', 'Fresh pass 3');
  const cleanRow = usageRow(ui, 'P2', 'Fresh pass 3');
  assert.ok(firstRow.includes(money(first.usage.knownCostUsd)));
  assert.ok(secondRow.includes(money(failedP1.usage.knownCostUsd)));
  assert.ok(firstRow.includes(`Unknown charge up to ${money('0.0299008')}`));
  assert.ok(secondRow.includes(`Unknown charge up to ${money('0.0299008')}`));
  assert.doesNotMatch(secondRow, /Unknown charge up to \$0\.0598016/);
  assert.doesNotMatch(cleanRow, /Unknown charge up to/);
  assert.match(ui.get('repeat-lead').textContent, /DEV-006 and DEV-031 each retain a separate unknown-charge upper bound/);
  assert.match(ui.get('repeat-lead').textContent, /These bounds are not invoice charges/);
});

test('latest cumulative charges follow frozen phase order despite object order', async () => {
  const payload = clone(actual);
  const series = payload.series[0];
  series.passes = {fresh3: Object.fromEntries(Object.entries(series.passes.fresh3).reverse()),
    fresh2: Object.fromEntries(Object.entries(series.passes.fresh2).reverse()),
    fresh1: Object.fromEntries(Object.entries(series.passes.fresh1).reverse())};
  const final = series.passes.fresh3.P0.budgetAccountingCumulative;
  const ui = await render(payload);
  assert.ok(ui.get('repeat-lead').textContent.includes(money(final.combinedKnownAllAttemptCostUsd)));
  assert.ok(ui.get('repeat-lead').textContent.includes(money(final.combinedUnknownChargeUpperBoundUsd)));
});

test('optional 404 leaves other series; 500 and malformed final feed fail visibly', async () => {
  const missing = await render(null, 404, configuration);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  const failed = await render(null, 500, configuration);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const examples = [];
  let bad = clone(actual); bad.schema = 'unexpected'; examples.push(bad);
  bad = clone(actual); bad.series[0].seriesId = configuration; examples.push(bad);
  bad = clone(actual); bad.series[0].method = 'fresh-matched-three'; examples.push(bad);
  bad = clone(actual); bad.series[0].cleanMatchedThreeEligible = true; examples.push(bad);
  bad = clone(actual); bad.series[0].completedConditions = 8; examples.push(bad);
  bad = clone(actual); bad.series[0].passes.fresh1.P0.score.valid = 60; examples.push(bad);
  bad = clone(actual); bad.series[0].passes.fresh3.P1.score.valid = 60; examples.push(bad);
  bad = clone(actual); bad.series[0].secondInterruption.retainedOldUnknownBounds[1].upperBoundUsd = '0'; examples.push(bad);
  bad = clone(actual); bad.series[0].passes.fresh3.P0.budgetAccountingCumulative.combinedUnknownChargeUpperBoundUsd = '0'; examples.push(bad);
  bad = clone(actual); bad.series[0].withinPassPromptFlips[0].denominator = 60; bad.series[0].withinPassPromptFlips[0].excludedIds = []; examples.push(bad);
  bad = clone(actual); bad.series[0].passes.fresh3.P2.status = 'not_completed'; examples.push(bad);
  for (const payload of examples) {
    const malformed = await render(payload, 200, configuration);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
