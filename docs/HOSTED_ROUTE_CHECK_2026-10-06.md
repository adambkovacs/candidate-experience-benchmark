# Hosted route check · 6 October 2026

## Latest check, 08:59 UTC

A fresh root fetch supersedes the availability observation below. The exact `open-inference/fp4` endpoint is listed with **status -2**, not the required available status 0. Its reported prices also differ: $0.0495/M input, $1.32/M output and $0.0165/M cached input. The runner must refuse this snapshot. No model request, reservation or allocation was made. The earlier price calculation remains a dated observation and cannot authorize execution now.

The [archived audit](../results/route-audits/deepseek-fourth-price-20261006/audit.json) binds the complete public [model catalog](../results/route-audits/deepseek-fourth-price-20261006/models.raw.json) and [endpoint response](../results/route-audits/deepseek-fourth-price-20261006/endpoints.raw.json). Another admission needs a fresh available exact route, verified prices and budget checks; changing the provider is not authorized by this failure.

## Earlier check, 08:43 UTC

Read-only audit at **2026-10-06 08:43 UTC**. No inference, paid request, budget write, or credential value was accessed. This audit note is the only file created by the audit.

## DeepSeek low suffix

The current public OpenRouter endpoint response lists the exact DeepSeek V4.1 Flash provider route required by the prepared suffix: `OpenInference`, tag `open-inference/fp4`, quantization `fp4`, endpoint status `0`, context `1,048,576`, maximum completion `943,718`. Current rates are **$0.0033/M input** and **$3.30/M output**. Status and catalog presence establish public listing only; they do not prove account entitlement, usable quota, or successful inference.

The saved 2 October route receipt recorded zero exact endpoint matches. The previously reviewed price successor bounded output at $0.50/M; the prepared third suffix raises that ceiling only to $1.20/M and retains a $0.10/M input ceiling. Both reject the live $3.30/M output price. The exact 10-record suffix remains DEV-051–060; prior errors and invalid output are retained, and those records must not be replayed.

Using the existing reservation rule (`context × input ceiling + 4,096 × output ceiling`), a successor retaining the $0.10/M input ceiling and raising output to $3.30/M would reserve **$0.1183744 per request**, or **$1.183744 for 10 requests**. Its current $0.25 child allocation is short by **$0.933744**. A separately reviewed successor using the current catalog input rate as its input ceiling ($0.0033/M) and $3.30/M output would reserve **$0.0169771008 per request**, or **$0.169771008 for 10**; the existing $0.25 child cap would cover that calculated hold if a fresh admission verifies unchanged route/rates and all other gates.

Read-only replay of the current ledgers found $0.48041261750 unallocated under the $12.38 OpenRouter cap (no pending attempts, blocked state, or active partitions) and $0.50818040 unheld under the separate $10 cross-provider authority. These are ledger headroom figures, not account balance or spending approval. Thus the first price-ceiling option does not fit either authority; the second calculation fits both at a $0.25 hold, before any new reservation. No hold was created.

Next gate: prepare a distinct price-bound continuation that preserves the exact ten unsent IDs and all failed outcomes; independently review it; recheck the public endpoint and prices; and verify both ledgers, access, and request limits immediately before any allocation or dispatch. The existing v1 runner cannot pass its price check at the current rates.

## Cloudflare Clef

A read-only connected-app Cloudflare API request for account model search, billable-usage info, and billing history returned `10000: Authentication error`. No account identifier or credential was recorded. This means current read-only account access could not be verified; it is not evidence that the account lacks quota or that the provider rejected inference. No current quota, entitlement, Clef route, or charges were established. Saved receipts and the $10 authority ledger retain their prior Cloudflare holds, but these do not prove present access or remaining provider quota.

## Sources

- [OpenRouter DeepSeek endpoint catalog](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints) · live unauthenticated GET at 08:43 UTC.
- [OpenRouter model catalog](https://openrouter.ai/api/v1/models) · endpoint identity is catalog metadata, not an account-specific entitlement check.
- [Saved route-block receipt](../results/repeatability-v1/deepseek-low-fresh3-v2/third-interruption-suffix-051-060-v1/blocked-route-20261002T164956Z.json) · exact route absent on 2 October.
- [Prepared suffix manifest](../results/repeatability-v1/deepseek-low-fresh3-v2/third-interruption-suffix-051-060-v1/manifest.json) and [runner](../scripts/deepseek_low_third_suffix_v1.py) · exact suffix, ceilings, 4,096 output-token bound, and $0.25 child cap.
- [Reviewed second price successor](../scripts/deepseek_low_price_successor_v2.py) · saved price bounds and fresh-route gate.
- [Cloudflare model search API](https://developers.cloudflare.com/api/resources/ai/subresources/models/methods/search/) and [billing usage API](https://developers.cloudflare.com/api/resources/billing/subresources/usage/methods/get/) · read-only endpoints attempted through the connected app; authentication failed.
