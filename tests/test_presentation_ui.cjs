// Exercises the deck that public-site/presentation.html actually loads: its script tags, its section ids and the
// Reveal boot in deck/deck.js. Runs in plain node with stubs (no browser), like the other *_ui.cjs tests.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.resolve(__dirname, '../public-site');
const html = fs.readFileSync(path.join(site, 'presentation.html'), 'utf8');
const localScripts = [...html.matchAll(/<script[^>]*\ssrc="\.\/([^"]+)"/g)].map(m => m[1]);
const sectionIds = [...html.matchAll(/<section[^>]*\sid="([^"]+)"/g)].map(m => m[1]);

test('every script presentation.html loads exists and parses, and the deck scripts are among them', () => {
  assert.ok(localScripts.includes('deck/deck.js'));
  assert.ok(localScripts.some(s => s.startsWith('deck/content/')));
  assert.ok(!localScripts.some(s => /meetup-presentation/.test(s)), 'the retired deck script must stay unloaded');
  for (const src of localScripts) {
    const file = path.join(site, src);
    assert.ok(fs.existsSync(file), `missing ${src}`);
    assert.doesNotThrow(() => new vm.Script(fs.readFileSync(file, 'utf8'), {filename: src}), src);
  }
});

test('slide ids are unique and every in-deck link points at a real slide', () => {
  assert.ok(sectionIds.length >= 30, `only ${sectionIds.length} sections`);
  assert.equal(new Set(sectionIds).size, sectionIds.length, 'duplicate section id');
  const links = [...html.matchAll(/href="#\/([^"/]+)"/g)].map(m => m[1]);
  assert.ok(links.length >= 15, `only ${links.length} deck links`); // v3 appendix has 15 slides
  for (const id of links) assert.ok(sectionIds.includes(id), `link #/${id} has no slide`);
});

// Boots the real deck.js against a stub Reveal and reports what it did for a given page URL.
function boot(search, hash, currentSlideId) {
  const calls = {initialize: null, slide: null, ready: []};
  const Reveal = {
    initialize(config) { calls.initialize = config; },
    isReady: () => true,
    on(type, fn) { if (type === 'ready') calls.ready.push(fn); },
    sync() {}, getProgress: () => 0,
    getCurrentSlide: () => ({id: currentSlideId}),
    getIndices: () => ({h: 4, v: 0}),
    slide(h, v, f) { calls.slide = [h, v, f]; },
  };
  const window = {Reveal, RevealNotes: {}, DeckData: {ready: Promise.resolve()},
    DeckMotion: {still: () => false, wire() {}, prepare: () => Promise.resolve()}, DeckScene: {start: () => Promise.resolve()}};
  window.window = window;
  const context = {window, location: {search, hash}, document: {querySelector: () => null}};
  vm.runInNewContext(fs.readFileSync(path.join(site, 'deck/deck.js'), 'utf8'), context);
  return {calls, ready: window.DeckReady};
}

test('deck boots with hash navigation on, and a reload on "#/slide/step" restores the step', async () => {
  const id = sectionIds[1];
  const {calls, ready} = boot('', `#/${id}/3`, id);
  assert.equal(calls.initialize.hash, true);
  assert.equal(calls.initialize.respondToHashChanges, true);
  assert.equal(calls.initialize.controls, true);
  await ready;
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls.slide, [4, 0, 3]);
});

test('a reload does not drag the presenter back when they already moved to another slide', async () => {
  const {calls, ready} = boot('', `#/${sectionIds[1]}/3`, sectionIds[2]);
  await ready;
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.slide, null);
});

test('print view waits for data and scenes before it initializes Reveal', async () => {
  const {calls, ready} = boot('?print-pdf', '', sectionIds[0]);
  assert.equal(calls.initialize, null, 'initialized before data and scenes were ready');
  await ready;
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(calls.initialize);
});
