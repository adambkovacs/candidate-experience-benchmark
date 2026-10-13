# Cold read of the public site

A visitor's pass over Read, Explore and Method at `feat/site-content-v2` (ffb9305a). Read-only: no site file was changed.

## What was captured

Served `public-site/` over HTTP with the verify folder's server, loaded each page in headless Chromium, scrolled the whole page so reveal and count-up observers fired, and waited until no visible "Loading…" or "Checking…" placeholder remained. All six loads finished with zero console errors, zero failed requests and zero stuck placeholders.

| File | What it is |
|---|---|
| `docs/site-pass/cold/index-desktop-part1..3.png` | Read at 1440x900, full page, in 6000 px slices (one capture was too tall) |
| `docs/site-pass/cold/index-mobile.png` | Read at 390x844, full page |
| `docs/site-pass/cold/explore-desktop.png`, `explore-mobile.png` | Explore, full page |
| `docs/site-pass/cold/method-desktop.png`, `method-mobile.png` | Method, full page |
| `docs/site-pass/cold/sections/*.png` | Every top-level block of `main` at 1440x900, one file each |
| `docs/site-pass/cold/rendered-text.txt` / `.json` | Rendered text per section after scripts ran, plus every `title` attribute |

Page heights: Read 15,532 px desktop and 28,657 px mobile; Explore 33,532 and 50,846; Method 2,305 and 3,118. The rendered Explore page carries about 65,000 words, most of them run ids inside pickers and review-id lists.

One capture caveat: the section shots of `#rule` were taken while its count-up was still running, so they show 13, 2, 15, 1 and 9. The rendered text and the full-page shot have the final 53, 7, 58, 2 and 35.

## The verdict in one paragraph

The site reads like an audit trail, not a benchmark. The numbers a visitor came for exist, but they are spread over 34 sections, wrapped in hedges, and the best material sits under a block titled "What changed on 8 October" or inside a collapsed "Explore the evidence behind the story" panel. There is no leaderboard of models. The ranking on Explore lists runs, so Clef and Jev each appear three times under raw ids such as `extended-typesafe-jev113-native-prompts-fresh1-p0`, with "not applicable" printed as the effort. Every number on Read carries a dotted underline and a hover title showing a JSON path, which is exactly the "hover a number to see the file" pattern Adam banned. Two cost labels contradict each other across pages, which undercuts trust more than any hedge protects it.

## 1. Section by section

Verdicts: KEEP means the section stays with light copy edits. REWRITE means the purpose is right and the copy or chart has to change. MERGE means its content moves into another section. CUT means remove it.

### Read (`index.html`)

| # | Section id and heading | What it literally says | What a visitor wants from it | Verdict | Why |
|---|---|---|---|---|---|
| R1 | `#overview` "Do models like Jev get it right when correctness is business-critical?" | Jev matched 54 of 60, general models 58 or 59 at 4 to 40 times the cost, so buy a rule that hands hard reviews to a person. | The answer, plus which models and what they cost, at a glance. | REWRITE | The answer is good, but it arrives before the test is explained, sits under a kicker, ends in a "hover a number" instruction and a sources line, and says "buy a rule" where Adam changed the deck to "create a rule". |
| R2 | `#decisions` "Every review gets four decisions." | Four question cards with their options and one worked example, DEV-003, with its key. | What was asked and what "matched" means. | KEEP | This is the clearest setup on the site. Drop the eyebrows, the sources line and the caption that repeats card 03's serious-concern definition. |
| R3 | `#gap` "The gap is five reviews." | Jev 54, 53, 52 against Opus 59, 58, 58 and Sonnet 58 nine times, shown as three 3x3 grids, with Jev missing a harassment follow-up. | Who scored what on every pass, and the cost of a pass. | REWRITE | The grids are the best chart on the site. The copy hedges the cost twice and the caption ends "so this is not a ranking". |
| R4 | `#hard-reviews` "The reviews that split the models are the ones a person pauses on." | Six review ids with orange bars counting how many of seven decision models missed each one. | The review text, the key and what the models answered. | REWRITE | Only DEV-029 shows its text. The other five are ids and bars, which breaks "question shown with every answer"; the full text lives in R7. |
| R5 | `#controls` "Neither confidence nor a longer prompt works as a gate." | Jev's calibration gap 0.011 against Clef Flash 0.358, 0.96 confident on a wrong testimonial, P1 to P2 raised 4 of 39 setups and lowered 21. | Can I trust the confidence score, and does a better prompt help? | REWRITE | "Gate" is the word Adam asked about ("what gates?"), "hit rate" was flagged in the deck review, and "calibration gap" is never explained. |
| R6 | `#rule` "Agree or defer." | Solar plus Perplexity accept 53 with 0 errors and defer 7; Qwen plus Gemma accept 58; 35 of 60 reach a person under the full policy. | What to do, what it costs, how big the human queue is. | REWRITE | The structure works. The copy carries "known charge", "observed", "pass-sensitive", "not a recommended production setup" and the queue sentence Adam struck from the deck. |
| R7 | `#deep-insights` "Recomputed findings from the saved answers" | Five finding cards, a 21-pair explorer, a calibration chart, the ten hardest reviews with text and keys, and eight SAID and CORRECTED pairs. | The richest benchmark content on the site. | MERGE | The findings belong with the other findings, the ten hardest belong in R4, and the corrections log is an internal changelog with repo paths. It is framed as "What changed on 8 October" and "Second-pass analysis", which tells a visitor nothing. |
| R8 | `#limits` "What this test does not show." | Eight bold disclaimers, starting with "It is not a leaderboard." | A short, honest scope statement. | MERGE | Eight hedges at the end of the main page read as defensive. Keep two or three lines on Read and move the full list to Method. |
| R9 | `#team` "Questions to ask before an AI pilot" | Generic advice for three roles, opening with "Our fictional examples … cannot tell you which system to deploy." | What should I do on Monday? | REWRITE | It explains basics to an adult audience. Adam's four steps from the deck (label 60 of your own cases, add can't-tell, run two cheap models, count the queue) are the content. |
| R10 | `#next` "Where to go next" | Links to Explore, Method and GitHub, and "classification-bench … is being open-sourced. Ask Adam for early access." | Where to dig further, and how to run this on my own data. | KEEP | The links are right. The classification-bench line uses the wording Adam removed from the deck. |

