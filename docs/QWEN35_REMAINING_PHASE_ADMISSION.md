# Qwen3.5 remaining-phase admission

## Decision boundary

The interrupted `qwen3.5-4b-sdk-thinking-on/fresh1/P0` phase can support a descriptive continuation, but it cannot become a clean repeat. Its original evidence remains fixed at 52 attempted positions, 51 saved records, seven invalid outputs, and one unknown outcome at `DEV-052`. The approved suffix covers only `DEV-053` through `DEV-060`; it never replays `DEV-052` or any earlier position. See the [approved suffix manifest](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen35-p0-unsent-suffix-v1/manifest.json), the [interruption review](../results/repeatability-v1/legacy-qwen-fresh3-v1/qwen3.5-4b-sdk-thinking-on/fresh1/P0/interruption.root-review.json), and the [suffix controller](../scripts/qwen35_p0_unsent_suffix_v1.cjs).

Root must wait for the suffix to reach an evidence-backed terminal state before preparing any later phase. If all eight suffix positions are saved, the P0 composite has 60 accounted positions: 59 saved results and one unknown result. Invalid outputs remain saved outcomes. `DEV-052` remains unknown, carries no inferred classification, and receives no retry. This composite stays outside the clean paired-repeat cohort.

## Frozen phase order

The [legacy Qwen manifest](../results/repeatability-v1/legacy-qwen-fresh3-v1/manifest.json) fixes the condition order for all three passes. After the descriptive fresh1/P0 composite closes, the remaining eight phases are:

1. `fresh1/P2`, after the descriptive `fresh1/P0` composite.
2. `fresh1/P1`, after `fresh1/P2`.
3. `fresh2/P2`, after all fresh1 phases.
4. `fresh2/P1`, after `fresh2/P2`.
5. `fresh2/P0`, after `fresh2/P1`.
6. `fresh3/P1`, after all fresh1 and fresh2 phases.
7. `fresh3/P0`, after `fresh3/P1`.
8. `fresh3/P2`, after `fresh3/P0`.

Each phase still has a three-record smoke stage followed by a 60-record development stage. The successor must use the existing request hashes, rendered-prompt hashes, token counts, model artifact, Q4_K_M quantization, SDK controls, cache policy, and phase order. It must not rebuild or edit the frozen request set.

## Existing gates

The [legacy controller](../scripts/legacy_qwen_repeat_admission.cjs) applies these checks before a stage can send a request:

1. `phaseInfo` builds one linear predecessor list from the frozen schedule.
2. `checkPredecessor` requires every earlier development terminal to exist with `status: "completed"`, `attempted: 60`, and `saved: 60`. It also checks the journal, raw, and records hashes.
3. A development stage requires its own completed smoke with three attempted and three saved records. The independent inspection must be approved, its hashes must match, and all three decisions must be `ok`.
4. `checkReceipt` requires a root-approved receipt bound to the plan, controller, phase, stage, model identifier, artifact hash, 8192 MiB cache policy, and the full 60-request preflight hash. It also requires a fresh exact-route audit and confirms that references were not read.
5. `runStage` checks the current runtime, loaded artifact, exact hosted-route absence, rendered prompt, token count, and model instance before it writes an atomic claim. It stops without retry on a service, timeout, or control failure.

The first remaining smoke, `fresh1/P2`, currently fails gate 2 because the original P0 terminal says `status: "stopped"`, `attempted: 52`, and `saved: 51`. Every later phase includes fresh1/P0 in its predecessor list, so the same terminal blocks all eight phases. Replacing that terminal with a fabricated 60/60 completion would erase the unknown outcome and is prohibited.

## Minimal successor

Prepare one versioned successor manifest and one thin controller in a new result directory after root closes and reviews the current suffix. Keep the original manifest, controller, phase files, interruption audit, and suffix evidence unchanged.

The successor needs four narrow changes:

1. Build a `fresh1/P0` composite closure receipt. Bind every original P0 file, the interruption audit and review, the completed three-record smoke, and every suffix file by SHA-256. Assert that the original saved IDs are `DEV-001` through `DEV-051`, the only original unknown is `DEV-052`, and the suffix IDs are exactly `DEV-053` through `DEV-060`. Record the composite as descriptive and non-clean. Do not emit a normal 60/60 development completion for P0.
2. Freeze the eight-phase order above and copy the existing request metadata from the legacy plan. The successor must bind the legacy plan, request constructor, classifier, predictor, [current host-admission policy](../scripts/local_host_admission.cjs), artifact, and SDK controls by hash.
3. Replace only the first predecessor decision. `fresh1/P2` may treat the reviewed P0 composite closure as its predecessor. Every later phase must require all earlier successor development stages to have normal completed 60/60 terminals. Development stages keep the existing three-valid-smoke inspection gate.
4. Write all later smoke and development evidence under the new successor directory. A root-reviewed stage receipt must bind the successor manifest and controller, the P0 composite closure hash, the exact phase request hashes, a fresh host baseline, current runtime and artifact evidence, all 60 render and token checks, and a fresh exact hosted-route audit. Root alone performs preflight and dispatch under the shared native GPU lock.

The existing controller already exposes the useful pieces: `phaseInfo`, `stageRows`, `checkLiveRoute`, `verifyRequestRuntime`, and `runStage`. Its `runStage` dependency hooks can accept successor paths plus successor-specific predecessor and receipt checks. A thin wrapper can therefore preserve the request construction, classifier, raw-first journal order, timeout handling, and no-replay behavior without editing the frozen controller.

## Stop conditions and reporting

Do not admit `fresh1/P2` if the current suffix ends with fewer than eight saved records, a new unknown outcome, a control failure, missing hashes, or an unreviewed terminal. Root must first record the new disposition and may prepare another continuation only for positions proven never sent. Failed or unknown positions remain unreplayed.

Later phases can count as individually complete when their own smoke and development gates pass. The configuration still carries the fresh1/P0 caveat in every report: one unknown position, no clean-repeat credit, no repaired output, and no claim of 60 observed P0 classifications. References remain outside inference, and scoring remains an offline step.

## Receipt provenance

Successor receipts carry `unknown_ids: ["DEV-052"]` and `clean_repeat_credit: false` as provenance of the interrupted predecessor. These fields do not describe failures in a later stage. Later-stage outcomes must be read from that stage's own saved records, terminal and host audit. The runtime route audit checks only the exact Qwen3.5 4B family; hosted availability of a different Qwen size does not block this configuration.
