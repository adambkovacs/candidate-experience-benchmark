# Cost check: provider-reported charges for the quoted runs

Date: 2026-10-08. Method: read-only. The only provider calls were GETs: the OpenRouter generation endpoint (once per saved generation id), the OpenRouter key and credits endpoints, a model list and a few route probes against the TypeSafe API, and one Cloudflare billing read. No inference was sent and no money was spent. No key was printed or written. The raw per-generation results stayed in the session scratchpad, not in the repo.

## Verdict

- **Every OpenRouter-routed run quoted on the slides is a known provider charge.** All 15,135 saved generation ids that OpenRouter still returns sum to $12.653729. Each quoted run matches the project feeds to the last digit. The one exception is a 2e-8 rounding difference on the Mistral row.
- **Clef moves from estimate to known charge.** The synthesis calls $0.03184656 a "list-price input estimate". OpenRouter's records for the same 60 requests report exactly that total, billed by Cloudflare through OpenRouter. The nine-run Clef series ($0.31128624) is also a known charge.
- **Jev direct on the TypeSafe API stays an estimate.** TypeSafe documents no usage or billing API, and the key gets 404 on every probed route. The $0.00589092 is saved input tokens times the published $0.042 per million.
- **Jev via OpenRouter is a known charge of $0.00589092 per P0 pass.** It used the same 140,260 input tokens at the same price, so the OpenRouter route adds no markup.
- **Unresolved:** Cloudflare's own account billing, TypeSafe's own invoice, and about $0.62 of OpenRouter key usage that no saved generation id explains (details at the end).

## Slide label recommendation

| Quoted figure | Label |
|---|---|
| Seven native decision models, fresh1/P0 (Clef, Clef Flash, Luna, Perplexity, Solar, Liquid, Tev) | known charge (provider-reported via OpenRouter) |
| Nine-run series totals for the same models | known charge (Clef Flash and Solar series include one unknown-charge bound in the project feed; see section 2) |
| Jev 1.13 via OpenRouter native, $0.00589092 | known charge |
| Jev 1.13 direct on TypeSafe, same figure | estimate (saved input tokens at the published price; no bill available) |
| Gemma 4 26B on, Qwen3.8 27B low, Gemini and DeepSeek paid runs | known charge (observed), as already labelled |
| Claude Opus 5.5 and Sonnet 5.5 subscription runs | estimate (API-equivalent; outside this check) |

## 1. OpenRouter: decision-model and Jev native runs

Charge is the sum of `total_cost` from the generation endpoint over the run's saved generation ids, taken from each run's raw or attempts jsonl. Tokens are OpenRouter's native counts. Decision-model charges are input-only: Clef is $0.24 per million input tokens, and the Jev route bills $0.042 per million. "Output tokens" for decision models are not billed. Sources: `results/clef-openrouter-v1`, `results/perplexity-decider-v1`, `results/solar-decide-native-full-v1`, `results/tev-native-v1`, `results/liquid-d1-native-v1`, `results/route-audits/jev-authority-v2-20261006`.

| Run | Provider (OpenRouter-reported) | Requests | Input tokens | Output tokens | Charge USD (generation API) | Project feed / synthesis value | Match |
|---|---|---:|---:|---:|---:|---:|---|
| Clef (Cloudflare Clef) | Cloudflare | 60 | 132,694 | 0 | 0.03184656 | 0.03184656 | exact |
| Clef Flash | Cloudflare | 60 | 132,694 | 0 | 0.01194246 | 0.01194246 | exact |
| Luna Decisions | OpenAI | 60 | 133,523 | 0 | 0.01335230 | 0.0133523 | exact |
| Perplexity Decider | Perplexity | 60 | 385,684 | 240 | 0.01542736 | 0.01542736 | exact |
| Solar Decide | Upstage | 60 | 441,340 | 240 | 0.02206700 | 0.022067 | exact |
| Liquid d1 | Liquid | 60 | 392,228 | 0 | 0.01568912 | 0.01568912 | exact |
| Tev 1 4B | Together | 60 | 389,116 | 480 | 0.01634287 | 0.016342872 | exact |
| Jev 1.13 via OpenRouter native P0 fresh1 | TypeSafe | 60 | 140,260 | 11,176 | 0.00589092 | 0.00589092 | exact |
| Jev 1.13 via OpenRouter native P0 fresh2 | TypeSafe | 60 | 140,260 | 11,176 | 0.00589092 | 0.00589092 | exact |
| Jev 1.13 via OpenRouter native P0 fresh3 | TypeSafe | 60 | 140,260 | 11,176 | 0.00589092 | 0.00589092 | exact |
All saved ids were present for these runs (60 of 60), so none relies on a fallback.

### Nine-run series (fresh1-3 by P0-P2, 60 requests per cell)

