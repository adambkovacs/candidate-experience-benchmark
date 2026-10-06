/* Nine matched Liquid prompt comparisons from the closed public findings feed. */
(() => {
  const target = document.getElementById('liquid-prompt-chart');
  if (!target) return;

  const passes = ['fresh1', 'fresh2', 'fresh3'];
  const pairs = [
    ['P0', 'P1', 'Base task', 'Classifier instructions'],
    ['P1', 'P2', 'Classifier instructions', 'Decision rules'],
    ['P0', 'P2', 'Base task', 'Decision rules']
  ];
  const source = './liquid-d1-native-full-findings.json';
  const whole = value => Number.isInteger(value) && value >= 0 && value <= 60;
  const uniqueIds = ids => Array.isArray(ids) && ids.every(id => /^DEV-\d{3}$/.test(id)) &&
    new Set(ids).size === ids.length;

  function readPairs(feed) {
    if (feed?.kind !== 'liquid-d1-native-full-findings-v1' ||
        feed.closed_stage_count !== 9 || !feed.matched_prompt_comparisons ||
        !Array.isArray(feed.sourceBindings) ||
        !feed.sourceBindings.some(binding =>
          binding.path === 'data/pilot/proposed_labels.jsonl' &&
          /^[0-9a-f]{64}$/.test(binding.sha256))) {
      throw Error('Incomplete Liquid findings');
    }
    return passes.map(pass => pairs.map(([left, right, leftName, rightName]) => {
      const key = `${pass}/${left}_vs_${pass}/${right}`;
      const item = feed.matched_prompt_comparisons[key];
      const score = item?.all_four;
      const changed = item?.changed_record_count;
      const gained = score?.gained_ids;
      const lost = score?.lost_ids;
      const changedIds = item?.changed_records?.map(row => row.id);
      if (item?.left !== `${pass}/${left}` || item?.right !== `${pass}/${right}` ||
          item.shared_valid !== 60 || !whole(changed) ||
          !Array.isArray(item.changed_records) || item.changed_records.length !== changed ||
          !uniqueIds(changedIds) ||
          !uniqueIds(gained) || !uniqueIds(lost) ||
          !whole(score.left_correct) || !whole(score.right_correct) ||
          [...gained, ...lost].some(id => !changedIds.includes(id)) ||
          gained.some(id => lost.includes(id)) ||
          gained.length + lost.length > changed ||
          score.right_correct - score.left_correct !== gained.length - lost.length) {
        throw Error('Incomplete Liquid paired comparison');
      }
      return {leftName, rightName, changed, gained: gained.length, lost: lost.length};
    }));
  }

  function row(item, scale) {
    const lossWidth = item.lost / scale * 100;
    const gainWidth = item.gained / scale * 100;
    return `<li class="liquid-prompt-chart__row">
      <div class="liquid-prompt-chart__row-label"><strong>${item.leftName} <span aria-hidden="true">→</span> ${item.rightName}</strong><span>${item.changed}/60 changed an answer</span></div>
      <div class="liquid-prompt-chart__bars" aria-hidden="true"><span class="liquid-prompt-chart__negative"><i style="width:${lossWidth}%"></i></span><span class="liquid-prompt-chart__positive"><i style="width:${gainWidth}%"></i></span></div>
      <p class="liquid-prompt-chart__values"><span>${item.lost} lost a full match</span><span>${item.gained} gained a full match</span></p>
    </li>`;
  }

  function render(groups) {
    const scale = Math.max(4, ...groups.flatMap(items => items.flatMap(item => [item.lost, item.gained])));
    target.innerHTML = `<figure class="liquid-prompt-chart__figure" aria-labelledby="liquid-prompt-chart-title">
      <div class="liquid-prompt-chart__heading"><p class="liquid-prompt-chart__kicker">Liquid d1 / native Choice</p><h3 id="liquid-prompt-chart-title">Prompt changes, review by review</h3><p>Each comparison uses the same 60 development reviews. A changed answer is separate from a gained or lost all-four match.</p></div>
      <div class="liquid-prompt-chart__legend" aria-label="Bar legend"><span><i class="liquid-prompt-chart__swatch liquid-prompt-chart__swatch--loss" aria-hidden="true"></i> Lost all-four match</span><span><i class="liquid-prompt-chart__swatch liquid-prompt-chart__swatch--gain" aria-hidden="true"></i> Gained all-four match</span></div>
      <p class="liquid-prompt-chart__axis">Bar scale: 0 to ${scale} reviews on each side</p>
      <div class="liquid-prompt-chart__groups">${groups.map((items, index) => `<section aria-labelledby="liquid-prompt-pass-${index + 1}"><h4 id="liquid-prompt-pass-${index + 1}">Pass ${index + 1}</h4><ol>${items.map(item => row(item, scale)).join('')}</ol></section>`).join('')}</div>
      <figcaption>Matches use the frozen provisional reference answers. The three passes repeat these reviews; they are not 180 independent cases. <a href="${source}">Read the Liquid findings and source hashes</a>.</figcaption>
    </figure>`;
  }

  target.setAttribute('aria-live', 'polite');
  target.setAttribute('aria-busy', 'true');
  fetch(source, {cache: 'no-store'}).then(response => {
    if (!response.ok) throw Error('Liquid findings unavailable');
    return response.json();
  }).then(feed => render(readPairs(feed))).catch(() => {
    target.innerHTML = '<p class="liquid-prompt-chart__unavailable" role="alert">The Liquid prompt comparison could not be loaded. <a href="./liquid-d1-native-full-findings.json">Open the findings file</a>.</p>';
  }).finally(() => target.setAttribute('aria-busy', 'false'));
})();
