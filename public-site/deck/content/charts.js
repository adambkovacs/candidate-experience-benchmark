/* Chart components. Every drawn length or position is computed from a number already bound on the slide,
   so the picture and the printed number cannot disagree.
   bars S2 · wave S4 · stairs S11 · tally S11/A3 · pipeline S14 · histo S9/A5 · hbars A2 · pairs A10 */
(() => {
  'use strict';
  const C = window.DeckContent, gsap = window.gsap, { DeckData } = window;
  const num = el => Number(el?.dataset.value ?? String(el?.textContent).replace(/,/g, ''));
  const countAll = root => root.querySelectorAll('[data-countup]').forEach(n => window.DeckMotion.countUp(n));

  // ---------- S2 bars: value out of 60, three-pass ticks, the gap shaded ----------
  async function buildBars(el) {
    await C.bind(el);
    const max = Number(el.dataset.max);
    const rows = [...el.querySelectorAll('.c-bar-row')];
    rows.forEach(row => {
      row.style.setProperty('--v', num(row.querySelector('.c-bar-val [data-source]')) / max);
      row.querySelectorAll('.c-passes [data-source]').forEach(p => {
        row.querySelector('.c-track').insertAdjacentHTML('beforeend', `<i class="c-pass-tick" style="--at:${num(p) / max}"></i>`);
      });
    });
    const gap = el.querySelector('.c-gap');
    if (gap) {
      const [lo, hi] = gap.dataset.between.split(',').map(sel => num(el.querySelector(sel)) / max);
      gap.style.setProperty('--lo', lo); gap.style.setProperty('--hi', hi);
    }
  }
  function renderBars(el, step, { animate }) {
    const fills = el.querySelectorAll('.c-fill'), ticks = el.querySelectorAll('.c-pass-tick'), gap = el.querySelectorAll('.c-gap, .c-gap-label');
    C.kill(el);
    gsap.set([...fills, ...ticks, ...gap], { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (!animate) return;
    C.timeline(el)
      .from(fills, { scaleX: 0, duration: 1.1, ease: 'power3.out', stagger: 0.25, transformOrigin: '0 50%' })
      .add(() => countAll(el), 0)
      .from(ticks, { scaleY: 0, opacity: 0, duration: 0.3, ease: 'power3.out', stagger: 0.08 }, 1.1)
      .fromTo(gap, { clipPath: 'inset(0% 100% 0% 0%)', opacity: 0 }, { clipPath: 'inset(0% 0% 0% 0%)', opacity: 1, duration: 0.6, ease: 'power2.out', stagger: 0.15, clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' }, 1.45);
  }

  // ---------- S4 wave: labelled launches are fragments; every other verified launch is a tick that lands as the line passes ----------
  const DAY = 864e5;
  async function buildWave(el) {
    const tl = await C.file(el.dataset.timeline);
    const [start, end] = el.dataset.range.split(',').map(d => Date.parse(d));
    const at = date => (Date.parse(date) - start) / (end - start);
    const labelled = new Set();
    el.querySelectorAll('.d-event').forEach(ev => {
      const entries = ev.dataset.entries.split('|').map(m => tl.entries.find(e => e.model === m));
      if (entries.some(e => !e || !e.verified)) throw new Error(`timeline entry "${ev.dataset.entries}" is missing or unverified`);
      entries.forEach(e => labelled.add(e));
      ev.style.setProperty('--at', at(entries[0].date).toFixed(4));
    });
    const ticks = tl.entries.filter(e => e.verified && !labelled.has(e) && Date.parse(e.date) >= start && Date.parse(e.date) <= end);
    const k = {}; // same-day launches stack upward
    el.insertAdjacentHTML('beforeend', ticks.map(e => `<li class="c-wtick" style="--at:${at(e.date).toFixed(4)};--k:${(k[e.date] = (k[e.date] ?? -1) + 1)}" title="${C.esc(`${e.date} · ${e.maker} · ${e.model}`)}" aria-hidden="true"></li>`).join(''));
    el.dataset.days = String(Math.round((end - start) / DAY));
  }
  function renderWave(el, step, { animate, from }) {
    const shown = [...el.querySelectorAll('.d-event')].filter(ev => !ev.classList.contains('fragment') || ev.classList.contains('visible'));
    const reach = Math.max(0, ...shown.map(ev => Number(ev.style.getPropertyValue('--at'))));
    const prev = from === undefined ? 0 : (el._reach ?? 0); // JS-only state: print clones never animate, so they never need it
    el._reach = reach;
    const at = t => Number(t.style.getPropertyValue('--at'));
    const ticks = [...el.querySelectorAll('.c-wtick')];
    C.kill(el);
    ticks.forEach(t => { t.classList.toggle('is-on', at(t) <= reach + 1e-6); gsap.set(t, { clearProps: 'opacity,transform' }); });
    if (!animate || reach <= prev) return;
    // The foundation draws the line over 0.9 s (power2.inOut); each tick lands roughly as the line passes it.
    const tl = C.timeline(el);
    ticks.filter(t => at(t) > prev && at(t) <= reach + 1e-6).forEach(t => {
      tl.fromTo(t, { opacity: 0, scaleY: 0 }, { opacity: 1, scaleY: 1, duration: 0.35, ease: 'power3.out', clearProps: 'opacity,transform' }, 0.2 + ((at(t) - prev) / (reach - prev)) * 0.75);
    });
  }

  // ---------- S11 stairs: one model's score per prompt version, as treads on a labelled axis ----------
  async function buildStairs(el) {
    await C.bind(el);
    const [lo, hi] = el.dataset.axis.split(',').map(Number);
    el.querySelectorAll('.c-tread').forEach(t => t.style.setProperty('--y', (num(t.querySelector('[data-source]')) - lo) / (hi - lo)));
  }
  function renderStairs(el, step, { animate }) {
    const treads = el.querySelectorAll('.c-tread');
    C.kill(el);
    gsap.set(treads, { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (animate) C.timeline(el).from(treads, { opacity: 0, y: -40, duration: 0.6, ease: 'power3.out', stagger: 0.45 }).add(() => countAll(el), 0);
  }

  // ---------- tally: unit squares for better / same / worse from bound counts ----------
  async function buildTally(el) {
    await C.bind(el);
    el.querySelectorAll('.c-tally-row').forEach(row => {
      const parts = [...row.querySelectorAll('[data-part]')].map(n => [n.dataset.part, num(n)]);
      row.querySelector('.c-units').innerHTML = parts.map(([kind, n]) => `<i class="is-${kind}"></i>`.repeat(n)).join('');
    });
  }
  function renderTally(el, step, { animate }) {
    const units = el.querySelectorAll('.c-units i');
    C.kill(el);
    gsap.set(units, { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (animate) C.timeline(el, { delay: Number(el.dataset.delay || 0) }).from(units, { opacity: 0, scale: 0.3, duration: 0.25, ease: 'power3.out', stagger: 0.012 });
  }

  // ---------- S14 pipeline ----------
  function renderPipeline(el, step, { animate }) {
    const nodes = el.querySelectorAll('.c-node'), links = el.querySelectorAll('.c-link'), routes = el.querySelectorAll('.c-route'), badge = el.querySelectorAll('.c-pipe-badge');
    C.kill(el);
    gsap.set([...nodes, ...links, ...routes, ...badge], { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (!animate) return;
    const tl = C.timeline(el);
    nodes.forEach((n, i) => {
      tl.from(n, { opacity: 0, y: 20, duration: 0.4, ease: 'power3.out' }, i * 0.32);
      if (links[i]) tl.from(links[i], { scaleX: 0, transformOrigin: '0 50%', duration: 0.3, ease: 'power2.inOut' }, i * 0.32 + 0.25);
    });
    // Overlap, never gap: a gap with no running tween lets "motion finished" checks fire mid-sequence.
    tl.from(routes, { opacity: 0, y: -18, duration: 0.35, ease: 'power3.out', stagger: 0.12 }, '-=0.1')
      .from(badge, { opacity: 0, y: 18, duration: 0.4, ease: 'power3.out' }, '-=0.1');
  }

  // ---------- histo: vertical bars, height from each bar's bound count ----------
  async function buildHisto(el) {
    await C.bind(el);
    const bars = [...el.querySelectorAll('.c-hbar')];
    const max = Math.max(...bars.map(b => num(b.querySelector('[data-source]'))));
    bars.forEach(b => b.style.setProperty('--h', num(b.querySelector('[data-source]')) / max));
  }
  function renderHisto(el, step, { animate }) {
    const fills = el.querySelectorAll('.c-hbar i');
    C.kill(el);
    gsap.set(fills, { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (animate) C.timeline(el, { delay: Number(el.dataset.delay || 0) }).from(fills, { scaleY: 0, transformOrigin: '50% 100%', duration: 0.5, ease: 'power3.out', stagger: 0.05 });
  }

  // ---------- hbars: horizontal bars from a cited number in each row ----------
  function buildHbars(el) {
    const rows = [...el.querySelectorAll('.c-hrow')];
    const max = Math.max(...rows.map(r => num(r.querySelector('.c-hval'))));
    rows.forEach(r => r.style.setProperty('--w', num(r.querySelector('.c-hval')) / max));
  }
  function renderHbars(el, step, { animate }) {
    const fills = el.querySelectorAll('.c-hrow i');
    C.kill(el);
    gsap.set(fills, { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (animate) C.timeline(el).from(fills, { scaleX: 0, transformOrigin: '0 50%', duration: 0.6, ease: 'power3.out', stagger: 0.05 });
  }

  // ---------- A10 pairs: all 21 pairs, every cell bound ----------
  async function buildPairs(el) {
    const policy = await DeckData.feed('native-agreement-policy-v1.json');
    const names = new Map(policy.components.map(c => [c.id, c.display_name.replace(/ (D1|1 4B|Decide|Decisions|Decider V1 27B)$/, '')]));
    const P = (p, f, round = '') => `<span class="d-num" data-source="native-agreement-policy-v1.json#pairs[left=${p.left},right=${p.right}].${f}"${round}>–</span>`;
    el.querySelector('tbody').innerHTML = policy.pairs.map(p => {
      const zero = p.accepted_all_four_error_count === 0, soup = p.accepted_ids.includes('DEV-029');
      return `<tr class="${zero ? 'is-zero' : ''}"><th scope="row">${C.esc(names.get(p.left))} + ${C.esc(names.get(p.right))}${soup ? ' <em>soup accepted</em>' : ''}</th>`
        + `<td>${P(p, 'accepted_count')}</td><td class="${zero ? '' : 'is-diff'}">${P(p, 'accepted_all_four_error_count')}</td><td>${P(p, 'deferred_count')}</td>`
        + ['escalated_beyond_deferral', 'clarification_beyond_deferral', 'reaches_person'].map(f => `<td><span class="d-num" data-source="deep-insights-v1.json#agreement_rule.native_routing[left=${p.left},right=${p.right}].${f}">–</span></td>`).join('')
        + `<td>$${P(p, 'known_two_run_development_cost_usd', ' data-round="4"')}</td></tr>`;
    }).join('');
    await C.bind(el);
  }
  const still = (el, step, { animate }) => {
    const rows = el.querySelectorAll('tbody tr');
    C.kill(el);
    gsap.set(rows, { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' });
    if (animate) C.timeline(el).from(rows, { opacity: 0, x: -14, duration: 0.3, ease: 'power3.out', stagger: 0.03 });
  };

  C.register('bars', { build: buildBars, render: renderBars });
  C.register('wave', { build: buildWave, render: renderWave });
  C.register('stairs', { build: buildStairs, render: renderStairs });
  C.register('tally', { build: buildTally, render: renderTally });
  C.register('pipeline', { render: renderPipeline });
  C.register('histo', { build: buildHisto, render: renderHisto });
  C.register('hbars', { build: buildHbars, render: renderHbars });
  C.register('pairs', { build: buildPairs, render: still });
})();
