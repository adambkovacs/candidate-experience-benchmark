# Clef: first classifier-instruction pass

Verified 5 October 2026. Clef fresh1/P1 returned valid native choices for all 60 reviews and matched all four provisional reference labels on 52/60. The matched fresh1/P0 base-task pass scored 53/60. Adding classifier instructions did not improve this first-pass total; two further P1 passes remain required before describing repeatability.

| Decision | P1 agreement |
|---|---:|
| Sentiment | 57/60 |
| Follow-up needed | 59/60 |
| Serious concern | 55/60 |
| Testimonial potential | 57/60 |
| All four | 52/60 |

Four reviews changed at least one decision between P0 and P1: DEV-013, DEV-014, DEV-053 and DEV-056. DEV-056 gained an all-four match; DEV-013 and DEV-014 lost one. This compares the same reviews, not independent samples, and does not establish that instructions alone caused the change. References remain frozen and provisional.

The three-record smoke completed valid and was inspected before development admission. The full pass used `@cf/cloudflare/clef` through the connected Cloudflare Workers AI app. Ordered inputs and request hashes match the frozen P1 plan. Inference records explicitly confirm that reference labels were not read; scoring occurred offline.

Development reported 144,694 input tokens and zero output tokens. At the [published Clef input price](https://developers.cloudflare.com/workers-ai/models/clef/) of $0.24 per million, that is **$0.03472656 estimated**, not an observed provider charge. Smoke usage was 7,228 input tokens and is excluded from that development estimate. Operator-mediated request duration is not pure inference latency; hardware, quantization and server inference duration are unavailable.

## Evidence

- [P1 records](../results/clef-native-v1/clef/fresh1/P1/development/records.jsonl), SHA-256 `3bc681b50494b4d94222c10a84e735d55e78f80577f712d0295d8a1a6fde33cb`.
- [P1 completion](../results/clef-native-v1/clef/fresh1/P1/development/completion.json), SHA-256 `e103f8a3e74a8336772262cfc187f0bfd972beceee982ea4b0c0f75eea1a8d18`.
- [P0 records](../results/clef-native-v1/clef/fresh1/P0/development/records.jsonl), SHA-256 `222971089e6093eaa24b510c123055e87d4e87752311bfc397f30a85046b55be`.
- [Frozen references](../data/pilot/proposed_labels.jsonl), used offline only.
- [Smoke inspection](../results/clef-native-v1/clef/fresh1/P1/smoke/root-smoke-review.json).

Root and an independent audit checked completion hashes and ordered records. Raw native probabilities and provider confidence are preserved separately. No completed or failed request was replayed. This document adds a first-pass finding; the [combined-analysis feed](../public-site/analysis-refresh.json) incorporates this result as `clefP1FirstPass`, separate from the three-pass results.
