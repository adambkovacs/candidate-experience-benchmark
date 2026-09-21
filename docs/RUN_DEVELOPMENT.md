# Run the development smoke test

No model has been benchmarked yet. The [local preflight](LOCAL_PREFLIGHT.md) verified the Mac setup and offline tests, but found no suitable downloaded instruction model. This runner executes on the Mac with LM Studio.

## Setup and execution

Use Python 3.10 or later. No Python packages are required.

1. Pull the latest recruitment-feedback-demo repository on the Mac.
2. In LM Studio, load a supported instruction model and start its local server. Copy its exact model identifier.
3. Run from the repository root:

```bash
python3 scripts/development_benchmark.py validate
python3 scripts/development_benchmark.py run --model 'EXACT_MODEL_ID' --limit 3 --output smoke-local.jsonl --config-note 'M4 variant; LM Studio version; artifact; quantization; context; power mode'
python3 scripts/development_benchmark.py evaluate --predictions smoke-local.jsonl
```

Replace the model/config placeholders. The three-record smoke evaluation deliberately reports the other 57 records as missing. To run all 60, omit --limit and use a NEW output filename. Existing output files are never overwritten. If local server authentication is enabled, configure LM_STUDIO_API_KEY through your normal local environment; do not commit it.

The server defaults to http://localhost:1234/v1. This runner only accepts localhost HTTP endpoints. It cannot spend money on hosted providers. It makes no retry or silent fallback request.
Structured-output support is checked through actual response validation; unsupported model/runtime combinations will be recorded as failures. Confirm the selected loaded artifact locally and inspect requested_model/returned_model in the log.

Official endpoint documentation: https://lmstudio.ai/docs/developer/openai-compat/chat-completions

## Input separation

The run command reads only inputs.jsonl, the judgment portion of LABELING_GUIDE.md, and the output schema. Metadata, rationales and reference labels are never included in requests. It uses a fresh message list per record. The evaluate command reads the reference labels locally after predictions exist.

## Interpretation

Scores compare with AI-reviewed provisional references on development data. They are diagnostic, not held-out quality claims.
Malformed JSON, extra fields, invalid enums, refusal and truncated output are invalid_output; HTTP/timeouts are service_error. Raw model responses and elapsed time are retained. Missing or invalid outputs count against accuracy and recall.
Serious reports predicted no are shown separately from insufficient_information and failed/missing output. Pair consistency is not correctness: the report shows both.

No model-only speed, paid cost, demographic fairness, legal compliance or production readiness can be inferred from this smoke test. Latency summaries and matched review-budget evaluation will be added for final runs.
