# Gemma E2B thinking-off: fresh three-pass results

All nine development phases returned 60 valid four-field outputs. The same 60 synthetic reviews were used in each phase, with provisional reference version 0.2. These are 540 repeated outputs, not 540 independent reviews. Historical local runs remain observational and are excluded from this fresh series.

| Prompt condition | Fresh pass 1 | Fresh pass 2 | Fresh pass 3 | Reviews changing any decision |
| --- | ---: | ---: | ---: | ---: |
| P0: original task prompt | 35/60 | 35/60 | 35/60 | 9/60 |
| P1: classifier instructions | 34/60 | 33/60 | 33/60 | 5/60 |
| P2: instructions and decision procedure | 31/60 | 31/60 | 33/60 | 15/60 |

The table counts reviews matching all four reference labels. P0 has the same score in every pass while nine reviews change at least one decision. Score stability therefore conceals substantial answer variation. P2 has the most changed reviews in this series, including seven testimonial decisions and six sentiment decisions; field counts overlap and should not be added.

P1 trails P0 by one, two and two all-field matches. P2 trails P0 by four, four and two. Neither expanded prompt improves agreement over P0 in any observed pass. This is a result for these exact prompts, model artifact and reviews, not evidence that detailed prompts are generally harmful.

The fields differ sharply: follow-up agreement is 58–59/60 across the series, while serious-concern agreement is 41–43/60. Testimonial agreement falls from 51–54/60 under P0 to 46–49/60 under P2. A single overall score would hide these differences. The labels are AI-reviewed and provisional; unresolved reference disputes remain separate from this repeat analysis.

The exact local artifact is Gemma 4 E2B Q4_K_M, SHA-256 `71e6e8cb64a76da1a734fb8f6ba389d2784950d9902f5e87244fca0a15190c94`, running on Apple M4 Max (Mac16,5) through LM Studio 0.4.16+2, CLI `efce996`. The selected backend preference is llama.cpp 2.22.0; the loaded instance does not expose its engine version. The frozen settings include an 8,192-token context, one parallel session, full GPU offload, temperature 0.6, top-k 20, top-p 0.95 and no explicit seed. Exact load controls, request bytes and cache settings were verified before dispatch.

Client elapsed times and runtime token counts are retained in [the phase evidence](../results/repeatability-v1/small-local-v1/gemma4-e2b-sdk-thinking-off/). They are not hosted latency or pure inference time. Model-loading time, electricity cost and total local cost were not measured. The [frozen plan](../results/repeatability-v1/small-local-v1/manifest.json) includes the four other pending local configurations; finishing this one does not finish the local roster.
