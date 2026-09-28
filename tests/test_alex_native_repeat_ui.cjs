const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feedUrl = './alex-native-repeats.json';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function score(allFour, valid = 60) {
  return {denominator: 60, valid, allFour,
    fields: {sentiment: allFour, follow_up_needed: allFour,
      serious_concern_reported: allFour, testimonial_potential: allFour}};
}

function phase(allFour, valid = 60) {
  return {completionStatus: 'complete', score: score(allFour, valid),
    usage: {clientPredictionSeconds: 86.25, nativeNliInputTokenPositions: 123456,
      generatedOutputTokens: null, isolatedInferenceSeconds: null,
      actualCostUsd: null, costKnown: false}};
}

function alex(configuration, first = null) {
  return {schema: 'alex-native-repeat-findings-v1', configuration,
    displayName: configuration.includes('08') ? 'Alex OpenJev 0.8B · native NLI' : 'Alex OpenJev 4B · native NLI',
    method: 'native-output-stability', conditionOrder: ['P0'],
    passOrder: ['fresh1', 'fresh2', 'fresh3'],
    completedConditions: first == null ? 0 : 1, plannedConditions: 3,
    denominator: 60,
    passes: {fresh1: first == null ? {} : {P0: phase(first)}, fresh2: {}, fresh3: {}},
    historicalObservation: {status: 'observational_only', freshPassEligible: false,
      unknownPriorAttempt: configuration.includes('4b')
        ? {id: 'DEV-046', status: 'possibly_started_outcome_unknown'} : null},
    missingPasses: [], partialPasses: [], pairwiseFlips: [],
    changesAcrossThreePasses: {}, withinPassPromptDeltas: [],
    threePassSummary: {P0: {allFour: {range: null}}}};
}

async function render(payload, status = 200, selected = 'alex-openjev08-native-p0-v1') {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const requested = [];
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    requested.push(url);
    if (url === feedUrl) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () => url === './typesafe-repeats.json'
      ? {series: [alex('existing-repeat-fixture', 2)]} : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested};
}

test('Alex feed is optional only when unpublished', async () => {
  const missing = await render(null, 404, 'existing-repeat-fixture');
  assert.equal(missing.requested.filter(url => url === feedUrl).length, 1);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const broken = await render(null, 500, 'existing-repeat-fixture');
  assert.match(broken.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});

test('0.8B first fresh pass renders while 4B remains 0 of 3', async () => {
  const payload = {series: [alex('alex-openjev08-native-p0-v1', 3),
    alex('alex-openjev4b-native-p0-v1')]};
  const ui = await render(payload);
  assert.match(ui.get('repeat-results').innerHTML, /alex-openjev08-native-p0-v1/);
  assert.match(ui.get('repeat-results').innerHTML, /alex-openjev4b-native-p0-v1/);
  assert.match(ui.get('repeat-lead').textContent, /1 of 3 planned native P0 passes/);
  assert.match(ui.get('repeat-lead').textContent, /Earlier results are observational and excluded/);
  assert.match(ui.get('repeat-lead').textContent, /input positions are not billed API tokens/);
  assert.match(ui.get('repeat-condition').innerHTML, /Native NLI output/);
  assert.doesNotMatch(ui.get('repeat-condition').innerHTML, /P1|P2/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.match(ui.get('repeat-chart').innerHTML, /Fresh pass 1/);
  assert.match(ui.get('repeat-chart').innerHTML, /<strong>3<small> \/ 60/);
  assert.equal(ui.get('repeat-deltas').innerHTML, '');
  assert.match(ui.get('repeat-usage-body').innerHTML, /Native NLI input positions: 123,456/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /86\.3/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);

  ui.get('repeat-config').value = 'alex-openjev4b-native-p0-v1';
  ui.get('repeat-config').change();
  assert.match(ui.get('repeat-lead').textContent, /0 of 3 planned native P0 passes/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 0);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /DEV-046/);
});

test('claimed phase with stale score and usage stays unscored', async () => {
  const item = alex('alex-openjev08-native-p0-v1', 3);
  item.passes.fresh2.P0 = {completionStatus: 'claimed', score: score(60),
    usage: {clientPredictionSeconds: 999, actualCostUsd: 100}};
  const ui = await render({series: [item]});
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /<strong>60<small>/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /999\.0|\$100/);
});

test('future closed Alex passes show only feed-supplied range and case flips', async () => {
  const item = alex('alex-openjev08-native-p0-v1', 3);
  item.passes.fresh2.P0 = phase(4, 59);
  item.passes.fresh3.P0 = phase(2);
  item.completedConditions = 3;
  item.threePassSummary.P0.allFour.range = [2, 4];
  item.pairwiseFlips = [{condition: 'P0', from: 'fresh1', to: 'fresh2',
    denominator: 59, fourFieldVector: {changed: 1}}];
  item.changesAcrossThreePasses.P0 = {denominator: 59,
    fourFieldVector: ['DEV-001'], excludedIds: ['DEV-002'],
    fields: {sentiment: ['DEV-001']}};
  const ui = await render({series: [item]});
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 3);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>2–4<\/strong>/);
  assert.match(ui.get('repeat-flips').innerHTML, /Fresh pass 1 to Fresh pass 2: 1 \/ 59 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-001/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /#inspect|<a\s/);
  assert.match(ui.get('repeat-lead').textContent, /59\/60 valid responses/);
});
