(() => {
  'use strict';
  const chapters = [...document.querySelectorAll('.story-chapter')];
  const links = [...document.querySelectorAll('.story-nav a')];
  const header = document.querySelector('.site-header');
  if (header) {
    const syncHeader = () => document.documentElement.style.setProperty('--reader-header-height', `${Math.ceil(header.getBoundingClientRect().height)}px`);
    syncHeader();
    window.addEventListener('resize', syncHeader);
    if ('ResizeObserver' in window) new ResizeObserver(syncHeader).observe(header);
  }
  const example = document.querySelector('.hero-example-details');
  if (example) {
    const compact = window.matchMedia('(max-width: 760px)');
    let mobileOpen = false;
    example.querySelector('summary').addEventListener('click', () => { mobileOpen = !example.open; });
    const syncExample = () => { example.open = compact.matches ? mobileOpen : true; };
    syncExample();
    compact.addEventListener('change', syncExample);
  }
  const noteSearch = document.getElementById('evidence-note-search');
  if (noteSearch) {
    const groups = [...document.querySelectorAll('.note-group')];
    const notes = groups.flatMap(group => [...group.querySelectorAll('.note-items .analysis-caveat')]);
    const status = document.getElementById('evidence-note-status');
    const empty = document.getElementById('evidence-note-empty');
    noteSearch.addEventListener('input', () => {
      const query = noteSearch.value.trim().toLocaleLowerCase();
      let matches = 0;
      groups.forEach(group => {
        let groupMatches = 0;
        group.querySelectorAll('.note-items .analysis-caveat').forEach(note => {
          const visible = !query || note.textContent.toLocaleLowerCase().includes(query);
          note.hidden = !visible;
          if (visible) groupMatches++;
        });
        group.hidden = Boolean(query) && groupMatches === 0;
        group.open = Boolean(query) && groupMatches > 0;
        matches += groupMatches;
      });
      empty.hidden = matches > 0;
      status.textContent = query ? `${matches} of ${notes.length} notes match.` : `${notes.length} notes across four topics.`;
    });
  }
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
  // The published Jev disagreement IDs are checked against the source-bound feed in tests.
  const jevDisagreements = new Set(['DEV-006','DEV-013','DEV-027','DEV-029','DEV-030','DEV-059']);
  const jevGrid = document.getElementById('story-jev-grid');
  if (jevGrid) {
    const fragment = document.createDocumentFragment();
    for (let n = 1; n <= 60; n++) {
      const id = `DEV-${String(n).padStart(3, '0')}`;
      const changed = jevDisagreements.has(id);
      const cell = document.createElement(changed ? 'a' : 'i');
      if (changed) {
        cell.className = 'changed';
        cell.href = `?run=typesafe-jev113-v2&case=${id}#inspect`;
        cell.setAttribute('aria-label', `Inspect Jev disagreement on ${id}`);
        cell.title = `Inspect ${id}`;
      } else cell.setAttribute('aria-hidden', 'true');
      fragment.appendChild(cell);
    }
    jevGrid.replaceChildren(fragment);
  }
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
  const story = document.getElementById('story');
  let pending = false;
  function updateReadingPosition() {
    pending = false;
    if (!story || !chapters.length) return;
    const readingLine = Math.min(window.innerHeight * .42, 330);
    const current = [...chapters].reverse().find(chapter => chapter.getBoundingClientRect().top <= readingLine) || chapters[0];
    mark(current.id);
    const start = chapters[0].offsetTop;
    const end = chapters[chapters.length - 1].offsetTop + chapters[chapters.length - 1].offsetHeight - window.innerHeight * .6;
    const progress = end > start ? Math.max(0, Math.min(1, (window.scrollY + readingLine - start) / (end - start))) : 0;
    story.style.setProperty('--story-progress', progress.toFixed(3));
  }
  function scheduleReadingPosition() {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(updateReadingPosition);
  }
  links.forEach(link => link.addEventListener('click', () => mark(link.hash.slice(1))));
  window.addEventListener('scroll', scheduleReadingPosition, {passive:true});
  window.addEventListener('resize', scheduleReadingPosition);
  window.addEventListener('hashchange', scheduleReadingPosition);
  scheduleReadingPosition();
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) entry.target.classList.add('is-visible');
    }, {threshold:.08});
    chapters.forEach(chapter => observer.observe(chapter));
  } else chapters.forEach(chapter => chapter.classList.add('is-visible'));
})();
