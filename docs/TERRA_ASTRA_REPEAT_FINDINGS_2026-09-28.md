# Terra and Astra repeat findings, 28 September 2026

Terra extra-high and Astra low, high and extra-high have completed all nine prompt/pass combinations per configuration. All combinations have 60 valid classifications. The 24 new development phases and their separate smokes retain the frozen batch-ten requests and phase admissions.

Astra low illustrates a reversed prompt effect: decision-tree instructions lost one all-four match against the base prompt in passes one and two, then gained one in pass three. Terra extra-high tied the base-prompt total with classifier instructions in all three passes, while its individual answers still changed across passes. Astra extra-high produced the same complete decision vectors for all 60 comments in all three P2 passes; that observed stability applies to this configuration and sample.

| Configuration | Prompt | All-four matches, passes 1 / 2 / 3 | Reviews with any changed decision across passes |
| --- | --- | ---: | ---: |
| GPT-5.6 Terra · xhigh effort | P0 | 57 / 58 / 58 | 3/60 |
| GPT-5.6 Terra · xhigh effort | P1 | 57 / 58 / 58 | 2/60 |
| GPT-5.6 Terra · xhigh effort | P2 | 57 / 58 / 57 | 1/60 |
| GPT-6 Astra · high effort | P0 | 58 / 57 / 57 | 3/60 |
| GPT-6 Astra · high effort | P1 | 58 / 58 / 57 | 2/60 |
| GPT-6 Astra · high effort | P2 | 58 / 57 / 58 | 1/60 |
| GPT-6 Astra · low effort | P0 | 58 / 58 / 57 | 2/60 |
| GPT-6 Astra · low effort | P1 | 58 / 58 / 57 | 2/60 |
| GPT-6 Astra · low effort | P2 | 57 / 57 / 58 | 1/60 |
| GPT-6 Astra · xhigh effort | P0 | 58 / 57 / 57 | 1/60 |
| GPT-6 Astra · xhigh effort | P1 | 57 / 58 / 57 | 1/60 |
| GPT-6 Astra · xhigh effort | P2 | 57 / 57 / 57 | 0/60 |

Scores count agreement with all four provisional v0.2 references out of 60 comments. P0 is the base task, P1 adds classifier instructions, and P2 adds a decision tree. Valid output format is separate from agreement. Repeated comments are not independent samples; accepted CLI patch differences and hidden serving behavior prevent attributing every change to randomness.

No actual per-run subscription cost or model-only inference time is available. Reported tokens and summed client request durations remain in the [source-bound repeat report](../public-site/repeats.json), alongside per-field scores, changed IDs and source hashes.

These four completed series do not close the remaining Codex configurations or the [full repeat inventory](REPEAT_EXECUTION_STATUS_2026-09-28.md).
