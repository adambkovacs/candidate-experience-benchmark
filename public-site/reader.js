(() => {
  'use strict';
  const chapters = [...document.querySelectorAll('.story-chapter')];
  const links = [...document.querySelectorAll('.story-nav a')];
  const mark = id => links.forEach(link => {
    if (link.hash === '#' + id) link.setAttribute('aria-current', 'step');
    else link.removeAttribute('aria-current');
  });
  const draw = (id, changed) => {
    const grid = document.getElementById(id);
    if (!grid) return;
    const fragment = document.createDocumentFragment();
    for (let n = 1; n <= 60; n++) {
      const cell = document.createElement('i');
      cell.setAttribute('aria-hidden', 'true');
      if (changed.has(n)) cell.className = 'changed';
      fragment.appendChild(cell);
    }
    grid.replaceChildren(fragment);
  };
  // A totals diagram for the published Jev baseline, not a review-order chart.
  draw('story-jev-grid', new Set([55,56,57,58,59,60]));
  async function loadChangedExamples() {
    const select = document.getElementById('story-change-select');
    try {
      const response = await fetch('./reader-evidence.json');
      if (!response.ok) throw new Error('Examples unavailable');
      const data = await response.json();
      if (data.schema !== 'reader-selected-two-pass-v1' || data.denominator !== 60 || data.changes.length !== 11)
        throw new Error('Selected illustration changed; review the story before publishing');
      draw('story-flip-grid', new Set(data.changes.map(row => Number(row.id.slice(4)))));
      select.replaceChildren(...data.changes.map(row => {
        const option = document.createElement('option'); option.value = row.id; option.textContent = row.id; return option;
      }));
      const names = {sentiment:'Experience',follow_up_needed:'Follow-up needed',serious_concern_reported:'Serious concern',testimonial_potential:'Testimonial potential'};
      function show() {
        const row = data.changes.find(item => item.id === select.value);
        if (!row) return;
        document.getElementById('story-change-text').textContent = row.feedback;
        const list = document.getElementById('story-change-answers'); list.replaceChildren();
        for (const field of Object.keys(names)) {
          if (row.first[field] === row.second[field]) continue;
          const item = document.createElement('p');
          item.textContent = names[field] + ': ' + row.first[field].replaceAll('_',' ') + ' → ' + row.second[field].replaceAll('_',' ');
          list.appendChild(item);
        }
      }
      select.addEventListener('change',show); show();
    } catch (error) {
      select.replaceChildren(new Option('Examples unavailable',''));
      document.getElementById('story-change-text').textContent = 'The detailed examples could not load. Use the saved-answer source link below.';
    }
  }
  loadChangedExamples();
  links.forEach(link => link.addEventListener('click', () => mark(link.hash.slice(1))));
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(e => e.isIntersecting).sort((a,b) => b.intersectionRatio-a.intersectionRatio);
      for (const entry of visible) entry.target.classList.add('is-visible');
      if (visible.length) mark(visible[0].target.id);
    }, {threshold:[.15,.4,.7], rootMargin:'-100px 0px -15% 0px'});
    chapters.forEach(chapter => observer.observe(chapter));
  } else chapters.forEach(chapter => chapter.classList.add('is-visible'));
})();
