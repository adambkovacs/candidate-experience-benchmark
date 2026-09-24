# Local generic route recheck — 24 September 2026

At this snapshot, the 11 frozen local generic configurations have no observed exact serving route on OpenRouter. This is a route finding, **not execution approval**. The 22 P1/P2 development conditions remain uncompleted. One condition, Qwen3 0.6B SDK thinking-on P2, has a completed three-record local smoke and is held after the user’s routing question.

The unauthenticated [OpenRouter model catalog](https://openrouter.ai/api/v1/models) returned 458 records with none of the five exact family IDs. Exact Qwen3 0.6B and 1.7B [endpoint lists](https://openrouter.ai/docs/api/api-reference/endpoints/list-all-endpoints-for-a-model) returned HTTP 200 with zero providers; their `:free` aliases also returned zero. The Qwen3.5 4B and Gemma 4 E2B/E4B endpoint URLs returned HTTP 404. The Qwen3 8B positive control returned one provider, confirming that the endpoint check was functioning. Raw response bodies and hashes are in [evidence.json](evidence.json) and `endpoint-*.json`. A later provider change requires a fresh check.

| Frozen configuration | Scheduled order | Saved P1/P2 status |
|---|---|---|
| `qwen3-0.6b-q4km-nonthinking` | P1, P2 | Both development conditions unstarted |
| `qwen3-0.6b-sdk-thinking-on` | P2, P1 | P2 smoke 3/3; no development; P1 unstarted |
| `qwen3-0.6b-sdk-thinking-off` | P1, P2 | Both development conditions unstarted |
| `qwen3-1.7b-sdk-thinking-on` | P2, P1 | Both development conditions unstarted |
| `qwen3-1.7b-sdk-thinking-off` | P1, P2 | Both development conditions unstarted |
| `qwen3.5-4b-sdk-thinking-on` | P2, P1 | Both development conditions unstarted |
| `qwen3.5-4b-sdk-thinking-off` | P1, P2 | Both development conditions unstarted |
| `gemma4-e2b-sdk-thinking-on` | P1, P2 | Both development conditions unstarted |
| `gemma4-e2b-sdk-thinking-off` | P2, P1 | Both development conditions unstarted |
| `gemma4-e4b-sdk-thinking-on` | P1, P2 | Both development conditions unstarted |
| `gemma4-e4b-sdk-thinking-off` | P2, P1 | Both development conditions unstarted |

No different model generation, size, or Gemma family is substituted. Existing P0 local runs remain P0. For any future local P1/P2 execution, first retain the frozen prompt/runtime controls, complete model-specific offline context preflight, and obtain the separate review gate. The Qwen0.6 smoke rows do not satisfy the 60-record development denominator.

Sources: [frozen roster](../prompt-comparison-v1-2026-09-24/roster.json), [frozen schedule](../prompt-comparison-v1-2026-09-24/schedule.json), [global journal](../prompt-comparison-v1-2026-09-24/execution-journal.jsonl), [Qwen0.6 smoke terminal](../qwen06-prompt-exact-v1/thinking-on-P2/smoke.terminal.json), and [prior routing review](../../docs/LOCAL_HOSTED_ROUTING_REVIEW.md).
