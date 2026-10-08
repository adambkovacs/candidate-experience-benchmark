# Findings synthesis for the talk

Talk: "Do Models Like Jev Get It Right When Correctness Is Business-Critical?" (15 min, Adam Kovacs, AI Enablement Academy).
Prepared 8 October 2026 from the saved results in this repository. No inference was run and no result file was modified. All paths are relative to the repository root. Every score is agreement with the frozen provisional v0.2 reference on the same 60 synthetic reviews, out of 60 unless stated. "Correct" below always means "matched that reference".

Confidence tags used throughout:
- **solid**: repeated passes, source-bound JSON, exact counts.
- **descriptive-only**: one pass or a composite; true for these saved runs, no causal or general claim.
- **anecdotal**: a single review or a single pair of runs used as an illustration.

---

## 1. The one-sentence answer

On 60 synthetic candidate reviews, TypeSafe Jev matched the human-checked reference on 54 of 60 reviews (all four judgments) for an estimated $0.006 per pass, while frontier LLMs reached 58 to 59 of 60 for roughly 4x to 40x the estimated spend; but every Jev disagreement sat on an ambiguous, off-topic or disputed review, some of those wrong answers carried confidence of 0.91 to 0.96, and no single model, prompt or confidence threshold caught every disagreement, so a business-critical workflow should buy correctness with an agree-or-defer rule and a human queue, not with a leaderboard score.

Defensible from: `docs/FINDINGS.md`, `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`, `docs/JEV_CONFIDENCE_FINDINGS_2026-10-01.md`, `public-site/native-agreement-policy-v1.json`, `public-site/subscription-price-estimates.json`.

---

## 2. Talk-ready insights, ranked by audience value

### Insight 1. Jev is good, frontier LLMs are better on this set, and the gap is five reviews

**Headline.** A purpose-built decision model landed at 54/60; the best general models landed at 58 to 59/60.

**Numbers.**

| Configuration | Valid / 60 | All four / 60 | Cost basis |
| --- | ---: | ---: | --- |
| TypeSafe Jev 1.13, direct native, historical P0 | 60 | 54 | $0.00589092 token-price estimate; not a provider bill |
| Jev 1.13 via OpenRouter native Choice, P0 fresh1 / fresh2 / fresh3 | 60 / 60 / 59 | 54 / 53 / 52 | $0.005890920 known provider charge per pass |
| Claude Opus 5.5, high effort, batch of 10, P0 | 60 | 59 (three P0 passes: 59, 58, 58) | $0.222052 API-equivalent estimate of subscription CLI usage |
| Claude Sonnet 5.5, xhigh, every one of nine P0/P1/P2 cells | 60 | 58 | nine-cell estimate $1.1070244 |
| Gemma 4 26B A4B, thinking on, OpenRouter P0 | 59 | 59 | $0.02114858 observed |
| Qwen3.8 27B, low effort, OpenRouter P0 | 60 | 59 | $0.0492372 observed |
| DeepSeek V4.1 Flash, low effort, fresh3 P0 | 60 | 58 | separate ledger |

Field scores for Jev direct P0: sentiment 56, follow-up 58, serious concern 57, testimonial 58. Jev matched all 25 reviews whose reference says serious concern = yes.

**Sources.** `results/comparison/REPORT.md` (configuration table), `docs/FINDINGS.md` ("Higher scores can hide different failure patterns"), `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`, `public-site/subscription-price-estimates.json` (`runs.opus55-high-batch10`), `public-site/findings.json` (`charts.costAgreement`).

**Why it matters.** Five reviews out of 60 is the difference between 90% and 98%. In a workflow that escalates harassment reports, that gap is the whole product.

**Confidence.** solid for the Jev and Sonnet repeats; Opus 5.5 high has three P0 passes (59, 58, 58; `public-site/claude-roster-repeats.json`); descriptive-only for the single-pass Gemma row.

### Insight 2. Jev's wrong answers are not random; they cluster on the hard, disputed and off-topic reviews

**Headline.** All six Jev disagreements are on reviews that other models also split on, and three of the six are the disputed reference labels.

**Numbers.** Jev direct P0 disagreed on DEV-006, DEV-013, DEV-027, DEV-029, DEV-030, DEV-059. Of these, DEV-006, DEV-013 and DEV-030 are the three reviews where the reference itself is disputed (`docs/REFERENCE_REVIEW_V1.md`). DEV-029 is the off-topic soup review. DEV-027 and DEV-059 are clear errors under the guide. Among 39 audited hosted/subscription P0 configurations, DEV-013 drew 30 disagreements, DEV-030 drew 28 and DEV-006 drew 26.

Opus 5.5 high (first pass) matched five of Jev's six misses and kept all 54 of Jev's matches; the two shared one miss. Gemma 26B thinking-on matched all six Jev misses but returned one invalid output on a review Jev got right.

**Sources.** `docs/FINDINGS.md` ("Jev's six disagreements need different explanations", "Disagreements cluster around three ambiguous reviews"), `public-site/findings.json` (`charts.jev.overlap`).

**Why it matters.** The failure surface is predictable. A builder can route the predictable part (off-topic, insufficient information, disputed boundaries) to a human and keep the model on the rest.

