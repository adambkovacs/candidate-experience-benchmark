const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('public-site/kev-prompts.js', 'utf8');
const page = fs.readFileSync('public-site/explore.html', 'utf8');
const fields = {
  sentiment: [53, 54],
  follow_up_needed: [58, 53],
  serious_concern_reported: [55, 55],
  testimonial_potential: [58, 59]
};

function fixture() {
  const condition = (name, allFour, side) => ({
    completedPasses: 3,
    plannedPasses: 3,
    passOrder: ['fresh1', 'fresh2', 'fresh3'],
    passes: Object.fromEntries(['fresh1', 'fresh2', 'fresh3'].map((pass, index) => [pass, {
      completionStatus: 'complete',
      score: {denominator: 60, valid: 60, allFour,
        fields: Object.fromEntries(Object.entries(fields).map(([key, values]) => [key, values[side]]))},
      usage: {
        inputTokens: side ? 134246 : 123986,
        outputTokens: side ? 17365 : 17339,
        actualProviderCostUsd: side ? '0.005638332' : '0.005207412',
        clientRequestSeconds: {total: (side ? 54.1 : 51.4) + index / 10,
          median: side ? 0.88 : 0.82, p95: side ? 1.05 : 1.08,
          kind: 'client_observed_request'}
      }
    }])),
    repeatComparisons: [['fresh1','fresh2'],['fresh1','fresh3'],['fresh2','fresh3']].map(([from,to]) => ({
      from, to, denominator: 60, fourFieldVectorChanges: 0,
      nativeProbabilityDictionaryChanges: 0, vendorConfidenceChanges: 0
    })),
    repeatVariation: {available: true, allFourRange: [allFour, allFour],
      fieldRanges: Object.fromEntries(Object.entries(fields).map(([key, values]) => [key, [values[side], values[side]]]))}
  });
  const changed = ['DEV-001','DEV-005','DEV-022','DEV-030','DEV-035','DEV-041','DEV-059'];
  return {
    schema: 'kev-native-prompt-findings-v1', denominator: 60,
    conditionOrder: ['P1','P2'],
    nativePromptEquivalence: {verified: true,
      meaning: 'P1 and P2 share feedback, policy, criteria, labels, label order, route, and parser. Only each native Choice question instruction differs.',
      wireEquivalence: 'Native Choice analogues; not byte-identical chat prompts.'},
    conditions: {P1: condition('P1', 49, 0), P2: condition('P2', 46, 1)},
    pairedP1P2: ['fresh1','fresh2','fresh3'].map(stage => ({stage, denominator: 60,
      fourFieldVectorChanges: 7, fourFieldVectorChangedIds: changed,
      nativeProbabilityDictionaryChanges: 60, vendorConfidenceChanges: 60,
      scoreDeltaP2MinusP1: {allFour: -3,
        fields: {sentiment: 1, follow_up_needed: -5, serious_concern_reported: 0, testimonial_potential: 1}}})),
    historicalP0: {controlsVerified: true, interruptedThirdExcluded: true,
      cleanComparisons: {fresh1: {score: {allFour: 48}}, fresh2: {score: {allFour: 48}}}},
    interpretation: {timing: 'Client-observed request duration includes network and local work; it is not provider inference time.'},
    sourceBindings: [{path: 'results/route-audits/native-variants-full-v1-20261006/kev-openrouter-native-p1-choice-v1/fresh1/completion.json', sha256: 'a'.repeat(64)}]
  };
}

async function render(feed = fixture(), responseOk = true) {
  const target = {innerHTML: '', textContent: '', setAttribute(name, value) {this[name] = value;}};
  const requests = [];
  const errors = [];
  const fetch = async (url, options) => {
    requests.push({url, options});
    return {ok: responseOk, status: responseOk ? 200 : 500, json: async () => feed};
  };
  vm.runInNewContext(source, {
    document: {getElementById: id => id === 'kev-prompt-results' ? target : null},
    fetch, console: {error: error => errors.push(String(error))}, Intl
  });
  await new Promise(resolve => setImmediate(resolve));
  return {target, requests, errors};
}

