/* Hero components.
   gate   S14: 60 Jev testimonial answers as dots at their confidence, sorted; the gate at 0.95 is the final state and sweeps
          up from 0.50 on entry (about 1.7 s). No clicks.
   sorter S16: 60 review cards sorted by the Solar + Perplexity rule on entry; step 1 re-sorts with Qwen + Gemma.
   queue  S13: the full policy routes all 60 into three bands; computed from the saved answers and checked against the feed. */
(() => {
  'use strict';
  const C = window.DeckContent, gsap = window.gsap, { DeckData } = window;
  const NS = 'http://www.w3.org/2000/svg';

  // ---------- S10 gate ----------
  const G = { w: 1664, h: 520, x0: 96, x1: 1640, top: 24, bottom: 470, lo: 0.4, hi: 1, from: 0.5, to: 0.95, sweep: 1.2 };
  const gy = c => G.top + (1 - (c - G.lo) / (G.hi - G.lo)) * (G.bottom - G.top);
  const gx = i => G.x0 + 22 + i * ((G.x1 - G.x0 - 44) / 59);

  async function buildGate(el) {
    const data = await C.file(el.dataset.points);
    const pts = data.reviews; // sorted by confidence in the file
    const svg = el.querySelector('svg');
    svg.setAttribute('viewBox', `0 0 ${G.w} ${G.h}`);
    const grid = [0.5, 0.7, 0.9, 1].map(c => `<line class="c-grid" x1="${G.x0}" x2="${G.x1}" y1="${gy(c)}" y2="${gy(c)}"/><text class="c-tick" x="${G.x0 - 14}" y="${gy(c) + 7}">${c.toFixed(1)}</text>`).join('');
    const dots = pts.map((p, i) => `<g class="c-dot${p.correct ? '' : ' is-wrong'}${p.id === el.dataset.hero ? ' is-hero' : ''}" data-conf="${p.confidence}" data-id="${C.esc(p.id)}" transform="translate(${gx(i).toFixed(1)} ${gy(p.confidence).toFixed(1)})">`
      + `${p.correct ? '' : '<circle class="c-ring" r="19"/>'}<circle class="c-core" r="10"/></g>`).join('');
    svg.innerHTML = `<text class="c-axis" x="${G.x0 - 14}" y="${G.top - 6}" text-anchor="end"></text>${grid}`
      + `<g class="c-gate-line" transform="translate(0 ${gy(G.from)})"><rect x="${G.x0}" y="0" width="${G.x1 - G.x0}" height="${G.bottom - gy(G.from) + 4}" class="c-gate-shade"/><line x1="${G.x0}" x2="${G.x1}" y1="0" y2="0"/></g>${dots}`;
    // Callout leaders: from each labelled dot to its label box, drawn in stage pixels.
    el.querySelectorAll('[data-callout]').forEach(box => {
      const i = pts.findIndex(p => p.id === box.dataset.callout);
      if (i < 0) throw new Error(`no point ${box.dataset.callout}`);
      const line = document.createElementNS(NS, 'line');
      line.setAttribute('class', 'c-leader');
      Object.entries({ x1: gx(i), y1: gy(pts[i].confidence), x2: Number(box.dataset.x), y2: Number(box.dataset.y) }).forEach(([k, v]) => line.setAttribute(k, v));
      svg.insertBefore(line, svg.querySelector('.c-dot'));
      Object.assign(box.style, { left: `${box.dataset.x}px`, top: `${box.dataset.y}px` });
    });
    el.querySelectorAll('[data-at]').forEach(n => { n.style.top = `${gy(Number(n.dataset.at))}px`; });
  }

  function gate(el, value) {
    const line = el.querySelector('.c-gate-line'), shade = el.querySelector('.c-gate-shade');
    line.setAttribute('transform', `translate(0 ${gy(value).toFixed(1)})`);
    shade.setAttribute('height', String(Math.max(0, G.bottom - gy(value) + 4)));
    el.querySelectorAll('.c-dot').forEach(d => d.classList.toggle('is-held', Number(d.dataset.conf) < value));
    el.querySelector('.c-gate-value').textContent = value.toFixed(2);
  }

  function renderGate(el, step, { animate }) {
    const dots = el.querySelectorAll('.c-dot'), lineG = el.querySelector('.c-gate-line'), readout = el.querySelector('.c-gate-readout');
    C.kill(el);
    C.badge(el.closest('section'), true);
    gsap.set(dots, { clearProps: 'opacity' });
    el.querySelectorAll('.c-dot .c-core').forEach(c => gsap.set(c, { clearProps: 'transform' }));
    gsap.set([lineG, readout], { autoAlpha: 1 });
    gate(el, G.to);
    if (!animate) return;
    // Each answer rises from the axis to its confidence, left to right; the gate sweeps up behind them.
    const state = { v: G.from };
    gate(el, G.from);
    C.timeline(el)
      .from([...dots].map(d => d.querySelector('.c-core')), { y: (i, t) => G.bottom - gy(Number(t.parentNode.dataset.conf)), opacity: 0, duration: 0.7, ease: 'power3.out', stagger: 0.012, clearProps: 'transform,opacity' }, 0)
      .fromTo([lineG, readout], { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }, 0.5)
      .to(state, { v: G.to, duration: G.sweep, ease: 'none', onUpdate: () => gate(el, state.v) }, 0.5)
      .add(() => gate(el, G.to));
  }

  // ---------- S12 sorter ----------
  const S = { cw: 116, ch: 50, gx: 12, gy: 12, accCols: 10, personX: 1310, personW: 354, top: 72 };

  async function buildSorter(el) {
    const ids = (await DeckData.feed('disputed-reviews-v1.json')).reviews.map(r => r.id).sort();
    const pairs = await Promise.all(['pairA', 'pairB'].map(k => DeckData.get(el.dataset[k])));
    const deferred = pairs.map(p => new Set(p.deferred_ids));
    const errors = pairs.map(p => new Set(p.accepted_all_four_error_ids ?? p.accepted_error_ids));
    const tags = JSON.parse(el.dataset.tags || '{}');
    const host = el.querySelector('.c-cards');
    host.innerHTML = ids.map(id => `<div class="c-rv${tags[id] ? ' has-tag' : ''}" data-id="${C.esc(id)}" data-a="${deferred[0].has(id) ? 'defer' : errors[0].has(id) ? 'error' : 'accept'}" data-b="${deferred[1].has(id) ? 'defer' : errors[1].has(id) ? 'error' : 'accept'}">`
      + `<b><span>DEV-</span>${C.esc(id.replace('DEV-', ''))}</b><i class="c-st"></i><i class="c-st"></i>${tags[id] ? `<em>${C.esc(tags[id])}</em>` : ''}</div>`).join('');
    if (ids.length !== 60) throw new Error(`expected 60 reviews, got ${ids.length}`);
  }

  // Target box for one card at one step: the unsorted grid, or the accepted grid / the person column.
  function layout(cards, step) {
    const key = step === 1 ? 'a' : 'b';
    let acc = 0, per = 0;
    return cards.map((card, i) => {
      if (step === 0) return { x: 64 + (i % 12) * (S.cw + S.gx), y: S.top + Math.floor(i / 12) * (S.ch + S.gy), w: S.cw };
      if (card.dataset[key] === 'defer') { const y = S.top + per++ * (S.ch + S.gy); return { x: S.personX, y, w: S.personW, person: true }; }
      const k = acc++;
      return { x: (k % S.accCols) * (S.cw + S.gx), y: S.top + Math.floor(k / S.accCols) * (S.ch + S.gy), w: S.cw };
    });
  }

  // Visual state is one ahead of the click count: the slide enters sorted by pair A, one click re-sorts by pair B.
  function renderSorter(el, click, { animate, from: fromClick }) {
    const step = Math.min(click + 1, 2), from = fromClick === undefined ? undefined : Math.min(fromClick + 1, 2);
    const cards = [...el.querySelectorAll('.c-rv')];
    const stamps = el.querySelectorAll('.c-st');
    const labels = { 1: el.querySelectorAll('.c-when-a'), 2: el.querySelectorAll('.c-when-b') };
    C.kill(el);
    const key = step === 1 ? 'a' : 'b';
    const place = (boxes, now) => cards.forEach((c, i) => {
      c.classList.toggle('is-person', Boolean(boxes[i].person));
      c.classList.toggle('is-split', step > 0 && c.dataset[key] === 'defer');
      if (now) gsap.set(c, { x: boxes[i].x, y: boxes[i].y, width: boxes[i].w });
    });
    const boxes = layout(cards, step);
    el.dataset.pair = step === 0 ? '' : key;
    gsap.set([...labels[1], ...labels[2]], { autoAlpha: 0 });
    if (step) gsap.set(labels[step], { autoAlpha: 1 });
    gsap.set(stamps, { autoAlpha: step ? 1 : 0, scale: 1 });
    if (!animate || step === 0 || (step === 2 && from !== 1)) return place(boxes, true);
    // Animate from the previous step's arrangement.
    const prev = layout(cards, step - 1);
    place(prev, true);
    cards.forEach(c => c.classList.remove('is-split'));
    gsap.set(labels[step], { autoAlpha: 0 });
    const tl = C.timeline(el);
    if (step === 1) tl.fromTo(stamps, { autoAlpha: 0, scale: 2.2 }, { autoAlpha: 1, scale: 1, duration: 0.3, ease: 'power3.out', stagger: 0.007 });
    else {
      gsap.set(labels[1], { autoAlpha: 1 });
      tl.to(labels[1], { autoAlpha: 0, duration: 0.3 }).fromTo(stamps, { scaleX: 0 }, { scaleX: 1, duration: 0.25, stagger: 0.004, ease: 'power2.out' }, 0.1);
    }
    tl.to({}, { duration: 0.1 }).add(() => cards.forEach(c => c.classList.toggle('is-split', c.dataset[key] === 'defer')))
      .to({}, { duration: 0.3 })
      .add(() => cards.forEach((c, i) => c.classList.toggle('is-person', Boolean(boxes[i].person))))
      .to(cards, { x: (i) => boxes[i].x, y: (i) => boxes[i].y, width: (i) => boxes[i].w, duration: 0.9, ease: 'power3.inOut', stagger: 0.006 })
      .fromTo(labels[step], { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, duration: 0.5, ease: 'power3.out', stagger: 0.12, clearProps: 'transform' }, '-=0.35')
      .add(() => labels[step].forEach(n => n.querySelectorAll('[data-countup]').forEach(x => window.DeckMotion.countUp(x))), '<');
  }

  // ---------- S13 queue ----------
  async function buildQueue(el) {
    const [a, b] = el.dataset.models.split(',');
    const data = await DeckData.feed('disputed-reviews-v1.json');
    const band = { concern: [], clean: [], person: [] };
    for (const r of data.reviews) {
      const p = [a, b].map(id => r.answers.find(x => x.model_id === id)?.prediction ?? {});
      const differ = C.FIELDS.some(f => p[0][f] !== p[1][f]);
      if (p.some(x => x.serious_concern_reported === 'yes')) band.concern.push(r.id);
      else if (differ || p.some(x => C.FIELDS.some(f => x[f] === 'insufficient_information'))) band.person.push(r.id);
      else band.clean.push(r.id);
    }
    // The routing must reproduce the published counts, or the slide says so loudly.
    const routing = await DeckData.get(el.dataset.routing);
    if (band.concern.length !== routing.concern_any || band.clean.length !== routing.accepted_no_routing
      || band.concern.length + band.person.length !== routing.reaches_person) throw new Error(`queue routing ${JSON.stringify(Object.values(band).map(x => x.length))} does not match ${el.dataset.routing}`);
    for (const [name, list] of Object.entries(band)) {
      el.querySelector(`[data-band="${name}"] .c-band-cards`).innerHTML = list.sort().map(id => `<i title="${id}"></i>`).join('');
    }
  }

  // The closing question is a plain Reveal fragment outside this component; the queue only builds in on entry.
  function renderQueue(el, step, { animate }) {
    const chips = el.querySelectorAll('.c-band-cards i'), heads = el.querySelectorAll('.c-band-head');
    C.kill(el);
    gsap.set([...chips, ...heads], { clearProps: 'opacity,transform' });
    if (!animate) return;
    const tl = C.timeline(el);
    el.querySelectorAll('.c-band').forEach((b, k) => {
      tl.fromTo(b.querySelector('.c-band-head'), { opacity: 0, x: -20 }, { opacity: 1, x: 0, duration: 0.45, ease: 'power3.out' }, 0.2 + k * 0.7)
        .fromTo(b.querySelectorAll('.c-band-cards i'), { opacity: 0, x: -60 }, { opacity: 1, x: 0, duration: 0.4, ease: 'power3.out', stagger: 0.018 }, 0.3 + k * 0.7);
    });
  }

  C.register('gate', { build: buildGate, render: renderGate });
  C.register('sorter', { build: buildSorter, render: renderSorter });
  C.register('queue', { build: buildQueue, render: renderQueue });
})();
