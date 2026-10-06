const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const site = path.join(__dirname, '../public-site');
const source = fs.readFileSync(path.join(site, 'liquid-prompt-chart.js'), 'utf8');
const css = fs.readFileSync(path.join(site, 'liquid-prompt-chart.css'), 'utf8');
const feed = JSON.parse(fs.readFileSync(path.join(site, 'liquid-d1-native-full-findings.json'), 'utf8'));

async function render(value = feed, ok = true, present = true) {
  const target = {innerHTML: '', attributes: {}, setAttribute(name, content) {this.attributes[name] = content;}};
  const requests = [];
  vm.runInNewContext(source, {
    document: {getElementById: id => present && id === 'liquid-prompt-chart' ? target : null},
    fetch: async (url, options) => {
      requests.push({url, options});
      return {ok, json: async () => value};
    }
  });
  await new Promise(resolve => setImmediate(resolve));
  return {target, requests};
}

test('renders nine source-derived comparisons with distinct changed and match counts', async () => {
  const {target, requests} = await render();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, './liquid-d1-native-full-findings.json');
  assert.equal(requests[0].options.cache, 'no-store');
  assert.equal(target.attributes['aria-live'], 'polite');
  assert.equal(target.attributes['aria-busy'], 'false');
  assert.equal((target.innerHTML.match(/class="liquid-prompt-chart__row"/g) || []).length, 9);
  assert.match(target.innerHTML, /Base task.*Classifier instructions/s);
  assert.match(target.innerHTML, /Classifier instructions.*Decision rules/s);
  assert.match(target.innerHTML, /Pass 1.*Pass 2.*Pass 3/s);
  assert.equal((target.innerHTML.match(/4\/60 changed an answer/g) || []).length, 4);
  assert.equal((target.innerHTML.match(/2 lost a full match/g) || []).length, 3);
  assert.match(target.innerHTML, /1 gained a full match/);
  assert.match(target.innerHTML, /same 60 development reviews/);
  assert.match(target.innerHTML, /not 180 independent cases/);
  assert.match(target.innerHTML, /Read the Liquid findings and source hashes/);
});

test('zero values stay visible and are not silently replaced', async () => {
  const changed = structuredClone(feed);
  const pair = changed.matched_prompt_comparisons['fresh2/P0_vs_fresh2/P1'];
  pair.changed_record_count = 0;
  pair.changed_records = [];
  pair.all_four.right_correct = pair.all_four.left_correct;
  pair.all_four.gained_ids = [];
  pair.all_four.lost_ids = [];
  const {target} = await render(changed);
  assert.match(target.innerHTML, /0\/60 changed an answer/);
  assert.match(target.innerHTML, /0 lost a full match/);
  assert.match(target.innerHTML, /0 gained a full match/);
  assert.doesNotMatch(target.innerHTML, /could not be loaded/);
});

test('missing pair, impossible arithmetic and failed fetch show an unavailable state', async () => {
  const missing = structuredClone(feed);
  delete missing.matched_prompt_comparisons['fresh3/P0_vs_fresh3/P2'];
  assert.match((await render(missing)).target.innerHTML, /role="alert".*could not be loaded/s);
  const inconsistent = structuredClone(feed);
  inconsistent.matched_prompt_comparisons['fresh1/P0_vs_fresh1/P2'].all_four.right_correct = 60;
  assert.match((await render(inconsistent)).target.innerHTML, /role="alert".*could not be loaded/s);
  assert.match((await render(feed, false)).target.innerHTML, /role="alert".*could not be loaded/s);
});

test('does not fetch without its placeholder; CSS covers responsive and reduced-motion states', async () => {
  assert.equal((await render(feed, true, false)).requests.length, 0);
  assert.match(css, /@media \(max-width: 650px\)/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(css, /\.liquid-prompt-chart__negative.*justify-content: flex-end/);
});
