const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const code = fs.readFileSync(path.join(root, 'public-site/agreement-policy.js'), 'utf8');
const publicBytes = fs.readFileSync(path.join(root, 'public-site/native-agreement-policy-v1.json'));
const findingsBytes = fs.readFileSync(path.join(root, 'results/native-agreement-policy-v1/findings.json'));
const data = JSON.parse(publicBytes);
const context = {
  document: {getElementById: () => null},
  location: {href: 'https://example.test/?cohort=decision#agreement-policy'},
  URL, console,
};
context.globalThis = context;
vm.runInNewContext(code, context);
const policy = context.BenchmarkAgreementPolicy;
const models = new Map(data.components.map(model => [model.id, model]));

test('public copy is byte-identical to the reviewed findings', () => {
  assert.deepEqual(publicBytes, findingsBytes);
  assert.equal(policy.validate(data), data);
  assert.equal(data.components.length, 7);
  assert.equal(data.pairs.length, 21);
  assert.equal(data.inference_requests, 0);
});

test('validation requires every fixed source-order pair and exact 60-review partitions', () => {
  const omitted = structuredClone(data);
  omitted.pairs.pop();
  assert.throws(() => policy.validate(omitted), /header changed/);
  const reordered = structuredClone(data);
  [reordered.pairs[0], reordered.pairs[1]] = [reordered.pairs[1], reordered.pairs[0]];
  assert.throws(() => policy.validate(reordered), /source order/);
  const drift = structuredClone(data);
  drift.pairs[0].deferred_ids[0] = drift.pairs[0].accepted_ids[0];
  assert.throws(() => policy.validate(drift), /counts or review IDs/);
  const price = structuredClone(data);
  price.pairs[0].known_two_run_development_cost_usd = 'unpriced';
  assert.throws(() => policy.validate(price), /counts or review IDs/);
});

test('pair display shows accepted coverage, retained errors, deferrals and exact source links', () => {
  const pair = data.pairs.find(row => row.accepted_all_four_error_count > 0);
  assert.ok(pair);
  const html = policy.renderPair(pair, models);
  assert.match(html, new RegExp(`${pair.accepted_count}<span>/60`));
  assert.match(html, new RegExp(`Accepted with an error`));
  assert.match(html, new RegExp(`${pair.deferred_count} deferred for human review`));
  assert.match(html, /known charge for both saved 60-review development runs/i);
  assert.match(html, /excludes human review, smoke requests/i);
  assert.ok(html.includes(`review=${pair.accepted_all_four_error_ids[0]}`));
  assert.ok(html.includes(`review=${pair.deferred_ids[0]}`));
  assert.ok(html.includes(models.get(pair.left).source_path));
  assert.ok(html.includes(models.get(pair.right).source_path));
  assert.match(html, /native-agreement-policy-v1\.json/);
});

test('all 21 pairs remain visible in source order, with no ranked winner', () => {
  const selected = policy.pairKey(data.pairs[0]);
  const html = policy.renderTable(data, models, selected);
  assert.equal((html.match(/data-pair=/g) || []).length, 21);
  assert.equal((html.match(/class="selected"/g) || []).length, 1);
  assert.ok(html.indexOf(models.get(data.pairs[0].left).display_name) <
            html.indexOf(models.get(data.pairs.at(-1).right).display_name));
  assert.match(html, /lower error counts can reflect more deferrals/i);
  assert.doesNotMatch(html, /best pair|winner|recommend/i);
});

test('review deep links retain report query and target the existing case view', () => {
  assert.equal(policy.reviewUrl('DEV-029'),
    '/?cohort=decision&review=DEV-029#review-evidence');
});


test('evidence link clears filters that could hide its requested review', () => {
  context.location.href = 'https://example.test/?cohort=decision&reviewSubset=testimonial&reviewModel=clef&reviewField=sentiment&reviewSearch=unrelated&agreementPair=liquid%3A%3Atev#agreement-policy';
  const target = new URL(policy.reviewUrl('DEV-002'), 'https://example.test');
  assert.equal(target.searchParams.get('review'), 'DEV-002');
  for (const key of ['reviewSubset', 'reviewModel', 'reviewField', 'reviewSearch']) {
    assert.equal(target.searchParams.has(key), false);
  }
  assert.equal(target.searchParams.get('cohort'), 'decision');
  assert.equal(target.searchParams.get('agreementPair'), 'liquid::tev');
  assert.equal(target.hash, '#review-evidence');
});