Also on Read: four part-mark dividers (`01 Three findings`, `02 The rule`, `03 What changed on 8 October`, `04 Limits`) are cut, see the metacomment list.

### Explore (`explore.html`)

| # | Section id and heading | What it literally says | What a visitor wants from it | Verdict | Why |
|---|---|---|---|---|---|
| E1 | `#explore-top` "Explore the saved runs." | Every panel reads the same 60 reviews; four jump cards to the inspector, ranking, review cases and pairs. | A table of contents for the data. | KEEP | Clear and short. |
| E2 | `#how-it-works` "We asked four questions about the same 60 comments." | A four-step clickable explainer of the test. | Nothing new after Read R2. | MERGE | Third copy of the test setup (Read R2, this, Method). Fold into Method and leave one line here. |
| E3 | `#scores` "What the scores mean" | Valid responses, all four match, each decision, each out of 60. | How to read a score. | MERGE | Belongs as two lines above the leaderboard, not as its own section. |
| E4 | `#report-lens` "Start with the models you want to examine." | Three group buttons, "121 closed saved runs in this view", "637 additional report-backed stages", and a five-step list. | A filter. | REWRITE | It is a filter bar presented as a section, with pipeline vocabulary ("report-backed stages", "source-bound catalog"). Make it the leaderboard's filter row. |
| E5 | `#outcome-chart` "A usable answer can still miss the reference." | Scatter of valid answers against all-four matches, default selection Laya at 0 of 60, and a 120-word caption naming five data feeds. | A chart that separates the models. | REWRITE | Every point sits at 58 to 60 valid answers, so the chart uses about a twentieth of its width. Cost against matches is the chart a visitor wants; keep the `outcome-*` ids on it. |
| E6 | `#run-ranking` "Compare models on the same 60 comments." | A list of saved runs, default filter decision models at P0, 8 of 54 shown, each row a raw run id with "not applicable" as effort. | The leaderboard. | REWRITE | It lists runs, not models, so Clef and Jev each fill three rows. It hides every general model by default and labels the same Clef cost "Known charge" that E17 calls an estimate. |
| E7 | `#inspect` "Read the comments behind a result." | Run picker over 1,004 run ids, scores per decision, timing, tokens and a cost block, then 60 rows reading "DEV-0xx · matches reference". | Pick a model, read each review next to its answer and the key. | REWRITE | The tool is right. The review list shows ids, not text, and the cost block alone has five qualifiers ("Unavailable", "not billed", "upper bound", "not a provider billing receipt", "smoke excluded"). |
| E8 | `#jev` "Historical Jev API run" | Jev base task 54 of 60, price an estimate, provider charge unavailable. | Nothing beyond the inspector. | MERGE | A one-model feature block; its copy contradicts Read R3 on whether Jev's cost is a known charge. |
| E9 | `#models` "Compare Jev with another saved run." | Pick a second run to compare with Jev. | A side-by-side of two models. | MERGE | The inspector already has "Compare A with B". One comparison tool is enough. |
| E10 | `#explore` "Did different instructions change the answers?" | P0, P1 and P2 defined in one line each, then three score cards for a chosen setup, plus a collapsed "Browse every saved run" ledger. | What the prompt levels are and whether they helped. | KEEP | The definitions are the best on the site. Move the collapsed all-runs ledger into the leaderboard. |
| E11 | `#usage` "Tokens, cost and measured time." | A second run picker with tokens, cost and timing for one run. | Nothing beyond the inspector. | MERGE | Duplicates the inspector's resource block. |
| E12 | `#cross-category` "Compare the same reviews across model roles." | Joins 149 general configurations with seven decision models, pick a pair, see where each matched. | Decision models against general LLMs, per decision. | REWRITE | This is the comparison Adam said he was missing, but it is built as a pair picker with "retrospective" and "declared cohort" language. It should show per-decision accuracy for both groups. |
| E13 | `#cohort-reviews` "Difficult reviews across selected runs" | All 60 reviews, seven decision models, first pass. | Same as E14. | MERGE | Same reviews, same seven models, same pass as E14. |
| E14 | `#review-evidence` "The same review can produce different decisions." | All 60 reviews with text; pick one to see seven decision models' answers. | Every review with its question, key and answers. | KEEP | Shows the review text. Absorb E13 and add the general models' answers. |
| E15 | `#agreement-policy` "Two models can agree and still be wrong." | The 21 decision-model pairs with accepted, errors, deferred and two-run charge. | Which pairs to try. | KEEP | Strong table. Cut the closing caveat paragraph and absorb the general-model pairs from Read R7. |
| E16 | `#reference-sensitivity` "What if three disputed labels changed?" | Rescoring under alternative keys for the three disputed reviews; the default state reads "0 under this hypothetical key". | How much the disputed labels move scores. | MERGE | Keep it on Explore next to the review cases (its id stays on Explore), and link it from Method's reference review. The default "0" reads like a broken result. |
| E17 | `#clef-first-pass` "Clef and Clef Flash: first-pass results" | One vendor's two models, one pass each, with "Published input-price estimate … Observed charge unavailable." | Clef's row in the leaderboard. | MERGE | A vendor-specific panel; the leaderboard covers it. |
| E18 | `#analysis-update` "Similar scores can hide changed answers." | Eyebrow "Analysis updated / 7 October 2026", Sonnet effort table, two analysis-caveat blocks, Liquid and Clef charts, a "What else changed" panel. | Repeatability across passes. | MERGE | A dated changelog. Its content is repeatability and belongs in one repeatability section with `#repeat-analysis`. |
| E19 | `#analysis-library` "Explore the evidence behind the story" | Collapsed on load. Holds the paired prompt comparisons, Kev and Jev prompt panels, repeatability, decision errors, observed spending and "comments worth a second look". | Cost per model, per-decision errors, repeats. | REWRITE | The cost and per-decision panels a benchmark reader looks for are hidden behind a closed toggle. Unfold them into top-level sections. |
| E20 | `#story` "What we learned from the answers." | Three chapters: Jev as a specialist, longer instructions, a Gemma run that changed 11 answers. | Nothing new after Read. | MERGE | Repeats Read's findings with older framing ("one historical TypeSafe API run", "For leaders assessing a pilot:"). Move the Gemma flip grid into repeatability and the prompt chart into prompt levels. |
| E21 | `#sources` "About these runs" | Repeats the fictional and provisional disclaimer. | Downloads. | CUT | The disclaimer appears on every page already. Replace it with a downloads block. |

