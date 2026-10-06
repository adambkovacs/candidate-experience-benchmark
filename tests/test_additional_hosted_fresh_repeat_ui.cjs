const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const url = './additional-hosted-fresh-repeats.json';
const schema = 'additional-hosted-fresh-repeat-findings-v1';
const qwen = 'openrouter-paid-qwen36-35b-a3b-off';
const low = 'openrouter-paid-deepseek-v41-flash-low';
const on = 'openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
  'repeat-usage-body'];

const score = (allFour, valid = 60) => ({denominator: 60, valid, allFour,
  fields: {sentiment: allFour, follow_up_needed: allFour,
    serious_concern_reported: allFour, testimonial_potential: allFour},
  outcomes: valid === 60 ? {ok: 60} : {ok: valid, invalid_output: 60 - valid},
  invalidIds: valid === 60 ? [] : ['DEV-042']});
const phase = (allFour, valid = 60) => ({status: 'completed', score: score(allFour, valid),
  usage: {requestCount: 60, tokens: {prompt_tokens: 1234, completion_tokens: 456},
    actualCostUsd: '0.01234', requestSecondsTotal: 87.6}});

function fixture() {
  const item = (configuration, displayName, count, valid = 60) => ({
    schema, configuration, seriesId: `${configuration}-fresh-matched3-v2`, displayName,
    method: 'fresh-matched-three', denominator: 60, completedConditions: 1,
    plannedConditions: 9, passOrder: ['fresh1', 'fresh2', 'fresh3'],
    conditionOrder: ['P0', 'P1', 'P2'],
    passes: {fresh1: {P0: phase(count, valid)}, fresh2: {}, fresh3: {}},
    threePassSummary: {}, withinPassPromptDeltas: [], pairwiseFlips: [],
    changesAcrossThreePasses: {}});
  return {schema, series: [item(qwen, 'Qwen off fresh', 49), item(low, 'DeepSeek low fresh', 46, 59)]};
}

function historical() {
  return {schema: 'repeat-findings-v1', configuration: qwen,
    displayName: 'Historical Qwen result', denominator: 60,
    completedConditions: 1, plannedConditions: 9,
    passOrder: ['original', 'repeat2', 'repeat3'], conditionOrder: ['P0', 'P1', 'P2'],
    passes: {original: {P0: {score: score(40)}}, repeat2: {}, repeat3: {}},
    threePassSummary: {}, withinPassPromptDeltas: [], pairwiseFlips: [],
    changesAcrossThreePasses: {}};
}

async function render(payload = fixture(), status = 200, selected = `${qwen}-fresh-matched3-v2`) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async feed => {
    requested.push(feed);
    if (feed === url) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () => feed === './typesafe-repeats.json'
      ? {series: [historical()]} : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested, select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

function usageRow(ui, condition, pass) {
  const rows = ui.get('repeat-usage-body').innerHTML.match(/<tr>.*?<\/tr>/g) || [];
  return rows.find(row => row.includes(`<th scope="row">${condition}</th><td>${pass}</td>`));
}

test('both additional hosted series are separate from historical results and show closed evidence', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(item => item === url).length, 1);
  for (const configuration of [qwen, low]) {
    assert.match(ui.get('repeat-results').innerHTML,
      new RegExp(`value="${configuration}-fresh-matched3-v2"`));
  }
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${qwen}"`));
  assert.match(ui.get('repeat-chart').innerHTML, /49 out of 60/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.match(ui.get('repeat-lead').textContent, /Earlier results remain separate and are not pass one/);
  const row = usageRow(ui, 'P0', 'Fresh pass 1');
  assert.match(row, /1,234/);
  assert.match(row, /456/);
  assert.match(row, /\$0\.01234/);
  assert.match(row, /87\.6/);
  ui.select(`${low}-fresh-matched3-v2`);
  assert.match(ui.get('repeat-chart').innerHTML, /46 out of 60/);
  assert.match(ui.get('repeat-lead').textContent, /59\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /Failed or invalid answers remain in the score denominator/);
  ui.select(qwen);
  assert.match(ui.get('repeat-lead').textContent, /Historical Qwen result/);
  assert.doesNotMatch(ui.get('repeat-lead').textContent, /three fresh hosted passes/);
});

test('published hosted ON P1 composite is visible without clean repeat credit', async () => {
  const published = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'public-site',
    'additional-hosted-fresh-repeats.json'), 'utf8'));
  const ui = await render(published, 200, `${on}-fresh-matched3`);
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${on}-fresh-matched3"`));
  assert.match(ui.get('repeat-chart').innerHTML, /54 out of 60/);
  assert.match(ui.get('repeat-chart').innerHTML, /52 out of 60/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /DEV-049 remains an unknown timeout/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /no clean repeat credit/);
  assert.match(ui.get('repeat-lead').textContent, /1 of 9/);
});

test('open phases cannot expose stale scores, derived values, tokens, costs or durations', async () => {
  const payload = fixture();
  const item = payload.series[0];
  item.passes.fresh1.P1 = {status: 'not_completed', score: score(60),
    usage: {requestCount: 60, tokens: {prompt_tokens: 999999, completion_tokens: 999998},
      actualCostUsd: '999.99', requestSecondsTotal: 999.9}};
  item.passes.fresh2.P0 = {status: 'not_completed', score: score(60)};
  item.threePassSummary.P0 = {allFour: {range: [49, 60]}};
  item.withinPassPromptDeltas = [{pass: 'fresh1', to: 'P1', allFour: 999}];
  item.pairwiseFlips = [{condition: 'P0', from: 'fresh1', to: 'fresh2',
    denominator: 60, fourFieldVector: {changed: 999}}];
  item.changesAcrossThreePasses.P0 = {denominator: 60, excludedIds: [],
    fourFieldVector: ['DEV-999']};
  const ui = await render(payload);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>|<strong>60<small>/);
  assert.doesNotMatch(ui.get('repeat-deltas').innerHTML, /999/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /999|DEV-999/);
  const row = usageRow(ui, 'P1', 'Fresh pass 1');
  assert.match(row, /Unavailable/);
  assert.doesNotMatch(row, /999|\$999/);
});

test('optional 404 remains usable, while 500 and malformed feeds fail visibly', async () => {
  const missing = await render(null, 404, qwen);
  assert.match(missing.get('repeat-results').innerHTML, /repeat-config/);
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /could not be loaded/);
  const failed = await render(null, 500, qwen);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const good = fixture();
  for (const payload of [
    {}, {...good, schema: 'unexpected'},
    {...good, series: [{...good.series[0], schema: 'unexpected'}]},
    {...good, series: [{...good.series[0], seriesId: qwen}]},
    {...good, series: [{...good.series[0], method: 'historical'}]},
    {...good, series: [good.series[0], good.series[0]]},
    {...good, series: [{...good.series[0], configuration: 'unknown'}]},
  ]) {
    const malformed = await render(payload, 200, qwen);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
