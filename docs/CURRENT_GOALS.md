# Current objectives and direction

## E4B continuation accounted for, 6 October 2026

The eight never-sent E4B thinking-on fresh2/P2 reviews finished on battery without a host sleep transition. All eight responses are valid; seven matched all four references. The full interrupted pass now has 58 valid responses, two earlier unknown outcomes and no unsent reviews, with a descriptive score of 48/60. It remains outside clean repeat coverage. [Accounting and source evidence](../public-site/e4b-interruption-findings.json).

## Jev and Qwen reconciliation, 6 October 2026

Jev P0 and P1 each have three full passes. P0 scores 54/53/52 out of 60; P1 scores 54/53/54. Invalid distributions remain failures. The second P2 pass and its continuation together account for all 60 attempts: 57 valid, one invalid and two unknown, with 50 all-four matches. It remains interrupted. The third P2 pass returned 60 valid answers and scored 54/60; its classifications differ from the first P2 pass on DEV-030 despite the equal totals. Updated report publication is pending.

Qwen3.5 has two closed full phases out of nine. Its next P2 smoke produced an invalid output; the subsequent P1 smoke stopped during host sleep, leaving DEV-003 unknown. Neither smoke admitted a full pass. Battery use is enabled, but sleep checks remain active.

## Native prompt update, 6 October 2026

Kev P1 and P2 each completed three full passes, with 60 valid responses per pass. P1 scores 49/60 all-four matches and P2 scores 46/60 in every pass; follow-up agreement falls from 58/60 to 53/60. No labels changed within either three-pass condition. [Kev findings](KEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md) are verified and published; Pages run 37453498358 succeeded and live asset bytes match commit f0515800. OpenRouter Jev first P1/P2 passes each score 54/60 with 60 valid responses. Its second P1 has 59 valid and one invalid response; second P2 is interrupted by HTTP 429 after 17 valid answers. These are unfinished repeat studies. See [the checklist](TODO.md) for the exact continuation and publication state.

## Qwen3.5 P1/P2 update, 6 October 2026

Qwen3.5 4B thinking-on has closed its first P1 and P2 passes: **47/60 and 50/60 all-four matches**, respectively. Each has 51 valid responses and nine invalid outputs. Among the 47 reviews valid in both passes, two changed sentiment under P2 and became full matches. This is one matched prompt comparison; repeatability is still untested. The next P2 smoke stopped when DEV-001 exhausted the 4,096-token output limit without returning JSON. Its full pass was not sent. Clean coverage is 2/9; the interrupted P0 remains descriptive. [Findings](QWEN35_P1_FIRST_PASS_2026-10-06.md).

## Qwen3.5 interruption, 6 October 2026

The first fresh thinking-on P0 pass and its eight-review continuation now account for all 60 positions: 51 valid responses, eight invalid responses and one unknown outcome. Its descriptive all-four score is 47/60 (47/51 among valid answers); it remains 0/9 clean completed phases. [The interruption report](QWEN35_P0_INTERRUPTION_2026-10-06.md) preserves the evidence and timing caveat. The separate continuation for DEV-053–060 is closed and reviewed; DEV-052 remains unknown and must not be replayed. No inference is running at this checkpoint.

## Mistral P1 execution update, 5 October 2026

The reviewed P1 successor was attempted through the exact hosted route. Its first smoke request returned upstream HTTP 429; the remaining smoke reviews and full P1 pass were not sent. The [terminal evidence](../results/repeatability-v1/mistral119-fresh-matched3-v1/p1-successor-v1/smoke.terminal-public.json) retains the failed position and unknown-charge bound. No retry or scope exclusion is authorized by that failure. Qwen3.5 was running at that checkpoint and subsequently stopped as recorded above; see [the checklist](TODO.md) for current ownership. Earlier completed scores remain unchanged.

Updated 2026-10-05 with Clef Flash P1/P2 repeats, the final interrupted Mistral P0 checkpoint and report category work. The classification-bench implementation remains owned by a separate user-started task. This document supersedes conflicting historical routing and scope statements. It does not authorize a higher spending cap.

## Local power policy, 5 October 2026

The user authorized local inference on battery. `config/local-execution.json` now sets `allow_battery_power` to true. Current preflight uses `scripts/local_host_admission.cjs` through `scripts/legacy_qwen_current_preflight.cjs`; power source, battery percentage and policy hash are recorded in new receipts. AC is no longer an admission requirement. Open-lid, memory and sleep checks remain. Preserve historical receipts and distinguish battery observations when comparing timing; no model request settings or reference labels change.

## Current checkpoint, 5 October 2026

Qwen3 1.7B SDK thinking-on has completed all nine planned runs. P0 scores 24/23/24, P1 12/11/16 and P2 8/9/8 out of 60. P0 and P1 are valid on all 60 reviews in every pass; P2 has 59/59/60 valid outputs, preserving earlier format failures on DEV-012 and DEV-033. Across three passes, labels vary on 19/60 reviews for P0, 30/60 for P1 and 40/58 valid in all three P2 passes. P1 and P2 score below P0 in every matched pass. The [updated findings](LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md) keep this exact local configuration separate from hosted Qwen models; fresh route checks found no exact hosted family. Final smoke inspection, all-60 runtime/render/token preflight and post-run host checks passed. The wider roster is not complete: the 1.7B thinking-off matrix is now complete, while the 3.5 4B thinking-on matrix and other recorded work remain pending.

Qwen3 1.7B with thinking disabled has closed its first P0/P1/P2 passes, scoring 28/25/32 all-four matches out of 60, with 60/59/57 valid answers. P1 preserves one strict-JSON failure (DEV-029); P2 preserves three (DEV-002, DEV-005 and DEV-018). All four failures were JSON answers wrapped in Markdown code fences. The protocol requires bare JSON; outputs were not repaired. Decision rules improved the first-pass all-four total over P0 while reducing format validity. This differs from thinking-on, where P2 scored below P0 in all three passes. These are observations of the exact settings, not a general effect of reasoning or prompt detail. Thinking-off has completed all nine full passes: P0 scores 28/26/26, P1 scores 25/26/25, and P2 scores 32/30/30 out of 60. P2 valid counts were 57/56/55. Across three passes, at least one label changed on 10/60 P0 reviews, 12/59 reviews valid in all P1 passes, and 7/48 valid in all P2 passes. The stopped third P2 smoke is preserved; a separately reviewed admission allowed the full pass with unchanged requests and strict parsing. Later runs used battery power, recorded separately from earlier AC timing. [Detailed repeat findings](LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md).

This checkpoint supersedes unfinished-run statements in the dated history below. [Clef Flash P1](CLEF_FLASH_P1_FINDINGS_2026-10-05.md) and [P2](CLEF_FLASH_P2_FINDINGS_2026-10-05.md) each have three closed 60-valid passes, scoring 47/60 and 46/60 respectively. No labels, native probabilities or vendor confidence values changed within either condition. Flash's third P0 pass remains interrupted (DEV-001 and DEV-002 unknown, DEV-003–060 never sent after the 5 October continuation hit a provider quota limit); Clef fresh1/P1 is closed with 60 valid answers and 52/60 all-four matches; its two further P1 passes and all three P2 passes remain required. The [first P1 findings](CLEF_P1_FIRST_PASS_2026-10-05.md) preserve the separate single-pass comparison. The pending request to increase the separate $10 postapproval cap is not approval. Existing caps still apply.

Gemma's nine planned phases now have descriptive results, including retained failures; [P1 scores are 58/58/57](GEMMA26_FRESH3_P1_INTERRUPTED_2026-10-02.md) on the fixed 60-review denominator. Mistral fresh1/P0 attempted all 60: 55 valid, five failed and 40 all-four matches. Its [report](MISTRAL119_FRESH1_P0_FINDINGS_2026-10-05.md) passed clean-checkout reconstruction and exact-byte verification in `324695e3`; Pages publication is verified, including exact live feed bytes. Other Mistral conditions are unfinished. [DeepSeek's exact required endpoint remains absent](ROUTE_RECHECK_2026-10-05.md); other endpoints do not continue that frozen configuration.

