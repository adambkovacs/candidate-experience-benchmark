# Hosted repeats resumed: 1 October 2026

The first full P0 pass in the [Gemma26 reasoning-on v2 series](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh1/manifest.json) is closed: **60 valid responses and 59/60 all-four matches** against the unchanged [provisional reference answers](../data/pilot/proposed_labels.jsonl). This is one pass of one prompt, not a completed repeat study or independently established accuracy.

| Measure | Observed result |
| --- | ---: |
| Sentiment matches | 59/60 |
| Follow-up matches | 60/60 |
| Serious-concern matches | 60/60 |
| Testimonial matches | 60/60 |
| Provider-reported development cost | $0.01931258 |
| Provider-reported input tokens | 87,568 |
| Provider-reported completion tokens | 38,773 |
| Provider-reported total tokens | 126,341 |
| Pure inference duration | Unavailable |

The only disagreement was DEV-005: the model returned `neutral` sentiment where the saved reference says `insufficient_information`. The other three fields matched. Review this against the rubric rather than treating a high score as evidence of production performance.

The exact route was `google/gemma-4-26b-a4b-it`, DeepInfra `deepinfra/fp8`, with reasoning on. Hardware is not reported. The [attempt records](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh1/P0/development.attempts.jsonl) preserve requests, returned identity, usage, charges and client timing; [response captures](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh1/P0/development.responses.jsonl) and [wire captures](../results/repeatability-v1/gemma26-on-fresh-matched3-v2/fresh1/P0/development.wire.jsonl) preserve the original provider outputs. Reference labels were used only for offline scoring.

Provider metadata reports more reasoning tokens than completion tokens in **27 of 60 responses**. The stored values remain unchanged. The token totals above sum the provider's top-level fields; reasoning tokens are not added again. Do not infer a precise reasoning-token fraction from these inconsistent fields. Summed client request time was 1,110.18 seconds, which includes service and network time and is not pure inference time.

The three-record P0 smoke cost $0.00088227 separately. P1 and P2 and the later full passes remain unfinished. The two Qwen27 v2 P0 smokes returned three valid responses each, with observed costs of $0.002560725 for medium and $0.00184095 for xhigh. Their full runs were separately admitted after raw-response inspection; smoke outcomes are not included in development scores.
