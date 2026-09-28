# Current objectives and direction

Updated 2026-09-28 after classification-bench implementation moved to a separate user-started task. This document supersedes conflicting historical routing and scope statements. It does not authorize a higher spending cap.

## Standing objective

Complete and document the Candidate Experience Feedback Benchmark on the existing 60 synthetic development reviews. Do not generate the remaining 340 case-study records. The private classification-bench repository is now owned by a separate user-started task. Do not implement it or launch agents for it here. Its handoff is complete at private commit aff6f02. See [APP_GOAL.md](APP_GOAL.md) for the stable replacement goal text.

Reconcile saved evidence before dispatch. Preserve historical configurations, failures and completed attempts. Complete remaining roster work where the exact authorized route is available; otherwise record concrete blockers or evidence-backed exclusions. Prefer OpenRouter for Qwen, Gemma, DeepSeek, Mistral and Gemini within the existing aggregate $10 cap; TypeSafe has a separate $1 cap. Use supported Claude and Codex subscriptions for their models, without paid overage or credit redemption. Use local inference only where the required native interface or model has no suitable hosted route. Do not resume the cancelled DeepSeek download. Supported thinking efforts remain in scope; exclude max and ultra from future runs.

Run a declared repeatability study covering P0, P1 and P2 separately. Target three separately dispatched full passes per eligible configuration and condition: two additional passes only where the historical first pass meets the frozen protocol; otherwise declare a new matched three-pass series. Repeats are authorized experimental work, distinct from retries, recovery, smoke tests and replay. Freeze model route, prompt bytes, settings, context/batch membership, parser and seed policy, and retain failed/invalid/missing outcomes. Audit eligibility and costs before launch; do not exceed existing caps. Keep the complete repeat matrix visible, including blocked or unsupported entries, rather than silently narrowing it.

Keep reference labels and prior predictions out of inference. Record exact observable model/runtime/quantization/hardware, controls, request timing, token usage and observed or estimated costs with missingness. Never silently repair outputs, substitute models or present client timing as pure inference time. Review disputed references against the rubric; keep corrections versioned and preserve original evaluations. Report per-field/all-field agreement, validity, class balance, paired prompt changes, per-record repeat flips and score ranges. Repeated responses are not independent new reviews, and separate requests do not prove statistical independence when provider caching or serving behavior is unknown. AI-reviewed references are not human ground truth.

Keep this task focused on the case study. Record reusable lessons here for the separate tool task to consult. Do not change its code, datasets or spending authority. Preserve the case-study archive and avoid a framework migration while the experiment is running.

Use deterministic code for bookkeeping and cheaper agents for suitable bounded work; use parallel agents with exclusive ownership. Keep current status, analysis, public case-study presentation and repository documentation consistent. Run relevant checks, commit and push verified changes, and finish each checkpoint with exact completed, pending and blocked work. Do not claim the complete MVP or repeat study is finished while required work remains.

## Guidance and status sources

The latest user instructions control scope and authorization. This document records the standing direction; frozen manifests and saved attempt evidence establish what actually ran. Attached goal snapshots and older plans are historical context when their checkpoints conflict with newer verified evidence. Update this document as milestones change, without rewriting frozen experimental inputs. The standing objective continues under the latest user instructions; a stale attached checkpoint is not a reason to restart completed work or restore superseded routing. Keep the app goal limited to the standing objective and a link to this document. Run counts, implementation progress and budget balances belong in dated checkpoints, so that a fixed attachment cannot become a competing status source.

## Work order and separate completion milestones

1. Finish the case study with its existing adapters. Reconcile the full requested roster, finish available authorized runs, and record exact blockers for the rest. The 53 complete comparison groups are a subset of the roster, not permission to omit unfinished configurations.
2. Complete the P0/P1/P2 repeat study within the approved budgets and subscription quotas. Publish within-condition variation alongside paired prompt effects so a small single-pass difference is not presented as a reliable improvement. Keep label adjudication separate from model consensus.
3. Publish the findings and supporting evidence on the public case-study site. Explain denominators, show Jev comparisons prominently, and distinguish measured inference time from client request time. Missing token, price or inference measurements remain explicitly unavailable.


Execution and publication take priority over optional coordinator improvements. Run independent, admitted provider configurations concurrently within shared budget reservations and provider limits; preserve the frozen order within each configuration. A shortfall for the entire paid matrix does not block affordable waves. Stop affected work at a real route, quota or spending boundary and report the exact remaining requirement. Additional funding requires explicit authorization.