**Confidence.** solid.

### Insight 3. Jev was confidently wrong, so a confidence threshold alone would not have saved you

**Headline.** Jev reported 0.96 confidence on a testimonial answer that disagreed with the reference, and 0.91 on the off-topic soup review's serious-concern field.

**Numbers (Jev direct P0, provider-reported confidence, retrospective withholding).**

| Field | Wrong / valid | Retained at ≥0.9 | Wrong retained at ≥0.9 | Withheld at ≥0.9 (of which correct) |
| --- | ---: | ---: | ---: | ---: |
| Sentiment | 4/60 | 47 | 0 | 13 (9) |
| Follow-up | 2/60 | 52 | 0 | 8 (6) |
| Serious concern | 3/60 | 53 | 1 (DEV-029, conf 0.91) | 7 (5) |
| Testimonial | 2/60 | 54 | 1 (DEV-027, conf 0.96) | 6 (5) |

Wrong-case confidences, P0: sentiment DEV-013 0.33, DEV-027 0.71, DEV-029 0.46, DEV-030 0.53; follow-up DEV-029 0.84, DEV-059 0.49; serious concern DEV-006 0.71, DEV-029 0.91, DEV-030 0.59; testimonial DEV-027 0.96, DEV-029 0.88. Provider confidence and selected-option probability are different numbers (DEV-029 serious concern: 0.91 confidence, 0.94 option probability). Neither has demonstrated calibration.

Other decision models show the same pattern: Solar Decide first-P0 sentiment at ≥0.9 retains 31/60 including 3 errors (DEV-013, DEV-027, DEV-030); at ≥0.99 retains 16 including 2 errors. Tev first-P0 sentiment at ≥0.9 retains 41/60 including 4 errors. Clef's first P0 misses DEV-029 on follow-up, serious concern and testimonial with provider confidence at least 0.9.

**Sources.** `docs/JEV_CONFIDENCE_FINDINGS_2026-10-01.md`, `public-site/jev-confidence-findings.json`, `public-site/solar-decide-full-findings.json`, `public-site/tev-native-full-findings.json`, `docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md` ("Confidence, abstention, cost and timing").

**Why it matters.** "Only act when confidence is above X" is the first control every team reaches for. On this set it removes coverage faster than it removes errors, and it leaves the most embarrassing errors in.

**Confidence.** solid for the numbers; the thresholds are retrospective, not a deployed abstention policy.

### Insight 4. More instructions did not consistently help, for Jev or for anyone

**Headline.** Adding classifier framing and then a decision tree made things worse more often than better.

**Numbers.** Across 39 audited hosted/subscription setups, P0 to P1: 15 better, 15 same, 9 worse. P1 to P2: 4 better, 14 same, 21 worse. Across 21 Claude configurations with three matched passes each, no configuration beat P0 with P1 or P2 in all three passes. Decision models, every pass: Clef 54 / 51 / 49 (P0 / P1 / P2), Luna Decisions 49 / 51 / 49, Clef Flash 45 / 47 / 46 (final P2 pass 45 after one provider failure), Solar 55,53,54 / 53,52,51 / 53,52,52. Jev via OpenRouter: P0 54,53,52; P1 54,53,54; P2 54, interrupted, 54. Qwen3 1.7B thinking-on local: P0 24/23/24, P1 12/11/16, P2 8/9/8.

**Sources.** `docs/FINDINGS.md` ("More instructions did not consistently improve agreement"), `docs/ANALYSIS_REFRESH_2026-10-02.md`, `docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md` (latest decision-model table), `docs/CLEF_PROMPT_CORRECTNESS_TRANSITIONS_2026-10-07.md`, `README.md` (Qwen 1.7B table).

**Why it matters.** The instinct when a classifier is wrong is to write a longer SOP into the prompt. On this set that was the least reliable lever available.

**Confidence.** solid as a within-configuration observation; not a causal estimate (prompt audits verify pairing, not randomization).

### Insight 5. Equal scores hide different answers

**Headline.** A model can repeat its total exactly and still change its mind on individual reviews.

**Numbers.** Sonnet 5.5 xhigh scored 58/60 in all nine cells, yet changed DEV-006 between P1 passes and DEV-030 between P2 passes. Fable 5.1 low returned 57/60 under P1 in all three passes while changing three reviews' classifications. Gemma E4B thinking-off scored 42/60 under P2 in every pass while seven comments changed at least one label. Gemma E2B kept 35/60 while changing nine reviews. Jev P2 fresh1 and fresh3 both scored 54/60 and differ on DEV-030. Gemma E2B thinking-on: P1 36 and 39 out of 60 with 11 reviews changed between those passes (the live site's headline example).

**Sources.** `docs/ANALYSIS_REFRESH_2026-10-02.md`, `README.md` (Fable, Gemma E4B, Gemma E2B paragraphs), `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`, live site section "Three findings from the saved answers".

**Why it matters.** If you monitor a deployed classifier by aggregate accuracy, this kind of drift is invisible, and the affected candidate still got a different decision.

**Confidence.** solid.

### Insight 6. Stable is not the same as right

**Headline.** The most repeatable models in the study include both a 54/60 model and several 0/60 models.