Also on Explore: three part-mark dividers (`01 Results`, `02`, `03`) and an 18-item sticky sub-nav that overflows the header at 1440 px ("Agreei…" is cut off in the screenshots).

### Method (`method.html`)

| # | Section id and heading | What it literally says | What a visitor wants from it | Verdict | Why |
|---|---|---|---|---|---|
| M1 | `#method` "How we ran the test, and what it cannot tell you." | Prompt versions in one sentence, a timing paragraph, a cost-label paragraph and nine FAQs, including "What are tokens?" | The models tested, the prompts, the passes, how the key was built. | REWRITE | At 384 words it is the thinnest page. It has no model roster, no prompt text and no class balance, and it spends space on tokens and on "Can I use these scores to choose a hiring tool? No." |
| M2 | `#findings` "The reference answers were checked too." | A person checked all 60; DEV-006 has a proposed correction; DEV-013 and DEV-030 are judgment calls. | Which labels are disputed and why. | KEEP | Short and useful. Link to E16 and show the three reviews' text. |
| M3 | `#harness` "classification-bench" | "is being open-sourced. Ask Adam for early access." | How to run this on my own cases. | REWRITE | Uses the wording Adam removed from the deck; say what it does in one or two sentences instead. |

### Counts

| Verdict | Read | Explore | Method | Total |
|---|---|---|---|---|
| KEEP | 2 | 4 | 1 | 7 |
| REWRITE | 6 | 6 | 2 | 14 |
| MERGE | 2 | 10 | 0 | 12 |
| CUT | 0 | 1 | 0 | 1 |
| Sections | 10 | 21 | 3 | 34 |

Plus seven part-mark dividers to cut (four on Read, three on Explore).

## 2. Metacomments and provenance artefacts

Exact rendered text unless marked. Page and section id first.