The baseline/prompt study and repeat study have separate completion milestones. Tool development belongs to the separate task and must not delay publication of completed benchmark evidence here.

## Checkpoint reviewed on 2026-09-28

Ten configurations now have all nine P0/P1/P2 and pass combinations complete: GPT-6 Luna medium; GPT-6 Sol medium and high; Gemma 26 off; Gemma 31 off and on; Qwen 27 off; Claude Opus 5.5 medium; and Gemini 3.6 and 3.7 Flash low. Each combination contains 60 valid outputs. These are completed configurations within the wider requested matrix, not completion of the whole study. Reports use provisional v0.2 references and preserve the original public first-pass analysis separately. See the [latest repeat analysis](REPEAT_CHECKPOINT_2026-09-28.md).

Mistral has eight full combinations and one second-pass P1 combination with 59 valid responses plus the retained DEV-043 HTTP 429. Its 17 previously never-sent records were completed in a separate suffix. All four later phases are now closed with 60 valid responses each. The changed timing and failed position remain visible; this is not a clean nine-pass series. See the [continuation evidence](../results/repeatability-v1/openrouter-paid-mistral-small32-24b-venice-not-applicable/later-phases-v1/) and [budget reconciliation](../results/repeatability-v1/openrouter-paid-mistral-small32-24b-venice-not-applicable/budget-reconciliation-v1.json).

The seven hosted repeat allocations are closed. The OpenRouter ledger accounts for **$6.69733468150**, leaving **$3.30266531850** under the existing $10 cap. This includes conservative unknown-charge bounds and is not an invoice total. The completed Gemma 31 on, Qwen 27 off, Gemini 3.6 low and Gemini 3.7 low waves cost $0.09300556, $0.082192125, $0.13433850 and $0.15271350 respectively, including their smoke calls. Mistral records $0.070531 known charges plus the $0.025024 unknown-charge bound. Recheck the [ledger](../results/openrouter-paid-budget.jsonl) before new allocations; the older budget preflight is a historical estimate, not the current balance.

The specialist audit confirmed saved results for Laya, SemIf, OpenJev, AlexNLI and AnyJev. They were hard to find because the public ranking default excluded local specialists. The site now starts with all routes and offers a direct specialist filter. Laya's three expanded-context variants each have 60 valid outputs; its original context-limited configurations remain unsupported. SemIf direct, serial and shared each have 60 valid outputs; generated P2 has 59 saved outputs, 57 valid, two invalid, and DEV-033's started outcome remains unknown. Validity is not agreement with the reference. See the [roster accounting](MVP_ROSTER_ACCOUNTING.md) and [SemIf reconciliation](../results/prompt-comparison-v1-2026-09-24/semif-generated-exact/P2-continuation-v1/reconciliation.json).

Reference review still has a proposed DEV-006 correction and unresolved DEV-013/030 sentiment adjudication. No human adjudication or silent reference change is claimed. The earlier Qwen thinking-on partial run also retains 37 valid outputs, five service errors and 18 never-sent positions in its [saved report](../results/qwen36-on-p2-final19-v4/SUMMARY.md).

