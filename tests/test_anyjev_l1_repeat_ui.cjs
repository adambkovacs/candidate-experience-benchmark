const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feedUrl = './anyjev-l1-repeats.json';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function phase(allFour, valid = 60) {
  return {completionStatus: 'complete',
    score: {denominator: 60, valid, allFour,
      fields: {sentiment: allFour, follow_up_needed: allFour,
        serious_concern_reported: allFour, testimonial_potential: allFour}},
    usage: {requestCount: 60, requestSecondsTotal: 125.5,
      modelLoadSeconds: null, inferenceSeconds: null,
      tokens: {input_token_positions: 96000, output_tokens: null}, actualCostUsd: null}};
}

function fixture(closed = false) {
  const first = phase(4);
  first.usage.modelLoadSeconds = 3.2;
  const second = phase(5, 59);
  return {schema: 'anyjev-l1-direct-native-repeat-findings-v1',
    configuration: 'anyjev-qwen06-l1',
    displayName: 'AnyJev Qwen3 0.6B · L1 calibration',
    method: 'native-output-stability', conditionOrder: ['P0'],
    passOrder: ['original', 'repeat2', 'repeat3'],
    completedConditions: closed ? 3 : 2, plannedConditions: 3, denominator: 60,
    passes: {original: {P0: first}, repeat2: {P0: second},
      repeat3: closed ? {P0: phase(3)} : {}},
    threePassSummary: {P0: {allFour: {range: closed ? [3, 5] : null}}},
    pairwiseFlips: closed ? [{condition: 'P0', from: 'original', to: 'repeat2',
      denominator: 59, fourFieldVector: ['DEV-001'], fields: {sentiment: ['DEV-001']}}] : [],
    changesAcrossThreePasses: closed ? {P0: {denominator: 59,
      fourFieldVector: ['DEV-001'], excludedIds: ['DEV-002'],
      fields: {sentiment: ['DEV-001']}}} : {},
    interpretation: [
      'Native L1 applies cyclic option shifts and a calibration.',
      'Matching predictions across passes show observed stability, not correctness.',
      'Client request time includes overhead; isolated inference time is unavailable.'],
    missingPasses: closed ? [] : [{pass: 'repeat3', condition: 'P0', status: 'not_started'}],
    partialPasses: []};
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
      ? {series: [{...fixture(false), configuration: 'existing-repeat-fixture'}]}
      : {series: []}};
  };
  elements.get('repeat-config').value = status === 404 ? 'existing-repeat-fixture' : 'anyjev-qwen06-l1';
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested};
}

test('unpublished L1 feed is optional only on 404', async () => {
  const missing = await render(null, 404);
  assert.equal(missing.requested.filter(url => url === feedUrl).length, 1);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const broken = await render(null, 500);
  assert.match(broken.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});

test('pending L1 third pass shows only completed native P0 scores', async () => {
  const item = fixture(false);
  item.passes.repeat3.P0 = {completionStatus: 'claimed', ...phase(60)};
  item.passes.repeat3.P0.completionStatus = 'claimed';
  item.passes.repeat3.P0.usage.requestSecondsTotal = 999;
  const ui = await render(item);
  assert.match(ui.get('repeat-lead').textContent, /2 of 3 planned native P0 passes/);
  assert.match(ui.get('repeat-lead').textContent, /fits calibration separately in five folds/);
  assert.match(ui.get('repeat-lead').textContent, /its own reference labels are excluded/);
  assert.match(ui.get('repeat-lead').textContent, /Client and pure inference times were not recorded; local cost is unavailable/);
  assert.doesNotMatch(ui.get('repeat-condition').innerHTML, /P1|P2/);
  assert.match(ui.get('repeat-condition').innerHTML, /Native L1 calibration/);
  assert.equal(ui.get('repeat-deltas').innerHTML, '');
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /Not completed/);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /<strong>60<small>/);
  assert.match(ui.get('repeat-lead').textContent, /59\/60 valid responses/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /999\.0/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /125\.5/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Native input positions: 96,000 \(not billed tokens\)/);
});

test('closed L1 three-pass range and comparable flips keep native IDs unlinked', async () => {
  const ui = await render(fixture(true));
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>3–5<\/strong> out of 60/);
  assert.match(ui.get('repeat-flips').innerHTML, /1 \/ 59/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /undefined/);
  ui.get('repeat-field').value = 'sentiment'; ui.get('repeat-field').change();
  assert.match(ui.get('repeat-flips').innerHTML, /1 \/ 59 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /1 comments excluded/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-001/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not correctness/);
});
