# Current work checklist

## Current checkpoint, 6 October 2026: hosted work after reconciliation

- Qwen thinking-on final fresh3/P1 finished with 60 valid responses. The [final audit](../results/repeatability-v1/qwen36-on-hosted-authority-v3-v2/remaining-hosted-v1/fresh3-p1-final-closure-audit.json) and sealed-child reconciliation are archived. The series has eight clean full phases and one interrupted descriptive phase; do not call it nine clean passes.
- DeepSeek low fresh2/P2 continuation finished DEV-006–060 with 55 valid responses. Together with the earlier four valid responses and DEV-005's unknown outcome, the descriptive composite has 59 valid responses out of 60. The [closure audit](../results/repeatability-v1/deepseek-low-remaining6-price-v2/unsent-continuation-v1/fresh2-p2-suffix-closure-audit.json) preserves that distinction. Its child is sealed. Agent gemini_recovery owns a separate v4 adapter for the five remaining full phases; no completed request may be replayed.
- DeepSeek high's exact-unsent v4 continuation passed independent review and 11 tests. Agent qwen_recovery owns the active DEV-028–060 development continuation on original handle 8123, after root inspected the successful DEV-028–030 smoke. DEV-001–027 stay preserved, including DEV-027's unknown outcome. Five full phases follow only through their declared gates.
- Liquid d1's [three-review native smoke](../results/liquid-d1-native-v1/smoke.closure-audit.json) passed and its allocation is reconciled. Agent deepseek_recovery owns the full native-decision executor and offline tests. Full execution still needs independent review and admission.
- Root verified and applied the [v4 release receipts](../results/authority-release-v4-20261006/). All 12 prior OpenRouter-only children were sealed first. Only unused reservations were released; actual charges and unknown-charge bounds remain accounted for. Old v3 execution must not restart.
- Pages deployment [37511309931](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37511309931) succeeded for f6d4c53d. Root verified exact live bytes for the hosted feed, combined analysis, analysis JavaScript and repeat JavaScript against that commit. The final Qwen P1 feed and combined analysis were pushed in a618022f, including its 57/60 result. The next analysis update adds label changes on 5/60 baseline reviews and 7/60 decision-rule reviews across three clean passes, plus 6/60 classifier-instruction reviews across two clean passes. Independent review approved it; 16 Python and nine UI tests passed. DeepSeek low continuation still needs report integration.
- Cloudflare funding, rate-limited Mistral work, remaining specialist coverage, and final roster/analysis reconciliation remain open. No new local inference was started. Historical dated entries below describe earlier checkpoints, not current running processes.

## Public report browser checks, 6 October 2026

Root checked the published report at a 390 × 844 viewport: no horizontal page overflow, the six main navigation links were present, selecting the hosted Qwen repeat study worked, and Tab from the model selector focused the study-details summary. No console errors were reported in this bounded check. The normal viewport was restored. This is not full mobile, keyboard or reduced-motion coverage; those remaining checks stay open. The rendered report still reflected the last deployed cohort while the newer Qwen closure deployment was in progress.

## Third Qwen pass and DeepSeek low launched, 6 October 2026

- Qwen fresh2/P0 is closed and pushed in `0c2dfa9a`: 60 valid answers, 53/60 all-four matches. Second-pass P0/P1/P2 scores are 53/54/56. Pages run 37504246044 succeeded; root verified exact live hosted-report and combined-analysis bytes against `0c2dfa9a`. Root inspected fresh3/P2 smoke (original 67883, terminal success) and launched full development on original 40515.
- DeepSeek low remaining-six smoke (original 47187) completed with three inspected valid raw answers. Full fresh2/P2 original 57830 stopped after five attempts: DEV-005 returned HTTP 429 with unknown cost; DEV-006–060 were never sent. The first four responses and full unknown reservation remain preserved. The agent owns interruption audit; no retry or continuation dispatch is admitted. Its source-bound adapter is archived in `8f124bb5`; isolated review-state tests in `fc319ee7` pass. The frozen pre-admission test retains a known live-state assumption and is not in Pages CI; broad pytest is not claimed green.
- DeepSeek high fresh1/P2 remains on original 55857. Root owns execution. The report agents own closed-only projection preparation; the authority agent owns offline release preparation. No active ledger may be staged or released.

## Hosted execution resumed, 6 October 2026, 17:21 UTC

- Root inspected DeepSeek high remaining-seven fresh1/P2 smoke: three valid raw JSON answers with normal stops. Original smoke handle 93637 exited successfully; full development is admitted on original handle 55857, with no completion credit yet. The separately priced configuration and reviewed adapter are archived and pushed in `75001769`; its $1 child comes from the OpenRouter-only allowance.
- Qwen hosted fresh2/P0 is independently closed: 60 valid strict outputs, 53/60 all-four matches and $0.0687864 known development cost. Its immutable child snapshot has 252 matched reserves and settlements and $0.2803957 cumulative known cost. The original handle 61377 exited; no request was replayed. Fresh2/P0/P1/P2 now score 53/54/56, giving matched differences of +1 for classifier instructions and +3 for decision rules against P0 on these 60 reviews. Fresh3/P2 is next in the declared order; root owns admission. The preceding `9eeea0a3` publication is verified: [Pages run 37502397634](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37502397634) succeeded, and root matched the live hosted and combined JSON bytes.
- `gemini_recovery` owns a read-only audit of retained shared-authority holds for Clef. `deepseek_recovery` owns preparation of the remaining low-effort hosted proposal. Neither may allocate or dispatch; root owns admission. No local inference is running.

## Recovery after unexpected shutdown, 6 October 2026

- Hosted Qwen thinking-on has five independently closed clean phases: fresh1/P0 (54/60), [fresh1/P2](../results/repeatability-v1/qwen36-on-hosted-authority-v3-v2/remaining-hosted-v1/openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2/fresh1/P2/closure.review.json) (56/60), and fresh2/[P0](../results/repeatability-v1/qwen36-on-hosted-authority-v3-v2/remaining-hosted-v1/openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2/fresh2/P0/closure.review.json), [P1](../results/repeatability-v1/qwen36-on-hosted-authority-v3-v2/remaining-hosted-v1/openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2/fresh2/P1/closure.review.json), [P2](../results/repeatability-v1/qwen36-on-hosted-authority-v3-v2/remaining-hosted-v1/openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2/fresh2/P2/closure.review.json) (53/54/56). Fresh1/P1 remains a separate interrupted descriptive composite with DEV-049 unknown. All fresh3 phases remain unclosed. The [hosted report](../public-site/additional-hosted-fresh-repeats.json) and [combined analysis](../public-site/analysis-refresh.json) include only closed evidence; this latest report refresh still needs publication verification.
- [DeepSeek high fresh1/P0](../results/repeatability-v1/deepseek-high-authority-v3/fresh1/P0/closure.root-review.json) is closed with 59 valid, one intrinsic invalid and 57/60 matches. [Fresh1/P1](../results/repeatability-v1/deepseek-high-authority-v3/fresh1/P1/closure.root-review.json) is closed and archived in `55641d6f`: 59 valid, DEV-006 retained as an intrinsic length-invalid output, 57/60 all-four matches and $0.031765648225 known development cost. Fresh1/P2 is blocked before claim by live pricing changes: cache-read first fell, then prompt pricing rose above the frozen ceiling. A separate remaining-phase proposal with explicit fixed price ceilings is being prepared. No P2 request or completion is credited. Mistral Small 4 high has two distinct stopped first smokes: [`mistral/zdr`](MISTRAL119_HIGH_HOSTED_AUTHORITY_V3_ADMISSION.md) and [plain `mistral`](MISTRAL119_HIGH_PLAIN_AUTHORITY_V1_ADMISSION.md) each attempted only DEV-001 and received HTTP 429 `upstream_provider_shared_pool`. Each child was separately reconciled with its full $0.04177920 unknown-cost upper bound retained and $0.70822080 unused allocation released; DEV-002–003 were never sent in either smoke. Both configurations remain 0/9. No claim may be replayed and no further tag probe is admitted by these results.
- Gemini 3.1 Pro Preview high has [9/9 verified phases](../public-site/gemini-repeats.json), with the [combined analysis](../public-site/analysis-refresh.json) updated; root verified the current live JSON bytes. This completes that declared Gemini series, while the wider roster and repeat matrix remain unfinished. Root owns new admissions, terminal reconciliation and publication.

Earlier bullets in this section are dated checkpoints; their running handles and pending-publication statements are historical.

- Gemini high series is complete and independently verified at 9/9: P0 scores 55/56/56, P1 56/56/56, P2 55/56/56. The six newly executed full passes plus smokes cost $1.636000. Root reconciled the child with no unknown costs; $0.364 unused allocation was released in the master. The separate authority hold remains conservative. Historical closure ledger hashes are preserved as exact immutable prefix snapshots.
- DeepSeek high P0 original 49284 exited successfully after all 60 attempts (59 valid, one intrinsic invalid). Root found a closure-verifier adapter bug involving path/argument compatibility and lower live pricing; completed requests remain preserved. A separate verifier repair is required before P1 admission. Preliminary offline score is 57/60 and known cost $0.034324790897, pending full closure audit.
- Pages run 37493723371 succeeded for the seven-condition report; newer eight-condition run 37494161989 is in progress. Nine-condition report and combined findings are prepared for the next publication.

- Latest: Gemini repeat3/P0 is verified (60 valid, 56/60, $0.228962 development). Repeat3/P1 is now running on handle 11129 after its inspected smoke; this is the last condition in that series. DeepSeek high P0 remains running on 49284.
- Qwen suffix is independently closed and reconciled in `7f4ae647`: 11 valid, 9 all-four matches, $0.0134064. Full interrupted P1 is descriptive: 59 valid, one preserved unknown, 52/60 matches, $0.0696082 known development charges plus $0.0299008 unknown upper bound. No P1 positions remain unsent. Further Qwen phases need separate admission after parent closure.
- Pages attempt 37493274075 failed because the immutable Gemini allocation manifest was absent from Git. Fix `9c9a774e` includes it; an isolated 990-file report verification passed. Replacement Pages run 37493723371 remains pending verification. The report currently includes seven closed Gemini conditions; the newer P0 closure and final P1 result need the next report refresh.

- Hosted execution has resumed concurrently: Gemini repeat3/P0 (handle 63965), DeepSeek high fresh1/P0 (49284), and Qwen P1 DEV-050–060 continuation (56685). Gemini repeat3/P2 is closed and independently verified: 60 valid, 56/60 matches, $0.264350 development charges. Root owns closure and next admissions.
- Qwen parent accounting is reconciled: $0.1300116 known charges across its completed stages and $0.0299008 retained unknown bound. The suffix has a separate $0.3289088 maximum allocation; its output will remain an interrupted descriptive composite.
- Gemini public-feed integration now has seven independently verified conditions out of nine, preserving the original eight series. Tests pass; publication verification is pending. Shared Ruflo sentinel retrieval and recovery checkpoint save-back are verified in both canonical stores.

- Root verified the $22.38 OpenRouter amendment and both authority pools. Existing reservations remain counted; the additional $10 was not applied again. No matching benchmark process survived the shutdown, and no local inference was restarted.
- Gemini repeat2/P1 and P2 closed evidence is pushed in `9b4440e2`. P0 is now independently verified: six batches, 60 valid records, 56/60 all-four matches and $0.294926 development charges. Repeat3/P2 passed its three-review smoke and raw inspection; its full hosted pass is running on original handle 63970.
- `qwen_recovery` owns the separate continuation for P1 DEV-050–060 only. DEV-049 remains an unknown timed-out request with its $0.0299008 bound retained. Root owns ledger reconciliation and dispatch after review.
- DeepSeek high lower-price admission is reviewed and committed in `f1a3793a`; 32 tests and seven subtests passed. Root allocated the $0.90 child, inspected three valid smoke responses, and launched the first P0 full hosted pass on original handle 49284. `deepseek_recovery` is now checking the public-report integration needed for new closed runs.
- Root verified 13 Gemini authority and budget-amendment tests. Root owns the next hosted dispatches and publication reconciliation. No completed request is queued again.

## Hosted runs and publication verified, 6 October 2026

- Pages run [37485975020](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37485975020) succeeded for `0816f09f`. Live analysis-refresh.json, deepseek-low-final-suffix-findings.json, legacy-qwen-repeats.json, repeats.js and analysis-refresh.js match committed bytes. Browser checks show 58/57/53 DeepSeek scores, 56 valid P2 answers, retained failures, and the known-cost/token denominators.
- Gemini high repeat2/P1 is independently verified: six batches, 60 valid records, $0.248738. Hosted Qwen3.6 thinking-on fresh1/P0 is independently verified: 60 valid records, $0.0673437. Both passed request/raw/strict prediction and settlement checks.
- Gemini repeat2/P2 and Qwen fresh1/P1 each passed a new three-review smoke. Gemini P2 full process 3895 is root-verified: 60 valid, 56/60 all-four matches, $0.266594; six exact request/raw bindings and reserve/settle pairs passed. gemini_closure_checkpoint owns P1/P2 source-bound closure receipts. Gemini repeat2/P0 smoke is running on handle 31363. Qwen P1 full process 92924 stopped: DEV-001–048 are valid, DEV-049 has TimeoutError with no captured response or confirmed HTTP status, and DEV-050–060 remain unsent. Its $0.0299008 unresolved reservation remains counted. hosted_closed_audit owns a new never-sent suffix proposal; root has not finalized the parent ledger. Root owns subsequent admissions.
- The new DeepSeek high adapter passed 26 tests and seven subtests, including actual amended-ledger admission. Root live route verification refused a changed endpoint field before allocation; the exact difference is under inspection. No DeepSeek high inference or allocation is admitted. Its existing executor rejects current price and budget controls; frozen history stays unchanged.
- No local inference was started. The broader roster, later repeats and final analysis remain incomplete.

## Latest execution and publication checkpoint, 6 October 2026

- OpenRouter-first routing and the additional $10 are activated in AGENTS.md, APP_GOAL.md and the versioned ledgers. Cumulative OpenRouter ceiling: $22.38. The same grant is counted once across overlapping authority.
- Gemini high repeat2/P1 and hosted Qwen3.6 thinking-on fresh1/P0 processes have exited successfully. `hosted_closed_audit` owns independent counts, hashes, strict-output and cost verification. Root owns subsequent smoke inspection and dispatch. Do not restart either completed command.
- Local Qwen3.5 4B fresh2/P0 is closed, verified and archived in `abad20dd`: 52 valid, eight invalid, 48/60 all-four matches, 3/9 full phases closed. Its model is unloaded; no further local phase starts pending battery preference.
- DeepSeek final ten reviews are closed and verified in `a002196e`. The full P2 descriptive score is 53/60; invalid and failed historical responses remain. Root owns the prepared report, combined analysis, tests and publication. These website changes are not yet published.

Earlier entries below are dated history, not current running-process instructions.

## Additional OpenRouter funding, 6 October 2026

- DeepSeek original handle 26250 exited zero. DEV-051–060 are all valid and all ten match all four references; cost $0.004464008007, 25,205 input and 3,125 output tokens. Root verified request/raw bindings and strict predictions, sealed/reconciled the child, and archived closed evidence in a002196e. Full P2 composite remains 56 valid, one invalid and three prior failed outcomes; analysis/publication are pending. The overlapping authority still conservatively holds the initial reservation.

- DeepSeek DEV-051–060 continuation is now live on original handle 26250 using OpenRouter, after root review, the fresh live gate and a $0.630784 conservative child reservation. Price-ceiling successor 9f47ecac preserves all ten requests; no completed review is replayed. Root owns terminal reconciliation and publication.
- Parallel preparation: gemini_high_hosted_prepare owns Gemini 3.1 Pro Preview high repeat2/3; qwen_host_successor_review owns Qwen3.6 35B A3B thinking-on hosted fresh-series admission. Neither preparation has permission to allocate or dispatch; root owns admission. Read-only audit confirmed Gemini 3.7 Flash high already has all six repeat phases, so it is not queued again.

- Root approved and committed the DeepSeek authority bridge in f88b42f5. Live admission found one changed field: input price decreased from $0.055/M to $0.021421/M; model, provider, reasoning and reserve were unchanged. No allocation or inference occurred. qwen_host_successor_review owns a successor that accepts prices within the unchanged ceiling and records the live rate. next_hosted_admission_audit owns read-only prioritization of the next independent hosted configurations.

- User authorized an additional $10. Root owns versioned activation of the $22.38 OpenRouter cap and the same $10 once in overlapping authority, earmarked for OpenRouter. The pending $0.55 proposal is superseded, not added. No other provider receives new authority.
- qwen_host_successor_review owns the offline budget amendment implementation and the separate DeepSeek bridge required by its frozen $12.38 checks. DeepSeek's price continuation is reviewed and committed in 9069c285. Root verified that the account top-up is available; The reviewed ledger amendment is activated and pushed in f67403df (10 tests passed); dispatch awaits the separate bridge review and a fresh exact-route check. The bridge must retain historical cap checks against the frozen original ledger prefix while spending against the full current ledger.
- OpenRouter is the default where model identity and required interface are available. Quantization/runtime differences are separate configurations, not reasons to keep work local. Current catalogue lacks Qwen3.5 4B and Gemma E4B; larger Qwen sizes are not substitutes. The current local pass is preserved; no additional local pass starts pending the battery preference.

