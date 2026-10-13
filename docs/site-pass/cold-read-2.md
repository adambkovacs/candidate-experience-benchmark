# Cold read 2 of the public site

A second visitor's pass over Read, Explore and Method at `feat/site-content-v2` b9287eb5, judged against Adam's three complaints ("tons of metacomments, not premium, doesn't feel like giving us info and benchmarks"), his rules in `docs/talk/00-adam-brief.md`, sections 5 and 6 of `docs/talk/13-deck-brief-review.md`, the presentation voice profile and anti-slop tiers 1 to 4. Read-only: no site file was changed. The working tree carried one uncommitted edit to `public-site/app.js` (4 lines) from another lane, so the captures show the tree as it stood, not the bare commit.

## What was captured

`public-site/` served with `serve()` from `public-site/deck/verify/lib.mjs`, headless Chromium, each page loaded, scrolled top to bottom so reveal and count-up observers fired, then waited until no "Loading…" or "Checking…" text remained. Text was extracted after every `details` element was opened.

| File | What it is |
|---|---|
| `docs/site-pass/cold2/<page>-1440-fold.png`, `<page>-390-fold.png` | First screen at 1440x900 and 390x844 |
| `docs/site-pass/cold2/<page>-<w>-full-N.png` | Full page in 7,000 px slices, disclosures as shipped |
| `docs/site-pass/cold2/<page>-<w>-open-N.png` | Full page with every disclosure open |
| `docs/site-pass/cold2/sections/*.png` | Every top-level block of `main` at 1440, one file each (Read and Explore) |
| `docs/site-pass/cold2/rendered-text.txt`, `rendered.json` | Rendered text per section, header, footer, title attributes, overflow probes |

| Page | Height at 1440 | Height at 390 | With every disclosure open, 1440 | Previous read, 1440 |
|---|---|---|---|---|
| Read | 15,062 | 22,142 | 18,270 | 15,532 |
| Explore | 57,541 | 71,933 | 266,990 | 33,532 |
| Method | 6,333 | 8,526 | 6,648 | 2,305 |

No console errors, no failed requests, no stuck placeholders, no horizontal page scroll at either width. The only console output is the SwiftShader WebGL "GPU stall due to ReadPixels" warning on Read, which is a headless GL diagnostic. Read now carries 0 `title` attributes (was 93) and 0 middle dots in visible prose (was 72). One capture artefact: in the full-page slices the fixed header is painted mid-page and the hero is faded, because the screenshot resizes the viewport; the fold shots show the real first screen.

## Verdict in one paragraph

Read is now a benchmark page. The fold leads with the score, the third block is a pass-by-pass table with cost, the hard reviews show the review text with every model's four answers, and the rule reads like a person talking. The two places it falls back are the "Five more findings" block, which is still a stat dump with instructions to the reader, and "What I'd do on Monday", which undoes Adam's own edit to the deck. Explore got the right top half (all results, per decision, stability, cost) and kept the entire old bottom half, so it grew from 33,532 px to 57,541 px and still contains checkpoints, smoke-test exclusions, 12-decimal costs, raw run ids and a broken scatter. Method went from thin to the best-written page on the site. Two cost contradictions survive in a new form, and one of them looks like a data error rather than a wording problem.

## 1. Per page verdict and scores

Scores are 1 to 10, higher is better: Benchmarks means "gives info and benchmarks first", Premium means "reads as premium", Adam means "reads as Adam, no metacomments".

| Page | Benchmarks | Premium | Adam |
|---|---|---|---|
| Read | 8 | 6 | 6 |
| Explore | 6 | 4 | 3 |
| Method | 7 | 7 | 7 |

**Read.** It does give the benchmarks first: the answer, the four questions with an example, then a table of every decision model and the best general models with all nine passes and the cost of a pass. The gap grids, the hard-review table and the rule section are clean and confident. It loses premium points on the "Five more findings" block, which drops into fine-print stat rows in a different visual system, and on costs printed to eight decimals in running prose. It loses Adam points because that block reads like a report generator, and because the Monday section is in first person under the heading Adam asked to change.
- Benchmarks 8: "Jev matched 54 of 60 reviews. The big general models matched 58 or 59." is the first thing on the screen, and the full table is two scrolls down.
- Premium 6: the block headed "Decision models answered most "insufficient information" cells with a definite label" sits in small grey rows directly under the polished rule section.
- Adam 6: "Treat insufficient information as its own detection task with its own recall; the four-field total hides this gap on exactly the reviews that need a person." is nobody's speaking voice.

