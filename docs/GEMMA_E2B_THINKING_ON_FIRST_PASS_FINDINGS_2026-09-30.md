# Gemma 4 E2B thinking-on: three P2 passes and two P0/P1 passes

The [frozen small-local plan](../results/repeatability-v1/small-local-v1/manifest.json) schedules three separately dispatched development passes under each P0, P1 and P2 prompt. The [source-bound report](../public-site/small-local-repeats.json) contains seven of nine planned full phases: two passes under P0 and P1, and all three under P2. The third P0 and P1 passes remain outside this snapshot.

| Closed phase | Valid / 60 | All four fields / 60 | Sentiment | Follow-up | Serious concern | Testimonial | Summed client seconds | Input / output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Fresh1/P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/development.completion.json) | 60 | 38 | 51 | 57 | 47 | 55 | 512.94 | 97,888 / 31,407 |
| [Fresh1/P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P1/development.completion.json) | 60 | 36 | 48 | 56 | 47 | 54 | 466.74 | 108,688 / 28,999 |
| [Fresh1/P2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P2/development.completion.json) | 60 | 36 | 46 | 56 | 50 | 57 | 494.04 | 164,548 / 30,423 |
| [Fresh2/P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh2/P1/development.completion.json) | 60 | 39 | 54 | 57 | 48 | 54 | 549.16 | 108,688 / 29,627 |
| [Fresh2/P2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh2/P2/development.completion.json) | 60 | 36 | 46 | 58 | 48 | 53 | 709.57 | 164,548 / 30,093 |
| [Fresh2/P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh2/P0/development.completion.json) | 60 | 37 | 52 | 58 | 48 | 52 | 616.92 | 97,888 / 30,393 |
| [Fresh3/P2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh3/P2/development.completion.json) | 60 | 35 | 48 | 56 | 48 | 55 | 629.70 | 164,548 / 30,450 |

The three first-pass phases returned valid decisions for the same 60 synthetic reviews. Against the [provisional version 0.2 references](../data/pilot/proposed_labels.jsonl), all-four agreement was 38/60 under P0 and 36/60 under both P1 and P2. Equal P1 and P2 totals conceal different answers. The saved [P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/development.records.jsonl), [P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P1/development.records.jsonl) and [P2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P2/development.records.jsonl) records support these paired comparisons:

| Prompt pair | Reviews with a changed four-field answer / 60 | All-four gains | All-four losses | Field changes: sentiment / follow-up / serious concern / testimonial |
| --- | ---: | ---: | ---: | ---: |
| P0 to P1 | 13 | 3 | 5 | 7 / 1 / 6 / 3 |
| P1 to P2 | 17 | 6 | 6 | 10 / 2 / 7 / 3 |
| P0 to P2 | 17 | 5 | 7 | 9 / 3 / 8 / 2 |

A review can change more than one field. Gains and losses count reviews that crossed the all-four agreement threshold, so their net difference matches the score change. These first-pass prompt comparisons do not isolate a prompt effect.

The second pass changed answers under every prompt, even where the score stayed the same. The table compares each condition's [fresh1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/development.records.jsonl) and [fresh2](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh2/P0/development.records.jsonl) saved decisions. The [P1 records](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh2/P1/development.records.jsonl) and [P2 records](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh2/P2/development.records.jsonl) are linked separately. All six phases were valid on the same 60 reviews, so every change count below has a 60-review shared-valid denominator.

| Prompt | All-four score, pass 1 to 2 | Reviews with a changed four-field answer / 60 | All-four gains / losses | Field changes: sentiment / follow-up / serious concern / testimonial |
| --- | ---: | ---: | ---: | ---: |
| P0 | 38 to 37 | 17 | 6 / 7 | 5 / 1 / 8 / 7 |
| P1 | 36 to 39 | 11 | 4 / 1 | 6 / 1 / 5 / 4 |
| P2 | 36 to 36 | 19 | 6 / 6 | 8 / 2 / 6 / 4 |

P2's unchanged 36/60 total hides 19 reviews with a changed classification. The four field counts can exceed the number of changed reviews because one review may change in several fields. Gains and losses count reviews that crossed the all-four agreement threshold, not every answer change. These two-pass observations do not estimate how often a future run will change; P0 and P1 still lack their third pass in this snapshot.

The table keeps every score on the fixed 60-review denominator. Its seconds sum client-observed request durations and include local workflow overhead; isolated inference duration and model load time are unavailable. The saved local token counts are not hosted billing records. Hardware and electricity cost were not measured, so dollar cost is unavailable. The frozen plan and [reporter](../scripts/build_small_local_repeat_findings.py) preserve one attempt per review and use the provisional references only for offline scoring.

The original fresh1/P0 and fresh1/P1 smoke inspections omitted an explicit statement that reference labels were withheld. [Post-run P0](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P0/smoke-inspection-reference-attestation.json) and [P1](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-on/fresh1/P1/smoke-inspection-reference-attestation.json) attestations bind the original inspection, plan and smoke hashes without changing the original evidence. The [review note](SMALL_LOCAL_REPEAT_REVIEW_2026-09-28.md) explains this supplement and its limits. The report binds all seven closed full phases and lists SHA-256 paths for its sources.

The completed [Gemma E2B thinking-off study](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md) is a separate configuration. Only P2 has a complete three-pass thinking-on condition in this snapshot. These observations do not establish the effect of enabling thinking.

## What all three P2 passes show

All three P2 passes returned 60 valid responses. All-four reference agreement was **36, 36 and 35 out of 60**, a range of 35–36. Yet **24 of the same 60 comments** received at least one different answer across those passes. Sentiment changed on 14 comments, follow-up on three, serious concern on ten and testimonial potential on eight; these counts overlap. A narrow range of total scores therefore does not mean the model made the same decisions. These are repeated observations on 60 fictional comments, not 180 independent cases. The [source-bound report](../public-site/small-local-repeats.json) lists the changed IDs and saved outputs.
