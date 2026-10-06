# Candidate Experience Feedback Benchmark

[![Compare: Jev vs AI models](https://img.shields.io/badge/compare-Jev_vs_AI_models-235a48)](results/comparison/REPORT.md)
[![Task: Feedback classification](https://img.shields.io/badge/task-feedback_classification-335d82)](#what-the-models-decide)
[![Results: Interactive explorer](https://img.shields.io/badge/results-interactive_explorer-235a48)](https://adambkovacs.github.io/candidate-experience-benchmark/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**How well can TypeSafe Jev and general-purpose language models classify feedback written by candidates about their hiring experience?**

This project compares their responses to the same 60 fictional reviews, complaints and potential testimonials. Each method makes four judgments. Saved results include output validity, agreement with provisional references, prompt variations, request times, token counts and costs where recorded.

[Explore the results](https://adambkovacs.github.io/candidate-experience-benchmark/) · [Read the evidence report](results/comparison/REPORT.md) · [See the method](docs/PLAN.md)

[![Public explorer preview](public-site/preview.png)](https://adambkovacs.github.io/candidate-experience-benchmark/)

## Explore the findings

Qwen3.5 4B thinking-on completed its first P2 pass: **50/60 all-four matches**, with 51 valid responses and nine invalid outputs. DEV-030 was the only valid response that differed from the frozen reference. Its interrupted P0 result remains descriptive, so this is not a clean paired prompt comparison or a completed repeatability study. The run used 303,294 tokens; pure inference time and local cost are unavailable. [P2 findings](docs/QWEN35_P2_FIRST_PASS_2026-10-06.md).

Qwen3.5 4B thinking-on matched all four reference fields on **47/60** reviews in its first new P0 pass, or **47/51** among valid answers. The pass was interrupted by low-power sleep; a separate continuation sent only the eight remaining reviews. Combined results retain 51 valid answers, eight invalid answers and one unknown outcome. This descriptive result is not a clean repeat. The sleep-spanning timeout cannot measure inference time. [Interruption evidence](docs/QWEN35_P0_INTERRUPTION_2026-10-06.md).

Clef's first classifier-instruction (P1) pass scored **52/60**, compared with **53/60** for its matched base-task pass. Four reviews changed an answer; one gained a full match and two lost one. All 60 responses were valid. This is one prompt comparison; two further P1 passes are still required. Reported usage was 144,694 input tokens and zero output tokens, with a $0.03472656 published-price estimate rather than a provider bill. [First P1 findings](docs/CLEF_P1_FIRST_PASS_2026-10-05.md).

Cloudflare Clef and Clef Flash have native P0 results on the same 60 reviews. Clef scored 53/60 in each of its three P0 passes. Clef Flash scored 45/60 in its first two P0 passes; its third remains unscored after two unknown outcomes, leaving 58 reviews unsent. The [5 October continuation](docs/CLEF_FLASH_P0_SUFFIX_CHECKPOINT_2026-10-05.md) returned no usable prediction and did not change earlier scores. In three P1 passes, Clef Flash scored 47/60 each time, with no observed changes to predictions, native probability distributions or vendor confidence. In the matched fresh1 comparison, P1 scored 47/60 against P0's 45/60; DEV-027 and DEV-044 became all-four matches, with no losses. This single prompt contrast is descriptive. Provider-billed dollars and pure inference latency are unavailable. [P1 findings](docs/CLEF_FLASH_P1_FINDINGS_2026-10-05.md) · [third P0 checkpoint](docs/CLEF_P0_THIRD_CHECKPOINT_2026-10-02.md).

Mistral 119B fresh1 P0 returned 55 valid answers and five failed requests. It matched all four provisional reference fields on 40/60 records, or 40/55 among valid answers. This interrupted pass is not a repeat result; its failures and unknown-charge bound remain visible in the [partial findings](public-site/mistral119-fresh1-p0-findings.json). The subsequent P1 smoke stopped on an upstream HTTP 429 before returning a prediction. It adds no P1 score and leaves the P0 findings unchanged. [P1 smoke record](results/repeatability-v1/mistral119-fresh-matched3-v1/p1-successor-v1/smoke.terminal-public.json).

Gemma 26B thinking-on now has descriptive fixed-60 scores for all nine planned repeat runs. Its third decision-tree (P2) pass has **56/60** all-four matches, 58 valid answers and two preserved request failures; the three P2 scores are 57, 56 and 56. [P2 changes and failure counts](docs/GEMMA26_P2_REPEAT_FINDINGS_2026-10-02.md). The three base-task (P0) passes scored **59, 56 and 58/60**, with the second retaining one failed request. [P0 scores and usage](docs/GEMMA26_FRESH3_P0_CHECKPOINT_2026-10-02.md). The three classifier-instruction (P1) passes scored **58, 58 and 57/60**. The third has 59 valid answers and retains the DEV-059 timeout with a full unknown-charge bound; DEV-060 was sent once and returned a valid answer. Among the 59 reviews valid in all three P1 passes, one classification vector changed from the first to the third pass. [P1 interrupted findings](docs/GEMMA26_FRESH3_P1_INTERRUPTED_2026-10-02.md). These preserved failures make the nine-run series descriptive, not a clean matched-three experiment.

The [5 October analysis update](docs/ANALYSIS_REFRESH_2026-10-05.md) adds Clef Flash P1/P2 and Mistral 119B fresh1 P0 to the combined source-bound feed while retaining earlier cohort cutoffs. [See the updated comparison](https://adambkovacs.github.io/candidate-experience-benchmark/#analysis-update). Across the earlier 17 Claude configurations and four new Sonnet settings, neither added-instruction prompt beat the base task in all three passes for any configuration. That result describes within-configuration repeats, not a controlled comparison between models.

The [visual findings](https://adambkovacs.github.io/candidate-experience-benchmark/#findings) explain prompt changes, Jev's disagreements, difficult reviews and observed costs. The [analysis report](docs/FINDINGS.md) gives the interpretation and links to saved evidence. A separate [analysis of seven hosted continuation runs](docs/HOSTED_CONTINUATION_FINDINGS_2026-09-28.md) compares field changes and output failures. Those runs departed from the planned schedule and remain outside the strict paired cohort.

- Adding a decision tree after classifier framing reduced agreement in 21 of 39 audited hosted/subscription setups, improved it in 4, and left 14 unchanged. Extra instructions did not consistently help.
- The 18 Codex configurations in the published repeat cohort completed their three-pass studies. Classifier instructions improved agreement in every pass for two configurations; decision-tree instructions did so for none. [See the repeat analysis](docs/CODEX_REPEAT_SYNTHESIS_2026-09-28.md).
- SemIf matches 54/60 testimonial labels in its completed native passes, but identifies only four of nine reference-positive testimonials. [Class-level findings explain the difference](docs/SEMIF_REPEAT_FINDINGS_2026-09-28.md).
- SemIf completed three fresh generated-output passes per prompt. Each P0 pass matched all four labels on 35/60 reviews; P1 matched 26/60 and P2 matched 43/60 in each pass. No answer changed among reviews valid in all three passes: 0/52 for P0, 0/38 for P1 and 0/58 for P2. The same eight, 22 and two reviews respectively returned the schema instead of a classification every time. [Generated-output findings](docs/SEMIF_GENERATED_REPEAT_FINDINGS_2026-09-30.md) remain separate from its native option-scoring results.
- Three native Laya configurations produced unchanged answers across three passes, but each matched all four reference decisions on 0 of 60 reviews. [Repeatability did not imply agreement with the rubric](docs/LAYA_REPEAT_FINDINGS_2026-09-28.md).
- Jev matched all 25 reviews whose reference reported a serious concern. Its six all-four disagreements included an off-topic review, a misread positive review and cases with documented reference-boundary questions.
- Returning no for every testimonial judgment already matches 50 of 60 references. Read field scores alongside their class balance.

Use [model comparison](https://adambkovacs.github.io/candidate-experience-benchmark/#models), [prompt versions](https://adambkovacs.github.io/candidate-experience-benchmark/#explore), and [usage details](https://adambkovacs.github.io/candidate-experience-benchmark/#usage) to investigate a specific result. The results include first passes and repeat studies of the same 60 synthetic reviews. They are not a held-out leaderboard.

[Qwen's nine completed combinations](docs/QWEN36_OFF_REPEAT_FINDINGS_2026-09-29.md) retain two provider failures. Its decision-tree prompt gained one or two all-field matches over the base prompt on shared-valid reviews in each pass, with interrupted dispatch limiting the comparison. [DeepSeek low's first fresh pass](docs/DEEPSEEK_LOW_FRESH_REPEAT_FINDINGS_2026-09-29.md) matched all four fields on 58/60 reviews for P0 and 57/60 for P1. P0 had 59 valid outputs; P1 had 60. Seven planned condition/pass combinations remain unclosed. The [latest P2 interruption](docs/DEEPSEEK_LOW_THIRD_INTERRUPTION_FINDINGS_2026-10-01.md) retains 46 valid, one invalid, three failed and ten unsent positions; it has no full-run score.

[Qwen 27B's completed third-pass comparison](docs/QWEN27_V2_SECOND_CONTINUATION_FINDINGS_2026-10-01.md) shows why failed requests need to stay visible. Medium scored 57/60 with the base prompt and 56/60 with classifier instructions; xhigh scored 58/60 with either. Each base-prompt run retains one service error. Among the 59 reviews answered in both conditions, medium changed two four-field answers and xhigh changed one. The [full three-pass analysis](docs/QWEN27_V2_FINAL_DESCRIPTIVE_FINDINGS_2026-10-01.md) now shows medium-effort classifier instructions scoring below the base prompt in all three passes. With those instructions, four of 60 comments changed at least one answer across passes. Interrupted dispatch limits the comparison; it does not establish that the prompt caused the changes.

The [follow-up reference review](docs/REFERENCE_REVIEW_V1.md) proposes one correction, which would change Jev from 54 to 55 all-four matches. Original labels and published scores remain preserved.

The [repeat comparison](https://adambkovacs.github.io/candidate-experience-benchmark/#repeat-analysis) now covers multiple GPT, Claude, Gemini and other hosted configurations, plus native Jev instructions. Three separately dispatched passes often change the apparent prompt advantage. For example, [Opus 5 high](docs/OPUS5_REPEAT_FINDINGS_2026-09-28.md) gained two matches from decision-tree instructions in its first two passes and lost two in its third. [Fable 5.1 low](docs/FABLE_REPEAT_FINDINGS_2026-09-28.md) returned the same 57/60 classifier-instruction score in all three passes while changing three reviews' classifications. A stable total does not imply stable answers.

[Haiku's fresh three-pass comparison](docs/HAIKU_MATCHED3_FINDINGS_2026-09-28.md) ranges from 53 to 59 classifier-instruction matches out of 60. [Sonnet 5 medium](docs/SONNET5_REPEAT_FINDINGS_2026-09-28.md) gained two and one matches from those instructions in its first two passes, then lost four in the third.

[Sonnet 5.5's fresh matched-three study](docs/SONNET55_FRESH_MATCHED3_FINDINGS_2026-10-02.md) completed all 36 effort/prompt/pass cells with 60 valid answers each. Xhigh matched all four provisional fields on 58/60 reviews in every cell, yet changed a review's answer across passes under P1 and another under P2. Low P2 ranged from 56 to 57/60. The [source-bound feed](public-site/sonnet55-fresh-matched3.json) and [sanitized evidence](public-site/sonnet55-fresh-matched3-evidence/report.json) retain the scores, flips, usage, and original guard-failed smoke separately.

The [Gemini 3.8 Flash low repeats](docs/GEMINI38_LOW_REPEAT_FINDINGS_2026-09-28.md) kept a 57/60 base-prompt score in all three passes while changing one review’s classification. The [fresh Gemma E2B local study](docs/GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md) kept a 35/60 base score while changing nine reviews. Neither model gained all-field matches from either added-instruction prompt in these series. Local timing is reported separately from hosted timing.

The [Gemma E4B thinking-off repeats](docs/GEMMA_E4B_FIRST_PASS_FINDINGS_2026-10-01.md) are complete for all three prompts. The decision-procedure prompt scored 42/60 in every pass, yet seven comments changed at least one classification. The base task ranged from 38 to 40 matches; classifier instructions ranged from 40 to 41. All nine passes returned 60 answers in the required format. These results describe one local setup and the same fictional comments.

The Qwen3 1.7B SDK thinking-on setup has completed three passes of each prompt version. Added instructions scored lower in every matched pass on these 60 reviews:

| Prompt | All-four matches in passes 1 / 2 / 3 | Reviews whose labels changed across repeats |
| --- | --- | --- |
| Base task (P0) | 24 / 23 / 24 out of 60 | 19 of 60 |
| Classifier instructions (P1) | 12 / 11 / 16 out of 60 | 30 of 60 |
| Decision rules (P2) | 8 / 9 / 8 out of 60 | 40 of 58 valid in all three |

P0 and P1 returned 60 valid answers in every pass. P2 returned 59, 59 and 60; the two format failures remain in the score denominators. Nearly identical totals did not mean identical decisions. Testimonial agreement stayed lower under P1 (18–21/60) and P2 (13–14/60) than P0 (36–41/60). [The exact local configuration, usage and evidence](docs/LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md) stay separate from smaller models and hosted runs. Other configurations remain unfinished.

Qwen3 1.7B with thinking disabled has closed its first P0/P1/P2 passes, scoring 28/25/32 all-four matches out of 60, with 60/59/57 valid answers. P1 preserves one strict-JSON failure (DEV-029); P2 preserves three (DEV-002, DEV-005 and DEV-018). All four failures were JSON answers wrapped in Markdown code fences. The protocol requires bare JSON; outputs were not repaired. Decision rules improved the first-pass all-four total over P0 while reducing format validity. This differs from thinking-on, where P2 scored below P0 in all three passes. These are observations of the exact settings, not a general effect of reasoning or prompt detail. Thinking-off has completed all nine full passes: P0 scores 28/26/26, P1 scores 25/26/25, and P2 scores 32/30/30 out of 60. P2 valid counts were 57/56/55. Across three passes, at least one label changed on 10/60 P0 reviews, 12/59 reviews valid in all P1 passes, and 7/48 valid in all P2 passes. The stopped third P2 smoke is preserved; a separately reviewed admission allowed the full pass with unchanged requests and strict parsing. Later runs used battery power, recorded separately from earlier AC timing. [Detailed repeat findings](docs/LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md).

[Qwen3 0.6B now has three full passes per prompt through each tested HTTP and SDK setup](docs/LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md). The HTTP setup returned valid classifications every time, but no review matched all four reference answers. Its predictions stayed identical across repeats; under the base prompt, it marked all 60 reviews as potential testimonials against nine in the reference key.

The SDK setup with thinking enabled behaved differently. Base-prompt scores were 0/60 in all three passes, classifier instructions scored 1/60, 3/60 and 2/60, and the decision-tree prompt scored 3/60, 1/60 and 1/60. Among reviews valid in all three passes, at least one label changed for 5/5, 36/40 and 47/52 reviews respectively. With thinking disabled, strict-format failures left no review valid in all three passes for any prompt, so label stability cannot be measured. These findings describe this exact small quantized model and its distinct routes, not the wider Qwen family. The three larger configurations in this local repeat plan remain pending.

The separate [Gemma E2B thinking-on control](docs/GEMMA_E2B_THINKING_ON_FIRST_PASS_FINDINGS_2026-09-30.md) completed all nine phases, each with 60 valid answers. Across three passes, P0 scored 38, 37 and 39; P1 scored 36, 39 and 39; P2 scored 36, 36 and 35 out of 60. Answers changed on 24, 18 and 24 of the same 60 comments respectively. A narrow score range can hide changed decisions. These observations do not establish the effect of enabling thinking.

[AnyJev's raw native readout](docs/ANYJEV_RAW_REPEAT_FINDINGS_2026-09-28.md) returned unchanged classifications across three passes but matched all four fields on 0/60 reviews. It predicted neutral sentiment, follow-up needed and serious concern for every review. Stable output alone does not establish useful classification.

[AnyJev's fresh generated JSON control](docs/ANYJEV_GENERATED_REPEAT_FINDINGS_2026-09-30.md) completed three full passes per prompt. P0 and P1 returned 60 fenced, invalid responses and scored 0/60 in every pass; neither has valid classifications to compare across passes. P2 returned the same 30 valid and 30 invalid reviews each time, scored 1/60, and had 0/30 observed four-field changes among reviews valid in all three passes. This generated control is separate from AnyJev's native readouts.

[AnyJev L0](docs/ANYJEV_L0_REPEAT_FINDINGS_2026-09-28.md) also returned unchanged classifications in all three passes, with 60 valid outputs each, but only 4/60 reviews matched all four provisional reference fields. It answered "insufficient information" for follow-up 44 times against one such reference. The raw and L0 methods differ in several ways, so the score gap does not tell us which change caused it.

[Alex OpenJev 0.8B](docs/ALEX_NATIVE_REPEAT_FINDINGS_2026-09-28.md) matched all four reference decisions on 3/60 reviews in each of three fresh native passes, with no changed classifications. All outputs were valid, but it marked 59 reviews as potential testimonials, including 49 reference-negative cases. Its 0.8B native repeat study is complete. The [4B native study](docs/ALEX4B_NATIVE_REPEAT_FINDINGS_2026-09-29.md) also completed all three passes: 39/60 each, with no changed classifications. It missed the same eight of 25 reference-positive serious concerns in every pass.

Across the [17 Claude configurations reviewed on 28 September](docs/CLAUDE_REPEAT_SYNTHESIS_2026-09-28.md), neither added-instruction prompt beat the base task in all three observed passes. The full requested repeat matrix remains unfinished; see the [full repeat execution inventory](docs/REPEAT_EXECUTION_STATUS_2026-09-28.md) and [current objectives](docs/CURRENT_GOALS.md).

The [six additional fresh Codex comparisons](docs/CODEX_FRESH_REPEAT_FINDINGS_2026-09-29.md) are complete: three passes for each of three prompt versions. Neither added-instruction prompt improved all-four agreement in every pass for any of the six configurations. Classifier instructions switched between a gain and a loss in four configurations. These 3,240 responses still describe the same 60 reviews, not 3,240 independent cases.

The [DeepSeek Flash reasoning-off repeats](docs/DEEPSEEK_FRESH_REPEAT_FINDINGS_2026-09-29.md) completed all nine runs. The original prompt scored 48–49/60, classifier guidance 45–47/60, and the decision-tree prompt 43–46/60. Both added-instruction prompts scored lower in every matched pass, although testimonial agreement improved. The complete series including smoke tests cost $0.02913576 in observed provider charges.

## What the models decide

| Judgment | Question |
| --- | --- |
| Sentiment | Is the candidate's experience positive, negative, mixed, neutral, or unclear? |
| Follow-up needed | Does this feedback call for a response or action? |
| Serious concern reported | Does the candidate report a concern that warrants escalation? |
| Testimonial potential | Could this feedback be considered for a testimonial, subject to permission and review? |

The task concerns candidates' experience of a process. It does not assess their suitability for a job. All reviews are synthetic; no invented testimonial is a real endorsement.

## Jev alongside the alternatives

TypeSafe Jev is the starting point for this comparison. The roster also includes OpenJev, SemIf, AnyJev, Laya and NLI specialists; GPT and Claude subscription configurations; Gemini; and hosted Qwen, Gemma, DeepSeek and Mistral configurations. Exact model, effort, route and controls matter: two rows sharing a model family are not necessarily the same experiment.

The saved TypeSafe Jev development result has **60 valid outputs out of 60**, with **all four judgments agreeing on 54 of 60 reviews**. Its recorded development cost estimate is **$0.00589**. That is a token-price estimate, not a provider-confirmed charge. The timing evidence includes 61 requests because one failed request preceded a successful continuation. See the [source report](results/comparison/REPORT.md) and [specialist registry](results/specialist-run-registry.json).

These are development findings, not a held-out leaderboard. The reference labels were drafted and reviewed with AI assistance; the project owner confirmed people checked all 60 reviews on 2 October 2026. The frozen v0.2 key remains provisional, with [proposed revisions](docs/REFERENCE_REVIEW_V1.md) kept separately. A model matching those references does not establish real-world reliability or general model quality.

The new native Jev instruction runs completed all 60 reviews: P1 and P2 each produced 59 valid responses and 53 all-four matches. Each had one response rejected by the unchanged probability validator because one distribution summed to 0.99. These failures remain in the score. P1 adds classifier instructions; P2 adds decision procedures to the native Choice questions. See the [native comparison report](results/jev-native-prompt-variants-v1/report.json) and [timing and prompt audit](docs/JEV_PROMPT_AND_TIMING_AUDIT.md).

Jev's server inference time is unavailable. Its earlier 2.2-minute display was the sum of 61 client requests, including a failed request. The public explorer now separates client timing from OpenRouter-reported generation duration, and displays input/output/reasoning tokens and actual or estimated cost. Provider generation duration is also not a measurement of pure accelerator computation.

Gemini now also has 27 completed hosted P0/P1/P2 runs through OpenRouter, covering nine model/effort configurations. Their smoke and development requests cost $2.328085 in total. Five invalid ten-review batches remain in the results; one additional configuration stopped at its rate-limited smoke. See the [Gemini run notes](docs/GEMINI_OPENROUTER_RUN.md).

## Does the prompt change the result?

| Condition | What changes |
| --- | --- |
| P0: baseline | The original task, rubric and output schema. |
| P1: classifier framing | An explicit classifier role and task instructions. |
| P2: SOP and decision tree | Classifier framing plus a procedure for making the judgments. |

Prompt comparisons have run. The original [38 audited paired comparisons](results/prompt-comparison-v1-2026-09-24/paired-reports/thirty-eight-eligible-comparisons.html) preserve eligibility checks. The current export also includes the [audited GPT-6 Sol medium comparison](results/prompt-comparison-v1-2026-09-24/paired-reports/codex-gpt-6-sol-medium-batch10/evaluation.json), bringing this cohort to 39. The accepted CLI patch difference and unobserved provider rendering limit causal interpretation. Other saved outcomes can be descriptive without qualifying as a controlled P0/P1/P2 comparison. Native classification interfaces do not automatically have equivalent generative prompt conditions.

Batch-context baselines remain separate from historical single-record runs. Missing results and invalid outputs remain visible; they are not dropped to improve a score. Read the [prompt protocol](docs/PROMPT_VARIANTS.md) for the exact distinctions.

## Reading the numbers

- **Valid / 60** counts responses that meet the output contract. A valid response can still disagree with every reference judgment.
- **Each judgment / 60** counts agreement for that field. **All four / 60** requires every judgment on a review to agree.
- **Request time** measures the recorded execution surface. A request may contain one review or a batch of ten. Summed request time is not necessarily elapsed wall time when requests overlap.
- **Tokens** use the provider's reported fields. Missing usage is unknown, not zero; cache and reasoning counts retain their provider meanings.
- **Cost** distinguishes observed API charges, estimates and unknown-charge bounds. Subscription fees and local hardware costs are not allocated per run.

Local timing depends on the recorded Mac, runtime and quantization. It is diagnostic evidence, not a hosted speed ranking. Hosted replacements have their own identities; a hosted result does not overwrite a local measurement.

## Reproduce the offline checks

```sh
git clone https://github.com/adambkovacs/candidate-experience-benchmark.git
cd candidate-experience-benchmark
python3 scripts/development_benchmark.py validate
python3 -m unittest discover -s tests -q
node --test tests/*.cjs
```

These checks do not launch paid inference or download models. Native Laya admission checks require the pinned local interpreter and checkpoint files; they report an explicit skip when those are absent. Runner-specific dependencies and instructions are in [development setup](docs/RUN_DEVELOPMENT.md) and [MVP run notes](docs/RUN_MVP.md).

To serve the saved public view locally:

```sh
python3 -m http.server 8768
# Open http://localhost:8768/public-site/
```

The website is static. Its published bundle contains an allowlisted result export and site assets; it needs no API key or backend. See [publishing notes](docs/PUBLIC_EXPLORER.md).

Provider keys belong in an ignored `.env` file, never in source code or saved results. See [credential setup](docs/CREDENTIALS.md) and the empty [environment template](.env.example).

## Data and evidence

| Start here | Contents |
| --- | --- |
| [60 inputs](data/pilot/inputs.jsonl) | Fictional candidate feedback used for this development run |
| [Labeling guide](docs/LABELING_GUIDE.md) | Judgment definitions and decision rules |
| [Provisional references](data/pilot/proposed_labels.jsonl) | Offline scoring labels, excluded from inference requests |
| [Output schema](schemas/judgments.schema.json) | Required fields and allowed values |
| [Pilot audit](docs/PILOT_AUDIT.md) | Dataset and reference limitations |
| [MVP status](docs/MVP_STATUS.md) | Operational progress and outstanding work |
| [Full roster accounting](docs/MVP_ROSTER_ACCOUNTING.md) | Every configuration, saved outcomes, exclusions and remaining blockers |
| [Harness research](docs/HARNESS_RESEARCH.md) | Options for reducing manual coordination in later runs |

The broader plan describes 400 records. **Only the 60 development records are in scope for this run; the remaining 340 have not been generated.** Future validation and test sets need separate authorization and independent reference review.

The repository was previously named `recruitment-feedback-demo`. Historical evidence retains original paths and identifiers so its hashes and provenance remain intact.

AnyJev L1's three calibrated passes each have 60 valid outputs and 6/60 all-field matches. Their classifications match across all 60 reviews, with zero pairwise flips and a three-pass all-field range of 6–6/60. Repeated agreement on this fixed set does not prove deterministic behavior elsewhere. [The findings](docs/ANYJEV_L1_REPEAT_FINDINGS_2026-09-29.md) explain its follow-up uncertainty, missed serious concerns and held-out calibration protocol.

AnyJev L2 completed three native passes, each with 60 valid outputs and 13/60 all-field matches. Their classifications were identical across all 60 reviews, with zero pairwise flips and a three-pass all-field range of 13–13/60. These fitted-head results use held-out folds within the development set; stable answers do not establish accuracy beyond it. [Read the class-level findings and measurement limits](docs/ANYJEV_L2_REPEAT_FINDINGS_2026-09-29.md).

OpenJev completed all three native P0 triplets with 60 valid outputs per pass. Fixed scored 53/60 and adaptive 52/60 all-field matches in each pass, with no within-mode classification flips. Thinking scored 53/60, 54/60 and 54/60; its pairwise comparisons changed at least one decision on 9, 9 and 4 reviews. Cross-mode score differences are descriptive. [Read the class-level findings and measurement limits](docs/OPENJEV_NATIVE_REPEAT_FINDINGS_2026-09-29.md).

The separate OpenJev generated-off and generated-on series have each closed all nine development phases. Generated-off P0 scored 48, 51 and 49 all-field matches out of 60 across three fresh passes; P1 scored 48, 50 and 49; P2 scored 51, 54 and 51. Generated-on P0 scored 54, 53 and 49; P1 scored 50, 46 and 49; P2 scored 46, 47 and 42. Among reviews valid in all three generated-on passes, 8/54 P0, 2/39 P1 and 8/35 P2 reviews changed a four-field answer. Invalid outputs remain in the fixed 60-review score denominator. The references are provisional, and these scores do not establish an instruction effect. [See the source-bound generated findings](docs/OPENJEV_GENERATED_REPEAT_FINDINGS_2026-09-29.md).

## License

This project is licensed under the [MIT License](LICENSE). Third-party dependencies and model weights retain their respective licenses.