## Battery and hosted continuation, 6 October 2026

- Qwen fresh2/P0 remains on its original live handle 4810. The user raised battery drain; no further local pass will start until they answer whether to continue local execution. Preserve the running pass and all saved responses.
- The user reaffirmed OpenRouter usage and reported $0.47 remaining account credit. DeepSeek's ten-request conservative reservation is $0.630784. No new paid allocation or request has been sent. The new price/authority adapter is prepared with 21 offline tests passing and is under independent review; root owns admission after account capacity and spending authority are reconciled.
- The repeat selector accessibility update is published: Pages 37473696141 succeeded for 85663666, and root verified exact live repeats.js bytes. Qwen admission transition tests are committed and pushed in c7f5f554; only isolated fixtures changed.

## Current checkpoint, 6 October 2026

- Publication is verified: Pages run [37469516388](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37469516388) succeeded for `a8640dc0`. Live `e4b-interruption-findings.json`, `repeats.js` and `analysis-refresh.json` match the committed files byte for byte.
- Jev P0 and P1 each have three full passes. P0 scores 54/53/52 and P1 scores 54/53/54. P2 fresh1 and fresh3 each have 60 valid responses and 54/60 matches; the interrupted middle composite has 57 valid, one invalid, two unknown and 50/60 matches. It has no clean-pass credit.
- E4B thinking-on fresh2/P2 accounts for all 60 positions: 58 valid, two earlier unknown, zero unsent and 48/60 descriptive all-four matches. The eight-review suffix is valid 8/8, with 7/8 matches. This remains an interrupted composite outside clean repeat coverage.
- Qwen3.5 thinking-on has 2/9 clean phases. Its later P2 smoke produced an invalid output; its P1 smoke stopped during host sleep with DEV-003 unknown. The independently reviewed successor completed the fresh2/P0 smoke with three valid answers. Root inspected raw responses; the full development pass is running on handle 4810. Root owns closure and reporting.
- DeepSeek's exact `open-inference/fp4` route exists, but current pricing exceeds the frozen ceiling. The ten-request conservative reserve is `$0.630784`, against `$0.083836340` free in the separate authority. Admission refused before inference; no cap changed. See the [route audit](../results/route-audits/deepseek-route-recheck-20261006-1320/audit.json).

The dated entries below record earlier checkpoints and ownership. Their running, pending-publication and route-availability statements are historical, not current instructions.

## E4B suffix closed, 6 October 2026

- Original handle 46546 exited zero. All eight never-sent reviews returned valid answers; 7/8 matched all four frozen references. Root checked hashes and strict predictions. Host stayed awake on battery with no sleep transition. The interrupted full pass now has 58 valid and two earlier unknown outcomes; it remains descriptive.
- Closed evidence is archived separately. E4B report integration is pending; no inference is running. Jev third-pass report integration and Pages verification remain underway.

## Portable publication and E4B continuation, 6 October 2026

- Root verified the Jev archived-path fix in a clean checkout: combined report check and 15 Jev reporter tests passed. Fix 048f7753 is pushed; Pages was manually dispatched. Publication is not yet verified.
- E4B fresh2/P2 never-sent DEV-053–060 is running on original handle 46546. Seven offline tests and all 60 live render/token checks passed; exact hosted E4B was absent from a fresh 464-model OpenRouter catalogue. Loaded Gemma4 E4B Q4_K_M at context8192, instance rPBkF4BjfjDl6SDDWo3j0Xwl; battery92%, lid open, sleep counter94. Earlier unknown DEV-039/052 remain unchanged.
- authority_reconciliation_v2 owns Jev P2 fresh3 report/renderer integration. Root owns combined feed, publication and local closure.

## Jev P2 third pass closed, 6 October 2026

- Original handle 88263 exited successfully: 60 valid responses, 54/60 all-four matches, $0.006851040 observed cost. Root verified all request/raw-response hashes and strict predictions, reconciled the child, and released only $0.073788960 unused authority. No inference is running.
- P0/P1/P2 each have three declared attempts; P2 fresh2 remains interrupted (57 valid, one invalid, two unknown). This does not make the requested clean repeat study complete.
- Pages run 37465810307 failed before deployment because the Jev report verifier compared archived absolute paths across checkouts. authority_reconciliation_v2 owns the portable archived-verifier fix and regression test. The live site retains the previous version. Third-pass report integration remains pending.

## Report reconciliation, 6 October 2026

- Root rebuilt the Jev and Qwen feeds, including all three Jev P0/P1 passes and the interrupted P2 composite. Combined analysis now checks those values against the raw-evidence report. Publication is pending verification.
- Jev P2 fresh3 passed independent review and is running on original handle 88263 under a separate $0.080640 reservation. Root verified the exact route, frozen inputs, predecessor, context and budget before dispatch. The published-report cutoff below excludes this live pass.
- Qwen checks preserve the invalid P2 smoke and sleep-interrupted P1 smoke as separate outcomes; neither counts as a development pass.
- Three unused Kev P1 reservations were released through the unchanged verifier. Known charges remain counted; no spending cap changed.

## Jev P0/P1 three-pass execution, 06 October 2026, 12:31 UTC

- P0 now has three terminal full passes: 60/60/59 valid responses. The third retains DEV-040 as an invalid probability distribution. Each pass has $0.005890920 observed cost. Root verified all raw/request bindings and reconciled all children. The third pass's authority hold remains encumbered because the frozen release verifier requires all-valid outcomes; no output was repaired.
- P1 has three terminal full passes: 60/59/60 valid, each $0.006405000 observed cost. P2 fresh2 accounts for all 60 positions as an interrupted composite, but P2 fresh3 remains unsent. authority_reconciliation_v2 owns a separate predecessor wrapper for that third pass, without changing frozen runner code.
- No inference is running. jev_authority_v2_bridge owns the expanded native P0/P1/P2 report and renderer; jev_v2_activation_review owns Qwen combined-analysis compatibility. Root owns publication and the next reviewed admission. Existing private active ledgers are not staged.


## Jev P1 repeat closure and P0 admission, 06 October 2026, 12:27 UTC

- P1 fresh3 finished with 60 valid responses, zero invalid and $0.006405000 observed cost. Root checked all 60 request and response hashes and strict parsed decisions, then reconciled the child. P1 now has three full passes with 60/59/60 valid responses. Updated scores and repeat comparisons are being calculated by jev_authority_v2_bridge.
- Root released the reviewed P1 fresh1 unused reservation and the source-verified P1 fresh3 unused reservation, each $0.074235, using the unchanged authority-v2 verifier. Known charges remain counted. P1 fresh2 and the interrupted P2 tail remain encumbered under that verifier.
- Jev P0 fresh1 is now live on handle 19352. Its historical three-record native smoke was re-inspected, all 60 request/context bindings verified, exact route checked and a root receipt/child allocation admitted. It retains original model controls, label-free requests and strict offline scoring. No other inference is running.


## Interrupted execution, 06 October 2026, 12:17 UTC

- Both live handles are terminal. Qwen fresh2/P1 smoke saved two valid answers; DEV-003 timed out after a recorded host sleep. Host audit failed as expected; no full pass is admitted and no unknown request was replayed. qwen35_successor_report owns offline reporting of the terminal evidence.
- Jev P2 continuation attempted all 42 previously unsent reviews. It saved 40 valid responses, one invalid response on DEV-040, then DEV-060 timed out. Root verified all request/raw hashes, retained the full $0.001344 unknown-charge bound, and reconciled the child. Known continuation cost is $0.004681740. Combined with the parent: 57 valid, one invalid and two unknown positions across 60; no never-sent reviews remain. This is an interrupted composite, not a clean repeat. jev_authority_v2_bridge owns report integration.
- No inference is running. authority_reconciliation_v2 is preparing the next known-cost P1 fresh1 reserve release; the invalid-output P1 fresh2 release is unsupported by the frozen v2 verifier and remains encumbered. Future paid admission remains root-owned.


## Publication and admission checks, 06 October 2026, 11:47 UTC

- Qwen publication is verified: Pages 37457799533 succeeded for `d54ab26a`. Live legacy-Qwen and combined-analysis feeds match that commit exactly and report 2/9 closed Qwen3.5 phases.
- Jev tail admission stopped before allocation because its proposed partition name contained uppercase characters rejected by the real allocator. Root verified no child, receipt or stage exists; authority and master heads are unchanged. jev_authority_v2_bridge is fixing the name and adding a real-allocation regression test. No request was sent.
- Independent Qwen continuation review found a blocking host-audit schema mismatch between smoke completion and development admission. qwen35_successor_report is fixing it with a transition test. jev_v2_activation_review owns independent re-review of both fixes.

## Jev v2 activation, 6 October 2026, 11:44 UTC

- Independent activation review: APPROVE, no confirmed blocking or residual findings; 40 focused and related offline tests passed. The reviewed implementation is committed in `3adc27d6`.
- Root activated exactly one source-bound unused-reservation release of $0.073788960 and verified its durable receipt. Shared-authority accounted amount is now $9.874582064, leaving $0.125417936 under the unchanged $10 cap. OpenRouter aggregate authority remains $12.38. Known charges and unknown-charge bounds remain reserved. No new child allocation or inference has occurred yet.
- Root owns fresh exact-route admission of the 42 never-sent Jev P2 reviews. Legacy hold-only writers now fail closed on the versioned release event; future paid work must use a reviewed v2-aware bridge.
- Qwen post-smoke continuation is offline-prepared; jev_v2_activation_review is reviewing it independently. The failed fresh2/P2 gate is preserved, with no development credit or replay.

## Active checkpoint, 6 October 2026, 11:40 UTC

- Qwen3.5: fresh1/P1 is closed and raw-verified, with 51 valid responses, nine invalid and 47/60 all-four matches. P1/P2 findings and both feeds now show 2/9 clean phases; pushed in `d54ab26a`; Pages job 37457799533 is running. The fresh2/P2 smoke is terminal: three saved, DEV-001 invalid after exhausting 4,096 output tokens, no full-pass dispatch. No model inference is currently running. qwen35_successor_report is preparing a separate controller to continue other scheduled phases without replaying this smoke or concealing the failed gate.
- Jev publication: Pages 37456158933 succeeded. Live HTML, renderer, Jev feed and combined-analysis feed match deployment bbf00d95 byte for byte. The panel was inspected on desktop and at 390px width; its cost disclosure opened by keyboard. No new reduced-motion emulation was performed.
- Paid execution: the reviewed authority-v2 accounting module is committed in 80a13242. jev_authority_v2_bridge owns its full/tail runner integration; authority_reconciliation_v2 owns durable release-receipt activation. The implementations passed root offline tests (five release-controller tests and seven bridge tests); jev_v2_activation_review owns independent review. No production release, new allocation, cap increase or paid inference has occurred. Root reviews and admits only after the implementations and fresh budget checks pass.
- Wider roster, reference controls and remaining repeats remain in scope. Earlier dated running-handle and balance statements below are historical.


## Active checkpoint, 06 October 2026, 11:26 UTC

- Jev: public prompt/repeat panel and combined analysis are pushed in `bbf00d95`. Pages 37456158933 is running; publication is not yet verified. Clean staged reconstruction passed 20 Python and 19 JavaScript tests, including relocated archived receipts, child-ledger and unknown-evidence tampering. Both first passes score 54/60; P1 fresh2 retains 59 valid/53 matches and P2 fresh2 remains stopped with 17 valid, one HTTP 429 and 42 unsent.
- Reservation reconciliation: the read-only 47-hold audit is committed in `28813b7d`. authority_reconciliation_v2 (Sol high) owns offline v2 accounting implementation and tests; authority_v2_review (Sol high) owns independent money/concurrency review. No production release, authority amendment or new paid inference is admitted. Verified unused reservations may avoid the pending cap increase; do not treat historical holds as observed charges.
- Root: Qwen3.5 fresh1/P1 remains live on handle 92736. On terminal completion, verify all raw/source hashes and post-run host audit, archive only closed evidence, then prepare the scheduled fresh2/P2 smoke. Never replay an already attempted position.

## Publication verified and authority audit, 6 October 2026, 11:08 UTC

- Kev publication is verified: Pages [37453498358](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37453498358) succeeded for `f0515800`. Live HTML, renderer and both data feeds match committed bytes exactly. Desktop and 390px mobile views were inspected; the cost disclosure expanded by keyboard. New reduced-motion emulation was not performed.
- The 47-entry shared-authority tracker retains maximum historical holds after terminal reconciliation. Read-only audit found at least one verified unused hold of $0.073788960 (Jev P2 fresh1), exceeding the immediate continuation shortfall. The $10.41 question is still unapproved, but an increase may be unnecessary after a reviewed versioned reconciliation. Do not append release events to the frozen hold-only format or spend against an unimplemented release. native_variant_admission_audit owns the full provenance audit; root owns any later guarded implementation.
- Jev P0 and the exact P2 unsent proposal passed independent review; no dispatch is admitted. Jev findings are prepared in separate offline files and await root integration. Qwen P1 continues on its original handle.

## Publication and next admissions, 6 October 2026, 11:01 UTC

- Kev: publication commit `f0515800` is pushed; Pages job 37453498358 is running. The combined analysis binds 193 source hashes. A clean staged checkout passed 15 Python and 12 JavaScript tests after fixing offline verification of archived absolute budget paths. Live page verification is still pending.
- Jev: closed and interrupted evidence is pushed in `31774b56`. P0 adapter passed seven offline tests and independent review, but no full P0 pass is admitted. The exact P2 fresh2 DEV-019–060 continuation has five passing offline tests and a proposal-only controller; independent review and executable admission remain pending. No replay of DEV-018 is permitted.
- Funding: the latest pending request is $10.41 for the separate shared postapproval ceiling, superseding the unanswered $10.36 proposal. The rate-limit continuation adds a reserve; remaining Jev work requires a ceiling of $10.408019024. OpenRouter aggregate authority remains $12.38. Neither pending amount is approved.
- Root: Qwen3.5 fresh1/P1 remains live on handle 92736. e4b_unsent_prepare owns offline Jev findings; root owns final report integration and publication verification.

## Verified checkpoint, 06 October 2026, 10:53 UTC

- Root: Jev OpenRouter fresh1 P1 and P2 are closed, raw-verified and budget-reconciled: each 60 valid answers and 54/60 all-four matches. P1 fresh2 is terminal with 59 valid, DEV-056 invalid and 53/60 all-four matches. P2 fresh2 stopped at DEV-018 with HTTP 429 after 17 valid answers; DEV-019–060 are never sent. The full $0.001344 unknown-charge bound is retained and its child is reconciled. No failed request was replayed. Earlier reconciliation helper attempts failed on method lookup before ledger mutation; the corrected call succeeded.
- Root: Qwen3.5 fresh1/P1 remains live on original handle 92736, verified this checkpoint. Battery execution is enabled.
- qwen35_successor_report: Kev P1/P2 findings and website panel are implemented and independently verified (six Python and five UI tests); combined analysis/docs integration is underway. Publication remains pending.
- native_variant_admission_audit: prepare only the 42 never-sent Jev P2 reviews as a separately reviewed continuation. New P0 adapter is offline-prepared; e4b_unsent_prepare reviews it. No new Jev dispatch is admitted while the separate authority cap cannot cover its conservative reserve. The request to raise $10 to $10.36 remains unanswered.

## Verified checkpoint, 6 October 2026, 10:33 UTC

- Publication: Qwen3.5 P2 findings in e9b49905 are live. Pages run [37449776179](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37449776179) succeeded. Live legacy-Qwen and combined-analysis feeds match committed bytes (SHA-256 `3a80bebb076d6b96015a5addb673934d37deffa183100fefea77bccc94ae0f1c` and `c2f3a3d219f23a0af94317892d7ad4f94d29645b2fd846016271e37eee51d622`). Public browser text renders 1/9 and the 50/60 P2 result; this does not claim a new mobile or visual review.
- Root: Qwen3.5 fresh1/P1 development continues on original handle 92736.
- Root: reviewed Kev native full-run executor passed seven tests and independent review. P1 and P2 each have three closed, root-verified full passes with 60 valid responses per pass. All six child allocations are reconciled; total observed full-pass cost is $0.032537232. qwen35_successor_report owns the offline findings; publication is pending. Each reserves at most $0.020643840. The declared all-60 context calculation is a conservative estimate, not a provider guarantee; failures and unknown charges remain preserved.
- Root: OpenRouter Jev P1/P2 smokes each closed with three valid responses. Observed costs are $0.000319998 and $0.000342300. Both were inspected unchanged and child allocations reconciled. Full Jev admission preparation belongs to native_variant_admission_audit; e4b_unsent_prepare reviews it independently. No full Jev run is admitted by this checkpoint.


## Verified execution checkpoint, 6 October 2026, 10:19 UTC

