# Gemini 3.8 Flash low: repeated scores and changed decisions

Three passes on the same 60 synthetic reviews are complete for each prompt condition. Scores count agreement with all four provisional reference labels on a review, out of 60. All 540 development outputs were structurally valid. This is agreement with AI-reviewed references, not measured accuracy against independently adjudicated ground truth.

| Prompt | Pass 1 | Pass 2 | Pass 3 | Reviews with at least one changed decision |
| --- | ---: | ---: | ---: | ---: |
| P0: original task prompt | 57 | 57 | 57 | 1 of 60 |
| P1: explicit classifier instructions | 56 | 57 | 56 | 5 of 60 |
| P2: classifier instructions and decision procedure | 56 | 55 | 56 | 3 of 60 |

P0 keeps the same total in all three passes, but DEV-030 changes a decision. Equal scores therefore do not mean identical classifications. P1 changes decisions on DEV-006, DEV-013, DEV-029, DEV-030 and DEV-053; P2 changes on DEV-006, DEV-010 and DEV-018. A changed review counts once even if several fields change.

Neither expanded prompt improves the all-four score over P0 in any pass. P1 trails by one, ties, then trails by one; P2 trails by one, two and one. This supports a narrow finding for this model, route, settings and dataset: adding these instructions did not produce a score advantage in the observed series. It does not establish that more detailed prompts generally hurt classification. Some changed reviews also have disputed provisional labels, so model consensus is not a substitute for human adjudication.

The two additional passes cost $0.15296100 including six separate three-review smokes. Their 360 development outputs are repeat measurements of the same 60 reviews, not 360 new reviews. The provider route was Google AI Studio through OpenRouter, model `google/gemini-3.8-flash`, low reasoning effort, temperature 0, batch size 10 and an 8,192-token output limit. Raw provider usage, charges and responses remain in the [repeat evidence](../results/repeatability-v1/gemini38-low-p0-openrouter-v2/); the [sealed budget reconciliation](../results/repeatability-v1/gemini38-low-p0-openrouter-v2/budget-reconciliation-v1.json) retains actual charges and the released allocation.

The [historical admission review](GEMINI38_LOW_REPEAT_ADMISSION.md) explains how the original P0 identity stop was resolved from saved metadata without resending that batch. The first pass predates the repeats. Effective serving revisions, seeds and caching are not fully observed, so changes cannot be attributed solely to random sampling. Client request time is not pure model inference time.
