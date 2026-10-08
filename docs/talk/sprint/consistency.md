# Consistency lane: slide numbers and claims against the site and the docs

Claim tested: "every number and claim on a slide matches the site and the docs."
Verdict: refuted in a small way. No headline number is wrong. Seven items need a fix or a decision (section 1).

Evidence base. Deck text came from `review-capture.mjs` (34 slides, 19 main plus 15 backup) and the notes in the same capture. Pinned SHA is 35cdc4c8. The working tree also carried uncommitted director edits to `charts.js`, `content.js`, `heroes.js`, `review-card.js` and `motion.js`. `presentation.html` itself was unchanged, so slide copy and notes are from the pinned SHA. Site text came from rendering `index.html`, `explore.html` and `method.html` in a served browser (files in `consistency-cap/site-*.txt`). Feeds were read directly. Docs: 01, 01b, 02, 03, 04, 06, 07, 08 in `docs/talk/`, plus `docs/FINDINGS.md`, `docs/REFERENCE_REVIEW_V1.md`, `docs/PILOT_AUDIT.md`, `docs/LABELING_GUIDE.md`, `docs/MVP_STATUS.md`.

## 1. What to fix or decide (ordered by risk on stage)

1. **Slide 2 headline, "four to forty times".** The slide pins 4x to 40x on "Opus and Sonnet". Opus 5.5 high is about 38x ($0.222 over $0.00589). Sonnet 5.5 xhigh is about 21x ($1.107 over nine cells, $0.123 a pass). The 4x end is Gemma 26B (about 3.6x). The site says "General models, from Gemma 4 26B up to Opus 5.5, matched 58 or 59, for roughly 4 to 40 times". Fix: say "about 20 to 40 times" for Opus and Sonnet, or name Gemma for the low end. (MISMATCH)
2. **Slide 13, "Each one is hard for a reason you can name."** The site says "Most of Jev's 6 misses sat on reviews a person would pause on. Two were plain errors." Doc 01 says DEV-027 and DEV-059 are clear errors under the guide. The slide's own cards label them "kindness during a logistics failure" and "serious concern without a complaint", which are reasons, but they are errors, not hard calls. Fix: "Four of the six are judgment calls. Two are plain errors." (MISMATCH)
3. **Slide 13 and the site show two different "sixes".** The slide shows the six Jev missed (DEV-030, 006, 013, 029, 027, 059). The site shows the six that split four or more of the seven decision models (same list but DEV-056 in place of DEV-059). The slide note already says so. A viewer who opens the site after the talk will see DEV-056 and not find DEV-059 in that list. Decide whether to say it out loud. (MISMATCH, presentation)
4. **Slide 9, "44 runs from 7 model families".** Matches the site ("Model families in that one set: 7"). Doc `05r2-outline-review.md` R4 says this overstates: they are seven models from three vendors, and 34 of the 44 are OpenAI GPT. `01b-deep-analysis.md` Q7 lists gpt-6-astra, gpt-6-sol, gpt-5.6-sol, fable-5.1, sonnet-5, opus-5.5, gemini-3.6-flash. Safer wording: "seven models from three vendors". The site wording should change too. (MISMATCH against the docs, MATCH against the site)
5. **Slide 17 versus the site, same 35.** Slide: 25 flagged, 25 auto-accepted, 10 other. Site and `native_routing` feed: 7 deferred, 24 escalated for concern, 4 sent for clarification. Totals agree (35, and 25 auto-accepted). The feed has `concern_any` 25 (24 plus one concern flag that sits inside the 7 deferred), so the slide's 25 is right. The "10" is derived (35 minus 25) and appears in no feed or page. Backup A9 adds "7 said can't tell", which is `insufficient_any`, not the 4 on the site. Three splits of the same 35 will confuse anyone who compares. Pick one split on slide, site and backup. (MISMATCH, presentation)
6. **Slide 19, "Reuven's @ruvector/typesafe is a free local classifier."** No doc names Reuven. `08-ruvector-decision-probe.md` says only that the package lives in ruvnet/ruvector. The attribution is probably right (Reuven "rUv" Cohen is speaking at the same meetup per `00-adam-brief.md`) but it is not in our docs, so confirm with Adam. "Free local" is true. Doc 08 also says the published npm 0.2.0 binary ships only a hash test embedder that "carries no meaning on real text", and real use needs a source build. "Candidate relevance check, no accuracy number" matches doc 08 exactly. (UNSUPPORTED name, MATCH otherwise)
7. **Backup A2, "Every open follower is a frozen Qwen or Gemma backbone with a small head or adapter".** Copied from `02-landscape.md` line 67, but the same slide lists Liquid d1-3B, which doc 02 B-section says is built from LFM2.5-VL-3B (not Qwen or Gemma). Tev1 is a LoRA SFT that keeps the normal LM head. "Frozen" is wrong for every LoRA or SFT follower. Fix: "Most open followers are a Qwen or Gemma backbone with a small head or adapter." (MISMATCH, backup only)

