const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const feeds = [
  'typesafe-repeats.json', 'repeats.json', 'hosted-repeats.json',
  'claude-repeats.json', 'claude-roster-repeats.json',
  'gemini-repeats.json', 'haiku-fresh-matched3.json', 'laya-repeats.json', 'semif-repeats.json',
];

async function renderWith(payloads) {
  const elements = new Map();
  for (const id of [
    'repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
    'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart', 'repeat-delta-title',
    'repeat-delta-intro', 'repeat-deltas', 'repeat-flips', 'repeat-usage-body',
  ]) elements.set(id, {innerHTML: '', textContent: '', value: '', addEventListener(type, fn) { this[type] = fn; }});
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    const index = feeds.indexOf(url.slice(2));
    return index < 0 ? {ok: false, status: 404} : {ok: true, status: 200, json: async () => payloads[index]};
  };
  elements.get('repeat-config').value = (payloads[0].series || [payloads[0]])[0].configuration;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {element: id => elements.get(id), select(configuration) {
    elements.get('repeat-config').value = configuration;
    elements.get('repeat-config').change();
  }};
}

function nativeSeries() {
  const score = {allFour: 50, fields: Object.fromEntries(['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'].map(field => [field, 52])), valid: 60};
  const phase = {completionStatus: 'complete', score, usage: {requestCount: 60}};
  return {
    configuration: 'laya-native-fixture', displayName: 'Laya native P0',
    method: 'native-output-stability', conditionOrder: ['P0'],
    completedConditions: 3, plannedConditions: 3, denominator: 60,
    passes: {original: {P0: phase}, repeat2: {P0: phase}, repeat3: {P0: phase}},
    threePassSummary: {P0: {allFour: {range: [50, 50]}, fields: {sentiment: {range: [52, 52]}}}},
    changesAcrossThreePasses: {P0: {denominator: 60, fourFieldVector: [], excludedIds: [], fields: {sentiment: []}}},
    pairwiseFlips: [], withinPassPromptDeltas: [],
  };
}

test('native P0 series has one condition, three passes, and no missing prompt variants', async () => {
  const ui = await renderWith([{series: [nativeSeries()]}, ...feeds.slice(1).map(() => ({series: []}))]);
  assert.match(ui.element('repeat-lead').textContent, /3 of 3 planned native P0 passes/);
  assert.match(ui.element('repeat-chart').innerHTML, /P0 <span>Native output<\/span>/);
  assert.equal((ui.element('repeat-chart').innerHTML.match(/class="repeat-bar-row"/g) || []).length, 3);
  assert.doesNotMatch(ui.element('repeat-chart').innerHTML, /P1|P2|Not completed/);
  assert.match(ui.element('repeat-condition').innerHTML, /P0: Native output/);
  assert.equal(ui.element('repeat-condition-label').textContent, 'Native condition');
  assert.doesNotMatch(ui.element('repeat-condition').innerHTML, /P1|P2/);
  assert.match(ui.element('repeat-delta-intro').textContent, /variants do not apply/);
  assert.equal(ui.element('repeat-deltas').innerHTML, '');
  assert.equal((ui.element('repeat-usage-body').innerHTML.match(/<tr>/g) || []).length, 3);
});

test('current published repeat feeds retain all series and three-condition layout', async () => {
  const payloads = feeds.map(file => JSON.parse(fs.readFileSync(path.join(site, file), 'utf8')));
  const series = payloads.flatMap(payload => payload.series || [payload]);
  assert.ok(series.length >= 48);
  const ui = await renderWith(payloads);
  for (const item of series.filter(item => item.method !== 'native-output-stability')) {
    ui.select(item.configuration);
    assert.match(ui.element('repeat-chart').innerHTML, /P0 <span>/);
    assert.match(ui.element('repeat-chart').innerHTML, /P1 <span>/);
    assert.match(ui.element('repeat-chart').innerHTML, /P2 <span>/);
    assert.match(ui.element('repeat-condition').innerHTML, /P0:/);
    assert.match(ui.element('repeat-condition').innerHTML, /P2:/);
    assert.match(ui.element('repeat-deltas').innerHTML, /<th scope="row">P1<\/th>/);
  }
  ui.select('typesafe-jev113-v2');
  assert.match(ui.element('repeat-lead').textContent, /Jev uses native Choice instruction variants/);
  ui.select('haiku45-fresh-matched3-batch10');
  assert.match(ui.element('repeat-chart').innerHTML, /Pass 1/);
  assert.match(ui.element('repeat-chart').innerHTML, /Pass 3/);
});

test('switching from native P0 restores all three conditions for existing series', async () => {
  const published = JSON.parse(fs.readFileSync(path.join(site, 'typesafe-repeats.json'), 'utf8'));
  const ui = await renderWith([{series: [nativeSeries(), ...published.series]}, ...feeds.slice(1).map(() => ({series: []}))]);
  ui.select('typesafe-jev113-v2');
  assert.match(ui.element('repeat-condition').innerHTML, /P1: Classifier instructions/);
  assert.match(ui.element('repeat-deltas').innerHTML, /<th scope="row">P2<\/th>/);
  assert.equal(ui.element('repeat-condition-label').textContent, 'Prompt condition');
});