**Explore.** The first five blocks are what a benchmark reader wants: every configuration with every pass, per-decision scores, stability, and cost per pass with a "Jev passes for the same money" column. After that the page repeats itself (a second ranking, a scatter, a run inspector, two more run pickers, a second review matrix, a story section, a how-it-works section) and ends in collapsed panels full of pipeline language. Model names in the main table are slugs such as `claude-opus-5-5` over `opus55-low-batch10`.
- Benchmarks 6: "All results" is the first block, but its rows read `claude-sonnet-5 / sonnet5-high-phase2-batch10-p0` and the cost column runs to `$0.034324790897`.
- Premium 4: the scatter in `#outcome-chart` draws its points as overlapping vertical ovals that spill over the top of the plot, and the page is 57,541 px long.
- Adam 3: "Known development cost is $0.030564226637; the unknown request has a separate upper bound of $0.06905856. Smoke costs are excluded."

**Method.** Short, factual and in plain sentences: the four questions with definitions, how a match is scored, the three prompts, which passes broke, the three disputed labels with their text, the launch wave as a table, what the study cost, and the correction log. It still lacks a model roster, the prompt text and the class balance of the key, and the cost section hedges reservations twice.
- Benchmarks 7: "252 configurations ran each prompt three times with fresh requests: 50 decision-model configurations and 202 general ones" is the pass design a reader asks for, stated once.
- Premium 7: clean type, five font sizes, no clutter, but no table or chart for the roster or the key.
- Adam 7: "Up to $3.88 more sits in reservations for requests whose id was never saved, mostly failed or interrupted calls. That is a ceiling on what we may owe, never a charge." is the one paragraph that slips back into price hedging.

## 2. Remaining metacomments, hedges, instructions, provenance artefacts and badges

Exact rendered text. No eyebrows, part marks, hover paths or dotted-underline numbers remain on any page. Items 1 to 22 are on Read, 23 to 52 on Explore and 53 to 56 on Method. Items 14 to 17 and 42 to 46 sit inside panels that are collapsed on load; everything else is visible without a click.

### Read (`index.html`)

