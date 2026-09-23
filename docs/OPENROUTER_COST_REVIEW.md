# OpenRouter cost review — 2026-09-23

The user requested a low-effort agent to assess whether hosted models could reduce download and local execution time. This was a read-only review. The subsequent user instruction authorized reasonably priced hosted matches instead of downloading them. Execution is bounded to an aggregate $1 OpenRouter inference cap; the existing TypeSafe $1 cap is separate.

The [official model catalog](https://openrouter.ai/api/v1/models) advertised the following routes and prices at review time. A listing is not proof of successful inference or a latency guarantee.

| Model ID | USD / million input tokens | USD / million output tokens | Estimated USD / 60 records |
|---|---:|---:|---:|
| `qwen/qwen3.8-27b` | 0.42 | 3.00 | 0.0980 |
| `qwen/qwen3.6-35b-a3b` | 0.15 | 1.00 | 0.0336 |
| `google/gemma-4-26b-a4b-it` | 0.09 | 0.30 | 0.0145 |
| `google/gemma-4-31b-it` | 0.09 | 0.34 | 0.0152 |
| `mistralai/mistral-small-3.2-24b-instruct` | 0.09375 | 0.25 | 0.0139 |
| `mistralai/mistral-small-2603` | 0.15 | 0.60 | 0.0260 |

The last route identifies Mistral Small 4 119B 2603 in the catalog. These are model-name matches, not verified matches to local quantization, artifact revision, runtime or decoding behavior. Hosted results must have separate configuration IDs and provenance.

Estimates use the completed local Qwen3.8-27B low-effort run: 97,230 input tokens and 19,053 generated tokens across 60 records (`results/qwen3.8-27b-2026-09-23/low-development.jsonl`). Generated-token counts include reasoning. Formula: `(input_tokens * input_rate + output_tokens * output_rate) / 1,000,000`. This is a common workload assumption, not a measurement of the other models. Each effort or prompt variant requires another pass. Different tokenizers, reasoning lengths, smoke requests, retries and provider pricing can change the cost. The estimates exclude the three-record smoke and retries.

No exact catalog entry was found for DeepSeek-R1-Distill-Qwen-32B or Gemma 4 E4B. A related DeepSeek model would be an additional comparison, not a replacement. Specialist Laya/OpenJev/SemIf/AnyJev availability was not established; a base-model endpoint does not implement their specialist decision procedures.

The free `qwen/qwen3.8-27b:free` listing remains advertised, but the September 23 reasoning-off smoke returned HTTP 429 before any prediction. See `results/openrouter/qwen38-off-smoke-2026-09-23.jsonl`. Do not treat the paid listing as proof that its route is healthy either.

The [official billing FAQ](https://openrouter.ai/docs/faq) describes credit purchases and a purchase fee. This review did not establish a current minimum deposit or numerical fee. After this review, the user authorized reasonably priced hosted matches. The implementation uses a separate aggregate $1 inference cap; no credit purchase or automatic top-up is authorized. Prices and provider availability must be checked again before any authorized paid run.

## Hosted execution decision

The live endpoint snapshot and model reasoning metadata are saved in `results/openrouter-paid-planning-2026-09-23/`. Exact providers and remaining configurations are listed in `results/openrouter-paid-run-registry.json`; they must be revalidated before requests. Existing completed local results remain intact. DeepSeek-R1-Distill-Qwen-32B, Gemma E4B and specialist models stay local because no exact hosted route was established. Stopped partial downloads are preserved. The paid runner must reserve each request against the shared budget before sending, reconcile reported cost, stop on unknown billing or the first request failure, and inspect three smoke responses before a full60 run.

The first Mistral119B smoke returned an upstream HTTP429 without reported usage cost. Its full $0.04177920 maximum reservation is permanently counted against the cap, with actual cost still unknown; an explicit ledger event records the evidence hash. This is not a zero-charge assertion or an automatic retry. The separate Mistral24B/DeepInfra FP8 smoke passed all three records and reported $0.00034845 total cost. Hosted development proceeds only after smoke inspection, with no fallback provider.

The original plan also reserved a hosted DeepSeek slot independent of the local32B distill. The September23 public [DeepSeek V4.1 Flash endpoint metadata](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints) lists `open-inference/fp4` at flat $0.10/$0.50 per million input/output tokens, with structured output and reasoning support. This is about $0.01925 for the same illustrative60-record token volume. Off/low/high are queued under the existing aggregate cap; max is excluded. It is a separate model comparison, not a renamed or equivalent32B distill.

## Measured cost checkpoint

The Qwen3.6-35B-A3B hosted runs completed all 60 records with thinking off and on. Their development calls cost $0.0072576 and $0.0636796 respectively; the three-record smokes cost $0.0004834 and $0.0025828. These are observed costs from the [saved runs](../results/openrouter-paid-run-registry.json), rather than the common-workload estimates above.

At this checkpoint, the [shared ledger](../results/openrouter-paid-budget.jsonl) records $0.0752812 in known charges and $0.0521984 in conservative upper bounds for two attempts with unknown charges. Total accounted spending is $0.1274796, leaving $0.8725204 of the $1 cap; there are no unresolved reservations. The upper bounds are not measured charges. No additional deposit is needed for this capped work based on the previously checked account balance, although balance and endpoint availability must be rechecked before further authorized calls.

## Destination approval pending

Automatic approval review rejected two three-record smoke commands on September 23 before either command executed:

| Requested model | Provider | Control | Review outcome |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4.1-flash` | `open-inference/fp4` | off; $0.10/$0.50 per million input/output tokens | Review could not confirm explicit approval for this payload and destination. |
| `google/gemma-4-26b-a4b-it` | `deepinfra/fp8` | off; $0.07/$0.34 per million input/output tokens | Review acknowledged the reasonably priced substitution authorization but still required explicit approval of the payload and specific model/provider. |

Both commands specified 4,096 maximum output tokens, a 300-second timeout and the shared $1 cap. Neither command ran: no feedback payload was sent, no inference charge was incurred, and no budget reservation or smoke output was created by these rejected commands. Neither was retried or routed through another execution path.

The earlier authorization to use reasonably priced OpenRouter replacements remains recorded above. The repository describes the feedback as entirely synthetic, with no actual candidate records ([agreed scope](../README.md#agreed-scope), [accepted decisions](PLAN.md#accepted-decisions)). Approval review nevertheless required confirmation scoped to these destinations. Their off configurations are now `pending_explicit_destination_approval` in the [paid registry](../results/openrouter-paid-run-registry.json). Further paid calls are paused pending that explicit approval; existing successful outputs and recorded charges remain unchanged.
