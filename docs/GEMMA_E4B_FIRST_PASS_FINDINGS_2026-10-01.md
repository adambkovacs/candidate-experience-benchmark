# Gemma E4B thinking-off: nine saved passes

The [source-bound small-local report](../public-site/small-local-repeats.json) now includes all nine planned development phases of the [frozen E4B thinking-off study](../results/repeatability-v1/small-local-v1/manifest.json). Every phase saved 60 valid responses. Scores count agreement with the [provisional v0.2 reference answers](../data/pilot/proposed_labels.jsonl) for the same 60 fictional candidate comments. They do not measure accuracy on real candidate feedback.

| Prompt | Pass 1 | Pass 2 | Pass 3 | Three-pass score range | Comments with any changed answer across passes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base task, P0 | 38/60 | 40/60 | 39/60 | 38–40 | 11/60 |
| Classifier instructions, P1 | 41/60 | 40/60 | 40/60 | 40–41 | 9/60 |
| Decision procedure, P2 | 42/60 | 42/60 | 42/60 | 42 | 7/60 |

The P2 score stayed at 42/60 in all three passes, yet seven comments received at least one different decision. A tied total did not mean identical classifications. All responses were valid, so each changed-answer count uses the full 60-comment denominator. These are repeated decisions on the same comments, not 180 independent cases per prompt.

## Which answers changed

| Prompt | Pass 1 to 2 | Pass 1 to 3 | Pass 2 to 3 |
| --- | --- | --- | --- |
| P0 | 7 changed; 2 gained a full match, 0 lost | 8 changed; 3 gained, 2 lost | 7 changed; 2 gained, 3 lost |
| P1 | 6 changed; 1 gained, 2 lost | 5 changed; 1 gained, 2 lost | 7 changed; 2 gained, 2 lost |
| P2 | 5 changed; 1 gained, 1 lost | 3 changed; 1 gained, 1 lost | 6 changed; 1 gained, 1 lost |

“Changed” counts a comment once if any of its four decisions differed. “Gained” and “lost” mean a change in agreement with the provisional four-answer reference, not a verified correction to a real candidate outcome. Across passes, follow-up decisions did not change under any prompt. Most observed changes were in sentiment; serious-concern and testimonial answers also changed. The [report](../public-site/small-local-repeats.json) lists the exact changed IDs and field counts.

P2 had more four-answer matches than P0 in each matched pass, by four, two and three comments. Compared with P1, it had one, two and two more matches. These are saved outcomes under one local setup. They do not isolate the effect of longer instructions from other run conditions.

## Saved phase measurements

| Phase | Valid / 60 | All four / 60 | Sentiment | Follow-up | Serious concern | Testimonial | Sum of client request seconds | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Pass 1 P0](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh1/P0/development.completion.json) | 60 | 38 | 46 | 58 | 52 | 57 | 93.90 | 97,768 / 2,100 |
| [Pass 1 P1](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh1/P1/development.completion.json) | 60 | 41 | 48 | 58 | 52 | 57 | 96.48 | 108,568 / 2,100 |
| [Pass 1 P2](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh1/P2/development.completion.json) | 60 | 42 | 48 | 58 | 54 | 58 | 105.31 | 164,428 / 2,106 |
| [Pass 2 P0](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh2/P0/development.completion.json) | 60 | 40 | 48 | 58 | 52 | 57 | 98.80 | 97,768 / 2,100 |
| [Pass 2 P1](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh2/P1/development.completion.json) | 60 | 40 | 46 | 58 | 52 | 58 | 95.54 | 108,568 / 2,100 |
| [Pass 2 P2](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh2/P2/development.completion.json) | 60 | 42 | 49 | 58 | 54 | 57 | 114.61 | 164,428 / 2,106 |
| [Pass 3 P0](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh3/P0/development.completion.json) | 60 | 39 | 46 | 58 | 53 | 58 | 104.40 | 97,768 / 2,103 |
| [Pass 3 P1](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh3/P1/development.completion.json) | 60 | 40 | 48 | 58 | 52 | 58 | 76.54 | 108,568 / 2,100 |
| [Pass 3 P2](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh3/P2/development.completion.json) | 60 | 42 | 48 | 58 | 54 | 58 | 95.66 | 164,428 / 2,106 |

The reported durations sum 60 client-observed request times per phase. They include local workflow overhead and are neither pure model inference time nor the phase's elapsed wall-clock time. Token totals are local runtime reports. Hardware and electricity costs were not measured, so cost is unavailable, not zero.

The [dated route audit](../results/route-audits/small-local-admission-20260930T200956Z/catalog-audit.json) found no exact E4B route in the OpenRouter catalogue it checked. This study used the exact local Q4_K_M artifact on an Apple M4 Max. The [plan](../results/repeatability-v1/small-local-v1/manifest.json) records its controls. The selected backend was observed as 2.22.0; the loaded engine version was not independently available. Reference answers were withheld from requests and used only for offline scoring. Four smoke inspections needed [post-run reference-withholding attestations](../results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-off/fresh3/P2/smoke-inspection-reference-attestation.json); the original inspections and receipts remain unchanged.

Publication evidence cutoff: `750ac4a4`. The report binds 139 source paths for this configuration by SHA-256. The completed [E2B thinking-off study](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md) is separate; these runs do not establish an E4B-versus-E2B model effect.
