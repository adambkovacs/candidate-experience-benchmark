/* Review cards: saved answers from disputed-reviews-v1.json replayed against the frozen reference.
   data-c="flip"   S8: seven model cards face down; step 1 auto-plays the flips, step 2 shows the extra row.
   data-c="wall"   S9: six hard-review cards, one per step, each auto-plays in under 3 seconds.
   data-c="replay" A13-A18: one review, seven model rows; step 1 lands the rows one by one.
   Review text is never animated; trigger phrases are wrapped in <mark> without changing the text. */
(() => {
  'use strict';
  const C = window.DeckContent, gsap = window.gsap, { DeckData } = window;
  const SHORT = { 'Liquid D1': 'Liquid', 'Tev 1 4B': 'Tev', 'Solar Decide': 'Solar', 'Luna Decisions': 'Luna', 'Perplexity Decider V1 27B': 'Perplexity' };
  const short = name => SHORT[name] ?? name;
  const MAX_CARD = 2.9; // seconds; the outline caps each card's auto-play at about 3

  // Wrap each "phrase" (|-separated, in order) inside the bound review text. textContent stays identical.
  function mark(textEl, phrases) {
    const text = textEl.textContent;
    const spans = [];
    let from = 0;
    for (const phrase of phrases.split('|').filter(Boolean)) {
      const at = text.indexOf(phrase, from);
      if (at < 0) { DeckData.report(`trigger phrase "${phrase}" not found in ${textEl.dataset.review}`); continue; }
      spans.push([at, at + phrase.length]);
      from = at + phrase.length;
    }
    if (!spans.length) return;
    textEl.textContent = '';
    let pos = 0;
    for (const [a, b] of spans) {
      textEl.append(text.slice(pos, a));
      const m = document.createElement('mark');
      m.className = 'c-mark';
      m.textContent = text.slice(a, b);
      textEl.append(m);
      pos = b;
    }
    textEl.append(text.slice(pos));
  }

  // Wait until data.js has bound the review text, then mark it.
  async function markWhenBound(textEl, phrases) {
    if (!phrases) return;
    const review = await DeckData.review(textEl.dataset.review);
    if (textEl.textContent !== review.feedback) textEl.textContent = review.feedback;
    mark(textEl, phrases);
  }

  // data-answer names the feed path of every label, so verify/content-numbers.mjs can check the text against the feed.
  const fieldRow = (f, value, ref, src) => `<li class="${value === ref ? '' : 'is-diff'}"><span>${C.FIELD_LABEL[f]}</span><b data-answer="${C.esc(`${src}.${f}`)}">${C.esc(C.say(value))}</b></li>`;
  const R = id => `disputed-reviews-v1.json#reviews[id=${id}]`;

  // ---------- S8: flip ----------
  async function buildFlip(el) {
    const { review, answers } = await DeckData.answers(el.dataset.reviewId);
    const order = (el.dataset.order || '').split(',');
    const sorted = order.map(id => answers.find(a => a.id === id)).filter(Boolean);
    if (sorted.length !== answers.length) throw new Error('flip order does not cover every model');
    el.querySelector('.c-flip-row').innerHTML = sorted.map(a => {
      const match = C.FIELDS.every(f => a.prediction?.[f] === review.reference[f]);
      return `<div class="c-flip" data-match="${match}"><div class="c-flip-in">
        <div class="c-face c-back"><b>${C.esc(short(a.name))}</b><span class="d-ladder" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span><small>saved answer</small></div>
        <div class="c-face c-front"><b>${C.esc(short(a.name))}</b><ul>${C.FIELDS.map(f => fieldRow(f, a.prediction?.[f], review.reference[f], `${R(review.id)}.answers[model_id=${a.id}].prediction`)).join('')}</ul></div>
      </div></div>`;
    }).join('');
    el.querySelector('.c-key').innerHTML = `<span>Key</span>${C.FIELDS.map(f => `<b><small>${C.FIELD_LABEL[f]}</small><span data-answer="${R(review.id)}.reference.${f}">${C.esc(C.say(review.reference[f]))}</span></b>`).join('')}`;
    const jev = el.querySelector('[data-jev-case]');
    if (jev) {
      const c = await DeckData.get(jev.dataset.jevCase);
      jev.innerHTML = C.FIELDS.map(f => fieldRow(f, c.prediction[f], review.reference[f], `${jev.dataset.jevCase}.prediction`)).join('');
    }
  }

  // Bound numbers never change text mid-animation (print pages and numbers.mjs read them); progress shows in pips.
  function renderFlip(el, step, { animate }) {
    const inner = [...el.querySelectorAll('.c-flip-in')];
    const pips = [...el.querySelectorAll('.c-pip')];
    const tally = el.querySelector('.c-flagged'), extra = el.querySelectorAll('.c-flip-extra');
    C.kill(el);
    C.badge(el.closest('section'), step >= 1);
    gsap.set(inner, { rotationY: step >= 1 ? 180 : 0 });
    pips.forEach(p => p.classList.toggle('is-on', step >= 1));
    gsap.set(pips.map(p => p.querySelector('b')), { clearProps: 'transform' }); // an interrupted fuse falls back to the class
    gsap.set(tally, { autoAlpha: step >= 1 ? 1 : 0, scale: 1 }); // a step-1 sequence cut short must not leave the tally scaled
    gsap.set(extra, { autoAlpha: step >= 2 ? 1 : 0, y: 0 });
    if (!animate || step === 0) return;
    if (step === 2) return C.timeline(el).fromTo(extra, { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, duration: 0.6, ease: 'power3.out', stagger: 0.25 });
    // Step 1: each pip fills like a fuse, then its card flips (1.8 s per card). No idle gaps, so "motion done" means done.
    gsap.set(inner, { rotationY: 0 }); gsap.set(tally, { autoAlpha: 0 });
    pips.forEach(p => p.classList.remove('is-on'));
    const fills = pips.map(p => p.querySelector('b'));
    gsap.set(fills, { scaleX: 0 });
    const tl = C.timeline(el);
    inner.forEach((card, i) => {
      tl.to(fills[i], { scaleX: 1, duration: i ? 1.1 : 0.3, ease: 'none' })
        .to(card, { rotationY: 180, duration: 0.7, ease: 'power3.inOut' });
    });
    tl.fromTo(tally, { autoAlpha: 0, scale: 1.25 }, { autoAlpha: 1, scale: 1, duration: 0.45, ease: 'power3.out' })
      .add(() => { pips.forEach(p => p.classList.add('is-on')); gsap.set(fills, { clearProps: 'transform' }); });
  }

  // ---------- S9: wall ----------
  async function buildWall(el) {
    const { models } = await DeckData.feed('disputed-reviews-v1.json');
    await Promise.all([...el.querySelectorAll('.c-hard')].map(async card => {
      const { review, answers } = await DeckData.answers(card.dataset.reviewId);
      await markWhenBound(card.querySelector('[data-review]'), card.dataset.marks);
      card.querySelector('.c-hard-key').innerHTML = `<span>Key</span>${C.FIELDS.map(f => `<b data-answer="${R(review.id)}.reference.${f}">${C.esc(C.say(review.reference[f]))}</b>`).join('<i>·</i>')}`;
      card.querySelector('.c-tiles').innerHTML = answers.map(a => `<span class="c-tile" title="${C.esc(a.name)}">${C.FIELDS.map(f =>
        `<i class="${a.prediction?.[f] === review.reference[f] ? '' : 'is-diff'}"></i>`).join('')}<small>${C.esc(short(a.name))}</small></span>`).join('');
      if (models.length !== answers.length) throw new Error('model count mismatch');
    }));
  }

  function renderWall(el, step, { animate }) {
    const cards = [...el.querySelectorAll('.c-hard')];
    C.kill(el);
    C.badge(el.closest('section'), step >= 1);
    cards.forEach((card, i) => card.classList.toggle('is-shown', i < step));
    gsap.set(cards, { clearProps: 'opacity,transform' });
    el.querySelectorAll('.c-hard .c-tile, .c-hard .c-tile i, .c-hard-key').forEach(n => gsap.set(n, { clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' }));
    // Never hand a <mark> to GSAP's transform parser: on a hidden slide it re-parents the node to measure it and puts it
    // back before the next element sibling, which moves a mark followed only by text to the end of the review.
    el.querySelectorAll('.c-mark').forEach(n => n.style.removeProperty('background-size'));
    el.querySelectorAll('.c-hard').forEach(card => card.classList.remove('is-playing'));
    if (!animate || step === 0) return;
    const card = cards[step - 1];
    const marks = card.querySelectorAll('.c-mark'), key = card.querySelector('.c-hard-key');
    const tiles = card.querySelectorAll('.c-tile'), diffs = card.querySelectorAll('.c-tile i.is-diff');
    const counters = card.querySelectorAll('[data-countup]');
    card.classList.add('is-playing');
    const tl = C.timeline(el, { onComplete: () => card.classList.remove('is-playing') });
    tl.fromTo(card, { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.4, ease: 'power3.out' }) // text appears, never moves
      .fromTo(marks, { backgroundSize: '0% 0.2em' }, { backgroundSize: '100% 0.2em', duration: 0.45, ease: 'power2.out', stagger: 0.15 }, 0.35)
      .fromTo(key, { opacity: 0, scale: 1.3 }, { opacity: 1, scale: 1, duration: 0.3, ease: 'power3.out' }, 0.8)
      .fromTo(tiles, { opacity: 0, y: -14 }, { opacity: 1, y: 0, duration: 0.25, ease: 'power3.out', stagger: 0.12 }, 1.1)
      .fromTo(diffs, { backgroundColor: 'rgba(251,252,254,.18)', scaleY: 0.2 }, { backgroundColor: '#f57c00', scaleY: 1, duration: 0.25, ease: 'power2.out', stagger: 0.04, clearProps: 'opacity,visibility,transform,clipPath,backgroundColor' }, 1.35)
      .add(() => counters.forEach(n => window.DeckMotion.countUp(n)), '>')
      .to({}, { duration: Number(counters[0]?.dataset.duration ?? 0.6) }); // keep the timeline alive while the counters run
    if (tl.duration() > MAX_CARD + 0.6) tl.timeScale(tl.duration() / MAX_CARD);
  }

  // ---------- A13-A18: replay table ----------
  async function buildReplay(el) {
    const { review, answers } = await DeckData.answers(el.dataset.reviewId);
    await markWhenBound(el.querySelector('[data-review]'), el.dataset.marks);
    const cells = (p, diff, src) => C.FIELDS.map(f => {
      const d = diff && p?.[f] !== review.reference[f];
      return `<td class="${d ? 'is-diff' : ''}" data-answer="${C.esc(`${src}.${f}`)}">${C.esc(C.say(p?.[f]))}</td>`;
    }).join('');
    el.querySelector('tbody').innerHTML = `<tr class="is-reference"><th scope="row">Key</th>${cells(review.reference, false, `${R(review.id)}.reference`)}<td></td></tr>`
      + answers.map(a => {
        const miss = C.FIELDS.some(f => a.prediction?.[f] !== review.reference[f]);
        return `<tr class="c-row"><th scope="row">${C.esc(a.name)}</th>${cells(a.prediction, true, `${R(review.id)}.answers[model_id=${a.id}].prediction`)}<td class="c-verdict ${miss ? 'is-miss' : 'is-match'}">${miss ? 'miss' : 'match'}</td></tr>`;
      }).join('');
  }

  function renderReplay(el, step, { animate }) {
    const rows = el.querySelectorAll('.c-row'), diffs = el.querySelectorAll('.c-row td.is-diff');
    C.kill(el);
    C.badge(el.closest('section'), step >= 1);
    el.classList.toggle('is-open', step >= 1);
    gsap.set([...rows, ...diffs], { clearProps: 'opacity,transform,color' });
    if (!animate || step === 0) return;
    C.timeline(el)
      .fromTo(rows, { opacity: 0, x: -16 }, { opacity: 1, x: 0, duration: 0.3, ease: 'power3.out', stagger: 0.28, clearProps: 'transform' })
      .fromTo(diffs, { color: '#fbfcfe' }, { color: '#f57c00', duration: 0.3, stagger: 0.05, clearProps: 'color' }, 0.5);
  }

  C.register('flip', { build: buildFlip, render: renderFlip });
  C.register('wall', { build: buildWall, render: renderWall });
  C.register('replay', { build: buildReplay, render: renderReplay });
})();
