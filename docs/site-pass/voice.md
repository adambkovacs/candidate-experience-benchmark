# Voice and metacomment audit: index, explore, method

Worktree `/Users/adamkovacs/lanes/cxb-talk`, branch `feat/site-content-v2` at `ffb9305a`. Read-only audit. Nothing edited, nothing committed.

Adam's complaint: "tons of metacomments, not premium, doesn't feel like giving us info and benchmarks."
Verdict: the complaint holds. The numbers are strong and specific. The prose around them spends most of its words telling the reader how to read, what not to conclude, and where each figure came from. Every one of those can move to the Method page or die.

## How this was produced

- Pages served over HTTP from `public-site/`, rendered in Chromium (Playwright via `deck/verify/lib.mjs`), all `<details>` opened, page scrolled end to end, 6.5 s settle. Zero "loading" placeholders remained.
- Rendered text: `voice/index.txt` (4,791 words), `voice/explore.txt` (91,814 words, mostly run tables and review text), `voice/method.txt` (679 words).
- Meta elements and every `title` attribute with the id of the enclosing section: `voice/meta-index.txt` (173 rows), `voice/meta-explore.txt` (97), `voice/meta-method.txt` (2). Beyond the classes you named I also captured `di-implication`, `di-meta`, `di-tag`, `di-source`, `di-badge`, `di-sub`, because the second-pass section is where most of the meta lives.
- Machine-extracted hedge and instruction sentences from the caveat blocks, one row per sentence, with the same columns as the table below: `voice/appendix-hedges.md` (68 rows).

## Script scores

| Page | Words | Anti-slop NO-SLOP score | Formality | Warmth | Energy | Directness | Complexity | Avg sentence | Flesch-Kincaid | Nominalization | Passive |
|---|---|---|---|---|---|---|---|---|---|---|---|
| index | 4,791 | 100.0% (0 instances) | 4.8 | 2.2 | 2.0 | 3.4 | 2.9 | 21.4 words | 12.2 | 4.09% | 4.02% |
| method | 679 | 100.0% (0 instances) | 4.6 | 2.3 | 2.1 | 3.7 | 2.7 | 11.3 words | 7.4 | 3.39% | 13.33% |
| explore | 91,814 | 55.5% (8,170 penalty) | 5.0 | 2.1 | 2.0 | 3.4 | 4.5 | 56.1 words | 31.8 | 4.66% | 7.03% |
| Adam presentation target | | | 2.1 | 4.7 | 2.2 | 3.5 | 1.9 | 22.5 words | 8.6 | 1.33% | 3.03% |

How to read these honestly:

- **The anti-slop 100% on index and method means almost nothing.** The scanner looks for banned words and punctuation. This copy has none. It is not slop in the vocabulary sense. It is report-generator prose, which the scanner cannot see.
- **The explore 55.5% is a false alarm.** All 814 "hard ban" hits are the pattern `--` inside run identifiers such as `fable51-high-phase2-batch10-p0--p1`. The real hits are 3 pairs of curly quotes (`“Differs”`, `“not verified”`) and 5 triple lists. Fix the quotes, ignore the rest.
- **The explore complexity, sentence length and Flesch-Kincaid are inflated** by table rows and ID lists. Do not quote them. The prose-only sentences read around grade 12 or higher.
- **The voice scores say what the ear says.** Formality 4.6 to 5.0 against a 2.1 target, warmth 2.1 to 2.3 against 4.7, nominalization three times Adam's rate. A data page should not hit warmth 4.7. It should reach formality 3 and a Flesch-Kincaid around 9. Today it reads like a methods appendix.

## Counts of metacomments by type

Counted as page elements or sentences found in the rendered pages. Full lists are in the tables below, the meta files and the appendix.

| Type | index | explore | method | Total | Verdict |
|---|---|---|---|---|---|
| Provenance footer or source line (`source-line`, `example-source`, `di-source`, `analysis-source`) | 26 | 1 | 0 | 27 | CUT, move to Method |
| Hover hint (`title` attributes that print file paths and formulas, plus the "Hover a number" sentence) | 93 | 11 | 0 | 104 | CUT or replace with plain-language derivation |
| Eyebrow or kicker label | 13 | 40 | 2 | 55 | CUT, the heading does the work |
| Hedge, disclaimer or caveat element (`hero-boundary`, `di-meta`, `analysis-caveat`, `chart-limit`, `overview-caution`) | 9 | 42 | 0 | 51 elements, 29 separate hedge sentences in the appendix | CUT or fold one clause into the number |
| Reliability badge (`SOLID`, `DESCRIPTIVE ONLY`) | 9 | 0 | 0 | 9 | CUT |
| Instruction to the reader ("Choose a run", "Select a step", "Read the...", "See...") | about 20 | about 70 | about 5 | 79 sentences in body prose plus 39 inside caveat blocks | CUT, keep the link |
| Narrator aside or process label ("Implication:", "SAID / CORRECTED", "That queue is the price of...", the two duplicate intros to the second-pass section) | 20 | 3 | 1 | 24 | CUT or fold into the claim |
| Repeated disclaimer of the same limit (fictional, provisional, "not a ranking", "same 60") | 6 fictional, 5 provisional, 8 ranking-related | 14 fictional, 43 provisional, 21 ranking-related, 96 "same 60" | 3 fictional | see rows | Say once in Limits |