- Root: Qwen3.5 thinking-on fresh1/P2 closed with 60 saved responses, 51 valid and nine invalid; terminal exit 0 and host audit passed. Findings review is assigned to qwen35_successor_report. These results are not yet published.
- Root: Qwen3.5 fresh1/P1 smoke passed and was inspected. Its full 60-review pass is now running on handle 92736 after fresh route, runtime, token and host checks.
- Root: Kev P1 native smoke closed with three valid responses and $0.000260064 observed cost. Raw responses inspected unchanged; child allocation reconciled. The earlier missing-directory admission failed before any ledger mutation or inference. Full-pass context proof and executor preparation belong to native_variant_admission_audit; no full Kev P1 pass is admitted.
- The complete roster remains unfinished. This dated checkpoint supersedes older running-handle statements below; preserved historical notes are not current dispatch instructions.


## Native smoke executor reviewed, 6 October 2026, 10:13 UTC

The [v2 Kev/Jev smoke executor](../scripts/openrouter_native_variants_v2.py) passed independent re-review after fixing the request-binding gap. Verdict: APPROVE, no confirmed remaining findings. Seven offline tests pass in both the implementer's and root's runs, including temporary-ledger accounting and changed-input refusal before spending. Four offline manifests remain `prepared_not_admitted`; no allocation, authority hold or model call was made.

The next eligible native stage is Kev P1 DEV-001–003, subject to fresh exact-route verification, an atomic child allocation and a root receipt binding the current shared-authority head. Full passes remain disabled pending all-record context proof and inspected smoke evidence. The [dated route audit](../results/route-audits/native-variants-recheck-20261006/README.md) records public metadata and ledger headroom, not current admission.

## Publication verified, 6 October 2026, 10:08 UTC

[Pages run 37447299000](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37447299000) succeeded for `92d07574`. Live `kev-native-repeats.json` matches the committed feed, SHA-256 `3f8b95ae790a8252fe2bb7a6823a8ee8196a245bf37bd4fb4f5944cb2b0e0fa9`; live HTML also matches, SHA-256 `4dc84f169a20b7201adc6b96bf6b0bda1fef81d6ceee703d5d07be1d06a5e3c0`. This verifies publication bytes, not a new browser visual inspection. The earlier failed deployment is preserved.

Qwen3.5 P2 is still running, last counted at 56 saved and 49 valid. Independent native-v2 review requested changes for a BLOCKING request-binding gap between manifest verification and dispatch. The implementer owns the fix and zero-spend regression. No native smoke is admitted and no paid request was sent.

## Gemma continuation prepared; native review underway, 6 October 2026, 10:05 UTC

Root re-reviewed the E4B continuation after the live prompt/token preflight fix: APPROVE, no confirmed remaining findings. Six tests passed in root's run; the implementer then added and passed a seventh test for all eight successful fixture responses. The exact DEV-053–060 manifest is frozen as `offline_prepared_unapproved`, SHA `ce0ff9227691fff4be38cfba9f2e3e1372d528778062be640c60dbfd0fe4b6dc`. No runtime preflight, model load or inference has occurred for it. Qwen3.5 retains the GPU lock; later admission must verify hosted absence, the loaded model, current host and root receipt.

`e4b_unsent_prepare` now independently reviews the new Kev/Jev native-v2 smoke executor. Root is running its six offline tests. The old full-pass context gate remains; no smoke is yet admitted. Root manually dispatched Pages after the test-only publication fix, because this workflow triggers automatically only on public-site or workflow changes. Deployment success and live-byte verification are still pending.

## Publication fixture repaired, 6 October 2026, 09:58 UTC

Pages run 37445559463 failed because three new Qwen reporter tests read the uncommitted live development receipt. Root replaced that dependency with explicitly synthetic development receipts derived from committed smoke evidence. All 15 reporter tests pass both in the working tree and in a clean Git archive with only the proposed test overlaid. Review: APPROVE; the confirmed BLOCKING clean-checkout failure is resolved without committing live run files. No published score or inference request changed. A new deployment must still succeed before the Kev wording change is called published.

Gemma E4B successor review found a BLOCKING missing live render/token preflight. The implementation now measures all 60 frozen P2 prompts and revalidates the eight pending requests before claim. Root's focused rerun is underway; the manifest remains unfrozen and no execution is admitted.

## Kev reference-review wording corrected, 6 October 2026, 09:49 UTC

The Kev builder and feed now record the owner's 2 October confirmation that all 60 labels were human-reviewed, while retaining frozen provisional v0.2 labels and unchanged scores. JSON comparison confirms only `referenceStatus` changed. Combined analysis still verifies against all 130 source hashes. Of 27 combined reporter tests, one historical hosted-v2 export test failed at a pre-existing missing phase-closure file; no Kev test failed. The old hosted-v2 builder also fails its current-tree interrupted predecessor gate. Those historical builders and feeds were restored unchanged; their archival refresh needs a separately versioned approach. Root review of the two-line Kev change: APPROVE, no findings. Publication is pending.

The native-variant audit reports both exact Kev/Jev endpoints available at unchanged public rates. The old runner's hard $10 ledger and missing shared-authority hold prevent current admission despite sufficient last-observed headroom. No request or budget mutation was made; a reviewed versioned executor is the next step after the audit finishes.

## Independent continuation preparation, 6 October 2026, 09:44 UTC

`e4b_unsent_prepare` owns offline preparation for exactly DEV-053 through DEV-060 in Gemma E4B thinking-on fresh2/P2. Its two unknown outcomes, DEV-039 and DEV-052, and 50 saved answers must remain unchanged. The agent may create a separate controller, tests and unapproved manifest; it may not load a model or send requests. Root must review it and recheck hosted availability before any local admission.

`native_variant_admission_audit` owns a read-only check of the prepared Kev/Jev OpenRouter P1/P2 variants, including actual prior execution, exact routes, prices, context accounting and current budget-controller compatibility. Public metadata reads are allowed; credentials, paid calls and ledger changes are not. Root owns any later admission. Qwen3.5 P2 continues on handle 13132 under the shared GPU lock.

## Roster counts reconciled, 6 October 2026, 09:40 UTC

Root finalized the [remaining roster](REMAINING_ROSTER_2026-09-29.md) against the published reports. Five legacy Qwen configurations have all nine phases closed. Qwen3.5 thinking-on retains its separate interrupted P0 composite and live P2; neither is counted as a completed clean phase. Mistral none has one fully accounted P0 descriptive composite (55 valid, five failed, 40/60 all-four matches), with no clean-repeat credit; high remains unstarted. P1's failed smoke remains visible. Counts and local links were checked. The agent's specialist action inventory is unfinished and is not claimed as delivered; root retains that task. No new request or budget entry was made.

## Offline budget test added, 6 October 2026, 09:35 UTC

The DeepSeek fourth-price test now runs the complete ten-record continuation with temporary child and shared-authority ledgers and a fake transport. It verifies exact ordered IDs, paired reservations and settlements, simulated charges of $0.010, and one $0.25 hold. All 15 focused tests pass in root's rerun. Review: APPROVE, no confirmed findings in this test change. This closes the earlier budget-path coverage gap; it does not establish live provider availability or authorize dispatch.

Qwen3.5 P2 handle 13132 remains live, with 25 responses saved (19 valid) at this checkpoint. `remaining_action_audit` owns correction of stale Qwen and Mistral entries in the remaining-roster document. Root owns execution and commits; no real budget ledger changed.

## DeepSeek continuation reviewed, 6 October 2026, 09:31 UTC

The [fourth-price controller](../scripts/deepseek_low_fourth_price_suffix_v1.py) and its [unapproved manifest](../results/repeatability-v1/deepseek-low-fresh3-v2/fourth-price-suffix-051-060-v1/manifest.json) passed independent review and 14 offline tests. Verdict: APPROVE. RESIDUAL: the focused tests stop at the live gate rather than exercising a successful request against temporary budget ledgers; the inherited atomic budget implementation was inspected. This is a test coverage gap, not a confirmed execution defect.

The exact DEV-051 through DEV-060 continuation remains blocked: the latest archived provider status is -2, and its prices differ from this proposal. No allocation, hold or inference was made. Root owns fresh admission if that route becomes available. `remaining_action_audit` is checking the specialist roster for independent work; Qwen3.5 P2 continues on its existing handle 13132.

## Successor reporting reviewed, 6 October 2026, 09:27 UTC

The reporter now validates separately completed Qwen3.5 successor phases before counting them in the repeat study. The interrupted P0 composite keeps its own exclusion from clean repeats. Independent review approved the change with no remaining findings; all 15 focused reporter tests passed. Live P2 output remains excluded from the public feed. Handle 13132 is confirmed running, with 19 saved responses (14 valid) at this checkpoint. Root owns execution, closure and publication.

DeepSeek fourth-price continuation code and 14 passing offline tests are ready for independent review by `deepseek_fourth_review`. Its manifest is unapproved, and the archived exact endpoint reports status -2. No paid request, allocation or hold was made. Battery operation remains enabled and both policy tests pass; no active run was restarted.

## Admission tests repaired; hosted access checked, 6 October 2026, 09:12 UTC

Commit `3c958872` removes two stale test assumptions that historical run folders remain empty; all 43 admission/continuation tests pass. Production controllers and frozen evidence are unchanged. Qwen3.5 P2 handle 13132 remains live (nine saved at this checkpoint, seven valid and two invalid). The report agent is preparing validation for completed successor phases without exporting live output. The DeepSeek wrapper remains offline and its exact route is blocked by the 08:59 snapshot. A separate authorized read-only Cloudflare route could not read the model catalog (HTTP 403), so current Clef access and quota are still unverified. No paid request, reservation or credential change occurred.

## DeepSeek route unavailable again, 6 October 2026, 08:59 UTC

Root archived a fresh public catalog response: the exact `open-inference/fp4` endpoint now reports status -2 and changed prices. This supersedes the earlier 08:43 available observation. [Audit and raw snapshots](HOSTED_ROUTE_CHECK_2026-10-06.md) are saved; no child allocation, global hold or inference was made. The price-wrapper agent is finishing offline fixes only. Qwen3.5 P2 continues under handle 13132; its GPU lock remains exclusive.

## Qwen3.5 full P2 running, 6 October 2026, 08:53 UTC

Smoke handle 67319 completed with three valid outputs; root inspected each final JSON, verified raw classification and unchanged host, then recorded the smoke inspection. Fresh all-60 P2 preflight passed under the same model instance. Full development handle 13132 is running; no complete P2 score exists yet. Root owns monitoring and closure. Pages job 37438211625 succeeded for `58eb2682`; live HTML, repeat JavaScript, analysis JavaScript and both report JSON files match committed bytes. DeepSeek fourth-price successor remains offline preparation. No paid request or budget mutation occurred.

## Qwen3.5 P2 smoke running, 6 October 2026, 08:49 UTC

The P0 descriptive composite is closed at 47/60 all-four matches, 51 valid, eight invalid and one unknown; sources are archived in `772af561`, report changes in `58eb2682`. Remaining-phase successor `8d0dea4c` passed seven offline tests and independent review after an exact-model route check fix. Verdict APPROVE; RESIDUAL receipt provenance fields are documented. Fresh host, artifact, instance and all-60 prompt/token checks passed. Handle 67319 is running fresh1/P2 smoke under the shared GPU lock. Root must inspect its three raw responses before any full pass. Do not stage live phase files or replay the claimed stage. DeepSeek price successor preparation is delegated to `deepseek_price_fallback` after Sol capacity failure; no paid request or hold has been made. Pages job 37438211625 is still deploying the P0 composite at this checkpoint.

## Qwen3.5 P0 continuation closed, 6 October 2026, 08:39 UTC

Handle 41371 exited 0 after all eight never-sent reviews were saved: seven valid and one invalid. DEV-057 exhausted 4,096 output tokens without final JSON; it is retained unchanged. Root reclassified saved outputs and checked hashes, ordered request IDs, reference isolation and unchanged host state. The [composite root review](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-p0-unsent-suffix-v1/composite.root-review.json) binds 28 source files. Combined P0 accounting is 59 saved: 51 valid, eight invalid, plus DEV-052 unknown and zero unsent. It remains descriptive and non-clean. No inference is running. The report agent owns composite projections; the successor agent owns offline admission for the remaining eight phases. Root owns review, generated feeds, publication and dispatch.

## Eight-record Qwen3.5 continuation running, 6 October 2026, 08:25 UTC

Commit `21f19ed5` is pushed. Seventeen Python report tests, eleven UI checks and four suffix tests passed. Root review: APPROVE; no remaining BLOCKING findings. RESIDUAL: two older admission tests assume completed smoke evidence is absent. The new continuation retains the completed smoke and permits only DEV-053–060; DEV-052 remains unknown. Fresh all-60 rendered-prompt/token checks, artifact identity, host state and exact OpenRouter route absence passed. Handle 41371 is live and DEV-053 has started. Root owns dispatch and closure; the implementation agent completed the [next-phase admission design](QWEN35_REMAINING_PHASE_ADMISSION.md); implementation follows terminal reconciliation of this suffix. Pages job 37435857145 succeeded; live HTML, both JavaScript files and both report JSON files match the committed bytes. Browser visual verification remains unavailable under the recorded access restriction. Do not stage live suffix output or replay its claimed stage.

## Qwen3.5 P0 interrupted by low-power sleep, 6 October 2026

Handle 35256 is terminal (exit 1), and LM Studio reports the model idle. The run saved 51 responses: 44 valid and seven invalid. DEV-052 was started and remains unknown after the 600-second prediction cancellation; DEV-053–060 were never sent. Completion hashes and ordered IDs are verified. The [host audit](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/interruption.host-audit.json) records Low Power Sleep at 1% battery on 5 October, followed by hibernation wake on 6 October. Sleep count changed from 92 to 93 without a reboot. The timeout spans that sleep and is not an inference-time measurement.

No clean pass or full score is claimed. `qwen35_interruption_report` owns the separate partial-result projection. `qwen35_suffix_fallback` owns an offline, exact DEV-053–060 continuation; the originally selected Sol agent could not start because of capacity. Root owns review and any live dispatch. The completed smoke and all 52 attempted positions are preserved; DEV-052 must not be replayed. The host is currently on AC with its lid open and adequate memory, but a new admission must verify current route/runtime and host state. No inference is running and no additional paid request was sent.

## Mistral P1 smoke stopped, 5 October 2026, 20:24 UTC

Reviewed successor `f0b98402` passed eight offline tests and independent review (APPROVE; no remaining findings). Fresh credentials and exact route checks passed. Root reserved $0.12533760 for the three-record smoke under both authorities. Handle 67707 exited 1 after DEV-001 returned HTTP 429 from the upstream provider shared pool with no reported cost. DEV-002/003 were never sent; no P1 development request was admitted. The raw response is retained locally; the [public terminal receipt](../results/repeatability-v1/mistral119-fresh-matched3-v1/p1-successor-v1/smoke.terminal-public.json) excludes the private account identifier. No request was replayed.

Root retained the full $0.04177920 unknown-charge bound, sealed the child, and released $0.08355840 unused OpenRouter allocation. The separate $0.12533760 global authority hold remains retained. This is a provider capacity failure, not insufficient account credit. The local Qwen3.5 P0 run remains active under handle 35256. The whole benchmark remains incomplete.

## Hosted admission preparation, 5 October 2026, 20:11 UTC

Root verified the existing Qwen3.5 first-P0 handle 35256 remains live, with 17 saved responses at this checkpoint. No new local run is admitted. A fresh locked OpenRouter replay has $0.52219181750 unallocated under $12.38, no pending reservations and no active children. The separate cross-provider authority has $0.633518 remaining under $10. Both files were unchanged by these checks.

`pending_hosted_recheck` owns a read-only exact-route audit. `mistral_p1_admission_prepare` owns a new offline exact-P1 successor and tests; root retains review, budget and dispatch. The old Mistral predecessor gate requires 59 valid plus one unknown P0 position, whereas the closed result has 55 valid and five failed. A separate admission must bind the actual evidence, preserve every failure and prevent replay. The proposed smoke/full child caps total $0.37533760 and fit both current ceilings, but no hold, receipt or request has been issued. DeepSeek's exact frozen endpoint remains unavailable in the fresh audit. These are execution boundaries, not accepted exclusions.

## Analysis consistency checkpoint, 5 October 2026, 20:01 UTC

Publication verified: commit `2dd9cc5c`, Pages job `37367158387` succeeded. Public HTML, analysis JavaScript, analysis JSON and the legacy repeat feed match the committed bytes. The live Qwen3.5 run remains active at 12/60 saved responses; no completed score is inferred from that partial count.

Root verified handle 35256 remains live, with eight saved Qwen3.5 P0 responses at this checkpoint. No full Qwen3.5 result is published. The roster and analysis document now reflect all nine completed Qwen1.7 thinking-off phases. The report agent added closed-phase Qwen3.5 scores, validity, tokens, client timing and supported comparisons; root regenerated the analysis feed from 130 source hashes. Fifteen Python and ten UI checks pass. Review: APPROVE, no confirmed BLOCKING findings. RESIDUAL: browser visual verification remains unavailable under the previously recorded browser-tool access restriction. Root owns publication and the live run; no paid request or budget change occurred.

