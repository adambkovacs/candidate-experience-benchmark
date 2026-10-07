const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const categorySource = fs.readFileSync(path.join(site, 'model-categories.js'), 'utf8');
const appSource = fs.readFileSync(path.join(site, 'app.js'), 'utf8');
const runs = JSON.parse(fs.readFileSync(path.join(site, 'data-provider-errors-v1.json'), 'utf8')).runs;

function categories() {
  const context = {};
  vm.runInNewContext(categorySource, context);
  return context.BenchmarkCategories;
}

test('purpose can overlap while training lineage remains source-backed and separate', () => {
  const classify = categories().classify;
  const byId = id => classify(runs.find(run => run.id === id));
  assert.equal(byId('typesafe-jev113-v2').category, 'decision');
  assert.deepEqual(Array.from(byId('typesafe-jev113-v2').categories), ['decision']);
  assert.equal(byId('laya-typed-expanded-cpu').interfaceKind, 'native');
  assert.equal(byId('alex-openjev4b').category, 'tuned');
  assert.deepEqual(Array.from(byId('alex-openjev4b').categories), ['tuned','decision']);
  assert.equal(byId('alex-openjev4b').trainingLineage, 'task_finetuned');
  assert.equal(byId('alex-openjev4b').interfaceKind, 'nli');
  assert.equal(byId('openjev-fixed').category, 'general');
  assert.equal(byId('openjev-fixed').trainingLineage, 'unknown');
  assert.equal(byId('openjev-fixed').interfaceKind, 'native');
  assert.equal(byId('openjev-generated-off').interfaceKind, 'generated');
  assert.equal(byId('semif-direct').category, 'general');
  assert.equal(byId('semif-direct').trainingLineage, 'frozen');
  assert.equal(byId('anyjev-qwen06-l0').trainingLineage, 'frozen');
  assert.equal(byId('anyjev-qwen06-l2').category, 'decision');
  assert.deepEqual(Array.from(byId('anyjev-qwen06-l2').categories), ['general','decision']);
  assert.equal(byId('anyjev-qwen06-l2').trainingLineage, 'fitted_head');
  assert.equal(byId('anyjev-qwen06-l2').interfaceKind, 'adapted');
  assert.equal(byId('rules-v1').category, 'rules');
  assert.equal(classify({configuration:'unverified-new-model'}).category, 'unknown');
  assert.equal(classify({configuration:'unverified-new-model'}).trainingLineage, 'unknown');
  assert.equal(classify({configuration:'clef-flash-prepared'}).category, 'decision');
  assert.equal(classify({configuration:'kev-4b-native'}).category, 'decision');
  assert.equal(classify({configuration:'kev-4b-native'}).trainingLineage, 'fitted_head');
  const perplexity = classify({id:'perplexity-decider-native-fresh1-p0',model:'perplexity/pplx-decider-v1-27b'});
  assert.equal(perplexity.category, 'decision');
  assert.equal(perplexity.interfaceKind, 'native');
  assert.equal(perplexity.trainingLineage, 'unknown');
  assert.equal(perplexity.source, 'https://openrouter.ai/perplexity/pplx-decider-v1-27b');
});

test('saved-run category and interface filters retain the fixed 60-record scope', () => {
  const controls = Object.fromEntries([
    'search','condition-filter','surface-filter','family-filter','effort-filter','category-filter','training-filter','interface-filter','sort','include-incomplete','metric'
  ].map(id => [`#${id}`, {value:'',checked:true}]));
  controls['#sort'].value = 'score-desc';
  controls['#metric'].value = 'all_four';
  const document = {querySelector(selector) {return controls[selector] || null;}};
  const instrumented = appSource.replace('  init();\n})();', '  globalThis.__categoriesUi = {state,visibleRuns,modelType};\n})();');
  assert.notEqual(instrumented, appSource);
  const context = {document,URL};
  vm.runInNewContext(categorySource, context);
  vm.runInNewContext(instrumented, context);
  context.__categoriesUi.state.data = {runs};
  controls['#category-filter'].value = 'general';
  controls['#interface-filter'].value = 'native';
  let shown = context.__categoriesUi.visibleRuns();
  assert.ok(shown.some(run => run.id === 'openjev-fixed'));
  assert.ok(shown.some(run => run.id === 'semif-direct'));
  assert.ok(!shown.some(run => run.id === 'typesafe-jev113-v2'));
  assert.ok(!shown.some(run => run.id === 'openjev-generated-off'));
  controls['#category-filter'].value = 'decision';
  controls['#interface-filter'].value = '';
  shown = context.__categoriesUi.visibleRuns();
  assert.ok(shown.some(run => run.id === 'typesafe-jev113-v2'));
  assert.ok(shown.some(run => run.id === 'alex-openjev4b'));
  assert.ok(shown.every(run => context.__categoriesUi.modelType(run).categories.includes('decision')));
  controls['#category-filter'].value = '';
  controls['#training-filter'].value = 'fitted_head';
  shown = context.__categoriesUi.visibleRuns();
  assert.ok(shown.some(run => run.id === 'anyjev-qwen06-l2'));
  assert.ok(shown.every(run => context.__categoriesUi.modelType(run).trainingLineage === 'fitted_head'));
  controls['#category-filter'].value = 'rules';
  controls['#training-filter'].value = '';
  shown = context.__categoriesUi.visibleRuns();
  assert.deepEqual(Array.from(shown, run => run.id), ['rules-v1']);
});

test('both public views load the shared mapping before rendering category controls', () => {
  const html = fs.readFileSync(path.join(site, 'index.html'), 'utf8');
  const repeats = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
  assert.ok(html.indexOf('model-categories.js') < html.indexOf('app.js'));
  assert.ok(html.indexOf('model-categories.js') < html.indexOf('repeats.js'));
  assert.match(html, /id="category-filter"/);
  assert.match(html, /id="training-filter"/);
  assert.match(html, /id="interface-filter"/);
  assert.match(repeats, /id="repeat-category"/);
  assert.match(repeats, /id="repeat-training"/);
  assert.match(repeats, /id="repeat-interface"/);
  assert.match(repeats, /modelType\(s\)\.categories \|\| \[modelType\(s\)\.category\]/);
  assert.match(repeats, /modelType\(s\)\.trainingLineage === trainingLineage/);
  assert.match(repeats, /modelType\(s\)\.interfaceKind === interfaceKind/);
  assert.match(html, /Fresh native OpenJev P0 results/);
  assert.doesNotMatch(html, /Fresh native Jev P0 results/);
});