1. `#overview` chart legend: "The ring is DEV-003, the review in the next section." The same kind of caption as "the orange point" that Adam struck.
2. `#gap`: "An Opus pass works out to $0.222052 at API rates, since Claude ran on a subscription." Price basis restated in prose; the leaderboard footnote already says it.
3. `#leaderboard` footnote: "Gemma and Qwen show their first P0 pass here; their repeats are in the full table on Explore." A pointer standing in for data the row should show.
4. `#hard-reviews` footnote: "The seven decision models are on their first pass with the base prompt; Jev is its direct P0 run." Route provenance a visitor cannot parse.
5. `#deep-insights`: "The analysis scripts reran every count over the saved answers. No model was called again."
6. `#deep-insights`: "The recount corrected 8 earlier statements. They are listed on the Method page."
7. `#deep-insights` headline with a hedge inside it: "On these 60 reviews, Jev's confidence is calibrated on average (expected calibration error 0.011) and still 0.96 on a wrong testimonial".
8. `#deep-insights` row label: "Jev expected calibration error on these 60 reviews (pooled provider confidence)".
9. `#deep-insights` instruction: "Treat insufficient information as its own detection task with its own recall; the four-field total hides this gap on exactly the reviews that need a person."
10. `#deep-insights` instruction: "Pick a second model that fails on different reviews; two strong models that share an answer set accept the same disputed answers together."
11. `#deep-insights` instruction: "Pick a pair for complementary failures and price, and budget for the deferred reviews; agreement still cannot catch a blind spot both models share."
12. `#deep-insights` instruction: "A decision model gives a fixed wrong list you can audit once; a general LLM gives a different wrong list each batch, so monitoring should count per-review flips, since totals can stay flat while answers change."
13. `#deep-insights` instruction: "If a vendor exposes two numbers, threshold on the option probability, and expect even the best-calibrated model to be confident about the wrong field on off-topic input."
14. `#deep-insights` collapsed "Three more patterns" instruction: "After a prompt change, regression-test the label distribution as well as the score."
15. `#deep-insights` collapsed instruction: "The thinking switch is model- and size-specific; test it per configuration instead of assuming more reasoning helps."
16. `#deep-insights` collapsed, with Adam's banned "gate": "The cheapest gate-clearing pass failed the insufficient-information gate when its configuration ran again", "Cheapest gate-clearing pass, all four fields", "Select a configuration only after the gate holds across three passes."
17. `#deep-insights` collapsed, old cost vocabulary: "Observed or known-charge frontier points 7 of 303".
18. `#deep-insights` pair explorer: "Both are decision models on their first pass with the base prompt. The charge is the provider charge for both runs." The fourth statement of cost basis on Read.
19. `#limits`: "Route, interface, batch size, effort and prompt differ across runs, so the order of scores is not an order of models." The old "so this is not a ranking" hedge, now sitting under a ranked table.
20. `#limits`: "Every number on this site describes these 60 reviews." and "a missing cost is unknown, never zero." Both repeat on Method.
21. `#next`: a "Sources and downloads" list of eleven raw file names (`findings.json`, `jev-native-prompt-findings.json`, `hard-cases.json` and eight more). Explore and Method each carry their own downloads block, so on Read it works as the source footer Adam removed.
22. `#rule` pair labels use run vocabulary in the pair explorer below it: "Qwen3.8 27B low effort (fp4) original + Gemma 4 26B thinking on fresh1", "DeepSeek V4.1 Flash low effort fresh1 + Gemma 4 26B thinking on fresh1".

### Explore (`explore.html`)