**Numbers.** Perplexity Decider: 540/540 valid responses, 54/60 in all nine runs, identical answers within each prompt; the same errors every time (DEV-013 sentiment, DEV-029 and DEV-035 follow-up, DEV-006/029/030 serious concern, DEV-028 testimonial). Clef, Clef Flash and Luna: zero categorical flips between same-prompt repeats. Laya (three native configurations): unchanged answers across three passes, 0/60 each. AnyJev raw: unchanged across three passes, 0/60, predicting neutral / follow-up / serious concern for every review. Alex OpenJev 0.8B: 3/60 in each of three passes, no changes.

**Sources.** `results/perplexity-decider-v1/full-v2/findings.json`, `public-site/native-agreement-policy-v1.json` (`components[].field_error_ids`), `docs/LAYA_REPEAT_FINDINGS_2026-09-28.md`, `docs/ANYJEV_RAW_REPEAT_FINDINGS_2026-09-28.md`, `docs/ALEX_NATIVE_REPEAT_FINDINGS_2026-09-28.md`.

**Why it matters.** Determinism is a property of the serving stack, not of correctness. A deterministic wrong answer is a wrong answer you will get at scale.

**Confidence.** solid.

### Insight 7. Requiring two decision models to agree gives you a zero-error accepted set, at the price of a human queue

**Headline.** Accept only when two models return the identical four-field answer; defer the rest. Five of 21 pairs retained zero reference errors; coverage ranged from 33 to 53 of 60.

**Numbers (seven native fresh1/P0 runs, all 21 pairs, policy fixed before calculation).**

| Pair | Accepted / 60 | Accepted errors | Deferred to human | Two-run known charge |
| --- | ---: | ---: | ---: | ---: |
| Solar + Perplexity | 53 | 0 | 7 | $0.03749436 |
| Clef + Perplexity | 53 | 2 (DEV-006, DEV-030) | 7 | $0.04727392 |
| Solar + Clef | 52 | 0 | 8 | $0.05391356 |
| Clef + Luna | 50 | 2 (DEV-006, DEV-029) | 10 | $0.04519886 |
| Solar + Clef Flash | 44 | 0 | 16 | $0.03400946 |
| Liquid + Solar | 43 | 0 | 17 | $0.03775612 |
| Clef + Clef Flash | 47 | 4 | 13 | $0.04378902 |
| Liquid + Tev | 33 | 0 | 27 | $0.032031992 |

Range over all 21 pairs: accepted 33 to 53, accepted errors 0 to 4. Human review cost of the deferred cases is not measured. No pair is selected as a validated production choice.

**Sources.** `public-site/native-agreement-policy-v1.json`, `results/native-agreement-policy-v1/README.md`, `docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md`.

**Why it matters.** This is the first control in the study that produced a zero-error accepted set without reading the reference. It costs you 12% to 45% of reviews going to a person.

**Confidence.** solid on this set; retrospective, not out-of-sample.

### Insight 8. The leaderboard is fragile to three labels

**Headline.** Flipping the three disputed reference labels moves most runs' scores by one to three points in either direction.

**Numbers.** Across 637 extended run entries, changing DEV-006 serious concern to "no" improves 212 runs, worsens 168, leaves 257 unchanged. Changing DEV-013 sentiment to "positive": 289 improve, 185 decline, 163 unchanged. Changing DEV-030 sentiment to "negative": 136 improve, 94 decline, 407 unchanged. All three together: 265 improve, 153 decline, 219 unchanged, with per-run deltas from -3 to +3. The DEV-006 change alone moves Jev from 54 to 55; across 38 strict P0 configurations it moves the total from 2,143 to 2,139 of 2,280 because several "no" predictions disagree on another field.

**Sources.** `public-site/reference-sensitivity-v1.json` (`scenario_summaries`), `docs/REFERENCE_REVIEW_V1.md`, `results/reference-review-v1.json`.

**Why it matters.** When a one-point difference decides a vendor choice, the label quality of your evaluation set is the bottleneck, not the model.

**Confidence.** solid (hypothetical rescoring of saved outputs; frozen scores unchanged).

### Insight 9. Class imbalance and the testimonial trap

**Headline.** Answering "no" to every testimonial question already scores 50/60. The field total tells you nothing about whether a model finds the nine real testimonials.

**Numbers.** Reference distribution: testimonial 9 yes / 50 no / 1 insufficient; serious concern 25 yes / 29 no / 6 insufficient; follow-up 35 yes / 24 no / 1 insufficient; sentiment 31 negative / 11 positive / 8 neutral / 8 mixed / 2 insufficient. Tev first-P0: testimonial yes recall 9/9, precision 9/12 (three false positives), field score 56/60. Luna Decisions: recall 6/9, precision 6/6, field score 56/60. Same field total, opposite failure mode. SemIf native: testimonial field 54/60 while finding only 4 of 9 positives. Alex OpenJev 0.8B: 59 reviews marked testimonial-yes, 49 of them reference-negative. Qwen3 0.6B HTTP: all 60 marked testimonial-yes.

**Sources.** `docs/FINDINGS.md` ("The four fields have different class balances"), `results/analysis-native-cohort-v1/README.md`, `docs/SEMIF_REPEAT_FINDINGS_2026-09-28.md`, `README.md`.