### Sitewide

1. All pages, header: a rainbow scroll-progress rail and the rainbow AEA mark next to the title. Adam called the rainbow "overuse" on the deck.
2. All pages, footer: "An open experiment with 60 fictional comments. Scores show agreement with a provisional reference, not deployment quality."
3. Read, every number: 93 `title` attributes that show a feed path on hover, each drawn with a dotted underline. Examples: `Source: deep-insights-v1.json#denominator` on "60"; `Derived: SP#runs.opus55-high-batch10.estimateUsd / J#passes.P0.fresh1.knownCostUsd = 37.7` on "40"; `Derived: 6 misses minus 3 disputed labels (DI#reference_status) minus the off-topic DEV-029` on "Two".
4. Read, middle dots: 72 in the visible text. Explore uses them in nearly every run label ("not applicable · OpenRouter native Choice · P0 · solar-decide-native-fresh1-p0").
5. Read and Explore, eyebrow kickers: 12 on Read, 40 on Explore, 2 on Method. Several are slash paths: "RESULTS / CHOOSE A VIEW", "ANALYSIS / JOINED SAVED ANSWERS", "DEV-029 / FROZEN DEVELOPMENT REVIEW".

### Read (`index.html`)

6. Header nav: "8 October" as a menu item, a date with no meaning to a visitor.
7. `#overview` eyebrow: "A TALK COMPANION · AI ENABLEMENT ACADEMY".
8. `#overview`: "Hover a number to see the file it comes from; each section lists its sources."
9. `#overview`: "matched our provisional reference" and "for roughly 4 to 40 times the estimated cost of a Jev pass".
10. `#overview`: "SOURCES deep-insights-v1.json · findings.json · sonnet55-fresh-matched3.json".
11. `#overview` legend: "DEV-003, the example below." This is a meta caption of the "the orange point" kind.
12. `#decisions` eyebrows "THE TEST" and "ONE COMMENT, FOUR DECISIONS", plus "Comment DEV-003 of 60 · Inspect the answers".
13. `#decisions`: "These are the provisional reference answers. "Serious concern" has a specific definition here, including harassment, discrimination and privacy breaches. It does not mean every bad experience." It repeats card 03 directly above it.
14. `#decisions`: "SOURCES deep-insights-v1.json".
15. Part mark: "01 THREE FINDINGS".
16. `#gap` eyebrow "FINDING 1".
17. `#gap`: "A Jev pass cost $0.00589092, a known provider charge. An Opus pass is an API-equivalent estimate of $0.222052, not a bill."
18. `#gap`: "Twenty-five synthetic examples cannot show real-world sensitivity".
19. `#gap`: "DEV-059 · Inspect Jev's answers".
20. `#gap` caption: "Routes, interfaces and settings differ between the three, so this is not a ranking."
21. `#gap`: "SOURCES jev-native-prompt-findings.json · claude-roster-repeats.json · sonnet55-fresh-matched3.json · subscription-price-estimates.json · findings.json".
22. `#hard-reviews` eyebrow "FINDING 2" and caption "Decision models, out of seven, whose four answers differed from the reference on each review. Seven OpenRouter native models, first pass, base prompt."
23. `#hard-reviews`: "SOURCES deck/data/hard-cases.json · cross-category-v1.json", which exposes an internal deck folder.
24. `#controls` eyebrow "FINDING 3" and chart label "CALIBRATION GAP, LOWER IS CLOSER".
25. `#controls`: "Calibration figures are descriptive and look back at the same reviews. Jev never abstained, and no threshold was chosen on held-out data."
26. `#controls`: "SOURCES deep-insights-v1.json · findings.json".
27. Part mark: "02 THE RULE".
28. `#rule` eyebrows "WHAT TO DO ABOUT IT", "TWO DECISION MODELS", "TWO GENERAL MODELS".
29. `#rule`: "$0.03749436 known charge for both runs over all 60 reviews."
30. `#rule`: "$0.06854978 observed. This pair is pass-sensitive: other passes of the same two models give different counts."
31. `#rule`: "That queue is the price of zero accepted errors on this set." Adam removed this sentence from the deck.
32. `#rule`: "These counts look back at the same 60 development reviews. None of these pairs is a recommended production setup." and "SOURCES deep-insights-v1.json".
33. Part mark: "03 WHAT CHANGED ON 8 OCTOBER".
34. `#deep-insights` eyebrow "SECOND-PASS ANALYSIS" and "The talk's analysis scripts reran over the saved predictions … Each number names its place in the data file, which also lists the SHA-256 of every source file it was built from."
35. `#deep-insights`: "On 8 October 2026 the talk's analysis scripts recomputed every number in this section from the saved answers of 1,004 run-passes … The recomputation corrected 8 earlier statements".
36. `#deep-insights` confidence badges, five of them: "SOLID Counts are exact over saved answers. The decision vs general split is a working category split, so the comparison is descriptive-only." and "DESCRIPTIVE ONLY Answers pooled across stages come from the same development reviews, so they are not independent. No abstention policy was run, and the two confident errors are anecdotal."
37. `#deep-insights` script credits, six of them: "Computed by s02_confusion.py, s06_rare_classes.py from data.json, extended-cases-v1.json, additional-cases-v1.json. Numbers: deep-insights-v1.json."
38. `#deep-insights` card headline with the hedge inside it: "On these 60 reviews, Jev's confidence is calibrated on average (expected calibration error 0.011, descriptive-only) and still 0.96 on a wrong testimonial".
39. `#deep-insights` corrections log: "Corrections dated 8 October 2026" with eight SAID and CORRECTED pairs and internal paths such as "Source: public-site/supplemental-decision-runs-v1.json; docs/talk/06-cost-check.md section 1" and "Source: docs/talk/scripts/s07_repeatability.py".
40. `#deep-insights`: "Limits. The numbers describe saved runs; they rank no model and make no claim about cause. The reference is provisional, and three of its labels are disputed. A missing cost stays unknown and never counts as zero …"
41. Part mark: "04 LIMITS".
42. `#limits`: "It is not a leaderboard." followed by seven more disclaimers, including "A missing cost means unknown. Known charges, observed charges and API-equivalent estimates are labelled and kept apart.", and then "SOURCES deep-insights-v1.json" under a list of limits.
43. `#team` eyebrow "FOR YOUR TEAM" and "Our fictional examples show what to investigate. They cannot tell you which system to deploy." and "A high score on fictional examples is an early test, not deployment approval." These explain the obvious to an adult reader.
44. `#next`: "classification-bench, the tool that ran these tests, is being open-sourced. Ask Adam for early access."