## Qwen3.5 first full pass running, 5 October 2026, 19:50 UTC

Smoke handle 10314 completed with three valid outputs. Root inspected each raw response, verified hashes and reference isolation, then passed fresh all-60 preflight under the same pinned instance. Fresh1/P0 development handle 35256 is running; do not dispatch another phase or model on its GPU lock. Completed smoke evidence is archived separately from live development files. The preceding final Qwen1.7B report is verified published. No paid request occurred.

## Qwen3.5 4B smoke running, 5 October 2026, 19:48 UTC

Root refreshed the 464-model OpenRouter catalogue: no exact Qwen3.5 4B family was found. Loaded the existing Q4_K_M artifact through the CLI with context 8192, GPU ratio 1 and parallel count 1. Frozen runtime, artifact and all-60 rendered/token checks passed on battery, instance Nqw5yKTLeyosrkku4WOQzW4M. Fresh1/P0 smoke handle 10314 is live; LM Studio confirms GENERATING and DEV-001 saved a valid JSON response. No full development request is admitted yet. Root owns smoke inspection and dispatch. Qwen1.7B final publication job 37365373674 succeeded; live HTML, repeat JS, legacy report and combined analysis JSON/JS exactly match cac0776d. No paid request occurred.

## Final thinking-off P2 closed, 5 October 2026, 19:35 UTC

Root reviewed the exact-phase successor (APPROVE, no confirmed BLOCKING or RESIDUAL findings); twelve current and historical successor tests passed. Independent raw-smoke inspection was approved by `battery_review`. Fresh locked host/route/all-60 runtime checks passed, then root approved the candidate receipt and dispatched handle 8976. The full phase completed with 60 saved, 55 valid, five invalid. Hashes, ordered IDs, reference isolation and post-stage host checks passed. All nine thinking-off development phases are executed; source-bound report integration and final analysis/publication remain underway. Independent review caught a BLOCKING builder regression in the old 0.6B branch; it was fixed before publication. Settled review: APPROVE, no confirmed BLOCKING or RESIDUAL findings. Both feeds rebuilt; fourteen Python and twenty-one Node tests passed. README, findings, coverage and main analysis now reflect 9/9. Final publication is pending. Next local matrix is Qwen3.5 4B thinking-on, subject to fresh exact-route/runtime admission. The original stopped smoke is unchanged. No inference is running and no paid request occurred. Pages 37363502046 for 3e0f0492 succeeded; live HTML, repeat JS, legacy report and combined analysis JSON match committed bytes.

## Final P2 continuation preparation, 5 October 2026

No inference is running. `battery_review` owns the new exact-phase 1.7B thinking-off fresh3/P2 successor controller, manifest and offline tests; it is unapproved. `off_p2_findings` owns the main analysis builder/UI update to remove stale second/third-pass wording and expose current repeated results. Root owns independent admission, regenerated feeds, documentation, git and publication. Existing frozen runners, requests and failed smoke are preserved. The broader goal remains active and incomplete.

## Eight thinking-off passes closed, 5 October 2026, 19:27 UTC

Fresh2/P0 and fresh3/P1/P0 closed with 60 valid answers each; all post-stage checks passed. Scores P0 28/26/26, P1 25/26/25, P2 32/30. Fresh3/P2 smoke handle 98636 stopped after three responses: two valid, DEV-003 invalid fenced JSON. No full P2 request was sent and no inference is running. Root and review agent are examining a separately versioned continuation; the failed smoke must not be repaired or replayed. Public power-source labels and source-bound evidence pass review (APPROVE, no BLOCKING or RESIDUAL findings). Browser visual verification was blocked by the browser tool policy; automated UI checks pass. Report refresh and publication of this checkpoint are pending.

## Second P0 closed; third P1 running, 5 October 2026, 19:22 UTC

Root closed fresh2/P0 with 60 valid responses and verified post-stage host evidence. Thinking-off execution is 6/9; third P1 handle 91247 is running after three inspected valid smoke responses and all-60 preflight. The report agent owns power-source provenance in the legacy builder and repeat UI; root owns execution, regenerated feeds, docs and git. Pages job 37362249831 succeeded for 03a4bfc3; exact live HTML, legacy feed and combined analysis JSON/JavaScript bytes are verified. No paid request occurred.

## Battery run closed, 5 October 2026, 19:13 UTC

Root closed thinking-off fresh2/P2: 60 saved, 56 valid, 30/60 all-four matches. Actual battery operation is recorded, with unchanged boot/sleep and open lid verified. Fresh2/P1 handle 49188 then closed: 60 valid, 26/60 matches, with post-stage checks passed. Coverage is 5/9; next is fresh2/P0 smoke. No inference is running. A route-audit filename mismatch stopped the first preflight before dispatch; the helper now sanitizes the directory name and the frozen controller remains unchanged. Eleven Python and thirteen Node checks pass. Combined and legacy report feeds are regenerated; publication is pending. No paid request or budget mutation occurred. Read-only review: APPROVE; RESIDUAL receipt candidate timestamps precede the explicit root review/copy step, retained for follow-up.

## Battery execution authorized, 5 October 2026

The user removed the AC-only restriction. `config/local-execution.json` permits battery operation; the current host helper and Qwen preflight record actual power source and policy hash. Five tests pass, including battery admission, preserved historical AC enforcement, sleep detection, and lid/memory checks. Live host admission passed on battery at 49%. Earlier power-blocked notes are historical. Next step remains a fresh development preflight for thinking-off fresh2/P2, retaining the completed smoke.

## Published; execution blocked, 5 October 2026, 15:42 UTC

Pages job `37334126837` succeeded for `b9d041e2`. Live HTML, analysis JSON and analysis JavaScript match committed bytes; a transient SSL timeout was followed by a successful bounded retry. Roster correction `f29ee95f` is pushed. AC power remains unavailable across three consecutive goal turns. No inference is running; thinking-off fresh2/P2 development is still never sent and its completed smoke inspection is preserved. Offline paired analysis and its publication are verified. Resume local execution after AC and runtime checks; existing hosted budget, quota and exact-route/access blockers remain. The benchmark is not complete.

## Offline paired-prompt analysis, 5 October 2026

AC-power requirement still blocks local inference. Root added source-bound thinking-off P0→P1/P2 review comparisons, independently recomputed by the projection agent: P1 gained/lost 4/7 matches among 59 jointly valid; P2 gained/lost 9/5 among 57. Invalidated reviews were already non-matches in P0. Two Python tests (including relocated reconstruction and source-tamper rejection) and seven UI checks pass. Root review: APPROVE, no confirmed BLOCKING or RESIDUAL findings. Browser counts and explanation are verified; publication follows. The preceding `039416a5` Pages run `37333275549` succeeded and its live HTML plus three report assets match committed bytes. No model request or budget mutation occurred.

## Local host boundary, 5 October 2026, 15:30 UTC

Fresh2/P2 thinking-off smoke handle `15127` completed with three valid outputs and root inspection. The subsequent full-development preflight `55073` failed before dispatch because the host is on battery power, confirmed by `pmset -g batt`. No development request was sent and no inference is running. Reconnect AC, revalidate host and runtime, then create a fresh development receipt; do not repeat the completed smoke. First-prompt comparison commit `039416a5` is pushed; Pages job `37333275549` is pending. Other provider and budget limits remain unchanged.

## Qwen1.7B thinking-off first prompt comparison closed, 5 October 2026

Root closed P2 handle `27062` (57 valid, 3 invalid, 32/60 matches) and P1 handle `23860` (59 valid, 1 invalid, 25/60 matches). Root inspected P1 smoke, verified both completions, hashes, ordered IDs, reference isolation and unchanged host. All four invalid outputs contain Markdown code fences; no repair or retry occurred. Thinking-off is 3/9; thinking-on remains 9/9. No inference is currently running. Next is thinking-off fresh2/P2 smoke. No paid request or cap change occurred.

Preceding P0 commit `90e698d7` is verified live: Pages `37331900049` succeeded, and HTML, legacy report and combined analysis JSON/JavaScript match the committed bytes. Current first-prompt checkpoint passes eleven Python and eight UI checks. The browser shows 3/9 and the 28/25/32 comparison. Root review: APPROVE, no confirmed BLOCKING or new RESIDUAL findings. Commit and publication verification follow.

## Qwen1.7B thinking-off P0 closed, 5 October 2026

Root inspected three valid smoke outputs (handle `58919`), verified a fresh hosted-route audit and all 60 frozen runtime/render/token checks, then closed development handle `1536` with 60 valid outputs and 28/60 matches. Post-stage hashes, ordered IDs, reference isolation and unchanged boot/sleep/AC/lid passed. Thinking-off is 1/9; thinking-on remains 9/9. No inference is currently running. Next scheduled stage is thinking-off fresh1/P2 smoke. No paid request or budget mutation occurred. Eleven Python and eight UI checks pass; the browser shows 1/9 and 28/60 correctly. Root review: APPROVE, no confirmed BLOCKING or new RESIDUAL findings. Publication of this increment is pending. The preceding nine-run checkpoint `2d29c12d` is verified live: Pages job `37330774936` succeeded and HTML plus the three report assets match committed bytes.

## Qwen1.7B thinking-on matrix closed, 5 October 2026

Root closed final fresh3/P2: smoke handle 1418 and development handle 72800 exited zero. Smoke raw responses were inspected; full run saved 60 valid answers, with hashes, ordered IDs, reference isolation and unchanged host verified. The configuration is now 9/9. P2 scores 8/9/8; 40/58 shared-valid reviews vary across repeats. Root owns combined analysis, review, commit and publication; the projection agent owns the closed legacy feed and findings. No inference is currently running. No paid request or cap increase occurred. Remaining roster entries and provider/budget blockers below still apply.

Previous checkpoint f2a11778 is published: Pages job 37328666061 succeeded and live HTML plus the three report assets match the committed bytes. The final nine-run checkpoint passed eleven Python tests and eight UI tests. Browser checks show 9/9 coverage and the 40/58 P2 changed-review result. Root review: APPROVE, no confirmed BLOCKING findings or new RESIDUAL findings. Commit and publication verification follow.

## Third P0 closed, 5 October 2026

Pages job `37327405475` succeeded for `53457fe2`; live HTML, legacy Qwen JSON and combined analysis JSON/JavaScript match the committed bytes. Root review of this checkpoint: APPROVE, no confirmed BLOCKING or RESIDUAL findings. Eleven Python and eight UI checks passed; browser coverage and the matched three-pass comparison are verified.

Fresh3/P0 smoke handle `32428` exited zero with three valid outputs. Root inspected raw JSON, verified source hashes and reference isolation, then checked all 60 rendered requests and the pinned runtime against a fresh exact-route audit. Full handle `54665` exited zero with 60 saved and valid answers. Root verified hashes, ordered IDs, reference isolation and unchanged host boot/sleep/AC/lid. P0 scores 24/23/24 out of 60; across three passes 19/60 reviews change labels. Coverage is 8/9, with only third P2 remaining. No inference is currently running. Root owns execution and combined analysis; `qwen17_repeat_projection` owns only the closed legacy report and findings. No paid inference or cap change occurred.


## Third P1 closed, 5 October 2026

Root review: APPROVE, no confirmed BLOCKING findings. A RESIDUAL stale two-pass sentence was corrected before publication. Eleven Python and eight UI checks passed; browser coverage is 7/9 and the P1 three-pass finding is verified.

Pages job `37325886456` succeeded for `d374d20d`; live HTML, legacy Qwen JSON and combined analysis JSON/JavaScript match the committed bytes.

Root fresh3/P1 smoke handle `12337` exited zero with three valid outputs. Raw JSON, completion hashes and reference isolation were inspected. Fresh route and all 60 runtime/render/token checks passed under the same pinned instance. Full handle `73837` exited zero with 60 saved and valid answers. Root verified hashes, ordered IDs, reference isolation and unchanged boot/sleep/AC/lid. P1 scores 12/11/16 out of 60 across three passes; 30/60 reviews changed labels. Coverage is 7/9, with third P0/P2 pending. No inference is currently running. Root owns closure and combined analysis; `qwen17_repeat_projection` owns the closed legacy feed and findings after notification. No paid request or cap change occurred.


## Second P0 closed, 5 October 2026

Pages job `37324862613` succeeded for `16ce572a`; live HTML, legacy Qwen JSON and combined analysis JSON/JavaScript match that commit. Root review of the second-P0 report: APPROVE, no confirmed BLOCKING or RESIDUAL findings. Eleven Python and eight UI checks passed; browser coverage and paired findings are verified.

Root fresh2/P0 smoke handle `99236` exited zero with three valid outputs. Root inspected the raw JSON and verified completion hashes and reference isolation. A fresh exact-route audit and all 60 runtime/render/token checks passed under the pinned loaded Qwen1.7B model. Full handle `76829` exited zero with 60 saved and valid answers. Root verified hashes, ordered IDs, reference exclusion and unchanged host boot/sleep/AC/lid. The second P0 score is 23/60 versus 24/60 previously, with labels changing on 11/60 reviews. Coverage is 6/9; each condition needs one final pass. No inference is currently running; root owns closure and combined analysis, and `qwen17_repeat_projection` owns only the closed legacy projection and findings. No paid inference or cap change occurred.


## Second P2 published; second P1 closed, 5 October 2026

Pages job `37323486415` succeeded for `ee618fd8`. Live HTML, legacy Qwen JSON and combined analysis JSON/JavaScript match the committed bytes. Root independently verified fresh2/P1 smoke handle `98857` with three valid raw answers, hashes and reference isolation. All 60 fresh runtime/render/token checks passed; the exact family remains absent from the 466-model OpenRouter catalogue. Full handle `26168` exited zero with 60 saved and valid answers. Root verified source hashes, ordered IDs, reference isolation and unchanged boot/sleep/AC/lid state. P1 scores 11/60 versus 12/60 previously, with 23 of 60 reviews changing a label. Coverage is 5/9; four phases remain. No inference is currently running. Root owns execution and combined analysis; `qwen17_repeat_projection` owns the closed legacy feed and findings only after root verifies completion. No paid inference or cap change occurred.


## Qwen first-pass publication and second P2 execution, 5 October 2026

Pages job `37321501799` succeeded for `37d9c78f`. Root verified live HTML, repeat JavaScript, legacy Qwen JSON and combined analysis JSON/JavaScript against local committed bytes. The browser now shows the correct 3/9 first-pass coverage and scores 24/12/8 after the stale repeat-feed cache fix; 77 shared UI tests passed.

Fresh2/P2 smoke handle `90137` exited zero with three valid outputs. Root inspected raw responses, completion hashes, strict non-reasoning JSON and reference isolation. A fresh 466-model hosted catalogue audit still has no exact legacy Qwen route. All 60 runtime/token checks passed with the pinned loaded artifact and AC/open-lid host. Full handle `98747` exited zero: 60 saved, 59 valid and one format failure on DEV-033. Root verified source hashes, ordered IDs, reference isolation and unchanged host boot/sleep state. The second P2 pass scores 9/60; 30 of 58 jointly valid reviews change at least one label from the first pass. Coverage is 4/9, with five phases remaining. No inference is currently running. Root owns dispatch and closure; agent `qwen17_repeat_projection` owns only the report projection and findings after closure. Sol report delegation was unavailable at capacity; Luna is the declared fallback. No paid request or cap change occurred.


## Qwen1.7B P2 resumed, 5 October 2026

Root verified AC power, open lid, 85% memory headroom and the unchanged pinned SDK/app/CLI and Q4_K_M artifact. The current 466-model OpenRouter catalogue has no exact legacy Qwen family route. The loaded instance passed all 60 frozen P2 render/token checks. Fresh1/P2 smoke closed with three valid outputs and was independently inspected before development admission. Full pass handle `13294` exited zero with all 60 saved, 59 valid and one format failure. Root verified completion hashes, ordered IDs, reference exclusion and unchanged host boot/sleep state. Closed evidence is pushed in `1ff4ab61`. P2 scores 8/60 all-four matches versus 24/60 for P0 in this first pass; the format failure is DEV-012. Fresh1/P1 smoke subsequently closed with three valid outputs and was independently inspected. Its full pass handle `9570` exited zero with 60 saved and valid outputs; root verified the same hashes, IDs, reference exclusion and host checks. All three first-pass prompt conditions are now closed; scores P0/P1/P2 are 24/12/8 out of 60, and six second/third passes remain. No inference is currently running. Agent `qwen17_p2_report` owns the closed-result projection and narrative; root owns combined analysis and publication. The read-only dispatch audit independently confirmed the frozen stage order. No paid request or cap change occurred.

## Current repeat view and roster reconciliation, 5 October 2026

The current Clef P0/P1/P2 matrix now shows all three pass positions from the combined analysis feed. Clef has four scored passes; Flash has eight, with its third P0 preserving two unknown outcomes and 58 unsent reviews. The historical P0 snapshot is dated and collapsed. The roster also reflects Gemma's nine descriptive results and Mistral's first descriptive result with 55 valid and five failed answers.