Pattern: the same four caveats (fictional, provisional reference, same 60 reviews, not a ranking) are restated in roughly every block. They are true and they belong on one page.

---

## 1. Metacomment table

Rule used for the action column: CUT means delete from the page. A rewrite keeps the fact and drops the framing. "Move to Method" means the fact is real and should live once on the Method page.

The 93 hover titles on index and the 11 on explore are one family. They print identifiers like `findings.json#charts.jev.correct`. Per-element text is in `meta-index.txt`. They are summarised by section in the first block.

### index.html

| Section id | Exact text | Type | Action |
|---|---|---|---|
| overview | `A TALK COMPANION · AI ENABLEMENT ACADEMY` | eyebrow | CUT. The nav already names the site. |
| overview | `A small, fictional test. AI wrote the reviews and drafted the reference. A person checked every label, and three remain disputed. Hover a number to see the file it comes from; each section lists its sources.` | disclaimer + hover hint | Rewrite: `Sixty fictional reviews. AI wrote them and drafted the reference answers; a person checked every label and three are still disputed.` Cut the hover sentence. |
| overview | 9 hover titles, e.g. `Source: findings.json#charts.jev.correct`, `Derived: F#charts.costAgreement.rows[id=openrouter-paid-gemma4-26b-a4b-on].actualUsd / J#passes.P0.fresh1.knownCostUsd = 3.6` | hover hint | CUT. Replace the two derived ratios with visible text: `3.6x to 38x the cost of a Jev pass`. |
| overview | hover title on "Two": `Derived: 6 misses minus 3 disputed labels (DI#reference_status) minus the off-topic DEV-029` | hover hint hiding a fact | Promote to visible copy: `Of Jev's 6 misses, 3 sit on disputed labels, 1 is the off-topic soup review and 2 are plain errors.` |
| overview | `SOURCES deep-insights-v1.json · findings.json · sonnet55-fresh-matched3.json` | provenance footer | CUT, move to Method as one "Where the numbers come from" table. |
| decisions | `THE TEST` and `ONE COMMENT, FOUR DECISIONS` | eyebrow | CUT both. The h2 `Every review gets four decisions.` stands alone. |
| decisions | `Comment DEV-003 of 60 · Inspect the answers` | provenance caption | Rewrite: `DEV-003` as the card tag. Keep `See every model's answer ↗` as the link. |
| decisions | `These are the provisional reference answers. "Serious concern" has a specific definition here, including harassment, discrimination and privacy breaches. It does not mean every bad experience.` | disclaimer | CUT. The definition already appears one screen up in the four-decisions list. |
| decisions | `SOURCES deep-insights-v1.json` | provenance footer | CUT |
| gap | `FINDING 1` / hard-reviews `FINDING 2` / controls `FINDING 3` / `THREE FINDINGS` / `01` | eyebrow | CUT. The h2s are already numbered by position. |
| gap | 41 hover titles on the score table cells and cost figures | hover hint | CUT |
| gap | `A Jev pass cost $0.00589092, a known provider charge. An Opus pass is an API-equivalent estimate of $0.222052, not a bill.` | hedge | Rewrite: `A Jev pass cost $0.0059. An Opus pass would cost $0.22 at API prices.` Say once that Claude ran on a subscription. |
| gap | `Twenty-five synthetic examples cannot show real-world sensitivity, and it still answered no to "does someone need to follow up?" on this one, where the reference says yes:` | hedge + clumsy setup | Rewrite: `Jev flagged all 25 serious-concern reviews. It missed one follow-up: DEV-059 below, where the reference says yes.` |
| gap | `All-four matches out of 60 for each prompt version (P0, P1, P2) and fresh pass. Jev ran through OpenRouter's native Choice interface; its second P2 pass stopped after 17 valid responses and has no full score. Routes, interfaces and settings differ between the three, so this is not a ranking.` | caption + disclaimer | Rewrite: `Jev's second P2 pass stopped after 17 valid answers and has no score.` |
| gap | `SOURCES jev-native-prompt-findings.json · claude-roster-repeats.json · sonnet55-fresh-matched3.json · subscription-price-estimates.json · findings.json` | provenance footer | CUT |
| hard-reviews | `Decision models, out of seven, whose four answers differed from the reference on each review. Seven OpenRouter native models, first pass, base prompt. Read every review case.` | caption + instruction | Rewrite: `How many of the seven decision models missed each review (first pass, base prompt).` Keep a link `All 60 review cases ↗`. |
| hard-reviews | 12 hover titles | hover hint | CUT |
| hard-reviews | `SOURCES deck/data/hard-cases.json · cross-category-v1.json` | provenance footer | CUT |
| controls | `Calibration figures are descriptive and look back at the same reviews. Jev never abstained, and no threshold was chosen on held-out data.` | disclaimer | CUT. Limits repeats it nearly word for word (`Confidence thresholds here are hindsight`). |
| controls | 15 hover titles, `SOURCES deep-insights-v1.json · findings.json` | hover hint, provenance | CUT |
| rule | `WHAT TO DO ABOUT IT` and `THE RULE` | eyebrow | CUT one. |
| rule | `$0.06854978 observed. This pair is pass-sensitive: other passes of the same two models give different counts.` | hedge that carries a fact | Rewrite: `$0.0685. Other passes of this pair accept different counts, so 58 is one draw.` |
| rule | `That queue is the price of zero accepted errors on this set.` | narrator aside | Rewrite: `Zero accepted errors, with 35 of 60 reviews going to a person.` |
| rule | `These counts look back at the same 60 development reviews. None of these pairs is a recommended production setup. Compare all agreement pairs.` | disclaimer | CUT the first two sentences (Limits has them). Keep `Compare all agreement pairs ↗`. |
| rule | 13 hover titles, `SOURCES deep-insights-v1.json` | hover hint, provenance | CUT |
| deep-insights | `SECOND-PASS ANALYSIS` (eyebrow), heading `WHAT CHANGED ON 8 OCTOBER` | eyebrow | CUT the eyebrow. Heading becomes the finding, see sentence 3 in part 3. |
| deep-insights | `The talk's analysis scripts reran over the saved predictions for the same 60 fictional reviews and made no new model calls. Each number names its place in the data file, which also lists the SHA-256 of every source file it was built from.` | process narration | CUT. Duplicates the paragraph below. |
| deep-insights | `On 8 October 2026 the talk's analysis scripts recomputed every number in this section from the saved answers of 1,004 run-passes on the same 60 reviews, without new model calls. The recomputation corrected 8 earlier statements, listed at the end of this section, and produced the five findings in the cards below.` | process narration | Rewrite: `1,004 run-passes over the same 60 reviews, no new model calls. Five findings below; 8 earlier claims corrected on the Method page.` |
| deep-insights | 8 x `Implication: ...` (e.g. `Implication: Treat insufficient information as its own detection task with its own recall; the four-field total hides this gap on exactly the reviews that need a person.`) | narrator label | Keep the sentence as the card's last line, delete the word `Implication:`. |
| deep-insights | 7 x `SOLID` badge and 2 x `DESCRIPTIVE ONLY` badge | reliability badge | CUT all nine. A badge that says "solid" on seven of nine cards carries no information. |
| deep-insights | 8 x `di-meta` caveat, e.g. `SOLID Counts are exact over saved answers. The decision vs general split is a working category split, so the comparison is descriptive-only.` | caveat | CUT. If the category split is ours, say that once in the card title: `Our decision/general split: decision models guessed a definite label on 132 of 176 follow-up cells.` |
| deep-insights | 9 x `Computed by s02_confusion.py, s06_rare_classes.py from data.json, extended-cases-v1.json, additional-cases-v1.json. Numbers: deep-insights-v1.json.` | provenance footer | CUT, move to Method as a table of script, inputs, output. |
| deep-insights | 8 x `Source: public-site/...json` or `docs/talk/scripts/...py` under each correction | provenance footer | CUT with the corrections block. |
| deep-insights | `Corrections dated 8 October 2026` with 8 `SAID ... CORRECTED ...` pairs | changelog on the main page | Move to Method as "Corrections log". Only keep on index if the audience saw the old numbers. |
| deep-insights | `Limits. The numbers describe saved runs; they rank no model and make no claim about cause. The reference is provisional, and three of its labels are disputed. A missing cost stays unknown and never counts as zero, and provider charges stay separate from estimates. The section makes no speed claims. Every finding looks back at the same 60 development reviews, and repeated runs of them are not independent samples.` | disclaimer | CUT. Section 04 says all of it. |
| deep-insights | `Computed by s07_repeatability.py ...` plus the 42-row "All 42 configurations that changed no answer in three passes and still missed reviews" table caption `Same answers in all three passes; all-four matches out of 60.` | caption | Keep the table. It is benchmark data. Caption is fine. |
| limits | `LIMITS` eyebrow over h2 `What this test does not show.` | eyebrow | CUT eyebrow. |
| limits | `SOURCES deep-insights-v1.json` | provenance footer | CUT |
| limits | 8 bullets, each a bold negation: `It is not a leaderboard.` `Nothing here is causal.` `It is not real-world accuracy.` `There are no speed claims.` | binary contrast / disclaimer | Rewrite as facts. See part 2. |
| team | `Our fictional examples show what to investigate. They cannot tell you which system to deploy.` | disclaimer + binary contrast | Rewrite: `Use these as the questions to put to your vendor.` |
| next | `EXPLORE`, `METHOD`, `SOURCE` card eyebrows | eyebrow | CUT |
| footer | `An open experiment with 60 fictional comments. Scores show agreement with a provisional reference, not deployment quality.` | disclaimer | Rewrite: `60 fictional comments, scored against a provisional reference.` |

