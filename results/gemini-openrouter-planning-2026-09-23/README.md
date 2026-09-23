# Gemini OpenRouter planning, 2026-09-23

Public, unauthenticated metadata only. No inference, feedback transmission, credential use or registry changes. Catalog and endpoint JSON retain the source URLs; these are advertisements, not proof of successful requests.

| Candidate | Provider suitable for frozen temperature | Advertised input/output USD per million | Assumed 60-record cost | Catalog effort support |
| --- | --- | --- | --- | --- |
| `google/gemini-3.8-flash` | `google-ai-studio`, status0 | 0.75 / 3.75 | 0.14437125 | low, medium, high; reasoning mandatory |
| `google/gemini-3.7-flash` | `google-ai-studio`, status0 | 0.75 / 3.75 | 0.14437125 | low, medium, high; reasoning mandatory |
| `google/gemini-3.6-flash` | `google-ai-studio`, status0 | 0.75 / 3.75 | 0.14437125 | minimal, low, medium, high; reasoning mandatory |
| `google/gemini-3.1-pro-preview` | `google-ai-studio` or `google-vertex/global`, status0 | 2 / 12 below200K prompt tokens | 0.423096 | low, medium, high; reasoning mandatory |

The catalog has no exact `google/gemini-3.1-pro` ID. Preview and customtools are separately named entries; preview must not silently be claimed identical to the native Antigravity model. None of the hosted paths reproduces Antigravity's wrapper workflow. Preserve its existing registry entries and add separate hosted configuration IDs only after approval and adapter review.

Estimates apply the observed Qwen workload assumption of97,230 input and19,053 generated tokens, including reasoning, to each model's advertised prompt/completion rates. They exclude smoke, retries, cache effects, extra services and changes in tokenization/reasoning length. Internal reasoning is listed separately at the completion rate; estimates assume it is part of those19,053 output tokens and do not charge it twice. This billing interpretation still needs primary documentation and guard tests before execution. The advertised discount field is not applied again to listed rates.

Cheaper Vertex flex Flash routes advertise0.375/1.875 per million and an assumed0.072185625 per60, but omit temperature from supported parameters. The current benchmark must not silently discard its frozen temperature to use them. Batch listings have the same cheaper rates but introduce a separate batch-service workflow. Pro flex advertises1/6 with temperature support and an assumed0.211548 per60; it retains the price tiers and distinct service characteristics. Raw endpoint evidence includes global, priority and regional routes; no fallback is selected.

Start with one Flash3.8 low hosted comparison after scoped destination approval and adapter preparation. Under the common workload assumption, the original11 native effort slots mapped to9 Flash and2 Pro hosted runs would cost about2.14553325 before smokes/retries, but that is neither a spending guarantee nor authorization to erase the remaining baseline roster. Keep the $5 aggregate cap and measure the first smoke before committing further scope. Gemini3.6 minimal and Pro medium are additional advertised controls outside the original native registry and should be listed as pending decisions rather than silently run or excluded.

Execution blockers: Gemini IDs are absent from the paid adapter allowlist. Its strict nonzero-extra-fee guard rejects image/audio/search/internal_reasoning pricing; Pro also has tiered overrides. Cache read/write rates are already conservatively included in the existing input-price bound. Do not weaken those guards wholesale. A reviewed text-only Gemini pricing path must establish which fees can actually apply, prohibit extra services, bound tiered reservation cost, and test observed billing before use. Exact destination approval remains pending. No GPT/Claude paid models are included.

Sources: [OpenRouter catalog](https://openrouter.ai/api/v1/models), [Flash3.8 endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints), [Flash3.7 endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.7-flash/endpoints), [Flash3.6 endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.6-flash/endpoints), [Pro3.1 preview endpoints](https://openrouter.ai/api/v1/models/google/gemini-3.1-pro-preview/endpoints).

## Billing documentation check

OpenRouter's [reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) treats reasoning as billed output and says most providers share the top-level output limit between reasoning and visible output. Its Gemini section distinguishes `reasoning.max_tokens`: Gemini 3 maps that value to a thinking level, without precise token control. A Gemini spending guard must not treat a requested reasoning budget as a guaranteed independent bound. Until the selected route's total-output accounting is verified, use the advertised endpoint completion bound conservatively when reserving reasoning cost. This is a planning constraint; no Gemini inference has run.

The official [pricing schema](https://github.com/OpenRouterTeam/terraform-provider-openrouter/blob/main/docs/data-sources/model.md) also lists a separate internal-reasoning rate. The candidate estimates above assume reasoning is already part of the stated output workload; they are not the reservation formula and must not weaken the aggregate cap.
