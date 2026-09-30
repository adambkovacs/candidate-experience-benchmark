# Hosted budget checkpoint, 30 September 2026

## Update at 22:04 UTC

The approved **$12.38** ceiling is now implemented through the reviewed versioned [budget module](../scripts/openrouter_budget_v3.py) and [partition module](../scripts/paid_budget_partitions_v3.py), committed in `b12c80ae`. The master ledger amendment preserved $9.98032451750 of accounted charges and unknown bounds. Root then allocated **$0.40** to `gemma26-on-v2`, leaving **$1.99967548250** unallocated. The child allocation is reserved capacity, not a provider charge. Its separately reviewed three-record P0 smoke is dispatched; no full phase is yet admitted. Frozen older budget modules remain unchanged.

The following sections preserve the earlier pre-amendment calculation; their $10 enforcement statements describe that earlier checkpoint.

The user has authorized **$2.38 of additional OpenRouter spending capacity**, raising the intended aggregate ceiling from **$10 to $12.38**. The [master ledger](../results/openrouter-paid-budget.jsonl) still enforces **$10** at this checkpoint: the approved increase has not yet been implemented or recorded. This document makes no allocation, inference request or ledger change. It records project accounting, not an OpenRouter invoice or account balance. The [remaining roster](REMAINING_ROSTER_2026-09-29.md#hosted-configurations-still-requiring-execution) and [hosted matrix](HOSTED_PENDING_MATRIX_2026-09-29.md#current-preparation-and-execution-status) identify the unfinished configurations; each future stage still needs a fresh route, budget and admission check.

## Ledger calculation

I replayed the 1,155 events in the [master ledger](../results/openrouter-paid-budget.jsonl) with decimal arithmetic and the event rules in the [budget implementation](../scripts/openrouter_paid_benchmark.py). The ledger SHA-256 at this read was `dd311db93b794fa827034e7d6aa1bb062db3a3bc9b61aa5a8c0a1d672eee9f1e`. Each active child allocation counts at its full ceiling; after reconciliation, its known charges and retained unknown bounds replace that allocation. Closed child totals are included once, not added again to the master total.

| Accounting component | USD |
| --- | ---: |
| Known direct charges | 0.119776512 |
| Known charges from reconciled children | 7.08864853950 |
| **Known charges** | **7.20842505150** |
| Retained direct unknown-charge bounds | 0.062961664 |
| Retained unknown-charge bounds from reconciled children | 2.70893780200 |
| **Unknown-charge bounds** | **2.77189946600** |
| **Accounted against the $10 cap** | **9.98032451750** |
| **Unallocated headroom** | **0.01967548250** |

The calculation is `$7.20842505150 + $2.77189946600 = $9.98032451750`; `$10 - $9.98032451750 = $0.01967548250`. The unknown amounts retain full request reservations where billing was unavailable. They are **not observed charges**. At this read, the ledger had zero pending attempts, zero active child partitions and no blocked flag. The dated [hosted matrix](HOSTED_PENDING_MATRIX_2026-09-29.md#current-preparation-and-execution-status) independently records the same accounted amount and headroom.

## Remaining hosted work

| Exact configuration or group | Closed development phases | Funding and other boundary |
| --- | ---: | --- |
| DeepSeek V4.1 Flash low | 2/9 | P2 stopped with 46 valid, one invalid, two service failures and 11 never-sent positions; six later phases remain. Both children are sealed. A reviewed continuation and new budget admission are needed. [Interruption evidence](DEEPSEEK_LOW_INTERRUPTION_CONTINUATION_2026-09-29.md). |
| Qwen 3.8 27B medium and xhigh | 0/9 each | Proposed children of $1.00 and $0.80 are unfunded. Fresh exact-route and stage checks remain. [Admission](QWEN27_FRESH_REPEAT_ADMISSION_2026-09-29.md). |
| Gemma 4 26B reasoning-on | 0/9 | Proposed $0.40 child is unfunded. [Admission](GEMMA26_ON_FRESH_REPEAT_ADMISSION_2026-09-29.md). |
| Qwen 3.6 35B reasoning-on | 0/9 | Proposed $1.50 child is unfunded; historical service failures remain separate. [Admission](QWEN36_ON_FRESH_REPEAT_ADMISSION_2026-09-29.md). |
| DeepSeek V4.1 Flash high | 0/9 | Proposed $0.90 child is unfunded and the exact route needs a fresh check. [Admission](DEEPSEEK_HIGH_FRESH_REPEAT_ADMISSION_2026-09-29.md). |
| Mistral Small 4 119B none and high | 0/9 each | Earlier smokes returned HTTP 429. No whole-series cost proxy or child ceiling is proposed. Provider capacity, stage admission and funding remain open. [Admission](MISTRAL119_FRESH_REPEAT_ADMISSION_2026-09-29.md). |
| Gemini 3.1 Pro high | Six additional phases pending | Proposed $2 child is unfunded. Its historical first pass is separate. [High-effort plan](GEMINI_HIGH_REPEAT_WAVE.md). |

The separate free Gemma strict-schema route remains at 0/9 after an HTTP 404 smoke, with no paid substitution authorized ([disposition](GEMMA26_FREE_SMOKE_DISPOSITION_2026-09-29.md)). Qwen 3.6 reasoning-off and DeepSeek reasoning-off have their scheduled phases accounted for; their retained interruptions do not authorize replay ([roster](REMAINING_ROSTER_2026-09-29.md#hosted-configurations-still-requiring-execution)).

## Approved increase and historical $17 proposal

If the approved ceiling is safely implemented, the current ledger balance would leave `$12.38 - $9.98032451750 = $2.39967548250` of unallocated capacity. This is an accounting limit, not expected provider spending. The budget module still has a hard-coded $10 maximum ([implementation](../scripts/openrouter_budget_v2.py)); its current amendment method cannot record $12.38, and existing partition allocation opens that same module ([partition code](../scripts/paid_budget_partitions_v2.py)). The higher ceiling needs a reviewed, persistent budget-code change and a ledger amendment before any new child can use it. Frozen execution bindings and tests must be checked against that change. No one should append an amendment event by hand or rely on a one-process override.

The six named proposed children above, excluding DeepSeek low and Mistral, total **$6.60**, so they cannot all be funded under the approved $12.38 ceiling. For scale, the proposed $0.40 Gemma child plus $1.00 and $0.80 Qwen27 children total $2.20 and would leave **$0.19967548250**, assuming the ledger balance does not change. This arithmetic is not stage admission; all three still need fresh route checks and separate smoke reviews.

The earlier [28 September $17 proposal](EXPANDED_REPEAT_BUDGET_2026-09-28.md) requested a $7 increase and is now a historical, **unapproved** alternative to the user's narrower $2.38 authorization. It assigned $5 to eight then-pending fresh hosted triples and $2 to Gemini 3.1 Pro high. That $5 estimate included Qwen reasoning-off and DeepSeek reasoning-off, which have since closed; DeepSeek low is interrupted; Mistral 119B was excluded and still lacks a whole-series estimate. Neither the approved $12.38 ceiling nor the old $17 proposal guarantees completion of the full hosted roster. A child ceiling reserves project capacity, not permission to dispatch. Any revised allocation for DeepSeek low or Mistral needs its own evidence, and route prices, provider capacity and ledger headroom must be checked again before admission.