23. Footer: "Sixty fictional reviews, scored against a provisional reference." Read's footer dropped this; Explore kept it.
24. `#results` footnote: "A dash means the merged run feed holds no score for that pass. Some repeats sit only in per-family files, such as Sonnet 5.5, whose nine passes are on the Read page."
25. `#results` footnote: "178 configurations from 929 saved run-passes." The page header says "1,004 saved passes", `#report-lens` says 979 runs, `#run-ranking` says 242 setups, `#outcome-chart` says 381 runs. Five counts, no explanation.
26. `#results` row labels: raw slugs throughout, for example "claude-haiku-4-5-20251001 / haiku45-not_applicable-phase2-batch10-p0" and "deepseek-v4.1-flash / openrouter-paid-deepseek-v41-flash-high-authority-v3-current-price".
27. `#report-lens`: "979 closed saved runs in this view." and "637 more report-backed stages appear in the chart and the run list. Stage catalog".
28. `#outcome-chart`: "381 closed runs at 61 points; 25 partial runs excluded." and "Only complete 60-review runs are plotted. Partial runs keep their own status in the run inspector."
29. `#outcome-chart` side panel: "Run ID laya-english-expanded-cpu" and "Saved source ↗".
30. `#run-ranking`: "Costs are provider bills. A † marks the API-rate equivalent, shown for subscription routes and direct routes without a bill." The same table family uses "a" for the same thing in `#results`.
31. `#run-ranking` badge: "Jev, for comparison" in orange under the Jev row.
32. `#run-ranking`: "Complete means an answer saved for all 60 reviews; malformed answers count as misses. Partial runs are in the run inspector."
33. `#jev`: "The base-task run behind the six misses on the Read page. It matched 54 of 60 on its first pass, and this route has no bill. The same model through OpenRouter cost $0.00589092 a pass." followed by "API-rate estimate $0.00589092."
34. `#explore`: "A blank card means no saved result for that version." and "4 of 39 audited setups".
35. `#usage`: "Request time is what our client measured, network included; providers did not report inference time." Also on Method and Read.
36. `#cross-category`: "149 general-model first passes and the seven decision models on OpenRouter" with cohort options "Earlier first passes · 117 runs" and "Fresh first passes · 32 runs".
37. `#cohort-reviews`: "60 of 60 reviews shown. 39 distinct first-P0 configurations, 2340 run-review positions, 449 differ from the reference, 176 unusable." and "Comparison data (JSON) ↗".
38. `#reference-sensitivity`: "Here every saved answer is rescored against the alternative label for each, with no new model calls. Published scores keep the original labels." plus "Original labels: these are the published scores.", "No alternative label applied." and "Reference review ↗ · Dated proposal ↗ · Full findings ↗".
39. `#clef-first-pass`: "That route recorded no bill, so both costs are at the published API rate. The ranking's Clef 54 of 60 comes from a later pass through OpenRouter."
40. `#analysis-update`: "This extends the earlier review of 17 setups with 4 Sonnet effort settings." A changelog line.
41. `#analysis-update`: "Costs cover saved development requests, excluding smoke tests and unresolved possible charges. An interrupted run keeps missing answers in its 60-review score denominator; repeat changes compare only shared usable answers. Clef may read only the first part of a long policy; billed tokens do not prove…"
42. `#analysis-library`: "Clef native P0: At the P0 checkpoint, Clef had 3/9 planned runs scored" and "Latest Clef Flash P0 interruption: … Latest checkpoint."
43. `#analysis-library`: "DeepSeek high, original-control snapshot: This earlier report contains 2 runs from the 9-run plan. The later results appear above." and "DeepSeek high, first revised-price checkpoint: This earlier report contains 1 of the 7 phases then remaining".
44. `#analysis-library`: "Known development cost is $0.030564226637; the unknown request has a separate upper bound of $0.06905856. Smoke costs are excluded." and "Correct classifications on the usable answers do not erase those three failures."
45. `#analysis-library`: "Charge: $0.005084835; the five failed requests retain a separate unknown-charge bound. Partial P0 findings."
46. `#analysis-library`: "(unavailable reasoning tokens within output); 4631.1 seconds of client-observed request time" and "failed the frozen strict-JSON rule".
47. `#story`: "Jev matched 54 of the 60 comments against our draft answers in one historical TypeSafe API run." and "Separate fresh native OpenJev setups scored 52 to 54 out of 60; their routes and settings differ from this TypeSafe API run."
48. `#story`: "In this first recorded pass, we compared three prompt versions" and "lowered 21 scores in the audited comparison. A setup means a particular model, route and settings."
49. `#story` instructions: "Test added instructions on your own examples; more detail did not buy more matches here." and "Ask a vendor for repeat results and examples of changed answers; a three-point difference on one run can hide that variation."
50. `#story` captions: "Squares follow DEV-001 to DEV-060." and "Squares follow DEV-001 to DEV-060, left to right."
51. `#sources`: "AI wrote the 60 fictional comments and drafted the reference answers. A person checked all 60, and three labels are still disputed." The third copy on the site, plus "Jev source records ↗" and "Example prompt comparison report ↗".
52. Every run picker (`#inspect`, `#models`, `#usage`, `#reference-sensitivity`, `#outcome-chart`): raw ids joined by middle dots, for example "@cf/cloudflare/clef-flash · Cloudflare connected app · P0 · extended-cloudflare-clef-flash-direct-fresh2-p0". The `#inspect` review rows are summarised by id and status, "DEV-001 · matches reference".

### Method (`method.html`)

53. `#method`: "Every number on this site describes these 60 reviews and nothing wider."
54. `#study-cost`: "Up to $3.88 more sits in reservations for requests whose id was never saved, mostly failed or interrupted calls. That is a ceiling on what we may owe, never a charge."
55. `#study-cost`: "plus up to $0.1285 of unrecorded reservations."
56. `#study-cost`: "Every cost on this site is a provider charge, an API-rate equivalent, or unknown. A missing cost is unknown, never zero."

Count: 56 items, against 87 last time. Read went from 44 to 22, Method from 6 to 4, and Explore from 37 to 30, most of them in the collapsed lower half.

### Contradictions a visitor will notice

