const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feedUrl = './openjev-native-repeats.json';
const modes = ['fixed', 'adaptive', 'thinking'];
const passes = ['fresh1', 'fresh2', 'fresh3'];
const fields = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

function closedPhase(score, valid = 60) {
  return {completionStatus: 'complete', score: {denominator: 60, valid, allFour: score,
    fields: Object.fromEntries(fields.map(field => [field, score]))},
  usage: {requestCount: 60, clientRequestSecondsTotal: 123.25, inferenceSeconds: null,
    tokens: {input_tokens: 1200, output_tokens: null,
      cached_input_tokens: null, reasoning_output_tokens: null}, actualCostUsd: null}};
}

function configuration(mode, closed = 0, stopped = false) {
  const values = [50, 51, 49];
  const freshPasses = Object.fromEntries(passes.slice(0, closed).map((pass, i) =>
    [pass, closedPhase(values[i], i === 1 ? 59 : 60)]));
  const missingPasses = passes.slice(closed).map((pass, index) => stopped && index === 0
    ? {pass, condition: 'P0', stage: 'development', status: 'stopped', attempted: 12,
      saved: 11, startedIds: [], rawSavedIds: [], savedIds: [],
      unknownStartedIds: ['DEV-012'], failedIds: ['DEV-012']}
    : {pass, condition: 'P0', status: 'not_completed'});
  const flip = {from: 'fresh1', to: 'fresh2', denominator: 59,
    excludedIds: ['DEV-002'], fourFieldVector: {changed: 1, rate: 1 / 59, caseIds: ['DEV-001']},
    ...Object.fromEntries(fields.map(field =>
      [field, {changed: 1, rate: 1 / 59, caseIds: ['DEV-001']}]))};
  return {configuration: `openjev-${mode}`,
    historicalObservation: {status: 'historical_observation_excluded_from_fresh_triplet',
      score: {denominator: 60, valid: 60, allFour: 60}},
    freshPasses, missingPasses, pairwiseFlips: closed >= 2 ? [flip] : [],
    threePassSummary: {P0: {allFour: {range: closed === 3 ? [49, 51] : null},
      fields: Object.fromEntries(fields.map(field =>
        [field, {range: closed === 3 ? [49, 51] : null}]))}},
    changesAcrossThreePasses: closed === 3 ? {denominator: 59, excludedIds: ['DEV-002'],
      fourFieldVector: ['DEV-001'], fields: Object.fromEntries(fields.map(field =>
        [field, ['DEV-001']]))} : null};
}

function fixture(closed = 0, stopped = false) {
  return {schema: 'openjev-native-fresh-three-report-v1',
    configurations: Object.fromEntries(modes.map(mode =>
      [mode, configuration(mode, mode === 'fixed' ? closed : 0, mode === 'fixed' && stopped)])),
    limitations: ['Historical observations are excluded from fresh triplets.',
      'Client HTTP wall time is not model-only inference time.',
      'Local attributable dollar cost and actual adaptive rereads are unavailable.']};
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
      ? {series: [{configuration: 'existing-fixture', displayName: 'Existing fixture',
        passes: {original: {}, repeat2: {}, repeat3: {}}, denominator: 60,
        completedConditions: 0, plannedConditions: 9}]}
      : {series: []}};
  };
  elements.get('repeat-config').value = status === 404 ? 'existing-fixture' : 'openjev-fixed-fresh-native-p0';
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested,
    select(value) { elements.get('repeat-config').value = value; elements.get('repeat-config').change(); },
    field(value) { elements.get('repeat-field').value = value; elements.get('repeat-field').change(); }};
}

test('OpenJev feed is optional only on 404; malformed and server errors are visible', async () => {
  const missing = await render(null, 404);
  assert.equal(missing.requested.filter(url => url === feedUrl).length, 1);
  assert.match(missing.get('repeat-results').innerHTML, /existing-fixture/);
  for (const [feed, status] of [[null, 500], [null, 200], [{schema: 'wrong'}, 200]]) {
    const broken = await render(feed, status);
    assert.match(broken.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});

for (const closed of [0, 1, 2, 3]) {
  test(`OpenJev fixed with ${closed} closed fresh passes stays separate from history`, async () => {
    const ui = await render(fixture(closed));
    assert.match(ui.get('repeat-results').innerHTML, /OpenJev fixed|OpenJev adaptive|OpenJev thinking/);
    assert.match(ui.get('repeat-lead').textContent, new RegExp(`${closed} of 3 planned native P0 passes`));
    assert.match(ui.get('repeat-lead').textContent, /Historical observations are excluded/);
    assert.match(ui.get('repeat-condition').innerHTML, /P0: Native OpenJev P0/);
    assert.doesNotMatch(ui.get('repeat-condition').innerHTML, /P1|P2/);
    assert.equal(ui.get('repeat-deltas').innerHTML, '');
    const chart = ui.get('repeat-chart').innerHTML;
    assert.equal((chart.match(/<meter/g) || []).length, closed);
    assert.equal((chart.match(/Not completed/g) || []).length, 3 - closed);
    assert.doesNotMatch(chart, /<strong>60<small>/);
    assert.equal((ui.get('repeat-usage-body').innerHTML.match(/123\.3/g) || []).length, closed);
    assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /\$0\.00/);
    assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable/);
    assert.match(ui.get('repeat-lead').textContent, /Client HTTP time includes server and transport overhead/);
    if (closed < 3) assert.match(chart, /Three-pass range unavailable/);
    else assert.match(chart, /Three-pass range: <strong>49–51<\/strong>/);
    ui.select('openjev-adaptive-fresh-native-p0');
    assert.match(ui.get('repeat-lead').textContent, /0 of 3 planned native P0 passes/);
  });
}

test('OpenJev stopped development is unscored and retains the unknown started attempt', async () => {
  const ui = await render(fixture(1, true));
  assert.match(ui.get('repeat-lead').textContent,
    /Fresh pass 2 stopped during development after 12 attempts and 11 saved responses/);
  assert.match(ui.get('repeat-lead').textContent, /1 started requests have unknown outcomes/);
  assert.match(ui.get('repeat-chart').innerHTML, /Stopped; unscored/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Fresh pass 2 \(stopped, unscored\)/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /12\.0|\$0\.00/);
});

test('OpenJev field flips use reporter changed objects and shared-valid denominator', async () => {
  const ui = await render(fixture(3));
  ui.field('sentiment');
  const flips = ui.get('repeat-flips').innerHTML;
  assert.match(flips, /Fresh pass 1 to Fresh pass 2: 1 \/ 59 changed/);
  assert.match(flips, /1 \/ 59<\/strong> comparable comments changed/);
  assert.match(flips, /DEV-001/);
  assert.doesNotMatch(flips, /undefined|#inspect|<a\s/);
});
