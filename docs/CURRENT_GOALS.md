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
