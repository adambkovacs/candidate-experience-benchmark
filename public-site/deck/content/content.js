/* Deck content engine. A component is an element with data-c="<name>". Its picture is a pure function of its step:
   the number of visible .fragment.c-step markers inside it. render(el, step, {animate}) draws that step.
   It animates only when the presenter moved forward one step (or entered the slide at step 0); reduced motion,
   print view, backward navigation and hash jumps draw the final state instantly. Builders run inside
   DeckMotion.prepare(), so print view lays out finished components. Load after data.js, motion.js, scene.js. */
(() => {
  'use strict';
  const { gsap, DeckData, DeckMotion, Reveal } = window;
  const SITE = new URL('../../', document.currentScript.src); // public-site/
  const FIELDS = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const FIELD_LABEL = { sentiment: 'Sentiment', follow_up_needed: 'Follow-up', serious_concern_reported: 'Concern', testimonial_potential: 'Testimonial' };
  const files = new Map();
  const defs = {};

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const say = v => (v === undefined || v === null ? 'no answer' : v === 'insufficient_information' ? "can't tell" : String(v).replace(/_/g, ' '));
  const html = s => document.createRange().createContextualFragment(s);
  const still = () => DeckMotion.still();

  // Any JSON file under public-site by relative path (deck/data/..., deck/content/...). Top-level feeds go through DeckData.feed.
  function file(path) {
    if (/^[\w.-]+\.json$/.test(path)) return DeckData.feed(path);
    if (!/^deck\/(data|content)\/[\w.-]+\.json$/.test(path)) return Promise.reject(new Error(`unexpected data file "${path}"`));
    if (!files.has(path)) files.set(path, fetch(new URL(path, SITE)).then(r => { if (!r.ok) throw new Error(`${path} returned HTTP ${r.status}`); return r.json(); }));
    return files.get(path);
  }
  async function value(spec) { const [path, jsonPath] = spec.split('#'); return DeckData.resolve(await file(path), jsonPath); }

  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  function format(raw, el) {
    const kind = el.dataset.format;
    if (kind === 'date' || kind === 'date-short') {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
      if (!m) throw new Error(`not a date: ${JSON.stringify(raw)}`);
      const month = MONTHS[Number(m[2]) - 1];
      return `${Number(m[3])} ${kind === 'date' ? month : month.slice(0, 3)}`;
    }
    if (kind === 'text') { if (typeof raw !== 'string') throw new Error(`not text: ${JSON.stringify(raw)}`); return raw; }
    const n = Number(raw);
    if (typeof raw === 'boolean' || raw === '' || !Number.isFinite(n)) throw new Error(`not a number: ${JSON.stringify(raw)}`);
    return el.dataset.round !== undefined ? n.toFixed(Number(el.dataset.round)) : String(raw);
  }

  function setNumber(el, text) {
    if (el.hasAttribute('data-group') && /^\d{4,}$/.test(text)) text = Number(text).toLocaleString('en-US');
    el.textContent = text;
    if (/^-?[\d,]+(\.\d+)?$/.test(text)) Object.assign(el.dataset, { display: text, value: String(Number(text.replace(/,/g, ''))) });
    el.classList.remove('is-unbound');
    el.dispatchEvent(new CustomEvent('deck:bound', { bubbles: true }));
  }
  function fail(el, what, error) {
    el.textContent = '?';
    el.classList.add('is-unbound');
    DeckData.report(`${what}: ${error.message}`);
  }

  // data-deck-source="deck/data/x.json#path": like data-source, for deck-local files that data.js cannot load.
  // data-count="feed.json#path" data-count-where="k=v": the number of array items matching every k=v.
  async function bindLocal(root = document) {
    const jobs = [...root.querySelectorAll('[data-deck-source]')].map(async el => {
      try { setNumber(el, format(await value(el.dataset.deckSource), el)); } catch (e) { fail(el, el.dataset.deckSource, e); }
    });
    jobs.push(...[...root.querySelectorAll('[data-count]')].map(async el => {
      try {
        const list = await value(el.dataset.count);
        if (!Array.isArray(list)) throw new Error('expected a list');
        const where = (el.dataset.countWhere || '').split(',').filter(Boolean).map(p => p.split('='));
        setNumber(el, String(list.filter(item => where.every(([k, v]) => String(item?.[k]) === v)).length));
      } catch (e) { fail(el, `count ${el.dataset.count}`, e); }
    }));
    await Promise.all(jobs);
  }

  // data.js binds static numbers at load; components bind what they build.
  async function bind(node) { await DeckData.bind(node); await bindLocal(node); }

  // Thousands separators for 1,000 to 9,999 (data.js only groups 10,000 and up). numbers.mjs accepts grouped digits.
  document.addEventListener('deck:bound', e => {
    const el = e.target;
    if (el.hasAttribute?.('data-group') && el.dataset.display && /^\d{4}$/.test(el.dataset.display)) {
      el.dataset.display = Number(el.dataset.display).toLocaleString('en-US');
      el.textContent = el.dataset.display;
    }
  });

  // ---- steps and rendering ----
  const stepOf = el => el.querySelectorAll('.c-step.fragment.visible').length;
  const built = el => el.dataset.cBuilt === '1';

  function draw(el, animate) {
    const def = defs[el.dataset.c];
    if (!def || !built(el)) return;
    const step = stepOf(el), from = el._step;
    el._step = step;
    def.render(el, step, { animate: Boolean(animate) && !still(), from });
  }

  function badge(slide, on) { slide?.querySelector(':scope > .c-replay-badge')?.classList.toggle('is-on', Boolean(on)); }

  async function prepare() {
    const roots = [...document.querySelectorAll('[data-c]')];
    await Promise.all(roots.map(async el => {
      const def = defs[el.dataset.c];
      if (!def) throw new Error(`no component "${el.dataset.c}"`);
      try { await def.build?.(el); el.dataset.cBuilt = '1'; } catch (e) { DeckData.report(`${el.dataset.c} on ${el.closest('section')?.id}: ${e.message}`); }
    }));
    await bindLocal(document);
    roots.forEach(el => draw(el, false));
  }

  function wire() {
    let last = { h: 0, v: 0 };
    const backward = e => e.indexh < last.h || (e.indexh === last.h && e.indexv < last.v);
    const enter = (slide, animate) => slide?.querySelectorAll('[data-c]').forEach(el => { el._step = undefined; draw(el, animate && stepOf(el) === 0); });
    Reveal.on('ready', e => { last = { h: e.indexh, v: e.indexv }; enter(e.currentSlide, true); });
    Reveal.on('slidechanged', e => {
      e.previousSlide?.querySelectorAll('[data-c]').forEach(el => draw(el, false)); // finish anything still playing
      enter(e.currentSlide, !backward(e));
      last = { h: e.indexh, v: e.indexv };
    });
    const step = (e, shown) => {
      const roots = new Set(e.fragments.map(f => f.closest('[data-c]')).filter(Boolean));
      roots.forEach(el => draw(el, shown && el._step !== undefined && stepOf(el) === el._step + 1));
    };
    Reveal.on('fragmentshown', e => step(e, true));
    Reveal.on('fragmenthidden', e => step(e, false));
    // Print clones one page per fragment step: draw every clone at its own step.
    Reveal.on('pdf-ready', () => document.querySelectorAll('[data-c]').forEach(el => { el._step = undefined; draw(el, false); }));
  }

  // Join DeckMotion.prepare so deck.js waits for components before print layout and DeckReady.
  const basePrepare = DeckMotion.prepare;
  DeckMotion.prepare = root => Promise.all([basePrepare(root), prepare().catch(e => DeckData.report(`content: ${e.message}`))])
    // Before Reveal.initialize (print view) only queued methods exist on Reveal, so check isReady exists first.
    .then(() => { if (typeof Reveal.isReady === 'function' && Reveal.isReady()) Reveal.getCurrentSlide()?.querySelectorAll('[data-c]').forEach(el => { if (el._step === undefined) draw(el, false); }); });
  wire();

  window.DeckContent = {
    SITE, FIELDS, FIELD_LABEL, esc, say, html, still, file, value, bind, badge, stepOf,
    register(name, def) { defs[name] = def; },
    // Small helpers shared by components. Never reset with clearProps 'all': it also wipes inline custom properties
    // such as --at and --y that position the shapes.
    kill(el) { el._tl?.kill(); el._tl = null; gsap.killTweensOf(el.querySelectorAll('*')); },
    timeline(el, opts) { this.kill(el); el._tl = gsap.timeline(opts); return el._tl; },
  };
})();