| Model | Generation-API charge for the series | Project value | Note |
|---|---:|---:|---|
| Clef | 0.31128624 | 0.31128624 | was labelled estimate; now known |
| Clef Flash | 0.11649969 | 0.11649969 | includes the 21-request exact-unsent P2 run; the project also carries a $0.02359296 unknown bound |
| Luna Decisions | 0.1304487 | 0.1304487 | |
| Perplexity Decider | 0.14295744 | 0.14296 | |
| Solar Decide | 0.20325475 | 0.20325475 | project adds a $0.1048576 unknown bound for one pass |
| Tev 1 4B | 0.15134213 | 0.151342128 | |
| Liquid d1 | 0.14549328 | not quoted | |

The unknown bounds are reservations for requests whose outcome was never recorded. The generation API cannot price a request whose id was not saved, so those bounds stay bounds.

## 2. OpenRouter: paid hosted runs (Gemini, Gemma, Qwen, DeepSeek and others)

Same method, using the evidence file named in `public-site/findings.json` (`charts.costAgreement.rows[].evidenceUrl`). Gemini rows are 6 batched requests of 10 reviews each; all other rows are 60 single-review requests. Every row matches the feed.

| Run | Provider | Requests | Input tokens | Output tokens | Charge USD (generation API) | Feed `actualUsd` | Match |
|---|---|---:|---:|---:|---:|---:|---|
| openrouter-paid-deepseek-v41-flash-off | OpenInference | 60 | 84,217 | 2,484 | 0.00268114 | 0.00268114 | exact |
| openrouter-paid-gemma4-31b-off | DeepInfra | 60 | 87,688 | 2,674 | 0.00555500 | 0.005555 | exact |
| openrouter-paid-gemma4-26b-a4b-off | DeepInfra | 60 | 87,688 | 2,171 | 0.00687630 | 0.0068763 | exact |
| openrouter-paid-qwen36-35b-a3b-off | AkashML | 60 | 85,950 | 2,706 | 0.00725760 | 0.0072576 | exact |
| openrouter-paid-mistral-small32-24b-venice-not-applicable | Venice | 60 | 85,851 | 2,727 | 0.00873026 | 0.00873028125 | exact |
| openrouter-qwen3-8b-off-json-object-p0 | Alibaba | 60 | 92,250 | 2,340 | 0.01185795 | 0.01185795 | exact |
| openrouter-paid-gemma4-31b-on | DeepInfra | 60 | 87,568 | 24,316 | 0.01303944 | 0.01303944 | exact |
| openrouter-paid-qwen3.8-27b-off | DeepInfra | 60 | 85,950 | 2,718 | 0.01304955 | 0.01304955 | exact |
| openrouter-paid-deepseek-v41-flash-low | OpenInference | 60 | 85,717 | 27,358 | 0.01513539 | 0.01513539 | exact |
| openrouter-paid-deepseek-v41-flash-high | OpenInference | 60 | 85,717 | 34,117 | 0.01852893 | 0.01852893 | exact |
| gemini36-flash-low-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 2,920 | 0.01937025 | 0.01937025 | exact |
| openrouter-qwen3-8b-on-json-object-p0 | Alibaba | 60 | 92,010 | 22,711 | 0.02109868 | 0.021098675 | exact |
| openrouter-paid-gemma4-26b-a4b-on | DeepInfra | 60 | 87,568 | 44,173 | 0.02114858 | 0.02114858 | exact |
| gemini38-low-p0-openrouter-v2 | Google AI Studio | 6 | 11,227 | 3,486 | 0.02149275 | 0.02149275 | exact |
| gemini37-flash-low-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 3,534 | 0.02167275 | 0.02167275 | exact |
| openrouter-qwen27-low-darkbloom-fp4 | Darkbloom | 60 | 98,730 | 21,869 | 0.04923720 | 0.0492372 | exact |
| gemini37-flash-medium-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 12,679 | 0.05596650 | 0.0559665 | exact |
| openrouter-paid-qwen3.8-27b-xhigh | DeepInfra | 60 | 88,110 | 26,540 | 0.06192060 | 0.0619206 | exact |
| gemini31-pro-preview-low-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 3,417 | 0.06345800 | 0.063458 | exact |
| openrouter-paid-qwen36-35b-a3b-on | AkashML | 60 | 85,830 | 65,478 | 0.06367960 | 0.0636796 | exact |
| gemini36-flash-medium-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 16,431 | 0.07003650 | 0.0700365 | exact |
| gemini38-flash-medium-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 21,827 | 0.09027150 | 0.0902715 | exact |
| gemini37-flash-high-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 28,258 | 0.11438775 | 0.11438775 | exact |
| gemini31-pro-preview-high-p0-openrouter-v3 | Google AI Studio | 6 | 11,227 | 19,531 | 0.25682600 | 0.256826 | exact |

Gemini 3.8 Flash low (probe v2) is the sum over its first batch file and its continuation file, six requests in total.

## 3. TypeSafe Jev, direct API