### method.html

| Section id | Exact text | Type | Action |
|---|---|---|---|
| method | `METHOD AND LIMITS` | eyebrow | CUT |
| method | `How we ran the test, and what it cannot tell you.` | binary contrast heading | Rewrite: `How the test ran.` |
| method | `AI wrote these fictional comments and drafted the reference answers. A person checked all 60 answers; some remain disputed. Historical scores retain the original reference version. The results describe this test set, not performance with real candidates.` | disclaimer (fourth restatement) | Keep once, shorter: `AI wrote the 60 comments and drafted the answers; a person checked all 60 and three labels are disputed.` Cut the last sentence. |
| method | `Historical scores retain the original reference version.` (appears twice, intro and "The reference answers were checked too") | disclaimer | Say once. |
| method | `Cost: Reported API charges, price estimates and possible charges without a known bill are labeled separately. Subscription fees are not split across runs. An API price estimate is not an observed charge.` | disclaimer | Rewrite: `Cost columns: provider charge, API-price estimate, or unknown. Subscription fees are not allocated to runs.` |
| method | `Questions you may have` FAQ with 9 questions, e.g. `What do "model", "prompt" and "run" mean?` `What are tokens, and why do they matter?` | narrator framing, light condescension | Move to a collapsed glossary. Keep the answers about what the models saw and about missing prices, which are facts. |
| method | `Can I use these scores to choose a hiring tool? No. This small fictional set and its provisional answers do not measure performance with real candidates or the effect of using a model in hiring.` | disclaimer | Keep, this is the one honest answer. Delete the sibling `Does a valid response mean the answer matched? No.` style Q/A openers. |
| method | `The reference answers were checked too.` | kicker | Rewrite: `A person checked all 60 reference answers. DEV-006 has a proposed serious-concern correction; DEV-013 and DEV-030 are judgment calls.` |
| harness | `TOOLING` | eyebrow | CUT |
| harness | `classification-bench, the tool that ran these tests, is being open-sourced. Ask Adam for early access.` | fine | KEEP |
| footer | `An open experiment with 60 fictional comments. Scores show agreement with a provisional reference, not deployment quality.` | disclaimer | Same rewrite as index. |

