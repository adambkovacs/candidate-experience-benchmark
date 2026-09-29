const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const url = './openjev-generated-repeats.json';
const modes = ['generated-off', 'generated-on'];
const passes = ['fresh1', 'fresh2', 'fresh3'];
const conditions = ['P0', 'P1', 'P2'];
const order = passes.flatMap(pass => conditions.map(condition => [pass, condition]));
const fields = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips', 'repeat-usage-body'];

function phase(score = 50, valid = 60) {
  return {completionStatus: 'complete', score: {denominator: 60, valid, allFour: score,
    fields: Object.fromEntries(fields.map(field => [field, score])), outcomes: {ok: valid,
      invalid_output: 60 - valid}},
  predictedClassCounts: {}, confusionCounts: {},
  usage: {requestCount: 60, rawCaptureCount: 60, rawResponseCount: 60,
    clientRequestSecondsTotal: 137.25, inferenceSeconds: null,
    tokens: {input_tokens: 1200, output_tokens: 840,
      knownSavedInputTokens: 1200, knownSavedOutputTokens: 840}, actualCostUsd: null},
  evidence: {smoke: {}, development: {}}};
}

function flip() {
  return {from: 'fresh1', to: 'fresh2', denominator: 59,
    excludedIds: ['DEV-002'], fourFieldVector: {changed: 1, rate: 1 / 59,
      caseIds: ['DEV-001']}, ...Object.fromEntries(fields.map(field => [field,
      {changed: 1, rate: 1 / 59, caseIds: ['DEV-001']}]))};
}

function group(mode, closed = 0, stopped = false) {
  const freshPasses = Object.fromEntries(passes.map(pass => [pass, {}]));
  for (const [index, [pass, condition]] of order.slice(0, closed).entries())
    freshPasses[pass][condition] = phase(50 + (index % 2), index === 1 ? 59 : 60);
  const missingPhases = order.slice(closed).map(([pass, condition], index) =>
    stopped && index === 0 ? {pass, condition, stage: 'development', status: 'stopped_unknown',
      startedIds: Array.from({length: 12}, (_, i) => `DEV-${String(i + 1).padStart(3, '0')}`),
      rawSavedIds: Array.from({length: 11}, (_, i) => `DEV-${String(i + 1).padStart(3, '0')}`),
      savedIds: Array.from({length: 11}, (_, i) => `DEV-${String(i + 1).padStart(3, '0')}`),
      unknownStartedIds: ['DEV-012'],
      neverSentIds: Array.from({length: 48}, (_, i) => `DEV-${String(i + 13).padStart(3, '0')}`),
      usage: {requestCount: 12, clientRequestSecondsTotal: null,
        knownClientSecondsSubtotal: 20, tokens: {input_tokens: null,
          output_tokens: null, knownSavedInputTokens: 330}, actualCostUsd: null}}
      : {pass, condition, status: 'not_completed'});
  const within = Object.fromEntries(passes.map(pass => [pass, []]));
  if (freshPasses.fresh1.P0 && freshPasses.fresh1.P1) within.fresh1.push({
    from: 'P0', to: 'P1', netScoreDelta: {allFour: 1,
      fields: Object.fromEntries(fields.map(field => [field, 1]))},
    denominator: 59, excludedIds: ['DEV-002'],
    fourFieldVector: {changed: 2, rate: 2 / 59, caseIds: ['DEV-001', 'DEV-003']},
    ...Object.fromEntries(fields.map(field => [field,
      {changed: 2, rate: 2 / 59, caseIds: ['DEV-001', 'DEV-003']}]))});
  const changes = closed === 9 ? {P0: {denominator: 59,
    excludedIds: ['DEV-002'], fourFieldVector: ['DEV-001'],
    fields: Object.fromEntries(fields.map(field => [field, ['DEV-001']]))}} : {};
  return {historicalObservation: {status: 'historical_observation_excluded_from_fresh_triplet'},
    freshPasses, missingPhases,
    pairwiseFlips: {P0: closed === 9 ? [flip()] : [], P1: [], P2: []},
    withinPassPromptDifferences: within, changesAcrossThreePasses: changes};
}

