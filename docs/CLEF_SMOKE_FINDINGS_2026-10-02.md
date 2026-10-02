# Clef native P0 smoke findings, 2 October 2026

Both Cloudflare decision models passed their first native `fresh1/P0` smoke. [Clef](../results/clef-native-v1/clef/fresh1/P0/smoke/completion.json) and [Clef Flash](../results/clef-native-v1/clef-flash/fresh1/P0/smoke/completion.json) each returned three valid responses for DEV-001–003: six valid, zero failed, zero never sent. These are smoke results, not 60-record scores. The saved records mark `reference_labels_read: false`; no provisional labels entered the requests or this inspection.

The [source-bound inspection](../results/clef-native-v1/smoke-inspection-v1.json) checks 39 saved source files. It binds the [input-only preparation manifest](../results/clef-native-v1/preparation.json), [initial grant](../results/clef-native-v1/initial-smoke-grant.json), model-specific connected-app reviews, the six locked-ledger reservations, every request and connector result, the submitted response, and the runner's raw, parsed, journal, claim, and completion files. All six connector results report HTTP 200, `success: true`, the exact requested model, and four native `choice` answers with finite probabilities summing to one. The original [Cloudflare model documentation](https://developers.cloudflare.com/workers-ai/models/clef/) describes this typed-choice interface; [Clef Flash](https://developers.cloudflare.com/workers-ai/models/clef-flash/) uses its own pinned route.

| Model | Valid / attempted | Observed input tokens, DEV-001/002/003 | Observed output tokens | Full-context amount held as unknown charge |
| --- | ---: | --- | ---: | ---: |
| Clef | 3 / 3 | 2,219 / 2,193 / 2,216 | 0 | $0.047187 |
| Clef Flash | 3 / 3 | 2,219 / 2,193 / 2,216 | 0 | $0.017697 |
| Both | 6 / 6 | 13,256 total | 0 | $0.064884 |

The $0.064884 is a conservative reservation under the reviewed $0.10 initial Cloudflare subcap, **not a provider bill**. Exact USD charges remain unknown. The observed token counts do not release any hold or establish a safe ceiling for 60 future requests. The [published price sources](https://developers.cloudflare.com/workers-ai/platform/pricing/) support planning, while the saved [Cloudflare ledger](../results/clef-native-v1/budget.jsonl) preserves each attempt's full-context bound.

The connected-app handoff differs from direct REST transport. The runner's `raw.jsonl` contains the saved, serialized connector result for each attempt, with the complete outer tool return kept alongside it; it does not contain captured HTTP wire bytes. Its `client_seconds` includes the operator's time between ready-file publication and response submission, so it is not model latency or a fair speed comparison. No request was retried. The full 60-record P0 run for either model remains a separate stage requiring a new reviewed authority and budget guard; the three smokes do not count as development records.
