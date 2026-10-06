/* Progressive enhancement for the source-bound Clef repeat report. */
(() => {
  'use strict';
  const host = document.getElementById('clef-repeat-chart');
  if (!host) return;

  const prompts = ['P0', 'P1', 'P2'];
  const passes = ['fresh1', 'fresh2', 'fresh3'];
  const label = { P0: 'Base prompt', P1: 'Classifier instructions', P2: 'Decision rules' };
  const sourceUrl = './clef-closed-repeat-findings.json';
  const integer = (n) => Number.isInteger(n) && n >= 0 && n <= 60;

  function read(report) {
    if (report?.kind !== 'clef-closed-repeat-findings-public-v1' || report.model !== 'clef' ||
        report.declaredCells !== 9 || report.completeCleanCells !== 7 || report.interruptedCells !== 2 ||
        !Array.isArray(report.cells) || report.cells.length !== 9 || !Array.isArray(report.cleanRepeatFlips)) {
      throw new Error('Clef repeat report has changed');
    }
    const cells = new Map();
    for (const cell of report.cells) {
      if (!prompts.includes(cell.condition) || !passes.includes(cell.repeat)) throw new Error('Unexpected cell');
      const key = `${cell.condition}:${cell.repeat}`;
      if (cells.has(key) || !integer(cell.valid) || !integer(cell.unknownOutcome) || !integer(cell.neverSent)) {
        throw new Error('Incomplete cell');
      }
      if (cell.status === 'complete') {
        if (cell.valid !== 60 || cell.unknownOutcome !== 0 || cell.neverSent !== 0 ||
            !integer(cell.matchedAllFour) || typeof cell.agreementOf60 !== 'number') throw new Error('Invalid clean score');
      } else if (cell.status === 'interrupted_composite' || cell.status === 'interrupted_provider') {
        if (cell.agreementOf60 !== null || cell.unknownOutcome + cell.valid + cell.neverSent !== 60) {
          throw new Error('Invalid interrupted cell');
        }
      } else throw new Error('Unknown cell status');
      cells.set(key, cell);
    }
    if (cells.size !== 9) throw new Error('Missing cell');
    const cell = (p, r) => cells.get(`${p}:${r}`);
    if (!passes.every(r => cell('P0', r).status === 'complete' && cell('P0', r).matchedAllFour === 53) ||
        !passes.every((r, i) => cell('P1', r).status === 'complete' && cell('P1', r).matchedAllFour === [52, 51, 51][i]) ||
        cell('P2', 'fresh1').status !== 'interrupted_composite' || cell('P2', 'fresh1').valid !== 59 ||
        cell('P2', 'fresh1').matchedAllFour !== 48 || cell('P2', 'fresh1').unknownOutcome !== 1 ||
        cell('P2', 'fresh2').status !== 'complete' || cell('P2', 'fresh2').matchedAllFour !== 49 ||
        cell('P2', 'fresh3').status !== 'interrupted_provider' || cell('P2', 'fresh3').unknownOutcome !== 1 ||
        cell('P2', 'fresh3').neverSent !== 59) throw new Error('Clef conclusions changed');
    const flip = (p, a, b) => report.cleanRepeatFlips.find(f => f.condition === p && f.left === a && f.right === b);
    for (const [a, b] of [['fresh1', 'fresh2'], ['fresh1', 'fresh3'], ['fresh2', 'fresh3']]) {
      if (flip('P0', a, b)?.denominator !== 60 || flip('P0', a, b).anyFieldChanged !== 0) throw new Error('P0 repeat evidence changed');
    }
    for (const [a, b, count] of [['fresh1', 'fresh2', 1], ['fresh1', 'fresh3', 1], ['fresh2', 'fresh3', 0]]) {
      const f = flip('P1', a, b);
      if (f?.denominator !== 60 || f.anyFieldChanged !== count || f.perFieldChanged?.follow_up_needed !== count ||
          f.perFieldChanged?.sentiment !== 0 || f.perFieldChanged?.serious_concern_reported !== 0 ||
          f.perFieldChanged?.testimonial_potential !== 0) throw new Error('P1 repeat evidence changed');
    }
    return cell;
  }

  function scored(cell) {
    const score = cell.matchedAllFour;
    return `<div class="clef-repeat-score"><strong>${score}<span> / 60</span></strong><span class="clef-repeat-valid">60 valid</span></div>` +
      `<span class="clef-repeat-track" aria-hidden="true"><span style="width:${score / 60 * 100}%"></span></span>`;
  }

  function interrupted(cell) {
    if (cell.status === 'interrupted_composite') {
      return `<div class="clef-repeat-interrupted"><strong>Interrupted</strong><span>59 valid · 1 unknown</span>` +
        `<small>48 known four-label matches</small></div>`;
    }
    return `<div class="clef-repeat-interrupted"><strong>Interrupted</strong><span>1 unknown · 59 not sent</span></div>`;
  }

  function promptChanges(report, cell) {
    const pairs = report.matchedPromptDifferences;
    if (!Array.isArray(pairs) || pairs.length !== 5) throw new Error('Missing prompt comparisons');
    const seen = new Set();
    const rows = pairs.map(p => {
      const key = `${p.repeat}:${p.left}:${p.right}`;
      if (!passes.includes(p.repeat) || !prompts.includes(p.left) || !prompts.includes(p.right) ||
          prompts.indexOf(p.left) >= prompts.indexOf(p.right) || seen.has(key) ||
          cell(p.left, p.repeat).status !== 'complete' || cell(p.right, p.repeat).status !== 'complete' ||
          p.leftAllFour !== cell(p.left, p.repeat).matchedAllFour ||
          p.rightAllFour !== cell(p.right, p.repeat).matchedAllFour ||
          p.sharedValidDenominator !== 60 || !integer(p.gainedAllFour) || !integer(p.lostAllFour) ||
          !Array.isArray(p.becameAllFourCorrectIds) || !Array.isArray(p.lostAllFourCorrectIds) ||
          p.becameAllFourCorrectIds.length !== p.gainedAllFour ||
          p.lostAllFourCorrectIds.length !== p.lostAllFour ||
          p.rightAllFour - p.leftAllFour !== p.gainedAllFour - p.lostAllFour) {
        throw new Error('Invalid prompt comparison');
      }
      seen.add(key);
      return `<tr><th scope="row">Pass ${passes.indexOf(p.repeat) + 1}: ${p.left} → ${p.right}</th>` +
        `<td>${p.gainedAllFour} / 60</td><td>${p.lostAllFour} / 60</td></tr>`;
    }).join('');
    return `<details><summary>Did the added instructions improve the answers?</summary>` +
      `<p>These pairs returned all 60 answers. A gain means all four labels now match the reference; a loss means they matched before but no longer do. An answer can change and still be wrong.</p>` +
      `<div class="clef-repeat-scroll" role="region" aria-label="Clef prompt gains and losses" tabindex="0">` +
      `<table><caption class="clef-repeat-sr-only">Reviews gaining or losing four-label agreement</caption>` +
      `<thead><tr><th scope="col">Prompt change</th><th scope="col">Became correct</th><th scope="col">Became incorrect</th></tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p>Four pairs involving interrupted P2 runs are excluded from this table. Their missing outcomes remain in the run grid above.</p></details>`;
  }

  function render(cell, report) {
    const rows = prompts.map(p => `<tr><th scope="row"><span class="clef-repeat-prompt">${p}</span><span>${label[p]}</span></th>` +
      passes.map(r => { const c = cell(p, r); return `<td>${c.status === 'complete' ? scored(c) : interrupted(c)}</td>`; }).join('') + '</tr>').join('');
    return `<figure class="clef-repeat-chart" aria-labelledby="clef-repeat-title">` +
      `<figcaption><span class="clef-repeat-kicker">Clef · native interface</span>` +
      `<h3 id="clef-repeat-title">Seven full runs. Two interrupted.</h3>` +
      `<p>Each score counts reviews where all four answers matched the provisional reference, out of the same 60 reviews.</p></figcaption>` +
      `<div class="clef-repeat-scroll" role="region" aria-label="Clef scores by prompt and pass" tabindex="0">` +
      `<table><caption class="clef-repeat-sr-only">Clef four-label matches by prompt and fresh pass</caption>` +
      `<thead><tr><th scope="col">Prompt</th><th scope="col">Pass 1</th><th scope="col">Pass 2</th><th scope="col">Pass 3</th></tr></thead>` +
      `<tbody>${rows}</tbody></table></div>` +
      `<div class="clef-repeat-notes"><p><strong>P0 stayed fixed.</strong> Each pass scored 53/60, with no changed answers across passes.</p>` +
      `<p><strong>P1 changed once.</strong> Scores were 52/60, then 51/60 twice; one follow-up decision changed from the first pass.</p>` +
      `<p><strong>Only one P2 run returned all 60 answers.</strong> Pass 2 scored 49/60. The other two were interrupted.</p></div>` +
      promptChanges(report, cell) +
      `<p class="clef-repeat-source"><a href="${sourceUrl}">Source data and per-run evidence</a></p></figure>`;
  }

  fetch(sourceUrl, { cache: 'no-store' }).then(response => {
    if (!response.ok) throw new Error('Clef report unavailable');
    return response.json();
  }).then(report => { host.innerHTML = render(read(report), report); }).catch(() => {
    /* Keep the server-rendered fallback visible if the report is unavailable or changed. */
  });
})();
