const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(root, 'public-site/findings.json'), 'utf8'));
const script = fs.readFileSync(path.join(root, 'public-site/findings.js'), 'utf8');
const elements = new Map();
let onReady;
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, {innerHTML: '', textContent: ''});
    return elements.get(id);
  },
  addEventListener(event, callback) {
    if (event === 'DOMContentLoaded') onReady = callback;
  }
};
const errors = [];
const context = {
  document,
  fetch: async () => ({ok: true, json: async () => data}),
  console: {error: (...args) => errors.push(args)},
  URL,
  encodeURIComponent
};
vm.runInNewContext(script, context, {filename: 'findings.js'});
assert.equal(typeof onReady, 'function');

(async () => {
  await onReady();
  const html = id => document.getElementById(id).innerHTML;
  const text = id => document.getElementById(id).textContent;
  assert.deepEqual(errors, [], 'renderer must load without errors');
  assert.match(text('prompt-headline'), /21 of 38/);
  assert.match(html('finding-prompts'), /38 paired setups/);
  assert.match(html('finding-prompts'), /Pair report/);
  assert.match(html('finding-jev'), /DEV-029/);
  assert.match(html('finding-jev'), /case=DEV-029#inspect/);
  assert.match(html('finding-jev'), /restaurant review/i);
  assert.match(html('finding-cost'), /24 runs/);
  assert.equal((html('finding-cost').match(/fill="#176b5f"/g) || []).length, 9);
  assert.equal((html('finding-cost').match(/fill="#b75f43"/g) || []).length, 15);
  assert.match(html('finding-hard'), /A friend told me/);
  assert.match(html('finding-hard'), /30 \+ 0 \/ 38/);
  assert.match(html('finding-hard'), /case=DEV-013#inspect/);
  process.stdout.write('Findings UI data integration passed.\n');
})().catch(error => {console.error(error);process.exitCode = 1;});
