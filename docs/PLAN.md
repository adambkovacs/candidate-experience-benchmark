# Recruitment Feedback Comparison — project plan

Updated: 2026-09-21. Status: development runs in progress. Claude completed all 16 model/effort configurations; hosted Jev and local Qwen0.6B/1.7B/4B runs completed; see RUN_MVP.md and results/. Labels remain provisional.
Repository: https://github.com/adambkovacs/recruitment-feedback-demo (private).

## Research question

Which tested configuration routes synthetic candidate-experience feedback reliably, at what observed cost and speed, and where does it fail or need human review?

The study can find that Jev wins, loses, or fits only some operating conditions. Build the evaluation before the showcase. This is a comparison of specified configurations, not a universal model ranking.

## Accepted decisions

- 400 entirely synthetic feedback records. No actual candidate records or real-data consent workflow.
- Candidate-experience triage first. Interviewer evidence versus hire/no-hire vote remains a separate future study.
- Compare equivalent tasks with provider-appropriate interfaces.
- Use the user's Codex and Claude Code subscriptions for supported local CLI runs. Use direct provider APIs for Jev and hosted DeepSeek/Qwen as available.
- Local test machine: M4 MacBook Pro, 128 GB unified memory. LM Studio is installed. Verified Apple M4 Max, 16 CPU / 40 GPU cores, 128 GB; LM Studio 0.4.16+2, llama.cpp Metal 2.22.0. See results manifests.
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

Generate from a scenario specification with varied stage, role, length, writing style, and outcome. Use fictional people and employers; never imply that synthetic quotes are real endorsements or allegations. English first. Broad industries and seniority levels, as confirmed by the user.

## Generation and reference-label workflow

1. Define label meanings and scenario facts before generating prose.
2. Draft 30 development examples and refine the rubric.
3. Development allocation is now complete (60). The remaining 340 are ON HOLD until separately authorized. The future generation plan is to use multiple available generators and independently authored seed scenarios where available; record generator provenance. If multiple generators are unavailable, disclose the single-generator limitation.
4. Deduplicate and assign stable IDs and scenario-family IDs.
5. The user delegated development review to the assistant. Record this as same-assistant AI review, not human ground truth. For independent review, hide generator identity, intended category and model predictions.
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

Escalation rubric: see LABELING_GUIDE.md v0.2 for threats, harassment, identity-linked exclusion, retaliation, intrusive selection inquiries, exposure of private information and refused/ignored requested accessibility arrangements. Prior agreement is not required. The model flags reported concerns for review, not proven allegations or legal violations. Ordinary frustration alone is not escalation.

Each adapter returns the same categorical contract. For Jev, map primitives explicitly: Choice for sentiment; separate answerability checks plus yes/no probabilities for the other judgments, or equivalent Choice questions with all three outcomes. Freeze and document that mapping. Never equate a probability near 0.5 with objectively insufficient information.

Code composes judgments into simulated routes: escalation review, ordinary follow-up, testimonial shortlist, analytics, or human review. Multiple flags may coexist. No real messages or publication.

## Comparison roster and scope control

The original target was 9 model configurations plus a rules baseline. The current user-authorized development roster below supersedes that initial shortlist and includes Gemini, tiny generators, and open decision models; see [model research](MODEL_RESEARCH.md). The final roster is selected on development data and frozen before held-out testing.
- Jev: one pinned version.
- Codex: two supported model/settings configurations available to the user's ChatGPT Pro subscription.
- Claude Code: two supported configurations available to the user's Claude Max subscription.
- Gemini: Pro-class and Flash-class candidate configurations through a supported Google AI Pro client; verify actual exposed models, pinning, and noninteractive access locally.
- Hosted DeepSeek: one pinned model and provider endpoint.
- Hosted Qwen: one pinned model and provider endpoint.
- Local generative candidates: Qwen3-0.6B, Qwen3.5-4B, Gemma 4 26B A4B, and Qwen3.8-27B. Use development screening to select a compact final roster.
- Primary local decision-server candidate: razorback16/OpenJev on DiffusionGemma 26B A4B through its documented MLX backend. This is the exact project the user supplied. The separately discovered Laya 421M is included; exclude the user-supplied SalesRLAgent checkpoint because it predicts sales conversion rather than our four judgments; SemIf and AlexWortega/OpenJev 0.8B NLI are included distinct alternatives. No assumption that custom classification paths run through LM Studio.
- Rules baseline: fixed keyword/negation heuristics, with limitations documented.

