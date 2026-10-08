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
  // data-split="line" masks the whole element as one unit: it rises from behind a clean cut, it never fades in.
  function split(el) {
    if (!el.dataset.splitDone && el.dataset.split === 'line') {
      const mask = Object.assign(document.createElement('span'), { className: 'split-w split-line' });
      const inner = Object.assign(document.createElement('span'), { className: 'split-i' });
      inner.append(...el.childNodes);
      mask.append(inner);
      el.append(mask);
      el.dataset.splitDone = '1';
    }
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
    gsap.fromTo(row.cells, { autoAlpha: 0, y: 18 }, { autoAlpha: 1, y: 0, duration: .45, ease: EASE, stagger: .035, clearProps: 'transform' });
    diffs.forEach((c, i) => gsap.delayedCall(.4 + i * .14, () => flip(c)));
  }

  // Live replay: a request/response panel that looks like a live call but only replays saved answers, with a badge
  // that says so. data-review, data-model, data-route, data-answer="<feed>#<path to the saved prediction object>",
  // data-probability="<feed>#<path with {field}>", data-latency="<feed>#<seconds>", data-latency-label,
  // data-probability-label, data-fields, data-compare. Click 1 sends; click 2 (with data-compare) shows the reference.
  async function buildLive(host) {
    if (host.dataset.built) return;
    const D = window.DeckData, say = D.readable;
    const fields = (host.dataset.fields || D.FIELDS.join(',')).split(',');
    const review = await D.review(host.dataset.review);
    const answer = await D.get(host.dataset.answer);
    const probability = f => host.dataset.probability?.replaceAll('{field}', f);
    // A field without a saved probability says so; it is never an error and never a made-up number.
    const saved = await Promise.all(fields.map(f => (probability(f) ? D.get(probability(f)).then(() => true, () => false) : false)));
    const compare = host.hasAttribute('data-compare');
    const ref = (inner, tag = 'td') => (compare ? `<${tag} class="d-live-ref fragment" data-fragment-index="1">${inner}</${tag}>` : '');
    const row = (f, i) => `<tr class="d-live-row"${answer[f] !== review.reference[f] ? ' data-differs' : ''}><th scope="row">${LABELS[f] ?? esc(f)}</th>`
      + `<td class="d-live-value"><span data-text-source="${esc(host.dataset.answer)}.${f}">${esc(say(answer[f]))}</span></td>`
      + (saved[i] ? `<td class="d-live-p"><span class="d-live-meter"><i></i></span><span class="d-num" data-source="${esc(probability(f))}" data-round="2">–</span></td>`
        : '<td class="d-live-p d-muted">not saved</td>')
      + ref(`<span data-text-source="disputed-reviews-v1.json#reviews[id=${esc(review.id)}].reference.${f}">${esc(say(review.reference[f]))}</span>`) + '</tr>';
    host.innerHTML = '<div class="d-live-bar"><span class="d-live-dot" aria-hidden="true"></span><span>POST /decide</span><span class="d-live-badge">Replay of saved answers</span></div>'
      + `<dl class="d-live-request"><div><dt>model</dt><dd>${esc(host.dataset.model || '')}${host.dataset.route ? ` <span class="d-muted">· ${esc(host.dataset.route)}</span>` : ''}</dd></div>`
      + `<div><dt>review</dt><dd>${esc(review.id)}</dd></div></dl>`
      + `<blockquote class="d-live-text"><span class="d-live-typed" data-review="${esc(review.id)}">${esc(review.feedback)}</span><span class="d-live-caret" aria-hidden="true"></span></blockquote>`
      + '<div class="d-live-response fragment" data-fragment-index="0">'
      + (host.dataset.latency ? `<p class="d-live-wait"><span class="d-live-track"><i></i></span><span><span class="d-num" data-source="${esc(host.dataset.latency)}" data-round="2">–</span> s</span><span class="d-muted">${esc(host.dataset.latencyLabel || '')}</span></p>` : '')
      + `<table class="d-live-answer"><thead><tr><th scope="col">Field</th><th scope="col">Answer</th><th scope="col">${esc(host.dataset.probabilityLabel || 'Probability')}</th>${ref('Reference', 'th')}</tr></thead>`
      + `<tbody>${fields.map(row).join('')}</tbody></table></div>`;
    host.dataset.built = '1';
    await D.bind(host);
    host.querySelectorAll('.d-live-p').forEach(td => td.querySelector('i')?.style.setProperty('--p', td.querySelector('[data-value]')?.dataset.value ?? 0));
  }

  // Typing: natural cadence with a pause after punctuation. The quote's height is locked first, so nothing jumps.
  function typeIn(host, now = still()) {
    const typed = host.querySelector('.d-live-typed'), box = host.querySelector('.d-live-text');
    if (!typed) return;
    const full = typed.dataset.full ?? (typed.dataset.full = typed.textContent);
    gsap.killTweensOf(typed);
    host.querySelector('.d-live-caret')?.classList.remove('is-done');
    typed.textContent = full;
    if (now) return;
    box.style.minHeight = `${box.offsetHeight}px`;
    const at = [];
    [...full].reduce((t, ch, i) => (at[i] = t + 0.026 + (/[,.!?;]/.test(ch) ? 0.14 : 0)), 0);
    typed.textContent = '';
    gsap.to(typed, { duration: at[at.length - 1] || 0, ease: 'none', delay: .35,
      onUpdate() { let n = 0; while (n < at.length && at[n] <= this.time()) n++; typed.textContent = full.slice(0, n); },
      onComplete: () => { typed.textContent = full; } });
  }

  // Send: a latency tick, then each field lands on its own beat and its probability bar fills.
  function send(host, now = still()) {
    host.querySelector('.d-live-caret')?.classList.add('is-done');
    const latency = host.querySelector('.d-live-wait [data-source]'), track = host.querySelector('.d-live-track i');
    const rows = [...host.querySelectorAll('.d-live-row')];
    if (now) {
      if (latency) countUp(latency, true);
      if (track) gsap.set(track, { scaleX: 1 });
      return rows.forEach(r => { const num = r.querySelector('.d-live-p [data-source]'); if (num) countUp(num, true); gsap.set(r.querySelector('.d-live-meter i'), { clearProps: 'transform' }); });
    }
    const wait = Math.min(1.6, Math.max(0.6, Number(latency?.dataset.value) || 0.8));
    const tl = gsap.timeline();
    if (track) tl.fromTo(track, { scaleX: 0 }, { scaleX: 1, duration: wait, ease: 'none' }, 0);
    if (latency) tl.add(() => { latency.dataset.duration = String(wait); countUp(latency); }, 0);
    rows.forEach((r, i) => {
      const at = wait + 0.15 + i * 0.42, meter = r.querySelector('.d-live-meter i'), num = r.querySelector('.d-live-p [data-source]');
      tl.fromTo([...r.cells].filter(c => !c.classList.contains('d-live-ref')), { autoAlpha: 0, y: 18 }, { autoAlpha: 1, y: 0, duration: .45, ease: EASE, stagger: .06, clearProps: 'transform' }, at);
      if (meter && num) {
        tl.fromTo(meter, { scaleX: 0 }, { scaleX: Number(num.dataset.value), duration: .7, ease: 'power2.out' }, at + .12);
        tl.add(() => { num.dataset.duration = '.7'; countUp(num); }, at + .12);
      }
    });
  }

  function enter(slide, now = still()) {
    if (!slide) return;
    slide.querySelectorAll('[data-split]').forEach(el => headline(el, now));
    slide.querySelectorAll('[data-countup]').forEach(el => hiddenFragment(el) || countUp(el, now));
    slide.querySelectorAll('[data-stagger]').forEach(el => hiddenFragment(el) || stagger(el, now));
    slide.querySelectorAll('.d-track').forEach(track => { if (!now) gsap.set(track, { '--progress': 0 }); drawTimeline(track, now); });
    slide.querySelectorAll('.d-replay').forEach(host => tally(host, true));
    slide.querySelectorAll('.d-live').forEach(host => typeIn(host, now));
  }

  function fragment(f, shown) {
    const now = still();
    if (f.matches('.d-replay-row')) { if (shown) rowIn(f, now); return tally(f.closest('.d-replay'), now); }
    if (f.matches('.d-event')) { if (shown) dropEvent(f, now); return drawTimeline(f.closest('.d-track'), now); }
    if (f.matches('.d-live-response')) {
      if (shown) send(f.closest('.d-live'), now);
      else f.closest('.d-live').querySelector('.d-live-caret')?.classList.remove('is-done');
      return;
    }
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
    return Promise.all([
      ...[...root.querySelectorAll('.d-replay')].map(host => buildReplay(host).catch(error => window.DeckData.report(`replay ${host.dataset.review}: ${error.message}`))),
      ...[...root.querySelectorAll('.d-live')].map(host => buildLive(host).catch(error => window.DeckData.report(`live replay ${host.dataset.review}: ${error.message}`))),
    ]);
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

  window.DeckMotion = { still, countUp, stagger, split, headline, flip, drawTimeline, dropEvent, buildReplay, tally, buildLive, typeIn, send, enter, prepare, wire };
})();