### explore.html

Eyebrows (40). All are breadcrumb noise of the form `AREA / SUBJECT`. CUT all. The heading under each says the same thing. Exact text, by section id:

`explore-top` EXPLORE · `how-it-works` THE TEST, IN FOUR STEPS · `scores` A KEY TO THE NUMBERS · `report-lens` RESULTS / CHOOSE A VIEW · `outcome-chart` RESULTS / FORMAT AND AGREEMENT · `run-ranking` RESULTS / SAVED RUNS and ALL FOUR ANSWERS MATCH / 60 · `inspect` INDIVIDUAL RUN · `jev-title` HISTORICAL JEV API RUN · `models` MODEL COMPARISON · `explore` COMPARE PROMPT VERSIONS and SAVED RUNS · `audited-comparison` JEV INSTRUCTION COMPARISON · `usage` RESOURCE USE · `cross-category` ANALYSIS / JOINED SAVED ANSWERS · `cross-pair` SELECTED SAVED RUNS / P0 · `cross-case-detail` EXACT SAVED ANSWERS / DEV-001 · `cohort-reviews` FIRST P0 / THE SAME 60 COMMENTS · `cohort-review-selected` DEV-029 / FROZEN DEVELOPMENT REVIEW · `review-evidence` RESULTS / INDIVIDUAL REVIEWS · `disputed-detail` DEV-029 / SAVED COMMENT · `agreement-policy` ANALYSIS / FIXED AGREEMENT RULE · `agreement-detail` SELECTED PAIR / SOURCE ORDER · `reference-sensitivity` ANALYSIS / REFERENCE SENSITIVITY · `clef-first-pass` RESULTS / NATIVE DECISION MODELS · `clef-first-pass-results` CLOUDFLARE CLEF · NATIVE CHOICES and CLOUDFLARE CLEF FLASH · NATIVE CHOICES · `analysis-update` ANALYSIS UPDATED / 7 OCTOBER 2026 · `prompt-analysis` 01 / PAIRED PROMPT COMPARISONS · `kev-prompt-analysis` KEV NATIVE CHOICE / THREE PAIRED PASSES · `jev-prompt-analysis` JEV NATIVE CHOICE / CLOSED AND INTERRUPTED PASSES · `repeat-analysis` REPEATABILITY / COMPARE REPEATED ANSWERS · `repeat-notes` SOURCE NOTES / MODEL FINDINGS · `jev-analysis` 02 / DECISION ERRORS · `cost-analysis` 03 / OBSERVED SPENDING · `hard-analysis` 04 / COMMENTS WORTH A SECOND LOOK · `story` THREE FINDINGS FROM THE SAVED ANSWERS · `story-specialist` 01 / A SPECIALIST ALONGSIDE CHAT MODELS · `story-prompts` 02 / LONGER INSTRUCTIONS DID NOT CONSISTENTLY HELP · `story-repeat` 03 / THE SAME INSTRUCTIONS CAN GIVE DIFFERENT ANSWERS.

