const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {spawnSync} = require('node:child_process');
const vm = require('node:vm');

const source = fs.readFileSync('public-site/jev-prompts.js', 'utf8');
const page = fs.readFileSync('public-site/index.html', 'utf8');
const fieldScores = {
  sentiment: 56,
  follow_up_needed: 58,
  serious_concern_reported: 57,
  testimonial_potential: 58
};
const fieldNames = Object.keys(fieldScores);

function pass(status, valid, allFour, outcomes, inputTokens, cost, seconds) {
  return {
    status,
    score: {denominator: 60, valid, allFour,
      fields: Object.fromEntries(fieldNames.map(key => [key, Math.min(valid, fieldScores[key])]))},
    outcomes,
    knownCostUsd: cost,
    unknownUpperBoundUsd: outcomes.unknown_cost_http_429 || outcomes.unknown_cost_transport_timeout ? '0.001344000' : '0',
    inputTokens,
    outputTokens: Math.round(inputTokens / 14),
    clientSeconds: seconds
  };
}

function comparison(denominator, excludedIds, changedIds, probabilityCount, confidenceCount) {
  const ids = length => Array.from({length}, (_, index) => `DEV-${String(index + 1).padStart(3, '0')}`);
  return {
    denominator,
    excludedIds,
    fourFieldVectorChangedIds: changedIds,
    fields: Object.fromEntries(fieldNames.map((key, index) => [key, {
      choiceChangedIds: index === 0 ? changedIds : [],
      probabilityChangedIds: ids(Math.max(0, probabilityCount - index * 3)),
      confidenceChangedIds: ids(Math.max(0, confidenceCount - index * 2))
    }]))
  };
}

function fixture() {
  const parent = pass('stopped', 17, 15,
    {valid: 17, unknown_cost_http_429: 1, never_sent: 42}, 46207, '0.001940694', 10.30);
  const tail = pass('interrupted', 40, 35,
    {valid: 40, invalid_native_distribution: 1, unknown_cost_transport_timeout: 1},
    111470, '0.004681740', 83.77);
  tail.score.denominator = 42;
  const combined = pass('interrupted_parent_with_stopped_continuation', 57, 50,
    {valid: 57, invalid_native_distribution: 1, unknown_cost_http_429: 1,
      unknown_cost_transport_timeout: 1}, 157677, '0.006622434', 94.07);
  combined.score.fields = Object.fromEntries(fieldNames.map(key =>
    [key, parent.score.fields[key] + tail.score.fields[key]]));
  combined.unknownUpperBoundUsd = '0.002688000';
  combined.cleanRepeatCredit = false;
  combined.neverSent = 0;
  combined.parentOriginal = JSON.parse(JSON.stringify(parent));
  return {
    sourceBindings: [{path: 'results/route-audits/jev/fresh1/completion.json', sha256: 'a'.repeat(64)}],
    passes: {
      P0: {
        fresh1: pass('complete', 60, 54, {valid: 60}, 140260, '0.005890920', 32.50),
        fresh2: pass('complete', 60, 53, {valid: 60}, 140260, '0.005890920', 42.68),
        fresh3: pass('complete', 59, 52, {valid: 59, invalid_native_distribution: 1},
          140260, '0.005890920', 40.56)
      },
      P1: {
        fresh1: pass('complete', 60, 54, {valid: 60}, 152500, '0.006405000', 32.26),
        fresh2: pass('complete', 59, 53, {valid: 59, invalid_native_distribution: 1}, 152500, '0.006405000', 35.99),
        fresh3: pass('complete', 60, 54, {valid: 60}, 152500, '0.006405000', 31.99)
      },
      P2: {
        fresh1: pass('complete', 60, 54, {valid: 60}, 163120, '0.006851040', 32.84),
        fresh2: parent
      }
    },
    continuations: {P2fresh2tail: tail},
    composites: {P2fresh2: combined},
    comparisons: {
      P0fresh1fresh2: comparison(60, [], ['DEV-013', 'DEV-030', 'DEV-056'], 25, 20),
      P0fresh2fresh3: comparison(59, ['DEV-040'], ['DEV-030'], 21, 18),
      P0P1fresh1: comparison(60, [], ['DEV-013'], 30, 25),
      P1repeat: comparison(59, ['DEV-056'], [], 25, 22),
      P1P2fresh1: comparison(60, [], ['DEV-013'], 32, 27),
      P1P2fresh2shared: comparison(17,
        Array.from({length: 43}, (_, index) => `DEV-${String(index + 18).padStart(3, '0')}`),
        ['DEV-013'], 9, 8)
    }
  };
}

async function render(feed = fixture(), responseOk = true) {
  const target = {innerHTML: '', textContent: '', setAttribute(name, value) {this[name] = value;}};
  const requests = [];
  const errors = [];
  const fetch = async (url, options) => {
    requests.push({url, options});
    return {ok: responseOk, json: async () => feed};
  };
  vm.runInNewContext(source, {
    document: {getElementById: id => id === 'jev-prompt-results' ? target : null},
    fetch, console: {error: error => errors.push(String(error))}, Intl, Set
  });
  await new Promise(resolve => setImmediate(resolve));
  return {target, requests, errors};
}

test('renders all P0 and P1 passes and the complete first-pass comparison', async () => {
  const {target, requests, errors} = await render();
  assert.deepEqual(errors, []);
  assert.equal(requests[0].url, './jev-native-prompt-findings.json');
  assert.equal(requests[0].options.cache, 'no-store');
  assert.equal(target['aria-busy'], 'false');
  assert.match(target.innerHTML, /P0, P1, and P2 each matched 54\/60/);
  assert.match(target.innerHTML, /P0 completed three full passes/);
  assert.match(target.innerHTML, /P1 completed three full passes/);
  assert.match(target.innerHTML, /54\/60, 53\/60, and 52\/60/);
  assert.match(target.innerHTML, /DEV-040 had an invalid native distribution/);
  assert.match(target.innerHTML, /DEV-056 had an invalid native distribution/);
  assert.equal((target.innerHTML.match(/class="condition-score">54<small> \/ 60<\/small>/g) || []).length, 3);
});