**Why it matters.** Marketing wants the nine testimonials. Compliance wants zero missed harassment reports. Both need per-class recall and precision, not a four-field total.

**Confidence.** solid.

### Insight 10. Where the models split is where System 1 runs out: off-topic, insufficient information, ambiguous evaluation

**Headline.** Seven decision models agreed with the full reference on 26 of 60 reviews. The reviews that split them are the ones a human would pause on.

**Concrete cases (seven native fresh1/P0 models, `public-site/disputed-reviews-v1.json`).**

- **DEV-029, off-topic.** Text: "Great soup, tiny portions, wouldn't eat there again." Reference: insufficient_information on all four fields. 0 of 7 decision models matched; four of them (Tev, Clef, Clef Flash, Luna) labeled sentiment "mixed" and answered no / no / no on the other fields; Solar said negative / no / no / no and Liquid insufficient / no / no / no. Jev direct P0 did the same (mixed / no / no / no). Perplexity came closest (insufficient on sentiment and testimonial, "no" on the other two). Among general LLMs, 89 of 113 valid historical P0 configurations and 13 of 28 declared fresh configurations matched the full reference. A System 1 classifier answered the question it was asked; it did not notice the question did not apply.
- **DEV-030, uncertain resolution.** Text: "The accessibility issue from the assessment has been dealt with, I think. Someone said it was fixed, but I don't know whether that means I get another assessment or just that they've closed the ticket." Reference: neutral / yes / insufficient_information / no. 0 of 7 matched. Every model gave serious concern "no" or "insufficient"; sentiment ranged across neutral, negative and insufficient. Only 19 of 109 valid historical general configurations matched. The reference itself is flagged "needs human" on sentiment.
- **DEV-006, vague recurrence.** Text: "Same as last time. That thing happened again and it still isn't sorted." Reference: negative / yes / insufficient_information / no. 6 of 7 missed; all six said serious concern "no". The reference reviewer proposes "no" is correct under the guide. The models may be right and the key wrong.
- **DEV-013, rumour plus neutral own experience.** Text: "A friend told me they heard this firm asks inappropriate questions. My own interview was straightforward, and I have no complaint about it." Reference: neutral. Models split three ways: positive (Liquid, Perplexity), mixed (Tev, Solar, Luna), neutral (Clef, Clef Flash). 30 of 39 hosted configurations disagreed with the reference.
- **DEV-027, the testimonial.** Text: "Train got cancelled so they switched me to video with the same interviewers and gave me five mins to catch my breath. Really helpful of them." Reference: positive / no / no / yes. Jev said negative and not a testimonial, with 0.96 confidence on the testimonial field. Liquid did the same; Solar said mixed / no. Three of seven matched fully.

Histogram of mismatching-model counts across the 60 reviews: 26 reviews with 0, 15 with 1, 12 with 2, 1 with 3, 2 with 4, 1 with 5, 1 with 6, 2 with 7.

**Sources.** `public-site/disputed-reviews-v1.json`, `results/cross-category-v1/findings.md`, `public-site/findings.json` (`charts.hardCases`), `docs/REFERENCE_REVIEW_V1.md`.

**Why it matters.** The hard cases are not hard because of vocabulary. They are hard because the right answer requires stepping back from the question (is this even recruitment feedback?) or holding two states at once (resolved, maybe). That is the System 2 move, and it is exactly where a fast typed classifier should hand off.

**Confidence.** solid for the counts; the "System 1 vs System 2" framing is interpretation.

### Insight 11. Invalid output is a real failure class, and small models fail it most

**Headline.** Before you can be wrong you have to produce an answer. Several configurations could not.

**Numbers.**
- AnyJev generated-JSON control: all 360 P0 and P1 responses began with a Markdown code fence, so 0/60 valid in every pass under the strict parser. P2: the same 30 valid and 30 fenced every pass.
- SemIf generated: 8 (P0), 22 (P1) and 2 (P2) responses per pass returned the JSON schema text instead of four classification values; the same review IDs every pass.
- OpenJev generated-off fresh1: 7 / 7 / 4 invalid outputs across P0 / P1 / P2 (non-JSON, an out-of-vocabulary sentiment value, a misspelled key). The upstream OpenJev generated path passes the JSON schema as instruction text and extracts the first JSON object; the project records this as "schema-as-instruction/first-object extraction" and does not repair outputs.
- Qwen3 0.6B SDK thinking-off: 0 valid of 60. Qwen3 1.7B thinking-off: four strict-JSON failures, all JSON wrapped in code fences. Hosted Qwen3 8B thinking-on with JSON-object mode: 14 valid, 46 intrinsic invalid.
- Gemini 3.8 Flash medium and 3.7 Flash high: 50 valid of 60 (invalid ten-review batches).
- Jev itself: a handful of responses returned a native probability distribution summing to 0.99 and were rejected by the unchanged validator (direct P1 DEV-053, direct P2 DEV-040, OpenRouter P1 fresh2 DEV-056, OpenRouter P0 fresh3 DEV-040, OpenRouter P2 fresh2 continuation DEV-040). Each stays in the 60 denominator as unscorable, not wrong.
- Claude Opus/Sonnet/Fable, Codex and the seven native decision models: 60/60 valid in essentially every pass (Flash lost one answer to a provider 429 in its final P2 pass).

