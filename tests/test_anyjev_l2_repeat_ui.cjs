const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feedUrl = './anyjev-l2-repeats.json';
const configuration = 'anyjev-qwen06-native-l2-outer-cv5-hf517-adapter-v1';
const schema = 'anyjev-l2-native-repeat-findings-v1';
const passes = ['original', 'repeat2', 'repeat3'];
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function phase(score, valid = 60) {
  return {completionStatus: 'complete', score: {denominator: 60, valid, allFour: score,
    fields: {sentiment: score, follow_up_needed: score,
      serious_concern_reported: score, testimonial_potential: score}},
  usage: {requestCount: 60, requestSecondsTotal: 120.25, inferenceSeconds: null,
    tokens: {input_tokens: null, output_tokens: null}, actualCostUsd: null}};
}

function fixture(closed) {
  const values = [4, 5, 3];
  return {schema, configuration, displayName: 'AnyJev Qwen3 0.6B · native L2 outer CV5',
    method: 'native-output-stability', conditionOrder: ['P0'], passOrder: passes,
    completedConditions: closed, plannedConditions: 3, denominator: 60,
    passes: Object.fromEntries(passes.map((name, index) => [name,
      index < closed ? {P0: phase(values[index], index === 1 ? 59 : 60)} : {}])),
    missingPasses: passes.slice(closed).map(name => ({pass: name, condition: 'P0', status: 'not_completed'})),
    threePassSummary: {P0: {allFour: {range: closed === 3 ? [3, 5] : null}}},
    pairwiseFlips: closed >= 2 ? [{condition: 'P0', from: 'original', to: 'repeat2',
      denominator: 59, excludedIds: ['DEV-002'],
      fourFieldVector: {changed: 1, rate: 1 / 59, caseIds: ['DEV-001']},
      sentiment: {changed: 1, rate: 1 / 59, caseIds: ['DEV-001']}}] : [],
    changesAcrossThreePasses: closed === 3 ? {P0: {denominator: 59,
      fourFieldVector: ['DEV-001'], excludedIds: ['DEV-002'], fields: {sentiment: ['DEV-001']}}} : {},
    interpretation: ['The historical pass used the staged native procedure.']};
}

async function render(feed, status = 200) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const requested = [];
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    requested.push(url);
    if (url === feedUrl) return {ok: status === 200, status, json: async () => feed};
    return {ok: true, status: 200, json: async () => url === './typesafe-repeats.json'
      ? {series: [{...fixture(1), schema: 'existing-repeat-fixture', configuration: 'existing-repeat-fixture'}]}
      : {series: []}};
  };
  elements.get('repeat-config').value = status === 404 ? 'existing-repeat-fixture' : configuration;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested};
}

test('L2 feed is optional on 404 while server and schema errors remain visible', async () => {
  const missing = await render(null, 404);
  assert.equal(missing.requested.filter(url => url === feedUrl).length, 1);
  assert.match(missing.get('repeat-results').innerHTML, /existing-repeat-fixture/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  for (const [feed, status] of [[null, 500], [{schema: 'wrong'}, 200], [null, 200]]) {
    const broken = await render(feed, status);
    assert.match(broken.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});

for (const closed of [1, 2, 3]) {
  test(`L2 ${closed}-pass view shows only closed P0 scores and honest usage`, async () => {
    const ui = await render(fixture(closed));
    assert.match(ui.get('repeat-lead').textContent, new RegExp(`${closed} of 3 planned native P0 passes`));
    assert.match(ui.get('repeat-lead').textContent, /historical pass used the staged procedure/);
    assert.match(ui.get('repeat-lead').textContent, /Client time includes local overhead/);
    assert.match(ui.get('repeat-condition').innerHTML, /Native L2 calibration/);
    assert.doesNotMatch(ui.get('repeat-condition').innerHTML, /P1|P2/);
    assert.match(ui.get('repeat-delta-intro').textContent, /P1 and P2 chat prompt variants do not apply/);
    assert.equal(ui.get('repeat-deltas').innerHTML, '');
    const chart = ui.get('repeat-chart').innerHTML;
    assert.equal((chart.match(/<meter/g) || []).length, closed);
    assert.match(chart, /Historical pass/);
    assert.match(chart, /Repeat 2/);
    assert.match(chart, /Repeat 3/);
    assert.equal((chart.match(/Not completed/g) || []).length, 3 - closed);
    assert.match(ui.get('repeat-usage-body').innerHTML, /120\.3/);
    assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);
    assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /\$0\.00/);
    assert.equal((ui.get('repeat-usage-body').innerHTML.match(/120\.3/g) || []).length, closed);
    if (closed < 3) assert.match(chart, /Three-pass range unavailable/);
    else assert.match(chart, /Three-pass range: <strong>3–5<\/strong>/);
  });
}

test('L2 paired flips use shared-valid fields and native IDs remain plain text', async () => {
  const ui = await render(fixture(3));
  ui.get('repeat-field').value = 'sentiment';
  ui.get('repeat-field').change();
  const flips = ui.get('repeat-flips').innerHTML;
  assert.match(flips, /Historical pass to Repeat 2: 1 \/ 59 changed/);
  assert.match(flips, /1 \/ 59<\/strong> comparable comments changed/);
  assert.match(flips, /1 comments excluded/);
  assert.match(flips, /DEV-001/);
  assert.doesNotMatch(flips, /undefined|#inspect|<a\s/);
});
