# OpenRouter cost review — 2026-09-23

The user requested a low-effort agent to assess whether hosted models could reduce download and local execution time. This was a read-only review. The subsequent user instruction authorized reasonably priced hosted matches instead of downloading them. The latest user instruction explicitly approves paid OpenRouter for non-GPT/Claude models, prioritizes hosted execution over LM Studio where equivalent routes exist, and sets a $10 total OpenRouter inference cap (raised from $5 on September 24). Earlier spending counts toward $10; the existing TypeSafe $1 cap is separate.

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

The [official billing FAQ](https://openrouter.ai/docs/faq) describes credit purchases and a purchase fee. This review did not establish a current minimum deposit or numerical fee. After this review, the user authorized reasonably priced hosted matches. The implementation now uses a separate aggregate $5 inference cap; no credit purchase or automatic top-up is authorized. Prices and provider availability must be checked again before any authorized paid run.

## Hosted execution decision

The live endpoint snapshot and model reasoning metadata are saved in `results/openrouter-paid-planning-2026-09-23/`. Exact providers and remaining configurations are listed in `results/openrouter-paid-run-registry.json`; they must be revalidated before requests. Existing completed local results remain intact. DeepSeek-R1-Distill-Qwen-32B, Gemma E4B and specialist models stay local because no exact hosted route was established. Stopped partial downloads are preserved. The paid runner must reserve each request against the shared budget before sending, reconcile reported cost, stop on unknown billing or the first request failure, and inspect three smoke responses before a full60 run.

The first Mistral119B smoke returned an upstream HTTP429 without reported usage cost. Its full $0.04177920 maximum reservation is permanently counted against the cap, with actual cost still unknown; an explicit ledger event records the evidence hash. This is not a zero-charge assertion or an automatic retry. The separate Mistral24B/DeepInfra FP8 smoke passed all three records and reported $0.00034845 total cost. Hosted development proceeds only after smoke inspection, with no fallback provider.

The original plan also reserved a hosted DeepSeek slot independent of the local32B distill. The September23 public [DeepSeek V4.1 Flash endpoint metadata](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints) lists `open-inference/fp4` at flat $0.10/$0.50 per million input/output tokens, with structured output and reasoning support. This is about $0.01925 for the same illustrative60-record token volume. Off/low/high are queued under the existing aggregate cap; max is excluded. It is a separate model comparison, not a renamed or equivalent32B distill.

## Measured cost checkpoint

The Qwen3.6-35B-A3B hosted runs completed all 60 records with thinking off and on. Their development calls cost $0.0072576 and $0.0636796 respectively; the three-record smokes cost $0.0004834 and $0.0025828. These are observed costs from the [saved runs](../results/openrouter-paid-run-registry.json), rather than the common-workload estimates above.

At this checkpoint, the [shared ledger](../results/openrouter-paid-budget.jsonl) records $0.0752812 in known charges and $0.0521984 in conservative upper bounds for two attempts with unknown charges. Total accounted spending is $0.1274796, leaving $0.8725204 of the $1 cap; there are no unresolved reservations. The upper bounds are not measured charges. No additional deposit is needed for this capped work based on the previously checked account balance, although balance and endpoint availability must be rechecked before further authorized calls.

## Earlier destination review and subsequent approval

Automatic approval review rejected two three-record smoke commands on September 23 before either command executed:

| Requested model | Provider | Control | Review outcome |
| --- | --- | --- | --- |
| `deepseek/deepseek-v4.1-flash` | `open-inference/fp4` | off; $0.10/$0.50 per million input/output tokens | Review could not confirm explicit approval for this payload and destination. |
| `google/gemma-4-26b-a4b-it` | `deepinfra/fp8` | off; $0.07/$0.34 per million input/output tokens | Review acknowledged the reasonably priced substitution authorization but still required explicit approval of the payload and specific model/provider. |

Both commands specified 4,096 maximum output tokens, a 300-second timeout and the shared $1 cap. Neither command ran: no feedback payload was sent, no inference charge was incurred, and no budget reservation or smoke output was created by these rejected commands. Neither was retried or routed through another execution path.

The earlier authorization to use reasonably priced OpenRouter replacements remains recorded above. The repository describes the feedback as entirely synthetic, with no actual candidate records ([agreed scope](../README.md#agreed-scope), [accepted decisions](PLAN.md#accepted-decisions)). Approval review nevertheless required confirmation scoped to these destinations. Their off configurations were recorded as `pending_explicit_destination_approval` in the [paid registry](../results/openrouter-paid-run-registry.json). The user subsequently explicitly approved paid OpenRouter for models outside GPT and Claude and raised the total cap to $5. The controller treated those approvals as authorization for this synthetic benchmark, but the subsequent automatic review below still required exact route and payload confirmation. Execution also requires the price, endpoint, smoke and ledger checks. Existing successful outputs and recorded charges remain unchanged.

The cap increase is recorded as an append-only ledger amendment, preserving every earlier reservation and settlement. With the $0.1274796 checkpoint accounted above, the amended cap leaves $4.8725204 before new runs. Paid GPT/Claude calls remain excluded; those benchmarks use subscriptions. No top-up or credit purchase is authorized.

## Renewed Gemma review rejection after the $5 approval

The user then stated: "paid openrouter usage is approved for models outside of gpt and claude, prioritize them over running them on lm studio, use lm studio where its a must and no other option" and "you can use up 5 dollars, but dont go wild".

After the tested cap amendment, the controller submitted one Gemma smoke command for `google/gemma-4-26b-a4b-it`, provider `deepinfra/fp8`, reasoning off, price ceilings $0.07/$0.34 per million input/output tokens, 4,096 output tokens and a 300-second timeout. Its approval justification explicitly identified the synthetic feedback, absence of real candidate data/reference labels, exact destination and $5 aggregate cap.

Automatic approval review rejected that command before execution. It said general paid OpenRouter authorization did not explicitly authorize the exact provider/model route and payload for external transmission. No command ran, payload was sent, reservation was created or charge was incurred by this rejection. There was no retry or workaround. The Gemma26 off registry entry returns to `pending_explicit_destination_approval`; all paid dispatch is paused for one scoped approval covering the table below. Other configuration statuses retain their existing evidence.

The ledger remains unchanged by this rejected command: $0.0752812 observed charges plus $0.0521984 retained unknown-cost upper bounds, $0.1274796 accounted, $4.8725204 remaining under the $5 total cap, and no unresolved reservation. Retained bounds are not observed charges.

### Exact planned destinations for scoped approval

All requests go through OpenRouter to only the specified provider route, without provider fallback. The payload is the existing 60 entirely synthetic feedback texts plus the classification policy and JSON output schema, sent one feedback record per independent request. Each new configuration first uses DEV001-003 for smoke, then the existing 60 development records after inspection. Reference labels, generation metadata, real candidate information and authentication secrets are excluded from prompt payloads. The API credential is used only for the normal authenticated request. No paid GPT or Claude route, top-up or cap increase is included.

| Exact model ID | Exact provider route | Planned controls | Current execution boundary |
| --- | --- | --- | --- |
| `qwen/qwen3.8-27b` | `deepinfra/bf16` | off, medium, xhigh | Smoke then development; separate hosted configuration from local low |
| `qwen/qwen3.6-35b-a3b` | `akashml/fp8` | off, on | Already complete; included for destination accounting, no rerun planned |
| `google/gemma-4-26b-a4b-it` | `deepinfra/fp8` | off, on | Off command rejected before execution; smoke required for each |
| `google/gemma-4-31b-it` | `deepinfra/turbo` | off, on | Smoke required for each |
| `mistralai/mistral-small-3.2-24b-instruct` | `deepinfra/fp8` | reasoning not applicable | Existing 8 valid development records retained; any explicit continuation starts at DEV009 in a new attempt file |
| `mistralai/mistral-small-2603` | `mistral/zdr` | none, high | Earlier none smoke HTTP429 retained; no automatic retry; high needs smoke |
| `deepseek/deepseek-v4.1-flash` | `open-inference/fp4` | off, low, high | Separate hosted DeepSeek slot; smoke required for each |

The [paid registry](../results/openrouter-paid-run-registry.json) is the configuration source. Live endpoint status, reasoning support and prices must still pass the adapter's strict checks before any request. These rows do not imply that a route is currently healthy or that all runs will fit the remaining cap.

## Explicit approval of the destination table

After the exact seven model/provider routes and the 60-record synthetic payload were presented in chat, the user replied: "I already told you I approved, rock and roll moe forward". This confirms the listed destinations and payload under the existing $5 total cap. The benchmark resumes with strict endpoint pricing, no provider fallback, inspected smoke responses and shared-ledger reservations. Earlier review rejections remain preserved above; no further user confirmation is required for these approved routes.


## Parallel execution under the same $5 cap

The user requested concurrent OpenRouter runs on September 23. Ten remaining configurations now have independent $0.35 budgets, allocated by [the partition manifest](../results/openrouter-paid-partitions-2026-09-23/manifest.json). The $3.50 allocation reserves capacity; it is not a charge. Before allocation, known charges plus conservatively retained unknown-cost bounds totaled $0.16783330. The master ledger therefore encumbered $3.66783330 and left $1.33216670 unallocated under the existing $5 cap.

The [partition allocator](../scripts/paid_budget_partitions.py) binds each worker to one model, provider and reasoning setting. Each worker holds its own ledger lock and can run concurrently with other configurations. Master-ledger inference is blocked while partitions are active, preventing overlapping use of reserved capacity. Every configuration still requires an inspected three-record smoke before development. A failure stops that configuration without stopping unrelated funded configurations.

Terminal reconciliation locks and seals the child ledger, records known charges and unknown-cost bounds separately, and releases only unused capacity. A child with unresolved billing cannot be reconciled. The original ledger and all earlier unknown bounds remain intact. Partition totals are labeled separately from the aggregate cap; they must not be reported as global spending. No paid GPT/Claude calls, credit purchases or budget increase are authorized by this change.

## Offline frozen prompt previews

The [paid adapter](../scripts/openrouter_paid_benchmark.py) supports `--prompt-variant P0|P1|P2`, `--parent-baseline-id`, `--variant-preview-output` and `--variant-baseline-attempts`. Preview mode uses a saved attempt JSONL for the exact model/provider snapshot and baseline request controls. Supply the same model, provider, reasoning, token limit and price ceilings as that baseline. A mismatch is rejected. The usual phase and start arguments select only permitted synthetic inputs.

Preview mode reads no API key or budget ledger and makes no network request. Its artifact explicitly labels availability, prices and runtime identity as unverified saved evidence. P0 reproduces the existing request; P1 and P2 append their frozen additions to the complete system instruction while preserving feedback serialization, schema and provider controls. Live P1/P2 execution is blocked before credential or billing access until phase-two gates are met. The default live path retains its original P0 payload and has no frozen-bundle dependency. Saved-payload parity and these gates are covered by [the preview tests](../tests/test_openrouter_prompt_variants.py).


## Mistral 24B alternate provider

The DeepInfra FP8 configuration paused after repeated HTTP 429 responses, retaining 19 valid outputs across 21 unique attempted records and 39 unattempted records. Its raw attempts and unknown-charge bounds remain preserved. A September 23 public [endpoint check](https://openrouter.ai/api/v1/models/mistralai/mistral-small-3.2-24b-instruct/endpoints) also listed Venice FP8 with structured outputs at $0.09375/$0.25 per million input/output tokens.

Venice is a separately identified provider configuration for the same Mistral model, with no automatic fallback and no pooling with DeepInfra results. Its three inspected smoke responses were valid; full development execution then started under a separately reserved $0.35 child budget within the existing $5 aggregate cap. [Smoke inspection](../results/openrouter-mistral24-venice-na-2026-09-23/smoke-inspection.json) records the controls and runtime limitations. Exact serving weights and hardware are undisclosed. The two Mistral 119B effort configurations remain blocked by their provider rate limits.

## September 24 cap increase and parallel continuations

The user explicitly raised the total OpenRouter inference approval to $10 and requested aggressive parallel execution. The [master ledger](../results/openrouter-paid-budget.jsonl) preserves the previous $5 approval and all earlier charges, then appends the $10 amendment. At amendment, known charges plus unknown-charge bounds totaled $1.62462814050, leaving $8.37537185950 before new allocations. Historical $5 snapshots above remain unchanged. TypeSafe retains its separate $1 cap, and no subscription overage or credit purchase is authorized.

Versioned budget helpers preserve the source hashes used by historical runs. Concurrent conditions receive separate child allocations; their sum remains bounded by the shared master. Provider failures stop the affected condition without automatic retry.
