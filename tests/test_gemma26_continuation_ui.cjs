const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'public-site', 'repeats.js'), 'utf8');
const saved = JSON.parse(fs.readFileSync(path.join(root, 'public-site',
  'gemma26-continuation-findings.json'), 'utf8'));
const url = './gemma26-continuation-findings.json';
const id = 'gemma26-on-v2-interruption-continuation-v1';
const cleanId = 'gemma26-on-fresh-matched3-v2';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
  'repeat-flips', 'repeat-usage-body'];

const cleanSeries = {
  schema: 'hosted-v2-fresh-repeat-findings-v1',
  configuration: 'openrouter-paid-gemma4-26b-a4b-on', seriesId: cleanId,
  displayName: 'Gemma 26B clean series', method: 'fresh-matched-three',
  denominator: 60, plannedConditions: 9, completedConditions: 1,
  passOrder: ['fresh1', 'fresh2', 'fresh3'], conditionOrder: ['P0', 'P1', 'P2'],
  passes: {fresh1: {P0: {status: 'completed', score: {denominator: 60, valid: 60,
    allFour: 42, fields: {sentiment: 42, follow_up_needed: 42,
      serious_concern_reported: 42, testimonial_potential: 42}},
    usage: {requestCount: 60, tokens: {prompt_tokens: 100, completion_tokens: 20},
      actualCostUsd: '0.01', requestSecondsTotal: 1}}}, fresh2: {}, fresh3: {}},
  threePassSummary: {}, withinPassPromptDeltas: [], pairwiseFlips: [],
  changesAcrossThreePasses: {}
};

async function render(payload = saved, status = 200, selected = id) {
  const elements = new Map(ids.map(key => [key, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const document = {getElementById(key) { return elements.get(key); }};
  const fetch = async feed => {
    requested.push(feed);
    if (feed === url) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () => feed === './hosted-v2-repeats.json'
      ? {schema: 'hosted-v2-fresh-repeat-findings-v1', series: [cleanSeries]}
      : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: key => elements.get(key), requested, select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

function usageRow(ui, condition, pass) {
  const rows = ui.get('repeat-usage-body').innerHTML.match(/<tr>.*?<\/tr>/g) || [];
  return rows.find(row => row.includes(`<th scope="row">${condition}</th><td>${pass}`));
}

test('interrupted Gemma series stays separate and shows only five final scores', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(item => item === url).length, 1);
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${id}"`));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${cleanId}"`));
  assert.match(ui.get('repeat-summary').textContent, /5 of 9 phases have final scores/);
  assert.match(ui.get('repeat-summary').textContent, /one stopped|stopped without a score/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 5);
  assert.match(ui.get('repeat-chart').innerHTML, /Stopped: 1 valid, 1 service error, 58 unsent; no score/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/Not sent/g) || []).length, 3);
  assert.match(ui.get('repeat-chart').innerHTML, /59<small> \/ 60<\/small>/);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>/);
  ui.select(cleanId);
  assert.match(ui.get('repeat-chart').innerHTML, /42<small> \/ 60<\/small>/);
  assert.doesNotMatch(ui.get('repeat-lead').textContent, /DEV-002/);
});

test('stopped phase keeps known charges distinct from its unknown bound', async () => {
  const ui = await render();
  const stopped = usageRow(ui, 'P0', 'Fresh pass 2');
  assert.match(stopped, /stopped, unscored/);
  assert.match(stopped, /2 attempted/);
  assert.match(stopped, /1 of 2 reported/);
  assert.match(stopped, /\$0\.00028017 known/);
  assert.match(stopped, /Unknown charge up to \$0\.01974272; not observed/);
  const firstP2 = usageRow(ui, 'P2', 'Fresh pass 1');
  assert.match(firstP2, /Unknown charge up to \$0\.01974272; not observed/);
  const unsent = usageRow(ui, 'P1', 'Fresh pass 3');
  assert.match(unsent, /Not sent/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /NaN|undefined/);
});

test('optional absence remains usable but malformed or failed feed is visible', async () => {
  const absent = await render(null, 404, cleanId);
  assert.match(absent.get('repeat-results').innerHTML, /repeat-config/);
  const failed = await render(null, 500, cleanId);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  for (const payload of [
    {...saved, completedConditions: 6},
    {...saved, stoppedPhases: [{...saved.stoppedPhases[0], score: {allFour: 60}}]},
    {...saved, stoppedPhases: [{...saved.stoppedPhases[0], neverSentCount: 57}]},
    {...saved, stoppedPhases: [{...saved.stoppedPhases[0], usage: {
      ...saved.stoppedPhases[0].usage, unknownCostUpperBoundUsd: null}}]},
    {...saved, sourceBindings: [{path: 'private/account-error.json', sha256: 'a'.repeat(64)}]},
    {...saved, passes: {...saved.passes, fresh2: {...saved.passes.fresh2,
      P0: {status: 'completed', score: {allFour: 60}}}}}
  ]) {
    const malformed = await render(payload);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