**Sources.** `docs/ANYJEV_GENERATED_REPEAT_FINDINGS_2026-09-30.md`, `docs/SEMIF_GENERATED_REPEAT_FINDINGS_2026-09-30.md`, `docs/OPENJEV_GENERATED_REPEAT_FINDINGS_2026-09-29.md`, `results/comparison/REPORT.md` (lines 354-364 and 716-718), `docs/LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md`, `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`.

**Why it matters.** Invalid output stays in the denominator here. In production it becomes a silent retry, a default value, or a crash. Native typed interfaces (Choice heads) had far fewer format failures than generated JSON.

**Confidence.** solid.

### Insight 12. The open-source Jev clones mostly did not deliver Jev-level results

**Headline.** One clone (OpenJev native) came within a few points; the rest ranged from 39/60 down to 0/60.

**Numbers (all-four matches, three passes where available).**
- OpenJev native: thinking 53 / 54 / 54 (historical single run 57); fixed 53 each pass; adaptive 52 each pass. Generated-off P0 48 / 51 / 49; generated-on P2 46 / 47 / 42.
- Alex OpenJev 4B (task-fine-tuned): 39 / 39 / 39, missing the same 8 of 25 serious concerns every pass. Alex OpenJev 0.8B: 3 / 3 / 3.
- SemIf native direct: 36 (single run). SemIf generated: P0 35, P1 26, P2 43 in each pass.
- AnyJev (Qwen3 0.6B backbone): raw 0, L0 4, L1 6, L2 13, each stable across three passes.
- Laya English / typed / multilingual (expanded CPU): 0 / 0 / 0.
- Kev-4B native Choice: P0 48 (two clean passes), P1 49 every pass, P2 46 every pass.

**Sources.** `docs/OPENJEV_NATIVE_REPEAT_FINDINGS_2026-09-29.md`, `docs/ALEX4B_NATIVE_REPEAT_FINDINGS_2026-09-29.md`, `docs/SEMIF_REPEAT_FINDINGS_2026-09-28.md`, `docs/ANYJEV_L2_REPEAT_FINDINGS_2026-09-29.md`, `docs/LAYA_REPEAT_FINDINGS_2026-09-28.md`, `docs/KEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`, `results/comparison/REPORT.md`.

**Why it matters.** "Jev-like" on a model card is not a capability claim. Architecture family tells you nothing; the saved run does.

**Confidence.** solid (per configuration); no family-level claim.

### Insight 13. The rules baseline is the sanity floor, and some models fell below it

**Headline.** Hand-written regex rules scored 10/60. Five learned configurations scored lower.

**Numbers.** rules-v1: 60 valid, fields 22 / 25 / 35 / 41, all-four 10/60. Below it: Qwen3 0.6B (0), AnyJev raw (0), AnyJev L0 (4), AnyJev L1 (6), Alex 0.8B (3), Laya (0). The author of the rules had seen the development labels, so 10/60 is a generous floor.

**Sources.** `results/comparison/REPORT.md` (rules-v1 row and note), `docs/FINDINGS.md` (illustrative P0 table).

**Why it matters.** If your model cannot beat a weekend of regex, the model is not the right spend.

**Confidence.** solid.

### Insight 14. Cost versus quality: the decision-model frontier is cheap, and higher effort can buy nothing

**Headline.** Among seven decision models, four sit on the cost/agreement frontier at one to two cents per 60 reviews; more reasoning effort in Gemini cost 4x for one fewer match.

**Numbers (seven native fresh1/P0, known development charge for 60 one-review requests).**

| Model | All four / 60 | Known charge |
| --- | ---: | ---: |
| Clef Flash | 45 | $0.01194246 |
| Luna Decisions | 49 | $0.01335230 |
| Perplexity Decider | 54 | $0.01542736 |
| Liquid d1 | 43 | $0.01568912 |
| Tev 1 4B | 45 | $0.016342872 |
| Solar Decide | 55 | $0.02206700 |
| Clef | 54 | $0.03184656 (list-price input estimate; 132,694 input tokens, 0 output) |

Frontier (no other run both cheaper and at least as good): Flash, Luna, Perplexity, Solar. Perplexity's 54 at $0.0154 removes Clef's 54 at $0.0318 from the frontier. Full nine-run series charges: Perplexity $0.14296, Tev $0.151342128, Solar $0.20325475 (plus one $0.10485760 unknown-charge bound), Luna $0.1304487, Clef Flash $0.11649969 (plus $0.02359296 bound), Clef $0.31128624 (estimate).

Gemini effort example (same 11,227 input tokens, batch of 10): Gemini 3.1 Pro low 56/60, 3,417 output tokens, $0.063458; high 55/60, 19,531 output tokens, $0.256826. Gemini 3.7 Flash low 57/60, $0.02167275; medium 56/60, $0.0559665. Sonnet 5.5 xhigh used 2.47x low's output tokens across nine cells (83,131 vs 33,653) without a consistent gain.

