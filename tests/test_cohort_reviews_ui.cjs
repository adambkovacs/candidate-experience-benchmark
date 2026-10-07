const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const api = require('../public-site/cohort-reviews.js');
const data = JSON.parse(fs.readFileSync(path.join(root, 'public-site/cross-category-v1.json'), 'utf8'));
const fields = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];

async function mountedPanel(href = 'https://example.test/report') {
  const listeners = new Map(), controls = {}, historyUrls = [];
  const node = () => ({value:'', textContent:'', innerHTML:'', disabled:false, callbacks:new Map(),
    addEventListener(type, callback) { this.callbacks.set(type, callback); },
    dispatchEvent(event) { this.callbacks.get(event.type)?.({target:this}); },
    querySelectorAll() { return []; }});
  for (const id of ['category-filter', 'outcome-category', 'report-lens-count', 'report-lens-note',
    'cohort-review-cohort', 'cohort-review-stratum', 'cohort-review-subset', 'cohort-review-search',
    'cohort-review-count', 'cohort-review-list', 'cohort-review-selected']) controls[id] = node();
  const panel = {innerHTML:'', querySelector:selector => controls[selector.slice(1)]};
  const buttons = ['decision', 'general', 'all'].map(cohort => ({dataset:{cohort},
    setAttribute() {}, addEventListener(type, callback) { this.click = callback; }}));
  let activePanel = false;
  const context = {URL, console, Event, CustomEvent:class {
    constructor(type, options) { this.type=type; this.detail=options.detail; }
  }, location:{href}, history:{replaceState(_state, _title, address) {
    historyUrls.push(address); context.location.href = new URL(address, context.location.href).href;
  }}, fetch:async () => ({ok:true, json:async () => structuredClone(data)}),
  document:{getElementById:id => id === 'cohort-reviews' ? activePanel ? panel : null : controls[id],
    querySelectorAll:() => buttons},
  addEventListener(type, callback) {
    if (!listeners.has(type)) listeners.set(type, []);
    listeners.get(type).push(callback);
  }, dispatchEvent(event) { for (const callback of listeners.get(event.type) || []) callback(event); }};
  context.globalThis = context;
  for (const file of ['model-categories.js', 'report-navigation.js', 'cohort-reviews.js'])
    vm.runInNewContext(fs.readFileSync(path.join(root, 'public-site', file), 'utf8'), context);
  activePanel = true;
  await context.BenchmarkCohortReviews.init();
  return {context, controls, buttons, historyUrls};
}

function independentCounts(runs, review) {
  let disagree = 0;
  let unusable = 0;
  for (const run of runs) {
    const answer = run.cases.find(item => item.id === review.id);
    if (answer.prediction === null) unusable++;
    else if (fields.some(field => answer.prediction[field] !== review.reference[field])) disagree++;
  }
  return {disagree, unusable, match: runs.length - disagree - unusable};
}

test('selects distinct first-P0 configurations without pooling general strata', () => {
  assert.equal(api.validate(data), data);
  for (const [cohort, stratum, count] of [
    ['decision', 'fresh', 7], ['general', 'fresh', 32], ['general', 'historical', 117],
    ['all', 'fresh', 39], ['all', 'historical', 124]
  ]) {
    const runs = api.selectedRuns(data, cohort, stratum);
    assert.equal(runs.length, count);
    assert.equal(new Set(runs.map(run => run.runId)).size, count);
    assert.ok(runs.every(run => run.controls.condition === 'P0'));
    assert.ok(!runs.some(run => run.stratum === 'declared-fresh1-P0') ||
      !runs.some(run => run.stratum === 'historical-first-P0'));
  }
});

