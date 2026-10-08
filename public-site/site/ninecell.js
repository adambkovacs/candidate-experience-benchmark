/* Explore glue for the nine-cell repeat glyph. repeats.js draws each P0/P1/P2 x pass row with a <meter>; this copies
   the meter's score onto the row as --score and data-band so site.css can shade it. Panel files stay unedited. */
(() => {
  'use strict';
  const paint = root => {
    for (const row of root.querySelectorAll('.repeat-bar-row')) {
      const meter = row.querySelector(':scope > meter');
      if (!meter) continue;
      const score = Number(meter.value);
      row.classList.add('has-score');
      row.style.setProperty('--score', String(score));
      row.dataset.band = score >= 50 ? 'high' : 'low';
    }
  };
  const start = chart => {
    paint(chart);
    new MutationObserver(() => paint(chart)).observe(chart, {childList: true, subtree: true});
  };
  const chart = document.getElementById('repeat-chart');
  if (chart) { start(chart); return; }
  // repeats.js builds #repeat-chart after its feed loads.
  const host = document.getElementById('repeat-results');
  if (!host) return;
  const wait = new MutationObserver(() => {
    const found = document.getElementById('repeat-chart');
    if (found) { wait.disconnect(); start(found); }
  });
  wait.observe(host, {childList: true, subtree: true});
})();
