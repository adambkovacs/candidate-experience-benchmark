# Site content pass: writer charter (2026-10-12)

Three writer lanes work in parallel in /Users/adamkovacs/lanes/cxb-talk on branch feat/site-content-v2 (base ffb9305a). Each lane owns a disjoint set of files and never touches another lane's files. Nobody commits; the lead commits by path when all three report. Never run git except plain `git log`, `git diff --stat` and `git ls-files`; never checkout, stash, rebase or reset.

## Adam's verdict and bar

After presenting from the deck, Adam read the site and said: "I'm not convinced by the website content, tons of metacomments, not premium, doesn't feel like giving us info and benchmarks." His rules from the deck apply to the site (docs/talk/00-adam-brief.md verbatim; docs/talk/13-deck-brief-review.md sections 5 and 6; docs/talk/14-phrases.md for phrases to reuse):

- No visible source footers, feed paths, "computed by" lines, or hover hints that tell the reader which file a number came from. Keep the invisible data-source attributes for the audits.
- No eyebrow kickers, part marks, breadcrumb labels, SOLID / DESCRIPTIVE ONLY badges, pills or chips as decoration.
- No repeated hedges. "Fictional", "provisional reference", "same 60 reviews", "not a ranking", "descriptive only" are each said once per page, in one honest "About this test" block, never per section.
- No instructions to the reader ("hover a number", "choose a run below", "use the linked run notes"). Show the thing.
- No price hedging ("estimate, provider charge unavailable", "known charge"). State the cost once with the basis in a column header or a footnote at page end.
- Full sentences in Adam's voice that carry the point and the number. Setup before results. Every chart and table labelled. Question with every answer. Treat the reader as an adult.
- Anti-slop tiers 1 to 4 (/Users/adamkovacs/.claude/skills/anti-slop/SKILL.md) and the adam-voice presentation profile (/Users/adamkovacs/.claude/skills/adam-voice/references/profile-adam-presentation.md). No em dashes, no curly quotes, no "not X but Y", no rule-of-three flourishes, no "Implication:" asides.

## The audits (read all four before editing)

- docs/site-pass/voice.md: every metacomment with page, section id, text, type and action; the ten worst sentences with rewrites; appendix-hedges.md lists 68 hedge sentences.
- docs/site-pass/design-audit.md: 32 findings, the token set, component treatments, the delete list, which fixes are CSS-only. Captures in docs/site-pass/design/.
- docs/site-pass/info-gap.md: 30 items PRESENT / BURIED / MISSING, the exact numbers and feed paths, the five panels to add, the number mismatches to fix.
- docs/site-pass/cold-read.md: section-by-section verdicts and the proposed page outlines (lands shortly after launch; read it when it exists, do not wait for it to start).

## Information architecture (the lead's ruling)

Three pages stay. Every existing element id stays reachable (public-site/site/LINK-MAP.md); an id may move within a page or to a different page only if the shim in index.html and LINK-MAP.md are updated in the same change.

- Read (index.html): the answer in one paragraph that says what Jev is and what we did; the four decisions; the leaderboard (compact: the seven decision models, Jev, and the best general models, matched of 60 per prompt stage, cost per pass); the three findings with their charts; the twelve hard reviews as a matrix; the rule (agree or defer) with the real split 7 / 24 / 4 and 25 accepted; what to do; one "About this test" block (fictional reviews, AI-drafted reference checked by a person, three disputed labels, not a ranking, descriptive on these 60); Sources and downloads list at the end (one list, all feeds, the repo, the harness).
- Explore (explore.html): the full results table first (every configuration: model, route, effort, prompt stage, pass, matched of 60, the four per-decision scores, cost of the pass, with filters), then per-decision accuracy matrix, repeatability, prompt levels, the 21 pairs, calibration, then the existing inspectors (run inspector, review evidence, cohorts, cross-category, reference sensitivity) each with a real heading and one sentence of purpose, no caveat blocks. The 60-row review list becomes a table or a matrix, never 60 collapsed rows.
- Method (method.html): the four questions with the labelling guide, how matched is scored, how many passes and which were interrupted, the disputed labels, the launch wave of decision models (dates and vendors from deck/data/timeline.json, verified entries only), the cost of the whole study ($12.65 on OpenRouter over 15,135 saved generations plus up to $3.88 of reservations; seven-model series $1.2013 plus up to $0.13), and the Sources and downloads list.

## Lane W1: site-pages (opus)

