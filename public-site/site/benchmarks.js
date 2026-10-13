/* Benchmark tables: leaderboard, hard reviews, per-decision matrix, stability, cost ledger.
   Fills <div class="bm-mount" data-bm="..."> only. Every number carries data-source="<feed>#<path>"
   (grammar of deck/verify/numbers.mjs) or data-derived="<formula>". */
(() => {
  'use strict';
  const mounts = [...document.querySelectorAll('.bm-mount[data-bm]')];
  if (!mounts.length) return;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const cache = new Map();
  const feed = name => {
    if (!cache.has(name)) cache.set(name, fetch(`./${name}`).then(r => { if (!r.ok) throw new Error(name); return r.json(); }));
    return cache.get(name);
  };
  const FIELDS = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const FIELD_HEAD = ['Sentiment', 'Follow-up', 'Serious concern', 'Testimonial'];
  const QUESTION = ['How was the experience?', 'Does someone need to follow up?', 'Does it report a serious concern?', 'Could it work as a testimonial?'];
  const WORD = {positive: 'Positive', negative: 'Negative', mixed: 'Mixed', neutral: 'Neutral', insufficient_information: "Can't tell", yes: 'Yes', no: 'No'};
  const word = v => v == null ? '–' : esc(WORD[v] || String(v).replace(/_/g, ' '));
  const DASH = '<span class="bm-none">–</span>';
  const n = (value, source, fmt) => value == null || value === '' ? DASH
    : `<span class="bm-n" data-source="${esc(source)}">${esc(fmt ? fmt(value) : value)}</span>`;
  const d = (text, formula) => `<span class="bm-n" data-derived="${esc(formula)}">${esc(text)}</span>`;
  const usd = v => `$${Number(v)}`;
  const busy = (el, on) => { el.setAttribute('aria-busy', on ? 'true' : 'false'); el.classList.toggle('bm-loading', on); };
  const fail = el => { busy(el, false); el.innerHTML = '<p class="bm-note">These results did not load.</p>'; };
  const wrap = (table, note) => `<div class="bm-scroll">${table}</div>${note ? `<p class="bm-note">${note}</p>` : ''}`;

  /* Where a merged run came from, so its numbers point at the feed that holds them. */
  const SUPP = /^(solar-decide|liquid-d1|tev1-4b|clef-openrouter|clef-flash-openrouter|luna-decisions-openrouter|perplexity-decider)-native-fresh[123]-p[012]$/;
  function origin(run) {
    if (run.id.startsWith('extended-')) return 'extended-run-catalog-v1.json';
    if (SUPP.test(run.id)) return 'supplemental-decision-runs-v1.json';
    if (/--pass1-p[012]$/.test(run.id) || /^clef(-flash)?-native-fresh1-p0$/.test(run.id)) return null; // built in app.js from a findings feed
    return 'data-provider-errors-v1.json';
  }
  function metric(run, field) {
    const v = run?.metrics?.[field];
    if (v == null) return DASH;
    const o = origin(run);
    return o ? n(v, `${o}#runs[id=${run.id}].metrics.${field}`) : d(v, `app.js merge of ${run.id}.metrics.${field}`);
  }
  function cost(run) {
    const c = run?.cost || {};
    const o = origin(run);
    for (const key of ['knownUsd', 'actualUsd']) if (c[key] != null) return o ? n(c[key], `${o}#runs[id=${run.id}].cost.${key}`, usd) : d(usd(c[key]), `${run.id}.cost.${key}`);
    if (c.estimatedUsd != null) return d(`${usd(c.estimatedUsd)} at API rates`, `${run.id}.cost.estimatedUsd (API-rate estimate merged by app.js)`);
    return DASH;
  }

  /* ---------- Leaderboard, full: one row per configuration from the merged runs app.js already built ---------- */
  const DECISION = /jev|solar-decide|liquid\/d1|liquid-d1|tev1|clef|luna-decisions|pplx-decider|perplexity-decider|openjev|semif|laya|anyjev|kev|alex/;
  const type = run => { const s = `${run.model} ${run.id}`.toLowerCase(); return /rules/.test(s) ? 'Rules' : DECISION.test(s) ? 'Decision' : 'General'; };
  // ponytail: configuration = saved stage name minus its pass and prompt suffix, the same cut s07_repeatability.py makes.
  const base = run => run.sourceStage ? run.sourceStage.split('/')[0]
    : run.id.replace(/--pass\d-p\d$/, '').replace(/-fresh\d-p\d$/, '').replace(/--p\d$/, '');
  const passIndex = run => { const m = /(\d)$/.exec(run.repeatPass || ''); return m ? Number(m[1]) : 1; };
  const effort = e => e == null || /^not.applicable$|^na$|^none$/i.test(e) ? '–' : e;
  const shortModel = m => String(m).replace(/^[\w.-]+\//, '');

  function configurations(runs) {
    const map = new Map();
    let placed = 0, doubled = 0;
    for (const run of runs) {
      if (run.records !== 60 && run.records !== undefined) continue;
      const key = base(run);
      if (!map.has(key)) map.set(key, {key, model: run.model, type: type(run), route: run.surface || run.provider || '', effort: effort(run.effort), cells: {}});
      const cfg = map.get(key), cell = `${run.condition}.${passIndex(run)}`;
      if (cfg.cells[cell]) { doubled++; continue; }
      cfg.cells[cell] = run; placed++;
    }
    return {rows: [...map.values()], placed, doubled};
  }
  const score = run => run?.metrics?.all_four ?? -1;

  async function leaderboardFull(el, snapshot) {
    const {rows, placed} = configurations(snapshot.runs);
    // The catalog files Jev's nine prompt passes under TypeSafe with an estimate; they ran on OpenRouter native Choice
    // and carry a known charge (jev-native-prompt-findings.json). The direct TypeSafe run has no bill.
    const jev = await feed('jev-native-prompt-findings.json');
    for (const c of rows) {
      if (/typesafe-jev113-native-prompts/.test(c.key)) {
        c.route = 'OpenRouter native Choice';
        c.costCell = n(jev.passes.P0.fresh1.knownCostUsd, 'jev-native-prompt-findings.json#passes.P0.fresh1.knownCostUsd', usd);
      } else if (/^typesafe-jev113-v2/.test(c.key)) {
        c.route = 'TypeSafe direct API';
        c.costCell = '<span class="bm-none">no bill</span>';
      }
    }
    const total = rows.length;
    el.innerHTML = `<div class="bm-controls">
      <label>Model type<select data-f="type"><option value="">All</option><option>Decision</option><option>General</option></select></label>
      <label>Find a model<input type="search" data-f="q" autocomplete="off"></label>
      <label>Sort by<select data-f="sort"><option value="P0.1">P0 pass 1</option><option value="P1.1">P1 pass 1</option><option value="P2.1">P2 pass 1</option><option value="model">Model name</option></select></label>
      <p class="bm-count" role="status"></p></div><div class="bm-body"></div>`;
    let all = false;
    const pick = sel => el.querySelector(`[data-f="${sel}"]`);
    const passCells = cfg => ['P0', 'P1', 'P2'].map(p => [1, 2, 3].map(i => {
      const run = cfg.cells[`${p}.${i}`];
      if (!run) return `<td class="bm-num bm-pass">${DASH}</td>`;
      const stop = run.complete === false ? '<sup class="bm-stop">i</sup>' : '';
      return `<td class="bm-num bm-pass${i === 1 ? ' bm-first' : ''}">${metric(run, 'all_four')}${stop}</td>`;
    }).join('')).join('');
    const draw = () => {
      const t = pick('type').value, q = pick('q').value.trim().toLowerCase(), s = pick('sort').value;
      let list = rows.filter(c => (!t || c.type === t) && (!q || `${c.model} ${c.key} ${c.route}`.toLowerCase().includes(q)));
      list.sort(s === 'model' ? (a, b) => a.model.localeCompare(b.model) : (a, b) => score(b.cells[s]) - score(a.cells[s]) || a.model.localeCompare(b.model));
      const shown = all ? list : list.slice(0, 40);
      el.querySelector('.bm-count').textContent = `${shown.length} of ${list.length} configurations`;
      const body = shown.map(c => {
        const first = c.cells['P0.1'];
        return `<tr><th scope="row"><span class="bm-model">${esc(shortModel(c.model))}</span><span class="bm-id">${esc(c.key)}</span></th>
          <td>${c.type}</td><td>${esc(c.route)}</td><td>${esc(c.effort)}</td>${passCells(c)}
          ${FIELDS.map(f => `<td class="bm-num">${first ? metric(first, f) : DASH}</td>`).join('')}<td class="bm-num">${c.costCell || (first ? cost(first) : DASH)}</td></tr>`;
      }).join('');
      el.querySelector('.bm-body').innerHTML = wrap(`<table class="bm-table bm-wide"><thead>
        <tr><th rowspan="2" scope="col">Model and configuration</th><th rowspan="2" scope="col">Type</th><th rowspan="2" scope="col">Route</th><th rowspan="2" scope="col">Effort</th>
        <th colspan="3" scope="colgroup">P0 base task</th><th colspan="3" scope="colgroup">P1 classifier instructions</th><th colspan="3" scope="colgroup">P2 decision rules</th>
        <th colspan="4" scope="colgroup">P0 pass 1, each decision</th><th rowspan="2" scope="col">Cost of P0 pass 1</th></tr>
        <tr>${'<th scope="col">1</th><th scope="col">2</th><th scope="col">3</th>'.repeat(3)}${FIELD_HEAD.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead>
        <tbody>${body}</tbody></table>`,
        `All-four matches out of 60 for each prompt and pass. A dash means that pass has no saved score, and a small i marks a pass that was interrupted. Cost is the provider charge for one pass of 60 reviews; Claude and Codex ran on subscriptions, so their cost is the API-rate equivalent. ${total} configurations from ${placed} saved run-passes.`)
        + (!all && list.length > 40 ? `<button type="button" class="bm-more">Show all ${list.length} configurations</button>` : '');
      el.querySelector('.bm-more')?.addEventListener('click', () => { all = true; draw(); });
    };
    el.addEventListener('input', draw);
    draw();
    busy(el, false);
  }

  /* ---------- Leaderboard, compact (Read): small feeds only ---------- */
  const SEVEN = [['solar-decide', 'Solar Decide'], ['clef-openrouter', 'Clef'], ['perplexity-decider', 'Perplexity Decider'], ['luna-decisions-openrouter', 'Luna Decisions'],
    ['clef-flash-openrouter', 'Clef Flash'], ['tev1-4b', 'Tev 1 4B'], ['liquid-d1', 'Liquid d1']];
  async function leaderboardCompact(el) {
    const [sup, jev, roster, sonnet, fin, price] = await Promise.all(['supplemental-decision-runs-v1.json', 'jev-native-prompt-findings.json',
      'claude-roster-repeats.json', 'sonnet55-fresh-matched3.json', 'findings.json', 'subscription-price-estimates.json'].map(feed));
    const S = 'supplemental-decision-runs-v1.json', J = 'jev-native-prompt-findings.json';
    const supRun = id => sup.runs.find(r => r.id === id);
    const grid = f => ['P0', 'P1', 'P2'].map(p => `<td class="bm-num bm-trio">${[1, 2, 3].map(i => f(p, i)).join(' ')}</td>`).join('');
    const rows = SEVEN.map(([k, name]) => {
      const first = supRun(`${k}-native-fresh1-p0`);
      return `<tr><th scope="row">${name}</th><td>Decision</td>${grid((p, i) => { const id = `${k}-native-fresh${i}-${p.toLowerCase()}`, r = supRun(id);
        return r ? n(r.metrics.all_four, `${S}#runs[id=${id}].metrics.all_four`) + (r.complete === false ? '<sup class="bm-stop">i</sup>' : '') : DASH; })}
        <td class="bm-num">${n(first?.cost?.knownUsd, `${S}#runs[id=${k}-native-fresh1-p0].cost.knownUsd`, usd)}</td></tr>`;
    });
    rows.push(`<tr><th scope="row">Jev 1.13</th><td>Decision</td>${grid((p, i) => { const pass = jev.passes[p]?.[`fresh${i}`];
      return pass?.status === 'stopped' ? '<span class="bm-stopped">stopped</span>' : n(pass?.score?.allFour, `${J}#passes.${p}.fresh${i}.score.allFour`); })}
      <td class="bm-num">${n(jev.passes.P0.fresh1.knownCostUsd, `${J}#passes.P0.fresh1.knownCostUsd`, usd)}</td></tr>`);
    const opusPath = 'claude-roster-repeats.json#series[configuration=opus55-high-batch10].threePassSummary';
    const opus = roster.series.find(x => x.configuration === 'opus55-high-batch10');
    rows.push(`<tr><th scope="row">Opus 5.5, high effort</th><td>General</td>${grid((p, i) => n(opus?.threePassSummary?.[p]?.allFour?.values?.[i - 1], `${opusPath}.${p}.allFour.values[${i - 1}]`))}
      <td class="bm-num">${n(price.runs['opus55-high-batch10']?.estimateUsd, 'subscription-price-estimates.json#runs.opus55-high-batch10.estimateUsd', usd)}<sup class="bm-api">a</sup></td></tr>`);
    rows.push(`<tr><th scope="row">Sonnet 5.5, xhigh effort</th><td>General</td>${grid((p, i) => n(sonnet.threePassSummary.xhigh[p]?.allFour?.values?.[i - 1], `sonnet55-fresh-matched3.json#threePassSummary.xhigh.${p}.allFour.values[${i - 1}]`))}
      <td class="bm-num">${n(sonnet.cells.xhigh?.pass1?.P0?.development?.usage?.calculatedApiEquivalentUsd, 'sonnet55-fresh-matched3.json#cells.xhigh.pass1.P0.development.usage.calculatedApiEquivalentUsd', usd)}<sup class="bm-api">a</sup></td></tr>`);
    for (const [id, name] of [['openrouter-paid-gemma4-26b-a4b-on', 'Gemma 4 26B, thinking on'], ['openrouter-qwen27-low-darkbloom-fp4', 'Qwen3.8 27B, low effort']]) {
      const row = fin.charts.costAgreement.rows.find(r => r.id === id), path = `findings.json#charts.costAgreement.rows[id=${id}]`;
      rows.push(`<tr><th scope="row">${name}</th><td>General</td><td class="bm-num bm-trio">${n(row?.correct, `${path}.correct`)} ${DASH} ${DASH}</td><td class="bm-num bm-trio">${DASH}</td><td class="bm-num bm-trio">${DASH}</td>
        <td class="bm-num">${n(row?.actualUsd, `${path}.actualUsd`, usd)}</td></tr>`);
    }
    el.innerHTML = wrap(`<table class="bm-table"><thead><tr><th scope="col">Model</th><th scope="col">Type</th><th scope="col">P0 passes</th><th scope="col">P1 passes</th><th scope="col">P2 passes</th><th scope="col">Cost of one pass</th></tr></thead><tbody>${rows.join('')}</tbody></table>`,
      'Each cell is all-four matches out of 60, passes 1, 2 and 3 left to right. Jev ran on OpenRouter native Choice; its second P2 pass stopped early. Gemma and Qwen show their first P0 pass here; their repeats are in the full table on Explore. Cost is the provider charge for one pass of 60 reviews, except the two Claude rows marked a, which ran on a subscription and are priced at API rates.');
    busy(el, false);
  }

  /* ---------- Hard reviews ---------- */
  const HARD = ['DEV-029', 'DEV-030', 'DEV-006', 'DEV-013', 'DEV-027', 'DEV-056', 'DEV-059'];
  async function hardReviews(el, mode) {
    const [dr, fin, cc] = await Promise.all(['disputed-reviews-v1.json', 'findings.json', 'cross-category-v1.json'].map(feed));
    const D = 'disputed-reviews-v1.json';
    const disputed = new Set(['DEV-006', 'DEV-013', 'DEV-030']);
    const jevMiss = new Map(fin.charts.jev.cases.map(c => [c.id, c]));
    let reviews = dr.reviews;
    if (mode === 'seven') reviews = HARD.map(id => reviews.find(r => r.id === id)).filter(Boolean);
    else reviews = [...reviews].sort((a, b) => b.models_with_any_mismatch - a.models_with_any_mismatch || a.id.localeCompare(b.id));
    const models = dr.models;
    const head = `<thead><tr><th scope="col">Question</th><th scope="col">Reference</th><th scope="col">Jev</th>${models.map(m => `<th scope="col">${esc(m.display_name.replace(/ V1 27B$/, ''))}</th>`).join('')}</tr></thead>`;
    const bodies = reviews.map(r => {
      const notes = [];
      if (disputed.has(r.id)) notes.push('Disputed label.');
      if (r.off_topic) notes.push('Off-topic.');
      if (jevMiss.has(r.id)) notes.push('Jev missed it.');
      let general = '';
      const sum = cc.caseSummaries.find(c => c.id === r.id)?.byStratum?.['historical-first-P0'];
      if (r.id === 'DEV-029' && sum) general = ` ${n(sum.allFourMatches, `cross-category-v1.json#caseSummaries[id=DEV-029].byStratum["historical-first-P0"].allFourMatches`)} of ${n(sum.validOutputs, `cross-category-v1.json#caseSummaries[id=DEV-029].byStratum["historical-first-P0"].validOutputs`)} general configurations matched it.`;
      const jev = jevMiss.get(r.id);
      const rows = FIELDS.map((f, i) => {
        const ref = r.reference[f];
        const jv = jev ? jev.prediction[f] : ref;
        const jcell = jev ? `<span class="bm-word" data-text-source="findings.json#charts.jev.cases[id=${r.id}].prediction.${f}">${word(jv)}</span>`
          : `<span class="bm-word" data-derived="${r.id} not in findings.json#charts.jev.disagreementCaseIds, so Jev matched the reference">${word(jv)}</span>`;
        return `<tr><th scope="row">${QUESTION[i]}</th><td class="bm-ref">${word(ref)}</td><td${jv !== ref ? ' class="bm-diff"' : ''}>${jcell}</td>${models.map(m => {
          const a = r.answers.find(x => x.model_id === m.id)?.prediction?.[f];
          return `<td${a !== ref ? ' class="bm-diff"' : ''}>${word(a)}</td>`; }).join('')}</tr>`;
      }).join('');
      return `<tbody><tr class="bm-review"><th colspan="${models.length + 3}" scope="rowgroup"><span class="bm-id">${r.id}</span>
        <span class="bm-split">Differs on ${n(r.models_with_any_mismatch, `${D}#reviews[id=${r.id}].models_with_any_mismatch`)} of ${n(r.eligible_model_count, `${D}#reviews[id=${r.id}].eligible_model_count`)} decision models.</span>
        ${notes.length ? `<span class="bm-tagline">${notes.join(' ')}</span>` : ''}<q class="bm-quote">${esc(r.feedback)}</q>${general ? `<span class="bm-tagline">${general}</span>` : ''}</th></tr>${rows}</tbody>`;
    }).join('');
    el.innerHTML = wrap(`<table class="bm-table bm-hard">${head}${bodies}</table>`,
      'Orange marks an answer that differs from the reference. The seven decision models are on their first pass with the base prompt; Jev is its direct P0 run.');
    busy(el, false);
  }

  /* ---------- Per-decision matrix (Explore, from the merged runs) ---------- */
  const MATRIX = [...SEVEN.map(([k, name]) => [name, p => `${k}-native-fresh1-${p}`]),
    ['Jev 1.13', p => `extended-typesafe-jev113-native-prompts-fresh1-${p}`], ['Opus 5.5, high', p => p === 'p0' ? 'opus55-high-batch10' : `opus55-high-batch10--${p}`],
    ['Sonnet 5.5, xhigh', p => `sonnet55-xhigh-fresh-matched3-batch10-v2--pass1-${p}`], ['Gemma 4 26B, thinking on', p => `extended-openrouter-paid-gemma4-26b-a4b-on-fresh1-${p}`],
    ['Qwen3.8 27B, low', p => p === 'p0' ? 'openrouter-qwen27-low-darkbloom-fp4' : `openrouter-qwen27-low-darkbloom-fp4--${p}`]];
  async function decisionMatrix(el, snapshot) {
    const di = await feed('deep-insights-v1.json');
    const byId = new Map(snapshot.runs.map(r => [r.id, r]));
    el.innerHTML = `<div class="bm-controls"><label>Prompt<select data-f="p"><option value="p0">P0 base task</option><option value="p1">P1 classifier instructions</option><option value="p2">P2 decision rules</option></select></label></div><div class="bm-body"></div><div class="bm-gap"></div>`;
    const draw = () => {
      const p = el.querySelector('[data-f="p"]').value;
      const rows = MATRIX.map(([name, id]) => { const run = byId.get(id(p));
        return `<tr><th scope="row">${name}</th>${['all_four', ...FIELDS].map(f => `<td class="bm-num">${run ? metric(run, f) : DASH}</td>`).join('')}</tr>`; }).join('');
      el.querySelector('.bm-body').innerHTML = wrap(`<table class="bm-table"><thead><tr><th scope="col">Model</th><th scope="col">All four</th>${FIELD_HEAD.map(h => `<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`,
        'Matches out of 60 on the first pass. A dash means that model has no first pass at this prompt.');
    };
    el.addEventListener('change', draw);
    draw();
    const ic = di.insufficient_collapse?.fields || {};
    const gap = Object.keys(ic).map(f => ['decision', 'general'].map(g => ic[f][g] ? `<tr><th scope="row">${FIELD_HEAD[FIELDS.indexOf(f)] || f}, ${g} models</th>
      <td class="bm-num">${n(ic[f][g].definite, `deep-insights-v1.json#insufficient_collapse.fields.${f}.${g}.definite`)}</td><td class="bm-num">${n(ic[f][g].valid_answers, `deep-insights-v1.json#insufficient_collapse.fields.${f}.${g}.valid_answers`)}</td></tr>` : '').join('')).join('');
    if (gap) el.querySelector('.bm-gap').innerHTML = `<h3 class="bm-h3">When the reference says can't tell</h3>` + wrap(`<table class="bm-table"><thead><tr><th scope="col">Decision and model group</th><th scope="col">Gave a definite answer</th><th scope="col">Cells where the reference says can't tell</th></tr></thead><tbody>${gap}</tbody></table>`,
      'Counted over every saved pass with a valid answer. Decision models rarely say they cannot tell, even when the review gives them nothing to go on.');
    busy(el, false);
  }

  /* ---------- Stability and confidence (Explore) ---------- */
  async function stability(el) {
    const [di, pl, jc] = await Promise.all(['deep-insights-v1.json', 'deck/data/prompt-levels.json', 'jev-confidence-findings.json'].map(feed));
    const DI = 'deep-insights-v1.json', de = di.determinism;
    const t = pl.tally_39_setups;
    const moves = ['P0_to_P1', 'P0_to_P2', 'P1_to_P2'].map(k => `<tr><th scope="row">${k.replace(/_to_/, ' to ')}</th>${['better', 'same', 'worse'].map(x => `<td class="bm-num">${n(t[k][x], `deck/data/prompt-levels.json#tally_39_setups.${k}.${x}`)}</td>`).join('')}</tr>`).join('');
    const cal = m => di.calibration.models.find(x => x.model === m);
    const calRow = (m, name) => `<tr><th scope="row">${name}</th><td class="bm-num">${n(cal(m)?.ece_confidence, `${DI}#calibration.models[model=${m}].ece_confidence`)}</td><td class="bm-num">${n(cal(m)?.field_answers, `${DI}#calibration.models[model=${m}].field_answers`)}</td></tr>`;
    const cut = FIELDS.map((f, i) => { const th = jc.conditions.P0.fields[f]?.thresholds?.['0.9'], p = `jev-confidence-findings.json#conditions.P0.fields.${f}.thresholds["0.9"]`;
      return `<tr><th scope="row">${FIELD_HEAD[i]}</th><td class="bm-num">${n(th?.retained, `${p}.retained`)}</td><td class="bm-num">${n(th?.retainedWrong, `${p}.retainedWrong`)}</td></tr>`; }).join('');
    const wrong = di.calibration.jev_confident_wrong.answers.map(a => `<li>${n(a.confidence, `${DI}#calibration.jev_confident_wrong.answers[id=${a.id}].confidence`)} sure on ${esc(a.id)} ${FIELD_HEAD[FIELDS.indexOf(a.field)].toLowerCase()}: it said ${word(a.prediction)}, the reference says ${word(a.reference)}.</li>`).join('');
    el.innerHTML = `<div class="bm-two"><div><h3 class="bm-h3">Same prompt, three passes</h3>
      <div class="bm-stats"><p>${n(de.zero_change.decision, `${DI}#determinism.zero_change.decision`)}<small>of ${n(de.configurations.decision, `${DI}#determinism.configurations.decision`)}</small><span>decision-model configurations changed no answer</span></p>
      <p>${n(de.zero_change.general, `${DI}#determinism.zero_change.general`)}<small>of ${n(de.configurations.general, `${DI}#determinism.configurations.general`)}</small><span>general-model configurations changed no answer</span></p></div>
      <h3 class="bm-h3">Longer prompts across ${d('39', 'sum of better, same and worse in deck/data/prompt-levels.json#tally_39_setups.P1_to_P2')} setups</h3>
      ${wrap(`<table class="bm-table"><thead><tr><th scope="col">Move</th><th scope="col">Better</th><th scope="col">Same</th><th scope="col">Worse</th></tr></thead><tbody>${moves}</tbody></table>`, 'All-four matches on the first pass, setup by setup.')}</div>
      <div><h3 class="bm-h3">Confidence</h3>${wrap(`<table class="bm-table"><thead><tr><th scope="col">Model</th><th scope="col">Expected calibration error</th><th scope="col">Answers pooled</th></tr></thead><tbody>${calRow('jev', 'Jev')}${calRow('clef-flash', 'Clef Flash')}</tbody></table>`, 'Lower is closer: 0 means stated confidence equals the share of answers that matched.')}
      <h3 class="bm-h3">Keep only Jev answers at 0.9 confidence or higher</h3>${wrap(`<table class="bm-table"><thead><tr><th scope="col">Decision</th><th scope="col">Kept, of 60</th><th scope="col">Kept and wrong</th></tr></thead><tbody>${cut}</tbody></table>`, '')}
      <ul class="bm-list">${wrong}</ul></div></div>`;
    busy(el, false);
  }

  /* ---------- Cost ledger (Explore) ---------- */
  const LEDGER = [...SEVEN.map(([k, name]) => [name, `${k}-native-fresh1-p0`]), ['Gemma 4 26B, thinking on', 'openrouter-paid-gemma4-26b-a4b-on'], ['Qwen3.8 27B, low', 'openrouter-qwen27-low-darkbloom-fp4'],
    ['Gemini 3.1 Pro, low', 'gemini31-pro-preview-low-p0-openrouter-v3'], ['Gemini 3.1 Pro, high', 'gemini31-pro-preview-high-p0-openrouter-v3'], ['DeepSeek V4.1 Flash, off', 'openrouter-paid-deepseek-v41-flash-off']];
  async function costLedger(el, snapshot) {
    const [jev, fin, price, di] = await Promise.all(['jev-native-prompt-findings.json', 'findings.json', 'subscription-price-estimates.json', 'deep-insights-v1.json'].map(feed));
    const jevUsd = Number(jev.passes.P0.fresh1.knownCostUsd);
    const times = v => d(`${(Number(v) / jevUsd).toFixed(1)}x`, `${v} / jev-native-prompt-findings.json#passes.P0.fresh1.knownCostUsd`);
    const byId = new Map(snapshot.runs.map(r => [r.id, r]));
    const rows = [`<tr><th scope="row">Jev 1.13</th>${'<td class="bm-num">' + n(jev.passes.P0.fresh1.score.allFour, 'jev-native-prompt-findings.json#passes.P0.fresh1.score.allFour') + '</td>'}<td class="bm-num">${n(jev.passes.P0.fresh1.knownCostUsd, 'jev-native-prompt-findings.json#passes.P0.fresh1.knownCostUsd', usd)}</td><td class="bm-num">1.0x</td><td>Provider charge</td></tr>`];
    for (const [name, id] of LEDGER) {
      const run = byId.get(id), row = fin.charts.costAgreement.rows.find(r => r.id === id);
      const fp = `findings.json#charts.costAgreement.rows[id=${id}]`;
      const all = run ? metric(run, 'all_four') : n(row?.correct, `${fp}.correct`);
      const v = run?.cost?.knownUsd ?? row?.actualUsd;
      const c = run?.cost?.knownUsd != null ? cost(run) : n(row?.actualUsd, `${fp}.actualUsd`, usd);
      rows.push(`<tr><th scope="row">${name}</th><td class="bm-num">${all}</td><td class="bm-num">${c}</td><td class="bm-num">${v != null ? times(v) : DASH}</td><td>Provider charge</td></tr>`);
    }
    const opus = price.runs['opus55-high-batch10']?.estimateUsd;
    rows.push(`<tr><th scope="row">Opus 5.5, high</th><td class="bm-num">${n(fin.charts.jev.comparators?.[2]?.correct, 'findings.json#charts.jev.comparators[2].correct')}</td><td class="bm-num">${n(opus, 'subscription-price-estimates.json#runs.opus55-high-batch10.estimateUsd', usd)}</td><td class="bm-num">${opus ? times(opus) : DASH}</td><td>API-rate equivalent</td></tr>`);
    const AR = 'deep-insights-v1.json#agreement_rule';
    const pairs = [['solar_perplexity', 'Solar Decide + Perplexity Decider'], ['qwen_gemma', 'Qwen3.8 27B low + Gemma 4 26B on']].map(([k, name]) => {
      const p = di.agreement_rule[k];
      return `<tr><th scope="row">${name}</th><td class="bm-num">${n(p.accepted, `${AR}.${k}.accepted`)}</td><td class="bm-num">${n(p.accepted_errors, `${AR}.${k}.accepted_errors`)}</td><td class="bm-num">${n(p.deferred, `${AR}.${k}.deferred`)}</td><td class="bm-num">${n(p.two_run_charge_usd, `${AR}.${k}.two_run_charge_usd`, usd)}</td></tr>`;
    }).join('');
    el.innerHTML = wrap(`<table class="bm-table"><thead><tr><th scope="col">Model</th><th scope="col">All four, of 60</th><th scope="col">Cost of one pass</th><th scope="col">Jev passes for the same money</th><th scope="col">Basis</th></tr></thead><tbody>${rows.join('')}</tbody></table>`,
      'First P0 pass of 60 reviews for each model. Provider charge is what OpenRouter or the vendor billed; Opus ran on a Claude subscription and is priced at API rates.')
      + `<h3 class="bm-h3">Two models under agree or defer</h3>` + wrap(`<table class="bm-table"><thead><tr><th scope="col">Pair</th><th scope="col">Accepted</th><th scope="col">Accepted and wrong</th><th scope="col">Sent to a person</th><th scope="col">Cost of both passes</th></tr></thead><tbody>${pairs}</tbody></table>`,
      'Both models answer all 60 reviews; a review is accepted only when their four answers agree.');
    busy(el, false);
  }

  /* ---------- Wiring ---------- */
  let snapshot = null;
  const waiting = [];
  const needsRuns = {leaderboard: m => m === 'full', 'decision-matrix': () => true, 'cost-ledger': () => true};
  const RENDER = {
    leaderboard: (el, m) => m === 'full' ? leaderboardFull(el, snapshot) : leaderboardCompact(el),
    'hard-reviews': (el, m) => hardReviews(el, m), 'decision-matrix': el => decisionMatrix(el, snapshot),
    stability: el => stability(el), 'cost-ledger': el => costLedger(el, snapshot),
  };
  const run = el => Promise.resolve().then(() => RENDER[el.dataset.bm]?.(el, el.dataset.bmMode)).catch(() => fail(el));
  for (const el of mounts) {
    if (!RENDER[el.dataset.bm]) continue;
    busy(el, true);
    if (needsRuns[el.dataset.bm]?.(el.dataset.bmMode)) waiting.push(el); else run(el);
  }
  if (waiting.length) {
    addEventListener('benchmark:saved-runs-ready', event => { snapshot = event.detail; waiting.splice(0).forEach(run); }, {once: true});
    setTimeout(() => { if (!snapshot) waiting.splice(0).forEach(fail); }, 20000);
  }
})();