Jev: $0.00589 per 60-review pass (OpenRouter known charge; direct route is a token-price estimate). Opus 5.5 high: $0.222 API-equivalent per pass. These are different accounting categories and are not plotted together in the repo.

**Sources.** `docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md` (component table and frontier), `public-site/native-agreement-policy-v1.json`, `results/clef-openrouter-v1/findings-v1/findings.json` (`stages`), `docs/FINDINGS.md` ("Higher effort can cost more without adding matches"), `docs/ANALYSIS_REFRESH_2026-10-02.md`, `public-site/subscription-price-estimates.json`.

**Why it matters.** The entire 60-review decision-model study cost about $1.20 across seven models and 63 runs ($1.2013: known charges plus Clef's $0.3113 list-price estimate), plus up to $0.13 in unknown-charge bounds (Solar $0.1049, Clef Flash $0.0236). Cost is not the constraint; deciding what to do with the deferred 10% is.

**Confidence.** solid for observed charges; descriptive-only for frontier membership (seven runs, one pass each).

### Insight 15. Native Choice interfaces move the prompt-engineering problem, they do not remove it

**Headline.** Jev's native P0/P1/P2 variants changed the probability dictionaries far more than they changed the answers.

**Numbers.** Jev OpenRouter fresh1, P1 vs P2: 1/60 answer vectors changed (DEV-013), but native probability dictionaries changed on sentiment 32/60, follow-up 21/60, serious concern 26/60, testimonial 12/60. P1 fresh1 vs fresh2: 0/59 answers changed; probability dictionaries changed on 25 / 15 / 11 / 8 of 59. Clef, Flash and Luna reported 0 output tokens in every run (typed heads, not generation).

**Sources.** `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`, `results/clef-openrouter-v1/findings-v1/findings.json`.

**Why it matters.** If a downstream rule keys on the probability (a threshold) rather than the label, prompt wording and repeat passes will move your deferral rate even when the labels are identical.

**Confidence.** solid.

---

## 3. Numbers safe to put on a slide

| # | Slide number | Exact value | Source path |
| --- | --- | --- | --- |
| 1 | Reviews in the study | 60 synthetic reviews, 4 judgments each, 340 planned records never generated | `README.md`, `docs/PILOT_AUDIT.md` |
| 2 | Jev direct P0 | 60 valid, 54/60 all-four; fields 56/58/57/58 | `results/comparison/REPORT.md` row `typesafe-jev113-v2` |
| 3 | Jev OpenRouter P0 repeats | 54, 53, 52 of 60; P1 54, 53, 54; P2 54, (interrupted 50), 54 | `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md` |
| 4 | Jev cost per 60-review pass | $0.005890920 known provider charge (OpenRouter P0); 140,260 input / 11,176 output tokens | `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md` |
| 5 | Jev serious-concern recall | 25/25 reference-positive serious concerns matched | `docs/FINDINGS.md` |
| 6 | Jev confidently wrong | DEV-027 testimonial wrong at confidence 0.96; DEV-029 serious concern wrong at 0.91 | `public-site/jev-confidence-findings.json` |
| 7 | Jev sentiment at ≥0.9 | retains 47/60, 0 wrong, withholds 13 (9 of them correct) | `public-site/jev-confidence-findings.json` |
| 8 | Opus 5.5 high P0 | 60 valid, 59/60 first pass (three P0 passes: 59, 58, 58); $0.222052 API-equivalent estimate | `results/comparison/REPORT.md`, `public-site/subscription-price-estimates.json`, `public-site/claude-roster-repeats.json` |
| 9 | Sonnet 5.5 xhigh | 58/60 in all nine cells; 2,160/2,160 valid | `public-site/sonnet55-fresh-matched3.json`, `docs/ANALYSIS_REFRESH_2026-10-02.md` |
| 10 | Gemma 4 26B thinking-on P0 | 59 valid, 59/60, $0.02114858 observed | `public-site/findings.json` `charts.costAgreement` |
| 11 | Rules baseline | 10/60 | `results/comparison/REPORT.md` row `rules-v1` |
| 12 | Qwen3 0.6B | 0/60 in three passes; all 60 marked testimonial-yes | `docs/LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md` |
| 13 | Prompt effect, 39 setups | P1→P2: 4 better, 14 same, 21 worse | `docs/FINDINGS.md` |
| 14 | Clef P0/P1/P2 | 54 / 51 / 49 in every one of three passes | `docs/ANALYSIS_RELEASE_RECONCILIATION_2026-10-07.md` |
| 15 | Perplexity Decider | 54/60 in all nine runs, 540/540 valid, $0.14296 | `results/perplexity-decider-v1/full-v2/findings.json` |
| 16 | Agreement policy best pair | Solar + Perplexity: 53 accepted, 0 errors, 7 deferred, $0.03749436 | `public-site/native-agreement-policy-v1.json` |
| 17 | Agreement policy range | 21 pairs: 33 to 53 accepted, 0 to 4 accepted errors | `public-site/native-agreement-policy-v1.json` |
| 18 | Off-topic review DEV-029 | 0/7 decision models matched; 89/113 valid historical general configs did | `results/cross-category-v1/findings.md` |
| 19 | Testimonial class balance | 9 yes / 50 no / 1 insufficient; all-no scores 50/60 | `docs/FINDINGS.md` |
| 20 | Reference sensitivity | flipping DEV-006 alone: 212 runs up, 168 down, 257 unchanged of 637 | `public-site/reference-sensitivity-v1.json` |

Gemini effort pair (Insight 14) is also slide-safe: 3.1 Pro low 56/60 $0.063458 vs high 55/60 $0.256826, `docs/FINDINGS.md`.

---

## 4. Claims we must NOT make

- **Not a leaderboard.** The site and README say so explicitly. Runs differ in route, interface, batch size, effort and prompt implementation. Do not rank models or say "best model".
- **Not causal.** No prompt effect, effort effect, architecture effect or model-family effect is established. Paired comparisons are audited for pairing, not randomized. Say "in these saved runs".
- **Not real-world accuracy.** 60 synthetic, AI-written, concern-enriched reviews. Nothing here estimates performance on real candidate feedback, prevalence of concerns, or demographic fairness.
- **Reference is provisional.** Human-checked on 2 October 2026, still v0.2, three labels disputed, one proposed correction (DEV-006) not adopted. Say "matched the provisional reference", never "accurate" or "correct" without that qualifier.
- **Missing cost is unknown, not zero.** Subscription CLI runs have API-equivalent estimates, not bills. Jev direct is a token-price estimate. Clef/Flash/Luna charges are input-tariff estimates with zero output tokens. Local runs have no per-run cost. Do not put Jev's estimate and Gemini's observed charge on one scatter as if they were the same quantity.
- **No speed ranking across surfaces.** Client request time includes network, CLI, batch and operator handoff. Jev's old "2.2 minutes" was 61 client requests including a failure. Pure inference time is unavailable for every surface. Never say "Jev is faster".
- **No pooling.** 1,004 selectable run entries reuse the same 60 reviews. Do not say "60,240 reviews" or "1,004 experiments". Do not add counts from different cohorts.
- **Do not count invalid outputs out.** Every score is out of 60 with invalid, failed and unsent positions retained. Do not quote "47/51 among valid" without the fixed-denominator figure beside it.
- **Confidence thresholds are retrospective.** Jev did not abstain. No threshold was validated or selected on held-out data. "insufficient_information" is a label, not an abstention.
- **The hindsight oracle (58/60) is not an ensemble.** It selects after seeing the reference.
- **No two-model pair is a recommended production configuration.** All 21 pairs are reported; none was selected.
- **Decision-model category overlaps general LLM.** A model can be both. Do not frame "dedicated vs general" as a clean dichotomy.
- **Do not say the models "beat" the human key on DEV-006.** The reviewer proposed a correction; it has not been adopted.

---

## 5. Three surprise findings a builder audience will remember

1. **The soup review.** "Great soup, tiny portions, wouldn't eat there again." Every one of seven purpose-built decision models answered it as recruitment feedback (mostly "mixed, no, no, no"). Jev did too. Most frontier chat models said "this is not about recruitment". A typed classifier answers the question on the form; it does not ask whether the form applies. (`public-site/disputed-reviews-v1.json`, `results/cross-category-v1/findings.md`)

2. **Longer SOP, worse results.** Adding a decision tree to the prompt made 21 of 39 setups worse and 4 better. Clef dropped from 54 to 49 in every one of three passes. The thing every team does first was the least reliable lever in the study. (`docs/FINDINGS.md`, `docs/CLEF_PROMPT_CORRECTNESS_TRANSITIONS_2026-10-07.md`)

3. **A one-cent second opinion with zero accepted errors.** Running Solar Decide and Perplexity Decider on all 60 reviews cost $0.037 combined. Accepting only their identical answers gave 53 reviews with no reference errors and sent 7 to a human. Jev alone at 0.96 confidence was still wrong on a testimonial. (`public-site/native-agreement-policy-v1.json`, `public-site/jev-confidence-findings.json`)

---

## 6. How much confidence should a business-critical workflow demand?

Proposed answer, grounded in this set and stated as a policy to test, not a validated result.

**Single-model confidence is not the gate.** On Jev P0, no threshold below 0.97 removes the DEV-027 testimonial error, and no threshold below 0.92 removes the DEV-029 serious-concern error. Reaching 0.9 on sentiment zeroes Jev's sentiment errors but withholds 13 of 60 reviews, 9 of which were right. Solar at 0.99 still retains two sentiment errors in 16 retained answers. Provider "confidence" and selected-option probability disagree (0.91 vs 0.94 on the same answer), and neither is calibrated. Threshold policy therefore buys coverage loss faster than error removal on this data.

**Agreement is the gate that worked here.** The fixed rule "accept only when two independent decision models return the identical four-field answer, otherwise defer" produced five zero-error accepted sets among 21 pairs:

| Pair | Accepted | Deferred | Deferral rate | Two-run charge per 60 |
| --- | ---: | ---: | ---: | ---: |
| Solar + Perplexity | 53 | 7 | 11.7% | $0.0375 |
| Solar + Clef | 52 | 8 | 13.3% | $0.0539 |
| Solar + Clef Flash | 44 | 16 | 26.7% | $0.0340 |
| Liquid + Solar | 43 | 17 | 28.3% | $0.0378 |
| Liquid + Tev | 33 | 27 | 45.0% | $0.0320 |

The seven reviews Solar + Perplexity deferred are DEV-006, DEV-013, DEV-027, DEV-028, DEV-029, DEV-030 and DEV-035: the three disputed labels, the off-topic review, the testimonial and two follow-up/testimonial boundary cases. The 16 pairs that retained errors did so on 12 reviews: DEV-005, DEV-006, DEV-013, DEV-018, DEV-027, DEV-028, DEV-029, DEV-030, DEV-035, DEV-054, DEV-056 and DEV-059. Most retained errors sit on the disputed labels and the off-topic case (DEV-006 in 10 pairs, DEV-029 and DEV-030 in 6 each, DEV-013 in 4); each of the other eight reviews appears in one pair. So a second model catches disagreement; it does not catch shared blind spots, which concentrate on the disputed and off-topic reviews.

**Field-specific asymmetry.** For the escalation field, the cost of a miss and a false alarm are not symmetric. Jev matched all 25 serious-concern = yes references; its three misses on that field were "insufficient_information" references it labeled "no". Clef Flash and Tev each missed some positives. A workflow should route serious_concern = yes to review regardless of confidence, and treat any "insufficient_information" from any model as an automatic human queue (the labeling guide already defines this as clarification_review).

**Proposed operating policy for the talk (to be validated, not deployed from this data).**
1. Two decision models, both typed (native Choice), cheap enough to run on every review (here about $0.0006 per review per model).
2. Accept only identical four-field answers. Expect roughly 10% to 15% deferral with a well-matched pair on this kind of text; expect 25% to 45% with a weak pair.
3. Any serious_concern = yes from either model goes to escalation review even if accepted.
4. Any insufficient_information from either model goes to the human queue.
5. Do not use provider confidence as a gate; log it, and revisit only after a calibration study on real data.
6. Measure per-class recall on the rare classes (nine testimonials, 25 serious concerns), not the four-field total.
7. Re-run the pair quarterly on the same frozen set and count label flips, not just the score.

What this would have caught on the 60: five of Jev's six disagreement reviews (DEV-006, DEV-013, DEV-027, DEV-029, DEV-030) are in the Solar + Perplexity deferred set, at a cost of 7 deferrals; the sixth, DEV-059, was answered correctly by both models and accepted, so Jev's miss there would have been overruled rather than deferred. What it would not catch: a future review where both models share the same blind spot, as all seven did on the soup review. Human review cost of the deferred cases is unmeasured.

Sources: `public-site/native-agreement-policy-v1.json`, `public-site/jev-confidence-findings.json`, `public-site/solar-decide-full-findings.json`, `docs/LABELING_GUIDE.md` (simulated routing), `docs/FINDINGS.md`.

---

## 7. Open questions the benchmark cannot answer

- **Real feedback.** Only 60 synthetic, concern-enriched reviews exist; the 340 planned validation, ordinary and challenge records were never generated. Nothing here estimates performance, prevalence or fairness on real candidate text.
- **Reference truth.** The key is v0.2, human-checked but still provisional. DEV-013 and DEV-030 sentiment need human adjudication. DEV-006 has a proposed but unadopted correction. Until a versioned v0.3 is adopted, every one-point difference is inside the label noise.
- **Calibration.** No model's confidence or option probability has demonstrated calibration. The threshold tables are retrospective counts, not reliability curves on held-out data.
- **Inference time.** Pure server inference latency is unavailable on every surface. Client request time mixes network, batch size, CLI and operator time. No speed claim is possible.
- **Cost on a real workflow.** Observed charges cover 60 reviews. Human review cost of deferred cases, subscription quota, local hardware and operator time are not measured. The agreement-policy cost excludes the human queue entirely.
- **Causality.** No controlled experiment isolates prompt wording, reasoning effort, model family or interface type. Serving revision, seed, hidden retries and provider routing are unobserved.
- **Generalization of the agreement rule.** Zero accepted errors on 60 development reviews is not evidence of zero errors on the next 60. The policy was fixed before calculation but evaluated on the same set used for everything else.
- **Shared blind spots.** All seven decision models missed DEV-029 and DEV-030. The benchmark cannot say how often real input is off-topic or indeterminate, which is what decides the deferral rate.
- **Native vs generated.** Native Choice heads had almost no format failures; generated JSON had many. Whether that holds for longer or multilingual input is untested.
- **Scope cuts.** Direct Cloudflare Jev/Clef/Flash repeats, remaining Mistral execution and further local inference were removed from scope on 6 and 7 October. Three requested models were never available. Their absence is not a result.

---

Corrections 2026-10-08: DEV-029 "mixed" sentiment came from four decision models, not five; five of 21 agreement pairs (not four) kept zero accepted errors, Liquid + Solar added; the seven-model study total is $1.2013 including Clef's list-price estimate, plus up to $0.13 unknown, not "under $1.20"; Opus 5.5 high has three P0 passes (59, 58, 58), not one; the 16 error-retaining agreement pairs erred on 12 reviews, not only DEV-006, DEV-029 and DEV-030 (section 6).
