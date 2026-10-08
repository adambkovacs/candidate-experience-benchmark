/* Motion toolkit (GSAP). Brand motion: confident ease-outs, never bouncy.
   Reduced motion, print view and backward navigation all collapse to the final state instantly. */
(() => {
  'use strict';
  const gsap = window.gsap;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const still = () => reduced.matches || /print-pdf/i.test(location.search);
  const EASE = 'power3.out';
  const LABELS = { sentiment: 'Sentiment', follow_up_needed: 'Follow-up', serious_concern_reported: 'Serious concern', testimonial_potential: 'Testimonial' };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const hiddenFragment = el => el.closest('.fragment:not(.visible)');

  // Count-up: width is locked to the final value first, so tabular digits never shift the layout.
  function countUp(el, now = still()) {
    const final = el.dataset.display, target = Number(el.dataset.value);
    if (final === undefined || !Number.isFinite(target)) return;
    el._tween?.kill();
    el.style.minWidth = '';
    el.textContent = final;
    if (now) return;
    el.style.minWidth = `${el.offsetWidth}px`;
    const decimals = (final.split('.')[1] || '').length;
    const format = new Intl.NumberFormat('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: final.includes(',') });
    const state = { v: Number(el.dataset.countFrom ?? 0) };
    el.textContent = format.format(state.v);
    el._tween = gsap.to(state, { v: target, duration: Number(el.dataset.duration ?? 1.4), ease: 'power2.out',
      onUpdate: () => { el.textContent = format.format(state.v); }, onComplete: () => { el.textContent = final; } });
  }

  // Staggered reveal: data-stagger="" animates children; data-stagger="tbody tr" animates a selector.
  function stagger(container, now = still()) {
    const items = container.dataset.stagger ? container.querySelectorAll(container.dataset.stagger) : container.children;
    if (now) return gsap.set(items, { clearProps: 'opacity,visibility,transform' });
    gsap.fromTo(items, { autoAlpha: 0, y: 28 }, { autoAlpha: 1, y: 0, duration: .7, ease: EASE, stagger: .08, overwrite: true, clearProps: 'transform' });
  }

  // Split-text headline: words in overflow masks. The heading keeps its full text as its accessible name.
  function split(el) {
    if (!el.dataset.splitDone) {
      el.setAttribute('aria-label', el.textContent.replace(/\s+/g, ' ').trim());
      const walk = node => [...node.childNodes].forEach(child => {
        if (child.nodeType === Node.TEXT_NODE) {
          const parts = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).filter(Boolean).forEach(part => {
            if (/^\s+$/.test(part)) return parts.append(' ');
            const mask = Object.assign(document.createElement('span'), { className: 'split-w' });
            mask.setAttribute('aria-hidden', 'true');
            mask.append(Object.assign(document.createElement('span'), { className: 'split-i', textContent: part }));
            parts.append(mask);
          });
          child.replaceWith(parts);
        } else if (child.nodeType === Node.ELEMENT_NODE && child.tagName !== 'BR') walk(child);
      });
      walk(el);
      el.dataset.splitDone = '1';
    }
    return el.querySelectorAll('.split-i');
  }

  function headline(el, now = still()) {
    const words = split(el);
    if (now) return gsap.set(words, { yPercent: 0 });
    gsap.fromTo(words, { yPercent: 115 }, { yPercent: 0, duration: 1, ease: 'power4.out', stagger: .055, overwrite: true });
  }

  // Split-flap highlight: the cell shows the reference value, flips over, and lands on the differing answer.
  function flip(cell, now = still()) {
    const face = cell.querySelector('.flip');
    if (!face || cell.dataset.from === undefined) return;
    const final = face.dataset.final ?? (face.dataset.final = face.textContent);
    gsap.killTweensOf(face);
    face.textContent = final;
    cell.classList.add('is-diff');
    if (now) return gsap.set(face, { rotationX: 0 });
    face.textContent = cell.dataset.from;
    cell.classList.remove('is-diff');
    return gsap.timeline()
      .to(face, { rotationX: -90, duration: .2, ease: 'power2.in' })
      .add(() => { face.textContent = final; cell.classList.add('is-diff'); })
      .fromTo(face, { rotationX: 90 }, { rotationX: 0, duration: .45, ease: EASE });
  }

  // Timeline: the line draws to the furthest visible event; events drop in on fragment steps.
  function drawTimeline(track, now = still()) {
    const shown = [...track.querySelectorAll('.d-event')].filter(ev => !ev.classList.contains('fragment') || ev.classList.contains('visible'));
    const reach = Math.max(0, ...shown.map(ev => parseFloat(getComputedStyle(ev).getPropertyValue('--at')) || 0));
    gsap.to(track, { '--progress': reach, duration: now ? 0 : .9, ease: 'power2.inOut', overwrite: true });
  }

  function dropEvent(ev, now = still()) {
    if (now) return gsap.set(ev.children, { clearProps: 'opacity,visibility,transform' });
    gsap.fromTo(ev.children, { autoAlpha: 0, y: ev.dataset.side === 'above' ? 18 : -18 },
      { autoAlpha: 1, y: 0, duration: .6, ease: EASE, stagger: .06, delay: .25, clearProps: 'transform' });
  }

  // Replay: one review, saved answers row by row (each row a fragment), differing cells flip.
  async function buildReplay(host) {
    if (host.dataset.built) return;
    const fields = (host.dataset.fields || window.DeckData.FIELDS.join(',')).split(',');
    const runs = host.dataset.runs ? host.dataset.runs.split('|') : [];
    const { review, answers } = await window.DeckData.answers(host.dataset.review, { feed: host.dataset.replay, runs });
    const say = window.DeckData.readable;
    const cell = (answer, f) => {
      const differs = answer.prediction?.[f] !== review.reference[f];
      return `<td${differs ? ` class="is-diff" data-from="${esc(say(review.reference[f]))}"` : ''}><span class="flip">${esc(say(answer.prediction?.[f]))}</span></td>`;
    };
    const rows = answers.map(a => {
      const diff = fields.filter(f => a.prediction?.[f] !== review.reference[f]).length;
      return `<tr class="d-replay-row fragment" data-diff="${diff}"><th scope="row">${esc(a.name)}</th>${fields.map(f => cell(a, f)).join('')}</tr>`;
    }).join('');
    host.innerHTML = `<table class="d-data"><caption>${esc(host.dataset.caption || `${review.id} · saved answers against the reference`)}</caption>`
      + `<thead><tr><th scope="col">Answer</th>${fields.map(f => `<th scope="col">${LABELS[f] ?? esc(f)}</th>`).join('')}</tr></thead>`
      + `<tbody><tr class="is-reference"><th scope="row">Reference</th>${fields.map(f => `<td>${esc(say(review.reference[f]))}</td>`).join('')}</tr>${rows}</tbody></table>`
      + `<p class="d-replay-tally"><span class="d-num" data-tally>0</span>of ${answers.length} disagree with the reference on ${fields.length === 4 ? 'at least one field' : 'these fields'}</p>`;
    host.dataset.built = '1';
  }

  function tally(host, now = still()) {
    const el = host?.querySelector('[data-tally]');
    if (!el) return;
    const count = host.querySelectorAll('.d-replay-row.visible:not([data-diff="0"])').length;
    Object.assign(el.dataset, { countFrom: el.dataset.value ?? '0', value: String(count), display: String(count), duration: '.5' });
    countUp(el, now);
  }

  function rowIn(row, now = still()) {
    const diffs = row.querySelectorAll('td[data-from]');
    if (now) return diffs.forEach(c => flip(c, true));
    gsap.fromTo(row.cells, { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: .45, ease: EASE, stagger: .035, clearProps: 'transform' });
    diffs.forEach((c, i) => gsap.delayedCall(.4 + i * .14, () => flip(c)));
  }

  function enter(slide, now = still()) {
    if (!slide) return;
    slide.querySelectorAll('[data-split]').forEach(el => headline(el, now));
    slide.querySelectorAll('[data-countup]').forEach(el => hiddenFragment(el) || countUp(el, now));
    slide.querySelectorAll('[data-stagger]').forEach(el => hiddenFragment(el) || stagger(el, now));
    slide.querySelectorAll('.d-track').forEach(track => { if (!now) gsap.set(track, { '--progress': 0 }); drawTimeline(track, now); });
    slide.querySelectorAll('.d-replay').forEach(host => tally(host, true));
  }

  function fragment(f, shown) {
    const now = still();
    if (f.matches('.d-replay-row')) { if (shown) rowIn(f, now); return tally(f.closest('.d-replay'), now); }
    if (f.matches('.d-event')) { if (shown) dropEvent(f, now); return drawTimeline(f.closest('.d-track'), now); }
    if (!shown) return;
    [f, ...f.querySelectorAll('[data-countup]')].filter(el => el.matches('[data-countup]')).forEach(el => countUp(el, now));
    [f, ...f.querySelectorAll('[data-stagger]')].filter(el => el.matches('[data-stagger]')).forEach(el => stagger(el, now));
  }

  // Print clones one page per fragment step; settle tallies and timelines on every clone.
  function settlePrint() {
    document.querySelectorAll('.d-replay').forEach(host => tally(host, true));
    document.querySelectorAll('.d-track').forEach(track => drawTimeline(track, true));
  }

  function prepare(root = document) {
    return Promise.all([...root.querySelectorAll('.d-replay')].map(host => buildReplay(host)
      .catch(error => window.DeckData.report(`replay ${host.dataset.review}: ${error.message}`))));
  }

  function wire(Reveal) {
    let last = { h: 0, v: 0 };
    const backward = e => { const back = e.indexh < last.h || (e.indexh === last.h && e.indexv < last.v); last = { h: e.indexh, v: e.indexv }; return back; };
    Reveal.on('ready', e => { last = { h: e.indexh, v: e.indexv }; enter(e.currentSlide); });
    Reveal.on('slidechanged', e => enter(e.currentSlide, still() || backward(e)));
    Reveal.on('fragmentshown', e => e.fragments.forEach(f => fragment(f, true)));
    Reveal.on('fragmenthidden', e => e.fragments.forEach(f => fragment(f, false)));
    Reveal.on('pdf-ready', settlePrint);
    document.addEventListener('deck:bound', e => {
      const el = e.target;
      if (el.matches?.('[data-countup]') && Reveal.isReady() && Reveal.getCurrentSlide()?.contains(el) && !hiddenFragment(el)) countUp(el);
    });
  }

  window.DeckMotion = { still, countUp, stagger, split, headline, flip, drawTimeline, dropEvent, buildReplay, tally, enter, prepare, wire };
})();