1. **Clef's cost looks wrong, not just mislabelled.** `#clef-first-pass` says Clef cost "$0.03184656 for the pass" on Cloudflare's direct route, "at the published API rate", and that the 54 of 60 "comes from a later pass through OpenRouter". The Read leaderboard and Explore `#cost-ledger` pair that same $0.03184656 with the OpenRouter 54 and call it "Provider charge". `#analysis-update` gives Clef's nine OpenRouter runs a $0.3113 charge, about $0.0346 a pass. Clef Flash shows the same pattern: $0.01194246 in the ledger against $0.1165 over nine OpenRouter runs. Someone should check the feed before anything is reworded.
2. **Jev's cost.** Read `#gap`, Explore `#cost-ledger` and Method call $0.00589092 the OpenRouter provider charge. Explore `#run-ranking` prints it on the `jev-1.13.0 / TypeSafe API` row with a † for "API-rate equivalent", and `#jev` says the TypeSafe route "has no bill" and then shows "API-rate estimate $0.00589092".
3. **Study cost.** Method `#study-cost` opens "The whole study cost $12.65 on OpenRouter." Method `#corrections` says "The study cost $1.2013 in known provider charges over 63 runs". The first means all runs and the second means the seven decision models, but neither sentence says so.
4. **A headline that doesn't match its rows.** In Read `#deep-insights`, the collapsed card is headed "Thinking hurt Qwen 1.7B in every pair and helped Qwen 4B in every pair". Its rows are "Qwen 1.7B pairs where thinking hurt 12 of 12", "Gemma E2B pairs where thinking helped 12 of 12" and "Qwen3.6 35B pairs where thinking helped 11 of 12". No row mentions Qwen 4B.

## 3. Sentences that still read like a report generator, with rewrites

