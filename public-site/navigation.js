(() => {
  const links = [...document.querySelectorAll('.main-nav a[href^="#"]')];
  const sections = links.map(link => document.getElementById(link.hash.slice(1))).filter(Boolean);
  if (!links.length || !sections.length) return;
  const mark = id => links.forEach(link => {
    if (link.hash === `#${id}`) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  if (location.hash && sections.some(section => `#${section.id}` === location.hash)) mark(location.hash.slice(1));
  else mark(sections[0].id);
  if (!('IntersectionObserver' in window)) return;
  const observer = new IntersectionObserver(entries => {
    const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
    if (visible.length) mark(visible[0].target.id);
  }, {rootMargin: '-100px 0px -60% 0px'});
  sections.forEach(section => observer.observe(section));
})();