Exact model availability must be checked on the user's accounts; never claim that all ChatGPT or Claude web models are available in the CLIs. The user has authorized the expanded development roster and supported thinking levels; unsupported configurations must have explicit evidence rather than disappear from the comparison.

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
- [x] Draft and AI-review v0.2 rubric, schema and all 60 development records.
- [x] Add minimal LM Studio runner/evaluator and verify with offline fixtures and mocked transport.
- [ ] Run live development configurations; finalize rubric before generating the remaining 340.
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

Confirmed: ChatGPT Pro, Claude Max, Google AI Pro, and LM Studio. Verified runtime and hardware are recorded in result manifests. Remaining execution dependencies include local weight downloads and disk capacity, Gemini isolation, subscription quota, and service availability for the agreed batch10 subscription workflow. Development references have same-assistant AI review; independent human adjudication remains absent. Execution now runs on the user's Mac in the local checkout. Hosted TypeSafe has an approved aggregate $1 cap; other hosted API calls remain free-only unless separately approved.

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

Development measurements now exist; no held-out performance or production-readiness claims have been established.

## Model-research update

See [MODEL_RESEARCH.md](MODEL_RESEARCH.md) for the dense/MoE distinction, OpenJev name disambiguation, Laya limitations, and candidate-screening approach. Candidate additions are untested. The user's March 2025 reference is confirmed as SalesRLAgent, distinct from the separately discovered Laya typed-decision checkpoint; see the research notes for the supplied checkpoint and confidence-routing paper. The 400-record split and four-label task remain unchanged.

OpenJev-specific protocol: record automatic re-reads, optional thinking, and all settings. Separate fixed single-read from adaptive default results. A matched same-model direct-decision versus generated-label experiment is a priority diagnostic. DiffusionGemma is a distinct diffusion checkpoint, not interchangeable with regular Gemma 4 26B A4B. Validate output schema independently for text-generation runs.

## Pilot artifacts

- [Draft labeling guide](LABELING_GUIDE.md)
- [Feedback-only review sheet](PILOT_REVIEW.md)
- [Proposed answers and rationales](PILOT_PROPOSED_LABELS.md)
- [Model inputs](../data/pilot/inputs.jsonl) and [provisional labels/metadata](../data/pilot/proposed_labels.jsonl)
- [Judgment output schema](../schemas/judgments.schema.json)

All 60 are development records, generated and provisionally labeled/reviewed by one assistant. Exact generator model ID is not exposed. None are human-adjudicated. Paired scenario families remain in development. Inference runners must receive only feedback and the rubric, never the answer key or generation metadata. The current drafting conversation has seen the key and cannot serve as an isolated benchmark run.

## Critical review and executable development phase

[Audit](PILOT_AUDIT.md) records five corrected records (six label corrections), rubric gaps and source grounding. [Local run instructions](RUN_DEVELOPMENT.md) describe the standard-library LM Studio adapter and evaluator. Run offline checks with `python3 tests/test_development_benchmark.py`. Tests use fixtures and mocked HTTP, not live model predictions.

All 60 development records now exist; 340 remain ungenerated. Preserve the 400 ceiling. The 100-record challenge set will include at least 40 bias/concern probes overlapping existing families. Within its existing 20 pairs, allocate at least eight to identity/style invariance and four to meaningful evidence changes. Controlled development pairs never migrate into held-out sets. Report false escalations on benign identity mentions and missed reports separately; synthetic pair consistency cannot establish real-world demographic fairness.

The development smoke runner records transport failures without retries; final evaluation must implement and freeze the planned retry protocol. Jev, subscription and specialist adapters now exist; completed runs include latency summaries and hosted TypeSafe cost capture. Specialist inference is still awaiting verified weights. Calibrated review thresholds and held-out evaluation remain future work. The user-delegated AI review allows development to proceed without falsely claiming human validation.

## Current execution scope (user clarification, 2026-09-21)

Run the existing 60 development records only. Do not generate the remaining 340. Reuse completed configuration artifacts instead of repeating them. Each new configuration starts with three records and response inspection before the full 60.