Lower-risk notes (not counted as mismatches):
- **Slide 18 and A7, "433 tests".** `04-harness.md`: "433 tests, OK, 44 skipped" (jsdom missing). "Passing" is fine, "all green" would not be.
- **A5 and slide 6, "people checked all 60 on 2 October".** `REFERENCE_REVIEW_V1.md`: the owner confirmed on 2 October that people had checked. The date is the confirmation, not the check. The site method page says "A person". Plural is in the docs, singular on the site.
- **Slide 15 note, "60% of the time".** External (Kim et al., HELM, 71 models, `07-remedies.md`), not from this test. The note does not say so. Same for "200 labels" (Bucher and Martini 2024).
- **Slide 5, Perplexity on 7 October.** `02-landscape.md` dates the Perplexity release 1 October (secondary source). `timeline.json` and the slide use 7 October, the OpenRouter listing, which is the verified date. This is a deliberate choice and the note says so. The tested model is "Perplexity Decider V1 27B" while the OpenRouter listing on 7 October is V1.1.
- **Slide 10, "tells X and Reddit".** Rhetorical. `07-remedies.md` records no reliable figure for how often candidates post bad experiences ("UNVERIFIED"). The one cited Reddit case is about a rejection email, not a classifier miss.
- **Slide 4 and 8, "Jev caught all 25".** The site adds "Twenty-five synthetic examples cannot show real-world sensitivity". The slides drop the caveat.
- **Slide 8, Opus "$0.22".** Slide text no longer carries the word estimate (hedges were removed per Adam). It is an API-equivalent estimate of subscription use, not a bill. Slide 2 says "estimated cost" and the note says "API-equivalent estimate".

## 2. Known traps, checked

| Trap | Result |
|---|---|
| Nine runs only where complete | Slide 7 and A3 show blanks and "stopped". Jev has eight complete runs (P2 pass 2 stopped after 17 valid). Opus, Sonnet and Gemma show nine. Qwen shows one pass per prompt. MATCH. |
| Jev 54/53/52 on OpenRouter versus 54 direct | Slide 2 labels 54 "direct API, first P0 pass" and 54, 53, 52 "OpenRouter repeats". Slide 7 and A3 label the grid "via OpenRouter, native". Site matches. The 55 offline rescore in `answer.json` is not used. MATCH. |
| Soup: 0 of 7 decision models, 89 of 113 general configs | Slides 9, 11, 12, A14 all agree. Feed: 113 valid, 89 all-four matches. Site: "0 of 7 ... 89 of 113". The corrected "four of seven said mixed" is right on slide 12. MATCH. |
| Majority voting +0.14 of 60 | Slide 15: "0.14 more matches per 60". `07-remedies.md` section 3: 145 general groups, mean +0.14. Jev vote never beat best pass (54 in five conditions, 53 in one). Not on the site. MATCH. |
| Full policy routes 35 of 60 (7, 24, 4) | 35 matches. The slide uses a different split. See item 5. |
| P1 to P2 moves 4/14/21 | Slide 15 and A3 label it "P1 to P2, adding the tree: 4 up, 14 same, 21 down". P0 to P1 is 15/15/9. Site matches. The old mislabel in `05r-outline-review.md` B2 is fixed. MATCH. |
| Study cost $12.65 plus up to $3.88 reservations | Not stated on any slide or note. The only study-level cost line is the Q+G pair ($0.069 observed). `06-cost-check.md` totals are consistent with each quoted per-run figure. N/A, nothing to mismatch. |
| Typesafe is a candidate relevance gate with no accuracy number | Slide 19 says "a candidate relevance check" and shows no accuracy figure. MATCH with doc 08. See item 6 for the name. |

## 3. Claim table

Slide ids are the capture ids. Site column: what the rendered page or its feed says. Doc column: which doc. "feed" means the bound JSON agrees (also checked by `numbers.mjs`, not re-run here).

