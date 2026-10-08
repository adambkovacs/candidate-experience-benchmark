/* Read page motion: scroll reveals, count-ups on the Read numbers, the nine-cell glyphs settling in, the hero exit,
   and a small magnetic pull on the primary action. Timings and easing follow the talk deck (deck/MOTION.md):
   settle 0.7s, 0.08s apart, 28px rise, power3.out; count-ups 1.4s power2.out ending on the exact text; no overshoot.
   All of it is optional. Without this file, without GSAP, or with reduced motion, the page reads the same. */
(() => {
  'use strict';
  const gsap = globalThis.gsap;
  if (!gsap || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const fold = innerHeight * 0.9;

  // Only blocks that start below the first screen are hidden, only by opacity and a short rise, and they never
  // leave the tab order. An IntersectionObserver reads live layout, so late content cannot strand a block.
  const blocks = [
    '#decisions .section-intro', '.decision-strip li', '#decisions .hero-example', '.part-mark', '.finding-copy', '.finding-figure',
    '.rule .section-intro', '.rule-pair', '.rule-queue', '#deep-insights', '.limits .section-intro', '.limit-list li',
    '#team > div:first-child', '#team .audience-notes article', '.door', '.harness-note', 'body > footer'
  ].join(',');
  const hidden = gsap.utils.toArray(blocks).filter(el => !el.closest('details:not([open])') && el.getBoundingClientRect().top > fold);
  const show = (els, instant) => {
    const list = els.filter(el => el.classList.contains('js-reveal'));
    if (!list.length) return;
    list.forEach(el => el.classList.remove('js-reveal'));
    gsap.to(list, {opacity: 1, y: 0, duration: instant ? 0 : 0.7, ease: 'power3.out', stagger: instant ? 0 : 0.08, overwrite: true, clearProps: 'opacity,transform'});
    const rules = list.filter(el => el.matches('.part-mark')).map(el => el.querySelector('i')).filter(Boolean);
    if (rules.length && !instant) gsap.fromTo(rules, {scaleX: 0, transformOrigin: 'left center'}, {scaleX: 1, duration: 0.9, ease: 'power2.inOut', clearProps: 'transform'});
  };
  hidden.forEach(el => el.classList.add('js-reveal'));
  gsap.set(hidden, {opacity: 0, y: 28});

  const REVEAL = () => {};
  const pending = new Map();
  const flush = (els, instant) => {
    const reveals = [];
    for (const el of els) {
      const run = pending.get(el);
      if (!run) continue;
      pending.delete(el);
      watcher.unobserve(el);
      if (run === REVEAL) reveals.push(el); else run(instant);
    }
    show(reveals, instant);
  };
  const watcher = new IntersectionObserver(entries => flush(entries.filter(e => e.isIntersecting).map(e => e.target), false), {rootMargin: '0px 0px -6% 0px'});
  hidden.forEach(el => { pending.set(el, REVEAL); watcher.observe(el); });
  // Blocks jumped over by an anchor or the End key never intersect; finish them once scrolling settles.
  let settled = 0;
  addEventListener('scroll', () => {
    clearTimeout(settled);
    settled = setTimeout(() => flush([...pending.keys()].filter(el => el.getBoundingClientRect().bottom < 0), true), 150);
  }, {passive: true});
  document.addEventListener('focusin', event => {
    const block = event.target.closest('.js-reveal');
    if (block) flush([block], true);
    for (let el = event.target; el && el !== document.body; el = el.parentElement) gsap.getTweensOf(el).forEach(tween => tween.progress(1));
  });
  addEventListener('beforeprint', () => flush([...pending.keys()], true));

  // Nine-cell glyphs: cells settle left to right, row by row, when the set comes into view.
  for (const set of document.querySelectorAll('.ninecell-set')) {
    if (set.getBoundingClientRect().top < fold) continue;
    const cells = [...set.querySelectorAll('td')];
    gsap.set(cells, {opacity: 0, scale: 0.7});
    // The set may also be a reveal block; run both from the one observer entry.
    const reveal = pending.get(set) === REVEAL;
    pending.set(set, instant => {
      if (reveal) show([set], instant);
      gsap.to(cells, {opacity: 1, scale: 1, duration: instant ? 0 : 0.7, ease: 'power3.out', stagger: instant ? 0 : 0.03, delay: instant ? 0 : 0.15, clearProps: 'opacity,transform'});
    });
    watcher.observe(set);
  }

  // Count-ups end on the exact text. Each number's width is fixed first, so nothing shifts, and screen readers
  // hear the real value throughout. Measure all, then write all.
  const counts = [...document.querySelectorAll('[data-countup]')].map(el => {
    const node = [...el.childNodes].find(child => child.nodeType === 3 && /\d/.test(child.nodeValue));
    const box = el.getBoundingClientRect();
    return {el, node, final: node ? parseInt(node.nodeValue.replace(/,/g, ''), 10) : NaN, top: box.top, width: box.width};
  }).filter(item => Number.isFinite(item.final) && item.top >= fold);
  for (const {el, node, final, width} of counts) {
    const original = node.nodeValue;
    const shown = document.createElement('span');
    const spoken = document.createElement('span');
    shown.setAttribute('aria-hidden', 'true');
    shown.textContent = '0';
    spoken.className = 'sr-only';
    spoken.textContent = original;
    el.style.display = 'inline-block';
    el.style.minWidth = `${Math.ceil(width)}px`;
    node.replaceWith(shown, spoken);
    const counter = {value: 0};
    const finish = () => { shown.replaceWith(document.createTextNode(original)); spoken.remove(); el.style.minWidth = ''; el.style.display = ''; };
    pending.set(el, instant => {
      if (instant || final === 0) return finish();
      gsap.to(counter, {value: final, duration: 1.4, ease: 'power2.out', onUpdate: () => { shown.textContent = String(Math.round(counter.value)); }, onComplete: finish});
    });
    watcher.observe(el);
  }

  // Hero exit: the copy drifts up and dims only after the hero is half gone. A passive listener, no ScrollTrigger:
  // its refresh restored stale scroll positions while panels rendered and sent deep links off target.
  const hero = document.getElementById('overview');
  const copy = hero && hero.querySelector('.intro-copy');
  if (hero && copy) {
    let heroHeight = hero.offsetHeight || 1;
    new ResizeObserver(() => { heroHeight = hero.offsetHeight || 1; }).observe(hero);
    let queued = false, last = -1;
    const paint = () => {
      queued = false;
      const late = Math.max(0, Math.min(1, scrollY / heroHeight) - 0.5) * 2;
      if (late === last) return;
      last = late;
      gsap.set(copy, {y: -40 * late, opacity: 1 - 0.5 * late});
    };
    addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(paint); } }, {passive: true});
    paint();
  }

  // Magnetic primary action: a small pull toward the pointer and an even return, no overshoot.
  if (matchMedia('(hover: hover) and (pointer: fine)').matches) {
    for (const el of document.querySelectorAll('[data-magnetic]')) {
      const toX = gsap.quickTo(el, 'x', {duration: 0.5, ease: 'power3.out'});
      const toY = gsap.quickTo(el, 'y', {duration: 0.5, ease: 'power3.out'});
      let box = null;
      el.addEventListener('pointerenter', () => { box = el.getBoundingClientRect(); }, {passive: true});
      el.addEventListener('pointermove', event => {
        if (!box) return;
        toX(((event.clientX - box.left) / box.width - 0.5) * 14);
        toY(((event.clientY - box.top) / box.height - 0.5) * 10);
      }, {passive: true});
      el.addEventListener('pointerleave', () => { box = null; toX(0); toY(0); }, {passive: true});
    }
  }
})();