### Explore (`explore.html`)

45. `#explore-top` eyebrow "EXPLORE".
46. `#how-it-works` eyebrow "THE TEST, IN FOUR STEPS" and "checked its answers against the same draft reference. Select a step to see what each part means."
47. `#scores` eyebrow "A KEY TO THE NUMBERS".
48. Part mark: "01 RESULTS".
49. `#report-lens`: "121 closed saved runs in this view · the same 60 reviews per run" and "A model can appear in more than one category. Each run appears once within a view; repeat passes reuse the same 60 reviews."
50. `#report-lens`: "637 additional report-backed stages are available in the chart and run explorer. View their source-bound catalog."
51. `#outcome-chart` caption: "Only closed 60-record runs appear in the chart. They come from the main feed, Sonnet first passes, Clef first passes, native decision-model feed, and report-backed repeat and continuation catalog. … The extended case feed and first-pass and native case feed link each answer to saved public evidence. … Agreement uses a provisional reference, not an independent measure of deployment quality."
52. `#outcome-chart`: "54 closed runs shown at 13 plotted points. 25 partial runs are excluded." and the category option "Classification pending source".
53. `#run-ranking`: "Each row is one saved run. Model, prompt and execution settings can differ." and "Scores reflect saved outputs, not a controlled model ranking."
54. `#run-ranking` row labels: "not applicable · TypeSafe API · P0 · typesafe-jev113-v2" and "Observed charge unavailable · Estimate $0.00589092".
55. `#inspect`: "COMPLETE · 60 / 60 SAVED · 60 / 60 VALID", "Known usage only", "Client-observed request attempts, including network and local work. Provider inference duration unavailable; summed requests are not one inference."
56. `#inspect` cost block: "Observed API charges Unavailable", "API price estimate, not billed $0.00589092", "Possible additional charge, upper bound $0.002123688", "Input-token price estimate, not a provider billing receipt. Development only; smoke excluded."
57. `#inspect`: "Result status: complete; observational native comparison" and "The same 60 development reviews · human-checked provisional labels v0.2. … The comparison chooser includes all 1004 saved runs. Different routes and controls are separate configurations; an A/B difference does not establish a causal model effect."
58. `#inspect`: "A public run feed" and "A source 1" as visible labels.
59. `#jev` eyebrow "HISTORICAL JEV API RUN" and "Routes and settings can differ. Jev's API price is an estimate; its provider charge is unavailable."
60. `#models`: "Prompt, settings and execution method may differ, so use the linked run notes before drawing conclusions."
61. `#explore`: "A blank card means there is no public result for that version. Other differences between runs may also affect the scores."
62. `#usage`: "Missing provider usage and charges are shown as unavailable. Request duration is a client measurement, while inference time requires a separate server measurement." and "Estimates and upper bounds are not provider bills. The extra amount is a reservation ceiling for one failed request."
63. Part mark: "02".
64. `#cross-category`: "This retrospective P0 view joins 149 general-model configuration passes … The selected pair is a view of the full declared cohort, not a recommended deployment choice."
65. `#cohort-reviews`: "Other specialist setups and later repeats are outside this panel." and "Across all 60 reviews: 7 distinct first-P0 configurations · 420 run-review positions · 75 differ · 0 unusable."
66. `#review-evidence`: "It does not combine repeat passes or cover every model in the wider benchmark."
67. `#agreement-policy`: "Retrospective test on the same 60 fictional comments … The provisional reference scores accepted answers after that choice; it does not decide which answers are accepted." and "All 21 pairs are shown below in source order. No pair was selected or tuned as a deployment choice."
68. `#agreement-policy`: "This excludes human review, smoke requests and any invoice difference." and "This is a retrospective 60-review study, not a measured deployment gain. The same comment appears in many pairs, and the 21 rows are not independent samples."
69. `#reference-sensitivity`: "This retrospective calculation rescored saved answers … It made no model calls. The frozen provisional references and published scores have not changed." and "These are hypothetical agreement changes … not corrections, out-of-sample gains, or a preferred model."
70. `#clef-first-pass`: "Published input-price estimate: $0.03184656. Observed charge unavailable." and "Published input-price estimates are not observed charges, and connected-app operator time prevents a pure inference-speed comparison."
71. `#analysis-update` eyebrow "ANALYSIS UPDATED / 7 OCTOBER 2026" and "These estimates are not subscription charges."
72. `#analysis-update` analysis-caveat block "The newer runs change the cost comparison." ending "these two saved runs do not establish a general model-family advantage or a full workflow price."
73. `#analysis-update` analysis-caveat block "Qwen 0.6B repeated the same mistakes." ending "These findings apply to this quantized model and local HTTP setup."
74. `#analysis-update` collapsed panel "What else changed in the analysis?" ending "These results cannot establish which change caused a difference." and the link "Download the calculations and source hashes".
75. `#analysis-library` eyebrow "DETAILED FINDINGS / FIVE INVESTIGATIONS" and numbered inner eyebrows "01 / Paired prompt comparisons", "02 / Decision errors", "03 / Observed spending", "04 / Comments worth a second look".
76. Part mark: "03".
77. `#story` eyebrows "THREE FINDINGS FROM THE SAVED ANSWERS", "01 / A specialist alongside chat models", "02 / Longer instructions did not consistently help", "03 / The same instructions can give different answers".
78. `#story`: "For leaders assessing a pilot: ask for repeat results and examples of changed answers." and the bold-lead tip "check the type of mistake."
79. `#story`: "This measures agreement with draft answers, not verified accuracy." and "These first recorded pass results show an association. They do not prove that the added words alone caused a score change."
80. `#story`: "These are two selected local P1 passes, not the full three-pass result. … This illustration does not compare inference speed." and "Squares follow DEV-001 to DEV-060."
81. `#sources` "About these runs": "AI wrote these fictional comments and drafted the reference answers. A person checked all 60 answers; some remain disputed. Historical scores retain the original reference version."

