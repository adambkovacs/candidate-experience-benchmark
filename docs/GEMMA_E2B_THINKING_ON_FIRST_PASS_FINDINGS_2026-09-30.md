# Gemma 4 E2B thinking-on: first P0, P1 and P2 passes

The [frozen small-local plan](../results/repeatability-v1/small-local-v1/manifest.json) schedules three separately dispatched development passes under each P0, P1 and P2 prompt. The [source-bound report](../public-site/small-local-repeats.json) contains the first closed full pass under each prompt. Six planned full phases have no score in this publication snapshot. These first-pass observations cannot establish repeatability.

| Closed phase | Valid / 60 | All four fields / 60 | Sentiment | Follow-up | Serious concern | Testimonial | Summed client seconds | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Fresh1/P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/development.completion.json) | 60 | 38 | 51 | 57 | 47 | 55 | 512.94 | 97,888 / 31,407 |
| [Fresh1/P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P1/development.completion.json) | 60 | 36 | 48 | 56 | 47 | 54 | 466.74 | 108,688 / 28,999 |
| [Fresh1/P2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P2/development.completion.json) | 60 | 36 | 46 | 56 | 50 | 57 | 494.04 | 164,548 / 30,423 |

All three phases returned valid decisions for the same 60 synthetic reviews. Against the [provisional version 0.2 references](../data/pilot/proposed_labels.jsonl), all-four agreement was 38/60 under P0 and 36/60 under both P1 and P2. Equal P1 and P2 totals conceal different answers. The saved [P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/development.records.jsonl), [P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P1/development.records.jsonl) and [P2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P2/development.records.jsonl) records support these paired comparisons:

| Prompt pair | Reviews with a changed four-field answer / 60 | All-four gains | All-four losses | Field changes: sentiment / follow-up / serious concern / testimonial |
| --- | ---: | ---: | ---: | ---: |
| P0 to P1 | 13 | 3 | 5 | 7 / 1 / 6 / 3 |
| P1 to P2 | 17 | 6 | 6 | 10 / 2 / 7 / 3 |
| P0 to P2 | 17 | 5 | 7 | 9 / 3 / 8 / 2 |

A review can change more than one field. Gains and losses count reviews that crossed the all-four agreement threshold, so their net difference matches the score change. These are observed differences among separately dispatched first passes; later passes are needed to assess within-prompt variation. The comparisons do not isolate a prompt effect.

The table keeps every score on the fixed 60-review denominator. Its seconds sum client-observed request durations and include local workflow overhead; isolated inference duration and model load time are unavailable. The saved local token counts are not hosted billing records. Hardware and electricity cost were not measured, so dollar cost is unavailable. The frozen plan and [reporter](../scripts/build_small_local_repeat_findings.py) preserve one attempt per review and use the provisional references only for offline scoring.

The original P0 and P1 smoke inspections omitted an explicit statement that reference labels were withheld. [Post-run P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/smoke-inspection-reference-attestation.json) and [P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P1/smoke-inspection-reference-attestation.json) attestations bind the original inspection, plan and smoke hashes without changing the original evidence. The [review note](SMALL_LOCAL_REPEAT_REVIEW_2026-09-28.md) explains this supplement and its limits. The report binds all three closed full phases and lists SHA-256 paths for its sources.

The completed [Gemma E2B thinking-off study](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md) is a separate configuration. The current thinking-on snapshot has one full pass under each prompt, so these observations do not establish the effect of enabling thinking.