The user expanded the MVP to cover supported reasoning-effort levels, Haiku, and verification of Fable 5.1 availability. Include all listed Qwen sizes (0.6B, 1.7B, 4B, 8B, 27B), Gemma candidates, and the previously optional specialist projects and OpenJev variations. A model without a supported task mapping or accessible artifact must receive an explicit documented blocker; do not silently substitute another model or claim a completed run. SalesRLAgent remains incompatible with the four-label task without a separate adaptation experiment.

Downloads and hosted jobs may run in parallel. Serialize local inference and stage large downloads to fit available disk space. Exact effort support is model-specific; unavailable controls are recorded as such rather than sent as ignored parameters. TypeSafe's **$1 total** authorization covers all its configurations and retries together. On September23, the user authorized reasonably priced OpenRouter routes instead of matching local downloads. Those runs use a separate aggregate $1 cap; see [the hosted execution decision](OPENROUTER_COST_REVIEW.md).

## Follow-up prompt experiment (user request, 2026-09-21)

After the current model/settings comparison is finished, compare the existing baseline with two new generative-LLM prompt conditions: explicit classifier framing, and the same framing plus a rubric-derived SOP and decision tree. Preserve model settings and the same 60-record development scope, log exact prompt versions and role placement, and compare response changes, failures, quality, token usage and latency. See [the prompt experiment protocol](PROMPT_VARIANTS.md). This does not alter active runs or expand paid API authorization.

## Roster reconciliation (user clarification, 2026-09-21)

Include Codex Sol and Terra alongside Luna and Astra at verified supported effort levels. Reconcile the account catalogue and runner version before each smoke. The user also requested larger Qwen, DeepSeek and Mistral candidates. [ROSTER_RECONCILIATION.md](ROSTER_RECONCILIATION.md) pins the practical Qwen3.6-35B-A3B, DeepSeek-R1-Distill-Qwen-32B and Mistral-Small-3.2-24B artifacts, with Mistral-Small-4-119B separately staged pending disk and memory capacity. The DeepSeek distill is a Qwen-based variant; the original hosted DeepSeek slot remains separately recorded. Verify runtime/template support, inspect smoke responses, then run the existing 60. The September23 user-directed hosted switch is recorded in [OPENROUTER_COST_REVIEW.md](OPENROUTER_COST_REVIEW.md). Hosted configurations remain distinct from local artifacts, with completed local results preserved.

The user raised the quota cost of 60 individual expensive reasoning calls. A 10-record multi-input configuration has been proposed; its adoption is pending. Keep it distinct from individual-request results. Previously completed Claude runs are retained. Do not launch new expensive full sweeps until this method choice is resolved.

## Resumed scope, 2026-09-23

The user added Nokia Applied Research AnyJev (https://github.com/nokia-applied-research/AnyJev), Claude Opus 5.5, GPT-6 Sol and GPT-6 Luna. Verify exact artifacts, subscription availability and supported controls before inference. Remove max and ultra from future execution; retain already completed results as historical measurements. Low, medium, high and xhigh remain eligible only where supported.

Remaining subscription configurations use ten records per fresh prompt after the three-record smoke gate. Record batch membership and order, shared request timing and workflow class. Do not present shared batch latency as independently measured per-record latency or silently pool these runs with one-record requests. Reference labels remain offline.

Laya uses convaiinnovations/laya, with English, typed-decisions and multilingual checkpoints. Native input-length limits and expanded-context variants are logged separately. AnyJev raw/L0 are label-free; L1 calibration needs a defensible separate calibration/evaluation split and must not fit and evaluate against the same 60 labels. The remaining 340 records remain ungenerated.

## September23 hosted DeepSeek selection

The original hosted DeepSeek slot is separate from the local R1-Distill-Qwen-32B candidate. Select `deepseek/deepseek-v4.1-flash` through the explicitly pinned OpenRouter `open-inference/fp4` provider, subject to fresh endpoint validation and the same $1 aggregate OpenRouter cap. The saved catalog advertises reasoning off, low and high; max remains excluded. Current flat endpoint prices are $0.10/$0.50 per million input/output tokens. Model and provider identifiers are pinned in requests; exact serving weight revision and hardware remain undisclosed. Inspect smoke3 before each full60 configuration. Source snapshots are in `results/openrouter-paid-planning-2026-09-23/`.