Note the last three are real claims (`LONGER INSTRUCTIONS DID NOT CONSISTENTLY HELP`). They should be the h3, not a small-caps eyebrow.

| Section id | Exact text | Type | Action |
|---|---|---|---|
| explore-top | `Every panel here reads the same 60 fictional reviews. Pick a model group, follow a point or a row to its run, and open the run inspector to see each answer next to the reference.` | instruction to reader | Rewrite: `121 closed runs and 637 more report-backed stages, all scored on the same 60 reviews.` |
| explore-top | `New here? Start with the three findings, or read how the test works.` | throat-clearer | CUT |
| how-it-works | `We changed the AI setup, then checked its answers against the same draft reference. Select a step to see what each part means.` | instruction | Cut the second sentence. |
| scores | `We count format and agreement separately. A correctly formatted answer can still be wrong. Missing or unusable answers do not earn points; the denominator stays at 60.` | explanation | KEEP, shorten to the last sentence: `Missing or unusable answers score zero; the denominator stays 60.` |
| scores | `You can also see agreement for each decision separately.` | instruction | CUT |
| report-lens | `Every run used the same 60 fictional comments, but model purpose, output interface, prompt and route can differ. Choose a group, then follow a point or row to its saved source.` | disclaimer + instruction | CUT |
| report-lens | `A model can appear in more than one category. Each run appears once within a view; repeat passes reuse the same 60 reviews.` | caveat | CUT |
| outcome-chart | `These two measures ask different questions. Valid answers follow the required format; all-four matches also agree with the provisional reference on every decision. Select a point to see the exact saved runs behind it.` | rhetorical setup + instruction | Rewrite: `X axis: answers in the required format. Y axis: all-four matches against the reference.` |
| outcome-chart | `Both axes count the same 60 fictional comments. A point can hold several exact setups; its number shows how many. Only closed 60-record runs appear in the chart. They come from the main feed, Sonnet first passes, Clef first passes, native decision-model feed, and report-backed repeat and continuation catalog. Open Run detail to inspect...` | provenance + instruction | Rewrite: `54 closed runs at 13 points; a point's number is how many setups share it. 25 partial runs excluded.` |
| run-ranking | `P0: base task. P1: classifier instructions. P2: decision procedure. Jev's P1 and P2 use native Choice questions; see the prompt comparison.` | legend | KEEP the first three sentences once near the top of the page. Cut the rest. |
| run-ranking | `A complete run saved a result for all 60 comments. Some responses could not be scored because they did not follow the required format. Partial runs remain available in the run explorer below. Scores reflect saved outputs, not a controlled model ranking.` | caution | Rewrite in part 3, sentence 6. |
| inspect | `Choose a saved run to read its comments, answers and source report. Technical request timing and usage details follow the score summary.` | instruction + roadmap | CUT |
| jev-title / models | `Choose another run below to compare its four decisions with Jev. Routes and settings can differ. Jev's API price is an estimate; its provider charge is unavailable.` | instruction + hedge | Rewrite: `Jev's price is an API-rate estimate; the provider reported no charge.` |
| models | `Category describes the model's task. A decision model may use a general-purpose LLM, and one setup can fit more than one category. Fine-tuning or adaptation changes model weights; prompt instructions do not. ...` | definition lecture | Move to glossary. See part 3, sentence 10. |
| usage | `Client-observed request attempts, including network and local work. Provider inference duration unavailable; summed requests are not one inference.` / `Totals exclude requests with missing usage...` / `Input-token price estimate, not a provider billing receipt. Development only; smoke excluded.` | ledger-speak | Rewrite in part 3, sentence 7. |
| cross-pair | `Recorded controls and accounting for the selected pair. Unavailable is not zero.` / `Reported and reconciled known charges can describe the same requests; do not add those rows.` | footnote | Move to Method as one line on cost columns. |
| cohort-reviews | `Choose a first-pass cohort. General LLMs use the declared fresh1/pass1 set by default; historical first P0 runs are a separate choice...` | instruction | CUT |
| analysis-update | `The newer runs change the cost comparison. In their first base-task runs on OpenRouter, Perplexity Decider and Clef each matched all four reference answers on 54 of 60 reviews. Recorded development charges were $0.01542736 and $0.03184656 respectively. Equal totals can hide different field-level mistakes; these two saved runs do not establish a general model-family advantage or a full workflow price. Compare their exact answers · Read the reconciled findings...` | caveat with real numbers | Rewrite: `Perplexity Decider and Clef both matched 54 of 60 on their first base-task run, at $0.0154 and $0.0318. Same total, different misses.` |
| analysis-update | `Qwen 0.6B repeated the same mistakes. This small local model returned all four labels in the required format in every pass. Yet no review matched all four reference answers. With the base prompt, it marked all 60 comments as potential testimonials; the reference key marks nine. ... These findings apply to this quantized model and local HTTP setup. See the field-by-field results and method, or choose Qwen3 0.6B in the repeat comparison.` | caveat + instruction | Keep the first five sentences, they are the best writing on the page. Cut the last two. |
| repeat-note-prompts, repeat-note-changes, repeat-note-stable, repeat-note-invalid, repeat-analysis, repeat-chart, prompt-analysis, kev-prompt-results, jev-prompt-results, analysis-source, story-specialist, story-prompts, story-repeat, jev-analysis | 41 `analysis-caveat`, 3 `chart-limit`, 2 `overview-caution` blocks. The hedge and instruction sentences inside them are listed one per row in `voice/appendix-hedges.md` (68 rows: 29 hedge, 39 instruction). Typical hedge tails: `Repeated comments are not independent cases.` `Prompt changes are associations within saved runs.` `This measures agreement with draft answers, not verified accuracy.` Typical instruction tails: `Compare all six three-pass results.` `See the changed reviews, costs and limits.` | caveat + instruction | CUT every hedge tail that has no number in it. Keep every sentence that carries a score. Turn each `See / Read / Compare` tail into the link itself. |
| analysis-source | `Computed from saved records · source SHA-256 52d827b39690` | provenance footer | CUT, move to Method. |
| story-jev-grid | 6 `Inspect DEV-0xx` link titles; cross-pair 5 segment tooltips (`Both match reference: 0`) | hover hint | Link titles: CUT. Segment tooltips are chart data labels: KEEP. |

