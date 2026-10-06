# Remaining decision-route dispositions, 6 October 2026

Checked against public provider pages and catalogs on 6 October 2026. This is a route audit for the candidates already named in the [remaining roster](REMAINING_ROSTER_2026-10-06.md#decision-model-routes-without-a-full-run). It made no inference request, account probe, allocation or admission. The latest [hosted scope](CURRENT_GOALS.md#scope-update-6-october-2026-hosted-completion-and-cloudflare-approval) directs new work to OpenRouter first and allows worthwhile exact Cloudflare decision-model routes when unavailable there. Remaining direct-provider work for the first three candidates below is excluded from execution under that scope. Their zero-attempt history stays in the roster.

## Fastino GLiNER2.5-Decide

Fastino's unauthenticated [model catalog](https://api.fastino.ai/v1/models) and [base-model catalog](https://api.fastino.ai/v1/base-models) list exact hosted ID `fastino/GLiNER-2.5-Decide`, non-deprecated, with an 8,192-token input limit and $0.03 per million input tokens ($0 output). The [offline preflight](GLINER_NEXT_V1_PREFLIGHT_2026-10-02.md) built 180 requests but did not prove token fit, account access or the four-head response contract. No exact OpenRouter or Cloudflare route was verified. Direct Fastino work is outside the current execution scope; preserve zero inference attempts and the offline preflight.

## Alibaba `decision-model-preview`

The official [model page](https://www.alibabacloud.com/help/en/model-studio/decision-model-preview) identifies a 65,536-token decision model. The [System One API reference](https://www.alibabacloud.com/help/en/model-studio/decision-model-api) uses a Singapore workspace endpoint. The [pricing page](https://www.alibabacloud.com/help/en/model-studio/model-pricing) lists a limited-time free offer, without a numeric price after it ends. Workspace, entitlement and a bounded account tariff remain unverified. No exact OpenRouter or Cloudflare route was verified. Direct Alibaba work is outside the current execution scope; preserve zero admitted requests.

## Nace Drex

[Nace's Drex page](https://www.nace.ai/drex) describes Drex 1.5, a native per-option probability response, up to 128,000 tokens of context and managed access. The inspected public page gives no reproducible managed API model ID or numeric tariff. No exact OpenRouter or Cloudflare route was verified. Direct Nace work is outside the current execution scope; preserve zero admitted requests. The playground is not a pinned benchmark route.

## Jev through Cloudflare

[Cloudflare's model page](https://developers.cloudflare.com/ai/models/typesafe/jev/) lists `typesafe/jev`, a 32,000-token context, native Choice questions and $0.042 per million input tokens ($0 output). Its sample response says `jev-1.13.0`; that example does not establish the version a live request would return. This documented, available optional host comparison remains on the standing roster. OpenRouter Jev results do not fill it or make it an independent model. A Cloudflare wrapper, live account access, returned-version check and reviewed admission would be needed before any request. This audit does not declare the route excluded or authorize a run.

The public [OpenRouter model list](https://openrouter.ai/api/v1/models) showed no exact GLiNER, Alibaba preview or Drex ID at this check. Guessed individual paths for those IDs returned HTTP 404. The list has omitted other individually reachable decision models in prior checks, so this is evidence of no verified route, not proof that a route cannot exist. This audit found no exact Cloudflare listing for those three candidates. Recheck the exact provider interface if either catalog changes; do not substitute a similarly named chat model, size or checkpoint.