| Page and section | As rendered | Rewrite |
|---|---|---|
| Read `#deep-insights` | "Decision models answered most "insufficient information" cells with a definite label" | "When a review gave them nothing to go on, decision models still picked an answer three times out of four. General models did it about one time in seven." |
| Read `#deep-insights` | "Treat insufficient information as its own detection task with its own recall; the four-field total hides this gap on exactly the reviews that need a person." | "So score can't-tell on its own. The four-answer total hides this miss on exactly the reviews a person should see." |
| Read `#deep-insights` | "The strongest runs often return identical answer sets" with five stat rows | "The best runs make the same mistakes. Of the 373 runs that matched 57 or more, 44 gave the exact same answers, and those 44 came from seven different model families." |
| Read `#deep-insights` | "DeepSeek V4.1 Flash low effort fresh1 + Gemma 4 26B thinking on fresh1 accepted, with 0 errors" | "DeepSeek V4.1 Flash and Gemma 4 26B, two cheap general models, accepted 57 with no errors for $0.037, the same money Solar and Perplexity spent to accept 53." |
| Read `#deep-insights` | "Charged pairs with no accepted errors that accept more reviews than Solar + Perplexity at a lower charge 23 of 853" | "23 of the 853 paid pairs beat Solar and Perplexity for less money, with no errors let through." |
| Read `#deep-insights` | "A decision model gives a fixed wrong list you can audit once; a general LLM gives a different wrong list each batch, so monitoring should count per-review flips, since totals can stay flat while answers change." | "A decision model gets the same reviews wrong every time, so you check its mistakes once. A general model gets different ones wrong on each run, and the total can stay flat while the answers move underneath it." |
| Read `#deep-insights` | "If a vendor exposes two numbers, threshold on the option probability, and expect even the best-calibrated model to be confident about the wrong field on off-topic input." | "Clef Flash reports a confidence and an option probability, and on more than half its answers they disagree by over 0.2. Jev, the best calibrated model here, was still 0.91 sure on the soup review." |
| Read `#deep-insights` | "The cheapest gate-clearing pass failed the insufficient-information gate when its configuration ran again" | "The cheapest run that matched 54, DeepSeek V4.1 Flash at about a quarter of a cent, matched 48 when we ran it again." |
| Read `#deep-insights` | "Thinking hurt Qwen 1.7B in every pair and helped Qwen 4B in every pair" | "Turning thinking on made Qwen 1.7B worse in all 12 comparisons and made Gemma E2B better in all 12." |
| Read `#gap` | "A Jev pass over all 60 reviews cost $0.00589092 on OpenRouter. An Opus pass works out to $0.222052 at API rates, since Claude ran on a subscription." | "A Jev pass over all 60 reviews cost six tenths of a cent. An Opus pass costs 22 cents at API prices." (Adam's own line from the deck review, S8.) |
| Read `#hard-reviews` | "The seven decision models are on their first pass with the base prompt; Jev is its direct P0 run." | "Every model here is on its first pass with the plain prompt." |
| Read `#team` | "What I'd do on Monday" / "I'd pull 60 of my own cases and label them myself, before any model sees them." | "What should you do" / "Pull 60 of your own cases and label them yourself before any model sees them." Adam changed this exact heading on the deck. |
| Read `#limits` | "Route, interface, batch size, effort and prompt differ across runs, so the order of scores is not an order of models." | "Each row is one setup: the model plus its route, effort and prompt. Change any of those and the score can move." |
| Explore `#results` | "A dash means the merged run feed holds no score for that pass. Some repeats sit only in per-family files, such as Sonnet 5.5, whose nine passes are on the Read page." | "A dash means we didn't run that pass." Then put Sonnet 5.5's nine passes in the table. |
| Explore `#report-lens` | "979 closed saved runs in this view. 637 more report-backed stages appear in the chart and the run list." | Cut both lines. The filter buttons explain themselves. |
| Explore `#analysis-update` | "Across these 21 Claude setups, neither longer prompt improved the all-four score in every pass for any setup. This extends the earlier review of 17 setups with 4 Sonnet effort settings." | "We ran 21 Claude setups. Neither longer prompt raised the score on every pass for any of them." |
| Explore `#analysis-library` | "Known development cost is $0.030564226637; the unknown request has a separate upper bound of $0.06905856. Smoke costs are excluded." | "This pass cost about three cents. One request failed, so its cost is unknown." |
| Explore `#story` | "Jev matched 54 of the 60 comments against our draft answers in one historical TypeSafe API run. It is a specialist decision model, tested through native Choice questions rather than a chat prompt." | "On TypeSafe's own API, Jev matched 54 of 60, the same score as its first pass through OpenRouter." |
| Explore `#run-ranking` | "One row per setup, with its passes side by side, for example 3 passes: 54, 53, 52." | "One row per setup, best pass first." Or cut the block, since `#results` already ranks every setup. |
| Method `#study-cost` | "Up to $3.88 more sits in reservations for requests whose id was never saved, mostly failed or interrupted calls. That is a ceiling on what we may owe, never a charge." | "Failed calls may add up to $3.88 more." |

## 4. What a benchmark reader wants and still can't find within two scrolls

1. **The cheapest strong result.** In Explore `#cost-ledger`, DeepSeek V4.1 Flash with thinking off matched 54, Jev's score, for $0.00268, which is half a Jev pass. Gemma 4 26B matched 59 for 3.6 Jev passes. Read's hero says only that general models "cost 3.6 to 37.7 times as much per pass", and DeepSeek and Gemini are missing from the Read leaderboard. A reader who finds the ledger later will feel the hero picked its comparison. Add DeepSeek Flash and Gemini 3.1 Pro rows to Read `#leaderboard` and give the hero one sentence on it.
2. **Cost against accuracy in one picture.** There is still no chart of cost per pass against all-four matches. `#outcome-chart` plots valid answers against matches, where almost every point sits at 59 to 60 valid. Rebuild `#outcome-chart` as cost on a log axis against matches, keeping its ids, and put a small version under Read `#leaderboard`.
3. **Every pass for the general models on Read.** The Read leaderboard shows Gemma and Qwen as "59 – –". The hero leans on that 59, but Explore has Gemma's P0 passes as 59, 56 and 58. Show all three in the Read row.
4. **General models on the hard reviews.** Read `#hard-reviews` shows eight decision-model columns. The only general-model number is "89 of 113 general configurations matched it" on the soup review. Add Opus, Sonnet and Gemma columns there.
5. **Readable model names on Explore.** `#results`, `#run-ranking` and every picker label models by slug. Use the Read names ("Opus 5.5, high effort") with the slug in a second line or a tooltip.
6. **The prompt text.** P0, P1 and P2 are described in one line each on all three pages, but the prompts themselves are not on the site. Put them in Method `#method` under "Three prompts", or link the files.
7. **The class balance of the key.** How many reviews are positive, need a follow-up, report a serious concern (25) or would work as a testimonial (9) appears only in passing. Add a one-row table to Method `#method` under "The four questions".
8. **A model roster with type, maker, route and effort.** It exists only as two prose lists inside Read `#leaderboard`. Put a table in Method `#method`.
9. **How to get classification-bench.** Read `#next` and Method `#harness` say what it does but give no link, repository or contact. Add one line saying where it lives.

## 5. Visual defects in the captures

1. **Explore `#outcome-chart`** (`sections/explore-06-outcome-chart.png`). Points render as vertical ovals, so the SVG is stretched. They pile on top of each other at 59 to 60 valid, spill above the top edge of the plot, and cover the "0" and "30" axis ticks. The count label near x=32 is half hidden. The default selection is still Laya at 0 of 60, and the side panel's select cuts off "laya-english-expande".
2. **Cost precision.** One site, five precisions: $0.022067, $0.0133523, $0.03184656, $0.016342872 and $0.034324790897. The same Read page prints the Solar and Perplexity pair as $0.03749436 in `#rule` and $0.03749 in `#deep-insights`. Pick one rule, for example three significant figures, everywhere.
3. **Thousands separators.** Explore `#decision-matrix` and `#stability` print 1551, 4648 and 2156. Read prints 1,239 and 2,156.
4. **Read `#leaderboard` order and marks.** The decision rows are not sorted: Jev at 54 sits below Liquid d1 at 43. Solar's and Clef Flash's last P2 cells carry a superscript "i" that the footnote never explains (Explore's footnote does). Gemma and Qwen rows read "59 – –".
5. **Read `#team`** (`sections/index-08-team.png`). The subtitle "Four steps, and none of them needs a big budget." is almost the background colour. Each step is numbered twice, "01" and "1.".
6. **Read `#controls`.** The "Unchanged 14" segment is dark slate on a dark card and nearly disappears. Jev's calibration bar is a single dot, which reads as a missing bar.
7. **Read `#deep-insights` calibration chart.** The Clef Flash points are large grey discs that overlap each other along the top. The dashed diagonal that shows perfect calibration is partly hidden behind them.
8. **Header alignment in Explore tables.** Column headers are left-aligned over right-aligned numbers. In `#decision-matrix` the "Testimonial" header sits about 150 px left of its column, and `#cost-ledger` and `#stability` do the same.
9. **Theme split.** Read is dark navy. Explore and Method are light paper under the same header. This may be intended, but moving from Read to Explore feels like a different site.
10. **Read hero lattice.** The 60 dots are deliberately jittered, so at 1440 px the grid looks misaligned rather than designed.
11. **Explore length.** 57,541 px with disclosures as shipped and 266,990 px with them open. The nav has eight items, and five of them point into the first 12,000 px.

No clipping or horizontal page scroll was found at 390. Wide tables scroll inside their wrappers. I did not check each mobile table for a visible scroll cue.

## 6. The previous cold read's REWRITE, MERGE and CUT list

| # | Section | Previous verdict | Now | Note |
|---|---|---|---|---|
| R1 | Read `#overview` | REWRITE | DONE | Setup in the lede, "create a rule", no kicker, sources line or hover instruction. The ring caption remains (item 1). |
| R3 | Read `#gap` | REWRITE | DONE | No "not a ranking". Cost said once, though to eight decimals. |
| R4 | Read `#hard-reviews` | REWRITE | DONE | Seven reviews, each with its text, the key and eight models' four answers. |
| R5 | Read `#controls` | REWRITE | DONE | No "gate", and the calibration gap is defined in a sentence. |
| R6 | Read `#rule` | REWRITE | DONE | "Known charge", "observed", "pass-sensitive" and the queue sentence are gone. |
| R7 | Read `#deep-insights` | MERGE | STILL THERE | Still its own block, "Five more findings from 1,004 run-passes", with recount notes and instructions. Only the corrections log moved to Method. |
| R8 | Read `#limits` | MERGE | DONE | Three lines under "About this test". One hedge remains (item 19). |
| R9 | Read `#team` | REWRITE | PARTLY | Adam's four steps are used, but in first person under "What I'd do on Monday", the heading he changed to "What should you do". |
| E2 | Explore `#how-it-works` | MERGE | STILL THERE | Moved to the bottom of the page, still its own section. |
| E3 | Explore `#scores` | MERGE | STILL THERE | One line, still its own section at the bottom. |
| E4 | Explore `#report-lens` | REWRITE | STILL THERE | Still a section, with "979 closed saved runs" and "report-backed stages". |
| E5 | Explore `#outcome-chart` | REWRITE | STILL THERE | Still valid against matches, still defaults to Laya at 0, and now draws ovals. |
| E6 | Explore `#run-ranking` | REWRITE | DONE | The new `#results` table is the leaderboard. `#run-ranking` survives as a second ranking with slugs and † labels. |
| E7 | Explore `#inspect` | REWRITE | STILL THERE | Raw-id picker over every run. Review rows summarised as "DEV-0xx · matches reference". |
| E8 | Explore `#jev` | MERGE | STILL THERE | Still a separate block, and it now contradicts itself on cost (item 33). |
| E9 | Explore `#models` | MERGE | STILL THERE | Second comparison tool next to the inspector. |
| E11 | Explore `#usage` | MERGE | STILL THERE | Third run picker. |
| E12 | Explore `#cross-category` | REWRITE | PARTLY | Decision-against-general per decision now lives in `#decision-matrix`. `#cross-category` is still a pair picker with cohorts. |
| E13 | Explore `#cohort-reviews` | MERGE | STILL THERE | Sits beside `#hard-matrix` and `#review-evidence`, three views of the same 60 reviews. |
| E16 | Explore `#reference-sensitivity` | MERGE | STILL THERE | Its default run, a 3 of 60 local model, still shows "0 under the alternative key". |
| E17 | Explore `#clef-first-pass` | MERGE | STILL THERE | Still a vendor panel, and the source of contradiction 1. |
| E18 | Explore `#analysis-update` | MERGE | STILL THERE | The eyebrow is gone. The changelog content and the "extends the earlier review" line remain. |
| E19 | Explore `#analysis-library` | REWRITE | DONE | Cost, per-decision and stability are now top-level blocks. The library stays collapsed with old copy (items 42 to 46). |
| E20 | Explore `#story` | MERGE | STILL THERE | Three chapters with "historical TypeSafe API run" and "audited comparison". |
| E21 | Explore `#sources` | CUT | DONE | Replaced by a Downloads list. One disclaimer sentence remains. |
| M1 | Method `#method` | REWRITE | PARTLY | Now complete on questions, scoring, prompts and passes. Roster, prompt text and class balance are still missing. |
| M3 | Method `#harness` | REWRITE | DONE | Says what it does, with no "being open-sourced". No link. |

Totals: 10 DONE, 3 PARTLY, 14 STILL THERE, out of 27. All seven part marks are gone. Of the four contradictions in the previous read, Solar Decide is fixed and Jev's route is now explained on Method. Jev's cost and Clef's cost are still there, and Clef's now looks like a data error (contradiction 1 above).

## What would move the scores most

1. Delete or collapse Explore from `#report-lens` down to `#story`, keeping `#inspect` once, `#hard-matrix`, `#agreement-policy` and `#reference-sensitivity`. Fix `#outcome-chart` as cost against matches. That one cut takes care of about 20 of the 30 Explore items.
2. Rewrite Read `#deep-insights` as four findings in sentences, using the rewrites in section 3, with no stat rows and no instructions. Rename Monday to "What should you do" in second person.
3. Check the Clef and Clef Flash costs against the feed, then apply one price precision and one footnote mark across all three pages.
