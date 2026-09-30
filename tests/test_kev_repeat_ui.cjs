const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('public-site/repeats.js', 'utf8');
const saved = JSON.parse(fs.readFileSync('public-site/kev-native-repeats.json', 'utf8'));
async function render(feed = saved) {
  const elements = new Map();
  const document = {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {innerHTML:'', textContent:'', value: id === 'repeat-config' ? 'kev-openrouter-native-p0' : id === 'repeat-field' ? 'allFour' : 'P0', addEventListener(type, fn) {this[type]=fn;}});
    return elements.get(id);
  }};
  const fetch = async url => ({ok:true, json:async () => url === './kev-native-repeats.json' ? feed : {series:[]}});
  vm.runInNewContext(source, {document, fetch});
  await new Promise(resolve => setImmediate(resolve));
  return id => document.getElementById(id);
}
test('Kev shows two scored passes and preserves interrupted status', async () => {
  const el = await render();
  assert.match(el('repeat-lead').textContent, /2 of 3/);
  assert.equal((el('repeat-chart').innerHTML.match(/<meter /g)||[]).length, 2);
  assert.match(el('repeat-chart').innerHTML, /Interrupted; unscored/);
  assert.doesNotMatch(el('repeat-chart').innerHTML, /Three-pass range: <strong>/);
  assert.match(el('repeat-delta-intro').textContent, /P1 and P2.*pending/);
});
test('Kev usage and confidence retain definitions and real numbers', async () => {
  const el = await render();
  assert.match(el('repeat-usage-body').innerHTML, /111,986/);
  assert.match(el('repeat-usage-body').innerHTML, /17,350/);
  assert.match(el('repeat-usage-body').innerHTML, /0\.00470341/);
  assert.match(el('repeat-interpretation').innerHTML, /Reported confidence/);
  assert.match(el('repeat-interpretation').innerHTML, /not calibrated/);
  assert.match(el('repeat-flips').innerHTML, /0 \/ 60 changed/);
});
test('Kev rejects inconsistent completed counts', async () => {
  const feed=structuredClone(saved);feed.completedPasses=3;
  const el=await render(feed);
  assert.match(el('repeat-results').innerHTML, /could not be loaded/);
});

test('interrupted Kev usage separates known charges and unknown bound', async () => {
  const feed=structuredClone(saved);
  feed.passes.fresh3.outcomes={valid:59,transportErrorUnknownOutcome:1,neverSent:0};
  feed.passes.fresh3.knownActualProviderCostUsd='0.004624830';
  feed.passes.fresh3.usage={inputTokens:110115,outputTokens:17062,clientRequestSeconds:{total:118.756260290,unknownAttempt:60.435302333}};
  const el=await render(feed);
  assert.match(el('repeat-lead').textContent,/59 valid responses, 1 unknown outcome and 0 comments not sent/);
  const usage=el('repeat-usage-body').innerHTML;
  assert.match(usage,/110,115/); assert.match(usage,/17,062/);
  assert.match(usage,/60 attempted/); assert.match(usage,/0.00462483/);
  assert.match(usage,/Unknown charge up to/); assert.match(usage,/60.4 timeout/);
});
test('incomplete Kev cannot expose a three-pass range or incomplete pair', async () => {
  const feed=structuredClone(saved);
  feed.threePassSummary={P0:{allFour:{range:[1,60]}}};
  feed.repeatComparisons.fresh1_to_fresh3={denominator:60,recordsWithIdenticalFourFields:0,fieldAgreement:{sentiment:0}};
  const el=await render(feed);
  assert.doesNotMatch(el('repeat-chart').innerHTML,/Three-pass range: <strong>/);
  assert.doesNotMatch(el('repeat-flips').innerHTML,/Fresh pass 1 to Fresh pass 3/);
});
