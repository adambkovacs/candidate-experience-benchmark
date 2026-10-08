/* Nine-cell matrix glyph: three prompt versions across (P0, P1, P2), three fresh passes down. Each cell is one saved
   run, coloured by its all-four score on a fixed 40-to-60 scale and labelled with the number. Blank means no run.
   <figure data-c="matrix" data-matrix="jev"></figure>. Cells resolve from public-site feeds via data-source. */
(() => {
  'use strict';
  const C = window.DeckContent, gsap = window.gsap;
  const P = ['P0', 'P1', 'P2'];
  const FRESH = ['fresh1', 'fresh2', 'fresh3'];
  // cell(prompt, pass) returns [source, statusSource] or null for "no run".
  const supp = id => (p, i) => [`supplemental-decision-runs-v1.json#runs[id=${id}-${FRESH[i]}-${p.toLowerCase()}].metrics.all_four`,
    `supplemental-decision-runs-v1.json#runs[id=${id}-${FRESH[i]}-${p.toLowerCase()}].resultStatus`];
  const SPECS = {
    jev: { name: 'Jev 1.13', sub: 'via OpenRouter, native', cell: (p, i) => [`jev-native-prompt-findings.json#passes.${p}.${FRESH[i]}.score.allFour`, `jev-native-prompt-findings.json#passes.${p}.${FRESH[i]}.status`] },
    opus: { name: 'Opus 5.5', sub: 'high effort, batch 10', cell: (p, i) => [`claude-roster-repeats.json#series[configuration=opus55-high-batch10].threePassSummary.${p}.allFour.values[${i}]`] },
    sonnet: { name: 'Sonnet 5.5', sub: 'xhigh effort', cell: (p, i) => [`sonnet55-fresh-matched3.json#threePassSummary.xhigh.${p}.allFour.values[${i}]`] },
    gemma: { name: 'Gemma 4 26B', sub: 'A4B, thinking on', cell: (p, i) => [`extended-run-catalog-v1.json#runs[id=extended-openrouter-paid-gemma4-26b-a4b-on-${FRESH[i]}-${p.toLowerCase()}].metrics.all_four`,
      `extended-run-catalog-v1.json#runs[id=extended-openrouter-paid-gemma4-26b-a4b-on-${FRESH[i]}-${p.toLowerCase()}].resultStatus`] },
    qwen: { name: 'Qwen3.8 27B', sub: 'low effort, one pass each', cell: (p, i) => (i ? null : [`data.json#runs[id=openrouter-qwen27-low-darkbloom-fp4${p === 'P0' ? '' : `--${p.toLowerCase()}`}].metrics.all_four`]) },
    clef: { name: 'Clef', sub: 'Cloudflare, native', cell: supp('clef-openrouter-native') },
    luna: { name: 'Luna Decisions', sub: 'OpenAI, native', cell: supp('luna-decisions-openrouter-native') },
    clefFlash: { name: 'Clef Flash', sub: 'Cloudflare, native', cell: supp('clef-flash-openrouter-native') },
    solar: { name: 'Solar Decide', sub: 'Upstage, native', cell: supp('solar-decide-native') },
    perplexity: { name: 'Perplexity Decider', sub: 'V1 27B, native', cell: supp('perplexity-decider-native') },
  };
  const COMPLETE = new Set(['complete', 'completed']);

  // Fixed scale so every glyph in the deck is comparable: 40 ink, 52 brand blue, 60 near-white.
  const STOPS = [[40, [43, 54, 80]], [52, [21, 101, 192]], [60, [227, 238, 252]]];
  function colour(v) {
    const x = Math.max(40, Math.min(60, v));
    const i = x <= 52 ? 0 : 1, [a, ca] = STOPS[i], [b, cb] = STOPS[i + 1], t = (x - a) / (b - a);
    return `rgb(${ca.map((c, k) => Math.round(c + (cb[k] - c) * t)).join(',')})`;
  }

  function build(el) {
    const spec = SPECS[el.dataset.matrix];
    if (!spec) throw new Error(`unknown matrix "${el.dataset.matrix}"`);
    const first = spec.cell('P0', 0);
    const cells = [0, 1, 2].map(i => P.map(p => {
      const c = spec.cell(p, i);
      if (!c) return '<div class="c-cell is-empty" title="no run"></div>';
      return `<div class="c-cell" data-cell-status="${C.esc(c[1] || '')}"><span class="c-cell-n" data-source="${C.esc(c[0])}">–</span></div>`;
    }).join('')).join('');
    el.classList.add('c-mx');
    el.innerHTML = `<figcaption><b>${C.esc(spec.name)}</b><span>${C.esc(spec.sub)}</span></figcaption>
      <p class="c-mx-score"><span class="d-num" data-source="${C.esc(first[0])}" data-countup>–</span><small>P0, pass 1</small></p>
      <div class="c-mx-grid"><i>P0</i><i>P1</i><i>P2</i>${cells}</div>`;
    return C.bind(el).then(() => paint(el));
  }

  // Colour each cell from its bound number; a run that stopped shows "stopped", an interrupted-then-completed run gets a notch.
  async function paint(el) {
    for (const cell of el.querySelectorAll('.c-cell:not(.is-empty)')) {
      const n = cell.querySelector('.c-cell-n');
      const status = cell.dataset.cellStatus ? await C.value(cell.dataset.cellStatus) : 'complete';
      cell.dataset.status = status;
      if (status === 'stopped') {
        n.removeAttribute('data-source');
        n.textContent = '';
        cell.classList.add('is-stopped');
        cell.insertAdjacentHTML('beforeend', '<span class="c-cell-note" data-status-source="' + C.esc(cell.dataset.cellStatus) + '">stopped</span>');
        continue;
      }
      if (!COMPLETE.has(status)) cell.classList.add('is-patched');
      const v = Number(n.textContent);
      cell.style.setProperty('--fill', colour(v));
      cell.classList.toggle('is-light', v >= 56);
    }
  }

  function render(el, step, { animate }) {
    const cells = el.querySelectorAll('.c-cell');
    C.kill(el);
    if (!animate) return gsap.set(cells, { clearProps: 'opacity,transform' });
    // Columns (prompt versions) fill left to right, passes top to bottom; each matrix starts a beat after the last.
    const order = [...cells].sort((a, b) => (index(a) % 3) - (index(b) % 3) || index(a) - index(b));
    const delay = Number(el.dataset.delay || 0);
    C.timeline(el, { delay }).fromTo(order, { opacity: 0, scale: 0.55 }, { opacity: 1, scale: 1, duration: 0.45, ease: 'power3.out', stagger: 0.06, clearProps: 'transform' });
  }
  const index = cell => [...cell.parentNode.querySelectorAll('.c-cell')].indexOf(cell);

  C.register('matrix', { build, render });
  C.matrixColour = colour;
})();
