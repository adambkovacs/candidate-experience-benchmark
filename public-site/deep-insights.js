/* Four findings, the pair explorer and the calibration chart on Read; the corrections log on Method.
   Every number is read from a feed by path and carries data-source="<feed>#<path>". Mounts are optional. */
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
  const L = window.BM_LABEL;
  const usd = v => L ? L.usd(v) : `$${Number(v).toFixed(4)}`;
  const count = v => L ? L.count(v) : Number(v).toLocaleString('en-US');
  const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'];
  // A run as a reader names it: model and effort, never the pass or quantisation tag.
  const setup = run => L ? [L.model(run.model), L.effort(run.effort, run.run_id)].filter(Boolean).join(', ')
    : String(run.label).replace(/ \(fp4\)| (original|fresh\d|repeat\d)$/g, '');
  // Hedge words the feed carries inside corrections. \u0000n\u0000 stands for the n-th bound number.
  const STRIP = [
    [/ that share the same \u0000\d+\u0000 texts; descriptive-only\)/g, ')'],
    [/[,;] descriptive-only\)/g, ')'],
    [/^On these \u0000\d+\u0000 reviews, Jev/, 'Jev'],
    [/^The study cost (\u0000\d+\u0000) in known provider charges/, "The seven decision models' nine-pass series cost $1"],
  ];

  function fmt(value, format = 'count') {
    if (value === null || value === '') return 'not recorded';
    if (format === 'text') return String(value);
    if (format === 'date') return new Date(`${value}T00:00:00Z`).toLocaleDateString('en-GB', {day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC'});
    const n = Number(value);
    if (format === 'word') return WORDS[n] ?? count(n);
    if (format === 'pct') return `${(n * 100).toFixed(1)}%`;
    if (format === 'ece') return n.toFixed(3);
    if (format === 'conf') return n.toFixed(2);
    if (format.startsWith('usd')) return usd(n);
    return count(n);
  }

  // One bound number. data-value holds the raw feed value so a number audit can compare it.
  function num(data, path, format = 'count', feed = FEED) {
    const value = get(data, path);
    if (value === undefined) throw Error(`Unbound number ${feed}#${path}`);
    return `<span class="di-num${format === 'text' ? ' di-text' : ''}" data-value="${esc(value ?? '')}" data-source="${feed}#${esc(path)}">${esc(fmt(value, format))}</span>`;
  }

  function prose(data, parts) {
    const bound = parts.filter(part => typeof part !== 'string');
    let template = parts.map(part => typeof part === 'string' ? part : `\u0000${bound.indexOf(part)}\u0000`).join('');
    for (const [pattern, to] of STRIP) template = template.replace(pattern, to);
    return template.split(/\u0000(\d+)\u0000/).map((text, i) =>
      i % 2 ? num(data, bound[Number(text)].path, bound[Number(text)].format) : esc(text)).join('');
  }
  // Each review id stays on one line; a list breaks only between ids.
  const idList = ids => ids.length ? ids.map((id, i) => `<span class="di-id">${esc(id)}${i < ids.length - 1 ? ',' : ''}</span>`).join(' ') : 'none';

  function validate(data) {
    if (data?.schema !== 'deep-insights-v1' || data.denominator !== 60 || !Array.isArray(data.corrections?.items)) {
      throw Error('Deep insights feed header changed');
    }
    return data;
  }

  function findings(data) {
    const n = (path, format) => num(data, path, format);
    const F = 'insufficient_collapse.fields.follow_up_needed';
    const B = 'agreement_rule.best_beating';
    const G = 'cost_frontier.gate.passes';
    const best = data.agreement_rule.best_beating;
    const cheap = data.cost_frontier.frontier.find(f => f.run_id === data.cost_frontier.gate.passes[0].run_id);
    const cheapName = cheap ? setup(cheap).replace(', ', ' with ') : 'the cheapest setup';
    const cards = [
      ['When a review gave them nothing to go on, decision models still picked an answer three times out of four.',
        `Where the reference says a review doesn't say enough to decide on follow-up, decision models still answered yes or no in ${n(`${F}.decision.definite`)} of ${n(`${F}.decision.valid_answers`)} answers. General models did it in ${n(`${F}.general.definite`)} of ${n(`${F}.general.valid_answers`)}, about one time in seven. So score can't-tell on its own. The four-answer total hides this miss on exactly the reviews a person should see.`],
      ['The best runs make the same mistakes.',
        `Of the ${n('frontier_convergence.strong_run_passes')} runs that matched ${n('frontier_convergence.strong_min_all_four')} or more, ${n('frontier_convergence.largest_set.run_passes')} gave the exact same answers, and those ${n('frontier_convergence.largest_set.run_passes')} came from ${n('frontier_convergence.largest_set.family_count', 'word')} different model families. All of them miss the three reviews whose labels are disputed, so two of them paired under the agree-or-defer rule accept those answers together.`],
      ['Two cheap general models accepted more reviews than Solar and Perplexity, for less money.',
        `${esc(setup(best.run_a).split(', ')[0])} and ${esc(setup(best.run_b).split(', ')[0])} accepted ${n(`${B}.accepted`)} of ${n('denominator')} with ${n(`${B}.accepted_errors`, 'word')} errors for ${n(`${B}.two_run_charge_usd`, 'usd')}. Solar and Perplexity spent ${n('agreement_rule.solar_perplexity.two_run_charge_usd', 'usd')} to accept ${n('agreement_rule.solar_perplexity.accepted')}. ${n('agreement_rule.pairs_more_and_cheaper')} of the ${n('agreement_rule.charged_cross_pairs')} paid pairs beat Solar and Perplexity for less money, with no errors let through.`],
      ['Most decision models get the same reviews wrong every time, so you check their mistakes once.',
        `${n('determinism.zero_change.decision')} of the ${n('determinism.configurations.decision')} decision-model setups gave identical answers on all three passes, against ${n('determinism.zero_change.general')} of the ${n('determinism.configurations.general')} general ones. A general model gets different ones wrong on each run, and the total can stay flat while the answers move underneath it. The cheapest run that matched ${n(`${G}[0].all_four`)}, ${esc(cheapName)} at ${n(`${G}[0].usd`, 'usd')}, matched ${n(`${G}[1].all_four`)} when we ran it again.`],
    ];
    mount('cards').innerHTML = cards.map(([title, body]) => `<article class="di-finding"><h3>${esc(title)}</h3><p>${body}</p></article>`).join('');
  }

  function routingTable(data, index) {
    const row = data.agreement_rule.native_routing[index];
    const p = `agreement_rule.native_routing[${index}]`;
    const full = row.left === 'solar-decide-native-fresh1-p0' && row.right === 'perplexity-decider-native-fresh1-p0';
    const ids = step => full ? `<td>${idList(data.agreement_rule.full_policy_routing.rows[step].ids)}</td>` : '';
    return `<div class="di-table-wrap" tabindex="0" role="region" aria-label="Full policy routing"><table class="di-routing"><caption>Where the ${num(data, 'denominator')} reviews go under the full policy: a disagreement goes to a person, a serious concern is escalated, and a can't-tell answer goes back for clarification.</caption>
      <thead><tr><th scope="col">Route</th><th scope="col">Reviews</th>${full ? '<th scope="col">Review IDs</th>' : ''}</tr></thead><tbody>
      <tr><th scope="row">The two answers differ</th><td>${num(data, `${p}.deferred`)}</td>${ids(0)}</tr>
      <tr><th scope="row">Accepted, escalated for serious concern</th><td>${num(data, `${p}.escalated_beyond_deferral`)}</td>${ids(1)}</tr>
      <tr><th scope="row">Accepted, sent for clarification</th><td>${num(data, `${p}.clarification_beyond_deferral`)}</td>${ids(2)}</tr>
      <tr class="di-total"><th scope="row">Reaches a person</th><td>${num(data, `${p}.reaches_person`)}</td>${ids(3)}</tr>
      <tr><th scope="row">Accepted with no routing</th><td>${num(data, `${p}.accepted_no_routing`)}</td>${ids(4)}</tr></tbody></table></div>`;
  }

  // General pairs that differ only by pass collapse into one entry; the other passes show as one line.
  function generalPairs(data) {
    const seen = new Set();
    const groups = new Map();
    data.agreement_rule.explorer_pairs.forEach((pair, i) => {
      const runs = [pair.run_a.run_id, pair.run_b.run_id].sort().join('+');
      if (seen.has(runs)) return;
      seen.add(runs);
      const name = [setup(pair.run_a), setup(pair.run_b)];
      const key = [...name].sort().join(' + ');
      if (!groups.has(key)) groups.set(key, {name: name.join(' + '), indexes: []});
      groups.get(key).indexes.push(i);
    });
    return [...groups.values()];
  }

  function pairDetail(data, native, groups, choice) {
    const [kind, index] = choice.split(':');
    const i = Number(index);
    let name, rows, deferredIds, errorIds, extra = '';
    if (kind === 'native') {
      const pair = native.pairs[i];
      const names = new Map(native.components.map(c => [c.id, c.display_name]));
      const p = `pairs[${i}]`;
      name = `${names.get(pair.left)} + ${names.get(pair.right)}`;
      rows = [num(native, `${p}.accepted_count`, 'count', NATIVE), num(native, `${p}.accepted_all_four_error_count`, 'count', NATIVE),
        num(native, `${p}.deferred_count`, 'count', NATIVE), num(native, `${p}.known_two_run_development_cost_usd`, 'usd', NATIVE)];
      deferredIds = pair.deferred_ids;
      errorIds = pair.accepted_all_four_error_ids;
      const r = data.agreement_rule.native_routing.findIndex(x => x.left === pair.left && x.right === pair.right);
      if (r >= 0) extra = routingTable(data, r);
    } else {
      const group = groups[i];
      const [first, ...others] = group.indexes;
      const pair = data.agreement_rule.explorer_pairs[first];
      const p = `agreement_rule.explorer_pairs[${first}]`;
      name = group.name;
      rows = [num(data, `${p}.accepted`), num(data, `${p}.accepted_errors`), num(data, `${p}.deferred`), num(data, `${p}.two_run_charge_usd`, 'usd')];
      deferredIds = pair.deferred_ids;
      errorIds = pair.accepted_error_ids;
      if (others.length) {
        const runs = others.map(j => `${num(data, `agreement_rule.explorer_pairs[${j}].accepted`)} accepted with ${num(data, `agreement_rule.explorer_pairs[${j}].accepted_errors`, 'word')} error${data.agreement_rule.explorer_pairs[j].accepted_errors === 1 ? '' : 's'}`);
        extra = `<p class="di-sub">The same two setups on other passes: ${runs.length > 1 ? `${runs.slice(0, -1).join(', ')} and ${runs.at(-1)}` : runs[0]}.</p>`;
      }
    }
    return `<div class="di-table-wrap" tabindex="0" role="region" aria-label="Selected pair outcome"><table class="di-pair"><caption>${esc(name)}</caption><tbody>
      <tr><th scope="row">Accepted, out of ${num(data, 'denominator')}</th><td>${rows[0]}</td></tr>
      <tr><th scope="row">Accepted, but wrong on at least one decision</th><td>${rows[1]}</td></tr>
      <tr><th scope="row">Sent to a person</th><td>${rows[2]}</td></tr>
      <tr><th scope="row">Cost of both runs</th><td>${rows[3]}</td></tr></tbody></table></div>
      <p class="di-ids"><strong>Sent to a person:</strong> ${idList(deferredIds)}</p>
      <p class="di-ids"><strong>Accepted with an error:</strong> ${idList(errorIds)}</p>${extra}`;
  }

  function explorer(data, native) {
    const groups = generalPairs(data);
    const options = [];
    if (native) {
      const names = new Map(native.components.map(c => [c.id, c.display_name]));
      options.push(`<optgroup label="Two decision models">${native.pairs.map((p, i) =>
        `<option value="native:${i}">${esc(`${names.get(p.left)} + ${names.get(p.right)}`)}</option>`).join('')}</optgroup>`);
    }
    options.push(`<optgroup label="Pairs with a general model">${groups.map((g, i) => `<option value="general:${i}">${esc(g.name)}</option>`).join('')}</optgroup>`);
    const solar = native ? native.pairs.findIndex(p => p.left === 'solar-decide-native-fresh1-p0' && p.right === 'perplexity-decider-native-fresh1-p0') : -1;
    const el = mount('explorer');
    el.innerHTML = `<h3>What each pair accepts</h3>
      <p class="di-sub">A pair accepts a review only when both models give the same four answers. Everything else goes to a person.</p>
      <label for="di-pair">Pair</label> <select id="di-pair">${options.join('')}</select>
      <div class="di-pair-detail" aria-live="polite"></div>`;
    const select = el.querySelector('select');
    const detail = el.querySelector('.di-pair-detail');
    const show = () => { detail.innerHTML = pairDetail(data, native, groups, select.value); };
    select.value = solar >= 0 ? `native:${solar}` : 'general:0';
    select.addEventListener('change', show);
    show();
  }

  function calibrationChart(data) {
    const models = [['jev', 'Jev', 'di-series-a'], ['clef-flash', 'Clef Flash', 'di-series-b']];
    const at = Object.fromEntries(data.calibration.models.map((m, i) => [m.model, i]));
    const x = v => 48 + v * 260;
    const y = v => 222 - v * 200;
    // ponytail: one point size for every bin; the bins table below carries the answer counts.
    const series = models.map(([key, , cls]) => {
      const pts = data.calibration.reliability_bins[key].filter(b => b.n > 0);
      return `<g class="${cls}"><polyline fill="none" points="${pts.map(b => `${x(b.mean_confidence).toFixed(1)},${y(b.accuracy).toFixed(1)}`).join(' ')}"/>
        ${pts.map(b => `<circle cx="${x(b.mean_confidence).toFixed(1)}" cy="${y(b.accuracy).toFixed(1)}" r="${cls === 'di-series-a' ? 3.5 : 5}"/>`).join('')}</g>`;
    }).join('');
    const ticks = [0, 0.5, 1].map(t => `<text x="${x(t)}" y="240" text-anchor="middle">${t}</text><text x="40" y="${y(t) + 4}" text-anchor="end">${t}</text>`).join('');
    const tableRows = models.map(([key, label]) => data.calibration.reliability_bins[key].map((b, i) => {
      if (!b.n) return '';
      const p = `calibration.reliability_bins.${key}[${i}]`;
      return `<tr><th scope="row">${esc(label)}</th><td>${num(data, `${p}.lower`, 'text')} to ${num(data, `${p}.upper`, 'text')}</td><td>${num(data, `${p}.n`)}</td><td>${num(data, `${p}.mean_confidence`, 'conf')}</td><td>${num(data, `${p}.accuracy`, 'pct')}</td></tr>`;
    }).join('')).join('');
    const m = key => `calibration.models[${at[key]}]`;
    const soup = data.calibration.jev_confident_wrong.answers.findIndex(a => a.id === 'DEV-029');
    mount('calibration').innerHTML = `<h3>How sure Jev and Clef Flash said they were, against how often they were right</h3>
      <p class="di-sub">Each point is a band of stated confidence, all four questions pooled. On the dashed diagonal a model is right exactly as often as it says. Jev sits on it. Clef Flash sits well above it, so it was right more often than it said.</p>
      <figure class="di-chart"><svg viewBox="0 0 320 256" role="img" aria-labelledby="di-cal-title di-cal-desc">
        <title id="di-cal-title">Stated confidence against share matched, Jev and Clef Flash</title>
        <desc id="di-cal-desc">Jev's points sit on the diagonal, so its stated confidence matches how often it was right. Clef Flash's points sit far above it, so its confidence understates how often it matched.</desc>
        <line class="di-axis" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(0)}"/><line class="di-axis" x1="${x(0)}" y1="${y(0)}" x2="${x(0)}" y2="${y(1)}"/>
        ${ticks}${series}<line class="di-diagonal" x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}"/>
        <text class="di-axis-label" x="${x(0.5)}" y="254" text-anchor="middle">stated confidence</text>
        <text class="di-axis-label" x="12" y="${y(0.5)}" text-anchor="middle" transform="rotate(-90 12 ${y(0.5)})">share matched</text>
      </svg>
      <div><ul class="di-legend"><li class="di-series-a">Jev, calibration gap ${num(data, `${m('jev')}.ece_confidence`, 'ece')} over ${num(data, `${m('jev')}.field_answers`)} answers</li>
        <li class="di-series-b">Clef Flash, calibration gap ${num(data, `${m('clef-flash')}.ece_confidence`, 'ece')} over ${num(data, `${m('clef-flash')}.field_answers`)} answers</li></ul>
      <figcaption>Clef Flash reports a confidence and an option probability, and on more than half its answers (${num(data, `${m('clef-flash')}.gap_over_0_2`)} of ${num(data, `${m('clef-flash')}.gap_answers`)}) they disagree by over ${num(data, 'calibration.gap_threshold', 'text')}. Jev, the best calibrated model here, was still ${num(data, `calibration.jev_confident_wrong.answers[${soup}].confidence`, 'conf')} sure on the soup review.</figcaption></div></figure>
      <details class="di-details"><summary>The bins behind the chart</summary><div class="di-table-wrap" tabindex="0" role="region" aria-label="Confidence bins"><table>
        <caption>Answers per band of stated confidence, and how many of them matched the reference.</caption>
        <thead><tr><th scope="col">Model</th><th scope="col">Confidence band</th><th scope="col">Answers</th><th scope="col">Mean confidence</th><th scope="col">Matched</th></tr></thead>
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
    const status = mount('cards') || mount('corrections');
    try {
      const [data, native] = await Promise.all([load(FEED).then(validate), mount('explorer') ? load(NATIVE).catch(() => null) : null]);
      if (mount('cards')) findings(data);
      if (mount('explorer')) explorer(data, native);
      if (mount('calibration')) calibrationChart(data);
      if (mount('corrections')) corrections(data);
    } catch (error) {
      if (status) status.innerHTML = `<p>These findings did not load. <a href="./${FEED}">The data file</a> holds every number.</p>`;
      console.error('Deep insights source error:', error);
    } finally {
      mount('changed')?.setAttribute('aria-busy', 'false');
      status?.setAttribute('aria-busy', 'false');
    }
  }

  init();
})();