Root review: APPROVE, no remaining confirmed BLOCKING or RESIDUAL findings. The fixed source-count guard was corrected before publication so unrelated feed additions do not break the matrix. All 112 existing/shared repeat-view checks passed, followed by six focused checks including an additional source and duplicate-ID rejection. Desktop and 390px mobile previews are readable, with no horizontal page overflow; the table supports independent keyboard scrolling. No animation was added. Pages job `37317312711` succeeded for `27048820`; live HTML, repeat JavaScript and CSS match the verified local bytes. No inference is admitted or running; Cloudflare quota and other recorded execution blockers remain.

## Flash continuation stopped at provider quota, 5 October 2026

Reviewed controller `478615ce` is pushed. Root dispatched exactly one suffix request, DEV-002, through the connected Cloudflare app. The app returned error 4006, daily free-neuron allocation exhausted. The original runner handle `37421` then exited zero with a stopped receipt: one unknown outcome, zero valid outputs, DEV-003–060 never sent. No retry, upgrade or plan change occurred. DEV-001's earlier unknown outcome remains separate. Both completions and the new external-error audit are sealed.

The new $0.348041 stage hold remains conservative; total postapproval holds are $9.366482, leaving $0.633518. Actual Cloudflare charges are unavailable. Funding alone does not resolve the current daily provider quota. Further Cloudflare dispatch requires verified quota/access and separately admitted never-sent requests. Root review of the analysis update: APPROVE, no remaining confirmed BLOCKING or RESIDUAL findings. The draft's incorrect unknown-ID projection and missing completion-hash checks were fixed before publication. Two Python tests, three UI tests, clean-index archive reconstruction and browser text verification pass. All 127 analysis bindings match staged evidence. Pages job `37314865502` succeeded; live analysis JSON and JavaScript match the verified local bytes. All prior scores remain unchanged.

## Flash P0 recovery checks, 5 October 2026

The new one-shot suffix controller prepares exactly DEV-002 through DEV-060 for Flash fresh3/P0. Root verified the original request manifest, parent evidence, completed smoke, account binding and current billing source. Six focused offline tests pass both in the working tree and a clean Git archive with the new files overlaid; six existing remaining-stage tests also pass. Coverage includes all 59 requests, malformed and invalid responses, cap refusal, duplicate claims, concurrent ledger locking and the real connected-app submission handshake. The prepared manifest is `b5a512b67adbb1af9e852f6f9ed4c5326ca535ae9abd3a3e7463737f6d49006f`.

Independent review returned APPROVE with no confirmed BLOCKING findings. One RESIDUAL remains: a crash after the authority hold but before child creation can leave a conservative unused hold requiring reconciliation; it cannot send a request or overrun the cap. Root owns the grant and live dispatch. No new hold or inference request has been created. The proposed $0.348041 hold fits the current authority and would leave $0.633518. DEV-001 remains an unknown outcome, and its original hold is preserved.

## Clef P1 integrated; Flash continuation preparation, 5 October 2026

The combined analysis now recomputes Clef fresh1/P1 and matched P0 from ten completion-bound evidence files. Its 115-source feed reports 52/60 versus 53/60, four changed reviews, one gained full match and two lost matches. P1 remains one of three required passes. Two Python tests, including changed-source rejection, and three UI tests pass; root checked the rendered text. Independent review of `a4f1bc49` returned APPROVE with no confirmed BLOCKING or RESIDUAL findings and repeated the focused checks. Pages job `37311032456` succeeded. Root fetched live `analysis-refresh.json`, `analysis-refresh.js` and `index.html`; all are byte-identical to the verified local build.

Root's authenticated Cloudflare catalogue check still returns the exact Clef and Clef Flash routes, 65,536-token context and unchanged $0.24/$0.09 input prices per million. This is not a daily-quota check. The execution audit confirmed no existing reviewed runner can send only Flash fresh3/P0 DEV-002–060. Agent `flash_p0_suffix_prepare` failed at model capacity before producing files. Lower-cost fallback `flash_suffix_luna` now owns the new offline-only controller, tests and admission note; root owns review, grant and any later dispatch. The old DEV-001 unknown outcome and full-stage hold remain intact. A new $0.348041 suffix hold would fit current authority; nothing has been allocated or sent for it.

## Clef P1 closed; category filters verified, 5 October 2026

Clef fresh1/P1 smoke and development are closed: 3/3 and 60/60 valid. Independent audit verified completion hashes, ordered IDs and frozen request hashes; inference records confirm reference labels were not read. Development matched all four provisional labels on 52/60 reviews and reported 144,694 input tokens, zero output. This is one P1 pass, not a completed repeat study. Root owns immutable evidence archival; private app-bridge transport files stay untracked. The next required Clef P1/P2 passes and interrupted Flash P0 suffix remain unfinished; no spending cap changed. Shared paid-work holds total $9.018441, leaving $0.981559 under the $10 cap. A Clef smoke-plus-full pair reserves $0.990927, so another complete pair cannot currently be admitted. These are conservative holds, not observed bills. The existing request for a $14.33 aggregate postapproval ceiling remains pending.

The category update separates purpose, source-verified task-specific training and output interface. Categories can overlap; chart, saved-run and repeat filters agree. Seven focused UI tests pass. Browser checks verified decision-filter membership, fitted-head filtering, clearing filters and keyboard focus; the responsive viewport has no horizontal page overflow. Review APPROVE: no confirmed BLOCKING findings. Desktop and 390px mobile screenshots now confirm readable, stacked training controls with no page overflow. This is a verified filter increment, not a claim that the broader presentation redesign is complete.

Pages deployment `37308122826` for `5db1df22` succeeded. This confirms the Mistral public-archive fix and combined analysis build; the taxonomy increment `434d5b23` also deployed successfully in Pages run `37309296244`. Root fetched the live HTML and four changed JavaScript assets and verified exact local byte equality. Clef P1 evidence is pushed in `dd794be4`; its [first-pass analysis](CLEF_P1_FIRST_PASS_2026-10-05.md) still needs integration into the combined public feed. The analysis source inventory has 105 bindings.

## Public archive fixed; Clef P1 running, 5 October 2026

Root independently reproduced the Mistral report from a clean Git archive plus its candidate public bundle: exact JSON bytes matched and all three focused tests passed. The 61-file bundle preserves original and public hashes; differences are limited to local path removal and dependent hash references. A credential-pattern scan found no matches. Review: APPROVE, no confirmed BLOCKING findings. Fix `324695e3` is pushed; live deployment is not yet verified.

The combined analysis now includes Clef Flash P1/P2 and the final interrupted Mistral P0. Its 105 source bindings, two Python tests and three UI tests pass. The category agent still owns its frontend increment. The separate decision-model source note is pushed in `31bdfd66`.

Clef (not Flash) fresh1/P1 smoke `32325` completed 3/3 valid and was inspected by root. The exact new full-stage grant admitted development handle `22576`; root owns its connected-app dispatch. No failed or completed request is being replayed. The current $10 postapproval cap remains unchanged.


## Report categories and P2 analysis, 5 October 2026

Clef Flash P2 analysis is verified and pushed in `81f7c855`: three passes, each 60 valid answers and 46/60 all-four matches, with no pairwise label, probability or confidence changes. Root ran the projection check and all three focused tests. Review: APPROVE; no confirmed BLOCKING findings. This updates the earlier pending-analysis checkpoint below.

Following the user's [Cloudflare leaderboard reference](https://clef-evals.workers-ai-mle.workers.dev/), the presentation agent owns clearer category navigation and verified training-lineage filters. Purpose, fine-tuning and output interface can overlap and must remain separate. A source-research agent owns a bounded comparison of new decision-model families against our roster; external scores are not our results and discovery does not admit live runs.

The Mistral report agent owns a clean-checkout publication fix. Its builder still requires sealed evidence absent from the public archive; this is BLOCKING for publication. Root owns final integration and deployment verification. No budget increase or additional live dispatch occurred in this checkpoint.


## Clef Flash P2 three-pass execution complete, 5 October 2026

Root fresh3/P2 smoke `59400` and full-development `76311` exited zero. The smoke was inspected before full-stage admission. All three P2 full passes contain 60 valid ordered outputs, with 154,954 input tokens each and no pairwise changes in predictions, native probabilities or provider confidence. Root verified completion hashes and IDs independently. The P2 findings agent is extending the report to all three passes before root review. P1 and P2 repeat execution is now closed; Flash P0 remains interrupted and Clef P1/P2 remain unfinished.

The combined analysis draft is under root review. Root requested correction of a misleading P0 denominator and stale Mistral unsent-status text. Mistral's historical evidence dependency still needs a clean-checkout verification before publication. No spending cap was changed.


## P2 second pass closed; publication dependency found, 5 October 2026

Clef Flash fresh2/P2 smoke `37826` and development `66015` exited zero. Root inspected the smoke then admitted the full pass; all 60 ordered outputs are valid and completion hashes match. Both P2 passes report 154,954 input tokens and have identical predictions, probabilities and confidence. One P2 full pass remains. The report agent owns the two-pass P2 analysis update.

Pages `37303866029` succeeded for the Clef P1 evidence gate. Mistral deployment `37304071708` failed because `study.verify` requires an uncommitted historical smoke dependency (`results/openrouter-partition-mistral119-none-2026-09-23/smoke.jsonl`). Root reopened the report review as BLOCKING and assigned a full clean-archive verification, not just a helper fixture. No Mistral live-publication claim is valid. The existing public website remains at its prior successful deployment.


## Mistral findings approved after portability fix, 5 October 2026

Root reviewed the portable archived-child lookup, ran three focused tests and checked exact report regeneration. Verdict: APPROVE, with no remaining confirmed BLOCKING or RESIDUAL findings. Commit `5f3afa92` is pushed and includes the public projection plus CI verification. It reports 40/60 all-four matches, 55 valid outputs and five retained failures; 40/55 is the secondary valid-output figure. Deployment `37304071708` is queued behind `37303866029`; publication is not yet verified. The combined analysis agent is integrating this separate interrupted checkpoint and the approved Clef P1 findings.


## Clef P1 analysis approved, 5 October 2026

Root reviewed and committed the source-bound Clef Flash P1 findings in `4bab11d0`; four focused tests and the saved projection check passed. Three passes each score 47/60 with 60 valid outputs and no label/probability/confidence changes. The matched fresh1/P0 comparison rises from 45/60 to 47/60, with gains on DEV-027 and DEV-044 and no losses. The public analysis agent owns integration into the existing combined view; publication is not yet claimed.

Root review found a BLOCKING portability defect in the draft Mistral report: archived child ledger reads used original-machine absolute paths. The report agent is fixing the reads and adding a relocation check before approval. Its candidate 40/60 result remains unpublished pending verification. No spending-cap increase has been approved.


## Clef Flash P2 first pass closed, 5 October 2026

Root P2 smoke handle `46942` and full-development handle `41365` exited zero. Root inspected all three smoke responses before the separate full-stage admission; the full pass contains 60 ordered valid outputs with matching completion hashes. Two further P2 passes remain. The P1 findings builder passed four root-run tests; its report and the Mistral report are under final reference-history/copy review before combined publication.

Before P2 admission, the locked shared authority had $3.087397 available. Remaining Clef/Clef Flash stages required $7.408514 in conservative full-context holds, a $4.321117 shortfall. Root asked the user to raise the separate cross-provider cap from $10 to $14.33, leaving the OpenRouter $12.38 cap unchanged. No answer or cap change is recorded. The affordable P2 smoke/full pair used $0.371637 of the existing headroom; further work must continue to use the current cap until explicit approval. These are reservation bounds, not observed charges.


## Clef Flash P1 three-pass execution complete, 5 October 2026

Fresh2 and fresh3 P1 smoke/full stages completed under separate reviewed grants. Full-run handles `76818` and `5993` both exited zero with 60 valid outputs. Root verified source hashes, ordered IDs and all three pairwise comparisons: zero changes in predictions, probabilities or confidence across the three full passes. Each reports 144,694 input tokens. This establishes observed repeat stability, not correctness or calibration. The analysis agent is incorporating all three passes into the source-bound findings before publication. All actual Cloudflare charges remain unavailable and full-context reservations remain held.

The Mistral Sol analysis agent hit model capacity; a Luna agent now owns that bounded offline report. No new benchmark requests were assigned to analysis agents. Other Clef conditions and the wider roster remain unfinished.


## Clef Flash P1 complete and Mistral sealed, 5 October 2026

Root handle `79859` exited zero after all 60 Clef Flash fresh1/P1 development requests returned valid native outputs. Root verified ordered IDs, completion source hashes and input-only flags; reported input usage totals 144,694 tokens. The full $0.35394 stage hold remains because no actual charge was returned. The analysis agent owns the new P1 findings and comparison-control audit; no public score is claimed before that review.

Root reviewed the Mistral fourth terminal proposal (two tests passed before sealing), retained DEV-060's $0.04177920 unknown-charge bound, sealed the final child and released $0.04798245 unused allocation. Its observed DEV-059 cost is $0.00023835. The combined pass has 55 valid and five failed records, with none unsent. The Mistral agent owns the source-bound combined report; historical failures remain intact.


## Execution resumed, 5 October 2026, 11:10 UTC

Mistral fresh1/P0 has now attempted all 60 records: 55 valid and five failed (DEV-048, DEV-050, DEV-053, DEV-058, DEV-060). Root handle `48363` exited after DEV-060 returned HTTP 429; DEV-059 succeeded with $0.00023835 observed cost. The last child remains reserved pending terminal reconciliation; no failed request will be replayed. The terminal-review agent owns the proposal, root owns sealing and publication.

Clef Flash fresh1/P1 smoke handle `13299` exited zero with three valid responses. Root inspected all three native responses and wrote the source-bound smoke review. Input usage totals 7,228 tokens; no provider charges were returned, so the $0.017697 full-context hold remains. Parent environment credentials were verified without exposure. The unchanged 60-record development stage is next, requiring its separate exact grant and reservation.


Browser QA also passed on a local server using the published source: desktop 1280px, mobile 390px, keyboard disclosure, reduced motion, and category/interface filtering. No horizontal overflow or console errors were observed. Production asset equality was checked separately; this was not a direct production interaction test.

## Explorer publication verified, 5 October 2026

Pages run `37299477508` succeeded for `87cbf4bf`. Root fetched the live HTML and repeat script after deployment; both match the committed files (HTML SHA-256 `682e1fbd0b8d2e8a7bfb25ac09d26fe3ccccd8d481992b069a7b506588ccbf84`, repeat script `7f0667b5f3186bd3333269f2b494f01fac83a15a79dc6ffc3902b77988079eee`). Browser interaction checks remain assigned separately; byte equality does not prove desktop or mobile usability.

The Cloudflare connected app returned both exact Clef routes on 5 October, with 65,536-token context and unchanged input prices ($0.24/M for Clef; $0.09/M for Flash). This read-only catalogue check does not prove remaining daily allowance. A bounded preparation agent owns admission for an unstarted Flash fresh1/P1 smoke; no request has been sent. The manifest has 12 untouched combinations, one completed Clef fresh3/P0 and one interrupted Flash fresh3/P0. The latter still needs a separate 59-record suffix; DEV-001 must not be replayed.

## Resume checkpoint, 5 October 2026

This checkpoint supersedes the pending-analysis and unsent-Mistral statements below. Gemma has nine scored P0/P1/P2 conditions, with historical failures retained. P1 scores are 58/58/57 out of 60; all three passes score 57 on their 59 shared-valid reviews. The one-point fall comes from DEV-059's timeout. Pages run `37045652208` succeeded for `f190874d`; root fetched the live analysis script, analysis feed and P1 report and verified byte equality on 5 October. The repeat explorer update is committed as `87cbf4bf`; its deployment and real-browser checks are pending. Four focused P0/P1 UI tests pass. Root review: APPROVE, no confirmed BLOCKING or RESIDUAL findings.

Mistral fresh1/P0 has 54 valid responses, four preserved failures and two unsent reviews (DEV-059–060). The latest HTTP429 at DEV-058 retains its full $0.04177920 unknown-charge bound. Its child is sealed, with $0.000393795 known charges and $0.257827005 unused allocation released; evidence is archived in `e3c847ef`. A Sol agent owns a new offline continuation for only the two unsent reviews, with a proposed $0.09 child. No allocation or dispatch is authorized by that proposal. Root owns budget admission and execution. A separate browser-QA agent owns desktop/mobile/keyboard/reduced-motion verification; it may not change report data.

The broader requested roster remains unfinished. These milestones do not close the whole benchmark.

## Gemma DEV-060 closed; Mistral gate pending, 2 October 2026

The separately admitted [Gemma DEV-060 suffix](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p1-dev060-suffix-v1/fresh3/P1/suffix.attempts.jsonl) closed with one valid response and $0.00041054 observed cost. Its [child reconciliation](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p1-dev060-suffix-v1/reconciliation.json) retained no unknown charge and released $0.01958946 of the new $0.02 allocation. Commit `eed797b1` archives the closed suffix evidence. All 60 fresh3/P1 development positions are now accounted for: 59 valid, DEV-059 timed out with its $0.01974272 unknown-charge bound retained, and DEV-060 valid. The combined score is pending the source-bound report; this is not a clean 60-valid phase, and DEV-059 remains ineligible for replay.