The private tool handoff is complete at aff6f02 and no longer pending work here. Its separate task owns further implementation. The [handoff](https://github.com/AI-Enablement-Academy/classification-bench/blob/main/docs/HANDOFF.md) requires organization access.

The earlier app goal was usage-limited. The user has since replaced its text with the benchmark-only objective, and the API now confirms it is active. No reset credit or paid overage was enabled.

## Execution update at 2026-09-28 08:50 UTC

The earlier checkpoint above records ten configurations closed before this wave. Since then, GPT-5.6 Luna high and low have each closed all nine condition/pass combinations, with 60 valid responses per combination; their report integration is under review. Jev's six new native Choice passes are closed: repeat2 P0 has 58 valid outputs and two retained invalid distributions (DEV-040/055); the other five new passes have 60 valid outputs each. Its original first-attempt P0 retains DEV-046's transport failure, and original P1/P2 each retain one invalid distribution. Jev evidence and its public report were committed in c6aee0f; verify deployment before calling that update live. Any statement that no second or third passes have run is obsolete.

Jev's 378 new smoke and development requests have a token-price estimate of $0.040207104. Its shared ledger accounts for $0.062434344, including the retained historical unknown-charge bound, leaving $0.937565656 under $1. These estimates and bounds are not a verified invoice.

Four Gemini configurations are executing on OpenRouter: 3.1 Pro low and 3.6, 3.7 and 3.8 Flash medium. Their $2.70 combined allocations make the master ledger account for $9.39733468150, leaving $0.60266531850 unallocated at this checkpoint. Allocated capacity includes unfinished work and is not spent money. Reconcile closed partitions before calculating final headroom. The [next-wave inventory](HOSTED_REPEAT_NEXT_WAVE.md) retains the other unfinished Gemini configurations and the possible funding shortfall.

GPT-5.6 Luna medium and Sol high repeats are running in their subscription lane. Fable 5.1 low/medium repeats are running, with high/xhigh prepared. Exact controls are in the [Codex](CODEX_REPEAT_ROSTER.md) and [Claude](CLAUDE_REPEAT_ROSTER.md) roster documents. Haiku remains required and needs separate first-pass eligibility handling; its historical failed batch is not a complete valid result.

## Gemini completion update, 2026-09-28

All four configurations in the latest Gemini wave now have nine closed condition/pass combinations: 3.1 Pro low and 3.6, 3.7 and 3.8 Flash medium. The first three produced 60 valid outputs in every combination. Gemini 3.8 has five combinations with 50 valid outputs and ten invalid outputs, caused by a truncated batch; the other four have 60 valid outputs. Completed execution does not mean every output was valid. See the [Gemini repeat findings](GEMINI_REPEAT_FINDINGS_2026-09-28.md).

The four allocations are reconciled. Their six new passes and smoke calls cost $1.928587 according to returned provider charges. The master ledger accounts for $8.62592168150, including prior unknown-charge bounds, leaving $1.37407831850 under $10. No additional spending cap has been authorized. The Qwen suffix still requires controller review before allocation.

The public deployment for commit 0755b39 succeeded, including the two completed Luna repeat series and the Jev report. The new Gemini report and findings are published in d8f7786; GitHub Pages deployment 36401659783 succeeded, and the public JSON and findings paragraph were fetched and verified. Fable low and medium have completed their six new development phases; report integration remains pending. Codex Luna medium/Sol high and Fable high/xhigh continue in their subscription lanes.

## Qwen capacity update, 2026-09-28

After the reviewed controller fixes and 13 passing offline tests, the first never-sent Qwen position, DEV-043, returned HTTP 429 from AkashML with `queue_timeout` and `upstream_provider_shared_pool`. This is a provider-capacity failure, not evidence of exhausted account credits. The episode stopped, retained the full $0.0299008 unknown-charge bound and released its unused allocation. The master now accounts for $8.65582248150, leaving $1.34417751850 under $10.

The composite has 37 valid outputs, six service errors and 17 never-sent positions. The [publication record](../results/qwen36-on-p2-never-sent-episodes-v1/episode-001/PUBLICATION.md) explains the exact failure and the explicitly redacted public error copy. The original response remains private because it contains an account identifier. Further calls need a new admission after capacity review; no failed position is replayed. The requested $15 cap increase is still pending.

## Next delivery checkpoints

1. Verify the Jev deployment; finish and publish active Gemini, Codex and Claude waves from closed evidence. Keep invalid responses and original first-attempt failures visible.
2. Reconcile and admit the remaining requested hosted and subscription configurations against routes, frozen protocols, quotas and current budgets. Finish the never-sent Qwen suffix only after its exact route and preserved failures are audited. Do not replay failed positions.
3. Complete native-specialist eligibility work, unresolved-attempt dispositions, reference-review follow-up, repeat analysis and publication. Do not relabel unknown started attempts as never sent. Required human adjudication remains pending rather than fabricated.
4. Keep the full requested roster and remaining funding or route requirements explicit. Completed subsets do not replace that roster. Do not exceed the $10/$1 caps without new user authorization.

Freeze the requested roster for this study. A newly discovered model does not automatically add another required configuration. Changes to roster, protocols or budgets need a recorded decision.

## Completion boundaries

The case study is complete only when each required baseline/prompt/repeat configuration has an evidence-backed disposition and the requested available runs are finished within budget. A recorded blocker explains unfinished work; it does not count as a completed run or an accepted exclusion. Report a budget-limited or route-limited checkpoint as such. Required work can be removed from completion scope only by an explicit user decision. Completion of the separate classification-bench task is outside this task's completion criteria.
