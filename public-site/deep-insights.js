/* Recomputed findings panel. Every number is read from a feed by path and carries data-source="<feed>#<path>".
   Mounts are looked up across the document and are all optional: Read carries the findings, Method the corrections. */
(() => {
  'use strict';
  const FEED = 'deep-insights-v1.json';
  const NATIVE = 'native-agreement-policy-v1.json';
  const mount = name => document.querySelector(`[data-di-mount="${name}"]`);
  if (!document.querySelector('[data-di-mount]')) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const get = (data, path) => path.replace(/\]/g, '').split(/[.[]/).reduce((node, key) =>
    node == null ? undefined : node[Array.isArray(node) ? Number(key) : key], data);
  const FIELD = {sentiment: 'sentiment', follow_up_needed: 'follow-up', serious_concern_reported: 'serious concern', testimonial_potential: 'testimonial'};
  const MAIN = ['insufficient_collapse', 'frontier_convergence', 'agreement_rule', 'determinism', 'calibration'];
  const MORE = ['prompt_direction', 'size_thinking', 'cost_frontier'];
  // Hedge words the feed carries inside titles and corrections. \u0000n\u0000 stands for the n-th bound number.
  const STRIP = [
    [/ that share the same \u0000\d+\u0000 texts; descriptive-only\)/g, ')'],
    [/[,;] descriptive-only\)/g, ')'],
  ];

  function fmt(value, format = 'count') {
    if (value === null || value === undefined || value === '') return 'not recorded';
    if (format === 'text') return String(value);
    if (format === 'date') return new Date(`${value}T00:00:00Z`).toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'});
    const n = Number(value);
    if (format === 'pct') return `${(n * 100).toFixed(1)}%`;
    if (format === 'ece') return n.toFixed(3);
    if (format === 'conf') return n.toFixed(2);
    if (format === 'signed') return `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
    if (format.startsWith('usd')) {
      const places = format.split(':')[1];
      return `$${n.toFixed(places ? Number(places) : n < 0.01 ? 6 : n < 1 ? 5 : 4)}`;
    }
    return n.toLocaleString('en-US');
  }

  // One bound number: the value attribute holds the raw feed value so a number audit can compare it.
  function num(data, path, format = 'count', feed = FEED) {
    const value = get(data, path);
    return `<data class="di-num${format === 'text' ? ' di-text' : ''}" value="${esc(value ?? '')}" data-source="${feed}#${esc(path)}">${esc(fmt(value, format))}</data>`;
  }

  function prose(data, parts) {
    const bound = parts.filter(part => typeof part !== 'string');
    let template = parts.map(part => typeof part === 'string' ? part : `\u0000${bound.indexOf(part)}\u0000`).join('');
    for (const [pattern, to] of STRIP) template = template.replace(pattern, to);
    return template.split(/\u0000(\d+)\u0000/).map((text, i) =>
      i % 2 ? num(data, bound[Number(text)].path, bound[Number(text)].format) : esc(text)).join('');
  }
  const idList = ids => ids.length ? esc(ids.join(', ')) : 'none';

  function validate(data) {
    if (data?.schema !== 'deep-insights-v1' || data.denominator !== 60 || typeof data.source_sha256 !== 'object' ||
        ![...MAIN, ...MORE].every(id => Array.isArray(data[id]?.key_numbers)) || !Array.isArray(data.corrections?.items)) {
      throw Error('Deep insights feed header changed');
    }
    for (const id of [...MAIN, ...MORE]) {
      for (const item of data[id].key_numbers) {
        if (get(data, item.value) === undefined || (item.of && get(data, item.of) === undefined)) throw Error(`Unbound number in ${id}`);
      }
    }
    return data;
  }

  function card(data, id, extra = '') {
    const block = data[id];
    const numbers = block.key_numbers.map(k => `<li><span class="di-kn-label">${prose(data, k.label)}</span>
      <span class="di-kn-value">${num(data, k.value, k.format)}${k.of ? ` <span class="di-of">of ${num(data, k.of)}</span>` : ''}${k.share ? ` <span class="di-share">(${num(data, k.share, 'pct')})</span>` : ''}</span></li>`).join('');
    return `<article class="di-card" aria-labelledby="di-${id}-title">
      <h3 id="di-${id}-title">${prose(data, block.title)}</h3>
      <ul class="di-kn">${numbers}</ul>
      <p class="di-implication">${esc(block.implication)}</p>
      ${extra}
    </article>`;
  }

  function stableWrong(data) {
    const rows = data.determinism.stable_but_wrong.map((row, i) => {
      const p = `determinism.stable_but_wrong[${i}]`;
      return `<tr><th scope="row">${esc(row.family)} <span class="di-dim">${esc(row.configuration)}</span></th><td>${esc(row.condition)}</td><td>${esc(row.category)}</td>
        <td>${num(data, `${p}.all_four`)}</td><td>${num(data, `${p}.fixed_wrong`)}</td><td>${row.fixed_wrong <= 8 ? idList(row.fixed_wrong_ids) : `<span class="di-dim">${esc(row.fixed_wrong)} reviews</span>`}</td></tr>`;
    }).join('');
    return `<details class="di-details"><summary>All ${num(data, 'determinism.stable_but_wrong_count')} configurations that changed no answer in three passes and still missed reviews</summary>
      <div class="di-table-wrap" tabindex="0" role="region" aria-label="Stable but wrong configurations"><table><caption>Same answers in all three passes; all-four matches out of ${num(data, 'denominator')}.</caption>
      <thead><tr><th scope="col">Configuration</th><th scope="col">Prompt</th><th scope="col">Category</th><th scope="col">All four</th><th scope="col">Fixed misses</th><th scope="col">Missed reviews</th></tr></thead>
      <tbody>${rows}</tbody></table></div></details>`;
  }

  function confidentWrong(data) {
    const rows = data.calibration.jev_confident_wrong.answers.map((a, i) => {
      const p = `calibration.jev_confident_wrong.answers[${i}]`;
      return `<li>${esc(a.id)}, ${esc(FIELD[a.field])}: Jev answered "${esc(a.prediction)}" at confidence ${num(data, `${p}.confidence`, 'conf')}; the reference says "${esc(a.reference.replace(/_/g, ' '))}".</li>`;
    }).join('');
    return `<p class="di-sub">Jev's first-pass answers that were wrong at confidence ${num(data, 'calibration.jev_confident_wrong.threshold', 'conf')} or higher:</p><ul class="di-list">${rows}</ul>`;
  }

  function routingTable(data, index) {
    const row = data.agreement_rule.native_routing[index];
    const p = `agreement_rule.native_routing[${index}]`;
    const full = row.left === 'solar-decide-native-fresh1-p0' && row.right === 'perplexity-decider-native-fresh1-p0';
    const ids = step => full ? `<td>${idList(data.agreement_rule.full_policy_routing.rows[step].ids)}</td>` : '';
    return `<div class="di-table-wrap" tabindex="0" role="region" aria-label="Full policy routing"><table class="di-routing"><caption>Where the ${num(data, 'denominator')} reviews go under the full policy: a disagreement is deferred, a serious concern is escalated, and a can't-tell answer goes back for clarification.</caption>
      <thead><tr><th scope="col">Route</th><th scope="col">Reviews</th>${full ? '<th scope="col">Review IDs</th>' : ''}</tr></thead><tbody>
      <tr><th scope="row">Deferred: the two answers differ</th><td>${num(data, `${p}.deferred`)}</td>${ids(0)}</tr>
      <tr><th scope="row">Accepted, escalated for serious concern</th><td>${num(data, `${p}.escalated_beyond_deferral`)}</td>${ids(1)}</tr>
      <tr><th scope="row">Accepted, sent for clarification</th><td>${num(data, `${p}.clarification_beyond_deferral`)}</td>${ids(2)}</tr>
      <tr class="di-total"><th scope="row">Reaches a person</th><td>${num(data, `${p}.reaches_person`)}</td>${ids(3)}</tr>
      <tr><th scope="row">Accepted with no routing</th><td>${num(data, `${p}.accepted_no_routing`)}</td>${ids(4)}</tr></tbody></table></div>`;
  }

  function pairDetail(data, native, choice) {
    const [kind, index] = choice.split(':');
    const i = Number(index);
    let name, rows, note, deferredIds, errorIds, routing = '';
    if (kind === 'native') {
      const pair = native.pairs[i];
      const names = new Map(native.components.map(c => [c.id, c.display_name]));
      const p = `pairs[${i}]`;
      name = `${names.get(pair.left)} + ${names.get(pair.right)}`;
      rows = [num(native, `${p}.accepted_count`, 'count', NATIVE), num(native, `${p}.accepted_all_four_error_count`, 'count', NATIVE),
        num(native, `${p}.deferred_count`, 'count', NATIVE), num(native, `${p}.known_two_run_development_cost_usd`, 'usd', NATIVE)];
      deferredIds = pair.deferred_ids;
      errorIds = pair.accepted_all_four_error_ids;
      note = 'Both are decision models on their first pass with the base prompt. The charge is the provider charge for both runs.';
      const r = data.agreement_rule.native_routing.findIndex(x => x.left === pair.left && x.right === pair.right);
      if (r >= 0) routing = routingTable(data, r);
    } else {
      const pair = data.agreement_rule.explorer_pairs[i];
      const p = `agreement_rule.explorer_pairs[${i}]`;
      name = `${pair.run_a.label} + ${pair.run_b.label}`;
      rows = [num(data, `${p}.accepted`), num(data, `${p}.accepted_errors`), num(data, `${p}.deferred`), num(data, `${p}.two_run_charge_usd`, 'usd')];
      deferredIds = pair.deferred_ids;
      errorIds = pair.accepted_error_ids;
      note = `Both are general models on the base prompt. ${pair.two_run_charge_usd == null ? 'At least one of the two runs has no recorded charge.' : 'The charge is the provider charge for both runs.'}`;
    }
    return `<div class="di-table-wrap" tabindex="0" role="region" aria-label="Selected pair outcome"><table class="di-pair"><caption>${esc(name)}</caption><tbody>
      <tr><th scope="row">Accepted, out of ${num(data, 'denominator')}</th><td>${rows[0]}</td></tr>
      <tr><th scope="row">Accepted, but wrong on at least one decision</th><td>${rows[1]}</td></tr>
      <tr><th scope="row">Deferred to a person</th><td>${rows[2]}</td></tr>
      <tr><th scope="row">Two-run charge</th><td>${rows[3]}</td></tr></tbody></table></div>
      <p class="di-sub">${esc(note)}</p>
      <p class="di-ids"><strong>Deferred:</strong> ${idList(deferredIds)}</p>
      <p class="di-ids"><strong>Accepted with an error:</strong> ${idList(errorIds)}</p>${routing}`;
  }

  function explorer(data, native) {
    const options = [];
    if (native) {
      const names = new Map(native.components.map(c => [c.id, c.display_name]));
      options.push(`<optgroup label="Decision-model pairs, first pass">${native.pairs.map((p, i) =>
        `<option value="native:${i}">${esc(`${names.get(p.left)} + ${names.get(p.right)}`)}</option>`).join('')}</optgroup>`);
    }
    options.push(`<optgroup label="General-model pairs">${data.agreement_rule.explorer_pairs.map((p, i) =>
      `<option value="general:${i}">${esc(`${p.run_a.label} + ${p.run_b.label}`)}</option>`).join('')}</optgroup>`);
    const solar = native ? native.pairs.findIndex(p => p.left === 'solar-decide-native-fresh1-p0' && p.right === 'perplexity-decider-native-fresh1-p0') : -1;
    const el = mount('explorer');
    el.innerHTML = `<h3>Every pair under the agree-or-defer rule</h3>
      <p>${esc(data.agreement_rule.rule)}${native ? '' : ' The decision-model pair file did not load, so only general-model pairs are listed.'}</p>
      <label for="di-pair">Pair</label> <select id="di-pair">${options.join('')}</select>
      <div class="di-pair-detail" aria-live="polite"></div>`;
    const select = el.querySelector('select');
    const detail = el.querySelector('.di-pair-detail');
    const show = () => { detail.innerHTML = pairDetail(data, native, select.value); };
    select.value = solar >= 0 ? `native:${solar}` : 'general:0';
    select.addEventListener('change', show);
    show();
  }

  function calibrationChart(data) {
    const models = [['jev', 'Jev', 'di-series-a'], ['clef-flash', 'Clef Flash', 'di-series-b']];
    const x = v => 48 + v * 260;
    const y = v => 222 - v * 200;
    const ece = Object.fromEntries(data.calibration.models.map((m, i) => [m.model, i]));
    const series = models.map(([key, label, cls]) => {
      const pts = data.calibration.reliability_bins[key].map((b, i) => ({...b, i})).filter(b => b.n > 0);
      return `<g class="${cls}"><polyline fill="none" points="${pts.map(b => `${x(b.mean_confidence).toFixed(1)},${y(b.accuracy).toFixed(1)}`).join(' ')}"/>
        ${pts.map(b => `<circle cx="${x(b.mean_confidence).toFixed(1)}" cy="${y(b.accuracy).toFixed(1)}" r="${Math.min(11, 3 + Math.sqrt(b.n) / 3).toFixed(1)}"/>`).join('')}</g>`;
    }).join('');
    const ticks = [0, 0.5, 1].map(t => `<text x="${x(t)}" y="240" text-anchor="middle">${t}</text><text x="40" y="${y(t) + 4}" text-anchor="end">${t}</text>`).join('');
    const tableRows = models.map(([key, label]) => data.calibration.reliability_bins[key].map((b, i) => {
      const p = `calibration.reliability_bins.${key}[${i}]`;
      return `<tr><th scope="row">${esc(label)}</th><td>${num(data, `${p}.lower`, 'text')} to ${num(data, `${p}.upper`, 'text')}</td><td>${num(data, `${p}.n`)}</td><td>${num(data, `${p}.mean_confidence`, 'conf')}</td><td>${num(data, `${p}.accuracy`, 'pct')}</td></tr>`;
    }).join('')).join('');
    mount('calibration').innerHTML = `<h3>Jev's stated confidence against how often it was right</h3>
      <p class="di-sub">Each point is a confidence bin, all fields and stages pooled; a bigger point holds more answers. On the diagonal, stated confidence equals the share that matched. Jev sits on it. Clef Flash sits well above it, so it was right more often than it said.</p>
      <div class="di-chart"><svg viewBox="0 0 320 256" role="img" aria-labelledby="di-cal-title di-cal-desc">
        <title id="di-cal-title">Reliability of provider confidence, Jev and Clef Flash</title>
        <desc id="di-cal-desc">Each point is a confidence bin, all fields and stages pooled. Points on the diagonal mean the stated confidence matched the share of answers that agreed with the reference. Jev sits near the diagonal; Clef Flash sits far above it, so its confidence understates how often it matched.</desc>
        <line class="di-axis" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(0)}"/><line class="di-axis" x1="${x(0)}" y1="${y(0)}" x2="${x(0)}" y2="${y(1)}"/>
        <line class="di-diagonal" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}"/>${ticks}${series}
        <text class="di-axis-label" x="${x(0.5)}" y="254" text-anchor="middle">stated confidence</text>
        <text class="di-axis-label" x="12" y="${y(0.5)}" text-anchor="middle" transform="rotate(-90 12 ${y(0.5)})">share matched</text>
      </svg>
      <ul class="di-legend"><li class="di-series-a">Jev, expected calibration error ${num(data, `calibration.models[${ece.jev}].ece_confidence`, 'ece')} over ${num(data, `calibration.models[${ece.jev}].field_answers`)} answers</li>
        <li class="di-series-b">Clef Flash, expected calibration error ${num(data, `calibration.models[${ece['clef-flash']}].ece_confidence`, 'ece')} over ${num(data, `calibration.models[${ece['clef-flash']}].field_answers`)} answers</li></ul></div>
      <details class="di-details"><summary>The bins behind the chart</summary><div class="di-table-wrap" tabindex="0" role="region" aria-label="Reliability bins"><table>
        <caption>Provider confidence bins, all fields and stages pooled per model.</caption>
        <thead><tr><th scope="col">Model</th><th scope="col">Confidence bin</th><th scope="col">Answers</th><th scope="col">Mean confidence</th><th scope="col">Matched</th></tr></thead>
        <tbody>${tableRows}</tbody></table></div></details>`;
  }

  function corrections(data) {
    const items = data.corrections.items.map(item => `<li><p class="di-said">We said: ${esc(item.said)}</p>
      <p class="di-correct">The saved answers show: ${prose(data, item.correct)}</p></li>`).join('');
    mount('corrections').innerHTML = `<p>On ${num(data, 'corrections.date', 'date')} a recount over every saved answer corrected ${num(data, 'corrections.count')} statements we had made earlier.</p><ol class="di-corrections">${items}</ol>`;
  }

  async function load(path) {
    const response = await fetch(`./${path}`, {cache: 'no-store'});
    if (!response.ok) throw Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  async function init() {
    const status = mount('changed') || mount('corrections');
    try {
      const [data, native] = await Promise.all([load(FEED).then(validate), mount('explorer') ? load(NATIVE).catch(() => null) : null]);
      if (mount('changed')) mount('changed').innerHTML = `<p>The recount corrected ${num(data, 'corrections.count')} earlier statements. They are listed on the <a href="method.html#corrections">Method page</a>.</p>`;
      if (mount('cards')) mount('cards').innerHTML = MAIN.map(id => card(data, id, id === 'determinism' ? stableWrong(data) : id === 'calibration' ? confidentWrong(data) : '')).join('');
      if (mount('more')) mount('more').innerHTML = `<details class="di-details di-more"><summary>Three more patterns in the saved answers</summary><div class="deep-insights__cards">${MORE.map(id => card(data, id)).join('')}</div></details>`;
      if (mount('explorer')) explorer(data, native);
      if (mount('calibration')) calibrationChart(data);
      if (mount('corrections')) corrections(data);
    } catch (error) {
      if (status) status.innerHTML = `<p>The recomputed findings did not load. <a href="./${FEED}">The data file</a> holds every number.</p>`;
      console.error('Deep insights source error:', error);
    } finally {
      status?.setAttribute('aria-busy', 'false');
    }
  }

  init();
})();