Mistral's separate $0.30 child is allocated, but its DEV-054–060 suffix sent no requests. The first launch stopped at a nested predecessor source-drift gate before a phase claim. A versioned gate fix is pending independent review; do not treat the allocation as inference or retry the failed launch. The seven positions remain unsent.

## Mistral launch gate, 2 October 2026, 17:49 UTC

Root allocated a new $0.30 child and the controller retained its matching shared-authority hold. Launch handle `71186` exited with a source-drift validation error in the nested predecessor gate before creating any phase claim or sending a request. The child contains only its initial budget event. The native/preflight agent owns a versioned controller fix and regression test; no retry, release or further dispatch has occurred. The seven DEV-054–060 positions remain unsent.

## Gemma P1 interrupted and reconciled, 2 October 2026, 17:44 UTC

This checkpoint supersedes the live Gemma P1 statements in the dated entries below. The original process `31625` stopped after 59 of 60 development requests: DEV-001–058 are valid, DEV-059 timed out with no captured response and an unknown charge, and DEV-060 was never sent. The [terminal receipt](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p0-p1-composite-successor-v1/fresh3-p1-terminal-pending-review.json) and [root review](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p0-p1-composite-successor-v1/fresh3-p1-interrupted.root-review.json) bind the attempts, raw evidence and stopped journal. P1 has no third full-phase score. The [interruption note](GEMMA26_P1_INTERRUPTION_2026-10-02.md) keeps the eight scored Gemma phases separate from this partial ninth phase.

Root retained the full $0.01974272 unknown-cost bound, sealed the $0.40 child and [reconciled](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh3-p0-p1-composite-successor-v1/fresh3-p1-interrupted-reconciliation.json) $0.03995497 known charges, releasing $0.34030231 of unused allocation. The separate shared-authority hold remains $0.40. A 17:44 UTC locked [OpenRouter master ledger](../results/openrouter-paid-budget.jsonl) read showed $0.60679290250 unallocated under $12.38 and no active child; this is a dated snapshot, so the next stage must recheck the ledger and exact route. DEV-059 must not be replayed. DEV-060 is the only never-sent P1 position and needs its own reviewed admission. No new request is authorized by this checklist.

## Analysis publication confirmed, 2 October 2026, 17:25 UTC

- Pages `37039744218` succeeded for `e6d211f6`. Root fetched the live analysis script, analysis feed and Gemma P0 checkpoint; all three matched committed bytes. The newer repeat UI commit `b0776561` also deployed successfully in Pages run `37040279641`. Root fetched the live HTML and repeat script after completion; both matched committed bytes (HTML `97499ae1f43fa292a32477b3f63cd72561ad53f6dc4e79c142fdd204fea530e6`, script `53519706d32ea3c5a5213d286a55ef1b7e6c517ec016c40e2dea625b560f5129`).
- The UI agent recovered desktop verification through Helium: the selected checkpoint showed eight scored runs, P0 59/56/58 and range 56–59, the 59-review shared-valid comparison, source links and P1's missing full result. Four focused UI tests pass after the final link assertion. Mobile layout remains unverified; earlier IAB/Chrome failures did not stop terminal work.
- Gemma P1 original handle `31625` remains live; latest owner poll reported 37/60 valid outcomes, no invalid or unknown charges. No partition is sealed while the process is running.
- The hosted agent is checking whether the exact DeepSeek provider endpoint has returned and confirming Mistral's route read-only. No allocation or inference is authorized by that check.

## Repeat view verified offline, 2 October 2026, 17:22 UTC

- Root reviewed the Gemma P0 repeat-view integration: APPROVE after fixing the inherited source list and labeling the older P2 link accurately. No remaining confirmed BLOCKING or RESIDUAL finding. All 136 UI checks passed; the two focused tests also pass after those final metadata edits.
- The new selectable checkpoint shows eight scored runs, P0 scores 59/56/58, fixed-60 validity and 59-review shared-valid changes, plus usage and dated source links. Historical entries remain available.
- Live desktop/mobile/keyboard browser verification is pending: the UI agent's IAB and Chrome connections failed. No CSS or motion behavior changed. Offline interaction checks are not a substitute for visual verification.
- Pages run `37039744218` for analysis commit `e6d211f6` was still executing its static bundle checks. Verify the final deployment and live asset hashes before claiming publication.
- Gemma P1 remains on original handle `31625`; the latest owner poll recorded 27 valid responses, no invalid or unknown outcomes. No budget release or new Mistral allocation occurred.

## Gemma P0 report integration, 2 October 2026, 17:16 UTC

- Root reviewed the new P0 checkpoint builder and privacy projection; its seven tests and exact feed rebuild pass. P0 fixed-60 all-four scores are 59/56/58 with validity 60/59/60. Shared-valid comparisons explicitly use 59 records; fresh2 DEV-002 remains failed.
- The analysis refresh includes the new checkpoint and 88 direct source hashes. Two analysis tests and three analysis UI tests pass. README, coverage inventory and current goals reflect eight scored runs; the repeat-view integration is under final review.
- Fresh3/P1 full development remains live under the roster execution owner's handle `31625`; the latest poll reached 18 valid outcomes with no invalid or unknown result. The $0.40 child remains active.
- Public deployment is not yet verified for this checkpoint. Root owns commits/publication, the native-preflight agent owns the repeat UI, and the hosted agent reviews the combined analysis.

## Gemma P1 full run admitted, 2 October 2026, 17:08 UTC

- P1 smoke process `51253` exited zero with three valid responses, no unknown charges and $0.00091939 observed cost. Root inspected all three final raw answers and verified the ordered request, journal and wire bindings; the smoke was accepted unchanged.
- Root admitted fresh3/P1 development on the same reviewed successor and $0.40 child. The roster execution agent owns fresh route/budget checks and the single launch. No new allocation, retries or model substitutions are authorized.
- Provider DEV-001 reported 587 reasoning tokens and 549 completion tokens. Preserve both measurements and flag the inconsistency; do not sum them.
- P0 analysis is being prepared separately. The README now distinguishes the seven-run published cutoff from the newly closed third P0 and P1 smoke.

## Gemma third P0 closed, 2 October 2026, 17:04 UTC

- Original process `22047` exited zero. Root independently verified all 60 ordered DEV-001–060 outcomes, the exact phase journal, and raw/wire bindings: 60 valid, no invalid or unknown outcomes, $0.01918032 observed development charges.
- The shared $0.40 child remains open for P1, with $0.02002689 accounted including the P0 smoke and no pending reservation at closure. Do not seal it prematurely to fund another model.
- Root admitted only the fresh3/P1 three-record smoke through the unchanged successor and same child. The roster execution agent owns fresh route/budget checks and dispatch. Full P1 still requires independent raw smoke inspection.
- The hosted reporting agent owns a new source-bound P0 checkpoint and eventual separate P1 cutoff. Existing feeds remain frozen because execution admission binds them. Publication of the new P0 result is pending.

## Mistral continuation reviewed, 2 October 2026, 16:59 UTC

This checkpoint supersedes earlier running-state and admission statements below.

- Root independently reviewed the Mistral DEV-054–060 controller and inherited request lifecycle: APPROVE, with no confirmed BLOCKING or RESIDUAL finding. Six offline tests passed and the frozen manifest verified as `b0155804970144d421dfd9f633a5b26c232fda3b060c0fee0aef1975756c8aab`.
- No Mistral dispatch is admitted yet. The locked OpenRouter audit found $0.26649059250 unallocated against a proposed $0.30 child. Gemma's $0.40 child is still active. Reconcile its terminal evidence before deciding whether unused funds can cover Mistral; do not raise the cap or release unknown charges.
- Gemma's fresh3/P0 stage remains owned by the roster execution agent on handle `22047`; the latest live poll reached 43/60 saved valid responses. P1 is not admitted.
- DeepSeek's exact `open-inference/fp4` route was absent at fresh admission. No successor allocation or request occurred; the public endpoint snapshot and failure receipt are archived in `f4e750ab`.

## Third-P0 reporting and hosted continuation, 2 October 2026, 16:35 UTC

This checkpoint supersedes earlier assignment and running-state statements below.

- Root verified and pushed `b73487d0`: Clef's third P0 checkpoint and the Gemma fresh3 P0/P1 successor. Four report tests and eight successor tests passed. The budget fix binds the global hold to one exact child manifest, partition and ledger; a second child cannot reuse it.
- Clef: three P0 passes each scored 53/60 with 60 valid outputs, and no observed label, probability or confidence changes. Flash: two completed P0 passes; its third has one unknown outcome and 59 never-sent inputs. Further Cloudflare dispatch remains stopped. The hosted report agent owns integration of this dated checkpoint into analysis and repeat views.
- Gemma: root inspected all three fresh3/P0 smoke wire captures and final outputs. They are valid, with $0.00084657 observed cost. The roster execution agent started the separately admitted full P0 stage on handle `22047`, after fresh checks, using the same $0.40 child. P1 remains unadmitted. The closed publication still contains seven of nine phases; a live process is not a completed phase.
- Fastino: root reviewed the offline GLiNER2.5-Decide request manifest and three tests passed. Public catalogs now list $0.03/M input and zero output price. Missing credentials, unverified account access and complete-input token fit remain gates. No inference or budget allocation occurred.
- DeepSeek: the native-preflight agent owns a new versioned price/suffix admission for never-sent DEV-051–060, reviewed and committed in `8581d0f2`. Root admitted only those ten never-sent positions, but the fresh route check found no `open-inference/fp4` endpoint. Dispatch stopped before allocation, hold, claim or inference. The route snapshot and blocker receipt preserve this observation; no provider was substituted. Earlier failed requests must not be replayed.
- Website: category explanation `de9f9aa7` was included in successful Pages `37034747473` at `b2490a28`. Clef third-pass integration `bd336a5b` is pushed with 134 UI checks, two analysis tests and a browser content check passing; Pages `37035178875` succeeded, and root verified the live HTML, repeat script, analysis script and analysis feed byte-for-byte against `bd336a5b`. The existing category filters separate model specialization from output interface and hosting route.


## Published repeat findings and remaining-route preparation, 2 October 2026

The two source-bound repeat reports were published in `2deb6958`; Pages `37031477144` passed and both live feeds matched their committed bytes. Integration `1a30318e` adds Gemma's 2/57 shared-valid P2 changes and the separately dated Clef two-pass comparison. Root verified all four deployed HTML/script/feed assets against local bytes after deploy step success in `37032352052`; 132 UI tests, two analysis tests and browser checks passed. The first-pass Clef panel now explicitly names its historical cutoff and links the two-pass report.

Closed Clef fresh3 evidence and the Flash unknown-outcome/error audit are archived in `ec3bb8ef`; no further Cloudflare request is running. The hosted agent owns a separate third-P0 checkpoint report, preserving the earlier cutoffs. The roster agent is independently reviewing the proposed Gemma fresh3 P0/P1 successor's budget and order safeguards. No Gemma allocation, grant or inference has occurred. The native agent owns Fastino GLiNER2.5-Decide access, price and input-fit preflight plus offline adapter preparation; no paid smoke is admitted. Other unverified direct decision routes remain in the full roster.

## Third Clef P0 admission and repeat-analysis review, 2 October 2026

Root decoded and independently inspected all six fresh3/P0 smoke responses, checked response hashes, returned model IDs and parsed choices against the raw native answers. Each model has three valid smoke outputs. The roster agent owns the separately admitted 60-review fresh3/P0 stages for Clef and Clef Flash, with fresh route, price and account checks and atomic holds under the existing shared ceiling. No P1/P2 stage is admitted by this checkpoint. Clef fresh3/P0 has since closed with 60 valid responses; root verified terminal hashes and ordered IDs (completion SHA `e3382b7c6d6e86ba95509b56ac9e4494c932c975ca517aef1e0d7fc84b8db140`). Flash fresh3/P0 stopped sending after its first connected-app call returned Cloudflare error 4006: the daily free allocation is exhausted. The saved outer result is an error with plain text, not a provider response envelope; no response is fabricated and no retry is allowed. The original handle `68806` exited after its bounded timeout: one unknown outcome, zero valid responses (completion SHA `58ef1847646e705ae93db2339fbd52b6f49aa8e727fae28523f93478ed2c0878`). DEV-002–060 remain unsent and the full-stage hold stays reserved. Cloudflare documents reset at 00:00 UTC; no paid-plan upgrade has been made. Neither stage is part of the two-pass report cutoff.

The hosted agent is independently reviewing the new Gemma P2 three-pass analysis; the native agent is independently reviewing the Clef two-pass P0 analysis. Neither report is published yet. Root owns integration and publication after review. The proposed findings retain fixed-60 scores and shared-valid denominators separately. The previous publication and local AC-power blocker remain as recorded below. Both reviews returned APPROVE after the new Clef report replaced an unsupported negative adjudication claim with the confirmed human-check history. Follow-up: the frozen first-pass Clef feed still contains the old wording; correct it through a versioned report revision and refresh dependent source bindings, without changing scores or raw evidence.

## Report integration and second Clef passes, 2 October 2026

Both Clef fresh2/P0 stages are archived and pushed in `dd1220aa`, each with 60 valid outputs. Root independently checked completion hashes, ID order and reference exclusion; the archive scan found no credential or account-ID values. The hosted agent owns a separate two-pass findings report. The reviewed remaining-stage controller and deterministic budget fixtures are pushed in `b28fecc5`; 13 tests pass. Root admitted only the two fresh3/P0 three-record smokes, each requiring fresh account, route, price and atomic budget checks. Full development remains gated on independent raw-response review.

Gemma's seven-of-nine snapshot, costs and token missingness are integrated with the combined analysis and repeat view in `46a4b91e`. All 132 UI tests and 10 focused Python tests pass; 66 analysis and 108 Gemma source hashes match the staged archive. Desktop and 390px mobile checks show the 56–57 P2 range, two unsent conditions and partial cost coverage. The native agent owns offline three-pass P2 answer-change analysis. Pages `37029427985` succeeded. Root verified the live HTML, repeat script, analysis script/feed and Gemma feed byte-for-byte against the committed integration. The earlier Qwen report deployment `37027936864` succeeded and its live feed matches committed bytes.

Next local 1.7B thinking-on phase is fresh1/P2. Its preflight stopped before a claim or inference when the Mac switched to battery power. AC power and fresh route/host checks are required before resuming that smoke. No local process is left running by that stop.

## Clef second pass and larger Qwen checkpoint, 2 October 2026

- The three model-category filters and validity/agreement chart are published. Category provenance and the Cloudflare visual reference are documented in [the category review](REPORT_CATEGORY_REVIEW_2026-10-02.md). General models, task-fine-tuned checkpoints, and dedicated decision models stay separate from interface and hosting route.
- Qwen3 1.7B SDK thinking-on first P0 pass is closed: 60/60 valid responses. Its three-record smoke, controls, request hashes, exact local artifact and host checks are archived and pushed in `49a730c7`. The native agent owns the offline report refresh. No later 1.7B phase has been dispatched.
- Gemma's interrupted third P2 sequence now has 58 valid outputs and two preserved service failures across all 60 positions. It matches all four frozen reference fields on 56/60 reviews. The new seven-of-nine-condition report is committed in `8bbf3f0b`; six focused tests pass and all 108 source bindings match the archive. The hosted agent owns combined-analysis integration; the native agent will own repeat-view integration after the Qwen refresh. Third P0 and P1 remain unsent.
- Clef's second P0 pass has closed with 60/60 valid native responses. Its evidence is under the roster agent's verification and archive ownership. Both three-record smokes passed independent raw-response review. Clef Flash's second full P0 pass is authorized separately after fresh billing and atomic budget checks; its result remains pending. Further Clef phases are not dispatched by this checkpoint.
- These are progress checkpoints, not completion of the full model, prompt and repeat roster. Older sections below preserve historical cutoffs.

## Small-Qwen SDK studies closed, 2 October 2026

Both Qwen3 0.6B SDK setups now have all nine full P0/P1/P2 phases closed, alongside the nine completed HTTP phases. The final thinking-on P2 run saved 58 valid and two invalid outputs; thinking-off saved five valid and 55 invalid outputs. Raw responses, strict-parser failures and the between-stage host sleep remain preserved. The separate host rebaseline passed before and after both final runs. Thinking-on P2 scores across passes were 3/60, 1/60 and 1/60; 47 of 52 reviews valid in all three changed at least one label. Thinking-off has no shared-valid three-pass set for any prompt. Evidence, report, README and roster updates are committed in `a6ae6c77`. The release initially caught a stale UI-test assumption that SDK studies were incomplete; `1e28fbcb` corrects it. All 129 UI tests pass. Pages `37025068303` succeeded, and the live repeat feed matches committed bytes. The three larger legacy configurations remain pending.