---

## 2. Sentences to rewrite by pattern

Each rewrite keeps the number.

### Kicker fragments

| Page / section | Original | Rewrite |
|---|---|---|
| index / overview | `A small, fictional test.` | `Sixty fictional reviews.` |
| index / rule | `Agree or defer.` | `Run two cheap models and send every disagreement to a person.` |
| method | `The reference answers were checked too.` | `A person checked all 60 reference answers; 3 labels are still disputed.` |
| explore / repeat | `A similar score can hide different decisions.` | `Same score, different answers: Gemma E2B scored 35 of 60 in all three passes while 9 reviews changed a decision.` |
| explore / repeat-note-stable | `Stable answers can still be wrong under the rubric.` | `Three Laya configurations returned identical answers in all three passes and each matched 0 of 60.` |
| explore / usage | `Scores, changed answers and failed outputs tell different stories.` | CUT. The tabs already say which is which. |
| explore / repeat-note-stable | `Similar scores, different answers:` (Qwen 1.7B) | `Qwen 1.7B scored 8 and 9 of 60 on its first two decision-tree passes, and 30 of 58 shared valid reviews changed a label.` |
| index / rule | `That queue is the price of zero accepted errors on this set.` | `Zero accepted errors, 35 of 60 reviews sent to a person.` |
| index / limits | `A missing cost means unknown.` | `Missing costs are unknown, not zero.` Fine to keep. |

### Binary contrasts

| Page / section | Original | Rewrite |
|---|---|---|
| index / limits | `It is not a leaderboard.` / `Runs differ in route, interface, batch size, effort and prompt, so a ranking would compare unlike things.` | `Route, interface, batch size, effort and prompt differ across runs, so the order of scores is not an order of models.` |
| index / limits | `Nothing here is causal.` / `These are saved runs, compared after the fact.` | `Every comparison is after the fact, so no cause is claimed.` |
| index / limits | `It is not real-world accuracy.` / `The 60 reviews are synthetic, written by AI and enriched with concerns.` | `All 60 reviews are synthetic, written by AI and enriched with concerns.` |
| index / limits | `There are no speed claims.` | `Request times include network, batching and the operator, so no speed claim is made.` |
| index / limits | `Confidence thresholds here are hindsight.` | `No confidence threshold was chosen on held-out data, and Jev never abstained.` |
| index / gap | `An Opus pass is an API-equivalent estimate of $0.222052, not a bill.` | `An Opus pass costs about $0.22 at API rates.` |
| index / team | `Our fictional examples show what to investigate. They cannot tell you which system to deploy.` | `Take these to your vendor as questions.` |
| method / hero | `The results describe this test set, not performance with real candidates.` | CUT (Limits has it). |
| method / FAQ | `An API price estimate is not an observed charge.` | `Prices marked estimate are API-rate calculations.` |
| explore / story-specialist | `This measures agreement with draft answers, not verified accuracy.` | `Scored against draft answers; 3 labels are open to interpretation after human review.` |
| explore / story-repeat | `These are two selected local P1 passes, not the full three-pass result. Eleven comments changed at least one decision.` | `Two local P1 passes: 11 comments changed at least one decision.` |
| explore / usage | `Request time is client-observed and includes network and local work. It is not provider inference time.` | `Request time as our client measured it, network included.` |
| index / footer + method / footer | `Scores show agreement with a provisional reference, not deployment quality.` | `Scored against a provisional reference.` |

### Rhetorical setups