test('all 60 rankings independently reconcile disagreement and unusable denominators', () => {
  for (const [cohort, stratum] of [
    ['decision', 'fresh'], ['general', 'fresh'], ['general', 'historical'],
    ['all', 'fresh'], ['all', 'historical']
  ]) {
    const summary = api.summarize(data, cohort, stratum);
    assert.equal(summary.reviews.length, 60);
    assert.equal(summary.positions, summary.denominator * 60);
    let disagree = 0;
    let unusable = 0;
    summary.reviews.forEach((row, index) => {
      const expected = independentCounts(summary.runs, row.review);
      assert.deepEqual({disagree: row.disagree, unusable: row.unusable, match: row.match}, expected);
      assert.equal(row.denominator, summary.denominator);
      assert.equal(row.disagree + row.unusable + row.match, summary.denominator);
      if (index) assert.ok(summary.reviews[index - 1].disagree >= row.disagree);
      disagree += row.disagree;
      unusable += row.unusable;
    });
    assert.equal(summary.disagree, disagree);
    assert.equal(summary.unusable, unusable);
  }
});

test('testimonial, off-topic, and text filters use frozen references and saved feedback', () => {
  const summary = api.summarize(data, 'general', 'fresh');
  const testimonial = api.filterReviews(summary, {subset: 'testimonial'});
  assert.equal(testimonial.length, data.cases.filter(row => row.reference.testimonial_potential === 'yes').length);
  assert.ok(testimonial.every(row => row.testimonial));
  assert.deepEqual(api.filterReviews(summary, {subset: 'off-topic'}).map(row => row.review.id), ['DEV-029']);
  assert.deepEqual(api.filterReviews(summary, {search: 'tiny portions'}).map(row => row.review.id), ['DEV-029']);
  assert.ok(api.filterReviews(summary, {subset: 'disagree'}).every(row => row.disagree > 0));
});

test('unusable positions never become answer differences or invented predictions', () => {
  const summary = api.summarize(data, 'general', 'fresh');
  const row = summary.reviews.find(item => item.unusable > 0);
  assert.ok(row);
  const markup = api.detailMarkup(row, 'general', 'https://example.test/?search=old#review-evidence');
  assert.equal((markup.match(/No usable four-field answer saved for this position\./g) || []).length, row.unusable);
  assert.equal((markup.match(/<td colspan="4">/g) || []).length, row.unusable);
  assert.match(markup, /Frozen proposed reference/);
  assert.match(markup, /Saved status/);
  const changed = structuredClone(data);
  const invalid = changed.runs.find(run => run.cases.some(answer => answer.prediction === null));
  const invalidCase = invalid.cases.find(answer => answer.prediction === null);
  invalidCase.prediction = {...changed.cases.find(item => item.id === invalidCase.id).reference};
  assert.throws(() => api.validate(changed), /Saved answer or status changed/);
  const changedStatus = structuredClone(data);
  const noAnswer = changedStatus.runs.flatMap(run => run.cases).find(answer => answer.prediction === null);
  noAnswer.status = 'ok';
  assert.throws(() => api.validate(changedStatus), /Saved answer or status changed/);
});

test('exact explorer link retains run and review while clearing incompatible filters', () => {
  const url = api.explorerUrl('sample-run', 'DEV-030', 'general',
    'https://example.test/report?cohort=decision&category=tuned&search=old&reviewCohortSubset=off-topic&compareRun=other#review-evidence');
  assert.equal(url, '/report?cohort=general&run=sample-run&case=DEV-030#inspect');
  assert.throws(() => api.explorerUrl('sample-run', 'DEV-999', 'general', 'https://example.test/'), /Unknown case link/);
});

test('every selected run identity is present in the unified case explorer feeds', () => {
  const read = name => JSON.parse(fs.readFileSync(path.join(root, 'public-site', name), 'utf8'));
  const identities = new Set([
    ...read('data-provider-errors-v1.json').runs.map(run => run.id),
    ...read('extended-cases-v1.json').runs.map(run => run.runId),
    ...read('additional-cases-v1.json').runs.map(run => run.runId)
  ]);
  assert.equal(identities.size, 1004);
  assert.ok(data.runs.every(run => identities.has(run.runId)));
});

