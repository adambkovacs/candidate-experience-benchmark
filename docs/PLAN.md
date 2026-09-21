# Recruitment Feedback Comparison — project plan

Updated: 2026-09-21. Status: planning; no dataset generated or model performance measured.
Repository: https://github.com/adambkovacs/recruitment-feedback-demo (private).

## Research question

Which tested configuration routes synthetic candidate-experience feedback reliably, at what observed cost and speed, and where does it fail or need human review?

The study can find that Jev wins, loses, or fits only some operating conditions. Build the evaluation before the showcase. This is a comparison of specified configurations, not a universal model ranking.

## Accepted decisions

- 400 entirely synthetic feedback records. No actual candidate records or real-data consent workflow.
- Candidate-experience triage first. Interviewer evidence versus hire/no-hire vote remains a separate future study.
- Compare equivalent tasks with provider-appropriate interfaces.
- Use the user's Codex and Claude Code subscriptions for supported local CLI runs. Use direct provider APIs for Jev and hosted DeepSeek/Qwen as available.
- Local test machine: M4 MacBook Pro, 128 GB unified memory. LM Studio is installed. Exact chip variant and runtime version remain to be recorded.
- Evaluate small local models and a roughly 27B-class model. Gemma 4 and Qwen are candidate families.
- Keep reference labels hidden from evaluated models; freeze settings before testing.
- Build a failure explorer and case-study presentation after results are available.

## Dataset: exactly 400 unique records

| Split | Count | Use |
| --- | ---: | --- |
| Development | 60 | Includes first 30 pilot records; refine rubric and prompts |
| Validation | 40 | Select settings and review thresholds |
| Ordinary-case test | 200 | Plausible everyday synthetic feedback |
| Challenge test | 100 | Deliberate stress tests |
| Total | 400 | |

The ordinary-case set is synthetic, not statistically representative of recruitment traffic. Report ordinary and challenge results separately. Related scenarios and paraphrases stay in one split. Repeated inference does not increase the unique-record count.

Proposed ordinary-case allocation: 40 ordinary positive, 40 ordinary negative, 50 mixed, 30 neutral/vague, 25 specific praise, 15 serious reported concerns. These are primary generation categories; output labels can overlap. Development and validation cover every output label and each routing branch.

Challenge set: ten families of ten records each: politeness versus severity; negation; resolved versus unresolved; mixed praise and complaint; attribution and quoted allegations; missing context; instruction injection; irrelevant hire/reject outcome; style/typos/paraphrases; off-topic or unusable content. Within the 100, reserve 40 records for 20 paired tests (ten invariant-meaning pairs and ten meaning-changing pairs). Keep pairs together and account for their dependence in uncertainty estimates.

Generate from a scenario specification with varied stage, role, length, writing style, and outcome. Use fictional people and employers; never imply that synthetic quotes are real endorsements or allegations. English first.

## Generation and reference-label workflow

1. Define label meanings and scenario facts before generating prose.
2. Draft 30 development examples and refine the rubric.
3. Produce the remaining 370 with multiple available generators and manually written seed scenarios; record generator provenance. If multiple generators are unavailable, disclose the single-generator limitation.
4. Deduplicate and assign stable IDs and scenario-family IDs.
5. Humans label without seeing generator identity, intended category, or model predictions. AI-generated labels remain provisional until reviewed.
6. Prioritize independent second review for held-out records and serious concerns. If only one human reviewer is available, disclose it; do not describe model consensus as human ground truth.
7. Preserve ambiguity, acceptable answer sets where justified, and reviewer disagreement.
8. Freeze dataset, reference labels, rubric, and split manifest before final evaluation.

No publication-consent fields or workflow are required for invented records. Testimonial potential means suitability as a hypothetical editorial shortlist, not permission to pass fictional quotes off as real.

## Four core judgments

| Judgment | Contract |
| --- | --- |
| Sentiment | positive / negative / mixed / neutral / insufficient_information |
| Follow-up needed | yes / no / insufficient_information: an unresolved recruitment issue calls for a response or remedy |
| Serious concern reported | yes / no / insufficient_information under an explicit escalation rubric |
| Testimonial potential | yes / no / insufficient_information: specific, self-contained praise with usable context |

Sentiment is independent of operational labels. Mixed is not uncertainty. Topics and severity scoring are deferred.

Escalation rubric: reports of threats, harassment, discriminatory remarks, exposure of private information, or ignored agreed accessibility arrangements go to escalation review; the model is not determining whether allegations are proven. Ordinary frustration alone is not escalation.