| Page / section | Original | Rewrite |
|---|---|---|
| index / overview h1 | `Do models like Jev get it right when correctness is business-critical?` | `Jev matched the reference on 54 of 60 reviews. General models matched 58 or 59.` Then define Jev once: today the word is never explained on the page. |
| index / overview lede | `roughly 4 to 40 times the estimated cost of a Jev pass` | `3.6 to 38 times the cost of a Jev pass.` The hover titles show 3.6 and 37.7; "4 to 40" is rounding that loses the number a reader would check. |
| explore / kev-prompt-analysis | `Did the added decision rules improve the same four answers?` | `Kev lost 3 matches to decision rules: P1 scored 49 of 60, P2 46, and 7 reviews changed an answer.` |
| explore / jev-prompt-analysis | `Did the categorical answers and probability distributions change together?` | `Jev scored 54 of 60 on first-pass P0, P1 and P2. P1 and P2 differed on 1 review, while native probabilities changed on 49 and vendor confidence on 45.` |
| explore / usage | `Which reviews improved?` (Qwen 1.7B) | `With thinking off, classifier instructions gained 4 all-four matches and lost 7; decision rules gained 9 and lost 5.` |
| method / FAQ | `Do score changes show that one prompt is better?` | `Prompt effects cannot be separated from where and when each run was made. Five earlier local Qwen comparisons lack base-run logs.` |

### Rule-of-three and list flourishes

| Page / section | Original | Rewrite |
|---|---|---|
| index / deep-insights hardest | `The hardest reviews are the disputed, off-topic and boundary cases, so the human queue should cover them first.` | `Three of the ten hardest reviews are disputed labels and one is off-topic. Route them to a person first.` |
| index / limits | `Runs differ in route, interface, batch size, effort and prompt` | Keep the list. It is a true list, not a flourish. |
| index / limits | `Recorded request times include the network, batching and the operator.` | Keep. Same reason. |
| explore / scores | `The 60 comments include praise, complaints, mixed experiences and unclear or off-topic text.` | `The 60 comments: 9 testimonial-worthy, 25 serious-concern, 35 needing follow-up.` Those three counts are in the page's own recall notes. A count beats a genre list. |
| index / FOR YOUR TEAM section | `Harassment, discrimination or a privacy breach, for example.` | Keep. It is a definition, not a flourish. |

### Throat-clearers

| Page / section | Original | Action |
|---|---|---|
| explore-top | `New here? Start with the three findings, or read how the test works.` | CUT |
| explore-top | `Every panel here reads the same 60 fictional reviews.` | CUT. "Same 60" appears 96 times on this page. |
| explore / how-it-works | `Select a step to see what each part means.` | CUT |
| explore / inspect | `Choose a saved run to read its comments, answers and source report. Technical request timing and usage details follow the score summary.` | CUT |
| explore / repeat-analysis | `Read a repeat result: check which full passes finished, compare matches out of the same 60 comments, then open the changed answers. An unfinished pass is not a zero.` | Rewrite: `An unfinished pass has no score. It is not a zero.` |
| explore / repeat-analysis | `A similar score can hide different decisions. Choose a model and setup below to compare its saved passes.` | CUT |
| explore / usage | `Search for a model to read what it got right, what it missed, and which tests support that finding.` | CUT |
| explore | `Choose a model configuration to compare its three planned passes. Completion is shown separately for each configuration.` | CUT |
| index / overview | `Hover a number to see the file it comes from; each section lists its sources.` | CUT |

### Condescension

| Page / section | Original | Rewrite |
|---|---|---|
| method / FAQ | `The model is the AI system. A prompt is the set of instructions and the comment it receives. A run is one recorded attempt to classify this set of comments using a particular setup.` | Move to a glossary the reader opens on purpose. The audience of a talk on classification benchmarks does not need "model" defined in the main flow. |
| method / FAQ | `Tokens are small pieces of text a model reads or produces. Hosted services often price requests by input and output tokens.` | Same. One line in the glossary. |
| explore / usage | `Fine-tuning or adaptation changes model weights; prompt instructions do not.` | Glossary. |
| explore / how-it-works | `We asked four questions about the same 60 comments.` | Fine. Plain, no change. |

Note on the FAQ: `Can I use these scores to choose a hiring tool? No.` is the right instinct. Keep that one.

---

## 3. The ten sentences that read most like a report generator