test('accepts a fresh read-only source-bound build', async () => {
  const command = "import sys,json;sys.path.insert(0,'scripts');import build_jev_native_prompt_findings as b;print(json.dumps(b.build()))";
  const result = spawnSync('python3', ['-c', command], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
  const actual = JSON.parse(result.stdout);
  const {target, errors} = await render(actual);
  assert.deepEqual(errors, []);
  assert.match(target.innerHTML, /P0, P1, and P2 each matched 54\/60/);
  assert.match(target.innerHTML, /original parent saved 17 valid responses/);
  assert.match(target.innerHTML, /separate continuation attempted those 42 positions: 40 valid/);
  assert.match(target.innerHTML, /57 valid, 1 invalid, 2 unknown-cost attempts, and 0 unsent/);
});

test('keeps interrupted P2 out of complete score cards and preserves parent counts', async () => {
  const {target} = await render();
  assert.match(target.innerHTML, /parent saved 17 valid responses/);
  assert.match(target.innerHTML, /left 42 positions unsent/);
  assert.match(target.innerHTML, /50\/60 all-four figure is interrupted coverage, not a clean repeat or ranking result/);
  assert.doesNotMatch(target.innerHTML, /class="condition-score">15/);
  assert.doesNotMatch(target.innerHTML, /class="condition-score">50/);
});

test('derives changed values from an internally consistent fixture', async () => {
  const changed = fixture();
  changed.passes.P0.fresh1.score.allFour = 53;
  changed.passes.P1.fresh1.score.allFour = 52;
  changed.passes.P2.fresh1.score.allFour = 51;
  changed.passes.P1.fresh2.score.allFour = 50;
  changed.comparisons.P1P2fresh1.fourFieldVectorChangedIds = ['DEV-002', 'DEV-013'];
  changed.comparisons.P1P2fresh1.fields.sentiment.choiceChangedIds = ['DEV-002', 'DEV-013'];
  changed.comparisons.P1repeat.fourFieldVectorChangedIds = ['DEV-003'];
  changed.comparisons.P1repeat.fields.sentiment.choiceChangedIds = ['DEV-003'];
  const {target, errors} = await render(changed);
  assert.deepEqual(errors, []);
  assert.match(target.innerHTML, /P0 matched 53\/60, P1 52\/60, and P2 51\/60/);
  assert.match(target.innerHTML, /P1 and P2 differed on 2 reviews/);
  assert.match(target.innerHTML, /52\/60, 50\/60, and 54\/60/);
  assert.match(target.innerHTML, /1 answer vector changed/);
});

test('separates answer changes from probabilities, confidence, usage, and timing', async () => {
  const {target} = await render();
  assert.match(target.innerHTML, /Labels and distributions changed in different ways/);
  assert.match(target.innerHTML, /Answer changes/);
  assert.match(target.innerHTML, /Probability changes/);
  assert.match(target.innerHTML, /Confidence changes/);
  assert.match(target.innerHTML, /152,500/);
  assert.match(target.innerHTML, /140,260/);
  assert.match(target.innerHTML, /163,120/);
  assert.match(target.innerHTML, /\$0\.006405000/);
  assert.match(target.innerHTML, /client time includes network and local work; it is not pure inference time/i);
  assert.match(target.innerHTML, /Read the machine-readable evidence/);
  assert.match(target.innerHTML, /Read the source-bound findings/);
});

test('rejects any clean-repeat credit or changed parent snapshot', async () => {
  const broken = fixture();
  broken.composites.P2fresh2.cleanRepeatCredit = true;
  let result = await render(broken);
  assert.match(result.target.innerHTML, /role="alert"/);
  assert.match(result.errors[0], /Invalid interrupted composite/);
  broken.composites.P2fresh2.cleanRepeatCredit = false;
  broken.composites.P2fresh2.parentOriginal.score.valid = 18;
  result = await render(broken);
  assert.match(result.errors[0], /Invalid interrupted composite/);
});

test('page wires one accessible Jev prompt section beside Kev', () => {
  assert.equal((page.match(/id="jev-prompt-results"/g) || []).length, 1);
  assert.equal((page.match(/id="jev-prompt-analysis"/g) || []).length, 1);
  assert.match(page, /<section[^>]+id="jev-prompt-analysis"[^>]+aria-labelledby="jev-prompt-title"/);
  assert.match(page, /<h2 id="jev-prompt-title">How did Jev change across three instruction sets\?<\/h2>/);
  assert.match(page, /<a href="#jev-prompt-analysis">Jev prompt case<\/a>/);
  assert.match(page, /<script defer src="\.\/jev-prompts\.js\?v=20261006-native-prompts-v1"><\/script>/);
  assert.ok(page.indexOf('id="kev-prompt-analysis"') < page.indexOf('id="jev-prompt-analysis"'));
  assert.match(page, /<noscript><p class="analysis-caveat" role="alert">/);
});

test('renders an accessible error for missing or inconsistent evidence', async () => {
  const broken = fixture();
  broken.passes.P2.fresh2.outcomes.never_sent = 41;
  let result = await render(broken);
  assert.match(result.target.innerHTML, /role="alert"/);
  assert.match(result.errors[0], /Invalid pass accounting/);
  result = await render(fixture(), false);
  assert.match(result.target.innerHTML, /role="alert"/);
  assert.match(result.errors[0], /unavailable/);
});
