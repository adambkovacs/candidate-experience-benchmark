# Benchmark information gap audit

Date: 2026-10-13. Branch feat/site-content-v2 at ffb9305a. Read-only pass. Nothing was edited except this file, nothing was committed.

Method: rendered index.html, explore.html and method.html with Playwright (public-site/deck/verify/lib.mjs server), dumped the text of every section including closed details elements, then read the JS that renders each panel (app.js, deep-insights.js, disputed-reviews.js, cohort-reviews.js, analysis-refresh.js, jev-prompts.js, repeats.js). Feeds were opened with Python and compared with docs/talk/01, 01b, 06, 14 and docs/FINDINGS.md. The rendered dumps show the default state of every picker. Picker contents beyond the default were read from the feeds, not clicked through.

Ratings: PRESENT means visible in plain page text or a table at default state. BURIED means the information exists but only behind a picker, a closed details element, a click-through, or one sentence of a caveat paragraph. MISSING means not on the three pages (it may live in a docs file, a feed or the deck).

## Headline

- Of 30 sub-items: 14 PRESENT, 13 BURIED, 3 MISSING.
- The three MISSING items: a single all-results table, the whole-study cost, the decision-model launch wave.
- The site has the analysis. It does not have the reference table a benchmark reader looks for first. Every score table is one prompt, one pass or one picked run at a time.
- The site and README state "It is not a leaderboard" (index #limits). A scoreboard panel needs to keep that claim and add comparability columns so the framing holds. See the five panels at the end.
- One real number conflict on the site (Jev route and cost label), one softer conflict (Clef 53 vs 54). Details under Mismatches.

## Counts by item

| # | Item | Rating | Where |
|---|---|---|---|
| 1a | One table, every configuration, P0/P1/P2 and fresh passes | MISSING | nowhere |
| 1b | Ranking of runs by matched-of-60 | BURIED | explore #run-ranking |
| 1c | 3x3 grid of prompt by fresh pass | PRESENT for 3 setups only | index #gap |
| 1d | Cost of a pass beside the score | BURIED | explore #run-ranking row text, #usage picker |
| 2a | Per-decision accuracy, Jev | PRESENT | explore #jev-analysis |
| 2b | Per-decision accuracy, every other model | BURIED | #inspect, #models, #cross-category details |
| 3a | Six Jev misses with text, key, answers | BURIED | explore #jev-analysis, #inspect |
| 3b-i | Six reviews that split the seven decision models | PRESENT | index #hard-reviews |
| 3b-ii | Their text, key, and all model answers | BURIED | explore #review-evidence, one review at a time |
| 4a | Groups with no changed answer, decision vs general | PRESENT | index #deep-insights |
| 4b | P1 to P2 moves, 4 / 14 / 21 of 39 | PRESENT | index #controls, explore #story |
| 4c | Changed reviews per model across passes | BURIED | explore #repeat-analysis picker |
| 5a | Cost per pass per model | BURIED | #run-ranking, #usage, #cost-analysis (24 API runs only) |
| 5b | Pair costs | PRESENT | index #rule, explore #agreement-policy |
| 5c | Whole study cost | MISSING | nowhere |
| 6a | ECE 0.011 vs 0.358 | PRESENT | index #controls, #deep-insights |
| 6b | 0.9 cutoff keeps 54 of 60 | BURIED | one sentence in explore #jev-analysis |
| 7a | 35 of 60 routed, 25 accepted | PRESENT | index #rule, #deep-insights |
| 7b | 21 pairs, five with zero errors | PRESENT | explore #agreement-policy |
| 8 | Soup review DEV-029 | PRESENT | index #hard-reviews |
| 9 | Launch wave | MISSING | deck/data/timeline.json only |
| 10a | The four questions | PRESENT | index #decisions |
| 10b | Labelling guide | BURIED | rubric link inside a closed details |
| 10c | How matched is scored | PRESENT | index #decisions, method |
| 10d | How many passes | BURIED | no stated total |
| 10e | Which passes were interrupted | BURIED | closed details in explore |
| 10f | Disputed labels | PRESENT | index #limits, method #findings |
| 11a | Raw answers download | BURIED | one GitHub link in index #next |
| 11b | Feed downloads | BURIED | about 20 inline links, no list |
| 11c | Harness | PRESENT | "being open-sourced, ask Adam" |

## Item detail

### 1. Leaderboard

What the reader expects: one row per model and configuration, matched-of-60 for P0, P1, P2 and each fresh pass, plus cost of a pass.

- Feeds that hold it. public-site/data.json runs[] (290 original run-passes), extended-run-catalog-v1.json runs[] (637 repeat and continuation stages), supplemental-decision-runs-v1.json runs[] (63 native decision stages). Each run has model, effort, surface, condition (P0/P1/P2), repeatPass, valid, metrics.all_four and the four field scores, cost.{actualUsd, knownUsd, estimatedUsd, unknownUpperBoundUsd}. Together with additional-cases-v1.json and extended-cases-v1.json they give the 1,004 run-passes. docs/talk/scripts/common.py already loads and self-checks them.
- Numbers the table would carry: 1,004 run-passes. 252 configurations with exactly three passes (50 decision, 202 general), 241 clean. 163 roster setups. 290 + 637 + 63 rows before the dedupe the scripts apply.
- On the site. explore #run-ranking filters one prompt version at a time (P0 by default), one category at a time (decision models by default), and shows eight rows with a "Show all complete runs" button. Default text reads "8 of 54 complete Dedicated classification / decision model P0 runs shown". Cost is a small grey line per row. There is no P1 or P2 column and no pass column.
- Per-pass grid: only index #gap, for Jev, Opus 5.5 high and Sonnet 5.5 xhigh (3 of 252 configurations). Other families are in explore #repeat-analysis behind a family picker.
- Exact figures for the seven native decision models, first pass P0 (from supplemental-decision-runs-v1.json), all four / sentiment / follow-up / concern / testimonial, known charge:

| Model | All four | Sent | Follow | Concern | Testim | Known charge |
|---|---|---|---|---|---|---|
| Solar Decide | 55 | 56 | 58 | 57 | 58 | $0.022067 |
| Clef | 54 | 56 | 59 | 56 | 58 | $0.03184656 |
| Perplexity Decider | 54 | 59 | 58 | 57 | 59 | $0.01542736 |
| Luna Decisions | 49 | 54 | 58 | 56 | 56 | $0.0133523 |
| Clef Flash | 45 | 50 | 57 | 56 | 57 | $0.01194246 |
| Tev 1 4B | 45 | 51 | 57 | 56 | 56 | $0.016342872 |
| Liquid d1 | 43 | 49 | 55 | 57 | 58 | $0.01568912 |
| Jev (TypeSafe direct P0) | 54 | 56 | 58 | 57 | 58 | $0.00589092 |

- Three-pass prompt grids already in the repo: deck/data/prompt-levels.json (Clef 54/54/54, 51/51/51, 49/49/49; Luna 49, 51, 49; Clef Flash 45, 47, 46 with one 45; Solar 55/53/54, 53/52/51, 53/52/52; Jev 54/53/52, 54/53/54, 54/null/54), Opus 5.5 high 59/58/58, 59/59/58, 59/58/58 (claude-roster-repeats.json, checked), Sonnet 5.5 xhigh 58 in all nine cells (sonnet55-fresh-matched3.json).
- Rating: MISSING as a single table. The ranking is BURIED. Only the 3x3 grids for three setups are PRESENT.

### 2. Per-decision accuracy per model

- Feed fields: runs[].metrics.sentiment, follow_up_needed, serious_concern_reported, testimonial_potential, all_four in the three run feeds.
- On the site. Jev's disagreement counts by decision (4 sentiment, 2 follow-up, 3 concern, 2 testimonial, 11 total in six reviews) are plain text in explore #jev-analysis. Clef and Clef Flash have a four-field block in #clef-first-pass. Every other model needs the run inspector picker, the Model comparison picker, or the "Field matches and confusion tables" details in #cross-category (shows General 37/60 vs Native 49/60 on sentiment, 54 vs 55 on follow-up, 13 vs 57 on concern, 9 vs 58 on testimonial for the picked pair only).
- The cross-model finding hiding here, worth a column: concern and testimonial are where general and decision runs differ most, as in the 13 vs 57 and 9 vs 58 split above and the insufficient-information gap (decision follow-up definite answer on 132 of 176 reference-insufficient cells, general on 105 of 776).

### 3. The hard reviews

- Feeds: disputed-reviews-v1.json reviews[] (text, reference, seven model answers, mismatch counts, SHA-256), deck/data/hard-cases.json (0 to 7 histogram and the six with 4 or more mismatches), cross-category-v1.json (cases and 149 general passes), deep-insights-v1.json hardest_reviews.
- Six that split four or more of the seven decision models, with counts: DEV-029 7, DEV-030 7, DEV-006 6, DEV-013 5, DEV-027 4, DEV-056 4. Three carry disputed labels (006, 013, 030). Five of Jev's six misses sit in this set. Jev's sixth miss is DEV-059.
- Index #hard-reviews shows the six as chips (id, count, tag) and prints text only for the soup. The other five texts are in index #deep-insights ("ten hardest", ranked by 1,004 run-passes, a different ranking) and in explore #review-evidence as a 60-row list.
- The key and the seven answers appear only for the selected review in #review-evidence (default DEV-029). Jev is not among the seven, so Jev's answer on each of the six needs the inspector.
- Rating: 3b-i PRESENT. 3a and 3b-ii BURIED.

### 4. Repeatability

- Numbers. Decision models 31 of 50 three-pass groups changed no answer. General models 11 of 202. Total 42 of 252. Distribution of unstable reviews per configuration: 0 reviews 42, 1 to 2 68, 3 to 5 88, 6 to 10 29, 11 to 20 15, 21 to 56 10. 27 configurations kept the same all-four total in all three passes and still changed answers. 8 of the 10 most-flipped reviews are among the 10 hardest.
- Wording point for the brief: 31 of 50 and 11 of 202 count groups that did NOT change. The brief for this audit phrases them as groups that changed. The site is right, the brief is inverted.
- P1 to P2 over 39 audited setups: 4 higher, 14 unchanged, 21 lower. P0 to P1: 15, 15, 9. P0 to P2: 7, 16, 16 (deck/data/prompt-levels.json tally). Per-triplet view on index #deep-insights: 127 worse, 78 better of 299.
- Feed: deep-insights-v1.json determinism, findings.json, data.json promptComparisons[] (53). Per-config changed counts: repeats.json, claude-roster-repeats.json and the other per-family *-repeats.json files.
- Rating: 4a and 4b PRESENT. 4c BURIED.

### 5. Cost

- Per pass per model. Seven decision models $0.01194246 to $0.03184656. Jev $0.00589092 (known via OpenRouter, an estimate on the TypeSafe direct route). Gemma 4 26B thinking-on $0.02114858 observed. Qwen3.8 27B low $0.0492372 observed. Opus 5.5 high $0.222052 API-equivalent estimate. Gemini 3.1 Pro low $0.063458, high $0.256826. DeepSeek V4.1 Flash off $0.00268114.
- Pairs on the site. Solar + Perplexity $0.03749436 and Qwen3.8 27B low + Gemma 4 26B on $0.06854978, both in index #rule. The 21 native pair charges are in the explore #agreement-policy table.
- Whole study. OpenRouter $12.653729 across 15,135 saved generations plus up to $3.88 of reservations for requests whose id was never saved. Direct Cloudflare runs under $0.26. Seven-model series $1.2013 known plus up to $0.13 unknown. About $0.62 of key usage is unexplained. Sources: docs/talk/06-cost-check.md sections 1 and 4, docs/talk/05-session-outline.md Q&A 19, deck/data/answer.json. grep for 12.65, 15,135 and $3.88 over the three pages returns nothing. The seven-model $1.2013 appears only inside the corrections log in index #deep-insights.
- Rating: 5a BURIED. 5b PRESENT. 5c MISSING.

### 6. Confidence and calibration

- Jev expected calibration error 0.011 over 720 pooled field answers. Clef Flash 0.358 over 2,156. Jev wrong at 0.96 on DEV-027 testimonial and 0.91 on DEV-029 serious concern. Jev's ten least-confident reviews include 7 of the 10 hardest. Clef Flash confidence and option probability differ by more than 0.2 on 1,192 of 2,156 answers (55.3%). All on index #controls and #deep-insights, with a reliability plot and bin table.
- The 0.9 cutoff. The retained counts at confidence 0.9 and above, from jev-confidence-findings.json P0, are: sentiment 47 of 60 retained with 0 wrong; follow-up 52 with 0 wrong; serious concern 53 with 1 wrong; testimonial 54 with 1 wrong. The "54 of 60" is the testimonial field only. The site states it as one sentence in explore #jev-analysis and links to the docs report for the thresholds. The other three fields' numbers are not on the site.
- Rating: 6a PRESENT. 6b BURIED.

### 7. Agree or defer

- 35 of 60 reach a person under the full policy (7 deferred, 24 escalated for a concern, 4 sent for clarification). 25 accepted with no routing. Solar + Perplexity accepted 53 with 0 errors, 7 deferred. Queue and the 25 IDs are in index #deep-insights, default pair.
- 21 pairs: accepted range 33 to 53, accepted errors 0 to 4. Exactly five pairs kept zero accepted errors: Liquid D1 + Tev 1 4B, Liquid D1 + Solar, Solar + Clef, Solar + Clef Flash, Solar + Perplexity (checked against the table rows in explore #agreement-policy). The sentence "5 of 21 pairs kept zero accepted errors" appears only in the corrections log. The table lets a reader count them, nothing says it up front.
- Routing breakdowns for other pairs sit behind the "try a pair" picker in index #deep-insights (about 40 options including general-model pairs).
- Rating: PRESENT.

### 8. The soup review DEV-029

- 0 of 7 decision models matched the "can't tell" reference. 89 of 113 general configurations with valid answers did. 13 of 28 declared fresh configurations did (docs only). Four of seven decision models said "mixed", two "insufficient", one "negative" on sentiment. 6 of 21 pairs accepted it with the same wrong answer (docs/talk/14-phrases.md row 39).
- Index #hard-reviews has 0 of 7 and 89 of 113. The 13 of 28 and the 6 of 21 are not on the site.
- Rating: PRESENT.

### 9. Launch wave

- Feed: public-site/deck/data/timeline.json, 22 dated entries from 2026-09-15 (TypeSafe Jev 1.13, verified) to 2026-10-07 (Liquid d1-3B and d1-omni-600M open weights, Perplexity Decider V1.1 27B on OpenRouter). Seven items are excluded by design. Four entries are marked verified: false (Laya, GLiNER2.5-Decide, Liquid d1 first date, Perplexity pplx-decider launch date). Source doc docs/talk/02-landscape.md Part C.
- None of index, explore or method mentions launch dates, a wave, or makers by date. Vendors appear only as run names. grep for "launch", "released" and date strings returns nothing.
- Rating: MISSING from the three pages. It exists only in the deck.

### 10. Method

- Four questions and the definition of serious concern: PRESENT (index #decisions). How matched is scored (all four agree, denominator fixed at 60): PRESENT (index #decisions, method). Disputed labels DEV-006, DEV-013, DEV-030: PRESENT (index #limits, method #findings).
- method.html is three sections. It does not say how many passes, how many run entries, or which were interrupted. It does not list the labelling rubric. It links the disputed cases.
- Labelling guide: the rubric link sits in the "Source records and hashes" details of explore #review-evidence. docs/REFERENCE_REVIEW_V1.md is the full text.
- Passes: index #limits says "The 1,004 saved run entries reuse the same 60 reviews". Explore #how-it-works says "some planned passes remain unfinished". There is no "252 three-pass configurations, 241 clean, 11 with a partial pass" line.
- Interrupted passes: explore mentions "interrupted" 21 times, all inside repeat notes and details. Index shows only Jev P2 pass 2, "stopped after 17 valid responses".
- Rating: 10a, 10c, 10f PRESENT. 10b, 10d, 10e BURIED.

### 11. Downloads

- Explore carries about 20 inline links to individual feeds (data.json is reached through "main feed", analysis-refresh.json, cross-category-v1.json, disputed-reviews-v1.json, native-agreement-policy-v1.json and others) and about 30 links to GitHub docs. Index #next links the repository: "The reviews, the reference, every saved answer and the scripts".
- No page lists the feeds with size and SHA-256. The largest are data.json 9.97 MB and extended-cases-v1.json 6.7 MB. No CSV of the leaderboard exists.
- Harness: "classification-bench, the tool that ran these tests, is being open-sourced. Ask Adam for early access." on index #next and method #harness. The status is stated. 433 tests collected is in docs/talk/04-harness.md and not on the site.
- Rating: 11a and 11b BURIED. 11c PRESENT.

## Mismatches and traps

1. Jev route and cost label (medium). The nine Jev cells P0/P1/P2 by fresh 1 to 3 are labelled "OpenRouter native Choice" with "a known provider charge" on index #gap. The same cells in explore (run ranking, model picker, usage) read "TypeSafe native Choice API, observed charge unavailable, Estimate $0.00589092". extended-run-catalog-v1.json carries provider TypeSafe and estimatedUsd for these ids, while jev-native-prompt-findings.json carries knownCostUsd 0.00589092, 0.006405 and 0.00685104. docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md and docs/talk/06-cost-check.md say OpenRouter native, known. Fix in the catalog entries for extended-typesafe-jev113-native-prompts-*. The direct TypeSafe P0 run (typesafe-jev113-v2) legitimately stays an estimate.
2. Clef first pass 53 vs 54 (low-medium). Explore #clef-first-pass says Cloudflare Clef 53/60 (fields 55/59/56/58) and Clef Flash 45/60. Explore #run-ranking, deck/data/prompt-levels.json and docs/talk/01 say Clef 54/60 on P0 (OpenRouter fresh1, fields 56/59/56/58). docs/CLEF_FINDINGS_2026-10-02.md is the origin of 53. The panel does not say it is a different route and an earlier run. A reader sees both numbers.
3. 31 of 50 and 11 of 202 direction (brief wording, not a site error). They are groups with no changed answer.
4. "Decision models answered most 'insufficient information' cells with a definite label" (low). docs/talk/14-phrases.md row 69 warns to quote percentages. The card shows 75.0% on follow-up and 50.2% on serious concern, so "most" is barely true on one of the two and the testimonial figure (26.3% across all models) is not on the card.
5. 23 of 853 vs 35 of 853 (docs, not site). Index #deep-insights says 23 of 853 charged pairs accept more than Solar + Perplexity at a lower charge with no accepted errors. docs/talk/14-phrases.md section 3 item 26 and 01b section 11 say 35 of 853 "dominate". Different definitions. Pick one before a slide quotes both.
6. Calibrated or not (low). Index says Jev's confidence "is calibrated on average" (ECE 0.011). jev-prompts.js and kev-prompts.js say vendor confidence is not treated as a calibrated probability of correctness, and repeats.js says confidence values "are not calibrated probabilities of correctness". The scopes differ (pooled ECE vs per-field use), a careful reader can still read them as a contradiction.
7. Jev P2 pass 2 (low). Index: stopped after 17 valid responses, no full score. The catalog stores all_four 15 for that cell. deck/data/prompt-levels.json and docs call the interrupted composite 50/60. Three numbers for one cell. The index handles it by showing "stopped".
8. Path (trivial). The brief names FINDINGS.md at the repo root. The file is docs/FINDINGS.md. Root has README.md only.

Checked and consistent: Jev 54/53/52; Opus 5.5 high 59/58/58 (P0), 59/59/58 (P1), 59/58/58 (P2); Sonnet 5.5 xhigh 58 in nine cells; $0.00589092 and $0.222052; ECE 0.011 and 0.358; 0.96 and 0.91; 4/14/21 of 39; 35 of 60 with 7/24/4; 53, 0 errors, 7 deferred, $0.03749436; Qwen + Gemma 58 accepted, 0 errors, 2 deferred, $0.06854978; 31 of 50, 11 of 202; 0 of 7 and 89 of 113; the eight dated corrections are not reintroduced in index, explore, method, or the JS (grep for the old wording found nothing).

## Five panels that would most change a reader's sense

Each keeps the "not a ranking" rule by carrying route, batch size, effort and cost basis as columns, so the table does not compare unlike things silently.

### 1. All results (the missing table)
- Place: top of explore, before the pickers, or its own page results.html linked from index.
- Rows: one per configuration (252 three-pass configurations plus singletons). Sort default by P0 mean. Filter chips: decision, general, hosted, local, subscription.
- Columns: model and configuration, category, route and interface, batch size, effort or thinking; P0 pass 1/2/3; P1 pass 1/2/3; P2 pass 1/2/3 (or three small cells with min to max); valid out of 60; reviews that changed across passes; fixed misses (list, flagged "disputed only"); cost per pass with a basis tag (known, observed, estimate, unknown); invalid or interrupted marker.
- Source: data.json runs[], extended-run-catalog-v1.json runs[], supplemental-decision-runs-v1.json runs[] (metrics.all_four, condition, repeatPass, cost), changed-review counts from extended-cases-v1.json and additional-cases-v1.json via docs/talk/scripts/s07_repeatability.py, cost basis from subscription-price-estimates.json. Prebuild one JSON so the page does not merge three feeds in the browser. Add a CSV download.

### 2. Per-decision accuracy matrix
- Rows: the seven decision models, Jev, and the top general configurations (Opus 5.5 high, Sonnet 5.5 xhigh, Gemma 4 26B on, Qwen3.8 27B low).
- Columns: all four; sentiment, follow-up, serious concern, testimonial (each out of 60); recall on the 10 reference "can't tell" cells; definite-answer rate on reference-insufficient follow-up; stage (P0 fresh1 default, toggle P1/P2).
- Source: runs[].metrics in the three run feeds; recall columns from deep-insights-v1.json insufficient_collapse and docs/talk/01b section 12.1 (decision 19% to 45%, general 71% to 84%).

### 3. The twelve hard reviews
- Rows: the six Jev missed (DEV-006, 013, 027, 029, 030, 059) and the six that split four or more decision models (adds DEV-056). Seven distinct reviews in total.
- Columns: review text; reference on the four questions; Jev answer; seven decision-model answers as coloured cells; models out of 7 that differ; general configurations matching the reference (89 of 113 on DEV-029); label status (disputed, off-topic, polite serious).
- Source: disputed-reviews-v1.json reviews[], deck/data/hard-cases.json, cross-category-v1.json cases and runs, Jev answers from jev-native-prompt-findings.json or data.json cases for typesafe-jev113-v2.

### 4. Cost ledger
- Rows: one per model at its first P0 pass, the pairs, and the study totals.
- Columns: model or pair; matched of 60; charge for 60 reviews; basis tag; multiple of Jev's $0.00589092; output tokens or reasoning tokens where billed.
- Totals row: OpenRouter $12.65 over 15,135 generations plus up to $3.88 of unrecorded reservations; direct Cloudflare under $0.26; seven-model series $1.2013 known plus up to $0.13 unknown. Footer line: "A missing cost is unknown, never zero."
- Source: docs/talk/06-cost-check.md (sections 1, 2, 4 and the totals table), deck/data/answer.json, supplemental-decision-runs-v1.json, subscription-price-estimates.json, native-agreement-policy-v1.json components and pairs. The totals need a small feed (study-cost-v1.json) because they currently live only in docs.

### 5. Stability and gate strip
- Left block, repeatability: decision 31 of 50 unchanged, general 11 of 202; the 42 / 68 / 88 / 29 / 15 / 10 distribution; P1 to P2 as 4 up, 14 same, 21 down of 39.
- Right block, confidence: Jev and Clef Flash ECE; the 0.9 cutoff table for all four Jev fields (retained, wrong): sentiment 47 / 0, follow-up 52 / 0, serious concern 53 / 1, testimonial 54 / 1; the two wrong answers at 0.96 and 0.91; the 54-of-60 line lifted out of its paragraph.
- Source: deep-insights-v1.json determinism and calibration, findings.json, jev-confidence-findings.json conditions.P0.fields.*.thresholds["0.9"].

Two small adds that cost little: a launch-wave strip from deck/data/timeline.json (22 entries, mark the four unverified dates), and a Data page listing every feed with size and SHA-256 plus the repo link.

## Not verified

- Picker contents past their default option were read from the feeds, not clicked. Rankings for P1 and P2 were not rendered.
- I did not rebuild the 1,004 run-pass union. Counts of 252, 241 and 11 come from 01b section 7 and deep-insights-v1.json.
- Downloads: link targets were listed, not fetched.
