# Gemma 31 reasoning-off repeat study

All three passes of P0, P1 and P2 are complete on the same 60 synthetic development reviews. Every condition/pass has 60 valid categorical responses.

| Prompt | Pass 1 all-four agreement | Pass 2 | Pass 3 | Reviews with a changed decision |
| --- | ---: | ---: | ---: | ---: |
| P0 | 56/60 | 55/60 | 55/60 | 2/60 |
| P1 | 56/60 | 54/60 | 54/60 | 5/60 |
| P2 | 55/60 | 56/60 | 54/60 | 4/60 |

The six new development phases and 18 separate smoke calls cost $0.04416486 in reported charges, with no unknown charges. Reconciliation released $0.10583514 from the $0.15 allocation. See the [budget evidence](budget-reconciliation-v1.json).

Exact route: `google/gemma-4-31b-it`, `deepinfra/turbo`, FP4, reasoning off, OpenRouter HTTP v1. Remote hardware is undisclosed. Temperature 0, output limit 4,096 tokens, strict JSON schema, no fallback or controller retries. Frozen [repeat 2](repeat2/manifest.json) and [repeat 3](repeat3/manifest.json) requests match the eligible historical pass.

Scores use the unchanged provisional v0.2 references. Reference labels were excluded from inference and opened only for offline scoring. Separate requests do not prove statistical independence; these remain 60 synthetic reviews. Stable totals can conceal changed classifications. Pure inference time is unavailable; recorded durations include client and service overhead. Reported API charges are not invoice reconciliation.
