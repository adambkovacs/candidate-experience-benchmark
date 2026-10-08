/* Recomputed findings panel. Every number is read from a feed by path and carries data-source="<feed>#<path>". */
(() => {
  'use strict';
  const FEED = 'deep-insights-v1.json';
  const NATIVE = 'native-agreement-policy-v1.json';
  const root = document.getElementById('deep-insights');
  if (!root) return;
  const mount = name => root.querySelector(`[data-di-mount="${name}"]`);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const get = (data, path) => path.replace(/\]/g, '').split(/[.[]/).reduce((node, key) =>
    node == null ? undefined : node[Array.isArray(node) ? Number(key) : key], data);
  const FIELD = {sentiment: 'sentiment', follow_up_needed: 'follow-up', serious_concern_reported: 'serious concern', testimonial_potential: 'testimonial'};
  const MAIN = ['insufficient_collapse', 'frontier_convergence', 'agreement_rule', 'determinism', 'calibration'];
  const MORE = ['prompt_direction', 'size_thinking', 'cost_frontier'];
  const TAG = {solid: 'Solid', 'descriptive-only': 'Descriptive only', anecdotal: 'Anecdotal'};

  function fmt(value, format = 'count') {
    if (value === null || value === undefined || value === '') return 'unavailable';
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
    return `<data class="di-num" value="${esc(value ?? '')}" data-source="${feed}#${esc(path)}">${esc(fmt(value, format))}</data>`;
  }

  const prose = (data, parts) => parts.map(part => typeof part === 'string' ? esc(part) : num(data, part.path, part.format)).join('');
  const idList = ids => ids.length ? ids.map(id => `<span class="di-id">${esc(id)}</span>`).join(' ') : '<span class="di-none">none</span>';

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

  function sourceLine(block) {
    const scripts = block.scripts.map(path => `<code>${esc(path.split('/').pop())}</code>`).join(', ');
    const feeds = block.feeds.map(path => `<code>${esc(path.split('/').pop())}</code>`).join(', ');
    return `<p class="di-source">Computed by ${scripts} from ${feeds}. Numbers: <a href="./${FEED}">${FEED}</a>.</p>`;
  }

  function card(data, id, extra = '') {
    const block = data[id];
    const numbers = block.key_numbers.map(k => `<li><span class="di-kn-label">${prose(data, k.label)}</span>
      <span class="di-kn-value">${num(data, k.value, k.format)}${k.of ? ` <span class="di-of">of ${num(data, k.of)}</span>` : ''}${k.share ? ` <span class="di-share">(${num(data, k.share, 'pct')})</span>` : ''}</span></li>`).join('');
    return `<article class="di-card" aria-labelledby="di-${id}-title">
      <h3 id="di-${id}-title">${prose(data, block.title)}</h3>
      <ul class="di-kn">${numbers}</ul>
      <p class="di-implication"><strong>Implication:</strong> ${esc(block.implication)}</p>
      <p class="di-meta"><span class="di-tag di-tag--${esc(block.confidence.tag)}">${esc(TAG[block.confidence.tag] || block.confidence.tag)}</span> ${esc(block.confidence.note)}</p>
      ${extra}${sourceLine(block)}
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
      return `<li><span class="di-id">${esc(a.id)}</span> ${esc(FIELD[a.field])}: answered <q>${esc(a.prediction)}</q>, reference <q>${esc(a.reference.replace(/_/g, ' '))}</q>, confidence ${num(data, `${p}.confidence`, 'conf')}</li>`;
    }).join('');
    return `<p class="di-sub">Jev's first-pass answers wrong at confidence ${num(data, 'calibration.jev_confident_wrong.threshold', 'conf')} or higher:</p><ul class="di-list">${rows}</ul>`;
  }

  function routingTable(data, index) {
    const row = data.agreement_rule.native_routing[index];
    const p = `agreement_rule.native_routing[${index}]`;
    const full = row.left === 'solar-decide-native-fresh1-p0' && row.right === 'perplexity-decider-native-fresh1-p0';
    const ids = step => full ? `<td>${idList(data.agreement_rule.full_policy_routing.rows[step].ids)}</td>` : '';
    return `<div class="di-table-wrap" tabindex="0" role="region" aria-label="Full policy routing"><table class="di-routing"><caption>Full policy on all ${num(data, 'denominator')} reviews: defer on disagreement, escalate any serious concern, send any insufficient information for clarification.</caption>
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
      note = 'Seven native decision models, first pass, base prompt. Known charges for both runs.';
      const r = data.agreement_rule.native_routing.findIndex(x => x.left === pair.left && x.right === pair.right);
      if (r >= 0) routing = routingTable(data, r);
    } else {
      const pair = data.agreement_rule.explorer_pairs[i];
      const p = `agreement_rule.explorer_pairs[${i}]`;
      name = `${pair.run_a.label} + ${pair.run_b.label}`;
      rows = [num(data, `${p}.accepted`), num(data, `${p}.accepted_errors`), num(data, `${p}.deferred`), num(data, `${p}.two_run_charge_usd`, 'usd')];
      deferredIds = pair.deferred_ids;
      errorIds = pair.accepted_error_ids;
      note = `General LLM pair from saved base-prompt passes. Charge basis: ${pair.charge_basis}.`;
    }
    return `<div class="di-table-wrap" tabindex="0" role="region" aria-label="Selected pair outcome"><table class="di-pair"><caption>${esc(name)}</caption><tbody>
      <tr><th scope="row">Accepted, out of ${num(data, 'denominator')}</th><td>${rows[0]}</td></tr>
      <tr><th scope="row">Accepted with a reference error</th><td>${rows[1]}</td></tr>
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
      options.push(`<optgroup label="Seven native decision models, first pass">${native.pairs.map((p, i) =>
        `<option value="native:${i}">${esc(`${names.get(p.left)} + ${names.get(p.right)}`)}</option>`).join('')}</optgroup>`);
    }
    options.push(`<optgroup label="General LLM pairs, saved passes">${data.agreement_rule.explorer_pairs.map((p, i) =>
      `<option value="general:${i}">${esc(`${p.run_a.label} + ${p.run_b.label}`)}</option>`).join('')}</optgroup>`);
    const solar = native ? native.pairs.findIndex(p => p.left === 'solar-decide-native-fresh1-p0' && p.right === 'perplexity-decider-native-fresh1-p0') : -1;
    const el = mount('explorer');
    el.innerHTML = `<h3>Agree or defer: try a pair</h3>
      <p>${esc(data.agreement_rule.rule)} The reference scores accepted answers only after that choice.${native ? '' : ' The seven-model pair file could not be loaded, so only general LLM pairs are listed.'}</p>
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
        ${pts.map(b => `<circle cx="${x(b.mean_confidence).toFixed(1)}" cy="${y(b.accuracy).toFixed(1)}" r="${Math.min(11, 3 + Math.sqrt(b.n) / 3).toFixed(1)}"><title>${esc(label)}, confidence bin ${esc(b.lower)} to ${esc(b.upper)}</title></circle>`).join('')}</g>`;
    }).join('');
    const ticks = [0, 0.5, 1].map(t => `<text x="${x(t)}" y="240" text-anchor="middle">${t}</text><text x="40" y="${y(t) + 4}" text-anchor="end">${t}</text>`).join('');
    const tableRows = models.map(([key, label]) => data.calibration.reliability_bins[key].map((b, i) => {
      const p = `calibration.reliability_bins.${key}[${i}]`;
      return `<tr><th scope="row">${esc(label)}</th><td>${num(data, `${p}.lower`, 'text')} to ${num(data, `${p}.upper`, 'text')}</td><td>${num(data, `${p}.n`)}</td><td>${num(data, `${p}.mean_confidence`, 'conf')}</td><td>${num(data, `${p}.accuracy`, 'pct')}</td></tr>`;
    }).join('')).join('');
    mount('calibration').innerHTML = `<h3>Stated confidence against the share that matched</h3>
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
      <details class="di-details"><summary>Bin values</summary><div class="di-table-wrap" tabindex="0" role="region" aria-label="Reliability bins"><table>
        <caption>Provider confidence bins, all fields and stages pooled per model.</caption>
        <thead><tr><th scope="col">Model</th><th scope="col">Confidence bin</th><th scope="col">Answers</th><th scope="col">Mean confidence</th><th scope="col">Matched</th></tr></thead>
        <tbody>${tableRows}</tbody></table></div></details>`;
  }

  function hardest(data) {
    const block = data.hardest_reviews;
    const items = block.reviews.map((r, i) => {
      const p = `hardest_reviews.reviews[${i}]`;
      const answer = values => Object.keys(FIELD).map((f, k) => `${FIELD[f]} ${String(values[k] ?? values[f]).replace(/_/g, ' ')}`).join(' · ');
      const ref = answer(r.reference);
      const tags = [r.disputed_reference ? '<span class="di-badge">disputed reference</span>' : '', r.off_topic ? '<span class="di-badge">off-topic</span>' : ''].join('');
      return `<li><div class="di-hard-head"><span class="di-id">${esc(r.id)}</span> matched by ${num(data, `${p}.all_four`)} of ${num(data, `${p}.run_passes`)} run-passes (${num(data, `${p}.share`, 'pct')}) ${tags}</div>
        <blockquote><p>${esc(r.text)}</p></blockquote>
        <p class="di-sub">Reference: ${esc(ref)}. Most missed field: ${esc(FIELD[r.driving_field])}. Most common wrong answer, given ${num(data, `${p}.most_common_wrong_count`)} times: ${esc(r.most_common_wrong_answer ? answer(r.most_common_wrong_answer) : 'none')}.</p></li>`;
    }).join('');
    mount('hardest').innerHTML = `<h3>${prose(data, block.title)}</h3><p>${esc(block.implication)}</p><ol class="di-hardest">${items}</ol>${sourceLine(block)}`;
  }

  function corrections(data) {
    const items = data.corrections.items.map(item => `<li><p class="di-said"><span>Said</span> <s>${esc(item.said)}</s></p>
      <p class="di-correct"><span>Corrected</span> ${prose(data, item.correct)}</p><p class="di-source">${item.confidence_tag ? `<span class="di-tag di-tag--${esc(item.confidence_tag)}">${esc(TAG[item.confidence_tag] || item.confidence_tag)}</span> ` : ''}Source: <code>${esc(item.source)}</code></p></li>`).join('');
    mount('corrections').innerHTML = `<h3>Corrections dated ${num(data, 'corrections.date', 'date')}</h3><ol class="di-corrections">${items}</ol>`;
  }

  async function load(path) {
    const response = await fetch(`./${path}`, {cache: 'no-store'});
    if (!response.ok) throw Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  async function init() {
    const changed = mount('changed');
    try {
      const [data, native] = await Promise.all([load(FEED).then(validate), load(NATIVE).catch(() => null)]);
      changed.innerHTML = `<p>${prose(data, data.what_changed.segments)}</p>`;
      mount('cards').innerHTML = MAIN.map(id => card(data, id, id === 'determinism' ? stableWrong(data) : id === 'calibration' ? confidentWrong(data) : '')).join('');
      mount('more').innerHTML = `<details class="di-details di-more"><summary>Three more recomputed patterns</summary><div class="deep-insights__cards">${MORE.map(id => card(data, id)).join('')}</div></details>`;
      explorer(data, native);
      calibrationChart(data);
      hardest(data);
      corrections(data);
    } catch (error) {
      changed.innerHTML = `<p>This page could not load or check the recomputed findings. <a href="./${FEED}">Open the data file</a>.</p>`;
      console.error('Deep insights source error:', error);
    } finally {
      changed.setAttribute('aria-busy', 'false');
    }
  }

  init();
})();