### Method (`method.html`)

82. `#method` eyebrow "METHOD AND LIMITS".
83. `#method`: "Cost: Reported API charges, price estimates and possible charges without a known bill are labeled separately. Subscription fees are not split across runs. An API price estimate is not an observed charge."
84. `#method`: "Historical scores retain the original reference version." appears twice on the same page.
85. `#method` FAQ: "What are tokens, and why do they matter?" and "Can I use these scores to choose a hiring tool? No." These pitch below the audience.
86. `#findings`: "The charts retain the original answers so historical results remain inspectable."
87. `#harness` eyebrow "TOOLING" and "classification-bench, the tool that ran these tests, is being open-sourced. Ask Adam for early access."

Count: 87 items. Hedge-word totals in the rendered text: "provisional" 25 times, "estimate" 21, "fictional" or "synthetic" 22, "unavailable" 19 (Explore), "descriptive-only" 7 (Read), "retrospective" or "hypothetical" 11 (Explore).

### Contradictions a visitor will notice

These do more damage than the hedges, because they make the careful labelling look wrong.

1. **Jev's cost.** Read `#gap` calls $0.00589092 "a known provider charge". Explore `#run-ranking`, `#inspect` and `#jev` call the same number an estimate with the provider charge unavailable.
2. **Clef's cost.** Explore `#run-ranking` labels $0.03184656 "Known charge". Explore `#clef-first-pass` labels the same figure "Published input-price estimate … Observed charge unavailable". `#analysis-update` calls it a "recorded development charge".
3. **Jev's route.** Read `#gap` says Jev "ran through OpenRouter's native Choice interface". Every Jev row on Explore says "TypeSafe API" or "TypeSafe native Choice API". This needs a check against the feed before anything is rewritten.
4. **Who beat Jev among decision models.** Explore's ranking puts Solar Decide first at 55 of 60. Read never mentions it and frames Jev at 54 as the decision-model result.

### Mobile

No page scrolls sideways at 390 px. Two tables extend past the viewport: one on Read at 500 px wide and the review-id table in Explore `#cross-category` at 662 px. I did not verify whether they sit in a scroll container or are clipped.