Each adapter returns the same categorical contract. For Jev, map primitives explicitly: Choice for sentiment; separate answerability checks plus yes/no probabilities for the other judgments, or equivalent Choice questions with all three outcomes. Freeze and document that mapping. Never equate a probability near 0.5 with objectively insufficient information.

Code composes judgments into simulated routes: escalation review, ordinary follow-up, testimonial shortlist, analytics, or human review. Multiple flags may coexist. No real messages or publication.

## Comparison roster and scope control

Original target: 9 model configurations plus a rules baseline. Expanded candidate research now includes Gemini, tiny generators, and open decision models; see [model research](MODEL_RESEARCH.md). The final roster is selected on development data and frozen before held-out testing.
- Jev: one pinned version.
- Codex: two supported model/settings configurations available to the user's ChatGPT Pro subscription.
- Claude Code: two supported configurations available to the user's Claude Max subscription.
- Gemini: Pro-class and Flash-class candidate configurations through a supported Google AI Pro client; verify actual exposed models, pinning, and noninteractive access locally.
- Hosted DeepSeek: one pinned model and provider endpoint.
- Hosted Qwen: one pinned model and provider endpoint.
- Local generative candidates: Qwen3-0.6B, Qwen3.5-4B, Gemma 4 26B A4B, and Qwen3.8-27B. Use development screening to select a compact final roster.
- Primary local decision-server candidate: razorback16/OpenJev on DiffusionGemma 26B A4B through its documented MLX backend. This is the exact project the user supplied. The separately discovered Laya 421M is optional; exclude the user-supplied SalesRLAgent checkpoint because it predicts sales conversion rather than our four judgments; SemIf and AlexWortega/OpenJev 0.8B NLI are optional distinct alternatives. No assumption that custom classification paths run through LM Studio.
- Rules baseline: fixed keyword/negation heuristics, with limitations documented.

Exact model availability must be checked on the user's accounts; never claim that all ChatGPT or Claude web models are available in the CLIs. Avoid expanding the roster until the pilot establishes a reason.

Local candidate pool, verified in official sources on 2026-09-21:
- Gemma 4 E4B for the small-model slot.
- Qwen3.8-27B for the larger slot.
- Gemma 4 26B A4B or 31B as an alternative or targeted follow-up. Gemma 4 has no 27B size in the current official overview.
Select actual artifacts only after checking runtime support and doing a short local fit/speed test. Record total versus active MoE parameters accurately. Memory fit does not establish acceptable speed. Start with a supported 4-bit artifact, then test another precision only if a concrete quality issue warrants it.

## Equivalent tasks and isolation

Same rubric, source text, required output fields, and allowed task context for every configuration. Use provider-supported structured output. Do not demand generated explanations in the main test.

Fixed development-only tuning budget: up to three prompt/settings candidates per configuration. Freeze the selected candidate before held-out runs. No test-informed retries or prompt edits.

One independent record per fresh model context in the primary test; no 400-record conversation. CLI runs use a clean workspace with no reference labels, prior outputs, repository instructions, memories, or unrelated tools available. Disable unnecessary capabilities through supported controls; document unavoidable agent instructions, tools, and wrapper behavior. The controller logs results outside the inference workspace. If isolation cannot be enforced, label that run as a distinct agent workflow.

Primary retry policy: up to two retries for transient transport/rate-limit failures with backoff; record every attempt and elapsed time. Invalid schema/model output is an observed failure, not silently repaired. Any optional repair workflow is evaluated separately.

Codex exec and Claude Code print mode support structured outputs. Use ordinary supported subscription sign-in, respect account limits, and pause on quota exhaustion. Do not extract subscription credentials into custom provider API clients or silently enable paid overage. Hosted APIs require securely configured credentials and an agreed spend cap before execution.

## What the comparisons mean

Report a shared task-quality table with explicit execution-surface columns (CLI subscription / direct API / local runtime). This compares observed configurations, not isolated model intelligence.

Report speed by workflow: end-to-end CLI timing includes process and agent overhead; hosted timing includes network; local timing includes the selected runtime. Record model-only timing only when genuinely exposed. Separate cold startup, warm interactive latency, and batch throughput. Randomize/interleave hosted runs to reduce ordering effects. Run local models one at a time, plugged in, without competing inference, recording runtime version, chip variant, quantization, context, power mode, and memory use.

Cost columns:
- Hosted API: actual billed usage and verified pricing, with retries/caching.
- Subscription: plan and date, observed quota use if available, and incremental charge; not fictitious API-equivalent dollars. Show unknown quota use as unknown.
- Local: runtime and hardware context; energy only if measured. Do not call it free or invent amortization.
Optional subscription allocation and human-review cost are separately labeled scenarios with explicit assumptions.

