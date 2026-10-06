const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
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
    unknownUpperBoundUsd: outcomes.unknown_cost_http_429 ? '0.001344000' : '0',
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
  return {
    sourceBindings: [{path: 'results/route-audits/jev/fresh1/completion.json', sha256: 'a'.repeat(64)}],
    passes: {
      P1: {
        fresh1: pass('complete', 60, 54, {valid: 60}, 152500, '0.006405000', 32.26),
        fresh2: pass('complete', 59, 53, {valid: 59, invalid_native_distribution: 1}, 152500, '0.006405000', 35.99)
      },
      P2: {
        fresh1: pass('complete', 60, 54, {valid: 60}, 163120, '0.006851040', 32.84),
        fresh2: pass('stopped', 17, 15, {valid: 17, unknown_cost_http_429: 1, never_sent: 42}, 46207, '0.001940694', 10.30)
      }
    },
    comparisons: {
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

test('renders complete first passes and derives the strict P1 repeat', async () => {
  const {target, requests, errors} = await render();
  assert.deepEqual(errors, []);
  assert.equal(requests[0].url, './jev-native-prompt-findings.json');
  assert.equal(requests[0].options.cache, 'no-store');
  assert.equal(target['aria-busy'], 'false');
  assert.match(target.innerHTML, /first complete P1 and P2 passes both scored 54\/60/);
  assert.match(target.innerHTML, /second P1 pass scored <strong>53\/60<\/strong> with 59 valid responses/);
  assert.match(target.innerHTML, /0 reviews had a changed answer/);
  assert.match(target.innerHTML, /invalid native probability distribution/);
  assert.equal((target.innerHTML.match(/class="condition-score">54<small> \/ 60<\/small>/g) || []).length, 2);
});

test('accepts the generated source-bound feed', async () => {
  const actual = JSON.parse(fs.readFileSync('public-site/jev-native-prompt-findings.json', 'utf8'));
  const {target, errors} = await render(actual);
  assert.deepEqual(errors, []);
  assert.match(target.innerHTML, /both scored 54\/60/);
  assert.match(target.innerHTML, /second P1 pass scored <strong>53\/60<\/strong>/);
  assert.match(target.innerHTML, /0 reviews had a changed answer/);
  assert.match(target.innerHTML, /saved 17 valid responses/);
  assert.match(target.innerHTML, /left 42 reviews unsent/);
});

test('keeps stopped P2 out of completed score cards and rankings', async () => {
  const {target} = await render();
  assert.match(target.innerHTML, /saved 17 valid responses/);
  assert.match(target.innerHTML, /retained 1 request with an unknown charge/);
  assert.match(target.innerHTML, /left 42 reviews unsent/);
  assert.match(target.innerHTML, /coverage accounting, not a completed score or ranking result/);
  assert.doesNotMatch(target.innerHTML, /class="condition-score">15/);
});

test('derives changed values from an internally consistent fixture', async () => {
  const changed = fixture();
  changed.passes.P1.fresh1.score.allFour = 52;
  changed.passes.P2.fresh1.score.allFour = 51;
  changed.passes.P1.fresh2.score.allFour = 50;
  changed.comparisons.P1P2fresh1.fourFieldVectorChangedIds = ['DEV-002', 'DEV-013'];
  changed.comparisons.P1P2fresh1.fields.sentiment.choiceChangedIds = ['DEV-002', 'DEV-013'];
  changed.comparisons.P1repeat.fourFieldVectorChangedIds = ['DEV-003'];
  changed.comparisons.P1repeat.fields.sentiment.choiceChangedIds = ['DEV-003'];
  const {target, errors} = await render(changed);
  assert.deepEqual(errors, []);
  assert.match(target.innerHTML, /first complete P1 and P2 passes scored 52\/60 for P1 and 51\/60 for P2/);
  assert.match(target.innerHTML, /At least one answer changed on 2 reviews/);
  assert.match(target.innerHTML, /second P1 pass scored <strong>50\/60/);
  assert.match(target.innerHTML, /1 review had a changed answer/);
  assert.doesNotMatch(target.innerHTML, /both scored 54\/60/);
});

test('separates answer changes from probabilities, confidence, usage, and timing', async () => {
  const {target} = await render();
  assert.match(target.innerHTML, /Labels and distributions changed in different ways/);
  assert.match(target.innerHTML, /Answer changes/);
  assert.match(target.innerHTML, /Probability changes/);
  assert.match(target.innerHTML, /Confidence changes/);
  assert.match(target.innerHTML, /152,500/);
  assert.match(target.innerHTML, /163,120/);
  assert.match(target.innerHTML, /\$0\.006405000/);
  assert.match(target.innerHTML, /client time includes network and local work; it is not pure inference time/i);
  assert.match(target.innerHTML, /Read the machine-readable evidence/);
  assert.match(target.innerHTML, /Read the source-bound findings/);
});

test('page wires one accessible Jev prompt section beside Kev', () => {
  assert.equal((page.match(/id="jev-prompt-results"/g) || []).length, 1);
  assert.equal((page.match(/id="jev-prompt-analysis"/g) || []).length, 1);
  assert.match(page, /<section[^>]+id="jev-prompt-analysis"[^>]+aria-labelledby="jev-prompt-title"/);
  assert.match(page, /<h2 id="jev-prompt-title">What happened when Jev received two native instruction sets\?<\/h2>/);
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
