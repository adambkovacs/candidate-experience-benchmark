const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'public-site', 'index.html'), 'utf8');
const source = fs.readFileSync(path.join(root, 'public-site', 'app.js'), 'utf8');

function fixture() {
  const elements = {
    '#overview-condition': {value: 'P0'},
    '#overview-surface': {value: 'all'},
    '#overview-count': {textContent: ''},
    '#overview-rows': {innerHTML: '', querySelectorAll() { return []; }},
    '#overview-toggle': {hidden: false, textContent: '', setAttribute() {}},
  };
  const instrumented = source.replace('  init();\n})();', '  globalThis.__overview = {state,renderOverview};\n})();');
  assert.notEqual(instrumented, source);
  const context = {document: {querySelector: selector => elements[selector]}};
  vm.runInNewContext(instrumented, context, {filename: 'app.js'});
  context.__overview.state.data = {runs: [
    {id: 'hosted', condition: 'P0', complete: true, records: 60, valid: 60, metrics: {all_four: 58}, surface: 'OpenRouter', model: 'Hosted'},
    {id: 'typesafe-jev113-v2', condition: 'P0', complete: true, records: 60, valid: 60, metrics: {all_four: 54}, surface: 'TypeSafe API', model: 'Jev'},
    {id: 'semif-direct', condition: 'P0', complete: true, records: 60, valid: 60, metrics: {all_four: 36}, surface: 'Local / specialist', model: 'SemIf'},
    {id: 'laya-expanded', condition: 'P0', complete: true, records: 60, valid: 0, metrics: {all_four: 0}, surface: 'Local / specialist', model: 'Laya'},
    {id: 'semif-partial', condition: 'P0', complete: false, records: 59, valid: 57, metrics: {all_four: 42}, surface: 'Local / specialist', model: 'SemIf'},
  ]};
  return {ui: context.__overview, elements};
}

test('ranking defaults to all routes and points to saved specialist outcomes', () => {
  assert.match(html, /<select id="overview-surface"><option value="all">All routes<\/option>/);
  assert.match(html, /id="overview-specialists"[^>]*>See local specialists/);
  assert.match(html, /A complete run saved a result for all 60 comments/);
  assert.doesNotMatch(html, /id="overview-hosted"/);
  const {ui, elements} = fixture();
  ui.renderOverview();
  assert.match(elements['#overview-count'].textContent, /4 of 4 complete P0 runs shown/);
  assert.match(elements['#overview-rows'].innerHTML, /semif-direct/);
  assert.match(elements['#overview-rows'].innerHTML, /laya-expanded/);
  assert.doesNotMatch(elements['#overview-rows'].innerHTML, /semif-partial/);
});

test('local route filter keeps complete specialists including invalid outcomes', () => {
  const {ui, elements} = fixture();
  elements['#overview-surface'].value = 'local';
  ui.renderOverview();
  assert.match(elements['#overview-count'].textContent, /2 of 2 complete local specialist P0 runs shown/);
  assert.match(elements['#overview-rows'].innerHTML, /semif-direct/);
  assert.match(elements['#overview-rows'].innerHTML, /laya-expanded/);
  assert.doesNotMatch(elements['#overview-rows'].innerHTML, /hosted/);
  assert.doesNotMatch(elements['#overview-rows'].innerHTML, /typesafe-jev113-v2/);
  elements['#overview-surface'].value = 'hosted';
  ui.renderOverview();
  assert.match(elements['#overview-count'].textContent, /2 of 2 complete hosted \/ API P0 runs shown/);
  assert.doesNotMatch(elements['#overview-rows'].innerHTML, /semif-direct/);
});
