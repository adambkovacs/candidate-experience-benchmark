/* Site shell behaviour shared by Read, Explore and Method: current-section mark, reading rail, header height,
   sticky table heads and deep links that hold their target while panels render. No decorative motion. */
(() => {
  const root = document.documentElement;
  const header = document.querySelector('.site-header');
  const links = [...document.querySelectorAll('.main-nav a[href^="#"]')];
  const sections = links.map(link => document.getElementById(link.hash.slice(1))).filter(Boolean);
  const rail = document.querySelector('.scroll-rail > span');

  // Sticky offsets read --reader-header-height (reader.js also sets it on Explore).
  const syncHeader = () => { if (header) root.style.setProperty('--reader-header-height', `${Math.ceil(header.getBoundingClientRect().height)}px`); };
  syncHeader();
  if (header && 'ResizeObserver' in window) new ResizeObserver(syncHeader).observe(header);

  let currentId = '';
  const mark = id => {
    if (id === currentId) return;
    currentId = id;
    links.forEach(link => {
      if (link.hash === `#${id}`) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  // The current chapter is the last linked section whose top passed 40% of the viewport, or the last section at
  // the end of the page. Computed from live positions, so anchor jumps and late panels never leave a stale mark.
  let queued = false;
  const update = () => {
    queued = false;
    const max = root.scrollHeight - innerHeight;
    if (rail) rail.style.setProperty('--read', max > 0 ? Math.min(1, scrollY / max).toFixed(4) : '0');
    if (!sections.length) return;
    const visible = sections.filter(section => section.offsetParent !== null);
    let current = sections[0];
    if (scrollY >= max - 2 && visible.length) current = visible[visible.length - 1];
    else for (const section of visible) if (section.getBoundingClientRect().top <= innerHeight * 0.4) current = section;
    mark(current.id);
  };
  const queue = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
  if (sections.length) mark(location.hash && sections.some(s => `#${s.id}` === location.hash) ? location.hash.slice(1) : sections[0].id);
  addEventListener('scroll', queue, {passive: true});
  addEventListener('resize', queue, {passive: true});
  addEventListener('load', () => { queue(); requestAnimationFrame(() => root.classList.add('is-loaded')); }, {once: true});
  queue();

  // Long tables get a sticky head. A panel wrapper that scrolls sideways would trap it, so a wrapper whose table
  // currently fits is opened up, and it scrolls again as soon as the table no longer fits.
  const scrolls = el => { const s = getComputedStyle(el); return /(auto|scroll|hidden)/.test(s.overflowX + s.overflowY); };
  const fits = el => el.scrollWidth <= el.clientWidth + 1 && el.scrollHeight <= el.clientHeight + 1 && getComputedStyle(el).maxHeight === 'none';
  const stickyHeads = () => {
    const reclip = [...document.querySelectorAll('.is-unclipped')].filter(el => !fits(el));
    const plan = [];
    for (const table of document.querySelectorAll('[data-surface="paper"] table')) {
      if (!table.tHead || table.offsetHeight < 560) continue;
      const open = [];
      let free = true;
      for (let el = table.parentElement; el && !el.matches('main > *'); el = el.parentElement) {
        if (!scrolls(el) || el.classList.contains('is-unclipped')) continue;
        if (fits(el)) open.push(el); else { free = false; break; }
      }
      plan.push({table, open, free});
    }
    reclip.forEach(el => { el.classList.remove('is-unclipped'); el.querySelectorAll('table.has-sticky-head').forEach(t => t.classList.remove('has-sticky-head')); });
    for (const {table, open, free} of plan) if (free) { open.forEach(el => el.classList.add('is-unclipped')); table.classList.add('has-sticky-head'); }
  };
  const main = document.getElementById('main');
  let settle = 0;
  const onLayout = () => { clearTimeout(settle); settle = setTimeout(() => { stickyHeads(); queue(); }, 250); };
  if (main && 'ResizeObserver' in window) new ResizeObserver(onLayout).observe(main);
  addEventListener('load', onLayout, {once: true});

  // Deep links: panels render after load and push the target down. Keep it in place until the reader scrolls,
  // taps or types, or for 12 seconds at most.
  let target = null;
  try { target = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch { target = null; }
  if (target && main && 'ResizeObserver' in window) {
    const inputs = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
    let timer = 0;
    const align = () => { clearTimeout(timer); timer = setTimeout(() => target.scrollIntoView({block: 'start', behavior: 'instant'}), 120); };
    const keeper = new ResizeObserver(align);
    const stop = () => { keeper.disconnect(); clearTimeout(timer); inputs.forEach(type => removeEventListener(type, stop, true)); };
    inputs.forEach(type => addEventListener(type, stop, {capture: true, passive: true}));
    keeper.observe(main);
    // The header settles its height once the web fonts load, which shifts everything below it.
    if (header) keeper.observe(header);
    setTimeout(stop, 12000);
  }
})();
