# Gemini through OpenRouter

The user authorized Gemini through OpenRouter on 25 September 2026. These hosted configurations use new P0 baselines; earlier Antigravity results remain separate. The existing aggregate $10 OpenRouter cap applies. Only the 60 synthetic development reviews are in scope.

The roster has Gemini 3.1 Pro low/high, 3.6 Flash low/medium, and 3.7 and 3.8 Flash low/medium/high. Each configuration uses a three-review smoke before six batches of ten reviews. P1 and P2 use the same hosted baseline, provider and effort. No reference labels enter the requests.

The selected provider is Google AI Studio's standard endpoint, with fallback disabled. Published rates in the saved catalog are $2/M input and $12/M output for Pro, and $0.75/M input and $3.75/M output for Flash. The locked budget ledger reserves a conservative request bound before inference and retains unknown charges. Reservations are not bills. See the [catalog](../results/gemini-openrouter-prep-v1/catalog.json) and [OpenRouter provider controls](https://openrouter.ai/docs/guides/routing/provider-selection).

The runtime is OpenRouter's hosted chat-completions API routed to Google AI Studio. The saved requests and raw responses retain exact model IDs and returned revisions. Provider hardware and quantization are not recorded, so they remain unknown; the Mac is only the API client for these runs.

## Preserved routing failures

The first ten smoke requests received HTTP 404 at `Filter by Max Price`. They returned no model response or billing receipt. Version 1 set zero request and image price ceilings alongside token price ceilings. Those filters are inappropriate for choosing a multimodal endpoint for a text-only workload. Version 2 keeps the prompt/completion price ceilings and removes the other two filters. Both versions and all attempted requests are preserved.

The ten unknown charge reservations total $1.02345625. They were retained conservatively; unused allocations were released. This is not evidence that OpenRouter charged $1.02345625. See the [reconciliation](../results/gemini-openrouter-prep-v1/p0-routing-failure-reconciliation.json).

## Successful route check

The corrected Gemini 3.8 Flash low smoke returned three valid categorical responses. Its observed charge was $0.001704, with 1,552 prompt tokens, 144 completion tokens and zero reported reasoning tokens. Immediate generation metadata was unavailable, so the controller stopped with `identity_unverified`. A later read-only lookup verified the same generation ID, Google AI Studio, and `google/gemini-3.8-flash-20260902`. No inference was repeated.

The metadata reports 1,209 ms of generation time for the complete three-review batch, separately from 807 ms in its latency field. Neither figure establishes pure accelerator inference time or individual-review latency. [OpenRouter generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-generation) supplies the timing, native token counts and observed charge.

A separate recovery receipt must bind the original request, responses, terminal journal and recovered metadata before development proceeds. Recovery must preserve the original stop and must not repeat the paid smoke. Future metadata lookups may retry the read-only GET; model requests have no automatic retries.

## First completed hosted baseline

Gemini 3.8 Flash low completed all 60 reviews in six requests. The development requests reported 11,227 input tokens, 3,486 output tokens and $0.02149275 in charges. The three-review smoke cost $0.001704 separately.

Generation metadata was also delayed for development batch 1. A later read-only lookup verified its response. The original files keep the initial status; a hash-bound recovery proof and separate continuation record batches 2–6. No completed request was repeated.

Version 3 verifies the exact response provider and model when those fields are present. Missing provider identity requires a successful generation lookup; a conflicting identity stops the configuration. Timing metadata can arrive later without invalidating a response whose identity is already verified. Inference POST requests are never retried automatically.

The remaining nine hosted baselines use distinct budget partitions and run concurrently. A completed smoke is inspected before its development requests are admitted. Only closed, validated results enter the public website.

## Completed prompt comparison

Nine hosted model/effort configurations completed P0, P1 and P2, for 27 development runs and 1,620 review responses. Five ten-review batches had invalid output and remain in the results. All other batches were valid. Gemini 3.8 Flash high stopped at its P0 smoke with HTTP 429; its P1/P2 runs were not sent. No completed inference was repeated.

The 27 completed configurations cost **$2.328085 including their smoke tests**. The rate-limited smoke has no reported bill; its $0.071826 reservation remains an unknown-cost upper bound. After all Gemini partitions were closed, the aggregate OpenRouter ledger accounted for $6.01078369650 against the $10 cap, including earlier unknown-charge bounds. This ledger total is not an observed provider bill. See the [completed partition reconciliation](../results/gemini-openrouter-prep-v3/completed-budget-reconciliation-v1.json).

Gemini 3.8 Flash low matched all four reference judgments on 57/60 reviews at P0 and 56/60 at both P1 and P2. All three runs had 60 valid responses. These are single-pass observations; repeated runs would be needed to assess variation. The public prompt comparison preserves changed review IDs and their original responses.

Each request classified ten reviews. Provider generation duration, when available, describes that batch. It is never divided by ten and presented as measured per-review inference latency. Missing server timing remains unavailable.