## Metrics and failure analysis

Core: per-judgment precision/recall, sentiment macro-F1, serious-concern missed count, unnecessary escalations, testimonial precision, schema failure and service failure rates, median/p95 end-to-end latency, total runtime, and observed cost/usage.

Show raw counts and denominators, ordinary versus challenge results, and paired uncertainty estimates that respect scenario-family grouping. Do not declare a winner for small inconclusive differences.

Review comparison: evaluate at matched review budgets (10%, 20%, 30%). Freeze ranking methods and thresholds on validation data; show realized test coverage, including tie handling. Jev probabilities and distribution-derived confidence are not equivalent to an LLM's self-reported confidence. Label each uncertainty method and evaluate its usefulness empirically. Do not apply one numerical threshold across providers.

Repeat a fixed 40-record test subset three times total to assess instability; keep repeats out of headline unique-case metrics. For illustration only, with nine configurations the first pass over 400 records is 3,600 record evaluations; two extra passes over 40 add 720, before development tuning or transport retries. This is an estimate of evaluations, not a token or price estimate.

Failure explorer classifies errors as model judgment, rubric ambiguity, missing information, reference-label error, output/schema failure, or service/runtime failure. Inspect confident mistakes and cases where systems disagree. Do not assume a more expensive model is the reference truth.

## Milestones

- [x] Repository and original plan.
- [x] Agree 400 synthetic records and expanded comparison scope.
- [ ] Finalize labeling guide, record schema, and 30 development examples.
- [ ] Review pilot; discover available CLI models and local runtime.
- [ ] Build minimal adapters and evaluator; smoke-test on development only.
- [ ] Complete dataset, blinded review, and frozen split manifest.
- [ ] Tune within fixed budget; freeze configurations.
- [ ] Run both held-out sets and fixed stability subset.
- [ ] Publish result tables, failure examples, reproducibility manifest, and limitations.
- [ ] Build lightweight failure explorer and five-minute showcase.
- [ ] Optional: test a cheap/local-to-strong-model cascade after standalone results.

No full app, ATS integration, elaborate dashboard, or second recruitment task before baseline results.

## Kaggle reconnaissance

Kaggle's public dataset-list endpoint returned:
- murtazaziya/best-buy-interviews: titled Best Buy Interviews, described as interview reviews, license listed as Unknown. Full content and reuse terms were not verified.
- thisiserfan/wikitajrobe-dataset: experiences/comments/company data; license listed as Other. Suitability not verified.
- noeyislearning/it-job-market-insights: company ratings/reviews, listed CC0; candidate-interview narrative coverage not verified.

Search-page access was unreliable and no files were downloaded. No dataset is selected. Synthetic remains the agreed primary path. Kaggle listing availability does not establish suitability or reuse rights. Revisit only if a clearly suitable, licensed source can save effort; any imported public records would be marked as a separate non-synthetic source.

## Remaining execution inputs

Confirmed: ChatGPT Pro, Claude Max, Google AI Pro, and LM Studio. Remaining: actual model availability and client versions; exact Mac chip variant; reviewer availability; paid API budget and credentials. These do not block drafting the rubric and synthetic pilot. The current cloud workspace does not have direct access to the user's Mac; local runs will require a local checkout and runner.

## Sources checked

- https://learn.chatgpt.com/docs/auth
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://code.claude.com/docs/en/authentication
- https://code.claude.com/docs/en/headless
- https://ai.google.dev/gemma/docs/core
- https://huggingface.co/Qwen/Qwen3.8-27B
- https://docs.typesafe.ai/primitives
- https://docs.typesafe.ai/confidence
- https://www.kaggle.com/datasets/murtazaziya/best-buy-interviews

No model performance or production-readiness claims have been established.

## Model-research update

See [MODEL_RESEARCH.md](MODEL_RESEARCH.md) for the dense/MoE distinction, OpenJev name disambiguation, Laya limitations, and candidate-screening approach. Candidate additions are untested. The user's March 2025 reference is confirmed as SalesRLAgent, distinct from the separately discovered Laya typed-decision checkpoint; see the research notes for the supplied checkpoint and confidence-routing paper. The 400-record split and four-label task remain unchanged.

OpenJev-specific protocol: record automatic re-reads, optional thinking, and all settings. Separate fixed single-read from adaptive default results. A matched same-model direct-decision versus generated-label experiment is a priority diagnostic. DiffusionGemma is a distinct diffusion checkpoint, not interchangeable with regular Gemma 4 26B A4B. Validate output schema independently for text-generation runs.