test('saved links and review copy stay source-bound and escape comment text', () => {
  const summary = api.summarize(data, 'decision', 'fresh');
  const row = summary.reviews.find(item => item.review.id === 'DEV-030');
  const markup = api.detailMarkup(row, 'decision', 'https://example.test/');
  assert.match(markup, /docs\/REFERENCE_REVIEW_V1\.md/);
  assert.match(markup, /needs human adjudication/);
  assert.match(markup, /results\/.*\/.*public-projection\.json|development\.public\.json/);
  const changed = structuredClone(row);
  changed.review.feedback = '<img src=x onerror=alert(1)>';
  assert.match(api.detailMarkup(changed, 'decision', 'https://example.test/'), /&lt;img src=x onerror=alert\(1\)&gt;/);
});

test('report cohort events update the panel and preserve its general stratum without recursion', async () => {
  const ui = await mountedPanel('https://example.test/report?reviewGeneralStratum=historical');
  ui.buttons[1].click();
  assert.equal(ui.controls['cohort-review-cohort'].value, 'general');
  assert.equal(ui.controls['cohort-review-stratum'].value, 'historical');
  assert.equal(new URL(ui.context.location.href).searchParams.get('reviewGeneralStratum'), 'historical');
  assert.match(ui.controls['cohort-review-count'].textContent, /117 distinct first-P0 configurations/);
  ui.buttons[2].click();
  assert.match(ui.controls['cohort-review-count'].textContent, /124 distinct first-P0 configurations/);
  ui.controls['cohort-review-cohort'].value = 'decision';
  const before = ui.historyUrls.length;
  ui.controls['cohort-review-cohort'].dispatchEvent({type:'change'});
  assert.equal(ui.context.BenchmarkReportNavigation.getCohort(), 'decision');
  assert.equal(ui.controls['cohort-review-stratum'].value, 'historical');
  assert.equal(ui.controls['cohort-review-stratum'].disabled, true);
  assert.ok(ui.historyUrls.length - before <= 2, 'one panel update and one navigation update');
});

test('explicit panel deep links synchronize the shared cohort without erasing advanced categories', async () => {
  const linked = await mountedPanel('https://example.test/report?reviewCohort=general&reviewGeneralStratum=historical');
  assert.equal(linked.context.BenchmarkReportNavigation.getCohort(), 'general');
  assert.match(linked.controls['cohort-review-count'].textContent, /117 distinct first-P0 configurations/);
  const custom = await mountedPanel('https://example.test/report?category=tuned&reviewCohort=general');
  assert.equal(new URL(custom.context.location.href).searchParams.get('category'), 'tuned');
  custom.context.dispatchEvent({type:'benchmark:saved-runs-ready', detail:{runs:[]}});
  assert.equal(custom.controls['cohort-review-cohort'].value, 'general');
  assert.match(custom.controls['cohort-review-count'].textContent, /32 distinct first-P0 configurations/);
  custom.controls['cohort-review-stratum'].value = 'historical';
  custom.controls['cohort-review-stratum'].dispatchEvent({type:'change'});
  assert.equal(new URL(custom.context.location.href).searchParams.get('category'), 'tuned');
  custom.controls['category-filter'].value = 'rules';
  custom.controls['category-filter'].dispatchEvent({type:'change'});
  assert.equal(new URL(custom.context.location.href).searchParams.get('category'), 'rules');
  assert.equal(custom.controls['cohort-review-cohort'].value, 'general');
});

test('filtered review counts identify the whole-cohort denominator for outcome totals', async () => {
  const ui = await mountedPanel('https://example.test/report?reviewCohort=general&reviewCohortSubset=testimonial');
  assert.equal(ui.controls['cohort-review-count'].textContent,
    '9 of 60 reviews shown · Across all 60 reviews: 32 distinct first-P0 configurations · 1920 run-review positions · 374 differ · 176 unusable.');
});
