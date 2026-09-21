# First local development run

On 2026-09-21, the Qwen3-0.6B Q4_K_M configuration returned valid JSON for all 60 development records, but matched all four provisional reference labels on zero records. It predicted testimonial potential for every record and returned `no` for 19 of 25 reference-positive serious concerns. These results support investigating this configuration before using it for triage.

## Results

| Judgment | Correct / 60 | Accuracy | Macro-F1 |
| --- | ---: | ---: | ---: |
| Sentiment | 37 | 61.7% | 0.313 |
| Follow-up needed | 54 | 90.0% | 0.604 |
| Serious concern reported | 13 | 21.7% | 0.212 |
| Testimonial potential | 9 | 15.0% | 0.087 |

Serious-concern recall was 5/25 (20%). The other 20 comprised 19 outright misses and one `insufficient_information` response. Seven reference-negative cases triggered false escalation. Testimonial precision was 9/60 (15%). None of the six controlled pairs had both records fully correct; four preserved their designated invariants.

All 60 outputs passed the categorical schema; there were no transport errors, truncations or refusals. This illustrates that valid structured output does not establish correct judgments.

## Smoke gate

The three-record smoke test ran first, and the controller inspected all raw responses before authorizing the full run. All three were valid. DEV-002 described a friendly interview with no complaints but received negative sentiment. DEV-003 described a missed interview and unanswered emails but received testimonial potential `yes`. Those errors justified measuring the full development failure pattern without changing settings.

The full run uses a new output file and includes all 60 unique records, including the three smoke records. Total requests: 63. No retries, output repair, reference changes or prompt tuning occurred. The smoke evaluator intentionally lists the other 57 records as missing; those are unattempted smoke cases, not service failures.

## Configuration and timing

- Artifact: [lmstudio-community/Qwen3-0.6B-GGUF](https://huggingface.co/lmstudio-community/Qwen3-0.6B-GGUF/blob/3334d820ab76652cf6e242d7c6302b10f0951f23/Qwen3-0.6B-Q4_K_M.gguf), revision `3334d820ab76652cf6e242d7c6302b10f0951f23`, Q4_K_M, 484,219,808 bytes. The local SHA-256 matched the publisher's value.
- Apple M4 Max, 16 CPU cores, 40 GPU cores, 128 GB unified memory; macOS 26.6 (25G5028f).
- LM Studio 0.4.16+2; CLI commit `efce996`; selected GGUF runtime `llama.cpp-mac-arm64-apple-metal-advsimd@2.22.0`. Runtime logs identify the LlamaV4 backend.
- Context 8,192; GPU offload requested at maximum; parallelism one; temperature zero; maximum 512 output tokens; strict JSON schema. Other sampling options used runtime defaults. The artifact includes an LM Studio chat-template override, preserved in the metadata artifact.
- No reasoning override was sent. Runtime initialization reported thinking disabled; all responses reported zero reasoning tokens.

The 60 request durations summed to 32.29 seconds. Median latency was 0.552 seconds; nearest-rank p95 was 0.702 seconds. These are local HTTP end-to-end durations after model loading and the smoke test. The backend used warmup and a shared-prefix prompt cache; fresh message lists prevent conversation carryover, but do not disable caching.

Low Power Mode was enabled. Before inference, macOS reported AC power with the battery charging at 22%. Three other specialized models remained loaded and were idle at inspection. This was a shared machine, without continuous workload isolation. Do not present these timings as controlled hardware performance or compare them directly with subscription CLI process timings. Download, load and setup time are excluded. Energy was not measured.

## Evidence and limitations

[Run manifest](../results/qwen3-0.6b-q4_k_m-2026-09-21/manifest.json), [raw predictions](../results/qwen3-0.6b-q4_k_m-2026-09-21/development.jsonl), [evaluation](../results/qwen3-0.6b-q4_k_m-2026-09-21/development-evaluation.json), [request bodies](../results/qwen3-0.6b-q4_k_m-2026-09-21/development-requests.jsonl), [file-read audit](../results/qwen3-0.6b-q4_k_m-2026-09-21/development-input-audit.json), [all disagreements](../results/qwen3-0.6b-q4_k_m-2026-09-21/disagreements.json), and [GGUF metadata](../results/qwen3-0.6b-q4_k_m-2026-09-21/gguf-metadata.json) are retained.

The inference controller enforced a three-file allowlist: feedback inputs, rubric and schema. Reference labels were read separately after inference for evaluation. Every request contained only the rubric, schema and one feedback text. The new offline isolation test checks permitted reads and exact feedback-only payloads.

The references are same-assistant AI-reviewed provisional labels on deliberately enriched development data. Disagreements have not been independently adjudicated. Findings apply to this artifact, conversion, prompt, template, settings and runtime together; they do not isolate why the configuration failed or establish a general Qwen ranking.

The original installed inventory contained only embedding/reranking models. The user then authorized downloading the small Qwen candidate named in the plan. A stalled download was resumed at the pinned revision, verified, imported and made visible by cancelling the stale download entry. No hosted inference was used for this local run. The remaining 340 dataset records remain ungenerated.