function fixture(closed = 0, stopped = false) {
  return {schema: 'openjev-generated-fresh-three-report-v2',
    configurations: Object.fromEntries(modes.map(mode =>
      [mode, group(mode, mode === 'generated-off' ? closed : 0,
        mode === 'generated-off' && stopped)])),
    limitations: ['Historical generated observations do not count as fresh pass one.',
      'Client HTTP wall time is not model-only inference time; local dollar cost is unmeasured.']};
}

async function render(feed, status = 200) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const document = {getElementById(id) { return elements.get(id); }};
  const requested = [];
  const fetch = async name => {
    requested.push(name);
    if (name === url) return {ok: status === 200, status, json: async () => feed};
    return {ok: true, status: 200, json: async () => name === './typesafe-repeats.json'
      ? {series: [{configuration: 'existing-fixture', passes: {original: {}, repeat2: {}, repeat3: {}},
        denominator: 60, completedConditions: 0, plannedConditions: 9}]}
      : {series: []}};
  };
  elements.get('repeat-config').value = status === 404 ? 'existing-fixture'
    : 'openjev-generated-off-fresh-generated-p0p1p2';
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested,
    select(value) { elements.get('repeat-config').value = value; elements.get('repeat-config').change(); },
    field(value) { elements.get('repeat-field').value = value; elements.get('repeat-field').change(); }};
}

test('optional generated feed accepts only 404 and rejects malformed or server responses', async () => {
  const absent = await render(null, 404);
  assert.equal(absent.requested.filter(name => name === url).length, 1);
  assert.match(absent.get('repeat-results').innerHTML, /existing-fixture/);
  for (const [feed, status] of [[null, 200], [{schema: 'wrong'}, 200], [null, 500]]) {
    const broken = await render(feed, status);
    assert.match(broken.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});

for (const closed of [0, 1, 2, 9]) {
  test(`generated off with ${closed} closed phases shows only terminal scores`, async () => {
    const ui = await render(fixture(closed));
    assert.match(ui.get('repeat-results').innerHTML, /generated off|generated requested-on/);
    assert.match(ui.get('repeat-lead').textContent, new RegExp(`${closed} of 9 planned prompt/pass combinations`));
    assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, closed);
    assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /\$0\.00/);
    assert.match(ui.get('repeat-lead').textContent, /Requested-on effective reasoning is not measured/);
    if (closed !== 9) assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range unavailable/);
    ui.select('openjev-generated-on-fresh-generated-p0p1p2');
    assert.match(ui.get('repeat-lead').textContent, /0 of 9 planned prompt\/pass combinations/);
  });
}

test('invalid output remains scored out of 60 and field flips use shared-valid denominator', async () => {
  const ui = await render(fixture(9));
  assert.match(ui.get('repeat-lead').textContent, /P1 Fresh pass 1: 59\/60 valid responses/);
  assert.match(ui.get('repeat-deltas').innerHTML, /\+1/);
  assert.match(ui.get('repeat-deltas').innerHTML, /59 shared valid of 60; 1 excluded/);
  ui.field('sentiment');
  const flips = ui.get('repeat-flips').innerHTML;
  assert.match(flips, /Fresh pass 1 to Fresh pass 2: 1 \/ 59 changed/);
  assert.match(flips, /1 \/ 59<\/strong> comparable comments changed/);
  assert.doesNotMatch(flips, /undefined|#inspect|<a\s/);
});

test('stopped development retains counts while withholding score and full totals', async () => {
  const ui = await render(fixture(1, true));
  assert.match(ui.get('repeat-lead').textContent, /Fresh pass 1 P1 stopped during development: 12 started, 11 saved, 1 unknown, 48 not sent/);
  ui.get('repeat-condition').value = 'P1'; ui.get('repeat-condition').change();
  assert.match(ui.get('repeat-chart').innerHTML, /Stopped; unscored/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Fresh pass 1 \(stopped, unscored\)/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /20\.0|\$0\.00/);
});