- **Billing visibility.** The docs at https://docs.typesafe.ai/llms.txt list no usage, billing or invoice page. The quickstart points to the web console (console.typesafe.ai) for the Playground and API keys only. GET probes of the usage, billing, account, me and credits routes on api.typesafe.ai all returned 404. The model list route returned 200.
- **Published price.** $0.042 per million input tokens, output tokens free (https://docs.typesafe.ai/models.md).
- **Estimate from saved usage** (`results/openjev/typesafe-*-v2*.jsonl`, field `usage`):

| Run | Requests | Input tokens | Output tokens | Estimate USD | Label |
|---|---:|---:|---:|---:|---|
| Smoke (typesafe-smoke-v2) | 3 | 7,007 | 558 | 0.00029429 | estimate |
| Development, reconciled 60 reviews (typesafe-development-v2-reconciled, built from the 45 ok rows of the first file plus the 15-row continuation) | 60 | 140,260 | 11,176 | 0.00589092 | estimate |
| Failed attempt DEV-046 (service_error, usage not recorded) | 1 | unknown | unknown | unknown | not priced; the project ledger holds a 0.002123688 reservation |

The project's own cumulative accounting for this route is $0.008308902. That is the sum of the three lines above with the failed attempt counted at its reservation, so it is an upper-bound ledger, not a bill. The feed row `typesafe-jev113-v2` in `results/comparison/REPORT.md` shows the partial 0.002123688, which is that failed-attempt reservation, not a charge for the 60-review pass.

- **Cross-check.** The OpenRouter route for the same model billed 140,260 input tokens at $0.00589092 per pass in each of three passes. The direct estimate equals it to the digit, so the estimate is almost certainly right. It is still unconfirmed against a TypeSafe invoice, and the slide should say estimate.
- **TypeSafe total spend.** Not obtainable without the console. Repeat direct passes (`results/repeatability-v1/typesafe-jev113-v2`) are not included in the table above.

## 4. Project totals

| Provider | Total | Basis |
|---|---:|---|
| OpenRouter, sum of every saved generation id | $12.653729 | 15,135 generations, generation API |
| OpenRouter, project ledger known charges | $12.653730 | `results/openrouter-paid-budget.jsonl`: partition known actuals $12.533953 plus direct settles $0.119777 |
| OpenRouter, ledger unknown-cost upper bounds | $3.883743 | reservations for requests with no recorded cost; bounds, not charges |
| OpenRouter, this key's lifetime usage | $13.273502 | `GET /api/v1/auth/key`, field `usage` |
| OpenRouter, whole account lifetime usage | $33.540133 of $40 credits | `GET /api/v1/credits`; includes other keys and other work, not just this project |
| OpenRouter, Cloudflare-provider spend inside the project total | $0.449 | Clef, Clef Flash and their smokes, billed through OpenRouter |
| Cloudflare account billing | unavailable | see below |
| TypeSafe direct | about $0.006 to $0.0083 | estimate or upper-bound ledger; no bill |

The ledger's known charges and the sum of generation records agree to one micro-dollar, which is independent confirmation of both. The project OpenRouter cap was $10, raised from $5; the key's lifetime usage of $13.27 is above it. The excess is explained by ledger bounds and, possibly, by use of the same key outside this project. This check cannot tell which.

The account endpoints returned the same OpenRouter account for the project `.env` and the codebuild `.env` (identical key). Account identity: OpenRouter user `user_38nKAimnpyqyA7u4PMNVG8lCWie`, workspace `7846db30-9bff-5f6f-9da5-da459903c9de`. The TypeSafe key is also identical in both files, and TypeSafe has no identity endpoint. There was no OPENJEV_API_KEY in either file.

## 5. What could not be resolved

1. **About $0.62 of key usage.** The key reports $13.273502; saved generation ids explain $12.653729. The gap sits inside the $3.88 of unknown-cost reservations (failed or interrupted requests whose id was never saved), but it could also be other use of the key.
2. **Cloudflare billing.** The Cloudflare token in `.env` is valid but `GET /accounts/{id}/billing/usage/paygo` returned authentication error 10000, the same failure `docs/CLOUDFLARE_BUDGET_2026-10-06.md` recorded. The direct Cloudflare runs in `results/clef-native-v1` (761 attempts, rate-based upper bound $0.259584) therefore remain an upper bound, not a charge. They are not the runs quoted on the slides; the slides use the OpenRouter-routed Clef runs.
3. **TypeSafe invoice.** No API; only the web console can confirm the Jev direct figure.
4. **One generation id returns 404** (a DeepSeek V4.1 Flash high P2 request in the prompt-comparison run). It is not in any quoted run.
5. **Jev native P1 and P2 fresh1 and fresh2.** Their attempt files are not at the expected path, so only P1 and P2 fresh3 were priced ($0.006405 and $0.00685104). They are not quoted as costs on slides.
6. **Subscription runs** (Claude, Codex) have no per-run provider bill by design; their figures stay API-equivalent estimates.
