# Published report browser checks, 6 October 2026

Checked the [public report](https://adambkovacs.github.io/candidate-experience-benchmark/) in Chrome while the next report update was still being prepared. This check applies to the deployed page, not unpublished results.

- The main navigation exposes findings, results, prompt comparison, repeatability, reviews and method.
- With browser emulation set to `prefers-reduced-motion: reduce`, the page reports the preference as active and the root element's computed scroll behavior is `auto`.
- The resource-use section contains `usage-run-select`, labelled "Choose a run for resource use". Readers can select a run within that section.
- The browser reported no console errors during this check.
- Reduced-motion emulation was cleared afterward.

These are bounded checks. The browser's read-only DOM interface did not expose `document.getAnimations()`, so this check does not establish that every animation stops. Full keyboard navigation, visual focus, all responsive breakpoints and motion across every interactive chart remain to be checked. Earlier 390-by-844 viewport checks are recorded in [the checklist](TODO.md).