| Slide | Claim | Site says | Doc says | Verdict |
|---|---|---|---|---|
| title | 60 reviews; example is the harassment review (DEV-059) | 60; DEV-059 shown | 01 | MATCH |
| title | System 1 is Kahneman's term and TypeSafe borrowed it | not on site | 02 A3 quotes TypeSafe | MATCH |
| answer | Jev matched 54 of 60 | 54 | 01 insight 1 | MATCH |
| answer | Opus and Sonnet matched 58 or 59 | Opus 59/58/58, Sonnet 58 | 01 | MATCH |
| answer | "four to forty times the estimated cost" | "4 to 40 times", range spans Gemma 26B to Opus | 01 section 1 ("frontier LLMs") | MISMATCH (item 1) |
| answer | 5 reviews Opus matched and Jev missed | "The gap is five reviews" | 01: Opus matched 5 of Jev's 6 misses, kept all 54 | MATCH |
| answer | OpenRouter repeats 54, 53, 52; Opus 59, 58, 58 | same | 01, 07 corrections | MATCH |
| answer | Matched means agreeing with the key, not right | provisional reference wording | 01 | MATCH |
| about | Six years at Amazon | not on site | 03: Dec 2015 to Jan 2022 | MATCH |
| about | Co-founder and Chief AI Strategist; Agentics Foundation co-founding member and International Ambassador; Executive Director OPEN Talent Society | not on site | 03 | MATCH |
| about | Builds hands-on training and open benchmarks on recruiting problems | not on site | 03 line 123 | MATCH |
| about | github.com/adambkovacs | n/a | git remote | MATCH |
| decision-models | Decision model returns one of your options and a probability in one pass | n/a | 02 section A | MATCH |
| decision-models | Jev caught all 25 serious-concern reviews | "matched all 25" (with caveat) | 01 insight 1; feed: key has 25 yes | MATCH |
| decision-models | System 1 can't invent a label; System 2 reads literally, misses questions that don't apply | n/a | 02 A3 table, 08 | MATCH |
| launch-wave | Jev shipped 15 September | n/a | 02 timeline | MATCH |
| launch-wave | Nearly 13% of paid teams on Vercel AI Gateway within a day | n/a | 02 (Vercel blog, 24 hours) | MATCH |
| launch-wave | Cloudflare and AWS shipped 1 October | n/a | 02 | MATCH |
| launch-wave | OpenAI Decisions public beta 6 October | n/a | 02 | MATCH |
| launch-wave | Perplexity Decider listed on OpenRouter 7 October | n/a | 02 timeline says 10-01 (secondary) and 10-07 (OpenRouter) | MATCH (documented choice) |
| launch-wave | Credit to TypeSafe for a failure-mode page | n/a | 02 (nine failure modes) | MATCH |
| launch-wave | Ticks: Solar Decide, Kev, Nimble, AnyJev, Ollama, Liquid d1 | n/a | `timeline.json`, 02 | MATCH |
| what-we-did | Four questions and their options; concern excludes a bad experience alone | same wording | 08 section 2, LABELING_GUIDE | MATCH |
| what-we-did | AI drafted reviews and key, people checked 60, three disputed | "A person checked", three disputed | FINDINGS, REFERENCE_REVIEW_V1 | MATCH (plural vs singular, see notes) |
| what-we-did | 39 hosted and subscription setups ran P0, P1, P2 | n/a | FINDINGS, 01 insight 4 | MATCH |
| nine-runs | Jev grid 54/54/54, 53/53/stopped, 52/54/54 | same | `prompt-levels.json`, 01 | MATCH |
| nine-runs | Opus grid 59/59/59, 58/59/58, 58/58/58 | same | 01, feed | MATCH |
| nine-runs | Sonnet 58 in all nine | same | 01 | MATCH |
| nine-runs | Gemma 26B 59/58/57, 56/58/56, 58/57/56 | n/a | README line 80 (P0 59,56,58; P1 58,58,57; P2 57,56,56) | MATCH |
| nine-runs | Qwen3.8 27B low 59/56/53, one pass each | n/a | outline v2.3 note (05r3) | MATCH |
| nine-runs | Jev 52 to 54, Opus 58 or 59, "gap held in every run that exists" | same | 01 | MATCH (true for Jev vs Opus only) |
| pass-cost | Jev pass $0.006 | "$0.00589092, a known provider charge" | 06: known via OpenRouter, estimate if direct | MATCH |
| pass-cost | Opus pass about $0.22 | "$0.222052 API-equivalent estimate, not a bill" | 01, 06 | MATCH (see notes) |
| pass-cost | Jev still said no follow-up at 0.49 on the opening review | feed, 0.49 | 01 insight 3 | MATCH |
| general-models | Gemini 3.1 Pro 56 at $0.063, 55 at $0.257 | n/a | 06 table, feed | MATCH |
| general-models | 89 of 113 general setups said can't tell on all four (soup) | "89 of 113 did" | cross-category feed | MATCH |
| general-models | 44 runs from 7 model families, one identical answer set | "Model families 7" | 01b Q7, 05r2 R4 | MISMATCH vs docs (item 4) |
| general-models | 31 of 50 decision groups unchanged, 11 of 202 general | same | 01b section 12, `determinism` | MATCH |
| consequences | Perplexity 54 of 60 in all nine runs, same six misses | n/a | 01 insight 6 (540/540 valid) | MATCH |
| consequences | Missed report makes the candidate tell X and Reddit | n/a | 07: no reliable figure | UNSUPPORTED (rhetorical) |
| zero-of-seven | 0 of 7 decision models matched the key | "0 of 7" | hard-cases feed | MATCH |
| zero-of-seven | Seven answer rows (Tev, Clef, Clef Flash, Luna mixed; Solar negative; Liquid and Perplexity can't tell) | feed | A14, `disputed-reviews-v1.json` | MATCH |
| zero-of-seven | Jev's saved answer mixed/no/no/no, no concern at 0.91 | "0.91" | `results/openjev/...reconciled.jsonl`, 01 | MATCH |
| hard-six | The six are exactly Jev's six misses; three have disputed labels | site's six differ (DEV-056 for DEV-059) | 01 insight 2 | MATCH (and item 3) |
| hard-six | "Each one is hard for a reason you can name" | "Most ... Two were plain errors" | 01: DEV-027 and DEV-059 are clear errors | MISMATCH (item 2) |
| hard-six | Models matched 0, 0, 1, 2, 3, 5 of 7 for the six cards | feed | A13 to A18 | MATCH |
| hard-six | Histogram 26/15/12/1/2/1/1/2 over 60 | feed | `hard-cases.json` | MATCH |
| hard-six | Saved passes 144, 661, 262, 287, 713 of 1,004 | "1,004 run-passes" | `hardest_reviews` (800 for DEV-027 not in the top 10, not re-checked) | MATCH (5 of 6) |
| still-wrong | Pooled gap 0.011 (Jev) and 0.358 (Clef Flash) over 720 answers | same | 01b section 8 | MATCH |
| still-wrong | 0.96 on the wrong testimonial (DEV-027); 0.88 on the soup | 0.96 | 01 insight 3 | MATCH |
| still-wrong | 0.9 gate keeps 54, 0.7 and 0.5 keep 58, testimonial field | A4 table 58/58/54 | 01 insight 3 | MATCH |
| still-wrong | 0.9 gate would have caught the follow-up miss at 0.49 | feed | 01 | MATCH |
| more-instructions | P0 to P1 15/15/9; P1 to P2 4/14/21; tree lowered 21 of 39 | same | FINDINGS, 01 | MATCH |
| more-instructions | Clef 54, 51, 49 every pass | n/a | `prompt-levels.json` | MATCH |
| more-instructions | Vote of three gave strong general models +0.14 per 60 | not on site | 07 section 3 (145 groups) | MATCH |
| more-instructions | Voting Jev's three passes never beat its best pass | not on site | 07 | MATCH |
| more-instructions | Fine-tuning pays off around 200 labels; we have 9 testimonials | feed: 9 yes | 07 (external source), 01 | MATCH |
| more-instructions | Clef route may read about 2,000 state tokens | n/a | 05r Q&A 7, A3 | MATCH |
| agree-or-defer | Q+G accepted 58, 0 errors, 2 to a person, $0.069 observed | "$0.06854978 observed", pass-sensitive | 01b section 11 ($0.0686), 10-deck-verification R9 | MATCH |
| agree-or-defer | Five of 21 pairs let zero errors through; six accepted the soup | corrections: five | 01, 01b | MATCH |
| queue | 35 reach a person, 25 auto-accepted | 35; 24 escalated, 7 deferred, 4 clarification | `native_routing` | MATCH (item 5 on the split) |
| queue | 25 flagged and 10 other | 24 plus 7 plus 4 | feed `concern_any` 25 | MISMATCH (presentation, item 5) |
| queue | Set is concern-heavy by design | n/a | key: 25 of 60 concern yes | MATCH |
| classification-bench | 433 tests | n/a | 04: 433 OK, 44 skipped | MATCH (see notes) |
| classification-bench | OpenRouter and Cloudflare routes live; Claude Code and Codex wired | n/a | 04: small live smokes; subscription adapters untested live | MATCH |
| classification-bench | Being open-sourced, not public yet | n/a | 04 badge guidance | MATCH |
| monday | Repo URL and "every scored answer is in the public repo" (note) | n/a | git remote; repo is public (checked with `gh`) | MATCH on URL and visibility; "every" not checked |
| monday | "Reuven's @ruvector/typesafe is a free local classifier" | n/a | 08 | UNSUPPORTED name (item 6) |
| monday | A candidate relevance check, no accuracy number | n/a | 08 section 4 | MATCH |
| a1-hosted | Prices: Jev $0.042, OpenAI $0.10, Perplexity $0.02, Liquid $0.04 "per blog methodology", Solar unverified | n/a | 02 vendor sections and table | MATCH |
| a1-hosted | OpenAI has a refusal type; Jev no changelog, publishes failure page; Perplexity Apache-2.0 (v1) | n/a | 02 | MATCH |
| a2-open-weight | Decision Index values: Clef 61.21, Jev 57.91, Clef-flash 57.07, d1-3B 48.57, Nimble 39.57, Kev 9B 38.48, Kev 4B 34.64, Tev1 29.24, Strands 28.97 | n/a | 02 | MATCH |
| a2-open-weight | "Every open follower is a frozen Qwen or Gemma backbone" | n/a | 02 line 67, contradicted by 02 d1-3B section | MISMATCH (item 7) |
| a3-prompt-levels | Grids for Jev, Clef, Luna, Clef Flash, Solar; P0 to P2 7/16/16 | same | `prompt-levels.json`, 01 | MATCH |
| a3-prompt-levels | Tree pushed decision models from no to can't tell on serious concern | n/a | 01b section 12 | MATCH |
| a4-calibration | ECE: Jev 0.011, Liquid 0.035, Tev 0.047, Luna 0.074, Solar 0.145, Clef 0.217, Clef Flash 0.358 | same | 01b line 914 | MATCH |
| a4-calibration | 7 of Jev's 10 least-confident are among the 10 hardest; 1,192 of 2,156 | same | 01b, feed | MATCH |
| a4-calibration | Jev kept-answer table (57/55/47, 58/58/52, 59/57/53, 58/58/54) | n/a | 01 insight 3 (47, 52, 53, 54 at 0.9) | MATCH |
| a5-key | OpenAI assistant drafted key; disputes DEV-006, 013, 030; frozen v0.2 | similar | PILOT_AUDIT, REFERENCE_REVIEW_V1 | MATCH |
| a5-key | "People checked all 60 on 2 October 2026" | "A person checked" | owner confirmed on 2 October | MATCH (date is the confirmation) |
| a5-key | DEV-006 flip: 168 down, 257 same, 212 up of 637; three-flip spread sums to 637 | n/a | 01, feed | MATCH |
| a7-limits | 340 planned validation records never generated; no speed ranking | n/a | MVP_STATUS, claim rules | MATCH |
| a8-bench | 433 tests; Clef 42 of 42 valid; not built list | n/a | 04 | MATCH |
| a9-equal-scores | Sonnet 58 in every cell yet DEV-006 and DEV-030 changed; 31 of 50, 11 of 202 | same | 01 insight 5, 01b | MATCH |
| a10-pairs | All 21 pair rows (accepted plus deferred is 60, deferred plus concern plus can't tell equals person count, charges) | feed | 01 insight 7 | MATCH (every row summed) |
| a10-pairs | 32 to 42 reach a person; Solar in four of five zero-error pairs | n/a | 05 A10 | MATCH |
| a10-pairs | Solar + Perplexity: 25 flagged, 7 can't tell, 7 deferred, 35 | 4 can't tell for clarification | `native_routing` (`insufficient_any` 7) | MATCH (item 5) |
| a13 to a18 | Six hard-review tables, key rows and model rows | n/a | `disputed-reviews-v1.json`, 01b | MATCH (matched counts 0, 0, 1, 2, 3, 5 checked) |

## 4. Not checked

- Numbers bound by `data-source` were not re-run through `numbers.mjs`. The mechanics lane owns that. I compared the values I used against the feeds by hand.
- The DEV-027 count of 800 saved passes and the Jev answer-level values on backup A13 to A18 were not traced to raw jsonl beyond the soup.
- I did not check whether every scored answer is in the public repo, only that the repo is public.
- Cost-check figures were read from `06-cost-check.md`. No provider call was made.