## 3. What a benchmark reader expects, and where it is

| Item | Status | Where it lives now |
|---|---|---|
| Leaderboard of all models with matched-of-60 per pass and cost per pass | MISSING | No model-level table exists. Explore `#run-ranking` lists runs, default filter decision models at P0 (8 of 54 rows), one cost per row with varying labels. The full run ledger is collapsed inside "Browse every saved run" in `#explore`. Read `#gap` has per-pass grids for three models only. |
| Model roster: which models, how many, decision or general, hosted or local | MISSING | Only recoverable from run-id dropdowns. No sentence on any page says how many models were tested. |
| What a decision model is, and System 1 against System 2 | MISSING | Not explained anywhere, though Adam's brief and the talk blurb promise it. |
| Per-decision accuracy (sentiment, follow-up, serious concern, testimonial) across models | BURIED | One run at a time in `#inspect`, one setup at a time via the metric picker in `#explore`, aggregate "insufficient information" counts in Read `#deep-insights` card 1, and "02 / Decision errors" in the collapsed `#analysis-library`. |
| Decision models against general LLMs | BURIED | `#deep-insights` cards 1 and 4 on Read, `#cross-category` on Explore as a pair picker. |
| Hard reviews with question, key and answers | BURIED | Read `#hard-reviews` shows ids and bars with one text. The full text, key and most common wrong answer for the ten hardest sit in `#deep-insights` under "What changed on 8 October". All 60 texts are in Explore `#review-evidence`. |
| Repeatability across passes | BURIED | Three models on Read `#gap`; aggregate counts in `#deep-insights` card 4; the full comparison in `#repeat-analysis` inside the collapsed library and in `#analysis-update`. |
| Prompt levels: definitions, prompt text, effect | BURIED | Clear definitions in Explore `#explore` and one sentence in Method. On Read, P0, P1 and P2 appear in results before they are defined. The prompt text itself is not on the site. |
| Cost per model, cost against accuracy | BURIED | Per run in `#run-ranking` and `#inspect`; "03 / Observed spending" is in the collapsed library. No cost-against-matches chart. |
| Model pairs under agree-or-defer | PRESENT | Read `#rule`, Read `#deep-insights` pair explorer, Explore `#agreement-policy` with all 21 decision-model pairs. |
| Confidence and calibration | PRESENT | Read `#controls` and `#deep-insights` calibration card and chart. |
| Off-topic input (the soup review) | PRESENT | Read `#hard-reviews`. |
| The 60 reviews and the key | PRESENT | Explore `#review-evidence` lists all 60 texts. Class balance of the key is not shown. |
| Method summary | PRESENT | Method `#method`, but thin: no roster, no prompt text, no pass design table. |
| Disputed labels and their effect | PRESENT | Method `#findings` and Explore `#reference-sensitivity`. |
| What to do on Monday | PRESENT | Read `#team`, but generic; Adam's four concrete steps are not used. |
| Downloads (all results as CSV or JSON, repo) | BURIED | Scattered "SOURCES" footers and inline "Download the calculations and source hashes" links. No single downloads block. |
| Speed or latency | MISSING | Intentionally excluded ("There are no speed claims"). Fine to keep missing; say so once in Method. |

Count over 18 rows: 4 MISSING (leaderboard, roster, decision-model explainer, speed), 7 BURIED (per-decision accuracy, decision against general, hard reviews, repeatability, prompt levels, cost, downloads), 7 PRESENT. Speed is missing on purpose, so 3 of the 4 gaps need work.

## 4. Proposed outline for a benchmark-first site

Rules applied throughout: no source footers, no hover titles with feed paths, no dotted underlines on numbers, no eyebrows or part marks, no middle dots, one cost vocabulary used the same way everywhere, every chart titled and axis-labelled, every review shown with its text and the four answers. The "fictional set, provisional key" scope is said once on Read and once on Method, not per section. Ids from LINK-MAP stay on the element that now holds that content; where a section is absorbed, its id moves onto the absorbing block or an anchor inside it, so every existing link still lands somewhere sensible.

### Read (`index.html`): the benchmark in five minutes