Gemma's seven-record continuation completed and is archived in `ba4efcd3`. All seven responses are valid, with $0.00331689 new charges. Its existing child is sealed at $0.00575783 known total, zero unknown and $0.29424217 released to the OpenRouter master; the separate global carry remains retained. Third-pass P2 now accounts for all 60 positions, including the original DEV-005 and DEV-006 failures. The hosted agent is preparing the combined descriptive report; third-pass P0 and P1 remain unsent. Clef's reviewed fresh2/P0 controller is committed in `aaa3d2e6`; the report agent is authorized for the two separate three-review smokes only, with exact fresh route and billing-byte checks. Full development still requires independent inspection. The native agent is checking the installed 1.7B model for the next frozen smoke; no inference is authorized by that load check.

## Publication and continuation checkpoint, 2 October 2026

- The category filters, comparison chart and both Clef first-pass result cards are published. Pages run `37019450511` succeeded; root fetched `app.js`, `index.html`, `clef-first-pass.css`, `clef-findings.json` and `model-categories.js`, and each matched committed bytes. The mobile label fix in `7b134ada` is also published: Pages `37022452727` succeeded and the live stylesheet matches committed bytes.
- Qwen SDK thinking on and off each have eight of nine full phases archived. Third-pass P0 findings are published in `3194a83d`; thinking-on P0 had 0/60 complete matches in each pass, while all five shared-valid reviews changed at least one label. Both final P2 smokes were independently inspected and approved. Neither final full phase was sent before a host-sleep preflight stop. Root reviewed a separate host rebaseline after confirming AC power, open lid and unchanged runtime. The native agent started thinking-on final P2 under lock and caffeinate (handle `69923`); thinking-off follows only after closure and a fresh check. The old sleep evidence and frozen model controls are preserved.
- Gemma's final suffix saved DEV-047–053: seven valid responses with $0.00244094 reported charge. A catalogue lookup timed out before DEV-054; DEV-054–060 remain unsent. The process is terminal, and its existing $0.30 allocation remains active with no pending request reservation. The hosted agent owns a separately reviewed seven-record continuation; rerunning the claimed stage is prohibited.
- The [Clef continuation proposal](CLEF_REPEAT_ADMISSION_2026-10-02.md) lists all 16 remaining model/pass/condition combinations, with separate smokes. Root verified its 12 source bindings and all 32 unsent smoke/full request sets. The next paired stage fits the current authority, but the complete remaining matrix's conservative holds exceed it by $3.163076. This is a reservation requirement, not an observed bill. No continuation is dispatched by this proposal.
- The roster agent owns a dated update to the coverage inventory. Historical cohorts stay separate from these new full passes and interrupted continuations. The complete project remains unfinished.

## Closed Clef and second-pass checkpoint — 2 October 2026

- Clef and Clef Flash each finished 60/60 valid native P0 responses. Evidence is archived in `11c50cfe`; the [analysis](CLEF_FINDINGS_2026-10-02.md), builder and tests are pushed in `7701eedb`. All-four agreement is 53/60 and 45/60. All 625 report source hashes resolve to committed files. Input-price estimates total $0.04378902; provider charges and pure inference latency remain unavailable. Only one P0 pass per model has run; native instruction variants and repeats remain pending.
- The interactive validity/agreement chart is pushed in `6b90b3b5`, with all 125 UI tests passing and desktop/mobile/keyboard checks. It uses the same merged saved-run collection as the explorer, including Sonnet 5.5. Clef's public explorer integration is assigned to the report agent. Category deployment `37014648466` and chart deployment `37017406040` succeeded; each checked live asset matched committed bytes.
- Both small Qwen SDK setups have seven of nine full phases archived: two complete P0/P1/P2 passes plus third-pass P1. The feed and analysis are pushed in `69ad7917`. Thinking-on P1 scores were 1/3/2 out of 60; 36/40 shared-valid reviews changed at least one label. Third-pass P0 smokes are assigned to the native execution agent. Format failures stay in the results.
- Gemma DEV-017–046 finished with 30 valid outputs and $0.01109214 known charge, no unknown charge. The sealed evidence is archived in `8bb5c035`. The hosted agent is preparing the remaining DEV-047–060 admission; no final-suffix request has been sent. The global postapproval ledger keeps the old $0.60 carry conservatively, alongside Cloudflare holds; it is not released from token-price estimates.

## Category and repeat-analysis checkpoint — 2 October 2026

Model-category and output-interface filters are committed in `54ff76e0`, with the initial-selection fix in `4b2ede7e`. All 121 UI tests pass. Pages publication is being verified. The [category review](REPORT_CATEGORY_REVIEW_2026-10-02.md) records Cloudflare design references and source-backed model assignments.

Both small Qwen SDK settings now have four of nine full phases archived, including fresh2/P2. The updated findings and feed are committed in `61a73e30`: thinking-on P2 changed at least one label on 45 of 54 shared-valid reviews; thinking-off had no shared-valid reviews, so stability is unavailable. Fresh2/P1 smoke inspections passed independent review, and full phases are authorized serially. Gemma's fifth hosted continuation remains active under root session32610. Clef full-run accounting and controller preparation continue; six smoke calls are complete, no full Clef phase has run.

## Live Clef checkpoint — 2 October 2026

Clef and Clef Flash each completed the three-record P0 smoke through the connected Cloudflare app: six valid responses, retained native choice distributions, 6,628 input tokens per model and zero reported output tokens. Root checked raw choices and completion hashes; evidence is archived in `3ef70aa0`. Published input rates imply $0.00218724 combined, but observed charges remain unavailable and the $0.064884 full-context hold is retained. The live app route works; the direct environment token's earlier HTTP403 remains a separate observation. Full 60-record stages and shared accounting under the user's new $10 overall approval are being prepared; no full Clef phase has run.

Both Qwen SDK settings now have a complete first pass of P0/P1/P2. The findings are pushed in `f029b405`; Pages `37012485162` succeeded. Second-pass P2 work continues separately. Gemma's fifth hosted continuation remains assigned to root session32610. Model-category controls and Cloudflare-inspired chart review are assigned to the report agent.


## Current checkpoint — 2 October 2026, SDK P2 and new Cloudflare approval

- SDK P2 thinking-on/off full phases are archived in `cb0fabcb` and `85708a2d`. Thinking on returned 56 valid responses and 3/60 complete matches; thinking off returned one valid response and 0/60 complete matches. Invalid outputs remain unchanged. Reporter, README and findings updates are pushed in `0627b6ea`; Pages publication is still being verified.
- SDK fresh1/P1 smokes were independently inspected and approved under the existing successor policy; full runs are delegated serially to the local execution agent.
- Gemma DEV-017–046 is admitted through the reviewed fifth continuation, with a $0.60 child reserved within the existing OpenRouter cap. Root owns live session 32610. No completed or failed request is replayed.
- The user approved tests and live runs up to $10 overall in the current discussion. The first Cloudflare admission will remain limited to the reviewed $0.10 smoke stage. The shared environment token returned HTTP403 on Workers AI discovery; connected-app discovery works. The hosted agent is preparing an app transport that retains the runner's durable reservations and evidence before inference. No Clef request has been sent.
- The report research agent is reviewing Cloudflare's evaluation site and proposing evidence-backed model categories and charts. General-purpose, task-tuned and dedicated decision models must remain distinct from the API output format.


## Current checkpoint — 2 October 2026, after SDK first-pass archival

This checkpoint supersedes older running-state statements below.

- **Qwen SDK — execution:** thinking-on and thinking-off each saved all 60 fresh1/P0 responses. Strict parsing accepted 27 and 1 respectively; 33 and 59 format failures remain unchanged. The closed evidence and route audits are committed in `9d89c001`. Root has delegated the next scheduled fresh1/P2 smokes, serially, with independent inspection required before full development runs.
- **Qwen SDK — reporting:** the reporting agent is adding source bindings for the separately reviewed admission policy. These new full phases are not yet published in the findings feed.
- **Gemma hosted:** the DEV-007–016 continuation process exited successfully. The hosted agent is checking its terminal evidence and reconciling its budget partition before archival. No further hosted requests are dispatched by this checkpoint.
- **Cloudflare Clef:** the connected app can list the account and both exact model routes. Existing shared environment credentials are available; inference permission is not yet demonstrated. The runner is being updated to accept the existing variable aliases. The separate $0.10 smoke allowance remains pending; no Clef inference has been sent.
- **Website:** model-family and effort filters, repeat-study search and coverage filters, and comparison-section navigation are published and byte-verified in `a33187b9` / Pages `37008242107`.


## Restart recovery and analysis refresh — 2 October 2026

The forced restart interrupted the analysis/publication work, not a running model request. The completed Sonnet study remains published. The offline analysis refresh, website section and tests survived locally and are committed/pushed in `19dc646e`. Its 62 source bindings, 12 focused Python tests and 116 UI tests pass; independent review approved the corrected report. [Pages publication 36998863739](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36998863739) succeeded. Root verified all six changed live assets against committed bytes. The user resumed the updated app goal; its active attachment matches [APP_GOAL.md](APP_GOAL.md). The approved cap is $12.38. No completed inference is to be replayed.

## Resumed execution preparation, 2 October 2026

The separately reviewed Mistral DEV-051–060 continuation is terminal and preserved in `1251dcac`. DEV-051 and DEV-052 returned valid responses; DEV-053 hit HTTP 429 from the upstream shared pool; DEV-054–060 were never sent. Its child is sealed with $0.00047715 known charges, $0.04177920 retained unknown-charge bound and $0.20774365 released. Across the original phase and two continuations, 50 responses are valid, three positions failed or remain unknown, and seven are unsent. The phase is unscored; no failed request was replayed. The locked master now has $0.68739575250 unallocated and no active child.

Qwen3 0.6B HTTP nonthinking now has all nine fresh P0/P1/P2 phases closed: 540 development responses and 27 smoke responses, all schema-valid. Completion hashes and ordered IDs were verified; the final pass is archived in `5ac1b94e`. Every phase has 0/60 four-field matches, with identical predictions across the three passes within each prompt. See [field-level findings](LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md). This exact model had no OpenRouter catalogue match at each admission. The other five legacy configurations remain without full phases. SDK thinking-on now passes exact load controls, but its smoke saved two fenced, invalid outputs and one valid output; the frozen gate refused development. That evidence is archived in `b215a295`, with no output repair or replay. The distinct SDK thinking-off smoke also stopped after three fenced, invalid outputs; evidence is archived in `9d605d55`. A separately versioned admission policy is under preparation for both SDK configurations, preserving the strict parser while allowing reviewed intrinsic format failures to proceed to full measurement. No SDK development request has been admitted.

## Latest execution checkpoint — 2 October 2026

The host is awake again. The separately admitted Mistral DEV-049–060 continuation is closed and preserved in `48c8d62a`: DEV-049 returned a valid response; DEV-050 hit the provider's shared-pool HTTP 429 limit; DEV-051–060 were never sent. This was not an account-balance rejection. The child is sealed with $0.00023835 known cost and $0.04177920 retained unknown-charge bound. The original DEV-048 timeout is unchanged. No failed request was replayed.

Sonnet 5.5 low/medium/high/xhigh has completed all 36 full phases: three separate passes of P0/P1/P2 at each effort, or 2,160 classifications of the same 60 reviews. Root verified every frozen manifest and closed development phase. The first smoke's old-allowlist failure remains preserved; the reviewed v2 continuation did not replay it. The final [analysis](SONNET55_FRESH_MATCHED3_FINDINGS_2026-10-02.md) and sanitized evidence are published in `6e563a98`, with release-test fix `eda53919`. [Pages 36993821176](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36993821176) succeeded; six live assets, including the findings and evidence report, match committed bytes.

Lower-page run selectors, cache-aware API-equivalent subscription estimates and the user-confirmed reference-checking correction are live in `4efe38ff` (Pages `36989523124`). The broader historical-to-matched-series links and Sonnet integration are also live and byte-verified. See [website verification](WEBSITE_RESOURCE_UPDATE_2026-10-02.md).

No OpenRouter child is active. After the closed Mistral continuation, the aggregate ledger retains $0.72965210250 of unallocated capacity under the approved $12.38 cap. This includes retained unknown-charge bounds and differs from the account's displayed credit. The upstream Mistral 429 was not a funding rejection. Remaining Mistral, Gemma, DeepSeek, Solar and specialist work is not completed by the Sonnet result; the dated roster and preserved failures still apply.

The older checkpoints below are historical, including their host-sleep blocker and balances.


Historical checkpoint from 1 October 2026. The 2 October sections above supersede its process, budget and publication status. Frozen manifests and saved responses establish execution status; this checklist does not authorize spending or change the experiment protocol. See [current goals](CURRENT_GOALS.md) and the [detailed roster](REMAINING_ROSTER_2026-09-29.md).

## Historical assignments, 1 October 2026

Execution checkpoint, 1 October 2026, 07:48 UTC: website editorial revision is published and verified in `c313c2b2` / Pages `36831802703`. Fresh host evidence shows additional Maintenance Sleep intervals at 07:16:03 UTC (238 seconds) and 07:20:46 UTC (174 seconds), followed by maintenance DarkWake at 07:23:40 UTC; the lid remains closed. The repeated host-sleep barrier still prevents admitting the prepared Mistral suffix. Locked ledger replay: cap $12.38, accounted $11.60833034750, unallocated $0.77166965250, zero pending reservations and zero active children. The next $0.25 stage fits; no top-up is needed for it. Execution remains unfinished. Resume after a full host wake, with fresh route, process and budget checks; do not replay DEV-048.

Checkpoint: 1 October 2026, 06:23 UTC. Earlier statuses are retained in [coordination history](COORDINATION_HISTORY_2026-10-01.md). Counts below are observations, not permission to replay a request.

- **Qwen medium, publish_on_triple / root:** original P1 handle `9766` exited successfully with all 60 valid responses. Root independently verified its frozen manifest and strict closure hashes. Child sealed: $0.089620125 known charges, no new unknowns, $0.210379875 released. Closed evidence is committed in `a2b2d08a`. All nine scheduled conditions now have accounted positions, retaining the original DEV-022 P0 timeout. A separate final interrupted-composite reporter is in preparation; this is not clean matched-three evidence.
- **Qwen xhigh, publish_on_triple:** second-continuation fresh3/P1 suffix is terminal: all 52 responses are valid, joining the earlier eight valid P1 responses. Its child is sealed with $0.047987850 known charges and $0.252012150 released. Closed evidence is committed in `861c9084`. All nine scheduled conditions now have accounted positions, but the P0 composite retains DEV-037’s original timeout and is not a clean matched-three series.
- **Gemma26, root:** third-continuation handle `86569` is terminal. DEV-006 returned HTTP 429 from DeepInfra's shared upstream pool (`engine_overloaded`), not an account/key quota response. No retry occurred; DEV-007–060 remain unsent. The child is sealed with zero observed charges and a retained $0.01974272 unknown-charge bound. The sanitized terminal record is committed in `b3ffd706`. Fresh3/P2 remains unscored, with DEV-005's earlier timeout also preserved. Fresh3/P0 and P1 remain unstarted.
- **Solar Decide, root:** reviewed native P0 smoke ran on original handle `67561` and is terminal. DEV-001 returned upstream HTTP 429 request-limit wording; DEV-002/003 were never sent. No development request ran. Billing was absent, so the child retained $0.02621440 unknown bound and released $0.05242880. No retry or substitution occurred. [Sanitized outcome](../results/solar-decide-native-smoke-v1/terminal-public.json).
- **Public result integration, publish_on_triple / root:** historical Qwen/Gemma/DeepSeek cutoffs are live (Pages `36821195110`, root byte-verified). New Qwen final-pass P0/P1 comparison is live: Pages `36825062217` succeeded and root byte-verified the HTML, repeat UI and findings feed. It passed independent browser review and 93 UI tests. The full nine-condition reporter is committed in `e4ee58d5`; all 266 source bindings verified in a clean archive. Public integration `a7f6cb42` and reader link/cache `c23dce58` passed independent review and 95 UI tests; Pages `36826600260` succeeded; root verified identical live HTML, repeat UI and Qwen findings feed bytes. Original errors remain visible.
- **Website, root:** Reader revision `7882b755` and clarity follow-up `8c6f85cd` are live. The follow-up passed Pages `36825937756`; live HTML byte-matched the commit. Pages run `36819083251` succeeded; four changed assets match the commit byte for byte. Desktop, 390px mobile, keyboard, interactive chart and reduced-motion checks passed. The historical result integrations above are also live; final newly closed Qwen composite analysis is still in preparation.
- **Budget, root:** OpenRouter cap $12.38, TypeSafe $1 separately. Locked master check: $11.60833034750 accounted/encumbered, $0.77166965250 unallocated, no pending master charge and no active child. Accounted includes allocations and retained unknown bounds, not only provider charges. Gemma, Solar and both Qwen children are sealed; released capacity is available for independently reviewed next work.
- **Mistral119 none, native_variants_prepare / root:** original separate protocol-smoke handle `1302` exited successfully. DEV-002–004 all returned valid expected-model/provider responses; root inspected raw outputs and froze [inspection](../results/repeatability-v1/mistral119-fresh-matched3-v1/v3-protocol-smoke-none-v1/smoke.inspection.json). Known charge $0.000337980; smoke child sealed and $0.124999620 released. Root-reviewed first P0 handle `17315` is terminal exit 1: 47 valid responses, DEV-048 timed out, DEV-049–060 never sent. The Mac slept for 934 seconds during request 48; client timing is affected. The child is sealed: $0.003737190 known charges, $0.04177920 retained unknown bound, $0.204483610 released. Closed evidence is archived. The unsent-only continuation controller is committed in `6f13daa6`, independently approved, with eight offline tests passing. Each phase uses a separate budget manifest. No failed request is retried and no later stage is admitted. Historical DEV-001 failures remain unchanged; smoke earns no repeat credit.
- **Local execution, root:** held after sleep and thermal interruptions. Fresh read-only check still reports the Mac lid closed and AC power connected. No power safeguards changed. E4B P2 keeps 50 valid positions, timeouts at DEV-039/052 and eight unsent positions. Qwen3.5-4B's earlier smoke retains its load-config failure; the offline SDK diagnosis is preserved. Neither has a newly admitted request.
- **DeepSeek low, root:** the saved third interruption remains an upstream shared-pool 429 at DEV-050, with 46 valid, one invalid, three failed and ten never-sent positions. Its portable reporter is committed; no new recovery request has been sent.