| # | Page / section | Original | Rewrite |
|---|---|---|---|
| 1 | index / overview | `A small, fictional test. AI wrote the reviews and drafted the reference. A person checked every label, and three remain disputed. Hover a number to see the file it comes from; each section lists its sources.` | `Sixty fictional reviews. AI wrote them and drafted the reference answers. A person checked every label, and three are still disputed.` |
| 2 | index / gap | `All-four matches out of 60 for each prompt version (P0, P1, P2) and fresh pass. Jev ran through OpenRouter's native Choice interface; its second P2 pass stopped after 17 valid responses and has no full score. Routes, interfaces and settings differ between the three, so this is not a ranking.` | `All-four matches out of 60, three prompts by three passes. Jev's second P2 pass stopped after 17 valid answers and has no score.` |
| 3 | index / deep-insights | `On 8 October 2026 the talk's analysis scripts recomputed every number in this section from the saved answers of 1,004 run-passes on the same 60 reviews, without new model calls. The recomputation corrected 8 earlier statements, listed at the end of this section, and produced the five findings in the cards below.` | `Five findings from 1,004 run-passes on the same 60 reviews. No new model calls.` The 8 corrections go to Method. |
| 4 | index / deep-insights (flips card) | `Implication: A decision model gives a fixed wrong list you can audit once; a general LLM gives a different wrong list each batch, so monitoring should count per-review flips, since totals can stay flat while answers change.` | `31 of 50 decision-model configurations never changed an answer across three passes. Only 11 of 202 general ones held still. So audit a decision model's misses once, and for a general LLM count per-review flips, because the total can stay flat while the answers move.` Numbers are the card's own. |
| 5 | index / deep-insights (cost card) | `SOLID Charges are exact and source-bound; frontier membership is descriptive-only; the gate-clearing pass is one pass, so the selection is anecdotal.` | `That 54 of 60 for $0.002681 was a single pass. The same setup scored 48 on its first fresh pass.` Pick a configuration only after the gate holds across three passes. |
| 6 | explore / run-ranking | `A complete run saved a result for all 60 comments. Some responses could not be scored because they did not follow the required format. Partial runs remain available in the run explorer below. Scores reflect saved outputs, not a controlled model ranking.` | `Complete means an answer saved for all 60 reviews. Malformed answers score as misses. 25 partial runs are listed separately.` |
| 7 | explore / usage | `Client-observed request attempts, including network and local work. Provider inference duration unavailable; summed requests are not one inference.` and `Totals exclude requests with missing usage. Reported development input/output usage; missing failed-request usage is unknown.` | `Request time as our client measured it, network included. Providers did not report inference time. Token totals leave out requests that returned no usage.` |
| 8 | explore / jev-prompt-results | `P2 pass 2 remains interrupted The original parent saved 17 valid responses, retained 1 HTTP 429 attempt with an unknown charge, and left 42 positions unsent. A separate continuation attempted those 42 positions: 40 valid, 1 invalid DEV-040, and 1 timed-out DEV-060 with an unknown charge. The combined accounting covers all 60 positions: 57 valid, 1 invalid, 2 unknown-cost attempts, and 0 unsent. Its 50/60 all-four figure is interrupted coverage, not a clean repeat or ranking result.` | `P2 pass 2 died after 17 answers on a rate-limit error. A second run covered the other 42: 40 valid, 1 invalid, 1 timeout. Together that is 57 valid answers and 50 of 60 matching. Two charges are unknown. We do not count it as a clean repeat.` |
| 9 | explore / cohort and agreement detail | `Recall uses 35 reference-yes reviews with a valid output. Another 0 reference-yes reviews had no valid output and are excluded from that rate. Precision uses all 30 saved yes predictions, including any against an insufficient-information reference.` The `Another 0 ...` clause is a template filling a blank. | `Recall is measured on the 35 reviews the reference marks yes, all with valid output. Precision is measured on all 30 yes predictions.` Drop the "Another 0" clause when the count is 0. |
| 10 | explore / models | `Purpose and training history are separate: a decision model can use a general LLM backbone. Fine-tuning or adaptation changes model weights; prompt instructions do not. This filter shows only source-verified task-specific training or adaptation. Other training history stays "not verified."` | `Filter by whether the model's weights were changed for this task. Anything we could not verify from a source says "not verified".` |

---

## 4. What the page is missing (the "info and benchmarks" half of the complaint)

The complaint has two halves. The meta clutter is the first. The second is that the page rarely lets the numbers speak.

- **Jev is never defined.** The h1 and lede name it, and no sentence on index says it is a specialist classification model. The first reader question is "what is Jev?" Answer it in the first screen, with its price per 60 reviews.
- **The hero has one cost ratio in a rounded range.** "4 to 40 times" hides 3.6 and 37.7, which the hover titles do know. Print the exact ratios and the two dollar figures ($0.0059 against $0.22).
- **Benchmarks are buried or tabled.** The best comparison on the site, the 42-row repeatability table and the confidence bin table, sits under process prose. Lead each card with the number, then one sentence.
- **Instructions where the data should be.** Roughly 79 instruction sentences in body prose and 39 more inside caveat blocks. Each is a sentence not spent on a result.
- **Good writing that should be the model.** The Qwen 0.6B paragraph (`This small local model returned all four labels in the required format in every pass. Yet no review matched all four reference answers. With the base prompt, it marked all 60 comments as potential testimonials; the reference key marks nine.`) and the hero's `Two were plain errors, and one of those was a harassment report it marked as needing no follow-up.` do the job: a fact, a number, a consequence. Edit the rest toward those.

## Suggested order of work

1. Delete the nine badges, the nine `Computed by` lines, the seven `SOURCES` lines, and the 104 hover titles. This is mechanical and removes about 130 elements.
2. Collapse the four repeated disclaimers into the Limits section and one Method paragraph.
3. Delete the 40 explore eyebrows and promote the three real claims to headings.
4. Strip `See / Read / Compare / Choose` tails and keep the link text.
5. Rewrite the ten sentences above, then re-run the scorers. Target: Flesch-Kincaid near 9 on index and formality near 3.