1. **`#overview`** (keeps `#top`, `#main`, `#page-title`). The question, the one-paragraph answer with numbers, and a compact top-ten strip: model, type, best and worst all-four of 60 across passes, cost per pass. Purpose: answer the visitor's first three questions above the fold.
2. **`#decisions`** (keeps `#example-title`). The test in plain words: 60 short reviews, four questions with their options, "matched" means all four, P0, P1 and P2 in one line each, three fresh passes, how many decision models and general models. The DEV-003 example stays. Purpose: setup before results.
3. **New: what a decision model is.** Two columns: what a decision model does in one pass, and what still needs a second look. Purpose: the System 1 and System 2 framing Adam asked for.
4. **`#gap`**: Jev against the big general models. The three 3x3 grids, the cost of a pass in one plain sentence, the DEV-059 miss with its text. Mention Solar Decide at 55. Purpose: finding one, with every pass shown.
5. **`#hard-reviews`**: the reviews that split the models. Each of the six, then the rest of the ten hardest, as a card with the review text, the reference answers, how many models matched it and the most common wrong answer. Absorbs the ten-hardest block from `#deep-insights`. Purpose: question shown with every answer.
6. **`#controls`**: confidence and longer prompts. Retitled in plain words ("A confident answer can still be wrong, and longer prompts made more setups worse"), with the calibration chart titled and explained in one sentence. Purpose: finding three.
7. **`#deep-insights`** (keeps `#deep-insights-title`): more findings. The four remaining cards as findings four to seven, each with a headline sentence carrying its number, no badges and no script credits. Purpose: the extra insights, framed as findings rather than a changelog.
8. **`#rule`**: agree or defer. Both pairs, the queue of 35, the routing breakdown. Purpose: what to do about it.
9. **`#team`**: what you should do. Adam's four steps. Purpose: Monday actions.
10. **`#limits`**: three lines on scope, with a link to the full list on Method. Purpose: honest scope without a wall of hedges.
11. **`#next`**: Explore, Method, GitHub and classification-bench in Adam's current wording. Purpose: where to go next.

### Explore (`explore.html`): the data room

1. **`#explore-top`** (keeps `#explore-top`): one line and jump links to each block below.
2. **`#run-ranking`**: the leaderboard. One row per model setup, not per run. Columns: model, type, route, effort, all-four of 60 for each pass under P0, P1 and P2, best and worst, per-decision accuracy, cost per pass. Sortable, with the group filter from `#report-lens` and the filters from the all-runs ledger (`#search`, `#condition-filter`, `#family-filter` and the rest) as its toolbar; Clef's first-pass rows from `#clef-first-pass` become ordinary rows. Ids from `#report-lens`, `#comparison-list`, `#clef-first-pass` and `#scores` move here. Purpose: the table a benchmark visitor came for.
3. **`#outcome-chart`**: cost per pass against all-four matches, log cost axis, coloured by type. Keeps every `outcome-*` id. Purpose: the price and accuracy trade-off in one picture.
4. **`#cross-category`**: decision models against general LLMs, per decision, including how often each group answered "can't tell" when the key says so. Absorbs `#finding-jev` and `#jev-analysis` from the library. Purpose: the comparison Adam said he was missing.
5. **`#review-evidence`**: every review. All 60 texts, hardest first, each with the key and every model's answers. Absorbs `#cohort-reviews`; `#reference-sensitivity` sits directly below as the disputed-label view. Purpose: read any review and see who got it right.
6. **`#agreement-policy`**: every pair. The 21 decision-model pairs plus the general-model pairs from Read's pair explorer, one table. Purpose: pick a pair.
7. **`#repeat-analysis`**: repeatability. How many answers changed across three passes for each setup, the Gemma flip grid, the Sonnet effort table, the Clef and Liquid charts. Absorbs `#analysis-update`, `#story-repeat` and the repeat notes. Purpose: does the next run give the same answers.
8. **`#explore`**: prompt levels. The definitions, the actual prompt text for P0, P1 and P2, the per-setup comparison, the 39-setup chart. Absorbs `#prompt-analysis`, `#kev-prompt-analysis`, `#jev-prompt-analysis` and `#story-prompts`. Purpose: did the instructions help.
9. **`#cost-analysis`**: cost. Cost per pass for every model with one label scheme, and the full study cost. Purpose: what it cost.
10. **`#inspect`**: run inspector. Pick a run, read each review's text next to its answer and the key, compare with a second run. Absorbs `#jev`, `#models` and `#usage`; timing and tokens sit in a collapsed panel at the end. Purpose: check any number down to the answer.
11. **`#sources`**: downloads. One block with every results file, the scripts and the repo. Purpose: take the data away.

`#analysis-library`, `#story` and `#how-it-works` stop being sections; their ids stay as anchors on the blocks that absorbed them (library to repeatability, story to prompt levels, how-it-works to the leaderboard intro).

### Method (`method.html`): how it was run

1. **`#method`**: how we ran it. The dataset and how the reviews and key were made, the class balance of the key, the four questions with definitions, the prompt levels with links to the prompt text, a roster table of every model with type, route and effort, the pass design, how a score is counted, and one paragraph on how costs are labelled. Keep two or three FAQs that a technical reader actually asks.
2. **`#findings`**: the reference review. The three disputed reviews with their text and the alternative labels, linking to the rescoring on Explore.
3. **New: limits.** The full list moved from Read `#limits`.
4. **New: corrections.** The 8 October correction log moved from Read `#deep-insights`, for readers who want the audit trail.
5. **`#harness`**: classification-bench. What it does in two sentences, in Adam's current wording.