The [analysis update](ANALYSIS_REFRESH_2026-10-05.md) incorporates the new prompt/repeat results. The 130-source combined feed includes Clef's first P1 result and the later Flash P0 interruption. It is live, with exact analysis asset bytes verified after Pages job `37314865502`. Report filters now distinguish model purpose, verified task-specific training and output interface, which may overlap. Desktop, mobile and keyboard checks passed. The [Cloudflare leaderboard](https://clef-evals.workers-ai-mle.workers.dev/) is a design and model-discovery reference, not an additional source of scores for our dataset or automatic admission of every listed model. See [TODO](TODO.md) for current owners and verification status.

## Clef and report filtering, 2 October 2026

The user requested testing Cloudflare Clef following [Cloudflare's announcement](https://blog.cloudflare.com/clef-decision-models/), and better report sections, categories and filters. Prepare both Clef and Clef-Flash through their native typed-choice interface on the same 60 reviews. Preserve native prompt variants and three-pass identities, with references used only offline. The user subsequently approved tests and live runs up to $10 overall in this discussion. The versioned postapproval ledger applies that ceiling across new paid work, including Cloudflare and new OpenRouter allocations; it is not $10 per provider. Existing provider-specific ceilings and prior unknown-charge bounds remain in force. The [third-P0 checkpoint](CLEF_P0_THIRD_CHECKPOINT_2026-10-02.md) now records three full Clef P0 passes, each 60 valid and 53/60 all-four agreement. Clef Flash has two full P0 passes; its third stopped after one unknown outcome and left 59 reviews unsent, so it has no third score. P1/P2 and the unfinished Flash pass remain required. The [first-pass findings](CLEF_FINDINGS_2026-10-02.md) and [two-pass findings](CLEF_P0_REPEAT_FINDINGS_2026-10-02.md) keep their own dated cutoffs. This request does not transfer private classification-bench credentials or live-run authority.

## Execution boundary, 2 October 2026

The [source-bound Gemma findings](GEMMA26_POSTABORT_FINDINGS_2026-10-02.md) recorded seven of nine scored phases at their earlier cutoff, including interrupted fresh3/P2 with DEV-005 and DEV-006 failures preserved. Fresh3/P0 development later closed with 60 ordered valid responses and $0.01918032 observed cost, independently verified by root. The [P0 analysis](GEMMA26_FRESH3_P0_CHECKPOINT_2026-10-02.md) reports 59/56/58 all-four matches across three passes and advances published scored coverage to eight of nine. Fresh3/P1 development [stopped at DEV-059](GEMMA26_P1_INTERRUPTION_2026-10-02.md) after 58 valid responses; the timeout retains a $0.01974272 unknown-charge bound. The original $0.40 child is sealed and reconciled with $0.03995497 known charges and $0.34030231 unused allocation released. A separately admitted [DEV-060 suffix](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p1-dev060-suffix-v1/fresh3/P1/suffix.attempts.jsonl) then closed valid and was archived in `eed797b1`; its [$0.02 child reconciliation](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p1-dev060-suffix-v1/reconciliation.json) records $0.00041054 known cost and no unknown charge. All 60 P1 positions are accounted for, with 59 valid and the retained DEV-059 timeout. The combined score awaits a source-bound report; this is not a clean 60-valid pass, and DEV-059 must not be replayed. Mistral's $0.30 suffix child is allocated, but its first launch stopped at a nested source-drift gate before a phase claim or inference; a versioned fix is pending review and DEV-054–060 remain unsent. The [DeepSeek low cutoff](../public-site/deepseek-low-third-interruption-findings.json) remains at two of nine scored phases; the separately versioned price-aware DEV-051–060 successor passed review, but its fresh admission found the exact `open-inference/fp4` endpoint absent. No allocation or inference followed; the [route failure receipt](../results/repeatability-v1/deepseek-low-fresh3-v2/third-interruption-suffix-051-060-v1/blocked-route-20261002T164956Z.json) records the boundary. Never replay its earlier failed positions.

The [Fastino GLiNER2.5-Decide preflight](GLINER_NEXT_V1_PREFLIGHT_2026-10-02.md) has an offline 180-request manifest and fresh public catalog price of $0.03/M input, $0 output. Credentials, account entitlement, full-request token fit and an enforceable stage bound remain unresolved; no inference or allocation is admitted. The [roster accounting](MVP_ROSTER_ACCOUNTING.md#exact-requested-configurations-still-lacking-their-declared-full-result) lists the exact unfinished hosted, local and decision-route configurations without treating a blocker or smoke as a completed run. Keep the 163-entry historical roster, later additions and separate clean/descriptive repeat cutoffs distinct.

Keep general LLMs, task-fine-tuned LLMs and dedicated decision models filterable separately from output interface and execution route. Improve saved-run filtering by model family, reasoning setting and prompt; add repeat-study search and coverage filtering. Keep interrupted descriptive studies distinct from clean matched series, and preserve deep links and no-match states. Implementation, execution and published results must be reported separately.

## Resumed goal, 2 October 2026

The user resumed the full objective after the forced restart. [APP_GOAL.md](APP_GOAL.md) contains the active text. After each completed run or later interruption, refresh the combined analysis, website, README and coverage inventory against saved evidence. Keep historical and fresh cohorts separate and check whether earlier conclusions still hold. The restart does not authorize replaying completed requests.

## Scope and review update, 2 October 2026

Add Claude Sonnet 5.5 through the subscription CLI at low, medium, high and xhigh, with P0/P1/P2 and three declared full passes. Preserve its first stopped smoke and admit any changed guard as a separately versioned configuration. Max and ultra remain excluded. The user confirmed human checking of all 60 reference answers; keep original labels and scores versioned rather than silently changing them. Lower-page model selection, historical-to-matched-series links and cache-aware API-equivalent subscription price estimates are required website improvements. See [the latest checklist](TODO.md) and [prompt coverage audit](PROMPT_COVERAGE_AUDIT_2026-10-02.md).

The reported remaining OpenRouter account balance is available for this work within the existing authorization. It is not a new aggregate cap or permission to discard unresolved charge bounds. Ask for a numeric increase when the remaining authorized capacity prevents required execution.

## Scope update, 30 September 2026

The user-approved [app goal](APP_GOAL.md) now includes the newly requested decision models and Jev hosted-route comparisons from the [route audit](DECISION_MODEL_ROUTE_AUDIT_2026-09-30.md). Admit each exact configuration separately after interface, context, account and cost checks; these additions do not authorize spending above the existing caps. Website work must put useful comparisons first and keep detailed evidence accessible. Use [the current checklist](TODO.md) for ownership and next steps. Existing frozen runs and historical failures remain intact.

## Spending authorization, 30 September 2026

The user explicitly approved using a further $2.38 on OpenRouter: "I still have 2.38 left on openrouter, you're approved to use it." This raises the authorized aggregate experiment ceiling from $10 to $12.38. The $17 proposal remains unapproved. Preserve all existing unknown-charge bounds; an account balance is not evidence that those attempts were free. Versioned budget support and a recorded ledger amendment must precede new allocations. TypeSafe remains separately capped at $1. Earlier $10 statements are historical. Additional willingness to top up does not supply another numeric ceiling.

## Standing objective

Complete and document the Candidate Experience Feedback Benchmark on the existing 60 synthetic development reviews. Do not generate the remaining 340 case-study records. The private classification-bench repository is now owned by a separate user-started task. Do not implement it or launch agents for it here. Its handoff is complete at private commit aff6f02. See [APP_GOAL.md](APP_GOAL.md) for the stable replacement goal text.

Reconcile saved evidence before dispatch. Preserve historical configurations, failures and completed attempts. Complete remaining roster work where the exact authorized route is available; otherwise record concrete blockers or evidence-backed exclusions. Prefer OpenRouter for Qwen, Gemma, DeepSeek, Mistral and Gemini within the approved aggregate $12.38 cap (the original $10 plus the explicit $2.38 increase); TypeSafe has a separate $1 cap. Use supported Claude and Codex subscriptions for their models, without paid overage or credit redemption. Use local inference only where the required native interface or model has no suitable hosted route. Do not resume the cancelled DeepSeek download. Supported thinking efforts remain in scope; exclude max and ultra from future runs.

Run a declared repeatability study covering P0, P1 and P2 separately. Target three separately dispatched full passes per eligible configuration and condition: two additional passes only where the historical first pass meets the frozen protocol; otherwise declare a new matched three-pass series. Repeats are authorized experimental work, distinct from retries, recovery, smoke tests and replay. Freeze model route, prompt bytes, settings, context/batch membership, parser and seed policy, and retain failed/invalid/missing outcomes. Audit eligibility and costs before launch; do not exceed existing caps. Keep the complete repeat matrix visible, including blocked or unsupported entries, rather than silently narrowing it.

Keep reference labels and prior predictions out of inference. Record exact observable model/runtime/quantization/hardware, controls, request timing, token usage and observed or estimated costs with missingness. Never silently repair outputs, substitute models or present client timing as pure inference time. Review disputed references against the rubric; keep corrections versioned and preserve original evaluations. Report per-field/all-field agreement, validity, class balance, paired prompt changes, per-record repeat flips and score ranges. Repeated responses are not independent new reviews, and separate requests do not prove statistical independence when provider caching or serving behavior is unknown. AI-reviewed references are not human ground truth.

Keep this task focused on the case study. Record reusable lessons here for the separate tool task to consult. Do not change its code, datasets or spending authority. Preserve the case-study archive and avoid a framework migration while the experiment is running.

Use deterministic code for bookkeeping and cheaper agents for suitable bounded work; use parallel agents with exclusive ownership. Keep current status, analysis, public case-study presentation and repository documentation consistent. Run relevant checks, commit and push verified changes, and finish each checkpoint with exact completed, pending and blocked work. Do not claim the complete MVP or repeat study is finished while required work remains.

## Guidance and status sources

The latest user instructions control scope and authorization. This document records the standing direction; frozen manifests and saved attempt evidence establish what actually ran. Attached goal snapshots and older plans are historical context when their checkpoints conflict with newer verified evidence. Update this document as milestones change, without rewriting frozen experimental inputs. The standing objective continues under the latest user instructions; a stale attached checkpoint is not a reason to restart completed work or restore superseded routing. Keep the app goal limited to the standing objective and a link to this document. Run counts, implementation progress and budget balances belong in dated checkpoints, so that a fixed attachment cannot become a competing status source.

For the 29 September execution queue, including exact hosted, generic local and specialist IDs, use [the dated remaining-roster audit](REMAINING_ROSTER_2026-09-29.md). Its closed-phase counts and blockers supersede older progress prose below; frozen evidence and the current budget ledger still govern any new dispatch.

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

## Codex wave completion, 2026-09-28

GPT-5.6 Luna low, medium and high and GPT-5.6 Sol high have now closed all nine condition/pass combinations each, with 60 valid outputs in every combination. All 24 new development phases and their smokes are complete. The public report was rebuilt from a clean staged export; its 12 tests passed and the unchanged Jev report still reproduces. See the [updated repeat analysis](REPEAT_CHECKPOINT_2026-09-28.md).

The next four Codex configurations are in offline preparation: GPT-5.6 Sol low, medium and xhigh, and Terra high. Preparation is not dispatch. Fable high/xhigh repeats continue, followed by report integration. Haiku's saved P1 failure is attributable to a CLI ENOTFOUND transport failure, but its delayed suffix and retry history do not meet the existing matched-triple protocol. A separate fresh three-pass series is being prepared; the historical 50-valid/10-failed P1 remains preserved.

## Additional admissions, 2026-09-28

The completed four-configuration Codex wave is published in dad92c1; deployment 36403333599 succeeded and the public report was fetched with all seven published Codex series at nine completed combinations each. The next four configurations (GPT-5.6 Sol low/medium/xhigh and Terra high) are now admitted, with up to four independent configurations running concurrently under fresh phase-specific quota checks.

Haiku's separate matched three-pass study is frozen and admitted through the Claude subscription. Its P0 smoke passed and first development condition is running. The historical transport failure remains separate. See the [Haiku protocol](CLAUDE_HAIKU_MATCHED3.md).

Gemini 3.7 Flash high is also admitted on OpenRouter, with its first smoke passed and development running. A $1 child allocation raises master accounted/encumbered capacity to $9.65582248150, leaving $0.34417751850 unallocated under $10. This includes the full active allocation and is not actual spending. Reconcile it after closure. Gemini 3.1 Pro high is prepared in the reviewed controller but not allocated or dispatched; the requested $15 total cap remains pending. See the [high-effort wave](GEMINI_HIGH_REPEAT_WAVE.md).

## Subscription and high-effort progress, 2026-09-28

All four Fable 5.1 efforts (low, medium, high and xhigh) have closed both additional P0/P1/P2 passes: 24 development phases, 1,440 responses, all valid. Their report integration is in progress. Haiku has closed fresh pass-one P0 and P1 with 60 valid outputs each; the rest of its matched three-pass study remains in progress.

Gemini 3.7 Flash high has closed repeat two P0/P1/P2 and started repeat three. Its active allocation is unchanged; final spending will be reconciled after closure. GPT-5.6 Sol low/medium/xhigh and Terra high continue under their phase-specific subscription checks.

Opus 5 low, medium, high and xhigh have eight verified frozen repeat manifests. Their first smokes are admitted through the pinned Claude subscription runtime. Development requires inspection of each saved smoke before dispatch. No paid overage or new OpenRouter allocation is authorized by this update.

## Published and reconciled update, 2026-09-28

Fable's four effort series and findings are live in commit e31cf1c. Pages deployment 36406152132 succeeded; the public JSON and findings paragraph were fetched and verified. The clean staged export passed all 13 Claude report tests.

Gemini 3.7 Flash high now has nine closed combinations. Its three repeat-two conditions each have 60 valid outputs; all three repeat-three conditions have 50 valid and ten token-truncated invalid outputs. The historical P0/P1 each also retain ten invalid outputs. The closed wave returned $0.709266 in charges, bringing aggregate accounted spending and retained unknown-charge bounds to $9.36508848150. Remaining headroom is $0.63491151850; Gemini 3.1 Pro high remains pending budget admission. The requested $15 cap is not yet authorized.

Haiku has completed its first fresh full P0/P1/P2 pass, with 60 valid outputs per condition, and is running pass two. All four Opus 5 efforts have completed their first two repeat-two conditions and are progressing through the remaining frozen sequence. These are progress checkpoints, not completion of their three-pass series.

## Codex publication and remaining native work, 2026-09-28

GPT-5.6 Sol low/medium/extra-high and Terra high are published in 0e6770b. Deployment 36407950092 succeeded, and the fetched public report contains eleven Codex configurations with all nine combinations complete. The clean staged export passed 13 report tests; the Jev report was regenerated only to update its shared code binding, with its results unchanged.

The next admitted Codex wave is Terra extra-high and Astra low/high/extra-high. All four first smokes passed and development is running after fresh quota checks. No max or ultra efforts are admitted. Haiku has closed two full fresh passes, all conditions 60 valid, and is running pass three. Opus 5's four efforts are progressing through their final repeat-three conditions.

The remaining Opus 5.5 low/high/extra-high and four Sonnet 5 effort manifests are prepared and verified offline; preparation is not dispatch. The [native-specialist audit](NATIVE_SPECIALIST_REPEAT_AUDIT_2026-09-28.md) distinguishes fifteen saved native P0 outputs from original Laya length failures and AnyJev calibration-only work. Generative P1/P2 exclusions do not close the native P0 repeat requirement. The three expanded CPU Laya configurations are next in offline eligibility and admission preparation; no new local inference has started.

## Opus 5 publication, 2026-09-28

All four Opus 5 efforts now have nine closed condition/pass combinations, each with 60 valid outputs. Their two new passes contain 1,440 development responses, with smokes recorded separately. Commit e8fd6b5 passed 16 Claude report tests in a clean staged export; deployment 36409198713 succeeded. The fetched public report contains eight completed Fable/Opus 5 series, and the Opus findings paragraph is live. See [Opus 5 repeat findings](OPUS5_REPEAT_FINDINGS_2026-09-28.md).

Sonnet 5 low/medium/high/extra-high are admitted and running their frozen repeats through the Claude subscription. Opus 5.5 low/high/extra-high remain prepared but not dispatched. Haiku's third fresh pass, the next Terra/Astra Codex wave, and expanded Laya CPU admission preparation continue. OpenRouter accounted spending remains $9.36508848150, with $0.63491151850 remaining; no additional paid wave has been admitted.

## Execution and publication checkpoint, 2026-09-28 10:50 UTC

Haiku's fresh matched-three study has closed all nine condition/pass combinations with 60 valid development responses each. Its new source-bound report and four focused tests pass. P1 agreement ranges from 53 to 59 out of 60 across passes; its difference from P0 changes from -2 to +2. Historical Haiku transport failures remain separate. The report and site integration are prepared locally, not yet published.

All four Sonnet 5 efforts have closed repeat two and their first repeat-three condition. Opus 5.5 low/high/extra-high have closed their first two repeat-two conditions. Their next seven admitted P0 development phases are running under the pinned Claude 2.1.282 subscription runtime. The remaining Codex wave has completed additional phases, but new admissions are held because the app quota-check tool is failing. Already admitted requests may finish; no quota or overage guard is bypassed.

The native Laya admission plan and eight passing guard tests are committed and pushed in `78818f4`. It fixes the three expanded CPU variants, serial phase order, hardware/runtime, model assets and full-input checks. English repeat-two P0 passed its smoke and is running development. The six native development phases are not yet complete. No model download or new OpenRouter allocation was made.

Publication of the new Claude raw evidence is held for a privacy audit: CLI captures contain account-wide quota metadata that does not belong in the public report. Preserve immutable originals and their hashes; verify a redacted publication boundary before pushing new captures. This hold does not change inference evidence or stop admitted model runs. The current public site still contains the last verified published checkpoint.

## Claude closure and quota recovery, 2026-09-28

All four Sonnet 5 efforts and Opus 5.5 low/high/extra-high have now closed all nine condition/pass combinations per configuration. Every new development phase has 60 valid outputs. Across these seven configurations, the two new passes contain 2,520 development responses plus 126 smoke responses; all 294 captured requests passed the raw/control checks. The [Sonnet findings](SONNET5_REPEAT_FINDINGS_2026-09-28.md) and [Opus 5.5 findings](OPUS55_REPEAT_FINDINGS_2026-09-28.md) describe score reversals and per-review variation. New public evidence exports are still under review, so this does not claim the site has been updated.

The Codex quota service returned successfully after the earlier hold. New phases still need fresh per-phase receipts. The final three eligible roster configurations now have six prepared and reconstructed manifests: GPT-6 Luna high and extra-high, and GPT-6 Sol extra-high. Their pinned runtime and ChatGPT authentication check passed. The existing Terra/Astra wave retains its separate owner; no completed request is repeated.

Laya English repeat-two P0 is complete with 60 valid outputs and no changed classifications against its historical first pass. Typed repeat-two is running in the frozen serial sequence. Remaining native phases and the broader roster are still open. OpenRouter and TypeSafe caps are unchanged.

## Verified export and execution checkpoint, 2026-09-28

All seventeen eligible Claude configurations now have nine closed condition/pass combinations with 60 valid development responses in each. Haiku uses its separate fresh three-pass protocol. The new reports have verified public copies with immutable source snapshots and explicit original/public hash mappings. The exporter is committed in `9893c7e`; website integration is published in `b3d28ed`. GitHub Pages deployment `36417007326` succeeded, and all three Claude JSON files, the Codex report and page HTML matched the saved public files byte-for-byte after retrieval. Clean staged-checkout deployment checks passed. Earlier published account metadata still requires separate assessment, as explained in the [privacy record](PUBLIC_EVIDENCE_PRIVACY.md).

The current Codex report includes eighteen eligible configurations. Fourteen have all nine combinations closed; Astra extra-high and the final Luna high/extra-high and Sol extra-high series remain in progress. Reports include only closed phases, with unfinished combinations shown explicitly. Existing admissions retain exclusive execution owners.

All three expanded CPU Laya variants have closed repeat-two P0 with 60 valid results and no changed predictions against their own historical first passes. Repeat three is proceeding serially under the frozen native plan. These categorical stability results do not establish controlled inference timing. Hosted budget headroom remains $0.63491151850 under the unchanged $10 cap. The requested $15 cap increase is still pending; no new hosted wave is authorized by this checkpoint.

## Closed Qwen suffix and Terra/Astra update, 2026-09-28

The Qwen thinking-on P2 AkashML endpoint responded after a new exact-route review. Episode 002 sent only DEV-044–060 and returned 17 valid classifications, costing $0.0211142. Its closed child partition released $0.4871994 of unused allocation. The composite now has 60 attempted positions: 54 valid, six preserved service errors, zero never sent. No failed position was retried. It remains outside the clean paired-prompt cohort; the [publication record](../results/qwen36-on-p2-never-sent-episodes-v1/episode-002/PUBLICATION.md) explains the source and cost boundaries. Public explorer integration is pending.

OpenRouter master accounted charges and retained bounds are now $9.38620268150, leaving $0.61379731850 under $10. This does not fund the proposed $2 Gemini 3.1 Pro high allocation. The requested $15 cap remains pending.

Terra extra-high and Astra low/high/extra-high have all nine combinations closed, bringing completed Codex configurations to fifteen. Their public report is deployed in `bd7cd60`; Pages run `36419143867` succeeded, and the fetched report matched the committed bytes with fifteen complete configurations out of eighteen. The final Luna high/extra-high and Sol extra-high series continue. See the [Terra/Astra findings](TERRA_ASTRA_REPEAT_FINDINGS_2026-09-28.md) and [full repeat inventory](REPEAT_EXECUTION_STATUS_2026-09-28.md).

Laya English repeat three is closed with 60 valid outputs and no changes from either earlier pass. Its client elapsed sum differed substantially between repeats; uncontrolled local load/cache conditions prevent treating that as model-only latency drift. Typed and multilingual repeat three remain in progress. The [next native admission review](NATIVE_NEXT_REPEAT_ADMISSION_REVIEW_2026-09-28.md) supports SemIf direct/serial/shared eligibility; preparation does not authorize overlapping native execution.

The [current OpenRouter catalog audit](../results/route-audits/local-historical-small-models-20260928/catalog-audit.json) searched all 458 listed model IDs and names and found no Gemma E2B/E4B or Qwen3.5-4B matches. This is evidence about the public OpenRouter catalog only, not every possible host. The five exact local historical configurations remain pending runtime/artifact and repeat admission checks; the audit makes no inference calls or downloads.

## Next delivery checkpoints

SemIf completion checkpoint, 2026-09-28: all six additional native phases closed, yielding three passes for each of direct, serial and shared. Every pass has 60 valid outputs and no within-mode classification changes. All-four agreement is 36/60 in every direct pass and 35/60 in every serial/shared pass. The final report SHA-256 is `4bf539ce413e773bfec09c30fda8b502bd6300fe8b43cb85a41e922ca92c2e34`; published in `0d093ca`. Pages run `36436543860` succeeded, and the deployed report matched that SHA-256 exactly. No SemIf inference remains active.

Gemini 3.8 low historical review, 2026-09-28: the existing v2 report builder independently validates 60/60 outputs for P0, P1 and P2 (all-four matches 57, 56 and 56). P0 retains the original identity-verification stop and a metadata-backed recovery; its continuation sent only the remaining batches. The explicit recovered-parent adapter binds that v2 baseline to v3 P1/P2. The [source-bound review](../results/repeatability-v1/gemini38-low-historical-review-v1.json) is an evidence validation, not dispatch admission: repeat-controller compatibility, frozen controls and budget admission remain pending. No calls or charges were incurred.

SemIf publication checkpoint, 2026-09-28: four of six new native phases are closed (all repeat-two modes and direct repeat-three), each with 60 valid classifications and no within-mode changes. Commit `6b5a623` publishes these seven historical/new passes, the offline reporter and class-level analysis; the two remaining passes are visibly incomplete. Ten reporter tests, three UI tests and a relocated public-evidence build passed. Pages run `36432230557` succeeded; retrieved SemIf JSON, repeat JavaScript and HTML matched the committed bytes. The [analysis](SEMIF_REPEAT_FINDINGS_2026-09-28.md) separates 54/60 testimonial agreement from 4/9 reference-positive matches.

Codex closure checkpoint, 2026-09-28: all eighteen configurations now have nine complete P0/P1/P2 and pass combinations, each with 60 valid development outputs. The source-bound report rebuilt successfully and all fifteen offline tests passed. The [comparative synthesis](CODEX_REPEAT_SYNTHESIS_2026-09-28.md) finds consistent P1 gains in two configurations, no consistent P2 gains, and twelve configuration/condition groups whose unchanged scores concealed changed answers. Published in `1dd64c8`; Pages run `36431123734` succeeded. Retrieved `repeats.json` and `index.html` matched committed bytes exactly (report SHA-256 `e6acc3e09d4a2d59042e08d268c64ab9ff5a9949810513547802965d3f447c4a`). There are no remaining live Codex inference handles.

Latest integration checkpoint, 2026-09-28: the Qwen P2 explorer now includes the closed episode-002 evidence (54 valid, six retained failures, none never sent). Its known charges are $0.0628516 plus $0.1794048 of unresolved upper bounds; the bounds are not observed spending. The audited Sol medium comparison raises the hosted/subscription prompt cohort from 38 to 39, with the accepted CLI patch difference and provider-rendering uncertainty retained. P2 versus P1 now has 21 decreases, four increases and fourteen ties. Generated findings and copy were published in `a02383e`. Pages run `36423661248` succeeded, and retrieved data, findings and page HTML matched the committed bytes exactly.

Laya subsequently closed all six additional native P0 development passes with 60 valid outputs each. All three configurations now have three complete passes and no changed classifications, but all-four agreement remains zero in every pass. The [native findings](LAYA_REPEAT_FINDINGS_2026-09-28.md) explain the field-level mismatches. Its report and nine tests passed in a relocated checkout without private model assets. Publication commit `0f6c083` deployed successfully in Pages run `36424862025`; the Laya report, repeat UI and page HTML matched committed bytes after retrieval. At that earlier checkpoint, SemIf had begun its first development phase and the last three Codex configurations were still running. The Codex closure checkpoint above supersedes that execution status.

The [credential audit](CREDENTIAL_AUDIT_2026-09-28.md) found no matches for configured secrets in tracked files and classified every history-scanner detection as a hash or local model identifier. Its scope is explicit; historical provider-account metadata remains a separate privacy issue.

Earlier preparation checkpoint: SemIf native repeat preparation and P0-only UI support were committed in `9cca967`; Pages deployment `36420999273` succeeded. All nine offline SemIf checks passed in the pinned runtime. Laya was still active at that point and SemIf had not started; the later closure and execution status above supersede that state. Repository-local `.env` credentials are ignored and owner-only; no API key belongs in committed evidence.

1. Finish and publish remaining Gemini and native waves from closed evidence. All eighteen Codex configurations are complete and published. Jev's deployed repeat report was independently fetched and matched the saved bytes on 2026-09-28; Claude's seventeen configurations are published. Keep invalid responses and original first-attempt failures visible.
2. Reconcile and admit the remaining requested hosted and subscription configurations against routes, frozen protocols, quotas and current budgets. Qwen's closed suffix publication is verified; preserve its failed positions without replay.
3. Complete native-specialist eligibility work, unresolved-attempt dispositions, reference-review follow-up, repeat analysis and publication. Do not relabel unknown started attempts as never sent. Required human adjudication remains pending rather than fabricated.
4. Keep the full requested roster and remaining funding or route requirements explicit. Completed subsets do not replace that roster. Do not exceed the $10/$1 caps without new user authorization.

Freeze the requested roster for this study. A newly discovered model does not automatically add another required configuration. Changes to roster, protocols or budgets need a recorded decision.

## Completion boundaries

The case study is complete only when each required baseline/prompt/repeat configuration has an evidence-backed disposition and the requested available runs are finished within budget. A recorded blocker explains unfinished work; it does not count as a completed run or an accepted exclusion. Report a budget-limited or route-limited checkpoint as such. Required work can be removed from completion scope only by an explicit user decision. Completion of the separate classification-bench task is outside this task's completion criteria.

## Public evidence cleanup verified, 2026-09-28 14:49 UTC

Commit `2ef36e7` replaces 14 historical Claude evidence links with redacted public copies and removes 648 quota-bearing captures from the current Git tree. All working originals and private backups remain intact and hash-verified. Scores and usage are unchanged. The full Pages workflow passed in an actual staged-tree archive (97 Python tests and three UI tests), with four additional inventory tests passing. Independent review approved the change; historical Git exposure remains explicitly unresolved. Pages deployment `36438655663` succeeded, and live `data.json` and `findings.json` matched the committed files byte-for-byte. See the [cleanup record](PRIVATE_EVIDENCE_REMOVAL_PLAN_2026-09-28.md).

Gemini 3.8 Flash low repeat admission and AnyJev raw P0 repeat admission are being prepared offline in separate agent tasks. Neither has sent a new inference request. The five exact small-local configurations remain pending; the large-file hash fix is committed and the first smoke receipt now binds it, but runtime load verification must pass before dispatch. No new hosted spend or higher cap is authorized by this checkpoint.

## Repeat execution resumed, 2026-09-28

Gemma 4 E2B thinking-off completed fresh pass one for P0/P2/P1 and fresh pass two P2, each with 60 valid outputs. These are four of nine required development phases for this configuration; four other exact small-local configurations remain pending. A scoped LM Studio CLI reload matched all seven frozen load fields before inference. The SDK-only load attempt failed preflight without sending a request. The host is Apple M4 Max (Mac16,5), artifact Q4_K_M; backend preference is llama.cpp 2.22.0, while the loaded-instance engine version is unavailable. Raw runtime, timing and tokens are preserved per request; local client duration is not hosted or pure inference latency.

Gemini 3.8 Flash low completed its additional second P0/P1/P2 pass with 180 valid outputs. Smoke plus development charges total $0.07660425. Its third pass has started under the new source-bound controller. The $0.30 child partition stays within the unchanged $10 aggregate cap; it is an allocation, not actual spending. The historical first pass remains separately preserved with its recovered P0 identity evidence. Final partition reconciliation is pending.

The AnyJev raw native P0 controller and frozen plan passed nine offline tests and independent review. No AnyJev repeat inference has started. Historical native prompt identity is reconstructed from pinned source and tokenizer, with all 240 saved token lengths matching; absent historical prompt hashes remain disclosed. The local report builder is not yet published: review found that a process interruption before terminal metadata could hide an uncertain started attempt as not-started, and a fix with regression tests is in progress. These checkpoints do not complete the full repeat study.

## Gemini 3.8 Flash low repeats closed, 2026-09-28

Both additional P0/P1/P2 passes are complete: six development phases, 360 valid outputs, and six valid three-review smokes. Together with the audited historical first pass, all nine condition/pass combinations are closed. The partition records $0.15296100 observed charges, no unknown charges, and $0.14703900 released allocation. The master accounts for $9.53916368150, leaving $0.46083631850 under the unchanged $10 cap. The [reconciliation](../results/repeatability-v1/gemini38-low-p0-openrouter-v2/budget-reconciliation-v1.json) preserves the sealed child ledger hash. New findings and public report integration are still pending; execution closure is not publication. Gemini 3.1 Pro high remains awaiting sufficient authorized budget.

Gemma E2B thinking-off now has five closed development phases, all 60 valid: all three fresh-pass-one conditions and fresh-pass-two P2/P1. Fresh-pass-two P0 is active. AnyJev raw remains prepared and reviewed without inference.

## Gemma E2B publication and AnyJev raw checkpoint, 2026-09-28

Gemma 4 E2B thinking-off has completed all nine fresh P0/P1/P2 development phases: 540 valid outputs, plus 27 valid smoke outputs. P0 all-field agreement is 35/60 in every pass despite nine reviews changing classification; P1 scores are 34/33/33 and P2 scores are 31/31/33. The [findings](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md) distinguish local client timing from pure inference and hosted latency. Four other small-local configurations remain pending. The complete publication pipeline passed with 114 Python and six UI tests. Commit `59bd941` deployed successfully in Pages run `36446135330`; live small-local report, repeat JavaScript and HTML matched committed bytes exactly.

Gemini 3.8 Flash low findings are also published and byte-verified at commit `55d4569`. All three P0 scores remain 57/60 despite one changed review; P1 has five changed reviews and P2 three. The earlier execution-only checkpoint is superseded by this publication verification. OpenRouter accounting remains $9.53916368150 of the $10 cap; Gemini Pro high still requires additional authorization.

AnyJev raw native P0 repeat two completed all 60 records and exited successfully. Its completion record binds output SHA-256 `3caa0e952b110e72de6056a5564cf4f15caf4fb6732bfc7105e7e0be36ff5b96`. Third-pass admission is underway; the raw three-pass study is not yet complete. AnyJev L0 and Alex OpenJev 0.8B admission candidates are undergoing independent offline review. No new specialist result is claimed from preparation alone.

## AnyJev raw execution closure, 2026-09-28

AnyJev raw native P0 repeat three exited successfully with all 60 records valid. Its verified record hash is `afb9faf033d1500a75f00a4c19964c98b6bc3f25f9e0d5ccdf77e2205f078e99`. All three passes have identical classifications and 0/60 all-field agreement. The [findings](ANYJEV_RAW_REPEAT_FINDINGS_2026-09-28.md) explain the constant predictions and distinguish stable output from useful classification. Public report integration is pending independent review. AnyJev L0 has passed independent offline review and its separate repeat-two smoke admission has begun. Alex 0.8B's reviewed fresh-three plan is frozen in `6c238ca`; inference has not begun. OpenJev's candidate controller requires a stage-log correction before admission. Budgets and the full outstanding roster are unchanged.

## AnyJev raw publication verified, 2026-09-28

Commit `b124dba` published the complete AnyJev raw three-pass analysis. Pages run `36449477508` succeeded; live `anyjev-raw-repeats.json`, `repeats.js` and `index.html` matched committed bytes. The report hash is `8b729ad551a501aa71958df23fc26e8d491007d0af0361a08d6cd01798a36aa0`. Independent review approved the portable report and UI; a clean staged checkout passed 121 Python and nine UI tests. The report explicitly declares private model-asset hashes rather than claiming to rehash unavailable assets during publication.

AnyJev L0 repeat-two smoke exited successfully with three valid records. Root inspected all twelve finite normalized distributions and saved a source-bound inspection; the separate 60-record development admission has begun. Its full pass is not yet complete. Alex 4B passed eight tests and independent review, then its fresh-three manifest was frozen and reverified with hash `2fd72a67d00bddb1ced94c71b7c585ab9481081cc927ed08fa1fe58c83303e1a`; no Alex inference has begun. OpenJev's stage-log regression is fixed and tested in `e9f7b9e`; its native runs remain pending. Generated specialist controls and AnyJev L1/L2 retain distinct admission requirements in their new audits. No cap or roster change is implied.

## L0 analysis and generated-control preparation, 2026-09-28

The portable L0 report passed independent review and seven offline tests, including a synthetic closed-pass fixture that keeps an invalid output in the 60-review score denominator and excludes it from shared-valid flips. The fixture is not a benchmark run. The historical L0 pass scores 4/60 all-field agreement; repeat-two development remains active and unscored, and repeat three has not started. No partial live evidence is presented as a completed pass.

The Mistral terminal partial repeat already accounts for all 60 reviews: 59 valid and one service error, with zero never-sent positions. There is no missing suffix to dispatch. The expanded [execution inventory](REPEAT_EXECUTION_STATUS_2026-09-28.md) keeps native readouts, generated controls and L1/L2 calibration separate from the 55-series comparison. New generated-control controllers are under offline review; preparation is not a completed model run.

## SemIf generated runner verified, 2026-09-28

Commit `792ce89` freezes the independently reviewed SemIf generated P0/P1/P2 runner and its fresh three-pass schedule. Root reproduced all ten offline tests and manifest hash `b5b13e48cd92979404aeb35beb2f17adf738f8358b22a5f5f5a4a90e7c66ed38`. Complete responses that reach the output limit remain invalid outcomes; incomplete streams stop without replay. No SemIf generated repeat has been dispatched. The [admission note](SEMIF_GENERATED_FRESH_REPEAT_ADMISSION_2026-09-28.md) records the protocol and the residual requirement to audit a failed model load after a stage claim.

AnyJev L0 repeat two remains the sole active local inference process. Its latest inspected checkpoint contains 18 of 60 saved development records; this is partial progress, not a closed pass. Local GPU execution remains exclusive. OpenJev generated response handling is under review, and L1/L2 calibration implementation planning remains offline. Spending caps and outstanding scope are unchanged.

## Specialist analysis preparation and calibration review, 2026-09-28

The OpenJev native report builder is committed in `d4368b4`, with eight offline tests passing. The Alex 0.8B/4B report builder is committed in `5e6f605`, with seven offline tests passing. Both preserve historical observations separately, require closed evidence before scoring fresh passes, and retain invalid positions in the 60-review denominator. OpenJev also preserves stopped-stage outcomes without assigning completed-pass scores. These commits prepare analysis; they add no model-run results or public-site feeds. The portable reports declare external model hashes without claiming to rehash unavailable model files.

The generated AnyJev, SemIf and OpenJev runners are reviewed and frozen in `cd085d7`, `792ce89` and `6e9fe50`; all 36 generated specialist development phases remain pending. Alex native and OpenJev native fresh runs also remain pending. AnyJev L0 repeat two is live, with 32 of 60 saved rows at this checkpoint; repeat three has not started.

The [calibration implementation plan](ANYJEV_CALIBRATION_IMPLEMENTATION_PLAN_2026-09-28.md) is committed in `3b129ca`. L2 offline protocol, source, runtime and model-file checks pass. Independent review requested changes to its new runner: a durable completion must bind raw responses, the operation journal and review to the historical runner's collection before any successor stage is admitted. The candidate remains unfrozen and has made no model calls. Direct-native L1 remains required and is being prepared separately; cached-score refits do not meet that requirement.

## AnyJev L0 repeat two closed, 2026-09-28

The L0 second development pass exited successfully with all 60 records valid. The closed-evidence report verifies output SHA-256 `d7e0151e86d7dc4570679af91b903308830827ff52b31f27d93c452641c2b3ae` and finds no categorical changes from the historical first pass. Both passes score 4/60 all-field agreement against provisional v0.2 references; per-field agreement is sentiment 37/60, follow-up 13/60, serious concern 34/60 and testimonial potential 44/60. The full three-pass study remains incomplete. A separate repeat-three smoke has been launched under the same frozen manifest; its outcome is not yet established.

Direct-native L1 is reviewed, frozen and pushed in `b96b420`; all eleven offline tests and pinned manifest verification pass. Its three fresh calibration passes remain undispatched. L2 repeat-two manifests are frozen in `2ab6396` with the historical controls preserved; no L2 repeat has been dispatched.

## AnyJev L0 repeat-three admission checkpoint, 2026-09-28 18:24 UTC

The [repeat-two development evidence](../results/repeatability-v1/anyjev-l0-p0-v1/repeat2/P0/development.completion.json) is closed in `fdc7d24`: 60/60 valid, with record SHA-256 `d7e0151e86d7dc4570679af91b903308830827ff52b31f27d93c452641c2b3ae`. The source-bound offline report verifies two of three native L0 P0 passes; the original and repeat two each have 4/60 all-field agreement against provisional references. Repeat three remains separate and unscored.

The [repeat-three smoke](../results/repeatability-v1/anyjev-l0-p0-v1/repeat3/P0/smoke.completion.json) closed with three valid outputs, record SHA-256 `d69dc17ee375b68f90b23f22dea003c44444577885529c9dc59693bbf1a3fcd1`, and [root inspection](../results/repeatability-v1/anyjev-l0-p0-v1/repeat3/P0/smoke-inspection.json) of all twelve distributions. Commit `f1dcefc` preserves that evidence and the separate [development review](../results/repeatability-v1/anyjev-l0-p0-v1/repeat3/P0/development.root-review.json). The development claim and request-started journal are present, but no terminal completion existed at this checkpoint. An interrupted started request must not be replayed or counted as a completed pass.

Direct-native L1 is reviewed and frozen in `b96b420` with three fresh passes planned; its 11 offline tests pass and no stage has run. L2's reviewed controller (`ed62fc5`) and repeat-two offline manifests (`2ab6396`) have no stage receipt or repeat inference. The L1 cached-score study and historical L2 collection remain separate observations. The full requested native and generated specialist scope is unchanged.

## Generated specialist reporting and OpenJev dispatch correction, 2026-09-28

AnyJev generated reporting is committed in `8d5bbf7`; SemIf generated reporting is committed in `08a667a`. Independent review and clean-checkout tests pass (nine and ten tests respectively). These are offline analysis tools, not new model results. Both retain the full P0/P1/P2 repeat matrix, score only closed evidence, keep invalid outcomes in the 60-review denominator, and report case-level prompt changes separately from net score differences. No generated development phases have run.

Subsequent OpenJev review found a [v1 request-serialization defect](OPENJEV_GENERATED_REPEAT_ADMISSION.md) that blocks dispatch before HTTP. The saved manifest sorts payload keys, but execution compares the reloaded payload against an insertion-order wire hash. A versioned correction is being prepared and must pass persisted-manifest tests and independent review before admission. Preserve the original frozen controller and manifest. This supersedes the earlier generated OpenJev approval; it does not remove the eighteen requested development phases from scope.

## OpenJev generated v2 amendment reviewed, 2026-09-28

The [v2 amendment](OPENJEV_GENERATED_V2_AMENDMENT_2026-09-28.md) is independently approved. It preserves all 360 intended v1 request bodies and all experimental controls, validates saved bytes before a claim or server launch, and sends those exact bytes. Four regression tests and pinned-runtime manifest reconstruction pass. The original v1 files remain unchanged. All eighteen development phases still require stage admission and execution; no model calls were made by this correction.

## AnyJev L0 three-pass closure and generated report readiness, 2026-09-28

The [repeat-three development completion](../results/repeatability-v1/anyjev-l0-p0-v1/repeat3/P0/development.completion.json) and [saved records](../results/repeatability-v1/anyjev-l0-p0-v1/repeat3/P0/development.records.jsonl) are closed. The source-bound L0 report verifies three of three native P0 passes, each with 60 valid outputs and 4/60 all-field agreement with provisional v0.2 references. Per-field agreement in each pass is 37/60 sentiment, 13/60 follow-up, 34/60 serious concern and 44/60 testimonial potential. All 60 shared-valid cases keep the same classification across all three passes. The repeat-three record SHA-256 is `893af81312366d1efdbe248c117aa0bed13c617f9b7648e5ee3486f8ab3df4f5`; the source-bound report and findings are published, with deployment and live bytes verified. This completion supersedes the earlier open-development checkpoint without changing it.

AnyJev generated reporting (`8d5bbf7`), SemIf generated reporting (`08a667a`) and OpenJev generated v2 admission/reporting (`de88662`, `85e81e6`) have reviewed offline paths. Their 36 fresh prompt/pass development phases remain pending. OpenJev v1 is preserved as an unexecuted blocked version; v2 preserves its intended request bytes. Alex OpenJev 0.8B fresh-one smoke closed with three valid outputs and an inspected 42-distribution NLI check. Its development pass is running, with zero of three fresh full passes closed; the separate 4B fresh passes have not begun. Alex native, OpenJev native, AnyJev L1/L2 calibration and the other pending specialist work remain in scope.

## AnyJev L0 publication verified, 2026-09-28

Commit `83fb7c4` published the full L0 three-pass evidence and findings. Pages deployment `36472810339` succeeded, including the closed-report check and tests. Live `anyjev-l0-repeats.json`, `index.html` and `repeats.js` matched the committed bytes exactly. The live report SHA-256 is `2bcf22675dadfc1b3e15cec27d68edfcdd4901fbbd405f0e595c2941708f3958`. L0 is complete; the wider specialist and repeat roster remains unfinished. Alex 0.8B fresh-one development continues under its reviewed receipt.


## Alex 0.8B first fresh pass closed, 2026-09-28

Alex OpenJev 0.8B fresh-one native P0 development exited successfully. The frozen controller and the offline report independently verify all 60 saved outputs; record SHA-256 is `f4f5323876adc7f18bbe42b30a64179423af7600505dbba41f8bffcc527314f2`. All outputs are valid; all-four agreement is 3/60. Per-field agreement is sentiment 39/60, follow-up 37/60, serious concern 20/60 and testimonial potential 9/60. The model predicts testimonial yes for 59 reviews, including 49 reference-negative cases. These provisional-reference results describe this native NLI configuration. One completed fresh pass does not establish repeat stability. The historical observation remains separate.

The second fresh pass has a separate admitted smoke test; its full development pass is not yet admitted. The third pass and the 4B series remain pending. The recorded 1,321.63 seconds is the sum of client prediction durations for the first full pass, not isolated inference time; observed local cost is unavailable.

Native L1 reporting passed nine offline tests, independent review and a clean-export test run. L2 reporting passed seven offline tests, independent review and a real saved-evidence build/check. These tools add no inference results: L1 remains 0/3 complete, while L2 has its historical first pass only. L2 third-pass reporting will require an update after its successor plan is frozen. The current L1 report leaves interrupted partial stages unscored without exporting their partial record details.

The published L0 selector was checked in a browser: three 4/60 scores and zero changed classifications are visible. The local `.env` is ignored, untracked and mode 0600; a bounded current tracked-file scan found no confirmed live credential. This is not a claim about arbitrary credential formats or all Git history. Spending caps and remaining scope are unchanged.


## Alex first-pass publication verified, 2026-09-28

Commit `74115d8` publishes the [Alex first-pass findings](ALEX_NATIVE_REPEAT_FINDINGS_2026-09-28.md), README summary and native repeat chart. Pages deployment `36476372868` succeeded. Live `alex-native-repeats.json`, `repeats.js` and `index.html` match the committed bytes; the report SHA-256 is `6160834a1c11625e2b2c612f16d9fc7dd11524960195220eda506158201a2f03`. Browser selection verifies one 3/60 bar, two uncompleted passes and no premature three-pass range. Sixteen focused UI tests and seven reporter tests passed; a clean export reproduced the report and tests. A CLI fixture-root bug was fixed without changing the frozen inference controller.

Alex fresh-two smoke subsequently exited successfully; root inspected its 42 normalized distributions and three projected decisions. Commit `55af739` preserves the smoke, inspection and full-pass admission. Its development pass is running and remains unscored until closed. The 4B fresh series and other remaining native/generated/calibration work remain pending; this publication does not complete the benchmark.


## Alex second fresh pass closed, 2026-09-28

Alex 0.8B fresh-two development exited successfully and passed the frozen controller, output and predecessor checks. Record SHA-256 is `92b8c482f35cbafe9bf17361a3f4a1a1e5d903f1fd8a6f8268aae805912a5ef0`. Both closed fresh passes have 60 valid outputs, 3/60 all-four agreement and identical classifications on all 60 reviews; field matches remain 39/37/20/9. The second pass records 1,251,194 native input-token positions and 1,300.14 seconds of client prediction time; pure inference time and local cost remain unavailable. Third-pass smoke is separately admitted and running. The public chart still reflects the verified first-pass publication until its next refresh.


## Alex 0.8B three-pass closure, 2026-09-28

The third 0.8B development pass exited successfully. Frozen-plan and all three output/completion checks passed; the third record SHA-256 is `6e99d4a97b4f4ad9d18a3e75da4b6c555be6ebb3ae3d9f3caac893a598c11514`. All three passes have 60 valid outputs, 3/60 all-four agreement and identical classifications on all 60 reviews. Field matches are 39/37/20/9 each time. The public report and findings now include all three passes, pending deployment verification. Alex 4B's frozen source/runtime/model hashes were reverified before admitting its separate first smoke. That smoke is running; no 4B fresh full pass is complete.

The seven hosted continuation audits passed independent review and are committed in `527b78e`. A separate offline adapter supports descriptive comparisons by checking saved requests and continuation journals, with seven tests and seven real recomputations passing. Every comparison remains strictly ineligible because the recorded suffix ran outside the original counterbalanced schedule; original smoke/admission gates and historical retry-selection proof are not established by that adapter. Its results must not be merged into the audited-pair category. No new provider requests were made.

## Fresh-series checkpoint, 2026-09-29

See [the dated checkpoint](REPEAT_CHECKPOINT_2026-09-29.md): all six additional Codex first-pass prompt triples are closed (18/54 full runs), and Alex 4B has its first closed native pass. Second passes are underway. Earlier counts above are historical snapshots, not the current completion total.


## Verified execution checkpoint, 2026-09-29: final Qwen evidence

Commit `19d58b8f` preserves the final Qwen 3.6 reasoning-off phases and terminal spending reconciliation. All nine condition/pass combinations now account for their 540 development positions: 538 valid outputs and two retained HTTP 429 failures. The separately admitted continuations sent only never-sent positions; this remains a descriptive series after interruptions, not a clean matched-three experiment. The [final analysis](QWEN36_OFF_REPEAT_FINDINGS_2026-09-29.md) and public report passed their local checks; deployment of this final report is still pending the public-evidence migration.

DeepSeek low has one closed full pass (59 valid outputs, 58/60 all-field matches) and a closed P1 smoke. Its selected endpoint became unavailable before P1 development dispatch; eight full combinations remain unfinished. See the [DeepSeek low findings](DEEPSEEK_LOW_FRESH_REPEAT_FINDINGS_2026-09-29.md). AnyJev L1 first-pass development is running through its native calibration interface; no full L1 pass is yet claimed complete. The remaining native and hosted roster remains in scope.

The privacy migration has hash-verified private backups of all 28 audited provider-error originals. They remain locally intact and tracked until the clean-export Pages checks pass. Sanitized public copies and their explicit private-hash attestations are prepared; historical Git exposure is not removed by current-tree cleanup. See the [privacy audit](PUBLIC_EVIDENCE_PRIVACY_AUDIT_2026-09-29.md). No new spending authority or scope exclusion is implied by this checkpoint.


## Public evidence release prepared, 2026-09-29

All 53 Pages static checks passed against a public-only checkout, including the corrected fixture tests. The 28 audited originals are now untracked and ignored, with local bytes and private backups hash-verified. Active explorer/findings feeds use sanitized evidence links; final Qwen results and analysis are included. Historical Git exposure remains outside this current-tree cleanup. Deployment verification is pending. The remaining hosted matrix is in [the dated audit](HOSTED_PENDING_MATRIX_2026-09-29.md); the $10 aggregate cap is unchanged and the requested increase is unanswered.


## Public release verified, 2026-09-29

Pages run [36513456196](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36513456196) succeeded at commit `4084a388`. Seven live assets matched committed bytes by SHA-256: `app.js`, `findings.js`, `repeats.js`, `index.html`, the sanitized explorer and findings data, and the final Qwen second-interruption report. This supersedes the pending-deployment status above. All nine Qwen combinations and their limitations are now public.

Gemma 26B reasoning-on has a distinct fresh-three offline candidate under review, with a proposed $0.40 child allocation and no inference or allocation performed. Historical known-charge proxy is $0.19825584 for the full new series; a sensitivity including historical unknown-charge bounds is $0.31671216. These are estimates, not guarantees. Its raw provider attempts/responses are ignored; publication will require a sanitized projection. Execution lifecycle tests and stricter predecessor checks are being completed before dispatch. The requested aggregate cap increase remains unanswered; the $10 cap still applies. AnyJev L1 development remains in progress.


## AnyJev L1 first full pass verified, 2026-09-29

First-pass development exited successfully and passed frozen controller verification, with completion SHA-256 `776c1e513f017a125fe05fb547f852986ba3074c033d18d748232ee34f062f4a`. All 60 held-out outputs are valid; all-field agreement is 6/60 and field counts are sentiment 38, follow-up 16, serious concern 31 and testimonial 49. Closed evidence was pushed in `ce2913e4`. A narrow reporter artifact-identity fix passed eleven tests and independent review; the [first-pass findings](ANYJEV_L1_REPEAT_FINDINGS_2026-09-29.md) are prepared for publication. Fresh2 smoke/calibration is separately admitted and running. No full second pass is yet complete, and no inference protocol or result was changed by the reporter correction.


## AnyJev L1 publication verified, 2026-09-29

Pages run [36516409907](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36516409907) succeeded at `e6e33ea4`. The live L1 report and index match committed bytes. Browser selection shows one completed native pass at 6/60, two incomplete passes, and no premature repeat range. Eleven reporter tests, three UI tests and an independent clean-export check passed. Shared Ruflo retrieval and save-back were verified from fresh launcher connections and both canonical stores. Fresh2 smoke/calibration remains live; no second full pass is complete.

DeepSeek low became reachable again, but the exact endpoint input price changed from $0.10 to $0.03 per million tokens. The frozen price check rejected it before any inference or reservation. A price-only successor admission is being assessed; the original series and controls remain intact.


## Funded DeepSeek continuation and second L1 development, 2026-09-29

Commit `0119258a` preserves the independently reviewed price-only DeepSeek successor. Nine tests passed, including the original request loop with simulated transport and a real temporary budget ledger. The separate phase-02 development amendment receipt binds the new wrapper while retaining the original runner, manifest, request hashes, route and $0.1069056 reservation. The funded P1 development stage is running; it is not a completed result. Commit `ca7dc155` adds offline publication verification for the supplemental evidence, with six tests and independent review passing.

AnyJev L1 fresh2 smoke completed with three valid outputs and twelve normalized choice distributions. Its verified completion hash is `ddd630057c98a98b55924cf1ed9af2f85d4988064f34f001c6dc60370920486e`. Root inspection retained near-tied and insufficient-information choices without repair. Commit `dd795598` preserves the closed smoke and separate development receipt; the remaining 57 held-out records are now running. L1 remains at one completed full pass out of three.

The Qwen reasoning-on admission plans are independently reviewed and committed in `5d0a1c44`. They remain unexecuted and unfunded; a future controller must bind the planner and test hashes before dispatch. The aggregate cap remains $10.


## Hosted execution preparation verified, 2026-09-29

Commit `9288d268` adds the reviewed Qwen27 executor and corrects Gemma response capture. Bounded raw response bytes are durably saved before JSON parsing; malformed responses retain their unknown-charge reservation and cannot be replayed. All 25 combined tests pass. Both independent reviews approve after the Gemma raw-wire ignore rule was verified across all 18 stage paths. These are offline preparations, not new benchmark results or funding approvals.

The [hosted work matrix](HOSTED_PENDING_MATRIX_2026-09-29.md) now puts the latest verified preparation status before the preserved historical snapshot. DeepSeek low P1 and AnyJev L1 second-pass development remain active at this checkpoint. The remaining hosted allocations are unfunded. Shared Ruflo retrieval and exact save-back were verified through a fresh second launcher and both canonical databases for this commit.


## DeepSeek P1 publication verified, 2026-09-29

DeepSeek low P1 closed with 60 valid outputs, 57/60 all-field agreement and 59/60 agreement on each field. The original verifier and immutable settlement-prefix check passed; closed evidence is committed in `37c21495`. Publication commit `cc7bc217` passed a public-only report check, six reporter tests and three UI tests. Pages run [36521916906](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36521916906) succeeded, and the live report matches committed bytes. Its seven unclosed combinations remain unscored.

P2 smoke subsequently closed with three inspected valid responses and known billing; P2 development is running within the existing funded child. AnyJev L1 fresh2 remains active, with fresh3 still required before L2 is next. Qwen reasoning-on and DeepSeek high executors are reviewed and committed; the Mistral none/high offline plans are also reviewed and committed. Their new hosted allocations remain unfunded. See the updated [hosted matrix](HOSTED_PENDING_MATRIX_2026-09-29.md).


## AnyJev L1 second pass published, 2026-09-29

Fresh2 development exited successfully and passed the pinned stage verifier with completion hash `4193f1f322d190cc5ad14f45e783467e9f4a046d18b3ef303c10a038f7dcbd91`. Both completed passes have 60 valid outputs, 6/60 all-field agreement and field agreement counts of 38, 16, 31 and 49. No label vectors changed across the 60 paired reviews. This observed two-run consistency does not prove determinism or accuracy.

Closed evidence and the separate fresh3 smoke admission are committed in `49ab5ba2`. The third pass is calibrating; no third full pass is complete. Publication commit `a6248dd6` passed a public-only report check, eleven reporter tests and three UI tests. Pages run [36523880485](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36523880485) succeeded; the live report exactly matches SHA-256 `21af925625968960a6e3e7f070e95f175630f147f19dde89b5ff7f32ef85edc8`.

Mistral's executor is also reviewed and committed in `9c417ca2`, with eleven planner/executor tests passing. No new Mistral request or allocation has occurred. Its historical 429 capacity failures and unfunded status remain unresolved. The requested budget increase has not been approved; the $10 aggregate cap remains in force.


## Generated specialist completion and next local pass, 30 September 2026

AnyJev generated P0/P1/P2 has nine independently verified full phases. P0 and P1 each returned 60 invalid fenced responses in every pass. P2 returned the same 30 valid classifications in all three passes, with 1/60 all-field agreement and 0/30 shared-valid classification changes. Final findings are live in [Pages run 36774662260](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36774662260), commit `a6900d3b`; live assets match committed bytes. Native AnyJev results remain separate.

Gemma E2B thinking-on first P0 closed with 60 valid responses. Its P1 smoke passed root inspection and P1 development is running; evidence commit `d0c76e1a` contains only the closed P0 full pass and P1 smoke. Publication of this new local result is pending. Ten exact generic-local configurations remain unfinished, including this one. Hosted funding, direct-provider access and reference adjudication remain unresolved; no spending cap or scope exclusion changed.
