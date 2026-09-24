# Local to hosted routing review

Direct public OpenRouter API checks completed **2026-09-24 13:20 UTC**, with no API key, inference, or downloads. The current `GET /api/v1/models` returned 458 model records. Endpoint lists were fetched directly for all seven pending model families and DeepSeek R1 Distill Qwen 32B. The machine-readable file contains the ID-by-ID catalog snapshot and provider endpoint records.

| Local family | Configs | Current exact endpoint result | Routing disposition |
|---|---:|---|---|
| Qwen3 0.6B | 3 | Catalog ID absent. Exact endpoint URL returned HTTP 200 but zero endpoints. | No current serving provider observed. |
| Qwen3 1.7B | 2 | Catalog ID absent. Exact endpoint URL returned HTTP 200 but zero endpoints. | No current serving provider observed. |
| Qwen3.5 4B | 2 | Catalog ID absent; exact endpoint URL returned HTTP 404. | Do not substitute Qwen3 4B. |
| Qwen3 8B | 2 | One endpoint: Alibaba (`alibaba`), $0.117/M input and $0.455/M output. `reasoning` and `response_format` listed; no `structured_outputs` or `reasoning_effort` in this endpoint record. | Exact hosted candidate verified; use a separate hosted config. |
| Qwen3.8 27B | 1 | Sixteen provider records returned. Prices range $0.094–$0.45/M input and $1.80–$4.40/M output. The endpoint records include reasoning and, for the providers, `reasoning_effort`; structured output support varies by provider. | Exact hosted candidates verified; use a separate hosted config and select provider/price/controls explicitly. |
| Gemma 4 E2B | 2 | Catalog ID absent; exact endpoint URL returned HTTP 404. | Do not substitute Gemma 3n E2B. |
| Gemma 4 E4B | 2 | Catalog ID absent; exact endpoint URL returned HTTP 404. | Do not substitute Gemma 3n E4B. |

All local entries are quantized Q4_K_M GGUF runs. Hosted quantization is provider-specific or unknown, so these routes do not reproduce the local runtime. Keep completed local P0 results; do not rerun.

## Additional targets

`mistralai/mistral-small-2603` returned three Mistral provider endpoint records: `mistral/zdr` and `mistral` at $0.15/$0.60 per million input/output tokens; `mistral/eu` at $0.165/$0.66. All list `reasoning`, `reasoning_effort`, `response_format`, and `structured_outputs`. The catalog identifies it as Mistral Small 4, Hugging Face `mistralai/Mistral-Small-4-119B-2603`. This is endpoint evidence only; no retry or inference was performed.

`deepseek/deepseek-r1-distill-qwen-32b` returned HTTP 200 with zero endpoints. The exact model record exists, but this snapshot has no serving provider.

## Evidence

The public [model catalog](https://openrouter.ai/api/v1/models) and endpoint lists are documented in OpenRouter’s [endpoint API reference](https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints). The JSON records per-target HTTP status, exact catalog-ID presence, endpoint counts, provider tags, endpoint prices, quantization, supported parameters, and recent uptime: [`results/routing-review-2026-09-24.json`](../results/routing-review-2026-09-24.json).

## Exact local prompt preflight follow-up

Read-only verification on 24 September 2026 confirmed the remaining SDK limitation. Installed `@lmstudio/sdk` 1.5.0 implements `applyPromptTemplate` using the model handle's internal configuration stack (`dist/index.cjs:17476`); its public options do not accept the prediction-time template. The existing benchmark supplies its thinking/effort template to `respond` per request. Counting a default rendering therefore does not prove the actual request length. The installed `lms --help` lists no model-default configuration command. No private SDK state, settings or model loads were changed during this check.

A supported path worth testing next is LM Studio's [per-model prompt template override](https://lmstudio.ai/docs/app/advanced/prompt-template), followed by its public [template rendering and tokenization](https://lmstudio.ai/docs/typescript/tokenization). Once the native specialist GPU lane is idle, save the selected model's existing defaults, apply the exact already-pinned effective template, and verify that the SDK rendering uses it. Check all 60 P0/P1/P2 requests against the unchanged input/output budget before smoke inference, and restore the saved defaults afterward. Record the settings transition and rendered token hashes. This is an untested next step, not evidence that local prompt runs are ready or authorization to rerun the three configurations with hosted routes.
