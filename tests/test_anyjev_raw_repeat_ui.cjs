const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feedUrl = './anyjev-raw-repeats.json';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function phase(score) {
  return {completionStatus: 'complete',
    score: {denominator: 60, valid: 60, allFour: score,
      fields: {sentiment: score, follow_up_needed: score,
        serious_concern_reported: score, testimonial_potential: score}},
    usage: {requestCount: 60, requestSecondsTotal: 120.5,
      tokens: {input_tokens: 90000, output_tokens: null}, actualCostUsd: null}};
}

function fixture(closed = false) {
  return {configuration: 'anyjev-qwen06-raw',
    displayName: 'AnyJev Qwen3 0.6B · raw native readout',
    method: 'native-output-stability', conditionOrder: ['P0'],
    passOrder: ['original', 'repeat2', 'repeat3'],
    completedConditions: closed ? 3 : 2, plannedConditions: 3, denominator: 60,
    passes: {original: {P0: phase(0)}, repeat2: {P0: phase(0)},
      repeat3: closed ? {P0: phase(0)} : {}},
    threePassSummary: {P0: {allFour: {range: closed ? [0, 0] : null}}},
    pairwiseFlips: [],
    changesAcrossThreePasses: closed ? {P0: {denominator: 60,
      fourFieldVector: ['DEV-001'], excludedIds: [], fields: {sentiment: []}}} : {},
    interpretation: [
      'Matching predictions across passes show observed stability, not correctness.',
      'Historical prompts were reconstructed from saved lengths, not observed hashes.',
      'Client time is not isolated inference time; local hardware cost is unavailable.'],
    missingPasses: closed ? [] : [{pass: 'repeat3', condition: 'P0',
      status: 'claimed_in_progress_or_interrupted'}], partialPasses: []};
}

async function render(feed, status = 200) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const document = {getElementById(id) { return elements.get(id); }};
  const requested = [];
  const fetch = async url => {
    requested.push(url);
    if (url === feedUrl) return {ok: status === 200, status, json: async () => feed};
    return {ok: true, status: 200, json: async () => url === './typesafe-repeats.json'
      ? {series: [{...fixture(false), configuration: 'existing-repeat-fixture'}]} : {series: []}};
  };
  elements.get('repeat-config').value = status === 404 ? 'existing-repeat-fixture' : 'anyjev-qwen06-raw';
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested};
}

test('optional AnyJev feed preserves existing results on 404 but fails on server error', async () => {
  const missing = await render(null, 404);
  assert.equal(missing.requested.filter(url => url === feedUrl).length, 1);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const broken = await render(null, 500);
  assert.match(broken.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});

test('pending native raw pass renders one condition and explicit limitations', async () => {
  const ui = await render(fixture(false));
  assert.match(ui.get('repeat-lead').textContent, /2 of 3 planned native P0 passes/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/class="repeat-bar-row"/g) || []).length, 3);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /Not completed/);
  assert.doesNotMatch(ui.get('repeat-condition').innerHTML, /P1|P2/);
  assert.equal(ui.get('repeat-deltas').innerHTML, '');
  assert.match(ui.get('repeat-interpretation').innerHTML, /not correctness/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not observed hashes/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not isolated inference time/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);
});

test('closed native raw IDs stay plain text without unsupported historical inspect links', async () => {
  const ui = await render(fixture(true));
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>0–0<\/strong>/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-001/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
});