test('renders the three-pass P1/P2 comparison and follow-up tradeoff', async () => {
  const {target, requests} = await render();
  assert.equal(requests[0].url, './kev-native-prompt-findings.json');
  assert.equal(requests[0].options.cache, 'no-store');
  assert.equal(target['aria-live'], 'polite');
  assert.equal(target['aria-busy'], 'false');
  assert.match(target.innerHTML, /Classifier instructions \(P1\)/);
  assert.match(target.innerHTML, /Decision rules \(P2\)/);
  assert.match(target.innerHTML, /49<small> \/ 60<\/small>/);
  assert.match(target.innerHTML, /46<small> \/ 60<\/small>/);
  assert.match(target.innerHTML, /7 of 60 reviews changed/);
  assert.match(target.innerHTML, /Follow-up.*58.*53.*−5/s);
  assert.match(target.innerHTML, /DEV-001.*DEV-059/s);
  assert.equal((target.innerHTML.match(/aria-label="P[12] [^"]+: \d+ out of 60"/g) || []).length, 10);
});

test('headline follows changed but internally consistent feed values', async () => {
  const changed = fixture();
  for (const pass of ['fresh1', 'fresh2', 'fresh3']) {
    changed.conditions.P1.passes[pass].score.allFour = 50;
    changed.conditions.P2.passes[pass].score.allFour = 47;
    changed.conditions.P1.passes[pass].score.fields.follow_up_needed = 56;
    changed.conditions.P2.passes[pass].score.fields.follow_up_needed = 51;
  }
  changed.conditions.P1.repeatVariation.allFourRange = [50, 50];
  changed.conditions.P2.repeatVariation.allFourRange = [47, 47];
  for (const pair of changed.pairedP1P2) {
    pair.fourFieldVectorChanges = 8;
    pair.fourFieldVectorChangedIds = [...pair.fourFieldVectorChangedIds, 'DEV-060'];
  }
  const {target, errors} = await render(changed);
  assert.deepEqual(errors, []);
  assert.match(target.innerHTML, /P1 scored 50\/60; P2 scored 47\/60/);
  assert.match(target.innerHTML, /8 of 60 reviews changed at least one answer/);
  assert.match(target.innerHTML, /follow-up: P1 matched 56 references and P2 matched 51, a change of −5/);
  assert.doesNotMatch(target.innerHTML, /P1 scored 49\/60; P2 scored 46\/60/);
  assert.doesNotMatch(target.innerHTML, /same seven review IDs/);
});

test('page wires one labelled Kev section, navigation link, and deferred renderer', () => {
  assert.equal((page.match(/id="kev-prompt-results"/g) || []).length, 1);
  assert.equal((page.match(/id="kev-prompt-analysis"/g) || []).length, 1);
  assert.match(page, /<section[^>]+id="kev-prompt-analysis"[^>]+aria-labelledby="kev-prompt-title"/);
  assert.match(page, /<h2 id="kev-prompt-title">What changed when Kev received different decision instructions\?<\/h2>/);
  assert.match(page, /<a href="#kev-prompt-analysis">Kev prompt case<\/a>/);
  assert.match(page, /<script defer src="\.\/kev-prompts\.js\?v=20261006-native-prompts-v1"><\/script>/);
  assert.match(page, /<noscript><p class="analysis-caveat" role="alert">/);
});

test('shows zero repeat changes, measured usage, cost, and timing limits', async () => {
  const {target} = await render();
  assert.match(target.innerHTML, /zero answer, probability-dictionary, and vendor-confidence changes/);
  assert.match(target.innerHTML, /371,958/);
  assert.match(target.innerHTML, /402,738/);
  assert.match(target.innerHTML, /52,017/);
  assert.match(target.innerHTML, /\$0\.015622236/);
  assert.match(target.innerHTML, /client-observed/i);
  assert.match(target.innerHTML, /not provider inference time/i);
  assert.match(target.innerHTML, /<details/);
  assert.match(target.innerHTML, /Read the source-bound findings/);
  assert.match(target.innerHTML, /Read the machine-readable evidence/);
});

test('renders an accessible error state for incomplete or unavailable evidence', async () => {
  const broken = fixture();
  broken.conditions.P2.passes.fresh3.score.allFour = 51;
  let result = await render(broken);
  assert.match(result.target.innerHTML, /role="alert"/);
  assert.match(result.target.textContent || result.target.innerHTML, /could not be loaded/i);
  assert.match(result.errors[0], /Score range mismatch/);
  result = await render(fixture(), false);
  assert.match(result.target.innerHTML, /role="alert"/);
  assert.match(result.errors[0], /unavailable/);
});
