# Remaining local generic prompt work

The frozen roster has 11 local generic IDs. Four completed Qwen3 0.6B SDK conditions cover two IDs, leaving **nine IDs and 18 P1/P2 conditions**. The “seven configs” shorthand would omit two roster IDs, so this inventory retains all nine. None has an executable, model-specific P1/P2 controller or exact variant token preflight yet.

| Frozen ID | Condition order | Historical P0 surface | P1/P2 state |
|---|---|---|---|
| `qwen3-0.6b-q4km-nonthinking` | P1, P2 | local HTTP | not started |
| `qwen3-1.7b-sdk-thinking-on` | P2, P1 | LM Studio SDK | not started |
| `qwen3-1.7b-sdk-thinking-off` | P1, P2 | LM Studio SDK | not started |
| `qwen3.5-4b-sdk-thinking-on` | P2, P1 | LM Studio SDK | not started |
| `qwen3.5-4b-sdk-thinking-off` | P1, P2 | LM Studio SDK | not started |
| `gemma4-e2b-sdk-thinking-on` | P1, P2 | LM Studio SDK | not started |
| `gemma4-e2b-sdk-thinking-off` | P2, P1 | LM Studio SDK | not started |
| `gemma4-e4b-sdk-thinking-on` | P1, P2 | LM Studio SDK | not started |
| `gemma4-e4b-sdk-thinking-off` | P2, P1 | LM Studio SDK | not started |

All nine have saved 60-record P0 development files and P0 artifact manifests, bound in [remaining-local-inventory.json](remaining-local-inventory.json). Only Gemma4 E4B has a saved historical P0 preflight file; that does not establish P1/P2 token fit. The P0 runners support offline prompt previews but block direct P1/P2 execution. The [route snapshot](../local-route-recheck-2026-09-24/README.md) found no exact serving endpoints at its timestamp; refresh it before a later run. Do not substitute another model generation, size, or Gemma family.

No remaining model was loaded or invoked for this inventory.