- **Jev confidence analysis, native_variants_prepare:** offline source-bound analysis of saved native P0/P1/P2 confidence is committed and pushed in `8b5a590b`. Independent review approved all counts and 25 source bindings; five stdlib tests and clean-archive parity pass. Pages `36827483195` succeeded; root byte-verified the live HTML and confidence feed. No inference or new spending; invalid responses stay excluded with fixed-60 counts, and hypothetical withholding is not an executed policy.

- **Mistral next admission, root:** the exact DEV-049–060 suffix manifest is frozen and verified in `5b56c2c0`. Proposed child $0.25 fits current $0.77166965250 unallocated capacity (leaving $0.52166965250 while allocated). No top-up is required for this next stage. No child or execution receipt exists. Current maintenance DarkWake with lid closed remains an execution blocker; existing idle assertions did not prevent the preceding Sleep Service interruption.
- **GLiNER hosted contract, gliner_hosted_prepare:** the [hosted adapter contract](GLINER_HOSTED_ADAPTER_CONTRACT_2026-10-01.md) is complete. Official request syntax is documented, but the inner four-head response shape, policy behavior, full-token fit, account entitlement, bounded bill and hosted revision remain unverified. Root confirmed the current catalog/OpenAPI entry and DEV-001 sample. No model call or download occurred.

## Verified progress

- [x] Website editorial revision: Academy voice, findings before rankings, audience-specific guidance and expandable detailed analysis implemented and checked locally. See [the revision and verification notes](WEBSITE_EDITORIAL_REVISION_2026-10-01.md). Published in `c313c2b2`; Pages run `36831802703` succeeded. All six changed live assets match the checkout, and the live mobile deep link was checked. No inference was dispatched for this presentation work.

- [x] SemIf generated first P0/P1/P2 pass published in `0184bb6d`. Pages run `36756829330` succeeded; public HTML and 3/9 feed match committed bytes. All-field agreement is 35/60, 26/60 and 43/60 respectively, with 8, 22 and 2 invalid outputs retained. Desktop/mobile field selection and keyboard focus were checked on the preceding UI version; the latest data changes passed UI tests. Fresh2/P1 execution continues separately.

- [x] OpenJev generated-on fresh1/P2: 60 saved responses, 52 valid and eight retained invalid outputs. Root verified completion hashes. Closed evidence and the fresh2/P1 smoke are saved in `69be3266`; the first P0/P1/P2 generated-on comparison is now public in 40c20a03.
- [x] Ruflo checkpoint save-back verified in both canonical databases; identical content SHA-256 `709cc8aa9a0b320e6af37b834774e6f4088208fce3b79e6884ba3e3fe638c83c`.

- [x] Website deployment 36731918630 succeeded for be554f15; live HTML, navigation, stylesheet and generated report hashes match the commit.
- [x] OpenRouter native smokes: Jev 3/3 valid, $0.000294294; Kev 3/3 valid, $0.000234864. These are protocol checks, not full benchmark scores.

- [x] OpenJev generated-off: all nine full phases closed; 540 attempts saved, 491 valid and 49 retained invalid outputs. The execution agent verified the pinned plan and completion hashes. Publication is a separate task above.
- [x] Primary-source decision-model route audit written: [report](DECISION_MODEL_ROUTE_AUDIT_2026-09-30.md). No inference was performed by that audit.
- [x] Existing Claude and Codex repeat groups completed as listed in the detailed roster. Do not dispatch them again.
- [x] Project `.env` exists with mode 0600 and is ignored by Git. Never include credentials in source, evidence or memory.

## Remaining execution and blockers

- [x] AnyJev generated P0/P1/P2 execution is closed at 9/9, with intrinsic invalid outputs retained. SemIf generated is also closed at 9/9. Final AnyJev publication is live at a6900d3b.
- [ ] **Generic local execution:** the detailed roster and public small-local report confirm E2B off/on and E4B off at 9/9. E4B on remains 4/9 with the interrupted P2 outcomes above. Qwen3.5 off remains pending in the small-local matrix. In the separate legacy Qwen matrix, HTTP nonthinking 0.6B and SDK 0.6B/1.7B thinking-on/off are each closed at 9/9; Qwen3.5 4B thinking-on is the sole unfinished configuration, with its first P0 development pass running under root handle 35256. Refresh exact hosted availability and local runtime/cache/host readiness before admission. No download is authorized by this checklist.
- [ ] Finish the remaining hosted Qwen, Gemma, DeepSeek, Mistral and Gemini configurations listed in the detailed roster. The user approved an additional $2.38 on 30 September, and the [master ledger](../results/openrouter-paid-budget.jsonl) now records the $12.38 cap. Use the latest dated locked-budget checkpoint; the 1 October assignments below are historical. The proposed $17 total remains unapproved. TypeSafe retains its separate $1 cap.
- [ ] Admit new decision models individually after exact route, interface, account access, price and context checks. A vendor's free preview listing does not establish account access. Preserve native probabilities separately from generated-letter logprobs. The 30 September check found no conventional Liquid, Upstage, Alibaba/DashScope, Together, Nace/Drex, Fastino or Cloudflare credential variables in this project's `.env` or the current process environment. This does not establish whether credentials exist elsewhere; direct-provider access remains unverified. OpenRouter Jev/Kev access is verified by their saved smokes.
- [ ] Resolve reference-review items with human adjudication where required. Preserve frozen labels and original scores.
- [ ] Finish full roster reconciliation and publish completed, failed, unsupported and blocked dispositions. The overall MVP is not complete merely because one repeat series is finished.

## Memory and ownership

Use Ruflo decision entries for approvals and verified checkpoints, and ReasoningBank patterns for reusable learnings. Verify shared persistence; a successful store response alone is insufficient. The repository remains the evidence archive, not the memory database. The separate private classification-bench project belongs to its own user-started task.

- [x] **AnyJev generated publication — root / publish_on_triple:** Commit [61845b14](https://github.com/adambkovacs/candidate-experience-benchmark/commit/61845b140e67d900e6aed32a456929c560ab9f9c) publishes the first P0/P1/P2 pass (3/9 planned full phases). [Pages run 36768534384](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36768534384) succeeded. Live HTML, generated feed and repeats.js match committed bytes; SHA-256 respectively `5e64d669b0bbd9978873b8b88baf01b4c136c184cb06e2a90c5763f5155bb5c1`, `020de953ae4969653abccc2fb1a3e65887c4bad663600aef4fe6748ecc307d9c`, `e9e6874012d53bb72d50d3b8a82866152526deb94a7446bbc3e52588f6daf020`. Independent review approved; root checked desktop, 390px mobile and keyboard field selection. Later completed repeats remain separate from this published cutoff.

- [x] **AnyJev five-phase publication — root / publish_on_triple:** [a87394b8](https://github.com/adambkovacs/candidate-experience-benchmark/commit/a87394b8fc99b2d10b35b956bfe52e0bbb0eb75f) is live; [Pages run 36770420566](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36770420566) succeeded. Public HTML, AnyJev generated feed and repeats.js match the commit byte for byte. SHA-256 respectively `f714c29e9dc04e54b65d0a5da75b3043062ed11766eea7dac7f33f3414a1da15`, `fe8affbf9d9c15b99697ace581871d7a87cc26e14c073dbef9b84255528b3a8d`, `0683a7b050e7f28c39e3442067f949eef050fa354d37d3f8aa1238003dc57ab2`. The public cutoff is five closed full phases; later evidence stays separate.

- [x] **Pending small-local route preparation — root:** [20:09:56 UTC catalog audit](../results/route-audits/small-local-admission-20260930T200956Z/catalog-audit.json) checked 464 OpenRouter models across ID, name, canonical slug and Hugging Face identity, finding no exact E2B/E4B/Qwen3.5-4B family match. Raw catalog is preserved. The exact configuration `gemma4-e2b-sdk-thinking-on/fresh1/P0` subsequently passed root runtime and lock checks; its separate smoke is now admitted.

- [x] Final AnyJev fresh3/P1 smoke: root inspected all three intact fenced responses, retained their strict-parser failures, and verified the pinned predecessor and artifact bindings. The separate full-stage receipt is approved; final development execution is assigned to resume_generated. No final full result is claimed yet.

- [x] Final AnyJev generated publication: Pages [36774662260](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36774662260) succeeded for `a6900d3b`. Public HTML, AnyJev feed, repeats.js and small-local feed match committed bytes. AnyJev feed SHA-256 `b4c5a867a5bb5916c24d99977451c83a1366dfd34f8bc0a3515b57b3a64e8d20`. All nine generated phases are public; native readouts remain separate. Desktop, 390px mobile, keyboard disclosure and reduced-motion checks passed. The preceding failed release is preserved; its stale small-model smoke metadata was rebuilt from committed evidence.

- [x] Gemma E2B thinking-on first P0/P1 publication prepared and pushed in `db99819e`: 60 valid responses per phase, 38/60 and 36/60 all-field matches, with 13 changed four-field classifications. All 232 series bindings match the committed cutoff; 18 reporter and 61 UI tests passed. Pages [36776509888](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36776509888) succeeded; live HTML, small-local feed and raw README match `db99819e` byte for byte. Feed SHA-256 `8bf97064b5233bda8f01c4c11c300a263454adb4262b72b1b4c7941869c8aab0`. P2 smoke and live development are outside that published cutoff.

- [x] **Six-phase E2B publication — root:** `c5fc22d8` passed [Pages run 36784168095](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36784168095). The live small-local feed matches committed bytes, SHA-256 `21c4e4d332e394d8cff0ea2ea8c385bca48db504950b97fc228e2095503d4a7d`. This publishes six closed phases only; the third-pass P2 and hosted Gemma26 P0 processes continue separately.

- [x] **E2B thinking-on P2 third pass — root / native_variants_prepare:** `861ec962` archives all 60 valid results. P2 has three full passes (36/36/35 all-four matches; 24/60 comments changed across passes). Seven of nine phases are closed. Fresh3/P0 full is separately running on original handle 27582; fresh3/P1 remains pending.
- [ ] **Qwen27 v2 hosted wave — publish_on_triple / root:** reviewed versioned controllers committed in `c945e2db`, exact routes verified. Root allocated $1.00 medium and $0.80 xhigh under the $12.38 cap and admitted separate fresh1/P0 three-record smokes; neither full phase is admitted yet. Unallocated master capacity is $0.19967548250, with active allocations and unknown bounds retained.

- [x] **Seven-phase E2B publication — root:** `07df7c9d` passed [Pages run 36785448885](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/36785448885). Live feed equals committed bytes, SHA-256 `8694edef4396f8ad4552a0157b1fa821802b25712cd5eeb49151cdfd0da7568d`. P2 is complete at three passes; third P0/P1 remain outside this publication.
- [x] **Hosted Gemma26 v2 first P0 pass — resume_generated / root:** 60 valid, billed outputs, 59/60 all-four matches. Closed evidence is in `77984cb0`; [checkpoint](HOSTED_RESUME_CHECKPOINT_2026-10-01.md) explains the sole disagreement and provider token inconsistency. P1 smoke is running separately.
- [ ] **Qwen27 v2 full P0 runs — publish_on_triple:** medium and xhigh smokes inspected and accepted unchanged; original full execution handles 70171 and 44114 respectively. No later phase is admitted.

### 2026-10-01 reader presentation follow-up

- Root: revised public copy and layout using Academy voice/anti-slop, moved results ahead of the long narrative, added clickable method explanations and source-bound prompt comparison controls. Independent review approved; desktop/mobile/keyboard/reduced-motion checks passed. Published in 7882b755; GitHub Pages run 36819083251 succeeded, all four changed public assets match local SHA-256, and the live explainer was operated successfully.
- Qwen successor: independently reviewed controller committed as 2c3744d8; medium and xhigh never-sent suffixes running under distinct $0.30 children. Execution owner: publish_on_triple. No completed requests replayed.
- Gemma third successor: independent review approved six offline tests. Controller 0f1dcb96 and immutable admission f5fa893e; $0.40 child, exact DEV006–060 suffix now running on original session86569 under native_variants_prepare. No prior attempt replayed.

## Execution boundary, 1 October 2026

The host remained lid-closed in maintenance DarkWake on successive checks after the Mistral timeout. Its existing idle assertions did not prevent the earlier Sleep Service Back to Sleep interruption. Model execution requires a fully awake host; no power safeguards have been changed. The exact next action is the reviewed, separately funded DEV-049–060 Mistral suffix. Its proposed $0.25 child fits the available ledger capacity. No inference process or child allocation is active.

Qwen three-pass descriptive findings and Jev confidence findings are published and byte-verified. Mistral preparation and GLiNER contract work are saved. The requested roster remains unfinished as detailed above and in the roster audit. This is a blocked execution checkpoint, not completion, accepted exclusions or a reduction in scope. Resume with a fresh host, ledger and active-process check once the host is fully awake.

## Published repeat checkpoint, 2 October 2026, 12:26 UTC

Qwen HTTP findings and repeat navigation are published in `eb3774dc`. [Pages run 37005954223](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37005954223) succeeded; live HTML, repeat JavaScript and the new report match committed bytes. Independent review recalculated all nine scores from raw outputs and found no blocking or residual findings. All 171 evidence bindings match Git, four focused Python tests and 117 UI tests passed, and desktop/mobile checks found no horizontal overflow. Shared Ruflo decision retrieval and save-back were verified in both canonical stores.

Next hosted work is a separately versioned Gemma26 thinking-on fresh3/P2 suffix for never-sent DEV-007–016, under implementation and not dispatched. A proposed $0.20 child fits the last reconciled headroom; admission still requires independent review and fresh atomic budget checks. DeepSeek continuation needs a reviewed pricing successor because its current output price exceeds the frozen ceiling.

## Clef and report filters, 2 October 2026

- Report filters: implementation `a33187b9` adds model family, effort, repeat search/coverage and section navigation. Independent review approved after fixing the Qwen final descriptive-series count. All 118 UI tests passed; desktop and 390px checks found no overflow. [Pages publication 37008242107](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37008242107) succeeded; live HTML, app/repeat scripts and presentation CSS match `a33187b9` bytes.
- Clef / Clef-Flash: native adapter execution support is in preparation; initial six-request smoke plan reserves at most $0.064884. Cloudflare credentials and proposed separate $0.10 cap are pending user response. No Clef request has been sent.
- Gemma26: reviewed DEV-007–016 continuation admitted under its own $0.20 child. Initial launch stopped before claiming or sending because no env-file was passed; the corrected launch reads the ignored `.env` and is tracked on handle `6404`. No failed request was replayed.
- SDK Qwen0.6: separately reviewed format-admission successor prepared, preserving both failed smokes and all frozen request/parser controls. The approved successor is archived in `76e36d9b`. Thinking-on fresh1/P0 full development is running on handle `6457`; thinking-off fresh1/P0 is authorized next with its own fresh checks.

## Pending funding request, 6 October 2026

Root requested a revised separate postapproval ceiling of $10.36. Current holds are $9.625811024 against $10, leaving $0.374188976. Nine Jev full passes at the conservative $0.080640 bound need $0.351571024 additional reservation capacity. The request is pending, not approved. The OpenRouter aggregate cap remains $12.38; its current unallocated capacity is $0.44667141350 after Kev reconciliation. Root can continue individually admitted work within both current caps.

## Jev full-pass admission, 6 October 2026

Root and independent reviewer approved the separate Jev adapter after seven offline tests. First P1/P2 full passes are running on handles 72998 and 2040, each with a $0.080640 reservation inside the existing caps. The context estimate is explicit, source-bound and not a provider guarantee. A temporary launch helper initially stopped before allocation because its file handle shadowed a module variable; the helper was corrected before dispatch. No failed inference was replayed. The requested $10.36 postapproval cap remains pending.
