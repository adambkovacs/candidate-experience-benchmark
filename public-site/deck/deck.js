/* Boot. Normal view navigates immediately and binds data as it arrives.
   Print view (?print-pdf) waits for data so every PDF page carries the real, source-bound numbers. */
(() => {
  'use strict';
  const { Reveal, DeckData, DeckMotion, DeckScene } = window;
  const print = /print-pdf/i.test(location.search);
  const config = {
    // ponytail: Reveal rounds its scale to the nearest 0.01, which can overshoot the viewport by up to 0.5%.
    // A 1% margin keeps the rounded stage inside the viewport down to half scale (960px wide); below that it can clip by <1%.
    width: 1920, height: 1080, margin: 0.01, minScale: 0.05, maxScale: 4,
    center: false, display: 'flex',
    hash: true, respondToHashChanges: true, history: false, fragmentInURL: true,
    controls: true, controlsLayout: 'bottom-right', controlsTutorial: false,
    progress: true, slideNumber: 'c/t', showSlideNumber: 'all',
    transition: DeckMotion.still() ? 'none' : 'fade', transitionSpeed: 'fast', backgroundTransition: 'none',
    scrollActivationWidth: null, // never fall back to Reveal's scroll view on narrow screens
    pdfSeparateFragments: true, pdfMaxPagesPerSlide: 1,
    hideInactiveCursor: true,
    plugins: [window.RevealNotes],
  };
  const initialHash = location.hash; // read before Reveal normalises it
  DeckMotion.wire(Reveal);
  const progress = () => document.querySelector('.reveal .progress')?.style.setProperty('--p', Reveal.getProgress().toFixed(4));
  ['ready', 'slidechanged', 'fragmentshown', 'fragmenthidden'].forEach(type => Reveal.on(type, progress));
  const prepared = DeckData.ready.then(() => DeckMotion.prepare());
  if (print) prepared.finally(() => Reveal.initialize(config));
  else {
    Reveal.initialize(config);
    prepared.then(() => (Reveal.isReady() ? afterData() : Reveal.on('ready', afterData)));
  }
  // Replay rows are built from data after Reveal first reads the hash, so a reload on "#/slide/3" lands on step 0.
  // Once the rows exist, restore the step, unless the presenter has already moved to another slide.
  function afterData() {
    Reveal.sync();
    const [, id, step] = /^#\/([^/]+)\/(\d+)$/.exec(initialHash) || [];
    if (id && Reveal.getCurrentSlide()?.id === id) { const { h, v } = Reveal.getIndices(); Reveal.slide(h, v, Number(step)); }
  }
  DeckScene.start(Reveal);
  window.DeckReady = prepared.then(() => (Reveal.isReady() ? true : new Promise(resolve => Reveal.on('ready', () => resolve(true)))));
})();
