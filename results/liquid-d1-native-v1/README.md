# Liquid d1 native Decisions: offline preparation

Status: **prepared, not admitted**. No request, allocation, authority hold or credentialed account check was made for this preparation. The [public OpenRouter endpoint record](https://openrouter.ai/api/v1/models/liquid/d1/endpoints) was fetched on 6 October 2026 and saved as `endpoint-public.json`; public availability is not account access. [OpenRouter's Decisions example](https://openrouter.ai/blog/insights/what-is-jev/) identifies the intended `POST /api/alpha/decisions` transport. The [Liquid decision-model guide](https://docs.liquid.ai/lfm/models/decision-models) describes the native state/question contract.

The exact request alias is `liquid/d1`, pinned to Liquid's sole published `liquid` endpoint `liquid/d1-20260930`, 65,536-token context, `text->decisions`, and four typed Choice questions. `plan.json` binds the input-only 60 development records, the policy, frozen Jev question definitions and native P1/P2 instruction suffixes, the public endpoint snapshot and runner sources. It declares P0, P1 and P2 across fresh passes 1, 2 and 3: nine distinct 60-record phases. Repeated passes use the same request bytes; no seed control is published. Only fresh1/P0 DEV-001 through DEV-003 is wired for the first smoke. The other phases are planned but have no dispatch path here. No reference labels enter requests.

The catalog reports $0.04 per million prompt tokens, $0.04 per million cache-read tokens, zero completion price and zero discount. [Liquid's usage contract](https://docs.liquid.ai/lfm/models/decision-models#your-first-call) says input tokens are totaled across questions and each question is charged for its text. This plan therefore reserves **four full 65,536-token contexts**, or **$0.01048576 per request**. The three-record smoke needs a new **$0.03145728** OpenRouter child allocation and an equal additional-pool authority hold. This is a reservation ceiling based on the published context and tariff, not observed cost or proof that all rendered requests fit. The catalog labels its tokenizer `Other` and supplies no provider tokenizer. After an admitted smoke, inspect returned `usage.input_tokens`, model/provider identity, all four Choice distributions and raw responses. A completed 60-record pass still requires its own context and funding review. The full-context planning ceilings are $0.6291456 per 60-record phase and $5.6623104 for all nine phases; neither is allocated here.

Before any request, the root reviewer must independently check the current account balance, exact live route and the prepared plan. The root must allocate a distinct `$0.03145728` v4 child with partition ID `liquid-d1-native-fresh1-p0-smoke-v1`, model `liquid/d1`, provider `Liquid`, reasoning `native-decisions-P0-smoke`; create a matching v3 additional OpenRouter authority hold using the source digest from `scripts/liquid_d1_smoke_v1.py:hold_source`; and write `smoke.root-review.json` with the exact fields from `expected_receipt` plus a nonempty `reviewer`. The runner verifies those bindings, live route and full three-request child reserve before it creates a no-replay claim. Each request rechecks the route and reserves its four-question context ceiling before sending. Raw HTTP bytes and attempt accounting are saved; any unknown cost retains its full reservation and stops the stage. There are no automatic retries. Keep raw response and ledger files private; only immutable, reviewed evidence belongs in a checkpoint. The intended command, only **after** those gates, is:

```sh
PYTHONPATH=scripts python3 scripts/liquid_d1_smoke_v1.py run \
  --receipt results/liquid-d1-native-v1/smoke.root-review.json \
  --budget results/liquid-d1-native-v1/budget-manifest.json
```

Offline verification needs no credential and makes no inference request:

```sh
PYTHONPATH=scripts python3 scripts/liquid_d1_native_v1.py verify
PYTHONPATH=scripts python3 -m unittest tests.test_liquid_d1_native_v1
```
