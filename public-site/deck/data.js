/* Source-bound data layer. Every number on a slide resolves from a public-site JSON feed.
   Bind with data-source="<feed>.json#<path>" (numbers) or data-text-source (labels). Feeds are paths under public-site/,
   for example findings.json or deck/data/answer.json. Path grammar: dot keys, [3] indexes, ["0.9"] quoted keys,
   [key=value,key2=value2] finds.
   Failures are loud: an alert status line, an orange outline on the element, and console.error. */
(() => {
  'use strict';
  const CORE = ['disputed-reviews-v1.json', 'native-agreement-policy-v1.json', 'jev-confidence-findings.json', 'findings.json',
    'extended-cases-v1.json', 'codex-fresh-repeats.json', 'subscription-price-estimates.json'];
  const FIELDS = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const base = new URL('../', document.currentScript.src); // feeds live in public-site/
  const cache = new Map();
  const failures = new Set();

  // Offline copy: other scripts (content.js) fetch deck/data and deck/content JSON directly, so serve inlined feeds to them too.
  const inlined = new Map([...document.querySelectorAll('script[type="application/json"][data-feed]')].map(s => [new URL(s.dataset.feed, base).href, s]));
  if (inlined.size) {
    const realFetch = window.fetch;
    window.fetch = (input, init) => {
      const block = inlined.get(typeof input === 'string' ? input : input.url ?? String(input));
      return block ? Promise.resolve(new Response(block.textContent, { headers: { 'Content-Type': 'application/json' } })) : realFetch(input, init);
    };
  }

  function report(message) {
    failures.add(message);
    document.documentElement.dataset.deckData = 'error';
    let line = document.getElementById('deck-data-status');
    if (!line) {
      line = Object.assign(document.createElement('p'), { id: 'deck-data-status', className: 'd-data-status' });
      line.setAttribute('role', 'alert');
      document.body.append(line);
    }
    line.textContent = `Data feed problem: ${[...failures].join(' · ')}. Affected numbers are outlined in orange.`;
    console.error(`[deck-data] ${message}`);
  }

  // ponytail: loads only the feeds a deck references; extended-cases-v1.json is 6.7 MB, so nothing preloads "just in case".
  function feed(name) {
    // Directory segments allow no dots, so ".." can never climb out of public-site/.
    if (!/^(?:[\w-]+\/)*[\w.-]+\.json$/.test(name)) return Promise.reject(new Error(`invalid feed name "${name}"`));
    if (!cache.has(name)) {
      // Offline build: presentation-offline.html inlines feeds (see verify/bake-offline.mjs), because Chrome blocks fetch() on file://.
      const block = document.querySelector(`script[type="application/json"][data-feed="${name}"]`);
      const inline = window.__DECK_FEEDS?.[name] ?? (block && JSON.parse(block.textContent));
      if (inline) cache.set(name, Promise.resolve(inline));
    }
    if (!cache.has(name)) {
      cache.set(name, fetch(new URL(name, base)).then(response => {
        if (!response.ok) throw new Error(`${name} returned HTTP ${response.status}`);
        return response.json();
      }));
    }
    return cache.get(name);
  }

  function resolve(root, path) {
    let node = root;
    for (const [, bracket, key] of path.matchAll(/\[([^\]]*)\]|([^.[\]]+)/g)) {
      if (node == null) break;
      if (key !== undefined) node = node[key];
      else if (/^\d+$/.test(bracket)) node = node[Number(bracket)];
      else if (/^(["']).*\1$/.test(bracket)) node = node[bracket.slice(1, -1)];
      else {
        const pairs = bracket.split(',').map(pair => pair.split('='));
        node = Array.isArray(node) ? node.find(item => pairs.every(([k, v]) => String(item?.[k]) === v)) : undefined;
      }
    }
    if (node == null) throw new Error(`no value at "${path}"`);
    return node;
  }

  async function get(source) {
    const [name, path] = source.split('#');
    const json = await feed(name);
    return path ? resolve(json, path) : json;
  }

  // Exact decimal strings (costs) stay exact unless data-round asks for rounding.
  function display(value, el) {
    const number = Number(value);
    if (typeof value === 'boolean' || value === '' || !Number.isFinite(number)) throw new Error(`not a number: ${JSON.stringify(value)}`);
    if (el.dataset.round !== undefined) return number.toFixed(Number(el.dataset.round));
    if (typeof value === 'string') return value;
    return Number.isInteger(number) && Math.abs(number) >= 10000 ? number.toLocaleString('en-US') : String(number);
  }

  const readable = value => value === undefined || value === null ? 'No answer'
    : value === 'insufficient_information' ? 'Insufficient info' : String(value).replace(/_/g, ' ');

  const announce = el => el.dispatchEvent(new CustomEvent('deck:bound', { bubbles: true }));

  async function bindNumber(el) {
    try {
      const text = display(await get(el.dataset.source), el);
      Object.assign(el.dataset, { display: text, value: String(Number(text.replace(/,/g, ''))) });
      el.textContent = text;
      el.classList.remove('is-unbound');
      announce(el);
    } catch (error) {
      el.textContent = '?';
      el.classList.add('is-unbound');
      report(`${el.dataset.source}: ${error.message}`);
    }
  }

  // Labels from feeds (a model's answer, a model name). Shown through readable() unless data-raw is set.
  async function bindText(el) {
    try {
      const value = await get(el.dataset.textSource);
      if (typeof value !== 'string' && typeof value !== 'number') throw new Error(`not text: ${JSON.stringify(value)}`);
      el.textContent = el.dataset.display = el.hasAttribute('data-raw') ? String(value) : readable(value);
      el.classList.remove('is-unbound');
      announce(el);
    } catch (error) {
      el.textContent = '?';
      el.classList.add('is-unbound');
      report(`${el.dataset.textSource}: ${error.message}`);
    }
  }

  async function review(id) {
    const found = resolve(await feed('disputed-reviews-v1.json'), `reviews[id=${id}]`);
    return { id: found.id, feedback: found.feedback, reference: found.reference };
  }

  async function bindReview(el) {
    try {
      el.textContent = (await review(el.dataset.review)).feedback;
      announce(el);
    } catch (error) {
      el.classList.add('is-unbound');
      report(`review ${el.dataset.review}: ${error.message}`);
    }
  }

  // "@feed.json#path" on a scene attribute resolves from the feed: data-scene-highlight to a list of review IDs,
  // data-scene-number to the figure the points form. The source stays in data-scene-*-source for numbers.mjs.
  async function bindScene(section, key) {
    const source = section.dataset[key].slice(1);
    try {
      const value = await get(source);
      if (key === 'sceneHighlight' && !Array.isArray(value)) throw new Error('expected a list of review IDs');
      if (key === 'sceneNumber' && !Number.isFinite(Number(value))) throw new Error(`not a number: ${JSON.stringify(value)}`);
      section.dataset[`${key}Source`] = source;
      section.dataset[key] = Array.isArray(value) ? value.join(',') : String(value);
      announce(section);
    } catch (error) {
      report(`scene ${source}: ${error.message}`);
    }
  }

  // Saved answers per model for one review. disputed-reviews-v1: the seven native fresh1/P0 models.
  // extended-cases-v1: pass runs as ["runId=Label", ...] because it holds 637 runs.
  async function answers(id, { feed: name = 'disputed-reviews-v1.json', runs = [] } = {}) {
    const data = await feed(name);
    if (data.schema === 'disputed-reviews-v1') {
      const found = resolve(data, `reviews[id=${id}]`);
      const names = new Map(data.models.map(m => [m.id, m.display_name]));
      return {
        review: { id, feedback: found.feedback, reference: found.reference },
        answers: found.answers.map(a => ({ id: a.model_id, name: names.get(a.model_id) ?? a.model_id, prediction: a.prediction, different: a.different_fields })),
      };
    }
    if (data.schema === 'extended-cases-v1') {
      if (!runs.length) throw new Error('extended-cases-v1 needs an explicit run list');
      const found = resolve(data, `cases[id=${id}]`);
      return {
        review: found,
        answers: runs.map(spec => {
          const [runId, label] = spec.split('=');
          const run = resolve(data, `runs[runId=${runId}]`);
          const saved = resolve(run, `cases[id=${id}]`);
          return { id: runId, name: label || `${run.model} ${run.repeatPass} ${run.condition}`, prediction: saved.prediction ?? {}, status: saved.status,
            different: FIELDS.filter(f => saved.prediction?.[f] !== found.reference[f]) };
        }),
      };
    }
    throw new Error(`${name} has no saved answers by review (schema ${data.schema ?? 'unknown'})`);
  }

  const jevConfidence = async (field, condition = 'P0') => resolve(await feed('jev-confidence-findings.json'), `conditions.${condition}.fields.${field}`);

  async function agreementPairs() {
    const data = await feed('native-agreement-policy-v1.json');
    const names = new Map(data.components.map(c => [c.id, c.display_name]));
    return data.pairs.map(p => ({ ...p, leftName: names.get(p.left), rightName: names.get(p.right), denominator: data.denominator }))
      .sort((a, b) => b.accepted_count - a.accepted_count);
  }

  async function agreementPair(left, right) {
    const pair = (await agreementPairs()).find(p => (p.left === left && p.right === right) || (p.left === right && p.right === left));
    if (!pair) throw new Error(`no agreement pair ${left} + ${right}`);
    return pair;
  }

  // Safety net: a slide with bound numbers always names its feeds.
  function ensureFooters(root) {
    root.querySelectorAll('.slides section:not(.stack)').forEach(slide => {
      const sources = [...slide.querySelectorAll('[data-source], [data-text-source]')].map(el => (el.dataset.source || el.dataset.textSource).split('#')[0]);
      if (!sources.length || slide.querySelector(':scope > .d-source')) return;
      const links = [...new Set(sources)].map(name => `<a href="${new URL(name, base).href}">${name}</a>`).join(' · ');
      slide.insertAdjacentHTML('beforeend', `<footer class="d-source"><b>Source</b>${links}</footer>`);
    });
  }

  function bind(root = document) {
    ensureFooters(root);
    return Promise.all([
      ...[...root.querySelectorAll('[data-source]')].map(bindNumber),
      ...[...root.querySelectorAll('[data-text-source]')].map(bindText),
      ...[...root.querySelectorAll('[data-review]:not(.d-replay):not(.d-live)')].map(bindReview),
      ...[...root.querySelectorAll('[data-scene-highlight^="@"]')].map(el => bindScene(el, 'sceneHighlight')),
      ...[...root.querySelectorAll('[data-scene-number^="@"]')].map(el => bindScene(el, 'sceneNumber')),
    ]).then(() => { if (!failures.size) document.documentElement.dataset.deckData = 'ready'; });
  }

  window.DeckData = { CORE, FIELDS, feed, resolve, get, review, answers, jevConfidence, agreementPair, agreementPairs, readable, report, bind, ready: bind() };
})();
