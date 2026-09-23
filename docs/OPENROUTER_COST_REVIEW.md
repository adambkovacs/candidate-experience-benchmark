# OpenRouter cost review — 2026-09-23

The user requested a low-effort agent to assess whether hosted models could reduce download and local execution time. This was a read-only review. Paid OpenRouter inference is not authorized; the existing TypeSafe $1 cap is separate.

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

The [official billing FAQ](https://openrouter.ai/docs/faq) describes credit purchases and a purchase fee. This review did not establish a current minimum deposit or numerical fee. A proposed separate $1 inference cap is a recommendation only; it is not a credit purchase or spending authorization. Prices and provider availability must be checked again before any authorized paid run.