Owns: public-site/index.html, explore.html, method.html, deep-insights-section.html, deep-insights.js, site/hero.js, site/motion.js, site/navigation (if any), new files public-site/site/benchmarks.js and public-site/site/benchmarks.css, and the tests that assert page HTML (tests/test_report_navigation_ui.cjs html checks, tests/test_reader_story.py, tests/test_presentation_ui.cjs only if the shim changes). Builds the five new panels from info-gap.md section "Five panels" with the feeds named there (data.json runs, extended-run-catalog-v1.json, supplemental-decision-runs-v1.json, disputed-reviews-v1.json, deck/data/prompt-levels.json, deck/data/hard-cases.json, deck/data/timeline.json, deep-insights-v1.json, jev-confidence-findings.json, native-agreement-policy-v1.json). Every number rendered from a feed carries data-source. Rewrites all page prose per the voice report. Removes eyebrows, part marks, source lines, badges, hover-instruction sentences from the HTML (not only by CSS). Hero settles under two seconds (design finding 7). Keeps class names the CSS lane restyles; new components use class names prefixed `bm-` and are styled only in site/benchmarks.css. Uses the tokens from design-audit.md in benchmarks.css (do not redefine them; W2 defines them in site/site.css; if a token is missing at your runtime, use the literal value and note it).

## Lane W2: site-css (opus)

Owns: public-site/site/site.css, site/read.css, styles.css, reader.css, presentation.css, deep-insights.css, and the ten panel stylesheets (agreement-policy.css, clef-first-pass.css, clef-repeat-chart.css, cohort-reviews.css, cross-category.css, disputed-reviews.css, extended-cases.css, liquid-prompt-chart.css, outcome-chart.css, reference-sensitivity.css). No HTML, no JS. Applies design-audit.md: the token block in site.css, one type scale with a 13px floor (12px mono ticks only), two meaning colours (blue, orange) plus neutrals, the ladder only in the header rail and the logo, Explore as one continuous paper canvas, no offset shadows, no plate rails, table spec, chart frame spec, stat tile spec, callout spec, hard-review card spec, nav spec, mobile. Hides `.eyebrow`, `.part-mark`, `.source-line`, badges and `.num` dotted underlines by CSS as a safety net even though W1 removes them from the HTML. Keeps every existing selector working (W3 and W1 do not rename classes). Checks contrast on every text and background pair you set (4.5:1).

## Lane W3: panel-copy (opus)

Owns the panel JS modules and their UI tests: public-site/app.js, repeats.js, extended-cases.js, disputed-reviews.js, analysis-refresh.js, model-categories.js, agreement-policy.js, reference-sensitivity.js, outcome-chart.js, cohort-reviews.js, cross-category.js, findings.js, reader.js, jev-prompts.js, kev-prompts.js, clef-repeat-chart.js, liquid-prompt-chart.js, report-navigation.js, navigation.js, and tests/test_*_ui.cjs for those modules (not the ones W1 owns). No HTML, no CSS, no JSON feeds, no deep-insights.js. Task: every string these modules render is rewritten per voice.md: delete "Result status", "observational", "same 60 reviews", "provisional", "descriptive only", "estimate; provider charge unavailable" repetitions and every instruction to the reader; delete the per-panel caveat blocks (render nothing, or one sentence that carries a fact); turn "Loading…" headings into real headings; value labels instead of snake_case keys (design finding 14); the Jev cost label reads the same everywhere (known charge on OpenRouter; the TypeSafe direct route has no bill, say so once on Method, not per row); Clef first pass says it is a different route from the ranking's 54. Logic, data loading, ids and class names do not change. For every copy change that a test pins by regex, update the test in the same lane and keep the test's intent (it still checks the panel renders the right data). Run `node --test tests/<file>` for each touched test and `node --check` for each touched module.

## Verification before reporting (every lane)

- Serve public-site over HTTP (the static server in deck/verify/lib.mjs works in the sandbox) and load all three pages in Playwright: zero console errors, zero failed requests, no horizontal overflow at 390px.
- W1 and W3: node --check on every touched JS file; node --test on every touched test; python3 scripts/build_reader_story.py --check must still pass (W1).
- Rendered-text grep after scripts settle: "Hover", "provisional", "Sources", "Computed by", "SOLID", "DESCRIPTIVE", "estimate", "same 60", "Implication" each at most once per page (W1 and W3 share this target; report your own files' contribution).
- Final message: files changed (git diff --stat), what you did not finish, the verification output lines, and three screenshot paths (page fold at 1440, one new panel, one mobile fold) under docs/site-pass/<lane>/.

Hard stop: 75 minutes after launch. Report what is verified.
