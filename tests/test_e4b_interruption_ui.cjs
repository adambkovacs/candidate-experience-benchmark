const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const interrupted = JSON.parse(execFileSync('python3', ['-c',
  'import json,sys;sys.path.insert(0,"scripts");import build_e4b_interruption_findings as b;print(json.dumps(b.build()))'],
{cwd: path.join(__dirname, '..'), encoding: 'utf8'}));
const local = JSON.parse(fs.readFileSync(path.join(site, 'small-local-repeats.json'), 'utf8'));
const url = './e4b-interruption-findings.json';
const config = 'gemma4-e4b-sdk-thinking-on';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
  'repeat-flips', 'repeat-usage-body'];

async function render(payload = interrupted, status = 200, selected = config) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, callback) { this[type] = callback; }}]));
  const requested = [];
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async feed => {
    requested.push(feed);
    if (feed === url) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () =>
      feed === './small-local-repeats.json' ? local : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P2';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested, select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

test('E4B closed interruption shows a descriptive P2 without changing clean scores', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(item => item === url).length, 1);
  assert.match(ui.get('repeat-summary').textContent, /4 of 9 planned prompt-and-pass runs have final results/);
  assert.match(ui.get('repeat-summary').textContent, /58 valid saved responses, two unknown timeouts and no unsent/);
  assert.match(ui.get('repeat-summary').textContent, /48\/60 all-four figure is descriptive and gets no clean repeat credit/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 4);
  assert.match(ui.get('repeat-chart').innerHTML, /Descriptive interrupted: 48\/60 matches, 58 valid, 2 unknown, 0 unsent; no clean-pass credit/);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>/);
  const explanation = ui.get('repeat-interpretation').innerHTML;
  assert.match(explanation, /58 valid saved responses, 2 unknown timeouts, and 0 comments unsent/);
  assert.match(explanation, /historical cutoff had 50 valid responses, 2 unknown timeouts and 8 unsent comments/);
  assert.match(explanation, /7\/8 all-four matches/);
  assert.match(explanation, /<details><summary>What happened to this pass\?/);
  assert.match(explanation, /Both timeout intervals overlapped recorded host sleep/);
  assert.match(explanation, /docs\/HOST_INTERRUPTION_2026-10-01\.md/);
  assert.match(explanation, /development\.completion\.json/);
  assert.match(explanation, /suffix\.completion\.json/);
  assert.match(explanation, /suffix\.closure-review\.json/);
  assert.doesNotMatch(explanation, /partialResult|reasoningContent|Prediction exceeded/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /60 attempted/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /159,051/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /25,073/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Includes host sleep; not model inference time/);
});

test('optional missing feed leaves local series usable; malformed evidence fails visibly', async () => {
  const missing = await render(null, 404);
  assert.match(missing.get('repeat-summary').textContent, /4 of 9 planned prompt-and-pass runs/);
  assert.doesNotMatch(missing.get('repeat-interpretation').innerHTML, /What happened to this pass/);
  const failed = await render(null, 500);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  for (const bad of [
    {...interrupted, savedValid: 51},
    {...interrupted, finalScore: {allFour: 50}},
    {...interrupted, neverSentIds: ['DEV-060']},
    {...interrupted, descriptiveScore: {...interrupted.descriptiveScore, allFour: 49}},
    {...interrupted, finalSuffix: {...interrupted.finalSuffix, cleanRepeatCredit: true}},
    {...interrupted, originalCutoff: {...interrupted.originalCutoff, neverSentIds: []}},
    {...interrupted, hostInterruption: {...interrupted.hostInterruption,
      observation: 'no_host_overlap'}},
    {...interrupted, sourceBindings: [{path: 'private/account.json', sha256: 'a'.repeat(64)}]},
  ]) {
    const ui = await render(bad);
    assert.match(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});

test('other local configurations and the default selection keep their own view', async () => {
  const ui = await render(interrupted, 200, 'gemma4-e2b-sdk-thinking-on');
  assert.doesNotMatch(ui.get('repeat-interpretation').innerHTML, /What happened to this pass/);
  assert.doesNotMatch(ui.get('repeat-summary').textContent, /two unknown timeouts/);
  assert.equal((ui.get('repeat-results').innerHTML.match(/value="gemma4-e4b-sdk-thinking-on"/g) || []).length, 1);
  ui.select(config);
  assert.match(ui.get('repeat-summary').textContent, /two unknown timeouts/);
});
